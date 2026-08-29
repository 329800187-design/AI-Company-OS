from backend.services.capability_scanner import CapabilityScanner


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
