"""
Agent 通信协议 — 统一消息格式标准

所有 Agent 间通信必须使用 AgentMessage 格式。
这是 AI Company OS 的"TCP/IP"——定义了 Agent 之间如何对话。

协议版本: v1.0
消息类型:
  - request   → 请求执行任务
  - response  → 任务执行结果
  - event     → 状态变更通知
  - query     → 查询其他 Agent 状态
  - delegate  → 委派子任务
  - broadcast → 广播消息给所有 Agent

消息流向:
  Agent A → Bus/Registry → Agent B
  Commander → Agent (编排)
  Agent → Agent (Swarm 点对点)
"""
import json
import time
import uuid
from dataclasses import dataclass, field, asdict
from enum import Enum
from typing import Any, Dict, List, Optional


class MessageType(str, Enum):
    """消息类型"""
    REQUEST = "request"       # 请求执行任务
    RESPONSE = "response"     # 任务执行结果
    EVENT = "event"           # 状态变更通知
    QUERY = "query"           # 查询状态
    DELEGATE = "delegate"     # 委派子任务
    BROADCAST = "broadcast"   # 广播


class MessagePriority(int, Enum):
    """消息优先级"""
    LOW = 0
    NORMAL = 1
    HIGH = 2
    URGENT = 3


class TaskStatus(str, Enum):
    """任务状态（统一定义）"""
    PENDING = "pending"
    QUEUED = "queued"
    RUNNING = "running"
    SUCCESS = "success"
    FAILED = "failed"
    TIMEOUT = "timeout"
    CANCELLED = "cancelled"
    WAITING_INPUT = "waiting_input"
    DELEGATED = "delegated"


@dataclass
class AgentMessage:
    """
    Agent 通信标准消息格式

    所有 Agent 间通信必须使用此格式。
    字段说明:
      - id: 消息唯一 ID (自动生成)
      - type: 消息类型 (request/response/event/query/delegate/broadcast)
      - source: 发送方 Agent ID
      - target: 接收方 Agent ID (broadcast 时为 "*")
      - task_id: 关联的任务 ID (可选)
      - session_id: 关联的会话 ID (可选)
      - payload: 消息内容 (字典)
      - priority: 优先级 (0-3)
      - ttl: 消息存活时间 (秒, 超时自动丢弃)
      - timestamp: 创建时间戳 (自动生成)
      - reply_to: 回复目标消息 ID (用于 request→response 配对)
      - correlation_id: 关联 ID (用于追踪同一事务的所有消息)
      - metadata: 扩展元数据
    """
    type: MessageType
    source: str
    target: str
    payload: Dict[str, Any] = field(default_factory=dict)
    id: str = field(default_factory=lambda: uuid.uuid4().hex[:12])
    task_id: Optional[str] = None
    session_id: Optional[str] = None
    priority: MessagePriority = MessagePriority.NORMAL
    ttl: int = 300  # 默认 5 分钟
    timestamp: float = field(default_factory=time.time)
    reply_to: Optional[str] = None
    correlation_id: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """序列化为字典"""
        d = asdict(self)
        d["type"] = self.type.value
        d["priority"] = self.priority.value
        return d

    def to_json(self) -> str:
        """序列化为 JSON 字符串"""
        return json.dumps(self.to_dict(), ensure_ascii=False)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "AgentMessage":
        """从字典反序列化"""
        data = data.copy()
        data["type"] = MessageType(data.get("type", "request"))
        data["priority"] = MessagePriority(data.get("priority", 1))
        return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})

    @classmethod
    def from_json(cls, json_str: str) -> "AgentMessage":
        """从 JSON 字符串反序列化"""
        return cls.from_dict(json.loads(json_str))

    @property
    def is_expired(self) -> bool:
        """消息是否已过期"""
        return time.time() - self.timestamp > self.ttl

    @property
    def age_ms(self) -> int:
        """消息已存活时间 (毫秒)"""
        return int((time.time() - self.timestamp) * 1000)

    def create_reply(self, source: str, payload: Dict[str, Any],
                     status: TaskStatus = TaskStatus.SUCCESS) -> "AgentMessage":
        """创建回复消息"""
        return AgentMessage(
            type=MessageType.RESPONSE,
            source=source,
            target=self.source,
            payload={**payload, "status": status.value},
            task_id=self.task_id,
            session_id=self.session_id,
            priority=self.priority,
            reply_to=self.id,
            correlation_id=self.correlation_id or self.id,
        )

    def create_delegate(self, source: str, new_target: str,
                        sub_payload: Dict[str, Any]) -> "AgentMessage":
        """创建委派消息（将任务转给其他 Agent）"""
        return AgentMessage(
            type=MessageType.DELEGATE,
            source=source,
            target=new_target,
            payload=sub_payload,
            task_id=self.task_id,
            session_id=self.session_id,
            priority=self.priority,
            correlation_id=self.correlation_id or self.id,
            metadata={"delegated_from": self.source, "original_target": self.target},
        )


# ═══════════════════════════════════════════════════════════════
# 便捷工厂函数
# ═══════════════════════════════════════════════════════════════

def make_request(source: str, target: str, task_type: str, goal: str,
                 task_id: str = None, session_id: str = None,
                 **kwargs) -> AgentMessage:
    """创建任务请求消息"""
    return AgentMessage(
        type=MessageType.REQUEST,
        source=source,
        target=target,
        task_id=task_id or f"task_{uuid.uuid4().hex[:8]}",
        session_id=session_id,
        payload={"task_type": task_type, "goal": goal, **kwargs},
    )


def make_response(source: str, target: str, request: AgentMessage,
                  result: Any = None, error: str = None,
                  status: TaskStatus = None) -> AgentMessage:
    """创建任务响应消息"""
    if status is None:
        status = TaskStatus.FAILED if error else TaskStatus.SUCCESS
    return request.create_reply(
        source=source,
        payload={"result": result, "error": error},
        status=status,
    )


def make_event(source: str, event_type: str, data: Any = None) -> AgentMessage:
    """创建事件通知消息"""
    return AgentMessage(
        type=MessageType.EVENT,
        source=source,
        target="*",
        payload={"event_type": event_type, "data": data},
    )


def make_broadcast(source: str, payload: Dict[str, Any]) -> AgentMessage:
    """创建广播消息"""
    return AgentMessage(
        type=MessageType.BROADCAST,
        source=source,
        target="*",
        payload=payload,
    )


# ═══════════════════════════════════════════════════════════════
# 协议版本管理
# ═══════════════════════════════════════════════════════════════

PROTOCOL_VERSION = "1.0.0"

def get_protocol_info() -> Dict[str, Any]:
    """获取协议信息"""
    return {
        "version": PROTOCOL_VERSION,
        "message_types": [t.value for t in MessageType],
        "task_statuses": [s.value for s in TaskStatus],
        "priority_levels": [p.value for p in MessagePriority],
        "fields": list(AgentMessage.__dataclass_fields__.keys()),
    }
