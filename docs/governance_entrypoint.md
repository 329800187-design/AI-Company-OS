# Governance 主入口使用指南

## 推荐主入口

**POST /governance/run**

分类 -> 计划 -> 执行 -> 记录，一站式闭环。

### 请求示例：小红书文案

```json
POST /governance/run
{
  "goal": "帮我为手工耳环生成小红书种草文案",
  "platform": "xiaohongshu",
  "execute": true
}
```

### 请求示例：抖音文案

```json
POST /governance/run
{
  "goal": "帮我为手工耳环生成抖音种草文案",
  "platform": "douyin",
  "execute": true
}
```

### 请求参数说明

| 字段     | 类型   | 必填 | 说明                                         |
| -------- | ------ | ---- | -------------------------------------------- |
| goal     | string | 是   | 用户目标描述                                 |
| platform | string | 否   | xiaohongshu 或 douyin                        |
| execute  | bool   | 否   | false 只返回计划，true 执行并产出产物        |

### 成功响应关键字段（execute=true）

| 字段          | 说明                                      |
| ------------- | ----------------------------------------- |
| run_id        | 运行记录 ID                               |
| status        | succeeded / rejected / needs_clarification|
| artifact_path | 产物 Markdown 文件路径                    |
| json_path     | 结果 JSON 文件路径                        |
| task_id       | 任务 ID                                   |
| mode          | 生成模式：api 或 template_fallback        |
| summary       | 人类可读的执行摘要                        |
| result        | 完整结果对象（含 ok, checks, spec 等）    |

### 成功响应示例

```json
{
  "run_id": "run_abc123",
  "status": "succeeded",
  "artifact_path": "output/minidelivery/run_abc123/xiaohongshu_pack.md",
  "json_path": "output/minidelivery/run_abc123/result.json",
  "task_id": "run_abc123",
  "mode": "api",
  "summary": "小红书文案包生成成功（api），所有验收检查通过。",
  "plan": { "..." : "..." },
  "classification": { "..." : "..." },
  "result": { "ok": true, "..." : "..." }
}
```

### 仅分类+计划（execute=false）

```json
POST /governance/run
{
  "goal": "帮我为手工耳环生成小红书种草文案",
  "platform": "xiaohongshu",
  "execute": false
}
```

返回 run_id、classification、plan，不执行产物生成。

## 推荐测试流程

1. GET /governance/entrypoints -- 查看入口说明
2. POST /governance/classify -- 验证目标分类
3. POST /governance/plan -- 查看执行计划
4. POST /governance/run with execute=true -- 完整执行
5. GET /governance/runs/{run_id} -- 查看运行记录
6. GET /governance/runs/{run_id}/events -- 查看执行事件

## 底层能力入口

| 路径                         | 说明                                         |
| ---------------------------- | -------------------------------------------- |
| POST /minidelivery/copy-pack    | 底层文案包能力入口，供 Governance 调用或兼容测试 |
| POST /minidelivery/xhs-copy-pack | 旧小红书文案包兼容入口                       |

这些是受控入口（controlled），由 Governance 层调度，不建议前端优先调用。

## 已废弃入口

以下旧执行入口已返回 410 Gone，不应再直接调用：

- POST /workflows/ceo-create-task
- POST /workflows/ceo-codex-task
- POST /workflows/dag/run
- POST /workflows/dag/run-async
- POST /templates/run/{template_id}
- POST /commander/sessions/{session_id}/continue

## 治理状态接口

| 端点                         | 说明                                       |
| ---------------------------- | ------------------------------------------ |
| GET /governance/routes/summary  | 治理路由统计摘要                           |
| GET /governance/routes/high-risk | 高风险路由（应为 0）                      |
| GET /governance/entrypoints     | 推荐入口说明                               |

governance_complete=true 表示未治理执行入口为 0，治理收束已完成。

## 正式前端访问方式

正式前端通过 SPA 入口访问，`/governance/*` 是后端 API 路径，不是前端页面路由。

- 浏览器访问：`http://127.0.0.1:8000/app`
- 侧边栏 → **更多功能** → **Governance**
- 页面内调用：`POST /governance/run`（执行）+ `GET /governance/runs/{run_id}/artifact`（读取产物）

### 直接进入 Governance（跳过 Landing 页）

| 路径 | 说明 |
| ---- | ---- |
| `http://127.0.0.1:8000/app?page=governance` | URL query 参数 |
| `http://127.0.0.1:8000/app#governance` | URL hash 参数 |

两种方式均跳过 Landing 欢迎页，直接进入 Governance 页面。

## 浏览器测试页（开发验收用）

后端启动后，直接在浏览器访问：

http://127.0.0.1:8000/governance/test-page

页面包含：
- 目标输入框
- 平台选择（xiaohongshu / douyin）
- execute 开关
- 一键调用 POST /governance/run
- 展示关键字段和完整 JSON 响应

也可以直接打开 docs/governance_test_page.html 文件（会自动 fallback 到 127.0.0.1:8000）。

注意：此页面是开发验收用的临时测试页，不是正式前端 UI。正式前端在 frontend-new/ 目录，
后续正式 UI 应通过 frontend-new 调用 POST /governance/run。
