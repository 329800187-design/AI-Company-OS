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
