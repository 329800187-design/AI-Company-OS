"""
Collaboration Graph — 通用 DAG 协作图模型

把 Boss Lite 硬编码的两波 handoff 抽象成通用有向无环图（DAG）。
本模块只做纯函数/轻量类，不改现有路由，不接入生产执行路径。

核心功能：
  - CollaborationNode / CollaborationEdge / CollaborationGraph 数据结构
  - validate_graph(graph) — 校验图合法性（自环、循环、孤立节点）
  - topological_waves(graph) — Kahn's algorithm 变体，输出 wave 划分
  - build_boss_lite_graph() — 构造 Boss Lite 图，方便测试

设计文档：docs/phase3_collaboration_graph_design.md
"""
from __future__ import annotations

import logging
from collections import defaultdict, deque
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


# ── 数据结构 ─────────────────────────────────────────────────


@dataclass
class CollaborationNode:
    """协作图中的一个节点，对应一个 Agent 执行单元。"""
    id: str                              # 唯一标识
    agent_id: str                        # 实际执行的 agent_id
    label: str = ""                      # 显示名称
    config: Dict[str, Any] = field(default_factory=dict)  # 节点配置


@dataclass
class CollaborationEdge:
    """从一个节点指向另一个节点的有向边，表示数据依赖。"""
    from_node: str                       # 上游节点 ID
    to_node: str                         # 下游节点 ID
    label: str = ""                      # 边描述


@dataclass
class CollaborationGraph:
    """有向无环图（DAG），描述多个 Agent 之间的协作依赖关系。"""
    nodes: List[CollaborationNode] = field(default_factory=list)
    edges: List[CollaborationEdge] = field(default_factory=list)

    def get_node(self, node_id: str) -> Optional[CollaborationNode]:
        """按 ID 查找节点"""
        for node in self.nodes:
            if node.id == node_id:
                return node
        return None

    def node_ids(self) -> set:
        """返回所有节点 ID 的集合"""
        return {node.id for node in self.nodes}

    def upstream_of(self, node_id: str) -> List[str]:
        """返回指定节点的所有上游节点 ID"""
        return [edge.from_node for edge in self.edges if edge.to_node == node_id]

    def downstream_of(self, node_id: str) -> List[str]:
        """返回指定节点的所有下游节点 ID"""
        return [edge.to_node for edge in self.edges if edge.from_node == node_id]


# ── 验证 ─────────────────────────────────────────────────────


@dataclass
class GraphValidationResult:
    """图校验结果"""
    valid: bool = True
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)


def validate_graph(graph: CollaborationGraph) -> GraphValidationResult:
    """
    校验协作图的合法性。

    检查项：
      1. 节点 ID 唯一性
      2. 边引用合法性（from_node / to_node 必须存在于 nodes）
      3. 自环检测（from_node != to_node）
      4. 循环依赖检测（DFS 环路检测）
      5. 孤立节点警告（无任何边连接）

    Returns:
        GraphValidationResult
    """
    result = GraphValidationResult()
    node_ids = set()
    node_id_list = []  # 保持顺序

    # 1. 节点 ID 唯一性
    for node in graph.nodes:
        if node.id in node_ids:
            result.errors.append(f"重复的节点 ID: '{node.id}'")
            result.valid = False
        node_ids.add(node.id)
        node_id_list.append(node.id)

    # 2. 边引用合法性 + 3. 自环检测
    for edge in graph.edges:
        if edge.from_node not in node_ids:
            result.errors.append(
                f"边引用了不存在的节点: from_node='{edge.from_node}'"
            )
            result.valid = False
        if edge.to_node not in node_ids:
            result.errors.append(
                f"边引用了不存在的节点: to_node='{edge.to_node}'"
            )
            result.valid = False
        if edge.from_node == edge.to_node:
            result.errors.append(
                f"自环: '{edge.from_node}' → '{edge.to_node}'"
            )
            result.valid = False

    # 如果基本校验不通过，不再做环路检测
    if not result.valid:
        return result

    # 4. 循环依赖检测（DFS）
    cycle = _detect_cycle(graph)
    if cycle:
        result.errors.append(f"循环依赖: {' → '.join(cycle)}")
        result.valid = False

    # 5. 孤立节点警告
    connected = set()
    for edge in graph.edges:
        connected.add(edge.from_node)
        connected.add(edge.to_node)
    for node in graph.nodes:
        if node.id not in connected:
            result.warnings.append(f"孤立节点: '{node.id}' (无任何边连接)")

    return result


def _detect_cycle(graph: CollaborationGraph) -> List[str]:
    """
    DFS 检测有向图中的环路。

    Returns:
        环路路径列表，如 ["a", "b", "c", "a"]；
        无环返回空列表。
    """
    WHITE, GRAY, BLACK = 0, 1, 2
    color: Dict[str, int] = {node.id: WHITE for node in graph.nodes}
    parent: Dict[str, Optional[str]] = {node.id: None for node in graph.nodes}

    # 邻接表
    adj: Dict[str, List[str]] = defaultdict(list)
    for edge in graph.edges:
        adj[edge.from_node].append(edge.to_node)

    def dfs(u: str) -> List[str]:
        color[u] = GRAY
        for v in adj[u]:
            if color[v] == GRAY:
                # 找到环，回溯路径
                cycle = [v]
                current = u
                while current != v:
                    cycle.append(current)
                    current = parent[current]
                    if current is None:
                        break
                cycle.append(v)
                cycle.reverse()
                return cycle
            if color[v] == WHITE:
                parent[v] = u
                result = dfs(v)
                if result:
                    return result
        color[u] = BLACK
        return []

    for node in graph.nodes:
        if color[node.id] == WHITE:
            cycle = dfs(node.id)
            if cycle:
                return cycle

    return []


# ── 拓扑排序 → Wave 划分 ─────────────────────────────────────


def topological_waves(graph: CollaborationGraph) -> List[List[str]]:
    """
    Kahn's algorithm 变体：将 DAG 拓扑排序并按 wave 分组。

    同一 wave 内的节点互不依赖，可以并行执行。

    Args:
        graph: 已校验的协作图

    Returns:
        waves: List[List[str]] — 每个元素是一个 wave 的节点 ID 列表
               例如: [["research", "data"], ["marketing", "image", "website"]]

    Raises:
        ValueError: 如果图中存在循环（节点无法全部分配到 wave）
    """
    # 校验
    validation = validate_graph(graph)
    if not validation.valid:
        raise ValueError(f"图校验失败: {'; '.join(validation.errors)}")

    # 构建邻接表和入度表
    in_degree: Dict[str, int] = {node.id: 0 for node in graph.nodes}
    adj: Dict[str, List[str]] = defaultdict(list)

    for edge in graph.edges:
        adj[edge.from_node].append(edge.to_node)
        in_degree[edge.to_node] += 1

    # Wave 0: 入度为 0 的节点
    queue = deque()
    for node_id, deg in in_degree.items():
        if deg == 0:
            queue.append(node_id)

    waves: List[List[str]] = []
    visited = set()

    while queue:
        wave = []
        # 当前队列中的所有节点属于同一 wave（互不依赖）
        for _ in range(len(queue)):
            node_id = queue.popleft()
            wave.append(node_id)
            visited.add(node_id)

        if wave:
            waves.append(sorted(wave))  # 排序保证稳定输出

        # 移除当前 wave 节点的出边，更新入度
        for node_id in wave:
            for downstream in adj[node_id]:
                in_degree[downstream] -= 1
                if in_degree[downstream] == 0 and downstream not in visited:
                    queue.append(downstream)

    # 检查是否所有节点都被分配
    if len(visited) != len(graph.nodes):
        unvisited = [node.id for node in graph.nodes if node.id not in visited]
        raise ValueError(f"存在循环依赖，以下节点无法分配: {unvisited}")

    return waves


# ── Boss Lite 图构造 ─────────────────────────────────────────


def build_boss_lite_graph(
    agents: Optional[List[str]] = None,
) -> CollaborationGraph:
    """
    构造 Boss Lite 默认协作图。

    默认拓扑：
        research ──→ marketing
        research ──→ image
        research ──→ website
        data     ──→ marketing
        data     ──→ image
        data     ──→ website

    Args:
        agents: 可选，指定要包含的 agent ID 列表。
                None 表示全部 5 个。

    Returns:
        CollaborationGraph 实例
    """
    all_agents = ["research", "data", "marketing", "image", "website"]
    selected = set(agents) if agents else set(all_agents)

    nodes = []
    agent_labels = {
        "research": "市场调研",
        "data": "数据分析",
        "marketing": "营销方案",
        "image": "视觉方案",
        "website": "落地页方案",
    }
    agent_task_types = {
        "research": "research_brief",
        "data": "data_report",
        "marketing": "copywriting",
        "image": "image_prompt",
        "website": "landing_page_copy",
    }

    for agent_id in all_agents:
        if agent_id in selected:
            nodes.append(CollaborationNode(
                id=agent_id,
                agent_id=agent_id,
                label=agent_labels.get(agent_id, agent_id),
                config={"task_type": agent_task_types.get(agent_id, "")},
            ))

    # 上游 → 下游的完整边定义
    all_edges = [
        ("research", "marketing", "调研洞察"),
        ("research", "image", "调研洞察"),
        ("research", "website", "调研洞察"),
        ("data", "marketing", "数据洞察"),
        ("data", "image", "数据洞察"),
        ("data", "website", "数据洞察"),
    ]

    edges = [
        CollaborationEdge(from_node=f, to_node=t, label=lbl)
        for f, t, lbl in all_edges
        if f in selected and t in selected
    ]

    return CollaborationGraph(nodes=nodes, edges=edges)


def graph_to_waves_summary(graph: CollaborationGraph) -> str:
    """
    将图的 wave 划分格式化为可读字符串。

    例如: "research/data → marketing/image/website"
    """
    try:
        waves = topological_waves(graph)
    except ValueError as e:
        return f"[error: {e}]"

    parts = []
    for wave in waves:
        parts.append("/".join(wave))
    return " → ".join(parts)
