# AI Company OS · 多智能体协作操作系统

**版本 1.5.0**

## 最新状态（2026-07-06）

当前项目已经完成：

> 五个业务页 + MiniDelivery 交付中心端到端闭环验收

已验收闭环：

- `Marketing`：7 种模式均通过浏览器验收，包括通用文案、小红书、抖音、SEO 长文、邮件营销、品牌策略、活动方案。
- `Image / Data / Research / Website`：均通过生成、结构化展示、保存到交付中心、Delivery 搜索/预览/详情/下载。
- `MiniDelivery`：列表、搜索、详情、artifact 预览、下载均可用。
- `Delivery` 页面：可按 `task_id` 搜索交付物，预览和详情页正常。
- 开发模式：Vite 已代理 `/minidelivery`，前端保存和读取交付物可走本地后端。

最近验证：

```bash
python -c "import backend.app; print('ok')"
cd frontend-new && npm run build
```

详细进度见：

- `docs/project_progress_snapshot_2026-07-06.md`
- `docs/project_progress_snapshot_2026-07-05.md`
- `docs/VISION.md`

下一步建议：

1. 做阶段冻结和用户使用说明。
2. 检查首页/导航，让用户更容易进入五个业务页和 Delivery。
3. 暂不扩真实图片生成、真实数据源、OpenClaw 联网调研。

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
| Marketing Agent | 市场文案部 | 产出文案、品牌策略、活动方案 |
| Image Agent | 美术总监部 | 产出图片提示词和视觉 brief |
| Data Agent | 数据分析部 | 产出数据分析报告框架/简报 |
| Research Agent | 情报研究部 | 产出结构化研究简报 |
| Website Agent | 网站策划部 | 产出落地页文案和页面方案 |
| MiniDelivery | 后勤归档 | 保存、预览、下载交付物 |
| Governance | 风控/审计 | 拦截危险或不受控任务 |
| Boss 工作台 | 董事长办公室 | 高层入口，不接管所有业务 |

## 当前进度快照

最后保存时间：2026-07-05

当前项目已经推进到：

> 前端展示验收 + 业务 Agent 链路打通阶段

已经完成：

- `MiniDelivery v1` 已冻结：保存、列表、详情、预览、下载、归档。
- `Marketing / Image / Data / Research / Website` 五个业务 Agent 已完成 `LLM-first + template fallback`。
- 前端五个业务页开始按 `structured_output` 做结构化展示。
- `source / fallback / fallback_reason / warnings` 已进入前端可见范围。
- `backend/app.py` 已注册 `minidelivery_router`，保存到交付中心不再 404。
- `/agents/{agent_id}/execute` 对普通业务 Agent 跳过 Governance Guard，避免业务产出被误拦截。
- Marketing 页已从“小红书/抖音平台限制”扩展为文案类型选择：
  - 通用文案
  - 小红书
  - 抖音
  - SEO 长文
  - 邮件营销
  - 品牌策略
  - 活动方案

最近验证：

```bash
python -c "import backend.app; print('ok')"
cd frontend-new && npm run build
```

已验证 `POST /agents/marketing/execute` 的 `brand_strategy` 请求可以返回 `ok=true`，不再被 `blocked_by_governance` 拦截。

更详细的进度记录见：

- `docs/project_progress_snapshot_2026-07-05.md`
- `docs/project_progress_snapshot_2026-07-04.md`
- `docs/VISION.md`

## 下一步计划

当前不要继续扩新框架，优先做端到端验收：

1. 逐页测试 `Marketing / Image / Data / Research / Website`。
2. 每页确认能生成、能展示结构化字段、能显示 fallback/source/warnings。
3. 每页点击“保存到交付中心”。
4. 打开 Delivery 页面检查预览和下载内容是否与页面展示一致。
5. 如果保存后的 Markdown 丢字段，只修 `backend/routers/minidelivery_router.py` 的字段映射，不扩 MiniDelivery 功能。

当前边界：

- 不做真实图片生成。
- 不把爬虫/OpenClaw 接进 Research。
- 不让 Governance 接管普通业务 Agent 的生产链路。
- 不改 Boss / Collaboration / sandbox，除非明确进入高风险执行阶段。
- 不把 template fallback 伪装成真实 LLM 产出。

## ✨ 核心特性

- 🤖 **10个AI智能体** — CEO/Codex/OpenClaw/QA/System/CTO/Image/Marketing/Video/Data
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

## 📖 使用指南

### 访问界面

| 界面 | 地址 | 说明 |
|------|------|------|
| 新版UI（推荐） | http://localhost:8000/app | React科技感界面 |
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
| `/agents/{agent}/run` | POST | 调用指定Agent |
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
