"""Boss Router — 老板运营指挥台 API"""
import logging
import uuid
import json
import time
from datetime import datetime, timezone
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Optional, List, Dict, Any, Literal
from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import Response
from pydantic import BaseModel, ConfigDict, Field, ValidationError
from backend.services.boss_command_center import get_boss_command_center, MODULE_ORDER
from backend.services.collaboration_graph import (
    build_boss_lite_graph,
    topological_waves,
    CollaborationNode,
    CollaborationEdge,
    CollaborationGraph,
    validate_graph,
)
from backend.security import input_validator, rate_limiter

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/boss", tags=["Boss / 老板指挥台"])


class MissionCreateRequest(BaseModel):
    """创建 Mission 请求"""
    goal: str = Field(..., min_length=2, max_length=5000, description="业务目标")
    auto_run: bool = Field(default=False, description="创建后立即执行")
    enabled_modules: Optional[List[str]] = Field(default=None, description="启用的模块 ID 列表，None 表示全部")
    allow_browser_automation: bool = Field(default=False, description="是否允许浏览器自动化采集（需显式授权）")


class MissionFromTemplateRequest(BaseModel):
    """从模板创建 Mission 请求"""
    template_id: str = Field(..., description="模板 ID")
    goal: Optional[str] = Field(default=None, description="覆盖模板默认目标")
    auto_run: bool = Field(default=False, description="创建后立即执行")
    enabled_modules: Optional[List[str]] = Field(default=None, description="覆盖模板默认模块")
    inputs: Optional[Dict[str, str]] = Field(default=None, description="补充输入信息")
    allow_browser_automation: bool = Field(default=False, description="是否允许浏览器自动化采集（需显式授权）")


class MissionRunRequest(BaseModel):
    """执行 Mission 请求"""
    allow_browser_automation: bool = Field(default=False, description="是否允许浏览器自动化采集（需显式授权）")


class ModuleRunRequest(BaseModel):
    """执行单个模块请求"""
    allow_browser_automation: bool = Field(default=False, description="是否允许浏览器自动化采集（需显式授权）")


class MissionAcceptRequest(BaseModel):
    """用户接受 Mission 结果请求"""
    comment: str = Field(default="", description="用户备注")


class MissionOutcomeRequest(BaseModel):
    """Human-observed business result after accepting a Mission delivery."""
    outcome_status: Literal["improved", "unchanged", "worse", "inconclusive"] = Field(
        ..., description="人工观测到的结果，不由系统自动推断"
    )
    metrics: Dict[str, float] = Field(default_factory=dict, description="可选的实际指标观测")
    note: str = Field(default="", max_length=1200, description="复盘备注")


class MissionActionCreateRequest(BaseModel):
    """A proposed action after a Mission was accepted by a human."""
    action_type: str = Field(..., min_length=1, max_length=100)
    summary: str = Field(default="", max_length=500)
    payload: Dict[str, Any] = Field(default_factory=dict)
    connector_id: str = Field(default="local_simulation", max_length=100)


class MissionActionApprovalRequest(BaseModel):
    approval_note: str = Field(default="", max_length=800)


class MissionActionCancellationRequest(BaseModel):
    reason: str = Field(..., min_length=1, max_length=800)


class MissionKpiObservationRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=160)
    value: float
    unit: str = Field(default="", max_length=60)
    direction: Literal["increased", "decreased", "unchanged", "unknown"] = "unknown"
    note: str = Field(default="", max_length=1200)
    action_id: Optional[str] = Field(default=None, max_length=100)


class OperatingCycleCreateRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=160)
    objective: str = Field(..., min_length=1, max_length=1200)
    period_start: str = Field(default="", max_length=64)
    period_end: str = Field(default="", max_length=64)
    target_metrics: Dict[str, Any] = Field(default_factory=dict)


class OperatingCycleObservationRequest(BaseModel):
    observation_id: int = Field(..., ge=1)


class OperatingCycleReviewRequest(BaseModel):
    conclusion: str = Field(..., min_length=1, max_length=2400)
    decision: Literal["continue", "adjust", "pause", "complete"]
    next_actions: List[str] = Field(default_factory=list, max_length=20)


@router.get("/templates", summary="模板列表")
def list_templates():
    """返回所有内置任务模板"""
    service = get_boss_command_center()
    templates = service.get_templates()
    return {"templates": templates, "total": len(templates)}


@router.post("/missions/from-template", summary="从模板创建 Mission")
def create_mission_from_template(request: MissionFromTemplateRequest):
    """根据模板创建 Mission"""
    # Governance Guard: 有 goal 时检查，只有 template_id 无 goal 时不 block
    from backend.governance.scope_classifier import guard_payload, governance_block_response
    blocked, classification = guard_payload(request.model_dump())
    if blocked:
        return governance_block_response(classification)

    is_allowed, rate_msg = rate_limiter.check("boss", max_requests=10, window_seconds=60)
    if not is_allowed:
        raise HTTPException(status_code=429, detail=rate_msg)

    service = get_boss_command_center()
    mission = service.create_mission_from_template(
        template_id=request.template_id,
        goal=request.goal,
        enabled_modules=request.enabled_modules,
        inputs=request.inputs,
        auto_run=request.auto_run,
        allow_browser_automation=request.allow_browser_automation,
    )
    if not mission:
        raise HTTPException(status_code=404, detail=f"模板 {request.template_id} 不存在")
    return mission


@router.post("/missions", summary="创建 Mission")
def create_mission(request: MissionCreateRequest):
    """创建一个新 Mission，拆成模块（默认 5 个，可选部分）"""
    # Governance Guard: 拦截不支持的目标
    from backend.governance.scope_classifier import guard_payload, governance_block_response
    blocked, classification = guard_payload(request.model_dump())
    if blocked:
        return governance_block_response(classification)

    is_valid, error_msg = input_validator.validate_message(request.goal)
    if not is_valid:
        raise HTTPException(status_code=400, detail=error_msg)

    is_allowed, rate_msg = rate_limiter.check("boss", max_requests=10, window_seconds=60)
    if not is_allowed:
        raise HTTPException(status_code=429, detail=rate_msg)

    # 验证 enabled_modules
    if request.enabled_modules is not None:
        valid_ids = set(MODULE_ORDER)
        invalid = [m for m in request.enabled_modules if m not in valid_ids]
        if invalid:
            raise HTTPException(
                status_code=400,
                detail=f"无效的模块 ID: {', '.join(invalid)}，可选: {', '.join(MODULE_ORDER)}"
            )
        if not request.enabled_modules:
            raise HTTPException(status_code=400, detail="enabled_modules 不能为空")

    service = get_boss_command_center()
    mission = service.create_mission(
        request.goal,
        auto_run=request.auto_run,
        enabled_modules=request.enabled_modules,
        allow_browser_automation=request.allow_browser_automation,
    )
    return mission


@router.get("/missions", summary="Mission 列表")
def list_missions(limit: int = 20, offset: int = 0):
    """返回 Mission 列表"""
    service = get_boss_command_center()
    missions = service.list_missions(limit=limit, offset=offset)
    return {"missions": missions, "total": len(missions)}


@router.get("/overview", summary="Boss 运营闭环概览")
def get_boss_overview():
    """Return factual mission/outcome counters; it does not infer business success."""
    return get_boss_command_center().get_operating_summary()


class CleanupStaleRequest(BaseModel):
    """清理超时 running 模块请求"""
    timeout_minutes: int = Field(default=30, ge=1, le=1440, description="超时阈值（分钟），默认 30")


@router.post("/missions/cleanup-stale", summary="清理超时 running 模块")
def cleanup_stale_missions(request: CleanupStaleRequest = CleanupStaleRequest()):
    """清理超时的 running 状态模块和任务

    规则：
    - running 超过 timeout_minutes 的模块标记为 partial（有结果）或 interrupted（无结果）
    - 写入 warning 提示用户人工检查
    - 不删除任何数据，不自动重跑
    """
    service = get_boss_command_center()
    result = service.cleanup_stale_running_missions(timeout_minutes=request.timeout_minutes)
    return result


@router.get("/missions/{mission_id}", summary="Mission 详情")
def get_mission(mission_id: str):
    """返回 Mission 详情（含各模块结果）"""
    service = get_boss_command_center()
    mission = service.get_mission(mission_id)
    if not mission:
        raise HTTPException(status_code=404, detail=f"Mission {mission_id} 不存在")
    return mission


@router.get("/missions/{mission_id}/events", summary="Mission 事件日志")
def get_mission_events(mission_id: str):
    """返回 Mission 的事件列表（时间升序）"""
    service = get_boss_command_center()
    mission = service.get_mission(mission_id)
    if not mission:
        raise HTTPException(status_code=404, detail=f"Mission {mission_id} 不存在")

    events = service.get_events(mission_id)
    return {"mission_id": mission_id, "events": events, "total": len(events)}


@router.get("/missions/{mission_id}/export", summary="导出 Mission 报告")
def export_mission(mission_id: str, format: str = Query(default="json", pattern="^(json|markdown)$")):
    """导出 Mission 为 JSON 或 Markdown"""
    service = get_boss_command_center()
    exported = service.export_mission(mission_id, fmt=format)
    if not exported:
        raise HTTPException(status_code=404, detail=f"Mission {mission_id} 不存在")

    return Response(
        content=exported["content"],
        media_type=exported["content_type"],
        headers={
            "Content-Disposition": f'attachment; filename="{exported["filename"]}"'
        }
    )


@router.post("/missions/{mission_id}/run", summary="执行 Mission")
def run_mission(mission_id: str, request: MissionRunRequest = MissionRunRequest()):
    """执行完整 Mission（顺序执行模块，跳过 skipped）"""
    service = get_boss_command_center()
    mission = service.get_mission(mission_id)
    if not mission:
        raise HTTPException(status_code=404, detail=f"Mission {mission_id} 不存在")

    # Governance Guard: 读取 mission goal 后检查
    from backend.governance.scope_classifier import guard_payload, governance_block_response
    mission_goal = mission.get("goal", "")
    if mission_goal:
        blocked, classification = guard_payload({"goal": mission_goal})
        if blocked:
            return governance_block_response(classification)

    if mission["status"] == "running":
        raise HTTPException(status_code=409, detail="Mission 正在执行中，请勿重复提交")

    mission = service.run_mission(mission_id, allow_browser_automation=request.allow_browser_automation)
    return mission


@router.post("/missions/{mission_id}/modules/{module_id}/run", summary="重跑单个模块")
def run_module(mission_id: str, module_id: str, request: ModuleRunRequest = ModuleRunRequest()):
    """单独重跑某个模块"""
    service = get_boss_command_center()
    mission = service.get_mission(mission_id)
    if not mission:
        raise HTTPException(status_code=404, detail=f"Mission {mission_id} 不存在")

    # Governance Guard: 读取 mission goal 后检查
    from backend.governance.scope_classifier import guard_payload, governance_block_response
    mission_goal = mission.get("goal", "")
    if mission_goal:
        blocked, classification = guard_payload({"goal": mission_goal})
        if blocked:
            return governance_block_response(classification)

    # 验证 module_id 合法
    valid_modules = {m["module_id"] for m in mission.get("modules", [])}
    if module_id not in valid_modules:
        raise HTTPException(
            status_code=400,
            detail=f"无效的 module_id: {module_id}，可选: {', '.join(sorted(valid_modules))}"
        )

    mission = service.run_module(mission_id, module_id, allow_browser_automation=request.allow_browser_automation)
    return mission


@router.post("/missions/{mission_id}/accept", summary="用户接受 Mission 结果")
def accept_mission(mission_id: str, request: MissionAcceptRequest = MissionAcceptRequest()):
    """用户确认接受 Mission 结果，状态改为 done"""
    service = get_boss_command_center()
    mission = service.get_mission(mission_id)
    if not mission:
        raise HTTPException(status_code=404, detail=f"Mission {mission_id} 不存在")

    mission = service.accept_mission(mission_id, comment=request.comment)
    return mission


@router.get("/missions/{mission_id}/outcome", summary="获取 Mission 后续结果")
def get_mission_outcome(mission_id: str):
    service = get_boss_command_center()
    if not service.get_mission(mission_id):
        raise HTTPException(status_code=404, detail=f"Mission {mission_id} 不存在")
    outcome = service.get_outcome(mission_id)
    return {"mission_id": mission_id, "outcome": outcome}


@router.post("/missions/{mission_id}/outcome", summary="记录人工观测的 Mission 后续结果")
def record_mission_outcome(mission_id: str, request: MissionOutcomeRequest):
    service = get_boss_command_center()
    try:
        outcome = service.record_outcome(
            mission_id, request.outcome_status, metrics=request.metrics, note=request.note
        )
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc))
    if not outcome:
        raise HTTPException(status_code=404, detail=f"Mission {mission_id} 不存在")
    return {"mission_id": mission_id, "outcome": outcome}


@router.get("/action-connectors", summary="已注册的动作连接器")
def list_mission_action_connectors():
    """Only locally simulated connectors are available by default."""
    return {"connectors": get_boss_command_center().get_operating_summary()["available_action_connectors"]}


@router.get("/missions/{mission_id}/actions", summary="获取 Mission 动作记录")
def get_mission_actions(mission_id: str):
    service = get_boss_command_center()
    if not service.get_mission(mission_id):
        raise HTTPException(status_code=404, detail=f"Mission {mission_id} 不存在")
    actions = service.get_actions(mission_id)
    return {"mission_id": mission_id, "actions": actions, "total": len(actions)}


@router.post("/missions/{mission_id}/actions", summary="提出需要人工批准的动作")
def create_mission_action(mission_id: str, request: MissionActionCreateRequest):
    service = get_boss_command_center()
    try:
        action = service.create_action_request(
            mission_id=mission_id,
            action_type=request.action_type,
            summary=request.summary,
            payload=request.payload,
            connector_id=request.connector_id,
        )
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc))
    if not action:
        raise HTTPException(status_code=404, detail=f"Mission {mission_id} 不存在")
    return {"mission_id": mission_id, "action": action}


@router.post("/actions/{action_id}/approve", summary="人工批准一个动作")
def approve_mission_action(action_id: str, request: MissionActionApprovalRequest = MissionActionApprovalRequest()):
    service = get_boss_command_center()
    try:
        action = service.approve_action(action_id, request.approval_note)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc))
    if not action:
        raise HTTPException(status_code=404, detail=f"Action {action_id} 不存在")
    return {"action": action}


@router.post("/actions/{action_id}/cancel", summary="人工取消一个未执行动作")
def cancel_mission_action(action_id: str, request: MissionActionCancellationRequest):
    service = get_boss_command_center()
    try:
        action = service.cancel_action(action_id, request.reason)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc))
    if not action:
        raise HTTPException(status_code=404, detail=f"Action {action_id} 不存在")
    return {"action": action}


@router.post("/actions/{action_id}/preflight", summary="对待批准动作执行无副作用预检")
def preflight_mission_action(action_id: str):
    """Checks connector readiness without executing or contacting an external system."""
    service = get_boss_command_center()
    try:
        action = service.preflight_action(action_id)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc))
    if not action:
        raise HTTPException(status_code=404, detail=f"Action {action_id} 不存在")
    return {"action": action}


@router.post("/actions/{action_id}/execute", summary="执行一个已人工批准的动作")
def execute_mission_action(action_id: str):
    service = get_boss_command_center()
    try:
        action = service.execute_action(action_id)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc))
    if not action:
        raise HTTPException(status_code=404, detail=f"Action {action_id} 不存在")
    return {"action": action}


@router.get("/missions/{mission_id}/kpis", summary="获取 Mission KPI 观测")
def get_mission_kpis(mission_id: str):
    service = get_boss_command_center()
    if not service.get_mission(mission_id):
        raise HTTPException(status_code=404, detail=f"Mission {mission_id} 不存在")
    observations = service.get_kpi_observations(mission_id)
    return {"mission_id": mission_id, "observations": observations, "total": len(observations)}


@router.post("/missions/{mission_id}/kpis", summary="记录人工 KPI 观测")
def record_mission_kpi(mission_id: str, request: MissionKpiObservationRequest):
    service = get_boss_command_center()
    try:
        observation = service.record_kpi_observation(
            mission_id=mission_id,
            name=request.name,
            value=request.value,
            unit=request.unit,
            direction=request.direction,
            note=request.note,
            action_id=request.action_id,
        )
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc))
    if not observation:
        raise HTTPException(status_code=404, detail=f"Mission {mission_id} 不存在")
    return {"mission_id": mission_id, "observation": observation}


@router.get("/operating-cycles", summary="经营复盘周期列表")
def list_operating_cycles(limit: int = Query(default=20, ge=1, le=100)):
    cycles = get_boss_command_center().list_operating_cycles(limit=limit)
    return {"cycles": cycles, "total": len(cycles)}


@router.post("/operating-cycles", summary="创建人工经营复盘周期")
def create_operating_cycle(request: OperatingCycleCreateRequest):
    try:
        cycle = get_boss_command_center().create_operating_cycle(
            name=request.name,
            objective=request.objective,
            period_start=request.period_start,
            period_end=request.period_end,
            target_metrics=request.target_metrics,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return cycle


@router.get("/operating-cycles/{cycle_id}", summary="经营复盘周期详情")
def get_operating_cycle(cycle_id: str):
    cycle = get_boss_command_center().get_operating_cycle(cycle_id)
    if not cycle:
        raise HTTPException(status_code=404, detail=f"Cycle {cycle_id} 不存在")
    return cycle


@router.post("/operating-cycles/{cycle_id}/observations", summary="人工将 KPI 观测加入周期")
def attach_operating_cycle_observation(cycle_id: str, request: OperatingCycleObservationRequest):
    try:
        cycle = get_boss_command_center().attach_kpi_observation_to_cycle(
            cycle_id, request.observation_id
        )
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc))
    if not cycle:
        raise HTTPException(status_code=404, detail=f"Cycle {cycle_id} 不存在")
    return cycle


@router.post("/operating-cycles/{cycle_id}/review", summary="记录人工经营复盘结论")
def review_operating_cycle(cycle_id: str, request: OperatingCycleReviewRequest):
    try:
        cycle = get_boss_command_center().review_operating_cycle(
            cycle_id, request.conclusion, request.decision, request.next_actions
        )
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc))
    if not cycle:
        raise HTTPException(status_code=404, detail=f"Cycle {cycle_id} 不存在")
    return cycle


@router.get("/modules/definitions", summary="模块定义")
def get_module_definitions():
    """返回 5 个模块的定义（供前端渲染）"""
    from backend.services.boss_command_center import MODULE_DEFINITIONS
    return {
        "modules": [
            {
                "id": module_id,
                **MODULE_DEFINITIONS[module_id],
            }
            for module_id in MODULE_ORDER
        ]
    }


# ── Boss Lite ──────────────────────────────────────────────

# 通用业务 Agent 定义：每个 agent 对应一种通用业务能力
BOSS_LITE_AGENTS = [
    {
        "agent_id": "research",
        "title": "上下文整理",
        "task_type": "research_brief",
        "purpose": "围绕目标收集上下文、事实依据、参考案例和数据支撑",
        "prompt_tpl": "请围绕以下业务目标做一份上下文整理简报：\n\n{goal}\n\n要求：\n1. 相关背景与现状\n2. 参考案例（成功/失败）\n3. 关键数据与事实\n4. 差异化机会\n5. 风险提示\n6. 下一步建议",
    },
    {
        "agent_id": "marketing",
        "title": "沟通表达",
        "task_type": "copywriting",
        "purpose": "设计沟通策略、内容方向、触达渠道和具体文案",
        "prompt_tpl": "请围绕以下业务目标制定一套沟通与触达方案：\n\n{goal}\n\n要求：\n1. 目标受众画像\n2. 核心信息（3-5 个关键点）\n3. 触达渠道策略\n4. 内容选题方向（5 个以上）\n5. 3 条可直接使用的内容/文案\n6. 推荐执行节奏",
    },
    {
        "agent_id": "image",
        "title": "素材方向",
        "task_type": "image_prompt",
        "purpose": "生成素材方向、图片提示词和制作建议",
        "prompt_tpl": "请围绕以下业务目标制定素材方向建议：\n\n{goal}\n\n要求：\n1. 视觉风格方向\n2. 主色调与色彩方案\n3. 3 组可用的 AI 图片生成提示词\n4. 制作/拍摄建议\n5. 适配场景说明",
    },
    {
        "agent_id": "data",
        "title": "数据洞察",
        "task_type": "data_report",
        "purpose": "分析关键指标、趋势和行动建议",
        "prompt_tpl": "请围绕以下业务目标做一份数据洞察框架：\n\n{goal}\n\n要求：\n1. 需要关注的核心指标\n2. 数据采集渠道与方法\n3. 基准值与目标值建议\n4. 关键趋势判断\n5. 数据驱动的行动建议\n6. 风险与限制说明",
    },
    {
        "agent_id": "website",
        "title": "交付物结构",
        "task_type": "landing_page_copy",
        "purpose": "设计可交付物的结构、框架和核心内容",
        "prompt_tpl": "请围绕以下业务目标设计一个交付物方案：\n\n{goal}\n\n要求：\n1. 交付物定位与目标受众\n2. 核心结构（标题 + 副标题 + CTA）\n3. 3-5 个核心板块\n4. 信任支撑（案例/数据/背书）\n5. FAQ 区域\n6. 使用/分发建议\n7. 结构说明",
    },
]


class BossLiteRequest(BaseModel):
    """Boss Lite 一句话执行请求"""
    goal: str = Field(..., min_length=2, max_length=5000, description="业务目标")
    agents: Optional[List[str]] = Field(default=None, description="指定执行的 Agent 列表，None 表示全部 5 个")
    save_to_delivery: bool = Field(default=True, description="是否自动保存到交付中心")


# ── Boss Graph 自定义 DAG 请求模型 ───────────────────────────


class BossGraphNodeRequest(BaseModel):
    """自定义协作图节点"""
    id: str = Field(..., min_length=1, max_length=100, description="图节点 ID")
    agent_id: str = Field(..., min_length=1, max_length=100, description="实际执行的 agent_id")
    task_type: str = Field(default="general", max_length=100, description="传给 AgentTask 的任务类型")
    title: str = Field(default="", max_length=200, description="展示标题")
    prompt: str = Field(default="", max_length=10000, description="该节点 prompt")


class BossGraphEdgeRequest(BaseModel):
    """自定义协作图边"""
    from_node: str = Field(..., min_length=1, max_length=100, description="上游节点 ID")
    to_node: str = Field(..., min_length=1, max_length=100, description="下游节点 ID")
    handoff_type: str = Field(default="context", max_length=50, description="handoff 类型")


class BossGraphExecuteRequest(BaseModel):
    """自定义协作图执行请求"""
    goal: str = Field(..., min_length=2, max_length=5000, description="业务目标")
    nodes: List[BossGraphNodeRequest] = Field(..., min_length=1, description="图节点列表")
    edges: List[BossGraphEdgeRequest] = Field(default_factory=list, description="图边列表")
    save_to_delivery: bool = Field(default=True, description="是否自动保存到交付中心")


# ── Graph Template 请求模型 ─────────────────────────────────


class BossGraphTemplateCreateRequest(BaseModel):
    """创建 Graph Template 请求"""
    name: str = Field(..., min_length=2, max_length=100, description="模板名称")
    description: str = Field(default="", max_length=500, description="模板描述")
    goal_hint: str = Field(default="", max_length=500, description="目标提示")
    nodes: List[BossGraphNodeRequest] = Field(..., min_length=1, description="图节点列表")
    edges: List[BossGraphEdgeRequest] = Field(default_factory=list, description="图边列表")
    source_template_id: Optional[str] = Field(default=None, description="克隆来源模板 ID（用于审计）")
    canvas_layout: Optional[Dict[str, Dict[str, float]]] = Field(default=None, description="Canvas 节点布局")


class BossGraphTemplateExecuteRequest(BaseModel):
    """按模板执行请求"""
    goal: str = Field(..., min_length=2, max_length=5000, description="业务目标")
    save_to_delivery: bool = Field(default=True, description="是否自动保存到交付中心")


class BossVersionMetadataUpdateRequest(BaseModel):
    """更新版本元数据请求"""
    model_config = ConfigDict(extra="forbid")

    label: Optional[str] = Field(default=None, max_length=100, description="版本标签")
    note: Optional[str] = Field(default=None, max_length=500, description="版本备注")


# ── Boss Lite Handoff ──────────────────────────────────────

_HANDOFF_LABELS = {
    "research": "Research",
    "data": "Data",
    "marketing": "Marketing",
    "image": "Image",
    "website": "Website",
}

_HANDOFF_CN_LABELS = {
    "research": "上下文整理",
    "data": "数据洞察",
    "marketing": "沟通表达",
    "image": "素材方向",
    "website": "交付物结构",
}


def _extract_handoff_context(results_map: dict) -> dict:
    """从 wave1 结果中提取 handoff_context。

    Args:
        results_map: {agent_id: result_dict} — 只包含 wave1 的结果

    Returns:
        handoff_context dict，字段可能为空列表/空字符串
    """
    ctx = {
        "research_summary": "",
        "research_key_findings": [],
        "research_opportunities": [],
        "research_risks": [],
        "data_key_metrics": [],
        "data_findings": [],
        "data_recommendations": [],
    }

    # research
    research = results_map.get("research")
    if research and research.get("ok"):
        so = research.get("structured_output") or {}
        ctx["research_summary"] = (
            research.get("summary", "")
            or so.get("summary", "")
            or so.get("market_summary", "")
        )
        ctx["research_key_findings"] = so.get("key_findings") or so.get("findings", [])
        ctx["research_opportunities"] = so.get("opportunities", [])
        ctx["research_risks"] = so.get("risks", [])

    # data
    data = results_map.get("data")
    if data and data.get("ok"):
        so = data.get("structured_output") or {}
        ctx["data_key_metrics"] = so.get("key_metrics", [])
        ctx["data_findings"] = so.get("findings", [])
        ctx["data_recommendations"] = so.get("recommendations", [])

    return ctx


def _build_handoff_prompt(agent_id: str, handoff_ctx: dict, ho_sources: list) -> str:
    """为下游 agent 构建 handoff 附言。"""
    parts = []

    has_research = "research" in ho_sources and handoff_ctx.get("research_summary")
    has_data = "data" in ho_sources and handoff_ctx.get("data_key_metrics")

    if not has_research and not has_data:
        return ""

    parts.append("\n\n---\n## 上游部门洞察（请参考并保持一致）\n")

    if has_research:
        parts.append("### 上下文整理结论")
        if handoff_ctx["research_summary"]:
            parts.append(f"- 摘要：{handoff_ctx['research_summary'][:300]}")
        for item in handoff_ctx["research_key_findings"][:3]:
            parts.append(f"- 关键发现：{_format_boss_value(item)}")
        for item in handoff_ctx["research_opportunities"][:2]:
            parts.append(f"- 机会：{_format_boss_value(item)}")
        for item in handoff_ctx["research_risks"][:2]:
            parts.append(f"- 风险：{_format_boss_value(item)}")
        parts.append("")

    if has_data:
        parts.append("### 数据洞察结论")
        for item in handoff_ctx["data_key_metrics"][:3]:
            parts.append(f"- 核心指标：{_format_boss_value(item)}")
        for item in handoff_ctx["data_findings"][:3]:
            parts.append(f"- 数据发现：{_format_boss_value(item)}")
        for item in handoff_ctx["data_recommendations"][:2]:
            parts.append(f"- 行动建议：{_format_boss_value(item)}")
        parts.append("")

    parts.append("请确保你的输出与以上上游上下文和数据洞察保持一致。")
    return "\n".join(parts)


def _actual_handoff_sources(handoff_ctx: dict) -> List[str]:
    """返回本次实际可传递的上游来源，而不是理论来源。"""
    sources: List[str] = []
    if any([
        handoff_ctx.get("research_summary"),
        handoff_ctx.get("research_key_findings"),
        handoff_ctx.get("research_opportunities"),
        handoff_ctx.get("research_risks"),
    ]):
        sources.append("research")
    if any([
        handoff_ctx.get("data_key_metrics"),
        handoff_ctx.get("data_findings"),
        handoff_ctx.get("data_recommendations"),
    ]):
        sources.append("data")
    return sources


def _format_handoff_flow(sources: List[str], targets: List[str], labels: dict) -> str:
    """格式化 handoff 来源和目标。"""
    source_text = "/".join(labels.get(source, source) for source in sources)
    target_text = "/".join(labels.get(target, target) for target in targets)
    if not source_text or not target_text:
        return ""
    return f"{source_text} → {target_text}"


def _execute_boss_lite_agent(index: int, agent_id: str, agent_task) -> dict:
    """Execute a single Boss Lite agent and return result with index for ordering.

    Returns:
        {
            "index": int,
            "agent_id": str,
            "result": dict | None,
            "error": str | None,
            "duration_ms": float,
        }
    """
    start = time.perf_counter()
    try:
        from backend.services.agent_executor import execute_agent
        result = execute_agent(agent_id, agent_task)
        result_dict = result.model_dump(by_alias=False)
        return {
            "index": index,
            "agent_id": agent_id,
            "result": result_dict,
            "error": None,
            "duration_ms": round((time.perf_counter() - start) * 1000, 1),
        }
    except Exception as e:
        return {
            "index": index,
            "agent_id": agent_id,
            "result": None,
            "error": str(e),
            "duration_ms": round((time.perf_counter() - start) * 1000, 1),
        }


@router.post("/lite/execute", summary="Boss Lite — 一句话目标 → 多 Agent 协同执行")
def boss_lite_execute(request: BossLiteRequest):
    """
    Boss Lite DAG 协作执行:
    1. 接收一句话业务目标
    2. 构建 CollaborationGraph DAG，按拓扑 wave 执行
    3. 基于图的上游依赖决定 handoff sources
    4. 生成 Boss 汇总报告
    5. 保存到 MiniDelivery（可选）
    """
    is_valid, error_msg = input_validator.validate_message(request.goal)
    if not is_valid:
        raise HTTPException(status_code=400, detail=error_msg)

    is_allowed, rate_msg = rate_limiter.check("boss_lite", max_requests=5, window_seconds=60)
    if not is_allowed:
        raise HTTPException(status_code=429, detail=rate_msg)

    # 确定要执行的 agents
    selected_agents = request.agents or [a["agent_id"] for a in BOSS_LITE_AGENTS]
    invalid = [a for a in selected_agents if a not in {x["agent_id"] for x in BOSS_LITE_AGENTS}]
    if invalid:
        raise HTTPException(status_code=400, detail=f"不支持的 Agent: {', '.join(invalid)}")

    agent_defs = [a for a in BOSS_LITE_AGENTS if a["agent_id"] in selected_agents]

    # 构建执行计划（保持标准顺序）
    plan = []
    for i, agent_def in enumerate(agent_defs, 1):
        plan.append({
            "step": i,
            "agent_id": agent_def["agent_id"],
            "task_type": agent_def["task_type"],
            "title": agent_def["title"],
            "prompt": agent_def["prompt_tpl"].format(goal=request.goal),
            "purpose": agent_def["purpose"],
            "status": "pending",
        })

    # ── DAG 协作图执行 ──
    from backend.schemas.agent_protocol import AgentTask

    graph = build_boss_lite_graph(agents=selected_agents)
    waves = topological_waves(graph)
    # downstream_agents: 有上游依赖的 agent（需要 handoff 的 agent）
    downstream_agents = {edge.to_node for edge in graph.edges}

    handoff_enabled = False
    actual_handoff_sources: List[str] = []
    handoff_ctx = {}
    results_map: Dict[str, Dict[str, Any]] = {}  # agent_id → result_dict
    agent_durations: Dict[str, float] = {}  # agent_id → duration_ms
    total_start = time.perf_counter()

    # ── 按 wave 顺序执行 ──
    for wave in waves:
        # 从已完成的结果中提取 handoff context
        handoff_ctx = _extract_handoff_context(results_map)
        actual_handoff_sources = _actual_handoff_sources(handoff_ctx)
        wave_has_downstream = any(aid in downstream_agents for aid in wave)
        if actual_handoff_sources and wave_has_downstream:
            handoff_enabled = True

        # 为本 wave 的每个 agent 构建任务
        wave_tasks = []
        for i, task in enumerate(plan):
            if task["agent_id"] not in wave:
                continue
            base_prompt = task["prompt"]
            # 基于图的上游依赖判断 handoff sources
            upstream = graph.upstream_of(task["agent_id"])
            agent_ho_sources = [s for s in upstream if s in results_map and results_map[s].get("ok")]
            # 为有上游依赖的 agent 构建 handoff prompt
            handoff_prompt = _build_handoff_prompt(task["agent_id"], handoff_ctx, agent_ho_sources) if agent_ho_sources else ""
            full_prompt = base_prompt + handoff_prompt if handoff_prompt else base_prompt

            agent_task = AgentTask(
                task_id=f"boss_lite_{uuid.uuid4().hex[:8]}",
                goal=request.goal,
                task_type=task["task_type"],
                context={
                    "source": "boss_lite",
                    "prompt": full_prompt,
                    "handoff_context": handoff_ctx if agent_ho_sources else {},
                },
                input={"prompt": full_prompt},
            )
            wave_tasks.append((i, task["agent_id"], agent_task, agent_ho_sources))

        # 并行执行本 wave
        wave_raw: List[Optional[Dict[str, Any]]] = [None] * len(wave_tasks)
        max_workers = min(len(wave_tasks), 5)
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            future_to_idx = {
                executor.submit(_execute_boss_lite_agent, idx, aid, at): j
                for j, (idx, aid, at, _) in enumerate(wave_tasks)
            }
            for future in as_completed(future_to_idx):
                j = future_to_idx[future]
                try:
                    wave_raw[j] = future.result()
                except Exception as e:
                    idx, aid, _, _ = wave_tasks[j]
                    wave_raw[j] = {
                        "index": idx,
                        "agent_id": aid,
                        "result": None,
                        "error": str(e),
                    }

        # 收集本 wave 结果
        for raw in wave_raw:
            if raw is None:
                continue
            aid = raw["agent_id"]
            agent_durations[aid] = raw.get("duration_ms", 0)
            if raw["error"] or raw["result"] is None:
                results_map[aid] = {"ok": False, "error": raw["error"], "structured_output": {}}
            else:
                rd = raw["result"]
                results_map[aid] = {
                    "ok": rd.get("ok", False),
                    "summary": rd.get("summary", ""),
                    "structured_output": rd.get("structured_output") or rd.get("output") or {},
                    "warnings": rd.get("warnings", []),
                    "errors": rd.get("errors", []),
                    "error": rd.get("error"),
                }

    # ── 按 plan 顺序组装最终 results ──
    total_duration_ms = round((time.perf_counter() - total_start) * 1000, 1)
    # 计算 handoff_targets（基于图：有上游依赖且成功执行的 agent）
    handoff_targets = [aid for aid in downstream_agents if aid in selected_agents and results_map.get(aid, {}).get("ok")]
    results: List[Dict[str, Any]] = []
    for task in plan:
        aid = task["agent_id"]
        rd = results_map.get(aid)
        dur = agent_durations.get(aid, 0)
        # 基于图判断该 agent 的实际 handoff sources
        upstream = graph.upstream_of(aid)
        agent_ho_sources = [s for s in upstream if s in results_map and results_map[s].get("ok")]

        if rd is None:
            task["status"] = "failed"
            results.append({
                "agent_id": aid,
                "title": task["title"],
                "ok": False,
                "summary": "",
                "structured_output": {},
                "warnings": [],
                "errors": ["Agent execution did not return a result"],
                "error": "Agent execution did not return a result",
                "duration_ms": dur,
                "used_handoff": False,
                "handoff_sources": [],
            })
        elif rd.get("error") or not rd.get("ok"):
            task["status"] = "failed"
            results.append({
                "agent_id": aid,
                "title": task["title"],
                "ok": False,
                "summary": "",
                "structured_output": rd.get("structured_output", {}),
                "warnings": rd.get("warnings", []),
                "errors": [rd["error"]] if rd.get("error") else rd.get("errors", ["Unknown error"]),
                "error": rd.get("error") or "Unknown error",
                "duration_ms": dur,
                "used_handoff": False,
                "handoff_sources": [],
            })
        else:
            task["status"] = "done"
            used_ho = bool(agent_ho_sources and handoff_enabled)
            results.append({
                "agent_id": aid,
                "title": task["title"],
                "ok": True,
                "summary": rd.get("summary", ""),
                "structured_output": rd.get("structured_output", {}),
                "warnings": rd.get("warnings", []),
                "errors": rd.get("errors", []),
                "error": None,
                "duration_ms": dur,
                "used_handoff": used_ho,
                "handoff_sources": agent_ho_sources if used_ho else [],
            })

    # 生成汇总
    succeeded = sum(1 for r in results if r["ok"])
    failed = len(results) - succeeded
    summary_text = f"Boss Lite 执行完成：{succeeded}/{len(results)} 个 Agent 成功"
    if failed > 0:
        summary_text += f"，{failed} 个失败"
    if handoff_enabled:
        flow_text = _format_handoff_flow(actual_handoff_sources, handoff_targets, _HANDOFF_LABELS)
        summary_text += f"（已启用部门协作：{flow_text}）"

    # 构建 Boss 汇总 structured_output
    boss_structured_output = {
        "goal": request.goal,
        "plan": plan,
        "results_summary": [
            {
                "agent_id": r["agent_id"],
                "title": r["title"],
                "ok": r["ok"],
                "summary": r["summary"],
                "duration_ms": r["duration_ms"],
                "used_handoff": r["used_handoff"],
                "handoff_sources": r.get("handoff_sources", []),
            }
            for r in results
        ],
        "succeeded": succeeded,
        "failed": failed,
        "total": len(results),
        "total_duration_ms": total_duration_ms,
        "handoff_context": handoff_ctx,
        "handoff_sources": actual_handoff_sources,
        "handoff_targets": handoff_targets if handoff_enabled else [],
        "handoff_enabled": handoff_enabled,
        "execution_mode": "two_wave_handoff" if handoff_enabled else "parallel",
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }

    # 保存到 MiniDelivery
    delivery_task_id = None
    if request.save_to_delivery:
        try:
            from backend.minidelivery.artifact_writer import ensure_output_dir

            # 渲染 Boss 汇总 Markdown
            artifact_md = _render_boss_lite_md(request.goal, plan, results, boss_structured_output)

            task_id = f"boss_{uuid.uuid4().hex[:12]}"
            task_dir = ensure_output_dir(task_id)

            # 写入 artifact.md
            md_path = task_dir / "artifact.md"
            md_path.write_text(artifact_md, encoding="utf-8")

            # 写入 raw_agent_result.json
            raw_path = task_dir / "raw_agent_result.json"
            raw_path.write_text(
                json.dumps(boss_structured_output, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )

            # 写入 result.json
            result_json = {
                "task_id": task_id,
                "goal": request.goal,
                "agent_id": "boss",
                "artifact_type": "boss_lite",
                "title": f"Boss Lite: {request.goal[:50]}",
                "source_page": "boss",
                "created_at": datetime.now(timezone.utc).isoformat(),
                "ok": succeeded > 0,
                "mode": "boss_lite",
                "summary": summary_text,
                "artifact_path": str(md_path),
                "raw_agent_result_path": str(raw_path),
            }
            json_path = task_dir / "result.json"
            json_path.write_text(
                json.dumps(result_json, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
            delivery_task_id = task_id
        except Exception as e:
            # Phase 6.28: 记录持久化失败，不再静默吞掉
            logger.warning(f"Boss Lite 交付持久化失败: {e}", exc_info=True)
            delivery_task_id = None

    return {
        "ok": succeeded > 0,
        "task_id": delivery_task_id or f"boss_lite_{uuid.uuid4().hex[:8]}",
        "goal": request.goal,
        "plan": plan,
        "results": results,
        "summary": {
            "text": summary_text,
            "succeeded": succeeded,
            "failed": failed,
            "total": len(results),
            "total_duration_ms": total_duration_ms,
        },
        "structured_output": boss_structured_output,
        "delivery_task_id": delivery_task_id,
        "handoff_enabled": handoff_enabled,
        "execution_mode": boss_structured_output["execution_mode"],
    }


# ── Boss Graph 自定义 DAG 执行 ───────────────────────────────


def _build_custom_graph(request: BossGraphExecuteRequest) -> CollaborationGraph:
    """从请求构造 CollaborationGraph"""
    nodes = [
        CollaborationNode(
            id=n.id,
            agent_id=n.agent_id,
            label=n.title,
            config={"task_type": n.task_type, "prompt": n.prompt},
        )
        for n in request.nodes
    ]
    edges = [
        CollaborationEdge(
            from_node=e.from_node,
            to_node=e.to_node,
            label=e.handoff_type,
        )
        for e in request.edges
    ]
    return CollaborationGraph(nodes=nodes, edges=edges)


def _extract_custom_handoff_context(results_map: dict, graph: CollaborationGraph, node_id: str) -> tuple:
    """从上游节点结果中提取 handoff context。

    Returns:
        (handoff_prompt, handoff_sources) — handoff 附言和实际来源列表
    """
    upstream_ids = graph.upstream_of(node_id)
    # 只取成功执行的上游
    successful_upstream = [uid for uid in upstream_ids if results_map.get(uid, {}).get("ok")]

    if not successful_upstream:
        return "", []

    parts = ["\n\n---\n## 上游节点洞察（请参考并保持一致）\n"]
    for uid in successful_upstream:
        upstream_result = results_map[uid]
        upstream_node = graph.get_node(uid)
        label = upstream_node.label if upstream_node else uid
        so = upstream_result.get("structured_output") or {}
        summary = upstream_result.get("summary") or so.get("summary", "")

        parts.append(f"### {label}")
        if summary:
            parts.append(f"- 摘要：{summary[:300]}")

        # 提取常见结构化字段
        for key in ["key_findings", "findings", "recommendations", "opportunities", "risks"]:
            items = so.get(key, [])
            if items and isinstance(items, list):
                cn_label = {"key_findings": "关键发现", "findings": "发现", "recommendations": "建议",
                            "opportunities": "机会", "risks": "风险"}.get(key, key)
                for item in items[:3]:
                    parts.append(f"- {cn_label}: {_format_boss_value(item)}")
        parts.append("")

    parts.append("请确保你的输出与以上上游节点结论保持一致。")
    return "\n".join(parts), successful_upstream


def _execute_graph_node(node: CollaborationNode, agent_task) -> dict:
    """执行单个图节点，返回结果 dict"""
    start = time.perf_counter()
    try:
        from backend.services.agent_executor import execute_agent
        result = execute_agent(node.agent_id, agent_task)
        result_dict = result.model_dump(by_alias=False)
        return {
            "node_id": node.id,
            "agent_id": node.agent_id,
            "result": result_dict,
            "error": None,
            "duration_ms": round((time.perf_counter() - start) * 1000, 1),
        }
    except Exception as e:
        return {
            "node_id": node.id,
            "agent_id": node.agent_id,
            "result": None,
            "error": str(e),
            "duration_ms": round((time.perf_counter() - start) * 1000, 1),
        }


def _render_boss_graph_md(goal: str, request: BossGraphExecuteRequest, waves: list, results: list, boss_so: dict) -> str:
    """渲染自定义图执行报告为 Markdown"""
    total_dur = boss_so.get("total_duration_ms", 0)
    total_sec = f"{total_dur / 1000:.1f}" if total_dur else "—"

    lines = [
        "# Boss Graph 自定义协作图报告",
        "",
        "## 总目标",
        "",
        goal,
        "",
        f"**总耗时：{total_sec} 秒**",
        "",
        "---",
        "",
        "## 一、图结构",
        "",
        "### 节点",
        "",
    ]

    for n in request.nodes:
        lines.append(f"- **{n.title or n.id}** (agent: {n.agent_id}, type: {n.task_type})")
    lines.append("")

    lines.append("### 依赖关系")
    lines.append("")
    if request.edges:
        for e in request.edges:
            from_title = next((n.title or n.id for n in request.nodes if n.id == e.from_node), e.from_node)
            to_title = next((n.title or n.id for n in request.nodes if n.id == e.to_node), e.to_node)
            lines.append(f"- {from_title} → {to_title} ({e.handoff_type})")
    else:
        lines.append("无依赖关系（全部并行执行）")
    lines.append("")

    lines += ["---", "", "## 二、执行 Wave", ""]
    for i, wave in enumerate(waves):
        wave_labels = []
        for nid in wave:
            node = next((n for n in request.nodes if n.id == nid), None)
            wave_labels.append(node.title or nid if node else nid)
        lines.append(f"- **Wave {i + 1}:** {', '.join(wave_labels)}")
    lines.append("")

    lines += ["---", "", "## 三、各节点结果", ""]
    for r in results:
        status_icon = "✅" if r["ok"] else "❌"
        dur = r.get("duration_ms", 0)
        dur_str = f" （耗时 {dur / 1000:.1f}s）" if dur else ""
        lines.append(f"### {status_icon} {r['title']}{dur_str}")
        lines.append("")

        if r.get("used_handoff"):
            sources = ", ".join(r.get("handoff_sources", []))
            lines.append(f"- **Handoff 来源：** {sources}")
            lines.append("")

        so = r.get("structured_output") or {}
        summary = r.get("summary") or so.get("summary", "")
        if summary:
            lines.append(f"- **摘要：** {summary[:300]}")
            lines.append("")

        for key in ["key_findings", "findings", "recommendations"]:
            items = so.get(key, [])
            if items and isinstance(items, list):
                cn_label = {"key_findings": "关键发现", "findings": "发现", "recommendations": "建议"}.get(key, key)
                lines.append(f"- **{cn_label}：**")
                for item in items[:3]:
                    lines.append(f"  - {_format_boss_value(item)}")
                lines.append("")

        if r.get("error"):
            lines.append(f"- ⚠️ 错误: {r['error']}")
            lines.append("")

    lines += [
        "---",
        "",
        f"*由 AI Company OS Boss Graph 生成 · {boss_so.get('generated_at', '')}*",
    ]

    return "\n".join(lines)


@router.post("/graph/execute", summary="Boss Graph — 自定义 DAG 协作图执行")
def boss_graph_execute(request: BossGraphExecuteRequest):
    """
    自定义协作图执行:
    1. 接收 nodes/edges 定义的 DAG
    2. 校验图合法性
    3. 按拓扑 wave 并行执行
    4. 基于图上游依赖传递 handoff
    5. 保存到 MiniDelivery（可选）
    """
    # Governance Guard
    from backend.governance.scope_classifier import guard_payload, governance_block_response
    blocked, classification = guard_payload({"goal": request.goal})
    if blocked:
        return governance_block_response(classification)

    is_valid_input, error_msg = input_validator.validate_message(request.goal)
    if not is_valid_input:
        raise HTTPException(status_code=400, detail=error_msg)

    is_allowed, rate_msg = rate_limiter.check("boss_graph", max_requests=5, window_seconds=60)
    if not is_allowed:
        raise HTTPException(status_code=429, detail=rate_msg)

    # 构造图
    graph = _build_custom_graph(request)

    # 校验图
    validation = validate_graph(graph)
    if not validation.valid:
        raise HTTPException(status_code=400, detail={
            "message": "协作图校验失败",
            "errors": validation.errors,
            "warnings": validation.warnings,
        })

    # 拓扑 wave
    waves = topological_waves(graph)

    # 构建 node_id → node 映射
    node_map = {n.id: n for n in request.nodes}

    # 按 wave 顺序执行
    from backend.schemas.agent_protocol import AgentTask

    results_map: Dict[str, Dict[str, Any]] = {}  # node_id → result_dict
    node_durations: Dict[str, float] = {}
    total_start = time.perf_counter()

    for wave in waves:
        wave_tasks = []
        for node_id in wave:
            node = node_map[node_id]
            graph_node = graph.get_node(node_id)

            # 计算 handoff
            handoff_prompt, handoff_sources = _extract_custom_handoff_context(results_map, graph, node_id)
            full_prompt = node.prompt + handoff_prompt if handoff_prompt else node.prompt

            # 上游节点 ID 列表
            upstream_ids = graph.upstream_of(node_id)

            agent_task = AgentTask(
                task_id=f"boss_graph_{uuid.uuid4().hex[:8]}",
                goal=request.goal,
                task_type=node.task_type,
                context={
                    "source": "boss_graph",
                    "node_id": node_id,
                    "upstream_nodes": upstream_ids,
                    "handoff_sources": handoff_sources,
                },
                input={"prompt": full_prompt},
            )
            wave_tasks.append((node_id, graph_node, agent_task, handoff_sources))

        # 并行执行本 wave
        max_workers = min(len(wave_tasks), 5)
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            future_to_idx = {}
            for j, (node_id, graph_node, agent_task, _) in enumerate(wave_tasks):
                future = executor.submit(_execute_graph_node, graph_node, agent_task)
                future_to_idx[future] = j

            wave_raw = [None] * len(wave_tasks)
            for future in as_completed(future_to_idx):
                j = future_to_idx[future]
                try:
                    wave_raw[j] = future.result()
                except Exception as e:
                    node_id, graph_node, _, _ = wave_tasks[j]
                    wave_raw[j] = {
                        "node_id": node_id,
                        "agent_id": graph_node.agent_id,
                        "result": None,
                        "error": str(e),
                    }

        # 收集本 wave 结果
        for raw in wave_raw:
            if raw is None:
                continue
            nid = raw["node_id"]
            node_durations[nid] = raw.get("duration_ms", 0)
            if raw["error"] or raw["result"] is None:
                results_map[nid] = {"ok": False, "error": raw["error"], "structured_output": {}}
            else:
                rd = raw["result"]
                results_map[nid] = {
                    "ok": rd.get("ok", False),
                    "summary": rd.get("summary", ""),
                    "structured_output": rd.get("structured_output") or rd.get("output") or {},
                    "warnings": rd.get("warnings", []),
                    "errors": rd.get("errors", []),
                    "error": rd.get("error"),
                }

    total_duration_ms = round((time.perf_counter() - total_start) * 1000, 1)

    # 按 nodes 输入顺序组装 results
    results: List[Dict[str, Any]] = []
    for node in request.nodes:
        nid = node.id
        rd = results_map.get(nid)
        dur = node_durations.get(nid, 0)
        upstream_ids = graph.upstream_of(nid)
        successful_upstream = [uid for uid in upstream_ids if results_map.get(uid, {}).get("ok")]

        if rd is None:
            results.append({
                "node_id": nid,
                "agent_id": node.agent_id,
                "title": node.title or nid,
                "ok": False,
                "summary": "",
                "structured_output": {},
                "error": "Node execution did not return a result",
                "duration_ms": dur,
                "used_handoff": False,
                "handoff_sources": [],
            })
        elif rd.get("error") or not rd.get("ok"):
            results.append({
                "node_id": nid,
                "agent_id": node.agent_id,
                "title": node.title or nid,
                "ok": False,
                "summary": "",
                "structured_output": rd.get("structured_output", {}),
                "error": rd.get("error") or "Unknown error",
                "duration_ms": dur,
                "used_handoff": False,
                "handoff_sources": [],
            })
        else:
            used_ho = bool(successful_upstream)
            results.append({
                "node_id": nid,
                "agent_id": node.agent_id,
                "title": node.title or nid,
                "ok": True,
                "summary": rd.get("summary", ""),
                "structured_output": rd.get("structured_output", {}),
                "error": None,
                "duration_ms": dur,
                "used_handoff": used_ho,
                "handoff_sources": successful_upstream if used_ho else [],
            })

    # 生成汇总
    succeeded = sum(1 for r in results if r["ok"])
    failed = len(results) - succeeded

    boss_structured_output = {
        "goal": request.goal,
        "graph": {
            "nodes": [{"id": n.id, "agent_id": n.agent_id, "title": n.title} for n in request.nodes],
            "edges": [{"from": e.from_node, "to": e.to_node, "type": e.handoff_type} for e in request.edges],
        },
        "waves": waves,
        "results_summary": [
            {
                "node_id": r["node_id"],
                "agent_id": r["agent_id"],
                "title": r["title"],
                "ok": r["ok"],
                "summary": r["summary"],
                "duration_ms": r["duration_ms"],
                "used_handoff": r["used_handoff"],
                "handoff_sources": r.get("handoff_sources", []),
            }
            for r in results
        ],
        "succeeded": succeeded,
        "failed": failed,
        "total": len(results),
        "total_duration_ms": total_duration_ms,
        "handoff_enabled": any(r["used_handoff"] for r in results),
        "execution_mode": "custom_graph",
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }

    # 保存到 MiniDelivery
    delivery_task_id = None
    if request.save_to_delivery:
        try:
            from backend.minidelivery.artifact_writer import ensure_output_dir

            artifact_md = _render_boss_graph_md(request.goal, request, waves, results, boss_structured_output)

            task_id = f"boss_graph_{uuid.uuid4().hex[:12]}"
            task_dir = ensure_output_dir(task_id)

            md_path = task_dir / "artifact.md"
            md_path.write_text(artifact_md, encoding="utf-8")

            raw_path = task_dir / "raw_agent_result.json"
            raw_path.write_text(
                json.dumps(boss_structured_output, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )

            result_json = {
                "task_id": task_id,
                "goal": request.goal,
                "agent_id": "boss",
                "artifact_type": "boss_graph",
                "title": f"Boss Graph: {request.goal[:50]}",
                "source_page": "boss_graph",
                "created_at": datetime.now(timezone.utc).isoformat(),
                "ok": succeeded > 0,
                "mode": "boss_graph",
                "summary": f"自定义图执行完成：{succeeded}/{len(results)} 个节点成功",
                "artifact_path": str(md_path),
                "raw_agent_result_path": str(raw_path),
            }
            json_path = task_dir / "result.json"
            json_path.write_text(
                json.dumps(result_json, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
            delivery_task_id = task_id
        except Exception as e:
            # Phase 6.28: 记录持久化失败，不再静默吞掉
            logger.warning(f"Boss Graph 交付持久化失败: {e}", exc_info=True)
            delivery_task_id = None

    return {
        "ok": succeeded > 0,
        "task_id": delivery_task_id or f"boss_graph_{uuid.uuid4().hex[:8]}",
        "execution_mode": "custom_graph",
        "goal": request.goal,
        "waves": waves,
        "results": results,
        "summary": {
            "total": len(results),
            "succeeded": succeeded,
            "failed": failed,
            "total_duration_ms": total_duration_ms,
        },
        "structured_output": boss_structured_output,
        "delivery_task_id": delivery_task_id,
    }


# ── Graph Template API ──────────────────────────────────────


@router.post("/graph/templates", summary="创建 Graph Template")
def create_graph_template(request: BossGraphTemplateCreateRequest):
    """保存自定义 DAG 配置为可复用模板"""
    # 校验图合法性
    graph = _build_custom_graph_from_nodes_edges(request.nodes, request.edges)
    validation = validate_graph(graph)
    if not validation.valid:
        raise HTTPException(status_code=400, detail={
            "message": "协作图校验失败",
            "errors": validation.errors,
            "warnings": validation.warnings,
        })

    from backend.services.graph_template_store import save_template, get_template

    nodes_data = [n.model_dump() for n in request.nodes]
    edges_data = [e.model_dump() for e in request.edges]

    template = save_template(
        name=request.name,
        nodes=nodes_data,
        edges=edges_data,
        description=request.description,
        goal_hint=request.goal_hint,
        canvas_layout=request.canvas_layout,
    )

    # 审计日志
    from backend.services.graph_template_audit import append_event
    if request.source_template_id:
        source_name = ""
        source_t = get_template(request.source_template_id)
        if source_t:
            source_name = source_t.get("name", "")
        append_event(
            template["template_id"], "clone",
            f"克隆模板「{request.name}」← 「{source_name}」",
            {
                "source_template_id": request.source_template_id,
                "source_name": source_name,
                "new_template_id": template["template_id"],
                "node_count": len(nodes_data),
                "edge_count": len(edges_data),
            },
        )
    else:
        append_event(
            template["template_id"], "create",
            f"创建模板「{request.name}」",
            {"node_count": len(nodes_data), "edge_count": len(edges_data)},
        )

    return {"ok": True, "template": template}


@router.get("/graph/templates", summary="列出 Graph Templates")
def list_graph_templates():
    """列出所有已保存的 graph template"""
    from backend.services.graph_template_store import list_templates

    templates = list_templates()
    return {"ok": True, "templates": templates, "total": len(templates)}


@router.get("/graph/templates/{template_id}", summary="获取单个 Graph Template")
def get_graph_template(template_id: str):
    """获取指定 template 的完整配置"""
    from backend.services.graph_template_store import get_template

    template = get_template(template_id)
    if template is None:
        raise HTTPException(status_code=404, detail=f"模板 {template_id} 不存在")
    return {"ok": True, "template": template}


@router.put("/graph/templates/{template_id}", summary="更新 Graph Template")
def update_graph_template(template_id: str, request: BossGraphTemplateCreateRequest):
    """更新已有的 graph template"""
    from backend.services.graph_template_store import get_template, update_template

    existing = get_template(template_id)
    if existing is None:
        raise HTTPException(status_code=404, detail=f"模板 {template_id} 不存在")

    # 校验图合法性
    graph = _build_custom_graph_from_nodes_edges(request.nodes, request.edges)
    validation = validate_graph(graph)
    if not validation.valid:
        raise HTTPException(status_code=400, detail={
            "message": "协作图校验失败",
            "errors": validation.errors,
            "warnings": validation.warnings,
        })

    nodes_data = [n.model_dump() for n in request.nodes]
    edges_data = [e.model_dump() for e in request.edges]

    template = update_template(
        template_id=template_id,
        name=request.name,
        nodes=nodes_data,
        edges=edges_data,
        description=request.description,
        goal_hint=request.goal_hint,
        canvas_layout=request.canvas_layout,
    )
    if template is None:
        raise HTTPException(status_code=404, detail=f"模板 {template_id} 不存在")

    # 审计日志
    from backend.services.graph_template_audit import append_event
    append_event(
        template_id, "update",
        f"更新模板「{request.name}」",
        {"node_count": len(nodes_data), "edge_count": len(edges_data)},
    )

    return {"ok": True, "template": template}


class CanvasLayoutRequest(BaseModel):
    """更新 Canvas 布局请求"""
    canvas_layout: Dict[str, Dict[str, float]] = Field(
        ..., description="节点布局 {node_id: {x: float, y: float}}"
    )


@router.patch("/graph/templates/{template_id}/layout", summary="更新 Canvas 布局")
def update_canvas_layout(template_id: str, request: CanvasLayoutRequest):
    """仅更新模板的 Canvas 节点布局（不创建版本快照）"""
    from backend.services.graph_template_store import update_canvas_layout as store_update_layout

    template = store_update_layout(template_id, request.canvas_layout)
    if template is None:
        raise HTTPException(status_code=404, detail=f"模板 {template_id} 不存在")
    return {"ok": True, "template": template}


@router.delete("/graph/templates/{template_id}", summary="删除 Graph Template")
def delete_graph_template(template_id: str):
    """删除指定 template"""
    from backend.services.graph_template_store import delete_template, get_template

    # 审计日志（删除前记录）
    existing = get_template(template_id)
    if existing is None:
        raise HTTPException(status_code=404, detail=f"模板 {template_id} 不存在")

    from backend.services.graph_template_audit import append_event
    append_event(
        template_id, "delete",
        f"删除模板「{existing.get('name', '')}」",
        {
            "template_name": existing.get("name", ""),
            "node_count": len(existing.get("nodes", [])),
            "edge_count": len(existing.get("edges", [])),
            "deleted_at": datetime.now(timezone.utc).isoformat(),
        },
    )

    try:
        deleted = delete_template(template_id)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"删除失败: {e}")

    if not deleted:
        raise HTTPException(status_code=404, detail=f"模板 {template_id} 不存在")
    return {"ok": True, "deleted": True, "template_id": template_id}


# ── Phase 6.6: 版本历史 API ────────────────────────────────


@router.get("/graph/templates/{template_id}/versions", summary="列出 Template 版本历史")
def list_graph_template_versions(template_id: str):
    """列出模板的版本历史（摘要，不含完整 nodes/edges）"""
    from backend.services.graph_template_store import get_template, list_versions

    template = get_template(template_id)
    if template is None:
        raise HTTPException(status_code=404, detail=f"模板 {template_id} 不存在")

    versions = list_versions(template_id)
    return {"ok": True, "versions": versions, "total": len(versions)}


@router.get(
    "/graph/templates/{template_id}/versions/compare",
    summary="版本对比",
)
def compare_graph_template_versions(
    template_id: str,
    from_version: str = Query(..., alias="from", description="起始版本 ID"),
    to_version: str = Query(..., alias="to", description="目标版本 ID 或 current"),
):
    """对比两个版本或版本与当前模板的差异"""
    from backend.services.graph_template_store import (
        get_template,
        compare_versions,
        _is_valid_version_id,
    )

    template = get_template(template_id)
    if template is None:
        raise HTTPException(status_code=404, detail=f"模板 {template_id} 不存在")

    if not from_version:
        raise HTTPException(status_code=400, detail="缺少参数 from")

    if not to_version:
        raise HTTPException(status_code=400, detail="缺少参数 to")

    if not _is_valid_version_id(from_version):
        raise HTTPException(status_code=400, detail=f"无效的版本 ID: {from_version}")

    if to_version != "current" and not _is_valid_version_id(to_version):
        raise HTTPException(status_code=400, detail=f"无效的版本 ID: {to_version}")

    if from_version == to_version:
        raise HTTPException(status_code=400, detail="不能对比同一个版本")

    diff = compare_versions(template_id, from_version, to_version)
    if diff is None:
        raise HTTPException(status_code=404, detail="版本不存在或不属于该模板")

    return {"ok": True, "diff": diff}


@router.get(
    "/graph/templates/{template_id}/versions/{version_id}",
    summary="获取版本详情",
)
def get_graph_template_version(template_id: str, version_id: str):
    """获取指定版本的完整快照数据"""
    from backend.services.graph_template_store import get_template, get_version

    template = get_template(template_id)
    if template is None:
        raise HTTPException(status_code=404, detail=f"模板 {template_id} 不存在")

    version = get_version(template_id, version_id)
    if version is None:
        raise HTTPException(status_code=404, detail=f"版本 {version_id} 不存在")

    return {"ok": True, "version": version}


@router.post(
    "/graph/templates/{template_id}/versions/{version_id}/restore",
    summary="回滚到指定版本",
)
def restore_graph_template_version(template_id: str, version_id: str):
    """回滚模板到指定版本。回滚前自动保存当前版本。"""
    from backend.services.graph_template_store import (
        get_template,
        get_version,
        save_version_snapshot,
        update_template,
    )

    template = get_template(template_id)
    if template is None:
        raise HTTPException(status_code=404, detail=f"模板 {template_id} 不存在")

    version = get_version(template_id, version_id)
    if version is None:
        raise HTTPException(status_code=404, detail=f"版本 {version_id} 不存在")

    try:
        restore_request = BossGraphTemplateCreateRequest(
            name=version.get("name", ""),
            description=version.get("description", ""),
            goal_hint=version.get("goal_hint", ""),
            nodes=version.get("nodes", []),
            edges=version.get("edges", []),
        )
    except ValidationError as error:
        raise HTTPException(status_code=409, detail={
            "message": "版本快照格式无效，无法回滚",
            "errors": error.errors(),
        }) from error

    graph = _build_custom_graph_from_nodes_edges(
        restore_request.nodes,
        restore_request.edges,
    )
    validation = validate_graph(graph)
    if not validation.valid:
        raise HTTPException(status_code=409, detail={
            "message": "版本快照协作图无效，无法回滚",
            "errors": validation.errors,
            "warnings": validation.warnings,
        })

    # 回滚前先保存当前版本
    save_version_snapshot(template_id, template)

    # 恢复目标版本（跳过自动快照，避免重复保存）
    restored = update_template(
        template_id=template_id,
        name=restore_request.name,
        nodes=[node.model_dump() for node in restore_request.nodes],
        edges=[edge.model_dump() for edge in restore_request.edges],
        description=restore_request.description,
        goal_hint=restore_request.goal_hint,
        skip_version_snapshot=True,
    )

    if restored is None:
        raise HTTPException(status_code=500, detail="回滚失败")

    # 审计日志
    from backend.services.graph_template_audit import append_event
    append_event(
        template_id, "restore",
        f"回滚到版本 {version_id}",
        {"restored_from_version": version_id, "version_name": version.get("name", "")},
    )

    return {"ok": True, "template": restored, "restored_from_version": version_id}


@router.patch(
    "/graph/templates/{template_id}/versions/{version_id}",
    summary="更新版本元数据",
)
def update_graph_template_version_metadata(
    template_id: str,
    version_id: str,
    request: BossVersionMetadataUpdateRequest,
):
    """更新版本的 label/note 元数据（不可修改快照内容）"""
    from backend.services.graph_template_store import (
        get_template,
        update_version_metadata,
    )

    template = get_template(template_id)
    if template is None:
        raise HTTPException(status_code=404, detail=f"模板 {template_id} 不存在")

    if request.label is None and request.note is None:
        raise HTTPException(status_code=400, detail="至少需要提供 label 或 note")

    try:
        updated = update_version_metadata(
            template_id=template_id,
            version_id=version_id,
            label=request.label,
            note=request.note,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e

    if updated is None:
        raise HTTPException(status_code=404, detail=f"版本 {version_id} 不存在")

    # 审计日志
    from backend.services.graph_template_audit import append_event
    changes = {}
    if request.label is not None:
        changes["label"] = request.label
    if request.note is not None:
        changes["note"] = request.note[:100]
    append_event(
        template_id, "metadata_update",
        f"更新版本 {version_id} 元数据",
        {"version_id": version_id, "changes": changes},
    )

    return {"ok": True, "version": updated}


@router.post("/graph/templates/{template_id}/execute", summary="按 Graph Template 执行")
def execute_graph_template(template_id: str, request: BossGraphTemplateExecuteRequest):
    """读取 template 配置并执行 DAG"""
    from backend.services.graph_template_store import get_template

    template = get_template(template_id)
    if template is None:
        raise HTTPException(status_code=404, detail=f"模板 {template_id} 不存在")

    # 构造 BossGraphExecuteRequest 并复用执行逻辑
    nodes = [BossGraphNodeRequest(**n) for n in template["nodes"]]
    edges = [BossGraphEdgeRequest(**e) for e in template.get("edges", [])]

    execute_request = BossGraphExecuteRequest(
        goal=request.goal,
        nodes=nodes,
        edges=edges,
        save_to_delivery=request.save_to_delivery,
    )

    # 审计日志
    from backend.services.graph_template_audit import append_event
    append_event(
        template_id, "execute",
        f"执行模板「{template.get('name', '')}」",
        {"goal": request.goal[:200], "node_count": len(nodes)},
    )

    return boss_graph_execute(execute_request)


# ── Phase 6.8: 审计日志 & 版本固定 API ─────────────────────


@router.get(
    "/graph/templates/{template_id}/audit",
    summary="查询模板审计日志",
)
def list_graph_template_audit(
    template_id: str,
    event_type: Optional[str] = Query(default=None, description="按事件类型过滤"),
    limit: int = Query(default=100, ge=1, le=500, description="最大返回条数"),
):
    """查询模板的审计日志"""
    from backend.services.graph_template_store import get_template
    from backend.services.graph_template_audit import list_events, _EVENT_TYPES

    template = get_template(template_id)

    if event_type and event_type not in _EVENT_TYPES:
        raise HTTPException(
            status_code=400,
            detail=f"无效的事件类型: {event_type}，可选: {', '.join(sorted(_EVENT_TYPES))}",
        )

    events = list_events(template_id, event_type=event_type, limit=limit)

    # 模板已删除但审计文件仍存在 → 返回 events + deleted 标记
    if template is None:
        if not events:
            raise HTTPException(status_code=404, detail=f"模板 {template_id} 不存在且无审计记录")
        return {"ok": True, "events": events, "total": len(events), "deleted": True}

    return {"ok": True, "events": events, "total": len(events)}


@router.post(
    "/graph/templates/{template_id}/versions/{version_id}/pin",
    summary="固定版本",
)
def pin_graph_template_version(template_id: str, version_id: str):
    """固定版本，防止被自动裁剪"""
    from backend.services.graph_template_store import get_template, pin_version

    template = get_template(template_id)
    if template is None:
        raise HTTPException(status_code=404, detail=f"模板 {template_id} 不存在")

    result = pin_version(template_id, version_id)
    if result is None:
        raise HTTPException(status_code=404, detail=f"版本 {version_id} 不存在")

    # 审计日志
    from backend.services.graph_template_audit import append_event
    append_event(
        template_id, "pin",
        f"固定版本 {version_id}",
        {"version_id": version_id},
    )

    return {"ok": True, "version": result}


@router.post(
    "/graph/templates/{template_id}/versions/{version_id}/unpin",
    summary="取消固定版本",
)
def unpin_graph_template_version(template_id: str, version_id: str):
    """取消固定版本"""
    from backend.services.graph_template_store import get_template, unpin_version

    template = get_template(template_id)
    if template is None:
        raise HTTPException(status_code=404, detail=f"模板 {template_id} 不存在")

    result = unpin_version(template_id, version_id)
    if result is None:
        raise HTTPException(status_code=404, detail=f"版本 {version_id} 不存在")

    # 审计日志
    from backend.services.graph_template_audit import append_event
    append_event(
        template_id, "unpin",
        f"取消固定版本 {version_id}",
        {"version_id": version_id},
    )

    return {"ok": True, "version": result}


# ── Phase 6.9: Audit Retention Policy API ────────────────────


class AuditCleanupRequest(BaseModel):
    """审计日志清理请求"""
    retention_days: int = Field(..., ge=1, description="保留天数（必须 >= 1）")
    dry_run: bool = Field(default=True, description="True 只预览不删除，False 实际删除")


@router.get(
    "/graph/audit/storage",
    summary="查询审计存储信息",
)
def get_audit_storage():
    """返回审计文件数量、总大小、最早/最新事件时间"""
    from backend.services.graph_template_retention import summarize_audit_storage

    summary = summarize_audit_storage()
    return {"ok": True, "storage": summary}


@router.post(
    "/graph/audit/cleanup",
    summary="清理过期审计日志",
)
def cleanup_audit_logs(request: AuditCleanupRequest):
    """清理已删除模板的过期审计日志。

    - dry_run=True（默认）：只返回将删除的文件，不实际删除
    - dry_run=False：实际删除
    """
    from backend.services.graph_template_retention import cleanup_audit_logs

    try:
        result = cleanup_audit_logs(
            retention_days=request.retention_days,
            dry_run=request.dry_run,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    return {"ok": True, "cleanup": result}


def _build_custom_graph_from_nodes_edges(
    nodes: List[BossGraphNodeRequest],
    edges: List[BossGraphEdgeRequest],
) -> CollaborationGraph:
    """从 nodes/edges 列表构造 CollaborationGraph（用于模板校验）"""
    graph_nodes = [
        CollaborationNode(
            id=n.id,
            agent_id=n.agent_id,
            label=n.title,
            config={"task_type": n.task_type, "prompt": n.prompt},
        )
        for n in nodes
    ]
    graph_edges = [
        CollaborationEdge(
            from_node=e.from_node,
            to_node=e.to_node,
            label=e.handoff_type,
        )
        for e in edges
    ]
    return CollaborationGraph(nodes=graph_nodes, edges=graph_edges)


def _render_boss_lite_md(goal: str, plan: list, results: list, boss_so: dict) -> str:
    """渲染 Boss Lite 汇总报告为 Markdown — 老板可直接阅读的作战简报"""
    total_dur = boss_so.get("total_duration_ms", 0)
    total_sec = f"{total_dur / 1000:.1f}" if total_dur else "—"

    lines = [
        "# Boss Lite 作战报告",
        "",
        "## 总目标",
        "",
        goal,
        "",
        f"**总耗时：{total_sec} 秒**",
        "",
        "---",
        "",
        "## 一、执行计划",
        "",
    ]

    for task in plan:
        status_icon = "✅" if task["status"] == "done" else "❌" if task["status"] == "failed" else "⏳"
        # 从 results 中找对应 agent 的 duration_ms
        agent_dur = ""
        for r in results:
            if r["agent_id"] == task["agent_id"] and r.get("duration_ms"):
                agent_dur = f" （耗时 {r['duration_ms'] / 1000:.1f}s）"
                break
        lines.append(f"- {status_icon} **{task['title']}** — {task['purpose']}{agent_dur}")
    lines.append("")

    lines += ["---", "", "## 二、各部门结论", ""]

    for r in results:
        so = r.get("structured_output") or {}
        agent_id = r["agent_id"]
        status_icon = "✅" if r["ok"] else "❌"
        dur = r.get("duration_ms", 0)
        dur_str = f" （耗时 {dur / 1000:.1f}s）" if dur else ""

        lines.append(f"### {status_icon} {r['title']}{dur_str}")
        lines.append("")

        # 按 agent 类型提取关键信息
        if agent_id == "research":
            _render_research_section(lines, r, so)
        elif agent_id == "marketing":
            _render_marketing_section(lines, r, so)
        elif agent_id == "image":
            _render_image_section(lines, r, so)
        elif agent_id == "data":
            _render_data_section(lines, r, so)
        elif agent_id == "website":
            _render_website_section(lines, r, so)
        else:
            _render_generic_section(lines, r, so)

        if r.get("error"):
            lines.append(f"⚠️ 错误: {r['error']}")
            lines.append("")

    # Boss 最终建议 — 基于实际结果动态生成
    lines += ["---", "", "## 三、上游洞察传递", ""]

    handoff_ctx = boss_so.get("handoff_context", {})
    handoff_enabled = boss_so.get("handoff_enabled", False)
    handoff_targets = boss_so.get("handoff_targets", [])
    target_text = " / ".join(_HANDOFF_CN_LABELS.get(target, target) for target in handoff_targets) or "下游部门"
    if handoff_enabled and handoff_ctx:
        has_research = bool(handoff_ctx.get("research_summary"))
        has_data = bool(handoff_ctx.get("data_key_metrics"))
        if has_research:
            lines.append(f"- **上下文整理 → {target_text}**")
            if handoff_ctx["research_summary"]:
                lines.append(f"  - 摘要：{handoff_ctx['research_summary'][:200]}")
            for item in handoff_ctx.get("research_key_findings", [])[:3]:
                lines.append(f"  - 关键发现：{_format_boss_value(item)}")
            for item in handoff_ctx.get("research_opportunities", [])[:2]:
                lines.append(f"  - 机会：{_format_boss_value(item)}")
            lines.append("")
        if has_data:
            lines.append(f"- **数据洞察 → {target_text}**")
            for item in handoff_ctx.get("data_key_metrics", [])[:3]:
                lines.append(f"  - 核心指标：{_format_boss_value(item)}")
            for item in handoff_ctx.get("data_findings", [])[:3]:
                lines.append(f"  - 数据发现：{_format_boss_value(item)}")
            for item in handoff_ctx.get("data_recommendations", [])[:2]:
                lines.append(f"  - 行动建议：{_format_boss_value(item)}")
            lines.append("")
    else:
        lines.append("本次未启用上游洞察传递。")
        lines.append("")

    lines += ["---", "", "## 四、Boss 最终建议", ""]

    succeeded_agents = [r["agent_id"] for r in results if r["ok"]]
    failed_agents = [r["agent_id"] for r in results if not r["ok"]]

    if "research" in succeeded_agents:
        lines.append("- **先做什么：** 确认上下文整理的核心发现，验证目标对象需求和关键差异")
    elif "marketing" in succeeded_agents:
        lines.append("- **先做什么：** 基于沟通表达方案准备第一批可验证材料")
    elif "data" in succeeded_agents:
        lines.append("- **先做什么：** 先建立关键指标看板，用数据确认最值得投入的方向")
    elif "website" in succeeded_agents:
        lines.append("- **先做什么：** 先把交付物核心结构搭出来，验证交付路径是否清晰")
    elif "image" in succeeded_agents:
        lines.append("- **先做什么：** 先统一素材方向，产出第一批可用于测试的素材")
    else:
        lines.append("- **先做什么：** 先重新执行 Boss Lite，补齐可用的部门输出")

    if "marketing" in succeeded_agents and "image" in succeeded_agents:
        lines.append("- **再做什么：** 结合沟通表达和素材方向，制作可用于验证的图文素材")
    elif "website" in succeeded_agents:
        lines.append("- **再做什么：** 参考交付物结构完成首版交付，配合沟通节奏上线")

    if "data" in succeeded_agents:
        lines.append("- **数据追踪：** 按数据洞察框架建立效果追踪体系，每周复盘关键指标")

    if failed_agents:
        failed_titles = [r["title"] for r in results if not r["ok"]]
        lines.append(f"- **风险提醒：** {', '.join(failed_titles)} 执行失败，建议手动补充或重新执行")

    lines.append("- **下一步行动：** 选择 1-2 个最可行的方向，先跑最小可行版本（MVP），根据数据反馈迭代")
    lines.append("")

    lines += [
        "---",
        "",
        f"*由 AI Company OS Boss Lite 生成 · {boss_so.get('generated_at', '')}*",
    ]

    return "\n".join(lines)


def _render_research_section(lines: list, r: dict, so: dict):
    """渲染上下文整理结论"""
    summary = r.get("summary") or so.get("summary") or so.get("market_summary", "")
    if summary:
        lines.append(f"- **摘要：** {summary[:200]}")
        lines.append("")

    key_findings = so.get("key_findings") or so.get("findings", [])
    if key_findings and isinstance(key_findings, list):
        lines.append("- **关键发现：**")
        for item in key_findings[:5]:
            lines.append(f"  - {_format_boss_value(item)}")
        lines.append("")

    opportunities = so.get("opportunities", [])
    if opportunities and isinstance(opportunities, list):
        lines.append("- **机会：**")
        for item in opportunities[:3]:
            lines.append(f"  - {_format_boss_value(item)}")
        lines.append("")

    risks = so.get("risks", [])
    if risks and isinstance(risks, list):
        lines.append("- **风险：**")
        for item in risks[:3]:
            lines.append(f"  - {_format_boss_value(item)}")
        lines.append("")


def _render_marketing_section(lines: list, r: dict, so: dict):
    """渲染沟通表达结论"""
    headline = so.get("headline", "")
    if headline:
        lines.append(f"- **核心文案：** {headline}")
        lines.append("")

    body = so.get("body", "")
    if body and isinstance(body, str):
        lines.append(f"- **文案正文：** {body[:300]}")
        lines.append("")

    cta = so.get("cta", "")
    if cta:
        lines.append(f"- **CTA：** {cta}")
        lines.append("")

    selling_points = so.get("selling_points") or so.get("key_findings", [])
    if selling_points and isinstance(selling_points, list):
        lines.append("- **核心卖点：**")
        for item in selling_points[:5]:
            lines.append(f"  - {_format_boss_value(item)}")
        lines.append("")

    keywords = so.get("keywords") or so.get("hashtags", [])
    if keywords and isinstance(keywords, list):
        lines.append(f"- **关键词：** {', '.join(_format_boss_value(k) for k in keywords[:8])}")
        lines.append("")


def _render_image_section(lines: list, r: dict, so: dict):
    """渲染素材方向结论"""
    style = so.get("style", "")
    if style:
        lines.append(f"- **视觉风格：** {style}")
        lines.append("")

    image_prompt = so.get("image_prompt", "")
    if image_prompt:
        lines.append(f"- **图片提示词：** {image_prompt[:200]}")
        lines.append("")

    color_palette = so.get("color_palette", "")
    if color_palette:
        lines.append(f"- **色彩方案：** {_format_boss_value(color_palette)}")
        lines.append("")

    usage = so.get("usage_suggestions", "")
    if usage:
        lines.append(f"- **使用建议：** {_format_boss_value(usage)[:200]}")
        lines.append("")


def _render_data_section(lines: list, r: dict, so: dict):
    """渲染数据洞察结论"""
    question = so.get("analysis_question", "")
    if question:
        lines.append(f"- **分析主题：** {question}")
        lines.append("")

    metrics = so.get("key_metrics", [])
    if metrics and isinstance(metrics, list):
        lines.append("- **关键指标：**")
        for item in metrics[:5]:
            lines.append(f"  - {_format_boss_value(item)}")
        lines.append("")

    findings = so.get("findings", [])
    if findings and isinstance(findings, list):
        lines.append("- **发现：**")
        for item in findings[:5]:
            lines.append(f"  - {_format_boss_value(item)}")
        lines.append("")

    recommendations = so.get("recommendations", [])
    if recommendations and isinstance(recommendations, list):
        lines.append("- **建议：**")
        for item in recommendations[:5]:
            lines.append(f"  - {_format_boss_value(item)}")
        lines.append("")


def _render_website_section(lines: list, r: dict, so: dict):
    """渲染交付物结构结论"""
    page_goal = so.get("page_goal", "")
    if page_goal:
        lines.append(f"- **交付目标：** {page_goal}")
        lines.append("")

    hero = so.get("hero", {})
    if hero and isinstance(hero, dict):
        hero_headline = hero.get("headline", "")
        hero_sub = hero.get("subheadline", "")
        hero_cta = hero.get("cta", "")
        if hero_headline:
            lines.append(f"- **核心标题：** {hero_headline}")
        if hero_sub:
            lines.append(f"  - 副标题：{hero_sub}")
        if hero_cta:
            lines.append(f"  - CTA：{hero_cta}")
        lines.append("")

    sections = so.get("sections", [])
    if sections and isinstance(sections, list):
        lines.append("- **交付板块：**")
        for item in sections[:5]:
            if isinstance(item, dict):
                lines.append(f"  - {item.get('title', item.get('name', str(item)))}")
            else:
                lines.append(f"  - {item}")
        lines.append("")

    ctas = so.get("ctas", [])
    if ctas and isinstance(ctas, list):
        lines.append(f"- **CTA：** {', '.join(_format_boss_value(c) for c in ctas[:3])}")
        lines.append("")

    seo = so.get("seo", {})
    if seo and isinstance(seo, dict):
        lines.append("- **检索展示建议：**")
        for k, v in list(seo.items())[:3]:
            lines.append(f"  - {k}: {v}")
        lines.append("")


def _render_generic_section(lines: list, r: dict, so: dict):
    """渲染通用结论（未知 agent 类型）"""
    summary = r.get("summary") or so.get("summary", "")
    if summary:
        lines.append(f"- **摘要：** {summary[:200]}")
        lines.append("")

    # 提取常见字段
    for key in ["headline", "title", "content", "body", "recommendations", "findings"]:
        val = so.get(key)
        if val and isinstance(val, str):
            lines.append(f"- **{key}：** {val[:200]}")
            lines.append("")
        elif val and isinstance(val, list):
            lines.append(f"- **{key}：**")
            for item in val[:5]:
                lines.append(f"  - {_format_boss_value(item)}")
            lines.append("")


def _format_boss_value(value: Any) -> str:
    """把字符串、数组或对象压成适合 Markdown 摘要展示的一行文本。"""
    if value is None:
        return ""
    if isinstance(value, str):
        return value
    if isinstance(value, (int, float, bool)):
        return str(value)
    if isinstance(value, list):
        return "；".join(_format_boss_value(item) for item in value if item is not None)
    if isinstance(value, dict):
        name = value.get("name") or value.get("title") or value.get("metric") or value.get("label")
        description = value.get("description") or value.get("summary") or value.get("value")
        formula = value.get("formula")
        parts = [str(part) for part in [name, description] if part]
        if formula:
            parts.append(f"公式：{formula}")
        if parts:
            return " — ".join(parts)
        return "；".join(f"{key}: {_format_boss_value(val)}" for key, val in list(value.items())[:4])
    return str(value)
