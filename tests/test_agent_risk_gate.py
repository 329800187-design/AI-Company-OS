"""
Agent Risk Gate 测试

覆盖:
- high risk agent → requires_confirmation=true → waiting_human
- disabled agent → block → step failed
- capabilities empty → block → step failed
- low risk agent → normal execution
- approve risk gate waiting_human → resume 继续执行
- sandbox_required: high risk + code execution/browser/cli/http → sandbox flow
- timeline 记录 risk_gate_evaluated / risk_gate_blocked / risk_gate_waiting_confirmation / sandbox_required / sandbox_not_implemented
- review_required 仍然独立工作
"""
import os
import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest
from unittest.mock import patch, MagicMock

from backend.schemas.collaboration_plan import CollaborationPlan, CollaborationStep
from backend.schemas.agent_protocol import AgentTask, AgentRunResult
from backend.services.agent_risk_gate import evaluate_agent_risk, RiskDecision
from backend.services.agent_discovery import AgentCapability
from backend.services.collaboration_executor import execute_collaboration_plan
from backend.services.collaboration_planner import build_collaboration_plan
from backend.services.collaboration_run_store import (
    load_run_timeline,
    save_plan_snapshot,
    update_step_status,
    load_plan_snapshot,
)
from backend.services.sandbox_adapter import run_in_sandbox, SandboxRequest, SandboxResult


# ── Risk Gate 单元测试 ─────────────────────────────────────

class TestRiskGateEvaluation:
    """evaluate_agent_risk 单元测试"""

    def test_disabled_agent_blocks(self):
        """enabled=false → block"""
        agent = AgentCapability(id="test", name="Test", enabled=False)
        decision = evaluate_agent_risk(agent)
        assert decision.allowed is False
        assert decision.recommended_action == "block"
        assert decision.risk_level == "high"
        assert any("disabled" in r.lower() for r in decision.reasons)

    def test_empty_capabilities_blocks(self):
        """capabilities=[] → block"""
        agent = AgentCapability(id="test", name="Test", enabled=True, capabilities=[])
        decision = evaluate_agent_risk(agent)
        assert decision.allowed is False
        assert decision.recommended_action == "block"
        assert any("no" in r.lower() and "capabilit" in r.lower() for r in decision.reasons)

    def test_high_risk_agent_requires_confirmation(self):
        """risk_level=high → requires_confirmation=true"""
        agent = AgentCapability(
            id="test", name="Test", enabled=True,
            capabilities=["code_execution"], risk_level="high",
        )
        decision = evaluate_agent_risk(agent)
        assert decision.allowed is True
        assert decision.requires_confirmation is True
        assert decision.recommended_action == "confirm"
        assert decision.risk_level == "high"

    def test_cli_agent_medium_risk(self):
        """kind=cli → medium risk, requires_confirmation via kind"""
        agent = AgentCapability(
            id="test", name="Test", enabled=True,
            capabilities=["code"], kind="cli",
            risk_level="low", requires_confirmation=False,
        )
        decision = evaluate_agent_risk(agent)
        assert decision.allowed is True
        assert decision.risk_level == "medium"
        assert any("cli" in r.lower() for r in decision.reasons)

    def test_http_agent_medium_risk(self):
        """kind=http → medium risk"""
        agent = AgentCapability(
            id="test", name="Test", enabled=True,
            capabilities=["chat"], kind="http",
            risk_level="low", requires_confirmation=False,
        )
        decision = evaluate_agent_risk(agent)
        assert decision.allowed is True
        assert decision.risk_level == "medium"

    def test_low_risk_api_agent(self):
        """low risk API agent → allow"""
        agent = AgentCapability(
            id="test", name="Test", enabled=True,
            capabilities=["chat"], kind="api",
            risk_level="low", requires_confirmation=False,
        )
        decision = evaluate_agent_risk(agent)
        assert decision.allowed is True
        assert decision.requires_confirmation is False
        assert decision.recommended_action == "allow"
        assert decision.risk_level == "low"

    def test_code_execution_increases_risk(self):
        """supports_code_execution → medium risk"""
        agent = AgentCapability(
            id="test", name="Test", enabled=True,
            capabilities=["code"], kind="api",
            risk_level="low", supports_code_execution=True,
        )
        decision = evaluate_agent_risk(agent)
        assert decision.risk_level == "medium"
        assert any("code execution" in r.lower() for r in decision.reasons)

    def test_browser_increases_risk(self):
        """supports_browser → medium risk"""
        agent = AgentCapability(
            id="test", name="Test", enabled=True,
            capabilities=["web"], kind="api",
            risk_level="low", supports_browser=True,
        )
        decision = evaluate_agent_risk(agent)
        assert decision.risk_level == "medium"
        assert any("browser" in r.lower() for r in decision.reasons)

    def test_requires_confirmation_field(self):
        """requires_confirmation=True → requires_confirmation"""
        agent = AgentCapability(
            id="test", name="Test", enabled=True,
            capabilities=["chat"], kind="api",
            risk_level="low", requires_confirmation=True,
        )
        decision = evaluate_agent_risk(agent)
        assert decision.requires_confirmation is True
        assert decision.recommended_action == "confirm"

    def test_to_dict(self):
        """RiskDecision.to_dict() 返回正确结构"""
        d = RiskDecision(
            allowed=True, requires_confirmation=False,
            risk_level="low", reasons=["test"],
            recommended_action="allow",
        ).to_dict()
        assert d["allowed"] is True
        assert d["risk_level"] == "low"
        assert d["reasons"] == ["test"]

    def test_dict_input(self):
        """evaluate_agent_risk 也接受 dict 输入"""
        agent_dict = {
            "id": "test", "enabled": False, "capabilities": [],
        }
        decision = evaluate_agent_risk(agent_dict)
        assert decision.allowed is False
        assert decision.recommended_action == "block"


# ── Executor 集成测试 ─────────────────────────────────────

class TestRiskGateExecutorIntegration:
    """Risk Gate 与 executor 集成测试"""

    def _mock_agent(self, **overrides):
        """创建 mock AgentCapability"""
        defaults = {
            "id": "test_agent", "name": "Test Agent", "kind": "api",
            "enabled": True, "capabilities": ["chat"],
            "risk_level": "low", "requires_confirmation": False,
            "supports_code_execution": False, "supports_browser": False,
        }
        defaults.update(overrides)
        return AgentCapability(**defaults)

    @patch("backend.services.collaboration_executor.execute_agent")
    @patch("backend.services.collaboration_executor._resolve_agent_for_risk_gate")
    def test_high_risk_enters_waiting_human(self, mock_resolve, mock_exec):
        """high risk agent → step waiting_human"""
        mock_resolve.return_value = self._mock_agent(risk_level="high", requires_confirmation=True)
        mock_exec.return_value = AgentRunResult(ok=True, agent_id="marketing", output={"text": "done"})

        plan = build_collaboration_plan(
            goal="risk gate test",
            steps=[{"name": "High Risk Step", "task_type": "copywriting", "required_capability": "copywriting"}],
        )
        plan = execute_collaboration_plan(plan)

        assert plan.status == "waiting_human"
        assert plan.steps[0].status == "waiting_human"
        mock_exec.assert_not_called()
        # 验证 risk_decision 写入了 result
        rd = plan.steps[0].result.output.get("_risk_decision")
        assert rd is not None
        assert rd["requires_confirmation"] is True

    @patch("backend.services.collaboration_executor.execute_agent")
    @patch("backend.services.collaboration_executor._resolve_agent_for_risk_gate")
    def test_disabled_agent_blocks(self, mock_resolve, mock_exec):
        """disabled agent → step failed"""
        mock_resolve.return_value = self._mock_agent(enabled=False)
        mock_exec.return_value = AgentRunResult(ok=True, agent_id="marketing", output={"text": "done"})

        plan = build_collaboration_plan(
            goal="disabled agent test",
            steps=[{"name": "Disabled Step", "task_type": "copywriting", "required_capability": "copywriting"}],
        )
        plan = execute_collaboration_plan(plan)

        assert plan.status == "failed"
        assert plan.steps[0].status == "failed"
        mock_exec.assert_not_called()
        assert "blocked" in plan.steps[0].result.error.lower()

    @patch("backend.services.collaboration_executor.execute_agent")
    @patch("backend.services.collaboration_executor._resolve_agent_for_risk_gate")
    def test_empty_capabilities_blocks(self, mock_resolve, mock_exec):
        """empty capabilities → step failed"""
        mock_resolve.return_value = self._mock_agent(capabilities=[])
        mock_exec.return_value = AgentRunResult(ok=True, agent_id="marketing", output={"text": "done"})

        plan = build_collaboration_plan(
            goal="no caps test",
            steps=[{"name": "No Caps Step", "task_type": "copywriting", "required_capability": "copywriting"}],
        )
        plan = execute_collaboration_plan(plan)

        assert plan.status == "failed"
        assert plan.steps[0].status == "failed"
        mock_exec.assert_not_called()

    @patch("backend.services.collaboration_executor.execute_agent")
    @patch("backend.services.collaboration_executor._resolve_agent_for_risk_gate")
    def test_low_risk_normal_execution(self, mock_resolve, mock_exec):
        """low risk agent → 正常执行"""
        mock_resolve.return_value = self._mock_agent(risk_level="low")
        mock_exec.return_value = AgentRunResult(ok=True, agent_id="marketing", output={"text": "done"})

        plan = build_collaboration_plan(
            goal="low risk test",
            steps=[{"name": "Safe Step", "task_type": "copywriting", "required_capability": "copywriting"}],
        )
        plan = execute_collaboration_plan(plan)

        assert plan.status == "succeeded"
        assert plan.steps[0].status == "succeeded"
        mock_exec.assert_called_once()

    @patch("backend.services.collaboration_executor.execute_agent")
    @patch("backend.services.collaboration_executor._resolve_agent_for_risk_gate")
    def test_approve_risk_gate_then_resume(self, mock_resolve, mock_exec):
        """approve risk gate waiting_human 后 resume 继续执行"""
        mock_resolve.return_value = self._mock_agent(risk_level="high", requires_confirmation=True)
        mock_exec.return_value = AgentRunResult(ok=True, agent_id="marketing", output={"text": "done"})

        plan = build_collaboration_plan(
            goal="resume after risk approval",
            steps=[
                {"name": "High Risk Step", "task_type": "copywriting", "required_capability": "copywriting"},
                {"name": "Follow Up", "task_type": "image_generate", "required_capability": "image"},
            ],
        )

        # 第一次执行：停在 waiting_human
        plan = execute_collaboration_plan(plan)
        assert plan.status == "waiting_human"
        assert plan.steps[0].status == "waiting_human"
        assert plan.steps[1].status in ("pending", "assigned")

        # 模拟 approve：标记 step 为 succeeded
        update_step_status(plan.plan_id, "step_1", "succeeded", review_decision={"action": "approve"})

        # Reload
        plan = load_plan_snapshot(plan.plan_id)

        # Resume：step_2 已无 risk_decision（新步骤），_resolve 返回 None → 跳过 gate → 正常执行
        mock_resolve.return_value = None
        plan = execute_collaboration_plan(plan, resume=True)
        assert plan.status == "succeeded"
        assert plan.steps[0].status == "succeeded"
        assert plan.steps[1].status == "succeeded"

    @patch("backend.services.collaboration_executor.execute_agent")
    @patch("backend.services.collaboration_executor._resolve_agent_for_risk_gate")
    def test_blocked_agent_cascades_to_dependents(self, mock_resolve, mock_exec):
        """blocked step 导致依赖步骤 skipped"""
        mock_resolve.return_value = self._mock_agent(enabled=False)
        mock_exec.return_value = AgentRunResult(ok=True, agent_id="marketing", output={"text": "done"})

        plan = build_collaboration_plan(
            goal="cascade test",
            steps=[
                {"name": "Blocked Step", "task_type": "copywriting", "required_capability": "copywriting"},
                {"name": "Dependent", "task_type": "image_generate", "required_capability": "image", "depends_on": ["step_1"]},
            ],
        )
        plan = execute_collaboration_plan(plan)

        assert plan.status == "failed"
        assert plan.steps[0].status == "failed"
        assert plan.steps[1].status == "skipped"

    @patch("backend.services.collaboration_executor.execute_agent")
    def test_review_required_still_works(self, mock_exec):
        """review_required 仍然独立工作（不受 risk gate 影响）"""
        mock_exec.return_value = AgentRunResult(ok=True, agent_id="marketing", output={"text": "done"})

        plan = build_collaboration_plan(
            goal="review test",
            steps=[{"name": "Review Step", "task_type": "copywriting", "required_capability": "copywriting", "review_required": True}],
        )
        plan = execute_collaboration_plan(plan)

        assert plan.status == "waiting_human"
        assert plan.steps[0].status == "waiting_human"
        mock_exec.assert_not_called()
        # review_required 触发的 waiting_human 不应有 _risk_decision
        assert plan.steps[0].result is None or plan.steps[0].result.output.get("_risk_decision") is None


# ── Timeline 事件测试 ─────────────────────────────────────

class TestRiskGateTimeline:
    """Risk gate timeline 事件测试"""

    @patch("backend.services.collaboration_executor.execute_agent")
    @patch("backend.services.collaboration_executor._resolve_agent_for_risk_gate")
    def test_risk_gate_evaluated_event_recorded(self, mock_resolve, mock_exec):
        """high risk agent 记录 risk_gate_evaluated + risk_gate_waiting_confirmation"""
        mock_resolve.return_value = AgentCapability(
            id="marketing", name="Marketing", enabled=True,
            capabilities=["copywriting"], risk_level="high", requires_confirmation=True,
        )
        mock_exec.return_value = AgentRunResult(ok=True, agent_id="marketing", output={"text": "done"})

        plan = build_collaboration_plan(
            goal="timeline test",
            steps=[{"name": "Step", "task_type": "copywriting", "required_capability": "copywriting"}],
        )
        plan = execute_collaboration_plan(plan)

        timeline = load_run_timeline(plan.plan_id)
        event_types = [e["event_type"] for e in timeline]
        assert "risk_gate_evaluated" in event_types
        assert "risk_gate_waiting_confirmation" in event_types

    @patch("backend.services.collaboration_executor.execute_agent")
    @patch("backend.services.collaboration_executor._resolve_agent_for_risk_gate")
    def test_risk_gate_blocked_event_recorded(self, mock_resolve, mock_exec):
        """disabled agent 记录 risk_gate_evaluated + risk_gate_blocked"""
        mock_resolve.return_value = AgentCapability(
            id="marketing", name="Marketing", enabled=False, capabilities=["copywriting"],
        )
        mock_exec.return_value = AgentRunResult(ok=True, agent_id="marketing", output={"text": "done"})

        plan = build_collaboration_plan(
            goal="blocked timeline test",
            steps=[{"name": "Step", "task_type": "copywriting", "required_capability": "copywriting"}],
        )
        plan = execute_collaboration_plan(plan)

        timeline = load_run_timeline(plan.plan_id)
        event_types = [e["event_type"] for e in timeline]
        assert "risk_gate_evaluated" in event_types
        assert "risk_gate_blocked" in event_types

    @patch("backend.services.collaboration_executor.execute_agent")
    @patch("backend.services.collaboration_executor._resolve_agent_for_risk_gate")
    def test_no_risk_gate_event_for_low_risk(self, mock_resolve, mock_exec):
        """low risk agent（_resolve_agent 返回 None）不产生 risk_gate 事件"""
        mock_resolve.return_value = None
        mock_exec.return_value = AgentRunResult(ok=True, agent_id="marketing", output={"text": "done"})

        plan = build_collaboration_plan(
            goal="no event test",
            steps=[{"name": "Step", "task_type": "copywriting", "required_capability": "copywriting"}],
        )
        plan = execute_collaboration_plan(plan)

        timeline = load_run_timeline(plan.plan_id)
        event_types = [e["event_type"] for e in timeline]
        assert "risk_gate_evaluated" not in event_types


# ── Sandbox Adapter 单元测试 ─────────────────────────────────────

class TestSandboxAdapter:
    """run_in_sandbox 单元测试"""

    def test_run_in_sandbox_v0_returns_not_implemented(self):
        """v0 run_in_sandbox 返回 ok=false + not implemented error"""
        task = AgentTask(task_id="t1", goal="test", task_type="code")
        result = run_in_sandbox(agent_id="claude", task=task, risk_decision=None)
        assert result.ok is False
        assert "not implemented" in result.error.lower()
        assert len(result.audit_events) == 2
        assert result.audit_events[0]["event"] == "sandbox_requested"
        assert result.audit_events[1]["event"] == "sandbox_not_implemented"

    def test_run_in_sandbox_with_risk_decision(self):
        """run_in_sandbox 接受 dict risk_decision"""
        task = AgentTask(task_id="t2", goal="test", task_type="code")
        rd = {"risk_level": "high", "recommended_action": "sandbox_required"}
        result = run_in_sandbox(agent_id="codex", task=task, risk_decision=rd)
        assert result.ok is False
        assert result.audit_events[0]["risk_level"] == "high"

    def test_sandbox_request_fields(self):
        """SandboxRequest dataclass 字段完整"""
        req = SandboxRequest(request_id="r1", agent_id="a1", task_id="t1")
        assert req.request_id == "r1"
        assert req.risk_level == "low"
        assert req.allowed_operations == []

    def test_sandbox_result_to_dict(self):
        """SandboxResult.to_dict() 返回正确结构"""
        r = SandboxResult(ok=False, error="not implemented", audit_events=[{"event": "test"}])
        d = r.to_dict()
        assert d["ok"] is False
        assert d["error"] == "not implemented"
        assert len(d["audit_events"]) == 1


# ── Sandbox Required Risk Gate 测试 ─────────────────────────────────────

class TestSandboxRequiredRiskGate:
    """sandbox_required 触发条件测试"""

    def test_high_risk_code_execution_triggers_sandbox(self):
        """high risk + supports_code_execution → sandbox_required"""
        agent = AgentCapability(
            id="codex", name="Codex", enabled=True,
            capabilities=["code"], kind="api",
            risk_level="high", supports_code_execution=True,
        )
        decision = evaluate_agent_risk(agent)
        assert decision.recommended_action == "sandbox_required"
        assert decision.requires_confirmation is True
        assert decision.risk_level == "high"

    def test_high_risk_browser_triggers_sandbox(self):
        """high risk + supports_browser → sandbox_required"""
        agent = AgentCapability(
            id="browser", name="Browser", enabled=True,
            capabilities=["web"], kind="api",
            risk_level="high", supports_browser=True,
        )
        decision = evaluate_agent_risk(agent)
        assert decision.recommended_action == "sandbox_required"

    def test_high_risk_cli_triggers_sandbox(self):
        """high risk + kind=cli → sandbox_required"""
        agent = AgentCapability(
            id="claude", name="Claude CLI", enabled=True,
            capabilities=["code"], kind="cli",
            risk_level="high",
        )
        decision = evaluate_agent_risk(agent)
        assert decision.recommended_action == "sandbox_required"

    def test_high_risk_http_triggers_sandbox(self):
        """high risk + kind=http → sandbox_required"""
        agent = AgentCapability(
            id="ollama", name="Ollama", enabled=True,
            capabilities=["chat"], kind="http",
            risk_level="high",
        )
        decision = evaluate_agent_risk(agent)
        assert decision.recommended_action == "sandbox_required"

    def test_high_risk_no_code_browser_cli_http_stays_confirm(self):
        """high risk 但无 code execution/browser/cli/http → confirm（不是 sandbox_required）"""
        agent = AgentCapability(
            id="safe", name="Safe Agent", enabled=True,
            capabilities=["copywriting"], kind="api",
            risk_level="high", supports_code_execution=False, supports_browser=False,
        )
        decision = evaluate_agent_risk(agent)
        assert decision.recommended_action == "confirm"
        assert decision.risk_level == "high"

    def test_medium_risk_code_execution_stays_allow(self):
        """medium risk + supports_code_execution → allow（非 high risk 不触发 sandbox 也不触发 confirm）"""
        agent = AgentCapability(
            id="mcp_agent", name="MCP Agent", enabled=True,
            capabilities=["code"], kind="api",
            risk_level="medium", supports_code_execution=True,
        )
        decision = evaluate_agent_risk(agent)
        assert decision.recommended_action == "allow"
        assert decision.risk_level == "medium"


# ── Sandbox Required Executor 集成测试 ─────────────────────────────────────

class TestSandboxRequiredExecutorIntegration:
    """sandbox_required 与 executor 集成测试"""

    def _mock_agent(self, **overrides):
        """创建 mock AgentCapability"""
        defaults = {
            "id": "codex", "name": "Codex", "kind": "api",
            "enabled": True, "capabilities": ["code"],
            "risk_level": "low", "requires_confirmation": False,
            "supports_code_execution": False, "supports_browser": False,
        }
        defaults.update(overrides)
        return AgentCapability(**defaults)

    @patch("backend.services.collaboration_executor.execute_agent")
    @patch("backend.services.collaboration_executor._resolve_agent_for_risk_gate")
    def test_sandbox_required_enters_waiting_human(self, mock_resolve, mock_exec):
        """sandbox_required → step waiting_human"""
        mock_resolve.return_value = self._mock_agent(
            risk_level="high", supports_code_execution=True,
        )
        mock_exec.return_value = AgentRunResult(ok=True, agent_id="codex", output={"text": "done"})

        plan = build_collaboration_plan(
            goal="sandbox test",
            steps=[{"name": "Code Step", "task_type": "copywriting", "required_capability": "copywriting"}],
        )
        plan = execute_collaboration_plan(plan)

        assert plan.status == "waiting_human"
        assert plan.steps[0].status == "waiting_human"
        mock_exec.assert_not_called()
        # 验证 risk_decision 写入了 result
        rd = plan.steps[0].result.output.get("_risk_decision")
        assert rd is not None
        assert rd["recommended_action"] == "sandbox_required"

    @patch("backend.services.collaboration_executor.execute_agent")
    @patch("backend.services.collaboration_executor._resolve_agent_for_risk_gate")
    def test_sandbox_required_approve_does_not_call_execute_agent(self, mock_resolve, mock_exec):
        """sandbox_required approve 后不调用 execute_agent，而是走 run_in_sandbox"""
        mock_resolve.return_value = self._mock_agent(
            risk_level="high", supports_code_execution=True,
        )
        mock_exec.return_value = AgentRunResult(ok=True, agent_id="codex", output={"text": "done"})

        plan = build_collaboration_plan(
            goal="sandbox approve test",
            steps=[{"name": "Code Step", "task_type": "copywriting", "required_capability": "copywriting"}],
        )

        # 第一次执行：停在 waiting_human
        plan = execute_collaboration_plan(plan)
        assert plan.status == "waiting_human"

        # 模拟 approve：sandbox_required 需设为 pending（非 succeeded）让 executor 重走 sandbox 路径
        update_step_status(plan.plan_id, "step_1", "pending", review_decision={"action": "approve"})

        # Reload
        plan = load_plan_snapshot(plan.plan_id)

        # Resume: sandbox_required → run_in_sandbox → v0 未实现 → failed
        plan = execute_collaboration_plan(plan, resume=True)
        assert plan.status == "failed"
        assert plan.steps[0].status == "failed"
        # execute_agent 不应该被调用（sandbox_required 走 sandbox 路径）
        mock_exec.assert_not_called()
        # 验证错误信息
        assert "not implemented" in plan.steps[0].result.error.lower()

    @patch("backend.services.collaboration_executor.execute_agent")
    @patch("backend.services.collaboration_executor._resolve_agent_for_risk_gate")
    def test_sandbox_required_step_failed_v0(self, mock_resolve, mock_exec):
        """sandbox_required approve 后因 v0 未实现而 step failed"""
        mock_resolve.return_value = self._mock_agent(
            risk_level="high", supports_browser=True,
        )
        mock_exec.return_value = AgentRunResult(ok=True, agent_id="codex", output={"text": "done"})

        plan = build_collaboration_plan(
            goal="sandbox v0 fail test",
            steps=[
                {"name": "Browser Step", "task_type": "copywriting", "required_capability": "copywriting"},
                {"name": "Follow Up", "task_type": "image_generate", "required_capability": "image", "depends_on": ["step_1"]},
            ],
        )

        # 第一次执行：停在 waiting_human
        plan = execute_collaboration_plan(plan)
        assert plan.status == "waiting_human"

        # 模拟 approve：sandbox_required 设为 pending 让 executor 重走 sandbox 路径
        update_step_status(plan.plan_id, "step_1", "pending", review_decision={"action": "approve"})
        plan = load_plan_snapshot(plan.plan_id)

        # Resume: sandbox v0 → failed → 依赖步骤 skipped
        plan = execute_collaboration_plan(plan, resume=True)
        assert plan.status == "failed"
        assert plan.steps[0].status == "failed"
        assert plan.steps[1].status == "skipped"

    @patch("backend.services.collaboration_executor.execute_agent")
    @patch("backend.services.collaboration_executor._resolve_agent_for_risk_gate")
    def test_high_risk_no_dangerous_caps_stays_confirm(self, mock_resolve, mock_exec):
        """普通 high risk 但无 code/browser/cli/http → confirm，不是 sandbox_required"""
        mock_resolve.return_value = self._mock_agent(
            risk_level="high", requires_confirmation=True,
            supports_code_execution=False, supports_browser=False, kind="api",
        )
        mock_exec.return_value = AgentRunResult(ok=True, agent_id="codex", output={"text": "done"})

        plan = build_collaboration_plan(
            goal="confirm test",
            steps=[{"name": "High Risk Step", "task_type": "copywriting", "required_capability": "copywriting"}],
        )
        plan = execute_collaboration_plan(plan)

        assert plan.status == "waiting_human"
        assert plan.steps[0].status == "waiting_human"
        rd = plan.steps[0].result.output.get("_risk_decision")
        assert rd is not None
        assert rd["recommended_action"] == "confirm"


# ── Sandbox Required Timeline 测试 ─────────────────────────────────────

class TestSandboxRequiredTimeline:
    """sandbox_required timeline 事件测试"""

    @patch("backend.services.collaboration_executor.execute_agent")
    @patch("backend.services.collaboration_executor._resolve_agent_for_risk_gate")
    def test_sandbox_required_events_recorded(self, mock_resolve, mock_exec):
        """sandbox_required 记录 risk_gate_evaluated + sandbox_required"""
        mock_resolve.return_value = AgentCapability(
            id="marketing", name="Marketing", enabled=True,
            capabilities=["copywriting"], kind="api",
            risk_level="high", supports_code_execution=True,
        )
        mock_exec.return_value = AgentRunResult(ok=True, agent_id="marketing", output={"text": "done"})

        plan = build_collaboration_plan(
            goal="sandbox timeline test",
            steps=[{"name": "Code Step", "task_type": "copywriting", "required_capability": "copywriting"}],
        )
        plan = execute_collaboration_plan(plan)

        timeline = load_run_timeline(plan.plan_id)
        event_types = [e["event_type"] for e in timeline]
        assert "risk_gate_evaluated" in event_types
        assert "sandbox_required" in event_types

    @patch("backend.services.collaboration_executor.execute_agent")
    @patch("backend.services.collaboration_executor._resolve_agent_for_risk_gate")
    def test_sandbox_not_implemented_events_recorded(self, mock_resolve, mock_exec):
        """sandbox approve 后记录 sandbox_requested + sandbox_not_implemented"""
        mock_resolve.return_value = AgentCapability(
            id="marketing", name="Marketing", enabled=True,
            capabilities=["copywriting"], kind="api",
            risk_level="high", supports_code_execution=True,
        )
        mock_exec.return_value = AgentRunResult(ok=True, agent_id="marketing", output={"text": "done"})

        plan = build_collaboration_plan(
            goal="sandbox not impl timeline test",
            steps=[{"name": "Code Step", "task_type": "copywriting", "required_capability": "copywriting"}],
        )

        # 第一次执行：停在 waiting_human
        plan = execute_collaboration_plan(plan)

        # 模拟 approve：sandbox_required 设为 pending 让 executor 重走 sandbox 路径
        update_step_status(plan.plan_id, "step_1", "pending", review_decision={"action": "approve"})
        plan = load_plan_snapshot(plan.plan_id)

        # Resume: sandbox v0 → failed
        plan = execute_collaboration_plan(plan, resume=True)

        timeline = load_run_timeline(plan.plan_id)
        event_types = [e["event_type"] for e in timeline]
        assert "sandbox_requested" in event_types
        assert "sandbox_not_implemented" in event_types
