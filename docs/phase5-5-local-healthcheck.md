# Phase 5.5 — 本地部署体检脚本

## 概述

`scripts/healthcheck_local.py` 一次性检查本地 AI Company OS 的所有关键服务是否正常运行。

**不启动任何服务**，只检查已启动的。服务没启动时给出明确的修复建议。

## 检查项

| 检查 | 必须 | 说明 |
|------|------|------|
| backend_health | ✓ | `GET /health` 返回 200 |
| providers_health | ✓ | `GET /config/providers/health` 可达，报告 search/image mock 状态 |
| frontend_dev_server | | Vite dev server 端口可达（默认 5173，非必须） |
| minidelivery_list | ✓ | `GET /minidelivery/tasks` 返回 200 |
| pdf_endpoint | ✓ | `GET /minidelivery/tasks/{id}/pdf` 返回 404（路由可达，task 不存在是预期） |
| provider_verification | | 可选，运行 `verify_real_providers.py` 验证真实 API Key |

## 使用

```bash
# 基础体检（后端 + 前端 + 交付物 + PDF）
python scripts/healthcheck_local.py

# 指定后端端口
python scripts/healthcheck_local.py --port 8001

# 指定前端端口
python scripts/healthcheck_local.py --frontend-port 3000

# 跳过前端检查
python scripts/healthcheck_local.py --skip-frontend

# 同时验证真实 Provider API Key
python scripts/healthcheck_local.py --with-providers

# 仅输出 JSON（适合 CI）
python scripts/healthcheck_local.py --json

# 全部参数
python scripts/healthcheck_local.py --port 8001 --frontend-port 3000 --with-providers --timeout 60 --json
```

## 输出示例

### 全部正常

```
  ═══ Phase 5.5 — 本地部署体检 ═══

  ✓ PASS  backend_health
        HTTP 200 (0.02s)
  ✓ PASS  providers_health
        搜索=SerpAPI，图片=mock
  ✓ PASS  frontend_dev_server
        Vite dev server 运行中 (port 5173)
  ✓ PASS  minidelivery_list
        共 3 个交付物
  ✓ PASS  pdf_endpoint
        路由可达（404 = task 不存在，符合预期）

  ── 汇总 ──
  PASS:5  FAIL:0  WARN:0  SKIP:0  Total:5

  [OK] 本地部署正常
```

### 后端未启动

```
  ═══ Phase 5.5 — 本地部署体检 ═══

  ✗ FAIL  backend_health
        Connection refused: [Errno 111] Connection refused
        → 修复: 后端未启动。运行: uvicorn backend.app:app --reload --port 8000
  – SKIP  providers_health
        后端未就绪，跳过
  – SKIP  minidelivery_list
        后端未就绪，跳过
  – SKIP  pdf_endpoint
        后端未就绪，跳过

  ── 汇总 ──
  PASS:0  FAIL:1  WARN:0  SKIP:3  Total:4

  [FAIL] 1 项异常
```

## 退出码

| 退出码 | 含义 |
|--------|------|
| 0 | 所有必须检查通过（skip/warn 算通过） |
| 1 | 至少一项必须检查失败 |

## 与 Phase 5.4 的区别

| | Phase 5.4 | Phase 5.5 |
|---|---|---|
| 脚本 | `verify_real_providers.py` | `healthcheck_local.py` |
| 目的 | 验证真实 API Key 集成 | 本地服务全面体检 |
| 范围 | 仅 search/image provider | 后端 + 前端 + 交付物 + PDF + 可选 provider |
| 前置 | 需要 API Key | 无需任何 Key |
| 场景 | CI 验收、Key 配置后验证 | 日常开发、部署后快速体检 |
