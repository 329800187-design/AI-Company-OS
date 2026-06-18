"""
Agent Discovery — 自动发现用户电脑上的 AI 工具

扫描类别：
1. CLI Agent (claude, codex, gemini, aider, etc.)
2. 本地 HTTP 服务 (Ollama, ComfyUI, LM Studio, etc.)
3. API Agent (MiMo, DeepSeek, OpenAI, etc.)
4. MCP Server
5. 项目本地 Agents
"""
import os
import shutil
import socket
import subprocess
from pathlib import Path
from typing import Dict, List, Any, Optional
from backend.logger import get_logger

logger = get_logger()


class AgentCapability:
    """Agent 能力描述"""

    def __init__(self, **kwargs):
        self.id: str = kwargs.get("id", "")
        self.name: str = kwargs.get("name", "")
        self.kind: str = kwargs.get("kind", "unknown")  # cli, http, api, mcp, local
        self.executable: str = kwargs.get("executable", "")
        self.endpoint: str = kwargs.get("endpoint", "")
        self.status: str = kwargs.get("status", "unknown")  # available, unavailable, error
        self.capabilities: List[str] = kwargs.get("capabilities", [])
        self.task_types: List[str] = kwargs.get("task_types", [])
        self.requires_api_key: bool = kwargs.get("requires_api_key", False)
        self.requires_gpu: bool = kwargs.get("requires_gpu", False)
        self.supports_files: bool = kwargs.get("supports_files", False)
        self.supports_web_search: bool = kwargs.get("supports_web_search", False)
        self.supports_code_execution: bool = kwargs.get("supports_code_execution", False)
        self.supports_image_generation: bool = kwargs.get("supports_image_generation", False)
        self.supports_browser: bool = kwargs.get("supports_browser", False)
        self.health: Dict[str, Any] = kwargs.get("health", {})
        self.priority: int = kwargs.get("priority", 100)
        self.cost_level: str = kwargs.get("cost_level", "unknown")  # free, low, medium, high
        self.latency_level: str = kwargs.get("latency_level", "unknown")  # fast, medium, slow
        self.reliability_score: float = kwargs.get("reliability_score", 0.5)
        self.last_error: str = kwargs.get("last_error", "")

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "kind": self.kind,
            "executable": self.executable,
            "endpoint": self.endpoint,
            "status": self.status,
            "capabilities": self.capabilities,
            "task_types": self.task_types,
            "requires_api_key": self.requires_api_key,
            "requires_gpu": self.requires_gpu,
            "supports_files": self.supports_files,
            "supports_web_search": self.supports_web_search,
            "supports_code_execution": self.supports_code_execution,
            "supports_image_generation": self.supports_image_generation,
            "supports_browser": self.supports_browser,
            "health": self.health,
            "priority": self.priority,
            "cost_level": self.cost_level,
            "latency_level": self.latency_level,
            "reliability_score": self.reliability_score,
            "last_error": self.last_error
        }


class AgentDiscovery:
    """Agent 自动发现"""

    def __init__(self):
        self._agents: Dict[str, AgentCapability] = {}
        self._scanned = False

    def scan_all(self, force: bool = False) -> Dict[str, AgentCapability]:
        """扫描所有 Agent"""
        if self._scanned and not force:
            return self._agents

        logger.info("AgentDiscovery: Starting full scan...")

        self._agents.clear()

        # 1. CLI Agent
        self._scan_cli_agents()

        # 2. 本地 HTTP 服务
        self._scan_http_services()

        # 3. API Agent
        self._scan_api_agents()

        # 4. MCP Server
        self._scan_mcp_servers()

        # 5. 项目本地 Agents
        self._scan_local_agents()

        self._scanned = True
        logger.info(f"AgentDiscovery: Found {len(self._agents)} agents")
        return self._agents

    def get_agent(self, agent_id: str) -> Optional[AgentCapability]:
        """获取指定 Agent"""
        return self._agents.get(agent_id)

    def get_available_agents(self) -> List[AgentCapability]:
        """获取所有可用 Agent"""
        return [a for a in self._agents.values() if a.status == "available"]

    def get_agents_by_capability(self, capability: str) -> List[AgentCapability]:
        """根据能力获取 Agent"""
        return [a for a in self._agents.values()
                if capability in a.capabilities and a.status == "available"]

    def get_agents_by_task_type(self, task_type: str) -> List[AgentCapability]:
        """根据任务类型获取 Agent"""
        return [a for a in self._agents.values()
                if task_type in a.task_types and a.status == "available"]

    # ── CLI Agent 扫描 ──────────────────────────────────────

    def _scan_cli_agents(self):
        """扫描 CLI Agent"""
        cli_agents = [
            {"id": "claude", "name": "Claude Code", "cmd": "claude", "args": ["--version"],
             "task_types": ["code", "analysis", "complex_reasoning"],
             "capabilities": ["code_execution", "file_analysis", "reasoning"],
             "supports_code_execution": True, "supports_files": True},
            {"id": "codex", "name": "Codex CLI", "cmd": "codex", "args": ["--version"],
             "task_types": ["code"],
             "capabilities": ["code_execution"],
             "supports_code_execution": True},
            {"id": "gemini", "name": "Gemini CLI", "cmd": "gemini", "args": ["--version"],
             "task_types": ["chat", "code"],
             "capabilities": ["chat", "reasoning"]},
            {"id": "aider", "name": "Aider", "cmd": "aider", "args": ["--version"],
             "task_types": ["code"],
             "capabilities": ["code_execution", "git_integration"],
             "supports_code_execution": True},
            {"id": "python", "name": "Python", "cmd": "python", "args": ["--version"],
             "task_types": ["code", "data"],
             "capabilities": ["code_execution", "data_analysis"],
             "supports_code_execution": True, "supports_files": True},
            {"id": "node", "name": "Node.js", "cmd": "node", "args": ["--version"],
             "task_types": ["code"],
             "capabilities": ["code_execution"],
             "supports_code_execution": True},
            {"id": "git", "name": "Git", "cmd": "git", "args": ["--version"],
             "task_types": ["code"],
             "capabilities": ["version_control"],
             "supports_files": True},
        ]

        for agent_info in cli_agents:
            agent = self._check_cli_agent(agent_info)
            if agent:
                self._agents[agent.id] = agent

    def _check_cli_agent(self, info: Dict[str, Any]) -> Optional[AgentCapability]:
        """检查 CLI Agent"""
        cmd = info["cmd"]
        args = info.get("args", ["--version"])

        # 查找命令
        cmd_path = shutil.which(cmd)
        if not cmd_path:
            return None

        # 测试执行
        try:
            result = subprocess.run(
                [cmd] + args,
                capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=10
            )
            version = result.stdout.strip()[:100] if result.returncode == 0 else "unknown"
            available = result.returncode == 0
        except Exception as e:
            version = "unknown"
            available = False

        return AgentCapability(
            id=info["id"],
            name=info["name"],
            kind="cli",
            executable=cmd_path,
            status="available" if available else "unavailable",
            capabilities=info.get("capabilities", []),
            task_types=info.get("task_types", []),
            supports_files=info.get("supports_files", False),
            supports_code_execution=info.get("supports_code_execution", False),
            health={"version": version, "tested": True},
            priority=50,
            cost_level="free",
            latency_level="fast",
            reliability_score=0.9 if available else 0.0
        )

    # ── HTTP 服务扫描 ──────────────────────────────────────

    def _scan_http_services(self):
        """扫描本地 HTTP 服务"""
        http_services = [
            {"id": "ollama", "name": "Ollama", "port": 11434, "path": "/api/tags",
             "task_types": ["chat", "code", "analysis"],
             "capabilities": ["chat", "reasoning", "code_execution"],
             "supports_code_execution": True},
            {"id": "lm_studio", "name": "LM Studio", "port": 1234, "path": "/v1/models",
             "task_types": ["chat"],
             "capabilities": ["chat"]},
            {"id": "comfyui", "name": "ComfyUI", "port": 8188, "path": "/system_stats",
             "task_types": ["image"],
             "capabilities": ["image_generation"],
             "supports_image_generation": True, "requires_gpu": True},
            {"id": "sd_webui", "name": "Stable Diffusion WebUI", "port": 7860, "path": "/sdapi/v1/options",
             "task_types": ["image"],
             "capabilities": ["image_generation"],
             "supports_image_generation": True, "requires_gpu": True},
            {"id": "n8n", "name": "n8n", "port": 5678, "path": "/healthz",
             "task_types": ["automation"],
             "capabilities": ["workflow_automation"]},
        ]

        for service_info in http_services:
            agent = self._check_http_service(service_info)
            if agent:
                self._agents[agent.id] = agent

    def _check_http_service(self, info: Dict[str, Any]) -> Optional[AgentCapability]:
        """检查 HTTP 服务"""
        port = info["port"]

        # 检查端口
        if not self._check_port(port):
            return AgentCapability(
                id=info["id"],
                name=info["name"],
                kind="http",
                endpoint=f"http://localhost:{port}",
                status="unavailable",
                capabilities=info.get("capabilities", []),
                task_types=info.get("task_types", []),
                supports_image_generation=info.get("supports_image_generation", False),
                requires_gpu=info.get("requires_gpu", False),
                health={"error": "服务未启动", "port": port},
                priority=60,
                reliability_score=0.0
            )

        # 尝试健康检查
        try:
            import httpx
            with httpx.Client(timeout=5) as client:
                response = client.get(f"http://localhost:{port}{info.get('path', '/')}")
                available = response.status_code == 200
        except Exception:
            available = True  # 端口在线但健康检查失败，仍然标记为可用

        return AgentCapability(
            id=info["id"],
            name=info["name"],
            kind="http",
            endpoint=f"http://localhost:{port}",
            status="available" if available else "unavailable",
            capabilities=info.get("capabilities", []),
            task_types=info.get("task_types", []),
            supports_image_generation=info.get("supports_image_generation", False),
            requires_gpu=info.get("requires_gpu", False),
            health={"checked": True, "port": port},
            priority=60,
            cost_level="free",
            latency_level="fast",
            reliability_score=0.8 if available else 0.0
        )

    # ── API Agent 扫描 ──────────────────────────────────────

    def _scan_api_agents(self):
        """扫描 API Agent"""
        api_agents = [
            {"id": "mimo", "name": "MiMo", "env_key": "MIMO_API_KEY",
             "base_url_env": "MIMO_BASE_URL", "model_env": "MIMO_MODEL",
             "task_types": ["research", "marketing", "chat", "website"],
             "capabilities": ["chat", "reasoning", "web_search"],
             "supports_web_search": True},
            {"id": "deepseek", "name": "DeepSeek", "env_key": "DEEPSEEK_API_KEY",
             "base_url_env": "DEEPSEEK_BASE_URL", "model_env": "DEEPSEEK_MODEL",
             "task_types": ["chat", "code", "marketing"],
             "capabilities": ["chat", "reasoning", "code_execution"],
             "supports_code_execution": True},
            {"id": "openai", "name": "OpenAI", "env_key": "OPENAI_API_KEY",
             "base_url_env": "OPENAI_BASE_URL", "model_env": "OPENAI_MODEL",
             "task_types": ["chat", "code", "image"],
             "capabilities": ["chat", "reasoning", "code_execution", "image_generation"],
             "supports_code_execution": True, "supports_image_generation": True},
            {"id": "claude_api", "name": "Claude API", "env_key": "CLAUDE_API_KEY",
             "base_url_env": "CLAUDE_BASE_URL", "model_env": "CLAUDE_MODEL",
             "task_types": ["chat", "code", "analysis"],
             "capabilities": ["chat", "reasoning", "code_execution"],
             "supports_code_execution": True},
        ]

        for agent_info in api_agents:
            agent = self._check_api_agent(agent_info)
            if agent:
                self._agents[agent.id] = agent

    def _check_api_agent(self, info: Dict[str, Any]) -> Optional[AgentCapability]:
        """检查 API Agent"""
        api_key = os.getenv(info["env_key"], "")
        base_url = os.getenv(info.get("base_url_env", ""), "")
        model = os.getenv(info.get("model_env", ""), "")

        if not api_key:
            return AgentCapability(
                id=info["id"],
                name=info["name"],
                kind="api",
                status="unavailable",
                capabilities=info.get("capabilities", []),
                task_types=info.get("task_types", []),
                requires_api_key=True,
                health={"error": "未配置 API Key"},
                priority=70,
                reliability_score=0.0
            )

        return AgentCapability(
            id=info["id"],
            name=info["name"],
            kind="api",
            endpoint=base_url,
            status="available",
            capabilities=info.get("capabilities", []),
            task_types=info.get("task_types", []),
            requires_api_key=True,
            supports_web_search=info.get("supports_web_search", False),
            supports_code_execution=info.get("supports_code_execution", False),
            supports_image_generation=info.get("supports_image_generation", False),
            health={"configured": True, "model": model},
            priority=70,
            cost_level="low",
            latency_level="medium",
            reliability_score=0.7
        )

    # ── MCP Server 扫描 ──────────────────────────────────────

    def _scan_mcp_servers(self):
        """扫描 MCP Server"""
        # 扫描 .mcp.json
        mcp_config_paths = [
            Path.home() / ".mcp.json",
            Path(".mcp.json"),
            Path.home() / ".config" / "claude" / "mcp.json",
        ]

        for config_path in mcp_config_paths:
            if config_path.exists():
                try:
                    import json
                    with open(config_path) as f:
                        config = json.load(f)
                    # 解析 MCP 配置
                    for server_name, server_config in config.get("mcpServers", {}).items():
                        agent = AgentCapability(
                            id=f"mcp_{server_name}",
                            name=f"MCP: {server_name}",
                            kind="mcp",
                            endpoint=server_config.get("command", ""),
                            status="available",
                            capabilities=["mcp_tools"],
                            task_types=["chat", "code"],
                            health={"config_path": str(config_path)},
                            priority=80,
                            reliability_score=0.6
                        )
                        self._agents[agent.id] = agent
                except Exception as e:
                    logger.warning(f"Failed to parse MCP config {config_path}: {e}")

    # ── 本地 Agent 扫描 ──────────────────────────────────────

    def _scan_local_agents(self):
        """扫描项目本地 Agent"""
        agents_dir = Path("agents")
        if not agents_dir.exists():
            return

        for agent_dir in agents_dir.iterdir():
            if agent_dir.is_dir() and not agent_dir.name.startswith("_"):
                agent_file = agent_dir / "agent.py"
                if agent_file.exists():
                    agent = AgentCapability(
                        id=agent_dir.name,
                        name=agent_dir.name.replace("_agent", "").title(),
                        kind="local",
                        executable=str(agent_file),
                        status="available",
                        capabilities=["local_agent"],
                        task_types=[agent_dir.name.replace("_agent", "")],
                        health={"module": f"agents.{agent_dir.name}.agent"},
                        priority=40,
                        cost_level="free",
                        latency_level="fast",
                        reliability_score=0.7
                    )
                    self._agents[agent.id] = agent

    # ── Helper ──────────────────────────────────────────────

    def _check_port(self, port: int, host: str = "localhost") -> bool:
        """检查端口"""
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(2)
            result = sock.connect_ex((host, port))
            sock.close()
            return result == 0
        except:
            return False


# 全局实例
_discovery = None


def get_agent_discovery() -> AgentDiscovery:
    """获取 Agent Discovery 单例"""
    global _discovery
    if _discovery is None:
        _discovery = AgentDiscovery()
    return _discovery
