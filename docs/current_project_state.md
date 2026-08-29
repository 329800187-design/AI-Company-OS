# Current Project State

Last updated: 2026-08-29

## Capability Runtime Convergence — Phase 1

Status: COMPLETE for Phase 1 Closure on `codex/capability-runtime-convergence`; pending architecture acceptance.

- `AIRegistry.scan_runtime_capabilities()` is the canonical entry point for the runtime capability snapshot; scanner observations are exposed through its `resources` projection.
- Agent Discovery is a compatibility projection for canonical Agent/LLM resources and retains only MCP/project-specific discovery metadata.
- `core/capability_scanner.py` is a compatibility facade with no independent cache or state model.
- Resource taxonomy distinguishes `agent`, `llm_provider`, `local_tool`, `browser`, and `local_service`.
- Readiness is derived centrally from discovery, availability, configuration, verification, adapter, and authorization prerequisites; `ready` is not equivalent to `available`.
- Runtime state is resolved under the user-level application data directory. Legacy database and enabled-agent locations are copied without deletion or overwriting an existing new database.
- Migration behavior is covered for fresh, legacy-only, new-only, both-present, rerun, macOS, Windows, and Linux path semantics.
- Phase 1 targeted backend tests currently pass: 86 passed, 1 skipped in the convergence suite; runtime migration fixtures pass for fresh, legacy-only, new-only, both-present, rerun, and platform path semantics.
- Frontend typecheck, production build, and lint pass. Agent Console E2E passes after starting the backend health endpoint.
- Full backend regression is 1617 passed, 15 failed, 7 skipped; all 15 failures reproduce on the GitHub baseline and are not introduced by this branch.
- Agent Console E2E passes with the formal backend health endpoint running; canonical projection identity/status/readiness equality was verified across Agent Console and Core Agent routes.
- No Phase 2 work is included.

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
| 6.23 | Done | Frontend boss page visible copy cleaned (页面目标→交付目标, 首屏标题→核心标题, 上下文调研→上下文整理, 营销方案→沟通表达, 落地页→交付物结构, SEO→检索展示). |
| 6.24 | Done | README and residual docs cleaned of domain-locked terms; generic framing verified. |

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

## Phase Status

### Phase 6 — Generic Correction: COMPLETE
Phases 6.13–6.24 are all Done, including 6.23/6.24 frontend + README residual cleanup (shipped via the Phase 6 squash merge). The product is now a generic AI business-process execution system; no domain-locked terms remain in prompts, visible copy, or docs.

### Phase 7C — Test Baseline Zero: COMPLETE
All Phase 7C assertion-baseline fixes are merged (PR #8, squash commit `94f3a3f` on main). Full pytest: **1577 passed, 0 failed, 6 skipped**. CI (test + docker) green.

### Phase 7D — Deploy & One-click Verify: IN PROGRESS

Completed locally on 2026-08-11:

- Added the deployment/runbook doc for local and Docker operation.
- Added cross-platform one-click verification (`verify.bat`, `verify.sh`, `scripts/verify_deployment.py`).
- The verifier checks environment versions, backend import, frontend production build, ephemeral backend health, core API smoke, MiniDelivery and PDF routing.
- Added an incremental SQLite metadata index for MiniDelivery task listings. With 5,814 historical deliveries, the deployment healthcheck now completes in about 3.7 seconds instead of timing out after a 56.7-second full JSON scan.
- Updated local start scripts and Docker to build `frontend-new` instead of relying on an ignored, pre-existing `dist` directory.
- Local Phase 7D verification: **9 passed, 0 failed**; backend smoke: **11 passed, 0 failed**; deployment healthcheck: **4 passed, 0 failed**.

Re-verified locally on 2026-08-16:

- `python scripts/verify_deployment.py`: **9 passed, 0 failed, 0 warnings, 0 skipped**; its backend smoke subcheck is now **14 passed, 0 failed**.
- Full `pytest -q --maxfail=1`: **1599 passed, 0 failed, 7 skipped** in 14m45s.
- Optional local integrations now degrade deterministically: an unconfigured CC Switch credential skips its external chat check; a broken `llama-cpp` native DLL is reported as unavailable; browser tests skip only when their public remote target cannot complete.
- Image fallback responses now retain real-render setup guidance, and invalid research output with no evidence reports both the content and missing-source causes.

Remaining before Phase 7D can be marked complete:

- Run `verify.bat` from a clean Windows checkout or release archive.
- Run `verify.sh` from a clean Linux or macOS checkout.

Completed Docker verification on 2026-08-17:

- The revised multi-stage image `ai-company-os-app:latest` built successfully. Docker Desktop returned a final build-status `rpc EOF`, but the image was exported and usable.
- `docker compose up -d` started both `aios-app` and `aios-nginx`; the app healthcheck became `healthy`.
- The public Compose entrypoint returned HTTP 200 for both `http://localhost/health` and `http://localhost/app`.

Do not rename compatibility field names like `page_goal`, `hero`, `seo`, or `landing_page_copy` unless there is a separate migration plan.

### Phase 8 - Operating-Memory Closed Loop: IN PROGRESS

Completed locally on 2026-08-15:

- A Boss Mission now writes a bounded, structured operating-memory record only after a human accepts it. The record contains the goal, review comment, completion metrics, module conclusions, and next actions, not raw artifacts or tool traces.
- Later Boss module execution retrieves only relevant, human-accepted Boss records and supplies them as advisory context. The prompt explicitly requires current facts to be rechecked.
- Commander now passes shared skill and memory context into its CEO and fallback planners; previously it retrieved those values but did not use them.
- A human can record an observed outcome after acceptance (`improved`, `unchanged`, `worse`, or `inconclusive`), with optional real metrics and a review note. The observation updates the accepted-mission memory and is visible in the Boss operating overview.
- The Boss command-center UI now shows accepted deliveries, observed outcomes, and feedback coverage, and offers an in-context human outcome form for completed Missions.
- Memory is non-blocking: an unavailable memory store records an event but cannot undo a user's acceptance decision.

Still needed for the original "continuous company" vision:

- Connect verified external actions and real business-data feedback, rather than primarily local/mock/template execution.

### Phase 8.1 - Governed Actions & KPI Return: COMPLETE (local simulation)

Completed locally on 2026-08-20:

- Accepted Missions can propose a generic action only after human delivery acceptance.
- Every action follows `pending_approval -> approved -> executed`; approval never auto-executes it, and execution is exactly once with an auditable receipt.
- The only default connector is `local_simulation`. It records an execution-shaped receipt and payload digest but never contacts an external system or creates external side effects.
- Human KPI observations can be attached to an accepted Mission (and optionally its action), are persisted with source `human_entry`, shown in the Boss command center, and added to the bounded operating-memory record.
- Boss overview now reports action and KPI counters. Service regression: `10 passed`; frontend production build passed.

### Phase 8.2 - Shared Memory Governance: COMPLETE

Completed locally on 2026-08-20:

- Operating-memory records now carry retention metadata and support explicit soft retirement. Retired or expired records are excluded from exact recall, search, recent lists, and prompt-context injection.
- A human can set an optional retention period, retire a record with a reason, and run an expiry cleanup without permanently deleting the original database row.
- Memory governance endpoints expose factual active, retired, and expiring counters. Boss overview surfaces the governance state for its shared operating memory.
- Regression coverage validates soft retirement, expiry cleanup, and router behavior; the Phase 8 targeted suite has **13 passed**.

### Phase 8.3 - Human Operating Review Cycles: COMPLETE

Completed locally on 2026-08-21:

- A human can create a collecting operating cycle with an objective, period, and target metrics; it neither schedules work nor performs any action.
- KPI observations enter a cycle only through an explicit human attachment. A review cannot be submitted until at least one observation is attached.
- Each cycle accepts exactly one human conclusion and one decision: `continue`, `adjust`, `pause`, or `complete`. The reviewed conclusion is then retained as a governed, human-accepted Boss operating-memory record; collecting cycles are never written to shared memory.
- The Boss command center exposes the create, attach, and review flow, while the overview reports collecting and reviewed-cycle counts.
- Regression coverage for the Phase 8 suite is **15 passed**; the frontend production build passed.

### Phase 8.4 - Action Preflight Contract: COMPLETE (simulation only)

Completed locally on 2026-08-21:

- Every action connector now declares its mode, credential requirements, whether it needs a preflight, and whether it can have external side effects.
- Proposed actions must pass a connector-owned, non-mutating preflight before human approval. The preflight is persisted and logged separately from the execution receipt.
- The default and only registered connector remains `local_simulation`; its preflight verifies the action shape and explicitly reports that no external system will be contacted.
- The Boss command center shows the required `propose → preflight → approve → execute` sequence. No credentials were added and no real external integration was enabled.
- Regression coverage for the Phase 8 suite is **16 passed**; the frontend production build passed.

### Phase 8.5 - Human Action Cancellation: COMPLETE (simulation only)

Completed locally on 2026-08-21:

- A human can cancel a pending or approved action before execution, but must supply a reason. The cancellation, timestamp, and reason are persisted and logged as an audit event.
- A cancelled action cannot be preflighted, approved, or executed. An executed action cannot be labelled as cancelled; it requires a separate, explicit remediation action instead.
- The Boss command center exposes the cancellation path and makes the recorded reason visible. No external connector or credentials were enabled.
- Regression coverage for the Phase 8 suite is **17 passed**; the frontend production build passed.

### Phase 8.6 - Credential-Safe Action Payloads: COMPLETE (simulation only)

Completed locally on 2026-08-21:

- Action payloads are rejected when field names indicate credentials, including API keys, tokens, passwords, secrets, authorization values, and private keys. The guard examines field names only; it does not inspect, log, or retain the corresponding values.
- Future real connectors must obtain credentials from a dedicated connector configuration boundary, never from an auditable action request, preflight, receipt, or shared operating memory.
- The Boss command center now states this constraint alongside the simulation-only execution workflow.
- Regression coverage for the Phase 8 suite is **18 passed**; the frontend production build passed.

### Phase 8.7 - Expiring Human Action Approval: COMPLETE (simulation only)

Completed locally on 2026-08-21:

- An action approval now has a bounded validity period: 30 minutes by default, configurable through `ACO_ACTION_APPROVAL_TTL_SECONDS` within a safe 1-minute to 24-hour range.
- An expired approval automatically returns the action to `pending_approval`, clears the prior preflight and approval state, and requires a new preflight plus a new explicit human approval before execution.
- Expiry is logged as an audit event and surfaced in the Boss command center alongside the approval expiry time.
- Regression coverage for the Phase 8 suite is **19 passed**; the frontend production build passed.

### Phase 8.8 - Governed Webhook Connector: COMPLETE (disabled by default)

- A generic `webhook` action connector is available only when an HTTPS endpoint and its exact hostname allowlist are both configured in the deployment environment.
- Webhook preflight is strictly local and non-mutating. It validates the HTTPS endpoint and allowlist without contacting the destination.
- Execution remains subject to the existing acceptance, preflight, human approval, expiry, and exactly-once receipt flow. The receipt stores delivery metadata and a payload digest, never the response body or connector credential.
- Credentials may only come from `ACO_WEBHOOK_ACTION_TOKEN`; action payload credential-shaped fields remain rejected.

## Recent Verification Reported

Latest (Phase 7C, main `94f3a3f`):

- Full pytest: **1577 passed, 0 failed, 6 skipped**
- CI: test + docker green (PR #8 merged)
- `npm run build` -> passed
- `npx playwright test e2e/boss-flow.spec.ts` -> 5 passed

Latest local Phase 7D verification (2026-08-11, working tree):

- `python scripts/verify_deployment.py` -> 9 passed, 0 failed
- Backend smoke -> 11 passed, 0 failed
- Deployment healthcheck -> 4 passed, 0 failed
- MiniDelivery index regression -> 22 passed

Latest local Phase 8.3 verification (2026-08-21, working tree):

- `pytest -q tests/test_operating_cycles.py tests/test_boss_operating_memory.py tests/test_memory_governance.py --maxfail=1` -> **15 passed**
- `npm run build` (in `frontend-new`) -> passed

Latest local Phase 8.4 verification (2026-08-21, working tree):

- `pytest -q tests/test_boss_operating_memory.py tests/test_operating_cycles.py tests/test_memory_governance.py --maxfail=1` -> **16 passed**
- `npm run build` (in `frontend-new`) -> passed

Latest local Phase 8.5 verification (2026-08-21, working tree):

- `pytest -q tests/test_boss_operating_memory.py tests/test_operating_cycles.py tests/test_memory_governance.py --maxfail=1` -> **17 passed**
- `npm run build` (in `frontend-new`) -> passed

Latest local Phase 8.6 verification (2026-08-21, working tree):

- `pytest -q tests/test_boss_operating_memory.py tests/test_operating_cycles.py tests/test_memory_governance.py --maxfail=1` -> **18 passed**
- `npm run build` (in `frontend-new`) -> passed

Latest local Phase 8.7 verification (2026-08-21, working tree):

- `pytest -q tests/test_boss_operating_memory.py tests/test_operating_cycles.py tests/test_memory_governance.py --maxfail=1` -> **19 passed**
- `npm run build` (in `frontend-new`) -> passed after one transient system-memory allocation retry

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
