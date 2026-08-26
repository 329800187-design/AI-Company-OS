# Capability Runtime Convergence Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 收敛 AI Company OS 的本机能力发现、Agent 执行、LLM Provider 配置和前端状态，使外部 Agent 优先且所有状态来自同一个能力注册中心。

**Architecture:** 以现有 `backend/ai_registry/registry.py` 为唯一事实源，新增稳定的资源和执行契约；旧扫描接口改为注册中心投影。外部 OpenClaw/Hermes 只有经过专用适配器验证后才能路由，项目内置 Agent 作为显式业务编排和安全回退；Provider 配置保存、连接测试和切换独立处理。

**Tech Stack:** Python 3.14、FastAPI、Pydantic、httpx、pytest、React、TypeScript、Vite。

**Spec:** `docs/superpowers/specs/2026-08-26-capability-runtime-architecture-design.md`

## Global Constraints

- 不回滚或覆盖当前工作区已有的未提交修改；每个任务只提交自己新增或修改的文件。
- 不读取、记录或输出 API Key、Cookie、密码和会话 Token。
- 不进行默认全盘递归扫描；探测范围限于 PATH、已知应用路径、用户级配置、项目 manifest、localhost 端点和进程证据。
- `online`、`configured`、`verified`、`ready` 必须保持语义分离。
- 没有执行适配器的资源不能进入任务路由。
- 外部 Agent 和项目内置 Agent 必须拥有不同的 `origin` 与 `resource_id`。
- 所有真实远程连接只在用户显式触发连接测试或执行任务时发起；单元测试使用 mock transport。
- 每个任务完成后运行该任务列出的测试，并以独立提交保存。

---

### Task 1: Freeze Resource and Execution Contracts

**Files:**
- Create: `backend/ai_registry/contracts.py`
- Modify: `backend/ai_registry/__init__.py`
- Test: `tests/test_ai_runtime_contracts.py`

**Interfaces:**
- Produces `ResourceKind`, `ResourceOrigin`, `ResourceStatus`, `AuthorizationState`, `ExecutionStatus` string enums.
- Produces `LLMBinding`, `Evidence`, `CapabilityResource`, `ExecutionReceipt` Pydantic models.
- Produces `CapabilityResource.is_routable()` and `ExecutionReceipt.safe_dict()`.
- Later tasks consume these types instead of creating ad-hoc dictionaries for canonical registry records.

- [ ] **Step 1: Write contract tests first**

```python
def test_resource_is_not_routable_without_adapter_or_ready_status():
    resource = CapabilityResource(
        resource_id="openclaw",
        name="OpenClaw",
        kind=ResourceKind.AGENT,
        origin=ResourceOrigin.EXTERNAL_RUNTIME,
        status=ResourceStatus.ONLINE,
        capabilities=["browser"],
    )
    assert resource.is_routable() is False


def test_ready_resource_requires_enabled_adapter_and_authorization():
    resource = CapabilityResource(
        resource_id="project_research",
        name="Research Agent",
        kind=ResourceKind.AGENT,
        origin=ResourceOrigin.PROJECT,
        status=ResourceStatus.READY,
        capabilities=["research"],
        adapter_id="project_agent_adapter",
        enabled=True,
        authorization=AuthorizationState.NOT_REQUIRED,
    )
    assert resource.is_routable() is True


def test_execution_receipt_redacts_sensitive_fields():
    receipt = ExecutionReceipt(
        execution_id="exec_test",
        resource_id="deepseek",
        resource_kind=ResourceKind.LLM_PROVIDER,
        adapter_id="provider_adapter",
        status=ExecutionStatus.FAILED,
        error_code="provider_error",
        evidence={"response": "Authorization: Bearer secret"},
    )
    assert "secret" not in str(receipt.safe_dict())
```

- [ ] **Step 2: Run the contract tests and verify failure**

Run: `.venv/bin/pytest -q tests/test_ai_runtime_contracts.py`

Expected: FAIL because `backend.ai_registry.contracts` does not exist.

- [ ] **Step 3: Implement the minimal typed contracts**

Use Pydantic models with default-safe fields. Set `is_routable()` to require `status == READY`, `enabled`, a non-empty `adapter_id`, and either `authorization == NOT_REQUIRED` or `authorization == APPROVED`. Make `safe_dict()` remove credential-like values recursively and preserve stable error codes.

- [ ] **Step 4: Run the contract tests and existing registry tests**

Run: `.venv/bin/pytest -q tests/test_ai_runtime_contracts.py tests/test_ai_registry.py`

Expected: PASS.

- [ ] **Step 5: Commit the contract boundary**

```bash
git add backend/ai_registry/contracts.py backend/ai_registry/__init__.py tests/test_ai_runtime_contracts.py
git commit -m "feat: define capability runtime contracts"
```

### Task 2: Make AIRegistry the Canonical Discovery Source

**Files:**
- Modify: `backend/ai_registry/registry.py`
- Modify: `backend/routers/ai_registry_router.py`
- Modify: `backend/services/capability_scanner.py`
- Modify: `backend/services/agent_discovery.py`
- Modify: `backend/routers/agent_console_router.py`
- Test: `tests/test_capability_registry_projection.py`
- Test: `tests/test_agent_discovery.py`

**Interfaces:**
- `AIRegistry.scan_all(force: bool = False) -> Dict[str, CapabilityResource]` becomes the canonical scan result.
- `AIRegistry.get_resource(resource_id: str) -> Optional[CapabilityResource]` returns one canonical resource.
- `AIRegistry.project_capabilities() -> dict` returns the legacy `/capabilities` shape.
- `AIRegistry.project_discovered_agents() -> dict` returns the legacy Agent Console shape while preserving `kind`, `origin`, `adapter_id`, and `status`.
- Legacy scanners no longer perform independent machine probes.

- [ ] **Step 1: Add projection contract tests**

```python
def test_all_public_views_use_same_resource_ids(client, monkeypatch):
    canonical = client.get("/ai/scan").json()
    capabilities = client.get("/capabilities").json()
    discovered = client.get("/agent-console/discovered").json()

    canonical_ids = {row["resource_id"] for row in canonical["services"]}
    view_ids = {row["id"] for rows in capabilities.values() if isinstance(rows, list) for row in rows}
    discovered_ids = {row["id"] for row in discovered["agents"]}

    assert view_ids <= canonical_ids
    assert discovered_ids <= canonical_ids
```

- [ ] **Step 2: Run the projection tests and capture the current failure**

Run: `.venv/bin/pytest -q tests/test_capability_registry_projection.py`

Expected: FAIL or expose missing `resource_id` fields because the existing `/capabilities` and Agent Discovery paths scan independently.

- [ ] **Step 3: Adapt AIRegistry records to the typed contracts**

Wrap current scanners in registry-owned conversion methods. Preserve existing `/ai/scan` response compatibility while adding `kind`, `origin`, `adapter_id`, `authorization`, `execution_ready`, and `evidence`. Keep service-specific metadata such as OpenClaw control UI URLs under `evidence` or `metadata` without exposing credentials.

- [ ] **Step 4: Replace legacy scanning with projections**

Change `backend/services/capability_scanner.py` and `backend/services/agent_discovery.py` so their public methods call `get_registry().scan_all()` and transform canonical resources. Remove their independent HTTP, PATH, and project scans only after equivalent projection tests exist. Update `agent_console_router.py` to return canonical resource status and source data.

- [ ] **Step 5: Verify current local resource coverage**

Run: `curl -sS http://127.0.0.1:8000/ai/scan | jq '.services[] | {service_id,name,kind,status,capabilities}'`

Expected: the same OpenClaw and Ollama identities are visible through `/ai/scan`, `/capabilities`, and `/agent-console/discovered`; no project `openclaw_agent` record is presented as external OpenClaw.

- [ ] **Step 6: Run regression tests and commit the canonical source change**

Run: `.venv/bin/pytest -q tests/test_ai_registry.py tests/test_capability_registry_projection.py tests/test_agent_discovery.py`

Expected: PASS.

```bash
git add backend/ai_registry/registry.py backend/routers/ai_registry_router.py backend/services/capability_scanner.py backend/services/agent_discovery.py backend/routers/agent_console_router.py tests/test_capability_registry_projection.py tests/test_agent_discovery.py
git commit -m "refactor: make AI registry the capability source of truth"
```

### Task 3: Add Explicit External Runtime Probes and Adapter Boundaries

**Files:**
- Create: `backend/adapters/openclaw_gateway_adapter.py`
- Create: `backend/adapters/hermes_runtime_adapter.py`
- Modify: `backend/adapters/openclaw_adapter.py`
- Modify: `backend/ai_registry/registry.py`
- Modify: `backend/config.py`
- Test: `tests/test_external_runtime_adapters.py`

**Interfaces:**
- `OpenClawGatewayAdapter.resource_id = "openclaw_gateway"` and `origin = external_runtime`.
- `HermesRuntimeAdapter.resource_id = "hermes_runtime"` and `origin = external_runtime`.
- Both adapters implement `health_check() -> dict`, `can_handle(task_type: str, task: dict) -> bool`, and `run(task: dict) -> ExecutionReceipt`.
- The existing `OpenClawAdapter` remains explicitly project-local and is renamed in metadata to `project_openclaw_adapter`.

- [ ] **Step 1: Write tests for identity separation and unsupported runtime behavior**

```python
def test_external_openclaw_and_project_openclaw_have_distinct_ids():
    external = OpenClawGatewayAdapter()
    project = OpenClawAdapter()
    assert external.resource_id != project.TOOL_NAME
    assert external.origin == "external_runtime"
    assert project.origin == "project"


def test_hermes_dashboard_only_runtime_is_not_ready(monkeypatch):
    monkeypatch.setattr(HermesRuntimeAdapter, "_probe_task_api", lambda self: False)
    result = HermesRuntimeAdapter().health_check()
    assert result["online"] is True
    assert result["execution_ready"] is False
    assert result["error_code"] == "execution_api_unavailable"
```

- [ ] **Step 2: Run the tests and verify failure**

Run: `.venv/bin/pytest -q tests/test_external_runtime_adapters.py`

Expected: FAIL because the external adapter classes and explicit origins do not exist.

- [ ] **Step 3: Implement safe OpenClaw Gateway probing and execution discovery**

Probe the configured localhost Gateway endpoint and process evidence without treating the Control UI as a task API. Inspect the installed OpenClaw entry point with its documented non-interactive help output during development. Implement only a documented task invocation; if no documented invocation is available, return `unsupported` with `execution_api_unavailable` and keep the resource out of `ready`. Never fall through to `agents.openclaw_agent` from the external adapter.

- [ ] **Step 4: Implement Hermes Runtime probing**

Detect the current Hermes Desktop process and localhost Runtime endpoint. Do not use the existing `HERMES_CLI_PATH=hermes` assumption as proof of availability. Probe only a documented task endpoint; a dashboard response alone produces `online` and `execution_unavailable`. Keep the existing Boss CLI provider as a compatibility path, but mark it unavailable when `shutil.which("hermes")` fails.

- [ ] **Step 5: Register adapters and preserve explicit fallback metadata**

Register external adapters by resource identity. Project-local OpenClaw remains available only as a project resource. When an external adapter fails, the registry returns a receipt with `fallback_used=false`; the higher-level orchestrator may then invoke a declared project fallback and set `fallback_used=true` with the original resource failure.

- [ ] **Step 6: Run adapter, OpenClaw, and browser approval tests**

Run: `.venv/bin/pytest -q tests/test_external_runtime_adapters.py tests/test_openclaw_agent.py tests/test_browser_automation_approval.py`

Expected: PASS; live runtime tests must remain opt-in and must not require a secret token.

- [ ] **Step 7: Commit the external runtime boundaries**

```bash
git add backend/adapters/openclaw_gateway_adapter.py backend/adapters/hermes_runtime_adapter.py backend/adapters/openclaw_adapter.py backend/ai_registry/registry.py backend/config.py tests/test_external_runtime_adapters.py
git commit -m "feat: separate external runtime adapters from project agents"
```

### Task 4: Unify Execution Routing and Receipts

**Files:**
- Modify: `backend/services/agent_router.py`
- Modify: `backend/services/agent_executor.py`
- Modify: `backend/routers/ai_registry_router.py`
- Modify: `backend/routers/agent_router.py`
- Modify: `backend/routers/core_agent_router.py`
- Test: `tests/test_execution_routing_contract.py`

**Interfaces:**
- `AgentRouter.select_resource(task_type: str, message: str, resources: list[CapabilityResource]) -> Optional[CapabilityResource]` consumes canonical records and excludes non-routable resources; the existing `route()` method remains a compatibility wrapper.
- `AIRegistry.execute(service_id: str, payload: dict) -> ExecutionReceipt` must identify the actual resource and adapter.
- `AIRegistry.execute_with_fallback(service_id: str, payload: dict) -> ExecutionReceipt` performs only declared fallback transitions and records the original resource failure.
- Unified Agent endpoints must return the same receipt envelope for project and external resources.

- [ ] **Step 1: Write routing and fallback tests**

```python
from backend.ai_registry.contracts import (
    AuthorizationState,
    CapabilityResource,
    ExecutionReceipt,
    ExecutionStatus,
    ResourceKind,
    ResourceOrigin,
    ResourceStatus,
)
from backend.ai_registry.registry import AIRegistry
from backend.services.agent_router import AgentRouter


def test_router_excludes_online_resource_without_adapter():
    router = AgentRouter()
    candidates = [
        CapabilityResource(
            resource_id="openclaw_gateway",
            name="OpenClaw Gateway",
            kind=ResourceKind.AGENT,
            origin=ResourceOrigin.EXTERNAL_RUNTIME,
            status=ResourceStatus.ONLINE,
            capabilities=["browser"],
            adapter_id=None,
        ),
        CapabilityResource(
            resource_id="project_research",
            name="Research Agent",
            kind=ResourceKind.AGENT,
            origin=ResourceOrigin.PROJECT,
            status=ResourceStatus.READY,
            capabilities=["browser"],
            adapter_id="project_agent_adapter",
            authorization=AuthorizationState.NOT_REQUIRED,
        ),
    ]
    selected = router.select_resource("research", "read a page", candidates)
    assert selected.resource_id == "project_research"


def test_fallback_receipt_contains_original_resource(monkeypatch):
    registry = AIRegistry()
    monkeypatch.setattr(registry, "execute", lambda service_id, payload: ExecutionReceipt(
        execution_id="exec_test",
        resource_id=service_id,
        resource_kind=ResourceKind.AGENT,
        adapter_id="openclaw_gateway_adapter",
        status=ExecutionStatus.UNSUPPORTED,
        error_code="execution_api_unavailable",
    ))
    receipt = registry.execute_with_fallback("openclaw_gateway", {"task_type": "browser"})
    assert receipt.fallback_used is True
    assert receipt.evidence["original_resource_id"] == "openclaw_gateway"
```

- [ ] **Step 2: Run the tests and verify failure**

Run: `.venv/bin/pytest -q tests/test_execution_routing_contract.py`

Expected: FAIL because current routing accepts adapter-less resources and returns different result shapes.

- [ ] **Step 3: Gate candidate selection on canonical readiness**

Update `backend/services/agent_router.py` and registry routing to require `CapabilityResource.is_routable()`. Preserve existing task capability scoring after readiness filtering so this change does not alter unrelated priority behavior.

- [ ] **Step 4: Normalize all execution paths to ExecutionReceipt**

Wrap project Agent results, Provider calls, OpenClaw calls, and Hermes calls in the standard receipt. Map existing `ok`, `success`, `blocked`, and `error` fields into stable statuses and error codes. Retain old response fields only as compatibility fields.

- [ ] **Step 5: Add explicit fallback orchestration**

Only the orchestrator may invoke a fallback. Record the original resource, original adapter error, selected fallback resource, and whether any side effect occurred. Do not fall back from a blocked high-risk action into an unapproved action.

- [ ] **Step 6: Run routing and API regressions**

Run: `.venv/bin/pytest -q tests/test_execution_routing_contract.py tests/test_capability_router.py tests/test_agent_risk_gate.py tests/test_agent_run_result_schema.py`

Expected: PASS.

- [ ] **Step 7: Commit the execution contract**

```bash
git add backend/services/agent_router.py backend/services/agent_executor.py backend/routers/ai_registry_router.py backend/routers/agent_router.py backend/routers/core_agent_router.py tests/test_execution_routing_contract.py
git commit -m "refactor: route only ready resources and return execution receipts"
```

### Task 5: Separate Provider Save, Test, and Switch

**Files:**
- Create: `backend/services/provider_config.py`
- Modify: `backend/config.py`
- Modify: `backend/routers/config_router.py`
- Modify: `core/brain_manager.py`
- Modify: `frontend-new/src/api/client.ts`
- Modify: `frontend-new/src/pages/settings/index.tsx`
- Test: `tests/test_provider_config_contract.py`
- Test: `tests/test_brain_manager.py`

**Interfaces:**
- `normalize_openai_compatible_base_url(provider: str, value: str) -> str` returns a canonical base URL without endpoint duplication.
- `save_provider_fields(provider: str, fields: dict) -> dict` updates only submitted fields and does not switch the active Provider.
- `test_provider_connection(provider: str, transport=None) -> dict` returns `credential_missing`, `verified`, or a stable provider error.
- `switch_provider(provider: str) -> dict` is the only operation that changes the active Provider.

- [ ] **Step 1: Write DeepSeek and save-flow tests**

```python
def test_deepseek_base_url_normalizes_to_v1():
    assert normalize_openai_compatible_base_url("deepseek", "https://api.deepseek.com") == "https://api.deepseek.com/v1"
    assert normalize_openai_compatible_base_url("deepseek", "https://api.deepseek.com/v1/") == "https://api.deepseek.com/v1"


def test_model_only_save_does_not_require_key(client):
    response = client.post("/config/save", json={"deepseek_model": "deepseek-reasoner"})
    assert response.status_code == 200


def test_provider_switch_without_credentials_is_blocked(client):
    response = client.post("/config/switch", json={"provider": "deepseek"})
    assert response.status_code == 400
    assert response.json()["detail"]["code"] == "credential_missing"
```

- [ ] **Step 2: Run the tests and verify the existing failure**

Run: `.venv/bin/pytest -q tests/test_provider_config_contract.py tests/test_brain_manager.py`

Expected: FAIL because `/config/save` currently treats every save containing `ai_provider` as an implicit switch and DeepSeek URLs are not normalized.

- [ ] **Step 3: Implement provider URL normalization and field storage**

Normalize OpenAI-compatible base URLs once, strip endpoint suffixes, and append `/v1` for DeepSeek when absent. Store runtime configuration under the user-level runtime directory resolved by `backend/runtime_paths.py`; environment variables override stored values. Do not write secrets into project-tracked files.

- [ ] **Step 4: Split backend routes**

Keep `/config/save` as a compatibility endpoint that updates submitted fields only. Add explicit `/config/test` behavior using the shared provider service and add `/config/switch` for active Provider changes. Return stable status objects and never return secret values.

- [ ] **Step 5: Update BrainManager to consume normalized config**

Make `_sync_runtime_profiles()` use the shared provider service. Make `_chat_openai_compatible()` append only `/chat/completions` to the canonical base URL. Ensure a Provider is not considered verified merely because a key exists.

- [ ] **Step 6: Update settings UI actions**

Change `handleSave()` to omit `ai_provider` unless the user explicitly selected a switch. Keep the separate test and switch buttons. Display `missing`, `verified`, `invalid`, and `offline` states from the backend.

- [ ] **Step 7: Run provider and frontend checks**

Run: `.venv/bin/pytest -q tests/test_provider_config_contract.py tests/test_brain_manager.py tests/test_provider_health.py`

Run: `npm run build` in `frontend-new`.

Expected: PASS; the build must complete without TypeScript errors.

- [ ] **Step 8: Commit provider configuration changes**

```bash
git add backend/services/provider_config.py backend/config.py backend/routers/config_router.py core/brain_manager.py frontend-new/src/api/client.ts frontend-new/src/pages/settings/index.tsx tests/test_provider_config_contract.py tests/test_brain_manager.py
git commit -m "fix: separate provider configuration testing and switching"
```

### Task 6: Align Frontend Capability Views

**Files:**
- Modify: `frontend-new/src/pages/agent-console/index.tsx`
- Modify: `frontend-new/src/pages/dashboard/index.tsx`
- Modify: `frontend-new/src/pages/settings/index.tsx`
- Modify: `frontend-new/src/api/client.ts`
- Test: `tests/test_frontend_capability_contract.py`

**Interfaces:**
- Frontend API client exposes one canonical capability response and typed projections for Agent, Provider, Tool, and Service.
- Agent Console displays `resource_id`, `kind`, `origin`, `status`, `adapter_id`, `authorization`, and `llm_binding`.
- Dashboard status labels distinguish online, configured, verified, ready, blocked, and unavailable.

- [ ] **Step 1: Add API projection tests**

```python
def test_frontend_payload_contains_source_and_execution_state(client):
    payload = client.get("/agent-console/discovered").json()
    assert all("source" in agent or "origin" in agent for agent in payload["agents"])
    assert all("status" in agent and "runnable" in agent for agent in payload["agents"])
```

- [ ] **Step 2: Update TypeScript types and client methods**

Define `CapabilityResource`, `LLMBinding`, and `ExecutionReceipt` types in `frontend-new/src/api/client.ts`. Keep compatibility parsing for existing fields while making `origin`, `adapter_id`, and canonical `status` available to all pages.

- [ ] **Step 3: Replace stale capability fetches**

Change pages that call `/capabilities` directly to use the canonical client method or its explicit projection. Remove the settings-page Hermes-only health flag and derive service status from the canonical resource list.

- [ ] **Step 4: Render execution semantics clearly**

Show separate labels for online, ready, execution unavailable, blocked, and fallback. Show the actual Agent source and bound Provider/model; do not label a project Agent as OpenClaw or show a configured Provider as verified.

- [ ] **Step 5: Build and inspect the live page**

Run: `npm run build` in `frontend-new`.

Open: `http://127.0.0.1:5173/agent-console`

Verify: OpenClaw, Hermes, project Agents, LLM Providers, and ordinary tools are visually separated and the scan timestamp changes after refresh.

- [ ] **Step 6: Commit the frontend projection changes**

```bash
git add frontend-new/src/pages/agent-console/index.tsx frontend-new/src/pages/dashboard/index.tsx frontend-new/src/pages/settings/index.tsx frontend-new/src/api/client.ts tests/test_frontend_capability_contract.py
git commit -m "feat: show canonical capability runtime state"
```

### Task 7: Platform Regression, Runtime Verification, and Mainline Cleanup

**Files:**
- Modify: `tests/test_boss_hermes_smoke.py`
- Modify: `tests/test_codex_gate_regression.py`
- Modify: `tests/test_core_app.py`
- Modify: `tests/test_system_agent.py`
- Modify: `backend/core_app.py`
- Modify: `agents/system_agent/agent.py`
- Create: `tests/test_runtime_acceptance.py`
- Modify: `scripts/healthcheck_local.py` only if a new acceptance check is required

**Interfaces:**
- Mac acceptance tests do not require Windows `cmd`, PowerShell, `.exe`, or Windows-only route assumptions.
- Hermes smoke tests validate the explicit unavailable/fallback result when no Hermes CLI or Runtime task API exists.
- Runtime acceptance verifies canonical discovery, DeepSeek save semantics, and safe execution receipts without secrets.

- [ ] **Step 1: Reproduce and classify the existing 15 failures**

Run: `.venv/bin/pytest -q`

Record each failure under one of: Hermes provider mock contract, browser approval prompt, stale core app test, or platform-specific System Agent behavior. Do not weaken assertions just to increase the pass count.

- [ ] **Step 2: Repair Hermes test doubles and acceptance semantics**

Make mocked process objects implement the methods used by the current provider, or replace subprocess mocking with an injected process runner. Assert that an unavailable Hermes runtime produces `execution_unavailable` or an explicit fallback, never a successful external execution.

- [ ] **Step 3: Gate platform-specific tests**

Use `pytest.mark.skipif` or platform-specific expected behavior for Windows-only shell commands. Add Mac-native tests using `/bin/sh`, `/bin/echo`, and `open`-safe non-destructive probes where System Agent behavior is intended to be supported.

- [ ] **Step 4: Repair stale core app tests against the current FastAPI route tree**

Update `tests/test_core_app.py` to recursively inspect `APIRoute` entries inside included routers. Remove the two assertions for the obsolete `dist/ai-company-os-core-v0.1-alpha/docs/core_console.html` fixture because `frontend-new` is the supported console surface; retain route inclusion and legacy-route exclusion assertions.

- [ ] **Step 5: Add runtime acceptance tests**

```python
def test_runtime_acceptance_has_canonical_machine_identity(client):
    response = client.get("/ai/scan")
    assert response.status_code == 200
    assert response.json()["count"] >= 1


def test_runtime_acceptance_never_exposes_credentials(client):
    response = client.get("/config/status")
    body = response.text.lower()
    assert "api_key" not in body
    assert "authorization: bearer" not in body
```

- [ ] **Step 6: Run the complete verification set**

Run: `.venv/bin/pytest -q`

Run: `npm run build` in `frontend-new`.

Run: `.venv/bin/python scripts/healthcheck_local.py --json`.

Run: `curl -sS http://127.0.0.1:8000/ai/scan` and compare resource IDs with `/capabilities` and `/agent-console/discovered`.

Expected: all supported tests pass; unsupported external runtimes are reported explicitly rather than counted as successes.

- [ ] **Step 7: Establish a clean integration boundary**

Run: `git status --short` and review every remaining modified file. Preserve unrelated user changes, stage only the completed convergence changes, and compare the resulting branch with `origin/main`. Do not merge or push until the complete verification set passes.

- [ ] **Step 8: Commit the platform and acceptance baseline**

```bash
git add tests/test_boss_hermes_smoke.py tests/test_codex_gate_regression.py tests/test_core_app.py tests/test_system_agent.py backend/core_app.py agents/system_agent/agent.py tests/test_runtime_acceptance.py scripts/healthcheck_local.py
git commit -m "test: establish cross-platform runtime acceptance baseline"
```

## Execution Order and Review Gates

Execute Tasks 1 through 7 in order. Task 2 cannot begin until Task 1 contracts pass. Tasks 3 and 4 depend on the canonical registry. Task 5 is independent at the code level but must land before frontend status work in Task 6. Task 7 is the final gate and must run against the combined branch.

After each task, review the diff for accidental changes outside the listed files, run its focused tests, and confirm that the resource status semantics still match the specification. Stop before the next task if a test requires a product decision rather than a local implementation fix.
