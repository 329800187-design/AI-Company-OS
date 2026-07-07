# 第三阶段 P0：Collaboration Graph 设计文档

> 阶段：Phase 3 — P0 Agent 协作通用化
> 创建日期：2026-07-07
> 最后更新：2026-07-07
> 状态：**Boss Lite 已接入 CollaborationGraph · 真实 API 验收通过**

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
| `boss_router.py` Boss Lite | 硬编码两波 handoff → **已改为 Graph 驱动** | ✅ 已重构 |
| `collaboration_graph.py` | 通用 DAG → wave 划分 | ✅ 已完成 |

**实际策略：** `collaboration_graph.py` 作为独立模块提供 DAG 数据结构和拓扑排序，`boss_router.py` 的 Boss Lite 执行路径已从硬编码 wave 改为 `build_boss_lite_graph(agents) → topological_waves(graph) → 按 DAG wave 执行`。

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

| 阶段 | 做什么 | 改动范围 | 状态 |
|------|--------|---------|------|
| Phase 3.1 | 新建 collaboration_graph.py，纯函数骨架 | 无路由改动 | ✅ 已完成 |
| Phase 3.2 | 用 Graph 重构 Boss Lite 执行路径 | boss_router.py | ✅ 已完成 |
| Phase 3.3 | 真实 API 端到端验收（5 场景） | 测试 + 文档 | ✅ 已完成 |
| 下一步 | 用户自定义 DAG API | 前端 + API | 待定 |
| 远期 | 前端 DAG 可视化编辑器 | 前端 | 待定 |
| 远期 | 跨 Mission 协作 | 架构 | 待定 |

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

### 8.3 已改动的文件

- ✅ `boss_router.py` — Boss Lite 执行路径改为 Graph 驱动
- ✅ `tests/test_boss_lite_graph.py` — 新增 Boss Lite Graph 集成测试
- ❌ `collaboration_executor.py` — 未改
- ❌ `collaboration_planner.py` — 未改
- ❌ 前端代码 — 未改

---

## 九、验证方式

```bash
# 1. 后端导入验证
python -c "import backend.app; print('ok')"

# 2. Collaboration Graph + Boss Lite Graph 测试
pytest tests/test_collaboration_graph.py tests/test_boss_lite_graph.py -q

# 3. 前端构建
cd frontend-new && npm run build
```

---

## 十、Boss Lite 已接入 CollaborationGraph

### 10.1 改动说明

`backend/routers/boss_router.py` 的 Boss Lite 执行路径已从硬编码 wave 改为 Graph 驱动：

**改动前（硬编码）：**
```python
_WAVE1_AGENTS = {"research", "data"}
_WAVE2_AGENTS = {"marketing", "image", "website"}
HANDOFF_SOURCES = {"marketing": ["research", "data"], ...}
```

**改动后（Graph 驱动）：**
```python
graph = build_boss_lite_graph(agents=selected_agents)
waves = topological_waves(graph)
# 按 wave 顺序执行，handoff_sources 从图上游依赖动态计算
```

### 10.2 当前默认 DAG

```
research ──→ marketing
research ──→ image
research ──→ website
data     ──→ marketing
data     ──→ image
data     ──→ website
```

拓扑排序结果：
- Wave 0: `research`, `data`（无上游依赖，并行执行）
- Wave 1: `marketing`, `image`, `website`（依赖 wave 0 输出）

### 10.3 Partial Agents 自动裁剪

当用户指定部分 agents 时，图自动裁剪：

| agents 参数 | 实际图 | waves |
|-------------|--------|-------|
| `None`（默认 5 个） | 完整图 | `[research, data] → [marketing, image, website]` |
| `["research", "marketing"]` | 裁剪子图 | `[research] → [marketing]` |
| `["data", "website"]` | 裁剪子图 | `[data] → [website]` |
| `["marketing"]` | 单节点 | `[marketing]` |
| `["research", "data"]` | 两独立节点 | `[research, data]` |

### 10.4 handoff_sources 动态计算

handoff_sources 不再硬编码，而是从图的上游依赖动态计算：

```python
upstream = graph.upstream_of(agent_id)
agent_ho_sources = [s for s in upstream if s in results_map and results_map[s].get("ok")]
```

---

## 十一、真实 API 验收结果（2026-07-07）

### 11.1 验收场景

| 场景 | agents | 请求目标 |
|------|--------|---------|
| A | 默认 5 agent | 为手工银饰新品做一次上线作战计划 |
| B | research + marketing | 调研手工银饰市场并生成营销文案 |
| C | data + website | 基于销售数据生成落地页方案 |
| D | marketing only | 写一段新品上线文案 |
| E | research + data | 做市场调研和数据分析 |

### 11.2 验收结果

| 场景 | ok | execution_mode | handoff_enabled | results 顺序 | handoff_sources | artifact.md |
|------|-----|----------------|-----------------|-------------|-----------------|-------------|
| A | ✅ | two_wave_handoff | true | research→marketing→image→data→website | marketing: [research,data], image: [research,data], website: [research,data] | ✅ 上游洞察传递正确 |
| B | ✅ | two_wave_handoff | true | research→marketing | marketing: [research] | ✅ 无虚假 data 来源 |
| C | ✅ | two_wave_handoff | true | data→website | website: [data] | ✅ 无虚假 research 来源 |
| D | ✅ | parallel | false | marketing | [] | ✅ 显示"未启用上游洞察传递" |
| E | ✅ | parallel | false | research→data | [] | ✅ 显示"未启用上游洞察传递" |

### 11.3 MiniDelivery 验收

| 场景 | delivery_task_id | 搜索 | 详情 | 预览 | 下载 |
|------|-----------------|------|------|------|------|
| A | boss_e93b0b171f6d | ✅ | ✅ | ✅ | HTTP 200 |
| B | boss_67c66e6f483f | ✅ | ✅ | ✅ | HTTP 200 |
| C | boss_9d4306c7533b | ✅ | ✅ | ✅ | HTTP 200 |
| D | boss_5ef57f90ecb8 | ✅ | ✅ | ✅ | HTTP 200 |
| E | boss_15a14c5fe291 | ✅ | ✅ | ✅ | HTTP 200 |

### 11.4 关键验证点

- ✅ handoff_sources 来自图上游依赖（动态计算），不是硬编码
- ✅ partial agents 场景正确裁剪子图，不被错误标记为 two_wave_handoff
- ✅ 单 agent（场景 D）正确标记为 parallel + handoff_enabled=false
- ✅ 两个上游 agents（场景 E）正确标记为 parallel + handoff_enabled=false
- ✅ artifact.md 的「上游洞察传递」章节与真实 sources/targets 一致
- ✅ 场景 B 的 artifact.md 不错误显示 data 作为来源
- ✅ 场景 C 的 artifact.md 不错误显示 research 作为来源

---

## 十二、仍未完成

| 项目 | 说明 |
|------|------|
| 自定义 DAG API | 允许用户通过 API 定义任意 Agent 依赖关系 |
| 前端图可视化 | 在前端展示 DAG 结构和执行状态 |
| 跨 Mission 协作 | 不同 Mission 之间的 Agent 输出复用 |
| CollaborationPlan 统一 | 将 CollaborationGraph 与现有 CollaborationPlan 合并 |

---

*由 AI Company OS Phase 3 P0 生成 · 2026-07-07 · 最后更新：Boss Lite 接入 + 真实 API 验收*
