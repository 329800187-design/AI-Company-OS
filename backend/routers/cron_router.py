"""定时任务路由"""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from core.cron_scheduler import get_scheduler

router = APIRouter(prefix="/cron", tags=["Cron / 定时任务"])

class CronJobRequest(BaseModel):
    name: str = Field(..., min_length=1)
    cron_expr: str = Field(..., min_length=5, description="5-field cron: min hour dom month dow")
    task_type: str = Field(..., description="ceo|marketing|data_explore|qa|commander")
    task_params: dict = {}

@router.get("/list", summary="列出所有定时任务")
def list_jobs():
    return {"jobs": get_scheduler().list_tasks()}

@router.post("/add", summary="添加定时任务")
def add_job(req: CronJobRequest):
    jid = get_scheduler().add_task(req.name, req.cron_expr, req.task_type, req.task_params)
    return {"job_id": jid, "name": req.name, "next_run": get_scheduler().list_tasks()[0].get("next_run","") if get_scheduler().list_tasks() else ""}

@router.delete("/{job_id}", summary="删除定时任务")
def delete_job(job_id: str):
    get_scheduler().remove_task(job_id)
    return {"status": "deleted"}

@router.get("/logs", summary="执行日志")
def cron_logs(job_id: str = "", limit: int = 50):
    return {"logs": get_scheduler().get_logs(job_id, limit)}
