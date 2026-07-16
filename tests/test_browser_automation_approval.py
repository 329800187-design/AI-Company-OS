"""浏览器自动化审批闸门测试

验证：
- 默认配置下，browser/ecommerce 采集被阻止
- allow_browser_automation=false 时不调用 hermes CLI
- allow_browser_automation=true 时正常调用 hermes CLI
- auto_run=true 时需浏览器模块被标记为 blocked
- approval_required 事件记录
- structured_output.status = "blocked"
"""
import sys
import os
import json
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest
from unittest.mock import patch, MagicMock


# ── Mock 数据 ────────────────────────────────────────────────

MOCK_MARKET_RESEARCH_RESPONSE = json.dumps({
    "summary": "蓝牙耳机市场持续增长",
    "evidence": [
        {"title": "来源1", "url": "https://real1.com", "type": "source"},
        {"title": "来源2", "url": "https://real2.com", "type": "browser"},
    ],
    "tool_calls": [{"tool": "browser", "args": {}, "result": "采集成功"}],
    "competitors": [
        {"name": "AirPods", "price": "1299", "platform": "Apple"},
        {"name": "Sony", "price": "1699", "platform": "京东"},
    ],
    "pricing": {"range": "99-1999"},
    "warnings": [],
})


def _mock_popen(stdout_text):
    class MockPipe:
        def __init__(self, text):
            self.text = text
            self.used = False

        def read(self, size=-1):
            if self.used:
                return ""
            self.used = True
            return self.text

    class MockProcess:
        returncode = 0

        def __init__(self):
            self.stdout = MockPipe(stdout_text)
            self.stderr = MockPipe("")

        def wait(self, timeout=None):
            return 0

        def kill(self):
            pass

    return MockProcess()


class TestBrowserAutomationApprovalGate:
    """浏览器自动化审批闸门测试"""

    @pytest.fixture(autouse=True)
    def _setup_hermes_provider(self, monkeypatch):
        """设置 BOSS_EXECUTION_PROVIDER=hermes 并重置 registry"""
        monkeypatch.setenv("BOSS_EXECUTION_PROVIDER", "hermes")
        # 确保浏览器自动化审批闸门生效（.env 可能有 BROWSER_AUTOMATION_APPROVED=true）
        monkeypatch.setenv("BROWSER_AUTOMATION_REQUIRE_APPROVAL", "true")
        monkeypatch.setenv("BROWSER_AUTOMATION_APPROVED", "false")
        # 直接 patch config 模块级常量（monkeypatch.setenv 无法更新已加载的模块常量）
        import backend.config as cfg
        monkeypatch.setattr(cfg, "BOSS_EXECUTION_PROVIDER", "hermes")
        monkeypatch.setattr(cfg, "BROWSER_AUTOMATION_REQUIRE_APPROVAL", True)
        monkeypatch.setattr(cfg, "BROWSER_AUTOMATION_APPROVED", False)
        import backend.services.boss_execution_providers as provider_module
        provider_module._registry = None
        # 清除 executor 的 provider 缓存
        import backend.services.boss_module_executors as executor_module
        for template_executors in executor_module._EXECUTOR_REGISTRY.values():
            for executor in template_executors.values():
                executor._provider = None

    @pytest.fixture
    def service(self):
        from backend.services.boss_command_center import BossCommandCenterService
        return BossCommandCenterService()

    @pytest.fixture(autouse=True)
    def _bypass_rate_limit(self):
        with patch("backend.routers.boss_router.rate_limiter") as mock_rl:
            mock_rl.check.return_value = (True, "")
            yield

    def test_default_config_blocks_browser_automation(self, service, monkeypatch):
        """默认配置下，浏览器自动化被阻止（不调用 hermes CLI）"""
        import subprocess
        import shutil

        # Mock Hermes CLI 可用
        monkeypatch.setattr(shutil, "which", lambda x: "/usr/bin/hermes")

        # 记录是否调用了 subprocess（hermes CLI）
        subprocess_called = False
        original_run = subprocess.run

        def mock_run(cmd, **kwargs):
            nonlocal subprocess_called
            if isinstance(cmd, list) and cmd[0] == "hermes":
                subprocess_called = True
            return original_run(cmd, **kwargs)

        monkeypatch.setattr(subprocess, "run", mock_run)

        # 创建 mission 并执行 market 模块（默认不允许浏览器自动化）
        mission = service.create_mission_from_template(
            "ecommerce_product_research",
            goal="测试浏览器自动化审批",
            enabled_modules=["market"],
            allow_browser_automation=False,  # 显式禁止
        )
        mission_id = mission["mission_id"]

        # 执行 market 模块
        updated = service.run_module(mission_id, "market")
        market = next(m for m in updated["modules"] if m["module_id"] == "market")

        # 验证：不调用 hermes CLI
        assert not subprocess_called, "不应调用 hermes CLI（浏览器自动化未授权）"

        # 验证：状态为 blocked
        assert market["status"] == "failed"
        so = market["structured_output"]
        assert so["status"] == "blocked"

        # 验证：事件日志包含 approval_required
        events = service.get_events(mission_id)
        event_types = [e["type"] for e in events]
        assert "approval_required" in event_types

    def test_allow_browser_automation_true_calls_hermes(self, service, monkeypatch):
        """allow_browser_automation=true 时正常调用 hermes CLI"""
        import subprocess
        import shutil

        # Mock Hermes CLI 可用
        monkeypatch.setattr(shutil, "which", lambda x: "/usr/bin/hermes")

        # Mock subprocess.run 返回合法 JSON
        def mock_popen(cmd, **kwargs):
            return _mock_popen(MOCK_MARKET_RESEARCH_RESPONSE)

        monkeypatch.setattr(subprocess, "Popen", mock_popen)

        # 创建 mission 并执行（允许浏览器自动化）
        mission = service.create_mission_from_template(
            "ecommerce_product_research",
            goal="测试浏览器自动化授权",
            enabled_modules=["market"],
            allow_browser_automation=True,  # 显式允许
        )
        mission_id = mission["mission_id"]

        # 执行 market 模块 — 也需要传入 allow_browser_automation
        updated = service.run_module(mission_id, "market", allow_browser_automation=True)
        market = next(m for m in updated["modules"] if m["module_id"] == "market")

        # 验证：正常执行
        assert market["status"] == "done"
        so = market["structured_output"]
        assert so["status"] == "success"
        assert so["provider"] == "hermes"

        # 验证：事件日志不包含 approval_required
        events = service.get_events(mission_id)
        event_types = [e["type"] for e in events]
        assert "approval_required" not in event_types
        assert "hermes_invoked" in event_types

    def test_auto_run_does_not_bypass_approval(self, service, monkeypatch):
        """auto_run=true 时，需要浏览器自动化的模块仍被阻止（v2: auto_run 不再自动执行，需显式 run_module）"""
        import subprocess
        import shutil

        # Mock Hermes CLI 可用
        monkeypatch.setattr(shutil, "which", lambda x: "/usr/bin/hermes")

        # 记录是否调用了 subprocess
        subprocess_called = False
        original_run = subprocess.run

        def mock_run(cmd, **kwargs):
            nonlocal subprocess_called
            if isinstance(cmd, list) and cmd[0] == "hermes":
                subprocess_called = True
            return original_run(cmd, **kwargs)

        monkeypatch.setattr(subprocess, "run", mock_run)

        # 创建 mission（v2: auto_run 不再自动执行）
        mission = service.create_mission_from_template(
            "ecommerce_product_research",
            goal="测试 auto_run 审批",
            auto_run=True,
            allow_browser_automation=False,  # 不允许浏览器自动化
        )

        # v2: auto_run 不再自动执行，需显式 run_module 来测试审批闸门
        updated = service.run_module(mission["mission_id"], "market", allow_browser_automation=False)
        market = next(m for m in updated["modules"] if m["module_id"] == "market")

        # 验证：需要浏览器的模块被标记为 blocked/failed
        assert market["status"] == "failed"
        so = market["structured_output"]
        assert so["status"] == "blocked"

        # 验证：不调用 hermes CLI
        assert not subprocess_called, "auto_run=true 不应绕过浏览器自动化审批"

    def test_blocked_output_has_correct_structure(self, service, monkeypatch):
        """blocked 状态的 structured_output 有正确的结构"""
        import subprocess
        import shutil

        monkeypatch.setattr(shutil, "which", lambda x: "/usr/bin/hermes")

        mission = service.create_mission_from_template(
            "ecommerce_product_research",
            goal="测试 blocked 输出结构",
            enabled_modules=["market"],
            allow_browser_automation=False,
        )
        mission_id = mission["mission_id"]

        updated = service.run_module(mission_id, "market")
        market = next(m for m in updated["modules"] if m["module_id"] == "market")

        so = market["structured_output"]

        # 验证所有必要字段存在
        assert so["status"] == "blocked"
        assert so["provider"] == "blocked_by_approval"
        assert so["evidence_gate_passed"] is False
        assert isinstance(so["evidence"], list)
        assert len(so["evidence"]) == 0  # blocked 时不应有证据
        assert isinstance(so["warnings"], list)
        assert len(so["warnings"]) > 0  # 应有警告信息
        assert "浏览器自动化采集需要用户确认后才能执行" in so["warnings"][0]

    def test_competitor_analysis_blocked_without_approval(self, service, monkeypatch):
        """竞品分析模块在未审批时也被阻止"""
        import subprocess
        import shutil

        monkeypatch.setattr(shutil, "which", lambda x: "/usr/bin/hermes")

        subprocess_called = False
        original_run = subprocess.run

        def mock_run(cmd, **kwargs):
            nonlocal subprocess_called
            if isinstance(cmd, list) and cmd[0] == "hermes":
                subprocess_called = True
            return original_run(cmd, **kwargs)

        monkeypatch.setattr(subprocess, "run", mock_run)

        mission = service.create_mission_from_template(
            "ecommerce_product_research",
            goal="测试竞品分析审批",
            enabled_modules=["market"],  # 只执行 market，它会调用竞品分析
            allow_browser_automation=False,
        )
        mission_id = mission["mission_id"]

        updated = service.run_module(mission_id, "market")
        market = next(m for m in updated["modules"] if m["module_id"] == "market")

        # 验证被阻止
        assert market["status"] == "failed"
        assert market["structured_output"]["status"] == "blocked"
        assert not subprocess_called

    def test_marketing_listing_pack_blocked_without_approval(self, service, monkeypatch):
        """marketing (listing pack) 模块在未审批时也被阻止"""
        import subprocess
        import shutil

        monkeypatch.setattr(shutil, "which", lambda x: "/usr/bin/hermes")

        subprocess_called = False
        original_run = subprocess.run

        def mock_run(cmd, **kwargs):
            nonlocal subprocess_called
            if isinstance(cmd, list) and cmd[0] == "hermes":
                subprocess_called = True
            return original_run(cmd, **kwargs)

        monkeypatch.setattr(subprocess, "run", mock_run)

        mission = service.create_mission_from_template(
            "ecommerce_product_research",
            goal="测试 listing pack 审批",
            enabled_modules=["marketing"],
            allow_browser_automation=False,
        )
        mission_id = mission["mission_id"]

        updated = service.run_module(mission_id, "marketing")
        marketing = next(m for m in updated["modules"] if m["module_id"] == "marketing")

        # 验证被阻止
        assert marketing["status"] == "failed"
        assert marketing["structured_output"]["status"] == "blocked"
        assert not subprocess_called


class TestIsBrowserAutomationAllowed:
    """is_browser_automation_allowed 函数单元测试"""

    def test_require_approval_false_allows_all(self, monkeypatch):
        """BROWSER_AUTOMATION_REQUIRE_APPROVAL=false 时允许所有"""
        monkeypatch.setenv("BROWSER_AUTOMATION_REQUIRE_APPROVAL", "false")
        # 重新加载 config 模块以应用新的环境变量
        import importlib
        import backend.config
        importlib.reload(backend.config)

        from backend.services.boss_execution_providers import is_browser_automation_allowed
        assert is_browser_automation_allowed(allow_from_request=False, module_id="market") is True

    def test_global_approved_allows_all(self, monkeypatch):
        """BROWSER_AUTOMATION_APPROVED=true 时允许所有"""
        monkeypatch.setenv("BROWSER_AUTOMATION_REQUIRE_APPROVAL", "true")
        monkeypatch.setenv("BROWSER_AUTOMATION_APPROVED", "true")
        # 重新加载 config 模块以应用新的环境变量
        import importlib
        import backend.config
        importlib.reload(backend.config)

        from backend.services.boss_execution_providers import is_browser_automation_allowed
        assert is_browser_automation_allowed(allow_from_request=False, module_id="market") is True

    def test_request_approval_allows(self, monkeypatch):
        """请求级别审批允许"""
        monkeypatch.setenv("BROWSER_AUTOMATION_REQUIRE_APPROVAL", "true")
        monkeypatch.setenv("BROWSER_AUTOMATION_APPROVED", "false")
        # 重新加载 config 模块以应用新的环境变量
        import importlib
        import backend.config
        importlib.reload(backend.config)

        from backend.services.boss_execution_providers import is_browser_automation_allowed
        assert is_browser_automation_allowed(allow_from_request=True, module_id="market") is True

    def test_non_browser_module_allowed(self, monkeypatch):
        """不需要浏览器的模块自动允许"""
        monkeypatch.setenv("BROWSER_AUTOMATION_REQUIRE_APPROVAL", "true")
        monkeypatch.setenv("BROWSER_AUTOMATION_APPROVED", "false")
        # 重新加载 config 模块以应用新的环境变量
        import importlib
        import backend.config
        importlib.reload(backend.config)

        from backend.services.boss_execution_providers import is_browser_automation_allowed
        # strategy 和 actions 模块不需要浏览器
        assert is_browser_automation_allowed(allow_from_request=False, module_id="strategy") is True
        assert is_browser_automation_allowed(allow_from_request=False, module_id="actions") is True

    def test_default_blocks_browser_modules(self, monkeypatch):
        """默认配置阻止需要浏览器的模块"""
        monkeypatch.setenv("BROWSER_AUTOMATION_REQUIRE_APPROVAL", "true")
        monkeypatch.setenv("BROWSER_AUTOMATION_APPROVED", "false")
        # 重新加载 config 模块以应用新的环境变量
        import importlib
        import backend.config
        importlib.reload(backend.config)

        from backend.services.boss_execution_providers import is_browser_automation_allowed
        # market, competitor_analysis, marketing 需要浏览器
        assert is_browser_automation_allowed(allow_from_request=False, module_id="market") is False
        assert is_browser_automation_allowed(allow_from_request=False, module_id="competitor_analysis") is False
        assert is_browser_automation_allowed(allow_from_request=False, module_id="marketing") is False


class TestOpenClawAgentApproval:
    """OpenClaw Agent 浏览器授权拦截测试"""

    def test_blocks_browser_scrape_without_approval(self):
        """默认构造的 OpenClawAgent 拒绝浏览器任务"""
        from agents.openclaw_agent.agent import OpenClawAgent
        agent = OpenClawAgent(headless=True, timeout=5)
        result = agent.run({
            "task_type": "browser_scrape",
            "goal": "测试抓取",
            "url": "https://example.com",
        })
        assert result["status"] == "blocked"
        assert result["blocked_reason"] == "browser_automation_approval_required"
        assert result["mode"] == "blocked"

    def test_blocks_browser_screenshot_without_approval(self):
        """默认 OpenClawAgent 拒绝截图任务"""
        from agents.openclaw_agent.agent import OpenClawAgent
        agent = OpenClawAgent(headless=True, timeout=5)
        result = agent.run({
            "task_type": "browser_screenshot",
            "goal": "截图",
            "url": "https://example.com",
        })
        assert result["status"] == "blocked"

    def test_blocks_browser_form_fill_without_approval(self):
        """默认 OpenClawAgent 拒绝表单填充任务"""
        from agents.openclaw_agent.agent import OpenClawAgent
        agent = OpenClawAgent(headless=True, timeout=5)
        result = agent.run({
            "task_type": "browser_form_fill",
            "goal": "填写表单",
            "url": "https://example.com",
        })
        assert result["status"] == "blocked"

    def test_allows_with_approval(self):
        """allow_browser_automation=True 时允许浏览器任务"""
        from agents.openclaw_agent.agent import OpenClawAgent
        agent = OpenClawAgent(headless=True, timeout=5, allow_browser_automation=True)
        # 即使有授权，如果没有 Playwright 安装也应该返回 Playwright 未安装错误
        # 而不是 blocked
        result = agent.run({
            "task_type": "browser_scrape",
            "goal": "测试抓取",
            "url": "https://example.com",
        })
        assert result["status"] != "blocked"

    def test_non_browser_tasks_unaffected(self):
        """research/reason/chat 类型不受授权影响"""
        from agents.openclaw_agent.agent import OpenClawAgent
        agent = OpenClawAgent(headless=True, timeout=5)
        # chat 任务不需要浏览器
        result = agent.run({
            "task_type": "chat",
            "goal": "你好",
        })
        assert result.get("status") != "blocked"

    def test_blocked_response_has_message(self):
        """blocked 结果包含正确的提示信息"""
        from agents.openclaw_agent.agent import OpenClawAgent
        agent = OpenClawAgent(headless=True, timeout=5)
        result = agent.run({
            "task_type": "browser_scrape",
            "goal": "测试",
            "url": "https://example.com",
        })
        assert "需要用户授权" in result["message"]
        assert "授权" in result["result"]


class TestAgentRouterApproval:
    """Agent Router 浏览器授权闸门测试"""

    def test_openclaw_default_blocks(self, monkeypatch):
        """/agents/openclaw/run 默认不传授权时被拦截"""
        from agents.openclaw_agent.agent import OpenClawAgent
        agent = OpenClawAgent(headless=True, timeout=5)
        result = agent.run({
            "task_type": "browser_scrape",
            "goal": "测试",
            "url": "https://example.com",
        })
        # 不传 allow_browser_automation 时，应该被拦截
        assert result["status"] == "blocked"

    def test_openclaw_explicit_allow(self):
        """显式传 allow_browser_automation=True 时不被拦截"""
        from agents.openclaw_agent.agent import OpenClawAgent
        agent = OpenClawAgent(headless=True, timeout=5, allow_browser_automation=True)
        result = agent.run({
            "task_type": "browser_scrape",
            "goal": "测试",
            "url": "https://example.com",
        })
        # 有授权，应该进入 Playwright 执行（可能因环境失败，但不是 blocked）
        assert result["status"] != "blocked"
