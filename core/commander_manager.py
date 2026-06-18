"""
Commander Manager — 主智能体管理器

支持：
1. 注册多个可选的主智能体 (Commander)
2. 动态切换当前主智能体
3. 自定义主智能体配置
4. 主智能体健康检查

默认主智能体: CommanderAgent (多Agent编排)
可替换为: 任意实现 run(goal, session_id) 接口的智能体
"""
import json
import logging
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Type

logger = logging.getLogger("commander_manager")


@dataclass
class CommanderProfile:
    """主智能体配置"""
    commander_id: str
    name: str
    description: str
    icon: str = "🧠"
    module_path: str = ""       # Python 模块路径: backend.commander.commander
    class_name: str = ""        # 类名: CommanderAgent
    is_builtin: bool = True     # 是否内置
    capabilities: List[str] = field(default_factory=list)
    config: Dict[str, Any] = field(default_factory=dict)
    enabled: bool = True
    priority: int = 0           # 优先级 (越高越优先)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "commander_id": self.commander_id,
            "name": self.name,
            "description": self.description,
            "icon": self.icon,
            "module_path": self.module_path,
            "class_name": self.class_name,
            "is_builtin": self.is_builtin,
            "capabilities": self.capabilities,
            "config": self.config,
            "enabled": self.enabled,
            "priority": self.priority,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "CommanderProfile":
        return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})


class CommanderManager:
    """主智能体管理器"""

    # 内置 Commander 配置
    BUILTIN_COMMANDERS = [
        CommanderProfile(
            commander_id="default",
            name="标准指挥官",
            description="多Agent协作编排 — 自动拆解目标、分配Agent、验收结果",
            icon="🧠",
            module_path="backend.commander.commander",
            class_name="CommanderAgent",
            capabilities=["decompose", "delegate", "verify", "multi_agent"],
            priority=100,
        ),
        CommanderProfile(
            commander_id="simple",
            name="简易指挥官",
            description="单Agent直接执行 — 不拆解，直接调用最佳Agent完成任务",
            icon="⚡",
            module_path="backend.commander.simple_commander",
            class_name="SimpleCommander",
            capabilities=["direct_execute", "fast_response"],
            priority=50,
        ),
        CommanderProfile(
            commander_id="swarm",
            name="群体指挥官",
            description="Swarm模式 — Agent点对点协同，无中心化编排",
            icon="🐝",
            module_path="backend.commander.swarm_commander",
            class_name="SwarmCommander",
            capabilities=["swarm", "peer_to_peer", "distributed"],
            priority=30,
        ),
    ]

    def __init__(self, config_dir: str = None):
        self._config_dir = Path(config_dir or str(
            Path(__file__).parent.parent / "backend" / "config"
        ))
        self._config_dir.mkdir(parents=True, exist_ok=True)
        self._config_file = self._config_dir / "commander_config.json"

        # 注册表
        self._profiles: Dict[str, CommanderProfile] = {}
        self._current_id: str = "default"
        self._instances: Dict[str, Any] = {}  # 缓存实例

        # 加载配置
        self._load_config()

    def _load_config(self):
        """加载配置文件"""
        # 先加载内置
        for p in self.BUILTIN_COMMANDERS:
            self._profiles[p.commander_id] = p

        # 再加载用户配置
        if self._config_file.exists():
            try:
                data = json.loads(self._config_file.read_text(encoding="utf-8"))
                self._current_id = data.get("current", "default")
                for item in data.get("custom", []):
                    profile = CommanderProfile.from_dict(item)
                    self._profiles[profile.commander_id] = profile
            except Exception as e:
                logger.warning(f"加载 Commander 配置失败: {e}")

    def _save_config(self):
        """保存配置文件"""
        custom = [
            p.to_dict() for p in self._profiles.values()
            if not p.is_builtin
        ]
        data = {
            "current": self._current_id,
            "custom": custom,
        }
        self._config_file.write_text(
            json.dumps(data, ensure_ascii=False, indent=2),
            encoding="utf-8"
        )

    # ── 查询 ──────────────────────────────────────────────────

    def list_all(self) -> List[Dict[str, Any]]:
        """列出所有可用的 Commander"""
        result = []
        for p in self._profiles.values():
            d = p.to_dict()
            d["is_current"] = (p.commander_id == self._current_id)
            result.append(d)
        result.sort(key=lambda x: -x.get("priority", 0))
        return result

    def get_current(self) -> Dict[str, Any]:
        """获取当前 Commander 信息"""
        profile = self._profiles.get(self._current_id)
        if not profile:
            profile = self._profiles["default"]
            self._current_id = "default"
        return {
            **profile.to_dict(),
            "is_current": True,
        }

    def get_profile(self, commander_id: str) -> Optional[CommanderProfile]:
        """获取指定 Commander 配置"""
        return self._profiles.get(commander_id)

    # ── 切换 ──────────────────────────────────────────────────

    def switch_to(self, commander_id: str) -> Dict[str, Any]:
        """切换当前 Commander"""
        if commander_id not in self._profiles:
            return {"ok": False, "error": f"Commander 不存在: {commander_id}"}

        profile = self._profiles[commander_id]
        if not profile.enabled:
            return {"ok": False, "error": f"Commander 已禁用: {profile.name}"}

        old_id = self._current_id
        self._current_id = commander_id
        self._save_config()

        # 清除旧实例缓存
        self._instances.pop(old_id, None)

        return {
            "ok": True,
            "message": f"已切换到 {profile.icon} {profile.name}",
            "old": old_id,
            "new": commander_id,
        }

    # ── 自定义 Commander ──────────────────────────────────────

    def register_custom(self, profile: CommanderProfile) -> Dict[str, Any]:
        """注册自定义 Commander"""
        profile.is_builtin = False
        profile.enabled = True
        self._profiles[profile.commander_id] = profile
        self._save_config()
        return {"ok": True, "message": f"已注册 {profile.name}"}

    def unregister_custom(self, commander_id: str) -> Dict[str, Any]:
        """注销自定义 Commander"""
        profile = self._profiles.get(commander_id)
        if not profile:
            return {"ok": False, "error": "不存在"}
        if profile.is_builtin:
            return {"ok": False, "error": "不能注销内置 Commander"}

        del self._profiles[commander_id]
        if self._current_id == commander_id:
            self._current_id = "default"
        self._save_config()
        return {"ok": True, "message": f"已注销 {commander_id}"}

    def update_config(self, commander_id: str, config: Dict[str, Any]) -> Dict[str, Any]:
        """更新 Commander 配置"""
        profile = self._profiles.get(commander_id)
        if not profile:
            return {"ok": False, "error": "不存在"}
        profile.config.update(config)
        self._save_config()
        return {"ok": True, "message": "配置已更新"}

    # ── 实例化 ────────────────────────────────────────────────

    def get_instance(self, commander_id: str = None) -> Any:
        """获取 Commander 实例"""
        cid = commander_id or self._current_id
        profile = self._profiles.get(cid)
        if not profile:
            raise ValueError(f"Commander 不存在: {cid}")

        # 有缓存就用缓存
        if cid in self._instances:
            return self._instances[cid]

        # 动态导入
        try:
            import importlib
            module = importlib.import_module(profile.module_path)
            cls = getattr(module, profile.class_name)
            instance = cls(**profile.config)
            self._instances[cid] = instance
            return instance
        except Exception as e:
            logger.error(f"实例化 Commander 失败 [{cid}]: {e}")
            # fallback 到默认
            if cid != "default":
                return self.get_instance("default")
            raise

    # ── 健康检查 ──────────────────────────────────────────────

    def health_check(self) -> Dict[str, Any]:
        """检查所有 Commander 健康状态"""
        results = {}
        for cid, profile in self._profiles.items():
            if not profile.enabled:
                continue
            try:
                instance = self.get_instance(cid)
                results[cid] = {
                    "status": "ok",
                    "name": profile.name,
                    "icon": profile.icon,
                    "is_current": cid == self._current_id,
                }
            except Exception as e:
                results[cid] = {
                    "status": "error",
                    "name": profile.name,
                    "error": str(e),
                }
        return results


# ═══════════════════════════════════════════════════════════════
# Singleton
# ═══════════════════════════════════════════════════════════════

_manager: Optional[CommanderManager] = None


def get_commander_manager() -> CommanderManager:
    global _manager
    if _manager is None:
        _manager = CommanderManager()
    return _manager
