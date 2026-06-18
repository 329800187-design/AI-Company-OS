"""
SwarmCommander — 群体指挥官

基于 Agent Swarm 模式，Agent 点对点协同，无中心化编排。

特点:
  - Agent 之间直接通信，不经过中心 Commander
  - 支持 pipeline: Agent A → Agent B → Agent C
  - 支持 fan-out: 同时调用多个 Agent
  - 支持 chain: 自动链式调用
"""
import time
import uuid
from typing import Any, Dict, List, Optional

from backend.database.database import SessionDB, StepDB
from core.agent_swarm import AgentSwarm


class SwarmCommander:
    """群体指挥官 — Agent 点对点协同"""

    def __init__(self, **kwargs):
        self._swarm = AgentSwarm()
        self._init_swarm()

    def _init_swarm(self):
        """初始化 Swarm 节点"""
        try:
            from agents.ceo_agent.agent import CEOAgent
            from agents.codex_agent.agent import CodexAgent
            from agents.qa_agent.agent import QAAgent
            from agents.cto_agent.agent import CTOAgent
            from agents.system_agent.agent import SystemAgent

            agents = [
                ("ceo", CEOAgent(), ["decompose", "plan"]),
                ("codex", CodexAgent(timeout=30), ["code", "execute"]),
                ("qa", QAAgent(), ["review", "verify"]),
                ("cto", CTOAgent(), ["code_review", "architecture"]),
                ("system", SystemAgent(timeout=60), ["file_ops", "system"]),
            ]
            for name, agent, caps in agents:
                self._swarm.register(name, agent.run, caps)
        except Exception as e:
            print(f"[SwarmCommander] 初始化失败: {e}")

    def decompose_goal(self, goal: str, session_id: str) -> list:
        """Swarm 模式：让 CEO 拆解，然后分发到 Swarm"""
        step_id = f"step_{uuid.uuid4().hex[:8]}"
        return [{
            "step_id": step_id,
            "session_id": session_id,
            "agent": "swarm",
            "goal": goal,
            "status": "pending",
            "order": 0,
        }]

    def execute_session(self, session_id: str) -> Dict[str, Any]:
        """执行会话 — 通过 Swarm 协同"""
        steps = StepDB.list_by_session(session_id)
        if not steps:
            return {"status": "error", "message": "无步骤"}

        step = steps[0]
        goal = step.get("goal", "")
        start_time = time.time()

        StepDB.update(step["step_id"], status="running", agent="swarm")

        # Swarm 执行链: CEO 拆解 → 匹配 Agent 执行 → QA 验收
        try:
            # Step 1: CEO 拆解
            ceo_result = self._swarm.execute_task("ceo", {
                "task_id": f"swarm_{uuid.uuid4().hex[:8]}",
                "task_type": "decompose_goal",
                "goal": goal,
            })

            # Step 2: 选择最佳 Agent 执行
            best_agent = self._pick_agent(goal)
            exec_result = self._swarm.execute_task(best_agent, {
                "task_id": f"swarm_{uuid.uuid4().hex[:8]}",
                "task_type": "execute",
                "goal": goal,
                "context": ceo_result,
            })

            # Step 3: QA 验收
            qa_result = self._swarm.execute_task("qa", {
                "task_id": f"swarm_{uuid.uuid4().hex[:8]}",
                "task_type": "quality_check",
                "goal": f"验证执行结果: {exec_result}",
            })

            duration = int((time.time() - start_time) * 1000)

            StepDB.update(step["step_id"],
                          status="completed",
                          result=str(exec_result)[:2000],
                          duration_ms=duration)

            SessionDB.update(session_id, status="completed",
                             summary=str(exec_result)[:500])

            return {
                "status": "completed",
                "session_id": session_id,
                "mode": "swarm",
                "agents_used": ["ceo", best_agent, "qa"],
                "result": exec_result,
                "qa_review": qa_result,
                "duration_ms": duration,
            }

        except Exception as e:
            duration = int((time.time() - start_time) * 1000)
            StepDB.update(step["step_id"], status="failed", duration_ms=duration)
            SessionDB.update(session_id, status="failed", summary=str(e)[:500])
            return {"status": "failed", "error": str(e), "duration_ms": duration}

    def _pick_agent(self, goal: str) -> str:
        """根据目标选择最佳 Agent"""
        goal_lower = goal.lower()
        if any(kw in goal_lower for kw in ["代码", "code", "程序", "python", "脚本"]):
            return "codex"
        if any(kw in goal_lower for kw in ["审查", "review", "架构", "技术"]):
            return "cto"
        if any(kw in goal_lower for kw in ["文件", "系统", "命令", "操作"]):
            return "system"
        return "codex"  # 默认

    def continue_session(self, session_id: str, user_input: str) -> Dict[str, Any]:
        """Swarm 模式不支持暂停"""
        return {"status": "error", "message": "Swarm 模式不支持暂停/继续"}

    def get_session_status(self, session_id: str) -> Dict[str, Any]:
        """获取会话状态"""
        session = SessionDB.get(session_id)
        if not session:
            return {"status": "error", "message": "Session 不存在"}
        steps = StepDB.list_by_session(session_id)
        return {
            "session_id": session_id,
            "status": session.get("status", "unknown"),
            "mode": "swarm",
            "steps": steps,
        }
