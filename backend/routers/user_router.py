"""用户路由器 — 注册/登录/订阅"""
from fastapi import APIRouter, HTTPException, Header, Request
from pydantic import BaseModel, Field, EmailStr
from typing import Optional

from backend.auth.user_system import (
    get_user_manager, BillingManager, SUBSCRIPTION_TIERS
)

router = APIRouter(prefix="/user", tags=["用户 / User"])


class RegisterRequest(BaseModel):
    username: str = Field(..., min_length=2, max_length=50)
    email: str = Field(..., max_length=100)
    password: str = Field(..., min_length=6, max_length=100)


class LoginRequest(BaseModel):
    username: str = Field(..., min_length=1)
    password: str = Field(..., min_length=1)


@router.post("/register", summary="用户注册")
def register(request: RegisterRequest):
    try:
        user = get_user_manager().register(request.username, request.email, request.password)
        return {"status": "ok", "user": user}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/login", summary="用户登录")
def login(request: LoginRequest):
    result = get_user_manager().login(request.username, request.password)
    if not result:
        raise HTTPException(status_code=401, detail="用户名或密码错误")
    return {"status": "ok", **result}


@router.get("/me", summary="获取当前用户信息")
def me(request: Request):
    user = getattr(request.state, "user", None)
    if not user:
        raise HTTPException(status_code=401, detail="未登录")
    if user.get("auth_method") == "api_key":
        return {
            "user_id": user["user_id"],
            "username": user["username"],
            "tier": user["tier"],
            "tenant_id": user["tenant_id"],
            "auth_method": "api_key",
        }
    mgr = get_user_manager()
    u = mgr.get_user(user["user_id"])
    if not u:
        raise HTTPException(status_code=404, detail="用户不存在")
    return {
        "user_id": u["user_id"], "username": u["username"],
        "email": u["email"], "tier": u["tier"],
        "tenant_id": u["tenant_id"],
        "subscription": SUBSCRIPTION_TIERS.get(u["tier"], SUBSCRIPTION_TIERS["free"]),
    }


@router.get("/limits", summary="查询套餐限制")
def check_limits(request: Request):
    user = getattr(request.state, "user", None)
    if not user:
        raise HTTPException(status_code=401, detail="未登录")
    limits = get_user_manager().check_limits(user["user_id"])
    return limits


@router.get("/usage", summary="查询用量统计")
def get_usage(request: Request):
    user = getattr(request.state, "user", None)
    if not user:
        raise HTTPException(status_code=401, detail="未登录")
    usage = BillingManager.get_usage(user["user_id"])
    return {"usage": usage, "count": len(usage)}


@router.get("/tiers", summary="获取所有套餐信息")
def list_tiers():
    return {"tiers": SUBSCRIPTION_TIERS}
