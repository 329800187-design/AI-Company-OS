"""Phase 7D deployment verification for AI Company OS.

This script is intentionally built with the Python standard library so it can
also prepare a fresh checkout before project dependencies are installed.

Examples:
    python scripts/verify_deployment.py
    python scripts/verify_deployment.py --install-deps
    python scripts/verify_deployment.py --skip-frontend
    python scripts/verify_deployment.py --with-providers
    python scripts/verify_deployment.py --json
"""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import socket
import subprocess
import sys
import tempfile
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Iterable, Sequence
from urllib.error import URLError
from urllib.request import Request, urlopen


PROJECT_ROOT = Path(__file__).resolve().parent.parent
FRONTEND_DIR = PROJECT_ROOT / "frontend-new"
MIN_PYTHON = (3, 12)
MIN_NODE = (20, 19)
ANSI_ESCAPE = re.compile(r"\x1b\[[0-?]*[ -/]*[@-~]")


@dataclass
class CheckResult:
    name: str
    status: str
    detail: str
    duration_seconds: float = 0.0
    fix: str = ""


def _parse_version(value: str) -> tuple[int, ...]:
    cleaned = value.strip().lstrip("vV")
    parts = []
    for token in cleaned.split("."):
        digits = "".join(char for char in token if char.isdigit())
        if not digits:
            break
        parts.append(int(digits))
    return tuple(parts)


def _tail(value: str, lines: int = 12) -> str:
    clean = ANSI_ESCAPE.sub("", value)
    items = [line.rstrip() for line in clean.splitlines() if line.strip()]
    return "\n".join(items[-lines:])


def _summary(results: Iterable[CheckResult]) -> dict[str, int | bool]:
    items = list(results)
    passed = sum(result.status == "pass" for result in items)
    failed = sum(result.status == "fail" for result in items)
    skipped = sum(result.status == "skip" for result in items)
    warned = sum(result.status == "warn" for result in items)
    return {
        "total": len(items),
        "passed": passed,
        "failed": failed,
        "warned": warned,
        "skipped": skipped,
        "all_passed": failed == 0,
    }


def _executable(name: str) -> str | None:
    candidates = [name]
    if os.name == "nt" and not name.lower().endswith(".cmd"):
        candidates.insert(0, f"{name}.cmd")
    for candidate in candidates:
        resolved = shutil.which(candidate)
        if resolved:
            return resolved
    return None


def _run(
    name: str,
    command: Sequence[str],
    *,
    cwd: Path = PROJECT_ROOT,
    timeout: int = 300,
    env: dict[str, str] | None = None,
) -> CheckResult:
    started = time.monotonic()
    try:
        completed = subprocess.run(
            list(command),
            cwd=str(cwd),
            env=env,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout,
            check=False,
        )
    except subprocess.TimeoutExpired as exc:
        return CheckResult(
            name=name,
            status="fail",
            detail=f"timed out after {timeout}s",
            duration_seconds=round(time.monotonic() - started, 2),
            fix=f"Re-run manually: {' '.join(command)}",
        )
    except OSError as exc:
        return CheckResult(
            name=name,
            status="fail",
            detail=str(exc),
            duration_seconds=round(time.monotonic() - started, 2),
        )

    output = "\n".join(part for part in (completed.stdout, completed.stderr) if part)
    duration = round(time.monotonic() - started, 2)
    if completed.returncode == 0:
        return CheckResult(name, "pass", _tail(output) or "completed", duration)
    return CheckResult(
        name=name,
        status="fail",
        detail=_tail(output) or f"exit code {completed.returncode}",
        duration_seconds=duration,
        fix=f"Re-run manually: {' '.join(command)}",
    )


def check_required_files() -> CheckResult:
    required = [
        "requirements.txt",
        "backend/app.py",
        "frontend-new/package.json",
        "frontend-new/package-lock.json",
        "scripts/backend_smoke_check.py",
        "scripts/healthcheck_local.py",
    ]
    missing = [path for path in required if not (PROJECT_ROOT / path).is_file()]
    if missing:
        return CheckResult(
            "required_files",
            "fail",
            f"missing: {', '.join(missing)}",
            fix="Use a complete release archive or clean Git checkout.",
        )
    return CheckResult("required_files", "pass", f"{len(required)} required files present")


def check_python() -> CheckResult:
    current = sys.version_info[:3]
    if current < MIN_PYTHON:
        return CheckResult(
            "python_version",
            "fail",
            f"Python {'.'.join(map(str, current))}; requires 3.12+",
            fix="Install Python 3.12 or use the project virtual environment.",
        )
    return CheckResult("python_version", "pass", f"Python {'.'.join(map(str, current))}")


def check_node() -> tuple[CheckResult, CheckResult]:
    node = _executable("node")
    npm = _executable("npm")
    if not node:
        node_result = CheckResult(
            "node_version", "fail", "node not found", fix="Install Node.js 20.19+ or 22.12+."
        )
    else:
        node_result = _run("node_version", [node, "--version"], timeout=15)
        if node_result.status == "pass":
            version = _parse_version(node_result.detail)
            if version < MIN_NODE:
                node_result.status = "fail"
                node_result.fix = "Install Node.js 20.19+ or 22.12+."
    if not npm:
        npm_result = CheckResult(
            "npm_version", "fail", "npm not found", fix="Install npm with Node.js."
        )
    else:
        npm_result = _run("npm_version", [npm, "--version"], timeout=15)
    return node_result, npm_result


def install_dependencies(npm: str | None) -> list[CheckResult]:
    results = [
        _run(
            "python_dependencies",
            [sys.executable, "-m", "pip", "install", "-r", "requirements.txt"],
            timeout=900,
        )
    ]
    if not npm:
        results.append(
            CheckResult("frontend_dependencies", "fail", "npm not found", fix="Install Node.js first.")
        )
    elif (FRONTEND_DIR / "node_modules").is_dir():
        results.append(
            CheckResult("frontend_dependencies", "pass", "node_modules already present")
        )
    else:
        results.append(
            _run("frontend_dependencies", [npm, "ci"], cwd=FRONTEND_DIR, timeout=900)
        )
    return results


def reserve_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def wait_for_health(base_url: str, timeout: int) -> CheckResult:
    started = time.monotonic()
    last_error = "backend did not respond"
    while time.monotonic() - started < timeout:
        try:
            request = Request(f"{base_url}/health", headers={"Accept": "application/json"})
            with urlopen(request, timeout=2) as response:
                data = json.loads(response.read().decode("utf-8", errors="replace"))
                if response.status == 200 and data.get("status") == "ok":
                    return CheckResult(
                        "backend_health",
                        "pass",
                        f"{base_url}/health returned status=ok, version={data.get('version', '?')}",
                        round(time.monotonic() - started, 2),
                    )
                last_error = f"unexpected response: HTTP {response.status} {data}"
        except (OSError, URLError, ValueError, json.JSONDecodeError) as exc:
            last_error = str(exc)
        time.sleep(1)
    return CheckResult(
        "backend_health",
        "fail",
        last_error,
        round(time.monotonic() - started, 2),
        fix="Inspect the backend log path printed by this verifier.",
    )


def stop_process(process: subprocess.Popen[bytes]) -> None:
    if process.poll() is not None:
        return
    process.terminate()
    try:
        process.wait(timeout=10)
    except subprocess.TimeoutExpired:
        process.kill()
        process.wait(timeout=5)


def verify_backend(port: int, startup_timeout: int, with_providers: bool) -> list[CheckResult]:
    base_url = f"http://127.0.0.1:{port}"
    environment = os.environ.copy()
    environment["PYTHONPATH"] = str(PROJECT_ROOT) + os.pathsep + environment.get("PYTHONPATH", "")
    environment["PYTHONIOENCODING"] = "utf-8"
    environment["PYTHONUTF8"] = "1"
    # The ephemeral verification instance validates routing without depending on
    # a user's local authentication token.
    environment["AUTH_ENABLED"] = "false"

    log_file = tempfile.NamedTemporaryFile(
        mode="w+b", prefix="ai-company-os-phase7d-", suffix=".log", delete=False
    )
    log_path = Path(log_file.name)
    process: subprocess.Popen[bytes] | None = None
    results: list[CheckResult] = []
    try:
        process = subprocess.Popen(
            [
                sys.executable,
                "-m",
                "uvicorn",
                "backend.app:app",
                "--host",
                "127.0.0.1",
                "--port",
                str(port),
            ],
            cwd=str(PROJECT_ROOT),
            env=environment,
            stdout=log_file,
            stderr=subprocess.STDOUT,
        )
        health = wait_for_health(base_url, startup_timeout)
        if health.status == "fail":
            health.detail = f"{health.detail}; backend log: {log_path}"
            results.append(health)
            return results
        results.append(health)

        results.append(
            _run(
                "backend_smoke",
                [
                    sys.executable,
                    "scripts/backend_smoke_check.py",
                    "--host",
                    "127.0.0.1",
                    "--port",
                    str(port),
                ],
                timeout=120,
                env=environment,
            )
        )

        health_command = [
            sys.executable,
            "scripts/healthcheck_local.py",
            "--host",
            "127.0.0.1",
            "--port",
            str(port),
            "--skip-frontend",
        ]
        if with_providers:
            health_command.append("--with-providers")
        results.append(
            _run("deployment_healthcheck", health_command, timeout=180, env=environment)
        )
        return results
    finally:
        if process is not None:
            stop_process(process)
        log_file.close()
        if results and all(result.status == "pass" for result in results):
            try:
                log_path.unlink()
            except OSError:
                pass


def print_report(results: Sequence[CheckResult]) -> None:
    print("\nAI Company OS — Phase 7D Deployment Verification\n")
    icons = {"pass": "PASS", "fail": "FAIL", "warn": "WARN", "skip": "SKIP"}
    for result in results:
        print(f"[{icons.get(result.status, '?'):4}] {result.name} ({result.duration_seconds:.2f}s)")
        for line in result.detail.splitlines():
            print(f"       {line}")
        if result.fix:
            print(f"       Fix: {result.fix}")
    summary = _summary(results)
    print(
        "\nSummary: "
        f"PASS={summary['passed']} FAIL={summary['failed']} "
        f"WARN={summary['warned']} SKIP={summary['skipped']} TOTAL={summary['total']}"
    )
    print("DEPLOYMENT VERIFICATION PASSED\n" if summary["all_passed"] else "DEPLOYMENT VERIFICATION FAILED\n")


def main() -> int:
    # Windows PowerShell commonly exposes a legacy console encoding. The
    # verifier may relay Unicode output from Vite and pytest, so force a stable
    # machine-readable encoding instead of crashing while printing the report.
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    if hasattr(sys.stderr, "reconfigure"):
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")

    parser = argparse.ArgumentParser(description="Verify a deployable AI Company OS checkout.")
    parser.add_argument(
        "--install-deps",
        action="store_true",
        help="Install Python dependencies and run npm ci when node_modules is absent.",
    )
    parser.add_argument("--skip-frontend", action="store_true", help="Skip npm production build.")
    parser.add_argument("--skip-backend", action="store_true", help="Skip ephemeral backend checks.")
    parser.add_argument("--with-providers", action="store_true", help="Verify configured real providers.")
    parser.add_argument("--port", type=int, default=0, help="Ephemeral backend port; 0 selects a free port.")
    parser.add_argument("--startup-timeout", type=int, default=45)
    parser.add_argument("--command-timeout", type=int, default=600)
    parser.add_argument("--json", action="store_true", help="Emit a machine-readable report.")
    args = parser.parse_args()

    results: list[CheckResult] = [check_required_files(), check_python()]
    node_result, npm_result = check_node()
    results.extend((node_result, npm_result))
    npm = _executable("npm")

    if args.install_deps:
        results.extend(install_dependencies(npm))

    if any(result.status == "fail" for result in results):
        if args.json:
            print(json.dumps({"results": [asdict(r) for r in results], "summary": _summary(results)}, indent=2))
        else:
            print_report(results)
        return 1

    results.append(
        _run(
            "backend_import",
            [sys.executable, "-c", "import backend.app; print('backend import ok')"],
            timeout=120,
        )
    )

    if args.skip_frontend:
        results.append(CheckResult("frontend_build", "skip", "disabled by --skip-frontend"))
    elif not npm:
        results.append(CheckResult("frontend_build", "fail", "npm not found"))
    elif not (FRONTEND_DIR / "node_modules").is_dir():
        results.append(
            CheckResult(
                "frontend_build",
                "fail",
                "frontend-new/node_modules is missing",
                fix="Re-run with --install-deps.",
            )
        )
    else:
        results.append(
            _run("frontend_build", [npm, "run", "build"], cwd=FRONTEND_DIR, timeout=args.command_timeout)
        )

    if args.skip_backend:
        results.append(CheckResult("backend_runtime", "skip", "disabled by --skip-backend"))
    elif all(result.status != "fail" for result in results):
        results.extend(
            verify_backend(args.port or reserve_port(), args.startup_timeout, args.with_providers)
        )
    else:
        results.append(CheckResult("backend_runtime", "skip", "earlier required check failed"))

    report = {"results": [asdict(result) for result in results], "summary": _summary(results)}
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print_report(results)
    return 0 if report["summary"]["all_passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
