# Phase 6.13–6.16 Boss 执行闭环审计文档

> 审计日期：2026-07-13
> 范围：Phase 6.13（人工确认执行流）→ Phase 6.16.2（ThreadPoolExecutor timeout 修复）

---

## 1. 状态机（最终版）

```
pending_review ──confirm──> running ──all done──> ready_for_review ──accept──> done
                         │                  │                         │
                         │                  ├──some have results──> partial ──accept──> done
                         │                  │                         │
                         │                  └──timeout/interrupted──> interrupted ──accept──> done
                         │
                         └──all failed, no results──> failed
```

### 状态定义

| 状态 | 含义 | 触发条件 |
|------|------|----------|
| `pending_review` | 计划已生成，等待用户确认执行 | `create_mission()` 后默认状态 |
| `running` | 正在执行中 | `run_mission()` 或 `run_module()` 开始时 |
| `ready_for_review` | 所有模块执行完成，等待用户审核 | 所有 active 模块 status=done |
| `partial` | 部分模块有结果，部分失败或中断 | 有至少一个模块有 result，但非全部 done |
| `interrupted` | 执行中断，无有效结果 | 所有 active 模块为 interrupted 或 failed 且无 result |
| `failed` | 所有模块均无有效结果 | 所有 active 模块 failed 且无 result |
| `done` | 用户已接受结果 | `accept_mission()` 从 ready_for_review/partial/interrupted 转入 |

### 模块状态

| 状态 | 含义 |
|------|------|
| `pending` | 待执行 |
| `running` | 执行中 |
| `done` | 执行成功 |
| `partial` | 有结果但执行有问题（ok=False 但 final_answer >= 10 字符）|
| `failed` | 执行失败，无有效结果 |
| `interrupted` | 执行超时或被中断 |
| `skipped` | 未启用的模块 |

---

## 2. 核心原则

### 2.1 人工确认原则

**从 Phase 6.13 起，Boss 执行流程变为"生成计划 → 人工确认 → 执行 → 人工审核/接受"。**

- `create_mission()` **始终**创建 mission 为 `pending_review` 状态
- `auto_run` 参数被忽略（保留 API 兼容性但不生效）
- 用户必须显式调用 `POST /boss/missions/{id}/run` 才会执行
- 执行完成后，用户必须调用 `POST /boss/missions/{id}/accept` 才会变为 `done`
- 没有自动重试机制——每个模块只执行一次

### 2.2 Timeout 策略

每个模块有独立的硬超时（Phase 6.16）：

| 模块 | 超时（秒） |
|------|-----------|
| strategy | 60 |
| market | 90 |
| marketing | 90 |
| landing | 60 |
| actions | 60 |

超时后：
- 模块状态标记为 `interrupted`
- 保留已有 result（底层线程可能已部分写入）
- 后续模块不再执行（`run_mission` 遇到 interrupted 模块会 break）
- 记录 `module_timeout` 事件

**Phase 6.16.2 修复**：`ThreadPoolExecutor.shutdown(wait=False, cancel_futures=True)` 确保超时后不阻塞请求。

### 2.3 Stale Cleanup 策略

两层清理机制：

**全局清理**（`cleanup_stale_running_missions`）：
- 默认 30 分钟超时阈值
- running 超时 + 有 result → `partial`（保留结果）
- running 超时 + 无 result → `interrupted`
- 写入 warning 提示人工检查
- 不删除数据，不自动重跑

**单任务清理**（`cleanup_mission_stale_modules`）：
- 在 `run_mission` 开始前自动调用（5 分钟阈值）
- 避免重复执行卡死状态的模块

### 2.4 Late Result CAS 保护（Phase 6.16.1）

`_update_module_result()` 新增 `expected_status` 参数：
- 传入 `expected_status="running"` 时，UPDATE 语句加 `WHERE status = 'running'`
- 如果模块状态已被其他路径修改（如 timeout → interrupted），`rowcount == 0`，返回 False
- 晚返回的线程结果不会覆盖已标记的 interrupted/failed 状态
- 记录 `module_result_ignored` 事件用于审计

---

## 3. 代码路径验证

| 路径 | 代码位置 | 验证状态 |
|------|----------|----------|
| create_mission 默认 pending_review | `boss_command_center.py:391` | ✅ SQL 硬编码 `'pending_review'` |
| auto_run 被忽略 | `boss_command_center.py:422-425` | ✅ 注释明确，无 auto_run 逻辑 |
| confirm execute 调 run_mission | `boss_router.py:180-199` | ✅ POST /run 端点 |
| run_mission 只执行一次 | `boss_command_center.py:690-693` | ✅ 跳过 done/skipped，无重试循环 |
| run_module timeout → interrupted | `boss_command_center.py:863-894` | ✅ TimeoutError → interrupted + CAS |
| stale cleanup 不丢 result | `boss_command_center.py:537-539` | ✅ has_result → partial |
| late result 不覆盖 interrupted | `boss_command_center.py:837-850` | ✅ CAS + module_result_ignored |
| accept_mission → done | `boss_command_center.py:479-494` | ✅ 接受 ready_for_review/partial/interrupted |
| partial/interrupted 可 accept | `boss_command_center.py:485` | ✅ 状态白名单包含三者 |

---

## 4. 用户操作流程

### 正常流程

1. **创建任务**：`POST /boss/missions` 或从模板创建
2. **查看计划**：`GET /boss/missions/{id}` 查看 pending_review 状态和模块列表
3. **确认执行**：`POST /boss/missions/{id}/run`
4. **等待完成**：前端轮询 `GET /boss/missions/{id}`，直到 status 不是 `running`
5. **审核结果**：查看各模块 result，决定是否接受
6. **接受结果**：`POST /boss/missions/{id}/accept`

### 异常处理

- **模块超时**：status 变为 `partial` 或 `interrupted`，用户可接受或重跑单个模块
- **全部失败**：status 变为 `failed`，用户可重跑 `POST /boss/missions/{id}/run`
- **部分成功**：status 变为 `partial`，用户可接受当前结果或重跑失败模块

### 重跑单个模块

`POST /boss/missions/{id}/modules/{module_id}/run` 可单独重跑某个失败/中断的模块。

---

## 5. 已取消的自动循环

| 旧机制 | 当前状态 |
|--------|----------|
| auto_run=True 创建后立即执行 | ❌ 已废弃，参数保留但忽略 |
| 自动重试失败模块 | ❌ 不存在，每个模块只执行一次 |
| 自动验收 | ❌ 不存在，必须人工 accept |
| 自动清理 stale | ❌ 需手动调用 cleanup API 或 run_mission 前自动清理 |

---

## 6. 推荐验证命令

```bash
# Boss Command Center 单元测试（全量通过）
python -m pytest tests/test_boss_command_center.py -v

# Graph Template 测试（全量通过）
python -m pytest tests/test_graph_template_store.py -v

# 前端构建
cd frontend-new && npm run build

# Boss E2E 测试（5 个场景，route mock，不依赖真实 AI）
npx playwright test e2e/boss-flow.spec.ts

# DAG Canvas E2E（51 个场景）
npx playwright test e2e/dag-editor.spec.ts --grep "DAG Canvas"
```

---

## 7. E2E 测试覆盖（Phase 6.18）

E2E 测试文件：`frontend-new/e2e/boss-flow.spec.ts`

使用 Playwright `page.route()` 拦截所有 Boss API，用内存状态模拟 mission 生命周期。不依赖真实 AI、不依赖 DB。

### 覆盖场景

| # | 场景 | 验证点 |
|---|------|--------|
| 1 | 创建计划 | pending_review 状态、模块列表、确认执行按钮 |
| 2 | 确认执行 + 轮询 | running → ready_for_review 状态推进、结果文本、接受按钮 |
| 3 | 接受结果 | done 状态、接受按钮消失 |
| 4 | partial 可见 | 部分结果显示、接受按钮、重跑按钮 |
| 5 | runMission 失败 | 500 错误横幅、partial 结果保留 |

### Mock 方案

单个正则路由 `/\/boss/missions/` 处理所有请求，按 URL 后缀和 HTTP 方法分发：
- `POST /boss/missions` → 创建 pending_review
- `POST .../run` → 返回 running（延迟 3s 让轮询有时间触发）
- `GET .../events` → 返回事件列表
- `GET /boss/missions/{id}` → 按轮询计数推进状态
- `POST .../accept` → 返回 done

### 关键设计决策

- `runMission` mock 延迟 3 秒：因为 `confirmRun` 在 `finally` 中立即停止轮询，延迟让轮询有时间触发
- 使用正则路由而非 glob：避免多个路由注册顺序导致的匹配歧义
- 单一闭包变量 `pollCount`：在 mission GET 中递增，events GET 中只读取

---

## 8. 通用业务流程执行协议（Phase 6.19）

### 设计原则

Boss Command Center 是一个**通用业务流程执行系统**，不是某个具体业务的工具。

核心原则：
1. **系统核心适配所有业务流程**，不绑定任何具体行业
2. **业务差异通过用户输入、模板参数、上下文 schema、审核清单体现**
3. **核心代码中不把任何单一业务当成默认骨架**
4. **具体行业模板只能作为 example 或 alias，不能成为核心默认架构**

### 模板协议

每个模板必须包含以下字段：

| 字段 | 类型 | 说明 |
|------|------|------|
| `id` | string | 模板唯一标识 |
| `protocol_version` | string | 协议版本号 |
| `template_type` | string | 固定为 `generic_business_process` |
| `domain_lock` | boolean | 固定为 `False`（不锁定具体业务领域） |
| `name` | string | 模板名称 |
| `description` | string | 模板描述 |
| `default_goal` | string | 默认目标（通用，不绑定具体行业） |
| `default_modules` | list | 默认启用的模块 |
| `suggested_inputs` | list | 建议的用户输入 |
| `expected_outputs` | list | 期望的输出 |
| `input_fields` | list | 结构化输入字段定义 |
| `context_schema` | object | 上下文 schema |
| `review_checklist` | list | 审核清单 |

### 通用模板列表

| ID | 名称 | 用途 |
|----|------|------|
| `goal_to_plan` | 目标到计划 | 从目标出发，产出策略判断和执行计划 |
| `research_to_decision` | 调研到决策 | 围绕决策问题，收集信息、分析选项、给出建议 |
| `deliverable_pack` | 交付物生成 | 围绕交付目标，产出结构化内容或文档 |
| `communication_plan` | 沟通与触达方案 | 围绕沟通目标，设计触达策略和内容方案 |
| `operation_review` | 流程复盘 | 对已完成工作进行复盘，总结经验教训 |
| `risk_check` | 风险检查 | 对计划进行风险评估，给出应对方案 |
| `execution_checklist` | 执行清单 | 将复杂任务拆解为详细执行清单 |
| `data_insight` | 数据洞察 | 围绕数据进行分析，发现关键洞察 |

### 旧模板兼容

旧业务模板 ID 通过 `TEMPLATE_ALIASES` 映射到通用模板：

| 旧 ID | 映射到 |
|-------|--------|
| `ecommerce_product_research` | `research_to_decision` |
| `xianyu_listing_pack` | `deliverable_pack` |
| `saas_feature_planning` | `goal_to_plan` |
| `landing_page_offer` | `deliverable_pack` |
| `weekly_business_review` | `operation_review` |
| `xianyu_delivery_pack` | `deliverable_pack` |

旧 ID 可正常创建 mission，但使用通用模板协议和通用模块 prompt。

### 模块定义（通用能力）

| 模块 ID | 名称 | 能力描述 |
|---------|------|----------|
| `strategy` | 目标理解与策略判断 | 理解用户目标，提取核心意图，给出策略判断 |
| `market` | 上下文与证据整理 | 围绕目标收集相关上下文、事实依据和参考案例 |
| `marketing` | 沟通与触达方案 | 设计沟通策略、内容方向、触达渠道和具体文案 |
| `landing` | 交付物结构 | 设计可交付物的结构、框架和核心内容 |
| `actions` | 执行计划 | 将目标拆解为可执行的行动项 |

---

## 9. 已知限制

1. **编码问题**：Windows 环境下日志输出的中文字符显示为乱码，不影响实际功能。
