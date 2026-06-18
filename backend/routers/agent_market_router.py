"""Agent 市场路由 — Agent 发现、安装、管理"""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from typing import Any, Dict, List, Optional

router = APIRouter(prefix="/marketplace", tags=["Agent 市场 / Marketplace"])


class InstallRequest(BaseModel):
    agent_id: str


class UninstallRequest(BaseModel):
    agent_id: str


class SearchRequest(BaseModel):
    query: str


@router.get("/agents", summary="列出所有可用 Agent")
def list_agents(category: str = None):
    """列出市场中所有可用的 Agent"""
    from core.agent_marketplace import get_marketplace
    mp = get_marketplace()
    return {
        "agents": mp.list_available(category),
        "stats": mp.get_stats(),
    }


@router.get("/agents/{agent_id}", summary="获取 Agent 详情")
def get_agent(agent_id: str):
    """获取指定 Agent 的详细信息"""
    from core.agent_marketplace import get_marketplace
    mp = get_marketplace()
    agent = mp.get_agent(agent_id)
    if not agent:
        raise HTTPException(status_code=404, detail="Agent 不存在")
    return agent


@router.post("/search", summary="搜索 Agent")
def search_agents(request: SearchRequest):
    """搜索 Agent"""
    from core.agent_marketplace import get_marketplace
    mp = get_marketplace()
    return {"results": mp.search(request.query)}


@router.post("/install", summary="安装 Agent")
def install_agent(request: InstallRequest):
    """安装指定 Agent"""
    from core.agent_marketplace import get_marketplace
    mp = get_marketplace()
    result = mp.install(request.agent_id)
    if not result.get("ok"):
        raise HTTPException(status_code=400, detail=result.get("error"))
    return result


@router.post("/uninstall", summary="卸载 Agent")
def uninstall_agent(request: UninstallRequest):
    """卸载指定 Agent"""
    from core.agent_marketplace import get_marketplace
    mp = get_marketplace()
    result = mp.uninstall(request.agent_id)
    if not result.get("ok"):
        raise HTTPException(status_code=400, detail=result.get("error"))
    return result


@router.get("/installed", summary="已安装的 Agent")
def list_installed():
    """列出已安装的 Agent"""
    from core.agent_marketplace import get_marketplace
    mp = get_marketplace()
    return {"agents": mp.list_installed()}


@router.get("/categories", summary="Agent 分类")
def list_categories():
    """获取所有 Agent 分类"""
    from core.agent_marketplace import get_marketplace
    mp = get_marketplace()
    return {"categories": mp.get_categories()}
