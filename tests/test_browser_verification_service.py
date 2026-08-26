from backend.services.browser_verification_service import (
    BACKEND_HEALTH_URL,
    FRONTEND_URL,
    BrowserVerificationService,
    is_allowed_local_target,
)


def test_only_explicit_local_targets_are_allowed():
    assert is_allowed_local_target(BACKEND_HEALTH_URL)
    assert is_allowed_local_target(FRONTEND_URL)
    assert not is_allowed_local_target("http://localhost:8000/health")
    assert not is_allowed_local_target("https://github.com/329800187-design/AI-Company-OS")
    assert not is_allowed_local_target("http://127.0.0.1:8000/docs")


def test_run_persists_sanitized_audit_result(tmp_path, monkeypatch):
    service = BrowserVerificationService(db_path=tmp_path / "verification.db")
    monkeypatch.setattr(
        service,
        "_check_backend_health",
        lambda: {"id": "backend_health", "target": BACKEND_HEALTH_URL, "passed": True, "message": "后端健康检查通过"},
    )
    monkeypatch.setattr(
        service,
        "_check_frontend",
        lambda: {"id": "frontend_page", "target": FRONTEND_URL, "passed": True, "message": "前端页面加载通过"},
    )

    result = service.run()

    assert result["status"] == "passed"
    assert result["passed_count"] == 2
    assert result["targets"] == [BACKEND_HEALTH_URL, FRONTEND_URL]
    assert service.list_runs() == [result]


def test_run_reports_failed_check_without_page_content(tmp_path, monkeypatch):
    service = BrowserVerificationService(db_path=tmp_path / "verification.db")
    monkeypatch.setattr(
        service,
        "_check_backend_health",
        lambda: {"id": "backend_health", "target": BACKEND_HEALTH_URL, "passed": True, "message": "后端健康检查通过"},
    )
    monkeypatch.setattr(
        service,
        "_check_frontend",
        lambda: {"id": "frontend_page", "target": FRONTEND_URL, "passed": False, "message": "页面根节点或标题不可用"},
    )

    result = service.run()

    assert result["status"] == "failed"
    assert result["passed_count"] == 1
    assert "content" not in result["checks"][1]
