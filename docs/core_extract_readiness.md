# Core 拆分审计：可分发底座

**审计日期**: 2026-07-02
**审计目标**: 判断当前项目能否拆成一个可给别人使用的 AI Company OS Core，不新增功能，不改业务逻辑。

---

## 1. 审计结论

**当前能否直接分发？** → **不能直接分发，但距离很近。**

核心问题：
1. `agents/installed/` 目录为空——没有可运行的示例 Agent
2. `user_data/agent_registry/enabled_agents.json` 不存在——首次启动无默认启用配置
3. `governance_router.py` 硬依赖 `minidelivery` 业务管线——Core 和业务没解耦
4. `app.py` 注册了 30+ 个 router——无法只加载 Core router

---

## 2. Core 必须保留目录盘点

### 2.1 数据模型层（零外部依赖）

| 文件 | 依赖 | 状态 |
|------|------|------|
| `backend/schemas/agent_manifest.py` | pydantic, json, pathlib | ✅ 自包含 |
| `backend/schemas/agent_protocol.py` | pydantic | ✅ 自包含 |
| `backend/schemas/collaboration_plan.py` | pydantic, agent_protocol | ✅ 仅依赖 Core 内部 |

### 2.2 服务层

| 文件 | 依赖 | 状态 |
|------|------|------|
| `backend/services/agent_loader.py` | importlib, agent_manifest | ✅ 自包含 |
| `backend/services/agent_executor.py` | agent_protocol, agent_manifest, agent_loader, agent_discovery | ✅ Core 内部闭环 |
| `backend/services/agent_discovery.py` | agent_manifest, adapters (ollama/mimo lazy import), logger | ⚠️ 有 lazy import 到 adapters |
| `backend/services/collaboration_planner.py` | collaboration_plan, agent_manifest | ✅ Core 内部闭环 |
| `backend/services/collaboration_executor.py` | collaboration_plan, agent_protocol, agent_executor | ✅ Core 内部闭环 |

### 2.3 Governance 层（框架约束层）

| 文件 | 依赖 | 状态 |
|------|------|------|
| `backend/governance/__init__.py` | 无 | ✅ |
| `backend/governance/capability_catalog.py` | pydantic | ✅ 自包含 |
| `backend/governance/classifier.py` | pydantic, re | ✅ 自包含 |
| `backend/governance/execution_plan.py` | pydantic | ✅ 自包含 |
| `backend/governance/run_record.py` | pydantic, json, execution_plan | ✅ Core 内部 |
| `backend/governance/guard.py` | — | ✅ |
| `backend/governance/route_policy.py` | — | ✅ |
| `backend/governance/errors.py` | — | ✅ |
| `backend/governance/deprecated.py` | — | ✅ |

### 2.4 路由层

| 文件 | 依赖 | 状态 |
|------|------|------|
| `backend/routers/governance_router.py` | governance/*, minidelivery/*, collaboration_* | ⚠️ 硬依赖 minidelivery |
| `backend/routers/collaboration_router.py` | collaboration_planner, collaboration_executor | ✅ 自包含 |

---

## 3. 可选 / Legacy 目录盘点

### 3.1 Legacy Agents（不进 Core）

| 目录 | 说明 | 进 Core? |
|------|------|----------|
| `agents/ceo_agent/` | CEO Agent（旧格式，无 manifest） | ❌ |
| `agents/cto_agent/` | CTO Agent（旧格式） | ❌ |
| `agents/codex_agent/` | Codex Agent（旧格式） | ❌ |
| `agents/qa_agent/` | QA Agent（旧格式） | ❌ |
| `agents/system_agent/` | System Agent（旧格式） | ❌ |
| `agents/openclaw_agent/` | OpenClaw Agent（旧格式） | ❌ |
| `agents/video_agent/` | Video Agent（旧格式） | ❌ |
| `agents/user_plugins/` | 用户插件目录 | ❌ |

### 3.2 有 Manifest 的 Agent（可选进 Core 作为示例）

| 目录 | manifest id | 进 Core? |
|------|-------------|----------|
| `agents/marketing_agent/` | marketing | ✅ 可作为示例 |
| `agents/image_agent/` | image | ✅ 可作为示例 |
| `agents/data_agent/` | data | ✅ 可作为示例 |

### 3.3 旧 Boss/Workflow/Pipeline 路由

| 文件 | 说明 | 进 Core? |
|------|------|----------|
| `backend/routers/boss_router.py` | Boss 指挥中心 | ❌ Legacy |
| `backend/routers/commander_router.py` | 指挥官路由 | ❌ Legacy |
| `backend/routers/commander_manager_router.py` | 指挥官管理 | ❌ Legacy |
| `backend/routers/workflow_router.py` | 工作流路由 | ❌ Legacy |
| `backend/routers/pipeline_router.py` | Pipeline 路由 | ❌ Legacy |
| `backend/routers/swarm_router.py` | Swarm 路由 | ❌ Legacy |
| `backend/routers/brain_router.py` | Brain 路由 | ❌ Legacy |

### 3.4 业务路由（不进 Core）

| 文件 | 说明 |
|------|------|
| `backend/routers/image_router.py` | 图片生成 |
| `backend/routers/marketing_router.py` | 营销内容 |
| `backend/routers/data_router.py` | 数据分析 |
| `backend/routers/cto_router.py` | CTO 路由 |
| `backend/routers/feishu_router.py` | 飞书集成 |
| `backend/routers/minidelivery_router.py` | 小红书文案包 |
| `backend/routers/payment_router.py` | 支付 |
| `backend/routers/user_router.py` | 用户管理 |
| `backend/routers/admin_router.py` | 管理后台 |

### 3.5 基础设施路由（Core 可选保留）

| 文件 | 说明 | 进 Core? |
|------|------|----------|
| `backend/routers/agent_router.py` | Agent CRUD/启停 | ✅ Core 需要 |
| `backend/routers/agent_console_router.py` | Agent 控制台 | ✅ Core 需要 |
| `backend/routers/task_router.py` | 任务管理 | ✅ Core 需要 |
| `backend/routers/config_router.py` | 配置管理 | ✅ Core 需要 |
| `backend/routers/ai_registry_router.py` | AI 服务注册 | ✅ Core 需要 |
| `backend/routers/health_router.py` | 健康检查 | ✅ 内嵌在 app.py |
| `backend/routers/agent_market_router.py` | Agent 市场 | ⚠️ 可选 |
| `backend/routers/capabilities_router.py` | 能力目录 | ✅ Core 需要 |
| `backend/routers/plugin_router.py` | 插件管理 | ⚠️ 可选 |
| `backend/routers/plugin_config_router.py` | 插件配置 | ⚠️ 可选 |

---

## 4. 最小可运行目录结构

```
ai-company-os-core/
├── backend/
│   ├── __init__.py
│   ├── app.py                    # 精简版，只注册 Core router
│   ├── config.py                 # 配置
│   ├── version.py                # 版本号
│   ├── logger.py                 # 日志
│   ├── error_handler.py          # 错误处理
│   ├── database/
│   │   ├── __init__.py
│   │   └── database.py           # SQLite，零配置
│   ├── middleware/
│   │   ├── __init__.py
│   │   ├── auth_middleware.py     # API Key 认证
│   │   ├── error_handler.py      # 全局错误
│   │   └── audit.py              # 审计日志
│   ├── schemas/
│   │   ├── __init__.py
│   │   ├── agent_manifest.py     # Agent 清单模型
│   │   ├── agent_protocol.py     # 执行协议
│   │   └── collaboration_plan.py # 协同计划模型
│   ├── services/
│   │   ├── __init__.py
│   │   ├── agent_loader.py       # Agent 加载器
│   │   ├── agent_executor.py     # 统一执行器
│   │   ├── agent_discovery.py    # Agent 发现（精简版）
│   │   ├── collaboration_planner.py  # 协同计划构建
│   │   ├── collaboration_executor.py # 协同执行
│   │   └── logger.py             # 服务日志
│   ├── governance/
│   │   ├── __init__.py
│   │   ├── capability_catalog.py # 能力目录
│   │   ├── classifier.py         # 目标分类器
│   │   ├── execution_plan.py     # 执行计划
│   │   ├── run_record.py         # 运行记录
│   │   ├── guard.py              # 治理守卫
│   │   ├── route_policy.py       # 路由策略
│   │   ├── errors.py             # 错误定义
│   │   └── deprecated.py         # 废弃标记
│   ├── routers/
│   │   ├── __init__.py
│   │   ├── governance_router.py  # 治理 API（需解耦 minidelivery）
│   │   ├── collaboration_router.py # 协同 API
│   │   ├── agent_router.py       # Agent CRUD
│   │   ├── agent_console_router.py # Agent 控制台
│   │   ├── task_router.py        # 任务管理
│   │   ├── config_router.py      # 配置
│   │   └── capabilities_router.py # 能力目录
│   ├── adapters/                 # 可选：精简为只保留 base + ollama
│   │   ├── __init__.py
│   │   ├── base_adapter.py
│   │   └── ollama_adapter.py
│   └── task_queue/
│       ├── __init__.py
│       └── queue.py              # 后台任务
├── agents/
│   ├── __init__.py
│   ├── base_agent.py             # Agent 基类
│   └── installed/
│       └── example_echo_agent/   # 示例 Agent
│           ├── agent.json
│           └── agent.py
├── user_data/
│   └── agent_registry/
│       └── enabled_agents.json   # 默认启用配置
├── core/                         # 可选：Agent 间通信协议
│   └── agent_protocol.py
├── requirements.txt              # 精简依赖
├── .env.example
├── README.md
└── start.sh / start.bat
```

---

## 5. 第三方 Agent 接入协议

### 5.1 agent.json Manifest 格式

```json
{
  "id": "my_agent",
  "name": "我的 Agent",
  "version": "1.0.0",
  "entrypoint": "agents.installed.my_agent.agent:MyAgent",
  "capabilities": ["copywriting", "research"],
  "task_types": ["copywriting", "research"],
  "risk_level": "low",
  "enabled": true,
  "description": "一句话说明这个 Agent 做什么",
  "requires_api_key": false,
  "requires_gpu": false
}
```

### 5.2 entrypoint 格式

```
module.path:ClassName
```

- `module.path` — Python 模块路径，从项目根目录开始
- `:ClassName` — 类名，必须实现 `execute(task_dict) -> dict` 方法

### 5.3 Agent 类实现要求

```python
class MyAgent:
    """第三方 Agent 示例"""

    def __init__(self, **kwargs):
        """可选初始化，接收配置参数"""
        pass

    def execute(self, task: dict) -> dict:
        """
        执行任务。

        Args:
            task: 字典，包含以下字段：
                - task_id: str — 任务唯一标识
                - goal: str — 任务目标
                - task_type: str — 任务类型
                - 其他自定义字段

        Returns:
            dict — 必须包含以下字段：
                - ok: bool — 是否成功
                - agent: str — Agent 标识
                - data: dict — 执行产出
                - artifacts: list[str] — 产物路径列表（可选）
                - error: str — 错误信息（失败时）
                - meta: dict — 元数据（可选）
        """
        return {
            "ok": True,
            "agent": "my_agent",
            "data": {"result": "执行完成"},
            "artifacts": [],
            "meta": {},
        }
```

### 5.4 AgentRunResult 标准返回

```python
class AgentRunResult(BaseModel):
    ok: bool                    # 是否执行成功
    agent_id: str               # 执行的 agent 标识
    output: Dict[str, Any]      # 执行产出数据
    artifacts: List[str]        # 产物路径列表
    error: Optional[str]        # 错误信息（ok=false 时）
    metadata: Dict[str, Any]    # 执行元数据
```

---

## 6. Clean Install 验证流程

### Step 1: 安装依赖

```bash
cd ai-company-os-core
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

**requirements.txt 最小依赖：**
```
fastapi>=0.104.0
uvicorn[standard]>=0.24.0
pydantic>=2.0.0
httpx>=0.25.0
```

### Step 2: 配置环境

```bash
cp .env.example .env
# 编辑 .env，设置 AI_PROVIDER 和 API Key（可选）
```

### Step 3: 启动 Backend

```bash
uvicorn backend.app:app --reload --port 8001
```

### Step 4: 验证健康检查

```bash
curl http://localhost:8001/health
# 期望返回: {"status":"ok","version":"..."}
```

### Step 5: 访问 Agent 控制台

```bash
curl http://localhost:8001/app
# 浏览器打开 http://localhost:8001/app
```

### Step 6: 启用示例 Agent

```bash
# 查看可用 Agent
curl http://localhost:8001/agents

# 启用 example_echo_agent
curl -X POST http://localhost:8001/agents/example_echo/enable
```

### Step 7: 运行协同任务

```bash
# 通过 Governance 入口
curl -X POST http://localhost:8001/governance/run \
  -H "Content-Type: application/json" \
  -d '{"goal": "帮我为手工耳环写一段推广文案", "execute": true}'

# 通过 Collaboration 入口
curl -X POST http://localhost:8001/collaboration/run \
  -H "Content-Type: application/json" \
  -d '{
    "goal": "生成推广内容",
    "steps": [
      {"name": "写文案", "task_type": "copywriting", "required_capability": "copywriting"}
    ]
  }'
```

### Step 8: 查看运行记录

```bash
curl http://localhost:8001/governance/runs
curl http://localhost:8001/governance/runs/{run_id}
curl http://localhost:8001/governance/runs/{run_id}/events
```

---

## 7. 当前阻塞项

### 7.1 文件硬依赖旧 Agents

| 文件 | 硬依赖 | 影响 |
|------|--------|------|
| `backend/services/agent_loader.py` | `AGENT_REGISTRY` 硬编码了 10 个旧 agent 的 entrypoint | Core 版本需要清空或改为动态注册 |
| `backend/services/agent_discovery.py` | `_default_enabled_config` 硬编码了旧 agent ID | Core 版本需要改为只注册 manifest agent |
| `backend/services/agent_discovery.py` | `_scan_local_agents()` 中的 `agent_capabilities` fallback 字典硬编码了 7 个旧 agent | 需要删除 fallback，只走 manifest |
| `backend/app.py` | 注册了 30+ 个 router，包括所有旧路由 | Core 版本需要精简 app.py |

### 7.2 Router 不适合放进 Core

| Router | 原因 |
|--------|------|
| `boss_router.py` | 旧 Boss 指挥中心，已被 governance 替代 |
| `commander_router.py` | 旧指挥官路由 |
| `commander_manager_router.py` | 旧指挥官管理 |
| `workflow_router.py` | 旧工作流系统 |
| `pipeline_router.py` | 旧 Pipeline |
| `swarm_router.py` | 旧 Swarm |
| `brain_router.py` | 旧 Brain |
| `cto_router.py` | 业务路由 |
| `image_router.py` | 业务路由 |
| `marketing_router.py` | 业务路由 |
| `data_router.py` | 业务路由 |
| `feishu_router.py` | 外部集成 |
| `minidelivery_router.py` | 业务路由（小红书文案包） |
| `payment_router.py` | 支付系统 |
| `user_router.py` | 用户管理（Core 可简化） |
| `admin_router.py` | 管理后台 |
| `backup_router.py` | 备份恢复 |
| `search_router.py` | 全文搜索 |
| `cron_router.py` | 定时任务 |
| `metrics_router.py` | 指标监控 |
| `export_router.py` | 数据导出 |
| `audit_router.py` | 审计日志（Core 可保留精简版） |
| `skill_router.py` | 技能管理 |
| `memory_router.py` | 内存管理 |
| `usage_router.py` | 用量统计 |
| `template_router.py` | 模板管理 |
| `apikey_router.py` | API Key 管理 |

### 7.3 governance_router 需要解耦

`governance_router.py` 的 `api_run()` 函数中，针对每个 `capability_id` 都有硬编码的 `from backend.minidelivery.pipeline import ...` 调用。Core 版本需要：

1. 将 `capability_catalog.py` 中的 `entrypoint` 字段改为动态加载
2. `api_run()` 改为通过 `entrypoint` 动态调用，而不是 if/elif 分支
3. 或者将 minidelivery 作为可选插件，Core 只保留 governance 框架

### 7.4 测试需要独立

| 测试文件 | 说明 | 进 Core? |
|----------|------|----------|
| `test_governance.py` | Governance 测试 | ✅ Core 测试 |
| `test_collaboration_plan.py` | 协同计划测试 | ✅ Core 测试 |
| `test_capability.py` | 能力目录测试 | ✅ Core 测试 |
| `test_agents_quick.py` | Agent 快速测试 | ✅ Core 测试 |
| `test_minidelivery.py` | MiniDelivery 测试 | ❌ 业务测试 |
| `test_boss_*.py` | Boss 相关测试 | ❌ Legacy 测试 |
| `test_commander.py` | 指挥官测试 | ❌ Legacy 测试 |
| `test_e2e_workflow.py` | 端到端测试 | ❌ 业务测试 |
| 其他 test_*.py | 各种业务测试 | ❌ 业务测试 |

---

## 8. 解耦行动清单（不改业务逻辑）

| # | 行动 | 复杂度 | 阻塞? |
|---|------|--------|-------|
| 1 | 创建 `agents/installed/example_echo_agent/` 示例 Agent | 低 | ✅ 是 |
| 2 | 创建 `user_data/agent_registry/enabled_agents.json` 默认配置 | 低 | ✅ 是 |
| 3 | 精简 `app.py`，创建 `core_app.py` 只注册 Core router | 中 | ✅ 是 |
| 4 | 解耦 `governance_router.py` 的 minidelivery 硬依赖 | 中 | ✅ 是 |
| 5 | 清理 `agent_loader.py` 的 `AGENT_REGISTRY` 硬编码 | 低 | ⚠️ 可选 |
| 6 | 清理 `agent_discovery.py` 的 fallback 硬编码 | 低 | ⚠️ 可选 |
| 7 | 精简 `requirements.txt` | 低 | ⚠️ 可选 |
| 8 | 编写 Core 专属测试 | 中 | ⚠️ 可选 |

---

## 9. 最终判断

| 维度 | 状态 | 说明 |
|------|------|------|
| 数据模型层 | ✅ 可分发 | schemas 零外部依赖 |
| 服务层 | ✅ 可分发 | 核心服务自包含 |
| Governance 层 | ✅ 可分发 | 框架层零外部依赖 |
| 路由层 | ⚠️ 需解耦 | governance_router 硬依赖 minidelivery |
| Agent 加载 | ⚠️ 需补充 | agents/installed 为空，无示例 |
| 配置 | ⚠️ 需补充 | enabled_agents.json 不存在 |
| app.py | ⚠️ 需精简 | 注册了 30+ router，Core 只需 7 个 |
| 测试 | ⚠️ 需分离 | Core 测试和业务测试混在一起 |

**总结**: 核心框架代码（schemas + services + governance）已经是自包含的，可以直接分发。阻塞项是：缺少示例 Agent、缺少默认配置、governance_router 与 minidelivery 未解耦、app.py 未精简。完成 4 个阻塞项（约 1-2 天工作量）即可发布 Core 版本。
