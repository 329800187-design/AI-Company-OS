"""支付路由 — Stripe Checkout + Webhook"""
from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field
from typing import Optional

from backend.auth.user_system import get_user_manager, SUBSCRIPTION_TIERS
from backend.services.payment_service import get_payment_service

router = APIRouter(prefix="/payment", tags=["支付 / Payment"])


class SubscribeRequest(BaseModel):
    tier: str = Field(..., description="pro | enterprise")
    success_url: str = ""
    cancel_url: str = ""


class WebhookResponse(BaseModel):
    ok: bool
    event: str = ""


@router.post("/subscribe", summary="创建订阅")
def create_subscription(request: SubscribeRequest, fastapi_request: Request):
    """创建 Stripe Checkout 订阅会话"""
    user = getattr(fastapi_request.state, "user", None)
    if not user:
        raise HTTPException(status_code=401, detail="请先登录")

    payment = get_payment_service()
    result = payment.create_checkout_session(
        user["user_id"], request.tier,
        success_url=request.success_url,
        cancel_url=request.cancel_url,
    )
    if not result["ok"]:
        raise HTTPException(status_code=400, detail=result["error"])
    return result


@router.post("/webhook", summary="Stripe Webhook")
async def stripe_webhook(request: Request):
    """接收 Stripe Webhook 事件"""
    payload = await request.body()
    signature = request.headers.get("stripe-signature", "")
    payment = get_payment_service()
    result = payment.handle_webhook(payload, signature)
    if not result.get("ok"):
        raise HTTPException(status_code=400, detail=result.get("error", "Webhook 验证失败"))
    return result


@router.get("/history", summary="支付历史")
def payment_history(request: Request):
    user = getattr(request.state, "user", None)
    user_id = user["user_id"] if user else ""
    entries = get_payment_service().get_payment_history(user_id)
    return {"payments": entries, "count": len(entries)}


@router.get("/prices", summary="价格列表")
def list_prices():
    """返回所有套餐价格（含 Stripe Price ID）"""
    from backend.services.payment_service import PRICE_MAP, STRIPE_KEY
    tiers = {}
    for tid, info in SUBSCRIPTION_TIERS.items():
        tiers[tid] = {
            "name": info["name"],
            "price_yuan_month": info["price_yuan_month"],
            "features": info["features"],
            "stripe_price_id": PRICE_MAP.get(tid, ""),
            "stripe_configured": bool(STRIPE_KEY),
        }
    return {"tiers": tiers}


@router.get("/status", summary="支付系统状态")
def payment_status():
    payment = get_payment_service()
    from backend.services.payment_service import PRICE_MAP
    return {
        "stripe_available": payment.available,
        "price_ids": dict(PRICE_MAP),
    }
