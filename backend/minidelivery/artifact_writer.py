"""产物写入器 — 将内容写入文件系统，支持多平台文件命名"""
import json
import os
from pathlib import Path
from typing import Any, Dict, Optional


OUTPUT_ROOT = Path(__file__).resolve().parent.parent.parent / "output" / "minidelivery"


def ensure_output_dir(task_id: str) -> Path:
    """确保输出目录存在，返回目录路径"""
    task_dir = OUTPUT_ROOT / task_id
    task_dir.mkdir(parents=True, exist_ok=True)
    return task_dir


def write_artifact(
    task_id: str,
    markdown_content: str,
    result_json: Dict[str, Any],
    md_filename: Optional[str] = None,
) -> Dict[str, str]:
    """
    写入 Markdown 产物和结果 JSON。

    md_filename: 自定义 md 文件名，默认 "xiaohongshu_pack.md"
    返回 {"md_path": "...", "json_path": "..."}
    """
    task_dir = ensure_output_dir(task_id)

    md_name = md_filename or "xiaohongshu_pack.md"
    md_path = task_dir / md_name
    json_path = task_dir / "result.json"

    md_path.write_text(markdown_content, encoding="utf-8")
    json_path.write_text(
        json.dumps(result_json, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    return {
        "md_path": str(md_path),
        "json_path": str(json_path),
    }
