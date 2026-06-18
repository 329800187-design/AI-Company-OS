"""
认证服务 — 管理用户激活和 Token
"""
import os
import uuid
import hashlib
import secrets
from datetime import datetime, timedelta
from typing import Optional, Dict


class AuthService:
    """认证服务"""

    def __init__(self):
        # 激活码存储（生产环境应该用数据库）
        self._activation_codes: Dict[str, dict] = {}
        # 用户 Token 存储
        self._tokens: Dict[str, dict] = {}
        # 用户信息存储
        self._users: Dict[str, dict] = {}

        # 初始化测试激活码
        self._init_test_codes()

    def _init_test_codes(self):
        """初始化测试激活码"""
        test_codes = [
            {"code": "TRIAL-2024-DEMO", "plan": "trial", "quota": 50},
            {"code": "PRO-2024-TEST", "plan": "pro", "quota": 500},
            {"code": "ENTERPRISE-2024", "plan": "enterprise", "quota": 9999},
        ]

        for item in test_codes:
            self._activation_codes[item["code"]] = {
                "plan": item["plan"],
                "quota": item["quota"],
                "used": False,
                "created_at": datetime.now().isoformat()
            }

    def activate(self, activation_code: str) -> dict:
        """使用激活码激活"""

        # 检查激活码是否存在
        if activation_code not in self._activation_codes:
            return {"ok": False, "error": "无效的激活码"}

        code_info = self._activation_codes[activation_code]

        # 检查是否已使用
        if code_info["used"]:
            return {"ok": False, "error": "激活码已被使用"}

        # 创建用户
        user_id = f"user_{uuid.uuid4().hex[:8]}"
        token = secrets.token_urlsafe(32)

        # 保存用户信息
        self._users[user_id] = {
            "user_id": user_id,
            "plan": code_info["plan"],
            "quota": code_info["quota"],
            "used": 0,
            "activated_at": datetime.now().isoformat(),
            "activation_code": activation_code
        }

        # 保存 Token
        self._tokens[token] = {
            "user_id": user_id,
            "created_at": datetime.now().isoformat(),
            "expires_at": (datetime.now() + timedelta(days=30)).isoformat()
        }

        # 标记激活码已使用
        code_info["used"] = True
        code_info["user_id"] = user_id

        return {
            "ok": True,
            "token": token,
            "user_id": user_id,
            "plan": code_info["plan"],
            "remaining_quota": code_info["quota"]
        }

    def validate_token(self, token: str) -> Optional[dict]:
        """验证 Token"""
        if token not in self._tokens:
            return None

        token_info = self._tokens[token]

        # 检查是否过期
        expires_at = datetime.fromisoformat(token_info["expires_at"])
        if datetime.now() > expires_at:
            del self._tokens[token]
            return None

        # 获取用户信息
        user_id = token_info["user_id"]
        if user_id not in self._users:
            return None

        return self._users[user_id]

    def get_user(self, user_id: str) -> Optional[dict]:
        """获取用户信息"""
        return self._users.get(user_id)
