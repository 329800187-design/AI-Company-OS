"""
Pipeline Router — 统一任务执行接口

执行优先级：
1. 本地工具可用 -> 本地执行
2. 本地工具不可用 + 允许 fallback -> 云端执行
3. 都不可用 -> ok=false

严格规则：
- image/data/research/website/code 不允许 fallback 到旧 DeliveryPipeline
- 旧 DeliveryPipeline 只能临时保留给 marketing/chat
- 所有结果必须经过 ResultVerifier
"""
from typing import List, Optional
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from backend.services.local_agent_runtime import get_local_agent_runtime
from backend.services.result_verifier import get_result_verifier
from backend.security import input_validator, rate_limiter
from backend.logger import get_logger

logger = get_logger()
router = APIRouter(prefix="/pipeline", tags=["Pipeline / 任务流水线"])

# 不允许 fallback 的强类型任务
STRICT_TASK_TYPES = {"image", "data", "research", "website", "code"}


class PipelineRequest(BaseModel):
    """任务请求"""
    message: str = Field(..., description="用户输入")
    context: Optional[dict] = Field(default_factory=dict, description="上下文信息")


@router.post("/execute", summary="执行任务流水线")
async def execute_pipeline(request: PipelineRequest):
    """
    执行统一任务流水线

    优先使用本地工具，严格任务不允许 fallback
    """
    # Governance Guard: 拦截不支持的目标
    from backend.governance.guard import guard_payload, governance_block_response
    blocked, classification = guard_payload(request.model_dump())
    if blocked:
        return governance_block_response(classification)

    # 输入验证
    is_valid, error_msg = input_validator.validate_message(request.message)
    if not is_valid:
        raise HTTPException(status_code=400, detail=error_msg)

    # 速率限制
    is_allowed, rate_msg = rate_limiter.check("pipeline", max_requests=30, window_seconds=60)
    if not is_allowed:
        raise HTTPException(status_code=429, detail=rate_msg)

    try:
        # 使用 LocalAgentRuntime 执行
        runtime = get_local_agent_runtime()
        result = runtime.execute(request.message, request.context)

        # 如果本地执行失败，检查是否允许 fallback
        if not result.get("ok"):
            task_type = result.get("task_type", "unknown")

            # 强类型任务不允许 fallback
            if task_type in STRICT_TASK_TYPES:
                logger.info(f"Pipeline: {task_type} task failed, no fallback allowed")
                return result

            # marketing/chat 可以尝试旧 DeliveryPipeline
            logger.info(f"Pipeline: {task_type} task failed, trying legacy pipeline")
            from backend.services.delivery_pipeline import get_delivery_pipeline
            legacy_pipeline = get_delivery_pipeline()
            legacy_result = legacy_pipeline.execute(request.message, request.context)

            # 转换旧结果
            if legacy_result.get("ok"):
                verifier = get_result_verifier()
                verification = verifier.verify(task_type, legacy_result)

                legacy_result["verification_result"] = verification
                legacy_result["qa"] = verification
                legacy_result["mode"] = "legacy"

                # 验证失败则返回失败
                if not verification.get("passed"):
                    legacy_result["ok"] = False
                    legacy_result["error"] = "结果验证失败"
                    legacy_result["warnings"] = verification.get("issues", [])

                return legacy_result

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
