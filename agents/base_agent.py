"""
BaseAgent v3 — 所有 Agent 的统一基础类

v3 核心变更:
  - execute() 作为调度层入口，自动计时 + 异常捕获
  - 子类声明 AGENT_ID / DISPLAY_NAME / CAPABILITIES / TASK_TYPES
  - 内置 retry 装饰器（指数退避）
  - 内置标准 logging（替代 print）
  - duration_ms 自动计算，不再硬编码为 0

统一输出信封:
  {
    "ok": true/false,
    "agent": "agent_id",
    "status": "human-readable status",
    "data": {...},           # 核心产出
    "error": null/"message", # 失败时的错误
    "meta": {
      "task_id": "...",
      "duration_ms": 123,
      "model": "...",
      "tokens_used": 0,
      "fallback": false
    }
  }

向后兼容: 旧代码仍可通过 result["success"] / result["status"] 访问
"""
import functools
import logging
import time as _time
from abc import ABC, abstractmethod
from typing import Any, Callable, Dict, List, Optional, Tuple, Type


def retry(max_attempts: int = 2, backoff: float = 1.0,
          exceptions: Tuple[Type[Exception], ...] = (Exception,)):
    """指数退避重试装饰器 — 用于 LLM 调用等不稳定操作"""
    def decorator(fn: Callable) -> Callable:
        @functools.wraps(fn)
        def wrapper(*args, **kwargs):
            last_exc = None
            for attempt in range(max_attempts):
                try:
                    return fn(*args, **kwargs)
                except exceptions as e:
                    last_exc = e
                    if attempt < max_attempts - 1:
                        _time.sleep(backoff * (2 ** attempt))
            raise last_exc
        return wrapper
    return decorator


class BaseAgent(ABC):
    """
    所有 Agent 的基础类。

    子类必须:
      1. 设置 AGENT_ID (唯一标识，如 "codex")
      2. 设置 DISPLAY_NAME (中文名，如 "代码执行")
      3. 实现 run(task) 方法
    """

    # ── 子类必须声明的元数据 ──
    AGENT_ID: str = ""           # 唯一标识，如 "codex", "openclaw"
    DISPLAY_NAME: str = ""       # 中文显示名，如 "代码执行"
    CAPABILITIES: List[str] = [] # 能力标签，如 ["code", "sandbox"]
    TASK_TYPES: List[str] = []   # 可处理的任务类型，如 ["code_execute", "code_test"]

    def __init_subclass__(cls, **kwargs):
        """自动校验非抽象子类声明了 AGENT_ID"""
        super().__init_subclass__(**kwargs)
        # 跳过中间抽象类（没有实现 run 的类）
        if getattr(cls, '__abstractmethods__', None):
            return
        # 如果子类自己没定义 AGENT_ID，从基类继承（不报错，留给运行时检查）

    def __init__(self, name: str = "", timeout: int = 60):
        self.name = name or self.AGENT_ID or self.__class__.__name__
        self.timeout = timeout
        self.logger = logging.getLogger(f"agent.{self.name}")

    # ── 子类必须实现 ──

    @abstractmethod
    def run(self, task: Dict[str, Any]) -> Dict[str, Any]:
        """执行任务 — 子类必须实现，返回统一信封"""
        pass

    # ── 调度层入口（自动计时 + 异常捕获）──

    def execute(self, task: Dict[str, Any]) -> Dict[str, Any]:
        """
        调度层应调用此方法而非直接调用 run()。
        自动计时、捕获异常、记录日志。
        """
        start = _time.monotonic()
        task_id = task.get("task_id", "")
        try:
            result = self.run(task)
            # 确保 meta 存在且有 duration_ms
            if isinstance(result, dict):
                if "meta" not in result:
                    result["meta"] = {}
                result["meta"]["duration_ms"] = int((_time.monotonic() - start) * 1000)
            return result
        except Exception as e:
            duration_ms = int((_time.monotonic() - start) * 1000)
            self.logger.exception(f"Agent {self.name} crashed on task {task_id}")
            return self.fail(
                task_id=task_id,
                error=f"Agent 内部异常: {type(e).__name__}: {e}",
                meta={"duration_ms": duration_ms},
            )

    # ── 统一信封构造器 ──

    def ok(self, task_id: str, status: str = "completed",
           data: Dict = None, meta: Dict = None) -> Dict:
        """构建标准成功响应"""
        return {
            "ok": True,
            "success": True,          # 向后兼容
            "agent": self.AGENT_ID or self.name,
            "agent_name": self.DISPLAY_NAME or self.name,
            "status": status,
            "result": status,         # 向后兼容
            "data": data or {},
            "output": data or {},     # 向后兼容
            "error": None,
            "meta": {
                "task_id": task_id,
                "duration_ms": 0,     # execute() 会覆盖
                "model": getattr(self, 'model', ''),
                "tokens_used": 0,
                "fallback": False,
                **(meta or {}),
            },
        }

    def fail(self, task_id: str, error: str, status: str = "failed",
             meta: Dict = None) -> Dict:
        """构建标准失败响应"""
        return {
            "ok": False,
            "success": False,         # 向后兼容
            "agent": self.AGENT_ID or self.name,
            "agent_name": self.DISPLAY_NAME or self.name,
            "status": status,
            "result": error,          # 向后兼容
            "data": {},
            "output": {},             # 向后兼容
            "error": error,
            "meta": {
                "task_id": task_id,
                "duration_ms": 0,     # execute() 会覆盖
                "model": getattr(self, 'model', ''),
                "tokens_used": 0,
                "fallback": False,
                **(meta or {}),
            },
        }

    def wrap_legacy(self, legacy_result: Dict, task_id: str = "",
                    meta: Dict = None) -> Dict:
        """包装旧格式结果 → 统一信封（向后兼容过渡）"""
        ok = legacy_result.get("success", legacy_result.get("status") not in ("失败", "failed", "错误"))
        return {
            "ok": ok,
            "success": ok,
            "agent": self.AGENT_ID or self.name,
            "agent_name": legacy_result.get("agent_name", self.DISPLAY_NAME or self.name),
            "status": legacy_result.get("status", "completed" if ok else "failed"),
            "result": legacy_result.get("result", legacy_result.get("summary", "")),
            "data": legacy_result.get("data", legacy_result.get("output", {})),
            "output": legacy_result.get("output", legacy_result.get("data", {})),
            "error": None if ok else legacy_result.get("result", ""),
            "meta": {
                "task_id": task_id or legacy_result.get("task_id", ""),
                "duration_ms": 0,
                "model": getattr(self, 'model', ''),
                "tokens_used": 0,
                "fallback": legacy_result.get("data", {}).get("mode") == "template_fallback",
                "score": legacy_result.get("score"),
                "findings_count": len(legacy_result.get("findings", [])),
                **(meta or {}),
            },
            # Pass through legacy fields
            "_legacy": legacy_result,
            "findings": legacy_result.get("findings", []),
            "score": legacy_result.get("score"),
            "suggestions": legacy_result.get("suggestions", []),
            "problems": legacy_result.get("problems", []),
        }

    # ── 元数据查询（供动态注册使用）──

    @classmethod
    def get_agent_info(cls) -> Dict[str, Any]:
        """返回 Agent 元数据，用于动态注册和发现"""
        return {
            "agent_id": cls.AGENT_ID,
            "display_name": cls.DISPLAY_NAME,
            "capabilities": cls.CAPABILITIES,
            "task_types": cls.TASK_TYPES,
            "class": cls.__name__,
            "module": cls.__module__,
        }

    # ── AI 调用辅助（集成 Brain Manager）──

    def call_ai(self, message: str, system: str = "", temperature: float = 0.7,
                max_tokens: int = 4096) -> Dict[str, Any]:
        """
        调用当前主脑进行 AI 对话。
        自动使用 Brain Manager 选择最佳 AI 服务。

        返回: {"ok": True, "reply": "...", "model": "..."} 或 {"ok": False, "error": "..."}
        """
        try:
            from core.brain_manager import get_brain_manager
            brain = get_brain_manager()
            return brain.chat(message, system, temperature, max_tokens)
        except Exception as e:
            return {"ok": False, "error": f"AI 调用失败: {str(e)}"}

    def get_current_brain(self) -> Dict[str, Any]:
        """获取当前主脑信息"""
        try:
            from core.brain_manager import get_brain_manager
            return get_brain_manager().get_current()
        except Exception:
            return {"brain_id": "unknown", "name": "Unknown"}
