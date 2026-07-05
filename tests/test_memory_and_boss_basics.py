"""Memory Router + Boss Router 基础测试

覆盖:
- Memory: recent / search / remember / clear / context
- Boss: missions list / get mission / export mission / templates
- 不依赖外部 AI API、Hermes、浏览器自动化
"""
import sys
import os
import json
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest
from fastapi.testclient import TestClient
from backend.app import app


@pytest.fixture
def client():
    return TestClient(app, raise_server_exceptions=False)


# ── Memory Router ───────────────────────────────────────────────────────


class TestMemoryRouter:
    """memory_router 基础功能测试"""

    def test_recent_empty(self, client):
        """GET /memory/recent 返回 memories 列表（可为空）"""
        # 清空后查询
        client.delete("/memory/clear")
        resp = client.get("/memory/recent?limit=5")
        assert resp.status_code == 200
        data = resp.json()
        assert "memories" in data
        assert "count" in data
        assert isinstance(data["memories"], list)
        assert data["count"] == 0

    def test_remember_and_recent(self, client):
        """POST /memory/remember + GET /memory/recent 验证写入和读取"""
        # 写入记忆
        resp = client.post("/memory/remember", json={
            "key": "pytest_test_key",
            "content": "这是一个测试记忆",
            "source": "test",
            "tags": ["pytest", "test"],
            "importance": 0.8,
        })
        assert resp.status_code == 200
        assert resp.json()["status"] == "ok"

        # 查询最近记忆
        resp = client.get("/memory/recent?limit=10")
        assert resp.status_code == 200
        data = resp.json()
        assert data["count"] >= 1
        # 找到刚写入的记忆
        keys = [m["key"] for m in data["memories"]]
        assert "pytest_test_key" in keys

    def test_search(self, client):
        """GET /memory/search?q=pytest 搜索记忆"""
        # 先确保有数据
        client.post("/memory/remember", json={
            "key": "pytest_search_target",
            "content": "搜索测试专用内容",
            "source": "test",
            "tags": [],
            "importance": 0.5,
        })
        resp = client.get("/memory/search?q=pytest_search_target&limit=5")
        assert resp.status_code == 200
        data = resp.json()
        assert "memories" in data
        assert data["count"] >= 1
        # 搜索结果中应包含目标
        keys = [m["key"] for m in data["memories"]]
        assert "pytest_search_target" in keys

    def test_search_empty_query(self, client):
        """GET /memory/search?q= (空查询) 返回最近记忆"""
        resp = client.get("/memory/search?q=&limit=5")
        assert resp.status_code == 200
        data = resp.json()
        assert "memories" in data
        assert isinstance(data["memories"], list)

    def test_context(self, client):
        """GET /memory/context?goal=... 返回上下文字符串"""
        resp = client.get("/memory/context?goal=测试目标")
        assert resp.status_code == 200
        data = resp.json()
        assert "context" in data
        assert "goal" in data
        assert data["goal"] == "测试目标"

    def test_clear(self, client):
        """DELETE /memory/clear 清空所有记忆"""
        client.post("/memory/remember", json={
            "key": "pytest_clear_test",
            "content": "将被清空",
            "source": "test",
        })
        resp = client.delete("/memory/clear")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "ok"

        # 验证已清空
        resp = client.get("/memory/recent?limit=5")
        assert resp.json()["count"] == 0

    def test_remember_response_shape(self, client):
        """记忆对象包含所有必要字段"""
        client.post("/memory/remember", json={
            "key": "pytest_shape_check",
            "content": "字段检查",
            "source": "test",
            "tags": ["a"],
            "importance": 0.6,
        })
        resp = client.get("/memory/recent?limit=1")
        data = resp.json()
        assert data["count"] >= 1
        mem = data["memories"][0]
        # 必需字段
        for field in ("id", "key", "content", "source", "tags", "importance",
                      "created_at", "accessed_at", "access_count"):
            assert field in mem, f"Missing field: {field}"
        assert isinstance(mem["tags"], list)
        assert isinstance(mem["importance"], float)
        assert isinstance(mem["access_count"], int)

    def teardown_method(self):
        """每个测试后清理测试数据"""
        # 清理本次测试写入的数据
        pass


# ── Boss Router 基础 ────────────────────────────────────────────────────


class TestBossRouterBasics:
    """boss_router 基础功能测试（不执行 mission）"""

    def test_list_missions(self, client):
        """GET /boss/missions 返回 missions 列表"""
        resp = client.get("/boss/missions?limit=10&offset=0")
        assert resp.status_code == 200
        data = resp.json()
        assert "missions" in data
        assert "total" in data
        assert isinstance(data["missions"], list)
        assert isinstance(data["total"], int)

    def test_list_missions_response_shape(self, client):
        """mission 列表项包含必要字段"""
        resp = client.get("/boss/missions?limit=10&offset=0")
        data = resp.json()
        if data["missions"]:
            m = data["missions"][0]
            for field in ("mission_id", "goal", "status", "created_at", "updated_at"):
                assert field in m, f"Missing field: {field}"

    def test_create_and_get_mission(self, client):
        """POST /boss/missions 创建 + GET /boss/missions/{id} 查询"""
        # 创建
        resp = client.post("/boss/missions", json={
            "goal": "pytest 测试 mission",
            "auto_run": False,
            "enabled_modules": ["strategy"],
        })
        assert resp.status_code == 200
        mission = resp.json()
        mission_id = mission["mission_id"]
        assert mission["goal"] == "pytest 测试 mission"
        assert mission["status"] == "pending_review"
        assert "modules" in mission
        assert len(mission["modules"]) >= 1

        # 查询
        resp = client.get(f"/boss/missions/{mission_id}")
        assert resp.status_code == 200
        data = resp.json()
        assert data["mission_id"] == mission_id
        assert data["goal"] == "pytest 测试 mission"
        assert "metrics" in data

    def test_mission_metrics(self, client):
        """创建 mission 后 metrics 存在且结构正确"""
        resp = client.post("/boss/missions", json={
            "goal": "pytest metrics 检查",
            "auto_run": False,
        })
        mission_id = resp.json()["mission_id"]
        resp = client.get(f"/boss/missions/{mission_id}")
        metrics = resp.json()["metrics"]
        for key in ("total_modules", "succeeded_modules", "failed_modules",
                     "skipped_modules", "duration_ms", "warning_count",
                     "next_action_count", "completion_rate"):
            assert key in metrics, f"Missing metric: {key}"

    def test_export_mission_json(self, client):
        """GET /boss/missions/{id}/export?format=json 导出 JSON"""
        resp = client.post("/boss/missions", json={
            "goal": "pytest export 测试",
            "auto_run": False,
        })
        mission_id = resp.json()["mission_id"]
        resp = client.get(f"/boss/missions/{mission_id}/export?format=json")
        assert resp.status_code == 200
        # 导出内容应为 JSON
        export_data = json.loads(resp.text)
        assert "mission_id" in export_data
        assert export_data["mission_id"] == mission_id

    def test_export_mission_markdown(self, client):
        """GET /boss/missions/{id}/export?format=markdown 导出 Markdown"""
        resp = client.post("/boss/missions", json={
            "goal": "pytest markdown export 测试",
            "auto_run": False,
        })
        mission_id = resp.json()["mission_id"]
        resp = client.get(f"/boss/missions/{mission_id}/export?format=markdown")
        assert resp.status_code == 200
        # 导出内容应为 Markdown 格式，包含 goal 文本
        assert "pytest markdown export" in resp.text

    def test_templates(self, client):
        """GET /boss/templates 返回模板列表"""
        resp = client.get("/boss/templates")
        assert resp.status_code == 200
        data = resp.json()
        assert "templates" in data
        assert "total" in data
        assert data["total"] >= 1
        # 模板应有基本字段
        tpl = data["templates"][0]
        for field in ("id", "name", "description"):
            assert field in tpl, f"Missing template field: {field}"

    def test_module_definitions(self, client):
        """GET /boss/modules/definitions 返回模块定义"""
        resp = client.get("/boss/modules/definitions")
        assert resp.status_code == 200
        data = resp.json()
        assert "modules" in data
        assert len(data["modules"]) == 5
        module_ids = {m["id"] for m in data["modules"]}
        assert module_ids == {"strategy", "market", "marketing", "landing", "actions"}

    def test_mission_events(self, client):
        """GET /boss/missions/{id}/events 返回事件列表"""
        resp = client.post("/boss/missions", json={
            "goal": "pytest events 测试",
            "auto_run": False,
        })
        mission_id = resp.json()["mission_id"]
        resp = client.get(f"/boss/missions/{mission_id}/events")
        assert resp.status_code == 200
        data = resp.json()
        assert "events" in data
        assert "total" in data
        assert isinstance(data["events"], list)

    def test_nonexistent_mission(self, client):
        """GET /boss/missions/{不存在的id} 返回 404"""
        resp = client.get("/boss/missions/nonexistent_mission_id_12345")
        assert resp.status_code == 404
