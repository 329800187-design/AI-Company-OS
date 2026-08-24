# Phase 7D — 部署与一键验收运行手册

> 目标：从完整 Git checkout 或发布压缩包出发，用一个命令完成依赖准备、前端生产构建、临时后端启动、健康检查和核心 smoke 验收。

## 1. 验收边界

默认一键验收包含：

1. Python、Node.js、npm 和必要项目文件检查。
2. Python 依赖安装；仅在 `node_modules` 不存在时执行 `npm ci`。
3. `backend.app` 导入检查。
4. `frontend-new` 生产构建。
5. 在随机空闲端口启动临时后端，并确认 `/health` 返回 `status=ok`。
6. 运行 `backend_smoke_check.py`，验证 Memory、Boss mission、模板和导出等核心 API。
7. 运行 `healthcheck_local.py --skip-frontend`，验证 Provider 状态、MiniDelivery 和 PDF 路由。
8. 关闭本次验收自己启动的后端进程。

默认验收不调用付费 AI Provider、不执行浏览器自动化，也不修改用户已有任务。真实 Provider 验收需要显式添加 `--with-providers`。

## 2. 环境要求

| 组件 | 最低要求 | 说明 |
|---|---:|---|
| Python | 3.12 | 与 Docker 和 CI 版本一致 |
| Node.js | 20.19 | Vite 8 最低兼容线；Node 22.12+ 也可 |
| npm | 随 Node 安装 | 必须能够运行 `npm ci` 和 `npm run build` |
| 可用端口 | 1 个本地随机端口 | 验收程序自动选择，不占用正式 8000 端口 |

## 3. Windows 一键验收

在项目根目录双击 `verify.bat`，或在 PowerShell/CMD 中运行：

```powershell
.\verify.bat
```

脚本会在缺少时创建 `.venv`，然后执行完整验收。全部必选检查通过时退出码为 `0`；任一必选检查失败时退出码为 `1`。

## 4. Linux / macOS 一键验收

```bash
chmod +x verify.sh
./verify.sh
```

也可以直接运行主程序：

```bash
python3 scripts/verify_deployment.py --install-deps
```

## 5. 常用参数

```bash
# 已安装依赖时直接验证
python scripts/verify_deployment.py

# 跳过前端构建，只定位后端问题
python scripts/verify_deployment.py --skip-frontend

# 只检查环境、导入与前端构建
python scripts/verify_deployment.py --skip-backend

# 验证已配置的真实搜索/图片 Provider（可能产生外部请求或费用）
python scripts/verify_deployment.py --with-providers

# 输出机器可读 JSON
python scripts/verify_deployment.py --json
```

## 6. 正式本地启动

验收通过后，正式运行可使用：

```powershell
# Windows
.\start.bat
```

```bash
# Linux / macOS
./start.sh
```

默认访问地址：

- Web：`http://127.0.0.1:8000/app`
- API 文档：`http://127.0.0.1:8000/docs`
- 健康检查：`http://127.0.0.1:8000/health`

首次启动前可复制 `.env.example` 为 `.env` 并配置所需 Provider。没有真实 Key 时系统允许使用 Mock/模板 fallback，但这不等同于真实能力验收。

## 7. Docker Compose 部署

```bash
cp .env.example .env
docker compose build
docker compose up -d
docker compose ps
curl http://127.0.0.1/health
```

Web 入口为 `http://127.0.0.1/`。当前 Compose 使用绑定目录保存日志和 SQLite 数据；升级或重新构建前应备份 `backend/database` 和 `logs`。

停止服务：

```bash
docker compose down
```

不要使用 `down -v`，除非明确需要删除持久化数据。

## 8. 失败排查

| 失败项 | 常见原因 | 建议动作 |
|---|---|---|
| `python_version` | Python 版本低于 3.12 | 安装 3.12，并删除后重新创建 `.venv` |
| `node_version` | Node 版本过低 | 升级到 Node 20.19+ 或 22.12+ |
| `python_dependencies` | 网络、编译器或镜像问题 | 手动运行 `.venv` 中的 `pip install -r requirements.txt` |
| `frontend_dependencies` | npm 网络或 lockfile 不一致 | 在 `frontend-new` 运行 `npm ci` |
| `frontend_build` | TypeScript、Vite 或原生依赖错误 | 在 `frontend-new` 单独运行 `npm run build` 查看完整输出 |
| `backend_health` | 后端导入错误或启动超时 | 查看报告给出的临时后端日志路径 |
| `backend_smoke` | 核心 API 状态码或结构变化 | 单独运行报告中的复现命令 |
| `deployment_healthcheck` | MiniDelivery、PDF 或 Provider 路由异常 | 运行 `scripts/healthcheck_local.py` 定位具体检查项 |

## 9. 发布验收清单

- [ ] 从干净 checkout 或发布压缩包开始，而不是复用开发目录。
- [ ] Windows 至少完成一次 `verify.bat`。
- [ ] Linux 或 macOS 至少完成一次 `verify.sh`。
- [ ] `python -m pytest` 全量测试完成且无 failed。
- [ ] CI 的 test 与 docker job 均为绿色。
- [ ] 记录本次 Git commit、Python/Node 版本和验收时间。
- [ ] 如宣称真实能力可用，使用 `--with-providers` 验证对应 Provider。
- [ ] 发布包不包含 `.env`、API Key、用户数据库、日志或本地上传文件。

## 10. 当前仍不覆盖的生产能力

Phase 7D 验收证明“该版本可安装、可启动、核心路由可用”，但不代表以下能力已经完成：

- 高并发与长时间稳定性测试。
- PostgreSQL/Redis 生产拓扑验证。
- 多租户数据隔离安全审计。
- 外部 Provider 的 SLA、费用和限流验证。
- 跨日自主经营与业务 KPI 闭环。
