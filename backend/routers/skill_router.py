"""技能系统 API"""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from core.skills.skill_manager import get_skill_manager

router = APIRouter(prefix="/skills", tags=["技能 / Skills"])


class CreateSkillRequest(BaseModel):
    name: str
    title: str = ""
    description: str = ""
    category: str = "learned"
    capabilities: list = []
    triggers: list = []
    body: str = ""


@router.get("/list", summary="列出所有技能")
def list_skills():
    mgr = get_skill_manager()
    skills = mgr.list_all()
    return {"skills": skills, "count": len(skills)}


@router.get("/match", summary="匹配相关技能")
def match_skills(goal: str = ""):
    if not goal:
        raise HTTPException(400, "goal 参数不能为空")
    mgr = get_skill_manager()
    matched = mgr.match(goal)
    return {"matched": [s.to_dict() for s in matched], "goal": goal}


@router.post("/create", summary="创建新技能（学习）")
def create_skill(req: CreateSkillRequest):
    mgr = get_skill_manager()
    skill = mgr.create(
        name=req.name,
        title=req.title or req.name,
        description=req.description,
        category=req.category,
        capabilities=req.capabilities,
        triggers=req.triggers,
        body=req.body,
    )
    return {"status": "ok", "skill": skill.to_dict()}


@router.get("/context", summary="获取技能上下文")
def get_skill_context(goal: str = ""):
    mgr = get_skill_manager()
    ctx = mgr.get_context_for_goal(goal)
    return {"context": ctx, "goal": goal}
