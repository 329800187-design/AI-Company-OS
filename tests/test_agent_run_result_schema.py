"""AgentRunResult Schema 测试 — 验证统一结果结构"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest
from backend.schemas.agent_protocol import AgentRunResult


class TestAgentRunResultSchema:
    """测试 AgentRunResult 模型字段"""

    def test_default_values(self):
        """测试默认值"""
        result = AgentRunResult()
        assert result.ok is False
        assert result.mode == "single_agent"
        assert result.agent_id == ""
        assert result.task_type == ""
        assert result.summary == ""
        assert result.structured_output == {}
        assert result.output == {}
        assert result.artifacts == []
        assert result.warnings == []
        assert result.errors == []
        assert result.error is None
        assert result.next_actions == []
        assert result.risk_decision is None
        assert result.timeline_events == []
        assert result.metadata == {}

    def test_all_fields(self):
        """测试所有字段"""
        result = AgentRunResult(
            ok=True,
            mode="single_agent",
            agent_id="marketing",
            task_type="copywriting",
            summary="文案已生成",
            structured_output={"headline": "测试标题", "body": "测试内容"},
            output={"headline": "测试标题", "body": "测试内容"},
            artifacts=["artifact1.md"],
            warnings=["这是一个警告"],
            errors=["这是一个错误"],
            error="错误信息",
            next_actions=["下一步操作1", "下一步操作2"],
            risk_decision={"risk_level": "low", "recommended_action": "allow"},
            timeline_events=[{"event": "start", "timestamp": "2024-01-01"}],
            metadata={"task_id": "test_123", "duration_ms": 1000},
        )

        assert result.ok is True
        assert result.mode == "single_agent"
        assert result.agent_id == "marketing"
        assert result.task_type == "copywriting"
        assert result.summary == "文案已生成"
        assert result.structured_output == {"headline": "测试标题", "body": "测试内容"}
        assert result.output == {"headline": "测试标题", "body": "测试内容"}
        assert result.artifacts == ["artifact1.md"]
        assert result.warnings == ["这是一个警告"]
        assert result.errors == ["这是一个错误"]
        assert result.error == "错误信息"
        assert result.next_actions == ["下一步操作1", "下一步操作2"]
        assert result.risk_decision == {"risk_level": "low", "recommended_action": "allow"}
        assert result.timeline_events == [{"event": "start", "timestamp": "2024-01-01"}]
        assert result.metadata == {"task_id": "test_123", "duration_ms": 1000}

    def test_backward_compatibility(self):
        """测试向后兼容性 - 使用旧字段名"""
        result = AgentRunResult(
            ok=True,
            agent_id="marketing",
            output={"headline": "测试标题"},
            artifacts=["artifact1.md"],
            error=None,
            metadata={"task_id": "test_123"},
        )

        assert result.ok is True
        assert result.agent_id == "marketing"
        assert result.output == {"headline": "测试标题"}
        assert result.artifacts == ["artifact1.md"]
        assert result.error is None
        assert result.metadata == {"task_id": "test_123"}

        # 新字段应该有默认值
        assert result.mode == "single_agent"
        assert result.task_type == ""
        assert result.summary == ""
        assert result.structured_output == {}
        assert result.warnings == []
        assert result.errors == []
        assert result.next_actions == []
        assert result.risk_decision is None
        assert result.timeline_events == []

    def test_alias_support(self):
        """测试别名支持"""
        result = AgentRunResult(
            **{
                "ok": True,
                "智能体ID": "marketing",
                "结构化产出": {"headline": "测试标题"},
                "产出": {"body": "测试内容"},
                "产物": ["artifact1.md"],
                "错误": "错误信息",
                "元数据": {"task_id": "test_123"},
            }
        )

        assert result.ok is True
        assert result.agent_id == "marketing"
        assert result.structured_output == {"headline": "测试标题"}
        assert result.output == {"body": "测试内容"}
        assert result.artifacts == ["artifact1.md"]
        assert result.error == "错误信息"
        assert result.metadata == {"task_id": "test_123"}

    def test_model_dump(self):
        """测试模型序列化"""
        result = AgentRunResult(
            ok=True,
            agent_id="marketing",
            task_type="copywriting",
            summary="文案已生成",
            structured_output={"headline": "测试标题"},
            output={"headline": "测试标题"},
            artifacts=["artifact1.md"],
            warnings=["警告"],
            errors=["错误"],
            next_actions=["下一步"],
            risk_decision={"risk_level": "low"},
            timeline_events=[],
            metadata={"task_id": "test_123"},
        )

        data = result.model_dump()
        assert data["ok"] is True
        assert data["agent_id"] == "marketing"
        assert data["task_type"] == "copywriting"
        assert data["summary"] == "文案已生成"
        assert data["structured_output"] == {"headline": "测试标题"}
        assert data["output"] == {"headline": "测试标题"}
        assert data["artifacts"] == ["artifact1.md"]
        assert data["warnings"] == ["警告"]
        assert data["errors"] == ["错误"]
        assert data["next_actions"] == ["下一步"]
        assert data["risk_decision"] == {"risk_level": "low"}
        assert data["timeline_events"] == []
        assert data["metadata"] == {"task_id": "test_123"}

    def test_model_dump_by_alias(self):
        """测试使用别名序列化"""
        result = AgentRunResult(
            ok=True,
            agent_id="marketing",
            structured_output={"headline": "测试标题"},
            output={"headline": "测试标题"},
            artifacts=["artifact1.md"],
            error="错误信息",
            metadata={"task_id": "test_123"},
        )

        data = result.model_dump(by_alias=True)
        assert data["ok"] is True
        assert data["智能体ID"] == "marketing"
        assert data["结构化产出"] == {"headline": "测试标题"}
        assert data["产出"] == {"headline": "测试标题"}
        assert data["产物"] == ["artifact1.md"]
        assert data["错误"] == "错误信息"
        assert data["元数据"] == {"task_id": "test_123"}

    def test_extra_fields_allowed(self):
        """测试允许额外字段"""
        result = AgentRunResult(
            ok=True,
            agent_id="marketing",
            extra_field="extra_value",
            another_field=123,
        )

        assert result.ok is True
        assert result.agent_id == "marketing"
        # 额外字段应该被允许（因为 extra="allow"）
        assert hasattr(result, "extra_field")
        assert hasattr(result, "another_field")

    def test_risk_decision_optional(self):
        """测试 risk_decision 可选"""
        result_without_risk = AgentRunResult(ok=True, agent_id="marketing")
        result_with_risk = AgentRunResult(
            ok=True,
            agent_id="marketing",
            risk_decision={"risk_level": "high", "recommended_action": "review_required"},
        )

        assert result_without_risk.risk_decision is None
        assert result_with_risk.risk_decision == {"risk_level": "high", "recommended_action": "review_required"}

    def test_timeline_events_optional(self):
        """测试 timeline_events 可选"""
        result_without_events = AgentRunResult(ok=True, agent_id="marketing")
        result_with_events = AgentRunResult(
            ok=True,
            agent_id="marketing",
            timeline_events=[
                {"event": "start", "timestamp": "2024-01-01T00:00:00"},
                {"event": "end", "timestamp": "2024-01-01T00:01:00"},
            ],
        )

        assert result_without_events.timeline_events == []
        assert len(result_with_events.timeline_events) == 2


class TestAgentRunResultMarketingIntegration:
    """测试 AgentRunResult 与 Marketing Agent 的集成"""

    def test_marketing_result_fields(self):
        """测试 Marketing Agent 返回的结果包含必要字段"""
        # 模拟 MarketingAgent 返回的结果
        marketing_raw = {
            "task_id": "mkt_12345678",
            "ok": True,
            "success": True,
            "agent": "marketing_agent",
            "agent_name": "Marketing 营销内容",
            "status": "生成完成",
            "summary": "手工耳环小红书种草文案",
            "result": "手工耳环小红书种草文案",
            "data": {
                "headline": "手工耳环，让你更美丽",
                "body": "这是一段测试内容...",
                "cta": "立即购买",
                "content_type": "social_media",
            },
            "output": {
                "headline": "手工耳环，让你更美丽",
                "body": "这是一段测试内容...",
                "cta": "立即购买",
                "content_type": "social_media",
            },
            "error": None,
            "meta": {
                "task_id": "mkt_12345678",
                "duration_ms": 0,
                "model": "deepseek-chat",
                "tokens_used": 0,
                "fallback": False,
            },
        }

        # 使用 _map_result 函数进行转换
        from backend.services.agent_executor import _map_result
        result = _map_result("marketing", "mkt_12345678", marketing_raw)

        # 验证字段映射
        assert result.ok is True
        assert result.agent_id == "marketing"
        assert result.summary == "手工耳环小红书种草文案"
        assert result.task_type == ""  # MarketingAgent 没有返回 task_type
        assert result.structured_output == marketing_raw["data"]
        assert result.output == marketing_raw["data"]
        assert result.warnings == []
        assert result.errors == []
        assert result.error is None
        assert result.metadata["task_id"] == "mkt_12345678"

    def test_marketing_fallback_result(self):
        """测试 Marketing Agent 模板降级结果"""
        marketing_fallback = {
            "task_id": "mkt_87654321",
            "ok": True,
            "success": True,
            "agent": "marketing_agent",
            "agent_name": "Marketing 营销内容",
            "status": "模板模式（未调用 AI）",
            "summary": "未配置 AI API Key，使用模板占位内容。这不是真实 AI 生成的结果。",
            "result": "未配置 AI API Key，使用模板占位内容。这不是真实 AI 生成的结果。",
            "data": {
                "headline": "[产品名] — 让手工耳环更简单",
                "body": "还在为手工耳环烦恼吗？...",
                "cta": "立即体验 →",
                "content_type": "copywriting",
                "mode": "template_fallback",
            },
            "output": {
                "headline": "[产品名] — 让手工耳环更简单",
                "body": "还在为手工耳环烦恼吗？...",
                "cta": "立即体验 →",
                "content_type": "copywriting",
                "mode": "template_fallback",
            },
            "error": None,
            "meta": {
                "task_id": "mkt_87654321",
                "duration_ms": 0,
                "model": "",
                "tokens_used": 0,
                "fallback": True,
            },
        }

        from backend.services.agent_executor import _map_result
        result = _map_result("marketing", "mkt_87654321", marketing_fallback)

        assert result.ok is True
        assert result.summary == "未配置 AI API Key，使用模板占位内容。这不是真实 AI 生成的结果。"
        assert result.metadata.get("fallback") is True

    def test_marketing_error_result(self):
        """测试 Marketing Agent 错误结果"""
        marketing_error = {
            "task_id": "mkt_error",
            "ok": False,
            "success": False,
            "agent": "marketing_agent",
            "agent_name": "Marketing 营销内容",
            "status": "失败",
            "summary": "缺少营销内容需求描述",
            "result": "缺少营销内容需求描述",
            "data": {},
            "output": {},
            "error": "缺少营销内容需求描述",
            "meta": {
                "task_id": "mkt_error",
                "duration_ms": 0,
                "model": "",
                "tokens_used": 0,
                "fallback": False,
            },
        }

        from backend.services.agent_executor import _map_result
        result = _map_result("marketing", "mkt_error", marketing_error)

        assert result.ok is False
        assert result.error == "缺少营销内容需求描述"
        assert result.errors == ["缺少营销内容需求描述"]


class TestMarketingExecuteEndpointNewFields:
    """测试 /agents/marketing/execute 返回新字段"""

    def test_execute_returns_new_fields(self):
        """测试执行返回新字段"""
        from fastapi.testclient import TestClient
        from backend.app import app

        client = TestClient(app)
        resp = client.post("/agents/marketing/execute", json={
            "task_id": "",
            "goal": "帮我为手工耳环写小红书种草文案",
            "task_type": "social_media",
            "context": {"platform": "xiaohongshu"},
            "input": {"platform": "xiaohongshu", "goal": "帮我为手工耳环写小红书种草文案"},
        })

        assert resp.status_code == 200
        data = resp.json()

        # 验证新字段存在
        assert "ok" in data
        assert "mode" in data
        assert "agent_id" in data
        assert "task_type" in data
        assert "summary" in data
        assert "structured_output" in data
        assert "output" in data
        assert "artifacts" in data
        assert "warnings" in data
        assert "errors" in data
        assert "error" in data
        assert "next_actions" in data
        assert "risk_decision" in data
        assert "timeline_events" in data
        assert "metadata" in data

        # 验证字段类型
        assert isinstance(data["ok"], bool)
        assert isinstance(data["mode"], str)
        assert isinstance(data["agent_id"], str)
        assert isinstance(data["task_type"], str)
        assert isinstance(data["summary"], str)
        assert isinstance(data["structured_output"], dict)
        assert isinstance(data["output"], dict)
        assert isinstance(data["artifacts"], list)
        assert isinstance(data["warnings"], list)
        assert isinstance(data["errors"], list)
        assert isinstance(data["error"], (str, type(None)))
        assert isinstance(data["next_actions"], list)
        assert isinstance(data["timeline_events"], list)
        assert isinstance(data["metadata"], dict)

    def test_execute_structured_output_matches_output(self):
        """测试 structured_output 和 output 字段一致"""
        from fastapi.testclient import TestClient
        from backend.app import app

        client = TestClient(app)
        resp = client.post("/agents/marketing/execute", json={
            "task_id": "",
            "goal": "帮我为手工耳环写小红书种草文案",
            "task_type": "social_media",
            "context": {"platform": "xiaohongshu"},
            "input": {"platform": "xiaohongshu", "goal": "帮我为手工耳环写小红书种草文案"},
        })

        data = resp.json()
        # 对于 Marketing Agent，structured_output 和 output 应该相同
        assert data["structured_output"] == data["output"]


if __name__ == "__main__":
    pytest.main([__file__, "-v"])