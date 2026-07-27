"""Exact V2-9.8B.18 residue recovery; no sources, Scheduler runtime or retry."""

from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import sqlite3
import subprocess
from typing import Any, Callable

from printer_v1.db import apply_migrations
from printer_v1.operator_cli.campaign_active_work import campaign_active_work_report
from printer_v1.operator_cli.final_campaign_report import LOCKED_CAPABILITY_TABLES
from printer_v1.operator_cli.operational_backup_restore_preflight import (
    operational_backup_restore_preflight,
)
from printer_v1.operator_cli.unified_terminal_closure import (
    build_campaign_terminal_report,
    reconcile_campaign_terminal,
    write_campaign_terminal_report,
)


EXECUTION_ID = "20260727T161750Z-95e40c3efae3"
FACTORY_RUN_ID = "42afd94c-2e5a-40c3-939d-e1941a4033e4"
CAMPAIGN_ID = f"{EXECUTION_ID}-campaign"
CONFIGURATION_ID = f"{EXECUTION_ID}-configuration"
CAMPAIGN_RUN_ID = f"{EXECUTION_ID}-campaign-run"
CYCLE_ID = f"{EXECUTION_ID}-cycle"
SUPERVISION_ID = f"{EXECUTION_ID}-supervision"
OWNER_ID = f"{EXECUTION_ID}-owner"
ORIGINAL_REPORT_ID = f"{EXECUTION_ID}-report"
RECOVERY_REPORT_ID = f"{EXECUTION_ID}-v2-9-8b-18-recovery-report"
TERMINAL_CAUSE = "LEASE_RENEWAL_UNCONFIRMED_HISTORICAL_SUBTYPE_UNKNOWN"
SLOTS = (
    (f"slot-{EXECUTION_ID}-cycle-1", 1, 20, 24, 18),
    (f"slot-{EXECUTION_ID}-cycle-2", 2, 21, 25, 19),
)
ACTIVE_SCHEDULER_STATES = ("PENDING", "RUNNING", "COOLDOWN")


class HeartbeatTerminalizationRecoveryError(RuntimeError):
    """Fail-closed exact recovery contract violation."""


def _iso(now: datetime | None = None) -> str:
    return (now or datetime.now(timezone.utc)).astimezone(timezone.utc).isoformat()


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _read_only(path: Path) -> sqlite3.Connection:
    connection = sqlite3.connect(
        f"file:{path.resolve().as_posix()}?mode=ro", uri=True, timeout=0.0
    )
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA query_only=ON")
    return connection


def _canonical_table_hash(connection: sqlite3.Connection, table: str) -> str:
    columns = [str(row[1]) for row in connection.execute(
        f'PRAGMA table_info("{table}")'
    ).fetchall()]
    rows = [dict(row) for row in connection.execute(
        f'SELECT * FROM "{table}"'
    ).fetchall()]
    rows.sort(key=lambda row: repr(tuple(row.get(column) for column in columns)))
    payload = json.dumps(
        rows, sort_keys=True, separators=(",", ":"), ensure_ascii=True,
        allow_nan=False,
    ) + "\n"
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _locked_hashes(connection: sqlite3.Connection) -> dict[str, str]:
    return {
        table: _canonical_table_hash(connection, table)
        for table in LOCKED_CAPABILITY_TABLES
    }


def _global_active_scheduler(connection: sqlite3.Connection) -> int:
    placeholders = ",".join("?" for _ in ACTIVE_SCHEDULER_STATES)
    return int(connection.execute(
        f"""SELECT COUNT(*) FROM printer_scheduler_jobs
             WHERE status IN ({placeholders})
                OR locked_at IS NOT NULL OR lock_owner IS NOT NULL""",
        ACTIVE_SCHEDULER_STATES,
    ).fetchone()[0])


def _default_process_probe() -> bool:
    try:
        result = subprocess.run(
            ["ps", "-axo", "pid=,command="], capture_output=True, text=True,
            timeout=5.0, check=False, shell=False,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise HeartbeatTerminalizationRecoveryError(
            "Printer process state could not be verified"
        ) from exc
    if result.returncode != 0:
        raise HeartbeatTerminalizationRecoveryError(
            "Printer process state could not be verified"
        )
    own_pid = os.getpid()
    for line in result.stdout.splitlines():
        fields = line.strip().split(maxsplit=1)
        if len(fields) != 2:
            continue
        try:
            pid = int(fields[0])
        except ValueError:
            continue
        command = fields[1]
        if pid == own_pid:
            continue
        if (
            "operational_memory_factory_command" in command
            or "Start-PrinterV1-MemoryFactory" in command
            or "printer-run-v2-9-8-memory-factory" in command
        ):
            return True
    return False


def _integrity(connection: sqlite3.Connection) -> tuple[str, int]:
    integrity = str(connection.execute("PRAGMA integrity_check").fetchone()[0])
    foreign_keys = len(connection.execute("PRAGMA foreign_key_check").fetchall())
    return integrity, foreign_keys


def _preflight(connection: sqlite3.Connection) -> dict[str, Any]:
    integrity, foreign_keys = _integrity(connection)
    if integrity != "ok" or foreign_keys:
        raise HeartbeatTerminalizationRecoveryError(
            "authoritative SQLite integrity or foreign keys are not clean"
        )
    factory = connection.execute(
        "SELECT * FROM printer_memory_factory_runs WHERE run_id=?",
        (FACTORY_RUN_ID,),
    ).fetchone()
    if factory is None or factory["run_status"] != "RUNNING":
        raise HeartbeatTerminalizationRecoveryError(
            "exact RUNNING factory residue was not proven"
        )
    if int(connection.execute(
        "SELECT COUNT(*) FROM printer_memory_factory_run_steps WHERE run_id=?",
        (FACTORY_RUN_ID,),
    ).fetchone()[0]) != 0:
        raise HeartbeatTerminalizationRecoveryError(
            "exact factory run is not a zero-step residue"
        )
    rows = connection.execute(
        """SELECT token_slot_id,slot_ordinal,token_row_id,pair_row_id,
                  tracking_queue_id,token_state
           FROM printer_memory_factory_campaign_token_slots
           WHERE campaign_id=? AND run_id=? AND cycle_id=?
           ORDER BY slot_ordinal""",
        (CAMPAIGN_ID, CAMPAIGN_RUN_ID, CYCLE_ID),
    ).fetchall()
    observed = tuple(
        (
            str(row["token_slot_id"]), int(row["slot_ordinal"]),
            int(row["token_row_id"]), int(row["pair_row_id"]),
            int(row["tracking_queue_id"]),
        )
        for row in rows if row["token_state"] == "SELECTED"
    )
    if observed != SLOTS:
        raise HeartbeatTerminalizationRecoveryError(
            "exact campaign slot ownership was not proven"
        )
    for _slot, _ordinal, token_id, pair_id, queue_id in SLOTS:
        queue = connection.execute(
            "SELECT token_id,pair_id,queue_status FROM printer_tracking_queue WHERE id=?",
            (queue_id,),
        ).fetchone()
        if queue is None or (
            int(queue["token_id"]), int(queue["pair_id"]), queue["queue_status"]
        ) != (token_id, pair_id, "QUEUED"):
            raise HeartbeatTerminalizationRecoveryError(
                "exact campaign queue ownership was not proven"
            )
    supervision = connection.execute(
        """SELECT * FROM printer_memory_factory_campaign_supervision
           WHERE supervision_id=? AND campaign_id=? AND configuration_id=?
             AND run_id=? AND owner_id=?""",
        (SUPERVISION_ID, CAMPAIGN_ID, CONFIGURATION_ID, CAMPAIGN_RUN_ID, OWNER_ID),
    ).fetchone()
    if supervision is None or supervision["supervision_state"] != "TERMINAL":
        raise HeartbeatTerminalizationRecoveryError(
            "exact terminal supervision ownership was not proven"
        )
    if Path(str(supervision["lease_lock_path"])).exists():
        raise HeartbeatTerminalizationRecoveryError("campaign lease still exists")
    if _global_active_scheduler(connection):
        raise HeartbeatTerminalizationRecoveryError(
            "active or locked Scheduler work exists"
        )
    work = campaign_active_work_report(
        connection, factory_run_id=FACTORY_RUN_ID, campaign_id=CAMPAIGN_ID,
        run_id=CAMPAIGN_RUN_ID, cycle_id=CYCLE_ID,
    )
    if not work["clean_terminal"]:
        raise HeartbeatTerminalizationRecoveryError("campaign active work exists")
    original = connection.execute(
        "SELECT report_json FROM printer_memory_factory_campaign_reports WHERE report_id=?",
        (ORIGINAL_REPORT_ID,),
    ).fetchone()
    if original is None:
        raise HeartbeatTerminalizationRecoveryError("original terminal report is missing")
    original_payload = json.loads(str(original["report_json"]))
    if original_payload.get("identity", {}).get("factory_run_id") is not None:
        raise HeartbeatTerminalizationRecoveryError(
            "original report no longer has the proven missing factory identity"
        )
    return {
        "integrity": integrity,
        "foreign_key_violations": foreign_keys,
        "locked_hashes": _locked_hashes(connection),
        "original_report_json": str(original["report_json"]),
        "campaign_counts": {
            "campaigns": int(connection.execute(
                "SELECT COUNT(*) FROM printer_memory_factory_campaigns"
            ).fetchone()[0]),
            "campaign_runs": int(connection.execute(
                "SELECT COUNT(*) FROM printer_memory_factory_campaign_runs"
            ).fetchone()[0]),
            "factory_runs": int(connection.execute(
                "SELECT COUNT(*) FROM printer_memory_factory_runs"
            ).fetchone()[0]),
        },
    }


def _verify_recovered(
    connection: sqlite3.Connection,
    *,
    locked_hashes: dict[str, str],
    original_report_json: str,
    campaign_counts: dict[str, int],
) -> dict[str, Any]:
    integrity, foreign_keys = _integrity(connection)
    factory = connection.execute(
        "SELECT run_status,stop_reason FROM printer_memory_factory_runs WHERE run_id=?",
        (FACTORY_RUN_ID,),
    ).fetchone()
    if factory is None or tuple(factory) != ("SAFE_STOPPED", TERMINAL_CAUSE):
        raise HeartbeatTerminalizationRecoveryError(
            "factory residue did not reach the exact terminal disposition"
        )
    for slot_id, _ordinal, _token, _pair, queue_id in SLOTS:
        slot = connection.execute(
            "SELECT token_state,first_terminal_cause FROM "
            "printer_memory_factory_campaign_token_slots WHERE token_slot_id=?",
            (slot_id,),
        ).fetchone()
        queue = connection.execute(
            "SELECT queue_status,tracking_action FROM printer_tracking_queue WHERE id=?",
            (queue_id,),
        ).fetchone()
        if slot is None or tuple(slot) != ("MANUAL_REVIEW", TERMINAL_CAUSE):
            raise HeartbeatTerminalizationRecoveryError("slot terminal disposition failed")
        if queue is None or tuple(queue) != ("SKIPPED", "MANUAL_REVIEW"):
            raise HeartbeatTerminalizationRecoveryError("queue terminal disposition failed")
    report_row = connection.execute(
        "SELECT report_json FROM printer_memory_factory_campaign_reports WHERE report_id=?",
        (RECOVERY_REPORT_ID,),
    ).fetchone()
    if report_row is None:
        raise HeartbeatTerminalizationRecoveryError("recovery report is missing")
    report = json.loads(str(report_row["report_json"]))
    if (
        report.get("identity", {}).get("factory_run_id") != FACTORY_RUN_ID
        or report.get("terminal", {}).get("first_terminal_cause") != TERMINAL_CAUSE
        or report.get("reconciliation", {}).get("factory_run") != "SAFE_STOPPED"
    ):
        raise HeartbeatTerminalizationRecoveryError("recovery report is not truthful")
    original = connection.execute(
        "SELECT report_json FROM printer_memory_factory_campaign_reports WHERE report_id=?",
        (ORIGINAL_REPORT_ID,),
    ).fetchone()
    if original is None or str(original["report_json"]) != original_report_json:
        raise HeartbeatTerminalizationRecoveryError(
            "original incident report evidence changed"
        )
    heartbeat_rows = int(connection.execute(
        "SELECT COUNT(*) FROM printer_memory_factory_campaign_heartbeat_failures "
        "WHERE supervision_id=?", (SUPERVISION_ID,),
    ).fetchone()[0])
    if heartbeat_rows:
        raise HeartbeatTerminalizationRecoveryError(
            "historical heartbeat subtype was invented"
        )
    if _locked_hashes(connection) != locked_hashes:
        raise HeartbeatTerminalizationRecoveryError(
            "retrieval or financial state changed"
        )
    current_counts = {
        "campaigns": int(connection.execute(
            "SELECT COUNT(*) FROM printer_memory_factory_campaigns"
        ).fetchone()[0]),
        "campaign_runs": int(connection.execute(
            "SELECT COUNT(*) FROM printer_memory_factory_campaign_runs"
        ).fetchone()[0]),
        "factory_runs": int(connection.execute(
            "SELECT COUNT(*) FROM printer_memory_factory_runs"
        ).fetchone()[0]),
    }
    if current_counts != campaign_counts:
        raise HeartbeatTerminalizationRecoveryError("retry, restart or successor detected")
    if _global_active_scheduler(connection):
        raise HeartbeatTerminalizationRecoveryError("active Scheduler work remains")
    work = campaign_active_work_report(
        connection, factory_run_id=FACTORY_RUN_ID, campaign_id=CAMPAIGN_ID,
        run_id=CAMPAIGN_RUN_ID, cycle_id=CYCLE_ID,
    )
    if not work["clean_terminal"]:
        raise HeartbeatTerminalizationRecoveryError("active campaign work remains")
    if integrity != "ok" or foreign_keys:
        raise HeartbeatTerminalizationRecoveryError("post-recovery SQLite checks failed")
    return {
        "integrity": integrity,
        "foreign_key_violations": foreign_keys,
        "factory_run_id": FACTORY_RUN_ID,
        "factory_run_status": "SAFE_STOPPED",
        "terminal_cause": TERMINAL_CAUSE,
        "active_work": 0,
        "active_scheduler_work": 0,
        "retrieval_financial_deltas": {
            table: 0 for table in LOCKED_CAPABILITY_TABLES
        },
        "retry_created": False,
        "restart_created": False,
        "successor_created": False,
    }


def recover_exact_heartbeat_terminal_residue(
    *,
    operator_approved: bool,
    db_path: str | Path,
    artifact_root: str | Path,
    recovery_root: str | Path,
    process_probe: Callable[[], bool] = _default_process_probe,
    now: datetime | None = None,
) -> dict[str, Any]:
    """Recover only the pinned V2-9.8B.17 residue after all read-only gates."""
    if not operator_approved:
        raise HeartbeatTerminalizationRecoveryError(
            "explicit operator recovery approval is required"
        )
    database = Path(db_path).resolve()
    reports = Path(artifact_root).resolve() / "reports"
    instant = now or datetime.now(timezone.utc)

    connection = _read_only(database)
    try:
        recovery_row = connection.execute(
            "SELECT report_json FROM printer_memory_factory_campaign_reports "
            "WHERE report_id=?", (RECOVERY_REPORT_ID,),
        ).fetchone()
        if recovery_row is not None:
            original = connection.execute(
                "SELECT report_json FROM printer_memory_factory_campaign_reports "
                "WHERE report_id=?", (ORIGINAL_REPORT_ID,),
            ).fetchone()
            if original is None:
                raise HeartbeatTerminalizationRecoveryError(
                    "original terminal report is missing"
                )
            verification = _verify_recovered(
                connection,
                locked_hashes=_locked_hashes(connection),
                original_report_json=str(original["report_json"]),
                campaign_counts={
                    "campaigns": int(connection.execute(
                        "SELECT COUNT(*) FROM printer_memory_factory_campaigns"
                    ).fetchone()[0]),
                    "campaign_runs": int(connection.execute(
                        "SELECT COUNT(*) FROM printer_memory_factory_campaign_runs"
                    ).fetchone()[0]),
                    "factory_runs": int(connection.execute(
                        "SELECT COUNT(*) FROM printer_memory_factory_runs"
                    ).fetchone()[0]),
                },
            )
            return {
                "status": "ALREADY_RECOVERED_IDEMPOTENT",
                "database_writes": 0,
                "source_calls": 0,
                "scheduler_runtime_calls": 0,
                **verification,
            }
        preflight = _preflight(connection)
    finally:
        connection.close()
    if process_probe():
        raise HeartbeatTerminalizationRecoveryError("active Printer process exists")

    recovery_directory = Path(recovery_root).resolve()
    recovery_directory.mkdir(parents=True, exist_ok=False)
    backup_path = recovery_directory / "printer_v1.pre-v2-9-8b-18-recovery.sqlite3"
    restore_path = recovery_directory / "printer_v1.v2-9-8b-18-restore.sqlite3"
    source_hash = _sha256(database)
    backup = operational_backup_restore_preflight(
        database,
        expected_source_path=database,
        expected_source_identity=f"sha256:{source_hash}",
        backup_path=backup_path,
        disposable_restore_root=recovery_directory,
        restore_path=restore_path,
    )
    if backup.get("status") != "OPERATIONAL_BACKUP_RESTORE_PREFLIGHT_READY":
        raise HeartbeatTerminalizationRecoveryError("fresh recovery backup failed")

    apply_migrations(database)
    reconciliation = reconcile_campaign_terminal(
        database,
        campaign_id=CAMPAIGN_ID,
        run_id=CAMPAIGN_RUN_ID,
        cycle_id=CYCLE_ID,
        terminal_cause=TERMINAL_CAUSE,
        run_status="FAILED",
        factory_run_id=FACTORY_RUN_ID,
        lifecycle_started=True,
        now=_iso(instant),
    )
    connection = _read_only(database)
    try:
        provenance_row = connection.execute(
            "SELECT launch_provenance_json FROM "
            "printer_memory_factory_campaign_configurations "
            "WHERE configuration_id=? AND campaign_id=?",
            (CONFIGURATION_ID, CAMPAIGN_ID),
        ).fetchone()
        if provenance_row is None:
            raise HeartbeatTerminalizationRecoveryError(
                "configuration provenance is missing"
            )
        provenance = json.loads(str(provenance_row["launch_provenance_json"]))
    finally:
        connection.close()
    report_payload = build_campaign_terminal_report(
        campaign_id=CAMPAIGN_ID,
        configuration_id=CONFIGURATION_ID,
        run_id=CAMPAIGN_RUN_ID,
        cycle_id=CYCLE_ID,
        report_id=RECOVERY_REPORT_ID,
        factory_run_id=FACTORY_RUN_ID,
        execution_id=EXECUTION_ID,
        terminal_status="FAILED",
        terminal_cause=TERMINAL_CAUSE,
        run_status="FAILED",
        lifecycle_started=True,
        reconciliation=reconciliation,
        forbidden_deltas={table: 0 for table in LOCKED_CAPABILITY_TABLES},
        launch_git_provenance=provenance,
        fault_details={
            "historical_heartbeat_subtype": "UNKNOWN_NOT_PERSISTED",
            "historical_subtype_inferred": False,
        },
    )
    report = write_campaign_terminal_report(
        database,
        reports,
        report_id=RECOVERY_REPORT_ID,
        campaign_id=CAMPAIGN_ID,
        configuration_id=CONFIGURATION_ID,
        report=report_payload,
        now=instant,
    )
    connection = _read_only(database)
    try:
        verification = _verify_recovered(
            connection,
            locked_hashes=preflight["locked_hashes"],
            original_report_json=preflight["original_report_json"],
            campaign_counts=preflight["campaign_counts"],
        )
    finally:
        connection.close()
    return {
        "status": "RECOVERED",
        "database_writes": 1,
        "source_calls": 0,
        "scheduler_runtime_calls": 0,
        "backup_path": str(backup_path),
        "backup_sha256": _sha256(backup_path),
        "report_artifact": report.get("artifact_path"),
        **verification,
    }


__all__ = [
    "HeartbeatTerminalizationRecoveryError",
    "recover_exact_heartbeat_terminal_residue",
]
