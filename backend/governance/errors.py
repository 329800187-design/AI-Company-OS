"""错误类型定义"""
from typing import Optional


class ClassificationRejected(Exception):
    """目标分类被拒绝"""
    def __init__(self, capability_id: str, reason: str, needs_clarification: bool = False):
        self.capability_id = capability_id
        self.reason = reason
        self.needs_clarification = needs_clarification
        super().__init__(reason)
