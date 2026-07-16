"""
SQLite 持久化数据库

提供:
- sessions: 指挥官执行会话
- steps: 会话中的执行步骤
- tasks: 任务数据
"""
import sqlite3
import json
import os
import threading
from datetime import datetime
from typing import Any, Dict, List, Optional
from contextlib import contextmanager

# 尝试导入连接池
try:
    from backend.performance import get_connection_pool
    USE_POOL = True
except ImportError:
    USE_POOL = False


DB_PATH = os.path.join(os.path.dirname(__file__), "company_os.db")
_local = threading.local()
_all_connections: list = []  # 跟踪所有连接以便 atexit 清理


def get_conn() -> sqlite3.Connection:
    """每个线程获取独立连接"""
    if USE_POOL:
        pool = get_connection_pool(DB_PATH)
        return pool.get_connection()

    if not hasattr(_local, "conn") or _local.conn is None:
        _local.conn = sqlite3.connect(DB_PATH)
        _local.conn.row_factory = sqlite3.Row
        _local.conn.execute("PRAGMA journal_mode=WAL")
        _local.conn.execute("PRAGMA foreign_keys=ON")
        _local.conn.execute("PRAGMA busy_timeout=5000")  # 5 秒超时避免 SQLITE_BUSY
        _all_connections.append(_local.conn)
    return _local.conn


def return_conn(conn: sqlite3.Connection):
    """归还连接到池"""
    if USE_POOL:
        pool = get_connection_pool(DB_PATH)
        pool.return_connection(conn)


def close_all_connections():
    """关闭所有数据库连接（进程退出时调用）"""
    if USE_POOL:
        pool = get_connection_pool(DB_PATH)
        pool.close_all()
    else:
        for conn in _all_connections:
            try:
                conn.close()
            except Exception:
                pass
        _all_connections.clear()


# 注册进程退出时自动清理
import atexit
atexit.register(close_all_connections)


@contextmanager
def get_db():
    """上下文管理器用法: with get_db() as db:
    成功时自动 commit（SQLITE_BUSY 时重试），异常时自动 rollback"""
    import time as _time_
    conn = get_conn()
    try:
        yield conn
    except Exception:
        conn.rollback()
        raise
    else:
        # 面对并发写入，SQLITE_BUSY 重试最多 3 次
        for attempt in range(3):
            try:
                conn.commit()
                break
            except sqlite3.OperationalError as e:
                if "database is locked" in str(e) and attempt < 2:
                    _time_.sleep(0.1 * (attempt + 1))  # 100ms, 200ms 递增
                else:
                    raise
    finally:
        if USE_POOL:
            return_conn(conn)


def init_db():
    """建表（幂等）"""
    conn = get_conn()
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS sessions (
            session_id TEXT PRIMARY KEY,
            goal TEXT NOT NULL,
            status TEXT DEFAULT 'active',
            total_steps INTEGER DEFAULT 0,
            completed_steps INTEGER DEFAULT 0,
            summary TEXT,
            created_at TEXT DEFAULT (datetime('now','localtime')),
            updated_at TEXT DEFAULT (datetime('now','localtime')),
            completed_at TEXT
        );

        CREATE TABLE IF NOT EXISTS steps (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id TEXT NOT NULL,
            step_number INTEGER NOT NULL,
            description TEXT,
            assigned_agent TEXT,
            task_id TEXT,
            details_json TEXT,
            status TEXT DEFAULT 'pending',
            result_summary TEXT,
            decision TEXT,
            decision_detail TEXT,
            created_at TEXT DEFAULT (datetime('now','localtime')),
            updated_at TEXT DEFAULT (datetime('now','localtime')),
            FOREIGN KEY (session_id) REFERENCES sessions(session_id)
        );

        CREATE TABLE IF NOT EXISTS tasks (
            task_id TEXT PRIMARY KEY,
            session_id TEXT,
            step_number INTEGER,
            data TEXT NOT NULL,
            result TEXT,
            status TEXT DEFAULT 'todo',
            created_at TEXT DEFAULT (datetime('now','localtime'))
        );
    """)
    # 迁移: 为旧数据库添加 details_json 列
    try:
        conn.execute("ALTER TABLE steps ADD COLUMN details_json TEXT")
    except Exception:
        pass  # 列已存在
    conn.commit()


# ====== Sessions ======

class SessionDB:
    @staticmethod
    def create(session_id: str, goal: str, total_steps: int = 0) -> Dict[str, Any]:
        with get_db() as db:
            db.execute(
                "INSERT OR IGNORE INTO sessions (session_id, goal, total_steps) VALUES (?, ?, ?)",
                (session_id, goal, total_steps)
            )
        return SessionDB.get(session_id)

    @staticmethod
    def get(session_id: str) -> Optional[Dict[str, Any]]:
        with get_db() as db:
            row = db.execute("SELECT * FROM sessions WHERE session_id = ?", (session_id,)).fetchone()
            return dict(row) if row else None

    @staticmethod
    def list_all(limit: int = 20) -> List[Dict[str, Any]]:
        with get_db() as db:
            rows = db.execute("SELECT * FROM sessions ORDER BY created_at DESC LIMIT ?", (limit,)).fetchall()
            return [dict(r) for r in rows]

    @staticmethod
    def update(session_id: str, **kwargs):
        # 白名单允许更新的字段
        allowed_fields = {
            'goal', 'status', 'total_steps', 'completed_steps',
            'summary', 'completed_at'
        }

        # 过滤非法字段
        filtered_kwargs = {k: v for k, v in kwargs.items() if k in allowed_fields}

        if not filtered_kwargs:
            return

        fields = ", ".join(f"{k}=?" for k in filtered_kwargs)
        values = list(filtered_kwargs.values()) + [session_id]
        with get_db() as db:
            db.execute(f"UPDATE sessions SET {fields}, updated_at=datetime('now','localtime') WHERE session_id=?", values)

    @staticmethod
    def delete(session_id: str):
        with get_db() as db:
            db.execute("DELETE FROM steps WHERE session_id=?", (session_id,))
            db.execute("DELETE FROM tasks WHERE session_id=?", (session_id,))
            db.execute("DELETE FROM sessions WHERE session_id=?", (session_id,))


# ====== Steps ======

class StepDB:
    @staticmethod
    def create(session_id: str, step_number: int, description: str = "",
               assigned_agent: str = "", task_id: str = "", details: dict = None) -> Dict[str, Any]:
        with get_db() as db:
            details_json = json.dumps(details, ensure_ascii=False) if details else None
            db.execute(
                """INSERT INTO steps (session_id, step_number, description, assigned_agent, task_id, details_json)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (session_id, step_number, description, assigned_agent, task_id, details_json)
            )
        return StepDB.get(session_id, step_number)

    @staticmethod
    def _parse_details(step: Dict[str, Any]) -> Dict[str, Any]:
        """解析 details_json 字段为 dict"""
        if step and step.get("details_json"):
            step = dict(step)  # 复制避免 mutate 调用方
            try:
                step["details"] = json.loads(step["details_json"])
            except (json.JSONDecodeError, TypeError):
                step["details"] = {}
        del step["details_json"]
        return step

    @staticmethod
    def get(session_id: str, step_number: int) -> Optional[Dict[str, Any]]:
        with get_db() as db:
            row = db.execute(
                "SELECT * FROM steps WHERE session_id=? AND step_number=?",
                (session_id, step_number)
            ).fetchone()
            step = dict(row) if row else None
            return StepDB._parse_details(step) if step else None

    @staticmethod
    def list_by_session(session_id: str) -> List[Dict[str, Any]]:
        with get_db() as db:
            rows = db.execute(
                "SELECT * FROM steps WHERE session_id=? ORDER BY step_number",
                (session_id,)
            ).fetchall()
            return [StepDB._parse_details(dict(r)) for r in rows]

    @staticmethod
    def update(session_id: str, step_number: int, **kwargs):
        fields = ", ".join(f"{k}=?" for k in kwargs)
        values = list(kwargs.values()) + [session_id, step_number]
        with get_db() as db:
            db.execute(
                f"UPDATE steps SET {fields}, updated_at=datetime('now','localtime') WHERE session_id=? AND step_number=?",
                values
            )


# ====== Tasks ======

class TaskDB:
    @staticmethod
    def save(task_id: str, data: Dict[str, Any], session_id: str = "", step_number: int = 0):
        with get_db() as db:
            db.execute(
                "INSERT OR REPLACE INTO tasks (task_id, session_id, step_number, data) VALUES (?, ?, ?, ?)",
                (task_id, session_id, step_number, json.dumps(data, ensure_ascii=False))
            )

    @staticmethod
    def update(task_id: str, result: Optional[Dict] = None, status: Optional[str] = None):
        with get_db() as db:
            if result is not None:
                db.execute("UPDATE tasks SET result=?, status=? WHERE task_id=?",
                           (json.dumps(result, ensure_ascii=False), status or "done", task_id))
            elif status is not None:
                db.execute("UPDATE tasks SET status=? WHERE task_id=?", (status, task_id))

    @staticmethod
    def get(task_id: str) -> Optional[Dict[str, Any]]:
        with get_db() as db:
            row = db.execute("SELECT * FROM tasks WHERE task_id=?", (task_id,)).fetchone()
            if row:
                d = dict(row)
                d["data"] = json.loads(d["data"])
                if d["result"]:
                    d["result"] = json.loads(d["result"])
                return d
            return None

    @staticmethod
    def list_by_session(session_id: str) -> List[Dict[str, Any]]:
        with get_db() as db:
            rows = db.execute(
                "SELECT * FROM tasks WHERE session_id=? ORDER BY step_number", (session_id,)
            ).fetchall()
            result = []
            for r in rows:
                d = dict(r)
                d["data"] = json.loads(d["data"])
                if d["result"]:
                    d["result"] = json.loads(d["result"])
                result.append(d)
            return result
