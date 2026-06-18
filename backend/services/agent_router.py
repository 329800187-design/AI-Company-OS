"""
Agent Router — 自动决策路由

根据任务自动选择最合适的 Agent
"""
from typing import Dict, List, Any, Optional
from backend.services.agent_registry import get_agent_registry, AgentCapability
from backend.logger import get_logger

logger = get_logger()


class TaskPlan:
    """任务计划"""

    def __init__(self, task_type: str, message: str, context: Dict = None):
        self.task_type = task_type
        self.message = message
        self.context = context or {}
        self.required_capabilities: List[str] = []
        self.optional_capabilities: List[str] = []
        self.verification_rules: Dict[str, Any] = {}
        self.output_format: str = "text"

        self._analyze()

    def _analyze(self):
        """分析任务，确定所需能力"""
        if self.task_type == "image":
            self.required_capabilities = ["image_generation"]
            self.output_format = "image"

        elif self.task_type == "data":
            self.required_capabilities = ["data_analysis"]
            self.output_format = "text"

        elif self.task_type == "research":
            self.required_capabilities = ["web_search"]
            self.optional_capabilities = ["browser", "reasoning"]
            self.output_format = "text"
            self.verification_rules = {"requires_sources": True, "min_sources": 2}

        elif self.task_type == "website":
            self.required_capabilities = ["reasoning"]
            self.output_format = "html"

        elif self.task_type == "code":
            self.required_capabilities = ["code_execution"]
            self.output_format = "code"

        elif self.task_type == "marketing":
            self.required_capabilities = ["reasoning"]
            self.optional_capabilities = ["web_search"]
            self.output_format = "text"

        else:
            self.required_capabilities = ["chat"]
            self.output_format = "text"


class AgentRouter:
    """Agent 路由器"""

    def __init__(self):
        self._registry = get_agent_registry()

    def route(self, task_type: str, message: str, context: Dict = None) -> Optional[AgentCapability]:
        """为任务选择最佳 Agent"""
        # 创建任务计划
        plan = TaskPlan(task_type, message, context)

        # 获取候选 Agent
        candidates = self._get_candidates(plan)

        if not candidates:
            logger.warning(f"AgentRouter: No candidates for {task_type}")
            return None

        # 选择最佳 Agent
        best = self._select_best(candidates, plan)

        logger.info(f"AgentRouter: Selected {best.id} for {task_type}")
        return best

    def _get_candidates(self, plan: TaskPlan) -> List[AgentCapability]:
        """获取候选 Agent"""
        candidates = []

        for agent in self._registry.get_available_agents():
            # 检查是否满足必需能力
            if not all(cap in agent.capabilities for cap in plan.required_capabilities):
                continue

            # 检查是否支持该任务类型
            if plan.task_type not in agent.task_types and "chat" not in agent.task_types:
                continue

            candidates.append(agent)

        return candidates

    def _select_best(self, candidates: List[AgentCapability], plan: TaskPlan) -> AgentCapability:
        """选择最佳 Agent"""

        # 计算每个候选的分数
        scored = []
        for agent in candidates:
            score = self._calculate_score(agent, plan)
            scored.append((score, agent))

        # 按分数排序
        scored.sort(key=lambda x: -x[0])

        return scored[0][1]

    def _calculate_score(self, agent: AgentCapability, plan: TaskPlan) -> float:
        """计算 Agent 分数"""
        score = 0.0

        # 基础分：可靠性
        score += agent.reliability_score * 30

        # 优先级分
        score += (100 - agent.priority) * 0.2

        # 本地优先
        if agent.kind == "local":
            score += 20
        elif agent.kind == "cli":
            score += 15
        elif agent.kind == "http":
            score += 10
        elif agent.kind == "api":
            score += 5

        # 能力匹配
        for cap in plan.required_capabilities:
            if cap in agent.capabilities:
                score += 10

        for cap in plan.optional_capabilities:
            if cap in agent.capabilities:
                score += 5

        # 任务类型精确匹配
        if plan.task_type in agent.task_types:
            score += 15

        # 成本考虑
        if agent.cost_level == "free":
            score += 5
        elif agent.cost_level == "low":
            score += 3

        # 延迟考虑
        if agent.latency_level == "fast":
            score += 5
        elif agent.latency_level == "medium":
            score += 3

        return score

    def explain_selection(self, task_type: str, message: str, context: Dict = None) -> Dict[str, Any]:
        """解释选择过程"""
        plan = TaskPlan(task_type, message, context)
        candidates = self._get_candidates(plan)

        explanations = []
        for agent in candidates:
            score = self._calculate_score(agent, plan)
            explanations.append({
                "agent_id": agent.id,
                "agent_name": agent.name,
                "score": score,
                "kind": agent.kind,
                "capabilities": agent.capabilities,
                "reliability": agent.reliability_score
            })

        explanations.sort(key=lambda x: -x["score"])

        return {
            "task_type": task_type,
            "required_capabilities": plan.required_capabilities,
            "candidates": explanations,
            "selected": explanations[0] if explanations else None
        }


# 全局实例
_router = None


def get_agent_router() -> AgentRouter:
    """获取 Agent Router 单例"""
    global _router
    if _router is None:
        _router = AgentRouter()
    return _router
