# 第三阶段 P0：Collaboration Graph 设计文档

> 阶段：Phase 3 — P0 Agent 协作通用化
> 创建日期：2026-07-07
> 状态：**架构设计 + 最小骨架**

---

## 一、当前 Boss Lite Handoff 现状

### 1.1 硬编码结构

Boss Lite 的协作逻辑全部硬编码在 `backend/routers/boss_router.py` 中：

```python
# Wave 分类：research/data 是上游，marketing/image/website 是下游
_WAVE1_AGENTS = {"research", "data"}
_WAVE2_AGENTS = {"marketing", "image", "website"}

HANDOFF_SOURCES = {
    "marketing": ["research", "data"],
    "image": ["research", "data"],
    "website": ["research", "data"],
}
```

### 1.2 执行流程

1. 用户输入一句话目标
2. `_classify_waves(selected_agents)` 把 agents 分成 wave1 / wave2
3. Wave 1 并行执行 research + data
4. `_extract_handoff_context(results_map)` 从 wave1 结果中提取固定字段
5. `_build_handoff_prompt(agent_id, handoff_ctx)` 为 wave2 agents 拼接 handoff 附言
6. Wave 2 并行执行 marketing + image + website
7. 组装结果，生成报告

### 1.3 硬编码的问题

| 问题 | 说明 |
|------|------|
| Wave 写死 | 只能 research/data → marketing/image/website，无法自定义 |
| Handoff 字段写死 | `_extract_handoff_context` 只提取 research_summary / data_key_metrics 等固定字段 |
| 无法扩展 | 加一个新 agent（如 video）需要改多处代码 |
| 无通用验证 | 没有 DAG 校验，无法检测循环依赖 |
| 与 collaboration_planner 割裂 | 已有的 CollaborationPlan 是线性步进，不支持 wave 并行 |

---

## 二、为什么需要 Collaboration Graph

### 2.1 目标

把 Boss Lite 的两波 handoff 思路抽象成**通用有向无环图（DAG）**，使得：

- 任意 Agent 之间可以定义依赖关系
- 自动拓扑排序 → 按 wave 并行执行
- 上下文（handoff payload）自动从上游传递到下游
- 未来支持用户自定义 DAG（但本轮不做）

### 2.2 与已有系统的关系

| 系统 | 定位 | 本轮是否修改 |
|------|------|-------------|
| `CollaborationPlan` / `CollaborationStep` | 线性步进执行，支持 depends_on | ❌ 不改 |
| `collaboration_executor.py` | 顺序执行 CollaborationPlan | ❌ 不改 |
| `boss_router.py` Boss Lite | 硬编码两波 handoff | ❌ 不改 |
| `collaboration_graph.py`（新建） | 通用 DAG → wave 划分 | ✅ 新建 |

**策略：** 新建 CollaborationGraph 作为独立模块，不接入任何现有路由。后续可以把 Boss Lite 的硬编码逻辑替换为 Graph 驱动。

---

## 三、核心概念

### 3.1 Graph（协作图）

一个有向无环图，描述多个 Agent 之间的依赖关系。

```
Graph = {
    nodes: [Node, Node, ...],
    edges: [Edge, Edge, ...],
}
```

### 3.2 Node（节点）

图中的一个 Agent 执行单元。

```
Node = {
    id: "research",           # 唯一标识，对应 agent_id
    agent_id: "research",     # 实际执行的 agent
    label: "市场调研",         # 可选，显示名称
    config: {                  # 可选，节点配置
        task_type: "research_brief",
        prompt_tpl: "...",
    }
}
```

### 3.3 Edge（边）

从一个节点指向另一个节点的有向边，表示数据依赖。

```
Edge = {
    from_node: "research",    # 上游节点 ID
    to_node: "marketing",     # 下游节点 ID
    label: "调研洞察",         # 可选，边的描述
}
```

含义：`marketing` 依赖 `research` 的输出。

### 3.4 Wave（执行波次）

拓扑排序后的并行执行组。同一 wave 内的节点互不依赖，可以并行执行。

```
Wave 0: ["research", "data"]           # 无上游依赖，先执行
Wave 1: ["marketing", "image", "website"]  # 依赖 wave 0 的输出
```

### 3.5 Context / Handoff Payload

上游节点执行完成后，其输出自动成为下游节点的 context。

```
Context = {
    "handoff_from_research": { ... research 的 structured_output ... },
    "handoff_from_data": { ... data 的 structured_output ... },
}
```

### 3.6 Execution Result

每个节点的执行结果。

```
ExecutionResult = {
    node_id: "marketing",
    ok: true,
    summary: "...",
    structured_output: { ... },
    duration_ms: 1234,
    used_handoff: true,
    handoff_sources: ["research", "data"],
}
```

---

## 四、最小数据结构草案

### 4.1 Python Dataclass（纯函数，不依赖 Pydantic）

```python
@dataclass
class CollaborationNode:
    id: str                              # 唯一标识
    agent_id: str                        # 实际 agent_id
    label: str = ""                      # 显示名称
    config: dict = field(default_factory=dict)  # 节点配置

@dataclass
class CollaborationEdge:
    from_node: str                       # 上游节点 ID
    to_node: str                         # 下游节点 ID
    label: str = ""                      # 边描述

@dataclass
class CollaborationGraph:
    nodes: list[CollaborationNode]       # 所有节点
    edges: list[CollaborationEdge]       # 所有边
```

### 4.2 验证结果

```python
@dataclass
class GraphValidationResult:
    valid: bool
    errors: list[str]                    # 验证错误列表
    warnings: list[str]                  # 警告列表
```

---

## 五、执行流程草案

### 5.1 validate_graph(graph)

校验图的合法性：

1. **节点 ID 唯一性** — 不允许重复 ID
2. **边引用合法性** — edge.from_node / to_node 必须存在于 nodes 中
3. **自环检测** — from_node != to_node
4. **循环依赖检测** — DFS 检测环路
5. **孤立节点警告** — 没有任何边连接的节点（warning，不 block）

### 5.2 topological_waves(graph)

Kahn's algorithm 变体，输出 wave 划分：

1. 计算每个节点的入度（in-degree）
2. 入度为 0 的节点归入 wave 0
3. 移除 wave 0 的出边，重新计算入度
4. 入度为 0 的节点归入 wave 1
5. 重复直到所有节点都被分配
6. 如果还有节点未分配 → 存在循环，报错

### 5.3 execute_wave(wave, context, executor)

（本轮只做接口定义，不实现）

```
for node in wave.nodes:
    result = executor(node.agent_id, task_with_context)
    context[node.id] = result.structured_output
```

### 5.4 build_handoff_context(node, results_map, edges)

从上游节点的输出中构建 handoff context：

1. 找到所有 `edge.to_node == node.id` 的边
2. 取 `edge.from_node` 对应的执行结果
3. 合并为 `handoff_context` dict

### 5.5 完整执行流程

```
1. validate_graph(graph) → 校验通过
2. topological_waves(graph) → [wave0, wave1, wave2, ...]
3. results_map = {}
4. for wave in waves:
5.     handoff_ctx = build_handoff_context_for_wave(wave, results_map, edges)
6.     wave_results = parallel_execute(wave.nodes, handoff_ctx)
7.     results_map.update(wave_results)
8. aggregate_result(results_map)
```

---

## 六、与现有 Boss Lite 的兼容策略

### 6.1 Boss Lite Graph 表达

当前 Boss Lite 的硬编码可以表达为：

```
Nodes: [research, data, marketing, image, website]

Edges:
  research → marketing
  research → image
  research → website
  data → marketing
  data → image
  data → website
```

topological_waves 输出：
```
Wave 0: ["research", "data"]
Wave 1: ["marketing", "image", "website"]
```

### 6.2 渐进迁移路径

| 阶段 | 做什么 | 改动范围 |
|------|--------|---------|
| **本轮** | 新建 collaboration_graph.py，纯函数骨架 | 无路由改动 |
| 下一步 | 用 Graph 重构 `_classify_waves` | boss_router.py 内部 |
| 再下一步 | 用 Graph 驱动整个 Boss Lite 执行 | boss_router.py |
| 远期 | 用户自定义 DAG | 前端 + API |

---

## 七、本轮不做（明确排除）

| 不做 | 原因 |
|------|------|
| 可视化编辑器 | 需要前端 DAG 编辑器，复杂度高 |
| 用户自定义任意 DAG | 需要 API + 存储 + 验证 |
| 循环图 | 执行语义复杂，暂不需要 |
| 跨任务长期记忆 | 需要全局状态管理 |
| 多用户权限 | 需要认证系统 |
| 替换现有 Boss Lite | 本轮只打地基 |
| 接入 collaboration_executor | 两套执行模型并存，后续统一 |

---

## 八、MVP 范围

### 8.1 新建文件

- `backend/services/collaboration_graph.py` — 纯函数/轻量类
- `docs/phase3_collaboration_graph_design.md` — 本文档

### 8.2 核心功能

| 功能 | 说明 |
|------|------|
| `CollaborationNode` | 节点 dataclass |
| `CollaborationEdge` | 边 dataclass |
| `CollaborationGraph` | 图 dataclass |
| `validate_graph(graph)` | 校验图合法性 |
| `topological_waves(graph)` | 拓扑排序 → wave 划分 |
| Boss Lite 图构造函数 | `build_boss_lite_graph()` 方便测试 |

### 8.3 不改的文件

- ❌ `boss_router.py`
- ❌ `collaboration_executor.py`
- ❌ `collaboration_planner.py`
- ❌ 前端代码
- ❌ 任何路由/API

---

## 九、验证方式

```bash
# 1. 后端导入验证
python -c "import backend.app; print('ok')"

# 2. Collaboration Graph 自检
python -c "
from backend.services.collaboration_graph import (
    CollaborationNode, CollaborationEdge, CollaborationGraph,
    validate_graph, topological_waves, build_boss_lite_graph,
)
graph = build_boss_lite_graph()
result = validate_graph(graph)
print('valid:', result.valid)
waves = topological_waves(graph)
print('waves:', waves)
"

# 3. 前端构建
cd frontend-new && npm run build
```

---

*由 AI Company OS Phase 3 P0 生成 · 2026-07-07*
