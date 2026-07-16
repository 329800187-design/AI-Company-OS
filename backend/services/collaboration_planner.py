"""
Collaboration Planner — 确定性协同计划构建

通过 capability_router 动态匹配 agent 到步骤，不调用 LLM。
"""
import logging
from typing import Dict, List

from backend.schemas.collaboration_plan import CollaborationPlan, CollaborationStep
from backend.services.capability_router import route_capability

logger = logging.getLogger(__name__)


def build_collaboration_plan(
    goal: str,
    steps: List[Dict[str, str]],
) -> CollaborationPlan:
    """
    构建协同计划 — 纯确定性逻辑，通过 capability_router 路由。

    Args:
        goal: 目标描述
        steps: 步骤定义列表，每项包含:
            - name: 步骤名
            - task_type: 任务类型
            - required_capability: 所需能力标签
            - input_from (可选): 上游步骤 id

    Returns:
        CollaborationPlan — 各 step 已分配 agent 或标记 unassigned
    """
    plan_steps: List[CollaborationStep] = []
    for i, step_def in enumerate(steps):
        step_id = f"step_{i + 1}"
        required_cap = step_def.get("required_capability", "")
        task_type = step_def.get("task_type", "")

        result = route_capability(
            required_capability=required_cap,
            task_type=task_type,
        )

        # input_from -> depends_on 兼容：如果 depends_on 为空但 input_from 有值，自动加入
        depends_on = step_def.get("depends_on", [])
        input_from = step_def.get("input_from")
        if not depends_on and input_from:
            depends_on = [input_from]

        plan_steps.append(CollaborationStep(
            id=step_id,
            name=step_def.get("name", f"Step {i + 1}"),
            task_type=task_type,
            required_capability=required_cap,
            input_from=input_from,
            status="assigned" if result.assigned_agent_id else "unassigned",
            assigned_agent_id=result.assigned_agent_id,
            routing_reason=result.reason,
            candidate_agent_ids=result.candidates,
            matched_capability=result.matched_capability,
            depends_on=depends_on,
            expected_output=step_def.get("expected_output"),
            review_required=step_def.get("review_required", False),
        ))

    plan = CollaborationPlan(goal=goal, steps=plan_steps)
    assigned_count = sum(1 for s in plan_steps if s.status == "assigned")
    logger.info(
        f"CollaborationPlanner: plan {plan.plan_id} created with {len(plan_steps)} steps, "
        f"{assigned_count}/{len(plan_steps)} assigned"
    )
    return plan
