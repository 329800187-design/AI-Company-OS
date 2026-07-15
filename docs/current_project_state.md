# Current Project State

Last updated: 2026-07-14

## Current Goal

AI Company OS is being corrected back to its original direction:

**A generic AI business process execution system.**

It must not become a Xianyu, ecommerce, Xiaohongshu, SEO, landing-page, SaaS, or any other single-domain tool. All systems, templates, modules, prompts, UI copy, reports, tests, and docs should treat concrete industries as user input, examples, compatibility aliases, or optional plugins only.

## Hard Rules

- The core system must fit all business workflows.
- Business differences enter through user input, template parameters, context schema, review checklist, and optional configuration.
- Core templates must use `template_type = "generic_business_process"` and `domain_lock = false`.
- Do not add new default flows that hard-code a specific business, channel, platform, or artifact type.
- Old business IDs may exist only as compatibility aliases.
- Old specialized executors must not run by default.
- User review is required: generate plan -> human confirm -> execute once -> human review/accept.
- Do not restore automatic loops, automatic QA reassignment, or auto retry chains.

## Boss Execution Status

The Boss Command Center execution loop has been corrected through Phase 6.22.

### Completed Phases

| Phase | Status | Meaning |
|---|---|---|
| 6.13 | Done | `create_mission` defaults to `pending_review`; `auto_run` is ignored; user must confirm execution; user must accept results. |
| 6.14 | Done | Stale running cleanup marks timed-out modules as `partial` or `interrupted` without deleting data. |
| 6.15 | Done | Frontend polling shows live module progress while execution is running. |
| 6.16 | Done | Module-level timeout marks interrupted modules and stops later modules. |
| 6.16.1 | Done | Late-result CAS protection prevents stale thread results from overwriting interrupted states. |
| 6.16.2 | Done | `ThreadPoolExecutor.shutdown(wait=False)` prevents timeout paths from blocking requests. |
| 6.17 | Done | Governance test bypass is opt-in for pytest; Boss test DB cleanup added. |
| 6.18 | Done | Boss main flow E2E tests added with mocked API routes. |
| 6.19 | Done | Boss templates changed to generic business process protocol. |
| 6.20 | Done | Legacy aliases are canonicalized; legacy business executors are disabled by default. |
| 6.21 | Done | Boss Lite visible names changed to generic capability names. |
| 6.22 | Done | Boss Lite backend prompts and reports mostly cleaned of domain-locked terms. |

## Generic Template Protocol

The active template protocol is `PROTOCOL_VERSION = "1.0"` in `backend/services/boss_command_center.py`.

Each core template must include:

- `protocol_version`
- `template_type = "generic_business_process"`
- `domain_lock = false`
- `default_goal`
- `default_modules`
- `suggested_inputs`
- `expected_outputs`
- `input_fields`
- `context_schema`
- `review_checklist`

### Current Generic Templates

| Template ID | Name | Purpose |
|---|---|---|
| `goal_to_plan` | 目标到计划 | Turn a goal into strategy, context, and executable plan. |
| `research_to_decision` | 调研到决策 | Gather context and compare options for a decision. |
| `deliverable_pack` | 交付物生成 | Produce structured deliverables around a delivery goal. |
| `communication_plan` | 沟通与触达方案 | Design audience, message, channel, and communication plan. |
| `operation_review` | 流程复盘 | Review completed work and produce improvement actions. |
| `risk_check` | 风险检查 | Identify risks and mitigations for a plan or decision. |
| `execution_checklist` | 执行清单 | Break work into steps, checks, and acceptance criteria. |
| `data_insight` | 数据洞察 | Analyze data or indicators and find actions. |

### Legacy Alias Mapping

Old business template IDs are supported only through `TEMPLATE_ALIASES`.

| Old ID | Canonical Template |
|---|---|
| `ecommerce_product_research` | `research_to_decision` |
| `xianyu_listing_pack` | `deliverable_pack` |
| `saas_feature_planning` | `goal_to_plan` |
| `landing_page_offer` | `deliverable_pack` |
| `weekly_business_review` | `operation_review` |
| `xianyu_delivery_pack` | `deliverable_pack` |

Important behavior:

- `get_template(old_id)` may return a compatibility object with `aliased_to`.
- `create_mission_from_template(old_id)` must store the canonical template ID in `mission.template_id`.
- The original alias may be recorded in a `template_aliased` event payload.
- The old ID must not control executor selection.

## Generic Module Layer

The module IDs are preserved for compatibility, but their meaning is generic:

| Module ID | Generic Name |
|---|---|
| `strategy` | 目标理解与策略判断 |
| `market` | 上下文与证据整理 |
| `marketing` | 沟通与触达方案 |
| `landing` | 交付物结构 |
| `actions` | 执行计划 |

Do not rename these IDs casually; existing data and frontend logic depend on them. Rename visible copy and prompts instead.

## Boss Lite Generic Capability Names

Boss Lite still uses the internal agent IDs for compatibility, but visible names must stay generic:

| Agent ID | Visible Name |
|---|---|
| `research` | 上下文整理 |
| `marketing` | 沟通表达 |
| `image` | 素材方向 |
| `data` | 数据洞察 |
| `website` | 交付物结构 |

The backend source is `backend/routers/boss_router.py`.

Prompt/report terms already corrected in Phase 6.22:

- `上下文调研简报` -> `上下文整理简报`
- `视觉方案` -> `素材方向建议`
- `数据分析框架` -> `数据洞察框架`
- `页面目标` -> `交付目标`
- `首屏标题` -> `核心标题`
- `SEO 建议` -> `检索展示建议`

## Legacy Executor Policy

Specialized ecommerce executors remain defined for backward compatibility, but must not be active by default.

In `backend/services/boss_module_executors.py`:

- `_EXECUTOR_REGISTRY` is empty by default.
- Legacy executors register only when `ACO_ENABLE_LEGACY_BUSINESS_EXECUTORS=true`.
- Default behavior for all generic templates is `DefaultModuleExecutor`.

## Current Known Residuals

Phase 6.23 is still pending. Do this before adding new features.

Known residuals from the latest audit:

- `frontend-new/src/pages/boss/index.tsx` still has visible labels like `页面目标` and `首屏标题` in `extractKeyFields`.
- `frontend-new/src/pages/boss/index.tsx` default DAG draft still has `上下文调研`.
- `README.md` still has old wording such as `落地页文案和页面方案` and old agent role descriptions in some places.

These are not backend execution blockers, but they keep the product memory tied to old marketing/landing-page language.

## Next Required Task: Phase 6.23

Phase 6.23 should clean frontend details and README residuals only.

Scope:

- `frontend-new/src/pages/boss/index.tsx`
- `README.md`
- tests if helpful

Replace visible copy:

- `页面目标` -> `交付目标`
- `首屏标题` -> `核心标题`
- `页面板块` -> `交付板块`
- `上下文调研` -> `上下文整理`
- `营销方案` / `营销文案` -> `沟通表达`
- `落地页` -> `交付物结构`
- visible `SEO` -> `检索展示`

Do not rename compatibility field names like `page_goal`, `hero`, `seo`, or `landing_page_copy` unless there is a separate migration plan.

Recommended validation:

```bash
python -m pytest tests/test_boss_command_center.py -q
cd frontend-new && npm run build
npx playwright test e2e/boss-flow.spec.ts
```

## Recent Verification Reported

Claude reported these results after Phase 6.22:

- `python -m pytest tests/test_boss_command_center.py -q` -> 145 passed
- `npm run build` -> passed
- `npx playwright test e2e/boss-flow.spec.ts` -> 5 passed

DAG editor E2E had known pre-existing failures in some runs; do not treat those as caused by the genericization work unless reproduced after a clean build/server restart.

## Collaboration Notes

When asking Claude/Hermes to continue:

- State the phase number.
- State that the system must remain generic across all business workflows.
- Ask for modified files, behavior changes, tests, and remaining risk.
- Do not accept "internal only" as a reason to keep domain-locked prompt text; prompts shape model output.

When reviewing:

- Inspect real files, not only summaries.
- Search for domain-locked terms in backend prompts, frontend visible copy, README, and tests.
- Distinguish internal compatibility field names from visible product language.
