"""Agent performance timing decorator — auto-records every agent call"""
import functools, time
from typing import Callable

def timed(agent_name: str):
    """Decorator that auto-records agent performance stats"""
    def decorator(fn: Callable) -> Callable:
        @functools.wraps(fn)
        def wrapper(*args, **kwargs):
            start = time.monotonic()
            task_id = ""
            task_type = ""
            try:
                if args:
                    task = args[0] if isinstance(args[0], dict) else getattr(args[0], '__dict__', {})
                    task_id = task.get("task_id", "")
                    task_type = task.get("task_type", "")
            except Exception:
                pass
            try:
                result = fn(*args, **kwargs)
                duration_ms = int((time.monotonic() - start) * 1000)
                success = result.get("success", result.get("ok", True)) if isinstance(result, dict) else True
                try:
                    from core.agent_stats import record
                    tokens = 0
                    if isinstance(result, dict):
                        meta = result.get("meta", {})
                        tokens = meta.get("tokens_used", 0)
                    record(agent_name, task_type, "completed" if success else "failed", duration_ms, success, tokens)
                except Exception:
                    pass
                return result
            except Exception as e:
                duration_ms = int((time.monotonic() - start) * 1000)
                try:
                    from core.agent_stats import record
                    record(agent_name, task_type, "error", duration_ms, False, 0)
                except Exception:
                    pass
                raise
        return wrapper
    return decorator
