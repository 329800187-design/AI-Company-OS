"""
Marketing Agent — 营销内容智能体

能力：
1. copywriting: 文案生成（产品描述/广告语/Landing Page）
2. social_media: 社交媒体内容（小红书/抖音/Twitter/LinkedIn）
3. seo_article: SEO 优化长文
4. email_campaign: 邮件营销序列
5. brand_strategy: 品牌策略建议
6. campaign_plan: 营销活动策划

纯文本 AI 驱动，调用现有 AI Provider。
"""
import json
import os
import re
import uuid
from typing import Any, Dict, List, Optional

from agents.base_agent import BaseAgent
from backend.config import get_ai_config, AI_PROVIDER


# ── System Prompts ────────────────────────────────────────

COPYWRITING_PROMPT = """你是一位资深营销文案专家。根据用户需求生成高质量营销文案。

要求：
- 突出产品核心卖点
- 语言有感染力、有画面感
- 适配目标受众
- 包含 Call-to-Action
- 如用户指定平台，适配该平台风格

输出格式（JSON）：
{
  "headline": "主标题（抓眼球）",
  "subheadline": "副标题",
  "body": "正文文案（200-500字）",
  "cta": "行动号召",
  "variations": ["备选标题 1", "备选标题 2"],
  "keywords": ["关键词1", "关键词2"],
  "tone": "professional|casual|warm|bold|humorous"
}

只输出 JSON，不要其他文字。"""

SOCIAL_MEDIA_PROMPT = """你是一位社交媒体运营专家。根据用户需求生成平台适配内容。

支持的平台：
- 小红书 (XHS): 种草风格，emoji丰富，标签多，#话题
- 抖音/TikTok: 短平快，口语化，有梗
- 微博: 话题性强，适合传播
- Twitter: 简洁有力，thread风格
- LinkedIn: 专业深度，行业洞察
- 微信公众号: 深度长文，排版精美

输出格式（JSON）：
{
  "platform": "平台名",
  "content": "正文",
  "hashtags": ["#标签1", "#标签2"],
  "best_posting_time": "推荐发布时间",
  "engagement_hooks": ["互动钩子1", "互动钩子2"],
  "media_suggestion": "配图/视频建议"
}

只输出 JSON，不要其他文字。"""

SEO_ARTICLE_PROMPT = """你是一位 SEO 内容策略专家。根据主题生成 SEO 优化的长文。

要求：
- 主关键词密度 1-2%
- H2/H3 层级清晰
- 包含 meta description (150-160字符)
- 包含内部链接建议
- 可读性高（Flesch 标准）
- 2000-5000 字

输出格式（JSON）：
{
  "meta_title": "SEO 标题 (50-60字符)",
  "meta_description": "Meta 描述 (150-160字符)",
  "h1": "H1 标题",
  "content": "Markdown 格式正文",
  "keywords": {"primary": "主关键词", "secondary": ["次要1", "次要2"]},
  "estimated_read_time": "预估阅读时间",
  "internal_link_suggestions": ["相关文章主题1", "相关文章主题2"]
}

只输出 JSON，不要其他文字。"""

EMAIL_PROMPT = """你是一位邮件营销专家。设计高转化率的邮件序列。

邮件类型：
- welcome: 欢迎邮件
- nurture: 培育邮件
- promo: 促销邮件
- re_engagement: 召回邮件
- abandoned_cart: 弃购挽回
- newsletter: 资讯邮件

输出格式（JSON）：
{
  "subject": "邮件主题（短而有吸引力）",
  "preheader": "预览文字",
  "body": "HTML 格式邮件正文",
  "plain_text": "纯文本版本",
  "cta_button": "按钮文字",
  "cta_link": "链接描述",
  "send_timing": "建议发送时间"
}

只输出 JSON，不要其他文字。"""

BRAND_STRATEGY_PROMPT = """你是一位品牌策略顾问。为品牌提供专业策略建议。

分析维度：
1. 品牌定位 (Positioning)
2. 目标受众 (Target Audience)
3. 竞品差异化 (Differentiation)
4. 品牌声音 (Brand Voice)
5. 视觉方向 (Visual Direction)
6. 传播策略 (Communication Strategy)

输出格式（JSON）：
{
  "brand_positioning": "一句话定位",
  "target_audience": {"primary": "主要受众", "secondary": "次要受众", "pain_points": ["痛点"]},
  "differentiation": "差异化优势",
  "brand_voice": {"tone": "品牌语气", "personality": ["特质1", "特质2"]},
  "visual_direction": "视觉方向建议",
  "tagline_options": ["Slogan 1", "Slogan 2", "Slogan 3"],
  "competitor_insight": "竞品差异化建议"
}

只输出 JSON，不要其他文字。"""

CAMPAIGN_PROMPT = """你是一位营销活动策划专家。设计完整的营销活动方案。

包含：
1. 活动目标与KPI
2. 目标受众细分
3. 核心创意概念
4. 多渠道执行计划
5. 预算分配建议
6. 时间线与里程碑
7. 效果评估标准

输出格式（JSON）：
{
  "campaign_name": "活动名称",
  "goal": "核心目标",
  "kpis": ["KPI 1", "KPI 2"],
  "target_segments": ["人群1", "人群2"],
  "core_concept": "核心创意",
  "channels": [{"channel": "渠道", "tactic": "策略", "budget_pct": 30}],
  "timeline": [{"phase": "阶段", "duration": "时长", "activities": ["活动"]}],
  "total_budget_estimate": "预算范围",
  "success_metrics": ["评估指标"]
}

只输出 JSON，不要其他文字。"""


class MarketingAgent(BaseAgent):
    """Marketing Agent — 营销内容生成"""

    AGENT_ID = "marketing"
    DISPLAY_NAME = "营销内容"
    CAPABILITIES = ["copywriting", "social_media", "seo", "email", "brand"]
    TASK_TYPES = ["copywriting", "social_media", "seo_article", "email_campaign", "brand_strategy", "campaign_plan"]

    PROMPTS = {
        "copywriting": COPYWRITING_PROMPT,
        "social_media": SOCIAL_MEDIA_PROMPT,
        "seo_article": SEO_ARTICLE_PROMPT,
        "email_campaign": EMAIL_PROMPT,
        "brand_strategy": BRAND_STRATEGY_PROMPT,
        "campaign_plan": CAMPAIGN_PROMPT,
    }

    def __init__(self, api_key: Optional[str] = None, timeout: int = 60):
        super().__init__(name="marketing", timeout=timeout)
        try:
            config = get_ai_config()
            self.api_key = api_key or config["api_key"]
            self.model = config["model"]
            self.api_base = config["base_url"]
        except RuntimeError:
            self.api_key = ""
            self.model = "deepseek-chat"
            self.api_base = "https://api.deepseek.com"

    def run(self, task: Dict[str, Any]) -> Dict[str, Any]:
        task_id = task.get("task_id", f"mkt_{uuid.uuid4().hex[:8]}")
        task_type = task.get("task_type", "copywriting")
        goal = task.get("goal", "")
        prompt = task.get("prompt", task.get("content_brief", goal))

        if not prompt:
            return self._result(task_id, "失败", "缺少营销内容需求描述", {})

        sys_prompt = self.PROMPTS.get(task_type, COPYWRITING_PROMPT)

        if self.api_key:
            ai_result = self._call_ai(sys_prompt, prompt)
            if ai_result:
                result_data = dict(ai_result)
                result_data["content_type"] = task_type
                return self._result(
                    task_id, "生成完成",
                    self._extract_summary(task_type, ai_result),
                    result_data,
                )

        # 规则降级
        return self._rule_fallback(task_id, task_type, prompt)

    # ── AI 调用 ──────────────────────────────────────────

    def _call_ai(self, system_prompt: str, user_prompt: str) -> Optional[Dict]:
        try:
            import urllib.request

            if AI_PROVIDER == "claude":
                payload = json.dumps({
                    "model": self.model,
                    "max_tokens": 3000,
                    "system": system_prompt,
                    "messages": [{"role": "user", "content": user_prompt}],
                }).encode("utf-8")
                req = urllib.request.Request(
                    f"{self.api_base.rstrip('/')}/v1/messages",
                    data=payload,
                    headers={
                        "Content-Type": "application/json",
                        "x-api-key": self.api_key,
                        "anthropic-version": "2023-06-01",
                    },
                )
                with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                    body = json.loads(resp.read().decode("utf-8"))
                    text = body["content"][0]["text"]
            else:
                payload = json.dumps({
                    "model": self.model,
                    "messages": [
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_prompt},
                    ],
                    "temperature": 0.8,
                    "max_tokens": 3000,
                }).encode("utf-8")
                req = urllib.request.Request(
                    f"{self.api_base.rstrip('/')}/chat/completions",
                    data=payload,
                    headers={
                        "Content-Type": "application/json",
                        "Authorization": f"Bearer {self.api_key}",
                    },
                )
                with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                    body = json.loads(resp.read().decode("utf-8"))
                    text = body["choices"][0]["message"]["content"]

            return self._extract_json(text)
        except Exception as e:
            print(f"[Marketing Agent] AI 调用失败: {e}")
            return None

    @staticmethod
    def _extract_json(text: str) -> Optional[Dict]:
        text = re.sub(r"```(?:json)?\s*", "", text).replace("```", "").strip()
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            match = re.search(r"\{[\s\S]*\}", text)
            if match:
                try: return json.loads(match.group())
                except json.JSONDecodeError: pass
        return None

    @staticmethod
    def _extract_summary(task_type: str, data: Dict) -> str:
        if task_type == "copywriting":
            return data.get("headline", "文案已生成")
        elif task_type == "social_media":
            return f"[{data.get('platform', '社媒')}] {data.get('content', '')[:100]}..."
        elif task_type == "seo_article":
            return data.get("h1", data.get("meta_title", "SEO文章已生成"))
        elif task_type == "email_campaign":
            return f"[{data.get('subject', '邮件')}] 序列已生成"
        elif task_type == "brand_strategy":
            return data.get("brand_positioning", "品牌策略已生成")
        elif task_type == "campaign_plan":
            return data.get("campaign_name", "活动方案已生成")
        return "营销内容已生成"

    # ── 规则降级 ──────────────────────────────────────────

    def _rule_fallback(self, task_id: str, task_type: str, prompt: str) -> Dict:
        templates = {
            "copywriting": {
                "headline": f"[产品名] — 让{self._extract_topic(prompt)}更简单",
                "body": f"还在为{self._extract_topic(prompt)}烦恼吗？\n试试我们的解决方案...\n\n（此为模板内容，配置 AI API 获得定制文案）",
                "cta": "立即体验 →",
                "variations": ["变体1", "变体2"],
            },
            "social_media": {
                "platform": "通用",
                "content": f"📢 {self._extract_topic(prompt)}\n\n分享一个关于{self._extract_topic(prompt)}的想法...\n（配置 AI API 获得定制内容）",
                "hashtags": ["#内容营销", "#品牌"],
            },
            "seo_article": {
                "meta_title": f"{self._extract_topic(prompt)} — 完整指南",
                "h1": f"{self._extract_topic(prompt)}完全指南",
                "content": f"## 什么是{self._extract_topic(prompt)}？\n\n（配置 AI API 获得 SEO 优化长文）",
            },
            "email_campaign": {
                "subject": f"关于{self._extract_topic(prompt)}的重要消息",
                "body": f"<p>亲爱的用户：</p><p>关于{self._extract_topic(prompt)}...（配置 AI API 获得定制邮件）</p>",
            },
            "brand_strategy": {
                "brand_positioning": f"为{self._extract_topic(prompt)}领域提供创新解决方案",
                "tagline_options": ["让未来更简单", "创新驱动价值"],
            },
            "campaign_plan": {
                "campaign_name": f"{self._extract_topic(prompt)}推广活动",
                "goal": f"提升{self._extract_topic(prompt)}的知名度和转化率",
            },
        }
        data = templates.get(task_type, templates["copywriting"])
        data["content_type"] = task_type
        data["mode"] = "template_fallback"

        return self._result(
            task_id, f"生成完成（模板模式）",
            f"使用模板生成{task_type}内容。配置 AI API Key 获得智能定制。",
            data,
        )

    @staticmethod
    def _extract_topic(text: str, max_len: int = 20) -> str:
        """从文本中提取主题词"""
        stopwords = {"帮我","请","写","生成","一个","一份","一篇","的","和","与","了"}
        for sw in stopwords:
            text = text.replace(sw, " ")
        words = [w for w in text.split() if len(w) >= 2]
        topic = " ".join(words[:4]) if words else text[:30]
        return topic[:max_len]

    def _result(self, task_id: str, status: str, summary: str,
                data: Dict = None) -> Dict:
        return {
            "task_id": task_id,
            "agent": "marketing_agent",
            "agent_name": "Marketing 营销内容",
            "status": status,
            "summary": summary,
            "result": summary,
            "data": data or {},
            "output": data or {},
        }
