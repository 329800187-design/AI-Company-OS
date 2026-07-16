"""
Collaboration Plan — 多智能体协同计划数据模型

Core 级多 Agent 协同计划，不使用旧 Boss/Workflow 硬编排。
通过 manifest capabilities 匹配 agent，按步骤顺序执行。

协议版本: v1.0
"""
import uuid
from datetime import datetime, timezone
from typing import List, Optional

from pydantic import BaseModel, Field

from backend.schemas.agent_protocol import AgentRunResult


class CollaborationStep(BaseModel):
    """协同计划单步"""

    id: str = Field(default="", description="步骤唯一标识，如 step_1")
    name: str = Field(..., description="步骤名称")
    task_type: str = Field(..., description="任务类型，传给 AgentTask.task_type")
    required_capability: str = Field(..., description="所需能力标签，匹配 manifest.capabilities")
    input_from: Optional[str] = Field(default=None, description="上游步骤 id，其 output 注入本步 context")
    status: str = Field(default="pending", description="pending|assigned|running|succeeded|failed|unassigned")
    assigned_agent_id: Optional[str] = Field(default=None, description="planner 分配的 agent id")
    result: Optional[AgentRunResult] = Field(default=None, description="executor 执行结果")
    # --- 向后兼容扩展字段 (v1.1) ---
    routing_reason: Optional[str] = Field(default=None, description="capability router 路由原因")
    candidate_agent_ids: List[str] = Field(default_factory=list, description="所有候选 agent id")
    matched_capability: Optional[str] = Field(default=None, description="实际匹配到的能力标签")
    # --- 扩展字段 (v1.2) ---
    depends_on: List[str] = Field(default_factory=list, description="依赖步骤 id 列表")
    expected_output: Optional[str] = Field(default=None, description="预期产出描述")
    review_required: bool = Field(default=False, description="是否需要人工审核")


class CollaborationPlan(BaseModel):
    """协同计划"""

    plan_id: str = Field(default="", description="计划唯一标识")
    goal: str = Field(..., description="目标描述")
    steps: List[CollaborationStep] = Field(default_factory=list, description="执行步骤列表")
    status: str = Field(default="pending", description="pending|running|succeeded|failed")
    created_at: str = Field(default="", description="创建时间 ISO 格式")

    def model_post_init(self, __context) -> None:
        if not self.plan_id:
            object.__setattr__(self, "plan_id", f"cplan_{uuid.uuid4().hex[:12]}")
        if not self.created_at:
            object.__setattr__(self, "created_at", datetime.now(timezone.utc).isoformat())
