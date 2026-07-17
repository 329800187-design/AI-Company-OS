"""
Performance Module — 性能优化工具

功能：
1. 数据库连接池
2. 异步工具
3. 缓存管理
4. 内存优化
"""
import asyncio
import sqlite3
import threading
import time
import weakref
from concurrent.futures import ThreadPoolExecutor
from contextlib import asynccontextmanager
from typing import Any, Callable, Dict, Optional
from functools import lru_cache

# ── 数据库连接池 ──────────────────────────────────────────────

class ConnectionPool:
    """SQLite 连接池"""

    def __init__(self, db_path: str, max_connections: int = 10):
        self.db_path = db_path
        self.max_connections = max_connections
        self._pool = []
        self._lock = threading.Lock()
        self._in_use = set()

    def get_connection(self) -> sqlite3.Connection:
        """获取连接"""
        with self._lock:
            # 尝试从池中获取
            while self._pool:
                conn = self._pool.pop()
                if self._is_valid(conn):
                    self._in_use.add(id(conn))
                    return conn

            # 创建新连接
            if len(self._in_use) < self.max_connections:
                conn = self._create_connection()
                self._in_use.add(id(conn))
                return conn

            # 等待连接释放
            raise ConnectionError("连接池已满，请稍后再试")

    def return_connection(self, conn: sqlite3.Connection):
        """归还连接"""
        with self._lock:
            conn_id = id(conn)
            if conn_id in self._in_use:
                self._in_use.remove(conn_id)
                if self._is_valid(conn):
                    self._pool.append(conn)
                else:
                    try:
                        conn.close()
                    except Exception:
                        pass

    def _create_connection(self) -> sqlite3.Connection:
        """创建新连接"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA foreign_keys=ON")
        conn.execute("PRAGMA busy_timeout=5000")
        return conn

    def _is_valid(self, conn: sqlite3.Connection) -> bool:
        """检查连接是否有效"""
        try:
            conn.execute("SELECT 1")
            return True
        except Exception:
            return False

    def close_all(self):
        """关闭所有连接"""
        with self._lock:
            for conn in self._pool:
                try:
                    conn.close()
                except Exception:
                    pass
            self._pool.clear()
            self._in_use.clear()

    @asynccontextmanager
    async def acquire(self):
        """异步上下文管理器"""
        conn = self.get_connection()
        try:
            yield conn
        finally:
            self.return_connection(conn)


# ── 异步工具 ──────────────────────────────────────────────────

class AsyncTaskRunner:
    """异步任务运行器"""

    def __init__(self, max_workers: int = 4):
        self.executor = ThreadPoolExecutor(max_workers=max_workers)
        self._tasks: Dict[str, asyncio.Task] = {}

    async def run_in_executor(self, func: Callable, *args) -> Any:
        """在线程池中运行同步函数"""
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(self.executor, func, *args)

    def submit_task(self, task_id: str, coro) -> asyncio.Task:
        """提交异步任务"""
        task = asyncio.create_task(coro)
        self._tasks[task_id] = task

        # 任务完成后清理
        task.add_done_callback(lambda t: self._tasks.pop(task_id, None))

        return task

    def cancel_task(self, task_id: str) -> bool:
        """取消任务"""
        task = self._tasks.get(task_id)
        if task and not task.done():
            task.cancel()
            return True
        return False

    def get_task(self, task_id: str) -> Optional[asyncio.Task]:
        """获取任务"""
        return self._tasks.get(task_id)

    def shutdown(self):
        """关闭线程池"""
        self.executor.shutdown(wait=False)


# ── 缓存管理 ──────────────────────────────────────────────────

class CacheManager:
    """简单的缓存管理器"""

    def __init__(self, max_size: int = 1000, ttl: int = 300):
        self.max_size = max_size
        self.ttl = ttl  # 秒
        self._cache: Dict[str, tuple] = {}  # {key: (value, expire_time)}
        self._lock = threading.Lock()

    def get(self, key: str) -> Optional[Any]:
        """获取缓存"""
        with self._lock:
            if key in self._cache:
                value, expire_time = self._cache[key]
                if time.time() < expire_time:
                    return value
                else:
                    del self._cache[key]
        return None

    def set(self, key: str, value: Any, ttl: int = None):
        """设置缓存"""
        with self._lock:
            # 清理过期缓存
            if len(self._cache) >= self.max_size:
                self._cleanup()

            expire_time = time.time() + (ttl or self.ttl)
            self._cache[key] = (value, expire_time)

    def delete(self, key: str):
        """删除缓存"""
        with self._lock:
            self._cache.pop(key, None)

    def clear(self):
        """清空缓存"""
        with self._lock:
            self._cache.clear()

    def _cleanup(self):
        """清理过期缓存"""
        now = time.time()
        expired_keys = [k for k, (_, exp) in self._cache.items() if now >= exp]
        for k in expired_keys:
            del self._cache[k]

        # 如果还是太多，删除最旧的
        if len(self._cache) >= self.max_size:
            sorted_keys = sorted(self._cache.keys(), key=lambda k: self._cache[k][1])
            for k in sorted_keys[:len(sorted_keys) // 2]:
                del self._cache[k]


# ── 内存优化 ──────────────────────────────────────────────────

class MemoryOptimizer:
    """内存优化器"""

    @staticmethod
    def get_memory_usage() -> Dict[str, Any]:
        """获取内存使用情况"""
        import psutil
        import os

        process = psutil.Process(os.getpid())
        memory_info = process.memory_info()

        return {
            "rss": memory_info.rss / 1024 / 1024,  # MB
            "vms": memory_info.vms / 1024 / 1024,  # MB
            "percent": process.memory_percent(),
        }

    @staticmethod
    def cleanup_garbage():
        """清理垃圾回收"""
        import gc
        gc.collect()

    @staticmethod
    def limit_cache_size(cache: dict, max_size: int):
        """限制缓存大小"""
        if len(cache) > max_size:
            # 删除最旧的 20%
            sorted_keys = sorted(cache.keys())
            remove_count = len(cache) - max_size + max_size // 5
            for key in sorted_keys[:remove_count]:
                del cache[key]


# ── 全局实例 ──────────────────────────────────────────────────

# 连接池（延迟初始化）
_connection_pool: Optional[ConnectionPool] = None

# 异步任务运行器
task_runner = AsyncTaskRunner(max_workers=4)

# 缓存管理器
cache_manager = CacheManager(max_size=1000, ttl=300)


def get_connection_pool(db_path: str = None) -> ConnectionPool:
    """获取连接池"""
    global _connection_pool
    if _connection_pool is None:
        if db_path is None:
            from backend.database.database import DB_PATH
            db_path = DB_PATH
        _connection_pool = ConnectionPool(db_path)
    return _connection_pool


def cleanup():
    """清理资源"""
    global _connection_pool
    if _connection_pool:
        _connection_pool.close_all()
        _connection_pool = None
    task_runner.shutdown()
    cache_manager.clear()
