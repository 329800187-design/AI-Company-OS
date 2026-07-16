"""Graph Template Audit Log — 审计日志持久化

每个模板一个 JSONL 文件：output/graph_template_audit/{template_id}.jsonl
追加写入（JSONL append + flush + fsync），单行写入保证原子性。

事件类型：create, update, clone, delete, execute, restore, metadata_update, pin, unpin
"""
from __future__ import annotations

import json
import logging
import os
import re
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

DEFAULT_AUDIT_DIR = Path("output/graph_template_audit")
_TEMPLATE_ID_RE = re.compile(r"^tpl_[A-Za-z0-9_-]+$")
_MAX_PROMPT_DETAIL_LENGTH = 200
_EVENT_TYPES = frozenset({
    "create", "update", "clone", "delete", "execute",
    "restore", "metadata_update", "pin", "unpin",
})


def _get_audit_dir() -> Path:
    DEFAULT_AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    return DEFAULT_AUDIT_DIR


def _audit_path(template_id: str) -> Optional[Path]:
    if not _TEMPLATE_ID_RE.fullmatch(template_id or ""):
        return None
    return _get_audit_dir() / f"{template_id}.jsonl"


def _strip_sensitive(details: Dict[str, Any]) -> Dict[str, Any]:
    """移除敏感字段，截断长文本。返回新 dict。"""
    stripped = {}
    for key, value in details.items():
        if key in ("api_key", "token", "secret", "password", "authorization"):
            continue
        if isinstance(value, str) and len(value) > _MAX_PROMPT_DETAIL_LENGTH:
            stripped[key] = value[:_MAX_PROMPT_DETAIL_LENGTH] + "..."
        elif isinstance(value, dict):
            stripped[key] = _strip_sensitive(value)
        elif isinstance(value, list):
            stripped[key] = [
                _strip_sensitive(item) if isinstance(item, dict) else item
                for item in value[:10]  # 最多保留 10 项
            ]
        else:
            stripped[key] = value
    return stripped


def append_event(
    template_id: str,
    event_type: str,
    summary: str,
    details: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """追加一条审计事件（原子写入）。

    Args:
        template_id: 模板 ID
        event_type: 事件类型
        summary: 一句话摘要
        details: 详情（会自动脱敏）

    Returns:
        写入的事件 dict
    """
    if event_type not in _EVENT_TYPES:
        raise ValueError(f"无效的事件类型: {event_type}，可选: {', '.join(sorted(_EVENT_TYPES))}")

    path = _audit_path(template_id)
    if path is None:
        raise ValueError(f"无效的 template_id: {template_id}")

    event = {
        "event_id": f"aevt_{uuid.uuid4().hex[:12]}",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "template_id": template_id,
        "event_type": event_type,
        "summary": summary,
        "details": _strip_sensitive(details or {}),
    }

    line = json.dumps(event, ensure_ascii=False) + "\n"

    # 原子追加：写入临时文件后 rename 不适用于 append 场景，
    # 直接用 append 模式，单行 JSONL 保证写入原子性（小于 PIPE_BUF）
    try:
        with open(path, "a", encoding="utf-8") as f:
            f.write(line)
            f.flush()
            os.fsync(f.fileno())
    except OSError as e:
        logger.error("Failed to write audit event for %s: %s", template_id, e)
        raise

    return event


def list_events(
    template_id: str,
    event_type: Optional[str] = None,
    limit: int = 100,
) -> List[Dict[str, Any]]:
    """读取模板的审计日志。

    Args:
        template_id: 模板 ID
        event_type: 可选，按事件类型过滤
        limit: 最大返回条数（默认 100，最大 500）

    Returns:
        事件列表（时间升序）
    """
    path = _audit_path(template_id)
    if path is None or not path.exists():
        return []

    limit = min(limit, 500)
    events: List[Dict[str, Any]] = []

    try:
        with open(path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    event = json.loads(line)
                    if event_type and event.get("event_type") != event_type:
                        continue
                    events.append(event)
                except json.JSONDecodeError:
                    logger.warning("Skipping corrupt audit line in %s", path)
                    continue
    except OSError as e:
        logger.error("Failed to read audit log for %s: %s", template_id, e)
        return []

    # 时间升序，取最后 limit 条
    events.sort(key=lambda ev: ev.get("timestamp", ""))
    return events[-limit:]


def delete_audit_for_template(template_id: str) -> None:
    """删除模板的审计日志文件。在删除模板时调用。"""
    path = _audit_path(template_id)
    if path is None or not path.exists():
        return
    try:
        path.unlink()
        logger.info("Deleted audit log for template: %s", template_id)
    except OSError as e:
        logger.error("Failed to delete audit log for %s: %s", template_id, e)
