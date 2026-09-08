"""Website execute tests for the A5 LLM-first agent path."""

import os
import sys
from unittest.mock import patch

from fastapi.testclient import TestClient

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from backend.app import app


client = TestClient(app)


def _website_payload(goal="Create a landing page for handmade earrings", task_type="website_draft"):
    return {
        "task_id": "",
        "goal": goal,
        "task_type": task_type,
        "context": {},
        "input": {"goal": goal},
    }


def _post_website_execute(payload):
    with patch(
        "agents.website_agent.agent.WebsiteAgent.call_ai",
        return_value={"ok": False, "error": "No provider available"},
    ):
        return client.post("/agents/website/execute", json=payload)


class TestWebsiteAgentLoad:
    def test_website_agent_in_registry(self):
        from backend.services.agent_loader import AGENT_REGISTRY

        assert "agents.website_agent.agent" in AGENT_REGISTRY
        assert AGENT_REGISTRY["agents.website_agent.agent"] == "WebsiteAgent"

    def test_website_agent_loads_via_loader(self):
        from backend.services.agent_loader import load_agent

        cls = load_agent("agents.website_agent.agent:WebsiteAgent")
        assert cls is not None
        assert cls.AGENT_ID == "website"

    def test_website_agent_instantiate(self):
        from backend.services.agent_loader import load_agent_instance

        agent = load_agent_instance("agents.website_agent.agent", "WebsiteAgent")
        assert agent is not None
        assert agent.AGENT_ID == "website"
        assert agent.DISPLAY_NAME

    def test_website_agent_has_required_capabilities(self):
        from backend.services.agent_loader import load_agent

        cls = load_agent("agents.website_agent.agent:WebsiteAgent")
        assert "website_draft" in cls.CAPABILITIES
        assert "landing_page" in cls.CAPABILITIES

    def test_website_agent_has_required_task_types(self):
        from backend.services.agent_loader import load_agent

        cls = load_agent("agents.website_agent.agent:WebsiteAgent")
        assert "website_draft" in cls.TASK_TYPES
        assert "landing_page" in cls.TASK_TYPES


class TestWebsiteExecuteEndpoint:
    def test_execute_website_returns_agent_run_result(self):
        resp = _post_website_execute(_website_payload())
        assert resp.status_code == 200
        data = resp.json()

        assert "ok" in data
        assert "agent_id" in data
        assert "output" in data
        assert "artifacts" in data
        assert isinstance(data["ok"], bool)
        assert isinstance(data["output"], dict)
        assert isinstance(data["artifacts"], list)

    def test_execute_website_ok_true(self):
        resp = _post_website_execute(_website_payload())
        assert resp.json()["ok"] is True

    def test_execute_website_all_standard_fields(self):
        resp = _post_website_execute(_website_payload())
        data = resp.json()
        required_fields = [
            "ok",
            "mode",
            "agent_id",
            "task_type",
            "summary",
            "structured_output",
            "output",
            "artifacts",
            "warnings",
            "errors",
            "next_actions",
            "metadata",
        ]
        for field in required_fields:
            assert field in data, f"missing field: {field}"

    def test_execute_website_structured_output_has_hero(self):
        resp = _post_website_execute(_website_payload())
        output = resp.json().get("structured_output") or {}

        assert "hero" in output
        assert "headline" in output["hero"]
        assert "subheadline" in output["hero"]
        assert "primary_cta" in output["hero"]

    def test_execute_website_structured_output_has_sections(self):
        resp = _post_website_execute(_website_payload())
        output = resp.json().get("structured_output") or {}

        assert isinstance(output.get("sections"), list)
        assert len(output["sections"]) > 0
        assert "title" in output["sections"][0]
        assert "content" in output["sections"][0]

    def test_execute_website_structured_output_has_seo(self):
        resp = _post_website_execute(_website_payload())
        output = resp.json().get("structured_output") or {}

        assert "seo" in output
        assert "title" in output["seo"]
        assert "description" in output["seo"]
        assert isinstance(output["seo"].get("keywords"), list)

    def test_execute_website_structured_output_has_design_direction(self):
        resp = _post_website_execute(_website_payload())
        output = resp.json().get("structured_output") or {}

        assert "design_direction" in output

    def test_execute_website_fallback_warning(self):
        resp = _post_website_execute(_website_payload())
        data = resp.json()
        meta = data.get("metadata") or {}

        assert meta.get("fallback") is True
        assert meta.get("source") == "template"
        assert meta.get("fallback_reason")
        assert data.get("warnings")
        assert data["structured_output"].get("limitations")

    def test_execute_website_empty_goal_fails(self):
        resp = _post_website_execute(_website_payload(goal=""))
        assert resp.json()["ok"] is False

    def test_execute_website_disabled_agent(self):
        from backend.services.agent_discovery import set_agent_enabled

        set_agent_enabled("website", False)
        try:
            resp = _post_website_execute(_website_payload())
            data = resp.json()
            assert data["ok"] is False
            assert data.get("error") or data.get("message") or data.get("errors")
        finally:
            set_agent_enabled("website", True)

    def test_execute_website_agent_id_correct(self):
        resp = _post_website_execute(_website_payload())
        assert resp.json()["agent_id"] == "website"

    def test_execute_website_different_task_types(self):
        for task_type in ["landing_page", "product_page", "squeeze_page"]:
            resp = _post_website_execute(_website_payload(task_type=task_type))
            data = resp.json()
            output = data.get("structured_output") or {}

            assert data["ok"] is True
            assert "page_goal" in output
            assert output.get("content_type") == "landing_page_copy"


class TestWebsiteGovernanceFallback:
    def test_governance_run_still_works(self):
        resp = client.post(
            "/governance/run",
            json={
                "goal": "Create a Xiaohongshu copy pack for handmade earrings",
                "platform": "xiaohongshu",
                "execute": True,
            },
        )
        data = resp.json()
        assert "run_id" in data
        assert "status" in data
        assert data["status"] == "succeeded"
