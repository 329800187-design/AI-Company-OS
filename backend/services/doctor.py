"""Runtime self-checks for AI Company OS.

The doctor reports capability status without exposing secrets. It is safe to
call from the API, CLI, or tests.
"""
from __future__ import annotations

import importlib
import os
import platform
import sys
from pathlib import Path
from typing import Any, Dict, List


ROOT = Path(__file__).resolve().parents[2]


def _check(name: str, status: str, summary: str, **details: Any) -> Dict[str, Any]:
    return {"name": name, "status": status, "summary": summary, "details": details}


def _import_check(module: str, package: str | None = None, required: bool = True) -> Dict[str, Any]:
    label = package or module
    try:
        importlib.import_module(module)
        return _check(label, "ok", "installed")
    except Exception as exc:
        status = "error" if required else "warn"
        return _check(label, status, f"missing or broken: {exc.__class__.__name__}", error=str(exc)[:200])


def _provider_checks() -> List[Dict[str, Any]]:
    from backend import config

    checks = []
    providers = config.get_provider_info()
    configured = [p["id"] for p in providers if p.get("configured")]
    current = config.AI_PROVIDER
    current_cfg = next((p for p in providers if p["id"] == current), None)
    if current_cfg and current_cfg.get("configured"):
        checks.append(_check("ai_provider", "ok", f"{current} configured", provider=current, model=current_cfg.get("model")))
    elif configured:
        checks.append(_check("ai_provider", "warn", f"{current} not configured; other providers available", provider=current, configured=configured))
    else:
        checks.append(_check("ai_provider", "error", "no AI provider API key configured", provider=current))
    checks.append(_check("auth", "warn" if not config.AUTH_TOKEN else "ok",
                         "auth token configured" if config.AUTH_TOKEN else "auth disabled or token not configured",
                         env=config.ENV))
    return checks


def _database_check() -> Dict[str, Any]:
    try:
        from backend.database.database import DB_PATH, get_db, init_db

        init_db()
        with get_db() as db:
            db.execute("CREATE TEMP TABLE IF NOT EXISTS __doctor_check (x INTEGER)")
            db.execute("DELETE FROM __doctor_check")
            db.execute("INSERT INTO __doctor_check VALUES (1)")
            count = db.execute("SELECT COUNT(*) FROM __doctor_check").fetchone()[0]
            sessions = db.execute("SELECT COUNT(*) FROM sessions").fetchone()[0]
        status = "ok" if count == 1 else "error"
        return _check("database", status, "sqlite readable and writable", path=DB_PATH, sessions=sessions)
    except Exception as exc:
        return _check("database", "error", f"database check failed: {exc.__class__.__name__}", error=str(exc)[:300])


def _frontend_check() -> Dict[str, Any]:
    files = [ROOT / "frontend" / "index.html", ROOT / "frontend" / "js" / "app.js", ROOT / "frontend" / "css" / "style.css"]
    missing = [str(p.relative_to(ROOT)) for p in files if not p.exists()]
    if missing:
        return _check("frontend", "error", "required frontend files missing", missing=missing)
    size = sum(p.stat().st_size for p in files)
    return _check("frontend", "ok", "ui files present", bytes=size)


def _agent_import_checks() -> Dict[str, Any]:
    agents = {
        "ceo": "agents.ceo_agent.agent",
        "codex": "agents.codex_agent.agent",
        "qa": "agents.qa_agent.agent",
        "cto": "agents.cto_agent.agent",
        "system": "agents.system_agent.agent",
        "openclaw": "agents.openclaw_agent.agent",
        "image": "agents.image_agent.agent",
        "marketing": "agents.marketing_agent.agent",
        "video": "agents.video_agent.agent",
        "data": "agents.data_agent.agent",
    }
    results: Dict[str, str] = {}
    errors: Dict[str, str] = {}
    for name, module in agents.items():
        try:
            importlib.import_module(module)
            results[name] = "ok"
        except Exception as exc:
            results[name] = "error"
            errors[name] = str(exc)[:200]
    failed = [name for name, status in results.items() if status != "ok"]
    return _check(
        "agents",
        "ok" if not failed else "error",
        f"{len(results) - len(failed)}/{len(results)} agents import",
        agents=results,
        errors=errors,
    )


def _ai_registry_check(force_scan: bool) -> Dict[str, Any]:
    try:
        from backend.ai_registry.registry import get_registry

        registry = get_registry()
        services = registry.scan_all(force=force_scan)
        service_rows = [svc.to_dict() for svc in services.values()]
        online = [s["service_id"] for s in service_rows if s.get("status") in ("online", "running")]
        installed = [s["service_id"] for s in service_rows if s.get("status") == "installed"]
        status = "ok" if online else ("warn" if installed else "error")
        return _check(
            "ai_registry",
            status,
            f"{len(online)} online, {len(installed)} installed, {len(service_rows)} discovered",
            online=online,
            installed=installed,
            services=[{"id": s["service_id"], "status": s["status"], "capabilities": s["capabilities"]} for s in service_rows],
        )
    except Exception as exc:
        return _check("ai_registry", "error", f"registry check failed: {exc.__class__.__name__}", error=str(exc)[:300])


def _playwright_check(deep: bool) -> Dict[str, Any]:
    try:
        from playwright.sync_api import sync_playwright
    except Exception as exc:
        return _check("playwright", "warn", "package unavailable", error=str(exc)[:200])

    if not deep:
        return _check("playwright", "ok", "package installed", browser_launch="skipped")

    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            browser.close()
        return _check("playwright", "ok", "chromium launches")
    except Exception as exc:
        return _check("playwright", "warn", "chromium launch failed; run `playwright install chromium`", error=str(exc)[:300])


def run_doctor(deep: bool = False) -> Dict[str, Any]:
    checks: List[Dict[str, Any]] = []
    checks.append(_check("python", "ok", sys.version.split()[0], executable=sys.executable, platform=platform.platform()))
    checks.append(_check("project_root", "ok" if ROOT.exists() else "error", str(ROOT)))

    for module, package, required in [
        ("fastapi", None, True),
        ("uvicorn", None, True),
        ("pydantic", None, True),
        ("httpx", None, True),
        ("dotenv", "python-dotenv", True),
        ("yaml", "pyyaml", True),
        ("pandas", None, False),
        ("matplotlib", None, False),
    ]:
        checks.append(_import_check(module, package, required=required))

    checks.extend(_provider_checks())
    checks.append(_database_check())
    checks.append(_frontend_check())
    checks.append(_agent_import_checks())
    checks.append(_playwright_check(deep=deep))
    checks.append(_ai_registry_check(force_scan=deep))

    errors = [c for c in checks if c["status"] == "error"]
    warnings = [c for c in checks if c["status"] == "warn"]
    overall = "error" if errors else ("warn" if warnings else "ok")
    next_actions = []
    if any(c["name"] == "ai_provider" and c["status"] == "error" for c in checks):
        next_actions.append("Configure at least one provider API key in .env or the UI settings page.")
    if any(c["name"] == "playwright" and c["status"] == "warn" for c in checks):
        next_actions.append("Run `playwright install chromium` if browser automation is needed.")
    if any(c["name"] in ("pandas", "matplotlib") and c["status"] == "warn" for c in checks):
        next_actions.append("Install data extras with `pip install pandas openpyxl matplotlib` if spreadsheet analysis or charts are needed.")
    if any(c["name"] == "ai_registry" and c["status"] != "ok" for c in checks):
        next_actions.append("Start the local AI services you expect to route through, such as Ollama, CC Switch, or OpenClaw.")

    return {
        "status": overall,
        "summary": {
            "ok": sum(1 for c in checks if c["status"] == "ok"),
            "warn": len(warnings),
            "error": len(errors),
        },
        "checks": checks,
        "next_actions": next_actions,
        "deep": deep,
        "cwd": os.getcwd(),
    }


def get_capability_matrix() -> Dict[str, Any]:
    """Return user-facing capability readiness without running expensive tasks."""
    from backend import config

    providers = {p["id"]: p for p in config.get_provider_info()}
    current_provider = config.AI_PROVIDER
    current_configured = bool(providers.get(current_provider, {}).get("configured"))
    openai_configured = bool(providers.get("openai", {}).get("configured"))
    claude_configured = bool(providers.get("claude", {}).get("configured"))

    try:
        from backend.ai_registry.registry import get_registry

        services = get_registry().scan_all(force=False)
        service_status = {sid: svc.status for sid, svc in services.items()}
    except Exception:
        service_status = {}

    rows = [
        {
            "id": "commander",
            "label": "Commander task orchestration",
            "status": "ready" if current_configured else "degraded",
            "mode": "ai" if current_configured else "rule_fallback",
            "note": "Uses the configured provider for planning when available.",
        },
        {
            "id": "codex",
            "label": "Codex code execution",
            "status": "ready",
            "mode": "local_sandbox",
            "note": "Python sandbox execution is local and does not require model tokens.",
        },
        {
            "id": "qa",
            "label": "QA validation",
            "status": "ready" if current_configured else "degraded",
            "mode": "ai_or_rule_fallback",
            "note": "Can score with AI, then falls back to rules.",
        },
        {
            "id": "cto",
            "label": "CTO review and decomposition",
            "status": "ready" if current_configured else "degraded",
            "mode": "ai_or_static_analysis",
            "note": "Static checks catch obvious risks even without an API key.",
        },
        {
            "id": "openclaw",
            "label": "Browser automation",
            "status": "ready" if service_status.get("openclaw") in ("online", "running") else "partial",
            "mode": "playwright_local",
            "note": "Agent can use local Playwright; OpenClaw service is optional but currently tracked separately.",
        },
        {
            "id": "image",
            "label": "Image generation",
            "status": "ready" if openai_configured else "degraded",
            "mode": "openai_images" if openai_configured else "prompt_only",
            "note": "Without OpenAI image support it returns an optimized prompt instead of an image.",
        },
        {
            "id": "video",
            "label": "Video generation",
            "status": "stub",
            "mode": "script_storyboard_only",
            "note": "Script and storyboard generation work; direct video rendering is a placeholder.",
        },
        {
            "id": "marketing",
            "label": "Marketing content",
            "status": "ready" if current_configured else "degraded",
            "mode": "ai_or_template_fallback",
            "note": "Falls back to templates when the configured provider is unavailable.",
        },
        {
            "id": "vision_analysis",
            "label": "Image analysis",
            "status": "ready" if (openai_configured or claude_configured) else "degraded",
            "mode": "vision_model" if (openai_configured or claude_configured) else "unsupported_provider",
            "note": "Needs a vision-capable OpenAI or Claude configuration.",
        },
        {
            "id": "local_llm",
            "label": "Local LLM routing",
            "status": "ready" if service_status.get("ollama") in ("online", "running") else "offline",
            "mode": "ollama" if service_status.get("ollama") in ("online", "running") else "not_detected",
            "note": "Ollama can be used for local inference paths where supported.",
        },
    ]

    counts: Dict[str, int] = {}
    for row in rows:
        counts[row["status"]] = counts.get(row["status"], 0) + 1
    return {
        "provider": current_provider,
        "provider_configured": current_configured,
        "services": service_status,
        "summary": counts,
        "capabilities": rows,
    }
