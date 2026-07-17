"""
Capability Router 测试

覆盖:
- exact capability match
- task_type fallback match
- 多 agent 匹配时选择结果稳定（risk_level, capabilities 数量, id 字典序）
- 无匹配时返回 unassigned（不抛异常）
- enabled=false 的 agent 不参与路由
- manifest scan 失败时不崩溃
- get_agent_enabled=False 的 agent 不参与路由
"""
import os
import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest
from unittest.mock import patch

from backend.schemas.agent_manifest import AgentManifest
from backend.services.capability_router import route_capability, RoutingResult


# 默认让所有 agent 通过 agent_discovery 检查（除非测试中显式 mock）
@pytest.fixture(autouse=True)
def _mock_agent_discovery_enabled():
    with patch("backend.services.capability_router.get_agent_enabled", return_value=True):
        yield


# ── 测试用 manifest 数据 ──────────────────────────────────

def _manifest(**overrides) -> AgentManifest:
    """快速构建测试用 manifest"""
    defaults = dict(
        id="test_agent",
        name="Test Agent",
        version="1.0.0",
        entrypoint="test.agent:TestAgent",
        capabilities=["cap_a"],
        task_types=["type_a"],
        risk_level="low",
        enabled=True,
        description="test",
    )
    defaults.update(overrides)
    return AgentManifest(**defaults)


MARKETING = _manifest(
    id="marketing",
    name="营销内容",
    capabilities=["copywriting", "social_media", "seo", "email", "brand"],
    task_types=["copywriting", "social_media", "seo_article", "email_campaign", "brand_strategy", "campaign_plan"],
)

IMAGE = _manifest(
    id="image",
    name="图片生成",
    capabilities=["image", "dalle", "vision"],
    task_types=["image_generate", "image_analyze"],
)

DATA = _manifest(
    id="data",
    name="数据分析",
    capabilities=["data", "pandas", "visualization", "csv", "excel"],
    task_types=["data_load", "data_explore", "data_clean", "data_analyze", "data_viz", "data_export"],
)

ECHO = _manifest(
    id="example_echo",
    name="Echo Agent",
    capabilities=["echo", "copywriting"],
    task_types=["echo", "copywriting"],
)

ALL_MANIFESTS = {m.id: m for m in [MARKETING, IMAGE, DATA, ECHO]}


# ── 精确 capability 匹配 ──────────────────────────────────

class TestExactCapabilityMatch:
    """精确 capability 匹配测试"""

    def test_exact_cap_copywriting(self):
        """copywriting 能力同时匹配 marketing 和 echo，echo caps 更少更精确，优先"""
        result = route_capability("copywriting", manifests=ALL_MANIFESTS)
        assert result.assigned_agent_id == "example_echo"
        assert result.matched_capability == "copywriting"
        assert "marketing" in result.candidates
        assert "example_echo" in result.candidates
        assert result.reason.startswith("exact capability match")

    def test_exact_cap_image(self):
        """image 能力应匹配到 image agent"""
        result = route_capability("image", manifests=ALL_MANIFESTS)
        assert result.assigned_agent_id == "image"
        assert result.matched_capability == "image"

    def test_exact_cap_data(self):
        """data 能力应匹配到 data agent"""
        result = route_capability("data", manifests=ALL_MANIFESTS)
        assert result.assigned_agent_id == "data"
        assert result.matched_capability == "data"

    def test_exact_cap_pandas(self):
        """pandas 能力应匹配到 data agent"""
        result = route_capability("pandas", manifests=ALL_MANIFESTS)
        assert result.assigned_agent_id == "data"

    def test_exact_cap_dalle(self):
        """dalle 能力应匹配到 image agent"""
        result = route_capability("dalle", manifests=ALL_MANIFESTS)
        assert result.assigned_agent_id == "image"


# ── task_type fallback 匹配 ───────────────────────────────

class TestTaskTypeFallback:
    """task_type 回退匹配测试"""

    def test_fallback_image_generate(self):
        """task_type=image_generate 应匹配到 image agent"""
        result = route_capability(
            required_capability="nonexistent_cap",
            task_type="image_generate",
            manifests=ALL_MANIFESTS,
        )
        assert result.assigned_agent_id == "image"
        assert result.matched_capability == "image_generate"
        assert result.reason.startswith("task_type fallback")

    def test_fallback_data_analyze(self):
        """task_type=data_analyze 应匹配到 data agent"""
        result = route_capability(
            required_capability="nonexistent_cap",
            task_type="data_analyze",
            manifests=ALL_MANIFESTS,
        )
        assert result.assigned_agent_id == "data"

    def test_no_cap_no_task_type(self):
        """两者都不匹配时返回 unassigned"""
        result = route_capability(
            required_capability="nonexistent_cap",
            task_type="nonexistent_type",
            manifests=ALL_MANIFESTS,
        )
        assert result.assigned_agent_id is None
        assert result.reason.startswith("no agent found")


# ── 多 agent 匹配稳定性 ───────────────────────────────────

class TestMultiAgentStability:
    """多 agent 匹配时选择结果稳定"""

    def test_copywriting_chooses_echo_over_marketing(self):
        """copywriting 同时匹配 marketing(5 caps) 和 echo(2 caps)，echo 更精确应优先"""
        result = route_capability("copywriting", manifests=ALL_MANIFESTS)
        assert result.assigned_agent_id == "example_echo"
        assert len(result.candidates) >= 2

    def test_stable_sort_by_id(self):
        """当 risk_level 和 capabilities 数量相同时，按 id 字典序选择"""
        agents = {
            "z_agent": _manifest(id="z_agent", capabilities=["shared_cap"], task_types=[], risk_level="low"),
            "a_agent": _manifest(id="a_agent", capabilities=["shared_cap"], task_types=[], risk_level="low"),
        }
        result = route_capability("shared_cap", manifests=agents)
        assert result.assigned_agent_id == "a_agent"

    def test_risk_level_low_preferred(self):
        """risk_level=low 应优先于 risk_level=high"""
        agents = {
            "high_risk": _manifest(id="high_risk", capabilities=["cap_x"], risk_level="high"),
            "low_risk": _manifest(id="low_risk", capabilities=["cap_x"], risk_level="low"),
        }
        result = route_capability("cap_x", manifests=agents)
        assert result.assigned_agent_id == "low_risk"


# ── 无匹配场景 ────────────────────────────────────────────

class TestNoMatch:
    """无匹配场景测试"""

    def test_no_enabled_agents(self):
        """所有 agent disabled 时返回 unassigned"""
        agents = {
            "disabled1": _manifest(id="disabled1", capabilities=["cap_a"], enabled=False),
        }
        result = route_capability("cap_a", manifests=agents)
        assert result.assigned_agent_id is None
        assert "no enabled agents" in result.reason

    def test_empty_manifests(self):
        """空 manifests 时返回 unassigned"""
        result = route_capability("anything", manifests={})
        assert result.assigned_agent_id is None

    def test_no_exception_on_missing(self):
        """找不到时不抛异常，返回 RoutingResult"""
        result = route_capability("totally_missing", manifests=ALL_MANIFESTS)
        assert isinstance(result, RoutingResult)
        assert result.assigned_agent_id is None


# ── enabled 状态过滤 ──────────────────────────────────────

class TestEnabledFilter:
    """enabled 状态过滤测试"""

    def test_disabled_agent_not_routed(self):
        """disabled agent 不参与路由"""
        agents = {
            "disabled": _manifest(id="disabled", capabilities=["cap_a"], enabled=False),
            "enabled": _manifest(id="enabled", capabilities=["cap_a"], enabled=True),
        }
        result = route_capability("cap_a", manifests=agents)
        assert result.assigned_agent_id == "enabled"
        assert "disabled" not in result.candidates

    @patch("backend.services.capability_router.get_agent_enabled")
    def test_agent_discovery_disabled_not_routed(self, mock_get_enabled):
        """agent_discovery 禁用的 agent 不参与路由"""
        def side_effect(agent_id):
            return agent_id == "enabled"
        mock_get_enabled.side_effect = side_effect

        agents = {
            "disabled_by_config": _manifest(id="disabled_by_config", capabilities=["cap_a"], enabled=True),
            "enabled": _manifest(id="enabled", capabilities=["cap_a"], enabled=True),
        }
        result = route_capability("cap_a", manifests=agents)
        assert result.assigned_agent_id == "enabled"
        assert "disabled_by_config" not in result.candidates

    @patch("backend.services.capability_router.get_agent_enabled")
    def test_multi_agent_config_disabled_skipped(self, mock_get_enabled):
        """多 agent 中 config disabled 的 agent 被跳过"""
        def side_effect(agent_id):
            return agent_id != "marketing"
        mock_get_enabled.side_effect = side_effect

        result = route_capability("copywriting", manifests=ALL_MANIFESTS)
        # marketing 被 config 禁用，只有 echo 匹配
        assert result.assigned_agent_id == "example_echo"
        assert "marketing" not in result.candidates

    @patch("backend.services.capability_router.get_agent_enabled")
    def test_manifest_disabled_still_filtered(self, mock_get_enabled):
        """manifest.enabled=false 仍然不参与路由"""
        mock_get_enabled.return_value = True  # agent_discovery 允许

        agents = {
            "disabled": _manifest(id="disabled", capabilities=["cap_a"], enabled=False),
            "enabled": _manifest(id="enabled", capabilities=["cap_a"], enabled=True),
        }
        result = route_capability("cap_a", manifests=agents)
        assert result.assigned_agent_id == "enabled"
        assert "disabled" not in result.candidates


# ── manifest scan 失败处理 ────────────────────────────────

class TestScanFailure:
    """manifest scan 失败处理"""

    @patch("backend.services.capability_router.scan_manifests", side_effect=Exception("disk error"))
    def test_scan_failure_returns_unassigned(self, mock_scan):
        """scan 失败时返回 unassigned，不抛异常"""
        result = route_capability("any_cap")
        assert result.assigned_agent_id is None
        assert "scan failed" in result.reason
