"""Boss Router — 老板运营指挥台 API"""
from typing import Optional, List, Dict
from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import Response
from pydantic import BaseModel, Field
from backend.services.boss_command_center import get_boss_command_center, MODULE_ORDER
from backend.security import input_validator, rate_limiter

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
    from backend.governance.guard import guard_payload, governance_block_response
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
    from backend.governance.guard import guard_payload, governance_block_response
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
    from backend.governance.guard import guard_payload, governance_block_response
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
    from backend.governance.guard import guard_payload, governance_block_response
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
