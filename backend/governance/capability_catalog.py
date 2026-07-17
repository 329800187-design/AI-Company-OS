"""能力目录 — 定义系统明确支持的能力边界"""
from pydantic import BaseModel, Field
from typing import Dict, List, Optional


class Capability(BaseModel):
    """能力定义"""
    id: str
    name: str
    description: str
    supported: bool = True
    entrypoint: str = ""
    input_schema: Dict = Field(default_factory=dict)
    artifact_expectation: Dict = Field(default_factory=dict)
    required_checks: List[str] = Field(default_factory=list)
    risk_level: str = "low"  # "low" | "medium" | "high"


# ── 能力注册表 ──────────────────────────────────────────────

_CAPABILITIES: List[Capability] = [
    Capability(
        id="copy_pack.xiaohongshu",
        name="小红书文案包生成",
        description="生成小红书种草文案包，包含标题方案、目标人群、正文文案、话题标签、行动号召、发布建议",
        supported=True,
        entrypoint="backend.minidelivery.pipeline.run_copy_pack_pipeline",
        input_schema={"goal": "str", "platform": "xiaohongshu"},
        artifact_expectation={"type": "markdown", "description": "小红书文案包 Markdown 文件"},
        required_checks=[
            "file_exists", "contains_product", "no_placeholders",
            "has_cta", "has_publish_tips", "xhs_platform_checks",
        ],
        risk_level="low",
    ),
    Capability(
        id="copy_pack.douyin",
        name="抖音短视频文案包生成",
        description="生成抖音短视频文案包，包含开头钩子、视频脚本/分镜、卖点介绍、使用场景、互动引导、行动号召、发布建议",
        supported=True,
        entrypoint="backend.minidelivery.pipeline.run_copy_pack_pipeline",
        input_schema={"goal": "str", "platform": "douyin"},
        artifact_expectation={"type": "markdown", "description": "抖音短视频文案包 Markdown 文件"},
        required_checks=[
            "file_exists", "contains_product", "no_placeholders",
            "has_hook", "has_script", "has_selling_points", "has_engagement",
        ],
        risk_level="low",
    ),
    Capability(
        id="chat.general",
        name="通用对话",
        description="通用文本问答，尚未接入 Governance 执行路径",
        supported=False,
        entrypoint="manual_response",
        input_schema={"goal": "str"},
        artifact_expectation={"type": "text", "description": "文本回答"},
        required_checks=[],
        risk_level="low",
    ),
    Capability(
        id="unsupported.complex_agent_workflow",
        name="不支持的复杂任务",
        description="需要无约束多智能体编排、浏览器自动化、未知工具或模糊业务构建的任务，当前系统不支持",
        supported=False,
        entrypoint="",
        input_schema={},
        artifact_expectation={},
        required_checks=[],
        risk_level="high",
    ),
    # ── 图片提示词包 ────────────────────────────────────────
    Capability(
        id="image_prompt_pack",
        name="图片提示词包生成",
        description="生成产品图片提示词包，包含主图、细节图、场景图提示词，风格关键词、负面提示词、尺寸构图建议、使用建议",
        supported=True,
        entrypoint="backend.minidelivery.pipeline.run_image_prompt_pack_pipeline",
        input_schema={"goal": "str"},
        artifact_expectation={"type": "markdown", "description": "图片提示词包 Markdown 文件"},
        required_checks=[
            "file_exists", "contains_product", "no_placeholders",
            "has_main_prompt", "has_detail_prompt", "has_scene_prompt",
            "has_negative_prompt", "has_usage_tips",
        ],
        risk_level="low",
    ),
    # ── 调研简报 ────────────────────────────────────────────
    Capability(
        id="research_brief",
        name="调研简报生成",
        description="生成调研简报 Markdown，包含调研目标、目标用户、竞品维度、用户痛点假设、内容机会、风险提醒、下一步建议",
        supported=True,
        entrypoint="backend.minidelivery.pipeline.run_research_brief_pipeline",
        input_schema={"goal": "str"},
        artifact_expectation={"type": "markdown", "description": "调研简报 Markdown 文件"},
        required_checks=[
            "file_exists", "contains_product", "no_placeholders",
            "has_research_goal", "has_target_users", "has_competitor_dimensions",
            "has_pain_points", "has_content_opportunities", "has_risk_warnings",
            "has_next_steps",
        ],
        risk_level="low",
    ),
    # ── 落地页文案 ────────────────────────────────────────────
    Capability(
        id="landing_page_copy",
        name="落地页文案生成",
        description="生成落地页文案 Markdown，包含页面定位、首屏标题、副标题、核心卖点、目标用户、页面结构、CTA 文案、FAQ、视觉建议",
        supported=True,
        entrypoint="backend.minidelivery.pipeline.run_landing_page_copy_pipeline",
        input_schema={"goal": "str"},
        artifact_expectation={"type": "markdown", "description": "落地页文案 Markdown 文件"},
        required_checks=[
            "file_exists", "contains_product", "no_placeholders",
            "has_page_positioning", "has_hero_title", "has_subtitle",
            "has_selling_points", "has_target_users", "has_page_structure",
            "has_cta", "has_faq", "has_visual_suggestions",
        ],
        risk_level="low",
    ),
    # ── 数据分析报告 ────────────────────────────────────────────
    Capability(
        id="data_report",
        name="数据分析报告生成",
        description="生成数据分析报告框架 Markdown，包含分析目标、数据范围假设、核心指标、趋势观察、异常点检查、业务解释、行动建议、后续需要补充的数据",
        supported=True,
        entrypoint="backend.minidelivery.pipeline.run_data_report_pipeline",
        input_schema={"goal": "str"},
        artifact_expectation={"type": "markdown", "description": "数据分析报告 Markdown 文件"},
        required_checks=[
            "file_exists", "contains_product", "no_placeholders",
            "has_analysis_goal", "has_data_scope", "has_core_metrics",
            "has_trend_observations", "has_anomaly_checks", "has_business_interpretation",
            "has_action_recommendations", "has_supplementary_data",
        ],
        risk_level="low",
    ),
    # ── 受控多智能体协同 ────────────────────────────────────────
    Capability(
        id="collaboration.controlled",
        name="受控多智能体协同",
        description="多步骤协同任务，组合文案、图片、调研等已受控能力，通过 manifest agents 顺序执行",
        supported=True,
        entrypoint="backend.services.collaboration_executor.execute_collaboration_plan",
        input_schema={"goal": "str"},
        artifact_expectation={"type": "collaboration_result", "description": "多智能体协同执行结果"},
        required_checks=["all_steps_succeeded"],
        risk_level="medium",
    ),
    # ── 已识别但未支持的交付物类型 ────────────────────────────
    Capability(
        id="unsupported.artifact_type",
        name="未支持的交付物类型",
        description="已识别用户意图对应的交付物类型，但当前尚未实现该类型的闭环能力",
        supported=False,
        entrypoint="",
        input_schema={},
        artifact_expectation={},
        required_checks=[],
        risk_level="medium",
    ),
]


# ── 查询函数 ────────────────────────────────────────────────

def list_capabilities() -> List[Capability]:
    """返回所有已注册能力"""
    return list(_CAPABILITIES)


def get_capability(capability_id: str) -> Optional[Capability]:
    """按 ID 获取能力"""
    for cap in _CAPABILITIES:
        if cap.id == capability_id:
            return cap
    return None


def get_supported_capabilities() -> List[Capability]:
    """返回所有 supported=True 的能力"""
    return [cap for cap in _CAPABILITIES if cap.supported]
