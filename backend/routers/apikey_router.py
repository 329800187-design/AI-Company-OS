"""User API Key management"""
import hashlib, secrets
from fastapi import APIRouter, HTTPException, Request
from backend.database.database import get_db

router = APIRouter(prefix="/user", tags=["User / API Keys"])

def _ensure_table():
    with get_db() as db:
        db.execute("""CREATE TABLE IF NOT EXISTS api_keys (
            id INTEGER PRIMARY KEY AUTOINCREMENT, user_id TEXT NOT NULL,
            key_hash TEXT NOT NULL, prefix TEXT, name TEXT DEFAULT 'default',
            created_at TEXT DEFAULT (datetime('now')), last_used_at TEXT)""")

@router.get("/api-keys")
def list_api_keys(request: Request):
    user = getattr(request.state, "user", None)
    if not user: raise HTTPException(401, "Login required")
    _ensure_table()
    with get_db() as db:
        rows = db.execute(
            "SELECT id, prefix, created_at, last_used_at, name FROM api_keys WHERE user_id=? ORDER BY created_at DESC",
            (user["user_id"],)
        ).fetchall()
    return {"keys": [{"id": r[0], "prefix": r[1], "created_at": r[2], "last_used_at": r[3], "name": r[4]} for r in rows]}

@router.post("/api-keys")
def create_api_key(request: Request, name: str = "default"):
    user = getattr(request.state, "user", None)
    if not user: raise HTTPException(401, "Login required")
    raw_key = f"aios_{secrets.token_hex(24)}"
    key_hash = hashlib.sha256(raw_key.encode()).hexdigest()
    prefix = raw_key[:12] + "..."
    with get_db() as db:
        db.execute("""CREATE TABLE IF NOT EXISTS api_keys (
            id INTEGER PRIMARY KEY AUTOINCREMENT, user_id TEXT NOT NULL,
            key_hash TEXT NOT NULL, prefix TEXT, name TEXT DEFAULT 'default',
            created_at TEXT DEFAULT (datetime('now')), last_used_at TEXT
        )""")
        db.execute("INSERT INTO api_keys (user_id,key_hash,prefix,name) VALUES (?,?,?,?)",
                   (user["user_id"], key_hash, prefix, name))
    return {"key": raw_key, "prefix": prefix, "name": name, "warning": "Store this key safely — it only appears once"}

@router.delete("/api-keys/{key_id}")
def revoke_api_key(key_id: int, request: Request):
    user = getattr(request.state, "user", None)
    if not user: raise HTTPException(401, "Login required")
    with get_db() as db:
        db.execute("DELETE FROM api_keys WHERE id=? AND user_id=?", (key_id, user["user_id"]))
    return {"status": "revoked"}


def validate_api_key(raw_key: str) -> dict:
    """Validate an API Key, return user dict or None"""
    if not raw_key or not raw_key.startswith("aios_"): return None
    key_hash = hashlib.sha256(raw_key.encode()).hexdigest()
    with get_db() as db:
        row = db.execute(
            "SELECT u.user_id,u.username,u.email,u.tier,u.tenant_id FROM api_keys k JOIN users u ON k.user_id=u.user_id WHERE k.key_hash=?",
            (key_hash,)
        ).fetchone()
    if row:
        with get_db() as db:
            db.execute("UPDATE api_keys SET last_used_at=datetime('now') WHERE key_hash=?", (key_hash,))
        return {"user_id": row[0], "username": row[1], "email": row[2], "tier": row[3], "tenant_id": row[4]}
    return None
