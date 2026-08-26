"""
Agent Registry — Agent 注册中心

统一管理所有已发现的 Agent
"""
from typing import Dict, List, Optional, Any
from backend.services.agent_discovery import AgentCapability, get_agent_discovery
from backend.logger import get_logger

logger = get_logger()


class AgentRegistry:
    """Agent 注册中心"""

    def __init__(self):
        self._agents: Dict[str, AgentCapability] = {}
        self._discovery = get_agent_discovery()

    def refresh(self, force: bool = False) -> Dict[str, AgentCapability]:
        """刷新 Agent 列表"""
        self._agents = self._discovery.scan_all(force=force)
        logger.info(f"AgentRegistry: Refreshed, {len(self._agents)} agents registered")
        return self._agents

    def get_agent(self, agent_id: str) -> Optional[AgentCapability]:
        """获取指定 Agent"""
        return self._agents.get(agent_id)

    def get_available_agents(self) -> List[AgentCapability]:
        """获取所有可用 Agent"""
        return [a for a in self._agents.values()
                if a.status == "available" and a.enabled]

    def get_agents_for_task(self, task_type: str) -> List[AgentCapability]:
        """获取能处理指定任务的 Agent"""
        candidates = []
        for agent in self._agents.values():
            if agent.status != "available" or not agent.enabled:
                continue
            if task_type in agent.task_types:
                candidates.append(agent)

        # 按优先级排序
        candidates.sort(key=lambda a: (a.priority, -a.reliability_score))
        return candidates

    def get_agents_by_capability(self, capability: str) -> List[AgentCapability]:
        """根据能力获取 Agent"""
        return [a for a in self._agents.values()
                if capability in a.capabilities and a.status == "available"]

    def get_summary(self) -> Dict[str, Any]:
        """获取摘要"""
        available = self.get_available_agents()
        return {
            "total": len(self._agents),
            "available": len(available),
            "unavailable": len(self._agents) - len(available),
            "by_kind": {
                "cli": len([a for a in available if a.kind == "cli"]),
                "http": len([a for a in available if a.kind == "http"]),
                "api": len([a for a in available if a.kind == "api"]),
                "mcp": len([a for a in available if a.kind == "mcp"]),
                "local": len([a for a in available if a.kind == "local"]),
            },
            "agents": [a.to_dict() for a in self._agents.values()]
        }


# 全局实例
_registry = None


def get_agent_registry() -> AgentRegistry:
    """获取 Agent Registry 单例"""
    global _registry
    if _registry is None:
        _registry = AgentRegistry()
    return _registry
