"""
Capability Router — 按能力动态路由 agent

扫描 agent manifests，建立 capability -> candidate agents 映射，
根据 required_capability、task_type、enabled 状态选择最合适 agent。
"""
import logging
from dataclasses import dataclass, field
from typing import Dict, List, Optional

from backend.schemas.agent_manifest import AgentManifest, scan_manifests
from backend.services.agent_discovery import get_agent_enabled

logger = logging.getLogger(__name__)


@dataclass
class RoutingResult:
    """路由结果"""
    assigned_agent_id: Optional[str] = None
    matched_capability: Optional[str] = None
    candidates: List[str] = field(default_factory=list)
    reason: str = ""


def _agent_priority(manifest: AgentManifest) -> tuple:
    """
    排序优先级：risk_level low 优先，capabilities 少的更精确优先，id 字典序兜底。
    """
    risk_order = {"low": 0, "medium": 1, "high": 2}
    return (
        risk_order.get(manifest.risk_level, 9),
        len(manifest.capabilities),
        manifest.id,
    )


def route_capability(
    required_capability: str,
    task_type: str = "",
    manifests: Optional[Dict[str, AgentManifest]] = None,
) -> RoutingResult:
    """
    根据 required_capability 和 task_type 路由到最合适的 agent。

    选择规则：
    1. 只考虑 enabled=True 的 agent
    2. 优先 exact capability match（required_capability 在 manifest.capabilities 中）
    3. 其次 task_type match（task_type 在 manifest.task_types 中）
    4. 多个匹配时：risk_level=low 优先 -> capabilities 更少更精确 -> id 字典序稳定排序
    5. 找不到时返回 unassigned，不抛异常

    Args:
        required_capability: 所需能力标签
        task_type: 任务类型（可选，作为 fallback）
        manifests: 预加载的 manifests（可选，为 None 时自动扫描）

    Returns:
        RoutingResult — 包含 assigned_agent_id、匹配详情、候选列表、路由原因
    """
    if manifests is None:
        try:
            manifests = scan_manifests()
        except Exception as e:
            logger.warning(f"CapabilityRouter: manifest scan failed: {e}")
            return RoutingResult(reason=f"manifest scan failed: {e}")

    # 过滤 enabled agents（manifest.enabled + agent_discovery enabled 双重检查）
    enabled = {
        mid: m for mid, m in manifests.items()
        if m.enabled and get_agent_enabled(mid)
    }

    if not enabled:
        return RoutingResult(reason="no enabled agents found")

    # --- Stage 1: exact capability match ---
    cap_candidates: List[AgentManifest] = []
    for manifest in enabled.values():
        if required_capability in manifest.capabilities:
            cap_candidates.append(manifest)

    if cap_candidates:
        cap_candidates.sort(key=_agent_priority)
        winner = cap_candidates[0]
        return RoutingResult(
            assigned_agent_id=winner.id,
            matched_capability=required_capability,
            candidates=[m.id for m in cap_candidates],
            reason=f"exact capability match: '{required_capability}'",
        )

    # --- Stage 2: task_type fallback ---
    if task_type:
        tt_candidates: List[AgentManifest] = []
        for manifest in enabled.values():
            if task_type in manifest.task_types:
                tt_candidates.append(manifest)

        if tt_candidates:
            tt_candidates.sort(key=_agent_priority)
            winner = tt_candidates[0]
            return RoutingResult(
                assigned_agent_id=winner.id,
                matched_capability=task_type,
                candidates=[m.id for m in tt_candidates],
                reason=f"task_type fallback: '{task_type}'",
            )

    # --- No match ---
    return RoutingResult(
        reason=f"no agent found for capability='{required_capability}', task_type='{task_type}'",
    )
