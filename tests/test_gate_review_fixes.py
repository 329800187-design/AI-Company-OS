"""Regression tests for Codex gate review findings

1. Research tasks must require browser automation approval (OpenClawAgent)
2. Malformed website/code outputs must fail, not pass as partial (ResultVerifier)
3. Marketing fallback must populate missing_evidence via listing_pack threshold
4. listing_pack evidence gate passes when own or upstream evidence is sufficient
5. Website output missing <head> or <body> must hard-fail
"""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest
from unittest.mock import patch, MagicMock


# ════════════════════════════════════════════════════════════════
# Finding 1: Research tasks bypass browser approval
# ════════════════════════════════════════════════════════════════

class TestResearchBrowserApproval:
    """Research/deep_research must be blocked when allow_browser_automation=False"""

    def _make_agent(self, allow_browser: bool = False):
        from agents.openclaw_agent.agent import OpenClawAgent
        agent = OpenClawAgent(allow_browser_automation=allow_browser)
        return agent

    def test_research_blocked_without_approval(self):
        agent = self._make_agent(allow_browser=False)
        task = {"task_id": "t1", "task_type": "research", "goal": "Find competitors"}
        result = agent.run(task)
        assert result.get("blocked") is True or "审批" in str(result.get("error", "")) \
            or "授权" in str(result.get("error", "")) or result.get("ok") is False

    def test_deep_research_blocked_without_approval(self):
        agent = self._make_agent(allow_browser=False)
        task = {"task_id": "t2", "task_type": "deep_research", "goal": "Deep market analysis"}
        result = agent.run(task)
        assert result.get("blocked") is True or result.get("ok") is False

    def test_research_allowed_with_approval(self):
        """When approved, research should proceed (may fail for other reasons, but not blocked)"""
        agent = self._make_agent(allow_browser=True)
        task = {"task_id": "t3", "task_type": "research", "goal": "test"}
        result = agent.run(task)
        # Should not be blocked by browser approval — may fail due to missing Playwright etc.
        assert result.get("blocked") is not True

    def test_verify_blocked_without_approval(self):
        agent = self._make_agent(allow_browser=False)
        task = {"task_id": "t5", "task_type": "verify", "goal": "fact check claims"}
        result = agent.run(task)
        assert result.get("blocked") is True or result.get("ok") is False

    def test_browser_still_blocked_without_approval(self):
        """Existing browser task types should still be blocked"""
        agent = self._make_agent(allow_browser=False)
        task = {"task_id": "t4", "task_type": "browser_scrape", "goal": "scrape"}
        result = agent.run(task)
        assert result.get("blocked") is True or result.get("ok") is False


# ════════════════════════════════════════════════════════════════
# Finding 2: Malformed website/code outputs pass as partial
# ════════════════════════════════════════════════════════════════

class TestResultVerifierStrictArtifact:
    """Website and code tasks must fail when output is wrong type"""

    def setup_method(self):
        from backend.services.result_verifier import ResultVerifier
        self.verifier = ResultVerifier()

    # ── Website ──

    def test_website_non_html_fails(self):
        result = self.verifier.verify("website", {
            "final_answer": "这是一个关于如何搭建网站的说明文档，包含一些步骤和建议。",
        })
        assert result["passed"] is False
        assert result["qa_status"] == "failed"

    def test_website_valid_html_passes(self):
        result = self.verifier.verify("website", {
            "final_answer": "<!DOCTYPE html><html><head><style>body{}</style></head><body><h1>Hello</h1></body></html>",
        })
        assert result["passed"] is True

    def test_website_empty_fails(self):
        result = self.verifier.verify("website", {"final_answer": ""})
        assert result["passed"] is False

    # ── Code ──

    def test_code_prose_fails(self):
        result = self.verifier.verify("code", {
            "final_answer": "你需要安装 Python 3.12，然后配置虚拟环境，安装依赖包即可运行。",
        })
        assert result["passed"] is False
        assert result["qa_status"] == "failed"

    def test_code_real_code_passes(self):
        result = self.verifier.verify("code", {
            "final_answer": "def hello():\n    return 'world'\nimport os",
        })
        assert result["passed"] is True
        assert result["has_code"] is True

    def test_code_empty_fails(self):
        result = self.verifier.verify("code", {"final_answer": ""})
        assert result["passed"] is False

    def test_code_env_setup_without_code_fails(self):
        result = self.verifier.verify("code", {
            "final_answer": "安装说明：先安装 configure 环境，然后 setup 依赖，总共不到200字符",
        })
        assert result["passed"] is False


# ════════════════════════════════════════════════════════════════
# Finding 3: Marketing fallback missing_evidence empty
# ════════════════════════════════════════════════════════════════

class TestMarketingFallbackEvidence:
    """Marketing fallback must populate missing_evidence using listing_pack threshold"""

    def test_marketing_module_maps_to_listing_pack(self):
        from backend.services.boss_execution_providers import build_fallback_structured_output
        result = build_fallback_structured_output(
            module_id="marketing",
            provider_reason="Hermes timeout",
            warnings=["slow"],
        )
        assert result["evidence_gate_passed"] is False
        assert result["status"] == "partial"
        # marketing → listing_pack threshold → min_evidence=1 → should have missing_evidence
        assert len(result["missing_evidence"]) > 0, \
            "Marketing fallback must include missing_evidence (listing_pack requires ≥1 evidence)"

    def test_market_module_still_works(self):
        from backend.services.boss_execution_providers import build_fallback_structured_output
        result = build_fallback_structured_output(
            module_id="market",
            provider_reason="Hermes failed",
        )
        assert result["evidence_gate_passed"] is False
        assert len(result["missing_evidence"]) > 0

    def test_competitor_analysis_module_still_works(self):
        from backend.services.boss_execution_providers import build_fallback_structured_output
        result = build_fallback_structured_output(
            module_id="competitor_analysis",
            provider_reason="Hermes failed",
        )
        assert result["evidence_gate_passed"] is False
        assert len(result["missing_evidence"]) > 0


# ════════════════════════════════════════════════════════════════
# Finding 4: listing_pack evidence gate bypass via self-generated evidence
# ════════════════════════════════════════════════════════════════

class TestListingPackEvidenceGate:
    """listing_pack passes when combined (own + upstream) evidence meets min_evidence=1.
    Fails only when neither own nor upstream evidence is present."""

    def test_listing_pack_fails_with_no_evidence_at_all(self):
        """listing_pack with no own evidence and no prev_results should fail"""
        from backend.services.boss_execution_providers import check_evidence_gate
        result = check_evidence_gate(
            "listing_pack",
            evidence=[],
            prev_results=None,
        )
        assert result["passed"] is False
        assert any("evidence 不足" in m for m in result["missing"])

    def test_listing_pack_fails_with_empty_own_and_empty_prev(self):
        """listing_pack should fail when own evidence is empty and prev_results
        exist but contain no evidence items"""
        from backend.services.boss_execution_providers import check_evidence_gate
        prev_results = {
            "market": {
                "structured_output": {
                    "evidence": [],  # empty upstream evidence
                }
            }
        }
        result = check_evidence_gate(
            "listing_pack",
            evidence=[],
            prev_results=prev_results,
        )
        assert result["passed"] is False
        assert any("evidence 不足" in m for m in result["missing"])

    def test_listing_pack_passes_with_own_evidence_only(self):
        """listing_pack should pass when own evidence alone is sufficient,
        even without any upstream evidence"""
        from backend.services.boss_execution_providers import check_evidence_gate
        result = check_evidence_gate(
            "listing_pack",
            evidence=[{"title": "self-generated", "url": "https://example.com"}],
            prev_results=None,
        )
        assert result["passed"] is True
        assert len(result["missing"]) == 0

    def test_listing_pack_passes_with_prev_evidence_only(self):
        """listing_pack should pass when upstream evidence alone is sufficient"""
        from backend.services.boss_execution_providers import check_evidence_gate
        prev_results = {
            "market": {
                "structured_output": {
                    "evidence": [
                        {"title": "Source 1", "url": "https://real.com/1"},
                    ],
                }
            }
        }
        result = check_evidence_gate(
            "listing_pack",
            evidence=[],
            prev_results=prev_results,
        )
        assert result["passed"] is True
        assert len(result["missing"]) == 0

    def test_listing_pack_passes_with_combined_evidence(self):
        """listing_pack should pass when combined own + upstream evidence is sufficient"""
        from backend.services.boss_execution_providers import check_evidence_gate
        prev_results = {
            "market": {
                "structured_output": {
                    "evidence": [],
                }
            },
            "competitor_analysis": {
                "structured_output": {
                    "evidence": [],
                }
            },
        }
        result = check_evidence_gate(
            "listing_pack",
            evidence=[
                {"title": "Source 1", "url": "https://example.com/1"},
                {"title": "Source 2", "url": "https://example.com/2"},
            ],
            prev_results=prev_results,
        )
        assert result["passed"] is True
        assert len(result["missing"]) == 0


# ════════════════════════════════════════════════════════════════
# Finding 5: Website output missing <head> or <body> passes
# ════════════════════════════════════════════════════════════════

class TestWebsiteMissingCoreTags:
    """Website output missing <head> or <body> must hard-fail"""

    def setup_method(self):
        from backend.services.result_verifier import ResultVerifier
        self.verifier = ResultVerifier()

    def test_html_without_head_fails(self):
        result = self.verifier.verify("website", {
            "final_answer": "<!DOCTYPE html><html><body><h1>Hello</h1></body></html>",
        })
        assert result["passed"] is False
        assert result["qa_status"] == "failed"

    def test_html_without_body_fails(self):
        result = self.verifier.verify("website", {
            "final_answer": "<!DOCTYPE html><html><head><style>body{}</style></head></html>",
        })
        assert result["passed"] is False
        assert result["qa_status"] == "failed"

    def test_html_without_both_head_and_body_fails(self):
        result = self.verifier.verify("website", {
            "final_answer": "<!DOCTYPE html><html><p>Hello</p></html>",
        })
        assert result["passed"] is False
        assert result["qa_status"] == "failed"

    def test_html_with_head_and_body_passes(self):
        result = self.verifier.verify("website", {
            "final_answer": "<!DOCTYPE html><html><head><style>body{}</style></head><body><h1>Hello</h1></body></html>",
        })
        assert result["passed"] is True

    def test_html_with_head_no_style_is_partial(self):
        """Missing style is advisory in non-strict: passed=True but qa_status=partial"""
        result = self.verifier.verify("website", {
            "final_answer": "<!DOCTYPE html><html><head><title>T</title></head><body><p>Hi</p></body></html>",
        })
        assert result["passed"] is True
        assert result["qa_status"] == "partial"

    def test_pipeline_rejects_broken_html(self):
        """Verify that pipeline_router's check on passed=False would reject broken HTML"""
        from backend.services.result_verifier import ResultVerifier
        verifier = ResultVerifier()
        broken = verifier.verify("website", {
            "final_answer": "<!DOCTYPE html><html><h1>No head or body</h1></html>",
        })
        # pipeline_router checks: if not verification.get("passed"): reject
        assert broken["passed"] is False, \
            "Broken HTML without <head>/<body> must be rejected by pipeline_router"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
