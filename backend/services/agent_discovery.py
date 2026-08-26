"""
Agent Discovery — 自动发现用户电脑上的 AI 工具

扫描类别：
1. CLI Agent (claude, codex, gemini, aider, etc.)
2. 本地 HTTP 服务 (Ollama, ComfyUI, LM Studio, etc.)
3. API Agent (MiMo, DeepSeek, OpenAI, etc.)
4. MCP Server
5. 项目本地 Agents
"""
import json
import os
import shutil
import socket
import subprocess
from pathlib import Path
from typing import Dict, List, Any, Optional
from backend.logger import get_logger

logger = get_logger()
PROJECT_ROOT = Path(__file__).resolve().parents[2]

# ── Enabled Agents 配置管理 ──────────────────────────────────────
_user_data_dir = Path(os.getenv("AI_COMPANY_OS_USER_DATA", "user_data"))
_enabled_agents_file = _user_data_dir / "agent_registry" / "enabled_agents.json"

# 默认启用配置：内置 manifest agent 默认 enabled=true，外部 CLI/HTTP agent 默认 enabled=false
_default_enabled_config: Dict[str, bool] = {
    # 内置 manifest agents（默认启用）
    "marketing": True,
    "image": True,
    "data": True,
    "research": True,
    "website": True,
    "example_echo": True,
    # 内置 legacy agents（默认启用）
    "ceo_agent": True,
    "cto_agent": True,
    "codex_agent": True,
    "openclaw_agent": True,
    "qa_agent": True,
    "system_agent": True,
    "video_agent": True,
    # 外部 CLI agents（默认禁用，需用户手动启用）
    "claude": False,
    "codex_cli": False,
    "gemini": False,
    "aider": False,
    # 外部 HTTP agents（默认禁用）
    "ollama": False,
    "lm_studio": False,
    "comfyui": False,
    "sd_webui": False,
}


def _load_enabled_config() -> Dict[str, bool]:
    """加载 enabled_agents.json 配置"""
    if not _enabled_agents_file.exists():
        return {}
    try:
        with open(_enabled_agents_file, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        logger.warning(f"Failed to load enabled_agents.json: {e}")
        return {}


def _save_enabled_config(config: Dict[str, bool]):
    """保存 enabled_agents.json 配置"""
    try:
        _enabled_agents_file.parent.mkdir(parents=True, exist_ok=True)
        with open(_enabled_agents_file, "w", encoding="utf-8") as f:
            json.dump(config, f, indent=2, ensure_ascii=False)
        logger.debug(f"Saved enabled_agents.json: {_enabled_agents_file}")
    except Exception as e:
        logger.error(f"Failed to save enabled_agents.json: {e}")


def get_agent_enabled(agent_id: str) -> bool:
    """获取 agent 启用状态"""
    config = _load_enabled_config()
    if agent_id in config:
        return config[agent_id]
    return _default_enabled_config.get(agent_id, False)


def set_agent_enabled(agent_id: str, enabled: bool) -> bool:
    """设置 agent 启用状态，返回是否成功"""
    config = _load_enabled_config()
    config[agent_id] = enabled
    _save_enabled_config(config)
    return True


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
        self.risk_level: str = kwargs.get("risk_level", "low")  # low, medium, high
        self.requires_api_key: bool = kwargs.get("requires_api_key", False)
        self.requires_gpu: bool = kwargs.get("requires_gpu", False)
        self.requires_confirmation: bool = kwargs.get("requires_confirmation", False)
        self.enabled: bool = kwargs.get("enabled", True)
        # “发现”不等于“可执行”。CLI 只有在接入专用适配器后才可进入路由。
        self.runnable: bool = kwargs.get("runnable", self.kind != "cli")
        self.source: str = kwargs.get("source", "unknown")  # manifest, cli, http, api, mcp, fallback
        self.timeout_seconds: int = kwargs.get("timeout_seconds", 60)
        self.input_schema: Optional[Dict[str, Any]] = kwargs.get("input_schema", None)
        self.output_schema: Optional[Dict[str, Any]] = kwargs.get("output_schema", None)
        self.tools: List[str] = kwargs.get("tools", [])
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
            "risk_level": self.risk_level,
            "requires_api_key": self.requires_api_key,
            "requires_gpu": self.requires_gpu,
            "requires_confirmation": self.requires_confirmation,
            "enabled": self.enabled,
            "runnable": self.runnable,
            "source": self.source,
            "timeout_seconds": self.timeout_seconds,
            "input_schema": self.input_schema,
            "output_schema": self.output_schema,
            "tools": self.tools,
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
        self._scan_scope: Dict[str, Any] = {}

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

        # 6. 应用 enabled_agents.json 配置
        self._apply_enabled_config()

        self._scanned = True
        logger.info(f"AgentDiscovery: Found {len(self._agents)} agents")
        return self._agents

    def get_scan_scope(self) -> Dict[str, Any]:
        """Explain what was inspected so discovery is observable and bounded."""
        if not self._scanned:
            self.scan_all()
        return dict(self._scan_scope)

    def _apply_enabled_config(self):
        """应用 enabled_agents.json 配置到扫描结果"""
        config = _load_enabled_config()
        for agent_id, agent in self._agents.items():
            # 优先使用配置中的 enabled 状态
            if agent_id in config:
                agent.enabled = config[agent_id]
            else:
                # 使用默认配置
                agent.enabled = _default_enabled_config.get(agent_id, False)

            # CLI/HTTP agent 默认 requires_confirmation=True
            if agent.kind in ("cli", "http"):
                agent.requires_confirmation = True
            else:
                agent.requires_confirmation = False

            # 设置 risk_level 默认值（基于 kind）
            if agent.risk_level == "low" and agent.kind in ("cli", "http"):
                # CLI/HTTP agent 默认 high risk（执行本地命令/连接本地服务）
                agent.risk_level = "high"
            elif agent.risk_level == "low" and agent.kind == "mcp":
                agent.risk_level = "medium"

            # 记录 source
            if agent.source == "unknown":
                agent.source = agent.kind

    def get_agent(self, agent_id: str) -> Optional[AgentCapability]:
        """获取指定 Agent"""
        return self._agents.get(agent_id)

    def get_available_agents(self) -> List[AgentCapability]:
        """获取所有可用 Agent"""
        return [a for a in self._agents.values()
                if a.status == "available" and a.enabled]

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
            {"id": "cursor", "name": "Cursor Agent", "cmd": "cursor", "args": ["--version"],
             "task_types": ["code", "analysis"],
             "capabilities": ["code_execution", "file_analysis"],
             "supports_code_execution": True, "supports_files": True},
            {"id": "qwen_code", "name": "Qwen Code", "cmd": "qwen", "args": ["--version"],
             "task_types": ["code", "analysis"],
             "capabilities": ["code_execution", "reasoning"],
             "supports_code_execution": True},
            {"id": "opencode", "name": "OpenCode", "cmd": "opencode", "args": ["--version"],
             "task_types": ["code", "analysis"],
             "capabilities": ["code_execution", "reasoning"],
             "supports_code_execution": True},
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
            requires_confirmation=True,
            enabled=False,
            source="cli",
            health={"version": version, "tested": True},
            priority=50,
            cost_level="free",
            latency_level="fast",
            reliability_score=0.9 if available else 0.0,
            runnable=False,
        )

    # ── HTTP 服务扫描 ──────────────────────────────────────

    def _scan_http_services(self):
        """扫描本地 HTTP 服务"""
        # Ollama 特殊处理：使用 OllamaAdapter.health_check()
        ollama_agent = self._scan_ollama_with_adapter()
        if ollama_agent:
            self._agents["ollama"] = ollama_agent

        # 其他 HTTP 服务
        http_services = [
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

    def _scan_ollama_with_adapter(self) -> Optional[AgentCapability]:
        """使用 OllamaAdapter.health_check() 扫描 Ollama"""
        try:
            from backend.adapters.ollama_adapter import OllamaAdapter
            adapter = OllamaAdapter()
            health = adapter.health_check()

            return AgentCapability(
                id="ollama",
                name="Ollama",
                kind="http",
                endpoint="http://localhost:11434",
                status="available" if health.get("available") else "unavailable",
                capabilities=["chat", "reasoning", "code_execution"],
                task_types=["chat", "marketing", "simple_task"],
                supports_code_execution=True,
                requires_confirmation=True,
                enabled=False,
                source="http",
                health=health,
                priority=55,
                cost_level="free",
                latency_level="fast",
                reliability_score=0.8 if health.get("available") else 0.0,
                last_error=health.get("error", "")
            )
        except Exception as e:
            return AgentCapability(
                id="ollama",
                name="Ollama",
                kind="http",
                status="unavailable",
                requires_confirmation=True,
                enabled=False,
                source="http",
                health={"error": str(e)},
                last_error=str(e)
            )

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
                requires_confirmation=True,
                enabled=False,
                source="http",
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
            requires_confirmation=True,
            enabled=False,
            source="http",
            health={"checked": True, "port": port},
            priority=60,
            cost_level="free",
            latency_level="fast",
            reliability_score=0.8 if available else 0.0
        )

    # ── API Agent 扫描 ──────────────────────────────────────

    def _scan_api_agents(self):
        """扫描 API Agent"""
        # MiMo 特殊处理：使用 MiMoAdapter.health_check()
        mimo_agent = self._scan_mimo_with_adapter()
        if mimo_agent:
            self._agents["mimo"] = mimo_agent

        # 其他 API Agent
        api_agents = [
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

    def _scan_mimo_with_adapter(self) -> Optional[AgentCapability]:
        """使用 MiMoAdapter.health_check() 扫描 MiMo"""
        try:
            from backend.adapters.mimo_adapter import MiMoAdapter
            adapter = MiMoAdapter()
            health = adapter.health_check()

            return AgentCapability(
                id="mimo",
                name="MiMo",
                kind="api",
                endpoint=os.getenv("MIMO_BASE_URL", ""),
                status="available" if health.get("available") else "unavailable",
                capabilities=["chat", "reasoning", "web_search"],
                task_types=["research", "marketing", "chat", "website"],
                requires_api_key=True,
                requires_confirmation=False,
                enabled=True,
                source="api",
                supports_web_search=health.get("web_search_enabled", False),
                health=health,
                priority=65,
                cost_level="low",
                latency_level="medium",
                reliability_score=0.8 if health.get("available") else 0.0,
                last_error=health.get("error", "")
            )
        except Exception as e:
            return AgentCapability(
                id="mimo",
                name="MiMo",
                kind="api",
                status="unavailable",
                requires_confirmation=False,
                enabled=True,
                source="api",
                health={"error": str(e)},
                last_error=str(e)
            )

    def _check_api_agent(self, info: Dict[str, Any]) -> Optional[AgentCapability]:
        """检查 API Agent"""
        api_key = os.getenv(info["env_key"], "")
        if info["id"] == "claude_api" and not api_key:
            api_key = os.getenv("ANTHROPIC_API_KEY", "")
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
                requires_confirmation=False,
                enabled=True,
                source="api",
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
            requires_confirmation=False,
            enabled=True,
            source="api",
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
                            requires_confirmation=False,
                            enabled=True,
                            source="mcp",
                            health={"config_path": str(config_path)},
                            priority=80,
                            reliability_score=0.6
                        )
                        self._agents[agent.id] = agent
                except Exception as e:
                    logger.warning(f"Failed to parse MCP config {config_path}: {e}")

    # ── 本地 Agent 扫描 ──────────────────────────────────────

    def _scan_local_agents(self):
        """扫描项目本地 Agent

        优先级：
        1. 读取 agent.json manifest（声明式注册）
        2. 无 manifest 的旧 agent 走兼容 fallback（硬编码能力映射）
        """
        agents_dir = PROJECT_ROOT / "agents"
        if not agents_dir.exists():
            return

        # ── Step 1: 扫描 manifest ──
        from backend.schemas.agent_manifest import scan_manifests
        manifests = scan_manifests(agents_dir.parent)

        for agent_id, manifest in manifests.items():
            if not manifest.enabled:
                logger.debug(f"Agent '{agent_id}' disabled in manifest, skipping")
                continue

            # 通过 manifest entrypoint 验证可用性
            module_path, class_name = manifest.parse_entrypoint()
            status = "available"
            last_error = ""
            try:
                import importlib
                mod = importlib.import_module(module_path)
                if class_name:
                    getattr(mod, class_name)
            except ImportError as e:
                status = "unavailable"
                last_error = f"ImportError: {e}"
            except AttributeError as e:
                status = "unavailable"
                last_error = f"AttributeError: {e}"
            except Exception as e:
                status = "unavailable"
                last_error = f"Error: {e}"

            agent = AgentCapability(
                id=manifest.id,
                name=manifest.name,
                kind="local",
                executable=manifest.entrypoint,
                status=status,
                capabilities=manifest.capabilities,
                task_types=manifest.task_types,
                risk_level=manifest.risk_level,
                requires_api_key=manifest.requires_api_key,
                requires_gpu=manifest.requires_gpu,
                requires_confirmation=False,
                enabled=True,
                source="manifest",
                health={
                    "module": module_path,
                    "class": class_name,
                    "version": manifest.version,
                    "source": "manifest",
                    "last_error": last_error,
                },
                priority=40,
                cost_level="free",
                latency_level="fast",
                reliability_score=0.7 if status == "available" else 0.0,
                last_error=last_error,
            )
            self._agents[agent.id] = agent

        # ── Step 2: 兼容 fallback — 无 manifest 的旧 agent ──
        agent_capabilities = {
            "ceo_agent": {
                "capabilities": ["reasoning", "task_decomposition"],
                "task_types": ["planning", "decomposition"]
            },
            "cto_agent": {
                "capabilities": ["reasoning", "code_review", "architecture"],
                "task_types": ["code", "architecture"]
            },
            "codex_agent": {
                "capabilities": ["code_execution", "sandbox"],
                "task_types": ["code"],
                "supports_code_execution": True
            },
            "openclaw_agent": {
                "capabilities": ["browser", "web_read", "deep_research"],
                "task_types": ["research", "browser"],
                "supports_browser": True,
                "supports_web_search": True
            },
            "qa_agent": {
                "capabilities": ["qa", "verification"],
                "task_types": ["qa", "verification"]
            },
            "system_agent": {
                "capabilities": ["system_control", "file_operations"],
                "task_types": ["system"],
                "supports_files": True
            },
            "video_agent": {
                "capabilities": ["video_script", "storyboard"],
                "task_types": ["video"]
            },
        }

        for agent_dir in agents_dir.iterdir():
            if not agent_dir.is_dir() or agent_dir.name.startswith("_"):
                continue

            # 跳过已有 manifest 的 agent
            if agent_dir.name in manifests or any(
                m.id == agent_dir.name for m in manifests.values()
            ):
                continue

            # 跳过已通过目录名匹配到 manifest id 的
            agent_file = agent_dir / "agent.py"
            if not agent_file.exists():
                continue

            cap_config = agent_capabilities.get(agent_dir.name, {})
            capabilities = cap_config.get("capabilities", ["local_agent"])
            task_types = cap_config.get("task_types", [agent_dir.name.replace("_agent", "")])

            status = "available"
            last_error = ""
            module_name = f"agents.{agent_dir.name}.agent"
            try:
                import importlib
                importlib.import_module(module_name)
            except ImportError as e:
                status = "unavailable"
                last_error = f"ImportError: {str(e)}"
            except Exception as e:
                status = "unavailable"
                last_error = f"Error: {str(e)}"

            agent = AgentCapability(
                id=agent_dir.name,
                name=agent_dir.name.replace("_agent", "").title(),
                kind="local",
                executable=str(agent_file),
                status=status,
                capabilities=capabilities,
                task_types=task_types,
                supports_files=cap_config.get("supports_files", False),
                supports_code_execution=cap_config.get("supports_code_execution", False),
                supports_image_generation=cap_config.get("supports_image_generation", False),
                supports_browser=cap_config.get("supports_browser", False),
                supports_web_search=cap_config.get("supports_web_search", False),
                requires_confirmation=False,
                enabled=True,
                source="fallback",
                health={"module": module_name, "source": "fallback", "last_error": last_error},
                priority=40,
                cost_level="free",
                latency_level="fast",
                reliability_score=0.7 if status == "available" else 0.0
            )
            self._agents[agent.id] = agent

        self._scan_scope = {
            "project_root": str(PROJECT_ROOT),
            "project_agent_dirs": [str(agents_dir), str(agents_dir / "installed")],
            "path_commands": ["claude", "codex", "gemini", "aider", "python", "node", "git", "cursor", "qwen", "opencode"],
            "local_services": ["ollama", "lm_studio", "comfyui", "sd_webui", "n8n"],
            "mcp_configs": ["~/.mcp.json", "~/.config/claude/mcp.json", "项目/.mcp.json"],
            "filesystem_scan": "仅扫描项目 Agent、用户级 MCP 配置和 PATH 中的已知 Agent 命令；不递归读取整个系统磁盘。",
        }

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
