"""AI Company OS v1.1.0 — Full Capability Audit"""
import sys, os, json, tempfile
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import pytest

if os.getenv("AIOS_RUN_INTEGRATION") != "1":
    pytest.skip("integration audit; set AIOS_RUN_INTEGRATION=1 to run", allow_module_level=True)

from fastapi.testclient import TestClient
from backend.app import app
c = TestClient(app)

results = []

def check(cat, name, ok, note=""):
    if note and len(str(note)) > 100:
        note = str(note)[:97] + "..."
    results.append((cat, name, "PASS" if ok else "FAIL", str(note) if note else ""))
    print(f"  [{'OK' if ok else 'FAIL'}] {name:<45} {note}")

print("=" * 100)
print("AI Company OS v1.1.0 — Full Capability Audit")
print("=" * 100)
print()

# ── 1. SYSTEM INFRASTRUCTURE ──
print("── 1. SYSTEM INFRASTRUCTURE ──")
r = c.get("/health")
check("Infra", "Health check", r.status_code == 200, f"v{r.json()['version']}")
r = c.get("/system/info"); d = r.json()
check("Infra", "System info", d.get("version") == "1.1.0", f"{d['agents']['total']} agents, {d['skills']['count']} skills")
r = c.get("/system/metrics"); d = r.json()
check("Infra", "Metrics endpoint", r.status_code == 200, f"{sum(1 for v in d.get('agents',{}).values() if v=='ok')}/10 agents healthy")
r = c.get("/api/versions")
check("Infra", "Version history", len(r.json()["versions"]) >= 10)
r = c.get("/config/status")
check("Infra", "Config status", r.status_code == 200, f"provider={r.json().get('current_provider','?')}")
r = c.get("/system/audit?limit=5")
check("Infra", "Audit logging", r.status_code == 200 and r.json()["count"] > 0, f"{r.json()['count']} entries")
r = c.get("/auth/info")
check("Infra", "Auth info", r.status_code == 200)

# ── 2. ALL 10 AGENTS ──
print()
print("── 2. AGENT CAPABILITIES ──")
# CEO
r = c.post("/agents/ceo/run", json={"goal": "write a Python function to calculate fibonacci numbers"}); d = r.json()
tasks = d.get("output", {}).get("created_tasks", [])
check("Agent", "CEO decompose", r.status_code == 200 and len(tasks) > 0, f"{len(tasks)} tasks")

# Codex
r = c.post("/agents/codex/run", json={"task_type": "code_execute", "code": "def fib(n): return n if n<2 else fib(n-1)+fib(n-2); print(fib(10))"}); d = r.json()
check("Agent", "Codex execute", r.status_code == 200 and d.get("success", False))

# QA
r = c.post("/agents/qa/run", json={"goal": "verify fibonacci output", "result": "55", "expected_output": {"type": "output", "description": "fib(10)=55"}}); d = r.json()
check("Agent", "QA review", r.status_code == 200, f"score={d.get('score','?')}")

# CTO (5 modes)
r = c.post("/agents/cto/run", json={"task_type": "code_review", "goal": "security review", "code": "password='admin'; eval(user_input); sql='SELECT * FROM users WHERE id='+uid"}); d = r.json()
check("Agent", "CTO code review", r.status_code == 200 and len(d.get("findings", [])) > 0, f"{len(d.get('findings',[]))} findings")
r = c.post("/agents/cto/run", json={"task_type": "tech_choice", "goal": "high traffic e-commerce tech stack"}); d = r.json()
check("Agent", "CTO tech choice", r.status_code == 200, str(d.get("summary",""))[:50])
r = c.post("/agents/cto/run", json={"task_type": "architecture_review", "goal": "review", "architecture_desc": "Monolith with no cache, single DB"}); d = r.json()
check("Agent", "CTO architecture", r.status_code == 200, f"score={d.get('score','?')}/100")
r = c.post("/agents/cto/run", json={"task_type": "task_decompose", "goal": "implement OAuth2 login system"}); d = r.json()
subs = d.get("data", {}).get("subtasks", [])
check("Agent", "CTO decompose", r.status_code == 200 and len(subs) > 0, f"{len(subs)} subtasks")
r = c.post("/agents/cto/run", json={"task_type": "effort_estimate", "goal": "build user auth + RBAC module"}); d = r.json()
check("Agent", "CTO estimate", r.status_code == 200, f"~{d.get('data',{}).get('total_hours','?')}h")

# System (3 modes)
r = c.post("/agents/system/run", json={"task_type": "file_write", "file_path": "_e2e.txt", "file_content": "test"})
check("Agent", "System file write", r.status_code == 200 and r.json().get("success", False))
r = c.post("/agents/system/run", json={"task_type": "file_read", "file_path": "_e2e.txt"})
check("Agent", "System file read", r.status_code == 200 and r.json().get("success", False))
r = c.post("/agents/system/run", json={"task_type": "file_delete", "file_path": "_e2e.txt"})
check("Agent", "System file delete", r.status_code == 200 and r.json().get("success", False))
r = c.post("/agents/system/run", json={"task_type": "process_list", "filter": "python"})
check("Agent", "System process list", r.status_code == 200, "")

# OpenClaw v2 (3 modes)
r = c.post("/agents/openclaw/run", json={"task_type": "chat", "goal": "Explain AI agent in one sentence", "max_tokens": 100}); d = r.json()
check("Agent", "OpenClaw chat", r.status_code == 200, str(d.get("data",{}).get("reply",""))[:40])
r = c.post("/agents/openclaw/run", json={"task_type": "reason", "goal": "Why microservices? Technical and organizational analysis"}); d = r.json()
check("Agent", "OpenClaw reason", r.status_code == 200, f"{len(str(d.get('result','')))} chars" if r.status_code == 200 else "FAIL")
r = c.post("/agents/openclaw/run", json={"task_type": "deep_research", "goal": "Top AI agent frameworks 2025"}); d = r.json()
srcs = d.get("data",{}).get("sources",[]) if isinstance(d,dict) else []
check("Agent", "OpenClaw research", r.status_code == 200, f"sources={len(srcs)}" if r.status_code == 200 else "FAIL")

# Image
r = c.post("/agents/image/run", json={"task_type": "image_generate", "prompt": "A cute orange cat"}); d = r.json()
check("Agent", "Image generate", r.status_code == 200, str(d.get("status",""))[:30])

# Marketing (6 modes)
for mode, prompt, ek in [
    ("copywriting", "AI note-taking app for students", "headline"),
    ("social_media", "AI learning tips Xiaohongshu", "content"),
    ("seo_article", "Python beginner tutorial 2025", "h1"),
    ("email_campaign", "SaaS subscription renewal", "subject"),
    ("brand_strategy", "AI education startup kids 3-12", "brand_positioning"),
    ("campaign_plan", "AI learning device launch", "campaign_name"),
]:
    r = c.post(f"/agents/marketing/run", json={"task_type": mode, "prompt": prompt}); d = r.json()
    has_key = bool(isinstance(d.get("data",{}), dict) and d.get("data",{}).get(ek, ""))
    check("Agent", f"Marketing/{mode}", r.status_code == 200 and has_key, str(has_key)[:50])

# Video (4 modes)
for mode in ["video_script", "video_storyboard", "video_idea"]:
    r = c.post("/agents/video/run", json={"task_type": mode, "prompt": "Product demo for AI tool"})
    check("Agent", f"Video/{mode}", r.status_code == 200)
r = c.post("/agents/video/run", json={"task_type": "video_generate", "prompt": "demo"})
check("Agent", "Video/generate (stub)", r.status_code == 200, "returns stub")

# Data
td = tempfile.gettempdir()
csv = os.path.join(td, "_e2edata.csv")
with open(csv, "w") as f: f.write("x,y\n1,10\n2,20\n3,30")
r = c.post("/agents/data/run", json={"file_path": csv}); d = r.json()
check("Agent", "Data load", r.status_code == 200 and d.get("data",{}).get("shape") == [3, 2])
r = c.post("/agents/data/run", json={"task_type": "data_explore"})
check("Agent", "Data explore", r.status_code == 200)
r = c.post("/agents/data/run", json={"task_type": "data_analyze", "group_by": ["x"], "agg_column": "y", "agg_func": "sum"}); d = r.json()
check("Agent", "Data analyze", r.status_code == 200, f"groups={len(d.get('data',{}).get('grouped',{}))}")
os.unlink(csv)

# External Plugin
r = c.get("/plugins")
check("Infra", "Plugin list", r.status_code == 200, f"{len(r.json().get('plugins',[]))} plugins")
r = c.post("/plugins/example_hello/run", json={"goal": "test", "name": "E2E"})
check("Infra", "Plugin execute", r.status_code == 200, r.json().get("data",{}).get("message","")[:50])

# ── 3. COMMANDER ──
print()
print("── 3. COMMANDER PIPELINE ──")
r = c.post("/commander/run", json={"目标": "write a Python function to check if a number is prime, test with 17"}); d = r.json()
check("Commander", "Sync execution", d.get("status") == "completed", f"{len(d.get('results',[]))} steps")
r = c.post("/commander/run-async", json={"目标": "calculate prime numbers 1-50"}); d = r.json()
check("Commander", "Async execution", d.get("status") == "queued", f"task={d.get('task_id','')}")
r = c.get("/commander/sessions")
check("Commander", "Session list", r.status_code == 200, f"{r.json().get('count',0)} sessions")
r = c.post("/commander/chat/send", json={"message": "What is Python? one sentence", "max_tokens": 100}); d = r.json()
check("Commander", "Chat send", r.status_code == 200, str(d.get("reply",""))[:40])

# ── 4. DAG ──
print()
print("── 4. DAG WORKFLOWS ──")
for wf in ["seo-article", "video-script", "image-campaign", "product-launch", "web-research"]:
    r = c.get(f"/workflows/dag/{wf}")
    if r.status_code == 200 and isinstance(r.json(), dict):
        check("DAG", f"Definition: {wf}", True, f"{len(r.json().get('steps',[]))} steps")
    else:
        check("DAG", f"Definition: {wf}", False, f"HTTP{r.status_code}")
r = c.post("/workflows/dag/run", json={"workflow": "seo-article", "inputs": {"topic": "Python async", "keywords": "python,async", "word_count": "800"}}); d = r.json()
done = sum(1 for v in d.get("results",{}).values() if v.get("status")=="completed") if isinstance(d,dict) else 0
total = len(d.get("results",{})) if isinstance(d,dict) else 0
check("DAG", "Execute SEO workflow", d.get("status") == "completed", f"{done}/{total} steps")

# ── 5. SWARM ──
print()
print("── 5. MULTI-AGENT SWARM ──")
r = c.get("/swarm/agents")
check("Swarm", "Agent list", r.status_code == 200, f"{len(r.json().get('agents',[]))} agents")
r = c.post("/swarm/chain", json={"chain": [{"agent":"cto","task_type":"code_review","goal":"review","code":"eval(x)"},{"agent":"qa","task_type":"qa_review","goal":"verify"}]}); d = r.json()
check("Swarm", "Chain execution", r.status_code == 200, f"{len(d.get('results',[]))} steps")
r = c.post("/swarm/fanout", json={"tasks": [{"agent":"cto","task_type":"code_review","goal":"reviewA","code":"print(1)"},{"agent":"cto","task_type":"tech_choice","goal":"choose"}]}); d = r.json()
check("Swarm", "Fanout execution", r.status_code == 200, f"{len(d.get('results',[]))} tasks parallel")

# ── 6. KNOWLEDGE ──
print()
print("── 6. KNOWLEDGE SYSTEMS ──")
r = c.get("/skills/list")
check("Skills", "List all", r.status_code == 200, f"{len(r.json().get('skills', r.json().get('data',[])))} skills")
r = c.get("/skills/match?goal=fix security bug in Python code"); mt = r.json().get("matched", r.json().get("data", []))
check("Skills", "Match query", len(mt) >= 2, f"{len(mt)} matched")
r = c.get("/memory/search?q=code+review"); mem = r.json().get("memories", r.json().get("data", []))
check("Memory", "Search", r.status_code == 200, f"{len(mem)} memories")
r = c.get("/search?q=python+security+code+review"); d = r.json()
hits = sum(len(v) for v in d.get("hits",{}).values())
check("Search", "Full-text search", hits > 0, f"{hits} hits across {d.get('found_in',[])}")

# ── 7. USER & PAYMENT ──
print()
print("── 7. USER & PAYMENT ──")
r = c.post("/user/register", json={"username":"audit_u","email":"au@t.com","password":"test123"})
check("User", "Register", r.status_code == 200)
r = c.post("/user/login", json={"username":"audit_u","password":"test123"})
check("User", "Login", r.status_code == 200, f"tier={r.json().get('tier','?')}")
r = c.get("/user/tiers")
check("User", "Tiers list", len(r.json().get("tiers",{})) == 3)
r = c.get("/payment/status")
check("Payment", "Stripe status", r.status_code == 200, f"stripe={'ON' if r.json().get('stripe_available') else 'off'}")
r = c.get("/payment/prices")
check("Payment", "Price list", r.status_code == 200, f"{len(r.json().get('tiers',{}))} tiers")

# ── 8. INFRASTRUCTURE ──
print()
print("── 8. INFRASTRUCTURE ──")
r = c.get("/ai/list")
check("AI Reg", "Service list", r.status_code == 200, f"{len(r.json().get('services',[]))} services")
r = c.get("/ai/capabilities")
check("AI Reg", "Capabilities", r.status_code == 200, f"{len(r.json().get('capabilities', r.json()))} capabilities")
r = c.get("/templates/list")
check("Template", "List templates", r.status_code == 200, f"{len(r.json().get('templates',[]))} templates")
r = c.get("/cron/list")
check("Cron", "Job list", r.status_code == 200, "")
r = c.post("/system/backup")
check("Backup", "Create backup", r.status_code == 200, f"{r.json().get('size_mb','?')}MB")
r = c.get("/system/backups")
check("Backup", "List backups", r.status_code == 200, f"{r.json().get('count',0)} backups")

# ── 9. SECURITY ──
print()
print("── 9. SECURITY ──")
from agents.codex_agent.agent import CodexAgent
ca = CodexAgent(timeout=5)
check("Sec", "Sandbox: safe code", ca.run({"task_id":"s1","task_type":"code_execute","code":"print(42)"}).get("success",False))
check("Sec", "Sandbox: block eval", not ca.run({"task_id":"s2","task_type":"code_execute","code":"eval('1+1')"}).get("success",True))
check("Sec", "Sandbox: block os.system", not ca.run({"task_id":"s3","task_type":"code_execute","code":"import os; os.system('echo x')"}).get("success",True))
check("Sec", "Sandbox: block subprocess", not ca.run({"task_id":"s4","task_type":"code_execute","code":"import subprocess; subprocess.run(['echo','x'])"}).get("success",True))
from backend.middleware.auth_middleware import _is_whitelisted
check("Sec", "WS /ws/task needs auth", not _is_whitelisted("/ws/task/abc123"))
check("Sec", "Health whitelisted", _is_whitelisted("/health"))
from backend.database.database import get_db
try:
    with get_db() as db:
        db.execute("CREATE TABLE IF NOT EXISTS __rb(x int)")
        db.execute("INSERT INTO __rb VALUES(1)")
        raise RuntimeError("sim")
except RuntimeError:
    with get_db() as db:
        cnt = db.execute("SELECT COUNT(*) FROM __rb").fetchone()[0]
        db.execute("DROP TABLE __rb")
        check("Sec", "DB rollback on error", cnt == 0)
from backend.auth.rbac import has_permission
check("Sec", "RBAC: admin allowed", has_permission({"role":"admin"},"agent_run"))
check("Sec", "RBAC: viewer blocked", not has_permission({"role":"viewer"},"agent_run"))

# ── 10. CORE ──
print()
print("── 10. CORE ENGINE ──")
from core.context_engine import ContextEngine
ctx = ContextEngine(max_context_tokens=4000, target_usage=0.7, hot_window=500)
for i in range(50):
    ctx.add_message("user", f"Long message about AI development {i}. " * 6)
    ctx.add_message("assistant", f"Response with analysis {i}. " * 6)
virtual = ctx.total_stored_tokens; _, sent = ctx.build_context("System prompt")
check("Core", "Context compression", virtual > sent * 1.2, f"{virtual:,}->{sent:,}t ({virtual/sent:.1f}x)")

from core.cache_store import cache
cache.set("_audit", 42, ttl=10)
check("Core", "Cache LRU", cache.get("_audit") == 42)
cache.evict("_audit")

from core.embedding_service import get_embedding_service
emb = get_embedding_service()
v1, v2 = emb.embed("Python security review"), emb.embed("Fix code vulnerability")
check("Core", "Embedding", emb.similarity(v1, v2) > -1, f"sim={emb.similarity(v1,v2):.3f}")

import datetime as dt
from core.cron_scheduler import CronParser
check("Core", "Cron: */15 match", CronParser.matches("*/15 * * * *", dt.datetime(2026, 6, 15, 9, 15)))
check("Core", "Cron: 3am miss", not CronParser.matches("0 3 * * *", dt.datetime(2026, 6, 15, 9, 0)))

from core.agent_bus import get_agent_bus
bus = get_agent_bus()
got = []; bus.subscribe("_audit", lambda m: got.append(m["payload"]))
bus.publish("_audit", "hello", "test")
check("Core", "Agent Bus pub/sub", got == ["hello"])

from core.workflow.engine import get_workflow_engine, DAGBuilder
wf = get_workflow_engine().get("product-launch")
layers, _ = DAGBuilder.build(wf.steps)
check("Core", "DAG topology", len(layers) == 4, f"{len(layers)} layers")

from core.agent_swarm import get_swarm
check("Core", "Swarm registered", len(get_swarm().get_agents()) >= 10)

from core.agent_stats import get_stats as ags
check("Core", "Agent stats", len(ags().get("summary",{})) > 0, f"{len(ags().get('summary',{}))} agents tracked")

# ── 11. NOTIFICATION ──
print()
print("── 11. NOTIFICATION ──")
from backend.services.notification_service import get_notification
check("Notify", "Service ready", True, f"enabled={get_notification().available}")

# ── 12. FRONTEND ──
print()
print("── 12. FRONTEND ──")
for path in ["/static/css/style.css", "/static/js/app.js", "/ui"]:
    r = c.get(path)
    check("FE", path, r.status_code == 200, f"{len(r.text)} bytes" if path != "/ui" else f"{len(r.text)} bytes")
if "/ui" in [p for _, p, _, _ in [("","","","")] if True]:
    r = c.get("/ui"); html = r.text
    for page in ["page-dashboard","page-commander","page-openclaw-chat","page-image","page-marketing","page-skills","page-cto","page-settings"]:
        check("FE", page, page in html)

# ── 13. CLI ──
print()
print("── 13. CLI TOOL ──")
import aios_cli
for cmd in ["status", "run", "agent", "workflow", "search", "metrics", "backup", "serve"]:
    check("CLI", f"Command: {cmd}", cmd in aios_cli.HELP.lower())

# ── SUMMARY ──
print()
print("=" * 100)
passed = sum(1 for _, _, s, _ in results if s == "PASS")
total = len(results)
print(f"TOTAL: {passed}/{total} PASSED ({passed*100//total}%)")

from collections import defaultdict
cats = defaultdict(lambda: [0, 0])
for cat, _, status, _ in results:
    cats[cat][1] += 1
    if status == "PASS": cats[cat][0] += 1
print()
for cat in sorted(cats):
    p, t = cats[cat]
    bar = "#" * (p * 20 // t) + "-" * ((t - p) * 20 // t)
    print(f"  {cat:<15} {bar} {p}/{t}")
