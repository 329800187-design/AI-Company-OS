# AI Company OS Progress Snapshot — 2026-07-03

## Current Position

The project has moved from a broad AI-company prototype into a Core v0.1 freeze phase.

Core is now the lower-level runtime foundation for controlled execution:

- Governance: unified goal classification, route policy, execution planning, and run records.
- Agent platform: manifest registration, discovery, enable/disable controls, unified executor.
- Collaboration: multi-step agent plans, step persistence, review/resume/retry, timeline events.
- Risk gate: high-risk agent checks, confirmation flow, sandbox-required flow.
- MiniDelivery: deterministic artifact generation, verification, result.json, artifact reading.
- Core app: a small `backend.core_app` entrypoint that avoids loading legacy Boss/Workflow/Pipeline routes.

The current product direction is:

> Agent orchestration framework + business workbench + artifact delivery system.

## 当前阶段

**五个业务入口 Agent-first + MiniDelivery v1 可用**

2026-07-03 完成状态：
- 五个业务页面（营销/图片/数据/调研/网站）全部接入 Agent-first 执行流程
- MiniDelivery v1 阶段冻结：Agent 产物保存 / 查看 / 下载闭环可用
- 详见 `docs/minidelivery_v1_freeze.md`

## Progress Against The Target

Estimated status:

- Agent orchestration framework: about 70%.
- Business workbench: about 50%.
- Artifact delivery system: about 65%.
- Overall system: about 60%.
- Core v0.1 readiness: about 85-90%.

The system is no longer just a toy prototype, but it is not yet a stable end-user product.

## What Works Now

- 五个业务入口全部接入 Agent-first 流程：
  - 营销文案页 → Marketing Agent → 保存到交付中心
  - 图片提示词页 → Image Agent → 保存到交付中心
  - 数据分析页 → Data Agent → 保存到交付中心
  - 调研分析页 → Research Agent → 保存到交付中心
  - 网站落地页 → Website Agent → 保存到交付中心
- MiniDelivery v1 可用：save-from-agent → 列表 → 详情 → 预览 → 下载 → 搜索/筛选/分页
- 6 种产物类型：小红书文案包、抖音文案包、图片提示词包、调研简报、落地页文案、数据报告
- The recommended execution entrypoint is `POST /governance/run`.
- Supported artifact loops include copy packs, image prompt packs, research briefs, landing page copy, and data-report scaffolds.
- Collaboration plans can be built, executed, reviewed, resumed, retried, and inspected.
- High-risk agent execution now goes through a risk gate.
- `sandbox_required` approve no longer skips execution; it routes to the sandbox adapter path.
- Core-related backend tests have passed locally:
  - `tests/test_agent_risk_gate.py tests/test_collaboration_plan.py`: 105 passed.
  - `tests/test_governance.py tests/test_minidelivery.py tests/test_collaboration_plan.py tests/test_core_app.py`: pytest reported 493 passed, 2 warnings.

## Important Caveats

- `run_in_sandbox()` is still a v0 placeholder, not a real sandbox.
- Frontend-to-backend product polish is incomplete: error states, naming, result display, and report workflows still need tightening.
- Several pages produce structured Markdown artifacts rather than performing full real-world automation.
- The full app still contains many legacy routes. Core mode avoids these, but full app cleanup is not finished.
- The current local repository has no GitHub remote configured.
- There are many unstaged and untracked changes. They should be reviewed and split before committing.

## Recent Major Changes

- 五个业务页面全部接入 Agent-first 执行流程，替代旧的 Governance 直连模式。
- MiniDelivery v1 阶段冻结：Agent 产物保存/查看/下载闭环完成，不再新增功能。
- Added MiniDelivery v1 freeze document (`docs/minidelivery_v1_freeze.md`)。
- Added `SaveToDeliveryButton` 组件，5 个业务页面复用。
- Added `/delivery` 交付中心列表页，支持搜索/筛选/分页/预览/下载。
- Shifted the recommended system entrypoint from legacy Boss/Workflow/Pipeline paths to Governance.
- Added Core v0.1 documents, quickstart, freeze audit, and distribution manifest.
- Added a lightweight `backend.core_app` for distributable Core mode.
- Added Governance, MiniDelivery, Collaboration, Agent manifest/protocol/executor, and risk-gate modules.
- Connected many `frontend-new` pages to the Governance flow.
- Added report/artifact viewing paths.
- Added API-level regression coverage for `sandbox_required` approval.
- Cleaned root-level temporary test/debug scripts from the workspace.

## Next Work

MiniDelivery v1 已冻结，不再新增功能。下一阶段候选项见 `docs/minidelivery_v1_freeze.md`。

Do not add major new capabilities before the v0.1 freeze is clean.

Recommended order:

1. Review and stage Core backend changes.
2. Review and stage Agent platform and Collaboration changes.
3. Review and stage frontend Governance/workbench changes.
4. Review and stage tests and docs.
5. Keep temporary local data, generated artifacts, prompt scratch files, and ad-hoc learned files out of release commits.
6. Configure a GitHub remote and push a review branch.

## GitHub Upload Checklist

If this repository has not been connected to GitHub yet:

```powershell
git remote add origin https://github.com/<your-user-or-org>/<repo-name>.git
git branch -M main
git push -u origin main
```

Recommended safer flow for the current large change set:

```powershell
git switch -c codex/core-v0.1-freeze
git add <reviewed-files>
git commit -m "core: freeze v0.1 runtime foundation"
git push -u origin codex/core-v0.1-freeze
```

Before pushing, run:

```powershell
python -m pytest tests/test_governance.py tests/test_minidelivery.py tests/test_collaboration_plan.py tests/test_core_app.py -q
python -m pytest tests/test_agent_risk_gate.py tests/test_collaboration_plan.py -q
cd frontend-new
npm run build
```
