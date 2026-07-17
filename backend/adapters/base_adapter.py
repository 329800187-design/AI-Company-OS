"""
Base Adapter — 适配器基类
"""
import time
from abc import ABC, abstractmethod
from typing import Dict, Any, List
from backend.logger import get_logger

logger = get_logger()


class BaseAdapter(ABC):
    """适配器基类"""

    TOOL_NAME: str = "base"

    @abstractmethod
    def can_handle(self, task_type: str, task: Dict[str, Any]) -> bool:
        """判断是否能处理此任务"""
        pass

    @abstractmethod
    def health_check(self) -> Dict[str, Any]:
        """健康检查"""
        pass

    @abstractmethod
    def run(self, task: Dict[str, Any]) -> Dict[str, Any]:
        """执行任务"""
        pass

    def _create_result(self, **kwargs) -> Dict[str, Any]:
        """创建统一的返回结构"""
        return {
            "ok": kwargs.get("ok", True),
            "tool": kwargs.get("tool", self.TOOL_NAME),
            "mode": kwargs.get("mode", "local"),
            "result": kwargs.get("result", {}),
            "stdout": kwargs.get("stdout", ""),
            "stderr": kwargs.get("stderr", ""),
            "error": kwargs.get("error", ""),
            "duration_ms": kwargs.get("duration_ms", 0),
            "artifacts": kwargs.get("artifacts", []),
            "warnings": kwargs.get("warnings", [])
        }

    def _measure_time(self, func, *args, **kwargs) -> tuple:
        """测量执行时间"""
        start = time.time()
        result = func(*args, **kwargs)
        duration = int((time.time() - start) * 1000)
        return result, duration
