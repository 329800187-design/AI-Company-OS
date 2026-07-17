"""
模型客户端 — 统一调用 AI 模型

支持：
- DeepSeek（优先）
- OpenAI
- Claude
"""
import os
import httpx
from typing import Optional


class ModelClient:
    """模型客户端"""

    def __init__(self):
        self.provider = os.getenv("AI_PROVIDER", "deepseek")

        # DeepSeek 配置
        self.deepseek_api_key = os.getenv("DEEPSEEK_API_KEY", "")
        self.deepseek_base_url = os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com")
        self.deepseek_model = os.getenv("DEEPSEEK_MODEL", "deepseek-chat")

        # OpenAI 配置
        self.openai_api_key = os.getenv("OPENAI_API_KEY", "")
        self.openai_base_url = os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1")
        self.openai_model = os.getenv("OPENAI_MODEL", "gpt-4o")

        # Claude 配置
        self.claude_api_key = os.getenv("CLAUDE_API_KEY", "")
        self.claude_base_url = os.getenv("CLAUDE_BASE_URL", "https://api.anthropic.com")
        self.claude_model = os.getenv("CLAUDE_MODEL", "claude-sonnet-4-20250514")

    def chat(self, message: str, system: str = "", temperature: float = 0.7, max_tokens: int = 2000) -> dict:
        """调用 AI 模型"""

        if self.provider == "deepseek" and self.deepseek_api_key:
            return self._call_deepseek(message, system, temperature, max_tokens)
        elif self.provider == "openai" and self.openai_api_key:
            return self._call_openai(message, system, temperature, max_tokens)
        elif self.provider == "claude" and self.claude_api_key:
            return self._call_claude(message, system, temperature, max_tokens)
        else:
            # 尝试按顺序调用
            if self.deepseek_api_key:
                return self._call_deepseek(message, system, temperature, max_tokens)
            elif self.openai_api_key:
                return self._call_openai(message, system, temperature, max_tokens)
            elif self.claude_api_key:
                return self._call_claude(message, system, temperature, max_tokens)
            else:
                return {"ok": False, "error": "未配置 API Key"}

    def _call_deepseek(self, message: str, system: str, temperature: float, max_tokens: int) -> dict:
        """调用 DeepSeek"""
        try:
            messages = []
            if system:
                messages.append({"role": "system", "content": system})
            messages.append({"role": "user", "content": message})

            with httpx.Client(timeout=60) as client:
                response = client.post(
                    f"{self.deepseek_base_url}/chat/completions",
                    json={
                        "model": self.deepseek_model,
                        "messages": messages,
                        "temperature": temperature,
                        "max_tokens": max_tokens
                    },
                    headers={
                        "Authorization": f"Bearer {self.deepseek_api_key}",
                        "Content-Type": "application/json"
                    }
                )

                if response.status_code != 200:
                    return {"ok": False, "error": f"DeepSeek API error: {response.status_code}"}

                data = response.json()
                return {
                    "ok": True,
                    "reply": data["choices"][0]["message"]["content"],
                    "model": self.deepseek_model,
                    "provider": "deepseek"
                }
        except Exception as e:
            return {"ok": False, "error": str(e)}

    def _call_openai(self, message: str, system: str, temperature: float, max_tokens: int) -> dict:
        """调用 OpenAI"""
        try:
            messages = []
            if system:
                messages.append({"role": "system", "content": system})
            messages.append({"role": "user", "content": message})

            with httpx.Client(timeout=60) as client:
                response = client.post(
                    f"{self.openai_base_url}/chat/completions",
                    json={
                        "model": self.openai_model,
                        "messages": messages,
                        "temperature": temperature,
                        "max_tokens": max_tokens
                    },
                    headers={
                        "Authorization": f"Bearer {self.openai_api_key}",
                        "Content-Type": "application/json"
                    }
                )

                if response.status_code != 200:
                    return {"ok": False, "error": f"OpenAI API error: {response.status_code}"}

                data = response.json()
                return {
                    "ok": True,
                    "reply": data["choices"][0]["message"]["content"],
                    "model": self.openai_model,
                    "provider": "openai"
                }
        except Exception as e:
            return {"ok": False, "error": str(e)}

    def _call_claude(self, message: str, system: str, temperature: float, max_tokens: int) -> dict:
        """调用 Claude"""
        try:
            with httpx.Client(timeout=60) as client:
                response = client.post(
                    f"{self.claude_base_url}/v1/messages",
                    json={
                        "model": self.claude_model,
                        "max_tokens": max_tokens,
                        "messages": [{"role": "user", "content": message}],
                        "system": system or "You are a helpful assistant."
                    },
                    headers={
                        "x-api-key": self.claude_api_key,
                        "anthropic-version": "2023-06-01",
                        "Content-Type": "application/json"
                    }
                )

                if response.status_code != 200:
                    return {"ok": False, "error": f"Claude API error: {response.status_code}"}

                data = response.json()
                return {
                    "ok": True,
                    "reply": data["content"][0]["text"],
                    "model": self.claude_model,
                    "provider": "claude"
                }
        except Exception as e:
            return {"ok": False, "error": str(e)}
