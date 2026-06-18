"""
Multi-Agent Swarm Mode — Agent 点对点协同

Agent 之间不经过 Commander 直接协作：
  - Agent 可以向其他 Agent 发出子任务请求
  - 支持 pipeline: ImageAgent → MarketingAgent 生成图文
  - 支持 fan-out: CEOAgent → 同时调用多个 Agent
  - 支持 chain: MarketingAgent → CTOAgent → QAAgent

每个 Agent 可以通过 `swarm.delegate(agent_name, task)` 委派子任务
"""
import json
import threading
import time
import uuid
from collections import defaultdict
from typing import Any, Callable, Dict, List, Optional


class SwarmNode:
    """Swarm 中的一个 Agent 节点"""

    def __init__(self, name: str, execute_fn: Callable):
        self.name = name
        self.execute = execute_fn
        self.peers: Dict[str, "SwarmNode"] = {}
        self.capabilities: List[str] = []

    def delegate(self, peer_name: str, task: Dict) -> Dict:
        """向另一个 Agent 委派子任务"""
        if peer_name not in self.peers:
            return {"ok": False, "error": f"Agent {peer_name} not reachable"}
        return self.peers[peer_name].execute(task)


class AgentSwarm:
    """多 Agent 群集引擎"""

    def __init__(self):
        self._nodes: Dict[str, SwarmNode] = {}
        self._lock = threading.Lock()
        self._execution_log: List[Dict] = []

    def register(self, name: str, execute_fn: Callable, capabilities: List[str] = None):
        with self._lock:
            node = SwarmNode(name, execute_fn)
            node.capabilities = capabilities or []
            # 连接到所有已有节点
            for existing in self._nodes.values():
                existing.peers[name] = node
                node.peers[existing.name] = existing
            self._nodes[name] = node

    def find_by_capability(self, capability: str) -> List[str]:
        return [n for n in self._nodes if capability in self._nodes[n].capabilities]

    def execute_chain(self, chain: List[Dict], context: Dict = None) -> Dict:
        """串行执行链: [ {agent, task_type, goal}, ... ]，每步的输出传递给下一步"""
        context = context or {}
        results = []
        for i, step in enumerate(chain):
            agent_name = step.get("agent", "")
            if agent_name not in self._nodes:
                results.append({"step": i, "error": f"Agent {agent_name} not found"})
                continue
            # Merge context into task
            task = {**step, **context, "chain_context": results[-1] if results else None}
            result = self._nodes[agent_name].execute(task)
            results.append({"step": i, "agent": agent_name, "result": result})
            context[f"step_{i}_output"] = result.get("data", result.get("result", ""))
        return {"ok": True, "chain_length": len(chain), "results": results}

    def execute_fanout(self, tasks: List[Dict]) -> Dict:
        """并行分发多个任务"""
        import concurrent.futures
        results = []

        def run_one(idx, task):
            agent = task.get("agent", "")
            if agent not in self._nodes:
                return {"step": idx, "error": f"Agent {agent} not found"}
            return {"step": idx, "agent": agent, "result": self._nodes[agent].execute(task)}

        with concurrent.futures.ThreadPoolExecutor(max_workers=min(len(tasks), 8)) as pool:
            futures = [pool.submit(run_one, i, t) for i, t in enumerate(tasks)]
            for f in concurrent.futures.as_completed(futures):
                try:
                    results.append(f.result(timeout=120))
                except Exception as e:
                    results.append({"error": str(e)})

        results.sort(key=lambda x: x.get("step", 0))
        return {"ok": True, "fanout_count": len(tasks), "results": results}

    def execute_pipeline(self, pipeline: List[Dict]) -> Dict:
        """流水线: 第一步→结果→第二步→结果→..."""
        return self.execute_chain(pipeline)

    def get_agents(self) -> List[Dict]:
        return [{
            "name": n.name, "capabilities": n.capabilities,
            "peers": list(n.peers.keys()),
        } for n in self._nodes.values()]


_swarm: Optional[AgentSwarm] = None


def get_swarm() -> AgentSwarm:
    global _swarm
    if _swarm is None:
        _swarm = AgentSwarm()
        _init_default_agents()
    return _swarm


def _init_default_agents():
    """注册所有 Agent 到 Swarm"""
    s = get_swarm()

    try:
        from agents.ceo_agent.agent import CEOAgent
        s.register("ceo", lambda t: CEOAgent().run(t), ["decompose", "plan"])
    except Exception:
        pass
    try:
        from agents.codex_agent.agent import CodexAgent
        s.register("codex", lambda t: CodexAgent(timeout=30).run(t), ["code", "execute", "sandbox"])
    except Exception:
        pass
    try:
        from agents.qa_agent.agent import QAAgent
        s.register("qa", lambda t: QAAgent().run(t), ["review", "score", "verify"])
    except Exception:
        pass
    try:
        from agents.cto_agent.agent import CTOAgent
        s.register("cto", lambda t: CTOAgent(timeout=60).run(t), ["review", "architect", "estimate"])
    except Exception:
        pass
    try:
        from agents.marketing_agent.agent import MarketingAgent
        s.register("marketing", lambda t: MarketingAgent(timeout=60).run(t), ["copywriting", "seo", "social", "brand"])
    except Exception:
        pass
    try:
        from agents.image_agent.agent import ImageAgent
        s.register("image", lambda t: ImageAgent(timeout=90).run(t), ["image_generate", "image_analyze"])
    except Exception:
        pass
    try:
        from agents.video_agent.agent import VideoAgent
        s.register("video", lambda t: VideoAgent(timeout=60).run(t), ["video_script", "storyboard"])
    except Exception:
        pass
    try:
        from agents.system_agent.agent import SystemAgent
        s.register("system", lambda t: SystemAgent(timeout=120).run(t), ["shell", "file", "process"])
    except Exception:
        pass
    try:
        from agents.openclaw_agent.agent import OpenClawAgent
        s.register("openclaw", lambda t: OpenClawAgent(headless=True, timeout=30).run(t),
                   ["browser", "screenshot", "scrape", "research", "chat", "search"])
    except Exception:
        pass
    try:
        from agents.data_agent.agent import DataAgent
        s.register("data", lambda t: DataAgent().run(t), ["data_load", "data_explore", "data_analyze", "data_viz"])
    except Exception:
        pass
