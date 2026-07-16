"""
Stripe 支付服务 — 订阅管理 + Webhook

配置:
  STRIPE_SECRET_KEY=sk_test_xxx   # Stripe 密钥
  STRIPE_WEBHOOK_SECRET=whsec_xxx # Webhook 签名密钥

套餐映射:
  free → 免费 (无需 Stripe)
  pro → price_pro_monthly (Stripe Price ID)
  enterprise → price_enterprise_monthly
"""
import json
import os
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

try:
    import stripe
    STRIPE_AVAILABLE = True
except ImportError:
    STRIPE_AVAILABLE = False

from backend.auth.user_system import get_user_manager, SUBSCRIPTION_TIERS

# Stripe 配置
STRIPE_KEY = os.getenv("STRIPE_SECRET_KEY", "")
STRIPE_WEBHOOK_SECRET = os.getenv("STRIPE_WEBHOOK_SECRET", "")

# Price ID 映射
PRICE_MAP = {
    "pro": os.getenv("STRIPE_PRICE_PRO", "price_pro_monthly"),
    "enterprise": os.getenv("STRIPE_PRICE_ENTERPRISE", "price_enterprise_monthly"),
}


class PaymentService:
    """Stripe 支付管理"""

    def __init__(self):
        if STRIPE_KEY and STRIPE_AVAILABLE:
            stripe.api_key = STRIPE_KEY
        self._payment_log_path = Path(__file__).parent.parent / "database" / "payments.jsonl"

    @property
    def available(self) -> bool:
        return bool(STRIPE_KEY) and STRIPE_AVAILABLE

    def create_checkout_session(self, user_id: str, tier: str,
                                success_url: str = "", cancel_url: str = "") -> Dict:
        """创建 Stripe Checkout 会话"""
        if not self.available:
            return {"ok": False, "error": "Stripe 未配置。请设置 STRIPE_SECRET_KEY 环境变量"}

        if tier not in ("pro", "enterprise"):
            return {"ok": False, "error": f"无效套餐: {tier}"}

        user = get_user_manager().get_user(user_id)
        if not user:
            return {"ok": False, "error": "用户不存在"}

        price_id = PRICE_MAP.get(tier)
        tier_info = SUBSCRIPTION_TIERS.get(tier, {})

        try:
            session = stripe.checkout.Session.create(
                payment_method_types=["card"],
                mode="subscription",
                customer_email=user.get("email", ""),
                client_reference_id=user_id,
                line_items=[{
                    "price": price_id,
                    "quantity": 1,
                }],
                metadata={
                    "user_id": user_id,
                    "tier": tier,
                },
                success_url=success_url or f"http://localhost:8000/ui?payment=success",
                cancel_url=cancel_url or f"http://localhost:8000/ui?payment=cancelled",
            )
            self._log_payment(user_id, tier, "checkout_created", session.id)
            return {
                "ok": True,
                "checkout_url": session.url,
                "session_id": session.id,
                "tier": tier,
                "price": tier_info.get("price_yuan_month", 0),
            }
        except Exception as e:
            return {"ok": False, "error": str(e)}

    def handle_webhook(self, payload: bytes, signature: str) -> Dict:
        """处理 Stripe Webhook 事件"""
        if not self.available:
            return {"ok": False, "error": "Stripe 未配置"}

        try:
            event = stripe.Webhook.construct_event(
                payload, signature, STRIPE_WEBHOOK_SECRET
            )
        except Exception as e:
            return {"ok": False, "error": f"Webhook 验证失败: {e}"}

        event_type = event["type"]
        data = event["data"]["object"]

        if event_type == "checkout.session.completed":
            user_id = data.get("client_reference_id") or data.get("metadata", {}).get("user_id", "")
            tier = data.get("metadata", {}).get("tier", "pro")
            if user_id:
                get_user_manager().set_tier(user_id, tier)
                self._log_payment(user_id, tier, "subscription_activated", data.get("id", ""))

        elif event_type == "customer.subscription.deleted":
            user_id = data.get("metadata", {}).get("user_id", "")
            if user_id:
                get_user_manager().set_tier(user_id, "free")
                self._log_payment(user_id, "free", "subscription_cancelled", data.get("id", ""))

        return {"ok": True, "event": event_type}

    def get_payment_history(self, user_id: str = "") -> List[Dict]:
        """获取支付历史"""
        if not self._payment_log_path.exists():
            return []
        entries = []
        for line in self._payment_log_path.read_text(encoding="utf-8").splitlines():
            if line.strip():
                try:
                    entry = json.loads(line)
                    if not user_id or entry.get("user_id") == user_id:
                        entries.append(entry)
                except json.JSONDecodeError:
                    continue
        return entries[-100:]  # 最近 100 条

    def _log_payment(self, user_id: str, tier: str, event: str, session_id: str):
        entry = {
            "time": datetime.now().isoformat(),
            "user_id": user_id,
            "tier": tier,
            "event": event,
            "session_id": session_id,
        }
        self._payment_log_path.parent.mkdir(parents=True, exist_ok=True)
        with open(self._payment_log_path, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")


# 全局单例
_payment: Optional[PaymentService] = None


def get_payment_service() -> PaymentService:
    global _payment
    if _payment is None:
        _payment = PaymentService()
    return _payment
