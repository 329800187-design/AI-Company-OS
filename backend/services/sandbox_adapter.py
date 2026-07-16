"""
Sandbox Adapter — 沙箱执行接口 (v0)

提供沙箱执行抽象层，v0 仅定义接口，不做真实隔离。
high-risk agent 涉及代码执行/浏览器/CLI/HTTP 时，必须通过沙箱执行。

v0 行为:
  - run_in_sandbox() 返回 ok=false
  - error = "Sandbox execution is not implemented yet"
  - audit_events 记录 sandbox_requested / sandbox_not_implemented
"""
import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


@dataclass
class SandboxRequest:
    """沙箱执行请求"""
    request_id: str = ""
    agent_id: str = ""
    task_id: str = ""
    risk_level: str = "low"
    context_summary: str = ""
    workspace_dir: str = ""
    allowed_operations: List[str] = field(default_factory=list)
    started_at: Optional[str] = None
    finished_at: Optional[str] = None


@dataclass
class SandboxResult:
    """沙箱执行结果"""
    ok: bool = False
    output: Dict[str, Any] = field(default_factory=dict)
    error: Optional[str] = None
    audit_events: List[Dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "ok": self.ok,
            "output": self.output,
            "error": self.error,
            "audit_events": self.audit_events,
        }


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def run_in_sandbox(
    agent_id: str,
    task: Any,
    risk_decision: Any = None,
) -> SandboxResult:
    """
    在沙箱中执行 agent 任务。v0 未实现真实沙箱。

    Args:
        agent_id: agent 标识
        task: AgentTask 或 dict
        risk_decision: RiskDecision 或 dict（来自 risk gate）

    Returns:
        SandboxResult
    """
    from backend.schemas.agent_protocol import AgentTask

    # 提取 task_id
    task_id = ""
    if isinstance(task, AgentTask):
        task_id = task.task_id
    elif isinstance(task, dict):
        task_id = task.get("task_id", "")

    # 提取 risk_level
    risk_level = "low"
    if risk_decision is not None:
        if hasattr(risk_decision, "risk_level"):
            risk_level = risk_decision.risk_level
        elif isinstance(risk_decision, dict):
            risk_level = risk_decision.get("risk_level", "low")

    request_id = f"sbox_{agent_id}_{task_id}"

    request = SandboxRequest(
        request_id=request_id,
        agent_id=agent_id,
        task_id=task_id,
        risk_level=risk_level,
        started_at=_now_iso(),
    )

    logger.info(f"SandboxAdapter: sandbox_requested agent='{agent_id}' task='{task_id}' risk='{risk_level}'")

    audit_events = [
        {
            "event": "sandbox_requested",
            "timestamp": _now_iso(),
            "agent_id": agent_id,
            "task_id": task_id,
            "risk_level": risk_level,
        },
        {
            "event": "sandbox_not_implemented",
            "timestamp": _now_iso(),
            "agent_id": agent_id,
            "task_id": task_id,
            "message": "Sandbox execution is not implemented yet",
        },
    ]

    request.finished_at = _now_iso()

    return SandboxResult(
        ok=False,
        output={"request_id": request_id},
        error="Sandbox execution is not implemented yet",
        audit_events=audit_events,
    )
