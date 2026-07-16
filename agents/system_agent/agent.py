"""
System Agent — 本地系统操控 + 本地 AI 推理
============================================
能力：
  1. 执行命令行程序（cmd / powershell / bash）
  2. 启动本地 GUI 程序
  3. 读写文件系统
  4. 本地 AI 推理（llama.cpp / Ollama / LM Studio / 任意兼容 OpenAI 接口的本地服务）
  5. 进程管理
  6. 执行后自动揭示产出文件路径

安全护栏：
  - 危险命令警告（format / del / rd / rm -rf / shutdown）
  - 超时限制（默认 120s，可配置）
  - 输出截断（最长 50KB）
  - 命令日志记录
"""
import json
import os
import re
import shlex
import shutil
import subprocess
import sys
import tempfile
import time
import traceback
import uuid
from typing import Any, Dict, List, Optional
from pathlib import Path
from datetime import datetime

# ═══════════════════════════════════════════════════════════════
# 本地 AI 检测
# ═══════════════════════════════════════════════════════════════

def _detect_local_ai() -> Dict[str, Any]:
    """检测本机可用的 AI 推理能力"""
    info: Dict[str, Any] = {
        "ollama_available": False,
        "ollama_models": [],
        "llama_cpp_available": False,
        "transformers_available": False,
        "local_openai_endpoints": [],
    }

    # Ollama CLI
    try:
        result = subprocess.run(["ollama", "list"], capture_output=True, text=True, timeout=5)
        if result.returncode == 0:
            info["ollama_available"] = True
            for line in result.stdout.strip().split("\n")[1:]:
                name = line.split()[0] if line.split() else ""
                if name:
                    info["ollama_models"].append(name)
    except Exception:
        pass

    # llama-cpp-python
    try:
        import llama_cpp  # noqa: F401
        info["llama_cpp_available"] = True
    except ImportError:
        pass

    # transformers
    try:
        import transformers  # noqa: F401
        info["transformers_available"] = True
    except ImportError:
        pass

    # 扫描常见本地推理端口
    for port_name, port in [("LM Studio", 1234), ("Ollama API", 11434),
                              ("LocalAI", 8080), ("text-generation-webui", 5000),
                              ("vLLM", 8000)]:
        try:
            import httpx
            r = httpx.get(f"http://127.0.0.1:{port}/v1/models", timeout=2)
            if r.status_code == 200:
                info["local_openai_endpoints"].append({"name": port_name, "port": port, "url": f"http://127.0.0.1:{port}/v1"})
        except Exception:
            pass

    return info


# 危险命令列表（含 Windows LOLBin 和 Unix 危险命令）
DANGEROUS_COMMANDS = [
    # Windows 高危命令
    "format ", "del /f", "del /q", "rd /s", "rmdir /s",
    "diskpart", "reg delete", "reg add",
    "shutdown /s", "shutdown /r", "shutdown -h", "shutdown -r",
    # Windows LOLBin (Living Off the Land Binaries)
    "certutil -urlcache", "certutil -decode", "certutil -encode",
    "bitsadmin /transfer", "bitsadmin /create",
    "regsvr32 /s /u", "regsvr32 /u /s",
    "mshta ", "cscript ", "wscript ",
    "rundll32 ", "msiexec /q", "cmd /c del", "cmd /c rd",
    "powershell -EncodedCommand", "powershell -e ",
    "powershell -enc ", "powershell -window hidden",
    "powershell -w hidden", "powershell -nop -w hidden",
    "Invoke-Expression", "Invoke-WebRequest -OutFile",
    "Start-Process -WindowStyle Hidden",
    "wmic process call create", "wmic os get",
    "schtasks /create", "schtasks /delete",
    # Unix 高危命令
    "rm -rf", "rm -r ", "dd if=", "mkfs.", ":(){ :|:& };:",
    "chmod 777 /", "chmod -R 777",
    "> /dev/sda", "/dev/null",  # 磁盘写入
    "mkfs.ext", "fdisk ", "wipefs ",
    # 中文高危关键词
    "格式化", "格式化磁盘", "删除系统", "删系统", "关机 /s", "关机 /r",
    "格式化 c:", "格式化 d:", "清空磁盘",
]


from agents.base_agent import BaseAgent


class SystemAgent(BaseAgent):
    """System Agent — 本地系统完全控制"""

    AGENT_ID = "system"
    DISPLAY_NAME = "系统操作"
    CAPABILITIES = ["shell", "file", "process", "system"]
    TASK_TYPES = ["shell_execute", "shell_cmd", "system_run", "run_program",
                  "file_write", "file_read", "file_list", "file_search", "file_delete",
                  "local_ai", "local_ai_list", "process_list", "process_kill"]

    def __init__(self, timeout: int = 120, output_dir: Optional[str] = None,
                 allow_dangerous: bool = False):
        super().__init__(name="system", timeout=timeout)
        self.allow_dangerous = allow_dangerous
        self.output_dir = output_dir or os.path.join(
            os.path.dirname(__file__), "..", "..", "output", "system_agent"
        )
        os.makedirs(self.output_dir, exist_ok=True)
        self._last_outputs: List[str] = []

    # ═══════════════════════════════════════════════════════════
    # 主入口
    # ═══════════════════════════════════════════════════════════

    def run(self, task: Dict[str, Any]) -> Dict[str, Any]:
        task_id = task.get("task_id", f"system_{uuid.uuid4().hex[:8]}")
        task_type = task.get("task_type", "shell_execute")
        goal = task.get("goal", "")

        self._last_outputs = []

        try:
            result = self._dispatch(task_type, task, task_id, goal)
            result["task_id"] = task_id
            result["agent"] = "system"
            result["agent_name"] = "System 系统操作"
            result["title"] = goal
            # 附加产出文件清单
            if self._last_outputs:
                result["output_files"] = self._last_outputs
                result["output_dir"] = self.output_dir
            return result
        except Exception as e:
            return self.fail(
                task_id=task_id,
                error=f"系统操作异常: {e}",
                status="执行异常",
                meta={"stderr": traceback.format_exc(), "output_files": self._last_outputs},
            )

    def _dispatch(self, task_type: str, task: Dict, task_id: str, goal: str) -> Dict:
        handlers = {
            "shell_execute": self._handle_shell,
            "shell_cmd": self._handle_shell,
            "system_run": self._handle_shell,
            "run_program": self._handle_run_program,
            "file_write": self._handle_file_write,
            "file_read": self._handle_file_read,
            "file_list": self._handle_file_list,
            "file_search": self._handle_file_search,
            "file_delete": self._handle_file_delete,
            "local_ai": self._handle_local_ai,
            "local_ai_list": self._handle_local_ai_list,
            "process_list": self._handle_process_list,
            "process_kill": self._handle_process_kill,
        }
        handler = handlers.get(task_type, self._handle_smart)
        return handler(task, task_id, goal)

    def _handle_smart(self, task: Dict, task_id: str, goal: str) -> Dict:
        """智能推断任务类型"""
        command = task.get("command", task.get("cmd", task.get("shell", "")))
        if command:
            return self._handle_shell(task, task_id, goal)

        program = task.get("program", task.get("exe", task.get("app", "")))
        if program:
            return self._handle_run_program(task, task_id, goal)

        file_content = task.get("file_content", task.get("content", ""))
        file_path = task.get("file_path", task.get("path", task.get("file", "")))
        if file_content and file_path:
            return self._handle_file_write(task, task_id, goal)
        if file_path and task.get("action") == "read":
            return self._handle_file_read(task, task_id, goal)

        ai_task = task.get("ai_prompt", task.get("local_ai_prompt", ""))
        if ai_task:
            return self._handle_local_ai(task, task_id, goal)

        return {
            "agent": "system", "status": "跳过",
            "result": "无法识别任务类型。请提供 command / program / file_path / ai_prompt 字段",
            "success": False,
        }

    # ═══════════════════════════════════════════════════════════
    # 1. Shell / 命令行执行
    # ═══════════════════════════════════════════════════════════

    def _handle_shell(self, task: Dict, task_id: str, goal: str) -> Dict:
        command = task.get("command", task.get("cmd", task.get("shell", "")))
        if not command:
            return {"agent": "system", "status": "失败", "result": "未提供命令", "success": False}

        shell_type = task.get("shell_type", "auto")
        cwd = task.get("cwd", task.get("working_dir", os.getcwd()))

        # 安全检测
        is_dangerous = any(d in command.lower() for d in DANGEROUS_COMMANDS)
        if is_dangerous and not self.allow_dangerous:
            return {
                "agent": "system", "status": "被拦截",
                "result": f"⚠️ 危险命令已拦截: {command[:80]}\n如需执行，设置 allow_dangerous=true",
                "success": False,
            }

        # 选择 shell
        if shell_type == "auto":
            if sys.platform == "win32":
                shell = "cmd"
            else:
                shell = "bash"
        else:
            shell = shell_type

        shell_map = {
            "cmd": {"executable": "cmd.exe", "args": ["/c", command]},
            "powershell": {"executable": "powershell.exe", "args": ["-Command", command]},
            "pwsh": {"executable": "pwsh.exe", "args": ["-Command", command]},
            "bash": {"executable": "bash", "args": ["-c", command]},
        }
        cfg = shell_map.get(shell, shell_map["cmd"])
        executable = shutil.which(cfg["executable"])
        if not executable:
            executable = cfg["executable"]

        try:
            result = subprocess.run(
                [executable] + cfg["args"],
                capture_output=True, text=True, timeout=self.timeout,
                cwd=cwd, shell=False,
            )
            stdout = result.stdout
            stderr = result.stderr
            if len(stdout) > 50_000:
                stdout = stdout[:50_000] + "\n...（输出已截断）"
            if len(stderr) > 50_000:
                stderr = stderr[:50_000] + "\n...（输出已截断）"

            success = result.returncode == 0
            return {
                "agent": "system", "agent_name": "System 系统操作",
                "status": "执行成功" if success else "执行失败",
                "result": stdout[:3000] or "(无输出)",
                "stdout": stdout, "stderr": stderr,
                "exit_code": result.returncode,
                "command": command, "cwd": cwd,
                "success": success,
            }
        except subprocess.TimeoutExpired:
            return {
                "agent": "system", "status": "超时",
                "result": f"命令执行超时（{self.timeout}秒）: {command[:100]}",
                "success": False,
            }

    # ═══════════════════════════════════════════════════════════
    # 2. 启动本地程序
    # ═══════════════════════════════════════════════════════════

    def _handle_run_program(self, task: Dict, task_id: str, goal: str) -> Dict:
        program = task.get("program", task.get("exe", task.get("app", "")))
        if not program:
            return {"agent": "system", "status": "失败", "result": "未提供程序路径", "success": False}

        args = task.get("args", task.get("arguments", []))
        if isinstance(args, str):
            args = shlex.split(args)

        cwd = task.get("cwd", task.get("working_dir", None))
        wait = task.get("wait", task.get("wait_for_exit", False))
        timeout = task.get("timeout", self.timeout)

        # 查找可执行文件
        exe_path = shutil.which(program)
        if not exe_path:
            if os.path.exists(program):
                exe_path = program
            else:
                return {
                    "agent": "system", "status": "失败",
                    "result": f"找不到程序: {program}\nPATH 中未找到，请提供完整路径",
                    "success": False,
                }

        try:
            if wait:
                full_cmd = [exe_path] + args
                result = subprocess.run(
                    full_cmd, capture_output=True, text=True,
                    timeout=timeout, cwd=cwd,
                )
                return {
                    "agent": "system", "agent_name": "System 系统操作",
                    "status": "执行完成" if result.returncode == 0 else "执行出错",
                    "result": f"程序已退出 (exit_code={result.returncode})",
                    "stdout": result.stdout[:5000], "stderr": result.stderr[:5000],
                    "exit_code": result.returncode,
                    "program": str(exe_path),
                    "success": result.returncode == 0,
                }
            else:
                full_cmd = [exe_path] + args
                proc = subprocess.Popen(
                    full_cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                    cwd=cwd, creationflags=subprocess.CREATE_NEW_CONSOLE if sys.platform == "win32" else 0,
                )
                return {
                    "agent": "system", "agent_name": "System 系统操作",
                    "status": "已启动", "result": f"程序已启动（后台运行）: {exe_path}",
                    "pid": proc.pid, "program": str(exe_path),
                    "args": args, "success": True,
                }
        except FileNotFoundError:
            return {"agent": "system", "status": "失败", "result": f"找不到: {program}", "success": False}
        except Exception as e:
            return {"agent": "system", "status": "异常", "result": str(e), "success": False}

    # ═══════════════════════════════════════════════════════════
    # 3. 文件操作
    # ═══════════════════════════════════════════════════════════

    def _handle_file_write(self, task: Dict, task_id: str, goal: str) -> Dict:
        file_path = task.get("file_path", task.get("path", task.get("file", "")))
        content = task.get("file_content", task.get("content", ""))
        if not file_path:
            return {"agent": "system", "status": "失败", "result": "未提供文件路径", "success": False}

        # 解析路径: 相对路径 → output_dir；绝对路径需要检查安全范围
        if not os.path.isabs(file_path):
            file_path = os.path.join(self.output_dir, file_path)
        else:
            # 防止路径遍历：绝对路径必须在 output_dir 内或显式允许
            allowed = task.get("allow_absolute_path", False)
            if not allowed:
                # 转为 output_dir 下的文件名（只取文件名部分）
                safe_name = os.path.basename(file_path)
                file_path = os.path.join(self.output_dir, safe_name)

        os.makedirs(os.path.dirname(file_path), exist_ok=True)
        encoding = task.get("encoding", "utf-8")
        with open(file_path, "w", encoding=encoding) as f:
            f.write(content)

        file_size = os.path.getsize(file_path)
        self._last_outputs.append(file_path)

        return {
            "agent": "system", "agent_name": "System 系统操作",
            "status": "写入完成", "result": f"文件已保存: {file_path} ({file_size} bytes)",
            "file_path": str(file_path), "file_size": file_size,
            "encoding": encoding, "success": True,
        }

    def _handle_file_read(self, task: Dict, task_id: str, goal: str) -> Dict:
        file_path = task.get("file_path", task.get("path", task.get("file", "")))
        if not file_path:
            return {"agent": "system", "status": "失败", "result": "未提供文件路径", "success": False}

        if not os.path.isabs(file_path):
            file_path = os.path.join(self.output_dir, file_path)
        elif not task.get("allow_absolute_path", False):
            safe_name = os.path.basename(file_path)
            file_path = os.path.join(self.output_dir, safe_name)

        if not os.path.exists(file_path):
            return {"agent": "system", "status": "失败", "result": f"文件不存在", "success": False}

        max_lines = task.get("max_lines", 500)
        encoding = task.get("encoding", "utf-8")
        lines = []  # 初始化，避免 UnicodeDecodeError 时未定义
        try:
            with open(file_path, "r", encoding=encoding) as f:
                lines = f.readlines()
            truncated = len(lines) > max_lines
            display = lines[:max_lines]
            content = "".join(display)
            if truncated:
                content += f"\n...（共 {len(lines)} 行，仅显示前 {max_lines} 行）"
        except UnicodeDecodeError:
            with open(file_path, "rb") as f:
                raw = f.read()
            content = f"[二进制文件] {len(raw)} bytes"

        return {
            "agent": "system", "agent_name": "System 系统操作",
            "status": "读取完成", "result": content,
            "file_path": str(file_path), "file_size": os.path.getsize(file_path),
            "total_lines": len(lines),
            "success": True,
        }

    def _handle_file_list(self, task: Dict, task_id: str, goal: str) -> Dict:
        directory = task.get("directory", task.get("dir", task.get("path", os.getcwd())))
        if not os.path.isabs(directory):
            directory = os.path.join(self.output_dir, directory)

        if not os.path.exists(directory):
            return {"agent": "system", "status": "失败", "result": f"目录不存在: {directory}", "success": False}

        pattern = task.get("pattern", "*")
        import fnmatch
        entries = []
        if os.path.isdir(directory):
            for name in os.listdir(directory):
                full = os.path.join(directory, name)
                is_dir = os.path.isdir(full)
                if fnmatch.fnmatch(name, pattern):
                    size = "" if is_dir else f" ({os.path.getsize(full):,} bytes)"
                    entries.append(f"{'[DIR]' if is_dir else '[FILE]'}  {name}{size}")
        else:
            entries = [f"[FILE]  {directory} ({os.path.getsize(directory):,} bytes)"]

        return {
            "agent": "system", "agent_name": "System 系统操作",
            "status": "列表完成", "result": "\n".join(entries) if entries else "(空目录)",
            "directory": str(directory), "file_count": len(entries),
            "pattern": pattern, "success": True,
        }

    def _handle_file_search(self, task: Dict, task_id: str, goal: str) -> Dict:
        directory = task.get("directory", task.get("dir", task.get("path", "C:\\" if sys.platform == "win32" else "/")))
        pattern = task.get("pattern", task.get("filename", "*"))
        max_results = task.get("max_results", 50)

        matches = []
        try:
            for root, dirs, files in os.walk(directory):
                for fname in files:
                    import fnmatch
                    if fnmatch.fnmatch(fname, pattern):
                        matches.append(os.path.join(root, fname))
                        if len(matches) >= max_results:
                            break
                if len(matches) >= max_results:
                    break
        except PermissionError:
            pass

        return {
            "agent": "system", "agent_name": "System 系统操作",
            "status": "搜索完成", "result": "\n".join(matches) if matches else f"未找到匹配 '{pattern}' 的文件",
            "matches": matches, "match_count": len(matches),
            "searched_dir": directory, "success": True,
        }

    # ── 3.5 文件删除 ────────────────────────────────────────

    def _handle_file_delete(self, task: Dict, task_id: str, goal: str) -> Dict:
        file_path = task.get("file_path", task.get("path", task.get("file", "")))
        if not file_path:
            return {"agent": "system", "status": "失败", "result": "未提供文件路径", "success": False}

        # 安全：相对路径解析到 output_dir，绝对路径需显式允许
        if not os.path.isabs(file_path):
            file_path = os.path.join(self.output_dir, file_path)
        elif not task.get("allow_absolute_path", False):
            safe_name = os.path.basename(file_path)
            file_path = os.path.join(self.output_dir, safe_name)

        if not os.path.exists(file_path):
            return {"agent": "system", "status": "失败", "result": f"文件不存在", "success": False}

        try:
            os.remove(file_path)
            return {
                "agent": "system", "agent_name": "System 系统操作",
                "status": "删除完成", "result": f"已删除: {file_path}",
                "file_path": str(file_path), "success": True,
            }
        except Exception as e:
            return {"agent": "system", "status": "失败", "result": str(e), "success": False}

    # ═══════════════════════════════════════════════════════════
    # 4. 本地 AI 推理
    # ═══════════════════════════════════════════════════════════

    def _handle_local_ai(self, task: Dict, task_id: str, goal: str) -> Dict:
        prompt = task.get("ai_prompt", task.get("local_ai_prompt", task.get("prompt", goal)))
        backend = task.get("ai_backend", "auto")  # auto / ollama / llama_cpp / openai_compatible
        model = task.get("ai_model", "")
        system_prompt = task.get("system_prompt", "")
        max_tokens = task.get("max_tokens", 1024)
        temperature = task.get("temperature", 0.7)

        if not prompt:
            return {"agent": "system", "status": "失败", "result": "未提供 ai_prompt", "success": False}

        # ══ 后端 1: Ollama CLI ══
        if backend in ("auto", "ollama"):
            try:
                result = self._call_ollama(prompt, model, system_prompt, max_tokens, temperature)
                if result:
                    return result
            except Exception:
                if backend == "ollama":
                    return {"agent": "system", "status": "失败", "result": "Ollama 推理失败", "success": False}

        # ══ 后端 2: llama-cpp-python ══
        if backend in ("auto", "llama_cpp"):
            model_path = task.get("gguf_model_path", "")
            if model_path and os.path.exists(model_path):
                try:
                    return self._call_llama_cpp(model_path, prompt, system_prompt, max_tokens, temperature)
                except Exception as e:
                    if backend == "llama_cpp":
                        return {"agent": "system", "status": "失败", "result": f"llama.cpp 推理失败: {e}", "success": False}

        # ══ 后端 3: OpenAI 兼容接口（Ollama API / LM Studio / etc） ══
        if backend in ("auto", "openai_compatible"):
            endpoint = task.get("api_endpoint", "")
            api_key = task.get("api_key", "not-needed")
            if not endpoint:
                endpoints = _detect_local_ai().get("local_openai_endpoints", [])
                if endpoints:
                    endpoint = endpoints[0]["url"]
            if endpoint:
                try:
                    return self._call_openai_compatible(
                        endpoint, api_key, prompt, model, system_prompt, max_tokens, temperature
                    )
                except Exception as e:
                    if backend == "openai_compatible":
                        return {"agent": "system", "status": "失败", "result": str(e), "success": False}

        # ══ 全部失败 ══
        ai_info = _detect_local_ai()
        return {
            "agent": "system", "agent_name": "System 系统操作",
            "status": "未完成",
            "result": (
                "⚠️ 未检测到可用本地 AI。\n\n"
                f"检测结果:\n"
                f"  Ollama CLI:  {'✅' if ai_info['ollama_available'] else '❌ 未安装'}\n"
                f"  llama.cpp:   {'✅' if ai_info['llama_cpp_available'] else '❌ 未安装'}\n"
                f"  Transformers:{'✅' if ai_info['transformers_available'] else '❌ 未安装'}\n"
                f"  在线端点:    {ai_info['local_openai_endpoints'] or '未检测到'}\n\n"
                "快速修复:\n"
                "  1. 下载 Ollama: https://ollama.ai\n"
                "  2. ollama pull qwen2.5:7b\n"
                "  3. ollama serve\n"
                "  或者放一个 GGUF 文件路径在 gguf_model_path 字段"
            ),
            "ai_detection": ai_info,
            "success": False,
        }

    def _handle_local_ai_list(self, task: Dict, task_id: str, goal: str) -> Dict:
        """列出所有可用本地 AI 能力"""
        info = _detect_local_ai()
        lines = []

        if info["ollama_available"]:
            models = ", ".join(info["ollama_models"]) or "(无已下载模型)"
            lines.append(f"✅ Ollama CLI: 已安装 (模型: {models})")
        else:
            lines.append("❌ Ollama CLI: 未安装 → https://ollama.ai")

        lines.append(f"{'✅' if info['llama_cpp_available'] else '❌'} llama-cpp-python")
        lines.append(f"{'✅' if info['transformers_available'] else '❌'} HuggingFace Transformers")

        if info["local_openai_endpoints"]:
            lines.append("\n🌐 检测到在线本地推理端点:")
            for ep in info["local_openai_endpoints"]:
                lines.append(f"  - {ep['name']}: {ep['url']}")
        else:
            lines.append("🌐 未检测到在线本地推理端点")

        return {
            "agent": "system", "agent_name": "System 系统操作",
            "status": "检测完成", "result": "\n".join(lines),
            "ai_detection": info, "success": True,
        }

    # ═══════════════════════════════════════════════════════════
    # 5. 进程管理
    # ═══════════════════════════════════════════════════════════

    def _handle_process_list(self, task: Dict, task_id: str, goal: str) -> Dict:
        filter_name = task.get("filter", task.get("name_filter", ""))
        try:
            if sys.platform == "win32":
                cmd = ["tasklist", "/fo", "csv", "/nh"]
                r = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
                lines = r.stdout.strip().split("\n")
                processes = []
                for line in lines:
                    parts = line.replace('"', '').split(",")
                    if len(parts) >= 5:
                        name, pid = parts[0].strip(), parts[1].strip()
                        if filter_name and filter_name.lower() not in name.lower():
                            continue
                        processes.append(f"{pid:>8s}  {name}")
                return {
                    "agent": "system", "status": "进程列表",
                    "result": "\n".join(processes[:100]),
                    "process_count": len(processes),
                    "success": True,
                }
            else:
                cmd = ["ps", "aux"]
                r = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
                return {"agent": "system", "status": "进程列表", "result": r.stdout[:5000], "success": True}
        except Exception as e:
            return {"agent": "system", "status": "失败", "result": str(e), "success": False}

    def _handle_process_kill(self, task: Dict, task_id: str, goal: str) -> Dict:
        pid = task.get("pid", task.get("process_id", 0))
        name = task.get("name", task.get("process_name", ""))
        try:
            if pid:
                if sys.platform == "win32":
                    subprocess.run(["taskkill", "/pid", str(pid), "/f"], timeout=10)
                else:
                    subprocess.run(["kill", "-9", str(pid)], timeout=10)
                return {"agent": "system", "status": "已终止", "result": f"进程 PID={pid} 已终止", "success": True}
            elif name:
                if sys.platform == "win32":
                    subprocess.run(["taskkill", "/im", name, "/f"], timeout=10)
                else:
                    subprocess.run(["pkill", "-f", name], timeout=10)
                return {"agent": "system", "status": "已终止", "result": f"进程 '{name}' 已终止", "success": True}
            return {"agent": "system", "status": "失败", "result": "请提供 pid 或 name", "success": False}
        except Exception as e:
            return {"agent": "system", "status": "失败", "result": str(e), "success": False}

    # ═══════════════════════════════════════════════════════════
    # 内部 AI 调用
    # ═══════════════════════════════════════════════════════════

    def _call_ollama(self, prompt: str, model: str = "", system_prompt: str = "",
                     max_tokens: int = 1024, temperature: float = 0.7) -> Optional[Dict]:
        """通过 Ollama CLI 调用本地模型"""
        try:
            # 列出模型
            r = subprocess.run(["ollama", "list"], capture_output=True, text=True, timeout=5)
            if r.returncode != 0:
                return None
            available = []
            for line in r.stdout.strip().split("\n")[1:]:
                if line.split():
                    available.append(line.split()[0])

            if not available:
                return None

            use_model = model if model and model in available else available[0]

            full_prompt = f"{system_prompt}\n\n{prompt}" if system_prompt else prompt
            cmd = ["ollama", "run", use_model, full_prompt,
                   "--format", "json"]
            r = subprocess.run(cmd, capture_output=True, text=True, timeout=self.timeout)

            if r.returncode == 0:
                return {
                    "agent": "system", "agent_name": "System 本地 AI",
                    "status": "推理完成",
                    "result": r.stdout.strip(),
                    "model": use_model, "backend": "ollama",
                    "success": True,
                }

            # 非 JSON 模式重试
            cmd_simple = ["ollama", "run", use_model, full_prompt]
            r2 = subprocess.run(cmd_simple, capture_output=True, text=True, timeout=self.timeout)
            return {
                "agent": "system", "agent_name": "System 本地 AI",
                "status": "推理完成",
                "result": r2.stdout.strip()[:10000],
                "model": use_model, "backend": "ollama",
                "success": True,
            }
        except Exception:
            return None

    def _call_llama_cpp(self, model_path: str, prompt: str, system_prompt: str = "",
                        max_tokens: int = 1024, temperature: float = 0.7) -> Dict:
        """通过 llama-cpp-python 直接加载 GGUF 模型推理"""
        from llama_cpp import Llama

        llm = Llama(model_path=model_path, n_ctx=4096, verbose=False)
        full_prompt = f"{system_prompt}\n\n{prompt}" if system_prompt else prompt
        output = llm(full_prompt, max_tokens=max_tokens, temperature=temperature)
        text = output["choices"][0]["text"].strip()

        return {
            "agent": "system", "agent_name": "System 本地 AI",
            "status": "推理完成",
            "result": text[:10000],
            "model": model_path, "backend": "llama_cpp",
            "success": True,
        }

    def _call_openai_compatible(self, endpoint: str, api_key: str, prompt: str,
                                 model: str = "", system_prompt: str = "",
                                 max_tokens: int = 1024, temperature: float = 0.7) -> Dict:
        """调用 OpenAI 兼容接口 (Ollama API / LM Studio / vLLM / ...)"""
        import httpx

        url = f"{endpoint.rstrip('/')}/chat/completions"
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        headers = {"Content-Type": "application/json"}
        if api_key and api_key != "not-needed":
            headers["Authorization"] = f"Bearer {api_key}"

        body = {
            "model": model or "local-model",
            "messages": messages,
            "max_tokens": max_tokens,
            "temperature": temperature,
        }

        r = httpx.post(url, headers=headers, json=body, timeout=self.timeout)
        r.raise_for_status()
        data = r.json()
        text = data["choices"][0]["message"]["content"].strip()

        return {
            "agent": "system", "agent_name": "System 本地 AI",
            "status": "推理完成",
            "result": text[:10000],
            "model": data.get("model", "local"),
            "backend": "openai_compatible", "endpoint": endpoint,
            "success": True,
        }
