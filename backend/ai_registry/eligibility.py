"""Centralized execution eligibility checks for canonical Agent resources."""
from typing import Any


def _snapshot(snapshot: dict[str, Any] | None) -> dict[str, Any]:
    if snapshot is not None:
        return snapshot
    from backend.ai_registry import get_registry
    return get_registry().scan_runtime_capabilities()


def get_canonical_resource(agent_id: str, snapshot: dict[str, Any] | None = None) -> dict[str, Any] | None:
    """Return an Agent resource from one snapshot, or None (fail closed)."""
    for resource in _snapshot(snapshot).get("resources", []):
        if resource.get("resource_id") == agent_id and resource.get("resource_type") == "agent":
            return resource
    return None


def canonical_ready(agent_id: str, snapshot: dict[str, Any] | None = None) -> bool:
    resource = get_canonical_resource(agent_id, snapshot)
    return bool(resource and resource.get("ready") is True)


def is_execution_eligible(
    agent_id: str,
    enabled: bool,
    task_match: bool = True,
    capability_match: bool = True,
    policy_allowed: bool = True,
    snapshot: dict[str, Any] | None = None,
) -> bool:
    return bool(
        enabled
        and task_match
        and capability_match
        and policy_allowed
        and canonical_ready(agent_id, snapshot)
    )
