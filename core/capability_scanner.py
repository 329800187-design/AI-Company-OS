"""
Capability Scanner — 本机能力扫描器

自动扫描本机可用的 AI 服务和工具软件，无需用户配置。
扫描结果用于系统自动选择最佳执行路径。

扫描类别：
  1. AI 服务（DeepSeek/MiMo/Claude/OpenAI/Ollama/LM Studio/CC Switch）
  2. 浏览器（Chrome/Edge/Firefox）
  3. 本地工具（Python/Node/VS Code/Office/WPS）
  4. Agent 工具（OpenClaw/Codex CLI/Claude Code）

使用方式：
  scanner = CapabilityScanner()
  result = scanner.scan_all()
  ai_services = result["ai_services"]
  browsers = result["browsers"]
  tools = result["tools"]
"""
import os
import shutil
import subprocess
import sys
import time
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

import httpx

# 绕过系统代理的 HTTP 客户端
_http = httpx.Client(proxy=None, trust_env=False, timeout=5.0)


@dataclass
class ScanResult:
    """扫描结果"""
    name: str                    # 名称
    category: str                # 类别: ai_service / browser / tool / agent
    status: str                  # available / installed / running / unavailable
    path: str = ""               # 可执行文件路径
    url: str = ""                # 服务 URL
    version: str = ""            # 版本
    capabilities: List[str] = field(default_factory=list)  # 能力标签
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "category": self.category,
            "status": self.status,
            "path": self.path,
            "url": self.url,
            "version": self.version,
            "capabilities": self.capabilities,
            "metadata": self.metadata,
        }


class CapabilityScanner:
    """本机能力扫描器"""

    def __init__(self):
        self._results: Dict[str, ScanResult] = {}

    def scan_all(self, force: bool = False) -> Dict[str, Any]:
        """扫描所有能力"""
        if self._results and not force:
            return self._format_results()

        self._results = {}

        # 并行扫描各类能力
        self._scan_ai_services()
        self._scan_browsers()
        self._scan_tools()
        self._scan_agents()

        return self._format_results()

    def _format_results(self) -> Dict[str, Any]:
        """格式化扫描结果"""
        ai_services = []
        browsers = []
        tools = []
        agents = []

        for r in self._results.values():
            d = r.to_dict()
            if r.category == "ai_service":
                ai_services.append(d)
            elif r.category == "browser":
                browsers.append(d)
            elif r.category == "tool":
                tools.append(d)
            elif r.category == "agent":
                agents.append(d)

        return {
            "ai_services": ai_services,
            "browsers": browsers,
            "tools": tools,
            "agents": agents,
            "summary": {
                "ai_services": len(ai_services),
                "browsers": len(browsers),
                "tools": len(tools),
                "agents": len(agents),
                "total": len(self._results),
            },
        }

    # ── AI 服务扫描 ──────────────────────────────────────────

    def _scan_ai_services(self):
        """扫描 AI 服务"""
        # CC Switch (本地代理)
        self._check_http_service(
            "cc_switch", "CC Switch", "ai_service",
            "http://127.0.0.1:15721/v1/models",
            capabilities=["chat", "proxy", "multi_backend"]
        )

        # Ollama (本地推理)
        self._check_http_service(
            "ollama", "Ollama", "ai_service",
            "http://127.0.0.1:11434/api/tags",
            capabilities=["chat", "local_inference"]
        )

        # LM Studio (本地推理)
        self._check_http_service(
            "lm_studio", "LM Studio", "ai_service",
            "http://127.0.0.1:1234/v1/models",
            capabilities=["chat", "local_inference"]
        )

        # MiMo Gateway (本地代理)
        self._check_http_service(
            "mimo_gateway", "MiMo Gateway", "ai_service",
            "http://127.0.0.1:8080/v1/models",
            capabilities=["chat", "code"]
        )

        # 检查环境变量中的 API Key
        self._check_env_api_keys()

    def _check_http_service(self, key: str, name: str, category: str,
                            url: str, capabilities: List[str] = None):
        """检查 HTTP 服务是否可用"""
        try:
            r = _http.get(url)
            if r.status_code == 200:
                self._results[key] = ScanResult(
                    name=name,
                    category=category,
                    status="available",
                    url=url,
                    capabilities=capabilities or [],
                    metadata={"response_time_ms": int(r.elapsed.total_seconds() * 1000)},
                )
        except Exception:
            pass

    def _check_env_api_keys(self):
        """检查环境变量中的 API Key"""
        api_keys = {
            "deepseek": {"name": "DeepSeek", "env": "DEEPSEEK_API_KEY", "caps": ["chat", "code"]},
            "openai": {"name": "OpenAI", "env": "OPENAI_API_KEY", "caps": ["chat", "code", "image"]},
            "claude": {"name": "Claude", "env": "ANTHROPIC_API_KEY", "caps": ["chat", "code", "analysis"]},
            "mimo": {"name": "MiMo", "env": "MIMO_API_KEY", "caps": ["chat", "code"]},
        }

        for key, info in api_keys.items():
            api_key = os.getenv(info["env"], "")
            if api_key:
                self._results[f"api_{key}"] = ScanResult(
                    name=info["name"],
                    category="ai_service",
                    status="configured",
                    capabilities=info["caps"],
                    metadata={"env_var": info["env"], "key_preview": api_key[:8] + "..."},
                )

    # ── 浏览器扫描 ──────────────────────────────────────────

    def _scan_browsers(self):
        """扫描浏览器"""
        browsers = [
            ("chrome", "Google Chrome", [
                r"C:\Program Files\Google\Chrome\Application\chrome.exe",
                r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
                os.path.expandvars(r"%LOCALAPPDATA%\Google\Chrome\Application\chrome.exe"),
            ]),
            ("edge", "Microsoft Edge", [
                r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
                r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
            ]),
            ("firefox", "Firefox", [
                r"C:\Program Files\Mozilla Firefox\firefox.exe",
                r"C:\Program Files (x86)\Mozilla Firefox\firefox.exe",
            ]),
        ]

        for key, name, paths in browsers:
            found_path = ""
            for p in paths:
                if os.path.exists(p):
                    found_path = p
                    break

            if found_path:
                self._results[f"browser_{key}"] = ScanResult(
                    name=name,
                    category="browser",
                    status="installed",
                    path=found_path,
                    capabilities=["browse", "screenshot"],
                )

    # ── 本地工具扫描 ──────────────────────────────────────────

    def _scan_tools(self):
        """扫描本地工具"""
        # Python
        python_path = shutil.which("python") or shutil.which("python3")
        if python_path:
            version = self._get_version(python_path, "--version")
            self._results["tool_python"] = ScanResult(
                name="Python",
                category="tool",
                status="available",
                path=python_path,
                version=version,
                capabilities=["code_execute", "script"],
            )

        # Node.js
        node_path = shutil.which("node")
        if node_path:
            version = self._get_version(node_path, "--version")
            self._results["tool_node"] = ScanResult(
                name="Node.js",
                category="tool",
                status="available",
                path=node_path,
                version=version,
                capabilities=["code_execute", "script"],
            )

        # VS Code
        code_path = shutil.which("code")
        if code_path:
            self._results["tool_vscode"] = ScanResult(
                name="VS Code",
                category="tool",
                status="installed",
                path=code_path,
                capabilities=["editor", "ide"],
            )

        # Office
        office_paths = [
            (r"C:\Program Files\Microsoft Office\root\Office16\WINWORD.EXE", "Microsoft Word"),
            (r"C:\Program Files (x86)\Microsoft Office\root\Office16\WINWORD.EXE", "Microsoft Word"),
            (r"C:\Program Files\WPS Office\11.1.0.12345\office6\wps.exe", "WPS Office"),
        ]
        for path, name in office_paths:
            if os.path.exists(path):
                self._results["tool_office"] = ScanResult(
                    name=name,
                    category="tool",
                    status="installed",
                    path=path,
                    capabilities=["document", "spreadsheet"],
                )
                break

    # ── Agent 工具扫描 ──────────────────────────────────────────

    def _scan_agents(self):
        """扫描 Agent 工具"""
        # OpenClaw
        self._check_http_service(
            "agent_openclaw", "OpenClaw", "agent",
            "http://127.0.0.1:18789/",
            capabilities=["browser", "scrape", "screenshot"]
        )

        # Codex CLI
        codex_home = os.path.expandvars(r"%LOCALAPPDATA%\OpenAI\Codex")
        if os.path.isdir(codex_home):
            bin_dir = os.path.join(codex_home, "bin")
            if os.path.isdir(bin_dir):
                for entry in sorted(os.listdir(bin_dir), reverse=True):
                    exe = os.path.join(bin_dir, entry, "codex.exe")
                    if os.path.exists(exe):
                        self._results["agent_codex"] = ScanResult(
                            name="Codex CLI",
                            category="agent",
                            status="installed",
                            path=exe,
                            capabilities=["code", "computer_use", "browser"],
                        )
                        break

        # Claude Code
        claude_path = shutil.which("claude")
        if claude_path:
            self._results["agent_claude_code"] = ScanResult(
                name="Claude Code",
                category="agent",
                status="installed",
                path=claude_path,
                capabilities=["code", "analysis", "file_ops"],
            )

    # ── 辅助方法 ──────────────────────────────────────────

    def _get_version(self, path: str, flag: str) -> str:
        """获取工具版本"""
        try:
            r = subprocess.run([path, flag], capture_output=True, text=True, timeout=5)
            return r.stdout.strip().split("\n")[0] if r.returncode == 0 else ""
        except Exception:
            return ""

    def get_available_ai_services(self) -> List[Dict[str, Any]]:
        """获取可用的 AI 服务列表"""
        self.scan_all()
        return [
            r.to_dict() for r in self._results.values()
            if r.category == "ai_service" and r.status in ("available", "configured")
        ]

    def get_best_ai_service(self) -> Optional[Dict[str, Any]]:
        """获取最佳 AI 服务（优先级：本地服务 > 云端 API）"""
        services = self.get_available_ai_services()
        if not services:
            return None

        # 优先使用本地服务（低延迟）
        local_priority = ["cc_switch", "ollama", "lm_studio", "mimo_gateway"]
        for key in local_priority:
            for s in services:
                if s["name"].lower().replace(" ", "_") == key:
                    return s

        # 其次使用云端 API
        cloud_priority = ["deepseek", "openai", "claude", "mimo"]
        for key in cloud_priority:
            for s in services:
                if s["name"].lower() == key:
                    return s

        return services[0] if services else None


# ── 单例 ──────────────────────────────────────────

_scanner: Optional[CapabilityScanner] = None


def get_capability_scanner() -> CapabilityScanner:
    global _scanner
    if _scanner is None:
        _scanner = CapabilityScanner()
    return _scanner
