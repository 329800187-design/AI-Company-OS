"""Feishu/Lark bot callback routes."""
from __future__ import annotations

import json

from fastapi import APIRouter, HTTPException, Request

from backend.services.feishu_bot import feishu_bot_service

router = APIRouter(prefix="/integrations/feishu", tags=["Integrations / Feishu"])


@router.get("/health", summary="飞书机器人状态")
def feishu_health():
    return {
        "status": "ok",
        "enabled": feishu_bot_service.enabled(),
        "callback_url": "/integrations/feishu/events",
    }


@router.api_route("/events", methods=["GET", "POST"], summary="飞书事件回调")
async def feishu_events(request: Request):
    if request.method == "GET":
        return {"status": "ok", "message": "Feishu callback endpoint is ready"}

    body = await request.body()
    if not body:
        raise HTTPException(status_code=400, detail="Empty Feishu callback body")

    try:
        payload = json.loads(body.decode("utf-8"))
    except json.JSONDecodeError as exc:
        raise HTTPException(status_code=400, detail=f"Invalid JSON body: {exc}") from exc

    try:
        return feishu_bot_service.handle_event(payload)
    except ValueError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Feishu callback failed: {exc}") from exc
