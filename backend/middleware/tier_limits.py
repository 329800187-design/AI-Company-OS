"""Tier Limits Middleware — enforce subscription limits on agent execution"""
from fastapi import Request
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
from backend.auth.user_system import get_user_manager, SUBSCRIPTION_TIERS

LIMITED_PATHS = ("/agents/", "/image/", "/marketing/")

class TierLimitMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        path = request.url.path
        if not any(path.startswith(p) for p in LIMITED_PATHS):
            return await call_next(request)

        user = getattr(request.state, "user", None)
        if not user: return await call_next(request)

        tier = user.get("tier", "free")
        limits = SUBSCRIPTION_TIERS.get(tier, SUBSCRIPTION_TIERS.get("free", {}))

        # Check daily session limit
        mgr = get_user_manager()
        check = mgr.check_limits(user["user_id"])
        if not check.get("allowed", True):
            return JSONResponse(status_code=429, content={
                "ok": False, "error": check.get("reason", "套餐限制"),
                "tier": tier, "upgrade_url": "/pricing"
            })
        return await call_next(request)
