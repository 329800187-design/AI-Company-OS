"""Brain Manager 路由 — 主脑切换与能力扫描"""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from typing import Any, Dict, List, Optional

router = APIRouter(prefix="/brain", tags=["主脑管理 / Brain Manager"])


class SwitchRequest(BaseModel):
    brain_id: str


class EnableRequest(BaseModel):
    brain_id: str


@router.get("/", summary="获取系统状态")
def get_status():
    """获取系统状态（面向小白）"""
    from backend.config import get_system_status
    return get_system_status()


@router.get("/list", summary="列出所有主脑")
def list_brains():
    """列出所有可用的 AI 主脑"""
    from core.brain_manager import get_brain_manager
    mgr = get_brain_manager()
    return {
        "brains": mgr.list_all(),
        "available": mgr.list_available(),
        "current": mgr.get_current(),
    }


@router.get("/current", summary="获取当前主脑")
def get_current():
    """获取当前使用的主脑"""
    from core.brain_manager import get_brain_manager
    return get_brain_manager().get_current()


@router.post("/switch", summary="切换主脑")
def switch_brain(request: SwitchRequest):
    """切换 AI 主脑（DeepSeek/MiMo/Claude/OpenAI/Ollama/LM Studio/CC Switch）"""
    from core.brain_manager import get_brain_manager
    mgr = get_brain_manager()
    result = mgr.switch_to(request.brain_id)
    if not result.get("ok"):
        raise HTTPException(status_code=400, detail=result.get("error"))
    return result


@router.post("/enable", summary="启用主脑")
def enable_brain(request: EnableRequest):
    """启用指定主脑"""
    from core.brain_manager import get_brain_manager
    mgr = get_brain_manager()
    result = mgr.enable_brain(request.brain_id)
    if not result.get("ok"):
        raise HTTPException(status_code=400, detail=result.get("error"))
    return result


@router.post("/disable", summary="禁用主脑")
def disable_brain(request: EnableRequest):
    """禁用指定主脑"""
    from core.brain_manager import get_brain_manager
    mgr = get_brain_manager()
    result = mgr.disable_brain(request.brain_id)
    if not result.get("ok"):
        raise HTTPException(status_code=400, detail=result.get("error"))
    return result


@router.get("/health", summary="主脑健康检查")
def health_check():
    """检查所有主脑的健康状态"""
    from core.brain_manager import get_brain_manager
    return get_brain_manager().health_check()


@router.get("/auto-select", summary="自动选择最佳主脑")
def auto_select():
    """自动选择最佳可用主脑"""
    from core.brain_manager import get_brain_manager
    mgr = get_brain_manager()
    brain_id = mgr.auto_select()
    return {"brain_id": brain_id, "brain": mgr.get_brain(brain_id)}


# ── 能力扫描 ──────────────────────────────────────────────

@router.get("/capabilities", summary="扫描本机能力")
def scan_capabilities(force: bool = False):
    """扫描本机可用的 AI 服务、浏览器、工具和 Agent"""
    from core.capability_scanner import get_capability_scanner
    scanner = get_capability_scanner()
    return scanner.scan_all(force=force)


@router.get("/capabilities/ai-services", summary="可用 AI 服务")
def list_ai_services():
    """列出本机可用的 AI 服务"""
    from core.capability_scanner import get_capability_scanner
    scanner = get_capability_scanner()
    return {"services": scanner.get_available_ai_services()}


@router.get("/capabilities/best", summary="最佳 AI 服务")
def get_best_ai():
    """获取最佳可用 AI 服务"""
    from core.capability_scanner import get_capability_scanner
    scanner = get_capability_scanner()
    best = scanner.get_best_ai_service()
    return best or {"error": "没有可用的 AI 服务"}
