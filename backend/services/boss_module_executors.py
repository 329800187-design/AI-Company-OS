"""
Boss Module Executors — 模块级执行器

每个 executor 实现 ModuleExecutor 接口：
- execute(mission, module, goal, context) -> ExecutionResult

注册表根据 (template_id, module_id) 分发到具体执行器。
未注册的模块 fallback 到 LocalAgentRuntime。
"""
import json
from abc import ABC, abstractmethod
from typing import Dict, Any, List, Optional
from backend.logger import get_logger

logger = get_logger()


class ExecutionResult:
    """模块执行结果"""

    def __init__(self, ok: bool, final_answer: str = "",
                 structured_output: Dict[str, Any] = None,
                 confidence: float = 0.0, warnings: List[str] = None,
                 used_tools: List[str] = None, mode: str = "",
                 error: str = "", next_actions: List[str] = None):
        self.ok = ok
        self.final_answer = final_answer
        self.structured_output = structured_output or {}
        self.confidence = confidence
        self.warnings = warnings or []
        self.used_tools = used_tools or []
        self.mode = mode
        self.error = error
        self.next_actions = next_actions or []

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
        }


class ModuleExecutor(ABC):
    """模块执行器接口"""

    @abstractmethod
    def execute(self, goal: str, module_id: str,
                mission_id: str, context: Dict[str, Any] = None) -> ExecutionResult:
        """执行模块"""
        pass


# ── 电商选品市场调研执行器 ──────────────────────────────

class EcommerceMarketResearchExecutor(ModuleExecutor):
    """电商市场调研执行器 — 使用 MiMo 联网搜索"""

    def execute(self, goal: str, module_id: str,
                mission_id: str, context: Dict[str, Any] = None) -> ExecutionResult:
        context = context or {}

        # 构建结构化搜索 prompt
        search_prompt = (
            f"请调研以下电商业务的市场情况：{goal}\n\n"
            f"请按以下结构输出：\n"
            f"1. 市场趋势（增长趋势、规模、驱动力）\n"
            f"2. 目标用户画像（人群特征、购买动机、价格敏感度）\n"
            f"3. 竞品列表（至少 3 个，含名称、价格区间、卖点、平台）\n"
            f"4. 差异化机会\n"
            f"5. 风险提示\n\n"
            f"尽量引用来源，提供数据支撑。"
        )

        # 调用 LocalAgentRuntime
        try:
            from backend.services.local_agent_runtime import get_local_agent_runtime
            runtime = get_local_agent_runtime()
            result = runtime.execute(search_prompt, {
                "boss_mission": True,
                "mission_id": mission_id,
                "mission_module": module_id,
                "mission_goal": goal,
                "task_type_hint": "research",
            })
        except Exception as e:
            logger.error(f"EcommerceMarketResearch failed: {e}")
            return ExecutionResult(ok=False, error=str(e))

        # 提取结构化输出
        text = result.get("final_answer", "")
        sources = result.get("sources", [])

        structured = {
            "evidence": sources,
            "research_summary": text[:500] if text else "",
            "sources_count": len(sources),
        }

        # 尝试从文本中提取竞品列表
        competitors = self._extract_competitors(text)
        if competitors:
            structured["competitors"] = competitors

        warnings = []
        if not sources:
            warnings.append("市场模块未获取到联网搜索结果，分析基于模型已有知识")

        return ExecutionResult(
            ok=result.get("ok", False),
            final_answer=text,
            structured_output=structured,
            confidence=result.get("confidence", 0.0),
            warnings=warnings + result.get("warnings", []),
            used_tools=result.get("used_tools", []),
            mode=result.get("mode", ""),
            next_actions=[],
        )

    def _extract_competitors(self, text: str) -> List[Dict[str, Any]]:
        """尝试从文本中提取竞品信息"""
        competitors = []
        lines = text.split("\n")
        current = {}
        for line in lines:
            line = line.strip()
            if not line:
                if current.get("name"):
                    competitors.append(current)
                    current = {}
                continue
            # 简单规则提取
            lower = line.lower()
            if any(kw in lower for kw in ["竞品", "competitor", "对手", "品牌"]):
                current = {"name": line[:50], "details": ""}
            elif current.get("name") and not current.get("details"):
                current["details"] = line[:200]
        if current.get("name"):
            competitors.append(current)
        return competitors[:10]


# ── 电商竞品分析执行器 ──────────────────────────────────

class EcommerceCompetitorAnalysisExecutor(ModuleExecutor):
    """竞品分析执行器"""

    def execute(self, goal: str, module_id: str,
                mission_id: str, context: Dict[str, Any] = None) -> ExecutionResult:
        # 从上下文获取市场调研结果
        prev_results = context.get("prev_results", {})
        market_data = prev_results.get("market", {}).get("structured_output", {})
        competitors = market_data.get("competitors", [])

        analysis_prompt = (
            f"请基于以下信息，对电商业务「{goal}」做竞品分析：\n\n"
        )
        if competitors:
            analysis_prompt += f"已知竞品：{json.dumps(competitors, ensure_ascii=False)}\n\n"
        analysis_prompt += (
            "请输出：\n"
            "1. 竞品对比表（名称、价格、核心卖点、目标用户）\n"
            "2. 价格区间分析\n"
            "3. 我们的差异化定位\n"
            "4. 风险提示\n"
            "5. 建议定价范围"
        )

        try:
            from backend.services.local_agent_runtime import get_local_agent_runtime
            runtime = get_local_agent_runtime()
            result = runtime.execute(analysis_prompt, {
                "boss_mission": True,
                "mission_id": mission_id,
                "mission_module": module_id,
                "mission_goal": goal,
            })
        except Exception as e:
            return ExecutionResult(ok=False, error=str(e))

        text = result.get("final_answer", "")
        structured = {
            "competitors": competitors,
            "pricing": self._extract_pricing(text),
            "analysis_summary": text[:500] if text else "",
        }

        return ExecutionResult(
            ok=result.get("ok", False),
            final_answer=text,
            structured_output=structured,
            confidence=result.get("confidence", 0.0),
            warnings=result.get("warnings", []),
            used_tools=result.get("used_tools", []),
            mode=result.get("mode", ""),
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
        market_data = prev_results.get("market", {}).get("structured_output", {})
        competitor_data = prev_results.get("competitor_analysis", {}).get("structured_output", {})

        listing_prompt = (
            f"请为以下产品生成闲鱼/电商上架物料包：{goal}\n\n"
            f"已知竞品信息：{json.dumps(competitor_data.get('competitors', []), ensure_ascii=False)}\n\n"
            f"请按以下结构输出：\n"
            f"1. **标题**（3 个备选，含关键词）\n"
            f"2. **核心卖点**（3-5 个，简洁有力）\n"
            f"3. **详情文案**（200-500 字，含规格/优势/使用场景）\n"
            f"4. **定价建议**（含成本分析和利润空间）\n"
            f"5. **SKU 建议**（规格/颜色/套餐）\n"
            f"6. **首图建议**（拍摄角度/风格/道具）"
        )

        try:
            from backend.services.local_agent_runtime import get_local_agent_runtime
            runtime = get_local_agent_runtime()
            result = runtime.execute(listing_prompt, {
                "boss_mission": True,
                "mission_id": mission_id,
                "mission_module": module_id,
                "mission_goal": goal,
            })
        except Exception as e:
            return ExecutionResult(ok=False, error=str(e))

        text = result.get("final_answer", "")
        structured = {
            "listing_copy": text,
            "pricing": competitor_data.get("pricing", {}),
            "image_plan": self._extract_image_plan(text),
            "next_actions": [
                "根据定价建议确定最终价格",
                "拍摄首图（参考首图建议）",
                "上架商品并填写标题和详情",
            ],
        }

        return ExecutionResult(
            ok=result.get("ok", False),
            final_answer=text,
            structured_output=structured,
            confidence=result.get("confidence", 0.0),
            warnings=result.get("warnings", []),
            used_tools=result.get("used_tools", []),
            mode=result.get("mode", ""),
            next_actions=structured["next_actions"],
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

        return ExecutionResult(
            ok=result.get("ok", False),
            final_answer=result.get("final_answer", ""),
            structured_output={},
            confidence=result.get("confidence", 0.0),
            warnings=result.get("warnings", []),
            used_tools=result.get("used_tools", []),
            mode=result.get("mode", ""),
            error=result.get("error", ""),
            next_actions=result.get("next_actions", []),
        )


def get_executor(template_id: str, module_id: str) -> ModuleExecutor:
    """获取模块执行器"""
    template_executors = _EXECUTOR_REGISTRY.get(template_id, {})
    executor = template_executors.get(module_id)
    if executor:
        return executor
    return DefaultModuleExecutor()
