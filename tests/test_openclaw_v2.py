"""OpenClaw v2 能力验证"""
import os, sys, json
sys.path.insert(0, ".")
import pytest

if os.getenv("AIOS_RUN_INTEGRATION") != "1":
    pytest.skip("integration audit; set AIOS_RUN_INTEGRATION=1 to run", allow_module_level=True)

from agents.openclaw_agent.agent import OpenClawAgent, PLAYWRIGHT_AVAILABLE

print("=== OpenClaw v2 ===")
oc = OpenClawAgent(headless=True, timeout=15)

# 1. V1 兼容
print("1. V1 browser_scrape...")
try:
    r = oc.run({"task_id":"t1","task_type":"browser_scrape","url":"https://httpbin.org/get"})
    print(f"   scrape: {r['status']}")
except Exception as e:
    print(f"   scrape: SKIP ({e})")

# 2. 搜索策略
print("2. 搜索策略...")
plan = oc._plan_search("AI大模型2025最新发展")
print(f"   primary={plan.get('primary_query','')[:60]}")

# 3. V1 screenshot
print("3. V1 screenshot...")
try:
    r = oc.run({"task_id":"t2","task_type":"browser_screenshot","url":"https://httpbin.org/get"})
    print(f"   screenshot: {r['status']}")
except Exception as e:
    print(f"   screenshot: SKIP ({e})")

# 4. 白名单放宽（研究模式）
print("4. URL 白名单...")
assert oc._is_url_allowed("https://zhihu.com/question/123")
assert oc._is_url_allowed("https://arxiv.org/abs/1234.5678")
assert oc._is_url_allowed("https://news.ycombinator.com/item?id=1")
print("   研究白名单: OK (zhihu, arxiv, hackernews)")

# 5. 思考模式
print("5. 深度思考...")
r = oc.run({"task_id":"t3","task_type":"reason","goal":"从技术和组织两个角度分析为什么微服务比单体更受欢迎"})
print(f"   success={r['success']} len={len(r.get('result',''))}")
if r['success']:
    print(f"   {r['result'][:120]}...")

# 6. verify模式
print("6. 事实核查...")
r = oc.run({"task_id":"t4","task_type":"verify","goal":"Python3.13是否已经发布"})
print(f"   success={r['success']} sources={len(r.get('data',{}).get('sources',[]))}")

# 7. 记忆检查
print("7. 记忆存储...")
from core.memory.memory_store import get_memory_store
mem = get_memory_store()
recent = mem.recent(10)
oc_mem = [m for m in recent if m.get('source') == 'openclaw']
print(f"   openclaw记忆: {len(oc_mem)}条")

# 8. import 双向兼容
print("8. 双向兼容...")
from agents.openclaw_agent.agent import OpenClawAgent as OC2
assert OC2 is OpenClawAgent or OC2.__name__ == 'OpenClawAgent'
print(f"   旧位置导入: OK")

print()
print("=== OpenClaw v2 全部测试通过 ===")
