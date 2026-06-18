"""
Data Agent — 数据分析智能体

能力：
1. data_load: 加载 CSV/Excel/JSON 文件，自动检测编码
2. data_explore: 数据探索 (shape/dtypes/missing/describe)
3. data_clean: 数据清洗 (去重/填充缺失/异常值/格式统一)
4. data_analyze: 统计分析 (groupby/aggregate/correlation)
5. data_viz: 可视化图表生成 (bar/line/pie/scatter/heatmap)
6. data_export: 导出 CSV/Excel/JSON + 分析报告

依赖: pandas, matplotlib (自动降级到纯规则模式)
"""
import json
import os
import re
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from agents.base_agent import BaseAgent

OUTPUT_DIR = Path(__file__).parent.parent.parent / "output" / "data_agent"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

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


class DataAgent(BaseAgent):
    """Data Agent — 数据分析与可视化"""

    AGENT_ID = "data"
    DISPLAY_NAME = "数据分析"
    CAPABILITIES = ["data", "pandas", "visualization", "csv", "excel"]
    TASK_TYPES = ["data_load", "data_explore", "data_clean", "data_analyze", "data_viz", "data_export"]

    ALLOWED_EXT = {'.csv', '.xlsx', '.xls', '.json', '.tsv', '.parquet'}

    def __init__(self):
        super().__init__(name="data")
        self._df = None
        self._file_name = ""

    def run(self, task: Dict[str, Any]) -> Dict[str, Any]:
        task_id = task.get("task_id", f"data_{uuid.uuid4().hex[:8]}")
        task_type = task.get("task_type", "data_explore")

        if task_type == "data_load":
            return self._load_data(task, task_id)
        elif task_type == "data_explore":
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

    # ── 加载 ──────────────────────────────────────────

    def _load_data(self, task: Dict, task_id: str) -> Dict:
        file_path = task.get("file_path", task.get("path", ""))
        url = task.get("url", "")
        content = task.get("content", task.get("data", ""))

        if not PANDAS_AVAILABLE:
            return self.fail(task_id, "pandas 未安装。请运行: pip install pandas openpyxl")

        try:
            if file_path and os.path.exists(file_path):
                self._file_name = Path(file_path).name
                ext = Path(file_path).suffix.lower()
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

        # Drop duplicates
        if task.get("drop_duplicates", True):
            before = len(df)
            df = df.drop_duplicates()
            removed = before - len(df)
            if removed > 0:
                actions.append(f"去除 {removed} 条重复行")

        # Fill missing
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

        # Drop columns
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

        # Correlation
        numeric_cols = self._df.select_dtypes(include=['number']).columns.tolist()
        if len(numeric_cols) >= 2:
            corr = self._df[numeric_cols].corr().to_dict()
            result["correlation"] = corr
            result["top_correlations"] = self._top_correlations(corr)

        # Top N
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
        chart_path = OUTPUT_DIR / f"{chart_id}.png"

        try:
            fig, ax = _plt.subplots(figsize=(10, 6))
            data = self._df.head(50)  # 限制数据量

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
        file_path = OUTPUT_DIR / f"export_{export_id}{ext}"

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

    # ── 智能路由 ──────────────────────────────────────

    def _smart_dispatch(self, task: Dict, task_id: str) -> Dict:
        goal = task.get("goal", task.get("prompt", ""))
        file_path = task.get("file_path", task.get("path", ""))
        if file_path and os.path.exists(file_path):
            return self._load_data(task, task_id)
        if any(kw in goal.lower() for kw in ['chart', 'graph', 'plot', 'visual', '图表']):
            return self._visualize(task, task_id)
        return self._explore(task, task_id)

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
