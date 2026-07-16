"""
Local Module Adapter — 本地 Agent 模块适配器

用于调用 agents/*_agent/agent.py 中的 Agent
"""
import importlib
import inspect
from typing import Dict, Any, Optional
from .base_adapter import BaseAdapter


class LocalModuleAdapter(BaseAdapter):
    """本地 Agent 模块适配器"""

    TOOL_NAME = "local_module"

    def __init__(self, agent_id: str, module_path: str, class_name: str = None):
        self.agent_id = agent_id
        self.module_path = module_path
        self.class_name = class_name or self._guess_class_name(agent_id)
        self._agent_instance = None
        self._module = None

    def _guess_class_name(self, agent_id: str) -> str:
        """根据 agent_id 推测类名"""
        # data_agent -> DataAgent
        # marketing_agent -> MarketingAgent
        parts = agent_id.split("_")
        return "".join(p.title() for p in parts) + "Agent"

    def can_handle(self, task_type: str, task: Dict[str, Any]) -> bool:
        """判断是否能处理此任务"""
        # 根据 agent_id 推测能力
        agent_task_types = {
            "data_agent": ["data"],
            "marketing_agent": ["marketing"],
            "qa_agent": ["qa", "verification"],
            "codex_agent": ["code"],
            "image_agent": ["image"],
            "video_agent": ["video"],
            "ceo_agent": ["planning"],
            "cto_agent": ["code", "architecture"],
            "system_agent": ["system"],
        }
        return task_type in agent_task_types.get(self.agent_id, [])

    def health_check(self) -> Dict[str, Any]:
        """健康检查"""
        try:
            self._load_module()
            if self._agent_instance:
                return {
                    "available": True,
                    "installed": True,
                    "running": True,
                    "module": self.module_path,
                    "class": self.class_name
                }
            else:
                return {
                    "available": False,
                    "installed": True,
                    "error": f"无法实例化 {self.class_name}",
                    "fix_hint": f"请检查 {self.module_path} 中的 {self.class_name} 类"
                }
        except ImportError as e:
            return {
                "available": False,
                "installed": False,
                "error": f"无法导入模块: {str(e)[:100]}",
                "fix_hint": f"请检查 {self.module_path} 是否存在"
            }
        except Exception as e:
            return {
                "available": False,
                "error": f"加载失败: {str(e)[:100]}",
                "fix_hint": f"请检查 {self.module_path} 的实现"
            }

    def _load_module(self):
        """加载模块"""
        if self._module and self._agent_instance:
            return

        try:
            self._module = importlib.import_module(self.module_path)

            # 查找 Agent 类
            agent_class = getattr(self._module, self.class_name, None)
            if not agent_class:
                # 尝试查找 Agent 后缀的类
                for name, obj in inspect.getmembers(self._module, inspect.isclass):
                    if name.endswith("Agent") and name != "BaseAgent":
                        agent_class = obj
                        break

            if agent_class:
                # 尝试实例化
                try:
                    self._agent_instance = agent_class()
                except Exception:
                    # 如果需要参数，尝试无参实例化
                    try:
                        self._agent_instance = agent_class(name=self.agent_id)
                    except Exception:
                        self._agent_instance = None
        except ImportError:
            raise

    def run(self, task: Dict[str, Any]) -> Dict[str, Any]:
        """执行任务"""
        health = self.health_check()
        if not health.get("available"):
            return self._create_result(
                ok=False,
                error=health.get("error", f"{self.agent_id} 不可用"),
                warnings=[health.get("fix_hint", "")]
            )

        try:
            # 尝试调用 run 方法
            if hasattr(self._agent_instance, 'run'):
                result = self._agent_instance.run(task)
            elif hasattr(self._agent_instance, 'execute'):
                result = self._agent_instance.execute(task)
            elif hasattr(self._agent_instance, 'process'):
                result = self._agent_instance.process(task)
            else:
                return self._create_result(
                    ok=False,
                    error=f"{self.class_name} 没有 run/execute/process 方法"
                )

            # 标准化返回
            if isinstance(result, dict):
                ok = result.get("ok", result.get("success", True))
                data = result.get("data", result)
                stdout = str(result.get("data", result.get("result", "")))
                error = result.get("error", "")
                # 提取 fix_hints 和 suggestions 传递给上层
                fix_hints = result.get("fix_hints", [])
                suggestions = result.get("suggestions", [])
                warnings = result.get("warnings", [])
                if not fix_hints and suggestions:
                    fix_hints = suggestions

                # 直接构造返回 dict（_create_result 不支持自定义字段）
                return {
                    "ok": ok,
                    "tool": self.TOOL_NAME,
                    "mode": "local",
                    "result": data,
                    "stdout": stdout,
                    "stderr": "",
                    "error": error,
                    "duration_ms": 0,
                    "artifacts": [],
                    "warnings": warnings,
                    "fix_hints": fix_hints,
                }

            else:
                return self._create_result(
                    ok=True,
                    result={"output": str(result)},
                    stdout=str(result)
                )

        except Exception as e:
            return self._create_result(ok=False, error=str(e))


def create_local_adapter(agent_id: str) -> Optional[LocalModuleAdapter]:
    """创建本地 Agent 适配器"""
    module_path = f"agents.{agent_id}.agent"
    adapter = LocalModuleAdapter(agent_id, module_path)

    # 检查是否可用
    health = adapter.health_check()
    if health.get("available"):
        return adapter

    return None
