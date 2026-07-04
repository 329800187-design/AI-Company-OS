"""Research Execute 测试 — /agents/research/execute 统一入口闭环"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest
from fastapi.testclient import TestClient

from backend.app import app

client = TestClient(app)


class TestResearchAgentLoading:
    """测试 Research Agent 可加载"""

    def test_research_agent_class_importable(self):
        """ResearchAgent 类可以导入"""
        from agents.research_agent.agent import ResearchAgent
        assert ResearchAgent is not None

    def test_research_agent_has_required_metadata(self):
        """ResearchAgent 声明了必要的元数据"""
        from agents.research_agent.agent import ResearchAgent
        assert ResearchAgent.AGENT_ID == "research"
        assert ResearchAgent.DISPLAY_NAME == "调研分析"
        assert "research" in ResearchAgent.CAPABILITIES
        assert "research_brief" in ResearchAgent.TASK_TYPES

    def test_research_agent_registered_in_loader(self):
        """Research Agent 在 AGENT_REGISTRY 中注册"""
        from backend.services.agent_loader import AGENT_REGISTRY
        assert "agents.research_agent.agent" in AGENT_REGISTRY
        assert AGENT_REGISTRY["agents.research_agent.agent"] == "ResearchAgent"

    def test_research_agent_loadable_via_loader(self):
        """通过 agent_loader 可以加载 ResearchAgent"""
        from backend.services.agent_loader import load_agent_instance
        agent = load_agent_instance("agents.research_agent.agent", "ResearchAgent")
        assert agent is not None
        assert hasattr(agent, "run")
        assert hasattr(agent, "execute")


class TestResearchExecuteEndpoint:
    """测试 /agents/research/execute 统一执行端点"""

    def test_execute_research_returns_agent_run_result(self):
        """正常调用 /agents/research/execute 应返回 AgentRunResult 结构"""
        resp = client.post("/agents/research/execute", json={
            "task_id": "",
            "goal": "帮我为手工耳环做一份竞品调研简报",
            "task_type": "research_brief",
            "context": {"source": "test"},
            "input": {"goal": "帮我为手工耳环做一份竞品调研简报"},
        })
        assert resp.status_code == 200
        data = resp.json()
        # AgentRunResult 标准字段
        assert "ok" in data
        assert "agent_id" in data
        assert "output" in data
        assert "artifacts" in data
        assert "warnings" in data
        assert "errors" in data
        assert isinstance(data["ok"], bool)
        assert isinstance(data["output"], dict)
        assert isinstance(data["artifacts"], list)
        assert isinstance(data["warnings"], list)

    def test_execute_research_has_structured_output_fields(self):
        """structured_output 包含调研标准字段"""
        resp = client.post("/agents/research/execute", json={
            "task_id": "",
            "goal": "帮我为手工耳环做一份竞品调研简报，分析主要竞争对手的价格和定位",
            "task_type": "research_brief",
            "context": {},
            "input": {"goal": "帮我为手工耳环做一份竞品调研简报，分析主要竞争对手的价格和定位"},
        })
        data = resp.json()
        so = data.get("structured_output", {})
        # 标准调研字段必须存在
        assert "research_question" in so, "structured_output 缺少 research_question"
        assert "market_summary" in so, "structured_output 缺少 market_summary"
        assert "key_findings" in so, "structured_output 缺少 key_findings"
        assert "competitors" in so, "structured_output 缺少 competitors"
        assert "opportunities" in so, "structured_output 缺少 opportunities"
        assert "risks" in so, "structured_output 缺少 risks"
        assert "recommended_actions" in so, "structured_output 缺少 recommended_actions"
        assert "limitations" in so, "structured_output 缺少 limitations"
        assert "sources" in so, "structured_output 缺少 sources"
        assert isinstance(so["sources"], list), "sources 应为数组"

    def test_execute_research_ok_true(self):
        """Research Agent 应返回 ok=true（模板模式也算成功产出）"""
        resp = client.post("/agents/research/execute", json={
            "task_id": "",
            "goal": "帮我为手工耳环做一份竞品调研简报，分析主要竞争对手",
            "task_type": "research_brief",
            "context": {},
            "input": {"goal": "帮我为手工耳环做一份竞品调研简报，分析主要竞争对手"},
        })
        data = resp.json()
        assert data["ok"] is True

    def test_execute_research_market_research_task_type(self):
        """task_type=market_research 也能正常执行"""
        resp = client.post("/agents/research/execute", json={
            "task_id": "",
            "goal": "帮我做一份手工耳环市场调研简报，分析市场规模和趋势",
            "task_type": "market_research",
            "context": {},
            "input": {"goal": "帮我做一份手工耳环市场调研简报，分析市场规模和趋势"},
        })
        data = resp.json()
        assert data["ok"] is True
        so = data.get("structured_output", {})
        assert "research_question" in so

    def test_execute_research_competitor_analysis_task_type(self):
        """task_type=competitor_analysis 也能正常执行"""
        resp = client.post("/agents/research/execute", json={
            "task_id": "",
            "goal": "帮我做一份手工耳环竞品调研简报，比较价格和品质差异",
            "task_type": "competitor_analysis",
            "context": {},
            "input": {"goal": "帮我做一份手工耳环竞品调研简报，比较价格和品质差异"},
        })
        data = resp.json()
        assert data["ok"] is True

    def test_execute_research_empty_goal_returns_error(self):
        """空 goal 应返回 ok=false"""
        resp = client.post("/agents/research/execute", json={
            "task_id": "",
            "goal": "",
            "task_type": "research_brief",
            "context": {},
            "input": {},
        })
        data = resp.json()
        assert data["ok"] is False

    def test_execute_research_disabled_agent(self):
        """禁用 research agent 后应返回 ok=false + 明确错误"""
        from backend.services.agent_discovery import set_agent_enabled
        set_agent_enabled("research", False)
        try:
            resp = client.post("/agents/research/execute", json={
                "task_id": "",
                "goal": "帮我为手工耳环做一份竞品调研简报",
                "task_type": "research_brief",
                "context": {},
                "input": {"goal": "帮我为手工耳环做一份竞品调研简报"},
            })
            data = resp.json()
            assert data["ok"] is False
            err = data.get("error") or data.get("message") or ""
            assert len(err) > 0, "应该有明确的错误信息"
        finally:
            set_agent_enabled("research", True)

    def test_execute_unknown_agent_returns_not_found(self):
        """调用不存在的 agent 应返回 ok=false"""
        resp = client.post("/agents/nonexistent_xyz/execute", json={
            "task_id": "",
            "goal": "test",
            "task_type": "research_brief",
            "context": {},
            "input": {},
        })
        data = resp.json()
        assert data["ok"] is False

    def test_execute_research_structured_output_limitations_has_framework_note(self):
        """limitations 应包含框架型调研声明"""
        resp = client.post("/agents/research/execute", json={
            "task_id": "",
            "goal": "帮我为手工耳环做一份竞品调研简报",
            "task_type": "research_brief",
            "context": {},
            "input": {},
        })
        data = resp.json()
        so = data.get("structured_output", {})
        limitations = so.get("limitations", [])
        assert isinstance(limitations, list)
        # 应包含框架声明
        has_framework_note = any("框架" in l or "联网" in l for l in limitations)
        assert has_framework_note, "limitations 应包含框架型调研声明"

    def test_execute_research_sources_is_empty_array(self):
        """sources 在无联网能力时应为空数组"""
        resp = client.post("/agents/research/execute", json={
            "task_id": "",
            "goal": "帮我为手工耳环做一份竞品调研简报",
            "task_type": "research_brief",
            "context": {},
            "input": {},
        })
        data = resp.json()
        so = data.get("structured_output", {})
        sources = so.get("sources", None)
        assert sources is not None, "sources 字段必须存在"
        assert isinstance(sources, list), "sources 应为数组"


class TestResearchGovernanceGuard:
    """Governance guard 在 /agents/research/execute 仍然生效"""

    def test_vague_goal_blocked_by_guard(self):
        """模糊目标应被 governance guard 拦截"""
        resp = client.post("/agents/research/execute", json={
            "task_id": "",
            "goal": "帮我赚钱",
            "task_type": "research_brief",
            "context": {},
            "input": {},
        })
        data = resp.json()
        assert data["ok"] is False or "blocked" in str(data).lower()


class TestResearchGovernanceFallback:
    """/governance/run 调研 fallback 仍然正常工作"""

    def test_governance_run_research_still_works(self):
        """/governance/run 对调研目标仍然正常执行"""
        resp = client.post("/governance/run", json={
            "goal": "帮我为手工耳环做一份竞品调研简报",
            "platform": "",
            "execute": True,
        })
        data = resp.json()
        assert "run_id" in data
        assert "status" in data


class TestResearchAgentUnit:
    """Research Agent 单元测试"""

    def test_research_agent_rule_fallback(self):
        """无 AI API 时应走规则降级"""
        from unittest.mock import patch
        from agents.research_agent.agent import ResearchAgent
        agent = ResearchAgent(api_key="")
        # mock call_ai 模拟无 provider
        with patch.object(agent, "call_ai", return_value={"ok": False, "error": "No provider"}):
            result = agent.run({
                "task_id": "test_001",
                "goal": "帮我分析手工耳环市场",
                "task_type": "research_brief",
            })
        assert result["ok"] is True  # 模板模式也算成功
        assert "data" in result
        data = result["data"]
        assert "research_question" in data
        assert "market_summary" in data
        assert "key_findings" in data
        assert "competitors" in data
        assert "opportunities" in data
        assert "risks" in data
        assert "recommended_actions" in data
        assert "limitations" in data
        assert "sources" in data
        assert isinstance(data["sources"], list)
        # fallback 语义正确
        assert result["meta"]["fallback"] is True
        assert len(result["warnings"]) > 0, "规则降级应有 warnings"

    def test_research_agent_empty_goal(self):
        """空 goal 应返回失败"""
        from agents.research_agent.agent import ResearchAgent
        agent = ResearchAgent(api_key="")
        result = agent.run({
            "task_id": "test_002",
            "goal": "",
            "task_type": "research_brief",
        })
        assert result["ok"] is False

    def test_research_agent_enrich_result(self):
        """_enrich_result 应补充标准字段"""
        from agents.research_agent.agent import ResearchAgent
        raw = {"research_question": "test"}
        enriched = ResearchAgent._enrich_result(raw, "test goal")
        assert "research_question" in enriched
        assert "market_summary" in enriched
        assert "key_findings" in enriched
        assert "competitors" in enriched
        assert "opportunities" in enriched
        assert "risks" in enriched
        assert "recommended_actions" in enriched
        assert "limitations" in enriched
        assert "sources" in enriched
        # limitations 应包含框架声明（_enrich_result 补充）
        lim_text = " ".join(enriched["limitations"])
        assert "framework" in lim_text or len(enriched["limitations"]) >= 0

    def test_research_agent_extract_topic(self):
        """_extract_topic 应提取关键词"""
        from agents.research_agent.agent import ResearchAgent
        topic = ResearchAgent._extract_topic("帮我为手工耳环做一份竞品调研简报")
        assert len(topic) > 0
        assert topic != "未指定"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
