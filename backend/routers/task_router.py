"""任务中心路由 - 任务的创建、查询、状态更新"""
from fastapi import APIRouter, HTTPException

from backend.schemas.task_schema import TaskCreate, TaskStatus
from backend.services.task_service import task_service

router = APIRouter(prefix="/tasks", tags=["任务中心 / Tasks"])


@router.post("/", summary="创建任务", description="创建一个新任务并保存到任务中心")
def create_task(task_create: TaskCreate):
    return task_service.create_task(task_create)


@router.get("/", summary="获取所有任务", description="返回任务中心的所有任务列表")
def list_tasks():
    return task_service.list_tasks()


@router.get("/{task_id}", summary="查询单个任务", description="根据任务 ID 查询任务详情")
def get_task(task_id: str):
    task = task_service.get_task(task_id)

    if task is None:
        raise HTTPException(status_code=404, detail="任务不存在")

    return task


@router.patch("/{task_id}/status", summary="更新任务状态", description="更新任务的执行状态")
def update_task_status(task_id: str, status: TaskStatus):
    task = task_service.update_task(task_id, status=status)

    if task is None:
        raise HTTPException(status_code=404, detail="任务不存在")

    return task
