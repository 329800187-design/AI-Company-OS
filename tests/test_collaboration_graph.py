"""Collaboration Graph 单元测试"""
import pytest
from backend.services.collaboration_graph import (
    CollaborationNode,
    CollaborationEdge,
    CollaborationGraph,
    GraphValidationResult,
    validate_graph,
    topological_waves,
    build_boss_lite_graph,
    graph_to_waves_summary,
)


# ── validate_graph ────────────────────────────────────────────


class TestValidateGraph:
    """图校验测试"""

    def test_empty_graph_is_valid(self):
        graph = CollaborationGraph()
        result = validate_graph(graph)
        assert result.valid is True
        assert result.errors == []

    def test_single_node_no_edges(self):
        graph = CollaborationGraph(
            nodes=[CollaborationNode(id="a", agent_id="a")],
        )
        result = validate_graph(graph)
        assert result.valid is True
        # 孤立节点 → warning
        assert any("孤立节点" in w for w in result.warnings)

    def test_simple_valid_graph(self):
        graph = CollaborationGraph(
            nodes=[
                CollaborationNode(id="a", agent_id="a"),
                CollaborationNode(id="b", agent_id="b"),
            ],
            edges=[
                CollaborationEdge(from_node="a", to_node="b"),
            ],
        )
        result = validate_graph(graph)
        assert result.valid is True
        assert result.errors == []

    def test_duplicate_node_id(self):
        graph = CollaborationGraph(
            nodes=[
                CollaborationNode(id="a", agent_id="a"),
                CollaborationEdge(from_node="a", to_node="a"),  # 自环
            ],
        )
        # 用 edges 替代
        graph2 = CollaborationGraph(
            nodes=[
                CollaborationNode(id="a", agent_id="a"),
                CollaborationNode(id="a", agent_id="a2"),  # 重复 ID
            ],
        )
        result = validate_graph(graph2)
        assert result.valid is False
        assert any("重复" in e for e in result.errors)

    def test_edge_references_missing_node(self):
        graph = CollaborationGraph(
            nodes=[CollaborationNode(id="a", agent_id="a")],
            edges=[CollaborationEdge(from_node="a", to_node="x")],
        )
        result = validate_graph(graph)
        assert result.valid is False
        assert any("不存在的节点" in e for e in result.errors)

    def test_self_loop(self):
        graph = CollaborationGraph(
            nodes=[CollaborationNode(id="a", agent_id="a")],
            edges=[CollaborationEdge(from_node="a", to_node="a")],
        )
        result = validate_graph(graph)
        assert result.valid is False
        assert any("自环" in e for e in result.errors)

    def test_cycle_detection(self):
        """a → b → c → a 形成循环"""
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

    def test_no_cycle_diamond(self):
        """菱形图：a → b, a → c, b → d, c → d（无环）"""
        graph = CollaborationGraph(
            nodes=[
                CollaborationNode(id="a", agent_id="a"),
                CollaborationNode(id="b", agent_id="b"),
                CollaborationNode(id="c", agent_id="c"),
                CollaborationNode(id="d", agent_id="d"),
            ],
            edges=[
                CollaborationEdge(from_node="a", to_node="b"),
                CollaborationEdge(from_node="a", to_node="c"),
                CollaborationEdge(from_node="b", to_node="d"),
                CollaborationEdge(from_node="c", to_node="d"),
            ],
        )
        result = validate_graph(graph)
        assert result.valid is True


# ── topological_waves ─────────────────────────────────────────


class TestTopologicalWaves:
    """拓扑排序 wave 划分测试"""

    def test_empty_graph(self):
        graph = CollaborationGraph()
        waves = topological_waves(graph)
        assert waves == []

    def test_single_node(self):
        graph = CollaborationGraph(
            nodes=[CollaborationNode(id="a", agent_id="a")],
        )
        waves = topological_waves(graph)
        assert waves == [["a"]]

    def test_two_independent_nodes(self):
        """两个无依赖节点 → 同一 wave"""
        graph = CollaborationGraph(
            nodes=[
                CollaborationNode(id="a", agent_id="a"),
                CollaborationNode(id="b", agent_id="b"),
            ],
        )
        waves = topological_waves(graph)
        assert len(waves) == 1
        assert set(waves[0]) == {"a", "b"}

    def test_linear_chain(self):
        """a → b → c → 三波"""
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

    def test_two_wave_parallel(self):
        """research/data → marketing/image/website 两波"""
        graph = CollaborationGraph(
            nodes=[
                CollaborationNode(id="research", agent_id="research"),
                CollaborationNode(id="data", agent_id="data"),
                CollaborationNode(id="marketing", agent_id="marketing"),
                CollaborationNode(id="image", agent_id="image"),
                CollaborationNode(id="website", agent_id="website"),
            ],
            edges=[
                CollaborationEdge(from_node="research", to_node="marketing"),
                CollaborationEdge(from_node="research", to_node="image"),
                CollaborationEdge(from_node="research", to_node="website"),
                CollaborationEdge(from_node="data", to_node="marketing"),
                CollaborationEdge(from_node="data", to_node="image"),
                CollaborationEdge(from_node="data", to_node="website"),
            ],
        )
        waves = topological_waves(graph)
        assert len(waves) == 2
        assert set(waves[0]) == {"data", "research"}
        assert set(waves[1]) == {"image", "marketing", "website"}

    def test_three_wave_diamond(self):
        """a → b, a → c, b → d, c → d → 三波"""
        graph = CollaborationGraph(
            nodes=[
                CollaborationNode(id="a", agent_id="a"),
                CollaborationNode(id="b", agent_id="b"),
                CollaborationNode(id="c", agent_id="c"),
                CollaborationNode(id="d", agent_id="d"),
            ],
            edges=[
                CollaborationEdge(from_node="a", to_node="b"),
                CollaborationEdge(from_node="a", to_node="c"),
                CollaborationEdge(from_node="b", to_node="d"),
                CollaborationEdge(from_node="c", to_node="d"),
            ],
        )
        waves = topological_waves(graph)
        assert len(waves) == 3
        assert waves[0] == ["a"]
        assert set(waves[1]) == {"b", "c"}
        assert waves[2] == ["d"]

    def test_cycle_raises_error(self):
        """循环图应抛出 ValueError"""
        graph = CollaborationGraph(
            nodes=[
                CollaborationNode(id="a", agent_id="a"),
                CollaborationNode(id="b", agent_id="b"),
            ],
            edges=[
                CollaborationEdge(from_node="a", to_node="b"),
                CollaborationEdge(from_node="b", to_node="a"),
            ],
        )
        with pytest.raises(ValueError, match="校验失败"):
            topological_waves(graph)


# ── build_boss_lite_graph ─────────────────────────────────────


class TestBuildBossLiteGraph:
    """Boss Lite 图构造测试"""

    def test_full_graph(self):
        graph = build_boss_lite_graph()
        assert len(graph.nodes) == 5
        assert len(graph.edges) == 6

    def test_partial_agents(self):
        """只选 research + marketing"""
        graph = build_boss_lite_graph(agents=["research", "marketing"])
        assert len(graph.nodes) == 2
        assert len(graph.edges) == 1
        assert graph.edges[0].from_node == "research"
        assert graph.edges[0].to_node == "marketing"

    def test_wave_output(self):
        graph = build_boss_lite_graph()
        waves = topological_waves(graph)
        assert len(waves) == 2
        assert set(waves[0]) == {"data", "research"}
        assert set(waves[1]) == {"image", "marketing", "website"}

    def test_summary_string(self):
        graph = build_boss_lite_graph()
        summary = graph_to_waves_summary(graph)
        # 输出格式: "data/research → image/marketing/website"
        assert "→" in summary
        parts = summary.split(" → ")
        assert len(parts) == 2


# ── CollaborationGraph 方法 ──────────────────────────────────


class TestGraphMethods:
    """Graph 实例方法测试"""

    def test_get_node(self):
        graph = build_boss_lite_graph()
        node = graph.get_node("research")
        assert node is not None
        assert node.agent_id == "research"
        assert node.label == "市场调研"

    def test_get_node_not_found(self):
        graph = build_boss_lite_graph()
        assert graph.get_node("nonexistent") is None

    def test_node_ids(self):
        graph = build_boss_lite_graph()
        ids = graph.node_ids()
        assert ids == {"research", "data", "marketing", "image", "website"}

    def test_upstream_of(self):
        graph = build_boss_lite_graph()
        upstream = graph.upstream_of("marketing")
        assert set(upstream) == {"research", "data"}

    def test_downstream_of(self):
        graph = build_boss_lite_graph()
        downstream = graph.downstream_of("research")
        assert set(downstream) == {"marketing", "image", "website"}

    def test_upstream_of_root(self):
        graph = build_boss_lite_graph()
        assert graph.upstream_of("research") == []
