"""Commander full pipeline unit tests"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.commander.commander import CommanderAgent

def test_commander_instantiation():
    c = CommanderAgent()
    assert c.ceo is not None
    assert c.codex is not None
    assert c.qa is not None
    assert c.openclaw is not None
    assert c.system is not None
    # These are in _agents dict, not direct attributes
    assert c._agents.get("cto") is not None
    assert c._agents.get("image") is not None
    assert c._agents.get("marketing") is not None
    assert c._agents.get("video") is not None
    assert c._agents.get("data") is not None

def test_agent_mapping():
    c = CommanderAgent()
    mapping = c._get_executor
    assert mapping("codex") is not None
    assert mapping("openclaw") is not None
    assert mapping("system") is not None
    assert mapping("qa") is not None
    assert mapping("ceo") is not None
    assert mapping("cto") is not None
    assert mapping("image") is not None
    assert mapping("marketing") is not None
    assert mapping("video") is not None
    assert mapping("data") is not None
    assert mapping("nonexistent") is None

def test_decompose_basic():
    from backend.database.database import SessionDB
    c = CommanderAgent()
    sid = "test_session_decomp_001"
    try:
        SessionDB.create(sid, "write a hello world Python function and test it")
        steps = c.decompose_goal("write a hello world Python function and test it", sid)
        assert len(steps) > 0
        assert all("step" in s for s in steps)
        assert all("agent" in s for s in steps)
    finally:
        try: SessionDB.delete(sid)
        except: pass

def test_continue_session_invalid():
    c = CommanderAgent()
    result = c.continue_session("nonexistent_session_id", "test input")
    assert result.get("status") == "error"

def test_make_decision():
    c = CommanderAgent()
    decision = c._make_decision(
        step={"step_number": 1, "description": "test step"},
        result={"result": "success", "status": "completed"},
        retry_count=0,
        remaining_steps=3
    )
    assert "decision" in decision
    assert decision["decision"] in ("continue", "complete", "retry", "adjust", "ask")

def test_get_session_status_invalid():
    c = CommanderAgent()
    result = c.get_session_status("nonexistent")
    assert result.get("status") == "error"

if __name__ == "__main__":
    test_commander_instantiation(); print("[OK] commander instantiation")
    test_agent_mapping(); print("[OK] agent mapping")
    test_decompose_basic(); print("[OK] decompose basic")
    test_continue_session_invalid(); print("[OK] continue invalid")
    test_make_decision(); print("[OK] make decision")
    test_get_session_status_invalid(); print("[OK] session status invalid")
    print("\nALL COMMANDER TESTS PASSED")
