"""Commander planning must use, not merely fetch, shared operating memory."""
import json

from core.memory.memory_store import MemoryStore


def test_accepted_boss_memory_has_actionable_shared_context(tmp_path):
    memory = MemoryStore(tmp_path / "memory.db")
    memory.remember(
        key="boss_mission_example",
        source="boss",
        tags=["boss", "mission", "accepted", "execution"],
        importance=0.9,
        content=json.dumps({
            "record_type": "accepted_boss_mission",
            "goal": "优化客户入职流程",
            "review_comment": "先明确责任人和验收边界",
            "modules": [{"title": "执行计划", "summary": "第一天确定责任人，再按周复盘。"}],
        }, ensure_ascii=False),
    )

    context = memory.get_context("优化客户入职流程")

    assert "Boss 已验收" in context
    assert "先明确责任人和验收边界" in context
    assert "第一天确定责任人" in context


def test_commander_passes_planning_context_to_ceo():
    from backend.commander.commander import CommanderAgent

    commander = CommanderAgent()
    captured = {}

    class CEO:
        def run(self, task):
            captured.update(task)
            return {"output": {"created_tasks": [{
                "goal": "确认目标", "assigned_to": "qa", "task_type": "qa_review",
            }]}}

    commander.ceo = CEO()
    steps = commander._ceo_decompose(
        "优化客户入职流程", "planning_context_test",
        planning_context="## 相关记忆\n- [Boss 已验收] 搭建客户入职流程",
    )

    assert steps[0]["description"] == "确认目标"
    assert "Boss 已验收" in captured["planning_context"]
    assert captured["goal"] == "优化客户入职流程"


def test_ai_fallback_marks_memory_as_advisory(monkeypatch):
    from backend.commander.commander import CommanderAgent

    captured = {}

    def fake_call(prompt, **_kwargs):
        captured["prompt"] = prompt
        return '[{"step": 1, "description": "确认当前事实", "agent": "qa"}]'

    monkeypatch.setattr("backend.commander.commander._call_ai_v2", fake_call)
    steps = CommanderAgent()._ai_decompose(
        "优化客户入职流程", "ai_context_test", planning_context="已验收结论：先确认责任人",
    )

    assert steps[0]["description"] == "确认当前事实"
    assert "必须按当前目标重新核验" in captured["prompt"]
