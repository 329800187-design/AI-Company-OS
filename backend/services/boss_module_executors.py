"""
Boss Module Executors — 模块级执行器

每个 executor 实现 ModuleExecutor 接口：
- execute(mission, module, goal, context) -> ExecutionResult

注册表根据 (template_id, module_id) 分发到具体执行器。
未注册的模块 fallback 到 LocalAgentRuntime。

V2: 引入 ExecutionProvider 抽象层
- executor 负责模块编排、事件、结构化输出整理
- provider 负责真实能力来源（市场调研、竞品分析、上架物料包生成）
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
                 provider: str = ""):
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

        # 获取 Provider
        provider = self._get_provider()
        provider_warnings = getattr(self, '_provider_warnings', [])
        warnings.extend(provider_warnings)

        # 记录 provider_selected 事件
        from backend.services.boss_command_center import get_boss_command_center
        service = get_boss_command_center()
        service._log_event(mission_id, "provider_selected", f"使用 Provider: {provider.name}",
                          module_id=module_id, payload={"provider": provider.name})

        # 调用 Provider 执行市场调研
        try:
            provider_result = provider.execute_market_research(goal, context)
        except Exception as e:
            logger.error(f"EcommerceMarketResearch provider failed: {e}")
            # Fallback 到 LocalAgentRuntime
            service._log_event(mission_id, "provider_fallback",
                              f"Provider {provider.name} 失败，fallback 到 LocalAgentRuntime: {str(e)[:100]}",
                              module_id=module_id, payload={"error": str(e)})
            return self._fallback_to_runtime(goal, module_id, mission_id, context)

        if not provider_result.get("ok"):
            return ExecutionResult(ok=False, error=provider_result.get("error", "Provider 执行失败"))

        # 标准化 structured_output
        from backend.services.boss_execution_providers import create_standard_output
        structured = create_standard_output(
            status="success",
            summary=provider_result.get("summary", ""),
            evidence=provider_result.get("evidence", []),
            competitors=provider_result.get("competitors", []),
            pricing=provider_result.get("pricing", {}),
            warnings=provider_result.get("warnings", []),
            provider=provider.name,
            raw_data=provider_result.get("raw_data", {}),
        )

        # 记录 evidence_collected 和 structured_output_generated 事件
        service._log_event(mission_id, "evidence_collected",
                          f"收集到 {len(structured['evidence'])} 条证据",
                          module_id=module_id, payload={"count": len(structured["evidence"])})
        service._log_event(mission_id, "structured_output_generated",
                          f"生成标准化输出",
                          module_id=module_id, payload={"provider": provider.name})

        warnings.extend(structured.get("warnings", []))

        return ExecutionResult(
            ok=True,
            final_answer=structured.get("summary", ""),
            structured_output=structured,
            confidence=0.7,
            warnings=warnings,
            used_tools=[provider.name],
            mode="provider",
            provider=provider.name,
            next_actions=[],
        )

    def _fallback_to_runtime(self, goal: str, module_id: str, mission_id: str,
                             context: Dict[str, Any]) -> ExecutionResult:
        """Fallback 到 LocalAgentRuntime"""
        from backend.services.local_agent_runtime import get_local_agent_runtime
        runtime = get_local_agent_runtime()
        result = runtime.execute(goal, context)

        return ExecutionResult(
            ok=result.get("ok", False),
            final_answer=result.get("final_answer", ""),
            structured_output={},
            confidence=result.get("confidence", 0.0),
            warnings=result.get("warnings", []),
            used_tools=result.get("used_tools", []),
            mode=result.get("mode", ""),
            provider="local_heuristic_fallback",
        )


# ── 电商竞品分析执行器 ──────────────────────────────────

class EcommerceCompetitorAnalysisExecutor(ModuleExecutor):
    """竞品分析执行器"""

    def execute(self, goal: str, module_id: str,
                mission_id: str, context: Dict[str, Any] = None) -> ExecutionResult:
        # 从上下文获取市场调研结果
        prev_results = context.get("prev_results", {})
        market_data = prev_results.get("market", {}).get("structured_output", {})
        competitors = market_data.get("competitors", [])

        # 获取 Provider
        provider = self._get_provider()
        provider_warnings = getattr(self, '_provider_warnings', [])

        # 记录 provider_selected 事件
        from backend.services.boss_command_center import get_boss_command_center
        service = get_boss_command_center()
        service._log_event(mission_id, "provider_selected", f"使用 Provider: {provider.name}",
                          module_id=module_id, payload={"provider": provider.name})

        # 调用 Provider 执行竞品分析
        try:
            provider_result = provider.execute_competitor_analysis(goal, competitors, context)
        except Exception as e:
            logger.error(f"EcommerceCompetitorAnalysis provider failed: {e}")
            service._log_event(mission_id, "provider_fallback",
                              f"Provider {provider.name} 失败: {str(e)[:100]}",
                              module_id=module_id, payload={"error": str(e)})
            return self._fallback_to_runtime(goal, module_id, mission_id, context, competitors)

        if not provider_result.get("ok"):
            return ExecutionResult(ok=False, error=provider_result.get("error", "Provider 执行失败"))

        # 标准化 structured_output
        from backend.services.boss_execution_providers import create_standard_output
        structured = create_standard_output(
            status="success",
            summary=provider_result.get("summary", ""),
            competitors=provider_result.get("competitors", competitors),
            pricing=provider_result.get("pricing", {}),
            warnings=provider_result.get("warnings", []),
            provider=provider.name,
            raw_data=provider_result.get("raw_data", {}),
        )

        service._log_event(mission_id, "structured_output_generated",
                          f"生成标准化输出",
                          module_id=module_id, payload={"provider": provider.name})

        warnings = provider_warnings + structured.get("warnings", [])

        return ExecutionResult(
            ok=True,
            final_answer=structured.get("summary", ""),
            structured_output=structured,
            confidence=0.7,
            warnings=warnings,
            used_tools=[provider.name],
            mode="provider",
            provider=provider.name,
        )

    def _fallback_to_runtime(self, goal: str, module_id: str, mission_id: str,
                             context: Dict[str, Any], competitors: List[Dict]) -> ExecutionResult:
        """Fallback 到 LocalAgentRuntime"""
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

        return ExecutionResult(
            ok=result.get("ok", False),
            final_answer=text,
            structured_output={"competitors": competitors, "pricing": pricing},
            confidence=result.get("confidence", 0.0),
            warnings=result.get("warnings", []),
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
        prev_results = context.get("prev_results", {})
        competitor_data = prev_results.get("competitor_analysis", {}).get("structured_output", {})
        competitors = competitor_data.get("competitors", [])
        pricing = competitor_data.get("pricing", {})

        # 获取 Provider
        provider = self._get_provider()
        provider_warnings = getattr(self, '_provider_warnings', [])

        # 记录 provider_selected 事件
        from backend.services.boss_command_center import get_boss_command_center
        service = get_boss_command_center()
        service._log_event(mission_id, "provider_selected", f"使用 Provider: {provider.name}",
                          module_id=module_id, payload={"provider": provider.name})

        # 调用 Provider 执行上架物料包生成
        try:
            provider_result = provider.execute_listing_pack(goal, competitors, pricing, context)
        except Exception as e:
            logger.error(f"EcommerceListingPack provider failed: {e}")
            service._log_event(mission_id, "provider_fallback",
                              f"Provider {provider.name} 失败: {str(e)[:100]}",
                              module_id=module_id, payload={"error": str(e)})
            return self._fallback_to_runtime(goal, module_id, mission_id, context, competitors, pricing)

        if not provider_result.get("ok"):
            return ExecutionResult(ok=False, error=provider_result.get("error", "Provider 执行失败"))

        # 标准化 structured_output
        from backend.services.boss_execution_providers import create_standard_output
        structured = create_standard_output(
            status="success",
            summary=provider_result.get("summary", ""),
            listing_copy=provider_result.get("listing_copy", ""),
            pricing=provider_result.get("pricing", pricing),
            image_plan=provider_result.get("image_plan", {}),
            next_actions=provider_result.get("next_actions", []),
            warnings=provider_result.get("warnings", []),
            provider=provider.name,
            raw_data=provider_result.get("raw_data", {}),
        )

        service._log_event(mission_id, "structured_output_generated",
                          f"生成标准化输出",
                          module_id=module_id, payload={"provider": provider.name})

        warnings = provider_warnings + structured.get("warnings", [])

        return ExecutionResult(
            ok=True,
            final_answer=structured.get("summary", ""),
            structured_output=structured,
            confidence=0.7,
            warnings=warnings,
            used_tools=[provider.name],
            mode="provider",
            provider=provider.name,
            next_actions=structured.get("next_actions", []),
        )

    def _fallback_to_runtime(self, goal: str, module_id: str, mission_id: str,
                             context: Dict[str, Any], competitors: List[Dict],
                             pricing: Dict[str, Any]) -> ExecutionResult:
        """Fallback 到 LocalAgentRuntime"""
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

        return ExecutionResult(
            ok=result.get("ok", False),
            final_answer=text,
            structured_output={"listing_copy": text, "pricing": pricing, "image_plan": image_plan},
            confidence=result.get("confidence", 0.0),
            warnings=result.get("warnings", []),
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

_EXECUTOR_REGISTRY: Dict[str, Dict[str, ModuleExecutor]] = {
    "ecommerce_product_research": {
        "market": EcommerceMarketResearchExecutor(),
        "competitor_analysis": EcommerceCompetitorAnalysisExecutor(),
        "marketing": EcommerceListingPackExecutor(),
    },
    # 未来模板可以在这里注册
    # "xianyu_listing_pack": { ... },
    # "saas_feature_planning": { ... },
}

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
        try:
            from backend.services.local_agent_runtime import get_local_agent_runtime
            runtime = get_local_agent_runtime()
            result = runtime.execute(prompt, {
                "boss_mission": True,
                "mission_id": mission_id,
                "mission_module": module_id,
                "mission_goal": goal,
            })
        except Exception as e:
            return ExecutionResult(ok=False, error=str(e))

        # 标准化输出
        from backend.services.boss_execution_providers import create_standard_output
        structured = create_standard_output(
            status="success" if result.get("ok") else "failed",
            summary=result.get("final_answer", "")[:500] if result.get("final_answer") else "",
            provider="local_heuristic",
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
            provider="local_heuristic",
        )


def get_executor(template_id: str, module_id: str) -> ModuleExecutor:
    """获取模块执行器"""
    template_executors = _EXECUTOR_REGISTRY.get(template_id, {})
    executor = template_executors.get(module_id)
    if executor:
        return executor
    return DefaultModuleExecutor()
