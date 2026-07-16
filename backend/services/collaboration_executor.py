"""
Collaboration Executor — 顺序执行协同计划

按步骤调用 execute_agent()，支持:
  - depends_on 依赖检查
  - Agent Risk Gate（block / requires_confirmation / sandbox_required）
  - review_required 审核（waiting_human）
  - resume: 跳过已完成步骤，从断点继续
  - approve / reject 后继续执行
  - sandbox_required: approve 后走 run_in_sandbox() 而非 execute_agent()
"""
import logging
from typing import Dict

from backend.schemas.collaboration_plan import CollaborationPlan
from backend.schemas.agent_protocol import AgentTask, AgentRunResult
from backend.services.agent_executor import execute_agent
from backend.services.agent_risk_gate import evaluate_agent_risk
from backend.services.sandbox_adapter import run_in_sandbox
from backend.services.collaboration_run_store import (
    save_step_record,
    save_plan_snapshot,
    append_run_event,
)

logger = logging.getLogger(__name__)


def execute_collaboration_plan(
    plan: CollaborationPlan,
    *,
    resume: bool = False,
) -> CollaborationPlan:
    """
    顺序执行协同计划。

    Args:
        plan: 已构建的 CollaborationPlan（步骤已分配 agent）
        resume: 是否为恢复执行（跳过 succeeded 步骤）

    Returns:
        更新后的 CollaborationPlan（status 和各 step.result 已填充）
    """
    plan.status = "running"

    # 构建 step_id → step 索引，用于 input_from 链式查找
    step_index: Dict[str, int] = {s.id: i for i, s in enumerate(plan.steps)}

    for step in plan.steps:
        # ── Resume 模式：跳过已完成的步骤 ──
        if resume and step.status == "succeeded":
            continue

        # 未分配的步骤直接跳过（标记 skipped）
        if step.status == "unassigned":
            logger.warning(
                f"CollaborationExecutor: step '{step.id}' unassigned "
                f"(capability '{step.required_capability}' not found), skipping"
            )
            step.status = "skipped"
            _save_step_record(plan, step, "skipped", context={})
            continue

        # 未就绪的步骤（非 pending/assigned）跳过
        if step.status not in ("pending", "assigned"):
            continue

        # depends_on 检查：依赖步骤必须 succeeded 否则跳过
        if step.depends_on:
            deps_met = True
            for dep_id in step.depends_on:
                if dep_id in step_index:
                    dep_step = plan.steps[step_index[dep_id]]
                    if dep_step.status != "succeeded":
                        deps_met = False
                        break
                else:
                    deps_met = False
                    break
            if not deps_met:
                logger.warning(
                    f"CollaborationExecutor: step '{step.id}' dependencies not met "
                    f"(depends_on={step.depends_on}), skipping"
                )
                step.status = "skipped"
                _save_step_record(plan, step, "skipped", context={})
                continue

        # review_required 检查：进入 waiting_human 状态
        # （如果已 approved，调用方会先将 step.status 改为 succeeded 再 resume）
        if step.review_required and step.status != "succeeded":
            step.status = "waiting_human"
            plan.status = "waiting_human"
            logger.info(f"CollaborationExecutor: step '{step.id}' waiting for human review")
            _save_step_record(plan, step, "waiting_human", context={})
            save_plan_snapshot(plan)
            return plan

        # ── Agent Risk Gate ──
        # 如果 step 已有 risk_decision（resume 后 approve 继续），跳过重新评估
        existing_risk = _get_risk_decision(step)
        if existing_risk is None:
            agent_obj = _resolve_agent_for_risk_gate(step.assigned_agent_id)
            if agent_obj is not None:
                risk_decision = evaluate_agent_risk(agent_obj)
                append_run_event(plan.plan_id, "risk_gate_evaluated", {
                    "step_id": step.id,
                    "agent_id": step.assigned_agent_id,
                    "risk_level": risk_decision.risk_level,
                    "allowed": risk_decision.allowed,
                    "requires_confirmation": risk_decision.requires_confirmation,
                    "recommended_action": risk_decision.recommended_action,
                    "reasons": risk_decision.reasons,
                })

                if not risk_decision.allowed:
                    # block → step failed
                    step.status = "failed"
                    plan.status = "failed"
                    error_msg = f"Risk gate blocked: {'; '.join(risk_decision.reasons)}"
                    step.result = AgentRunResult(
                        ok=False, agent_id=step.assigned_agent_id or "",
                        error=error_msg,
                        output={"_risk_decision": risk_decision.to_dict()},
                    )
                    logger.warning(f"CollaborationExecutor: step '{step.id}' blocked by risk gate")
                    _save_step_record(plan, step, "failed", context={}, error=error_msg)
                    append_run_event(plan.plan_id, "risk_gate_blocked", {
                        "step_id": step.id,
                        "agent_id": step.assigned_agent_id,
                        "reasons": risk_decision.reasons,
                    })
                    _mark_remaining_unmet_dependencies(plan, step_index)
                    save_plan_snapshot(plan)
                    return plan

                if risk_decision.requires_confirmation:
                    # requires_confirmation / sandbox_required → waiting_human
                    step.status = "waiting_human"
                    plan.status = "waiting_human"
                    step.result = AgentRunResult(
                        ok=True, agent_id=step.assigned_agent_id or "",
                        output={"_risk_decision": risk_decision.to_dict()},
                    )
                    event_type = (
                        "sandbox_required"
                        if risk_decision.recommended_action == "sandbox_required"
                        else "risk_gate_waiting_confirmation"
                    )
                    logger.info(
                        f"CollaborationExecutor: step '{step.id}' waiting for "
                        f"risk confirmation (action={risk_decision.recommended_action})"
                    )
                    _save_step_record(plan, step, "waiting_human", context={})
                    append_run_event(plan.plan_id, event_type, {
                        "step_id": step.id,
                        "agent_id": step.assigned_agent_id,
                        "risk_level": risk_decision.risk_level,
                        "recommended_action": risk_decision.recommended_action,
                        "reasons": risk_decision.reasons,
                    })
                    save_plan_snapshot(plan)
                    return plan

        step.status = "running"

        # 构建 task context
        context: Dict = {}
        if step.depends_on:
            for dep_id in step.depends_on:
                if dep_id in step_index:
                    prev_step = plan.steps[step_index[dep_id]]
                    if prev_step.result and prev_step.result.output:
                        context.setdefault("previous_outputs", {})
                        context["previous_outputs"][dep_id] = prev_step.result.output
        # 兼容旧的 input_from
        if step.input_from and step.input_from in step_index:
            prev_step = plan.steps[step_index[step.input_from]]
            if prev_step.result and prev_step.result.output:
                context["previous_output"] = prev_step.result.output

        task = AgentTask(
            task_id=f"{plan.plan_id}_{step.id}",
            goal=plan.goal,
            task_type=step.task_type,
            context=context,
        )

        # 执行
        # sandbox_required: approve 后走 run_in_sandbox() 而非 execute_agent()
        existing_risk = _get_risk_decision(step)
        is_sandbox_required = (
            existing_risk is not None
            and existing_risk.get("recommended_action") == "sandbox_required"
        )

        if is_sandbox_required:
            logger.info(f"CollaborationExecutor: executing {step.id} in sandbox (agent='{step.assigned_agent_id}')")
            sandbox_result = run_in_sandbox(
                agent_id=step.assigned_agent_id or "",
                task=task,
                risk_decision=existing_risk,
            )
            # 写入 sandbox audit events
            for evt in sandbox_result.audit_events:
                append_run_event(plan.plan_id, evt["event"], {
                    "step_id": step.id,
                    "agent_id": step.assigned_agent_id,
                    **{k: v for k, v in evt.items() if k != "event"},
                })
            # v0: sandbox 未实现，step 直接 failed
            # 保留已有的 _risk_decision 和 _review_decision
            prev_output = {}
            if step.result and isinstance(step.result.output, dict):
                prev_output = dict(step.result.output)
            sandbox_output = {"_sandbox_result": sandbox_result.to_dict()}
            for key in ("_risk_decision", "_review_decision"):
                if key in prev_output:
                    sandbox_output[key] = prev_output[key]
            result = AgentRunResult(
                ok=False, agent_id=step.assigned_agent_id or "",
                error=sandbox_result.error,
                output=sandbox_output,
            )
            step.result = result
            step.status = "failed"
            plan.status = "failed"
            logger.warning(f"CollaborationExecutor: {step.id} sandbox not implemented — {sandbox_result.error}")
            _save_step_record(plan, step, "failed", context=context, error=sandbox_result.error)
            _mark_remaining_unmet_dependencies(plan, step_index)
            save_plan_snapshot(plan)
            return plan
        else:
            logger.info(f"CollaborationExecutor: executing {step.id} with agent '{step.assigned_agent_id}'")
            result = execute_agent(step.assigned_agent_id, task)
            step.result = result

        if result.ok:
            step.status = "succeeded"
            logger.info(f"CollaborationExecutor: {step.id} succeeded")
            _save_step_record(plan, step, "succeeded", context=context, result=output_to_dict(result))
        else:
            step.status = "failed"
            plan.status = "failed"
            logger.warning(f"CollaborationExecutor: {step.id} failed — {result.error}")
            _save_step_record(plan, step, "failed", context=context, error=result.error)
            _mark_remaining_unmet_dependencies(plan, step_index)
            save_plan_snapshot(plan)
            return plan

    # 后处理：标记未执行的依赖步骤为 skipped
    _mark_remaining_unmet_dependencies(plan, step_index)

    # 确定最终状态
    statuses = [s.status for s in plan.steps]
    if all(s == "skipped" for s in statuses):
        plan.status = "failed"
    elif any(s == "succeeded" for s in statuses):
        plan.status = "succeeded"
    else:
        plan.status = "failed"

    logger.info(f"CollaborationExecutor: plan {plan.plan_id} finished as '{plan.status}' ({len(plan.steps)} steps)")
    save_plan_snapshot(plan)

    return plan


def _save_step_record(plan, step, status, context=None, result=None, error=None):
    """保存步骤执行记录"""
    record = {
        "assigned_agent_id": step.assigned_agent_id,
        "status": status,
        "required_capability": step.required_capability,
        "task_type": step.task_type,
    }
    if context:
        record["context"] = context
    if result:
        record["result"] = result
    if error:
        record["error"] = error
    save_step_record(plan.plan_id, step.id, record)


def output_to_dict(result) -> dict:
    """将 AgentRunResult 转为可序列化的 dict"""
    return {
        "ok": result.ok,
        "agent_id": result.agent_id,
        "output": result.output,
        "artifacts": result.artifacts,
        "error": result.error,
    }


def _mark_remaining_unmet_dependencies(plan: CollaborationPlan, step_index: Dict[str, int]) -> None:
    """
    后处理：标记仍未执行的、依赖未满足的步骤为 skipped。
    用于处理前置步骤失败导致后续依赖步骤未被执行的情况。
    """
    for step in plan.steps:
        if step.status not in ("pending", "assigned"):
            continue
        if not step.depends_on:
            continue
        deps_met = True
        for dep_id in step.depends_on:
            if dep_id in step_index:
                dep_step = plan.steps[step_index[dep_id]]
                if dep_step.status != "succeeded":
                    deps_met = False
                    break
            else:
                deps_met = False
                break
        if not deps_met:
            logger.warning(
                f"CollaborationExecutor: step '{step.id}' dependencies not met "
                f"(depends_on={step.depends_on}), marking skipped"
            )
            step.status = "skipped"
            _save_step_record(plan, step, "skipped", context={})


def _get_risk_decision(step) -> dict | None:
    """从 step.result.output._risk_decision 中提取已有的风险决策"""
    if step.result and step.result.output and isinstance(step.result.output, dict):
        rd = step.result.output.get("_risk_decision")
        if rd and isinstance(rd, dict):
            return rd
    return None


def _resolve_agent_for_risk_gate(agent_id: str | None):
    """通过 agent_id 获取 AgentCapability 对象供 risk gate 评估。
    优先从 agent_discovery 获取，找不到则从 manifest 构造轻量评估对象。
    """
    if not agent_id:
        return None
    try:
        from backend.services.agent_discovery import get_agent_discovery
        discovery = get_agent_discovery()
        agent = discovery.get_agent(agent_id)
        if agent is not None:
            return agent
    except Exception as e:
        logger.debug(f"RiskGate: could not resolve agent '{agent_id}' from discovery: {e}")

    # Fallback: 从 manifest 构造评估对象
    try:
        from backend.schemas.agent_manifest import scan_manifests
        from backend.services.agent_discovery import AgentCapability
        from pathlib import Path
        manifests = scan_manifests(Path("agents").parent)
        manifest = manifests.get(agent_id)
        if manifest is not None:
            return AgentCapability(
                id=manifest.id,
                name=manifest.name,
                kind="local",
                enabled=manifest.enabled,
                capabilities=manifest.capabilities,
                task_types=manifest.task_types,
                risk_level=manifest.risk_level,
                requires_confirmation=False,
                source="manifest",
            )
    except Exception as e:
        logger.debug(f"RiskGate: could not resolve agent '{agent_id}' from manifest: {e}")

    return None
