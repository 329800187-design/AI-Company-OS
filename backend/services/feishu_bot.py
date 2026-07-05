"""Feishu/Lark bot bridge service."""
from __future__ import annotations

import json
import logging
import re
import time
from dataclasses import dataclass
from typing import Any, Dict, Optional, Tuple

import httpx

from backend import config

logger = logging.getLogger(__name__)


FEISHU_API_BASE = "https://open.feishu.cn/open-apis"


@dataclass
class TokenCache:
    token: str = ""
    expires_at: float = 0


class FeishuBotService:
    """Receive Feishu message events, call AI Company, and reply in chat."""

    def __init__(self) -> None:
        self._tenant_token = TokenCache()

    def enabled(self) -> bool:
        return bool(config.FEISHU_BOT_ENABLED and config.FEISHU_APP_ID and config.FEISHU_APP_SECRET)

    def handle_event(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        if payload.get("type") == "url_verification" and payload.get("challenge"):
            self._verify_legacy_token(payload.get("token"))
            return {"challenge": payload["challenge"]}

        if "encrypt" in payload:
            return {
                "status": "unsupported",
                "message": "Encrypted Feishu events are not enabled in this MVP. Disable encryption or add decrypt support.",
            }

        header = payload.get("header") or {}
        if header:
            self._verify_legacy_token(header.get("token"))

        event_type = header.get("event_type") or payload.get("type", "")
        if event_type != "im.message.receive_v1":
            return {"status": "ignored", "reason": f"unsupported_event:{event_type}"}

        if not self.enabled():
            return {"status": "disabled", "message": "FEISHU_BOT_ENABLED=false or app credentials missing"}

        event = payload.get("event") or {}
        message = event.get("message") or {}
        sender = event.get("sender") or {}
        chat_type = message.get("chat_type", "")
        message_type = message.get("message_type", "")
        message_id = message.get("message_id", "")

        if message_type != "text":
            self._reply_to_message(message_id, "我目前先支持文字消息。")
            return {"status": "ignored", "reason": f"unsupported_message_type:{message_type}"}

        text = self._extract_text(message)
        should_reply, reason = self._should_reply(message, chat_type)
        if not should_reply:
            return {"status": "ignored", "reason": reason}

        cleaned = self._clean_text(text)
        if not cleaned:
            self._reply_to_message(message_id, "我在，直接把问题发给我就行。")
            return {"status": "ok", "message": "empty_prompt_replied"}

        reply = self._generate_ai_reply(cleaned, sender=sender, chat_type=chat_type)
        self._reply_to_message(message_id, reply)
        return {"status": "ok", "message_id": message_id}

    def _verify_legacy_token(self, token: Optional[str]) -> None:
        expected = config.FEISHU_VERIFICATION_TOKEN
        if expected and not token:
            raise ValueError("Feishu verification token missing but expected")
        if expected and token and token != expected:
            raise ValueError("Feishu verification token mismatch")

    def _should_reply(self, message: Dict[str, Any], chat_type: str) -> Tuple[bool, str]:
        if chat_type == "p2p":
            return True, "p2p"
        if not config.FEISHU_REPLY_ONLY_MENTION:
            return True, "reply_all"
        mentions = message.get("mentions") or []
        if mentions:
            return True, "mentioned"
        text = self._extract_text(message).strip()
        if text.startswith("@"):
            return True, "at_prefix"
        return False, "not_mentioned"

    def _extract_text(self, message: Dict[str, Any]) -> str:
        raw_content = message.get("content") or "{}"
        try:
            content = json.loads(raw_content)
        except json.JSONDecodeError:
            return raw_content
        return str(content.get("text") or "")

    def _clean_text(self, text: str) -> str:
        text = re.sub(r"<at[^>]*>.*?</at>", "", text, flags=re.IGNORECASE)
        text = re.sub(r"^@\S+\s*", "", text.strip())
        return text.strip()

    def _generate_ai_reply(self, prompt: str, sender: Dict[str, Any], chat_type: str) -> str:
        from backend.routers.commander_router import ChatRequest, chat_send

        system_context = (
            "你正在飞书群聊中作为 AI Company OS 智能体参与讨论。"
            "回答要简洁、中文、可执行；如果问题适合创建任务，请说明下一步可以交给 Boss 指挥台。"
        )
        request = ChatRequest(
            message=f"{system_context}\n\n用户消息：{prompt}",
            history=[],
            temperature=0.5,
            max_tokens=1200,
        )
        response = chat_send(request)
        reply = response.reply.strip()
        max_chars = max(200, config.FEISHU_MAX_REPLY_CHARS)
        if len(reply) > max_chars:
            reply = reply[: max_chars - 20].rstrip() + "\n\n…（已截断）"
        return reply

    def _get_tenant_access_token(self) -> str:
        now = time.time()
        if self._tenant_token.token and self._tenant_token.expires_at > now + 60:
            return self._tenant_token.token

        with httpx.Client(timeout=20, proxy=None, trust_env=False) as client:
            response = client.post(
                f"{FEISHU_API_BASE}/auth/v3/tenant_access_token/internal",
                json={"app_id": config.FEISHU_APP_ID, "app_secret": config.FEISHU_APP_SECRET},
            )
            response.raise_for_status()
            data = response.json()

        if data.get("code") != 0:
            raise RuntimeError(f"Failed to get Feishu tenant_access_token: {data.get('msg')}")

        token = data["tenant_access_token"]
        expire = int(data.get("expire", 7200))
        self._tenant_token = TokenCache(token=token, expires_at=now + expire)
        return token

    def _reply_to_message(self, message_id: str, text: str) -> None:
        if not message_id:
            raise ValueError("Feishu message_id is empty")

        token = self._get_tenant_access_token()
        with httpx.Client(timeout=20, proxy=None, trust_env=False) as client:
            response = client.post(
                f"{FEISHU_API_BASE}/im/v1/messages/{message_id}/reply",
                headers={"Authorization": f"Bearer {token}"},
                json={
                    "msg_type": "text",
                    "content": json.dumps({"text": text}, ensure_ascii=False),
                },
            )
            response.raise_for_status()
            data = response.json()

        if data.get("code") != 0:
            raise RuntimeError(f"Failed to reply Feishu message: {data.get('msg')}")


feishu_bot_service = FeishuBotService()
