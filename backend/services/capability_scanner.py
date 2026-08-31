"""Real-time, bounded inspection of the current machine."""
import hashlib
import os
import platform
import shutil
import subprocess
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

import httpx

from backend.config import get_provider_info
from backend.ai_registry.contracts import CapabilityResource, ResourceType

_KNOWN_AGENTS = {
    "claude": ("Claude Code", ["code", "analysis"]),
    "codex": ("Codex CLI", ["code", "computer_use"]),
    "gemini": ("Gemini CLI", ["chat", "code"]),
    "aider": ("Aider", ["code"]),
    "cursor": ("Cursor Agent", ["code"]),
    "qwen": ("Qwen Code", ["code"]),
    "opencode": ("OpenCode", ["code"]),
}


class CapabilityScanner:
    """Report observations without recursively scanning the filesystem."""

    def __init__(self, ttl_seconds: int = 8):
        self._cache: Dict[str, Any] = {}
        self._scanned_at = 0.0
        self._ttl_seconds = ttl_seconds

    @staticmethod
    def machine_id() -> str:
        raw = "|".join((platform.system(), platform.machine(), platform.node(), str(Path.home())))
        return hashlib.sha256(raw.encode("utf-8", "replace")).hexdigest()[:16]

    def scan_all(self, force: bool = False) -> Dict[str, Any]:
        now = time.time()
        if self._cache and not force and now - self._scanned_at < self._ttl_seconds:
            return self._cache
        self._cache = {
            "ai_services": self._scan_ai_services(),
            "llm_providers": self._scan_llm_providers(),
            "browsers": self._scan_browsers(),
            "tools": self._scan_tools(),
            "agents": self._scan_agents(),
            "scan": {
                "machine_id": self.machine_id(),
                "scanned_at": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
                "scanned_at_epoch": now,
                "platform": platform.platform(),
                "scope": "PATH commands, known application paths, localhost health endpoints, and environment variable presence only",
            },
        }
        self._cache["resources"] = self._canonical_resources(self._cache)
        self._cache["summary"] = {
            "ai_services": len(self._cache["ai_services"]),
            "llm_providers": len(self._cache["llm_providers"]),
            "browsers": len(self._cache["browsers"]),
            "tools": len(self._cache["tools"]),
            "agents": len(self._cache["agents"]),
            "total": sum(len(self._cache[key]) for key in ("ai_services", "llm_providers", "browsers", "tools", "agents")),
            "available_agents": sum(x["status"] == "available" for x in self._cache["agents"]),
            "available_tools": sum(x["status"] == "available" for x in self._cache["tools"]),
        }
        self._scanned_at = now
        return self._cache

    def _canonical_resources(self, observations: Dict[str, Any]) -> List[dict]:
        """Convert scanner observations to the single public readiness model."""
        resources = []
        type_map = {
            "llm_provider": ResourceType.LLM_PROVIDER,
            "browser": ResourceType.BROWSER,
            "tool": ResourceType.LOCAL_TOOL,
            "local_service": ResourceType.LOCAL_SERVICE,
            "agent": ResourceType.AGENT,
        }
        for category in ("ai_services", "llm_providers", "browsers", "tools", "agents"):
            for item in observations[category]:
                configured = bool(item.get("configured", False))
                if category == "ai_services":
                    resource_type = ResourceType.LOCAL_SERVICE
                else:
                    resource_type = type_map[item["category"]]
                available = item.get("status") in {"available", "configured"}
                requires_verification = resource_type == ResourceType.LLM_PROVIDER
                adapter_id = item.get("adapter") if item.get("adapter") not in (None, "none") else None
                if resource_type in {ResourceType.BROWSER, ResourceType.LOCAL_TOOL} and available:
                    adapter_id = f"{resource_type.value}_adapter"
                resource = CapabilityResource(
                    resource_id=item["id"],
                    resource_type=resource_type,
                    display_name=item["name"],
                    provider_type=item.get("provider", ""),
                    discovered=True,
                    available=available,
                    configured=configured,
                    verified=bool(item.get("verified", False)),
                    execution_unavailable=not bool(item.get("execution_ready", False)) and resource_type == ResourceType.AGENT,
                    requires_configuration=resource_type == ResourceType.LLM_PROVIDER,
                    requires_verification=requires_verification,
                    requires_adapter=resource_type == ResourceType.AGENT,
                    requires_llm=bool(item.get("requires_llm", False)),
                    bound_provider_id=item.get("bound_provider_id"),
                    adapter_id=adapter_id,
                    last_scanned_at=observations["scan"]["scanned_at"],
                    machine_id=observations["scan"]["machine_id"],
                    source=item.get("source", "realtime_machine_scan"),
                    metadata=item,
                )
                resources.append(resource.safe_dict())
        providers = {}
        for item in resources:
            if item["resource_type"] != ResourceType.LLM_PROVIDER.value:
                continue
            provider_data = dict(item)
            if provider_data.get("authorization") == "[REDACTED]":
                provider_data["authorization"] = "not_required"
            providers[item["resource_id"]] = CapabilityResource(**provider_data)
        resolved = []
        for item in resources:
            resource_data = dict(item)
            if resource_data.get("authorization") == "[REDACTED]":
                resource_data["authorization"] = "not_required"
            resource = CapabilityResource(**resource_data)
            if resource.requires_llm:
                resource = resource.with_provider_dependency(providers.get(resource.bound_provider_id))
            resolved.append(resource.safe_dict())
        return resolved

    def get_available_tools(self) -> List[str]:
        return [x["id"] for x in self.scan_all()["tools"] if x["status"] == "available"]

    def get_tool_info(self, tool_name: str) -> Optional[dict]:
        return next((x for x in self.scan_all()["tools"] if x["id"] == tool_name), None)

    def get_summary(self) -> dict:
        result = self.scan_all()
        return {**result["summary"], "scan": result["scan"]}

    def _result(self, item_id: str, name: str, category: str, status: str,
                capabilities: Optional[List[str]] = None, **extra: Any) -> dict:
        return {"id": item_id, "name": name, "category": category, "status": status,
                "capabilities": capabilities or [], "source": "realtime_machine_scan", **extra}

    def _health(self, url: str) -> tuple[bool, Dict[str, Any]]:
        try:
            started = time.monotonic()
            response = httpx.get(url, timeout=1.5, proxy=None, trust_env=False)
            return response.status_code < 500, {"url": url, "status_code": response.status_code,
                                                "response_time_ms": int((time.monotonic() - started) * 1000)}
        except Exception as exc:
            return False, {"url": url, "error": type(exc).__name__}

    def _scan_ai_services(self) -> List[dict]:
        services = [
            ("ollama", "Ollama", "http://127.0.0.1:11434/api/tags", ["local_inference", "chat"]),
            ("lm_studio", "LM Studio", "http://127.0.0.1:1234/v1/models", ["local_inference", "chat"]),
            ("cc_switch", "CC Switch", "http://127.0.0.1:15721/v1/models", ["proxy", "chat"]),
            ("comfyui", "ComfyUI", "http://127.0.0.1:8188/system_stats", ["image_generation"]),
            ("n8n", "n8n", "http://127.0.0.1:5678/healthz", ["workflow_automation"]),
        ]
        result = []
        for item_id, name, url, caps in services:
            online, health = self._health(url)
            models = []
            if online and item_id in {"ollama", "lm_studio", "cc_switch"}:
                try:
                    payload = httpx.get(url, timeout=1.5, proxy=None, trust_env=False).json()
                    models = payload.get("models", payload.get("data", [])) if isinstance(payload, dict) else []
                    if item_id in {"ollama", "lm_studio"} and not models:
                        online = False
                        health["error"] = "服务在线但没有可用模型"
                except Exception:
                    pass
            result.append(self._result(item_id, name, "local_service", "available" if online else "unavailable",
                                       caps, endpoint=url, health=health,
                                       models=models,
                                       execution_ready=online and item_id in {"ollama", "lm_studio", "cc_switch"}))
        return result

    def _scan_llm_providers(self) -> List[dict]:
        providers = []
        for item in get_provider_info():
            configured = bool(item.get("configured"))
            providers.append(self._result(item["id"], item["name"], "llm_provider",
                                          "configured" if configured else "unavailable",
                                          ["chat", "reasoning"], model=item.get("model", ""),
                                          base_url=item.get("base_url", ""), configured=configured,
                                          credential_source="environment_variable" if configured else "none",
                                          credential_present=configured, execution_ready=False,
                                          note="已配置不等于已验证连接"))
        return providers

    def _scan_browsers(self) -> List[dict]:
        system = platform.system()
        candidates = {
            "Google Chrome": (["google-chrome", "chrome"], ["/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"] if system == "Darwin" else []),
            "Microsoft Edge": (["msedge", "microsoft-edge"], ["/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge"] if system == "Darwin" else []),
            "Firefox": (["firefox"], ["/Applications/Firefox.app/Contents/MacOS/firefox"] if system == "Darwin" else []),
            "Safari": ([], ["/Applications/Safari.app/Contents/MacOS/Safari"] if system == "Darwin" else []),
        }
        result = []
        for name, (commands, paths) in candidates.items():
            path = next((shutil.which(c) for c in commands if shutil.which(c)), None)
            path = path or next((p for p in paths if Path(p).exists()), "")
            result.append(self._result(name.lower().replace(" ", "_"), name, "browser",
                                       "available" if path else "unavailable", ["browse", "screenshot"],
                                       path=path, execution_ready=bool(path),
                                       error="未检测到浏览器可执行文件" if not path else ""))
        return result

    def _scan_tools(self) -> List[dict]:
        known = {
            "python": ("Python", ["python3", "python"], ["script", "code_execute"]),
            "node": ("Node.js", ["node"], ["script", "code_execute"]),
            "git": ("Git", ["git"], ["version_control"]),
            "docker": ("Docker", ["docker"], ["container"]),
            "code": ("VS Code", ["code"], ["editor"]),
        }
        result = []
        for item_id, (name, commands, caps) in known.items():
            path = next((shutil.which(c) for c in commands if shutil.which(c)), "")
            result.append(self._result(item_id, name, "tool", "available" if path else "unavailable",
                                       caps, path=path, version=self._version(path) if path else "",
                                       execution_ready=bool(path), error="未检测到命令" if not path else ""))
        return result

    def _scan_agents(self) -> List[dict]:
        result = []
        for command, (name, caps) in _KNOWN_AGENTS.items():
            path = shutil.which(command) or ""
            result.append(self._result(command, name, "agent", "available" if path else "unavailable", caps,
                                       path=path, version=self._version(path) if path else "",
                                       execution_ready=False, adapter="none",
                                       error="未检测到命令" if not path else "发现命令但没有安全执行适配器"))
        try:
            from backend.schemas.agent_manifest import scan_manifests
            manifests = scan_manifests()
            for manifest in manifests.values():
                if manifest.enabled:
                    result.append(self._result(
                        manifest.id, manifest.name, "agent", "available",
                        manifest.capabilities, source="project_manifest",
                        task_types=manifest.task_types, execution_ready=True,
                        adapter="project_agent_adapter", requires_llm=manifest.requires_api_key,
                        bound_provider_id=os.getenv("AI_PROVIDER", ""),
                    ))
            agents_root = Path(__file__).resolve().parents[2] / "agents"
            for agent_dir in agents_root.iterdir() if agents_root.exists() else ():
                if not agent_dir.is_dir() or not (agent_dir / "agent.py").exists():
                    continue
                agent_id = agent_dir.name.replace("_agent", "")
                if agent_id in manifests or agent_id.replace("_agent", "") in manifests:
                    continue
                result.append(self._result(
                    agent_id, agent_id.replace("_", " ").title(), "agent", "available",
                    ["local_agent"], source="project_agent", task_types=[agent_id.replace("_agent", "")],
                    execution_ready=True, adapter="project_agent_adapter",
                    requires_llm=False,
                    bound_provider_id=os.getenv("AI_PROVIDER", ""),
                ))
        except Exception:
            pass
        for config_path in (Path.home() / ".mcp.json", Path(".mcp.json"),
                            Path.home() / ".config" / "claude" / "mcp.json"):
            try:
                import json
                config = json.loads(config_path.read_text(encoding="utf-8"))
                for server_name, server in config.get("mcpServers", {}).items():
                    result.append(self._result(
                        f"mcp_{server_name}", f"MCP: {server_name}", "agent", "available",
                        ["mcp_tools"], source="mcp", endpoint=server.get("command", ""),
                        task_types=["chat", "code"], execution_ready=True,
                        adapter="mcp_adapter", requires_llm=False,
                    ))
            except (OSError, ValueError, TypeError):
                continue
        return result

    @staticmethod
    def _version(path: str) -> str:
        try:
            completed = subprocess.run([path, "--version"], capture_output=True, text=True,
                                       timeout=3, encoding="utf-8", errors="replace")
            lines = (completed.stdout or completed.stderr).strip().splitlines()
            return lines[0][:120] if completed.returncode == 0 and lines else ""
        except Exception:
            return ""


_scanner: Optional[CapabilityScanner] = None


def get_capability_scanner() -> CapabilityScanner:
    global _scanner
    if _scanner is None:
        _scanner = CapabilityScanner()
    return _scanner
