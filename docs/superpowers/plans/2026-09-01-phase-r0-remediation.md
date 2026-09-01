# Phase R0 Remediation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task with review checkpoints.

**Goal:** Make `backend/core_app.py` the single supported application entry point, retain Boss Command Center governance flows, and remove the obsolete Commander, swarm, marketplace, Feishu, and high-risk Agent execution surfaces without leaving executable callers behind.

**Architecture:** Preserve Boss router/service implementations and their public URLs, mounting them from the core application alongside the existing governance, collaboration, MiniDelivery, and core-agent routers. Remove obsolete execution surfaces only after repository-wide callers are either removed with their UI/tests or explicitly migrated to supported Boss/core capabilities. Keep startup and deployment references pointed at `backend.app:app`, where `backend/app.py` becomes the completed core application.

**Tech Stack:** Python 3, FastAPI, pytest, React/TypeScript, npm, Docker/Uvicorn.

**Spec:** `/Users/mac/Downloads/CODEX-execution-brief.md`, Phase R0, expanded by the dependency findings recorded in the execution report.

## Global Constraints

- Execute only Phase R0 on branch `remediation/phase-r0`.
- Do not change Boss business logic, template definitions, or governance semantics.
- Preserve Boss route URLs and request/response formats.
- Do not delete `research_agent`, `marketing_agent`, `image_agent`, `data_agent`, or `website_agent`.
- Remove executable imports/callers for deleted surfaces; comments and migration records may mention historical names.
- Do not modify `main` or use rebase, reset, amend, squash, force push, or Phase 2 work.
- Run focused tests during implementation and the R0 acceptance checks at the end; do not hide failures by weakening assertions.

### Task 1: Capture current route and dependency inventory

**Files:**
- Read: `backend/app.py`, `backend/core_app.py`, `backend/routers/boss_router.py`, `backend/services/boss_command_center.py`
- Read: all repository callers discovered by `rg` for Commander, swarm, marketplace, Feishu/Lark, and six deleted Agent IDs
- Test: existing route and Boss tests used as compatibility reference

- [ ] **Step 1: Enumerate Boss routes and dependencies**

  Record the router exports, service imports, governance dependencies, and route paths required to mount Boss unchanged.

- [ ] **Step 2: Enumerate all deleted-surface callers**

  Search `backend/`, `agents/`, `core/`, `tests/`, `frontend-new/src/`, and startup/deployment files. Classify each hit as executable import/call, UI/API consumer, test, configuration, or documentation.

- [ ] **Step 3: Stop on unresolved ownership**

  If a caller cannot be removed or mapped to a supported route without changing product behavior, record its exact file and symbol and pause for confirmation.

### Task 2: Promote the core application entry point

**Files:**
- Modify: `backend/core_app.py`
- Modify: `backend/app.py`
- Modify: `main.py`, `start.sh`, `start.bat`, `Dockerfile`
- Test: `tests/test_core_app.py` and Boss route tests

- [ ] **Step 1: Add Boss router and required core-compatible startup behavior**

  Import and include `boss_router` in `core_app.py` without changing its implementation. Preserve `/health` and existing core routers.

- [ ] **Step 2: Compare full-app middleware and route dependencies**

  Move only required non-legacy initialization and middleware behavior into the core entry point; do not copy Commander, workflow, pipeline, swarm, marketplace, or Feishu routers.

- [ ] **Step 3: Make `backend/app.py` the supported entry module**

  Preserve the import path `backend.app:app` for deployment while replacing the old app surface with the completed core app implementation. Keep the old app recoverable until import and focused route checks pass.

- [ ] **Step 4: Update launch references**

  Ensure `main.py`, `start.sh`, `start.bat`, `Dockerfile`, and compose/runtime configuration reference only the supported app entry point.

### Task 3: Remove obsolete backend execution surfaces and callers

**Files:**
- Delete: `backend/commander/`, `backend/routers/commander_router.py`, `backend/routers/agent_market_router.py`, `backend/routers/swarm_router.py`, `core/agent_swarm.py`, `core/agent_marketplace.py`, `backend/routers/feishu_router.py`
- Delete: `agents/system_agent/`, `agents/codex_agent/`, `agents/openclaw_agent/`, `agents/qa_agent/`, `agents/cto_agent/`, `agents/video_agent/`
- Modify or delete callers: `core/commander_manager.py`, `core/cron_scheduler.py`, `core/workflow/engine.py`, `core/agent_protocol.py`, `backend/services/agent_loader.py`, `backend/services/doctor.py`, `backend/services/delivery_pipeline.py`, `backend/services/pdf_service.py`, `backend/services/export_service.py`, `backend/services/usage_stats.py`, `backend/services/logger.py`, `backend/ai_registry/registry.py`, `backend/adapters/local_module_adapter.py`, `backend/adapters/openclaw_adapter.py`, `backend/routers/workflow_router.py`, `backend/routers/cto_router.py`, `backend/routers/metrics_router.py`, `backend/routers/commander_manager_router.py`, `backend/services/feishu_bot.py`, `backend/config.py`, and route-policy/middleware files with executable legacy references

- [ ] **Step 1: Remove route registrations before deleting implementations**

  Remove obsolete router imports and `include_router` calls from the supported app. Preserve unrelated supported routers.

- [ ] **Step 2: Remove or migrate direct imports and registries**

  Delete registry entries and lazy imports for removed Agents. Remove scheduler, workflow, delivery, adapter, and provider paths that would import deleted modules. Do not replace them with arbitrary execution behavior.

- [ ] **Step 3: Remove Feishu bridge dependencies**

  Delete the Feishu router/service integration and its configuration only where no supported runtime consumer remains; remove the Commander chat callback dependency rather than redirecting it silently.

- [ ] **Step 4: Remove obsolete policy, limits, and metadata entries**

  Remove policies and rate/tier entries for routes that no longer exist. Preserve policies for supported routes.

- [ ] **Step 5: Delete implementation directories**

  Delete the specified Commander, swarm, marketplace, Feishu router, and six Agent directories only after import scans are clean.

### Task 4: Remove obsolete UI and tests

**Files:**
- Modify or delete: `frontend-new/src/app/routes.tsx`, `frontend-new/src/app/routes.tsx`, `frontend-new/src/api/client.ts`, `frontend-new/src/components/layout/sidebar.tsx`, `frontend-new/src/pages/index.ts`, `frontend-new/src/pages/commander/`
- Delete or modify tests that only exercise removed surfaces, including Commander, deleted Agents, swarm, marketplace, Feishu, and legacy workflow-only tests

- [ ] **Step 1: Remove Commander UI/API navigation**

  Remove lazy routes, sidebar entries, API methods, and page exports for deleted Commander functionality. Keep supported Boss UI paths intact.

- [ ] **Step 2: Remove tests whose subject no longer exists**

  Delete tests only when they exclusively test a deleted module or route. Update mixed tests to cover supported behavior without weakening unrelated assertions.

- [ ] **Step 3: Search for historical callers again**

  Run repository-wide searches and inspect every remaining executable hit. Documentation-only mentions may remain; executable imports/calls may not.

### Task 5: R0 acceptance verification

**Files:**
- Modify: only files required to correct verified R0 failures

- [ ] **Step 1: Verify forbidden executable references are absent**

  Run targeted `rg` scans over `backend/`, `agents/`, `core/`, `frontend-new/src/`, and tests, excluding comments/docs only when the scan result is manually inspected.

- [ ] **Step 2: Verify application startup and health**

  Import `backend.app:app` and run the project-supported health probe without requiring external credentials.

- [ ] **Step 3: Verify Boss route compatibility**

  Run focused Boss route, template, governance, and runtime acceptance tests.

- [ ] **Step 4: Run required test/build checks**

  Run pytest according to the R0 acceptance scope and `cd frontend-new && npm run build`; record passed, failed, and skipped counts. Do not repair historical baseline/flaky failures outside R0.

- [ ] **Step 5: Final clean-state review**

  Check `git status --short`, inspect the complete diff, confirm no Phase R1/R2/R3 changes, and produce the Phase R0 execution report. Stop and wait for human confirmation.
