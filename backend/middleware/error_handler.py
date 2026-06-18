"""
Global error handling middleware + standardized response envelope.

All unhandled exceptions → JSON {"ok": false, "error": "...", "code": "..."}
All normal responses → pass through unchanged (Agent env already handled per-endpoint)
"""
import traceback
import uuid
from fastapi import Request, Response
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware


class GlobalErrorMiddleware(BaseHTTPMiddleware):
    """Catch-all exception handler → standardized JSON error response"""

    async def dispatch(self, request: Request, call_next):
        try:
            response = await call_next(request)
            return response
        except Exception as exc:
            error_id = uuid.uuid4().hex[:8]
            tb = traceback.format_exc()[-500:]

            status_code = 500
            if hasattr(exc, "status_code"):
                status_code = exc.status_code

            # Log to stderr for ops visibility
            import sys
            print(f"[ERROR {error_id}] {request.method} {request.url.path}: {exc}", file=sys.stderr)

            return JSONResponse(
                status_code=status_code,
                content={
                    "ok": False,
                    "error": str(exc)[:300] or type(exc).__name__,
                    "code": type(exc).__name__,
                    "error_id": error_id,
                },
            )
