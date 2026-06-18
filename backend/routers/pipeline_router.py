"""
Pipeline Router — 统一任务执行接口

执行优先级：
1. 本地工具可用 -> 本地执行
2. 本地工具不可用 + 云端 fallback -> 云端执行
3. 都不可用 -> ok=false
"""
from typing import List, Optional
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from backend.services.local_agent_runtime import get_local_agent_runtime
from backend.services.delivery_pipeline import get_delivery_pipeline
from backend.security import input_validator, rate_limiter
from backend.logger import get_logger

logger = get_logger()
router = APIRouter(prefix="/pipeline", tags=["Pipeline / 任务流水线"])


class PipelineRequest(BaseModel):
    """任务请求"""
    message: str = Field(..., description="用户输入")
    context: Optional[dict] = Field(default_factory=dict, description="上下文信息")


def _convert_legacy_result(legacy_result: dict) -> dict:
    """将旧 DeliveryPipeline 结果转换为统一结构"""
    return {
        "ok": legacy_result.get("ok", False),
        "mode": legacy_result.get("mode", "local"),
        "task_id": legacy_result.get("task_id", ""),
        "task_type": legacy_result.get("task_type", "unknown"),
        "used_tools": legacy_result.get("used_agents", []),
        "tool_trace": legacy_result.get("agent_trace", []),
        "used_web_search": legacy_result.get("used_web_search", False),
        "search_mode": "local_browser" if legacy_result.get("used_web_search") else "none",
        "sources": legacy_result.get("sources", []),
        "final_answer": legacy_result.get("final_answer", ""),
        "deliverables": legacy_result.get("deliverables", {}),
        "qa": legacy_result.get("qa", {}),
        "confidence": legacy_result.get("confidence", 0.0),
        "warnings": legacy_result.get("warnings", []),
        "error": legacy_result.get("error", ""),
    }


@router.post("/execute", summary="执行任务流水线")
async def execute_pipeline(request: PipelineRequest):
    """
    执行统一任务流水线

    优先使用本地工具，本地不可用时云端 fallback
    """
    # 输入验证
    is_valid, error_msg = input_validator.validate_message(request.message)
    if not is_valid:
        raise HTTPException(status_code=400, detail=error_msg)

    # 速率限制
    is_allowed, rate_msg = rate_limiter.check("pipeline", max_requests=30, window_seconds=60)
    if not is_allowed:
        raise HTTPException(status_code=429, detail=rate_msg)

    try:
        # 优先使用 LocalAgentRuntime
        runtime = get_local_agent_runtime()
        result = runtime.execute(request.message, request.context)

        # 如果本地执行失败，尝试云端 fallback
        if not result.get("ok"):
            logger.info("Pipeline: Local execution failed, trying cloud fallback")
            pipeline = get_delivery_pipeline()
            legacy_result = pipeline.execute(request.message, request.context)

            # 转换旧结果为统一结构
            cloud_result = _convert_legacy_result(legacy_result)

            if cloud_result.get("ok"):
                return cloud_result

        return result
    except Exception as e:
        logger.error(f"Pipeline execution error: {e}")
        raise HTTPException(status_code=500, detail=f"任务执行失败: {str(e)}")


@router.get("/health", summary="流水线健康检查")
async def pipeline_health():
    """检查流水线状态"""
    runtime = get_local_agent_runtime()
    return {
        "status": "ok",
        "mode": "local_first",
        "adapters_loaded": len(runtime._adapters),
        "available_adapters": [a.TOOL_NAME for a in runtime._adapters.values() if a.health_check().get("available")]
    }
