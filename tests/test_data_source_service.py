"""Data Source Service 测试 — Phase 4.4

覆盖场景：
1. CSV 文件读取
2. JSON 文件读取（数组格式）
3. JSON 文件读取（嵌套格式 data/rows/items）
4. 内联数据读取（JSON 字符串）
5. 内联数据读取（CSV 字符串）
6. 内联数据读取（list[dict]）
7. detect_and_load 从 task 字典自动检测
8. detect_and_load 从 context/input 中提取
9. 无数据源时返回 ok=False
10. 文件不存在时返回 ok=False
11. Data Agent 有真实数据路径 vs 无数据路径对比
12. metadata.data_source_type 标记正确
"""
import sys, os, json, tempfile
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest
import pandas as pd
from unittest.mock import MagicMock, patch

from backend.services.data_source_service import (
    load_csv, load_json, load_inline, load_url,
    detect_and_load, DataSourceResult,
    URL_READ_TIMEOUT_SECONDS, MAX_REMOTE_BYTES,
)


# ── Fixtures ──────────────────────────────────────────────

@pytest.fixture
def tmp_csv(tmp_path):
    """创建临时 CSV 文件"""
    df = pd.DataFrame({
        "name": ["Alice", "Bob", "Charlie"],
        "age": [25, 30, 35],
        "city": ["Beijing", "Shanghai", "Guangzhou"],
    })
    path = tmp_path / "test_data.csv"
    df.to_csv(str(path), index=False, encoding="utf-8")
    return str(path)


@pytest.fixture
def tmp_json_array(tmp_path):
    """创建临时 JSON 数组文件"""
    data = [
        {"product": "耳环", "price": 99, "sales": 10},
        {"product": "项链", "price": 199, "sales": 5},
        {"product": "手链", "price": 149, "sales": 8},
    ]
    path = tmp_path / "test_data.json"
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False)
    return str(path)


@pytest.fixture
def tmp_json_nested(tmp_path):
    """创建临时嵌套 JSON 文件"""
    data = {
        "data": [
            {"product": "耳环", "price": 99, "sales": 10},
            {"product": "项链", "price": 199, "sales": 5},
        ],
        "total": 2,
    }
    path = tmp_path / "test_nested.json"
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False)
    return str(path)


# ── 1. CSV 文件读取 ──────────────────────────────────────

def test_load_csv_ok(tmp_csv):
    """CSV 读取成功"""
    result = load_csv(tmp_csv)
    assert result.ok is True
    assert result.source_type == "csv"
    assert result.row_count == 3
    assert result.col_count == 3
    assert "name" in result.columns
    assert "age" in result.columns
    assert result.file_name == "test_data.csv"
    assert result.df is not None
    assert len(result.df) == 3


def test_load_csv_not_found():
    """CSV 文件不存在"""
    result = load_csv("/nonexistent/file.csv")
    assert result.ok is False
    assert "不存在" in result.error


# ── 2. JSON 文件读取（数组格式）─────────────────────────────

def test_load_json_array(tmp_json_array):
    """JSON 数组读取成功"""
    result = load_json(tmp_json_array)
    assert result.ok is True
    assert result.source_type == "json"
    assert result.row_count == 3
    assert result.col_count == 3
    assert "product" in result.columns
    assert result.file_name == "test_data.json"


# ── 3. JSON 文件读取（嵌套格式）─────────────────────────────

def test_load_json_nested_data(tmp_json_nested):
    """JSON 嵌套格式（data 字段）读取成功"""
    result = load_json(tmp_json_nested)
    assert result.ok is True
    assert result.source_type == "json"
    assert result.row_count == 2
    assert "product" in result.columns


def test_load_json_nested_rows(tmp_path):
    """JSON 嵌套格式（rows 字段）读取成功"""
    data = {"rows": [{"x": 1}, {"x": 2}]}
    path = tmp_path / "rows.json"
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f)
    result = load_json(str(path))
    assert result.ok is True
    assert result.row_count == 2


def test_load_json_single_object(tmp_path):
    """JSON 单对象 → 单行 DataFrame"""
    data = {"name": "test", "value": 42}
    path = tmp_path / "single.json"
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f)
    result = load_json(str(path))
    assert result.ok is True
    assert result.row_count == 1


def test_load_json_not_found():
    """JSON 文件不存在"""
    result = load_json("/nonexistent/file.json")
    assert result.ok is False


# ── 4. 内联数据读取（JSON 字符串）─────────────────────────────

def test_load_inline_json_string():
    """JSON 字符串内联读取"""
    data = json.dumps([{"a": 1}, {"a": 2}])
    result = load_inline(data)
    assert result.ok is True
    assert result.source_type == "inline"
    assert result.row_count == 2
    assert result.file_name == "inline_data"


# ── 5. 内联数据读取（CSV 字符串）─────────────────────────────

def test_load_inline_csv_string():
    """CSV 字符串内联读取"""
    data = "name,age\nAlice,25\nBob,30"
    result = load_inline(data)
    assert result.ok is True
    assert result.source_type == "inline"
    assert result.row_count == 2
    assert "name" in result.columns


# ── 6. 内联数据读取（list[dict]）─────────────────────────────

def test_load_inline_list_dict():
    """list[dict] 内联读取"""
    data = [{"x": 1, "y": 2}, {"x": 3, "y": 4}]
    result = load_inline(data)
    assert result.ok is True
    assert result.source_type == "inline"
    assert result.row_count == 2
    assert "x" in result.columns


def test_load_inline_empty():
    """空内联数据"""
    result = load_inline("")
    assert result.ok is False


def test_load_inline_none():
    """None 内联数据"""
    result = load_inline(None)
    assert result.ok is False


# ── 7. detect_and_load 自动检测 ──────────────────────────────

def test_detect_csv_file(tmp_csv):
    """detect_and_load 检测 CSV 文件"""
    task = {"file_path": tmp_csv}
    result = detect_and_load(task)
    assert result.ok is True
    assert result.source_type == "csv"
    assert result.row_count == 3


def test_detect_json_file(tmp_json_array):
    """detect_and_load 检测 JSON 文件"""
    task = {"file_path": tmp_json_array}
    result = detect_and_load(task)
    assert result.ok is True
    assert result.source_type == "json"


def test_detect_inline_data():
    """detect_and_load 检测内联数据"""
    task = {"data": json.dumps([{"a": 1}])}
    result = detect_and_load(task)
    assert result.ok is True
    assert result.source_type == "inline"


def test_detect_rows_field():
    """detect_and_load 检测 rows 字段"""
    task = {"rows": [{"a": 1}, {"a": 2}]}
    result = detect_and_load(task)
    assert result.ok is True
    assert result.source_type == "inline"
    assert result.row_count == 2


# ── 8. detect_and_load 从 context/input 中提取 ─────────────

def test_detect_from_context(tmp_csv):
    """detect_and_load 从 context 中提取 file_path"""
    task = {"context": {"file_path": tmp_csv}, "input": {}}
    result = detect_and_load(task)
    assert result.ok is True
    assert result.source_type == "csv"


def test_detect_from_input():
    """detect_and_load 从 input 中提取 data"""
    task = {"context": {}, "input": {"data": [{"a": 1}]}}
    result = detect_and_load(task)
    assert result.ok is True
    assert result.source_type == "inline"


# ── 9. 无数据源 ──────────────────────────────────────────

def test_detect_no_source():
    """无数据源时返回 ok=False"""
    task = {"goal": "分析数据", "task_type": "data_analyze"}
    result = detect_and_load(task)
    assert result.ok is False
    assert result.source_type == "none"


# ── 10. 文件不存在 ──────────────────────────────────────────

def test_detect_file_not_found():
    """文件不存在时返回 ok=False"""
    task = {"file_path": "/nonexistent/data.csv"}
    result = detect_and_load(task)
    assert result.ok is False


def test_load_url_uses_timeout_and_reads_csv():
    """load_url should fetch remote CSV with timeout."""
    mock_resp = MagicMock()
    mock_resp.content = b"name,age\nAlice,25\nBob,30"
    mock_resp.encoding = "utf-8"
    mock_resp.headers = {"content-type": "text/csv"}
    mock_resp.raise_for_status = MagicMock()

    with patch("requests.get", return_value=mock_resp) as mock_get:
        result = load_url("https://example.com/data.csv")

    mock_get.assert_called_once_with("https://example.com/data.csv", timeout=URL_READ_TIMEOUT_SECONDS)
    assert result.ok is True
    assert result.source_type == "csv"
    assert result.row_count == 2
    assert result.columns == ["name", "age"]


def test_load_url_rejects_oversized_response():
    """load_url should reject remote payloads above the size cap."""
    mock_resp = MagicMock()
    mock_resp.content = b"x" * (MAX_REMOTE_BYTES + 1)
    mock_resp.encoding = "utf-8"
    mock_resp.headers = {"content-type": "text/csv"}
    mock_resp.raise_for_status = MagicMock()

    with patch("requests.get", return_value=mock_resp):
        result = load_url("https://example.com/large.csv")

    assert result.ok is False
    assert "大小限制" in result.error


# ── 11. Data Agent 有/无数据路径对比 ────────────────────────

def test_data_agent_with_real_data(tmp_csv):
    """Data Agent 有真实数据 → file_analysis 类型 + data_source_type=csv"""
    from agents.data_agent.agent import DataAgent
    agent = DataAgent()
    result = agent.run({
        "task_id": "test_real_001",
        "goal": "分析数据",
        "task_type": "data_analyze",
        "file_path": tmp_csv,
    })
    assert result["ok"] is True
    data = result["data"]
    # 真实数据路径 → file_analysis 类型
    assert data.get("type") == "file_analysis"
    # metadata 包含 data_source_type
    meta = result.get("meta", {})
    assert meta.get("data_source_type") == "csv"
    assert meta.get("sample_rows", 0) > 0


def test_data_agent_with_inline_data():
    """Data Agent 有内联数据 → file_analysis 类型 + data_source_type=inline"""
    from agents.data_agent.agent import DataAgent
    agent = DataAgent()
    rows = json.dumps([{"product": "A", "price": 10}, {"product": "B", "price": 20}])
    result = agent.run({
        "task_id": "test_inline_001",
        "goal": "分析数据",
        "task_type": "data_analyze",
        "data": rows,
    })
    assert result["ok"] is True
    data = result["data"]
    assert data.get("type") == "file_analysis"
    meta = result.get("meta", {})
    assert meta.get("data_source_type") == "inline"


def test_data_agent_with_missing_values_is_strict_json_safe():
    """Data Agent 输出应清洗 NaN/Inf，严格 JSON 序列化不报错"""
    from agents.data_agent.agent import DataAgent
    agent = DataAgent()
    result = agent.run({
        "task_id": "test_nan_safe_001",
        "goal": "分析含缺失值的数据",
        "task_type": "data_analyze",
        "data": "name,score,bonus\nA,10,\nB,20,5\nC,,7\n",
    })
    assert result["ok"] is True
    assert result.get("meta", {}).get("data_source_type") == "inline"
    json.dumps(result, ensure_ascii=False, allow_nan=False)


def test_data_agent_no_data():
    """Data Agent 无数据 → data_report 类型 + data_source_type=none"""
    from agents.data_agent.agent import DataAgent
    agent = DataAgent()
    result = agent.run({
        "task_id": "test_nodata_001",
        "goal": "分析销售数据",
        "task_type": "data_analyze",
    })
    assert result["ok"] is True
    data = result["data"]
    # 无数据路径 → data_report 类型
    assert data.get("content_type") == "data_report"
    meta = result.get("meta", {})
    assert meta.get("data_source_type") == "none"
    assert meta.get("sample_rows", 0) == 0


# ── 12. metadata.data_source_type 通过 execute_agent 传递 ────

def test_execute_agent_data_source_type_csv(tmp_csv):
    """execute_agent 返回的 metadata 包含 data_source_type=csv"""
    from backend.services.agent_executor import execute_agent
    from backend.schemas.agent_protocol import AgentTask
    task = AgentTask(
        task_id="test_ds_csv_001",
        goal="分析数据",
        task_type="data_analyze",
        input={"file_path": tmp_csv},
    )
    result = execute_agent("data", task)
    assert result.ok is True
    assert result.metadata.get("data_source_type") == "csv"
    assert result.metadata.get("sample_rows", 0) == 3


def test_execute_agent_data_source_type_none():
    """execute_agent 返回的 metadata 包含 data_source_type=none"""
    from backend.services.agent_executor import execute_agent
    from backend.schemas.agent_protocol import AgentTask
    task = AgentTask(
        task_id="test_ds_none_001",
        goal="分析销售数据",
        task_type="data_analyze",
        input={"goal": "分析销售数据"},
    )
    result = execute_agent("data", task)
    assert result.ok is True
    assert result.metadata.get("data_source_type") == "none"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
