"""Disposable contract for migration-only one-shot authorization."""

from datetime import datetime, timezone
import sqlite3
from pathlib import Path
import json
import os
import inspect
import subprocess

import pytest

from printer_v1.db.migrate import apply_exact_migration
from printer_v1.operator_cli.migration_one_shot_authorization import (
    MigrationAuthorizationError,
    consume_and_apply_migration_authorization,
    prepare_migration_authorization,
    review_migration_authorization,
)


def _through_063(path) -> None:
    from printer_v1.db.migrate import MIGRATIONS_DIR, canonical_migration_names

    connection = sqlite3.connect(path)
    try:
        connection.execute(
            "CREATE TABLE printer_schema_migrations (version TEXT PRIMARY KEY, "
            "applied_at TEXT NOT NULL DEFAULT (datetime('now')))"
        )
        for name in canonical_migration_names()[:63]:
            connection.executescript((MIGRATIONS_DIR / name).read_text())
            connection.execute(
                "INSERT INTO printer_schema_migrations(version) VALUES (?)", (name,)
            )
        connection.commit()
    finally:
        connection.close()


def _prepared(tmp_path, monkeypatch):
    from printer_v1.operator_cli import migration_one_shot_authorization as auth
    db = tmp_path / "through-063.sqlite3"; _through_063(db)
    head = subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip()
    git = {"branch": "fixture-branch", "head": head, "remote_head": head, "tracked_clean": True}
    monkeypatch.setattr(auth, "_live_git_facts", lambda root: dict(git))
    monkeypatch.setattr(auth, "active_printer_runtime_processes", lambda path: ())
    monkeypatch.setattr(auth, "DEFAULT_PACKAGE_ROOT", tmp_path / "packages")
    monkeypatch.setattr(auth, "DEFAULT_MARKER_ROOT", tmp_path / "markers")
    monkeypatch.setattr(auth, "DEFAULT_TERMINAL_ROOT", tmp_path / "terminal")
    now = datetime.now(timezone.utc); repository = Path(__file__).resolve().parents[1]
    prepared = prepare_migration_authorization(
        repository_root=repository, database_path=db,
        target_migration="064_four_token_started_lifecycle_zero_attempt_provenance.sql",
        authorization_id="FIXTURE_MIGRATION_064_AUTH",
        authorized_at=now.isoformat(), validity_seconds=60,
        prior_authorizations_non_reusable=("V2_9_8B_FOUR_TOKEN_STD4H_AUTH_20260913T220119Z_eb53caac", "V2_9_8B_MIGRATION_063_AUTH_20260913T203954Z_5f3a8c1d"), now=now,
    )
    return auth, db, repository, now, prepared, git


def test_migration_only_authorization_surface_exists() -> None:
    """The migration authority is separate from every runtime authority."""
    assert callable(apply_exact_migration)
    assert callable(prepare_migration_authorization)
    assert callable(review_migration_authorization)
    assert callable(consume_and_apply_migration_authorization)


def test_disposable_064_prepare_review_consume_applies_once(tmp_path, monkeypatch) -> None:
    """Marker-first migration-only authority applies exactly canonical 064 once."""
    from printer_v1.operator_cli import migration_one_shot_authorization as auth

    auth, db, repository, now, prepared, _git = _prepared(tmp_path, monkeypatch)
    review = review_migration_authorization(
        repository_root=repository, database_path=db,
        authorization_file=prepared["authorization_file"],
        authorization_sha256=prepared["authorization_sha256"], now=now,
    )
    assert review["consumed"] is False
    assert not (tmp_path / "markers" / "FIXTURE_MIGRATION_064_AUTH").exists()
    result = consume_and_apply_migration_authorization(
        repository_root=repository, database_path=db,
        authorization_file=prepared["authorization_file"],
        authorization_sha256=prepared["authorization_sha256"],
        operator_approved=True, now=now,
    )
    assert result["applied_migrations"] == ["064_four_token_started_lifecycle_zero_attempt_provenance.sql"]
    assert (tmp_path / "markers" / "FIXTURE_MIGRATION_064_AUTH" / "migration_application_marker.json").is_file()
    connection = sqlite3.connect(db)
    try:
        assert connection.execute("SELECT COUNT(*) FROM printer_schema_migrations").fetchone()[0] == 64
        assert connection.execute("SELECT version FROM printer_schema_migrations ORDER BY rowid DESC LIMIT 1").fetchone()[0] == "064_four_token_started_lifecycle_zero_attempt_provenance.sql"
        assert connection.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='printer_four_token_started_lifecycle_zero_attempt_terminal_provenance'").fetchone()
        assert connection.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
        assert connection.execute("PRAGMA foreign_key_check").fetchall() == []
    finally:
        connection.close()
    with pytest.raises(MigrationAuthorizationError):
        consume_and_apply_migration_authorization(
            repository_root=repository, database_path=db,
            authorization_file=prepared["authorization_file"],
            authorization_sha256=prepared["authorization_sha256"],
            operator_approved=True, now=now,
        )


def test_prepare_blocks_dirty_git_and_sidecar_and_live_runtime(tmp_path, monkeypatch) -> None:
    from printer_v1.operator_cli import migration_one_shot_authorization as auth
    db = tmp_path / "db.sqlite3"; _through_063(db); repository = Path(__file__).resolve().parents[1]
    clean = {"branch": "fixture", "head": "a" * 40, "remote_head": "a" * 40, "tracked_clean": False}
    monkeypatch.setattr(auth, "_live_git_facts", lambda root: dict(clean))
    monkeypatch.setattr(auth, "active_printer_runtime_processes", lambda path: ())
    with pytest.raises(MigrationAuthorizationError):
        prepare_migration_authorization(repository_root=repository, database_path=db, target_migration="064_four_token_started_lifecycle_zero_attempt_provenance.sql", authorization_id="DIRTY", authorized_at=datetime.now(timezone.utc).isoformat(), validity_seconds=60, prior_authorizations_non_reusable=())
    clean["tracked_clean"] = True
    (Path(f"{db}-wal")).write_text("not a real sidecar")
    with pytest.raises(MigrationAuthorizationError):
        prepare_migration_authorization(repository_root=repository, database_path=db, target_migration="064_four_token_started_lifecycle_zero_attempt_provenance.sql", authorization_id="SIDECAR", authorized_at=datetime.now(timezone.utc).isoformat(), validity_seconds=60, prior_authorizations_non_reusable=())
    Path(f"{db}-wal").unlink()
    monkeypatch.setattr(auth, "active_printer_runtime_processes", lambda path: (123,))
    with pytest.raises(MigrationAuthorizationError):
        prepare_migration_authorization(repository_root=repository, database_path=db, target_migration="064_four_token_started_lifecycle_zero_attempt_provenance.sql", authorization_id="PID", authorized_at=datetime.now(timezone.utc).isoformat(), validity_seconds=60, prior_authorizations_non_reusable=())


def test_review_blocks_binding_target_expiry_and_runtime_cross_authority(tmp_path, monkeypatch) -> None:
    auth, db, repository, now, prepared, git = _prepared(tmp_path, monkeypatch)
    git["head"] = "b" * 40
    with pytest.raises(MigrationAuthorizationError):
        review_migration_authorization(repository_root=repository, database_path=db, authorization_file=prepared["authorization_file"], authorization_sha256=prepared["authorization_sha256"], now=now)
    git["head"] = "a" * 40
    stale = now.replace(year=now.year - 1)
    with pytest.raises(MigrationAuthorizationError):
        review_migration_authorization(repository_root=repository, database_path=db, authorization_file=prepared["authorization_file"], authorization_sha256=prepared["authorization_sha256"], now=stale)
    from printer_v1.operator_cli.four_token_standard_four_hour_one_shot_wrapper import validate_four_token_standard_four_hour_authorization_document
    with pytest.raises(Exception):
        validate_four_token_standard_four_hour_authorization_document(json.loads(Path(prepared["authorization_file"]).read_text()))


def test_exact_target_never_skips_or_applies_a_second_migration(tmp_path) -> None:
    from printer_v1.db.migrate import MIGRATIONS_DIR, canonical_migration_names
    db = tmp_path / "through-062.sqlite3"; connection = sqlite3.connect(db)
    try:
        connection.execute("CREATE TABLE printer_schema_migrations (version TEXT PRIMARY KEY)")
        for name in canonical_migration_names()[:62]:
            connection.executescript((MIGRATIONS_DIR / name).read_text())
            connection.execute("INSERT INTO printer_schema_migrations(version) VALUES (?)", (name,))
        connection.commit()
    finally: connection.close()
    with pytest.raises(RuntimeError):
        apply_exact_migration(db, "064_four_token_started_lifecycle_zero_attempt_provenance.sql")
    connection = sqlite3.connect(db)
    try: assert connection.execute("SELECT COUNT(*) FROM printer_schema_migrations").fetchone()[0] == 62
    finally: connection.close()


def test_marker_remains_consumed_when_application_or_terminal_evidence_fails(tmp_path, monkeypatch) -> None:
    auth, db, repository, now, prepared, _git = _prepared(tmp_path, monkeypatch)
    monkeypatch.setattr(auth, "apply_exact_migration", lambda *args, **kwargs: (_ for _ in ()).throw(RuntimeError("forced SQL failure")))
    with pytest.raises(MigrationAuthorizationError):
        consume_and_apply_migration_authorization(repository_root=repository, database_path=db, authorization_file=prepared["authorization_file"], authorization_sha256=prepared["authorization_sha256"], operator_approved=True, now=now)


def test_terminal_evidence_failure_never_reopens_consumed_marker(tmp_path, monkeypatch) -> None:
    auth, db, repository, now, prepared, _git = _prepared(tmp_path, monkeypatch)
    monkeypatch.setattr(auth, "apply_exact_migration", lambda *args, **kwargs: (_ for _ in ()).throw(RuntimeError("forced SQL failure")))
    monkeypatch.setattr(auth, "_write_terminal", lambda **kwargs: (_ for _ in ()).throw(OSError("forced terminal failure")))
    with pytest.raises(OSError):
        consume_and_apply_migration_authorization(repository_root=repository, database_path=db, authorization_file=prepared["authorization_file"], authorization_sha256=prepared["authorization_sha256"], operator_approved=True, now=now)
    assert (tmp_path / "markers" / "FIXTURE_MIGRATION_064_AUTH" / "migration_application_marker.json").is_file()
    marker = tmp_path / "markers" / "FIXTURE_MIGRATION_064_AUTH" / "migration_application_marker.json"
    assert marker.is_file()
    with pytest.raises(MigrationAuthorizationError):
        consume_and_apply_migration_authorization(repository_root=repository, database_path=db, authorization_file=prepared["authorization_file"], authorization_sha256=prepared["authorization_sha256"], operator_approved=True, now=now)


def test_failed_publication_leaves_no_unfinalized_authorization_package(tmp_path, monkeypatch) -> None:
    from printer_v1.operator_cli import migration_one_shot_authorization as auth
    db = tmp_path / "through-063.sqlite3"; _through_063(db)
    head = subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip()
    git = {"branch": "fixture", "head": head, "remote_head": head, "tracked_clean": True}
    monkeypatch.setattr(auth, "_live_git_facts", lambda root: dict(git))
    monkeypatch.setattr(auth, "active_printer_runtime_processes", lambda path: ())
    monkeypatch.setattr(auth, "DEFAULT_PACKAGE_ROOT", tmp_path / "packages")
    monkeypatch.setattr(auth, "_write_exclusive", lambda *args: (_ for _ in ()).throw(OSError("forced publication failure")))
    with pytest.raises(OSError):
        prepare_migration_authorization(repository_root=Path(__file__).resolve().parents[1], database_path=db, target_migration="064_four_token_started_lifecycle_zero_attempt_provenance.sql", authorization_id="UNPUBLISHED", authorized_at=datetime.now(timezone.utc).isoformat(), validity_seconds=60, prior_authorizations_non_reusable=())
    assert not (tmp_path / "packages" / "UNPUBLISHED").exists()


def test_production_consumption_cannot_select_an_alternate_marker_namespace() -> None:
    assert "marker_root" not in inspect.signature(
        consume_and_apply_migration_authorization
    ).parameters


def test_failed_consumption_cannot_be_redirected_to_an_alternate_root(tmp_path, monkeypatch) -> None:
    auth, db, repository, now, prepared, _git = _prepared(tmp_path, monkeypatch)
    monkeypatch.setattr(auth, "apply_exact_migration", lambda *args, **kwargs: (_ for _ in ()).throw(RuntimeError("forced SQL failure")))
    with pytest.raises(MigrationAuthorizationError):
        consume_and_apply_migration_authorization(repository_root=repository, database_path=db, authorization_file=prepared["authorization_file"], authorization_sha256=prepared["authorization_sha256"], operator_approved=True, now=now)
    with pytest.raises(TypeError):
        consume_and_apply_migration_authorization(repository_root=repository, database_path=db, authorization_file=prepared["authorization_file"], authorization_sha256=prepared["authorization_sha256"], marker_root=tmp_path / "alternate", operator_approved=True, now=now)


def test_marker_publication_failure_tombstones_namespace_before_sql(tmp_path, monkeypatch) -> None:
    auth, db, repository, now, prepared, _git = _prepared(tmp_path, monkeypatch)
    monkeypatch.setattr(auth, "_write_exclusive", lambda *args: (_ for _ in ()).throw(OSError("forced marker write failure")))
    with pytest.raises(MigrationAuthorizationError, match="tombstoned"):
        consume_and_apply_migration_authorization(repository_root=repository, database_path=db, authorization_file=prepared["authorization_file"], authorization_sha256=prepared["authorization_sha256"], operator_approved=True, now=now)
    assert (tmp_path / "markers" / "FIXTURE_MIGRATION_064_AUTH").is_dir()
    with pytest.raises(MigrationAuthorizationError, match="consumed"):
        review_migration_authorization(repository_root=repository, database_path=db, authorization_file=prepared["authorization_file"], authorization_sha256=prepared["authorization_sha256"], now=now)


def test_exact_migration_executes_the_single_verified_sql_read(tmp_path, monkeypatch) -> None:
    """A legacy second migration-file read must be impossible after hashing."""
    from printer_v1.db import migrate

    migrations = tmp_path / "migrations"; migrations.mkdir()
    first = migrations / "001_foundation.sql"; first.write_text("CREATE TABLE x (id INTEGER);\n")
    target = migrations / "002_target.sql"; target.write_text("CREATE TABLE verified (id INTEGER);\n")
    db = tmp_path / "db.sqlite3"; connection = sqlite3.connect(db)
    try:
        connection.execute("CREATE TABLE printer_schema_migrations (version TEXT PRIMARY KEY)")
        connection.executescript(first.read_text())
        connection.execute("INSERT INTO printer_schema_migrations VALUES ('001_foundation.sql')")
        connection.commit()
    finally:
        connection.close()
    monkeypatch.setattr(migrate, "MIGRATIONS_DIR", migrations)
    original = Path.read_text
    def forbid_second_read(path, *args, **kwargs):
        if path == target:
            raise AssertionError("migration SQL was read a second time")
        return original(path, *args, **kwargs)
    monkeypatch.setattr(Path, "read_text", forbid_second_read)
    digest = __import__("hashlib").sha256(target.read_bytes()).hexdigest()
    migrate.apply_exact_migration(db, "002_target.sql", expected_sha256=digest)
    connection = sqlite3.connect(db)
    try:
        assert connection.execute("SELECT 1 FROM sqlite_master WHERE name='verified'").fetchone()
    finally:
        connection.close()


def test_target_facts_reject_untracked_migration_catalogue_entries(tmp_path, monkeypatch) -> None:
    from printer_v1.operator_cli import migration_one_shot_authorization as auth

    monkeypatch.setattr(auth, "_migration_catalogue_is_clean", lambda root: False)
    with pytest.raises(MigrationAuthorizationError):
        auth._target_facts(
            "064_four_token_started_lifecycle_zero_attempt_provenance.sql",
            repository_root=Path(__file__).resolve().parents[1], head="a" * 40,
        )
