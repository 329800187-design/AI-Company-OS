"""使用量统计路由器 — AI API Token 用量和成本"""
from fastapi import APIRouter, Query
from backend.services.usage_stats import get_usage_stats, get_all_time_stats, get_recent_calls

router = APIRouter(prefix="/usage", tags=["使用统计 / Usage"])


@router.get("/stats", summary="查看 AI 使用量统计",
            description="返回最近 N 小时的 AI API 调用统计（token 数、调用次数、预估费用）")
def usage_stats(hours: int = Query(24, description="统计过去多少小时的数据")):
    """查看 AI 使用量统计"""
    stats = get_usage_stats(hours=hours)
    return stats


@router.get("/total", summary="查看总使用量",
            description="返回从系统启动至今的所有 AI API 调用统计")
def usage_total():
    """查看总使用量"""
    return get_all_time_stats()


@router.get("/recent", summary="查看最近调用记录",
            description="返回最近 N 条 AI API 调用详情")
def usage_recent(limit: int = Query(50, description="返回条数")):
    """查看最近的调用记录"""
    return {"calls": get_recent_calls(limit=limit), "count": min(limit, 50)}
