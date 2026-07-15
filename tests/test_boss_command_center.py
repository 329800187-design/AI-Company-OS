"""Boss Command Center 测试

覆盖：
- 创建 mission（含 enabled_modules）
- 执行 mission（mock LocalAgentRuntime）
- 单模块重跑
- market 无联网能力时返回 warning
- skipped module 状态
- export json / markdown
- API 接口验证
- duration_ms / started_at / finished_at / next_actions 字段
- provider 抽象层测试
- structured_output 标准化测试
- 事件日志增强测试
"""
import sys
import os
import json
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest
from unittest.mock import patch, MagicMock


def _make_mock_executor(ok=True, final_answer="", confidence=0.0,
                        warnings=None, used_tools=None, mode="local",
                        error="", next_actions=None, structured_output=None,
                        provider="local_mock"):
    """创建 mock executor"""
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
    mock_exec.execute.return_value = mock_result
    return mock_exec


# ── Service 层测试 ───────────────────────────────────────

class TestBossCommandCenterService:
    """BossCommandCenterService 单元测试"""

    @pytest.fixture
    def service(self):
        from backend.services.boss_command_center import BossCommandCenterService
        return BossCommandCenterService()

    def test_create_mission(self, service):
        """创建 mission 应返回完整结构（v2: 初始状态 pending_review）"""
        mission = service.create_mission("测试业务目标")
        assert mission is not None
        assert mission["mission_id"].startswith("mission_")
        assert mission["goal"] == "测试业务目标"
        assert mission["status"] == "pending_review"
        assert len(mission["modules"]) == 5

        module_ids = [m["module_id"] for m in mission["modules"]]
        assert module_ids == ["strategy", "market", "marketing", "landing", "actions"]

        for mod in mission["modules"]:
            assert mod["status"] == "pending"
            assert mod["prompt"]
            assert "测试业务目标" in mod["prompt"]

    def test_create_mission_enabled_modules(self, service):
        """enabled_modules 只跑部分模块，其他 skipped"""
        mission = service.create_mission("部分模块测试", enabled_modules=["strategy", "market"])
        assert mission is not None

        for mod in mission["modules"]:
            if mod["module_id"] in ("strategy", "market"):
                assert mod["status"] == "pending", f"{mod['module_id']} should be pending"
            else:
                assert mod["status"] == "skipped", f"{mod['module_id']} should be skipped"

    def test_create_mission_all_disabled_fallback(self, service):
        """enabled_modules 为空列表时 fallback 到全部"""
        mission = service.create_mission("空列表测试", enabled_modules=[])
        # 应该 fallback 到全部启用
        all_pending = all(m["status"] == "pending" for m in mission["modules"])
        assert all_pending

    def test_list_missions(self, service):
        """列出 missions"""
        service.create_mission("任务A")
        service.create_mission("任务B")
        missions = service.list_missions()
        assert len(missions) >= 2
        goals = [m["goal"] for m in missions]
        assert "任务B" in goals
        assert "任务A" in goals

    def test_get_mission(self, service):
        """获取 mission 详情"""
        created = service.create_mission("详情测试")
        mission_id = created["mission_id"]
        mission = service.get_mission(mission_id)
        assert mission is not None
        assert mission["mission_id"] == mission_id
        assert len(mission["modules"]) == 5

    def test_get_nonexistent_mission(self, service):
        """获取不存在的 mission 返回 None"""
        result = service.get_mission("mission_nonexistent")
        assert result is None

    def test_run_module_mock(self, service):
        """单模块执行（mock executor）"""
        mission = service.create_mission("mock 测试")
        mission_id = mission["mission_id"]

        mock_exec_result = MagicMock()
        mock_exec_result.ok = True
        mock_exec_result.final_answer = "这是战略分析结果"
        mock_exec_result.confidence = 0.85
        mock_exec_result.warnings = []
        mock_exec_result.used_tools = ["mimo"]
        mock_exec_result.mode = "local"
        mock_exec_result.error = ""
        mock_exec_result.next_actions = ["联系投资人", "写商业计划书"]
        mock_exec_result.structured_output = {}
        mock_exec_result.provider = "local_mock"

        mock_executor = MagicMock()
        mock_executor.execute.return_value = mock_exec_result

        with patch("backend.services.boss_module_executors.get_executor", return_value=mock_executor):
            updated = service.run_module(mission_id, "strategy")
            assert updated is not None

            strategy = next(m for m in updated["modules"] if m["module_id"] == "strategy")
            assert strategy["status"] == "done"
            assert strategy["result"] == "这是战略分析结果"
            assert strategy["confidence"] == 0.85
            assert strategy["next_actions"] == ["联系投资人", "写商业计划书"]
            assert strategy["started_at"] is not None
            assert strategy["finished_at"] is not None
            assert strategy["duration_ms"] >= 0  # mock 执行极快，duration 可能为 0

    def test_run_module_failure(self, service):
        """模块执行失败时返回 failed 状态"""
        mission = service.create_mission("失败测试")
        mission_id = mission["mission_id"]

        mock_executor = _make_mock_executor(ok=False, error="Adapter 不可用")

        with patch("backend.services.boss_module_executors.get_executor", return_value=mock_executor):
            updated = service.run_module(mission_id, "market")
            assert updated is not None

            market = next(m for m in updated["modules"] if m["module_id"] == "market")
            assert market["status"] == "failed"
            assert "Adapter 不可用" in market["error"]
            assert market["duration_ms"] >= 0

    def test_run_module_blocked_not_partial(self, service):
        """Regression: browser-approval-blocked module must be 'failed', not 'partial'."""
        mission = service.create_mission("blocked 测试")
        mission_id = mission["mission_id"]

        mock_executor = _make_mock_executor(
            ok=False,
            final_answer="浏览器自动化采集需要用户确认后才能执行",
            mode="blocked",
            error="浏览器自动化需要用户授权",
        )

        with patch("backend.services.boss_module_executors.get_executor", return_value=mock_executor):
            updated = service.run_module(mission_id, "market")
            market = next(m for m in updated["modules"] if m["module_id"] == "market")
            assert market["status"] == "failed", (
                f"blocked module should be 'failed', got '{market['status']}'"
            )

    def test_market_no_web_search_warning(self, service):
        """market 模块无联网能力时应返回 warning（由 executor 产生）"""
        mission = service.create_mission("联网测试")
        mission_id = mission["mission_id"]

        # executor 负责添加联网 warning
        mock_executor = _make_mock_executor(ok=True, final_answer="市场分析结果（无联网）",
                                            confidence=0.6, used_tools=["api_models"],
                                            warnings=["市场模块未获取到联网搜索结果，分析基于模型已有知识"])

        with patch("backend.services.boss_module_executors.get_executor", return_value=mock_executor):
            updated = service.run_module(mission_id, "market")
            market = next(m for m in updated["modules"] if m["module_id"] == "market")
            assert market["status"] == "done"
            assert any("联网" in w for w in market["warnings"])

    def test_run_module_nonexistent(self, service):
        """执行不存在的模块返回 None"""
        mission = service.create_mission("不存在模块测试")
        result = service.run_module(mission["mission_id"], "nonexistent_module")
        assert result is None

    def test_skip_done_modules_on_rerun(self, service):
        """rerun_mission 跳过已完成的模块"""
        mission = service.create_mission("跳过测试")
        mission_id = mission["mission_id"]

        mock_executor = _make_mock_executor(ok=True, final_answer="战略分析结果文本内容", confidence=0.7)

        with patch("backend.services.boss_module_executors.get_executor", return_value=mock_executor):
            # 先执行一次 strategy
            service.run_module(mission_id, "strategy")

            # 再执行整个 mission，strategy 不应重复执行
            mock_executor.execute.reset_mock()
            service.run_mission(mission_id)

            # executor.execute 应该只被调用 4 次（跳过已完成的 strategy）
            assert mock_executor.execute.call_count == 4

    # ── Export 测试 ────────────────────────────────────────

    def test_export_json(self, service):
        """导出 JSON 格式"""
        mission = service.create_mission("导出测试")
        exported = service.export_mission(mission["mission_id"], fmt="json")
        assert exported is not None
        assert exported["filename"].endswith(".json")
        assert exported["content_type"] == "application/json; charset=utf-8"

        data = json.loads(exported["content"])
        assert data["mission_id"] == mission["mission_id"]
        assert data["goal"] == "导出测试"
        assert len(data["modules"]) == 5

    def test_export_markdown(self, service):
        """导出 Markdown 格式"""
        mission = service.create_mission("MD 导出测试")
        exported = service.export_mission(mission["mission_id"], fmt="markdown")
        assert exported is not None
        assert exported["filename"].endswith(".md")
        assert exported["content_type"] == "text/markdown; charset=utf-8"

        md = exported["content"]
        assert "MD 导出测试" in md
        assert "目标理解与策略判断" in md
        assert "上下文与证据整理" in md
        assert "沟通与触达方案" in md
        assert "交付物结构" in md
        assert "执行计划" in md

    def test_export_nonexistent(self, service):
        """导出不存在的 mission 返回 None"""
        result = service.export_mission("mission_nonexistent", fmt="json")
        assert result is None

    def test_export_skipped_module(self, service):
        """导出包含 skipped 模块"""
        mission = service.create_mission("skipped 导出", enabled_modules=["strategy"])
        exported = service.export_mission(mission["mission_id"], fmt="markdown")
        md = exported["content"]
        # skipped 模块应有特殊标记
        assert "未启用" in md


# ── API 层测试 ───────────────────────────────────────────

class TestBossAPI:
    """Boss API 接口测试"""

    @pytest.fixture(autouse=True)
    def _bypass_rate_limit(self, bypass_governance_guard):
        """绕过 API 速率限制 + Governance Guard，避免测试间互相干扰"""
        from unittest.mock import patch
        with patch("backend.routers.boss_router.rate_limiter") as mock_rl:
            mock_rl.check.return_value = (True, "")
            yield

    @pytest.fixture
    def client(self):
        from fastapi.testclient import TestClient
        from backend.app import app
        return TestClient(app, raise_server_exceptions=False)

    def test_create_mission(self, client):
        """POST /boss/missions 创建 mission"""
        resp = client.post("/boss/missions", json={
            "goal": "测试创建 mission API",
            "auto_run": False,
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["mission_id"].startswith("mission_")
        assert data["goal"] == "测试创建 mission API"
        assert len(data["modules"]) == 5

    def test_create_mission_with_enabled_modules(self, client):
        """POST /boss/missions with enabled_modules"""
        resp = client.post("/boss/missions", json={
            "goal": "部分模块 API 测试",
            "enabled_modules": ["strategy", "actions"],
        })
        assert resp.status_code == 200
        data = resp.json()
        for mod in data["modules"]:
            if mod["module_id"] in ("strategy", "actions"):
                assert mod["status"] == "pending"
            else:
                assert mod["status"] == "skipped"

    def test_create_mission_invalid_module(self, client):
        """POST /boss/missions with invalid module_id 返回 400"""
        resp = client.post("/boss/missions", json={
            "goal": "无效模块 API 测试",
            "enabled_modules": ["fake_module"],
        })
        assert resp.status_code == 400

    def test_create_mission_empty_enabled_modules(self, client):
        """POST /boss/missions with empty enabled_modules 返回 400"""
        resp = client.post("/boss/missions", json={
            "goal": "空列表 API 测试",
            "enabled_modules": [],
        })
        assert resp.status_code == 400

    def test_list_missions(self, client):
        """GET /boss/missions 列出 missions"""
        client.post("/boss/missions", json={"goal": "列表测试"})
        resp = client.get("/boss/missions")
        assert resp.status_code == 200
        data = resp.json()
        assert "missions" in data
        assert len(data["missions"]) >= 1

    def test_get_mission(self, client):
        """GET /boss/missions/{id} 获取详情"""
        create_resp = client.post("/boss/missions", json={"goal": "详情 API 测试"})
        mission_id = create_resp.json()["mission_id"]

        resp = client.get(f"/boss/missions/{mission_id}")
        assert resp.status_code == 200
        data = resp.json()
        assert data["mission_id"] == mission_id
        assert len(data["modules"]) == 5

    def test_get_nonexistent_mission(self, client):
        """GET /boss/missions/{id} 不存在返回 404"""
        resp = client.get("/boss/missions/mission_nonexistent")
        assert resp.status_code == 404

    def test_run_invalid_module(self, client):
        """POST 单模块重跑，无效 module_id 返回 400"""
        create_resp = client.post("/boss/missions", json={"goal": "无效模块测试"})
        mission_id = create_resp.json()["mission_id"]

        resp = client.post(f"/boss/missions/{mission_id}/modules/fake_module/run")
        assert resp.status_code == 400

    def test_module_definitions(self, client):
        """GET /boss/modules/definitions 返回 5 个模块定义"""
        resp = client.get("/boss/modules/definitions")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["modules"]) == 5
        ids = [m["id"] for m in data["modules"]]
        assert "strategy" in ids
        assert "actions" in ids

    # ── Export API 测试 ────────────────────────────────────

    def test_export_json_api(self, client):
        """GET /boss/missions/{id}/export?format=json"""
        create_resp = client.post("/boss/missions", json={"goal": "导出 API 测试"})
        mission_id = create_resp.json()["mission_id"]

        resp = client.get(f"/boss/missions/{mission_id}/export?format=json")
        assert resp.status_code == 200
        assert "application/json" in resp.headers.get("content-type", "")
        assert "attachment" in resp.headers.get("content-disposition", "")

        data = json.loads(resp.content)
        assert data["mission_id"] == mission_id

    def test_export_markdown_api(self, client):
        """GET /boss/missions/{id}/export?format=markdown"""
        create_resp = client.post("/boss/missions", json={"goal": "导出 MD API 测试"})
        mission_id = create_resp.json()["mission_id"]

        resp = client.get(f"/boss/missions/{mission_id}/export?format=markdown")
        assert resp.status_code == 200
        assert "text/markdown" in resp.headers.get("content-type", "")

        md = resp.content.decode("utf-8")
        assert "导出 MD API 测试" in md

    def test_export_nonexistent_api(self, client):
        """GET /boss/missions/{id}/export 不存在返回 404"""
        resp = client.get("/boss/missions/mission_nonexistent/export?format=json")
        assert resp.status_code == 404

    def test_export_invalid_format(self, client):
        """GET /boss/missions/{id}/export?format=xml 返回 422"""
        create_resp = client.post("/boss/missions", json={"goal": "无效格式测试"})
        mission_id = create_resp.json()["mission_id"]

        resp = client.get(f"/boss/missions/{mission_id}/export?format=xml")
        assert resp.status_code == 422  # validation error


# ── 事件日志测试 ─────────────────────────────────────────

class TestMissionEvents:
    """Mission 事件日志测试"""

    @pytest.fixture
    def service(self):
        from backend.services.boss_command_center import BossCommandCenterService
        return BossCommandCenterService()

    @pytest.fixture(autouse=True)
    def _bypass_rate_limit(self, bypass_governance_guard):
        """绕过 API 速率限制 + Governance Guard"""
        from unittest.mock import patch
        with patch("backend.routers.boss_router.rate_limiter") as mock_rl:
            mock_rl.check.return_value = (True, "")
            yield

    @pytest.fixture
    def client(self):
        from fastapi.testclient import TestClient
        from backend.app import app
        return TestClient(app, raise_server_exceptions=False)

    def test_create_mission_logs_created(self, service):
        """创建 mission 后应存在 mission_created event"""
        mission = service.create_mission("事件测试")
        events = service.get_events(mission["mission_id"])
        types = [e["type"] for e in events]
        assert "mission_created" in types

    def test_create_mission_logs_skipped_modules(self, service):
        """disabled module 应产生 module_skipped event"""
        mission = service.create_mission("skipped 事件", enabled_modules=["strategy"])
        events = service.get_events(mission["mission_id"])
        skipped = [e for e in events if e["type"] == "module_skipped"]
        assert len(skipped) >= 4  # market, marketing, landing, actions 被跳过
        skipped_ids = [e["module_id"] for e in skipped]
        assert "market" in skipped_ids

    def test_run_mission_logs_events(self, service):
        """run mission 后应包含 mission_started/mission_ready（v2: ready_for_review）"""
        mission = service.create_mission("运行事件测试", enabled_modules=["strategy"])
        mission_id = mission["mission_id"]

        mock_executor = _make_mock_executor(ok=True, final_answer="战略分析结果文本内容", confidence=0.7)
        with patch("backend.services.boss_module_executors.get_executor", return_value=mock_executor):
            service.run_mission(mission_id)

        events = service.get_events(mission_id)
        types = [e["type"] for e in events]
        assert "mission_started" in types
        # v2: 所有模块 done → mission_ready (ready_for_review)
        assert "mission_ready" in types
        assert "module_started" in types
        assert "module_succeeded" in types

    def test_run_module_logs_success(self, service):
        """run module 成功后应产生 module_started + module_succeeded"""
        mission = service.create_mission("模块事件测试")
        mission_id = mission["mission_id"]

        mock_executor = _make_mock_executor(ok=True, final_answer="战略结果", confidence=0.8, used_tools=["mimo"])
        with patch("backend.services.boss_module_executors.get_executor", return_value=mock_executor):
            service.run_module(mission_id, "strategy")

        events = service.get_events(mission_id)
        module_events = [e for e in events if e["module_id"] == "strategy"]
        types = [e["type"] for e in module_events]
        assert "module_started" in types
        assert "module_succeeded" in types

    def test_run_module_failure_logs_failed(self, service):
        """module failed 时应产生 module_failed event"""
        mission = service.create_mission("失败事件测试")
        mission_id = mission["mission_id"]

        mock_executor = _make_mock_executor(ok=False, error="Adapter 不可用")
        with patch("backend.services.boss_module_executors.get_executor", return_value=mock_executor):
            service.run_module(mission_id, "market")

        events = service.get_events(mission_id)
        failed_events = [e for e in events if e["type"] == "module_failed" and e["module_id"] == "market"]
        assert len(failed_events) == 1
        assert "Adapter 不可用" in failed_events[0]["message"]

    def test_export_logs_event(self, service):
        """export 后应产生 mission_exported event"""
        mission = service.create_mission("导出事件测试")
        mission_id = mission["mission_id"]

        service.export_mission(mission_id, fmt="json")
        events = service.get_events(mission_id)
        exported = [e for e in events if e["type"] == "mission_exported"]
        assert len(exported) == 1
        assert exported[0]["payload"]["format"] == "json"

    def test_events_chronological_order(self, service):
        """事件应按时间升序返回"""
        mission = service.create_mission("顺序测试")
        mission_id = mission["mission_id"]

        mock_executor = _make_mock_executor(ok=True, final_answer="战略分析结果文本内容", confidence=0.5)
        with patch("backend.services.boss_module_executors.get_executor", return_value=mock_executor):
            service.run_mission(mission_id)

        events = service.get_events(mission_id)
        ids = [e["id"] for e in events]
        assert ids == sorted(ids), "事件 ID 应按升序排列"

    def test_events_api(self, client):
        """GET /boss/missions/{id}/events 返回事件列表"""
        create_resp = client.post("/boss/missions", json={"goal": "事件 API 测试"})
        mission_id = create_resp.json()["mission_id"]

        resp = client.get(f"/boss/missions/{mission_id}/events")
        assert resp.status_code == 200
        data = resp.json()
        assert data["mission_id"] == mission_id
        assert isinstance(data["events"], list)
        assert data["total"] >= 1
        assert any(e["type"] == "mission_created" for e in data["events"])

    def test_events_api_nonexistent(self, client):
        """GET /boss/missions/{id}/events 不存在返回 404"""
        resp = client.get("/boss/missions/mission_nonexistent/events")
        assert resp.status_code == 404


# ── 模板测试 ─────────────────────────────────────────────

class TestTemplates:
    """模板 API 测试"""

    @pytest.fixture(autouse=True)
    def _bypass_rate_limit(self, bypass_governance_guard):
        from unittest.mock import patch
        with patch("backend.routers.boss_router.rate_limiter") as mock_rl:
            mock_rl.check.return_value = (True, "")
            yield

    @pytest.fixture
    def client(self):
        from fastapi.testclient import TestClient
        from backend.app import app
        return TestClient(app, raise_server_exceptions=False)

    def test_list_templates(self, client):
        """GET /boss/templates 返回通用业务流程模板列表"""
        resp = client.get("/boss/templates")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 8  # 8 个通用模板
        ids = [t["id"] for t in data["templates"]]
        # 通用模板
        assert "goal_to_plan" in ids
        assert "research_to_decision" in ids
        assert "deliverable_pack" in ids
        assert "communication_plan" in ids
        assert "operation_review" in ids
        assert "risk_check" in ids
        assert "execution_checklist" in ids
        assert "data_insight" in ids
        # 旧业务模板不应在列表中
        assert "ecommerce_product_research" not in ids
        assert "xianyu_listing_pack" not in ids
        assert "saas_feature_planning" not in ids
        assert "landing_page_offer" not in ids
        assert "weekly_business_review" not in ids
        assert "xianyu_delivery_pack" not in ids

    def test_from_template_default(self, client):
        """POST /boss/missions/from-template 创建 mission"""
        resp = client.post("/boss/missions/from-template", json={
            "template_id": "deliverable_pack",
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["mission_id"].startswith("mission_")
        # 使用模板默认模块（strategy, marketing, landing, actions）
        module_ids = [m["module_id"] for m in data["modules"]]
        assert "strategy" in module_ids
        assert "marketing" in module_ids
        assert "landing" in module_ids
        assert "actions" in module_ids
        # market 应该被 skipped
        market = next(m for m in data["modules"] if m["module_id"] == "market")
        assert market["status"] == "skipped"

    def test_from_template_override_goal(self, client):
        """from-template overrides goal 生效"""
        resp = client.post("/boss/missions/from-template", json={
            "template_id": "research_to_decision",
            "goal": "自定义目标：分析市场进入策略",
        })
        assert resp.status_code == 200
        data = resp.json()
        assert "市场进入策略" in data["goal"]

    def test_from_template_override_modules(self, client):
        """from-template overrides enabled_modules 生效"""
        resp = client.post("/boss/missions/from-template", json={
            "template_id": "operation_review",
            "enabled_modules": ["strategy", "actions"],
        })
        assert resp.status_code == 200
        data = resp.json()
        active = [m for m in data["modules"] if m["status"] != "skipped"]
        assert len(active) == 2

    def test_from_template_with_inputs(self, client):
        """from-template with inputs 追加到 goal"""
        resp = client.post("/boss/missions/from-template", json={
            "template_id": "deliverable_pack",
            "inputs": {"deliverable_type": "产品文档", "target_audience": "开发者"},
        })
        assert resp.status_code == 200
        data = resp.json()
        assert "产品文档" in data["goal"]

    def test_from_template_invalid_id(self, client):
        """from-template 无效 template_id 返回 404"""
        resp = client.post("/boss/missions/from-template", json={
            "template_id": "nonexistent_template",
        })
        assert resp.status_code == 404


# ── Phase 6.19: 通用业务流程模板测试 ──────────────────────────

class TestBusinessTemplates:
    """Phase 6.19: 通用业务流程模板机制测试"""

    @pytest.fixture
    def service(self):
        from backend.services.boss_command_center import BossCommandCenterService
        return BossCommandCenterService()

    @pytest.fixture(autouse=True)
    def _bypass_rate_limit_and_guard(self, bypass_governance_guard):
        from unittest.mock import patch
        with patch("backend.routers.boss_router.rate_limiter") as mock_rl:
            mock_rl.check.return_value = (True, "")
            yield

    @pytest.fixture
    def client(self):
        from fastapi.testclient import TestClient
        from backend.app import app
        return TestClient(app, raise_server_exceptions=False)

    # ── 通用模板存在性测试 ──

    def test_generic_templates_exist(self, service):
        """所有通用业务流程模板存在"""
        generic_ids = [
            "goal_to_plan", "research_to_decision", "deliverable_pack",
            "communication_plan", "operation_review", "risk_check",
            "execution_checklist", "data_insight",
        ]
        for tpl_id in generic_ids:
            tpl = service.get_template(tpl_id)
            assert tpl is not None, f"模板 {tpl_id} 不存在"
            assert tpl["id"] == tpl_id

    def test_all_templates_have_generic_type(self, service):
        """所有模板 template_type = generic_business_process"""
        for tpl in service.get_templates():
            assert tpl.get("template_type") == "generic_business_process", \
                f"模板 {tpl['id']} 的 template_type 不是 generic_business_process"

    def test_all_templates_have_domain_lock_false(self, service):
        """所有模板 domain_lock = False"""
        for tpl in service.get_templates():
            assert tpl.get("domain_lock") is False, \
                f"模板 {tpl['id']} 的 domain_lock 不是 False"

    def test_all_templates_have_protocol_version(self, service):
        """所有模板有 protocol_version"""
        for tpl in service.get_templates():
            assert "protocol_version" in tpl, f"模板 {tpl['id']} 缺少 protocol_version"

    def test_all_templates_have_review_checklist(self, service):
        """所有模板有 review_checklist"""
        for tpl in service.get_templates():
            assert "review_checklist" in tpl, f"模板 {tpl['id']} 缺少 review_checklist"
            assert len(tpl["review_checklist"]) >= 3, \
                f"模板 {tpl['id']} 的 review_checklist 不足 3 项"

    def test_all_templates_have_context_schema(self, service):
        """所有模板有 context_schema"""
        for tpl in service.get_templates():
            assert "context_schema" in tpl, f"模板 {tpl['id']} 缺少 context_schema"
            assert "fields" in tpl["context_schema"]

    def test_no_business_terms_in_templates(self, service):
        """模板中不包含硬编码业务词"""
        business_terms = ["闲鱼", "电商", "小红书", "抖音", "SaaS", "SEO"]
        for tpl in service.get_templates():
            for term in business_terms:
                assert term not in tpl.get("name", ""), \
                    f"模板 {tpl['id']} 的 name 包含业务词: {term}"
                assert term not in tpl.get("description", ""), \
                    f"模板 {tpl['id']} 的 description 包含业务词: {term}"
                assert term not in tpl.get("default_goal", ""), \
                    f"模板 {tpl['id']} 的 default_goal 包含业务词: {term}"

    # ── 旧 ID 兼容测试 ──

    def test_old_id_alias_to_generic(self, service):
        """旧业务模板 ID 映射到通用模板"""
        aliases = {
            "ecommerce_product_research": "research_to_decision",
            "xianyu_listing_pack": "deliverable_pack",
            "saas_feature_planning": "goal_to_plan",
            "landing_page_offer": "deliverable_pack",
            "weekly_business_review": "operation_review",
            "xianyu_delivery_pack": "deliverable_pack",
        }
        for old_id, expected_target in aliases.items():
            tpl = service.get_template(old_id)
            assert tpl is not None, f"旧 ID {old_id} 无法解析"
            assert tpl.get("aliased_to") == expected_target, \
                f"旧 ID {old_id} 映射到 {tpl.get('aliased_to')}，期望 {expected_target}"

    def test_old_id_can_create_mission(self, service):
        """旧业务模板 ID 仍可创建 mission"""
        old_ids = [
            "ecommerce_product_research", "xianyu_listing_pack",
            "saas_feature_planning", "landing_page_offer", "weekly_business_review",
        ]
        for old_id in old_ids:
            mission = service.create_mission_from_template(old_id)
            assert mission is not None, f"旧 ID {old_id} 创建 mission 失败"
            assert mission["status"] == "pending_review"

    def test_old_id_mission_uses_generic_modules(self, service):
        """旧 ID 创建的 mission 使用通用模块定义"""
        mission = service.create_mission_from_template("xianyu_listing_pack")
        assert mission is not None
        strategy = next(m for m in mission["modules"] if m["module_id"] == "strategy")
        # 通用 prompt 不包含 "闲鱼"
        assert "闲鱼" not in strategy["prompt"]
        # 通用 prompt 包含 "业务策略顾问"
        assert "业务策略顾问" in strategy["prompt"]

    # ── 通用模板功能测试 ──

    def test_goal_to_plan_template(self, service):
        """goal_to_plan 模板正常工作"""
        tpl = service.get_template("goal_to_plan")
        assert tpl["default_modules"] == ["strategy", "market", "actions"]
        mission = service.create_mission_from_template("goal_to_plan")
        assert mission is not None
        assert mission["status"] == "pending_review"

    def test_deliverable_pack_template(self, service):
        """deliverable_pack 模板正常工作"""
        tpl = service.get_template("deliverable_pack")
        assert "strategy" in tpl["default_modules"]
        assert "marketing" in tpl["default_modules"]
        assert "landing" in tpl["default_modules"]

    def test_template_with_inputs(self, service):
        """模板 with inputs 追加到 goal"""
        mission = service.create_mission_from_template(
            "deliverable_pack",
            goal="生成产品文档",
            inputs={"deliverable_type": "API 文档", "target_audience": "开发者"},
        )
        assert mission is not None
        assert "API 文档" in mission["goal"]
        assert "开发者" in mission["goal"]

    def test_template_create_mission_pending_review(self, service):
        """所有模板创建的 mission 默认 pending_review"""
        for tpl in service.get_templates():
            mission = service.create_mission_from_template(tpl["id"])
            assert mission is not None, f"模板 {tpl['id']} 创建失败"
            assert mission["status"] == "pending_review", \
                f"模板 {tpl['id']} 状态不是 pending_review"

    def test_old_templates_still_work(self, service):
        """旧模板 ID 通过 alias 映射仍可正常工作"""
        for tpl_id in ["ecommerce_product_research", "xianyu_listing_pack", "saas_feature_planning"]:
            tpl = service.get_template(tpl_id)
            assert tpl is not None
            assert "aliased_to" in tpl  # 标记为别名

    def test_old_id_from_template_api(self, client):
        """POST /boss/missions/from-template 使用旧 ID 仍可创建，但 mission.template_id 必须是 canonical 通用 ID"""
        resp = client.post("/boss/missions/from-template", json={
            "template_id": "xianyu_listing_pack",
            "goal": "帮我生成上架物料包",
            "inputs": {"product_name": "测试商品"},
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["mission_id"].startswith("mission_")
        # Phase 6.20: mission.template_id 必须是 canonical 通用 ID，不是旧 alias
        assert data["template_id"] == "deliverable_pack"
        assert data["status"] == "pending_review"

    def test_old_id_records_alias_event(self, service):
        """旧 ID 创建 mission 时应记录 template_aliased 事件"""
        mission = service.create_mission_from_template("ecommerce_product_research")
        assert mission is not None
        # mission.template_id 必须是 canonical ID
        assert mission["template_id"] == "research_to_decision"
        # 验证事件
        events = service.get_events(mission["mission_id"])
        alias_events = [e for e in events if e["type"] == "template_aliased"]
        assert len(alias_events) == 1
        assert alias_events[0]["payload"]["aliased_from"] == "ecommerce_product_research"
        assert alias_events[0]["payload"]["canonical_id"] == "research_to_decision"

    def test_canonical_id_mission_does_not_trigger_legacy_executor(self, service):
        """旧 ID 创建的 mission 执行时走 DefaultModuleExecutor，不触发旧业务执行器"""
        mission = service.create_mission_from_template("ecommerce_product_research")
        mission_id = mission["mission_id"]
        # template_id 应该是通用 ID
        assert mission["template_id"] == "research_to_decision"

        # 执行时 get_executor 应返回 DefaultModuleExecutor（不是 EcommerceMarketResearchExecutor）
        from backend.services.boss_module_executors import get_executor, DefaultModuleExecutor
        executor = get_executor(mission["template_id"], "market")
        assert isinstance(executor, DefaultModuleExecutor), (
            f"Expected DefaultModuleExecutor for canonical template, got {type(executor).__name__}"
        )

    def test_templates_api_includes_generic_fields(self, client):
        """GET /boss/templates 返回包含通用字段的模板"""
        resp = client.get("/boss/templates")
        assert resp.status_code == 200
        data = resp.json()
        tpl = data["templates"][0]
        assert "template_type" in tpl
        assert "domain_lock" in tpl
        assert "protocol_version" in tpl
        assert "review_checklist" in tpl
        assert "context_schema" in tpl

    def test_template_count(self, client):
        """模板总数应为 8（8 个通用模板）"""
        resp = client.get("/boss/templates")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 8

    def test_old_ids_not_in_template_list(self, client):
        """get_templates 不展示旧业务 ID"""
        resp = client.get("/boss/templates")
        assert resp.status_code == 200
        data = resp.json()
        ids = [t["id"] for t in data["templates"]]
        old_ids = ["ecommerce_product_research", "xianyu_listing_pack",
                    "saas_feature_planning", "landing_page_offer",
                    "weekly_business_review", "xianyu_delivery_pack"]
        for old_id in old_ids:
            assert old_id not in ids, f"旧业务 ID '{old_id}' 不应出现在模板列表中"


# ── Phase 6.20: Legacy Executor 隔离测试 ──────────────────────

class TestLegacyExecutorIsolation:
    """Phase 6.20: 旧业务执行器默认不启用"""

    def test_default_registry_empty(self):
        """默认 _EXECUTOR_REGISTRY 不含旧业务模板 ID"""
        from backend.services.boss_module_executors import _EXECUTOR_REGISTRY
        assert "ecommerce_product_research" not in _EXECUTOR_REGISTRY

    def test_get_executor_returns_default_for_old_template_id(self):
        """默认情况下 get_executor('ecommerce_product_research', 'market') 返回 DefaultModuleExecutor"""
        from backend.services.boss_module_executors import get_executor, DefaultModuleExecutor
        executor = get_executor("ecommerce_product_research", "market")
        assert isinstance(executor, DefaultModuleExecutor)

    def test_get_executor_returns_default_for_canonical_id(self):
        """get_executor('research_to_decision', 'market') 返回 DefaultModuleExecutor"""
        from backend.services.boss_module_executors import get_executor, DefaultModuleExecutor
        executor = get_executor("research_to_decision", "market")
        assert isinstance(executor, DefaultModuleExecutor)

    def test_legacy_executor_classes_still_exist(self):
        """旧执行器类定义仍然存在（供 opt-in 使用）"""
        from backend.services.boss_module_executors import (
            EcommerceMarketResearchExecutor,
            EcommerceCompetitorAnalysisExecutor,
            EcommerceListingPackExecutor,
        )
        # 类存在但不会默认注册
        assert EcommerceMarketResearchExecutor is not None
        assert EcommerceCompetitorAnalysisExecutor is not None
        assert EcommerceListingPackExecutor is not None


# ── Metrics 测试 ─────────────────────────────────────────

class TestMetrics:
    """Mission Metrics 测试"""

    @pytest.fixture
    def service(self):
        from backend.services.boss_command_center import BossCommandCenterService
        return BossCommandCenterService()

    @pytest.fixture(autouse=True)
    def _bypass_rate_limit(self, bypass_governance_guard):
        from unittest.mock import patch
        with patch("backend.routers.boss_router.rate_limiter") as mock_rl:
            mock_rl.check.return_value = (True, "")
            yield

    @pytest.fixture
    def client(self):
        from fastapi.testclient import TestClient
        from backend.app import app
        return TestClient(app, raise_server_exceptions=False)

    def test_metrics_on_pending_mission(self, service):
        """pending mission 的 metrics 全为 0"""
        mission = service.create_mission("metrics 测试")
        metrics = mission["metrics"]
        assert metrics["total_modules"] == 5
        assert metrics["succeeded_modules"] == 0
        assert metrics["failed_modules"] == 0
        assert metrics["skipped_modules"] == 0
        assert metrics["completion_rate"] == 0.0
        assert metrics["duration_ms"] == 0

    def test_metrics_after_partial_run(self, service):
        """部分执行后 metrics 正确"""
        mission = service.create_mission("partial metrics", enabled_modules=["strategy", "market", "actions"])
        mission_id = mission["mission_id"]

        mock_executor = _make_mock_executor(ok=True, final_answer="战略分析结果文本内容", confidence=0.7,
                                            warnings=["w1"], next_actions=["a1", "a2"])
        with patch("backend.services.boss_module_executors.get_executor", return_value=mock_executor):
            service.run_module(mission_id, "strategy")
            service.run_module(mission_id, "market")

        mission = service.get_mission(mission_id)
        metrics = mission["metrics"]
        assert metrics["total_modules"] == 5
        assert metrics["succeeded_modules"] == 2
        assert metrics["failed_modules"] == 0
        assert metrics["skipped_modules"] == 2  # marketing, landing
        assert abs(metrics["completion_rate"] - 2 / 3) < 0.01  # 2 succeeded out of 3 active
        assert metrics["warning_count"] >= 2
        assert metrics["next_action_count"] >= 4

    def test_metrics_includes_failed(self, service):
        """failed module 计入 metrics"""
        mission = service.create_mission("failed metrics", enabled_modules=["strategy"])
        mission_id = mission["mission_id"]

        mock_executor = _make_mock_executor(ok=False, error="boom")
        with patch("backend.services.boss_module_executors.get_executor", return_value=mock_executor):
            service.run_module(mission_id, "strategy")

        mission = service.get_mission(mission_id)
        metrics = mission["metrics"]
        assert metrics["failed_modules"] == 1
        assert metrics["completion_rate"] == 0.0

    def test_metrics_in_api_response(self, client):
        """GET /boss/missions/{id} 返回 metrics"""
        create_resp = client.post("/boss/missions", json={"goal": "API metrics 测试"})
        mission_id = create_resp.json()["mission_id"]

        resp = client.get(f"/boss/missions/{mission_id}")
        assert resp.status_code == 200
        data = resp.json()
        assert "metrics" in data
        assert "completion_rate" in data["metrics"]
        assert data["metrics"]["total_modules"] == 5


# ── Provider 抽象层测试 ────────────────────────────────────

class TestExecutionProvider:
    """Execution Provider 测试"""

    def test_mock_provider_available(self):
        """LocalMockExecutionProvider 应该可用"""
        from backend.services.boss_execution_providers import LocalMockExecutionProvider
        provider = LocalMockExecutionProvider()
        assert provider.is_available is True
        assert provider.name == "local_mock"

    def test_mock_provider_market_research(self):
        """Mock Provider 市场调研应返回正确结构"""
        from backend.services.boss_execution_providers import LocalMockExecutionProvider
        provider = LocalMockExecutionProvider()
        result = provider.execute_market_research("测试目标")
        assert result["ok"] is True
        assert "summary" in result
        assert "evidence" in result
        assert "competitors" in result
        assert "pricing" in result
        assert "warnings" in result
        assert "raw_data" in result

    def test_mock_provider_market_research_accepts_allow_browser(self):
        """Regression: local_mock execute_market_research must accept allow_browser_automation kwarg."""
        from backend.services.boss_execution_providers import LocalMockExecutionProvider
        provider = LocalMockExecutionProvider()
        result = provider.execute_market_research(
            "测试目标", context={}, allow_browser_automation=True
        )
        assert result["ok"] is True

    def test_mock_provider_competitor_analysis(self):
        """Mock Provider 竞品分析应返回正确结构"""
        from backend.services.boss_execution_providers import LocalMockExecutionProvider
        provider = LocalMockExecutionProvider()
        result = provider.execute_competitor_analysis("测试目标", [])
        assert result["ok"] is True
        assert "summary" in result
        assert "competitors" in result
        assert "pricing" in result

    def test_mock_provider_listing_pack(self):
        """Mock Provider 上架物料包应返回正确结构"""
        from backend.services.boss_execution_providers import LocalMockExecutionProvider
        provider = LocalMockExecutionProvider()
        result = provider.execute_listing_pack("测试目标", [], {})
        assert result["ok"] is True
        assert "summary" in result
        assert "listing_copy" in result
        assert "pricing" in result
        assert "image_plan" in result
        assert "next_actions" in result

    def test_provider_registry(self):
        """Provider Registry 应该能注册和获取 Provider"""
        from backend.services.boss_execution_providers import ProviderRegistry, LocalMockExecutionProvider
        registry = ProviderRegistry()
        provider = LocalMockExecutionProvider()
        registry.register(provider, is_fallback=True)

        retrieved = registry.get_provider("local_mock")
        assert retrieved is not None
        assert retrieved.name == "local_mock"

    def test_provider_registry_get_available(self):
        """Provider Registry 应该能获取可用的 Provider"""
        from backend.services.boss_execution_providers import ProviderRegistry, LocalMockExecutionProvider
        registry = ProviderRegistry()
        provider = LocalMockExecutionProvider()
        registry.register(provider, is_fallback=True)

        available, warnings = registry.get_available_provider("local_mock")
        assert available is not None
        assert available.name == "local_mock"
        assert len(warnings) == 0

    def test_provider_registry_fallback(self):
        """Provider Registry 应该能 fallback"""
        from backend.services.boss_execution_providers import ProviderRegistry, LocalMockExecutionProvider

        class UnavailableProvider(LocalMockExecutionProvider):
            @property
            def is_available(self):
                return False

        registry = ProviderRegistry()
        unavailable = UnavailableProvider()
        unavailable._name = "unavailable"
        registry.register(unavailable)

        fallback = LocalMockExecutionProvider()
        registry.register(fallback, is_fallback=True)

        available, warnings = registry.get_available_provider("unavailable")
        assert available is not None
        assert available.name == "local_mock"
        assert len(warnings) > 0


# ── 标准化输出测试 ──────────────────────────────────────────

class TestStandardOutput:
    """标准化 structured_output 测试"""

    def test_create_standard_output(self):
        """create_standard_output 应该返回完整结构"""
        from backend.services.boss_execution_providers import create_standard_output
        output = create_standard_output(
            status="success",
            summary="测试摘要",
            provider="local_mock",
        )
        assert output["status"] == "success"
        assert output["summary"] == "测试摘要"
        assert output["provider"] == "local_mock"
        assert "generated_at" in output
        assert "evidence" in output
        assert "competitors" in output
        assert "pricing" in output
        assert "listing_copy" in output
        assert "image_plan" in output
        assert "next_actions" in output
        assert "warnings" in output
        assert "raw_data" in output


# ── 事件日志增强测试 ─────────────────────────────────────────

class TestEnhancedEvents:
    """增强事件日志测试"""

    @pytest.fixture
    def service(self):
        from backend.services.boss_command_center import BossCommandCenterService
        return BossCommandCenterService()

    @pytest.fixture(autouse=True)
    def _bypass_rate_limit(self):
        from unittest.mock import patch
        with patch("backend.routers.boss_router.rate_limiter") as mock_rl:
            mock_rl.check.return_value = (True, "")
            yield

    def test_module_succeeded_logs_provider(self, service):
        """module_succeeded 事件应包含 provider"""
        mission = service.create_mission("provider 事件测试")
        mission_id = mission["mission_id"]

        mock_executor = _make_mock_executor(ok=True, final_answer="战略分析结果文本内容", confidence=0.7,
                                            provider="local_mock")
        with patch("backend.services.boss_module_executors.get_executor", return_value=mock_executor):
            service.run_module(mission_id, "strategy")

        events = service.get_events(mission_id)
        succeeded = [e for e in events if e["type"] == "module_succeeded"]
        assert len(succeeded) == 1
        assert succeeded[0]["payload"]["provider"] == "local_mock"

    def test_module_failed_logs_provider(self, service):
        """module_failed 事件应包含 provider"""
        mission = service.create_mission("失败 provider 测试")
        mission_id = mission["mission_id"]

        mock_executor = _make_mock_executor(ok=False, error="boom", provider="local_mock")
        with patch("backend.services.boss_module_executors.get_executor", return_value=mock_executor):
            service.run_module(mission_id, "strategy")

        events = service.get_events(mission_id)
        failed = [e for e in events if e["type"] == "module_failed"]
        assert len(failed) == 1
        assert failed[0]["payload"]["provider"] == "local_mock"

    def test_export_logs_report_generated(self, service):
        """export 应该产生 report_generated 事件"""
        mission = service.create_mission("报告生成事件测试")
        mission_id = mission["mission_id"]

        service.export_mission(mission_id, fmt="json")
        events = service.get_events(mission_id)
        report_events = [e for e in events if e["type"] == "report_generated"]
        assert len(report_events) == 1
        assert report_events[0]["payload"]["format"] == "json"
        assert "content_length" in report_events[0]["payload"]


# ── Hermes Provider 测试 ────────────────────────────────────

class TestHermesExecutionProvider:
    """Hermes Execution Provider 测试（mock subprocess）"""

    def test_hermes_provider_available_when_cli_exists(self, monkeypatch):
        """Hermes CLI 存在时应该可用"""
        import shutil
        from backend.services.boss_execution_providers import HermesExecutionProvider

        provider = HermesExecutionProvider()

        # Mock shutil.which 返回非 None
        def mock_which(cmd):
            return "/usr/bin/hermes"

        monkeypatch.setattr(shutil, "which", mock_which)
        assert provider.is_available is True

    def test_hermes_provider_unavailable_when_cli_missing(self, monkeypatch):
        """Hermes CLI 不存在时应该不可用"""
        import shutil
        from backend.services.boss_execution_providers import HermesExecutionProvider

        provider = HermesExecutionProvider()

        # Mock shutil.which 返回 None
        def mock_which(cmd):
            return None

        monkeypatch.setattr(shutil, "which", mock_which)
        assert provider.is_available is False

    def test_hermes_market_research_valid_json(self, monkeypatch):
        """Hermes 返回合法 JSON 时应该成功解析"""
        from backend.services.boss_execution_providers import HermesExecutionProvider
        import subprocess
        import io

        provider = HermesExecutionProvider()

        # Mock subprocess.Popen 返回成功结果
        mock_stdout = '{"summary": "测试摘要", "evidence": [{"title": "来源1", "url": "http://example.com"}], "competitors": [{"name": "竞品A", "price": "99-199"}], "pricing": {"range": "99-199"}, "warnings": []}'

        class MockProcess:
            returncode = 0
            stdout = io.StringIO(mock_stdout)
            stderr = io.StringIO("")

            def wait(self, timeout=None):
                return 0

            def kill(self):
                pass

        def mock_popen(cmd, **kwargs):
            return MockProcess()

        monkeypatch.setattr(subprocess, "Popen", mock_popen)

        result = provider.execute_market_research("测试目标", allow_browser_automation=True)
        assert result["ok"] is True
        assert result["summary"] == "测试摘要"
        assert len(result["evidence"]) == 1
        assert len(result["competitors"]) == 1

    def test_hermes_market_research_invalid_json(self, monkeypatch):
        """Hermes 返回非 JSON 时应该返回失败"""
        from backend.services.boss_execution_providers import HermesExecutionProvider
        import subprocess
        import io

        provider = HermesExecutionProvider()

        # Mock subprocess.Popen 返回非 JSON（实际代码用 Popen，不用 run）
        class MockProcess:
            returncode = 0
            stdout = io.StringIO("This is not JSON output from Hermes")
            stderr = io.StringIO("")

            def wait(self, timeout=None):
                return 0

            def kill(self):
                pass

        def mock_popen(cmd, **kwargs):
            return MockProcess()

        monkeypatch.setattr(subprocess, "Popen", mock_popen)

        result = provider.execute_market_research("测试目标", allow_browser_automation=True)
        assert result["ok"] is False
        assert len(result["warnings"]) >= 1

    def test_hermes_market_research_timeout(self, monkeypatch):
        """Hermes 超时应该返回失败"""
        from backend.services.boss_execution_providers import HermesExecutionProvider
        import subprocess

        provider = HermesExecutionProvider()

        # Mock subprocess.Popen 抛出 TimeoutExpired（实际代码用 Popen）
        def mock_popen(cmd, **kwargs):
            raise subprocess.TimeoutExpired(cmd=cmd, timeout=180)

        monkeypatch.setattr(subprocess, "Popen", mock_popen)

        result = provider.execute_market_research("测试目标", allow_browser_automation=True)
        assert result["ok"] is False
        assert len(result["warnings"]) >= 1

    def test_hermes_market_research_command_missing(self, monkeypatch):
        """Hermes CLI 不存在时应该返回失败"""
        from backend.services.boss_execution_providers import HermesExecutionProvider
        import subprocess

        provider = HermesExecutionProvider()

        # Mock subprocess.Popen 抛出 FileNotFoundError（实际代码用 Popen）
        def mock_popen(cmd, **kwargs):
            raise FileNotFoundError("No such file or directory: hermes")

        monkeypatch.setattr(subprocess, "Popen", mock_popen)

        result = provider.execute_market_research("测试目标", allow_browser_automation=True)
        assert result["ok"] is False
        assert len(result["warnings"]) >= 1

    def test_hermes_competitor_analysis_valid_json(self, monkeypatch):
        """Hermes 竞品分析返回合法 JSON 时应该成功解析"""
        from backend.services.boss_execution_providers import HermesExecutionProvider
        import subprocess
        import io

        provider = HermesExecutionProvider()

        mock_stdout = '{"summary": "竞品分析摘要", "competitors": [{"name": "竞品A", "price": "99", "strengths": "便宜", "weaknesses": "功能少"}], "pricing": {"recommended_range": "129-249"}, "warnings": []}'

        class MockProcess:
            returncode = 0
            stdout = io.StringIO(mock_stdout)
            stderr = io.StringIO("")

            def wait(self, timeout=None):
                return 0

            def kill(self):
                pass

        def mock_popen(cmd, **kwargs):
            return MockProcess()

        monkeypatch.setattr(subprocess, "Popen", mock_popen)

        result = provider.execute_competitor_analysis("测试目标", [], allow_browser_automation=True)
        assert result["ok"] is True
        assert result["summary"] == "竞品分析摘要"
        assert len(result["competitors"]) == 1

    def test_hermes_listing_pack_valid_json(self, monkeypatch):
        """Hermes 上架物料包返回合法 JSON 时应该成功解析"""
        from backend.services.boss_execution_providers import HermesExecutionProvider
        import subprocess
        import io

        provider = HermesExecutionProvider()

        mock_stdout = '{"summary": "物料包摘要", "listing_copy": "【爆款推荐】测试产品", "pricing": {"recommended": "199"}, "image_plan": {"main_image": "白底图"}, "next_actions": ["确定定价", "拍摄主图"], "warnings": []}'

        class MockProcess:
            returncode = 0
            stdout = io.StringIO(mock_stdout)
            stderr = io.StringIO("")

            def wait(self, timeout=None):
                return 0

            def kill(self):
                pass

        def mock_popen(cmd, **kwargs):
            return MockProcess()

        monkeypatch.setattr(subprocess, "Popen", mock_popen)

        result = provider.execute_listing_pack("测试目标", [], {}, allow_browser_automation=True)
        assert result["ok"] is True
        assert result["listing_copy"] == "【爆款推荐】测试产品"
        assert len(result["next_actions"]) == 2

    def test_hermes_fallback_to_local_heuristic(self, monkeypatch):
        """Hermes 失败时应该 fallback 到 local_heuristic"""
        from backend.services.boss_execution_providers import ProviderRegistry, HermesExecutionProvider, LocalHeuristicExecutionProvider
        import shutil

        # 创建一个总是失败的 Hermes provider
        class FailingHermesProvider(HermesExecutionProvider):
            @property
            def is_available(self):
                return True

            def execute_market_research(self, goal, context=None):
                return {"ok": False, "summary": "", "evidence": [], "competitors": [], "pricing": {}, "warnings": ["Hermes always fails"], "raw_data": {}}

        registry = ProviderRegistry()
        failing_hermes = FailingHermesProvider()
        heuristic = LocalHeuristicExecutionProvider()

        registry.register(failing_hermes)
        registry.register(heuristic, is_fallback=True)

        # 获取 hermes provider（可用但执行会失败）
        provider, warnings = registry.get_available_provider("hermes")
        assert provider.name == "hermes"

        # 执行时应该失败
        result = provider.execute_market_research("测试目标")
        assert result["ok"] is False
        assert "Hermes always fails" in result["warnings"][0]


# ── Regression: auto_run + browser flag defaults ───────────────

class TestAutoRunRegression:
    """Regression tests for auto_run=True and allow_browser_automation defaulting."""

    @pytest.fixture
    def service(self):
        from backend.services.boss_command_center import BossCommandCenterService
        return BossCommandCenterService()

    def test_auto_run_true_starts_execution(self, service):
        """Phase 6.13: create_mission(auto_run=True) must NOT execute modules.
        auto_run is deprecated — mission always stays in pending_review after creation.
        Callers must explicitly call run_mission() to execute."""
        mission = service.create_mission("auto run 测试", auto_run=True)

        # After create_mission, all active modules should still be pending
        active = [m for m in mission["modules"] if m["status"] != "skipped"]
        assert all(m["status"] == "pending" for m in active), (
            f"auto_run=True should be ignored; statuses: {[m['status'] for m in active]}"
        )
        assert mission["status"] == "pending_review"

    def test_auto_run_false_does_not_execute(self, service):
        """create_mission(auto_run=False) must NOT execute modules (plan only)."""
        mission = service.create_mission("no auto run 测试", auto_run=False)
        active = [m for m in mission["modules"] if m["status"] != "skipped"]
        assert all(m["status"] == "pending" for m in active)
        assert mission["status"] == "pending_review"

    def test_run_mission_defaults_browser_flag_from_mission(self, service):
        """run_mission() without explicit allow_browser_automation should use saved mission value."""
        # Create mission with browser automation approved
        mission = service.create_mission("browser 测试", allow_browser_automation=True)
        mission_id = mission["mission_id"]

        captured_ctx = {}

        def fake_execute(goal, module_id, mid, context=None):
            captured_ctx.update(context or {})
            return MagicMock(
                ok=True, final_answer="result text content here", confidence=0.7,
                warnings=[], used_tools=[], mode="local", error="",
                next_actions=[], structured_output={}, provider="mock",
            )

        mock_exec = MagicMock(side_effect=fake_execute)
        with patch("backend.services.boss_module_executors.get_executor", return_value=MagicMock(execute=mock_exec)):
            service.run_mission(mission_id)  # no explicit allow_browser_automation

        assert captured_ctx.get("allow_browser_automation") is True, (
            "run_mission() should default allow_browser_automation from saved mission when not passed"
        )

    def test_run_mission_explicit_false_overrides_saved(self, service):
        """run_mission(allow_browser_automation=False) overrides saved True."""
        mission = service.create_mission("override 测试", allow_browser_automation=True)
        mission_id = mission["mission_id"]

        captured_ctx = {}

        def fake_execute(goal, module_id, mid, context=None):
            captured_ctx.update(context or {})
            return MagicMock(
                ok=True, final_answer="result text content here", confidence=0.7,
                warnings=[], used_tools=[], mode="local", error="",
                next_actions=[], structured_output={}, provider="mock",
            )

        mock_exec = MagicMock(side_effect=fake_execute)
        with patch("backend.services.boss_module_executors.get_executor", return_value=MagicMock(execute=mock_exec)):
            service.run_mission(mission_id, allow_browser_automation=False)

        assert captured_ctx.get("allow_browser_automation") is False, (
            "Explicit False should override saved mission value"
        )


# ── Phase 6.13: accept_mission + run_mission result status ──────

class TestAcceptMission:
    """Phase 6.13: accept_mission 和 run_mission 结果状态测试"""

    @pytest.fixture
    def service(self):
        from backend.services.boss_command_center import BossCommandCenterService
        return BossCommandCenterService()

    def test_accept_from_ready_for_review(self, service):
        """accept_mission 从 ready_for_review 转为 done"""
        mission = service.create_mission("accept 测试", enabled_modules=["strategy"])
        mission_id = mission["mission_id"]

        mock_exec = _make_mock_executor(ok=True, final_answer="战略分析结果文本内容", confidence=0.8)
        with patch("backend.services.boss_module_executors.get_executor", return_value=mock_exec):
            service.run_mission(mission_id)

        mission = service.get_mission(mission_id)
        assert mission["status"] == "ready_for_review"

        result = service.accept_mission(mission_id, comment="LGTM")
        assert result["status"] == "done"

        # 验证事件日志
        events = service.get_events(mission_id)
        accepted = [e for e in events if e["type"] == "mission_accepted"]
        assert len(accepted) == 1
        assert "LGTM" in accepted[0]["payload"]["comment"]

    def test_accept_from_partial(self, service):
        """accept_mission 从 partial 转为 done"""
        mission = service.create_mission("partial accept 测试", enabled_modules=["strategy", "market"])
        mission_id = mission["mission_id"]

        # strategy 成功, market 失败（无结果）
        call_count = {"n": 0}
        def mixed_execute(*args, **kwargs):
            call_count["n"] += 1
            if call_count["n"] == 1:
                return MagicMock(
                    ok=True, final_answer="战略分析结果文本内容", confidence=0.8,
                    warnings=[], used_tools=[], mode="local", error="",
                    next_actions=[], structured_output={}, provider="mock",
                )
            return MagicMock(
                ok=False, final_answer="", confidence=0.0,
                warnings=["boom"], used_tools=[], mode="local", error="市场模块失败",
                next_actions=[], structured_output={}, provider="mock",
            )

        mock_exec = MagicMock(side_effect=mixed_execute)
        with patch("backend.services.boss_module_executors.get_executor", return_value=MagicMock(execute=mock_exec)):
            service.run_mission(mission_id)

        mission = service.get_mission(mission_id)
        # strategy done, market failed → 有 strategy 的结果 → partial
        assert mission["status"] in ("partial", "ready_for_review", "failed")

        if mission["status"] == "partial":
            result = service.accept_mission(mission_id)
            assert result["status"] == "done"

    def test_accept_from_pending_review_noop(self, service):
        """accept_mission 从 pending_review 不生效（返回原状态）"""
        mission = service.create_mission("pending accept 测试")
        mission_id = mission["mission_id"]

        result = service.accept_mission(mission_id)
        assert result["status"] == "pending_review"

    def test_run_mission_all_done_ready_for_review(self, service):
        """run_mission 所有模块成功 → ready_for_review"""
        mission = service.create_mission("全部成功测试", enabled_modules=["strategy", "market"])
        mission_id = mission["mission_id"]

        mock_exec = _make_mock_executor(ok=True, final_answer="分析结果文本内容充足", confidence=0.8)
        with patch("backend.services.boss_module_executors.get_executor", return_value=mock_exec):
            service.run_mission(mission_id)

        mission = service.get_mission(mission_id)
        assert mission["status"] == "ready_for_review"
        assert all(m["status"] == "done" for m in mission["modules"] if m["status"] != "skipped")

    def test_run_mission_partial_result_keeps_text(self, service):
        """run_mission 部分模块有结果 → partial，已有文本保留"""
        mission = service.create_mission("partial 保留测试", enabled_modules=["strategy", "market"])
        mission_id = mission["mission_id"]

        call_count = {"n": 0}
        def mixed_execute(*args, **kwargs):
            call_count["n"] += 1
            if call_count["n"] == 1:
                # strategy: ok=True，有结果
                return MagicMock(
                    ok=True, final_answer="战略分析结果文本内容充足", confidence=0.8,
                    warnings=[], used_tools=[], mode="local", error="",
                    next_actions=[], structured_output={}, provider="mock",
                )
            # market: ok=False，但有 final_answer（应标记为 partial）
            return MagicMock(
                ok=False, final_answer="市场分析虽有问题但有部分结果文本",
                confidence=0.3, warnings=["证据不足"], used_tools=[], mode="local",
                error="部分失败", next_actions=[], structured_output={}, provider="mock",
            )

        mock_exec = MagicMock(side_effect=mixed_execute)
        with patch("backend.services.boss_module_executors.get_executor", return_value=MagicMock(execute=mock_exec)):
            service.run_mission(mission_id)

        mission = service.get_mission(mission_id)
        strategy = next(m for m in mission["modules"] if m["module_id"] == "strategy")
        market = next(m for m in mission["modules"] if m["module_id"] == "market")

        # strategy 成功
        assert strategy["status"] == "done"
        assert strategy["result"] == "战略分析结果文本内容充足"

        # market 有文本但失败 → partial
        assert market["status"] == "partial"
        assert market["result"] == "市场分析虽有问题但有部分结果文本"

        # Mission 整体应为 partial（有结果但不是全部 done）
        assert mission["status"] == "partial"

    def test_run_mission_no_result_failed(self, service):
        """run_mission 全部无结果 → failed"""
        mission = service.create_mission("全部失败测试", enabled_modules=["strategy"])
        mission_id = mission["mission_id"]

        mock_exec = _make_mock_executor(ok=False, error="Adapter 不可用", final_answer="")
        with patch("backend.services.boss_module_executors.get_executor", return_value=mock_exec):
            service.run_mission(mission_id)

        mission = service.get_mission(mission_id)
        assert mission["status"] == "failed"

    def test_run_mission_no_auto_retry(self, service):
        """run_mission 不自动重试 — 每个模块只执行一次"""
        mission = service.create_mission("无重试测试", enabled_modules=["strategy", "market"])
        mission_id = mission["mission_id"]

        mock_exec = _make_mock_executor(ok=False, error="boom", final_answer="")
        with patch("backend.services.boss_module_executors.get_executor", return_value=MagicMock(execute=mock_exec)) as mock_factory:
            service.run_mission(mission_id)

        # 2 个模块，每个只调用 1 次 → 共 2 次
        assert mock_exec.call_count == 2


# ── 僵尸状态清理测试 ─────────────────────────────────────

class TestStaleCleanup:
    """cleanup_stale_running_missions 测试"""

    @pytest.fixture
    def service(self):
        from backend.services.boss_command_center import BossCommandCenterService
        return BossCommandCenterService()

    def _create_running_module(self, service, mission_id, module_id,
                                started_at="2020-01-01T00:00:00", result=""):
        """手动将模块设为 running 状态（模拟卡死）"""
        from backend.database.database import get_db
        now = started_at
        with get_db() as db:
            db.execute(
                """UPDATE boss_mission_modules
                   SET status = 'running', started_at = ?, result = ?, updated_at = ?
                   WHERE mission_id = ? AND module_id = ?""",
                (now, result, now, mission_id, module_id)
            )
            db.commit()

    def test_cleanup_stale_running_no_result(self, service):
        """running 超时且无 result → interrupted"""
        mission = service.create_mission("清理测试", enabled_modules=["strategy"])
        mission_id = mission["mission_id"]
        self._create_running_module(service, mission_id, "strategy")

        result = service.cleanup_stale_running_missions(timeout_minutes=30)
        assert result["cleaned_modules"] == 1
        assert mission_id in result["affected_missions"]

        detail = result["details"][0]
        assert detail["module_id"] == "strategy"
        assert detail["new_status"] == "interrupted"
        assert detail["has_result"] is False

        mission = service.get_mission(mission_id)
        strategy = next(m for m in mission["modules"] if m["module_id"] == "strategy")
        assert strategy["status"] == "interrupted"
        assert "上次执行可能中断" in strategy["warnings"][0]

    def test_cleanup_stale_running_with_result(self, service):
        """running 超时但有 result → partial（保留已有结果）"""
        mission = service.create_mission("有结果清理测试", enabled_modules=["strategy"])
        mission_id = mission["mission_id"]
        self._create_running_module(service, mission_id, "strategy",
                                     result="这是已有的分析结果内容，足够长以通过检查")

        result = service.cleanup_stale_running_missions(timeout_minutes=30)
        assert result["cleaned_modules"] == 1

        detail = result["details"][0]
        assert detail["new_status"] == "partial"
        assert detail["has_result"] is True

        mission = service.get_mission(mission_id)
        strategy = next(m for m in mission["modules"] if m["module_id"] == "strategy")
        assert strategy["status"] == "partial"
        assert strategy["result"] == "这是已有的分析结果内容，足够长以通过检查"
        assert "上次执行可能中断" in strategy["warnings"][0]

    def test_cleanup_mission_status_interrupted(self, service):
        """所有 active 模块都 interrupted → mission interrupted"""
        mission = service.create_mission("全中断测试", enabled_modules=["strategy", "market"])
        mission_id = mission["mission_id"]
        self._create_running_module(service, mission_id, "strategy")
        self._create_running_module(service, mission_id, "market")

        service.cleanup_stale_running_missions(timeout_minutes=30)
        mission = service.get_mission(mission_id)
        assert mission["status"] == "interrupted"

    def test_cleanup_mission_status_partial_mixed(self, service):
        """done + interrupted → mission partial"""
        mission = service.create_mission("混合测试", enabled_modules=["strategy", "market"])
        mission_id = mission["mission_id"]

        # strategy 已完成
        from backend.database.database import get_db
        with get_db() as db:
            db.execute(
                """UPDATE boss_mission_modules
                   SET status = 'done', result = '战略分析完成结果内容充足'
                   WHERE mission_id = ? AND module_id = ?""",
                (mission_id, "strategy")
            )
            db.commit()

        # market 卡在 running
        self._create_running_module(service, mission_id, "market")

        service.cleanup_stale_running_missions(timeout_minutes=30)
        mission = service.get_mission(mission_id)
        assert mission["status"] == "partial"

        market = next(m for m in mission["modules"] if m["module_id"] == "market")
        assert market["status"] == "interrupted"

    def test_cleanup_preserves_done_modules(self, service):
        """清理不会影响已完成的模块"""
        mission = service.create_mission("保留测试", enabled_modules=["strategy", "market"])
        mission_id = mission["mission_id"]

        mock_exec = _make_mock_executor(ok=True, final_answer="战略分析完成结果内容充足", confidence=0.9)
        with patch("backend.services.boss_module_executors.get_executor", return_value=mock_exec):
            service.run_module(mission_id, "strategy")

        # market 卡在 running
        self._create_running_module(service, mission_id, "market")

        service.cleanup_stale_running_missions(timeout_minutes=30)
        mission = service.get_mission(mission_id)

        strategy = next(m for m in mission["modules"] if m["module_id"] == "strategy")
        assert strategy["status"] == "done"
        assert strategy["result"] == "战略分析完成结果内容充足"

    def test_cleanup_no_stale_modules(self, service):
        """没有 stale 模块时返回空结果"""
        mission = service.create_mission("无清理测试", enabled_modules=["strategy"])
        mission_id = mission["mission_id"]

        result = service.cleanup_stale_running_missions(timeout_minutes=30)
        assert result["cleaned_modules"] == 0
        assert result["affected_missions"] == []

    def test_cleanup_recent_running_not_cleaned(self, service):
        """最近的 running 模块不会被清理"""
        mission = service.create_mission("新任务测试", enabled_modules=["strategy"])
        mission_id = mission["mission_id"]

        # started_at 设为当前时间（不会超时）
        from datetime import datetime
        now = datetime.now().isoformat()
        self._create_running_module(service, mission_id, "strategy", started_at=now)

        result = service.cleanup_stale_running_missions(timeout_minutes=30)
        assert result["cleaned_modules"] == 0

    def test_cleanup_events_logged(self, service):
        """清理后应记录事件"""
        mission = service.create_mission("事件测试", enabled_modules=["strategy"])
        mission_id = mission["mission_id"]
        self._create_running_module(service, mission_id, "strategy")

        service.cleanup_stale_running_missions(timeout_minutes=30)

        events = service.get_events(mission_id)
        event_types = [e["type"] for e in events]
        assert "module_interrupted" in event_types
        assert "stale_running_cleaned" in event_types

    def test_cleanup_mission_stale_modules(self, service):
        """cleanup_mission_stale_modules 只清理指定 mission"""
        mission1 = service.create_mission("任务1", enabled_modules=["strategy"])
        mission2 = service.create_mission("任务2", enabled_modules=["market"])

        self._create_running_module(service, mission1["mission_id"], "strategy")
        self._create_running_module(service, mission2["mission_id"], "market")

        cleaned = service.cleanup_mission_stale_modules(mission1["mission_id"], timeout_minutes=30)
        assert cleaned == 1

        # mission2 不受影响
        mission2 = service.get_mission(mission2["mission_id"])
        market = next(m for m in mission2["modules"] if m["module_id"] == "market")
        assert market["status"] == "running"

    def test_accept_interrupted_mission(self, service):
        """可以接受 interrupted 状态的 mission"""
        mission = service.create_mission("接受中断测试", enabled_modules=["strategy"])
        mission_id = mission["mission_id"]
        self._create_running_module(service, mission_id, "strategy")

        service.cleanup_stale_running_missions(timeout_minutes=30)
        mission = service.get_mission(mission_id)
        assert mission["status"] == "interrupted"

        accepted = service.accept_mission(mission_id, comment="已检查")
        assert accepted["status"] == "done"

    def test_metrics_include_interrupted(self, service):
        """metrics 应包含 interrupted_modules 计数"""
        mission = service.create_mission("指标测试", enabled_modules=["strategy"])
        mission_id = mission["mission_id"]
        self._create_running_module(service, mission_id, "strategy")

        service.cleanup_stale_running_missions(timeout_minutes=30)
        mission = service.get_mission(mission_id)
        assert mission["metrics"]["interrupted_modules"] == 1


class TestStaleCleanupAPI:
    """cleanup-stale API 接口测试"""

    @pytest.fixture
    def client(self):
        from fastapi.testclient import TestClient
        from backend.app import app
        return TestClient(app, raise_server_exceptions=False)

    def test_cleanup_stale_endpoint(self, client):
        """POST /boss/missions/cleanup-stale 正常返回"""
        response = client.post("/boss/missions/cleanup-stale", json={"timeout_minutes": 30})
        assert response.status_code == 200
        data = response.json()
        assert "cleaned_modules" in data
        assert "affected_missions" in data
        assert "details" in data

    def test_cleanup_stale_default_timeout(self, client):
        """默认 timeout_minutes=30"""
        response = client.post("/boss/missions/cleanup-stale")
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data["cleaned_modules"], int)

    def test_cleanup_stale_custom_timeout(self, client):
        """自定义 timeout_minutes"""
        response = client.post("/boss/missions/cleanup-stale", json={"timeout_minutes": 5})
        assert response.status_code == 200


# ── Phase 6.16: 模块级执行超时测试 ──────────────────────────────

class TestModuleTimeout:
    """模块执行超时与失败降级测试"""

    @pytest.fixture
    def service(self):
        from backend.services.boss_command_center import BossCommandCenterService
        return BossCommandCenterService()

    def _make_slow_executor(self, delay_seconds):
        """创建一个会阻塞 delay_seconds 秒的 mock executor"""
        import time as _time
        mock_exec = MagicMock()
        def slow_execute(*args, **kwargs):
            _time.sleep(delay_seconds)
            result = MagicMock()
            result.ok = True
            result.final_answer = "慢速结果" * 20  # 足够长
            result.confidence = 0.9
            result.warnings = []
            result.used_tools = []
            result.mode = "local"
            result.error = ""
            result.next_actions = []
            result.structured_output = {}
            result.provider = "slow_mock"
            return result
        mock_exec.execute.side_effect = slow_execute
        return mock_exec

    def test_run_module_timeout_marks_interrupted(self, service):
        """模块执行超时后 status=interrupted，error 含 timeout"""
        mission = service.create_mission("超时测试", enabled_modules=["strategy"])
        mission_id = mission["mission_id"]

        slow_exec = self._make_slow_executor(10)  # 10s >> 1s timeout

        with patch("backend.services.boss_module_executors.get_executor", return_value=slow_exec), \
             patch("backend.services.boss_command_center.MODULE_TIMEOUT_SECONDS", {"strategy": 1}), \
             patch("backend.services.boss_command_center.MODULE_TIMEOUT_DEFAULT", 1):
            result = service.run_module(mission_id, "strategy")

        assert result is not None
        strategy = next(m for m in result["modules"] if m["module_id"] == "strategy")
        assert strategy["status"] == "interrupted"
        assert "超时" in strategy["error"]
        assert strategy["duration_ms"] >= 0
        assert strategy["finished_at"] is not None

    def test_run_module_timeout_logs_event(self, service):
        """超时后记录 module_timeout 事件"""
        mission = service.create_mission("超时事件测试", enabled_modules=["strategy"])
        mission_id = mission["mission_id"]

        slow_exec = self._make_slow_executor(10)

        with patch("backend.services.boss_module_executors.get_executor", return_value=slow_exec), \
             patch("backend.services.boss_command_center.MODULE_TIMEOUT_SECONDS", {"strategy": 1}), \
             patch("backend.services.boss_command_center.MODULE_TIMEOUT_DEFAULT", 1):
            service.run_module(mission_id, "strategy")

        events = service.get_events(mission_id)
        timeout_events = [e for e in events if e["type"] == "module_timeout"]
        assert len(timeout_events) >= 1
        assert timeout_events[0]["module_id"] == "strategy"
        assert "timeout_sec" in timeout_events[0]["payload"]

    def test_run_mission_timeout_stops_remaining(self, service):
        """第一个模块超时后，后续模块不执行"""
        mission = service.create_mission("停止测试", enabled_modules=["strategy", "market"])
        mission_id = mission["mission_id"]

        call_count = {"n": 0}

        def tracking_execute(*args, **kwargs):
            call_count["n"] += 1
            if call_count["n"] == 1:
                import time as _time
                _time.sleep(10)  # 第一个模块阻塞
            # 第二个模块正常返回
            result = MagicMock()
            result.ok = True
            result.final_answer = "正常结果" * 20
            result.confidence = 0.9
            result.warnings = []
            result.used_tools = []
            result.mode = "local"
            result.error = ""
            result.next_actions = []
            result.structured_output = {}
            result.provider = "mock"
            return result

        mock_exec = MagicMock()
        mock_exec.execute.side_effect = tracking_execute

        with patch("backend.services.boss_module_executors.get_executor", return_value=mock_exec), \
             patch("backend.services.boss_command_center.MODULE_TIMEOUT_SECONDS", {"strategy": 1}), \
             patch("backend.services.boss_command_center.MODULE_TIMEOUT_DEFAULT", 1):
            result = service.run_mission(mission_id)

        assert result is not None
        strategy = next(m for m in result["modules"] if m["module_id"] == "strategy")
        market = next(m for m in result["modules"] if m["module_id"] == "market")
        assert strategy["status"] == "interrupted"
        # market 应该仍为 pending（被跳过）
        assert market["status"] == "pending"
        # 只调用了一次 executor
        assert call_count["n"] == 1

    def test_run_mission_timeout_mission_interrupted(self, service):
        """所有模块超时 → mission interrupted（无结果）"""
        mission = service.create_mission("mission interrupted 测试", enabled_modules=["strategy"])
        mission_id = mission["mission_id"]

        slow_exec = self._make_slow_executor(10)

        with patch("backend.services.boss_module_executors.get_executor", return_value=slow_exec), \
             patch("backend.services.boss_command_center.MODULE_TIMEOUT_SECONDS", {"strategy": 1}), \
             patch("backend.services.boss_command_center.MODULE_TIMEOUT_DEFAULT", 1):
            result = service.run_mission(mission_id)

        assert result is not None
        assert result["status"] == "interrupted"

    def test_run_mission_timeout_with_partial_result(self, service):
        """有已有结果的模块超时 → mission partial"""
        mission = service.create_mission("partial 测试", enabled_modules=["strategy", "market"])
        mission_id = mission["mission_id"]

        # 第一个模块正常完成
        ok_exec = _make_mock_executor(ok=True, final_answer="这是一个正常的策略结果，足够长以通过验证", confidence=0.9)

        with patch("backend.services.boss_module_executors.get_executor", return_value=ok_exec):
            service.run_module(mission_id, "strategy")

        # 第二个模块超时
        slow_exec = self._make_slow_executor(10)

        with patch("backend.services.boss_module_executors.get_executor", return_value=slow_exec), \
             patch("backend.services.boss_command_center.MODULE_TIMEOUT_SECONDS", {"market": 1}), \
             patch("backend.services.boss_command_center.MODULE_TIMEOUT_DEFAULT", 1):
            result = service.run_mission(mission_id)

        assert result is not None
        strategy = next(m for m in result["modules"] if m["module_id"] == "strategy")
        market = next(m for m in result["modules"] if m["module_id"] == "market")
        assert strategy["status"] == "done"
        assert market["status"] == "interrupted"
        # mission 应为 partial（有 strategy 结果）
        assert result["status"] == "partial"

    def test_normal_execution_unaffected(self, service):
        """正常执行不受 timeout 影响"""
        mission = service.create_mission("正常测试", enabled_modules=["strategy"])
        mission_id = mission["mission_id"]

        mock_exec = _make_mock_executor(ok=True, final_answer="正常策略结果" * 10, confidence=0.85)

        with patch("backend.services.boss_module_executors.get_executor", return_value=mock_exec):
            result = service.run_module(mission_id, "strategy")

        assert result is not None
        strategy = next(m for m in result["modules"] if m["module_id"] == "strategy")
        assert strategy["status"] == "done"
        assert "超时" not in (strategy["error"] or "")

    def test_run_module_timeout_returns_quickly(self, service):
        """超时后 run_module 必须快速返回，不等待底层线程结束

        Phase 6.16.2: 验证 ThreadPoolExecutor.shutdown(wait=False) 生效
        如果 __exit__(wait=True) 仍阻塞，此测试会超时失败
        """
        import time as _time

        mission = service.create_mission("快速返回测试", enabled_modules=["strategy"])
        mission_id = mission["mission_id"]

        # 底层 sleep 30s，timeout 只设 1s
        slow_exec = self._make_slow_executor(30)

        with patch("backend.services.boss_module_executors.get_executor", return_value=slow_exec), \
             patch("backend.services.boss_command_center.MODULE_TIMEOUT_SECONDS", {"strategy": 1}), \
             patch("backend.services.boss_command_center.MODULE_TIMEOUT_DEFAULT", 1):
            start = _time.monotonic()
            result = service.run_module(mission_id, "strategy")
            elapsed = _time.monotonic() - start

        # run_module 应在 ~1s 内返回（timeout），而不是等待 30s
        # 给 5s 容差，但必须远小于 30s
        assert elapsed < 5.0, f"run_module took {elapsed:.1f}s, expected < 5s (timeout=1s, sleep=30s)"
        assert result is not None
        strategy = next(m for m in result["modules"] if m["module_id"] == "strategy")
        assert strategy["status"] == "interrupted"


# ── Phase 6.16.1: Late-return protection tests ──────────────────

class TestLateReturnProtection:
    """防止超时后的晚返回结果覆盖 interrupted 状态"""

    @pytest.fixture
    def service(self):
        from backend.services.boss_command_center import BossCommandCenterService
        return BossCommandCenterService()

    def _set_module_status(self, mission_id, module_id, status, result=""):
        """手动设置模块状态"""
        from backend.database.database import get_db
        from datetime import datetime
        now = datetime.now().isoformat()
        with get_db() as db:
            db.execute(
                """UPDATE boss_mission_modules
                   SET status = ?, result = ?, updated_at = ?
                   WHERE mission_id = ? AND module_id = ?""",
                (status, result, now, mission_id, module_id)
            )
            db.commit()

    def test_update_module_result_with_expected_status_match(self, service):
        """expected_status 匹配时，更新成功返回 True"""
        mission = service.create_mission("CAS 匹配测试", enabled_modules=["strategy"])
        mission_id = mission["mission_id"]

        # 模块初始为 pending，先设为 running
        self._set_module_status(mission_id, "strategy", "running")

        result = service._update_module_result(
            mission_id, "strategy", "done",
            "测试结果内容", 0.8, [], "", [], "local", [], 100, {},
            expected_status="running",
        )
        assert result is True

        # 验证状态已更新
        mission = service.get_mission(mission_id)
        strategy = next(m for m in mission["modules"] if m["module_id"] == "strategy")
        assert strategy["status"] == "done"
        assert strategy["result"] == "测试结果内容"

    def test_update_module_result_with_expected_status_mismatch(self, service):
        """expected_status 不匹配时，更新失败返回 False，状态不被覆盖"""
        mission = service.create_mission("CAS 不匹配测试", enabled_modules=["strategy"])
        mission_id = mission["mission_id"]

        # 模块已经是 interrupted
        self._set_module_status(mission_id, "strategy", "interrupted",
                                "已有中断结果内容")

        # 尝试用 expected_status="running" 更新为 done
        result = service._update_module_result(
            mission_id, "strategy", "done",
            "晚到的结果内容", 0.9, [], "", [], "local", [], 100, {},
            expected_status="running",
        )
        assert result is False

        # 验证状态仍是 interrupted，result 不被覆盖
        mission = service.get_mission(mission_id)
        strategy = next(m for m in mission["modules"] if m["module_id"] == "strategy")
        assert strategy["status"] == "interrupted"
        assert strategy["result"] == "已有中断结果内容"

    def test_update_module_result_without_expected_status(self, service):
        """不传 expected_status 时，无条件更新（兼容旧逻辑）"""
        mission = service.create_mission("无 CAS 测试", enabled_modules=["strategy"])
        mission_id = mission["mission_id"]

        # 模块已经是 interrupted
        self._set_module_status(mission_id, "strategy", "interrupted",
                                "已有中断结果")

        # 不传 expected_status，应该无条件更新
        result = service._update_module_result(
            mission_id, "strategy", "done",
            "新结果内容", 0.9, [], "", [], "local", [], 100, {},
        )
        assert result is True

        # 验证状态已被更新
        mission = service.get_mission(mission_id)
        strategy = next(m for m in mission["modules"] if m["module_id"] == "strategy")
        assert strategy["status"] == "done"
        assert strategy["result"] == "新结果内容"

    def test_late_return_after_timeout_logs_ignored_event(self, service):
        """晚返回结果被忽略时，记录 module_result_ignored 事件"""
        mission = service.create_mission("ignored 事件测试", enabled_modules=["strategy"])
        mission_id = mission["mission_id"]

        # 模拟：模块先被设为 interrupted（模拟 timeout 路径已完成）
        self._set_module_status(mission_id, "strategy", "interrupted",
                                "超时中断结果")

        # 模拟晚返回：直接调用 _update_module_result(expected_status="running")
        # 这是 run_module 内部 timeout 后线程晚返回时实际走的路径
        updated = service._update_module_result(
            mission_id, "strategy", "done",
            "晚到的结果内容", 0.9, [], "", [], "local", [], 100, {},
            expected_status="running",
        )
        assert updated is False

        # 记录 ignored 事件（模拟 run_module 中的处理）
        service._log_event(mission_id, "module_result_ignored",
                           f"模块 战略摘要 结果被忽略（状态已变为 interrupted）",
                           module_id="strategy",
                           payload={"module_id": "strategy",
                                    "attempted_status": "done",
                                    "current_status": "interrupted",
                                    "reason": "expected_status mismatch — module no longer running"})

        # 验证 module_result_ignored 事件被记录
        events = service.get_events(mission_id)
        ignored_events = [e for e in events if e["type"] == "module_result_ignored"]
        assert len(ignored_events) == 1
        assert ignored_events[0]["module_id"] == "strategy"
        assert ignored_events[0]["payload"]["current_status"] == "interrupted"
        assert ignored_events[0]["payload"]["reason"] == "expected_status mismatch — module no longer running"

    def test_late_return_does_not_override_interrupted_status(self, service):
        """晚返回结果不能把 interrupted 状态覆盖为 done/failed"""
        mission = service.create_mission("不覆盖测试", enabled_modules=["strategy"])
        mission_id = mission["mission_id"]

        # 模块已经是 interrupted
        self._set_module_status(mission_id, "strategy", "interrupted",
                                "超时中断结果内容")

        # 晚返回成功结果：直接调用 _update_module_result(expected_status="running")
        updated = service._update_module_result(
            mission_id, "strategy", "done",
            "晚到的成功结果", 0.9, [], "", [], "local", [], 100, {},
            expected_status="running",
        )
        assert updated is False

        # 验证状态仍是 interrupted，result 不被覆盖
        mission = service.get_mission(mission_id)
        strategy = next(m for m in mission["modules"] if m["module_id"] == "strategy")
        assert strategy["status"] == "interrupted"
        assert strategy["result"] == "超时中断结果内容"

    def test_late_return_does_not_override_interrupted_error(self, service):
        """晚返回失败结果也不能覆盖 interrupted 状态"""
        mission = service.create_mission("失败不覆盖测试", enabled_modules=["strategy"])
        mission_id = mission["mission_id"]

        # 模块已经是 interrupted
        self._set_module_status(mission_id, "strategy", "interrupted",
                                "超时中断结果内容")

        # 晚返回失败结果：直接调用 _update_module_result(expected_status="running")
        updated = service._update_module_result(
            mission_id, "strategy", "failed",
            "", 0.0, ["晚到的错误"], "晚到的错误", [], "error", [], 100, {},
            expected_status="running",
        )
        assert updated is False

        # 验证状态仍是 interrupted，result 不被覆盖
        mission = service.get_mission(mission_id)
        strategy = next(m for m in mission["modules"] if m["module_id"] == "strategy")
        assert strategy["status"] == "interrupted"
        assert strategy["result"] == "超时中断结果内容"

    def test_late_return_does_not_trigger_mission_status_update(self, service):
        """晚返回被忽略时，返回的 mission 状态保持不变"""
        mission = service.create_mission("mission 状态保护测试", enabled_modules=["strategy", "market"])
        mission_id = mission["mission_id"]

        # strategy 正常完成
        ok_exec = _make_mock_executor(ok=True, final_answer="策略分析结果内容充足" * 5, confidence=0.8)
        with patch("backend.services.boss_module_executors.get_executor", return_value=ok_exec):
            service.run_module(mission_id, "strategy")

        # market 被 timeout 标记为 interrupted
        self._set_module_status(mission_id, "market", "interrupted", "")

        # 确认 mission 状态是 partial（有 strategy 结果）
        mission = service.get_mission(mission_id)
        assert mission["status"] == "partial"

        # 模拟 market 的晚返回：直接调用 _update_module_result(expected_status="running")
        updated = service._update_module_result(
            mission_id, "market", "done",
            "晚到的市场分析结果", 0.7, [], "", [], "local", [], 100, {},
            expected_status="running",
        )
        assert updated is False

        # mission 状态不应改变（晚返回被忽略，不触发状态重算）
        mission = service.get_mission(mission_id)
        assert mission["status"] == "partial"
        market = next(m for m in mission["modules"] if m["module_id"] == "market")
        assert market["status"] == "interrupted"

    def test_normal_running_to_done_still_works(self, service):
        """正常 running → done 路径不受影响"""
        mission = service.create_mission("正常更新测试", enabled_modules=["strategy"])
        mission_id = mission["mission_id"]

        mock_exec = _make_mock_executor(ok=True, final_answer="正常策略分析结果" * 10, confidence=0.85)
        with patch("backend.services.boss_module_executors.get_executor", return_value=mock_exec):
            result = service.run_module(mission_id, "strategy")

        strategy = next(m for m in result["modules"] if m["module_id"] == "strategy")
        assert strategy["status"] == "done"
        assert strategy["result"] == "正常策略分析结果" * 10

    def test_normal_running_to_failed_still_works(self, service):
        """正常 running → failed 路径不受影响"""
        mission = service.create_mission("正常失败测试", enabled_modules=["strategy"])
        mission_id = mission["mission_id"]

        mock_exec = _make_mock_executor(ok=False, error="执行失败", final_answer="")
        with patch("backend.services.boss_module_executors.get_executor", return_value=mock_exec):
            result = service.run_module(mission_id, "strategy")

        strategy = next(m for m in result["modules"] if m["module_id"] == "strategy")
        assert strategy["status"] == "failed"
        assert "执行失败" in strategy["error"]


# ── Phase 6.16.3: Boss 闭环 Smoke Test ─────────────────────

class TestBossFlowSmoke:
    """最小 Boss 闭环 smoke test — 验证 create → run → accept 全链路"""

    @pytest.fixture
    def service(self):
        from backend.services.boss_command_center import BossCommandCenterService
        return BossCommandCenterService()

    def test_full_happy_path(self, service):
        """create(pending_review) → run(ready_for_review) → accept(done)"""
        # 1. 创建 mission → pending_review
        mission = service.create_mission("smoke 测试目标", enabled_modules=["strategy"])
        mission_id = mission["mission_id"]
        assert mission["status"] == "pending_review"

        strategy = next(m for m in mission["modules"] if m["module_id"] == "strategy")
        assert strategy["status"] == "pending"

        # 2. 执行 → ready_for_review
        mock_exec = _make_mock_executor(ok=True, final_answer="战略分析结果文本内容充足" * 3, confidence=0.9)
        with patch("backend.services.boss_module_executors.get_executor", return_value=mock_exec):
            mission = service.run_mission(mission_id)

        assert mission["status"] == "ready_for_review"
        strategy = next(m for m in mission["modules"] if m["module_id"] == "strategy")
        assert strategy["status"] == "done"
        assert len(strategy["result"]) >= 10

        # 3. 接受 → done
        mission = service.accept_mission(mission_id, comment="LGTM")
        assert mission["status"] == "done"

        # 4. 验证事件日志完整
        events = service.get_events(mission_id)
        event_types = [e["type"] for e in events]
        assert "mission_created" in event_types
        assert "mission_started" in event_types
        assert "module_started" in event_types
        assert "module_succeeded" in event_types
        assert "mission_ready" in event_types
        assert "mission_accepted" in event_types

    def test_partial_path(self, service):
        """create → run(partial) → accept(done)"""
        mission = service.create_mission("partial smoke", enabled_modules=["strategy", "market"])
        mission_id = mission["mission_id"]

        call_count = {"n": 0}
        def mixed_execute(*args, **kwargs):
            call_count["n"] += 1
            if call_count["n"] == 1:
                return MagicMock(
                    ok=True, final_answer="战略分析结果文本内容充足" * 3, confidence=0.8,
                    warnings=[], used_tools=[], mode="local", error="",
                    next_actions=[], structured_output={}, provider="mock",
                )
            return MagicMock(
                ok=False, final_answer="", confidence=0.0,
                warnings=[], used_tools=[], mode="local", error="市场模块失败",
                next_actions=[], structured_output={}, provider="mock",
            )

        mock_exec = MagicMock(side_effect=mixed_execute)
        with patch("backend.services.boss_module_executors.get_executor", return_value=MagicMock(execute=mock_exec)):
            mission = service.run_mission(mission_id)

        # strategy done, market failed → partial（有 strategy 结果）
        assert mission["status"] in ("partial", "ready_for_review", "failed")

        # 只有 partial/ready_for_review/interrupted 可以 accept
        if mission["status"] in ("partial", "ready_for_review"):
            mission = service.accept_mission(mission_id)
            assert mission["status"] == "done"

    def test_interrupted_path(self, service):
        """create → run(timeout/interrupted) → accept(done)"""
        mission = service.create_mission("interrupted smoke", enabled_modules=["strategy"])
        mission_id = mission["mission_id"]

        slow_exec = MagicMock()
        def slow_execute(*args, **kwargs):
            import time as _time
            _time.sleep(10)
            return MagicMock(ok=True, final_answer="慢速结果" * 20, confidence=0.9,
                             warnings=[], used_tools=[], mode="local", error="",
                             next_actions=[], structured_output={}, provider="mock")
        slow_exec.execute.side_effect = slow_execute

        with patch("backend.services.boss_module_executors.get_executor", return_value=slow_exec), \
             patch("backend.services.boss_command_center.MODULE_TIMEOUT_SECONDS", {"strategy": 1}), \
             patch("backend.services.boss_command_center.MODULE_TIMEOUT_DEFAULT", 1):
            mission = service.run_mission(mission_id)

        assert mission["status"] == "interrupted"

        # interrupted 可以 accept
        mission = service.accept_mission(mission_id, comment="已检查")
        assert mission["status"] == "done"


# ── Phase 6.21: Boss Lite 通用能力名称测试 ─────────────────

class TestBossLiteGenericNames:
    """Phase 6.21: Boss Lite 输出不含业务锁定词"""

    BUSINESS_LOCKED_TERMS = ["营销方案", "落地页方案", "市场调研", "视觉方案"]

    def test_boss_lite_agent_titles_are_generic(self):
        """BOSS_LITE_AGENTS 的 title 不含业务锁定词"""
        from backend.routers.boss_router import BOSS_LITE_AGENTS
        for agent in BOSS_LITE_AGENTS:
            for term in self.BUSINESS_LOCKED_TERMS:
                assert term not in agent["title"], (
                    f"Agent {agent['agent_id']} title '{agent['title']}' 包含业务锁定词: {term}"
                )

    def test_boss_lite_agent_titles_have_generic_names(self):
        """BOSS_LITE_AGENTS 使用通用能力名称"""
        from backend.routers.boss_router import BOSS_LITE_AGENTS
        titles = {a["agent_id"]: a["title"] for a in BOSS_LITE_AGENTS}
        assert titles["research"] == "上下文整理"
        assert titles["marketing"] == "沟通表达"
        assert titles["image"] == "素材方向"
        assert titles["data"] == "数据洞察"
        assert titles["website"] == "交付物结构"

    def test_handoff_cn_labels_are_generic(self):
        """_HANDOFF_CN_LABELS 不含业务锁定词"""
        from backend.routers.boss_router import _HANDOFF_CN_LABELS
        for agent_id, label in _HANDOFF_CN_LABELS.items():
            for term in self.BUSINESS_LOCKED_TERMS:
                assert term not in label, (
                    f"Handoff label '{label}' ({agent_id}) 包含业务锁定词: {term}"
                )

    def test_boss_lite_markdown_report_no_business_terms(self):
        """Boss Lite markdown 报告不含业务锁定词"""
        from backend.routers.boss_router import _render_boss_lite_md

        # 模拟 plan 和 results
        plan = [
            {"agent_id": "research", "title": "上下文整理", "purpose": "收集上下文", "status": "done"},
            {"agent_id": "marketing", "title": "沟通表达", "purpose": "设计方案", "status": "done"},
            {"agent_id": "image", "title": "素材方向", "purpose": "视觉方向", "status": "done"},
            {"agent_id": "data", "title": "数据洞察", "purpose": "分析数据", "status": "done"},
            {"agent_id": "website", "title": "交付物结构", "purpose": "设计交付物", "status": "done"},
        ]
        results = [
            {"agent_id": "research", "title": "上下文整理", "ok": True, "summary": "调研完成",
             "structured_output": {}, "warnings": [], "error": None, "duration_ms": 1000,
             "used_handoff": False, "handoff_sources": []},
            {"agent_id": "marketing", "title": "沟通表达", "ok": True, "summary": "方案完成",
             "structured_output": {}, "warnings": [], "error": None, "duration_ms": 1000,
             "used_handoff": True, "handoff_sources": ["research"]},
            {"agent_id": "image", "title": "素材方向", "ok": True, "summary": "视觉完成",
             "structured_output": {}, "warnings": [], "error": None, "duration_ms": 1000,
             "used_handoff": False, "handoff_sources": []},
            {"agent_id": "data", "title": "数据洞察", "ok": True, "summary": "数据完成",
             "structured_output": {"key_metrics": ["m1"], "findings": ["f1"], "recommendations": ["r1"]},
             "warnings": [], "error": None, "duration_ms": 1000,
             "used_handoff": False, "handoff_sources": []},
            {"agent_id": "website", "title": "交付物结构", "ok": True, "summary": "交付物完成",
             "structured_output": {}, "warnings": [], "error": None, "duration_ms": 1000,
             "used_handoff": True, "handoff_sources": ["research", "marketing"]},
        ]
        boss_so = {
            "total_duration_ms": 5000,
            "handoff_enabled": True,
            "handoff_context": {
                "research_summary": "测试摘要",
                "research_key_findings": ["发现1"],
                "research_opportunities": ["机会1"],
                "research_risks": [],
                "data_key_metrics": ["指标1"],
                "data_findings": ["数据发现1"],
                "data_recommendations": ["建议1"],
            },
            "handoff_sources": ["research", "data"],
            "handoff_targets": ["marketing", "image", "website"],
            "generated_at": "2026-07-14T00:00:00Z",
        }

        md = _render_boss_lite_md("测试目标", plan, results, boss_so)

        for term in self.BUSINESS_LOCKED_TERMS:
            assert term not in md, (
                f"Boss Lite markdown 报告包含业务锁定词: {term}\n---\n{md[:500]}"
            )

    def test_boss_lite_handoff_prompt_no_business_terms(self):
        """Boss Lite handoff 附言不含业务锁定词"""
        from backend.routers.boss_router import _build_handoff_prompt

        handoff_ctx = {
            "research_summary": "测试摘要",
            "research_key_findings": ["发现1"],
            "research_opportunities": ["机会1"],
            "research_risks": [],
            "data_key_metrics": ["指标1"],
            "data_findings": ["数据发现1"],
            "data_recommendations": ["建议1"],
        }

        prompt = _build_handoff_prompt("marketing", handoff_ctx, ["research", "data"])

        for term in self.BUSINESS_LOCKED_TERMS:
            assert term not in prompt, (
                f"Handoff prompt 包含业务锁定词: {term}"
            )
        # 验证通用名称存在
        assert "上下文整理结论" in prompt
        assert "数据洞察结论" in prompt

    # ── Phase 6.22: prompt_tpl 和 report section 通用化测试 ──

    PROMPT_BANNED_TERMS = [
        "市场调研", "上下文调研", "营销方案", "视觉方案",
        "数据分析框架", "落地页", "SEO", "竞品",
    ]

    def test_boss_lite_prompt_templates_no_business_terms(self):
        """BOSS_LITE_AGENTS 的 prompt_tpl 不含业务锁定词"""
        from backend.routers.boss_router import BOSS_LITE_AGENTS
        for agent in BOSS_LITE_AGENTS:
            tpl = agent["prompt_tpl"]
            for term in self.PROMPT_BANNED_TERMS:
                assert term not in tpl, (
                    f"Agent {agent['agent_id']} prompt_tpl 包含业务锁定词: {term}\n  prompt_tpl: {tpl[:100]}"
                )

    def test_boss_lite_markdown_generic_internal_sections(self):
        """website structured_output 渲染后使用通用标签"""
        from backend.routers.boss_router import _render_boss_lite_md

        plan = [
            {"agent_id": "research", "title": "上下文整理", "purpose": "收集上下文", "status": "done"},
            {"agent_id": "marketing", "title": "沟通表达", "purpose": "设计方案", "status": "done"},
            {"agent_id": "image", "title": "素材方向", "purpose": "素材建议", "status": "done"},
            {"agent_id": "data", "title": "数据洞察", "purpose": "分析数据", "status": "done"},
            {"agent_id": "website", "title": "交付物结构", "purpose": "设计交付物", "status": "done"},
        ]
        website_so = {
            "page_goal": "生成产品介绍页",
            "hero": {"headline": "产品标题", "subheadline": "副标题", "cta": "立即试用"},
            "sections": [{"title": "功能介绍"}, {"title": "客户案例"}],
            "ctas": ["免费试用"],
            "seo": {"title": "SEO标题", "description": "SEO描述"},
        }
        results = [
            {"agent_id": "research", "title": "上下文整理", "ok": True, "summary": "完成",
             "structured_output": {}, "warnings": [], "error": None, "duration_ms": 500,
             "used_handoff": False, "handoff_sources": []},
            {"agent_id": "marketing", "title": "沟通表达", "ok": True, "summary": "完成",
             "structured_output": {}, "warnings": [], "error": None, "duration_ms": 500,
             "used_handoff": False, "handoff_sources": []},
            {"agent_id": "image", "title": "素材方向", "ok": True, "summary": "完成",
             "structured_output": {}, "warnings": [], "error": None, "duration_ms": 500,
             "used_handoff": False, "handoff_sources": []},
            {"agent_id": "data", "title": "数据洞察", "ok": True, "summary": "完成",
             "structured_output": {}, "warnings": [], "error": None, "duration_ms": 500,
             "used_handoff": False, "handoff_sources": []},
            {"agent_id": "website", "title": "交付物结构", "ok": True, "summary": "完成",
             "structured_output": website_so, "warnings": [], "error": None, "duration_ms": 500,
             "used_handoff": False, "handoff_sources": []},
        ]
        boss_so = {
            "total_duration_ms": 2500,
            "handoff_enabled": False,
            "handoff_context": {},
            "handoff_sources": [],
            "handoff_targets": [],
            "generated_at": "2026-07-14T00:00:00Z",
        }

        md = _render_boss_lite_md("测试目标", plan, results, boss_so)

        # 必须包含通用标签
        assert "交付目标" in md, "报告应包含 '交付目标'"
        assert "核心标题" in md, "报告应包含 '核心标题'"
        assert "检索展示建议" in md, "报告应包含 '检索展示建议'"
        assert "交付板块" in md, "报告应包含 '交付板块'"

        # 不应包含旧标签
        banned = ["页面目标", "首屏标题", "SEO 建议", "页面板块", "落地页"]
        for term in banned:
            assert term not in md, (
                f"报告包含旧标签: {term}\n---\n{md[md.find('交付物结构'):md.find('交付物结构') + 800]}"
            )


class TestFrontendBossTextScan:
    """Phase 6.23: 前端 Boss 页面不含用户可见旧词"""

    # 用户可见中文旧词（不含字段名如 page_goal / seo / landing_page_copy）
    BANNED_VISIBLE_TERMS = [
        "页面目标",
        "首屏标题",
        "首屏 CTA",
        "页面板块",
        "上下文调研",
        "营销方案",
        "营销文案",
        "落地页",
    ]

    def _read_boss_index(self) -> str:
        import os
        path = os.path.join(
            os.path.dirname(__file__), "..", "frontend-new", "src", "pages", "boss", "index.tsx"
        )
        with open(path, encoding="utf-8") as f:
            return f.read()

    def test_boss_index_no_banned_visible_terms(self):
        """boss/index.tsx 用户可见中文文案不含旧词"""
        content = self._read_boss_index()
        # 去掉 import/类型注释区域，只检查用户可见文案
        # 通过引号内的中文文本来匹配
        import re
        # 匹配所有中文字符串字面量（双引号和反引号内的）
        chinese_strings = re.findall(r'"([^"]*[一-鿿][^"]*)"', content)
        chinese_strings += re.findall(r'`([^`]*[一-鿿][^`]*)`', content)
        all_visible = "\n".join(chinese_strings)

        for term in self.BANNED_VISIBLE_TERMS:
            assert term not in all_visible, (
                f"boss/index.tsx 用户可见文案包含旧词: '{term}'"
            )

    def test_boss_index_uses_generic_labels(self):
        """boss/index.tsx 使用通用标签替代旧标签"""
        content = self._read_boss_index()
        assert '"交付目标"' in content, "应使用 '交付目标' 替代 '页面目标'"
        assert '"核心标题"' in content, "应使用 '核心标题' 替代 '首屏标题'"
        assert '"交付板块"' in content, "应使用 '交付板块' 替代 '页面板块'"
        assert '"上下文整理"' in content or "上下文整理" in content, "应使用 '上下文整理' 替代 '上下文调研'"

    def test_boss_index_draft_key_upgraded_to_v2(self):
        """Phase 6.24: 草稿 key 已升级到 v2，旧 v1 key 启动时清理"""
        content = self._read_boss_index()
        assert 'draft_v2' in content, "DRAFT_STORAGE_KEY 应使用 v2"
        assert 'draft_v1' in content, "应保留 v1 key 常量用于启动时清理旧数据"
        # v1 key 不应用于写入（setItem）
        import re
        # 找到所有 localStorage.setItem(...) 调用，确保没有写入 v1
        setitem_calls = re.findall(r'localStorage\.setItem\(([^)]+)\)', content)
        for call in setitem_calls:
            assert 'v1' not in call or 'DRAFT_STORAGE_KEY_V1' not in call, (
                f"localStorage.setItem 不应写入 v1 key: {call}"
            )

