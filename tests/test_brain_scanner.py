"""
测试 Brain Manager 和 Capability Scanner
"""
import sys
from pathlib import Path

# 确保项目根目录在 sys.path 中
_PROJECT_ROOT = str(Path(__file__).resolve().parent.parent)
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)


def test_capability_scanner():
    """测试能力扫描器"""
    from core.capability_scanner import get_capability_scanner

    scanner = get_capability_scanner()
    result = scanner.scan_all()

    assert "ai_services" in result
    assert "browsers" in result
    assert "tools" in result
    assert "agents" in result
    assert "summary" in result

    summary = result["summary"]
    assert summary["total"] >= 0
    assert isinstance(summary["ai_services"], int)
    assert isinstance(summary["browsers"], int)
    assert isinstance(summary["tools"], int)
    assert isinstance(summary["agents"], int)

    print(f"[PASS] capability_scanner: {summary['total']} items found")
    return True


def test_brain_manager():
    """测试主脑管理器"""
    from core.brain_manager import get_brain_manager

    mgr = get_brain_manager()

    # 测试 list_all
    all_brains = mgr.list_all()
    assert len(all_brains) >= 5  # 至少有 5 个内置主脑
    print(f"[PASS] brain_manager.list_all: {len(all_brains)} brains")

    # 测试 get_current
    current = mgr.get_current()
    assert "brain_id" in current
    assert "name" in current
    print(f"[PASS] brain_manager.get_current: {current['name']}")

    # 测试 list_available
    available = mgr.list_available()
    print(f"[PASS] brain_manager.list_available: {len(available)} available")

    # 测试 switch_to（切换到 deepseek）
    result = mgr.switch_to("deepseek")
    assert result["ok"] == True
    print(f"[PASS] brain_manager.switch_to: {result['message'].encode('ascii', 'replace').decode()}")

    # 测试 health_check
    health = mgr.health_check()
    assert isinstance(health, dict)
    print(f"[PASS] brain_manager.health_check: {len(health)} checked")

    return True


def test_config_integration():
    """测试 config.py 的集成"""
    from backend.config import get_system_status, get_brain_manager, get_capability_scanner

    # 测试 get_system_status
    status = get_system_status()
    assert "current_brain" in status
    assert "capabilities" in status
    print(f"[PASS] config.get_system_status: brain={status['current_brain']['name']}")

    return True


def test_brain_router():
    """测试 brain_router 的导入"""
    from backend.routers.brain_router import router
    assert router is not None
    print("[PASS] brain_router imports OK")
    return True


if __name__ == "__main__":
    tests = [
        test_capability_scanner,
        test_brain_manager,
        test_config_integration,
        test_brain_router,
    ]

    passed = 0
    failed = 0

    for test in tests:
        try:
            if test():
                passed += 1
        except Exception as e:
            print(f"[FAIL] {test.__name__}: {e}")
            failed += 1

    print(f"\n{'='*50}")
    print(f"Results: {passed} passed, {failed} failed")
    print(f"{'='*50}")
