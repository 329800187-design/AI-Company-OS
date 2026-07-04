"""
Website Agent — 落地页文案智能体 (LLM-first)

Phase A5 核心变更:
  - run(task) 执行链路: _try_llm() → _rule_fallback()
  - LLM 成功: ok(fallback=false, source=llm), structured_output 包含完整落地页文案字段
  - LLM 失败: ok(fallback=true, source=template), warnings 非空, limitations 明确
  - 本阶段只生成结构化落地页文案和页面方案，不生成真实前端项目
  - 不接浏览器/爬虫/OpenClaw，不走旧 pipeline
  - 不做真实建站、不部署、不调用 OpenClaw

结构化产出字段:
  page_goal, target_audience, hero, sections, ctas, trust_elements,
  seo, design_direction, risks, recommendations, assumptions,
  limitations, content_type: "landing_page_copy"
"""
import json
import re
import uuid
from typing import Any, Dict, List, Optional

from agents.base_agent import BaseAgent


# ── LLM System Prompt ────────────────────────────────────────────

LANDING_PAGE_LLM_SYSTEM = """You are an expert landing page copywriter and conversion strategist.
Convert user requests into structured, high-converting landing page copy and page plan.

You MUST output valid JSON with these fields:
{
  "page_goal": "the primary goal of this landing page (e.g. collect leads, sell product, book demo)",
  "target_audience": "detailed target audience description (who they are, pain points, desires)",
  "hero": {
    "headline": "main headline (under 10 words, punchy and clear)",
    "subheadline": "supporting line (20-40 words, explain the value proposition)",
    "primary_cta": "primary button text (3-6 words, action-oriented)"
  },
  "sections": [
    {
      "title": "section title",
      "content": "section copy (50-150 words, persuasive)",
      "cta": "optional section-level CTA text, or null"
    }
  ],
  "ctas": {
    "primary": "main CTA text and placement strategy",
    "secondary": "secondary CTA if applicable",
    "exit_intent": "exit-intent popup CTA suggestion"
  },
  "trust_elements": [
    "list of trust signals to include (testimonials, logos, guarantees, stats, certifications)"
  ],
  "seo": {
    "title": "SEO title tag (50-60 chars)",
    "description": "meta description (150-160 chars)",
    "keywords": ["keyword1", "keyword2", "keyword3"]
  },
  "design_direction": "specific design suggestions (colors, typography, layout, imagery style, whitespace)",
  "risks": ["potential conversion risks or challenges for this page"],
  "recommendations": ["actionable recommendations to improve conversion"],
  "assumptions": ["assumptions made during copy generation"],
  "limitations": ["limitations of this copy, things that need real data or A/B testing"]
}

Rules:
1. Output in the same language as the user's input (Chinese input → Chinese output, English → English)
2. Headlines must be punchy, clear, and benefit-focused
3. All fields must be present even if brief
4. sections should have 3-5 sections minimum
5. trust_elements should include at least 3 specific signals
6. recommendations should be actionable and specific
7. Output ONLY the JSON object, no extra text"""


# ── 标准化模板字段 ──────────────────────────────────────────────

WEBSITE_OUTPUT_FIELDS = {
    "page_goal": "",
    "target_audience": "",
    "hero": {
        "headline": "",
        "subheadline": "",
        "primary_cta": "立即了解",
    },
    "sections": [],
    "ctas": {
        "primary": "",
        "secondary": "",
        "exit_intent": "",
    },
    "trust_elements": [],
    "seo": {
        "title": "",
        "description": "",
        "keywords": [],
    },
    "design_direction": "",
    "risks": [],
    "recommendations": [],
    "assumptions": [],
    "limitations": [],
    "content_type": "landing_page_copy",
}


# ── 辅助函数 ────────────────────────────────────────────────────

def _extract_topic(text: str, max_len: int = 20) -> str:
    """从文本中提取主题词"""
    stopwords = {"帮我", "请", "写", "生成", "一个", "一份", "的", "和", "与", "了", "想要", "需要"}
    for sw in stopwords:
        text = text.replace(sw, " ")
    words = [w for w in text.split() if len(w) >= 2]
    topic = " ".join(words[:4]) if words else text[:30]
    return topic[:max_len]


def _extract_json(text: str) -> Optional[Dict]:
    """从 LLM 回复中提取 JSON"""
    text = re.sub(r"```(?:json)?\s*", "", text).replace("```", "").strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        match = re.search(r"\{[\s\S]*\}", text)
        if match:
            try:
                return json.loads(match.group())
            except json.JSONDecodeError:
                pass
    return None


# ── WebsiteAgent ────────────────────────────────────────────────

class WebsiteAgent(BaseAgent):
    """Website Agent — LLM-first 落地页文案生成"""

    AGENT_ID = "website"
    DISPLAY_NAME = "网站落地页"
    CAPABILITIES = ["website_draft", "landing_page", "product_page", "squeeze_page"]
    TASK_TYPES = ["website_draft", "landing_page", "product_page", "squeeze_page", "coming_soon"]

    def __init__(self, api_key: Optional[str] = None, timeout: int = 90):
        super().__init__(name="website", timeout=timeout)
        self.api_key = api_key or ""

    # ── 主入口 ──────────────────────────────────────────────────

    def run(self, task: Dict[str, Any]) -> Dict[str, Any]:
        task_id = task.get("task_id", f"web_{uuid.uuid4().hex[:8]}")
        task_type = task.get("task_type", "website_draft")
        goal = task.get("goal", "")

        if not goal:
            return self.fail(
                task_id=task_id,
                error="缺少目标描述，请提供网站需求",
            )

        # 第一步: 尝试 LLM 生成
        llm_result = self._try_llm(task_id, goal, task_type)
        if llm_result is not None:
            return llm_result

        # 第二步: 模板/规则降级
        return self._rule_fallback(task_id, goal, task_type)

    # ── LLM 生成 (LLM-first) ──────────────────────────────────

    def _try_llm(self, task_id: str, goal: str, task_type: str) -> Optional[Dict]:
        """尝试通过 LLM 生成落地页文案"""
        try:
            resp = self.call_ai(
                message=f"为以下需求生成落地页文案和页面方案：\n{goal}\n\n页面类型: {task_type}",
                system=LANDING_PAGE_LLM_SYSTEM,
                temperature=0.7,
                max_tokens=3000,
            )

            if not resp.get("ok"):
                self.logger.warning(f"[Website Agent] LLM 调用失败: {resp.get('error')}")
                return None

            reply = resp.get("reply", "")
            parsed = _extract_json(reply)

            if parsed is None:
                self.logger.warning("[Website Agent] LLM 返回无效 JSON，使用 fallback")
                return None

            # 规范化: 补齐缺失字段
            normalized = self._normalize_llm_output(parsed, goal, task_type)

            # 构建 AgentRunResult 格式
            return self.ok(
                task_id,
                status="LLM 落地页文案生成完成",
                data=normalized,
                meta={
                    "fallback": False,
                    "source": "llm",
                    "model": resp.get("model", ""),
                },
            )

        except Exception as e:
            self.logger.error(f"[Website Agent] LLM 异常: {e}")
            return None

    # ── 模板/规则降级 ──────────────────────────────────────────

    def _rule_fallback(self, task_id: str, goal: str, task_type: str) -> Dict:
        """模板/规则降级 — 本地规则生成落地页文案框架"""
        topic = _extract_topic(goal)
        page_type = task_type if task_type in (
            "landing_page", "product_page", "squeeze_page", "coming_soon"
        ) else "landing_page"

        output = {
            "page_goal": f"为 {topic} 生成高转化落地页，吸引目标用户采取行动",
            "target_audience": f"对 {topic} 感兴趣的通用用户（模板推测，需真实用户调研确认）",
            "hero": {
                "headline": f"{topic} — 一句话打动你",
                "subheadline": f"专业{topic}解决方案，让选择更简单。配置 AI API 获得定制文案。",
                "primary_cta": "立即体验",
            },
            "sections": [
                {
                    "title": "为什么选择我们",
                    "content": f"我们专注于{topic}领域，提供专业、高效的服务。{chr(10)}（此为模板内容，配置 AI API 获得定制文案）",
                    "cta": None,
                },
                {
                    "title": "核心优势",
                    "content": "专业团队 / 定制方案 / 快速交付 / 持续支持。（模板内容）",
                    "cta": None,
                },
                {
                    "title": "客户评价",
                    "content": '"非常满意，服务很专业！" -- 模板示例客户',
                    "cta": None,
                },
            ],
            "ctas": {
                "primary": "页面顶部和底部各放一个主 CTA 按钮，文案'立即体验'",
                "secondary": "中间 section 可放'了解更多'次要 CTA",
                "exit_intent": "弹窗提示'别走！免费体验一次'",
            },
            "trust_elements": [
                "客户评价（需真实数据）",
                "合作品牌 logo（需真实数据）",
                "数据统计（如服务客户数，需真实数据）",
                "安全保障/退款承诺",
            ],
            "seo": {
                "title": f"{topic} — 专业解决方案 | 落地页模板",
                "description": f"了解我们的{topic}服务，助您快速实现目标。模板草稿，配置 AI API 获得优化 SEO 内容。",
                "keywords": [topic, "解决方案", "专业服务", "落地页"],
            },
            "design_direction": "建议使用简洁现代风格，主色调根据品牌选择。Hero 区域使用高质量配图，CTA 按钮使用对比色突出。保持充足留白。",
            "risks": [
                "模板内容缺乏差异化，转化率可能较低",
                "未基于真实用户数据，文案可能不精准",
                "SEO 关键词未做竞争分析",
            ],
            "recommendations": [
                "配置 AI API Key 获得定制化文案",
                "补充真实客户评价和品牌素材",
                "进行 A/B 测试优化 CTA 文案",
                "接入真实用户行为数据分析",
            ],
            "assumptions": [
                "假设目标用户为通用人群，需真实用户画像确认",
                "假设页面类型为标准落地页",
                "当前为模板草稿，未做竞品分析",
            ],
            "limitations": [
                "当前为模板/规则降级产物，非真实 LLM 生成",
                "未部署网站，仅为文案草稿",
                "未调用浏览器/OpenClaw，不做真实竞品抓取",
                "配置 AI API 后可获得定制化内容",
            ],
            "content_type": "landing_page_copy",
        }

        warnings = [
            "当前为模板/规则降级产物，非真实 LLM 生成",
            "未配置 LLM API 或 LLM 调用失败，使用本地规则生成",
            "本阶段只生成结构化落地页文案，不生成真实前端项目、不部署、不调用浏览器/OpenClaw",
        ]

        return self.ok(
            task_id,
            status="模板降级生成完成",
            data=output,
            meta={
                "fallback": True,
                "source": "template",
                "fallback_reason": "LLM 不可用或返回无效结果",
            },
        ) | {"warnings": warnings}

    # ── 辅助方法 ────────────────────────────────────────────────

    def _normalize_llm_output(self, parsed: Dict, goal: str, task_type: str) -> Dict:
        """规范化 LLM 输出，补齐缺失字段"""
        topic = _extract_topic(goal)
        output = dict(WEBSITE_OUTPUT_FIELDS)

        # 逐字段覆盖（LLM 返回的非空值优先）
        for key in WEBSITE_OUTPUT_FIELDS:
            if key in parsed and parsed[key]:
                output[key] = parsed[key]

        # 确保 hero 结构完整
        if isinstance(output["hero"], dict):
            for hkey in ("headline", "subheadline", "primary_cta"):
                if hkey not in output["hero"] or not output["hero"][hkey]:
                    output["hero"][hkey] = WEBSITE_OUTPUT_FIELDS["hero"].get(hkey, "")
        else:
            output["hero"] = WEBSITE_OUTPUT_FIELDS["hero"]

        # 确保 seo 结构完整
        if isinstance(output["seo"], dict):
            for skey in ("title", "description", "keywords"):
                if skey not in output["seo"] or not output["seo"][skey]:
                    output["seo"][skey] = WEBSITE_OUTPUT_FIELDS["seo"].get(skey, "" if skey != "keywords" else [])
        else:
            output["seo"] = WEBSITE_OUTPUT_FIELDS["seo"]

        # 确保 ctas 结构完整
        if isinstance(output["ctas"], dict):
            for ckey in ("primary", "secondary", "exit_intent"):
                if ckey not in output["ctas"] or not output["ctas"][ckey]:
                    output["ctas"][ckey] = WEBSITE_OUTPUT_FIELDS["ctas"].get(ckey, "")
        else:
            output["ctas"] = WEBSITE_OUTPUT_FIELDS["ctas"]

        # 确保 sections 是列表
        if not isinstance(output["sections"], list):
            output["sections"] = []

        # 确保列表字段是列表
        for list_key in ("trust_elements", "risks", "recommendations", "assumptions", "limitations"):
            if not isinstance(output[list_key], list):
                output[list_key] = []

        # 确保 content_type 固定
        output["content_type"] = "landing_page_copy"

        return output
