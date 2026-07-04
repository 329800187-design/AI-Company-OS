# Current Project State

Last updated: 2026-07-02

## 当前架构

**主入口：`/governance/run`** — 所有任务执行统一走此入口。

| 功能 | 入口 | 说明 |
|------|------|------|
| **首页** | 智能任务 / 写文案 / 做图片 / 做调研 | 直接跳转到对应功能页 |
| **Agent 管理** | `/agent-console/discovered` | 启用/禁用 Agent |
| **协同执行** | 由 Governance 调用 collaboration | 不推荐用户直接调 `/collaboration/run` |
| **报告中心** | Governance/Collaboration 历史 | 查看运行记录和产物 |

### 主入口清单

| 页面 | 推荐路径 | 状态 |
|------|----------|------|
| 首页 → 智能任务 | `/governance/run` | ✅ 主入口 |
| 首页 → 写文案 | `/governance/run` | ✅ 主入口 |
| 首页 → 做图片 | `/governance/run` | ✅ 主入口 |
| 首页 → 做调研 | `/governance/run` | ✅ 主入口 |
| Agent 控制台 | `/agent-console/discovered` | ✅ Agent 启用管理 |
| 报告中心 | Governance/Collaboration 历史 | ✅ 查看历史 |

### Legacy/Protected 入口

| 页面 | 路由 | 状态 |
|------|------|------|
| Boss 指挥台 | `/boss/*` | ⚠️ 保留但不推荐 |
| 工作流 | `/workflow/*` | ⚠️ 保留但不推荐 |
| 任务中心 | `/missions` | ⚠️ 保留但不推荐 |
| Agent 旧执行 | `/agents/*/run` | ⚠️ 保留但不推荐 |

The verified loop is:

1. User enters a goal in the frontend.
2. Frontend calls `POST /governance/run`.
3. Governance classifies and blocks unsupported goals.
4. Supported copy-pack tasks run through `backend/minidelivery`.
5. The system writes a Markdown artifact and `result.json`.
6. Frontend calls `GET /governance/runs/{run_id}/artifact`.
7. The generated artifact is displayed in the page.

## Working Entrypoints

- Dev validation page: `http://127.0.0.1:8000/governance/test-page`
- Formal frontend: `http://127.0.0.1:8000/app?page=governance`
- Formal frontend fallback: `http://127.0.0.1:8000/app#governance`
- Main API: `POST /governance/run`
- Artifact API: `GET /governance/runs/{run_id}/artifact`

## Supported Capabilities

Currently executable:

- `copy_pack.xiaohongshu`
- `copy_pack.douyin`
- `image_prompt_pack`
- `research_brief`
- `landing_page_copy`
- `data_report`

Known but not executable yet:

- `product_listing`
- `content_calendar`
- `analysis_report`
- `competitor_report`
- `image_prompt_pack`
- `sop_doc`
- `campaign_plan`
- `email_sequence`
- `landing_page_copy`

Unsupported artifact types must return `unsupported.artifact_type` and must not execute.

## Governance Status

- Old high-risk execution routes are guarded or deprecated.
- Deprecated workflow/template/commander-continue routes remain blocked.
- No default fallback to `xiaohongshu` is allowed.
- Explicit `platform` must not bypass vague or dangerous goal blocking.
- Artifact reading is restricted to `output/minidelivery` via resolved path checks.

## Frontend Status

- `frontend-new` is the formal frontend.
- The Governance page exists and can generate/display artifacts.
- The original `marketing` / "写文案" page now uses the Governance loop.
- The original `image` / "做图片" page now generates `image_prompt_pack` Markdown artifacts. It does not call a real image model yet.
- The original `commander` / "智能任务" page now uses the Governance loop as a controlled main-brain entry point.
- The original `research` / "做调研" page now uses the Governance loop as a controlled artifact entry point, generating `research_brief` Markdown artifacts.
- The original `website` / "建网站" page now uses the Governance loop as a controlled artifact entry point, generating `landing_page_copy` Markdown artifacts.
- The original `templates` / "场景模板" page now uses the Governance loop as a controlled artifact entry point, with built-in templates for `copy_pack.xiaohongshu`, `copy_pack.douyin`, `image_prompt_pack`, `research_brief`, and `landing_page_copy`.
- The original `data` / "看数据" page now uses the Governance loop as a controlled artifact entry point, generating `data_report` Markdown artifacts. It currently produces a report framework/summary, not real Excel/CSV parsing.
- The original `reports` / "报告中心" page now shows the list of recent Governance runs and their artifacts, replacing the old boss mission export view.
- `frontend-new/index.html` uses `lang="zh-CN"` and disables auto-translation to avoid React DOM crashes.
- After each frontend build, restart the backend so `/app` reloads the latest `dist/index.html`.

## Next Recommended Step

进入 v0.1 冻结阶段。

Do not add new capabilities until the current worktree has been audited and staged.

Recommended next work:

- Review `docs/v0.1_freeze_audit.md`.
- Keep Governance, MiniDelivery, Collaboration, Agent Manifest/Executor, recommended frontend pages, and their tests as the v0.1 core.
- Review temporary root scripts, local runtime data, learned skill files, old frontend deletions, and broad legacy backend edits before staging.
- Prefer separate commits for core backend, agent platform, frontend, docs, and tests.

Recommended validation before committing:

- `python -m pytest tests/test_governance.py tests/test_minidelivery.py tests/test_collaboration_plan.py -q`
- `cd frontend-new && npm run build`
- `python -c "import backend.app; print('ok')"`
