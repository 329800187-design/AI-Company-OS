"""Phase R2.5 coverage for the inert code-execution capability placeholder."""

from pathlib import Path

import pytest

from core.memory.memory_store import MemoryStore


def _accepted_mission(service):
    mission = service.create_mission("验证预留代码执行能力", enabled_modules=["strategy"])
    from backend.database.database import get_db

    with get_db() as db:
        db.execute(
            "UPDATE boss_mission_modules SET status='done' WHERE mission_id=? AND module_id='strategy'",
            (mission["mission_id"],),
        )
        db.execute(
            "UPDATE boss_missions SET status='ready_for_review' WHERE mission_id=?",
            (mission["mission_id"],),
        )
    return service.accept_mission(mission["mission_id"])


def test_code_execution_connector_is_registered_but_unconfigured():
    from backend.services.action_connectors import get_action_connector, list_action_connectors

    connector = get_action_connector("code_execution")

    assert any(item["connector_id"] == "code_execution" for item in list_action_connectors())
    assert connector.describe() == {
        "connector_id": "code_execution",
        "display_name": "代码执行（未开通）",
        "mode": "disabled",
        "configured": False,
        "requires_human_approval": True,
        "requires_preflight": True,
        "external_side_effects": False,
        "credential_requirements": [],
        "note": "该能力尚未开通，不会执行代码、系统命令或外部操作。",
    }


def test_code_execution_preflight_and_execution_are_inert(tmp_path: Path):
    from backend.services.action_connectors import get_action_connector
    from backend.services.boss_command_center import BossCommandCenterService

    connector = get_action_connector("code_execution")
    preflight = connector.preflight({"action_type": "run", "payload": {"command": "echo unsafe"}})
    assert preflight["ready"] is False
    assert preflight["external_side_effects"] is False
    assert preflight["reason"] == "code_execution capability is not enabled"

    with pytest.raises(RuntimeError, match="code_execution capability is not enabled"):
        connector.execute({"action_type": "run", "payload": {"command": "echo unsafe"}})

    service = BossCommandCenterService(memory_store=MemoryStore(tmp_path / "memory.db"))
    mission = _accepted_mission(service)
    action = service.create_action_request(
        mission["mission_id"], "run", {"command": "echo unsafe"}, connector_id="code_execution"
    )
    preflighted = service.preflight_action(action["action_id"])
    assert preflighted["preflight"]["ready"] is False
    with pytest.raises(ValueError, match="successful action preflight"):
        service.approve_action(action["action_id"])
