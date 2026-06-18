"""
Capabilities Router — 本地能力扫描接口
"""
from fastapi import APIRouter
from backend.services.capability_scanner import get_capability_scanner
from backend.logger import get_logger

logger = get_logger()
router = APIRouter(prefix="/capabilities", tags=["Capabilities / 本地能力"])


@router.get("", summary="获取所有本地能力")
async def get_capabilities():
    """获取所有本地工具的扫描结果"""
    scanner = get_capability_scanner()
    return scanner.scan_all()


@router.post("/refresh", summary="刷新能力扫描")
async def refresh_capabilities():
    """强制重新扫描所有本地工具"""
    scanner = get_capability_scanner()
    return scanner.scan_all(force=True)


@router.get("/summary", summary="获取能力摘要")
async def get_capabilities_summary():
    """获取本地能力摘要"""
    scanner = get_capability_scanner()
    scanner.scan_all()
    return scanner.get_summary()
