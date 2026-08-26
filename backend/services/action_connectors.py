"""Governed connectors for post-acceptance Boss actions.

Only a local simulator is registered by default.  Real integrations must be
registered explicitly in a future deployment and must keep the same approval
and receipt contract.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
from datetime import datetime, timezone
from typing import Any, Dict, Protocol
from urllib.parse import urlparse

import httpx


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


class WebhookActionConnector:
    """Explicitly configured HTTPS webhook for one approved external action."""

    connector_id = "webhook"

    def __init__(self, endpoint: str, allowed_hosts: set[str], token: str = ""):
        self._endpoint = endpoint.rstrip("/")
        self._allowed_hosts = allowed_hosts
        self._token = token

    @classmethod
    def from_environment(cls) -> "WebhookActionConnector | None":
        endpoint = os.getenv("ACO_WEBHOOK_ACTION_URL", "").strip()
        allowed_hosts = {
            host.strip().lower()
            for host in os.getenv("ACO_WEBHOOK_ACTION_ALLOWED_HOSTS", "").split(",")
            if host.strip()
        }
        parsed = urlparse(endpoint)
        hostname = (parsed.hostname or "").lower()
        if (
            parsed.scheme != "https"
            or not hostname
            or parsed.username
            or parsed.password
            or parsed.fragment
            or hostname not in allowed_hosts
        ):
            return None
        return cls(endpoint, allowed_hosts, os.getenv("ACO_WEBHOOK_ACTION_TOKEN", ""))

    def describe(self) -> Dict[str, Any]:
        hostname = urlparse(self._endpoint).hostname or ""
        return {
            "connector_id": self.connector_id,
            "display_name": "受控 Webhook",
            "mode": "external",
            "configured": True,
            "requires_human_approval": True,
            "requires_preflight": True,
            "external_side_effects": True,
            "credential_requirements": [
                {
                    "environment_variable": "ACO_WEBHOOK_ACTION_TOKEN",
                    "required": False,
                    "note": "凭据仅从运行环境读取，不得写入动作载荷。",
                }
            ],
            "target_host": hostname,
            "note": "仅向已配置白名单中的 HTTPS 主机发送已批准的动作。",
        }

    def preflight(self, action: Dict[str, Any]) -> Dict[str, Any]:
        """Validate local configuration only; preflight never contacts the endpoint."""
        hostname = (urlparse(self._endpoint).hostname or "").lower()
        ready = bool(hostname and hostname in self._allowed_hosts)
        return {
            "connector_id": self.connector_id,
            "ready": ready,
            "external_side_effects": True,
            "action_type": action.get("action_type", ""),
            "target_host": hostname,
            "checked_at": datetime.now(timezone.utc).isoformat(),
            "checks": [
                {
                    "name": "https_endpoint",
                    "passed": self._endpoint.startswith("https://"),
                    "detail": "Webhook endpoint uses HTTPS.",
                },
                {
                    "name": "host_allowlist",
                    "passed": ready,
                    "detail": "Endpoint host is explicitly allowlisted.",
                },
                {
                    "name": "non_mutating_preflight",
                    "passed": True,
                    "detail": "Preflight validates configuration locally and does not contact the endpoint.",
                },
            ],
        }

    def execute(self, action: Dict[str, Any]) -> Dict[str, Any]:
        hostname = (urlparse(self._endpoint).hostname or "").lower()
        if hostname not in self._allowed_hosts:
            raise ValueError("Webhook endpoint host is not allowlisted")

        payload = action.get("payload") or {}
        payload_json = json.dumps(payload, ensure_ascii=False, sort_keys=True, default=str)
        request_body = {
            "event_id": action.get("action_id", ""),
            "event_type": action.get("action_type", ""),
            "mission_id": action.get("mission_id", ""),
            "summary": action.get("summary", ""),
            "payload": payload,
        }
        headers = {
            "Content-Type": "application/json",
            "Idempotency-Key": str(action.get("action_id", "")),
            "User-Agent": "AI-Company-OS/1.5",
        }
        if self._token:
            headers["Authorization"] = f"Bearer {self._token}"

        with httpx.Client(timeout=15, follow_redirects=False, proxy=None, trust_env=False) as client:
            response = client.post(self._endpoint, json=request_body, headers=headers)
            response.raise_for_status()
        return {
            "connector_id": self.connector_id,
            "delivered": True,
            "external_side_effects": True,
            "action_type": action.get("action_type", ""),
            "target_host": hostname,
            "status_code": response.status_code,
            "request_id": response.headers.get("x-request-id", ""),
            "payload_sha256": hashlib.sha256(payload_json.encode("utf-8")).hexdigest(),
            "executed_at": datetime.now(timezone.utc).isoformat(),
        }


def _configured_connectors() -> Dict[str, ActionConnector]:
    connectors: Dict[str, ActionConnector] = {
        LocalSimulationConnector.connector_id: LocalSimulationConnector(),
    }
    webhook = WebhookActionConnector.from_environment()
    if webhook:
        connectors[webhook.connector_id] = webhook
    return connectors


def get_action_connector(connector_id: str) -> ActionConnector:
    connectors = _configured_connectors()
    try:
        return connectors[connector_id]
    except KeyError as exc:
        raise ValueError(f"Unsupported action connector: {connector_id}") from exc


def list_action_connectors() -> list[Dict[str, Any]]:
    connectors = _configured_connectors()
    return [connectors[connector_id].describe() for connector_id in sorted(connectors)]
