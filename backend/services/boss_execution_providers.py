"""
Boss Execution Providers — 执行能力提供者抽象层

职责：
1. 定义 BossExecutionProvider 接口
2. 实现 LocalMockExecutionProvider（测试用）
3. 实现 LocalHeuristicExecutionProvider（默认，基于 LocalAgentRuntime）
4. 预留 HermesExecutionProvider（真实 Hermes 工具链）

Provider 负责真实能力来源，Executor 负责模块编排和结构化输出整理。
"""
from abc import ABC, abstractmethod
from datetime import datetime
from typing import Dict, Any, List, Optional
from backend.logger import get_logger

logger = get_logger()


# ── Evidence Gate 配置 ──────────────────────────────────────

# 每个模块类型的最低 evidence 要求
EVIDENCE_GATE_THRESHOLDS = {
    "market": {
        "min_evidence": 2,      # 至少 2 条来源
        "min_competitors": 2,   # 至少 2 个竞品
        "description": "市场调研需要至少 2 条搜索来源和 2 个竞品数据",
    },
    "competitor_analysis": {
        "min_evidence": 3,      # 至少 3 条来源/货源样本
        "min_competitors": 3,   # 至少 3 个竞品
        "description": "竞品分析需要至少 3 条货源样本和 3 个竞品数据",
    },
    "listing_pack": {
        "min_evidence": 1,      # 至少 1 条来源（依赖前序 evidence）
        "description": "上架文案需要基于前序 evidence，不能凭空生成",
    },
}

# 需要浏览器自动化的模块（涉及 browser/ecommerce/sourcing 工具调用）
MODULES_REQUIRING_BROWSER = {"market", "competitor_analysis", "marketing"}
BROWSER_AUTOMATION_PROMPT_KEYWORDS = (
    "browser",
    "playwright",
    "goofish",
    "taobao",
    "ecommerce-bridge",
    "sourcing-price-bridge",
    "ecommerce_mcp",
    "sourcing_price",
)


def prompt_requests_browser_automation(prompt: str) -> bool:
    """Best-effort hard stop for prompts that would launch browser automation."""
    normalized = (prompt or "").lower()
    return any(keyword in normalized for keyword in BROWSER_AUTOMATION_PROMPT_KEYWORDS)


# ── 浏览器自动化审批闸门 ──────────────────────────────────

def is_browser_automation_allowed(
    allow_from_request: bool = False,
    module_id: str = "",
) -> bool:
    """检查浏览器自动化是否被允许

    检查顺序：
    1. 全局配置 BROWSER_AUTOMATION_APPROVED=true → 允许
    2. 请求参数 allow_browser_automation=true → 允许
    3. 模块不需要浏览器采集 → 允许（无需审批）
    4. 其他情况 → 不允许

    注意：每次调用都从 os.getenv() 读取最新值，确保测试 monkeypatch 生效。

    Args:
        allow_from_request: API 请求中传入的 allow_browser_automation 参数
        module_id: 模块 ID，用于判断是否需要浏览器采集

    Returns:
        True if browser automation is allowed, False otherwise
    """
    import os

    def _bool(v: str, default: bool = False) -> bool:
        if not v:
            return default
        return v.strip().lower() in ("true", "1", "yes", "on")

    # 从环境变量实时读取（不使用缓存的模块级常量）
    require_approval = _bool(os.getenv("BROWSER_AUTOMATION_REQUIRE_APPROVAL", "true"), True)
    global_approved = _bool(os.getenv("BROWSER_AUTOMATION_APPROVED", "false"), False)

    # 如果不需要审批，直接允许
    if not require_approval:
        return True

    # 全局审批通过
    if global_approved:
        return True

    # 请求级别审批
    if allow_from_request:
        return True

    # 模块不需要浏览器采集
    if module_id and module_id not in MODULES_REQUIRING_BROWSER:
        return True

    return False


def build_approval_required_output(
    module_id: str,
    action: str = "浏览器自动化采集",
) -> Dict[str, Any]:
    """构建审批未通过时的标准化 structured_output

    当浏览器自动化需要审批但未获得时使用。
    - status: blocked
    - evidence_gate_passed: False
    - 不调用任何外部工具（不启动浏览器、不调用 Hermes CLI）
    """
    return create_standard_output(
        status="blocked",
        summary="",
        evidence=[],
        evidence_files=[],
        screenshots=[],
        tool_calls=[],
        missing_evidence=[f"{action}需要用户授权后才能执行"],
        evidence_gate_passed=False,
        competitors=[],
        pricing={},
        listing_copy="",
        image_plan={},
        next_actions=[
            "在 API 请求中设置 allow_browser_automation=true",
            "或在 .env 中设置 BROWSER_AUTOMATION_APPROVED=true",
        ],
        warnings=[f"浏览器自动化采集需要用户确认后才能执行（模块: {module_id}）"],
        provider="blocked_by_approval",
    )


# ── 标准化输出结构 ────────────────────────────────────────

def create_standard_output(
    status: str = "success",
    summary: str = "",
    evidence: List[Dict[str, Any]] = None,
    evidence_files: List[str] = None,
    screenshots: List[str] = None,
    tool_calls: List[Dict[str, Any]] = None,
    missing_evidence: List[str] = None,
    evidence_gate_passed: bool = True,
    competitors: List[Dict[str, Any]] = None,
    pricing: Dict[str, Any] = None,
    listing_copy: str = "",
    image_plan: Dict[str, Any] = None,
    next_actions: List[str] = None,
    warnings: List[str] = None,
    provider: str = "",
    raw_data: Dict[str, Any] = None,
) -> Dict[str, Any]:
    """创建标准化的 structured_output

    新增字段：
    - evidence_files: 采集到的文件路径列表
    - screenshots: 截图路径列表
    - tool_calls: Hermes 工具调用记录 [{"tool": "name", "args": {}, "result": "..."}]
    - missing_evidence: 缺失的证据类型列表
    - evidence_gate_passed: 证据门槛是否通过
    """
    return {
        "status": status,
        "summary": summary,
        "evidence": evidence or [],
        "evidence_files": evidence_files or [],
        "screenshots": screenshots or [],
        "tool_calls": tool_calls or [],
        "missing_evidence": missing_evidence or [],
        "evidence_gate_passed": evidence_gate_passed,
        "competitors": competitors or [],
        "pricing": pricing or {},
        "listing_copy": listing_copy,
        "image_plan": image_plan or {},
        "next_actions": next_actions or [],
        "warnings": warnings or [],
        "provider": provider,
        "generated_at": datetime.now().isoformat(),
        "raw_data": raw_data or {},
    }


def check_evidence_gate(
    module_id: str,
    evidence: List[Dict[str, Any]] = None,
    competitors: List[Dict[str, Any]] = None,
    prev_results: Dict[str, Any] = None,
) -> Dict[str, Any]:
    """检查 evidence gate 是否通过

    Args:
        module_id: 模块 ID（market / competitor_analysis / listing_pack）
        evidence: 当前模块收集的 evidence 列表
        competitors: 竞品列表
        prev_results: 前序模块结果（listing 依赖前序 evidence）

    Returns:
        {
            "passed": bool,
            "missing": [str],  # 缺失的证据类型
            "details": str,    # 可读描述
        }
    """
    thresholds = EVIDENCE_GATE_THRESHOLDS.get(module_id, {})
    if not thresholds:
        return {"passed": True, "missing": [], "details": "无门槛要求"}

    evidence = evidence or []
    competitors = competitors or []
    missing = []

    # 检查 evidence 数量
    min_evidence = thresholds.get("min_evidence", 0)
    if module_id == "listing_pack":
        # listing_pack: accept if either prev_results evidence OR own evidence is sufficient.
        # Own evidence (e.g. from browser tools within the listing step) should not be rejected
        # just because upstream modules are sparse.
        own_evidence_count = len(evidence)
        prev_evidence = []
        if prev_results:
            for prev_module in prev_results.values():
                prev_so = prev_module.get("structured_output", {})
                prev_evidence.extend(prev_so.get("evidence", []))
        combined = own_evidence_count + len(prev_evidence)
        if combined < min_evidence:
            missing.append(
                f"evidence 不足（需要 {min_evidence} 条，"
                f"own={own_evidence_count}, prev={len(prev_evidence)}）"
            )
    elif len(evidence) < min_evidence:
        missing.append(f"evidence 不足（需要 {min_evidence} 条，当前 {len(evidence)} 条）")

    # 检查竞品数量
    min_competitors = thresholds.get("min_competitors", 0)
    if min_competitors > 0 and len(competitors) < min_competitors:
        missing.append(f"竞品数据不足（需要 {min_competitors} 个，当前 {len(competitors)} 个）")

    passed = len(missing) == 0
    details = thresholds.get("description", "")
    if not passed:
        details = f"证据门槛未通过：{'; '.join(missing)}"

    return {
        "passed": passed,
        "missing": missing,
        "details": details,
    }


# ── Fallback structured_output 构建 ────────────────────────

def build_fallback_structured_output(
    module_id: str,
    provider_reason: str,
    warnings: List[str] = None,
    extra: Dict[str, Any] = None,
) -> Dict[str, Any]:
    """构建 fallback 时的标准化 structured_output

    当 Hermes 超时/失败 fallback 到 local_heuristic 时使用。
    - evidence_gate_passed 始终为 False
    - status 始终为 partial
    - evidence 为空列表（不伪造任何证据）
    - missing_evidence 根据模块门槛要求填充

    Args:
        module_id: 模块 ID（market / competitor_analysis / marketing）
        provider_reason: fallback 原因描述
        warnings: 额外警告信息
        extra: 额外字段（如 competitors, pricing 等，来自 fallback runtime 结果）
    """
    # 根据模块门槛确定 missing_evidence
    from backend.services.boss_execution_providers import EVIDENCE_GATE_THRESHOLDS
    # module_id 映射：marketing 实际对应 listing_pack 门槛
    threshold_key = "listing_pack" if module_id == "marketing" else module_id
    thresholds = EVIDENCE_GATE_THRESHOLDS.get(threshold_key, {})
    missing_evidence = []

    min_evidence = thresholds.get("min_evidence", 0)
    if min_evidence > 0:
        missing_evidence.append(
            f"evidence 不足（需要 {min_evidence} 条来源，当前 0 条）—— Hermes 工具链未采集到数据"
        )

    min_competitors = thresholds.get("min_competitors", 0)
    if min_competitors > 0:
        missing_evidence.append(
            f"竞品数据不足（需要 {min_competitors} 个竞品，当前 0 个）—— 未执行真实采集"
        )

    # 模块特定提示
    next_actions = [
        "检查 Hermes CLI 是否可用且网络正常",
        "尝试缩小任务范围后重试",
        "或切换到 local_heuristic 模式手动执行",
    ]

    all_warnings = [f"Hermes 失败/超时，fallback 到 local_heuristic: {provider_reason}"]
    if warnings:
        all_warnings.extend(warnings)

    extra = extra or {}

    return create_standard_output(
        status="partial",
        summary="",
        evidence=[],
        evidence_files=[],
        screenshots=[],
        tool_calls=[],
        missing_evidence=missing_evidence,
        evidence_gate_passed=False,
        competitors=extra.get("competitors", []),
        pricing=extra.get("pricing", {}),
        listing_copy="",
        image_plan={},
        next_actions=next_actions,
        warnings=all_warnings,
        provider="local_heuristic_fallback",
    )


# ── Provider 接口 ─────────────────────────────────────────

class BossExecutionProvider(ABC):
    """Boss 执行能力提供者接口"""

    @property
    @abstractmethod
    def name(self) -> str:
        """Provider 名称"""
        pass

    @property
    @abstractmethod
    def is_available(self) -> bool:
        """Provider 是否可用"""
        pass

    @abstractmethod
    def execute_market_research(self, goal: str, context: Dict[str, Any] = None,
                                 allow_browser_automation: bool = False) -> Dict[str, Any]:
        """执行市场调研

        Args:
            goal: 市场调研目标
            context: 执行上下文
            allow_browser_automation: 是否允许浏览器自动化采集

        Returns:
            {
                "ok": bool,
                "blocked": bool,  # True if blocked by approval gate
                "summary": str,
                "evidence": list,
                "competitors": list,
                "pricing": dict,
                "warnings": list,
                "raw_data": dict,
            }
        """
        pass

    @abstractmethod
    def execute_competitor_analysis(self, goal: str, competitors: List[Dict] = None,
                                     context: Dict[str, Any] = None,
                                     allow_browser_automation: bool = False) -> Dict[str, Any]:
        """执行竞品分析

        Args:
            goal: 竞品分析目标
            competitors: 已知竞品列表
            context: 执行上下文
            allow_browser_automation: 是否允许浏览器自动化采集

        Returns:
            {
                "ok": bool,
                "blocked": bool,  # True if blocked by approval gate
                "summary": str,
                "competitors": list,
                "pricing": dict,
                "warnings": list,
                "raw_data": dict,
            }
        """
        pass

    @abstractmethod
    def execute_listing_pack(self, goal: str, competitors: List[Dict] = None,
                             pricing: Dict[str, Any] = None,
                             context: Dict[str, Any] = None,
                             allow_browser_automation: bool = False) -> Dict[str, Any]:
        """执行上架物料包生成

        Args:
            goal: 上架物料包生成目标
            competitors: 竞品列表
            pricing: 定价信息
            context: 执行上下文
            allow_browser_automation: 是否允许浏览器自动化采集

        Returns:
            {
                "ok": bool,
                "blocked": bool,  # True if blocked by approval gate
                "summary": str,
                "listing_copy": str,
                "pricing": dict,
                "image_plan": dict,
                "next_actions": list,
                "warnings": list,
                "raw_data": dict,
            }
        """
        pass

    def export_report(self, mission_data: Dict[str, Any], fmt: str = "json") -> Dict[str, Any]:
        """导出报告（可选实现）"""
        raise NotImplementedError(f"{self.name} does not support export_report")


# ── Local Mock Provider（测试用）──────────────────────────

class LocalMockExecutionProvider(BossExecutionProvider):
    """本地 Mock Provider — 用于测试，返回固定数据"""

    def __init__(self, mock_data: Dict[str, Any] = None):
        self._mock_data = mock_data or {}

    @property
    def name(self) -> str:
        return "local_mock"

    @property
    def is_available(self) -> bool:
        return True

    def execute_market_research(self, goal: str, context: Dict[str, Any] = None,
                                 allow_browser_automation: bool = False) -> Dict[str, Any]:
        """返回 mock 市场调研数据"""
        return self._mock_data.get("market_research", {
            "ok": True,
            "summary": f"Mock 市场调研结果：{goal[:50]}",
            "evidence": [
                {"title": "Mock Source 1", "url": "https://example.com/1"},
                {"title": "Mock Source 2", "url": "https://example.com/2"},
            ],
            "competitors": [
                {"name": "竞品A", "price": "99-199", "platform": "淘宝", "features": "功能1,功能2"},
                {"name": "竞品B", "price": "149-299", "platform": "京东", "features": "功能3,功能4"},
            ],
            "pricing": {"range": "99-299", "avg": "199"},
            "warnings": [],
            "raw_data": {"mock": True},
        })

    def execute_competitor_analysis(self, goal: str, competitors: List[Dict] = None,
                                     context: Dict[str, Any] = None,
                                     allow_browser_automation: bool = False) -> Dict[str, Any]:
        """返回 mock 竞品分析数据"""
        return self._mock_data.get("competitor_analysis", {
            "ok": True,
            "summary": f"Mock 竞品分析结果：{goal[:50]}",
            "competitors": competitors or [
                {"name": "竞品A", "price": "99-199", "strengths": "价格低", "weaknesses": "功能少"},
            ],
            "pricing": {"recommended_range": "129-249", "rationale": "中等价位"},
            "warnings": [],
            "raw_data": {"mock": True},
        })

    def execute_listing_pack(self, goal: str, competitors: List[Dict] = None,
                             pricing: Dict[str, Any] = None,
                             context: Dict[str, Any] = None,
                             allow_browser_automation: bool = False) -> Dict[str, Any]:
        """返回 mock 上架物料包数据"""
        return self._mock_data.get("listing_pack", {
            "ok": True,
            "summary": f"Mock 上架物料包：{goal[:50]}",
            "listing_copy": f"【爆款推荐】{goal[:30]}\n\n核心卖点：\n1. 高性价比\n2. 品质保证\n3. 快速发货",
            "pricing": pricing or {"recommended": "199", "min": "149", "max": "249"},
            "image_plan": {
                "main_image": "白底产品图",
                "lifestyle": "使用场景图",
                "details": "细节展示图",
            },
            "next_actions": ["确定最终定价", "拍摄主图", "上架商品"],
            "warnings": [],
            "raw_data": {"mock": True},
        })


# ── Local Heuristic Provider（默认）───────────────────────

class LocalHeuristicExecutionProvider(BossExecutionProvider):
    """本地启发式 Provider — 基于 LocalAgentRuntime，离线可用"""

    def __init__(self):
        self._runtime = None

    @property
    def name(self) -> str:
        return "local_heuristic"

    @property
    def is_available(self) -> bool:
        """检查 LocalAgentRuntime 是否可用"""
        try:
            from backend.services.local_agent_runtime import get_local_agent_runtime
            runtime = get_local_agent_runtime()
            return runtime is not None
        except Exception:
            return False

    def _get_runtime(self):
        """延迟加载 runtime"""
        if self._runtime is None:
            from backend.services.local_agent_runtime import get_local_agent_runtime
            self._runtime = get_local_agent_runtime()
        return self._runtime

    def _execute_with_runtime(self, prompt: str, context: Dict[str, Any] = None) -> Dict[str, Any]:
        """使用 LocalAgentRuntime 执行任务"""
        try:
            runtime = self._get_runtime()
            result = runtime.execute(prompt, context or {})
            return {
                "ok": result.get("ok", False),
                "text": result.get("final_answer", ""),
                "sources": result.get("sources", []),
                "confidence": result.get("confidence", 0.0),
                "warnings": result.get("warnings", []),
                "used_tools": result.get("used_tools", []),
                "mode": result.get("mode", ""),
                "raw_data": result,
            }
        except Exception as e:
            logger.error(f"LocalHeuristicExecutionProvider failed: {e}")
            return {
                "ok": False,
                "text": "",
                "sources": [],
                "confidence": 0.0,
                "warnings": [str(e)],
                "used_tools": [],
                "mode": "error",
                "raw_data": {"error": str(e)},
            }

    def _extract_competitors(self, text: str) -> List[Dict[str, Any]]:
        """从文本中提取竞品信息"""
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
            lower = line.lower()
            if any(kw in lower for kw in ["竞品", "competitor", "对手", "品牌"]):
                current = {"name": line[:50], "details": ""}
            elif current.get("name") and not current.get("details"):
                current["details"] = line[:200]
        if current.get("name"):
            competitors.append(current)
        return competitors[:10]

    def _extract_pricing(self, text: str) -> Dict[str, Any]:
        """从文本中提取定价建议"""
        import re
        prices = re.findall(r'[\d.]+\s*(?:元|￥|¥|RMB|USD|\$)', text)
        return {
            "mentioned_prices": prices[:10],
            "raw_text": text[:300] if text else "",
        }

    def _extract_image_plan(self, text: str) -> Dict[str, Any]:
        """提取图片/拍摄建议"""
        import re
        image_sections = re.findall(r'(?:首图|图片|拍摄|图片建议)[：:]\s*(.+?)(?:\n\n|\n\d|$)', text, re.DOTALL)
        return {
            "suggestions": [s.strip()[:200] for s in image_sections[:3]],
            "raw_text": text[:300] if text else "",
        }

    def execute_market_research(self, goal: str, context: Dict[str, Any] = None,
                                 allow_browser_automation: bool = False) -> Dict[str, Any]:
        """执行市场调研"""
        prompt = (
            f"请调研以下电商业务的市场情况：{goal}\n\n"
            f"请按以下结构输出：\n"
            f"1. 市场趋势（增长趋势、规模、驱动力）\n"
            f"2. 目标用户画像（人群特征、购买动机、价格敏感度）\n"
            f"3. 竞品列表（至少 3 个，含名称、价格区间、卖点、平台）\n"
            f"4. 差异化机会\n"
            f"5. 风险提示\n\n"
            f"尽量引用来源，提供数据支撑。"
        )

        result = self._execute_with_runtime(prompt, context)
        text = result.get("text", "")
        sources = result.get("sources", [])

        competitors = self._extract_competitors(text)
        pricing = self._extract_pricing(text)

        warnings = result.get("warnings", [])
        if not sources:
            warnings.append("市场模块未获取到联网搜索结果，分析基于模型已有知识")

        return {
            "ok": result.get("ok", False),
            "summary": text[:500] if text else "",
            "evidence": sources,
            "competitors": competitors,
            "pricing": pricing,
            "warnings": warnings,
            "raw_data": result.get("raw_data", {}),
        }

    def execute_competitor_analysis(self, goal: str, competitors: List[Dict] = None,
                                     context: Dict[str, Any] = None,
                                     allow_browser_automation: bool = False) -> Dict[str, Any]:
        """执行竞品分析"""
        prompt = f"请基于以下信息，对电商业务「{goal}」做竞品分析：\n\n"
        if competitors:
            import json
            prompt += f"已知竞品：{json.dumps(competitors, ensure_ascii=False)}\n\n"
        prompt += (
            "请输出：\n"
            "1. 竞品对比表（名称、价格、核心卖点、目标用户）\n"
            "2. 价格区间分析\n"
            "3. 我们的差异化定位\n"
            "4. 风险提示\n"
            "5. 建议定价范围"
        )

        result = self._execute_with_runtime(prompt, context)
        text = result.get("text", "")

        pricing = self._extract_pricing(text)

        return {
            "ok": result.get("ok", False),
            "summary": text[:500] if text else "",
            "competitors": competitors or [],
            "pricing": pricing,
            "warnings": result.get("warnings", []),
            "raw_data": result.get("raw_data", {}),
        }

    def execute_listing_pack(self, goal: str, competitors: List[Dict] = None,
                             pricing: Dict[str, Any] = None,
                             context: Dict[str, Any] = None,
                             allow_browser_automation: bool = False) -> Dict[str, Any]:
        """执行上架物料包生成"""
        import json
        prompt = (
            f"请为以下产品生成闲鱼/电商上架物料包：{goal}\n\n"
            f"已知竞品信息：{json.dumps(competitors or [], ensure_ascii=False)}\n\n"
            f"请按以下结构输出：\n"
            f"1. **标题**（3 个备选，含关键词）\n"
            f"2. **核心卖点**（3-5 个，简洁有力）\n"
            f"3. **详情文案**（200-500 字，含规格/优势/使用场景）\n"
            f"4. **定价建议**（含成本分析和利润空间）\n"
            f"5. **SKU 建议**（规格/颜色/套餐）\n"
            f"6. **首图建议**（拍摄角度/风格/道具）"
        )

        result = self._execute_with_runtime(prompt, context)
        text = result.get("text", "")

        image_plan = self._extract_image_plan(text)
        next_actions = [
            "根据定价建议确定最终价格",
            "拍摄首图（参考首图建议）",
            "上架商品并填写标题和详情",
        ]

        return {
            "ok": result.get("ok", False),
            "summary": text[:500] if text else "",
            "listing_copy": text,
            "pricing": pricing or {},
            "image_plan": image_plan,
            "next_actions": next_actions,
            "warnings": result.get("warnings", []),
            "raw_data": result.get("raw_data", {}),
        }


# ── Hermes Provider（v1 实现）───────────────────────────────

class HermesExecutionProvider(BossExecutionProvider):
    """Hermes Provider — 通过 subprocess 调用 Hermes CLI

    安全要求：
    - 不执行发布/付款/发消息等不可逆操作
    - 失败时 fallback 到 local_heuristic
    - event log 记录 hermes_invoked / hermes_failed
    """

    def __init__(self):
        self._cli_path = None
        self._timeout = None
        self._ecommerce_enabled = None

    @property
    def name(self) -> str:
        return "hermes"

    @property
    def is_available(self) -> bool:
        """Hermes host-process execution is disabled by the safety baseline."""
        return False

    def _get_cli_path(self) -> str:
        """获取 Hermes CLI 路径"""
        if self._cli_path is None:
            from backend.config import HERMES_CLI_PATH
            self._cli_path = HERMES_CLI_PATH
        return self._cli_path

    def _get_timeout(self) -> int:
        """获取执行超时"""
        if self._timeout is None:
            from backend.config import HERMES_EXECUTION_TIMEOUT_SECONDS
            self._timeout = HERMES_EXECUTION_TIMEOUT_SECONDS
        return self._timeout

    def _is_ecommerce_enabled(self) -> bool:
        """检查电商模式是否启用"""
        if self._ecommerce_enabled is None:
            from backend.config import HERMES_ECOMMERCE_MODE_ENABLED
            self._ecommerce_enabled = HERMES_ECOMMERCE_MODE_ENABLED
        return self._ecommerce_enabled

    def _execute_hermes_cli(self, prompt: str, context: Dict[str, Any] = None) -> Dict[str, Any]:
        """Reject the retired host-process provider without side effects."""
        return {
            "ok": False,
            "blocked": True,
            "stdout": "",
            "stderr": "",
            "exit_code": -3,
            "error": "Hermes host-process execution is disabled",
        }

    def _parse_json_output(self, stdout: str) -> Dict[str, Any]:
        """解析 Hermes 输出的 JSON

        尝试从 stdout 中提取 JSON 对象。
        Hermes 可能在 JSON 前后输出其他文本，需要智能提取。
        """
        import json
        import re

        if not stdout or not stdout.strip():
            return None

        # 尝试直接解析整个输出
        try:
            return json.loads(stdout.strip())
        except json.JSONDecodeError:
            pass

        # 尝试提取 JSON 对象（以 { 开头，以 } 结尾）
        json_match = re.search(r'\{[\s\S]*\}', stdout)
        if json_match:
            try:
                return json.loads(json_match.group())
            except json.JSONDecodeError:
                pass

        # 尝试提取 JSON 数组（以 [ 开头，以 ] 结尾）
        json_match = re.search(r'\[[\s\S]*\]', stdout)
        if json_match:
            try:
                return json.loads(json_match.group())
            except json.JSONDecodeError:
                pass

        return None

    def _build_market_research_prompt(self, goal: str, context: Dict[str, Any] = None,
                                       browser_allowed: bool = False) -> str:
        """构建市场调研 prompt — 根据审批状态决定是否要求真实工具链采集"""
        ecommerce_hint = ""
        if browser_allowed and self._is_ecommerce_enabled():
            ecommerce_hint = (
                "【重要】你必须使用真实工具链采集证据，不能凭记忆生成数据。\n\n"
                "工具链要求：\n"
                "1. 必须先调用 ecommerce-bridge 或 sourcing-price-bridge 技能获取真实货源数据\n"
                "2. 必须使用 browser 技能访问至少 2 个真实网页采集证据\n"
                "3. 每条 evidence 必须包含真实 URL（不能是 example.com）\n"
                "4. 每个竞品必须包含真实的价格区间和平台信息\n"
                "5. 不要执行发布/付款/发消息等操作\n\n"
                "工具调用记录：\n"
                "在输出 JSON 中，必须包含 tool_calls 数组，记录你调用的每个工具：\n"
                '```json\n'
                '  "tool_calls": [\n'
                '    {"tool": "sourcing-price-bridge", "args": {"keyword": "..."}, "result": "获取到 N 条货源"},\n'
                '    {"tool": "browser", "args": {"url": "https://..."}, "result": "采集到 N 条数据"}\n'
                '  ]\n'
                '```\n\n'
            )
        else:
            # 未授权浏览器自动化：仅基于本地数据生成草稿
            ecommerce_hint = (
                "【注意】当前浏览器自动化未授权，无法进行真实网页采集。\n"
                "请基于你已有的本地知识和用户提供的信息生成分析草稿。\n"
                "所有数据必须在 warnings 中标注 '数据来源：模型已有知识，未经实时验证'。\n"
                "不要编造任何 URL 或来源。\n\n"
            )

        return (
            f"{ecommerce_hint}"
            f"请调研以下电商业务的市场情况：{goal}\n\n"
            f"请严格按以下 JSON 格式输出（不要输出其他内容）：\n"
            f'{{\n'
            f'  "summary": "市场调研摘要（200-500字）",\n'
            f'  "evidence": [\n'
            f'    {{"title": "来源标题", "url": "https://真实URL", "type": "source/sourcing/browser"}},\n'
            f'    ...\n'
            f'  ],\n'
            f'  "tool_calls": [\n'
            f'    {{"tool": "工具名", "args": {{}}, "result": "调用结果摘要"}}\n'
            f'  ],\n'
            f'  "evidence_files": [],\n'
            f'  "screenshots": [],\n'
            f'  "competitors": [\n'
            f'    {{"name": "竞品名称", "price": "真实价格区间", "platform": "真实平台", "features": "核心卖点", "source_url": "数据来源URL"}},\n'
            f'    ...\n'
            f'  ],\n'
            f'  "pricing": {{"range": "价格区间", "avg": "平均价格", "sources": ["数据来源"]}},\n'
            f'  "warnings": ["警告信息（如有）"]\n'
            f'}}\n\n'
            f"【严格要求】\n"
            f"- evidence 数组至少 2 条，且 URL 必须是真实可访问的链接\n"
            f"- competitors 数组至少 2 个，每个必须有 price 和 platform\n"
            f"- tool_calls 必须记录你实际调用的工具\n"
            f"- 如果无法获取真实数据，必须在 warnings 中说明，不能编造数据\n"
            f"- 不要执行发布、付款、发消息等操作"
        )

    def _build_competitor_analysis_prompt(self, goal: str, competitors: List[Dict] = None,
                                          context: Dict[str, Any] = None,
                                          browser_allowed: bool = False) -> str:
        """构建竞品分析 prompt — 根据审批状态决定是否要求真实工具链采集"""
        import json as json_lib

        competitor_info = ""
        if competitors:
            competitor_info = f"\n已知竞品信息：{json_lib.dumps(competitors, ensure_ascii=False)}\n"

        ecommerce_hint = ""
        if browser_allowed and self._is_ecommerce_enabled():
            ecommerce_hint = (
                "【重要】你必须使用真实工具链采集证据，不能凭记忆生成数据。\n\n"
                "工具链要求：\n"
                "1. 必须先调用 ecommerce-bridge 或 sourcing-price-bridge 技能获取真实货源数据\n"
                "2. 必须使用 browser 技能访问至少 3 个竞品页面采集详细信息\n"
                "3. 每条竞品必须有真实 URL 和真实价格\n"
                "4. 不要执行发布/付款/发消息等操作\n\n"
                "工具调用记录：\n"
                "在输出 JSON 中，必须包含 tool_calls 数组，记录你调用的每个工具。\n\n"
            )
        else:
            ecommerce_hint = (
                "【注意】当前浏览器自动化未授权，无法进行真实网页采集。\n"
                "请基于你已有的本地知识和用户提供的信息生成分析草稿。\n"
                "不要编造任何 URL 或来源。\n\n"
            )

        return (
            f"{ecommerce_hint}"
            f"请对电商业务「{goal}」做竞品分析：{competitor_info}\n\n"
            f"请严格按以下 JSON 格式输出（不要输出其他内容）：\n"
            f'{{\n'
            f'  "summary": "竞品分析摘要（200-500字）",\n'
            f'  "evidence": [\n'
            f'    {{"title": "来源标题", "url": "https://真实URL", "type": "source/sourcing/browser"}},\n'
            f'    ...\n'
            f'  ],\n'
            f'  "tool_calls": [\n'
            f'    {{"tool": "工具名", "args": {{}}, "result": "调用结果摘要"}}\n'
            f'  ],\n'
            f'  "competitors": [\n'
            f'    {{"name": "竞品名称", "price": "真实价格", "strengths": "优势", "weaknesses": "劣势", "source_url": "数据来源URL"}},\n'
            f'    ...\n'
            f'  ],\n'
            f'  "pricing": {{"recommended_range": "建议定价范围", "rationale": "定价理由"}},\n'
            f'  "warnings": ["警告信息（如有）"]\n'
            f'}}\n\n'
            f"【严格要求】\n"
            f"- evidence 数组至少 3 条，且 URL 必须是真实可访问的链接\n"
            f"- competitors 数组至少 3 个，每个必须有真实价格和来源 URL\n"
            f"- tool_calls 必须记录你实际调用的工具\n"
            f"- 如果无法获取真实数据，必须在 warnings 中说明，不能编造数据\n"
            f"- 不要执行发布、付款、发消息等操作"
        )

    def _build_listing_pack_prompt(self, goal: str, competitors: List[Dict] = None,
                                   pricing: Dict[str, Any] = None,
                                   context: Dict[str, Any] = None,
                                   browser_allowed: bool = False) -> str:
        """构建上架物料包 prompt — 根据审批状态决定是否要求基于真实数据"""
        import json as json_lib

        competitor_info = ""
        if competitors:
            competitor_info = f"\n竞品信息：{json_lib.dumps(competitors, ensure_ascii=False)}\n"

        pricing_info = ""
        if pricing:
            pricing_info = f"\n定价参考：{json_lib.dumps(pricing, ensure_ascii=False)}\n"

        # 获取前序 evidence
        prev_evidence_info = ""
        if context and context.get("prev_results"):
            all_evidence = []
            for module_id, module_data in context["prev_results"].items():
                so = module_data.get("structured_output", {})
                all_evidence.extend(so.get("evidence", []))
            if all_evidence:
                prev_evidence_info = f"\n前序 evidence（必须基于这些真实数据生成文案）：\n{json_lib.dumps(all_evidence[:10], ensure_ascii=False)}\n"

        ecommerce_hint = ""
        if browser_allowed and self._is_ecommerce_enabled():
            ecommerce_hint = (
                "【重要】上架文案必须基于前序 evidence 生成，不能凭空编造。\n\n"
                "要求：\n"
                "1. 标题和卖点必须引用前序 evidence 中的真实数据\n"
                "2. 定价必须基于前序竞品分析的真实价格\n"
                "3. 如果前序 evidence 不足，必须在 warnings 中说明\n"
                "4. 不要执行发布/付款/发消息等操作\n\n"
            )
        else:
            ecommerce_hint = (
                "【注意】当前浏览器自动化未授权，上架文案基于模型知识生成草稿。\n"
                "请在 warnings 中标注数据不足，建议用户补充真实数据后重新生成。\n\n"
            )

        return (
            f"{ecommerce_hint}"
            f"请为以下产品生成闲鱼/电商上架物料包：{goal}\n"
            f"{competitor_info}{pricing_info}{prev_evidence_info}\n\n"
            f"请严格按以下 JSON 格式输出（不要输出其他内容）：\n"
            f'{{\n'
            f'  "summary": "上架物料包摘要",\n'
            f'  "listing_copy": "完整的产品标题和详情文案（200-500字）",\n'
            f'  "evidence": [\n'
            f'    {{"title": "数据来源", "url": "https://真实URL", "type": "source/sourcing/browser"}},\n'
            f'    ...\n'
            f'  ],\n'
            f'  "tool_calls": [\n'
            f'    {{"tool": "工具名", "args": {{}}, "result": "调用结果摘要"}}\n'
            f'  ],\n'
            f'  "pricing": {{"recommended": "建议售价", "min": "最低价", "max": "最高价", "evidence_based": true}},\n'
            f'  "image_plan": {{"main_image": "主图建议", "lifestyle": "场景图建议", "details": "细节图建议"}},\n'
            f'  "next_actions": ["行动项1", "行动项2", "行动项3"],\n'
            f'  "warnings": ["警告信息（如有）"]\n'
            f'}}\n\n'
            f"【严格要求】\n"
            f"- listing_copy 中的标题、卖点、定价必须引用前序 evidence 中的真实数据\n"
            f"- pricing.evidence_based 必须为 true（基于前序数据）\n"
            f"- 如果前序 evidence 不足，必须在 warnings 中说明证据不足，不能编造数据\n"
            f"- 不要执行发布、付款、发消息等操作"
        )

    def execute_market_research(self, goal: str, context: Dict[str, Any] = None,
                                 allow_browser_automation: bool = False) -> Dict[str, Any]:
        """执行市场调研 — 带审批闸门和 evidence gate 验证"""
        # 检查浏览器自动化审批
        if not is_browser_automation_allowed(allow_from_request=allow_browser_automation, module_id="market"):
            return {
                "ok": False,
                "blocked": True,
                "summary": "",
                "evidence": [],
                "competitors": [],
                "pricing": {},
                "warnings": ["浏览器自动化采集需要用户确认后才能执行（模块: market）"],
                "raw_data": {"blocked_reason": "approval_required"},
            }

        context = dict(context or {})
        context.update({"allow_browser_automation": allow_browser_automation, "module_id": "market"})

        # Compute effective browser permission (may be approved via config/env even if request flag is False)
        browser_approved = is_browser_automation_allowed(
            allow_from_request=allow_browser_automation, module_id="market"
        )
        prompt = self._build_market_research_prompt(goal, context,
                                                     browser_allowed=browser_approved)
        cli_result = self._execute_hermes_cli(prompt, context)

        if cli_result.get("blocked"):
            return {
                "ok": False,
                "blocked": True,
                "summary": "",
                "evidence": [],
                "competitors": [],
                "pricing": {},
                "warnings": [cli_result["error"]],
                "raw_data": cli_result,
            }

        if not cli_result["ok"]:
            return {
                "ok": False,
                "summary": "",
                "evidence": [],
                "competitors": [],
                "pricing": {},
                "warnings": [cli_result["error"]],
                "raw_data": cli_result,
            }

        # 解析 JSON 输出
        parsed = self._parse_json_output(cli_result["stdout"])
        if not parsed:
            return {
                "ok": False,
                "summary": "",
                "evidence": [],
                "competitors": [],
                "pricing": {},
                "warnings": ["Hermes 输出无法解析为 JSON，无法获取真实证据"],
                "raw_data": cli_result,
            }

        # 提取新增字段
        tool_calls = parsed.get("tool_calls", [])
        evidence_files = parsed.get("evidence_files", [])
        screenshots = parsed.get("screenshots", [])

        # 构建原始 warning
        warnings = parsed.get("warnings", [])

        # 如果没有 tool_calls，添加警告
        if not tool_calls:
            warnings.append("Hermes 未记录工具调用，可能未使用真实工具链采集数据")

        # 检查 evidence gate
        from backend.services.boss_execution_providers import check_evidence_gate
        gate_result = check_evidence_gate(
            "market",
            evidence=parsed.get("evidence", []),
            competitors=parsed.get("competitors", []),
        )

        if not gate_result["passed"]:
            warnings.append(f"证据门槛未通过: {gate_result['details']}")

        return {
            "ok": True,
            "summary": parsed.get("summary", ""),
            "evidence": parsed.get("evidence", []),
            "evidence_files": evidence_files,
            "screenshots": screenshots,
            "tool_calls": tool_calls,
            "competitors": parsed.get("competitors", []),
            "pricing": parsed.get("pricing", {}),
            "warnings": warnings,
            "raw_data": {"cli_result": cli_result, "parsed": parsed},
            "evidence_gate_passed": gate_result["passed"],
            "missing_evidence": gate_result["missing"],
        }

    def execute_competitor_analysis(self, goal: str, competitors: List[Dict] = None,
                                     context: Dict[str, Any] = None,
                                     allow_browser_automation: bool = False) -> Dict[str, Any]:
        """执行竞品分析 — 带审批闸门和 evidence gate 验证"""
        # 检查浏览器自动化审批
        if not is_browser_automation_allowed(allow_from_request=allow_browser_automation, module_id="competitor_analysis"):
            return {
                "ok": False,
                "blocked": True,
                "summary": "",
                "competitors": competitors or [],
                "pricing": {},
                "warnings": ["浏览器自动化采集需要用户确认后才能执行（模块: competitor_analysis）"],
                "raw_data": {"blocked_reason": "approval_required"},
            }

        context = dict(context or {})
        context.update({"allow_browser_automation": allow_browser_automation, "module_id": "competitor_analysis"})

        # Compute effective browser permission (may be approved via config/env even if request flag is False)
        browser_approved = is_browser_automation_allowed(
            allow_from_request=allow_browser_automation, module_id="competitor_analysis"
        )
        prompt = self._build_competitor_analysis_prompt(goal, competitors, context,
                                                        browser_allowed=browser_approved)
        cli_result = self._execute_hermes_cli(prompt, context)

        if cli_result.get("blocked"):
            return {
                "ok": False,
                "blocked": True,
                "summary": "",
                "competitors": competitors or [],
                "pricing": {},
                "warnings": [cli_result["error"]],
                "raw_data": cli_result,
            }

        if not cli_result["ok"]:
            return {
                "ok": False,
                "summary": "",
                "competitors": competitors or [],
                "pricing": {},
                "warnings": [cli_result["error"]],
                "raw_data": cli_result,
            }

        parsed = self._parse_json_output(cli_result["stdout"])
        if not parsed:
            return {
                "ok": False,
                "summary": "",
                "competitors": competitors or [],
                "pricing": {},
                "warnings": ["Hermes 输出无法解析为 JSON，无法获取真实证据"],
                "raw_data": cli_result,
            }

        # 提取新增字段
        tool_calls = parsed.get("tool_calls", [])
        evidence_files = parsed.get("evidence_files", [])
        screenshots = parsed.get("screenshots", [])
        evidence = parsed.get("evidence", [])

        # 构建原始 warning
        warnings = parsed.get("warnings", [])

        # 如果没有 tool_calls，添加警告
        if not tool_calls:
            warnings.append("Hermes 未记录工具调用，可能未使用真实工具链采集数据")

        # 检查 evidence gate
        from backend.services.boss_execution_providers import check_evidence_gate
        gate_result = check_evidence_gate(
            "competitor_analysis",
            evidence=evidence,
            competitors=parsed.get("competitors", competitors or []),
        )

        if not gate_result["passed"]:
            warnings.append(f"证据门槛未通过: {gate_result['details']}")

        return {
            "ok": True,
            "summary": parsed.get("summary", ""),
            "evidence": evidence,
            "evidence_files": evidence_files,
            "screenshots": screenshots,
            "tool_calls": tool_calls,
            "competitors": parsed.get("competitors", competitors or []),
            "pricing": parsed.get("pricing", {}),
            "warnings": warnings,
            "raw_data": {"cli_result": cli_result, "parsed": parsed},
            "evidence_gate_passed": gate_result["passed"],
            "missing_evidence": gate_result["missing"],
        }

    def execute_listing_pack(self, goal: str, competitors: List[Dict] = None,
                             pricing: Dict[str, Any] = None,
                             context: Dict[str, Any] = None,
                             allow_browser_automation: bool = False) -> Dict[str, Any]:
        """执行上架物料包生成 — 带审批闸门，必须基于前序 evidence"""
        # 检查浏览器自动化审批（marketing 模块需要浏览器采集）
        if not is_browser_automation_allowed(allow_from_request=allow_browser_automation, module_id="marketing"):
            return {
                "ok": False,
                "blocked": True,
                "summary": "",
                "listing_copy": "",
                "pricing": pricing or {},
                "image_plan": {},
                "next_actions": [],
                "warnings": ["浏览器自动化采集需要用户确认后才能执行（模块: marketing/listing_pack）"],
                "raw_data": {"blocked_reason": "approval_required"},
            }

        context = dict(context or {})
        context.update({"allow_browser_automation": allow_browser_automation, "module_id": "marketing"})

        # Compute effective browser permission (may be approved via config/env even if request flag is False)
        browser_approved = is_browser_automation_allowed(
            allow_from_request=allow_browser_automation, module_id="marketing"
        )
        prompt = self._build_listing_pack_prompt(goal, competitors, pricing, context,
                                                 browser_allowed=browser_approved)
        cli_result = self._execute_hermes_cli(prompt, context)

        if cli_result.get("blocked"):
            return {
                "ok": False,
                "blocked": True,
                "summary": "",
                "listing_copy": "",
                "pricing": pricing or {},
                "image_plan": {},
                "next_actions": [],
                "warnings": [cli_result["error"]],
                "raw_data": cli_result,
            }

        if not cli_result["ok"]:
            return {
                "ok": False,
                "summary": "",
                "listing_copy": "",
                "pricing": pricing or {},
                "image_plan": {},
                "next_actions": [],
                "warnings": [cli_result["error"]],
                "raw_data": cli_result,
            }

        parsed = self._parse_json_output(cli_result["stdout"])
        if not parsed:
            return {
                "ok": False,
                "summary": "",
                "listing_copy": "",
                "pricing": pricing or {},
                "image_plan": {},
                "next_actions": [],
                "warnings": ["Hermes 输出无法解析为 JSON，无法基于证据生成文案"],
                "raw_data": cli_result,
            }

        # 提取新增字段
        tool_calls = parsed.get("tool_calls", [])
        evidence = parsed.get("evidence", [])
        evidence_files = parsed.get("evidence_files", [])
        screenshots = parsed.get("screenshots", [])

        # 构建原始 warning
        warnings = parsed.get("warnings", [])

        # 检查前序 evidence 是否足够
        if context and context.get("prev_results"):
            prev_evidence_count = 0
            for module_id, module_data in context["prev_results"].items():
                so = module_data.get("structured_output", {})
                prev_evidence_count += len(so.get("evidence", []))

            if prev_evidence_count == 0:
                warnings.append("前序模块未提供任何 evidence，上架文案可能基于模型知识而非真实数据")
        else:
            warnings.append("未获取到前序模块结果，上架文案可能基于模型知识而非真实数据")

        # 检查 evidence gate
        from backend.services.boss_execution_providers import check_evidence_gate
        gate_result = check_evidence_gate(
            "listing_pack",
            evidence=evidence,
            prev_results=context.get("prev_results") if context else None,
        )

        if not gate_result["passed"]:
            warnings.append(f"证据门槛未通过: {gate_result['details']}")

        # 检查 pricing 是否基于 evidence
        result_pricing = parsed.get("pricing", pricing or {})
        if isinstance(result_pricing, dict) and not result_pricing.get("evidence_based"):
            warnings.append("定价未明确标注基于 evidence，可能是凭空生成")

        return {
            "ok": True,
            "summary": parsed.get("summary", ""),
            "listing_copy": parsed.get("listing_copy", ""),
            "pricing": result_pricing,
            "image_plan": parsed.get("image_plan", {}),
            "next_actions": parsed.get("next_actions", []),
            "evidence": evidence,
            "evidence_files": evidence_files,
            "screenshots": screenshots,
            "tool_calls": tool_calls,
            "warnings": warnings,
            "raw_data": {"cli_result": cli_result, "parsed": parsed},
            "evidence_gate_passed": gate_result["passed"],
            "missing_evidence": gate_result["missing"],
        }


# ── Provider Registry ─────────────────────────────────────

class ProviderRegistry:
    """Provider 注册表 — 管理和选择 Provider"""

    def __init__(self):
        self._providers: Dict[str, BossExecutionProvider] = {}
        self._fallback_chain: List[str] = []

    def register(self, provider: BossExecutionProvider, is_fallback: bool = False):
        """注册 Provider"""
        self._providers[provider.name] = provider
        if is_fallback:
            self._fallback_chain.append(provider.name)

    def get_provider(self, name: str) -> Optional[BossExecutionProvider]:
        """获取指定 Provider"""
        return self._providers.get(name)

    def get_available_provider(self, preferred: str = None) -> tuple[BossExecutionProvider, List[str]]:
        """获取可用的 Provider，返回 (provider, warnings)

        优先使用 preferred，如果不可用则按 fallback_chain 选择。
        """
        warnings = []

        # 尝试首选 provider
        if preferred:
            provider = self._providers.get(preferred)
            if provider and provider.is_available:
                return provider, warnings
            if provider:
                warnings.append(f"首选 Provider '{preferred}' 不可用，尝试 fallback")

        # 按 fallback chain 尝试
        for name in self._fallback_chain:
            provider = self._providers.get(name)
            if provider and provider.is_available:
                if preferred and name != preferred:
                    warnings.append(f"已 fallback 到 Provider '{name}'")
                return provider, warnings

        # 所有都不可用
        raise RuntimeError("没有可用的 Execution Provider")

    def list_providers(self) -> List[Dict[str, Any]]:
        """列出所有 Provider"""
        return [
            {
                "name": p.name,
                "available": p.is_available,
                "in_fallback_chain": p.name in self._fallback_chain,
            }
            for p in self._providers.values()
        ]


# ── 全局实例 ──────────────────────────────────────────────

_registry = None


def get_provider_registry() -> ProviderRegistry:
    """获取 Provider Registry 单例"""
    global _registry
    if _registry is None:
        _registry = ProviderRegistry()

        # 注册所有 Provider
        mock_provider = LocalMockExecutionProvider()
        heuristic_provider = LocalHeuristicExecutionProvider()
        hermes_provider = HermesExecutionProvider()

        _registry.register(mock_provider)
        _registry.register(hermes_provider)
        _registry.register(heuristic_provider, is_fallback=True)  # 默认 fallback

    return _registry
