"""Memory system API."""

from typing import List, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from core.memory.memory_store import get_memory_store

router = APIRouter(prefix="/memory", tags=["Memory"])


class RememberRequest(BaseModel):
    key: str = Field(..., min_length=1)
    content: str = Field(..., min_length=1)
    source: str = "api"
    tags: List[str] = []
    importance: float = Field(default=0.5, ge=0, le=1)


class UpdateMemoryRequest(BaseModel):
    content: Optional[str] = None
    source: Optional[str] = None
    tags: Optional[List[str]] = None
    importance: Optional[float] = Field(default=None, ge=0, le=1)


class RetentionRequest(BaseModel):
    retention_days: Optional[int] = Field(default=None, ge=1)
    retention_class: str = Field(default="standard", min_length=1, max_length=80)


class RetireMemoryRequest(BaseModel):
    reason: str = Field(default="", max_length=500)


class CleanupExpiredRequest(BaseModel):
    source: Optional[str] = Field(default=None, max_length=100)


@router.get("/search", summary="Search memories")
def search_memory(q: str = "", limit: int = 10):
    store = get_memory_store()
    results = store.search(q, limit) if q else store.recent(limit)
    return {"memories": results, "count": len(results)}


@router.get("/recent", summary="Recent memories")
def recent_memories(limit: int = 10):
    store = get_memory_store()
    results = store.recent(limit)
    return {"memories": results, "count": len(results)}


@router.post("/remember", summary="Create or update a memory")
def remember(req: RememberRequest):
    store = get_memory_store()
    store.remember(
        key=req.key,
        content=req.content,
        source=req.source,
        tags=req.tags,
        importance=req.importance,
    )
    return {"status": "ok"}


@router.get("/context", summary="Get memory context")
def get_memory_context(goal: str = ""):
    store = get_memory_store()
    context = store.get_context(goal)
    return {"context": context, "goal": goal}


@router.get("/governance", summary="Memory retention and deletion status")
def memory_governance(source: Optional[str] = None):
    return get_memory_store().governance_summary(source=source)


@router.post("/governance/cleanup", summary="Retire explicitly expired memories")
def cleanup_expired_memories(req: CleanupExpiredRequest = CleanupExpiredRequest()):
    return get_memory_store().cleanup_expired(source=req.source)


@router.patch("/{key}/retention", summary="Set one memory retention policy")
def set_memory_retention(key: str, req: RetentionRequest):
    store = get_memory_store()
    try:
        updated = store.set_retention(key, req.retention_days, req.retention_class)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    if not updated:
        raise HTTPException(status_code=404, detail=f"Memory '{key}' not found or is retired")
    return {"status": "ok", "key": key, "retention_days": req.retention_days, "retention_class": req.retention_class}


@router.delete("/{key}/retire", summary="Retire one memory from all recall paths")
def retire_memory(key: str, req: RetireMemoryRequest = RetireMemoryRequest()):
    retired = get_memory_store().retire_by_key(key, req.reason)
    if not retired:
        raise HTTPException(status_code=404, detail=f"Memory '{key}' not found or already retired")
    return {"status": "ok", "message": f"Memory '{key}' retired"}


@router.delete("/clear", summary="Clear all memories")
def clear_memory():
    store = get_memory_store()
    store.clear()
    return {"status": "ok", "message": "All memories cleared"}


@router.put("/{key}", summary="Edit one memory")
def update_memory(key: str, req: UpdateMemoryRequest):
    store = get_memory_store()
    updated = store.update_by_key(
        key=key,
        content=req.content,
        source=req.source,
        tags=req.tags,
        importance=req.importance,
    )
    if not updated:
        raise HTTPException(status_code=404, detail=f"Memory '{key}' not found")
    return {"status": "ok"}


@router.delete("/{key}", summary="Delete one memory")
def delete_memory(key: str):
    store = get_memory_store()
    deleted = store.delete_by_key(key)
    if not deleted:
        raise HTTPException(status_code=404, detail=f"Memory '{key}' not found")
    return {"status": "ok", "message": f"Memory '{key}' deleted"}
