"""Boss Graph 自定义 DAG 执行测试

覆盖场景：
  A. validate invalid graph: 缺失节点引用、自环、循环依赖
  B. graph waves: research → marketing、research + data → marketing
  C. request model: 单节点 graph、edge.handoff_type 默认值
  D. API 最小集成（monkeypatch mock execute_agent）
"""
import pytest
from unittest.mock import patch, MagicMock

from backend.services.collaboration_graph import (
    CollaborationNode,
    CollaborationEdge,
    CollaborationGraph,
    validate_graph,
    topological_waves,
)
from backend.routers.boss_router import (
    BossGraphNodeRequest,
    BossGraphEdgeRequest,
    BossGraphExecuteRequest,
    _build_custom_graph,
)


# ── A. validate invalid graph ─────────────────────────────────


class TestInvalidGraphValidation:
    """无效图校验（直接调用 validate_graph，不经过 API）"""

    def test_missing_from_node_reference(self):
        """边引用不存在的 from_node → invalid"""
        graph = CollaborationGraph(
            nodes=[CollaborationNode(id="a", agent_id="a")],
            edges=[CollaborationEdge(from_node="x", to_node="a")],
        )
        result = validate_graph(graph)
        assert result.valid is False
        assert any("不存在的节点" in e for e in result.errors)

    def test_missing_to_node_reference(self):
        """边引用不存在的 to_node → invalid"""
        graph = CollaborationGraph(
            nodes=[CollaborationNode(id="a", agent_id="a")],
            edges=[CollaborationEdge(from_node="a", to_node="x")],
        )
        result = validate_graph(graph)
        assert result.valid is False
        assert any("不存在的节点" in e for e in result.errors)

    def test_self_loop(self):
        """自环 → invalid"""
        graph = CollaborationGraph(
            nodes=[CollaborationNode(id="a", agent_id="a")],
            edges=[CollaborationEdge(from_node="a", to_node="a")],
        )
        result = validate_graph(graph)
        assert result.valid is False
        assert any("自环" in e for e in result.errors)

    def test_cycle_dependency(self):
        """循环依赖 a → b → c → a → invalid"""
        graph = CollaborationGraph(
            nodes=[
                CollaborationNode(id="a", agent_id="a"),
                CollaborationNode(id="b", agent_id="b"),
                CollaborationNode(id="c", agent_id="c"),
            ],
            edges=[
                CollaborationEdge(from_node="a", to_node="b"),
                CollaborationEdge(from_node="b", to_node="c"),
                CollaborationEdge(from_node="c", to_node="a"),
            ],
        )
        result = validate_graph(graph)
        assert result.valid is False
        assert any("循环依赖" in e for e in result.errors)

    def test_duplicate_node_ids(self):
        """重复节点 ID → invalid"""
        graph = CollaborationGraph(
            nodes=[
                CollaborationNode(id="a", agent_id="a"),
                CollaborationNode(id="a", agent_id="a2"),
            ],
        )
        result = validate_graph(graph)
        assert result.valid is False
        assert any("重复" in e for e in result.errors)


# ── B. graph waves ─────────────────────────────────────────────


class TestCustomGraphWaves:
    """自定义图 wave 划分"""

    def test_research_marketing_two_waves(self):
        """research → marketing 得到 [["research"], ["marketing"]]"""
        graph = CollaborationGraph(
            nodes=[
                CollaborationNode(id="research", agent_id="research"),
                CollaborationNode(id="marketing", agent_id="marketing"),
            ],
            edges=[
                CollaborationEdge(from_node="research", to_node="marketing"),
            ],
        )
        waves = topological_waves(graph)
        assert waves == [["research"], ["marketing"]]

    def test_research_data_marketing_two_waves(self):
        """research + data → marketing 得到两波"""
        graph = CollaborationGraph(
            nodes=[
                CollaborationNode(id="research", agent_id="research"),
                CollaborationNode(id="data", agent_id="data"),
                CollaborationNode(id="marketing", agent_id="marketing"),
            ],
            edges=[
                CollaborationEdge(from_node="research", to_node="marketing"),
                CollaborationEdge(from_node="data", to_node="marketing"),
            ],
        )
        waves = topological_waves(graph)
        assert len(waves) == 2
        assert set(waves[0]) == {"research", "data"}
        assert waves[1] == ["marketing"]

    def test_single_node_one_wave(self):
        """单节点图 → 一个 wave"""
        graph = CollaborationGraph(
            nodes=[CollaborationNode(id="solo", agent_id="solo")],
        )
        waves = topological_waves(graph)
        assert waves == [["solo"]]

    def test_three_level_chain(self):
        """a → b → c 三波"""
        graph = CollaborationGraph(
            nodes=[
                CollaborationNode(id="a", agent_id="a"),
                CollaborationNode(id="b", agent_id="b"),
                CollaborationNode(id="c", agent_id="c"),
            ],
            edges=[
                CollaborationEdge(from_node="a", to_node="b"),
                CollaborationEdge(from_node="b", to_node="c"),
            ],
        )
        waves = topological_waves(graph)
        assert waves == [["a"], ["b"], ["c"]]


# ── C. request model ──────────────────────────────────────────


class TestRequestModel:
    """请求模型测试"""

    def test_single_node_graph(self):
        """单节点 graph 可构造"""
        request = BossGraphExecuteRequest(
            goal="测试目标",
            nodes=[
                BossGraphNodeRequest(
                    id="solo",
                    agent_id="research",
                    task_type="research_brief",
                    title="单节点调研",
                    prompt="做一次调研",
                )
            ],
        )
        assert len(request.nodes) == 1
        assert request.edges == []
        assert request.save_to_delivery is True

    def test_edge_handoff_type_default(self):
        """edge.handoff_type 默认为 context"""
        edge = BossGraphEdgeRequest(from_node="a", to_node="b")
        assert edge.handoff_type == "context"

    def test_custom_handoff_type(self):
        """edge.handoff_type 可自定义"""
        edge = BossGraphEdgeRequest(from_node="a", to_node="b", handoff_type="data")
        assert edge.handoff_type == "data"

    def test_build_custom_graph(self):
        """_build_custom_graph 正确构造 CollaborationGraph"""
        request = BossGraphExecuteRequest(
            goal="测试",
            nodes=[
                BossGraphNodeRequest(id="a", agent_id="research", task_type="research_brief", title="调研", prompt="p1"),
                BossGraphNodeRequest(id="b", agent_id="marketing", task_type="copywriting", title="营销", prompt="p2"),
            ],
            edges=[
                BossGraphEdgeRequest(from_node="a", to_node="b"),
            ],
        )
        graph = _build_custom_graph(request)
        assert len(graph.nodes) == 2
        assert len(graph.edges) == 1
        assert graph.nodes[0].id == "a"
        assert graph.nodes[0].config["task_type"] == "research_brief"
        assert graph.nodes[0].config["prompt"] == "p1"
        assert graph.edges[0].from_node == "a"
        assert graph.edges[0].to_node == "b"

    def test_save_to_delivery_default_true(self):
        """save_to_delivery 默认 true"""
        request = BossGraphExecuteRequest(
            goal="测试",
            nodes=[BossGraphNodeRequest(id="a", agent_id="a")],
        )
        assert request.save_to_delivery is True


# ── D. API 最小集成 ───────────────────────────────────────────


def _mock_execute_agent(agent_id, task):
    """Mock execute_agent 返回标准结果"""
    mock_result = MagicMock()
    mock_result.ok = True
    mock_result.summary = f"{agent_id} 执行完成"
    mock_result.structured_output = {
        "summary": f"{agent_id} 摘要",
        "key_findings": [f"{agent_id} 发现1", f"{agent_id} 发现2"],
    }
    mock_result.warnings = []
    mock_result.errors = []
    mock_result.error = None
    mock_result.model_dump.return_value = {
        "ok": True,
        "agent_id": agent_id,
        "summary": f"{agent_id} 执行完成",
        "structured_output": {
            "summary": f"{agent_id} 摘要",
            "key_findings": [f"{agent_id} 发现1", f"{agent_id} 发现2"],
        },
        "warnings": [],
        "errors": [],
        "error": None,
    }
    return mock_result


def _mock_execute_agent_fail(agent_id, task):
    """Mock execute_agent 模拟失败"""
    mock_result = MagicMock()
    mock_result.ok = False
    mock_result.summary = ""
    mock_result.structured_output = {}
    mock_result.warnings = []
    mock_result.errors = ["执行失败"]
    mock_result.error = "执行失败"
    mock_result.model_dump.return_value = {
        "ok": False,
        "agent_id": agent_id,
        "summary": "",
        "structured_output": {},
        "warnings": [],
        "errors": ["执行失败"],
        "error": "执行失败",
    }
    return mock_result


def _bypass_governance(payload, platform=None):
    """绕过 governance guard，始终放行"""
    from backend.governance.classifier import ClassificationResult
    return False, ClassificationResult(ok=True, confidence=1.0, reason="test bypass")


def _bypass_rate_limit(name, max_requests=5, window_seconds=60):
    """绕过 rate limiter"""
    return True, ""


class TestBossGraphAPI:
    """API 集成测试（mock execute_agent + bypass governance）"""

    @patch("backend.security.rate_limiter.check", side_effect=_bypass_rate_limit)
    @patch("backend.governance.scope_classifier.guard_payload", side_effect=_bypass_governance)
    @patch("backend.services.agent_executor.execute_agent", side_effect=_mock_execute_agent)
    def test_single_node_execute(self, mock_exec, mock_guard, mock_rate):
        """单节点执行 ok"""
        from fastapi.testclient import TestClient
        from backend.app import app

        client = TestClient(app)
        response = client.post("/boss/graph/execute", json={
            "goal": "为手工银饰品牌做一次市场调研",
            "nodes": [
                {
                    "id": "research",
                    "agent_id": "research",
                    "task_type": "research_brief",
                    "title": "市场调研",
                    "prompt": "做一次调研",
                }
            ],
            "save_to_delivery": False,
        })

        assert response.status_code == 200
        data = response.json()
        assert data["ok"] is True
        assert data["execution_mode"] == "custom_graph"
        assert len(data["results"]) == 1
        assert data["results"][0]["ok"] is True
        assert data["results"][0]["node_id"] == "research"
        assert data["results"][0]["used_handoff"] is False
        assert data["results"][0]["handoff_sources"] == []
        assert data["summary"]["succeeded"] == 1
        assert data["summary"]["failed"] == 0

    @patch("backend.security.rate_limiter.check", side_effect=_bypass_rate_limit)
    @patch("backend.governance.scope_classifier.guard_payload", side_effect=_bypass_governance)
    @patch("backend.services.agent_executor.execute_agent", side_effect=_mock_execute_agent)
    def test_research_marketing_handoff(self, mock_exec, mock_guard, mock_rate):
        """research → marketing 时 marketing used_handoff=true，handoff_sources=["research"]"""
        from fastapi.testclient import TestClient
        from backend.app import app

        client = TestClient(app)
        response = client.post("/boss/graph/execute", json={
            "goal": "为手工银饰品牌做一次新品上线",
            "nodes": [
                {
                    "id": "research",
                    "agent_id": "research",
                    "task_type": "research_brief",
                    "title": "市场调研",
                    "prompt": "调研手工银饰市场机会",
                },
                {
                    "id": "marketing",
                    "agent_id": "marketing",
                    "task_type": "copywriting",
                    "title": "营销文案",
                    "prompt": "基于上游洞察生成营销文案",
                },
            ],
            "edges": [
                {"from_node": "research", "to_node": "marketing"},
            ],
            "save_to_delivery": False,
        })

        assert response.status_code == 200
        data = response.json()
        assert data["ok"] is True
        assert len(data["waves"]) == 2
        assert data["waves"][0] == ["research"]
        assert data["waves"][1] == ["marketing"]

        # research 结果
        research_result = data["results"][0]
        assert research_result["node_id"] == "research"
        assert research_result["ok"] is True
        assert research_result["used_handoff"] is False

        # marketing 结果
        marketing_result = data["results"][1]
        assert marketing_result["node_id"] == "marketing"
        assert marketing_result["ok"] is True
        assert marketing_result["used_handoff"] is True
        assert marketing_result["handoff_sources"] == ["research"]

    @patch("backend.security.rate_limiter.check", side_effect=_bypass_rate_limit)
    @patch("backend.governance.scope_classifier.guard_payload", side_effect=_bypass_governance)
    def test_invalid_graph_returns_400(self, mock_guard, mock_rate):
        """无效图（缺失节点引用）返回 HTTP 400"""
        from fastapi.testclient import TestClient
        from backend.app import app

        client = TestClient(app)
        response = client.post("/boss/graph/execute", json={
            "goal": "为手工银饰品牌做一次新品上线",
            "nodes": [
                {"id": "a", "agent_id": "research", "title": "A", "prompt": "p"},
            ],
            "edges": [
                {"from_node": "a", "to_node": "x"},  # x 不存在
            ],
            "save_to_delivery": False,
        })

        assert response.status_code == 400

    @patch("backend.security.rate_limiter.check", side_effect=_bypass_rate_limit)
    @patch("backend.governance.scope_classifier.guard_payload", side_effect=_bypass_governance)
    def test_self_loop_returns_400(self, mock_guard, mock_rate):
        """自环返回 HTTP 400"""
        from fastapi.testclient import TestClient
        from backend.app import app

        client = TestClient(app)
        response = client.post("/boss/graph/execute", json={
            "goal": "为手工银饰品牌做一次新品上线",
            "nodes": [
                {"id": "a", "agent_id": "research", "title": "A", "prompt": "p"},
            ],
            "edges": [
                {"from_node": "a", "to_node": "a"},
            ],
            "save_to_delivery": False,
        })

        assert response.status_code == 400

    @patch("backend.security.rate_limiter.check", side_effect=_bypass_rate_limit)
    @patch("backend.governance.scope_classifier.guard_payload", side_effect=_bypass_governance)
    def test_cycle_returns_400(self, mock_guard, mock_rate):
        """循环依赖返回 HTTP 400"""
        from fastapi.testclient import TestClient
        from backend.app import app

        client = TestClient(app)
        response = client.post("/boss/graph/execute", json={
            "goal": "为手工银饰品牌做一次新品上线",
            "nodes": [
                {"id": "a", "agent_id": "research", "title": "A", "prompt": "p"},
                {"id": "b", "agent_id": "marketing", "title": "B", "prompt": "p"},
                {"id": "c", "agent_id": "data", "title": "C", "prompt": "p"},
            ],
            "edges": [
                {"from_node": "a", "to_node": "b"},
                {"from_node": "b", "to_node": "c"},
                {"from_node": "c", "to_node": "a"},
            ],
            "save_to_delivery": False,
        })

        assert response.status_code == 400

    @patch("backend.security.rate_limiter.check", side_effect=_bypass_rate_limit)
    @patch("backend.governance.scope_classifier.guard_payload", side_effect=_bypass_governance)
    @patch("backend.services.agent_executor.execute_agent")
    def test_upstream_fail_no_handoff(self, mock_exec, mock_guard, mock_rate):
        """research 失败时 marketing 的 handoff_sources 应为空"""

        def selective_fail(agent_id, task):
            if agent_id == "research":
                return _mock_execute_agent_fail(agent_id, task)
            return _mock_execute_agent(agent_id, task)

        mock_exec.side_effect = selective_fail

        from fastapi.testclient import TestClient
        from backend.app import app

        client = TestClient(app)
        response = client.post("/boss/graph/execute", json={
            "goal": "为手工银饰品牌做一次新品上线",
            "nodes": [
                {"id": "research", "agent_id": "research", "title": "调研", "prompt": "p"},
                {"id": "marketing", "agent_id": "marketing", "title": "营销", "prompt": "p"},
            ],
            "edges": [
                {"from_node": "research", "to_node": "marketing"},
            ],
            "save_to_delivery": False,
        })

        assert response.status_code == 200
        data = response.json()

        # research 失败
        research_result = data["results"][0]
        assert research_result["ok"] is False

        # marketing 成功但没有从 research handoff（因为 research 失败了）
        marketing_result = data["results"][1]
        assert marketing_result["ok"] is True
        assert marketing_result["used_handoff"] is False
        assert marketing_result["handoff_sources"] == []

    @patch("backend.security.rate_limiter.check", side_effect=_bypass_rate_limit)
    @patch("backend.governance.scope_classifier.guard_payload", side_effect=_bypass_governance)
    @patch("backend.services.agent_executor.execute_agent", side_effect=_mock_execute_agent)
    def test_save_to_minidelivery_writes_files(self, mock_exec, mock_guard, mock_rate, tmp_path):
        """save_to_delivery=true writes artifact, raw result, and metadata files."""
        import json
        from fastapi.testclient import TestClient
        from backend.app import app

        client = TestClient(app)

        with patch("backend.minidelivery.artifact_writer.OUTPUT_ROOT", tmp_path):
            response = client.post("/boss/graph/execute", json={
                "goal": "create a custom graph launch plan",
                "nodes": [
                    {
                        "id": "research",
                        "agent_id": "research",
                        "task_type": "research_brief",
                        "title": "Research",
                        "prompt": "Find market insights",
                    },
                    {
                        "id": "marketing",
                        "agent_id": "marketing",
                        "task_type": "copywriting",
                        "title": "Marketing",
                        "prompt": "Write launch copy",
                    },
                ],
                "edges": [
                    {"from_node": "research", "to_node": "marketing"},
                ],
                "save_to_delivery": True,
            })

        assert response.status_code == 200
        data = response.json()
        task_id = data["delivery_task_id"]
        assert task_id

        task_dir = tmp_path / task_id
        artifact_path = task_dir / "artifact.md"
        raw_path = task_dir / "raw_agent_result.json"
        result_path = task_dir / "result.json"

        assert artifact_path.exists()
        assert raw_path.exists()
        assert result_path.exists()
        assert "Boss Graph" in artifact_path.read_text(encoding="utf-8")

        raw = json.loads(raw_path.read_text(encoding="utf-8"))
        result = json.loads(result_path.read_text(encoding="utf-8"))
        assert raw["execution_mode"] == "custom_graph"
        assert raw["handoff_enabled"] is True
        assert result["artifact_type"] == "boss_graph"
        assert result["source_page"] == "boss_graph"
