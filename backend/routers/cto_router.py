"""CTO Agent 路由器 — 技术架构审查与决策"""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from agents.cto_agent.agent import CTOAgent

router = APIRouter(prefix="/cto", tags=["CTO / 技术架构"])


class CodeReviewRequest(BaseModel):
    """代码审查请求"""
    code: str = ""
    language: str = ""
    context: str = ""
    goal: str = ""


class TechChoiceRequest(BaseModel):
    """技术选型请求"""
    goal: str = ""
    constraints: dict = {}
    budget: str = ""


class ArchitectReviewRequest(BaseModel):
    """架构评审请求"""
    goal: str = ""
    architecture_desc: str = ""
    diagram: str = ""


class TaskDecomposeRequest(BaseModel):
    """任务拆解请求"""
    goal: str = ""


class EffortEstimateRequest(BaseModel):
    """工作量评估请求"""
    goal: str = ""


cto = CTOAgent()


@router.post("/review", summary="代码审查",
            description="提交代码，CTO Agent 会从质量、安全、性能、可维护性等维度进行全面审查。")
def code_review(request: CodeReviewRequest):
    """代码审查 — 分析代码质量、安全、性能"""
    if not request.code and not request.goal:
        raise HTTPException(status_code=400, detail="请提供 code 或 goal")
    task = {
        "task_id": "cto_review",
        "task_type": "code_review",
        "goal": request.goal or "代码审查",
        "code": request.code,
        "language": request.language,
        "context": request.context,
    }
    result = cto.run(task)
    if result.get("status") == "失败":
        raise HTTPException(status_code=400, detail=result.get("summary", "审查失败"))
    return result


@router.post("/tech-choice", summary="技术选型建议",
            description="描述你的需求场景，CTO Agent 会推荐合适的技术栈。")
def tech_choice(request: TechChoiceRequest):
    """技术选型建议"""
    if not request.goal:
        raise HTTPException(status_code=400, detail="请提供需求场景描述")
    task = {
        "task_id": "cto_tech_choice",
        "task_type": "tech_choice",
        "goal": request.goal,
        "constraints": request.constraints,
        "budget": request.budget,
    }
    return cto.run(task)


@router.post("/architect", summary="架构评审",
            description="提交架构描述，CTO Agent 会从合理性、扩展性、可靠性等维度评审。")
def architect_review(request: ArchitectReviewRequest):
    """架构评审"""
    if not request.goal and not request.architecture_desc:
        raise HTTPException(status_code=400, detail="请提供架构描述")
    task = {
        "task_id": "cto_architect",
        "task_type": "architecture_review",
        "goal": request.goal or "架构评审",
        "architecture_desc": request.architecture_desc,
        "diagram": request.diagram,
    }
    return cto.run(task)


@router.post("/decompose", summary="技术任务拆解",
            description="把复杂的技术目标拆解为可执行的子任务，含依赖和工时估算。")
def task_decompose(request: TaskDecomposeRequest):
    """技术任务拆解"""
    if not request.goal:
        raise HTTPException(status_code=400, detail="请提供技术目标")
    task = {
        "task_id": "cto_decompose",
        "task_type": "task_decompose",
        "goal": request.goal,
    }
    return cto.run(task)


@router.post("/estimate", summary="工作量评估",
            description="评估开发任务的工作量，含分阶段工时估算和风险提示。")
def effort_estimate(request: EffortEstimateRequest):
    """工作量评估"""
    if not request.goal:
        raise HTTPException(status_code=400, detail="请提供开发任务描述")
    task = {
        "task_id": "cto_estimate",
        "task_type": "effort_estimate",
        "goal": request.goal,
    }
    return cto.run(task)
