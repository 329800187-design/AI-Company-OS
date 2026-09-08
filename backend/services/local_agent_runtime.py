"""
Local Agent Runtime — 本地优先任务调度器

职责：
1. 接收用户任务
2. 使用 TaskClassifier 识别任务类型
3. 使用 AgentRouter 选择最佳 Agent
4. 执行任务
5. 使用 ResultVerifier 验证结果
6. 返回统一结果
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
        self._task_classifier = None
        self._agent_router = None
        self._result_verifier = None
        self._init_adapters()
        self._init_services()

    def _init_adapters(self):
        """初始化所有适配器"""
        try:
            from backend.adapters import (
                ClaudeCodeAdapter,
                ComfyUIAdapter,
                OllamaAdapter,
                DataAdapter,
                ApiModelAdapter,
                MiMoAdapter,
                LocalModuleAdapter,
                create_local_adapter
            )

            self._adapters = {
                "claude_code": ClaudeCodeAdapter(),
                "comfyui": ComfyUIAdapter(),
                "ollama": OllamaAdapter(),
                "data_tools": DataAdapter(),
                "api_models": ApiModelAdapter(),
                "mimo": MiMoAdapter(),
            }

            # 为项目本地 Agent 注册 LocalModuleAdapter
            local_agent_ids = [
                "data_agent", "image_agent", "marketing_agent",
                "research_agent", "website_agent"
            ]
            for agent_id in local_agent_ids:
                adapter = create_local_adapter(agent_id)
                if adapter:
                    self._adapters[agent_id] = adapter
                    logger.info(f"LocalAgentRuntime: Registered local adapter for {agent_id}")

            logger.info("LocalAgentRuntime: Adapters initialized")
        except Exception as e:
            logger.error(f"LocalAgentRuntime: Failed to init adapters: {e}")

    def _init_services(self):
        """初始化服务"""
        try:
            from backend.services.task_classifier import get_task_classifier
            self._task_classifier = get_task_classifier()
        except Exception as e:
            logger.error(f"LocalAgentRuntime: Failed to init task classifier: {e}")

        try:
            from backend.services.agent_router import get_agent_router
            self._agent_router = get_agent_router()
        except Exception as e:
            logger.error(f"LocalAgentRuntime: Failed to init agent router: {e}")

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
        fix_hints = []

        logger.info(f"LocalAgentRuntime: Executing task {task_id}")

        # 1. 使用 TaskClassifier 识别任务类型
        task_type, classification_confidence = "chat", 0.5
        if self._task_classifier:
            task_type, classification_confidence = self._task_classifier.classify(message, context)

        # The local image agent can always fall back to a prompt/mock asset.
        # Keep the real-render setup steps visible even when that fallback is
        # considered a successful response by a verifier.
        if task_type == "image":
            fix_hints = self._get_fix_hints(task_type)

        tool_trace.append({
            "tool": "task_classifier",
            "action": "任务识别",
            "status": "done",
            "summary": f"识别为 {task_type} 类型任务 (置信度: {classification_confidence:.2f})",
            "selected_reason": f"关键词匹配",
            "required_capabilities": self._get_required_capabilities(task_type)
        })

        # 2. 使用 AgentRouter 选择最佳 Agent
        selected_adapter = None
        candidate_agents = []
        rejected_agents = []

        if self._agent_router:
            # 获取候选 Agent
            from backend.services.agent_registry import get_agent_registry
            registry = get_agent_registry()
            registry.refresh()

            candidates = registry.get_agents_for_task(task_type)
            candidate_agents = [a.to_dict() for a in candidates]

            # 选择最佳 Agent
            selected_agent = self._agent_router.route(task_type, message, context)

            if selected_agent:
                # 映射到 adapter
                adapter_name = self._map_agent_to_adapter(selected_agent.id)
                if adapter_name and adapter_name in self._adapters:
                    selected_adapter = self._adapters[adapter_name]

                    tool_trace.append({
                        "tool": adapter_name,
                        "action": "Agent 选择",
                        "status": "done",
                        "summary": f"选择 {selected_agent.name} ({selected_agent.kind})",
                        "selected_reason": f"优先级: {selected_agent.priority}, 可靠性: {selected_agent.reliability_score}",
                        "candidate_agents": candidate_agents,
                        "rejected_agents": rejected_agents
                    })

        # 3. 如果 AgentRouter 没有选择，使用 fallback
        if not selected_adapter:
            selected_adapter = self._fallback_select_adapter(task_type, message)

            if selected_adapter:
                tool_trace.append({
                    "tool": selected_adapter.TOOL_NAME,
                    "action": "Fallback 选择",
                    "status": "done",
                    "summary": f"使用 fallback 适配器: {selected_adapter.TOOL_NAME}",
                    "selected_reason": "AgentRouter 未找到匹配 Agent"
                })

        # 4. 检查是否有可用工具
        if not selected_adapter:
            fix_hints = self._get_fix_hints(task_type)
            return self._create_result(
                ok=False,
                mode="unavailable",
                task_id=task_id,
                task_type=task_type,
                error=f"没有可用的工具处理 {task_type} 类型任务",
                warnings=warnings,
                fix_hints=fix_hints,
                tool_trace=tool_trace,
                confidence=0.0
            )

        used_tools.append(selected_adapter.TOOL_NAME)

        # 5. 执行任务
        task = {
            "goal": message,
            "prompt": message,
            "task_type": task_type,
            **(context or {})
        }

        import time
        start_time = time.time()
        result = selected_adapter.run(task)
        duration_ms = int((time.time() - start_time) * 1000)

        # 从 local agent 结果中提取 fix_hints
        agent_fix_hints = []
        if isinstance(result, dict):
            agent_data = result.get("result", result.get("data", {}))
            if isinstance(agent_data, dict):
                agent_fix_hints = agent_data.get("fix_hints", [])
                agent_suggestions = agent_data.get("suggestions", [])
                if agent_suggestions and not agent_fix_hints:
                    agent_fix_hints = agent_suggestions
            # 也检查顶层
            if not agent_fix_hints:
                agent_fix_hints = result.get("fix_hints", [])
            if not agent_fix_hints:
                agent_fix_hints = result.get("warnings", [])

        tool_trace.append({
            "tool": selected_adapter.TOOL_NAME,
            "action": "执行任务",
            "status": "done" if result.get("ok") else "failed",
            "summary": result.get("error", "执行完成") if not result.get("ok") else "执行成功",
            "duration_ms": duration_ms
        })

        if not result.get("ok"):
            # 合并 agent 自身的 fix_hints 和 runtime 的 fix_hints
            combined_hints = fix_hints or agent_fix_hints or self._get_fix_hints(task_type)
            return self._create_result(
                ok=False,
                mode="local",
                task_id=task_id,
                task_type=task_type,
                used_tools=used_tools,
                tool_trace=tool_trace,
                error=result.get("error", "任务执行失败"),
                warnings=result.get("warnings", []),
                fix_hints=combined_hints,
                confidence=0.0
            )

        # 6. 提取内容和元数据
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
                warnings=["本地工具未返回有效内容"],
                fix_hints=fix_hints or self._get_fix_hints(task_type),
                confidence=0.0
            )

        # 7. 结果验证（Boss 模块跳过严格验证，由模块执行器自行处理）
        verification = {"passed": True, "score": 100, "issues": []}
        is_boss_mission = context and context.get("boss_mission")
        if self._result_verifier and not is_boss_mission:
            # Use strict mode for task types where partial means real failure
            strict_task_types = {"website", "code"}
            strict = task_type in strict_task_types
            verification = self._result_verifier.verify(task_type, {
                "final_answer": content,
                "sources": sources,
                "deliverables": result.get("result", {})
            }, strict=strict)

            tool_trace.append({
                "tool": "result_verifier",
                "action": "结果验证",
                "status": "passed" if verification["passed"] else "failed",
                "summary": f"验证得分: {verification['score']}, 问题: {len(verification.get('issues', []))}",
                "duration_ms": 0
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
                    final_answer=content,
                    error="结果验证失败",
                    warnings=verification.get("issues", []),
                    fix_hints=fix_hints or self._get_fix_hints(task_type),
                    verification_result=verification,
                    confidence=0.0
                )

        # 8. 构建最终结果
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
            confidence=self._calculate_confidence(verification, sources, metadata, classification_confidence),
            warnings=warnings,
            fix_hints=fix_hints
        )

    def _map_agent_to_adapter(self, agent_id: str) -> Optional[str]:
        """映射 Agent ID 到适配器名称

        正确映射：
        - CLI Agent -> 对应的 CLI Adapter
        - HTTP Service -> 对应的 HTTP Adapter
        - API Agent -> ApiModelAdapter
        - Local Agent -> 对应的 LocalModuleAdapter
        """
        mapping = {
            # CLI Agent
            "claude": "claude_code",
            "codex": "claude_code",

            # HTTP Service
            "ollama": "ollama",
            "comfyui": "comfyui",

            # API Agent
            "mimo": "mimo",
            "deepseek": "api_models",
            "openai": "api_models",
            "claude_api": "api_models",

            # Local Agent — 通过 LocalModuleAdapter 执行
            "data_agent": "data_agent",
            "image_agent": "image_agent",
            "marketing_agent": "marketing_agent",
            "research_agent": "research_agent",
            "website_agent": "website_agent",

            # 兼容短名（AgentRouter 可能返回不带 _agent 后缀的 id）
            "image": "image_agent",
            "data": "data_tools",
            "marketing": "marketing_agent",
        }
        return mapping.get(agent_id)

    def _fallback_select_adapter(self, task_type: str, message: str):
        """Fallback 适配器选择"""
        # 图片任务：优先 image_agent（LocalModuleAdapter），再 ComfyUI
        if task_type == "image":
            if "image_agent" in self._adapters:
                return self._adapters["image_agent"]
            return None

        # 数据任务：优先 data_agent（LocalModuleAdapter），再 DataAdapter
        if task_type == "data":
            if "data_agent" in self._adapters:
                return self._adapters["data_agent"]
            if "data_tools" in self._adapters:
                return self._adapters["data_tools"]
            return None

        # 代码任务只使用显式的 Claude Code 适配器，不提供本地代码执行。
        if task_type == "code":
            if "claude_code" in self._adapters:
                adapter = self._adapters["claude_code"]
                if adapter.health_check().get("available"):
                    return adapter

        # 调研任务使用无浏览器的模型或 API 适配器。
        if task_type in {"research", "competitor_analysis", "market_analysis"}:
            if "mimo" in self._adapters:
                adapter = self._adapters["mimo"]
                if adapter.health_check().get("available"):
                    return adapter

        # 其他任务：优先 Ollama，然后 API
        if "ollama" in self._adapters:
            adapter = self._adapters["ollama"]
            if adapter.health_check().get("available"):
                return adapter

        if "api_models" in self._adapters:
            adapter = self._adapters["api_models"]
            if adapter.health_check().get("available"):
                return adapter

        return None

    def _get_required_capabilities(self, task_type: str) -> List[str]:
        """获取任务所需能力"""
        capabilities = {
            "image": ["image_generation"],
            "data": ["data_analysis"],
            "research": ["web_search"],
            "website": ["reasoning"],
            "code": ["code_execution"],
            "marketing": ["reasoning"],
            "chat": ["chat"],
        }
        return capabilities.get(task_type, ["chat"])

    def _get_fix_hints(self, task_type: str) -> List[str]:
        """获取修复建议"""
        hints = {
            "image": [
                "请安装 ComfyUI: https://github.com/comfyanonymous/ComfyUI",
                "启动 ComfyUI: cd ComfyUI && python main.py"
            ],
            "data": [
                "请安装数据分析依赖: pip install pandas openpyxl matplotlib"
            ],
            "research": [
                "请配置 MIMO_API_KEY 以启用联网搜索",
                "或安装 Playwright: pip install playwright && playwright install chromium"
            ],
            "website": [
                "请配置至少一个 API Key（DeepSeek/OpenAI/Claude）"
            ],
            "code": [
                "请安装 Claude Code: npm install -g @anthropic-ai/claude-code",
                "或配置 API Key"
            ],
            "marketing": [
                "请配置至少一个 API Key（DeepSeek/OpenAI/Claude）"
            ],
        }
        return hints.get(task_type, ["请配置至少一个 API Key"])

    def _calculate_confidence(self, verification: Dict, sources: List, metadata: Dict, classification_confidence: float) -> float:
        """计算置信度"""
        confidence = classification_confidence * 0.3  # 分类置信度

        if verification.get("passed"):
            confidence += 0.3
        if verification.get("score", 0) >= 90:
            confidence += 0.1
        if sources and len(sources) > 0:
            confidence += 0.2
        if metadata.get("used_web_search"):
            confidence += 0.1

        return min(confidence, 1.0)

    def _create_result(self, **kwargs) -> Dict[str, Any]:
        """创建统一的返回结构"""
        return {
            "ok": kwargs.get("ok", False),
            "mode": kwargs.get("mode", "local"),
            "task_id": kwargs.get("task_id", ""),
            "task_type": kwargs.get("task_type", "unknown"),
            "final_answer": kwargs.get("final_answer", ""),
            "deliverables": kwargs.get("deliverables", {}),
            "used_tools": kwargs.get("used_tools", []),
            "tool_trace": kwargs.get("tool_trace", []),
            "search_mode": kwargs.get("search_mode", "none"),
            "used_web_search": kwargs.get("used_web_search", False),
            "sources": kwargs.get("sources", []),
            "verification_result": kwargs.get("verification_result", {}),
            "qa": kwargs.get("verification_result", {}),
            "confidence": kwargs.get("confidence", 0.0),
            "warnings": kwargs.get("warnings", []),
            "error": kwargs.get("error", ""),
            "fix_hints": kwargs.get("fix_hints", []),
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
