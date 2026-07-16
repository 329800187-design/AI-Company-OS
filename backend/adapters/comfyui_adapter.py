"""
ComfyUI Adapter — ComfyUI 图片生成适配器

注意：ComfyUI API 调用尚未实现
图片生成功能暂未开通
"""
import os
import socket
from pathlib import Path
from typing import Dict, Any, List
from .base_adapter import BaseAdapter


class ComfyUIAdapter(BaseAdapter):
    """ComfyUI 适配器"""

    TOOL_NAME = "comfyui"

    def __init__(self):
        self._comfyui_dir = self._find_comfyui()
        self._port = 8188

    def _find_comfyui(self) -> Path:
        """查找 ComfyUI 安装目录"""
        comfyui_paths = [
            Path.home() / "ComfyUI-Installs" / "comfyui-local",
            Path("C:/ComfyUI"),
            Path("D:/ComfyUI"),
            Path.home() / "ComfyUI",
        ]

        env_path = os.getenv("COMFYUI_PATH")
        if env_path:
            comfyui_paths.insert(0, Path(env_path))

        for path in comfyui_paths:
            if path.exists() and (path / "main.py").exists():
                return path

        return None

    def can_handle(self, task_type: str, task: Dict[str, Any]) -> bool:
        """判断是否能处理此任务"""
        return task_type == "image"

    def health_check(self) -> Dict[str, Any]:
        """健康检查"""
        if not self._comfyui_dir:
            return {
                "available": False,
                "installed": False,
                "error": "未找到 ComfyUI 安装目录",
                "fix_hint": "请安装 ComfyUI 或设置 COMFYUI_PATH 环境变量"
            }

        # 检查模型
        models = self._get_models()

        # 检查是否运行
        running = self._check_port()

        if not running:
            return {
                "available": False,
                "installed": True,
                "running": False,
                "models": models,
                "model_count": len(models),
                "error": "ComfyUI 未启动",
                "fix_hint": f"请启动 ComfyUI: cd {self._comfyui_dir} && python main.py"
            }

        # ComfyUI 运行中，但 API 调用尚未实现
        return {
            "available": False,
            "installed": True,
            "running": True,
            "models": models,
            "model_count": len(models),
            "error": "图片生成功能暂未开通",
            "fix_hint": "ComfyUI API 调用正在开发中，请等待后续版本"
        }

    def run(self, task: Dict[str, Any]) -> Dict[str, Any]:
        """执行图片生成"""
        health = self.health_check()

        # 明确返回不可用
        return self._create_result(
            ok=False,
            error=health.get("error", "图片生成功能暂未开通"),
            warnings=[health.get("fix_hint", "")]
        )

    def _get_models(self) -> List[str]:
        """获取可用模型列表"""
        if not self._comfyui_dir:
            return []

        checkpoints_dir = self._comfyui_dir / "models" / "checkpoints"
        if not checkpoints_dir.exists():
            return []

        return [f.stem for f in checkpoints_dir.glob("*.safetensors")]

    def _check_port(self) -> bool:
        """检查端口是否在线"""
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(2)
            result = sock.connect_ex(("localhost", self._port))
            sock.close()
            return result == 0
        except:
            return False
