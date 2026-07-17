"""轻量级后台任务队列 — 基于 asyncio + ThreadPoolExecutor
无需 Redis/Celery，适合单进程部署"""

import asyncio
import threading
import uuid
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from typing import Any, Callable, Dict, List, Optional, Tuple

from fastapi import WebSocket


class BackgroundTaskManager:
    """轻量级后台任务队列

    管理异步提交的后台任务，支持：
    - ThreadPoolExecutor 执行同步代码
    - WebSocket 实时推送进度
    - 任务状态追踪（queued → running → completed/failed）
    - 取消任务
    """

    def __init__(self, max_workers: int = 4):
        """
        Args:
            max_workers: 线程池最大并行数
        """
        self._lock = threading.Lock()                 # 保护所有共享状态
        self._tasks: Dict[str, Dict] = {}          # task_id -> task info
        self._ws_clients: Dict[str, List[WebSocket]] = {}  # task_id -> websocket clients
        self._futures: Dict[str, Any] = {}          # task_id -> Future
        self._cancelled: set = set()                 # 已取消的 task_id
        self._executor = ThreadPoolExecutor(max_workers=max_workers)
        self._cleanup_started = False
        self._start_auto_cleanup()

    # ── 任务提交 ──────────────────────────────────────────

    def submit(self, task_id: str, fn: Callable, *args, **kwargs) -> str:
        """提交任务到线程池执行

        Args:
            task_id: 任务唯一 ID
            fn: 要执行的同步函数
            *args, **kwargs: 传给 fn 的参数

        Returns:
            task_id

        任务状态流转: queued → running → completed / failed
        """
        now = datetime.now().isoformat()
        with self._lock:
            self._tasks[task_id] = {
                "task_id": task_id,
                "status": "queued",
                "progress": 0,
                "created_at": now,
                "started_at": None,
                "completed_at": None,
                "result": None,
                "error": None,
            }

        # 在线程池中执行
        loop = asyncio.get_event_loop()
        future = loop.run_in_executor(self._executor, self._run_task, task_id, fn, args, kwargs)
        with self._lock:
            self._futures[task_id] = future

        # 任务完成后的回调（在事件循环中运行）
        future.add_done_callback(lambda f: self._on_task_done(task_id, f))

        return task_id

    def _run_task(self, task_id: str, fn: Callable, args: Tuple, kwargs: Dict) -> Any:
        """在线程池中实际执行任务"""
        # 检查是否已取消（under lock）
        with self._lock:
            if task_id in self._cancelled:
                return None
            self._tasks[task_id]["status"] = "running"
            self._tasks[task_id]["started_at"] = datetime.now().isoformat()

        try:
            result = fn(*args, **kwargs)
            with self._lock:
                if task_id in self._cancelled:
                    return None
                self._tasks[task_id]["result"] = result
                self._tasks[task_id]["status"] = "completed"
                self._tasks[task_id]["completed_at"] = datetime.now().isoformat()
            return result
        except Exception as e:
            with self._lock:
                self._tasks[task_id]["status"] = "failed"
                self._tasks[task_id]["error"] = str(e)
                self._tasks[task_id]["completed_at"] = datetime.now().isoformat()
            raise

    def _on_task_done(self, task_id: str, future):
        """任务完成后的清理（在事件循环中 + 5分钟后自动清理）"""
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                task = self.get_task(task_id)
                if task:
                    coro = self.push_progress(task_id, {
                        "type": "task_completed" if task["status"] == "completed" else "task_failed",
                        "task_id": task_id,
                        "status": task["status"],
                        "result": task.get("result"),
                        "error": task.get("error"),
                    })
                    asyncio.run_coroutine_threadsafe(coro, loop)
        except RuntimeError:
            pass  # Event loop 不可用（测试/非异步环境正常）
        except Exception as e:
            print(f"[TaskQueue] _on_task_done 推送失败: {e}")
        finally:
            # 5分钟后清理任务记录
            def _delayed_cleanup():
                time.sleep(300)
                with self._lock:
                    self._tasks.pop(task_id, None)
                    self._futures.pop(task_id, None)
                    self._cancelled.discard(task_id)
                    self._ws_clients.pop(task_id, None)
            threading.Thread(target=_delayed_cleanup, daemon=True).start()

    # ── WebSocket 推送 ────────────────────────────────────

    async def push_progress(self, task_id: str, data: Dict):
        """向所有订阅该 task_id 的 WebSocket 客户端推送进度

        Args:
            task_id: 任务 ID
            data: 要推送的数据（会自动补充 task_id 和时间戳）
        """
        data["task_id"] = task_id
        data["timestamp"] = datetime.now().isoformat()

        with self._lock:
            clients = list(self._ws_clients.get(task_id, []))
        if not clients:
            return

        # 同时推送多个客户端
        disconnected = []
        for ws in clients:
            try:
                await ws.send_json(data)
            except Exception:
                disconnected.append(ws)

        # 清理已断开的客户端
        for ws in disconnected:
            await self.unsubscribe(task_id, ws)

    # ── 任务查询 ──────────────────────────────────────────

    def get_task(self, task_id: str) -> Optional[Dict]:
        """获取任务当前状态和信息"""
        with self._lock:
            return dict(self._tasks.get(task_id, {})) if task_id in self._tasks else None

    def list_tasks(self, limit: int = 50) -> List[Dict]:
        """列出所有任务（按创建时间倒序）"""
        with self._lock:
            tasks = sorted(self._tasks.values(), key=lambda t: t.get("created_at", ""), reverse=True)
            return tasks[:limit]

    # ── 取消任务 ──────────────────────────────────────────

    def cancel(self, task_id: str):
        """取消任务（标记为取消，实际执行无法立即停止）"""
        with self._lock:
            if task_id in self._tasks and self._tasks[task_id]["status"] in ("queued", "running"):
                self._cancelled.add(task_id)
                self._tasks[task_id]["status"] = "cancelled"
                self._tasks[task_id]["completed_at"] = datetime.now().isoformat()
                # 尝试取消 future
                future = self._futures.get(task_id)
                if future and not future.done():
                    future.cancel()

    # ── WebSocket 订阅管理 ────────────────────────────────

    async def subscribe(self, task_id: str, ws: WebSocket):
        """WebSocket 客户端订阅某个任务的进度推送

        Args:
            task_id: 要订阅的任务 ID
            ws: WebSocket 连接
        """
        with self._lock:
            if task_id not in self._ws_clients:
                self._ws_clients[task_id] = []
            self._ws_clients[task_id].append(ws)

        # 立即推送当前状态（如果任务已存在，get_task 自身加锁）
        task = self.get_task(task_id)
        if task:
            await ws.send_json({
                "type": "task_status",
                "task_id": task_id,
                "status": task["status"],
                "task": task,
            })

    async def unsubscribe(self, task_id: str, ws: WebSocket):
        """取消 WebSocket 客户端对某个任务的订阅

        Args:
            task_id: 任务 ID
            ws: 要取消的 WebSocket 连接
        """
        with self._lock:
            clients = self._ws_clients.get(task_id, [])
            if ws in clients:
                clients.remove(ws)
            # 清理空列表
            if task_id in self._ws_clients and not self._ws_clients[task_id]:
                del self._ws_clients[task_id]

    # ── 自动清理 ──────────────────────────────────────────

    def _start_auto_cleanup(self):
        """启动后台线程，定期清理已完成/失败的旧任务"""
        if self._cleanup_started:
            return
        self._cleanup_started = True

        def _cleanup_loop():
            while True:
                time.sleep(300)  # 每 5 分钟清理一次
                try:
                    self.cleanup(older_than_seconds=600)  # 清理 10 分钟前的任务
                except Exception:
                    pass

        t = threading.Thread(target=_cleanup_loop, daemon=True, name="task-cleanup")
        t.start()

    def cleanup(self, older_than_seconds: int = 600):
        """清理已完成/失败超过指定时间的任务（线程安全）

        Args:
            older_than_seconds: 超过多少秒的任务将被清理
        """
        with self._lock:
            now = time.time()
            to_remove = []
            for task_id, task in list(self._tasks.items()):
                if task["status"] in ("completed", "failed", "cancelled"):
                    completed_at = task.get("completed_at")
                    if completed_at:
                        try:
                            dt = datetime.fromisoformat(completed_at)
                            if (now - dt.timestamp()) > older_than_seconds:
                                to_remove.append(task_id)
                        except Exception:
                            pass
            for task_id in to_remove:
                self._tasks.pop(task_id, None)
                self._futures.pop(task_id, None)
                self._cancelled.discard(task_id)
                self._ws_clients.pop(task_id, None)
