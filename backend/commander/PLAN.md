# Commander 主脑 · 实施计划

## 目标
把 AI Company OS 从"请求-响应"式 API 升级为**能持续自主运转的多智能体系统**。

## 核心流程
```
用户给一个目标 → Commander 拆解 → 循环执行 → 决策 → 继续/重试/问人 → 最终报告
```

## 实现步骤

### 1. SQLite 持久化存储
- 新建 `backend/database/` 模块
- `sessions` 表: session_id, goal, status, steps 总数, 创建/完成时间
- `steps` 表: step_number, 描述, 分配的 Agent, task_id, 状态, 结果摘要, AI 决策
- `tasks` 表: 复用现有任务数据但持久化到 SQLite
- `task_service.py` 改造为 SQLite 后端，保留内存作为临时回退

### 2. Commander Agent (`backend/commander/commander.py`)
- **创建模式**: 收到目标 → AI 拆解为步骤列表 → 存入 SQLite
- **执行模式**: 逐步骤执行，分配给对应 Agent
- **决策模式**: 执行完看结果 → AI 判断: continue(继续) / retry(重试) / adjust(修方案) / ask(问用户)
- **人机交互**: 卡住时暂停，等你输入后再继续
- **收尾模式**: 全部完成 → 生成总结报告

### 3. Commander 路由器 (`backend/routers/commander_router.py`)
- `POST /commander/run` — 提交目标，开始自主执行
- `GET /commander/sessions` — 所有执行记录
- `GET /commander/sessions/{id}` — 查看某次执行的完整步骤和状态
- `POST /commander/sessions/{id}/continue` — 继续被暂停的执行

### 4. 整合到 app.py

## 文件清单
```
backend/
  database/
    __init__.py
    database.py      ← SQLite 建表、CRUD
  services/
    task_service.py   ← 升级为 SQLite 存储
  commander/
    __init__.py
    commander.py      ← 主脑编排逻辑
  routers/
    commander_router.py
  app.py             ← 注册新路由器
```
