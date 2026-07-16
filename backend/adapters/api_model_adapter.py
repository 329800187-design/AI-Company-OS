"""
API Model Adapter — 云端 API 模型适配器

支持 DeepSeek/OpenAI/Claude API
"""
import os
import httpx
from typing import Dict, Any
from .base_adapter import BaseAdapter


class ApiModelAdapter(BaseAdapter):
    """API 模型适配器"""

    TOOL_NAME = "api_models"

    def __init__(self):
        self.provider = os.getenv("AI_PROVIDER", "deepseek")
        self.deepseek_api_key = os.getenv("DEEPSEEK_API_KEY", "")
        self.openai_api_key = os.getenv("OPENAI_API_KEY", "")
        self.claude_api_key = os.getenv("CLAUDE_API_KEY", "")

    def can_handle(self, task_type: str, task: Dict[str, Any]) -> bool:
        """判断是否能处理此任务"""
        # API 模型可以处理大多数任务
        return task_type in {"marketing", "chat", "website", "code", "research", "simple_task"}

    def health_check(self) -> Dict[str, Any]:
        """健康检查"""
        has_key = bool(self.deepseek_api_key or self.openai_api_key or self.claude_api_key)

        if not has_key:
            return {
                "available": False,
                "error": "未配置 API Key",
                "fix_hint": "请在 .env 文件中配置至少一个 API Key"
            }

        return {
            "available": True,
            "provider": self.provider
        }

    def run(self, task: Dict[str, Any]) -> Dict[str, Any]:
        """执行任务"""
        health = self.health_check()
        if not health.get("available"):
            return self._create_result(
                ok=False,
                error=health.get("error", "API 模型不可用"),
                warnings=[health.get("fix_hint", "")]
            )

        prompt = task.get("goal", task.get("prompt", ""))
        task_type = task.get("task_type", "chat")

        if not prompt:
            return self._create_result(ok=False, error="未提供任务内容")

        # 构建系统 prompt
        system = self._get_system_prompt(task_type)

        # 调用 API
        result, duration = self._measure_time(
            self._call_api, prompt, system
        )

        if result.get("ok"):
            return self._create_result(
                ok=True,
                result={"output": result["reply"]},
                stdout=result["reply"],
                duration_ms=duration
            )
        else:
            return self._create_result(
                ok=False,
                error=result.get("error", "API 调用失败"),
                duration_ms=duration
            )

    def _get_system_prompt(self, task_type: str) -> str:
        """获取系统 prompt"""
        prompts = {
            "marketing": "你是一个专业的营销文案专家。请根据用户需求生成高质量的营销文案。要求：吸引人、有感染力、适合目标平台、包含行动号召。",
            "website": "你是一个专业的网页设计师。请根据用户需求生成完整的 HTML 页面。要求：输出完整 HTML 代码、使用现代 CSS、响应式设计。",
            "code": "你是一个专业的程序员。请根据用户需求编写代码。要求：代码规范、有注释、可运行。",
            "research": "你是一个专业的市场研究员。请根据用户需求进行分析。要求：基于事实、提供数据支持、给出可操作建议。",
            "chat": "你是一个友好的 AI 助手，请帮助用户解答问题。",
        }
        return prompts.get(task_type, prompts["chat"])

    def _call_api(self, prompt: str, system: str) -> Dict[str, Any]:
        """调用 API"""
        if self.deepseek_api_key:
            return self._call_deepseek(prompt, system)
        elif self.openai_api_key:
            return self._call_openai(prompt, system)
        elif self.claude_api_key:
            return self._call_claude(prompt, system)
        else:
            return {"ok": False, "error": "未配置 API Key"}

    def _call_deepseek(self, prompt: str, system: str) -> Dict[str, Any]:
        """调用 DeepSeek"""
        try:
            messages = []
            if system:
                messages.append({"role": "system", "content": system})
            messages.append({"role": "user", "content": prompt})

            with httpx.Client(timeout=60) as client:
                response = client.post(
                    f"{os.getenv('DEEPSEEK_BASE_URL', 'https://api.deepseek.com')}/chat/completions",
                    json={
                        "model": os.getenv("DEEPSEEK_MODEL", "deepseek-chat"),
                        "messages": messages,
                        "temperature": 0.7,
                        "max_tokens": 2000
                    },
                    headers={
                        "Authorization": f"Bearer {self.deepseek_api_key}",
                        "Content-Type": "application/json"
                    }
                )

                if response.status_code == 200:
                    data = response.json()
                    return {"ok": True, "reply": data["choices"][0]["message"]["content"]}
                else:
                    return {"ok": False, "error": f"DeepSeek API error: {response.status_code}"}
        except Exception as e:
            return {"ok": False, "error": str(e)}

    def _call_openai(self, prompt: str, system: str) -> Dict[str, Any]:
        """调用 OpenAI"""
        try:
            messages = []
            if system:
                messages.append({"role": "system", "content": system})
            messages.append({"role": "user", "content": prompt})

            with httpx.Client(timeout=60) as client:
                response = client.post(
                    f"{os.getenv('OPENAI_BASE_URL', 'https://api.openai.com/v1')}/chat/completions",
                    json={
                        "model": os.getenv("OPENAI_MODEL", "gpt-4o"),
                        "messages": messages,
                        "temperature": 0.7,
                        "max_tokens": 2000
                    },
                    headers={
                        "Authorization": f"Bearer {self.openai_api_key}",
                        "Content-Type": "application/json"
                    }
                )

                if response.status_code == 200:
                    data = response.json()
                    return {"ok": True, "reply": data["choices"][0]["message"]["content"]}
                else:
                    return {"ok": False, "error": f"OpenAI API error: {response.status_code}"}
        except Exception as e:
            return {"ok": False, "error": str(e)}

    def _call_claude(self, prompt: str, system: str) -> Dict[str, Any]:
        """调用 Claude"""
        try:
            with httpx.Client(timeout=60) as client:
                response = client.post(
                    f"{os.getenv('CLAUDE_BASE_URL', 'https://api.anthropic.com')}/v1/messages",
                    json={
                        "model": os.getenv("CLAUDE_MODEL", "claude-sonnet-4-20250514"),
                        "max_tokens": 2000,
                        "messages": [{"role": "user", "content": prompt}],
                        "system": system or "You are a helpful assistant."
                    },
                    headers={
                        "x-api-key": self.claude_api_key,
                        "anthropic-version": "2023-06-01",
                        "Content-Type": "application/json"
                    }
                )

                if response.status_code == 200:
                    data = response.json()
                    return {"ok": True, "reply": data["content"][0]["text"]}
                else:
                    return {"ok": False, "error": f"Claude API error: {response.status_code}"}
        except Exception as e:
            return {"ok": False, "error": str(e)}
