"""Tier Limits Middleware — enforce subscription-gated capabilities."""
from fastapi import Request
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
from backend.auth.user_system import get_user_manager, SUBSCRIPTION_TIERS

_TIER_ORDER = {"free": 0, "pro": 1, "enterprise": 2}
_FEATURE_REQUIREMENTS = {
    "/boss/graph/": "pro",  # SUBSCRIPTION_TIERS: DAG 工作流属于 Pro 功能。
}
_QUOTA_PATHS = ("/agents/", "/image/", "/marketing/")


def _required_tier(path: str) -> str | None:
    return next(
        (tier for prefix, tier in _FEATURE_REQUIREMENTS.items() if path.startswith(prefix)),
        None,
    )

class TierLimitMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        path = request.url.path
        required_tier = _required_tier(path)
        if not required_tier and not any(path.startswith(prefix) for prefix in _QUOTA_PATHS):
            return await call_next(request)

        user = getattr(request.state, "user", None)
        if not user: return await call_next(request)

        tier = user.get("tier", "free")
        if any(path.startswith(prefix) for prefix in _QUOTA_PATHS):
            check = get_user_manager().check_limits(user["user_id"])
            if not check.get("allowed", True):
                return JSONResponse(status_code=429, content={
                    "ok": False,
                    "error": check.get("reason", "套餐限制"),
                    "tier": tier,
                    "upgrade_url": "/pricing",
                })
        if required_tier and _TIER_ORDER.get(tier, 0) < _TIER_ORDER[required_tier]:
            return JSONResponse(status_code=403, content={
                "ok": False,
                "error": "subscription_required",
                "message": f"此功能需要 {SUBSCRIPTION_TIERS[required_tier]['name']} 或更高套餐",
                "tier": tier,
                "required_tier": required_tier,
            })
        return await call_next(request)
