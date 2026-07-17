"""
使用量服务 — 管理用户额度和使用统计
"""
from typing import Dict


class UsageService:
    """使用量服务"""

    def __init__(self):
        # 用户使用量存储（生产环境应该用数据库）
        self._usage: Dict[str, dict] = {}

    def get_usage(self, user_id: str) -> dict:
        """获取用户使用量"""
        if user_id not in self._usage:
            # 初始化默认使用量
            self._usage[user_id] = {
                "user_id": user_id,
                "plan": "trial",
                "total_quota": 50,
                "used": 0,
                "remaining": 50
            }

        return self._usage[user_id]

    def use_quota(self, user_id: str, amount: int = 1) -> bool:
        """使用额度"""
        usage = self.get_usage(user_id)

        if usage["remaining"] < amount:
            return False

        usage["used"] += amount
        usage["remaining"] = usage["total_quota"] - usage["used"]

        return True

    def add_quota(self, user_id: str, amount: int):
        """增加额度"""
        usage = self.get_usage(user_id)
        usage["total_quota"] += amount
        usage["remaining"] = usage["total_quota"] - usage["used"]

    def set_plan(self, user_id: str, plan: str, quota: int):
        """设置套餐"""
        self._usage[user_id] = {
            "user_id": user_id,
            "plan": plan,
            "total_quota": quota,
            "used": 0,
            "remaining": quota
        }
