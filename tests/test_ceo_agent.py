"""测试 CEO Agent（新版：AI + 规则降级）"""
import sys
sys.path.insert(0, r"E:\AI-company-os")

from agents.ceo_agent.agent import CEOAgent


def test_ceo_ai_decompose():
    ceo = CEOAgent()
    result = ceo.run({"goal": "写一个Python脚本来计算1到100的质数之和"})

    assert result["status"] == "已完成", f"预期 已完成, 实际 {result['status']}"
    tasks = result["data"]["created_tasks"]
    assert len(tasks) >= 1, f"至少生成1个任务, 实际 {len(tasks)}"

    summary = result["data"].get("summary", "")
    print(f"  模式: {'AI' if 'AI' in summary else 'RULE'}")
    print(f"  生成 {len(tasks)} 个任务:")
    for t in tasks:
        print(f"    - [{t['task_type']}] {t['assigned_to']}: {t['goal']}")
        if t.get("code"):
            print(f"      code: {t['code'][:50]}...")
        if t.get("files"):
            print(f"      files: {list(t['files'].keys())}")

    print("[PASS] ceo_ai_decompose")


def test_ceo_rule_decompose():
    ceo = CEOAgent(api_key="")
    result = ceo.run({"goal": "开发一个登录页面"})

    assert result["status"] == "已完成"
    tasks = result["data"]["created_tasks"]
    assert len(tasks) >= 2  # 至少包含 执行 + QA
    assert tasks[0]["assigned_to"] in ("codex_agent", "openclaw_agent", "system_agent")
    assert tasks[-1]["assigned_to"] in ("qa_agent", "codex_agent", "openclaw_agent")
    print("[PASS] ceo_rule_decompose")


def test_ceo_empty_goal():
    ceo = CEOAgent()
    result = ceo.run({"goal": ""})
    assert result["status"] in ("失败", "failed"), f"Expected 失败 or failed, got {result['status']}"
    print("[PASS] ceo_empty_goal")


if __name__ == "__main__":
    test_ceo_empty_goal()
    test_ceo_rule_decompose()
    print("\n--- AI mode test (needs network) ---")
    test_ceo_ai_decompose()
    print("\n[ALL PASS] All CEO Agent tests passed")
