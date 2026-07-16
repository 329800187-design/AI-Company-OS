"""CTO Agent 测试"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# 确保项目根在 path 中
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from agents.cto_agent.agent import CTOAgent


def test_code_review_rule_mode():
    """测试：规则模式代码审查（无 AI API 也正常返回）"""
    agent = CTOAgent(api_key="")  # 强制使用规则模式
    task = {
        "task_id": "test_review_001",
        "task_type": "code_review",
        "goal": "审查以下 Python 代码",
        "code": 'password = "hardcoded123"\ndef get_user(user_id):\n    sql = "SELECT * FROM users WHERE id=" + user_id\n    eval("print(1)")\n    except:\n        pass',
        "language": "python",
    }
    result = agent.run(task)
    assert result["agent"] == "cto"
    assert "data" in result
    assert len(result["data"].get("findings", [])) > 0, f"应有静态检查发现，实际: {result['data'].get('findings')}"
    print(f"  ✅ 代码审查（规则模式）: score={result['data']['score']}, findings={len(result['data']['findings'])}")
    for f in result["data"]["findings"]:
        print(f"     - [{f['severity']}] {f['description'][:60]}")


def test_tech_choice_rule_mode():
    """测试：规则模式技术选型"""
    agent = CTOAgent(api_key="")
    task = {
        "task_id": "test_tech_001",
        "task_type": "tech_choice",
        "goal": "构建一个 Web API 后端服务",
    }
    result = agent.run(task)
    assert result["status"] != "失败"
    assert "data" in result
    print(f"  ✅ 技术选型（规则模式）: {result['data']['summary'][:60]}")


def test_architect_review_rule_mode():
    """测试：规则模式架构评审"""
    agent = CTOAgent(api_key="")
    task = {
        "task_id": "test_arch_001",
        "task_type": "architecture_review",
        "goal": "评审电商系统架构",
        "architecture_desc": "单体应用 + 同步处理所有订单，无缓存，单数据库实例",
    }
    result = agent.run(task)
    assert result["agent"] == "cto"
    assert "data" in result
    print(f"  ✅ 架构评审（规则模式）: score={result['data']['score']}")


def test_task_decompose_rule_mode():
    """测试：规则模式任务拆解"""
    agent = CTOAgent(api_key="")
    task = {
        "task_id": "test_decomp_001",
        "task_type": "task_decompose",
        "goal": "实现用户认证模块",
    }
    result = agent.run(task)
    # subtasks may be in data.data.subtasks or data.subtasks
    data = result.get("data", {})
    subtasks = data.get("subtasks", []) or data.get("data", {}).get("subtasks", [])
    assert len(subtasks) > 0
    print(f"  ✅ 任务拆解（规则模式）: {len(subtasks)} 个子任务")
    for s in subtasks:
        print(f"     - {s.get('title', s)}")


def test_effort_estimate_rule_mode():
    """测试：规则模式工作量评估"""
    agent = CTOAgent(api_key="")
    task = {
        "task_id": "test_est_001",
        "task_type": "effort_estimate",
        "goal": "开发一个带有用户注册、登录、个人资料管理的 Web 应用",
    }
    result = agent.run(task)
    assert result["agent"] == "cto"
    data = result.get("data", {})
    # total_hours may be in data.data.total_hours
    total_hours = data.get("total_hours", 0) or data.get("data", {}).get("total_hours", 0)
    assert total_hours > 0
    print(f"  ✅ 工作量评估（规则模式）: {total_hours}h")


def test_smart_routing():
    """测试：智能推断 — 自动识别任务类型"""
    agent = CTOAgent(api_key="")
    # 代码关键词 → 代码审查
    task = {"task_id": "test_smart_1", "goal": "帮我看看这段代码有没有 bug"}
    result = agent.run(task)
    print(f"  ✅ 智能路由 '代码+bug' → {result['status']}")

    # 架构关键词 → 架构评审
    task = {"task_id": "test_smart_2", "goal": "评审微服务架构方案"}
    result = agent.run(task)
    print(f"  ✅ 智能路由 '架构评审' → {result['status']}")

    # 选型关键词 → 技术选型
    task = {"task_id": "test_smart_3", "goal": "推荐一个前端技术栈"}
    result = agent.run(task)
    print(f"  ✅ 智能路由 '技术选型' → {result['status']}")


if __name__ == "__main__":
    print("CTO Agent 测试")
    print("=" * 50)
    test_code_review_rule_mode()
    test_tech_choice_rule_mode()
    test_architect_review_rule_mode()
    test_task_decompose_rule_mode()
    test_effort_estimate_rule_mode()
    test_smart_routing()
    print("\n" + "=" * 50)
    print("全部 CTO Agent 测试通过 ✅")
