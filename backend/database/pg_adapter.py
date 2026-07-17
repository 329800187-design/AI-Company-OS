"""
PostgreSQL 适配器 — 可选生产级数据库后端

通过 DATABASE_URL 环境变量启用:
  DATABASE_URL=postgresql://user:pass@localhost:5432/company_os

留空则默认使用 SQLite。
"""
import os
import time
from contextlib import contextmanager
from typing import Any, Dict, List, Optional

try:
    import psycopg2
    import psycopg2.extras
    _PG_AVAILABLE = True
except ImportError:
    _PG_AVAILABLE = False


class PostgreSQLAdapter:
    """PostgreSQL 数据库适配器（与 SQLite database.py 接口兼容）"""

    def __init__(self, dsn: str = ""):
        self.dsn = dsn or os.getenv("DATABASE_URL", "")
        self._conn = None

    @property
    def available(self) -> bool:
        return bool(self.dsn) and _PG_AVAILABLE

    def _get_conn(self):
        if not self.available:
            raise RuntimeError("PostgreSQL 未配置或 psycopg2 未安装")
        if self._conn is None or self._conn.closed:
            self._conn = psycopg2.connect(self.dsn)
            self._conn.autocommit = False
        return self._conn

    @contextmanager
    def get_db(self):
        conn = self._get_conn()
        try:
            yield conn
        except Exception:
            conn.rollback()
            raise
        else:
            conn.commit()

    def init_db(self):
        conn = self._get_conn()
        conn.execute("""
            CREATE TABLE IF NOT EXISTS sessions (
                session_id TEXT PRIMARY KEY,
                goal TEXT NOT NULL,
                status TEXT DEFAULT 'active',
                total_steps INTEGER DEFAULT 0,
                completed_steps INTEGER DEFAULT 0,
                summary TEXT,
                created_at TIMESTAMPTZ DEFAULT NOW(),
                updated_at TIMESTAMPTZ DEFAULT NOW(),
                completed_at TIMESTAMPTZ
            );
            CREATE TABLE IF NOT EXISTS steps (
                id SERIAL PRIMARY KEY,
                session_id TEXT NOT NULL REFERENCES sessions(session_id),
                step_number INTEGER NOT NULL,
                description TEXT,
                assigned_agent TEXT,
                task_id TEXT,
                details_json TEXT,
                status TEXT DEFAULT 'pending',
                result_summary TEXT,
                decision TEXT,
                decision_detail TEXT,
                created_at TIMESTAMPTZ DEFAULT NOW(),
                updated_at TIMESTAMPTZ DEFAULT NOW()
            );
            CREATE TABLE IF NOT EXISTS tasks (
                task_id TEXT PRIMARY KEY,
                session_id TEXT,
                step_number INTEGER,
                data JSONB NOT NULL DEFAULT '{}',
                result JSONB,
                status TEXT DEFAULT 'todo',
                created_at TIMESTAMPTZ DEFAULT NOW()
            );
            CREATE TABLE IF NOT EXISTS memories (
                id SERIAL PRIMARY KEY,
                key TEXT NOT NULL,
                content TEXT NOT NULL,
                source TEXT DEFAULT 'system',
                tags JSONB DEFAULT '[]',
                importance REAL DEFAULT 0.5,
                created_at TIMESTAMPTZ DEFAULT NOW(),
                accessed_at TIMESTAMPTZ DEFAULT NOW(),
                access_count INTEGER DEFAULT 0
            );
            CREATE TABLE IF NOT EXISTS usage_logs (
                id SERIAL PRIMARY KEY,
                time TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                provider TEXT NOT NULL,
                model TEXT NOT NULL,
                prompt_tokens INTEGER DEFAULT 0,
                completion_tokens INTEGER DEFAULT 0,
                total_tokens INTEGER DEFAULT 0,
                cost_yuan REAL DEFAULT 0.0,
                source TEXT DEFAULT '',
                duration_ms INTEGER DEFAULT 0,
                success BOOLEAN DEFAULT TRUE
            );
        """)
        conn.execute("CREATE INDEX IF NOT EXISTS idx_steps_session ON steps(session_id)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_tasks_session ON tasks(session_id)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_memories_key ON memories(key)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_usage_time ON usage_logs(time)")
        conn.commit()


# 全局单例
_pg: Optional[PostgreSQLAdapter] = None


def get_pg_adapter() -> PostgreSQLAdapter:
    global _pg
    if _pg is None:
        _pg = PostgreSQLAdapter()
        if _pg.available:
            try:
                _pg.init_db()
            except Exception as e:
                print(f"[DB] PostgreSQL 初始化失败: {e}")
    return _pg
