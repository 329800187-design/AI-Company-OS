"""Boss Command Center v2 人工审核闭环防回归测试

覆盖 ad-hoc 验证中的全部 25 项语义：
  create_mission → pending_review, 不自动执行
  accept_mission 拒绝 pending_review 状态
  无结果时 Mission 保持 pending_review
  ResultVerifier advisory 模式（partial 不阻断, 空结果才 failed）
  MODULE_OWNER 覆盖 + ExecutionResult.qa_status
  MissionAcceptRequest schema + accept endpoint

测试层级：
  - Service 层：BossCommandCenterService 直接调用
  - Verifier 层：ResultVerifier 独立验证
  - Executor 层：MODULE_OWNER + ExecutionResult
  - API 层：FastAPI TestClient HTTP 调用
"""
import sys
import os
import json
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest
from unittest.mock import patch, MagicMock


# ── helpers ──────────────────────────────────────────────────

def _make_mock_executor(ok=True, final_answer="", confidence=0.0,
                        warnings=None, used_tools=None, mode="local",
                        error="", next_actions=None, structured_output=None,
                        provider="local_mock", qa_status=""):
    mock_exec = MagicMock()
    mock_result = MagicMock()
    mock_result.ok = ok
    mock_result.final_answer = final_answer
    mock_result.confidence = confidence
    mock_result.warnings = warnings or []
    mock_result.used_tools = used_tools or []
    mock_result.mode = mode
    mock_result.error = error
    mock_result.next_actions = next_actions or []
    mock_result.structured_output = structured_output or {}
    mock_result.provider = provider
    mock_result.qa_status = qa_status
    mock_exec.execute.return_value = mock_result
    return mock_exec


# ═══════════════════════════════════════════════════════════════
# Service 层：Mission 生命周期 v2
# ═══════════════════════════════════════════════════════════════

class TestBossV2MissionLifecycle:
    """v2 Mission 生命周期：pending_review → run → ready_for_review/partial/failed → accept → done"""

    @pytest.fixture
    def service(self):
        from backend.services.boss_command_center import BossCommandCenterService
        return BossCommandCenterService()

    # ── create_mission ──

    def test_create_mission_initial_status_pending_review(self, service):
        """Mission 创建后默认状态为 pending_review"""
        m = service.create_mission("防回归测试")
        assert m["status"] == "pending_review"

    def test_create_mission_all_modules_pending(self, service):
        """创建后 5 个模块全部 pending（非 running/done）"""
        m = service.create_mission("5模块状态")
        statuses = [mod["status"] for mod in m["modules"]]
        assert all(s == "pending" for s in statuses), statuses

    def test_create_mission_does_not_auto_run(self, service):
        """即使 auto_run=True 也不自动执行（v2 已禁用）"""
        m = service.create_mission("不自动跑", auto_run=True)
        # 模块应该全部 pending
        statuses = [mod["status"] for mod in m["modules"]]
        assert all(s == "pending" for s in statuses), statuses
        # mission 应该是 pending_review
        assert m["status"] == "pending_review"

    # ── accept_mission 守卫 ──

    def test_accept_rejects_pending_review(self, service):
        """pending_review 状态的 Mission 不能被 accept"""
        m = service.create_mission("拒绝 accept 测试")
        result = service.accept_mission(m["mission_id"])
        assert result["status"] == "pending_review"

    def test_accept_succeeds_ready_for_review(self, service):
        """ready_for_review 状态的 Mission 可以被 accept → done"""
        m = service.create_mission("accept 成功测试")
        mid = m["mission_id"]

        # 手动把状态设为 ready_for_review
        from backend.database.database import get_db
        with get_db() as db:
            db.execute("UPDATE boss_missions SET status='ready_for_review' WHERE mission_id=?",
                       (mid,))
            db.commit()

        result = service.accept_mission(mid, comment="good")
        assert result["status"] == "done"

    def test_accept_succeeds_partial(self, service):
        """partial 状态的 Mission 也可以被 accept → done"""
        m = service.create_mission("partial accept 测试")
        mid = m["mission_id"]

        from backend.database.database import get_db
        with get_db() as db:
            db.execute("UPDATE boss_missions SET status='partial' WHERE mission_id=?",
                       (mid,))
            db.commit()

        result = service.accept_mission(mid, comment="partial but ok")
        assert result["status"] == "done"

    # ── 无结果时状态保持 ──

    def test_no_result_preserves_pending_review(self, service):
        """_update_mission_status_from_modules 在无结果时保持 pending_review"""
        m = service.create_mission("空结果测试")
        mid = m["mission_id"]
        svc = service
        svc._update_mission_status_from_modules(mid)
        refreshed = svc.get_mission(mid)
        assert refreshed["status"] == "pending_review"


# ═══════════════════════════════════════════════════════════════
# Verifier 层：advisory 模式
# ═══════════════════════════════════════════════════════════════

LONG_TEXT = "A" * 200 + " 结论：这是一个有内容的结果。"

class TestBossV2VerifierAdvisory:
    """v2 ResultVerifier advisory 模式"""

    @pytest.fixture
    def verifier(self):
        from backend.services.result_verifier import get_result_verifier
        return get_result_verifier()

    # ── research ──

    def test_research_content_no_sources_passed_true(self, verifier):
        """有内容但无来源 → passed=True"""
        r = verifier.verify("research", {"final_answer": LONG_TEXT, "sources": []})
        assert r["passed"] is True

    def test_research_content_no_sources_qa_partial(self, verifier):
        """有内容但无来源 → qa_status=partial"""
        r = verifier.verify("research", {"final_answer": LONG_TEXT, "sources": []})
        assert r["qa_status"] == "partial"

    def test_research_content_two_sources_qa_pass(self, verifier):
        """有内容 + 2 个来源 → qa_status=pass"""
        r = verifier.verify("research", {
            "final_answer": LONG_TEXT,
            "sources": [{"title": "a", "url": "https://a.com"},
                         {"title": "b", "url": "https://b.com"}]
        })
        assert r["qa_status"] == "pass"

    # ── marketing ──

    def test_marketing_no_cta_qa_partial(self, verifier):
        """营销内容缺 CTA → qa_status=partial"""
        r = verifier.verify("marketing", {"final_answer": LONG_TEXT, "sources": []})
        assert r["qa_status"] == "partial"

    def test_marketing_no_cta_does_not_block(self, verifier):
        """营销内容缺 CTA → passed=True（不阻断）"""
        r = verifier.verify("marketing", {"final_answer": LONG_TEXT, "sources": []})
        assert r["passed"] is True

    def test_marketing_no_cta_score_below_pass_threshold(self, verifier):
        """营销内容缺 CTA → score 降低到 partial 区间"""
        r = verifier.verify("marketing", {"final_answer": LONG_TEXT, "sources": []})
        assert r["score"] < 80

    # ── empty ──

    def test_empty_content_failed(self, verifier):
        """空结果 → passed=False, qa_status=failed"""
        r = verifier.verify("research", {"final_answer": "", "sources": []})
        assert r["passed"] is False
        assert r["qa_status"] == "failed"


# ═══════════════════════════════════════════════════════════════
# Executor 层：MODULE_OWNER + ExecutionResult
# ═══════════════════════════════════════════════════════════════

class TestBossV2ModuleOwnerAndResult:
    """v2 模块 owner 固定 + ExecutionResult qa_status 字段"""

    def test_module_owner_covers_all_five(self):
        from backend.services.boss_module_executors import MODULE_OWNER
        for mid in ("strategy", "market", "marketing", "landing", "actions"):
            assert mid in MODULE_OWNER, f"Missing: {mid}"

    def test_module_owner_market_is_hermes(self):
        from backend.services.boss_module_executors import MODULE_OWNER
        assert MODULE_OWNER["market"] == "hermes"

    def test_module_owner_others_are_local_heuristic(self):
        from backend.services.boss_module_executors import MODULE_OWNER
        for mid in ("strategy", "marketing", "landing", "actions"):
            assert MODULE_OWNER[mid] == "local_heuristic", f"{mid} owner={MODULE_OWNER[mid]}"

    def test_execution_result_to_dict_includes_qa_status(self):
        from backend.services.boss_module_executors import ExecutionResult
        er = ExecutionResult(ok=True, final_answer="test", qa_status="partial")
        d = er.to_dict()
        assert "qa_status" in d
        assert d["qa_status"] == "partial"

    def test_default_executor_resolves(self):
        from backend.services.boss_module_executors import get_executor
        executor = get_executor("", "strategy")
        assert executor is not None


# ═══════════════════════════════════════════════════════════════
# API 层 + Router
# ═══════════════════════════════════════════════════════════════

class TestBossV2API:
    """v2 API 端点测试"""

    @pytest.fixture(autouse=True)
    def _bypass_rate_limit(self):
        from unittest.mock import patch
        with patch("backend.routers.boss_router.rate_limiter") as mock_rl:
            mock_rl.check.return_value = (True, "")
            yield

    @pytest.fixture(autouse=True)
    def _bypass_governance(self):
        from unittest.mock import patch
        from backend.governance.classifier import ClassificationResult
        with patch("backend.governance.guard.guard_payload") as mock_guard:
            mock_guard.return_value = (False, ClassificationResult(ok=True, confidence=1.0, reason="test bypass"))
            yield

    @pytest.fixture
    def client(self):
        from fastapi.testclient import TestClient
        from backend.app import app
        return TestClient(app, raise_server_exceptions=False)

    # ── MissionAcceptRequest schema ──

    def test_accept_request_schema_exists(self):
        from backend.routers.boss_router import MissionAcceptRequest
        req = MissionAcceptRequest(comment="good")
        assert req.comment == "good"

    def test_accept_request_default_comment_empty(self):
        from backend.routers.boss_router import MissionAcceptRequest
        req = MissionAcceptRequest()
        assert req.comment == ""

    # ── accept endpoint ──

    def test_accept_endpoint_exists(self):
        from backend.routers.boss_router import accept_mission
        assert callable(accept_mission)

    def test_accept_api_returns_200_on_valid(self, client):
        """POST /boss/missions/{id}/accept 对 ready_for_review 返回 200"""
        # 创建后手动设状态为 ready_for_review
        resp = client.post("/boss/missions", json={
            "goal": "accept API 测试",
            "auto_run": False,
        })
        mid = resp.json()["mission_id"]

        from backend.database.database import get_db
        with get_db() as db:
            db.execute("UPDATE boss_missions SET status='ready_for_review' WHERE mission_id=?",
                       (mid,))
            db.commit()

        resp = client.post(f"/boss/missions/{mid}/accept", json={"comment": "ok"})
        assert resp.status_code == 200
        assert resp.json()["status"] == "done"

    def test_accept_api_rejects_pending_review(self, client):
        """POST /boss/missions/{id}/accept 对 pending_review 返回 200 但状态不变"""
        resp = client.post("/boss/missions", json={
            "goal": "accept reject API 测试",
            "auto_run": False,
        })
        mid = resp.json()["mission_id"]

        resp = client.post(f"/boss/missions/{mid}/accept", json={"comment": "try"})
        assert resp.status_code == 200
        # pending_review 不能被 accept
        assert resp.json()["status"] == "pending_review"

    def test_create_mission_api_returns_pending_review(self, client):
        """POST /boss/missions 创建后返回 pending_review"""
        resp = client.post("/boss/missions", json={
            "goal": "API status 测试",
            "auto_run": False,
        })
        assert resp.status_code == 200
        assert resp.json()["status"] == "pending_review"

    def test_create_mission_api_auto_run_does_not_execute(self, client):
        """POST /boss/missions with auto_run=True 仍不执行（v2 禁用）"""
        resp = client.post("/boss/missions", json={
            "goal": "auto_run API 测试",
            "auto_run": True,
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "pending_review"
        # 模块全部 pending
        for mod in data["modules"]:
            assert mod["status"] == "pending", f"{mod['module_id']} status={mod['status']}"
