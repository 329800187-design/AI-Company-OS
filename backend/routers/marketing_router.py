"""Marketing Agent 路由器 — 营销内容生成"""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from typing import Optional

from backend.services.agent_loader import load_agent_instance

router = APIRouter(prefix="/marketing", tags=["Marketing / 营销内容"])


class MarketingRequest(BaseModel):
    prompt: str = Field(..., min_length=1, max_length=10000)
    task_type: str = "copywriting"
    platform: str = ""
    language: str = "zh"


def _get_marketing_agent():
    """延迟加载 Marketing Agent"""
    agent = load_agent_instance("agents.marketing_agent.agent", "MarketingAgent")
    if agent is None:
        raise HTTPException(status_code=503, detail="Marketing Agent unavailable")
    return agent


@router.post("/copywriting", summary="文案生成",
             description="生成产品描述、广告语、Landing Page 等营销文案")
def copywriting(request: MarketingRequest):
    if not request.prompt.strip():
        raise HTTPException(status_code=400, detail="请提供文案需求描述")

    # Governance Guard: 拦截不支持的目标
    from backend.governance.scope_classifier import guard_payload, governance_block_response
    blocked, classification = guard_payload(request.model_dump())
    if blocked:
        return governance_block_response(classification)

    return _get_marketing_agent().run({
        "task_id": "mkt_copy", "task_type": "copywriting",
        "prompt": request.prompt,
    })


@router.post("/social", summary="社交媒体内容",
             description="生成适配各平台的社媒内容（小红书/抖音/Twitter/LinkedIn等）")
def social_media(request: MarketingRequest):
    if not request.prompt.strip():
        raise HTTPException(status_code=400, detail="请提供内容主题")

    # Governance Guard: 拦截不支持的目标
    from backend.governance.scope_classifier import guard_payload, governance_block_response
    blocked, classification = guard_payload(request.model_dump())
    if blocked:
        return governance_block_response(classification)

    return _get_marketing_agent().run({
        "task_id": "mkt_social", "task_type": "social_media",
        "prompt": request.prompt,
    })


@router.post("/seo", summary="SEO 文章生成",
             description="生成 SEO 优化的长文（含 meta、关键词、内链建议）")
def seo_article(request: MarketingRequest):
    if not request.prompt.strip():
        raise HTTPException(status_code=400, detail="请提供文章主题")

    # Governance Guard: 拦截不支持的目标
    from backend.governance.scope_classifier import guard_payload, governance_block_response
    blocked, classification = guard_payload(request.model_dump())
    if blocked:
        return governance_block_response(classification)

    return _get_marketing_agent().run({
        "task_id": "mkt_seo", "task_type": "seo_article",
        "prompt": request.prompt,
    })


@router.post("/email", summary="邮件营销序列",
             description="设计高转化率的邮件营销序列")
def email_campaign(request: MarketingRequest):
    if not request.prompt.strip():
        raise HTTPException(status_code=400, detail="请提供邮件营销需求")

    # Governance Guard: 拦截不支持的目标
    from backend.governance.scope_classifier import guard_payload, governance_block_response
    blocked, classification = guard_payload(request.model_dump())
    if blocked:
        return governance_block_response(classification)

    return _get_marketing_agent().run({
        "task_id": "mkt_email", "task_type": "email_campaign",
        "prompt": request.prompt,
    })


@router.post("/brand-strategy", summary="品牌策略建议",
             description="生成品牌定位、差异化、Slogan 等策略建议")
def brand_strategy(request: MarketingRequest):
    if not request.prompt.strip():
        raise HTTPException(status_code=400, detail="请提供品牌背景")

    # Governance Guard: 拦截不支持的目标
    from backend.governance.scope_classifier import guard_payload, governance_block_response
    blocked, classification = guard_payload(request.model_dump())
    if blocked:
        return governance_block_response(classification)

    return _get_marketing_agent().run({
        "task_id": "mkt_brand", "task_type": "brand_strategy",
        "prompt": request.prompt,
    })


@router.post("/campaign", summary="营销活动策划",
             description="设计完整的营销活动方案（含 KPI、渠道、预算、时间线）")
def campaign_plan(request: MarketingRequest):
    if not request.prompt.strip():
        raise HTTPException(status_code=400, detail="请提供活动目标")

    # Governance Guard: 拦截不支持的目标
    from backend.governance.scope_classifier import guard_payload, governance_block_response
    blocked, classification = guard_payload(request.model_dump())
    if blocked:
        return governance_block_response(classification)

    return _get_marketing_agent().run({
        "task_id": "mkt_campaign", "task_type": "campaign_plan",
        "prompt": request.prompt,
    })
