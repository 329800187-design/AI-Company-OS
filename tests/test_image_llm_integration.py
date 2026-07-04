"""Image Agent LLM 集成测试 — Phase A3: LLM-first 路径全覆盖"""
import json
import os
import sys
from unittest.mock import patch, MagicMock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest


# ── Helper ──────────────────────────────────────────────────────

def _make_agent():
    """构造 ImageAgent 实例 (不依赖外部配置)"""
    from agents.image_agent.agent import ImageAgent
    return ImageAgent(api_key="test-key")


def _good_llm_reply():
    """构造有效的 LLM JSON 回复"""
    return json.dumps({
        "image_prompt": "A beautiful handmade silver earring with delicate filigree work, "
                        "photorealistic style, soft natural lighting against a clean white background, "
                        "showcasing intricate craftsmanship and elegant design details",
        "negative_prompt": "blurry, low quality, distorted, watermark",
        "style": "photorealistic",
        "aspect_ratio": "1:1",
        "composition": "centered subject with shallow depth of field",
        "lighting": "soft natural window lighting",
        "color_palette": "silver and white with warm undertones",
        "subject": "handmade silver earring",
        "background": "clean white background",
        "usage_suggestions": ["product listing", "social media", "website banner"],
        "variations": ["close-up detail shot", "lifestyle model shot"],
        "limitations": [],
    }, ensure_ascii=False)


def _partial_llm_reply():
    """构造部分字段的 LLM 回复 (测试补齐)"""
    return json.dumps({
        "image_prompt": "A cute cartoon cat wearing a tiny hat",
        "style": "illustration",
    }, ensure_ascii=False)


def _invalid_json_reply():
    """构造无效 JSON 回复"""
    return "This is not JSON at all, just random text about image prompts."


def _call_ai_success(message, system="", temperature=0.7, max_tokens=4096):
    """模拟 call_ai 成功"""
    return {"ok": True, "reply": _good_llm_reply(), "model": "deepseek-chat"}


def _call_ai_success_partial(message, system="", temperature=0.7, max_tokens=4096):
    """模拟 call_ai 返回部分字段"""
    return {"ok": True, "reply": _partial_llm_reply(), "model": "deepseek-chat"}


def _call_ai_invalid_json(message, system="", temperature=0.7, max_tokens=4096):
    """模拟 call_ai 返回无效 JSON"""
    return {"ok": True, "reply": _invalid_json_reply(), "model": "deepseek-chat"}


def _call_ai_failure(message, system="", temperature=0.7, max_tokens=4096):
    """模拟 call_ai 失败"""
    return {"ok": False, "error": "API 连接超时"}


def _call_ai_exception(message, system="", temperature=0.7, max_tokens=4096):
    """模拟 call_ai 抛异常"""
    raise RuntimeError("Network error")


def _no_provider_agent():
    """构造无 API key 的 ImageAgent"""
    from agents.image_agent.agent import ImageAgent
    agent = ImageAgent(api_key="")
    return agent


# ── 测试用例 ────────────────────────────────────────────────────

class TestImageLLMIntegration:
    """Phase A3: Image Agent LLM-first 集成测试"""

    # 1. LLM 成功返回 image_prompt
    def test_llm_success_returns_image_prompt(self):
        """LLM 成功时 structured_output 包含 image_prompt"""
        agent = _make_agent()
        with patch.object(agent, "call_ai", side_effect=_call_ai_success):
            result = agent.run({
                "task_id": "img_test_001",
                "task_type": "image_generate",
                "prompt": "手工银饰耳环",
            })
        assert result["ok"] is True
        assert "image_prompt" in result["data"]
        assert len(result["data"]["image_prompt"]) > 10

    # 2. LLM 成功 metadata.source === "llm"
    def test_llm_success_metadata_source(self):
        """LLM 成功时 metadata.source 为 'llm'"""
        agent = _make_agent()
        with patch.object(agent, "call_ai", side_effect=_call_ai_success):
            result = agent.run({
                "task_id": "img_test_002",
                "task_type": "image_generate",
                "prompt": "手工银饰耳环",
            })
        assert result["meta"]["source"] == "llm"
        assert result["meta"]["fallback"] is False

    # 3. fallback metadata.source === "template"
    def test_fallback_metadata_source(self):
        """LLM 失败时 metadata.source 为 'template'"""
        agent = _make_agent()
        with patch.object(agent, "call_ai", side_effect=_call_ai_failure):
            result = agent.run({
                "task_id": "img_test_003",
                "task_type": "image_generate",
                "prompt": "手工银饰耳环",
            })
        assert result["meta"]["source"] == "template"
        assert result["meta"]["fallback"] is True

    # 4. fallback_reason 不混入 source
    def test_fallback_reason_not_in_source(self):
        """fallback_reason 是独立字段，不混入 source"""
        agent = _make_agent()
        with patch.object(agent, "call_ai", side_effect=_call_ai_failure):
            result = agent.run({
                "task_id": "img_test_004",
                "task_type": "image_generate",
                "prompt": "手工银饰耳环",
            })
        meta = result["meta"]
        assert "fallback_reason" in meta
        assert meta["source"] == "template"
        assert "fallback_reason" not in meta["source"]

    # 5. 无效 JSON fallback
    def test_invalid_json_fallback(self):
        """LLM 返回无效 JSON 时自动 fallback"""
        agent = _make_agent()
        with patch.object(agent, "call_ai", side_effect=_call_ai_invalid_json):
            result = agent.run({
                "task_id": "img_test_005",
                "task_type": "image_generate",
                "prompt": "手工银饰耳环",
            })
        assert result["ok"] is True
        assert result["meta"]["source"] == "template"
        assert result["meta"]["fallback"] is True

    # 6. call_ai 抛错 fallback
    def test_call_ai_exception_fallback(self):
        """call_ai 抛异常时 fallback"""
        agent = _make_agent()
        with patch.object(agent, "call_ai", side_effect=_call_ai_exception):
            result = agent.run({
                "task_id": "img_test_006",
                "task_type": "image_generate",
                "prompt": "手工银饰耳环",
            })
        assert result["ok"] is True
        assert result["meta"]["source"] == "template"
        assert result["meta"]["fallback"] is True

    # 7. 无 provider/key fallback
    def test_no_provider_fallback(self):
        """无 API key 时 call_ai 失败，自动 fallback"""
        agent = _no_provider_agent()
        with patch.object(agent, "call_ai", side_effect=_call_ai_failure):
            result = agent.run({
                "task_id": "img_test_007",
                "task_type": "image_generate",
                "prompt": "手工银饰耳环",
            })
        assert result["ok"] is True
        assert result["meta"]["source"] == "template"
        assert result["meta"]["fallback"] is True

    # 8. partial JSON 规范化补齐字段
    def test_partial_json_normalized(self):
        """LLM 返回部分字段时，自动补齐缺失字段"""
        agent = _make_agent()
        with patch.object(agent, "call_ai", side_effect=_call_ai_success_partial):
            result = agent.run({
                "task_id": "img_test_008",
                "task_type": "image_generate",
                "prompt": "卡通猫咪",
            })
        data = result["data"]
        # LLM 只给了 image_prompt 和 style
        assert data["image_prompt"] == "A cute cartoon cat wearing a tiny hat"
        assert data["style"] == "illustration"
        # 缺失字段被补齐
        assert "negative_prompt" in data
        assert "aspect_ratio" in data
        assert "composition" in data
        assert "lighting" in data
        assert "color_palette" in data
        assert "subject" in data
        assert "background" in data
        assert "usage_suggestions" in data
        assert "variations" in data
        assert "limitations" in data
        assert data["content_type"] == "image_prompt"

    # 9. fallback warnings 非空
    def test_fallback_warnings_nonempty(self):
        """fallback 时 warnings 非空，明确说明是模板降级"""
        agent = _make_agent()
        with patch.object(agent, "call_ai", side_effect=_call_ai_failure):
            result = agent.run({
                "task_id": "img_test_009",
                "task_type": "image_generate",
                "prompt": "手工银饰耳环",
            })
        warnings = result.get("warnings", [])
        assert len(warnings) > 0
        # 包含降级说明
        joined = " ".join(warnings).lower()
        assert "模板" in joined or "降级" in joined or "非真实" in joined or "template" in joined

    # 10. 明确不调用真实图片生成 API / 文件生成 / browser / openclaw
    def test_no_real_image_generation(self):
        """确保不调用 DALL-E / SD / Midjourney / 文件写入 / browser / openclaw"""
        agent = _make_agent()
        called_methods = []

        def track_call(message, system="", temperature=0.7, max_tokens=4096):
            called_methods.append("call_ai")
            return _call_ai_success(message, system, temperature, max_tokens)

        with patch.object(agent, "call_ai", side_effect=track_call):
            result = agent.run({
                "task_id": "img_test_010",
                "task_type": "image_generate",
                "prompt": "手工银饰耳环",
            })

        # 只调用了 call_ai，没有调用其他 API
        assert called_methods == ["call_ai"]

        # 验证没有真实图片生成相关字段
        data = result["data"]
        assert "url" not in data
        assert "local_path" not in data
        assert "image_path" not in data
        assert data.get("content_type") == "image_prompt"


class TestImageLLMMetadataStructure:
    """验证 AgentRunResult 元数据结构"""

    def test_llm_success_metadata_fields(self):
        """LLM 成功时 meta 包含必要字段"""
        agent = _make_agent()
        with patch.object(agent, "call_ai", side_effect=_call_ai_success):
            result = agent.run({
                "task_id": "img_meta_001",
                "task_type": "image_generate",
                "prompt": "test",
            })
        meta = result["meta"]
        assert meta["fallback"] is False
        assert meta["source"] == "llm"
        assert "model" in meta
        assert meta["task_id"] == "img_meta_001"

    def test_fallback_metadata_fields(self):
        """fallback 时 meta 包含必要字段"""
        agent = _make_agent()
        with patch.object(agent, "call_ai", side_effect=_call_ai_failure):
            result = agent.run({
                "task_id": "img_meta_002",
                "task_type": "image_generate",
                "prompt": "test",
            })
        meta = result["meta"]
        assert meta["fallback"] is True
        assert meta["source"] == "template"
        assert "fallback_reason" in meta
        assert meta["task_id"] == "img_meta_002"

    def test_llm_success_warnings_empty_or_no_fallback(self):
        """LLM 成功时 warnings 为空或不含 fallback 语义"""
        agent = _make_agent()
        with patch.object(agent, "call_ai", side_effect=_call_ai_success):
            result = agent.run({
                "task_id": "img_meta_003",
                "task_type": "image_generate",
                "prompt": "test",
            })
        warnings = result.get("warnings", [])
        if warnings:
            joined = " ".join(warnings).lower()
            assert "降级" not in joined
            assert "模板" not in joined

    def test_fallback_limitations_include_no_real_image(self):
        """fallback limitations 明确说明不生成真实图片"""
        agent = _make_agent()
        with patch.object(agent, "call_ai", side_effect=_call_ai_failure):
            result = agent.run({
                "task_id": "img_meta_004",
                "task_type": "image_generate",
                "prompt": "test",
            })
        limitations = result["data"].get("limitations", [])
        joined = " ".join(limitations).lower()
        assert "提示词" in joined or "prompt" in joined or "不生成" in joined or "真实图片" in joined


class TestImageAgentEdgeCases:
    """边界情况测试"""

    def test_no_prompt_returns_fail(self):
        """无 prompt 时返回 fail"""
        agent = _make_agent()
        result = agent.run({
            "task_id": "img_edge_001",
            "task_type": "image_generate",
            "prompt": "",
        })
        assert result["ok"] is False
        assert "prompt" in result["error"].lower() or "缺少" in result["error"]

    def test_no_task_type_defaults_to_generate(self):
        """无 task_type 时默认 image_generate"""
        agent = _make_agent()
        with patch.object(agent, "call_ai", side_effect=_call_ai_failure):
            result = agent.run({
                "task_id": "img_edge_002",
                "prompt": "手工耳环",
            })
        # 应该走 generate 路径，不是 analyze
        assert result["ok"] is True
        assert "image_prompt" in result["data"]

    def test_goal_fallback_to_prompt(self):
        """无 prompt 时从 goal 取值"""
        agent = _make_agent()
        with patch.object(agent, "call_ai", side_effect=_call_ai_failure):
            result = agent.run({
                "task_id": "img_edge_003",
                "task_type": "image_generate",
                "goal": "帮我生成耳环图片",
            })
        assert result["ok"] is True

    def test_structured_output_has_content_type(self):
        """structured_output 始终包含 content_type: image_prompt"""
        agent = _make_agent()
        with patch.object(agent, "call_ai", side_effect=_call_ai_failure):
            result = agent.run({
                "task_id": "img_edge_004",
                "task_type": "image_generate",
                "prompt": "test",
            })
        assert result["data"]["content_type"] == "image_prompt"

    def test_image_analyze_returns_fail(self):
        """image_analyze 在本阶段返回 fail"""
        agent = _make_agent()
        result = agent.run({
            "task_id": "img_edge_005",
            "task_type": "image_analyze",
            "prompt": "描述这张图片",
        })
        assert result["ok"] is False
