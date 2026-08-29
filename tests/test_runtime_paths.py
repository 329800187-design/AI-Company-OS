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
    legacy = tmp_path / "legacy"
    new = tmp_path / "new"
    legacy.mkdir()
    (legacy / "company_os.db").write_bytes(b"legacy-db")
    resolver = RuntimePathResolver(new, legacy)

    result = migrate_legacy_runtime_data(resolver)

    assert result.action == "migrated"
    assert (new / "company_os.db").read_bytes() == b"legacy-db"
    assert (legacy / "company_os.db").read_bytes() == b"legacy-db"


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
