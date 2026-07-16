"""MiniDelivery 路由器 — 最小可交付闭环 API"""
import json
import os
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional

from datetime import datetime, timezone
from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import PlainTextResponse, FileResponse

from backend.minidelivery.models import XHSCopyRequest, CopyPackRequest, SaveFromAgentRequest, CompareTasksRequest
from backend.minidelivery.pipeline import run_pipeline, run_copy_pack_pipeline
from backend.minidelivery.artifact_writer import OUTPUT_ROOT, ensure_output_dir

router = APIRouter(prefix="/minidelivery", tags=["MiniDelivery / 最小交付闭环"])


def _as_list(val: Any) -> list:
    """确保值是列表——字符串不会被逐字符拆分"""
    if isinstance(val, list):
        return val
    if isinstance(val, str) and val:
        return [val]
    if val:
        return [str(val)]
    return []


def _has_value(val: Any) -> bool:
    return val not in (None, "", [], {})


def _format_md_value(val: Any) -> str:
    if isinstance(val, (dict, list)):
        return json.dumps(val, ensure_ascii=False, indent=2)
    return str(val)


def _append_value_section(lines: list, heading: str, val: Any, level: str = "###") -> None:
    if _has_value(val):
        lines += [f"{level} {heading}", "", _format_md_value(val), ""]


def _append_list_section(lines: list, heading: str, val: Any, level: str = "###") -> None:
    items = _as_list(val)
    if not items:
        return
    lines += [f"{level} {heading}", ""]
    for item in items:
        lines.append(f"- {_format_md_value(item)}")
    lines.append("")


# ── 旧接口（兼容保留）──────────────────────────────────────

@router.post("/xhs-copy-pack", summary="小红书文案包生成（旧接口）",
             description="输入业务目标，生成完整的小红书种草文案包 Markdown 文件并严格验收")
def create_xhs_copy_pack(request: XHSCopyRequest):
    result = run_pipeline(request.goal)
    return result.model_dump()


# ── 新通用接口 ─────────────────────────────────────────────

@router.post("/copy-pack", summary="通用文案包生成",
             description="输入业务目标，支持小红书/抖音平台，生成文案包 Markdown 文件并严格验收")
def create_copy_pack(request: CopyPackRequest):
    result = run_copy_pack_pipeline(
        goal=request.goal,
        platform=request.platform,
        artifact_type=request.artifact_type,
    )
    return result.model_dump()


# ── Agent 结果保存（Phase 1A）──────────────────────────────

# 每个 agent_id 对应的中文标签
_AGENT_LABELS: Dict[str, str] = {
    "marketing": "营销文案包",
    "image": "图片提示词 / 视觉 Brief",
    "data": "数据分析报告",
    "research": "调研简报",
    "website": "落地页草稿",
}


def _render_marketing(result: Dict, goal: str, title: Optional[str] = None) -> str:
    """渲染 marketing agent 的 Markdown 交付物"""
    so = result.get("structured_output") or result.get("output") or {}
    lines = [f"# {title or '营销文案包'}", "", f"> 目标：{goal}", ""]

    # ── brand_strategy 子对象 ──
    brand_strategy = so.get("brand_strategy", {})
    if not isinstance(brand_strategy, dict):
        brand_strategy = {}
    if not brand_strategy:
        brand_strategy = {
            key: so.get(key)
            for key in [
                "brand_positioning",
                "target_audience",
                "differentiation",
                "brand_voice",
                "visual_direction",
                "tagline_options",
                "competitor_insight",
            ]
            if _has_value(so.get(key))
        }
    if brand_strategy:
        lines += ["## 品牌策略", ""]
        _append_value_section(lines, "品牌定位", brand_strategy.get("brand_positioning"))
        _append_value_section(lines, "目标受众", brand_strategy.get("target_audience"))
        _append_value_section(lines, "差异化", brand_strategy.get("differentiation"))
        _append_value_section(lines, "品牌调性", brand_strategy.get("brand_voice"))
        _append_value_section(lines, "视觉方向", brand_strategy.get("visual_direction"))
        _append_list_section(lines, "标语备选", brand_strategy.get("tagline_options", []))
        _append_value_section(lines, "竞品洞察", brand_strategy.get("competitor_insight"))

    # ── campaign_plan 子对象 ──
    campaign_plan = so.get("campaign_plan", {})
    if not isinstance(campaign_plan, dict):
        campaign_plan = {}
    if not campaign_plan:
        campaign_plan = {
            key: so.get(key)
            for key in [
                "campaign_name",
                "goal",
                "target_segments",
                "key_message",
                "channels",
                "timeline",
                "kpis",
                "budget_suggestion",
                "risks",
            ]
            if _has_value(so.get(key))
        }
    if campaign_plan:
        lines += ["## 活动方案", ""]
        _append_value_section(lines, "活动名称", campaign_plan.get("campaign_name"))
        _append_value_section(lines, "目标", campaign_plan.get("goal"))
        _append_list_section(lines, "目标人群", campaign_plan.get("target_segments", []))
        _append_value_section(lines, "核心信息", campaign_plan.get("key_message"))
        _append_list_section(lines, "投放渠道", campaign_plan.get("channels", []))
        _append_value_section(lines, "时间表", campaign_plan.get("timeline"))
        _append_list_section(lines, "关键指标 (KPI)", campaign_plan.get("kpis", []))
        _append_value_section(lines, "预算建议", campaign_plan.get("budget_suggestion"))
        _append_list_section(lines, "风险", campaign_plan.get("risks", []))

    # ── 原有顶层字段 ──
    # 标题
    headline = so.get("headline") or so.get("title", "")
    if headline:
        lines += ["## 标题", "", headline, ""]

    # 副标题
    subheadline = so.get("subheadline", "")
    if subheadline:
        lines += ["## 副标题", "", subheadline, ""]

    # 正文 / 内容
    body = so.get("body") or so.get("content", "")
    if body:
        lines += ["## 正文", "", body, ""]

    # 行动号召
    cta = so.get("cta") or so.get("call_to_action", "")
    if cta:
        lines += ["## 行动号召", "", cta, ""]

    # 标签
    hashtags = _as_list(so.get("hashtags") or so.get("tags", []))
    if hashtags:
        tag_str = " ".join(f"#{t}" if not str(t).startswith("#") else str(t) for t in hashtags)
        lines += ["## 标签", "", tag_str, ""]

    # 关键词
    keywords = _as_list(so.get("keywords", []))
    if keywords:
        lines += ["## 关键词", "", ", ".join(keywords), ""]

    # 语气风格
    tone = so.get("tone", "")
    if tone:
        lines += ["## 语气风格", "", tone, ""]

    # 目标平台
    platform = so.get("platform", "")
    if platform:
        lines += ["## 目标平台", "", platform, ""]

    # 推荐发布时间
    best_posting_time = so.get("best_posting_time", "")
    if best_posting_time:
        lines += ["## 推荐发布时间", "", best_posting_time, ""]

    # 互动钩子
    engagement_hooks = _as_list(so.get("engagement_hooks", []))
    if engagement_hooks:
        lines += ["## 互动钩子", ""]
        for hook in engagement_hooks:
            lines.append(f"- {hook}")
        lines.append("")

    # 媒体建议
    media_suggestion = so.get("media_suggestion", "")
    if media_suggestion:
        lines += ["## 媒体建议", "", media_suggestion, ""]

    # 备选方案
    variations = _as_list(so.get("variations", []))
    if variations:
        lines += ["## 备选方案", ""]
        for v in variations:
            lines.append(f"- {v}")
        lines.append("")

    # 保留 warnings/errors/metadata
    _append_meta(lines, result)
    return "\n".join(lines)


def _render_image(result: Dict, goal: str, title: Optional[str] = None) -> str:
    """渲染 image agent 的 Markdown 交付物"""
    so = result.get("structured_output") or result.get("output") or {}
    lines = [f"# {title or '图片提示词 / 视觉 Brief'}", "", f"> 目标：{goal}", ""]

    # 图片提示词（优先 image_prompt，兼容旧字段）
    image_prompt = so.get("image_prompt") or so.get("main_prompt", "")
    if image_prompt:
        lines += ["## 图片提示词", "", image_prompt, ""]

    # 细节提示词
    detail_prompt = so.get("detail_prompt", "")
    if detail_prompt:
        lines += ["## 细节提示词", "", detail_prompt, ""]

    # 场景提示词
    scene_prompt = so.get("scene_prompt", "")
    if scene_prompt:
        lines += ["## 场景提示词", "", scene_prompt, ""]

    # 负向提示词
    negative_prompt = so.get("negative_prompt", "")
    if negative_prompt:
        lines += ["## 负向提示词", "", negative_prompt, ""]

    # 主体
    subject = so.get("subject", "")
    if subject:
        lines += ["## 主体", "", subject, ""]

    # 背景
    background = so.get("background", "")
    if background:
        lines += ["## 背景", "", background, ""]

    # 风格
    style = so.get("style", "")
    if style:
        lines += ["## 风格", "", style, ""]

    # 宽高比
    aspect_ratio = so.get("aspect_ratio", "")
    if aspect_ratio:
        lines += ["## 宽高比", "", aspect_ratio, ""]

    # 构图
    composition = so.get("composition", "")
    if composition:
        lines += ["## 构图", "", composition, ""]

    # 光线
    lighting = so.get("lighting", "")
    if lighting:
        lines += ["## 光线", "", lighting, ""]

    # 色彩方案
    color_palette = so.get("color_palette", "")
    if color_palette:
        lines += ["## 色彩方案", "", color_palette, ""]

    # 使用建议
    tips = so.get("usage_tips") or so.get("usage_suggestions") or so.get("tips", "")
    if tips:
        if isinstance(tips, list):
            lines += ["## 使用建议", ""]
            for tip in tips:
                lines.append(f"- {tip}")
            lines.append("")
        else:
            lines += ["## 使用建议", "", tips, ""]

    # 变体方案
    variations = _as_list(so.get("variations", []))
    if variations:
        lines += ["## 变体方案", ""]
        for v in variations:
            lines.append(f"- {v}")
        lines.append("")

    # 限制说明
    limitations = _as_list(so.get("limitations", []))
    if limitations:
        lines += ["## 限制说明", ""]
        for lim in limitations:
            lines.append(f"- {lim}")
        lines.append("")

    # 生成的图片 (Phase 4.8)
    generated_images = so.get("generated_images", [])
    if generated_images:
        lines += ["## 生成图片", ""]
        # 兼容 meta / metadata 两种 key
        provider = result.get("meta", {}).get("image_provider") or result.get("metadata", {}).get("image_provider", "unknown")
        lines.append(f"> Provider: {provider}")
        lines.append("")
        for img in generated_images:
            url = img.get("url", "")
            revised = img.get("revised_prompt", "")
            is_mock = img.get("is_mock", False)
            mock_tag = " (模拟)" if is_mock else ""
            lines.append(f"### 图片 {img.get('index', 0) + 1}{mock_tag}")
            lines.append("")
            if url:
                lines.append(f"![图片]({url})")
                lines.append("")
                lines.append(f"URL: {url}")
                lines.append("")
            if revised:
                lines.append(f"修订提示词: {revised}")
                lines.append("")
        lines.append("")

    # 如果以上都没有，尝试通用 content
    if not any(so.get(k) for k in ["image_prompt", "main_prompt", "detail_prompt", "scene_prompt", "negative_prompt", "subject", "style"]):
        content = so.get("content", "")
        if content:
            lines += ["## 内容", "", content, ""]

    _append_meta(lines, result)
    return "\n".join(lines)


def _render_data(result: Dict, goal: str, title: Optional[str] = None) -> str:
    """渲染 data agent 的 Markdown 交付物"""
    so = result.get("structured_output") or result.get("output") or {}
    meta = result.get("metadata", {})
    lines = [f"# {title or '数据分析报告'}", "", f"> 目标：{goal}", ""]

    # ── 数据来源信息（Phase 4.4）──
    data_source_type = meta.get("data_source_type", "none")
    sample_rows = meta.get("sample_rows", 0)
    ds_label = {"csv": "CSV 文件", "json": "JSON 文件", "inline": "内联数据", "none": "无真实数据（框架建议）"}.get(data_source_type, data_source_type)
    lines += [
        "## 数据来源", "",
        f"- **来源类型**: {ds_label}",
        f"- **样本行数**: {sample_rows}" if sample_rows > 0 else "- **样本行数**: 无",
        "",
    ]

    # 分析问题
    analysis_question = so.get("analysis_question", "")
    if analysis_question:
        lines += ["## 分析问题", "", analysis_question, ""]

    # 分析目标（兼容旧字段）
    analysis_goal = so.get("analysis_goal", "")
    if analysis_goal and not analysis_question:
        lines += ["## 分析目标", "", analysis_goal, ""]

    # 数据概况
    data_summary = so.get("data_summary", "")
    if data_summary:
        lines += ["## 数据概况", "", data_summary, ""]

    # 数据范围（兼容旧字段）
    data_scope = so.get("data_scope", "")
    if data_scope and not data_summary:
        lines += ["## 数据范围", "", data_scope, ""]

    # 关键指标
    key_metrics = so.get("key_metrics", [])
    if key_metrics:
        lines += ["## 关键指标", ""]
        if isinstance(key_metrics, list):
            for m in key_metrics:
                if isinstance(m, dict):
                    desc = f"{m.get('name', '')}: {m.get('description', '')}"
                    if m.get('formula'):
                        desc += f" ({m['formula']})"
                    lines.append(f"- {desc}")
                else:
                    lines.append(f"- {m}")
        else:
            lines.append(str(key_metrics))
        lines.append("")

    # 核心指标（兼容旧字段）
    core_metrics = so.get("core_metrics", "")
    if core_metrics and not key_metrics:
        lines += ["## 核心指标", "", str(core_metrics), ""]

    # 趋势
    trends = _as_list(so.get("trends", []))
    if trends:
        lines += ["## 趋势", ""]
        for t in trends:
            lines.append(f"- {t}")
        lines.append("")

    # 趋势观察（兼容旧字段）
    trend_observations = so.get("trend_observations", "")
    if trend_observations and not trends:
        lines += ["## 趋势观察", "", str(trend_observations), ""]

    # 关键发现
    findings = _as_list(so.get("findings", []))
    if not findings:
        findings = _as_list(so.get("key_findings", []))
    if findings:
        lines += ["## 关键发现", ""]
        for f in findings:
            lines.append(f"- {f}")
        lines.append("")

    # 风险
    risks = _as_list(so.get("risks", []))
    if risks:
        lines += ["## 风险", ""]
        for r in risks:
            lines.append(f"- {r}")
        lines.append("")

    # 建议
    recommendations = _as_list(so.get("recommendations", []))
    if not recommendations:
        recommendations = _as_list(so.get("action_recommendations", []))
    if recommendations:
        lines += ["## 建议", ""]
        for rec in recommendations:
            lines.append(f"- {rec}")
        lines.append("")

    # 行动建议（兼容旧字段）
    action_recommendations = so.get("action_recommendations", "")
    if action_recommendations and not recommendations:
        lines += ["## 行动建议", "", str(action_recommendations), ""]

    # 假设前提
    assumptions = _as_list(so.get("assumptions", []))
    if assumptions:
        lines += ["## 假设前提", ""]
        for a in assumptions:
            lines.append(f"- {a}")
        lines.append("")

    # 限制说明
    limitations = _as_list(so.get("limitations", []))
    if limitations:
        lines += ["## 限制说明", ""]
        for lim in limitations:
            lines.append(f"- {lim}")
        lines.append("")

    # 建议图表
    charts_suggested = _as_list(so.get("charts_suggested", []))
    if charts_suggested:
        lines += ["## 建议图表", ""]
        for c in charts_suggested:
            if isinstance(c, dict):
                lines.append(f"- {c.get('type', '')}: {c.get('x_axis', '')} vs {c.get('y_axis', '')} — {c.get('purpose', '')}")
            else:
                lines.append(f"- {c}")
        lines.append("")

    # 异常检查（兼容旧字段）
    anomaly_checks = so.get("anomaly_checks", "")
    if anomaly_checks:
        lines += ["## 异常检查", "", str(anomaly_checks), ""]

    # 业务解读（兼容旧字段）
    business_interpretation = so.get("business_interpretation", "")
    if business_interpretation:
        lines += ["## 业务解读", "", str(business_interpretation), ""]

    # 如果以上都没有，尝试通用 content
    if not any(so.get(k) for k in ["analysis_question", "data_summary", "key_metrics", "trends", "findings"]):
        content = so.get("content", "")
        if content:
            lines += ["## 内容", "", content, ""]

    _append_meta(lines, result)
    return "\n".join(lines)


def _render_research(result: Dict, goal: str, title: Optional[str] = None) -> str:
    """渲染 research agent 的 Markdown 交付物"""
    so = result.get("structured_output") or result.get("output") or {}
    lines = [f"# {title or '调研简报'}", "", f"> 目标：{goal}", ""]

    # 调研问题
    research_question = so.get("research_question", "")
    if research_question:
        lines += ["## 调研问题", "", research_question, ""]

    # 调研目标（兼容旧字段）
    research_goal = so.get("research_goal", "")
    if research_goal and not research_question:
        lines += ["## 调研目标", "", research_goal, ""]

    # 市场概况
    market_summary = so.get("market_summary", "")
    if market_summary:
        lines += ["## 市场概况", "", market_summary, ""]

    # 关键发现
    key_findings = _as_list(so.get("key_findings", []))
    if key_findings:
        lines += ["## 关键发现", ""]
        for f in key_findings:
            lines.append(f"- {f}")
        lines.append("")

    # 竞品分析
    competitors = _as_list(so.get("competitors", []))
    if competitors:
        lines += ["## 竞品分析", ""]
        for c in competitors:
            if isinstance(c, dict):
                lines.append(f"### {c.get('name', '竞品')}")
                lines.append(f"- 优势: {c.get('strength', '')}")
                lines.append(f"- 劣势: {c.get('weakness', '')}")
                lines.append(f"- 定位: {c.get('positioning', '')}")
                lines.append("")
            else:
                lines.append(f"- {c}")
        lines.append("")

    # 竞品维度（兼容旧字段）
    competitor_dimensions = so.get("competitor_dimensions", "")
    if competitor_dimensions and not competitors:
        lines += ["## 竞品维度", "", str(competitor_dimensions), ""]

    # 机会
    opportunities = _as_list(so.get("opportunities", []))
    if not opportunities:
        opportunities = _as_list(so.get("content_opportunities", []))
    if opportunities:
        lines += ["## 机会", ""]
        for o in opportunities:
            lines.append(f"- {o}")
        lines.append("")

    # 内容机会（兼容旧字段）
    content_opportunities = _as_list(so.get("content_opportunities", []))
    if content_opportunities and not opportunities:
        lines += ["## 内容机会", ""]
        for o in content_opportunities:
            lines.append(f"- {o}")
        lines.append("")

    # 风险
    risks = _as_list(so.get("risks", []))
    if not risks:
        risks = _as_list(so.get("risk_warnings", []))
    if risks:
        lines += ["## 风险", ""]
        for r in risks:
            lines.append(f"- {r}")
        lines.append("")

    # 风险提示（兼容旧字段）
    risk_warnings = _as_list(so.get("risk_warnings", []))
    if risk_warnings and not risks:
        lines += ["## 风险提示", ""]
        for r in risk_warnings:
            lines.append(f"- {r}")
        lines.append("")

    # 建议行动
    recommended_actions = _as_list(so.get("recommended_actions", []))
    if recommended_actions:
        lines += ["## 建议行动", ""]
        for i, a in enumerate(recommended_actions, 1):
            lines.append(f"{i}. {a}")
        lines.append("")

    # 目标用户（兼容旧字段）
    target_users = so.get("target_users", "")
    if target_users:
        lines += ["## 目标用户", "", str(target_users), ""]

    # 痛点分析（兼容旧字段）
    pain_points = so.get("pain_points", "")
    if pain_points:
        lines += ["## 痛点分析", "", str(pain_points), ""]

    # 下一步（兼容旧字段）
    next_steps = so.get("next_steps", "")
    if next_steps:
        lines += ["## 下一步", "", str(next_steps), ""]

    # 限制说明
    limitations = _as_list(so.get("limitations", []))
    if limitations:
        lines += ["## 限制说明", ""]
        for lim in limitations:
            lines.append(f"- {lim}")
        lines.append("")

    # 信息来源
    sources = _as_list(so.get("sources", []))
    if sources:
        lines += ["## 信息来源", ""]
        for s in sources:
            lines.append(f"- {s}")
        lines.append("")

    # 如果以上都没有，尝试通用 content
    if not any(so.get(k) for k in ["research_question", "market_summary", "key_findings", "competitors"]):
        content = so.get("content", "")
        if content:
            lines += ["## 内容", "", content, ""]

    _append_meta(lines, result)
    return "\n".join(lines)


def _render_website(result: Dict, goal: str, title: Optional[str] = None) -> str:
    """渲染 website agent 的 Markdown 交付物"""
    so = result.get("structured_output") or result.get("output") or {}
    lines = [f"# {title or '落地页草稿'}", "", f"> 目标：{goal}", ""]

    # 页面目标
    page_goal = so.get("page_goal", "")
    if page_goal:
        lines += ["## 页面目标", "", page_goal, ""]

    # 目标受众
    target_audience = so.get("target_audience", "")
    if target_audience:
        lines += ["## 目标受众", "", target_audience, ""]

    # 页面定位（兼容旧字段）
    page_positioning = so.get("page_positioning", "")
    if page_positioning and not page_goal:
        lines += ["## 页面定位", "", page_positioning, ""]

    # Hero 区域
    hero = so.get("hero", {})
    if hero:
        lines += ["## Hero 区域", ""]
        if hero.get("headline"):
            lines.append(f"**标题:** {hero['headline']}")
        if hero.get("subheadline"):
            lines.append(f"**副标题:** {hero['subheadline']}")
        if hero.get("primary_cta"):
            lines.append(f"**CTA:** {hero['primary_cta']}")
        lines.append("")

    # Hero 标题（兼容旧字段）
    hero_title = so.get("hero_title", "")
    if hero_title and not hero:
        lines += ["## Hero 标题", "", hero_title, ""]

    # 副标题（兼容旧字段）
    subtitle = so.get("subtitle", "")
    if subtitle and not hero:
        lines += ["## 副标题", "", subtitle, ""]

    # 内容板块
    sections = _as_list(so.get("sections", []))
    if sections:
        lines += [f"## 内容板块 ({len(sections)})", ""]
        for i, section in enumerate(sections, 1):
            if isinstance(section, dict):
                lines.append(f"### {section.get('title', f'板块 {i}')}")
                if section.get("content"):
                    lines.append(section["content"])
                if section.get("cta"):
                    lines.append(f"\n**CTA:** {section['cta']}")
            else:
                lines.append(f"### 板块 {i}\n{section}")
            lines.append("")

    # 卖点（兼容旧字段）
    selling_points = so.get("selling_points", "")
    if selling_points and not sections:
        lines += ["## 卖点", "", str(selling_points), ""]

    # 页面结构（兼容旧字段）
    page_structure = so.get("page_structure", "")
    if page_structure and not sections:
        lines += ["## 页面结构", "", str(page_structure), ""]

    # 行动号召
    ctas = so.get("ctas", {})
    if ctas:
        lines += ["## 行动号召", ""]
        if ctas.get("primary"):
            lines.append(f"**主要 CTA:** {ctas['primary']}")
        if ctas.get("secondary"):
            lines.append(f"**次要 CTA:** {ctas['secondary']}")
        if ctas.get("exit_intent"):
            lines.append(f"**退出弹窗:** {ctas['exit_intent']}")
        lines.append("")

    # CTA（兼容旧字段，单个字符串）
    cta = so.get("cta", "")
    if cta and not ctas:
        lines += ["## 行动号召", "", cta, ""]

    # 信任元素
    trust_elements = _as_list(so.get("trust_elements", []))
    if trust_elements:
        lines += ["## 信任元素", ""]
        for t in trust_elements:
            lines.append(f"- {t}")
        lines.append("")

    # SEO 信息
    seo = so.get("seo", {})
    if seo:
        lines += ["## SEO 信息", ""]
        if seo.get("title"):
            lines.append(f"**Title:** {seo['title']}")
        if seo.get("description"):
            lines.append(f"**Description:** {seo['description']}")
        if seo.get("keywords"):
            lines.append(f"**Keywords:** {', '.join(seo['keywords'])}")
        lines.append("")

    # 设计方向
    design_direction = so.get("design_direction", "")
    if design_direction:
        lines += ["## 设计方向", "", design_direction, ""]

    # 风险
    risks = _as_list(so.get("risks", []))
    if risks:
        lines += ["## 风险", ""]
        for r in risks:
            lines.append(f"- {r}")
        lines.append("")

    # 建议
    recommendations = _as_list(so.get("recommendations", []))
    if recommendations:
        lines += ["## 建议", ""]
        for rec in recommendations:
            lines.append(f"- {rec}")
        lines.append("")

    # 假设前提
    assumptions = _as_list(so.get("assumptions", []))
    if assumptions:
        lines += ["## 假设前提", ""]
        for a in assumptions:
            lines.append(f"- {a}")
        lines.append("")

    # 限制说明
    limitations = _as_list(so.get("limitations", []))
    if limitations:
        lines += ["## 限制说明", ""]
        for lim in limitations:
            lines.append(f"- {lim}")
        lines.append("")

    # FAQ（兼容旧字段）
    faq = _as_list(so.get("faq", []))
    if faq:
        lines += ["## 常见问题", ""]
        for item in faq:
            if isinstance(item, dict):
                lines.append(f"**Q: {item.get('question', '')}**")
                lines.append(f"A: {item.get('answer', '')}")
            else:
                lines.append(f"- {item}")
            lines.append("")

    # 视觉建议（兼容旧字段）
    visual_suggestions = so.get("visual_suggestions", "")
    if visual_suggestions:
        lines += ["## 视觉建议", "", str(visual_suggestions), ""]

    # 如果以上都没有，尝试通用 content
    if not any(so.get(k) for k in ["page_goal", "hero", "sections", "page_positioning", "hero_title"]):
        content = so.get("content", "")
        if content:
            lines += ["## 内容", "", content, ""]

    _append_meta(lines, result)
    return "\n".join(lines)


def _render_generic(result: Dict, goal: str, title: Optional[str] = None) -> str:
    """通用渲染：未知 agent_id 时使用"""
    agent_id = result.get("agent_id", "unknown")
    label = _AGENT_LABELS.get(agent_id, agent_id)
    lines = [f"# {title or f'{label} 交付物'}", "", f"> 目标：{goal}", ""]

    so = result.get("structured_output") or result.get("output") or {}
    if so:
        lines += ["## 结构化产出", "", "```json"]
        lines.append(json.dumps(so, ensure_ascii=False, indent=2))
        lines += ["```", ""]

    artifacts = result.get("artifacts", [])
    if artifacts:
        lines += ["## 产物路径", ""]
        for a in artifacts:
            lines.append(f"- `{a}`")
        lines.append("")

    _append_meta(lines, result)
    return "\n".join(lines)


def _render_boss(result: Dict, goal: str, title: Optional[str] = None) -> str:
    """渲染 boss agent 的 Markdown 交付物（Boss Lite 汇总报告）"""
    so = result.get("structured_output") or result.get("output") or {}
    lines = [f"# {title or 'Boss Lite 作战报告'}", "", f"> **业务目标：** {goal}", "", "---", ""]

    # 执行计划
    plan = so.get("plan", [])
    if plan:
        lines += ["## 执行计划", ""]
        for task in plan:
            status_icon = "✅" if task.get("status") == "done" else "❌" if task.get("status") == "failed" else "⏳"
            lines.append(f"{status_icon} **{task.get('title', '')}** ({task.get('agent_id', '')}) — {task.get('purpose', '')}")
        lines.append("")

    # 各部门结果
    results_summary = so.get("results_summary", [])
    if results_summary:
        lines += ["---", "", "## 各部门执行结果", ""]
        for r in results_summary:
            status_icon = "✅" if r.get("ok") else "❌"
            lines.append(f"### {status_icon} {r.get('title', '')} ({r.get('agent_id', '')})")
            lines.append("")
            if r.get("summary"):
                lines.append(f"> {r['summary']}")
                lines.append("")

    # 总结
    succeeded = so.get("succeeded", 0)
    failed = so.get("failed", 0)
    total = so.get("total", 0)
    lines += [
        "---",
        "",
        "## 总结",
        "",
        f"- 成功: {succeeded}/{total}",
        f"- 失败: {failed}/{total}",
        "",
        "---",
        "",
        "## 最终建议",
        "",
        "根据以上各部门的分析，建议按以下优先级推进：",
        "",
        "1. 先确认市场调研的核心发现，验证目标用户需求",
        "2. 基于营销方案准备第一批内容素材",
        "3. 使用视觉方案制作配图和封面",
        "4. 参考落地页方案搭建转化页面",
        "5. 按数据分析框架建立效果追踪体系",
        "",
        "---",
        "",
        f"*由 AI Company OS Boss Lite 生成 · {so.get('generated_at', '')}*",
    ]

    _append_meta(lines, result)
    return "\n".join(lines)


def _append_meta(lines: list, result: Dict) -> None:
    """追加 warnings/errors/metadata 到 Markdown 末尾"""
    warnings = result.get("warnings", [])
    errors = result.get("errors", [])
    metadata = result.get("metadata", {})

    if warnings:
        lines += ["## ⚠️ 警告", ""]
        for w in warnings:
            lines.append(f"- {w}")
        lines.append("")

    if errors:
        lines += ["## ❌ 错误", ""]
        for e in errors:
            lines.append(f"- {e}")
        lines.append("")

    if metadata:
        lines += ["## 元数据", "", "```json"]
        lines.append(json.dumps(metadata, ensure_ascii=False, indent=2))
        lines += ["```", ""]


_RENDERER_MAP = {
    "marketing": _render_marketing,
    "image": _render_image,
    "data": _render_data,
    "research": _render_research,
    "website": _render_website,
    "boss": _render_boss,
}


@router.post("/save-from-agent", summary="保存 Agent 结果到交付中心",
             description="将 AgentRunResult 转为可保存的交付物，不调用任何生产 pipeline")
def save_from_agent(request: SaveFromAgentRequest):
    agent_id = request.agent_id
    result = request.agent_result

    # 渲染 Markdown 交付物
    renderer = _RENDERER_MAP.get(agent_id, _render_generic)
    artifact_md = renderer(result, request.goal, request.title)

    # 生成 task_id 并保存
    task_id = f"agent_{uuid.uuid4().hex[:12]}"
    task_dir = ensure_output_dir(task_id)

    # 写入 artifact.md
    md_path = task_dir / "artifact.md"
    md_path.write_text(artifact_md, encoding="utf-8")

    # 写入 raw_agent_result.json
    raw_path = task_dir / "raw_agent_result.json"
    raw_path.write_text(
        json.dumps(result, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    # 写入 result.json（完整元数据）
    result_meta = result.get("metadata", {})
    result_json = {
        "task_id": task_id,
        "goal": request.goal,
        "agent_id": agent_id,
        "artifact_type": request.artifact_type or agent_id,
        "title": request.title,
        "source_page": request.source_page,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "ok": result.get("ok", False),
        "mode": "agent_save",
        "summary": result.get("summary", ""),
        "data_source_type": result_meta.get("data_source_type", "none"),
        "sample_rows": result_meta.get("sample_rows", 0),
        "artifact_path": str(md_path),
        "raw_agent_result_path": str(raw_path),
    }
    json_path = task_dir / "result.json"
    json_path.write_text(
        json.dumps(result_json, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    return {
        "task_id": task_id,
        "artifact_path": str(md_path),
        "result_path": str(json_path),
        "agent_id": agent_id,
        "artifact_type": request.artifact_type or agent_id,
    }


# ── 列表接口（Phase 2A）─────────────────────────────────────

@router.get("/tasks", summary="交付物列表",
            description="扫描 output/minidelivery/*/result.json，返回列表，支持搜索、筛选与分页")
def list_tasks(
    q: Optional[str] = Query(None, description="搜索关键词，匹配 goal/task_id/agent_id/artifact_type/source_page，大小写不敏感"),
    agent_id: Optional[str] = Query(None, description="按 agent_id 筛选"),
    artifact_type: Optional[str] = Query(None, description="按 artifact_type 筛选"),
    source_page: Optional[str] = Query(None, description="按 source_page 筛选"),
    limit: int = Query(50, ge=1, le=100, description="每页条数，默认 50，最大 100"),
    offset: int = Query(0, ge=0, description="跳过前 N 条，默认 0"),
):
    tasks: List[Dict[str, Any]] = []
    warnings: List[str] = []

    minidelivery_root = OUTPUT_ROOT
    if not minidelivery_root.exists():
        return {"tasks": [], "warnings": [], "total": 0, "limit": limit, "offset": 0, "has_more": False}

    for task_dir in sorted(minidelivery_root.iterdir()):
        if not task_dir.is_dir():
            continue
        result_path = task_dir / "result.json"
        if not result_path.exists():
            continue
        try:
            with open(result_path, "r", encoding="utf-8") as f:
                data = json.load(f)
        except (json.JSONDecodeError, UnicodeDecodeError) as exc:
            warnings.append(f"跳过损坏的 result.json: {task_dir.name} ({exc})")
            continue

        # 构建摘要（不读取 artifact.md 全文）
        task_id = data.get("task_id", task_dir.name)
        entry = {
            "task_id": task_id,
            "goal": data.get("goal", ""),
            "agent_id": data.get("agent_id", ""),
            "artifact_type": data.get("artifact_type", ""),
            "source_page": data.get("source_page", ""),
            "created_at": data.get("created_at", ""),
            "artifact_path": data.get("artifact_path", ""),
            "result_path": str(result_path),
        }

        # 如果 result.json 没有 created_at，用文件修改时间兜底
        if not entry["created_at"]:
            import os as _os
            mtime = _os.path.getmtime(result_path)
            from datetime import datetime, timezone
            entry["created_at"] = datetime.fromtimestamp(mtime, tz=timezone.utc).isoformat()

        # Boss Lite 复盘字段（可选，读取 raw_agent_result.json，失败不影响列表）
        if entry["agent_id"] == "boss":
            raw_p = task_dir / "raw_agent_result.json"
            try:
                if raw_p.exists():
                    with open(raw_p, "r", encoding="utf-8") as rf:
                        raw = json.load(rf)
                    for _key in ("succeeded", "failed", "total", "total_duration_ms", "handoff_enabled", "execution_mode"):
                        _val = raw.get(_key)
                        if _val is not None:
                            entry[_key] = _val
            except (json.JSONDecodeError, UnicodeDecodeError, OSError):
                pass  # 读取失败不影响列表返回

        # 精确筛选
        if agent_id and entry["agent_id"] != agent_id:
            continue
        if artifact_type and entry["artifact_type"] != artifact_type:
            continue
        if source_page and entry["source_page"] != source_page:
            continue

        # 关键词搜索（大小写不敏感，匹配 result.json 元数据字段）
        if q:
            q_lower = q.lower()
            searchable = " ".join(
                str(v or "") for v in [
                    entry.get("goal"),
                    entry.get("task_id"),
                    entry.get("agent_id"),
                    entry.get("artifact_type"),
                    entry.get("source_page"),
                ]
            ).lower()
            if q_lower not in searchable:
                continue

        tasks.append(entry)

    # 按 created_at 倒序
    tasks.sort(key=lambda t: t.get("created_at", ""), reverse=True)

    # 分页
    total = len(tasks)
    page = tasks[offset: offset + limit]
    has_more = (offset + limit) < total

    return {
        "tasks": page,
        "warnings": warnings,
        "total": total,
        "limit": limit,
        "offset": offset,
        "has_more": has_more,
    }


# ── 读取接口 ───────────────────────────────────────────────

@router.get("/tasks/{task_id}", summary="查询任务结果",
            description="返回 result.json 内容，含 raw_agent_result 摘要信息")
def get_task_result(task_id: str):
    json_path = OUTPUT_ROOT / task_id / "result.json"
    if not json_path.exists():
        raise HTTPException(status_code=404, detail=f"任务 {task_id} 不存在")
    with open(json_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    # 补充 raw_agent_result 信息
    raw_path = OUTPUT_ROOT / task_id / "raw_agent_result.json"
    data["has_raw_agent_result"] = raw_path.exists()
    if raw_path.exists():
        try:
            with open(raw_path, "r", encoding="utf-8") as f:
                raw = json.load(f)
            # 提取摘要：优先 summary，否则取 structured_output 前 200 字
            summary = raw.get("summary", "")
            if not summary:
                so = raw.get("structured_output") or raw.get("output") or {}
                summary = json.dumps(so, ensure_ascii=False)[:200] if so else ""
            data["agent_result_summary"] = summary
        except (json.JSONDecodeError, UnicodeDecodeError):
            data["agent_result_summary"] = ""

    return data


@router.get("/tasks/{task_id}/artifact", summary="读取产物内容",
            description="返回 Markdown 产物原文",
            response_class=PlainTextResponse)
def get_task_artifact(task_id: str):
    task_dir = OUTPUT_ROOT / task_id
    if not task_dir.exists():
        raise HTTPException(status_code=404, detail=f"任务 {task_id} 不存在")

    # 优先查找 xiaohongshu_pack.md，再查找 copy_pack.md，再查找 artifact.md
    for name in ["xiaohongshu_pack.md", "copy_pack.md", "artifact.md"]:
        md_path = task_dir / name
        if md_path.exists():
            return PlainTextResponse(md_path.read_text(encoding="utf-8"))

    raise HTTPException(status_code=404, detail=f"任务 {task_id} 产物文件不存在")


# ── 下载接口（Phase 2B）─────────────────────────────────────

def _validate_task_id(task_id: str) -> bool:
    """验证 task_id 防止路径穿越"""
    # 只允许字母、数字、下划线、连字符
    import re
    return bool(re.match(r'^[a-zA-Z0-9_-]+$', task_id))


@router.get("/tasks/{task_id}/download", summary="下载产物文件",
            description="下载指定任务的 artifact.md 文件",
            response_class=FileResponse)
def download_task_artifact(task_id: str):
    """下载指定任务的 artifact.md 文件"""
    # 防路径穿越
    if not _validate_task_id(task_id):
        raise HTTPException(status_code=400, detail="无效的 task_id")

    task_dir = OUTPUT_ROOT / task_id
    if not task_dir.exists():
        raise HTTPException(status_code=404, detail=f"任务 {task_id} 不存在")

    # 优先查找 xiaohongshu_pack.md，再查找 copy_pack.md，再查找 artifact.md
    for name in ["xiaohongshu_pack.md", "copy_pack.md", "artifact.md"]:
        md_path = task_dir / name
        if md_path.exists():
            # 安全检查：确保文件在预期目录内
            resolved_path = md_path.resolve()
            resolved_task_dir = task_dir.resolve()
            if not str(resolved_path).startswith(str(resolved_task_dir)):
                raise HTTPException(status_code=403, detail="路径越权")

            # 构建下载文件名
            download_filename = f"{task_id}.md"

            return FileResponse(
                path=str(md_path),
                media_type="text/markdown; charset=utf-8",
                filename=download_filename,
            )

    raise HTTPException(status_code=404, detail=f"任务 {task_id} 产物文件不存在")


# ── PDF 导出（Phase 5.1）─────────────────────────────────────

@router.get("/tasks/{task_id}/pdf", summary="导出产物为 PDF",
            description="将指定任务的 artifact.md 转换为 PDF 下载",
            response_class=FileResponse)
def export_task_pdf(task_id: str):
    """将指定任务的 artifact.md 导出为 PDF 文件"""
    from backend.services.pdf_service import export_artifact_pdf

    # 防路径穿越
    if not _validate_task_id(task_id):
        raise HTTPException(status_code=400, detail="无效的 task_id")

    task_dir = OUTPUT_ROOT / task_id
    if not task_dir.exists():
        raise HTTPException(status_code=404, detail=f"任务 {task_id} 不存在")

    # 优先查找 xiaohongshu_pack.md，再查找 copy_pack.md，再查找 artifact.md
    md_path = None
    for name in ["xiaohongshu_pack.md", "copy_pack.md", "artifact.md"]:
        candidate = task_dir / name
        if candidate.exists():
            md_path = candidate
            break

    if md_path is None:
        raise HTTPException(status_code=404, detail=f"任务 {task_id} 产物文件不存在")

    # 安全检查
    resolved_path = md_path.resolve()
    resolved_task_dir = task_dir.resolve()
    try:
        resolved_path.relative_to(resolved_task_dir)
    except ValueError:
        raise HTTPException(status_code=403, detail="路径越权")

    # 读取 markdown 内容
    markdown_content = md_path.read_text(encoding="utf-8")

    # 从 result.json 提取标题
    title = ""
    result_path = task_dir / "result.json"
    if result_path.exists():
        try:
            with open(result_path, "r", encoding="utf-8") as f:
                result_data = json.load(f)
            title = result_data.get("goal", "")[:80]
        except (json.JSONDecodeError, UnicodeDecodeError):
            pass

    # 生成 PDF
    pdf_path = export_artifact_pdf(task_id, markdown_content, title=title)

    # 确定 media type 和文件名
    if pdf_path.endswith(".pdf"):
        media_type = "application/pdf"
        download_filename = f"{task_id}.pdf"
    else:
        media_type = "text/html; charset=utf-8"
        download_filename = f"{task_id}.html"

    return FileResponse(
        path=pdf_path,
        media_type=media_type,
        filename=download_filename,
    )


# ── 任务对比 ─────────────────────────────────────────────────

COMPARE_FIELDS = [
    "task_id", "goal", "created_at", "artifact_type", "source_page",
    "agent_id", "ok", "mode", "summary",
]
COMPARE_RAW_FIELDS = [
    "succeeded", "failed", "total", "total_duration_ms",
    "handoff_enabled", "execution_mode",
]


def _read_task_summary(task_id: str) -> Dict[str, Any]:
    """读取单个 task 的 result.json + raw_agent_result.json 摘要"""
    if not _validate_task_id(task_id):
        raise HTTPException(status_code=400, detail=f"无效的 task_id: {task_id}")

    task_dir = OUTPUT_ROOT / task_id
    result_path = task_dir / "result.json"
    if not result_path.exists():
        raise HTTPException(status_code=404, detail=f"任务 {task_id} 不存在")

    with open(result_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    entry: Dict[str, Any] = {}
    for key in COMPARE_FIELDS:
        entry[key] = data.get(key)

    # 数值字段兜底
    if not entry.get("created_at"):
        mtime = os.path.getmtime(result_path)
        entry["created_at"] = datetime.fromtimestamp(mtime, tz=timezone.utc).isoformat()

    # 读取 raw_agent_result.json（Boss Lite/Graph 复盘字段）
    raw_path = task_dir / "raw_agent_result.json"
    for key in COMPARE_RAW_FIELDS:
        entry[key] = None
    if raw_path.exists():
        try:
            with open(raw_path, "r", encoding="utf-8") as rf:
                raw = json.load(rf)
            for key in COMPARE_RAW_FIELDS:
                val = raw.get(key)
                if val is not None:
                    entry[key] = val
        except (json.JSONDecodeError, UnicodeDecodeError, OSError):
            pass

    return entry


def _compute_diff(a: Dict[str, Any], b: Dict[str, Any]) -> Dict[str, Any]:
    """计算两个 task 摘要之间的结构化 diff"""
    diff: Dict[str, Any] = {}

    # goal
    diff["goal_changed"] = a.get("goal") != b.get("goal")
    if diff["goal_changed"]:
        diff["goal_diff"] = {"a": a.get("goal", ""), "b": b.get("goal", "")}

    # 数值差值
    for key in ("succeeded", "failed", "total", "total_duration_ms"):
        va = a.get(key)
        vb = b.get(key)
        if va is not None and vb is not None:
            diff[f"{key}_diff"] = vb - va
        else:
            diff[f"{key}_diff"] = None

    # 布尔/字符串 changed
    diff["handoff_changed"] = a.get("handoff_enabled") != b.get("handoff_enabled")
    diff["execution_mode_changed"] = a.get("execution_mode") != b.get("execution_mode")
    diff["artifact_type_changed"] = a.get("artifact_type") != b.get("artifact_type")
    diff["summary_changed"] = a.get("summary") != b.get("summary")

    return diff


@router.post("/tasks/compare", summary="对比两个任务",
             description="传入恰好 2 个 task_id，返回结构化对比结果")
def compare_tasks(request: CompareTasksRequest):
    task_ids = request.task_ids
    if len(task_ids) != 2:
        raise HTTPException(status_code=400, detail="恰好需要 2 个 task_id")
    if task_ids[0] == task_ids[1]:
        raise HTTPException(status_code=400, detail="请选择两个不同的任务进行对比")

    a = _read_task_summary(task_ids[0])
    b = _read_task_summary(task_ids[1])
    diff = _compute_diff(a, b)

    return {
        "ok": True,
        "tasks": [a, b],
        "diff": diff,
    }
