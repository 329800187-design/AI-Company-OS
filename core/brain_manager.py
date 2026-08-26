"""
Brain Manager — 主脑管理器

管理所有可用的 AI 主脑（大模型），支持动态切换。
用户无需关心 Provider/Token/Endpoint，系统自动选择最佳主脑。

主脑列表：
  1. DeepSeek — 默认主脑，性价比高
  2. MiMo — 阿里系，代码能力强
  3. Claude — Anthropic，分析能力强
  4. OpenAI — GPT-4，通用能力强
  5. Ollama — 本地推理，零成本
  6. LM Studio — 本地推理，GUI 管理
  7. CC Switch — 本地代理，多后端切换

使用方式：
  brain = get_brain_manager()
  current = brain.get_current()  # 获取当前主脑
  brain.switch_to("deepseek")    # 切换主脑
  response = brain.chat("你好")  # 对话
"""
import json
import os
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

import httpx


@dataclass
class BrainProfile:
    """主脑配置"""
    brain_id: str                # 唯一标识
    name: str                    # 显示名称
    provider: str                # 提供商
    description: str             # 描述
    icon: str = "🧠"             # 图标
    base_url: str = ""           # API 地址
    model: str = ""              # 模型名称
    api_key_env: str = ""        # API Key 环境变量名
    is_local: bool = False       # 是否本地服务
    capabilities: List[str] = field(default_factory=list)
    priority: int = 0            # 优先级（越高越优先）
    enabled: bool = True         # 是否启用

    def to_dict(self) -> Dict[str, Any]:
        return {
            "brain_id": self.brain_id,
            "name": self.name,
            "provider": self.provider,
            "description": self.description,
            "icon": self.icon,
            "base_url": self.base_url,
            "model": self.model,
            "is_local": self.is_local,
            "capabilities": self.capabilities,
            "priority": self.priority,
            "enabled": self.enabled,
            "has_api_key": (
                bool(os.getenv(self.api_key_env, ""))
                or (self.provider == "claude" and bool(os.getenv("ANTHROPIC_API_KEY", "")))
            ) if self.api_key_env else True,
        }


class BrainManager:
    """主脑管理器"""

    # 内置主脑配置
    BUILTIN_BRAINS = [
        BrainProfile(
            brain_id="deepseek",
            name="DeepSeek",
            provider="deepseek",
            description="性价比高的国产大模型，适合日常对话和代码生成",
            icon="🔮",
            base_url="https://api.deepseek.com/v1",
            model="deepseek-chat",
            api_key_env="DEEPSEEK_API_KEY",
            capabilities=["chat", "code", "analysis"],
            priority=100,
        ),
        BrainProfile(
            brain_id="mimo",
            name="MiMo",
            provider="mimo",
            description="阿里系大模型，代码能力强",
            icon="🤖",
            base_url="https://api.mimo.ai/v1",
            model="mimo-chat",
            api_key_env="MIMO_API_KEY",
            capabilities=["chat", "code"],
            priority=90,
        ),
        BrainProfile(
            brain_id="claude",
            name="Claude",
            provider="claude",
            description="Anthropic 出品，分析和写作能力强",
            icon="🎭",
            base_url="https://api.anthropic.com/v1",
            model="claude-sonnet-4-20250514",
            api_key_env="CLAUDE_API_KEY",
            capabilities=["chat", "code", "analysis", "writing"],
            priority=85,
        ),
        BrainProfile(
            brain_id="openai",
            name="OpenAI",
            provider="openai",
            description="GPT-4 系列，通用能力最强",
            icon="✨",
            base_url="https://api.openai.com/v1",
            model="gpt-4o",
            api_key_env="OPENAI_API_KEY",
            capabilities=["chat", "code", "image", "analysis"],
            priority=80,
        ),
        BrainProfile(
            brain_id="ollama",
            name="Ollama",
            provider="ollama",
            description="本地推理，零成本，隐私安全",
            icon="🦙",
            base_url="http://127.0.0.1:11434",
            model="llama3",
            is_local=True,
            capabilities=["chat", "code", "local"],
            priority=70,
        ),
        BrainProfile(
            brain_id="lm_studio",
            name="LM Studio",
            provider="lm_studio",
            description="本地推理，GUI 管理模型",
            icon="🏠",
            base_url="http://127.0.0.1:1234/v1",
            model="local-model",
            is_local=True,
            capabilities=["chat", "code", "local"],
            priority=65,
        ),
        BrainProfile(
            brain_id="cc_switch",
            name="CC Switch",
            provider="cc_switch",
            description="本地代理，多后端自动切换",
            icon="🔄",
            base_url="http://127.0.0.1:15721/v1",
            model="auto",
            is_local=True,
            capabilities=["chat", "proxy", "multi_backend"],
            priority=60,
        ),
    ]

    def __init__(self, config_dir: str = None):
        self._config_dir = Path(config_dir or str(
            Path(__file__).parent.parent / "backend" / "config"
        ))
        self._config_dir.mkdir(parents=True, exist_ok=True)
        self._config_file = self._config_dir / "brain_config.json"

        self._brains: Dict[str, BrainProfile] = {}
        self._current_id: str = "deepseek"

        self._load_config()

    def _load_config(self):
        """加载配置"""
        # 加载内置主脑
        for b in self.BUILTIN_BRAINS:
            self._brains[b.brain_id] = b

        # 加载用户配置
        if self._config_file.exists():
            try:
                data = json.loads(self._config_file.read_text(encoding="utf-8"))
                self._current_id = data.get("current", "deepseek")
                # 更新启用状态
                for brain_id, enabled in data.get("enabled", {}).items():
                    if brain_id in self._brains:
                        self._brains[brain_id].enabled = enabled
            except Exception:
                pass

    def _sync_runtime_profiles(self) -> None:
        """同步 Web UI 配置到主脑资料，避免启动时快照覆盖运行时修改。"""
        try:
            from backend.config import get_ai_config, get_current_provider
        except Exception:
            return

        for brain_id in ("deepseek", "openai", "claude"):
            brain = self._brains.get(brain_id)
            if not brain:
                continue
            cfg = get_ai_config(brain_id)
            brain.base_url = cfg["base_url"].rstrip("/")
            if brain_id == "claude" and not brain.base_url.endswith("/v1"):
                brain.base_url += "/v1"
            brain.model = cfg["model"]

        runtime_brain = os.getenv("AI_BRAIN_ID", "")
        if runtime_brain in self._brains:
            self._current_id = runtime_brain
        else:
            runtime_provider = get_current_provider()
            if runtime_provider in ("deepseek", "openai", "claude"):
                self._current_id = runtime_provider

    @staticmethod
    def _has_credentials(brain: BrainProfile) -> bool:
        if brain.is_local:
            return True
        if os.getenv(brain.api_key_env, ""):
            return True
        return brain.provider == "claude" and bool(os.getenv("ANTHROPIC_API_KEY", ""))

    def _save_config(self):
        """保存配置"""
        data = {
            "current": self._current_id,
            "enabled": {bid: b.enabled for bid, b in self._brains.items()},
        }
        self._config_file.write_text(
            json.dumps(data, ensure_ascii=False, indent=2),
            encoding="utf-8"
        )

    # ── 查询 ──────────────────────────────────────────────────

    def list_all(self) -> List[Dict[str, Any]]:
        """列出所有主脑"""
        self._sync_runtime_profiles()
        return [b.to_dict() for b in self._brains.values()]

    def list_available(self) -> List[Dict[str, Any]]:
        """列出可用主脑（已启用且有 API Key 或是本地服务）"""
        self._sync_runtime_profiles()
        available = []
        for b in self._brains.values():
            if not b.enabled:
                continue
            # 本地服务直接可用
            if b.is_local:
                available.append(b.to_dict())
                continue
            # 云端服务需要 API Key
            if self._has_credentials(b):
                available.append(b.to_dict())
        return available

    def get_current(self) -> Dict[str, Any]:
        """获取当前主脑"""
        self._sync_runtime_profiles()
        brain = self._brains.get(self._current_id)
        if not brain:
            brain = self._brains["deepseek"]
            self._current_id = "deepseek"
        return brain.to_dict()

    def get_brain(self, brain_id: str) -> Optional[Dict[str, Any]]:
        """获取指定主脑"""
        brain = self._brains.get(brain_id)
        return brain.to_dict() if brain else None

    # ── 切换 ──────────────────────────────────────────────────

    def switch_to(self, brain_id: str) -> Dict[str, Any]:
        """切换主脑"""
        if brain_id not in self._brains:
            return {"ok": False, "error": f"主脑不存在: {brain_id}"}

        brain = self._brains[brain_id]
        if not brain.enabled:
            return {"ok": False, "error": f"主脑已禁用: {brain.name}"}

        # 允许先选择未配置的云端主脑，再由设置页补充凭据；它不会被列为可用主脑，聊天也会明确返回缺钥提示。
        ready = self._has_credentials(brain)

        old_id = self._current_id
        self._current_id = brain_id
        os.environ["AI_BRAIN_ID"] = brain_id
        if brain.provider in ("deepseek", "openai", "claude"):
            try:
                from backend.config import apply_runtime_config
                apply_runtime_config({"AI_PROVIDER": brain.provider})
            except Exception:
                pass
        self._save_config()

        result = {
            "ok": True,
            "message": f"已切换到 {brain.icon} {brain.name}",
            "old": old_id,
            "new": brain_id,
            "ready": ready,
        }
        if not ready:
            result["warning"] = f"尚未配置 API Key: {brain.api_key_env}"
        return result

    def enable_brain(self, brain_id: str) -> Dict[str, Any]:
        """启用主脑"""
        if brain_id not in self._brains:
            return {"ok": False, "error": "不存在"}
        self._brains[brain_id].enabled = True
        self._save_config()
        return {"ok": True}

    def disable_brain(self, brain_id: str) -> Dict[str, Any]:
        """禁用主脑"""
        if brain_id not in self._brains:
            return {"ok": False, "error": "不存在"}
        if brain_id == self._current_id:
            return {"ok": False, "error": "不能禁用当前主脑"}
        self._brains[brain_id].enabled = False
        self._save_config()
        return {"ok": True}

    # ── 自动选择 ──────────────────────────────────────────────

    def auto_select(self) -> str:
        """自动选择最佳主脑（基于可用性和优先级）"""
        available = self.list_available()
        if not available:
            return "deepseek"  # 默认

        # 按优先级排序
        available.sort(key=lambda x: -x.get("priority", 0))
        return available[0]["brain_id"]

    # ── 对话 ──────────────────────────────────────────────────

    def chat(self, message: str, system: str = "", temperature: float = 0.7,
             max_tokens: int = 4096, history: Optional[List[Dict[str, str]]] = None) -> Dict[str, Any]:
        """使用当前主脑进行对话"""
        self._sync_runtime_profiles()
        brain = self._brains.get(self._current_id)
        if not brain:
            return {"ok": False, "error": "主脑未配置"}

        if not self._has_credentials(brain):
            return {
                "ok": False,
                "error": f"{brain.name} API Key 未配置，请先在设置页填写并保存",
                "brain": brain.brain_id,
                "provider": brain.provider,
            }

        # 获取 API Key
        api_key = os.getenv(brain.api_key_env, "") if brain.api_key_env else ""
        if not api_key and brain.provider == "claude":
            api_key = os.getenv("ANTHROPIC_API_KEY", "")

        # 构建请求
        if brain.provider == "claude":
            return self._chat_claude(brain, message, system, api_key, max_tokens, history or [])
        else:
            return self._chat_openai_compatible(brain, message, system, api_key,
                                                 temperature, max_tokens, history or [])

    def _chat_openai_compatible(self, brain: BrainProfile, message: str,
                                 system: str, api_key: str,
                                 temperature: float, max_tokens: int,
                                 history: List[Dict[str, str]]) -> Dict[str, Any]:
        """OpenAI 兼容格式对话"""
        headers = {"Content-Type": "application/json"}
        if api_key:
            headers["Authorization"] = f"Bearer {api_key}"

        body = {
            "model": brain.model,
            "messages": ([{"role": "system", "content": system or "你是一个有帮助的AI助手。"}]
                         + history[-20:] + [{"role": "user", "content": message}]),
            "temperature": temperature,
            "max_tokens": max_tokens,
        }

        try:
            with httpx.Client(timeout=60, proxy=None, trust_env=False) as client:
                r = client.post(
                    f"{brain.base_url}/chat/completions",
                    headers=headers,
                    json=body,
                )
                r.raise_for_status()
                data = r.json()

            reply = data["choices"][0]["message"]["content"]
            return {
                "ok": True,
                "reply": reply,
                "provider": brain.provider,
                "brain": brain.brain_id,
                "model": data.get("model", brain.model),
                "usage": data.get("usage", {}),
            }
        except Exception as e:
            return {"ok": False, "error": str(e), "brain": brain.name}

    def _chat_claude(self, brain: BrainProfile, message: str,
                     system: str, api_key: str, max_tokens: int,
                     history: List[Dict[str, str]]) -> Dict[str, Any]:
        """Claude 格式对话"""
        if not api_key:
            return {"ok": False, "error": "缺少 Claude API Key"}

        headers = {
            "Content-Type": "application/json",
            "x-api-key": api_key,
            "anthropic-version": "2023-06-01",
        }

        body = {
            "model": brain.model,
            "max_tokens": max_tokens,
            "system": system or "你是一个有帮助的AI助手。",
            "messages": history[-20:] + [{"role": "user", "content": message}],
        }

        try:
            with httpx.Client(timeout=60, proxy=None, trust_env=False) as client:
                r = client.post(
                    f"{brain.base_url}/messages",
                    headers=headers,
                    json=body,
                )
                r.raise_for_status()
                data = r.json()

            text = ""
            for block in data.get("content", []):
                if block.get("type") == "text":
                    text += block.get("text", "")

            return {
                "ok": True,
                "reply": text,
                "provider": brain.provider,
                "brain": brain.brain_id,
                "model": data.get("model", brain.model),
                "usage": data.get("usage", {}),
            }
        except Exception as e:
            return {"ok": False, "error": str(e), "brain": brain.name}

    # ── 健康检查 ──────────────────────────────────────────────

    def health_check(self) -> Dict[str, Any]:
        """检查所有主脑健康状态"""
        results = {}
        for brain_id, brain in self._brains.items():
            if not brain.enabled:
                continue

            # 本地服务检查连接
            if brain.is_local:
                try:
                    with httpx.Client(timeout=3, proxy=None, trust_env=False) as client:
                        r = client.get(f"{brain.base_url}/models" if "ollama" not in brain_id else f"{brain.base_url}/api/tags")
                        status = "online" if r.status_code == 200 else "offline"
                except Exception:
                    status = "offline"
            else:
                # 云端服务检查 API Key
                status = "configured" if self._has_credentials(brain) else "no_api_key"

            results[brain_id] = {
                "name": brain.name,
                "icon": brain.icon,
                "status": status,
                "is_current": brain_id == self._current_id,
            }

        return results


# ── 单例 ──────────────────────────────────────────

_manager: Optional[BrainManager] = None


def get_brain_manager() -> BrainManager:
    global _manager
    if _manager is None:
        _manager = BrainManager()
    return _manager
