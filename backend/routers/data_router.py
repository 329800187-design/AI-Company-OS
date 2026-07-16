"""Data Agent 路由"""
import os
import uuid
from pathlib import Path
from typing import Any, Dict
from fastapi import APIRouter, HTTPException, UploadFile, File, Form
from pydantic import BaseModel, Field
from backend.services.agent_loader import load_agent_instance
from backend.security import input_validator, file_security

router = APIRouter(prefix="/data", tags=["Data / 数据分析"])

UPLOAD_DIR = Path(__file__).parent.parent.parent / "uploads" / "data"
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

class DataTask(BaseModel):
    task_type: str = "data_explore"
    goal: str = ""
    prompt: str = ""
    message: str = ""
    command: str = ""
    目标: str = ""
    命令: str = ""
    file_path: str = ""
    url: str = ""
    group_by: list = []
    agg_column: str = ""
    chart_type: str = "bar"
    x_column: str = ""
    y_column: str = ""
    title: str = ""
    format: str = "csv"
    fill_missing: str = ""
    drop_columns: list = []

# ── 意图字段：只有这些字段能代表用户目标 ──────────────────────
_DATA_INTENT_KEYS = ("goal", "prompt", "message", "command", "目标", "命令")


def has_data_intent(req: DataTask) -> bool:
    """判断请求是否携带用户意图（goal/prompt/message/command/目标/命令）"""
    return any(getattr(req, k, "").strip() for k in _DATA_INTENT_KEYS)


def _intent_block_response() -> dict:
    """无意图时的统一阻断响应"""
    from backend.governance.classifier import ClassificationResult
    from backend.governance.guard import governance_block_response
    no_intent = ClassificationResult(
        ok=False, confidence=0.0,
        reason="数据操作必须提供明确的分析目标（goal/prompt/message/command），不允许无目标执行",
        needs_clarification=True,
        clarification_questions=["请提供数据分析目标，例如：分析销售趋势、生成月度报表等"],
    )
    return governance_block_response(no_intent)

@router.post("/upload", summary="上传数据文件")
async def upload_data(
    file: UploadFile = File(None),
    goal: str = Form(""),
    prompt: str = Form(""),
):
    """上传 CSV/Excel/JSON 文件并自动分析"""
    # Governance Guard: 检查是否有明确的分析目标
    from backend.governance.guard import guard_payload, governance_block_response

    # 构造 payload 用于 guard 检查
    payload = {"goal": goal, "prompt": prompt}

    # 如果 goal/prompt 都为空，返回 blocked
    if not goal.strip() and not prompt.strip():
        from backend.governance.classifier import ClassificationResult
        no_goal_class = ClassificationResult(
            ok=False, confidence=0.0,
            reason="数据上传必须提供明确的分析目标（goal/prompt），不允许无目标执行",
            needs_clarification=True,
            clarification_questions=["请提供数据分析目标，例如：分析销售趋势、生成月度报表等"],
        )
        return governance_block_response(no_goal_class)

    # 有 goal/prompt 时，调用 guard_payload 进行分类
    blocked, classification = guard_payload(payload)
    if blocked:
        return governance_block_response(classification)

    # 通过 Governance 后，检查文件是否存在
    if file is None:
        raise HTTPException(status_code=400, detail="请提供数据文件")

    # 验证文件名
    is_valid, error_msg = input_validator.validate_filename(file.filename)
    if not is_valid:
        raise HTTPException(status_code=400, detail=error_msg)

    # 验证文件扩展名
    allowed_ext = {'.csv', '.xlsx', '.xls', '.json', '.tsv'}
    is_valid, error_msg = input_validator.validate_file_extension(file.filename, allowed_ext)
    if not is_valid:
        raise HTTPException(status_code=400, detail=error_msg)

    # 读取文件内容
    content = await file.read()

    # 检查文件大小
    is_valid, error_msg = file_security.check_file_size(content.__len__(), max_size=50 * 1024 * 1024)  # 50MB
    if not is_valid:
        raise HTTPException(status_code=400, detail=error_msg)

    # 检查文件内容
    ext = Path(file.filename).suffix.lower()
    is_valid, error_msg = file_security.check_file_content(content, ext)
    if not is_valid:
        raise HTTPException(status_code=400, detail=error_msg)

    # 保存文件（使用随机文件名，防止路径遍历）
    file_id = f"{uuid.uuid4().hex[:8]}{ext}"
    file_path = UPLOAD_DIR / file_id

    with open(file_path, "wb") as f:
        f.write(content)

    # 自动加载并分析
    da = load_agent_instance("agents.data_agent.agent", "DataAgent")
    if da is None:
        raise HTTPException(status_code=503, detail="Data Agent unavailable")
    load_result = da.run({"task_type": "data_load", "file_path": str(file_path)})

    if not load_result.get("ok"):
        return {"status": "error", "message": "文件加载失败", "detail": load_result}

    # 自动探索
    explore_result = da.run({"task_type": "data_explore", "file_path": str(file_path)})

    return {
        "status": "success",
        "file_id": file_id,
        "file_name": file.filename,
        "file_path": str(file_path),
        "load": load_result,
        "explore": explore_result,
    }


@router.post("/load", summary="加载数据")
def load(req: DataTask):
    # Governance Guard: 必须有用户意图
    from backend.governance.guard import guard_payload, governance_block_response
    if not has_data_intent(req):
        return _intent_block_response()
    blocked, classification = guard_payload(req.model_dump())
    if blocked:
        return governance_block_response(classification)

    da = load_agent_instance("agents.data_agent.agent", "DataAgent")
    if da is None:
        raise HTTPException(status_code=503, detail="Data Agent unavailable")
    return da.run({"task_type": "data_load", **req.model_dump(exclude_none=True)})

@router.post("/explore", summary="数据探索")
def explore(req: DataTask):
    from backend.governance.guard import guard_payload, governance_block_response
    if not has_data_intent(req):
        return _intent_block_response()
    blocked, classification = guard_payload(req.model_dump())
    if blocked:
        return governance_block_response(classification)

    agent = load_agent_instance("agents.data_agent.agent", "DataAgent")
    if agent is None:
        raise HTTPException(status_code=503, detail="Data Agent unavailable")
    return agent.run({"task_type": "data_explore", **req.model_dump(exclude_none=True)})

@router.post("/clean", summary="数据清洗")
def clean(req: DataTask):
    from backend.governance.guard import guard_payload, governance_block_response
    if not has_data_intent(req):
        return _intent_block_response()
    blocked, classification = guard_payload(req.model_dump())
    if blocked:
        return governance_block_response(classification)

    agent = load_agent_instance("agents.data_agent.agent", "DataAgent")
    if agent is None:
        raise HTTPException(status_code=503, detail="Data Agent unavailable")
    return agent.run({"task_type": "data_clean", **req.model_dump(exclude_none=True)})

@router.post("/analyze", summary="统计分析")
def analyze(req: DataTask):
    from backend.governance.guard import guard_payload, governance_block_response
    if not has_data_intent(req):
        return _intent_block_response()
    blocked, classification = guard_payload(req.model_dump())
    if blocked:
        return governance_block_response(classification)

    agent = load_agent_instance("agents.data_agent.agent", "DataAgent")
    if agent is None:
        raise HTTPException(status_code=503, detail="Data Agent unavailable")
    return agent.run({"task_type": "data_analyze", **req.model_dump(exclude_none=True)})

@router.post("/viz", summary="可视化图表")
def viz(req: DataTask):
    from backend.governance.guard import guard_payload, governance_block_response
    if not has_data_intent(req):
        return _intent_block_response()
    blocked, classification = guard_payload(req.model_dump())
    if blocked:
        return governance_block_response(classification)

    agent = load_agent_instance("agents.data_agent.agent", "DataAgent")
    if agent is None:
        raise HTTPException(status_code=503, detail="Data Agent unavailable")
    return agent.run({"task_type": "data_viz", **req.model_dump(exclude_none=True)})

@router.post("/export", summary="导出数据")
def export(req: DataTask):
    from backend.governance.guard import guard_payload, governance_block_response
    if not has_data_intent(req):
        return _intent_block_response()
    blocked, classification = guard_payload(req.model_dump())
    if blocked:
        return governance_block_response(classification)

    agent = load_agent_instance("agents.data_agent.agent", "DataAgent")
    if agent is None:
        raise HTTPException(status_code=503, detail="Data Agent unavailable")
    return agent.run({"task_type": "data_export", **req.model_dump(exclude_none=True)})
