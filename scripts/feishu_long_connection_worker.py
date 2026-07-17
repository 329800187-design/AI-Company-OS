"""Run AI Company OS as a Feishu/Lark long-connection bot."""
from __future__ import annotations

import json
import logging
import os
import re
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

try:
    from dotenv import load_dotenv

    load_dotenv(PROJECT_ROOT / ".env")
except Exception:
    pass

from backend import config
from backend.services.feishu_bot import feishu_bot_service

logger = logging.getLogger("feishu-long-connection")
logging.basicConfig(level=os.getenv("LOG_LEVEL", "INFO"))


def _clean_text(text: str) -> str:
    text = re.sub(r"<at[^>]*>.*?</at>", "", text or "", flags=re.IGNORECASE)
    text = re.sub(r"^@\S+\s*", "", text.strip())
    return text.strip()


def _get_attr(obj, *names, default=None):
    for name in names:
        value = getattr(obj, name, None)
        if value is not None:
            return value
    if isinstance(obj, dict):
        for name in names:
            if name in obj:
                return obj[name]
    return default


def _extract_text(content: str) -> str:
    try:
        data = json.loads(content or "{}")
        return str(data.get("text") or "")
    except json.JSONDecodeError:
        return content or ""


def main() -> None:
    try:
        import lark_oapi as lark
        from lark_oapi.api.im.v1 import ReplyMessageRequest, ReplyMessageRequestBody
        from lark_oapi.ws import Client as WsClient
    except ImportError as exc:
        raise RuntimeError("缺少 lark-oapi。请先运行：pip install lark-oapi") from exc

    if not feishu_bot_service.enabled():
        raise RuntimeError("请先在 .env 中设置 FEISHU_BOT_ENABLED=true、FEISHU_APP_ID、FEISHU_APP_SECRET")

    api_client = lark.Client.builder().app_id(config.FEISHU_APP_ID).app_secret(config.FEISHU_APP_SECRET).build()

    def reply_to_message(message_id: str, text: str) -> None:
        request = (
            ReplyMessageRequest.builder()
            .message_id(message_id)
            .request_body(
                ReplyMessageRequestBody.builder()
                .msg_type("text")
                .content(json.dumps({"text": text}, ensure_ascii=False))
                .build()
            )
            .build()
        )
        response = api_client.im.v1.message.reply(request)
        if not response.success():
            raise RuntimeError(f"Feishu reply failed: code={response.code}, msg={response.msg}")

    def on_message(event) -> None:
        try:
            message = _get_attr(event.event, "message", default={})
            sender = _get_attr(event.event, "sender", default={})
            chat_type = _get_attr(message, "chat_type", default="")
            message_id = _get_attr(message, "message_id", default="")
            message_type = _get_attr(message, "message_type", default="")
            content = _get_attr(message, "content", default="")
            mentions = _get_attr(message, "mentions", default=[])

            if message_type != "text":
                return

            text = _extract_text(str(content))
            if config.FEISHU_REPLY_ONLY_MENTION and chat_type != "p2p" and not mentions and not text.strip().startswith("@"):
                return

            prompt = _clean_text(text) or "你好"
            logger.info("Feishu message received message_id=%s text=%s", message_id, prompt[:80])
            try:
                reply = feishu_bot_service._generate_ai_reply(prompt, sender=sender, chat_type=chat_type)
            except Exception as exc:
                logger.exception("Failed to generate AI reply")
                reply = f"我已经接入飞书了，但 AI 模型配置还没准备好：{exc}"
            reply_to_message(message_id, reply)
        except Exception:
            logger.exception("Failed to handle Feishu message event")

    event_handler = (
        lark.EventDispatcherHandler.builder(
            config.FEISHU_ENCRYPT_KEY,
            config.FEISHU_VERIFICATION_TOKEN,
            lark.LogLevel.INFO,
        )
        .register_p2_im_message_receive_v1(on_message)
        .build()
    )

    logger.info("Feishu long-connection bot is starting...")
    WsClient(
        config.FEISHU_APP_ID,
        config.FEISHU_APP_SECRET,
        event_handler=event_handler,
        log_level=lark.LogLevel.INFO,
    ).start()


if __name__ == "__main__":
    main()
