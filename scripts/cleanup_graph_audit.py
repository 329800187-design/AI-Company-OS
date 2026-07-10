#!/usr/bin/env python3
"""Graph Template Audit Cleanup Script

清理已删除模板的过期审计日志。

用法：
  python scripts/cleanup_graph_audit.py --retention-days 30 --dry-run
  python scripts/cleanup_graph_audit.py --retention-days 30 --apply
  python scripts/cleanup_graph_audit.py --retention-days 30 --apply --json

参数：
  --retention-days N  保留天数（必须 >= 1，默认 30）
  --dry-run           预览模式，只显示将删除的文件（默认行为）
  --apply             实际删除（需显式指定）
  --json              输出 JSON 格式
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

# 确保项目根目录在 sys.path 中
_PROJECT_ROOT = str(Path(__file__).resolve().parent.parent)
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

from backend.services.graph_template_retention import (
    cleanup_audit_logs,
    summarize_audit_storage,
)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="清理已删除模板的过期审计日志",
    )
    parser.add_argument(
        "--retention-days",
        type=int,
        default=30,
        help="保留天数（默认 30）",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        default=True,
        help="预览模式，只显示将删除的文件（默认）",
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        default=False,
        help="实际删除（需显式指定）",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        default=False,
        help="输出 JSON 格式",
    )

    args = parser.parse_args()

    # --apply 覆盖 --dry-run
    dry_run = not args.apply

    # 先显示存储摘要
    if not args.json:
        print("=" * 60)
        print("Graph Template Audit Storage Summary")
        print("=" * 60)
        summary = summarize_audit_storage()
        print(f"  文件数量: {summary['file_count']}")
        print(f"  总大小:   {summary['total_size_human']}")
        print(f"  最早事件: {summary['earliest_event'] or '—'}")
        print(f"  最新事件: {summary['latest_event'] or '—'}")
        print()

    # 执行清理
    try:
        result = cleanup_audit_logs(
            retention_days=args.retention_days,
            dry_run=dry_run,
        )
    except ValueError as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1

    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0

    # 人类可读输出
    print("=" * 60)
    if dry_run:
        print(f"Cleanup Preview (retention_days={args.retention_days})")
    else:
        print(f"Cleanup Applied (retention_days={args.retention_days})")
    print("=" * 60)
    print(f"  匹配文件:   {result['matched']}")
    print(f"  跳过文件:   {result['skipped']}")
    if dry_run:
        print(f"  将释放空间: {result['bytes_freed_human']}")
    else:
        print(f"  已删除文件: {result['deleted']}")
        print(f"  已释放空间: {result['bytes_freed_human']}")
    print(f"  错误数:     {len(result['errors'])}")
    print()

    if dry_run and result["would_delete"]:
        print("将删除的文件:")
        for f in result["would_delete"]:
            print(f"  - {f['template_id']}: {f['event_count']} 事件, {f['size_bytes']} B")
        print()

    if result["errors"]:
        print("错误:")
        for e in result["errors"]:
            print(f"  - {e['template_id']}: {e['error']}")
        print()

    if dry_run:
        print("提示: 使用 --apply 参数实际删除文件")
    else:
        if result["deleted"] > 0:
            print(f"已删除 {result['deleted']} 个文件")
        else:
            print("没有文件需要删除")

    return 0


if __name__ == "__main__":
    sys.exit(main())
