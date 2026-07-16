"""
Agent Risk Gate — 执行前统一风险判断层

在 agent 执行前评估风险，返回:
  - allowed: 是否允许执行
  - requires_confirmation: 是否需要人工确认
  - risk_level: low / medium / high
  - reasons: 触发的风险原因列表
  - recommended_action: allow / confirm / block / sandbox_required

风险规则:
  1. enabled=false → block
  2. capabilities 为空 → block
  3. risk_level == high → requires_confirmation
  4. requires_confirmation == true → requires_confirmation
  5. supports_code_execution / supports_browser / kind in (cli, http) → 增加风险原因
"""
import logging
from dataclasses import dataclass, field
from typing import List, Optional

logger = logging.getLogger(__name__)


@dataclass
class RiskDecision:
    """风险评估结果"""
    allowed: bool = True
    requires_confirmation: bool = False
    risk_level: str = "low"  # low / medium / high
    reasons: List[str] = field(default_factory=list)
    recommended_action: str = "allow"  # allow / confirm / block / sandbox_required

    def to_dict(self) -> dict:
        return {
            "allowed": self.allowed,
            "requires_confirmation": self.requires_confirmation,
            "risk_level": self.risk_level,
            "reasons": self.reasons,
            "recommended_action": self.recommended_action,
        }


def evaluate_agent_risk(agent, task=None) -> RiskDecision:
    """
    评估 agent 执行风险。

    Args:
        agent: AgentCapability 对象或具有相同属性的 dict
        task: 可选的 AgentTask 对象（预留，当前未使用）

    Returns:
        RiskDecision 评估结果
    """
    # 兼容 dict 和对象
    def _get(key, default=None):
        if isinstance(agent, dict):
            return agent.get(key, default)
        return getattr(agent, key, default)

    decision = RiskDecision()
    risk_score = 0  # 0=low, 1=medium, 2=high

    # ── 规则 1: enabled=false → block ──
    enabled = _get("enabled", True)
    if not enabled:
        decision.allowed = False
        decision.recommended_action = "block"
        decision.reasons.append("Agent is disabled")
        decision.risk_level = "high"
        logger.info(f"RiskGate: agent '{_get('id', '?')}' blocked — disabled")
        return decision

    # ── 规则 2: capabilities 为空 → block ──
    capabilities = _get("capabilities", [])
    if not capabilities:
        decision.allowed = False
        decision.recommended_action = "block"
        decision.reasons.append("Agent has no declared capabilities")
        decision.risk_level = "high"
        logger.info(f"RiskGate: agent '{_get('id', '?')}' blocked — no capabilities")
        return decision

    # ── 规则 3: risk_level == high → requires_confirmation ──
    agent_risk = _get("risk_level", "low")
    if agent_risk == "high":
        decision.requires_confirmation = True
        decision.reasons.append(f"Agent risk_level is high")
        risk_score = max(risk_score, 2)

    # ── 规则 4: requires_confirmation == true → requires_confirmation ──
    if _get("requires_confirmation", False):
        decision.requires_confirmation = True
        decision.reasons.append("Agent requires confirmation")
        risk_score = max(risk_score, 1)

    # ── 规则 5: capability-based risk factors ──
    if _get("supports_code_execution", False):
        decision.reasons.append("Agent supports code execution")
        risk_score = max(risk_score, 1)

    if _get("supports_browser", False):
        decision.reasons.append("Agent supports browser access")
        risk_score = max(risk_score, 1)

    kind = _get("kind", "unknown")
    if kind in ("cli", "http"):
        decision.reasons.append(f"Agent kind is '{kind}' (local execution)")
        risk_score = max(risk_score, 1)

    # ── 综合判定 ──
    if risk_score >= 2:
        decision.risk_level = "high"
    elif risk_score >= 1:
        decision.risk_level = "medium"
    else:
        decision.risk_level = "low"

    # ── sandbox_required: high risk + 代码执行/浏览器/CLI/HTTP ──
    # v0: 沙箱未实现，但 flow 已打通——先 waiting_human，approve 后走 run_in_sandbox
    needs_sandbox = (
        decision.risk_level == "high"
        and (
            _get("supports_code_execution", False)
            or _get("supports_browser", False)
            or kind in ("cli", "http")
        )
    )

    if needs_sandbox:
        decision.requires_confirmation = True
        decision.recommended_action = "sandbox_required"
    elif decision.requires_confirmation:
        decision.recommended_action = "confirm"
    else:
        decision.recommended_action = "allow"

    logger.debug(
        f"RiskGate: agent '{_get('id', '?')}' → "
        f"risk={decision.risk_level}, confirm={decision.requires_confirmation}, "
        f"action={decision.recommended_action}, reasons={decision.reasons}"
    )
    return decision
