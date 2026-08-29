"""Agent performance stats — latency, success rate, call counts"""
import json, sqlite3, threading, time
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

from backend.runtime_paths import DATABASE_PATH

DB = DATABASE_PATH
_lock = threading.Lock()

def _init():
    conn = sqlite3.connect(str(DB))
    conn.execute("""CREATE TABLE IF NOT EXISTS agent_stats (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        agent TEXT NOT NULL, task_type TEXT, status TEXT, duration_ms INTEGER,
        success INTEGER, tokens_used INTEGER DEFAULT 0,
        time TEXT DEFAULT (datetime('now'))
    )""")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_astats_agent ON agent_stats(agent)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_astats_time ON agent_stats(time)")
    conn.commit()
    conn.close()

def record(agent: str, task_type: str, status: str, duration_ms: int, success: bool, tokens: int = 0):
    _init()
    conn = sqlite3.connect(str(DB))
    conn.execute("INSERT INTO agent_stats (agent,task_type,status,duration_ms,success,tokens_used) VALUES (?,?,?,?,?,?)",
                 (agent, task_type, status[:20], duration_ms, int(success), tokens))
    conn.commit()
    conn.close()

def get_stats(agent: str = "", hours: int = 24) -> Dict:
    conn = sqlite3.connect(str(DB))
    conn.row_factory = sqlite3.Row
    if agent:
        rows = conn.execute("SELECT * FROM agent_stats WHERE agent=? AND time >= datetime('now',?) ORDER BY id DESC LIMIT 200",
                            (agent, f"-{hours} hours")).fetchall()
    else:
        rows = conn.execute("SELECT * FROM agent_stats WHERE time >= datetime('now',?) ORDER BY id DESC LIMIT 500",
                            (f"-{hours} hours",)).fetchall()
    data = [dict(r) for r in rows]
    conn.close()

    # Aggregate
    aggs = {}
    for r in data:
        a = r["agent"]
        if a not in aggs:
            aggs[a] = {"calls": 0, "success": 0, "failed": 0, "total_ms": 0, "total_tokens": 0}
        aggs[a]["calls"] += 1
        if r["success"]: aggs[a]["success"] += 1
        else: aggs[a]["failed"] += 1
        aggs[a]["total_ms"] += r["duration_ms"]
        aggs[a]["total_tokens"] += r.get("tokens_used", 0)

    summary = {}
    for a, s in aggs.items():
        summary[a] = {
            "calls": s["calls"],
            "success_rate": f"{s['success']/s['calls']*100:.1f}%" if s["calls"] > 0 else "0%",
            "avg_latency_ms": s["total_ms"] // s["calls"] if s["calls"] > 0 else 0,
            "total_tokens": s["total_tokens"],
        }
    return {"records": data[:50], "summary": summary, "total_records": len(data)}
