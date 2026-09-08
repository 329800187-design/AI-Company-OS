"""Reject newly added domain-locked product language in selected repository paths.

The term set is derived from the explicit generic-business-process rules in
``docs/current_project_state.md``.  This checker intentionally examines only
added lines in a Git diff so historical compatibility material does not block
the first rollout of the guardrail.
"""
from __future__ import annotations

import argparse
import os
import re
import subprocess
import sys
from pathlib import Path


# Source: docs/current_project_state.md, "Hard Rules" and Phase 6.21/6.22 notes.
DOMAIN_LOCK_TERMS = (
    "闲鱼", "电商", "小红书", "抖音", "SaaS", "SEO", "市场调研", "上下文调研",
    "营销方案", "视觉方案", "数据分析框架", "落地页", "竞品", "页面目标", "首屏标题", "页面板块",
)
SCOPED_PREFIXES = ("backend/", "frontend-new/", "agents/", "docs/")
SCOPED_FILES = {"README.md"}
IGNORED_PATH_PARTS = {".git", "node_modules", "dist", "build", "__pycache__", ".cache", "vendor"}
COMPATIBILITY_IDENTIFIERS = ("seo", "page_goal", "landing_page_copy")
_HUNK = re.compile(r"^@@ -\d+(?:,\d+)? \+(\d+)(?:,\d+)? @@")


def _in_scope(path: str) -> bool:
    parts = set(Path(path).parts)
    return not (parts & IGNORED_PATH_PARTS) and (path in SCOPED_FILES or path.startswith(SCOPED_PREFIXES))


def _strip_exact_compatibility_identifiers(line: str) -> str:
    """Remove only exact technical identifier occurrences, not prose around them."""
    for identifier in COMPATIBILITY_IDENTIFIERS:
        quoted = re.compile(rf"(['\"])({re.escape(identifier)})\1(?=\s*[:,\]\)])")
        line = quoted.sub("<compatibility_identifier>", line)
        line = re.sub(rf"\b{re.escape(identifier)}\b(?=\s*=)", "<compatibility_identifier>", line)
    return line


def _added_lines(repo: Path, base: str, head: str):
    command = ["git", "diff", "--no-ext-diff", "--unified=0", "--find-renames", base, head, "--"]
    result = subprocess.run(command, cwd=repo, capture_output=True, text=True, encoding="utf-8")
    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip() or "git diff failed")

    path = ""
    line_number = 0
    for raw in result.stdout.splitlines():
        if raw.startswith("+++ "):
            candidate = raw[4:]
            path = candidate[2:] if candidate.startswith("b/") else candidate
            continue
        hunk = _HUNK.match(raw)
        if hunk:
            line_number = int(hunk.group(1))
            continue
        if raw.startswith("+") and not raw.startswith("+++"):
            yield path, line_number, raw[1:]
            line_number += 1


def find_violations(repo: Path, base: str, head: str) -> list[tuple[str, int, str]]:
    violations = []
    for path, line_number, line in _added_lines(repo, base, head):
        if not _in_scope(path) or "\x00" in line:
            continue
        candidate = _strip_exact_compatibility_identifiers(line)
        for term in DOMAIN_LOCK_TERMS:
            if re.search(re.escape(term), candidate, flags=re.IGNORECASE):
                violations.append((path, line_number, term))
    return violations


def _default_base() -> str:
    for key in ("GITHUB_BASE_SHA", "BASE_SHA", "GITHUB_EVENT_BEFORE"):
        if os.getenv(key):
            return os.environ[key]
    raise ValueError("missing base SHA; pass --base or set GITHUB_BASE_SHA/BASE_SHA/GITHUB_EVENT_BEFORE")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base", help="base commit SHA")
    parser.add_argument("--head", default=os.getenv("GITHUB_SHA", "HEAD"), help="head commit SHA")
    parser.add_argument("--repo", type=Path, default=Path.cwd(), help="repository root")
    args = parser.parse_args()
    try:
        base = args.base or _default_base()
        violations = find_violations(args.repo.resolve(), base, args.head)
    except (OSError, RuntimeError, ValueError) as exc:
        print(f"domain-lock scan could not determine a safe diff: {exc}", file=sys.stderr)
        return 2
    if not violations:
        return 0
    for path, line_number, term in violations:
        print(f"{path}:{line_number}: domain-locked term '{term}' added in this diff", file=sys.stderr)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
