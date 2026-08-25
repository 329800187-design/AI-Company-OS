"""Governed connectors for post-acceptance Boss actions.

Only a local simulator is registered by default.  Real integrations must be
registered explicitly in a future deployment and must keep the same approval
and receipt contract.
"""
from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime, timezone
from typing import Any, Dict, Protocol


_SENSITIVE_PAYLOAD_KEY = re.compile(
    r"(?:api[_-]?key|access[_-]?token|refresh[_-]?token|authorization|password|passwd|secret|credential|private[_-]?key)",
    re.IGNORECASE,
)


def find_sensitive_payload_paths(payload: Any, path: str = "$", depth: int = 0) -> list[str]:
    """Return key paths that look like credentials; values are never inspected or logged."""
    if depth > 8:
        return []
    matches: list[str] = []
    if isinstance(payload, dict):
        for key, value in payload.items():
            key_text = str(key)
            child_path = f"{path}.{key_text}"
            if _SENSITIVE_PAYLOAD_KEY.search(key_text):
                matches.append(child_path)
            if len(matches) < 10:
                matches.extend(find_sensitive_payload_paths(value, child_path, depth + 1))
            if len(matches) >= 10:
                return matches[:10]
    elif isinstance(payload, list):
        for index, value in enumerate(payload):
            matches.extend(find_sensitive_payload_paths(value, f"{path}[{index}]", depth + 1))
            if len(matches) >= 10:
                return matches[:10]
    return matches[:10]


class ActionConnector(Protocol):
    connector_id: str

    def describe(self) -> Dict[str, Any]: ...

    def preflight(self, action: Dict[str, Any]) -> Dict[str, Any]: ...

    def execute(self, action: Dict[str, Any]) -> Dict[str, Any]: ...


class LocalSimulationConnector:
    """Safe default connector that records an execution-shaped receipt only."""

    connector_id = "local_simulation"

    def describe(self) -> Dict[str, Any]:
        return {
            "connector_id": self.connector_id,
            "display_name": "本地模拟",
            "mode": "simulation",
            "configured": True,
            "requires_human_approval": True,
            "requires_preflight": True,
            "external_side_effects": False,
            "credential_requirements": [],
            "note": "仅生成可审计回执，不会联系外部系统。",
        }

    def preflight(self, action: Dict[str, Any]) -> Dict[str, Any]:
        """Validate the execution shape without sending or changing anything."""
        payload = action.get("payload") or {}
        payload_json = json.dumps(payload, ensure_ascii=False, sort_keys=True, default=str)
        return {
            "connector_id": self.connector_id,
            "ready": True,
            "simulated": True,
            "external_side_effects": False,
            "action_type": action.get("action_type", ""),
            "payload_sha256": hashlib.sha256(payload_json.encode("utf-8")).hexdigest(),
            "checked_at": datetime.now(timezone.utc).isoformat(),
            "checks": [
                {"name": "connector_configured", "passed": True, "detail": "Local simulator is available."},
                {"name": "external_side_effects", "passed": True, "detail": "No external system will be contacted."},
            ],
        }

    def execute(self, action: Dict[str, Any]) -> Dict[str, Any]:
        payload = action.get("payload") or {}
        payload_json = json.dumps(payload, ensure_ascii=False, sort_keys=True, default=str)
        return {
            "connector_id": self.connector_id,
            "simulated": True,
            "action_type": action.get("action_type", ""),
            "payload_sha256": hashlib.sha256(payload_json.encode("utf-8")).hexdigest(),
            "executed_at": datetime.now(timezone.utc).isoformat(),
            "message": "Local simulation completed; no external system was contacted.",
        }


_CONNECTORS: Dict[str, ActionConnector] = {
    LocalSimulationConnector.connector_id: LocalSimulationConnector(),
}


def get_action_connector(connector_id: str) -> ActionConnector:
    try:
        return _CONNECTORS[connector_id]
    except KeyError as exc:
        raise ValueError(f"Unsupported action connector: {connector_id}") from exc


def list_action_connectors() -> list[Dict[str, Any]]:
    return [_CONNECTORS[connector_id].describe() for connector_id in sorted(_CONNECTORS)]
