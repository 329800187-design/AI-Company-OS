"""
Agent Loader — 安全加载 agent，缺失时返回 unavailable 状态

用法：
    from backend.services.agent_loader import load_agent, get_agent_status

    # 加载 agent（旧格式：从 AGENT_REGISTRY 查找）
    agent = load_agent("agents.ceo_agent.agent", "CEOAgent")
    if agent is None:
        return {"status": "unavailable", "agent": "ceo"}

    # 加载 agent（新格式：module.path:ClassName）
    agent = load_agent("agents.marketing_agent.agent:MarketingAgent")

    # 通过 manifest 加载
    agent = load_manifest_agent(manifest)

    # 获取所有 agent 状态
    statuses = get_agent_status()
"""

import importlib
import logging
from typing import Any, Dict, Optional, Type

logger = logging.getLogger(__name__)

# Agent 注册表：entrypoint -> class_name（兼容旧 agent，无 manifest 的 fallback）
# 注意：有 manifest 的 agent 仍保留在此，供旧路由的 load_agent_instance 调用使用
AGENT_REGISTRY: Dict[str, str] = {
    "agents.ceo_agent.agent": "CEOAgent",
    "agents.codex_agent.agent": "CodexAgent",
    "agents.qa_agent.agent": "QAAgent",
    "agents.system_agent.agent": "SystemAgent",
    "agents.openclaw_agent.agent": "OpenClawAgent",
    "agents.cto_agent.agent": "CTOAgent",
    "agents.image_agent.agent": "ImageAgent",
    "agents.marketing_agent.agent": "MarketingAgent",
    "agents.video_agent.agent": "VideoAgent",
    "agents.data_agent.agent": "DataAgent",
    "agents.research_agent.agent": "ResearchAgent",
    "agents.website_agent.agent": "WebsiteAgent",
}

# 缓存已加载的 agent 类
_agent_cache: Dict[str, Optional[Type]] = {}

# 缓存加载状态
_agent_status: Dict[str, Dict[str, Any]] = {}


def _parse_entrypoint(entrypoint: str) -> tuple:
    """
    解析 entrypoint 字符串

    支持格式：
    - "module.path:ClassName" → ("module.path", "ClassName")
    - "module.path" + AGENT_REGISTRY → ("module.path", "ClassName") 从注册表查
    - "module.path" 无注册表 → ("module.path", None)
    """
    if ":" in entrypoint:
        module_path, class_name = entrypoint.rsplit(":", 1)
        return module_path, class_name

    # 无冒号：检查 AGENT_REGISTRY
    if entrypoint in AGENT_REGISTRY:
        return entrypoint, AGENT_REGISTRY[entrypoint]

    # 无冒号且不在注册表：尝试最后一个点分段作为类名
    parts = entrypoint.rsplit(".", 1)
    if len(parts) == 2:
        return parts[0], parts[1]

    return entrypoint, None


def load_agent(entrypoint: str, class_name: Optional[str] = None) -> Optional[Type]:
    """
    安全加载 agent 类

    支持两种 entrypoint 格式：
    1. 旧格式：entrypoint="agents.ceo_agent.agent", class_name="CEOAgent"
    2. 新格式：entrypoint="agents.marketing_agent.agent:MarketingAgent"

    Args:
        entrypoint: 模块路径，可包含 :ClassName
        class_name: 类名。如果为 None，从 entrypoint 解析或从 AGENT_REGISTRY 查找

    Returns:
        Agent 类，如果加载失败返回 None
    """
    # 解析 entrypoint
    module_path, parsed_class = _parse_entrypoint(entrypoint)
    if class_name is None:
        class_name = parsed_class

    # 构造缓存 key
    cache_key = f"{module_path}:{class_name}" if class_name else module_path

    # 检查缓存
    if cache_key in _agent_cache:
        return _agent_cache[cache_key]

    # 查找类名
    if class_name is None:
        class_name = AGENT_REGISTRY.get(module_path)
        if class_name is None:
            logger.warning(f"Agent '{entrypoint}' not found in AGENT_REGISTRY and no class specified")
            _agent_cache[cache_key] = None
            _agent_status[cache_key] = {
                "status": "unavailable",
                "error": "Not registered in AGENT_REGISTRY and no class specified"
            }
            return None

    try:
        # 动态导入模块
        module = importlib.import_module(module_path)
        # 获取类
        agent_class = getattr(module, class_name)

        # 缓存成功加载的结果
        _agent_cache[cache_key] = agent_class
        _agent_status[cache_key] = {
            "status": "available",
            "class": class_name,
            "module": module_path,
        }

        logger.debug(f"Successfully loaded agent: {module_path}.{class_name}")
        return agent_class

    except ImportError as e:
        logger.warning(f"Failed to import agent '{module_path}': {e}")
        _agent_cache[cache_key] = None
        _agent_status[cache_key] = {
            "status": "unavailable",
            "error": f"ImportError: {str(e)}"
        }
        return None

    except AttributeError as e:
        logger.warning(f"Failed to find class '{class_name}' in '{module_path}': {e}")
        _agent_cache[cache_key] = None
        _agent_status[cache_key] = {
            "status": "unavailable",
            "error": f"AttributeError: {str(e)}"
        }
        return None

    except Exception as e:
        logger.error(f"Unexpected error loading agent '{module_path}': {e}")
        _agent_cache[cache_key] = None
        _agent_status[cache_key] = {
            "status": "unavailable",
            "error": f"Exception: {str(e)}"
        }
        return None


def load_manifest_agent(manifest) -> Optional[Type]:
    """
    通过 AgentManifest 加载 agent

    Args:
        manifest: AgentManifest 实例

    Returns:
        Agent 类，加载失败返回 None
    """
    if not manifest.enabled:
        logger.debug(f"Agent '{manifest.id}' is disabled in manifest")
        return None

    module_path, class_name = manifest.parse_entrypoint()
    return load_agent(f"{module_path}:{class_name}")


def load_agent_instance(entrypoint: str, class_name: Optional[str] = None, **kwargs) -> Optional[Any]:
    """
    安全加载并实例化 agent

    Args:
        entrypoint: 模块路径，支持 "module.path:ClassName" 格式
        class_name: 类名
        **kwargs: 传递给构造函数的参数

    Returns:
        Agent 实例，如果加载失败返回 None
    """
    agent_class = load_agent(entrypoint, class_name)
    if agent_class is None:
        return None

    try:
        return agent_class(**kwargs)
    except Exception as e:
        module_path, cls = _parse_entrypoint(entrypoint)
        cache_key = f"{module_path}:{cls or class_name}"
        logger.error(f"Failed to instantiate agent '{cache_key}': {e}")
        _agent_status[cache_key] = {
            "status": "unavailable",
            "error": f"Instantiation error: {str(e)}"
        }
        return None


def get_agent_status(entrypoint: Optional[str] = None) -> Dict[str, Dict[str, Any]]:
    """
    获取 agent 状态

    Args:
        entrypoint: 如果指定，返回该 agent 的状态；否则返回所有 agent 的状态

    Returns:
        状态字典
    """
    if entrypoint:
        # 确保已尝试加载
        if entrypoint not in _agent_status:
            load_agent(entrypoint)
        return _agent_status.get(entrypoint, {"status": "unknown"})

    # 返回所有 agent 状态
    for ep in AGENT_REGISTRY:
        if ep not in _agent_status:
            load_agent(ep)

    return dict(_agent_status)


def get_available_agents() -> Dict[str, Type]:
    """
    获取所有可用的 agent 类

    Returns:
        可用 agent 字典：{entrypoint: agent_class}
    """
    available = {}

    for entrypoint, class_name in AGENT_REGISTRY.items():
        agent_class = load_agent(entrypoint, class_name)
        if agent_class is not None:
            available[entrypoint] = agent_class

    return available


def reset_cache():
    """重置缓存（用于测试）"""
    global _agent_cache, _agent_status
    _agent_cache = {}
    _agent_status = {}
