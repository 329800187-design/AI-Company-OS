"""Graph Template Store 测试

覆盖场景：
  1. 创建模板成功
  2. 创建模板时 invalid graph 返回 400
  3. 列出模板
  4. 获取单个模板
  5. 删除模板
  6. 删除不存在模板返回 404
  7. 模板 JSON 文件确实落盘
  8. 按模板执行（mock execute_agent）
"""
import json
import pytest
from unittest.mock import patch, MagicMock
from pathlib import Path

from backend.services.graph_template_store import (
    save_template,
    get_template,
    list_templates,
    delete_template,
    update_template,
    save_version_snapshot,
    list_versions,
    get_version,
    delete_versions_for_template,
    update_canvas_layout,
)


# ── 存储层测试（使用 tmp_path 隔离） ─────────────────────────


class TestTemplateStore:
    """Graph Template Store 纯存储层测试"""

    @pytest.fixture(autouse=True)
    def setup_tmp_dir(self, tmp_path, monkeypatch):
        """每个测试使用独立的临时目录"""
        self.tmp_dir = tmp_path / "graph_templates"
        self.tmp_dir.mkdir()
        monkeypatch.setattr(
            "backend.services.graph_template_store.DEFAULT_TEMPLATES_DIR",
            self.tmp_dir,
        )
        # Phase 6.6: 版本目录也需要隔离
        self.versions_dir = tmp_path / "graph_template_versions"
        self.versions_dir.mkdir()
        monkeypatch.setattr(
            "backend.services.graph_template_store.DEFAULT_VERSIONS_DIR",
            self.versions_dir,
        )
        # Phase 6.8: 审计日志目录也需要隔离，避免 API 测试污染 output/
        self.audit_dir = tmp_path / "graph_template_audit"
        self.audit_dir.mkdir()
        monkeypatch.setattr(
            "backend.services.graph_template_audit.DEFAULT_AUDIT_DIR",
            self.audit_dir,
        )

    def _sample_nodes(self):
        return [
            {"id": "research", "agent_id": "research", "task_type": "research_brief", "title": "调研", "prompt": "做调研"},
            {"id": "marketing", "agent_id": "marketing", "task_type": "copywriting", "title": "营销", "prompt": "做营销"},
        ]

    def _sample_edges(self):
        return [{"from_node": "research", "to_node": "marketing", "handoff_type": "context"}]

    def test_save_and_get_template(self):
        """保存后可读取"""
        template = save_template(
            name="测试模板",
            nodes=self._sample_nodes(),
            edges=self._sample_edges(),
            description="测试描述",
            goal_hint="测试目标",
        )
        assert template["template_id"].startswith("tpl_")
        assert template["name"] == "测试模板"
        assert template["description"] == "测试描述"
        assert template["goal_hint"] == "测试目标"
        assert len(template["nodes"]) == 2
        assert len(template["edges"]) == 1
        assert "created_at" in template
        assert "updated_at" in template

        # 读取
        loaded = get_template(template["template_id"])
        assert loaded is not None
        assert loaded["template_id"] == template["template_id"]
        assert loaded["name"] == "测试模板"

    def test_file_written_to_disk(self):
        """模板 JSON 确实落盘"""
        template = save_template(
            name="落盘测试",
            nodes=self._sample_nodes(),
            edges=self._sample_edges(),
        )
        file_path = self.tmp_dir / f"{template['template_id']}.json"
        assert file_path.exists()

        data = json.loads(file_path.read_text(encoding="utf-8"))
        assert data["template_id"] == template["template_id"]
        assert data["name"] == "落盘测试"

    def test_list_templates(self):
        """列出所有模板"""
        # 创建 3 个模板
        ids = []
        for i in range(3):
            t = save_template(
                name=f"模板 {i}",
                nodes=self._sample_nodes(),
                edges=self._sample_edges(),
            )
            ids.append(t["template_id"])

        templates = list_templates()
        assert len(templates) == 3
        # 验证所有模板都在
        returned_ids = {t["template_id"] for t in templates}
        assert returned_ids == set(ids)

    def test_list_templates_empty(self):
        """空目录返回空列表"""
        templates = list_templates()
        assert templates == []

    def test_get_nonexistent_template(self):
        """不存在的模板返回 None"""
        result = get_template("tpl_nonexistent")
        assert result is None

    def test_delete_template(self):
        """删除模板成功"""
        template = save_template(
            name="待删除",
            nodes=self._sample_nodes(),
            edges=self._sample_edges(),
        )
        tid = template["template_id"]

        # 确认存在
        assert get_template(tid) is not None

        # 删除
        deleted = delete_template(tid)
        assert deleted is True

        # 确认不存在
        assert get_template(tid) is None

    def test_delete_nonexistent_returns_false(self):
        """删除不存在的模板返回 False"""
        deleted = delete_template("tpl_nonexistent")
        assert deleted is False

    def test_custom_template_id(self):
        """可指定 template_id"""
        template = save_template(
            name="自定义 ID",
            nodes=self._sample_nodes(),
            edges=self._sample_edges(),
            template_id="tpl_custom_123",
        )
        assert template["template_id"] == "tpl_custom_123"
        assert get_template("tpl_custom_123") is not None

    def test_invalid_template_id_rejected_on_save(self):
        """Invalid template IDs are rejected before writing files."""
        with pytest.raises(ValueError):
            save_template(
                name="Invalid ID",
                nodes=self._sample_nodes(),
                edges=[],
                template_id="../evil",
            )

    def test_invalid_template_id_cannot_read_or_delete(self):
        """Path-like template IDs are treated as not found."""
        assert get_template("../evil") is None
        assert delete_template("../evil") is False

    def test_empty_edges(self):
        """无边的模板"""
        template = save_template(
            name="无边模板",
            nodes=self._sample_nodes(),
            edges=[],
        )
        assert template["edges"] == []
        loaded = get_template(template["template_id"])
        assert loaded["edges"] == []

    def test_update_template_success(self):
        """更新模板成功"""
        template = save_template(
            name="原始名称",
            nodes=self._sample_nodes(),
            edges=self._sample_edges(),
            description="原始描述",
            goal_hint="原始目标",
        )
        tid = template["template_id"]

        new_nodes = [
            {"id": "research", "agent_id": "research", "task_type": "research_brief", "title": "新调研", "prompt": "新调研内容"},
            {"id": "marketing", "agent_id": "marketing", "task_type": "copywriting", "title": "新营销", "prompt": "新营销内容"},
            {"id": "image", "agent_id": "image", "task_type": "image_prompt", "title": "视觉", "prompt": "视觉内容"},
        ]
        new_edges = [
            {"from_node": "research", "to_node": "marketing", "handoff_type": "context"},
            {"from_node": "research", "to_node": "image", "handoff_type": "context"},
        ]

        updated = update_template(
            template_id=tid,
            name="更新后的名称",
            nodes=new_nodes,
            edges=new_edges,
            description="更新后的描述",
            goal_hint="更新后的目标",
        )

        assert updated is not None
        assert updated["template_id"] == tid
        assert updated["name"] == "更新后的名称"
        assert updated["description"] == "更新后的描述"
        assert updated["goal_hint"] == "更新后的目标"
        assert len(updated["nodes"]) == 3
        assert len(updated["edges"]) == 2

        # 读取验证
        loaded = get_template(tid)
        assert loaded is not None
        assert loaded["name"] == "更新后的名称"
        assert len(loaded["nodes"]) == 3

    def test_update_preserves_created_at(self):
        """更新保留 created_at，更新 updated_at"""
        template = save_template(
            name="时间测试",
            nodes=self._sample_nodes(),
            edges=[],
        )
        tid = template["template_id"]
        original_created = template["created_at"]
        original_updated = template["updated_at"]

        import time
        time.sleep(0.01)

        updated = update_template(
            template_id=tid,
            name="时间测试更新",
            nodes=self._sample_nodes(),
            edges=[],
        )

        assert updated is not None
        assert updated["created_at"] == original_created
        assert updated["updated_at"] != original_updated

    def test_update_nonexistent_returns_none(self):
        """更新不存在的模板返回 None"""
        result = update_template(
            template_id="tpl_nonexistent",
            name="不存在",
            nodes=self._sample_nodes(),
            edges=[],
        )
        assert result is None

    def test_update_invalid_template_id_returns_none(self):
        """非法 template_id 返回 None"""
        result = update_template(
            template_id="../evil",
            name="邪恶",
            nodes=self._sample_nodes(),
            edges=[],
        )
        assert result is None

    # ── Phase 6.6: Version History 测试 ─────────────────────

    def test_update_creates_version_snapshot(self):
        """更新模板时自动保存旧版本快照"""
        template = save_template(
            name="原始名称",
            nodes=self._sample_nodes(),
            edges=self._sample_edges(),
        )
        tid = template["template_id"]

        update_template(
            template_id=tid,
            name="更新后名称",
            nodes=self._sample_nodes(),
            edges=self._sample_edges(),
        )

        versions = list_versions(tid)
        assert len(versions) == 1
        assert versions[0]["name"] == "原始名称"
        assert versions[0]["template_id"] == tid

    def test_version_id_format(self):
        """版本 ID 符合 ver_ 格式"""
        template = save_template(
            name="版本ID测试",
            nodes=self._sample_nodes(),
            edges=[],
        )
        update_template(
            template_id=template["template_id"],
            name="更新",
            nodes=self._sample_nodes(),
            edges=[],
        )
        versions = list_versions(template["template_id"])
        assert len(versions) == 1
        assert versions[0]["version_id"].startswith("ver_")
        import re
        assert re.fullmatch(r"ver_[0-9a-f]{12}", versions[0]["version_id"])

    def test_version_file_content(self):
        """版本文件包含所有必需字段"""
        template = save_template(
            name="内容测试",
            nodes=self._sample_nodes(),
            edges=self._sample_edges(),
            description="描述",
            goal_hint="目标",
        )
        update_template(
            template_id=template["template_id"],
            name="更新",
            nodes=self._sample_nodes(),
            edges=[],
        )
        versions = list_versions(template["template_id"])
        vid = versions[0]["version_id"]
        version = get_version(template["template_id"], vid)

        assert version is not None
        assert version["version_id"] == vid
        assert version["template_id"] == template["template_id"]
        assert "created_at" in version
        assert version["name"] == "内容测试"
        assert version["description"] == "描述"
        assert version["goal_hint"] == "目标"
        assert len(version["nodes"]) == 2
        assert len(version["edges"]) == 1

    def test_list_versions(self):
        """多次更新后列出版本，按 created_at 降序"""
        template = save_template(
            name="V1",
            nodes=self._sample_nodes(),
            edges=[],
        )
        tid = template["template_id"]

        import time
        for i in range(3):
            time.sleep(0.01)
            update_template(
                template_id=tid,
                name=f"V{i + 2}",
                nodes=self._sample_nodes(),
                edges=[],
            )

        versions = list_versions(tid)
        assert len(versions) == 3
        # 降序：最新的在前（版本快照保存的是更新前的状态）
        assert versions[0]["name"] == "V3"
        assert versions[1]["name"] == "V2"
        assert versions[2]["name"] == "V1"

    def test_list_versions_empty(self):
        """未更新过的模板版本列表为空"""
        template = save_template(
            name="无版本",
            nodes=self._sample_nodes(),
            edges=[],
        )
        versions_dir = self.versions_dir / template["template_id"]
        assert not versions_dir.exists()
        assert list_versions(template["template_id"]) == []
        assert not versions_dir.exists()

    def test_get_version(self):
        """可按 ID 获取特定版本"""
        template = save_template(
            name="原始",
            nodes=self._sample_nodes(),
            edges=[],
        )
        tid = template["template_id"]
        update_template(
            template_id=tid,
            name="更新",
            nodes=self._sample_nodes(),
            edges=[],
        )
        versions = list_versions(tid)
        vid = versions[0]["version_id"]

        version = get_version(tid, vid)
        assert version is not None
        assert version["version_id"] == vid
        assert version["name"] == "原始"

    def test_get_nonexistent_version_returns_none(self):
        """不存在的版本返回 None"""
        template = save_template(
            name="测试",
            nodes=self._sample_nodes(),
            edges=[],
        )
        assert get_version(template["template_id"], "ver_nonexistent") is None

    def test_max_version_trim(self):
        """超过 20 个版本时裁剪最旧的"""
        template = save_template(
            name="裁剪测试",
            nodes=self._sample_nodes(),
            edges=[],
        )
        tid = template["template_id"]

        import time
        for i in range(25):
            time.sleep(0.01)
            update_template(
                template_id=tid,
                name=f"V{i + 2}",
                nodes=self._sample_nodes(),
                edges=[],
            )

        versions = list_versions(tid)
        assert len(versions) == 20
        assert versions[0]["name"] == "V25"
        assert versions[-1]["name"] == "V6"

    def test_delete_template_cleans_up_versions(self):
        """删除模板时同步清理版本目录"""
        template = save_template(
            name="待删除",
            nodes=self._sample_nodes(),
            edges=[],
        )
        tid = template["template_id"]
        update_template(
            template_id=tid,
            name="更新",
            nodes=self._sample_nodes(),
            edges=[],
        )

        # 确认版本存在
        assert len(list_versions(tid)) == 1

        # 删除模板
        delete_template(tid)

        # 版本目录应不存在
        versions_dir = self.versions_dir / tid
        assert not versions_dir.exists()

    def test_version_immutable(self):
        """版本快照内容不会随后续更新而改变"""
        template = save_template(
            name="不可变测试",
            nodes=self._sample_nodes(),
            edges=[],
        )
        tid = template["template_id"]

        update_template(
            template_id=tid,
            name="更新1",
            nodes=self._sample_nodes(),
            edges=[],
        )
        versions1 = list_versions(tid)
        vid = versions1[0]["version_id"]
        version_before = get_version(tid, vid)

        update_template(
            template_id=tid,
            name="更新2",
            nodes=self._sample_nodes(),
            edges=[],
        )
        version_after = get_version(tid, vid)

        # 版本内容不应改变
        assert version_before["name"] == version_after["name"] == "不可变测试"

    # ── Phase 6.7: Version Metadata & Compare 测试 ──────────

    def test_version_snapshot_has_label_note(self):
        """版本快照包含 label/note 字段"""
        template = save_template(
            name="元数据测试",
            nodes=self._sample_nodes(),
            edges=[],
        )
        tid = template["template_id"]
        update_template(template_id=tid, name="更新", nodes=self._sample_nodes(), edges=[])
        versions = list_versions(tid)
        vid = versions[0]["version_id"]
        version = get_version(tid, vid)
        assert "label" in version
        assert "note" in version
        assert version["label"] == ""
        assert version["note"] == ""

    def test_list_versions_includes_label_note(self):
        """list_versions 摘要包含 label/note"""
        template = save_template(
            name="摘要测试",
            nodes=self._sample_nodes(),
            edges=[],
        )
        tid = template["template_id"]
        update_template(template_id=tid, name="更新", nodes=self._sample_nodes(), edges=[])
        versions = list_versions(tid)
        assert "label" in versions[0]
        assert "note" in versions[0]

    def test_update_version_metadata_label(self):
        """更新版本 label"""
        from backend.services.graph_template_store import update_version_metadata

        template = save_template(name="label测试", nodes=self._sample_nodes(), edges=[])
        tid = template["template_id"]
        update_template(template_id=tid, name="更新", nodes=self._sample_nodes(), edges=[])
        vid = list_versions(tid)[0]["version_id"]

        result = update_version_metadata(tid, vid, label="发布前备份")
        assert result is not None
        assert result["label"] == "发布前备份"
        # 验证持久化
        version = get_version(tid, vid)
        assert version["label"] == "发布前备份"

    def test_update_version_metadata_note(self):
        """更新版本 note"""
        from backend.services.graph_template_store import update_version_metadata

        template = save_template(name="note测试", nodes=self._sample_nodes(), edges=[])
        tid = template["template_id"]
        update_template(template_id=tid, name="更新", nodes=self._sample_nodes(), edges=[])
        vid = list_versions(tid)[0]["version_id"]

        result = update_version_metadata(tid, vid, note="修复了调研 prompt")
        assert result is not None
        assert result["note"] == "修复了调研 prompt"

    def test_update_version_metadata_label_too_long(self):
        """label 超长抛 ValueError"""
        from backend.services.graph_template_store import update_version_metadata

        template = save_template(name="超长测试", nodes=self._sample_nodes(), edges=[])
        tid = template["template_id"]
        update_template(template_id=tid, name="更新", nodes=self._sample_nodes(), edges=[])
        vid = list_versions(tid)[0]["version_id"]

        with pytest.raises(ValueError, match="label"):
            update_version_metadata(tid, vid, label="x" * 101)

    def test_update_version_metadata_note_too_long(self):
        """note 超长抛 ValueError"""
        from backend.services.graph_template_store import update_version_metadata

        template = save_template(name="超长测试", nodes=self._sample_nodes(), edges=[])
        tid = template["template_id"]
        update_template(template_id=tid, name="更新", nodes=self._sample_nodes(), edges=[])
        vid = list_versions(tid)[0]["version_id"]

        with pytest.raises(ValueError, match="note"):
            update_version_metadata(tid, vid, note="x" * 501)

    def test_update_version_metadata_nonexistent(self):
        """不存在的版本返回 None"""
        from backend.services.graph_template_store import update_version_metadata

        template = save_template(name="不存在测试", nodes=self._sample_nodes(), edges=[])
        tid = template["template_id"]

        result = update_version_metadata(tid, "ver_nonexistent", label="x")
        assert result is None

    def test_update_version_metadata_no_snapshot_change(self):
        """元数据更新不改变快照内容"""
        from backend.services.graph_template_store import update_version_metadata

        template = save_template(name="不可变测试", nodes=self._sample_nodes(), edges=[])
        tid = template["template_id"]
        update_template(template_id=tid, name="更新", nodes=self._sample_nodes(), edges=[])
        vid = list_versions(tid)[0]["version_id"]

        version_before = get_version(tid, vid)
        update_version_metadata(tid, vid, label="新标签", note="新备注")
        version_after = get_version(tid, vid)

        # 快照内容不变
        assert version_before["name"] == version_after["name"]
        assert version_before["nodes"] == version_after["nodes"]
        assert version_before["edges"] == version_after["edges"]
        # 元数据变了
        assert version_after["label"] == "新标签"
        assert version_after["note"] == "新备注"

    def test_compare_versions_no_changes(self):
        """对比两个相同版本返回空 diff"""
        from backend.services.graph_template_store import compare_versions

        template = save_template(name="对比测试", nodes=self._sample_nodes(), edges=[])
        tid = template["template_id"]
        update_template(template_id=tid, name="更新", nodes=self._sample_nodes(), edges=[])
        vid = list_versions(tid)[0]["version_id"]

        diff = compare_versions(tid, vid, vid)
        # 同版本对比会抛 HTTP 400，但 store 层返回空 diff
        # 实际上 store 层不检查同版本，直接返回结果
        assert diff is not None
        assert diff["field_changes"] == []
        assert diff["nodes"]["added"] == []
        assert diff["nodes"]["removed"] == []

    def test_compare_versions_field_changes(self):
        """对比版本检测基础字段变化"""
        from backend.services.graph_template_store import compare_versions

        template = save_template(name="V1名称", nodes=self._sample_nodes(), edges=[], description="V1描述")
        tid = template["template_id"]
        update_template(template_id=tid, name="V2名称", nodes=self._sample_nodes(), edges=[], description="V2描述")
        vid = list_versions(tid)[0]["version_id"]

        diff = compare_versions(tid, vid, "current")
        assert diff is not None
        fields = {c["field"]: c for c in diff["field_changes"]}
        assert "name" in fields
        assert fields["name"]["from"] == "V1名称"
        assert fields["name"]["to"] == "V2名称"
        assert "description" in fields

    def test_compare_versions_node_changes(self):
        """对比版本检测节点增删改"""
        from backend.services.graph_template_store import compare_versions

        template = save_template(
            name="节点测试",
            nodes=self._sample_nodes(),
            edges=self._sample_edges(),
        )
        tid = template["template_id"]

        # 更新：修改一个节点，删除一个节点，新增一个节点
        new_nodes = [
            {"id": "research", "agent_id": "research", "task_type": "research_brief", "title": "调研v2", "prompt": "新调研"},
            {"id": "data", "agent_id": "data", "task_type": "analysis", "title": "数据", "prompt": "分析数据"},
        ]
        update_template(template_id=tid, name="节点测试", nodes=new_nodes, edges=[])
        vid = list_versions(tid)[0]["version_id"]

        diff = compare_versions(tid, vid, "current")
        assert diff is not None
        assert len(diff["nodes"]["added"]) == 1
        assert diff["nodes"]["added"][0]["id"] == "data"
        assert len(diff["nodes"]["removed"]) == 1
        assert diff["nodes"]["removed"][0]["id"] == "marketing"
        assert len(diff["nodes"]["modified"]) == 1
        assert diff["nodes"]["modified"][0]["id"] == "research"

    def test_compare_versions_edge_changes(self):
        """对比版本检测边增删"""
        from backend.services.graph_template_store import compare_versions

        template = save_template(
            name="边测试",
            nodes=self._sample_nodes(),
            edges=self._sample_edges(),
        )
        tid = template["template_id"]

        # 更新：删除旧边，新增新边
        new_edges = [{"from_node": "marketing", "to_node": "research", "handoff_type": "feedback"}]
        update_template(template_id=tid, name="边测试", nodes=self._sample_nodes(), edges=new_edges)
        vid = list_versions(tid)[0]["version_id"]

        diff = compare_versions(tid, vid, "current")
        assert diff is not None
        assert len(diff["edges"]["added"]) == 1
        assert diff["edges"]["added"][0]["from_node"] == "marketing"
        assert len(diff["edges"]["removed"]) == 1
        assert diff["edges"]["removed"][0]["from_node"] == "research"

    def test_compare_versions_parallel_edges(self):
        """同端点多条边不会在对比时被字典覆盖"""
        from backend.services.graph_template_store import compare_versions

        old_edges = [
            {"from_node": "research", "to_node": "marketing", "handoff_type": "context"},
            {"from_node": "research", "to_node": "marketing", "handoff_type": "brief"},
        ]
        new_edges = [
            {"from_node": "research", "to_node": "marketing", "handoff_type": "context"},
            {"from_node": "research", "to_node": "marketing", "handoff_type": "review"},
        ]
        template = save_template(
            name="并行边",
            nodes=self._sample_nodes(),
            edges=old_edges,
        )
        tid = template["template_id"]
        update_template(
            template_id=tid,
            name="并行边",
            nodes=self._sample_nodes(),
            edges=new_edges,
        )
        vid = list_versions(tid)[0]["version_id"]

        diff = compare_versions(tid, vid, "current")
        assert diff is not None
        assert len(diff["edges"]["modified"]) == 1
        assert diff["edges"]["added"] == []
        assert diff["edges"]["removed"] == []

    def test_compare_versions_vs_current(self):
        """对比版本 vs current"""
        from backend.services.graph_template_store import compare_versions

        template = save_template(name="原始", nodes=self._sample_nodes(), edges=[])
        tid = template["template_id"]
        update_template(template_id=tid, name="当前", nodes=self._sample_nodes(), edges=[])
        vid = list_versions(tid)[0]["version_id"]

        diff = compare_versions(tid, vid, "current")
        assert diff is not None
        assert diff["from_version"] == vid
        assert diff["to_version"] == "current"
        fields = {c["field"]: c for c in diff["field_changes"]}
        assert fields["name"]["from"] == "原始"
        assert fields["name"]["to"] == "当前"

    def test_compare_versions_nonexistent_from(self):
        """不存在的起始版本返回 None"""
        from backend.services.graph_template_store import compare_versions

        template = save_template(name="测试", nodes=self._sample_nodes(), edges=[])
        tid = template["template_id"]

        diff = compare_versions(tid, "ver_nonexistent", "current")
        assert diff is None

    def test_compare_versions_nonexistent_to(self):
        """不存在的目标版本返回 None"""
        from backend.services.graph_template_store import compare_versions

        template = save_template(name="测试", nodes=self._sample_nodes(), edges=[])
        tid = template["template_id"]
        update_template(template_id=tid, name="更新", nodes=self._sample_nodes(), edges=[])
        vid = list_versions(tid)[0]["version_id"]

        diff = compare_versions(tid, vid, "ver_nonexistent")
        assert diff is None

    # ── Phase 6.11: Canvas Layout 测试 ──────────────────────────

    def test_save_template_with_canvas_layout(self):
        """save_template 保存 canvas_layout"""
        layout = {"research": {"x": 100, "y": 200}, "marketing": {"x": 300, "y": 200}}
        template = save_template(
            name="布局测试",
            nodes=self._sample_nodes(),
            edges=self._sample_edges(),
            canvas_layout=layout,
        )
        assert template["canvas_layout"] == layout
        # 读回来也一致
        loaded = get_template(template["template_id"])
        assert loaded["canvas_layout"] == layout

    def test_save_template_without_canvas_layout(self):
        """save_template 不传 canvas_layout 时字段不存在"""
        template = save_template(
            name="无布局测试",
            nodes=self._sample_nodes(),
            edges=self._sample_edges(),
        )
        assert "canvas_layout" not in template

    def test_update_template_preserves_canvas_layout(self):
        """update_template 不传 canvas_layout 时保留旧值"""
        layout = {"research": {"x": 10, "y": 20}}
        template = save_template(
            name="保留布局",
            nodes=self._sample_nodes(),
            edges=self._sample_edges(),
            canvas_layout=layout,
        )
        tid = template["template_id"]
        # 更新时不传 canvas_layout
        updated = update_template(
            template_id=tid,
            name="保留布局-更新",
            nodes=self._sample_nodes(),
            edges=self._sample_edges(),
        )
        assert updated["canvas_layout"] == layout

    def test_update_template_overwrites_canvas_layout(self):
        """update_template 传入新 canvas_layout 时覆盖"""
        old_layout = {"research": {"x": 10, "y": 20}}
        template = save_template(
            name="覆盖布局",
            nodes=self._sample_nodes(),
            edges=self._sample_edges(),
            canvas_layout=old_layout,
        )
        tid = template["template_id"]
        new_layout = {"research": {"x": 999, "y": 888}}
        updated = update_template(
            template_id=tid,
            name="覆盖布局-更新",
            nodes=self._sample_nodes(),
            edges=self._sample_edges(),
            canvas_layout=new_layout,
        )
        assert updated["canvas_layout"] == new_layout

    def test_update_canvas_layout(self):
        """update_canvas_layout 仅更新布局字段"""
        from backend.services.graph_template_store import update_canvas_layout
        template = save_template(
            name="专用布局更新",
            nodes=self._sample_nodes(),
            edges=self._sample_edges(),
        )
        tid = template["template_id"]
        layout = {"research": {"x": 50, "y": 60}, "marketing": {"x": 250, "y": 60}}
        updated = update_canvas_layout(tid, layout)
        assert updated is not None
        assert updated["canvas_layout"] == layout
        # 名称等字段不变
        assert updated["name"] == "专用布局更新"

    def test_update_canvas_layout_nonexistent(self):
        """update_canvas_layout 对不存在的模板返回 None"""
        from backend.services.graph_template_store import update_canvas_layout
        result = update_canvas_layout("tpl_nonexistent", {"a": {"x": 0, "y": 0}})
        assert result is None

    def test_update_canvas_layout_does_not_create_version(self):
        """update_canvas_layout 不创建版本快照"""
        from backend.services.graph_template_store import update_canvas_layout
        template = save_template(
            name="布局无版本",
            nodes=self._sample_nodes(),
            edges=self._sample_edges(),
        )
        tid = template["template_id"]
        update_canvas_layout(tid, {"research": {"x": 1, "y": 2}})
        versions = list_versions(tid)
        assert len(versions) == 0

    def test_canvas_layout_not_in_version_snapshot(self):
        """版本快照不包含 canvas_layout（布局是 per-template，不是 per-version）"""
        layout = {"research": {"x": 100, "y": 200}}
        template = save_template(
            name="版本不含布局",
            nodes=self._sample_nodes(),
            edges=self._sample_edges(),
            canvas_layout=layout,
        )
        tid = template["template_id"]
        # 触发版本快照
        update_template(
            template_id=tid,
            name="版本不含布局-更新",
            nodes=self._sample_nodes(),
            edges=[],
        )
        versions = list_versions(tid)
        assert len(versions) == 1
        # 快照中不含 canvas_layout（save_version_snapshot 不复制该字段）
        version = get_version(tid, versions[0]["version_id"])
        assert "canvas_layout" not in version

    def test_update_canvas_layout_sanitizes_nan_inf(self):
        """update_canvas_layout 过滤 NaN 和 Infinity 值"""
        template = save_template(
            name="NaN过滤",
            nodes=self._sample_nodes(),
            edges=self._sample_edges(),
        )
        tid = template["template_id"]
        bad_layout = {
            "research": {"x": float("nan"), "y": 100},
            "marketing": {"x": 200, "y": float("inf")},
            "cto": {"x": 300, "y": 400},
        }
        updated = update_canvas_layout(tid, bad_layout)
        assert updated is not None
        # NaN/Infinity entries should be filtered out
        assert "research" not in updated["canvas_layout"]
        assert "marketing" not in updated["canvas_layout"]
        # Valid entry should survive
        assert updated["canvas_layout"]["cto"] == {"x": 300.0, "y": 400.0}

    def test_update_canvas_layout_clears_with_empty_dict(self):
        """update_canvas_layout 传空字典清除布局"""
        layout = {"research": {"x": 100, "y": 200}}
        template = save_template(
            name="清除布局",
            nodes=self._sample_nodes(),
            edges=self._sample_edges(),
            canvas_layout=layout,
        )
        tid = template["template_id"]
        updated = update_canvas_layout(tid, {})
        assert updated is not None
        assert updated["canvas_layout"] == {}
        # 读回来也是空
        loaded = get_template(tid)
        assert loaded["canvas_layout"] == {}


# ── API 集成测试 ──────────────────────────────────────────────


def _bypass_governance(payload, platform=None):
    from backend.governance.classifier import ClassificationResult
    return False, ClassificationResult(ok=True, confidence=1.0, reason="test bypass")


def _bypass_rate_limit(name, max_requests=5, window_seconds=60):
    return True, ""


def _mock_execute_agent(agent_id, task):
    mock_result = MagicMock()
    mock_result.ok = True
    mock_result.summary = f"{agent_id} 执行完成"
    mock_result.structured_output = {"summary": f"{agent_id} 摘要", "key_findings": []}
    mock_result.warnings = []
    mock_result.errors = []
    mock_result.error = None
    mock_result.model_dump.return_value = {
        "ok": True,
        "agent_id": agent_id,
        "summary": f"{agent_id} 执行完成",
        "structured_output": {"summary": f"{agent_id} 摘要", "key_findings": []},
        "warnings": [],
        "errors": [],
        "error": None,
    }
    return mock_result


def _sample_api_nodes():
    return [
        {"id": "research", "agent_id": "research", "task_type": "research_brief", "title": "调研", "prompt": "做调研"},
        {"id": "marketing", "agent_id": "marketing", "task_type": "copywriting", "title": "营销", "prompt": "做营销"},
    ]


def _sample_api_edges():
    return [{"from_node": "research", "to_node": "marketing", "handoff_type": "context"}]


class TestGraphTemplateAudit:
    """Graph Template Audit Log 单元测试"""

    @pytest.fixture(autouse=True)
    def setup_tmp_dir(self, tmp_path, monkeypatch):
        self.audit_dir = tmp_path / "audit"
        self.audit_dir.mkdir()
        monkeypatch.setattr(
            "backend.services.graph_template_audit.DEFAULT_AUDIT_DIR",
            self.audit_dir,
        )

    def test_append_and_list_events(self):
        """追加事件并读取"""
        from backend.services.graph_template_audit import append_event, list_events

        append_event("tpl_test12345678", "create", "创建模板", {"name": "测试"})
        append_event("tpl_test12345678", "update", "更新模板", {"name": "测试v2"})

        events = list_events("tpl_test12345678")
        assert len(events) == 2
        assert events[0]["event_type"] == "create"
        assert events[1]["event_type"] == "update"

    def test_filter_by_event_type(self):
        """按事件类型过滤"""
        from backend.services.graph_template_audit import append_event, list_events

        append_event("tpl_test12345678", "create", "创建", {})
        append_event("tpl_test12345678", "update", "更新", {})
        append_event("tpl_test12345678", "create", "创建2", {})

        create_events = list_events("tpl_test12345678", event_type="create")
        assert len(create_events) == 2
        assert all(e["event_type"] == "create" for e in create_events)

    def test_event_id_format(self):
        """事件 ID 符合 aevt_ 格式"""
        from backend.services.graph_template_audit import append_event, list_events

        append_event("tpl_test12345678", "create", "测试", {})
        events = list_events("tpl_test12345678")
        assert events[0]["event_id"].startswith("aevt_")

    def test_sensitive_data_stripped(self):
        """敏感字段被脱敏"""
        from backend.services.graph_template_audit import append_event, list_events

        append_event("tpl_test12345678", "create", "测试", {
            "api_key": "sk-secret",
            "token": "bearer-xxx",
            "name": "正常数据",
        })
        events = list_events("tpl_test12345678")
        details = events[0]["details"]
        assert "api_key" not in details
        assert "token" not in details
        assert details["name"] == "正常数据"

    def test_long_text_truncated(self):
        """长文本被截断"""
        from backend.services.graph_template_audit import append_event, list_events

        long_text = "x" * 500
        append_event("tpl_test12345678", "execute", "执行", {"goal": long_text})
        events = list_events("tpl_test12345678")
        assert len(events[0]["details"]["goal"]) < 300
        assert events[0]["details"]["goal"].endswith("...")

    def test_list_events_empty(self):
        """无事件返回空列表"""
        from backend.services.graph_template_audit import list_events

        events = list_events("tpl_nonexistent123")
        assert events == []

    def test_list_events_limit(self):
        """限制返回条数"""
        from backend.services.graph_template_audit import append_event, list_events

        for i in range(10):
            append_event("tpl_test12345678", "execute", f"执行{i}", {})

        events = list_events("tpl_test12345678", limit=3)
        assert len(events) == 3

    def test_invalid_event_type_raises(self):
        """无效事件类型抛 ValueError"""
        from backend.services.graph_template_audit import append_event

        with pytest.raises(ValueError, match="无效的事件类型"):
            append_event("tpl_test12345678", "bad_type", "测试", {})

    def test_delete_audit_for_template(self):
        """删除模板审计日志"""
        from backend.services.graph_template_audit import append_event, list_events, delete_audit_for_template

        append_event("tpl_test12345678", "create", "测试", {})
        assert len(list_events("tpl_test12345678")) == 1

        delete_audit_for_template("tpl_test12345678")
        assert len(list_events("tpl_test12345678")) == 0

    def test_atomic_write(self):
        """写入后文件完整（单行 JSONL）"""
        from backend.services.graph_template_audit import append_event
        import json as json_mod

        append_event("tpl_test12345678", "create", "测试", {})
        path = self.audit_dir / "tpl_test12345678.jsonl"
        assert path.exists()

        lines = path.read_text(encoding="utf-8").strip().split("\n")
        assert len(lines) == 1
        # 每行都是合法 JSON
        data = json_mod.loads(lines[0])
        assert data["event_type"] == "create"


class TestGraphTemplateAPI:
    """Graph Template API 集成测试"""

    @pytest.fixture(autouse=True)
    def setup_tmp_dir(self, tmp_path, monkeypatch):
        """每个测试使用独立的临时目录"""
        self.tmp_dir = tmp_path / "graph_templates"
        self.tmp_dir.mkdir()
        monkeypatch.setattr(
            "backend.services.graph_template_store.DEFAULT_TEMPLATES_DIR",
            self.tmp_dir,
        )
        # Phase 6.6: 版本目录也需要隔离
        self.versions_dir = tmp_path / "graph_template_versions"
        self.versions_dir.mkdir()
        monkeypatch.setattr(
            "backend.services.graph_template_store.DEFAULT_VERSIONS_DIR",
            self.versions_dir,
        )
        # Phase 6.8: API 调用会写审计日志，也必须隔离到临时目录
        self.audit_dir = tmp_path / "graph_template_audit"
        self.audit_dir.mkdir()
        monkeypatch.setattr(
            "backend.services.graph_template_audit.DEFAULT_AUDIT_DIR",
            self.audit_dir,
        )

    @patch("backend.security.rate_limiter.check", side_effect=_bypass_rate_limit)
    @patch("backend.governance.scope_classifier.guard_payload", side_effect=_bypass_governance)
    def test_create_template_success(self, mock_guard, mock_rate):
        """创建模板成功"""
        from fastapi.testclient import TestClient
        from backend.app import app

        client = TestClient(app)
        response = client.post("/boss/graph/templates", json={
            "name": "新品上线协作图",
            "description": "research → marketing",
            "goal_hint": "为品牌做新品上线",
            "nodes": _sample_api_nodes(),
            "edges": _sample_api_edges(),
        })

        assert response.status_code == 200
        data = response.json()
        assert data["ok"] is True
        assert data["template"]["name"] == "新品上线协作图"
        assert data["template"]["template_id"].startswith("tpl_")
        assert len(data["template"]["nodes"]) == 2
        assert len(data["template"]["edges"]) == 1

    @patch("backend.security.rate_limiter.check", side_effect=_bypass_rate_limit)
    @patch("backend.governance.scope_classifier.guard_payload", side_effect=_bypass_governance)
    def test_create_template_invalid_graph_400(self, mock_guard, mock_rate):
        """无效图（缺失节点引用）返回 400"""
        from fastapi.testclient import TestClient
        from backend.app import app

        client = TestClient(app)
        response = client.post("/boss/graph/templates", json={
            "name": "无效图模板",
            "nodes": [
                {"id": "a", "agent_id": "research", "title": "A", "prompt": "p"},
            ],
            "edges": [
                {"from_node": "a", "to_node": "x"},  # x 不存在
            ],
        })

        assert response.status_code == 400

    @patch("backend.security.rate_limiter.check", side_effect=_bypass_rate_limit)
    @patch("backend.governance.scope_classifier.guard_payload", side_effect=_bypass_governance)
    def test_create_template_self_loop_400(self, mock_guard, mock_rate):
        """自环返回 400"""
        from fastapi.testclient import TestClient
        from backend.app import app

        client = TestClient(app)
        response = client.post("/boss/graph/templates", json={
            "name": "自环模板",
            "nodes": [
                {"id": "a", "agent_id": "research", "title": "A", "prompt": "p"},
            ],
            "edges": [
                {"from_node": "a", "to_node": "a"},
            ],
        })

        assert response.status_code == 400

    @patch("backend.security.rate_limiter.check", side_effect=_bypass_rate_limit)
    @patch("backend.governance.scope_classifier.guard_payload", side_effect=_bypass_governance)
    def test_list_templates(self, mock_guard, mock_rate):
        """列出模板"""
        from fastapi.testclient import TestClient
        from backend.app import app

        client = TestClient(app)

        # 先创建 2 个模板
        for i in range(2):
            client.post("/boss/graph/templates", json={
                "name": f"模板 {i}",
                "nodes": _sample_api_nodes(),
            })

        response = client.get("/boss/graph/templates")
        assert response.status_code == 200
        data = response.json()
        assert data["ok"] is True
        assert data["total"] == 2
        assert len(data["templates"]) == 2

    @patch("backend.security.rate_limiter.check", side_effect=_bypass_rate_limit)
    @patch("backend.governance.scope_classifier.guard_payload", side_effect=_bypass_governance)
    def test_get_single_template(self, mock_guard, mock_rate):
        """获取单个模板"""
        from fastapi.testclient import TestClient
        from backend.app import app

        client = TestClient(app)

        # 创建
        create_resp = client.post("/boss/graph/templates", json={
            "name": "获取测试",
            "nodes": _sample_api_nodes(),
        })
        tid = create_resp.json()["template"]["template_id"]

        # 获取
        response = client.get(f"/boss/graph/templates/{tid}")
        assert response.status_code == 200
        data = response.json()
        assert data["ok"] is True
        assert data["template"]["template_id"] == tid

    @patch("backend.security.rate_limiter.check", side_effect=_bypass_rate_limit)
    @patch("backend.governance.scope_classifier.guard_payload", side_effect=_bypass_governance)
    def test_get_nonexistent_template_404(self, mock_guard, mock_rate):
        """不存在的模板返回 404"""
        from fastapi.testclient import TestClient
        from backend.app import app

        client = TestClient(app)
        response = client.get("/boss/graph/templates/tpl_nonexistent")
        assert response.status_code == 404

    @patch("backend.security.rate_limiter.check", side_effect=_bypass_rate_limit)
    @patch("backend.governance.scope_classifier.guard_payload", side_effect=_bypass_governance)
    def test_delete_template(self, mock_guard, mock_rate):
        """删除模板"""
        from fastapi.testclient import TestClient
        from backend.app import app

        client = TestClient(app)

        # 创建
        create_resp = client.post("/boss/graph/templates", json={
            "name": "待删除",
            "nodes": _sample_api_nodes(),
        })
        tid = create_resp.json()["template"]["template_id"]

        # 删除
        response = client.delete(f"/boss/graph/templates/{tid}")
        assert response.status_code == 200
        data = response.json()
        assert data["ok"] is True
        assert data["deleted"] is True
        assert data["template_id"] == tid

        # 确认不存在
        get_resp = client.get(f"/boss/graph/templates/{tid}")
        assert get_resp.status_code == 404

    @patch("backend.security.rate_limiter.check", side_effect=_bypass_rate_limit)
    @patch("backend.governance.scope_classifier.guard_payload", side_effect=_bypass_governance)
    def test_delete_nonexistent_template_404(self, mock_guard, mock_rate):
        """删除不存在的模板返回 404"""
        from fastapi.testclient import TestClient
        from backend.app import app

        client = TestClient(app)
        response = client.delete("/boss/graph/templates/tpl_nonexistent")
        assert response.status_code == 404

    @patch("backend.security.rate_limiter.check", side_effect=_bypass_rate_limit)
    @patch("backend.governance.scope_classifier.guard_payload", side_effect=_bypass_governance)
    @patch("backend.services.agent_executor.execute_agent", side_effect=_mock_execute_agent)
    def test_execute_template(self, mock_exec, mock_guard, mock_rate):
        """按模板执行"""
        from fastapi.testclient import TestClient
        from backend.app import app

        client = TestClient(app)

        # 创建模板
        create_resp = client.post("/boss/graph/templates", json={
            "name": "执行测试",
            "nodes": _sample_api_nodes(),
            "edges": _sample_api_edges(),
        })
        tid = create_resp.json()["template"]["template_id"]

        # 按模板执行
        response = client.post(f"/boss/graph/templates/{tid}/execute", json={
            "goal": "为手工银饰做新品上线",
            "save_to_delivery": False,
        })

        assert response.status_code == 200
        data = response.json()
        assert data["ok"] is True
        assert data["execution_mode"] == "custom_graph"
        assert len(data["results"]) == 2

    @patch("backend.security.rate_limiter.check", side_effect=_bypass_rate_limit)
    @patch("backend.governance.scope_classifier.guard_payload", side_effect=_bypass_governance)
    def test_execute_nonexistent_template_404(self, mock_guard, mock_rate):
        """执行不存在的模板返回 404"""
        from fastapi.testclient import TestClient
        from backend.app import app

        client = TestClient(app)
        response = client.post("/boss/graph/templates/tpl_nonexistent/execute", json={
            "goal": "测试目标",
        })
        assert response.status_code == 404

    @patch("backend.security.rate_limiter.check", side_effect=_bypass_rate_limit)
    @patch("backend.governance.scope_classifier.guard_payload", side_effect=_bypass_governance)
    def test_update_template_success(self, mock_guard, mock_rate):
        """PUT 更新模板成功"""
        from fastapi.testclient import TestClient
        from backend.app import app

        client = TestClient(app)

        # 创建
        create_resp = client.post("/boss/graph/templates", json={
            "name": "待更新",
            "nodes": _sample_api_nodes(),
            "edges": _sample_api_edges(),
        })
        tid = create_resp.json()["template"]["template_id"]

        # 更新
        new_nodes = [
            {"id": "research", "agent_id": "research", "task_type": "research_brief", "title": "新调研", "prompt": "新内容"},
            {"id": "marketing", "agent_id": "marketing", "task_type": "copywriting", "title": "新营销", "prompt": "新营销"},
            {"id": "image", "agent_id": "image", "task_type": "image_prompt", "title": "视觉", "prompt": "视觉内容"},
        ]
        new_edges = [
            {"from_node": "research", "to_node": "marketing", "handoff_type": "context"},
            {"from_node": "research", "to_node": "image", "handoff_type": "context"},
        ]

        response = client.put(f"/boss/graph/templates/{tid}", json={
            "name": "更新后的模板",
            "description": "新描述",
            "goal_hint": "新目标",
            "nodes": new_nodes,
            "edges": new_edges,
        })

        assert response.status_code == 200
        data = response.json()
        assert data["ok"] is True
        assert data["template"]["name"] == "更新后的模板"
        assert data["template"]["description"] == "新描述"
        assert len(data["template"]["nodes"]) == 3
        assert len(data["template"]["edges"]) == 2

    @patch("backend.security.rate_limiter.check", side_effect=_bypass_rate_limit)
    @patch("backend.governance.scope_classifier.guard_payload", side_effect=_bypass_governance)
    def test_update_nonexistent_template_404(self, mock_guard, mock_rate):
        """PUT 不存在的模板返回 404"""
        from fastapi.testclient import TestClient
        from backend.app import app

        client = TestClient(app)
        response = client.put("/boss/graph/templates/tpl_nonexistent", json={
            "name": "不存在",
            "nodes": _sample_api_nodes(),
        })
        assert response.status_code == 404

    @patch("backend.security.rate_limiter.check", side_effect=_bypass_rate_limit)
    @patch("backend.governance.scope_classifier.guard_payload", side_effect=_bypass_governance)
    def test_update_template_invalid_graph_400(self, mock_guard, mock_rate):
        """PUT 无效图返回 400"""
        from fastapi.testclient import TestClient
        from backend.app import app

        client = TestClient(app)

        # 创建
        create_resp = client.post("/boss/graph/templates", json={
            "name": "待更新",
            "nodes": _sample_api_nodes(),
        })
        tid = create_resp.json()["template"]["template_id"]

        # 更新为无效图
        response = client.put(f"/boss/graph/templates/{tid}", json={
            "name": "无效图更新",
            "nodes": [{"id": "a", "agent_id": "research", "title": "A", "prompt": "p"}],
            "edges": [{"from_node": "a", "to_node": "x"}],
        })
        assert response.status_code == 400

    # ── Phase 6.6: Version History API 测试 ─────────────────

    @patch("backend.security.rate_limiter.check", side_effect=_bypass_rate_limit)
    @patch("backend.governance.scope_classifier.guard_payload", side_effect=_bypass_governance)
    def test_list_versions_empty(self, mock_guard, mock_rate):
        """新模板版本列表为空"""
        from fastapi.testclient import TestClient
        from backend.app import app

        client = TestClient(app)

        create_resp = client.post("/boss/graph/templates", json={
            "name": "无版本",
            "nodes": _sample_api_nodes(),
        })
        tid = create_resp.json()["template"]["template_id"]

        response = client.get(f"/boss/graph/templates/{tid}/versions")
        assert response.status_code == 200
        data = response.json()
        assert data["ok"] is True
        assert data["total"] == 0
        assert data["versions"] == []

    @patch("backend.security.rate_limiter.check", side_effect=_bypass_rate_limit)
    @patch("backend.governance.scope_classifier.guard_payload", side_effect=_bypass_governance)
    def test_update_auto_creates_version(self, mock_guard, mock_rate):
        """PUT 更新自动创建版本快照"""
        from fastapi.testclient import TestClient
        from backend.app import app

        client = TestClient(app)

        create_resp = client.post("/boss/graph/templates", json={
            "name": "原始名称",
            "nodes": _sample_api_nodes(),
            "edges": _sample_api_edges(),
        })
        tid = create_resp.json()["template"]["template_id"]

        # 更新
        client.put(f"/boss/graph/templates/{tid}", json={
            "name": "更新后名称",
            "nodes": _sample_api_nodes(),
        })

        # 版本列表应有 1 条
        response = client.get(f"/boss/graph/templates/{tid}/versions")
        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 1
        assert data["versions"][0]["name"] == "原始名称"
        assert data["versions"][0]["node_count"] == 2
        assert data["versions"][0]["edge_count"] == 1

    @patch("backend.security.rate_limiter.check", side_effect=_bypass_rate_limit)
    @patch("backend.governance.scope_classifier.guard_payload", side_effect=_bypass_governance)
    def test_get_version_detail(self, mock_guard, mock_rate):
        """获取版本详情"""
        from fastapi.testclient import TestClient
        from backend.app import app

        client = TestClient(app)

        create_resp = client.post("/boss/graph/templates", json={
            "name": "详情测试",
            "nodes": _sample_api_nodes(),
            "edges": _sample_api_edges(),
        })
        tid = create_resp.json()["template"]["template_id"]

        client.put(f"/boss/graph/templates/{tid}", json={
            "name": "更新后",
            "nodes": _sample_api_nodes(),
        })

        # 获取版本列表
        versions_resp = client.get(f"/boss/graph/templates/{tid}/versions")
        vid = versions_resp.json()["versions"][0]["version_id"]

        # 获取版本详情
        response = client.get(f"/boss/graph/templates/{tid}/versions/{vid}")
        assert response.status_code == 200
        data = response.json()
        assert data["ok"] is True
        assert data["version"]["version_id"] == vid
        assert data["version"]["name"] == "详情测试"
        assert len(data["version"]["nodes"]) == 2

    @patch("backend.security.rate_limiter.check", side_effect=_bypass_rate_limit)
    @patch("backend.governance.scope_classifier.guard_payload", side_effect=_bypass_governance)
    def test_get_version_nonexistent_404(self, mock_guard, mock_rate):
        """不存在的版本返回 404"""
        from fastapi.testclient import TestClient
        from backend.app import app

        client = TestClient(app)

        create_resp = client.post("/boss/graph/templates", json={
            "name": "测试",
            "nodes": _sample_api_nodes(),
        })
        tid = create_resp.json()["template"]["template_id"]

        response = client.get(f"/boss/graph/templates/{tid}/versions/ver_nonexistent")
        assert response.status_code == 404

    @patch("backend.security.rate_limiter.check", side_effect=_bypass_rate_limit)
    @patch("backend.governance.scope_classifier.guard_payload", side_effect=_bypass_governance)
    def test_restore_version(self, mock_guard, mock_rate):
        """回滚到旧版本"""
        from fastapi.testclient import TestClient
        from backend.app import app

        client = TestClient(app)

        create_resp = client.post("/boss/graph/templates", json={
            "name": "原始版本",
            "nodes": _sample_api_nodes(),
            "edges": _sample_api_edges(),
        })
        tid = create_resp.json()["template"]["template_id"]

        # 更新
        client.put(f"/boss/graph/templates/{tid}", json={
            "name": "更新后版本",
            "nodes": _sample_api_nodes(),
        })

        # 获取版本 ID
        versions_resp = client.get(f"/boss/graph/templates/{tid}/versions")
        vid = versions_resp.json()["versions"][0]["version_id"]

        # 回滚
        response = client.post(f"/boss/graph/templates/{tid}/versions/{vid}/restore")
        assert response.status_code == 200
        data = response.json()
        assert data["ok"] is True
        assert data["template"]["name"] == "原始版本"
        assert data["restored_from_version"] == vid

        # 版本列表应有 2 条（原始 + 更新后）
        versions_resp2 = client.get(f"/boss/graph/templates/{tid}/versions")
        assert versions_resp2.json()["total"] == 2

    @patch("backend.security.rate_limiter.check", side_effect=_bypass_rate_limit)
    @patch("backend.governance.scope_classifier.guard_payload", side_effect=_bypass_governance)
    def test_restore_nonexistent_version_404(self, mock_guard, mock_rate):
        """回滚不存在的版本返回 404"""
        from fastapi.testclient import TestClient
        from backend.app import app

        client = TestClient(app)

        create_resp = client.post("/boss/graph/templates", json={
            "name": "测试",
            "nodes": _sample_api_nodes(),
        })
        tid = create_resp.json()["template"]["template_id"]

        response = client.post(f"/boss/graph/templates/{tid}/versions/ver_nonexistent/restore")
        assert response.status_code == 404

    @patch("backend.security.rate_limiter.check", side_effect=_bypass_rate_limit)
    @patch("backend.governance.scope_classifier.guard_payload", side_effect=_bypass_governance)
    def test_restore_rejects_corrupt_version(self, mock_guard, mock_rate):
        """损坏的版本快照不能回滚，也不会额外保存当前版本"""
        from fastapi.testclient import TestClient
        from backend.app import app

        client = TestClient(app)
        create_resp = client.post("/boss/graph/templates", json={
            "name": "原始版本",
            "nodes": _sample_api_nodes(),
        })
        tid = create_resp.json()["template"]["template_id"]
        client.put(f"/boss/graph/templates/{tid}", json={
            "name": "当前版本",
            "nodes": _sample_api_nodes(),
        })

        versions_resp = client.get(f"/boss/graph/templates/{tid}/versions")
        vid = versions_resp.json()["versions"][0]["version_id"]
        version_path = self.versions_dir / tid / f"{vid}.json"
        version_data = json.loads(version_path.read_text(encoding="utf-8"))
        version_data["nodes"] = []
        version_path.write_text(
            json.dumps(version_data, ensure_ascii=False),
            encoding="utf-8",
        )

        response = client.post(f"/boss/graph/templates/{tid}/versions/{vid}/restore")
        assert response.status_code == 409
        current = client.get(f"/boss/graph/templates/{tid}").json()["template"]
        assert current["name"] == "当前版本"
        assert client.get(f"/boss/graph/templates/{tid}/versions").json()["total"] == 1

    @patch("backend.security.rate_limiter.check", side_effect=_bypass_rate_limit)
    @patch("backend.governance.scope_classifier.guard_payload", side_effect=_bypass_governance)
    def test_restore_nonexistent_template_404(self, mock_guard, mock_rate):
        """回滚不存在的模板返回 404"""
        from fastapi.testclient import TestClient
        from backend.app import app

        client = TestClient(app)
        response = client.post("/boss/graph/templates/tpl_nonexistent/versions/ver_xxx/restore")
        assert response.status_code == 404

    @patch("backend.security.rate_limiter.check", side_effect=_bypass_rate_limit)
    @patch("backend.governance.scope_classifier.guard_payload", side_effect=_bypass_governance)
    def test_list_versions_nonexistent_template_404(self, mock_guard, mock_rate):
        """列出不存在模板的版本返回 404"""
        from fastapi.testclient import TestClient
        from backend.app import app

        client = TestClient(app)
        response = client.get("/boss/graph/templates/tpl_nonexistent/versions")
        assert response.status_code == 404

    @patch("backend.security.rate_limiter.check", side_effect=_bypass_rate_limit)
    @patch("backend.governance.scope_classifier.guard_payload", side_effect=_bypass_governance)
    def test_delete_template_removes_versions(self, mock_guard, mock_rate):
        """删除模板时同步清理版本"""
        from fastapi.testclient import TestClient
        from backend.app import app

        client = TestClient(app)

        create_resp = client.post("/boss/graph/templates", json={
            "name": "待删除",
            "nodes": _sample_api_nodes(),
        })
        tid = create_resp.json()["template"]["template_id"]

        # 创建一个版本
        client.put(f"/boss/graph/templates/{tid}", json={
            "name": "更新",
            "nodes": _sample_api_nodes(),
        })

        # 删除模板
        response = client.delete(f"/boss/graph/templates/{tid}")
        assert response.status_code == 200

        # 版本列表应返回 404（模板已不存在）
        versions_resp = client.get(f"/boss/graph/templates/{tid}/versions")
        assert versions_resp.status_code == 404

    # ── Phase 6.7: Version Metadata & Compare API 测试 ──────

    @patch("backend.security.rate_limiter.check", side_effect=_bypass_rate_limit)
    @patch("backend.governance.scope_classifier.guard_payload", side_effect=_bypass_governance)
    def test_update_version_metadata_success(self, mock_guard, mock_rate):
        """更新版本元数据成功"""
        from fastapi.testclient import TestClient
        from backend.app import app

        client = TestClient(app)
        create_resp = client.post("/boss/graph/templates", json={
            "name": "元数据测试",
            "nodes": _sample_api_nodes(),
        })
        tid = create_resp.json()["template"]["template_id"]

        # 创建版本
        client.put(f"/boss/graph/templates/{tid}", json={
            "name": "更新",
            "nodes": _sample_api_nodes(),
        })
        vid = client.get(f"/boss/graph/templates/{tid}/versions").json()["versions"][0]["version_id"]

        # 更新元数据
        response = client.patch(f"/boss/graph/templates/{tid}/versions/{vid}", json={
            "label": "发布前备份",
            "note": "修复了调研 prompt",
        })
        assert response.status_code == 200
        data = response.json()
        assert data["ok"] is True
        assert data["version"]["label"] == "发布前备份"
        assert data["version"]["note"] == "修复了调研 prompt"

    @patch("backend.security.rate_limiter.check", side_effect=_bypass_rate_limit)
    @patch("backend.governance.scope_classifier.guard_payload", side_effect=_bypass_governance)
    def test_update_version_metadata_404(self, mock_guard, mock_rate):
        """不存在的版本返回 404"""
        from fastapi.testclient import TestClient
        from backend.app import app

        client = TestClient(app)
        create_resp = client.post("/boss/graph/templates", json={
            "name": "测试",
            "nodes": _sample_api_nodes(),
        })
        tid = create_resp.json()["template"]["template_id"]

        response = client.patch(f"/boss/graph/templates/{tid}/versions/ver_nonexistent", json={
            "label": "test",
        })
        assert response.status_code == 404

    @patch("backend.security.rate_limiter.check", side_effect=_bypass_rate_limit)
    @patch("backend.governance.scope_classifier.guard_payload", side_effect=_bypass_governance)
    def test_update_version_metadata_label_too_long(self, mock_guard, mock_rate):
        """label 超长返回 422（Pydantic 校验）"""
        from fastapi.testclient import TestClient
        from backend.app import app

        client = TestClient(app)
        create_resp = client.post("/boss/graph/templates", json={
            "name": "测试",
            "nodes": _sample_api_nodes(),
        })
        tid = create_resp.json()["template"]["template_id"]
        client.put(f"/boss/graph/templates/{tid}", json={"name": "更新", "nodes": _sample_api_nodes()})
        vid = client.get(f"/boss/graph/templates/{tid}/versions").json()["versions"][0]["version_id"]

        response = client.patch(f"/boss/graph/templates/{tid}/versions/{vid}", json={
            "label": "x" * 101,
        })
        assert response.status_code == 422

    @patch("backend.security.rate_limiter.check", side_effect=_bypass_rate_limit)
    @patch("backend.governance.scope_classifier.guard_payload", side_effect=_bypass_governance)
    def test_update_version_metadata_empty_body(self, mock_guard, mock_rate):
        """空请求体返回 400"""
        from fastapi.testclient import TestClient
        from backend.app import app

        client = TestClient(app)
        create_resp = client.post("/boss/graph/templates", json={
            "name": "测试",
            "nodes": _sample_api_nodes(),
        })
        tid = create_resp.json()["template"]["template_id"]
        client.put(f"/boss/graph/templates/{tid}", json={"name": "更新", "nodes": _sample_api_nodes()})
        vid = client.get(f"/boss/graph/templates/{tid}/versions").json()["versions"][0]["version_id"]

        response = client.patch(f"/boss/graph/templates/{tid}/versions/{vid}", json={})
        assert response.status_code == 400

    @patch("backend.security.rate_limiter.check", side_effect=_bypass_rate_limit)
    @patch("backend.governance.scope_classifier.guard_payload", side_effect=_bypass_governance)
    def test_update_version_metadata_rejects_snapshot_fields(self, mock_guard, mock_rate):
        """PATCH 只允许 label/note，不能夹带快照字段"""
        from fastapi.testclient import TestClient
        from backend.app import app

        client = TestClient(app)
        create_resp = client.post("/boss/graph/templates", json={
            "name": "不可变测试",
            "nodes": _sample_api_nodes(),
        })
        tid = create_resp.json()["template"]["template_id"]
        client.put(f"/boss/graph/templates/{tid}", json={
            "name": "更新",
            "nodes": _sample_api_nodes(),
        })
        vid = client.get(f"/boss/graph/templates/{tid}/versions").json()["versions"][0]["version_id"]

        response = client.patch(f"/boss/graph/templates/{tid}/versions/{vid}", json={
            "label": "合法标签",
            "nodes": [],
        })
        assert response.status_code == 422
        version = client.get(
            f"/boss/graph/templates/{tid}/versions/{vid}"
        ).json()["version"]
        assert version["label"] == ""
        assert len(version["nodes"]) == 2

    @patch("backend.security.rate_limiter.check", side_effect=_bypass_rate_limit)
    @patch("backend.governance.scope_classifier.guard_payload", side_effect=_bypass_governance)
    def test_compare_versions_no_changes(self, mock_guard, mock_rate):
        """版本对比无变化"""
        from fastapi.testclient import TestClient
        from backend.app import app

        client = TestClient(app)
        create_resp = client.post("/boss/graph/templates", json={
            "name": "对比测试",
            "nodes": _sample_api_nodes(),
            "edges": _sample_api_edges(),
        })
        tid = create_resp.json()["template"]["template_id"]

        client.put(f"/boss/graph/templates/{tid}", json={
            "name": "对比测试",
            "nodes": _sample_api_nodes(),
            "edges": _sample_api_edges(),
        })
        vid = client.get(f"/boss/graph/templates/{tid}/versions").json()["versions"][0]["version_id"]

        response = client.get(f"/boss/graph/templates/{tid}/versions/compare?from={vid}&to=current")
        assert response.status_code == 200
        data = response.json()
        assert data["ok"] is True
        assert data["diff"]["field_changes"] == []
        assert data["diff"]["nodes"]["added"] == []
        assert data["diff"]["edges"]["added"] == []

    @patch("backend.security.rate_limiter.check", side_effect=_bypass_rate_limit)
    @patch("backend.governance.scope_classifier.guard_payload", side_effect=_bypass_governance)
    def test_compare_versions_field_changes(self, mock_guard, mock_rate):
        """版本对比检测基础字段变化"""
        from fastapi.testclient import TestClient
        from backend.app import app

        client = TestClient(app)
        create_resp = client.post("/boss/graph/templates", json={
            "name": "V1",
            "nodes": _sample_api_nodes(),
            "edges": _sample_api_edges(),
            "description": "描述V1",
        })
        tid = create_resp.json()["template"]["template_id"]

        client.put(f"/boss/graph/templates/{tid}", json={
            "name": "V2",
            "nodes": _sample_api_nodes(),
            "edges": _sample_api_edges(),
            "description": "描述V2",
        })
        vid = client.get(f"/boss/graph/templates/{tid}/versions").json()["versions"][0]["version_id"]

        response = client.get(f"/boss/graph/templates/{tid}/versions/compare?from={vid}&to=current")
        assert response.status_code == 200
        diff = response.json()["diff"]
        fields = {c["field"]: c for c in diff["field_changes"]}
        assert "name" in fields
        assert fields["name"]["from"] == "V1"
        assert fields["name"]["to"] == "V2"

    @patch("backend.security.rate_limiter.check", side_effect=_bypass_rate_limit)
    @patch("backend.governance.scope_classifier.guard_payload", side_effect=_bypass_governance)
    def test_compare_versions_node_changes(self, mock_guard, mock_rate):
        """版本对比检测节点变化"""
        from fastapi.testclient import TestClient
        from backend.app import app

        client = TestClient(app)
        create_resp = client.post("/boss/graph/templates", json={
            "name": "节点对比",
            "nodes": _sample_api_nodes(),
            "edges": _sample_api_edges(),
        })
        tid = create_resp.json()["template"]["template_id"]

        # 更新：修改节点 + 新增节点
        client.put(f"/boss/graph/templates/{tid}", json={
            "name": "节点对比",
            "nodes": [
                {"id": "research", "agent_id": "research", "task_type": "research_brief", "title": "调研v2", "prompt": "新调研"},
                {"id": "marketing", "agent_id": "marketing", "task_type": "copywriting", "title": "营销", "prompt": "做营销"},
                {"id": "data", "agent_id": "data", "task_type": "analysis", "title": "数据", "prompt": "分析"},
            ],
        })
        vid = client.get(f"/boss/graph/templates/{tid}/versions").json()["versions"][0]["version_id"]

        response = client.get(f"/boss/graph/templates/{tid}/versions/compare?from={vid}&to=current")
        assert response.status_code == 200
        diff = response.json()["diff"]
        assert len(diff["nodes"]["added"]) == 1
        assert diff["nodes"]["added"][0]["id"] == "data"
        assert len(diff["nodes"]["modified"]) == 1
        assert diff["nodes"]["modified"][0]["id"] == "research"

    @patch("backend.security.rate_limiter.check", side_effect=_bypass_rate_limit)
    @patch("backend.governance.scope_classifier.guard_payload", side_effect=_bypass_governance)
    def test_compare_versions_edge_changes(self, mock_guard, mock_rate):
        """版本对比检测边变化"""
        from fastapi.testclient import TestClient
        from backend.app import app

        client = TestClient(app)
        create_resp = client.post("/boss/graph/templates", json={
            "name": "边对比",
            "nodes": _sample_api_nodes(),
            "edges": _sample_api_edges(),
        })
        tid = create_resp.json()["template"]["template_id"]

        # 更新：替换边
        client.put(f"/boss/graph/templates/{tid}", json={
            "name": "边对比",
            "nodes": _sample_api_nodes(),
            "edges": [{"from_node": "marketing", "to_node": "research", "handoff_type": "feedback"}],
        })
        vid = client.get(f"/boss/graph/templates/{tid}/versions").json()["versions"][0]["version_id"]

        response = client.get(f"/boss/graph/templates/{tid}/versions/compare?from={vid}&to=current")
        assert response.status_code == 200
        diff = response.json()["diff"]
        assert len(diff["edges"]["added"]) == 1
        assert len(diff["edges"]["removed"]) == 1

    @patch("backend.security.rate_limiter.check", side_effect=_bypass_rate_limit)
    @patch("backend.governance.scope_classifier.guard_payload", side_effect=_bypass_governance)
    def test_compare_versions_vs_current(self, mock_guard, mock_rate):
        """版本 vs current 对比"""
        from fastapi.testclient import TestClient
        from backend.app import app

        client = TestClient(app)
        create_resp = client.post("/boss/graph/templates", json={
            "name": "原始",
            "nodes": _sample_api_nodes(),
        })
        tid = create_resp.json()["template"]["template_id"]

        client.put(f"/boss/graph/templates/{tid}", json={
            "name": "当前",
            "nodes": _sample_api_nodes(),
        })
        vid = client.get(f"/boss/graph/templates/{tid}/versions").json()["versions"][0]["version_id"]

        response = client.get(f"/boss/graph/templates/{tid}/versions/compare?from={vid}&to=current")
        assert response.status_code == 200
        diff = response.json()["diff"]
        assert diff["from_version"] == vid
        assert diff["to_version"] == "current"

    @patch("backend.security.rate_limiter.check", side_effect=_bypass_rate_limit)
    @patch("backend.governance.scope_classifier.guard_payload", side_effect=_bypass_governance)
    def test_compare_versions_nonexistent_template_404(self, mock_guard, mock_rate):
        """不存在模板的版本对比返回 404"""
        from fastapi.testclient import TestClient
        from backend.app import app

        client = TestClient(app)
        response = client.get("/boss/graph/templates/tpl_nonexistent/versions/compare?from=ver_a&to=current")
        assert response.status_code == 404

    @patch("backend.security.rate_limiter.check", side_effect=_bypass_rate_limit)
    @patch("backend.governance.scope_classifier.guard_payload", side_effect=_bypass_governance)
    def test_compare_versions_invalid_from_id(self, mock_guard, mock_rate):
        """无效的 from 版本 ID 返回 400"""
        from fastapi.testclient import TestClient
        from backend.app import app

        client = TestClient(app)
        create_resp = client.post("/boss/graph/templates", json={
            "name": "测试",
            "nodes": _sample_api_nodes(),
        })
        tid = create_resp.json()["template"]["template_id"]

        response = client.get(f"/boss/graph/templates/{tid}/versions/compare?from=invalid_id&to=current")
        assert response.status_code == 400

    @patch("backend.security.rate_limiter.check", side_effect=_bypass_rate_limit)
    @patch("backend.governance.scope_classifier.guard_payload", side_effect=_bypass_governance)
    def test_compare_versions_invalid_to_id(self, mock_guard, mock_rate):
        """无效的 to 版本 ID 返回 400"""
        from fastapi.testclient import TestClient
        from backend.app import app

        client = TestClient(app)
        create_resp = client.post("/boss/graph/templates", json={
            "name": "测试",
            "nodes": _sample_api_nodes(),
        })
        tid = create_resp.json()["template"]["template_id"]

        response = client.get(f"/boss/graph/templates/{tid}/versions/compare?from=ver_aabbccddeeff&to=bad_id")
        assert response.status_code == 400

    @patch("backend.security.rate_limiter.check", side_effect=_bypass_rate_limit)
    @patch("backend.governance.scope_classifier.guard_payload", side_effect=_bypass_governance)
    def test_compare_versions_missing_params(self, mock_guard, mock_rate):
        """缺少参数返回 422"""
        from fastapi.testclient import TestClient
        from backend.app import app

        client = TestClient(app)
        create_resp = client.post("/boss/graph/templates", json={
            "name": "测试",
            "nodes": _sample_api_nodes(),
        })
        tid = create_resp.json()["template"]["template_id"]

        # 缺少 from
        response = client.get(f"/boss/graph/templates/{tid}/versions/compare?to=current")
        assert response.status_code == 422

        # 缺少 to
        response = client.get(f"/boss/graph/templates/{tid}/versions/compare?from=ver_aabbccddeeff")
        assert response.status_code == 422

    @patch("backend.security.rate_limiter.check", side_effect=_bypass_rate_limit)
    @patch("backend.governance.scope_classifier.guard_payload", side_effect=_bypass_governance)
    def test_compare_versions_same_version(self, mock_guard, mock_rate):
        """对比同一个版本返回 400"""
        from fastapi.testclient import TestClient
        from backend.app import app

        client = TestClient(app)
        create_resp = client.post("/boss/graph/templates", json={
            "name": "测试",
            "nodes": _sample_api_nodes(),
        })
        tid = create_resp.json()["template"]["template_id"]
        client.put(f"/boss/graph/templates/{tid}", json={"name": "更新", "nodes": _sample_api_nodes()})
        vid = client.get(f"/boss/graph/templates/{tid}/versions").json()["versions"][0]["version_id"]

        response = client.get(f"/boss/graph/templates/{tid}/versions/compare?from={vid}&to={vid}")
        assert response.status_code == 400

    @patch("backend.security.rate_limiter.check", side_effect=_bypass_rate_limit)
    @patch("backend.governance.scope_classifier.guard_payload", side_effect=_bypass_governance)
    def test_compare_versions_cross_template_rejected(self, mock_guard, mock_rate):
        """跨模板版本对比返回 404"""
        from fastapi.testclient import TestClient
        from backend.app import app

        client = TestClient(app)

        resp1 = client.post("/boss/graph/templates", json={"name": "模板A", "nodes": _sample_api_nodes()})
        tid_a = resp1.json()["template"]["template_id"]
        client.put(f"/boss/graph/templates/{tid_a}", json={"name": "更新A", "nodes": _sample_api_nodes()})

        resp2 = client.post("/boss/graph/templates", json={"name": "模板B", "nodes": _sample_api_nodes()})
        tid_b = resp2.json()["template"]["template_id"]
        client.put(f"/boss/graph/templates/{tid_b}", json={"name": "更新B", "nodes": _sample_api_nodes()})

        vid_a = client.get(f"/boss/graph/templates/{tid_a}/versions").json()["versions"][0]["version_id"]

        # 用模板A的版本去对比模板B（from 属于 A，但 API 路由是 B）
        response = client.get(f"/boss/graph/templates/{tid_b}/versions/compare?from={vid_a}&to=current")
        assert response.status_code == 404

    # ── Phase 6.8: Audit Log & Pin API 测试 ─────────────────

    @patch("backend.security.rate_limiter.check", side_effect=_bypass_rate_limit)
    @patch("backend.governance.scope_classifier.guard_payload", side_effect=_bypass_governance)
    def test_audit_log_created_on_create(self, mock_guard, mock_rate):
        """创建模板时自动写入审计日志"""
        from fastapi.testclient import TestClient
        from backend.app import app

        client = TestClient(app)
        resp = client.post("/boss/graph/templates", json={
            "name": "审计创建测试",
            "nodes": _sample_api_nodes(),
        })
        tid = resp.json()["template"]["template_id"]

        audit_resp = client.get(f"/boss/graph/templates/{tid}/audit")
        assert audit_resp.status_code == 200
        events = audit_resp.json()["events"]
        assert len(events) >= 1
        assert events[0]["event_type"] == "create"
        assert "审计创建测试" in events[0]["summary"]

    @patch("backend.security.rate_limiter.check", side_effect=_bypass_rate_limit)
    @patch("backend.governance.scope_classifier.guard_payload", side_effect=_bypass_governance)
    def test_audit_log_created_on_update(self, mock_guard, mock_rate):
        """更新模板时写入审计日志"""
        from fastapi.testclient import TestClient
        from backend.app import app

        client = TestClient(app)
        resp = client.post("/boss/graph/templates", json={
            "name": "审计更新测试",
            "nodes": _sample_api_nodes(),
        })
        tid = resp.json()["template"]["template_id"]

        client.put(f"/boss/graph/templates/{tid}", json={
            "name": "审计更新后",
            "nodes": _sample_api_nodes(),
        })

        audit_resp = client.get(f"/boss/graph/templates/{tid}/audit")
        events = audit_resp.json()["events"]
        assert len(events) >= 2
        event_types = [e["event_type"] for e in events]
        assert "create" in event_types
        assert "update" in event_types

    @patch("backend.security.rate_limiter.check", side_effect=_bypass_rate_limit)
    @patch("backend.governance.scope_classifier.guard_payload", side_effect=_bypass_governance)
    def test_audit_log_filter_by_type(self, mock_guard, mock_rate):
        """按事件类型过滤审计日志"""
        from fastapi.testclient import TestClient
        from backend.app import app

        client = TestClient(app)
        resp = client.post("/boss/graph/templates", json={
            "name": "过滤测试",
            "nodes": _sample_api_nodes(),
        })
        tid = resp.json()["template"]["template_id"]

        client.put(f"/boss/graph/templates/{tid}", json={
            "name": "过滤测试更新",
            "nodes": _sample_api_nodes(),
        })

        # 只看 create
        audit_resp = client.get(f"/boss/graph/templates/{tid}/audit?event_type=create")
        events = audit_resp.json()["events"]
        assert all(e["event_type"] == "create" for e in events)

    @patch("backend.security.rate_limiter.check", side_effect=_bypass_rate_limit)
    @patch("backend.governance.scope_classifier.guard_payload", side_effect=_bypass_governance)
    def test_audit_log_invalid_type_400(self, mock_guard, mock_rate):
        """无效事件类型返回 400"""
        from fastapi.testclient import TestClient
        from backend.app import app

        client = TestClient(app)
        resp = client.post("/boss/graph/templates", json={
            "name": "无效类型测试",
            "nodes": _sample_api_nodes(),
        })
        tid = resp.json()["template"]["template_id"]

        audit_resp = client.get(f"/boss/graph/templates/{tid}/audit?event_type=invalid")
        assert audit_resp.status_code == 400

    @patch("backend.security.rate_limiter.check", side_effect=_bypass_rate_limit)
    @patch("backend.governance.scope_classifier.guard_payload", side_effect=_bypass_governance)
    def test_audit_log_nonexistent_template_404(self, mock_guard, mock_rate):
        """不存在模板的审计日志返回 404"""
        from fastapi.testclient import TestClient
        from backend.app import app

        client = TestClient(app)
        audit_resp = client.get("/boss/graph/templates/tpl_nonexistent/audit")
        assert audit_resp.status_code == 404

    @patch("backend.security.rate_limiter.check", side_effect=_bypass_rate_limit)
    @patch("backend.governance.scope_classifier.guard_payload", side_effect=_bypass_governance)
    def test_audit_log_no_secrets(self, mock_guard, mock_rate):
        """审计日志不包含敏感信息"""
        from fastapi.testclient import TestClient
        from backend.app import app

        client = TestClient(app)
        resp = client.post("/boss/graph/templates", json={
            "name": "安全测试",
            "nodes": _sample_api_nodes(),
        })
        tid = resp.json()["template"]["template_id"]

        audit_resp = client.get(f"/boss/graph/templates/{tid}/audit")
        import json as json_mod
        full_text = json_mod.dumps(audit_resp.json())
        assert "api_key" not in full_text.lower()
        assert "token" not in full_text.lower()
        assert "secret" not in full_text.lower()

    @patch("backend.security.rate_limiter.check", side_effect=_bypass_rate_limit)
    @patch("backend.governance.scope_classifier.guard_payload", side_effect=_bypass_governance)
    def test_clone_creates_clone_audit(self, mock_guard, mock_rate):
        """克隆模板写 clone 审计，不只是 create"""
        from fastapi.testclient import TestClient
        from backend.app import app

        client = TestClient(app)
        # 创建源模板
        resp = client.post("/boss/graph/templates", json={
            "name": "源模板",
            "nodes": _sample_api_nodes(),
        })
        source_tid = resp.json()["template"]["template_id"]

        # 克隆
        clone_resp = client.post("/boss/graph/templates", json={
            "name": "源模板 副本",
            "nodes": _sample_api_nodes(),
            "source_template_id": source_tid,
        })
        clone_tid = clone_resp.json()["template"]["template_id"]

        # 克隆模板的审计日志应包含 clone 事件
        audit_resp = client.get(f"/boss/graph/templates/{clone_tid}/audit")
        events = audit_resp.json()["events"]
        event_types = [e["event_type"] for e in events]
        assert "clone" in event_types
        assert "create" not in event_types  # 不应出现 create

    @patch("backend.security.rate_limiter.check", side_effect=_bypass_rate_limit)
    @patch("backend.governance.scope_classifier.guard_payload", side_effect=_bypass_governance)
    def test_clone_audit_has_source_template_id(self, mock_guard, mock_rate):
        """clone 审计 details 包含 source_template_id"""
        from fastapi.testclient import TestClient
        from backend.app import app

        client = TestClient(app)
        resp = client.post("/boss/graph/templates", json={
            "name": "源模板",
            "nodes": _sample_api_nodes(),
        })
        source_tid = resp.json()["template"]["template_id"]

        clone_resp = client.post("/boss/graph/templates", json={
            "name": "克隆体",
            "nodes": _sample_api_nodes(),
            "source_template_id": source_tid,
        })
        clone_tid = clone_resp.json()["template"]["template_id"]

        audit_resp = client.get(f"/boss/graph/templates/{clone_tid}/audit?event_type=clone")
        events = audit_resp.json()["events"]
        assert len(events) == 1
        details = events[0]["details"]
        assert details["source_template_id"] == source_tid
        assert details["source_name"] == "源模板"
        assert details["new_template_id"] == clone_tid
        assert details["node_count"] == 2

    @patch("backend.security.rate_limiter.check", side_effect=_bypass_rate_limit)
    @patch("backend.governance.scope_classifier.guard_payload", side_effect=_bypass_governance)
    def test_create_without_source_still_creates_create_audit(self, mock_guard, mock_rate):
        """普通创建（无 source_template_id）仍写 create 审计"""
        from fastapi.testclient import TestClient
        from backend.app import app

        client = TestClient(app)
        resp = client.post("/boss/graph/templates", json={
            "name": "普通创建",
            "nodes": _sample_api_nodes(),
        })
        tid = resp.json()["template"]["template_id"]

        audit_resp = client.get(f"/boss/graph/templates/{tid}/audit")
        events = audit_resp.json()["events"]
        assert len(events) == 1
        assert events[0]["event_type"] == "create"

    @patch("backend.security.rate_limiter.check", side_effect=_bypass_rate_limit)
    @patch("backend.governance.scope_classifier.guard_payload", side_effect=_bypass_governance)
    def test_pin_version_success(self, mock_guard, mock_rate):
        """固定版本成功"""
        from fastapi.testclient import TestClient
        from backend.app import app

        client = TestClient(app)
        resp = client.post("/boss/graph/templates", json={
            "name": "固定测试",
            "nodes": _sample_api_nodes(),
        })
        tid = resp.json()["template"]["template_id"]
        client.put(f"/boss/graph/templates/{tid}", json={"name": "更新", "nodes": _sample_api_nodes()})
        vid = client.get(f"/boss/graph/templates/{tid}/versions").json()["versions"][0]["version_id"]

        pin_resp = client.post(f"/boss/graph/templates/{tid}/versions/{vid}/pin")
        assert pin_resp.status_code == 200
        assert pin_resp.json()["version"]["pinned"] is True

        # 列表也应显示 pinned
        versions = client.get(f"/boss/graph/templates/{tid}/versions").json()["versions"]
        pinned_ver = next(v for v in versions if v["version_id"] == vid)
        assert pinned_ver["pinned"] is True

    @patch("backend.security.rate_limiter.check", side_effect=_bypass_rate_limit)
    @patch("backend.governance.scope_classifier.guard_payload", side_effect=_bypass_governance)
    def test_unpin_version_success(self, mock_guard, mock_rate):
        """取消固定版本成功"""
        from fastapi.testclient import TestClient
        from backend.app import app

        client = TestClient(app)
        resp = client.post("/boss/graph/templates", json={
            "name": "取消固定测试",
            "nodes": _sample_api_nodes(),
        })
        tid = resp.json()["template"]["template_id"]
        client.put(f"/boss/graph/templates/{tid}", json={"name": "更新", "nodes": _sample_api_nodes()})
        vid = client.get(f"/boss/graph/templates/{tid}/versions").json()["versions"][0]["version_id"]

        # 先固定
        client.post(f"/boss/graph/templates/{tid}/versions/{vid}/pin")
        # 取消固定
        unpin_resp = client.post(f"/boss/graph/templates/{tid}/versions/{vid}/unpin")
        assert unpin_resp.status_code == 200
        assert unpin_resp.json()["version"]["pinned"] is False

    @patch("backend.security.rate_limiter.check", side_effect=_bypass_rate_limit)
    @patch("backend.governance.scope_classifier.guard_payload", side_effect=_bypass_governance)
    def test_pin_nonexistent_version_404(self, mock_guard, mock_rate):
        """固定不存在的版本返回 404"""
        from fastapi.testclient import TestClient
        from backend.app import app

        client = TestClient(app)
        resp = client.post("/boss/graph/templates", json={
            "name": "测试",
            "nodes": _sample_api_nodes(),
        })
        tid = resp.json()["template"]["template_id"]

        pin_resp = client.post(f"/boss/graph/templates/{tid}/versions/ver_nonexistent/pin")
        assert pin_resp.status_code == 404

    @patch("backend.security.rate_limiter.check", side_effect=_bypass_rate_limit)
    @patch("backend.governance.scope_classifier.guard_payload", side_effect=_bypass_governance)
    def test_pin_version_survives_trim(self, mock_guard, mock_rate):
        """固定版本不被自动裁剪"""
        from fastapi.testclient import TestClient
        from backend.app import app

        client = TestClient(app)
        resp = client.post("/boss/graph/templates", json={
            "name": "裁剪测试",
            "nodes": _sample_api_nodes(),
        })
        tid = resp.json()["template"]["template_id"]

        # 创建第一个版本
        client.put(f"/boss/graph/templates/{tid}", json={"name": "v1", "nodes": _sample_api_nodes()})
        versions1 = client.get(f"/boss/graph/templates/{tid}/versions").json()["versions"]
        vid_first = versions1[0]["version_id"]

        # 固定第一个版本
        client.post(f"/boss/graph/templates/{tid}/versions/{vid_first}/pin")

        # 创建 25 个版本（超过 20 限额）
        for i in range(25):
            client.put(f"/boss/graph/templates/{tid}", json={"name": f"v{i+2}", "nodes": _sample_api_nodes()})

        # 固定版本应该还在
        versions_final = client.get(f"/boss/graph/templates/{tid}/versions").json()["versions"]
        pinned_ids = [v["version_id"] for v in versions_final if v.get("pinned")]
        assert vid_first in pinned_ids

    @patch("backend.security.rate_limiter.check", side_effect=_bypass_rate_limit)
    @patch("backend.governance.scope_classifier.guard_payload", side_effect=_bypass_governance)
    def test_audit_log_created_on_restore(self, mock_guard, mock_rate):
        """回滚版本时写入审计日志"""
        from fastapi.testclient import TestClient
        from backend.app import app

        client = TestClient(app)
        resp = client.post("/boss/graph/templates", json={
            "name": "回滚审计测试",
            "nodes": _sample_api_nodes(),
        })
        tid = resp.json()["template"]["template_id"]
        client.put(f"/boss/graph/templates/{tid}", json={"name": "更新", "nodes": _sample_api_nodes()})
        vid = client.get(f"/boss/graph/templates/{tid}/versions").json()["versions"][0]["version_id"]

        client.post(f"/boss/graph/templates/{tid}/versions/{vid}/restore")

        audit_resp = client.get(f"/boss/graph/templates/{tid}/audit?event_type=restore")
        events = audit_resp.json()["events"]
        assert len(events) >= 1
        assert vid in events[0]["summary"]

    @patch("backend.security.rate_limiter.check", side_effect=_bypass_rate_limit)
    @patch("backend.governance.scope_classifier.guard_payload", side_effect=_bypass_governance)
    def test_audit_log_created_on_metadata_update(self, mock_guard, mock_rate):
        """更新版本元数据时写入审计日志"""
        from fastapi.testclient import TestClient
        from backend.app import app

        client = TestClient(app)
        resp = client.post("/boss/graph/templates", json={
            "name": "元数据审计测试",
            "nodes": _sample_api_nodes(),
        })
        tid = resp.json()["template"]["template_id"]
        client.put(f"/boss/graph/templates/{tid}", json={"name": "更新", "nodes": _sample_api_nodes()})
        vid = client.get(f"/boss/graph/templates/{tid}/versions").json()["versions"][0]["version_id"]

        client.patch(f"/boss/graph/templates/{tid}/versions/{vid}", json={"label": "测试标签"})

        audit_resp = client.get(f"/boss/graph/templates/{tid}/audit?event_type=metadata_update")
        events = audit_resp.json()["events"]
        assert len(events) >= 1
        assert events[0]["details"]["version_id"] == vid

    @patch("backend.security.rate_limiter.check", side_effect=_bypass_rate_limit)
    @patch("backend.governance.scope_classifier.guard_payload", side_effect=_bypass_governance)
    def test_audit_log_created_on_pin(self, mock_guard, mock_rate):
        """固定版本时写入审计日志"""
        from fastapi.testclient import TestClient
        from backend.app import app

        client = TestClient(app)
        resp = client.post("/boss/graph/templates", json={
            "name": "固定审计测试",
            "nodes": _sample_api_nodes(),
        })
        tid = resp.json()["template"]["template_id"]
        client.put(f"/boss/graph/templates/{tid}", json={"name": "更新", "nodes": _sample_api_nodes()})
        vid = client.get(f"/boss/graph/templates/{tid}/versions").json()["versions"][0]["version_id"]

        client.post(f"/boss/graph/templates/{tid}/versions/{vid}/pin")

        audit_resp = client.get(f"/boss/graph/templates/{tid}/audit?event_type=pin")
        events = audit_resp.json()["events"]
        assert len(events) >= 1
        assert vid in events[0]["summary"]

    @patch("backend.security.rate_limiter.check", side_effect=_bypass_rate_limit)
    @patch("backend.governance.scope_classifier.guard_payload", side_effect=_bypass_governance)
    def test_delete_template_audit_retained(self, mock_guard, mock_rate):
        """删除模板后审计日志仍可查询"""
        from fastapi.testclient import TestClient
        from backend.app import app

        client = TestClient(app)
        resp = client.post("/boss/graph/templates", json={
            "name": "保留审计测试",
            "nodes": _sample_api_nodes(),
        })
        tid = resp.json()["template"]["template_id"]

        # 审计日志存在
        audit_resp = client.get(f"/boss/graph/templates/{tid}/audit")
        assert audit_resp.status_code == 200

        # 删除模板
        client.delete(f"/boss/graph/templates/{tid}")

        # 审计日志仍可查询，返回 deleted=true
        audit_resp2 = client.get(f"/boss/graph/templates/{tid}/audit")
        assert audit_resp2.status_code == 200
        data = audit_resp2.json()
        assert data["ok"] is True
        assert data["deleted"] is True
        # 包含 create 和 delete 事件
        event_types = [e["event_type"] for e in data["events"]]
        assert "create" in event_types
        assert "delete" in event_types

    @patch("backend.security.rate_limiter.check", side_effect=_bypass_rate_limit)
    @patch("backend.governance.scope_classifier.guard_payload", side_effect=_bypass_governance)
    def test_delete_event_has_details(self, mock_guard, mock_rate):
        """delete 事件 details 包含 template_name / node_count / edge_count / deleted_at"""
        from fastapi.testclient import TestClient
        from backend.app import app

        client = TestClient(app)
        resp = client.post("/boss/graph/templates", json={
            "name": "详情测试",
            "nodes": _sample_api_nodes(),
            "edges": _sample_api_edges(),
        })
        tid = resp.json()["template"]["template_id"]

        client.delete(f"/boss/graph/templates/{tid}")

        audit_resp = client.get(f"/boss/graph/templates/{tid}/audit?event_type=delete")
        assert audit_resp.status_code == 200
        events = audit_resp.json()["events"]
        assert len(events) == 1
        details = events[0]["details"]
        assert details["template_name"] == "详情测试"
        assert details["node_count"] == 2
        assert details["edge_count"] == 1
        assert "deleted_at" in details

    @patch("backend.security.rate_limiter.check", side_effect=_bypass_rate_limit)
    @patch("backend.governance.scope_classifier.guard_payload", side_effect=_bypass_governance)
    def test_audit_nonexistent_no_file_404(self, mock_guard, mock_rate):
        """不存在且无审计文件的模板仍返回 404"""
        from fastapi.testclient import TestClient
        from backend.app import app

        client = TestClient(app)
        audit_resp = client.get("/boss/graph/templates/tpl_neverexist123/audit")
        assert audit_resp.status_code == 404

    # ── Phase 6.11: Canvas Layout API 测试 ──────────────────────

    @patch("backend.security.rate_limiter.check", side_effect=_bypass_rate_limit)
    @patch("backend.governance.scope_classifier.guard_payload", side_effect=_bypass_governance)
    def test_patch_layout_updates_canvas(self, mock_guard, mock_rate):
        """PATCH /layout 更新 canvas_layout 并返回完整模板"""
        from fastapi.testclient import TestClient
        from backend.app import app

        client = TestClient(app)
        resp = client.post("/boss/graph/templates", json={
            "name": "布局API测试",
            "nodes": _sample_api_nodes(),
            "edges": _sample_api_edges(),
        })
        tid = resp.json()["template"]["template_id"]

        layout = {"research": {"x": 100, "y": 200}, "marketing": {"x": 300, "y": 200}}
        patch_resp = client.patch(f"/boss/graph/templates/{tid}/layout", json={
            "canvas_layout": layout,
        })
        assert patch_resp.status_code == 200
        data = patch_resp.json()
        assert data["ok"] is True
        assert data["template"]["canvas_layout"] == layout

    @patch("backend.security.rate_limiter.check", side_effect=_bypass_rate_limit)
    @patch("backend.governance.scope_classifier.guard_payload", side_effect=_bypass_governance)
    def test_patch_layout_nonexistent_404(self, mock_guard, mock_rate):
        """PATCH /layout 对不存在的模板返回 404"""
        from fastapi.testclient import TestClient
        from backend.app import app

        client = TestClient(app)
        resp = client.patch("/boss/graph/templates/tpl_nonexistent/layout", json={
            "canvas_layout": {"a": {"x": 0, "y": 0}},
        })
        assert resp.status_code == 404

    @patch("backend.security.rate_limiter.check", side_effect=_bypass_rate_limit)
    @patch("backend.governance.scope_classifier.guard_payload", side_effect=_bypass_governance)
    def test_get_template_includes_canvas_layout(self, mock_guard, mock_rate):
        """GET 模板包含 canvas_layout 字段"""
        from fastapi.testclient import TestClient
        from backend.app import app

        client = TestClient(app)
        layout = {"research": {"x": 50, "y": 60}}
        resp = client.post("/boss/graph/templates", json={
            "name": "GET布局测试",
            "nodes": _sample_api_nodes(),
            "edges": _sample_api_edges(),
            "canvas_layout": layout,
        })
        tid = resp.json()["template"]["template_id"]

        get_resp = client.get(f"/boss/graph/templates/{tid}")
        assert get_resp.status_code == 200
        assert get_resp.json()["template"]["canvas_layout"] == layout

    @patch("backend.security.rate_limiter.check", side_effect=_bypass_rate_limit)
    @patch("backend.governance.scope_classifier.guard_payload", side_effect=_bypass_governance)
    def test_patch_layout_does_not_create_version(self, mock_guard, mock_rate):
        """PATCH /layout 不创建版本快照"""
        from fastapi.testclient import TestClient
        from backend.app import app

        client = TestClient(app)
        resp = client.post("/boss/graph/templates", json={
            "name": "布局无版本API",
            "nodes": _sample_api_nodes(),
            "edges": _sample_api_edges(),
        })
        tid = resp.json()["template"]["template_id"]

        client.patch(f"/boss/graph/templates/{tid}/layout", json={
            "canvas_layout": {"research": {"x": 1, "y": 2}},
        })

        ver_resp = client.get(f"/boss/graph/templates/{tid}/versions")
        assert ver_resp.status_code == 200
        assert len(ver_resp.json()["versions"]) == 0

    @patch("backend.security.rate_limiter.check", side_effect=_bypass_rate_limit)
    @patch("backend.governance.scope_classifier.guard_payload", side_effect=_bypass_governance)
    def test_list_templates_includes_canvas_layout(self, mock_guard, mock_rate):
        """列表接口也包含 canvas_layout"""
        from fastapi.testclient import TestClient
        from backend.app import app

        client = TestClient(app)
        layout = {"research": {"x": 10, "y": 20}}
        client.post("/boss/graph/templates", json={
            "name": "列表布局测试",
            "nodes": _sample_api_nodes(),
            "edges": _sample_api_edges(),
            "canvas_layout": layout,
        })

        list_resp = client.get("/boss/graph/templates")
        assert list_resp.status_code == 200
        templates = list_resp.json()["templates"]
        found = [t for t in templates if t["name"] == "列表布局测试"]
        assert len(found) == 1
        assert found[0]["canvas_layout"] == layout

    @patch("backend.security.rate_limiter.check", side_effect=_bypass_rate_limit)
    @patch("backend.governance.scope_classifier.guard_payload", side_effect=_bypass_governance)
    def test_patch_layout_clear_with_empty_object(self, mock_guard, mock_rate):
        """PATCH /layout 传空对象清除布局"""
        from fastapi.testclient import TestClient
        from backend.app import app

        client = TestClient(app)
        layout = {"research": {"x": 100, "y": 200}}
        resp = client.post("/boss/graph/templates", json={
            "name": "清除布局API",
            "nodes": _sample_api_nodes(),
            "edges": _sample_api_edges(),
            "canvas_layout": layout,
        })
        tid = resp.json()["template"]["template_id"]

        # Clear with empty object
        patch_resp = client.patch(f"/boss/graph/templates/{tid}/layout", json={
            "canvas_layout": {},
        })
        assert patch_resp.status_code == 200
        assert patch_resp.json()["template"]["canvas_layout"] == {}

    @patch("backend.security.rate_limiter.check", side_effect=_bypass_rate_limit)
    @patch("backend.governance.scope_classifier.guard_payload", side_effect=_bypass_governance)
    def test_patch_layout_null_rejects_422(self, mock_guard, mock_rate):
        """PATCH /layout 传 null 返回 422"""
        from fastapi.testclient import TestClient
        from backend.app import app

        client = TestClient(app)
        resp = client.post("/boss/graph/templates", json={
            "name": "null布局API",
            "nodes": _sample_api_nodes(),
            "edges": _sample_api_edges(),
        })
        tid = resp.json()["template"]["template_id"]

        # null should be rejected by Pydantic
        patch_resp = client.patch(f"/boss/graph/templates/{tid}/layout", json={
            "canvas_layout": None,
        })
        assert patch_resp.status_code == 422
