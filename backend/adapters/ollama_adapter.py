"""
Ollama Adapter — Ollama 本地模型适配器
"""
import shutil
import socket
from typing import Dict, Any, List
from .base_adapter import BaseAdapter


class OllamaAdapter(BaseAdapter):
    """Ollama 适配器"""

    TOOL_NAME = "ollama"

    def can_handle(self, task_type: str, task: Dict[str, Any]) -> bool:
        """判断是否能处理此任务"""
        # Ollama 可以处理聊天和简单任务
        return task_type in {"chat", "marketing", "simple_task"}

    def health_check(self) -> Dict[str, Any]:
        """健康检查"""
        ollama_path = shutil.which("ollama")
        if not ollama_path:
            return {
                "available": False,
                "installed": False,
                "error": "未找到 ollama 命令",
                "fix_hint": "请安装 Ollama: https://ollama.ai"
            }

        running = self._check_port()
        models = self._get_models() if running else []

        return {
            "available": running,
            "installed": True,
            "running": running,
            "models": models,
            "model_count": len(models),
            "error": "" if running else "Ollama 未启动",
            "fix_hint": "" if running else "请启动 Ollama: ollama serve"
        }

    def run(self, task: Dict[str, Any]) -> Dict[str, Any]:
        """执行任务"""
        health = self.health_check()
        if not health.get("available"):
            return self._create_result(
                ok=False,
                error=health.get("error", "Ollama 不可用"),
                warnings=[health.get("fix_hint", "")]
            )

        prompt = task.get("goal", task.get("prompt", ""))
        if not prompt:
            return self._create_result(ok=False, error="未提供任务内容")

        try:
            import httpx
            result, duration = self._measure_time(
                self._call_ollama, prompt
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
                    error=result.get("error", "Ollama 调用失败"),
                    duration_ms=duration
                )
        except Exception as e:
            return self._create_result(ok=False, error=str(e))

    def _call_ollama(self, prompt: str) -> Dict[str, Any]:
        """调用 Ollama"""
        try:
            import httpx
            with httpx.Client(timeout=60) as client:
                response = client.post(
                    "http://localhost:11434/api/generate",
                    json={
                        "model": self._get_default_model(),
                        "prompt": prompt,
                        "stream": False
                    }
                )

                if response.status_code == 200:
                    data = response.json()
                    return {
                        "ok": True,
                        "reply": data.get("response", "")
                    }
                else:
                    return {
                        "ok": False,
                        "error": f"Ollama API error: {response.status_code}"
                    }
        except Exception as e:
            return {"ok": False, "error": str(e)}

    def _get_models(self) -> List[str]:
        """获取可用模型列表"""
        try:
            import httpx
            with httpx.Client(timeout=5) as client:
                response = client.get("http://localhost:11434/api/tags")
                if response.status_code == 200:
                    data = response.json()
                    return [m["name"] for m in data.get("models", [])]
        except:
            pass
        return []

    def _get_default_model(self) -> str:
        """获取默认模型"""
        models = self._get_models()
        if models:
            # 优先使用 llama 系列
            for m in models:
                if "llama" in m.lower():
                    return m
            return models[0]
        return "llama2"

    def _check_port(self) -> bool:
        """检查端口是否在线"""
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(2)
            result = sock.connect_ex(("localhost", 11434))
            sock.close()
            return result == 0
        except:
            return False
