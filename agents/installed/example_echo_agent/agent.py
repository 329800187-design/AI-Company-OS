"""
Example Echo Agent — 最小可运行第三方 Agent 示例

能力：
1. echo: 回声，原样返回 goal
2. copywriting: 简易文案生成（无需 AI API）

照此模板编写你自己的 Agent：
  1. 继承 BaseAgent
  2. 声明 AGENT_ID / DISPLAY_NAME / CAPABILITIES / TASK_TYPES
  3. 实现 run(task) → 统一信封 dict
  4. 在同目录放 agent.json manifest
"""
import uuid
from typing import Any, Dict, List

from agents.base_agent import BaseAgent


class ExampleEchoAgent(BaseAgent):
    """Example Echo Agent — 回声 + 简易文案示例"""

    AGENT_ID = "example_echo"
    DISPLAY_NAME = "Echo 示例"
    CAPABILITIES: List[str] = ["echo", "copywriting"]
    TASK_TYPES: List[str] = ["echo", "copywriting"]

    def health(self) -> Dict[str, Any]:
        """健康检查"""
        return {"ok": True, "agent": self.AGENT_ID, "status": "healthy"}

    def run(self, task: Dict[str, Any]) -> Dict[str, Any]:
        """
        执行任务。

        Args:
            task: {
                "task_id": "可选",
                "goal": "任务目标",
                "task_type": "echo | copywriting",
                ...
            }

        Returns:
            统一信封 dict
        """
        task_id = task.get("task_id", f"echo_{uuid.uuid4().hex[:8]}")
        task_type = task.get("task_type", "echo")
        goal = task.get("goal", "")

        if not goal:
            return self.fail(task_id, "缺少 goal 参数")

        if task_type == "echo":
            return self._handle_echo(task_id, goal)
        elif task_type == "copywriting":
            return self._handle_copywriting(task_id, goal)
        else:
            return self.fail(task_id, f"不支持的 task_type: {task_type}")

    def _handle_echo(self, task_id: str, goal: str) -> Dict[str, Any]:
        """回声模式 — 原样返回 goal"""
        return self.ok(
            task_id=task_id,
            status="completed",
            data={
                "echo": goal,
                "message": f"Echo: {goal}",
            },
            meta={"agent": self.AGENT_ID, "mode": "echo"},
        )

    def _handle_copywriting(self, task_id: str, goal: str) -> Dict[str, Any]:
        """简易文案 — 规则生成，无需 AI"""
        return self.ok(
            task_id=task_id,
            status="completed",
            data={
                "headline": f"爆款标题：{goal}",
                "body": f"你是否也在为{goal}烦恼？试试这个方法...",
                "cta": "立即了解 →",
                "mode": "template_fallback",
            },
            meta={"agent": self.AGENT_ID, "mode": "copywriting_template"},
        )
