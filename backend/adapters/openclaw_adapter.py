"""
OpenClaw Adapter — 浏览器/搜索适配器

支持在线程池中运行，避免 asyncio 冲突
"""
import asyncio
import concurrent.futures
from typing import Dict, Any
from .base_adapter import BaseAdapter

# 线程池
_executor = concurrent.futures.ThreadPoolExecutor(max_workers=2)


class OpenClawAdapter(BaseAdapter):
    """OpenClaw 适配器"""

    TOOL_NAME = "openclaw"

    def can_handle(self, task_type: str, task: Dict[str, Any]) -> bool:
        """判断是否能处理此任务"""
        return task_type in {"research", "web_search", "browser"}

    def health_check(self) -> Dict[str, Any]:
        """健康检查"""
        try:
            from agents.openclaw_agent.agent import OpenClawAgent

            # 检测 Playwright
            try:
                import playwright
                playwright_ok = True
            except ImportError:
                playwright_ok = False

            if not playwright_ok:
                return {
                    "available": False,
                    "installed": True,
                    "error": "Playwright 未安装",
                    "fix_hint": "请运行: pip install playwright && playwright install chromium"
                }

            # 尝试在线程池中测试 Playwright
            try:
                test_result = self._test_playwright()
                if not test_result:
                    return {
                        "available": False,
                        "installed": True,
                        "error": "Playwright 浏览器不可用",
                        "fix_hint": "请运行: playwright install chromium"
                    }
            except Exception as e:
                return {
                    "available": False,
                    "installed": True,
                    "error": f"Playwright 测试失败: {str(e)[:50]}",
                    "fix_hint": "请运行: playwright install chromium"
                }

            return {
                "available": True,
                "installed": True,
                "running": True
            }
        except ImportError:
            return {
                "available": False,
                "installed": False,
                "error": "OpenClaw Agent 未找到",
                "fix_hint": "请确保 agents/openclaw_agent 目录存在"
            }
        except Exception as e:
            return {
                "available": False,
                "error": str(e)[:100],
                "fix_hint": "请检查 OpenClaw 安装"
            }

    def _test_playwright(self) -> bool:
        """测试 Playwright 是否可用"""
        try:
            from playwright.sync_api import sync_playwright
            with sync_playwright() as p:
                browser = p.chromium.launch(headless=True)
                browser.close()
            return True
        except Exception:
            return False

    def run(self, task: Dict[str, Any]) -> Dict[str, Any]:
        """执行搜索/浏览器任务"""
        health = self.health_check()
        if not health.get("available"):
            return self._create_result(
                ok=False,
                error=health.get("error", "OpenClaw 不可用"),
                warnings=[health.get("fix_hint", "")]
            )

        goal = task.get("goal", "")
        task_type = task.get("task_type", "web_search")

        # 检查是否在 asyncio 环境中
        try:
            asyncio.get_running_loop()
            # 在 asyncio 环境中，使用线程池
            return self._run_in_thread(task_type, goal)
        except RuntimeError:
            # 不在 asyncio 环境中，直接运行
            return self._run_direct(task_type, goal)

    def _run_in_thread(self, task_type: str, goal: str) -> Dict[str, Any]:
        """在线程池中运行"""
        try:
            future = _executor.submit(self._run_direct, task_type, goal)
            return future.result(timeout=120)
        except concurrent.futures.TimeoutError:
            return self._create_result(ok=False, error="执行超时")
        except Exception as e:
            return self._create_result(ok=False, error=str(e))

    def _run_direct(self, task_type: str, goal: str) -> Dict[str, Any]:
        """直接运行"""
        try:
            from agents.openclaw_agent.agent import OpenClawAgent

            agent = OpenClawAgent()
            result, duration = self._measure_time(
                agent.run,
                {"task_type": task_type, "goal": goal}
            )

            return self._create_result(
                ok=result.get("ok", result.get("success", False)),
                result=result.get("data", {}),
                stdout=result.get("data", {}).get("content", ""),
                duration_ms=duration
            )
        except Exception as e:
            return self._create_result(ok=False, error=str(e))
