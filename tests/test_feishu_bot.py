from fastapi.testclient import TestClient

from backend import config
from backend.app import app
from backend.services.feishu_bot import feishu_bot_service


client = TestClient(app)


def test_feishu_health_endpoint():
    response = client.get("/integrations/feishu/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert data["callback_url"] == "/integrations/feishu/events"


def test_feishu_url_verification():
    response = client.post(
        "/integrations/feishu/events",
        json={"type": "url_verification", "challenge": "challenge-token"},
    )
    assert response.status_code == 200
    assert response.json() == {"challenge": "challenge-token"}


def test_feishu_events_reject_invalid_json():
    response = client.post(
        "/integrations/feishu/events",
        content="not-json",
        headers={"content-type": "text/plain"},
    )
    assert response.status_code == 400
    assert "Invalid JSON body" in response.json()["detail"]


def test_feishu_url_verification_rejects_missing_token_when_expected(monkeypatch):
    """Regression: tokenless callback must be rejected when FEISHU_VERIFICATION_TOKEN is set."""
    monkeypatch.setattr(config, "FEISHU_VERIFICATION_TOKEN", "real-secret-token")

    response = client.post(
        "/integrations/feishu/events",
        json={"type": "url_verification", "challenge": "challenge-token"},
    )
    # Missing token should be rejected, not treated as valid
    assert response.status_code in (400, 403, 500)


def test_feishu_url_verification_rejects_empty_token_when_expected(monkeypatch):
    """Regression: empty-string token must be rejected when FEISHU_VERIFICATION_TOKEN is set."""
    monkeypatch.setattr(config, "FEISHU_VERIFICATION_TOKEN", "real-secret-token")

    response = client.post(
        "/integrations/feishu/events",
        json={"type": "url_verification", "challenge": "challenge-token", "token": ""},
    )
    assert response.status_code in (400, 403, 500)


def test_feishu_group_message_ignored_when_not_mentioned(monkeypatch):
    monkeypatch.setattr(config, "FEISHU_BOT_ENABLED", True)
    monkeypatch.setattr(config, "FEISHU_APP_ID", "cli_test")
    monkeypatch.setattr(config, "FEISHU_APP_SECRET", "secret")
    monkeypatch.setattr(config, "FEISHU_REPLY_ONLY_MENTION", True)

    response = client.post(
        "/integrations/feishu/events",
        json={
            "schema": "2.0",
            "header": {"event_type": "im.message.receive_v1"},
            "event": {
                "sender": {},
                "message": {
                    "message_id": "om_test",
                    "chat_type": "group",
                    "message_type": "text",
                    "content": "{\"text\":\"大家讨论一下\"}",
                    "mentions": [],
                },
            },
        },
    )

    assert response.status_code == 200
    assert response.json()["status"] == "ignored"
    assert response.json()["reason"] == "not_mentioned"


def test_feishu_mentioned_message_replies(monkeypatch):
    monkeypatch.setattr(config, "FEISHU_BOT_ENABLED", True)
    monkeypatch.setattr(config, "FEISHU_APP_ID", "cli_test")
    monkeypatch.setattr(config, "FEISHU_APP_SECRET", "secret")
    monkeypatch.setattr(config, "FEISHU_REPLY_ONLY_MENTION", True)
    monkeypatch.setattr(feishu_bot_service, "_generate_ai_reply", lambda *args, **kwargs: "收到")

    sent = {}

    def fake_reply(message_id, text):
        sent["message_id"] = message_id
        sent["text"] = text

    monkeypatch.setattr(feishu_bot_service, "_reply_to_message", fake_reply)

    response = client.post(
        "/integrations/feishu/events",
        json={
            "schema": "2.0",
            "header": {"event_type": "im.message.receive_v1"},
            "event": {
                "sender": {},
                "message": {
                    "message_id": "om_test",
                    "chat_type": "group",
                    "message_type": "text",
                    "content": "{\"text\":\"<at user_id=\\\"ou_bot\\\">AI</at> 帮我总结\"}",
                    "mentions": [{"name": "AI"}],
                },
            },
        },
    )

    assert response.status_code == 200
    assert response.json()["status"] == "ok"
    assert sent == {"message_id": "om_test", "text": "收到"}
