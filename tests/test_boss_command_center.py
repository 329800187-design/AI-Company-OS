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
"""
import sys
import os
import json
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest
from unittest.mock import patch, MagicMock


# ── Service 层测试 ───────────────────────────────────────

class TestBossCommandCenterService:
    """BossCommandCenterService 单元测试"""

    @pytest.fixture
    def service(self):
        from backend.services.boss_command_center import BossCommandCenterService
        return BossCommandCenterService()

    def test_create_mission(self, service):
        """创建 mission 应返回完整结构"""
        mission = service.create_mission("测试业务目标")
        assert mission is not None
        assert mission["mission_id"].startswith("mission_")
        assert mission["goal"] == "测试业务目标"
        assert mission["status"] == "pending"
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
        """单模块执行（mock runtime）"""
        mission = service.create_mission("mock 测试")
        mission_id = mission["mission_id"]

        mock_result = {
            "ok": True,
            "final_answer": "这是战略分析结果",
            "confidence": 0.85,
            "warnings": [],
            "used_tools": ["mimo"],
            "mode": "local",
            "error": "",
            "next_actions": ["联系投资人", "写商业计划书"],
        }

        with patch.object(service, '_get_runtime') as mock_get_runtime:
            mock_runtime = MagicMock()
            mock_runtime.execute.return_value = mock_result
            mock_get_runtime.return_value = mock_runtime

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

        mock_result = {
            "ok": False,
            "final_answer": "",
            "confidence": 0.0,
            "warnings": [],
            "used_tools": [],
            "mode": "error",
            "error": "Adapter 不可用",
        }

        with patch.object(service, '_get_runtime') as mock_get_runtime:
            mock_runtime = MagicMock()
            mock_runtime.execute.return_value = mock_result
            mock_get_runtime.return_value = mock_runtime

            updated = service.run_module(mission_id, "market")
            assert updated is not None

            market = next(m for m in updated["modules"] if m["module_id"] == "market")
            assert market["status"] == "failed"
            assert "Adapter 不可用" in market["error"]
            assert market["duration_ms"] >= 0  # mock 执行极快，duration 可能为 0

    def test_market_no_web_search_warning(self, service):
        """market 模块无联网能力时应返回 warning"""
        mission = service.create_mission("联网测试")
        mission_id = mission["mission_id"]

        mock_result = {
            "ok": True,
            "final_answer": "市场分析结果（无联网）",
            "confidence": 0.6,
            "warnings": [],
            "used_tools": ["api_models"],
            "mode": "local",
            "error": "",
        }

        with patch.object(service, '_get_runtime') as mock_get_runtime:
            mock_runtime = MagicMock()
            mock_runtime.execute.return_value = mock_result
            mock_get_runtime.return_value = mock_runtime

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

        mock_result = {
            "ok": True,
            "final_answer": "结果",
            "confidence": 0.7,
            "warnings": [],
            "used_tools": [],
            "mode": "local",
            "error": "",
        }

        with patch.object(service, '_get_runtime') as mock_get_runtime:
            mock_runtime = MagicMock()
            mock_runtime.execute.return_value = mock_result
            mock_get_runtime.return_value = mock_runtime

            # 先执行一次 strategy
            service.run_module(mission_id, "strategy")

            # 再执行整个 mission，strategy 不应重复执行
            mock_runtime.execute.reset_mock()
            service.run_mission(mission_id)

            # runtime.execute 应该只被调用 4 次（跳过已完成的 strategy）
            assert mock_runtime.execute.call_count == 4

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
        assert "战略摘要" in md
        assert "市场与竞品" in md
        assert "营销方案" in md
        assert "落地页草稿" in md
        assert "执行清单" in md

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
