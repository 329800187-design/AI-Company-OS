"""记忆系统 API"""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from core.memory.memory_store import get_memory_store

router = APIRouter(prefix="/memory", tags=["记忆 / Memory"])


class RememberRequest(BaseModel):
    key: str
    content: str
    source: str = "api"
    tags: list = []
    importance: float = 0.5


@router.get("/search", summary="搜索记忆")
def search_memory(q: str = "", limit: int = 10):
    store = get_memory_store()
    if q:
        results = store.search(q, limit)
    else:
        results = store.recent(limit)
    return {"memories": results, "count": len(results)}


@router.get("/recent", summary="最近记忆")
def recent_memories(limit: int = 10):
    store = get_memory_store()
    results = store.recent(limit)
    return {"memories": results, "count": len(results)}


@router.post("/remember", summary="记录记忆")
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


@router.get("/context", summary="获取记忆上下文")
def get_memory_context(goal: str = ""):
    store = get_memory_store()
    ctx = store.get_context(goal)
    return {"context": ctx, "goal": goal}


@router.delete("/clear", summary="清空记忆")
def clear_memory():
    store = get_memory_store()
    store.clear()
    return {"status": "ok", "message": "所有记忆已清空"}
