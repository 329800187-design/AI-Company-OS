"""配置路由器 — Web UI 可调用的配置管理接口"""
import os
import re
from pathlib import Path
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, field_validator
from typing import Optional

from backend.config import (
    HOST, PORT, AI_PROVIDER, AUTH_TOKEN,
    DEEPSEEK_API_KEY, DEEPSEEK_BASE_URL, DEEPSEEK_MODEL,
    OPENAI_API_KEY, OPENAI_BASE_URL, OPENAI_MODEL,
    CLAUDE_API_KEY, CLAUDE_BASE_URL, CLAUDE_MODEL,
    CODEX_TIMEOUT, CODEX_MAX_OUTPUT,
    OPENCLAW_HEADLESS, OPENCLAW_TIMEOUT,
    LOG_LEVEL, LOG_DIR, LOG_MAX_DAYS,
    get_provider_info, get_ai_config, get_current_provider, apply_runtime_config,
)
from backend.services.provider_verification import (
    get_provider_verification,
    invalidate_provider,
    set_provider_verification,
)
from backend.middleware.auth_middleware import set_auth_token, set_auth_enabled

router = APIRouter(prefix="/config", tags=["配置管理 / Config"])

ENV_FILE = Path(__file__).parent.parent.parent / ".env"


def _sanitize_env_value(v: str) -> str:
    """防止换行注入 — 移除所有控制字符和换行符"""
    if not v:
        return ""
    # 移除换行符（防止注入额外环境变量）和非法控制字符
    return re.sub(r'[\r\n\x00-\x08\x0b\x0c\x0e-\x1f]', '', v)


class ProviderUpdate(BaseModel):
    provider: str  # deepseek / openai / claude
    api_key: str = ""
    base_url: str = ""
    model: str = ""


class ServerConfig(BaseModel):
    host: str = "0.0.0.0"
    port: int = 8000
    auth_token: str = ""


class ConfigSaveData(BaseModel):
    """配置保存请求（字段均可选，仅更新提供的字段）"""
    ai_provider: Optional[str] = None
    deepseek_api_key: Optional[str] = None
    deepseek_base_url: Optional[str] = None
    deepseek_model: Optional[str] = None
    openai_api_key: Optional[str] = None
    openai_base_url: Optional[str] = None
    openai_model: Optional[str] = None
    claude_api_key: Optional[str] = None
    claude_base_url: Optional[str] = None
    claude_model: Optional[str] = None
    auth_token: Optional[str] = None
    auth_enabled: Optional[bool] = None

    @field_validator('*')
    @classmethod
    def sanitize_strings(cls, v):
        """清理所有字符串字段，防止注入"""
        if isinstance(v, str):
            return _sanitize_env_value(v)
        return v


class TestConnectionData(BaseModel):
    """测试连接请求"""
    provider: str = "deepseek"


class SwitchProviderData(BaseModel):
    provider: str = "deepseek"


@router.get("/providers", summary="获取所有 AI Provider 状态")
def list_providers():
    """返回所有 AI Provider 信息（不包含 Key）"""
    return {"providers": get_provider_info(), "current": get_current_provider()}


@router.get("/providers/health", summary="获取 Search/Image Provider 健康状态")
def providers_health():
    """返回 Search 和 Image Provider 状态（不暴露 API Key）

    用于前端 Provider 状态面板，显示：
    - 当前使用的 provider 名称
    - 是否为 mock 模式
    - API key 是否已配置
    - 各 provider 的可用性
    """
    from backend.services.web_search_service import get_provider_info as get_search_info
    from backend.services.image_generation_service import get_image_provider

    # Search provider
    search_info = get_search_info()

    # Image provider
    img_provider = get_image_provider()
    img_has_key = bool(os.getenv("OPENAI_API_KEY"))
    img_env = os.getenv("IMAGE_PROVIDER", "auto")

    return {
        "search": {
            "name": search_info["provider"],
            "is_mock": "Mock" in search_info["provider"],
            "has_api_key": search_info["has_api_key"],
            "env_provider": search_info["env_provider"],
            "available": True,  # mock always available
            "providers": [
                {"name": "serpapi", "has_key": bool(os.getenv("SERPAPI_API_KEY")), "env_var": "SERPAPI_API_KEY"},
                {"name": "bing", "has_key": bool(os.getenv("BING_SEARCH_API_KEY")), "env_var": "BING_SEARCH_API_KEY"},
            ],
        },
        "image": {
            "name": img_provider.name,
            "is_mock": img_provider.name == "mock",
            "has_api_key": img_has_key,
            "env_provider": img_env,
            "available": True,
            "providers": [
                {"name": "openai", "has_key": img_has_key, "env_var": "OPENAI_API_KEY"},
            ],
        },
    }


@router.get("/status", summary="获取完整配置状态")
def config_status():
    """获取当前系统配置（敏感信息脱敏）"""
    def _mask(key: str) -> str:
        if not key:
            return ""
        if len(key) <= 8:
            return "***"
        return key[:4] + "****" + key[-4:]

    from core.brain_manager import get_brain_manager
    brain_manager = get_brain_manager()
    return {
        "server": {
            "host": HOST,
            "port": PORT,
            "auth_configured": bool(AUTH_TOKEN),
        },
        "providers": get_provider_info(),
        "current_provider": get_current_provider(),
        "current_brain": brain_manager.get_current(),
        "agents": {
            "codex_timeout": CODEX_TIMEOUT,
            "codex_max_output": CODEX_MAX_OUTPUT,
            "openclaw_headless": OPENCLAW_HEADLESS,
            "openclaw_timeout": OPENCLAW_TIMEOUT,
        },
        "logging": {
            "level": LOG_LEVEL,
            "dir": LOG_DIR,
            "max_days": LOG_MAX_DAYS,
        },
    }


@router.post("/save", summary="保存配置到 .env 文件",
              description="保存配置。所有字段可选，只更新提供的字段。字符串字段自动过滤换行注入。")
def save_config(data: ConfigSaveData):
    """将配置写入 .env 文件（Pydantic 校验 + 防注入）"""
    data_dict = data.model_dump(exclude_none=True)

    # 读取现有内容
    existing = {}
    if ENV_FILE.exists():
        for line in ENV_FILE.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                existing[k.strip()] = v.strip()

    # 合并新值
    env_map = {
        "DEEPSEEK_API_KEY": "deepseek_api_key",
        "DEEPSEEK_BASE_URL": "deepseek_base_url",
        "DEEPSEEK_MODEL": "deepseek_model",
        "OPENAI_API_KEY": "openai_api_key",
        "OPENAI_BASE_URL": "openai_base_url",
        "OPENAI_MODEL": "openai_model",
        "CLAUDE_API_KEY": "claude_api_key",
        "CLAUDE_BASE_URL": "claude_base_url",
        "CLAUDE_MODEL": "claude_model",
        "AUTH_TOKEN": "auth_token",
    }
    provider_by_config_field = {
        "deepseek_api_key": "deepseek",
        "deepseek_base_url": "deepseek",
        "deepseek_model": "deepseek",
        "openai_api_key": "openai",
        "openai_base_url": "openai",
        "openai_model": "openai",
        "claude_api_key": "claude",
        "claude_base_url": "claude",
        "claude_model": "claude",
    }

    verify_invalidation: set[str] = set()

    for env_key, json_key in env_map.items():
        if json_key in data_dict:
            val = str(data_dict[json_key])
            if json_key.endswith("_api_key") and not val.strip():
                continue
            # 双重保险：再次过滤注入字符
            sanitized = _sanitize_env_value(val)
            existing[env_key] = sanitized
            if json_key in provider_by_config_field:
                provider = provider_by_config_field[json_key]
                verify_invalidation.add(provider)

    runtime_values = {
        env_key: _sanitize_env_value(str(data_dict[json_key]))
        for env_key, json_key in env_map.items()
        if json_key in data_dict
    }

    # 空 API Key 不覆盖旧值：在此过滤后仅写入非空值
    runtime_values = {
        env_key: value
        for env_key, value in runtime_values.items()
        if not env_key.endswith("_API_KEY") or value.strip()
    }
    apply_runtime_config(runtime_values)

    for provider in verify_invalidation:
        invalidate_provider(provider)

    # 认证配置特殊处理：运行时生效
    if "auth_token" in data_dict:
        existing["AUTH_TOKEN"] = data_dict["auth_token"]
        set_auth_token(data_dict["auth_token"])
    if "auth_enabled" in data_dict:
        existing["AUTH_ENABLED"] = "true" if data_dict["auth_enabled"] else "false"
        set_auth_enabled(data_dict["auth_enabled"])

    # 写回文件（每行验证不包含非法字符）
    lines = []
    for k, v in existing.items():
        # 最终防御：只允许安全的 key=value 格式
        if not re.match(r'^[A-Z_][A-Z0-9_]*$', k):
            continue  # 非法 key，跳过
        lines.append(f"{k}={v}")

    ENV_FILE.write_text("\n".join(lines) + "\n", encoding="utf-8")
    from core.brain_manager import get_brain_manager
    return {
        "status": "ok",
        "message": "配置已保存",
        "current_provider": get_current_provider(),
        "current_brain": get_brain_manager().get_current(),
    }


@router.post("/switch", summary="切换 AI Provider")
def switch_provider(data: SwitchProviderData):
    """只切换运行中的 Provider，不写入配置。"""
    provider = (data.provider or "").strip()
    provider_info = next((p for p in get_provider_info() if p.get("id") == provider), None)
    if not provider_info:
        raise HTTPException(status_code=400, detail="不支持的 provider")
    if not provider_info.get("configured"):
        raise HTTPException(status_code=400, detail="该 Provider 未配置 API Key，无法切换")
    if not get_provider_verification(provider).get("verified"):
        raise HTTPException(status_code=400, detail="该 Provider 未通过测试验证，请先执行连接测试")

    from core.brain_manager import get_brain_manager
    result = get_brain_manager().switch_to(provider)
    if not result.get("ok"):
        raise HTTPException(status_code=400, detail=result.get("error", "Provider 不可用"))
    return {
        "status": "ok",
        "message": result.get("message", "Provider 已切换"),
        "current_provider": get_current_provider(),
        "current_brain": get_brain_manager().get_current(),
    }


@router.post("/test", summary="测试 AI Provider 连接")
def test_connection(data: TestConnectionData):
    """测试指定的 Provider 是否能正常连接"""
    provider = data.provider
    try:
        config = get_ai_config(provider)
        if not config["api_key"]:
            return {"status": "error", "message": f"{provider} 尚未配置 API Key"}
        import httpx

        if provider == "claude":
            url = f"{config['base_url']}/v1/messages"
            headers = {
                "x-api-key": config["api_key"],
                "Content-Type": "application/json",
                "anthropic-version": "2023-06-01",
            }
            body = {
                "model": config["model"],
                "max_tokens": 10,
                "messages": [{"role": "user", "content": "Hi"}],
            }
        else:
            url = f"{config['base_url']}/chat/completions"
            headers = {"Authorization": f"Bearer {config['api_key']}", "Content-Type": "application/json"}
            body = {
                "model": config["model"],
                "messages": [{"role": "user", "content": "Hi"}],
                "max_tokens": 10,
            }

        resp = httpx.post(url, headers=headers, json=body, timeout=15)
        resp.raise_for_status()
        message = f"[OK] {provider} connection success"
        set_provider_verification(provider, verified=True, message=message)
        return {"status": "ok", "message": message, "verified": True}
    except Exception as e:
        message = f"[FAIL] {provider} connection failed: {str(e)}"
        try:
            set_provider_verification(provider, verified=False, message=message)
        except ValueError:
            pass
        return {"status": "error", "message": message, "verified": False}
