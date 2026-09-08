"""Image Agent 路由器 — AI 图片生成与分析"""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from typing import Optional

from backend.services.agent_loader import load_agent_instance

router = APIRouter(prefix="/image", tags=["Image / 图片生成"])


class ImageGenerateRequest(BaseModel):
    prompt: str = Field(..., min_length=1, max_length=4000)
    size: str = "1024x1024"
    style: str = "vivid"
    n: int = 1


class ImageAnalyzeRequest(BaseModel):
    prompt: str = "描述这张图片"
    image_url: str = ""
    image_path: str = ""


def _get_image_agent():
    """延迟加载 Image Agent"""
    agent = load_agent_instance("agents.image_agent.agent", "ImageAgent")
    if agent is None:
        raise HTTPException(status_code=503, detail="Image Agent unavailable")
    return agent


@router.post("/generate", summary="AI 图片生成",
             description="根据文字描述生成图片（使用 DALL-E 3 / OpenAI Images API）")
def generate_image(request: ImageGenerateRequest):
    if not request.prompt.strip():
        raise HTTPException(status_code=400, detail="请提供图片描述")

    # Governance Guard
    from backend.governance.scope_classifier import guard_payload, governance_block_response
    blocked, classification = guard_payload(request.model_dump())
    if blocked:
        return governance_block_response(classification)

    task = {
        "task_id": "img_gen",
        "task_type": "image_generate",
        "prompt": request.prompt,
        "size": request.size,
        "style": request.style,
        "n": request.n,
    }
    return _get_image_agent().run(task)


@router.post("/analyze", summary="图片分析",
             description="分析图片内容（需要 Claude vision 或 GPT-4V）")
def analyze_image(request: ImageAnalyzeRequest):
    if not request.image_url and not request.image_path:
        raise HTTPException(status_code=400, detail="请提供 image_url 或 image_path")

    # Governance Guard
    from backend.governance.scope_classifier import guard_payload, governance_block_response
    blocked, classification = guard_payload(request.model_dump())
    if blocked:
        return governance_block_response(classification)

    task = {
        "task_id": "img_analyze",
        "task_type": "image_analyze",
        "prompt": request.prompt,
        "image_url": request.image_url,
        "image_path": request.image_path,
    }
    return _get_image_agent().run(task)
