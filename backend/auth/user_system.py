"""
用户系统 — 多租户支持 v0.5.0

特性：
1. 用户注册/登录（PBKDF2 密码哈希）
2. Session token 认证
3. 多租户隔离（tenant_id）
4. 订阅套餐（free/pro/enterprise）
5. 用量计费跟踪
"""
import hashlib
import hmac
import json
import os
import secrets
import sqlite3
import threading
import time
from contextlib import contextmanager
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional


# ── 配置 ──────────────────────────────────────────────

from backend.runtime_paths import DATABASE_PATH, ensure_user_data_dir

ensure_user_data_dir()
DB_PATH = DATABASE_PATH
_local = threading.local()

SUBSCRIPTION_TIERS = {
    "free": {
        "name": "免费版",
        "price_yuan_month": 0,
        "max_agents": 5,
        "max_sessions_day": 20,
        "max_tokens_month": 100_000,
        "features": ["基础 Agent", "SQLite 存储", "Web UI"],
    },
    "pro": {
        "name": "专业版",
        "price_yuan_month": 99,
        "max_agents": 20,
        "max_sessions_day": 200,
        "max_tokens_month": 1_000_000,
        "features": ["全部 Agent", "PostgreSQL 支持", "DAG 工作流", "优先队列"],
    },
    "enterprise": {
        "name": "企业版",
        "price_yuan_month": 499,
        "max_agents": 999,
        "max_sessions_day": 9999,
        "max_tokens_month": 10_000_000,
        "features": ["无限 Agent", "自定义工作流", "API 访问", "专属支持", "私有部署"],
    },
}


# ── 数据库 ──────────────────────────────────────────────

def _get_conn() -> sqlite3.Connection:
    if not hasattr(_local, "conn") or _local.conn is None:
        _local.conn = sqlite3.connect(str(DB_PATH))
        _local.conn.row_factory = sqlite3.Row
        _local.conn.execute("PRAGMA journal_mode=WAL")
    return _local.conn


@contextmanager
def _db():
    conn = _get_conn()
    try:
        yield conn
    except Exception:
        conn.rollback()
        raise
    else:
        conn.commit()


def init_user_tables():
    """初始化用户相关表"""
    conn = _get_conn()
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS users (
            user_id TEXT PRIMARY KEY,
            username TEXT UNIQUE NOT NULL,
            email TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            tenant_id TEXT NOT NULL DEFAULT '',
            tier TEXT DEFAULT 'free',
            created_at TEXT DEFAULT (datetime('now','localtime')),
            last_login_at TEXT
        );
        CREATE TABLE IF NOT EXISTS sessions_tokens (
            token TEXT PRIMARY KEY,
            user_id TEXT NOT NULL,
            tenant_id TEXT NOT NULL DEFAULT '',
            created_at TEXT DEFAULT (datetime('now','localtime')),
            expires_at TEXT,
            FOREIGN KEY (user_id) REFERENCES users(user_id)
        );
        CREATE TABLE IF NOT EXISTS usage_billing (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id TEXT NOT NULL,
            tenant_id TEXT NOT NULL DEFAULT '',
            month TEXT NOT NULL,
            tokens_used INTEGER DEFAULT 0,
            sessions_run INTEGER DEFAULT 0,
            cost_yuan REAL DEFAULT 0.0,
            FOREIGN KEY (user_id) REFERENCES users(user_id)
        );
    """)
    conn.commit()


# ── 密码哈希 ────────────────────────────────────────────

def _hash_password(password: str, salt: str = None) -> tuple:
    """PBKDF2 密码哈希 → (hash_hex, salt_hex)"""
    if salt is None:
        salt = secrets.token_hex(16)
    dk = hashlib.pbkdf2_hmac("sha256", password.encode(), salt.encode(), 100_000)
    return dk.hex(), salt


def _verify_password(password: str, stored_hash: str, salt: str) -> bool:
    new_hash, _ = _hash_password(password, salt)
    return hmac.compare_digest(new_hash, stored_hash)


# ── 用户操作 ────────────────────────────────────────────

class UserManager:
    """用户管理"""

    @staticmethod
    def register(username: str, email: str, password: str, tenant_id: str = "") -> Dict:
        with _db() as db:
            user_id = f"u_{secrets.token_hex(8)}"
            pw_hash, salt = _hash_password(password)
            stored = f"{pw_hash}${salt}"

            try:
                db.execute(
                    "INSERT INTO users (user_id, username, email, password_hash, tenant_id) VALUES (?, ?, ?, ?, ?)",
                    (user_id, username, email, stored, tenant_id or user_id)
                )
                return {"user_id": user_id, "username": username, "email": email}
            except sqlite3.IntegrityError:
                raise ValueError("用户名或邮箱已存在")

    @staticmethod
    def login(username: str, password: str) -> Optional[Dict]:
        with _db() as db:
            row = db.execute(
                "SELECT * FROM users WHERE username = ? OR email = ?",
                (username, username)
            ).fetchone()

        if not row:
            return None

        stored = row["password_hash"]
        if "$" not in stored:
            return None  # 格式错误

        pw_hash, salt = stored.split("$", 1)
        if not _verify_password(password, pw_hash, salt):
            return None

        # 创建 session token
        token = f"at_{secrets.token_hex(32)}"
        expires = (datetime.now() + timedelta(days=7)).isoformat()

        with _db() as db:
            db.execute(
                "INSERT INTO sessions_tokens (token, user_id, tenant_id, expires_at) VALUES (?, ?, ?, ?)",
                (token, row["user_id"], row["tenant_id"], expires)
            )
            db.execute("UPDATE users SET last_login_at = datetime('now','localtime') WHERE user_id = ?",
                       (row["user_id"],))

        return {
            "token": token,
            "user_id": row["user_id"],
            "username": row["username"],
            "email": row["email"],
            "tenant_id": row["tenant_id"],
            "tier": row["tier"],
            "expires_at": expires,
        }

    @staticmethod
    def validate_token(token: str) -> Optional[Dict]:
        """验证 token，返回用户信息或 None"""
        with _db() as db:
            row = db.execute(
                "SELECT u.*, s.expires_at FROM users u JOIN sessions_tokens s ON u.user_id = s.user_id "
                "WHERE s.token = ?", (token,)
            ).fetchone()

        if not row:
            return None

        # 检查过期
        if row["expires_at"] and row["expires_at"] < datetime.now().isoformat():
            db.execute("DELETE FROM sessions_tokens WHERE token = ?", (token,))
            return None

        return {
            "user_id": row["user_id"],
            "username": row["username"],
            "tenant_id": row["tenant_id"],
            "tier": row["tier"],
        }

    @staticmethod
    def get_user(user_id: str) -> Optional[Dict]:
        with _db() as db:
            row = db.execute("SELECT * FROM users WHERE user_id = ?", (user_id,)).fetchone()
        return dict(row) if row else None

    @staticmethod
    def set_tier(user_id: str, tier: str):
        if tier not in SUBSCRIPTION_TIERS:
            raise ValueError(f"无效套餐: {tier}")
        with _db() as db:
            db.execute("UPDATE users SET tier = ? WHERE user_id = ?", (tier, user_id))

    @staticmethod
    def check_limits(user_id: str) -> Dict:
        """检查用户是否超出套餐限制"""
        user = UserManager.get_user(user_id)
        if not user:
            return {"allowed": False, "reason": "用户不存在"}

        tier = SUBSCRIPTION_TIERS.get(user["tier"], SUBSCRIPTION_TIERS["free"])

        # 检查每日 session 数
        today = datetime.now().strftime("%Y-%m-%d")
        with _db() as db:
            row = db.execute(
                "SELECT COUNT(*) as cnt FROM sessions WHERE created_at LIKE ?",
                (f"{today}%",)
            ).fetchone()
            if row["cnt"] >= tier["max_sessions_day"]:
                return {"allowed": False, "reason": f"已达到每日会话上限 ({tier['max_sessions_day']})"}

        return {"allowed": True, "tier": user["tier"], "limits": tier}


# ── 计费 ────────────────────────────────────────────────

class BillingManager:
    """用量计费"""

    @staticmethod
    def record_usage(user_id: str, tenant_id: str, tokens: int, cost: float = 0.0):
        month = datetime.now().strftime("%Y-%m")
        with _db() as db:
            row = db.execute(
                "SELECT * FROM usage_billing WHERE user_id = ? AND month = ?",
                (user_id, month)
            ).fetchone()

            if row:
                db.execute(
                    "UPDATE usage_billing SET tokens_used = tokens_used + ?, "
                    "sessions_run = sessions_run + 1, cost_yuan = cost_yuan + ? "
                    "WHERE user_id = ? AND month = ?",
                    (tokens, cost, user_id, month)
                )
            else:
                db.execute(
                    "INSERT INTO usage_billing (user_id, tenant_id, month, tokens_used, sessions_run, cost_yuan) "
                    "VALUES (?, ?, ?, ?, 1, ?)",
                    (user_id, tenant_id, month, tokens, cost)
                )

    @staticmethod
    def get_usage(user_id: str, months: int = 3) -> List[Dict]:
        cutoff = (datetime.now() - timedelta(days=months * 30)).strftime("%Y-%m")
        with _db() as db:
            rows = db.execute(
                "SELECT * FROM usage_billing WHERE user_id = ? AND month >= ? ORDER BY month DESC",
                (user_id, cutoff)
            ).fetchall()
        return [dict(r) for r in rows]

    @staticmethod
    def get_tenant_usage(tenant_id: str) -> List[Dict]:
        with _db() as db:
            rows = db.execute(
                "SELECT * FROM usage_billing WHERE tenant_id = ? ORDER BY month DESC",
                (tenant_id,)
            ).fetchall()
        return [dict(r) for r in rows]


# ── 全局单例 ────────────────────────────────────────────

_user_manager: Optional[UserManager] = None


def get_user_manager() -> UserManager:
    global _user_manager
    if _user_manager is None:
        init_user_tables()
        _user_manager = UserManager()
    return _user_manager
