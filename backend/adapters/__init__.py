"""
Local Tool Adapters — 本地工具适配器

统一接口：
- can_handle(task) - 是否能处理此任务
- health_check() - 健康检查
- run(task) - 执行任务
"""
from .base_adapter import BaseAdapter
from .claude_code_adapter import ClaudeCodeAdapter
from .comfyui_adapter import ComfyUIAdapter
from .ollama_adapter import OllamaAdapter
from .openclaw_adapter import OpenClawAdapter
from .data_adapter import DataAdapter
from .api_model_adapter import ApiModelAdapter
from .mimo_adapter import MiMoAdapter

__all__ = [
    "BaseAdapter",
    "ClaudeCodeAdapter",
    "ComfyUIAdapter",
    "OllamaAdapter",
    "OpenClawAdapter",
    "DataAdapter",
    "ApiModelAdapter",
    "MiMoAdapter"
]
