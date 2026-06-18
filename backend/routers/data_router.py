"""Data Agent 路由"""
import os
import uuid
from pathlib import Path
from typing import Any, Dict
from fastapi import APIRouter, HTTPException, UploadFile, File
from pydantic import BaseModel, Field
from agents.data_agent.agent import DataAgent
from backend.security import input_validator, file_security

router = APIRouter(prefix="/data", tags=["Data / 数据分析"])

UPLOAD_DIR = Path(__file__).parent.parent.parent / "uploads" / "data"
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

class DataTask(BaseModel):
    task_type: str = "data_explore"
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

@router.post("/upload", summary="上传数据文件")
async def upload_data(file: UploadFile = File(...)):
    """上传 CSV/Excel/JSON 文件并自动分析"""
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
    da = DataAgent()
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
    da = DataAgent()
    return da.run({"task_type": "data_load", **req.model_dump(exclude_none=True)})

@router.post("/explore", summary="数据探索")
def explore(req: DataTask):
    return DataAgent().run({"task_type": "data_explore", **req.model_dump(exclude_none=True)})

@router.post("/clean", summary="数据清洗")
def clean(req: DataTask):
    return DataAgent().run({"task_type": "data_clean", **req.model_dump(exclude_none=True)})

@router.post("/analyze", summary="统计分析")
def analyze(req: DataTask):
    return DataAgent().run({"task_type": "data_analyze", **req.model_dump(exclude_none=True)})

@router.post("/viz", summary="可视化图表")
def viz(req: DataTask):
    return DataAgent().run({"task_type": "data_viz", **req.model_dump(exclude_none=True)})

@router.post("/export", summary="导出数据")
def export(req: DataTask):
    return DataAgent().run({"task_type": "data_export", **req.model_dump(exclude_none=True)})
