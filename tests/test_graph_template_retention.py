"""Graph Template Audit Retention Policy 测试

覆盖场景：
  1. storage summary 空目录
  2. storage summary 多文件统计
  3. dry_run 不删除
  4. apply 删除过期已删除模板 audit
  5. 未删除模板 audit 不删除
  6. retention_days <= 0 报错
  7. 非 tpl_*.jsonl 文件跳过
  8. 损坏 JSONL 不崩
  9. API storage 返回正确
  10. API cleanup dry_run/apply 正确
"""
import json
import pytest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch, MagicMock

from backend.services.graph_template_retention import (
    scan_audit_files,
    summarize_audit_storage,
    cleanup_audit_logs,
)


# ── 存储层测试（使用 tmp_path 隔离） ─────────────────────────


class TestAuditRetention:
    """Graph Template Audit Retention 纯存储层测试"""

    @pytest.fixture(autouse=True)
    def setup_tmp_dir(self, tmp_path, monkeypatch):
        """每个测试使用独立的临时目录"""
        self.audit_dir = tmp_path / "graph_template_audit"
        self.audit_dir.mkdir()
        monkeypatch.setattr(
            "backend.services.graph_template_retention.DEFAULT_AUDIT_DIR",
            self.audit_dir,
        )
        # 模板目录也需要隔离
        self.templates_dir = tmp_path / "graph_templates"
        self.templates_dir.mkdir()
        monkeypatch.setattr(
            "backend.services.graph_template_store.DEFAULT_TEMPLATES_DIR",
            self.templates_dir,
        )

    def _write_audit_file(self, template_id: str, events: list[dict]) -> Path:
        """写入审计文件"""
        file_path = self.audit_dir / f"{template_id}.jsonl"
        with open(file_path, "w", encoding="utf-8") as f:
            for event in events:
                f.write(json.dumps(event, ensure_ascii=False) + "\n")
        return file_path

    def _write_template_file(self, template_id: str) -> Path:
        """写入模板文件（表示模板存在）"""
        file_path = self.templates_dir / f"{template_id}.json"
        template = {
            "template_id": template_id,
            "name": f"Template {template_id}",
            "nodes": [],
            "edges": [],
            "created_at": datetime.now(timezone.utc).isoformat(),
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }
        file_path.write_text(json.dumps(template, ensure_ascii=False), encoding="utf-8")
        return file_path

    def _make_event(self, template_id: str, timestamp: str, event_type: str = "create") -> dict:
        """创建测试事件"""
        return {
            "event_id": f"aevt_test_{template_id}_{event_type}",
            "timestamp": timestamp,
            "template_id": template_id,
            "event_type": event_type,
            "summary": f"Test {event_type} event",
            "details": {},
        }

    # ── 1. storage summary 空目录 ─────────────────────────────

    def test_storage_summary_empty_dir(self):
        """空目录返回零统计"""
        summary = summarize_audit_storage(self.audit_dir)
        assert summary["file_count"] == 0
        assert summary["total_bytes"] == 0
        assert summary["total_size_human"] == "0 B"
        assert summary["earliest_event"] is None
        assert summary["latest_event"] is None
        assert summary["files"] == []

    # ── 2. storage summary 多文件统计 ─────────────────────────

    def test_storage_summary_multiple_files(self):
        """多文件统计正确"""
        now = datetime.now(timezone.utc)
        ts1 = (now - timedelta(days=10)).isoformat()
        ts2 = (now - timedelta(days=5)).isoformat()
        ts3 = now.isoformat()

        self._write_audit_file("tpl_001", [self._make_event("tpl_001", ts1)])
        self._write_audit_file("tpl_002", [
            self._make_event("tpl_002", ts2),
            self._make_event("tpl_002", ts3),
        ])

        summary = summarize_audit_storage(self.audit_dir)
        assert summary["file_count"] == 2
        assert summary["total_bytes"] > 0
        assert summary["earliest_event"] == ts1
        assert summary["latest_event"] == ts3
        assert len(summary["files"]) == 2

    # ── 3. dry_run 不删除 ─────────────────────────────────────

    def test_dry_run_does_not_delete(self):
        """dry_run=True 不删除文件"""
        now = datetime.now(timezone.utc)
        old_ts = (now - timedelta(days=60)).isoformat()

        # 创建一个已删除模板的审计文件（模板不存在）
        self._write_audit_file("tpl_deleted", [
            self._make_event("tpl_deleted", old_ts, "delete"),
        ])

        result = cleanup_audit_logs(retention_days=30, dry_run=True, audit_dir=self.audit_dir)
        assert result["dry_run"] is True
        assert result["matched"] == 1
        assert result["deleted"] == 0
        assert len(result["would_delete"]) == 1

        # 文件仍然存在
        assert (self.audit_dir / "tpl_deleted.jsonl").exists()

    # ── 4. apply 删除过期已删除模板 audit ─────────────────────

    def test_apply_deletes_expired_deleted_template_audit(self):
        """apply 删除过期已删除模板的审计文件"""
        now = datetime.now(timezone.utc)
        old_ts = (now - timedelta(days=60)).isoformat()

        # 创建一个已删除模板的审计文件（模板不存在）
        self._write_audit_file("tpl_deleted", [
            self._make_event("tpl_deleted", old_ts, "delete"),
        ])

        result = cleanup_audit_logs(retention_days=30, dry_run=False, audit_dir=self.audit_dir)
        assert result["dry_run"] is False
        assert result["matched"] == 1
        assert result["deleted"] == 1
        assert result["bytes_freed"] > 0
        assert len(result["would_delete"]) == 0

        # 文件已被删除
        assert not (self.audit_dir / "tpl_deleted.jsonl").exists()

    # ── 5. 未删除模板 audit 不删除 ─────────────────────────────

    def test_does_not_delete_active_template_audit(self):
        """不删除仍存在的模板的审计文件"""
        now = datetime.now(timezone.utc)
        old_ts = (now - timedelta(days=60)).isoformat()

        # 创建一个存在模板的审计文件
        self._write_template_file("tpl_active")
        self._write_audit_file("tpl_active", [
            self._make_event("tpl_active", old_ts, "create"),
        ])

        result = cleanup_audit_logs(retention_days=30, dry_run=False, audit_dir=self.audit_dir)
        assert result["matched"] == 0
        assert result["deleted"] == 0
        assert result["skipped"] == 1

        # 文件仍然存在
        assert (self.audit_dir / "tpl_active.jsonl").exists()

    # ── 6. retention_days <= 0 报错 ───────────────────────────

    def test_retention_days_zero_raises(self):
        """retention_days=0 抛出 ValueError"""
        with pytest.raises(ValueError, match="retention_days must be positive"):
            cleanup_audit_logs(retention_days=0, dry_run=True, audit_dir=self.audit_dir)

    def test_retention_days_negative_raises(self):
        """retention_days=-1 抛出 ValueError"""
        with pytest.raises(ValueError, match="retention_days must be positive"):
            cleanup_audit_logs(retention_days=-1, dry_run=True, audit_dir=self.audit_dir)

    # ── 7. 非 tpl_*.jsonl 文件跳过 ────────────────────────────

    def test_skips_non_tpl_files(self):
        """跳过不符合命名规则的文件"""
        # 创建不符合规则的文件
        (self.audit_dir / "random.jsonl").write_text('{"test": true}\n')
        (self.audit_dir / "tpl_invalid!.jsonl").write_text('{"test": true}\n')
        (self.audit_dir / "other_file.txt").write_text('test')

        files = scan_audit_files(self.audit_dir)
        assert len(files) == 0

    # ── 8. 损坏 JSONL 不崩 ────────────────────────────────────

    def test_corrupt_jsonl_does_not_crash(self):
        """损坏的 JSONL 行被跳过，不影响其他行"""
        now = datetime.now(timezone.utc)
        old_ts = (now - timedelta(days=60)).isoformat()

        # 写入包含损坏行的审计文件
        file_path = self.audit_dir / "tpl_corrupt.jsonl"
        with open(file_path, "w", encoding="utf-8") as f:
            f.write("this is not json\n")
            f.write(json.dumps(self._make_event("tpl_corrupt", old_ts, "delete")) + "\n")
            f.write('{"incomplete": \n')
            f.write("\n")  # 空行

        summary = summarize_audit_storage(self.audit_dir)
        assert summary["file_count"] == 1
        assert summary["files"][0]["event_count"] == 1  # 只计算有效行

    # ── 9. API storage 返回正确 ───────────────────────────────

    def test_api_storage_endpoint(self, client):
        """GET /boss/graph/audit/storage 返回正确"""
        response = client.get("/boss/graph/audit/storage")
        assert response.status_code == 200
        data = response.json()
        assert data["ok"] is True
        assert "storage" in data
        assert "file_count" in data["storage"]
        assert "total_bytes" in data["storage"]
        assert "total_size_human" in data["storage"]

    # ── 10. API cleanup dry_run/apply 正确 ────────────────────

    def test_api_cleanup_dry_run(self, client):
        """POST /boss/graph/audit/cleanup dry_run=True 不删除"""
        now = datetime.now(timezone.utc)
        old_ts = (now - timedelta(days=60)).isoformat()

        # 创建测试文件
        self._write_audit_file("tpl_test", [
            self._make_event("tpl_test", old_ts, "delete"),
        ])

        response = client.post("/boss/graph/audit/cleanup", json={
            "retention_days": 30,
            "dry_run": True,
        })
        assert response.status_code == 200
        data = response.json()
        assert data["ok"] is True
        assert data["cleanup"]["dry_run"] is True
        assert data["cleanup"]["matched"] >= 0

    def test_api_cleanup_apply(self, client):
        """POST /boss/graph/audit/cleanup dry_run=False 删除"""
        now = datetime.now(timezone.utc)
        old_ts = (now - timedelta(days=60)).isoformat()

        # 创建测试文件（模板不存在）
        self._write_audit_file("tpl_old", [
            self._make_event("tpl_old", old_ts, "delete"),
        ])

        response = client.post("/boss/graph/audit/cleanup", json={
            "retention_days": 30,
            "dry_run": False,
        })
        assert response.status_code == 200
        data = response.json()
        assert data["ok"] is True
        assert data["cleanup"]["dry_run"] is False

    def test_api_cleanup_invalid_retention_days(self, client):
        """POST /boss/graph/audit/cleanup retention_days=0 返回 422 (Pydantic validation)"""
        response = client.post("/boss/graph/audit/cleanup", json={
            "retention_days": 0,
            "dry_run": True,
        })
        assert response.status_code == 422


# ── API 测试用的 client fixture ──────────────────────────────


@pytest.fixture
def client(tmp_path, monkeypatch):
    """创建测试客户端，隔离存储目录"""
    from fastapi.testclient import TestClient
    from backend.app import app

    # 隔离存储目录（使用 exist_ok 避免目录已存在时出错）
    audit_dir = tmp_path / "graph_template_audit"
    audit_dir.mkdir(exist_ok=True)
    templates_dir = tmp_path / "graph_templates"
    templates_dir.mkdir(exist_ok=True)

    monkeypatch.setattr(
        "backend.services.graph_template_retention.DEFAULT_AUDIT_DIR",
        audit_dir,
    )
    monkeypatch.setattr(
        "backend.services.graph_template_store.DEFAULT_TEMPLATES_DIR",
        templates_dir,
    )

    return TestClient(app)
