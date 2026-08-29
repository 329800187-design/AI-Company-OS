"""Agent Router v2 — Pydantic 校验 + 统一信封"""
from typing import Any, Dict, Optional, List
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from backend.services.agent_loader import load_agent, load_agent_instance
from backend.schemas.agent_protocol import AgentTask, AgentRunResult
from backend.security import input_validator, rate_limiter
from backend.services.agent_discovery import get_agent_discovery, get_agent_enabled, set_agent_enabled

router = APIRouter(prefix="/agents", tags=["Agents / 智能体"])

BUSINESS_AGENT_IDS = {"marketing", "image", "data", "research", "website"}

# ── Unified Request Models ──────────────────────────

class AgentBaseTask(BaseModel):
    """所有 Agent 通用请求基类"""
    task_type: str = Field(default="", alias="任务类型", description="任务类型")
    goal: str = Field(default="", alias="目标", description="任务目标")
    timeout: int = Field(default=60, alias="超时", description="超时秒数")
    task_id: str = Field(default="", alias="任务ID", description="任务ID")

    model_config = {"populate_by_name": True, "extra": "allow"}

class CodexTask(AgentBaseTask):
    code: str = Field(default="", alias="代码内容", description="Python代码")
    language: str = Field(default="python", alias="语言")
    files: Dict[str, str] = Field(default_factory=dict, alias="文件列表")

class OpenClawTask(AgentBaseTask):
    url: str = Field(default="", alias="目标URL", description="目标网页URL")
    selector: str = Field(default="", alias="选择器")
    extract_type: str = Field(default="text", alias="提取类型")
    full_page: bool = Field(default=False, alias="全页")
    form_data: Dict[str, str] = Field(default_factory=dict, alias="表单数据")
    headless: bool = Field(default=True)
    allow_browser_automation: bool = Field(default=False, description="是否允许浏览器自动化（需显式授权）")

class CTOTask(AgentBaseTask):
    code: str = Field(default="", alias="代码", description="审查的代码")
    language: str = Field(default="", alias="语言")
    context: str = Field(default="", alias="上下文")
    architecture_desc: str = Field(default="", alias="架构描述")

class SystemTask(AgentBaseTask):
    command: str = Field(default="", alias="命令")
    file_path: str = Field(default="", alias="路径")
    file_content: str = Field(default="", alias="内容")
    program: str = Field(default="", alias="程序")
    shell_type: str = Field(default="cmd", alias="shell类型")
    cwd: str = Field(default="", alias="工作目录")

class ImageTask(AgentBaseTask):
    prompt: str = Field(default="", description="图片描述")
    size: str = Field(default="1024x1024")
    style: str = Field(default="vivid")

class MarketingTask(AgentBaseTask):
    prompt: str = Field(default="", description="营销需求描述")
    platform: str = Field(default="")

class DataTask(AgentBaseTask):
    file_path: str = Field(default="", alias="路径")
    url: str = Field(default="")
    chart_type: str = Field(default="bar", alias="图表类型")
    group_by: List[str] = Field(default_factory=list, alias="分组列")
    format: str = Field(default="csv", alias="导出格式")

class QATask(AgentBaseTask):
    result: Any = Field(default="", description="执行结果")
    extracted_data: List[Any] = Field(default_factory=list, alias="提取数据")
    expected_output: Dict = Field(default_factory=dict, alias="期望产出")

class CEOTask(BaseModel):
    goal: str = Field(default="", alias="目标")
    task_type: str = Field(default="goal_decompose", alias="任务类型")
    model_config = {"populate_by_name": True, "extra": "allow"}

class VideoTask(AgentBaseTask):
    prompt: str = Field(default="", description="视频脚本需求")

# ── Endpoints ────────────────────────────────────────

def _check_rate_limit(agent_name: str):
    """检查速率限制"""
    is_allowed, msg = rate_limiter.check(f"agent_{agent_name}", max_requests=30, window_seconds=60)
    if not is_allowed:
        raise HTTPException(status_code=429, detail=msg)

@router.post("/qa/run", summary="QA Agent")
def run_qa_agent(task: QATask):
    # Governance Guard: 拦截不支持的目标
    from backend.governance.guard import guard_payload, governance_block_response
    blocked, classification = guard_payload(task.model_dump())
    if blocked:
        return governance_block_response(classification)

    _check_rate_limit("qa")
    agent = load_agent_instance("agents.qa_agent.agent", "QAAgent")
    if agent is None:
        raise HTTPException(status_code=503, detail="QA Agent unavailable")
    return agent.run(_to_legacy(task))

@router.post("/ceo/run", summary="CEO Agent")
def run_ceo_agent(task: CEOTask):
    # Governance Guard: 拦截不支持的目标
    from backend.governance.guard import guard_payload, governance_block_response
    blocked, classification = guard_payload(task.model_dump())
    if blocked:
        return governance_block_response(classification)

    _check_rate_limit("ceo")
    agent = load_agent_instance("agents.ceo_agent.agent", "CEOAgent")
    if agent is None:
        raise HTTPException(status_code=503, detail="CEO Agent unavailable")
    return agent.run(_to_legacy(task))

@router.post("/codex/run", summary="Codex Agent — 安全沙箱执行Python代码")
def run_codex_agent(task: CodexTask):
    # Governance Guard: 拦截不支持的目标（只有 code 没有 goal 时不 block）
    from backend.governance.guard import guard_payload, governance_block_response
    blocked, classification = guard_payload(task.model_dump())
    if blocked:
        return governance_block_response(classification)

    _check_rate_limit("codex")
    agent = load_agent_instance("agents.codex_agent.agent", "CodexAgent", timeout=task.timeout)
    if agent is None:
        raise HTTPException(status_code=503, detail="Codex Agent unavailable")
    return agent.run(_to_legacy(task))

@router.post("/openclaw/run", summary="OpenClaw Agent — 浏览器自动化 / 深度研究 / 思考")
def run_openclaw_agent(task: OpenClawTask):
    # Governance Guard: 拦截不支持的目标（只有 url 没有 goal 时不 block）
    from backend.governance.guard import guard_payload, governance_block_response
    blocked, classification = guard_payload(task.model_dump())
    if blocked:
        return governance_block_response(classification)

    _check_rate_limit("openclaw")
    agent = load_agent_instance(
        "agents.openclaw_agent.agent", "OpenClawAgent",
        headless=task.headless, timeout=task.timeout,
        allow_browser_automation=task.allow_browser_automation,
    )
    if agent is None:
        raise HTTPException(status_code=503, detail="OpenClaw Agent unavailable")
    result = agent.run(_to_legacy(task))
    if result.get("status") == "blocked":
        from fastapi.responses import JSONResponse
        return JSONResponse(status_code=403, content=result)
    return result

@router.post("/cto/run", summary="CTO Agent — 代码审查/技术选型/架构评审")
def run_cto_agent(task: CTOTask):
    # Governance Guard: 拦截不支持的目标
    from backend.governance.guard import guard_payload, governance_block_response
    blocked, classification = guard_payload(task.model_dump())
    if blocked:
        return governance_block_response(classification)

    _check_rate_limit("cto")
    agent = load_agent_instance("agents.cto_agent.agent", "CTOAgent", timeout=task.timeout)
    if agent is None:
        raise HTTPException(status_code=503, detail="CTO Agent unavailable")
    return agent.run(_to_legacy(task))

@router.post("/system/run", summary="System Agent — 本地系统操作")
def run_system_agent(task: SystemTask):
    # Governance Guard: 拦截不支持的目标
    from backend.governance.guard import guard_payload, governance_block_response
    blocked, classification = guard_payload(task.model_dump())
    if blocked:
        return governance_block_response(classification)

    _check_rate_limit("system")
    agent = load_agent_instance("agents.system_agent.agent", "SystemAgent", timeout=task.timeout)
    if agent is None:
        raise HTTPException(status_code=503, detail="System Agent unavailable")
    return agent.run(_to_legacy(task))

@router.post("/image/run", summary="Image Agent — AI图片生成")
def run_image_agent(task: ImageTask):
    # Governance Guard: 拦截不支持的目标
    from backend.governance.guard import guard_payload, governance_block_response
    blocked, classification = guard_payload(task.model_dump())
    if blocked:
        return governance_block_response(classification)

    _check_rate_limit("image")
    agent = load_agent_instance("agents.image_agent.agent", "ImageAgent", timeout=task.timeout)
    if agent is None:
        raise HTTPException(status_code=503, detail="Image Agent unavailable")
    return agent.run(_to_legacy(task))

@router.post("/marketing/run", summary="Marketing Agent — 营销内容生成")
def run_marketing_agent(task: MarketingTask):
    # Governance Guard: 拦截不支持的目标
    from backend.governance.guard import guard_payload, governance_block_response
    blocked, classification = guard_payload(task.model_dump())
    if blocked:
        return governance_block_response(classification)

    _check_rate_limit("marketing")
    agent = load_agent_instance("agents.marketing_agent.agent", "MarketingAgent", timeout=task.timeout)
    if agent is None:
        raise HTTPException(status_code=503, detail="Marketing Agent unavailable")
    return agent.run(_to_legacy(task))

@router.post("/video/run", summary="Video Agent — 视频创意生成")
def run_video_agent(task: VideoTask):
    # Governance Guard: 拦截不支持的目标
    from backend.governance.guard import guard_payload, governance_block_response
    blocked, classification = guard_payload(task.model_dump())
    if blocked:
        return governance_block_response(classification)

    _check_rate_limit("video")
    agent = load_agent_instance("agents.video_agent.agent", "VideoAgent", timeout=task.timeout)
    if agent is None:
        raise HTTPException(status_code=503, detail="Video Agent unavailable")
    return agent.run(_to_legacy(task))

@router.post("/data/run", summary="Data Agent — 数据分析与可视化")
def run_data_agent(task: DataTask):
    # Governance Guard: 拦截不支持的目标
    from backend.governance.guard import guard_payload, governance_block_response
    blocked, classification = guard_payload(task.model_dump())
    if blocked:
        return governance_block_response(classification)

    _check_rate_limit("data")
    agent = load_agent_instance("agents.data_agent.agent", "DataAgent")
    if agent is None:
        raise HTTPException(status_code=503, detail="Data Agent unavailable")
    return agent.run(_to_legacy(task))


# ── 统一执行入口 ──────────────────────────────────────────

@router.post("/{agent_id}/execute", summary="统一执行入口 — 通过 agent_id 调用任意 Agent")
def execute_agent_unified(agent_id: str, task: AgentTask):
    """
    统一执行端点：通过 agent_id 调用任意 manifest 或 registry agent。

    - 优先从 manifest 解析 agent
    - 回退到 AGENT_REGISTRY 查找
    - 普通业务 Agent 直连执行，保留 LLM-first/fallback 能力
    - 非业务 Agent 仍由 Governance Guard 拦截不支持目标
    - 缺失 agent 返回 ok=false，不抛崩
    """
    if agent_id not in BUSINESS_AGENT_IDS:
        from backend.governance.guard import guard_payload, governance_block_response
        blocked, classification = guard_payload(task.model_dump())
        if blocked:
            return governance_block_response(classification)

    _check_rate_limit(agent_id)

    from backend.services.agent_executor import execute_agent
    import math

    def _clean_nan(obj):
        """递归清洗 NaN/Inf → None，确保 FastAPI JSONResponse 序列化安全"""
        if isinstance(obj, float) and (math.isnan(obj) or math.isinf(obj)):
            return None
        if isinstance(obj, dict):
            return {k: _clean_nan(v) for k, v in obj.items()}
        if isinstance(obj, (list, tuple)):
            return [_clean_nan(v) for v in obj]
        return obj

    result = execute_agent(agent_id, task)
    return _clean_nan(result.model_dump(by_alias=False))


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
    agent_list = [agent.to_dict() for agent in agents.values() if agent.kind != "llm"]
    enabled_count = sum(1 for a in agents.values() if a.enabled and a.kind != "llm")
    from backend.ai_registry import get_registry
    machine = get_registry().scan_runtime_capabilities(force=True)

    return {
        "agents": agent_list,
        "total": len(agent_list),
        "enabled_count": enabled_count,
        "llm_providers": machine["llm_providers"],
        "local_services": machine["ai_services"],
        "browsers": machine["browsers"],
        "tools": machine["tools"],
        "canonical_resources": machine["resources"],
        "machine_scan": machine["scan"],
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

    return {
        "ok": True,
        "agent_id": agent_id,
        "enabled": False,
        "message": f"Agent '{agent_id}' has been disabled"
    }


def _to_legacy(model: BaseModel) -> dict:
    return {**model.model_dump(by_alias=False, exclude_none=True),
            **model.model_dump(by_alias=True, exclude_none=True)}
