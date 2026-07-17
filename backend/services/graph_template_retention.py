"""Graph Template Audit Retention Policy — 审计日志保留/清理

功能：
  1. scan_audit_files()：扫描 output/graph_template_audit/*.jsonl
  2. summarize_audit_storage()：返回文件数、总大小、最早/最新事件时间
  3. cleanup_audit_logs(retention_days, dry_run=True)：清理已删除模板的过期审计日志

安全设计：
  - 默认 dry_run=True，只返回将删除的文件，不实际删除
  - 只清理"已删除模板"的 audit 文件，仍存在的模板 audit 不删
  - retention_days <= 0 返回 ValueError
  - 路径防穿越，只允许 output/graph_template_audit 下的 tpl_*.jsonl
  - 文件读取失败进入 errors，不崩整个任务
"""
from __future__ import annotations

import json
import logging
import os
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

DEFAULT_AUDIT_DIR = Path("output/graph_template_audit")
_TEMPLATE_ID_RE = re.compile(r"^tpl_[A-Za-z0-9_-]+$")
_JSONL_PATTERN = "tpl_*.jsonl"


def _get_audit_dir() -> Path:
    """获取审计目录，不存在则创建"""
    DEFAULT_AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    return DEFAULT_AUDIT_DIR


def scan_audit_files(audit_dir: Optional[Path] = None) -> List[Path]:
    """扫描审计目录下的所有 tpl_*.jsonl 文件。

    Args:
        audit_dir: 审计目录路径，默认 output/graph_template_audit

    Returns:
        文件路径列表（已排序）
    """
    if audit_dir is None:
        audit_dir = _get_audit_dir()
    else:
        audit_dir.mkdir(parents=True, exist_ok=True)

    files = []
    for f in audit_dir.glob(_JSONL_PATTERN):
        # 防穿越：确保文件确实在审计目录下
        try:
            f.resolve().relative_to(audit_dir.resolve())
            # 验证文件名符合 tpl_*.jsonl 模式
            if _TEMPLATE_ID_RE.fullmatch(f.stem):
                files.append(f)
        except ValueError:
            logger.warning("Skipping file outside audit dir: %s", f)
            continue

    return sorted(files)


def _extract_template_id(file_path: Path) -> Optional[str]:
    """从文件名提取 template_id"""
    stem = file_path.stem
    if _TEMPLATE_ID_RE.fullmatch(stem):
        return stem
    return None


def _get_file_time_range(file_path: Path) -> Dict[str, Any]:
    """读取 JSONL 文件，提取最早和最新事件时间。

    Returns:
        {"earliest": str|None, "latest": str|None, "event_count": int, "error": str|None}
    """
    earliest = None
    latest = None
    event_count = 0
    error = None

    try:
        with open(file_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    event = json.loads(line)
                    ts = event.get("timestamp", "")
                    if ts:
                        event_count += 1
                        if earliest is None or ts < earliest:
                            earliest = ts
                        if latest is None or ts > latest:
                            latest = ts
                except json.JSONDecodeError:
                    # 损坏行跳过，不崩
                    continue
    except OSError as e:
        error = str(e)
        logger.warning("Failed to read audit file %s: %s", file_path, e)

    return {
        "earliest": earliest,
        "latest": latest,
        "event_count": event_count,
        "error": error,
    }


def summarize_audit_storage(audit_dir: Optional[Path] = None) -> Dict[str, Any]:
    """汇总审计存储信息。

    Returns:
        {
            "file_count": int,
            "total_bytes": int,
            "total_size_human": str,
            "earliest_event": str|None,
            "latest_event": str|None,
            "files": [{"template_id": str, "size_bytes": int, "event_count": int, ...}]
        }
    """
    files = scan_audit_files(audit_dir)
    total_bytes = 0
    earliest_event = None
    latest_event = None
    file_details = []

    for f in files:
        template_id = _extract_template_id(f)
        if template_id is None:
            continue

        try:
            size = f.stat().st_size
        except OSError:
            size = 0

        total_bytes += size
        time_range = _get_file_time_range(f)

        if time_range["earliest"] and (earliest_event is None or time_range["earliest"] < earliest_event):
            earliest_event = time_range["earliest"]
        if time_range["latest"] and (latest_event is None or time_range["latest"] > latest_event):
            latest_event = time_range["latest"]

        file_details.append({
            "template_id": template_id,
            "size_bytes": size,
            "event_count": time_range["event_count"],
            "earliest": time_range["earliest"],
            "latest": time_range["latest"],
            "error": time_range["error"],
        })

    return {
        "file_count": len(files),
        "total_bytes": total_bytes,
        "total_size_human": _human_readable_size(total_bytes),
        "earliest_event": earliest_event,
        "latest_event": latest_event,
        "files": file_details,
    }


def _human_readable_size(size_bytes: int) -> str:
    """将字节数转换为人类可读格式"""
    if size_bytes < 1024:
        return f"{size_bytes} B"
    elif size_bytes < 1024 * 1024:
        return f"{size_bytes / 1024:.1f} KB"
    elif size_bytes < 1024 * 1024 * 1024:
        return f"{size_bytes / (1024 * 1024):.1f} MB"
    else:
        return f"{size_bytes / (1024 * 1024 * 1024):.1f} GB"


def _is_template_deleted(template_id: str) -> bool:
    """检查模板是否已被删除（不存在于 graph_templates 目录）"""
    from backend.services.graph_template_store import get_template
    return get_template(template_id) is None


def cleanup_audit_logs(
    retention_days: int,
    dry_run: bool = True,
    audit_dir: Optional[Path] = None,
) -> Dict[str, Any]:
    """清理已删除模板的过期审计日志。

    Args:
        retention_days: 保留天数（必须 > 0）
        dry_run: True 只返回将删除的文件，不实际删除
        audit_dir: 审计目录路径，默认 output/graph_template_audit

    Returns:
        {
            "matched": int,      # 匹配条件的文件数
            "deleted": int,      # 实际删除的文件数（dry_run 时为 0）
            "skipped": int,      # 跳过的文件数（未删除模板或未过期）
            "bytes_freed": int,  # 释放的字节数（dry_run 时为将释放的字节数）
            "errors": [],        # 错误列表
            "dry_run": bool,
            "retention_days": int,
            "would_delete": []   # dry_run 时返回将删除的文件详情
        }

    Raises:
        ValueError: retention_days <= 0
    """
    if retention_days <= 0:
        raise ValueError("retention_days must be positive")

    files = scan_audit_files(audit_dir)
    cutoff = datetime.now(timezone.utc) - timedelta(days=retention_days)
    cutoff_iso = cutoff.isoformat()

    matched = 0
    deleted = 0
    skipped = 0
    bytes_freed = 0
    errors = []
    would_delete = []

    for f in files:
        template_id = _extract_template_id(f)
        if template_id is None:
            skipped += 1
            continue

        # 检查模板是否已删除
        try:
            if not _is_template_deleted(template_id):
                skipped += 1
                continue
        except Exception as e:
            errors.append({"template_id": template_id, "error": f"Failed to check template: {e}"})
            continue

        # 检查最新事件是否过期
        time_range = _get_file_time_range(f)
        if time_range["error"]:
            errors.append({"template_id": template_id, "error": time_range["error"]})
            continue

        if time_range["latest"] is None:
            # 空文件或无时间戳，跳过
            skipped += 1
            continue

        if time_range["latest"] > cutoff_iso:
            # 未过期，跳过
            skipped += 1
            continue

        # 匹配条件
        matched += 1
        try:
            size = f.stat().st_size
        except OSError:
            size = 0

        file_info = {
            "template_id": template_id,
            "file_path": str(f),
            "size_bytes": size,
            "event_count": time_range["event_count"],
            "latest_event": time_range["latest"],
        }

        if dry_run:
            would_delete.append(file_info)
            bytes_freed += size
        else:
            try:
                f.unlink()
                deleted += 1
                bytes_freed += size
                logger.info("Deleted audit log: %s", f)
            except OSError as e:
                errors.append({"template_id": template_id, "error": f"Failed to delete: {e}"})

    return {
        "matched": matched,
        "deleted": deleted,
        "skipped": skipped,
        "bytes_freed": bytes_freed,
        "bytes_freed_human": _human_readable_size(bytes_freed),
        "errors": errors,
        "dry_run": dry_run,
        "retention_days": retention_days,
        "would_delete": would_delete if dry_run else [],
    }
