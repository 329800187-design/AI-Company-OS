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
    get_provider_info, get_ai_config,
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


@router.get("/providers", summary="获取所有 AI Provider 状态")
def list_providers():
    """返回所有 AI Provider 信息（不包含 Key）"""
    return {"providers": get_provider_info(), "current": AI_PROVIDER}


@router.get("/status", summary="获取完整配置状态")
def config_status():
    """获取当前系统配置（敏感信息脱敏）"""
    def _mask(key: str) -> str:
        if not key:
            return ""
        if len(key) <= 8:
            return "***"
        return key[:4] + "****" + key[-4:]

    return {
        "server": {
            "host": HOST,
            "port": PORT,
            "auth_configured": bool(AUTH_TOKEN),
        },
        "providers": get_provider_info(),
        "current_provider": AI_PROVIDER,
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
        "AI_PROVIDER": "ai_provider",
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

    for env_key, json_key in env_map.items():
        if json_key in data_dict:
            val = str(data_dict[json_key])
            # 双重保险：再次过滤注入字符
            existing[env_key] = _sanitize_env_value(val)

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
    return {"status": "ok", "message": "配置已保存，部分配置需要重启服务后生效"}


@router.post("/test", summary="测试 AI Provider 连接")
def test_connection(data: TestConnectionData):
    """测试指定的 Provider 是否能正常连接"""
    provider = data.provider
    try:
        config = get_ai_config(provider)
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
        return {"status": "ok", "message": f"[OK] {provider} connection success"}
    except Exception as e:
        return {"status": "error", "message": f"[FAIL] {provider} connection failed: {str(e)}"}
