"""Migration 064 reviewed schema-admission contract (disposable DBs only)."""

from __future__ import annotations

import sqlite3
from pathlib import Path

from printer_v1.db import migrate as migration_runner
from printer_v1.operator_cli import proof_db_schema_readiness as schema
from printer_v1.operator_cli import schema_admission_coherence as coherence

MIGRATION_063 = "063_four_token_zero_attempt_terminal_provenance.sql"
MIGRATION_064 = "064_four_token_started_lifecycle_zero_attempt_provenance.sql"
TABLE = "printer_four_token_started_lifecycle_zero_attempt_terminal_provenance"
TRIGGERS = {
    "printer_four_token_started_lifecycle_zero_attempt_provenance_exact_shape",
    "printer_four_token_started_lifecycle_zero_attempt_provenance_immutable_update",
    "printer_four_token_started_lifecycle_zero_attempt_provenance_immutable_delete",
    "printer_pre_admission_attempt_forbids_started_lifecycle_zero_attempt_provenance",
    "printer_pre_lifecycle_provenance_forbids_started_lifecycle_zero_attempt_provenance",
    "printer_planned_lifecycle_provenance_forbids_started_lifecycle_zero_attempt_provenance",
}


def _full(tmp_path: Path) -> Path:
    db = tmp_path / "full64.sqlite3"
    migration_runner.apply_migrations(db)
    return db


def _through_62(db: Path) -> None:
    connection = sqlite3.connect(db)
    try:
        connection.execute("PRAGMA foreign_keys=ON")
        connection.execute(
            "CREATE TABLE IF NOT EXISTS printer_schema_migrations ("
            "version TEXT PRIMARY KEY, "
            "applied_at TEXT NOT NULL DEFAULT (datetime('now')))"
        )
        for migration in sorted(migration_runner.MIGRATIONS_DIR.glob("*.sql")):
            if int(migration.name[:3]) > 62:
                continue
            connection.executescript(migration.read_text(encoding="utf-8"))
            connection.execute(
                "INSERT INTO printer_schema_migrations(version) VALUES (?)",
                (migration.name,),
            )
        connection.commit()
    finally:
        connection.close()


def test_reviewed_pin_matches_canonical_64_head() -> None:
    names = list(migration_runner.canonical_migration_names())
    assert len(names) == 64
    assert names[-1] == MIGRATION_064
    assert coherence.REQUIRED_MIGRATION_COUNT == 64
    assert coherence.REQUIRED_MIGRATION_HEAD == MIGRATION_064


def test_064_objects_are_registered_in_runtime_schema_contract() -> None:
    assert schema.MIGRATION_064_REQUIRED_TABLES == frozenset({TABLE})
    assert schema.MIGRATION_064_REQUIRED_TRIGGERS == frozenset(TRIGGERS)
    assert schema.MIGRATION_064_REQUIRED_INDEXES == frozenset()
    assert set(schema.REQUIRED_TABLE_COLUMNS[TABLE]) == {
        "campaign_id", "campaign_run_id", "authoritative_factory_run_id",
        "cycle_id", "cycle_ordinal", "proposed_cycle_ordinal",
        "terminal_phase", "first_terminal_cause", "recorded_at",
    }


def test_fully_migrated_64_db_is_schema_ready(tmp_path: Path) -> None:
    db = _full(tmp_path)
    result = coherence.evaluate_schema_admission_coherence(
        db_path=db, expected_target=db
    )
    assert result.admission_schema_ready is True, result.summary()
    assert result.migration_063_objects_ready is True
    assert result.migration_064_objects_ready is True
    assert result.blocker_codes == ()


def test_62_prefix_is_fail_closed_against_64_contract(tmp_path: Path) -> None:
    db = tmp_path / "through62.sqlite3"
    _through_62(db)
    result = coherence.evaluate_schema_admission_coherence(
        db_path=db, expected_target=db
    )
    assert result.admission_schema_ready is False
    assert result.applied_count == 62
    assert "migration_count_mismatch" in result.blocker_codes
    assert "migration_head_mismatch" in result.blocker_codes
    assert result.migration_063_objects_ready is False
    assert result.migration_064_objects_ready is False


def test_missing_064_table_is_fail_closed(tmp_path: Path) -> None:
    db = _full(tmp_path)
    connection = sqlite3.connect(db)
    try:
        connection.execute("PRAGMA foreign_keys=OFF")
        connection.execute(f"DROP TABLE {TABLE}")
        connection.commit()
    finally:
        connection.close()
    result = coherence.evaluate_schema_admission_coherence(
        db_path=db, expected_target=db
    )
    assert result.admission_schema_ready is False
    assert result.migration_064_objects_ready is False
    assert "required_schema_object_missing" in result.blocker_codes


def test_missing_064_trigger_is_fail_closed(tmp_path: Path) -> None:
    db = _full(tmp_path)
    trigger = "printer_four_token_started_lifecycle_zero_attempt_provenance_exact_shape"
    connection = sqlite3.connect(db)
    try:
        connection.execute(f"DROP TRIGGER {trigger}")
        connection.commit()
    finally:
        connection.close()
    result = coherence.evaluate_schema_admission_coherence(
        db_path=db, expected_target=db
    )
    assert result.admission_schema_ready is False
    assert result.migration_064_objects_ready is False
    assert "required_schema_object_missing" in result.blocker_codes
