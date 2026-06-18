import os
import shutil
import json
import subprocess
import time

# 配置你的路径
PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
TASKS_DB_PATH = os.path.join(PROJECT_ROOT, "memory", "tasks.json")
TASKS_FOLDER = os.path.join(PROJECT_ROOT, "memory", "tasks")
APP_FILE = os.path.join(PROJECT_ROOT, "backend", "app.py")
VENV_PYTHON = os.path.join(PROJECT_ROOT, ".venv", "Scripts", "python.exe")  # Windows

def reset_tasks():
    # 清空任务数据库
    if os.path.exists(TASKS_DB_PATH):
        with open(TASKS_DB_PATH, "w", encoding="utf-8") as f:
            json.dump([], f)
        print(f"[✔] 已清空任务数据库: {TASKS_DB_PATH}")
    else:
        print(f"[!] 任务数据库不存在: {TASKS_DB_PATH}")

    # 清空任务文件夹
    if os.path.exists(TASKS_FOLDER):
        shutil.rmtree(TASKS_FOLDER)
        os.makedirs(TASKS_FOLDER, exist_ok=True)
        print(f"[✔] 已清空任务文件夹: {TASKS_FOLDER}")
    else:
        print(f"[!] 任务文件夹不存在: {TASKS_FOLDER}")

def start_server():
    print("[→] 启动 AI Company OS 服务器...")
    # 使用 uvicorn 启动 FastAPI
    cmd = [VENV_PYTHON, "-m", "uvicorn", "backend.app:app", "--reload", "--host", "127.0.0.1", "--port", "8000"]
    # Windows 下 subprocess 可以直接用 creationflags=subprocess.CREATE_NEW_CONSOLE 打开新窗口
    subprocess.Popen(cmd, creationflags=subprocess.CREATE_NEW_CONSOLE)
    print("[✔] 服务器已启动，浏览器访问 http://127.0.0.1:8000/docs 查看接口")

if __name__ == "__main__":
    reset_tasks()
    start_server()