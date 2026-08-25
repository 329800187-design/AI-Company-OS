"""
AI Resource Registry — Auto-Discover + Capability Router
========================================================
Scans the local machine for AI services, tests connectivity,
registers capabilities, and provides a unified dispatch interface.

Discovered resources (as of boot scan):
  - CC Switch      127.0.0.1:15721    Multi-backend proxy (DeepSeek, OpenAI, Codex)
  - OpenClaw       127.0.0.1:18789    Browser automation + Canvas
  - Codex CLI      local filesystem    Computer-use, browser, code execution
  - ChatGPT CLI    WindowsApps         OpenAI chat (desktop app)
  - Kimi           local filesystem    Moonshot AI desktop app

Architecture:
  Registry → Scanner → Probe → Capability Registration → Dispatch Router
"""
import json
import os
import shutil
import subprocess
import sys
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

import httpx

# 创建绕过 Windows 系统代理的 httpx 客户端
# httpx >= 0.28 默认 trust_env=True，会通过 IE/WinHTTP 代理，导致本地地址返回 502
_http = httpx.Client(proxy=None, trust_env=False, timeout=10.0)


def _get(url: str, **kwargs) -> httpx.Response:
    return _http.get(url, **kwargs)


def _post(url: str, **kwargs) -> httpx.Response:
    return _http.post(url, **kwargs)


def _cc_switch_config() -> tuple[str, str, str]:
    """Read the local proxy configuration without embedding a credential."""
    base_url = os.getenv("CC_SWITCH_BASE_URL", "http://127.0.0.1:15721").rstrip("/")
    api_key = os.getenv("CC_SWITCH_API_KEY", "").strip()
    model = os.getenv("CC_SWITCH_MODEL", "deepseek-v4-pro").strip() or "deepseek-v4-pro"
    return base_url, api_key, model


def _cc_switch_headers(api_key: str) -> Dict[str, str]:
    headers = {
        "Content-Type": "application/json",
        "anthropic-version": "2023-06-01",
    }
    if api_key:
        headers["x-api-key"] = api_key
    return headers

# ═══════════════════════════════════════════════════════════════
# Data Model
# ═══════════════════════════════════════════════════════════════


@dataclass
class AIService:
    """An AI service registered in the system"""
    service_id: str
    name: str                          # e.g. "CC Switch", "OpenClaw", "ChatGPT"
    provider: str                      # e.g. "deepseek", "openai", "openclaw", "moonshot"
    kind: str                          # "proxy" | "agent" | "cli" | "desktop_app"
    status: str = "unknown"            # "online" | "offline" | "unknown"
    base_url: str = ""                 # API endpoint if applicable
    models: List[str] = field(default_factory=list)
    capabilities: List[str] = field(default_factory=list)  # ["chat", "browser", "code", "computer_use", ...]
    exe_path: Optional[str] = None
    pid: Optional[int] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    last_checked: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "service_id": self.service_id,
            "name": self.name,
            "provider": self.provider,
            "kind": self.kind,
            "status": self.status,
            "base_url": self.base_url,
            "models": self.models,
            "capabilities": self.capabilities,
            "exe_path": self.exe_path,
            "pid": self.pid,
            "metadata": self.metadata,
            "last_checked": self.last_checked,
        }


# ═══════════════════════════════════════════════════════════════
# Scanners — each one finds a specific AI service
# ═══════════════════════════════════════════════════════════════

class CCScanner:
    """Scan CC Switch — the multi-backend proxy hub at 127.0.0.1:15721"""

    def scan(self) -> Optional[AIService]:
        base_url, api_key, default_model = _cc_switch_config()
        svc = AIService(
            service_id="cc-switch",
            name="CC Switch",
            provider="cc-switch",
            kind="proxy",
            base_url=base_url,
            capabilities=["chat", "proxy", "multi_backend"],
        )

        # Test Anthropic-compatible endpoint (already verified working)
        try:
            r = _get(f"{base_url}/v1/models", timeout=10)
            if r.status_code == 200:
                svc.status = "online"
                svc.last_checked = time.time()
                data = r.json()
                svc.models = data.get("models", data.get("data", []))
                if isinstance(svc.models, list) and svc.models and isinstance(svc.models[0], dict):
                    svc.models = [m.get("id", str(m)) for m in svc.models]
        except Exception:
            pass

        # Try to discover backend providers by probing known paths
        try:
            r = _get(f"{base_url}/providers", timeout=3)
            if r.status_code == 200:
                svc.metadata["providers_raw"] = r.json()
        except Exception:
            pass

        # Test actual chat capability
        if svc.status == "online" and api_key:
            try:
                r = _post(
                    f"{base_url}/v1/messages",
                    headers=_cc_switch_headers(api_key),
                    json={
                        "model": default_model,
                        "max_tokens": 5,
                        "messages": [{"role": "user", "content": "ping"}],
                    },
                    timeout=10,
                )
                if r.status_code == 200:
                    svc.capabilities.append("verified_working")
                    svc.metadata["default_model"] = default_model
                    svc.metadata["api_type"] = "anthropic_compatible"
            except Exception:
                pass
        elif svc.status == "online":
            svc.metadata["auth_configured"] = False

        return svc


class OpenClawScanner:
    """Scan OpenClaw — browser automation agent at 127.0.0.1:18789"""

    def scan(self) -> Optional[AIService]:
        svc = AIService(
            service_id="openclaw",
            name="OpenClaw",
            provider="openclaw",
            kind="agent",
            base_url="http://127.0.0.1:18789",
            capabilities=["browser", "screenshot", "scrape", "canvas", "file_system"],
        )

        # OpenClaw serves its Control UI on port 18789 — a 200 on GET / means it's running
        try:
            r = _get("http://127.0.0.1:18789/", timeout=5)
            if r.status_code == 200:
                svc.status = "online"
                svc.last_checked = time.time()
                svc.metadata["control_ui"] = "http://127.0.0.1:18789/"
                svc.metadata["canvas_url"] = "http://127.0.0.1:18789/__openclaw__/canvas/"
        except Exception:
            svc.status = "offline"

        # Check if OpenClaw process is running
        pid = self._find_process("openclaw")
        if pid:
            svc.pid = pid
            svc.metadata["process_found"] = True

        return svc

    @staticmethod
    def _find_process(name: str) -> Optional[int]:
        try:
            if sys.platform == "win32":
                r = subprocess.run(["tasklist", "/fo", "csv", "/nh"], capture_output=True, text=True, timeout=5)
                for line in r.stdout.strip().split("\n"):
                    parts = line.replace('"', '').split(",")
                    if len(parts) >= 2 and name.lower() in parts[0].strip().lower():
                        return int(parts[1].strip())
            else:
                r = subprocess.run(["pgrep", "-f", name], capture_output=True, text=True, timeout=5)
                if r.stdout.strip():
                    return int(r.stdout.strip().split("\n")[0])
        except Exception:
            pass
        return None


class CodexScanner:
    """Scan Codex CLI — OpenAI's local Codex agent"""

    CODEX_HOME = os.path.expandvars(r"%LOCALAPPDATA%\OpenAI\Codex")

    def scan(self) -> Optional[AIService]:
        svc = AIService(
            service_id="codex-cli",
            name="Codex CLI",
            provider="openai",
            kind="cli",
            capabilities=["chat", "code", "computer_use", "browser", "mcp"],
        )

        if not os.path.isdir(self.CODEX_HOME):
            svc.status = "not_installed"
            return svc

        # Find latest codex.exe
        bin_dir = os.path.join(self.CODEX_HOME, "bin")
        if os.path.isdir(bin_dir):
            for entry in sorted(os.listdir(bin_dir), reverse=True):
                exe = os.path.join(bin_dir, entry, "codex.exe")
                if os.path.exists(exe):
                    svc.exe_path = exe
                    svc.metadata["bin_version"] = entry
                    break

        # Check node_repl (MCP server for computer-use)
        runtimes = os.path.join(self.CODEX_HOME, "runtimes", "cua_node")
        if os.path.isdir(runtimes):
            for d in os.listdir(runtimes):
                repl = os.path.join(runtimes, d, "bin", "node_repl.exe")
                if os.path.exists(repl):
                    svc.metadata["node_repl"] = repl
                    svc.metadata["node_repl_version"] = d
                    break

        # Read config for additional info
        config_path = os.path.join(os.path.expandvars(r"%USERPROFILE%"), ".codex", "config.toml")
        if os.path.exists(config_path):
            svc.metadata["has_config"] = True
            svc.metadata["config_path"] = config_path
            # Codex proxies through CC Switch
            svc.metadata["proxy_via"] = "cc-switch:15721"

        svc.status = "installed"
        svc.last_checked = time.time()
        return svc


class ChatGPTScanner:
    """Scan ChatGPT desktop app"""

    def scan(self) -> Optional[AIService]:
        svc = AIService(
            service_id="chatgpt",
            name="ChatGPT",
            provider="openai",
            kind="desktop_app",
            capabilities=["chat", "file_analysis", "long_context", "deep_read"],
        )

        chatgpt_path = shutil.which("chatgpt.exe")
        if chatgpt_path:
            svc.exe_path = chatgpt_path
            svc.metadata["cl_path"] = str(Path(chatgpt_path).resolve())
            # WindowsApps path is usually a 0-byte appexec link
            try:
                real_path = str(Path(chatgpt_path).resolve())
                if "WindowsApps" in real_path:
                    svc.metadata["note"] = "Windows Store app, CLI interface may be limited"
            except Exception:
                pass

        if svc.exe_path:
            svc.status = "installed"
        else:
            svc.status = "not_found"

        svc.last_checked = time.time()
        return svc


class KimiScanner:
    """Scan Kimi (Moonshot AI) desktop app"""

    def scan(self) -> Optional[AIService]:
        svc = AIService(
            service_id="kimi",
            name="Kimi (豆包)",
            provider="moonshot",
            kind="desktop_app",
            capabilities=["chat", "long_context", "image_generation", "search"],
        )

        kimi_path = os.path.expandvars(r"%LOCALAPPDATA%\Programs\kimi-desktop\Kimi.exe")
        if os.path.exists(kimi_path):
            svc.exe_path = kimi_path

        # Check if running
        pid = self._find_process("Kimi")
        if pid:
            svc.pid = pid
            svc.status = "running"

        # 只有未检测到运行时才根据 exe_path 判断
        if svc.status != "running":
            svc.status = "installed" if svc.exe_path else "not_found"
        svc.last_checked = time.time()
        return svc

    @staticmethod
    def _find_process(name: str) -> Optional[int]:
        try:
            if sys.platform == "win32":
                r = subprocess.run(["tasklist", "/fo", "csv", "/nh"], capture_output=True, text=True, timeout=5)
                for line in r.stdout.strip().split("\n"):
                    parts = line.replace('"', '').split(",")
                    if len(parts) >= 2 and name.lower() in parts[0].strip().lower():
                        return int(parts[1].strip())
        except Exception:
            pass
        return None


class OllamaScanner:
    """Scan Ollama — local LLM at 127.0.0.1:11434"""

    def scan(self) -> Optional[AIService]:
        svc = AIService(
            service_id="ollama", name="Ollama", provider="ollama",
            kind="proxy", base_url="http://127.0.0.1:11434",
            capabilities=["chat", "local_inference", "text_generation"],
        )
        try:
            r = _get("http://127.0.0.1:11434/api/tags", timeout=3)
            if r.status_code == 200:
                svc.status = "online"
                svc.last_checked = time.time()
                data = r.json()
                models = data.get("models", [])
                svc.models = [m.get("name", str(m)) for m in models]
        except Exception:
            pass
        return svc


class LMStudioScanner:
    """Scan LM Studio — local GUI LLM at 127.0.0.1:1234"""

    def scan(self) -> Optional[AIService]:
        svc = AIService(
            service_id="lm-studio", name="LM Studio", provider="lm-studio",
            kind="proxy", base_url="http://127.0.0.1:1234/v1",
            capabilities=["chat", "local_inference", "openai_compatible"],
        )
        try:
            r = _get("http://127.0.0.1:1234/v1/models", timeout=3)
            if r.status_code == 200:
                svc.status = "online"
                svc.last_checked = time.time()
                data = r.json()
                models = data.get("data", [])
                svc.models = [m.get("id", str(m)) for m in models]
        except Exception:
            pass
        return svc


class LlamaCppScanner:
    """Scan llama.cpp server at 127.0.0.1:8080"""

    def scan(self) -> Optional[AIService]:
        svc = AIService(
            service_id="llama-cpp", name="llama.cpp", provider="llama-cpp",
            kind="proxy", base_url="http://127.0.0.1:8080",
            capabilities=["chat", "local_inference", "openai_compatible"],
        )
        try:
            r = _get("http://127.0.0.1:8080/v1/models", timeout=3)
            if r.status_code == 200:
                svc.status = "online"
                svc.last_checked = time.time()
        except Exception:
            pass
        return svc


# ═══════════════════════════════════════════════════════════════
# Registry — orchestrates all scanners + dispatch
# ═══════════════════════════════════════════════════════════════

class AIRegistry:
    """AI 资源注册中心 — 自动发现 + 能力路由"""

    # Dispatch table: capability → (priority_service_id, task_type)
    CAPABILITY_ROUTES = {
        "chat":          ("cc-switch", "chat"),
        "code":          ("codex-cli", "code_execute"),
        "browser":       ("openclaw", "browser_scrape"),
        "screenshot":    ("openclaw", "browser_screenshot"),
        "scrape":        ("openclaw", "browser_scrape"),
        "canvas":        ("openclaw", "canvas"),
        "computer_use":  ("codex-cli", "computer_use"),
        "image_generation": ("kimi", "image_generate"),
        "file_analysis": ("chatgpt", "file_analyze"),
        "search":        ("kimi", "web_search"),
        "proxy":         ("cc-switch", "proxy_chat"),
    }

    def __init__(self):
        self._services: Dict[str, AIService] = {}
        self._scanners = [
            CCScanner(), OllamaScanner(), LMStudioScanner(), LlamaCppScanner(),
            OpenClawScanner(), CodexScanner(), ChatGPTScanner(), KimiScanner(),
        ]
        self._last_scan: float = 0.0

    # ── Scan ────────────────────────────────────────────────

    def scan_all(self, force: bool = False) -> Dict[str, AIService]:
        """扫描所有 AI 资源（缓存 30 秒 + 应用级缓存）"""
        from core.cache_store import cache
        cache_key = "ai_registry_services"
        if not force:
            cached = cache.get(cache_key)
            if cached:
                self._services = cached
                return self._services
        now = time.time()
        if not force and self._services and (now - self._last_scan) < 30:
            return self._services

        success_count = 0
        for scanner in self._scanners:
            try:
                svc = scanner.scan()
                if svc:
                    self._services[svc.service_id] = svc
                    success_count += 1
            except Exception as e:
                print(f"[AIRegistry] {scanner.__class__.__name__} 扫描失败: {e}", file=sys.stderr)

        # 只有当至少一个扫描成功时才更新缓存
        if success_count > 0:
            self._last_scan = now
            cache.set(cache_key, self._services, ttl=120)  # 应用级缓存 120s
        return self._services

    def get_service(self, service_id: str) -> Optional[AIService]:
        """获取单个服务"""
        self.scan_all()
        return self._services.get(service_id)

    # ── Query ───────────────────────────────────────────────

    def list_all(self) -> List[Dict[str, Any]]:
        self.scan_all()
        return [s.to_dict() for s in self._services.values()]

    def list_cached(self) -> List[Dict[str, Any]]:
        """Return the last scanned services without triggering a fresh scan."""
        return [s.to_dict() for s in self._services.values()]

    def list_online(self) -> List[Dict[str, Any]]:
        self.scan_all()
        return [s.to_dict() for s in self._services.values() if s.status in ("online", "running")]

    def get_capabilities(self) -> Dict[str, List[str]]:
        """返回所有可用的能力及其提供者"""
        self.scan_all()
        caps: Dict[str, List[str]] = {}
        for svc in self._services.values():
            if svc.status in ("online", "running", "installed"):
                for cap in svc.capabilities:
                    caps.setdefault(cap, []).append(svc.service_id)
        return caps

    # ── Route ───────────────────────────────────────────────

    def best_for(self, capability: str) -> Optional[str]:
        """给定能力，返回最佳服务 ID"""
        # 先确保服务已扫描
        self.scan_all()

        route = self.CAPABILITY_ROUTES.get(capability)
        if route:
            svc_id = route[0]
            svc = self._services.get(svc_id)
            if svc and svc.status in ("online", "running", "installed"):
                return svc_id

        # Fallback: 遍历找到第一个有此能力的服务
        for svc in self._services.values():
            if capability in svc.capabilities and svc.status in ("online", "running", "installed"):
                return svc.service_id
        return None

    def route_by_goal(self, goal: str) -> Dict[str, Any]:
        """
        根据用户目标关键词智能路由到最合适的 AI 服务。
        这是给 Commander 用的核心方法。
        """
        goal_lower = goal.lower()

        # 代码相关 → Codex
        if any(kw in goal_lower for kw in ["代码", "code", "程序", "脚本", "开发", "bug", "测试", "运行", "执行", "python", "javascript", "写一个", "实现"]):
            return {"service": "codex-cli", "task_type": "code_execute", "reason": "代码/编程任务匹配 Codex CLI"}

        # 浏览器相关 → OpenClaw
        if any(kw in goal_lower for kw in ["网页", "浏览器", "截图", "抓取", "打开", "表单", "页面", "browser", "screenshot", "scrape", "网站", "链接"]):
            return {"service": "openclaw", "task_type": "browser_scrape", "reason": "浏览器操作匹配 OpenClaw"}

        # 文件分析 → ChatGPT
        if any(kw in goal_lower for kw in ["分析文件", "读文档", "总结", "长篇", "长文档", "pdf", "报告", "论文", "读", "文档"]):
            return {"service": "chatgpt", "task_type": "file_analyze", "reason": "文档/文件分析匹配 ChatGPT"}

        # 图片相关 → Kimi
        if any(kw in goal_lower for kw in ["图片", "图像", "画", "生成图", "image", "picture", "设计", "海报"]):
            return {"service": "kimi", "task_type": "image_generate", "reason": "图片生成匹配 Kimi (豆包)"}

        # General chat → CC Switch (always available)
        return {"service": "cc-switch", "task_type": "chat", "reason": "通用推理 → CC Switch (DeepSeek V4 Pro)"}

    # ── Execute ─────────────────────────────────────────────

    def execute(self, service_id: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        """向指定 AI 服务发送任务并返回结果"""
        svc = self._services.get(service_id)
        if not svc:
            # Try scanning
            self.scan_all(force=True)
            svc = self._services.get(service_id)
            if not svc:
                return {"success": False, "error": f"服务不存在: {service_id}"}

        if svc.status not in ("online", "running", "installed"):
            return {"success": False, "error": f"服务不可用: {svc.name} ({svc.status})"}

        # Dispatch by service
        if service_id == "cc-switch":
            return self._exec_cc_switch(svc, payload)
        elif service_id == "openclaw":
            return self._exec_openclaw(svc, payload)
        elif service_id == "codex-cli":
            return self._exec_local_python(svc, payload)
        elif service_id in ("chatgpt", "kimi"):
            return self._exec_desktop_app(svc, payload)

        return {"success": False, "error": f"不支持的服务: {service_id}"}

    def _exec_cc_switch(self, svc: AIService, payload: Dict) -> Dict[str, Any]:
        """通过 CC Switch 发送 chat 请求"""
        prompt = payload.get("prompt", payload.get("目标", ""))
        if not prompt:
            return {"success": False, "error": "缺少 prompt 字段"}

        system = payload.get("system_prompt", "你是 AI Company OS 的智能助手。")
        base_url, api_key, default_model = _cc_switch_config()
        if not api_key:
            return {
                "success": False,
                "error": "CC Switch credential is not configured; set CC_SWITCH_API_KEY before executing chat tasks.",
                "service": "cc-switch",
            }
        model = payload.get("model", svc.metadata.get("default_model", default_model))

        try:
            r = _post(
                f"{base_url}/v1/messages",
                headers=_cc_switch_headers(api_key),
                json={
                    "model": model,
                    "max_tokens": payload.get("max_tokens", 2048),
                    "temperature": payload.get("temperature", 0.7),
                    "thinking": {"type": "enabled", "budget_tokens": 200},
                    "system": system,
                    "messages": [{"role": "user", "content": prompt}],
                },
                timeout=120,
            )
            r.raise_for_status()
            data = r.json()
            if not isinstance(data, dict):
                return {"success": False, "error": f"非预期的响应格式", "service": "cc-switch"}
            # DeepSeek V4 Pro returns thinking + text blocks; collect all text blocks
            text = ""
            for block in data.get("content", []):
                if isinstance(block, dict) and block.get("type") == "text":
                    text += block.get("text", "")
            return {
                "success": True,
                "service": "cc-switch",
                "model": data.get("model", model),
                "result": text[:10000],
                "usage": data.get("usage", {}),
            }
        except Exception as e:
            return {"success": False, "error": str(e), "service": "cc-switch"}

    def _exec_openclaw(self, svc: AIService, payload: Dict) -> Dict[str, Any]:
        """通过 OpenClaw Agent 执行浏览器任务"""
        try:
            from agents.openclaw_agent.agent import OpenClawAgent

            goal = payload.get("goal", payload.get("prompt", ""))
            url = payload.get("url", payload.get("目标URL", ""))
            task_type = payload.get("task_type", "browser_scrape")
            selector = payload.get("selector", "")

            agent = OpenClawAgent(
                headless=payload.get("headless", True),
                timeout=payload.get("timeout", 30),
                allow_browser_automation=payload.get("allow_browser_automation", False),
            )

            task = {
                "task_id": f"registry_openclaw_{uuid.uuid4().hex[:8]}",
                "task_type": task_type,
                "goal": goal or f"浏览器操作: {url}",
                "url": url,
                "selector": selector,
                "extract_type": payload.get("extract_type", "text"),
                "full_page": payload.get("full_page", False),
            }

            result = agent.run(task)
            # 检查浏览器授权拦截
            if result.get("status") == "blocked":
                return {
                    "success": False,
                    "service": "openclaw",
                    "error": result.get("message", "需要用户授权浏览器采集"),
                    "blocked_reason": result.get("blocked_reason", "browser_automation_approval_required"),
                }
            return {
                "success": result.get("success", False),
                "service": "openclaw",
                "result": result.get("result", ""),
                "data": result.get("data", []),
                "screenshot_path": result.get("screenshot_path", ""),
                "page_title": result.get("page_title", ""),
                "agent_result": result,
            }
        except ImportError:
            return {
                "success": False,
                "service": "openclaw",
                "error": "Playwright 未安装。请运行: pip install playwright && playwright install chromium",
            }
        except Exception as e:
            return {
                "success": False,
                "service": "openclaw",
                "error": f"OpenClaw 执行失败: {str(e)}",
            }

    def _exec_local_python(self, svc: AIService, payload: Dict) -> Dict[str, Any]:
        """通过 CodexAgent 的安全沙箱执行 Python 代码"""
        code = payload.get("code", payload.get("代码内容", ""))
        if not code:
            return {"success": False, "error": "缺少 code 字段"}

        try:
            from agents.codex_agent.agent import CodexAgent
            agent = CodexAgent(timeout=payload.get("timeout", 30))
            task = {
                "task_id": f"registry_codex_{uuid.uuid4().hex[:8]}",
                "task_type": "code_execute",
                "goal": payload.get("goal", "代码执行"),
                "code": code,
            }
            result = agent.run(task)
            success = result.get("success", False)
            return {
                "success": success,
                "service": "codex-cli",
                "result": result.get("result", result.get("stdout", ""))[:5000],
                "stderr": result.get("stderr", "")[:5000],
                "exit_code": result.get("exit_code", -1),
                "sandbox_path": result.get("sandbox_path", ""),
            }
        except ImportError:
            return {"success": False, "error": "Codex Agent 不可用", "service": "codex-cli"}
        except Exception as e:
            return {"success": False, "error": f"沙箱执行失败: {str(e)}", "service": "codex-cli"}

    def _exec_desktop_app(self, svc: AIService, payload: Dict) -> Dict[str, Any]:
        """启动桌面 AI 应用"""
        exe = svc.exe_path
        if not exe:
            return {"success": False, "error": f"{svc.name} 路径未找到"}

        try:
            if sys.platform == "win32":
                subprocess.Popen([exe], creationflags=subprocess.CREATE_NEW_CONSOLE)
            else:
                subprocess.Popen([exe], start_new_session=True)
            return {
                "success": True,
                "service": svc.service_id,
                "result": f"已启动 {svc.name} ({exe})",
                "note": "桌面应用已在前台打开，可通过其自带界面交互",
            }
        except Exception as e:
            return {"success": False, "error": str(e), "service": svc.service_id}


# ═══════════════════════════════════════════════════════════════
# Singleton
# ═══════════════════════════════════════════════════════════════

_registry: Optional[AIRegistry] = None


def get_registry() -> AIRegistry:
    global _registry
    if _registry is None:
        _registry = AIRegistry()
    return _registry
