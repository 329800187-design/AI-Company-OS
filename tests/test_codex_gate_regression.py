"""Regression tests for Codex narrow gate findings

Issue 1: auto_run and allow_browser_automation must be persisted
Issue 2: accept_mission must allow pending_review status
Issue 3: strict verify mode must reject partial results
"""
import sys
import os
import json
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest
from unittest.mock import patch, MagicMock


# ═══════════════════════════════════════════════════════════════
# Issue 1: auto_run / allow_browser_automation persistence
# ═══════════════════════════════════════════════════════════════

class TestIssue1FlagsPersistence:
    """auto_run and allow_browser_automation must be visible, not silently dropped."""

    @pytest.fixture
    def service(self):
        from backend.services.boss_command_center import BossCommandCenterService
        return BossCommandCenterService()

    def test_allow_browser_automation_persisted_on_create(self, service):
        """allow_browser_automation=True is stored and retrievable from mission."""
        mission = service.create_mission("browser test", allow_browser_automation=True)
        mid = mission["mission_id"]

        fetched = service.get_mission(mid)
        assert fetched["allow_browser_automation"] is True

    def test_allow_browser_automation_default_false(self, service):
        """Default allow_browser_automation is False."""
        mission = service.create_mission("default test")
        fetched = service.get_mission(mission["mission_id"])
        assert fetched["allow_browser_automation"] is False

    def test_auto_run_logged_in_event(self, service):
        """auto_run flag is logged in mission_created event payload."""
        mission = service.create_mission("auto_run log test", auto_run=True)
        events = service.get_events(mission["mission_id"])
        created = [e for e in events if e["type"] == "mission_created"]
        assert len(created) == 1
        assert created[0]["payload"]["auto_run"] is True

    def test_allow_browser_automation_logged_in_event(self, service):
        """allow_browser_automation flag is logged in mission_created event payload."""
        mission = service.create_mission("browser log test", allow_browser_automation=True)
        events = service.get_events(mission["mission_id"])
        created = [e for e in events if e["type"] == "mission_created"]
        assert len(created) == 1
        assert created[0]["payload"]["allow_browser_automation"] is True

    def test_from_template_preserves_allow_browser(self, service):
        """create_mission_from_template passes allow_browser_automation through."""
        mission = service.create_mission_from_template(
            "xianyu_listing_pack",
            allow_browser_automation=True,
        )
        assert mission is not None
        fetched = service.get_mission(mission["mission_id"])
        assert fetched["allow_browser_automation"] is True


# ═══════════════════════════════════════════════════════════════
# Issue 2: accept_mission from pending_review
# ═══════════════════════════════════════════════════════════════

class TestIssue2AcceptFromPendingReview:
    """accept_mission must allow pending_review → done transition."""

    @pytest.fixture
    def service(self):
        from backend.services.boss_command_center import BossCommandCenterService
        return BossCommandCenterService()

    def test_accept_rejected_from_pending_review(self, service):
        """v2: pending_review → accept → rejected (mission not executed yet, no results to accept)."""
        mission = service.create_mission("accept pending_review test")
        mid = mission["mission_id"]
        assert mission["status"] == "pending_review"

        result = service.accept_mission(mid, comment="skip execution")
        # v2: pending_review cannot be accepted — must run first
        assert result["status"] == "pending_review"

    def test_accept_succeeds_from_ready_for_review(self, service):
        """ready_for_review → accept → done (existing behavior preserved)."""
        mission = service.create_mission("accept ready test")
        mid = mission["mission_id"]

        from backend.database.database import get_db
        with get_db() as db:
            db.execute("UPDATE boss_missions SET status='ready_for_review' WHERE mission_id=?", (mid,))
            db.commit()

        result = service.accept_mission(mid)
        assert result["status"] == "done"

    def test_accept_succeeds_from_partial(self, service):
        """partial → accept → done (existing behavior preserved)."""
        mission = service.create_mission("accept partial test")
        mid = mission["mission_id"]

        from backend.database.database import get_db
        with get_db() as db:
            db.execute("UPDATE boss_missions SET status='partial' WHERE mission_id=?", (mid,))
            db.commit()

        result = service.accept_mission(mid)
        assert result["status"] == "done"

    def test_accept_still_rejects_running(self, service):
        """running → accept is rejected."""
        mission = service.create_mission("running reject test")
        mid = mission["mission_id"]

        from backend.database.database import get_db
        with get_db() as db:
            db.execute("UPDATE boss_missions SET status='running' WHERE mission_id=?", (mid,))
            db.commit()

        result = service.accept_mission(mid)
        assert result["status"] == "running"

    def test_accept_still_rejects_failed(self, service):
        """failed → accept is rejected."""
        mission = service.create_mission("failed reject test")
        mid = mission["mission_id"]

        from backend.database.database import get_db
        with get_db() as db:
            db.execute("UPDATE boss_missions SET status='failed' WHERE mission_id=?", (mid,))
            db.commit()

        result = service.accept_mission(mid)
        assert result["status"] == "failed"


# ═══════════════════════════════════════════════════════════════
# Issue 3: strict verify mode
# ═══════════════════════════════════════════════════════════════

LONG_TEXT = "A" * 200 + " 结论：这是一个有内容的结果。"
SOURCES_OK = [{"title": "a", "url": "https://a.com"}, {"title": "b", "url": "https://b.com"}]
# Data analysis text long enough (>=50 chars) to pass the content-length guard
# and trigger the "partial" path (no input data rows/columns)
DATA_TEXT = "分析结果包含统计信息：经过对全部数据的统计分析，得出平均值为123.45，总计为4567，最大值为890，最小值为12。以上为本次数据分析的核心指标汇总结果。"


class TestIssue3StrictVerifyMode:
    """strict=True must make partial results return passed=False."""

    @pytest.fixture
    def verifier(self):
        from backend.services.result_verifier import get_result_verifier
        return get_result_verifier()

    # ── default (non-strict) behavior preserved ──

    def test_research_partial_non_strict_passed_true(self, verifier):
        """Non-strict: partial still returns passed=True (advisory mode)."""
        r = verifier.verify("research", {"final_answer": LONG_TEXT, "sources": []})
        assert r["passed"] is True
        assert r["qa_status"] == "partial"

    def test_marketing_partial_non_strict_passed_true(self, verifier):
        """Non-strict: partial still returns passed=True (advisory mode)."""
        r = verifier.verify("marketing", {"final_answer": LONG_TEXT, "sources": []})
        assert r["passed"] is True
        assert r["qa_status"] == "partial"

    def test_image_partial_non_strict_passed_true(self, verifier):
        """Non-strict: image with small file → partial, still passed=True."""
        import tempfile
        # Create a small file (< 10KB) to trigger partial
        with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as f:
            f.write(b"x" * 5000)
            path = f.name
        try:
            r = verifier.verify("image", {
                "deliverables": {"image_path": path}
            })
            assert r["passed"] is True
            assert r["qa_status"] == "partial"
        finally:
            os.unlink(path)

    def test_data_partial_non_strict_passed_true(self, verifier):
        """Non-strict: data with content but no input data → partial, still passed=True."""
        r = verifier.verify("data", {
            "final_answer": DATA_TEXT,
            "deliverables": {"rows": 0, "columns": 0}
        })
        assert r["passed"] is True
        assert r["qa_status"] == "partial"

    # ── strict mode ──

    def test_research_partial_strict_passed_false(self, verifier):
        """Strict: partial research → passed=False."""
        r = verifier.verify("research", {"final_answer": LONG_TEXT, "sources": []}, strict=True)
        assert r["passed"] is False
        assert r["qa_status"] == "partial"

    def test_research_pass_strict_passed_true(self, verifier):
        """Strict: full pass research → passed=True."""
        r = verifier.verify("research", {"final_answer": LONG_TEXT, "sources": SOURCES_OK}, strict=True)
        assert r["passed"] is True
        assert r["qa_status"] == "pass"

    def test_research_failed_still_false_in_strict(self, verifier):
        """Strict: failed research → passed=False."""
        r = verifier.verify("research", {"final_answer": "", "sources": []}, strict=True)
        assert r["passed"] is False
        assert r["qa_status"] == "failed"

    def test_marketing_partial_strict_passed_false(self, verifier):
        """Strict: partial marketing → passed=False."""
        r = verifier.verify("marketing", {"final_answer": LONG_TEXT, "sources": []}, strict=True)
        assert r["passed"] is False
        assert r["qa_status"] == "partial"

    def test_image_partial_strict_passed_false(self, verifier):
        """Strict: image with small file → partial → passed=False."""
        import tempfile
        with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as f:
            f.write(b"x" * 5000)
            path = f.name
        try:
            r = verifier.verify("image", {
                "deliverables": {"image_path": path}
            }, strict=True)
            assert r["passed"] is False
            assert r["qa_status"] == "partial"
        finally:
            os.unlink(path)

    def test_data_partial_strict_passed_false(self, verifier):
        """Strict: data with no input data → partial → passed=False."""
        r = verifier.verify("data", {
            "final_answer": DATA_TEXT,
            "deliverables": {"rows": 0, "columns": 0}
        }, strict=True)
        assert r["passed"] is False
        assert r["qa_status"] == "partial"

    def test_website_partial_strict_passed_false(self, verifier):
        """Strict: website without style → partial → passed=False."""
        r = verifier.verify("website", {
            "final_answer": "<!doctype html><html><head></head><body>content</body></html>"
        }, strict=True)
        assert r["passed"] is False
        assert r["qa_status"] == "partial"

    def test_website_pass_strict_passed_true(self, verifier):
        """Strict: complete website → passed=True."""
        r = verifier.verify("website", {
            "final_answer": "<!doctype html><html><head><style>.x{}</style></head><body>content</body></html>"
        }, strict=True)
        assert r["passed"] is True
        assert r["qa_status"] == "pass"


# ═══════════════════════════════════════════════════════════════
# Issue 1 (new): Browser-approval path — effective permission in prompts
# ═══════════════════════════════════════════════════════════════


class TestBrowserApprovalPromptBuilders:
    """When is_browser_automation_allowed() approves via config/env,
    prompt builders should receive browser_allowed=True even if the
    request flag is False."""

    def _make_provider(self):
        from backend.services.boss_execution_providers import HermesExecutionProvider
        return HermesExecutionProvider()

    def test_execute_market_research_passes_effective_permission(self):
        """execute_market_research should compute effective permission, not pass raw flag."""
        provider = self._make_provider()
        captured = {}
        original_build = provider._build_market_research_prompt

        def spy_build(goal, context=None, browser_allowed=False):
            captured["browser_allowed"] = browser_allowed
            return original_build(goal, context, browser_allowed=browser_allowed)

        provider._build_market_research_prompt = spy_build

        with patch("backend.services.boss_execution_providers.is_browser_automation_allowed", return_value=True):
            with patch.object(provider, "_execute_hermes_cli") as mock_cli:
                mock_cli.return_value = {"ok": False, "blocked": True, "error": "test"}
                provider.execute_market_research("test", allow_browser_automation=False)

        assert captured.get("browser_allowed") is True, (
            "Prompt builder should receive effective permission (True), not raw request flag (False)"
        )

    def test_execute_competitor_analysis_passes_effective_permission(self):
        """execute_competitor_analysis should compute effective permission."""
        provider = self._make_provider()
        captured = {}
        original_build = provider._build_competitor_analysis_prompt

        def spy_build(goal, competitors=None, context=None, browser_allowed=False):
            captured["browser_allowed"] = browser_allowed
            return original_build(goal, competitors, context, browser_allowed=browser_allowed)

        provider._build_competitor_analysis_prompt = spy_build

        with patch("backend.services.boss_execution_providers.is_browser_automation_allowed", return_value=True):
            with patch.object(provider, "_execute_hermes_cli") as mock_cli:
                mock_cli.return_value = {"ok": False, "blocked": True, "error": "test"}
                provider.execute_competitor_analysis("test", allow_browser_automation=False)

        assert captured.get("browser_allowed") is True, (
            "Prompt builder should receive effective permission (True), not raw request flag (False)"
        )

    def test_execute_listing_pack_passes_effective_permission(self):
        """execute_listing_pack should compute effective permission."""
        provider = self._make_provider()
        captured = {}
        original_build = provider._build_listing_pack_prompt

        def spy_build(goal, competitors=None, pricing=None, context=None, browser_allowed=False):
            captured["browser_allowed"] = browser_allowed
            return original_build(goal, competitors, pricing, context, browser_allowed=browser_allowed)

        provider._build_listing_pack_prompt = spy_build

        with patch("backend.services.boss_execution_providers.is_browser_automation_allowed", return_value=True):
            with patch.object(provider, "_execute_hermes_cli") as mock_cli:
                mock_cli.return_value = {"ok": False, "blocked": True, "error": "test"}
                provider.execute_listing_pack("test", allow_browser_automation=False)

        assert captured.get("browser_allowed") is True, (
            "Prompt builder should receive effective permission (True), not raw request flag (False)"
        )

    def test_market_research_prompt_draft_when_not_approved(self):
        """When not approved, market research prompt should instruct draft mode."""
        provider = self._make_provider()
        prompt = provider._build_market_research_prompt(
            "test goal", context={}, browser_allowed=False
        )
        assert "浏览器自动化未授权" in prompt or "未授权" in prompt


# ═══════════════════════════════════════════════════════════════
# Issue 2 (new): listing_pack evidence gate — own evidence counts
# ═══════════════════════════════════════════════════════════════


class TestListingPackEvidenceGate:
    """listing_pack gate should accept when either own evidence or prev_results evidence
    is sufficient, not reject a valid listing_pack with real own evidence."""

    def test_own_evidence_satisfies_gate(self):
        """listing_pack with its own evidence should pass even without prev_results."""
        from backend.services.boss_execution_providers import check_evidence_gate
        own_evidence = [{"title": "Source 1", "url": "https://example.com/1"}]
        result = check_evidence_gate("listing_pack", evidence=own_evidence, prev_results=None)
        assert result["passed"] is True

    def test_no_evidence_fails_gate(self):
        """listing_pack with no evidence and no prev_results should fail."""
        from backend.services.boss_execution_providers import check_evidence_gate
        result = check_evidence_gate("listing_pack", evidence=[], prev_results=None)
        assert result["passed"] is False
        assert any("evidence 不足" in m for m in result["missing"])

    def test_prev_results_satisfy_gate(self):
        """listing_pack should still pass with prev_results evidence alone."""
        from backend.services.boss_execution_providers import check_evidence_gate
        prev_results = {
            "market": {
                "structured_output": {
                    "evidence": [{"title": "Prev Source", "url": "https://prev.com/1"}]
                }
            }
        }
        result = check_evidence_gate("listing_pack", evidence=[], prev_results=prev_results)
        assert result["passed"] is True

    def test_combined_evidence_satisfies_gate(self):
        """listing_pack with some own + some prev evidence should pass."""
        from backend.services.boss_execution_providers import check_evidence_gate
        prev_results = {
            "market": {
                "structured_output": {
                    "evidence": [{"title": "Prev Source", "url": "https://prev.com/1"}]
                }
            }
        }
        own_evidence = [{"title": "Own Source", "url": "https://own.com/1"}]
        result = check_evidence_gate("listing_pack", evidence=own_evidence, prev_results=prev_results)
        assert result["passed"] is True

    def test_market_gate_still_requires_own_evidence(self):
        """market module gate should NOT accept prev_results — only own evidence."""
        from backend.services.boss_execution_providers import check_evidence_gate
        prev_results = {
            "some_module": {
                "structured_output": {
                    "evidence": [{"title": "Prev", "url": "https://prev.com/1"}]
                }
            }
        }
        # market has 0 own evidence, prev_results shouldn't matter
        result = check_evidence_gate("market", evidence=[], prev_results=prev_results)
        assert result["passed"] is False


# ═══════════════════════════════════════════════════════════════
# Issue 3 (new): Strict verifier wired into LocalAgentRuntime
# ═══════════════════════════════════════════════════════════════


class TestStrictVerifierWiring:
    """LocalAgentRuntime should pass strict=True for website/code tasks."""

    def test_website_task_uses_strict_verifier(self):
        """website task should use strict=True in verifier call."""
        from backend.services.local_agent_runtime import LocalAgentRuntime
        runtime = LocalAgentRuntime()

        captured_calls = []
        original_verify = runtime._result_verifier.verify

        def spy_verify(task_type, result, strict=False):
            captured_calls.append({"task_type": task_type, "strict": strict})
            return {"passed": True, "qa_status": "pass", "score": 100, "issues": []}

        runtime._result_verifier.verify = spy_verify

        mock_adapter = MagicMock()
        mock_adapter.TOOL_NAME = "test_adapter"
        mock_adapter.run.return_value = {
            "ok": True,
            "stdout": "<!DOCTYPE html><html><head><style>.x{}</style></head><body><p>Hello</p></body></html>",
            "result": {"output": "", "sources": [], "deliverables": {}},
            "metadata": {},
        }
        runtime._adapters = {"test_adapter": mock_adapter}
        runtime._fallback_select_adapter = lambda t, m: mock_adapter

        runtime.execute("build a website", context={})

        verifier_calls = [c for c in captured_calls if c["task_type"] == "website"]
        assert len(verifier_calls) > 0, "Verifier should have been called for website task"
        assert verifier_calls[0]["strict"] is True, (
            f"website task should use strict=True, got strict={verifier_calls[0]['strict']}"
        )

    def test_code_task_uses_strict_verifier(self):
        """code task should use strict=True in verifier call."""
        from backend.services.local_agent_runtime import LocalAgentRuntime
        runtime = LocalAgentRuntime()

        captured_calls = []
        original_verify = runtime._result_verifier.verify

        def spy_verify(task_type, result, strict=False):
            captured_calls.append({"task_type": task_type, "strict": strict})
            return {"passed": True, "qa_status": "pass", "score": 100, "issues": []}

        runtime._result_verifier.verify = spy_verify

        mock_adapter = MagicMock()
        mock_adapter.TOOL_NAME = "test_adapter"
        mock_adapter.run.return_value = {
            "ok": True,
            "stdout": "def hello():\n    return 'world'\n",
            "result": {"output": "", "sources": [], "deliverables": {}},
            "metadata": {},
        }
        runtime._adapters = {"test_adapter": mock_adapter}
        runtime._fallback_select_adapter = lambda t, m: mock_adapter

        runtime.execute("write a function", context={})

        verifier_calls = [c for c in captured_calls if c["task_type"] == "code"]
        assert len(verifier_calls) > 0, "Verifier should have been called for code task"
        assert verifier_calls[0]["strict"] is True

    def test_chat_task_uses_advisory_verifier(self):
        """chat task should use strict=False (advisory mode)."""
        from backend.services.local_agent_runtime import LocalAgentRuntime
        runtime = LocalAgentRuntime()

        captured_calls = []
        original_verify = runtime._result_verifier.verify

        def spy_verify(task_type, result, strict=False):
            captured_calls.append({"task_type": task_type, "strict": strict})
            return {"passed": True, "qa_status": "pass", "score": 100, "issues": []}

        runtime._result_verifier.verify = spy_verify

        mock_adapter = MagicMock()
        mock_adapter.TOOL_NAME = "test_adapter"
        mock_adapter.run.return_value = {
            "ok": True,
            "stdout": "Hello, this is a chat response with enough content to pass verification.",
            "result": {"output": "", "sources": [], "deliverables": {}},
            "metadata": {},
        }
        runtime._adapters = {"test_adapter": mock_adapter}
        runtime._fallback_select_adapter = lambda t, m: mock_adapter

        runtime.execute("hello chat", context={})

        chat_calls = [c for c in captured_calls if c["task_type"] == "chat"]
        assert len(chat_calls) > 0
        assert chat_calls[0]["strict"] is False

    def test_boss_mission_skips_verifier(self):
        """Boss missions should skip verifier entirely."""
        from backend.services.local_agent_runtime import LocalAgentRuntime
        runtime = LocalAgentRuntime()

        verify_called = []
        original_verify = runtime._result_verifier.verify

        def spy_verify(task_type, result, strict=False):
            verify_called.append(True)
            return {"passed": True, "qa_status": "pass", "score": 100, "issues": []}

        runtime._result_verifier.verify = spy_verify

        mock_adapter = MagicMock()
        mock_adapter.TOOL_NAME = "test_adapter"
        mock_adapter.run.return_value = {
            "ok": True,
            "stdout": "Boss mission result",
            "result": {"output": "", "sources": [], "deliverables": {}},
            "metadata": {},
        }
        runtime._adapters = {"test_adapter": mock_adapter}
        runtime._fallback_select_adapter = lambda t, m: mock_adapter

        runtime.execute("boss task", context={"boss_mission": True})

        assert len(verify_called) == 0, "Boss mission should skip verifier"
