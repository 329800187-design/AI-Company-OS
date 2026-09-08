from pathlib import Path
import subprocess
import sys


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "generate_architecture_doc.py"


def test_architecture_generator_emits_runtime_inventory(tmp_path):
    output = tmp_path / "ARCHITECTURE.md"
    result = subprocess.run(
        [sys.executable, str(SCRIPT), "--output", str(output)],
        cwd=ROOT,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr
    document = output.read_text(encoding="utf-8")
    assert "# AI Company OS Architecture" in document
    assert "`/health`" in document
    assert "`backend/routers/boss_router.py`" in document
    assert "`agents/research_agent/agent.py`" in document
    assert "`requirements.txt`" in document


def test_architecture_generator_check_detects_drift(tmp_path):
    output = tmp_path / "ARCHITECTURE.md"
    subprocess.run(
        [sys.executable, str(SCRIPT), "--output", str(output)],
        cwd=ROOT,
        check=True,
    )

    clean = subprocess.run(
        [sys.executable, str(SCRIPT), "--output", str(output), "--check"],
        cwd=ROOT,
        capture_output=True,
        text=True,
    )
    assert clean.returncode == 0, clean.stderr

    output.write_text(output.read_text(encoding="utf-8") + "\nDrift\n", encoding="utf-8")
    drift = subprocess.run(
        [sys.executable, str(SCRIPT), "--output", str(output), "--check"],
        cwd=ROOT,
        capture_output=True,
        text=True,
    )
    assert drift.returncode == 1
