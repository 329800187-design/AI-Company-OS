"""Execution Plan — 结构化执行计划"""
import uuid
from pydantic import BaseModel, Field
from typing import Dict, List, Optional

from .classifier import ClassificationResult


class ExecutionStep(BaseModel):
    """执行步骤"""
    id: str
    name: str
    kind: str  # "parse_spec" | "generate" | "write" | "verify" | "return" | "manual"
    entrypoint: Optional[str] = None
    expected_output: str = ""
    required: bool = True


class ExecutionPlan(BaseModel):
    """执行计划"""
    plan_id: str
    capability_id: str
    goal: str
    normalized_inputs: Dict = Field(default_factory=dict)
    steps: List[ExecutionStep] = Field(default_factory=list)
    artifact_expectation: Dict = Field(default_factory=dict)
    required_checks: List[str] = Field(default_factory=list)
    status: str = "planned"  # "planned" | "rejected" | "needs_clarification"


# ── 固定计划模板 ────────────────────────────────────────────

_COPY_PACK_STEPS = [
    ExecutionStep(
        id="step_parse_spec",
        name="解析交付规格",
        kind="parse_spec",
        entrypoint="backend.minidelivery.spec.parse_delivery_spec",
        expected_output="DeliverySpec",
        required=True,
    ),
    ExecutionStep(
        id="step_generate",
        name="生成文案包内容",
        kind="generate",
        entrypoint="backend.minidelivery.template_generator.generate_copy_pack_template",
        expected_output="markdown content",
        required=True,
    ),
    ExecutionStep(
        id="step_write",
        name="写入产物文件",
        kind="write",
        entrypoint="backend.minidelivery.artifact_writer.write_artifact",
        expected_output="artifact file path",
        required=True,
    ),
    ExecutionStep(
        id="step_verify",
        name="验收产物",
        kind="verify",
        entrypoint="backend.minidelivery.verifier.verify_artifact",
        expected_output="verification result",
        required=True,
    ),
    ExecutionStep(
        id="step_return",
        name="返回结果",
        kind="return",
        expected_output="MiniDeliveryResult",
        required=True,
    ),
]

_IMAGE_PROMPT_PACK_STEPS = [
    ExecutionStep(
        id="step_parse_spec",
        name="解析交付规格",
        kind="parse_spec",
        expected_output="DeliverySpec",
        required=True,
    ),
    ExecutionStep(
        id="step_generate",
        name="生成图片提示词包",
        kind="generate",
        entrypoint="backend.minidelivery.template_generator.generate_image_prompt_pack_template",
        expected_output="markdown content",
        required=True,
    ),
    ExecutionStep(
        id="step_write",
        name="写入产物文件",
        kind="write",
        entrypoint="backend.minidelivery.artifact_writer.write_artifact",
        expected_output="artifact file path",
        required=True,
    ),
    ExecutionStep(
        id="step_verify",
        name="验收产物",
        kind="verify",
        entrypoint="backend.minidelivery.verifier.verify_image_prompt_pack",
        expected_output="verification result",
        required=True,
    ),
    ExecutionStep(
        id="step_return",
        name="返回结果",
        kind="return",
        expected_output="MiniDeliveryResult",
        required=True,
    ),
]


_RESEARCH_BRIEF_STEPS = [
    ExecutionStep(
        id="step_parse_spec",
        name="解析交付规格",
        kind="parse_spec",
        expected_output="DeliverySpec",
        required=True,
    ),
    ExecutionStep(
        id="step_generate",
        name="生成调研简报",
        kind="generate",
        entrypoint="backend.minidelivery.template_generator.generate_research_brief_template",
        expected_output="markdown content",
        required=True,
    ),
    ExecutionStep(
        id="step_write",
        name="写入产物文件",
        kind="write",
        entrypoint="backend.minidelivery.artifact_writer.write_artifact",
        expected_output="artifact file path",
        required=True,
    ),
    ExecutionStep(
        id="step_verify",
        name="验收产物",
        kind="verify",
        entrypoint="backend.minidelivery.verifier.verify_research_brief",
        expected_output="verification result",
        required=True,
    ),
    ExecutionStep(
        id="step_return",
        name="返回结果",
        kind="return",
        expected_output="MiniDeliveryResult",
        required=True,
    ),
]


_LANDING_PAGE_COPY_STEPS = [
    ExecutionStep(
        id="step_parse_spec",
        name="解析交付规格",
        kind="parse_spec",
        expected_output="DeliverySpec",
        required=True,
    ),
    ExecutionStep(
        id="step_generate",
        name="生成落地页文案",
        kind="generate",
        entrypoint="backend.minidelivery.template_generator.generate_landing_page_copy_template",
        expected_output="markdown content",
        required=True,
    ),
    ExecutionStep(
        id="step_write",
        name="写入产物文件",
        kind="write",
        entrypoint="backend.minidelivery.artifact_writer.write_artifact",
        expected_output="artifact file path",
        required=True,
    ),
    ExecutionStep(
        id="step_verify",
        name="验收产物",
        kind="verify",
        entrypoint="backend.minidelivery.verifier.verify_landing_page_copy",
        expected_output="verification result",
        required=True,
    ),
    ExecutionStep(
        id="step_return",
        name="返回结果",
        kind="return",
        expected_output="MiniDeliveryResult",
        required=True,
    ),
]

_DATA_REPORT_STEPS = [
    ExecutionStep(
        id="step_parse_spec",
        name="解析交付规格",
        kind="parse_spec",
        expected_output="DeliverySpec",
        required=True,
    ),
    ExecutionStep(
        id="step_generate",
        name="生成数据分析报告",
        kind="generate",
        entrypoint="backend.minidelivery.template_generator.generate_data_report_template",
        expected_output="markdown content",
        required=True,
    ),
    ExecutionStep(
        id="step_write",
        name="写入产物文件",
        kind="write",
        entrypoint="backend.minidelivery.artifact_writer.write_artifact",
        expected_output="artifact file path",
        required=True,
    ),
    ExecutionStep(
        id="step_verify",
        name="验收产物",
        kind="verify",
        entrypoint="backend.minidelivery.verifier.verify_data_report",
        expected_output="verification result",
        required=True,
    ),
    ExecutionStep(
        id="step_return",
        name="返回结果",
        kind="return",
        expected_output="MiniDeliveryResult",
        required=True,
    ),
]


_CHAT_STEPS = [
    ExecutionStep(
        id="step_generate_text",
        name="生成文本回答",
        kind="generate",
        entrypoint="manual_response",
        expected_output="text answer",
        required=True,
    ),
    ExecutionStep(
        id="step_return",
        name="返回结果",
        kind="return",
        expected_output="response",
        required=True,
    ),
]


_COLLABORATION_STEPS = [
    ExecutionStep(
        id="step_classify",
        name="分类子目标",
        kind="classify",
        entrypoint="backend.services.collaboration_planner.build_collaboration_plan",
        expected_output="CollaborationPlan",
        required=True,
    ),
    ExecutionStep(
        id="step_build_plan",
        name="构建协同计划",
        kind="plan",
        entrypoint="backend.services.collaboration_planner.build_collaboration_plan",
        expected_output="CollaborationPlan",
        required=True,
    ),
    ExecutionStep(
        id="step_assign_agents",
        name="分配智能体",
        kind="assign",
        expected_output="agent assignments",
        required=True,
    ),
    ExecutionStep(
        id="step_execute",
        name="执行协同计划",
        kind="execute",
        entrypoint="backend.services.collaboration_executor.execute_collaboration_plan",
        expected_output="CollaborationPlan with results",
        required=True,
    ),
    ExecutionStep(
        id="step_return",
        name="返回结果",
        kind="return",
        expected_output="collaboration_result",
        required=True,
    ),
]


def build_execution_plan(
    goal: str,
    classification: ClassificationResult,
) -> ExecutionPlan:
    """基于分类结果构建执行计划"""
    plan_id = f"plan_{uuid.uuid4().hex[:12]}"

    if not classification.ok or classification.capability_id is None:
        return ExecutionPlan(
            plan_id=plan_id,
            capability_id=classification.capability_id or "unknown",
            goal=goal,
            normalized_inputs=classification.normalized_inputs,
            steps=[],
            status="rejected" if not classification.needs_clarification else "needs_clarification",
        )

    cap_id = classification.capability_id

    if cap_id == "copy_pack.xiaohongshu":
        return ExecutionPlan(
            plan_id=plan_id,
            capability_id=cap_id,
            goal=goal,
            normalized_inputs=classification.normalized_inputs,
            steps=list(_COPY_PACK_STEPS),
            artifact_expectation={"type": "markdown", "description": "小红书文案包"},
            required_checks=["file_exists", "contains_product", "no_placeholders", "has_cta", "has_publish_tips"],
            status="planned",
        )

    if cap_id == "copy_pack.douyin":
        return ExecutionPlan(
            plan_id=plan_id,
            capability_id=cap_id,
            goal=goal,
            normalized_inputs=classification.normalized_inputs,
            steps=list(_COPY_PACK_STEPS),
            artifact_expectation={"type": "markdown", "description": "抖音短视频文案包"},
            required_checks=["file_exists", "contains_product", "no_placeholders", "has_hook", "has_script", "has_selling_points"],
            status="planned",
        )

    if cap_id == "chat.general":
        return ExecutionPlan(
            plan_id=plan_id,
            capability_id=cap_id,
            goal=goal,
            normalized_inputs=classification.normalized_inputs,
            steps=list(_CHAT_STEPS),
            artifact_expectation={"type": "text", "description": "文本回答"},
            required_checks=[],
            status="planned",
        )

    if cap_id == "image_prompt_pack":
        return ExecutionPlan(
            plan_id=plan_id,
            capability_id=cap_id,
            goal=goal,
            normalized_inputs=classification.normalized_inputs,
            steps=list(_IMAGE_PROMPT_PACK_STEPS),
            artifact_expectation={"type": "markdown", "description": "图片提示词包"},
            required_checks=[
                "file_exists", "contains_product", "no_placeholders",
                "has_main_prompt", "has_detail_prompt", "has_scene_prompt",
                "has_negative_prompt", "has_usage_tips",
            ],
            status="planned",
        )

    if cap_id == "research_brief":
        return ExecutionPlan(
            plan_id=plan_id,
            capability_id=cap_id,
            goal=goal,
            normalized_inputs=classification.normalized_inputs,
            steps=list(_RESEARCH_BRIEF_STEPS),
            artifact_expectation={"type": "markdown", "description": "调研简报"},
            required_checks=[
                "file_exists", "contains_product", "no_placeholders",
                "has_research_goal", "has_target_users", "has_competitor_dimensions",
                "has_pain_points", "has_content_opportunities", "has_risk_warnings",
                "has_next_steps",
            ],
            status="planned",
        )

    if cap_id == "landing_page_copy":
        return ExecutionPlan(
            plan_id=plan_id,
            capability_id=cap_id,
            goal=goal,
            normalized_inputs=classification.normalized_inputs,
            steps=list(_LANDING_PAGE_COPY_STEPS),
            artifact_expectation={"type": "markdown", "description": "落地页文案"},
            required_checks=[
                "file_exists", "contains_product", "no_placeholders",
                "has_page_positioning", "has_hero_title", "has_subtitle",
                "has_selling_points", "has_target_users", "has_page_structure",
                "has_cta", "has_faq", "has_visual_suggestions",
            ],
            status="planned",
        )

    if cap_id == "data_report":
        return ExecutionPlan(
            plan_id=plan_id,
            capability_id=cap_id,
            goal=goal,
            normalized_inputs=classification.normalized_inputs,
            steps=list(_DATA_REPORT_STEPS),
            artifact_expectation={"type": "markdown", "description": "数据分析报告"},
            required_checks=[
                "file_exists", "contains_product", "no_placeholders",
                "has_analysis_goal", "has_data_scope", "has_core_metrics",
                "has_trend_observations", "has_anomaly_checks", "has_business_interpretation",
                "has_action_recommendations", "has_supplementary_data",
            ],
            status="planned",
        )

    if cap_id == "collaboration.controlled":
        return ExecutionPlan(
            plan_id=plan_id,
            capability_id=cap_id,
            goal=goal,
            normalized_inputs=classification.normalized_inputs,
            steps=list(_COLLABORATION_STEPS),
            artifact_expectation={"type": "collaboration_result", "description": "多智能体协同执行结果"},
            required_checks=["all_steps_succeeded"],
            status="planned",
        )

    # unsupported
    return ExecutionPlan(
        plan_id=plan_id,
        capability_id=cap_id,
        goal=goal,
        normalized_inputs=classification.normalized_inputs,
        steps=[],
        status="rejected",
    )
