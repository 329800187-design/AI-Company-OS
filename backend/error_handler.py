"""
Error Handler Module — 统一错误处理

功能：
1. 统一错误响应格式
2. 错误分类和编码
3. 错误日志记录
4. 用户友好的错误消息
"""
from typing import Any, Dict, Optional
from fastapi import HTTPException, Request
from fastapi.responses import JSONResponse
from backend.logger import get_logger

logger = get_logger()


# ── 错误码定义 ──────────────────────────────────────────────

class ErrorCode:
    """错误码定义"""

    # 通用错误 (1xxx)
    UNKNOWN_ERROR = 1000
    INVALID_REQUEST = 1001
    NOT_FOUND = 1002
    METHOD_NOT_ALLOWED = 1003

    # 认证错误 (2xxx)
    UNAUTHORIZED = 2001
    FORBIDDEN = 2002
    TOKEN_EXPIRED = 2003
    TOKEN_INVALID = 2004

    # 参数错误 (3xxx)
    PARAMETER_MISSING = 3001
    PARAMETER_INVALID = 3002
    PARAMETER_TOO_LONG = 3003
    PARAMETER_FORMAT_ERROR = 3004

    # 业务错误 (4xxx)
    AGENT_ERROR = 4001
    TASK_ERROR = 4002
    SESSION_ERROR = 4003
    AI_PROVIDER_ERROR = 4004

    # 系统错误 (5xxx)
    DATABASE_ERROR = 5001
    FILE_SYSTEM_ERROR = 5002
    NETWORK_ERROR = 5003
    INTERNAL_ERROR = 5004

    # 限流错误 (6xxx)
    RATE_LIMIT_EXCEEDED = 6001


# ── 错误消息映射 ──────────────────────────────────────────────

ERROR_MESSAGES = {
    ErrorCode.UNKNOWN_ERROR: "未知错误",
    ErrorCode.INVALID_REQUEST: "无效的请求",
    ErrorCode.NOT_FOUND: "资源不存在",
    ErrorCode.METHOD_NOT_ALLOWED: "请求方法不允许",

    ErrorCode.UNAUTHORIZED: "未授权，请先登录",
    ErrorCode.FORBIDDEN: "权限不足",
    ErrorCode.TOKEN_EXPIRED: "Token已过期，请重新登录",
    ErrorCode.TOKEN_INVALID: "无效的Token",

    ErrorCode.PARAMETER_MISSING: "缺少必要参数",
    ErrorCode.PARAMETER_INVALID: "参数无效",
    ErrorCode.PARAMETER_TOO_LONG: "参数长度超过限制",
    ErrorCode.PARAMETER_FORMAT_ERROR: "参数格式错误",

    ErrorCode.AGENT_ERROR: "Agent执行错误",
    ErrorCode.TASK_ERROR: "任务执行错误",
    ErrorCode.SESSION_ERROR: "会话错误",
    ErrorCode.AI_PROVIDER_ERROR: "AI服务错误",

    ErrorCode.DATABASE_ERROR: "数据库错误",
    ErrorCode.FILE_SYSTEM_ERROR: "文件系统错误",
    ErrorCode.NETWORK_ERROR: "网络错误",
    ErrorCode.INTERNAL_ERROR: "内部错误",

    ErrorCode.RATE_LIMIT_EXCEEDED: "请求过于频繁，请稍后再试",
}


# ── 自定义异常 ──────────────────────────────────────────────

class AppException(Exception):
    """应用异常基类"""

    def __init__(
        self,
        code: int = ErrorCode.UNKNOWN_ERROR,
        message: str = "",
        detail: Any = None,
        status_code: int = 500
    ):
        self.code = code
        self.message = message or ERROR_MESSAGES.get(code, "未知错误")
        self.detail = detail
        self.status_code = status_code
        super().__init__(self.message)


class ValidationException(AppException):
    """验证异常"""

    def __init__(self, message: str = "", detail: Any = None):
        super().__init__(
            code=ErrorCode.PARAMETER_INVALID,
            message=message,
            detail=detail,
            status_code=400
        )


class AuthenticationException(AppException):
    """认证异常"""

    def __init__(self, message: str = "", detail: Any = None):
        super().__init__(
            code=ErrorCode.UNAUTHORIZED,
            message=message,
            detail=detail,
            status_code=401
        )


class AuthorizationException(AppException):
    """授权异常"""

    def __init__(self, message: str = "", detail: Any = None):
        super().__init__(
            code=ErrorCode.FORBIDDEN,
            message=message,
            detail=detail,
            status_code=403
        )


class NotFoundException(AppException):
    """资源不存在异常"""

    def __init__(self, message: str = "", detail: Any = None):
        super().__init__(
            code=ErrorCode.NOT_FOUND,
            message=message,
            detail=detail,
            status_code=404
        )


class RateLimitException(AppException):
    """限流异常"""

    def __init__(self, message: str = "", detail: Any = None):
        super().__init__(
            code=ErrorCode.RATE_LIMIT_EXCEEDED,
            message=message,
            detail=detail,
            status_code=429
        )


class AgentException(AppException):
    """Agent异常"""

    def __init__(self, message: str = "", detail: Any = None):
        super().__init__(
            code=ErrorCode.AGENT_ERROR,
            message=message,
            detail=detail,
            status_code=500
        )


class AIProviderException(AppException):
    """AI Provider异常"""

    def __init__(self, message: str = "", detail: Any = None):
        super().__init__(
            code=ErrorCode.AI_PROVIDER_ERROR,
            message=message,
            detail=detail,
            status_code=502
        )


# ── 错误响应格式 ──────────────────────────────────────────────

def create_error_response(
    code: int,
    message: str,
    detail: Any = None,
    status_code: int = 500
) -> JSONResponse:
    """创建错误响应"""
    response = {
        "ok": False,
        "error": {
            "code": code,
            "message": message,
        }
    }

    if detail:
        response["error"]["detail"] = detail

    return JSONResponse(content=response, status_code=status_code)


# ── 全局异常处理器 ──────────────────────────────────────────────

async def app_exception_handler(request: Request, exc: AppException):
    """应用异常处理器"""
    logger.error(f"AppException | Code: {exc.code} | Message: {exc.message} | Path: {request.url.path}")

    return create_error_response(
        code=exc.code,
        message=exc.message,
        detail=exc.detail,
        status_code=exc.status_code
    )


async def http_exception_handler(request: Request, exc: HTTPException):
    """HTTP异常处理器"""
    logger.warning(f"HTTPException | Status: {exc.status_code} | Detail: {exc.detail} | Path: {request.url.path}")

    return create_error_response(
        code=ErrorCode.INVALID_REQUEST,
        message=str(exc.detail),
        status_code=exc.status_code
    )


async def general_exception_handler(request: Request, exc: Exception):
    """通用异常处理器"""
    logger.exception(f"Unhandled Exception | Type: {type(exc).__name__} | Message: {str(exc)} | Path: {request.url.path}")

    return create_error_response(
        code=ErrorCode.INTERNAL_ERROR,
        message="服务器内部错误，请稍后再试",
        status_code=500
    )


# ── 注册异常处理器 ──────────────────────────────────────────────

def register_error_handlers(app):
    """注册异常处理器"""
    app.add_exception_handler(AppException, app_exception_handler)
    app.add_exception_handler(HTTPException, http_exception_handler)
    app.add_exception_handler(Exception, general_exception_handler)
