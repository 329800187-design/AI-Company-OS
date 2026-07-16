"""Responses for deprecated execution routes."""

from typing import Optional

from fastapi.responses import JSONResponse


def deprecated_route_response(
    path: str,
    replacement: Optional[str] = "/governance/run",
    reason: str = "该旧执行入口已停用，请改用受控 Governance 入口。",
) -> JSONResponse:
    """Return a consistent 410 response for disabled legacy execution routes."""
    return JSONResponse(
        status_code=410,
        content={
            "ok": False,
            "deprecated": True,
            "blocked_by_governance": True,
            "path": path,
            "replacement": replacement,
            "reason": reason,
            "message": "该旧入口已废弃，不再允许绕过 Governance 执行。",
        },
    )
