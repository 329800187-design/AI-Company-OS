"""Boss Lite + CollaborationGraph 集成测试

验证 boss_router 的 DAG 协作图集成：
- graph waves 与执行顺序
- handoff sources 基于图上游依赖
- partial agents 正确行为
- results 顺序稳定性
"""
import pytest
from backend.services.collaboration_graph import (
    build_boss_lite_graph,
    topological_waves,
)


# ── Graph Waves 测试 ────────────────────────────────────────


class TestBossLiteGraphWaves:
    """Boss Lite 图 waves 正确性"""

    def test_default_5_agents_two_waves(self):
        """默认 5 个 agent 应产出两波：wave0=[data, research], wave1=[image, marketing, website]"""
        graph = build_boss_lite_graph()
        waves = topological_waves(graph)
        assert len(waves) == 2
        assert set(waves[0]) == {"research", "data"}
        assert set(waves[1]) == {"marketing", "image", "website"}

    def test_partial_research_marketing(self):
        """research + marketing → 两波，marketing 在 wave1"""
        graph = build_boss_lite_graph(agents=["research", "marketing"])
        waves = topological_waves(graph)
        assert len(waves) == 2
        assert waves[0] == ["research"]
        assert waves[1] == ["marketing"]

    def test_partial_data_website(self):
        """data + website → 两波，website 在 wave1"""
        graph = build_boss_lite_graph(agents=["data", "website"])
        waves = topological_waves(graph)
        assert len(waves) == 2
        assert waves[0] == ["data"]
        assert waves[1] == ["website"]

    def test_partial_research_data_only(self):
        """research + data → 同一 wave（无依赖）"""
        graph = build_boss_lite_graph(agents=["research", "data"])
        waves = topological_waves(graph)
        assert len(waves) == 1
        assert set(waves[0]) == {"research", "data"}

    def test_single_marketing_one_wave(self):
        """单独 marketing → 一个 wave"""
        graph = build_boss_lite_graph(agents=["marketing"])
        waves = topological_waves(graph)
        assert len(waves) == 1
        assert waves[0] == ["marketing"]

    def test_wave_order_stable_across_calls(self):
        """多次调用 waves 顺序稳定"""
        graph = build_boss_lite_graph()
        waves1 = topological_waves(graph)
        waves2 = topological_waves(graph)
        assert waves1 == waves2


# ── Handoff Sources 测试 ────────────────────────────────────


class TestBossLiteHandoffSources:
    """handoff sources 基于图上游依赖"""

    def test_marketing_upstream_includes_research_and_data(self):
        """默认图中 marketing 的上游是 research + data"""
        graph = build_boss_lite_graph()
        upstream = graph.upstream_of("marketing")
        assert set(upstream) == {"research", "data"}

    def test_image_upstream_includes_research_and_data(self):
        """默认图中 image 的上游是 research + data"""
        graph = build_boss_lite_graph()
        upstream = graph.upstream_of("image")
        assert set(upstream) == {"research", "data"}

    def test_website_upstream_includes_research_and_data(self):
        """默认图中 website 的上游是 research + data"""
        graph = build_boss_lite_graph()
        upstream = graph.upstream_of("website")
        assert set(upstream) == {"research", "data"}

    def test_research_marketing_handoff_only_research(self):
        """只选 research + marketing → marketing 的 handoff_sources 只有 research"""
        graph = build_boss_lite_graph(agents=["research", "marketing"])
        upstream = graph.upstream_of("marketing")
        assert upstream == ["research"]

    def test_data_website_handoff_only_data(self):
        """只选 data + website → website 的 handoff_sources 只有 data"""
        graph = build_boss_lite_graph(agents=["data", "website"])
        upstream = graph.upstream_of("website")
        assert upstream == ["data"]

    def test_marketing_alone_no_upstream(self):
        """单独 marketing → 无上游，不启用 handoff"""
        graph = build_boss_lite_graph(agents=["marketing"])
        upstream = graph.upstream_of("marketing")
        assert upstream == []
        # 确认无边
        assert len(graph.edges) == 0

    def test_research_data_no_downstream(self):
        """research + data 都是上游节点，无 handoff"""
        graph = build_boss_lite_graph(agents=["research", "data"])
        assert graph.upstream_of("research") == []
        assert graph.upstream_of("data") == []
        # 无边
        assert len(graph.edges) == 0


# ── Handoff Sources 模拟执行测试 ────────────────────────────


class TestBossLiteHandoffExecution:
    """模拟 handoff 逻辑（不调用真实 agent）"""

    def _simulate_handoff_sources(self, agents, results_map):
        """模拟 boss_lite_execute 中的 handoff source 计算逻辑"""
        graph = build_boss_lite_graph(agents=agents)
        upstream_map = {}
        for agent_id in agents:
            upstream = graph.upstream_of(agent_id)
            agent_ho_sources = [s for s in upstream if s in results_map and results_map[s].get("ok")]
            upstream_map[agent_id] = agent_ho_sources
        return upstream_map

    def test_research_marketing_handoff_sources_research_only(self):
        """research 成功 → marketing 的 handoff_sources = ["research"]"""
        results_map = {"research": {"ok": True, "summary": "调研结果", "structured_output": {}}}
        ho = self._simulate_handoff_sources(["research", "marketing"], results_map)
        assert ho["research"] == []
        assert ho["marketing"] == ["research"]

    def test_data_website_handoff_sources_data_only(self):
        """data 成功 → website 的 handoff_sources = ["data"]"""
        results_map = {"data": {"ok": True, "summary": "数据结果", "structured_output": {}}}
        ho = self._simulate_handoff_sources(["data", "website"], results_map)
        assert ho["data"] == []
        assert ho["website"] == ["data"]

    def test_marketing_alone_no_handoff(self):
        """单独 marketing → handoff_sources = []"""
        results_map = {}
        ho = self._simulate_handoff_sources(["marketing"], results_map)
        assert ho["marketing"] == []

    def test_default_5_agents_handoff_sources(self):
        """默认 5 个 agent，research+data 成功 → downstream 的 sources = ["data", "research"]"""
        results_map = {
            "research": {"ok": True, "summary": "", "structured_output": {}},
            "data": {"ok": True, "summary": "", "structured_output": {}},
        }
        ho = self._simulate_handoff_sources(
            ["research", "marketing", "image", "data", "website"],
            results_map,
        )
        assert ho["research"] == []
        assert ho["data"] == []
        assert set(ho["marketing"]) == {"research", "data"}
        assert set(ho["image"]) == {"research", "data"}
        assert set(ho["website"]) == {"research", "data"}

    def test_partial_failure_handoff(self):
        """research 成功但 data 失败 → marketing 只从 research handoff"""
        results_map = {
            "research": {"ok": True, "summary": "", "structured_output": {}},
            "data": {"ok": False, "error": "failed", "structured_output": {}},
        }
        ho = self._simulate_handoff_sources(
            ["research", "data", "marketing"],
            results_map,
        )
        assert ho["research"] == []
        assert ho["data"] == []
        assert ho["marketing"] == ["research"]


# ── Graph 结构测试 ──────────────────────────────────────────


class TestBossLiteGraphStructure:
    """图结构完整性"""

    def test_full_graph_node_count(self):
        graph = build_boss_lite_graph()
        assert len(graph.nodes) == 5

    def test_full_graph_edge_count(self):
        graph = build_boss_lite_graph()
        assert len(graph.edges) == 6

    def test_partial_graph_node_count(self):
        graph = build_boss_lite_graph(agents=["research", "marketing"])
        assert len(graph.nodes) == 2

    def test_partial_graph_edge_count(self):
        graph = build_boss_lite_graph(agents=["research", "marketing"])
        assert len(graph.edges) == 1

    def test_downstream_agents_set(self):
        """默认图中 downstream agents = {marketing, image, website}"""
        graph = build_boss_lite_graph()
        downstream = {edge.to_node for edge in graph.edges}
        assert downstream == {"marketing", "image", "website"}

    def test_upstream_agents_set(self):
        """默认图中 upstream agents = {research, data}"""
        graph = build_boss_lite_graph()
        upstream = {edge.from_node for edge in graph.edges}
        assert upstream == {"research", "data"}
