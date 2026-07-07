"""Graph Template Store — 轻量级图模板持久化

把自定义 DAG 配置保存为可复用的 template。
每个 template 存为一个 JSON 文件：output/graph_templates/{template_id}.json
"""
from __future__ import annotations

import json
import logging
import re
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

# 默认存储目录（可通过 patch 覆盖）
DEFAULT_TEMPLATES_DIR = Path("output/graph_templates")
_TEMPLATE_ID_RE = re.compile(r"^tpl_[A-Za-z0-9_-]+$")


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
        logger.info("Deleted graph template: %s", template_id)
        return True
    except OSError as e:
        logger.error("Failed to delete template %s: %s", template_id, e)
        raise
