import pytest


def test_provider_verification_persists_and_invalidates_on_config_change(monkeypatch, tmp_path):
    from backend.services import provider_verification as verification

    monkeypatch.setattr(verification, "_VERIFICATION_FILE", tmp_path / "provider-verification.json")
    monkeypatch.setenv("OPENAI_API_KEY", "old-key")
    monkeypatch.setenv("OPENAI_BASE_URL", "http://provider.test/v1")
    monkeypatch.setenv("OPENAI_MODEL", "model-a")

    verification.set_provider_verification("openai", verified=True)
    assert verification.get_provider_verification("openai")["verified"] is True

    monkeypatch.setenv("OPENAI_API_KEY", "new-key")
    assert verification.get_provider_verification("openai")["verified"] is False


def test_save_does_not_switch_or_clear_existing_api_key(monkeypatch, tmp_path):
    import backend.routers.config_router as config_router

    env_file = tmp_path / ".env"
    env_file.write_text("AI_PROVIDER=deepseek\nOPENAI_API_KEY=old-key\n", encoding="utf-8")
    monkeypatch.setattr(config_router, "ENV_FILE", env_file)
    monkeypatch.setenv("AI_PROVIDER", "deepseek")
    monkeypatch.setenv("OPENAI_API_KEY", "old-key")

    config_router.save_config(config_router.ConfigSaveData(ai_provider="openai", openai_api_key=""))

    assert "OPENAI_API_KEY=old-key" in env_file.read_text(encoding="utf-8")
    assert config_router.get_current_provider() == "deepseek"


def test_switch_rejects_unverified_provider(monkeypatch):
    import backend.routers.config_router as config_router

    monkeypatch.setattr(config_router, "get_provider_info", lambda: [
        {"id": "openai", "configured": True},
    ])
    monkeypatch.setattr(config_router, "get_provider_verification", lambda provider: {"verified": False})

    with pytest.raises(config_router.HTTPException) as exc_info:
        config_router.switch_provider(config_router.SwitchProviderData(provider="openai"))

    assert exc_info.value.status_code == 400


def test_switch_allows_verified_provider(monkeypatch):
    import backend.routers.config_router as config_router

    class FakeManager:
        def switch_to(self, provider):
            return {"ok": True, "message": "switched"}

        def get_current(self):
            return {"brain_id": "openai"}

    monkeypatch.setenv("AI_PROVIDER", "openai")
    monkeypatch.setattr(config_router, "get_provider_info", lambda: [
        {"id": "openai", "configured": True},
    ])
    monkeypatch.setattr(config_router, "get_provider_verification", lambda provider: {"verified": True})
    monkeypatch.setattr("core.brain_manager.get_brain_manager", lambda: FakeManager())

    result = config_router.switch_provider(config_router.SwitchProviderData(provider="openai"))
    assert result["status"] == "ok"


def test_safe_dict_preserves_authorization_state_but_redacts_secret():
    from backend.ai_registry.contracts import AuthorizationState, CapabilityResource, ResourceType

    resource = CapabilityResource(
        resource_id="browser",
        resource_type=ResourceType.BROWSER,
        display_name="Browser",
        authorization=AuthorizationState.REQUIRED,
        metadata={"authorization": "Bearer secret"},
    )
    result = resource.safe_dict()

    assert result["authorization"] == "required"
    assert result["metadata"]["authorization"] == "[REDACTED]"
