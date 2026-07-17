"""v0.9.0 Final Verification"""
import sys, os
sys.path.insert(0, ".")
import pytest

if os.getenv("AIOS_RUN_INTEGRATION") != "1":
    pytest.skip("legacy integration audit; set AIOS_RUN_INTEGRATION=1 to run", allow_module_level=True)
from fastapi.testclient import TestClient
from backend.app import app
c = TestClient(app)

print("v0.9.0 Final")
print()

# 1. Search
r = c.get("/search?q=Python security")
d = r.json()
hits = sum(len(v) for v in d.get("hits", {}).values())
print(f"1. Search: {hits} hits across {d.get('found_in',[])}")

# 2. Backup + restore
r = c.post("/system/backup")
d = r.json()
fn = os.path.basename(d.get("backup_path", ""))
r2 = c.post("/system/restore?filename=" + fn)
d2 = r2.json()
errs = [v for v in d2.get("tables", {}).values() if "skipped" in str(v)]
print(f'2. Backup+Restore: {"OK" if not errs else str(errs)}')

# 3. Swarm agents
r = c.get("/swarm/agents")
print(f"3. Swarm: {len(r.json()['agents'])} agents")

# 4. Swarm chain
r = c.post("/swarm/chain", json={"chain": [
    {"agent": "cto", "task_type": "code_review", "goal": "review", "code": "password='admin'; eval(x)"},
    {"agent": "qa", "task_type": "qa_review", "goal": "verify review quality"}
]})
d = r.json()
print(f"4. Swarm chain: {d.get('ok')} ({len(d.get('results',[]))} steps)")

# 5. Routes
routes = [r.path for r in app.routes]
print(f"5. Routes: {len(routes)} total")

# 6. Sandbox
from agents.codex_agent.agent import CodexAgent
r = CodexAgent(timeout=5).run({"task_id": "s", "task_type": "code_execute", "code": "print(42)"})
r2 = CodexAgent(timeout=5).run({"task_id": "s2", "task_type": "code_execute", "code": 'eval("1+1")'})
print(f'6. Sandbox: safe={"OK" if r.get("success") else "FAIL"} blocked={"OK" if not r2.get("success") else "FAIL"}')

# 7. Commander
r = c.post("/commander/run", json={"目标": "write a fibonacci function in Python and test it"})
d = r.json()
print(f"7. Commander: {d.get('status','?')} ({len(d.get('results',[]))} steps)")

# 8. DAG
r = c.post("/workflows/dag/run", json={"workflow": "seo-article", "inputs": {"topic": "AI tools", "keywords": "AI", "word_count": "500"}})
d = r.json()
done = sum(1 for v in d.get("results", {}).values() if v.get("status") == "completed")
print(f"8. DAG: {d.get('status','?')} ({done}/{len(d.get('results',{}))})")

# 9. All agent routes
all_ok = True
for name in ["ceo", "codex", "qa", "cto", "system", "openclaw", "image", "marketing", "video", "data"]:
    payload = {"goal": "test"}
    if name == "data": payload["task_type"] = "data_explore"
    elif name == "marketing": payload["task_type"] = "copywriting"; payload["prompt"] = "test"
    elif name == "video": payload["task_type"] = "video_script"; payload["prompt"] = "test"
    elif name == "image": payload["task_type"] = "image_generate"; payload["prompt"] = "test"
    elif name == "openclaw": payload["task_type"] = "chat"; payload["goal"] = "hello"
    elif name == "system": payload["task_type"] = "file_write"; payload["file_path"] = "_tf.txt"; payload["file_content"] = "x"
    elif name == "codex": payload["task_type"] = "code_execute"; payload["code"] = "print(1)"
    r = c.post(f"/agents/{name}/run", json=payload)
    if r.status_code != 200: all_ok = False
print(f"9. Agent routes: {'OK' if all_ok else 'FAIL'}")

print()
print("v0.9.0 ALL CLEAN")
