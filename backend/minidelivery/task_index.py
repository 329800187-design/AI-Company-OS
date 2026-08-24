"""Incremental metadata index for MiniDelivery task listings.

The delivery directory may contain thousands of small result.json files.
Reading every file for every list request becomes prohibitively slow on
Windows. This module keeps an internal SQLite index under OUTPUT_ROOT/.index
and only parses newly added task directories after the initial migration.
"""

from __future__ import annotations

import json
import os
import sqlite3
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional


_LOCKS: dict[str, threading.Lock] = {}
_LOCKS_GUARD = threading.Lock()


def _lock_for(root: Path) -> threading.Lock:
    key = str(root.resolve())
    with _LOCKS_GUARD:
        return _LOCKS.setdefault(key, threading.Lock())


def _connect(root: Path) -> sqlite3.Connection:
    index_dir = root / ".index"
    index_dir.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(str(index_dir / "tasks.sqlite3"), timeout=30)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA journal_mode=WAL")
    connection.execute("PRAGMA synchronous=NORMAL")
    connection.executescript(
        """
        CREATE TABLE IF NOT EXISTS tasks (
            task_id TEXT PRIMARY KEY,
            directory_name TEXT NOT NULL UNIQUE,
            goal TEXT NOT NULL DEFAULT '',
            agent_id TEXT NOT NULL DEFAULT '',
            artifact_type TEXT NOT NULL DEFAULT '',
            source_page TEXT NOT NULL DEFAULT '',
            created_at TEXT NOT NULL DEFAULT '',
            artifact_path TEXT NOT NULL DEFAULT '',
            result_path TEXT NOT NULL DEFAULT '',
            result_mtime_ns INTEGER NOT NULL,
            result_size INTEGER NOT NULL,
            succeeded INTEGER,
            failed INTEGER,
            total INTEGER,
            total_duration_ms INTEGER,
            handoff_enabled INTEGER,
            execution_mode TEXT
        );
        CREATE INDEX IF NOT EXISTS idx_tasks_created_at ON tasks(created_at DESC);
        CREATE INDEX IF NOT EXISTS idx_tasks_agent ON tasks(agent_id);
        CREATE INDEX IF NOT EXISTS idx_tasks_artifact ON tasks(artifact_type);
        CREATE INDEX IF NOT EXISTS idx_tasks_source ON tasks(source_page);
        CREATE TABLE IF NOT EXISTS index_errors (
            directory_name TEXT PRIMARY KEY,
            warning TEXT NOT NULL,
            result_mtime_ns INTEGER NOT NULL,
            result_size INTEGER NOT NULL
        );
        CREATE TABLE IF NOT EXISTS index_meta (
            key TEXT PRIMARY KEY,
            value TEXT NOT NULL
        );
        """
    )
    return connection


def _task_directories(root: Path) -> list[os.DirEntry[str]]:
    try:
        with os.scandir(root) as entries:
            return [
                entry
                for entry in entries
                if not entry.name.startswith(".") and entry.is_dir(follow_symlinks=False)
            ]
    except FileNotFoundError:
        return []


def _read_boss_metrics(task_dir: Path) -> dict[str, Any]:
    raw_path = task_dir / "raw_agent_result.json"
    if not raw_path.is_file():
        return {}
    try:
        raw = json.loads(raw_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        return {}
    return {
        key: raw.get(key)
        for key in (
            "succeeded",
            "failed",
            "total",
            "total_duration_ms",
            "handoff_enabled",
            "execution_mode",
        )
        if raw.get(key) is not None
    }


def _sync_index(connection: sqlite3.Connection, root: Path) -> None:
    directories = _task_directories(root)
    directory_names = {entry.name for entry in directories}
    indexed = {
        row["directory_name"]: (row["result_mtime_ns"], row["result_size"])
        for row in connection.execute(
            "SELECT directory_name, result_mtime_ns, result_size FROM tasks"
        )
    }
    indexed_errors = {
        row["directory_name"]: (row["result_mtime_ns"], row["result_size"])
        for row in connection.execute(
            "SELECT directory_name, result_mtime_ns, result_size FROM index_errors"
        )
    }

    known_names = set(indexed) | set(indexed_errors)
    removed = known_names - directory_names
    if removed:
        placeholders = ",".join("?" for _ in removed)
        values = tuple(removed)
        connection.execute(f"DELETE FROM tasks WHERE directory_name IN ({placeholders})", values)
        connection.execute(
            f"DELETE FROM index_errors WHERE directory_name IN ({placeholders})", values
        )

    for entry in directories:
        result_path = Path(entry.path) / "result.json"
        try:
            stat = result_path.stat()
        except OSError:
            continue
        signature = (stat.st_mtime_ns, stat.st_size)
        if indexed.get(entry.name) == signature or indexed_errors.get(entry.name) == signature:
            continue

        try:
            data = json.loads(result_path.read_text(encoding="utf-8"))
            if not isinstance(data, dict):
                raise ValueError("result.json root must be an object")
        except (OSError, UnicodeDecodeError, json.JSONDecodeError, ValueError) as exc:
            warning = f"跳过损坏的 result.json: {entry.name} ({exc})"
            connection.execute("DELETE FROM tasks WHERE directory_name = ?", (entry.name,))
            connection.execute(
                """
                INSERT INTO index_errors(directory_name, warning, result_mtime_ns, result_size)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(directory_name) DO UPDATE SET
                    warning=excluded.warning,
                    result_mtime_ns=excluded.result_mtime_ns,
                    result_size=excluded.result_size
                """,
                (entry.name, warning, stat.st_mtime_ns, stat.st_size),
            )
            continue

        created_at = data.get("created_at") or datetime.fromtimestamp(
            stat.st_mtime, tz=timezone.utc
        ).isoformat()
        task_id = str(data.get("task_id") or entry.name)
        metrics = _read_boss_metrics(Path(entry.path)) if data.get("agent_id") == "boss" else {}
        connection.execute("DELETE FROM index_errors WHERE directory_name = ?", (entry.name,))
        # A repaired result.json may change its task_id while keeping the same
        # directory. Remove the old row first so the directory uniqueness
        # constraint cannot block the upsert.
        connection.execute(
            "DELETE FROM tasks WHERE directory_name = ? AND task_id != ?",
            (entry.name, task_id),
        )
        connection.execute(
            """
            INSERT INTO tasks(
                task_id, directory_name, goal, agent_id, artifact_type, source_page,
                created_at, artifact_path, result_path, result_mtime_ns, result_size,
                succeeded, failed, total, total_duration_ms, handoff_enabled, execution_mode
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(task_id) DO UPDATE SET
                directory_name=excluded.directory_name,
                goal=excluded.goal,
                agent_id=excluded.agent_id,
                artifact_type=excluded.artifact_type,
                source_page=excluded.source_page,
                created_at=excluded.created_at,
                artifact_path=excluded.artifact_path,
                result_path=excluded.result_path,
                result_mtime_ns=excluded.result_mtime_ns,
                result_size=excluded.result_size,
                succeeded=excluded.succeeded,
                failed=excluded.failed,
                total=excluded.total,
                total_duration_ms=excluded.total_duration_ms,
                handoff_enabled=excluded.handoff_enabled,
                execution_mode=excluded.execution_mode
            """,
            (
                task_id,
                entry.name,
                str(data.get("goal") or ""),
                str(data.get("agent_id") or ""),
                str(data.get("artifact_type") or ""),
                str(data.get("source_page") or ""),
                str(created_at),
                str(data.get("artifact_path") or ""),
                str(result_path),
                stat.st_mtime_ns,
                stat.st_size,
                metrics.get("succeeded"),
                metrics.get("failed"),
                metrics.get("total"),
                metrics.get("total_duration_ms"),
                None if metrics.get("handoff_enabled") is None else int(bool(metrics["handoff_enabled"])),
                metrics.get("execution_mode"),
            ),
        )
    connection.commit()


def list_indexed_tasks(
    root: Path,
    *,
    q: Optional[str] = None,
    agent_id: Optional[str] = None,
    artifact_type: Optional[str] = None,
    source_page: Optional[str] = None,
    limit: int = 50,
    offset: int = 0,
) -> dict[str, Any]:
    if not root.exists():
        return {
            "tasks": [],
            "warnings": [],
            "total": 0,
            "limit": limit,
            "offset": offset,
            "has_more": False,
        }

    with _lock_for(root):
        connection = _connect(root)
        try:
            _sync_index(connection, root)
            clauses: list[str] = []
            params: list[Any] = []
            for column, value in (
                ("agent_id", agent_id),
                ("artifact_type", artifact_type),
                ("source_page", source_page),
            ):
                if value:
                    clauses.append(f"{column} = ?")
                    params.append(value)
            if q:
                pattern = f"%{q.lower()}%"
                clauses.append(
                    "(" + " OR ".join(
                        f"LOWER(COALESCE({column}, '')) LIKE ?"
                        for column in ("goal", "task_id", "agent_id", "artifact_type", "source_page")
                    ) + ")"
                )
                params.extend([pattern] * 5)

            where = f" WHERE {' AND '.join(clauses)}" if clauses else ""
            total = int(connection.execute(f"SELECT COUNT(*) FROM tasks{where}", params).fetchone()[0])
            rows = connection.execute(
                f"SELECT * FROM tasks{where} ORDER BY created_at DESC LIMIT ? OFFSET ?",
                [*params, limit, offset],
            ).fetchall()
            warnings = [
                row["warning"]
                for row in connection.execute(
                    "SELECT warning FROM index_errors ORDER BY directory_name"
                )
            ]
        finally:
            connection.close()

    tasks = []
    for row in rows:
        item = {
            "task_id": row["task_id"],
            "goal": row["goal"],
            "agent_id": row["agent_id"],
            "artifact_type": row["artifact_type"],
            "source_page": row["source_page"],
            "created_at": row["created_at"],
            "artifact_path": row["artifact_path"],
            "result_path": row["result_path"],
        }
        for key in (
            "succeeded",
            "failed",
            "total",
            "total_duration_ms",
            "handoff_enabled",
            "execution_mode",
        ):
            value = row[key]
            if value is not None:
                item[key] = bool(value) if key == "handoff_enabled" else value
        tasks.append(item)

    return {
        "tasks": tasks,
        "warnings": warnings,
        "total": total,
        "limit": limit,
        "offset": offset,
        "has_more": (offset + limit) < total,
    }
