"""
Agent Console Router — Agent 控制台接口
"""
from fastapi import APIRouter
from backend.services.agent_registry import get_agent_registry
from backend.services.agent_router import get_agent_router
from backend.logger import get_logger

logger = get_logger()
router = APIRouter(prefix="/agent-console", tags=["Agent Console / 控制台"])


@router.get("/agents", summary="获取所有 Agent")
async def get_agents():
    """获取所有已发现的 Agent"""
    registry = get_agent_registry()
    registry.refresh()
    return registry.get_summary()


@router.post("/refresh", summary="刷新 Agent 列表")
async def refresh_agents():
    """重新扫描所有 Agent"""
    registry = get_agent_registry()
    registry.refresh(force=True)
    return registry.get_summary()


@router.get("/route/{task_type}", summary="查看路由决策")
async def explain_route(task_type: str, message: str = ""):
    """查看指定任务类型的路由决策"""
    router_instance = get_agent_router()
    return router_instance.explain_selection(task_type, message)
