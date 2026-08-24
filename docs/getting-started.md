# AI Company OS — 快速开始

## 环境要求

- Python 3.12+
- Node.js 20.19+ 或 22.12+
- npm
- Docker Desktop 或 Docker Engine（仅 Docker 部署需要）

## 首次安装：先做一键验收

Windows：

```powershell
.\verify.bat
```

Linux / macOS：

```bash
chmod +x verify.sh
./verify.sh
```

验收会准备依赖、构建 React 前端、启动临时后端、检查核心 API 与交付中心，并在结束后关闭临时后端。全部必选项通过时退出码为 `0`。

## 正式启动

Windows：

```powershell
.\start.bat
```

Linux / macOS：

```bash
chmod +x start.sh
./start.sh
```

启动脚本会确保 Python 依赖、Playwright Chromium 和 React 生产构建就绪，然后启动 Uvicorn。

访问地址：

- 新版界面：`http://127.0.0.1:8000/app`
- 经典界面：`http://127.0.0.1:8000/ui`
- API 文档：`http://127.0.0.1:8000/docs`
- 健康检查：`http://127.0.0.1:8000/health`

## 环境变量与真实 Provider

首次启动会在缺少 `.env` 时复制 `.env.example`。可以配置 DeepSeek/OpenAI/Claude，以及搜索和图片 Provider。

没有真实 API Key 时系统允许使用 Mock、模板或本地 heuristic fallback，但这不代表真实 Provider 已通过验收。显式验证真实 Provider：

```bash
python scripts/verify_deployment.py --with-providers
```

## Docker Compose

```bash
cp .env.example .env
docker compose build
docker compose up -d
docker compose ps
curl http://127.0.0.1/health
```

新版前端在 Docker 多阶段构建中生成，无需把本地 `frontend-new/dist` 放入镜像。

## 本地开发

后端：

```bash
python -m uvicorn backend.app:app --reload --port 8000
```

前端：

```bash
cd frontend-new
npm ci
npm run dev
```

Vite 默认代理到 `http://127.0.0.1:8000`。

## 更多信息

完整的部署矩阵、验收边界、故障排查、数据备份和发布清单见：

- `docs/phase7d_deployment_runbook.md`
