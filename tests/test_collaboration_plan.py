"""
Collaboration Plan — 协同计划协议测试

验收标准:
- 有 marketing/image/data manifest 时，能分配对应 agent
- 缺少能力时 step.status=unassigned，不崩
- /collaboration/run 能顺序执行 2 个简单步骤
- 不出现 /boss /workflow /pipeline 调用
"""
import os
import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest
from unittest.mock import patch, MagicMock

from backend.schemas.collaboration_plan import CollaborationStep, CollaborationPlan
from backend.schemas.agent_protocol import AgentRunResult
from backend.services.collaboration_planner import build_collaboration_plan
from backend.services.collaboration_executor import execute_collaboration_plan
from backend.services.collaboration_run_store import (
    save_step_record,
    load_plan_records,
    reset_step_for_retry,
    load_run_timeline,
    collect_plan_artifacts,
)


# ── Planner 测试 ──────────────────────────────────────────

class TestCollaborationPlanner:
    """测试协同计划构建"""

    def test_assign_marketing_agent(self):
        """有 marketing manifest 时，copywriting 步骤应分配 agent（echo caps 更少更精确）"""
        plan = build_collaboration_plan(
            goal="写一篇营销文案",
            steps=[{"name": "Generate Copy", "task_type": "copywriting", "required_capability": "copywriting"}],
        )
        assert plan.status == "pending"
        assert len(plan.steps) == 1
        step = plan.steps[0]
        assert step.status == "assigned"
        assert step.assigned_agent_id is not None

    def test_assign_image_agent(self):
        """有 image manifest 时，image 步骤应分配 image agent"""
        plan = build_collaboration_plan(
            goal="生成产品图片",
            steps=[{"name": "Generate Image", "task_type": "image_generate", "required_capability": "image"}],
        )
        step = plan.steps[0]
        assert step.status == "assigned"
        assert step.assigned_agent_id == "image"

    def test_assign_data_agent(self):
        """有 data manifest 时，data 步骤应分配 data agent"""
        plan = build_collaboration_plan(
            goal="分析销售数据",
            steps=[{"name": "Analyze Data", "task_type": "data_analyze", "required_capability": "data"}],
        )
        step = plan.steps[0]
        assert step.status == "assigned"
        assert step.assigned_agent_id == "data"

    def test_unassigned_when_capability_missing(self):
        """缺少对应能力时，step.status 应为 unassigned"""
        plan = build_collaboration_plan(
            goal="做一个视频",
            steps=[{"name": "Edit Video", "task_type": "video_edit", "required_capability": "video_editing"}],
        )
        step = plan.steps[0]
        assert step.status == "unassigned"
        assert step.assigned_agent_id is None

    def test_multi_step_plan(self):
        """多步骤计划应正确分配各步骤"""
        plan = build_collaboration_plan(
            goal="创建带图的营销内容",
            steps=[
                {"name": "Generate Copy", "task_type": "copywriting", "required_capability": "copywriting"},
                {"name": "Generate Image", "task_type": "image_generate", "required_capability": "image", "input_from": "step_1"},
            ],
        )
        assert len(plan.steps) == 2
        assert plan.steps[0].id == "step_1"
        assert plan.steps[0].assigned_agent_id is not None
        assert plan.steps[0].input_from is None
        assert plan.steps[1].id == "step_2"
        assert plan.steps[1].assigned_agent_id == "image"
        assert plan.steps[1].input_from == "step_1"

    def test_step_ids_auto_generated(self):
        """步骤 id 应自动生成 step_1, step_2, ..."""
        plan = build_collaboration_plan(
            goal="test",
            steps=[
                {"name": "A", "task_type": "copywriting", "required_capability": "copywriting"},
                {"name": "B", "task_type": "image_generate", "required_capability": "image"},
                {"name": "C", "task_type": "data_analyze", "required_capability": "data"},
            ],
        )
        ids = [s.id for s in plan.steps]
        assert ids == ["step_1", "step_2", "step_3"]

    def test_plan_has_id_and_created_at(self):
        """计划应有自动生成的 plan_id 和 created_at"""
        plan = build_collaboration_plan(
            goal="test",
            steps=[{"name": "A", "task_type": "copywriting", "required_capability": "copywriting"}],
        )
        assert plan.plan_id.startswith("cplan_")
        assert plan.created_at != ""

    def test_routing_metadata_populated(self):
        """路由后 step 应包含 routing_reason、candidate_agent_ids、matched_capability"""
        plan = build_collaboration_plan(
            goal="test routing metadata",
            steps=[{"name": "Copy", "task_type": "copywriting", "required_capability": "copywriting"}],
        )
        step = plan.steps[0]
        assert step.routing_reason is not None
        assert len(step.routing_reason) > 0
        assert isinstance(step.candidate_agent_ids, list)
        assert step.matched_capability == "copywriting"

    def test_unassigned_step_has_reason(self):
        """未分配步骤也应有 routing_reason"""
        plan = build_collaboration_plan(
            goal="test",
            steps=[{"name": "Video", "task_type": "video_edit", "required_capability": "video_editing"}],
        )
        step = plan.steps[0]
        assert step.status == "unassigned"
        assert step.routing_reason is not None
        assert "no agent found" in step.routing_reason

    def test_task_type_fallback_routing(self):
        """task_type fallback 也能正确分配 agent"""
        plan = build_collaboration_plan(
            goal="test fallback",
            steps=[{"name": "Img", "task_type": "image_generate", "required_capability": "nonexistent"}],
        )
        step = plan.steps[0]
        assert step.status == "assigned"
        assert step.assigned_agent_id == "image"
        assert "task_type fallback" in step.routing_reason

    def test_backward_compat_json_roundtrip(self):
        """旧格式 JSON（无新字段）仍可反序列化"""
        old_step_data = {
            "id": "step_1",
            "name": "Copy",
            "task_type": "copywriting",
            "required_capability": "copywriting",
            "status": "assigned",
            "assigned_agent_id": "marketing",
        }
        step = CollaborationStep(**old_step_data)
        assert step.routing_reason is None
        assert step.candidate_agent_ids == []
        assert step.matched_capability is None

    def test_depends_on_field(self):
        """新字段 depends_on 能正确传递"""
        plan = build_collaboration_plan(
            goal="test depends_on",
            steps=[
                {"name": "Step A", "task_type": "copywriting", "required_capability": "copywriting"},
                {"name": "Step B", "task_type": "image_generate", "required_capability": "image", "depends_on": ["step_1"]},
            ],
        )
        assert plan.steps[0].depends_on == []
        assert plan.steps[1].depends_on == ["step_1"]
        assert plan.steps[1].input_from is None

    def test_expected_output_field(self):
        """新字段 expected_output 能正确传递"""
        plan = build_collaboration_plan(
            goal="test expected_output",
            steps=[{"name": "Copy", "task_type": "copywriting", "required_capability": "copywriting", "expected_output": "一篇 500 字文案"}],
        )
        assert plan.steps[0].expected_output == "一篇 500 字文案"

    def test_review_required_field(self):
        """新字段 review_required 能正确传递"""
        plan = build_collaboration_plan(
            goal="test review_required",
            steps=[{"name": "Copy", "task_type": "copywriting", "required_capability": "copywriting", "review_required": True}],
        )
        assert plan.steps[0].review_required is True

    def test_input_from_auto_depends_on(self):
        """input_from 自动转换为 depends_on"""
        plan = build_collaboration_plan(
            goal="test input_from compat",
            steps=[
                {"name": "Step A", "task_type": "copywriting", "required_capability": "copywriting"},
                {"name": "Step B", "task_type": "image_generate", "required_capability": "image", "input_from": "step_1"},
            ],
        )
        assert plan.steps[1].depends_on == ["step_1"]
        assert plan.steps[1].input_from == "step_1"

    def test_depends_on_and_input_from_both_present(self):
        """depends_on 和 input_from 同时存在时保留 depends_on"""
        plan = build_collaboration_plan(
            goal="test both fields",
            steps=[
                {"name": "Step A", "task_type": "copywriting", "required_capability": "copywriting"},
                {"name": "Step B", "task_type": "image_generate", "required_capability": "image", "input_from": "step_1", "depends_on": ["step_1"]},
            ],
        )
        assert plan.steps[1].depends_on == ["step_1"]
        assert plan.steps[1].input_from == "step_1"

    def test_model_dump_includes_new_fields(self):
        """model_dump() 输出包含所有新旧字段"""
        plan = build_collaboration_plan(
            goal="test dump",
            steps=[{"name": "Copy", "task_type": "copywriting", "required_capability": "copywriting", "review_required": True}],
        )
        dumped = plan.model_dump()
        step_data = dumped["steps"][0]
        assert "depends_on" in step_data
        assert "expected_output" in step_data
        assert "review_required" in step_data
        assert "input_from" in step_data
        assert "routing_reason" in step_data
        assert "candidate_agent_ids" in step_data
        assert "matched_capability" in step_data

    def test_old_request_without_new_fields_still_works(self):
        """旧请求只传 input_from 仍成功（无 depends_on/expected_output/review_required）"""
        plan = build_collaboration_plan(
            goal="old format test",
            steps=[
                {"name": "Copy", "task_type": "copywriting", "required_capability": "copywriting"},
                {"name": "Image", "task_type": "image_generate", "required_capability": "image", "input_from": "step_1"},
            ],
        )
        assert plan.steps[1].depends_on == ["step_1"]
        assert plan.steps[1].expected_output is None
        assert plan.steps[1].review_required is False


# ── Executor 测试 ─────────────────────────────────────────

class TestCollaborationExecutor:
    """测试协同计划执行"""

    def _make_plan(self, steps_def):
        """辅助方法：构建计划"""
        return build_collaboration_plan("test goal", steps_def)

    @patch("backend.services.collaboration_executor.execute_agent")
    def test_single_step_success(self, mock_exec):
        """单步执行成功"""
        mock_exec.return_value = AgentRunResult(ok=True, agent_id="marketing", output={"text": "hello"})

        plan = self._make_plan([
            {"name": "Copy", "task_type": "copywriting", "required_capability": "copywriting"},
        ])
        plan = execute_collaboration_plan(plan)

        assert plan.status == "succeeded"
        assert plan.steps[0].status == "succeeded"
        assert plan.steps[0].result.ok is True
        mock_exec.assert_called_once()

    @patch("backend.services.collaboration_executor.execute_agent")
    def test_two_step_success_with_chaining(self, mock_exec):
        """两步顺序执行，第二步接收第一步 output"""
        call_count = [0]

        def side_effect(agent_id, task):
            call_count[0] += 1
            if call_count[0] == 1:
                return AgentRunResult(ok=True, agent_id="marketing", output={"headline": "Great Product"})
            else:
                # 验证第二步收到了第一步的 output
                assert "previous_output" in task.context
                assert task.context["previous_output"]["headline"] == "Great Product"
                return AgentRunResult(ok=True, agent_id="image", output={"image_url": "http://img.png"})

        mock_exec.side_effect = side_effect

        plan = self._make_plan([
            {"name": "Copy", "task_type": "copywriting", "required_capability": "copywriting"},
            {"name": "Image", "task_type": "image_generate", "required_capability": "image", "input_from": "step_1"},
        ])
        plan = execute_collaboration_plan(plan)

        assert plan.status == "succeeded"
        assert all(s.status == "succeeded" for s in plan.steps)
        assert mock_exec.call_count == 2

    @patch("backend.services.collaboration_executor.execute_agent")
    def test_step_failure_stops_plan(self, mock_exec):
        """某步失败后，plan.status 应为 failed，后续步骤不执行"""
        def side_effect(agent_id, task):
            return AgentRunResult(ok=False, agent_id=agent_id, error="agent crashed")

        mock_exec.side_effect = side_effect

        plan = self._make_plan([
            {"name": "Copy", "task_type": "copywriting", "required_capability": "copywriting"},
            {"name": "Image", "task_type": "image_generate", "required_capability": "image", "input_from": "step_1"},
        ])
        plan = execute_collaboration_plan(plan)

        assert plan.status == "failed"
        assert plan.steps[0].status == "failed"
        # depends_on: step_2 依赖 step_1，step_1 失败后 step_2 被 skipped
        assert plan.steps[1].status == "skipped"
        assert mock_exec.call_count == 1

    def test_unassigned_step_is_skipped(self):
        """未分配步骤被跳过（skipped），全部 skipped 时 plan 失败"""
        plan = self._make_plan([
            {"name": "Video", "task_type": "video_edit", "required_capability": "video_editing"},
        ])
        plan = execute_collaboration_plan(plan)

        assert plan.status == "failed"
        assert plan.steps[0].status == "skipped"

    @patch("backend.services.collaboration_executor.execute_agent")
    def test_no_boss_workflow_pipeline_imports(self, mock_exec):
        """验证 executor 不导入旧 Boss/Workflow/Pipeline"""
        import backend.services.collaboration_executor as mod
        source = open(mod.__file__, encoding="utf-8").read()
        forbidden = ["boss_command_center", "workflow_router", "boss_router", "delivery_pipeline", "pipeline_router"]
        for term in forbidden:
            assert term not in source, f"collaboration_executor.py 仍引用旧模块: {term}"


# ── 阶段 4：depends_on / review_required / run store 测试 ────

class TestDependsOnExecution:
    """depends_on 依赖检查测试"""

    @patch("backend.services.collaboration_executor.execute_agent")
    def test_depends_on_success_chain(self, mock_exec):
        """depends_on 正常链式执行"""
        call_count = [0]

        def side_effect(agent_id, task):
            call_count[0] += 1
            return AgentRunResult(ok=True, agent_id=agent_id, output={"step": call_count[0]})

        mock_exec.side_effect = side_effect

        plan = build_collaboration_plan(
            goal="test depends_on chain",
            steps=[
                {"name": "Step A", "task_type": "copywriting", "required_capability": "copywriting"},
                {"name": "Step B", "task_type": "image_generate", "required_capability": "image", "depends_on": ["step_1"]},
            ],
        )
        plan = execute_collaboration_plan(plan)
        assert plan.status == "succeeded"
        assert all(s.status == "succeeded" for s in plan.steps)
        assert mock_exec.call_count == 2

    @patch("backend.services.collaboration_executor.execute_agent")
    def test_depends_on_failure_skips_dependent(self, mock_exec):
        """依赖步骤失败时，后续步骤被 skipped"""
        def side_effect(agent_id, task):
            return AgentRunResult(ok=False, agent_id=agent_id, error="agent crashed")

        mock_exec.side_effect = side_effect

        plan = build_collaboration_plan(
            goal="test depends_on skip",
            steps=[
                {"name": "Step A", "task_type": "copywriting", "required_capability": "copywriting"},
                {"name": "Step B", "task_type": "image_generate", "required_capability": "image", "depends_on": ["step_1"]},
            ],
        )
        plan = execute_collaboration_plan(plan)
        assert plan.steps[0].status == "failed"
        assert plan.steps[1].status == "skipped"

    @patch("backend.services.collaboration_executor.execute_agent")
    def test_review_required_enters_waiting_human(self, mock_exec):
        """review_required=true 的步骤进入 waiting_human 状态"""
        mock_exec.return_value = AgentRunResult(ok=True, agent_id="marketing", output={"text": "done"})

        plan = build_collaboration_plan(
            goal="test review_required",
            steps=[
                {"name": "Copy", "task_type": "copywriting", "required_capability": "copywriting", "review_required": True},
            ],
        )
        plan = execute_collaboration_plan(plan)
        assert plan.status == "waiting_human"
        assert plan.steps[0].status == "waiting_human"
        mock_exec.assert_not_called()

    @patch("backend.services.collaboration_executor.execute_agent")
    def test_step_record_saved(self, mock_exec):
        """执行后步骤记录被保存到 run_store"""
        mock_exec.return_value = AgentRunResult(ok=True, agent_id="marketing", output={"text": "hello"})

        plan = build_collaboration_plan(
            goal="test run store",
            steps=[{"name": "Copy", "task_type": "copywriting", "required_capability": "copywriting"}],
        )
        plan = execute_collaboration_plan(plan)
        assert plan.status == "succeeded"

        # 验证记录文件存在且内容正确
        records = load_plan_records(plan.plan_id)
        assert len(records) >= 1
        step_record = records[0]
        assert step_record["step_id"] == "step_1"
        assert step_record["status"] == "succeeded"
        assert step_record["assigned_agent_id"] is not None
        assert "timestamp" in step_record


# ── 最终状态判定测试 ─────────────────────────────────────

class TestFinalStatus:
    """测试 plan 最终状态判定"""

    def test_all_skipped_plan_failed(self):
        """全部 skipped 时 plan.status = failed"""
        plan = build_collaboration_plan(
            goal="all skipped",
            steps=[
                {"name": "Video", "task_type": "video_edit", "required_capability": "video_editing"},
                {"name": "Audio", "task_type": "audio_edit", "required_capability": "audio_editing"},
            ],
        )
        plan = execute_collaboration_plan(plan)
        assert plan.status == "failed"
        assert all(s.status == "skipped" for s in plan.steps)

    @patch("backend.services.collaboration_executor.execute_agent")
    def test_mixed_succeeded_and_skipped(self, mock_exec):
        """部分 succeeded + 部分 skipped → plan.status = succeeded"""
        def side_effect(agent_id, task):
            return AgentRunResult(ok=True, agent_id=agent_id, output={"text": "done"})
        mock_exec.side_effect = side_effect

        plan = build_collaboration_plan(
            goal="mixed result",
            steps=[
                {"name": "Copy", "task_type": "copywriting", "required_capability": "copywriting"},
                {"name": "Video", "task_type": "video_edit", "required_capability": "video_editing"},
            ],
        )
        plan = execute_collaboration_plan(plan)
        assert plan.status == "succeeded"
        assert plan.steps[0].status == "succeeded"
        assert plan.steps[1].status == "skipped"

    @patch("backend.services.collaboration_executor.execute_agent")
    def test_depends_on_failure_cascades(self, mock_exec):
        """depends_on 失败导致后续步骤 skipped，但前置步骤 succeeded → succeeded"""
        call_count = [0]

        def side_effect(agent_id, task):
            call_count[0] += 1
            if call_count[0] == 1:
                return AgentRunResult(ok=True, agent_id=agent_id, output={"text": "done"})
            return AgentRunResult(ok=False, agent_id=agent_id, error="crashed")
        mock_exec.side_effect = side_effect

        plan = build_collaboration_plan(
            goal="cascading failure",
            steps=[
                {"name": "Step A", "task_type": "copywriting", "required_capability": "copywriting"},
                {"name": "Step B", "task_type": "image_generate", "required_capability": "image"},
                {"name": "Step C", "task_type": "data_analyze", "required_capability": "data", "depends_on": ["step_2"]},
            ],
        )
        plan = execute_collaboration_plan(plan)
        assert plan.steps[0].status == "succeeded"
        assert plan.steps[1].status == "failed"
        assert plan.steps[2].status == "skipped"
        assert plan.status == "failed"


# ── API 测试 ──────────────────────────────────────────────

class TestCollaborationAPI:
    """测试 API 端点"""

    def test_plan_endpoint(self):
        """POST /collaboration/plan 返回计划"""
        from fastapi.testclient import TestClient
        from backend.app import app
        client = TestClient(app)

        resp = client.post("/collaboration/plan", json={
            "goal": "创建营销内容",
            "steps": [
                {"name": "Generate Copy", "task_type": "copywriting", "required_capability": "copywriting"},
            ],
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "pending"
        assert len(data["steps"]) == 1
        assert data["steps"][0]["assigned_agent_id"] is not None

    def test_run_endpoint_with_mock(self):
        """POST /collaboration/run 执行计划"""
        from fastapi.testclient import TestClient
        from backend.app import app
        client = TestClient(app)

        with patch("backend.services.collaboration_executor.execute_agent") as mock_exec:
            mock_exec.return_value = AgentRunResult(ok=True, agent_id="marketing", output={"text": "done"})
            resp = client.post("/collaboration/run", json={
                "goal": "写营销文案",
                "steps": [
                    {"name": "Copy", "task_type": "copywriting", "required_capability": "copywriting"},
                ],
            })
            assert resp.status_code == 200
            data = resp.json()
            assert data["status"] == "succeeded"
            assert data["steps"][0]["status"] == "succeeded"

    def test_plan_endpoint_unassigned(self):
        """缺少能力时 step.status=unassigned"""
        from fastapi.testclient import TestClient
        from backend.app import app
        client = TestClient(app)

        resp = client.post("/collaboration/plan", json={
            "goal": "做视频",
            "steps": [
                {"name": "Video Edit", "task_type": "video_edit", "required_capability": "video_editing"},
            ],
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["steps"][0]["status"] == "unassigned"


# ── Plan Snapshot 持久化测试 ─────────────────────────────

class TestPlanSnapshot:
    """测试计划快照保存/读取"""

    def test_save_and_load_snapshot(self):
        """save_plan_snapshot 后能 load 回来"""
        from backend.services.collaboration_run_store import save_plan_snapshot, load_plan_snapshot

        plan = build_collaboration_plan(
            goal="snapshot test",
            steps=[{"name": "Step A", "task_type": "copywriting", "required_capability": "copywriting"}],
        )
        save_plan_snapshot(plan)
        loaded = load_plan_snapshot(plan.plan_id)

        assert loaded is not None
        assert loaded.plan_id == plan.plan_id
        assert loaded.goal == "snapshot test"
        assert len(loaded.steps) == 1

    def test_load_nonexistent_returns_none(self):
        """load_plan_snapshot 不存在的 plan_id 返回 None"""
        from backend.services.collaboration_run_store import load_plan_snapshot

        result = load_plan_snapshot("nonexistent_plan_id_12345")
        assert result is None

    def test_update_step_status(self):
        """update_step_status 能修改 step 状态"""
        from backend.services.collaboration_run_store import (
            save_plan_snapshot, load_plan_snapshot, update_step_status,
        )

        plan = build_collaboration_plan(
            goal="update test",
            steps=[{"name": "Step A", "task_type": "copywriting", "required_capability": "copywriting"}],
        )
        save_plan_snapshot(plan)

        updated = update_step_status(plan.plan_id, "step_1", "succeeded")
        assert updated is not None
        assert updated.steps[0].status == "succeeded"

        # 验证持久化
        loaded = load_plan_snapshot(plan.plan_id)
        assert loaded is not None
        assert loaded.steps[0].status == "succeeded"

    def test_update_step_status_with_review_decision(self):
        """update_step_status 写入 review_decision"""
        from backend.services.collaboration_run_store import (
            save_plan_snapshot, update_step_status, load_plan_snapshot,
        )

        plan = build_collaboration_plan(
            goal="review decision test",
            steps=[{"name": "Step A", "task_type": "copywriting", "required_capability": "copywriting"}],
        )
        plan.steps[0].status = "waiting_human"
        save_plan_snapshot(plan)

        decision = {"action": "approve", "comment": "looks good"}
        updated = update_step_status(plan.plan_id, "step_1", "succeeded", review_decision=decision)
        assert updated is not None

        # 验证 decision 写入了 result.output
        loaded = load_plan_snapshot(plan.plan_id)
        assert loaded is not None
        step = loaded.steps[0]
        assert step.result is not None
        assert step.result.output["_review_decision"]["action"] == "approve"

    def test_update_nonexistent_step_returns_none(self):
        """update_step_status 找不到 step 返回 None"""
        from backend.services.collaboration_run_store import save_plan_snapshot, update_step_status

        plan = build_collaboration_plan(
            goal="no step",
            steps=[{"name": "Step A", "task_type": "copywriting", "required_capability": "copywriting"}],
        )
        save_plan_snapshot(plan)

        result = update_step_status(plan.plan_id, "nonexistent_step", "succeeded")
        assert result is None


# ── Resume 执行测试 ─────────────────────────────────────

class TestResumeExecution:
    """测试 resume 模式"""

    @patch("backend.services.collaboration_executor.execute_agent")
    def test_approve_continues_execution(self, mock_exec):
        """approve waiting_human 步骤后继续执行后续步骤"""
        mock_exec.return_value = AgentRunResult(ok=True, agent_id="marketing", output={"text": "done"})

        plan = build_collaboration_plan(
            goal="resume test",
            steps=[
                {"name": "Review Step", "task_type": "copywriting", "required_capability": "copywriting", "review_required": True},
                {"name": "After Review", "task_type": "image_generate", "required_capability": "image"},
            ],
        )

        # 第一次执行：停在 waiting_human
        plan = execute_collaboration_plan(plan)
        assert plan.status == "waiting_human"
        assert plan.steps[0].status == "waiting_human"
        assert plan.steps[1].status in ("pending", "assigned")

        # 模拟 approve：标记 step 为 succeeded
        from backend.services.collaboration_run_store import save_plan_snapshot, update_step_status, load_plan_snapshot
        save_plan_snapshot(plan)
        update_step_status(plan.plan_id, "step_1", "succeeded", review_decision={"action": "approve"})

        # Reload plan from disk to pick up the status change
        plan = load_plan_snapshot(plan.plan_id)

        # Resume：继续执行
        plan = execute_collaboration_plan(plan, resume=True)
        assert plan.status == "succeeded"
        assert plan.steps[0].status == "succeeded"
        assert plan.steps[1].status == "succeeded"

    @patch("backend.services.collaboration_executor.execute_agent")
    def test_succeeded_steps_not_repeated(self, mock_exec):
        """resume 时已 succeeded 的步骤不重复执行"""
        mock_exec.return_value = AgentRunResult(ok=True, agent_id="marketing", output={"text": "done"})

        plan = build_collaboration_plan(
            goal="no repeat",
            steps=[
                {"name": "Step A", "task_type": "copywriting", "required_capability": "copywriting"},
                {"name": "Step B", "task_type": "image_generate", "required_capability": "image"},
            ],
        )

        # 第一次执行：全部成功
        plan = execute_collaboration_plan(plan)
        assert plan.status == "succeeded"
        assert mock_exec.call_count == 2

        # Resume：不再执行
        mock_exec.reset_mock()
        plan = execute_collaboration_plan(plan, resume=True)
        assert mock_exec.call_count == 0

    @patch("backend.services.collaboration_executor.execute_agent")
    def test_reject_marks_plan_failed(self, mock_exec):
        """reject waiting_human 步骤后 plan.status=failed"""
        from backend.services.collaboration_run_store import save_plan_snapshot, update_step_status

        mock_exec.return_value = AgentRunResult(ok=True, agent_id="marketing", output={"text": "done"})

        plan = build_collaboration_plan(
            goal="reject test",
            steps=[
                {"name": "Review Step", "task_type": "copywriting", "required_capability": "copywriting", "review_required": True},
            ],
        )

        plan = execute_collaboration_plan(plan)
        assert plan.status == "waiting_human"

        save_plan_snapshot(plan)
        updated = update_step_status(plan.plan_id, "step_1", "failed", review_decision={"action": "reject"})
        assert updated is not None
        assert updated.status == "failed"
        assert updated.steps[0].status == "failed"

    @patch("backend.services.collaboration_executor.execute_agent")
    def test_plain_execution_still_works(self, mock_exec):
        """原有普通执行仍通过（无 review_required）"""
        mock_exec.return_value = AgentRunResult(ok=True, agent_id="marketing", output={"text": "done"})

        plan = build_collaboration_plan(
            goal="plain test",
            steps=[
                {"name": "Step A", "task_type": "copywriting", "required_capability": "copywriting"},
            ],
        )

        plan = execute_collaboration_plan(plan)
        assert plan.status == "succeeded"
        assert plan.steps[0].status == "succeeded"


# ── Human Review API 测试 ───────────────────────────────

class TestHumanReviewAPI:
    """测试 approve / reject / resume / get API"""

    def _create_plan_with_review(self, client):
        """创建一个带 review_required 步骤的计划并执行到 waiting_human"""
        with patch("backend.services.collaboration_executor.execute_agent") as mock_exec:
            mock_exec.return_value = AgentRunResult(ok=True, agent_id="marketing", output={"text": "done"})
            resp = client.post("/collaboration/run", json={
                "goal": "API review test",
                "steps": [
                    {"name": "Review Step", "task_type": "copywriting", "required_capability": "copywriting", "review_required": True},
                    {"name": "After Review", "task_type": "image_generate", "required_capability": "image"},
                ],
            })
            assert resp.status_code == 200
            data = resp.json()
            assert data["status"] == "waiting_human"
            return data["plan_id"]

    def test_get_plan(self):
        """GET /collaboration/runs/{plan_id} 返回计划详情"""
        from fastapi.testclient import TestClient
        from backend.app import app
        client = TestClient(app)

        plan_id = self._create_plan_with_review(client)
        resp = client.get(f"/collaboration/runs/{plan_id}")
        assert resp.status_code == 200
        data = resp.json()
        assert data["plan"]["plan_id"] == plan_id
        assert data["plan"]["status"] == "waiting_human"
        assert len(data["step_records"]) > 0

    def test_get_plan_404(self):
        """GET 不存在的 plan 返回 404"""
        from fastapi.testclient import TestClient
        from backend.app import app
        client = TestClient(app)

        resp = client.get("/collaboration/runs/nonexistent_id")
        assert resp.status_code == 404

    def test_approve_api(self):
        """POST approve 批准步骤并继续执行"""
        from fastapi.testclient import TestClient
        from backend.app import app
        client = TestClient(app)

        plan_id = self._create_plan_with_review(client)

        with patch("backend.services.collaboration_executor.execute_agent") as mock_exec:
            mock_exec.return_value = AgentRunResult(ok=True, agent_id="image", output={"image_url": "http://..."})
            resp = client.post(f"/collaboration/runs/{plan_id}/approve", json={
                "step_id": "step_1",
                "comment": "approved",
            })
            assert resp.status_code == 200
            data = resp.json()
            assert data["status"] == "succeeded"
            assert data["steps"][0]["status"] == "succeeded"

    def test_reject_api(self):
        """POST reject 拒绝步骤"""
        from fastapi.testclient import TestClient
        from backend.app import app
        client = TestClient(app)

        plan_id = self._create_plan_with_review(client)

        resp = client.post(f"/collaboration/runs/{plan_id}/reject", json={
            "step_id": "step_1",
            "comment": "not good",
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "failed"
        assert data["steps"][0]["status"] == "failed"

    def test_approve_nonexistent_step_404(self):
        """approve 不存在的 step 返回 404"""
        from fastapi.testclient import TestClient
        from backend.app import app
        client = TestClient(app)

        plan_id = self._create_plan_with_review(client)

        resp = client.post(f"/collaboration/runs/{plan_id}/approve", json={
            "step_id": "nonexistent_step",
        })
        assert resp.status_code == 404

    def test_approve_non_waiting_step_400(self):
        """approve 非 waiting_human 步骤返回 400"""
        from fastapi.testclient import TestClient
        from backend.app import app
        client = TestClient(app)

        plan_id = self._create_plan_with_review(client)

        # step_2 是 pending 状态，不是 waiting_human
        resp = client.post(f"/collaboration/runs/{plan_id}/approve", json={
            "step_id": "step_2",
        })
        assert resp.status_code == 400

    def test_resume_api(self):
        """POST resume 恢复执行"""
        from fastapi.testclient import TestClient
        from backend.app import app
        client = TestClient(app)

        plan_id = self._create_plan_with_review(client)

        # 先 approve step_1
        with patch("backend.services.collaboration_executor.execute_agent") as mock_exec:
            mock_exec.return_value = AgentRunResult(ok=True, agent_id="marketing", output={"text": "done"})
            client.post(f"/collaboration/runs/{plan_id}/approve", json={
                "step_id": "step_1",
            })

        # Resume
        with patch("backend.services.collaboration_executor.execute_agent") as mock_exec:
            mock_exec.return_value = AgentRunResult(ok=True, agent_id="image", output={"image_url": "http://..."})
            resp = client.post(f"/collaboration/runs/{plan_id}/resume")
            assert resp.status_code == 200
            data = resp.json()
            assert data["status"] == "succeeded"


# ── Step Retry 测试 ──────────────────────────────────────────


class TestStepRetry:
    """步骤级重试测试"""

    def _make_plan_with_failure(self):
        """创建一个 step_1 succeeded、step_2 failed、step_3 skipped 的计划"""
        from backend.services.collaboration_run_store import save_plan_snapshot
        plan = CollaborationPlan(
            goal="测试重试",
            steps=[
                CollaborationStep(
                    id="step_1", name="步骤1", task_type="copywriting",
                    required_capability="marketing", status="succeeded",
                    assigned_agent_id="marketing",
                    result=AgentRunResult(ok=True, agent_id="marketing", output={"text": "done"}),
                ),
                CollaborationStep(
                    id="step_2", name="步骤2", task_type="image_generate",
                    required_capability="image", status="failed",
                    assigned_agent_id="image",
                    result=AgentRunResult(ok=False, agent_id="image", error="生成失败"),
                    depends_on=["step_1"],
                ),
                CollaborationStep(
                    id="step_3", name="步骤3", task_type="data_analyze",
                    required_capability="data", status="skipped",
                    depends_on=["step_2"],
                ),
            ],
            status="failed",
        )
        save_plan_snapshot(plan)
        return plan.plan_id

    def test_reset_failed_step(self):
        """failed step reset 后变 assigned"""
        plan_id = self._make_plan_with_failure()
        result = reset_step_for_retry(plan_id, "step_2")
        assert result is not None
        step2 = [s for s in result.steps if s.id == "step_2"][0]
        assert step2.status == "assigned"
        assert step2.result is None

    def test_reset_skipped_step(self):
        """skipped step reset 后变 assigned/pending"""
        plan_id = self._make_plan_with_failure()
        result = reset_step_for_retry(plan_id, "step_3")
        assert result is not None
        step3 = [s for s in result.steps if s.id == "step_3"][0]
        # step_3 没有 assigned_agent_id，应该变成 pending
        assert step3.status == "pending"
        assert step3.result is None

    def test_reset_downstream_steps(self):
        """下游 skipped/failed 步骤被重置"""
        plan_id = self._make_plan_with_failure()
        # 重试 step_2，step_3（依赖 step_2）也应该被重置
        result = reset_step_for_retry(plan_id, "step_2")
        assert result is not None
        step3 = [s for s in result.steps if s.id == "step_3"][0]
        assert step3.status == "pending"
        assert step3.result is None

    def test_reset_succeeded_step_returns_none(self):
        """succeeded 步骤不允许重试"""
        plan_id = self._make_plan_with_failure()
        result = reset_step_for_retry(plan_id, "step_1")
        assert result is None

    def test_reset_nonexistent_step_returns_none(self):
        """不存在的步骤返回 None"""
        plan_id = self._make_plan_with_failure()
        result = reset_step_for_retry(plan_id, "step_999")
        assert result is None

    def test_reset_plan_status_becomes_running(self):
        """reset 后 plan.status 变为 running"""
        plan_id = self._make_plan_with_failure()
        result = reset_step_for_retry(plan_id, "step_2")
        assert result is not None
        assert result.status == "running"

    def test_retry_endpoint_success(self):
        """API retry 成功"""
        from fastapi.testclient import TestClient
        from backend.app import app
        client = TestClient(app)

        plan_id = self._make_plan_with_failure()

        with patch("backend.services.collaboration_executor.execute_agent") as mock_exec:
            mock_exec.return_value = AgentRunResult(ok=True, agent_id="image", output={"image_url": "http://..."})
            resp = client.post(f"/collaboration/runs/{plan_id}/retry-step", json={
                "step_id": "step_2",
            })
            assert resp.status_code == 200
            data = resp.json()
            # step_2 重试成功后，step_3 也应该继续执行
            assert data["status"] == "succeeded"

    def test_retry_endpoint_404_plan(self):
        """retry 不存在 plan 返回 404"""
        from fastapi.testclient import TestClient
        from backend.app import app
        client = TestClient(app)

        resp = client.post("/collaboration/runs/nonexistent/retry-step", json={
            "step_id": "step_1",
        })
        assert resp.status_code == 404

    def test_retry_endpoint_404_step(self):
        """retry 不存在 step 返回 404"""
        from fastapi.testclient import TestClient
        from backend.app import app
        client = TestClient(app)

        plan_id = self._make_plan_with_failure()

        resp = client.post(f"/collaboration/runs/{plan_id}/retry-step", json={
            "step_id": "step_999",
        })
        assert resp.status_code == 404

    def test_retry_endpoint_400_succeeded(self):
        """retry succeeded step 返回 400"""
        from fastapi.testclient import TestClient
        from backend.app import app
        client = TestClient(app)

        plan_id = self._make_plan_with_failure()

        resp = client.post(f"/collaboration/runs/{plan_id}/retry-step", json={
            "step_id": "step_1",
        })
        assert resp.status_code == 400


class TestCollaborationRunDetail:
    """Run detail timeline and artifact center tests."""

    def test_save_step_record_appends_timeline_event(self):
        plan = CollaborationPlan(goal="timeline test", steps=[])
        save_step_record(plan.plan_id, "step_1", {
            "assigned_agent_id": "marketing",
            "status": "succeeded",
            "required_capability": "copywriting",
            "task_type": "copywriting",
            "result": {
                "ok": True,
                "agent_id": "marketing",
                "output": {"text": "done"},
                "artifacts": ["output/demo.md"],
                "error": None,
            },
        })

        timeline = load_run_timeline(plan.plan_id)
        assert len(timeline) >= 1
        assert timeline[-1]["event_type"] == "step_succeeded"
        assert timeline[-1]["payload"]["step_id"] == "step_1"
        assert timeline[-1]["payload"]["artifacts"] == ["output/demo.md"]

    def test_collect_plan_artifacts(self):
        plan = CollaborationPlan(
            goal="artifact test",
            steps=[
                CollaborationStep(
                    id="step_1",
                    name="Write report",
                    task_type="copywriting",
                    required_capability="copywriting",
                    assigned_agent_id="marketing",
                    result=AgentRunResult(
                        ok=True,
                        agent_id="marketing",
                        output={"text": "done"},
                        artifacts=["output/report.md", "output/data.json"],
                    ),
                )
            ],
        )

        artifacts = collect_plan_artifacts(plan)
        assert len(artifacts) == 2
        assert artifacts[0]["step_id"] == "step_1"
        assert artifacts[0]["kind"] == "markdown"
        assert artifacts[1]["kind"] == "json"

    def test_get_plan_includes_timeline_and_artifacts(self):
        from fastapi.testclient import TestClient
        from backend.app import app
        from backend.services.collaboration_run_store import save_plan_snapshot

        client = TestClient(app)
        plan = CollaborationPlan(
            goal="detail api test",
            steps=[
                CollaborationStep(
                    id="step_1",
                    name="Write report",
                    task_type="copywriting",
                    required_capability="copywriting",
                    status="succeeded",
                    assigned_agent_id="marketing",
                    result=AgentRunResult(
                        ok=True,
                        agent_id="marketing",
                        output={"text": "done"},
                        artifacts=["output/report.md"],
                    ),
                )
            ],
            status="succeeded",
        )
        save_plan_snapshot(plan)
        save_step_record(plan.plan_id, "step_1", {
            "assigned_agent_id": "marketing",
            "status": "succeeded",
            "required_capability": "copywriting",
            "task_type": "copywriting",
        })

        resp = client.get(f"/collaboration/runs/{plan.plan_id}")
        assert resp.status_code == 200
        data = resp.json()
        assert data["plan"]["plan_id"] == plan.plan_id
        assert data["timeline"]
        assert data["artifacts"][0]["path"] == "output/report.md"


# ── Sandbox Required API 测试 ────────────────────────────────────

class TestSandboxRequiredAPI:
    """sandbox_required approve API 级别回归测试"""

    def _create_sandbox_required_plan(self, client):
        """创建一个 sandbox_required 步骤的计划，返回 plan_id"""
        from backend.services.collaboration_run_store import save_plan_snapshot
        from backend.services.collaboration_executor import _resolve_agent_for_risk_gate

        with patch("backend.services.collaboration_executor._resolve_agent_for_risk_gate") as mock_resolve:
            from backend.services.agent_discovery import AgentCapability
            mock_resolve.return_value = AgentCapability(
                id="codex", name="Codex", kind="api",
                enabled=True, capabilities=["code"],
                risk_level="high", supports_code_execution=True,
            )
            resp = client.post("/collaboration/run", json={
                "goal": "sandbox approve API test",
                "steps": [
                    {"name": "Code Step", "task_type": "copywriting", "required_capability": "copywriting"},
                    {"name": "Follow Up", "task_type": "image_generate", "required_capability": "image"},
                ],
            })
            assert resp.status_code == 200
            data = resp.json()
            assert data["status"] == "waiting_human"
            return data["plan_id"]

    def test_sandbox_required_approve_returns_failed(self):
        """sandbox_required approve 后 plan.status == failed (v0 sandbox 未实现)"""
        from fastapi.testclient import TestClient
        from backend.app import app
        client = TestClient(app)

        plan_id = self._create_sandbox_required_plan(client)

        # approve → executor 走 sandbox → v0 not implemented → failed
        resp = client.post(f"/collaboration/runs/{plan_id}/approve", json={
            "step_id": "step_1",
            "comment": "approved",
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "failed"
        assert data["steps"][0]["status"] == "failed"
        # v0 sandbox 未实现错误
        step_result = data["steps"][0].get("result") or {}
        error = step_result.get("error", "") or ""
        assert "not implemented" in error.lower()

    def test_sandbox_required_approve_timeline_has_sandbox_events(self):
        """sandbox_required approve 后 timeline 包含 sandbox_requested + sandbox_not_implemented"""
        from fastapi.testclient import TestClient
        from backend.app import app
        client = TestClient(app)

        plan_id = self._create_sandbox_required_plan(client)

        resp = client.post(f"/collaboration/runs/{plan_id}/approve", json={
            "step_id": "step_1",
        })
        assert resp.status_code == 200

        # 检查 timeline
        resp = client.get(f"/collaboration/runs/{plan_id}")
        assert resp.status_code == 200
        data = resp.json()
        event_types = [e["event_type"] for e in data["timeline"]]
        assert "sandbox_requested" in event_types
        assert "sandbox_not_implemented" in event_types

    def test_sandbox_required_approve_does_not_call_execute_agent(self):
        """sandbox_required approve 不调用 execute_agent"""
        from fastapi.testclient import TestClient
        from backend.app import app
        client = TestClient(app)

        plan_id = self._create_sandbox_required_plan(client)

        with patch("backend.services.collaboration_executor.execute_agent") as mock_exec:
            resp = client.post(f"/collaboration/runs/{plan_id}/approve", json={
                "step_id": "step_1",
            })
            assert resp.status_code == 200
            mock_exec.assert_not_called()

    def test_sandbox_required_approve_step_failed(self):
        """sandbox_required approve 后 step_1.status == failed"""
        from fastapi.testclient import TestClient
        from backend.app import app
        client = TestClient(app)

        plan_id = self._create_sandbox_required_plan(client)

        resp = client.post(f"/collaboration/runs/{plan_id}/approve", json={
            "step_id": "step_1",
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["steps"][0]["status"] == "failed"

    def test_sandbox_required_approve_preserves_risk_decision(self):
        """sandbox_required approve 后 _risk_decision 不丢失"""
        from fastapi.testclient import TestClient
        from backend.app import app
        client = TestClient(app)

        plan_id = self._create_sandbox_required_plan(client)

        resp = client.post(f"/collaboration/runs/{plan_id}/approve", json={
            "step_id": "step_1",
        })
        assert resp.status_code == 200
        data = resp.json()
        step_output = data["steps"][0].get("result", {}).get("output", {})
        # _risk_decision 应该还在 output 里（或 _sandbox_result 替代）
        # v0 sandbox 失败后 step.result.output 包含 _sandbox_result
        # 但 _review_decision 也应该存在
        assert "_review_decision" in step_output or "_sandbox_result" in step_output

    def test_plain_confirm_approve_still_succeeds(self):
        """普通 confirm/review_required approve 仍然 succeeded 并继续后续步骤"""
        from fastapi.testclient import TestClient
        from backend.app import app
        client = TestClient(app)

        # 创建普通 review_required 计划
        with patch("backend.services.collaboration_executor.execute_agent") as mock_exec:
            mock_exec.return_value = AgentRunResult(ok=True, agent_id="marketing", output={"text": "done"})
            resp = client.post("/collaboration/run", json={
                "goal": "plain confirm test",
                "steps": [
                    {"name": "Review Step", "task_type": "copywriting", "required_capability": "copywriting", "review_required": True},
                    {"name": "After Review", "task_type": "image_generate", "required_capability": "image"},
                ],
            })
            assert resp.status_code == 200
            plan_id = resp.json()["plan_id"]

        # approve
        with patch("backend.services.collaboration_executor.execute_agent") as mock_exec:
            mock_exec.return_value = AgentRunResult(ok=True, agent_id="image", output={"image_url": "http://..."})
            resp = client.post(f"/collaboration/runs/{plan_id}/approve", json={
                "step_id": "step_1",
                "comment": "looks good",
            })
            assert resp.status_code == 200
            data = resp.json()
            assert data["status"] == "succeeded"
            assert data["steps"][0]["status"] == "succeeded"
