"""V2-9.1 isolated proof-DB schema preparation and validation.

This module never runs sources or scheduler work. It copies a persistent DB to
an isolated target, applies the canonical migration chain to that copy, validates
the V2-8.1 runtime ledger contract, and creates a backup only after validation.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import shutil
import sqlite3
from typing import Any, Iterable

from printer_v1.db import migrate as migration_runner


PROJECT_ROOT = Path(__file__).resolve().parents[3]
CANONICAL_PERSISTENT_DB = (PROJECT_ROOT / "data" / "printer_v1.sqlite3").resolve()
RUN_LEDGER_MIGRATION = "028_memory_factory_run_ledger.sql"

REQUIRED_TABLE_COLUMNS = {
    "printer_memory_factory_runs": {
        "id", "run_id", "run_status", "stop_reason", "window_kind", "db_mode",
        "config_hash", "config_json", "selection_seed", "selection_batch_id",
        "eligible_pool_size", "selected_token_count", "started_at", "finished_at",
        "final_report_json", "created_at", "updated_at",
    },
    "printer_memory_factory_run_steps": {
        "id", "run_id", "step_key", "step_kind", "step_status", "token_id",
        "pair_id", "token_mint", "pair_address", "tracking_lane", "scheduled_for",
        "scheduler_job_id", "source_request_id", "source_response_id",
        "source_failure_id", "snapshot_id", "memory_window_id", "result_json",
        "error_or_skip_reason", "started_at", "finished_at", "created_at",
        "updated_at",
    },
}

REQUIRED_NOT_NULL_COLUMNS = {
    "printer_memory_factory_runs": {
        "run_id", "run_status", "window_kind", "db_mode", "config_hash",
        "config_json", "selected_token_count", "started_at", "created_at",
        "updated_at",
    },
    "printer_memory_factory_run_steps": {
        "run_id", "step_key", "step_kind", "step_status", "created_at",
        "updated_at",
    },
}

REQUIRED_INDEXES = {
    "idx_memory_factory_runs_status": (
        "printer_memory_factory_runs", ("run_status", "started_at"),
    ),
    "idx_memory_factory_steps_run_status": (
        "printer_memory_factory_run_steps",
        ("run_id", "step_status", "scheduled_for"),
    ),
    "idx_memory_factory_steps_job": (
        "printer_memory_factory_run_steps", ("scheduler_job_id",),
    ),
}

REQUIRED_UNIQUE_KEYS = {
    "printer_memory_factory_runs": {("run_id",)},
    "printer_memory_factory_run_steps": {("run_id", "step_key")},
}

REQUIRED_STEP_FOREIGN_KEYS = {
    ("run_id", "printer_memory_factory_runs", "run_id"),
    ("token_id", "printer_tokens", "id"),
    ("pair_id", "printer_pairs", "id"),
    ("scheduler_job_id", "printer_scheduler_jobs", "id"),
    ("source_request_id", "printer_source_requests", "id"),
    ("source_response_id", "printer_source_responses", "id"),
    ("source_failure_id", "printer_source_failures", "id"),
    ("snapshot_id", "printer_token_snapshots", "id"),
    ("memory_window_id", "printer_memory_windows", "id"),
}

CRITICAL_DATA_TABLES = (
    "printer_source_requests", "printer_source_responses",
    "printer_source_failures", "printer_scheduler_jobs",
    "printer_token_snapshots", "printer_memory_windows", "printer_memories",
    "printer_memory_fingerprints", "printer_memory_retrieval_queries",
    "printer_memory_retrieval_matches", "printer_paper_decisions",
    "printer_paper_positions", "printer_paper_trade_events",
    "printer_paper_trade_audits", "printer_paper_audit_reports",
    "printer_memory_factory_runs", "printer_memory_factory_run_steps",
)


class ProofDbReadinessError(ValueError):
    """Fail-closed proof preparation or schema validation error."""


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest().upper()


def _canonical_migration_names() -> list[str]:
    return [path.name for path in sorted(migration_runner.MIGRATIONS_DIR.glob("*.sql"))]


def _table_exists(connection: sqlite3.Connection, table: str) -> bool:
    return connection.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (table,)
    ).fetchone() is not None


def _critical_counts(connection: sqlite3.Connection) -> dict[str, int]:
    return {
        table: (
            int(connection.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0])
            if _table_exists(connection, table) else 0
        )
        for table in CRITICAL_DATA_TABLES
    }


def critical_counts(db_path: str | Path) -> dict[str, int]:
    path = Path(db_path).resolve()
    connection = sqlite3.connect(f"file:{path.as_posix()}?mode=ro", uri=True)
    try:
        return _critical_counts(connection)
    finally:
        connection.close()


def _index_columns(connection: sqlite3.Connection, index_name: str) -> tuple[str, ...]:
    return tuple(str(row[2]) for row in connection.execute(
        f"PRAGMA index_info('{index_name}')"
    ).fetchall())


def _unique_keys(connection: sqlite3.Connection, table: str) -> set[tuple[str, ...]]:
    keys: set[tuple[str, ...]] = set()
    for row in connection.execute(f"PRAGMA index_list('{table}')").fetchall():
        if int(row[2]) == 1:
            keys.add(_index_columns(connection, str(row[1])))
    return keys


def validate_runtime_schema_connection(
    connection: sqlite3.Connection, *, raise_on_error: bool = True,
) -> dict[str, Any]:
    """Validate the complete canonical migration and V2-8.1 ledger contract."""
    issues: list[str] = []
    expected_migrations = _canonical_migration_names()
    if RUN_LEDGER_MIGRATION not in expected_migrations:
        issues.append(f"required canonical migration missing: {RUN_LEDGER_MIGRATION}")

    integrity = str(connection.execute("PRAGMA integrity_check").fetchone()[0])
    if integrity.lower() != "ok":
        issues.append(f"integrity_check failed: {integrity}")
    foreign_key_errors = connection.execute("PRAGMA foreign_key_check").fetchall()
    if foreign_key_errors:
        issues.append(f"foreign_key_check failed: {len(foreign_key_errors)} row(s)")

    applied: list[str] = []
    if not _table_exists(connection, "printer_schema_migrations"):
        issues.append("missing table: printer_schema_migrations")
    else:
        applied = [
            str(row[0]) for row in connection.execute(
                "SELECT version FROM printer_schema_migrations ORDER BY version"
            ).fetchall()
        ]
        missing = sorted(set(expected_migrations) - set(applied))
        unknown = sorted(set(applied) - set(expected_migrations))
        if missing:
            issues.append(f"missing canonical migrations: {missing}")
        if unknown:
            issues.append(f"unknown migration ledger entries: {unknown}")

    for table, required_columns in REQUIRED_TABLE_COLUMNS.items():
        if not _table_exists(connection, table):
            issues.append(f"missing table: {table}")
            continue
        rows = connection.execute(f"PRAGMA table_info('{table}')").fetchall()
        columns = {str(row[1]) for row in rows}
        missing_columns = sorted(required_columns - columns)
        if missing_columns:
            issues.append(f"{table} missing columns: {missing_columns}")
        not_null = {str(row[1]) for row in rows if int(row[3]) == 1}
        missing_not_null = sorted(REQUIRED_NOT_NULL_COLUMNS[table] - not_null)
        if missing_not_null:
            issues.append(f"{table} missing NOT NULL constraints: {missing_not_null}")
        missing_unique = REQUIRED_UNIQUE_KEYS[table] - _unique_keys(connection, table)
        if missing_unique:
            issues.append(f"{table} missing unique keys: {sorted(missing_unique)}")

    for index_name, (table, columns) in REQUIRED_INDEXES.items():
        row = connection.execute(
            "SELECT tbl_name FROM sqlite_master WHERE type='index' AND name=?",
            (index_name,),
        ).fetchone()
        if row is None or str(row[0]) != table:
            issues.append(f"missing index: {index_name}")
        elif _index_columns(connection, index_name) != columns:
            issues.append(f"index column mismatch: {index_name}")

    if _table_exists(connection, "printer_memory_factory_runs"):
        row = connection.execute(
            "SELECT sql FROM sqlite_master WHERE type='table' "
            "AND name='printer_memory_factory_runs'"
        ).fetchone()
        normalized_sql = " ".join(str(row[0] or "").lower().split())
        if "check (window_kind = 'window_15m')" not in normalized_sql:
            issues.append("runs table missing WINDOW_15M check constraint")
        if "check (db_mode = 'proof_only')" not in normalized_sql:
            issues.append("runs table missing PROOF_ONLY check constraint")

    if _table_exists(connection, "printer_memory_factory_run_steps"):
        actual_foreign_keys = {
            (str(row[3]), str(row[2]), str(row[4]))
            for row in connection.execute(
                "PRAGMA foreign_key_list('printer_memory_factory_run_steps')"
            ).fetchall()
        }
        missing_foreign_keys = REQUIRED_STEP_FOREIGN_KEYS - actual_foreign_keys
        if missing_foreign_keys:
            issues.append(
                f"run steps missing foreign keys: {sorted(missing_foreign_keys)}"
            )

    report = {
        "runtime_ready": not issues,
        "issues": issues,
        "canonical_migration_count": len(expected_migrations),
        "applied_migration_count": len(applied),
        "latest_migration": applied[-1] if applied else None,
        "required_tables": sorted(REQUIRED_TABLE_COLUMNS),
        "integrity_check": integrity,
        "foreign_key_error_count": len(foreign_key_errors),
    }
    if issues and raise_on_error:
        raise ProofDbReadinessError("; ".join(issues))
    return report


def validate_runtime_schema(db_path: str | Path) -> dict[str, Any]:
    path = Path(db_path).resolve()
    if not path.is_file():
        raise ProofDbReadinessError(f"database missing: {path}")
    connection = sqlite3.connect(f"file:{path.as_posix()}?mode=ro", uri=True)
    try:
        return validate_runtime_schema_connection(connection)
    finally:
        connection.close()


def _validate_paths(persistent: Path, proof: Path, backup: Path) -> None:
    if not persistent.is_file():
        raise ProofDbReadinessError(f"persistent source DB missing: {persistent}")
    if proof == CANONICAL_PERSISTENT_DB:
        raise ProofDbReadinessError("canonical persistent DB is forbidden as proof target")
    if backup == CANONICAL_PERSISTENT_DB:
        raise ProofDbReadinessError("canonical persistent DB is forbidden as backup target")
    if len({persistent, proof, backup}) != 3:
        raise ProofDbReadinessError("persistent, proof, and backup paths must be distinct")
    if proof.exists():
        raise ProofDbReadinessError(f"proof target must be fresh: {proof}")
    if backup.exists():
        raise ProofDbReadinessError(f"proof backup target must be fresh: {backup}")
    if proof.suffix.lower() not in {".sqlite", ".sqlite3", ".db"}:
        raise ProofDbReadinessError("proof target must be a SQLite file")
    if backup.suffix.lower() not in {".sqlite", ".sqlite3", ".db"}:
        raise ProofDbReadinessError("proof backup target must be a SQLite file")


def prepare_proof_db(
    persistent_db_path: str | Path,
    proof_db_path: str | Path,
    backup_path: str | Path,
) -> dict[str, Any]:
    """Prepare one fresh proof copy without mutating the persistent database."""
    persistent = Path(persistent_db_path).resolve()
    proof = Path(proof_db_path).resolve()
    backup = Path(backup_path).resolve()
    _validate_paths(persistent, proof, backup)

    migration_names = _canonical_migration_names()
    if not migration_names:
        raise ProofDbReadinessError("no canonical migrations found")
    if RUN_LEDGER_MIGRATION not in migration_names:
        raise ProofDbReadinessError(
            f"required canonical migration missing: {RUN_LEDGER_MIGRATION}"
        )

    persistent_hash_before = _sha256(persistent)
    persistent_counts_before = critical_counts(persistent)
    proof.parent.mkdir(parents=True, exist_ok=True)
    backup.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(persistent, proof)

    migration_runner.apply_migrations(proof)
    proof_validation = validate_runtime_schema(proof)
    proof_counts = critical_counts(proof)
    if proof_counts != persistent_counts_before:
        raise ProofDbReadinessError(
            "canonical migrations changed critical data-row counts in proof copy"
        )

    persistent_hash_after = _sha256(persistent)
    persistent_counts_after = critical_counts(persistent)
    if persistent_hash_after != persistent_hash_before:
        raise ProofDbReadinessError("persistent DB hash changed during proof preparation")
    if persistent_counts_after != persistent_counts_before:
        raise ProofDbReadinessError(
            "persistent DB critical counts changed during proof preparation"
        )

    shutil.copy2(proof, backup)
    proof_hash = _sha256(proof)
    backup_hash = _sha256(backup)
    if proof_hash != backup_hash:
        raise ProofDbReadinessError("prepared proof DB and backup are not byte-identical")
    backup_validation = validate_runtime_schema(backup)

    return {
        "status": "PROOF_DB_SCHEMA_READY",
        "persistent_db": str(persistent),
        "proof_db": str(proof),
        "backup_db": str(backup),
        "persistent_hash_before": persistent_hash_before,
        "persistent_hash_after": persistent_hash_after,
        "persistent_unchanged": True,
        "proof_hash": proof_hash,
        "backup_hash": backup_hash,
        "proof_backup_byte_identical": True,
        "critical_counts_before": persistent_counts_before,
        "critical_counts_after": persistent_counts_after,
        "proof_critical_counts": proof_counts,
        "proof_validation": proof_validation,
        "backup_validation": backup_validation,
        "sources_run": False,
        "scheduler_runtime_run": False,
    }


def main_prepare_proof_db(argv: Iterable[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Prepare an isolated, fully migrated V2-9 proof DB and backup."
    )
    parser.add_argument("--operator-approved", action="store_true")
    parser.add_argument("--persistent-db-path", required=True)
    parser.add_argument("--proof-db-path", required=True)
    parser.add_argument("--backup-proof-path", required=True)
    args = parser.parse_args(list(argv) if argv is not None else None)
    try:
        if not args.operator_approved:
            raise ProofDbReadinessError("operator approval required")
        report = prepare_proof_db(
            args.persistent_db_path, args.proof_db_path, args.backup_proof_path
        )
        print(json.dumps(report, indent=2, sort_keys=True))
        return 0
    except Exception as exc:
        print(json.dumps({
            "status": "PROOF_DB_SCHEMA_BLOCKED",
            "error": f"{type(exc).__name__}: {exc}",
            "sources_run": False,
            "scheduler_runtime_run": False,
        }, indent=2, sort_keys=True))
        return 1
