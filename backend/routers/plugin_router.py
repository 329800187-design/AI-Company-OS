"""External Plugin Router"""
from fastapi import APIRouter, HTTPException
from core.plugin_loader import get_plugin_loader

router = APIRouter(prefix="/plugins", tags=["Plugins / 插件"])

@router.get("", summary="List external plugins")
def list_plugins():
    return {"plugins": get_plugin_loader().list_all()}

@router.post("/{plugin_id}/run", summary="Run external plugin")
def run_plugin(plugin_id: str, task: dict):
    # Governance Guard: 从 task payload 提取 goal 并检查
    from backend.governance.scope_classifier import guard_payload, governance_block_response, extract_goal_from_payload
    from backend.governance.classifier import ClassificationResult

    blocked, classification = guard_payload(task)
    if blocked:
        return governance_block_response(classification)

    # 插件是任意代码执行入口，不允许无目标执行
    if not task or not extract_goal_from_payload(task):
        no_goal_class = ClassificationResult(
            ok=False,
            confidence=0.0,
            reason="插件执行必须提供明确的用户意图（goal/prompt/message/command）",
            needs_clarification=True,
            clarification_questions=["请提供 goal 或 prompt 描述你希望插件执行的任务"],
        )
        return governance_block_response(no_goal_class)

    result = get_plugin_loader().run(plugin_id, task)
    if not result.get("ok"): raise HTTPException(400, detail=result.get("error"))
    return result
