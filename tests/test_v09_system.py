"""v0.9.0 全系统回归测试 — 全面验证"""
import sys, os, json, time, tempfile
sys.path.insert(0, ".")
import pytest

if os.getenv("AIOS_RUN_INTEGRATION") != "1":
    pytest.skip("legacy integration audit; set AIOS_RUN_INTEGRATION=1 to run", allow_module_level=True)
from fastapi.testclient import TestClient
from backend.app import app
c = TestClient(app)

total = 0; passed = 0
def t(name, ok, info=""):
    global total, passed
    total += 1
    if ok: passed += 1
    s = "OK" if ok else "FAIL"
    print(f"  [{s:4}] {name:<40} {info}")

print("=" * 90)
print("AI Company OS v0.9.0 — Full System Regression")
print("=" * 90)
print()

# ═══ 1. SYSTEM ═══
print("── 1. System Health ──")
r = c.get("/health")
t("Health check", r.status_code==200 and r.json().get("status")=="ok")
r = c.get("/system/info")
d = r.json()
t("System info", d.get("version")=="0.9.0", f"v{d.get('version')} | {d.get('agents',{}).get('total')} agents")
r = c.get("/system/metrics")
d = r.json()
t("Metrics", sum(1 for v in d.get("agents",{}).values() if v=="ok")==10, f"{sum(1 for v in d.get('agents',{}).values() if v=='ok')}/10 agents healthy")
t("Metrics DB", d.get("db",{}).get("sessions",0)>0, f"{d.get('db')}")
r = c.get("/config/status")
t("Config", r.status_code==200)

# ═══ 2. ALL 10 AGENTS ═══
print()
print("── 2. Agent Routes (Pydantic validated) ──")
agents = {
    "ceo":      {"goal": "write hello world python function"},
    "qa":       {"goal": "verify test", "result": "hello world output successful"},
    "codex":    {"code": "print(42)", "task_type": "code_execute"},
    "cto":      {"goal": "review code", "code": "password='admin'; eval(x)", "language": "python"},
    "system":   {"task_type": "file_write", "file_path": "_vfy_test.txt", "file_content": "v0.9 test"},
    "openclaw": {"task_type": "chat", "goal": "Say hi in one word", "max_tokens": 50},
    "image":    {"task_type": "image_generate", "prompt": "A simple blue circle"},
    "marketing":{"task_type": "copywriting", "prompt": "AI note-taking app for students"},
    "video":    {"task_type": "video_script", "prompt": "60 second product demo for an AI tool"},
    "data":     {"task_type": "data_explore"},
}
for name, payload in agents.items():
    r = c.post(f"/agents/{name}/run", json=payload)
    ok = r.status_code == 200
    agent_name = r.json().get("agent", r.json().get("agent_name", "?")) if ok else "ERR"
    t(f"Agent/{name}", ok, f"{agent_name}")
# Clean up system test file
os.remove("_vfy_test.txt") if os.path.exists("_vfy_test.txt") else None

# ═══ 3. CORE FEATURES ═══
print()
print("── 3. Feature Endpoints ──")
features = [
    ("GET", "/skills/list", None, "skills"),
    ("GET", "/skills/match?goal=fix+security+bug+in+python+code", None, "matched"),
    ("GET", "/memory/search?q=code+review", None, "memories"),
    ("GET", "/ai/list", None, "services"),
    ("GET", "/ai/capabilities", None, "capabilities"),
    ("GET", "/workflows/dag/list", None, "workflows"),
    ("GET", "/workflows/dag/seo-article", None, "steps"),
    ("GET", "/cron/list", None, "jobs"),
    ("GET", "/payment/status", None, "stripe"),
    ("GET", "/payment/prices", None, "tiers"),
    ("GET", "/user/tiers", None, "tiers"),
    ("GET", "/templates/list", None, "templates"),
    ("GET", "/commander/sessions", None, "sessions"),
    ("GET", "/search?q=python+security", None, "hits"),
    ("GET", "/system/backups", None, "backups"),
    ("GET", "/static/css/style.css", None, ""),
    ("GET", "/static/js/app.js", None, ""),
    ("GET", "/ui", None, "page-commander"),
    ("GET", "/docs", None, ""),
    ("GET", "/swarm/agents", None, "agents"),
]
for method, path, payload, expect in features:
    r = c.get(path) if method == "GET" else c.post(path, json=payload or {})
    ok = r.status_code == 200 and (expect in r.text if expect else True)
    t(path.split("?")[0][:40], ok, f"HTTP{r.status_code}")

# ═══ 4. SECURITY ═══
print()
print("── 4. Security ──")
from agents.codex_agent.agent import CodexAgent
r_safe = CodexAgent(timeout=5).run({"task_id":"s1","task_type":"code_execute","code":"print(sum(range(10)))"})
t("Sandbox safe code", r_safe.get("success",False))
r_block = CodexAgent(timeout=5).run({"task_id":"s2","task_type":"code_execute","code":"import os; os.system('echo x')"})
t("Sandbox blocks os.system", not r_block.get("success", True))
r_block2 = CodexAgent(timeout=5).run({"task_id":"s3","task_type":"code_execute","code":"eval('1+1')"})
t("Sandbox blocks eval", not r_block2.get("success", True))

from backend.middleware.auth_middleware import _is_whitelisted
t("WS /ws/task/ needs auth", not _is_whitelisted("/ws/task/abc123"))
t("Health /health whitelisted", _is_whitelisted("/health"))

from backend.database.database import get_db
try:
    with get_db() as db:
        db.execute("CREATE TABLE IF NOT EXISTS _rollback_test(x int)")
        db.execute("INSERT INTO _rollback_test VALUES(1)")
        raise RuntimeError("simulated error")
except RuntimeError:
    with get_db() as db:
        cnt = db.execute("SELECT COUNT(*) FROM _rollback_test").fetchone()[0]
        db.execute("DROP TABLE _rollback_test")
        t("DB rollback on error", cnt == 0, f"rows={cnt}")

# ═══ 5. COMMANDER PIPELINE ═══
print()
print("── 5. Commander Pipeline ──")
r = c.post("/commander/run", json={"目标": "write a Python function to check if a number is prime, and test it with 17"})
d = r.json()
t("Commander sync", d.get("status")=="completed", f"{d.get('status','?')} | {len(d.get('results',[]))} steps")

r2 = c.post("/commander/run", json={"目标": "analyze this code: password='admin'; sql='SELECT * FROM users WHERE id='+uid; and suggest the best tech stack for a social media app"})
d2 = r2.json()
agents_used = {s.get("agent","?") for s in d2.get("results",[])}
t("Multi-agent dispatch", len(agents_used)>=2, f"agents: {agents_used}")

# ═══ 6. DAG WORKFLOW ═══
print()
print("── 6. DAG Workflow ──")
r = c.post("/workflows/dag/run", json={"workflow":"video-script","inputs":{"topic":"AI coding assistant demo","platform":"YouTube","duration":"90","format":"tutorial"}})
d = r.json()
done = sum(1 for v in d.get("results",{}).values() if v.get("status")=="completed")
t("DAG video-script", d.get("status")=="completed", f"{done}/{len(d.get('results',{}))}")

# ═══ 7. SWARM ═══
print()
print("── 7. Multi-Agent Swarm ──")
r = c.post("/swarm/chain", json={"chain":[
    {"agent":"cto","task_type":"code_review","goal":"review security","code":"eval(user_input)"},
    {"agent":"qa","task_type":"qa_review","goal":"verify cto quality"}
]})
d = r.json()
steps_ok = sum(1 for s in d.get("results",[]) if "error" not in str(s.get("result","")))
t("Swarm chain", d.get("ok") and steps_ok==2, f"{steps_ok}/2 steps")

# ═══ 8. DATA AGENT ═══
print()
print("── 8. Data Agent ──")
from agents.data_agent.agent import DataAgent
da = DataAgent()
td = tempfile.gettempdir()
csv_path = os.path.join(td, "_vfy_data.csv")
with open(csv_path, "w") as f: f.write("name,score\nAlice,95\nBob,87\nCharlie,92")
da.run({"task_id":"d1","task_type":"data_load","file_path":csv_path})
r = da.run({"task_id":"d2","task_type":"data_analyze","group_by":["name"],"agg_column":"score","agg_func":"sum"})
t("Data load+analyze", r.get("success",False), f"groups={len(r.get('data',{}).get('grouped',{}))}")
os.unlink(csv_path)

# ═══ 9. CONTEXT ENGINE ═══
print()
print("── 9. Context Engine ──")
from core.context_engine import ContextEngine
ctx = ContextEngine(max_context_tokens=4000, target_usage=0.7, hot_window=500)
for i in range(50):
    ctx.add_message("user", f"Long message {i} about AI and Python development. " * 6)
    ctx.add_message("assistant", f"Response {i} with technical analysis and recommendations. " * 6)
virtual = ctx.total_stored_tokens
_, sent = ctx.build_context("System prompt")
t("Context compression", virtual > sent * 1.2, f"{virtual:,}t->{sent:,}t ({virtual/sent:.1f}x)")

# ═══ 10. CACHE + EMBEDDING ═══
print()
print("── 10. Infra ──")
from core.cache_store import cache
cache.set("vfy", 42, ttl=10)
t("Cache LRU", cache.get("vfy")==42)
from core.embedding_service import get_embedding_service
emb = get_embedding_service()
v1, v2 = emb.embed("code review"), emb.embed("bug fix")
t("Embedding", emb.similarity(v1, v2) > -1, f"sim={emb.similarity(v1,v2):.3f}")
from core.cron_scheduler import CronParser
t("Cron */15", CronParser.matches("*/15 * * * *", __import__("datetime").datetime(2026,6,15,9,15)))
from core.agent_bus import get_agent_bus
bus = get_agent_bus()
got = []; bus.subscribe("_vfy", lambda m: got.append(m["payload"]))
bus.publish("_vfy", "hello", "test")
t("Agent Bus", got == ["hello"])

# ═══ SUMMARY ═══
print()
print("=" * 90)
print(f"TOTAL: {passed}/{total} passed ({passed*100//total}%)")
print("=" * 90)
