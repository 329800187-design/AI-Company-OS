# AI Company OS — Quick Start

## 1. Prerequisites

- Python 3.12+
- Git Bash (Windows) or bash (Linux/Mac)

## 2. One-Click Start (Windows)

Double-click `start.bat` in the project root. It will:
1. Create virtual environment
2. Install dependencies
3. Copy `.env.example` → `.env` (edit API keys)
4. Install Playwright Chromium
5. Start server at `http://localhost:8000`

## 3. Manual Start

```bash
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env
# Edit .env: add DEEPSEEK_API_KEY=
uvicorn backend.app:app --host 0.0.0.0 --port 8000 --reload
```

## 4. Configure API Key

Open `http://localhost:8000/ui` → Settings → add your DeepSeek/OpenAI/Claude API key.

## 5. First Command

In Commander page (default home), type:
```
write a hello world Python function and test it
```

The system will:
1. CEO decomposes → Codex writes code → QA verifies
2. Results appear in real-time

## 6. Docker

```bash
docker compose up -d
# http://localhost (port 80)
```

## 7. Available Pages

| Page | Description |
|------|-------------|
| 📊 Dashboard | System overview, agent health, usage stats |
| 🧠 Commander | Goal input → auto decompose → execute |
| 💬 AI Chat | Direct LLM conversation |
| 🔍 CTO | Code review / tech choice / architecture |
| 🎨 Image | AI image generation (DALL-E 3) |
| 📝 Marketing | Copywriting / SEO / social / brand |
| 🌐 OpenClaw | Web research + deep thinking + 1M context |
| 📚 Skills | 25 built-in skills with semantic search |
| 📋 Templates | 12 industry scenario templates |
| ⚙️ Settings | API keys, provider switching, auth |

## 8. API Reference

Swagger docs: `http://localhost:8000/docs`

Key endpoints:
- `POST /commander/run` — sync execution
- `POST /commander/run-async` — async with WebSocket progress
- `POST /agents/{name}/run` — direct agent call
- `POST /workflows/dag/run` — DAG workflow
- `GET /system/metrics` — monitoring data

## 9. Local Verification (Smoke Check)

After starting the server, run the smoke check to verify core endpoints:

```bash
# Run smoke check (requires server at 127.0.0.1:8000)
python scripts/backend_smoke_check.py

# Custom host/port
python scripts/backend_smoke_check.py --host 127.0.0.1 --port 8000
```

This checks: `/health`, `/memory/recent`, `/memory/search`, `/boss/missions`, `/boss/templates`, mission detail/export, and response structures. No AI API key needed.

## 10. Running Tests

```bash
# Boss command center (67 tests)
python -m pytest tests/test_boss_command_center.py -q

# Memory + Boss basics (17 tests, no external API deps)
python -m pytest tests/test_memory_and_boss_basics.py -q

# Browser automation approval (19 tests)
python -m pytest tests/test_browser_automation_approval.py -q
```

## 11. Frontend Build

```bash
cd frontend-new
npm install
npx vite build          # production build
npx vite                # dev server
```
- `GET /search?q=...` — full-text search
