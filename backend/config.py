"""
配置中心 — 统一管理所有配置
优先级: 环境变量 > .env 文件 > 默认值
"""
import os
import sys
from pathlib import Path
from typing import Optional

# 尝试加载 .env 文件
try:
    from dotenv import load_dotenv
    _ENV_FILE = Path(__file__).parent.parent / ".env"
    if _ENV_FILE.exists():
        load_dotenv(_ENV_FILE)
    else:
        # 尝试从 .env.example 中读取（降级模式）
        _EXAMPLE = Path(__file__).parent.parent / ".env.example"
        if _EXAMPLE.exists():
            load_dotenv(_EXAMPLE)
except ImportError:
    pass


def _bool(v: str, default: bool = False) -> bool:
    """解析布尔值"""
    if not v:
        return default
    return v.strip().lower() in ("true", "1", "yes", "on")


def _int(v: str, default: int = 0) -> int:
    """解析整数"""
    try:
        return int(v.strip())
    except (ValueError, AttributeError):
        return default


# ── 服务器 ───────────────────────────────────────────────────
HOST: str = os.getenv("HOST", "0.0.0.0")
PORT: int = _int(os.getenv("PORT", "8000"), 8000)
ENV: str = os.getenv("ENV", "development")
AUTH_TOKEN: str = os.getenv("AUTH_TOKEN", "")

# ── AI Provider ─────────────────────────────────────────────
AI_PROVIDER: str = os.getenv("AI_PROVIDER", "deepseek")

DEEPSEEK_API_KEY: str = os.getenv("DEEPSEEK_API_KEY", "")
DEEPSEEK_BASE_URL: str = os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com")
DEEPSEEK_MODEL: str = os.getenv("DEEPSEEK_MODEL", "deepseek-chat")

OPENAI_API_KEY: str = os.getenv("OPENAI_API_KEY", "")
OPENAI_BASE_URL: str = os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1")
OPENAI_MODEL: str = os.getenv("OPENAI_MODEL", "gpt-4o")

CLAUDE_API_KEY: str = os.getenv("CLAUDE_API_KEY", "")
CLAUDE_BASE_URL: str = os.getenv("CLAUDE_BASE_URL", "https://api.anthropic.com")
CLAUDE_MODEL: str = os.getenv("CLAUDE_MODEL", "claude-sonnet-4-20250514")

# ── Agent ──────────────────────────────────────────────────
CODEX_TIMEOUT: int = _int(os.getenv("CODEX_TIMEOUT", "30"), 30)
CODEX_MAX_OUTPUT: int = _int(os.getenv("CODEX_MAX_OUTPUT", "100000"), 100000)
OPENCLAW_HEADLESS: bool = _bool(os.getenv("OPENCLAW_HEADLESS", "true"), True)
OPENCLAW_TIMEOUT: int = _int(os.getenv("OPENCLAW_TIMEOUT", "30"), 30)

# ── 数据库 ─────────────────────────────────────────────────
DATABASE_URL: str = os.getenv("DATABASE_URL", "")  # PostgreSQL URL（留空则用 SQLite）

# ── Boss Command Center ─────────────────────────────────────
BOSS_EXECUTION_PROVIDER: str = os.getenv("BOSS_EXECUTION_PROVIDER", "local_heuristic")
# 可选值: local_mock / local_heuristic / hermes
# 默认 local_heuristic，保证离线可跑

# ── 日志 ───────────────────────────────────────────────────
LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")
LOG_DIR: str = os.getenv("LOG_DIR", "./logs")
LOG_MAX_DAYS: int = _int(os.getenv("LOG_MAX_DAYS", "7"), 7)


def get_ai_config(provider: Optional[str] = None) -> dict:
    """获取当前 AI Provider 的配置"""
    provider = provider or AI_PROVIDER
    configs = {
        "deepseek": {
            "api_key": DEEPSEEK_API_KEY,
            "base_url": DEEPSEEK_BASE_URL,
            "model": DEEPSEEK_MODEL,
        },
        "openai": {
            "api_key": OPENAI_API_KEY,
            "base_url": OPENAI_BASE_URL,
            "model": OPENAI_MODEL,
        },
        "claude": {
            "api_key": CLAUDE_API_KEY,
            "base_url": CLAUDE_BASE_URL,
            "model": CLAUDE_MODEL,
        },
    }
    cfg = configs.get(provider, configs["deepseek"])
    if not cfg["api_key"]:
        raise RuntimeError(
            f"未设置 {provider.upper()}_API_KEY。请在 .env 文件或 Web UI 设置页面中填写。"
        )
    return cfg


def get_provider_info() -> list[dict]:
    """返回所有 Provider 的信息（不含 Key）"""
    return [
        {
            "id": "deepseek",
            "name": "DeepSeek",
            "model": DEEPSEEK_MODEL,
            "configured": bool(DEEPSEEK_API_KEY),
            "base_url": DEEPSEEK_BASE_URL,
        },
        {
            "id": "openai",
            "name": "OpenAI",
            "model": OPENAI_MODEL,
            "configured": bool(OPENAI_API_KEY),
            "base_url": OPENAI_BASE_URL,
        },
        {
            "id": "claude",
            "name": "Anthropic Claude",
            "model": CLAUDE_MODEL,
            "configured": bool(CLAUDE_API_KEY),
            "base_url": CLAUDE_BASE_URL,
        },
    ]


# ── 新增：Brain Manager 和 Capability Scanner 集成 ──────────

def get_brain_manager():
    """获取主脑管理器（懒加载）"""
    from core.brain_manager import get_brain_manager as _get
    return _get()


def get_capability_scanner():
    """获取能力扫描器（懒加载）"""
    from core.capability_scanner import get_capability_scanner as _get
    return _get()


def get_system_status() -> dict:
    """获取系统状态（面向小白）"""
    brain_mgr = get_brain_manager()
    scanner = get_capability_scanner()

    # 扫描能力
    capabilities = scanner.scan_all()

    # 获取当前主脑
    current_brain = brain_mgr.get_current()

    # 获取可用主脑
    available_brains = brain_mgr.list_available()

    return {
        "current_brain": current_brain,
        "available_brains": len(available_brains),
        "capabilities": capabilities["summary"],
        "ai_services": capabilities["ai_services"],
        "browsers": capabilities["browsers"],
        "tools": capabilities["tools"],
        "agents": capabilities["agents"],
    }
