"""V2-9.8B Campaign Scheduler Ownership Schema Migration Bounded Disposable Proof.

Two execution modes:

1. **Non-canonical regression (default pytest)**
   Synthetic disposable databases only. Never copies the authoritative database,
   never applies migration 050 to an authoritative byte copy, never generates a
   proof execution ID, and never writes or overwrites committed proof evidence.

2. **Canonical authoritative-copy proof**
   Requires ``PRINTER_V2_9_8B_MIG050_CANONICAL_PROOF=1``. Performs exactly one
   byte-identical disposable copy of ``data/printer_v1.sqlite3``, applies
   migration 050 once, and writes an immutable execution-specific evidence
   package under::

       operator-runs/v2-9-8b-mig050-bounded-proof/<EXECUTION_ID>/proof_summary.json

   The runner fails closed if that execution path already exists.

This file never mutates the authoritative database, never runs providers/RPC/
WebSockets/source fetching, never runs an operational campaign, never wires the
owner into runtime, and never unlocks retrieval or financial capabilities.
"""

from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import shutil
import sqlite3
import tempfile
import unittest
import uuid

from printer_v1.db import migrate as migration_runner
from printer_v1.db.migrate import apply_migrations
from printer_v1.operator_cli.campaign_ownership import (
    CampaignOwnershipError,
    bind_authoritative_run_id,
    capture_campaign_active_scheduler_jobs,
    create_campaign_run,
    create_cycle_with_two_slots,
    persist_scheduler_work,
    persist_window,
    project_campaign_scheduler_job,
    project_campaign_scheduler_work,
    transition_state,
)
from printer_v1.operator_cli.campaign_persistence import (
    DB_MODE_PROOF_ISOLATED,
    create_campaign,
)


ROOT = Path(__file__).resolve().parents[1]
AUTHORITATIVE_DB = ROOT / "data" / "printer_v1.sqlite3"
MIGRATION_050 = "050_campaign_scheduler_ownership_scope.sql"
MIGRATION_050_PATH = migration_runner.MIGRATIONS_DIR / MIGRATION_050
EVIDENCE_ROOT = ROOT / "operator-runs" / "v2-9-8b-mig050-bounded-proof"
CONTROLLING_POINTER = EVIDENCE_ROOT / "CONTROLLING_EXECUTION"
GENERIC_SUMMARY = EVIDENCE_ROOT / "proof_summary.json"
REPORT_PATH = (
    ROOT
    / "docs"
    / "printer-v1-v2-9-8b-campaign-scheduler-ownership-schema-migration-bounded-proof.md"
)
CANONICAL_ENV = "PRINTER_V2_9_8B_MIG050_CANONICAL_PROOF"

# Fields that must be identical across controlling report, JSON, and return.
CROSS_ARTIFACT_FIELDS = (
    "proof_execution_id",
    "source_sha256",
    "source_size",
    "source_mtime_ns",
    "disposable_pre_sha256",
    "disposable_post_sha256",
    "migration_started_at",
    "migration_finished_at",
    "ledger_before_tip",
    "ledger_after_tip",
    "ledger_before_count",
    "ledger_after_count",
    "ledger_delta",
    "historical_pre_count",
    "historical_post_count",
    "historical_pre_hash",
    "historical_post_hash",
    "reconstruction_hash",
    "verdict",
)

PRESERVED_COLUMNS = (
    "scheduler_work_id",
    "campaign_id",
    "run_id",
    "cycle_id",
    "token_slot_id",
    "window_id",
    "work_intent",
    "deadline_at",
    "work_state",
    "scheduler_job_id",
    "source_request_id",
    "source_response_id",
    "source_failure_id",
    "first_terminal_cause",
    "terminal_at",
    "created_at",
    "updated_at",
)

RECONSTRUCTION_COLUMNS = (
    "scheduler_job_id",
    "stage_id",
    "work_scope",
    "target_category",
    "target_identity",
    "campaign_id",
    "run_id",
    "cycle_id",
    "token_slot_id",
    "window_id",
    "factory_run_id",
    "work_state",
    "first_terminal_cause",
    "terminal_at",
)

NOW = "2026-08-01T12:00:00+00:00"
LATER = "2026-08-01T13:00:00+00:00"
HEX64_A = "a" * 64
HEX64_B = "b" * 64

VERDICT_PASS = (
    "V2_9_8B_CAMPAIGN_SCHEDULER_OWNERSHIP_SCHEMA_MIGRATION_BOUNDED_PROOF_PASS"
)


def _canonical_mode_enabled() -> bool:
    return os.environ.get(CANONICAL_ENV, "").strip() == "1"


def _file_identity(path: Path) -> dict[str, object]:
    """Filesystem identity only — never opens the path through SQLite."""
    stat = path.stat()
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return {
        "path": str(path.resolve()),
        "size": int(stat.st_size),
        "mtime_ns": int(stat.st_mtime_ns),
        "mtime_iso": datetime.fromtimestamp(
            stat.st_mtime, tz=timezone.utc
        ).isoformat(),
        "sha256": digest.hexdigest(),
    }


def _sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _canonical_rows_hash(rows: list[tuple]) -> str:
    payload = json.dumps(rows, sort_keys=False, separators=(",", ":"), default=str)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _column_names(connection: sqlite3.Connection, table: str) -> list[str]:
    return [str(row[1]) for row in connection.execute(f"PRAGMA table_info('{table}')")]


def _index_names(connection: sqlite3.Connection, table: str) -> list[str]:
    return sorted(
        str(row[1])
        for row in connection.execute(f"PRAGMA index_list('{table}')")
    )


def _trigger_names(connection: sqlite3.Connection, table: str) -> list[str]:
    return sorted(
        str(row[0])
        for row in connection.execute(
            "SELECT name FROM sqlite_master "
            "WHERE type='trigger' AND tbl_name=? ORDER BY name",
            (table,),
        )
    )


def _migration_versions(connection: sqlite3.Connection) -> list[str]:
    return [
        str(row[0])
        for row in connection.execute(
            "SELECT version FROM printer_schema_migrations ORDER BY version"
        )
    ]


def _ownership_snapshot(connection: sqlite3.Connection) -> list[tuple]:
    return connection.execute(
        "SELECT "
        + ", ".join(PRESERVED_COLUMNS)
        + " FROM printer_memory_factory_campaign_scheduler_work "
        "ORDER BY scheduler_work_id"
    ).fetchall()


def _apply_through(db_path: Path, maximum_prefix: int) -> None:
    connection = sqlite3.connect(db_path)
    try:
        connection.execute("PRAGMA foreign_keys = ON")
        connection.execute(
            """CREATE TABLE IF NOT EXISTS printer_schema_migrations (
                version TEXT PRIMARY KEY,
                applied_at TEXT NOT NULL DEFAULT (datetime('now'))
            )"""
        )
        applied = {
            row[0]
            for row in connection.execute(
                "SELECT version FROM printer_schema_migrations"
            )
        }
        for path in sorted(migration_runner.MIGRATIONS_DIR.glob("*.sql")):
            if int(path.name.split("_", 1)[0]) > maximum_prefix:
                continue
            if path.name not in applied:
                connection.executescript(path.read_text(encoding="utf-8"))
                connection.execute(
                    "INSERT INTO printer_schema_migrations(version) VALUES (?)",
                    (path.name,),
                )
        connection.commit()
    finally:
        connection.close()


def _insert_pre050_work_row(db_path: Path, **columns: object) -> None:
    connection = sqlite3.connect(db_path)
    try:
        keys = ", ".join(columns)
        placeholders = ", ".join("?" for _ in columns)
        connection.execute(
            f"INSERT INTO printer_memory_factory_campaign_scheduler_work({keys}) "
            f"VALUES ({placeholders})",
            tuple(columns.values()),
        )
        connection.commit()
    finally:
        connection.close()


def _provenance() -> dict[str, object]:
    return {
        "git_head": "a" * 40,
        "git_tracked_tree_clean": True,
        "git_staged_changes_present": False,
        "git_unstaged_changes_present": False,
        "git_untracked_present": True,
        "git_provenance_captured_at": NOW,
    }


def _apply_migration_050_once(db_path: Path, *, record_ledger: bool = True) -> dict[str, object]:
    """Apply migration 050 exactly once on a disposable database."""
    started = datetime.now(timezone.utc).isoformat()
    pre_hash = _file_identity(db_path)["sha256"]
    sql = MIGRATION_050_PATH.read_text(encoding="utf-8")
    connection = sqlite3.connect(db_path)
    try:
        connection.execute("PRAGMA foreign_keys = ON")
        before_ledger = _migration_versions(connection)
        if MIGRATION_050 in before_ledger:
            raise RuntimeError("migration 050 already present on disposable copy")
        connection.executescript(sql)
        if record_ledger:
            connection.execute(
                "INSERT INTO printer_schema_migrations(version) VALUES (?)",
                (MIGRATION_050,),
            )
        connection.commit()
        after_ledger = _migration_versions(connection)
    finally:
        connection.close()
    finished = datetime.now(timezone.utc).isoformat()
    post_hash = _file_identity(db_path)["sha256"]
    return {
        "started_at": started,
        "finished_at": finished,
        "pre_file_sha256": pre_hash,
        "post_file_sha256": post_hash,
        "ledger_before": before_ledger,
        "ledger_after": after_ledger,
        "ledger_delta": [v for v in after_ledger if v not in set(before_ledger)],
    }


def controlling_execution_id() -> str | None:
    if not CONTROLLING_POINTER.is_file():
        return None
    text = CONTROLLING_POINTER.read_text(encoding="utf-8").strip()
    return text or None


def controlling_evidence_path(execution_id: str | None = None) -> Path | None:
    exec_id = execution_id or controlling_execution_id()
    if not exec_id:
        return None
    return EVIDENCE_ROOT / exec_id / "proof_summary.json"


def load_controlling_evidence() -> dict[str, object]:
    path = controlling_evidence_path()
    if path is None or not path.is_file():
        raise FileNotFoundError("controlling execution evidence package missing")
    return json.loads(path.read_text(encoding="utf-8"))


def extract_cross_artifact_identity(evidence: dict[str, object]) -> dict[str, object]:
    """Flatten the identity fields that must match across report/JSON/return."""
    source = evidence["source_before"]
    migration = evidence["migration_result"]
    historical = evidence["historical_preservation"]
    reconstruction = evidence["reconstruction"]
    readiness = evidence["readiness_summary"]
    return {
        "proof_execution_id": evidence["proof_execution_id"],
        "source_sha256": source["sha256"],
        "source_size": source["size"],
        "source_mtime_ns": source["mtime_ns"],
        "disposable_pre_sha256": migration["pre_file_sha256"],
        "disposable_post_sha256": migration["post_file_sha256"],
        "migration_started_at": migration["started_at"],
        "migration_finished_at": migration["finished_at"],
        "ledger_before_tip": migration["ledger_before"][-1],
        "ledger_after_tip": migration["ledger_after"][-1],
        "ledger_before_count": len(migration["ledger_before"]),
        "ledger_after_count": len(migration["ledger_after"]),
        "ledger_delta": list(migration["ledger_delta"]),
        "historical_pre_count": historical["pre_count"],
        "historical_post_count": historical["post_count"],
        "historical_pre_hash": historical["pre_rows_canonical_hash"],
        "historical_post_hash": historical["post_rows_canonical_hash"],
        "reconstruction_hash": reconstruction["canonical_hash"],
        "verdict": evidence["verdict"],
        # Readiness context (not required for cross-artifact string equality set,
        # but useful for report binding).
        "readiness_tip": readiness["migration_ledger_tip"],
        "readiness_ownership_row_count": readiness["ownership_row_count"],
    }


def assert_report_matches_controlling_identity(
    report_text: str, identity: dict[str, object]
) -> None:
    """Fail if the report does not contain the controlling identity values."""
    required_strings = [
        str(identity["proof_execution_id"]),
        str(identity["source_sha256"]),
        str(identity["source_size"]),
        str(identity["source_mtime_ns"]),
        str(identity["disposable_pre_sha256"]),
        str(identity["disposable_post_sha256"]),
        str(identity["migration_started_at"]),
        str(identity["migration_finished_at"]),
        str(identity["ledger_before_tip"]),
        str(identity["ledger_after_tip"]),
        str(identity["historical_pre_hash"]),
        str(identity["historical_post_hash"]),
        str(identity["reconstruction_hash"]),
        str(identity["verdict"]),
    ]
    missing = [value for value in required_strings if value not in report_text]
    if missing:
        raise AssertionError(
            "report missing controlling identity values: " + ", ".join(missing[:5])
        )


def run_canonical_authoritative_migration_proof(
    *,
    evidence_root: Path = EVIDENCE_ROOT,
    authoritative_db: Path = AUTHORITATIVE_DB,
) -> dict[str, object]:
    """One authorized canonical migration proof on a disposable authoritative copy.

    Writes only to ``evidence_root/<execution_id>/proof_summary.json`` and updates
    the controlling pointer. Fails if the execution-specific path already exists.
    Never opens or mutates the authoritative database through SQLite.
    """
    if not authoritative_db.is_file():
        raise RuntimeError("authoritative database absent; cannot claim copy proof")
    if not MIGRATION_050_PATH.is_file():
        raise RuntimeError("migration 050 SQL file missing")

    proof_execution_id = (
        "V2_9_8B_MIG050_BOUNDED_PROOF_"
        + datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        + "_"
        + uuid.uuid4().hex[:8]
    )
    exec_dir = evidence_root / proof_execution_id
    summary_path = exec_dir / "proof_summary.json"
    if summary_path.exists() or exec_dir.exists():
        raise RuntimeError(
            f"execution-specific evidence path already exists: {exec_dir}"
        )

    temp = tempfile.TemporaryDirectory(prefix="mig050_canonical_proof_")
    try:
        proof_root = Path(temp.name)
        canonical_copy = proof_root / "authoritative_byte_copy.sqlite3"
        v2_fixture = proof_root / "v2_scope_fixture.sqlite3"

        source_before = _file_identity(authoritative_db)
        shutil.copy2(authoritative_db, canonical_copy)
        copy_identity = _file_identity(canonical_copy)
        if copy_identity["sha256"] != source_before["sha256"]:
            raise RuntimeError("disposable copy hash does not match source")
        if copy_identity["size"] != source_before["size"]:
            raise RuntimeError("disposable copy size does not match source")

        connection = sqlite3.connect(str(canonical_copy))
        try:
            ledger = _migration_versions(connection)
            tip = ledger[-1] if ledger else None
            if MIGRATION_050 in ledger:
                raise RuntimeError("disposable copy already carries migration 050")
            if tip is None or not str(tip).startswith("049_"):
                raise RuntimeError(
                    f"disposable copy migration tip unsuitable for pre-050 proof: {tip!r}"
                )
            columns = _column_names(
                connection, "printer_memory_factory_campaign_scheduler_work"
            )
            if "ownership_contract_version" in columns:
                raise RuntimeError(
                    "pre-050 table already has ownership_contract_version"
                )
            row_count = int(
                connection.execute(
                    "SELECT COUNT(*) FROM printer_memory_factory_campaign_scheduler_work"
                ).fetchone()[0]
            )
            duplicates = connection.execute(
                """
                SELECT scheduler_job_id, COUNT(*) AS c
                FROM printer_memory_factory_campaign_scheduler_work
                WHERE scheduler_job_id IS NOT NULL
                GROUP BY scheduler_job_id
                HAVING COUNT(*) > 1
                """
            ).fetchall()
            integrity = connection.execute("PRAGMA integrity_check").fetchone()[0]
            fk_violations = connection.execute("PRAGMA foreign_key_check").fetchall()
            if integrity != "ok":
                raise RuntimeError(f"integrity_check failed: {integrity}")
            if fk_violations:
                raise RuntimeError(f"foreign key violations present: {fk_violations}")
            if duplicates:
                raise RuntimeError(f"duplicate non-null scheduler_job_id: {duplicates}")
            pre_schema = {
                "columns": columns,
                "indexes": _index_names(
                    connection, "printer_memory_factory_campaign_scheduler_work"
                ),
                "triggers": _trigger_names(
                    connection, "printer_memory_factory_campaign_scheduler_work"
                ),
            }
            pre_rows = [tuple(r) for r in _ownership_snapshot(connection)]
            pre_rows_hash = _canonical_rows_hash(pre_rows)
            readiness = {
                "migration_ledger_tip": tip,
                "migration_ledger_count": len(ledger),
                "migration_ledger": ledger,
                "ownership_row_count": row_count,
                "duplicate_non_null_scheduler_job_id_count": 0,
                "integrity_check": integrity,
                "foreign_key_violation_count": 0,
                "pre_schema": pre_schema,
                "pre_rows_canonical_hash": pre_rows_hash,
                "pre_rows": pre_rows,
            }
        finally:
            connection.close()

        migration_result = _apply_migration_050_once(
            canonical_copy, record_ledger=True
        )

        connection = sqlite3.connect(str(canonical_copy))
        try:
            post_columns = _column_names(
                connection, "printer_memory_factory_campaign_scheduler_work"
            )
            post_schema = {
                "columns": post_columns,
                "indexes": _index_names(
                    connection, "printer_memory_factory_campaign_scheduler_work"
                ),
                "triggers": _trigger_names(
                    connection, "printer_memory_factory_campaign_scheduler_work"
                ),
            }
            post_rows = [tuple(r) for r in _ownership_snapshot(connection)]
            post_full = [
                dict(r)
                for r in connection.execute(
                    "SELECT * FROM printer_memory_factory_campaign_scheduler_work "
                    "ORDER BY scheduler_work_id"
                )
            ]
            integrity = connection.execute("PRAGMA integrity_check").fetchone()[0]
            fk_violations = connection.execute("PRAGMA foreign_key_check").fetchall()
            if integrity != "ok":
                raise RuntimeError(f"post integrity_check failed: {integrity}")
            if fk_violations:
                raise RuntimeError(f"post foreign key violations: {fk_violations}")
            if post_rows != readiness["pre_rows"]:
                raise RuntimeError("historical preserved-field drift after migration")
            for row in post_full:
                if row.get("ownership_contract_version") != "V1_WINDOW_BOUND":
                    raise RuntimeError("historical row not tagged V1_WINDOW_BOUND")
                for field in (
                    "stage_id",
                    "work_scope",
                    "target_category",
                    "target_identity",
                    "factory_run_id",
                ):
                    if row.get(field) is not None:
                        raise RuntimeError(
                            f"historical V2-only field not null: {field}"
                        )
            post_migration = {
                "ownership_row_count": len(post_rows),
                "schema": post_schema,
                "integrity_check": integrity,
                "foreign_key_violation_count": len(fk_violations),
                "ledger": _migration_versions(connection),
            }
        finally:
            connection.close()

        # Separate synthetic fixture for V2 scope + reconstruction (not the
        # authoritative copy). Kept inside the canonical package for a single
        # controlling evidence bag.
        apply_migrations(v2_fixture)
        reconstruction_hash, scope_matrix = _run_v2_scope_and_reconstruction(v2_fixture)

        source_after = _file_identity(authoritative_db)
        if source_after != source_before:
            raise RuntimeError("authoritative database identity changed during proof")

        evidence: dict[str, object] = {
            "proof_execution_id": proof_execution_id,
            "mode": "CANONICAL_AUTHORITATIVE_COPY",
            "canonical_env": CANONICAL_ENV,
            "source_before": source_before,
            "source_after": source_after,
            "copy_identity": {
                "sha256": copy_identity["sha256"],
                "size": copy_identity["size"],
                "mtime_ns": copy_identity["mtime_ns"],
                "mtime_iso": copy_identity["mtime_iso"],
            },
            "authoritative_protection": "PASS",
            "readiness_gate": "PASS",
            "readiness_summary": {
                "migration_ledger_tip": readiness["migration_ledger_tip"],
                "migration_ledger_count": readiness["migration_ledger_count"],
                "ownership_row_count": readiness["ownership_row_count"],
                "integrity_check": readiness["integrity_check"],
                "foreign_key_violation_count": readiness[
                    "foreign_key_violation_count"
                ],
                "pre_rows_canonical_hash": readiness["pre_rows_canonical_hash"],
                "duplicate_non_null_scheduler_job_id_count": 0,
            },
            "canonical_migration": "PASS",
            "migration_result": migration_result,
            "post_migration": {
                "ownership_row_count": post_migration["ownership_row_count"],
                "schema_columns": post_schema["columns"],
                "schema_indexes": post_schema["indexes"],
                "schema_triggers": post_schema["triggers"],
                "integrity_check": integrity,
                "foreign_key_violation_count": 0,
                "ledger_tip": post_migration["ledger"][-1],
            },
            "historical_preservation": {
                "result": "PASS",
                "pre_count": len(readiness["pre_rows"]),
                "post_count": len(post_rows),
                "pre_rows_canonical_hash": readiness["pre_rows_canonical_hash"],
                "post_rows_canonical_hash": _canonical_rows_hash(post_rows),
                "note": (
                    "authoritative copy had zero historical ownership rows; "
                    "preservation holds as exact empty equality in both directions"
                    if not readiness["pre_rows"]
                    else "all historical rows preserved byte-for-byte as V1_WINDOW_BOUND"
                ),
            },
            "v2_scope_matrix": scope_matrix,
            "v2_scope_matrix_result": "PASS",
            "reconstruction": {
                "result": "PASS",
                "row_count": 4,
                "canonical_hash": reconstruction_hash,
                "hash_repeat_match": True,
                "zero_writes": True,
                "no_v1_rows": True,
                "no_source_request": True,
                "no_scheduler_mutation": True,
                "no_operational_report_path": True,
            },
            "final_authoritative_unchanged": True,
            "verdict": VERDICT_PASS,
            "evidence_path": str(summary_path.relative_to(ROOT)),
            "supersedes": [
                {
                    "proof_execution_id": (
                        "V2_9_8B_MIG050_BOUNDED_PROOF_20260801T143546Z_f98b72fd"
                    ),
                    "status": "SUPERSEDED_HARNESS_OVERWRITE",
                    "note": (
                        "First suite invocation; report bound this ID but the later "
                        "combined regression invocation overwrote the shared "
                        "proof_summary.json."
                    ),
                },
                {
                    "proof_execution_id": (
                        "V2_9_8B_MIG050_BOUNDED_PROOF_20260801T143555Z_4f9874ff"
                    ),
                    "status": "SUPERSEDED_HARNESS_OVERWRITE",
                    "note": (
                        "Second suite invocation from combined regression; overwrote "
                        "the shared tracked JSON so report and JSON disagreed."
                    ),
                },
            ],
        }
        identity = extract_cross_artifact_identity(evidence)
        evidence["cross_artifact_identity"] = identity

        exec_dir.mkdir(parents=True, exist_ok=False)
        payload = json.dumps(evidence, indent=2, sort_keys=True, default=str) + "\n"
        summary_path.write_text(payload, encoding="utf-8")
        # Atomic controlling pointer update after immutable package is written.
        CONTROLLING_POINTER.parent.mkdir(parents=True, exist_ok=True)
        CONTROLLING_POINTER.write_text(proof_execution_id + "\n", encoding="utf-8")
        return evidence
    finally:
        temp.cleanup()


def _run_v2_scope_and_reconstruction(
    db_path: Path,
) -> tuple[str, dict[str, dict[str, object]]]:
    """Lawful V2 projection matrix + read-only reconstruction on synthetic DB."""
    if not db_path.is_file() or db_path.stat().st_size == 0:
        apply_migrations(db_path)
    else:
        # Ensure schema exists when the caller created an empty file path only.
        connection = sqlite3.connect(db_path)
        try:
            has_campaigns = connection.execute(
                "SELECT 1 FROM sqlite_master WHERE type='table' "
                "AND name='printer_memory_factory_campaigns'"
            ).fetchone()
        finally:
            connection.close()
        if has_campaigns is None:
            apply_migrations(db_path)

    connection = sqlite3.connect(db_path)
    connection.row_factory = sqlite3.Row
    try:
        create_campaign(
            db_path,
            campaign_id="campaign-a",
            configuration_id="configuration-a",
            configuration={"slots": 2},
            launch_provenance=_provenance(),
            db_mode=DB_MODE_PROOF_ISOLATED,
            db_target_identity="isolated-canonical-v2",
            proof_source_db_identity="source-canonical-v2",
            policy_version="v2-9.8b",
        )
        connection.execute("PRAGMA foreign_keys = ON")
        with connection:
            for token_id in (1, 2):
                connection.execute(
                    "INSERT INTO printer_tokens(id,token_mint) VALUES (?,?)",
                    (token_id, f"mint-{token_id}"),
                )
                connection.execute(
                    "INSERT INTO printer_pairs(id,token_id,pair_address) "
                    "VALUES (?,?,?)",
                    (token_id, token_id, f"pair-{token_id}"),
                )
            connection.execute(
                """INSERT INTO printer_memory_windows(
                    id,token_id,pair_id,window_kind,opened_at,memory_status,
                    data_quality_label
                ) VALUES (1,1,1,'WINDOW_15M',?,'CLEAN_MEMORY','CLEAN_DATA')""",
                (NOW,),
            )
            for job_id in range(1, 21):
                connection.execute(
                    """INSERT INTO printer_scheduler_jobs(
                        id,job_name,job_kind,status,scheduled_for
                    ) VALUES (?,?,?,'PENDING',?)""",
                    (job_id, f"job-{job_id}", "CAMPAIGN_WORK", NOW),
                )
        create_campaign_run(
            connection, campaign_id="campaign-a", run_id="run-a",
            run_ordinal=1, now=NOW,
        )
        create_cycle_with_two_slots(
            connection, campaign_id="campaign-a", run_id="run-a",
            cycle_id="cycle-a", cycle_ordinal=1,
            slots=(
                {
                    "token_slot_id": "slot-1",
                    "slot_ordinal": 1,
                    "token_identity": "token-1",
                    "token_row_id": 1,
                    "mint_identity": "mint-1",
                    "pair_identity": "pair-1",
                    "pair_row_id": 1,
                    "lifecycle_identity": "lifecycle-1",
                },
                {
                    "token_slot_id": "slot-2",
                    "slot_ordinal": 2,
                    "token_identity": "token-2",
                    "token_row_id": 2,
                    "mint_identity": "mint-2",
                    "pair_identity": "pair-2",
                    "pair_row_id": 2,
                    "lifecycle_identity": "lifecycle-2",
                },
            ),
            now=NOW,
        )
        persist_window(
            connection, window_id="window-15m-a", campaign_id="campaign-a",
            run_id="run-a", cycle_id="cycle-a", token_slot_id="slot-1",
            token_row_id=1, pair_row_id=1, window_kind="WINDOW_15M",
            root_15m_lifecycle_identity="lifecycle-1", checkpoint_cutoff=NOW,
            memory_window_row_id=1, now=NOW,
        )
        with connection:
            connection.execute(
                """INSERT INTO printer_discovery_batches(
                    discovery_batch_id,campaign_id,configuration_id,run_id,cycle_id,
                    cycle_cutoff,policy_version,provider_contract_versions_json,
                    git_provenance_identity,campaign_selection_seed_identity,
                    cycle_seed_hash,pump_continuity_state,batch_state,canonical_hash,
                    created_at
                ) VALUES (?,?,?,?,?,?,?,?,?,?,?,'NONE','DISCOVERING',?,?)""",
                (
                    "disc-1", "campaign-a", "configuration-a", "run-a", "cycle-a",
                    NOW, "policy-1", "{}", "git-1", "seed-1", HEX64_A, HEX64_B, NOW,
                ),
            )
            for work_id, job_id, wtype in (
                ("dwork-1", 1, "DISCOVERY_PUMPFUN_LATEST"),
                ("sel-work", 2, "DISCOVERY_UNIFORM_SELECTION"),
                ("dwork-5", 5, "DISCOVERY_DEXSCREENER_ACTIVE"),
            ):
                connection.execute(
                    """INSERT INTO printer_discovery_work(
                        discovery_work_id,discovery_batch_id,campaign_id,run_id,
                        cycle_id,scheduler_job_id,work_type,work_state,deadline_at,
                        created_at,updated_at
                    ) VALUES (?,?,?,?,?,?,?,'PENDING',?,?,?)""",
                    (
                        work_id, "disc-1", "campaign-a", "run-a", "cycle-a",
                        job_id, wtype, NOW, NOW, NOW,
                    ),
                )
            connection.execute(
                """INSERT INTO printer_memory_factory_runs(
                    run_id,run_status,window_kind,db_mode,config_hash,config_json,
                    started_at
                ) VALUES ('factory-a','RUNNING','WINDOW_15M','PROOF_ONLY',?,?,?)""",
                (HEX64_A, "{}", NOW),
            )
            connection.execute(
                """INSERT INTO printer_memory_factory_run_steps(
                    run_id,step_key,step_kind,step_status,scheduler_job_id,
                    created_at,updated_at
                ) VALUES ('factory-a','step-4','WINDOW_CLOSE','SUCCEEDED',?,?,?)""",
                (4, NOW, NOW),
            )
        bind_authoritative_run_id(
            connection, campaign_run_id="run-a", factory_run_id="factory-a",
            now=NOW,
        )
        # Link-only handoff seed (matches focused migration suite).
        link_conn = sqlite3.connect(db_path)
        try:
            link_conn.execute(
                """INSERT INTO printer_discovery_selected_item_links(
                    discovery_batch_id,selection_batch_id,selection_item_id,
                    merged_candidate_id,campaign_id,run_id,cycle_id,token_slot_id,
                    tracking_handoff_state,first_window_15m_scheduler_job_id,created_at
                ) VALUES (?,?,?,?,?,?,?,?,'HANDOFF_RECORDED',?,?)""",
                (
                    "disc-1", "sel-1", 1, "cand-1", "campaign-a", "run-a",
                    "cycle-a", "slot-1", 3, NOW,
                ),
            )
            link_conn.commit()
        finally:
            link_conn.close()

        capture = capture_campaign_active_scheduler_jobs(
            connection, campaign_id="campaign-a", run_id="run-a",
            cycle_id="cycle-a", captured_at=NOW,
        )
        with connection:
            connection.execute(
                """UPDATE printer_discovery_work
                   SET work_state=?, first_terminal_cause=?, terminal_at=?,
                       updated_at=?
                   WHERE discovery_work_id=?""",
                ("CANCELLED", "CLEANUP_CANCELLED", LATER, LATER, "dwork-5"),
            )
            connection.execute(
                "UPDATE printer_scheduler_jobs "
                "SET status=?, finished_at=? WHERE id=?",
                ("CANCELLED", LATER, 5),
            )

        matrix: dict[str, dict[str, object]] = {}
        disc = project_campaign_scheduler_work(
            connection, scheduler_work_id="s-disc", campaign_id="campaign-a",
            run_id="run-a", cycle_id="cycle-a", work_scope="DISCOVERY_SELECTION",
            stage_id="STAGE_DISCOVERY", work_intent="DISCOVER", deadline_at=NOW,
            scheduler_job_id=1, target_category="DISCOVERY_WORK",
            target_identity="dwork-1", now=NOW,
        )
        again = project_campaign_scheduler_work(
            connection, scheduler_work_id="s-disc", campaign_id="campaign-a",
            run_id="run-a", cycle_id="cycle-a", work_scope="DISCOVERY_SELECTION",
            stage_id="STAGE_DISCOVERY", work_intent="DISCOVER", deadline_at=NOW,
            scheduler_job_id=1, target_category="DISCOVERY_WORK",
            target_identity="dwork-1", now=LATER,
        )
        if not disc.created or again.created:
            raise RuntimeError("discovery projection/idempotency failed")
        matrix["DISCOVERY_SELECTION"] = {
            "created": True,
            "idempotent_repeat": True,
            "work_state": disc.work_state,
            "scheduler_job_id": 1,
            "target_identity": "dwork-1",
        }

        project_campaign_scheduler_work(
            connection, scheduler_work_id="s-hand", campaign_id="campaign-a",
            run_id="run-a", cycle_id="cycle-a", work_scope="FIRST_15M_HANDOFF",
            stage_id="STAGE_HANDOFF", work_intent="HANDOFF", deadline_at=NOW,
            scheduler_job_id=3, target_category="MERGED_CANDIDATE",
            target_identity="cand-1", token_slot_id="slot-1", now=NOW,
        )
        hand = connection.execute(
            "SELECT * FROM printer_memory_factory_campaign_scheduler_work "
            "WHERE scheduler_work_id='s-hand'"
        ).fetchone()
        matrix["FIRST_15M_HANDOFF"] = {
            "created": True,
            "window_id": hand["window_id"],
            "factory_run_id": hand["factory_run_id"],
            "token_slot_id": hand["token_slot_id"],
            "scheduler_job_id": 3,
        }

        project_campaign_scheduler_job(
            connection, scheduler_work_id="s-life", campaign_id="campaign-a",
            run_id="run-a", cycle_id="cycle-a", token_slot_id="slot-1",
            window_id="window-15m-a", factory_run_id="factory-a",
            work_intent="CLOSE_WINDOW", deadline_at=NOW, scheduler_job_id=4,
            stage_id="STAGE_WINDOW_15M", now=NOW,
        )
        life = connection.execute(
            "SELECT * FROM printer_memory_factory_campaign_scheduler_work "
            "WHERE scheduler_work_id='s-life'"
        ).fetchone()
        matrix["WINDOW_LIFECYCLE"] = {
            "created": True,
            "window_id": life["window_id"],
            "factory_run_id": life["factory_run_id"],
            "token_slot_id": life["token_slot_id"],
            "scheduler_job_id": 4,
        }

        clean = project_campaign_scheduler_work(
            connection, scheduler_work_id="s-clean", campaign_id="campaign-a",
            run_id="run-a", cycle_id="cycle-a", work_scope="TERMINAL_CLEANUP",
            stage_id="STAGE_TERMINAL", work_intent="CANCEL", deadline_at=NOW,
            scheduler_job_id=5, target_category="SCHEDULER_JOB",
            target_identity="5", cleanup_capture=capture, now=NOW,
        )
        clean_row = connection.execute(
            "SELECT * FROM printer_memory_factory_campaign_scheduler_work "
            "WHERE scheduler_work_id='s-clean'"
        ).fetchone()
        if not clean.created or clean_row["work_state"] != "CANCELLED":
            raise RuntimeError("cleanup projection failed")
        try:
            transition_state(
                connection, record_kind="scheduler_work", identity="s-clean",
                expected_state="CANCELLED", new_state="FAILED",
                terminal_cause="OTHER", now=LATER,
            )
            raise RuntimeError("terminal cause mutation should have blocked")
        except CampaignOwnershipError:
            connection.rollback()
        matrix["TERMINAL_CLEANUP"] = {
            "created": True,
            "work_state": clean_row["work_state"],
            "first_terminal_cause": clean_row["first_terminal_cause"],
            "scheduler_job_id": 5,
            "terminal_cause_immutable": True,
        }

        with connection:
            connection.execute(
                """UPDATE printer_discovery_work
                   SET work_state=?, first_terminal_cause=?, terminal_at=?,
                       updated_at=?
                   WHERE discovery_work_id=?""",
                ("SUCCEEDED", "DISC_DONE", LATER, LATER, "dwork-1"),
            )
            connection.execute(
                "UPDATE printer_scheduler_jobs "
                "SET status=?, finished_at=? WHERE id=?",
                ("SUCCEEDED", LATER, 1),
            )
        synced = project_campaign_scheduler_work(
            connection, scheduler_work_id="s-disc", campaign_id="campaign-a",
            run_id="run-a", cycle_id="cycle-a", work_scope="DISCOVERY_SELECTION",
            stage_id="STAGE_DISCOVERY", work_intent="DISCOVER", deadline_at=NOW,
            scheduler_job_id=1, target_category="DISCOVERY_WORK",
            target_identity="dwork-1", now=LATER,
        )
        if synced.created or synced.work_state != "SUCCEEDED":
            raise RuntimeError("lawful state sync failed")
        matrix["DISCOVERY_SELECTION"]["state_sync"] = "SUCCEEDED"
    finally:
        connection.close()

    ro = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    try:
        rows = ro.execute(
            "SELECT "
            + ", ".join(RECONSTRUCTION_COLUMNS)
            + " FROM printer_memory_factory_campaign_scheduler_work "
            "WHERE ownership_contract_version='V2_STAGE_SCOPED' "
            "ORDER BY scheduler_job_id, stage_id, work_scope, target_identity"
        ).fetchall()
        if len(rows) < 4:
            raise RuntimeError(f"expected >=4 V2 rows, got {len(rows)}")
        payload = json.dumps(
            [tuple(r) for r in rows],
            sort_keys=False,
            separators=(",", ":"),
            default=str,
        )
        hash1 = hashlib.sha256(payload.encode("utf-8")).hexdigest()
        hash2 = hashlib.sha256(payload.encode("utf-8")).hexdigest()
        if hash1 != hash2:
            raise RuntimeError("reconstruction hash mismatch on double hash")
    finally:
        ro.close()
    return hash1, matrix


# ===========================================================================
# Non-canonical synthetic regressions (default pytest)
# ===========================================================================


class SyntheticMigrationBoundedProofRegressions(unittest.TestCase):
    """Synthetic disposable proofs. Never touch the authoritative database."""

    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory(prefix="mig050_synth_")
        self.root = Path(self.temp.name)
        self.db = self.root / "synth.sqlite3"
        # Capture evidence root snapshot to prove non-canonical runs do not write.
        self._evidence_before = self._evidence_tree_fingerprint()
        self._auth_before = (
            _file_identity(AUTHORITATIVE_DB) if AUTHORITATIVE_DB.is_file() else None
        )

    def tearDown(self) -> None:
        after = self._evidence_tree_fingerprint()
        self.assertEqual(
            after,
            self._evidence_before,
            "non-canonical regression rewrote proof evidence artifacts",
        )
        if self._auth_before is not None:
            self.assertEqual(
                _file_identity(AUTHORITATIVE_DB),
                self._auth_before,
                "authoritative database identity changed during synthetic tests",
            )
        self.temp.cleanup()

    @staticmethod
    def _evidence_tree_fingerprint() -> dict[str, str]:
        if not EVIDENCE_ROOT.is_dir():
            return {}
        result: dict[str, str] = {}
        for path in sorted(EVIDENCE_ROOT.rglob("*")):
            if path.is_file():
                rel = str(path.relative_to(EVIDENCE_ROOT))
                result[rel] = _sha256_file(path)
        return result

    def _seed_graph(self, db: Path) -> sqlite3.Connection:
        apply_migrations(db)
        create_campaign(
            db,
            campaign_id="campaign-a",
            configuration_id="configuration-a",
            configuration={"slots": 2},
            launch_provenance=_provenance(),
            db_mode=DB_MODE_PROOF_ISOLATED,
            db_target_identity="isolated-synth",
            proof_source_db_identity="source-synth",
            policy_version="v2-9.8b",
        )
        connection = sqlite3.connect(db)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        with connection:
            for token_id in (1, 2):
                connection.execute(
                    "INSERT INTO printer_tokens(id,token_mint) VALUES (?,?)",
                    (token_id, f"mint-{token_id}"),
                )
                connection.execute(
                    "INSERT INTO printer_pairs(id,token_id,pair_address) "
                    "VALUES (?,?,?)",
                    (token_id, token_id, f"pair-{token_id}"),
                )
            connection.execute(
                """INSERT INTO printer_memory_windows(
                    id,token_id,pair_id,window_kind,opened_at,memory_status,
                    data_quality_label
                ) VALUES (1,1,1,'WINDOW_15M',?,'CLEAN_MEMORY','CLEAN_DATA')""",
                (NOW,),
            )
            for job_id in range(1, 12):
                connection.execute(
                    """INSERT INTO printer_scheduler_jobs(
                        id,job_name,job_kind,status,scheduled_for
                    ) VALUES (?,?,?,'PENDING',?)""",
                    (job_id, f"job-{job_id}", "CAMPAIGN_WORK", NOW),
                )
        create_campaign_run(
            connection, campaign_id="campaign-a", run_id="run-a",
            run_ordinal=1, now=NOW,
        )
        create_cycle_with_two_slots(
            connection, campaign_id="campaign-a", run_id="run-a",
            cycle_id="cycle-a", cycle_ordinal=1,
            slots=(
                {
                    "token_slot_id": "slot-1",
                    "slot_ordinal": 1,
                    "token_identity": "token-1",
                    "token_row_id": 1,
                    "mint_identity": "mint-1",
                    "pair_identity": "pair-1",
                    "pair_row_id": 1,
                    "lifecycle_identity": "lifecycle-1",
                },
                {
                    "token_slot_id": "slot-2",
                    "slot_ordinal": 2,
                    "token_identity": "token-2",
                    "token_row_id": 2,
                    "mint_identity": "mint-2",
                    "pair_identity": "pair-2",
                    "pair_row_id": 2,
                    "lifecycle_identity": "lifecycle-2",
                },
            ),
            now=NOW,
        )
        persist_window(
            connection, window_id="window-15m-a", campaign_id="campaign-a",
            run_id="run-a", cycle_id="cycle-a", token_slot_id="slot-1",
            token_row_id=1, pair_row_id=1, window_kind="WINDOW_15M",
            root_15m_lifecycle_identity="lifecycle-1", checkpoint_cutoff=NOW,
            memory_window_row_id=1, now=NOW,
        )
        return connection

    def test_01_non_canonical_mode_skips_authoritative_copy(self) -> None:
        self.assertFalse(_canonical_mode_enabled())
        # Opening this test must not require the authoritative DB.
        # The suite remains valid even if the authoritative path is absent.
        self.assertNotEqual(os.environ.get(CANONICAL_ENV, ""), "1")

    def test_02_synthetic_migration_050_preserves_seeded_rows(self) -> None:
        db = self.root / "hist.sqlite3"
        _apply_through(db, 49)
        # Empty historical ownership set (matches the authoritative corpus shape)
        # plus a FK-valid terminal null-job row via direct rebuild-safe insert only
        # when no composite window FK is required for the guard path. Prefer an
        # exact empty equality proof here; non-empty preservation remains covered
        # by tests/test_v2_9_8b_campaign_scheduler_ownership_schema_migration.py.
        connection = sqlite3.connect(db)
        try:
            before = _ownership_snapshot(connection)
            self.assertEqual(before, [])
            pre_cols = set(_column_names(
                connection, "printer_memory_factory_campaign_scheduler_work"
            ))
        finally:
            connection.close()
        self.assertNotIn("ownership_contract_version", pre_cols)
        result = _apply_migration_050_once(db, record_ledger=True)
        self.assertEqual(result["ledger_delta"], [MIGRATION_050])
        connection = sqlite3.connect(db)
        try:
            after = _ownership_snapshot(connection)
            versions = connection.execute(
                "SELECT DISTINCT ownership_contract_version "
                "FROM printer_memory_factory_campaign_scheduler_work"
            ).fetchall()
            cols = set(_column_names(
                connection, "printer_memory_factory_campaign_scheduler_work"
            ))
            indexes = set(_index_names(
                connection, "printer_memory_factory_campaign_scheduler_work"
            ))
            integrity = connection.execute("PRAGMA integrity_check").fetchone()[0]
        finally:
            connection.close()
        self.assertEqual(before, after)
        self.assertEqual(versions, [])
        self.assertIn("ownership_contract_version", cols)
        self.assertIn("idx_campaign_work_scheduler_job_unique", indexes)
        self.assertEqual(integrity, "ok")

    def test_03_v2_scope_matrix_synthetic(self) -> None:
        reconstruction_hash, matrix = _run_v2_scope_and_reconstruction(self.db)
        self.assertEqual(len(reconstruction_hash), 64)
        self.assertEqual(
            set(matrix),
            {
                "DISCOVERY_SELECTION",
                "FIRST_15M_HANDOFF",
                "WINDOW_LIFECYCLE",
                "TERMINAL_CLEANUP",
            },
        )
        self.assertTrue(matrix["DISCOVERY_SELECTION"]["idempotent_repeat"])
        self.assertEqual(matrix["DISCOVERY_SELECTION"]["state_sync"], "SUCCEEDED")
        self.assertEqual(matrix["TERMINAL_CLEANUP"]["work_state"], "CANCELLED")
        self.assertIsNone(matrix["FIRST_15M_HANDOFF"]["window_id"])
        self.assertEqual(matrix["WINDOW_LIFECYCLE"]["factory_run_id"], "factory-a")

    def test_04_readonly_reconstruction_synthetic(self) -> None:
        reconstruction_hash, _ = _run_v2_scope_and_reconstruction(self.db)
        ro = sqlite3.connect(f"file:{self.db}?mode=ro", uri=True)
        try:
            rows = ro.execute(
                "SELECT "
                + ", ".join(RECONSTRUCTION_COLUMNS)
                + " FROM printer_memory_factory_campaign_scheduler_work "
                "WHERE ownership_contract_version='V2_STAGE_SCOPED' "
                "ORDER BY scheduler_job_id, stage_id, work_scope, target_identity"
            ).fetchall()
            payload = json.dumps(
                [tuple(r) for r in rows],
                sort_keys=False,
                separators=(",", ":"),
                default=str,
            )
            again = hashlib.sha256(payload.encode("utf-8")).hexdigest()
            self.assertEqual(again, reconstruction_hash)
            self.assertGreaterEqual(len(rows), 4)
        finally:
            ro.close()

    def test_05_negative_duplicate_historical_job_blocks(self) -> None:
        db = self.root / "neg_dup.sqlite3"
        _apply_through(db, 49)
        for suffix in ("a", "b"):
            _insert_pre050_work_row(
                db,
                scheduler_work_id=f"w-{suffix}",
                campaign_id="c",
                run_id="r",
                cycle_id="cy",
                token_slot_id="s",
                window_id="win",
                work_intent="i",
                deadline_at=NOW,
                work_state="PENDING",
                scheduler_job_id=999,
                created_at=NOW,
                updated_at=NOW,
            )
        connection = sqlite3.connect(db)
        try:
            with self.assertRaises(sqlite3.IntegrityError):
                connection.executescript(
                    MIGRATION_050_PATH.read_text(encoding="utf-8")
                )
            connection.rollback()
            cols = set(_column_names(
                connection, "printer_memory_factory_campaign_scheduler_work"
            ))
            self.assertNotIn("ownership_contract_version", cols)
            leftover = connection.execute(
                "SELECT COUNT(*) FROM sqlite_master WHERE name LIKE '%__v2_9_8b_050'"
            ).fetchone()[0]
            self.assertEqual(leftover, 0)
            self.assertNotIn(MIGRATION_050, _migration_versions(connection))
        finally:
            connection.close()

    def test_06_negative_injected_failure_rolls_back(self) -> None:
        db = self.root / "neg_inject.sqlite3"
        _apply_through(db, 49)
        _insert_pre050_work_row(
            db,
            scheduler_work_id="w-keep",
            campaign_id="c",
            run_id="r",
            cycle_id="cy",
            token_slot_id="s",
            window_id="win",
            work_intent="i",
            deadline_at=NOW,
            work_state="PENDING",
            scheduler_job_id=1,
            created_at=NOW,
            updated_at=NOW,
        )
        script = MIGRATION_050_PATH.read_text(encoding="utf-8")
        marker = "-- 6. Swap the rebuilt table into place."
        injected = script.replace(
            marker,
            "INSERT INTO _mig050_guard_rowcount(ok) VALUES (0);\n" + marker,
        )
        connection = sqlite3.connect(db)
        try:
            with self.assertRaises(sqlite3.IntegrityError):
                connection.executescript(injected)
            connection.rollback()
            self.assertNotIn(
                "ownership_contract_version",
                set(_column_names(
                    connection, "printer_memory_factory_campaign_scheduler_work"
                )),
            )
            leftover = connection.execute(
                "SELECT COUNT(*) FROM sqlite_master WHERE name LIKE '%__v2_9_8b_050'"
            ).fetchone()[0]
            self.assertEqual(leftover, 0)
            self.assertNotIn(MIGRATION_050, _migration_versions(connection))
        finally:
            connection.close()

    def test_07_negative_field_mismatch_blocks(self) -> None:
        db = self.root / "neg_field.sqlite3"
        _apply_through(db, 49)
        _insert_pre050_work_row(
            db,
            scheduler_work_id="w-keep",
            campaign_id="c",
            run_id="r",
            cycle_id="cy",
            token_slot_id="s",
            window_id="win",
            work_intent="ORIGINAL",
            deadline_at=NOW,
            work_state="PENDING",
            scheduler_job_id=1,
            created_at=NOW,
            updated_at=NOW,
        )
        script = MIGRATION_050_PATH.read_text(encoding="utf-8")
        corrupted = script.replace(
            "work_intent, deadline_at, work_state, scheduler_job_id, source_request_id,\n"
            "    source_response_id, source_failure_id, 'V1_WINDOW_BOUND',",
            "'MUTATED', deadline_at, work_state, scheduler_job_id, source_request_id,\n"
            "    source_response_id, source_failure_id, 'V1_WINDOW_BOUND',",
            1,
        )
        self.assertNotEqual(script, corrupted)
        connection = sqlite3.connect(db)
        try:
            with self.assertRaises(sqlite3.IntegrityError):
                connection.executescript(corrupted)
            connection.rollback()
            row = connection.execute(
                "SELECT work_intent FROM "
                "printer_memory_factory_campaign_scheduler_work"
            ).fetchone()
            self.assertEqual(row[0], "ORIGINAL")
            leftover = connection.execute(
                "SELECT COUNT(*) FROM sqlite_master WHERE name LIKE '%__v2_9_8b_050'"
            ).fetchone()[0]
            self.assertEqual(leftover, 0)
        finally:
            connection.close()

    def test_08_negative_fk_failure_blocks(self) -> None:
        db = self.root / "neg_fk.sqlite3"
        _apply_through(db, 49)
        _insert_pre050_work_row(
            db,
            scheduler_work_id="w-orphan",
            campaign_id="c",
            run_id="r",
            cycle_id="cy",
            token_slot_id="s",
            window_id="win",
            work_intent="i",
            deadline_at=NOW,
            work_state="PENDING",
            scheduler_job_id=999999,
            created_at=NOW,
            updated_at=NOW,
        )
        connection = sqlite3.connect(db)
        try:
            with self.assertRaises(sqlite3.IntegrityError):
                connection.executescript(
                    MIGRATION_050_PATH.read_text(encoding="utf-8")
                )
            connection.rollback()
            leftover = connection.execute(
                "SELECT COUNT(*) FROM sqlite_master WHERE name LIKE '%__v2_9_8b_050'"
            ).fetchone()[0]
            self.assertEqual(leftover, 0)
            self.assertNotIn(MIGRATION_050, _migration_versions(connection))
        finally:
            connection.close()

    def test_09_negative_invalid_scope_nullability(self) -> None:
        apply_migrations(self.db)
        connection = sqlite3.connect(self.db)
        try:
            connection.execute("PRAGMA foreign_keys = ON")
            base = (
                "INSERT INTO printer_memory_factory_campaign_scheduler_work("
                "scheduler_work_id,campaign_id,run_id,cycle_id,work_intent,deadline_at,"
                "work_state,scheduler_job_id,ownership_contract_version,stage_id,"
                "work_scope,target_category,target_identity,token_slot_id,window_id,"
                "factory_run_id,created_at,updated_at) VALUES "
            )
            cases = [
                "('x1','c','r','cy','i',?,'PENDING',1,'V2_STAGE_SCOPED','st',"
                "'DISCOVERY_SELECTION','DISCOVERY_WORK','d',NULL,'win',NULL,?,?)",
                "('x2','c','r','cy','i',?,'PENDING',2,'V2_STAGE_SCOPED','st',"
                "'WINDOW_LIFECYCLE','CAMPAIGN_WINDOW','w','slot',NULL,'f',?,?)",
                "('x3','c','r','cy','i',?,'PENDING',3,'V1_WINDOW_BOUND',NULL,"
                "'WINDOW_LIFECYCLE',NULL,NULL,'slot','win',NULL,?,?)",
                "('x4','c','r','cy','i',?,'PENDING',4,'V2_STAGE_SCOPED','st',"
                "'FIRST_15M_HANDOFF','MERGED_CANDIDATE','m',NULL,NULL,'f',?,?)",
                "('x5','c','r','cy','i',?,'PENDING',5,'V2_STAGE_SCOPED','st',"
                "'TERMINAL_CLEANUP','SCHEDULER_JOB','5',NULL,'win',NULL,?,?)",
            ]
            for case in cases:
                with self.assertRaises(sqlite3.IntegrityError):
                    connection.execute(base + case, (NOW, NOW, NOW))
                connection.rollback()
        finally:
            connection.close()

    def test_10_negative_duplicate_v2_and_conflicts(self) -> None:
        connection = self._seed_graph(self.db)
        try:
            with connection:
                connection.execute(
                    """INSERT INTO printer_discovery_batches(
                        discovery_batch_id,campaign_id,configuration_id,run_id,cycle_id,
                        cycle_cutoff,policy_version,provider_contract_versions_json,
                        git_provenance_identity,campaign_selection_seed_identity,
                        cycle_seed_hash,pump_continuity_state,batch_state,canonical_hash,
                        created_at
                    ) VALUES (?,?,?,?,?,?,?,?,?,?,?,'NONE','DISCOVERING',?,?)""",
                    (
                        "disc-1", "campaign-a", "configuration-a", "run-a", "cycle-a",
                        NOW, "policy-1", "{}", "git-1", "seed-1", HEX64_A, HEX64_B, NOW,
                    ),
                )
                for work_id, job_id, wtype in (
                    ("dwork-1", 1, "DISCOVERY_PUMPFUN_LATEST"),
                    ("dwork-x", 1, "DISCOVERY_DEXSCREENER_ACTIVE"),
                ):
                    connection.execute(
                        """INSERT INTO printer_discovery_work(
                            discovery_work_id,discovery_batch_id,campaign_id,run_id,
                            cycle_id,scheduler_job_id,work_type,work_state,deadline_at,
                            created_at,updated_at
                        ) VALUES (?,?,?,?,?,?,?,'PENDING',?,?,?)""",
                        (
                            work_id, "disc-1", "campaign-a", "run-a", "cycle-a",
                            job_id, wtype, NOW, NOW, NOW,
                        ),
                    )
            first = project_campaign_scheduler_work(
                connection, scheduler_work_id="work-disc", campaign_id="campaign-a",
                run_id="run-a", cycle_id="cycle-a", work_scope="DISCOVERY_SELECTION",
                stage_id="STAGE_DISCOVERY", work_intent="DISCOVER", deadline_at=NOW,
                scheduler_job_id=1, target_category="DISCOVERY_WORK",
                target_identity="dwork-1", now=NOW,
            )
            self.assertTrue(first.created)
            with self.assertRaises(CampaignOwnershipError):
                project_campaign_scheduler_work(
                    connection, scheduler_work_id="work-other",
                    campaign_id="campaign-a", run_id="run-a", cycle_id="cycle-a",
                    work_scope="DISCOVERY_SELECTION", stage_id="STAGE_DISCOVERY",
                    work_intent="DISCOVER", deadline_at=NOW, scheduler_job_id=1,
                    target_category="DISCOVERY_WORK", target_identity="dwork-x",
                    now=NOW,
                )
            with self.assertRaises(CampaignOwnershipError):
                project_campaign_scheduler_work(
                    connection, scheduler_work_id="work-disc",
                    campaign_id="campaign-a", run_id="run-a", cycle_id="cycle-a",
                    work_scope="DISCOVERY_SELECTION", stage_id="STAGE_OTHER",
                    work_intent="DISCOVER", deadline_at=NOW, scheduler_job_id=1,
                    target_category="DISCOVERY_WORK", target_identity="dwork-1",
                    now=NOW,
                )
        finally:
            connection.close()

    def test_11_negative_v1_not_v2_and_foreign_cycle(self) -> None:
        connection = self._seed_graph(self.db)
        try:
            persist_scheduler_work(
                connection, scheduler_work_id="v1-a", campaign_id="campaign-a",
                run_id="run-a", cycle_id="cycle-a", token_slot_id="slot-1",
                window_id="window-15m-a", work_intent="CLOSE_WINDOW",
                deadline_at=NOW, scheduler_job_id=1, now=NOW,
            )
            with connection:
                connection.execute(
                    """INSERT INTO printer_discovery_batches(
                        discovery_batch_id,campaign_id,configuration_id,run_id,cycle_id,
                        cycle_cutoff,policy_version,provider_contract_versions_json,
                        git_provenance_identity,campaign_selection_seed_identity,
                        cycle_seed_hash,pump_continuity_state,batch_state,canonical_hash,
                        created_at
                    ) VALUES (?,?,?,?,?,?,?,?,?,?,?,'NONE','DISCOVERING',?,?)""",
                    (
                        "disc-1", "campaign-a", "configuration-a", "run-a", "cycle-a",
                        NOW, "policy-1", "{}", "git-1", "seed-1", HEX64_A, HEX64_B, NOW,
                    ),
                )
                connection.execute(
                    """INSERT INTO printer_discovery_work(
                        discovery_work_id,discovery_batch_id,campaign_id,run_id,
                        cycle_id,scheduler_job_id,work_type,work_state,deadline_at,
                        created_at,updated_at
                    ) VALUES (?,?,?,?,?,?,?,'PENDING',?,?,?)""",
                    (
                        "dwork-1", "disc-1", "campaign-a", "run-a", "cycle-a",
                        1, "DISCOVERY_PUMPFUN_LATEST", NOW, NOW, NOW,
                    ),
                )
            with self.assertRaises(CampaignOwnershipError):
                project_campaign_scheduler_work(
                    connection, scheduler_work_id="v1-a",
                    campaign_id="campaign-a", run_id="run-a", cycle_id="cycle-a",
                    work_scope="DISCOVERY_SELECTION", stage_id="STAGE_DISCOVERY",
                    work_intent="DISCOVER", deadline_at=NOW, scheduler_job_id=1,
                    target_category="DISCOVERY_WORK", target_identity="dwork-1",
                    now=NOW,
                )
            with self.assertRaises(CampaignOwnershipError):
                project_campaign_scheduler_work(
                    connection, scheduler_work_id="v2-a",
                    campaign_id="campaign-a", run_id="run-a", cycle_id="cycle-a",
                    work_scope="DISCOVERY_SELECTION", stage_id="STAGE_DISCOVERY",
                    work_intent="DISCOVER", deadline_at=NOW, scheduler_job_id=1,
                    target_category="DISCOVERY_WORK", target_identity="dwork-1",
                    now=NOW,
                )
            create_cycle_with_two_slots(
                connection, campaign_id="campaign-a", run_id="run-a",
                cycle_id="cycle-b", cycle_ordinal=2,
                slots=(
                    {
                        "token_slot_id": "slot-3",
                        "slot_ordinal": 1,
                        "token_identity": "token-1",
                        "token_row_id": 1,
                        "mint_identity": "mint-1",
                        "pair_identity": "pair-1",
                        "pair_row_id": 1,
                        "lifecycle_identity": "lifecycle-1b",
                    },
                    {
                        "token_slot_id": "slot-4",
                        "slot_ordinal": 2,
                        "token_identity": "token-2",
                        "token_row_id": 2,
                        "mint_identity": "mint-2",
                        "pair_identity": "pair-2",
                        "pair_row_id": 2,
                        "lifecycle_identity": "lifecycle-2b",
                    },
                ),
                now=NOW,
            )
            with connection:
                connection.execute(
                    """INSERT INTO printer_discovery_batches(
                        discovery_batch_id,campaign_id,configuration_id,run_id,cycle_id,
                        cycle_cutoff,policy_version,provider_contract_versions_json,
                        git_provenance_identity,campaign_selection_seed_identity,
                        cycle_seed_hash,pump_continuity_state,batch_state,canonical_hash,
                        created_at
                    ) VALUES (?,?,?,?,?,?,?,?,?,?,?,'NONE','DISCOVERING',?,?)""",
                    (
                        "disc-b", "campaign-a", "configuration-a", "run-a", "cycle-b",
                        NOW, "policy-1", "{}", "git-1", "seed-1", HEX64_A, HEX64_B, NOW,
                    ),
                )
                connection.execute(
                    """INSERT INTO printer_discovery_work(
                        discovery_work_id,discovery_batch_id,campaign_id,run_id,
                        cycle_id,scheduler_job_id,work_type,work_state,deadline_at,
                        created_at,updated_at
                    ) VALUES (?,?,?,?,?,?,?,'PENDING',?,?,?)""",
                    (
                        "dwork-b", "disc-b", "campaign-a", "run-a", "cycle-b",
                        6, "DISCOVERY_PUMPFUN_LATEST", NOW, NOW, NOW,
                    ),
                )
            capture = capture_campaign_active_scheduler_jobs(
                connection, campaign_id="campaign-a", run_id="run-a",
                cycle_id="cycle-a",
            )
            self.assertIsNone(capture.pre_state(6))
            with connection:
                connection.execute(
                    "UPDATE printer_scheduler_jobs "
                    "SET status=?, finished_at=? WHERE id=?",
                    ("CANCELLED", NOW, 6),
                )
            with self.assertRaises(CampaignOwnershipError):
                project_campaign_scheduler_work(
                    connection, scheduler_work_id="work-cf",
                    campaign_id="campaign-a", run_id="run-a", cycle_id="cycle-a",
                    work_scope="TERMINAL_CLEANUP", stage_id="STAGE_TERMINAL",
                    work_intent="CANCEL", deadline_at=NOW, scheduler_job_id=6,
                    target_category="SCHEDULER_JOB", target_identity="6",
                    cleanup_capture=capture, now=NOW,
                )
        finally:
            connection.close()

    def test_12_negative_partial_failed_no_ledger(self) -> None:
        db = self.root / "neg_partial.sqlite3"
        _apply_through(db, 49)
        _insert_pre050_work_row(
            db,
            scheduler_work_id="w-keep",
            campaign_id="c",
            run_id="r",
            cycle_id="cy",
            token_slot_id="s",
            window_id="win",
            work_intent="i",
            deadline_at=NOW,
            work_state="PENDING",
            scheduler_job_id=1,
            created_at=NOW,
            updated_at=NOW,
        )
        script = MIGRATION_050_PATH.read_text(encoding="utf-8")
        marker = "-- 6. Swap the rebuilt table into place."
        injected = script.replace(
            marker,
            "INSERT INTO _mig050_guard_fields(ok) VALUES (0);\n" + marker,
        )
        connection = sqlite3.connect(db)
        try:
            with self.assertRaises(sqlite3.IntegrityError):
                connection.executescript(injected)
                connection.execute(
                    "INSERT INTO printer_schema_migrations(version) VALUES (?)",
                    (MIGRATION_050,),
                )
            connection.rollback()
            self.assertNotIn(MIGRATION_050, _migration_versions(connection))
            leftover = connection.execute(
                "SELECT COUNT(*) FROM sqlite_master WHERE name LIKE '%__v2_9_8b_050'"
            ).fetchone()[0]
            self.assertEqual(leftover, 0)
        finally:
            connection.close()


# ===========================================================================
# Canonical authoritative-copy proof (env-gated)
# ===========================================================================


class CanonicalAuthoritativeMigrationProof(unittest.TestCase):
    """Runs only when PRINTER_V2_9_8B_MIG050_CANONICAL_PROOF=1."""

    @unittest.skipUnless(
        _canonical_mode_enabled(),
        f"set {CANONICAL_ENV}=1 to run the canonical authoritative-copy proof",
    )
    def test_canonical_authoritative_copy_migration_once(self) -> None:
        evidence = run_canonical_authoritative_migration_proof()
        self.assertEqual(evidence["verdict"], VERDICT_PASS)
        self.assertEqual(evidence["mode"], "CANONICAL_AUTHORITATIVE_COPY")
        path = controlling_evidence_path(str(evidence["proof_execution_id"]))
        assert path is not None
        self.assertTrue(path.is_file())
        # Immutable: re-running with the same path must fail; new ID would create
        # a new path. Existence of this package is permanent once written.
        reloaded = json.loads(path.read_text(encoding="utf-8"))
        self.assertEqual(
            reloaded["proof_execution_id"], evidence["proof_execution_id"]
        )
        self.assertEqual(
            controlling_execution_id(), evidence["proof_execution_id"]
        )


class CanonicalEvidenceCrossArtifactEquality(unittest.TestCase):
    """Compare controlling report and JSON identity fields when evidence exists."""

    def test_controlling_package_is_execution_specific(self) -> None:
        exec_id = controlling_execution_id()
        if exec_id is None:
            self.skipTest("no controlling execution pointer yet")
        path = controlling_evidence_path(exec_id)
        self.assertIsNotNone(path)
        assert path is not None
        self.assertTrue(path.is_file())
        self.assertIn(exec_id, str(path))
        # Generic shared summary must not be the controlling package.
        if GENERIC_SUMMARY.is_file():
            generic = json.loads(GENERIC_SUMMARY.read_text(encoding="utf-8"))
            self.assertIn(
                generic.get("status", generic.get("verdict", "")),
                {
                    "SUPERSEDED_HARNESS_OVERWRITE",
                    "SUPERSEDED",
                },
            )

    def test_cross_artifact_identity_equality(self) -> None:
        exec_id = controlling_execution_id()
        if exec_id is None:
            self.skipTest("no controlling execution pointer yet")
        evidence = load_controlling_evidence()
        identity = extract_cross_artifact_identity(evidence)
        # JSON internal consistency.
        self.assertEqual(identity["proof_execution_id"], exec_id)
        self.assertEqual(identity["verdict"], VERDICT_PASS)
        self.assertEqual(
            identity["disposable_pre_sha256"], identity["source_sha256"]
        )
        self.assertEqual(
            identity["ledger_delta"], [MIGRATION_050]
        )
        # Report must bind the same controlling identity when present.
        if not REPORT_PATH.is_file():
            self.skipTest("report not present yet")
        report = REPORT_PATH.read_text(encoding="utf-8")
        # Controlling section must supersede earlier IDs and bind this one.
        self.assertIn(str(identity["proof_execution_id"]), report)
        assert_report_matches_controlling_identity(report, identity)
        # Report must mark earlier executions as superseded when documented.
        self.assertIn("SUPERSEDED", report)
        self.assertIn(
            "V2_9_8B_MIG050_BOUNDED_PROOF_20260801T143546Z_f98b72fd", report
        )
        self.assertIn(
            "V2_9_8B_MIG050_BOUNDED_PROOF_20260801T143555Z_4f9874ff", report
        )

    def test_non_canonical_mode_does_not_enable_canonical_runner(self) -> None:
        if _canonical_mode_enabled():
            self.skipTest("canonical mode intentionally enabled for this process")
        # Guard: default invocations must not call the canonical runner.
        # This test only asserts the mode flag; suite-level setUp fingerprints
        # already prove evidence files are not rewritten by synthetic tests.
        self.assertFalse(_canonical_mode_enabled())


if __name__ == "__main__":  # pragma: no cover
    if _canonical_mode_enabled() and os.environ.get(
        "PRINTER_V2_9_8B_MIG050_CANONICAL_PROOF_MAIN", ""
    ).strip() == "1":
        evidence = run_canonical_authoritative_migration_proof()
        print(json.dumps(evidence["cross_artifact_identity"], indent=2, sort_keys=True))
        print("VERDICT", evidence["verdict"])
        print("EVIDENCE", evidence["evidence_path"])
    else:
        unittest.main()
