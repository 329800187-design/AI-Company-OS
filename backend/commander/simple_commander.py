"""
SimpleCommander — 简易指挥官

不拆解目标，直接调用最佳 Agent 完成任务。
适合简单任务，响应速度快。

特点:
  - 无拆解步骤，直接路由到最佳 Agent
  - 单 Agent 执行，无协作
  - 响应快，token 消耗少
"""
import time
import uuid
from typing import Any, Dict, Optional

from backend.ai_registry.registry import get_registry
from backend.database.database import SessionDB, StepDB


class SimpleCommander:
    """简易指挥官 — 直接执行，不拆解"""

    def __init__(self, **kwargs):
        self._registry = get_registry()

    def decompose_goal(self, goal: str, session_id: str) -> list:
        """简易模式：不拆解，直接返回单步骤"""
        step_id = f"step_{uuid.uuid4().hex[:8]}"
        return [{
            "step_id": step_id,
            "session_id": session_id,
            "agent": "auto",
            "goal": goal,
            "status": "pending",
            "order": 0,
        }]

    def execute_session(self, session_id: str) -> Dict[str, Any]:
        """执行会话"""
        steps = StepDB.list_by_session(session_id)
        if not steps:
            return {"status": "error", "message": "无步骤"}

        step = steps[0]
        goal = step.get("goal", "")
        start_time = time.time()

        # 路由到最佳 Agent
        route = self._registry.route_by_goal(goal)
        service_id = route.get("service", "cc-switch")
        task_type = route.get("task_type", "chat")

        StepDB.update(step["step_id"], status="running", agent=service_id)

        # 执行
        result = self._registry.execute(service_id, {
            "prompt": goal,
            "goal": goal,
            "task_type": task_type,
        })

        duration = int((time.time() - start_time) * 1000)
        success = result.get("success", False)

        StepDB.update(step["step_id"],
                      status="completed" if success else "failed",
                      result=str(result.get("result", ""))[:2000],
                      duration_ms=duration)

        SessionDB.update(session_id,
                         status="completed" if success else "failed",
                         summary=str(result.get("result", ""))[:500])

        return {
            "status": "completed" if success else "failed",
            "session_id": session_id,
            "agent": service_id,
            "result": result.get("result", ""),
            "duration_ms": duration,
            "reason": route.get("reason", ""),
        }

    def continue_session(self, session_id: str, user_input: str) -> Dict[str, Any]:
        """继续会话（简易模式不支持暂停）"""
        return {"status": "error", "message": "简易模式不支持暂停/继续"}

    def get_session_status(self, session_id: str) -> Dict[str, Any]:
        """获取会话状态"""
        session = SessionDB.get(session_id)
        if not session:
            return {"status": "error", "message": "Session 不存在"}
        steps = StepDB.list_by_session(session_id)
        return {
            "session_id": session_id,
            "status": session.get("status", "unknown"),
            "steps": steps,
        }
