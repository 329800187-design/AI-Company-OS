"""Quick smoke test — all 10 agents instantiate and run (offline fallback)"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import pytest

@pytest.fixture
def agents():
    agents = {}
    from agents.ceo_agent.agent import CEOAgent; agents["ceo"] = CEOAgent()
    from agents.codex_agent.agent import CodexAgent; agents["codex"] = CodexAgent(timeout=5)
    from agents.qa_agent.agent import QAAgent; agents["qa"] = QAAgent()
    from agents.cto_agent.agent import CTOAgent; agents["cto"] = CTOAgent(api_key="")
    from agents.system_agent.agent import SystemAgent; agents["system"] = SystemAgent()
    from agents.openclaw_agent.agent import OpenClawAgent; agents["openclaw"] = OpenClawAgent(headless=True, timeout=5)
    from agents.image_agent.agent import ImageAgent; agents["image"] = ImageAgent(api_key="")
    from agents.marketing_agent.agent import MarketingAgent; agents["marketing"] = MarketingAgent(api_key="")
    from agents.video_agent.agent import VideoAgent; agents["video"] = VideoAgent(api_key="")
    from agents.data_agent.agent import DataAgent; agents["data"] = DataAgent()
    assert len(agents) == 10
    return agents

def test_all_agents(agents):
    assert len(agents) == 10

def test_agent_runs(agents):
    tasks = {
        "ceo": {"task_id":"t1","goal":"write hello world"},
        "codex": {"task_id":"t2","task_type":"code_execute","code":"print(42)"},
        "qa": {"task_id":"t3","goal":"test QA","result":"hello world success"},
        "cto": {"task_id":"t4","task_type":"code_review","goal":"review","code":"print(1)"},
        "system": {"task_id":"t5","task_type":"file_write","file_path":"_t.txt","file_content":"x"},
        "openclaw": {"task_id":"t6","task_type":"chat","goal":"hi","max_tokens":30},
        "image": {"task_id":"t7","task_type":"image_generate","prompt":"cat"},
        "marketing": {"task_id":"t8","task_type":"copywriting","prompt":"AI tool ad"},
        "video": {"task_id":"t9","task_type":"video_script","prompt":"demo"},
        "data": {"task_id":"t10","task_type":"data_explore"},
    }
    for name, agent in agents.items():
        result = agent.run(tasks[name])
        assert result is not None, f"{name}: returned None"
        assert "agent" in result or "ok" in result, f"{name}: bad format: {list(result.keys())[:5]}"
    if os.path.exists("_t.txt"): os.remove("_t.txt")

def test_sandbox():
    from agents.codex_agent.agent import CodexAgent
    c = CodexAgent(timeout=5)
    assert c.run({"task_id":"s1","task_type":"code_execute","code":"print(42)"}).get("success")
    assert not c.run({"task_id":"s2","task_type":"code_execute","code":"eval('1+1')"}).get("success")
    assert not c.run({"task_id":"s3","task_type":"code_execute","code":"import os; os.system('echo x')"}).get("success")

def test_rbac():
    from backend.auth.rbac import has_permission, require_permission
    assert has_permission({"role":"admin"},"agent_run")
    assert has_permission({"role":"user"},"agent_run")
    assert not has_permission({"role":"viewer"},"agent_run")
    try: require_permission({"role":"viewer"},"agent_run"); assert False
    except PermissionError: pass

def test_cache():
    from core.cache_store import cache
    cache.set("test_key", 42, ttl=10)
    assert cache.get("test_key") == 42
    cache.evict("test_key")
    assert cache.get("test_key") is None

def test_context():
    from core.context_engine import ContextEngine
    ctx = ContextEngine(max_context_tokens=4000, target_usage=0.7, hot_window=500)
    for i in range(40):
        ctx.add_message("user", f"Message {i} about AI. " * 6)
        ctx.add_message("assistant", f"Response {i} with analysis. " * 6)
    _, sent = ctx.build_context("System prompt")
    assert sent <= 4000
    assert ctx.total_stored_tokens > sent

def test_workflow_dag():
    from core.workflow.engine import get_workflow_engine, DAGBuilder
    wf = get_workflow_engine().get("seo-article")
    assert wf is not None
    layers, deps = DAGBuilder.build(wf.steps)
    assert len(layers) > 0

if __name__ == "__main__":
    print("Running quick test suite...")
    agents = test_all_agents();        print("  [OK] 10 agents instantiated")
    test_agent_runs(agents);           print("  [OK] all agents run")
    test_sandbox();                    print("  [OK] sandbox security")
    test_rbac();                       print("  [OK] RBAC permissions")
    test_cache();                      print("  [OK] cache LRU")
    test_context();                    print("  [OK] context compression")
    test_workflow_dag();               print("  [OK] DAG workflow")
    print("\nALL TESTS PASSED")
