"""Audit logging — every API call recorded to SQLite"""
import time, json, sqlite3, threading, asyncio
from datetime import datetime
from pathlib import Path
from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware

from backend.runtime_paths import DATABASE_PATH, ensure_user_data_dir

ensure_user_data_dir()
DB = DATABASE_PATH

class AuditMiddleware(BaseHTTPMiddleware):
    def __init__(self, app, skip_paths: tuple = None):
        super().__init__(app)
        self._skip = skip_paths or ("/static", "/docs", "/openapi.json", "/redoc", "/health", "/ws")
        self._init_db()

    def _init_db(self):
        conn = sqlite3.connect(str(DB))
        conn.execute("""CREATE TABLE IF NOT EXISTS audit_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            time TEXT DEFAULT (datetime('now')),
            method TEXT, path TEXT, status INTEGER, duration_ms INTEGER,
            ip TEXT, user_id TEXT, user_agent TEXT
        )""")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_audit_time ON audit_logs(time)")
        conn.commit()
        conn.close()

    async def dispatch(self, request: Request, call_next):
        for p in self._skip:
            if request.url.path.startswith(p): return await call_next(request)
        start = time.monotonic()
        try:
            response = await call_next(request)
        except Exception:
            response = None
        duration_ms = int((time.monotonic() - start) * 1000)
        status = response.status_code if response else 500
        user = getattr(request.state, "user", None)
        user_id = user.get("user_id", "") if user else ""

        # 异步写入 SQLite，不阻塞事件循环
        await asyncio.to_thread(_write_audit,
            request.method, request.url.path[:200], status, duration_ms,
            request.client.host if request.client else "", user_id,
            request.headers.get("user-agent", "")[:200])
        return response


def _write_audit(method: str, path: str, status: int, duration_ms: int,
                 ip: str, user_id: str, user_agent: str):
    """同步写入审计日志到 SQLite（在线程池中执行）"""
    try:
        conn = sqlite3.connect(str(DB))
        conn.execute(
            "INSERT INTO audit_logs (method,path,status,duration_ms,ip,user_id,user_agent) VALUES (?,?,?,?,?,?,?)",
            (method, path, status, duration_ms, ip, user_id, user_agent))
        conn.commit()
        conn.close()
    except Exception:
        pass  # 审计日志失败不影响主请求
