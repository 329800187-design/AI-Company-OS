"""数据模型 — minidelivery 子系统"""
from pydantic import BaseModel, Field
from typing import Dict, List, Optional


class XHSCopyRequest(BaseModel):
    """小红书文案包请求（旧接口兼容）"""
    goal: str = Field(..., min_length=2, max_length=500, description="业务目标描述")


class CopyPackRequest(BaseModel):
    """通用文案包请求（新接口）"""
    goal: str = Field(..., min_length=2, max_length=500, description="业务目标描述")
    platform: Optional[str] = Field(None, description="平台: xiaohongshu | douyin")
    artifact_type: Optional[str] = Field(None, description="产物类型")


class SaveFromAgentRequest(BaseModel):
    """从 Agent 结果保存到交付中心"""
    goal: str = Field(..., min_length=1, max_length=2000, description="业务目标描述")
    agent_id: str = Field(..., min_length=1, max_length=100, description="Agent 标识，如 marketing / image / data / research / website")
    agent_result: Dict = Field(..., description="完整的 AgentRunResult")
    artifact_type: Optional[str] = Field(None, description="产物类型覆盖")
    title: Optional[str] = Field(None, max_length=200, description="交付物标题")
    source_page: Optional[str] = Field(None, max_length=100, description="来源页面，如 marketing / image")


class VerificationChecks(BaseModel):
    """验收检查项"""
    file_exists: bool = False
    file_size_ok: bool = False
    has_titles: bool = False
    has_target_audience: bool = False
    has_body_text: bool = False
    has_hashtags: bool = False
    has_cta: bool = False
    has_publish_tips: bool = False
    contains_goal_keyword: bool = False
    no_placeholders: bool = False
    title_count_ok: bool = False
    hashtag_count_ok: bool = False
    body_length_ok: bool = False
    # douyin 专项检查
    has_hook: bool = False
    has_script: bool = False
    has_selling_points: bool = False
    has_use_scenarios: bool = False
    has_engagement: bool = False
    # image_prompt_pack 专项检查
    has_main_prompt: bool = False
    has_detail_prompt: bool = False
    has_scene_prompt: bool = False
    has_negative_prompt: bool = False
    has_usage_tips: bool = False
    # research_brief 专项检查
    has_research_goal: bool = False
    has_target_users: bool = False
    has_competitor_dimensions: bool = False
    has_pain_points: bool = False
    has_content_opportunities: bool = False
    has_risk_warnings: bool = False
    has_next_steps: bool = False
    # landing_page_copy 专项检查
    has_page_positioning: bool = False
    has_hero_title: bool = False
    has_subtitle: bool = False
    has_selling_points: bool = False
    has_page_structure: bool = False
    has_cta: bool = False
    has_faq: bool = False
    has_visual_suggestions: bool = False
    # data_report 专项检查
    has_analysis_goal: bool = False
    has_data_scope: bool = False
    has_core_metrics: bool = False
    has_trend_observations: bool = False
    has_anomaly_checks: bool = False
    has_business_interpretation: bool = False
    has_action_recommendations: bool = False
    has_supplementary_data: bool = False


class CompareTasksRequest(BaseModel):
    """任务对比请求"""
    task_ids: List[str] = Field(..., description="恰好 2 个 task_id 进行对比")


class MiniDeliveryResult(BaseModel):
    """闭环产出结构"""
    ok: bool
    task_id: str
    mode: str  # "api" | "template_fallback"
    artifact_path: str
    json_path: str
    checks: VerificationChecks
    failed_checks: List[str] = Field(default_factory=list)
    summary: str
    # API 失败回退诊断字段
    api_failed_checks: Optional[List[str]] = Field(default=None)
    api_rejected_reason: Optional[str] = Field(default=None)
    original_mode_attempted: Optional[str] = Field(default=None)
    # 规格信息
    spec: Optional[Dict] = Field(default=None)
