"""Marketing Execute 测试 — /agents/marketing/execute 统一入口闭环"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest
from fastapi.testclient import TestClient

from backend.app import app

client = TestClient(app)


class TestMarketingExecuteEndpoint:
    """测试 /agents/marketing/execute 统一执行端点"""

    def test_execute_marketing_returns_agent_run_result(self):
        """正常调用 /agents/marketing/execute 应返回 AgentRunResult 结构"""
        resp = client.post("/agents/marketing/execute", json={
            "task_id": "",
            "goal": "帮我为手工耳环写小红书种草文案",
            "task_type": "social_media",
            "context": {"platform": "xiaohongshu"},
            "input": {"platform": "xiaohongshu", "goal": "帮我为手工耳环写小红书种草文案"},
        })
        assert resp.status_code == 200
        data = resp.json()
        # AgentRunResult 标准字段
        assert "ok" in data
        assert "agent_id" in data
        assert "output" in data
        assert "artifacts" in data
        assert isinstance(data["ok"], bool)
        assert isinstance(data["output"], dict)
        assert isinstance(data["artifacts"], list)

    def test_execute_marketing_ok_true_has_output(self):
        """调用成功时 ok=true 且 output 非空"""
        resp = client.post("/agents/marketing/execute", json={
            "task_id": "",
            "goal": "帮我为手工耳环写小红书种草文案",
            "task_type": "social_media",
            "context": {"platform": "xiaohongshu"},
            "input": {"platform": "xiaohongshu", "goal": "帮我为手工耳环写小红书种草文案"},
        })
        data = resp.json()
        # MarketingAgent 带 template fallback，应该能返回 ok=true
        assert data["ok"] is True
        assert len(data["output"]) > 0

    def test_execute_marketing_copywriting_task_type(self):
        """task_type=copywriting 也能正常执行（需明确目标避免 guard 拦截）"""
        resp = client.post("/agents/marketing/execute", json={
            "task_id": "",
            "goal": "帮我为手工银饰耳环写小红书种草文案",
            "task_type": "copywriting",
            "context": {"platform": "xiaohongshu"},
            "input": {"platform": "xiaohongshu"},
        })
        data = resp.json()
        assert data["ok"] is True

    def test_execute_marketing_disabled_agent(self):
        """禁用 marketing agent 后应返回 ok=false + 明确错误"""
        from backend.services.agent_discovery import set_agent_enabled
        set_agent_enabled("marketing", False)
        try:
            resp = client.post("/agents/marketing/execute", json={
                "task_id": "",
                "goal": "帮我为手工耳环写小红书种草文案",
                "task_type": "social_media",
                "context": {"platform": "xiaohongshu"},
                "input": {"platform": "xiaohongshu"},
            })
            data = resp.json()
            assert data["ok"] is False
            # governance guard 或 agent executor 返回的错误
            err = data.get("error") or data.get("message") or ""
            assert len(err) > 0, "应该有明确的错误信息"
        finally:
            set_agent_enabled("marketing", True)

    def test_execute_unknown_agent_returns_not_found(self):
        """调用不存在的 agent 应返回 ok=false + not found"""
        resp = client.post("/agents/nonexistent_agent_xyz/execute", json={
            "task_id": "",
            "goal": "帮我为手工耳环写小红书种草文案",
            "task_type": "social_media",
            "context": {"platform": "xiaohongshu"},
            "input": {"platform": "xiaohongshu"},
        })
        data = resp.json()
        assert data["ok"] is False
        err = data.get("error") or data.get("message") or ""
        assert "not found" in err.lower() or "not enabled" in err.lower()


class TestMarketingGovernanceFallback:
    """/governance/run 营销 fallback 仍然正常工作"""

    def test_governance_run_xiaohongshu_still_works(self):
        """/governance/run 对小红书目标仍然正常执行"""
        resp = client.post("/governance/run", json={
            "goal": "帮我为手工耳环生成小红书种草文案",
            "platform": "xiaohongshu",
            "execute": True,
        })
        data = resp.json()
        assert "run_id" in data
        assert "status" in data
        assert data["status"] == "succeeded"

    def test_governance_run_douyin_still_works(self):
        """/governance/run 对抖音目标仍然正常执行"""
        resp = client.post("/governance/run", json={
            "goal": "帮我为手工耳环生成抖音种草脚本",
            "platform": "douyin",
            "execute": True,
        })
        data = resp.json()
        assert "run_id" in data
        assert data["status"] == "succeeded"
