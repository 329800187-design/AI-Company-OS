"""任务数据模型 Schema — 字段英文（代码兼容）+ alias 中文（Swagger 显示）"""
from typing import Any, Dict, Optional
from pydantic import BaseModel, Field, ConfigDict
from enum import Enum


class TaskStatus(str, Enum):
    """任务状态枚举"""
    TODO = "todo"
    DOING = "doing"
    REVIEW = "review"
    DONE = "done"
    FAILED = "failed"
    RETRY = "retry"
    CANCELLED = "cancelled"

    def __str__(self):
        labels = {
            "todo": "待处理",
            "doing": "执行中",
            "review": "验收中",
            "done": "已完成",
            "failed": "失败",
            "retry": "需重试",
            "cancelled": "已取消",
        }
        return labels.get(self.value, self.value)


class TaskCreate(BaseModel):
    """创建新的任务"""
    model_config = ConfigDict(populate_by_name=True)

    project_id: str = Field(default="default_project", alias="项目ID", description="所属项目 ID")
    created_by: str = Field(default="user", alias="创建者", description="任务创建者")
    assigned_to: str = Field(..., alias="分配给", description="分配给哪个核心智能体")
    task_type: str = Field(..., alias="任务类型", description="任务类型：code_execute / browser_screenshot / qa_review 等")
    priority: str = Field(default="normal", alias="优先级", description="优先级：high / normal / low")
    goal: str = Field(..., alias="目标", description="任务目标描述（必填）")
    context: Optional[str] = Field(default="", alias="上下文", description="任务背景信息")
    input: Dict[str, Any] = Field(default_factory=dict, alias="输入参数", description="输入参数")
    expected_output: Dict[str, Any] = Field(default_factory=dict, alias="期望产出", description="期望得到的输出结果")
    constraints: Dict[str, Any] = Field(default_factory=dict, alias="约束条件", description="约束条件，如超时时间、限制等")
    code: Optional[str] = Field(default="", alias="代码内容", description="要执行的 Python 代码（Codex Agent 使用）")
    files: Dict[str, str] = Field(default_factory=dict, alias="文件列表", description="要创建的文件：{文件名: 文件内容}")
    url: Optional[str] = Field(default="", alias="目标URL", description="要访问的网页 URL（OpenClaw Agent 使用）")
    selector: Optional[str] = Field(default="", alias="选择器", description="CSS 选择器（OpenClaw Agent 使用）")


class Task(TaskCreate):
    """完整任务数据"""
    task_id: str = Field(..., alias="任务ID", description="任务唯一标识符")
    status: TaskStatus = Field(default=TaskStatus.TODO, alias="状态", description="当前任务状态")
    result: Optional[Dict[str, Any]] = Field(default=None, alias="执行结果", description="智能体执行后返回的结果")
    score: Optional[int] = Field(default=None, alias="QA评分", description="QA 质量评分（0-100）")
