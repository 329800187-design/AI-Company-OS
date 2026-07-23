# 已知测试失败清单

> 更新日期：2026-07-24（Phase 7C-8 断言基线清理完成）
> 范围：本地全量 pytest 测试

---

## 当前基线

| 指标 | Phase 7C-1 | Phase 7C-2 | Phase 7C-3 | Phase 7C-4 | Phase 7C-5 | Phase 7C-6 | Phase 7C-7 | Phase 7C-8（当前） | 变化 |
|------|------------|------------|------------|------------|------------|------------|------------|-------------------|------|
| 通过 | 1437 | 1510 | 1521 | 1539 | 1559 | 1566 | 1570 | 1577 | +7 |
| 失败 | 130 | 66 | 55 | 37 | 16 | 9 | 5 | 0 | -5 |
| 跳过 | 6 | 6 | 6 | 6 | 6 | 6 | 6 | 6 | 0 |
| 警告 | 2 | 2 | 2 | 2 | 2 | 2 | 2 | 6 | +4 |

> Phase 7C-3 修复了 boss 端点 404（分类 A，11 个）：mock governance guard + 启用 legacy executors。
> Phase 7C-4 修复了 minidelivery task listing（分类 B，18 个）：_create_task() helper 路径多了 `minidelivery/` 层级。
> Phase 7C-5 修复了 AgentRouter 无候选（分类 E，21 个）：模板别名导致 executor 注册键不匹配 + 测试 fixture 启用 legacy executors。
> Phase 7C-6 修复了 feishu_router 未注册（分类 D，7 个）：在 app.py 注册 feishu_router。
> Phase 7C-7 对齐了 vague goal guard 测试语义（4 个），业务 Agent execute 直连执行，治理分类/阻断走 `/governance/run`。
> Phase 7C-8 清理了最后 5 个断言不匹配失败，失败数降为 0。

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

CI 测试集当前通过；全量测试仍有 6 个明确 skip，均为 integration/optional 场景，不计入 failure。

---

## 失败分类总览（Phase 7C-8 更新）

| 分类 | 失败数 | 根因 | 优先级 | 状态 |
|------|--------|------|--------|------|
| ~~A. boss 端点 404~~ | ~~11~~ | ~~boss_router 部分端点未正确注册或路径变更~~ | ~~高~~ | ✅ 已修复 |
| ~~B. minidelivery task listing~~ | ~~18~~ | ~~_create_task() helper 路径多了 minidelivery/ 层级~~ | ~~中~~ | ✅ 已修复 |
| ~~C. vague goal guard 不拦截~~ | ~~4~~ | ~~业务 Agent execute 入口改为直连执行，测试期望过时~~ | ~~中~~ | ✅ 已修复 |
| ~~D. feishu_router 未注册~~ | ~~7~~ | ~~feishu_router 未在 app.py 注册~~ | ~~低~~ | ✅ 已修复 |
| ~~E. AgentRouter 无候选~~ | ~~21~~ | ~~模板别名与 executor 注册键不匹配 + 测试 fixture 未启用 legacy executors~~ | ~~中~~ | ✅ 已修复 |
| ~~F. 断言不匹配~~ | ~~5~~ | ~~OpenClaw 授权输出和 Image Agent fallback 语义已变化，测试断言过时~~ | ~~低~~ | ✅ 已修复 |
| **合计** | **0** | | | |

> Phase 7C-8 完成测试基线清理：本阶段 5 个断言不匹配已全部修复。全量测试中仍有 6 个明确 skip，均为 integration/optional 场景，不计入 failure。

---

## Phase 7C-8 修复记录

**✅ 已修复（2026-07-24）**

**根因与处理：**
- OpenClaw 的浏览器任务现在默认需要显式浏览器授权，测试没有传 `allow_browser_automation=True`，导致返回稳定的 `status="blocked"`；浏览器测试已显式授权，URL 拦截测试改为断言稳定的 `blocked`、`blocked_reason` 和失败状态字段。
- Image Agent fallback 的 limitations 已统一为“模板/规则降级产物，非真实 LLM 生成”；测试改为断言这两个稳定语义片段，而不是依赖历史提示词/中文变体。

**修改文件：**
- `tests/test_openclaw_agent.py`
- `tests/test_image_llm_integration.py`
- `docs/known_test_failures.md`

---

## 历史修复记录

此前 Phase 7C-3 至 Phase 7C-7 的修复记录保留在 git 历史与对应 PR 中：
- Phase 7C-3：boss 端点 404
- Phase 7C-4：minidelivery task listing
- Phase 7C-5：AgentRouter 无候选
- Phase 7C-6：feishu_router 注册
- Phase 7C-7：vague goal guard 测试语义对齐

---

## 计数口径

- `failure` 只指 pytest failed。
- `skip` 是明确的 integration/optional 场景，不计入 failure。
- 警告不计入 failure。
