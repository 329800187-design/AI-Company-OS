"""
系统备份恢复 — 全量数据导出/导入

端点:
  POST /system/backup  → 创建 JSON 备份文件
  POST /system/restore → 从备份文件恢复
  GET  /system/backups → 列出备份文件
"""
import json
import gzip
import shutil
from datetime import datetime
from pathlib import Path
from typing import Dict, List
from fastapi import APIRouter, HTTPException

router = APIRouter(prefix="/system", tags=["System / 备份恢复"], include_in_schema=False)

BACKUP_DIR = Path(__file__).parent.parent / "database" / "backups"
BACKUP_DIR.mkdir(parents=True, exist_ok=True)


@router.post("/backup", summary="创建系统备份")
def create_backup():
    from backend.database.database import get_db

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_path = BACKUP_DIR / f"backup_{timestamp}.json.gz"

    data = {"version": "0.8.0", "created_at": datetime.now().isoformat(), "tables": {}}

    with get_db() as db:
        for table in ["sessions", "steps", "tasks", "memories", "cron_jobs", "cron_logs", "usage_logs", "users", "sessions_tokens", "usage_billing"]:
            try:
                rows = db.execute(f"SELECT * FROM {table}").fetchall()
                data["tables"][table] = [dict(r) for r in rows]
            except Exception:
                data["tables"][table] = []

    # Compress
    with gzip.open(str(backup_path), "wt", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, default=str)

    size = backup_path.stat().st_size
    return {
        "ok": True,
        "backup_path": str(backup_path),
        "size_bytes": size,
        "size_mb": f"{size/1024/1024:.2f}",
        "tables": {k: len(v) for k, v in data["tables"].items()},
    }


@router.get("/backups", summary="列出备份文件")
def list_backups():
    backups = []
    for f in sorted(BACKUP_DIR.glob("backup_*.json.gz"), reverse=True):
        backups.append({
            "filename": f.name,
            "size_kb": f"{f.stat().st_size/1024:.1f}",
            "created": datetime.fromtimestamp(f.stat().st_mtime).isoformat(),
        })
    return {"backups": backups, "count": len(backups)}


@router.post("/restore", summary="从备份恢复")
def restore_backup(filename: str = ""):
    if not filename:
        # 用最新备份
        files = sorted(BACKUP_DIR.glob("backup_*.json.gz"), reverse=True)
        if not files:
            raise HTTPException(status_code=404, detail="无可用备份")
        filename = files[0].name

    backup_path = BACKUP_DIR / filename
    if not backup_path.exists():
        raise HTTPException(status_code=404, detail=f"备份文件不存在: {filename}")

    with gzip.open(str(backup_path), "rt", encoding="utf-8") as f:
        data = json.load(f)

    from backend.database.database import get_db
    restored = {}

    # 先逆序删除（子表先删），再正序插入（主表先插）
    table_deps = ["sessions", "users", "steps", "tasks", "memories",
                  "usage_logs", "usage_billing", "sessions_tokens",
                  "cron_jobs", "cron_logs"]
    with get_db() as db:
        db.execute("PRAGMA foreign_keys = OFF")
        for table in reversed(table_deps):
            try: db.execute(f"DELETE FROM {table}")
            except Exception: pass
        for table in table_deps:
            rows = data.get("tables", {}).get(table, [])
            if not rows:
                continue
            try:
                db.execute(f"DELETE FROM {table}")
                if rows:
                    cols = list(rows[0].keys())
                    placeholders = ",".join(["?"] * len(cols))
                    cols_str = ",".join(cols)
                    for row in rows:
                        values = [row.get(c) for c in cols]
                        db.execute(f"INSERT OR IGNORE INTO {table} ({cols_str}) VALUES ({placeholders})", values)
                restored[table] = len(rows)
            except Exception as e:
                restored[table] = f"skipped: {e}"
        db.execute("PRAGMA foreign_keys = ON")

    return {"ok": True, "restored_from": filename, "tables": restored}
