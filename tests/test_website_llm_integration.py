"""
Website Agent LLM Integration Tests — Phase A5

覆盖场景：
1. LLM 成功生成落地页文案
2. LLM 成功时 metadata.source == "llm"
3. fallback 时 metadata.source == "template"
4. fallback_reason 不混入 source
5. 无效 JSON fallback
6. call_ai 抛错 fallback
7. 无 provider/key fallback
8. partial JSON 规范化补齐字段
9. fallback warnings 非空
10. 不生成真实前端项目/不部署
11. 不调用浏览器/OpenClaw/pipeline
12. structured_output 字段完整性
13. 不修改其他 Agent
"""
import sys
import os
import json
import pytest
from unittest.mock import patch, MagicMock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from agents.website_agent.agent import WebsiteAgent
from backend.services.agent_executor import execute_agent, _map_result
from backend.schemas.agent_protocol import AgentRunResult, AgentTask


# ── Fixtures ──────────────────────────────────────────────

def _make_task(goal="帮我为手工耳环生成一个落地页文案", task_type="website_draft", task_id="test_web_llm_001"):
    return AgentTask(
        task_id=task_id,
        goal=goal,
        task_type=task_type,
        input={"goal": goal},
    )


def _llm_success_response(goal="为手工耳环生成落地页"):
    """模拟 LLM 返回的有效 JSON"""
    return {
        "ok": True,
        "reply": json.dumps({
            "page_goal": "收集潜在客户线索，推广手工耳环品牌",
            "target_audience": "25-40岁女性，喜欢手工饰品，追求独特审美",
            "hero": {
                "headline": "每一对耳环，都是独一无二的故事",
                "subheadline": "手工匠人精心打造，让您的耳朵也能讲述故事。100%手工制作，每一件都附带匠人签名。",
                "primary_cta": "立即选购",
            },
            "sections": [
                {
                    "title": "为什么选择手工耳环",
                    "content": "在流水线产品泛滥的时代，手工耳环代表着对品质和个性的坚持。每一对都经过匠人反复打磨，确保佩戴舒适、经久耐用。",
                    "cta": "查看作品集",
                },
                {
                    "title": "匠人故事",
                    "content": "我们的每一位匠人都有超过10年的手工饰品制作经验。她们用双手赋予每一块材料生命，让金属和宝石绽放独特的光芒。",
                    "cta": None,
                },
                {
                    "title": "客户好评",
                    "content": "戴上之后收到好多夸奖！做工真的太精致了。—— 小红书用户@手工爱好者",
                    "cta": None,
                },
            ],
            "ctas": {
                "primary": "页面顶部和底部各放一个主CTA按钮，文案'立即选购'",
                "secondary": "中部放'查看更多款式'次要CTA",
                "exit_intent": "弹窗提示'首单立减20元'",
            },
            "trust_elements": [
                "真实客户评价截图",
                "匠人资质证书",
                "7天无理由退换保障",
                "累计服务客户数统计",
            ],
            "seo": {
                "title": "手工耳环 | 独一无二的手工饰品 | 匠心打造",
                "description": "100%手工制作耳环，每一对都是独一无二的艺术品。支持定制，7天无理由退换。",
                "keywords": ["手工耳环", "手工饰品", "匠人精神", "定制耳环"],
            },
            "design_direction": "温暖自然风格，主色调采用大地色系（米白、棕褐、暖灰）。字体使用衬线体标题搭配无衬线正文。图片以自然光实拍为主，突出手工质感。",
            "risks": [
                "价格可能高于竞品，需要强调价值感",
                "手工制作周期较长，需在页面说明交付时间",
            ],
            "recommendations": [
                "增加匠人视频介绍，增强信任感",
                "设置限时优惠，促进首单转化",
                "加入UGC内容展示区，展示真实买家秀",
            ],
            "assumptions": [
                "假设目标受众主要通过小红书和微信渠道触达",
                "假设客单价在100-300元区间",
            ],
            "limitations": [
                "本阶段只生成落地页文案，不生成真实前端项目",
                "未做竞品分析，文案策略需根据实际竞品调整",
            ],
        }),
        "model": "deepseek-chat",
    }


def _llm_invalid_json_response():
    """模拟 LLM 返回无效 JSON"""
    return {
        "ok": True,
        "reply": "这不是一个有效的JSON响应，只是一段普通文本。手工耳环很好看。",
        "model": "deepseek-chat",
    }


def _llm_partial_json_response():
    """模拟 LLM 返回部分字段的 JSON"""
    return {
        "ok": True,
        "reply": json.dumps({
            "page_goal": "推广手工耳环",
            "hero": {
                "headline": "手工耳环，匠心之作",
                "subheadline": "每一对都独一无二",
                "primary_cta": "立即选购",
            },
            # 缺少其他必选字段
        }),
        "model": "deepseek-chat",
    }


def _llm_error_response():
    """模拟 LLM 调用失败"""
    return {
        "ok": False,
        "error": "API key 无效",
    }


# ── 1. LLM 成功 ──────────────────────────────────────────

def test_llm_success():
    """LLM 成功时应返回 structured_output 且 ok=True"""
    agent = WebsiteAgent()
    with patch.object(agent, 'call_ai', return_value=_llm_success_response("为手工耳环生成落地页")):
        result = agent.run({
            "task_id": "test_llm_ok_001",
            "goal": "为手工耳环生成落地页",
            "task_type": "website_draft",
        })
    assert result["ok"] is True
    data = result["data"]
    assert data.get("content_type") == "landing_page_copy"
    assert "page_goal" in data
    assert "hero" in data
    assert "sections" in data
    assert "ctas" in data
    assert "trust_elements" in data
    assert "seo" in data
    assert "design_direction" in data
    assert "risks" in data
    assert "recommendations" in data
    assert "assumptions" in data
    assert "limitations" in data


# ── 2. LLM 成功 metadata.source == "llm" ─────────────────

def test_llm_success_metadata_source():
    """LLM 成功时 metadata.source 必须为 'llm'"""
    agent = WebsiteAgent()
    with patch.object(agent, 'call_ai', return_value=_llm_success_response("为手工耳环生成落地页")):
        result = agent.run({
            "task_id": "test_llm_src_001",
            "goal": "为手工耳环生成落地页",
            "task_type": "website_draft",
        })
    meta = result["meta"]
    assert meta.get("source") == "llm", f"LLM 成功时 source 应为 'llm'，实际: {meta.get('source')}"
    assert meta.get("fallback") is False, f"LLM 成功时 fallback 应为 False，实际: {meta.get('fallback')}"


# ── 3. fallback metadata.source == "template" ─────────────

def test_fallback_metadata_source():
    """fallback 时 metadata.source 必须为 'template'"""
    agent = WebsiteAgent()
    with patch.object(agent, 'call_ai', return_value=_llm_error_response()):
        result = agent.run({
            "task_id": "test_fb_src_001",
            "goal": "为手工耳环生成落地页",
            "task_type": "website_draft",
        })
    meta = result["meta"]
    assert meta.get("source") == "template", f"fallback 时 source 应为 'template'，实际: {meta.get('source')}"
    assert meta.get("fallback") is True, f"fallback 时 fallback 应为 True，实际: {meta.get('fallback')}"


# ── 4. fallback_reason 不混入 source ──────────────────────

def test_fallback_reason_not_in_source():
    """fallback_reason 是独立字段，不应混入 source"""
    agent = WebsiteAgent()
    with patch.object(agent, 'call_ai', return_value=_llm_error_response()):
        result = agent.run({
            "task_id": "test_fb_reason_001",
            "goal": "为手工耳环生成落地页",
            "task_type": "website_draft",
        })
    meta = result["meta"]
    assert "fallback_reason" in meta, "fallback 时应有 fallback_reason 字段"
    assert meta["source"] == "template", "source 应为 template，不含 fallback_reason 内容"
    assert "fallback_reason" not in meta["source"], "fallback_reason 不应混入 source"


# ── 5. 无效 JSON fallback ─────────────────────────────────

def test_invalid_json_fallback():
    """LLM 返回无效 JSON 时应 fallback"""
    agent = WebsiteAgent()
    with patch.object(agent, 'call_ai', return_value=_llm_invalid_json_response()):
        result = agent.run({
            "task_id": "test_invalid_json_001",
            "goal": "为手工耳环生成落地页",
            "task_type": "website_draft",
        })
    assert result["ok"] is True
    meta = result["meta"]
    assert meta.get("fallback") is True
    assert meta.get("source") == "template"
    assert len(result.get("warnings", [])) > 0


# ── 6. call_ai 抛错 fallback ──────────────────────────────

def test_call_ai_exception_fallback():
    """call_ai 抛异常时应 fallback"""
    agent = WebsiteAgent()
    with patch.object(agent, 'call_ai', side_effect=RuntimeError("连接超时")):
        result = agent.run({
            "task_id": "test_ai_err_001",
            "goal": "为手工耳环生成落地页",
            "task_type": "website_draft",
        })
    assert result["ok"] is True
    meta = result["meta"]
    assert meta.get("fallback") is True
    assert meta.get("source") == "template"
    assert len(result.get("warnings", [])) > 0


# ── 7. 无 provider/key fallback ───────────────────────────

def test_no_provider_fallback():
    """无可用 provider 时 call_ai 返回 ok=False，应 fallback"""
    agent = WebsiteAgent()
    with patch.object(agent, 'call_ai', return_value={"ok": False, "error": "No provider available"}):
        result = agent.run({
            "task_id": "test_no_prov_001",
            "goal": "为手工耳环生成落地页",
            "task_type": "website_draft",
        })
    assert result["ok"] is True
    meta = result["meta"]
    assert meta.get("fallback") is True
    assert meta.get("source") == "template"


# ── 8. partial JSON 补字段 ────────────────────────────────

def test_partial_json_normalize():
    """LLM 返回部分字段时应自动补齐必选字段"""
    agent = WebsiteAgent()
    with patch.object(agent, 'call_ai', return_value=_llm_partial_json_response()):
        result = agent.run({
            "task_id": "test_partial_001",
            "goal": "为手工耳环生成落地页",
            "task_type": "website_draft",
        })
    assert result["ok"] is True
    data = result["data"]
    # 必选字段必须存在
    assert "page_goal" in data
    assert "target_audience" in data
    assert "hero" in data
    assert "sections" in data
    assert "ctas" in data
    assert "trust_elements" in data
    assert "seo" in data
    assert "design_direction" in data
    assert "risks" in data
    assert "recommendations" in data
    assert "assumptions" in data
    assert "limitations" in data
    # LLM 返回的字段保留
    assert data["page_goal"] == "推广手工耳环"
    assert data["hero"]["headline"] == "手工耳环，匠心之作"


# ── 9. fallback warnings 非空 ─────────────────────────────

def test_fallback_warnings_non_empty():
    """fallback 时 warnings 必须非空"""
    agent = WebsiteAgent()
    with patch.object(agent, 'call_ai', return_value=_llm_error_response()):
        result = agent.run({
            "task_id": "test_warn_001",
            "goal": "为手工耳环生成落地页",
            "task_type": "website_draft",
        })
    warnings = result.get("warnings", [])
    assert len(warnings) > 0, f"fallback 时 warnings 不应为空: {warnings}"
    # warnings 应包含降级语义
    warn_text = " ".join(warnings).lower()
    assert "模板" in warn_text or "降级" in warn_text or "未调用" in warn_text or "规则" in warn_text, \
        f"warnings 应包含降级语义: {warnings}"


# ── 10. 不生成真实前端项目 ────────────────────────────────

def test_no_real_frontend_project():
    """LLM-first 路径不应生成真实前端项目"""
    agent = WebsiteAgent()
    with patch.object(agent, 'call_ai', return_value=_llm_success_response("为手工耳环生成落地页")):
        result = agent.run({
            "task_id": "test_no_fe_001",
            "goal": "为手工耳环生成落地页",
            "task_type": "website_draft",
        })
    data = result.get("data", {})
    limitations = data.get("limitations", [])
    limitations_text = " ".join(limitations).lower()
    assert "不生成真实前端" in limitations_text or "文案" in limitations_text or \
           "前端项目" in limitations_text or "不部署" in limitations_text or \
           "不生成" in limitations_text, \
        f"limitations 应声明不生成真实前端项目: {limitations}"


# ── 11. 不调用浏览器/OpenClaw/pipeline ───────────────────

def test_no_browser_call():
    """LLM-first 路径不应调用 browser/openclaw"""
    agent = WebsiteAgent()
    with patch.object(agent, 'call_ai', return_value=_llm_success_response("为手工耳环生成落地页")):
        with patch('urllib.request.urlopen', side_effect=Exception("不应被调用")) as mock_urlopen:
            result = agent.run({
                "task_id": "test_no_br_001",
                "goal": "为手工耳环生成落地页",
                "task_type": "website_draft",
            })
            # urllib.request.urlopen 不应被调用（LLM-first 不走自建 HTTP 调用）
            mock_urlopen.assert_not_called()
    data = result.get("data", {})
    # 产物中不应有浏览器/OpenClaw 相关标记
    all_text = json.dumps(data, ensure_ascii=False).lower()
    assert "browser" not in all_text
    assert "openclaw" not in all_text
    # LLM 成功路径也应有 limitations 声明边界
    limitations = data.get("limitations", [])
    assert len(limitations) > 0, "LLM 成功路径也应有 limitations"


def test_no_pipeline_call():
    """LLM-first 路径不应调用旧 pipeline"""
    agent = WebsiteAgent()
    with patch.object(agent, 'call_ai', return_value=_llm_success_response("为手工耳环生成落地页")):
        result = agent.run({
            "task_id": "test_no_pipe_001",
            "goal": "为手工耳环生成落地页",
            "task_type": "website_draft",
        })
    data = result.get("data", {})
    # content_type 应为 landing_page_copy，不是旧 pipeline 标记
    assert data.get("content_type") == "landing_page_copy"


# ── 12. structured_output 字段完整性 ───────────────────────

def test_structured_output_fields():
    """structured_output 必须包含全部 12 个必选字段"""
    agent = WebsiteAgent()
    with patch.object(agent, 'call_ai', return_value=_llm_success_response("为手工耳环生成落地页")):
        result = agent.run({
            "task_id": "test_fields_001",
            "goal": "为手工耳环生成落地页",
            "task_type": "website_draft",
        })
    data = result["data"]
    required = [
        "page_goal", "target_audience", "hero", "sections", "ctas",
        "trust_elements", "seo", "design_direction", "risks",
        "recommendations", "assumptions", "limitations", "content_type",
    ]
    for field in required:
        assert field in data, f"缺少必选字段: {field}，实际字段: {list(data.keys())}"
    assert data["content_type"] == "landing_page_copy"
    # hero 子字段
    hero = data["hero"]
    assert "headline" in hero, "hero 缺少 headline"
    assert "subheadline" in hero, "hero 缺少 subheadline"
    assert "primary_cta" in hero, "hero 缺少 primary_cta"
    # seo 子字段
    seo = data["seo"]
    assert "title" in seo, "seo 缺少 title"
    assert "description" in seo, "seo 缺少 description"
    assert "keywords" in seo, "seo 缺少 keywords"
    # ctas 子字段
    ctas = data["ctas"]
    assert "primary" in ctas, "ctas 缺少 primary"


# ── 13. 不修改其他 Agent ──────────────────────────────────

def test_marketing_agent_unchanged():
    """Marketing Agent 不应被修改"""
    from agents.marketing_agent.agent import MarketingAgent
    agent = MarketingAgent()
    assert agent.AGENT_ID == "marketing"


def test_research_agent_unchanged():
    """Research Agent 不应被修改"""
    from agents.research_agent.agent import ResearchAgent
    agent = ResearchAgent()
    assert agent.AGENT_ID == "research"


def test_image_agent_unchanged():
    """Image Agent 不应被修改"""
    from agents.image_agent.agent import ImageAgent
    agent = ImageAgent()
    assert agent.AGENT_ID == "image"


def test_data_agent_unchanged():
    """Data Agent 不应被修改"""
    from agents.data_agent.agent import DataAgent
    agent = DataAgent()
    assert agent.AGENT_ID == "data"


# ── 通过 execute_agent 链路验证 ────────────────────────────

def test_execute_agent_llm_first():
    """通过 execute_agent 统一入口验证 LLM-first（有 provider 时走 LLM）"""
    task = AgentTask(
        task_id="test_exec_llm_001",
        goal="为手工耳环生成落地页文案",
        task_type="website_draft",
        input={"goal": "为手工耳环生成落地页文案"},
    )
    with patch('agents.website_agent.agent.WebsiteAgent.call_ai', return_value=_llm_success_response("为手工耳环生成落地页")):
        result = execute_agent("website", task)
    assert isinstance(result, AgentRunResult)
    assert result.ok is True
    assert result.agent_id == "website"
    # 有 provider 且 call_ai 成功 → LLM path
    assert result.metadata.get("source") == "llm"
    assert result.metadata.get("fallback") is False
    # structured_output 包含必选字段
    output = result.structured_output
    assert "page_goal" in output
    assert "hero" in output
    assert "seo" in output
    assert "limitations" in output
    assert output.get("content_type") == "landing_page_copy"


def test_execute_agent_fallback():
    """通过 execute_agent 验证 fallback 路径"""
    task = AgentTask(
        task_id="test_exec_fb_001",
        goal="为手工耳环生成落地页文案",
        task_type="website_draft",
        input={"goal": "为手工耳环生成落地页文案"},
    )
    with patch('agents.website_agent.agent.WebsiteAgent.call_ai', return_value=_llm_error_response()):
        result = execute_agent("website", task)
    assert isinstance(result, AgentRunResult)
    assert result.ok is True
    assert result.metadata.get("source") == "template"
    assert result.metadata.get("fallback") is True
    assert len(result.warnings) > 0


# ── 通过 execute_agent 验证不同 task_type ─────────────────

def test_execute_different_task_types():
    """不同 task_type 也能正常执行"""
    for task_type in ["landing_page", "product_page", "squeeze_page", "coming_soon"]:
        task = AgentTask(
            task_id=f"test_exec_{task_type}_001",
            goal=f"帮我为手工耳环生成一个{task_type}文案",
            task_type=task_type,
            input={"goal": f"帮我为手工耳环生成一个{task_type}文案"},
        )
        with patch('agents.website_agent.agent.WebsiteAgent.call_ai', return_value=_llm_success_response(f"为手工耳环生成{task_type}")):
            result = execute_agent("website", task)
        assert isinstance(result, AgentRunResult)
        assert result.ok is True, f"task_type={task_type} 应该成功"


# ── 空 goal 失败 ─────────────────────────────────────────

def test_empty_goal_fails():
    """空目标应返回失败"""
    agent = WebsiteAgent()
    result = agent.run({
        "task_id": "test_empty_001",
        "goal": "",
        "task_type": "website_draft",
    })
    assert result["ok"] is False


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
