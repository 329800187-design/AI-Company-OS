"""
Claude Code Adapter — Claude Code 适配器
"""
import subprocess
import shutil
from typing import Dict, Any
from .base_adapter import BaseAdapter


class ClaudeCodeAdapter(BaseAdapter):
    """Claude Code 适配器"""

    TOOL_NAME = "claude_code"

    def can_handle(self, task_type: str, task: Dict[str, Any]) -> bool:
        """判断是否能处理此任务"""
        # Claude Code 适合代码、复杂推理、文件分析
        code_types = {"code", "engineering", "analysis", "complex_reasoning"}
        return task_type in code_types

    def health_check(self) -> Dict[str, Any]:
        """健康检查"""
        claude_path = shutil.which("claude")
        if not claude_path:
            return {
                "available": False,
                "error": "未找到 claude 命令",
                "fix_hint": "请安装 Claude Code: npm install -g @anthropic-ai/claude-code"
            }

        try:
            result = subprocess.run(
                ["claude", "--version"],
                capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=10
            )
            if result.returncode == 0:
                return {
                    "available": True,
                    "version": result.stdout.strip()
                }
            else:
                return {
                    "available": False,
                    "error": "Claude Code 无法执行",
                    "fix_hint": "请检查 Claude Code 安装"
                }
        except Exception as e:
            return {
                "available": False,
                "error": str(e),
                "fix_hint": "请确保 Claude Code 已正确安装"
            }

    def run(self, task: Dict[str, Any]) -> Dict[str, Any]:
        """执行任务"""
        health = self.health_check()
        if not health.get("available"):
            return self._create_result(
                ok=False,
                error=health.get("error", "Claude Code 不可用"),
                warnings=[health.get("fix_hint", "")]
            )

        prompt = task.get("goal", task.get("prompt", ""))
        if not prompt:
            return self._create_result(ok=False, error="未提供任务内容")

        try:
            result, duration = self._measure_time(
                self._run_claude, prompt
            )

            if result["returncode"] == 0:
                return self._create_result(
                    ok=True,
                    result={"output": result["stdout"]},
                    stdout=result["stdout"],
                    duration_ms=duration
                )
            else:
                return self._create_result(
                    ok=False,
                    error=result["stderr"] or "Claude Code 执行失败",
                    stderr=result["stderr"],
                    duration_ms=duration
                )
        except Exception as e:
            return self._create_result(ok=False, error=str(e))

    def _run_claude(self, prompt: str) -> Dict[str, Any]:
        """运行 Claude Code"""
        try:
            result = subprocess.run(
                ["claude", "-p", prompt],
                capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=120
            )
            return {
                "returncode": result.returncode,
                "stdout": result.stdout,
                "stderr": result.stderr
            }
        except subprocess.TimeoutExpired:
            return {
                "returncode": -1,
                "stdout": "",
                "stderr": "执行超时"
            }
