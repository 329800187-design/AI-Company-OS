# 第三阶段 P0：Collaboration Graph 设计文档

> 阶段：Phase 3 — P0 Agent 协作通用化
> 创建日期：2026-07-07
> 最后更新：2026-07-10
> 状态：**Graph Template Audit Log + Pin/Unpin 已完成（Phase 6.8）**

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
| Phase 3.4 | 用户自定义 DAG API 最小版 | `POST /boss/graph/execute` | ✅ 已完成 |
| Phase 3.5 | 前端 DAG 可视化最小版 | Boss 页面 GraphPreview | ✅ 已完成 |
| Phase 3.6 | 自定义图模板持久化 | Graph Template Store + API | ✅ 已完成 |
| Phase 3.7 | Graph Template 前端 UI | 模板列表 / 使用目标 / 按模板执行 / 删除 | ✅ 已完成 |
| Phase 3.8 | Graph Template 创建 UI | 创建模板表单 / 节点边编辑 / 前端校验 / 保存 | ✅ 已完成 |
| Phase 3.9 | Graph Template 克隆 UI | 克隆按钮 / 创建表单复用 / name 追加副本 | ✅ 已完成 |
| Phase 3.10 | Graph Template 更新 | PUT API / 前端编辑模式 / 保留 created_at | ✅ 已完成 |
| 远期 | 前端 DAG 编辑器 | 前端 | 待定 |
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
- ✅ `boss_router.py` — 新增 `POST /boss/graph/execute` 自定义 DAG 执行端点
- ✅ `tests/test_boss_lite_graph.py` — 新增 Boss Lite Graph 集成测试
- ✅ `tests/test_boss_graph_execute.py` — 新增自定义 Graph API 测试
- ✅ `frontend-new/src/pages/boss/index.tsx` — 新增协作图只读可视化卡片
- ✅ `backend/services/graph_template_store.py` — Graph Template 持久化服务
- ✅ `tests/test_graph_template_store.py` — Graph Template 测试（28 个）
- ✅ `frontend-new/src/api/client.ts` — Graph Template 前端 API client
- ✅ `frontend-new/src/pages/boss/index.tsx` — Graph Templates 面板和按模板执行结果展示
- ✅ `frontend-new/src/api/client.ts` — 新增 `createBossGraphTemplate()` 创建模板 API
- ✅ `frontend-new/src/pages/boss/index.tsx` — 新增创建模板表单（节点/边编辑、前端校验、保存）
- ❌ `collaboration_executor.py` — 未改
- ❌ `collaboration_planner.py` — 未改

---

## 九、验证方式

```bash
# 1. 后端导入验证
python -c "import backend.app; print('ok')"

# 2. Collaboration Graph + Boss Lite / Boss Graph / Graph Template 测试
pytest tests/test_collaboration_graph.py tests/test_boss_lite_graph.py tests/test_boss_graph_execute.py tests/test_graph_template_store.py -q

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

## 十二、自定义 DAG API 最小版

### 12.1 新增端点

```http
POST /boss/graph/execute
```

请求方可以直接传入 `nodes` 和 `edges` 定义任意 Agent 协作图。后端会先构造 `CollaborationGraph`，再执行：

```python
validate_graph(graph)
topological_waves(graph)
```

若图存在缺失节点引用、自环或循环依赖，接口返回 HTTP 400，并包含校验错误。

### 12.2 请求核心字段

| 字段 | 说明 |
|------|------|
| `goal` | 总业务目标 |
| `nodes[].id` | 图节点 ID，可与 `agent_id` 不同 |
| `nodes[].agent_id` | 实际执行的 Agent |
| `nodes[].task_type` | 传给 `AgentTask` 的任务类型 |
| `nodes[].title` | 展示标题 |
| `nodes[].prompt` | 节点执行 prompt |
| `edges[].from_node` | 上游节点 |
| `edges[].to_node` | 下游节点 |
| `edges[].handoff_type` | 默认 `context` |
| `save_to_delivery` | 是否保存到 MiniDelivery，默认 `true` |

### 12.3 返回与保存

返回结构包含：
- `execution_mode: "custom_graph"`
- `waves`
- `results[].node_id`
- `results[].used_handoff`
- `results[].handoff_sources`
- `summary.total_duration_ms`
- `structured_output.graph`

当 `save_to_delivery=true` 时，保存为：
- `artifact_type: "boss_graph"`
- `source_page: "boss_graph"`
- `artifact.md`
- `raw_agent_result.json`
- `result.json`

### 12.4 测试覆盖

`tests/test_boss_graph_execute.py` 覆盖：
- 无效图校验：缺失引用、自环、循环依赖、重复 ID
- wave 划分：单节点、两层 DAG、三层链路
- 请求模型默认值：`handoff_type=context`、`save_to_delivery=true`
- API mock 执行：单节点、research → marketing handoff、上游失败不 handoff
- MiniDelivery 保存：验证 `artifact.md`、`raw_agent_result.json`、`result.json` 落盘

---

## 十三、前端 DAG 可视化最小版

Boss 页面已新增「协作图 / Collaboration Graph」只读卡片，用于展示 Agent 协作过程。

### 13.1 支持的数据结构

`normalizeGraphResult(result)` 按优先级兼容：
- `result.graph.nodes / result.graph.edges`
- `result.structured_output.graph`
- `result.waves / result.structured_output.waves`
- `result.results[].handoff_sources` 推断 edges
- `structured_output.handoff_sources + handoff_targets` 推断 edges
- 无图数据时将所有节点归入单个 wave

### 13.2 展示内容

- **Waves**：按波次展示节点 chip，成功/失败/未知使用不同状态色
- **Edges**：展示 `from → to` 依赖关系，推断边显示「推断」
- **节点详情**：展示 `node_id / agent_id / title / ok / duration_ms / handoff_sources / summary`

当前版本只做只读展示，不做拖拽、不做编辑器、不调用 `/boss/graph/execute`。

---

## 十四、自定义图模板持久化（Phase 3.6）

### 14.1 功能说明

用户可将常用自定义 DAG 配置保存为可复用的 Graph Template，后续一键执行。

### 14.2 存储

- 路径：`output/graph_templates/{template_id}.json`
- 格式：JSON，包含 `template_id`、`name`、`description`、`goal_hint`、`nodes`、`edges`、`created_at`、`updated_at`
- 不接入数据库，纯文件系统
- `template_id` 限制为 `tpl_[A-Za-z0-9_-]+`，避免路径型 ID 读写文件。

### 14.3 新增 API

| 端点 | 方法 | 说明 |
|------|------|------|
| `/boss/graph/templates` | POST | 创建模板（校验图合法性） |
| `/boss/graph/templates` | GET | 列出所有模板 |
| `/boss/graph/templates/{template_id}` | GET | 获取单个模板 |
| `/boss/graph/templates/{template_id}` | DELETE | 删除模板 |
| `/boss/graph/templates/{template_id}/execute` | POST | 按模板执行 DAG |

### 14.4 DAG 校验

创建模板时使用 `validate_graph()` 校验：
- 节点 ID 唯一性
- 边引用合法性
- 自环检测
- 循环依赖检测

无效图返回 HTTP 400。

### 14.5 按模板执行

`POST /boss/graph/templates/{template_id}/execute` 读取模板配置，构造 `BossGraphExecuteRequest`，复用 `boss_graph_execute` 逻辑执行。

### 14.6 测试覆盖

`tests/test_graph_template_store.py` 覆盖 21 个场景：
- 存储层：保存/读取/列出/删除/落盘/空列表/不存在/自定义 ID/无边/非法 ID 拒绝
- API 层：创建成功/无效图 400/自环 400/列出/获取/获取 404/删除/删除 404/按模板执行/执行 404

---

## 十五、Graph Template 前端 UI（Phase 3.7）

Boss 页面已新增 Graph Templates 面板，复用后端模板 API：

| 前端方法 | 后端端点 |
|----------|----------|
| `listBossGraphTemplates()` | `GET /boss/graph/templates` |
| `getBossGraphTemplate(id)` | `GET /boss/graph/templates/{id}` |
| `deleteBossGraphTemplate(id)` | `DELETE /boss/graph/templates/{id}` |
| `executeBossGraphTemplate(id, payload)` | `POST /boss/graph/templates/{id}/execute` |

面板能力：
- 展示模板名称、描述、目标提示、模板 ID、节点数、边数、创建时间
- 「使用目标」将 `goal_hint` 填入 Boss Lite 输入框
- 「按模板执行」优先使用当前输入目标，否则使用模板 `goal_hint`
- 执行结果复用 `GraphPreviewCard` 展示 waves、edges、节点状态和 handoff 来源
- 删除模板后自动从本地列表移除

---

## 十六、Phase 3.8：Graph Template 创建 UI

Boss 页面 Graph Templates 面板新增「创建模板」按钮和表单：

### 16.1 表单字段

- 基础：name（必填）、description、goal_hint
- 节点列表：每行 id / agent_id / task_type / title / prompt，支持添加/删除
- 边列表：每行 from_node / to_node / handoff_type，支持添加/删除

### 16.2 前端校验规则

提交前校验：
- name 非空且 ≥ 2 字符
- nodes 至少 1 个
- node.id / node.agent_id 非空
- node id 不重复
- edge.from_node / edge.to_node 非空
- edge 不能自环
- edge 引用的节点必须存在

### 16.3 默认草稿

点击「创建模板」时默认填入两节点模板（research → marketing），方便用户直接修改。

### 16.4 新增 API 方法

`createBossGraphTemplate(payload)` → `POST /boss/graph/templates`

### 16.5 保存流程

1. 前端校验 → 2. 调用 API → 3. 成功后收起表单、刷新列表 → 4. 失败显示错误

---

## 十七、仍未完成

| 项目 | 说明 |
|------|------|
| 前端 DAG 编辑器 | 从只读 GraphPreview 升级为可配置 nodes/edges |
| ~~模板更新~~ | ✅ 已完成 — Phase 3.10 |
| 跨 Mission 协作 | 不同 Mission 之间的 Agent 输出复用 |
| CollaborationPlan 统一 | 将 CollaborationGraph 与现有 CollaborationPlan 合并 |
| 多用户权限 | 模板隔离、权限控制 |
| 版本历史 | 模板版本管理 |

---

## 十八、模板克隆 UI（Phase 3.9）

### 18.1 概述

Phase 3.9 实现了「克隆模板」功能：用户点击已有模板的「克隆」按钮后，创建表单自动展开并填入该模板的全部内容，name 自动追加「副本」后缀。用户修改后点击「保存模板」即可生成新模板。

### 18.2 实现方式

- **纯前端实现**，无需新增后端 API
- 克隆 = 将已有模板数据填入 `createDraft` → 展开创建表单 → 用户保存时调用现有 `POST /boss/graph/templates`
- 不保留原 `template_id`，保存时由后端生成新 ID
- nodes / edges 做浅拷贝，避免引用污染

### 18.3 交互流程

1. 用户在模板卡片点击「克隆」
2. 创建表单展开，name 变为 `${原名称} 副本`
3. description、goal_hint、nodes、edges 原样填入
4. 用户可自由修改
5. 点击「保存模板」→ 调用 `createBossGraphTemplate()` → 刷新列表
6. 原模板不受影响

### 18.4 模板更新（Phase 3.10）

模板更新已实现，详见第十九节。

---

## 十九、模板更新（Phase 3.10）

### 19.1 概述

Phase 3.10 实现了 Graph Template 更新功能：用户点击已有模板的「编辑」按钮后，创建表单自动展开并填入该模板的全部内容，进入编辑模式。保存时调用 `PUT /boss/graph/templates/{template_id}` 更新已有模板，而不是创建新模板。

### 19.2 后端

- 新增 `update_template(template_id, name, nodes, edges, description, goal_hint)` 到 `graph_template_store.py`
- 保留原 `created_at`，`updated_at` 用当前时间
- template_id 不合法或不存在返回 None
- 新增 `PUT /boss/graph/templates/{template_id}` 端点到 `boss_router.py`
- 请求结构复用 `BossGraphTemplateCreateRequest`
- 不存在返回 404，无效图返回 400

### 19.3 前端

- 新增 `updateBossGraphTemplate(templateId, payload)` 到 `client.ts`
- Boss 页面新增 `editingTemplateId` 状态
- 每个模板卡片新增「编辑」按钮
- 点击「编辑」→ 填入创建表单 → 进入编辑模式
- 表单标题变为「编辑 Graph Template」，保存按钮变为「更新模板」
- 保存时根据 `editingTemplateId` 决定调用 create 还是 update
- 克隆时必须清空 `editingTemplateId`，确保克隆保存为新模板
- 取消时清空 `editingTemplateId`

### 19.4 交互流程

1. 用户在模板卡片点击「编辑」
2. 创建表单展开，name、description、goal_hint、nodes、edges 原样填入
3. 表单标题变为「编辑 Graph Template」，保存按钮变为「更新模板」
4. 用户可自由修改
5. 点击「更新模板」→ 调用 `updateBossGraphTemplate()` → 刷新列表
6. 原模板被更新，`created_at` 不变，`updated_at` 更新

### 19.5 测试覆盖

- update_template 成功
- update_template 保留 created_at，更新 updated_at
- update_template 不存在返回 None
- update_template 非法 template_id 返回 None
- PUT API 成功
- PUT API 不存在返回 404
- PUT API 无效图返回 400

---

## 二十、Graph Template Audit Log（Phase 6.8）

### 20.1 概述

Phase 6.8 实现了 Graph Template 审计日志系统，记录模板全生命周期操作事件，支持事后追溯。

### 20.2 审计事件类型

| 事件类型 | 触发时机 | 说明 |
|----------|----------|------|
| `create` | 创建模板 | 记录模板名称、节点数、边数 |
| `clone` | 克隆模板 | 记录源模板 ID、源模板名称 |
| `update` | 更新模板 | 记录变更摘要 |
| `delete` | 删除模板 | 记录模板名称、节点数、边数、删除时间 |
| `execute` | 按模板执行 | 记录执行目标 |
| `restore` | 回滚版本 | 记录目标版本 ID |
| `metadata_update` | 更新版本标签/备注 | 记录变更字段 |
| `pin` | 固定版本 | 记录版本 ID |
| `unpin` | 取消固定版本 | 记录版本 ID |

### 20.3 存储

- 路径：`output/graph_template_audit/{template_id}.jsonl`
- 格式：JSONL，每行一个事件，包含 `event_id`（`aevt_{uuid}`）、`timestamp`（UTC ISO）、`template_id`、`event_type`、`summary`、`details`
- 写入策略：JSONL 追加写入，每次写入后 `flush` + `fsync`，保证单条事件尽快落盘
- 删除模板后审计日志**保留**，用于事后追溯

### 20.4 安全特性

- **敏感字段过滤**：自动移除 `api_key`、`token`、`secret`、`password`、`authorization` 等字段
- **长文本截断**：超过 200 字符的字符串自动截断并追加 `...`
- **列表长度限制**：列表类型最多保留 10 个元素

### 20.5 API 端点

| 端点 | 方法 | 说明 |
|------|------|------|
| `/boss/graph/templates/{template_id}/audit` | GET | 查询审计日志，支持 `event_type` 过滤和 `limit` 参数 |
| `/boss/graph/templates/{template_id}/versions/{version_id}/pin` | POST | 固定版本 |
| `/boss/graph/templates/{template_id}/versions/{version_id}/unpin` | POST | 取消固定版本 |

### 20.6 删除后查询

模板删除后，审计 API 仍可查询：

- 有审计记录：返回 `deleted: true` + 事件列表
- 无审计记录且模板不存在：返回 404

### 20.7 版本 Pin/Unpin

- 固定版本不会被自动裁剪（`_MAX_VERSIONS_PER_TEMPLATE = 20` 限制只对未固定版本生效）
- 固定版本在 UI 显示琥珀色「固定」徽章
- Pin/Unpin 操作本身也会记录审计事件

### 20.8 前端 UI

- **审计面板**：每个模板卡片新增「审计」按钮，点击打开审计日志面板
- **事件筛选**：下拉框支持按事件类型过滤（全部 + 9 种类型）
- **事件颜色**：`create`=绿、`clone`=翠绿、`update`=蓝、`delete`=红、`execute`=紫、`restore`=琥珀、`metadata_update`=青、`pin`=黄、`unpin`=灰
- **Pin UI**：版本列表每行显示固定/取消固定按钮，固定版本显示「固定」徽章

### 20.9 测试覆盖

`tests/test_graph_template_store.py` 覆盖 28 个场景：
- 存储层（10 个）：保存/读取/列出/删除/落盘/空列表/不存在/自定义 ID/无边/非法 ID 拒绝
- API 层（18 个）：创建/无效图/自环/列出/获取/获取 404/删除/删除 404/按模板执行/执行 404 + 审计相关：创建审计/更新审计/事件过滤/无效类型 400/不存在 404/无敏感信息/克隆审计/克隆来源/无来源创建审计/版本 pin/版本 unpin/不存在版本 pin 404/固定版本存活裁剪/回滚审计/元数据更新审计/pin 审计/删除后审计保留/删除事件详情/无文件 404

---

*由 AI Company OS Phase 3 P0 生成 · 2026-07-08 · 最后更新：Phase 6.8 Audit Log + Pin/Unpin*
