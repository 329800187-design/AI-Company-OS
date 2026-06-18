"""
PluginAgent 适配器 — 将用户插件模块包装为 BaseAgent 兼容类

用户插件约定：
  - 模块级 NAME: str — 插件名称
  - 模块级 DESCRIPTION: str — 插件描述
  - 模块级 CAPABILITIES: list[str] — 能力标签
  - 模块级 TASK_TYPES: list[str] — 可处理的任务类型
  - 模块级 run(task: dict) -> dict — 执行函数

示例见 example_hello.py
"""
import importlib
import importlib.util
import logging
import os
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

from agents.base_agent import BaseAgent

logger = logging.getLogger("agent.plugin_adapter")

PLUGIN_DIR = Path(__file__).parent


class PluginAgent(BaseAgent):
    """将模块级 run() 函数包装为 BaseAgent 兼容类"""

    def __init__(self, module_name: str, module_path: str):
        self._module_name = module_name
        self._module_path = module_path
        self._module = None

        # 动态导入模块
        try:
            spec = importlib.util.spec_from_file_location(module_name, module_path)
            if spec and spec.loader:
                self._module = importlib.util.module_from_spec(spec)
                sys.modules[module_name] = self._module
                spec.loader.exec_module(self._module)
        except Exception as e:
            logger.error(f"加载插件 {module_name} 失败: {e}")

        # 从模块读取元数据
        name = getattr(self._module, "NAME", module_name) if self._module else module_name
        capabilities = getattr(self._module, "CAPABILITIES", []) if self._module else []
        task_types = getattr(self._module, "TASK_TYPES", []) if self._module else []

        # 设置 BaseAgent 元数据
        self.AGENT_ID = f"plugin:{module_name}"
        self.DISPLAY_NAME = name
        self.CAPABILITIES = capabilities
        self.TASK_TYPES = task_types

        super().__init__(name=f"plugin:{module_name}", timeout=60)

    def run(self, task: Dict[str, Any]) -> Dict[str, Any]:
        task_id = task.get("task_id", f"plugin_{self._module_name}")

        if not self._module or not hasattr(self._module, "run"):
            return self.fail(task_id, f"插件 {self._module_name} 未正确加载或缺少 run() 函数")

        try:
            result = self._module.run(task)
            if isinstance(result, dict):
                # 如果插件返回了标准格式，直接包装
                if "ok" in result or "success" in result:
                    return self.ok(task_id, data=result)
                # 否则包装为统一信封
                return self.ok(task_id, data=result)
            return self.ok(task_id, data={"result": str(result)})
        except Exception as e:
            self.logger.exception(f"插件 {self._module_name} 执行异常")
            return self.fail(task_id, f"插件执行异常: {e}")


def discover_plugins(plugin_dir: str = None) -> List[PluginAgent]:
    """
    扫描插件目录，自动发现并加载所有用户插件。

    返回 PluginAgent 实例列表。
    """
    plugin_dir = Path(plugin_dir) if plugin_dir else PLUGIN_DIR
    plugins = []

    for f in sorted(plugin_dir.iterdir()):
        if not f.suffix == ".py":
            continue
        if f.name.startswith("_") or f.name == "adapter.py":
            continue

        module_name = f.stem
        try:
            agent = PluginAgent(module_name, str(f))
            if agent._module:  # 只加载成功的
                plugins.append(agent)
                logger.info(f"已加载插件: {module_name} ({agent.DISPLAY_NAME})")
        except Exception as e:
            logger.warning(f"跳过插件 {module_name}: {e}")

    return plugins
