"""Phase R2 authentication, subscription, and Stripe webhook coverage."""
from __future__ import annotations

from fastapi.testclient import TestClient


def _configure_isolated_user_store(monkeypatch, tmp_path):
    from backend.auth import user_system

    connection = getattr(user_system._local, "conn", None)
    if connection is not None:
        connection.close()
        user_system._local.conn = None
    monkeypatch.setattr(user_system, "DB_PATH", tmp_path / "company_os.db")
    monkeypatch.setattr(user_system, "_user_manager", None)
    return user_system


def _login(client: TestClient) -> dict:
    assert client.post(
        "/user/register",
        json={"username": "phase-r2-user", "email": "phase-r2@example.com", "password": "password123"},
    ).status_code == 200
    response = client.post(
        "/user/login", json={"username": "phase-r2-user", "password": "password123"}
    )
    assert response.status_code == 200
    return response.json()


def test_session_and_api_key_resolve_to_request_user(monkeypatch, tmp_path):
    _configure_isolated_user_store(monkeypatch, tmp_path)
    from backend.core_app import app
    from backend.middleware import auth_middleware

    monkeypatch.setitem(auth_middleware.AUTH_CONFIG, "enabled", True)
    monkeypatch.setitem(auth_middleware.AUTH_CONFIG, "token", "phase-r2-api-key")
    client = TestClient(app)

    login = _login(client)
    session_response = client.get("/user/me", headers={"Authorization": f"Bearer {login['token']}"})
    assert session_response.status_code == 200
    assert session_response.json()["username"] == "phase-r2-user"

    api_key_response = client.get("/user/me", headers={"Authorization": "Bearer phase-r2-api-key"})
    assert api_key_response.status_code == 200
    assert api_key_response.json()["auth_method"] == "api_key"


def test_free_user_is_denied_dag_workflow_until_signed_webhook_upgrades_tier(monkeypatch, tmp_path):
    user_system = _configure_isolated_user_store(monkeypatch, tmp_path)
    from backend.core_app import app
    from backend.middleware import auth_middleware
    from backend.services import payment_service

    monkeypatch.setitem(auth_middleware.AUTH_CONFIG, "enabled", True)
    monkeypatch.setitem(auth_middleware.AUTH_CONFIG, "token", "phase-r2-api-key")
    monkeypatch.setattr(payment_service, "STRIPE_KEY", "sk_test_phase_r2")
    monkeypatch.setattr(payment_service, "STRIPE_WEBHOOK_SECRET", "whsec_phase_r2")
    monkeypatch.setattr(payment_service, "STRIPE_AVAILABLE", True)
    monkeypatch.setattr(payment_service, "_payment", None)
    payment_service.get_payment_service()._payment_log_path = tmp_path / "payments.jsonl"
    client = TestClient(app)
    login = _login(client)
    headers = {"Authorization": f"Bearer {login['token']}"}
    template = {
        "name": "Phase R2 template",
        "nodes": [{"id": "research", "agent_id": "research", "prompt": "Research the goal"}],
        "edges": [],
    }

    denied = client.post("/boss/graph/templates", json=template, headers=headers)
    assert denied.status_code == 403
    assert denied.json()["error"] == "subscription_required"

    invalid_signature = client.post("/payment/webhook", content=b"{}", headers={"stripe-signature": "invalid"})
    assert invalid_signature.status_code == 400

    event = {
        "type": "checkout.session.completed",
        "data": {"object": {"id": "cs_phase_r2", "client_reference_id": login["user_id"], "metadata": {"tier": "pro"}}},
    }
    monkeypatch.setattr(payment_service.stripe.Webhook, "construct_event", lambda *_args: event)
    upgraded = client.post("/payment/webhook", content=b"signed", headers={"stripe-signature": "valid"})
    assert upgraded.status_code == 200
    assert upgraded.json()["ok"] is True

    allowed = client.post("/boss/graph/templates", json=template, headers=headers)
    assert allowed.status_code == 200
    assert allowed.json()["ok"] is True


def test_public_auth_endpoints_are_rate_limited(monkeypatch, tmp_path):
    _configure_isolated_user_store(monkeypatch, tmp_path)
    from backend.core_app import app
    from backend.middleware import auth_middleware
    from backend.security import rate_limiter

    monkeypatch.setitem(auth_middleware.AUTH_CONFIG, "enabled", True)
    monkeypatch.setitem(auth_middleware.AUTH_CONFIG, "token", "phase-r2-api-key")
    monkeypatch.setattr(rate_limiter, "check", lambda *_args, **_kwargs: (False, "too many requests"))
    response = TestClient(app).post(
        "/user/login", json={"username": "phase-r2-user", "password": "password123"}
    )
    assert response.status_code == 429


def test_daily_agent_quota_is_still_enforced(monkeypatch, tmp_path):
    user_system = _configure_isolated_user_store(monkeypatch, tmp_path)
    from backend.core_app import app
    from backend.middleware import auth_middleware

    monkeypatch.setitem(auth_middleware.AUTH_CONFIG, "enabled", True)
    monkeypatch.setitem(auth_middleware.AUTH_CONFIG, "token", "phase-r2-api-key")
    client = TestClient(app)
    login = _login(client)
    monkeypatch.setattr(user_system.UserManager, "check_limits", lambda _self, _user_id: {"allowed": False, "reason": "quota"})
    response = client.post(
        "/agents/research/execute",
        json={"task": "research", "input": {"goal": "test"}},
        headers={"Authorization": f"Bearer {login['token']}"},
    )
    assert response.status_code == 429
