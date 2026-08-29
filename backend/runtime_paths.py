"""Runtime-owned paths.

Project code and user state must have different lifecycles.  Keeping the
runtime database beside the checkout made a fresh machine appear to have the
previous machine's tasks and audit history.
"""
import os
import platform
import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Mapping


@dataclass(frozen=True)
class RuntimeMigrationResult:
    action: str
    database_path: Path
    copied_paths: tuple[Path, ...] = ()


class RuntimePathResolver:
    """Resolve runtime-owned paths and migrate legacy state safely."""

    def __init__(self, new_root: Path, legacy_root: Path):
        self.new_root = Path(new_root)
        self.legacy_root = Path(legacy_root)

    @classmethod
    def from_platform(
        cls, system: str | None = None, home: Path | None = None,
        env: Mapping[str, str] | None = None,
    ) -> "RuntimePathResolver":
        env = env or os.environ
        home = Path(home or Path.home())
        system = system or platform.system()
        override = env.get("AI_COMPANY_OS_USER_DATA", "").strip()
        if override:
            new_root = Path(override).expanduser()
        elif system == "Darwin":
            new_root = home / "Library" / "Application Support" / "AI Company OS"
        elif system == "Windows":
            new_root = Path(env.get("APPDATA", home / "AppData" / "Roaming")) / "AI Company OS"
        else:
            new_root = Path(env.get("XDG_DATA_HOME", home / ".local" / "share")) / "ai-company-os"
        legacy_root = Path(env.get(
            "AI_COMPANY_OS_LEGACY_DATA",
            str(Path(__file__).resolve().parents[1]),
        ))
        return cls(new_root, legacy_root)

    @property
    def database_path(self) -> Path:
        return self.new_root / "company_os.db"

    @property
    def agent_registry_dir(self) -> Path:
        return self.new_root / "agent_registry"

    @property
    def enabled_agents_path(self) -> Path:
        return self.agent_registry_dir / "enabled_agents.json"

    def legacy_database_candidates(self) -> tuple[Path, ...]:
        return (
            self.legacy_root / "company_os.db",
            self.legacy_root / "backend" / "database" / "company_os.db",
        )

    def legacy_agent_candidates(self) -> tuple[Path, ...]:
        return (
            self.legacy_root / "agent_registry" / "enabled_agents.json",
            self.legacy_root / "user_data" / "agent_registry" / "enabled_agents.json",
        )

    def ensure_new_root(self) -> Path:
        self.new_root.mkdir(parents=True, exist_ok=True)
        return self.new_root


def migrate_legacy_runtime_data(resolver: RuntimePathResolver) -> RuntimeMigrationResult:
    """Copy legacy state once, preserving both sources and never overwriting new state."""
    resolver.ensure_new_root()
    new_db = resolver.database_path
    new_agents = resolver.enabled_agents_path
    copied: list[Path] = []

    legacy_db = next((path for path in resolver.legacy_database_candidates() if path.exists()), None)
    legacy_agents = next((path for path in resolver.legacy_agent_candidates() if path.exists()), None)

    if new_db.exists() and legacy_db is not None:
        action = "both_existing"
    elif new_db.exists():
        action = "new_existing"
    elif legacy_db is not None:
        shutil.copy2(legacy_db, new_db)
        copied.append(new_db)
        action = "migrated"
    else:
        action = "fresh"

    if not new_agents.exists() and legacy_agents is not None:
        new_agents.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(legacy_agents, new_agents)
        copied.append(new_agents)

    return RuntimeMigrationResult(action, new_db, tuple(copied))


def _default_user_data_dir() -> Path:
    return RuntimePathResolver.from_platform().new_root


USER_DATA_DIR = _default_user_data_dir()
DATABASE_PATH = USER_DATA_DIR / "company_os.db"
AGENT_REGISTRY_DIR = USER_DATA_DIR / "agent_registry"
ENABLED_AGENTS_PATH = AGENT_REGISTRY_DIR / "enabled_agents.json"


def ensure_user_data_dir() -> Path:
    USER_DATA_DIR.mkdir(parents=True, exist_ok=True)
    return USER_DATA_DIR


_DEFAULT_RESOLVER = RuntimePathResolver.from_platform()
_DEFAULT_MIGRATION = migrate_legacy_runtime_data(_DEFAULT_RESOLVER)
