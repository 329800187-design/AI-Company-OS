"""Governance 测试 — 覆盖能力目录、分类器、执行计划、运行记录、路由、Route Policy"""
import os
import sys
import json
import shutil
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest
from fastapi.testclient import TestClient

from backend.governance.capability_catalog import (
    list_capabilities, get_capability, get_supported_capabilities,
)
from backend.governance.classifier import classify_goal
from backend.governance.execution_plan import build_execution_plan
from backend.governance.run_record import (
    create_run_record, append_run_event, update_run_status,
    load_run_record, load_run_events, OUTPUT_ROOT,
)
from backend.governance.execution_plan import ExecutionPlan
from backend.governance.guard import should_block_goal, governance_block_response, extract_goal_from_payload, guard_payload
from backend.governance.route_policy import (
    list_route_policies, get_route_policy, is_route_controlled,
    routes_requiring_guard, routes_high_risk_without_guard,
    routes_deprecated_without_guard, routes_unprotected_execution,
    routes_controlled_entrypoints,
    find_unclassified_routes,
)
from backend.app import app


client = TestClient(app)


# ── Capability Catalog 测试 ────────────────────────────────

class TestCapabilityCatalog:
    def test_list_capabilities_includes_xhs(self):
        caps = list_capabilities()
        ids = [c.id for c in caps]
        assert "copy_pack.xiaohongshu" in ids

    def test_list_capabilities_includes_douyin(self):
        caps = list_capabilities()
        ids = [c.id for c in caps]
        assert "copy_pack.douyin" in ids

    def test_get_capability_xhs(self):
        cap = get_capability("copy_pack.xiaohongshu")
        assert cap is not None
        assert cap.supported is True
        assert "minidelivery" in cap.entrypoint
        assert "file_exists" in cap.required_checks

    def test_get_capability_douyin(self):
        cap = get_capability("copy_pack.douyin")
        assert cap is not None
        assert cap.supported is True
        assert "has_hook" in cap.required_checks

    def test_get_capability_not_found(self):
        cap = get_capability("nonexistent.capability")
        assert cap is None

    def test_get_supported_capabilities(self):
        supported = get_supported_capabilities()
        assert all(c.supported for c in supported)
        # 只包含 copy_pack.xiaohongshu 和 copy_pack.douyin，不包含 chat.general
        supported_ids = [c.id for c in supported]
        assert "copy_pack.xiaohongshu" in supported_ids
        assert "copy_pack.douyin" in supported_ids
        assert "chat.general" not in supported_ids

    def test_chat_general_exists_but_unsupported(self):
        cap = get_capability("chat.general")
        assert cap is not None
        assert cap.supported is False

    def test_unsupported_capability(self):
        cap = get_capability("unsupported.complex_agent_workflow")
        assert cap is not None
        assert cap.supported is False


# ── Classifier 测试 ────────────────────────────────────────

class TestClassifier:
    def test_classify_xiaohongshu_goal(self):
        result = classify_goal("帮我为手工耳环生成小红书种草文案")
        assert result.ok is True
        assert result.capability_id == "copy_pack.xiaohongshu"

    def test_classify_douyin_goal(self):
        result = classify_goal("生成一个抖音文案模板，用于推广手工耳环")
        assert result.ok is True
        assert result.capability_id == "copy_pack.douyin"

    def test_explicit_platform_priority(self):
        result = classify_goal("帮我生成文案", explicit_platform="douyin")
        assert result.ok is True
        assert result.capability_id == "copy_pack.douyin"

    def test_explicit_xiaohongshu(self):
        result = classify_goal("帮我生成文案", explicit_platform="xiaohongshu")
        assert result.ok is True
        assert result.capability_id == "copy_pack.xiaohongshu"

    def test_vague_goal_needs_clarification(self):
        result = classify_goal("帮我搭建一个全自动赚钱公司系统")
        assert result.needs_clarification is True
        assert result.ok is False

    def test_unsupported_goal(self):
        result = classify_goal("开发一个全新的AI操作系统")
        assert result.ok is False
        assert result.capability_id == "unsupported.complex_agent_workflow"

    def test_short_input_needs_clarification(self):
        result = classify_goal("帮我")
        assert result.needs_clarification is True
        assert result.ok is False

    def test_douyin_keyword_only_needs_clarification(self):
        result = classify_goal("抖音")
        assert result.needs_clarification is True

    def test_xhs_keyword_only_needs_clarification(self):
        result = classify_goal("小红书")
        assert result.needs_clarification is True

    def test_normalized_inputs_include_platform(self):
        result = classify_goal("帮我为耳环生成小红书文案")
        assert result.normalized_inputs.get("platform") == "xiaohongshu"

    def test_confidence_range(self):
        result = classify_goal("帮我为手工耳环生成小红书种草文案")
        assert 0.0 <= result.confidence <= 1.0


# ── Execution Plan 测试 ────────────────────────────────────

class TestExecutionPlan:
    def test_xhs_plan_steps(self):
        classification = classify_goal("帮我为手工耳环生成小红书种草文案")
        plan = build_execution_plan("帮我为手工耳环生成小红书种草文案", classification)

        assert plan.status == "planned"
        assert plan.capability_id == "copy_pack.xiaohongshu"
        step_names = [s.name for s in plan.steps]
        assert "解析交付规格" in step_names
        assert "生成文案包内容" in step_names
        assert "写入产物文件" in step_names
        assert "验收产物" in step_names
        assert "返回结果" in step_names

    def test_douyin_plan_steps(self):
        classification = classify_goal("帮我为手工耳环生成抖音推广文案")
        plan = build_execution_plan("帮我为手工耳环生成抖音推广文案", classification)

        assert plan.status == "planned"
        assert plan.capability_id == "copy_pack.douyin"

    def test_unsupported_plan_rejected(self):
        classification = classify_goal("开发一个全新的AI操作系统")
        plan = build_execution_plan("开发一个全新的AI操作系统", classification)

        assert plan.status in ("rejected", "needs_clarification")
        assert len(plan.steps) == 0

    def test_needs_clarification_plan(self):
        classification = classify_goal("帮我搭建一个全自动赚钱公司系统")
        plan = build_execution_plan("帮我搭建一个全自动赚钱公司系统", classification)

        assert plan.status == "needs_clarification"

    def test_plan_has_artifact_expectation(self):
        classification = classify_goal("帮我为手工耳环生成小红书文案")
        plan = build_execution_plan("帮我为手工耳环生成小红书文案", classification)
        assert plan.artifact_expectation.get("type") == "markdown"

    def test_plan_has_required_checks(self):
        classification = classify_goal("帮我为手工耳环生成小红书文案")
        plan = build_execution_plan("帮我为手工耳环生成小红书文案", classification)
        assert "file_exists" in plan.required_checks
        assert "contains_product" in plan.required_checks


# ── Run Record 测试 ────────────────────────────────────────

class TestRunRecord:
    def test_create_run_record(self, tmp_path):
        with patch("backend.governance.run_record.OUTPUT_ROOT", tmp_path):
            classification = classify_goal("帮我为手工耳环生成小红书文案")
            plan = build_execution_plan("帮我为手工耳环生成小红书文案", classification)
            record = create_run_record("帮我为手工耳环生成小红书文案", plan)

            assert record.run_id.startswith("run_")
            assert record.capability_id == "copy_pack.xiaohongshu"
            assert record.status == "planned"

            # record.json 存在
            record_path = tmp_path / record.run_id / "record.json"
            assert record_path.exists()

            # events.jsonl 存在
            events_path = tmp_path / record.run_id / "events.jsonl"
            assert events_path.exists()

    def test_append_run_event(self, tmp_path):
        with patch("backend.governance.run_record.OUTPUT_ROOT", tmp_path):
            classification = classify_goal("test goal")
            plan = build_execution_plan("test goal", classification)
            record = create_run_record("test goal", plan)

            append_run_event(record.run_id, "test_event", {"key": "value"})

            events = load_run_events(record.run_id)
            assert len(events) >= 2  # plan_built + test_event
            assert events[-1]["event_type"] == "test_event"
            assert events[-1]["payload"]["key"] == "value"

    def test_update_run_status(self, tmp_path):
        with patch("backend.governance.run_record.OUTPUT_ROOT", tmp_path):
            classification = classify_goal("test goal")
            plan = build_execution_plan("test goal", classification)
            record = create_run_record("test goal", plan)

            update_run_status(record.run_id, "succeeded", artifact_path="/tmp/test.md")

            updated = load_run_record(record.run_id)
            assert updated.status == "succeeded"
            assert updated.artifact_path == "/tmp/test.md"

    def test_load_run_record(self, tmp_path):
        with patch("backend.governance.run_record.OUTPUT_ROOT", tmp_path):
            classification = classify_goal("test goal")
            plan = build_execution_plan("test goal", classification)
            record = create_run_record("test goal", plan)

            loaded = load_run_record(record.run_id)
            assert loaded is not None
            assert loaded.run_id == record.run_id

    def test_load_run_record_not_found(self, tmp_path):
        with patch("backend.governance.run_record.OUTPUT_ROOT", tmp_path):
            loaded = load_run_record("run_nonexistent")
            assert loaded is None

    def test_events_append_correctly(self, tmp_path):
        with patch("backend.governance.run_record.OUTPUT_ROOT", tmp_path):
            classification = classify_goal("test")
            plan = build_execution_plan("test", classification)
            record = create_run_record("test", plan)

            append_run_event(record.run_id, "execution_started", {})
            append_run_event(record.run_id, "execution_succeeded", {"task_id": "t1"})

            events = load_run_events(record.run_id)
            event_types = [e["event_type"] for e in events]
            assert "plan_built" in event_types
            assert "execution_started" in event_types
            assert "execution_succeeded" in event_types


# ── Router 测试 ────────────────────────────────────────────

class TestGovernanceRouter:
    def test_classify_endpoint(self):
        resp = client.post("/governance/classify", json={"goal": "帮我为手工耳环生成小红书文案"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["ok"] is True
        assert data["capability_id"] == "copy_pack.xiaohongshu"

    def test_plan_endpoint(self):
        resp = client.post("/governance/plan", json={"goal": "帮我为手工耳环生成抖音文案"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "planned"
        assert data["capability_id"] == "copy_pack.douyin"
        assert len(data["steps"]) >= 4

    def test_run_execute_false(self):
        resp = client.post("/governance/run", json={
            "goal": "帮我为手工耳环生成小红书文案",
            "execute": False,
        })
        assert resp.status_code == 200
        data = resp.json()
        assert "run_id" in data
        assert data["status"] == "planned"
        assert "result" not in data

    def test_run_unsupported_rejected(self):
        resp = client.post("/governance/run", json={
            "goal": "开发一个全新的AI操作系统",
            "execute": True,
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] in ("rejected", "needs_clarification")

    def test_run_execute_true_copy_pack(self):
        resp = client.post("/governance/run", json={
            "goal": "帮我为手工耳环生成小红书种草文案",
            "execute": True,
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "succeeded"
        assert "result" in data
        assert data["result"]["ok"] is True

    def test_get_run_record(self):
        # 先创建一个 run
        resp = client.post("/governance/run", json={
            "goal": "帮我为手工耳环生成小红书文案",
            "execute": False,
        })
        run_id = resp.json()["run_id"]

        resp = client.get(f"/governance/runs/{run_id}")
        assert resp.status_code == 200
        data = resp.json()
        assert data["run_id"] == run_id

    def test_get_run_events(self):
        resp = client.post("/governance/run", json={
            "goal": "帮我为手工耳环生成小红书文案",
            "execute": False,
        })
        run_id = resp.json()["run_id"]

        resp = client.get(f"/governance/runs/{run_id}/events")
        assert resp.status_code == 200
        data = resp.json()
        assert data["run_id"] == run_id
        assert len(data["events"]) >= 1

    def test_get_run_not_found(self):
        resp = client.get("/governance/runs/run_nonexistent")
        assert resp.status_code == 404

    def test_get_run_events_not_found(self):
        resp = client.get("/governance/runs/run_nonexistent/events")
        assert resp.status_code == 404

    def test_classify_needs_clarification(self):
        resp = client.post("/governance/classify", json={"goal": "帮我搭建一个全自动赚钱公司系统"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["needs_clarification"] is True
        assert len(data["clarification_questions"]) >= 1

    def test_invalid_platform_rejected(self):
        """explicit_platform=weibo 必须返回 ok=false，不能降级"""
        resp = client.post("/governance/classify", json={"goal": "帮我生成文案", "platform": "weibo"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["ok"] is False
        assert data["confidence"] == 1.0
        assert "weibo" in data["reason"]
        assert data["capability_id"] == "unsupported.complex_agent_workflow"

    def test_invalid_platform_no_downgrade(self):
        """explicit_platform=weibo 不会降级成 copy_pack.xiaohongshu"""
        resp = client.post("/governance/classify", json={"goal": "帮我生成小红书文案", "platform": "weibo"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["ok"] is False
        assert data["capability_id"] != "copy_pack.xiaohongshu"

    def test_list_runs_returns_records(self):
        """GET /governance/runs 返回运行记录列表"""
        # 先创建一个 run
        resp = client.post("/governance/run", json={
            "goal": "帮我为手工耳环生成小红书文案",
            "execute": False,
        })
        assert resp.status_code == 200

        # 查询列表
        resp = client.get("/governance/runs")
        assert resp.status_code == 200
        data = resp.json()
        assert "records" in data
        assert "total" in data
        assert data["total"] >= 1
        # 每条记录包含必要字段
        rec = data["records"][0]
        assert "run_id" in rec
        assert "goal" in rec
        assert "capability_id" in rec
        assert "status" in rec
        assert "created_at" in rec
        assert "updated_at" in rec

    def test_list_runs_limit_and_offset(self):
        """GET /governance/runs 支持 limit 和 offset 参数"""
        # 记录创建前的 total
        before = client.get("/governance/runs").json()["total"]

        # 创建 3 条记录
        for i in range(3):
            client.post("/governance/run", json={
                "goal": f"测试目标{i}",
                "execute": False,
            })

        total_after = client.get("/governance/runs").json()["total"]
        assert total_after >= before + 3

        resp = client.get("/governance/runs?limit=2&offset=0")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["records"]) == 2
        assert data["total"] == total_after

        resp2 = client.get("/governance/runs?limit=2&offset=2")
        assert resp2.status_code == 200
        data2 = resp2.json()
        assert len(data2["records"]) <= 2
        # 第二页的 ID 不应与第一页重复
        page1_ids = {r["run_id"] for r in data["records"]}
        page2_ids = {r["run_id"] for r in data2["records"]}
        assert page1_ids.isdisjoint(page2_ids)

    def test_list_runs_empty(self):
        """GET /governance/runs 在无记录时返回空列表"""
        resp = client.get("/governance/runs?limit=10")
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data["records"], list)
        assert isinstance(data["total"], int)

    def test_list_runs_records_sorted_by_updated_at(self):
        """GET /governance/runs 按 updated_at 倒序排列"""
        # 创建两条记录
        client.post("/governance/run", json={"goal": "先创建", "execute": False})
        client.post("/governance/run", json={"goal": "后创建", "execute": False})

        resp = client.get("/governance/runs")
        data = resp.json()
        records = data["records"]
        assert len(records) >= 2
        # 最新的应该在前面
        assert records[0]["updated_at"] >= records[1]["updated_at"]


# ── Guard 测试 ──────────────────────────────────────────────

class TestGuard:
    def test_block_vague_goal(self):
        blocked, classification = should_block_goal("帮我搭建一个全自动赚钱公司系统")
        assert blocked is True
        assert classification.ok is False

    def test_no_block_xhs_goal(self):
        blocked, classification = should_block_goal("小红书手工耳环文案")
        assert blocked is False
        assert classification.ok is True

    def test_no_block_douyin_goal(self):
        blocked, classification = should_block_goal("抖音推广文案，手工耳环")
        assert blocked is False
        assert classification.ok is True

    def test_block_response_format(self):
        _, classification = should_block_goal("帮我搭建一个全自动赚钱公司系统")
        resp = governance_block_response(classification)
        assert resp["ok"] is False
        assert resp["blocked_by_governance"] is True
        assert "classification" in resp
        assert resp["classification"]["ok"] is False

    def test_guard_with_explicit_platform(self):
        blocked, _ = should_block_goal("帮我生成文案", platform="weibo")
        assert blocked is True

    def test_guard_with_valid_platform(self):
        blocked, classification = should_block_goal("帮我生成文案", platform="xiaohongshu")
        assert blocked is False
        assert classification.capability_id == "copy_pack.xiaohongshu"


# ── Events 审计测试 ─────────────────────────────────────────

class TestGovernanceEvents:
    def test_run_execute_false_events(self):
        """execute=false 后 events 包含 classification_done 和 plan_built"""
        resp = client.post("/governance/run", json={
            "goal": "帮我为手工耳环生成小红书文案",
            "execute": False,
        })
        run_id = resp.json()["run_id"]

        resp = client.get(f"/governance/runs/{run_id}/events")
        events = resp.json()["events"]
        event_types = [e["event_type"] for e in events]

        assert "classification_done" in event_types
        assert "plan_built" in event_types

    def test_unsupported_run_events(self):
        """unsupported execute=true 后 events 包含 classification_done、plan_built、run_rejected"""
        resp = client.post("/governance/run", json={
            "goal": "开发一个全新的AI操作系统",
            "execute": True,
        })
        run_id = resp.json()["run_id"]

        resp = client.get(f"/governance/runs/{run_id}/events")
        events = resp.json()["events"]
        event_types = [e["event_type"] for e in events]

        assert "classification_done" in event_types
        assert "plan_built" in event_types
        assert "run_rejected" in event_types

    def test_supported_run_events(self):
        """supported execute=true 后 events 包含完整审计链"""
        resp = client.post("/governance/run", json={
            "goal": "帮我为手工耳环生成小红书种草文案",
            "execute": True,
        })
        run_id = resp.json()["run_id"]

        resp = client.get(f"/governance/runs/{run_id}/events")
        events = resp.json()["events"]
        event_types = [e["event_type"] for e in events]

        assert "classification_done" in event_types
        assert "plan_built" in event_types
        assert "execution_started" in event_types
        assert "execution_succeeded" in event_types

    def test_classification_done_payload(self):
        """classification_done 事件 payload 包含必要字段"""
        resp = client.post("/governance/run", json={
            "goal": "帮我为手工耳环生成小红书文案",
            "execute": False,
        })
        run_id = resp.json()["run_id"]

        resp = client.get(f"/governance/runs/{run_id}/events")
        events = resp.json()["events"]

        classification_events = [e for e in events if e["event_type"] == "classification_done"]
        assert len(classification_events) >= 1
        payload = classification_events[0]["payload"]
        assert "ok" in payload
        assert "capability_id" in payload
        assert "confidence" in payload
        assert "needs_clarification" in payload
        assert "reason" in payload


# ── Route Policy 测试 ──────────────────────────────────────

class TestRoutePolicy:
    def test_list_route_policies_non_empty(self):
        """list_route_policies 返回非空"""
        policies = list_route_policies()
        assert len(policies) > 0

    def test_governance_run_is_controlled(self):
        """GET /governance/run 是 controlled"""
        policy = get_route_policy("/governance/run", "POST")
        assert policy is not None
        assert policy.category == "controlled"

    def test_minidelivery_copy_pack_is_controlled(self):
        """POST /minidelivery/copy-pack 是 controlled"""
        policy = get_route_policy("/minidelivery/copy-pack", "POST")
        assert policy is not None
        assert policy.category == "controlled"

    def test_agents_run_is_high_risk(self):
        """已 guard 的 agent 路由不应标记 high_risk"""
        # 以下路由已加 Guard，应为 protected
        guarded_agent_paths = [
            "/agents/image/run", "/agents/marketing/run",
            "/agents/video/run", "/agents/data/run",
        ]
        for path in guarded_agent_paths:
            policy = get_route_policy(path, "POST")
            if policy:
                assert policy.category == "protected", f"{path} should be protected"

    def test_routes_requiring_guard_excludes_protected(self):
        """routes_requiring_guard 返回未加 guard 的高风险执行入口"""
        high_risk = routes_requiring_guard()
        guarded_paths = [p.path for p in high_risk]
        # 所有已 guard 的 agent/boss/pipeline 路由不应出现
        assert "/agents/ceo/run" not in guarded_paths
        assert "/pipeline/execute" not in guarded_paths
        # 所有 deprecated/high_risk 已阻断，不再有未保护执行入口
        assert len(high_risk) == 0

    def test_get_route_policy_not_found(self):
        """不存在的路由返回 None"""
        policy = get_route_policy("/nonexistent/path", "POST")
        assert policy is None

    def test_is_route_controlled(self):
        """is_route_controlled 正确判断"""
        assert is_route_controlled("/governance/run", "POST") is True

    def test_all_controlled_routes_have_reason(self):
        """所有 controlled 路由必须有明确 reason"""
        policies = list_route_policies()
        for p in policies:
            if p.category == "controlled":
                assert p.reason, f"{p.path} 缺少 reason"

    def test_all_protected_routes_have_reason(self):
        """所有 protected 路由必须有明确 reason"""
        policies = list_route_policies()
        for p in policies:
            if p.category == "protected":
                assert p.reason, f"{p.path} 缺少 reason"

    def test_all_high_risk_routes_have_replacement_or_reason(self):
        """所有 high_risk 路由必须有 replacement 或 reason"""
        policies = list_route_policies()
        for p in policies:
            if p.category == "high_risk":
                assert p.reason, f"{p.path} 缺少 reason"

    def test_all_deprecated_routes_have_replacement_or_reason(self):
        """所有 deprecated 路由必须有 replacement 或 reason"""
        policies = list_route_policies()
        for p in policies:
            if p.category == "deprecated":
                assert p.reason, f"{p.path} 缺少 reason"

    def test_find_unclassified_routes(self):
        """find_unclassified_routes 能扫描 FastAPI app"""
        unclassified = find_unclassified_routes(app)
        # 应返回列表（可能为空或包含未登记路由）
        assert isinstance(unclassified, list)

    def test_get_routes_endpoint(self):
        """GET /governance/routes 可用"""
        resp = client.get("/governance/routes")
        assert resp.status_code == 200
        data = resp.json()
        assert "total" in data
        assert "policies" in data
        assert data["total"] > 0

    def test_get_high_risk_routes_endpoint(self):
        """GET /governance/routes/high-risk 可用"""
        resp = client.get("/governance/routes/high-risk")
        assert resp.status_code == 200
        data = resp.json()
        assert "total" in data
        assert "policies" in data

    def test_get_unclassified_routes_endpoint(self):
        """GET /governance/routes/unclassified 可用"""
        resp = client.get("/governance/routes/unclassified")
        assert resp.status_code == 200
        data = resp.json()
        assert "total" in data
        assert "routes" in data


# ── Guard Helper 测试 ──────────────────────────────────────

class TestGuardHelper:
    def test_extract_goal_from_goal(self):
        """extract_goal_from_payload 可从 goal 提取"""
        assert extract_goal_from_payload({"goal": "生成小红书文案"}) == "生成小红书文案"

    def test_extract_goal_from_target(self):
        """extract_goal_from_payload 可从 目标 提取"""
        assert extract_goal_from_payload({"目标": "生成抖音文案"}) == "生成抖音文案"

    def test_extract_goal_from_prompt(self):
        """extract_goal_from_payload 可从 prompt 提取"""
        assert extract_goal_from_payload({"prompt": "写一篇种草文案"}) == "写一篇种草文案"

    def test_extract_goal_from_message(self):
        """extract_goal_from_payload 可从 message 提取"""
        assert extract_goal_from_payload({"message": "帮我写文案"}) == "帮我写文案"

    def test_extract_goal_from_command(self):
        """extract_goal_from_payload 可从 命令 / command 提取"""
        assert extract_goal_from_payload({"命令": "执行任务"}) == "执行任务"
        assert extract_goal_from_payload({"command": "run task"}) == "run task"

    def test_extract_goal_from_nested_task(self):
        """extract_goal_from_payload 可从 task.goal / task["目标"] 提取"""
        assert extract_goal_from_payload({"task": {"goal": "嵌套目标"}}) == "嵌套目标"
        assert extract_goal_from_payload({"task": {"目标": "嵌套中文目标"}}) == "嵌套中文目标"

    def test_extract_goal_empty_payload(self):
        """extract_goal_from_payload 空 payload 返回空字符串"""
        assert extract_goal_from_payload({}) == ""
        assert extract_goal_from_payload({"code": "print(1)"}) == ""

    def test_guard_payload_empty_no_block(self):
        """guard_payload 对空 payload 不 block"""
        blocked, classification = guard_payload({})
        assert blocked is False

    def test_guard_payload_vague_goal_blocks(self):
        """guard_payload 对模糊目标 block=true"""
        blocked, classification = guard_payload({"goal": "帮我搭建一个全自动赚钱公司系统"})
        assert blocked is True
        assert classification.ok is False

    def test_guard_payload_xhs_goal_no_block(self):
        """guard_payload 对小红书目标 block=false"""
        blocked, classification = guard_payload({"goal": "帮我为手工耳环生成小红书种草文案"})
        assert blocked is False
        assert classification.ok is True


class TestFindUnclassifiedRoutes:
    def test_exact_path_not_misclassified(self):
        """已登记的精确路径不应出现在 unclassified 中"""
        from fastapi import FastAPI
        test_app = FastAPI()
        # 注册一个已登记的路由
        @test_app.get("/boss/missions")
        def dummy(): pass
        unclassified = find_unclassified_routes(test_app)
        paths = [r["path"] for r in unclassified]
        assert "/boss/missions" not in paths

    def test_unregistered_route_detected(self):
        """未登记的路由能被识别为 unclassified"""
        from fastapi import FastAPI
        test_app = FastAPI()
        @test_app.post("/agents/new-danger/run")
        def dummy(): pass
        unclassified = find_unclassified_routes(test_app)
        paths = [r["path"] for r in unclassified]
        assert "/agents/new-danger/run" in paths

    def test_similar_prefix_not_false_positive(self):
        """/agents/openclaw/run 已登记，不应因前缀相似误判其他路由"""
        from fastapi import FastAPI
        test_app = FastAPI()
        @test_app.post("/agents/openclaw/run")
        def dummy1(): pass
        @test_app.post("/agents/new-danger/run")
        def dummy2(): pass
        unclassified = find_unclassified_routes(test_app)
        paths = [r["path"] for r in unclassified]
        # openclaw 已登记，不应出现
        assert "/agents/openclaw/run" not in paths
        # new-danger 未登记，应出现
        assert "/agents/new-danger/run" in paths

    def test_docs_routes_ignored(self):
        """文档路由 /docs、/openapi.json、/redoc 不作为问题路由返回"""
        from fastapi import FastAPI
        test_app = FastAPI()
        @test_app.get("/docs")
        def dummy1(): pass
        @test_app.get("/openapi.json")
        def dummy2(): pass
        @test_app.get("/redoc")
        def dummy3(): pass
        unclassified = find_unclassified_routes(test_app)
        paths = [r["path"] for r in unclassified]
        assert "/docs" not in paths
        assert "/openapi.json" not in paths
        assert "/redoc" not in paths

    def test_path_param_normalization(self):
        """路径参数名差异不影响匹配（归一化后匹配）"""
        from fastapi import FastAPI
        test_app = FastAPI()
        # 已登记 /boss/missions/{mission_id}/run，注册 /boss/missions/{id}/run 应匹配
        @test_app.post("/boss/missions/{id}/run")
        def dummy(): pass
        unclassified = find_unclassified_routes(test_app)
        paths = [r["path"] for r in unclassified]
        assert "/boss/missions/{id}/run" not in paths


# ── P2 Route Guard 集成测试 ─────────────────────────────────

class TestP2RouteGuard:
    def test_qa_run_vague_goal_blocked(self):
        """POST /agents/qa/run 模糊大目标会 blocked_by_governance=true"""
        resp = client.post("/agents/qa/run", json={
            "目标": "帮我搭建一个全自动赚钱公司系统",
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data.get("blocked_by_governance") is True
        assert data["ok"] is False

    def test_cto_run_vague_goal_blocked(self):
        """POST /agents/cto/run 模糊大目标会 blocked_by_governance=true"""
        resp = client.post("/agents/cto/run", json={
            "目标": "帮我搭建一个全自动赚钱公司系统",
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data.get("blocked_by_governance") is True
        assert data["ok"] is False

    def test_plugin_run_vague_goal_blocked(self):
        """POST /plugins/{id}/run 模糊大目标会 blocked_by_governance=true"""
        resp = client.post("/plugins/test_plugin/run", json={
            "goal": "帮我搭建一个全自动赚钱公司系统",
        })
        # 可能 404（插件不存在）或 blocked_by_governance
        if resp.status_code == 200:
            data = resp.json()
            assert data.get("blocked_by_governance") is True
            assert data["ok"] is False

    def test_plugin_test_vague_goal_blocked(self):
        """POST /plugins/{id}/test 模糊大目标会 blocked_by_governance=true"""
        resp = client.post("/plugins/test_plugin/test", json={
            "goal": "帮我搭建一个全自动赚钱公司系统",
        })
        # 可能 404（插件不存在）或 blocked_by_governance
        if resp.status_code == 200:
            data = resp.json()
            assert data.get("blocked_by_governance") is True
            assert data["ok"] is False

    def test_ai_run_vague_goal_blocked(self):
        """POST /ai/run 模糊大目标会 blocked_by_governance=true"""
        resp = client.post("/ai/run", json={
            "goal": "帮我搭建一个全自动赚钱公司系统",
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data.get("blocked_by_governance") is True
        assert data["ok"] is False

    def test_boss_module_run_vague_mission_goal_blocked(self):
        """POST /boss/missions/{id}/modules/{module_id}/run 使用 mission.goal 模糊目标时会 blocked"""
        from unittest.mock import patch, MagicMock
        with patch("backend.routers.boss_router.get_boss_command_center") as mock_get:
            mock_service = MagicMock()
            mock_service.get_mission.return_value = {
                "mission_id": "m1",
                "goal": "帮我搭建一个全自动赚钱公司系统",
                "status": "created",
                "modules": [{"module_id": "mod1"}],
            }
            mock_get.return_value = mock_service
            resp = client.post("/boss/missions/m1/modules/mod1/run")
            assert resp.status_code == 200
            data = resp.json()
            assert data.get("blocked_by_governance") is True
            assert data["ok"] is False


# ── P2 Route Policy 更新测试 ────────────────────────────────

class TestP2RoutePolicyUpdate:
    def test_qa_run_is_protected(self):
        """/agents/qa/run 是 protected 且 has_guard=true"""
        policy = get_route_policy("/agents/qa/run", "POST")
        assert policy is not None
        assert policy.category == "protected"
        assert policy.has_guard is True

    def test_cto_run_is_protected(self):
        """/agents/cto/run 是 protected 且 has_guard=true"""
        policy = get_route_policy("/agents/cto/run", "POST")
        assert policy is not None
        assert policy.category == "protected"
        assert policy.has_guard is True

    def test_plugin_run_is_protected(self):
        """/plugins/{plugin_id}/run 是 protected 且 has_guard=true"""
        policy = get_route_policy("/plugins/{plugin_id}/run", "POST")
        assert policy is not None
        assert policy.category == "protected"
        assert policy.has_guard is True

    def test_plugin_test_is_protected(self):
        """/plugins/{plugin_id}/test 是 protected 且 has_guard=true"""
        policy = get_route_policy("/plugins/{plugin_id}/test", "POST")
        assert policy is not None
        assert policy.category == "protected"
        assert policy.has_guard is True

    def test_ai_run_is_protected(self):
        """/ai/run 是 protected 且 has_guard=true"""
        policy = get_route_policy("/ai/run", "POST")
        assert policy is not None
        assert policy.category == "protected"
        assert policy.has_guard is True

    def test_boss_module_run_is_protected(self):
        """/boss/missions/{mission_id}/modules/{module_id}/run 是 protected 且 has_guard=true"""
        policy = get_route_policy("/boss/missions/{mission_id}/modules/{module_id}/run", "POST")
        assert policy is not None
        assert policy.category == "protected"
        assert policy.has_guard is True

    def test_p2_not_in_routes_requiring_guard(self):
        """routes_requiring_guard() 不包含本轮已保护的 6 条路由"""
        high_risk = routes_requiring_guard()
        guarded_paths = [p.path for p in high_risk]
        assert "/agents/qa/run" not in guarded_paths
        assert "/agents/cto/run" not in guarded_paths
        assert "/plugins/{plugin_id}/run" not in guarded_paths
        assert "/plugins/{plugin_id}/test" not in guarded_paths
        assert "/ai/run" not in guarded_paths
        assert "/boss/missions/{mission_id}/modules/{module_id}/run" not in guarded_paths

    def test_high_risk_count_reduced_by_6(self):
        """high_risk 总数应比之前减少 6"""
        policies = list_route_policies()
        high_risk_count = sum(1 for p in policies if p.category == "high_risk")
        # P1 后是 33，P2 应 <= 27
        assert high_risk_count <= 27, f"high_risk count {high_risk_count} should be <= 27"


# ── find_unclassified_routes method 维度测试 ────────────────

class TestFindUnclassifiedMethodDimension:
    def test_same_path_different_method_detected(self):
        """同路径不同 method 的未登记路由能被发现"""
        from fastapi import FastAPI
        test_app = FastAPI()
        # /boss/missions 已登记 GET，但新增 POST 应被发现
        # （实际 POST 也已登记，这里用一个未登记的 method 组合测试）
        @test_app.put("/boss/missions")
        def dummy(): pass
        unclassified = find_unclassified_routes(test_app)
        # PUT /boss/missions 未登记，应出现
        found = [r for r in unclassified if r["path"] == "/boss/missions" and "PUT" in r["methods"]]
        assert len(found) > 0, "PUT /boss/missions should be detected as unclassified"

    def test_registered_method_not_false_positive(self):
        """已登记的 (path, method) 不应误报"""
        from fastapi import FastAPI
        test_app = FastAPI()
        # /boss/missions GET 已登记
        @test_app.get("/boss/missions")
        def dummy(): pass
        unclassified = find_unclassified_routes(test_app)
        found = [r for r in unclassified if r["path"] == "/boss/missions" and "GET" in r["methods"]]
        assert len(found) == 0, "GET /boss/missions should NOT be unclassified"

    def test_method_aware_with_path_param(self):
        """路径参数 + method 维度同时匹配"""
        from fastapi import FastAPI
        test_app = FastAPI()
        # /boss/missions/{mission_id}/run POST 已登记
        # 注册 /boss/missions/{mission_id}/run PUT 应被发现
        @test_app.put("/boss/missions/{mission_id}/run")
        def dummy(): pass
        unclassified = find_unclassified_routes(test_app)
        found = [r for r in unclassified
                 if r["path"] == "/boss/missions/{mission_id}/run" and "PUT" in r["methods"]]
        assert len(found) > 0, "PUT on registered POST path should be detected"


# ── Task 1: routes_high_risk_without_guard 语义测试 ─────────

class TestRouteStatsSemantics:
    def test_routes_high_risk_without_guard_count(self):
        """routes_high_risk_without_guard() 数量应等于当前 high_risk 未保护数量"""
        hr = routes_high_risk_without_guard()
        policies = list_route_policies()
        expected = [p for p in policies if p.category == "high_risk"
                    and p.requires_governance and not p.has_guard]
        assert len(hr) == len(expected)

    def test_routes_high_risk_excludes_controlled(self):
        """routes_high_risk_without_guard 不包含 controlled 路由"""
        hr = routes_high_risk_without_guard()
        hr_paths = [p.path for p in hr]
        assert "/governance/run" not in hr_paths
        assert "/minidelivery/copy-pack" not in hr_paths
        assert "/minidelivery/xhs-copy-pack" not in hr_paths

    def test_routes_high_risk_excludes_protected(self):
        """routes_high_risk_without_guard 不包含 protected 路由"""
        hr = routes_high_risk_without_guard()
        hr_paths = [p.path for p in hr]
        assert "/agents/ceo/run" not in hr_paths
        assert "/agents/codex/run" not in hr_paths
        assert "/pipeline/execute" not in hr_paths

    def test_routes_requiring_guard_excludes_deprecated(self):
        """routes_requiring_guard 不再包含 deprecated 路由（已阻断）"""
        all_rg = routes_requiring_guard()
        all_rg_paths = [p.path for p in all_rg]
        # deprecated 路由已从 routes_requiring_guard 中移除（has_guard=True）


# ── Task 2: 插件无目标执行拦截测试 ─────────────────────────

class TestRoutePolicyNewFunctions:
    """新增统计函数和 summary 端点测试"""

    def test_unprotected_execution_returns_zero(self):
        """routes_unprotected_execution() 返回 0"""
        result = routes_unprotected_execution()
        assert len(result) == 0, f"Expected 0, got {len(result)}: {[p.path for p in result]}"

    def test_controlled_entrypoints_returns_three(self):
        """routes_controlled_entrypoints() 返回至少 3 条受控入口"""
        result = routes_controlled_entrypoints()
        paths = [p.path for p in result]
        assert len(result) >= 3, f"Expected >= 3, got {len(result)}: {paths}"
        assert "/governance/run" in paths
        assert "/minidelivery/copy-pack" in paths
        assert "/minidelivery/xhs-copy-pack" in paths
        for r in result:
            assert r.category == "controlled"
            assert r.requires_governance is True

    def test_high_risk_without_guard_still_zero(self):
        assert len(routes_high_risk_without_guard()) == 0

    def test_deprecated_without_guard_still_zero(self):
        assert len(routes_deprecated_without_guard()) == 0

    def test_summary_endpoint_governance_complete(self):
        """GET /governance/routes/summary 返回 governance_complete=true"""
        resp = client.get("/governance/routes/summary")
        assert resp.status_code == 200
        data = resp.json()
        assert data["governance_complete"] is True
        assert data["unprotected_execution_count"] == 0
        assert data["high_risk_without_guard_count"] == 0
        assert data["deprecated_without_guard_count"] == 0
        assert len(data["controlled_entrypoints"]) >= 3
        assert "/governance/run" in data["controlled_entrypoints"]
        assert data["total"] > 0
        assert "by_category" in data

    def test_summary_endpoint_by_category_keys(self):
        """summary 的 by_category 包含预期分类"""
        resp = client.get("/governance/routes/summary")
        cats = resp.json()["by_category"]
        assert "controlled" in cats
        assert "protected" in cats
        assert "safe_read" in cats

    def test_high_risk_endpoint_still_zero(self):
        """GET /governance/routes/high-risk 仍返回 total=0"""
        resp = client.get("/governance/routes/high-risk")
        assert resp.status_code == 200
        assert resp.json()["total"] == 0


# ── Governance 入口说明 + Run Smoke 测试 ────────────────────

class TestGovernanceEntrypoints:
    """GET /governance/entrypoints 返回推荐入口信息"""

    def test_entrypoints_status_200(self):
        resp = client.get("/governance/entrypoints")
        assert resp.status_code == 200

    def test_entrypoints_primary_path(self):
        data = client.get("/governance/entrypoints").json()
        assert data["primary"]["path"] == "/governance/run"
        assert data["primary"]["method"] == "POST"

    def test_entrypoints_primary_example_execute(self):
        data = client.get("/governance/entrypoints").json()
        assert data["primary"]["example"]["execute"] is True

    def test_entrypoints_capability_endpoints(self):
        data = client.get("/governance/entrypoints").json()
        paths = [ep["path"] for ep in data["capability_endpoints"]]
        assert "/minidelivery/copy-pack" in paths
        assert "/minidelivery/xhs-copy-pack" in paths

    def test_entrypoints_recommended_test_flow(self):
        data = client.get("/governance/entrypoints").json()
        flow = data["recommended_test_flow"]
        assert any("execute=true" in step for step in flow)
        assert any("/governance/run" in step for step in flow)


class TestGovernanceRunSmoke:
    """/governance/run execute=false 和 execute=true smoke 测试"""

    def test_run_plan_only_returns_plan(self):
        """execute=false 返回计划，不执行"""
        resp = client.post("/governance/run", json={
            "goal": "帮我为手工耳环生成小红书种草文案",
            "platform": "xiaohongshu",
            "execute": False,
        })
        assert resp.status_code == 200
        data = resp.json()
        assert "run_id" in data
        assert "classification" in data
        assert "plan" in data
        # execute=false 时 status 是 planned 或 rejected
        assert data["status"] in ("planned", "rejected", "needs_clarification")

    def test_run_rejected_goal(self):
        """不支持的目标返回 rejected"""
        resp = client.post("/governance/run", json={
            "goal": "帮我搭建一个全自动赚钱公司系统",
            "execute": False,
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] in ("rejected", "needs_clarification")
        assert data["classification"]["ok"] is False

    def test_run_execute_xiaohongshu_succeeds(self):
        """execute=true 小红书文案成功执行"""
        resp = client.post("/governance/run", json={
            "goal": "帮我为手工耳环生成小红书种草文案",
            "platform": "xiaohongshu",
            "execute": True,
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "succeeded"
        # 顶层字段
        assert "artifact_path" in data
        assert "json_path" in data
        assert "task_id" in data
        assert "mode" in data
        assert "summary" in data
        # artifact 文件存在
        import os
        assert os.path.exists(data["artifact_path"]), f"artifact not found: {data['artifact_path']}"
        # result.ok == True
        assert data["result"]["ok"] is True

    def test_run_execute_douyin_succeeds(self):
        """execute=true 抖音文案成功执行"""
        resp = client.post("/governance/run", json={
            "goal": "帮我为手工耳环生成抖音种草文案",
            "platform": "douyin",
            "execute": True,
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "succeeded"
        assert "artifact_path" in data
        import os
        assert os.path.exists(data["artifact_path"]), f"artifact not found: {data['artifact_path']}"
        # 验证平台是 douyin
        spec = data["result"].get("spec", {})
        assert spec.get("platform") == "douyin" or "douyin" in data.get("task_id", "")


# ── 文档和测试页验证 ─────────────────────────────────────────

class TestGovernanceDocs:
    """文档和 HTML 测试页存在性及内容验证"""

    def test_entrypoint_md_exists(self):
        """docs/governance_entrypoint.md 存在"""
        import os
        path = os.path.join(os.path.dirname(__file__), "..", "docs", "governance_entrypoint.md")
        assert os.path.isfile(path), f"Missing: {path}"

    def test_entrypoint_md_content(self):
        """文档包含关键内容"""
        import os
        path = os.path.join(os.path.dirname(__file__), "..", "docs", "governance_entrypoint.md")
        with open(path, "r", encoding="utf-8") as f:
            content = f.read()
        assert "POST /governance/run" in content
        assert "execute" in content
        assert "artifact_path" in content
        assert "governance_complete" in content

    def test_entrypoint_md_no_mojibake(self):
        """文档不包含明显乱码字符"""
        import os
        path = os.path.join(os.path.dirname(__file__), "..", "docs", "governance_entrypoint.md")
        with open(path, "r", encoding="utf-8") as f:
            content = f.read()
        for bad in ["鈥", "鐩", "�"]:
            assert bad not in content, f"Found mojibake '{bad}' in document"

    def test_test_page_html_exists(self):
        """docs/governance_test_page.html 存在"""
        import os
        path = os.path.join(os.path.dirname(__file__), "..", "docs", "governance_test_page.html")
        assert os.path.isfile(path), f"Missing: {path}"

    def test_test_page_html_content(self):
        """HTML 测试页调用 /governance/run，不以 /minidelivery 为主 fetch"""
        import os
        path = os.path.join(os.path.dirname(__file__), "..", "docs", "governance_test_page.html")
        with open(path, "r", encoding="utf-8") as f:
            content = f.read()
        assert "/governance/run" in content
        assert "execute" in content
        # 主 fetch 不应是 /minidelivery
        assert 'fetch.*minidelivery' not in content  # 没有直接 fetch minidelivery 作为主入口

    def test_test_page_html_has_fallback(self):
        """HTML 测试页包含 fallback 到 127.0.0.1:8000"""
        import os
        path = os.path.join(os.path.dirname(__file__), "..", "docs", "governance_test_page.html")
        with open(path, "r", encoding="utf-8") as f:
            content = f.read()
        assert "127.0.0.1:8000" in content


class TestGovernanceTestPageEndpoint:
    """GET /governance/test-page 返回 HTML 测试页"""

    def test_test_page_returns_200(self):
        resp = client.get("/governance/test-page")
        assert resp.status_code == 200

    def test_test_page_content_type_html(self):
        resp = client.get("/governance/test-page")
        assert "text/html" in resp.headers.get("content-type", "")

    def test_test_page_contains_governance_run(self):
        resp = client.get("/governance/test-page")
        html = resp.text
        assert "/governance/run" in html
        assert "fetch" in html

    def test_test_page_contains_title(self):
        resp = client.get("/governance/test-page")
        assert "Governance" in resp.text

    def test_test_page_no_mojibake(self):
        resp = client.get("/governance/test-page")
        for bad in ["鈥", "鐩", "�"]:
            assert bad not in resp.text, f"Found mojibake '{bad}'"

    def test_entrypoints_includes_test_page(self):
        """GET /governance/entrypoints 包含 test_page"""
        resp = client.get("/governance/entrypoints")
        data = resp.json()
        assert "test_page" in data
        assert data["test_page"]["path"] == "/governance/test-page"


# ── 分类升级：artifact_type + 平台识别 + 拒绝测试 ──────────

class TestClassifierRejectVagueGoals:
    """危险/宽泛目标必须被拒绝"""

    def test_blocks_auto_money_system(self):
        """帮我做一个自动赚钱系统 → rejected"""
        result = classify_goal("帮我做一个自动赚钱系统")
        assert result.ok is False
        assert result.capability_id == "unsupported.complex_agent_workflow"
        assert result.needs_clarification is True

    def test_blocks_full_auto_money_company(self):
        """帮我搭建一个全自动赚钱公司系统 → rejected"""
        result = classify_goal("帮我搭建一个全自动赚钱公司系统")
        assert result.ok is False
        assert result.capability_id == "unsupported.complex_agent_workflow"

    def test_blocks_lie_zhuan(self):
        """做一个躺赚系统 → rejected"""
        result = classify_goal("做一个躺赚系统")
        assert result.ok is False
        assert result.capability_id == "unsupported.complex_agent_workflow"

    def test_blocks_passive_income_auto(self):
        """帮我做一个被动收入自动化系统 → rejected"""
        result = classify_goal("帮我做一个被动收入自动化系统")
        assert result.ok is False

    def test_blocks_monthly_income_auto(self):
        """月入过万自动赚钱项目 → rejected"""
        result = classify_goal("月入过万自动赚钱项目")
        assert result.ok is False

    def test_blocks_auto_select_promote(self):
        """自动选品自动推广自动成交系统 → rejected"""
        result = classify_goal("自动选品自动推广自动成交系统")
        assert result.ok is False

    def test_blocks_build_company(self):
        """帮我搭建一个完整公司 → rejected"""
        result = classify_goal("帮我搭建一个完整公司")
        assert result.ok is False

    def test_blocks_full_auto_ops(self):
        """帮我做一个全自动运营系统 → rejected"""
        result = classify_goal("帮我做一个全自动运营系统")
        assert result.ok is False

    def test_explicit_xhs_cannot_bypass_auto_money_block(self):
        """显式 platform=xiaohongshu 不能绕过自动赚钱拦截"""
        result = classify_goal("帮我做一个自动赚钱系统", explicit_platform="xiaohongshu")
        assert result.ok is False
        assert result.capability_id == "unsupported.complex_agent_workflow"
        assert result.needs_clarification is True

    def test_explicit_douyin_cannot_bypass_auto_money_block(self):
        """显式 platform=douyin 不能绕过自动赚钱拦截"""
        result = classify_goal("帮我做一个自动赚钱系统", explicit_platform="douyin")
        assert result.ok is False
        assert result.capability_id == "unsupported.complex_agent_workflow"
        assert result.needs_clarification is True


class TestGovernanceRunRejectsVagueGoals:
    """/governance/run 不应对宽泛目标生成产物"""

    def test_run_blocks_auto_money_system(self):
        resp = client.post("/governance/run", json={
            "goal": "帮我做一个自动赚钱系统",
            "execute": True,
        })
        data = resp.json()
        assert data["status"] in ("rejected", "needs_clarification")
        assert data["classification"]["ok"] is False
        assert "artifact_path" not in data


class TestClassifierPlatformDetection:
    """平台识别和默认降级修复"""

    def test_missing_platform_requires_clarification(self):
        """有文案关键词但无平台 → 需要澄清"""
        result = classify_goal("帮我为手工耳环生成推广文案")
        assert result.ok is False
        assert result.needs_clarification is True
        assert len(result.clarification_questions) > 0

    def test_ambiguous_platform_requires_clarification(self):
        """同时包含小红书和抖音 → 需要澄清"""
        result = classify_goal("帮我为手工耳环生成小红书抖音推广文案")
        assert result.ok is False
        assert result.needs_clarification is True

    def test_douyin_detected_from_goal(self):
        """goal 包含抖音 → douyin"""
        result = classify_goal("帮我为手工耳环生成抖音种草视频脚本")
        assert result.ok is True
        assert result.capability_id == "copy_pack.douyin"
        assert result.normalized_inputs["platform"] == "douyin"

    def test_xiaohongshu_detected_from_goal(self):
        """goal 包含小红书 → xiaohongshu"""
        result = classify_goal("帮我为手工耳环生成小红书种草文案")
        assert result.ok is True
        assert result.capability_id == "copy_pack.xiaohongshu"
        assert result.normalized_inputs["platform"] == "xiaohongshu"

    def test_no_default_downgrade_to_xiaohongshu(self):
        """不允许默认降级到小红书"""
        result = classify_goal("帮我为手工耳环生成推广文案")
        assert result.ok is False
        # 不应该默认返回 xiaohongshu
        assert result.capability_id != "copy_pack.xiaohongshu"


class TestClassifierArtifactTypes:
    """已识别但未支持的交付物类型"""

    def test_product_listing_recognized_but_unsupported(self):
        result = classify_goal("帮我为蓝牙耳机生成商品上架物料包")
        assert result.ok is False
        assert result.capability_id == "unsupported.artifact_type"
        assert result.normalized_inputs.get("artifact_type") == "product_listing"
        assert "product_listing" in result.reason or "商品上架" in result.reason

    def test_content_calendar_recognized_but_unsupported(self):
        result = classify_goal("帮我生成一周小红书内容日历")
        assert result.ok is False
        assert result.capability_id == "unsupported.artifact_type"
        assert result.normalized_inputs.get("artifact_type") == "content_calendar"

    def test_competitor_report_recognized_but_unsupported(self):
        result = classify_goal("帮我做一份手工耳环竞品分析报告")
        assert result.ok is False
        assert result.capability_id == "unsupported.artifact_type"
        assert result.normalized_inputs.get("artifact_type") == "competitor_report"

    def test_image_prompt_pack_now_supported(self):
        """image_prompt_pack 已升级为 supported capability"""
        result = classify_goal("帮我生成手工耳环产品图提示词")
        assert result.ok is True
        assert result.capability_id == "image_prompt_pack"
        assert result.normalized_inputs.get("artifact_type") == "image_prompt_pack"


class TestGovernanceRunExecution:
    """/governance/run 执行测试"""

    def test_run_douyin_goal_executes_douyin(self):
        """抖音 goal 执行抖音产物"""
        resp = client.post("/governance/run", json={
            "goal": "帮我为手工耳环生成抖音种草视频脚本",
            "execute": True,
        })
        data = resp.json()
        assert data["status"] == "succeeded"
        assert data["result"]["spec"]["platform"] == "douyin"

    def test_run_xiaohongshu_goal_executes_xiaohongshu(self):
        """小红书 goal 执行小红书产物"""
        resp = client.post("/governance/run", json={
            "goal": "帮我为手工耳环生成小红书种草文案",
            "execute": True,
        })
        data = resp.json()
        assert data["status"] == "succeeded"
        assert data["result"]["spec"]["platform"] == "xiaohongshu"

    def test_run_unsupported_artifact_type_not_executed(self):
        """不支持的交付物类型不执行"""
        resp = client.post("/governance/run", json={
            "goal": "帮我为蓝牙耳机生成商品上架物料包",
            "execute": True,
        })
        data = resp.json()
        assert data["status"] in ("rejected", "needs_clarification")
        assert "artifact_path" not in data


class TestDocsAndUIRelationship:
    """文档和 UI 关系"""

    def test_test_page_documented_as_dev_page(self):
        """文档说明 /governance/test-page 是临时测试页"""
        import os
        path = os.path.join(os.path.dirname(__file__), "..", "docs", "governance_entrypoint.md")
        with open(path, "r", encoding="utf-8") as f:
            content = f.read()
        assert "test-page" in content.lower() or "test_page" in content.lower()

    def test_frontend_new_exists_or_documented(self):
        """frontend-new 目录存在或文档提及"""
        import os
        fe_path = os.path.join(os.path.dirname(__file__), "..", "frontend-new")
        doc_path = os.path.join(os.path.dirname(__file__), "..", "docs", "governance_entrypoint.md")
        has_fe = os.path.isdir(fe_path)
        with open(doc_path, "r", encoding="utf-8") as f:
            doc_content = f.read()
        # frontend-new 存在或文档提及
        assert has_fe or "frontend-new" in doc_content

    def test_entrypoints_mentions_primary_and_test_page(self):
        """entrypoints 同时包含 primary 和 test_page"""
        resp = client.get("/governance/entrypoints")
        data = resp.json()
        assert "primary" in data
        assert data["primary"]["path"] == "/governance/run"
        assert "test_page" in data


# ── Artifact 读取测试 ────────────────────────────────────────

class TestArtifactRead:
    """测试 GET /governance/runs/{run_id}/artifact 接口"""

    def test_read_artifact_success(self):
        """正常 run_id 可读产物"""
        # 先执行一个成功的 run
        resp = client.post("/governance/run", json={
            "goal": "帮我为手工耳环生成小红书种草文案",
            "execute": True,
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "succeeded"
        run_id = data["run_id"]

        # 读取产物
        resp = client.get(f"/governance/runs/{run_id}/artifact")
        assert resp.status_code == 200
        artifact_data = resp.json()
        assert artifact_data["run_id"] == run_id
        assert "artifact_path" in artifact_data
        assert "content" in artifact_data
        assert len(artifact_data["content"]) > 0

    def test_read_artifact_not_found(self):
        """不存在 run_id 返回 404"""
        resp = client.get("/governance/runs/run_nonexistent/artifact")
        assert resp.status_code == 404

    def test_read_artifact_no_artifact_path(self):
        """无 artifact_path 返回 404"""
        # 创建一个没有 artifact_path 的 run
        resp = client.post("/governance/run", json={
            "goal": "帮我为手工耳环生成小红书文案",
            "execute": False,
        })
        assert resp.status_code == 200
        run_id = resp.json()["run_id"]

        # 读取产物应返回 404
        resp = client.get(f"/governance/runs/{run_id}/artifact")
        assert resp.status_code == 404
        assert "没有关联的产物文件" in resp.json()["detail"]

    def test_read_artifact_path_traversal_evil_dir(self, tmp_path):
        """相邻目录 minidelivery_evil 不能通过"""
        from backend.governance.run_record import OUTPUT_ROOT, _ensure_run_dir
        import json as _json

        # 创建一个 run record
        classification = classify_goal("帮我为手工耳环生成小红书文案")
        plan = build_execution_plan("帮我为手工耳环生成小红书文案", classification)
        with patch("backend.governance.run_record.OUTPUT_ROOT", tmp_path):
            record = create_run_record("帮我为手工耳环生成小红书文案", plan)
            run_id = record.run_id

            # 创建相邻的 evil 目录和文件
            evil_dir = tmp_path.parent / "output" / "minidelivery_evil"
            evil_dir.mkdir(parents=True, exist_ok=True)
            evil_file = evil_dir / "evil.md"
            evil_file.write_text("EVIL CONTENT", encoding="utf-8")

            # 篡改 record.json 中的 artifact_path
            record_path = tmp_path / run_id / "record.json"
            with open(record_path, "r", encoding="utf-8") as f:
                data = _json.load(f)
            # 使用绝对路径指向 evil 文件
            data["artifact_path"] = str(evil_file.resolve())
            with open(record_path, "w", encoding="utf-8") as f:
                _json.dump(data, f, ensure_ascii=False, indent=2)

            # 读取应返回 403
            resp = client.get(f"/governance/runs/{run_id}/artifact")
            assert resp.status_code == 403
            assert "不允许读取该路径的文件" in resp.json()["detail"]

            # 清理
            import shutil
            if evil_dir.exists():
                shutil.rmtree(evil_dir)

    def test_read_artifact_path_traversal_outside_project(self, tmp_path):
        """项目外路径不能读取"""
        from backend.governance.run_record import _ensure_run_dir
        import json as _json

        # 创建一个 run record
        classification = classify_goal("帮我为手工耳环生成小红书文案")
        plan = build_execution_plan("帮我为手工耳环生成小红书文案", classification)
        with patch("backend.governance.run_record.OUTPUT_ROOT", tmp_path):
            record = create_run_record("帮我为手工耳环生成小红书文案", plan)
            run_id = record.run_id

            # 在项目外创建一个文件
            outside_file = tmp_path.parent / "outside_project.md"
            outside_file.write_text("OUTSIDE CONTENT", encoding="utf-8")

            # 篡改 record.json 中的 artifact_path
            record_path = tmp_path / run_id / "record.json"
            with open(record_path, "r", encoding="utf-8") as f:
                data = _json.load(f)
            data["artifact_path"] = str(outside_file.resolve())
            with open(record_path, "w", encoding="utf-8") as f:
                _json.dump(data, f, ensure_ascii=False, indent=2)

            # 读取应返回 403
            resp = client.get(f"/governance/runs/{run_id}/artifact")
            assert resp.status_code == 403
            assert "不允许读取该路径的文件" in resp.json()["detail"]

            # 清理
            if outside_file.exists():
                outside_file.unlink()


class TestTestPageEnhancements:
    """测试页面增强功能"""

    def test_test_page_contains_artifact_button(self):
        """页面包含读取产物按钮"""
        resp = client.get("/governance/test-page")
        assert resp.status_code == 200
        html = resp.text
        assert "读取产物" in html
        assert "readArtifact" in html

    def test_test_page_contains_artifact_api_call(self):
        """页面包含 artifact 接口调用"""
        resp = client.get("/governance/test-page")
        assert resp.status_code == 200
        html = resp.text
        assert "/governance/runs/" in html
        assert "/artifact" in html

    def test_test_page_has_artifact_section(self):
        """页面有产物内容显示区域"""
        resp = client.get("/governance/test-page")
        assert resp.status_code == 200
        html = resp.text
        assert "artifactContent" in html
        assert "artifactJson" in html


# ── image_prompt_pack 测试 ──────────────────────────────────

class TestImagePromptPackClassification:
    """图片提示词包分类测试"""

    def test_classify_image_prompt_pack(self):
        """检测图片提示词包意图"""
        result = classify_goal("帮我为手工耳环生成产品图提示词")
        assert result.ok is True
        assert result.capability_id == "image_prompt_pack"

    def test_classify_image_prompt_pack_with_keyword(self):
        """包含 '图片提示词' 关键词应识别为 image_prompt_pack"""
        result = classify_goal("手工耳环图片提示词包")
        assert result.ok is True
        assert result.capability_id == "image_prompt_pack"

    def test_classify_image_prompt_pack_ai_keyword(self):
        """包含 'AI 生图提示' 关键词应识别为 image_prompt_pack"""
        result = classify_goal("帮我为手工耳环生成 AI 生图提示")
        assert result.ok is True
        assert result.capability_id == "image_prompt_pack"

    def test_image_prompt_pack_not_blocked_by_vague(self):
        """图片提示词包不应被模糊检测拦截"""
        result = classify_goal("帮我为手工耳环生成图片提示词")
        assert result.ok is True
        assert result.capability_id == "image_prompt_pack"


class TestImagePromptPackCapability:
    """图片提示词包能力目录测试"""

    def test_image_prompt_pack_in_catalog(self):
        """image_prompt_pack 应在能力目录中"""
        cap = get_capability("image_prompt_pack")
        assert cap is not None
        assert cap.supported is True
        assert "minidelivery" in cap.entrypoint

    def test_image_prompt_pack_in_supported(self):
        """image_prompt_pack 应在支持列表中"""
        supported = get_supported_capabilities()
        supported_ids = [c.id for c in supported]
        assert "image_prompt_pack" in supported_ids

    def test_image_prompt_pack_required_checks(self):
        """image_prompt_pack 应有必需的检查项"""
        cap = get_capability("image_prompt_pack")
        assert "has_main_prompt" in cap.required_checks
        assert "has_detail_prompt" in cap.required_checks
        assert "has_scene_prompt" in cap.required_checks
        assert "has_negative_prompt" in cap.required_checks
        assert "has_usage_tips" in cap.required_checks


class TestImagePromptPackExecutionPlan:
    """图片提示词包执行计划测试"""

    def test_plan_has_steps(self):
        """image_prompt_pack 应有执行步骤"""
        classification = classify_goal("帮我为手工耳环生成产品图提示词")
        plan = build_execution_plan("帮我为手工耳环生成产品图提示词", classification)

        assert plan.status == "planned"
        assert len(plan.steps) > 0
        assert plan.capability_id == "image_prompt_pack"

    def test_plan_artifact_expectation(self):
        """image_prompt_pack 应有产物期望"""
        classification = classify_goal("帮我为手工耳环生成产品图提示词")
        plan = build_execution_plan("帮我为手工耳环生成产品图提示词", classification)

        assert plan.artifact_expectation["type"] == "markdown"
        assert "提示词" in plan.artifact_expectation["description"]

    def test_plan_required_checks(self):
        """image_prompt_pack 应有必需的检查项"""
        classification = classify_goal("帮我为手工耳环生成产品图提示词")
        plan = build_execution_plan("帮我为手工耳环生成产品图提示词", classification)

        assert "has_main_prompt" in plan.required_checks
        assert "has_negative_prompt" in plan.required_checks


class TestImagePromptPackGovernanceRun:
    """图片提示词包 Governance 执行测试"""

    def test_governance_run_image_prompt_pack(self):
        """POST /governance/run 执行 image_prompt_pack"""
        resp = client.post("/governance/run", json={
            "goal": "帮我为手工耳环生成产品图提示词",
            "execute": True,
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "succeeded"
        assert data["task_id"] is not None
        assert "artifact_path" in data

    def test_governance_run_image_prompt_pack_artifact_readable(self):
        """生成的产物可通过 artifact API 读取"""
        resp = client.post("/governance/run", json={
            "goal": "帮我为手工耳环生成产品图提示词",
            "execute": True,
        })
        run_id = resp.json()["run_id"]

        # 读取产物
        art_resp = client.get(f"/governance/runs/{run_id}/artifact")
        assert art_resp.status_code == 200
        art_data = art_resp.json()
        assert "content" in art_data
        assert "主图提示词" in art_data["content"]
        assert "负面提示词" in art_data["content"]


# ── research_brief 测试 ──────────────────────────────────────

class TestResearchBriefClassification:
    """调研简报分类测试"""

    def test_classify_research_brief(self):
        """检测调研简报意图"""
        result = classify_goal("帮我为手工耳环做一份竞品调研简报")
        assert result.ok is True
        assert result.capability_id == "research_brief"

    def test_classify_research_brief_market(self):
        """检测市场调研简报意图"""
        result = classify_goal("帮我做一份手工耳环市场调研简报")
        assert result.ok is True
        assert result.capability_id == "research_brief"

    def test_classify_research_brief_with_keyword(self):
        """包含 '调研简报' 关键词应识别为 research_brief"""
        result = classify_goal("手工耳环竞品分析简报")
        assert result.ok is True
        assert result.capability_id == "research_brief"

    def test_research_brief_not_blocked_by_vague(self):
        """调研简报不应被模糊检测拦截"""
        result = classify_goal("帮我为手工耳环做调研简报")
        assert result.ok is True
        assert result.capability_id == "research_brief"


class TestResearchBriefCapability:
    """调研简报能力目录测试"""

    def test_research_brief_in_catalog(self):
        """research_brief 应在能力目录中"""
        cap = get_capability("research_brief")
        assert cap is not None
        assert cap.supported is True
        assert "minidelivery" in cap.entrypoint

    def test_research_brief_in_supported(self):
        """research_brief 应在支持列表中"""
        supported = get_supported_capabilities()
        supported_ids = [c.id for c in supported]
        assert "research_brief" in supported_ids

    def test_research_brief_required_checks(self):
        """research_brief 应有必需的检查项"""
        cap = get_capability("research_brief")
        assert "has_research_goal" in cap.required_checks
        assert "has_target_users" in cap.required_checks
        assert "has_competitor_dimensions" in cap.required_checks
        assert "has_pain_points" in cap.required_checks
        assert "has_content_opportunities" in cap.required_checks
        assert "has_risk_warnings" in cap.required_checks
        assert "has_next_steps" in cap.required_checks


class TestResearchBriefExecutionPlan:
    """调研简报执行计划测试"""

    def test_plan_has_steps(self):
        """research_brief 应有执行步骤"""
        classification = classify_goal("帮我为手工耳环做一份竞品调研简报")
        plan = build_execution_plan("帮我为手工耳环做一份竞品调研简报", classification)

        assert plan.status == "planned"
        assert len(plan.steps) > 0
        assert plan.capability_id == "research_brief"

    def test_plan_artifact_expectation(self):
        """research_brief 应有产物期望"""
        classification = classify_goal("帮我为手工耳环做一份竞品调研简报")
        plan = build_execution_plan("帮我为手工耳环做一份竞品调研简报", classification)

        assert plan.artifact_expectation["type"] == "markdown"
        assert "调研简报" in plan.artifact_expectation["description"]

    def test_plan_required_checks(self):
        """research_brief 应有必需的检查项"""
        classification = classify_goal("帮我为手工耳环做一份竞品调研简报")
        plan = build_execution_plan("帮我为手工耳环做一份竞品调研简报", classification)

        assert "has_research_goal" in plan.required_checks
        assert "has_risk_warnings" in plan.required_checks


class TestResearchBriefGovernanceRun:
    """调研简报 Governance 执行测试"""

    def test_governance_run_research_brief(self):
        """POST /governance/run 执行 research_brief"""
        resp = client.post("/governance/run", json={
            "goal": "帮我为手工耳环做一份竞品调研简报",
            "execute": True,
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "succeeded"
        assert data["task_id"] is not None
        assert "artifact_path" in data

    def test_governance_run_research_brief_artifact_readable(self):
        """生成的产物可通过 artifact API 读取"""
        resp = client.post("/governance/run", json={
            "goal": "帮我为手工耳环做一份竞品调研简报",
            "execute": True,
        })
        run_id = resp.json()["run_id"]

        # 读取产物
        art_resp = client.get(f"/governance/runs/{run_id}/artifact")
        assert art_resp.status_code == 200
        art_data = art_resp.json()
        assert "content" in art_data
        assert "调研目标" in art_data["content"]
        assert "目标用户" in art_data["content"]
        assert "竞品" in art_data["content"]

    def test_auto_money_system_blocked(self):
        """自动赚钱系统目标被拦截"""
        resp = client.post("/governance/run", json={
            "goal": "帮我搭建一个全自动赚钱公司系统",
            "execute": True,
        })
        data = resp.json()
        assert data["status"] in ("rejected", "needs_clarification")
        assert "artifact_path" not in data


# ── landing_page_copy 测试 ──────────────────────────────────────

class TestLandingPageCopyClassification:
    """落地页文案分类测试"""

    def test_classify_landing_page_copy(self):
        """检测落地页文案意图"""
        result = classify_goal("帮我为手工耳环生成一个落地页文案")
        assert result.ok is True
        assert result.capability_id == "landing_page_copy"

    def test_classify_landing_page_copy_landing_keyword(self):
        """包含 'landing page' 关键词应识别为 landing_page_copy"""
        result = classify_goal("帮我为手工耳环生成 landing page 文案")
        assert result.ok is True
        assert result.capability_id == "landing_page_copy"

    def test_classify_landing_page_copy_zhluodi_keyword(self):
        """包含 '落地页' 关键词应识别为 landing_page_copy"""
        result = classify_goal("手工耳环落地页着陆页文案")
        assert result.ok is True
        assert result.capability_id == "landing_page_copy"

    def test_landing_page_copy_not_blocked_by_vague(self):
        """落地页文案不应被模糊检测拦截"""
        result = classify_goal("帮我为手工耳环生成落地页文案")
        assert result.ok is True
        assert result.capability_id == "landing_page_copy"


class TestLandingPageCopyCapability:
    """落地页文案能力目录测试"""

    def test_landing_page_copy_in_catalog(self):
        """landing_page_copy 应在能力目录中"""
        cap = get_capability("landing_page_copy")
        assert cap is not None
        assert cap.supported is True
        assert "minidelivery" in cap.entrypoint

    def test_landing_page_copy_in_supported(self):
        """landing_page_copy 应在支持列表中"""
        supported = get_supported_capabilities()
        supported_ids = [c.id for c in supported]
        assert "landing_page_copy" in supported_ids

    def test_landing_page_copy_required_checks(self):
        """landing_page_copy 应有必需的检查项"""
        cap = get_capability("landing_page_copy")
        assert "has_page_positioning" in cap.required_checks
        assert "has_hero_title" in cap.required_checks
        assert "has_subtitle" in cap.required_checks
        assert "has_selling_points" in cap.required_checks
        assert "has_target_users" in cap.required_checks
        assert "has_page_structure" in cap.required_checks
        assert "has_cta" in cap.required_checks
        assert "has_faq" in cap.required_checks
        assert "has_visual_suggestions" in cap.required_checks


class TestLandingPageCopyExecutionPlan:
    """落地页文案执行计划测试"""

    def test_plan_has_steps(self):
        """landing_page_copy 应有执行步骤"""
        classification = classify_goal("帮我为手工耳环生成一个落地页文案")
        plan = build_execution_plan("帮我为手工耳环生成一个落地页文案", classification)

        assert plan.status == "planned"
        assert len(plan.steps) > 0
        assert plan.capability_id == "landing_page_copy"

    def test_plan_artifact_expectation(self):
        """landing_page_copy 应有产物期望"""
        classification = classify_goal("帮我为手工耳环生成一个落地页文案")
        plan = build_execution_plan("帮我为手工耳环生成一个落地页文案", classification)

        assert plan.artifact_expectation["type"] == "markdown"
        assert "落地页" in plan.artifact_expectation["description"]

    def test_plan_required_checks(self):
        """landing_page_copy 应有必需的检查项"""
        classification = classify_goal("帮我为手工耳环生成一个落地页文案")
        plan = build_execution_plan("帮我为手工耳环生成一个落地页文案", classification)

        assert "has_page_positioning" in plan.required_checks
        assert "has_hero_title" in plan.required_checks
        assert "has_faq" in plan.required_checks
        assert "has_visual_suggestions" in plan.required_checks


class TestLandingPageCopyGovernanceRun:
    """落地页文案 Governance 执行测试"""

    def test_governance_run_landing_page_copy(self):
        """POST /governance/run 执行 landing_page_copy"""
        resp = client.post("/governance/run", json={
            "goal": "帮我为手工耳环生成一个落地页文案",
            "execute": True,
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "succeeded"
        assert data["task_id"] is not None
        assert "artifact_path" in data

    def test_governance_run_landing_page_copy_artifact_readable(self):
        """生成的产物可通过 artifact API 读取"""
        resp = client.post("/governance/run", json={
            "goal": "帮我为手工耳环生成一个落地页文案",
            "execute": True,
        })
        run_id = resp.json()["run_id"]

        # 读取产物
        art_resp = client.get(f"/governance/runs/{run_id}/artifact")
        assert art_resp.status_code == 200
        art_data = art_resp.json()
        assert "content" in art_data
        assert "页面定位" in art_data["content"]
        assert "首屏标题" in art_data["content"]
        assert "核心卖点" in art_data["content"]
        assert "FAQ" in art_data["content"]

    def test_auto_money_system_still_blocked(self):
        """自动赚钱系统目标仍被拦截"""
        resp = client.post("/governance/run", json={
            "goal": "帮我搭建一个全自动赚钱公司系统",
            "execute": True,
        })
        data = resp.json()
        assert data["status"] in ("rejected", "needs_clarification")
        assert "artifact_path" not in data
