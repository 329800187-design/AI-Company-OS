"""Marketing Agent LLM 集成测试 — mock provider 覆盖真实 LLM / fallback 场景"""
import json
import os
import sys
from unittest.mock import patch, MagicMock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest
from agents.marketing_agent.agent import MarketingAgent


# ── Fixtures ──────────────────────────────────────────────

@pytest.fixture
def agent():
    return MarketingAgent()


def _llm_ok(reply_text: str):
    """构造 LLM 成功响应"""
    return {"ok": True, "reply": reply_text, "model": "mock-model"}


def _llm_error(msg: str = "mock error"):
    """构造 LLM 失败响应"""
    return {"ok": False, "error": msg}


# ── 1. LLM 成功路径 ─────────────────────────────────────

class TestLLMSuccess:
    """mock LLM 返回有效 JSON → 规范化 structured_output"""

    def test_copywriting_llm_success(self, agent):
        llm_json = json.dumps({
            "headline": "手工耳环，让你更美丽",
            "body": "这是一款精心设计的手工耳环...",
            "cta": "立即购买",
            "variations": ["变体A", "变体B"],
            "keywords": ["手工耳环", "饰品"],
            "tone": "warm",
        })
        with patch.object(agent, "call_ai", return_value=_llm_ok(llm_json)):
            result = agent.run({
                "task_id": "t1",
                "task_type": "copywriting",
                "goal": "帮我写手工耳环文案",
            })
        assert result["ok"] is True
        assert result["meta"]["fallback"] is False
        assert result["meta"]["source"] == "llm"
        data = result["data"]
        assert data["headline"] == "手工耳环，让你更美丽"
        assert data["body"] == "这是一款精心设计的手工耳环..."
        assert data["cta"] == "立即购买"
        assert data["content_type"] == "copywriting"

    def test_social_media_llm_success(self, agent):
        llm_json = json.dumps({
            "platform": "小红书",
            "content": "发现一款超美的手工耳环！",
            "hashtags": ["#手工", "#耳环"],
            "best_posting_time": "晚上8点",
        })
        with patch.object(agent, "call_ai", return_value=_llm_ok(llm_json)):
            result = agent.run({
                "task_id": "t2",
                "task_type": "social_media",
                "goal": "帮我写小红书种草文案",
            })
        assert result["ok"] is True
        assert result["meta"]["fallback"] is False
        data = result["data"]
        assert "手工" in data["content"]
        assert "#手工" in data["hashtags"]

    def test_llm_success_has_required_fields(self, agent):
        """LLM 成功时 structured_output 至少包含 headline/body/cta/hashtags/keywords"""
        llm_json = json.dumps({
            "headline": "测试标题",
            "body": "测试内容",
            "cta": "立即行动",
        })
        with patch.object(agent, "call_ai", return_value=_llm_ok(llm_json)):
            result = agent.run({
                "task_id": "t3",
                "task_type": "copywriting",
                "goal": "测试",
            })
        data = result["data"]
        assert "headline" in data
        assert "body" in data
        assert "cta" in data
        assert "hashtags" in data
        assert "keywords" in data

    def test_llm_json_in_markdown_block(self, agent):
        """LLM 返回 ```json ... ``` 包裹的 JSON"""
        inner = json.dumps({"headline": "测试", "body": "内容", "cta": "CTA"})
        llm_reply = f"```json\n{inner}\n```"
        with patch.object(agent, "call_ai", return_value=_llm_ok(llm_reply)):
            result = agent.run({
                "task_id": "t4",
                "task_type": "copywriting",
                "goal": "测试",
            })
        assert result["ok"] is True
        assert result["data"]["headline"] == "测试"

    def test_llm_json_embedded_in_text(self, agent):
        """LLM 返回混有非 JSON 文本的响应"""
        inner = json.dumps({"headline": "标题", "body": "内容", "cta": "CTA"})
        llm_reply = f"好的，这是你要的文案：\n{inner}\n希望对你有帮助。"
        with patch.object(agent, "call_ai", return_value=_llm_ok(llm_reply)):
            result = agent.run({
                "task_id": "t5",
                "task_type": "copywriting",
                "goal": "测试",
            })
        assert result["ok"] is True
        assert result["data"]["headline"] == "标题"


# ── 2. LLM 返回无效 JSON → fallback ──────────────────────

class TestLLMInvalidJSON:
    """mock LLM 返回无效 JSON → 模板 fallback"""

    def test_llm_returns_plain_text(self, agent):
        with patch.object(agent, "call_ai", return_value=_llm_ok("这不是JSON格式的内容")):
            result = agent.run({
                "task_id": "t6",
                "task_type": "copywriting",
                "goal": "帮我写文案",
            })
        # fallback
        assert result["ok"] is True
        assert result["meta"]["fallback"] is True
        assert result["meta"]["source"] == "template"
        assert "content_type" in result["data"]

    def test_llm_returns_empty_string(self, agent):
        with patch.object(agent, "call_ai", return_value=_llm_ok("")):
            result = agent.run({
                "task_id": "t7",
                "task_type": "copywriting",
                "goal": "帮我写文案",
            })
        assert result["ok"] is True
        assert result["meta"]["fallback"] is True

    def test_llm_returns_partial_json(self, agent):
        with patch.object(agent, "call_ai", return_value=_llm_ok('{"headline": "标题"')):
            result = agent.run({
                "task_id": "t8",
                "task_type": "copywriting",
                "goal": "帮我写文案",
            })
        assert result["ok"] is True
        assert result["meta"]["fallback"] is True


# ── 3. LLM 抛错后 fallback ──────────────────────────────

class TestLLMError:
    """mock LLM 调用抛错 → 模板 fallback"""

    def test_llm_returns_error_response(self, agent):
        with patch.object(agent, "call_ai", return_value=_llm_error("API limit exceeded")):
            result = agent.run({
                "task_id": "t9",
                "task_type": "copywriting",
                "goal": "帮我写文案",
            })
        assert result["ok"] is True
        assert result["meta"]["fallback"] is True
        assert result["meta"]["source"] == "template"

    def test_llm_call_raises_exception(self, agent):
        with patch.object(agent, "call_ai", side_effect=RuntimeError("network error")):
            result = agent.run({
                "task_id": "t10",
                "task_type": "copywriting",
                "goal": "帮我写文案",
            })
        assert result["ok"] is True
        assert result["meta"]["fallback"] is True

    def test_llm_timeout_fallback(self, agent):
        with patch.object(agent, "call_ai", side_effect=TimeoutError("LLM timeout")):
            result = agent.run({
                "task_id": "t11",
                "task_type": "social_media",
                "goal": "帮我写小红书文案",
            })
        assert result["ok"] is True
        assert result["meta"]["fallback"] is True
        assert result["data"]["content_type"] == "social_media"


# ── 4. 无 API key / provider fallback ──────────────────────

class TestNoProvider:
    """无 API key / provider 时 → 模板 fallback"""

    def test_no_api_key_fallback(self, agent):
        agent.api_key = ""
        with patch.object(agent, "call_ai", return_value=_llm_error("No provider available")):
            result = agent.run({
                "task_id": "t12",
                "task_type": "copywriting",
                "goal": "帮我写文案",
            })
        assert result["ok"] is True
        assert result["meta"]["fallback"] is True
        assert "template" in result["meta"]["source"]

    def test_fallback_has_warnings(self, agent):
        """fallback 时顶层 warnings 非空且包含降级语义"""
        with patch.object(agent, "call_ai", return_value=_llm_error("no provider")):
            result = agent.run({
                "task_id": "t13",
                "task_type": "copywriting",
                "goal": "帮我写文案",
            })
        meta = result["meta"]
        assert meta["fallback"] is True
        assert "fallback_reason" in meta
        # 顶层 warnings 必须非空
        warnings = result.get("warnings", [])
        assert len(warnings) > 0, "fallback 时 warnings 不应为空"
        # warnings 必须包含降级/模板/非真实 LLM 语义
        warnings_text = " ".join(warnings).lower()
        assert any(kw in warnings_text for kw in ["模板", "降级", "非真实", "llm", "placeholder"]), \
            f"warnings 应说明非真实 LLM 生成，实际: {warnings}"


# ── 5. 规范化补全 ──────────────────────────────────────────

class TestNormalize:
    """LLM 返回不完整字段时，规范化应补全"""

    def test_llm_missing_headline_falls_back(self, agent):
        """LLM 没返回 headline 但有 meta_title → 自动补全"""
        llm_json = json.dumps({
            "meta_title": "手工耳环指南",
            "h1": "手工耳环完全指南",
            "content": "正文内容...",
        })
        with patch.object(agent, "call_ai", return_value=_llm_ok(llm_json)):
            result = agent.run({
                "task_id": "t14",
                "task_type": "seo_article",
                "goal": "写SEO文章",
            })
        data = result["data"]
        assert data["headline"] == "手工耳环指南"
        assert data["body"] == "正文内容..."

    def test_llm_minimal_output_gets_defaults(self, agent):
        """LLM 只返回一个字段，其余用默认值补全"""
        llm_json = json.dumps({"brand_positioning": "为手工耳环领域提供创新"})
        with patch.object(agent, "call_ai", return_value=_llm_ok(llm_json)):
            result = agent.run({
                "task_id": "t15",
                "task_type": "brand_strategy",
                "goal": "品牌策略",
            })
        data = result["data"]
        assert "headline" in data
        assert "body" in data
        assert "cta" in data
        assert isinstance(data["hashtags"], list)
        assert isinstance(data["keywords"], list)


# ── 6. 输入校验 ──────────────────────────────────────────

class TestInputValidation:
    def test_empty_goal_returns_fail(self, agent):
        result = agent.run({"task_id": "t16", "task_type": "copywriting", "goal": ""})
        assert result["ok"] is False

    def test_no_goal_returns_fail(self, agent):
        result = agent.run({"task_id": "t17", "task_type": "copywriting"})
        assert result["ok"] is False

    def test_unknown_task_type_uses_copywriting_prompt(self, agent):
        """未知 task_type 应 fallback 到 copywriting prompt"""
        llm_json = json.dumps({"headline": "测试", "body": "内容", "cta": "CTA"})
        with patch.object(agent, "call_ai", return_value=_llm_ok(llm_json)) as mock:
            result = agent.run({
                "task_id": "t18",
                "task_type": "unknown_type",
                "goal": "测试",
            })
            # 验证 call_ai 被调用了（说明走了 LLM 路径）
            mock.assert_called_once()
        assert result["ok"] is True


# ── 7. 各 task_type fallback 模板 ──────────────────────────

class TestTemplateFallback:
    """每种 task_type 的 fallback 模板都应该生成有效内容"""

    @pytest.mark.parametrize("task_type", [
        "copywriting", "social_media", "seo_article",
        "email_campaign", "brand_strategy", "campaign_plan",
    ])
    def test_fallback_all_task_types(self, agent, task_type):
        with patch.object(agent, "call_ai", return_value=_llm_error("no provider")):
            result = agent.run({
                "task_id": f"t_fallback_{task_type}",
                "task_type": task_type,
                "goal": "帮我写关于手工耳环的内容",
            })
        assert result["ok"] is True
        assert result["meta"]["fallback"] is True
        assert result["data"]["content_type"] == task_type
        assert len(result["data"]) > 0, f"{task_type} fallback 模板不应为空"
        # fallback 必须有 warnings
        warnings = result.get("warnings", [])
        assert len(warnings) > 0, f"{task_type} fallback 时 warnings 不应为空"

    def test_llm_success_no_fallback_warnings(self, agent):
        """LLM 成功时不应有 fallback warnings"""
        llm_json = json.dumps({"headline": "测试", "body": "内容", "cta": "CTA"})
        with patch.object(agent, "call_ai", return_value=_llm_ok(llm_json)):
            result = agent.run({
                "task_id": "t_no_warn",
                "task_type": "copywriting",
                "goal": "测试",
            })
        assert result["ok"] is True
        assert result["meta"]["fallback"] is False
        warnings = result.get("warnings", [])
        assert len(warnings) == 0, "LLM 成功时不应有 warnings"


# ── 8. metadata.source/fallback_reason 专项验收 ─────────────

class TestMetadataFieldSpec:
    """metadata.source / fallback_reason 专项验收"""

    def test_marketing_llm_success_metadata_source_is_llm(self, agent):
        """LLM 成功时 metadata.source === "llm" """
        llm_json = json.dumps({
            "headline": "手工耳环，让你更美丽",
            "body": "精心设计...",
            "cta": "立即购买",
        })
        with patch.object(agent, "call_ai", return_value=_llm_ok(llm_json)):
            result = agent.run({
                "task_id": "t_meta_1",
                "task_type": "copywriting",
                "goal": "测试",
            })
        assert result["ok"] is True
        assert result["meta"]["fallback"] is False
        assert result["meta"]["source"] == "llm"
        # LLM 成功时 warnings 必须为空
        warnings = result.get("warnings", [])
        assert len(warnings) == 0

    def test_marketing_fallback_metadata_source_is_template(self, agent):
        """fallback 时 metadata.source === "template" """
        with patch.object(agent, "call_ai", return_value=_llm_error("no provider")):
            result = agent.run({
                "task_id": "t_meta_2",
                "task_type": "copywriting",
                "goal": "帮我写文案",
            })
        assert result["ok"] is True
        assert result["meta"]["fallback"] is True
        assert result["meta"]["source"] == "template"
        # fallback 时 warnings 必须非空
        warnings = result.get("warnings", [])
        assert len(warnings) > 0

    def test_marketing_fallback_reason_not_in_source(self, agent):
        """fallback_reason 独立存 meta.fallback_reason，不允许拼进 metadata.source"""
        with patch.object(agent, "call_ai", return_value=_llm_error("no provider")):
            result = agent.run({
                "task_id": "t_meta_3",
                "task_type": "copywriting",
                "goal": "测试",
            })
        meta = result["meta"]
        # source 必须是纯 "template"，不能含 fallback_reason 文本
        assert meta["source"] == "template"
        assert "fallback" not in meta["source"].replace("template", "").strip()
        # fallback_reason 必须独立存在
        assert "fallback_reason" in meta
        assert len(meta["fallback_reason"]) > 0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
