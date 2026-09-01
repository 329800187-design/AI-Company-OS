from backend.ai_registry.eligibility import (
    canonical_ready,
    get_canonical_resource,
    is_execution_eligible,
)


def _snapshot(resource_id="agent", ready=True, resource_type="agent"):
    return {"resources": [{
        "resource_id": resource_id,
        "resource_type": resource_type,
        "display_name": resource_id,
        "ready": ready,
        "readiness_reasons": [] if ready else ["not_ready"],
    }]}


def test_missing_or_non_agent_resource_fails_closed():
    assert get_canonical_resource("missing", _snapshot()) is None
    assert get_canonical_resource("provider", _snapshot("provider", True, "llm_provider")) is None
    assert canonical_ready("missing", _snapshot()) is False


def test_execution_eligibility_separates_ready_from_enabled_match_and_policy():
    snapshot = _snapshot()
    assert canonical_ready("agent", snapshot) is True
    assert is_execution_eligible("agent", True, snapshot=snapshot) is True
    assert is_execution_eligible("agent", False, snapshot=snapshot) is False
    assert is_execution_eligible("agent", True, task_match=False, snapshot=snapshot) is False
    assert is_execution_eligible("agent", True, policy_allowed=False, snapshot=snapshot) is False


def test_unready_canonical_resource_is_not_execution_eligible():
    snapshot = _snapshot(ready=False)
    assert canonical_ready("agent", snapshot) is False
    assert is_execution_eligible("agent", True, snapshot=snapshot) is False
