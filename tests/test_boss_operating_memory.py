"""Regression coverage for the Boss human-accepted operating-memory loop."""
from pathlib import Path

from core.memory.memory_store import MemoryStore


def _review_ready_mission(service, goal="为新客户建立入职流程"):
    mission = service.create_mission(goal, enabled_modules=["strategy"])
    from backend.database.database import get_db
    with get_db() as db:
        db.execute("""UPDATE boss_mission_modules
                      SET status='done', result=?, next_actions=?
                      WHERE mission_id=? AND module_id='strategy'""",
                   ("先确认关键交付与责任人，再按周推进。", '["确认责任人"]', mission["mission_id"]))
        db.execute("UPDATE boss_missions SET status='ready_for_review' WHERE mission_id=?",
                   (mission["mission_id"],))
    return mission


def test_acceptance_persists_bounded_operating_memory(tmp_path: Path):
    from backend.services.boss_command_center import BossCommandCenterService

    memory = MemoryStore(tmp_path / "memory.db")
    service = BossCommandCenterService(memory_store=memory)
    mission = _review_ready_mission(service)

    accepted = service.accept_mission(mission["mission_id"], comment="后续优先明确交付边界")

    saved = memory.recall(f"boss_mission_{mission['mission_id']}")
    assert accepted["status"] == "done"
    assert saved is not None
    assert saved["source"] == "boss"
    assert {"mission", "accepted"}.issubset(saved["tags"])
    assert "后续优先明确交付边界" in saved["content"]
    assert any(event["type"] == "mission_memory_saved" for event in service.get_events(mission["mission_id"]))


def test_new_mission_modules_receive_relevant_accepted_memory(tmp_path: Path, monkeypatch):
    from backend.services.boss_command_center import BossCommandCenterService
    from backend.services.boss_module_executors import ExecutionResult

    memory = MemoryStore(tmp_path / "memory.db")
    service = BossCommandCenterService(memory_store=memory)
    first = _review_ready_mission(service, "搭建客户入职流程")
    service.accept_mission(first["mission_id"], comment="责任人要在第一天确认")

    second = service.create_mission("优化客户入职流程", enabled_modules=["strategy"])
    captured = {}

    class Executor:
        def execute(self, goal, module_id, mission_id, context=None):
            captured.update(context or {})
            return ExecutionResult(ok=True, final_answer="完成规划结果", confidence=0.8)

    monkeypatch.setattr("backend.services.boss_module_executors.get_executor", lambda *_: Executor())
    service.run_module(second["mission_id"], "strategy")

    assert "已验收的相关经验" in captured["accepted_mission_memory"]
    assert "搭建客户入职流程" in captured["accepted_mission_memory"]


def test_default_executor_appends_operating_memory_to_runtime_prompt(monkeypatch):
    from backend.services.boss_module_executors import DefaultModuleExecutor

    captured = {}

    class Runtime:
        def execute(self, prompt, context):
            captured["prompt"] = prompt
            captured["context"] = context
            return {"ok": True, "final_answer": "已完成", "confidence": 0.8}

    monkeypatch.setattr(
        "backend.services.local_agent_runtime.get_local_agent_runtime", lambda: Runtime()
    )
    result = DefaultModuleExecutor().execute(
        "优化客户入职流程", "strategy", "mission_example",
        context={"accepted_mission_memory": "## 已验收的相关经验\\n- 已验收目标：搭建客户入职流程"},
    )

    assert result.ok is True
    assert "已验收的相关经验" in captured["prompt"]
    assert captured["context"]["accepted_mission_memory"].startswith("## 已验收")


def test_memory_write_failure_does_not_reverse_human_acceptance():
    from backend.services.boss_command_center import BossCommandCenterService

    class BrokenMemory:
        def remember(self, **_kwargs):
            raise RuntimeError("memory unavailable")

    service = BossCommandCenterService(memory_store=BrokenMemory())
    mission = _review_ready_mission(service, "验收失败隔离")

    accepted = service.accept_mission(mission["mission_id"])

    assert accepted["status"] == "done"
    assert any(event["type"] == "mission_memory_failed" for event in service.get_events(mission["mission_id"]))


def test_human_outcome_is_persisted_and_syncs_to_operating_memory(tmp_path: Path):
    from backend.services.boss_command_center import BossCommandCenterService

    memory = MemoryStore(tmp_path / "memory.db")
    service = BossCommandCenterService(memory_store=memory)
    mission = _review_ready_mission(service, "提升客户入职完成率")
    service.accept_mission(mission["mission_id"])

    outcome = service.record_outcome(
        mission["mission_id"], "improved", metrics={"completion_rate": 0.72},
        note="两周后完成率从 0.48 提升到 0.72",
    )

    assert outcome["outcome_status"] == "improved"
    assert outcome["metrics"]["completion_rate"] == 0.72
    saved = memory.recall(f"boss_mission_{mission['mission_id']}")
    assert '"status": "improved"' in saved["content"]
    assert "completion_rate" in memory.get_context("提升客户入职完成率")
    assert any(event["type"] == "mission_outcome_recorded" for event in service.get_events(mission["mission_id"]))


def test_outcome_requires_human_accepted_mission(tmp_path: Path):
    from backend.services.boss_command_center import BossCommandCenterService
    import pytest

    service = BossCommandCenterService(memory_store=MemoryStore(tmp_path / "memory.db"))
    mission = service.create_mission("未验收不应记录结果", enabled_modules=["strategy"])

    with pytest.raises(ValueError, match="human-accepted"):
        service.record_outcome(mission["mission_id"], "improved")


def test_operating_summary_counts_accepted_missions_and_feedback(tmp_path: Path):
    from backend.services.boss_command_center import BossCommandCenterService

    service = BossCommandCenterService(memory_store=MemoryStore(tmp_path / "memory.db"))
    mission = _review_ready_mission(service, "运营概览闭环测试")
    service.accept_mission(mission["mission_id"])
    service.record_outcome(mission["mission_id"], "unchanged")

    summary = service.get_operating_summary()

    assert summary["accepted_mission_count"] >= 1
    assert summary["outcome_counts"]["unchanged"] >= 1
    assert summary["outcome_feedback_rate"] > 0
    assert service.get_mission(mission["mission_id"])["outcome"]["outcome_status"] == "unchanged"


def test_accepted_mission_action_requires_separate_approval_and_records_receipt(tmp_path: Path):
    from backend.services.boss_command_center import BossCommandCenterService

    memory = MemoryStore(tmp_path / "memory.db")
    service = BossCommandCenterService(memory_store=memory)
    mission = _review_ready_mission(service, "验证人工批准后的动作回执")
    service.accept_mission(mission["mission_id"])

    action = service.create_action_request(
        mission["mission_id"], "publish_delivery", {"delivery_id": "demo-1"},
        summary="以本地模拟方式验证交付发布",
    )
    assert action["status"] == "pending_approval"
    with __import__("pytest").raises(ValueError, match="preflight"):
        service.approve_action(action["action_id"])
    preflighted = service.preflight_action(action["action_id"])
    assert preflighted["preflight"]["ready"] is True
    assert preflighted["preflight"]["external_side_effects"] is False
    with __import__("pytest").raises(ValueError, match="approved"):
        service.execute_action(action["action_id"])

    approved = service.approve_action(action["action_id"], "已核对发布范围")
    assert approved["status"] == "approved"
    executed = service.execute_action(action["action_id"])
    assert executed["status"] == "executed"
    assert executed["receipt"]["simulated"] is True
    assert service.get_mission(mission["mission_id"])["actions"][0]["status"] == "executed"
    saved = memory.recall(f"boss_mission_{mission['mission_id']}")
    assert "action_receipts" in saved["content"]
    assert any(event["type"] == "action_preflighted" for event in service.get_events(mission["mission_id"]))
    assert any(event["type"] == "action_executed" for event in service.get_events(mission["mission_id"]))


def test_kpi_observation_requires_accepted_mission_and_can_reference_action(tmp_path: Path):
    from backend.services.boss_command_center import BossCommandCenterService
    import pytest

    service = BossCommandCenterService(memory_store=MemoryStore(tmp_path / "memory.db"))
    pending = service.create_mission("未验收 KPI 不应写入", enabled_modules=["strategy"])
    with pytest.raises(ValueError, match="human-accepted"):
        service.record_kpi_observation(pending["mission_id"], "完成率", 0.5)

    mission = _review_ready_mission(service, "记录动作后的 KPI 观测")
    service.accept_mission(mission["mission_id"])
    action = service.create_action_request(mission["mission_id"], "notify_stakeholders")
    service.preflight_action(action["action_id"])
    service.approve_action(action["action_id"])
    service.execute_action(action["action_id"])
    observation = service.record_kpi_observation(
        mission["mission_id"], "完成率", 0.81, unit="ratio", direction="increased",
        note="人工复核后的两周观测", action_id=action["action_id"],
    )

    assert observation["source"] == "human_entry"
    assert observation["action_id"] == action["action_id"]
    summary = service.get_operating_summary()
    assert summary["executed_action_count"] >= 1
    assert summary["kpi_observation_count"] >= 1


def test_unexecuted_action_can_be_cancelled_with_a_human_reason(tmp_path: Path):
    from backend.services.boss_command_center import BossCommandCenterService
    import pytest

    service = BossCommandCenterService(memory_store=MemoryStore(tmp_path / "memory.db"))
    mission = _review_ready_mission(service, "取消尚未执行的动作")
    service.accept_mission(mission["mission_id"])
    action = service.create_action_request(mission["mission_id"], "notify_stakeholders")

    with pytest.raises(ValueError, match="reason"):
        service.cancel_action(action["action_id"], "")
    cancelled = service.cancel_action(action["action_id"], "范围发生变化，暂不通知")

    assert cancelled["status"] == "cancelled"
    assert cancelled["cancellation_reason"] == "范围发生变化，暂不通知"
    with pytest.raises(ValueError, match="pending action"):
        service.preflight_action(action["action_id"])
    with pytest.raises(ValueError, match="pending"):
        service.approve_action(action["action_id"])
    assert any(event["type"] == "action_cancelled" for event in service.get_events(mission["mission_id"]))


def test_action_payload_rejects_credential_shaped_fields(tmp_path: Path):
    from backend.services.boss_command_center import BossCommandCenterService
    import pytest

    service = BossCommandCenterService(memory_store=MemoryStore(tmp_path / "memory.db"))
    mission = _review_ready_mission(service, "保护动作载荷中的凭据")
    service.accept_mission(mission["mission_id"])

    with pytest.raises(ValueError, match="must not contain credentials"):
        service.create_action_request(
            mission["mission_id"], "send_update", {"destination": "team", "api_key": "not-a-real-key"}
        )
    allowed = service.create_action_request(
        mission["mission_id"], "send_update", {"destination": "team", "message": "已完成"}
    )
    assert allowed["payload"]["destination"] == "team"


def test_expired_action_approval_requires_fresh_preflight_and_approval(tmp_path: Path):
    from backend.database.database import get_db
    from backend.services.boss_command_center import BossCommandCenterService
    import pytest

    service = BossCommandCenterService(memory_store=MemoryStore(tmp_path / "memory.db"))
    mission = _review_ready_mission(service, "过期批准不能执行")
    service.accept_mission(mission["mission_id"])
    action = service.create_action_request(mission["mission_id"], "notify_stakeholders")
    service.preflight_action(action["action_id"])
    service.approve_action(action["action_id"])
    with get_db() as db:
        db.execute(
            "UPDATE boss_mission_actions SET approval_expires_at=? WHERE action_id=?",
            ("2000-01-01T00:00:00+00:00", action["action_id"]),
        )

    with pytest.raises(ValueError, match="approval has expired"):
        service.execute_action(action["action_id"])

    reset = service.get_action(action["action_id"])
    assert reset["status"] == "pending_approval"
    assert reset["approval_expires_at"] is None
    assert reset["preflight"] == {}
    assert any(event["type"] == "action_approval_expired" for event in service.get_events(mission["mission_id"]))


def test_boss_overview_api_exposes_operating_loop_counters():
    from fastapi.testclient import TestClient
    from backend.app import app

    response = TestClient(app).get("/boss/overview")

    assert response.status_code == 200
    body = response.json()
    assert {
        "mission_count", "accepted_mission_count", "outcome_count", "outcome_feedback_rate",
        "action_count", "executed_action_count", "kpi_observation_count",
    }.issubset(body)


def test_action_connectors_api_exposes_safe_preflight_contract():
    from fastapi.testclient import TestClient
    from backend.app import app

    response = TestClient(app).get("/boss/action-connectors")

    assert response.status_code == 200
    connector = response.json()["connectors"][0]
    assert connector["connector_id"] == "local_simulation"
    assert connector["requires_preflight"] is True
    assert connector["external_side_effects"] is False
