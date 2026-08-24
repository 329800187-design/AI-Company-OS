"""Unit coverage for CC Switch configuration and credential handling."""


def test_cc_switch_config_reads_environment(monkeypatch):
    from backend.ai_registry.registry import _cc_switch_config

    monkeypatch.setenv("CC_SWITCH_BASE_URL", "http://127.0.0.1:19000/")
    monkeypatch.setenv("CC_SWITCH_API_KEY", "test-key")
    monkeypatch.setenv("CC_SWITCH_MODEL", "configured-model")

    assert _cc_switch_config() == ("http://127.0.0.1:19000", "test-key", "configured-model")


def test_cc_switch_execution_requires_configured_credential(monkeypatch):
    from backend.ai_registry.registry import AIRegistry, AIService

    monkeypatch.delenv("CC_SWITCH_API_KEY", raising=False)
    registry = AIRegistry()
    service = AIService(service_id="cc-switch", name="CC Switch", provider="cc-switch", kind="proxy", status="online")

    result = registry._exec_cc_switch(service, {"prompt": "hello"})

    assert result["success"] is False
    assert "CC_SWITCH_API_KEY" in result["error"]


def test_cc_switch_headers_do_not_send_empty_credential():
    from backend.ai_registry.registry import _cc_switch_headers

    assert "x-api-key" not in _cc_switch_headers("")
    assert _cc_switch_headers("configured-key")["x-api-key"] == "configured-key"
