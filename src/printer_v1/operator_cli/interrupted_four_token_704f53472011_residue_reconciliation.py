"""Exact recovery owner for consumed interrupted execution 704f53472011.

This module is intentionally hard-bound.  It does not fetch sources, run the
Scheduler, resume the consumed campaign, create a successor, or invent
no-admission evidence.  Mutation is delegated to the already-reviewed parent
interruption / shared terminal owners.
"""

from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import sqlite3
import subprocess
from typing import Any, Callable

from printer_v1.operator_cli.campaign_active_work import campaign_active_work_report
from printer_v1.operator_cli.campaign_supervision import cleanup_campaign_supervision
from printer_v1.operator_cli.final_campaign_report import LOCKED_CAPABILITY_TABLES
from printer_v1.operator_cli.four_token_factory_adapter import (
    finalize_four_token_shared_terminal,
)
from printer_v1.operator_cli.unified_terminal_closure import reconcile_campaign_terminal


EXECUTION_ID = "20260828T220832Z-704f53472011"
AUTHORIZATION_ID = "V2_9_8B_FOUR_TOKEN_STD4H_AUTH_20260828T211924Z_5fcb1bf5"
CAMPAIGN_ID = f"{EXECUTION_ID}-campaign"
CONFIGURATION_ID = f"{EXECUTION_ID}-configuration"
CAMPAIGN_RUN_ID = f"{EXECUTION_ID}-campaign-run"
CYCLE_ID = f"{EXECUTION_ID}-cycle"
SUPERVISION_ID = f"{EXECUTION_ID}-supervision"
OWNER_ID = f"{EXECUTION_ID}-owner"
FACTORY_RUN_ID = "42ef6217-3932-4846-948d-e2103fd34309"
ATTEMPT_ID = (
    "pre-admission:20260828T220832Z-704f53472011-campaign:"
    "20260828T220832Z-704f53472011-campaign-run:"
    "42ef6217-3932-4846-948d-e2103fd34309:c0002"
)
SCHEDULER_JOB_ID = 2808
TERMINAL_CAUSE = "LEASE_RENEWAL_SQLITE_LOCKED"
INTERRUPTION_CAUSE = f"PARENT_CAMPAIGN_INTERRUPTED:{TERMINAL_CAUSE}"
EXPECTED_DB_SHA256 = "c90376b9e26d0f2953a8d9b2fd5fee01d80ac4984510113e595fd1ccc3d9033d"
EXPECTED_APPLICATION_MARKER_SHA256 = (
    "9099e5f31949bd9dc219dbe58a301e095df1600cd5698b705841ee33bfd0c76a"
)
APPLICATION_MARKER_PATH = Path(
    "/Users/Dtwo1/PrinterOperations/v2-9-8/"
    "four-token-standard-four-hour-one-shot-applications/"
    f"{AUTHORIZATION_ID}/application-marker.json"
)
LEASE_LOCK_PATH = Path(
    "/Users/Dtwo1/PrinterOperations/v2-9-8/"
    f"{EXECUTION_ID}/campaign.lease.lock"
)
ACTIVE_SCHEDULER_STATES = ("PENDING", "RUNNING", "COOLDOWN")
EXPECTED_ATTEMPT_EVIDENCE_COUNT = 19
EXPECTED_OPPORTUNITY_EXECUTED_COUNT = 9
EXPECTED_SOURCE_REQUEST_TERMINAL_COUNT = 10


class InterruptedFourTokenResidueRecoveryError(RuntimeError):
    """Fail-closed exact-residue recovery contract violation."""


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


def _integrity(connection: sqlite3.Connection) -> tuple[str, int]:
    integrity = str(connection.execute("PRAGMA integrity_check").fetchone()[0])
    foreign_keys = len(connection.execute("PRAGMA foreign_key_check").fetchall())
    return integrity, foreign_keys


def _canonical_rows_hash(rows: list[sqlite3.Row]) -> str:
    payload = [dict(row) for row in rows]
    return hashlib.sha256(
        (json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
         + "\n").encode("utf-8")
    ).hexdigest()


def _canonical_table_hash(connection: sqlite3.Connection, table: str) -> str:
    columns = [
        str(row[1])
        for row in connection.execute(f'PRAGMA table_info("{table}")').fetchall()
    ]
    rows = [
        dict(row)
        for row in connection.execute(f'SELECT * FROM "{table}"').fetchall()
    ]
    rows.sort(key=lambda row: repr(tuple(row.get(column) for column in columns)))
    payload = json.dumps(
        rows, sort_keys=True, separators=(",", ":"), ensure_ascii=True, allow_nan=False
    ) + "\n"
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _locked_hashes(connection: sqlite3.Connection) -> dict[str, str]:
    return {
        table: _canonical_table_hash(connection, table)
        for table in LOCKED_CAPABILITY_TABLES
    }


def _default_process_probe() -> bool:
    try:
        result = subprocess.run(
            ["ps", "-axo", "pid=,command="],
            capture_output=True,
            text=True,
            timeout=5.0,
            check=False,
            shell=False,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise InterruptedFourTokenResidueRecoveryError(
            "Printer/Governor/Scheduler process state could not be verified"
        ) from exc
    if result.returncode != 0:
        raise InterruptedFourTokenResidueRecoveryError(
            "Printer/Governor/Scheduler process state could not be verified"
        )
    own_pid = os.getpid()
    markers = (
        "operational_memory_factory_command",
        "Start-PrinterV1-MemoryFactory",
        "printer-run-v2-9-8-memory-factory",
        "central_scheduler",
    )
    for line in result.stdout.splitlines():
        fields = line.strip().split(maxsplit=1)
        if len(fields) != 2:
            continue
        try:
            pid = int(fields[0])
        except ValueError:
            continue
        if pid == own_pid:
            continue
        command = fields[1]
        if any(marker in command for marker in markers):
            return True
    return False


def _default_git_head_probe(repository_root: Path) -> str:
    result = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=repository_root,
        capture_output=True,
        text=True,
        timeout=5.0,
        check=False,
        shell=False,
    )
    if result.returncode != 0:
        raise InterruptedFourTokenResidueRecoveryError(
            "exact recovery Git HEAD could not be verified"
        )
    return result.stdout.strip().lower()


def _require_no_sidecars(database: Path) -> None:
    for suffix in ("-wal", "-shm", "-journal"):
        if Path(f"{database}{suffix}").exists():
            raise InterruptedFourTokenResidueRecoveryError(
                f"SQLite sidecar exists: {suffix}"
            )


def _validate_consumed_marker(path: Path, expected_sha256: str) -> dict[str, Any]:
    if not path.is_file() or path.is_symlink():
        raise InterruptedFourTokenResidueRecoveryError(
            "exact consumed authorization marker is missing or unsafe"
        )
    observed_sha = _sha256(path)
    if observed_sha != expected_sha256:
        raise InterruptedFourTokenResidueRecoveryError(
            "exact consumed authorization marker SHA mismatch"
        )
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise InterruptedFourTokenResidueRecoveryError(
            "exact consumed authorization marker is unreadable"
        ) from exc
    if not isinstance(payload, dict) or payload.get("authorization_id") != AUTHORIZATION_ID:
        raise InterruptedFourTokenResidueRecoveryError(
            "exact consumed authorization marker identity mismatch"
        )
    consumed_at = str(payload.get("authorization_consumed_at") or "").strip()
    if not consumed_at or int(payload.get("allowed_invocation_count") or 0) != 1:
        raise InterruptedFourTokenResidueRecoveryError(
            "exact authorization consumption law was not proven"
        )
    for key in (
        "automatic_retry_allowed",
        "manual_rerun_allowed",
        "restart_allowed",
        "resume_allowed",
        "successor_allowed",
    ):
        if payload.get(key) is not False:
            raise InterruptedFourTokenResidueRecoveryError(
                f"consumed authorization non-reuse flag mismatch: {key}"
            )
    return {
        "marker_sha256": observed_sha,
        "authorization_consumed_at": consumed_at,
    }


def _exact_lease_payload(path: Path) -> None:
    if not path.is_file() or path.is_symlink():
        raise InterruptedFourTokenResidueRecoveryError("exact campaign lease is missing")
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise InterruptedFourTokenResidueRecoveryError(
            "exact campaign lease is unreadable"
        ) from exc
    expected = {
        "scope": "OPERATIONAL_CAMPAIGN",
        "supervision_id": SUPERVISION_ID,
        "campaign_id": CAMPAIGN_ID,
        "configuration_id": CONFIGURATION_ID,
        "run_id": CAMPAIGN_RUN_ID,
        "owner_id": OWNER_ID,
    }
    if not isinstance(payload, dict) or any(payload.get(k) != v for k, v in expected.items()):
        raise InterruptedFourTokenResidueRecoveryError(
            "exact campaign lease ownership mismatch"
        )


def _global_active_scheduler(connection: sqlite3.Connection) -> list[sqlite3.Row]:
    placeholders = ",".join("?" for _ in ACTIVE_SCHEDULER_STATES)
    return connection.execute(
        f"""SELECT id,job_kind,status,locked_at,lock_owner
             FROM printer_scheduler_jobs
             WHERE status IN ({placeholders})
                OR locked_at IS NOT NULL OR lock_owner IS NOT NULL
             ORDER BY id""",
        ACTIVE_SCHEDULER_STATES,
    ).fetchall()


def _state_rows(connection: sqlite3.Connection) -> dict[str, sqlite3.Row]:
    queries = {
        "campaign": (
            "SELECT * FROM printer_memory_factory_campaigns WHERE campaign_id=?",
            (CAMPAIGN_ID,),
        ),
        "run": (
            "SELECT * FROM printer_memory_factory_campaign_runs WHERE run_id=? AND campaign_id=?",
            (CAMPAIGN_RUN_ID, CAMPAIGN_ID),
        ),
        "cycle": (
            "SELECT * FROM printer_memory_factory_campaign_cycles WHERE cycle_id=? AND campaign_id=? AND run_id=?",
            (CYCLE_ID, CAMPAIGN_ID, CAMPAIGN_RUN_ID),
        ),
        "factory": (
            "SELECT * FROM printer_memory_factory_runs WHERE run_id=?",
            (FACTORY_RUN_ID,),
        ),
        "supervision": (
            """SELECT * FROM printer_memory_factory_campaign_supervision
               WHERE supervision_id=? AND campaign_id=? AND configuration_id=?
                 AND run_id=? AND owner_id=?""",
            (SUPERVISION_ID, CAMPAIGN_ID, CONFIGURATION_ID, CAMPAIGN_RUN_ID, OWNER_ID),
        ),
        "attempt": (
            """SELECT * FROM printer_pre_admission_discovery_attempts
               WHERE attempt_id=? AND campaign_id=? AND campaign_run_id=?
                 AND authoritative_factory_run_id=? AND proposed_cycle_ordinal=2""",
            (ATTEMPT_ID, CAMPAIGN_ID, CAMPAIGN_RUN_ID, FACTORY_RUN_ID),
        ),
        "job": (
            "SELECT * FROM printer_scheduler_jobs WHERE id=?",
            (SCHEDULER_JOB_ID,),
        ),
    }
    result: dict[str, sqlite3.Row] = {}
    for name, (sql, params) in queries.items():
        rows = connection.execute(sql, params).fetchall()
        if len(rows) != 1:
            raise InterruptedFourTokenResidueRecoveryError(
                f"exact {name} ownership was not proven"
            )
        result[name] = rows[0]
    return result


def _attempt_evidence_snapshot(connection: sqlite3.Connection) -> dict[str, Any]:
    rows = connection.execute(
        """SELECT * FROM printer_pre_admission_attempt_evidence
           WHERE attempt_id=? ORDER BY event_key""",
        (ATTEMPT_ID,),
    ).fetchall()
    counts = {
        str(row["evidence_kind"]): 0 for row in rows
    }
    for row in rows:
        counts[str(row["evidence_kind"])] = counts.get(str(row["evidence_kind"]), 0) + 1
        if int(row["opportunity_ordinal"]) != 0:
            raise InterruptedFourTokenResidueRecoveryError(
                "attempt evidence contains an unproven delayed opportunity"
            )
    if len(rows) != EXPECTED_ATTEMPT_EVIDENCE_COUNT:
        raise InterruptedFourTokenResidueRecoveryError(
            "exact attempt evidence row count mismatch"
        )
    if counts.get("OPPORTUNITY_EXECUTED", 0) != EXPECTED_OPPORTUNITY_EXECUTED_COUNT:
        raise InterruptedFourTokenResidueRecoveryError(
            "exact attempt opportunity evidence mismatch"
        )
    if counts.get("SOURCE_REQUEST_TERMINAL", 0) != EXPECTED_SOURCE_REQUEST_TERMINAL_COUNT:
        raise InterruptedFourTokenResidueRecoveryError(
            "exact attempt source-terminal evidence mismatch"
        )
    return {
        "count": len(rows),
        "sha256": _canonical_rows_hash(rows),
    }


def _classify_state(
    connection: sqlite3.Connection,
    *,
    lease_path: Path,
) -> tuple[str, dict[str, Any]]:
    rows = _state_rows(connection)
    campaign = rows["campaign"]
    run = rows["run"]
    cycle = rows["cycle"]
    factory = rows["factory"]
    supervision = rows["supervision"]
    attempt = rows["attempt"]
    job = rows["job"]

    cycle_exact = (
        str(cycle["cycle_state"]) == "TERMINAL_BLOCKED"
        and str(cycle["first_terminal_cause"] or "") == TERMINAL_CAUSE
    )
    if not cycle_exact:
        raise InterruptedFourTokenResidueRecoveryError(
            "Cycle-1 immutable terminal evidence mismatch"
        )

    pre = (
        str(campaign["campaign_state"]) == "RUNNING"
        and str(run["run_state"]) == "RUNNING"
        and str(run["authoritative_run_id"] or "") == FACTORY_RUN_ID
        and str(factory["run_status"]) == "RUNNING"
        and str(factory["stop_reason"] or "") == TERMINAL_CAUSE
        and str(supervision["supervision_state"]) == "ACTIVE"
        and supervision["cleanup_completed_at"] is None
        and supervision["lease_released_at"] is None
        and str(supervision["lease_lock_path"]) == str(LEASE_LOCK_PATH)
        and str(attempt["attempt_state"]) == "RUNNING"
        and attempt["first_terminal_cause"] is None
        and attempt["consumed_cycle_id"] is None
        and int(attempt["scheduler_job_id"]) == SCHEDULER_JOB_ID
        and str(job["job_kind"]) == "PRE_ADMISSION_DISCOVERY_SELECTION"
        and str(job["status"]) == "PENDING"
        and job["locked_at"] is None
        and job["lock_owner"] is None
    )
    if pre:
        if not lease_path.is_file():
            raise InterruptedFourTokenResidueRecoveryError(
                "exact pre-recovery lease is missing"
            )
        active = _global_active_scheduler(connection)
        if len(active) != 1 or int(active[0]["id"]) != SCHEDULER_JOB_ID:
            raise InterruptedFourTokenResidueRecoveryError(
                "exact sole active Scheduler residue was not proven"
            )
        work = campaign_active_work_report(
            connection,
            factory_run_id=FACTORY_RUN_ID,
            campaign_id=CAMPAIGN_ID,
            run_id=CAMPAIGN_RUN_ID,
            cycle_id=CYCLE_ID,
        )
        if (
            int(work["active_jobs"]) != 1
            or int(work["active_pre_admission_attempts"]) != 1
            or int(work["active_factory_runs"]) != 1
            or bool(work["clean_terminal"])
        ):
            raise InterruptedFourTokenResidueRecoveryError(
                "exact active-work residue shape was not proven"
            )
        return "PRE_RECOVERY", rows

    recovered = (
        str(campaign["campaign_state"]).startswith("TERMINAL_")
        and str(campaign["first_terminal_cause"] or "") == TERMINAL_CAUSE
        and str(run["run_state"]).startswith("TERMINAL_")
        and str(run["first_terminal_cause"] or "") == TERMINAL_CAUSE
        and str(factory["run_status"]) == "SAFE_STOPPED"
        and str(factory["stop_reason"] or "") == TERMINAL_CAUSE
        and str(supervision["supervision_state"]) == "TERMINAL"
        and str(supervision["terminal_status"] or "") == "FAILED"
        and str(supervision["first_terminal_cause"] or "") == TERMINAL_CAUSE
        and supervision["cleanup_completed_at"] is not None
        and supervision["lease_released_at"] is not None
        and str(attempt["attempt_state"]) == "CANCELLED"
        and str(attempt["first_terminal_cause"] or "") == INTERRUPTION_CAUSE
        and attempt["consumed_cycle_id"] is None
        and int(attempt["scheduler_job_id"]) == SCHEDULER_JOB_ID
        and str(job["job_kind"]) == "PRE_ADMISSION_DISCOVERY_SELECTION"
        and str(job["status"]) == "CANCELLED"
        and job["locked_at"] is None
        and job["lock_owner"] is None
        and not lease_path.exists()
    )
    if recovered:
        work = campaign_active_work_report(
            connection,
            factory_run_id=FACTORY_RUN_ID,
            campaign_id=CAMPAIGN_ID,
            run_id=CAMPAIGN_RUN_ID,
            cycle_id=CYCLE_ID,
        )
        if not bool(work["clean_terminal"]):
            raise InterruptedFourTokenResidueRecoveryError(
                "recovered graph still has active work"
            )
        return "RECOVERED", rows

    raise InterruptedFourTokenResidueRecoveryError(
        "database does not match the exact sanctioned pre- or post-recovery shape"
    )


def _inspect(
    *,
    db_path: Path,
    repository_root: Path,
    expected_git_head: str,
    expected_db_sha256: str,
    marker_path: Path,
    expected_marker_sha256: str,
    lease_path: Path,
    process_probe: Callable[[], bool],
    git_head_probe: Callable[[Path], str],
) -> dict[str, Any]:
    if not db_path.is_file() or db_path.is_symlink():
        raise InterruptedFourTokenResidueRecoveryError("exact database is missing or unsafe")
    observed_head = git_head_probe(repository_root).strip().lower()
    if observed_head != expected_git_head.strip().lower():
        raise InterruptedFourTokenResidueRecoveryError("exact recovery Git HEAD mismatch")
    marker = _validate_consumed_marker(marker_path, expected_marker_sha256)
    if process_probe():
        raise InterruptedFourTokenResidueRecoveryError(
            "active Printer/Governor/Scheduler process exists"
        )
    _require_no_sidecars(db_path)

    observed_sha = _sha256(db_path)
    connection = _read_only(db_path)
    try:
        integrity, foreign_keys = _integrity(connection)
        if integrity != "ok" or foreign_keys:
            raise InterruptedFourTokenResidueRecoveryError(
                "SQLite integrity or foreign keys are not clean"
            )
        journal = str(connection.execute("PRAGMA journal_mode").fetchone()[0]).lower()
        if journal != "delete":
            raise InterruptedFourTokenResidueRecoveryError(
                "exact recovery requires delete journal mode"
            )
        shape, rows = _classify_state(connection, lease_path=lease_path)
        evidence = _attempt_evidence_snapshot(connection)
        locked_hashes = _locked_hashes(connection)
        cycle_snapshot = dict(rows["cycle"])
        counts = {
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
    finally:
        connection.close()

    if shape == "PRE_RECOVERY":
        if observed_sha != expected_db_sha256:
            raise InterruptedFourTokenResidueRecoveryError(
                "exact pre-recovery database SHA mismatch"
            )
        _exact_lease_payload(lease_path)

    return {
        "shape": shape,
        "database_sha256": observed_sha,
        "git_head": observed_head,
        "marker": marker,
        "integrity": integrity,
        "foreign_key_violations": foreign_keys,
        "attempt_evidence": evidence,
        "locked_hashes": locked_hashes,
        "cycle_snapshot": cycle_snapshot,
        "counts": counts,
    }


def inspect_exact_interrupted_four_token_residue(
    *,
    db_path: str | Path,
    repository_root: str | Path,
    expected_git_head: str,
    process_probe: Callable[[], bool] = _default_process_probe,
) -> dict[str, Any]:
    """Read-only live binding inspection; never changes the consumed residue."""
    return _inspect(
        db_path=Path(db_path).resolve(),
        repository_root=Path(repository_root).resolve(),
        expected_git_head=expected_git_head,
        expected_db_sha256=EXPECTED_DB_SHA256,
        marker_path=APPLICATION_MARKER_PATH,
        expected_marker_sha256=EXPECTED_APPLICATION_MARKER_SHA256,
        lease_path=LEASE_LOCK_PATH,
        process_probe=process_probe,
        git_head_probe=_default_git_head_probe,
    )


def _verify_post(
    *,
    database: Path,
    lease_path: Path,
    locked_hashes: dict[str, str],
    cycle_snapshot: dict[str, Any],
    evidence_snapshot: dict[str, Any],
    counts: dict[str, int],
) -> dict[str, Any]:
    connection = _read_only(database)
    try:
        integrity, foreign_keys = _integrity(connection)
        if integrity != "ok" or foreign_keys:
            raise InterruptedFourTokenResidueRecoveryError(
                "post-recovery SQLite checks failed"
            )
        shape, rows = _classify_state(connection, lease_path=lease_path)
        if shape != "RECOVERED":
            raise InterruptedFourTokenResidueRecoveryError(
                "exact residue did not reach recovered shape"
            )
        if dict(rows["cycle"]) != cycle_snapshot:
            raise InterruptedFourTokenResidueRecoveryError(
                "Cycle-1 immutable evidence changed"
            )
        if _attempt_evidence_snapshot(connection) != evidence_snapshot:
            raise InterruptedFourTokenResidueRecoveryError(
                "append-only attempt evidence changed"
            )
        if _locked_hashes(connection) != locked_hashes:
            raise InterruptedFourTokenResidueRecoveryError(
                "retrieval or financial capability state changed"
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
        if current_counts != counts:
            raise InterruptedFourTokenResidueRecoveryError(
                "retry, restart or successor state was created"
            )
        active = _global_active_scheduler(connection)
        if active:
            raise InterruptedFourTokenResidueRecoveryError(
                "active or locked Scheduler work remains"
            )
    finally:
        connection.close()
    return {
        "shape": "RECOVERED",
        "integrity": integrity,
        "foreign_key_violations": foreign_keys,
        "attempt_state": "CANCELLED",
        "attempt_terminal_cause": INTERRUPTION_CAUSE,
        "scheduler_job_status": "CANCELLED",
        "factory_run_status": "SAFE_STOPPED",
        "supervision_state": "TERMINAL",
        "lease_released": True,
        "active_work": 0,
        "source_calls": 0,
        "scheduler_runtime_calls": 0,
        "retry_created": False,
        "restart_created": False,
        "successor_created": False,
        "retrieval_financial_deltas": {
            table: 0 for table in LOCKED_CAPABILITY_TABLES
        },
    }


def _reconcile(
    *,
    operator_approved: bool,
    db_path: Path,
    repository_root: Path,
    expected_git_head: str,
    expected_db_sha256: str,
    marker_path: Path,
    expected_marker_sha256: str,
    lease_path: Path,
    process_probe: Callable[[], bool],
    git_head_probe: Callable[[Path], str],
    lease_lock_path_override: Path | None,
    now: datetime | None,
) -> dict[str, Any]:
    if not operator_approved:
        raise InterruptedFourTokenResidueRecoveryError(
            "explicit operator reconciliation approval is required"
        )
    preflight = _inspect(
        db_path=db_path,
        repository_root=repository_root,
        expected_git_head=expected_git_head,
        expected_db_sha256=expected_db_sha256,
        marker_path=marker_path,
        expected_marker_sha256=expected_marker_sha256,
        lease_path=lease_path,
        process_probe=process_probe,
        git_head_probe=git_head_probe,
    )
    if preflight["shape"] == "RECOVERED":
        return {
            "status": "ALREADY_RECOVERED_IDEMPOTENT",
            "database_writes": 0,
            "source_calls": 0,
            "scheduler_runtime_calls": 0,
            "authorization_id": AUTHORIZATION_ID,
            "authorization_reused": False,
            "attempt_state": "CANCELLED",
            "scheduler_job_status": "CANCELLED",
            "lease_released": True,
        }

    instant = now or datetime.now(timezone.utc)
    connection = sqlite3.connect(str(db_path))
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys=ON")
    try:
        def _shared_terminalizer() -> dict[str, Any]:
            reconciliation = reconcile_campaign_terminal(
                db_path,
                campaign_id=CAMPAIGN_ID,
                run_id=CAMPAIGN_RUN_ID,
                cycle_id=CYCLE_ID,
                terminal_cause=TERMINAL_CAUSE,
                run_status="SAFE_STOPPED",
                factory_run_id=FACTORY_RUN_ID,
                lifecycle_started=True,
                now=_iso(instant),
            )
            cleanup = cleanup_campaign_supervision(
                db_path,
                supervision_id=SUPERVISION_ID,
                campaign_id=CAMPAIGN_ID,
                configuration_id=CONFIGURATION_ID,
                run_id=CAMPAIGN_RUN_ID,
                owner_id=OWNER_ID,
                terminal_status="FAILED",
                first_terminal_cause=TERMINAL_CAUSE,
                now=instant,
                lease_lock_path_override=lease_lock_path_override,
            )
            return {
                "clean_terminal": bool(reconciliation.get("clean_terminal")),
                "lease_released": bool(cleanup.get("lease_released")),
                "reconciliation": reconciliation,
                "cleanup": cleanup,
            }

        finalization = finalize_four_token_shared_terminal(
            connection,
            campaign_id=CAMPAIGN_ID,
            campaign_run_id=CAMPAIGN_RUN_ID,
            factory_run_id=FACTORY_RUN_ID,
            configuration_id=CONFIGURATION_ID,
            shared_terminalizer=_shared_terminalizer,
            now=instant,
        )
    finally:
        if connection.in_transaction:
            connection.rollback()
        connection.close()

    if finalization.get("admitted_shape") != "ONE_CYCLE_CAMPAIGN_INTERRUPTED_OPEN_ATTEMPT":
        raise InterruptedFourTokenResidueRecoveryError(
            "exact interrupted admitted shape was not preserved"
        )
    verification = _verify_post(
        database=db_path,
        lease_path=lease_path,
        locked_hashes=preflight["locked_hashes"],
        cycle_snapshot=preflight["cycle_snapshot"],
        evidence_snapshot=preflight["attempt_evidence"],
        counts=preflight["counts"],
    )
    return {
        "status": "RECOVERED",
        "authorization_id": AUTHORIZATION_ID,
        "authorization_reused": False,
        "admitted_shape": finalization.get("admitted_shape"),
        **verification,
    }


def reconcile_exact_interrupted_four_token_residue(
    *,
    operator_approved: bool,
    db_path: str | Path,
    repository_root: str | Path,
    expected_git_head: str,
    process_probe: Callable[[], bool] = _default_process_probe,
    now: datetime | None = None,
) -> dict[str, Any]:
    """Apply only the hard-bound live residue after separate operator approval."""
    return _reconcile(
        operator_approved=operator_approved,
        db_path=Path(db_path).resolve(),
        repository_root=Path(repository_root).resolve(),
        expected_git_head=expected_git_head,
        expected_db_sha256=EXPECTED_DB_SHA256,
        marker_path=APPLICATION_MARKER_PATH,
        expected_marker_sha256=EXPECTED_APPLICATION_MARKER_SHA256,
        lease_path=LEASE_LOCK_PATH,
        process_probe=process_probe,
        git_head_probe=_default_git_head_probe,
        lease_lock_path_override=None,
        now=now,
    )


__all__ = [
    "InterruptedFourTokenResidueRecoveryError",
    "inspect_exact_interrupted_four_token_residue",
    "reconcile_exact_interrupted_four_token_residue",
]
