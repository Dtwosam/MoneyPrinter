"""Focused proof for V2-9.8B post-Lane-4 schema/gate coherence.

Disposable databases only. No authorization, marker, campaign, provider,
Scheduler, or authoritative-DB mutation.
"""

from __future__ import annotations

import ast
import hashlib
import inspect
import re
import sqlite3
from pathlib import Path
import shutil
from unittest import mock

from printer_v1.db.migrate import apply_migrations, canonical_migration_names
from printer_v1.operator_cli.operational_memory_factory_command import (
    OperationalMemoryFactoryError,
)
from printer_v1.operator_cli import four_token_proof_zero_state_gate as gate
from printer_v1.operator_cli import git_provenance_authorization_manifest as git_auth
from printer_v1.operator_cli import operational_memory_factory_command as command
from printer_v1.operator_cli import pre_authorization_migration_ledger_guard as ledger_guard
from printer_v1.operator_cli import proof_db_schema_readiness as schema
from printer_v1.operator_cli import schema_admission_coherence as coherence
from printer_v1.operator_cli import standard_four_hour_one_shot_wrapper as standard_wrapper
from printer_v1.operator_cli import window_15m_one_shot_wrapper as window_wrapper
from printer_v1.operator_cli.four_token_operational_composition import LOCKED_WINDOWS
from printer_v1.operator_cli.proof_db_schema_readiness import (
    CANONICAL_PERSISTENT_DB,
    inspect_required_schema_objects,
    validate_runtime_schema_connection,
)


REPO_ROOT = Path(__file__).resolve().parents[1]
AUTHORITATIVE = Path(CANONICAL_PERSISTENT_DB).resolve()
MIGRATION_061 = "061_standard_4h_progression_fault_preservation.sql"
MIGRATION_060 = "060_pre_admission_frozen_tracking_lane_provenance.sql"
MIGRATION_059 = "059_pair_ready_parent_terminal_cancellation_transition.sql"
ATTEMPTS = "printer_memory_factory_standard_4h_progression_attempts"
TOKENS = "printer_memory_factory_standard_4h_progression_tokens"
ITEMS = "printer_pre_admission_discovery_attempt_items"
FIVE_COL_UNIQUE = (
    "progression_attempt_id",
    "campaign_id",
    "campaign_run_id",
    "cycle_id",
    "factory_run_id",
)


def _names_through(ordinal: int) -> list[str]:
    return [name for name in canonical_migration_names() if int(name[:3]) <= ordinal]


def _apply_named(db_path: Path, names: list[str]) -> None:
    connection = sqlite3.connect(db_path)
    try:
        connection.execute("PRAGMA foreign_keys = ON")
        connection.execute(
            "CREATE TABLE IF NOT EXISTS printer_schema_migrations ("
            "version TEXT PRIMARY KEY, "
            "applied_at TEXT NOT NULL DEFAULT (datetime('now')))"
        )
        applied = {
            str(row[0])
            for row in connection.execute(
                "SELECT version FROM printer_schema_migrations"
            )
        }
        for name in names:
            if name in applied:
                continue
            connection.executescript(
                (REPO_ROOT / "migrations" / name).read_text(encoding="utf-8")
            )
            connection.execute(
                "INSERT INTO printer_schema_migrations (version) VALUES (?)",
                (name,),
            )
        connection.commit()
    finally:
        connection.close()


def _evaluate(db_path: Path, *, migrations_dir=None, expected_target=None):
    return coherence.evaluate_schema_admission_coherence(
        db_path=db_path,
        migrations_dir=migrations_dir,
        expected_target=expected_target,
    )


def _full(tmp_path: Path) -> Path:
    db = tmp_path / "full61.sqlite3"
    apply_migrations(db)
    return db


def test_helper_pin_literals_match_catalogue_and_are_constants() -> None:
    names = list(canonical_migration_names())
    assert coherence.REQUIRED_MIGRATION_COUNT == 61
    assert coherence.REQUIRED_MIGRATION_HEAD == MIGRATION_061
    assert coherence.REQUIRED_MIGRATION_COUNT == len(names)
    assert coherence.REQUIRED_MIGRATION_HEAD == names[-1]
    tree = ast.parse(
        Path(coherence.__file__).read_text(encoding="utf-8")
    )
    found: dict[str, ast.expr] = {}
    for node in tree.body:
        if isinstance(node, ast.Assign) and len(node.targets) == 1:
            target = node.targets[0]
            if isinstance(target, ast.Name) and target.id in {
                "REQUIRED_MIGRATION_COUNT",
                "REQUIRED_MIGRATION_HEAD",
            }:
                found[target.id] = node.value
    assert isinstance(found["REQUIRED_MIGRATION_COUNT"], ast.Constant)
    assert found["REQUIRED_MIGRATION_COUNT"].value == 61
    assert isinstance(found["REQUIRED_MIGRATION_HEAD"], ast.Constant)
    source = Path(coherence.__file__).read_text(encoding="utf-8")
    assert "REQUIRED_MIGRATION_COUNT = canonical_migration_count()" not in source


def test_a_catalogue61_pin61_db59_blocks(tmp_path) -> None:
    db = tmp_path / "db59.sqlite3"
    _apply_named(db, _names_through(59))
    result = _evaluate(db, expected_target=db)
    assert result.admission_schema_ready is False
    assert result.applied_count == 59
    assert result.applied_head == MIGRATION_059
    assert result.migration_060_objects_ready is False
    assert result.migration_061_objects_ready is False
    assert "migration_count_mismatch" in result.blocker_codes
    assert result.to_dict()["campaign_authorized"] is False
    assert result.to_dict()["application_marker_created"] is False
    assert result.to_dict()["cycle_3_unlocked"] is False


def test_b_catalogue_ahead_of_pin_is_schema_expectation_mismatch(tmp_path) -> None:
    catalog = tmp_path / "catalog"
    catalog.mkdir()
    for name in canonical_migration_names():
        shutil.copy2(REPO_ROOT / "migrations" / name, catalog / name)
    extra = catalog / "062_synthetic_coherence_probe.sql"
    extra.write_text("BEGIN IMMEDIATE;\nCOMMIT;\n", encoding="utf-8")
    db = tmp_path / "db61.sqlite3"
    apply_migrations(db)
    result = _evaluate(db, migrations_dir=catalog, expected_target=db)
    assert result.admission_schema_ready is False
    assert result.pin_matches_catalogue is False
    assert coherence.SCHEMA_EXPECTATION_MISMATCH in result.blocker_codes
    assert coherence.REQUIRED_MIGRATION_COUNT == 61


def test_c_db60_blocks(tmp_path) -> None:
    db = tmp_path / "db60.sqlite3"
    _apply_named(db, _names_through(60))
    result = _evaluate(db, expected_target=db)
    assert result.admission_schema_ready is False
    assert result.applied_count == 60
    assert result.migration_060_objects_ready is True
    assert result.migration_061_objects_ready is False
    assert result.partial_application is True


def test_d_ledger_61_missing_061_table_blocks(tmp_path) -> None:
    db = _full(tmp_path)
    connection = sqlite3.connect(db)
    try:
        connection.execute("PRAGMA foreign_keys=OFF")
        connection.execute(f"DROP TABLE {TOKENS}")
        connection.execute(f"DROP TABLE {ATTEMPTS}")
        connection.commit()
    finally:
        connection.close()
    result = _evaluate(db, expected_target=db)
    assert result.admission_schema_ready is False
    assert result.applied_count == 61
    assert result.migration_061_objects_ready is False
    assert "required_schema_object_missing" in result.blocker_codes


def test_e_objects_present_ledger_wrong_blocks(tmp_path) -> None:
    db = _full(tmp_path)
    connection = sqlite3.connect(db)
    try:
        connection.execute(
            "DELETE FROM printer_schema_migrations WHERE version=?",
            (MIGRATION_061,),
        )
        connection.commit()
    finally:
        connection.close()
    result = _evaluate(db, expected_target=db)
    assert result.admission_schema_ready is False
    assert result.applied_head == MIGRATION_060
    assert result.migration_061_objects_ready is True
    assert "partial_migration_application" in result.blocker_codes


def test_f_exact_disposable_61_with_matching_target_is_schema_ready_not_campaign(
    tmp_path,
) -> None:
    db = _full(tmp_path)
    result = _evaluate(db, expected_target=db)
    assert result.admission_schema_ready is True
    assert result.migration_060_objects_ready is True
    assert result.migration_061_objects_ready is True
    payload = result.to_dict()
    assert payload["campaign_authorized"] is False
    assert payload["application_marker_created"] is False
    assert payload["cycle_3_unlocked"] is False
    assert result.blocker_codes == ()


def test_g_same_61_db_with_production_target_default_is_wrong_target(tmp_path) -> None:
    db = _full(tmp_path)
    result = _evaluate(db, expected_target=None)
    assert result.admission_schema_ready is False
    assert result.db_target_matches_authoritative is False
    assert "db_target_mismatch" in result.blocker_codes
    assert Path(result.expected_target_path).resolve() == AUTHORITATIVE


def test_h_missing_060_column_blocks(tmp_path) -> None:
    db = _full(tmp_path)
    connection = sqlite3.connect(db)
    try:
        connection.execute(
            "DROP TRIGGER printer_pre_admission_item_frozen_lane_complete"
        )
        connection.execute(f"ALTER TABLE {ITEMS} DROP COLUMN frozen_tracking_lane")
        connection.execute(
            "CREATE TRIGGER printer_pre_admission_item_frozen_lane_complete "
            f"BEFORE INSERT ON {ITEMS} BEGIN SELECT 1; END;"
        )
        connection.commit()
    finally:
        connection.close()
    result = _evaluate(db, expected_target=db)
    assert result.admission_schema_ready is False
    assert result.migration_060_objects_ready is False
    assert result.migration_061_objects_ready is True


def test_h_missing_060_trigger_blocks(tmp_path) -> None:
    db = _full(tmp_path)
    connection = sqlite3.connect(db)
    try:
        connection.execute(
            "DROP TRIGGER printer_pre_admission_item_frozen_lane_complete"
        )
        connection.commit()
    finally:
        connection.close()
    result = _evaluate(db, expected_target=db)
    assert result.admission_schema_ready is False
    assert result.migration_060_objects_ready is False


def test_h_missing_061_successor_index_blocks(tmp_path) -> None:
    db = _full(tmp_path)
    connection = sqlite3.connect(db)
    try:
        connection.execute("DROP INDEX idx_standard_4h_progression_successor")
        connection.commit()
    finally:
        connection.close()
    result = _evaluate(db, expected_target=db)
    assert result.admission_schema_ready is False
    assert result.migration_061_objects_ready is False
    assert result.migration_060_objects_ready is True


def test_h_missing_061_immutability_trigger_blocks(tmp_path) -> None:
    db = _full(tmp_path)
    connection = sqlite3.connect(db)
    try:
        connection.execute(
            "DROP TRIGGER printer_standard_4h_progression_attempt_identity_immutable"
        )
        connection.commit()
    finally:
        connection.close()
    result = _evaluate(db, expected_target=db)
    assert result.admission_schema_ready is False
    assert result.migration_061_objects_ready is False


def test_h_missing_061_composite_unique_blocks(tmp_path) -> None:
    db = _full(tmp_path)
    connection = sqlite3.connect(db)
    try:
        row = connection.execute(
            "SELECT sql FROM sqlite_master WHERE type='table' AND name=?",
            (ATTEMPTS,),
        ).fetchone()
        rebuilt = re.sub(
            r",\s*UNIQUE\s*\(\s*progression_attempt_id,\s*campaign_id,\s*"
            r"campaign_run_id,\s*cycle_id,\s*factory_run_id\s*\)",
            "",
            str(row[0]),
            count=1,
            flags=re.IGNORECASE,
        )
        connection.execute("PRAGMA foreign_keys=OFF")
        connection.execute(f"ALTER TABLE {ATTEMPTS} RENAME TO {ATTEMPTS}_old")
        connection.executescript(rebuilt.replace(ATTEMPTS, ATTEMPTS, 1) + ";")
        connection.execute(
            f"INSERT INTO {ATTEMPTS} SELECT * FROM {ATTEMPTS}_old"
        )
        connection.execute(f"DROP TABLE {ATTEMPTS}_old")
        connection.commit()
    finally:
        connection.close()
    result = _evaluate(db, expected_target=db)
    assert result.admission_schema_ready is False
    assert result.migration_061_objects_ready is False
    connection = sqlite3.connect(db)
    try:
        uniques = schema._unique_keys(connection, ATTEMPTS)
    finally:
        connection.close()
    assert FIVE_COL_UNIQUE not in uniques


def test_i_sister_dict_059_does_not_keyerror(tmp_path) -> None:
    db = tmp_path / "schema59.sqlite3"
    _apply_named(db, _names_through(59))
    connection = sqlite3.connect(db)
    try:
        report = inspect_required_schema_objects(connection)
        runtime = validate_runtime_schema_connection(
            connection, raise_on_error=False
        )
    finally:
        connection.close()
    assert isinstance(report["issues"], list)
    assert report["issues"]
    assert runtime["runtime_ready"] is False
    assert schema.REQUIRED_NOT_NULL_COLUMNS[ITEMS] == set()
    assert schema.REQUIRED_UNIQUE_KEYS[ITEMS] == set()
    source = Path(schema.__file__).read_text(encoding="utf-8")
    assert "inspect_required_schema_objects" in source
    assert "REQUIRED_NOT_NULL_COLUMNS.get(table, set())" in source


def test_j_admission_paths_reach_helper() -> None:
    assert "evaluate_schema_admission_coherence" in Path(gate.__file__).read_text()
    assert "evaluate_schema_admission_coherence" in Path(command.__file__).read_text()
    assert "evaluate_schema_admission_coherence" in Path(
        ledger_guard.__file__
    ).read_text()
    window_src = Path(window_wrapper.__file__).read_text()
    assert "migration_ledger_guard" in window_src
    assert "apply_authorization_once" in window_src
    standard_src = Path(standard_wrapper.__file__).read_text()
    assert "migration_ledger_guard" in standard_src
    preflight_src = Path(command.__file__).read_text()
    assert "def build_activation_preflight" in preflight_src
    assert preflight_src.index("evaluate_schema_admission_coherence") > preflight_src.index(
        "def build_activation_preflight"
    )


def test_k_consumed_authorization_binding_unusable_against_61(tmp_path) -> None:
    db = _full(tmp_path)
    info = db.stat()
    binding = {
        "path": str(AUTHORITATIVE),
        "sha256": "fbec54fca9fd8ec2e6dd95cf3dd3066d680cc8717b56ef3a0a0e213b0531a100",
        "size": 1,
        "inode": 0,
        "mtime_ns": 0,
        "migration_count": 59,
        "migration_head": MIGRATION_059,
    }
    result = ledger_guard.evaluate_migration_ledger_drift(
        mode="review",
        db_path=db,
        package_binding=binding,
    )
    assert result.status == "BLOCKED"
    assert "package_binding_dishonest" in result.blocker_codes
    assert result.to_dict()["authorization_created"] is False


def test_l_four_token_current_git_evidence_is_exact_061() -> None:
    for profile in (
        git_auth.FOUR_TOKEN_PROOF_AUTHORIZATION_PROFILE,
        git_auth.FOUR_TOKEN_STANDARD_FOUR_HOUR_AUTHORIZATION_PROFILE,
    ):
        assert profile.migration_package_kind == "MIGRATION_061_EVIDENCE"
        assert profile.migration_package_root == git_auth.MIGRATION_061_PACKAGE_ROOT
        assert profile.current_migration_execution_id == (
            git_auth.FOUR_TOKEN_CURRENT_MIGRATION_061_EXECUTION_ID
        )
        assert profile.current_migration_expected_file_count == 5


def test_m_cycle3_and_long_window_locks_unchanged() -> None:
    assert LOCKED_WINDOWS == ("WINDOW_12H", "WINDOW_24H")
    assert command.LOCKED_WINDOWS == ("WINDOW_1H", "WINDOW_4H", "WINDOW_12H", "WINDOW_24H")
    sql = (REPO_ROOT / "migrations" / MIGRATION_061).read_text(encoding="utf-8")
    assert "slot_ordinal INTEGER NOT NULL CHECK (slot_ordinal IN (1, 2))" in sql
    result = coherence.SchemaAdmissionCoherenceResult(
        catalogue_valid=True,
        catalogue_count=61,
        catalogue_head=MIGRATION_061,
        catalogue_digest=None,
        expected_count=61,
        expected_head=MIGRATION_061,
        pin_matches_catalogue=True,
        db_target_path=str(AUTHORITATIVE),
        expected_target_path=str(AUTHORITATIVE),
        db_target_matches_authoritative=True,
        db_readable=True,
        sidecars=(),
        integrity="ok",
        foreign_key_violations=0,
        applied_count=61,
        applied_head=MIGRATION_061,
        applied_ledger=(),
        ledger_digest=None,
        ledger_matches_catalogue=True,
        ledger_is_canonical_prefix=True,
        migration_060_objects_ready=True,
        migration_061_objects_ready=True,
        partial_application=False,
        admission_schema_ready=True,
        blocker_codes=(),
    )
    assert result.to_dict()["cycle_3_unlocked"] is False


def _package_binding(db: Path) -> dict[str, object]:
    info = db.stat()
    return {
        "path": str(db.resolve()),
        "sha256": hashlib.sha256(db.read_bytes()).hexdigest(),
        "size": info.st_size,
        "inode": info.st_ino,
        "mtime_ns": info.st_mtime_ns,
        "migration_count": 61,
        "migration_head": MIGRATION_061,
    }


def test_a_preflight_wrong_target_blocks_schema_admission(tmp_path) -> None:
    db = _full(tmp_path)
    with mock.patch.object(command, "AUTHORITATIVE_DB", db):
        try:
            command.build_activation_preflight(db_path=db)
        except OperationalMemoryFactoryError as exc:
            message = str(exc)
        else:
            raise AssertionError("preflight continued against a wrong-target 061 DB")
    assert "gate=schema_admission_coherence" in message
    assert "db_target_mismatch" in message


def test_b_prepare_wrong_target_blocks(tmp_path) -> None:
    db = _full(tmp_path)
    result = ledger_guard.evaluate_migration_ledger_drift(mode="prepare", db_path=db)
    assert result.status == "BLOCKED"
    assert "db_target_mismatch" in result.blocker_codes
    assert result.to_dict()["authorization_created"] is False


def test_c_review_wrong_target_cannot_claim_schema_honesty(tmp_path) -> None:
    db = _full(tmp_path)
    result = ledger_guard.evaluate_migration_ledger_drift(
        mode="review",
        db_path=db,
        package_binding=_package_binding(db),
    )
    assert result.status == "BLOCKED"
    assert "db_target_mismatch" in result.blocker_codes
    assert result.to_dict()["authorization_created"] is False
    assert result.verdict != ledger_guard.PASS_VERDICT


def test_d_window_15m_inherited_guard_blocks_wrong_target(tmp_path) -> None:
    default = inspect.signature(window_wrapper.apply_authorization_once).parameters[
        "migration_ledger_guard"
    ].default
    assert default is ledger_guard.assert_migration_ledger_ready
    db = _full(tmp_path)
    try:
        default(mode="review", db_path=db, package_binding=_package_binding(db))
    except ledger_guard.MigrationLedgerDriftGuardError as exc:
        message = str(exc)
    else:
        raise AssertionError("WINDOW_15M inherited guard continued")
    assert "db_target_mismatch" in message


def test_e_standard_4h_inherited_guard_blocks_wrong_target(tmp_path) -> None:
    default = inspect.signature(standard_wrapper.apply_authorization_once).parameters[
        "migration_ledger_guard"
    ].default
    assert default is ledger_guard.assert_migration_ledger_ready
    db = _full(tmp_path)
    try:
        default(mode="review", db_path=db, package_binding=_package_binding(db))
    except ledger_guard.MigrationLedgerDriftGuardError as exc:
        message = str(exc)
    else:
        raise AssertionError("standard-4h inherited guard continued")
    assert "db_target_mismatch" in message


def test_f_canonical_target_opposite_passes_when_candidate_is_canonical(
    tmp_path,
) -> None:
    db = _full(tmp_path)
    with mock.patch.object(coherence, "CANONICAL_PERSISTENT_DB", db):
        with mock.patch.object(command, "AUTHORITATIVE_DB", db):
            preflight_blocked = None
            try:
                command.build_activation_preflight(db_path=db)
            except OperationalMemoryFactoryError as exc:
                preflight_blocked = str(exc)
            prepare = ledger_guard.evaluate_migration_ledger_drift(
                mode="prepare", db_path=db
            )
    assert prepare.status == "PASS", prepare.summary()
    assert "db_target_mismatch" not in prepare.blocker_codes
    if preflight_blocked is not None:
        assert "db_target_mismatch" not in preflight_blocked
        assert "gate=schema_admission_coherence" not in preflight_blocked


def test_production_callers_do_not_self_target() -> None:
    preflight = Path(command.__file__).read_text(encoding="utf-8")
    guard_src = Path(ledger_guard.__file__).read_text(encoding="utf-8")
    gate_src = Path(gate.__file__).read_text(encoding="utf-8")
    assert "expected_target=None" in preflight
    assert "expected_target=path" not in preflight
    assert "expected_target=None if db_path is None else target" not in guard_src
    assert "expected_target=None" in guard_src
    assert "expected_target=None" in gate_src


def test_no_authoritative_migration_writer_in_this_change() -> None:
    helper = Path(coherence.__file__).read_text(encoding="utf-8")
    gate_src = Path(gate.__file__).read_text(encoding="utf-8")
    assert "apply_migrations(" not in helper
    assert "apply_migrations(" not in gate_src
    assert "initialize_operator_db" not in helper
    assert "recover_exact_heartbeat_terminal_residue" not in helper


def test_authoritative_db_untouched_identity() -> None:
    assert AUTHORITATIVE.is_file()
    connection = sqlite3.connect(f"file:{AUTHORITATIVE.as_posix()}?mode=ro", uri=True)
    try:
        applied = [
            str(row[0])
            for row in connection.execute(
                "SELECT version FROM printer_schema_migrations ORDER BY version"
            )
        ]
        tables = {
            str(row[0])
            for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            )
        }
        cols = {
            str(row[1])
            for row in connection.execute(f"PRAGMA table_info('{ITEMS}')")
        }
    finally:
        connection.close()
    assert len(applied) == 59
    assert applied[-1] == MIGRATION_059
    assert ATTEMPTS not in tables
    assert "frozen_tracking_lane" not in cols
