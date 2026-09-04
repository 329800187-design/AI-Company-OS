"""API Key 认证中间件

支持两种模式：
1. Bearer Token 模式：请求头 Authorization: Bearer <api_key>
2. 头部字段模式：X-API-Key: <api_key>

配置：
- AUTH_ENABLED=true/false（.env 配置，默认 true）
- AUTH_TOKEN=<your-api-key>（启用认证时必须设置）
"""
import hmac
import os
from pathlib import Path
from typing import Optional

from fastapi import Request, HTTPException
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse

# ── 白名单路径（不需认证）────────────────────────────────────
WHITELIST_PATHS = {
    "/docs",
    "/openapi.json",
    "/redoc",
    "/health",
    "/auth",
    "/favicon.ico",
}

def _load_auth_config() -> dict:
    """从环境变量 / .env 加载认证配置"""
    # 尝试直接读取 .env 文件
    env_file = Path(__file__).parent.parent.parent / ".env"
    auth_enabled_from_env = "AUTH_ENABLED" in os.environ
    auth_token_from_env = "AUTH_TOKEN" in os.environ
    auth_enabled = os.getenv("AUTH_ENABLED", "true").lower() in ("true", "1", "yes")
    auth_token = os.getenv("AUTH_TOKEN", "")

    # 如果 .env 没加载到，从文件直接读
    if env_file.exists():
        for line in env_file.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line.startswith("AUTH_TOKEN=") and not auth_token_from_env:
                auth_token = line.split("=", 1)[1].strip()
            elif line.startswith("AUTH_ENABLED=") and not auth_enabled_from_env:
                auth_enabled = line.split("=", 1)[1].strip().lower() in ("true", "1", "yes")

    if auth_enabled and not auth_token:
        raise RuntimeError(
            "AUTH_TOKEN must be configured when AUTH_ENABLED=true. "
            "Set AUTH_TOKEN in the environment or .env before starting the service."
        )

    return {
        "enabled": auth_enabled,
        "token": auth_token,
    }

# 全局配置（启动时加载）
AUTH_CONFIG = _load_auth_config()


def get_auth_config() -> dict:
    """获取当前认证配置"""
    return {
        "enabled": AUTH_CONFIG["enabled"],
        "token": AUTH_CONFIG["token"] if AUTH_CONFIG["enabled"] else "",
    }


def set_auth_token(new_token: str):
    """运行时更新认证 Token"""
    AUTH_CONFIG["token"] = new_token


def set_auth_enabled(enabled: bool):
    """运行时启用/禁用认证"""
    AUTH_CONFIG["enabled"] = enabled


def _is_whitelisted(path: str) -> bool:
    """判断路径是否在白名单中"""
    # 精确匹配
    if path in WHITELIST_PATHS:
        return True
    # 前缀匹配（如 /docs/xxx）
    for prefix in WHITELIST_PATHS:
        if path.startswith(prefix + "/") or path.startswith(prefix + "?"):
            return True
    # /ui 及其子路径
    if path == "/ui" or path.startswith("/ui/") or path.startswith("/ui?"):
        return True
    return False


class AuthMiddleware(BaseHTTPMiddleware):
    """API Key 认证中间件

    检查请求头中的 Authorization: Bearer <token> 或 X-API-Key: <token>
    白名单路径跳过检查
    """

    async def dispatch(self, request: Request, call_next):
        # 未启用认证 → 直接通过
        if not AUTH_CONFIG["enabled"]:
            return await call_next(request)

        path = request.url.path

        # 白名单路径 → 直接通过
        if _is_whitelisted(path):
            return await call_next(request)

        # OPTIONS 预检请求 → 通过
        if request.method == "OPTIONS":
            return await call_next(request)

        # 提取 Token
        token = None
        auth_header = request.headers.get("Authorization", "")
        if auth_header.startswith("Bearer "):
            token = auth_header[7:]
        if not token:
            token = request.headers.get("X-API-Key", "")

        # 验证（使用恒定时序比较防止时序攻击）
        if not token or not hmac.compare_digest(token, AUTH_CONFIG["token"]):
            return JSONResponse(
                status_code=401,
                content={
                    "error": "unauthorized",
                    "message": "缺少有效的 API Key。请在请求头中添加 Authorization: Bearer <your-api-key>",
                    "hint": "如果你是在浏览器中访问 UI，请确保已在设置中配置了 API Key。",
                },
                headers={
                    "WWW-Authenticate": "Bearer realm=\"AI Company OS\"",
                },
            )

        return await call_next(request)
