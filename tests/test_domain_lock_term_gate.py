from __future__ import annotations

import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "check_domain_lock_terms.py"


def _run(command, cwd: Path):
    return subprocess.run(command, cwd=cwd, check=True, capture_output=True, text=True)


def _repo(tmp_path: Path) -> tuple[Path, str]:
    repo = tmp_path / "repo"
    repo.mkdir()
    _run(["git", "init", "-q"], repo)
    _run(["git", "config", "user.email", "test@example.invalid"], repo)
    _run(["git", "config", "user.name", "Test"], repo)
    (repo / "docs").mkdir()
    (repo / "backend").mkdir()
    (repo / "docs" / "history.md").write_text("历史小红书示例\n", encoding="utf-8")
    (repo / "backend" / "compat.py").write_text("seo = payload.get(\"seo\", {})\n", encoding="utf-8")
    _run(["git", "add", "."], repo)
    _run(["git", "commit", "-qm", "baseline"], repo)
    return repo, _run(["git", "rev-parse", "HEAD"], repo).stdout.strip()


def _commit(repo: Path, message: str = "change") -> str:
    _run(["git", "add", "."], repo)
    _run(["git", "commit", "-qm", message], repo)
    return _run(["git", "rev-parse", "HEAD"], repo).stdout.strip()


def _gate(repo: Path, base: str, head: str):
    return subprocess.run(
        [sys.executable, str(SCRIPT), "--repo", str(repo), "--base", base, "--head", head],
        capture_output=True,
        text=True,
    )


def test_unchanged_historical_term_does_not_block(tmp_path):
    repo, base = _repo(tmp_path)
    (repo / "backend" / "new.py").write_text("value = 1\n", encoding="utf-8")
    assert _gate(repo, base, _commit(repo)).returncode == 0


def test_new_xiaohongshu_and_douyin_terms_are_blocked(tmp_path):
    repo, base = _repo(tmp_path)
    (repo / "docs" / "new.md").write_text("新增小红书和抖音方案\n", encoding="utf-8")
    result = _gate(repo, base, _commit(repo))
    assert result.returncode == 1
    assert "docs/new.md:1" in result.stderr
    assert "小红书" in result.stderr
    assert "抖音" in result.stderr


def test_new_backend_comment_is_checked(tmp_path):
    repo, base = _repo(tmp_path)
    (repo / "backend" / "new.py").write_text("# 小红书不是默认业务\n", encoding="utf-8")
    assert _gate(repo, base, _commit(repo)).returncode == 1


def test_new_term_in_historical_file_is_blocked(tmp_path):
    repo, base = _repo(tmp_path)
    history = repo / "docs" / "history.md"
    history.write_text(history.read_text(encoding="utf-8") + "新增电商描述\n", encoding="utf-8")
    assert _gate(repo, base, _commit(repo)).returncode == 1


def test_exact_compatibility_identifier_is_allowed_but_prose_is_blocked(tmp_path):
    repo, base = _repo(tmp_path)
    (repo / "backend" / "new.py").write_text(
        "page_goal = payload.get(\"page_goal\", \"\")\nlanding_page_copy = payload.get(\"landing_page_copy\", \"\")\n",
        encoding="utf-8",
    )
    assert _gate(repo, base, _commit(repo)).returncode == 0

    prose_base = _run(["git", "rev-parse", "HEAD"], repo).stdout.strip()
    with (repo / "backend" / "new.py").open("a", encoding="utf-8") as handle:
        handle.write('message = "为用户生成 SEO 营销方案"\n')
    assert _gate(repo, prose_base, _commit(repo)).returncode == 1


def test_deleting_a_historical_term_and_vendor_content_passes(tmp_path):
    repo, base = _repo(tmp_path)
    (repo / "docs" / "history.md").write_text("历史示例已删除\n", encoding="utf-8")
    vendor = repo / "node_modules" / "package"
    vendor.mkdir(parents=True)
    (vendor / "vendor.js").write_text("小红书\n", encoding="utf-8")
    generated = repo / "frontend-new" / "dist"
    generated.mkdir(parents=True)
    (generated / "bundle.js").write_text("抖音\n", encoding="utf-8")
    assert _gate(repo, base, _commit(repo)).returncode == 0


def test_missing_base_fails_safe(tmp_path):
    repo, _base = _repo(tmp_path)
    result = subprocess.run([sys.executable, str(SCRIPT), "--repo", str(repo)], capture_output=True, text=True)
    assert result.returncode == 2
    assert "missing base SHA" in result.stderr
