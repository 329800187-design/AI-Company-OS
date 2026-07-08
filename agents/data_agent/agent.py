"""
Data Agent — 数据分析智能体

能力：
1. data_load: 加载 CSV/Excel/JSON 文件，自动检测编码
2. data_explore: 数据探索 (shape/dtypes/missing/describe)
3. data_clean: 数据清洗 (去重/填充缺失/异常值/格式统一)
4. data_analyze: 统计分析 (groupby/aggregate/correlation)
5. data_viz: 可视化图表生成 (bar/line/pie/scatter/heatmap)
6. data_export: 导出 CSV/Excel/JSON + 分析报告

执行路径（纯文本目标）：
  1. 有 API key/provider → 调用真实 LLM（通过 BrainManager）生成数据分析报告
  2. LLM 返回有效 JSON → 规范化 structured_output
  3. 无 key / 调用失败 / 无效 JSON → 模板 fallback

注意：
- 本阶段不做真实文件上传解析（文件加载路径保留但非 LLM-first 主路径）
- 不接数据库、不生成 BI 图表
- 无真实数据文件时，LLM 产出为分析框架/建议，非真实数据计算
"""
import json
import os
import re
import uuid
from typing import Any, Dict, List, Optional

from agents.base_agent import BaseAgent
from backend.services.data_source_service import detect_and_load, DataSourceResult

OUTPUT_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__)))), "output", "data_agent")
os.makedirs(OUTPUT_DIR, exist_ok=True)

# 尝试导入数据分析库
try:
    import pandas as _pd
    PANDAS_AVAILABLE = True
except ImportError:
    PANDAS_AVAILABLE = False

try:
    import matplotlib as _mpl
    _mpl.use('Agg')
    import matplotlib.pyplot as _plt
    MATPLOTLIB_AVAILABLE = True
except ImportError:
    MATPLOTLIB_AVAILABLE = False


# ── System Prompt ────────────────────────────────────────

DATA_REPORT_PROMPT = """你是一位资深数据分析师。根据用户的数据分析需求，生成结构化的数据分析报告框架。

要求：
- 基于用户描述的分析目标，给出专业的分析框架和指标建议
- 如果用户提供了数据摘要或描述，基于此进行分析建议
- 明确标注数据局限性（是否有真实数据文件支撑）
- 给出可执行的分析建议和下一步行动
- 建议适合的可视化图表类型

输出格式（JSON）：
{
  "analysis_question": "本次分析的核心问题",
  "data_summary": "数据概况描述（基于用户提供的信息）",
  "key_metrics": [
    {"name": "指标名", "description": "指标说明", "formula": "计算公式（如有）"}
  ],
  "trends": ["趋势1", "趋势2"],
  "findings": ["发现1", "发现2", "发现3"],
  "risks": ["风险1", "风险2"],
  "recommendations": ["建议1", "建议2", "建议3"],
  "assumptions": ["假设1", "假设2"],
  "limitations": ["局限性说明"],
  "charts_suggested": [
    {"type": "图表类型", "x_axis": "X轴", "y_axis": "Y轴", "purpose": "用途"}
  ]
}

注意：
- limitations 必须包含"本报告未基于真实数据文件计算，为分析框架建议"说明
- charts_suggested 建议具体图表类型和用途
- 只输出 JSON，不要其他文字。"""


class DataAgent(BaseAgent):
    """Data Agent — 数据分析与可视化

    执行优先级（纯文本目标）：
      1. 调用真实 LLM（BrainManager 自动选 provider）
      2. LLM 返回有效 JSON → 规范化 structured_output
      3. 无 key / 调用失败 / 无效 JSON → 模板 fallback

    文件加载路径（data_load）保留原有 pandas 能力，不受 LLM-first 影响。
    """

    AGENT_ID = "data"
    DISPLAY_NAME = "数据分析"
    CAPABILITIES = ["data", "pandas", "visualization", "csv", "excel"]
    TASK_TYPES = ["data_load", "data_explore", "data_clean", "data_analyze", "data_viz", "data_export"]

    ALLOWED_EXT = {'.csv', '.xlsx', '.xls', '.json', '.tsv', '.parquet'}

    REQUIRED_FIELDS = [
        "analysis_question", "data_summary", "key_metrics",
        "trends", "findings", "risks", "recommendations",
        "assumptions", "limitations", "charts_suggested",
    ]

    def __init__(self, api_key: Optional[str] = None, timeout: int = 60):
        super().__init__(name="data", timeout=timeout)
        self.api_key = api_key or ""
        self._df = None
        self._file_name = ""

    def run(self, task: Dict[str, Any]) -> Dict[str, Any]:
        task_id = task.get("task_id", f"data_{uuid.uuid4().hex[:8]}")
        task_type = task.get("task_type", "data_analyze")

        if task_type == "data_load":
            return self._load_data(task, task_id)
        elif task_type in ("data_explore", "data_clean", "data_analyze", "data_viz", "data_export"):
            # 如果没有已加载数据，走智能路由（支持纯文本目标 → LLM-first）
            if self._df is None:
                return self._smart_dispatch(task, task_id)
            if task_type == "data_explore":
                return self._explore(task, task_id)
            elif task_type == "data_clean":
                return self._clean(task, task_id)
            elif task_type == "data_analyze":
                return self._analyze(task, task_id)
            elif task_type == "data_viz":
                return self._visualize(task, task_id)
            elif task_type == "data_export":
                return self._export(task, task_id)
        else:
            return self._smart_dispatch(task, task_id)

    # ── 智能路由 ──────────────────────────────────────────

    def _smart_dispatch(self, task: Dict, task_id: str) -> Dict:
        goal = task.get("goal", task.get("prompt", ""))

        # ── Phase 4.4: 优先通过 data_source_service 检测数据源 ──
        ds_result = detect_and_load(task)
        if ds_result.ok and ds_result.df is not None:
            # 成功加载真实数据 → 走 pandas 分析路径
            self._df = ds_result.df
            self._file_name = ds_result.file_name
            load_result = self._load_from_ds_result(ds_result, task_id)
            explore_result = self._explore(task, task_id)
            if explore_result.get("ok"):
                return self._build_analysis_result(
                    task_id, goal, load_result, explore_result,
                    data_source_type=ds_result.source_type,
                    row_count=ds_result.row_count,
                )
            return load_result

        # ── 兜底：原有 file_path / content 检测（兼容 xlsx/xls 等）──
        file_path = task.get("file_path", task.get("path", ""))
        if file_path and os.path.exists(file_path):
            load_result = self._load_data(task, task_id)
            if load_result.get("ok"):
                explore_result = self._explore(task, task_id)
                if explore_result.get("ok"):
                    ext = os.path.splitext(file_path)[1].lower()
                    ds_type = "csv" if ext == ".csv" else "json" if ext == ".json" else "file"
                    return self._build_analysis_result(
                        task_id, goal, load_result, explore_result,
                        data_source_type=ds_type,
                    )
            return load_result

        content = task.get("content", task.get("data", ""))
        if content:
            load_result = self._load_data(task, task_id)
            if load_result.get("ok"):
                explore_result = self._explore(task, task_id)
                if explore_result.get("ok"):
                    return self._build_analysis_result(
                        task_id, goal, load_result, explore_result,
                        data_source_type="inline",
                    )
            return load_result

        # ── 纯文本目标 → LLM-first 数据分析报告生成 ──
        return self._llm_first_dispatch(task, task_id, goal)

    # ── LLM-first 纯文本目标 ─────────────────────────────

    def _llm_first_dispatch(self, task: Dict, task_id: str, goal: str) -> Dict:
        """纯文本目标：优先调用 LLM 生成数据分析报告"""
        sys_prompt = DATA_REPORT_PROMPT

        # ── 尝试真实 LLM ────────────────────────────────────
        llm_result = self._try_llm(sys_prompt, goal)
        if llm_result is not None:
            enriched = self._enrich_result(llm_result, goal)
            enriched["content_type"] = "data_report"
            return self.ok(
                task_id,
                status="completed",
                data=enriched,
                meta={
                    "fallback": False,
                    "model": getattr(self, "model", ""),
                    "source": "llm",
                    "data_source_type": "none",
                    "sample_rows": 0,
                },
            )

        # ── 模板 fallback ────────────────────────────────────
        return self._rule_fallback(task_id, goal)

    # ── LLM 调用（复用 BrainManager）───────────────────────

    def _try_llm(self, system_prompt: str, user_prompt: str) -> Optional[Dict]:
        """尝试调用真实 LLM，返回规范化 structured_output 或 None。"""
        try:
            resp = self.call_ai(
                message=user_prompt,
                system=system_prompt,
                temperature=0.7,
                max_tokens=3000,
            )
            if not resp.get("ok"):
                self.logger.warning(
                    "[Data Agent] LLM 调用失败: %s", resp.get("error", "unknown")
                )
                return None

            text = resp.get("reply", "")
            raw = self._extract_json(text)
            if raw is None:
                self.logger.warning("[Data Agent] LLM 返回无效 JSON，回退模板")
                return None

            return self._normalize_structured_output(raw, user_prompt)

        except Exception as e:
            self.logger.error("[Data Agent] LLM 调用异常: %s", e)
            return None

    # ── structured_output 规范化 ─────────────────────────────

    def _normalize_structured_output(self, raw: Dict, prompt: str = "") -> Dict:
        """确保至少包含 10 个必选字段 + content_type。"""
        out = dict(raw)
        out.setdefault("analysis_question", prompt or "未指定")
        out.setdefault("data_summary", "")
        out.setdefault("key_metrics", [])
        out.setdefault("trends", [])
        out.setdefault("findings", [])
        out.setdefault("risks", [])
        out.setdefault("recommendations", [])
        out.setdefault("assumptions", [])
        out.setdefault("limitations", [])
        out.setdefault("charts_suggested", [])

        # 确保 limitations 包含无真实数据声明
        limitations = out.get("limitations", [])
        if not isinstance(limitations, list):
            limitations = [str(limitations)]
        data_note = "本报告未基于真实数据文件计算，为分析框架建议。如需真实数据分析，请上传 CSV/Excel 文件。"
        if not any("未基于真实数据" in l or "真实数据文件" in l for l in limitations):
            limitations.append(data_note)
        out["limitations"] = limitations

        return out

    # ── 结果增强 ──────────────────────────────────────────

    @staticmethod
    def _enrich_result(data: Dict, goal: str) -> Dict:
        """确保标准字段存在"""
        enriched = dict(data)
        enriched.setdefault("analysis_question", goal)
        enriched.setdefault("data_summary", "")
        enriched.setdefault("key_metrics", [])
        enriched.setdefault("trends", [])
        enriched.setdefault("findings", [])
        enriched.setdefault("risks", [])
        enriched.setdefault("recommendations", [])
        enriched.setdefault("assumptions", [])
        enriched.setdefault("limitations", [])
        enriched.setdefault("charts_suggested", [])
        return enriched

    # ── JSON 提取 ──────────────────────────────────────────

    @staticmethod
    def _extract_json(text: str) -> Optional[Dict]:
        text = re.sub(r"```(?:json)?\s*", "", text).replace("```", "").strip()
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            match = re.search(r"\{[\s\S]*\}", text)
            if match:
                try:
                    return json.loads(match.group())
                except json.JSONDecodeError:
                    pass
        return None

    # ── 规则降级 ──────────────────────────────────────────

    def _rule_fallback(self, task_id: str, goal: str) -> Dict:
        """无 AI API 时的规则降级 — 生成数据分析框架"""
        topic = self._extract_topic(goal)

        # 根据目标关键词推断分析维度
        goal_lower = goal.lower()
        key_metrics = []
        trends = []
        findings = []
        charts_suggested = []

        if any(kw in goal_lower for kw in ["销售", "sale", "营收", "revenue", "订单"]):
            key_metrics = [
                {"name": "销售额", "description": "指定时间段内的总销售金额", "formula": "SUM(金额)"},
                {"name": "订单数", "description": "指定时间段内的总订单数量", "formula": "COUNT(订单)"},
                {"name": "客单价", "description": "平均每笔订单金额", "formula": "销售额/订单数"},
                {"name": "转化率", "description": "浏览到下单的转化比例", "formula": "订单数/UV"},
            ]
            trends = ["时间维度趋势（日/周/月）", "品类对比趋势", "地区分布趋势"]
            findings = [
                f"关于「{topic}」的销售数据分析框架已生成",
                "建议分析时间维度趋势（日/周/月）",
                "建议按商品类别/地区做分组对比",
                "建议关注复购率和客单价变化",
            ]
            charts_suggested = [
                {"type": "折线图", "x_axis": "日期", "y_axis": "销售额", "purpose": "趋势分析"},
                {"type": "柱状图", "x_axis": "商品类别", "y_axis": "销售额", "purpose": "品类对比"},
                {"type": "饼图", "x_axis": "地区", "y_axis": "占比", "purpose": "地区分布"},
            ]
        elif any(kw in goal_lower for kw in ["用户", "user", "客户", "customer", "画像"]):
            key_metrics = [
                {"name": "活跃率", "description": "活跃用户占比", "formula": "活跃用户/总用户"},
                {"name": "留存率", "description": "次日/7日/30日留存", "formula": "留存用户/新增用户"},
                {"name": "ARPU", "description": "每用户平均收入", "formula": "总收入/用户数"},
                {"name": "LTV", "description": "用户生命周期价值", "formula": "ARPU×平均生命周期"},
            ]
            trends = ["用户增长趋势", "活跃度变化趋势", "消费行为趋势"]
            findings = [
                f"关于「{topic}」的用户分析框架已生成",
                "建议分析用户人口统计分布",
                "建议分析用户行为特征（活跃度/留存率）",
                "建议做用户分群（高价值/流失风险/新用户）",
            ]
            charts_suggested = [
                {"type": "柱状图", "x_axis": "年龄段", "y_axis": "用户数", "purpose": "人口分布"},
                {"type": "漏斗图", "x_axis": "转化阶段", "y_axis": "用户数", "purpose": "转化分析"},
                {"type": "散点图", "x_axis": "活跃度", "y_axis": "消费金额", "purpose": "分群分析"},
            ]
        elif any(kw in goal_lower for kw in ["运营", "operation", "电商", "ecommerce", "流量"]):
            key_metrics = [
                {"name": "UV", "description": "独立访客数", "formula": "COUNT(DISTINCT user_id)"},
                {"name": "PV", "description": "页面浏览量", "formula": "COUNT(page_view)"},
                {"name": "转化率", "description": "访问到购买的转化比例", "formula": "购买用户/UV"},
                {"name": "GMV", "description": "成交总额", "formula": "SUM(成交金额)"},
            ]
            trends = ["流量来源趋势", "转化率变化趋势", "渠道ROI趋势"]
            findings = [
                f"关于「{topic}」的运营分析框架已生成",
                "建议分析流量来源与转化路径",
                "建议关注核心转化节点的漏斗表现",
                "建议对比不同渠道的 ROI",
            ]
            charts_suggested = [
                {"type": "漏斗图", "x_axis": "转化阶段", "y_axis": "用户数", "purpose": "转化漏斗"},
                {"type": "折线图", "x_axis": "日期", "y_axis": "UV/PV", "purpose": "流量趋势"},
                {"type": "柱状图", "x_axis": "渠道", "y_axis": "ROI", "purpose": "渠道对比"},
            ]
        else:
            key_metrics = [
                {"name": "数据行数", "description": "数据集的记录总数", "formula": "COUNT(*)"},
                {"name": "数据列数", "description": "数据集的字段总数", "formula": "COUNT(columns)"},
            ]
            trends = ["待上传数据后自动检测"]
            findings = [
                f"关于「{topic}」的数据分析框架已生成",
                "请上传数据文件以获取真实分析结果",
                "支持 CSV/Excel/JSON/Parquet 格式",
            ]
            charts_suggested = [
                {"type": "柱状图", "x_axis": "待定", "y_axis": "待定", "purpose": "待上传数据后确定"},
            ]

        result_data = {
            "analysis_question": goal,
            "data_summary": f"关于「{topic}」的数据分析框架。当前为模板模式，未调用 AI。配置 AI API Key 后可获得定制化分析报告。",
            "key_metrics": key_metrics,
            "trends": trends,
            "findings": findings,
            "risks": [
                "未基于真实数据文件计算，分析结论需数据验证",
                "当前为框架模式，风险评估不完整",
            ],
            "recommendations": [
                "配置 AI API Key（DeepSeek/OpenAI/Claude）以获得智能分析",
                "上传数据文件（CSV/Excel/JSON）进行真实数据分析",
                "描述分析目标以便选择合适的分析方法",
                "指定输出格式（报告/图表/数据导出）",
            ],
            "assumptions": [
                "假设用户具备基本的数据分析背景",
                "假设分析目标明确且可量化",
            ],
            "limitations": [
                "本报告未基于真实数据文件计算，为模板/规则降级产物",
                "未调用 AI，内容为模板占位",
                "如需真实数据分析，请上传数据文件或配置 AI API",
            ],
            "charts_suggested": charts_suggested,
            "content_type": "data_report",
        }

        result = self.ok(
            task_id,
            status="模板模式 — 数据分析框架已生成",
            data=result_data,
            meta={
                "fallback": True,
                "fallback_reason": "无可用 LLM provider 或 API key，使用模板占位内容",
                "source": "template",
                "data_source_type": "none",
                "sample_rows": 0,
            },
        )
        result["warnings"] = [
            "当前为模板/规则降级产物，非真实 LLM 生成。配置 AI API Key 后可获得定制分析。",
            "本报告未基于真实数据文件计算，为分析框架建议。",
        ]
        return result

    @staticmethod
    def _extract_topic(text: str, max_len: int = 20) -> str:
        stopwords = {"帮我", "请", "写", "生成", "一个", "一份", "一篇", "的", "和", "与", "了",
                      "做", "分析", "数据", "报告", "简报", "看看"}
        for sw in stopwords:
            text = text.replace(sw, " ")
        words = [w for w in text.split() if len(w) >= 2]
        topic = " ".join(words[:4]) if words else text[:30]
        return topic[:max_len] or "未指定"

    # ── 加载 ──────────────────────────────────────────

    def _load_from_ds_result(self, ds_result: DataSourceResult, task_id: str) -> Dict:
        """从 DataSourceResult 构建加载结果（与 _load_data 输出格式一致）"""
        return self.ok(task_id, "加载完成", {
            "shape": [ds_result.row_count, ds_result.col_count],
            "columns": ds_result.columns,
            "dtypes": {k: str(v) for k, v in ds_result.df.dtypes.items()} if ds_result.df is not None else {},
            "missing": int(ds_result.df.isnull().sum().sum()) if ds_result.df is not None else 0,
            "preview": ds_result.df.head(5).to_dict(orient="records") if ds_result.df is not None else [],
        })

    def _load_data(self, task: Dict, task_id: str) -> Dict:
        file_path = task.get("file_path", task.get("path", ""))
        url = task.get("url", "")
        content = task.get("content", task.get("data", ""))

        if not PANDAS_AVAILABLE:
            return self.fail(task_id, "pandas 未安装。请运行: pip install pandas openpyxl")

        try:
            if file_path and os.path.exists(file_path):
                self._file_name = os.path.basename(file_path)
                ext = os.path.splitext(file_path)[1].lower()
                if ext == '.csv':
                    self._df = _pd.read_csv(file_path, encoding='utf-8')
                elif ext in ('.xlsx', '.xls'):
                    self._df = _pd.read_excel(file_path)
                elif ext == '.json':
                    self._df = _pd.read_json(file_path)
                elif ext == '.tsv':
                    self._df = _pd.read_csv(file_path, sep='\t')
                elif ext == '.parquet':
                    self._df = _pd.read_parquet(file_path)
            elif url:
                self._file_name = url.split('/')[-1] or "data"
                self._df = _pd.read_csv(url) if url.endswith('.csv') else _pd.read_json(url)
            elif content:
                self._file_name = "inline_data"
                self._df = _pd.read_json(json.dumps(json.loads(content))) if content.startswith('[') else \
                           _pd.read_csv(__import__('io').StringIO(content))

            if self._df is None:
                return self.fail(task_id, "无法加载数据: 请提供 file_path/url/content")

            info = self._df_info()
            return self.ok(task_id, "加载完成", {
                "shape": list(self._df.shape),
                "columns": list(self._df.columns),
                "dtypes": {k: str(v) for k, v in self._df.dtypes.items()},
                "missing": int(self._df.isnull().sum().sum()),
                "preview": self._df.head(5).to_dict(orient="records"),
            })

        except Exception as e:
            return self.fail(task_id, f"数据加载失败: {e}")

    # ── 探索 ──────────────────────────────────────────

    def _explore(self, task: Dict, task_id: str) -> Dict:
        if self._df is None:
            return self.fail(task_id, "请先加载数据 (data_load)")

        describe = self._df.describe(include='all').to_dict() if PANDAS_AVAILABLE else {}
        missing = self._df.isnull().sum().to_dict() if PANDAS_AVAILABLE else {}
        nunique = {c: int(self._df[c].nunique()) for c in self._df.columns} if PANDAS_AVAILABLE else {}

        return self.ok(task_id, "探索完成", {
            "shape": list(self._df.shape),
            "memory": f"{self._df.memory_usage(deep=True).sum() / 1024:.1f} KB",
            "dtypes": {k: str(v) for k, v in self._df.dtypes.items()},
            "missing_count": {k: int(v) for k, v in missing.items()},
            "missing_pct": {k: f"{v/len(self._df)*100:.1f}%" for k, v in missing.items()},
            "unique_values": nunique,
            "describe": describe,
            "duplicates": int(self._df.duplicated().sum()),
        })

    # ── 清洗 ──────────────────────────────────────────

    def _clean(self, task: Dict, task_id: str) -> Dict:
        if self._df is None:
            return self.fail(task_id, "请先加载数据")

        actions = []
        df = self._df.copy()

        if task.get("drop_duplicates", True):
            before = len(df)
            df = df.drop_duplicates()
            removed = before - len(df)
            if removed > 0:
                actions.append(f"去除 {removed} 条重复行")

        fill_strategy = task.get("fill_missing", "")
        if fill_strategy:
            for col in df.columns:
                if df[col].isnull().sum() > 0:
                    if fill_strategy == "mean" and df[col].dtype in ('int64', 'float64'):
                        df[col] = df[col].fillna(df[col].mean())
                    elif fill_strategy == "median" and df[col].dtype in ('int64', 'float64'):
                        df[col] = df[col].fillna(df[col].median())
                    elif fill_strategy == "mode":
                        df[col] = df[col].fillna(df[col].mode()[0] if len(df[col].mode()) > 0 else "")
                    elif fill_strategy == "zero":
                        df[col] = df[col].fillna(0 if df[col].dtype in ('int64', 'float64') else "")
                    else:
                        df[col] = df[col].fillna(fill_strategy)
            actions.append(f"填充缺失值 (策略: {fill_strategy})")

        drop_cols = task.get("drop_columns", [])
        if drop_cols:
            df = df.drop(columns=[c for c in drop_cols if c in df.columns])
            actions.append(f"删除 {len(drop_cols)} 列: {drop_cols}")

        self._df = df
        return self.ok(task_id, "清洗完成", {
            "actions": actions,
            "new_shape": list(df.shape),
            "remaining_missing": int(df.isnull().sum().sum()),
        })

    # ── 分析 ──────────────────────────────────────────

    def _analyze(self, task: Dict, task_id: str) -> Dict:
        if self._df is None:
            return self.fail(task_id, "请先加载数据")

        group_by = task.get("group_by", [])
        agg_col = task.get("agg_column", "")
        agg_func = task.get("agg_func", "count")

        result = {}
        if group_by and agg_col:
            group_cols = group_by if isinstance(group_by, list) else [group_by]
            grouped = self._df.groupby(group_cols)[agg_col].agg(agg_func)
            result["grouped"] = grouped.to_dict()

        numeric_cols = self._df.select_dtypes(include=['number']).columns.tolist()
        if len(numeric_cols) >= 2:
            corr = self._df[numeric_cols].corr().to_dict()
            result["correlation"] = corr
            result["top_correlations"] = self._top_correlations(corr)

        top_col = task.get("top_column", "")
        top_n = task.get("top_n", 10)
        if top_col:
            top = self._df[top_col].value_counts().head(top_n).to_dict()
            result["top_values"] = {str(k): int(v) for k, v in top.items()}

        return self.ok(task_id, "分析完成", result)

    # ── 可视化 ────────────────────────────────────────

    def _visualize(self, task: Dict, task_id: str) -> Dict:
        if self._df is None:
            return self.fail(task_id, "请先加载数据")
        if not MATPLOTLIB_AVAILABLE:
            return self.fail(task_id, "matplotlib 未安装。请运行: pip install matplotlib")

        chart_type = task.get("chart_type", "bar")
        x_col = task.get("x_column", self._df.columns[0])
        y_col = task.get("y_column", self._df.columns[1] if len(self._df.columns) > 1 else self._df.columns[0])
        title = task.get("title", f"{chart_type} chart")

        chart_id = f"{chart_type}_{uuid.uuid4().hex[:6]}"
        chart_path = os.path.join(OUTPUT_DIR, f"{chart_id}.png")

        try:
            fig, ax = _plt.subplots(figsize=(10, 6))
            data = self._df.head(50)

            if chart_type == "bar":
                data.plot(kind="bar", x=x_col, y=y_col, ax=ax, legend=False)
            elif chart_type == "line":
                data.plot(kind="line", x=x_col, y=y_col, ax=ax)
            elif chart_type == "pie":
                data[y_col].value_counts().head(10).plot(kind="pie", ax=ax, autopct='%1.1f%%')
            elif chart_type == "scatter":
                data.plot(kind="scatter", x=x_col, y=y_col, ax=ax)
            elif chart_type == "hist":
                data[y_col].hist(ax=ax, bins=task.get("bins", 20))
            elif chart_type == "heatmap":
                numeric = data.select_dtypes(include=['number'])
                if numeric.shape[1] >= 2:
                    im = ax.imshow(numeric.corr(), cmap='coolwarm', aspect='auto')
                    _plt.colorbar(im)
                    ax.set_xticklabels(numeric.columns, rotation=45, ha='right')
                    ax.set_yticklabels(numeric.columns)

            ax.set_title(title)
            fig.tight_layout()
            fig.savefig(str(chart_path), dpi=120, bbox_inches='tight')
            _plt.close(fig)

            return self.ok(task_id, "图表已生成", {
                "chart_path": str(chart_path),
                "chart_type": chart_type,
                "title": title,
            })

        except Exception as e:
            return self.fail(task_id, f"图表生成失败: {e}")

    # ── 导出 ──────────────────────────────────────────

    def _export(self, task: Dict, task_id: str) -> Dict:
        if self._df is None:
            return self.fail(task_id, "请先加载数据")

        fmt = task.get("format", "csv")
        export_id = uuid.uuid4().hex[:8]
        ext_map = {"csv": ".csv", "excel": ".xlsx", "json": ".json"}
        ext = ext_map.get(fmt, ".csv")
        file_path = os.path.join(OUTPUT_DIR, f"export_{export_id}{ext}")

        try:
            if fmt == "csv":
                self._df.to_csv(str(file_path), index=False, encoding='utf-8-sig')
            elif fmt == "excel":
                self._df.to_excel(str(file_path), index=False)
            elif fmt == "json":
                self._df.to_json(str(file_path), orient="records", force_ascii=False, indent=2)

            return self.ok(task_id, f"已导出 {fmt}", {
                "file_path": str(file_path),
                "format": fmt,
                "rows": len(self._df),
                "columns": len(self._df.columns),
            })
        except Exception as e:
            return self.fail(task_id, f"导出失败: {e}")

    # ── 文件加载后 → 完整分析结果 ──────────────────────────

    def _build_analysis_result(self, task_id: str, goal: str,
                                load_result: Dict, explore_result: Dict, *,
                                data_source_type: str = "none",
                                row_count: int = 0) -> Dict:
        """将加载和探索结果合并为完整分析报告"""
        load_data = load_result.get("data", {})
        explore_data = explore_result.get("data", {})

        shape = load_data.get("shape", [])
        columns = load_data.get("columns", [])
        dtypes = load_data.get("dtypes", {})
        missing = load_data.get("missing", 0)
        describe = explore_data.get("describe", {})
        missing_count = explore_data.get("missing_count", {})
        missing_pct = explore_data.get("missing_pct", {})
        nunique = explore_data.get("unique_values", {})
        duplicates = explore_data.get("duplicates", 0)

        key_findings = []
        recommendations = []

        if shape:
            key_findings.append(f"数据规模: {shape[0]} 行 × {shape[1]} 列")

        if missing > 0:
            key_findings.append(f"共有 {missing} 个缺失值")
            high_missing = [col for col, pct in missing_pct.items()
                           if isinstance(pct, str) and float(pct.replace('%', '')) > 50]
            if high_missing:
                recommendations.append(f"以下列缺失率超过50%，建议删除或特殊处理: {', '.join(high_missing)}")
        else:
            key_findings.append("数据完整，无缺失值")

        if duplicates > 0:
            key_findings.append(f"发现 {duplicates} 条重复行")
            recommendations.append("建议去除重复行以保证数据质量")

        type_counts = {}
        for col, dtype in dtypes.items():
            base_type = str(dtype).split()[0] if ' ' in str(dtype) else str(dtype)
            type_counts[base_type] = type_counts.get(base_type, 0) + 1
        if type_counts:
            key_findings.append(f"列类型分布: {type_counts}")

        numeric_cols = [col for col, dtype in dtypes.items()
                       if any(t in str(dtype).lower() for t in ['int', 'float', 'number'])]
        if numeric_cols:
            key_findings.append(f"数值列({len(numeric_cols)}个): {', '.join(numeric_cols[:5])}")
            recommendations.append("可对数值列进行分布分析、相关性分析、异常值检测")

        cat_cols = [col for col, dtype in dtypes.items()
                   if any(t in str(dtype).lower() for t in ['object', 'category', 'string'])]
        if cat_cols:
            key_findings.append(f"分类列({len(cat_cols)}个): {', '.join(cat_cols[:5])}")
            recommendations.append("可对分类列进行频次分析、交叉分析")

        low_unique = [col for col, u in nunique.items() if isinstance(u, int) and u <= 10]
        if low_unique:
            key_findings.append(f"低唯一值列（适合分类分析）: {', '.join(low_unique[:5])}")

        summary = f"数据分析完成 — {shape[0] if shape else '?'} 行 × {shape[1] if shape else '?'} 列"
        next_actions = []
        if missing > 0:
            next_actions.append("进行数据清洗以处理缺失值")
        if duplicates > 0:
            next_actions.append("去除重复行")
        if numeric_cols:
            next_actions.append("对数值列进行分布分析和相关性分析")
        if not next_actions:
            next_actions.append("查看数据可视化报告")

        data_content = {
            "type": "file_analysis",
            "goal": goal,
            "detected_columns": columns,
            "dtypes": dtypes,
            "shape": shape,
            "key_findings": key_findings,
            "recommendations": recommendations,
            "metrics": {
                "行数": shape[0] if shape else 0,
                "列数": shape[1] if shape else 0,
                "缺失值": missing,
                "重复行": duplicates,
                "数值列数": len(numeric_cols),
                "分类列数": len(cat_cols),
            },
            "describe": describe,
            "missing_count": missing_count,
            "missing_pct": missing_pct,
            "preview": load_data.get("preview", []),
            "warnings": [],
        }

        return {
            "ok": True,
            "success": True,
            "agent": self.AGENT_ID or self.name,
            "agent_name": self.DISPLAY_NAME or self.name,
            "status": summary,
            "result": summary,
            "summary": summary,
            "data": data_content,
            "output": data_content,
            "error": None,
            "next_actions": next_actions,
            "meta": {
                "task_id": task_id,
                "duration_ms": 0,
                "model": getattr(self, 'model', ''),
                "tokens_used": 0,
                "fallback": False,
                "data_source_type": data_source_type,
                "sample_rows": row_count or (shape[0] if shape else 0),
            },
        }

    # ── 辅助 ──────────────────────────────────────────

    def _df_info(self) -> Dict:
        return {
            "shape": list(self._df.shape) if self._df is not None else [],
            "columns": list(self._df.columns) if self._df is not None else [],
        }

    def _top_correlations(self, corr: Dict) -> List:
        pairs = []
        seen = set()
        for c1 in corr:
            for c2 in corr[c1]:
                if c1 != c2 and (c2, c1) not in seen:
                    v = corr[c1][c2]
                    if abs(v) > 0.3:
                        pairs.append({"pair": [c1, c2], "coefficient": round(v, 3)})
                        seen.add((c1, c2))
        pairs.sort(key=lambda x: abs(x["coefficient"]), reverse=True)
        return pairs[:10]
