# Phase 5 — 产品化收口验收文档

> 最后更新：2026-07-09

## 概述

Phase 5 的目标是将前四个阶段的成果收口为**可交付、可验证、可运维**的产品状态。不新增业务能力，聚焦于：导出、对比、监控、验收脚本、部署体检。

---

## Phase 5.1 — PDF 导出 ✅ 已闭环

### 交付物

| 文件 | 说明 |
|------|------|
| `backend/services/pdf_service.py` | Markdown → PDF 转换引擎（reportlab + CJK 字体） |
| `backend/routers/minidelivery_router.py` | `GET /minidelivery/tasks/{task_id}/pdf` 端点 |
| `frontend-new/src/pages/delivery/detail.tsx` | 详情页「导出 PDF」按钮 |

### 能力

- MiniDelivery 产物（artifact.md）一键导出 PDF
- 支持 Markdown 标题、列表、表格、代码块、粗体/斜体
- 中文字体自动检测（Windows / Linux / macOS）
- reportlab 不可用时 fallback 为 HTML
- 前端详情页直接下载

### 验收状态

- ✅ 后端端点可达
- ✅ PDF 生成逻辑完整（标题、元数据、正文、页脚）
- ✅ CJK 字体注册逻辑
- ✅ 前端下载按钮集成
- ✅ 无外部 API 依赖，纯本地能力

---

## Phase 5.2 — Mission 对比 ✅ 已闭环

### 交付物

| 文件 | 说明 |
|------|------|
| `backend/routers/minidelivery_router.py` | `POST /minidelivery/tasks/compare` 端点 |
| `backend/minidelivery/models.py` | `CompareTasksRequest` 数据模型 |
| `frontend-new/src/pages/boss/index.tsx` | Boss 历史工作台对比 UI |

### 能力

- 传入 2 个 task_id，返回结构化对比结果
- 对比字段：goal、created_at、artifact_type、agent_id、ok、mode、summary
- Boss Lite/Graph 复盘字段：succeeded、failed、total、total_duration_ms、handoff_enabled、execution_mode
- 差异高亮（diff 返回差值和变更标记，前端高亮有变化的行）

### 验收状态

- ✅ 后端端点逻辑完整
- ✅ 前端对比 UI 集成
- ✅ 无外部 API 依赖，纯本地能力

---

## Phase 5.3 — Provider Health 面板 ✅ 已闭环

### 交付物

| 文件 | 说明 |
|------|------|
| `backend/routers/config_router.py` | `GET /config/providers/health` 端点 |
| `backend/tests/test_provider_health.py` | 端点单元测试 |
| `frontend-new/src/pages/settings/index.tsx` | Settings 页 Provider 状态卡片 |
| `docs/provider-health-api.md` | API 文档 |

### 能力

- 返回 search / image 两组 provider 状态
- 每组包含：当前 provider 名、是否 mock、是否有 API key、可用性
- 列出所有支持的真实 provider 及其 key 状态
- **不暴露 API Key 值**，只返回 `has_key: boolean`
- 前端 Settings 页展示状态卡片 + 修复提示

### 验收状态

- ✅ 后端端点 + 单元测试
- ✅ 前端 UI 集成
- ✅ 安全：不泄露 key 值
- ✅ 无外部 API 依赖，纯本地能力

---

## Phase 5.4 — 真实 Provider E2E 验收脚本 ⚠️ 已闭环（依赖真实 API Key）

### 交付物

| 文件 | 说明 |
|------|------|
| `scripts/verify_real_providers.py` | E2E 验收脚本 |
| `docs/phase5-4-real-provider-e2e.md` | 使用文档 |

### 能力

- 自动检测 `.env` 中的 API Key
- 有 key 跑真实调用，没 key 跳过（不报错）
- 检查项：providers_health（始终执行）、research_real_sources（需搜索 key）、image_generation（需 OpenAI key）
- 支持 `--json` 输出（适合 CI）、`--port`、`--timeout`

### 验收状态

- ✅ 脚本逻辑完整
- ✅ 无 key 时 skipped 算通过
- ⚠️ **真实调用需配置 API Key**：
  - `SERPAPI_API_KEY` 或 `BING_SEARCH_API_KEY`（搜索）
  - `OPENAI_API_KEY`（图片生成）
- ✅ 不改业务代码

---

## Phase 5.5 — 本地部署体检脚本 ✅ 已闭环

### 交付物

| 文件 | 说明 |
|------|------|
| `scripts/healthcheck_local.py` | 本地全量体检脚本 |
| `docs/phase5-5-local-healthcheck.md` | 使用文档 |

### 能力

- 一次性检查所有关键服务（不启动任何服务）
- 检查项：backend_health、providers_health、frontend_dev_server、minidelivery_list、pdf_endpoint
- 可选：`--with-providers` 同时跑真实 Provider 验证
- 每项检查失败给出具体修复建议
- 支持 `--json`、`--skip-frontend`、`--port`、`--frontend-port`

### 验收状态

- ✅ 脚本逻辑完整
- ✅ 无需任何 API Key 即可运行
- ✅ 退出码语义明确（0=通过，1=失败）
- ✅ 不改业务代码

---

## Phase 5.6 — 产品化收口（本文档） ✅ 已闭环

### 交付物

| 文件 | 说明 |
|------|------|
| `docs/phase5_productization_acceptance.md` | 本文档 |
| `README.md` | 更新至 Phase 5 状态 |

### 验证

```bash
python -c "import backend.app; print('ok')"   # ✅ 通过
cd frontend-new && npm run build                # ✅ 通过 (1.13s)
```

---

## 能力总览

| 子阶段 | 能力 | 状态 | 依赖外部 API Key | 性质 |
|--------|------|------|------------------|------|
| 5.1 PDF 导出 | 产物一键导出 PDF | ✅ 已闭环 | 否 | 产品化 |
| 5.2 Mission 对比 | 两个任务结构化对比 | ✅ 已闭环 | 否 | 产品化 |
| 5.3 Provider Health | Provider 状态面板 | ✅ 已闭环 | 否 | 运维增强 |
| 5.4 E2E 验收脚本 | 真实 Provider 端到端验证 | ⚠️ 已闭环 | 是（SerpAPI/Bing/OpenAI） | 验收工具 |
| 5.5 本地体检脚本 | 本地服务全量体检 | ✅ 已闭环 | 否 | 运维增强 |
| 5.6 产品化收口 | 文档 + README 更新 | ✅ 已闭环 | 否 | 文档 |

---

## 分类说明

### 已闭环（纯本地，不依赖外部）

- PDF 导出 — 产品化核心能力
- Mission 对比 — 产品化核心能力
- Provider Health 面板 — 运维增强
- 本地体检脚本 — 运维增强
- 产品化收口 — 文档

### 依赖真实 API Key

- E2E 验收脚本 — 需要 SerpAPI/Bing/OpenAI key 才能跑完整验证，但无 key 时 skipped 不影响 CI

### 部署/运维增强

- Provider Health 面板 — 运行时状态可视化
- 本地体检脚本 — 部署后快速体检
- E2E 验收脚本 — CI/CD 集成验收

---

## Phase 5 未涉及（留给后续阶段）

| 方向 | 说明 | 建议阶段 |
|------|------|----------|
| 前端 DAG 编辑器 | 从表单升级为图形化配置 nodes/edges | Phase 6 |
| 多用户权限 | 用户认证、团队协作 | Phase 6 |
| Docker 生产配置 | docker-compose.prod.yml、CI/CD | Phase 6 |
| 跨 Mission 协作 | 图模板跨任务数据传递 | Phase 6 |
| 图版本历史 | Graph Template 版本管理 | Phase 6 |
