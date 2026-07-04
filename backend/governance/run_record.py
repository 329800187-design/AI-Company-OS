"""Run Record — 任务运行记录（JSONL 文件存储）"""
import json
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field

from .execution_plan import ExecutionPlan


OUTPUT_ROOT = Path(__file__).resolve().parent.parent.parent / "output" / "governance" / "runs"


class RunRecord(BaseModel):
    """任务运行记录"""
    run_id: str
    goal: str
    capability_id: str
    status: str = "planned"  # planned | running | succeeded | failed | rejected | needs_clarification
    plan: Optional[Dict] = None
    created_at: str = ""
    updated_at: str = ""
    failure_reason: Optional[str] = None
    artifact_path: Optional[str] = None
    result_ref: Optional[str] = None
    collaboration_result_ref: Optional[str] = None


def _ensure_run_dir(run_id: str) -> Path:
    """确保运行目录存在"""
    run_dir = OUTPUT_ROOT / run_id
    run_dir.mkdir(parents=True, exist_ok=True)
    return run_dir


def create_run_record(goal: str, plan: ExecutionPlan) -> RunRecord:
    """创建运行记录，写入 record.json 和 events.jsonl"""
    run_id = f"run_{uuid.uuid4().hex[:12]}"
    now = datetime.now(timezone.utc).isoformat()

    record = RunRecord(
        run_id=run_id,
        goal=goal,
        capability_id=plan.capability_id,
        status=plan.status,
        plan=plan.model_dump(),
        created_at=now,
        updated_at=now,
    )

    run_dir = _ensure_run_dir(run_id)

    # 写入 record.json
    record_path = run_dir / "record.json"
    record_path.write_text(
        json.dumps(record.model_dump(), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    # 写入初始事件
    events_path = run_dir / "events.jsonl"
    _append_event(events_path, "plan_built", {
        "plan_id": plan.plan_id,
        "capability_id": plan.capability_id,
        "status": plan.status,
    })

    return record


def append_run_event(run_id: str, event_type: str, payload: Dict[str, Any] = None):
    """追加事件到 events.jsonl"""
    run_dir = OUTPUT_ROOT / run_id
    events_path = run_dir / "events.jsonl"
    _append_event(events_path, event_type, payload or {})


def _append_event(events_path: Path, event_type: str, payload: Dict[str, Any]):
    """内部事件追加"""
    now = datetime.now(timezone.utc).isoformat()
    event = {
        "timestamp": now,
        "event_type": event_type,
        "payload": payload,
    }
    with open(events_path, "a", encoding="utf-8") as f:
        f.write(json.dumps(event, ensure_ascii=False) + "\n")


def update_run_status(run_id: str, status: str, **fields):
    """更新运行记录状态"""
    run_dir = OUTPUT_ROOT / run_id
    record_path = run_dir / "record.json"

    if not record_path.exists():
        return

    with open(record_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    data["status"] = status
    data["updated_at"] = datetime.now(timezone.utc).isoformat()
    for key, value in fields.items():
        data[key] = value

    with open(record_path, "w", encoding="utf-8") as f:
        f.write(json.dumps(data, ensure_ascii=False, indent=2))

    # 追加状态变更事件
    events_path = run_dir / "events.jsonl"
    _append_event(events_path, f"status_changed_{status}", fields)


def load_run_record(run_id: str) -> Optional[RunRecord]:
    """加载运行记录"""
    run_dir = OUTPUT_ROOT / run_id
    record_path = run_dir / "record.json"

    if not record_path.exists():
        return None

    with open(record_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    return RunRecord(**data)


def load_run_events(run_id: str) -> List[Dict[str, Any]]:
    """加载事件列表"""
    run_dir = OUTPUT_ROOT / run_id
    events_path = run_dir / "events.jsonl"

    if not events_path.exists():
        return []

    events = []
    with open(events_path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                events.append(json.loads(line))

    return events


def list_run_records(limit: int = 20, offset: int = 0) -> List[RunRecord]:
    """列出最近的运行记录，按 updated_at 倒序"""
    if not OUTPUT_ROOT.exists():
        return []

    records: List[RunRecord] = []
    for run_dir in OUTPUT_ROOT.iterdir():
        if not run_dir.is_dir():
            continue
        record_path = run_dir / "record.json"
        if not record_path.exists():
            continue
        try:
            with open(record_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            records.append(RunRecord(**data))
        except Exception:
            continue

    # 按 updated_at 倒序
    records.sort(key=lambda r: r.updated_at or r.created_at or "", reverse=True)
    return records[offset : offset + limit]
