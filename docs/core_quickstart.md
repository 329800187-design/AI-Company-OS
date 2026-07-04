# AI Company OS Core — 快速启动指南

## 概述

Core 是 AI Company OS 的最小启动入口，只包含：
- **Governance** — 框架约束层（分类、规划、执行）
- **Agent 管理** — 发现 / 启用 / 禁用 / 执行
- **Collaboration** — 多智能体协作计划
- **MiniDelivery** — 最小交付闭环（文案包生成）

不加载旧系统路由（Boss / Workflow / Pipeline / Commander / Marketing / Image / Data / CTO / Payment / User / OAuth / Cron / Admin）。

---

## 启动

```bash
cd E:\AI-company-os
pip install -r requirements-core.txt
uvicorn backend.core_app:app --reload --port 8000
```

## 验证

### 1. 健康检查

```bash
curl http://localhost:8000/health
```

返回：
```json
{"status":"ok","mode":"core","version":"1.5.1","timestamp":"..."}
```

### 2. 查看 API 文档

浏览器打开：http://localhost:8000/docs

### 3. 查看已发现的 Agent

```bash
curl http://localhost:8000/agents/discovered
```

### 4. 启用一个 Agent

```bash
curl -X POST http://localhost:8000/agents/{agent_id}/enable
```

### 5. 禁用一个 Agent

```bash
curl -X POST http://localhost:8000/agents/{agent_id}/disable
```

### 6. 执行 Agent 任务

```bash
curl -X POST http://localhost:8000/agents/{agent_id}/execute \
  -H "Content-Type: application/json" \
  -d '{"goal":"测试任务","task_type":"test"}'
```

### 7. 运行 Governance 协同

```bash
curl -X POST http://localhost:8000/governance/run \
  -H "Content-Type: application/json" \
  -d '{"goal":"帮我生成文案和图片","execute":true}'
```

### 8. 创建协作计划

```bash
curl -X POST http://localhost:8000/collaboration/plan \
  -H "Content-Type: application/json" \
  -d '{"goal":"测试协作","steps":[{"name":"Echo","task_type":"echo","required_capability":"echo"}]}'
```

---

## 安装 Agent

将 agent.json 放入 `agents/installed/xxx/agent.json`，重启 Core 后自动发现。

---

## Core 注册路由清单

| 路由前缀 | 端点 | 说明 |
|----------|------|------|
| `/governance` | `POST /classify` | 目标分类 |
| `/governance` | `POST /plan` | 生成执行计划 |
| `/governance` | `POST /run` | 执行协同 |
| `/governance` | `GET /runs` | 历史执行记录 |
| `/governance` | `GET /runs/{run_id}` | 运行记录详情 |
| `/governance` | `GET /runs/{run_id}/events` | 执行事件流 |
| `/governance` | `GET /runs/{run_id}/artifact` | 读取产物内容 |
| `/governance` | `GET /routes` | 路由查询 |
| `/collaboration` | `POST /plan` | 多智能体协作计划 |
| `/collaboration` | `POST /run` | 执行协作计划 |
| `/minidelivery` | `POST /xhs-copy-pack` | 小红书文案包 |
| `/minidelivery` | `POST /copy-pack` | 通用文案包 |
| `/minidelivery` | `GET /tasks/{task_id}` | 查询任务状态 |
| `/minidelivery` | `GET /tasks/{task_id}/artifact` | 获取产出物 |
| `/agents` | `GET /discovered` | 已发现 Agent 列表 |
| `/agents` | `POST /{id}/enable` | 启用 Agent |
| `/agents` | `POST /{id}/disable` | 禁用 Agent |
| `/agents` | `POST /{id}/execute` | 执行 Agent |

## Legacy 未注册清单

以下路由**不在** Core 中注册：

- `/boss/*` — Boss 管理
- `/workflows/*` — 工作流
- `/pipeline/*` — Pipeline
- `/commander/*` — 指挥官
- `/tasks/*` — 任务管理
- `/cto/*` — CTO Agent
- `/image/*` — 图片生成
- `/marketing/*` — 营销
- `/data/*` — 数据分析
- `/payment/*` — 支付
- `/user/*` — 用户管理
- `/oauth/*` — OAuth
- `/cron/*` — 定时任务
- `/admin/*` — 管理后台
- `/memory/*` — 记忆系统
- `/brain/*` — 大脑
- `/swarm/*` — 集群
- `/plugin/*` — 插件
- `/search/*` — 搜索
- `/backup/*` — 备份
- `/export/*` — 导出
- `/usage/*` — 用量统计
- `/metrics/*` — 指标
- `/audit/*` — 审计
- `/template/*` — 模板
- `/skill/*` — 技能
- `/ai-registry/*` — AI 注册中心
- `/config/*` — 配置
- `/api-keys/*` — API Key
- `/feishu/*` — 飞书
- `/agent-market/*` — Agent 市场
- `/agent-console/*` — Agent 控制台
- `/commander-manager/*` — 指挥官管理
- `/plugin-config/*` — 插件配置
- `/capabilities/*` — 能力管理
