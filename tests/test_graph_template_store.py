"""Graph Template Store 测试

覆盖场景：
  1. 创建模板成功
  2. 创建模板时 invalid graph 返回 400
  3. 列出模板
  4. 获取单个模板
  5. 删除模板
  6. 删除不存在模板返回 404
  7. 模板 JSON 文件确实落盘
  8. 按模板执行（mock execute_agent）
"""
import json
import pytest
from unittest.mock import patch, MagicMock
from pathlib import Path

from backend.services.graph_template_store import (
    save_template,
    get_template,
    list_templates,
    delete_template,
)


# ── 存储层测试（使用 tmp_path 隔离） ─────────────────────────


class TestTemplateStore:
    """Graph Template Store 纯存储层测试"""

    @pytest.fixture(autouse=True)
    def setup_tmp_dir(self, tmp_path, monkeypatch):
        """每个测试使用独立的临时目录"""
        self.tmp_dir = tmp_path / "graph_templates"
        self.tmp_dir.mkdir()
        monkeypatch.setattr(
            "backend.services.graph_template_store.DEFAULT_TEMPLATES_DIR",
            self.tmp_dir,
        )

    def _sample_nodes(self):
        return [
            {"id": "research", "agent_id": "research", "task_type": "research_brief", "title": "调研", "prompt": "做调研"},
            {"id": "marketing", "agent_id": "marketing", "task_type": "copywriting", "title": "营销", "prompt": "做营销"},
        ]

    def _sample_edges(self):
        return [{"from_node": "research", "to_node": "marketing", "handoff_type": "context"}]

    def test_save_and_get_template(self):
        """保存后可读取"""
        template = save_template(
            name="测试模板",
            nodes=self._sample_nodes(),
            edges=self._sample_edges(),
            description="测试描述",
            goal_hint="测试目标",
        )
        assert template["template_id"].startswith("tpl_")
        assert template["name"] == "测试模板"
        assert template["description"] == "测试描述"
        assert template["goal_hint"] == "测试目标"
        assert len(template["nodes"]) == 2
        assert len(template["edges"]) == 1
        assert "created_at" in template
        assert "updated_at" in template

        # 读取
        loaded = get_template(template["template_id"])
        assert loaded is not None
        assert loaded["template_id"] == template["template_id"]
        assert loaded["name"] == "测试模板"

    def test_file_written_to_disk(self):
        """模板 JSON 确实落盘"""
        template = save_template(
            name="落盘测试",
            nodes=self._sample_nodes(),
            edges=self._sample_edges(),
        )
        file_path = self.tmp_dir / f"{template['template_id']}.json"
        assert file_path.exists()

        data = json.loads(file_path.read_text(encoding="utf-8"))
        assert data["template_id"] == template["template_id"]
        assert data["name"] == "落盘测试"

    def test_list_templates(self):
        """列出所有模板"""
        # 创建 3 个模板
        ids = []
        for i in range(3):
            t = save_template(
                name=f"模板 {i}",
                nodes=self._sample_nodes(),
                edges=self._sample_edges(),
            )
            ids.append(t["template_id"])

        templates = list_templates()
        assert len(templates) == 3
        # 验证所有模板都在
        returned_ids = {t["template_id"] for t in templates}
        assert returned_ids == set(ids)

    def test_list_templates_empty(self):
        """空目录返回空列表"""
        templates = list_templates()
        assert templates == []

    def test_get_nonexistent_template(self):
        """不存在的模板返回 None"""
        result = get_template("tpl_nonexistent")
        assert result is None

    def test_delete_template(self):
        """删除模板成功"""
        template = save_template(
            name="待删除",
            nodes=self._sample_nodes(),
            edges=self._sample_edges(),
        )
        tid = template["template_id"]

        # 确认存在
        assert get_template(tid) is not None

        # 删除
        deleted = delete_template(tid)
        assert deleted is True

        # 确认不存在
        assert get_template(tid) is None

    def test_delete_nonexistent_returns_false(self):
        """删除不存在的模板返回 False"""
        deleted = delete_template("tpl_nonexistent")
        assert deleted is False

    def test_custom_template_id(self):
        """可指定 template_id"""
        template = save_template(
            name="自定义 ID",
            nodes=self._sample_nodes(),
            edges=self._sample_edges(),
            template_id="tpl_custom_123",
        )
        assert template["template_id"] == "tpl_custom_123"
        assert get_template("tpl_custom_123") is not None

    def test_invalid_template_id_rejected_on_save(self):
        """Invalid template IDs are rejected before writing files."""
        with pytest.raises(ValueError):
            save_template(
                name="Invalid ID",
                nodes=self._sample_nodes(),
                edges=[],
                template_id="../evil",
            )

    def test_invalid_template_id_cannot_read_or_delete(self):
        """Path-like template IDs are treated as not found."""
        assert get_template("../evil") is None
        assert delete_template("../evil") is False

    def test_empty_edges(self):
        """无边的模板"""
        template = save_template(
            name="无边模板",
            nodes=self._sample_nodes(),
            edges=[],
        )
        assert template["edges"] == []
        loaded = get_template(template["template_id"])
        assert loaded["edges"] == []


# ── API 集成测试 ──────────────────────────────────────────────


def _bypass_governance(payload, platform=None):
    from backend.governance.classifier import ClassificationResult
    return False, ClassificationResult(ok=True, confidence=1.0, reason="test bypass")


def _bypass_rate_limit(name, max_requests=5, window_seconds=60):
    return True, ""


def _mock_execute_agent(agent_id, task):
    mock_result = MagicMock()
    mock_result.ok = True
    mock_result.summary = f"{agent_id} 执行完成"
    mock_result.structured_output = {"summary": f"{agent_id} 摘要", "key_findings": []}
    mock_result.warnings = []
    mock_result.errors = []
    mock_result.error = None
    mock_result.model_dump.return_value = {
        "ok": True,
        "agent_id": agent_id,
        "summary": f"{agent_id} 执行完成",
        "structured_output": {"summary": f"{agent_id} 摘要", "key_findings": []},
        "warnings": [],
        "errors": [],
        "error": None,
    }
    return mock_result


def _sample_api_nodes():
    return [
        {"id": "research", "agent_id": "research", "task_type": "research_brief", "title": "调研", "prompt": "做调研"},
        {"id": "marketing", "agent_id": "marketing", "task_type": "copywriting", "title": "营销", "prompt": "做营销"},
    ]


def _sample_api_edges():
    return [{"from_node": "research", "to_node": "marketing", "handoff_type": "context"}]


class TestGraphTemplateAPI:
    """Graph Template API 集成测试"""

    @pytest.fixture(autouse=True)
    def setup_tmp_dir(self, tmp_path, monkeypatch):
        """每个测试使用独立的临时目录"""
        self.tmp_dir = tmp_path / "graph_templates"
        self.tmp_dir.mkdir()
        monkeypatch.setattr(
            "backend.services.graph_template_store.DEFAULT_TEMPLATES_DIR",
            self.tmp_dir,
        )

    @patch("backend.security.rate_limiter.check", side_effect=_bypass_rate_limit)
    @patch("backend.governance.guard.guard_payload", side_effect=_bypass_governance)
    def test_create_template_success(self, mock_guard, mock_rate):
        """创建模板成功"""
        from fastapi.testclient import TestClient
        from backend.app import app

        client = TestClient(app)
        response = client.post("/boss/graph/templates", json={
            "name": "新品上线协作图",
            "description": "research → marketing",
            "goal_hint": "为品牌做新品上线",
            "nodes": _sample_api_nodes(),
            "edges": _sample_api_edges(),
        })

        assert response.status_code == 200
        data = response.json()
        assert data["ok"] is True
        assert data["template"]["name"] == "新品上线协作图"
        assert data["template"]["template_id"].startswith("tpl_")
        assert len(data["template"]["nodes"]) == 2
        assert len(data["template"]["edges"]) == 1

    @patch("backend.security.rate_limiter.check", side_effect=_bypass_rate_limit)
    @patch("backend.governance.guard.guard_payload", side_effect=_bypass_governance)
    def test_create_template_invalid_graph_400(self, mock_guard, mock_rate):
        """无效图（缺失节点引用）返回 400"""
        from fastapi.testclient import TestClient
        from backend.app import app

        client = TestClient(app)
        response = client.post("/boss/graph/templates", json={
            "name": "无效图模板",
            "nodes": [
                {"id": "a", "agent_id": "research", "title": "A", "prompt": "p"},
            ],
            "edges": [
                {"from_node": "a", "to_node": "x"},  # x 不存在
            ],
        })

        assert response.status_code == 400

    @patch("backend.security.rate_limiter.check", side_effect=_bypass_rate_limit)
    @patch("backend.governance.guard.guard_payload", side_effect=_bypass_governance)
    def test_create_template_self_loop_400(self, mock_guard, mock_rate):
        """自环返回 400"""
        from fastapi.testclient import TestClient
        from backend.app import app

        client = TestClient(app)
        response = client.post("/boss/graph/templates", json={
            "name": "自环模板",
            "nodes": [
                {"id": "a", "agent_id": "research", "title": "A", "prompt": "p"},
            ],
            "edges": [
                {"from_node": "a", "to_node": "a"},
            ],
        })

        assert response.status_code == 400

    @patch("backend.security.rate_limiter.check", side_effect=_bypass_rate_limit)
    @patch("backend.governance.guard.guard_payload", side_effect=_bypass_governance)
    def test_list_templates(self, mock_guard, mock_rate):
        """列出模板"""
        from fastapi.testclient import TestClient
        from backend.app import app

        client = TestClient(app)

        # 先创建 2 个模板
        for i in range(2):
            client.post("/boss/graph/templates", json={
                "name": f"模板 {i}",
                "nodes": _sample_api_nodes(),
            })

        response = client.get("/boss/graph/templates")
        assert response.status_code == 200
        data = response.json()
        assert data["ok"] is True
        assert data["total"] == 2
        assert len(data["templates"]) == 2

    @patch("backend.security.rate_limiter.check", side_effect=_bypass_rate_limit)
    @patch("backend.governance.guard.guard_payload", side_effect=_bypass_governance)
    def test_get_single_template(self, mock_guard, mock_rate):
        """获取单个模板"""
        from fastapi.testclient import TestClient
        from backend.app import app

        client = TestClient(app)

        # 创建
        create_resp = client.post("/boss/graph/templates", json={
            "name": "获取测试",
            "nodes": _sample_api_nodes(),
        })
        tid = create_resp.json()["template"]["template_id"]

        # 获取
        response = client.get(f"/boss/graph/templates/{tid}")
        assert response.status_code == 200
        data = response.json()
        assert data["ok"] is True
        assert data["template"]["template_id"] == tid

    @patch("backend.security.rate_limiter.check", side_effect=_bypass_rate_limit)
    @patch("backend.governance.guard.guard_payload", side_effect=_bypass_governance)
    def test_get_nonexistent_template_404(self, mock_guard, mock_rate):
        """不存在的模板返回 404"""
        from fastapi.testclient import TestClient
        from backend.app import app

        client = TestClient(app)
        response = client.get("/boss/graph/templates/tpl_nonexistent")
        assert response.status_code == 404

    @patch("backend.security.rate_limiter.check", side_effect=_bypass_rate_limit)
    @patch("backend.governance.guard.guard_payload", side_effect=_bypass_governance)
    def test_delete_template(self, mock_guard, mock_rate):
        """删除模板"""
        from fastapi.testclient import TestClient
        from backend.app import app

        client = TestClient(app)

        # 创建
        create_resp = client.post("/boss/graph/templates", json={
            "name": "待删除",
            "nodes": _sample_api_nodes(),
        })
        tid = create_resp.json()["template"]["template_id"]

        # 删除
        response = client.delete(f"/boss/graph/templates/{tid}")
        assert response.status_code == 200
        data = response.json()
        assert data["ok"] is True
        assert data["deleted"] is True
        assert data["template_id"] == tid

        # 确认不存在
        get_resp = client.get(f"/boss/graph/templates/{tid}")
        assert get_resp.status_code == 404

    @patch("backend.security.rate_limiter.check", side_effect=_bypass_rate_limit)
    @patch("backend.governance.guard.guard_payload", side_effect=_bypass_governance)
    def test_delete_nonexistent_template_404(self, mock_guard, mock_rate):
        """删除不存在的模板返回 404"""
        from fastapi.testclient import TestClient
        from backend.app import app

        client = TestClient(app)
        response = client.delete("/boss/graph/templates/tpl_nonexistent")
        assert response.status_code == 404

    @patch("backend.security.rate_limiter.check", side_effect=_bypass_rate_limit)
    @patch("backend.governance.guard.guard_payload", side_effect=_bypass_governance)
    @patch("backend.services.agent_executor.execute_agent", side_effect=_mock_execute_agent)
    def test_execute_template(self, mock_exec, mock_guard, mock_rate):
        """按模板执行"""
        from fastapi.testclient import TestClient
        from backend.app import app

        client = TestClient(app)

        # 创建模板
        create_resp = client.post("/boss/graph/templates", json={
            "name": "执行测试",
            "nodes": _sample_api_nodes(),
            "edges": _sample_api_edges(),
        })
        tid = create_resp.json()["template"]["template_id"]

        # 按模板执行
        response = client.post(f"/boss/graph/templates/{tid}/execute", json={
            "goal": "为手工银饰做新品上线",
            "save_to_delivery": False,
        })

        assert response.status_code == 200
        data = response.json()
        assert data["ok"] is True
        assert data["execution_mode"] == "custom_graph"
        assert len(data["results"]) == 2

    @patch("backend.security.rate_limiter.check", side_effect=_bypass_rate_limit)
    @patch("backend.governance.guard.guard_payload", side_effect=_bypass_governance)
    def test_execute_nonexistent_template_404(self, mock_guard, mock_rate):
        """执行不存在的模板返回 404"""
        from fastapi.testclient import TestClient
        from backend.app import app

        client = TestClient(app)
        response = client.post("/boss/graph/templates/tpl_nonexistent/execute", json={
            "goal": "测试目标",
        })
        assert response.status_code == 404
