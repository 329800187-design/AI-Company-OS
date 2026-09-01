"""Endpoints for the fixed local browser acceptance checks."""
from fastapi import APIRouter, HTTPException, Query

from backend.security import rate_limiter
from backend.services.browser_verification_service import get_browser_verification_service


router = APIRouter(prefix="/browser-verification", tags=["Browser Verification / 本地浏览器验收"])


@router.post("/runs", summary="运行本地浏览器验收")
def run_browser_verification():
    allowed, message = rate_limiter.check("browser_verification", max_requests=5, window_seconds=60)
    if not allowed:
        raise HTTPException(status_code=429, detail=message)
    return get_browser_verification_service().run()


@router.get("/runs", summary="获取本地浏览器验收审计记录")
def list_browser_verification_runs(limit: int = Query(10, ge=1, le=100)):
    return {"runs": get_browser_verification_service().list_runs(limit=limit)}
