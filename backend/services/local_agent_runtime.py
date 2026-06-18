"""
Local Agent Runtime — 本地优先任务调度器

职责：
1. 接收用户任务
2. 识别任务类型
3. 查询 capability_scanner 当前能力
4. 选择合适 adapter
5. 执行任务
6. 结果验证
7. 返回统一结果
"""
import uuid
from datetime import datetime
from typing import Dict, Any, List, Optional
from backend.logger import get_logger

logger = get_logger()


class LocalAgentRuntime:
    """本地任务调度器"""

    def __init__(self):
        self._adapters = {}
        self._capability_scanner = None
        self._result_verifier = None
        self._init_adapters()
        self._init_scanner()
        self._init_verifier()

    def _init_adapters(self):
        """初始化所有适配器"""
        try:
            from backend.adapters import (
                ClaudeCodeAdapter,
                ComfyUIAdapter,
                OllamaAdapter,
                OpenClawAdapter,
                DataAdapter,
                ApiModelAdapter,
                MiMoAdapter
            )

            self._adapters = {
                "claude_code": ClaudeCodeAdapter(),
                "comfyui": ComfyUIAdapter(),
                "ollama": OllamaAdapter(),
                "openclaw": OpenClawAdapter(),
                "data_tools": DataAdapter(),
                "api_models": ApiModelAdapter(),
                "mimo": MiMoAdapter(),
            }
            logger.info("LocalAgentRuntime: Adapters initialized")
        except Exception as e:
            logger.error(f"LocalAgentRuntime: Failed to init adapters: {e}")

    def _init_scanner(self):
        """初始化能力扫描器"""
        try:
            from backend.services.capability_scanner import get_capability_scanner
            self._capability_scanner = get_capability_scanner()
        except Exception as e:
            logger.error(f"LocalAgentRuntime: Failed to init scanner: {e}")

    def _init_verifier(self):
        """初始化结果验证器"""
        try:
            from backend.services.result_verifier import get_result_verifier
            self._result_verifier = get_result_verifier()
        except Exception as e:
            logger.error(f"LocalAgentRuntime: Failed to init verifier: {e}")

    def execute(self, message: str, context: Dict = None) -> Dict[str, Any]:
        """执行任务"""
        task_id = f"task_{uuid.uuid4().hex[:8]}"
        used_tools = []
        tool_trace = []
        warnings = []

        logger.info(f"LocalAgentRuntime: Executing task {task_id}")

        # 1. 识别任务类型
        task_type = self._identify_task_type(message, context)
        tool_trace.append({
            "tool": "system",
            "action": "任务识别",
            "status": "done",
            "summary": f"识别为 {task_type} 类型任务"
        })

        # 2. 查询当前能力
        capabilities = self._capability_scanner.scan_all() if self._capability_scanner else {}
        available_tools = [t for t, info in capabilities.items() if info.get("available")]

        tool_trace.append({
            "tool": "system",
            "action": "能力扫描",
            "status": "done",
            "summary": f"可用工具: {', '.join(available_tools) if available_tools else '无'}"
        })

        # 3. 选择适配器
        adapter = self._select_adapter(task_type, message, capabilities)

        if not adapter:
            return self._create_result(
                ok=False,
                mode="unavailable",
                task_id=task_id,
                task_type=task_type,
                error=f"没有可用的工具处理 {task_type} 类型任务",
                warnings=self._get_fix_hints(task_type, capabilities),
                tool_trace=tool_trace
            )

        used_tools.append(adapter.TOOL_NAME)
        tool_trace.append({
            "tool": adapter.TOOL_NAME,
            "action": "选择工具",
            "status": "done",
            "summary": f"使用 {adapter.TOOL_NAME} 处理任务"
        })

        # 4. 执行任务
        task = {
            "goal": message,
            "prompt": message,
            "task_type": task_type,
            **(context or {})
        }

        result = adapter.run(task)

        tool_trace.append({
            "tool": adapter.TOOL_NAME,
            "action": "执行任务",
            "status": "done" if result.get("ok") else "failed",
            "summary": result.get("error", "执行完成") if not result.get("ok") else "执行成功",
            "duration_ms": result.get("duration_ms", 0)
        })

        if not result.get("ok"):
            return self._create_result(
                ok=False,
                mode="local",
                task_id=task_id,
                task_type=task_type,
                used_tools=used_tools,
                tool_trace=tool_trace,
                error=result.get("error", "任务执行失败"),
                warnings=result.get("warnings", [])
            )

        # 5. 提取内容和元数据
        content = result.get("stdout", "") or result.get("result", {}).get("output", "")
        sources = result.get("result", {}).get("sources", [])
        metadata = result.get("metadata", {})

        # 检查内容是否为空
        if not content or not content.strip():
            return self._create_result(
                ok=False,
                mode="local",
                task_id=task_id,
                task_type=task_type,
                used_tools=used_tools,
                tool_trace=tool_trace,
                error="任务执行结果为空",
                warnings=["本地工具未返回有效内容"]
            )

        # 6. 结果验证
        verification = {"passed": True, "score": 100, "issues": []}
        if self._result_verifier:
            verification = self._result_verifier.verify(task_type, {
                "final_answer": content,
                "sources": sources,
                "deliverables": result.get("result", {})
            })

            tool_trace.append({
                "tool": "verifier",
                "action": "结果验证",
                "status": "passed" if verification["passed"] else "failed",
                "summary": f"验证得分: {verification['score']}, 问题: {len(verification.get('issues', []))}"
            })

            # 验证失败
            if not verification["passed"]:
                return self._create_result(
                    ok=False,
                    mode="local",
                    task_id=task_id,
                    task_type=task_type,
                    used_tools=used_tools,
                    tool_trace=tool_trace,
                    error="结果验证失败",
                    warnings=verification.get("issues", []),
                    verification_result=verification
                )

        # 7. 构建最终结果
        return self._create_result(
            ok=True,
            mode="local",
            task_id=task_id,
            task_type=task_type,
            used_tools=used_tools,
            tool_trace=tool_trace,
            final_answer=content,
            sources=sources,
            search_mode=metadata.get("search_mode", "none"),
            used_web_search=metadata.get("used_web_search", False),
            deliverables=result.get("result", {}),
            verification_result=verification,
            confidence=self._calculate_confidence(verification, sources, metadata),
            warnings=warnings
        )

    def _identify_task_type(self, message: str, context: Dict = None) -> str:
        """识别任务类型"""
        message_lower = message.lower()

        # 关键词映射（按优先级排序）
        keywords = {
            "image": ["图片", "海报", "插画", "封面", "商品图", "生成图", "image", "poster", "illustration",
                      "logo", "照片", "photo", "picture", "design"],
            "data": ["数据", "excel", "csv", "表格", "分析数据", "data", "spreadsheet", "analyze",
                     "统计", "报表"],
            "research": ["调研", "搜索", "联网", "市场分析", "竞品分析", "research", "search", "analyze",
                        "market", "competitor", "趋势", "行业"],
            "website": ["网页", "官网", "落地页", "html", "website", "landing page", "web page",
                       "生成网页", "建网站"],
            "code": ["代码", "编程", "开发", "code", "program", "develop", "function", "python",
                    "script", "写一个", "写代码"],
            "marketing": ["文案", "营销", "推广", "朋友圈", "小红书", "淘宝", "抖音", "post", "write",
                         "wechat", "广告", "slogan"],
        }

        for task_type, kws in keywords.items():
            if any(kw in message_lower for kw in kws):
                return task_type

        return "chat"

    def _select_adapter(self, task_type: str, message: str, capabilities: Dict) -> Optional[Any]:
        """选择合适的适配器"""

        # 图片任务：只能用 ComfyUI，不允许 fallback
        if task_type == "image":
            if capabilities.get("comfyui", {}).get("available"):
                return self._adapters.get("comfyui")
            return None  # 没有图片工具就返回 None，不允许 fallback 到其他

        # 数据任务：只能用 DataAdapter，不允许 fallback
        if task_type == "data":
            if capabilities.get("data_tools", {}).get("available"):
                return self._adapters.get("data_tools")
            return None  # 没有数据工具就返回 None

        # 代码任务：优先 Claude Code，然后 API
        if task_type == "code":
            if capabilities.get("claude_code", {}).get("available"):
                return self._adapters.get("claude_code")

        # 调研任务：优先 MiMo（联网搜索），然后 OpenClaw
        if task_type in {"research", "competitor_analysis", "market_analysis"}:
            mimo_info = capabilities.get("mimo", {})
            if mimo_info.get("available") and mimo_info.get("models", [{}])[0].get("web_search_enabled"):
                return self._adapters.get("mimo")
            if capabilities.get("openclaw", {}).get("available"):
                return self._adapters.get("openclaw")

        # 营销任务：检查是否需要联网
        if task_type == "marketing":
            web_keywords = ["最新", "目前", "市场", "趋势", "竞品", "价格", "行业", "2025", "2026"]
            if any(kw in message.lower() for kw in web_keywords):
                mimo_info = capabilities.get("mimo", {})
                if mimo_info.get("available"):
                    return self._adapters.get("mimo")

        # 网站任务：优先 MiMo 或 API
        if task_type == "website":
            mimo_info = capabilities.get("mimo", {})
            if mimo_info.get("available"):
                return self._adapters.get("mimo")

        # 其他任务：优先 Ollama，然后 MiMo，然后 API 模型
        if capabilities.get("ollama", {}).get("available"):
            return self._adapters.get("ollama")

        if capabilities.get("mimo", {}).get("available"):
            return self._adapters.get("mimo")

        if capabilities.get("api_models", {}).get("available"):
            return self._adapters.get("api_models")

        return None

    def _get_fix_hints(self, task_type: str, capabilities: Dict) -> List[str]:
        """获取修复建议"""
        hints = []

        if task_type == "image":
            if not capabilities.get("comfyui", {}).get("installed"):
                hints.append("请安装 ComfyUI: https://github.com/comfyanonymous/ComfyUI")
            elif not capabilities.get("comfyui", {}).get("running"):
                hints.append("请启动 ComfyUI")

        if task_type == "data":
            if not capabilities.get("data_tools", {}).get("available"):
                hints.append(capabilities.get("data_tools", {}).get("fix_hint", "请安装数据分析依赖"))

        if task_type == "research":
            if not capabilities.get("mimo", {}).get("available"):
                hints.append("请配置 MIMO_API_KEY 以启用联网搜索")
            if not capabilities.get("openclaw", {}).get("available"):
                hints.append("请安装 Playwright 以启用浏览器搜索")

        if not capabilities.get("api_models", {}).get("available"):
            hints.append("请配置至少一个 API Key（DeepSeek/OpenAI/Claude）")

        return hints

    def _calculate_confidence(self, verification: Dict, sources: List, metadata: Dict) -> float:
        """计算置信度"""
        confidence = 0.5

        if verification.get("passed"):
            confidence += 0.2
        if verification.get("score", 0) >= 90:
            confidence += 0.1
        if sources and len(sources) > 0:
            confidence += 0.15
        if metadata.get("used_web_search"):
            confidence += 0.05

        return min(confidence, 1.0)

    def _create_result(self, **kwargs) -> Dict[str, Any]:
        """创建统一的返回结构"""
        return {
            "ok": kwargs.get("ok", False),
            "mode": kwargs.get("mode", "local"),
            "task_id": kwargs.get("task_id", ""),
            "task_type": kwargs.get("task_type", "unknown"),
            "used_tools": kwargs.get("used_tools", []),
            "tool_trace": kwargs.get("tool_trace", []),
            "used_web_search": kwargs.get("used_web_search", False),
            "search_mode": kwargs.get("search_mode", "none"),
            "sources": kwargs.get("sources", []),
            "final_answer": kwargs.get("final_answer", ""),
            "deliverables": kwargs.get("deliverables", {}),
            "verification_result": kwargs.get("verification_result", {}),
            "qa": kwargs.get("verification_result", {}),
            "confidence": kwargs.get("confidence", 0.0),
            "warnings": kwargs.get("warnings", []),
            "error": kwargs.get("error", ""),
            "created_at": datetime.now().isoformat()
        }


# 全局实例
_runtime = None


def get_local_agent_runtime() -> LocalAgentRuntime:
    """获取本地任务调度器单例"""
    global _runtime
    if _runtime is None:
        _runtime = LocalAgentRuntime()
    return _runtime
