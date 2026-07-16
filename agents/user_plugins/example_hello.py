"""Example user plugin — Hello World agent"""
NAME = "Hello World"
DESCRIPTION = "A simple example plugin that echoes input"
CAPABILITIES = ["echo", "hello"]

def run(task: dict) -> dict:
    goal = task.get("goal", "hello")
    name = task.get("name", "World")
    return {
        "message": f"Hello {name}! You asked: {goal}",
        "timestamp": __import__("datetime").datetime.now().isoformat(),
    }
