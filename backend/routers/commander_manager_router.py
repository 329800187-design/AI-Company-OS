"""Commander 管理路由 — 主智能体切换与配置"""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from typing import Any, Dict, List, Optional

router = APIRouter(prefix="/commanders", tags=["指挥官管理 / Commander Manager"])


class SwitchRequest(BaseModel):
    commander_id: str


class RegisterCustomRequest(BaseModel):
    commander_id: str
    name: str
    description: str
    icon: str = "🧠"
    module_path: str
    class_name: str
    capabilities: List[str] = []
    config: Dict[str, Any] = {}


class UpdateConfigRequest(BaseModel):
    commander_id: str
    config: Dict[str, Any]


@router.get("/", summary="列出所有可用指挥官")
def list_commanders():
    """列出所有可用的指挥官（主智能体）"""
    from core.commander_manager import get_commander_manager
    mgr = get_commander_manager()
    return {
        "commanders": mgr.list_all(),
        "current": mgr.get_current(),
    }


@router.get("/current", summary="获取当前指挥官")
def get_current():
    """获取当前激活的指挥官"""
    from core.commander_manager import get_commander_manager
    mgr = get_commander_manager()
    return mgr.get_current()


@router.post("/switch", summary="切换指挥官")
def switch_commander(request: SwitchRequest):
    """切换当前指挥官（主智能体）"""
    from core.commander_manager import get_commander_manager
    mgr = get_commander_manager()
    result = mgr.switch_to(request.commander_id)
    if not result.get("ok"):
        raise HTTPException(status_code=400, detail=result.get("error"))
    return result


@router.post("/register", summary="注册自定义指挥官")
def register_commander(request: RegisterCustomRequest):
    """注册一个自定义指挥官"""
    from core.commander_manager import get_commander_manager, CommanderProfile
    mgr = get_commander_manager()
    profile = CommanderProfile(
        commander_id=request.commander_id,
        name=request.name,
        description=request.description,
        icon=request.icon,
        module_path=request.module_path,
        class_name=request.class_name,
        capabilities=request.capabilities,
        config=request.config,
    )
    result = mgr.register_custom(profile)
    if not result.get("ok"):
        raise HTTPException(status_code=400, detail=result.get("error"))
    return result


@router.delete("/{commander_id}", summary="注销自定义指挥官")
def unregister_commander(commander_id: str):
    """注销一个自定义指挥官"""
    from core.commander_manager import get_commander_manager
    mgr = get_commander_manager()
    result = mgr.unregister_custom(commander_id)
    if not result.get("ok"):
        raise HTTPException(status_code=400, detail=result.get("error"))
    return result


@router.put("/config", summary="更新指挥官配置")
def update_config(request: UpdateConfigRequest):
    """更新指定指挥官的配置"""
    from core.commander_manager import get_commander_manager
    mgr = get_commander_manager()
    result = mgr.update_config(request.commander_id, request.config)
    if not result.get("ok"):
        raise HTTPException(status_code=400, detail=result.get("error"))
    return result


@router.get("/health", summary="指挥官健康检查")
def health_check():
    """检查所有指挥官的健康状态"""
    from core.commander_manager import get_commander_manager
    mgr = get_commander_manager()
    return {"status": mgr.health_check()}
