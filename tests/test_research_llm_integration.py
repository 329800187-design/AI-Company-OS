"""Research Agent LLM 集成测试 — mock provider 覆盖真实 LLM / fallback 场景"""
import json
import os
import sys
from unittest.mock import patch, MagicMock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest
from agents.research_agent.agent import ResearchAgent


# ── Fixtures ──────────────────────────────────────────────

@pytest.fixture
def agent():
    return ResearchAgent()


def _llm_ok(reply_text: str):
    return {"ok": True, "reply": reply_text, "model": "mock-model"}


def _llm_error(msg: str = "mock error"):
    return {"ok": False, "error": msg}


# ── 1. LLM 成功 ─────────────────────────────────────────

class TestLLMSuccess:
    """mock LLM 返回有效 JSON → 规范化 structured_output"""

    def test_research_brief_llm_success(self, agent):
        llm_json = json.dumps({
            "research_question": "手工耳环市场分析",
            "market_summary": "手工耳环市场正在增长...",
            "key_findings": ["发现1", "发现2"],
            "competitors": [{"name": "竞品A", "strength": "设计", "weakness": "价格", "positioning": "高端"}],
            "opportunities": ["定制化机会"],
            "risks": ["竞争加剧"],
            "recommended_actions": ["差异化定位"],
            "limitations": ["本简报为框架型调研，非联网实时数据"],
            "sources": [],
        })
        with patch.object(agent, "call_ai", return_value=_llm_ok(llm_json)):
            result = agent.run({
                "task_id": "r1",
                "task_type": "research_brief",
                "goal": "帮我做手工耳环市场调研",
            })
        assert result["ok"] is True
        assert result["meta"]["fallback"] is False
        assert result["meta"]["source"] == "llm"
        data = result["data"]
        assert data["research_question"] == "手工耳环市场分析"
        assert len(data["key_findings"]) == 2
        assert len(data["competitors"]) == 1
        assert data["content_type"] == "research_brief"

    def test_llm_success_has_all_required_fields(self, agent):
        """LLM 成功时 structured_output 至少包含 9 个必选字段"""
        llm_json = json.dumps({
            "research_question": "测试问题",
            "market_summary": "测试市场",
            "key_findings": ["发现"],
        })
        with patch.object(agent, "call_ai", return_value=_llm_ok(llm_json)):
            result = agent.run({
                "task_id": "r2",
                "task_type": "research_brief",
                "goal": "测试",
            })
        data = result["data"]
        for field in ["research_question", "market_summary", "key_findings",
                       "competitors", "opportunities", "risks",
                       "recommended_actions", "limitations", "sources"]:
            assert field in data, f"缺少必选字段: {field}"

    def test_llm_json_in_markdown_block(self, agent):
        inner = json.dumps({"research_question": "Q", "market_summary": "M", "key_findings": []})
        llm_reply = f"```json\n{inner}\n```"
        with patch.object(agent, "call_ai", return_value=_llm_ok(llm_reply)):
            result = agent.run({
                "task_id": "r3",
                "task_type": "research_brief",
                "goal": "测试",
            })
        assert result["ok"] is True
        assert result["data"]["research_question"] == "Q"

    def test_llm_json_embedded_in_text(self, agent):
        inner = json.dumps({"research_question": "嵌入测试", "market_summary": "市场", "key_findings": []})
        llm_reply = f"以下是调研结果：\n{inner}\n以上。"
        with patch.object(agent, "call_ai", return_value=_llm_ok(llm_reply)):
            result = agent.run({
                "task_id": "r4",
                "task_type": "market_research",
                "goal": "测试",
            })
        assert result["ok"] is True
        assert result["data"]["research_question"] == "嵌入测试"

    def test_llm_success_framework_note_in_limitations(self, agent):
        """LLM 成功时 limitations 应包含框架声明"""
        llm_json = json.dumps({
            "research_question": "Q",
            "market_summary": "M",
            "key_findings": [],
            "limitations": [],
        })
        with patch.object(agent, "call_ai", return_value=_llm_ok(llm_json)):
            result = agent.run({
                "task_id": "r5",
                "task_type": "research_brief",
                "goal": "测试",
            })
        limitations = result["data"]["limitations"]
        assert any("框架" in l or "联网" in l for l in limitations)


# ── 2. LLM 返回无效 JSON → fallback ──────────────────────

class TestLLMInvalidJSON:

    def test_llm_returns_plain_text(self, agent):
        with patch.object(agent, "call_ai", return_value=_llm_ok("这不是JSON格式")):
            result = agent.run({
                "task_id": "r6",
                "task_type": "research_brief",
                "goal": "调研",
            })
        assert result["ok"] is True
        assert result["meta"]["fallback"] is True
        assert result["meta"]["source"] == "template"

    def test_llm_returns_empty_string(self, agent):
        with patch.object(agent, "call_ai", return_value=_llm_ok("")):
            result = agent.run({
                "task_id": "r7",
                "task_type": "research_brief",
                "goal": "调研",
            })
        assert result["ok"] is True
        assert result["meta"]["fallback"] is True

    def test_llm_returns_partial_json(self, agent):
        with patch.object(agent, "call_ai", return_value=_llm_ok('{"research_question": "Q"')):
            result = agent.run({
                "task_id": "r8",
                "task_type": "research_brief",
                "goal": "调研",
            })
        assert result["ok"] is True
        assert result["meta"]["fallback"] is True


# ── 3. LLM 抛错后 fallback ──────────────────────────────

class TestLLMError:

    def test_llm_returns_error_response(self, agent):
        with patch.object(agent, "call_ai", return_value=_llm_error("API limit")):
            result = agent.run({
                "task_id": "r9",
                "task_type": "research_brief",
                "goal": "调研",
            })
        assert result["ok"] is True
        assert result["meta"]["fallback"] is True

    def test_llm_call_raises_exception(self, agent):
        with patch.object(agent, "call_ai", side_effect=RuntimeError("network")):
            result = agent.run({
                "task_id": "r10",
                "task_type": "research_brief",
                "goal": "调研",
            })
        assert result["ok"] is True
        assert result["meta"]["fallback"] is True

    def test_llm_timeout_fallback(self, agent):
        with patch.object(agent, "call_ai", side_effect=TimeoutError("timeout")):
            result = agent.run({
                "task_id": "r11",
                "task_type": "market_research",
                "goal": "调研",
            })
        assert result["ok"] is True
        assert result["meta"]["fallback"] is True
        assert result["data"]["content_type"] == "market_research"


# ── 4. 无 provider/key fallback ──────────────────────────

class TestNoProvider:

    def test_no_api_key_fallback(self, agent):
        agent.api_key = ""
        with patch.object(agent, "call_ai", return_value=_llm_error("No provider")):
            result = agent.run({
                "task_id": "r12",
                "task_type": "research_brief",
                "goal": "调研",
            })
        assert result["ok"] is True
        assert result["meta"]["fallback"] is True
        assert result["meta"]["source"] == "template"


# ── 5. fallback warnings ──────────────────────────────────

class TestFallbackWarnings:
    """fallback 时顶层 warnings 非空且包含降级/非实时语义"""

    def test_fallback_has_warnings(self, agent):
        with patch.object(agent, "call_ai", return_value=_llm_error("no provider")):
            result = agent.run({
                "task_id": "r13",
                "task_type": "research_brief",
                "goal": "调研手工耳环市场",
            })
        warnings = result.get("warnings", [])
        assert len(warnings) > 0, "fallback 时 warnings 不应为空"
        warnings_text = " ".join(warnings).lower()
        assert any(kw in warnings_text for kw in ["模板", "降级", "非真实", "llm", "非联网", "框架"]), \
            f"warnings 应说明非真实 LLM 生成，实际: {warnings}"

    def test_fallback_mentions_not_realtime(self, agent):
        """fallback warnings 必须说明非实时联网"""
        with patch.object(agent, "call_ai", return_value=_llm_error("no provider")):
            result = agent.run({
                "task_id": "r14",
                "task_type": "research_brief",
                "goal": "调研",
            })
        warnings_text = " ".join(result.get("warnings", [])).lower()
        assert "联网" in warnings_text or "实时" in warnings_text or "框架" in warnings_text, \
            f"warnings 应说明非实时联网，实际: {result.get('warnings', [])}"

    def test_llm_success_no_fallback_warnings(self, agent):
        """LLM 成功时不应有 fallback warnings"""
        llm_json = json.dumps({
            "research_question": "Q", "market_summary": "M", "key_findings": [],
        })
        with patch.object(agent, "call_ai", return_value=_llm_ok(llm_json)):
            result = agent.run({
                "task_id": "r15",
                "task_type": "research_brief",
                "goal": "测试",
            })
        assert result["ok"] is True
        assert result["meta"]["fallback"] is False
        warnings = result.get("warnings", [])
        assert len(warnings) == 0, "LLM 成功时不应有 warnings"

    @pytest.mark.parametrize("task_type", ["research_brief", "market_research", "competitor_analysis"])
    def test_fallback_all_task_types_have_warnings(self, agent, task_type):
        with patch.object(agent, "call_ai", return_value=_llm_error("no provider")):
            result = agent.run({
                "task_id": f"r_fb_{task_type}",
                "task_type": task_type,
                "goal": "调研手工耳环",
            })
        assert result["meta"]["fallback"] is True
        warnings = result.get("warnings", [])
        assert len(warnings) > 0, f"{task_type} fallback 时 warnings 不应为空"


# ── 6. 不调用 browser/http/openclaw ──────────────────────

class TestNoBrowserCalls:
    """确认不调用 browser / httpx / openclaw"""

    def test_no_urllib_request_call(self, agent):
        """Research Agent 不应直接调用 urllib.request"""
        import urllib.request
        with patch.object(urllib.request, "urlopen") as mock_urlopen, \
             patch.object(agent, "call_ai", return_value=_llm_ok(json.dumps({
                 "research_question": "Q", "market_summary": "M", "key_findings": [],
             }))):
            agent.run({
                "task_id": "r16",
                "task_type": "research_brief",
                "goal": "测试",
            })
        mock_urlopen.assert_not_called()

    def test_call_ai_used_not_custom_http(self, agent):
        """应通过 call_ai (BrainManager) 调用，不走自定义 HTTP"""
        with patch.object(agent, "call_ai", return_value=_llm_ok(json.dumps({
            "research_question": "Q", "market_summary": "M", "key_findings": [],
        }))) as mock_call:
            agent.run({
                "task_id": "r17",
                "task_type": "research_brief",
                "goal": "测试",
            })
        mock_call.assert_called_once()

    def test_no_openclaw_import(self):
        """Research Agent 模块不应导入 openclaw"""
        import importlib
        mod = importlib.import_module("agents.research_agent.agent")
        source = open(mod.__file__, encoding="utf-8").read()
        assert "openclaw" not in source.lower(), "Research Agent 不应引用 openclaw"


# ── 7. 输入校验 ──────────────────────────────────────────

class TestInputValidation:
    def test_empty_goal_returns_fail(self, agent):
        result = agent.run({"task_id": "r18", "task_type": "research_brief", "goal": ""})
        assert result["ok"] is False

    def test_no_goal_returns_fail(self, agent):
        result = agent.run({"task_id": "r19", "task_type": "research_brief"})
        assert result["ok"] is False

    def test_unknown_task_type_uses_research_brief_prompt(self, agent):
        llm_json = json.dumps({"research_question": "Q", "market_summary": "M", "key_findings": []})
        with patch.object(agent, "call_ai", return_value=_llm_ok(llm_json)) as mock:
            result = agent.run({
                "task_id": "r20",
                "task_type": "unknown_type",
                "goal": "测试",
            })
            mock.assert_called_once()
        assert result["ok"] is True


# ── 8. partial JSON 规范化 ────────────────────────────────

class TestPartialJSONNormalization:
    """LLM 返回不完整 JSON 时，规范化补全所有必选字段"""

    def test_minimal_json_gets_defaults(self, agent):
        llm_json = json.dumps({"research_question": "只有问题"})
        with patch.object(agent, "call_ai", return_value=_llm_ok(llm_json)):
            result = agent.run({
                "task_id": "r21",
                "task_type": "research_brief",
                "goal": "测试",
            })
        data = result["data"]
        assert data["research_question"] == "只有问题"
        assert isinstance(data["market_summary"], str)
        assert isinstance(data["key_findings"], list)
        assert isinstance(data["competitors"], list)
        assert isinstance(data["opportunities"], list)
        assert isinstance(data["risks"], list)
        assert isinstance(data["recommended_actions"], list)
        assert isinstance(data["limitations"], list)
        assert isinstance(data["sources"], list)

    def test_empty_json_gets_all_defaults(self, agent):
        llm_json = json.dumps({})
        with patch.object(agent, "call_ai", return_value=_llm_ok(llm_json)):
            result = agent.run({
                "task_id": "r22",
                "task_type": "market_research",
                "goal": "测试调研",
            })
        data = result["data"]
        assert data["research_question"] == "测试调研"
        assert len(data["limitations"]) > 0


# ── 9. metadata.source/fallback_reason 专项验收 ─────────────

class TestMetadataFieldSpec:
    """metadata.source / fallback_reason 专项验收"""

    def test_research_llm_success_metadata_source_is_llm(self, agent):
        """LLM 成功时 metadata.source === "llm" """
        llm_json = json.dumps({
            "research_question": "手工耳环市场分析",
            "market_summary": "市场增长中...",
            "key_findings": ["发现1"],
        })
        with patch.object(agent, "call_ai", return_value=_llm_ok(llm_json)):
            result = agent.run({
                "task_id": "r_meta_1",
                "task_type": "research_brief",
                "goal": "调研",
            })
        assert result["ok"] is True
        assert result["meta"]["fallback"] is False
        assert result["meta"]["source"] == "llm"
        # LLM 成功时 warnings 必须为空
        warnings = result.get("warnings", [])
        assert len(warnings) == 0

    def test_research_fallback_metadata_source_is_template(self, agent):
        """fallback 时 metadata.source === "template" """
        with patch.object(agent, "call_ai", return_value=_llm_error("no provider")):
            result = agent.run({
                "task_id": "r_meta_2",
                "task_type": "research_brief",
                "goal": "调研手工耳环",
            })
        assert result["ok"] is True
        assert result["meta"]["fallback"] is True
        assert result["meta"]["source"] == "template"
        # fallback 时 warnings 必须非空
        warnings = result.get("warnings", [])
        assert len(warnings) > 0

    def test_research_fallback_reason_not_in_source(self, agent):
        """fallback_reason 独立存 meta.fallback_reason，不允许拼进 metadata.source"""
        with patch.object(agent, "call_ai", return_value=_llm_error("no provider")):
            result = agent.run({
                "task_id": "r_meta_3",
                "task_type": "research_brief",
                "goal": "调研",
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
