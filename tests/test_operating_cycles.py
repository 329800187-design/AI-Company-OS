"""Regression coverage for human-owned operating review cycles."""
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from backend.app import app
from core.memory.memory_store import MemoryStore


def _accepted_mission_with_kpi(service):
    mission = service.create_mission("为复盘周期记录人工 KPI", enabled_modules=["strategy"])
    from backend.database.database import get_db
    with get_db() as db:
        db.execute("""UPDATE boss_mission_modules SET status='done', result='人工已确认交付'
                      WHERE mission_id=? AND module_id='strategy'""", (mission["mission_id"],))
        db.execute("UPDATE boss_missions SET status='ready_for_review' WHERE mission_id=?", (mission["mission_id"],))
    service.accept_mission(mission["mission_id"], "用于周期复盘")
    observation = service.record_kpi_observation(
        mission["mission_id"], "完成率", 0.76, unit="ratio", direction="increased"
    )
    return mission, observation


def test_operating_cycle_requires_human_kpi_then_allows_one_human_review(tmp_path: Path):
    from backend.services.boss_command_center import BossCommandCenterService

    memory = MemoryStore(tmp_path / "memory.db")
    service = BossCommandCenterService(memory_store=memory)
    mission, observation = _accepted_mission_with_kpi(service)
    cycle = service.create_operating_cycle(
        "客户入职优化复盘", "判断本周期的入职流程是否需要调整",
        period_start="2026-08-01", period_end="2026-08-31",
        target_metrics={"completion_rate": 0.7},
    )

    with pytest.raises(ValueError, match="KPI observation"):
        service.review_operating_cycle(cycle["cycle_id"], "没有数据不能复盘", "adjust")

    collecting = service.attach_kpi_observation_to_cycle(cycle["cycle_id"], observation["id"])
    assert collecting["observation_count"] == 1
    reviewed = service.review_operating_cycle(
        cycle["cycle_id"], "完成率达到目标，保留当前流程并观察异常样本", "continue",
        ["下周期继续记录异常样本"],
    )

    assert reviewed["status"] == "reviewed"
    assert reviewed["review"]["decision"] == "continue"
    assert reviewed["observations"][0]["mission_id"] == mission["mission_id"]
    saved_review = memory.recall(f"boss_cycle_{cycle['cycle_id']}")
    assert saved_review is not None
    assert "reviewed_boss_operating_cycle" in saved_review["content"]
    assert "完成率达到目标" in saved_review["content"]
    with pytest.raises(ValueError, match="only once"):
        service.review_operating_cycle(cycle["cycle_id"], "再次复盘", "adjust")
    assert service.get_operating_summary()["reviewed_cycle_count"] >= 1


def test_operating_cycle_api_creates_and_lists_human_owned_cycles():
    client = TestClient(app)
    created = client.post("/boss/operating-cycles", json={
        "name": "API 复盘周期", "objective": "验证人工创建周期的接口",
        "target_metrics": {"sample_size": 10},
    })
    assert created.status_code == 200
    cycle_id = created.json()["cycle_id"]
    detail = client.get(f"/boss/operating-cycles/{cycle_id}")
    assert detail.status_code == 200
    assert detail.json()["status"] == "collecting"
    assert client.get("/boss/operating-cycles").status_code == 200
