from backend.services.capability_scanner import CapabilityScanner
from backend.services.agent_discovery import AgentDiscovery


def test_scan_exposes_one_canonical_resource_list():
    scanner = CapabilityScanner(ttl_seconds=60)
    result = scanner.scan_all(force=True)

    resources = result["resources"]
    assert resources
    assert {item["resource_type"] for item in resources} <= {
        "agent", "llm_provider", "local_tool", "browser", "local_service"
    }
    assert all("ready" in item and "readiness_reasons" in item for item in resources)


def test_scan_cache_is_reused_until_force_refresh(monkeypatch):
    scanner = CapabilityScanner(ttl_seconds=60)
    calls = {"count": 0}
    original = scanner._scan_tools

    def counted():
        calls["count"] += 1
        return original()

    monkeypatch.setattr(scanner, "_scan_tools", counted)
    scanner.scan_all(force=True)
    scanner.scan_all()

    assert calls["count"] == 1


def test_agent_discovery_projects_machine_agents_from_canonical_snapshot(monkeypatch):
    discovery = AgentDiscovery()
    canonical = {
        "resources": [{
            "resource_id": "claude",
            "resource_type": "agent",
            "display_name": "Claude Code",
            "available": True,
            "configured": True,
            "verified": True,
            "ready": False,
            "readiness_reasons": ["execution_unavailable"],
            "source": "canonical-test",
        }]
    }
    monkeypatch.setattr(
        "backend.ai_registry.registry.get_registry",
        lambda: type("Registry", (), {
            "scan_runtime_capabilities": lambda self, force=False: canonical
        })(),
    )
    monkeypatch.setattr(discovery, "_scan_mcp_servers", lambda: None)
    monkeypatch.setattr(discovery, "_scan_local_agents", lambda: None)
    monkeypatch.setattr(discovery, "_apply_enabled_config", lambda: None)

    agents = discovery.scan_all(force=True)

    assert agents["claude"].source == "canonical_registry"
    assert agents["claude"].status == "available"


def test_planning_candidates_ignore_legacy_status():
    from backend.routers.agent_console_router import planning_candidates
    from backend.services.agent_discovery import AgentCapability

    agent = AgentCapability(
        id="agent", name="Agent", status="available", enabled=True, runnable=False,
        canonical_resource={"resource_id": "agent", "resource_type": "agent", "ready": False},
    )
    assert planning_candidates({"agent": agent}, {"agent": agent.canonical_resource}) == []


def test_llm_binding_projects_bound_provider_readiness(monkeypatch):
    from backend.services.agent_discovery import AgentDiscovery

    snapshot = {"resources": [
        {"resource_id": "provider", "resource_type": "llm_provider", "ready": False,
         "readiness_reasons": ["not_verified"]},
        {"resource_id": "agent", "resource_type": "agent", "ready": False,
         "requires_llm": True, "bound_provider_id": "provider", "readiness_reasons": ["llm_provider_not_verified"]},
    ]}
    discovery = AgentDiscovery()
    monkeypatch.setattr("backend.ai_registry.get_registry", lambda: type("R", (), {
        "scan_runtime_capabilities": lambda self, force=False: snapshot,
    })())
    discovery._project_canonical_agents()
    assert discovery._agents["agent"].llm_binding == {
        "provider_id": "provider", "ready": False, "readiness_reasons": ["not_verified"]
    }
