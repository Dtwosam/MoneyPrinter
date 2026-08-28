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
from printer_v1.db.migrate import (
    canonical_migration_names as _shared_canonical_migration_names,
)


PROJECT_ROOT = Path(__file__).resolve().parents[3]
CANONICAL_PERSISTENT_DB = (PROJECT_ROOT / "data" / "printer_v1.sqlite3").resolve()
RUN_LEDGER_MIGRATION = "028_memory_factory_run_ledger.sql"
SUPERVISION_MIGRATION = "030_v2_9_proof_run_supervision.sql"

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
    "printer_proof_run_supervision": {
        "id", "execution_id", "proof_scope", "owner_launcher_type", "process_id",
        "run_id", "execution_status", "terminal_status", "first_stop_reason",
        "heartbeat_at", "lease_expires_at", "proof_db_path", "backup_db_path",
        "one_proof_lock_path", "stdout_log_path", "stderr_log_path",
        "recovery_report_json", "started_at", "finished_at", "created_at",
        "updated_at",
    },
    "printer_memory_factory_standard_4h_progression_attempts": {
        "progression_attempt_id", "campaign_id", "configuration_id",
        "campaign_run_id", "factory_run_id", "cycle_id", "policy_version",
        "attempt_state", "authority_evidence_json", "first_terminal_cause",
        "fault_details_json", "eligibility_completed_at",
        "handoff_committed_at", "terminal_at", "created_at", "updated_at",
    },
    "printer_memory_factory_standard_4h_progression_tokens": {
        "progression_token_id", "progression_attempt_id", "campaign_id",
        "campaign_run_id", "factory_run_id", "cycle_id", "slot_ordinal",
        "token_slot_id", "token_identity", "token_row_id", "mint_identity",
        "pair_identity", "pair_row_id", "lifecycle_identity",
        "tracking_queue_id", "tracking_lane", "predecessor_window_1h_id",
        "predecessor_memory_window_id", "token_disposition",
        "disposition_reasons_json", "eligibility_evidence_json",
        "successor_window_4h_id", "first_terminal_cause",
        "fault_details_json", "evaluated_at", "created_at", "updated_at",
    },
    "printer_pre_admission_discovery_attempt_items": {
        "frozen_tracking_lane", "frozen_discovery_action",
        "frozen_discovery_label", "frozen_classification_reason",
        "frozen_lane_evidence_hash", "frozen_lane_decided_at",
        "frozen_lane_decision_owner",
    },
    "printer_pre_admission_attempt_evidence": {
        "attempt_id", "event_key", "opportunity_ordinal", "claim_ordinal",
        "evidence_kind", "mint_identity", "pair_identity",
        "categorical_reason", "source_request_id", "source_response_id",
        "source_failure_id", "payload_json", "payload_hash", "observed_at",
        "created_at",
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
    "printer_proof_run_supervision": {
        "execution_id", "proof_scope", "owner_launcher_type", "execution_status",
        "heartbeat_at", "lease_expires_at", "proof_db_path", "backup_db_path",
        "one_proof_lock_path", "stdout_log_path", "stderr_log_path", "started_at",
        "created_at", "updated_at",
    },
    "printer_memory_factory_standard_4h_progression_attempts": {
        "progression_attempt_id", "campaign_id", "configuration_id",
        "campaign_run_id", "factory_run_id", "cycle_id", "policy_version",
        "attempt_state", "authority_evidence_json", "fault_details_json",
        "created_at", "updated_at",
    },
    "printer_memory_factory_standard_4h_progression_tokens": {
        "progression_token_id", "progression_attempt_id", "campaign_id",
        "campaign_run_id", "factory_run_id", "cycle_id", "slot_ordinal",
        "token_slot_id", "token_identity", "token_row_id", "mint_identity",
        "pair_identity", "pair_row_id", "lifecycle_identity",
        "tracking_queue_id", "tracking_lane", "token_disposition",
        "disposition_reasons_json", "eligibility_evidence_json",
        "fault_details_json", "created_at", "updated_at",
    },
    "printer_pre_admission_discovery_attempt_items": set(),
    "printer_pre_admission_attempt_evidence": {
        "attempt_id", "event_key", "opportunity_ordinal", "claim_ordinal",
        "evidence_kind", "payload_json", "payload_hash", "observed_at",
        "created_at",
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
    "idx_proof_supervision_one_active_scope": (
        "printer_proof_run_supervision", ("proof_scope",),
    ),
    "idx_proof_supervision_lease": (
        "printer_proof_run_supervision", ("execution_status", "lease_expires_at"),
    ),
    "idx_proof_supervision_run": (
        "printer_proof_run_supervision", ("run_id",),
    ),
    "idx_standard_4h_progression_attempt_scope": (
        "printer_memory_factory_standard_4h_progression_attempts",
        ("campaign_id", "campaign_run_id", "cycle_id", "attempt_state"),
    ),
    "idx_standard_4h_progression_token_disposition": (
        "printer_memory_factory_standard_4h_progression_tokens",
        ("progression_attempt_id", "token_disposition", "slot_ordinal"),
    ),
    "idx_standard_4h_progression_successor": (
        "printer_memory_factory_standard_4h_progression_tokens",
        ("successor_window_4h_id",),
    ),
    "idx_pre_admission_attempt_evidence_reduce": (
        "printer_pre_admission_attempt_evidence",
        ("attempt_id", "opportunity_ordinal", "claim_ordinal", "evidence_kind"),
    ),
}

REQUIRED_UNIQUE_KEYS = {
    "printer_memory_factory_runs": {("run_id",)},
    "printer_memory_factory_run_steps": {("run_id", "step_key")},
    "printer_proof_run_supervision": {("execution_id",), ("run_id",)},
    "printer_memory_factory_standard_4h_progression_attempts": {
        ("progression_attempt_id",),
        ("campaign_id", "campaign_run_id", "cycle_id"),
        (
            "progression_attempt_id",
            "campaign_id",
            "campaign_run_id",
            "cycle_id",
            "factory_run_id",
        ),
    },
    "printer_memory_factory_standard_4h_progression_tokens": {
        ("progression_token_id",),
        ("progression_attempt_id", "slot_ordinal"),
        ("progression_attempt_id", "token_slot_id"),
    },
    "printer_pre_admission_discovery_attempt_items": set(),
    "printer_pre_admission_attempt_evidence": {
        ("attempt_id", "event_key"),
    },
}

REQUIRED_TRIGGERS = {
    "printer_pre_admission_item_frozen_lane_complete": (
        "printer_pre_admission_discovery_attempt_items"
    ),
    "printer_standard_4h_progression_attempt_identity_immutable": (
        "printer_memory_factory_standard_4h_progression_attempts"
    ),
    "printer_standard_4h_progression_attempt_terminal_immutable": (
        "printer_memory_factory_standard_4h_progression_attempts"
    ),
    "printer_standard_4h_progression_attempt_primary_immutable": (
        "printer_memory_factory_standard_4h_progression_attempts"
    ),
    "printer_standard_4h_progression_attempt_authority_immutable": (
        "printer_memory_factory_standard_4h_progression_attempts"
    ),
    "printer_standard_4h_progression_token_identity_immutable": (
        "printer_memory_factory_standard_4h_progression_tokens"
    ),
    "printer_standard_4h_progression_token_terminal_immutable": (
        "printer_memory_factory_standard_4h_progression_tokens"
    ),
    "printer_standard_4h_progression_token_primary_immutable": (
        "printer_memory_factory_standard_4h_progression_tokens"
    ),
    "printer_standard_4h_progression_token_evidence_immutable": (
        "printer_memory_factory_standard_4h_progression_tokens"
    ),
    "printer_pre_admission_attempt_evidence_immutable_update": (
        "printer_pre_admission_attempt_evidence"
    ),
    "printer_pre_admission_attempt_evidence_immutable_delete": (
        "printer_pre_admission_attempt_evidence"
    ),
    "printer_pre_admission_attempt_evidence_response_match": (
        "printer_pre_admission_attempt_evidence"
    ),
    "printer_pre_admission_attempt_evidence_failure_match": (
        "printer_pre_admission_attempt_evidence"
    ),
}

MIGRATION_060_REQUIRED_TABLES = frozenset({
    "printer_pre_admission_discovery_attempt_items",
})
MIGRATION_060_REQUIRED_TRIGGERS = frozenset({
    "printer_pre_admission_item_frozen_lane_complete",
})
MIGRATION_060_REQUIRED_INDEXES = frozenset()
MIGRATION_061_REQUIRED_TABLES = frozenset({
    "printer_memory_factory_standard_4h_progression_attempts",
    "printer_memory_factory_standard_4h_progression_tokens",
})
MIGRATION_061_REQUIRED_TRIGGERS = frozenset({
    "printer_standard_4h_progression_attempt_identity_immutable",
    "printer_standard_4h_progression_attempt_terminal_immutable",
    "printer_standard_4h_progression_attempt_primary_immutable",
    "printer_standard_4h_progression_attempt_authority_immutable",
    "printer_standard_4h_progression_token_identity_immutable",
    "printer_standard_4h_progression_token_terminal_immutable",
    "printer_standard_4h_progression_token_primary_immutable",
    "printer_standard_4h_progression_token_evidence_immutable",
})
MIGRATION_061_REQUIRED_INDEXES = frozenset({
    "idx_standard_4h_progression_attempt_scope",
    "idx_standard_4h_progression_token_disposition",
    "idx_standard_4h_progression_successor",
})
MIGRATION_062_REQUIRED_TABLES = frozenset({
    "printer_pre_admission_attempt_evidence",
})
MIGRATION_062_REQUIRED_TRIGGERS = frozenset({
    "printer_pre_admission_attempt_evidence_immutable_update",
    "printer_pre_admission_attempt_evidence_immutable_delete",
    "printer_pre_admission_attempt_evidence_response_match",
    "printer_pre_admission_attempt_evidence_failure_match",
})
MIGRATION_062_REQUIRED_INDEXES = frozenset({
    "idx_pre_admission_attempt_evidence_reduce",
})

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
    "printer_proof_run_supervision",
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
    """Ordered names from the single canonical migrations/*.sql source."""
    return list(_shared_canonical_migration_names())


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


def inspect_required_schema_objects(
    connection: sqlite3.Connection,
) -> dict[str, Any]:
    """Read-only presence inventory. Never raises because an object is absent."""
    issues: list[str] = []
    for table, required_columns in REQUIRED_TABLE_COLUMNS.items():
        if not _table_exists(connection, table):
            issues.append(f"missing table: {table}")
            continue
        try:
            rows = connection.execute(f"PRAGMA table_info('{table}')").fetchall()
        except sqlite3.Error:
            issues.append(f"missing table: {table}")
            continue
        columns = {str(row[1]) for row in rows}
        missing_columns = sorted(required_columns - columns)
        if missing_columns:
            issues.append(f"{table} missing columns: {missing_columns}")
        not_null = {str(row[1]) for row in rows if int(row[3]) == 1}
        missing_not_null = sorted(
            REQUIRED_NOT_NULL_COLUMNS.get(table, set()) - not_null
        )
        if missing_not_null:
            issues.append(f"{table} missing NOT NULL constraints: {missing_not_null}")
        missing_unique = REQUIRED_UNIQUE_KEYS.get(table, set()) - _unique_keys(
            connection, table
        )
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

    for trigger_name, table in REQUIRED_TRIGGERS.items():
        row = connection.execute(
            "SELECT tbl_name FROM sqlite_master WHERE type='trigger' AND name=?",
            (trigger_name,),
        ).fetchone()
        if row is None or str(row[0]) != table:
            issues.append(f"missing trigger: {trigger_name}")
    return {"issues": issues}


def validate_runtime_schema_connection(
    connection: sqlite3.Connection, *, raise_on_error: bool = True,
) -> dict[str, Any]:
    """Validate the complete canonical migration and V2-8.1 ledger contract."""
    issues: list[str] = []
    expected_migrations = _canonical_migration_names()
    if RUN_LEDGER_MIGRATION not in expected_migrations:
        issues.append(f"required canonical migration missing: {RUN_LEDGER_MIGRATION}")
    if SUPERVISION_MIGRATION not in expected_migrations:
        issues.append(f"required canonical migration missing: {SUPERVISION_MIGRATION}")

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

    object_report = inspect_required_schema_objects(connection)
    issues.extend(str(item) for item in object_report["issues"])

    if _table_exists(connection, "printer_memory_factory_runs"):
        row = connection.execute(
            "SELECT sql FROM sqlite_master WHERE type='table' "
            "AND name='printer_memory_factory_runs'"
        ).fetchone()
        normalized_sql = " ".join(str(row[0] or "").lower().split())
        if "check (window_kind = 'window_15m')" not in normalized_sql:
            issues.append("runs table missing WINDOW_15M check constraint")
        # V2-9.8B.10: operational lifecycle entry requires OPERATIONAL_PERSISTENT.
        # Accept the historical PROOF_ONLY-only form or the widened lawful pair.
        has_proof_only = "check (db_mode = 'proof_only')" in normalized_sql
        has_operational_pair = (
            "db_mode in ('proof_only', 'operational_persistent')" in normalized_sql
            or "db_mode in ('operational_persistent', 'proof_only')" in normalized_sql
        )
        if not (has_proof_only or has_operational_pair):
            issues.append(
                "runs table missing PROOF_ONLY/OPERATIONAL_PERSISTENT db_mode check"
            )

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

    if _table_exists(connection, "printer_proof_run_supervision"):
        row = connection.execute(
            "SELECT sql FROM sqlite_master WHERE type='table' "
            "AND name='printer_proof_run_supervision'"
        ).fetchone()
        normalized_sql = " ".join(str(row[0] or "").lower().split())
        for required in (
            "check (proof_scope = 'v2_9')",
            "'host_process_disappeared'",
            "'operator_cancelled'",
            "'budget_stop'",
            "'source_failure'",
        ):
            if required not in normalized_sql:
                issues.append(f"supervision table missing constraint: {required}")
        actual_foreign_keys = {
            (str(item[3]), str(item[2]), str(item[4]))
            for item in connection.execute(
                "PRAGMA foreign_key_list('printer_proof_run_supervision')"
            ).fetchall()
        }
        if ("run_id", "printer_memory_factory_runs", "run_id") not in actual_foreign_keys:
            issues.append("supervision table missing run ledger foreign key")
        index_row = connection.execute(
            "SELECT sql FROM sqlite_master WHERE type='index' "
            "AND name='idx_proof_supervision_one_active_scope'"
        ).fetchone()
        index_sql = " ".join(str(index_row[0] or "").lower().split()) if index_row else ""
        if "where execution_status in ('starting', 'running')" not in index_sql:
            issues.append("supervision active-scope index missing partial lock predicate")

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
    if SUPERVISION_MIGRATION not in migration_names:
        raise ProofDbReadinessError(
            f"required canonical migration missing: {SUPERVISION_MIGRATION}"
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


if __name__ == "__main__":  # pragma: no cover - module CLI
    raise SystemExit(main_prepare_proof_db())
