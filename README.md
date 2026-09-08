# AI Company OS

AI Company OS is a subscription-based AI business-process execution platform.
It helps a team turn a goal into a reviewed plan, governed execution, and
auditable deliverables.

## What users can do

- Use Boss Command Center templates to turn goals into plans, decisions,
  deliverables, communications, reviews, risk checks, and data insights.
- Review each Mission before execution and accept the resulting work after it
  completes.
- Discover and enable supported business agents for research, communication,
  image, data, and website work.
- Manage account access, subscription tiers, and usage through the web app.

## Safety model

- Authentication is required by default; configure `AUTH_TOKEN` before running
  the application.
- Actions follow `propose → preflight → approve → execute`.
- External webhook delivery requires explicit deployment configuration.
- The `code_execution` capability is registered only as a disabled placeholder;
  it cannot run code or host-system commands.

## Run locally

```bash
cp .env.example .env
# Set AUTH_TOKEN and any provider credentials required for your deployment.
pip install -r requirements.txt
uvicorn backend.app:app --reload --port 8000
```

Run the frontend separately:

```bash
cd frontend-new
npm install
npm run dev
```

## Documentation

- [Architecture inventory](ARCHITECTURE.md) — generated from the source tree.
- [Current project state](docs/current_project_state.md) — maintained change
  history and runtime convergence notes.
- [Core distribution manifest](docs/core_distribution_manifest.md) — Core
  runtime packaging reference.

To regenerate the architecture inventory:

```bash
python scripts/generate_architecture_doc.py
```
