import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from agents.qa_agent.agent import QAAgent


def main():
    task = {
        "task_id": "task_test_001",
        "goal": "测试 QA Agent 是否可以正常评分",
        "expected_output": {
            "type": "test_result",
            "description": "QA Agent 返回 score 和 status"
        },
        "result": {
            "summary": "模拟任务已经完成"
        }
    }

    qa_agent = QAAgent()
    result = qa_agent.run(task)

    print(result)


if __name__ == "__main__":
    main()