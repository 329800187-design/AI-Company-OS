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


# ── 标准化输出结构 ────────────────────────────────────────

def create_standard_output(
    status: str = "success",
    summary: str = "",
    evidence: List[Dict[str, Any]] = None,
    competitors: List[Dict[str, Any]] = None,
    pricing: Dict[str, Any] = None,
    listing_copy: str = "",
    image_plan: Dict[str, Any] = None,
    next_actions: List[str] = None,
    warnings: List[str] = None,
    provider: str = "",
    raw_data: Dict[str, Any] = None,
) -> Dict[str, Any]:
    """创建标准化的 structured_output"""
    return {
        "status": status,
        "summary": summary,
        "evidence": evidence or [],
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
    def execute_market_research(self, goal: str, context: Dict[str, Any] = None) -> Dict[str, Any]:
        """执行市场调研

        Returns:
            {
                "ok": bool,
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
                                     context: Dict[str, Any] = None) -> Dict[str, Any]:
        """执行竞品分析

        Returns:
            {
                "ok": bool,
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
                             context: Dict[str, Any] = None) -> Dict[str, Any]:
        """执行上架物料包生成

        Returns:
            {
                "ok": bool,
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

    def execute_market_research(self, goal: str, context: Dict[str, Any] = None) -> Dict[str, Any]:
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
                                     context: Dict[str, Any] = None) -> Dict[str, Any]:
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
                             context: Dict[str, Any] = None) -> Dict[str, Any]:
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

    def execute_market_research(self, goal: str, context: Dict[str, Any] = None) -> Dict[str, Any]:
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
                                     context: Dict[str, Any] = None) -> Dict[str, Any]:
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
                             context: Dict[str, Any] = None) -> Dict[str, Any]:
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
        """检查 Hermes CLI 是否可用"""
        try:
            import shutil
            cli_path = self._get_cli_path()
            return shutil.which(cli_path) is not None
        except Exception:
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
        """执行 Hermes CLI 调用

        Args:
            prompt: 完整的 prompt 内容
            context: 执行上下文（包含 mission_id, module_id 等）

        Returns:
            {
                "ok": bool,
                "stdout": str,
                "stderr": str,
                "exit_code": int,
                "error": str,
            }
        """
        import subprocess
        import json

        cli_path = self._get_cli_path()
        timeout = self._get_timeout()

        # 构建命令：hermes -z "<prompt>"
        # 使用 -z 标志表示非交互模式
        cmd = [cli_path, "-z", prompt]

        try:
            # 执行 subprocess
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=timeout,
                encoding="utf-8",
            )

            return {
                "ok": result.returncode == 0,
                "stdout": result.stdout,
                "stderr": result.stderr,
                "exit_code": result.returncode,
                "error": result.stderr if result.returncode != 0 else "",
            }

        except subprocess.TimeoutExpired:
            return {
                "ok": False,
                "stdout": "",
                "stderr": "",
                "exit_code": -1,
                "error": f"Hermes CLI 执行超时（{timeout}秒）",
            }
        except FileNotFoundError:
            return {
                "ok": False,
                "stdout": "",
                "stderr": "",
                "exit_code": -1,
                "error": f"Hermes CLI 未找到: {cli_path}",
            }
        except Exception as e:
            return {
                "ok": False,
                "stdout": "",
                "stderr": "",
                "exit_code": -1,
                "error": f"Hermes CLI 执行异常: {str(e)}",
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

    def _build_market_research_prompt(self, goal: str, context: Dict[str, Any] = None) -> str:
        """构建市场调研 prompt"""
        ecommerce_hint = ""
        if self._is_ecommerce_enabled():
            ecommerce_hint = (
                "请使用 /ecommerce 技能或 ecommerce 相关技能。\n"
                "优先使用 sourcing-price-bridge / ecommerce-bridge 获取真实数据。\n"
                "可以使用 browser 采集证据，但不要执行发布/付款/发消息等操作。\n\n"
            )

        return (
            f"{ecommerce_hint}"
            f"请调研以下电商业务的市场情况：{goal}\n\n"
            f"请严格按以下 JSON 格式输出（不要输出其他内容）：\n"
            f'{{\n'
            f'  "summary": "市场调研摘要（200-500字）",\n'
            f'  "evidence": [{{"title": "来源标题", "url": "来源URL"}}],\n'
            f'  "competitors": [{{"name": "竞品名称", "price": "价格区间", "platform": "平台", "features": "核心卖点"}}],\n'
            f'  "pricing": {{"range": "价格区间", "avg": "平均价格"}},\n'
            f'  "warnings": ["警告信息（如有）"]\n'
            f'}}\n\n'
            f"注意：\n"
            f"- 竞品列表至少 3 个\n"
            f"- 尽量引用真实来源\n"
            f"- 不要执行发布、付款、发消息等操作"
        )

    def _build_competitor_analysis_prompt(self, goal: str, competitors: List[Dict] = None,
                                          context: Dict[str, Any] = None) -> str:
        """构建竞品分析 prompt"""
        import json as json_lib

        competitor_info = ""
        if competitors:
            competitor_info = f"\n已知竞品信息：{json_lib.dumps(competitors, ensure_ascii=False)}\n"

        ecommerce_hint = ""
        if self._is_ecommerce_enabled():
            ecommerce_hint = (
                "请使用 /ecommerce 技能或 ecommerce 相关技能。\n"
                "优先使用 sourcing-price-bridge / ecommerce-bridge 获取真实数据。\n\n"
            )

        return (
            f"{ecommerce_hint}"
            f"请对电商业务「{goal}」做竞品分析：{competitor_info}\n\n"
            f"请严格按以下 JSON 格式输出（不要输出其他内容）：\n"
            f'{{\n'
            f'  "summary": "竞品分析摘要（200-500字）",\n'
            f'  "competitors": [{{"name": "竞品名称", "price": "价格", "strengths": "优势", "weaknesses": "劣势"}}],\n'
            f'  "pricing": {{"recommended_range": "建议定价范围", "rationale": "定价理由"}},\n'
            f'  "warnings": ["警告信息（如有）"]\n'
            f'}}\n\n'
            f"注意：\n"
            f"- 分析至少 3 个竞品\n"
            f"- 给出明确的定价建议\n"
            f"- 不要执行发布、付款、发消息等操作"
        )

    def _build_listing_pack_prompt(self, goal: str, competitors: List[Dict] = None,
                                   pricing: Dict[str, Any] = None,
                                   context: Dict[str, Any] = None) -> str:
        """构建上架物料包 prompt"""
        import json as json_lib

        competitor_info = ""
        if competitors:
            competitor_info = f"\n竞品信息：{json_lib.dumps(competitors, ensure_ascii=False)}\n"

        pricing_info = ""
        if pricing:
            pricing_info = f"\n定价参考：{json_lib.dumps(pricing, ensure_ascii=False)}\n"

        ecommerce_hint = ""
        if self._is_ecommerce_enabled():
            ecommerce_hint = (
                "请使用 /ecommerce 技能或 ecommerce 相关技能。\n"
                "优先使用 sourcing-price-bridge / ecommerce-bridge 获取真实数据。\n\n"
            )

        return (
            f"{ecommerce_hint}"
            f"请为以下产品生成闲鱼/电商上架物料包：{goal}\n"
            f"{competitor_info}{pricing_info}\n\n"
            f"请严格按以下 JSON 格式输出（不要输出其他内容）：\n"
            f'{{\n'
            f'  "summary": "上架物料包摘要",\n'
            f'  "listing_copy": "完整的产品标题和详情文案（200-500字）",\n'
            f'  "pricing": {{"recommended": "建议售价", "min": "最低价", "max": "最高价"}},\n'
            f'  "image_plan": {{"main_image": "主图建议", "lifestyle": "场景图建议", "details": "细节图建议"}},\n'
            f'  "next_actions": ["行动项1", "行动项2", "行动项3"],\n'
            f'  "warnings": ["警告信息（如有）"]\n'
            f'}}\n\n'
            f"注意：\n"
            f"- 生成可直接使用的文案\n"
            f"- 给出明确的定价建议\n"
            f"- 提供图片拍摄建议\n"
            f"- 不要执行发布、付款、发消息等操作"
        )

    def execute_market_research(self, goal: str, context: Dict[str, Any] = None) -> Dict[str, Any]:
        """执行市场调研"""
        prompt = self._build_market_research_prompt(goal, context)
        cli_result = self._execute_hermes_cli(prompt, context)

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
                "warnings": ["Hermes 输出无法解析为 JSON"],
                "raw_data": cli_result,
            }

        return {
            "ok": True,
            "summary": parsed.get("summary", ""),
            "evidence": parsed.get("evidence", []),
            "competitors": parsed.get("competitors", []),
            "pricing": parsed.get("pricing", {}),
            "warnings": parsed.get("warnings", []),
            "raw_data": {"cli_result": cli_result, "parsed": parsed},
        }

    def execute_competitor_analysis(self, goal: str, competitors: List[Dict] = None,
                                     context: Dict[str, Any] = None) -> Dict[str, Any]:
        """执行竞品分析"""
        prompt = self._build_competitor_analysis_prompt(goal, competitors, context)
        cli_result = self._execute_hermes_cli(prompt, context)

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
                "warnings": ["Hermes 输出无法解析为 JSON"],
                "raw_data": cli_result,
            }

        return {
            "ok": True,
            "summary": parsed.get("summary", ""),
            "competitors": parsed.get("competitors", competitors or []),
            "pricing": parsed.get("pricing", {}),
            "warnings": parsed.get("warnings", []),
            "raw_data": {"cli_result": cli_result, "parsed": parsed},
        }

    def execute_listing_pack(self, goal: str, competitors: List[Dict] = None,
                             pricing: Dict[str, Any] = None,
                             context: Dict[str, Any] = None) -> Dict[str, Any]:
        """执行上架物料包生成"""
        prompt = self._build_listing_pack_prompt(goal, competitors, pricing, context)
        cli_result = self._execute_hermes_cli(prompt, context)

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
                "warnings": ["Hermes 输出无法解析为 JSON"],
                "raw_data": cli_result,
            }

        return {
            "ok": True,
            "summary": parsed.get("summary", ""),
            "listing_copy": parsed.get("listing_copy", ""),
            "pricing": parsed.get("pricing", pricing or {}),
            "image_plan": parsed.get("image_plan", {}),
            "next_actions": parsed.get("next_actions", []),
            "warnings": parsed.get("warnings", []),
            "raw_data": {"cli_result": cli_result, "parsed": parsed},
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
