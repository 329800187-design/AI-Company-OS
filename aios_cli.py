#!/usr/bin/env python
"""
AIOS CLI — AI Company OS 命令行工具 v1.0

Usage:
  python aios_cli.py run "write a fibonacci function in Python"
  python aios_cli.py agent cto "review this code: exec(user_input)"
  python aios_cli.py workflow run seo-article --topic "Python async" --keywords "python,async"
  python aios_cli.py search "security review"
  python aios_cli.py status
  python aios_cli.py serve          # 启动服务

If click is installed, use `aios` command directly.
"""
import json, os, sys, time, urllib.request, urllib.error
from typing import Optional
from pathlib import Path

BASE_URL = os.getenv("AIOS_URL", "http://127.0.0.1:8000")

def _api(method: str, path: str, data: dict = None) -> dict:
    url = f"{BASE_URL}{path}"
    body = json.dumps(data).encode() if data else None
    req = urllib.request.Request(url, data=body, method=method)
    if body:
        req.add_header("Content-Type", "application/json")
    try:
        with urllib.request.urlopen(req, timeout=120) as r:
            return json.loads(r.read().decode())
    except urllib.error.HTTPError as e:
        return {"ok": False, "error": f"HTTP {e.code}: {e.reason}"}
    except Exception as e:
        return {"ok": False, "error": str(e)}

def _print_result(d: dict, verbose: bool = False):
    if d.get("ok") == False:
        print(f"❌ {d.get('error', 'Unknown error')}")
        return
    status = d.get("status", d.get("result", "?"))
    summary = d.get("summary", "")
    results = d.get("results", [])
    data = d.get("data", {})
    print(f"✅ {status}")
    if summary: print(f"\n{summary[:500]}")
    if results:
        for i, step in enumerate(results):
            agent = step.get("agent", "?")
            s = step.get("status", "?")
            r = str(step.get("result", ""))[:80]
            print(f"  Step {i+1}: [{agent}] {s} — {r}")
    if verbose:
        print(json.dumps(d, indent=2, ensure_ascii=False)[:2000])

# ── Commands ────────────────────────────────────────

def cmd_status():
    """Show system status"""
    r = _api("GET", "/system/info")
    if r.get("ok") == False:
        print(f"❌ Cannot reach AIOS at {BASE_URL}")
        print("   Start with: python aios_cli.py serve")
        return
    print(f"🤖 AI Company OS v{r['version']}")
    print(f"   {r['agents']['total']} agents | {r['skills']['count']} skills")
    print(f"   {r['ai_services']['online']}/{r['ai_services']['total']} AI services online")
    print(f"   Provider: {r['provider']}")
    usage = r.get("usage", {})
    print(f"   Total calls: {usage.get('total_calls', 0)} | Tokens: {usage.get('total_tokens', 0):,} | Cost: ¥{usage.get('estimated_cost_yuan', 0)}")

def cmd_run(goal: str, async_mode: bool = False):
    """Execute goal via Commander"""
    print(f"🧠 Commander: {goal[:80]}...")
    if async_mode:
        r = _api("POST", "/commander/run-async", {"目标": goal})
        print(f"   Task: {r.get('task_id','?')} — queued (WebSocket: /ws/task/{r.get('task_id','')})")
    else:
        r = _api("POST", "/commander/run", {"目标": goal})
        _print_result(r)

def cmd_agent(name: str, goal: str, **kwargs):
    """Call specific agent directly"""
    print(f"🤖 {name}: {goal[:60]}...")
    payload = {"goal": goal, **kwargs}
    r = _api("POST", f"/agents/{name}/run", payload)
    _print_result(r, verbose=True)

def cmd_workflow(action: str, wf_name: str = "", **inputs):
    """Manage DAG workflows"""
    if action == "list":
        r = _api("GET", "/workflows/dag/list")
        for w in r.get("workflows", []):
            print(f"  {w['name']:25} | {w['steps']} steps | {w['title']}")
    elif action == "run":
        print(f"⚡ Workflow: {wf_name}...")
        r = _api("POST", "/workflows/dag/run", {"workflow": wf_name, "inputs": inputs})
        _print_result(r)
    elif action == "show":
        r = _api("GET", f"/workflows/dag/{wf_name}")
        if r.get("steps"):
            for s in r["steps"]:
                deps = s.get("depends_on", [])
                dep_str = f" (depends: {deps})" if deps else ""
                print(f"  [{s['id']}] → {s['agent']}/{s['task_type']}{dep_str}")

def cmd_search(query: str):
    """Full-text search across memories/skills/sessions"""
    print(f"🔍 Searching: {query}")
    import urllib.parse
    r = _api("GET", f"/search?q={urllib.parse.quote(query)}")
    for section, hits in r.get("hits", {}).items():
        if hits:
            print(f"\n  ── {section} ({len(hits)}) ──")
            for h in hits[:5]:
                snippet = str(h.get("snippet", h.get("description", h.get("goal", ""))))[:100]
                print(f"    • {snippet}")

def cmd_serve(host: str = "127.0.0.1", port: int = 8000):
    """Start AIOS server"""
    import subprocess
    os.chdir(Path(__file__).parent)
    print(f"🚀 Starting AIOS on http://{host}:{port} ...")
    subprocess.run([sys.executable, "-m", "uvicorn", "backend.app:app",
                    "--host", host, "--port", str(port), "--reload"])

def cmd_backup():
    r = _api("POST", "/system/backup")
    print(f"💾 Backup: {r.get('size_mb','?')} MB → {r.get('backup_path','?')}")

def cmd_metrics():
    r = _api("GET", "/system/metrics")
    agents = r.get("agents", {})
    print(f"🤖 Agents: {sum(1 for v in agents.values() if v=='ok')}/{len(agents)} healthy")
    db = r.get("db", {})
    print(f"🗄️  DB: {db.get('sessions',0)} sessions, {db.get('memories', 0)} memories")
    cache = r.get("cache", {})
    print(f"⚡ Cache: {cache.get('hit_rate','?')}, {cache.get('size',0)} entries")

def cmd_doctor(deep: bool = False):
    """Run server or local self-checks."""
    r = _api("GET", f"/system/doctor{'?deep=true' if deep else ''}")
    if r.get("ok") == False:
        from backend.services.doctor import run_doctor
        r = run_doctor(deep=deep)

    summary = r.get("summary", {})
    print(f"AI Company OS doctor: {r.get('status', 'unknown').upper()} "
          f"({summary.get('ok', 0)} ok, {summary.get('warn', 0)} warn, {summary.get('error', 0)} error)")
    for check in r.get("checks", []):
        marker = {"ok": "OK", "warn": "WARN", "error": "ERR"}.get(check.get("status"), "?")
        print(f"  [{marker:4}] {check.get('name')}: {check.get('summary')}")
    actions = r.get("next_actions", [])
    if actions:
        print("\nNext actions:")
        for item in actions:
            print(f"  - {item}")

# ── Main ────────────────────────────────────────────

HELP = """AIOS CLI — AI Company OS v1.0

Commands:
  status              Show system status and health
  run <goal>          Execute goal via Commander (sync)
  run-async <goal>    Execute goal asynchronously
  agent <name> <text> Call specific agent (ceo/codex/qa/cto/system/openclaw/image/marketing/video/data)
  workflow list       List all DAG workflows
  workflow run <name> Execute DAG workflow (--key=value for inputs)
  workflow show <name> Show workflow steps
  search <query>      Full-text search
  metrics             Show monitoring metrics
  doctor [--deep]     Run startup/config/dependency self-checks
  backup              Create system backup
  serve [port]        Start AIOS server (default 8000)
  help                Show this help
"""

def main():
    args = sys.argv[1:]
    if not args:
        print(HELP)
        return

    cmd = args[0].lower()

    if cmd == "help":
        print(HELP)
    elif cmd == "status":
        cmd_status()
    elif cmd == "run":
        cmd_run(" ".join(args[1:]))
    elif cmd == "run-async":
        cmd_run(" ".join(args[1:]), async_mode=True)
    elif cmd == "agent":
        if len(args) < 3:
            print("Usage: aios agent <name> <goal>")
            print("Agents: ceo, codex, qa, cto, system, openclaw, image, marketing, video, data")
            return
        cmd_agent(args[1], " ".join(args[2:]))
    elif cmd == "workflow":
        if len(args) < 2:
            print("Usage: aios workflow <list|run|show> [name] [--key=value ...]")
            return
        action = args[1]
        wf_name = args[2] if len(args) > 2 and not args[2].startswith("--") else ""
        inputs = {}
        for a in args[3:]:
            if a.startswith("--") and "=" in a:
                k, v = a[2:].split("=", 1)
                inputs[k] = v
        cmd_workflow(action, wf_name, **inputs)
    elif cmd == "search":
        cmd_search(" ".join(args[1:]))
    elif cmd == "metrics":
        cmd_metrics()
    elif cmd == "doctor":
        cmd_doctor(deep="--deep" in args[1:])
    elif cmd == "backup":
        cmd_backup()
    elif cmd == "serve":
        port = int(args[1]) if len(args) > 1 and args[1].isdigit() else 8000
        cmd_serve(port=port)
    else:
        # Assume it's a goal — run via Commander
        cmd_run(" ".join(args))

if __name__ == "__main__":
    main()
