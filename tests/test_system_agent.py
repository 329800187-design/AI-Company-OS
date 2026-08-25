"""System Agent 测试"""
import os
import sys
import json
import builtins
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from agents.system_agent.agent import SystemAgent, _detect_local_ai


def test_detect_local_ai():
    """检测本机 AI 能力"""
    info = _detect_local_ai()
    assert "ollama_available" in info
    assert "llama_cpp_available" in info
    assert "local_openai_endpoints" in info
    print("AI Detection:", json.dumps(info, indent=2, ensure_ascii=False))


def test_detect_local_ai_handles_broken_optional_runtime(monkeypatch):
    """Optional native runtimes with missing DLLs must be reported unavailable."""
    original_import = builtins.__import__

    def broken_llama_import(name, *args, **kwargs):
        if name == "llama_cpp":
            raise RuntimeError("llama.dll is unavailable")
        return original_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", broken_llama_import)
    info = _detect_local_ai()

    assert info["llama_cpp_available"] is False


def test_shell_execute():
    """命令行执行"""
    agent = SystemAgent(timeout=30)
    result = agent.run({
        "task_id": "test_shell_001",
        "task_type": "shell_execute",
        "command": "echo Hello System Agent",
        "shell_type": "cmd",
    })
    print("Shell result:", result.get("stdout", ""))
    assert result["success"]
    assert "Hello System Agent" in result.get("stdout", "")


def test_shell_powershell():
    """PowerShell 执行"""
    agent = SystemAgent(timeout=30)
    result = agent.run({
        "task_id": "test_ps_001",
        "task_type": "shell_execute",
        "command": "Write-Output 'Hello PowerShell'",
        "shell_type": "powershell",
    })
    print("PS result:", result.get("stdout", ""))
    assert result["success"]
    assert "Hello PowerShell" in result.get("stdout", "")
    assert result["agent"] == "system"


def test_shell_timeout():
    """命令超时"""
    agent = SystemAgent(timeout=3)
    result = agent.run({
        "task_id": "test_timeout_001",
        "task_type": "shell_execute",
        "command": "ping -n 10 127.0.0.1",
        "shell_type": "cmd",
    })
    print("Timeout result:", result.get("status"))
    assert not result["success"]
    assert "超时" in result.get("status", "")


def test_dangerous_blocked():
    """危险命令拦截"""
    agent = SystemAgent(timeout=30)
    result = agent.run({
        "task_id": "test_dangerous_001",
        "task_type": "shell_execute",
        "command": "format C: /q",
    })
    assert not result["success"]
    assert "拦截" in result.get("status", "") or "拦截" in result.get("result", "")


def test_run_program_notepad():
    """启动程序（不等待）"""
    agent = SystemAgent(timeout=10)
    result = agent.run({
        "task_id": "test_prog_001",
        "task_type": "run_program",
        "program": "whoami.exe",
        "wait": True,
    })
    print("Program result:", result.get("stdout", ""))
    assert result["success"]


def test_file_write_and_read():
    """文件写入和读取"""
    agent = SystemAgent(timeout=10)
    test_path = os.path.join(agent.output_dir, "test_file.txt")

    # 写入
    w_result = agent.run({
        "task_id": "test_fw_001",
        "task_type": "file_write",
        "file_path": test_path,
        "file_content": "Hello from System Agent! 你好世界",
    })
    print("Write:", w_result)
    assert w_result["success"]
    assert os.path.exists(test_path)

    # 读取
    r_result = agent.run({
        "task_id": "test_fr_001",
        "task_type": "file_read",
        "file_path": test_path,
    })
    print("Read:", r_result.get("result", ""))
    assert r_result["success"]
    assert "你好世界" in r_result.get("result", "")

    # 清理
    os.remove(test_path)


def test_file_list():
    """目录列表"""
    agent = SystemAgent(timeout=10)
    result = agent.run({
        "task_id": "test_fl_001",
        "task_type": "file_list",
        "directory": os.path.dirname(__file__),
        "pattern": "*.py",
    })
    print("List:", result.get("result", ""))
    assert result["success"]
    assert "test_system_agent" in result.get("result", "")


def test_process_list():
    """进程列表"""
    agent = SystemAgent(timeout=15)
    result = agent.run({
        "task_id": "test_pl_001",
        "task_type": "process_list",
        "filter": "python",
    })
    print("Processes:", result.get("result", ""))
    assert result["success"]


def test_local_ai_detect():
    """本地 AI 检测"""
    agent = SystemAgent(timeout=10)
    result = agent.run({
        "task_id": "test_lai_001",
        "task_type": "local_ai_list",
    })
    output = result.get("result", "")
    print("AI Detection:", output)
    assert result["success"]
    assert "ai_detection" in result


def test_output_files_tracking():
    """产出文件跟踪"""
    agent = SystemAgent(timeout=10)
    result = agent.run({
        "task_id": "test_of_001",
        "task_type": "file_write",
        "file_path": "test_output.txt",
        "file_content": "产出文件测试",
    })
    print("Output files:", result.get("output_files"))
    assert result["success"]
    assert result.get("output_files")
    assert "output_dir" in result

    # 清理
    for f in result.get("output_files", []):
        if os.path.exists(f):
            os.remove(f)


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
