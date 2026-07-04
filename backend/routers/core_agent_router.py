"""Core Agent Router — 只保留 discovered / enable / disable / execute 四个端点"""
from fastapi import APIRouter, HTTPException

from backend.services.agent_discovery import get_agent_discovery, get_agent_enabled, set_agent_enabled
from backend.schemas.agent_protocol import AgentTask

router = APIRouter(prefix="/agents", tags=["Core Agents"])


@router.get("/discovered", summary="获取所有已发现的 Agent 列表")
async def get_discovered_agents():
    """
    获取所有已发现的本地 Agent 列表，包含 enabled 状态和 source 信息。
    """
    discovery = get_agent_discovery()
    agents = discovery.scan_all(force=True)
    agent_list = [agent.to_dict() for agent in agents.values()]
    enabled_count = sum(1 for a in agents.values() if a.enabled)

    return {
        "agents": agent_list,
        "total": len(agent_list),
        "enabled_count": enabled_count,
    }


@router.post("/{agent_id}/enable", summary="启用指定 Agent")
async def enable_agent(agent_id: str):
    """启用指定的 Agent。启用后可被调用执行任务。"""
    discovery = get_agent_discovery()
    agents = discovery.scan_all()

    if agent_id not in agents:
        raise HTTPException(
            status_code=404,
            detail=f"Agent '{agent_id}' not found. Available: {list(agents.keys())}"
        )

    set_agent_enabled(agent_id, True)
    agents[agent_id].enabled = True

    return {
        "ok": True,
        "agent_id": agent_id,
        "enabled": True,
        "message": f"Agent '{agent_id}' has been enabled"
    }


@router.post("/{agent_id}/disable", summary="禁用指定 Agent")
async def disable_agent(agent_id: str):
    """禁用指定的 Agent。禁用后无法被调用执行任务。"""
    discovery = get_agent_discovery()
    agents = discovery.scan_all()

    if agent_id not in agents:
        raise HTTPException(
            status_code=404,
            detail=f"Agent '{agent_id}' not found. Available: {list(agents.keys())}"
        )

    set_agent_enabled(agent_id, False)
    agents[agent_id].enabled = False

    return {
        "ok": True,
        "agent_id": agent_id,
        "enabled": False,
        "message": f"Agent '{agent_id}' has been disabled"
    }


@router.post("/{agent_id}/execute", summary="统一执行入口 — 通过 agent_id 调用任意 Agent")
def execute_agent_unified(agent_id: str, task: AgentTask):
    """
    统一执行端点：通过 agent_id 调用任意 manifest 或 registry agent。
    Governance Guard 拦截不支持目标，缺失 agent 返回 ok=false。
    """
    from backend.governance.guard import guard_payload, governance_block_response
    from backend.security import rate_limiter

    blocked, classification = guard_payload(task.model_dump())
    if blocked:
        return governance_block_response(classification)

    is_allowed, msg = rate_limiter.check(f"agent_{agent_id}", max_requests=30, window_seconds=60)
    if not is_allowed:
        raise HTTPException(status_code=429, detail=msg)

    from backend.services.agent_executor import execute_agent
    result = execute_agent(agent_id, task)
    return result.model_dump(by_alias=False)
