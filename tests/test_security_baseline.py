"""Long-lived security invariants for the supported Core runtime."""
from __future__ import annotations

import os
import subprocess
import sys

import pytest


def test_authentication_defaults_to_enabled(monkeypatch):
    from backend.middleware import auth_middleware

    class MissingEnvFile:
        @property
        def parent(self):
            return self

        def __truediv__(self, _other):
            return self

        def exists(self):
            return False

    monkeypatch.delenv("AUTH_ENABLED", raising=False)
    monkeypatch.delenv("AUTH_TOKEN", raising=False)
    monkeypatch.setattr(auth_middleware, "Path", lambda *_args: MissingEnvFile())

    with pytest.raises(RuntimeError, match="AUTH_TOKEN must be configured"):
        auth_middleware._load_auth_config()


def test_production_runtime_hides_api_documentation_endpoints():
    code = """
from fastapi.testclient import TestClient
from backend.core_app import app
client = TestClient(app)
assert all(client.get(path).status_code == 404 for path in ('/docs', '/openapi.json', '/redoc'))
"""
    environment = os.environ.copy()
    environment.update({"ENV": "production", "AUTH_TOKEN": "security-baseline-token"})
    result = subprocess.run([sys.executable, "-c", code], env=environment, capture_output=True, text=True)
    assert result.returncode == 0, result.stderr


def test_code_execution_connector_is_inert_by_default():
    from backend.services.action_connectors import get_action_connector

    connector = get_action_connector("code_execution")
    assert connector.describe()["configured"] is False
    assert connector.preflight({"action_type": "run"})["ready"] is False
    with pytest.raises(RuntimeError, match="not enabled"):
        connector.execute({"action_type": "run"})
