# AI Company OS · 多智能体协作操作系统

**版本 1.5.0**

## 最新状态（2026-07-07）

### 第一阶段：业务部门 MVP 闭环 ✅ 已完成

五个业务页 + MiniDelivery 交付中心端到端闭环验收完成。

### 第二阶段：Boss Lite ✅ 已完成

> 一句话目标 → 5 个 Agent 并行执行（含 Handoff） → 可读作战报告 → 自动保存交付中心 → 历史工作台可查可复用

当前推荐入口：**http://localhost:5173/app?page=boss**

当前分支：`codex/current-progress-20260705`

Boss Lite 已完成能力：

- 一句话目标输入，支持 8 个常用作战模板一键填入
- 自动拆解为 5 个业务 Agent：research / marketing / image / data / website
- 5 个 Agent 并行执行（ThreadPoolExecutor，max_workers=5）
- **Agent Handoff v1 已完成**：research / data 上游洞察自动传递给 marketing / image / website
- 前端已可视化 handoff 状态：Summary Banner 显示 handoff flow，下游 Agent 卡片显示「已参考上游洞察」，详情页显示 handoff 来源
- 可读的 Boss 作战报告（Markdown 格式，含各部门结论和 Boss 建议）
- 自动保存到 MiniDelivery（artifact.md + raw_agent_result.json + result.json）
- Delivery 搜索/预览/详情/下载全部可用
- 进度 UI（4 阶段动画）
- 总耗时 + 单 Agent 耗时统计
- **Boss Lite 历史工作台**：搜索/排序/加载更多/隐藏/恢复/复制目标/复用目标/查看交付物
- **历史复盘 Badge**：成功率、耗时、Handoff 标记、execution_mode
- **第二阶段核心闭环完成**：一句话目标 → 多 Agent 协同（含 handoff） → 作战报告 → 自动保存 → 历史可查可复用

已验证 task_id 示例：`boss_91329f9f810d`、`boss_9c21dac31fae`、`boss_932d0b352f0e`、`boss_c7dba8f25408`、`boss_27654a577ba5`、`boss_b8241c004c4d`、`boss_0fbb4623b07b`、`boss_d93dae73ab76`

最近验证：

```bash
python -c "import backend.app; print('ok')"  # ✅ 通过
cd frontend-new && npm run build              # ✅ 通过
```

详细进度见：

- `docs/phase2_boss_lite_acceptance.md` — 第二阶段 Boss Lite 验收清单
- `docs/phase1_acceptance_checklist.md` — 第一阶段验收清单
- `docs/phase3_collaboration_graph_design.md` — 第三阶段 CollaborationGraph 设计 + 验收
- `docs/business_pages_user_guide.md` — 业务页面使用说明
- `docs/project_progress_snapshot_2026-07-06.md` — 详细进度快照
- `docs/VISION.md` — 项目愿景

> 你告诉它"要做什么"，它自动拆解、分配、执行、验收，最后给你总结报告。

## 项目初心

这个项目最初的想法不是做一个普通聊天机器人，也不是堆一堆 Agent 名字，而是做一个“一人公司操作系统”：

> 用户只需要说清楚目标，系统像一家公司一样理解任务、分配部门、产出结果、检查质量、保存交付物。

更具体一点，它想解决的是：

- 一个人也能拥有“市场部、设计部、数据部、研究部、网站部、技术部、老板办公室”。
- 不把所有事情都塞进一个聊天框，而是让不同业务入口承担不同工作。
- Agent 不只是回答文字，而要形成可保存、可预览、可下载的交付物。
- 系统需要有秩序：普通业务 Agent 直接生产，高风险执行交给 Governance 风控。
- Boss 工作台只是高层入口，不是整个系统本身。

当前类比是“大汉式 AI Company OS”：

| 模块 | 类比 | 当前职责 |
|------|------|----------|
| Boss Lite | 一句话指挥台 | 一句话目标 → 5 Agent 并行 → 作战报告 → 自动保存 |
| Marketing Agent | 市场文案部 | 产出文案、品牌策略、活动方案 |
| Image Agent | 美术总监部 | 产出图片提示词和视觉 brief |
| Data Agent | 数据分析部 | 产出数据分析报告框架/简报 |
| Research Agent | 情报研究部 | 产出结构化研究简报 |
| Website Agent | 网站策划部 | 产出落地页文案和页面方案 |
| MiniDelivery | 后勤归档 | 保存、预览、下载交付物 |
| Governance | 风控/审计 | 拦截危险或不受控任务 |
| Boss 指挥台 | 董事长办公室 | 两阶段流程，支持模块选择和浏览器授权 |

## 当前进度快照

最后保存时间：2026-07-07

当前项目已推进到：

> 第三阶段 CollaborationGraph 已接入 Boss Lite（DAG 驱动执行 + 真实 API 验收通过）

已经完成：

- **第一阶段（业务 Agent MVP）** ✅ 已完成
  - `MiniDelivery v1` 已冻结：保存、列表、详情、预览、下载、归档。
  - `Marketing / Image / Data / Research / Website` 五个业务 Agent 已完成 `LLM-first + template fallback`。
  - 前端五个业务页按 `structured_output` 做结构化展示。
  - `/agents/{agent_id}/execute` 统一端点，普通业务 Agent 跳过 Governance Guard。

- **第二阶段（Boss Lite）** ✅ 已完成
  - Boss 页面默认 Boss Lite 模式，一句话目标 → 5 Agent 并行执行。
  - Agent Handoff v1：先执行 research / data，再把上游洞察传递给下游 Agent。
  - 8 个常用作战模板（新品上线、品牌冷启动、小红书种草、抖音增长、SEO 增长、落地页转化、竞品调研、数据复盘）。
  - 并行执行 + 进度 UI + 总耗时/单 Agent 耗时统计。
  - 可读 Markdown 作战报告，自动保存到 MiniDelivery。
  - Delivery 搜索/预览/详情/下载已验证。
  - **Boss Lite 历史工作台**：搜索/排序/加载更多/隐藏/恢复/复制目标/复用目标/查看交付物/复盘 Badge。

- **第三阶段（CollaborationGraph）** 🔄 进行中
  - ✅ `collaboration_graph.py` 通用 DAG 数据结构 + 拓扑排序（wave 划分）。
  - ✅ Boss Lite 执行路径已从硬编码 wave 重构为 Graph 驱动（`build_boss_lite_graph → topological_waves`）。
  - ✅ 支持 partial agents 自动裁剪子图，handoff_sources 从图上游依赖动态计算。
  - ✅ 5 个真实 API 场景验收通过（默认5agent、research+marketing、data+website、marketing only、research+data）。
  - ✅ MiniDelivery 搜索/详情/预览/下载全部验证通过。
  - ✅ 新增 `POST /boss/graph/execute` 自定义 DAG API 最小版，支持调用方传入 nodes/edges 后按图执行。
  - ✅ Boss 页面新增「协作图 / Collaboration Graph」可视化卡片，展示 waves、edges、节点状态和 handoff 来源。
  - 待做：跨 Mission 协作、自定义图模板/持久化、图编辑器。

## 下一步计划

第一阶段、第二阶段 Boss Lite 已完成，第三阶段 CollaborationGraph 已接入 Boss Lite，并新增自定义 DAG API 最小版。下一步可选方向：

1. **自定义图模板/持久化（P1）** — 保存常用 nodes/edges 配置，支持复用
2. **前端 DAG 编辑器（P1）** — 从只读可视化升级为可配置 nodes/edges
3. **OpenClaw 联网调研（P1）** — Research Agent 接入实时搜索
4. **真实数据源接入（P1）** — Data Agent 接入真实数据库/API
5. **真实图片生成（P2）** — Image Agent 接入图片生成 API
6. **PDF 导出（P2）** — 作战报告一键导出 PDF 格式
7. **历史 Mission 对比（P2）** — Boss Lite 历史记录对比分析

当前边界：

- 不做真实图片生成（Image Agent 产出提示词框架）。
- 不把爬虫/OpenClaw 接进 Research。
- 不让 Governance 接管普通业务 Agent 的生产链路。
- 不把 template fallback 伪装成真实 LLM 产出。

## ✨ 核心特性

- 🤖 **10个AI智能体** — CEO/Codex/OpenClaw/QA/System/CTO/Image/Marketing/Video/Data
- ⚡ **Boss Lite 一句话执行** — 一句话目标 → 5 Agent 并行 → 作战报告
- 🧠 **智能任务编排** — 自动拆解复杂目标，多Agent协作执行
- 🎨 **科技感UI** — React + TypeScript + Tailwind CSS 4
- 🔌 **多Provider支持** — DeepSeek/OpenAI/Claude 一键切换
- 🔒 **安全可靠** — 输入验证、速率限制、敏感信息脱敏
- 📊 **数据分析** — 上传Excel/CSV，自动分析生成报告

## 🚀 快速开始

### 方式一：一键启动（推荐）

```bash
# Windows
双击 start.bat

# Linux/macOS
chmod +x start.sh && ./start.sh
```

### 方式二：手动启动

```bash
# 1. 克隆项目
git clone <repo-url>
cd AI-company-os

# 2. 创建虚拟环境
python -m venv .venv
source .venv/bin/activate  # Linux/macOS
# .venv\Scripts\activate   # Windows

# 3. 安装依赖
pip install -r requirements.txt

# 4. 配置环境变量
cp .env.example .env
# 编辑 .env 文件，填入你的 API Key

# 5. 启动服务
python -m uvicorn backend.app:app --host 0.0.0.0 --port 8000
```

### 方式三：Docker

```bash
# 构建镜像
docker compose build

# 启动服务
docker compose up -d

# 查看日志
docker compose logs -f
```

### 本地开发注意事项

```bash
# 后端（端口 8000）
python -m uvicorn backend.app:app --reload --port 8000

# 前端开发模式（端口 5173）
cd frontend-new
npm install
npm run dev
```

- 后端运行在 `localhost:8000`，前端 Vite dev server 运行在 `localhost:5173`。
- Vite 代理默认指向 `http://localhost:8000`（见 `frontend-new/vite.config.ts`）。
- 如需临时指向其他后端，启动前端时指定环境变量：
  ```bash
  # macOS/Linux/Git Bash：指向 8001 端口的后端（临时调试用）
  VITE_BACKEND_TARGET=http://localhost:8001 npm run dev
  ```
  ```powershell
  # Windows PowerShell
  $env:VITE_BACKEND_TARGET="http://localhost:8001"; npm run dev
  ```
  ```cmd
  :: Windows cmd
  set VITE_BACKEND_TARGET=http://localhost:8001&& npm run dev
  ```
- 如遇到 API 返回异常或列表为空，先重启后端和 Vite dev server。
- 前端构建（`npm run build`）如遇内存不足，使用：`NODE_OPTIONS="--max-old-space-size=4096" npm run build`。
- 业务页统一使用 `/agents/{agent_id}/execute` 端点。旧端点 `/agents/{agent_id}/run` 仍存在但不推荐使用。

**验证代理是否指向正确后端：**

```bash
# 应看到 total_duration_ms / handoff_enabled / execution_mode 字段
curl "http://localhost:5173/minidelivery/tasks?agent_id=boss&limit=1"
```

如果看不到复盘字段，说明 5173 代理到了旧后端。解决方法：
1. 确认后端在 8000 端口启动（不是 8001）
2. 重启 Vite dev server（`npm run dev`）
3. 或临时把前端代理指向 `8001` 后重新启动 Vite：
   - macOS/Linux/Git Bash：`VITE_BACKEND_TARGET=http://localhost:8001 npm run dev`
   - Windows PowerShell：`$env:VITE_BACKEND_TARGET="http://localhost:8001"; npm run dev`

详细使用说明见：`docs/business_pages_user_guide.md`

## 📖 使用指南

### 访问界面

| 界面 | 地址 | 说明 |
|------|------|------|
| Boss Lite（推荐） | http://localhost:5173/app?page=boss | 一句话目标 → 多 Agent 协同 |
| 新版UI | http://localhost:8000/app | React科技感界面 |
| 前端开发模式 | http://localhost:5173 | Vite dev server（热更新） |
| 旧版UI | http://localhost:8000/ui | 经典界面 |
| API文档 | http://localhost:8000/docs | Swagger文档 |
| 健康检查 | http://localhost:8000/health | 服务状态 |

### 配置AI Provider

编辑 `.env` 文件：

```bash
# 选择Provider: deepseek / openai / claude
AI_PROVIDER=deepseek

# DeepSeek配置
DEEPSEEK_API_KEY=your_api_key_here
DEEPSEEK_BASE_URL=https://api.deepseek.com
DEEPSEEK_MODEL=deepseek-chat

# OpenAI配置
OPENAI_API_KEY=your_api_key_here
OPENAI_BASE_URL=https://api.openai.com/v1
OPENAI_MODEL=gpt-4o

# Claude配置
CLAUDE_API_KEY=your_api_key_here
CLAUDE_BASE_URL=https://api.anthropic.com
CLAUDE_MODEL=claude-sonnet-4-20250514
```

### 获取API Key

| Provider | 获取地址 | 价格 |
|----------|----------|------|
| DeepSeek | https://platform.deepseek.com | ¥0.1-0.3/千次 |
| OpenAI | https://platform.openai.com | $0.005-0.03/千token |
| Claude | https://console.anthropic.com | $0.003-0.015/千token |

## 🏗️ 架构设计

```
AI Company OS
├── backend/           # FastAPI后端
│   ├── app.py         # 主应用入口
│   ├── config.py      # 配置中心
│   ├── security.py    # 安全模块
│   ├── performance.py # 性能优化
│   ├── logger.py      # 日志系统
│   ├── error_handler.py # 错误处理
│   ├── routers/       # API路由
│   ├── database/      # 数据库
│   └── middleware/    # 中间件
├── agents/            # AI智能体
│   ├── ceo_agent/     # 目标拆解
│   ├── codex_agent/   # 代码执行
│   ├── marketing_agent/ # 营销文案
│   └── ...
├── core/              # 核心模块
│   ├── skills/        # 技能系统
│   ├── memory/        # 记忆系统
│   └── workflow/      # 工作流引擎
├── frontend-new/      # React前端
│   ├── src/
│   └── dist/
└── docs/              # 文档
```

### 技术栈

| 层 | 技术 |
|----|------|
| 后端 | FastAPI + Python 3.11+ |
| 前端 | React 19 + TypeScript + Tailwind CSS 4 |
| 数据库 | SQLite (WAL模式) |
| AI | DeepSeek / OpenAI / Claude |
| 部署 | Docker Compose |

## 📚 API文档

### 核心接口

| 接口 | 方法 | 说明 |
|------|------|------|
| `/commander/chat/send` | POST | AI对话（支持上下文） |
| `/commander/run` | POST | 同步执行任务 |
| `/commander/run-async` | POST | 异步执行任务 |
| `/agents/{agent}/execute` | POST | 调用指定Agent（推荐） |
| `/agents/{agent}/run` | POST | 调用指定Agent（旧版，不推荐） |
| `/data/upload` | POST | 上传数据文件 |
| `/config/save` | POST | 保存配置 |

### 示例：AI对话

```bash
curl -X POST http://localhost:8000/commander/chat/send \
  -H "Content-Type: application/json" \
  -d '{
    "message": "帮我写一条朋友圈文案，推广手工耳环",
    "history": []
  }'
```

### 示例：上传数据

```bash
curl -X POST http://localhost:8000/data/upload \
  -F "file=@sales_data.csv"
```

## 🔒 安全特性

- ✅ 输入验证（长度、类型、格式）
- ✅ SQL注入防护（参数化查询）
- ✅ 文件上传安全检查（扩展名、内容、大小）
- ✅ XSS防护（输入清理）
- ✅ 速率限制（防止滥用）
- ✅ 敏感信息脱敏（API Key、Token）
- ✅ CORS配置
- ✅ 认证中间件

## 🧪 测试

```bash
# 运行测试
pytest

# 运行测试并生成覆盖率报告
pytest --cov=backend --cov-report=html
```

## 📦 部署

### 生产环境部署

```bash
# 1. 设置环境变量
export ENV=production
export AUTH_TOKEN=your_secure_token

# 2. 启动服务
python -m uvicorn backend.app:app \
  --host 0.0.0.0 \
  --port 8000 \
  --workers 4 \
  --log-level info
```

### Docker部署

```bash
# 构建并启动
docker compose -f docker-compose.prod.yml up -d

# 查看状态
docker compose ps

# 查看日志
docker compose logs -f
```

## 🤝 贡献指南

1. Fork 项目
2. 创建功能分支 (`git checkout -b feature/xxx`)
3. 提交更改 (`git commit -m 'Add feature xxx'`)
4. 推送到分支 (`git push origin feature/xxx`)
5. 创建 Pull Request

### 代码规范

- Python: 遵循 PEP 8
- TypeScript: 遵循 ESLint 规则
- 提交信息: 使用中文，格式为 `[类型] 描述`

### 类型说明

- `[功能]` 新功能
- `[修复]` Bug修复
- `[文档]` 文档更新
- `[重构]` 代码重构
- `[测试]` 测试相关
- `[配置]` 配置更新

## 📄 许可证

MIT License

## 🙏 致谢

- [FastAPI](https://fastapi.tiangolo.com/)
- [React](https://react.dev/)
- [Tailwind CSS](https://tailwindcss.com/)
- [DeepSeek](https://deepseek.com/)
- [OpenAI](https://openai.com/)
- [Anthropic](https://anthropic.com/)

## 📞 支持

- 📧 Email: support@example.com
- 💬 微信群: 添加微信 xxx 拉群
- 📖 文档: https://docs.example.com
- 🐛 Issue: https://github.com/xxx/ai-company-os/issues
