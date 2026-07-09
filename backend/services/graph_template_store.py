"""Graph Template Store — 轻量级图模板持久化

把自定义 DAG 配置保存为可复用的 template。
每个 template 存为一个 JSON 文件：output/graph_templates/{template_id}.json

Phase 6.6: 版本历史 — 每次更新前自动保存旧版本快照。
版本存储：output/graph_template_versions/{template_id}/{version_id}.json
"""
from __future__ import annotations

import json
import logging
import re
import shutil
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

# 默认存储目录（可通过 patch 覆盖）
DEFAULT_TEMPLATES_DIR = Path("output/graph_templates")
_TEMPLATE_ID_RE = re.compile(r"^tpl_[A-Za-z0-9_-]+$")

# ── Version History constants ──────────────────────────────
DEFAULT_VERSIONS_DIR = Path("output/graph_template_versions")
_VERSION_ID_RE = re.compile(r"^ver_[0-9a-f]{12}$")
_MAX_VERSIONS_PER_TEMPLATE = 20


def _get_templates_dir() -> Path:
    """获取模板存储目录，不存在则创建"""
    templates_dir = DEFAULT_TEMPLATES_DIR
    templates_dir.mkdir(parents=True, exist_ok=True)
    return templates_dir


def _generate_template_id() -> str:
    """生成唯一 template ID"""
    return f"tpl_{uuid.uuid4().hex[:12]}"


def _is_valid_template_id(template_id: str) -> bool:
    return bool(_TEMPLATE_ID_RE.fullmatch(template_id or ""))


def _template_path(template_id: str) -> Optional[Path]:
    if not _is_valid_template_id(template_id):
        return None
    return _get_templates_dir() / f"{template_id}.json"


# ── Version History helpers ─────────────────────────────────


def _generate_version_id() -> str:
    """生成唯一 version ID"""
    return f"ver_{uuid.uuid4().hex[:12]}"


def _is_valid_version_id(version_id: str) -> bool:
    return bool(_VERSION_ID_RE.fullmatch(version_id or ""))


def _get_versions_dir(template_id: str, *, create: bool = True) -> Path:
    """获取模板版本存储目录"""
    versions_dir = DEFAULT_VERSIONS_DIR / template_id
    if create:
        versions_dir.mkdir(parents=True, exist_ok=True)
    return versions_dir


def _version_path(
    template_id: str,
    version_id: str,
    *,
    create_parent: bool = False,
) -> Optional[Path]:
    if not _is_valid_template_id(template_id) or not _is_valid_version_id(version_id):
        return None
    return _get_versions_dir(template_id, create=create_parent) / f"{version_id}.json"


def _version_created_at(file_path: Path) -> str:
    try:
        data = json.loads(file_path.read_text(encoding="utf-8"))
        return str(data.get("created_at", ""))
    except (json.JSONDecodeError, OSError):
        return ""


def _trim_old_versions(template_id: str) -> None:
    """保留最近 _MAX_VERSIONS_PER_TEMPLATE 个版本，删除最旧的"""
    versions_dir = _get_versions_dir(template_id, create=False)
    if not versions_dir.exists():
        return
    version_files = sorted(
        versions_dir.glob("ver_*.json"),
        key=lambda file_path: (_version_created_at(file_path), file_path.name),
    )
    excess = len(version_files) - _MAX_VERSIONS_PER_TEMPLATE
    if excess > 0:
        for f in version_files[:excess]:
            try:
                f.unlink()
                logger.info("Trimmed old version: %s", f.name)
            except OSError as e:
                logger.warning("Failed to trim version %s: %s", f.name, e)


def save_version_snapshot(
    template_id: str, template_data: Dict[str, Any]
) -> Dict[str, Any]:
    """保存模板的版本快照（不可变）。

    Args:
        template_id: 模板 ID
        template_data: 当前模板完整数据

    Returns:
        版本 dict
    """
    if not _is_valid_template_id(template_id):
        raise ValueError("Invalid template_id")

    version_id = _generate_version_id()
    now = datetime.now(timezone.utc).isoformat()

    version = {
        "version_id": version_id,
        "template_id": template_id,
        "created_at": now,
        "name": template_data.get("name", ""),
        "description": template_data.get("description", ""),
        "goal_hint": template_data.get("goal_hint", ""),
        "nodes": template_data.get("nodes", []),
        "edges": template_data.get("edges", []),
    }

    file_path = _version_path(template_id, version_id, create_parent=True)
    if file_path is None:
        raise ValueError("Invalid IDs")
    file_path.write_text(
        json.dumps(version, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    _trim_old_versions(template_id)
    logger.info("Saved version snapshot: %s for template %s", version_id, template_id)
    return version


def list_versions(template_id: str) -> List[Dict[str, Any]]:
    """列出模板的所有版本（摘要，不含完整 nodes/edges）。

    Returns:
        版本摘要列表，按 created_at 降序
    """
    if not _is_valid_template_id(template_id):
        return []

    versions_dir = _get_versions_dir(template_id, create=False)
    if not versions_dir.exists():
        return []

    versions = []
    for file_path in versions_dir.glob("ver_*.json"):
        try:
            data = json.loads(file_path.read_text(encoding="utf-8"))
            versions.append({
                "version_id": data.get("version_id", ""),
                "template_id": data.get("template_id", ""),
                "created_at": data.get("created_at", ""),
                "name": data.get("name", ""),
                "node_count": len(data.get("nodes", [])),
                "edge_count": len(data.get("edges", [])),
            })
        except (json.JSONDecodeError, OSError) as e:
            logger.warning("Skipping corrupt version file %s: %s", file_path, e)
            continue

    versions.sort(key=lambda v: v.get("created_at", ""), reverse=True)
    return versions


def get_version(template_id: str, version_id: str) -> Optional[Dict[str, Any]]:
    """读取单个版本详情（完整数据）。

    Returns:
        版本 dict，不存在返回 None
    """
    file_path = _version_path(template_id, version_id)
    if file_path is None or not file_path.exists():
        return None

    try:
        data = json.loads(file_path.read_text(encoding="utf-8"))
        if data.get("template_id") != template_id:
            logger.error(
                "Version %s template_id mismatch: expected %s, got %s",
                version_id, template_id, data.get("template_id"),
            )
            return None
        return data
    except (json.JSONDecodeError, OSError) as e:
        logger.error("Failed to read version %s: %s", version_id, e)
        return None


def delete_versions_for_template(template_id: str) -> None:
    """删除模板的所有版本目录。在删除模板时调用。"""
    if not _is_valid_template_id(template_id):
        return
    versions_dir = DEFAULT_VERSIONS_DIR / template_id
    if versions_dir.exists():
        try:
            shutil.rmtree(versions_dir)
            logger.info("Deleted versions directory for template: %s", template_id)
        except OSError as e:
            logger.error("Failed to delete versions for %s: %s", template_id, e)


def save_template(
    name: str,
    nodes: List[Dict[str, Any]],
    edges: List[Dict[str, Any]],
    description: str = "",
    goal_hint: str = "",
    template_id: Optional[str] = None,
) -> Dict[str, Any]:
    """保存 graph template 到文件系统。

    Args:
        name: 模板名称
        nodes: 节点列表
        edges: 边列表
        description: 模板描述
        goal_hint: 目标提示
        template_id: 可选，指定 ID（用于更新）

    Returns:
        完整的 template dict
    """
    if template_id is None:
        template_id = _generate_template_id()
    elif not _is_valid_template_id(template_id):
        raise ValueError("Invalid template_id")

    now = datetime.now(timezone.utc).isoformat()

    template = {
        "template_id": template_id,
        "name": name,
        "description": description,
        "goal_hint": goal_hint,
        "nodes": nodes,
        "edges": edges,
        "created_at": now,
        "updated_at": now,
    }

    file_path = _template_path(template_id)
    if file_path is None:
        raise ValueError("Invalid template_id")
    file_path.write_text(
        json.dumps(template, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    logger.info("Saved graph template: %s (%s)", template_id, name)
    return template


def get_template(template_id: str) -> Optional[Dict[str, Any]]:
    """读取单个 template。

    Args:
        template_id: 模板 ID

    Returns:
        template dict，不存在返回 None
    """
    file_path = _template_path(template_id)

    if file_path is None or not file_path.exists():
        return None

    try:
        data = json.loads(file_path.read_text(encoding="utf-8"))
        return data
    except (json.JSONDecodeError, OSError) as e:
        logger.error("Failed to read template %s: %s", template_id, e)
        return None


def list_templates() -> List[Dict[str, Any]]:
    """列出所有 template。

    Returns:
        template dict 列表，按 created_at 降序
    """
    templates_dir = _get_templates_dir()
    templates = []

    for file_path in templates_dir.glob("tpl_*.json"):
        try:
            data = json.loads(file_path.read_text(encoding="utf-8"))
            templates.append(data)
        except (json.JSONDecodeError, OSError) as e:
            logger.warning("Skipping corrupt template file %s: %s", file_path, e)
            continue

    # 按 created_at 降序
    templates.sort(key=lambda t: t.get("created_at", ""), reverse=True)
    return templates


def update_template(
    template_id: str,
    name: str,
    nodes: List[Dict[str, Any]],
    edges: List[Dict[str, Any]],
    description: str = "",
    goal_hint: str = "",
    skip_version_snapshot: bool = False,
) -> Optional[Dict[str, Any]]:
    """更新已有的 graph template。

    Args:
        template_id: 模板 ID
        name: 模板名称
        nodes: 节点列表
        edges: 边列表
        description: 模板描述
        goal_hint: 目标提示
        skip_version_snapshot: 跳过版本快照（回滚时由调用方自行保存）

    Returns:
        完整的 template dict，不存在或 ID 非法返回 None
    """
    if not _is_valid_template_id(template_id):
        return None

    existing = get_template(template_id)
    if existing is None:
        return None

    # Phase 6.6: 更新前自动保存旧版本快照
    if not skip_version_snapshot:
        save_version_snapshot(template_id, existing)

    now = datetime.now(timezone.utc).isoformat()

    template = {
        "template_id": template_id,
        "name": name,
        "description": description,
        "goal_hint": goal_hint,
        "nodes": nodes,
        "edges": edges,
        "created_at": existing.get("created_at", now),
        "updated_at": now,
    }

    file_path = _template_path(template_id)
    if file_path is None:
        return None
    file_path.write_text(
        json.dumps(template, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    logger.info("Updated graph template: %s (%s)", template_id, name)
    return template


def delete_template(template_id: str) -> bool:
    """删除 template。

    Args:
        template_id: 模板 ID

    Returns:
        True if deleted, False if not found
    """
    file_path = _template_path(template_id)

    if file_path is None or not file_path.exists():
        return False

    try:
        file_path.unlink()
        # Phase 6.6: 删除模板时同步清理版本目录
        delete_versions_for_template(template_id)
        logger.info("Deleted graph template: %s", template_id)
        return True
    except OSError as e:
        logger.error("Failed to delete template %s: %s", template_id, e)
        raise
