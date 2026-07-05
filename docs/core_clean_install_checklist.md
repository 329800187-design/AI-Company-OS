# Core Clean Install Checklist

AI Company OS Core 分发版 — 最小安装清单

## 前置条件

- Python 3.10+
- pip
- git

## 安装步骤

### 1. 克隆仓库

```bash
git clone https://github.com/your-org/ai-company-os.git
cd ai-company-os
```

### 2. 创建虚拟环境

```bash
python -m venv .venv
```

### 3. 激活虚拟环境

**Windows:**
```bash
.venv\Scripts\activate
```

**macOS/Linux:**
```bash
source .venv/bin/activate
```

### 4. 安装依赖

```bash
pip install -r requirements-core.txt
```

### 5. 启动服务

```bash
uvicorn backend.core_app:app --reload --port 8000
```

## 验证步骤

### 1. 健康检查

```bash
curl http://localhost:8000/health
```

预期响应：
```json
{
  "status": "ok",
  "mode": "core",
  "version": "x.x.x",
  "timestamp": "2026-07-02T..."
}
```

### 2. 查询已发现的 Agent

```bash
curl http://localhost:8000/agents/discovered
```

预期响应：
```json
{
  "agents": [...],
  "total": N,
  "enabled_count": M
}
```

### 3. 执行示例 Agent

```bash
curl -X POST http://localhost:8000/agents/example_echo/execute \
  -H "Content-Type: application/json" \
  -d '{"task": "Hello World"}'
```

### 4. 构建协同计划

```bash
curl -X POST http://localhost:8000/collaboration/plan \
  -H "Content-Type: application/json" \
  -d '{
    "goal": "测试协同计划",
    "steps": [
      {
        "name": "步骤1",
        "task_type": "copywriting",
        "required_capability": "copywriting"
      }
    ]
  }'
```

### 5. 运行治理任务

```bash
curl -X POST http://localhost:8000/governance/run \
  -H "Content-Type: application/json" \
  -d '{
    "goal": "帮我为手工耳环生成小红书种草文案",
    "platform": "xiaohongshu",
    "execute": false
  }'
```

## Core 模块说明

| 模块 | 说明 |
|------|------|
| `/health` | 健康检查端点 |
| `/governance/*` | 框架约束层 API |
| `/agents/*` | Agent 发现/启用/禁用/执行 |
| `/collaboration/*` | 多智能体协作计划 |
| `/minidelivery/*` | 最小交付闭环 |

## 不包含的模块

| 模块 | 说明 |
|------|------|
| `/boss/*` | Boss 管理（已弃用） |
| `/workflows/*` | 工作流引擎（已弃用） |
| `/pipeline/execute` | 旧流水线执行（已弃用） |
| `/commander/run` | Commander 执行（已弃用） |

## 故障排查

### 导入失败

如果遇到 `ModuleNotFoundError`，检查：

1. 虚拟环境已激活
2. 已安装 `requirements-core.txt` 中的所有依赖
3. 在项目根目录下运行命令

### 端口被占用

```bash
# Windows
netstat -ano | findstr :8000

# macOS/Linux
lsof -i :8000
```

使用其他端口：
```bash
uvicorn backend.core_app:app --reload --port 8001
```
