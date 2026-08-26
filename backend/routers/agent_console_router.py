"""
Agent Console Router — Agent 控制台接口
"""
from fastapi import APIRouter, HTTPException
from backend.services.agent_registry import get_agent_registry
from backend.services.agent_router import get_agent_router
from backend.services.agent_discovery import get_agent_discovery, get_agent_enabled, set_agent_enabled
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


# ── 本地 Agent 发现与启用 API ──────────────────────────────────────

@router.get("/discovered", summary="获取所有已发现的 Agent 列表")
async def get_discovered_agents():
    """
    获取所有已发现的本地 Agent 列表，包含 enabled 状态和 source 信息。
    返回格式：
    {
        "agents": [
            {
                "id": "claude",
                "name": "Claude Code",
                "kind": "cli",
                "status": "available",
                "enabled": false,
                "source": "cli",
                "requires_confirmation": true,
                ...
            },
            ...
        ],
        "total": 10,
        "enabled_count": 3
    }
    """
    discovery = get_agent_discovery()
    agents = discovery.scan_all(force=True)
    agent_list = [agent.to_dict() for agent in agents.values()]
    enabled_count = sum(1 for a in agents.values() if a.enabled)

    return {
        "agents": agent_list,
        "total": len(agent_list),
        "enabled_count": enabled_count,
        "scan_scope": discovery.get_scan_scope(),
        "planning": {
            "available_enabled": [
                 {"id": agent.id, "name": agent.name, "capabilities": agent.capabilities,
                 "task_types": agent.task_types, "runnable": agent.runnable}
                for agent in agents.values()
                if agent.status == "available" and agent.enabled and agent.runnable
            ],
            "message": "任务拆解只会使用状态为可用且已启用的 Agent",
        },
    }


@router.post("/{agent_id}/enable", summary="启用指定 Agent")
async def enable_agent(agent_id: str):
    """
    启用指定的 Agent。

    启用后，该 Agent 将可以被调用执行任务。
    对于外部 CLI/HTTP Agent，启用前需要用户确认。
    """
    discovery = get_agent_discovery()
    agents = discovery.scan_all()

    if agent_id not in agents:
        raise HTTPException(
            status_code=404,
            detail=f"Agent '{agent_id}' not found. Available: {list(agents.keys())}"
        )

    agent = agents[agent_id]

    # 设置启用状态
    set_agent_enabled(agent_id, True)
    agent.enabled = True

    logger.info(f"Agent '{agent_id}' enabled (source={agent.source}, kind={agent.kind})")

    return {
        "ok": True,
        "agent_id": agent_id,
        "enabled": True,
        "message": f"Agent '{agent_id}' has been enabled"
    }


@router.post("/{agent_id}/disable", summary="禁用指定 Agent")
async def disable_agent(agent_id: str):
    """
    禁用指定的 Agent。

    禁用后，该 Agent 将无法被调用执行任务。
    """
    discovery = get_agent_discovery()
    agents = discovery.scan_all()

    if agent_id not in agents:
        raise HTTPException(
            status_code=404,
            detail=f"Agent '{agent_id}' not found. Available: {list(agents.keys())}"
        )

    agent = agents[agent_id]

    # 设置禁用状态
    set_agent_enabled(agent_id, False)
    agent.enabled = False

    logger.info(f"Agent '{agent_id}' disabled (source={agent.source}, kind={agent.kind})")

    return {
        "ok": True,
        "agent_id": agent_id,
        "enabled": False,
        "message": f"Agent '{agent_id}' has been disabled"
    }
