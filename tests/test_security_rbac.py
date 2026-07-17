"""Security + RBAC unit tests"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

def test_sandbox_safe_code():
    from agents.codex_agent.agent import CodexAgent
    ca = CodexAgent(timeout=5)
    r = ca.run({"task_id":"t1","task_type":"code_execute","code":"print(42)"})
    assert r.get("success") == True

def test_sandbox_block_eval():
    from agents.codex_agent.agent import CodexAgent
    ca = CodexAgent(timeout=5)
    r = ca.run({"task_id":"t2","task_type":"code_execute","code":"eval('1+1')"})
    assert r.get("success") == False

def test_sandbox_block_os():
    from agents.codex_agent.agent import CodexAgent
    ca = CodexAgent(timeout=5)
    r = ca.run({"task_id":"t3","task_type":"code_execute","code":"import os; os.system('echo x')"})
    assert r.get("success") == False

def test_sandbox_block_subprocess():
    from agents.codex_agent.agent import CodexAgent
    ca = CodexAgent(timeout=5)
    r = ca.run({"task_id":"t4","task_type":"code_execute","code":"import subprocess; subprocess.run(['echo','x'])"})
    assert r.get("success") == False

def test_sandbox_math_works():
    from agents.codex_agent.agent import CodexAgent
    ca = CodexAgent(timeout=5)
    r = ca.run({"task_id":"t5","task_type":"code_execute","code":"import math; print(math.sqrt(144))"})
    assert r.get("success") == True

def test_rbac_permissions():
    from backend.auth.rbac import has_permission, require_permission
    assert has_permission({"role":"admin"},"agent_run")
    assert has_permission({"role":"admin"},"config_write")
    assert has_permission({"role":"admin"},"system_manage")
    assert has_permission({"role":"operator"},"agent_run")
    assert has_permission({"role":"operator"},"config_write")
    assert not has_permission({"role":"operator"},"user_manage")
    assert has_permission({"role":"user"},"agent_run")
    assert not has_permission({"role":"user"},"config_write")
    assert has_permission({"role":"viewer"},"read_only")
    assert not has_permission({"role":"viewer"},"agent_run")

def test_rbac_require_raises():
    from backend.auth.rbac import require_permission
    try:
        require_permission({"role":"viewer"},"agent_run")
        assert False, "Should have raised PermissionError"
    except PermissionError:
        pass

def test_ws_not_whitelisted():
    from backend.middleware.auth_middleware import _is_whitelisted
    assert not _is_whitelisted("/ws/task/abc123")
    assert not _is_whitelisted("/ws/task")

def test_health_whitelisted():
    from backend.middleware.auth_middleware import _is_whitelisted
    assert _is_whitelisted("/health")
    assert _is_whitelisted("/docs")
    assert _is_whitelisted("/auth/info")

def test_db_rollback():
    from backend.database.database import get_db
    try:
        with get_db() as db:
            db.execute("CREATE TABLE IF NOT EXISTS _rb_test(x int)")
            db.execute("INSERT INTO _rb_test VALUES(1)")
            raise RuntimeError("simulated")
    except RuntimeError:
        with get_db() as db:
            cnt = db.execute("SELECT COUNT(*) FROM _rb_test").fetchone()[0]
            db.execute("DROP TABLE _rb_test")
            assert cnt == 0, f"Expected 0 rows after rollback, got {cnt}"

def test_dangerous_commands_detected():
    from agents.system_agent.agent import DANGEROUS_COMMANDS
    assert len(DANGEROUS_COMMANDS) >= 30
    # Check key patterns are there
    assert any("format" in d.lower() or "del /f" in d.lower() or "rm -rf" in d.lower() for d in DANGEROUS_COMMANDS)

if __name__ == "__main__":
    test_sandbox_safe_code(); print("[OK] sandbox safe")
    test_sandbox_block_eval(); print("[OK] sandbox block eval")
    test_sandbox_block_os(); print("[OK] sandbox block os")
    test_sandbox_block_subprocess(); print("[OK] sandbox block subprocess")
    test_sandbox_math_works(); print("[OK] sandbox math works")
    test_rbac_permissions(); print("[OK] RBAC permissions")
    test_rbac_require_raises(); print("[OK] RBAC require raises")
    test_ws_not_whitelisted(); print("[OK] WS not whitelisted")
    test_health_whitelisted(); print("[OK] health whitelisted")
    test_db_rollback(); print("[OK] DB rollback")
    test_dangerous_commands_detected(); print("[OK] dangerous commands")
    print("\nALL SECURITY TESTS PASSED")
