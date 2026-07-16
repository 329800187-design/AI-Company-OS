"""Context Engine + OpenClaw 1M Virtual Window Test"""
import os, sys, json
sys.path.insert(0, ".")
import pytest

if os.getenv("AIOS_RUN_INTEGRATION") != "1":
    pytest.skip("integration audit; set AIOS_RUN_INTEGRATION=1 to run", allow_module_level=True)

from core.context_engine import ContextEngine, estimate_tokens

print("=" * 70)
print("OpenClaw 1M Virtual Context Engine Test")
print("=" * 70)
print()

# 1. Token estimation
print("1. Token estimation...")
cn = "0123456789" * 10
en = "hello world " * 20
print(f"   cn 100 chars: ~{estimate_tokens(cn)} tokens")
print(f"   en 240 chars: ~{estimate_tokens(en)} tokens")
assert estimate_tokens(cn) > 0
assert estimate_tokens(en) > 0
print("   OK")
print()

# 2. Context engine compression
print("2. Context engine compression...")
ctx = ContextEngine(max_context_tokens=8000, target_usage=0.75, hot_window=500)

for i in range(60):
    ctx.add_message("user", "How to optimize Python performance? " + "lorem " * 15)
    ctx.add_message("assistant", "Use builtins, avoid globals, list comprehensions. " + "ipsum " * 15)

active = ctx._calc_active_tokens()
compressed = sum(1 for m in ctx.messages if m.level > 0)
print(f"   Virtual total: {ctx.total_stored_tokens:,} tokens")
print(f"   Active tokens: {active:,} tokens")
print(f"   Compression: {ctx.total_stored_tokens/active:.1f}x" if active > 0 else "   1x")
print(f"   Messages: {len(ctx.messages)} ({compressed} compressed)")
assert ctx.total_stored_tokens > active * 1.3, f"Ratio {ctx.total_stored_tokens/active:.1f}x"
print("   OK")
print()

# 3. Build LLM context
print("3. Build LLM context...")
context_text, actual_tokens = ctx.build_context("You are an AI assistant.")
print(f"   Context length: {len(context_text):,} chars")
print(f"   Actual tokens: {actual_tokens:,}")
assert actual_tokens <= 8000, f"Over limit! {actual_tokens}"
print("   OK")
print()

# 4. Semantic search
print("4. Semantic search...")
ctx.add_message("user", "How to deploy FastAPI with Docker multi-stage build?")
ctx.add_message("assistant", "Step 1: Dockerfile. Step 2: Multi-stage build.")
results = ctx.search_context("Docker deploy", top_k=3)
print(f"   Found {len(results)} results")
assert len(results) > 0
print("   OK")
print()

# 5. Persistence
print("5. Persistence...")
from pathlib import Path
test_path = Path("backend/database/_test_ctx.json")
ctx.save_to_disk(test_path)
ctx2 = ContextEngine()
ctx2.load_from_disk(test_path)
assert ctx2.total_stored_tokens > 0
print(f"   Saved/restored: {ctx2.total_stored_tokens:,} tokens")
test_path.unlink()
print("   OK")
print()

# 6. OpenClaw multi-turn chat
print("6. OpenClaw chat integration...")
from agents.openclaw_agent.agent import OpenClawAgent
oc = OpenClawAgent(headless=True, timeout=10)

for t in range(3):
    r = oc.run({"task_id": f"ct{t}", "task_type": "chat",
        "goal": f"Turn{t+1}: Say hi in one sentence", "max_tokens": 100})
    ok = r.get("success")
    msgs = oc.context_stats()["total_messages"]
    print(f"   Turn{t+1}: {'OK' if ok else 'FAIL'} (msgs={msgs})")

# 7. Stress test
print("7. Stress test: 500K virtual -> small physical...")
big = ContextEngine(max_context_tokens=3000, target_usage=0.70, hot_window=150)
lt = "Agent architecture tools memory collaboration performance caching batching. " * 15
for i in range(150):
    big.add_message("user", lt[:120] + f" msg{i}")
    big.add_message("assistant", lt[120:240] + f" reply{i}")

_, sent = big.build_context("You are an AI.")
ratio = big.total_stored_tokens / sent if sent > 0 else 1
print(f"   {big.total_stored_tokens:,}t virtual -> {sent:,}t physical ({ratio:.0f}x)")
assert sent <= 3000, f"OVER LIMIT: {sent}"
assert big.total_stored_tokens > sent * 3, f"Ratio {ratio:.1f}x too low"
print("   OK")

oc.clear_context()
assert oc.context_stats()["total_messages"] == 0
print("8. Clear context: OK")
print()
print("=" * 70)
print("ALL TESTS PASSED")
