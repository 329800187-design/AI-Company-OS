"""DeliverySpec — 可复用的最小文案交付规格"""
import re
from pydantic import BaseModel, Field
from typing import List, Optional


class DeliverySpec(BaseModel):
    """文案交付规格"""
    platform: str = "xiaohongshu"  # "xiaohongshu" | "douyin"
    product: str = ""
    artifact_type: str = "copy_pack"
    requirements: List[str] = Field(default_factory=list)
    original_goal: str = ""


# ── 需求关键词映射 ──────────────────────────────────────────

_REQUIREMENT_MAP = [
    (["开头钩子", "钩子"], "hook"),
    (["卖点"], "selling_points"),
    (["使用场景", "场景"], "use_scenarios"),
    (["互动"], "engagement"),
    (["行动号召", "CTA", "cta"], "cta"),
]

# ── 产品提取正则 ────────────────────────────────────────────

_PRODUCT_PATTERNS = [
    # "用于推广XXX" / "推广XXX"
    r"推广(.+?)(?:，|,|。|；|;|的|文案|内容|模板|要求|包含|$)",
    # "为XXX生成" / "帮XXX生成"
    r"为(.+?)生成",
    # "关于XXX的"
    r"关于(.+?)的",
    # "XXX文案" / "XXX推广" — 从 goal 开头提取
    r"^[一-鿿]+(?=文案|推广|种草|模板)",
]

# ── 平台识别 ────────────────────────────────────────────────

_PLATFORM_KEYWORDS = {
    "douyin": ["抖音", "短视频"],
    "xiaohongshu": ["小红书"],
}


def _extract_product(goal: str) -> str:
    """从中文 goal 中提取产品/品类。"""
    for pattern in _PRODUCT_PATTERNS:
        matches = re.findall(pattern, goal)
        if matches:
            product = matches[0].strip(" 的文案推广种草模板")
            if len(product) >= 2:
                return product

    # fallback: 提取 goal 中的中文片段，清理噪音词
    noise = {"请", "帮我", "生成", "一个", "一份", "一套", "的", "文案", "模板",
             "种草", "推广", "用于", "要求", "包含", "内容", "产品", "品牌"}
    words = re.findall(r"[一-鿿]+", goal)
    meaningful = [w for w in words if w not in noise and len(w) >= 2]
    if meaningful:
        return meaningful[0][:30]

    # 最终 fallback: goal 前 30 字符
    cleaned = re.sub(r"[^一-鿿]", "", goal)
    return cleaned[:30] if cleaned else goal[:30]


def _detect_platform(goal: str) -> str:
    """从 goal 中推断平台。"""
    for platform, keywords in _PLATFORM_KEYWORDS.items():
        if any(kw in goal for kw in keywords):
            return platform
    return "xiaohongshu"


def _extract_requirements(goal: str) -> List[str]:
    """从 goal 中粗略提取需求标签。"""
    reqs: List[str] = []
    for keywords, tag in _REQUIREMENT_MAP:
        if any(kw in goal for kw in keywords):
            reqs.append(tag)
    return reqs


def parse_delivery_spec(
    goal: str,
    platform: Optional[str] = None,
    artifact_type: Optional[str] = None,
) -> DeliverySpec:
    """
    解析 goal，构建 DeliverySpec。

    优先级：显式参数 > goal 推断 > 默认值
    """
    detected_platform = platform or _detect_platform(goal)
    product = _extract_product(goal)
    requirements = _extract_requirements(goal)

    return DeliverySpec(
        platform=detected_platform,
        product=product,
        artifact_type=artifact_type or "copy_pack",
        requirements=requirements,
        original_goal=goal,
    )
