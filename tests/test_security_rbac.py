"""Security + RBAC unit tests"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

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

if __name__ == "__main__":
    test_rbac_permissions(); print("[OK] RBAC permissions")
    test_rbac_require_raises(); print("[OK] RBAC require raises")
    test_ws_not_whitelisted(); print("[OK] WS not whitelisted")
    test_health_whitelisted(); print("[OK] health whitelisted")
    test_db_rollback(); print("[OK] DB rollback")
    test_dangerous_commands_detected(); print("[OK] dangerous commands")
    print("\nALL SECURITY TESTS PASSED")
