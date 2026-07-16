"""
System Doctor — 系统自检工具

检查系统是否正常工作，包括：
1. Python 环境
2. 依赖包
3. 配置文件
4. 数据库
5. AI 服务
6. 能力扫描
7. 主脑管理
8. 路由注册

使用方式：
  python doctor.py
"""
import sys
import os
from pathlib import Path

# 确保项目根目录在 sys.path 中
_PROJECT_ROOT = str(Path(__file__).resolve().parent)
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)


def check_python():
    """检查 Python 环境"""
    version = sys.version.split()[0]
    print(f"[OK] Python {version}")
    return True


def check_dependencies():
    """检查依赖包"""
    required = ["fastapi", "uvicorn", "httpx", "pydantic"]
    missing = []

    for pkg in required:
        try:
            __import__(pkg)
        except ImportError:
            missing.append(pkg)

    if missing:
        print(f"[WARN] Missing packages: {', '.join(missing)}")
        return False

    print(f"[OK] Dependencies installed")
    return True


def check_config():
    """检查配置文件"""
    from backend.config import get_system_status

    try:
        status = get_system_status()
        brain = status.get("current_brain", {})
        print(f"[OK] Config loaded, current brain: {brain.get('name', 'unknown')}")
        return True
    except Exception as e:
        print(f"[FAIL] Config error: {e}")
        return False


def check_database():
    """检查数据库"""
    from backend.database.database import init_db

    try:
        init_db()
        print("[OK] Database initialized")
        return True
    except Exception as e:
        print(f"[FAIL] Database error: {e}")
        return False


def check_capability_scanner():
    """检查能力扫描器"""
    from core.capability_scanner import get_capability_scanner

    try:
        scanner = get_capability_scanner()
        result = scanner.scan_all()
        summary = result.get("summary", {})
        print(f"[OK] Capability scanner: {summary.get('total', 0)} items")
        print(f"     - AI services: {summary.get('ai_services', 0)}")
        print(f"     - Browsers: {summary.get('browsers', 0)}")
        print(f"     - Tools: {summary.get('tools', 0)}")
        print(f"     - Agents: {summary.get('agents', 0)}")
        return True
    except Exception as e:
        print(f"[FAIL] Capability scanner error: {e}")
        return False


def check_brain_manager():
    """检查主脑管理器"""
    from core.brain_manager import get_brain_manager

    try:
        mgr = get_brain_manager()
        current = mgr.get_current()
        available = mgr.list_available()
        print(f"[OK] Brain manager: {current.get('name', 'unknown')}")
        print(f"     - Available brains: {len(available)}")
        return True
    except Exception as e:
        print(f"[FAIL] Brain manager error: {e}")
        return False


def check_routes():
    """检查路由注册"""
    try:
        from backend.app import app
        routes = []
        for route in app.routes:
            if hasattr(route, 'path') and hasattr(route, 'methods'):
                routes.append(f"{list(route.methods)[0]} {route.path}")

        print(f"[OK] Routes registered: {len(routes)}")

        # 检查关键路由
        key_routes = ["/brain/", "/brain/list", "/brain/switch", "/brain/capabilities"]
        for r in key_routes:
            found = any(r in route for route in routes)
            status = "OK" if found else "MISSING"
            print(f"     - {r}: {status}")

        return True
    except Exception as e:
        print(f"[FAIL] Routes error: {e}")
        return False


def check_agents():
    """检查 Agent 模块"""
    agents = [
        ("agents.base_agent", "BaseAgent"),
        ("agents.ceo_agent.agent", "CEOAgent"),
        ("agents.codex_agent.agent", "CodexAgent"),
        ("agents.qa_agent.agent", "QAAgent"),
        ("agents.cto_agent.agent", "CTOAgent"),
        ("agents.system_agent.agent", "SystemAgent"),
        ("agents.openclaw_agent.agent", "OpenClawAgent"),
        ("agents.image_agent.agent", "ImageAgent"),
        ("agents.marketing_agent.agent", "MarketingAgent"),
        ("agents.video_agent.agent", "VideoAgent"),
        ("agents.data_agent.agent", "DataAgent"),
    ]

    ok_count = 0
    for module_path, class_name in agents:
        try:
            import importlib
            module = importlib.import_module(module_path)
            cls = getattr(module, class_name)
            ok_count += 1
        except Exception as e:
            print(f"[WARN] {class_name}: {e}")

    print(f"[OK] Agents loaded: {ok_count}/{len(agents)}")
    return ok_count == len(agents)


def run_doctor():
    """运行所有检查"""
    print("=" * 60)
    print("AI Company OS - System Doctor")
    print("=" * 60)
    print()

    checks = [
        ("Python Environment", check_python),
        ("Dependencies", check_dependencies),
        ("Configuration", check_config),
        ("Database", check_database),
        ("Capability Scanner", check_capability_scanner),
        ("Brain Manager", check_brain_manager),
        ("Routes", check_routes),
        ("Agents", check_agents),
    ]

    passed = 0
    failed = 0

    for name, check_fn in checks:
        print(f"\n--- {name} ---")
        try:
            if check_fn():
                passed += 1
            else:
                failed += 1
        except Exception as e:
            print(f"[FAIL] {name}: {e}")
            failed += 1

    print("\n" + "=" * 60)
    print(f"Results: {passed} passed, {failed} failed")
    print("=" * 60)

    return failed == 0


if __name__ == "__main__":
    success = run_doctor()
    sys.exit(0 if success else 1)
