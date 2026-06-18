"""AI 资源注册中心路由 — 扫描、查询、路由、调用"""
from typing import Any, Dict
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from backend.ai_registry.registry import get_registry

router = APIRouter(prefix="/ai", tags=["AI 资源中心 / AI Registry"])


class AIRunRequest(BaseModel):
    """AI 资源调用请求"""
    goal: str = ""             # 用户目标描述
    prompt: str = ""           # 直接 prompt
    service_id: str = ""       # 指定服务 ID，留空=自动路由
    model: str = ""            # 模型名，留空=默认
    code: str = ""             # Codex 模式：要执行的代码

    model_config = {"populate_by_name": True, "extra": "allow"}


@router.get("/scan", summary="扫描所有 AI 资源",
           description="重新扫描本机所有可用的 AI 服务（CC Switch / OpenClaw / Codex / ChatGPT / Kimi）")
def scan_resources():
    registry = get_registry()
    services = registry.scan_all(force=True)
    return {
        "services": [s.to_dict() for s in services.values()],
        "count": len(services),
        "online": sum(1 for s in services.values() if s.status in ("online", "running")),
    }


@router.get("/list", summary="列出所有 AI 资源",
           description="返回当前注册的所有 AI 服务及其状态、能力")
def list_resources():
    registry = get_registry()
    services = registry.list_all()
    return {
        "services": services,
        "count": len(services),
        "online_count": sum(1 for s in services if s["status"] in ("online", "running")),
    }


@router.get("/capabilities", summary="获取所有可用能力",
           description="返回能力清单及其可用的 AI 服务提供者")
def get_capabilities():
    registry = get_registry()
    caps = registry.get_capabilities()
    routes = registry.CAPABILITY_ROUTES
    return {
        "capabilities": caps,
        "default_routes": {cap: svc_id for cap, (svc_id, _) in routes.items()},
    }


@router.post("/route", summary="智能路由目标",
           description="根据用户目标描述，自动匹配最合适的 AI 服务")
def route_goal(request: AIRunRequest):
    goal = request.goal or request.prompt
    if not goal:
        raise HTTPException(status_code=400, detail="请提供 goal 或 prompt")
    registry = get_registry()
    route = registry.route_by_goal(goal)
    return route


@router.post("/run", summary="调用 AI 资源执行任务",
           description="向指定或自动路由的 AI 服务发送任务并获取结果")
def run_ai(request: AIRunRequest):
    registry = get_registry()
    registry.scan_all()

    service_id = request.service_id
    if not service_id:
        route = registry.route_by_goal(request.goal or request.prompt)
        service_id = route["service"]

    payload: Dict[str, Any] = {}
    if request.prompt:
        payload["prompt"] = request.prompt
    if request.goal:
        payload["goal"] = request.goal
    if request.model:
        payload["model"] = request.model
    if request.code:
        payload["code"] = request.code

    # Always ensure prompt is populated for services that need it
    if not payload.get("prompt"):
        payload["prompt"] = payload.get("goal", "")

    result = registry.execute(service_id, payload)
    return result


@router.get("/service/{service_id}", summary="获取单个 AI 服务详情",
           description="查询指定 AI 服务的状态、能力和连接信息")
def get_service(service_id: str):
    registry = get_registry()
    svc = registry.get_service(service_id)
    if not svc:
        raise HTTPException(status_code=404, detail=f"服务不存在: {service_id}")
    return svc.to_dict()
