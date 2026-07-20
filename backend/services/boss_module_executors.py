"""
Boss Module Executors — 通用模块级执行器

每个 executor 实现 ModuleExecutor 接口：
- execute(mission, module, goal, context) -> ExecutionResult

注册表根据 (template_id, module_id) 分发到具体执行器。
未注册的模块 fallback 到 LocalAgentRuntime。

设计原则：
- 系统核心使用通用模块定义，不绑定具体行业
- 业务特定执行器仅用于旧模板 ID 的向后兼容
- 新模板统一使用 DefaultModuleExecutor + 通用 prompt
"""
import json
from abc import ABC, abstractmethod
from datetime import datetime
from typing import Dict, Any, List, Optional
from backend.logger import get_logger

logger = get_logger()


class ExecutionResult:
    """模块执行结果"""

    def __init__(self, ok: bool, final_answer: str = "",
                 structured_output: Dict[str, Any] = None,
                 confidence: float = 0.0, warnings: List[str] = None,
                 used_tools: List[str] = None, mode: str = "",
                 error: str = "", next_actions: List[str] = None,
                 provider: str = "", qa_status: str = ""):
        self.ok = ok
        self.final_answer = final_answer
        self.structured_output = structured_output or {}
        self.confidence = confidence
        self.warnings = warnings or []
        self.used_tools = used_tools or []
        self.mode = mode
        self.error = error
        self.next_actions = next_actions or []
        self.provider = provider
        self.qa_status = qa_status  # v2: QA 状态 pass/partial/needs_input/failed

    def to_dict(self) -> Dict[str, Any]:
        return {
            "ok": self.ok,
            "final_answer": self.final_answer,
            "structured_output": self.structured_output,
            "confidence": self.confidence,
            "warnings": self.warnings,
            "used_tools": self.used_tools,
            "mode": self.mode,
            "error": self.error,
            "next_actions": self.next_actions,
            "provider": self.provider,
            "qa_status": self.qa_status,
        }


class ModuleExecutor(ABC):
    """模块执行器接口"""

    def __init__(self):
        self._provider = None

    @abstractmethod
    def execute(self, goal: str, module_id: str,
                mission_id: str, context: Dict[str, Any] = None) -> ExecutionResult:
        """执行模块"""
        pass

    def _get_provider(self):
        """延迟加载 Provider"""
        if self._provider is None:
            from backend.config import BOSS_EXECUTION_PROVIDER
            from backend.services.boss_execution_providers import get_provider_registry
            registry = get_provider_registry()
            provider, warnings = registry.get_available_provider(BOSS_EXECUTION_PROVIDER)
            self._provider = provider
            self._provider_warnings = warnings
        return self._provider


# ── 电商选品市场调研执行器 ──────────────────────────────

class EcommerceMarketResearchExecutor(ModuleExecutor):
    """电商市场调研执行器 — 通过 Provider 获取市场数据"""

    def execute(self, goal: str, module_id: str,
                mission_id: str, context: Dict[str, Any] = None) -> ExecutionResult:
        context = context or {}
        warnings = []

        # 获取浏览器自动化审批状态
        allow_browser_automation = context.get("allow_browser_automation", False)

        # 获取 Provider
        provider = self._get_provider()
        provider_warnings = getattr(self, '_provider_warnings', [])
        warnings.extend(provider_warnings)

        # 记录 provider_selected 事件
        from backend.services.boss_command_center import get_boss_command_center
        service = get_boss_command_center()
        service._log_event(mission_id, "provider_selected", f"使用 Provider: {provider.name}",
                          module_id=module_id, payload={"provider": provider.name})
        if provider_warnings:
            service._log_event(mission_id, "provider_fallback",
                              f"Provider fallback: {'; '.join(provider_warnings)}",
                              module_id=module_id,
                              payload={"provider": provider.name, "warnings": provider_warnings})

        # 调用 Provider 执行市场调研
        try:
            provider_result = provider.execute_market_research(goal, context,
                                                               allow_browser_automation=allow_browser_automation)
        except Exception as e:
            logger.error(f"EcommerceMarketResearch provider failed: {e}")
            # Fallback 到 LocalAgentRuntime
            service._log_event(mission_id, "provider_fallback",
                              f"Provider {provider.name} 失败，fallback 到 LocalAgentRuntime: {str(e)[:100]}",
                              module_id=module_id, payload={"error": str(e)})
            if provider.name == "hermes":
                service._log_event(mission_id, "hermes_failed", f"Hermes 执行失败: {str(e)[:100]}",
                                  module_id=module_id, payload={"error": str(e)})
            return self._fallback_to_runtime(goal, module_id, mission_id, context, provider_reason=str(e))

        # 检查是否被审批闸门阻止
        if provider_result.get("blocked"):
            service._log_event(mission_id, "approval_required",
                              f"浏览器自动化需要用户授权（模块: {module_id}）",
                              module_id=module_id, payload={"blocked_reason": "approval_required"})
            from backend.services.boss_execution_providers import build_approval_required_output
            structured = build_approval_required_output(module_id)
            return ExecutionResult(
                ok=False,
                final_answer="浏览器自动化采集需要用户确认后才能执行",
                structured_output=structured,
                confidence=0.0,
                warnings=["浏览器自动化采集需要用户确认后才能执行"],
                used_tools=[],
                mode="blocked",
                error="浏览器自动化需要用户授权",
                provider=provider.name,
            )

        if provider.name == "hermes":
            service._log_event(mission_id, "hermes_invoked", "调用 Hermes CLI",
                              module_id=module_id, payload={"provider": "hermes"})

        if not provider_result.get("ok"):
            if provider.name == "hermes":
                service._log_event(mission_id, "hermes_failed",
                                  f"Hermes 返回失败: {provider_result.get('error', '未知错误')[:100]}",
                                  module_id=module_id, payload=provider_result)
            # Fallback 到 LocalAgentRuntime
            service._log_event(mission_id, "provider_fallback",
                              f"Provider {provider.name} 返回失败，fallback 到 LocalAgentRuntime",
                              module_id=module_id, payload=provider_result)
            return self._fallback_to_runtime(goal, module_id, mission_id, context,
                                            provider_reason=provider_result.get("error", "Hermes 执行失败"))

        # 如果是 Hermes provider，记录 hermes_response_parsed 和 tool_calls 事件
        if provider.name == "hermes":
            service._log_event(mission_id, "hermes_response_parsed", "Hermes 响应解析成功",
                              module_id=module_id, payload={
                                  "has_summary": bool(provider_result.get("summary")),
                                  "has_evidence": bool(provider_result.get("evidence")),
                                  "has_competitors": bool(provider_result.get("competitors")),
                              })

            # 记录 tool_calls 事件
            tool_calls = provider_result.get("tool_calls", [])
            if tool_calls:
                service._log_event(mission_id, "hermes_tool_call_detected",
                                  f"Hermes 记录了 {len(tool_calls)} 次工具调用",
                                  module_id=module_id, payload={"tool_calls": tool_calls})

        # 标准化 structured_output
        from backend.services.boss_execution_providers import create_standard_output
        structured = create_standard_output(
            status="success",
            summary=provider_result.get("summary", ""),
            evidence=provider_result.get("evidence", []),
            evidence_files=provider_result.get("evidence_files", []),
            screenshots=provider_result.get("screenshots", []),
            tool_calls=provider_result.get("tool_calls", []),
            missing_evidence=provider_result.get("missing_evidence", []),
            evidence_gate_passed=provider_result.get("evidence_gate_passed", True),
            competitors=provider_result.get("competitors", []),
            pricing=provider_result.get("pricing", {}),
            warnings=provider_result.get("warnings", []),
            provider=provider.name,
            raw_data=provider_result.get("raw_data", {}),
        )

        # 记录 evidence gate 事件
        evidence_gate_passed = structured.get("evidence_gate_passed", True)
        if evidence_gate_passed:
            service._log_event(mission_id, "evidence_gate_passed",
                              f"证据门槛通过: 收集到 {len(structured['evidence'])} 条证据",
                              module_id=module_id, payload={"evidence_count": len(structured["evidence"])})
        else:
            service._log_event(mission_id, "evidence_gate_failed",
                              f"证据门槛未通过: {', '.join(structured.get('missing_evidence', []))}",
                              module_id=module_id, payload={"missing_evidence": structured.get("missing_evidence", [])})
            # 证据不足时，status 标记为 partial
            structured["status"] = "partial"

        # 记录 evidence_collected 和 structured_output_generated 事件
        service._log_event(mission_id, "evidence_collected",
                          f"收集到 {len(structured['evidence'])} 条证据",
                          module_id=module_id, payload={"count": len(structured["evidence"])})
        service._log_event(mission_id, "structured_output_generated",
                          f"生成标准化输出",
                          module_id=module_id, payload={"provider": provider.name})

        warnings.extend(structured.get("warnings", []))

        # 如果 evidence gate 未通过，降低 confidence
        confidence = 0.7 if evidence_gate_passed else 0.3

        return ExecutionResult(
            ok=True,
            final_answer=structured.get("summary", ""),
            structured_output=structured,
            confidence=confidence,
            warnings=warnings,
            used_tools=[provider.name],
            mode="provider",
            provider=provider.name,
            next_actions=[],
        )

    def _fallback_to_runtime(self, goal: str, module_id: str, mission_id: str,
                             context: Dict[str, Any], provider_reason: str = "") -> ExecutionResult:
        """Fallback 到 LocalAgentRuntime

        必须返回标准化 structured_output，不能是空对象。
        evidence_gate_passed 始终为 False（因为没有通过 Hermes 真实采集）。
        """
        from backend.services.boss_command_center import get_boss_command_center
        from backend.services.boss_execution_providers import build_fallback_structured_output
        service = get_boss_command_center()

        # 记录 evidence_gate_failed 事件
        service._log_event(mission_id, "evidence_gate_failed",
                          f"证据门槛未通过: Hermes 失败/超时，无法采集真实证据",
                          module_id=module_id, payload={
                              "reason": provider_reason or "Hermes 执行失败",
                              "missing_evidence": ["Hermes 工具链未采集到数据"],
                              "provider": "hermes",
                              "module_id": module_id,
                          })

        # 记录 fallback_partial_result 事件
        service._log_event(mission_id, "fallback_partial_result",
                          f"Hermes 失败，fallback 到 LocalAgentRuntime，仅返回文本分析（无真实数据采集）",
                          module_id=module_id, payload={
                              "provider": "local_heuristic_fallback",
                              "module_id": module_id,
                          })

        from backend.services.local_agent_runtime import get_local_agent_runtime
        runtime = get_local_agent_runtime()
        result = runtime.execute(goal, context)

        # 构建标准化 structured_output
        structured = build_fallback_structured_output(
            module_id=module_id,
            provider_reason=provider_reason or "Hermes 执行失败",
            warnings=result.get("warnings", []),
        )

        # 记录 structured_output_generated 事件
        service._log_event(mission_id, "structured_output_generated",
                          f"生成标准化输出（partial, fallback）",
                          module_id=module_id, payload={"provider": "local_heuristic_fallback"})

        return ExecutionResult(
            ok=result.get("ok", False),
            final_answer=result.get("final_answer", ""),
            structured_output=structured,
            confidence=0.3,  # fallback 时 confidence 固定为 0.3
            warnings=result.get("warnings", []) + [
                "Hermes 失败/超时，分析基于本地模型已有知识，无真实数据采集",
            ],
            used_tools=result.get("used_tools", []),
            mode=result.get("mode", ""),
            provider="local_heuristic_fallback",
        )


# ── 电商竞品分析执行器 ──────────────────────────────────

class EcommerceCompetitorAnalysisExecutor(ModuleExecutor):
    """竞品分析执行器"""

    def execute(self, goal: str, module_id: str,
                mission_id: str, context: Dict[str, Any] = None) -> ExecutionResult:
        context = context or {}
        # 从上下文获取市场调研结果
        prev_results = context.get("prev_results", {})
        market_data = prev_results.get("market", {}).get("structured_output", {})
        competitors = market_data.get("competitors", [])

        # 获取浏览器自动化审批状态
        allow_browser_automation = context.get("allow_browser_automation", False)

        # 获取 Provider
        provider = self._get_provider()
        provider_warnings = getattr(self, '_provider_warnings', [])

        # 记录 provider_selected 事件
        from backend.services.boss_command_center import get_boss_command_center
        service = get_boss_command_center()
        service._log_event(mission_id, "provider_selected", f"使用 Provider: {provider.name}",
                          module_id=module_id, payload={"provider": provider.name})
        if provider_warnings:
            service._log_event(mission_id, "provider_fallback",
                              f"Provider fallback: {'; '.join(provider_warnings)}",
                              module_id=module_id,
                              payload={"provider": provider.name, "warnings": provider_warnings})

        # 调用 Provider 执行竞品分析
        try:
            provider_result = provider.execute_competitor_analysis(goal, competitors, context,
                                                                   allow_browser_automation=allow_browser_automation)
        except Exception as e:
            logger.error(f"EcommerceCompetitorAnalysis provider failed: {e}")
            service._log_event(mission_id, "provider_fallback",
                              f"Provider {provider.name} 失败: {str(e)[:100]}",
                              module_id=module_id, payload={"error": str(e)})
            if provider.name == "hermes":
                service._log_event(mission_id, "hermes_failed", f"Hermes 执行失败: {str(e)[:100]}",
                                  module_id=module_id, payload={"error": str(e)})
            return self._fallback_to_runtime(goal, module_id, mission_id, context, competitors,
                                            provider_reason=str(e))

        # 检查是否被审批闸门阻止
        if provider_result.get("blocked"):
            service._log_event(mission_id, "approval_required",
                              f"浏览器自动化需要用户授权（模块: {module_id}）",
                              module_id=module_id, payload={"blocked_reason": "approval_required"})
            from backend.services.boss_execution_providers import build_approval_required_output
            structured = build_approval_required_output(module_id)
            return ExecutionResult(
                ok=False,
                final_answer="浏览器自动化采集需要用户确认后才能执行",
                structured_output=structured,
                confidence=0.0,
                warnings=["浏览器自动化采集需要用户确认后才能执行"],
                used_tools=[],
                mode="blocked",
                error="浏览器自动化需要用户授权",
                provider=provider.name,
            )

        if provider.name == "hermes":
            service._log_event(mission_id, "hermes_invoked", "调用 Hermes CLI",
                              module_id=module_id, payload={"provider": "hermes"})

        if not provider_result.get("ok"):
            if provider.name == "hermes":
                service._log_event(mission_id, "hermes_failed",
                                  f"Hermes 返回失败: {provider_result.get('error', '未知错误')[:100]}",
                                  module_id=module_id, payload=provider_result)
            # Fallback 到 LocalAgentRuntime
            service._log_event(mission_id, "provider_fallback",
                              f"Provider {provider.name} 返回失败，fallback 到 LocalAgentRuntime",
                              module_id=module_id, payload=provider_result)
            return self._fallback_to_runtime(goal, module_id, mission_id, context, competitors,
                                            provider_reason=provider_result.get("error", "Hermes 执行失败"))

        # 如果是 Hermes provider，记录 hermes_response_parsed 事件
        if provider.name == "hermes":
            service._log_event(mission_id, "hermes_response_parsed", "Hermes 响应解析成功",
                              module_id=module_id, payload={
                                  "has_summary": bool(provider_result.get("summary")),
                                  "has_competitors": bool(provider_result.get("competitors")),
                                  "has_pricing": bool(provider_result.get("pricing")),
                              })

            # 记录 tool_calls 事件
            tool_calls = provider_result.get("tool_calls", [])
            if tool_calls:
                service._log_event(mission_id, "hermes_tool_call_detected",
                                  f"Hermes 记录了 {len(tool_calls)} 次工具调用",
                                  module_id=module_id, payload={"tool_calls": tool_calls})

        # 标准化 structured_output
        from backend.services.boss_execution_providers import create_standard_output
        structured = create_standard_output(
            status="success",
            summary=provider_result.get("summary", ""),
            evidence=provider_result.get("evidence", []),
            evidence_files=provider_result.get("evidence_files", []),
            screenshots=provider_result.get("screenshots", []),
            tool_calls=provider_result.get("tool_calls", []),
            missing_evidence=provider_result.get("missing_evidence", []),
            evidence_gate_passed=provider_result.get("evidence_gate_passed", True),
            competitors=provider_result.get("competitors", competitors),
            pricing=provider_result.get("pricing", {}),
            warnings=provider_result.get("warnings", []),
            provider=provider.name,
            raw_data=provider_result.get("raw_data", {}),
        )

        # 记录 evidence gate 事件
        evidence_gate_passed = structured.get("evidence_gate_passed", True)
        if evidence_gate_passed:
            service._log_event(mission_id, "evidence_gate_passed",
                              f"证据门槛通过: 收集到 {len(structured['evidence'])} 条证据和 {len(structured['competitors'])} 个竞品",
                              module_id=module_id, payload={
                                  "evidence_count": len(structured["evidence"]),
                                  "competitor_count": len(structured["competitors"]),
                              })
        else:
            service._log_event(mission_id, "evidence_gate_failed",
                              f"证据门槛未通过: {', '.join(structured.get('missing_evidence', []))}",
                              module_id=module_id, payload={"missing_evidence": structured.get("missing_evidence", [])})
            # 证据不足时，status 标记为 partial
            structured["status"] = "partial"

        service._log_event(mission_id, "structured_output_generated",
                          f"生成标准化输出",
                          module_id=module_id, payload={"provider": provider.name})

        warnings = provider_warnings + structured.get("warnings", [])

        # 如果 evidence gate 未通过，降低 confidence
        confidence = 0.7 if evidence_gate_passed else 0.3

        return ExecutionResult(
            ok=True,
            final_answer=structured.get("summary", ""),
            structured_output=structured,
            confidence=confidence,
            warnings=warnings,
            used_tools=[provider.name],
            mode="provider",
            provider=provider.name,
        )

    def _fallback_to_runtime(self, goal: str, module_id: str, mission_id: str,
                             context: Dict[str, Any], competitors: List[Dict],
                             provider_reason: str = "") -> ExecutionResult:
        """Fallback 到 LocalAgentRuntime"""
        from backend.services.boss_command_center import get_boss_command_center
        from backend.services.boss_execution_providers import build_fallback_structured_output
        service = get_boss_command_center()

        # 记录 evidence_gate_failed 事件
        service._log_event(mission_id, "evidence_gate_failed",
                          f"证据门槛未通过: Hermes 失败/超时，无法采集真实竞品数据",
                          module_id=module_id, payload={
                              "reason": provider_reason or "Hermes 执行失败",
                              "missing_evidence": ["Hermes 工具链未采集到竞品数据"],
                              "provider": "hermes",
                              "module_id": module_id,
                          })

        service._log_event(mission_id, "fallback_partial_result",
                          f"Hermes 失败，fallback 到 LocalAgentRuntime，仅返回文本分析（无真实数据采集）",
                          module_id=module_id, payload={
                              "provider": "local_heuristic_fallback",
                              "module_id": module_id,
                          })

        prompt = f"请基于以下信息，对电商业务「{goal}」做竞品分析：\n\n"
        if competitors:
            prompt += f"已知竞品：{json.dumps(competitors, ensure_ascii=False)}\n\n"
        prompt += (
            "请输出：\n"
            "1. 竞品对比表（名称、价格、核心卖点、目标用户）\n"
            "2. 价格区间分析\n"
            "3. 我们的差异化定位\n"
            "4. 风险提示\n"
            "5. 建议定价范围"
        )

        from backend.services.local_agent_runtime import get_local_agent_runtime
        runtime = get_local_agent_runtime()
        result = runtime.execute(prompt, context)

        text = result.get("final_answer", "")
        pricing = self._extract_pricing(text)

        # 构建标准化 structured_output
        structured = build_fallback_structured_output(
            module_id=module_id,
            provider_reason=provider_reason or "Hermes 执行失败",
            warnings=result.get("warnings", []),
            extra={"competitors": competitors, "pricing": pricing},
        )

        service._log_event(mission_id, "structured_output_generated",
                          f"生成标准化输出（partial, fallback）",
                          module_id=module_id, payload={"provider": "local_heuristic_fallback"})

        return ExecutionResult(
            ok=result.get("ok", False),
            final_answer=text,
            structured_output=structured,
            confidence=0.3,
            warnings=result.get("warnings", []) + [
                "Hermes 失败/超时，竞品分析基于本地模型已有知识，无真实数据采集",
            ],
            used_tools=result.get("used_tools", []),
            mode=result.get("mode", ""),
            provider="local_heuristic_fallback",
        )

    def _extract_pricing(self, text: str) -> Dict[str, Any]:
        """尝试从文本中提取定价建议"""
        import re
        prices = re.findall(r'[\d.]+\s*(?:元|￥|¥|RMB|USD|\$)', text)
        return {
            "mentioned_prices": prices[:10],
            "raw_text": text[:300] if text else "",
        }


# ── 电商上架物料包执行器 ────────────────────────────────

class EcommerceListingPackExecutor(ModuleExecutor):
    """上架物料包执行器 — 标题/卖点/详情/定价"""

    def execute(self, goal: str, module_id: str,
                mission_id: str, context: Dict[str, Any] = None) -> ExecutionResult:
        context = context or {}
        prev_results = context.get("prev_results", {})
        # Phase 6.28: fix — 模块 ID 是 "market" 不是 "competitor_analysis"
        market_data = prev_results.get("market", {}).get("structured_output", {})
        competitors = market_data.get("competitors", [])
        pricing = market_data.get("pricing", {})

        # 获取浏览器自动化审批状态
        allow_browser_automation = context.get("allow_browser_automation", False)

        # 获取 Provider
        provider = self._get_provider()
        provider_warnings = getattr(self, '_provider_warnings', [])

        # 记录 provider_selected 事件
        from backend.services.boss_command_center import get_boss_command_center
        service = get_boss_command_center()
        service._log_event(mission_id, "provider_selected", f"使用 Provider: {provider.name}",
                          module_id=module_id, payload={"provider": provider.name})
        if provider_warnings:
            service._log_event(mission_id, "provider_fallback",
                              f"Provider fallback: {'; '.join(provider_warnings)}",
                              module_id=module_id,
                              payload={"provider": provider.name, "warnings": provider_warnings})

        # 调用 Provider 执行上架物料包生成
        try:
            provider_result = provider.execute_listing_pack(goal, competitors, pricing, context,
                                                            allow_browser_automation=allow_browser_automation)
        except Exception as e:
            logger.error(f"EcommerceListingPack provider failed: {e}")
            service._log_event(mission_id, "provider_fallback",
                              f"Provider {provider.name} 失败: {str(e)[:100]}",
                              module_id=module_id, payload={"error": str(e)})
            if provider.name == "hermes":
                service._log_event(mission_id, "hermes_failed", f"Hermes 执行失败: {str(e)[:100]}",
                                  module_id=module_id, payload={"error": str(e)})
            return self._fallback_to_runtime(goal, module_id, mission_id, context, competitors, pricing,
                                            provider_reason=str(e))

        # 检查是否被审批闸门阻止
        if provider_result.get("blocked"):
            service._log_event(mission_id, "approval_required",
                              f"浏览器自动化需要用户授权（模块: {module_id}）",
                              module_id=module_id, payload={"blocked_reason": "approval_required"})
            from backend.services.boss_execution_providers import build_approval_required_output
            structured = build_approval_required_output(module_id)
            return ExecutionResult(
                ok=False,
                final_answer="浏览器自动化采集需要用户确认后才能执行",
                structured_output=structured,
                confidence=0.0,
                warnings=["浏览器自动化采集需要用户确认后才能执行"],
                used_tools=[],
                mode="blocked",
                error="浏览器自动化需要用户授权",
                provider=provider.name,
            )

        if provider.name == "hermes":
            service._log_event(mission_id, "hermes_invoked", "调用 Hermes CLI",
                              module_id=module_id, payload={"provider": "hermes"})

        if not provider_result.get("ok"):
            if provider.name == "hermes":
                service._log_event(mission_id, "hermes_failed",
                                  f"Hermes 返回失败: {provider_result.get('error', '未知错误')[:100]}",
                                  module_id=module_id, payload=provider_result)
            # Fallback 到 LocalAgentRuntime
            service._log_event(mission_id, "provider_fallback",
                              f"Provider {provider.name} 返回失败，fallback 到 LocalAgentRuntime",
                              module_id=module_id, payload=provider_result)
            return self._fallback_to_runtime(goal, module_id, mission_id, context, competitors, pricing,
                                            provider_reason=provider_result.get("error", "Hermes 执行失败"))

        # 如果是 Hermes provider，记录 hermes_response_parsed 事件
        if provider.name == "hermes":
            service._log_event(mission_id, "hermes_response_parsed", "Hermes 响应解析成功",
                              module_id=module_id, payload={
                                  "has_summary": bool(provider_result.get("summary")),
                                  "has_listing_copy": bool(provider_result.get("listing_copy")),
                                  "has_image_plan": bool(provider_result.get("image_plan")),
                              })

            # 记录 tool_calls 事件
            tool_calls = provider_result.get("tool_calls", [])
            if tool_calls:
                service._log_event(mission_id, "hermes_tool_call_detected",
                                  f"Hermes 记录了 {len(tool_calls)} 次工具调用",
                                  module_id=module_id, payload={"tool_calls": tool_calls})

        # 标准化 structured_output
        from backend.services.boss_execution_providers import create_standard_output
        structured = create_standard_output(
            status="success",
            summary=provider_result.get("summary", ""),
            evidence=provider_result.get("evidence", []),
            evidence_files=provider_result.get("evidence_files", []),
            screenshots=provider_result.get("screenshots", []),
            tool_calls=provider_result.get("tool_calls", []),
            missing_evidence=provider_result.get("missing_evidence", []),
            evidence_gate_passed=provider_result.get("evidence_gate_passed", True),
            listing_copy=provider_result.get("listing_copy", ""),
            pricing=provider_result.get("pricing", pricing),
            image_plan=provider_result.get("image_plan", {}),
            next_actions=provider_result.get("next_actions", []),
            warnings=provider_result.get("warnings", []),
            provider=provider.name,
            raw_data=provider_result.get("raw_data", {}),
        )

        # 记录 evidence gate 事件
        evidence_gate_passed = structured.get("evidence_gate_passed", True)
        if evidence_gate_passed:
            service._log_event(mission_id, "evidence_gate_passed",
                              f"证据门槛通过: 基于前序 evidence 生成上架文案",
                              module_id=module_id, payload={"evidence_count": len(structured["evidence"])})
        else:
            service._log_event(mission_id, "evidence_gate_failed",
                              f"证据门槛未通过: {', '.join(structured.get('missing_evidence', []))}",
                              module_id=module_id, payload={"missing_evidence": structured.get("missing_evidence", [])})
            # 证据不足时，status 标记为 partial
            structured["status"] = "partial"

        service._log_event(mission_id, "structured_output_generated",
                          f"生成标准化输出",
                          module_id=module_id, payload={"provider": provider.name})

        warnings = provider_warnings + structured.get("warnings", [])

        # 如果 evidence gate 未通过，降低 confidence
        confidence = 0.7 if evidence_gate_passed else 0.3

        return ExecutionResult(
            ok=True,
            final_answer=structured.get("summary", ""),
            structured_output=structured,
            confidence=confidence,
            warnings=warnings,
            used_tools=[provider.name],
            mode="provider",
            provider=provider.name,
            next_actions=structured.get("next_actions", []),
        )

    def _fallback_to_runtime(self, goal: str, module_id: str, mission_id: str,
                             context: Dict[str, Any], competitors: List[Dict],
                             pricing: Dict[str, Any], provider_reason: str = "") -> ExecutionResult:
        """Fallback 到 LocalAgentRuntime"""
        from backend.services.boss_command_center import get_boss_command_center
        from backend.services.boss_execution_providers import build_fallback_structured_output
        service = get_boss_command_center()

        # 记录 evidence_gate_failed 事件
        service._log_event(mission_id, "evidence_gate_failed",
                          f"证据门槛未通过: Hermes 失败/超时，无法生成基于真实数据的上架文案",
                          module_id=module_id, payload={
                              "reason": provider_reason or "Hermes 执行失败",
                              "missing_evidence": ["上架文案需要基于前序 evidence，但无真实数据采集"],
                              "provider": "hermes",
                              "module_id": module_id,
                          })

        service._log_event(mission_id, "fallback_partial_result",
                          f"Hermes 失败，fallback 到 LocalAgentRuntime，仅返回文本分析（无真实数据采集）",
                          module_id=module_id, payload={
                              "provider": "local_heuristic_fallback",
                              "module_id": module_id,
                          })

        prompt = (
            f"请为以下产品生成闲鱼/电商上架物料包：{goal}\n\n"
            f"已知竞品信息：{json.dumps(competitors, ensure_ascii=False)}\n\n"
            f"请按以下结构输出：\n"
            f"1. **标题**（3 个备选，含关键词）\n"
            f"2. **核心卖点**（3-5 个，简洁有力）\n"
            f"3. **详情文案**（200-500 字，含规格/优势/使用场景）\n"
            f"4. **定价建议**（含成本分析和利润空间）\n"
            f"5. **SKU 建议**（规格/颜色/套餐）\n"
            f"6. **首图建议**（拍摄角度/风格/道具）"
        )

        from backend.services.local_agent_runtime import get_local_agent_runtime
        runtime = get_local_agent_runtime()
        result = runtime.execute(prompt, context)

        text = result.get("final_answer", "")
        image_plan = self._extract_image_plan(text)
        next_actions = [
            "根据定价建议确定最终价格",
            "拍摄首图（参考首图建议）",
            "上架商品并填写标题和详情",
        ]

        # 构建标准化 structured_output
        structured = build_fallback_structured_output(
            module_id=module_id,
            provider_reason=provider_reason or "Hermes 执行失败",
            warnings=result.get("warnings", []),
        )
        # listing 特有字段
        structured["listing_copy"] = text
        structured["image_plan"] = image_plan
        structured["pricing"] = pricing or {}
        structured["next_actions"] = next_actions

        service._log_event(mission_id, "structured_output_generated",
                          f"生成标准化输出（partial, fallback）",
                          module_id=module_id, payload={"provider": "local_heuristic_fallback"})

        return ExecutionResult(
            ok=result.get("ok", False),
            final_answer=text,
            structured_output=structured,
            confidence=0.3,
            warnings=result.get("warnings", []) + [
                "Hermes 失败/超时，上架文案基于本地模型已有知识，无真实数据采集",
            ],
            used_tools=result.get("used_tools", []),
            mode=result.get("mode", ""),
            next_actions=next_actions,
            provider="local_heuristic_fallback",
        )

    def _extract_image_plan(self, text: str) -> Dict[str, Any]:
        """提取图片/拍摄建议"""
        import re
        image_sections = re.findall(r'(?:首图|图片|拍摄|图片建议)[：:]\s*(.+?)(?:\n\n|\n\d|$)', text, re.DOTALL)
        return {
            "suggestions": [s.strip()[:200] for s in image_sections[:3]],
            "raw_text": text[:300] if text else "",
        }


# ── 注册表 ──────────────────────────────────────────────

# v2: 模块 owner 固定 — 每个模块只有一个主负责执行器
# 其他 Agent 只能作为后续优化，不在本轮引入多 Agent 抢任务
MODULE_OWNER = {
    "strategy": "local_heuristic",    # 战略摘要：本地模型
    "market": "hermes",                # 市场调研：Hermes 主负责（可 fallback）
    "marketing": "local_heuristic",    # 营销方案：本地模型
    "landing": "local_heuristic",      # 落地页：本地模型
    "actions": "local_heuristic",      # 执行清单：本地模型
}

# Phase 6.20: 默认注册表为空 — 所有模块走 DefaultModuleExecutor 通用路径。
# 旧业务执行器（EcommerceMarketResearchExecutor 等）仅在显式设置
# ACO_ENABLE_LEGACY_BUSINESS_EXECUTORS=true 时才注册。
# 旧业务执行器类定义保留，供有需要的部署环境 opt-in 使用。
_LEGACY_EXECUTOR_MAP = {
    "ecommerce_product_research": {
        "market": EcommerceMarketResearchExecutor,
        "competitor_analysis": EcommerceCompetitorAnalysisExecutor,
        "marketing": EcommerceListingPackExecutor,
    },
}

_EXECUTOR_REGISTRY: Dict[str, Dict[str, ModuleExecutor]] = {}


def _init_legacy_executors():
    """仅当环境变量 ACO_ENABLE_LEGACY_BUSINESS_EXECUTORS=true 时注册旧业务执行器"""
    import os
    if os.environ.get("ACO_ENABLE_LEGACY_BUSINESS_EXECUTORS", "").lower() == "true":
        for tpl_id, module_map in _LEGACY_EXECUTOR_MAP.items():
            _EXECUTOR_REGISTRY[tpl_id] = {mod_id: cls() for mod_id, cls in module_map.items()}
            # 同时注册到 canonical template ID（模板别名解析后的 ID）
            try:
                from backend.services.boss_command_center import get_boss_command_center
                service = get_boss_command_center()
                template = service.get_template(tpl_id)
                if template and template.get("aliased_to"):
                    canonical = template["aliased_to"]
                    if canonical not in _EXECUTOR_REGISTRY:
                        _EXECUTOR_REGISTRY[canonical] = _EXECUTOR_REGISTRY[tpl_id]
            except Exception:
                pass
        logger.info("Legacy business executors enabled via ACO_ENABLE_LEGACY_BUSINESS_EXECUTORS")


_init_legacy_executors()

# 默认 fallback executor（使用 LocalAgentRuntime）
_default_executor = None


class DefaultModuleExecutor(ModuleExecutor):
    """默认模块执行器 — 使用 LocalAgentRuntime"""

    def execute(self, goal: str, module_id: str,
                mission_id: str, context: Dict[str, Any] = None) -> ExecutionResult:
        from backend.services.boss_command_center import MODULE_DEFINITIONS, MODULE_ORDER
        prompt_template = MODULE_DEFINITIONS.get(module_id, {}).get("prompt_template", "")
        if not prompt_template:
            return ExecutionResult(ok=False, error=f"未知模块: {module_id}")

        prompt = prompt_template.format(goal=goal)

        # v1.5.1: 每个模块加 30s 超时，防止 openclaw 等慢 Agent 卡死整个 Mission
        import concurrent.futures
        try:
            from backend.services.local_agent_runtime import get_local_agent_runtime
            runtime = get_local_agent_runtime()
            with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
                future = pool.submit(runtime.execute, prompt, {
                    "boss_mission": True,
                    "mission_id": mission_id,
                    "mission_module": module_id,
                    "mission_goal": goal,
                })
                result = future.result(timeout=30)
        except concurrent.futures.TimeoutError:
            return ExecutionResult(
                ok=False, error=f"模块 {module_id} 执行超时（30s），已跳过",
                final_answer="该模块执行超时，请稍后重试或简化目标。",
                warnings=[f"{module_id} 超时"],
            )
        except Exception as e:
            return ExecutionResult(ok=False, error=str(e))

        # 标准化输出
        from backend.services.boss_execution_providers import create_standard_output
        owner = MODULE_OWNER.get(module_id, "local_heuristic")
        structured = create_standard_output(
            status="success" if result.get("ok") else "failed",
            summary=result.get("final_answer", "")[:500] if result.get("final_answer") else "",
            provider=f"{owner} (via DefaultModuleExecutor)",
        )

        return ExecutionResult(
            ok=result.get("ok", False),
            final_answer=result.get("final_answer", ""),
            structured_output=structured,
            confidence=result.get("confidence", 0.0),
            warnings=result.get("warnings", []),
            used_tools=result.get("used_tools", []),
            mode=result.get("mode", ""),
            error=result.get("error", ""),
            next_actions=result.get("next_actions", []),
            provider=owner,
        )


def get_executor(template_id: str, module_id: str) -> ModuleExecutor:
    """获取模块执行器"""
    template_executors = _EXECUTOR_REGISTRY.get(template_id, {})
    executor = template_executors.get(module_id)
    if executor:
        return executor
    return DefaultModuleExecutor()
