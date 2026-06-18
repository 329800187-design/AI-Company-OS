# AI Company OS · 终极架构设计文档

> **版本 1.0 · 2026-06-14**
>
> 本文档定义 AI Company OS 的最终形态——一个可移植、可换脑、可操控本地软件的
> 多智能体协作操作系统。所有后续开发以此文档为准则。

---

## 1. 核心愿景

### 一句话定义

> **一个拷贝即用的 AI 操作系统——插上 API Key 就能工作，换一个 AI 模型就能换脑，
> 能打开桌面软件干活，能协同多个 AI 一起完成任务。**

### 三大核心能力

| 能力 | 说明 | 用户价值 |
|------|------|----------|
| 🧠 **可换脑** | 主脑 AI 可随时切换：DeepSeek / Claude / OpenAI / Ollama / LM Studio / llama.cpp | 不绑定任何厂商，用哪个由你决定 |
| 🤖 **Agent 协作网** | 主脑自动发现并调度本地其他 AI 服务，组成协作网络 | 多个 AI 各司其职，1+1>2 |
| 🖥️ **操控本地软件** | 能打开桌面程序、操作浏览器、执行脚本、读写文件 | AI 不只是聊天，能真正帮你干活 |

### 设计原则

```
PORTABLE  →  单文件夹，拷贝即用，无需安装
SWAPPABLE →  主脑模型可热切换，运行时改配置立即生效
AUTO-DISCOVER → 自动扫描本机 AI 服务，无需手动配置
GRACEFUL-DEGRADE → 某个 AI 不可用时自动降级，不影响整体运行
EXTENDABLE → 新 Agent 插件式添加，不修改核心代码
```

---

## 2. 终极架构全景

```
┌─────────────────────────────────────────────────────────────────┐
│                        AI Company OS                            │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  ┌─────────────── USER INTERFACE ───────────────┐               │
│  │  Web UI (localhost:8000)  │  CLI  │  API     │               │
│  └──────────────────────┬───────────────────────┘               │
│                         │                                       │
│  ┌──────────────────────▼───────────────────────┐               │
│  │           🧠 MAIN BRAIN (可换脑核心)           │               │
│  │  ┌─────────┐ ┌─────────┐ ┌─────────┐         │               │
│  │  │DeepSeek │ │ Claude  │ │ Ollama  │  ...    │               │
│  │  └────┬────┘ └────┬────┘ └────┬────┘         │               │
│  │       └───────────┼───────────┘               │               │
│  │                   ▼                           │               │
│  │         Provider Router (自动路由)              │               │
│  └──────────────────────┬───────────────────────┘               │
│                         │                                       │
│  ┌──────────────────────▼───────────────────────┐               │
│  │        🤖 AGENT MESH (智能体协作网)            │               │
│  │                                              │               │
│  │  ┌────────┐ ┌────────┐ ┌────────┐ ┌───────┐ │               │
│  │  │ CEO    │ │ Codex  │ │OpenClaw│ │System │ │               │
│  │  │ 拆解员  │ │ 代码员  │ │ 浏览器  │ │ 系统员 │ │               │
│  │  └────────┘ └────────┘ └────────┘ └───────┘ │               │
│  │  ┌────────┐ ┌────────┐ ┌────────┐ ┌───────┐ │               │
│  │  │  QA    │ │  CTO   │ │ 本地AI │ │ 自定义 │ │               │
│  │  │ 验收员  │ │ 架构师  │ │ 服务   │ │ Agent │ │               │
│  │  └────────┘ └────────┘ └────────┘ └───────┘ │               │
│  └──────────────────────┬───────────────────────┘               │
│                         │                                       │
│  ┌──────────────────────▼───────────────────────┐               │
│  │       🖥️ LOCAL CONTROL (本地软件操控层)        │               │
│  │                                              │               │
│  │  ┌──────────┐ ┌────────┐ ┌───────────────┐  │               │
│  │  │ 桌面应用   │ │ 浏览器  │ │ 终端/Shell     │  │               │
│  │  │ (Excel,   │ │(Chrome,│ │ (cmd, bash,   │  │               │
│  │  │  VS Code, │ │ Edge,  │ │  PowerShell)  │  │               │
│  │  │  Photoshop│ │Firefox)│ │               │  │               │
│  │  └──────────┘ └────────┘ └───────────────┘  │               │
│  │  ┌──────────┐ ┌────────┐ ┌───────────────┐  │               │
│  │  │ 文件系统   │ │ API调用 │ │ 本地AI推理     │  │               │
│  │  │ (读/写)   │ │(REST)  │ │ (Ollama等)    │  │               │
│  │  └──────────┘ └────────┘ └───────────────┘  │               │
│  └──────────────────────────────────────────────┘               │
│                                                                 │
│  ┌──────────────────────────────────────────────┐               │
│  │         💾 STORAGE (持久化层)                  │               │
│  │  SQLite (任务/会话/用量/记忆) + 文件系统          │               │
│  └──────────────────────────────────────────────┘               │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

---

## 3. 主脑可换架构 (Swappable Main Brain)

### 3.1 设计目标

用户可以在运行时切换主脑 AI，无需重启系统：

```python
# 方式一：Web UI 设置页面
#   选择 Provider → 填入 Key → 保存 → 立即生效

# 方式二：.env 文件
#   AI_PROVIDER=deepseek  →  切换到 DeepSeek
#   AI_PROVIDER=claude    →  切换到 Claude
#   AI_PROVIDER=ollama    →  切换到本地 Ollama

# 方式三：API 调用
#   POST /config/save  {"provider": "ollama", "model": "qwen2.5:7b"}
```

### 3.2 支持的 Provider 矩阵

| Provider | 类型 | 需要 Key | 需要安装 | 适用场景 |
|----------|------|----------|----------|----------|
| **DeepSeek** | 云端 | ✅ API Key | 无 | 日常主力，性价比最高 |
| **Claude** | 云端 | ✅ API Key | 无 | 复杂推理、长任务 |
| **OpenAI** | 云端 | ✅ API Key | 无 | 生态兼容 |
| **Ollama** | 本地 | 无 | Ollama 桌面版 | 离线使用、隐私敏感 |
| **LM Studio** | 本地 | 无 | LM Studio | 本地 GUI 管理模型 |
| **llama.cpp** | 本地 | 无 | llama.cpp | 极简本地推理 |
| **CC Switch** | 代理 | 无 | CC Switch | 统一代理网关 |

### 3.3 Provider 自动检测

```python
class ProviderDetector:
    """启动时自动扫描可用 AI 服务"""

    def scan_all(self) -> dict:
        return {
            "ollama":       self._check_port(11434),      # Ollama 默认端口
            "lm_studio":    self._check_port(1234),        # LM Studio 默认端口
            "llama_cpp":    self._check_port(8080),        # llama.cpp server
            "cc_switch":    self._check_port(15721),       # CC Switch
            "deepseek":     self._check_env("DEEPSEEK_API_KEY"),
            "claude":       self._check_env("CLAUDE_API_KEY"),
            "openai":       self._check_env("OPENAI_API_KEY"),
        }
```

### 3.4 主脑切换流程

```
用户切换 Provider
    │
    ▼
ProviderRouter.validate(provider, key)
    │── 测试连接（简单 ping 请求）
    │── 验证通过 → 更新全局 AI_PROVIDER
    │── 验证失败 → 返回错误 + 保持当前 Provider
    │
    ▼
所有后续 AI 调用自动路由到新 Provider
    │── CEO 拆解用新模型
    │── QA 验收用新模型
    │── Commander 决策用新模型
```

---

## 4. 智能体协作网 (Agent Mesh)

### 4.1 Agent 发现与注册

```
┌────────────────────────────────────────────────────────┐
│                  AI Registry 2.0                       │
│                                                       │
│  ┌─────────────┐   ┌──────────────┐                   │
│  │ Local Scan  │   │ Manual Reg   │                   │
│  │ (自动扫描)   │   │ (手动注册)    │                   │
│  │             │   │              │                   │
│  │ • Ollama    │   │ • 自定义端口  │                   │
│  │ • CC Switch │   │ • 远程 Agent │                   │
│  │ • LM Studio │   │ • MCP Server │                   │
│  │ • Codex CLI │   │              │                   │
│  └──────┬──────┘   └──────┬───────┘                   │
│         └────────┬────────┘                           │
│                  ▼                                     │
│         ┌──────────────┐                              │
│         │ Agent Catalog│  {name, capability, endpoint} │
│         └──────┬───────┘                              │
│                ▼                                       │
│         ┌──────────────┐                              │
│         │ Capability   │  "code"→Codex,                │
│         │ Router       │  "browser"→OpenClaw,          │
│         │ (能力路由)    │  "system"→System, ...         │
│         └──────────────┘                              │
└────────────────────────────────────────────────────────┘
```

### 4.2 Agent 标准接口

所有 Agent 必须实现统一接口，确保可互换：

```python
class AgentProtocol:
    """每个 Agent 必须实现的协议"""

    name: str           # "codex", "openclaw", "system", ...
    capabilities: list  # ["code_execution"], ["browser"], ...

    async def run(self, task: Task) -> TaskResult:
        """执行任务，返回结果"""
        ...

    def health_check(self) -> bool:
        """快速自检，确认 Agent 可用"""
        ...

    @classmethod
    def detect(cls) -> bool:
        """类方法：自动检测本机是否支持此 Agent"""
        ...
```

### 4.3 Agent 间通信

```
Commander (主脑)
    │
    ├── "拆解这个目标" → CEO Agent (用当前主脑模型)
    │   └── 返回: [task1, task2, task3]
    │
    ├── "执行 task1" → Codex Agent (Python 沙箱)
    │   └── 返回: {stdout, stderr, files}
    │
    ├── "执行 task2" → OpenClaw Agent (浏览器)
    │   └── 返回: {screenshot, extracted_data}
    │
    ├── "执行 task3" → System Agent (系统命令)
    │   └── 返回: {stdout, files}
    │
    └── "验收所有结果" → QA Agent
        └── 返回: {score, problems}
```

### 4.4 Agent 降级链

当某个 Agent 不可用时，自动寻找替代：

```
Codex 不可用
    │── System Agent 替代（直接执行 Python）
    │── CC Switch 替代（通过代理执行）
    │── 云端 API 替代（调用外部沙箱）

OpenClaw 不可用
    │── System Agent + curl/wget 替代
    │── 提示用户安装 Playwright
```

---

## 5. 本地软件操控层 (Local Control)

### 5.1 能力矩阵

| 能力 | 实现方式 | Windows | macOS | Linux |
|------|----------|---------|-------|-------|
| 打开桌面应用 | `subprocess` / `os.startfile` | ✅ | ✅ | ✅ |
| 操控浏览器 | Playwright (Chromium) | ✅ | ✅ | ✅ |
| 执行终端命令 | `subprocess` (cmd/bash/pwsh) | ✅ | ✅ | ✅ |
| 文件读写 | Python 标准库 | ✅ | ✅ | ✅ |
| 截图/录屏 | Playwright + pyautogui | ✅ | ✅ | ✅ |
| 键盘/鼠标模拟 | pyautogui (可选) | ✅ | ✅ | ✅ |
| 窗口管理 | pygetwindow (Windows) | ✅ | ❌ | ❌ |
| 进程管理 | psutil | ✅ | ✅ | ✅ |
| 系统信息 | platform + psutil | ✅ | ✅ | ✅ |
| 通知推送 | plyer / system notify | ✅ | ✅ | ✅ |

### 5.2 安全沙箱

```
┌─────────────────────────────────────────┐
│          SECURITY SANDBOX               │
│                                         │
│  ┌─────────────┐  ┌──────────────────┐  │
│  │ 命令白名单    │  │ 路径沙箱         │  │
│  │ (允许的cmd)  │  │ (限制访问目录)    │  │
│  └─────────────┘  └──────────────────┘  │
│  ┌─────────────┐  ┌──────────────────┐  │
│  │ 超时保护     │  │ 确认门禁         │  │
│  │ (30s timeout)│  │ (危险操作需确认)  │  │
│  └─────────────┘  └──────────────────┘  │
│  ┌─────────────┐  ┌──────────────────┐  │
│  │ 输出截断     │  │ 网络白名单        │  │
│  │ (max 100KB) │  │ (允许访问的URL)   │  │
│  └─────────────┘  └──────────────────┘  │
└─────────────────────────────────────────┘
```

### 5.3 本地软件调用示例

```python
# System Agent 能做的事：

# 1. 打开 Excel 并操作
system.run({
    "action": "run_program",
    "program": "excel",
    "args": ["report.xlsx"]
})

# 2. 用 VS Code 打开项目
system.run({
    "action": "run_program",
    "program": "code",
    "args": ["E:/AI-company-os"]
})

# 3. 执行系统命令
system.run({
    "action": "exec",
    "command": "dir E:\\AI-company-os /s",
    "shell": "cmd"
})

# 4. 发送桌面通知
system.run({
    "action": "notify",
    "title": "任务完成",
    "message": "CEO 已将目标拆解为 5 个子任务"
})
```

---

## 6. 可移植性设计 (Portability)

### 6.1 目标

> **拷贝整个文件夹到任何 Windows 电脑，双击 start.bat 就能跑。**

### 6.2 依赖策略

```
第一层：零依赖（Python 标准库）
    ├── SQLite (内置)
    ├── http.client / urllib (内置)
    ├── subprocess / os / pathlib (内置)
    └── tkinter (内置，可选 GUI)

第二层：轻量依赖（pip install，自动处理）
    ├── fastapi + uvicorn (Web 服务)
    ├── httpx (HTTP 客户端)
    ├── pydantic (数据验证)
    └── python-dotenv (配置)

第三层：可选依赖（按需安装，失败不影响核心功能）
    ├── playwright (浏览器自动化)
    ├── psutil (进程管理)
    ├── pyautogui (桌面自动化)
    └── pillow (图片处理)
```

### 6.3 目录结构

```
AI-Company-OS/
├── start.bat              ← 双击启动（Windows）
├── start.sh               ← 终端启动（Linux/macOS）
├── .env.example           ← 配置模板
├── README.md
│
├── core/                  ← 核心（零外部依赖）
│   ├── config.py          #   配置中心
│   ├── provider.py        #   Provider 路由器
│   └── sandbox.py         #   安全沙箱
│
├── agents/                ← 智能体（每个独立可拔插）
│   ├── base.py            #   Agent 基类（统一接口）
│   ├── ceo/               #   目标拆解
│   ├── codex/             #   代码执行
│   ├── openclaw/          #   浏览器
│   ├── system/            #   系统操作
│   ├── qa/                #   质量验收
│   └── cto/               #   架构设计（Phase 1）
│
├── server/                ← Web 服务
│   ├── app.py             #   FastAPI 入口
│   ├── routers/           #   API 路由
│   └── middleware/        #   中间件
│
├── ui/                    ← 前端
│   └── index.html         #   单文件 Web UI
│
├── storage/               ← 数据持久化
│   └── company_os.db      #   SQLite 数据库
│
├── tools/                  ← 工具脚本
│   ├── install.py         #   自动安装依赖
│   └── detect.py          #   检测本机环境
│
└── docs/                  ← 文档
    ├── VISION.md          #   本文档
    └── API.md             #   API 文档
```

### 6.4 启动流程

```
双击 start.bat
    │
    ├── 1. 检测 Python (≥3.10)
    │   └── 未安装 → 提示下载链接
    │
    ├── 2. 创建虚拟环境 (.venv/)
    │   └── 已存在 → 跳过
    │
    ├── 3. 安装依赖 (pip install -r requirements.txt)
    │   └── 可选依赖安装失败 → 跳过（不影响启动）
    │
    ├── 4. 检测 .env 文件
    │   └── 不存在 → 从 .env.example 复制
    │
    ├── 5. 自动扫描本机 AI 服务
    │   └── 打印可用服务列表
    │
    ├── 6. 启动服务
    │   └── http://localhost:8000
    │
    └── 7. 自动打开浏览器
```

---

## 7. 分阶段实施路线图

### Phase 0 ✅ 已完成
- [x] FastAPI 基础服务
- [x] 5 个基础 Agent（CEO/Codex/OpenClaw/QA/System）
- [x] Commander 编排引擎
- [x] AI Registry 自动发现
- [x] SQLite 持久化
- [x] Docker 部署
- [x] Web UI

### Phase 1 — 基础稳固 (当前)
- [ ] 修完所有已知 bug
- [ ] 统一 Agent 基类接口
- [ ] Provider Router 可换脑
- [ ] 用量统计持久化
- [ ] TaskService 读写一致
- [ ] OpenClaw 浏览器池化
- [ ] CTO Agent（架构设计）

### Phase 2 — 本地操控
- [ ] System Agent 增强（打开桌面软件、窗口管理、通知）
- [ ] OpenClaw 增强（表单提交、文件下载、Cookie 管理）
- [ ] 安全沙箱加固（目录隔离、命令白名单 UI 配置）
- [ ] 本地 AI 缓存（Ollama/LM Studio 扫描结果缓存）

### Phase 3 — 智能体协作网
- [ ] Agent 协议标准化
- [ ] Agent 热插拔（运行时加载/卸载）
- [ ] Agent 间消息总线
- [ ] 多 Agent 并行执行优化
- [ ] 自定义 Agent 模板

### Phase 4 — 可移植性
- [ ] 零依赖核心（纯标准库 fallback）
- [ ] 一键安装脚本（Windows/macOS/Linux）
- [ ] 便携版打包（zip 分发包）
- [ ] 环境自检工具
- [ ] 离线模式（纯本地 AI）

### Phase 5 — 产品化
- [ ] 多用户支持
- [ ] 插件市场
- [ ] 工作流可视化编辑器
- [ ] 移动端适配
- [ ] 远程 Agent 调用

---

## 8. 多 AI 协作测试策略

### 8.1 测试矩阵

| 场景 | 主脑 | 配合 Agent | 验证方式 |
|------|------|-----------|----------|
| 代码开发 | Claude Code | Codex (执行) + QA (验收) | 功能测试通过 |
| 网页抓取 | DeepSeek | OpenClaw (浏览器) + CEO (拆解) | 数据完整性 |
| 本地操作 | Ollama | System (系统命令) | 命令执行成功 |
| 混合协作 | DeepSeek | Claude (审查) + Codex (执行) | 端到端通过 |

### 8.2 与 Claude Code / OpenClaw / Codex 配合使用

```
你的使用场景：

Claude Code (我) → 写代码、架构设计、debug
    │              (当前正在做的事)
    │
    ├── OpenClaw → 浏览器操作、网页测试
    │              (Playwright 自动化)
    │
    ├── Codex → 代码执行、测试运行
    │          (Python 沙箱)
    │
    └── AI Company OS (本项目) → 集成以上所有
         │                      提供 Web UI + API
         │
         └── 目标：让非技术用户也能通过
             Web UI 驱动整个 AI 协作网
```

### 8.3 开发时的测试流程

```bash
# 1. Claude Code 帮我开发新功能
"帮我给 System Agent 添加打开桌面软件的能力"

# 2. 开发完成后，启动 AI Company OS
cd E:/AI-company-os
python -m uvicorn backend.app:app --reload

# 3. 用 OpenClaw 测试浏览器功能
curl -X POST http://localhost:8000/agents/openclaw/run \
  -H "Content-Type: application/json" \
  -d '{"action":"screenshot","url":"https://example.com"}'

# 4. 用 Codex 测试代码执行
curl -X POST http://localhost:8000/agents/codex/run \
  -H "Content-Type: application/json" \
  -d '{"action":"code_execute","code":"print(sum(range(100)))"}'

# 5. 端到端测试：CEO 拆解 → 执行 → QA 验收
curl -X POST http://localhost:8000/commander/run-async \
  -H "Content-Type: application/json" \
  -d '{"goal":"分析 example.com 的技术栈并生成报告"}'
```

---

## 9. 关键设计决策记录

| 决策 | 选择 | 原因 |
|------|------|------|
| **数据库** | SQLite + WAL | 零安装、单文件、够用 |
| **Web 框架** | FastAPI | 异步支持、自动文档、生态好 |
| **前端** | 单文件 HTML | 零构建、易部署、易修改 |
| **Agent 通信** | 直接函数调用 | 简单可靠，后续可升级为消息队列 |
| **主脑切换** | 全局变量 + 热重载 | 简单有效，不需要重启 |
| **安全模型** | 白名单 + 确认门禁 | 默认拒绝，显式允许 |

---

## 10. 附录：与其他工具的关系

| 工具 | 在生态中的位置 | 如何配合 |
|------|--------------|----------|
| **Claude Code** | 开发助手 | 写 AI Company OS 的代码、审查、架构 |
| **OpenClaw** | 浏览器 Agent | AI Company OS 的浏览器操作模块 |
| **Codex** | 代码执行 Agent | AI Company OS 的代码沙箱模块 |
| **Ollama** | 本地 AI 推理 | AI Company OS 的离线主脑选项 |
| **CC Switch** | AI 代理网关 | 统一管理和路由所有 AI API 调用 |

---

> **下一步行动：** 按 Phase 1 列表逐项实施。每个模块升级时以此文档为准则。
