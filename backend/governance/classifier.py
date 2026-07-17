"""Goal Classifier — 确定性规则分类器"""
import re
from pydantic import BaseModel, Field
from typing import Dict, List, Optional


class ClassificationResult(BaseModel):
    """分类结果"""
    ok: bool
    capability_id: Optional[str] = None
    confidence: float = 0.0
    reason: str = ""
    needs_clarification: bool = False
    clarification_questions: List[str] = Field(default_factory=list)
    normalized_inputs: Dict = Field(default_factory=dict)


# ── 模糊/拒绝关键词 ────────────────────────────────────────

_VAGUE_PATTERNS = [
    r"帮我搭建.*系统",
    r"赚钱.*系统",
    r"全自动.*运营",
    r"搭建.*公司",
    r"帮我做.*系统",
    r"构建.*平台",
    r"开发.*APP",
    r"开发.*软件",
    r"自动赚钱",
    r"躺赚",
    r"被动收入.*自动",
    r"月入过万.*自动",
    r"自动选品.*自动推广",
    r"搭建.*完整公司",
    r"全自动.*系统",
    r"做一个.*赚钱",
]

# ── 多能力协同识别 ────────────────────────────────────────

_COLLABORATION_CAPABILITY_KEYWORDS = {
    "copywriting": ["文案", "推广文案", "种草文案", "标题"],
    "image": ["图片", "配图", "生图", "产品图"],
    "research": ["调研", "调研简报", "竞品分析", "市场调研"],
    "data": ["数据", "数据分析", "数据报告"],
}

_COLLABORATION_CONJUNCTIONS = ["+", "和", "与", "以及", "带图的", "配上图", "加图"]

# ── 平台白名单 ──────────────────────────────────────────────

SUPPORTED_PLATFORMS = {"xiaohongshu", "douyin"}

# ── 平台识别 ────────────────────────────────────────────────

_XHS_KEYWORDS = ["小红书", "笔记"]
_XHS_TASK_KEYWORDS = ["文案", "推广", "标题", "种草"]
_DOUYIN_KEYWORDS = ["抖音", "短视频", "口播", "分镜", "脚本"]
_DOUYIN_TASK_KEYWORDS = ["文案", "推广", "脚本", "分镜"]

# ── 交付物类型识别 ──────────────────────────────────────────

_ARTIFACT_TYPE_PATTERNS = [
    # (正则, artifact_type, 中文名)
    (r"商品.*上架|上架.*物料|listing|产品详情", "product_listing", "商品上架物料包"),
    (r"内容日历|内容排期|发布计划|一周.*内容|每日.*内容", "content_calendar", "内容日历"),
    (r"调研.*简报|调研报告|市场.*调研|用户.*调研|竞品.*调研|做调研|调研分析|竞品分析简报", "research_brief", "调研简报"),
    (r"竞品.*分析|竞争对手.*分析|竞争.*报告|竞品调研|竞品简报", "competitor_report", "竞品分析报告"),
    (r"分析.*报告|数据分析|统计报告|运营报告", "analysis_report", "分析报告"),
    (r"数据.*分析报告|数据分析报告|数据.*简报|分析.*简报|销售.*分析|运营.*分析|业务.*分析|数据.*洞察|数据.*解读", "data_report", "数据分析报告"),
    (r"分析.*数据", "data_report", "数据分析"),
    (r"图片.*提示词|产品图.*提示|prompt.*图|AI.*图.*提示|生图.*提示", "image_prompt_pack", "图片提示词包"),
    (r"SOP|标准操作|操作流程|工作流程文档", "sop_doc", "SOP文档"),
    (r"营销.*方案|活动.*方案|推广方案|campaign", "campaign_plan", "营销活动方案"),
    (r"邮件.*序列|邮件.*营销|email.*sequence|邮件模板", "email_sequence", "邮件营销序列"),
    (r"landing\s*page|落地页|着陆页.*文案", "landing_page_copy", "Landing Page文案"),
]

# 已支持的 artifact_type
_SUPPORTED_ARTIFACT_TYPES = {"copy_pack", "image_prompt_pack", "research_brief", "landing_page_copy", "data_report"}


def classify_goal(
    goal: str,
    explicit_platform: Optional[str] = None,
) -> ClassificationResult:
    """
    对用户 goal 进行分类，确定是否在系统受控能力范围内。
    使用确定性规则，不调用 LLM。
    """
    if not goal or len(goal.strip()) < 3:
        return ClassificationResult(
            ok=False,
            needs_clarification=True,
            reason="输入过短，请提供更详细的业务目标",
            clarification_questions=["请描述你想要生成什么类型的文案？目标产品是什么？"],
        )

    # 0. 非法 platform 直接拒绝（空字符串视为 None）
    if explicit_platform is not None and explicit_platform != "" and explicit_platform not in SUPPORTED_PLATFORMS:
        return ClassificationResult(
            ok=False,
            capability_id="unsupported.complex_agent_workflow",
            confidence=1.0,
            needs_clarification=True,
            reason=f"不支持的平台: {explicit_platform}",
            clarification_questions=["当前仅支持 xiaohongshu 和 douyin"],
            normalized_inputs={"goal": goal, "platform": explicit_platform},
        )

    # 1. 模糊/拒绝关键词检测（优先于 explicit_platform，防止绕过）
    for pattern in _VAGUE_PATTERNS:
        if re.search(pattern, goal):
            return ClassificationResult(
                ok=False,
                capability_id="unsupported.complex_agent_workflow",
                confidence=1.0,
                reason="目标过于宽泛或涉及复杂系统构建，不在当前受控能力范围内",
                needs_clarification=True,
                clarification_questions=[
                    "你是否需要生成某个具体产品的文案？",
                    "请明确具体的平台（小红书/抖音）和产品品类",
                ],
                normalized_inputs={"goal": goal},
            )

    # 2. 显式 platform 优先（在模糊检测之后，防止自动赚钱等目标绕过）
    if explicit_platform == "xiaohongshu":
        return ClassificationResult(
            ok=True,
            capability_id="copy_pack.xiaohongshu",
            confidence=0.95,
            reason="显式指定平台为小红书",
            normalized_inputs={"artifact_type": "copy_pack", "platform": "xiaohongshu", "goal": goal},
        )
    if explicit_platform == "douyin":
        return ClassificationResult(
            ok=True,
            capability_id="copy_pack.douyin",
            confidence=0.95,
            reason="显式指定平台为抖音",
            normalized_inputs={"artifact_type": "copy_pack", "platform": "douyin", "goal": goal},
        )

    # 3. 多能力协同检测（明确组合 2+ 能力 → collaboration.controlled）
    for conjunction in _COLLABORATION_CONJUNCTIONS:
        if conjunction in goal:
            matched_caps = set()
            for cap_key, keywords in _COLLABORATION_CAPABILITY_KEYWORDS.items():
                for kw in keywords:
                    if kw in goal:
                        matched_caps.add(cap_key)
                        break
            if len(matched_caps) >= 2:
                return ClassificationResult(
                    ok=True,
                    capability_id="collaboration.controlled",
                    confidence=0.9,
                    reason=f"检测到多能力协同组合: {', '.join(matched_caps)}",
                    normalized_inputs={"goal": goal, "detected_capabilities": list(matched_caps)},
                )

    # 4. 识别交付物类型
    for pattern, artifact_type, type_name in _ARTIFACT_TYPE_PATTERNS:
        if re.search(pattern, goal, re.IGNORECASE):
            # 已支持的 artifact_type → 直接通过
            if artifact_type in _SUPPORTED_ARTIFACT_TYPES:
                return ClassificationResult(
                    ok=True,
                    capability_id=artifact_type,
                    confidence=0.9,
                    reason=f"已识别交付物类型为 {type_name}（{artifact_type}）",
                    normalized_inputs={"artifact_type": artifact_type, "goal": goal},
                )
            # 未支持的 → 拒绝
            return ClassificationResult(
                ok=False,
                capability_id="unsupported.artifact_type",
                confidence=0.85,
                reason=f"已识别交付物类型为 {type_name}（{artifact_type}），但当前尚未实现该类型的闭环能力",
                needs_clarification=True,
                clarification_questions=[
                    f"当前系统暂不支持 {type_name} 的自动生成",
                    "目前支持的交付物类型：小红书文案包、抖音短视频文案包、图片提示词包、数据分析报告",
                ],
                normalized_inputs={"artifact_type": artifact_type, "goal": goal},
            )

    # 5. 平台关键词检测
    has_xhs_platform = any(kw in goal for kw in _XHS_KEYWORDS)
    has_xhs_task = any(kw in goal for kw in _XHS_TASK_KEYWORDS)
    has_douyin_platform = any(kw in goal for kw in _DOUYIN_KEYWORDS)
    has_douyin_task = any(kw in goal for kw in _DOUYIN_TASK_KEYWORDS)

    # 6. 同时有小红书和抖音关键词 → 需要澄清（优先于单平台匹配）
    if has_xhs_platform and has_douyin_platform:
        return ClassificationResult(
            ok=False,
            needs_clarification=True,
            reason="同时检测到小红书和抖音关键词，请明确平台",
            clarification_questions=["请选择目标平台：小红书 或 抖音？"],
            normalized_inputs={"artifact_type": "copy_pack", "goal": goal},
        )

    # 7. 小红书文案匹配
    if has_xhs_platform and has_xhs_task:
        return ClassificationResult(
            ok=True,
            capability_id="copy_pack.xiaohongshu",
            confidence=0.85,
            reason="检测到小红书文案生成意图",
            normalized_inputs={"artifact_type": "copy_pack", "platform": "xiaohongshu", "goal": goal},
        )

    # 8. 抖音文案匹配
    if has_douyin_platform and has_douyin_task:
        return ClassificationResult(
            ok=True,
            capability_id="copy_pack.douyin",
            confidence=0.85,
            reason="检测到抖音文案生成意图",
            normalized_inputs={"artifact_type": "copy_pack", "platform": "douyin", "goal": goal},
        )

    # 9. 仅有平台关键词但无任务关键词 → 需要澄清
    if has_xhs_platform and not has_xhs_task:
        return ClassificationResult(
            ok=False,
            needs_clarification=True,
            reason="检测到小红书但未明确任务类型",
            clarification_questions=["你需要生成什么类型的文案？（种草文案、标题、推广内容等）"],
            normalized_inputs={"artifact_type": "copy_pack", "platform": "xiaohongshu", "goal": goal},
        )
    if has_douyin_platform and not has_douyin_task:
        return ClassificationResult(
            ok=False,
            needs_clarification=True,
            reason="检测到抖音但未明确任务类型",
            clarification_questions=["你需要生成什么类型的文案？（短视频脚本、口播文案、推广内容等）"],
            normalized_inputs={"artifact_type": "copy_pack", "platform": "douyin", "goal": goal},
        )

    # 10. 有文案任务关键词但无平台 → 需要澄清，不允许默认降级
    if has_xhs_task or has_douyin_task:
        return ClassificationResult(
            ok=False,
            needs_clarification=True,
            reason="检测到文案生成意图，但未明确目标平台",
            clarification_questions=["请明确目标平台：小红书 或 抖音？"],
            normalized_inputs={"artifact_type": "copy_pack", "goal": goal},
        )

    # 11. 无法匹配 → 不支持
    return ClassificationResult(
        ok=False,
        capability_id="unsupported.complex_agent_workflow",
        confidence=0.7,
        reason="无法将目标匹配到当前受控能力，不支持无约束的复杂任务",
        needs_clarification=True,
        clarification_questions=[
            "当前系统支持：小红书文案包、抖音短视频文案包、图片提示词包、数据分析报告生成",
            "请描述你的具体需求，例如：'帮我为手工耳环生成小红书种草文案'",
        ],
        normalized_inputs={"goal": goal},
    )
