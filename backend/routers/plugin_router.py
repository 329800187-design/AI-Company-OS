"""External Plugin Router"""
from fastapi import APIRouter, HTTPException
from core.plugin_loader import get_plugin_loader

router = APIRouter(prefix="/plugins", tags=["Plugins / 插件"])

@router.get("", summary="List external plugins")
def list_plugins():
    return {"plugins": get_plugin_loader().list_all()}

@router.post("/{plugin_id}/run", summary="Run external plugin")
def run_plugin(plugin_id: str, task: dict):
    result = get_plugin_loader().run(plugin_id, task)
    if not result.get("ok"): raise HTTPException(400, detail=result.get("error"))
    return result
