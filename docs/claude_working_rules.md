# Claude Working Rules

Use this file before modifying AI Company OS.

## Current Direction Override (2026-07-14)

- First read `docs/current_project_state.md`.
- Current Boss work is Phase 6.19+ genericization: AI Company OS must be a **generic business process execution system**, not a single business/process tool.
- Do not add default templates, UI copy, prompts, reports, or tests that lock the core product to Xianyu, ecommerce, Xiaohongshu, SEO, landing pages, SaaS, or any other specific domain.
- Concrete domains may appear only as user input, compatibility aliases, examples, tests for legacy compatibility, or opt-in legacy plugins.
- Next required cleanup is Phase 6.23: frontend Boss detail panel and README residual wording.

## Core Rules

- Governance is the only controlled execution entry.
- Prefer `POST /governance/run` for executable user goals.
- `/governance/test-page` is a development validation page, not the formal frontend.
- The formal frontend is `frontend-new`.
- Do not restore old direct execution routes.
- Do not route unsupported goals into execution.
- Do not silently default unknown goals to `xiaohongshu`.
- Explicit `platform` must not bypass dangerous or vague goal blocking.

## Current Executable Capabilities

- `copy_pack.xiaohongshu`
- `copy_pack.douyin`

Everything else must either:

- return `unsupported.artifact_type`, or
- request clarification.

## Old Route Policy

Keep these blocked/deprecated unless explicitly requested otherwise:

- old workflow execution routes
- old template execution routes
- commander continue execution
- direct high-risk agent execution without Governance guard

## Frontend Rules

- Keep `/governance/test-page` for development validation.
- Use `/app?page=governance` or `/app#governance` for the formal Governance frontend.
- For product work, prefer connecting original pages to Governance instead of adding more temporary pages.
- The next page to connect should be `frontend-new/src/pages/marketing`.

## Verification

For backend/Governance changes, run:

```bash
python -m pytest tests/test_governance.py tests/test_minidelivery.py -q
```

For frontend changes, run:

```bash
cd frontend-new
npm run build
```

For changed Python files, run relevant `py_compile`.

## Output Format

Always report:

- modified files
- new tests
- verification result
- manual validation path
- remaining risk

## Short Task Card Template

```text
读：docs/claude_working_rules.md + docs/current_project_state.md

任务：[one-line task]
问题：[what is broken or missing]
范围：[files/modules]
验收：[concrete checks]
输出：按规则
```
