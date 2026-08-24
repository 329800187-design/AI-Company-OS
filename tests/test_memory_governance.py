"""Regression coverage for governed operating-memory retention and retirement."""
from datetime import datetime, timedelta
from pathlib import Path

from fastapi.testclient import TestClient

from backend.app import app
from core.memory.memory_store import MemoryStore


def test_retired_memory_is_removed_from_all_recall_paths(tmp_path: Path):
    store = MemoryStore(tmp_path / "memory.db")
    store.remember("boss_mission_demo", '{"goal":"优化客户入职流程"}', source="boss",
                   tags=["boss", "mission", "accepted"], importance=0.9)

    assert store.recall("boss_mission_demo") is not None
    assert store.retire_by_key("boss_mission_demo", "用户要求删除") is True

    assert store.recall("boss_mission_demo") is None
    assert store.search("客户入职") == []
    assert store.recent() == []
    assert store.get_context("客户入职") == ""
    summary = store.governance_summary(source="boss")
    assert summary["active_count"] == 0
    assert summary["retired_count"] == 1


def test_explicit_retention_cleanup_soft_deletes_only_expired_records(tmp_path: Path):
    store = MemoryStore(tmp_path / "memory.db")
    store.remember("expiring", "可过期的经营经验", source="boss", importance=0.8)
    store.remember("indefinite", "持续保留的经营经验", source="boss", importance=0.8)
    assert store.set_retention("expiring", retention_days=1, retention_class="operating_short")

    conn = store._get_conn()
    conn.execute("UPDATE memories SET expires_at=? WHERE key='expiring'",
                 ((datetime.now() - timedelta(seconds=1)).isoformat(),))
    conn.commit()

    cleanup = store.cleanup_expired(source="boss")
    assert cleanup["retired_count"] == 1
    assert store.recall("expiring") is None
    assert store.recall("indefinite") is not None
    assert store.governance_summary(source="boss")["expiring_count"] == 0


def test_memory_governance_routes_use_soft_retirement(tmp_path: Path, monkeypatch):
    store = MemoryStore(tmp_path / "memory.db")
    monkeypatch.setattr("backend.routers.memory_router.get_memory_store", lambda: store)
    client = TestClient(app)

    assert client.post("/memory/remember", json={
        "key": "route-governance", "content": "通过路由管理的经营经验", "source": "boss",
    }).status_code == 200
    assert client.patch("/memory/route-governance/retention", json={
        "retention_days": 30, "retention_class": "operating",
    }).status_code == 200
    overview = client.get("/memory/governance?source=boss")
    assert overview.status_code == 200
    assert overview.json()["active_count"] == 1
    assert client.request("DELETE", "/memory/route-governance/retire", json={"reason": "不再适用"}).status_code == 200
    assert client.get("/memory/search?q=经营经验").json()["count"] == 0
