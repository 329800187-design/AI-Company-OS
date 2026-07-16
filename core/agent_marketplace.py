"""
Agent Marketplace — 远程 Agent 发现与安装

支持：
1. 远程 Agent 注册表 (HTTP API)
2. Agent 搜索与安装
3. Agent 评分与评论
4. 版本管理

Agent 市场协议:
  GET  /api/agents           → 列出所有可用 Agent
  GET  /api/agents/{id}      → 获取 Agent 详情
  POST /api/agents/register  → 注册新 Agent
  GET  /api/agents/search    → 搜索 Agent
"""
import json
import os
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

import httpx


# ═══════════════════════════════════════════════════════════════
# Data Model
# ═══════════════════════════════════════════════════════════════

@dataclass
class AgentManifest:
    """Agent 清单 — 描述一个可安装的 Agent"""
    agent_id: str
    name: str
    description: str
    version: str = "1.0.0"
    author: str = ""
    category: str = "general"       # general/productivity/code/browser/data/media
    capabilities: List[str] = field(default_factory=list)
    task_types: List[str] = field(default_factory=list)
    entry_point: str = ""           # Python 入口: module.path:ClassName
    install_url: str = ""           # 下载地址
    icon: str = "🤖"
    rating: float = 0.0
    downloads: int = 0
    tags: List[str] = field(default_factory=list)
    requirements: List[str] = field(default_factory=list)  # pip 依赖
    min_version: str = "0.8.0"      # 最低系统版本
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "agent_id": self.agent_id,
            "name": self.name,
            "description": self.description,
            "version": self.version,
            "author": self.author,
            "category": self.category,
            "capabilities": self.capabilities,
            "task_types": self.task_types,
            "entry_point": self.entry_point,
            "install_url": self.install_url,
            "icon": self.icon,
            "rating": self.rating,
            "downloads": self.downloads,
            "tags": self.tags,
            "requirements": self.requirements,
            "min_version": self.min_version,
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "AgentManifest":
        return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})


# ═══════════════════════════════════════════════════════════════
# Agent Marketplace
# ═══════════════════════════════════════════════════════════════

class AgentMarketplace:
    """Agent 市场 — 远程发现与本地安装"""

    # 内置 Agent 清单 (离线可用)
    BUILTIN_AGENTS: List[AgentManifest] = [
        AgentManifest(
            agent_id="ceo_agent", name="CEO Agent", icon="👔",
            description="目标拆解智能体 — 将高层目标分解为可执行子任务",
            category="productivity", capabilities=["decompose", "plan", "prioritize"],
            task_types=["decompose_goal", "create_plan"], author="AI Company OS",
            version="1.0.0", rating=4.8, downloads=1000,
        ),
        AgentManifest(
            agent_id="cto_agent", name="CTO Agent", icon="🔧",
            description="技术架构智能体 — 代码审查、技术选型、架构评审",
            category="code", capabilities=["code_review", "tech_stack", "architecture"],
            task_types=["code_review", "tech_selection"], author="AI Company OS",
            version="1.0.0", rating=4.7, downloads=800,
        ),
        AgentManifest(
            agent_id="codex_agent", name="Codex Agent", icon="💻",
            description="代码沙箱智能体 — 安全执行 Python/JS 代码",
            category="code", capabilities=["code_execute", "sandbox", "python", "javascript"],
            task_types=["code_execute", "code_generate"], author="AI Company OS",
            version="1.0.0", rating=4.9, downloads=1200,
        ),
        AgentManifest(
            agent_id="openclaw_agent", name="OpenClaw Agent", icon="🌐",
            description="浏览器自动化智能体 — 网页抓取、截图、表单填写",
            category="browser", capabilities=["browser", "scrape", "screenshot", "canvas"],
            task_types=["browser_scrape", "browser_screenshot"], author="AI Company OS",
            version="2.0.0", rating=4.6, downloads=900,
        ),
        AgentManifest(
            agent_id="qa_agent", name="QA Agent", icon="✅",
            description="质量验收智能体 — AI 语义评分、结果验证",
            category="productivity", capabilities=["review", "score", "validate"],
            task_types=["quality_check", "result_review"], author="AI Company OS",
            version="1.0.0", rating=4.5, downloads=700,
        ),
        AgentManifest(
            agent_id="system_agent", name="System Agent", icon="⚙️",
            description="系统操作智能体 — 文件管理、进程控制、环境配置",
            category="system", capabilities=["file_ops", "process", "env_config"],
            task_types=["file_operation", "system_command"], author="AI Company OS",
            version="1.0.0", rating=4.4, downloads=600,
        ),
        AgentManifest(
            agent_id="image_agent", name="Image Agent", icon="🎨",
            description="图片生成智能体 — DALL-E/DeepSeek 图片生成与分析",
            category="media", capabilities=["image_generate", "image_analyze", "image_edit"],
            task_types=["image_generate", "image_analyze"], author="AI Company OS",
            version="1.0.0", rating=4.6, downloads=850,
        ),
        AgentManifest(
            agent_id="marketing_agent", name="Marketing Agent", icon="📝",
            description="营销内容智能体 — 文案、SEO、社交媒体内容",
            category="productivity", capabilities=["copywriting", "seo", "social_media"],
            task_types=["marketing_copy", "seo_optimize"], author="AI Company OS",
            version="1.0.0", rating=4.5, downloads=750,
        ),
        AgentManifest(
            agent_id="video_agent", name="Video Agent", icon="🎬",
            description="视频创意智能体 — 脚本撰写、分镜设计",
            category="media", capabilities=["video_script", "storyboard"],
            task_types=["video_script", "storyboard"], author="AI Company OS",
            version="1.0.0", rating=4.3, downloads=500,
        ),
        AgentManifest(
            agent_id="data_agent", name="Data Agent", icon="📊",
            description="数据分析智能体 — CSV/Excel 分析、可视化图表",
            category="data", capabilities=["data_analyze", "data_viz", "data_clean"],
            task_types=["data_analyze", "data_visualize"], author="AI Company OS",
            version="1.0.0", rating=4.7, downloads=950,
        ),
    ]

    def __init__(self, remote_url: str = None, local_dir: str = None):
        self._remote_url = remote_url or os.getenv("AGENT_MARKETPLACE_URL", "")
        self._local_dir = Path(local_dir or os.getenv(
            "AGENT_MARKETPLACE_DIR",
            str(Path(__file__).parent.parent / "agents" / "installed")
        ))
        self._local_dir.mkdir(parents=True, exist_ok=True)
        self._installed: Dict[str, AgentManifest] = {}
        self._load_installed()

    def _load_installed(self):
        """加载已安装的 Agent 清单"""
        manifest_file = self._local_dir / "manifests.json"
        if manifest_file.exists():
            try:
                data = json.loads(manifest_file.read_text(encoding="utf-8"))
                for item in data:
                    manifest = AgentManifest.from_dict(item)
                    self._installed[manifest.agent_id] = manifest
            except Exception:
                pass

    def _save_installed(self):
        """保存已安装的 Agent 清单"""
        manifest_file = self._local_dir / "manifests.json"
        data = [m.to_dict() for m in self._installed.values()]
        manifest_file.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

    # ── 查询 ──────────────────────────────────────────────────

    def list_available(self, category: str = None) -> List[Dict[str, Any]]:
        """列出所有可用 Agent（内置 + 远程）"""
        agents = list(self.BUILTIN_AGENTS)

        # 远程市场
        if self._remote_url:
            try:
                remote = self._fetch_remote()
                agents.extend(remote)
            except Exception:
                pass

        # 本地已安装
        for installed in self._installed.values():
            if installed.agent_id not in [a.agent_id for a in agents]:
                agents.append(installed)

        if category:
            agents = [a for a in agents if a.category == category]

        return [a.to_dict() for a in agents]

    def search(self, query: str) -> List[Dict[str, Any]]:
        """搜索 Agent"""
        query_lower = query.lower()
        results = []
        for agent in self.BUILTIN_AGENTS:
            score = 0
            if query_lower in agent.name.lower():
                score += 10
            if query_lower in agent.description.lower():
                score += 5
            for cap in agent.capabilities:
                if query_lower in cap.lower():
                    score += 3
            for tag in agent.tags:
                if query_lower in tag.lower():
                    score += 2
            if score > 0:
                results.append((score, agent))

        results.sort(key=lambda x: -x[0])
        return [a.to_dict() for _, a in results]

    def get_agent(self, agent_id: str) -> Optional[Dict[str, Any]]:
        """获取 Agent 详情"""
        # 先查内置
        for agent in self.BUILTIN_AGENTS:
            if agent.agent_id == agent_id:
                return agent.to_dict()
        # 再查已安装
        if agent_id in self._installed:
            return self._installed[agent_id].to_dict()
        return None

    def get_categories(self) -> List[Dict[str, Any]]:
        """获取所有分类"""
        cats = {}
        for agent in self.BUILTIN_AGENTS:
            if agent.category not in cats:
                cats[agent.category] = {"id": agent.category, "name": agent.category, "count": 0}
            cats[agent.category]["count"] += 1
        return list(cats.values())

    # ── 安装 ──────────────────────────────────────────────────

    def install(self, agent_id: str) -> Dict[str, Any]:
        """安装 Agent"""
        manifest = self.get_agent(agent_id)
        if not manifest:
            return {"ok": False, "error": f"Agent 不存在: {agent_id}"}

        # 检查是否已安装
        if agent_id in self._installed:
            return {"ok": True, "message": "已安装", "agent": manifest}

        # 创建安装记录
        m = AgentManifest.from_dict(manifest)
        self._installed[agent_id] = m
        self._save_installed()

        return {"ok": True, "message": f"已安装 {m.name}", "agent": manifest}

    def uninstall(self, agent_id: str) -> Dict[str, Any]:
        """卸载 Agent"""
        if agent_id not in self._installed:
            return {"ok": False, "error": "未安装此 Agent"}
        del self._installed[agent_id]
        self._save_installed()
        return {"ok": True, "message": f"已卸载 {agent_id}"}

    def list_installed(self) -> List[Dict[str, Any]]:
        """列出已安装的 Agent"""
        return [m.to_dict() for m in self._installed.values()]

    # ── 远程市场 ──────────────────────────────────────────────

    def _fetch_remote(self) -> List[AgentManifest]:
        """从远程市场获取 Agent 列表"""
        if not self._remote_url:
            return []
        try:
            with httpx.Client(timeout=10, proxy=None, trust_env=False) as client:
                r = client.get(f"{self._remote_url}/api/agents")
                r.raise_for_status()
                data = r.json()
                return [AgentManifest.from_dict(item) for item in data.get("agents", [])]
        except Exception:
            return []

    def register_remote(self, manifest: AgentManifest) -> Dict[str, Any]:
        """向远程市场注册 Agent"""
        if not self._remote_url:
            return {"ok": False, "error": "未配置远程市场 URL"}
        try:
            with httpx.Client(timeout=10, proxy=None, trust_env=False) as client:
                r = client.post(
                    f"{self._remote_url}/api/agents/register",
                    json=manifest.to_dict(),
                )
                r.raise_for_status()
                return {"ok": True, "data": r.json()}
        except Exception as e:
            return {"ok": False, "error": str(e)}

    # ── 统计 ──────────────────────────────────────────────────

    def get_stats(self) -> Dict[str, Any]:
        """获取市场统计"""
        return {
            "builtin_count": len(self.BUILTIN_AGENTS),
            "installed_count": len(self._installed),
            "categories": len(set(a.category for a in self.BUILTIN_AGENTS)),
            "remote_configured": bool(self._remote_url),
        }


# ═══════════════════════════════════════════════════════════════
# Singleton
# ═══════════════════════════════════════════════════════════════

_marketplace: Optional[AgentMarketplace] = None


def get_marketplace() -> AgentMarketplace:
    global _marketplace
    if _marketplace is None:
        _marketplace = AgentMarketplace()
    return _marketplace
