"""
AgentManifest — Agent 清单模型

通过 agent.json 声明式注册 agent，替代硬编码目录/类名识别。
"""
import json
import logging
from pathlib import Path
from typing import Dict, List, Optional

from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


class AgentManifest(BaseModel):
    """Agent 清单描述"""
    id: str = Field(..., description="唯一标识，如 marketing")
    name: str = Field(..., description="显示名称，如 营销内容")
    version: str = Field(default="1.0.0", description="语义版本号")
    entrypoint: str = Field(
        ...,
        description="加载入口，格式 module.path:ClassName，如 agents.marketing_agent.agent:MarketingAgent"
    )
    capabilities: List[str] = Field(default_factory=list, description="能力标签")
    task_types: List[str] = Field(default_factory=list, description="可处理任务类型")
    risk_level: str = Field(default="low", description="风险等级: low/medium/high")
    enabled: bool = Field(default=True, description="是否启用")
    description: str = Field(default="", description="一句话说明")
    requires_api_key: bool = Field(default=False)
    requires_gpu: bool = Field(default=False)

    def parse_entrypoint(self) -> tuple:
        """
        解析 entrypoint 为 (module_path, class_name)

        Returns:
            (module_path, class_name) 元组
        """
        if ":" in self.entrypoint:
            module_path, class_name = self.entrypoint.rsplit(":", 1)
        else:
            # 兼容旧格式：没有冒号时，从末尾取类名
            parts = self.entrypoint.rsplit(".", 1)
            if len(parts) == 2:
                module_path, class_name = parts
            else:
                module_path = self.entrypoint
                class_name = ""
        return module_path, class_name


def scan_manifests(project_root: Optional[Path] = None) -> Dict[str, AgentManifest]:
    """
    扫描项目中所有 agent.json manifest

    扫描路径：
    - agents/*/agent.json
    - agents/installed/*/agent.json

    Returns:
        {manifest_id: AgentManifest} 字典
    """
    if project_root is None:
        project_root = Path(__file__).resolve().parent.parent.parent

    manifests: Dict[str, AgentManifest] = {}
    scan_dirs = [
        project_root / "agents",
    ]

    for base_dir in scan_dirs:
        if not base_dir.exists():
            continue

        for agent_dir in base_dir.iterdir():
            if not agent_dir.is_dir():
                continue

            manifest_file = agent_dir / "agent.json"
            if not manifest_file.exists():
                continue

            try:
                with open(manifest_file, "r", encoding="utf-8") as f:
                    data = json.load(f)

                manifest = AgentManifest(**data)
                if manifest.id in manifests:
                    logger.warning(
                        f"Duplicate manifest id '{manifest.id}' "
                        f"in {manifest_file} (already from {manifests[manifest.id].entrypoint})"
                    )
                manifests[manifest.id] = manifest
                logger.debug(f"Loaded manifest: {manifest.id} from {manifest_file}")

            except json.JSONDecodeError as e:
                logger.warning(f"Invalid JSON in {manifest_file}: {e}")
            except Exception as e:
                logger.warning(f"Failed to load manifest {manifest_file}: {e}")

    # 扫描 agents/installed/*/agent.json
    installed_dir = project_root / "agents" / "installed"
    if installed_dir.exists():
        for agent_dir in installed_dir.iterdir():
            if not agent_dir.is_dir():
                continue

            manifest_file = agent_dir / "agent.json"
            if not manifest_file.exists():
                continue

            try:
                with open(manifest_file, "r", encoding="utf-8") as f:
                    data = json.load(f)

                manifest = AgentManifest(**data)
                if manifest.id in manifests:
                    logger.warning(
                        f"Duplicate manifest id '{manifest.id}' "
                        f"in {manifest_file} (already from {manifests[manifest.id].entrypoint})"
                    )
                manifests[manifest.id] = manifest
                logger.debug(f"Loaded manifest: {manifest.id} from {manifest_file}")

            except json.JSONDecodeError as e:
                logger.warning(f"Invalid JSON in {manifest_file}: {e}")
            except Exception as e:
                logger.warning(f"Failed to load manifest {manifest_file}: {e}")

    logger.info(f"Scanned {len(manifests)} agent manifests")
    return manifests
