"""
Agent 消息总线 — 多 Agent 异步通信

Agent 可以：
  1. publish(topic, message) — 发布消息到主题
  2. subscribe(topic, callback) — 订阅主题
  3. request(agent, payload) — 同步请求→响应
  4. broadcast(message) — 广播给所有 Agent

Commander 通过 Bus 协调所有 Agent，Agent 之间也可以直接通信。
"""
import json
import threading
import time
import uuid
from collections import defaultdict, deque
from datetime import datetime
from typing import Any, Callable, Dict, List, Optional


class AgentBus:
    """轻量级 Agent 消息总线 — 内存 FIFO"""

    MAX_QUEUE_SIZE = 1000
    MAX_HISTORY = 500

    def __init__(self):
        self._lock = threading.Lock()
        self._topics: Dict[str, deque] = defaultdict(lambda: deque(maxlen=self.MAX_QUEUE_SIZE))
        self._subscribers: Dict[str, List[Callable]] = defaultdict(list)
        self._history: deque = deque(maxlen=self.MAX_HISTORY)
        self._pending_requests: Dict[str, threading.Event] = {}
        self._response_store: Dict[str, Any] = {}
        self._message_count = 0

    # ── 发布/订阅 ──────────────────────────────────

    def publish(self, topic: str, message: Any, sender: str = "unknown"):
        msg = {
            "id": uuid.uuid4().hex[:8],
            "topic": topic,
            "sender": sender,
            "timestamp": datetime.now().isoformat(),
            "payload": message,
        }
        with self._lock:
            self._topics[topic].append(msg)
            self._history.append(msg)
            self._message_count += 1
            subs = list(self._subscribers.get(topic, []))

        for cb in subs:
            try:
                cb(msg)
            except Exception:
                pass

    def subscribe(self, topic: str, callback: Callable):
        with self._lock:
            self._subscribers[topic].append(callback)

    def get_messages(self, topic: str, limit: int = 20) -> List[Dict]:
        with self._lock:
            q = self._topics.get(topic, deque())
            return list(q)[-limit:]

    # ── 请求/响应 ──────────────────────────────────

    def request(self, target_agent: str, payload: Dict, timeout: float = 30) -> Optional[Dict]:
        req_id = uuid.uuid4().hex[:8]
        event = threading.Event()
        with self._lock:
            self._pending_requests[req_id] = event

        self.publish(f"__req__{target_agent}", {
            "request_id": req_id, "payload": payload, "reply_topic": f"__res__{req_id}"
        })

        if event.wait(timeout):
            with self._lock:
                result = self._response_store.pop(req_id, None)
            return result
        return None

    def reply(self, request_id: str, response: Any):
        with self._lock:
            self._response_store[request_id] = response
            event = self._pending_requests.pop(request_id, None)
        if event:
            event.set()

    # ── 广播 ──────────────────────────────────────

    def broadcast(self, message: Any, sender: str = "system"):
        self.publish("__broadcast__", message, sender)

    # ── 统计 ──────────────────────────────────────

    def stats(self) -> Dict:
        with self._lock:
            return {
                "total_messages": self._message_count,
                "active_topics": len(self._topics),
                "subscriber_count": sum(len(v) for v in self._subscribers.values()),
                "history_size": len(self._history),
                "pending_requests": len(self._pending_requests),
            }

    def recent_activity(self, limit: int = 20) -> List[Dict]:
        with self._lock:
            return list(self._history)[-limit:]


# 全局单例
_bus: Optional[AgentBus] = None


def get_agent_bus() -> AgentBus:
    global _bus
    if _bus is None:
        _bus = AgentBus()
    return _bus
