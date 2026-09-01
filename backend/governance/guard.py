"""Governance Guard — 旧主入口轻量守卫"""
import os
from typing import Tuple, Optional

from .classifier import classify_goal, ClassificationResult


# ── Goal 提取字段优先级 ─────────────────────────────────────

_GOAL_KEYS = ["goal", "目标", "prompt", "message", "命令", "command"]


def extract_goal_from_payload(payload: dict) -> str:
    """
    从请求 payload 中提取用户意图（goal）。

    按优先级依次尝试：goal → 目标 → prompt → message → 命令 → command
    → task.goal → task["goal"] → task["目标"]

    如果没有可用字段，返回空字符串。
    """
    # 顶层字段
    for key in _GOAL_KEYS:
        val = payload.get(key)
        if isinstance(val, str) and val.strip():
            return val.strip()

    # 嵌套 task 字段
    task = payload.get("task")
    if isinstance(task, dict):
        for key in ["goal", "目标", "prompt", "message"]:
            val = task.get(key)
            if isinstance(val, str) and val.strip():
                return val.strip()

    # 嵌套 chain/tasks 数组
    for array_key in ["chain", "tasks"]:
        arr = payload.get(array_key)
        if isinstance(arr, list):
            for item in arr:
                if isinstance(item, dict):
                    for key in ["goal", "目标", "prompt", "message"]:
                        val = item.get(key)
                        if isinstance(val, str) and val.strip():
                            return val.strip()

    return ""


def should_block_goal(
    goal: str,
    platform: str = None,
) -> Tuple[bool, ClassificationResult]:
    """
    检查 goal 是否应被旧主入口拒绝。

    返回 (should_block, classification)
    """
    classification = classify_goal(goal, explicit_platform=platform)
    should_block = not classification.ok
    return should_block, classification


def guard_payload(
    payload: dict,
    platform: Optional[str] = None,
) -> Tuple[bool, ClassificationResult]:
    """
    对请求 payload 执行 Governance Guard。

    1. 从 payload 提取 goal
    2. 如果 goal 为空，不阻断（保持原有行为）
    3. 如果 goal 不为空，检查是否应阻断

    测试绕过：设置 ACO_TEST_BYPASS_GOVERNANCE=true 环境变量可跳过 guard 检查。
    仅限测试环境使用，生产环境默认不生效。

    返回 (blocked, classification)
    """
    # 测试绕过：仅在显式设置时生效
    if os.environ.get("ACO_TEST_BYPASS_GOVERNANCE", "").lower() == "true":
        return False, ClassificationResult(
            ok=True,
            confidence=1.0,
            reason="测试环境绕过 governance guard",
        )

    goal = extract_goal_from_payload(payload)
    if not goal:
        # 无法提取 goal → 不阻断，让旧逻辑处理
        return False, ClassificationResult(
            ok=True,
            confidence=0.0,
            reason="未提取到 goal，跳过 governance 检查",
        )
    return should_block_goal(goal, platform=platform)


def governance_block_response(classification: ClassificationResult) -> dict:
    """生成 blocked_by_governance 格式的响应"""
    return {
        "ok": False,
        "blocked_by_governance": True,
        "classification": classification.model_dump(),
        "message": "该目标不在当前受控能力范围内，请先明确具体平台、产品和交付物。",
    }
