"""Regression coverage for the runtime capability chain."""


def test_brain_profiles_follow_runtime_provider_config(monkeypatch, tmp_path):
    from core.brain_manager import BrainManager

    monkeypatch.setenv("AI_PROVIDER", "openai")
    monkeypatch.delenv("AI_BRAIN_ID", raising=False)
    monkeypatch.setenv("OPENAI_API_KEY", "runtime-key")
    monkeypatch.setenv("OPENAI_BASE_URL", "http://127.0.0.1:9000/v1")
    monkeypatch.setenv("OPENAI_MODEL", "runtime-model")

    manager = BrainManager(config_dir=str(tmp_path))
    current = manager.get_current()

    assert current["brain_id"] == "openai"
    assert current["base_url"] == "http://127.0.0.1:9000/v1"
    assert current["model"] == "runtime-model"
    assert current["has_api_key"] is True


def test_agent_registry_excludes_disabled_agents():
    from backend.services.agent_registry import AgentRegistry
    from backend.services.agent_discovery import AgentCapability

    registry = AgentRegistry()
    registry._agents = {
        "enabled": AgentCapability(id="enabled", name="Enabled", status="available", enabled=True),
        "disabled": AgentCapability(id="disabled", name="Disabled", status="available", enabled=False),
        "offline": AgentCapability(id="offline", name="Offline", status="unavailable", enabled=True),
    }

    assert [agent.id for agent in registry.get_available_agents()] == ["enabled"]


def test_discovery_scope_is_bounded():
    from backend.services.agent_discovery import AgentDiscovery

    discovery = AgentDiscovery()
    discovery._scan_scope = {
        "filesystem_scan": "bounded",
        "path_commands": ["claude"],
    }
    discovery._scanned = True

    scope = discovery.get_scan_scope()
    assert scope["filesystem_scan"] == "bounded"
    assert "/" not in scope["path_commands"]
