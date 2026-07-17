"""Plugin 配置路由 — 可视化管理用户插件"""
import json
import os
from pathlib import Path
from fastapi import APIRouter, HTTPException, UploadFile, File
from pydantic import BaseModel, Field
from typing import Any, Dict, List, Optional

router = APIRouter(prefix="/plugins", tags=["插件管理 / Plugin Manager"])

PLUGIN_DIR = Path(__file__).parent.parent.parent / "agents" / "user_plugins"
PLUGIN_DIR.mkdir(parents=True, exist_ok=True)


class CreatePluginRequest(BaseModel):
    """创建插件请求"""
    name: str = Field(..., description="插件名称")
    description: str = Field("", description="插件描述")
    capabilities: List[str] = Field(default_factory=list, description="能力标签")
    task_types: List[str] = Field(default_factory=list, description="可处理的任务类型")
    code: str = Field(..., description="Python 代码 (必须包含 run(task) 函数)")


class UpdatePluginRequest(BaseModel):
    """更新插件请求"""
    plugin_id: str
    name: Optional[str] = None
    description: Optional[str] = None
    capabilities: Optional[List[str]] = None
    task_types: Optional[List[str]] = None
    code: Optional[str] = None


@router.get("/", summary="列出所有用户插件")
def list_plugins():
    """列出所有用户自定义插件"""
    from core.plugin_loader import get_plugin_loader
    loader = get_plugin_loader()
    plugins = loader.list_all()
    # 添加文件信息
    for p in plugins:
        py_file = PLUGIN_DIR / f"{p['id']}.py"
        if py_file.exists():
            p["file_size"] = py_file.stat().st_size
            p["file_path"] = str(py_file)
            p["modified"] = py_file.stat().st_mtime
    return {"plugins": plugins, "count": len(plugins)}


@router.get("/{plugin_id}", summary="获取插件详情")
def get_plugin(plugin_id: str):
    """获取指定插件的详细信息（含源码）"""
    from core.plugin_loader import get_plugin_loader
    loader = get_plugin_loader()
    plugin = loader.get(plugin_id)
    if not plugin:
        raise HTTPException(status_code=404, detail="插件不存在")

    py_file = PLUGIN_DIR / f"{plugin_id}.py"
    source_code = ""
    if py_file.exists():
        source_code = py_file.read_text(encoding="utf-8")

    return {
        "id": plugin.id,
        "name": plugin.name,
        "description": plugin.description,
        "capabilities": plugin.capabilities,
        "source_code": source_code,
        "file_path": str(py_file),
    }


@router.post("/create", summary="创建新插件")
def create_plugin(request: CreatePluginRequest):
    """创建一个新的用户插件"""
    # 生成插件 ID
    plugin_id = request.name.lower().replace(" ", "_").replace("-", "_")
    plugin_id = "".join(c for c in plugin_id if c.isalnum() or c == "_")

    py_file = PLUGIN_DIR / f"{plugin_id}.py"
    if py_file.exists():
        raise HTTPException(status_code=400, detail=f"插件已存在: {plugin_id}")

    # 验证代码必须包含 run 函数
    if "def run(" not in request.code:
        raise HTTPException(status_code=400, detail="代码必须包含 run(task) 函数")

    # 生成插件文件
    code = _generate_plugin_code(
        name=request.name,
        description=request.description,
        capabilities=request.capabilities,
        task_types=request.task_types,
        user_code=request.code,
    )

    py_file.write_text(code, encoding="utf-8")

    # 重新加载
    from core.plugin_loader import get_plugin_loader
    loader = get_plugin_loader()
    loader._discover()

    return {
        "ok": True,
        "message": f"插件 {request.name} 创建成功",
        "plugin_id": plugin_id,
        "file_path": str(py_file),
    }


@router.put("/update", summary="更新插件")
def update_plugin(request: UpdatePluginRequest):
    """更新现有插件"""
    py_file = PLUGIN_DIR / f"{request.plugin_id}.py"
    if not py_file.exists():
        raise HTTPException(status_code=404, detail="插件文件不存在")

    if request.code:
        if "def run(" not in request.code:
            raise HTTPException(status_code=400, detail="代码必须包含 run(task) 函数")
        py_file.write_text(request.code, encoding="utf-8")
    else:
        # 读取现有代码并更新元数据
        existing = py_file.read_text(encoding="utf-8")
        if request.name:
            existing = _update_meta(existing, "NAME", request.name)
        if request.description:
            existing = _update_meta(existing, "DESCRIPTION", request.description)
        if request.capabilities is not None:
            existing = _update_meta(existing, "CAPABILITIES", request.capabilities)
        if request.task_types is not None:
            existing = _update_meta(existing, "TASK_TYPES", request.task_types)
        py_file.write_text(existing, encoding="utf-8")

    # 重新加载
    from core.plugin_loader import get_plugin_loader
    loader = get_plugin_loader()
    loader._discover()

    return {"ok": True, "message": "插件已更新"}


@router.delete("/{plugin_id}", summary="删除插件")
def delete_plugin(plugin_id: str):
    """删除指定插件"""
    py_file = PLUGIN_DIR / f"{plugin_id}.py"
    if not py_file.exists():
        raise HTTPException(status_code=404, detail="插件文件不存在")

    # 备份到 trash
    trash_dir = PLUGIN_DIR / "_trash"
    trash_dir.mkdir(exist_ok=True)
    import shutil
    shutil.move(str(py_file), str(trash_dir / f"{plugin_id}.py"))

    # 重新加载
    from core.plugin_loader import get_plugin_loader
    loader = get_plugin_loader()
    loader._discover()

    return {"ok": True, "message": f"插件 {plugin_id} 已删除（已备份到 _trash）"}


@router.post("/{plugin_id}/test", summary="测试插件")
def test_plugin(plugin_id: str, task: Dict[str, Any] = None):
    """测试运行指定插件"""
    # Governance Guard: 从 task payload 提取 goal 并检查
    from backend.governance.guard import guard_payload, governance_block_response, extract_goal_from_payload
    from backend.governance.classifier import ClassificationResult

    check_payload = task if task else {}
    blocked, classification = guard_payload(check_payload)
    if blocked:
        return governance_block_response(classification)

    # 插件是任意代码执行入口，不允许无目标执行
    if not task or not extract_goal_from_payload(task):
        no_goal_class = ClassificationResult(
            ok=False,
            confidence=0.0,
            reason="插件测试必须提供明确的用户意图（goal/prompt/message/command）",
            needs_clarification=True,
            clarification_questions=["请提供 goal 或 prompt 描述你希望插件执行的测试任务"],
        )
        return governance_block_response(no_goal_class)

    from core.plugin_loader import get_plugin_loader
    loader = get_plugin_loader()
    result = loader.run(plugin_id, task)
    return result


@router.get("/templates/list", summary="插件模板列表")
def list_templates():
    """获取插件代码模板"""
    return {
        "templates": [
            {
                "id": "basic",
                "name": "基础模板",
                "description": "最简单的插件模板",
                "code": BASIC_TEMPLATE,
            },
            {
                "id": "ai_chat",
                "name": "AI 对话模板",
                "description": "接入 AI API 的对话插件",
                "code": AI_CHAT_TEMPLATE,
            },
            {
                "id": "file_processor",
                "name": "文件处理模板",
                "description": "处理文件的插件模板",
                "code": FILE_PROCESSOR_TEMPLATE,
            },
        ]
    }


# ═══════════════════════════════════════════════════════════════
# 辅助函数
# ═══════════════════════════════════════════════════════════════

def _generate_plugin_code(name: str, description: str,
                          capabilities: List[str], task_types: List[str],
                          user_code: str) -> str:
    """生成插件代码"""
    caps_str = json.dumps(capabilities, ensure_ascii=False)
    types_str = json.dumps(task_types, ensure_ascii=False)

    return f'''"""
{name} — 用户自定义插件
{description}
"""
import json

NAME = "{name}"
DESCRIPTION = """{description}"""
CAPABILITIES = {caps_str}
TASK_TYPES = {types_str}


{user_code}
'''


def _update_meta(code: str, meta_name: str, value: Any) -> str:
    """更新代码中的元数据"""
    import re
    if isinstance(value, list):
        value_str = json.dumps(value, ensure_ascii=False)
    else:
        value_str = f'"{value}"'

    pattern = rf'^{meta_name}\s*=.*$'
    replacement = f'{meta_name} = {value_str}'
    return re.sub(pattern, replacement, code, count=1, flags=re.MULTILINE)


# ═══════════════════════════════════════════════════════════════
# 插件模板
# ═══════════════════════════════════════════════════════════════

BASIC_TEMPLATE = '''def run(task: dict) -> dict:
    """
    插件入口函数
    Args:
        task: 任务字典，包含 goal, task_type 等字段
    Returns:
        结果字典
    """
    goal = task.get("goal", "")

    # 在这里实现你的逻辑
    result = f"收到任务: {goal}"

    return {"output": result}
'''

AI_CHAT_TEMPLATE = '''def run(task: dict) -> dict:
    """AI 对话插件示例"""
    import httpx

    goal = task.get("goal", "")

    # 调用 AI API
    try:
        with httpx.Client(timeout=30) as client:
            resp = client.post(
                "http://127.0.0.1:15721/v1/messages",
                headers={
                    "Content-Type": "application/json",
                    "x-api-key": "sk-ccswitch-proxy",
                    "anthropic-version": "2023-06-01",
                },
                json={
                    "model": "deepseek-v4-pro",
                    "max_tokens": 1024,
                    "messages": [{"role": "user", "content": goal}],
                },
            )
            resp.raise_for_status()
            data = resp.json()

        text = ""
        for block in data.get("content", []):
            if block.get("type") == "text":
                text += block.get("text", "")

        return {"output": text, "model": data.get("model", "")}
    except Exception as e:
        return {"error": str(e)}
'''

FILE_PROCESSOR_TEMPLATE = '''import os
from pathlib import Path

def run(task: dict) -> dict:
    """文件处理插件示例"""
    goal = task.get("goal", "")
    file_path = task.get("file_path", "")

    if not file_path:
        return {"error": "请提供 file_path 参数"}

    path = Path(file_path)
    if not path.exists():
        return {"error": f"文件不存在: {file_path}"}

    # 读取文件
    content = path.read_text(encoding="utf-8")

    # 处理逻辑
    lines = content.split("\\n")
    word_count = len(content.split())
    char_count = len(content)

    return {
        "file": str(path),
        "lines": len(lines),
        "words": word_count,
        "characters": char_count,
        "preview": content[:500],
    }
'''
