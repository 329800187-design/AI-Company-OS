"""AI 使用量统计 — Token 计数器 + 成本估算

统计每次 AI API 调用的 token 使用量，提供查看接口。
支持 SQLite 持久化，重启后数据不丢失。
"""
import json
import os
import sqlite3
import threading
import time
import queue
from collections import defaultdict
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional

# ── 价格表（单位：元/百万 tokens）───────────────────────────
PRICING = {
    "deepseek": {"input": 0.5, "output": 2.0},      # DeepSeek-chat
    "openai":  {"input": 15.0, "output": 60.0},      # GPT-4o
    "claude":  {"input": 20.0, "output": 100.0},     # Claude Sonnet 4
}

# ── SQLite 持久化 ──────────────────────────────────────────
from backend.runtime_paths import DATABASE_PATH, ensure_user_data_dir

ensure_user_data_dir()
_DB_PATH = DATABASE_PATH
_persist_lock = threading.Lock()


def _get_persist_conn() -> sqlite3.Connection:
    """获取持久化连接"""
    conn = sqlite3.connect(str(_DB_PATH))
    conn.execute("PRAGMA journal_mode=WAL")
    return conn


def _init_persist():
    """初始化持久化表"""
    try:
        conn = _get_persist_conn()
        conn.execute("""
            CREATE TABLE IF NOT EXISTS usage_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                time TEXT NOT NULL,
                provider TEXT NOT NULL,
                model TEXT NOT NULL,
                prompt_tokens INTEGER DEFAULT 0,
                completion_tokens INTEGER DEFAULT 0,
                total_tokens INTEGER DEFAULT 0,
                cost_yuan REAL DEFAULT 0.0,
                source TEXT DEFAULT '',
                duration_ms INTEGER DEFAULT 0,
                success INTEGER DEFAULT 1
            )
        """)
        conn.execute("CREATE INDEX IF NOT EXISTS idx_usage_time ON usage_logs(time)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_usage_provider ON usage_logs(provider)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_usage_source ON usage_logs(source)")
        conn.commit()
    except Exception as e:
        print(f"[UsageStats] 持久化初始化失败: {e}")
    finally:
        conn.close()


# ── 内存存储（线程安全）────────────────────────────────────
_lock = threading.Lock()
_usage_log: List[Dict[str, Any]] = []
_counter = {
    "total_calls": 0,
    "total_prompt_tokens": 0,
    "total_completion_tokens": 0,
    "total_tokens": 0,
    "estimated_cost_yuan": 0.0,
}
_persist_initialized = False


def record_usage(
    provider: str,
    model: str,
    prompt_tokens: int = 0,
    completion_tokens: int = 0,
    source: str = "",
    duration_ms: int = 0,
    success: bool = True,
):
    """记录一次 AI API 调用

    Args:
        provider: deepseek/openai/claude
        model: 模型名
        prompt_tokens: 输入 tokens
        completion_tokens: 输出 tokens
        source: 调用来源（commander/ceo）
        duration_ms: 耗时
        success: 是否成功
    """
    global _persist_initialized

    total_tokens = prompt_tokens + completion_tokens
    pricing = PRICING.get(provider, {"input": 1.0, "output": 4.0})
    cost = (prompt_tokens / 1_000_000 * pricing["input"]) + \
           (completion_tokens / 1_000_000 * pricing["output"])

    record = {
        "time": datetime.now().isoformat(),
        "provider": provider,
        "model": model,
        "prompt_tokens": prompt_tokens,
        "completion_tokens": completion_tokens,
        "total_tokens": total_tokens,
        "cost_yuan": round(cost, 6),
        "source": source,
        "duration_ms": duration_ms,
        "success": success,
    }

    with _lock:
        _usage_log.append(record)
        _counter["total_calls"] += 1
        _counter["total_prompt_tokens"] += prompt_tokens
        _counter["total_completion_tokens"] += completion_tokens
        _counter["total_tokens"] += total_tokens
        _counter["estimated_cost_yuan"] = round(
            _counter["estimated_cost_yuan"] + cost, 4
        )

    # SQLite 持久化（首次调用时初始化，后台写入不阻塞主流程）
    if not _persist_initialized:
        _init_persist()
        _persist_initialized = True

    _persist_record(record)


def get_usage_stats(hours: int = 24) -> Dict:
    """获取使用量统计

    Args:
        hours: 统计过去多少小时的数据

    Returns:
        统计数据
    """
    cutoff = datetime.now() - timedelta(hours=hours)

    with _lock:
        recent = [r for r in _usage_log
                  if datetime.fromisoformat(r["time"]) >= cutoff]
        total = len(recent)
        prompt_tokens = sum(r["prompt_tokens"] for r in recent)
        completion_tokens = sum(r["completion_tokens"] for r in recent)
        total_tokens = prompt_tokens + completion_tokens
        cost = sum(r["cost_yuan"] for r in recent)
        success = sum(1 for r in recent if r["success"])
        failed = total - success

        # 按来源分组
        by_source = defaultdict(lambda: {"calls": 0, "tokens": 0, "cost": 0.0})
        for r in recent:
            s = r["source"] or "unknown"
            by_source[s]["calls"] += 1
            by_source[s]["tokens"] += r["total_tokens"]
            by_source[s]["cost"] += r["cost_yuan"]

    return {
        "period_hours": hours,
        "total_calls": total,
        "success_calls": success,
        "failed_calls": failed,
        "prompt_tokens": prompt_tokens,
        "completion_tokens": completion_tokens,
        "total_tokens": total_tokens,
        "estimated_cost_yuan": round(cost, 4),
        "by_source": dict(by_source),
    }


def get_all_time_stats() -> Dict:
    """获取所有时间的总使用量（含持久化数据）"""
    with _lock:
        c = dict(_counter)
        return c


def get_recent_calls(limit: int = 50) -> List[Dict]:
    """获取最近的调用记录（优先内存，回退 DB）"""
    with _lock:
        if _usage_log:
            return list(reversed(_usage_log[-limit:]))

    # 从 DB 加载
    try:
        conn = _get_persist_conn()
        rows = conn.execute(
            "SELECT * FROM usage_logs ORDER BY time DESC LIMIT ?", (limit,)
        ).fetchall()
        conn.close()
        return [{
            "time": r[1], "provider": r[2], "model": r[3],
            "prompt_tokens": r[4], "completion_tokens": r[5],
            "total_tokens": r[6], "cost_yuan": r[7],
            "source": r[8], "duration_ms": r[9], "success": bool(r[10]),
        } for r in rows]
    except Exception:
        return []


def load_history_from_db(days: int = 7) -> List[Dict]:
    """从数据库加载历史使用记录"""
    try:
        cutoff = (datetime.now() - timedelta(days=days)).isoformat()
        conn = _get_persist_conn()
        rows = conn.execute(
            "SELECT * FROM usage_logs WHERE time >= ? ORDER BY time DESC LIMIT 1000",
            (cutoff,)
        ).fetchall()
        conn.close()
        records = [{
            "time": r[1], "provider": r[2], "model": r[3],
            "prompt_tokens": r[4], "completion_tokens": r[5],
            "total_tokens": r[6], "cost_yuan": r[7],
            "source": r[8], "duration_ms": r[9], "success": bool(r[10]),
        } for r in rows]

        # 合并到内存
        with _lock:
            existing_times = {r["time"] for r in _usage_log}
            for rec in records:
                if rec["time"] not in existing_times:
                    _usage_log.append(rec)
                    _counter["total_calls"] += 1
                    _counter["total_prompt_tokens"] += rec["prompt_tokens"]
                    _counter["total_completion_tokens"] += rec["completion_tokens"]
                    _counter["total_tokens"] += rec["total_tokens"]
                    _counter["estimated_cost_yuan"] = round(
                        _counter["estimated_cost_yuan"] + rec["cost_yuan"], 4
                    )

        return records
    except Exception as e:
        print(f"[UsageStats] 加载历史失败: {e}")
        return []


# ── 后台写队列（单线程，避免 thread explosion）───────────────
_write_queue: queue.Queue = queue.Queue()

def _bg_writer():
    """单一线程循环消费写入队列"""
    conn = None
    try:
        conn = _get_persist_conn()
        while True:
            record = _write_queue.get()
            if record is None:  # 停止信号
                break
            try:
                conn.execute(
                    """INSERT INTO usage_logs (time, provider, model, prompt_tokens,
                       completion_tokens, total_tokens, cost_yuan, source, duration_ms, success)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    (record["time"], record["provider"], record["model"],
                     record["prompt_tokens"], record["completion_tokens"],
                     record["total_tokens"], record["cost_yuan"],
                     record["source"], record["duration_ms"], int(record["success"]))
                )
                conn.commit()
            except Exception as e:
                print(f"[UsageStats] 持久化写入失败: {e}")
    except Exception as e:
        print(f"[UsageStats] 后台写入线程异常: {e}")
    finally:
        if conn:
            try:
                conn.close()
            except Exception:
                pass

_writer_thread = threading.Thread(target=_bg_writer, daemon=True)
_writer_started = False


def _start_writer():
    """确保后台写入线程已启动"""
    global _writer_started
    if not _writer_started:
        _writer_started = True
        _writer_thread.start()


def _persist_record(record: Dict):
    """将记录入队，后台单线程异步写入 SQLite（不阻塞调用者）"""
    _start_writer()
    _write_queue.put(record)


def _stop_writer():
    """停止后台写入线程（进程退出时调用）"""
    _write_queue.put(None)
    _writer_thread.join(timeout=3)


# 启动时自动加载历史数据（延迟导入，避免循环依赖）
def _startup_load():
    try:
        _init_persist()
        _start_writer()
        load_history_from_db(days=7)
    except Exception:
        pass

_startup_load()
