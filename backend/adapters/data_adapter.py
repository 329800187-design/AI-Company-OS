"""
Data Adapter — 数据分析适配器
"""
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
        """执行数据分析任务"""
        health = self.health_check()
        if not health.get("available"):
            return self._create_result(
                ok=False,
                error=health.get("error", "数据分析工具不可用"),
                warnings=[health.get("fix_hint", "")]
            )

        file_path = task.get("file_path", "")
        task_type = task.get("task_type", "data_analysis")

        if not file_path:
            return self._create_result(ok=False, error="未提供数据文件路径")

        try:
            from agents.data_agent.agent import DataAgent

            agent = DataAgent()
            result, duration = self._measure_time(
                agent.run,
                {"task_type": task_type, "file_path": file_path, **task}
            )

            # 修复 NaN JSON 问题
            import json
            import math

            def clean_nan(obj):
                """递归清理 NaN/Inf"""
                if isinstance(obj, float):
                    if math.isnan(obj) or math.isinf(obj):
                        return None
                    return obj
                elif isinstance(obj, dict):
                    return {k: clean_nan(v) for k, v in obj.items()}
                elif isinstance(obj, list):
                    return [clean_nan(v) for v in obj]
                return obj

            cleaned_result = clean_nan(result)

            return self._create_result(
                ok=cleaned_result.get("ok", cleaned_result.get("success", False)),
                result=cleaned_result.get("data", {}),
                stdout=str(cleaned_result.get("data", {})),
                duration_ms=duration
            )
        except Exception as e:
            return self._create_result(ok=False, error=str(e))
