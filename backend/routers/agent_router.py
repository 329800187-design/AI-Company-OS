"""Agent Router v2 — Pydantic 校验 + 统一信封"""
from typing import Any, Dict, Optional, List
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from agents.ceo_agent.agent import CEOAgent
from agents.codex_agent.agent import CodexAgent
from agents.qa_agent.agent import QAAgent
from agents.system_agent.agent import SystemAgent
from agents.openclaw_agent.agent import OpenClawAgent
from agents.cto_agent.agent import CTOAgent
from agents.image_agent.agent import ImageAgent
from agents.marketing_agent.agent import MarketingAgent
from agents.video_agent.agent import VideoAgent
from agents.data_agent.agent import DataAgent
from backend.security import input_validator, rate_limiter

router = APIRouter(prefix="/agents", tags=["Agents / 智能体"])

# ── Unified Request Models ──────────────────────────

class AgentBaseTask(BaseModel):
    """所有 Agent 通用请求基类"""
    task_type: str = Field(default="", alias="任务类型", description="任务类型")
    goal: str = Field(default="", alias="目标", description="任务目标")
    timeout: int = Field(default=60, alias="超时", description="超时秒数")
    task_id: str = Field(default="", alias="任务ID", description="任务ID")

    model_config = {"populate_by_name": True, "extra": "allow"}

class CodexTask(AgentBaseTask):
    code: str = Field(default="", alias="代码内容", description="Python代码")
    language: str = Field(default="python", alias="语言")
    files: Dict[str, str] = Field(default_factory=dict, alias="文件列表")

class OpenClawTask(AgentBaseTask):
    url: str = Field(default="", alias="目标URL", description="目标网页URL")
    selector: str = Field(default="", alias="选择器")
    extract_type: str = Field(default="text", alias="提取类型")
    full_page: bool = Field(default=False, alias="全页")
    form_data: Dict[str, str] = Field(default_factory=dict, alias="表单数据")
    headless: bool = Field(default=True)

class CTOTask(AgentBaseTask):
    code: str = Field(default="", alias="代码", description="审查的代码")
    language: str = Field(default="", alias="语言")
    context: str = Field(default="", alias="上下文")
    architecture_desc: str = Field(default="", alias="架构描述")

class SystemTask(AgentBaseTask):
    command: str = Field(default="", alias="命令")
    file_path: str = Field(default="", alias="路径")
    file_content: str = Field(default="", alias="内容")
    program: str = Field(default="", alias="程序")
    shell_type: str = Field(default="cmd", alias="shell类型")
    cwd: str = Field(default="", alias="工作目录")

class ImageTask(AgentBaseTask):
    prompt: str = Field(default="", description="图片描述")
    size: str = Field(default="1024x1024")
    style: str = Field(default="vivid")

class MarketingTask(AgentBaseTask):
    prompt: str = Field(default="", description="营销需求描述")
    platform: str = Field(default="")

class DataTask(AgentBaseTask):
    file_path: str = Field(default="", alias="路径")
    url: str = Field(default="")
    chart_type: str = Field(default="bar", alias="图表类型")
    group_by: List[str] = Field(default_factory=list, alias="分组列")
    format: str = Field(default="csv", alias="导出格式")

class QATask(AgentBaseTask):
    result: Any = Field(default="", description="执行结果")
    extracted_data: List[Any] = Field(default_factory=list, alias="提取数据")
    expected_output: Dict = Field(default_factory=dict, alias="期望产出")

class CEOTask(BaseModel):
    goal: str = Field(default="", alias="目标")
    task_type: str = Field(default="goal_decompose", alias="任务类型")
    model_config = {"populate_by_name": True, "extra": "allow"}

class VideoTask(AgentBaseTask):
    prompt: str = Field(default="", description="视频脚本需求")

# ── Endpoints ────────────────────────────────────────

def _check_rate_limit(agent_name: str):
    """检查速率限制"""
    is_allowed, msg = rate_limiter.check(f"agent_{agent_name}", max_requests=30, window_seconds=60)
    if not is_allowed:
        raise HTTPException(status_code=429, detail=msg)

@router.post("/qa/run", summary="QA Agent")
def run_qa_agent(task: QATask):
    _check_rate_limit("qa")
    return QAAgent().run(_to_legacy(task))

@router.post("/ceo/run", summary="CEO Agent")
def run_ceo_agent(task: CEOTask):
    _check_rate_limit("ceo")
    return CEOAgent().run(_to_legacy(task))

@router.post("/codex/run", summary="Codex Agent — 安全沙箱执行Python代码")
def run_codex_agent(task: CodexTask):
    _check_rate_limit("codex")
    return CodexAgent(timeout=task.timeout).run(_to_legacy(task))

@router.post("/openclaw/run", summary="OpenClaw Agent — 浏览器自动化 / 深度研究 / 思考")
def run_openclaw_agent(task: OpenClawTask):
    _check_rate_limit("openclaw")
    return OpenClawAgent(headless=task.headless, timeout=task.timeout).run(_to_legacy(task))

@router.post("/cto/run", summary="CTO Agent — 代码审查/技术选型/架构评审")
def run_cto_agent(task: CTOTask):
    _check_rate_limit("cto")
    return CTOAgent(timeout=task.timeout).run(_to_legacy(task))

@router.post("/system/run", summary="System Agent — 本地系统操作")
def run_system_agent(task: SystemTask):
    _check_rate_limit("system")
    return SystemAgent(timeout=task.timeout).run(_to_legacy(task))

@router.post("/image/run", summary="Image Agent — AI图片生成")
def run_image_agent(task: ImageTask):
    _check_rate_limit("image")
    return ImageAgent(timeout=task.timeout).run(_to_legacy(task))

@router.post("/marketing/run", summary="Marketing Agent — 营销内容生成")
def run_marketing_agent(task: MarketingTask):
    _check_rate_limit("marketing")
    return MarketingAgent(timeout=task.timeout).run(_to_legacy(task))

@router.post("/video/run", summary="Video Agent — 视频创意生成")
def run_video_agent(task: VideoTask):
    _check_rate_limit("video")
    return VideoAgent(timeout=task.timeout).run(_to_legacy(task))

@router.post("/data/run", summary="Data Agent — 数据分析与可视化")
def run_data_agent(task: DataTask):
    _check_rate_limit("data")
    return DataAgent().run(_to_legacy(task))


def _to_legacy(model: BaseModel) -> dict:
    return {**model.model_dump(by_alias=False, exclude_none=True),
            **model.model_dump(by_alias=True, exclude_none=True)}
