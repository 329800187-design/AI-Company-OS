"""
Data Adapter — 数据分析适配器

严格要求：必须有真实数据输入
"""
import os
from typing import Dict, Any
from .base_adapter import BaseAdapter


class DataAdapter(BaseAdapter):
    """数据分析适配器"""

    TOOL_NAME = "data_tools"

    def can_handle(self, task_type: str, task: Dict[str, Any]) -> bool:
        """判断是否能处理此任务"""
        return task_type in {"data", "data_analysis", "data_upload"}

    def health_check(self) -> Dict[str, Any]:
        """健康检查"""
        missing = []
        versions = {}

        # 检查 pandas
        try:
            import pandas
            versions["pandas"] = pandas.__version__
        except ImportError:
            missing.append("pandas")

        # 检查 openpyxl
        try:
            import openpyxl
            versions["openpyxl"] = openpyxl.__version__
        except ImportError:
            missing.append("openpyxl")

        # 检查 matplotlib
        try:
            import matplotlib
            versions["matplotlib"] = matplotlib.__version__
        except ImportError:
            missing.append("matplotlib")

        if missing:
            return {
                "available": False,
                "installed": True,
                "error": f"缺少依赖: {', '.join(missing)}",
                "fix_hint": f"请安装: pip install {' '.join(missing)}",
                "versions": versions
            }

        return {
            "available": True,
            "installed": True,
            "running": True,
            "versions": versions
        }

    def run(self, task: Dict[str, Any]) -> Dict[str, Any]:
        """执行数据分析任务 - 严格要求真实数据"""
        health = self.health_check()
        if not health.get("available"):
            return self._create_result(
                ok=False,
                error=health.get("error", "数据分析工具不可用"),
                warnings=[health.get("fix_hint", "")]
            )

        # 检查是否有真实数据输入
        file_path = task.get("file_path", "")
        file_content = task.get("file_content", "")
        context = task.get("context", {})
        context_file = context.get("file_path", "")
        context_content = context.get("file_content", "")

        # 合并数据源
        actual_file = file_path or context_file
        actual_content = file_content or context_content

        # 严格检查：必须有真实数据
        if not actual_file and not actual_content:
            return self._create_result(
                ok=False,
                error="未提供可分析的数据文件或表格内容",
                warnings=["请上传 CSV/Excel 文件，或提供表格数据"]
            )

        # 如果是文件路径，检查文件是否存在
        if actual_file:
            if not os.path.exists(actual_file):
                return self._create_result(
                    ok=False,
                    error=f"数据文件不存在: {actual_file}",
                    warnings=["请检查文件路径是否正确"]
                )

            # 检查文件大小
            file_size = os.path.getsize(actual_file)
            if file_size == 0:
                return self._create_result(
                    ok=False,
                    error="数据文件为空",
                    warnings=["请提供包含数据的文件"]
                )

        # 尝试解析数据
        try:
            import pandas as pd

            # 读取数据
            if actual_file:
                if actual_file.endswith('.csv'):
                    df = pd.read_csv(actual_file)
                elif actual_file.endswith(('.xlsx', '.xls')):
                    df = pd.read_excel(actual_file)
                elif actual_file.endswith('.json'):
                    df = pd.read_json(actual_file)
                else:
                    return self._create_result(
                        ok=False,
                        error=f"不支持的文件格式: {actual_file}",
                        warnings=["支持的格式: CSV, Excel, JSON"]
                    )
            else:
                # 尝试从内容解析
                import io
                df = pd.read_csv(io.StringIO(actual_content))

            # 检查是否有数据
            if df.empty:
                return self._create_result(
                    ok=False,
                    error="数据文件为空（没有数据行）",
                    warnings=["请提供包含数据的文件"]
                )

            if len(df.columns) == 0:
                return self._create_result(
                    ok=False,
                    error="数据文件没有列",
                    warnings=["请检查文件格式是否正确"]
                )

            # 生成分析结果
            analysis = self._analyze_dataframe(df)

            return self._create_result(
                ok=True,
                result={
                    "output": analysis["summary"],
                    "rows": len(df),
                    "columns": len(df.columns),
                    "column_names": list(df.columns),
                    "statistics": analysis["statistics"]
                },
                stdout=analysis["summary"],
                duration_ms=0
            )

        except Exception as e:
            return self._create_result(
                ok=False,
                error=f"数据分析失败: {str(e)}",
                warnings=["请检查文件格式是否正确"]
            )

    def _analyze_dataframe(self, df) -> Dict[str, Any]:
        """分析 DataFrame"""
        import pandas as pd

        summary_parts = []
        statistics = {}

        # 基本信息
        summary_parts.append(f"数据概览：{len(df)} 行，{len(df.columns)} 列")
        summary_parts.append(f"列名：{', '.join(df.columns.tolist())}")
        summary_parts.append("")

        # 数值列统计
        numeric_cols = df.select_dtypes(include=['number']).columns
        if len(numeric_cols) > 0:
            summary_parts.append("数值列统计：")
            for col in numeric_cols:
                stats = {
                    "mean": float(df[col].mean()) if not pd.isna(df[col].mean()) else 0,
                    "sum": float(df[col].sum()) if not pd.isna(df[col].sum()) else 0,
                    "max": float(df[col].max()) if not pd.isna(df[col].max()) else 0,
                    "min": float(df[col].min()) if not pd.isna(df[col].min()) else 0,
                    "count": int(df[col].count())
                }
                statistics[col] = stats
                summary_parts.append(f"  {col}: 平均={stats['mean']:.2f}, 总计={stats['sum']:.2f}, 最大={stats['max']:.2f}, 最小={stats['min']:.2f}")

        # 缺失值
        missing = df.isnull().sum()
        if missing.sum() > 0:
            summary_parts.append("")
            summary_parts.append("缺失值：")
            for col in df.columns:
                if missing[col] > 0:
                    summary_parts.append(f"  {col}: {missing[col]} 个缺失值")

        return {
            "summary": "\n".join(summary_parts),
            "statistics": statistics
        }
