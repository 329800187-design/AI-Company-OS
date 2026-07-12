# Phase 6.10：DAG Canvas 验收文档

> 阶段：Phase 6.10 — 前端图形化 DAG 编辑器
> 创建日期：2026-07-12
> 状态：**已完成**

---

## 一、验收命令

### 1.1 前端构建

```bash
cd frontend-new && npm run build
```

结果：✅ 通过

### 1.2 DAG Canvas E2E 测试

```bash
cd frontend-new && npx playwright test e2e/dag-editor.spec.ts --grep "DAG Canvas"
```

结果：✅ 43 个用例全部通过

---

## 二、E2E 测试覆盖清单（43 个用例）

### 2.1 DAG Canvas 预览（3 个）

| # | 用例 | 说明 |
|---|------|------|
| 1 | 点击预览图能看到画布 | 模板卡片预览按钮 → Canvas 可见 → React Flow 容器渲染 |
| 2 | 节点数量正确渲染 | fixture 模板 2 节点 → `.react-flow__node` 计数为 2 |
| 3 | 空边状态正确显示 | 单节点无边模板 → 显示「无连线」提示 → 仍渲染 1 个节点 |

### 2.2 DAG Canvas 交互（3 个）

| # | 用例 | 说明 |
|---|------|------|
| 4 | 点击节点显示属性面板 | 点击节点 → `dag-detail-panel` 可见 → 显示 id/agent_id/title/入边/出边 |
| 5 | 点击边显示属性面板 | 点击边 → 面板显示 from_node/to_node/handoff_type |
| 6 | MiniMap 和 Controls 可见 | `.react-flow__minimap` 和 `.react-flow__controls` 均可见 |

### 2.3 边点击支持含连字符的节点 ID（1 个）

| # | 用例 | 说明 |
|---|------|------|
| 7 | 含连字符 ID 边点击正确 | `research-agent → marketing-agent` → 面板显示完整 ID |

### 2.4 DAG Canvas 编辑（4 个）

| # | 用例 | 说明 |
|---|------|------|
| 8 | 点击节点可编辑属性并同步到画布 | 编辑 title → 画布节点标签实时更新 |
| 9 | 点击边可编辑 handoff_type | 编辑 → 关闭 → 重新点击 → 值持久 |
| 10 | 删除节点自动清理关联边 | 删除节点 → badge 显示 1 节点 0 边 → 画布 1 个节点 |
| 11 | 删除边 | 面板删除边 → badge 显示 2 节点 0 边 |

### 2.5 agent_id 可编辑（1 个）

| # | 用例 | 说明 |
|---|------|------|
| 12 | 编辑 agent_id 并同步到画布 | `research` → `research-v2` → 画布子标签更新 |

### 2.6 相同标题节点切换（1 个）

| # | 用例 | 说明 |
|---|------|------|
| 13 | 同标题节点编辑后切换正确重置 | 两节点 title 均为「相同标题」→ 编辑 A 后切到 B → 输入框显示 B 的原值 |

### 2.7 键盘快捷键（2 个）

| # | 用例 | 说明 |
|---|------|------|
| 14 | 选中节点后按 Delete 删除 | Delete 键 → 节点和关联边移除 |
| 15 | 输入框聚焦时 Backspace 不触发删除 | 聚焦 title 输入 → Backspace → 节点不删除 |

### 2.8 Undo/Redo integration（4 个）

| # | 用例 | 说明 |
|---|------|------|
| 16 | 编辑 title 后撤销 → Canvas 标题回退 | 填写「新标题ABC」→ 撤销 → 画布不再显示该标题 |
| 17 | 删除节点后撤销 → 节点和边恢复 | 删除 → 撤销 → badge 回到 2 节点 1 边 |
| 18 | 撤销后再重做 → 删除状态恢复 | 删除 → 撤销 → 重做 → 回到 1 节点 0 边 |
| 19 | boss 页面不出现两个可编辑 Canvas | `dag-canvas` locator 计数为 1 |

### 2.9 图形编辑（7 个）

| # | 用例 | 说明 |
|---|------|------|
| 20 | 添加节点后 badge 从 2→3 节点 | Canvas 内「添加节点」按钮 → badge 更新 |
| 21 | 拖拽连线创建边 → 边数 +1 | 添加节点 → 从 source handle 拖到 target → 2 边 |
| 22 | 自环拖拽不新增边 | 从节点拖回自身 → 边数不变 → toast 提示 |
| 23 | 重复边拖拽不新增边 | research→marketing 已存在 → 再拖一次 → 边数不变 |
| 24 | cycle 边拖拽不新增边 | marketing→research → 会形成环 → 边数不变 |
| 25 | 新增节点后撤销/重做正常 | 添加节点 → 撤销 → 2 节点 → 重做 → 3 节点 |
| 26 | 新增边后撤销/重做正常 | 添加节点+连线 → 撤销 → 1 边 → 重做 → 2 边 |

### 2.10 只读预览（2 个）

| # | 用例 | 说明 |
|---|------|------|
| 27 | 只读预览无「添加节点」按钮 | 模板卡片 Canvas 内 `canvas-add-node-btn` 不可见 |
| 28 | 只读预览节点不可连线 | 所有 `.react-flow__handle` style 含 `visibility: hidden` |

### 2.11 节点拖拽（6 个）

| # | 用例 | 说明 |
|---|------|------|
| 29 | 拖拽节点后位置改变 | 拖拽 150px → 坐标变化 > 20px |
| 30 | 自动布局后节点回到 dagre 位置 | 拖拽 → 自动布局 → 位置接近原始 dagre 坐标（<30px） |
| 31 | 拖拽后 badge 不变 | 拖拽 → 2 节点 1 边 badge 不变 |
| 32 | 拖拽不产生 undo 历史 | 拖拽后 undo 按钮仍 disabled |
| 33 | 只读预览节点不可拖拽 | `draggable` 属性不为 `true` |
| 34 | 拖拽后点击仍显示属性面板 | 拖拽 → 点击 → 面板可见且 title 正确 |

### 2.12 节点定位（3 个）

| # | 用例 | 说明 |
|---|------|------|
| 35 | 选择节点后详情面板显示属性 | 下拉选 marketing → 面板 title 为「营销文案」 |
| 36 | 选择节点后 selected 样式 | 选中节点有 `.ring-2` 样式 |
| 37 | 只读预览不显示定位控件 | `canvas-locate-node-select` 计数为 0 |

### 2.13 小屏体验（2 个）

| # | 用例 | 说明 |
|---|------|------|
| 38 | 480px 下工具栏不遮挡第一个节点 | toolbar 和节点重叠 < 30px |
| 39 | 480px 下详情面板输入框无溢出 | panel + input 边界不超出 canvas 右边 |

### 2.14 布局持久化（4 个）

| # | 用例 | 说明 |
|---|------|------|
| 40 | 拖拽后关闭重开位置恢复 | 拖拽 → 取消 → 重开 → 节点在拖拽位置（<120px） |
| 41 | 自动布局后重开不再恢复旧位置 | 拖拽 → 自动布局 → 取消 → 重开 → 在 dagre 位置 |
| 42 | 新增节点后旧节点位置保留 | 拖拽 → 关闭重开 → 添加节点 → 旧节点位置不变 |
| 43 | 布局保存不产生 undo 历史 | 拖拽 → undo 按钮仍 disabled → localStorage 有保存数据 |

---

## 三、校验规则总结

| 规则 | 前端（Canvas onConnect） | 后端（validate_graph） |
|------|--------------------------|------------------------|
| Self-loop | ✅ 实时拦截 + toast | ✅ HTTP 400 |
| Duplicate edge | ✅ 实时拦截 + toast | ✅ HTTP 400 |
| Cycle detection | ✅ 实时拦截 + toast | ✅ HTTP 400 |
| 节点 ID 唯一 | 自动保证（生成唯一 ID） | ✅ HTTP 400 |
| 边引用合法性 | Canvas 内只连接已有节点 | ✅ HTTP 400 |

---

## 四、数据流说明

```
用户操作 Canvas
    ↓
DagCanvas onNodesChange / onEdgesChange / onConnect
    ↓
DagEditor dispatch (draft 状态更新)
    ↓
Undo/Redo history stack
    ↓
Canvas re-render (React Flow)
    ↓ (提交时)
draft → POST/PUT /boss/graph/templates (无 position 字段)
```

布局数据流（独立于模板数据）：

```
用户拖拽节点
    ↓
React Flow onNodeDragStop
    ↓
localStorage.setItem(`dag_layout_${draft.name}_${hash(sorted_node_ids)}`, nodeIdToPositionMap)
    ↓ (重新打开时)
DagCanvas useEffect → 从 localStorage 读取 → 应用到 React Flow nodes
```

---

## 五、已知边界与后续计划

| 边界 | 当前状态 | 后续计划 |
|------|----------|----------|
| **布局仅 localStorage** | 节点拖拽位置存入浏览器 localStorage，不同设备/浏览器不共享 | P2：保存布局到后端模板 API |
| **无批量选择** | Canvas 内只能单击选中单个节点/边 | P2：框选多个节点批量移动/删除 |
| **无节点模板库** | 添加节点使用默认空配置 | P2：预置常用 Agent 节点配置，拖入画布即创建 |
| **positions 不入模板 payload** | 提交模板时 nodes 无 position 字段，后端不存储布局 | 设计决策：布局与模板数据解耦，保持 API 简洁 |
| **只读预览属性面板可查看** | Readonly Canvas 点击节点/边仍显示属性面板（但不可编辑） | 可选优化：隐藏只读模式的属性面板 |

---

*Phase 6.10 DAG Canvas 验收文档 · 2026-07-12*
