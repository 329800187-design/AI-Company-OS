"""
Agent Executor — 统一执行服务

通过 agent_id 解析 agent、加载实例、执行任务，返回标准 AgentRunResult。
不依赖具体类名分支——所有 agent 通过同一协议执行。

解析链:
  agent_id → scan_manifests() 查找 → load_agent_instance() 加载
           → AGENT_REGISTRY fallback → load_agent_instance() 加载
           → 都没找到 → ok=false + error
"""
import logging
import uuid
from typing import Optional

from backend.schemas.agent_protocol import AgentTask, AgentRunResult
from backend.schemas.agent_manifest import scan_manifests
from backend.services.agent_loader import load_agent_instance, AGENT_REGISTRY
from backend.services.agent_discovery import get_agent_enabled

logger = logging.getLogger(__name__)


def execute_agent(agent_id: str, task: AgentTask) -> AgentRunResult:
    """
    统一执行入口：通过 agent_id 调用任意 agent。

    Args:
        agent_id: agent 标识，如 "marketing" / "image" / "ceo"
        task: 统一任务输入

    Returns:
        AgentRunResult — 永不抛异常
    """
    task_id = task.task_id or f"exec_{uuid.uuid4().hex[:8]}"

    try:
        # ── 0. 检查 agent 是否启用 ──
        if not get_agent_enabled(agent_id):
            available = _list_available_agents()
            enabled = _list_enabled_agents()
            return AgentRunResult(
                ok=False,
                agent_id=agent_id,
                error=f"Agent '{agent_id}' is not enabled. Enable it via POST /agents/{agent_id}/enable first.",
                metadata={
                    "task_id": task_id,
                    "enabled_agents": enabled,
                    "available_agents": available,
                },
            )

        # ── 1. 解析 agent ──
        agent_instance = _resolve_agent(agent_id)
        if agent_instance is None:
            available = _list_available_agents()
            return AgentRunResult(
                ok=False,
                agent_id=agent_id,
                error=f"Agent '{agent_id}' not found. Available: {available}",
                metadata={"task_id": task_id},
            )

        # ── 2. 构建 task_dict ──
        task_dict = {
            "task_id": task_id,
            "goal": task.goal,
            "task_type": task.task_type,
            **task.context,
            **task.input,
        }

        # ── 3. 执行 ──
        result = agent_instance.execute(task_dict)

        # ── 4. 映射 → AgentRunResult ──
        return _map_result(agent_id, task_id, result)

    except Exception as e:
        logger.exception(f"execute_agent('{agent_id}') crashed unexpectedly")
        return AgentRunResult(
            ok=False,
            agent_id=agent_id,
            error=f"Unexpected error: {type(e).__name__}: {e}",
            metadata={"task_id": task_id},
        )


def _resolve_agent(agent_id: str):
    """
    解析 agent_id → 实例。

    优先级: manifest > AGENT_REGISTRY fallback
    """
    # 1. Manifest 解析
    try:
        manifests = scan_manifests()
        if agent_id in manifests:
            manifest = manifests[agent_id]
            if manifest.enabled:
                module_path, class_name = manifest.parse_entrypoint()
                instance = load_agent_instance(f"{module_path}:{class_name}")
                if instance is not None:
                    logger.debug(f"Resolved '{agent_id}' via manifest: {manifest.entrypoint}")
                    return instance
                logger.warning(f"Manifest found for '{agent_id}' but load failed: {manifest.entrypoint}")
            else:
                logger.debug(f"Agent '{agent_id}' is disabled in manifest")
    except Exception as e:
        logger.warning(f"Manifest scan failed: {e}")

    # 2. AGENT_REGISTRY fallback
    candidate = f"agents.{agent_id}_agent.agent"
    if candidate in AGENT_REGISTRY:
        class_name = AGENT_REGISTRY[candidate]
        instance = load_agent_instance(candidate, class_name)
        if instance is not None:
            logger.debug(f"Resolved '{agent_id}' via AGENT_REGISTRY: {candidate}:{class_name}")
            return instance
        logger.warning(f"AGENT_REGISTRY found for '{agent_id}' but load failed: {candidate}")

    return None


def _map_result(agent_id: str, task_id: str, raw: dict) -> AgentRunResult:
    """将 BaseAgent 信封映射为 AgentRunResult"""
    if not isinstance(raw, dict):
        return AgentRunResult(
            ok=False,
            agent_id=agent_id,
            error=f"Agent returned non-dict result: {type(raw).__name__}",
            metadata={"task_id": task_id},
        )

    # 提取基本字段
    ok = raw.get("ok", False)
    summary = raw.get("summary", "")
    task_type = raw.get("task_type", "")

    # 提取结构化输出 - 优先使用 data，其次 output
    structured_output = raw.get("data") or raw.get("output") or {}

    # 提取错误信息
    error = raw.get("error")
    warnings = raw.get("warnings", [])
    errors = raw.get("errors", [])

    # 如果有 error 字符串但没有 errors 列表，添加到 errors 列表
    if error and not errors:
        errors = [error]

    # 提取元数据
    meta = raw.get("meta") or {}

    return AgentRunResult(
        ok=ok,
        mode=meta.get("mode", "single_agent"),
        agent_id=agent_id,
        task_type=task_type,
        summary=summary,
        structured_output=structured_output,
        output=structured_output,  # 向后兼容
        artifacts=raw.get("artifacts", []),
        warnings=warnings,
        errors=errors,
        error=error,
        next_actions=raw.get("next_actions", []),
        risk_decision=raw.get("risk_decision"),
        timeline_events=raw.get("timeline_events", []),
        metadata={
            "task_id": task_id,
            **meta,
        },
    )


def _list_available_agents() -> list:
    """列出所有已知 agent_id（用于错误提示）"""
    ids = set()
    try:
        manifests = scan_manifests()
        ids.update(manifests.keys())
    except Exception:
        pass
    # 从 AGENT_REGISTRY 提取 agent_id（agents.xxx_agent.agent → xxx）
    for key in AGENT_REGISTRY:
        parts = key.split(".")
        if len(parts) >= 2 and parts[0] == "agents" and parts[1].endswith("_agent"):
            ids.add(parts[1].replace("_agent", ""))
    return sorted(ids)


def _list_enabled_agents() -> list:
    """列出所有已启用的 agent_id"""
    ids = set()
    try:
        manifests = scan_manifests()
        for agent_id in manifests:
            if get_agent_enabled(agent_id):
                ids.add(agent_id)
    except Exception:
        pass
    # 从 AGENT_REGISTRY 提取 agent_id 并检查启用状态
    for key in AGENT_REGISTRY:
        parts = key.split(".")
        if len(parts) >= 2 and parts[0] == "agents" and parts[1].endswith("_agent"):
            agent_id = parts[1].replace("_agent", "")
            if get_agent_enabled(agent_id):
                ids.add(agent_id)
    return sorted(ids)
