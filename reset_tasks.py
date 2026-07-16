import os
import shutil
import json

# 配置你的路径
TASKS_DB_PATH = "memory/tasks.json"  # 假设任务保存在这个文件
TASKS_FOLDER = "memory/tasks/"      # 如果任务还有单独文件夹

def reset_tasks():
    # 1. 清空任务文件
    if os.path.exists(TASKS_DB_PATH):
        with open(TASKS_DB_PATH, "w", encoding="utf-8") as f:
            json.dump([], f)
        print(f"已清空任务数据库: {TASKS_DB_PATH}")
    else:
        print(f"任务数据库不存在: {TASKS_DB_PATH}")

    # 2. 清空任务文件夹
    if os.path.exists(TASKS_FOLDER):
        shutil.rmtree(TASKS_FOLDER)
        os.makedirs(TASKS_FOLDER, exist_ok=True)
        print(f"已清空任务文件夹: {TASKS_FOLDER}")
    else:
        print(f"任务文件夹不存在: {TASKS_FOLDER}")

    print("任务队列已重置完成。")

if __name__ == "__main__":
    reset_tasks()