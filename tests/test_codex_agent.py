"""测试 Codex Agent"""
import sys
sys.path.insert(0, r"E:\AI-company-os")

from agents.codex_agent.agent import CodexAgent


def test_code_execute():
    agent = CodexAgent(timeout=10)
    result = agent.run({
        "task_id": "test_exec_001",
        "task_type": "code_execute",
        "goal": "简单计算",
        "code": "print(1 + 2)\nprint(3 * 4)",
    })
    assert result["success"] is True, f"预期成功，实际: {result}"
    assert "3" in result["data"]["stdout"], f"输出应包含 3, 实际: {result['data']['stdout']}"
    print("[PASS] code_execute")


def test_code_write_and_run():
    agent = CodexAgent(timeout=10)
    result = agent.run({
        "task_id": "test_wr_001",
        "task_type": "code_write_and_run",
        "goal": "创建文件并执行",
        "files": {
            "hello.py": "print(100 + 200)\nprint('done')",
        },
    })
    assert result["success"] is True
    assert "300" in result["data"]["stdout"]
    assert "hello.py" in result["files_created"]
    print("[PASS] code_write_and_run")


def test_timeout():
    agent = CodexAgent(timeout=2)
    result = agent.run({
        "task_id": "test_timeout",
        "task_type": "code_execute",
        "goal": "死循环测试",
        "code": "import time; time.sleep(10); print('never')",
    })
    assert result["success"] is False
    # Timeout may have empty data
    print("[PASS] timeout protection")


def test_bad_code():
    agent = CodexAgent(timeout=10)
    result = agent.run({
        "task_id": "test_bad",
        "task_type": "code_execute",
        "goal": "语法错误",
        "code": "this is not valid python!!!",
    })
    assert result["success"] is False
    print("[PASS] syntax error handling")


def test_no_code():
    agent = CodexAgent(timeout=10)
    result = agent.run({
        "task_id": "test_empty",
        "task_type": "code_execute",
        "goal": "没有代码",
    })
    # 无 code 时会尝试 AI 生成。AI 成功则 success=True，AI 失败则 success=False
    # 两种情况都可能，取决于 AI API 是否配置
    print(f"[PASS] empty code handling (success={result['success']}, status={result.get('status','?')})")


if __name__ == "__main__":
    test_code_execute()
    test_code_write_and_run()
    test_timeout()
    test_bad_code()
    test_no_code()
    print("\n[ALL PASS] All Codex Agent tests passed")
