"""
Cloud Client — 本地连接云端服务

功能：
1. 调用云端 Agent 流水线
2. 处理云端响应
3. 本地 fallback
"""
import os
import httpx
from typing import Optional, Dict
from backend.logger import get_logger

logger = get_logger()


class CloudClient:
    """云端客户端"""

    def __init__(self):
        self.enabled = os.getenv("CLOUD_MODE", "false").lower() == "true"
        self.api_base = os.getenv("CLOUD_API_BASE", "http://localhost:8001")
        self.auth_token = os.getenv("CLOUD_AUTH_TOKEN", "")
        self.allow_fallback = os.getenv("ALLOW_LOCAL_FALLBACK", "true").lower() == "true"

    def is_available(self) -> bool:
        """检查云端是否可用"""
        if not self.enabled:
            return False

        try:
            with httpx.Client(timeout=5) as client:
                response = client.get(f"{self.api_base}/health")
                return response.status_code == 200
        except:
            return False

    def execute_task(self, message: str, context: dict = None) -> dict:
        """执行云端任务"""
        if not self.enabled or not self.auth_token:
            return {"ok": False, "error": "云端未配置"}

        try:
            with httpx.Client(timeout=120) as client:
                response = client.post(
                    f"{self.api_base}/pipeline/execute",
                    json={"message": message, "context": context or {}},
                    headers={"Authorization": f"Bearer {self.auth_token}"}
                )

                if response.status_code == 200:
                    return response.json()
                else:
                    return {
                        "ok": False,
                        "error": f"云端返回错误: {response.status_code}",
                        "detail": response.text
                    }
        except Exception as e:
            logger.error(f"CloudClient error: {e}")
            return {"ok": False, "error": str(e)}

    def get_usage(self) -> dict:
        """获取使用量"""
        if not self.enabled or not self.auth_token:
            return {"ok": False, "error": "云端未配置"}

        try:
            with httpx.Client(timeout=10) as client:
                response = client.get(
                    f"{self.api_base}/usage",
                    headers={"Authorization": f"Bearer {self.auth_token}"}
                )

                if response.status_code == 200:
                    return response.json()
                else:
                    return {"ok": False, "error": f"获取使用量失败: {response.status_code}"}
        except Exception as e:
            return {"ok": False, "error": str(e)}


# 全局实例
_cloud_client = None


def get_cloud_client() -> CloudClient:
    """获取云端客户端单例"""
    global _cloud_client
    if _cloud_client is None:
        _cloud_client = CloudClient()
    return _cloud_client
