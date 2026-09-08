"""Tests conftest — 测试环境配置

提供:
- init_db 建表（CI 空库环境下自动创建 sessions/steps/tasks 等表）
- Boss 表数据清理（测试隔离，autouse）
- Governance Guard 测试绕过（opt-in fixture）
"""
import os
import pytest

# The production default requires a token.  Existing behavior-focused tests
# opt out explicitly; dedicated security tests cover the enabled path.
os.environ.setdefault("AUTH_ENABLED", "false")


@pytest.fixture(autouse=True, scope="session")
def _ensure_db_initialized():
    """Session 级别: 确保数据库表已创建。

    CI 环境无预存 SQLite 文件，必须在所有测试前调用 init_db()。
    """
    from backend.database.database import init_db
    init_db()


@pytest.fixture(autouse=True, scope="function")
def _cleanup_boss_tables():
    """每个测试前后清理 boss 表，防止 stale 数据污染"""
    from backend.database.database import get_db

    yield

    # 测试结束后清理 boss 表
    try:
        with get_db() as db:
            db.execute("DELETE FROM boss_mission_events")
            db.execute("DELETE FROM boss_mission_modules")
            db.execute("DELETE FROM boss_missions")
            db.commit()
    except Exception:
        pass  # 表可能不存在（某些测试不依赖 boss 表）


@pytest.fixture(autouse=False)
def bypass_governance_guard():
    """Opt-in fixture: 绕过 Governance Guard 检查。

    仅在 Boss 相关测试中使用，不污染 Governance 自身的测试。
    通过环境变量 ACO_TEST_BYPASS_GOVERNANCE=true 实现。
    """
    os.environ["ACO_TEST_BYPASS_GOVERNANCE"] = "true"
    yield
    os.environ.pop("ACO_TEST_BYPASS_GOVERNANCE", None)
