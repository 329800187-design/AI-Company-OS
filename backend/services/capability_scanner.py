"""
Local Capability Scanner — 本地能力扫描器

启动时检测用户电脑中有哪些可用 AI 工具：
1. Claude Code
2. ComfyUI
3. Ollama
4. OpenClaw / Browser Agent
5. Python Data 工具
6. API 模型配置
"""
import os
import subprocess
import shutil
import socket
from pathlib import Path
from typing import Dict, List, Optional
from backend.logger import get_logger

logger = get_logger()


class CapabilityScanner:
    """本地能力扫描器"""

    def __init__(self):
        self._cache: Dict[str, dict] = {}
        self._scanned = False

    def scan_all(self, force: bool = False) -> Dict[str, dict]:
        """扫描所有本地能力"""
        if self._scanned and not force:
            return self._cache

        logger.info("CapabilityScanner: Starting full scan...")

        self._cache = {
            "hermes": self._scan_hermes(),
            "claude_code": self._scan_claude_code(),
            "comfyui": self._scan_comfyui(),
            "ollama": self._scan_ollama(),
            "openclaw": self._scan_openclaw(),
            "data_tools": self._scan_data_tools(),
            "api_models": self._scan_api_models(),
            "mimo": self._scan_mimo(),
        }

        self._scanned = True
        logger.info(f"CapabilityScanner: Scan complete. Available: {self.get_available_tools()}")
        return self._cache

    def get_available_tools(self) -> List[str]:
        """获取可用工具列表"""
        return [tool for tool, info in self._cache.items() if info.get("available")]

    def get_tool_info(self, tool_name: str) -> Optional[dict]:
        """获取指定工具信息"""
        return self._cache.get(tool_name)

    def get_summary(self) -> dict:
        """获取扫描摘要"""
        available = self.get_available_tools()
        unavailable = [t for t in self._cache if t not in available]

        return {
            "total_tools": len(self._cache),
            "available_count": len(available),
            "unavailable_count": len(unavailable),
            "available_tools": available,
            "unavailable_tools": unavailable,
            "overall_status": "ready" if len(available) >= 3 else "limited"
        }

    def _create_result(self, tool: str, available: bool, installed: bool = False,
                       running: bool = False, version: str = "", models: list = None,
                       error: str = "", fix_hint: str = "") -> dict:
        """创建统一的扫描结果"""
        return {
            "tool": tool,
            "available": available,
            "installed": installed,
            "running": running,
            "version": version,
            "models": models or [],
            "error": error,
            "fix_hint": fix_hint
        }

    # ── Hermes Agent ──────────────────────────────────────────

    def _scan_hermes(self) -> dict:
        """扫描 Hermes Agent"""
        try:
            # 检测 hermes 命令
            hermes_path = shutil.which("hermes")
            if not hermes_path:
                # 尝试常见安装路径
                hermes_paths = [
                    Path.home() / "AppData" / "Local" / "hermes" / "hermes-agent" / "venv" / "Scripts" / "hermes.exe",
                    Path("C:/Program Files/hermes/hermes.exe"),
                ]
                for path in hermes_paths:
                    if path.exists():
                        hermes_path = str(path)
                        break

            if not hermes_path:
                return self._create_result(
                    "hermes", False,
                    error="未找到 hermes 命令",
                    fix_hint="请安装 Hermes Agent"
                )

            # 检测版本
            try:
                result = subprocess.run(
                    [hermes_path, "--version"],
                    capture_output=True, text=True, timeout=10
                )
                version = result.stdout.strip() if result.returncode == 0 else "unknown"
            except:
                version = "unknown"

            # 检测是否在运行
            running = self._check_hermes_process()

            return self._create_result(
                "hermes", True,
                installed=True, running=running, version=version
            )
        except Exception as e:
            return self._create_result(
                "hermes", False,
                error=str(e),
                fix_hint="请确保 Hermes Agent 已正确安装"
            )

    def _check_hermes_process(self) -> bool:
        """检查 Hermes 进程是否在运行"""
        try:
            import psutil
            for proc in psutil.process_iter(['name']):
                if proc.info['name'] and 'hermes' in proc.info['name'].lower():
                    return True
        except:
            pass
        return False

    # ── Claude Code ──────────────────────────────────────────

    def _scan_claude_code(self) -> dict:
        """扫描 Claude Code"""
        try:
            # 检测 claude 命令
            claude_path = shutil.which("claude")
            if not claude_path:
                return self._create_result(
                    "claude_code", False,
                    error="未找到 claude 命令",
                    fix_hint="请安装 Claude Code: npm install -g @anthropic-ai/claude-code"
                )

            # 检测版本
            try:
                result = subprocess.run(
                    ["claude", "--version"],
                    capture_output=True, text=True, timeout=10
                )
                version = result.stdout.strip() if result.returncode == 0 else "unknown"
            except:
                version = "unknown"

            return self._create_result(
                "claude_code", True,
                installed=True, running=True, version=version
            )
        except Exception as e:
            return self._create_result(
                "claude_code", False,
                error=str(e),
                fix_hint="请确保 Claude Code 已安装并在 PATH 中"
            )

    # ── ComfyUI ──────────────────────────────────────────────

    def _scan_comfyui(self) -> dict:
        """扫描 ComfyUI"""
        # 常见安装路径
        comfyui_paths = [
            Path.home() / "ComfyUI-Installs" / "comfyui-local",
            Path("C:/ComfyUI"),
            Path("D:/ComfyUI"),
            Path.home() / "ComfyUI",
        ]

        # 检查环境变量
        env_path = os.getenv("COMFYUI_PATH")
        if env_path:
            comfyui_paths.insert(0, Path(env_path))

        comfyui_dir = None
        for path in comfyui_paths:
            if path.exists() and (path / "main.py").exists():
                comfyui_dir = path
                break

        if not comfyui_dir:
            return self._create_result(
                "comfyui", False,
                error="未找到 ComfyUI 安装目录",
                fix_hint="请安装 ComfyUI 或设置 COMFYUI_PATH 环境变量"
            )

        # 检查 checkpoints
        checkpoints_dir = comfyui_dir / "models" / "checkpoints"
        models = []
        if checkpoints_dir.exists():
            models = [f.stem for f in checkpoints_dir.glob("*.safetensors")]

        # 检查端口是否在线
        running = self._check_port(8188)

        return self._create_result(
            "comfyui", running,
            installed=True, running=running,
            models=models,
            error="" if running else "ComfyUI 未启动",
            fix_hint="" if running else f"请启动 ComfyUI: cd {comfyui_dir} && python main.py"
        )

    # ── Ollama ───────────────────────────────────────────────

    def _scan_ollama(self) -> dict:
        """扫描 Ollama"""
        try:
            # 检测 ollama 命令
            ollama_path = shutil.which("ollama")
            if not ollama_path:
                return self._create_result(
                    "ollama", False,
                    error="未找到 ollama 命令",
                    fix_hint="请安装 Ollama: https://ollama.ai"
                )

            # 检测 API 是否在线
            running = self._check_port(11434)

            # 获取模型列表
            models = []
            if running:
                try:
                    import httpx
                    with httpx.Client(timeout=5) as client:
                        response = client.get("http://localhost:11434/api/tags")
                        if response.status_code == 200:
                            data = response.json()
                            models = [m["name"] for m in data.get("models", [])]
                except:
                    pass

            # 只有运行且有模型才算可用
            available = running and len(models) > 0

            if not running:
                error = "Ollama 未启动"
                fix_hint = "请启动 Ollama: ollama serve"
            elif len(models) == 0:
                error = "Ollama 没有可用模型"
                fix_hint = "请下载模型: ollama pull llama2"
            else:
                error = ""
                fix_hint = ""

            return self._create_result(
                "ollama", available,
                installed=True, running=running,
                models=models,
                error=error,
                fix_hint=fix_hint
            )
        except Exception as e:
            return self._create_result(
                "ollama", False,
                error=str(e),
                fix_hint="请确保 Ollama 已安装并在 PATH 中"
            )

    # ── OpenClaw ──────────────────────────────────────────────

    def _scan_openclaw(self) -> dict:
        """扫描 OpenClaw"""
        try:
            # 检测是否可以 import
            from agents.openclaw_agent.agent import OpenClawAgent

            # 检测 Playwright
            try:
                import playwright
                playwright_installed = True
            except ImportError:
                playwright_installed = False

            if not playwright_installed:
                return self._create_result(
                    "openclaw", False,
                    installed=True,
                    error="Playwright 未安装",
                    fix_hint="请安装 Playwright: pip install playwright && playwright install chromium"
                )

            # 检测浏览器
            try:
                from playwright.sync_api import sync_playwright
                # 不在 asyncio 环境中测试
                import asyncio
                try:
                    asyncio.get_running_loop()
                    # 在 asyncio 环境中，跳过同步测试
                    browser_available = True
                except RuntimeError:
                    # 不在 asyncio 环境中，可以测试
                    browser_available = True
            except:
                browser_available = False

            return self._create_result(
                "openclaw", browser_available,
                installed=True, running=browser_available,
                error="" if browser_available else "浏览器依赖异常",
                fix_hint="" if browser_available else "请运行: playwright install chromium"
            )
        except ImportError:
            return self._create_result(
                "openclaw", False,
                error="OpenClaw Agent 未找到",
                fix_hint="请确保 agents/openclaw_agent 目录存在"
            )
        except Exception as e:
            return self._create_result(
                "openclaw", False,
                error=str(e),
                fix_hint="请检查 OpenClaw 安装"
            )

    # ── Data Tools ────────────────────────────────────────────

    def _scan_data_tools(self) -> dict:
        """扫描数据分析工具"""
        missing = []
        available = []

        # 检查 pandas
        try:
            import pandas
            available.append(f"pandas {pandas.__version__}")
        except ImportError:
            missing.append("pandas")

        # 检查 openpyxl
        try:
            import openpyxl
            available.append(f"openpyxl {openpyxl.__version__}")
        except ImportError:
            missing.append("openpyxl")

        # 检查 matplotlib
        try:
            import matplotlib
            available.append(f"matplotlib {matplotlib.__version__}")
        except ImportError:
            missing.append("matplotlib")

        if missing:
            return self._create_result(
                "data_tools", False,
                installed=True,
                error=f"缺少依赖: {', '.join(missing)}",
                fix_hint=f"请安装: pip install {' '.join(missing)}",
                models=available
            )

        return self._create_result(
            "data_tools", True,
            installed=True, running=True,
            models=available
        )

    # ── API Models ────────────────────────────────────────────

    def _scan_api_models(self) -> dict:
        """扫描 API 模型配置"""
        models = []

        # DeepSeek
        if os.getenv("DEEPSEEK_API_KEY"):
            models.append({"provider": "deepseek", "configured": True, "masked_key": self._mask_key(os.getenv("DEEPSEEK_API_KEY"))})

        # OpenAI
        if os.getenv("OPENAI_API_KEY"):
            models.append({"provider": "openai", "configured": True, "masked_key": self._mask_key(os.getenv("OPENAI_API_KEY"))})

        # Claude
        if os.getenv("CLAUDE_API_KEY"):
            models.append({"provider": "claude", "configured": True, "masked_key": self._mask_key(os.getenv("CLAUDE_API_KEY"))})

        available = len(models) > 0

        return self._create_result(
            "api_models", available,
            installed=available, running=available,
            models=models,
            error="" if available else "未配置任何 API Key",
            fix_hint="" if available else "请在 .env 文件中配置至少一个 API Key"
        )

    # ── MiMo ────────────────────────────────────────────────

    def _scan_mimo(self) -> dict:
        """扫描 MiMo 配置"""
        api_key = os.getenv("MIMO_API_KEY", "")
        model = os.getenv("MIMO_MODEL", "mimo-v2.5-pro")
        web_search_enabled = os.getenv("MIMO_ENABLE_WEB_SEARCH", "true").lower() == "true"

        if not api_key:
            return self._create_result(
                "mimo", False,
                error="未配置 MIMO_API_KEY",
                fix_hint="请配置 MIMO_API_KEY"
            )

        return self._create_result(
            "mimo", True,
            installed=True, running=True,
            models=[{"provider": "mimo", "model": model, "web_search_enabled": web_search_enabled}],
            error="",
            fix_hint=""
        )

    # ── Helper Methods ────────────────────────────────────────

    def _check_port(self, port: int, host: str = "localhost") -> bool:
        """检查端口是否在线"""
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(2)
            result = sock.connect_ex((host, port))
            sock.close()
            return result == 0
        except:
            return False

    def _mask_key(self, key: str) -> str:
        """脱敏 API Key"""
        if not key or len(key) < 8:
            return "***"
        return key[:4] + "****" + key[-4:]


# 全局实例
_scanner = None


def get_capability_scanner() -> CapabilityScanner:
    """获取能力扫描器单例"""
    global _scanner
    if _scanner is None:
        _scanner = CapabilityScanner()
    return _scanner
