# Boss Command Center — Hermes Provider 配置指南

## 概述

Hermes Execution Provider 让 Boss Command Center 可以通过 Hermes CLI 调用本地 AI 能力，生成真实的电商任务输出（市场调研、竞品分析、上架物料包）。

## 启用方法

### 1. 环境变量配置

在 `.env` 文件或系统环境变量中设置：

```env
# 必须：将 execution provider 切换为 hermes
BOSS_EXECUTION_PROVIDER=hermes

# 可选：Hermes CLI 路径（默认 "hermes"，假设在 PATH 中）
HERMES_CLI_PATH=hermes

# 可选：执行超时秒数（默认 180）
HERMES_EXECUTION_TIMEOUT_SECONDS=180

# 可选：是否启用电商模式（默认 true，会提示 Hermes 使用 /ecommerce 技能）
HERMES_ECOMMERCE_MODE_ENABLED=true
```

### 2. 前提条件

- Hermes CLI 已安装并在 PATH 中
- 可通过 `hermes --version` 验证

```bash
hermes --version
```

## 验证方法

### 1. 快速验证（推荐）

运行 Hermes smoke test：

```bash
cd /e/AI-company-os
python -m pytest tests/test_boss_hermes_smoke.py -v
```

### 2. API 验证

启动后端后，通过 API 验证：

```bash
# 创建 mission
curl -X POST http://localhost:8000/boss/missions \
  -H "Content-Type: application/json" \
  -d '{"goal": "调研蓝牙耳机市场", "enabled_modules": ["market"], "auto_run": true}'

# 查看结果中的 structured_output.provider 字段是否为 "hermes"
```

### 3. Event Log 验证

执行后查看 event log，应包含以下事件：

| 事件类型 | 说明 |
|---------|------|
| `provider_selected` | 选择了 Hermes provider |
| `hermes_invoked` | 调用了 Hermes CLI |
| `hermes_response_parsed` | Hermes 响应解析成功 |
| `evidence_collected` | 收集到证据 |
| `structured_output_generated` | 生成标准化输出 |

如果 Hermes 失败，还会看到：

| 事件类型 | 说明 |
|---------|------|
| `hermes_failed` | Hermes 执行失败 |
| `provider_fallback` | 已 fallback 到 local_heuristic |

## 工作原理

### Prompt 构建

HermesExecutionProvider 会构建结构化 prompt，要求 Hermes：

1. 使用 `/ecommerce` 技能或 ecommerce 相关技能
2. 优先使用 `sourcing-price-bridge` / `ecommerce-bridge` 获取真实数据
3. 可使用 browser 采集证据
4. 输出严格 JSON 格式
5. **不执行**发布、付款、发消息等不可逆操作

### JSON 输出格式

每个模块的 prompt 都要求 Hermes 返回严格 JSON：

```json
{
  "summary": "摘要（200-500字）",
  "evidence": [{"title": "来源标题", "url": "来源URL"}],
  "competitors": [{"name": "竞品名称", "price": "价格", "platform": "平台", "features": "核心卖点"}],
  "pricing": {"range": "价格区间", "avg": "平均价格"},
  "warnings": ["警告信息（如有）"]
}
```

### Fallback 机制

如果 Hermes 不可用或执行失败，会自动 fallback 到 `local_heuristic`（基于 LocalAgentRuntime）：

1. **CLI 不存在**：`shutil.which()` 返回 None
2. **执行超时**：超过 `HERMES_EXECUTION_TIMEOUT_SECONDS`
3. **JSON 解析失败**：Hermes 输出不是合法 JSON
4. **CLI 返回错误**：exit code != 0

Fallback 发生时，event log 会记录 `provider_fallback` 事件。

## 安全边界

### 允许的操作

- 市场调研（搜索、分析）
- 竞品分析（对比、定价）
- 上架物料包生成（文案、图片建议）
- 证据采集（browser 访问公开网页）

### 禁止的操作

- ❌ 发布商品
- ❌ 付款/交易
- ❌ 发送消息
- ❌ 修改账户设置
- ❌ 任何不可逆操作

Prompt 中明确要求 Hermes 不执行这些操作。如果 Hermes 返回了疑似发布/付款相关的输出，`warnings` 字段会包含警告。

## 配置项参考

| 环境变量 | 默认值 | 说明 |
|---------|-------|------|
| `BOSS_EXECUTION_PROVIDER` | `local_heuristic` | 执行 provider 选择 |
| `HERMES_CLI_PATH` | `hermes` | CLI 路径 |
| `HERMES_EXECUTION_TIMEOUT_SECONDS` | `180` | 超时秒数 |
| `HERMES_ECOMMERCE_MODE_ENABLED` | `true` | 是否启用电商模式 |

## 故障排查

### 问题：Hermes provider 不可用

```bash
# 检查 Hermes 是否安装
which hermes

# 检查环境变量
echo $BOSS_EXECUTION_PROVIDER
```

### 问题：执行超时

```bash
# 增加超时时间
export HERMES_EXECUTION_TIMEOUT_SECONDS=300
```

### 问题：JSON 解析失败

查看 event log 中的 `hermes_failed` 事件，检查 Hermes 输出内容。

## 相关文件

- `backend/services/boss_execution_providers.py` — Provider 抽象和实现
- `backend/services/boss_module_executors.py` — Executor 调用 Provider
- `backend/config.py` — 配置项
- `tests/test_boss_hermes_smoke.py` — Smoke test
- `tests/test_boss_command_center.py` — 单元测试
