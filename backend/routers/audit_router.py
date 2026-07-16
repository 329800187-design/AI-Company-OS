"""Audit log query endpoint"""
import sqlite3
from pathlib import Path
from fastapi import APIRouter, Query

router = APIRouter(prefix="/system", tags=["System / Audit"], include_in_schema=False)
DB = Path(__file__).parent.parent / "database" / "company_os.db"

@router.get("/audit")
def audit_logs(limit: int = Query(100, le=1000), user_id: str = "", path: str = ""):
    conn = sqlite3.connect(str(DB))
    conn.row_factory = sqlite3.Row
    if user_id:
        rows = conn.execute("SELECT * FROM audit_logs WHERE user_id=? ORDER BY id DESC LIMIT ?", (user_id, limit)).fetchall()
    elif path:
        rows = conn.execute("SELECT * FROM audit_logs WHERE path LIKE ? ORDER BY id DESC LIMIT ?", (f"%{path}%", limit)).fetchall()
    else:
        rows = conn.execute("SELECT * FROM audit_logs ORDER BY id DESC LIMIT ?", (limit,)).fetchall()
    conn.close()
    return {"logs": [dict(r) for r in rows], "count": len(rows)}
