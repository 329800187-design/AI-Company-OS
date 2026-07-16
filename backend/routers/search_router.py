"""
全文搜索引擎 — 跨记忆+技能+会话+步骤+工作流搜索
"""
import json
import hashlib
from typing import List, Dict, Optional
from fastapi import APIRouter, Query

router = APIRouter(prefix="/search", tags=["Search / 搜索"])


@router.get("", summary="全文搜索")
def search(q: str = Query(..., min_length=1, max_length=500), scope: str = "all", limit: int = 20):
    results = {"query": q, "scope": scope, "hits": {}, "total": 0}

    if scope in ("all", "memory"):
        try:
            from core.memory.memory_store import get_memory_store
            mem = get_memory_store()
            hits = mem.search(q, limit=limit)
            results["hits"]["memories"] = [{
                "id": h["id"], "key": h["key"][:80],
                "source": h["source"], "importance": h["importance"],
                "snippet": h.get("content", "")[:200]
            } for h in hits]
            results["total"] += len(hits)
        except Exception:
            results["hits"]["memories"] = []

    if scope in ("all", "skills"):
        try:
            from core.skills.skill_manager import get_skill_manager
            mgr = get_skill_manager()
            matched = mgr.match(q, top_k=limit)
            results["hits"]["skills"] = [{
                "name": s.name, "title": s.title, "category": s.category,
                "description": s.description, "triggers": s.triggers[:5]
            } for s in matched]
            results["total"] += len(matched)
        except Exception:
            results["hits"]["skills"] = []

    if scope in ("all", "sessions"):
        try:
            from backend.database.database import get_db
            with get_db() as db:
                pattern = f"%{q}%"
                rows = db.execute(
                    "SELECT session_id, goal, status, created_at, summary FROM sessions "
                    "WHERE goal LIKE ? OR summary LIKE ? ORDER BY created_at DESC LIMIT ?",
                    (pattern, pattern, limit)
                ).fetchall()
            results["hits"]["sessions"] = [{
                "session_id": r[0], "goal": (r[1] or "")[:100],
                "status": r[2], "created_at": r[3],
                "summary": (r[4] or "")[:200]
            } for r in rows]
            results["total"] += len(rows)
        except Exception:
            results["hits"]["sessions"] = []

    if scope in ("all", "workflows"):
        try:
            from core.workflow.engine import get_workflow_engine
            wf_engine = get_workflow_engine()
            all_wfs = wf_engine.list_all()
            wf_hits = []
            for wf in all_wfs:
                if q.lower() in wf.get("title","").lower() or q.lower() in wf.get("description","").lower():
                    wf_hits.append(wf)
            results["hits"]["workflows"] = wf_hits[:limit]
            results["total"] += len(wf_hits)
        except Exception:
            results["hits"]["workflows"] = []

    # Search summary
    found_in = [k for k, v in results["hits"].items() if v]
    results["found_in"] = found_in
    results["counts"] = {k: len(v) for k, v in results["hits"].items()}

    return results
