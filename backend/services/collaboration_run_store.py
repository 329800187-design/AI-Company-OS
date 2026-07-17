"""
Collaboration Run Store — 轻量文件存储，记录每步执行状态 + 计划快照

输出目录: output/collaboration/runs/{plan_id}/
  - steps.json   步骤执行记录（兼容旧逻辑）
  - plan.json    完整计划快照（CollaborationPlan 序列化）
不引入新数据库，纯 JSON 文件。
"""
import json
import logging
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from backend.schemas.collaboration_plan import CollaborationPlan

logger = logging.getLogger(__name__)

OUTPUT_ROOT = Path(__file__).resolve().parent.parent.parent / "output" / "collaboration" / "runs"


def save_step_record(plan_id: str, step_id: str, record: Dict[str, Any]) -> None:
    """
    保存单步执行记录。

    Args:
        plan_id: 协同计划 id
        step_id: 步骤 id
        record: 步骤执行记录字典
    """
    run_dir = OUTPUT_ROOT / plan_id
    run_dir.mkdir(parents=True, exist_ok=True)
    steps_path = run_dir / "steps.json"

    # 加载已有记录
    records = _load_steps_file(steps_path)

    # 更新或追加
    record["step_id"] = step_id
    record["step_id"] = step_id
    record["timestamp"] = datetime.now(timezone.utc).isoformat()
    found = False
    for i, r in enumerate(records):
        if r.get("step_id") == step_id:
            records[i] = record
            found = True
            break
    if not found:
        records.append(record)

    # 写入
    steps_path.write_text(
        json.dumps(records, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    append_run_event(plan_id, _event_type_for_status(record), {
        "step_id": step_id,
        "assigned_agent_id": record.get("assigned_agent_id"),
        "status": record.get("status"),
        "required_capability": record.get("required_capability"),
        "task_type": record.get("task_type"),
        "error": record.get("error"),
        "review_decision": record.get("review_decision"),
        "artifacts": _extract_record_artifacts(record),
    })
    logger.debug(f"RunStore: saved step record {step_id} for plan {plan_id}")


def load_plan_records(plan_id: str) -> List[Dict[str, Any]]:
    """
    加载计划的所有步骤执行记录。

    Args:
        plan_id: 协同计划 id

    Returns:
        步骤记录列表
    """
    run_dir = OUTPUT_ROOT / plan_id
    steps_path = run_dir / "steps.json"
    if not steps_path.exists():
        return []
    return _load_steps_file(steps_path)


def append_run_event(plan_id: str, event_type: str, payload: Dict[str, Any]) -> Dict[str, Any]:
    """Append an immutable audit event for collaboration run detail views."""
    run_dir = OUTPUT_ROOT / plan_id
    run_dir.mkdir(parents=True, exist_ok=True)
    events_path = run_dir / "events.json"
    events = _load_json_list(events_path)
    event = {
        "event_id": f"cevt_{uuid.uuid4().hex[:10]}",
        "event_type": event_type,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "actor": payload.pop("actor", "system") if isinstance(payload, dict) else "system",
        "summary": _event_summary(event_type, payload),
        "payload": payload,
    }
    events.append(event)
    events_path.write_text(json.dumps(events, ensure_ascii=False, indent=2), encoding="utf-8")
    return event


def load_run_timeline(plan_id: str) -> List[Dict[str, Any]]:
    """Load audit events; derive a timeline from steps.json for older runs."""
    events_path = OUTPUT_ROOT / plan_id / "events.json"
    events = _load_json_list(events_path)
    if events:
        return events

    timeline: List[Dict[str, Any]] = []
    for record in load_plan_records(plan_id):
        event_type = _event_type_for_status(record)
        payload = {
            "step_id": record.get("step_id"),
            "assigned_agent_id": record.get("assigned_agent_id"),
            "status": record.get("status"),
            "required_capability": record.get("required_capability"),
            "task_type": record.get("task_type"),
            "error": record.get("error"),
            "artifacts": _extract_record_artifacts(record),
        }
        timeline.append({
            "event_id": f"derived_{record.get('step_id', len(timeline))}",
            "event_type": event_type,
            "timestamp": record.get("timestamp"),
            "actor": "system",
            "summary": _event_summary(event_type, payload),
            "payload": payload,
        })
    return timeline


def collect_plan_artifacts(plan: CollaborationPlan) -> List[Dict[str, Any]]:
    """Collect all step artifacts into a flat list for report-center display."""
    artifacts: List[Dict[str, Any]] = []
    for step in plan.steps:
        if not step.result or not step.result.artifacts:
            continue
        for index, artifact_path in enumerate(step.result.artifacts):
            artifacts.append({
                "artifact_id": f"{step.id}_artifact_{index + 1}",
                "step_id": step.id,
                "step_name": step.name,
                "agent_id": step.assigned_agent_id or step.result.agent_id,
                "path": artifact_path,
                "kind": _guess_artifact_kind(artifact_path),
            })
    return artifacts


def _load_json_list(path: Path) -> List[Dict[str, Any]]:
    if not path.exists():
        return []
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return data if isinstance(data, list) else []
    except Exception as e:
        logger.warning(f"RunStore: failed to load {path}: {e}")
        return []


def _event_type_for_status(record: Dict[str, Any]) -> str:
    status = record.get("status")
    if status == "waiting_human":
        return "step_waiting_human"
    if status == "succeeded":
        return "step_succeeded"
    if status == "failed":
        return "step_failed"
    if status == "skipped":
        return "step_skipped"
    if status == "retry_reset":
        return "step_retry_reset"
    if status == "running":
        return "step_running"
    return "step_recorded"


def _event_summary(event_type: str, payload: Dict[str, Any]) -> str:
    step_id = payload.get("step_id") or "step"
    if event_type == "step_waiting_human":
        return f"{step_id} is waiting for human review"
    if event_type == "step_succeeded":
        return f"{step_id} succeeded"
    if event_type == "step_failed":
        return f"{step_id} failed"
    if event_type == "step_skipped":
        return f"{step_id} skipped because dependencies were not met"
    if event_type == "step_retry_reset":
        return f"{step_id} was reset for retry"
    if event_type == "step_running":
        return f"{step_id} started running"
    if event_type == "risk_gate_evaluated":
        return f"{step_id} risk gate evaluated (level={payload.get('risk_level', '?')})"
    if event_type == "risk_gate_blocked":
        return f"{step_id} blocked by risk gate"
    if event_type == "risk_gate_waiting_confirmation":
        return f"{step_id} waiting for risk confirmation"
    if event_type == "sandbox_required":
        return f"{step_id} approved for sandbox execution (risk gate)"
    if event_type == "sandbox_requested":
        return f"{step_id} sandbox execution requested"
    if event_type == "sandbox_not_implemented":
        return f"{step_id} sandbox not implemented — execution failed"
    return f"{step_id} recorded as {payload.get('status', 'unknown')}"


def _extract_record_artifacts(record: Dict[str, Any]) -> List[str]:
    result = record.get("result")
    if isinstance(result, dict) and isinstance(result.get("artifacts"), list):
        return result["artifacts"]
    if isinstance(record.get("artifacts"), list):
        return record["artifacts"]
    return []


def _guess_artifact_kind(path: str) -> str:
    suffix = Path(path).suffix.lower()
    if suffix in (".md", ".markdown"):
        return "markdown"
    if suffix == ".json":
        return "json"
    if suffix in (".png", ".jpg", ".jpeg", ".webp", ".gif"):
        return "image"
    if suffix in (".mp4", ".mov", ".avi"):
        return "video"
    return "file"


def _load_steps_file(steps_path: Path) -> List[Dict[str, Any]]:
    """读取 steps.json 文件"""
    if not steps_path.exists():
        return []
    try:
        with open(steps_path, "r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, Exception) as e:
        logger.warning(f"RunStore: failed to load {steps_path}: {e}")
        return []


# ── Plan Snapshot（计划快照持久化）──────────────────────────

def save_plan_snapshot(plan: CollaborationPlan) -> None:
    """将完整 CollaborationPlan 序列化到 plan.json"""
    run_dir = OUTPUT_ROOT / plan.plan_id
    run_dir.mkdir(parents=True, exist_ok=True)
    plan_path = run_dir / "plan.json"
    plan_path.write_text(
        json.dumps(plan.model_dump(), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    logger.debug(f"RunStore: saved plan snapshot {plan.plan_id}")


def load_plan_snapshot(plan_id: str) -> Optional[CollaborationPlan]:
    """从 plan.json 加载计划快照，不存在返回 None"""
    plan_path = OUTPUT_ROOT / plan_id / "plan.json"
    if not plan_path.exists():
        return None
    try:
        with open(plan_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return CollaborationPlan.model_validate(data)
    except Exception as e:
        logger.warning(f"RunStore: failed to load plan snapshot {plan_id}: {e}")
        return None


def reset_step_for_retry(
    plan_id: str,
    step_id: str,
) -> Optional[CollaborationPlan]:
    """
    重置指定步骤及其下游步骤，为重试做准备。

    将 failed/skipped 步骤重置为 assigned/pending，
    并递归重置依赖它的下游 failed/skipped 步骤。

    Args:
        plan_id: 计划 id
        step_id: 要重试的步骤 id

    Returns:
        更新后的 CollaborationPlan，不存在或状态不允许时返回 None
    """
    plan = load_plan_snapshot(plan_id)
    if plan is None:
        return None

    # 找到目标步骤
    target = None
    for s in plan.steps:
        if s.id == step_id:
            target = s
            break
    if target is None:
        return None

    # 只允许重试 failed 或 skipped 状态
    if target.status not in ("failed", "skipped"):
        return None

    # 重置单个步骤的函数
    def _reset_step(step):
        if step.assigned_agent_id:
            step.status = "assigned"
        else:
            step.status = "pending"
        step.result = None

    # 递归重置下游步骤
    def _reset_downstream(downstream_step_id):
        for s in plan.steps:
            if downstream_step_id in s.depends_on and s.status in ("failed", "skipped"):
                _reset_step(s)
                save_step_record(plan_id, s.id, {
                    "assigned_agent_id": s.assigned_agent_id,
                    "status": "retry_reset",
                    "required_capability": s.required_capability,
                    "task_type": s.task_type,
                })
                _reset_downstream(s.id)

    # 重置目标步骤
    _reset_step(target)
    save_step_record(plan_id, step_id, {
        "assigned_agent_id": target.assigned_agent_id,
        "status": "retry_reset",
        "required_capability": target.required_capability,
        "task_type": target.task_type,
    })

    # 重置下游
    _reset_downstream(step_id)

    # 更新 plan 状态
    plan.status = "running"
    save_plan_snapshot(plan)

    logger.info(f"RunStore: reset step '{step_id}' for retry in plan '{plan_id}'")
    return plan


def update_step_status(
    plan_id: str,
    step_id: str,
    status: str,
    review_decision: Optional[Dict[str, Any]] = None,
) -> Optional[CollaborationPlan]:
    """
    更新指定步骤状态并保存快照。

    Args:
        plan_id: 计划 id
        step_id: 步骤 id
        status: 新状态
        review_decision: 审批决策信息（approve/reject 时传入）

    Returns:
        更新后的 CollaborationPlan，找不到返回 None
    """
    plan = load_plan_snapshot(plan_id)
    if plan is None:
        return None

    step = None
    for s in plan.steps:
        if s.id == step_id:
            step = s
            break
    if step is None:
        logger.warning(f"RunStore: step '{step_id}' not found in plan '{plan_id}'")
        return None

    step.status = status

    # 将审批决策写入 step.result.output（不覆盖已有的 _risk_decision）
    if review_decision is not None:
        if step.result is None:
            # 创建一个空的 AgentRunResult 来承载 metadata
            from backend.schemas.agent_protocol import AgentRunResult
            step.result = AgentRunResult(ok=True, agent_id=step.assigned_agent_id or "")
        if not isinstance(step.result.output, dict):
            step.result.output = {}
        step.result.output["_review_decision"] = review_decision

    # 更新 plan 状态
    if status == "failed":
        plan.status = "failed"
    elif status == "succeeded":
        # 检查是否所有步骤都完成了
        all_done = all(
            s.status in ("succeeded", "skipped", "failed")
            for s in plan.steps
        )
        if all_done:
            plan.status = "succeeded"
        else:
            plan.status = "running"

    save_plan_snapshot(plan)

    # 同步写 step record（兼容旧的 steps.json 读取）
    record = {
        "assigned_agent_id": step.assigned_agent_id,
        "status": status,
        "required_capability": step.required_capability,
        "task_type": step.task_type,
    }
    if review_decision:
        record["review_decision"] = review_decision
    save_step_record(plan_id, step_id, record)

    return plan
