"""任务服务 - SQLite 持久化 + 内存双后端"""
import uuid
from typing import Dict, List, Optional, Any
from backend.schemas.task_schema import Task, TaskCreate, TaskStatus
from backend.database.database import TaskDB


class TaskService:
    """任务服务：SQLite 持久化，自动保存和读取"""

    def __init__(self):
        # 内存缓存，加速读操作
        self._cache: Dict[str, Task] = {}

    def _load_from_db(self, task_id: str) -> Optional[Task]:
        row = TaskDB.get(task_id)
        if not row:
            return None
        data = row["data"]
        result = row.get("result")
        return Task(
            task_id=task_id,
            status=TaskStatus(row["status"]),
            result=result,
            score=data.get("score"),
            **data,
        )

    def create_task(self, task_create: TaskCreate) -> Task:
        task_id = f"task_{uuid.uuid4().hex[:8]}"
        data = task_create.model_dump()
        task = Task(
            task_id=task_id,
            **data,
            status=TaskStatus.TODO,
            result=None,
            score=None,
        )
        TaskDB.save(task_id, data)
        self._cache[task_id] = task
        return task

    def list_tasks(self) -> List[Task]:
        if self._cache:
            return list(self._cache.values())
        return []

    def get_task(self, task_id: str) -> Optional[Task]:
        if task_id in self._cache:
            return self._cache[task_id]
        task = self._load_from_db(task_id)
        if task:
            self._cache[task_id] = task
        return task

    def update_task(
        self, task_id: str, status: Optional[TaskStatus] = None,
        result: Optional[Any] = None, score: Optional[int] = None
    ) -> Optional[Task]:
        task = self.get_task(task_id)
        if task is None:
            return None

        if status is not None:
            # 兼容字符串和 TaskStatus 枚举
            if isinstance(status, str):
                task.status = TaskStatus(task.status)
            else:
                task.status = status
            TaskDB.update(task_id, status=str(task.status.value))
        if result is not None:
            task.result = result
            TaskDB.update(task_id, result=result, status=str(task.status.value))
        if score is not None:
            task.score = score

        self._cache[task_id] = task
        return task


task_service = TaskService()
