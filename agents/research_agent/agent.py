"""
Research Agent — 文本调研框架智能体

能力：
1. research_brief: 结构化调研简报（市场/竞品/机会/风险）
2. market_research: 市场调研框架
3. competitor_analysis: 竞品分析框架

执行路径：
  1. 有 API key/provider → 调用真实 LLM（通过 BrainManager）
  2. LLM 返回有效 JSON → 规范化 structured_output
  3. 无 key / 调用失败 / 无效 JSON → 模板 fallback

注意：本 Agent 不具备联网抓取能力。
产出为基于用户输入的调研框架 + LLM 分析，非实时联网调研数据。
"""
import json
import re
import uuid
from typing import Any, Dict, List, Optional

from agents.base_agent import BaseAgent


# ── System Prompts ────────────────────────────────────────

RESEARCH_BRIEF_PROMPT = """你是一位资深市场调研分析师。根据用户的调研需求，生成结构化的调研简报。

要求：
- 分析市场概况、竞争格局、机会与风险
- 给出可执行的建议
- 明确标注信息局限性
- 保持客观、专业

输出格式（JSON）：
{
  "research_question": "本次调研的核心问题",
  "market_summary": "市场概况（200-400字）",
  "key_findings": ["发现1", "发现2", "发现3"],
  "competitors": [
    {"name": "竞品名", "strength": "优势", "weakness": "劣势", "positioning": "定位"}
  ],
  "opportunities": ["机会1", "机会2"],
  "risks": ["风险1", "风险2"],
  "recommended_actions": ["建议1", "建议2"],
  "limitations": ["本简报为框架型调研，非联网实时数据。如需真实数据，请配置联网 Agent。"],
  "sources": []
}

注意：
- sources 数组在无联网能力时为空，这是正常的
- limitations 必须包含"本简报为框架型调研，非联网实时数据"说明
- 只输出 JSON，不要其他文字。"""

MARKET_RESEARCH_PROMPT = """你是一位市场研究专家。根据用户需求生成市场调研框架。

输出格式（JSON）：
{
  "research_question": "调研核心问题",
  "market_summary": "市场概况",
  "key_findings": ["发现1", "发现2"],
  "competitors": [],
  "opportunities": ["机会1"],
  "risks": ["风险1"],
  "recommended_actions": ["建议1"],
  "limitations": ["局限性说明"],
  "sources": []
}

只输出 JSON，不要其他文字。"""

COMPETITOR_ANALYSIS_PROMPT = """你是一位竞品分析专家。根据用户需求生成竞品分析框架。

输出格式（JSON）：
{
  "research_question": "分析核心问题",
  "market_summary": "市场概况",
  "key_findings": ["发现1", "发现2"],
  "competitors": [
    {"name": "竞品", "strength": "优势", "weakness": "劣势", "positioning": "定位"}
  ],
  "opportunities": ["差异化机会"],
  "risks": ["竞争风险"],
  "recommended_actions": ["策略建议"],
  "limitations": ["局限性说明"],
  "sources": []
}

只输出 JSON，不要其他文字。"""


class ResearchAgent(BaseAgent):
    """Research Agent — 文本调研框架智能体

    执行优先级：
      1. 调用真实 LLM（BrainManager 自动选 provider）
      2. LLM 返回有效 JSON → 规范化 structured_output
      3. 无 key / 调用失败 / 无效 JSON → 模板 fallback
    """

    AGENT_ID = "research"
    DISPLAY_NAME = "调研分析"
    CAPABILITIES = ["research", "brief", "analysis"]
    TASK_TYPES = ["research_brief", "market_research", "competitor_analysis"]

    REQUIRED_FIELDS = [
        "research_question", "market_summary", "key_findings",
        "competitors", "opportunities", "risks",
        "recommended_actions", "limitations", "sources",
    ]

    PROMPTS = {
        "research_brief": RESEARCH_BRIEF_PROMPT,
        "market_research": MARKET_RESEARCH_PROMPT,
        "competitor_analysis": COMPETITOR_ANALYSIS_PROMPT,
    }

    def __init__(self, api_key: Optional[str] = None, timeout: int = 60):
        super().__init__(name="research", timeout=timeout)
        self.api_key = api_key or ""

    def run(self, task: Dict[str, Any]) -> Dict[str, Any]:
        task_id = task.get("task_id", f"res_{uuid.uuid4().hex[:8]}")
        task_type = task.get("task_type", "research_brief")
        goal = task.get("goal", "")
        prompt = task.get("prompt", goal)

        if not prompt:
            return self.fail(
                task_id,
                error="缺少调研目标描述",
                status="failed",
                meta={"fallback": True},
            )

        sys_prompt = self.PROMPTS.get(task_type, RESEARCH_BRIEF_PROMPT)

        # ── 尝试真实 LLM ────────────────────────────────────
        llm_result = self._try_llm(sys_prompt, prompt, task_type)
        if llm_result is not None:
            enriched = self._enrich_result(llm_result, prompt)
            enriched["content_type"] = task_type
            return self.ok(
                task_id,
                status="completed",
                data=enriched,
                meta={
                    "fallback": False,
                    "model": getattr(self, "model", ""),
                    "source": "llm",
                },
            )

        # ── 模板 fallback ────────────────────────────────────
        return self._rule_fallback(task_id, task_type, prompt)

    # ── LLM 调用（复用 BrainManager）───────────────────────

    def _try_llm(self, system_prompt: str, user_prompt: str,
                 task_type: str) -> Optional[Dict]:
        """尝试调用真实 LLM，返回规范化 structured_output 或 None。"""
        try:
            resp = self.call_ai(
                message=user_prompt,
                system=system_prompt,
                temperature=0.7,
                max_tokens=3000,
            )
            if not resp.get("ok"):
                self.logger.warning(
                    "[Research Agent] LLM 调用失败: %s", resp.get("error", "unknown")
                )
                return None

            text = resp.get("reply", "")
            raw = self._extract_json(text)
            if raw is None:
                self.logger.warning("[Research Agent] LLM 返回无效 JSON，回退模板")
                return None

            return self._normalize_structured_output(raw, prompt=user_prompt)

        except Exception as e:
            self.logger.error("[Research Agent] LLM 调用异常: %s", e)
            return None

    # ── structured_output 规范化 ─────────────────────────────

    def _normalize_structured_output(self, raw: Dict, prompt: str = "") -> Dict:
        """确保至少包含 research_market_summary/key_findings 等 9 个必选字段。"""
        out = dict(raw)
        out.setdefault("research_question", prompt or "未指定")
        out.setdefault("market_summary", "")
        out.setdefault("key_findings", [])
        out.setdefault("competitors", [])
        out.setdefault("opportunities", [])
        out.setdefault("risks", [])
        out.setdefault("recommended_actions", [])
        out.setdefault("limitations", [])
        out.setdefault("sources", [])

        # 确保 limitations 包含框架声明
        limitations = out.get("limitations", [])
        if not isinstance(limitations, list):
            limitations = [str(limitations)]
        framework_note = "本简报为框架型调研，非联网实时数据。如需真实数据，请配置联网 Agent。"
        if not any("框架" in l or "联网" in l for l in limitations):
            limitations.append(framework_note)
        out["limitations"] = limitations

        return out

    # ── 结果增强 ──────────────────────────────────────────

    @staticmethod
    def _enrich_result(data: Dict, goal: str) -> Dict:
        """确保标准字段存在"""
        enriched = dict(data)
        enriched.setdefault("research_question", goal)
        enriched.setdefault("market_summary", "")
        enriched.setdefault("key_findings", [])
        enriched.setdefault("competitors", [])
        enriched.setdefault("opportunities", [])
        enriched.setdefault("risks", [])
        enriched.setdefault("recommended_actions", [])
        enriched.setdefault("limitations", [])
        enriched.setdefault("sources", [])
        return enriched

    # ── JSON 提取 ──────────────────────────────────────────

    @staticmethod
    def _extract_json(text: str) -> Optional[Dict]:
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

    # ── 规则降级 ──────────────────────────────────────────

    def _rule_fallback(self, task_id: str, task_type: str, prompt: str) -> Dict:
        """无 AI API 时的规则降级 — 生成调研框架"""
        topic = self._extract_topic(prompt)

        result_data = {
            "research_question": prompt,
            "market_summary": f"关于「{topic}」的市场调研框架。当前为模板模式，未调用 AI。配置 AI API Key 后可获得定制化市场分析。",
            "key_findings": [
                f"关于「{topic}」的市场调研框架已生成",
                "当前为框架模式，非真实数据分析",
                "建议配置 AI API Key 以获得智能分析结果",
            ],
            "competitors": [
                {
                    "name": "（需配置 AI 后自动分析）",
                    "strength": "待分析",
                    "weakness": "待分析",
                    "positioning": "待分析",
                }
            ],
            "opportunities": [
                f"「{topic}」领域存在市场机会（需 AI 分析确认）",
                "建议配置 AI API 进行深度分析",
            ],
            "risks": [
                "市场风险需基于真实数据评估",
                "当前为框架模式，风险评估不完整",
            ],
            "recommended_actions": [
                "配置 AI API Key（DeepSeek/OpenAI/Claude）",
                "提供更详细的调研背景信息",
                "明确调研维度和重点关注领域",
            ],
            "limitations": [
                "本简报为框架型调研，非联网实时数据",
                "未调用 AI，内容为模板占位",
                "如需真实联网调研，需集成 browser agent",
            ],
            "sources": [],
            "content_type": task_type,
        }

        result = self.ok(
            task_id,
            status="模板模式 — 调研框架已生成",
            data=result_data,
            meta={
                "fallback": True,
                "fallback_reason": "无可用 LLM provider 或 API key，使用模板占位内容",
                "source": "template",
            },
        )
        result["warnings"] = [
            "当前为模板/规则降级产物，非真实 LLM 生成。配置 AI API Key 后可获得定制分析。",
            "本简报为框架型调研，非联网实时数据。",
        ]
        return result

    @staticmethod
    def _extract_topic(text: str, max_len: int = 20) -> str:
        stopwords = {"帮我", "请", "写", "生成", "一个", "一份", "一篇", "的", "和", "与", "了", "做", "调研", "简报", "分析"}
        for sw in stopwords:
            text = text.replace(sw, " ")
        words = [w for w in text.split() if len(w) >= 2]
        topic = " ".join(words[:4]) if words else text[:30]
        return topic[:max_len] or "未指定"
