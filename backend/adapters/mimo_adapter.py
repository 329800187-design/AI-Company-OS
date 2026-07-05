"""
MiMo Adapter — MiMo 联网搜索模型适配器

主要负责：联网搜索、市场调研、竞品分析、最新信息查询、文案和综合分析
"""
import os
import httpx
from typing import Dict, Any, List
from .base_adapter import BaseAdapter
from backend.logger import get_logger

logger = get_logger()


class MiMoAdapter(BaseAdapter):
    """MiMo 适配器"""

    TOOL_NAME = "mimo"

    def __init__(self):
        self.api_key = os.getenv("MIMO_API_KEY", "")
        self.base_url = os.getenv("MIMO_BASE_URL", "")
        self.model = os.getenv("MIMO_MODEL", "mimo-v2-pro")  # 默认使用稳定版，避免 v2.5-pro 易 429
        self.web_search_enabled = os.getenv("MIMO_ENABLE_WEB_SEARCH", "true").lower() == "true"
        # 健康检查缓存
        self._health_cache = None
        self._health_cache_ts = 0
        self._health_cache_ttl = 300  # 5 分钟

    def can_handle(self, task_type: str, task: Dict[str, Any]) -> bool:
        """判断是否能处理此任务"""
        supported_types = {"research", "competitor_analysis", "market_analysis", "marketing", "chat", "website"}
        return task_type in supported_types

    def health_check(self) -> Dict[str, Any]:
        """健康检查 - 带缓存，避免频繁消耗额度"""
        import time

        # 使用缓存（5 分钟内不重复调用）
        now = time.time()
        if self._health_cache and (now - self._health_cache_ts) < self._health_cache_ttl:
            return self._health_cache

        # 检查 API Key
        if not self.api_key:
            result = {
                "available": False,
                "installed": False,
                "error": "未配置 MIMO_API_KEY",
                "fix_hint": "请在 .env 中配置 MIMO_API_KEY"
            }
            self._health_cache = result
            self._health_cache_ts = now
            return result

        # 检查 Base URL
        if not self.base_url:
            result = {
                "available": False,
                "installed": True,
                "error": "未配置 MIMO_BASE_URL",
                "fix_hint": "请在 .env 中配置 MIMO_BASE_URL (MiMo API 端点)"
            }
            self._health_cache = result
            self._health_cache_ts = now
            return result

        # 真实调用测试
        try:
            with httpx.Client(timeout=10) as client:
                response = client.get(
                    f"{self.base_url}/models",
                    headers={"Authorization": f"Bearer {self.api_key}"}
                )

                result = self._evaluate_status(response.status_code, "GET /models")
                self._health_cache = result
                self._health_cache_ts = now
                return result

        except httpx.ConnectError:
            result = {
                "available": False,
                "installed": True,
                "error": "无法连接到 MiMo API",
                "fix_hint": f"请检查 MIMO_BASE_URL ({self.base_url}) 是否可访问"
            }
            self._health_cache = result
            self._health_cache_ts = now
            return result
        except httpx.ConnectTimeout:
            result = {
                "available": False,
                "installed": True,
                "error": "连接 MiMo API 超时",
                "fix_hint": "请检查网络连接或稍后重试"
            }
            self._health_cache = result
            self._health_cache_ts = now
            return result
        except Exception as e:
            result = {
                "available": False,
                "installed": True,
                "error": f"MiMo 健康检查失败: {str(e)[:100]}",
                "fix_hint": "请检查 MiMo 配置和网络"
            }
            self._health_cache = result
            self._health_cache_ts = now
            return result

    def _evaluate_status(self, status_code: int, action: str) -> Dict[str, Any]:
        """评估 HTTP 状态码，返回统一的健康结果"""
        if status_code == 200:
            return {
                "available": True,
                "installed": True,
                "running": True,
                "model": self.model,
                "web_search_enabled": self.web_search_enabled
            }
        elif status_code == 401:
            return {
                "available": False,
                "installed": True,
                "error": f"[401] MIMO_API_KEY 无效或已过期",
                "fix_hint": "请检查 .env 中的 MIMO_API_KEY 是否正确，或重新生成一个"
            }
        elif status_code == 429:
            return {
                "available": False,
                "installed": True,
                "error": f"[429] 请求过频，上游限流",
                "fix_hint": "请稍后重试，或切换到更稳定的模型 (如 mimo-v2-pro)"
            }
        elif status_code == 400:
            return {
                "available": False,
                "installed": True,
                "error": f"[400] 请求格式错误 — base_url/model/payload 可能不匹配",
                "fix_hint": f"当前 model={self.model}, base_url={self.base_url}，请检查配置"
            }
        elif status_code == 404:
            # /models 不存在，尝试用 chat completion 测试
            return self._test_with_chat()
        else:
            return {
                "available": False,
                "installed": True,
                "error": f"MiMo API 返回 HTTP {status_code}",
                "fix_hint": f"请检查 MIMO_BASE_URL ({self.base_url}) 配置是否正确"
            }

    def _format_api_error(self, status_code: int, response_text: str = "") -> str:
        """格式化 API 错误消息，提供明确的 fix_hint"""
        hint_map = {
            401: "[401] API Key 无效或已过期 — 请检查 .env 中的 MIMO_API_KEY",
            429: "[429] 请求过频，上游限流 — 请稍后重试，或切换到更稳定的模型 (如 mimo-v2-pro)",
            400: f"[400] 请求格式错误 — base_url={self.base_url}, model={self.model}，请检查配置",
        }
        hint = hint_map.get(status_code, f"MiMo API error: HTTP {status_code}")
        # 截断过长的 response text
        if response_text and len(response_text) < 200:
            hint += f" | 服务端响应: {response_text[:100]}"
        return hint

    def _test_with_chat(self) -> Dict[str, Any]:
        """用最小 chat completion 测试（仅 /models 404 时调用）"""
        try:
            with httpx.Client(timeout=15) as client:
                response = client.post(
                    f"{self.base_url}/chat/completions",
                    json={
                        "model": self.model,
                        "messages": [{"role": "user", "content": "hi"}],
                        "max_tokens": 5
                    },
                    headers={
                        "Authorization": f"Bearer {self.api_key}",
                        "Content-Type": "application/json"
                    }
                )

                return self._evaluate_status(response.status_code, "POST /chat/completions")
        except httpx.ConnectError:
            return {
                "available": False,
                "installed": True,
                "error": "无法连接到 MiMo API",
                "fix_hint": f"请检查 MIMO_BASE_URL ({self.base_url}) 是否可访问"
            }
        except httpx.ConnectTimeout:
            return {
                "available": False,
                "installed": True,
                "error": "连接 MiMo API 超时",
                "fix_hint": "请检查网络连接或稍后重试"
            }
        except Exception as e:
            return {
                "available": False,
                "installed": True,
                "error": f"MiMo 测试失败: {str(e)[:100]}",
                "fix_hint": "请检查 MiMo 配置和网络"
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

        # 降级：如果需要搜索但搜索不可用，退化为普通模式
        search_degraded = False
        if need_web_search and not self.web_search_enabled:
            search_degraded = True
            need_web_search = False
            logger.info("MiMo: web_search requested but disabled — degrading to normal mode")

        # 调用 MiMo API
        result, duration = self._measure_time(
            self._call_mimo, prompt, task_type, need_web_search
        )

        if result.get("ok"):
            # 检查 research 类任务是否有 sources
            warnings = []
            if task_type in {"research", "competitor_analysis", "market_analysis"}:
                sources = result.get("sources", [])
                if not sources and not search_degraded:
                    warnings = ["联网搜索未返回来源，结果基于模型已有知识"]
                elif search_degraded:
                    warnings = ["联网搜索不可用，结果基于模型已有知识"]

            return self._create_result(
                ok=True,
                result={
                    "output": result.get("reply", ""),
                    "sources": result.get("sources", [])
                },
                stdout=result.get("reply", ""),
                duration_ms=duration,
                warnings=warnings,
                metadata={
                    "model": self.model,
                    "used_web_search": need_web_search and bool(result.get("sources")),
                    "search_mode": "mimo_web_search" if need_web_search else ("degraded" if search_degraded else "none"),
                    "search_degraded": search_degraded
                }
            )
        else:
            # 遇到 429 时清除缓存，下次 health_check 可以重新探测
            if "429" in result.get("error", ""):
                self._health_cache = None
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
                    error_msg = self._format_api_error(response.status_code, response.text)
                    return {"ok": False, "error": error_msg}

                data = response.json()

                # 提取回复
                choices = data.get("choices") or [{}]
                reply = choices[0].get("message", {}).get("content", "")

                # 提取 sources
                sources = self._extract_sources(data, need_web_search)

                return {
                    "ok": True,
                    "reply": reply,
                    "sources": sources
                }
        except Exception as e:
            return {"ok": False, "error": str(e)}

    def _extract_sources(self, data: Dict, need_web_search: bool) -> List[Dict]:
        """提取来源 - 支持多种格式"""
        sources = []

        if not need_web_search:
            return sources

        # 尝试从 tool_calls 提取
        choices = data.get("choices") or []
        if choices:
            message = choices[0].get("message", {})
            tool_calls = message.get("tool_calls") or []
            for call in tool_calls:
                func = call.get("function", {})
                if func.get("name") == "web_search":
                    result = func.get("result", {})
                    if isinstance(result, dict):
                        sources.extend(result.get("sources", []))
                    elif isinstance(result, list):
                        sources.extend(result)

        # 尝试从 annotations 提取
        if not sources:
            annotations = data.get("annotations") or []
            for ann in annotations:
                if ann.get("type") == "citation":
                    sources.append({
                        "title": ann.get("title", ""),
                        "url": ann.get("url", ""),
                        "summary": ann.get("text", "")
                    })

        # 尝试从 citations 提取
        if not sources:
            citations = data.get("citations") or []
            for cite in citations:
                sources.append({
                    "title": cite.get("title", ""),
                    "url": cite.get("url", ""),
                    "summary": cite.get("text", "")
                })

        # 尝试从 references 提取
        if not sources:
            references = data.get("references") or []
            for ref in references:
                sources.append({
                    "title": ref.get("title", ""),
                    "url": ref.get("url", ""),
                    "summary": ref.get("snippet", "")
                })

        return sources

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
