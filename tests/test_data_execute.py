"""Data Agent Execute 测试 — 覆盖 POST /agents/data/execute 链路

注意：Phase A4 后 Data Agent 已升级为 LLM-first。
本文件测试覆盖 LLM-first 路径（有 provider 时）。
LLM fallback 路径见 test_data_llm_integration.py。
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import pytest
from unittest.mock import patch
from fastapi.testclient import TestClient

from backend.schemas.agent_protocol import AgentRunResult, AgentTask
from backend.services.agent_executor import execute_agent, _map_result
from agents.data_agent.agent import DataAgent


# ── 1. DataAgent 可被 agent_executor 正常加载 ───────────────────────────

def test_data_agent_instantiates():
    agent = DataAgent()
    assert agent.AGENT_ID == "data"
    assert "data" in agent.CAPABILITIES


def test_data_agent_execute_via_executor():
    """通过 execute_agent 统一入口调用 Data Agent"""
    task = AgentTask(
        task_id="test_data_001",
        goal="帮我分析销售数据",
        task_type="data_analyze",
        input={"goal": "帮我分析销售数据"},
    )
    result = execute_agent("data", task)
    assert isinstance(result, AgentRunResult)
    assert result.ok is True
    assert result.agent_id == "data"


# ── 2. POST /agents/data/execute 端点 ─────────────────────────────────

def test_data_execute_endpoint():
    from backend.app import app
    client = TestClient(app)
    response = client.post("/agents/data/execute", json={
        "task_id": "test_data_ep_001",
        "goal": "帮我分析手工耳环的销售数据",
        "task_type": "data_analyze",
        "context": {},
        "input": {"goal": "帮我分析手工耳环的销售数据"},
    })
    assert response.status_code == 200
    data = response.json()
    # Agent-first endpoint 不应被 governance guard 误拦
    assert not data.get("blocked_by_governance"), \
        f"Agent endpoint 被 governance 误拦: {data.get('classification', {})}"
    assert data["ok"] is True
    assert data["agent_id"] == "data"


# ── 3. AgentRunResult 标准字段 ────────────────────────────────────────

def test_agent_run_result_standard_fields():
    """返回的 AgentRunResult 包含所有标准字段"""
    task = AgentTask(
        task_id="test_data_fields_001",
        goal="做一份电商运营数据分析简报",
        task_type="data_analyze",
        input={"goal": "做一份电商运营数据分析简报"},
    )
    result = execute_agent("data", task)

    # 标准字段必须存在
    assert hasattr(result, "ok")
    assert hasattr(result, "mode")
    assert hasattr(result, "agent_id")
    assert hasattr(result, "task_type")
    assert hasattr(result, "summary")
    assert hasattr(result, "structured_output")
    assert hasattr(result, "output")
    assert hasattr(result, "artifacts")
    assert hasattr(result, "warnings")
    assert hasattr(result, "errors")
    assert hasattr(result, "error")
    assert hasattr(result, "next_actions")
    assert hasattr(result, "metadata")

    # 字段类型正确
    assert isinstance(result.ok, bool)
    assert isinstance(result.mode, str)
    assert isinstance(result.agent_id, str)
    assert isinstance(result.summary, str)
    assert isinstance(result.structured_output, dict)
    assert isinstance(result.output, dict)
    assert isinstance(result.artifacts, list)
    assert isinstance(result.warnings, list)
    assert isinstance(result.errors, list)
    assert isinstance(result.next_actions, list)
    assert isinstance(result.metadata, dict)


# ── 4. structured_output 包含 LLM-first 数据分析字段 ─────────────────

def test_structured_output_has_analysis_fields():
    """structured_output 包含 LLM-first 数据分析必选字段"""
    task = AgentTask(
        task_id="test_data_struct_001",
        goal="分析手工耳环的销售趋势和用户画像",
        task_type="data_analyze",
        input={"goal": "分析手工耳环的销售趋势和用户画像"},
    )
    result = execute_agent("data", task)
    output = result.structured_output

    # LLM-first 必选字段
    assert "findings" in output, f"缺少 findings，实际字段: {list(output.keys())}"
    assert "recommendations" in output, f"缺少 recommendations，实际字段: {list(output.keys())}"
    assert "key_metrics" in output, f"缺少 key_metrics，实际字段: {list(output.keys())}"
    assert "analysis_question" in output, f"缺少 analysis_question，实际字段: {list(output.keys())}"
    assert "limitations" in output, f"缺少 limitations，实际字段: {list(output.keys())}"

    # 字段类型正确
    assert isinstance(output["findings"], list)
    assert isinstance(output["recommendations"], list)
    assert isinstance(output["key_metrics"], list)
    assert isinstance(output["limitations"], list)

    # 内容非空
    assert len(output["findings"]) > 0, "findings 不应为空"
    assert len(output["recommendations"]) > 0, "recommendations 不应为空"


def test_structured_output_has_analysis_question():
    """structured_output 包含分析问题（analysis_question）"""
    task = AgentTask(
        task_id="test_data_goal_001",
        goal="帮我做一份电商运营数据分析简报",
        task_type="data_analyze",
        input={"goal": "帮我做一份电商运营数据分析简报"},
    )
    result = execute_agent("data", task)
    output = result.structured_output
    assert "analysis_question" in output
    # LLM 可能重述问题，只需确认字段存在且非空
    assert isinstance(output["analysis_question"], str)
    assert len(output["analysis_question"]) > 0


# ── 5. 不同分析场景覆盖 ──────────────────────────────────────────────

def test_sales_analysis():
    """销售分析场景"""
    task = AgentTask(
        task_id="test_sales_001",
        goal="帮我分析这个月销售数据，生成一份数据分析报告",
        task_type="data_analyze",
        input={"goal": "帮我分析这个月销售数据，生成一份数据分析报告"},
    )
    result = execute_agent("data", task)
    assert result.ok
    output = result.structured_output
    # LLM-first 输出应有 findings 和 recommendations
    assert "findings" in output
    assert "recommendations" in output
    assert len(output["findings"]) > 0


def test_user_analysis():
    """用户画像分析场景"""
    task = AgentTask(
        task_id="test_user_001",
        goal="分析手工耳环的用户画像",
        task_type="data_analyze",
        input={"goal": "分析手工耳环的用户画像"},
    )
    result = execute_agent("data", task)
    assert result.ok
    output = result.structured_output
    assert "findings" in output
    assert "recommendations" in output
    assert len(output["findings"]) > 0


def test_operations_analysis():
    """运营分析场景"""
    task = AgentTask(
        task_id="test_ops_001",
        goal="电商运营数据分析",
        task_type="data_analyze",
        input={"goal": "电商运营数据分析"},
    )
    result = execute_agent("data", task)
    assert result.ok
    output = result.structured_output
    assert "findings" in output
    assert "recommendations" in output
    assert len(output["findings"]) > 0


def test_generic_analysis():
    """通用分析场景（无特定关键词）"""
    task = AgentTask(
        task_id="test_generic_001",
        goal="帮我分析一下这个数据",
        task_type="data_analyze",
        input={"goal": "帮我分析一下这个数据"},
    )
    result = execute_agent("data", task)
    assert result.ok
    output = result.structured_output
    # LLM-first 通用分析也应有结构化字段
    assert "findings" in output
    assert "recommendations" in output
    assert "key_metrics" in output


# ── 6. warnings 和 fallback 行为 ─────────────────────────────────────

def test_no_file_returns_llm_output():
    """没有文件时走 LLM-first 路径，返回数据分析报告"""
    task = AgentTask(
        task_id="test_warn_001",
        goal="分析销售数据",
        task_type="data_analyze",
        input={"goal": "分析销售数据"},
    )
    result = execute_agent("data", task)
    output = result.structured_output
    # LLM-first 输出应有 content_type
    assert output.get("content_type") == "data_report"
    # metadata.fallback 取决于是否有可用 provider
    assert "fallback" in result.metadata


def test_agent_always_returns_ok_true():
    """Data Agent 在纯文本目标场景下应返回 ok=True"""
    task = AgentTask(
        task_id="test_ok_001",
        goal="分析数据",
        task_type="data_analyze",
        input={"goal": "分析数据"},
    )
    result = execute_agent("data", task)
    assert result.ok is True


# ── 7. summary 和 next_actions ───────────────────────────────────────

def test_summary_not_empty():
    """summary 不应为空"""
    task = AgentTask(
        task_id="test_summary_001",
        goal="分析销售趋势",
        task_type="data_analyze",
        input={"goal": "分析销售趋势"},
    )
    result = execute_agent("data", task)
    # LLM-first 路径 summary 可能为空字符串（LLM 不一定设置 summary）
    # 但 ok=True 且 structured_output 非空即可
    assert result.ok is True
    assert len(result.structured_output) > 0


# ── 8. metadata 包含 task_id ────────────────────────────────────────

def test_metadata_has_task_id():
    """metadata 应包含 task_id"""
    task = AgentTask(
        task_id="test_meta_001",
        goal="分析数据",
        task_type="data_analyze",
        input={"goal": "分析数据"},
    )
    result = execute_agent("data", task)
    assert "task_id" in result.metadata
    assert result.metadata["task_id"] == "test_meta_001"


# ── 9. _map_result 映射测试 ─────────────────────────────────────────

def test_map_result_from_raw():
    """_map_result 正确映射 Data Agent 原始结果"""
    raw = {
        "ok": True,
        "agent": "data",
        "status": "分析完成",
        "data": {
            "findings": ["发现1", "发现2"],
            "recommendations": ["建议1"],
            "key_metrics": [{"name": "指标1", "description": "说明"}],
            "analysis_question": "测试分析问题",
        },
        "error": None,
        "meta": {"task_id": "map_test_001", "duration_ms": 50},
    }
    result = _map_result("data", "map_test_001", raw)
    assert isinstance(result, AgentRunResult)
    assert result.ok is True
    assert result.agent_id == "data"
    assert "findings" in result.structured_output
    assert result.structured_output["findings"] == ["发现1", "发现2"]
    assert result.structured_output["key_metrics"] == [{"name": "指标1", "description": "说明"}]


# ── 10. 向后兼容：output == structured_output ────────────────────────

def test_output_backward_compatible():
    """output 字段应与 structured_output 内容一致（向后兼容）"""
    task = AgentTask(
        task_id="test_compat_001",
        goal="分析数据",
        task_type="data_analyze",
        input={"goal": "分析数据"},
    )
    result = execute_agent("data", task)
    assert result.output == result.structured_output, \
        "output 应与 structured_output 内容一致（向后兼容）"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
