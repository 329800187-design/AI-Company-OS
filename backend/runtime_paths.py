"""Runtime-owned paths.

Project code and user state must have different lifecycles.  Keeping the
runtime database beside the checkout made a fresh machine appear to have the
previous machine's tasks and audit history.
"""
import os
import platform
import shutil
import sqlite3
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Mapping


@dataclass(frozen=True)
class RuntimeMigrationResult:
    action: str
    database_path: Path
    copied_paths: tuple[Path, ...] = ()


class RuntimeMigrationError(RuntimeError):
    """Raised when runtime state cannot be migrated safely."""


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
        if _backup_sqlite_database(legacy_db, new_db):
            copied.append(new_db)
            action = "migrated"
        else:
            action = "new_existing"
    else:
        action = "fresh"

    if not new_agents.exists() and legacy_agents is not None:
        new_agents.parent.mkdir(parents=True, exist_ok=True)
        _atomic_copy_regular_file(legacy_agents, new_agents)
        copied.append(new_agents)

    return RuntimeMigrationResult(action, new_db, tuple(copied))


def _acquire_migration_lock(lock_path: Path):
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    handle = open(lock_path, "a+")
    try:
        handle.seek(0, os.SEEK_END)
        if handle.tell() == 0:
            handle.write("0")
            handle.flush()
        handle.seek(0)
        if os.name == "nt":
            import msvcrt
            msvcrt.locking(handle.fileno(), msvcrt.LK_LOCK, 1)
        else:
            import fcntl
            fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
        return handle
    except Exception:
        handle.close()
        raise


def _backup_sqlite_database(source: Path, destination: Path) -> bool:
    lock = _acquire_migration_lock(destination.parent / ".migration.lock")
    temp_path: Path | None = None
    try:
        if destination.exists():
            return False
        fd, raw_path = tempfile.mkstemp(prefix=".company_os.", suffix=".db", dir=destination.parent)
        os.close(fd)
        temp_path = Path(raw_path)
        with sqlite3.connect(source) as src, sqlite3.connect(temp_path) as dst:
            src.backup(dst)
            check = dst.execute("PRAGMA quick_check").fetchone()
            if not check or check[0] != "ok":
                raise RuntimeMigrationError(f"SQLite quick_check failed: {check}")
            dst.commit()
        with open(temp_path, "rb") as db_file:
            os.fsync(db_file.fileno())
        os.replace(temp_path, destination)
        temp_path = None
        return True
    except Exception as exc:
        raise RuntimeMigrationError(f"SQLite migration failed: {exc}") from exc
    finally:
        if temp_path is not None:
            temp_path.unlink(missing_ok=True)
        _release_migration_lock(lock)


def _atomic_copy_regular_file(source: Path, destination: Path) -> None:
    if not source.is_file() or source.is_symlink():
        raise RuntimeMigrationError(f"Unsafe migration source: {source}")
    fd, raw_path = tempfile.mkstemp(prefix=f".{destination.name}.", dir=destination.parent)
    os.close(fd)
    temp_path = Path(raw_path)
    try:
        shutil.copyfile(source, temp_path)
        os.replace(temp_path, destination)
    finally:
        temp_path.unlink(missing_ok=True)


def _release_migration_lock(handle) -> None:
    try:
        if os.name == "nt":
            import msvcrt
            msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
        else:
            import fcntl
            fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
    finally:
        handle.close()


def bootstrap_runtime_storage() -> RuntimeMigrationResult:
    """Explicitly initialize user-owned runtime storage during application startup."""
    return migrate_legacy_runtime_data(_DEFAULT_RESOLVER)


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
