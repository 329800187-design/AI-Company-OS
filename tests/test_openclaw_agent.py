"""测试 OpenClaw Agent"""
import sys
sys.path.insert(0, r"E:\AI-company-os")

from agents.openclaw_agent.agent import OpenClawAgent, PLAYWRIGHT_AVAILABLE


def test_playwright_available():
    assert PLAYWRIGHT_AVAILABLE, "Playwright 未安装"
    print("[PASS] playwright available")


def test_url_whitelist():
    agent = OpenClawAgent()
    assert agent._is_url_allowed("https://www.baidu.com")
    assert agent._is_url_allowed("https://httpbin.org/status/200")
    assert not agent._is_url_allowed("https://evil-site.com")
    assert not agent._is_url_allowed("")
    print("[PASS] url whitelist")


def test_browser_screenshot():
    agent = OpenClawAgent(headless=True, timeout=15, allow_browser_automation=True)
    result = agent.run({
        "task_id": "test_screenshot",
        "task_type": "browser_screenshot",
        "goal": "截图百度首页",
        "url": "https://www.baidu.com",
    })
    assert result["status"] == "截图完成"
    assert result["success"] is True
    assert "百度" in result.get("page_title", "")
    assert result.get("screenshot_path")
    import os
    assert os.path.exists(result["screenshot_path"])
    print(f"[PASS] browser_screenshot -> {result['page_title']}")


def test_browser_scrape():
    agent = OpenClawAgent(headless=True, timeout=15, allow_browser_automation=True)
    result = agent.run({
        "task_id": "test_scrape",
        "task_type": "browser_scrape",
        "goal": "抓取 httpbin",
        "url": "https://httpbin.org/get",
    })
    assert result["status"] == "抓取完成"
    assert result["success"] is True
    assert len(result["data"]) > 0
    print(f"[PASS] browser_scrape -> {len(result['data'])} lines")


def test_browser_test():
    agent = OpenClawAgent(headless=True, timeout=15, allow_browser_automation=True)
    result = agent.run({
        "task_id": "test_page_test",
        "task_type": "browser_test",
        "goal": "测试百度首页",
        "url": "https://www.baidu.com",
        "checks": [
            {"type": "page_loaded"},
            {"type": "has_title"},
        ],
    })
    assert result["status"] == "测试通过"
    assert result["total_count"] >= 2
    print(f"[PASS] browser_test -> {result['passed_count']}/{result['total_count']} passed")


def test_blocked_url():
    agent = OpenClawAgent(headless=True, timeout=10)
    result = agent.run({
        "task_id": "test_blocked",
        "task_type": "browser_screenshot",
        "url": "https://evil.phishing.site",
    })
    assert result["status"] == "blocked"
    assert result["blocked"] is True
    assert result["blocked_reason"] == "browser_automation_approval_required"
    assert result["success"] is False
    print("[PASS] blocked url protection")


if __name__ == "__main__":
    test_playwright_available()
    test_url_whitelist()
    test_blocked_url()
    print("\n--- Browser tests (needs network) ---")
    test_browser_screenshot()
    test_browser_scrape()
    test_browser_test()
    print("\n[ALL PASS] All OpenClaw Agent tests passed")
