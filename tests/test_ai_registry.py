"""AI Registry 测试"""
import os, sys, json
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest
from backend.ai_registry.registry import (
    AIRegistry, CCScanner, OpenClawScanner, CodexScanner, ChatGPTScanner, KimiScanner,
    get_registry,
)


def test_cc_switch_scan():
    scanner = CCScanner()
    svc = scanner.scan()
    assert svc is not None
    assert svc.service_id == "cc-switch"
    print(f"CC Switch: status={svc.status}, models={svc.models}")


def test_openclaw_scan():
    scanner = OpenClawScanner()
    svc = scanner.scan()
    assert svc is not None
    assert svc.service_id == "openclaw"
    print(f"OpenClaw: status={svc.status}")


def test_codex_scan():
    scanner = CodexScanner()
    svc = scanner.scan()
    assert svc is not None
    assert svc.service_id == "codex-cli"
    print(f"Codex: status={svc.status}, exe={svc.exe_path}")


def test_chatgpt_scan():
    scanner = ChatGPTScanner()
    svc = scanner.scan()
    assert svc is not None
    assert svc.service_id == "chatgpt"
    print(f"ChatGPT: status={svc.status}, exe={svc.exe_path}")


def test_kimi_scan():
    scanner = KimiScanner()
    svc = scanner.scan()
    assert svc is not None
    assert svc.service_id == "kimi"
    print(f"Kimi: status={svc.status}, exe={svc.exe_path}, pid={svc.pid}")


def test_registry_scan_all():
    reg = AIRegistry()
    services = reg.scan_all(force=True)
    assert len(services) >= 4
    print(f"Scan found {len(services)} services")
    for svc in services.values():
        print(f"  {svc.service_id:15s} | {svc.status:12s} | caps={svc.capabilities}")


def test_registry_capabilities():
    reg = AIRegistry()
    caps = reg.get_capabilities()
    print("Capabilities:", json.dumps(caps, indent=2, ensure_ascii=False))
    assert isinstance(caps, dict)


def test_registry_route_by_goal():
    reg = AIRegistry()
    reg.scan_all()

    # 代码 → Codex
    route = reg.route_by_goal("写一个计算质数的Python脚本")
    assert route["service"] == "codex-cli"
    print(f"Code task → {route['service']}")

    # 浏览器 → OpenClaw
    route = reg.route_by_goal("打开百度首页并截图")
    assert route["service"] == "openclaw"
    print(f"Browser task → {route['service']}")

    # 文件分析 → ChatGPT
    route = reg.route_by_goal("分析这份PDF报告并总结")
    assert route["service"] == "chatgpt"
    print(f"File analysis → {route['service']}")

    # 图片 → Kimi
    route = reg.route_by_goal("帮我设计一张活动海报")
    assert route["service"] == "kimi"
    print(f"Image → {route['service']}")

    # General → CC Switch
    route = reg.route_by_goal("帮我写一封英文商务邮件")
    assert route["service"] == "cc-switch"
    print(f"General task → {route['service']}")


def test_registry_best_for():
    reg = AIRegistry()
    reg.scan_all()

    best = reg.best_for("chat")
    print(f"Best for chat: {best}")
    assert best is not None

    best = reg.best_for("browser")
    print(f"Best for browser: {best}")
    assert best is not None


def test_registry_list_all():
    reg = get_registry()
    services = reg.list_all()
    assert len(services) >= 4
    for s in services:
        assert "service_id" in s
        assert "capabilities" in s
        print(f"{s['name']:20s} {s['status']:12s} [{', '.join(s['capabilities'])}]")


def test_registry_list_online():
    reg = get_registry()
    online = reg.list_online()
    print(f"Online: {len(online)}")
    for s in online:
        print(f"  {s['name']}")


def test_cc_switch_execute():
    """实际调一次 CC Switch → DeepSeek

    注意：这是外部本机服务 integration test，不应阻塞离线单元回归。
    当 CC Switch 不在线或上游 provider 返回 502/503/504 时自动 skip。
    仅在返回结构错误、执行器代码异常等真正问题上 fail。
    """
    reg = get_registry()
    reg.scan_all()

    svc = reg.get_service("cc-switch")
    if not svc or svc.status != "online":
        pytest.skip("CC Switch not online")

    result = reg.execute("cc-switch", {
        "prompt": "说一句话介绍你自己，不超过20个字",
        "max_tokens": 300,
    })
    print("CC Switch result:", json.dumps(result, indent=2, ensure_ascii=False))

    if not result.get("success"):
        error_msg = str(result.get("error", ""))
        # 上游 provider 暂时不可用 → skip（不阻塞离线回归）
        if any(code in error_msg for code in ("502", "503", "504", "429", "Service Unavailable", "Too Many Requests")):
            pytest.skip(f"CC Switch upstream provider unavailable: {error_msg[:120]}")
        # 连接失败 → skip（本机服务可能未启动）
        if any(code in error_msg for code in ("Connection refused", "ConnectError", "ConnectTimeout")):
            pytest.skip(f"CC Switch connection failed: {error_msg[:120]}")
        # 其他错误 → 真正的失败（结构错误、代码异常等）
        assert False, f"CC Switch execute failed: {error_msg[:200]}"

    assert "result" in result
    assert len(result["result"]) > 0


def test_registry_singleton():
    r1 = get_registry()
    r2 = get_registry()
    assert r1 is r2


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
