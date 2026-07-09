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
    update_template,
    save_version_snapshot,
    list_versions,
    get_version,
    delete_versions_for_template,
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
        # Phase 6.6: 版本目录也需要隔离
        self.versions_dir = tmp_path / "graph_template_versions"
        self.versions_dir.mkdir()
        monkeypatch.setattr(
            "backend.services.graph_template_store.DEFAULT_VERSIONS_DIR",
            self.versions_dir,
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

    def test_update_template_success(self):
        """更新模板成功"""
        template = save_template(
            name="原始名称",
            nodes=self._sample_nodes(),
            edges=self._sample_edges(),
            description="原始描述",
            goal_hint="原始目标",
        )
        tid = template["template_id"]

        new_nodes = [
            {"id": "research", "agent_id": "research", "task_type": "research_brief", "title": "新调研", "prompt": "新调研内容"},
            {"id": "marketing", "agent_id": "marketing", "task_type": "copywriting", "title": "新营销", "prompt": "新营销内容"},
            {"id": "image", "agent_id": "image", "task_type": "image_prompt", "title": "视觉", "prompt": "视觉内容"},
        ]
        new_edges = [
            {"from_node": "research", "to_node": "marketing", "handoff_type": "context"},
            {"from_node": "research", "to_node": "image", "handoff_type": "context"},
        ]

        updated = update_template(
            template_id=tid,
            name="更新后的名称",
            nodes=new_nodes,
            edges=new_edges,
            description="更新后的描述",
            goal_hint="更新后的目标",
        )

        assert updated is not None
        assert updated["template_id"] == tid
        assert updated["name"] == "更新后的名称"
        assert updated["description"] == "更新后的描述"
        assert updated["goal_hint"] == "更新后的目标"
        assert len(updated["nodes"]) == 3
        assert len(updated["edges"]) == 2

        # 读取验证
        loaded = get_template(tid)
        assert loaded is not None
        assert loaded["name"] == "更新后的名称"
        assert len(loaded["nodes"]) == 3

    def test_update_preserves_created_at(self):
        """更新保留 created_at，更新 updated_at"""
        template = save_template(
            name="时间测试",
            nodes=self._sample_nodes(),
            edges=[],
        )
        tid = template["template_id"]
        original_created = template["created_at"]
        original_updated = template["updated_at"]

        import time
        time.sleep(0.01)

        updated = update_template(
            template_id=tid,
            name="时间测试更新",
            nodes=self._sample_nodes(),
            edges=[],
        )

        assert updated is not None
        assert updated["created_at"] == original_created
        assert updated["updated_at"] != original_updated

    def test_update_nonexistent_returns_none(self):
        """更新不存在的模板返回 None"""
        result = update_template(
            template_id="tpl_nonexistent",
            name="不存在",
            nodes=self._sample_nodes(),
            edges=[],
        )
        assert result is None

    def test_update_invalid_template_id_returns_none(self):
        """非法 template_id 返回 None"""
        result = update_template(
            template_id="../evil",
            name="邪恶",
            nodes=self._sample_nodes(),
            edges=[],
        )
        assert result is None

    # ── Phase 6.6: Version History 测试 ─────────────────────

    def test_update_creates_version_snapshot(self):
        """更新模板时自动保存旧版本快照"""
        template = save_template(
            name="原始名称",
            nodes=self._sample_nodes(),
            edges=self._sample_edges(),
        )
        tid = template["template_id"]

        update_template(
            template_id=tid,
            name="更新后名称",
            nodes=self._sample_nodes(),
            edges=self._sample_edges(),
        )

        versions = list_versions(tid)
        assert len(versions) == 1
        assert versions[0]["name"] == "原始名称"
        assert versions[0]["template_id"] == tid

    def test_version_id_format(self):
        """版本 ID 符合 ver_ 格式"""
        template = save_template(
            name="版本ID测试",
            nodes=self._sample_nodes(),
            edges=[],
        )
        update_template(
            template_id=template["template_id"],
            name="更新",
            nodes=self._sample_nodes(),
            edges=[],
        )
        versions = list_versions(template["template_id"])
        assert len(versions) == 1
        assert versions[0]["version_id"].startswith("ver_")
        import re
        assert re.fullmatch(r"ver_[0-9a-f]{12}", versions[0]["version_id"])

    def test_version_file_content(self):
        """版本文件包含所有必需字段"""
        template = save_template(
            name="内容测试",
            nodes=self._sample_nodes(),
            edges=self._sample_edges(),
            description="描述",
            goal_hint="目标",
        )
        update_template(
            template_id=template["template_id"],
            name="更新",
            nodes=self._sample_nodes(),
            edges=[],
        )
        versions = list_versions(template["template_id"])
        vid = versions[0]["version_id"]
        version = get_version(template["template_id"], vid)

        assert version is not None
        assert version["version_id"] == vid
        assert version["template_id"] == template["template_id"]
        assert "created_at" in version
        assert version["name"] == "内容测试"
        assert version["description"] == "描述"
        assert version["goal_hint"] == "目标"
        assert len(version["nodes"]) == 2
        assert len(version["edges"]) == 1

    def test_list_versions(self):
        """多次更新后列出版本，按 created_at 降序"""
        template = save_template(
            name="V1",
            nodes=self._sample_nodes(),
            edges=[],
        )
        tid = template["template_id"]

        import time
        for i in range(3):
            time.sleep(0.01)
            update_template(
                template_id=tid,
                name=f"V{i + 2}",
                nodes=self._sample_nodes(),
                edges=[],
            )

        versions = list_versions(tid)
        assert len(versions) == 3
        # 降序：最新的在前（版本快照保存的是更新前的状态）
        assert versions[0]["name"] == "V3"
        assert versions[1]["name"] == "V2"
        assert versions[2]["name"] == "V1"

    def test_list_versions_empty(self):
        """未更新过的模板版本列表为空"""
        template = save_template(
            name="无版本",
            nodes=self._sample_nodes(),
            edges=[],
        )
        versions_dir = self.versions_dir / template["template_id"]
        assert not versions_dir.exists()
        assert list_versions(template["template_id"]) == []
        assert not versions_dir.exists()

    def test_get_version(self):
        """可按 ID 获取特定版本"""
        template = save_template(
            name="原始",
            nodes=self._sample_nodes(),
            edges=[],
        )
        tid = template["template_id"]
        update_template(
            template_id=tid,
            name="更新",
            nodes=self._sample_nodes(),
            edges=[],
        )
        versions = list_versions(tid)
        vid = versions[0]["version_id"]

        version = get_version(tid, vid)
        assert version is not None
        assert version["version_id"] == vid
        assert version["name"] == "原始"

    def test_get_nonexistent_version_returns_none(self):
        """不存在的版本返回 None"""
        template = save_template(
            name="测试",
            nodes=self._sample_nodes(),
            edges=[],
        )
        assert get_version(template["template_id"], "ver_nonexistent") is None

    def test_max_version_trim(self):
        """超过 20 个版本时裁剪最旧的"""
        template = save_template(
            name="裁剪测试",
            nodes=self._sample_nodes(),
            edges=[],
        )
        tid = template["template_id"]

        import time
        for i in range(25):
            time.sleep(0.01)
            update_template(
                template_id=tid,
                name=f"V{i + 2}",
                nodes=self._sample_nodes(),
                edges=[],
            )

        versions = list_versions(tid)
        assert len(versions) == 20
        assert versions[0]["name"] == "V25"
        assert versions[-1]["name"] == "V6"

    def test_delete_template_cleans_up_versions(self):
        """删除模板时同步清理版本目录"""
        template = save_template(
            name="待删除",
            nodes=self._sample_nodes(),
            edges=[],
        )
        tid = template["template_id"]
        update_template(
            template_id=tid,
            name="更新",
            nodes=self._sample_nodes(),
            edges=[],
        )

        # 确认版本存在
        assert len(list_versions(tid)) == 1

        # 删除模板
        delete_template(tid)

        # 版本目录应不存在
        versions_dir = self.versions_dir / tid
        assert not versions_dir.exists()

    def test_version_immutable(self):
        """版本快照内容不会随后续更新而改变"""
        template = save_template(
            name="不可变测试",
            nodes=self._sample_nodes(),
            edges=[],
        )
        tid = template["template_id"]

        update_template(
            template_id=tid,
            name="更新1",
            nodes=self._sample_nodes(),
            edges=[],
        )
        versions1 = list_versions(tid)
        vid = versions1[0]["version_id"]
        version_before = get_version(tid, vid)

        update_template(
            template_id=tid,
            name="更新2",
            nodes=self._sample_nodes(),
            edges=[],
        )
        version_after = get_version(tid, vid)

        # 版本内容不应改变
        assert version_before["name"] == version_after["name"] == "不可变测试"


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
        # Phase 6.6: 版本目录也需要隔离
        self.versions_dir = tmp_path / "graph_template_versions"
        self.versions_dir.mkdir()
        monkeypatch.setattr(
            "backend.services.graph_template_store.DEFAULT_VERSIONS_DIR",
            self.versions_dir,
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

    @patch("backend.security.rate_limiter.check", side_effect=_bypass_rate_limit)
    @patch("backend.governance.guard.guard_payload", side_effect=_bypass_governance)
    def test_update_template_success(self, mock_guard, mock_rate):
        """PUT 更新模板成功"""
        from fastapi.testclient import TestClient
        from backend.app import app

        client = TestClient(app)

        # 创建
        create_resp = client.post("/boss/graph/templates", json={
            "name": "待更新",
            "nodes": _sample_api_nodes(),
            "edges": _sample_api_edges(),
        })
        tid = create_resp.json()["template"]["template_id"]

        # 更新
        new_nodes = [
            {"id": "research", "agent_id": "research", "task_type": "research_brief", "title": "新调研", "prompt": "新内容"},
            {"id": "marketing", "agent_id": "marketing", "task_type": "copywriting", "title": "新营销", "prompt": "新营销"},
            {"id": "image", "agent_id": "image", "task_type": "image_prompt", "title": "视觉", "prompt": "视觉内容"},
        ]
        new_edges = [
            {"from_node": "research", "to_node": "marketing", "handoff_type": "context"},
            {"from_node": "research", "to_node": "image", "handoff_type": "context"},
        ]

        response = client.put(f"/boss/graph/templates/{tid}", json={
            "name": "更新后的模板",
            "description": "新描述",
            "goal_hint": "新目标",
            "nodes": new_nodes,
            "edges": new_edges,
        })

        assert response.status_code == 200
        data = response.json()
        assert data["ok"] is True
        assert data["template"]["name"] == "更新后的模板"
        assert data["template"]["description"] == "新描述"
        assert len(data["template"]["nodes"]) == 3
        assert len(data["template"]["edges"]) == 2

    @patch("backend.security.rate_limiter.check", side_effect=_bypass_rate_limit)
    @patch("backend.governance.guard.guard_payload", side_effect=_bypass_governance)
    def test_update_nonexistent_template_404(self, mock_guard, mock_rate):
        """PUT 不存在的模板返回 404"""
        from fastapi.testclient import TestClient
        from backend.app import app

        client = TestClient(app)
        response = client.put("/boss/graph/templates/tpl_nonexistent", json={
            "name": "不存在",
            "nodes": _sample_api_nodes(),
        })
        assert response.status_code == 404

    @patch("backend.security.rate_limiter.check", side_effect=_bypass_rate_limit)
    @patch("backend.governance.guard.guard_payload", side_effect=_bypass_governance)
    def test_update_template_invalid_graph_400(self, mock_guard, mock_rate):
        """PUT 无效图返回 400"""
        from fastapi.testclient import TestClient
        from backend.app import app

        client = TestClient(app)

        # 创建
        create_resp = client.post("/boss/graph/templates", json={
            "name": "待更新",
            "nodes": _sample_api_nodes(),
        })
        tid = create_resp.json()["template"]["template_id"]

        # 更新为无效图
        response = client.put(f"/boss/graph/templates/{tid}", json={
            "name": "无效图更新",
            "nodes": [{"id": "a", "agent_id": "research", "title": "A", "prompt": "p"}],
            "edges": [{"from_node": "a", "to_node": "x"}],
        })
        assert response.status_code == 400

    # ── Phase 6.6: Version History API 测试 ─────────────────

    @patch("backend.security.rate_limiter.check", side_effect=_bypass_rate_limit)
    @patch("backend.governance.guard.guard_payload", side_effect=_bypass_governance)
    def test_list_versions_empty(self, mock_guard, mock_rate):
        """新模板版本列表为空"""
        from fastapi.testclient import TestClient
        from backend.app import app

        client = TestClient(app)

        create_resp = client.post("/boss/graph/templates", json={
            "name": "无版本",
            "nodes": _sample_api_nodes(),
        })
        tid = create_resp.json()["template"]["template_id"]

        response = client.get(f"/boss/graph/templates/{tid}/versions")
        assert response.status_code == 200
        data = response.json()
        assert data["ok"] is True
        assert data["total"] == 0
        assert data["versions"] == []

    @patch("backend.security.rate_limiter.check", side_effect=_bypass_rate_limit)
    @patch("backend.governance.guard.guard_payload", side_effect=_bypass_governance)
    def test_update_auto_creates_version(self, mock_guard, mock_rate):
        """PUT 更新自动创建版本快照"""
        from fastapi.testclient import TestClient
        from backend.app import app

        client = TestClient(app)

        create_resp = client.post("/boss/graph/templates", json={
            "name": "原始名称",
            "nodes": _sample_api_nodes(),
            "edges": _sample_api_edges(),
        })
        tid = create_resp.json()["template"]["template_id"]

        # 更新
        client.put(f"/boss/graph/templates/{tid}", json={
            "name": "更新后名称",
            "nodes": _sample_api_nodes(),
        })

        # 版本列表应有 1 条
        response = client.get(f"/boss/graph/templates/{tid}/versions")
        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 1
        assert data["versions"][0]["name"] == "原始名称"
        assert data["versions"][0]["node_count"] == 2
        assert data["versions"][0]["edge_count"] == 1

    @patch("backend.security.rate_limiter.check", side_effect=_bypass_rate_limit)
    @patch("backend.governance.guard.guard_payload", side_effect=_bypass_governance)
    def test_get_version_detail(self, mock_guard, mock_rate):
        """获取版本详情"""
        from fastapi.testclient import TestClient
        from backend.app import app

        client = TestClient(app)

        create_resp = client.post("/boss/graph/templates", json={
            "name": "详情测试",
            "nodes": _sample_api_nodes(),
            "edges": _sample_api_edges(),
        })
        tid = create_resp.json()["template"]["template_id"]

        client.put(f"/boss/graph/templates/{tid}", json={
            "name": "更新后",
            "nodes": _sample_api_nodes(),
        })

        # 获取版本列表
        versions_resp = client.get(f"/boss/graph/templates/{tid}/versions")
        vid = versions_resp.json()["versions"][0]["version_id"]

        # 获取版本详情
        response = client.get(f"/boss/graph/templates/{tid}/versions/{vid}")
        assert response.status_code == 200
        data = response.json()
        assert data["ok"] is True
        assert data["version"]["version_id"] == vid
        assert data["version"]["name"] == "详情测试"
        assert len(data["version"]["nodes"]) == 2

    @patch("backend.security.rate_limiter.check", side_effect=_bypass_rate_limit)
    @patch("backend.governance.guard.guard_payload", side_effect=_bypass_governance)
    def test_get_version_nonexistent_404(self, mock_guard, mock_rate):
        """不存在的版本返回 404"""
        from fastapi.testclient import TestClient
        from backend.app import app

        client = TestClient(app)

        create_resp = client.post("/boss/graph/templates", json={
            "name": "测试",
            "nodes": _sample_api_nodes(),
        })
        tid = create_resp.json()["template"]["template_id"]

        response = client.get(f"/boss/graph/templates/{tid}/versions/ver_nonexistent")
        assert response.status_code == 404

    @patch("backend.security.rate_limiter.check", side_effect=_bypass_rate_limit)
    @patch("backend.governance.guard.guard_payload", side_effect=_bypass_governance)
    def test_restore_version(self, mock_guard, mock_rate):
        """回滚到旧版本"""
        from fastapi.testclient import TestClient
        from backend.app import app

        client = TestClient(app)

        create_resp = client.post("/boss/graph/templates", json={
            "name": "原始版本",
            "nodes": _sample_api_nodes(),
            "edges": _sample_api_edges(),
        })
        tid = create_resp.json()["template"]["template_id"]

        # 更新
        client.put(f"/boss/graph/templates/{tid}", json={
            "name": "更新后版本",
            "nodes": _sample_api_nodes(),
        })

        # 获取版本 ID
        versions_resp = client.get(f"/boss/graph/templates/{tid}/versions")
        vid = versions_resp.json()["versions"][0]["version_id"]

        # 回滚
        response = client.post(f"/boss/graph/templates/{tid}/versions/{vid}/restore")
        assert response.status_code == 200
        data = response.json()
        assert data["ok"] is True
        assert data["template"]["name"] == "原始版本"
        assert data["restored_from_version"] == vid

        # 版本列表应有 2 条（原始 + 更新后）
        versions_resp2 = client.get(f"/boss/graph/templates/{tid}/versions")
        assert versions_resp2.json()["total"] == 2

    @patch("backend.security.rate_limiter.check", side_effect=_bypass_rate_limit)
    @patch("backend.governance.guard.guard_payload", side_effect=_bypass_governance)
    def test_restore_nonexistent_version_404(self, mock_guard, mock_rate):
        """回滚不存在的版本返回 404"""
        from fastapi.testclient import TestClient
        from backend.app import app

        client = TestClient(app)

        create_resp = client.post("/boss/graph/templates", json={
            "name": "测试",
            "nodes": _sample_api_nodes(),
        })
        tid = create_resp.json()["template"]["template_id"]

        response = client.post(f"/boss/graph/templates/{tid}/versions/ver_nonexistent/restore")
        assert response.status_code == 404

    @patch("backend.security.rate_limiter.check", side_effect=_bypass_rate_limit)
    @patch("backend.governance.guard.guard_payload", side_effect=_bypass_governance)
    def test_restore_rejects_corrupt_version(self, mock_guard, mock_rate):
        """损坏的版本快照不能回滚，也不会额外保存当前版本"""
        from fastapi.testclient import TestClient
        from backend.app import app

        client = TestClient(app)
        create_resp = client.post("/boss/graph/templates", json={
            "name": "原始版本",
            "nodes": _sample_api_nodes(),
        })
        tid = create_resp.json()["template"]["template_id"]
        client.put(f"/boss/graph/templates/{tid}", json={
            "name": "当前版本",
            "nodes": _sample_api_nodes(),
        })

        versions_resp = client.get(f"/boss/graph/templates/{tid}/versions")
        vid = versions_resp.json()["versions"][0]["version_id"]
        version_path = self.versions_dir / tid / f"{vid}.json"
        version_data = json.loads(version_path.read_text(encoding="utf-8"))
        version_data["nodes"] = []
        version_path.write_text(
            json.dumps(version_data, ensure_ascii=False),
            encoding="utf-8",
        )

        response = client.post(f"/boss/graph/templates/{tid}/versions/{vid}/restore")
        assert response.status_code == 409
        current = client.get(f"/boss/graph/templates/{tid}").json()["template"]
        assert current["name"] == "当前版本"
        assert client.get(f"/boss/graph/templates/{tid}/versions").json()["total"] == 1

    @patch("backend.security.rate_limiter.check", side_effect=_bypass_rate_limit)
    @patch("backend.governance.guard.guard_payload", side_effect=_bypass_governance)
    def test_restore_nonexistent_template_404(self, mock_guard, mock_rate):
        """回滚不存在的模板返回 404"""
        from fastapi.testclient import TestClient
        from backend.app import app

        client = TestClient(app)
        response = client.post("/boss/graph/templates/tpl_nonexistent/versions/ver_xxx/restore")
        assert response.status_code == 404

    @patch("backend.security.rate_limiter.check", side_effect=_bypass_rate_limit)
    @patch("backend.governance.guard.guard_payload", side_effect=_bypass_governance)
    def test_list_versions_nonexistent_template_404(self, mock_guard, mock_rate):
        """列出不存在模板的版本返回 404"""
        from fastapi.testclient import TestClient
        from backend.app import app

        client = TestClient(app)
        response = client.get("/boss/graph/templates/tpl_nonexistent/versions")
        assert response.status_code == 404

    @patch("backend.security.rate_limiter.check", side_effect=_bypass_rate_limit)
    @patch("backend.governance.guard.guard_payload", side_effect=_bypass_governance)
    def test_delete_template_removes_versions(self, mock_guard, mock_rate):
        """删除模板时同步清理版本"""
        from fastapi.testclient import TestClient
        from backend.app import app

        client = TestClient(app)

        create_resp = client.post("/boss/graph/templates", json={
            "name": "待删除",
            "nodes": _sample_api_nodes(),
        })
        tid = create_resp.json()["template"]["template_id"]

        # 创建一个版本
        client.put(f"/boss/graph/templates/{tid}", json={
            "name": "更新",
            "nodes": _sample_api_nodes(),
        })

        # 删除模板
        response = client.delete(f"/boss/graph/templates/{tid}")
        assert response.status_code == 200

        # 版本列表应返回 404（模板已不存在）
        versions_resp = client.get(f"/boss/graph/templates/{tid}/versions")
        assert versions_resp.status_code == 404
