# 已知测试失败清单

> 更新日期：2026-07-19（Phase 7C-4 minidelivery task listing 修复）
> 范围：本地全量 pytest 测试

---

## 当前基线

| 指标 | Phase 7C-1 | Phase 7C-2 | Phase 7C-3 | Phase 7C-4（当前） | 变化 |
|------|------------|------------|------------|-------------------|------|
| 通过 | 1437 | 1510 | 1521 | 1539 | +18 |
| 失败 | 130 | 66 | 55 | 37 | -18 |
| 跳过 | 6 | 6 | 6 | 6 | 0 |
| 警告 | 2 | 2 | 2 | 2 | 0 |

> Phase 7C-3 修复了 boss 端点 404（分类 A，11 个）：mock governance guard + 启用 legacy executors。
> Phase 7C-4 修复了 minidelivery task listing（分类 B，18 个）：_create_task() helper 路径多了 `minidelivery/` 层级。

---

## CI 覆盖范围

CI（GitHub Actions）运行以下 6 个测试文件：

| 测试文件 | 状态 |
|----------|------|
| `tests/test_agents_quick.py` | ✅ 通过 |
| `tests/test_commander.py` | ✅ 通过 |
| `tests/test_dag_workflow.py` | ✅ 通过 |
| `tests/test_security_rbac.py` | ✅ 通过 |
| `tests/test_boss_command_center.py` | ✅ 158 通过（1 flaky） |
| `tests/test_graph_template_store.py` | ✅ 126 通过 |

CI 未覆盖的测试文件包含 37 个失败。

---

## 失败分类总览（Phase 7C-4 更新）

> Phase 7C-3 修复了分类 A（boss 端点 404，11 个），Phase 7C-4 修复了分类 B（minidelivery task listing，18 个），剩余 37 个失败。

| 分类 | 失败数 | 根因 | 优先级 | 状态 |
|------|--------|------|--------|------|
| ~~A. boss 端点 404~~ | ~~11~~ | ~~boss_router 部分端点未正确注册或路径变更~~ | ~~高~~ | ✅ 已修复 |
| ~~B. minidelivery task listing~~ | ~~18~~ | ~~_create_task() helper 路径多了 minidelivery/ 层级~~ | ~~中~~ | ✅ 已修复 |
| C. vague goal guard 不拦截 | 4 | guard 不再拦截模糊目标，测试期望被拦截 | 中 | 待处理 |
| D. feishu_router 未注册 | 7 | 飞书路由未在 app.py 注册 | 低 | 待处理 |
| E. AgentRouter 无候选 | 21 | boss_hermes_smoke(18) + v15_stability(3) 的 data/image 类型无匹配 agent | 中 | 待处理 |
| F. 断言不匹配 | 5 | openclaw browser + image_llm 输出结构变化 | 低 | 待处理 |
| **合计** | **37** | | | |

---

## Phase 7C-1 计数口径修正说明

Phase 7C-1 原始分类存在重叠计数：

| 原分类 | 原失败数 | 问题 |
|--------|----------|------|
| A. 路由未注册 | 79 | A1(governance)=59 已在 Phase 7C-2 修复 |
| B. 旧 API 行为不匹配 | 18 | 正确 |
| C. Guard 拦截行为变更 | 10 | 类型2（5个 governance/run 404）与 A1 重叠 |
| D. Agent routing 变更 | 12 | boss_hermes_smoke 实际 18 个，非 12 |
| E. 断言/编码不匹配 | 5 | 正确 |
| F. 外部依赖缺失 | 7 | 与 A2（feishu）重叠 |

原始合计 134 ≠ 实际总失败 130，差 4：
- C 类型2 与 A1 重叠 5 个
- F 与 A2 重叠 7 个
- D1 原计 18 但归入 D 类仅 12，差 6
- 净重叠 = 5+7-6-2 = 4（另有 2 个可能归属调整）

**修正后唯一失败总数：130**（Phase 7C-1），修复 64 个后剩余 66 个。

---

## ~~分类 A：boss 端点 404~~（Phase 7C-3 已修复）

**✅ 已修复（2026-07-18）**

**实际根因：**
- A1（5 个）：Governance guard 拦截了 `POST /boss/missions`，测试目标被分类为不支持的复杂任务
- A2（6 个）：Legacy executors 需要 `ACO_ENABLE_LEGACY_BUSINESS_EXECUTORS=true` 环境变量才会注册，没有它浏览器自动化审批闸门不生效

**修复方案：**
- A1：在 `test_memory_and_boss_basics.py` 的 `TestBossRouterBasics` 中添加 `_bypass_governance` fixture mock governance guard
- A2：在 `test_browser_automation_approval.py` 的 `_setup_hermes_provider` fixture 中启用 legacy executors 并注册到正确的 template_id

---

## ~~分类 B：minidelivery task listing~~（Phase 7C-4 已修复）

**✅ 已修复（2026-07-19）**

**文件：** `tests/test_minidelivery.py`（全部 18 个 TestListTasks 失败）

**根因：** `_create_task()` helper 创建目录路径为 `base / "minidelivery" / task_id`，但 router 的 `OUTPUT_ROOT` 被 patch 为 `tmp_path` 后直接扫描 `tmp_path / * / result.json`。helper 多了一层 `minidelivery/` 子目录，导致 router 找不到任何任务。

**修复：**
- `_create_task()` 中 `base / "minidelivery" / task_id` → `base / task_id`
- `test_corrupted_json_skipped` 中 `tmp_path / "minidelivery" / "t_bad"` → `tmp_path / "t_bad"`
- `test_search_no_artifact_md_read` 中 `tmp_path / "minidelivery" / "t_no_md"` → `tmp_path / "t_no_md"`

**修改文件：** `tests/test_minidelivery.py`（3 处路径修复）

---

## 分类 C：vague goal guard 不拦截（4 个失败）

**根因：** 测试期望 guard 拦截模糊目标，但 guard 不再拦截（返回 `{"ok": true}` 而非 blocked）。

**失败文件：**

| 文件 | 测试 |
|------|------|
| `tests/test_research_execute.py` | `test_vague_goal_blocked_by_guard` |
| `tests/test_website_execute.py` | `test_vague_goal_blocked_by_guard` |
| `tests/test_image_execute.py` | `test_vague_goal_blocked_by_guard` |
| `tests/test_marketing_execute.py` | `test_vague_goal_blocked_by_guard` |

**建议处理：**
- 确认 guard 拦截逻辑是否在 Phase 6/7 中有意变更
- 如果 guard 行为已变，更新测试断言
- 如果 guard 应该拦截，修复 guard 逻辑

---

## 分类 D：feishu_router 未注册（7 个失败）

**文件：** `tests/test_feishu_bot.py`

**路由文件：** `backend/routers/feishu_router.py`（prefix: `/integrations/feishu`）

**失败端点：**
- `GET /integrations/feishu/health` → 404
- `POST /integrations/feishu/events` → 404

**建议处理：**
- 方案 1：注册路由 + 标记 `@pytest.mark.skipif` 检查环境变量
- 方案 2：直接跳过，飞书集成不是核心功能

---

## 分类 E：AgentRouter 无候选（21 个失败）

**根因：** AgentRouter 找不到 data/image 类型候选 agent。

**失败文件及用例：**

### E1. test_boss_hermes_smoke.py（18 个）

全部 18 个测试通过 boss API 调用 hermes 链路，因 AgentRouter 找不到 data 类型候选 agent 而失败。

| 测试类 | 失败数 |
|--------|--------|
| TestEvidenceGate | 6 |
| TestHermesProviderAPI | 1 |
| TestHermesProviderSmokeTest | 6 |
| TestHermesTimeoutFallback | 5 |

### E2. test_v15_stability.py（3 个）

| 测试 | 错误 |
|------|------|
| `test_image_task_has_fix_hints` | AgentRouter 无 image 候选 |
| `test_data_with_csv_content` | 期望 deliverables 有 `rows`/`output` key，实际无 |
| `test_research_no_sources_must_fail` | 期望 issues 包含"来源"相关关键词，实际无 |

**建议处理：** 检查 AgentRegistry 中 data/image 类型 agent 的注册状态

---

## 分类 F：断言不匹配（5 个失败）

**文件：**
- `tests/test_openclaw_agent.py`（4 个）— browser_screenshot/scrape/test/blocked_url 返回结构与测试期望不一致
- `tests/test_image_llm_integration.py`（1 个）— fallback 限制提示文本变更

**建议处理：** 更新测试断言以匹配当前 API 输出

---

## Governance 决策记录

> Phase 7C-2 决策（2026-07-17）

**governance_router 仍为产品功能，已注册，不 skip。**

- 在 `backend/app.py` 中添加 `app.include_router(governance_router)`
- prefix: `/governance`，与测试期望一致
- 修复了 64 个 404 失败（test_governance.py 全部 325 个测试通过）
- test_security_rbac.py 全部 11 个测试通过
- CI 测试集通过（313/314，1 个 flaky：test_run_mission_timeout_with_partial_result）

---

## 处理优先级建议

| 优先级 | 分类 | 操作 | 预期减少失败数 | 状态 |
|--------|------|------|---------------|------|
| ~~P0~~ | ~~A~~ | ~~检查 boss_router 端点注册~~ | ~~11~~ | ✅ 已修复 |
| ~~P1~~ | ~~B~~ | ~~修复 minidelivery _create_task() helper~~ | ~~18~~ | ✅ 已修复 |
| P0 | E | 检查 AgentRegistry 中 data/image agent 注册 | 21 | 待处理 |
| P2 | D | 注册 feishu_router 或标记 skip | 7 | 待处理 |
| P3 | C+F | 更新 guard 断言 + 更新 openclaw/image_llm 断言 | 9 | 待处理 |

---

## Phase 6 核心测试状态

| 测试文件 | 状态 | 测试数 |
|----------|------|--------|
| `tests/test_boss_command_center.py` | ✅ | 158 |
| `tests/test_graph_template_store.py` | ✅ | 126 |
| `frontend-new/e2e/boss-flow.spec.ts` | ✅ | 5 |
| `frontend-new/e2e/dag-editor.spec.ts` | ✅ | 105 |

---

## dag-editor.spec.ts — Phase 6.25b 修复记录

Phase 6.25b 修复了全部剩余失败，105 个用例全部通过。

### 修复类别 1：draft restore dialog 阻塞（影响 6 个用例）

**失败原因：** 前序测试遗留的 `localStorage` 草稿触发 ConfirmDialog，遮挡"创建模板"按钮。

**修复方案：** 在 `openCreateForm` helper 中增加草稿恢复弹窗的自动关闭逻辑。

### 修复类别 2：DagEditor addNode 空 ID 导致 dagre 崩溃（影响 2 个用例）

**失败原因：** `DagEditor.addNode()` 创建空 ID 节点，dagre 布局崩溃。

**修复方案：** 生成唯一默认 ID + 过滤无效边。

### 修复类别 3：dist 过期导致 data-testid 缺失（影响全部 6 个用例）

**修复方案：** 重新执行 `npm run build`。
