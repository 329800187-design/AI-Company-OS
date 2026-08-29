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

# ── Hermes Execution Provider ───────────────────────────────
HERMES_CLI_PATH: str = os.getenv("HERMES_CLI_PATH", "hermes")
HERMES_EXECUTION_TIMEOUT_SECONDS: int = _int(os.getenv("HERMES_EXECUTION_TIMEOUT_SECONDS", "180"), 180)
HERMES_ECOMMERCE_MODE_ENABLED: bool = _bool(os.getenv("HERMES_ECOMMERCE_MODE_ENABLED", "false"), False)
# Hermes CLI 路径，默认 "hermes"（假设在 PATH 中）
# 执行超时，默认 180 秒
# 是否启用电商模式（默认关闭，需显式 opt-in）

# ── 浏览器自动化审批闸门 ──────────────────────────────────
BROWSER_AUTOMATION_REQUIRE_APPROVAL: bool = _bool(os.getenv("BROWSER_AUTOMATION_REQUIRE_APPROVAL", "true"), True)
BROWSER_AUTOMATION_APPROVED: bool = _bool(os.getenv("BROWSER_AUTOMATION_APPROVED", "false"), False)
# 默认需要审批才能执行浏览器自动化采集
# BROWSER_AUTOMATION_APPROVED=true 时允许自动执行
# 也可通过 API 参数 allow_browser_automation=True 临时授权

# ── 日志 ───────────────────────────────────────────────────
LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")
LOG_DIR: str = os.getenv("LOG_DIR", "./logs")
LOG_MAX_DAYS: int = _int(os.getenv("LOG_MAX_DAYS", "7"), 7)

# ── Feishu / Lark Bot ─────────────────────────────────────
FEISHU_BOT_ENABLED: bool = _bool(os.getenv("FEISHU_BOT_ENABLED", "false"), False)
FEISHU_APP_ID: str = os.getenv("FEISHU_APP_ID", "")
FEISHU_APP_SECRET: str = os.getenv("FEISHU_APP_SECRET", "")
FEISHU_VERIFICATION_TOKEN: str = os.getenv("FEISHU_VERIFICATION_TOKEN", "")
FEISHU_ENCRYPT_KEY: str = os.getenv("FEISHU_ENCRYPT_KEY", "")
FEISHU_REPLY_ONLY_MENTION: bool = _bool(os.getenv("FEISHU_REPLY_ONLY_MENTION", "true"), True)
FEISHU_MAX_REPLY_CHARS: int = _int(os.getenv("FEISHU_MAX_REPLY_CHARS", "1800"), 1800)
FEISHU_CONNECTION_MODE: str = os.getenv("FEISHU_CONNECTION_MODE", "long_connection")


def get_current_provider() -> str:
    """Read the provider at call time so Web UI changes work without restart."""
    return os.getenv("AI_PROVIDER", AI_PROVIDER) or "deepseek"


def get_ai_config(provider: Optional[str] = None) -> dict:
    """获取当前 AI Provider 的配置"""
    provider = provider or get_current_provider()
    configs = {
        "deepseek": {
            "api_key": os.getenv("DEEPSEEK_API_KEY", DEEPSEEK_API_KEY),
            "base_url": os.getenv("DEEPSEEK_BASE_URL", DEEPSEEK_BASE_URL),
            "model": os.getenv("DEEPSEEK_MODEL", DEEPSEEK_MODEL),
        },
        "openai": {
            "api_key": os.getenv("OPENAI_API_KEY", OPENAI_API_KEY),
            "base_url": os.getenv("OPENAI_BASE_URL", OPENAI_BASE_URL),
            "model": os.getenv("OPENAI_MODEL", OPENAI_MODEL),
        },
        "claude": {
            "api_key": os.getenv("CLAUDE_API_KEY", CLAUDE_API_KEY) or os.getenv("ANTHROPIC_API_KEY", ""),
            "base_url": os.getenv("CLAUDE_BASE_URL", CLAUDE_BASE_URL),
            "model": os.getenv("CLAUDE_MODEL", CLAUDE_MODEL),
        },
    }
    cfg = configs.get(provider, configs["deepseek"]).copy()
    cfg["provider"] = provider
    return cfg


def get_provider_info() -> list[dict]:
    """返回所有 Provider 的信息（不含 Key）"""
    return [
        {
            "id": "deepseek",
            "name": "DeepSeek",
            "model": os.getenv("DEEPSEEK_MODEL", DEEPSEEK_MODEL),
            "configured": bool(os.getenv("DEEPSEEK_API_KEY", DEEPSEEK_API_KEY)),
            "base_url": os.getenv("DEEPSEEK_BASE_URL", DEEPSEEK_BASE_URL),
        },
        {
            "id": "openai",
            "name": "OpenAI",
            "model": os.getenv("OPENAI_MODEL", OPENAI_MODEL),
            "configured": bool(os.getenv("OPENAI_API_KEY", OPENAI_API_KEY)),
            "base_url": os.getenv("OPENAI_BASE_URL", OPENAI_BASE_URL),
        },
        {
            "id": "claude",
            "name": "Anthropic Claude",
            "model": os.getenv("CLAUDE_MODEL", CLAUDE_MODEL),
            "configured": bool(os.getenv("CLAUDE_API_KEY", CLAUDE_API_KEY) or os.getenv("ANTHROPIC_API_KEY", "")),
            "base_url": os.getenv("CLAUDE_BASE_URL", CLAUDE_BASE_URL),
        },
    ]


def apply_runtime_config(values: dict) -> None:
    """Apply Web UI provider changes to the current process without restart."""
    allowed = {
        "AI_PROVIDER", "DEEPSEEK_API_KEY", "DEEPSEEK_BASE_URL", "DEEPSEEK_MODEL",
        "OPENAI_API_KEY", "OPENAI_BASE_URL", "OPENAI_MODEL",
        "CLAUDE_API_KEY", "CLAUDE_BASE_URL", "CLAUDE_MODEL",
    }
    for key, value in values.items():
        if key not in allowed:
            continue
        text = str(value or "")
        os.environ[key] = text
        globals()[key] = text


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
