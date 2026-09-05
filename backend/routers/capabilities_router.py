"""
Capabilities Router — 本地能力扫描接口
"""
from fastapi import APIRouter
from backend.ai_registry import get_registry
from backend.logger import get_logger

logger = get_logger()
router = APIRouter(prefix="/capabilities", tags=["Capabilities / 本地能力"])


@router.get("", summary="获取所有本地能力")
async def get_capabilities():
    """获取所有本地工具的扫描结果"""
    return get_registry().scan_runtime_capabilities()


@router.post("/refresh", summary="刷新能力扫描")
async def refresh_capabilities():
    """强制重新扫描所有本地工具"""
    return get_registry().scan_runtime_capabilities(force=True)


@router.get("/summary", summary="获取能力摘要")
async def get_capabilities_summary():
    """获取本地能力摘要"""
    snapshot = get_registry().scan_runtime_capabilities()
    return {**snapshot["summary"], "scan": snapshot["scan"]}
