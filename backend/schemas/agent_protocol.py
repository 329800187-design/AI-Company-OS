"""
Agent 执行协议 — 统一任务输入 / 结果输出标准

所有 manifest agent 通过 AgentTask 输入、AgentRunResult 输出。
与 core/agent_protocol.py（AgentMessage，Agent 间通信协议）互补。

协议版本: v1.0
"""
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class AgentTask(BaseModel):
    """统一任务输入 — 任何 agent 的执行请求"""

    task_id: str = Field(default="", alias="任务ID", description="任务唯一标识")
    goal: str = Field(default="", alias="目标", description="任务目标描述")
    task_type: str = Field(default="", alias="任务类型", description="任务类型，如 copywriting / image_generate")
    context: Dict[str, Any] = Field(default_factory=dict, alias="上下文", description="任务上下文（传递给 agent）")
    input: Dict[str, Any] = Field(default_factory=dict, alias="输入", description="任务输入参数（agent 专用字段）")

    model_config = {"populate_by_name": True, "extra": "allow"}


class AgentRunResult(BaseModel):
    """统一执行结果 — 任何 agent 的标准返回"""

    ok: bool = Field(default=False, description="是否执行成功")
    mode: str = Field(default="single_agent", description="执行模式: single_agent | collaboration | deterministic_pipeline | fallback")
    agent_id: str = Field(default="", alias="智能体ID", description="执行的 agent 标识")
    task_type: str = Field(default="", description="任务类型")
    summary: str = Field(default="", description="执行摘要")
    structured_output: Dict[str, Any] = Field(default_factory=dict, alias="结构化产出", description="结构化产出数据")
    output: Dict[str, Any] = Field(default_factory=dict, alias="产出", description="执行产出数据（向后兼容）")
    artifacts: List[str] = Field(default_factory=list, alias="产物", description="产物路径列表")
    warnings: List[str] = Field(default_factory=list, description="警告信息列表")
    errors: List[str] = Field(default_factory=list, description="错误信息列表")
    error: Optional[str] = Field(default=None, alias="错误", description="错误信息（向后兼容，ok=false 时）")
    next_actions: List[str] = Field(default_factory=list, description="建议的下一步操作")
    risk_decision: Optional[Dict[str, Any]] = Field(default=None, description="风险决策信息")
    timeline_events: List[Dict[str, Any]] = Field(default_factory=list, description="时间线事件")
    metadata: Dict[str, Any] = Field(default_factory=dict, alias="元数据", description="执行元数据")

    model_config = {"populate_by_name": True, "extra": "allow"}
