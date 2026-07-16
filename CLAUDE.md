# CLAUDE.md — AI Company OS

## Project Identity

**AI Company OS** — 一人公司AI助手 v1.0.0
- 目标：用户说"要做什么"，系统自动拆解→分配→执行→验收→总结
- **10 个 AI Agent：** Commander/CEO/Codex/OpenClaw/QA/System/CTO/Image/Marketing/Video/Data + AI Registry
- **技能系统:** 25 个技能（Embedding 语义搜索 + 缓存加速）
- **工作流引擎:** DAG 拓扑排序 + 条件分支 + 并行层执行 (5个工作流)
- **多租户:** 用户注册/登录 + 3 级套餐 + Stripe 支付
- **上下文引擎:** 1M 虚拟窗口 + 4层压缩 + 语义检索
- **定时任务:** Cron 调度器 + SQLite 持久化
- **消息总线:** Agent Pub/Sub + 请求/响应
- **路由模块:** 21 个 (153 条路由)

## Architecture

```
E:/AI-company-os/
├── backend/           # FastAPI 入口 + 路由 + 配置 + 中间件 + 数据库 + 任务队列
│   ├── app.py         # FastAPI 主应用 (路由注册、WebSocket、中间件)
│   ├── config.py      # 配置中心 (.env → 多Provider → Agent参数)
│   ├── commander/     # 指挥官主脑 (多Agent协作调度)
│   ├── routers/       # 12 个路由模块 (task/agent/workflow/commander/cto/config/ai_registry/template/export/usage/skill/memory)
│   ├── database/      # SQLite + WAL 模式
│   ├── services/      # 日志、使用统计
│   ├── middleware/     # API Key 认证中间件
│   ├── task_queue/    # 后台任务管理器 (ThreadPoolExecutor)
│   └── ai_registry/   # AI 服务注册中心 (扫描+路由+调用)
├── agents/            # 智能体实现 (10个)
│   ├── ceo_agent/     # 目标拆解 Agent
│   ├── cto_agent/     # 技术架构 Agent
│   ├── codex_agent/   # 代码沙箱 Agent (audit hook防护)
│   ├── data_agent/    # 数据分析 Agent (pandas/matplotlib)
│   ├── image_agent/   # 图片生成 Agent (DALL-E 3智能路由)
│   ├── marketing_agent/ # 营销内容 Agent (6种能力)
│   ├── openclaw_agent/  # 全能研究 Agent (v2: 搜索+思考+1M上下文)
│   ├── qa_agent/      # 质量验收 Agent (AI语义评分)
│   ├── system_agent/  # 系统操作 Agent (10种操作+50+危险命令)
│   └── video_agent/   # 视频创意 Agent (脚本/分镜)
├── core/              # 核心系统 (8个模块)
│   ├── skills/        # 技能管理 (TF-IDF + Embedding + 缓存)
│   ├── memory/        # 记忆存储 (TF-IDF语义搜索 + rerank)
│   ├── workflow/      # DAG工作流引擎 (拓扑排序+条件分支+并行)
│   ├── context_engine.py  # 1M虚拟上下文 (4层压缩)
│   ├── cache_store.py     # LRU+TTL缓存
│   ├── embedding_service.py # AI/本地Embedding
│   ├── cron_scheduler.py  # Cron调度器
│   ├── agent_bus.py       # Agent消息总线
│   ├── capability_scanner.py  # 本机能力扫描 (AI/浏览器/工具/Agent)
│   ├── brain_manager.py       # 主脑管理器 (7个AI主脑切换)
│   └── agent_protocol.py      # Agent统一通信协议
├── frontend-new/      # React 19 + TypeScript + Vite + Tailwind CSS 4
│   ├── src/
│   │   ├── app/       # 布局、路由、Provider
│   │   ├── components/# UI 组件 + 布局组件 + 共享组件
│   │   ├── pages/     # 10 个页面
│   │   ├── stores/    # Zustand 状态管理
│   │   ├── api/       # API 客户端
│   │   └── lib/       # 工具函数
│   └── dist/          # 构建产物
```

## Tech Stack

| Layer | Tech |
|-------|------|
| Backend | FastAPI (Python 3.12) + httpx |
| Database | SQLite (WAL mode) |
| Browser | Playwright (Chromium, OpenClaw agent) |
| AI | Multi-provider: DeepSeek/OpenAI/Claude |
| Deployment | Docker Compose |
| Frontend | React 19 + TypeScript + Vite + Tailwind CSS 4 (科技感 UI) |
| Task Queue | BackgroundTaskManager (ThreadPoolExecutor, max_workers=4) |

## Key Conventions

### Provider Routing (backend/config.py)
- `AI_PROVIDER` env var controls which AI to use
- Supported: `deepseek`, `openai`, `claude`
- Config priority: env var > .env file > defaults
- `get_ai_config()` returns {api_key, base_url, model}

### API Patterns
- All routers in `backend/routers/` with `router = APIRouter(prefix="/xxx")`
- Database: `init_db()` on startup, WAL mode enabled
- Auth: `AuthMiddleware` — development mode skips auth
- WebSocket: `/ws/task/{task_id}` for real-time task progress
- Health check: `GET /health`
- UI: `GET /ui` (served from `frontend/index.html`)

### Agent Patterns
- Agents in `agents/<name>_agent/agent.py` or `openclaw_agent/agent.py`
- Commander is the orchestrator — calls CEO → delegates to Codex/OpenClaw/System → QA verifies
- Agent calling convention: `agent.run(task: dict) → result dict`（所有 Agent 继承 BaseAgent，实现 `run()` 方法）

## Current Phase

- [x] Phase 0-6: ✅ 全部完成 (v0.8.0)
- [x] Phase 7: Agent OS 完善 ✅ 100% (v0.9.0)
- [x] Phase 8: 用户体验重构 ✅ 100% (v0.9.2)
  - ✅ 首页改为场景卡片引导（不再是空白输入框）
  - ✅ 侧边栏重分类（写文案/生成图片/分析数据/做调研/建网站）
  - ✅ 技术术语全部隐藏到「高级功能」折叠区
  - ✅ 定价页面简化（去掉Agent/tokens/DAG等术语）
  - ✅ 引导弹窗简化（3秒能看懂）
  - ✅ 快速对话入口（首页直接输入即可）
  - ✅ 新增「数据分析」页面（上传文件+快速场景）
  - ✅ 新增「做调研」页面（竞品/市场/用户画像/行业报告）
  - ✅ 新增「建网站」页面（一句话生成网页）
  - ✅ 对话页面增加示例按钮（小白一看就懂）

## Deployment

```bash
# Quick start (Windows)
双击 start.bat

# Manual
python -m venv .venv && source .venv/bin/activate (or .venv\Scripts\activate)
pip install -r requirements.txt
playwright install chromium
cp .env.example .env  # edit API keys
uvicorn backend.app:app --reload

# Docker
docker compose up -d
```

## Notes

- The user also uses **OpenClaw** and **Codex** as supplementary tools alongside Claude Code
- All agent communication goes through Commander as orchestrator
- AI Registry auto-discovers local AI services and routes by capability
