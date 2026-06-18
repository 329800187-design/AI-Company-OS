"""
MiMo Adapter — MiMo 联网搜索模型适配器

主要负责：联网搜索、市场调研、竞品分析、最新信息查询、文案和综合分析
"""
import os
import httpx
from typing import Dict, Any, List
from .base_adapter import BaseAdapter


class MiMoAdapter(BaseAdapter):
    """MiMo 适配器"""

    TOOL_NAME = "mimo"

    def __init__(self):
        self.api_key = os.getenv("MIMO_API_KEY", "")
        self.base_url = os.getenv("MIMO_BASE_URL", "https://api.mimo.com/v1")
        self.model = os.getenv("MIMO_MODEL", "mimo-v2.5-pro")
        self.web_search_enabled = os.getenv("MIMO_ENABLE_WEB_SEARCH", "true").lower() == "true"

    def can_handle(self, task_type: str, task: Dict[str, Any]) -> bool:
        """判断是否能处理此任务"""
        supported_types = {"research", "competitor_analysis", "market_analysis", "marketing", "chat", "website"}
        return task_type in supported_types

    def health_check(self) -> Dict[str, Any]:
        """健康检查"""
        if not self.api_key:
            return {
                "available": False,
                "installed": False,
                "error": "未配置 MIMO_API_KEY",
                "fix_hint": "请配置 MIMO_API_KEY"
            }

        return {
            "available": True,
            "installed": True,
            "running": True,
            "model": self.model,
            "web_search_enabled": self.web_search_enabled
        }

    def run(self, task: Dict[str, Any]) -> Dict[str, Any]:
        """执行任务"""
        health = self.health_check()
        if not health.get("available"):
            return self._create_result(
                ok=False,
                error=health.get("error", "MiMo 不可用"),
                warnings=[health.get("fix_hint", "")]
            )

        prompt = task.get("goal", task.get("prompt", ""))
        task_type = task.get("task_type", "chat")

        if not prompt:
            return self._create_result(ok=False, error="未提供任务内容")

        # 判断是否需要联网搜索
        need_web_search = self._need_web_search(task_type, prompt)

        # 调用 MiMo API
        result, duration = self._measure_time(
            self._call_mimo, prompt, task_type, need_web_search
        )

        if result.get("ok"):
            # 检查 research 类任务是否有 sources
            if task_type in {"research", "competitor_analysis", "market_analysis"}:
                sources = result.get("sources", [])
                if not sources:
                    return self._create_result(
                        ok=False,
                        error="联网搜索未返回来源",
                        warnings=["MiMo 未能获取到搜索结果"],
                        duration_ms=duration
                    )

            return self._create_result(
                ok=True,
                result={
                    "output": result.get("reply", ""),
                    "sources": result.get("sources", [])
                },
                stdout=result.get("reply", ""),
                duration_ms=duration,
                metadata={
                    "model": self.model,
                    "used_web_search": need_web_search,
                    "search_mode": "mimo_web_search" if need_web_search else "none"
                }
            )
        else:
            return self._create_result(
                ok=False,
                error=result.get("error", "MiMo 调用失败"),
                duration_ms=duration
            )

    def _need_web_search(self, task_type: str, prompt: str) -> bool:
        """判断是否需要联网搜索"""
        # research 类任务必须联网
        if task_type in {"research", "competitor_analysis", "market_analysis"}:
            return True

        # 检查关键词
        web_keywords = ["最新", "目前", "市场", "趋势", "竞品", "价格", "行业", "2025", "2026",
                       "latest", "current", "market", "trend", "competitor", "price"]
        if any(kw in prompt.lower() for kw in web_keywords):
            return True

        return False

    def _call_mimo(self, prompt: str, task_type: str, need_web_search: bool) -> Dict[str, Any]:
        """调用 MiMo API"""
        try:
            # 构建请求体
            messages = [
                {"role": "system", "content": self._get_system_prompt(task_type)},
                {"role": "user", "content": prompt}
            ]

            body = {
                "model": self.model,
                "messages": messages,
                "temperature": 0.7,
                "max_tokens": 2000
            }

            # 如果需要联网搜索
            if need_web_search and self.web_search_enabled:
                body["tools"] = [
                    {
                        "type": "web_search",
                        "max_keyword": 3,
                        "force_search": True
                    }
                ]
                body["thinking"] = {"type": "disabled"}

            # 调用 API
            with httpx.Client(timeout=120) as client:
                response = client.post(
                    f"{self.base_url}/chat/completions",
                    json=body,
                    headers={
                        "Authorization": f"Bearer {self.api_key}",
                        "Content-Type": "application/json"
                    }
                )

                if response.status_code != 200:
                    return {"ok": False, "error": f"MiMo API error: {response.status_code}"}

                data = response.json()

                # 提取回复
                reply = data.get("choices", [{}])[0].get("message", {}).get("content", "")

                # 提取 sources
                sources = []
                if need_web_search:
                    # MiMo 返回的搜索结果可能在不同位置
                    tool_calls = data.get("choices", [{}])[0].get("message", {}).get("tool_calls", [])
                    for call in tool_calls:
                        if call.get("function", {}).get("name") == "web_search":
                            result = call.get("function", {}).get("result", {})
                            if isinstance(result, dict):
                                sources = result.get("sources", [])
                            elif isinstance(result, list):
                                sources = result

                return {
                    "ok": True,
                    "reply": reply,
                    "sources": sources
                }
        except Exception as e:
            return {"ok": False, "error": str(e)}

    def _get_system_prompt(self, task_type: str) -> str:
        """获取系统 prompt"""
        prompts = {
            "research": "你是一个专业的市场研究员。请基于联网搜索结果进行分析。要求：引用来源、提供数据支持、给出可操作建议。",
            "competitor_analysis": "你是一个竞品分析专家。请基于联网搜索结果分析竞争对手。要求：分析产品特点、价格策略、市场定位。",
            "market_analysis": "你是一个市场分析专家。请基于联网搜索结果分析市场趋势。要求：分析市场规模、增长趋势、主要玩家。",
            "marketing": "你是一个专业的营销文案专家。请根据用户需求生成高质量的营销文案。",
            "website": "你是一个专业的网页设计师。请根据用户需求生成完整的 HTML 页面。",
            "chat": "你是一个友好的 AI 助手，请帮助用户解答问题。",
        }
        return prompts.get(task_type, prompts["chat"])
