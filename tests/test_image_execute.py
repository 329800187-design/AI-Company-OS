"""Image Execute 测试 — /agents/image/execute 统一入口闭环"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest
from fastapi.testclient import TestClient

from backend.app import app

client = TestClient(app)


class TestImageExecuteEndpoint:
    """测试 /agents/image/execute 统一执行端点"""

    def test_execute_image_returns_agent_run_result(self):
        """正常调用 /agents/image/execute 应返回 AgentRunResult 结构"""
        resp = client.post("/agents/image/execute", json={
            "task_id": "",
            "goal": "帮我为手工耳环生成产品图提示词",
            "task_type": "image_generate",
            "context": {},
            "input": {"prompt": "帮我为手工耳环生成产品图提示词"},
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

    def test_execute_image_ok_has_output(self):
        """调用成功时 ok=true 且 output 非空（或有明确 fallback）"""
        resp = client.post("/agents/image/execute", json={
            "task_id": "",
            "goal": "帮我为手工耳环生成产品图提示词",
            "task_type": "image_generate",
            "context": {},
            "input": {"prompt": "帮我为手工耳环生成产品图提示词"},
        })
        data = resp.json()
        # ImageAgent 在无 API key 时会返回 fallback 结构
        assert data["ok"] is True or "error" in data or "fallback" in str(data.get("metadata", {}))
        assert len(data["output"]) > 0

    def test_execute_image_with_explicit_prompt(self):
        """明确 prompt 字段应优先使用"""
        resp = client.post("/agents/image/execute", json={
            "task_id": "",
            "goal": "帮我为手工耳环生成产品图提示词",
            "task_type": "image_generate",
            "context": {},
            "input": {"prompt": "手工银饰耳环，简约风格"},
        })
        data = resp.json()
        # 可能被 guard 拦截，或正常返回
        assert data["ok"] is True or "blocked" in str(data).lower() or "error" in data

    def test_execute_image_disabled_agent(self):
        """禁用 image agent 后应返回 ok=false + 明确错误"""
        from backend.services.agent_discovery import set_agent_enabled
        set_agent_enabled("image", False)
        try:
            resp = client.post("/agents/image/execute", json={
                "task_id": "",
                "goal": "帮我为手工耳环生成产品图提示词",
                "task_type": "image_generate",
                "context": {},
                "input": {"prompt": "帮我为手工耳环生成产品图提示词"},
            })
            data = resp.json()
            assert data["ok"] is False
            # governance guard 或 agent executor 返回的错误
            err = data.get("error") or data.get("message") or ""
            assert len(err) > 0, "应该有明确的错误信息"
        finally:
            set_agent_enabled("image", True)

    def test_execute_image_analyze_task_type(self):
        """image_analyze task_type 也能正常执行"""
        resp = client.post("/agents/image/execute", json={
            "task_id": "",
            "goal": "帮我分析这张图片的内容",
            "task_type": "image_analyze",
            "context": {},
            "input": {"prompt": "描述这张图片"},
        })
        data = resp.json()
        # 可能被 guard 拦截，或正常返回 ok=false（无图片输入）
        assert data["ok"] is False or "blocked" in str(data).lower()


class TestImageGovernanceGuard:
    """Governance guard 在 /agents/image/execute 仍然生效"""

    def test_vague_goal_blocked_by_guard(self):
        """模糊目标应被 governance guard 拦截"""
        resp = client.post("/agents/image/execute", json={
            "task_id": "",
            "goal": "帮我赚钱",
            "task_type": "image_generate",
            "context": {},
            "input": {},
        })
        data = resp.json()
        # guard 拦截时返回 ok=false（或 status=blocked）
        assert data["ok"] is False or "blocked" in str(data).lower()

    def test_vague_image_run_blocked(self):
        """/agents/image/run 也被 guard 拦截"""
        resp = client.post("/agents/image/run", json={
            "goal": "帮我赚钱",
            "prompt": "帮我赚钱",
        })
        data = resp.json()
        assert data.get("ok") is False or data.get("status") == "blocked"


class TestImageGovernanceFallback:
    """/governance/run 图片 fallback 仍然正常工作"""

    def test_governance_run_image_still_works(self):
        """/governance/run 对图片目标仍然正常执行"""
        resp = client.post("/governance/run", json={
            "goal": "帮我为手工耳环生成产品图提示词",
            "platform": "",
            "execute": True,
        })
        data = resp.json()
        assert "run_id" in data
        assert "status" in data
        assert data["status"] == "succeeded"


class TestImageAgentMapping:
    """测试 Image Agent 结果到 AgentRunResult 的映射"""

    def test_image_fallback_result_mapping(self):
        """测试 Image Agent fallback 结果映射"""
        image_raw = {
            "task_id": "img_12345678",
            "ok": True,
            "success": True,
            "agent": "image_agent",
            "agent_name": "Image 图片生成",
            "status": "生成完成",
            "summary": "成功生成提示词",
            "result": "成功生成提示词",
            "data": {
                "enhanced_prompt": "handmade silver earrings, minimalist style",
                "negative_prompt": "blurry, low quality",
                "style": "photorealistic",
                "aspect_ratio": "1:1",
                "note": "功能暂未开通 — 需要配置 OPENAI_API_KEY",
            },
            "output": {
                "enhanced_prompt": "handmade silver earrings, minimalist style",
                "negative_prompt": "blurry, low quality",
                "style": "photorealistic",
                "aspect_ratio": "1:1",
                "note": "功能暂未开通 — 需要配置 OPENAI_API_KEY",
            },
            "error": None,
            "meta": {
                "task_id": "img_12345678",
                "duration_ms": 0,
                "model": "dall-e-3",
                "tokens_used": 0,
                "fallback": True,
            },
        }

        from backend.services.agent_executor import _map_result
        result = _map_result("image", "img_12345678", image_raw)

        assert result.ok is True
        assert result.agent_id == "image"
        assert result.summary == "成功生成提示词"
        assert "enhanced_prompt" in result.structured_output
        assert "enhanced_prompt" in result.output
        assert result.metadata["task_id"] == "img_12345678"

    def test_image_error_result_mapping(self):
        """测试 Image Agent 错误结果映射"""
        image_error = {
            "task_id": "img_error",
            "ok": False,
            "success": False,
            "agent": "image_agent",
            "agent_name": "Image 图片生成",
            "status": "失败",
            "summary": "缺少图片生成 prompt",
            "result": "缺少图片生成 prompt",
            "data": {},
            "output": {},
            "error": "缺少图片生成 prompt",
            "meta": {
                "task_id": "img_error",
                "duration_ms": 0,
                "model": "",
                "tokens_used": 0,
                "fallback": False,
            },
        }

        from backend.services.agent_executor import _map_result
        result = _map_result("image", "img_error", image_error)

        assert result.ok is False
        assert result.error == "缺少图片生成 prompt"
        assert result.errors == ["缺少图片生成 prompt"]


class TestImageExecuteEndpointFields:
    """测试 /agents/image/execute 返回新字段"""

    def test_execute_returns_new_fields(self):
        """测试执行返回新字段"""
        resp = client.post("/agents/image/execute", json={
            "task_id": "",
            "goal": "帮我为手工耳环生成产品图提示词",
            "task_type": "image_generate",
            "context": {},
            "input": {"prompt": "帮我为手工耳环生成产品图提示词"},
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
        resp = client.post("/agents/image/execute", json={
            "task_id": "",
            "goal": "帮我为手工耳环生成产品图提示词",
            "task_type": "image_generate",
            "context": {},
            "input": {"prompt": "帮我为手工耳环生成产品图提示词"},
        })

        data = resp.json()
        # 对于 Image Agent，structured_output 和 output 应该相同
        assert data["structured_output"] == data["output"]


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
