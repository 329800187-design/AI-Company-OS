"""Swarm 路由 — Multi-Agent 协同"""
from typing import List
from fastapi import APIRouter
from pydantic import BaseModel, Field
from core.agent_swarm import get_swarm

router = APIRouter(prefix="/swarm", tags=["Swarm / 多Agent协同"])

class SwarmStep(BaseModel):
    agent: str
    task_type: str
    goal: str = ""
    prompt: str = ""
    code: str = ""
    url: str = ""

class ChainRequest(BaseModel):
    chain: list = Field(default_factory=list)

class FanoutRequest(BaseModel):
    tasks: list = Field(default_factory=list)

@router.get("/agents", summary="Swarm Agent 列表")
def list_agents():
    return {"agents": get_swarm().get_agents()}

@router.post("/chain", summary="串行链")
def run_chain(req: ChainRequest):
    return get_swarm().execute_chain(req.chain)

@router.post("/fanout", summary="并行分发")
def run_fanout(req: FanoutRequest):
    return get_swarm().execute_fanout(req.tasks)

@router.post("/pipeline", summary="流水线")
def run_pipeline(req: ChainRequest):
    return get_swarm().execute_pipeline(req.chain)
