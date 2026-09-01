# AI Company OS 能力运行时架构设计

**日期：** 2026-08-26
**状态：** 已确认，进入实施计划阶段
**适用范围：** 本机能力发现、Agent 编排、LLM Provider 配置、真实执行、授权与运行态回执

## 1. 背景与问题

当前项目可以启动，也能检测部分本机服务，但存在多套互不一致的发现和执行链：`/ai/scan` 能发现运行中的 OpenClaw，而 `/capabilities` 和 Agent 控制台不能稳定展示它；页面显示的 OpenClaw 也可能最终调用项目内置 Python Agent。Hermes Desktop/Runtime 正在运行，但 Boss 执行器只寻找 PATH 中名为 `hermes` 的 CLI。DeepSeek 的模型保存、Provider 切换和连接测试被合并处理，默认地址又没有统一 `/v1` 规范。

这些问题属于运行时基础架构问题，而不是单个页面问题。本设计的目标是建立一个唯一能力事实源，明确 Agent、LLM、工具和服务的边界，并让发现结果、路由决策和真实执行共享同一个资源身份与适配器。

## 2. 目标

1. 任何页面和 API 查询到的本机能力都来自同一个能力注册中心。
2. 外部 Agent 优先执行，项目内置 Agent 只承担业务编排和明确声明的安全回退。
3. Hermes、OpenClaw、项目内置 Agent、LLM Provider 和普通工具在身份、状态和执行权限上完全分离。
4. “发现”“在线”“配置”“已授权”“可执行”“执行成功”必须是可区分的状态。
5. DeepSeek 等 Provider 的保存、连接测试、切换和 Agent 绑定必须独立。
6. 所有执行都返回标准化回执，包含实际资源、适配器、模型、授权和回退信息。
7. 安全边界默认为拒绝，不能因为进程在线或配置存在而自动获得执行权限。

## 3. 非目标与边界

- 不做默认全盘递归扫描；发现范围限于 PATH 命令、已知应用路径、用户级配置、项目 Agent manifest、明确的 localhost 健康端点和运行进程证据。
- 不把普通工具注册为 Agent。
- 不把 LLM Provider 伪装成 Agent；Provider 只提供推理能力。
- 不把项目内置 Agent 伪装成本机已安装的外部产品。
- 不自动读取、返回或记录 API Key、Cookie、密码和会话 Token。
- 不自动执行浏览器发布、付款、发消息等不可逆操作。
- 不因为 Hermes 只有 Dashboard 或 OpenClaw 只有控制页面就推断其具备任务执行 API。

## 4. 统一资源模型

能力注册中心是系统唯一事实源。现有 `/ai` 注册中心作为收敛基础；`/capabilities`、`/agent-console/discovered` 等旧接口保留兼容性，但只能读取注册中心并生成视图，不能再自行扫描。

### 4.1 资源分类

| kind | 含义 | 示例 | 是否可直接执行 |
| --- | --- | --- | --- |
| `agent` | 任务执行者 | OpenClaw、Hermes、Claude Code、项目 Research Agent | 只有存在适配器且状态 ready |
| `llm_provider` | 模型推理提供者 | DeepSeek、Claude、OpenAI、Ollama、CC Switch | 通过 Provider 适配器，不作为 Agent 路由目标 |
| `tool` | 基础工具或客户端 | Python、Node、Git、Docker、Safari | 只能作为工具依赖 |
| `service` | 本地运行时或服务端点 | OpenClaw Gateway、Hermes Runtime、Ollama 服务 | 由 Agent 或 Provider 适配器使用 |

### 4.2 资源记录

每个资源至少包含以下字段：

```text
resource_id          稳定的系统身份
name                 展示名称
kind                 agent / llm_provider / tool / service
origin               external_runtime / cli / local_service / project / environment
status               not_detected / detected / online / configured / ready /
                     execution_unavailable / blocked / degraded / failed
capabilities         能力标识集合
endpoint             脱敏后的服务地址
executable           可执行路径（如适用）
adapter_id           可执行适配器；没有则为 null
enabled              是否允许进入路由
authorization        not_required / required / approved / denied
llm_binding          provider、model、verified、binding_source
evidence              进程、端口、版本、探测方式和时间
last_error_code      稳定错误码，不包含凭据
scanned_at           本次探测时间
```

以下关系必须成立：`online` 不等于 `ready`；`configured` 不等于 `verified`；`detected` 不等于有适配器；没有适配器的资源不能被任务路由选择。

## 5. 发现与健康检查

注册中心通过职责单一的探测器收集事实：

- `CliProbe`：查找命令、版本和退出状态，不执行用户任务。
- `LocalServiceProbe`：探测 localhost 健康端点、模型列表和协议特征。
- `DesktopRuntimeProbe`：识别没有标准 PATH 命令但有运行进程和本地端口的应用，例如 Hermes Desktop/Runtime。
- `ProjectAgentProbe`：读取项目 Agent manifest，验证模块加载和协议元数据。
- `ProviderProbe`：只检查配置存在性；远程连接必须由用户主动测试。

探测结果必须保留证据和时间戳。扫描 TTL 可以用于减少重复探测，但不能把历史成功结果冒充当前在线状态。对于服务在线但没有可调用任务接口的资源，状态应为 `online` + `execution_unavailable`，而不是 `ready`。

### 5.1 当前机器的特殊处理

- OpenClaw Gateway：检测 `127.0.0.1:18789`、进程和控制页面；只有确认任务调用协议并完成适配器健康检查后才可进入 `ready`。
- Hermes：检测 Desktop 进程和 `127.0.0.1:9120` Runtime；不能把 `hermes` PATH 命令假设为存在。若 Runtime 没有稳定任务 API，必须明确显示不可执行。
- Ollama：服务在线、模型列表非空且存在聊天模型时才标记 Provider/Agent 适配器可用；嵌入模型不能被误判为聊天模型。
- 浏览器：浏览器可执行文件存在只代表工具存在，不能代表浏览器自动化已授权。

## 6. 执行适配器与路由

所有可执行资源必须通过专用适配器。适配器声明：`adapter_id`、绑定的 `resource_id`、支持的任务类型、是否需要 LLM、是否需要授权、输入输出协议、超时策略和稳定失败码。

首批适配器边界：

- `openclaw_gateway_adapter`：只调用外部 OpenClaw Gateway。
- `hermes_runtime_adapter`：只调用 Hermes Runtime 的已确认任务 API；没有任务 API 时不创建虚假执行路径。
- `project_agent_adapter`：调用项目内置 Agent，资源来源必须标记为 `project`。
- `provider_adapter`：调用 LLM Provider，不将其注册为 Agent。
- `tool_adapter`：为受控工具提供有限能力，不直接承担 Agent 规划身份。

路由规则：

1. 只从 `status=ready`、`enabled=true`、能力匹配且授权条件满足的资源中选择。
2. 同一能力优先选择来源为 `external_runtime` 或 `cli` 的真实外部 Agent。
3. 外部 Agent 不可执行时，才使用明确声明支持该任务的项目内置回退。
4. 回退必须返回 `fallback_used=true`、原始目标资源和失败原因。
5. 没有适配器、仅被发现、仅在线或仅配置的资源不能被任务拆解器选择。

## 7. 标准执行回执

每次执行返回统一结构：

```text
execution_id
resource_id
resource_kind
adapter_id
status                 succeeded / failed / blocked / unsupported
provider
model
fallback_used
authorization
started_at
finished_at
output
error_code
evidence
```

执行失败必须区分：未发现、服务离线、没有适配器、未授权、缺少模型、Provider 未配置、连接失败、超时和执行错误。错误消息不得包含凭据或完整远程响应中的敏感字段。

## 8. LLM Provider 配置

Provider 配置、连接测试和当前主脑切换是三个独立操作：

1. **保存配置**：只更新模型、地址或凭据，不改变当前 Provider；只修改模型或地址时不能因为缺少 Key 而被阻挡。
2. **测试连接**：用户主动触发；缺少 Key 时不发起请求，只返回 `credential_missing`；成功后记录 `verified` 和测试时间。
3. **切换 Provider**：用户明确触发；目标 Provider 未配置或未验证时阻止切换，避免系统处于表面可用状态。

Provider 状态至少区分：`missing`、`present`、`verified`、`invalid`、`offline`、`error`。Agent 的 `llm_binding.verified` 只有在对应 Provider 连接测试成功或本地模型探测满足协议时才为 true。

### 8.1 DeepSeek URL 规范

所有 OpenAI 兼容 Provider 经过统一规范化：

```text
https://api.deepseek.com
https://api.deepseek.com/
https://api.deepseek.com/v1
        ↓
https://api.deepseek.com/v1
        ↓
https://api.deepseek.com/v1/chat/completions
```

不同模块不得自行拼接 API 路径。模型保存和 Provider 切换不得共用一个隐式请求。

### 8.2 凭据边界

- API 响应只返回 `has_key`、凭据状态和错误码。
- 空 Key 不覆盖已有 Key，清除凭据必须是显式动作。
- 运行配置与项目代码、项目数据库分离，默认写入用户级运行目录；环境变量可作为最高优先级覆盖。
- Key、Cookie、Token 不进入日志、测试快照、Git 或前端状态。

## 9. 授权与安全边界

普通对话不需要额外授权。读取本地文件按路径范围授权；浏览器打开、截图、抓取和表单操作需要单次或任务级授权；发布、付款、发消息等不可逆动作始终需要人工确认。

授权状态不能由进程在线或 Provider 已配置自动推导。未授权任务返回 `blocked` 和稳定的 `approval_required` 错误码，不执行任何副作用。

## 10. 前端契约

前端所有能力视图都读取注册中心投影，至少展示：资源类型、来源、当前状态、执行适配器、授权状态、绑定 Provider/模型、最后探测时间和失败原因。

设置页拆成三个明确动作：

```text
保存配置 → 测试连接 → 设为当前主脑
```

控制台不得把“在线”显示成“可执行”，也不得把项目内置 Agent 显示成外部产品。执行结果必须展示实际 `resource_id`、`adapter_id` 和是否发生回退。

## 11. 实施阶段

### 阶段一：契约冻结

定义统一资源状态、资源记录、执行回执和错误码；为现有兼容接口建立契约测试。

### 阶段二：发现体系收敛

以 `/ai` 注册中心为唯一事实源，将旧扫描器改为只读视图；增加 Hermes Runtime 探测和 OpenClaw 来源区分。

### 阶段三：真实适配器

实现 OpenClaw Gateway 适配器；调查并实现 Hermes Runtime 适配器，若协议不足则保持 `execution_unavailable`；接入项目内置 Agent 的显式回退适配器。

### 阶段四：Provider 配置

分离保存、测试和切换；统一 URL 规范化；迁移运行配置到用户级目录；增加 DeepSeek、Claude、Ollama 的 mock transport 和真实测试入口。

### 阶段五：前端收敛

改为读取统一投影，展示来源、状态、授权、LLM 绑定和回退信息；移除“在线即可用”的旧逻辑。

### 阶段六：回归与主线整理

修复现有失败测试，隔离平台专属测试，完成前端构建、后端全量测试、运行态扫描和一次安全的本地执行验收，再提交和合并主线。

## 12. 验收标准

1. `/ai/scan`、`/capabilities`、`/agent-console/discovered` 资源集合一致，仅允许视图字段不同。
2. Hermes、OpenClaw、内置 Agent、LLM Provider 和普通工具分类正确。
3. OpenClaw 只有在真实 Gateway 适配器通过检查后才显示 `ready`。
4. Hermes 只有在实际 Runtime 任务 API 可调用时才显示 `ready`。
5. 路由不会选择无适配器或未授权资源。
6. 所有回退都包含 `fallback_used=true` 和原始失败原因。
7. DeepSeek 只改模型/地址时不会被 API Key 阻挡。
8. DeepSeek 请求统一使用 `/v1/chat/completions`。
9. 未验证 Provider 不显示为真实可用。
10. 凭据不出现在 API、日志、前端响应或 Git。
11. Mac 平台全量后端测试通过，Windows 专属测试不影响 Mac 基线。
12. 前端构建、健康检查、实际扫描和至少一次受控本地 Agent 执行均通过。

## 13. 当前基线与风险

截至本设计确认时：前端构建通过，本地健康检查通过，后端全量测试为 `1603 passed / 15 failed / 7 skipped`。OpenClaw Gateway 在本机可被 `/ai/scan` 探测，Hermes Desktop/Runtime 在本机运行，但 Hermes CLI 入口不可用；DeepSeek 当前未配置凭据，Claude 仅确认存在配置，尚未完成真实连接验证。

当前工作区存在上一轮未提交修改。本设计文档不覆盖、不回滚这些修改；实施阶段必须先建立变更基线，避免把工作区状态误认为稳定主线。
