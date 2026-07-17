# Agent Plugin Spec

第三方 Agent 开发规范。照此模板编写你自己的 Agent 并放入 `agents/installed/` 即可被系统自动发现和调用。

---

## 目录结构

```
agents/installed/your_agent/
├── __init__.py        # 空文件
├── agent.json         # 清单（必须）
└── agent.py           # Agent 类（必须）
```

---

## agent.json 字段说明

```json
{
  "id": "your_agent",
  "name": "你的 Agent 名称",
  "version": "1.0.0",
  "entrypoint": "agents.installed.your_agent.agent:YourAgentClass",
  "capabilities": ["capability_a", "capability_b"],
  "task_types": ["task_a", "task_b"],
  "risk_level": "low",
  "enabled": true,
  "description": "一句话说明这个 Agent 做什么",
  "requires_api_key": false,
  "requires_gpu": false
}
```

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `id` | string | ✅ | 唯一标识。系统通过此 ID 路由任务、查启用状态。全小写+下划线 |
| `name` | string | ✅ | 显示名称，出现在 Agent 列表和前端 UI |
| `version` | string | | 语义版本号，默认 `1.0.0` |
| `entrypoint` | string | ✅ | 加载入口，格式 `module.path:ClassName` |
| `capabilities` | string[] | | 能力标签列表。协作计划通过此字段匹配 Agent |
| `task_types` | string[] | | 可处理的任务类型，用于任务路由 |
| `risk_level` | string | | `low` / `medium` / `high`，默认 `low` |
| `enabled` | bool | | 是否启用，默认 `true` |
| `description` | string | | 一句话描述 |
| `requires_api_key` | bool | | 是否需要 API Key，默认 `false` |
| `requires_gpu` | bool | | 是否需要 GPU，默认 `false` |

---

## entrypoint 格式

```
module.path:ClassName
```

- **module.path**: Python 模块路径，用 `.` 分隔。项目根目录在 `sys.path` 中，所以 `agents.installed.your_agent.agent` 可直接导入。
- **ClassName**: 模块中 Agent 类的名称。

示例：
```
agents.installed.example_echo_agent.agent:ExampleEchoAgent
```

系统通过 `importlib.import_module(module_path)` 导入模块，再 `getattr(module, class_name)` 获取类。

---

## Agent 类协议

### 基础要求

```python
from agents.base_agent import BaseAgent

class YourAgent(BaseAgent):
    AGENT_ID = "your_agent"         # 与 agent.json 的 id 一致
    DISPLAY_NAME = "你的 Agent"      # 中文显示名
    CAPABILITIES = ["cap_a"]        # 与 agent.json 的 capabilities 一致
    TASK_TYPES = ["task_a"]         # 与 agent.json 的 task_types 一致

    def run(self, task: dict) -> dict:
        """必须实现 — 执行任务，返回统一信封"""
        ...
```

### health() 方法（可选）

```python
def health(self) -> dict:
    """健康检查，返回 {"ok": true, ...}"""
    return {"ok": True, "agent": self.AGENT_ID, "status": "healthy"}
```

系统不强制要求此方法，但建议实现以便前端展示健康状态。

### execute() vs run()

- **`run(task)`** — 你实现的核心逻辑。接收 task dict，返回统一信封 dict。
- **`execute(task)`** — 由 `BaseAgent` 提供，自动包装 `run()`：计时、异常捕获、日志。**调度层调用此方法**，你不需要覆盖它。

```
调度层 → execute(task) → 自动计时 + 异常捕获 → run(task) → 你的逻辑
```

---

## 返回格式（统一信封）

`run()` 必须返回一个 dict，包含以下字段：

```python
{
    "ok": True,                    # 是否成功
    "agent": "your_agent",         # Agent ID
    "status": "completed",         # human-readable 状态
    "data": {...},                 # 核心产出（任意 dict）
    "error": None,                 # 失败时的错误信息
    "meta": {
        "task_id": "xxx",
        "duration_ms": 0,          # execute() 会自动填充
        ...
    }
}
```

### 快捷构造器

`BaseAgent` 提供两个快捷方法：

```python
# 成功
return self.ok(task_id="123", status="completed", data={"result": "..."})

# 失败
return self.fail(task_id="123", error="缺少参数")
```

### AgentRunResult 映射

调度层通过 `agent_executor.py` 将你的信封映射为 `AgentRunResult`：

| 信封字段 | AgentRunResult 字段 |
|----------|-------------------|
| `ok` | `ok` |
| `agent` | `agent_id` |
| `data` | `output` |
| `error` | `error` |
| `meta` | `metadata` |

---

## 安装目录说明

### 标准安装位置

```
agents/installed/your_agent/
```

系统自动扫描 `agents/installed/*/agent.json`，发现后注册到 Agent 列表。

### 启用/禁用

- `agent.json` 中 `enabled: true/false` 控制 manifest 级别的启用
- 运行时通过 `POST /agents/your_agent/enable` 或 `/disable` 动态切换
- 配置持久化到 `user_data/agent_registry/enabled_agents.json`

### 调用示例

```bash
# 1. 发现所有 Agent
curl http://localhost:8000/agents/discovered

# 2. 启用 Agent
curl -X POST http://localhost:8000/agents/your_agent/enable

# 3. 执行任务
curl -X POST http://localhost:8000/agents/your_agent/execute \
  -H "Content-Type: application/json" \
  -d '{"goal": "你的任务描述", "task_type": "your_task_type"}'

# 4. 协作计划
curl -X POST http://localhost:8000/collaboration/plan \
  -H "Content-Type: application/json" \
  -d '{
    "goal": "完成一个多步骤任务",
    "steps": [
      {"name": "Step 1", "task_type": "echo", "required_capability": "echo"}
    ]
  }'
```

---

## 完整示例

参见 `agents/installed/example_echo_agent/` — 一个最小可运行的 Agent，包含 echo 和 copywriting 两种能力。
