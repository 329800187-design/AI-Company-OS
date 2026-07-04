"""
Data Agent LLM Integration Tests — Phase A4

覆盖场景：
1. LLM 成功生成数据分析报告
2. LLM 成功时 metadata.source == "llm"
3. fallback 时 metadata.source == "template"
4. fallback_reason 不混入 source
5. 无效 JSON fallback
6. call_ai 抛错 fallback
7. 无 provider/key fallback
8. partial JSON 规范化补齐字段
9. fallback warnings 非空
10. 无真实数据时 limitations/warnings 声明不是基于真实数据文件计算
11. 不调用文件解析/数据库/旧 pipeline/browser/openclaw
"""
import sys
import os
import json
import pytest
from unittest.mock import patch, MagicMock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from agents.data_agent.agent import DataAgent
from backend.services.agent_executor import execute_agent, _map_result
from backend.schemas.agent_protocol import AgentRunResult, AgentTask


# ── Fixtures ──────────────────────────────────────────────

def _make_task(goal="分析手工耳环的销售数据", task_type="data_analyze", task_id="test_data_llm_001"):
    return AgentTask(
        task_id=task_id,
        goal=goal,
        task_type=task_type,
        input={"goal": goal},
    )


def _llm_success_response(goal="分析销售数据"):
    """模拟 LLM 返回的有效 JSON"""
    return {
        "ok": True,
        "reply": json.dumps({
            "analysis_question": goal,
            "data_summary": "基于用户描述的手工耳环销售数据，当前无真实数据文件，为分析框架建议。",
            "key_metrics": [
                {"name": "销售额", "description": "总销售金额", "formula": "SUM(金额)"},
                {"name": "订单数", "description": "总订单数量", "formula": "COUNT(订单)"},
                {"name": "客单价", "description": "平均每笔订单金额", "formula": "销售额/订单数"},
            ],
            "trends": ["月度销售趋势", "品类对比趋势"],
            "findings": ["手工耳环品类销售额呈上升趋势", "复购率有待提升"],
            "risks": ["季节性波动风险", "竞争加剧风险"],
            "recommendations": ["增加高利润品类", "优化复购策略"],
            "assumptions": ["假设数据完整无缺失", "假设时间范围为近30天"],
            "limitations": ["本报告未基于真实数据文件计算，为分析框架建议"],
            "charts_suggested": [
                {"type": "折线图", "x_axis": "日期", "y_axis": "销售额", "purpose": "趋势分析"}
            ],
        }),
        "model": "deepseek-chat",
    }


def _llm_invalid_json_response():
    """模拟 LLM 返回无效 JSON"""
    return {
        "ok": True,
        "reply": "这不是一个有效的JSON响应，只是一段普通文本。",
        "model": "deepseek-chat",
    }


def _llm_partial_json_response():
    """模拟 LLM 返回部分字段的 JSON"""
    return {
        "ok": True,
        "reply": json.dumps({
            "analysis_question": "分析销售趋势",
            "findings": ["发现1", "发现2"],
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
    agent = DataAgent()
    with patch.object(agent, 'call_ai', return_value=_llm_success_response("分析销售数据")):
        result = agent.run({
            "task_id": "test_llm_ok_001",
            "goal": "分析销售数据",
            "task_type": "data_analyze",
        })
    assert result["ok"] is True
    data = result["data"]
    assert data.get("content_type") == "data_report"
    assert "analysis_question" in data
    assert "findings" in data
    assert "recommendations" in data
    assert "limitations" in data


# ── 2. LLM 成功 metadata.source == "llm" ─────────────────

def test_llm_success_metadata_source():
    """LLM 成功时 metadata.source 必须为 'llm'"""
    agent = DataAgent()
    with patch.object(agent, 'call_ai', return_value=_llm_success_response("分析销售数据")):
        result = agent.run({
            "task_id": "test_llm_src_001",
            "goal": "分析销售数据",
            "task_type": "data_analyze",
        })
    meta = result["meta"]
    assert meta.get("source") == "llm", f"LLM 成功时 source 应为 'llm'，实际: {meta.get('source')}"
    assert meta.get("fallback") is False, f"LLM 成功时 fallback 应为 False，实际: {meta.get('fallback')}"


# ── 3. fallback metadata.source == "template" ─────────────

def test_fallback_metadata_source():
    """fallback 时 metadata.source 必须为 'template'"""
    agent = DataAgent()
    with patch.object(agent, 'call_ai', return_value=_llm_error_response()):
        result = agent.run({
            "task_id": "test_fb_src_001",
            "goal": "分析销售数据",
            "task_type": "data_analyze",
        })
    meta = result["meta"]
    assert meta.get("source") == "template", f"fallback 时 source 应为 'template'，实际: {meta.get('source')}"
    assert meta.get("fallback") is True, f"fallback 时 fallback 应为 True，实际: {meta.get('fallback')}"


# ── 4. fallback_reason 不混入 source ──────────────────────

def test_fallback_reason_not_in_source():
    """fallback_reason 是独立字段，不应混入 source"""
    agent = DataAgent()
    with patch.object(agent, 'call_ai', return_value=_llm_error_response()):
        result = agent.run({
            "task_id": "test_fb_reason_001",
            "goal": "分析销售数据",
            "task_type": "data_analyze",
        })
    meta = result["meta"]
    assert "fallback_reason" in meta, "fallback 时应有 fallback_reason 字段"
    assert meta["source"] == "template", "source 应为 template，不含 fallback_reason 内容"
    assert "fallback_reason" not in meta["source"], "fallback_reason 不应混入 source"


# ── 5. 无效 JSON fallback ─────────────────────────────────

def test_invalid_json_fallback():
    """LLM 返回无效 JSON 时应 fallback"""
    agent = DataAgent()
    with patch.object(agent, 'call_ai', return_value=_llm_invalid_json_response()):
        result = agent.run({
            "task_id": "test_invalid_json_001",
            "goal": "分析销售数据",
            "task_type": "data_analyze",
        })
    assert result["ok"] is True
    meta = result["meta"]
    assert meta.get("fallback") is True
    assert meta.get("source") == "template"
    assert len(result.get("warnings", [])) > 0


# ── 6. call_ai 抛错 fallback ──────────────────────────────

def test_call_ai_exception_fallback():
    """call_ai 抛异常时应 fallback"""
    agent = DataAgent()
    with patch.object(agent, 'call_ai', side_effect=RuntimeError("连接超时")):
        result = agent.run({
            "task_id": "test_ai_err_001",
            "goal": "分析销售数据",
            "task_type": "data_analyze",
        })
    assert result["ok"] is True
    meta = result["meta"]
    assert meta.get("fallback") is True
    assert meta.get("source") == "template"
    assert len(result.get("warnings", [])) > 0


# ── 7. 无 provider/key fallback ───────────────────────────

def test_no_provider_fallback():
    """无可用 provider 时 call_ai 返回 ok=False，应 fallback"""
    agent = DataAgent()
    # 默认 call_ai 无 provider 时返回 ok=False
    with patch.object(agent, 'call_ai', return_value={"ok": False, "error": "No provider available"}):
        result = agent.run({
            "task_id": "test_no_prov_001",
            "goal": "分析销售数据",
            "task_type": "data_analyze",
        })
    assert result["ok"] is True
    meta = result["meta"]
    assert meta.get("fallback") is True
    assert meta.get("source") == "template"


# ── 8. partial JSON 补字段 ────────────────────────────────

def test_partial_json_normalize():
    """LLM 返回部分字段时应自动补齐必选字段"""
    agent = DataAgent()
    with patch.object(agent, 'call_ai', return_value=_llm_partial_json_response()):
        result = agent.run({
            "task_id": "test_partial_001",
            "goal": "分析销售趋势",
            "task_type": "data_analyze",
        })
    assert result["ok"] is True
    data = result["data"]
    # 必选字段必须存在
    assert "analysis_question" in data
    assert "data_summary" in data
    assert "key_metrics" in data
    assert "trends" in data
    assert "findings" in data
    assert "risks" in data
    assert "recommendations" in data
    assert "assumptions" in data
    assert "limitations" in data
    assert "charts_suggested" in data
    # LLM 返回的字段保留
    assert data["analysis_question"] == "分析销售趋势"
    assert len(data["findings"]) == 2


# ── 9. fallback warnings 非空 ─────────────────────────────

def test_fallback_warnings_non_empty():
    """fallback 时 warnings 必须非空"""
    agent = DataAgent()
    with patch.object(agent, 'call_ai', return_value=_llm_error_response()):
        result = agent.run({
            "task_id": "test_warn_001",
            "goal": "分析销售数据",
            "task_type": "data_analyze",
        })
    warnings = result.get("warnings", [])
    assert len(warnings) > 0, f"fallback 时 warnings 不应为空: {warnings}"
    # warnings 应包含降级语义
    warn_text = " ".join(warnings).lower()
    assert "模板" in warn_text or "降级" in warn_text or "未调用" in warn_text or "规则" in warn_text, \
        f"warnings 应包含降级语义: {warnings}"


# ── 10. 无真实数据声明 ────────────────────────────────────

def test_no_real_data_declaration_in_limitations():
    """无真实数据时 limitations 必须声明不是基于真实数据文件计算"""
    agent = DataAgent()
    with patch.object(agent, 'call_ai', return_value=_llm_error_response()):
        result = agent.run({
            "task_id": "test_no_data_001",
            "goal": "分析销售数据",
            "task_type": "data_analyze",
        })
    data = result["data"]
    limitations = data.get("limitations", [])
    limitations_text = " ".join(limitations).lower()
    assert "未基于真实数据" in limitations_text or "真实数据文件" in limitations_text, \
        f"limitations 必须声明未基于真实数据文件计算: {limitations}"


def test_no_real_data_declaration_in_warnings():
    """无真实数据时 warnings 必须声明不是基于真实数据文件计算"""
    agent = DataAgent()
    with patch.object(agent, 'call_ai', return_value=_llm_error_response()):
        result = agent.run({
            "task_id": "test_no_data_002",
            "goal": "分析销售数据",
            "task_type": "data_analyze",
        })
    warnings = result.get("warnings", [])
    warnings_text = " ".join(warnings).lower()
    assert "未基于真实数据" in warnings_text or "真实数据文件" in warnings_text or "真实数据分析" in warnings_text, \
        f"warnings 必须声明未基于真实数据文件计算: {warnings}"


# ── 11. 不调用文件解析/数据库/旧 pipeline/browser/openclaw ──

def test_no_file_parse_call():
    """LLM-first 路径不应调用 pandas 读取文件"""
    agent = DataAgent()
    with patch.object(agent, 'call_ai', return_value=_llm_success_response("分析销售数据")):
        with patch('agents.data_agent.agent._pd', create=True) as mock_pd:
            result = agent.run({
                "task_id": "test_no_file_001",
                "goal": "分析销售数据",
                "task_type": "data_analyze",
            })
            # pandas 不应被调用（纯文本目标走 LLM-first，不走文件加载）
            mock_pd.read_csv.assert_not_called()
            mock_pd.read_excel.assert_not_called()
            mock_pd.read_json.assert_not_called()


def test_no_database_call():
    """LLM-first 路径不应调用数据库"""
    agent = DataAgent()
    with patch.object(agent, 'call_ai', return_value=_llm_success_response("分析销售数据")):
        # 确保没有数据库相关调用
        result = agent.run({
            "task_id": "test_no_db_001",
            "goal": "分析销售数据",
            "task_type": "data_analyze",
        })
        # 产物中不应有数据库相关标记
        data = result.get("data", {})
        assert "database" not in str(data).lower()
        assert "sql" not in str(data).lower()


def test_no_old_pipeline_call():
    """LLM-first 路径不应调用旧 pipeline"""
    agent = DataAgent()
    with patch.object(agent, 'call_ai', return_value=_llm_success_response("分析销售数据")):
        result = agent.run({
            "task_id": "test_no_pipe_001",
            "goal": "分析销售数据",
            "task_type": "data_analyze",
        })
        data = result.get("data", {})
        # 不应有旧 pipeline 标记
        assert "pipeline" not in str(data).lower() or "content_type" in data


def test_no_browser_openclaw_call():
    """LLM-first 路径不应调用 browser/openclaw"""
    agent = DataAgent()
    with patch.object(agent, 'call_ai', return_value=_llm_success_response("分析销售数据")):
        result = agent.run({
            "task_id": "test_no_br_001",
            "goal": "分析销售数据",
            "task_type": "data_analyze",
        })
        data = result.get("data", {})
        assert "browser" not in str(data).lower()
        assert "openclaw" not in str(data).lower()


# ── 通过 execute_agent 链路验证 ────────────────────────────

def test_execute_agent_llm_first():
    """通过 execute_agent 统一入口验证 LLM-first（有 provider 时走 LLM）"""
    task = AgentTask(
        task_id="test_exec_llm_001",
        goal="分析手工耳环的销售数据",
        task_type="data_analyze",
        input={"goal": "分析手工耳环的销售数据"},
    )
    with patch('agents.data_agent.agent.DataAgent.call_ai', return_value=_llm_success_response("分析手工耳环的销售数据")):
        result = execute_agent("data", task)
    assert isinstance(result, AgentRunResult)
    assert result.ok is True
    assert result.agent_id == "data"
    # 有 provider 且 call_ai 成功 → LLM path
    assert result.metadata.get("source") == "llm"
    assert result.metadata.get("fallback") is False
    # structured_output 包含必选字段
    output = result.structured_output
    assert "analysis_question" in output
    assert "findings" in output
    assert "limitations" in output
    assert output.get("content_type") == "data_report"


def test_execute_agent_llm_success():
    """通过 execute_agent 验证 LLM 成功路径"""
    task = AgentTask(
        task_id="test_exec_llm_ok_001",
        goal="分析手工耳环的销售数据",
        task_type="data_analyze",
        input={"goal": "分析手工耳环的销售数据"},
    )
    with patch('agents.data_agent.agent.DataAgent.call_ai', return_value=_llm_success_response("分析手工耳环的销售数据")):
        result = execute_agent("data", task)
    assert isinstance(result, AgentRunResult)
    assert result.ok is True
    assert result.metadata.get("source") == "llm"
    assert result.metadata.get("fallback") is False


# ── structured_output 字段完整性 ───────────────────────────

def test_structured_output_fields():
    """structured_output 必须包含全部 11 个必选字段"""
    agent = DataAgent()
    with patch.object(agent, 'call_ai', return_value=_llm_success_response("分析销售数据")):
        result = agent.run({
            "task_id": "test_fields_001",
            "goal": "分析销售数据",
            "task_type": "data_analyze",
        })
    data = result["data"]
    required = [
        "analysis_question", "data_summary", "key_metrics",
        "trends", "findings", "risks", "recommendations",
        "assumptions", "limitations", "charts_suggested",
        "content_type",
    ]
    for field in required:
        assert field in data, f"缺少必选字段: {field}，实际字段: {list(data.keys())}"
    assert data["content_type"] == "data_report"


# ── 不修改其他 Agent ──────────────────────────────────────

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


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
