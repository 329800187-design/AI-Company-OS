"""Phase R1 security hardening regression coverage."""
import importlib
from pathlib import Path

import pytest
from fastapi.testclient import TestClient


def test_auth_configuration_requires_token_when_enabled_by_default(monkeypatch):
    from backend.middleware import auth_middleware

    monkeypatch.delenv("AUTH_ENABLED", raising=False)
    monkeypatch.delenv("AUTH_TOKEN", raising=False)
    monkeypatch.setattr(auth_middleware.Path, "exists", lambda _path: False)

    with pytest.raises(RuntimeError, match="AUTH_TOKEN"):
        auth_middleware._load_auth_config()


def test_core_app_registers_auth_middleware():
    from backend.core_app import app
    from backend.middleware.auth_middleware import AuthMiddleware

    assert any(middleware.cls is AuthMiddleware for middleware in app.user_middleware)


def test_auth_middleware_rejects_missing_token_and_accepts_valid_token(monkeypatch):
    from backend.core_app import app
    from backend.middleware import auth_middleware

    monkeypatch.setitem(auth_middleware.AUTH_CONFIG, "enabled", True)
    monkeypatch.setitem(auth_middleware.AUTH_CONFIG, "token", "phase-r1-test-token")
    client = TestClient(app)

    assert client.get("/boss/templates").status_code == 401
    assert client.get(
        "/boss/templates", headers={"Authorization": "Bearer phase-r1-test-token"}
    ).status_code == 200


def test_production_app_hides_api_documentation(monkeypatch):
    monkeypatch.setenv("ENV", "production")
    monkeypatch.setenv("AUTH_ENABLED", "false")
    monkeypatch.setenv("AUTH_TOKEN", "phase-r1-test-token")

    import backend.core_app

    production_app = importlib.reload(backend.core_app).app
    client = TestClient(production_app)

    assert client.get("/docs").status_code == 404
    assert client.get("/openapi.json").status_code == 404
    assert client.get("/redoc").status_code == 404

    monkeypatch.setenv("ENV", "development")
    importlib.reload(backend.core_app)


def test_frontend_api_client_uses_session_only_access_token_header():
    client_source = Path("frontend-new/src/api/client.ts").read_text(encoding="utf-8")

    assert "sessionStorage" in client_source
    assert "Authorization" in client_source
    assert "setAccessToken" in client_source


def test_frontend_delivery_downloads_use_authenticated_requests():
    client_source = Path("frontend-new/src/api/client.ts").read_text(encoding="utf-8")
    delivery_index_source = Path("frontend-new/src/pages/delivery/index.tsx").read_text(
        encoding="utf-8"
    )
    delivery_detail_source = Path("frontend-new/src/pages/delivery/detail.tsx").read_text(
        encoding="utf-8"
    )

    assert "downloadMiniDeliveryArtifact" in client_source
    assert "downloadMiniDeliveryPdf" in client_source
    assert "headers: this.authHeaders()" in client_source
    assert 'response.headers.get("content-type")' in client_source
    assert '`${taskId}.${extension}`' in client_source
    assert "getMiniDeliveryDownloadUrl" not in delivery_index_source
    assert "getMiniDeliveryDownloadUrl" not in delivery_detail_source
    assert "getMiniDeliveryPdfUrl" not in delivery_detail_source
