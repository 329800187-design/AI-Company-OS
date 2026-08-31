import sqlite3
import threading
from pathlib import Path

from backend.runtime_paths import (
    RuntimePathResolver,
    migrate_legacy_runtime_data,
)


def test_fresh_install_uses_new_runtime_directory(tmp_path):
    resolver = RuntimePathResolver(tmp_path / "new", tmp_path / "legacy")

    result = migrate_legacy_runtime_data(resolver)

    assert result.action == "fresh"
    assert result.database_path == tmp_path / "new" / "company_os.db"
    assert result.database_path.parent.is_dir()


def test_legacy_only_is_copied_without_deleting_source(tmp_path):
    import sqlite3
    legacy = tmp_path / "legacy"
    new = tmp_path / "new"
    legacy.mkdir()
    with sqlite3.connect(legacy / "company_os.db") as db:
        db.execute("CREATE TABLE marker (value TEXT)")
        db.execute("INSERT INTO marker VALUES ('legacy-db')")
        db.commit()
    resolver = RuntimePathResolver(new, legacy)

    result = migrate_legacy_runtime_data(resolver)

    assert result.action == "migrated"
    with sqlite3.connect(new / "company_os.db") as db:
        assert db.execute("SELECT value FROM marker").fetchone()[0] == "legacy-db"
    assert (legacy / "company_os.db").exists()


def test_new_only_wins_and_rerun_is_idempotent(tmp_path):
    new = tmp_path / "new"
    new.mkdir()
    (new / "company_os.db").write_bytes(b"new-db")
    resolver = RuntimePathResolver(new, tmp_path / "legacy")

    first = migrate_legacy_runtime_data(resolver)
    second = migrate_legacy_runtime_data(resolver)

    assert first.action == "new_existing"
    assert second.action == "new_existing"
    assert (new / "company_os.db").read_bytes() == b"new-db"


def test_both_locations_never_overwrite_new_database(tmp_path):
    legacy = tmp_path / "legacy"
    new = tmp_path / "new"
    legacy.mkdir()
    new.mkdir()
    (legacy / "company_os.db").write_bytes(b"legacy-db")
    (new / "company_os.db").write_bytes(b"new-db")
    resolver = RuntimePathResolver(new, legacy)

    result = migrate_legacy_runtime_data(resolver)

    assert result.action == "both_existing"
    assert (new / "company_os.db").read_bytes() == b"new-db"


def test_legacy_agent_registry_is_migrated_with_runtime_state(tmp_path):
    legacy = tmp_path / "legacy"
    new = tmp_path / "new"
    (legacy / "agent_registry").mkdir(parents=True)
    source = legacy / "agent_registry" / "enabled_agents.json"
    source.write_text('{"research": true}', encoding="utf-8")
    resolver = RuntimePathResolver(new, legacy)

    migrate_legacy_runtime_data(resolver)
    rerun = migrate_legacy_runtime_data(resolver)

    target = new / "agent_registry" / "enabled_agents.json"
    assert target.read_text(encoding="utf-8") == '{"research": true}'
    assert rerun.action == "fresh"
    assert source.exists()


def test_platform_directory_semantics(monkeypatch, tmp_path):
    resolver = RuntimePathResolver.from_platform(
        "Darwin", home=tmp_path, env={}
    )
    assert resolver.new_root == tmp_path / "Library/Application Support/AI Company OS"

    resolver = RuntimePathResolver.from_platform(
        "Linux", home=tmp_path, env={"XDG_DATA_HOME": str(tmp_path / "xdg")}
    )
    assert resolver.new_root == tmp_path / "xdg/ai-company-os"

    resolver = RuntimePathResolver.from_platform(
        "Windows", home=tmp_path, env={"APPDATA": str(tmp_path / "appdata")}
    )
    assert resolver.new_root == tmp_path / "appdata/AI Company OS"


def test_sqlite_migration_uses_valid_backup_and_preserves_wal_data(tmp_path):
    legacy = tmp_path / "legacy"
    legacy.mkdir()
    source = legacy / "company_os.db"
    with sqlite3.connect(source) as db:
        db.execute("PRAGMA journal_mode=WAL")
        db.execute("CREATE TABLE records (value TEXT)")
        db.execute("INSERT INTO records VALUES ('committed')")
        db.commit()

    resolver = RuntimePathResolver(tmp_path / "new", legacy)
    result = migrate_legacy_runtime_data(resolver)

    assert result.action == "migrated"
    with sqlite3.connect(result.database_path) as db:
        assert db.execute("PRAGMA quick_check").fetchone()[0] == "ok"
        assert db.execute("SELECT value FROM records").fetchone()[0] == "committed"
    assert source.exists()


def test_runtime_paths_import_does_not_migrate(monkeypatch, tmp_path):
    import importlib
    import backend.runtime_paths as runtime_paths

    legacy = tmp_path / "legacy"
    legacy.mkdir()
    (legacy / "company_os.db").write_bytes(b"legacy")
    monkeypatch.setenv("AI_COMPANY_OS_LEGACY_DATA", str(legacy))
    monkeypatch.setenv("AI_COMPANY_OS_USER_DATA", str(tmp_path / "new"))

    importlib.reload(runtime_paths)
    assert not (tmp_path / "new" / "company_os.db").exists()


def test_concurrent_migration_produces_one_valid_destination(tmp_path):
    legacy = tmp_path / "legacy"
    legacy.mkdir()
    source = legacy / "company_os.db"
    with sqlite3.connect(source) as db:
        db.execute("CREATE TABLE records (value TEXT)")
        db.execute("INSERT INTO records VALUES ('once')")
        db.commit()
    resolver = RuntimePathResolver(tmp_path / "new", legacy)
    results = []
    errors = []
    def migrate():
        try:
            results.append(migrate_legacy_runtime_data(resolver))
        except Exception as exc:
            errors.append(exc)
    threads = [threading.Thread(target=migrate) for _ in range(2)]
    for thread in threads: thread.start()
    for thread in threads: thread.join()
    assert not errors
    with sqlite3.connect(resolver.database_path) as db:
        assert db.execute("SELECT value FROM records").fetchone()[0] == "once"
    assert sum(result.action == "migrated" for result in results) == 1


def test_failed_backup_cleans_temp_and_can_rerun(monkeypatch, tmp_path):
    legacy = tmp_path / "legacy"
    legacy.mkdir()
    source = legacy / "company_os.db"
    with sqlite3.connect(source) as db:
        db.execute("CREATE TABLE records (value TEXT)")
        db.execute("INSERT INTO records VALUES ('recover')")
        db.commit()
    resolver = RuntimePathResolver(tmp_path / "new", legacy)
    import backend.runtime_paths as runtime_paths
    original = runtime_paths._backup_sqlite_database
    def fail_once(source_path, destination_path):
        runtime_paths._backup_sqlite_database = original
        raise RuntimeError("interrupted")
    monkeypatch.setattr(runtime_paths, "_backup_sqlite_database", fail_once)
    try:
        migrate_legacy_runtime_data(resolver)
    except RuntimeError:
        pass
    assert not resolver.database_path.exists()
    assert not list(resolver.new_root.glob(".company_os.*.db"))
    result = migrate_legacy_runtime_data(resolver)
    assert result.action == "migrated"
