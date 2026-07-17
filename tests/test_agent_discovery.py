"""
Agent Discovery 测试

覆盖:
- AgentCapability.to_dict() 返回所有新增字段
- risk_level 默认值和 kind-based 自动设置
- timeout_seconds 默认值
- input_schema / output_schema / tools 安全默认值
- disabled agent 不参与 capability routing（已在 test_capability_router.py 覆盖）
"""
import os
import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest

from backend.services.agent_discovery import AgentCapability, AgentDiscovery


# ── AgentCapability.to_dict() 新增字段测试 ──────────────────

class TestAgentCapabilityNewFields:
    """验证 to_dict() 包含所有新增协议字段"""

    def test_to_dict_has_risk_level(self):
        cap = AgentCapability(id="test", name="Test", risk_level="high")
        d = cap.to_dict()
        assert "risk_level" in d
        assert d["risk_level"] == "high"

    def test_to_dict_risk_level_default(self):
        cap = AgentCapability(id="test", name="Test")
        d = cap.to_dict()
        assert d["risk_level"] == "low"

    def test_to_dict_has_timeout_seconds(self):
        cap = AgentCapability(id="test", name="Test", timeout_seconds=120)
        d = cap.to_dict()
        assert d["timeout_seconds"] == 120

    def test_to_dict_timeout_seconds_default(self):
        cap = AgentCapability(id="test", name="Test")
        d = cap.to_dict()
        assert d["timeout_seconds"] == 60

    def test_to_dict_has_input_output_schema(self):
        schema_in = {"type": "object", "properties": {"goal": {"type": "string"}}}
        schema_out = {"type": "object", "properties": {"output": {"type": "string"}}}
        cap = AgentCapability(
            id="test", name="Test",
            input_schema=schema_in,
            output_schema=schema_out,
        )
        d = cap.to_dict()
        assert d["input_schema"] == schema_in
        assert d["output_schema"] == schema_out

    def test_to_dict_schema_defaults_to_none(self):
        cap = AgentCapability(id="test", name="Test")
        d = cap.to_dict()
        assert d["input_schema"] is None
        assert d["output_schema"] is None

    def test_to_dict_has_tools(self):
        cap = AgentCapability(id="test", name="Test", tools=["web_search", "code_exec"])
        d = cap.to_dict()
        assert d["tools"] == ["web_search", "code_exec"]

    def test_to_dict_tools_default_empty(self):
        cap = AgentCapability(id="test", name="Test")
        d = cap.to_dict()
        assert d["tools"] == []

    def test_to_dict_complete_field_coverage(self):
        """to_dict() 应包含所有协议要求的字段"""
        cap = AgentCapability(id="x", name="X")
        d = cap.to_dict()
        required_fields = [
            "id", "name", "kind", "source", "status",
            "enabled", "capabilities", "task_types",
            "risk_level", "requires_confirmation", "timeout_seconds",
            "input_schema", "output_schema", "tools",
            "health", "last_error",
            "supports_files", "supports_web_search",
            "supports_code_execution", "supports_browser",
        ]
        for field in required_fields:
            assert field in d, f"Missing field: {field}"


# ── AgentDiscovery risk_level 自动设置测试 ──────────────────

class TestDiscoveryRiskLevel:
    """验证 _apply_enabled_config 根据 kind 自动设置 risk_level"""

    def test_cli_agent_gets_high_risk(self):
        """CLI agent 默认 risk_level=low，_apply_enabled_config 应升级为 high"""
        discovery = AgentDiscovery()
        # 手动注入一个 CLI agent（跳过实际扫描）
        discovery._agents["test_cli"] = AgentCapability(
            id="test_cli", name="Test CLI", kind="cli",
            risk_level="low", enabled=True, source="cli",
        )
        discovery._apply_enabled_config()
        assert discovery._agents["test_cli"].risk_level == "high"

    def test_http_agent_gets_high_risk(self):
        """HTTP agent 默认 risk_level=low，_apply_enabled_config 应升级为 high"""
        discovery = AgentDiscovery()
        discovery._agents["test_http"] = AgentCapability(
            id="test_http", name="Test HTTP", kind="http",
            risk_level="low", enabled=True, source="http",
        )
        discovery._apply_enabled_config()
        assert discovery._agents["test_http"].risk_level == "high"

    def test_mcp_agent_gets_medium_risk(self):
        """MCP agent 默认 risk_level=low，_apply_enabled_config 应升级为 medium"""
        discovery = AgentDiscovery()
        discovery._agents["test_mcp"] = AgentCapability(
            id="test_mcp", name="Test MCP", kind="mcp",
            risk_level="low", enabled=True, source="mcp",
        )
        discovery._apply_enabled_config()
        assert discovery._agents["test_mcp"].risk_level == "medium"

    def test_api_agent_stays_low_risk(self):
        """API agent 保持 risk_level=low"""
        discovery = AgentDiscovery()
        discovery._agents["test_api"] = AgentCapability(
            id="test_api", name="Test API", kind="api",
            risk_level="low", enabled=True, source="api",
        )
        discovery._apply_enabled_config()
        assert discovery._agents["test_api"].risk_level == "low"

    def test_explicit_high_risk_not_downgraded(self):
        """显式设置 risk_level=high 不应被降级"""
        discovery = AgentDiscovery()
        discovery._agents["custom"] = AgentCapability(
            id="custom", name="Custom", kind="cli",
            risk_level="high", enabled=True, source="cli",
        )
        discovery._apply_enabled_config()
        assert discovery._agents["custom"].risk_level == "high"


# ── disabled agent 不参与 routing 集成测试 ──────────────────

class TestDisabledAgentRouting:
    """disabled agent 不参与 capability routing（与 test_capability_router.py 互补）"""

    def test_disabled_agent_not_in_scan_results_as_enabled(self):
        """disabled agent 在 scan_all 后 enabled=False"""
        from unittest.mock import patch
        discovery = AgentDiscovery()
        # 注入一个默认禁用的 agent
        discovery._agents["disabled_test"] = AgentCapability(
            id="disabled_test", name="Disabled Test", kind="cli",
            enabled=False, source="cli",
        )
        # Mock _load_enabled_config 返回空（使用默认配置）
        with patch("backend.services.agent_discovery._load_enabled_config", return_value={}):
            discovery._apply_enabled_config()
        assert discovery._agents["disabled_test"].enabled is False

    def test_enabled_agent_stays_enabled(self):
        """enabled agent 在 _apply_enabled_config 后，若在配置中则保持 enabled"""
        from unittest.mock import patch
        discovery = AgentDiscovery()
        discovery._agents["enabled_test"] = AgentCapability(
            id="enabled_test", name="Enabled Test", kind="api",
            enabled=True, source="api",
        )
        # 模拟配置中已启用该 agent
        with patch("backend.services.agent_discovery._load_enabled_config", return_value={"enabled_test": True}):
            discovery._apply_enabled_config()
        assert discovery._agents["enabled_test"].enabled is True
