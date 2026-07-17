"""
Codex Agent - 代码执行智能体

负责：
1. 在沙箱中执行 Python 代码
2. 创建/修改代码文件
3. 运行测试并收集结果

安全机制：
- 临时工作目录隔离
- 超时限制（默认 30 秒）
- 禁止危险模块和系统调用
- 工作目录外只读
"""
import json
import os
import sys
import shutil
import tempfile
import subprocess
import traceback
import urllib.request
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional

from agents.base_agent import BaseAgent, retry


# ── 沙箱安全前导码（Python 3.8+）──────────────────────────
# 注入到用户代码之前，通过 audit hook 阻断危险系统调用
_SANDBOX_PREAMBLE = r'''
import sys as _sys, os as _os

_SANDBOX_ROOT = _os.environ.get("CODEX_SANDBOX_ROOT", "")

# 保存原始 __import__ 然后替换内置函数
_ORIGINAL_IMPORT = __import__

class _RestrictedBuiltin:
    def __init__(self, name): self._name = name
    def __call__(self, *a, **kw):
        raise RuntimeError("Security: builtins." + self._name + " is disabled in sandbox.")

import builtins as _bi
for _n in ("eval", "exec", "compile", "open", "input", "breakpoint"):
    if hasattr(_bi, _n): setattr(_bi, _n, _RestrictedBuiltin(_n))

# Audit hook
def _sandbox_audit(event, args):
    if event in ("os.system", "os.exec", "os.spawn", "subprocess.Popen"):
        raise RuntimeError("Security: system calls disabled in sandbox")
    if event in ("os.remove", "os.unlink", "os.rmdir"):
        p = str(args[0]) if args else ""
        if _SANDBOX_ROOT and not p.startswith(_SANDBOX_ROOT):
            raise RuntimeError("Security: file ops outside sandbox")
    if event == "shutil.rmtree":
        raise RuntimeError("Security: shutil.rmtree disabled in sandbox")

_sys.addaudithook(_sandbox_audit)

# Safe import filter
def _safe_import(name, *a, **kw):
    root = name.split(".")[0]
    if root in {
        "os","subprocess","shutil","socket","http","urllib","ftplib",
        "telnetlib","smtplib","poplib","imaplib","requests","httpx",
        "aiohttp","urllib3","ctypes","multiprocessing","signal",
        "pdb","code","codeop","tkinter","pygame","curses",
        "pickle","shelve","marshal",
    }:
        raise ImportError("Security: module " + name + " is disabled in sandbox")
    return _ORIGINAL_IMPORT(name, *a, **kw)

_bi.__import__ = _safe_import
'''


class CodexSandbox:
    """代码执行沙箱 — 含真正的安全防护"""

    def __init__(self, timeout: int = 30, max_output_bytes: int = 100_000):
        self.timeout = timeout
        self.max_output_bytes = max_output_bytes
        self.work_dir: Optional[str] = None

    def setup(self, task_id: str) -> str:
        """创建隔离的工作目录"""
        base = Path(tempfile.gettempdir()) / "codex_sandbox"
        base.mkdir(exist_ok=True)
        work_dir = base / f"{task_id}_{uuid.uuid4().hex[:8]}"
        work_dir.mkdir(parents=True, exist_ok=True)
        self.work_dir = str(work_dir)
        return self.work_dir

    def cleanup(self):
        """清理工作目录"""
        if self.work_dir and os.path.exists(self.work_dir):
            try:
                shutil.rmtree(self.work_dir)
            except Exception:
                pass

    def write_file(self, filename: str, content: str) -> str:
        """在沙箱中写入文件"""
        if not self.work_dir:
            raise RuntimeError("沙箱未初始化，请先调用 setup()")
        # 防止路径遍历攻击
        safe_name = os.path.basename(filename.replace("\\", "/"))
        filepath = os.path.join(self.work_dir, safe_name)
        os.makedirs(os.path.dirname(filepath), exist_ok=True)
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(content)
        return filepath

    def _build_safe_env(self) -> dict:
        """构建安全的子进程环境变量 — 排除敏感信息"""
        safe = {}
        for k, v in os.environ.items():
            # 排除所有 API Key 和 Token
            if any(s in k.upper() for s in ("API_KEY", "TOKEN", "SECRET", "PASSWORD", "KEY")):
                continue
            # 排除可能泄露路径信息的
            if k in ("PATH", "SYSTEMROOT", "WINDIR", "TEMP", "TMP", "USERPROFILE",
                     "HOMEDRIVE", "HOMEPATH", "COMPUTERNAME", "USERNAME",
                     "PYTHONPATH", "PYTHONHOME", "VIRTUAL_ENV", "CONDA_PREFIX"):
                safe[k] = v
        safe["CODEX_SANDBOX_ROOT"] = self.work_dir
        safe["HOME"] = self.work_dir
        safe["TEMP"] = self.work_dir
        safe["TMP"] = self.work_dir
        safe["PYTHONIOENCODING"] = "utf-8"
        safe["PYTHONPATH"] = self.work_dir
        return safe

    def execute(self, code: str) -> Dict[str, Any]:
        """在安全沙箱中执行 Python 代码"""
        if not self.work_dir:
            raise RuntimeError("沙箱未初始化，请先调用 setup()")

        # 注入安全前导码
        sandboxed_code = _SANDBOX_PREAMBLE + "\n" + code

        script_path = os.path.join(self.work_dir, "_exec_script.py")
        with open(script_path, "w", encoding="utf-8") as f:
            f.write(sandboxed_code)

        safe_env = self._build_safe_env()

        try:
            result = subprocess.run(
                [sys.executable, "-I", script_path],  # -I = 隔离模式
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=self.timeout,
                cwd=self.work_dir,
                env=safe_env,
            )

            stdout = result.stdout
            stderr = result.stderr

            if len(stdout) > self.max_output_bytes:
                stdout = stdout[:self.max_output_bytes] + "\n...（输出已截断）"
            if len(stderr) > self.max_output_bytes:
                stderr = stderr[:self.max_output_bytes] + "\n...（输出已截断）"

            return {
                "exit_code": result.returncode,
                "stdout": stdout,
                "stderr": stderr,
                "success": result.returncode == 0,
            }
        except subprocess.TimeoutExpired:
            return {"exit_code": -1, "stdout": "", "stderr": f"执行超时（{self.timeout}秒）", "success": False}
        except Exception as e:
            return {"exit_code": -1, "stdout": "", "stderr": f"沙箱执行异常: {str(e)}", "success": False}

    def list_files(self) -> List[str]:
        """列出沙箱中的所有文件"""
        if not self.work_dir:
            return []
        files = []
        for root, _, filenames in os.walk(self.work_dir):
            for fname in filenames:
                full = os.path.join(root, fname)
                rel = os.path.relpath(full, self.work_dir)
                files.append(rel)
        return sorted(files)


class CodexAgent(BaseAgent):
    """Codex Agent - 在沙箱中执行代码任务"""

    AGENT_ID = "codex"
    DISPLAY_NAME = "代码执行"
    CAPABILITIES = ["code", "sandbox", "python"]
    TASK_TYPES = ["code_execute", "code_write_and_run", "code_test", "code_debug", "code_refactor"]

    def __init__(self, timeout: int = 30):
        super().__init__(name="codex", timeout=timeout)
        self.sandbox: Optional[CodexSandbox] = None

    def run(self, task: Dict[str, Any]) -> Dict[str, Any]:
        task_id = task.get("task_id", f"codex_{uuid.uuid4().hex[:8]}")
        task_type = task.get("task_type", "code_execute")
        goal = task.get("goal", "")
        code = task.get("code", "")
        files = task.get("files", {})

        self.sandbox = CodexSandbox(timeout=self.timeout)
        work_dir = self.sandbox.setup(task_id)

        try:
            result = self._dispatch(task_type, task, code, files)
            result["sandbox_path"] = work_dir
            result["files_created"] = self.sandbox.list_files()
            return result
        except Exception as e:
            return self.fail(
                task_id=task_id,
                error=f"执行异常: {e}",
                meta={"stdout": "", "stderr": traceback.format_exc(), "exit_code": -1},
            )
        finally:
            self.sandbox.cleanup()

    def _dispatch(self, task_type: str, task: Dict[str, Any], code: str, files: Dict[str, str]) -> Dict[str, Any]:
        task_id = task.get("task_id", "")
        goal = task.get("goal", "")

        handlers = {
            "code_write_and_run": self._handle_write_and_run,
            "code_execute": self._handle_execute,
            "code_test": self._handle_test,
        }
        handler = handlers.get(task_type, self._handle_smart)
        return handler(task, task_id, goal, code, files)

    def _handle_write_and_run(self, task: Dict, task_id: str, goal: str, code: str, files: Dict[str, str]) -> Dict[str, Any]:
        written_files = []
        for filename, content in files.items():
            path = self.sandbox.write_file(filename, content)
            written_files.append(path)

        exec_result = None
        if code:
            exec_result = self.sandbox.execute(code)
        else:
            py_files = [f for f in self.sandbox.list_files() if f.endswith(".py")]
            if py_files:
                main_file = py_files[0]
                with open(os.path.join(self.sandbox.work_dir, main_file), "r", encoding="utf-8") as f:
                    exec_result = self.sandbox.execute(f.read())

        success = exec_result and exec_result["success"]
        if success:
            return self.ok(task_id, status="执行成功", data={
                "result": exec_result.get("stdout", ""),
                "stdout": exec_result.get("stdout", ""),
                "stderr": exec_result.get("stderr", ""),
                "exit_code": exec_result.get("exit_code", 0),
                "written_files": written_files,
            })
        else:
            return self.fail(task_id, error=exec_result.get("stderr", "执行失败") if exec_result else "无执行结果", meta={
                "stdout": exec_result.get("stdout", "") if exec_result else "",
                "stderr": exec_result.get("stderr", "") if exec_result else "",
                "exit_code": exec_result.get("exit_code", -1) if exec_result else -1,
                "written_files": written_files,
            })

    def _handle_execute(self, task: Dict, task_id: str, goal: str, code: str, files: Dict[str, str]) -> Dict[str, Any]:
        if not code:
            # 有目标无代码：通过 AI 自动生成
            if goal:
                self.logger.info(f"通过 AI 为目标生成代码: {goal[:60]}...")
                generated = self._call_ai_for_code(goal)
                if generated:
                    self.logger.info("AI 代码生成成功，开始执行")
                    exec_result = self.sandbox.execute(generated)
                    success = exec_result["success"]
                    if success:
                        return self.ok(task_id, status="执行成功", data={
                            "result": exec_result["stdout"],
                            "stdout": exec_result["stdout"],
                            "stderr": exec_result["stderr"],
                            "exit_code": exec_result["exit_code"],
                            "ai_generated": True,
                            "generated_code": generated,
                        })
                    else:
                        return self.fail(task_id, error=exec_result.get("stderr", "执行失败"), meta={
                            "stdout": exec_result["stdout"],
                            "stderr": exec_result["stderr"],
                            "exit_code": exec_result["exit_code"],
                            "ai_generated": True,
                            "generated_code": generated,
                        })
            return self.fail(task_id, error="未提供要执行的代码", meta={"exit_code": -1})

        exec_result = self.sandbox.execute(code)
        success = exec_result["success"]
        if success:
            return self.ok(task_id, status="执行成功", data={
                "result": exec_result["stdout"],
                "stdout": exec_result["stdout"],
                "stderr": exec_result["stderr"],
                "exit_code": exec_result["exit_code"],
            })
        else:
            return self.fail(task_id, error=exec_result.get("stderr", "执行失败"), meta={
                "stdout": exec_result["stdout"],
                "stderr": exec_result["stderr"],
                "exit_code": exec_result["exit_code"],
            })

    def _handle_test(self, task: Dict, task_id: str, goal: str, code: str, files: Dict[str, str]) -> Dict[str, Any]:
        exec_result = self.sandbox.execute(code) if code else {"stdout": "", "stderr": "", "exit_code": 0, "success": True}
        test_passed = exec_result["success"] and "FAIL" not in exec_result.get("stderr", "")
        if test_passed:
            return self.ok(task_id, status="测试通过", data={
                "result": exec_result["stdout"],
                "stdout": exec_result["stdout"],
                "stderr": exec_result["stderr"],
                "exit_code": exec_result["exit_code"],
                "test_passed": True,
            })
        else:
            return self.fail(task_id, error=exec_result.get("stderr", "测试失败"), meta={
                "stdout": exec_result["stdout"],
                "stderr": exec_result["stderr"],
                "exit_code": exec_result["exit_code"],
                "test_passed": False,
            })

    @retry(max_attempts=2, backoff=1.0, exceptions=(Exception,))
    def _call_ai_for_code(self, goal: str) -> Optional[str]:
        """使用 AI 根据目标自动生成 Python 代码

        优先走 CC Switch（Anthropic 协议），失败降级直连 DeepSeek（OpenAI 格式）。
        """
        from core.http_client import get_shared_client
        client = get_shared_client()

        api_key = os.getenv("DEEPSEEK_API_KEY", "")
        model = os.getenv("DEEPSEEK_MODEL", "deepseek-chat")

        if not api_key:
            try:
                from backend.config import get_ai_config
                cfg = get_ai_config("deepseek")
                api_key = cfg.get("api_key", "")
            except ImportError:
                pass

        if not api_key:
            return None

        system_prompt = """你是一个 Python 代码生成专家。根据用户的需求，生成完整的 Python 代码。
要求：
1. 只输出代码，不要多余的解释
2. 代码必须是可执行的
3. 使用 print() 输出结果
4. 包含必要的 import
5. 处理可能的异常
6. 代码中变量名用英文
7. 如果用户要求具体文件，用 # === filename.py === 标注
"""

        user_message = f"请生成Python代码：{goal}\n\n只输出代码，不要多余的解释。"

        # === 方案 A: CC Switch（Anthropic 协议）===
        cc_switch_url = os.getenv("CC_SWITCH_URL", "http://127.0.0.1:15721")
        content_text = None
        try:
            resp = client.post(
                f"{cc_switch_url}/v1/messages",
                json={
                    "model": model,
                    "max_tokens": 8192,
                    "system": system_prompt,
                    "messages": [{"role": "user", "content": user_message}],
                },
                headers={
                    "x-api-key": api_key,
                    "anthropic-version": "2023-06-01",
                },
                timeout=60,
            )
            resp.raise_for_status()
            body = resp.json()
            content_blocks = body.get("content", [])
            if isinstance(content_blocks, list):
                for block in content_blocks:
                    if isinstance(block, dict) and block.get("type") == "text":
                        content_text = block.get("text", "")
                        break
        except Exception as e:
            self.logger.warning(f"CC Switch 调用失败: {e}")

        # === 方案 B: 直连 DeepSeek（OpenAI 格式，更可靠）===
        if not content_text:
            try:
                direct_url = "https://api.deepseek.com/chat/completions"
                ds_payload = json.dumps({
                    "model": model,
                    "messages": [
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_message},
                    ],
                    "temperature": 0.3,
                    "max_tokens": 4096,
                }).encode("utf-8")
                req = urllib.request.Request(
                    direct_url,
                    data=ds_payload,
                    headers={
                        "Content-Type": "application/json",
                        "Authorization": f"Bearer {api_key}",
                    },
                )
                with urllib.request.urlopen(req, timeout=30) as resp:
                    body = json.loads(resp.read().decode("utf-8"))
                    content_text = body["choices"][0]["message"]["content"].strip()
            except Exception as e:
                self.logger.warning(f"直连 DeepSeek 也失败: {e}")

        if not content_text:
            return None

        # 提取代码块（如果 AI 用 ``` 包裹）
        if "```python" in content_text:
            code = content_text.split("```python")[1].split("```")[0].strip()
        elif "```" in content_text:
            code = content_text.split("```")[1].split("```")[0].strip()
        else:
            code = content_text

        return code

    def _handle_smart(self, task: Dict, task_id: str, goal: str, code: str, files: Dict[str, str]) -> Dict[str, Any]:
        if code:
            return self._handle_execute(task, task_id, goal, code, files)
        if files:
            return self._handle_write_and_run(task, task_id, goal, code, files)
        if goal and ("print(" in goal or "def " in goal or "import " in goal):
            return self._handle_execute(task, task_id, goal, goal, files)
        # 有目标无代码：由 _handle_execute 自动走 AI 生成
        return self._handle_execute(task, task_id, goal, "", files)
