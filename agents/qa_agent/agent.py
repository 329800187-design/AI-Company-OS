"""
QA Agent — 质量验收智能体 v2

升级：AI 语义评分 + 规则降级
- AI 模式：调用大模型做语义质量评估
- 规则模式：启发式检查（goal/result/expected_output）
"""
import json
import os
import re
from typing import Any, Dict, List, Optional

from agents.base_agent import BaseAgent
from backend.config import get_ai_config, AI_PROVIDER
from core.agent_timing import timed


QA_AI_PROMPT = """你是一位 QA 质量验收专家。请评估以下任务执行结果的质量。

评估维度：
1. 完成度 (0-40分)：任务是否完成了目标要求的所有内容
2. 正确性 (0-30分)：产出是否符合预期，有无明显错误
3. 可用性 (0-20分)：产出是否可直接使用，格式是否规范
4. 完整性 (0-10分)：有无遗漏的关键信息或细节

输出 JSON：
{
  "overall_score": 0-100,
  "breakdown": {"完成度": 40, "正确性": 30, "可用性": 20, "完整性": 10},
  "summary": "一句话评价",
  "problems": ["问题1", "问题2"],
  "suggestions": ["改进建议1"],
  "verdict": "pass|needs_review|retry"
}

评分标准：
- pass (>=80): 任务完成，可直接使用
- needs_review (60-79): 基本完成，建议人工复查
- retry (<60): 未达标，需重新执行或修改

只输出 JSON，不要其他文字。"""


class QAAgent(BaseAgent):
    """QA Agent — 检查任务结果是否符合预期，给出评分和建议"""

    AGENT_ID = "qa"
    DISPLAY_NAME = "质量验收"
    CAPABILITIES = ["qa", "review", "scoring"]
    TASK_TYPES = ["qa_review", "quality_check"]

    def __init__(self):
        super().__init__(name="qa")
        try:
            config = get_ai_config()
            self.api_key = config["api_key"]
            self.model = config["model"]
            self.api_base = config["base_url"]
        except RuntimeError:
            self.api_key = ""
            self.model = "deepseek-chat"
            self.api_base = "https://api.deepseek.com"

    @timed("qa")
    def run(self, task: Dict[str, Any]) -> Dict[str, Any]:
        task_id = task.get("task_id", "unknown_task")
        goal = task.get("goal", "")
        result = task.get("result")
        extracted_data = task.get("extracted_data", [])

        result_text = ""
        if isinstance(result, dict):
            result_text = str(result.get("result", ""))
            result_data = result.get("data", [])
            if not extracted_data and result_data:
                extracted_data = result_data
        elif isinstance(result, str):
            result_text = result

        # 尝试 AI 语义评分
        if self.api_key:
            ai_result = self._ai_evaluate(goal, result_text, extracted_data, task)
            if ai_result:
                return self._format_ai_result(task_id, goal, ai_result, extracted_data)

        # 降级：规则评分
        return self._rule_evaluate(task_id, goal, result, result_text, extracted_data, task)

    def _ai_evaluate(self, goal: str, result_text: str,
                     extracted_data: List, task: Dict) -> Optional[Dict]:
        """AI 语义评估"""
        try:
            import urllib.request

            prompt = f"""请评估以下任务执行结果：

任务目标：{goal}
预期产出：{json.dumps(task.get('expected_output', {}), ensure_ascii=False)}
执行结果：{result_text[:2000] if result_text else '(无文本输出)'}
数据条数：{len(extracted_data)}"""

            if AI_PROVIDER == "claude":
                payload = json.dumps({
                    "model": self.model, "max_tokens": 1024,
                    "system": QA_AI_PROMPT,
                    "messages": [{"role": "user", "content": prompt}],
                }).encode("utf-8")
                req = urllib.request.Request(
                    f"{self.api_base.rstrip('/')}/v1/messages",
                    data=payload,
                    headers={"Content-Type": "application/json",
                             "x-api-key": self.api_key, "anthropic-version": "2023-06-01"},
                )
                with urllib.request.urlopen(req, timeout=20) as resp:
                    body = json.loads(resp.read().decode("utf-8"))
                    text = body["content"][0]["text"]
            else:
                payload = json.dumps({
                    "model": self.model,
                    "messages": [
                        {"role": "system", "content": QA_AI_PROMPT},
                        {"role": "user", "content": prompt},
                    ],
                    "temperature": 0.3, "max_tokens": 1024,
                }).encode("utf-8")
                req = urllib.request.Request(
                    f"{self.api_base.rstrip('/')}/chat/completions",
                    data=payload,
                    headers={"Content-Type": "application/json",
                             "Authorization": f"Bearer {self.api_key}"},
                )
                with urllib.request.urlopen(req, timeout=20) as resp:
                    body = json.loads(resp.read().decode("utf-8"))
                    text = body["choices"][0]["message"]["content"]

            return self._extract_json(text)
        except Exception as e:
            self.logger.warning(f"AI 评估失败: {e}")
            return None

    @staticmethod
    def _extract_json(text: str) -> Optional[Dict]:
        text = re.sub(r"```(?:json)?\s*", "", text).replace("```", "").strip()
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            m = re.search(r"\{[\s\S]*\}", text)
            if m:
                try:
                    return json.loads(m.group())
                except json.JSONDecodeError:
                    pass
        return None

    def _format_ai_result(self, task_id: str, goal: str,
                          ai: Dict, extracted_data: List) -> Dict:
        """格式化 AI 评估结果"""
        score = ai.get("overall_score", 70)
        verdict = ai.get("verdict", "needs_review")
        status_map = {"pass": "已完成", "needs_review": "需复查", "retry": "需重试"}
        status = status_map.get(verdict, "需复查")
        return self.ok(
            task_id=task_id,
            status=status,
            data={
                "summary": ai.get("summary", ""),
                "score": score,
                "problems": ai.get("problems", []),
                "suggestions": ai.get("suggestions", []),
                "next_suggestion": f"评分 {score}/100 — {'通过' if score >= 80 else '建议复查' if score >= 60 else '建议重试'}",
                "目标": goal, "是否有效": True,
                "数据条数": len(extracted_data),
                "评分明细": ai.get("breakdown", {}),
                "评估详情": ai.get("summary", ""),
            },
            meta={"score": score},
        )

    def _rule_evaluate(self, task_id: str, goal: str, result, result_text: str,
                       extracted_data: List, task: Dict) -> Dict:
        """规则评分（降级模式）"""
        score = 0
        problems = []

        if goal:
            score += 20
        else:
            problems.append("任务缺少目标描述（goal）")

        has_meaningful_result = False
        if result:
            has_meaningful_result = True
            score += 30
        elif extracted_data and len(extracted_data) > 3:
            has_meaningful_result = True
            score += 30
            result_text = f"包含 {len(extracted_data)} 条数据"

        if not has_meaningful_result:
            problems.append("未检测到有效执行结果数据")

        if result_text and len(result_text) > 20:
            score += 20
        else:
            problems.append("结果内容过短，可能未获取到有效信息")

        if task.get("expected_output"):
            score += 15
        else:
            problems.append("任务缺少预期产出描述（expected_output）")

        if extracted_data:
            score += 15
            goal_keywords = goal.lower().split()
            meaningful_count = sum(1 for line in extracted_data if any(kw in line.lower() for kw in goal_keywords[:5]))
            if meaningful_count >= 3:
                score += 15

        if score >= 80:
            status, summary, next_sug = "已完成", "QA 验收通过，任务结果符合预期", "任务可以进入完成状态"
        elif score >= 60:
            status, summary, next_sug = "需复查", "QA 基本通过，建议人工复查后确认", "建议人工确认后再完成任务"
        else:
            status, summary, next_sug = "需重试", "QA 验收未通过，需要修改后重新执行", "建议重新拆解或修改任务"

        return self.ok(
            task_id=task_id,
            status=status,
            data={
                "summary": summary,
                "score": score,
                "problems": problems,
                "next_suggestion": next_sug,
                "目标": goal, "是否有结果": has_meaningful_result,
                "数据条数": len(extracted_data) if extracted_data else 0,
                "结果摘要": result_text[:200],
                "预期产出": task.get("expected_output", {}),
            },
            meta={"score": score},
        )
