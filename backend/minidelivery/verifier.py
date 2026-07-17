"""验收器 — 支持多平台的 Markdown 产物校验"""
import os
import re
from typing import List, Optional, Tuple

from .models import VerificationChecks
from .spec import DeliverySpec, parse_delivery_spec


_PLACEHOLDER_PATTERNS = [
    "{{产品}}", "{product}", "产品}}", "{{product}}",
    "{{品类}}", "{品类}", "品类}}",
]


def verify_artifact(
    md_path: str,
    goal: str,
    spec: Optional[DeliverySpec] = None,
) -> Tuple[VerificationChecks, List[str]]:
    """
    对生成的 Markdown 文件进行严格验收。

    兼容旧调用：spec=None 时自动从 goal 解析。
    返回 (checks, failed_checks_list)
    """
    if spec is None:
        spec = parse_delivery_spec(goal)

    checks = VerificationChecks()
    failed: List[str] = []

    # ── 通用检查 ──────────────────────────────────────────────

    # 1. 文件必须真实存在
    if os.path.exists(md_path):
        checks.file_exists = True
    else:
        failed.append("file_not_found")
        return checks, failed

    # 2. 文件大小 > 300 bytes
    file_size = os.path.getsize(md_path)
    if file_size > 300:
        checks.file_size_ok = True
    else:
        failed.append(f"file_too_small({file_size}bytes)")

    # 读取内容
    with open(md_path, "r", encoding="utf-8") as f:
        content = f.read()

    # 3. 正文长度至少 120 中文字符
    chinese_chars = re.findall(r"[一-鿿]", content)
    if len(chinese_chars) >= 120:
        checks.has_body_text = True
        checks.body_length_ok = True
    else:
        failed.append(f"body_too_short({len(chinese_chars)}chinese_chars)")

    # 4. 必须包含 spec.product
    product = spec.product
    if product and product in content:
        checks.contains_goal_keyword = True
    else:
        # fallback: 从 goal 中提取关键词检查
        goal_words = re.findall(r"[一-鿿]{2,}", goal)
        if any(w in content for w in goal_words if len(w) >= 2):
            checks.contains_goal_keyword = True
        else:
            failed.append(f"missing_product({product})")

    # 5. 不允许包含未替换占位符
    has_placeholder = any(ph in content for ph in _PLACEHOLDER_PATTERNS)
    if not has_placeholder:
        checks.no_placeholders = True
    else:
        failed.append("contains_placeholders")

    # 6. 必须包含行动号召
    cta_keywords = ["行动", "号召", "立即", "快来", "点击", "关注", "收藏", "购买",
                     "下单", "加入", "领取", "体验", "CTA", "引导"]
    if any(kw in content for kw in cta_keywords):
        checks.has_cta = True
    else:
        failed.append("no_cta")

    # 7. 必须包含发布建议
    publish_keywords = ["发布", "建议", "时间", "频率", "封面", "图片", "排版",
                         "最佳时间", "注意事项", "发布技巧"]
    if any(kw in content for kw in publish_keywords):
        checks.has_publish_tips = True
    else:
        failed.append("no_publish_tips")

    # ── 平台特定检查 ──────────────────────────────────────────

    if spec.platform == "xiaohongshu":
        _verify_xhs(content, checks, failed)
    elif spec.platform == "douyin":
        _verify_douyin(content, checks, failed)

    return checks, failed


def _verify_xhs(content: str, checks: VerificationChecks, failed: List[str]):
    """小红书平台专项检查"""
    # 标题数量 >=3
    title_pattern = re.compile(r"(?:^#{1,3}\s+.+|^\*\*.+\*\*$)", re.MULTILINE)
    titles = title_pattern.findall(content)
    if len(titles) >= 3:
        checks.has_titles = True
        checks.title_count_ok = True
    else:
        failed.append(f"titles_insufficient({len(titles)}/3)")

    # 话题标签 >=5
    hashtags = re.findall(r"#\S+", content)
    if len(hashtags) >= 5:
        checks.has_hashtags = True
        checks.hashtag_count_ok = True
    else:
        failed.append(f"hashtags_insufficient({len(hashtags)}/5)")

    # 必须有人群/受众/目标用户类内容
    audience_keywords = ["人群", "受众", "目标用户", "适合", "谁", "人群画像", "用户画像"]
    if any(kw in content for kw in audience_keywords):
        checks.has_target_audience = True
    else:
        failed.append("no_target_audience")


def _verify_douyin(content: str, checks: VerificationChecks, failed: List[str]):
    """抖音平台专项检查"""
    # 开头钩子
    if "钩子" in content or "开头" in content:
        checks.has_hook = True
    else:
        failed.append("no_hook")

    # 分镜/脚本/口播
    if any(kw in content for kw in ["分镜", "脚本", "口播"]):
        checks.has_script = True
    else:
        failed.append("no_script")

    # 卖点
    if "卖点" in content:
        checks.has_selling_points = True
    else:
        failed.append("no_selling_points")

    # 使用场景
    if "场景" in content:
        checks.has_use_scenarios = True
    else:
        failed.append("no_use_scenarios")

    # 互动
    if "互动" in content:
        checks.has_engagement = True
    else:
        failed.append("no_engagement")


# ── 图片提示词包验收 ──────────────────────────────────────────

def verify_image_prompt_pack(
    md_path: str,
    goal: str,
    spec: Optional[DeliverySpec] = None,
) -> Tuple[VerificationChecks, List[str]]:
    """
    对生成的图片提示词包 Markdown 文件进行验收。

    返回 (checks, failed_checks_list)
    """
    if spec is None:
        spec = parse_delivery_spec(goal)

    checks = VerificationChecks()
    failed: List[str] = []

    # 1. 文件必须真实存在
    if os.path.exists(md_path):
        checks.file_exists = True
    else:
        failed.append("file_not_found")
        return checks, failed

    # 2. 文件大小 > 300 bytes
    file_size = os.path.getsize(md_path)
    if file_size > 300:
        checks.file_size_ok = True
    else:
        failed.append(f"file_too_small({file_size}bytes)")

    # 读取内容
    with open(md_path, "r", encoding="utf-8") as f:
        content = f.read()

    # 3. 必须包含产品名
    product = spec.product
    if product and product in content:
        checks.contains_goal_keyword = True
    else:
        goal_words = re.findall(r"[一-鿿]{2,}", goal)
        if any(w in content for w in goal_words if len(w) >= 2):
            checks.contains_goal_keyword = True
        else:
            failed.append(f"missing_product({product})")

    # 4. 不允许包含未替换占位符
    has_placeholder = any(ph in content for ph in _PLACEHOLDER_PATTERNS)
    if not has_placeholder:
        checks.no_placeholders = True
    else:
        failed.append("contains_placeholders")

    # 5. 必须包含主图提示词
    if "主图提示词" in content or "主图" in content:
        checks.has_main_prompt = True
    else:
        failed.append("no_main_prompt")

    # 6. 必须包含细节图提示词
    if "细节图提示词" in content or "细节图" in content:
        checks.has_detail_prompt = True
    else:
        failed.append("no_detail_prompt")

    # 7. 必须包含场景图提示词
    if "场景图提示词" in content or "场景图" in content:
        checks.has_scene_prompt = True
    else:
        failed.append("no_scene_prompt")

    # 8. 必须包含负面提示词
    if "负面提示词" in content or "Negative" in content:
        checks.has_negative_prompt = True
    else:
        failed.append("no_negative_prompt")

    # 9. 必须包含使用建议
    if "使用建议" in content or "使用技巧" in content:
        checks.has_usage_tips = True
    else:
        failed.append("no_usage_tips")

    return checks, failed


# ── 调研简报验收 ──────────────────────────────────────────────

def verify_research_brief(
    md_path: str,
    goal: str,
    spec: Optional[DeliverySpec] = None,
) -> Tuple[VerificationChecks, List[str]]:
    """
    对生成的调研简报 Markdown 文件进行验收。

    返回 (checks, failed_checks_list)
    """
    if spec is None:
        spec = parse_delivery_spec(goal)

    checks = VerificationChecks()
    failed: List[str] = []

    # 1. 文件必须真实存在
    if os.path.exists(md_path):
        checks.file_exists = True
    else:
        failed.append("file_not_found")
        return checks, failed

    # 2. 文件大小 > 300 bytes
    file_size = os.path.getsize(md_path)
    if file_size > 300:
        checks.file_size_ok = True
    else:
        failed.append(f"file_too_small({file_size}bytes)")

    # 读取内容
    with open(md_path, "r", encoding="utf-8") as f:
        content = f.read()

    # 3. 必须包含产品名
    product = spec.product
    if product and product in content:
        checks.contains_goal_keyword = True
    else:
        goal_words = re.findall(r"[一-鿿]{2,}", goal)
        if any(w in content for w in goal_words if len(w) >= 2):
            checks.contains_goal_keyword = True
        else:
            failed.append(f"missing_product({product})")

    # 4. 不允许包含未替换占位符
    has_placeholder = any(ph in content for ph in _PLACEHOLDER_PATTERNS)
    if not has_placeholder:
        checks.no_placeholders = True
    else:
        failed.append("contains_placeholders")

    # 5. 必须包含调研目标
    if "调研目标" in content or "核心问题" in content:
        checks.has_research_goal = True
    else:
        failed.append("no_research_goal")

    # 6. 必须包含目标用户
    if "目标用户" in content or "用户画像" in content:
        checks.has_target_users = True
    else:
        failed.append("no_target_users")

    # 7. 必须包含竞品维度
    if "竞品维度" in content or "竞品" in content:
        checks.has_competitor_dimensions = True
    else:
        failed.append("no_competitor_dimensions")

    # 8. 必须包含用户痛点假设
    if "痛点" in content or "假设" in content:
        checks.has_pain_points = True
    else:
        failed.append("no_pain_points")

    # 9. 必须包含内容机会
    if "内容机会" in content or "内容方向" in content:
        checks.has_content_opportunities = True
    else:
        failed.append("no_content_opportunities")

    # 10. 必须包含风险提醒
    if "风险" in content or "提醒" in content:
        checks.has_risk_warnings = True
    else:
        failed.append("no_risk_warnings")

    # 11. 必须包含下一步建议
    if "下一步" in content or "建议" in content:
        checks.has_next_steps = True
    else:
        failed.append("no_next_steps")

    return checks, failed


# ── 落地页文案验收 ──────────────────────────────────────────────

def verify_landing_page_copy(
    md_path: str,
    goal: str,
    spec: Optional[DeliverySpec] = None,
) -> Tuple[VerificationChecks, List[str]]:
    """
    对生成的落地页文案 Markdown 文件进行验收。

    返回 (checks, failed_checks_list)
    """
    if spec is None:
        spec = parse_delivery_spec(goal)

    checks = VerificationChecks()
    failed: List[str] = []

    # 1. 文件必须真实存在
    if os.path.exists(md_path):
        checks.file_exists = True
    else:
        failed.append("file_not_found")
        return checks, failed

    # 2. 文件大小 > 300 bytes
    file_size = os.path.getsize(md_path)
    if file_size > 300:
        checks.file_size_ok = True
    else:
        failed.append(f"file_too_small({file_size}bytes)")

    # 读取内容
    with open(md_path, "r", encoding="utf-8") as f:
        content = f.read()

    # 3. 必须包含产品名
    product = spec.product
    if product and product in content:
        checks.contains_goal_keyword = True
    else:
        goal_words = re.findall(r"[一-鿿]{2,}", goal)
        if any(w in content for w in goal_words if len(w) >= 2):
            checks.contains_goal_keyword = True
        else:
            failed.append(f"missing_product({product})")

    # 4. 不允许包含未替换占位符
    has_placeholder = any(ph in content for ph in _PLACEHOLDER_PATTERNS)
    if not has_placeholder:
        checks.no_placeholders = True
    else:
        failed.append("contains_placeholders")

    # 5. 必须包含页面定位
    if "页面定位" in content or "核心定位" in content:
        checks.has_page_positioning = True
    else:
        failed.append("no_page_positioning")

    # 6. 必须包含首屏标题
    if "首屏标题" in content or "主标题" in content:
        checks.has_hero_title = True
    else:
        failed.append("no_hero_title")

    # 7. 必须包含副标题
    if "副标题" in content:
        checks.has_subtitle = True
    else:
        failed.append("no_subtitle")

    # 8. 必须包含核心卖点
    if "核心卖点" in content or "卖点" in content:
        checks.has_selling_points = True
    else:
        failed.append("no_selling_points")

    # 9. 必须包含目标用户
    if "目标用户" in content or "用户画像" in content:
        checks.has_target_users = True
    else:
        failed.append("no_target_users")

    # 10. 必须包含页面结构
    if "页面结构" in content or "Section" in content:
        checks.has_page_structure = True
    else:
        failed.append("no_page_structure")

    # 11. 必须包含 CTA 文案
    if "CTA" in content or "行动号召" in content or "立即购买" in content:
        checks.has_cta = True
    else:
        failed.append("no_cta")

    # 12. 必须包含 FAQ
    if "FAQ" in content or "常见问题" in content:
        checks.has_faq = True
    else:
        failed.append("no_faq")

    # 13. 必须包含视觉建议
    if "视觉建议" in content or "视觉" in content:
        checks.has_visual_suggestions = True
    else:
        failed.append("no_visual_suggestions")

    return checks, failed


# ── 数据分析报告验收 ──────────────────────────────────────────────

def verify_data_report(
    md_path: str,
    goal: str,
    spec: Optional[DeliverySpec] = None,
) -> Tuple[VerificationChecks, List[str]]:
    """
    对生成的数据分析报告 Markdown 文件进行验收。

    返回 (checks, failed_checks_list)
    """
    if spec is None:
        spec = parse_delivery_spec(goal)

    checks = VerificationChecks()
    failed: List[str] = []

    # 1. 文件必须真实存在
    if os.path.exists(md_path):
        checks.file_exists = True
    else:
        failed.append("file_not_found")
        return checks, failed

    # 2. 文件大小 > 300 bytes
    file_size = os.path.getsize(md_path)
    if file_size > 300:
        checks.file_size_ok = True
    else:
        failed.append(f"file_too_small({file_size}bytes)")

    # 读取内容
    with open(md_path, "r", encoding="utf-8") as f:
        content = f.read()

    # 3. 必须包含产品名
    product = spec.product
    if product and product in content:
        checks.contains_goal_keyword = True
    else:
        goal_words = re.findall(r"[一-鿿]{2,}", goal)
        if any(w in content for w in goal_words if len(w) >= 2):
            checks.contains_goal_keyword = True
        else:
            failed.append(f"missing_product({product})")

    # 4. 不允许包含未替换占位符
    has_placeholder = any(ph in content for ph in _PLACEHOLDER_PATTERNS)
    if not has_placeholder:
        checks.no_placeholders = True
    else:
        failed.append("contains_placeholders")

    # 5. 必须包含分析目标
    if "分析目标" in content or "核心问题" in content:
        checks.has_analysis_goal = True
    else:
        failed.append("no_analysis_goal")

    # 6. 必须包含数据范围假设
    if "数据范围" in content or "假设" in content:
        checks.has_data_scope = True
    else:
        failed.append("no_data_scope")

    # 7. 必须包含核心指标
    if "核心指标" in content or "指标" in content:
        checks.has_core_metrics = True
    else:
        failed.append("no_core_metrics")

    # 8. 必须包含趋势观察
    if "趋势" in content or "观察" in content:
        checks.has_trend_observations = True
    else:
        failed.append("no_trend_observations")

    # 9. 必须包含异常点检查
    if "异常" in content or "检查" in content:
        checks.has_anomaly_checks = True
    else:
        failed.append("no_anomaly_checks")

    # 10. 必须包含业务解释
    if "业务解释" in content or "业务逻辑" in content:
        checks.has_business_interpretation = True
    else:
        failed.append("no_business_interpretation")

    # 11. 必须包含行动建议
    if "行动建议" in content or "建议" in content:
        checks.has_action_recommendations = True
    else:
        failed.append("no_action_recommendations")

    # 12. 必须包含后续需要补充的数据
    if "补充" in content or "后续" in content or "数据" in content:
        checks.has_supplementary_data = True
    else:
        failed.append("no_supplementary_data")

    return checks, failed
