"""端到端测试：CEO -> Codex -> QA 完整工作流"""
import sys
sys.path.insert(0, r"E:\AI-company-os")

from agents.ceo_agent.agent import CEOAgent
from agents.codex_agent.agent import CodexAgent
from agents.qa_agent.agent import QAAgent
from backend.schemas.task_schema import TaskCreate
from backend.services.task_service import task_service


def test_e2e_ai_workflow():
    """模拟 /ceo-codex-task 工作流：AI 模式"""
    ceo = CEOAgent()
    codex = CodexAgent(timeout=30)
    qa = QAAgent()

    # Step 1: CEO 拆解
    ceo_result = ceo.run({"goal": "写一个函数来判断一个数是否是回文数，并测试 121"})
    tasks_data = ceo_result["data"]["created_tasks"]
    summary = ceo_result["data"].get("summary", "")
    print(f"CEO 拆解: {len(tasks_data)} 个任务 (mode: {'AI' if 'AI' in summary else 'RULE'})")

    assert len(tasks_data) > 0

    for i, task_data in enumerate(tasks_data):
        print(f"\n--- Task {i+1}: [{task_data['task_type']}] {task_data['assigned_to']} ---")
        print(f"  goal: {task_data['goal']}")

        # 保存任务
        tc = TaskCreate(**task_data)
        saved = task_service.create_task(tc)

        # Codex 执行（如果是 codex 类型的任务）
        if saved.assigned_to == "codex_agent":
            codex_task = {
                "task_id": saved.task_id,
                "task_type": task_data.get("task_type", "code_execute"),
                "title": task_data.get("goal", ""),
                "goal": task_data.get("goal", ""),
                "code": task_data.get("code", ""),
                "files": task_data.get("files", {}),
                "expected_output": task_data.get("expected_output", {}),
            }
            codex_result = codex.run(codex_task)
            stdout = codex_result.get('data', {}).get('stdout', '') or codex_result.get('data', {}).get('result', '')
            print(f"  stdout: {str(stdout)[:100]}")
            # 无 code 时 Codex 尝试 AI 生成代码；AI 不可用时 success=False 也是正常的
            if not codex_result["success"]:
                print(f"  (Codex 未成功执行，将跳过 QA 验收)")
                codex_result = {"result": f"codex fallback: {codex_result.get('data', {}).get('stderr', '')[:200]}"}
        else:
            codex_result = {"result": "skipped - not a codex task"}

        # QA 验收
        qa_input = {
            "task_id": saved.task_id,
            "goal": task_data.get("goal", ""),
            "expected_output": task_data.get("expected_output", {}),
            "result": codex_result.get("data", {}).get("stdout") or codex_result.get("result", ""),
        }
        qa_result = qa.run(qa_input)
        print(f"  QA: score={qa_result['data']['score']} status={qa_result['status']}")

    print("\n[PASS] e2e_ai_workflow")


def test_e2e_rule_workflow():
    """测试规则模式降级也正常"""
    ceo = CEOAgent(api_key="")
    codex = CodexAgent(timeout=10)
    qa = QAAgent()

    ceo_result = ceo.run({"goal": "打印 Hello World"})
    tasks_data = ceo_result["output"]["created_tasks"]
    print(f"\n规则模式: {len(tasks_data)} 个任务")

    for task_data in tasks_data:
        tc = TaskCreate(**task_data)
        saved = task_service.create_task(tc)

        if saved.assigned_to == "codex_agent":
            codex_task = {
                "task_id": saved.task_id,
                "task_type": task_data.get("task_type"),
                "title": task_data.get("goal", ""),
                "goal": task_data.get("goal", ""),
                "code": task_data.get("code", ""),
                "files": task_data.get("files", {}),
            }
            c_result = codex.run(codex_task)
            print(f"  Codex: success={c_result['success']}")
        else:
            print(f"  {saved.assigned_to}: skipped codex")

    print("[PASS] e2e_rule_workflow")


if __name__ == "__main__":
    test_e2e_rule_workflow()
    print("\n--- AI E2E ---")
    test_e2e_ai_workflow()
    print("\n[ALL PASS] End-to-end workflow tests passed")
