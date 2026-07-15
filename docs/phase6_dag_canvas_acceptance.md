# Phase 6.10：DAG Canvas 验收文档

> 阶段：Phase 6.10 — 前端图形化 DAG 编辑器 + Phase 6.11 布局后端持久化
> 创建日期：2026-07-12
> 更新日期：2026-07-13
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

结果：✅ 46 个用例全部通过

---

## 二、E2E 测试覆盖清单（46 个用例）

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

### 2.15 布局后端持久化（3 个）

| # | 用例 | 说明 |
|---|------|------|
| 44 | 拖拽后 PATCH 到后端，重新编辑恢复布局 | 拖拽 → PATCH 200 → 关闭 → 重开 → 节点在拖拽位置 |
| 45 | 自动布局清空后端布局，重开使用 dagre | 拖拽 → 自动布局 → PATCH 空对象 → 关闭 → 重开 → dagre 位置 |
| 46 | 只读预览不触发 PATCH | 预览 Canvas → 拖拽不可用 → 无 PATCH 请求 |

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

布局数据流（Phase 6.11 升级为后端持久化）：

```
用户拖拽节点
    ↓
React Flow onNodeDragStop
    ↓
setPositions → localStorage (即时保存)
    ↓
onLayoutChange(layout) 回调
    ↓
800ms 防抖 → PATCH /boss/graph/templates/{id}/layout
    ↓
后端 graph_template_store → canvas_layout 字段写入 JSON
    ↓ (重新打开时)
DagCanvas useEffect → 后端 canvas_layout 优先 → localStorage fallback → dagre 默认
```

---

## 五、已知边界与后续计划

| 边界 | 当前状态 | 后续计划 |
|------|----------|----------|
| **布局已后端持久化** ✅ | Canvas 拖拽布局通过 PATCH API 持久化到模板 JSON | Phase 6.11 已完成 |
| **批量选择** ✅ | 框选/Shift+拖拽多选节点，批量删除、批量拖动，undo/redo 正确恢复 | Phase 6.12 已完成 |
| **无节点模板库** | 添加节点使用默认空配置 | P2：预置常用 Agent 节点配置，拖入画布即创建 |
| **只读预览属性面板可查看** | Readonly Canvas 点击节点/边仍显示属性面板（但不可编辑） | 可选优化：隐藏只读模式的属性面板 |

---

## 六、Phase 6.11：布局后端持久化

### 6.1 验收命令

```bash
# 后端测试（17 个新增）
python -m pytest tests/test_graph_template_store.py -k "canvas_layout" -v

# 全量测试（126 个通过）
python -m pytest tests/test_graph_template_store.py -v

# 前端构建
cd frontend-new && npm run build

# E2E 测试（46 个 Canvas 用例）
cd frontend-new && npx playwright test e2e/dag-editor.spec.ts --grep "DAG Canvas"
```

### 6.2 数据结构

模板 JSON 新增可选字段 `canvas_layout`：

```json
{
  "template_id": "tpl_xxxxxxxxxxxx",
  "name": "...",
  "nodes": [...],
  "edges": [...],
  "canvas_layout": {
    "research": {"x": 100, "y": 200},
    "marketing": {"x": 300, "y": 200}
  }
}
```

- `canvas_layout` 是可选字段，旧模板不存在时自动 fallback
- 布局格式：`{node_id: {x: number, y: number}}`（与 localStorage 格式一致）
- 版本快照不包含 `canvas_layout`（布局是 per-template，非 per-version）

### 6.3 API 端点

| 方法 | 路径 | 说明 |
|------|------|------|
| PATCH | `/boss/graph/templates/{id}/layout` | 专用布局更新（不创建版本快照） |
| POST | `/boss/graph/templates` | 创建时可选传入 `canvas_layout` |
| PUT | `/boss/graph/templates/{id}` | 更新时可选传入 `canvas_layout`，None 保留旧值 |
| GET | `/boss/graph/templates/{id}` | 返回包含 `canvas_layout` |
| GET | `/boss/graph/templates` | 列表返回包含 `canvas_layout` |

### 6.4 前端数据流

```
用户拖拽节点
    ↓
React Flow onNodeDragStop
    ↓
setPositions → localStorage (即时)
    ↓
onLayoutChange(layout) 回调
    ↓
800ms 防抖 → PATCH /boss/graph/templates/{id}/layout
```

读取优先级：

```
编辑模板 → 后端 canvas_layout (最高优先级)
         → localStorage fallback
         → dagre 自动布局 (默认)
```

### 6.5 向后兼容性

| 场景 | 行为 |
|------|------|
| 旧模板无 canvas_layout | 读取时无此字段 → fallback 到 localStorage → dagre |
| 新模板有 canvas_layout | 优先使用后端布局，localStorage 作为即时缓存 |
| 自动布局 | 清除后端布局 + localStorage，后续使用 dagre 默认 |
| 版本回滚 | 不影响 canvas_layout（布局不在版本快照中） |

### 6.6 测试覆盖（17 个新增）

**Store 层（10 个）：**

| # | 用例 | 说明 |
|---|------|------|
| 1 | save_template 保存 canvas_layout | 保存后读回一致 |
| 2 | save_template 不传 canvas_layout | 字段不存在 |
| 3 | update_template 保留 canvas_layout | 不传时保留旧值 |
| 4 | update_template 覆盖 canvas_layout | 传入新值时覆盖 |
| 5 | update_canvas_layout 专用函数 | 仅更新布局字段 |
| 6 | update_canvas_layout 不存在模板 | 返回 None |
| 7 | update_canvas_layout 不创建版本 | 版本列表为空 |
| 8 | 版本快照不含 canvas_layout | 快照中无此字段 |
| 9 | update_canvas_layout 过滤 NaN/Infinity | 非法浮点值被拒绝 |
| 10 | update_canvas_layout 空字典清除布局 | 传空对象后布局为空 |

**API 层（7 个）：**

| # | 用例 | 说明 |
|---|------|------|
| 11 | PATCH /layout 更新成功 | 返回完整模板含布局 |
| 12 | PATCH /layout 不存在返回 404 | 正确报错 |
| 13 | GET 包含 canvas_layout | 单个模板读取正确 |
| 14 | PATCH 不创建版本 | 版本列表为空 |
| 15 | 列表包含 canvas_layout | 列表接口也返回布局 |
| 16 | PATCH 空对象清除布局 | 清除后 canvas_layout 为空 |
| 17 | PATCH null 返回 422 | Pydantic 校验拒绝 null |

---

*Phase 6.10 DAG Canvas 验收文档 + Phase 6.11 布局后端持久化 · 2026-07-13*

---

## 七、Phase 6.12：批量选择

### 7.1 验收命令

```bash
# 前端构建
cd frontend-new && npm run build

# E2E 测试（51 个 Canvas 用例，含 5 个批量选择新增）
cd frontend-new && npx playwright test e2e/dag-editor.spec.ts --grep "DAG Canvas"

# 后端测试（126 个，无变化）
python -m pytest tests/test_graph_template_store.py -v
```

### 7.2 功能说明

在编辑模式的 DAG Canvas 内支持多节点批量操作：

| 能力 | 说明 |
|------|------|
| **框选多选** | 按住 Shift 键在画布上拖拽，拉出选择框批量选中节点 |
| **批量拖动** | 多个节点选中后，拖动其中任意一个，所有选中节点同步移动 |
| **批量删除** | 选中多个节点后，底部出现浮动工具条，点击「批量删除」一次性移除所有选中节点及其关联边 |
| **自动清理边** | 批量删除时自动移除所有与被删节点相关的边 |
| **Undo/Redo** | 批量删除作为单次操作进入撤销历史，撤销恢复所有节点和边，重做再次删除 |
| **只读隔离** | 只读预览模式不显示批量操作工具条，不可框选编辑 |

### 7.3 UI 说明

- **选择方式**：按住 Shift 键 + 在画布上拖拽，拉出蓝色选择框
- **浮动工具条**：选中 ≥2 个节点后，在画布底部中央显示浮动工具条
  - 显示「已选中 N 个节点」
  - 显示「批量删除」按钮（红色，带垃圾桶图标）
- **点击空白处**：取消所有选中状态，工具条消失

### 7.4 E2E 测试覆盖（5 个新增）

| # | 用例 | 说明 |
|---|------|------|
| 1 | 多选两个节点后显示批量操作工具条 | Shift+拖拽框选 → 工具条可见 → 显示「已选中 2 个节点」→ 删除按钮可见 |
| 2 | 批量删除两个节点，相关边消失 | 框选 → 批量删除 → 0 节点 0 边 → 工具条消失 |
| 3 | 批量删除后 undo/redo 恢复正确 | 删除 → 撤销 → 2 节点 1 边恢复 → 重做 → 0 节点 0 边 |
| 4 | 只读预览不显示批量操作工具条 | 只读 Canvas 框选 → 工具条不可见 |
| 5 | 批量拖动后节点位置改变 | 框选 → 拖动 → 节点坐标变化 > 20px |

### 7.5 测试总计

- **DAG Canvas E2E 测试**：51 个用例全部通过（46 个已有 + 5 个新增）
- **后端测试**：126 个全部通过（无变化）
- **前端构建**：✅ 通过

*Phase 6.12 批量选择 · 2026-07-13*
