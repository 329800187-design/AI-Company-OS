"""Collaboration Router — 多智能体协作计划 API"""
from datetime import datetime, timezone
from typing import Dict, List, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from backend.services.collaboration_planner import build_collaboration_plan
from backend.services.collaboration_executor import execute_collaboration_plan
from backend.services.collaboration_run_store import (
    load_plan_snapshot,
    save_plan_snapshot,
    update_step_status,
    load_plan_records,
    reset_step_for_retry,
    load_run_timeline,
    collect_plan_artifacts,
)

router = APIRouter(prefix="/collaboration", tags=["Collaboration / 多智能体协作计划"])


class StepDef(BaseModel):
    """步骤定义"""
    name: str = Field(..., description="步骤名称")
    task_type: str = Field(..., description="任务类型")
    required_capability: str = Field(..., description="所需能力标签")
    input_from: Optional[str] = Field(default=None, description="上游步骤 id")
    depends_on: Optional[List[str]] = Field(default=None, description="依赖步骤 id 列表")
    expected_output: Optional[str] = Field(default=None, description="预期产出描述")
    review_required: Optional[bool] = Field(default=None, description="是否需要人工审核")


class CollaborationPlanRequest(BaseModel):
    """构建协同计划请求"""
    goal: str = Field(..., min_length=2, max_length=500, description="目标描述")
    steps: List[StepDef] = Field(..., min_length=1, description="步骤定义列表")


class CollaborationRunRequest(BaseModel):
    """构建并执行协同计划请求"""
    goal: str = Field(..., min_length=2, max_length=500, description="目标描述")
    steps: List[StepDef] = Field(..., min_length=1, description="步骤定义列表")


@router.post("/plan", summary="构建协同计划",
             description="根据目标和步骤定义，通过 manifest capabilities 匹配 agent，返回计划")
def api_collaboration_plan(request: CollaborationPlanRequest):
    steps_dicts = [s.model_dump(exclude_none=True) for s in request.steps]
    plan = build_collaboration_plan(request.goal, steps_dicts)
    return plan.model_dump()


@router.post("/run", summary="执行协同计划",
             description="构建协同计划并顺序执行各步骤")
def api_collaboration_run(request: CollaborationRunRequest):
    steps_dicts = [s.model_dump(exclude_none=True) for s in request.steps]
    plan = build_collaboration_plan(request.goal, steps_dicts)
    save_plan_snapshot(plan)
    plan = execute_collaboration_plan(plan)
    return plan.model_dump()


# ── Human Review: approve / reject / resume / get ──


class ReviewDecisionRequest(BaseModel):
    """人工审核决策"""
    step_id: str = Field(..., description="待审核步骤 id")
    comment: Optional[str] = Field(default=None, description="审核意见")


@router.get("/runs/{plan_id}", summary="获取计划详情",
            description="返回计划快照 + 各步骤执行记录")
def api_get_plan(plan_id: str):
    plan = load_plan_snapshot(plan_id)
    if plan is None:
        raise HTTPException(status_code=404, detail=f"Plan '{plan_id}' not found")
    records = load_plan_records(plan_id)
    return {
        "plan": plan.model_dump(),
        "step_records": records,
        "timeline": load_run_timeline(plan_id),
        "artifacts": collect_plan_artifacts(plan),
    }


@router.post("/runs/{plan_id}/approve", summary="批准继续",
             description="批准 waiting_human 步骤，标记 succeeded 并继续执行后续步骤")
def api_approve_step(plan_id: str, request: ReviewDecisionRequest):
    plan = load_plan_snapshot(plan_id)
    if plan is None:
        raise HTTPException(status_code=404, detail=f"Plan '{plan_id}' not found")

    # 找到目标步骤
    target_step = None
    for s in plan.steps:
        if s.id == request.step_id:
            target_step = s
            break
    if target_step is None:
        raise HTTPException(status_code=404, detail=f"Step '{request.step_id}' not found in plan")

    if target_step.status != "waiting_human":
        raise HTTPException(
            status_code=400,
            detail=f"Step '{request.step_id}' is '{target_step.status}', not 'waiting_human'"
        )

    # 记录审批决策
    decision = {
        "action": "approve",
        "comment": request.comment,
        "decided_at": datetime.now(timezone.utc).isoformat(),
    }

    # 区分 sandbox_required 和普通 confirm/review_required
    is_sandbox_required = False
    if (
        target_step.result
        and target_step.result.output
        and isinstance(target_step.result.output, dict)
    ):
        risk_decision = target_step.result.output.get("_risk_decision")
        if isinstance(risk_decision, dict):
            is_sandbox_required = risk_decision.get("recommended_action") == "sandbox_required"

    if is_sandbox_required:
        # sandbox_required: approve 后设为 pending，让 executor 走 run_in_sandbox 路径
        updated_plan = update_step_status(plan_id, request.step_id, "pending", review_decision=decision)
    else:
        # 普通 confirm/review_required: approve 后设为 succeeded，继续后续步骤
        updated_plan = update_step_status(plan_id, request.step_id, "succeeded", review_decision=decision)

    if updated_plan is None:
        raise HTTPException(status_code=500, detail="Failed to update plan")

    # 继续执行后续步骤（resume 模式）
    updated_plan = execute_collaboration_plan(updated_plan, resume=True)
    return updated_plan.model_dump()


@router.post("/runs/{plan_id}/reject", summary="拒绝终止",
             description="拒绝 waiting_human 步骤，标记 failed，计划终止")
def api_reject_step(plan_id: str, request: ReviewDecisionRequest):
    plan = load_plan_snapshot(plan_id)
    if plan is None:
        raise HTTPException(status_code=404, detail=f"Plan '{plan_id}' not found")

    target_step = None
    for s in plan.steps:
        if s.id == request.step_id:
            target_step = s
            break
    if target_step is None:
        raise HTTPException(status_code=404, detail=f"Step '{request.step_id}' not found in plan")

    if target_step.status != "waiting_human":
        raise HTTPException(
            status_code=400,
            detail=f"Step '{request.step_id}' is '{target_step.status}', not 'waiting_human'"
        )

    decision = {
        "action": "reject",
        "comment": request.comment,
        "decided_at": datetime.now(timezone.utc).isoformat(),
    }

    updated_plan = update_step_status(plan_id, request.step_id, "failed", review_decision=decision)
    if updated_plan is None:
        raise HTTPException(status_code=500, detail="Failed to update plan")
    return updated_plan.model_dump()


@router.post("/runs/{plan_id}/resume", summary="恢复执行",
             description="从 waiting_human 计划的断点恢复执行（跳过已完成步骤）")
def api_resume_plan(plan_id: str):
    plan = load_plan_snapshot(plan_id)
    if plan is None:
        raise HTTPException(status_code=404, detail=f"Plan '{plan_id}' not found")

    plan = execute_collaboration_plan(plan, resume=True)
    return plan.model_dump()


class RetryStepRequest(BaseModel):
    """步骤重试请求"""
    step_id: str = Field(..., description="要重试的步骤 id")


@router.post("/runs/{plan_id}/retry-step", summary="重试失败步骤",
             description="重置 failed/skipped 步骤及其下游，然后继续执行")
def api_retry_step(plan_id: str, request: RetryStepRequest):
    plan = load_plan_snapshot(plan_id)
    if plan is None:
        raise HTTPException(status_code=404, detail=f"Plan '{plan_id}' not found")

    # 找到目标步骤
    target_step = None
    for s in plan.steps:
        if s.id == request.step_id:
            target_step = s
            break
    if target_step is None:
        raise HTTPException(status_code=404, detail=f"Step '{request.step_id}' not found in plan")

    if target_step.status not in ("failed", "skipped"):
        raise HTTPException(
            status_code=400,
            detail=f"Step '{request.step_id}' is '{target_step.status}', only 'failed' or 'skipped' steps can be retried"
        )

    # 重置步骤
    updated_plan = reset_step_for_retry(plan_id, request.step_id)
    if updated_plan is None:
        raise HTTPException(status_code=500, detail="Failed to reset step for retry")

    # 继续执行（resume 模式）
    updated_plan = execute_collaboration_plan(updated_plan, resume=True)
    return updated_plan.model_dump()
