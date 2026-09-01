"""Read-only browser verification for the local AI Company OS instance."""
import json
import sqlite3
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List
from urllib.parse import urlparse

import httpx

try:
    from playwright.sync_api import sync_playwright
except ImportError:  # pragma: no cover - exercised when Playwright is absent
    sync_playwright = None


PROJECT_ROOT = Path(__file__).resolve().parents[2]
from backend.runtime_paths import DATABASE_PATH

DEFAULT_DB_PATH = DATABASE_PATH
BACKEND_HEALTH_URL = "http://127.0.0.1:8000/health"
FRONTEND_URL = "http://127.0.0.1:5173/app?page=agent-console"


class BrowserVerificationService:
    """Runs a fixed, non-mutating acceptance check against local services only."""

    def __init__(self, db_path: Path = DEFAULT_DB_PATH):
        self.db_path = Path(db_path)
        self._init_db()

    def run(self) -> Dict[str, Any]:
        run_id = f"browser_verify_{uuid.uuid4().hex[:12]}"
        started_at = _now()
        checks = [self._check_backend_health(), self._check_frontend()]
        passed = all(check["passed"] for check in checks)
        result = {
            "run_id": run_id,
            "status": "passed" if passed else "failed",
            "started_at": started_at,
            "finished_at": _now(),
            "targets": [BACKEND_HEALTH_URL, FRONTEND_URL],
            "checks": checks,
            "passed_count": sum(1 for check in checks if check["passed"]),
            "total_count": len(checks),
        }
        self._save_result(result)
        return result

    def list_runs(self, limit: int = 20) -> List[Dict[str, Any]]:
        limit = max(1, min(limit, 100))
        with sqlite3.connect(str(self.db_path)) as conn:
            rows = conn.execute(
                "SELECT result_json FROM browser_verification_runs ORDER BY created_at DESC LIMIT ?",
                (limit,),
            ).fetchall()
        return [json.loads(row[0]) for row in rows]

    def _check_backend_health(self) -> Dict[str, Any]:
        try:
            with httpx.Client(timeout=5, follow_redirects=False, proxy=None, trust_env=False) as client:
                response = client.get(BACKEND_HEALTH_URL)
            body = response.json() if response.headers.get("content-type", "").startswith("application/json") else {}
            passed = response.status_code == 200 and body.get("status") in {"ok", "healthy"}
            return _check_result(
                "backend_health",
                BACKEND_HEALTH_URL,
                passed,
                "后端健康检查通过" if passed else f"健康检查未通过（HTTP {response.status_code}）",
            )
        except Exception as error:
            return _check_result("backend_health", BACKEND_HEALTH_URL, False, _safe_error(error))

    def _check_frontend(self) -> Dict[str, Any]:
        if sync_playwright is None:
            return _check_result("frontend_page", FRONTEND_URL, False, "本地浏览器运行时不可用")

        page_errors: List[str] = []
        try:
            with sync_playwright() as playwright:
                browser = playwright.chromium.launch(headless=True, args=["--no-sandbox"])
                page = browser.new_page(viewport={"width": 1280, "height": 720})
                page.on("pageerror", lambda error: page_errors.append(str(error)))
                page.goto(FRONTEND_URL, wait_until="domcontentloaded", timeout=15000)
                root_visible = page.locator("#root").is_visible()
                page_title = page.title()
                browser.close()

            passed = root_visible and bool(page_title) and not page_errors
            if passed:
                message = "前端页面加载通过"
            elif page_errors:
                message = f"页面脚本错误：{_safe_text(page_errors[0])}"
            else:
                message = "页面根节点或标题不可用"
            return _check_result("frontend_page", FRONTEND_URL, passed, message)
        except Exception as error:
            return _check_result("frontend_page", FRONTEND_URL, False, _safe_error(error))

    def _init_db(self) -> None:
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        with sqlite3.connect(str(self.db_path)) as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS browser_verification_runs (
                    run_id TEXT PRIMARY KEY,
                    created_at TEXT NOT NULL,
                    status TEXT NOT NULL,
                    result_json TEXT NOT NULL
                )
                """
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_browser_verification_created "
                "ON browser_verification_runs(created_at DESC)"
            )

    def _save_result(self, result: Dict[str, Any]) -> None:
        with sqlite3.connect(str(self.db_path)) as conn:
            conn.execute(
                "INSERT INTO browser_verification_runs (run_id, created_at, status, result_json) VALUES (?, ?, ?, ?)",
                (result["run_id"], result["finished_at"], result["status"], json.dumps(result, ensure_ascii=False)),
            )


def is_allowed_local_target(url: str) -> bool:
    """Keep this capability bound to the two explicit local acceptance targets."""
    parsed = urlparse(url)
    return url in {BACKEND_HEALTH_URL, FRONTEND_URL} and parsed.scheme == "http" and parsed.hostname == "127.0.0.1"


def _check_result(check_id: str, target: str, passed: bool, message: str) -> Dict[str, Any]:
    return {"id": check_id, "target": target, "passed": passed, "message": message}


def _safe_error(error: Exception) -> str:
    return _safe_text(f"本地检查失败：{error}")


def _safe_text(value: str) -> str:
    return value.replace("\n", " ").replace("\r", " ")[:240]


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


_service: BrowserVerificationService | None = None


def get_browser_verification_service() -> BrowserVerificationService:
    global _service
    if _service is None:
        _service = BrowserVerificationService()
    return _service
