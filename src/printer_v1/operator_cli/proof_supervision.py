"""V2-9.4 durable proof supervision and zero-source recovery.

The supervision ledger and lock are coordination evidence only. This module
never fetches a source during inspection, heartbeat, cancellation, or recovery.
"""

from __future__ import annotations

import argparse
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
import json
import os
from pathlib import Path
import sqlite3
from typing import Any, Callable, Iterable, Iterator
import uuid


PROOF_SCOPE = "V2_9"
OWNER_MANUAL_POWERSHELL = "MANUAL_POWERSHELL"
OWNER_TEST_FIXTURE = "TEST_FIXTURE"

STATUS_STARTING = "STARTING"
STATUS_RUNNING = "RUNNING"
STATUS_TERMINAL = "TERMINAL"

TERMINAL_COMPLETED = "COMPLETED"
TERMINAL_GOVERNED_SAFE_STOP = "GOVERNED_SAFE_STOP"
TERMINAL_OPERATOR_CANCELLED = "OPERATOR_CANCELLED"
TERMINAL_SOURCE_FAILURE = "SOURCE_FAILURE"
TERMINAL_BUDGET_STOP = "BUDGET_STOP"
TERMINAL_HOST_DISAPPEARED = "HOST_PROCESS_DISAPPEARED"

HOST_PROCESS_DISAPPEARED = "HOST_PROCESS_DISAPPEARED"
OPERATOR_CANCELLED = "OPERATOR_CANCELLED"
SUPERVISION_HEARTBEAT_PERSISTENCE_FAILED = (
    "SUPERVISION_HEARTBEAT_PERSISTENCE_FAILED"
)
DEFAULT_LEASE_SECONDS = 90
ACTIVE_STATUSES = (STATUS_STARTING, STATUS_RUNNING)
TERMINAL_STATUSES = {
    TERMINAL_COMPLETED,
    TERMINAL_GOVERNED_SAFE_STOP,
    TERMINAL_OPERATOR_CANCELLED,
    TERMINAL_SOURCE_FAILURE,
    TERMINAL_BUDGET_STOP,
    TERMINAL_HOST_DISAPPEARED,
}
EVIDENCE_TABLES = (
    "printer_source_requests",
    "printer_source_responses",
    "printer_source_failures",
    "printer_token_snapshots",
    "printer_memory_windows",
    "printer_memories",
    "printer_memory_fingerprints",
    "printer_memory_retrieval_queries",
    "printer_memory_retrieval_matches",
    "printer_paper_decisions",
    "printer_paper_positions",
    "printer_paper_trade_events",
    "printer_paper_trade_audits",
)


class ProofSupervisionError(RuntimeError):
    """Fail-closed supervision or recovery error."""


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _iso(value: datetime | None = None) -> str:
    return (value or _utc_now()).astimezone(timezone.utc).isoformat()


def _parse(value: str) -> datetime:
    parsed = datetime.fromisoformat(value)
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


@contextmanager
def _connect(
    db_path: str | Path, *, readonly: bool = False,
) -> Iterator[sqlite3.Connection]:
    path = Path(db_path).resolve()
    if readonly:
        connection = sqlite3.connect(f"file:{path.as_posix()}?mode=ro", uri=True)
    else:
        connection = sqlite3.connect(str(path))
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys=ON")
    try:
        yield connection
        if not readonly:
            connection.commit()
    except Exception:
        if not readonly:
            connection.rollback()
        raise
    finally:
        connection.close()


def _row_dict(row: sqlite3.Row) -> dict[str, Any]:
    return {key: row[key] for key in row.keys()}


def _require_supervision_schema(connection: sqlite3.Connection) -> None:
    row = connection.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' "
        "AND name='printer_proof_run_supervision'"
    ).fetchone()
    if row is None:
        raise ProofSupervisionError("canonical supervision migration is missing")


def _counts(connection: sqlite3.Connection) -> dict[str, int]:
    return {
        table: (
            int(connection.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0])
            if connection.execute(
                "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?",
                (table,),
            ).fetchone() is not None else 0
        )
        for table in EVIDENCE_TABLES
    }

def full_run_evidence_deltas(
    db_path: str | Path, backup_db_path: str | Path,
) -> dict[str, int]:
    """Measure the complete isolated proof against its prepared baseline."""
    with _connect(backup_db_path, readonly=True) as baseline:
        before = _counts(baseline)
    with _connect(db_path, readonly=True) as proof:
        after = _counts(proof)
    return {table: after[table] - before[table] for table in EVIDENCE_TABLES}

def inspect_one_proof_lock(lock_path: str | Path) -> dict[str, Any]:
    path = Path(lock_path).resolve()
    if not path.exists():
        return {"lock_path": str(path), "exists": False, "available": True}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ProofSupervisionError(f"ambiguous one-proof lock: {exc}") from exc
    return {"lock_path": str(path), "exists": True, "available": False, **payload}



def _write_lock_payload_atomic(path: Path, payload: dict[str, Any]) -> None:
    """Replace the active lease without exposing a partially written lock."""
    temporary = path.with_name(f".{path.name}.{uuid.uuid4().hex}.tmp")
    try:
        temporary.write_text(
            json.dumps(payload, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
            newline="\n",
        )
        os.replace(temporary, path)
    finally:
        if temporary.exists():
            temporary.unlink()


def heartbeat_active_lease(
    lock_path: str | Path,
    execution_id: str,
    *,
    process_id: int | None = None,
    lease_seconds: int = DEFAULT_LEASE_SECONDS,
    now: datetime | None = None,
) -> dict[str, Any]:
    """Renew the authoritative active lease without opening the proof DB."""
    if lease_seconds < 15:
        raise ProofSupervisionError("lease must be at least 15 seconds")
    path = Path(lock_path).resolve()
    current = inspect_one_proof_lock(path)
    if not current.get("exists") or current.get("execution_id") != execution_id:
        raise ProofSupervisionError("active lease belongs to a different execution")
    instant = now or _utc_now()
    payload = {
        key: value for key, value in current.items()
        if key not in {"lock_path", "exists", "available"}
    }
    payload.update({
        "process_id": process_id if process_id is not None else payload.get("process_id"),
        "heartbeat_at": _iso(instant),
        "lease_expires_at": _iso(instant + timedelta(seconds=lease_seconds)),
        "updated_at": _iso(instant),
    })
    _write_lock_payload_atomic(path, payload)
    return {"lock_path": str(path), "exists": True, "available": False, **payload}


def request_cooperative_stop(
    lock_path: str | Path,
    execution_id: str,
    *,
    stop_reason: str,
    now: datetime | None = None,
) -> dict[str, Any]:
    if not stop_reason:
        raise ProofSupervisionError("cooperative stop reason is required")
    path = Path(lock_path).resolve()
    current = inspect_one_proof_lock(path)
    if not current.get("exists") or current.get("execution_id") != execution_id:
        raise ProofSupervisionError("active lease belongs to a different execution")
    instant = now or _utc_now()
    payload = {
        key: value for key, value in current.items()
        if key not in {"lock_path", "exists", "available"}
    }
    payload.setdefault("cancellation_requested_at", _iso(instant))
    payload.setdefault("cancellation_reason", stop_reason)
    payload["updated_at"] = _iso(instant)
    _write_lock_payload_atomic(path, payload)
    return {"lock_path": str(path), "exists": True, "available": False, **payload}


def cooperative_stop_reason(lock_path: str | Path, execution_id: str) -> str | None:
    current = inspect_one_proof_lock(lock_path)
    if not current.get("exists") or current.get("execution_id") != execution_id:
        return None
    reason = current.get("cancellation_reason")
    return str(reason) if reason else None
def _acquire_one_proof_lock(
    lock_path: str | Path, *, execution_id: str, proof_db_path: str | Path,
    created_at: str, process_id: int | None, lease_expires_at: str,
) -> Path:
    path = Path(lock_path).resolve()
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps({
        "proof_scope": PROOF_SCOPE,
        "execution_id": execution_id,
        "proof_db_path": str(Path(proof_db_path).resolve()),
        "process_id": process_id,
        "heartbeat_at": created_at,
        "lease_expires_at": lease_expires_at,
        "created_at": created_at,
        "updated_at": created_at,
    }, indent=2, sort_keys=True)
    try:
        with path.open("x", encoding="utf-8", newline="\n") as handle:
            handle.write(payload + "\n")
    except FileExistsError as exc:
        current = inspect_one_proof_lock(path)
        raise ProofSupervisionError(
            "one V2-9 proof is already active or unresolved: "
            f"execution_id={current.get('execution_id')}"
        ) from exc
    return path


def _release_one_proof_lock(lock_path: str | Path, execution_id: str) -> bool:
    path = Path(lock_path).resolve()
    if not path.exists():
        return True
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ProofSupervisionError(f"cannot safely release ambiguous lock: {exc}") from exc
    if payload.get("execution_id") != execution_id:
        raise ProofSupervisionError("one-proof lock belongs to a different execution")
    path.unlink()
    return not path.exists()


def create_execution(
    db_path: str | Path,
    *,
    execution_id: str | None,
    owner_launcher_type: str,
    process_id: int | None,
    backup_db_path: str | Path,
    one_proof_lock_path: str | Path,
    stdout_log_path: str | Path,
    stderr_log_path: str | Path,
    lease_seconds: int = DEFAULT_LEASE_SECONDS,
    now: datetime | None = None,
) -> dict[str, Any]:
    if owner_launcher_type not in {OWNER_MANUAL_POWERSHELL, OWNER_TEST_FIXTURE}:
        raise ProofSupervisionError("unsupported owner/launcher type")
    if lease_seconds < 15:
        raise ProofSupervisionError("lease must be at least 15 seconds")
    path = Path(db_path).resolve()
    backup = Path(backup_db_path).resolve()
    if path == backup:
        raise ProofSupervisionError("proof DB and backup must be distinct")
    if not path.is_file() or not backup.is_file():
        raise ProofSupervisionError("prepared proof DB and backup are required")
    from printer_v1.operator_cli.proof_db_schema_readiness import (
        _sha256,
        validate_runtime_schema,
    )
    validate_runtime_schema(path)
    validate_runtime_schema(backup)
    if _sha256(path) != _sha256(backup):
        raise ProofSupervisionError("prepared proof DB and backup are not byte-identical")

    identifier = execution_id or str(uuid.uuid4())
    instant = now or _utc_now()
    instant_text = _iso(instant)
    lease_text = _iso(instant + timedelta(seconds=lease_seconds))
    lock = _acquire_one_proof_lock(
        one_proof_lock_path,
        execution_id=identifier,
        proof_db_path=path,
        created_at=instant_text,
        process_id=process_id,
        lease_expires_at=lease_text,
    )
    try:
        with _connect(path) as connection:
            _require_supervision_schema(connection)
            unresolved = connection.execute(
                "SELECT execution_id FROM printer_proof_run_supervision "
                "WHERE proof_scope=? AND execution_status IN ('STARTING','RUNNING')",
                (PROOF_SCOPE,),
            ).fetchone()
            if unresolved is not None:
                raise ProofSupervisionError(
                    "an active or abandoned proof must be resolved before a new proof"
                )
            connection.execute(
                """INSERT INTO printer_proof_run_supervision
                   (execution_id,proof_scope,owner_launcher_type,process_id,
                    execution_status,heartbeat_at,lease_expires_at,proof_db_path,
                    backup_db_path,one_proof_lock_path,stdout_log_path,
                    stderr_log_path,started_at,created_at,updated_at)
                   VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (
                    identifier, PROOF_SCOPE, owner_launcher_type, process_id,
                    STATUS_STARTING, instant_text, lease_text, str(path), str(backup),
                    str(lock), str(Path(stdout_log_path).resolve()),
                    str(Path(stderr_log_path).resolve()), instant_text, instant_text,
                    instant_text,
                ),
            )
    except Exception:
        _release_one_proof_lock(lock, identifier)
        raise
    return inspect_execution(path, identifier)


def attach_run(
    db_path: str | Path,
    execution_id: str,
    run_id: str,
    *,
    process_id: int | None = None,
    now: datetime | None = None,
    lease_seconds: int = DEFAULT_LEASE_SECONDS,
) -> dict[str, Any]:
    instant = now or _utc_now()
    with _connect(db_path) as connection:
        cursor = connection.execute(
            """UPDATE printer_proof_run_supervision
               SET run_id=?, process_id=COALESCE(?,process_id),
                   execution_status='RUNNING', heartbeat_at=?, lease_expires_at=?,
                   updated_at=?
               WHERE execution_id=? AND execution_status IN ('STARTING','RUNNING')
                 AND (run_id IS NULL OR run_id=?)""",
            (
                run_id, process_id, _iso(instant),
                _iso(instant + timedelta(seconds=lease_seconds)), _iso(instant),
                execution_id, run_id,
            ),
        )
        if cursor.rowcount != 1:
            raise ProofSupervisionError("execution cannot attach this run")
    supervision = inspect_execution(db_path, execution_id)
    heartbeat_active_lease(
        str(supervision["one_proof_lock_path"]),
        execution_id,
        process_id=process_id,
        lease_seconds=lease_seconds,
        now=instant,
    )

    return inspect_execution(db_path, execution_id)


def heartbeat_execution(
    db_path: str | Path,
    execution_id: str,
    *,
    process_id: int | None = None,
    lease_seconds: int = DEFAULT_LEASE_SECONDS,
    now: datetime | None = None,
) -> dict[str, Any]:
    """Compatibility wrapper; active renewal itself is proof-DB independent."""
    supervision = inspect_execution(db_path, execution_id, now=now)
    return heartbeat_active_lease(
        str(supervision["one_proof_lock_path"]),
        execution_id,
        process_id=process_id,
        lease_seconds=lease_seconds,
        now=now,
    )

def inspect_execution(
    db_path: str | Path,
    execution_id: str,
    *,
    now: datetime | None = None,
) -> dict[str, Any]:
    instant = now or _utc_now()
    with _connect(db_path, readonly=True) as connection:
        _require_supervision_schema(connection)
        row = connection.execute(
            "SELECT * FROM printer_proof_run_supervision WHERE execution_id=?",
            (execution_id,),
        ).fetchone()
        if row is None:
            raise ProofSupervisionError(f"unknown execution_id={execution_id}")
        payload = _row_dict(row)
        if payload["execution_status"] in ACTIVE_STATUSES:
            active_lease = inspect_one_proof_lock(str(payload["one_proof_lock_path"]))
            if (
                not active_lease.get("exists")
                or active_lease.get("execution_id") != execution_id
            ):
                raise ProofSupervisionError("active execution lease is missing or ambiguous")
            payload["ledger_heartbeat_at"] = payload["heartbeat_at"]
            payload["ledger_lease_expires_at"] = payload["lease_expires_at"]
            payload["heartbeat_at"] = active_lease["heartbeat_at"]
            payload["lease_expires_at"] = active_lease["lease_expires_at"]
            payload["process_id"] = active_lease.get("process_id")
            payload["cancellation_requested_at"] = active_lease.get(
                "cancellation_requested_at"
            )
            payload["cancellation_reason"] = active_lease.get("cancellation_reason")
        payload["lease_expired"] = _parse(str(payload["lease_expires_at"])) <= instant
        payload["inspection_mode"] = "READ_ONLY"
        payload["source_calls"] = 0
        return payload


def process_is_alive(process_id: int | None) -> bool:
    if process_id is None or process_id <= 0:
        return False
    if os.name == "nt":
        import ctypes
        process_query_limited_information = 0x1000
        still_active = 259
        kernel32 = ctypes.windll.kernel32
        handle = kernel32.OpenProcess(
            process_query_limited_information, False, int(process_id)
        )
        if not handle:
            return False
        try:
            exit_code = ctypes.c_ulong()
            if not kernel32.GetExitCodeProcess(handle, ctypes.byref(exit_code)):
                raise ProofSupervisionError("unable to inspect supervised process")
            return int(exit_code.value) == still_active
        finally:
            kernel32.CloseHandle(handle)
    try:
        os.kill(int(process_id), 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    return True


def _terminalize_execution(
    connection: sqlite3.Connection,
    execution_id: str,
    *,
    terminal_status: str,
    first_stop_reason: str,
    finished_at: str,
    recovery_report: dict[str, Any] | None = None,
) -> None:
    if terminal_status not in TERMINAL_STATUSES:
        raise ProofSupervisionError("unsupported terminal status")
    cursor = connection.execute(
        """UPDATE printer_proof_run_supervision
           SET execution_status='TERMINAL', terminal_status=?,
               first_stop_reason=COALESCE(first_stop_reason,?), finished_at=?,
               process_id=NULL, lease_expires_at=?,
               recovery_report_json=COALESCE(?,recovery_report_json), updated_at=?
           WHERE execution_id=? AND execution_status IN ('STARTING','RUNNING')""",
        (
            terminal_status, first_stop_reason, finished_at, finished_at,
            json.dumps(recovery_report, sort_keys=True) if recovery_report else None,
            finished_at, execution_id,
        ),
    )
    if cursor.rowcount != 1:
        existing = connection.execute(
            "SELECT terminal_status,first_stop_reason FROM printer_proof_run_supervision "
            "WHERE execution_id=?",
            (execution_id,),
        ).fetchone()
        if existing is None:
            raise ProofSupervisionError("execution not found")
        if (
            str(existing["terminal_status"]) != terminal_status
            or str(existing["first_stop_reason"]) != first_stop_reason
        ):
            raise ProofSupervisionError("terminal first cause is immutable")


def _zero_source_cleanup(
    db_path: str | Path,
    execution_id: str,
    *,
    terminal_status: str,
    stop_reason: str,
    require_expired: bool,
    process_probe: Callable[[int | None], bool],
    now: datetime | None = None,
) -> dict[str, Any]:
    instant = now or _utc_now()
    inspection = inspect_execution(db_path, execution_id, now=instant)
    if inspection["execution_status"] == STATUS_TERMINAL:
        stored = inspection.get("recovery_report_json")
        if stored:
            report = json.loads(str(stored))
            report["idempotent_replay"] = True
            return report
        raise ProofSupervisionError("execution is already terminal")
    if require_expired and not inspection["lease_expired"]:
        raise ProofSupervisionError("heartbeat lease has not expired")
    if process_probe(inspection.get("process_id")):
        raise ProofSupervisionError("supervised process is still alive")
    run_id = inspection.get("run_id")
    if not run_id:
        raise ProofSupervisionError("execution has no attached run")

    with _connect(db_path) as connection:
        connection.execute("BEGIN IMMEDIATE")
        current = connection.execute(
            "SELECT * FROM printer_proof_run_supervision WHERE execution_id=?",
            (execution_id,),
        ).fetchone()
        if current is None:
            raise ProofSupervisionError("execution disappeared during recovery")
        if current["execution_status"] == STATUS_TERMINAL:
            connection.rollback()
            return _zero_source_cleanup(
                db_path, execution_id, terminal_status=terminal_status,
                stop_reason=stop_reason, require_expired=require_expired,
                process_probe=process_probe, now=instant,
            )
        if require_expired and _parse(str(current["lease_expires_at"])) > instant:
            raise ProofSupervisionError("heartbeat renewed during recovery")
        if process_probe(current["process_id"]):
            raise ProofSupervisionError("process reappeared during recovery")

        evidence_before = _counts(connection)
        window_ids_before = [
            int(row[0]) for row in connection.execute(
                "SELECT id FROM printer_memory_windows ORDER BY id"
            ).fetchall()
        ]
        step_cursor = connection.execute(
            """UPDATE printer_memory_factory_run_steps
               SET step_status='CANCELLED', error_or_skip_reason=?,
                   finished_at=?, updated_at=?
               WHERE run_id=? AND step_status IN ('PENDING','RUNNING')""",
            (stop_reason, _iso(instant), _iso(instant), run_id),
        )
        job_cursor = connection.execute(
            """UPDATE printer_scheduler_jobs
               SET status='CANCELLED', finished_at=?, locked_at=NULL,
                   lock_owner=NULL, last_error=?, updated_at=?
               WHERE id IN (
                   SELECT scheduler_job_id FROM printer_memory_factory_run_steps
                   WHERE run_id=? AND scheduler_job_id IS NOT NULL
               ) AND status IN ('PENDING','RUNNING','COOLDOWN')""",
            (_iso(instant), stop_reason, _iso(instant), run_id),
        )
        pending_steps = int(connection.execute(
            "SELECT COUNT(*) FROM printer_memory_factory_run_steps "
            "WHERE run_id=? AND step_status IN ('PENDING','RUNNING')",
            (run_id,),
        ).fetchone()[0])
        active_jobs = int(connection.execute(
            """SELECT COUNT(*) FROM printer_scheduler_jobs
               WHERE id IN (
                   SELECT scheduler_job_id FROM printer_memory_factory_run_steps
                   WHERE run_id=? AND scheduler_job_id IS NOT NULL
               ) AND (status IN ('PENDING','RUNNING','COOLDOWN')
                      OR locked_at IS NOT NULL OR lock_owner IS NOT NULL)""",
            (run_id,),
        ).fetchone()[0])
        evidence_after = _counts(connection)
        evidence_deltas = {
            table: evidence_after[table] - evidence_before[table]
            for table in EVIDENCE_TABLES
        }
        windows_after = [
            int(row[0]) for row in connection.execute(
                "SELECT id FROM printer_memory_windows ORDER BY id"
            ).fetchall()
        ]
        if any(evidence_deltas.values()) or windows_after != window_ids_before:
            raise ProofSupervisionError("recovery attempted to mutate evidence")
        if pending_steps or active_jobs:
            raise ProofSupervisionError("abandoned proof cleanup is incomplete")

        full_deltas = full_run_evidence_deltas(
            db_path, str(inspection["backup_db_path"])
        )

        report = {
            "command": "printer-supervise-v2-9-proof",
            "mode": "ZERO_SOURCE_ABANDONED_RECOVERY",
            "execution_id": execution_id,
            "run_id": run_id,
            "terminal_status": terminal_status,
            "first_stop_reason": stop_reason,
            "heartbeat_expired": bool(inspection["lease_expired"]),
            "process_absent": True,
            "cancelled_run_steps": int(step_cursor.rowcount),
            "cancelled_scheduler_jobs": int(job_cursor.rowcount),
            "pending_or_running_steps_after": pending_steps,
            "pending_or_running_jobs_after": active_jobs,
            "released_scheduler_locks": True,
            "source_calls": 0,
            "automatic_retries": 0,
            "successor_created": False,
            "evidence_deltas": evidence_deltas,
            "recovery_evidence_deltas": evidence_deltas,
            "full_run_evidence_deltas": full_deltas,
            "finished_at": _iso(instant),
            "idempotent_replay": False,
        }
        factory_report = {
            **report,
            "run_status": "FAILED" if terminal_status == TERMINAL_HOST_DISAPPEARED
            else "SAFE_STOPPED",
            "stop_reason": stop_reason,
            "replay": {
                "mode": "REPORT_ONLY",
                "new_source_calls": 0,
                "new_evidence_rows": 0,
            },
        }
        connection.execute(
            """UPDATE printer_memory_factory_runs
               SET run_status=?,stop_reason=COALESCE(stop_reason,?),finished_at=?,
                   final_report_json=COALESCE(final_report_json,?),updated_at=?
               WHERE run_id=? AND run_status='RUNNING'""",
            (
                factory_report["run_status"], stop_reason, _iso(instant),
                json.dumps(factory_report, sort_keys=True), _iso(instant), run_id,
            ),
        )
        _terminalize_execution(
            connection, execution_id, terminal_status=terminal_status,
            first_stop_reason=stop_reason, finished_at=_iso(instant),
            recovery_report=report,
        )
        connection.commit()

    lock_released = _release_one_proof_lock(
        str(inspection["one_proof_lock_path"]), execution_id
    )
    report["one_proof_lock_released"] = lock_released
    return report


def recover_abandoned_execution(
    db_path: str | Path,
    execution_id: str,
    *,
    process_probe: Callable[[int | None], bool] = process_is_alive,
    now: datetime | None = None,
) -> dict[str, Any]:
    return _zero_source_cleanup(
        db_path, execution_id,
        terminal_status=TERMINAL_HOST_DISAPPEARED,
        stop_reason=HOST_PROCESS_DISAPPEARED,
        require_expired=True,
        process_probe=process_probe,
        now=now,
    )


def cancel_execution(
    db_path: str | Path,
    execution_id: str,
    *,
    process_probe: Callable[[int | None], bool] = process_is_alive,
    now: datetime | None = None,
) -> dict[str, Any]:
    return _zero_source_cleanup(
        db_path, execution_id,
        terminal_status=TERMINAL_OPERATOR_CANCELLED,
        stop_reason=OPERATOR_CANCELLED,
        require_expired=False,
        process_probe=process_probe,
        now=now,
    )


def stop_execution(
    db_path: str | Path,
    execution_id: str,
    *,
    stop_reason: str,
    process_probe: Callable[[int | None], bool] = process_is_alive,
    now: datetime | None = None,
) -> dict[str, Any]:
    """Clean a cooperatively stopped supervision fault without misattribution."""
    if not stop_reason or stop_reason == OPERATOR_CANCELLED:
        raise ProofSupervisionError("explicit non-operator stop reason is required")
    return _zero_source_cleanup(
        db_path,
        execution_id,
        terminal_status=TERMINAL_GOVERNED_SAFE_STOP,
        stop_reason=stop_reason,
        require_expired=False,
        process_probe=process_probe,
        now=now,
    )
def finalize_execution_from_report(
    db_path: str | Path,
    execution_id: str,
    report: dict[str, Any],
    *,
    now: datetime | None = None,
) -> dict[str, Any]:
    run_status = str(report.get("run_status") or "")
    stop_reason = str(report.get("stop_reason") or "UNKNOWN_TERMINAL_STOP")
    if stop_reason == "SAFE_STOP_OPERATOR_INTERRUPTED":
        terminal = TERMINAL_OPERATOR_CANCELLED
    elif stop_reason == "SAFE_STOP_SOURCE_FAILURE":
        terminal = TERMINAL_SOURCE_FAILURE
    elif stop_reason == "SAFE_STOP_BUDGET_CEILING_EXCEEDED":
        terminal = TERMINAL_BUDGET_STOP
    elif run_status == "COMPLETED":
        terminal = TERMINAL_COMPLETED
    else:
        terminal = TERMINAL_GOVERNED_SAFE_STOP
    instant = now or _utc_now()
    with _connect(db_path) as connection:
        _terminalize_execution(
            connection, execution_id, terminal_status=terminal,
            first_stop_reason=stop_reason, finished_at=_iso(instant),
        )
        row = connection.execute(
            "SELECT one_proof_lock_path FROM printer_proof_run_supervision "
            "WHERE execution_id=?",
            (execution_id,),
        ).fetchone()
    if row is None:
        raise ProofSupervisionError("execution missing after terminal update")
    _release_one_proof_lock(str(row[0]), execution_id)
    return inspect_execution(db_path, execution_id, now=instant)


def run_supervised_v2_9_proof(
    db_path: str | Path,
    backup_path: str | Path,
    execution_id: str,
) -> dict[str, Any]:
    """Run the single approved proof with a lock-file cancellation probe."""
    from printer_v1.operator_cli.one_command_15m_factory import (
        run_one_command_15m_factory,
    )
    supervision = inspect_execution(db_path, execution_id)
    lock_path = str(supervision["one_proof_lock_path"])
    print(json.dumps({
        "event": "PROCESS_START",
        "execution_id": execution_id,
        "process_id": os.getpid(),
        "at": _iso(),
    }, sort_keys=True), flush=True)
    return run_one_command_15m_factory(
        db_path,
        backup_path,
        operator_approved=True,
        proof_mode=True,
        window_kind="WINDOW_15M",
        max_selected_tokens=1,
        max_source_requests=2,
        timeout_seconds=10.0,
        total_duration_seconds=18_000.0,
        continuous_first_hour=True,
        continuous_four_hour=True,
        four_hour_proof_mode=True,
        supervision_execution_id=execution_id,
        cancellation_probe=lambda: cooperative_stop_reason(lock_path, execution_id),
    )


def main_run_supervised_proof(argv: Iterable[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run one supervised V2-9 proof.")
    parser.add_argument("--operator-approved", action="store_true")
    parser.add_argument("--db-path", required=True)
    parser.add_argument("--backup-proof-path", required=True)
    parser.add_argument("--execution-id", required=True)
    args = parser.parse_args(list(argv) if argv is not None else None)
    if not args.operator_approved:
        raise SystemExit("--operator-approved is required")
    report = run_supervised_v2_9_proof(
        args.db_path, args.backup_proof_path, args.execution_id
    )
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0 if report.get("run_status") != "FAILED" else 1


def main_supervision(argv: Iterable[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="V2-9 durable proof supervision.")
    sub = parser.add_subparsers(dest="action", required=True)
    lock = sub.add_parser("inspect-lock")
    lock.add_argument("--lock-path", required=True)
    create = sub.add_parser("create")
    create.add_argument("--operator-approved", action="store_true")
    create.add_argument("--db-path", required=True)
    create.add_argument("--backup-proof-path", required=True)
    create.add_argument("--execution-id", required=True)
    create.add_argument("--owner-launcher-type", default=OWNER_MANUAL_POWERSHELL)
    create.add_argument("--pid", type=int)
    create.add_argument("--lock-path", required=True)
    create.add_argument("--stdout-log-path", required=True)
    create.add_argument("--stderr-log-path", required=True)
    create.add_argument("--lease-seconds", type=int, default=DEFAULT_LEASE_SECONDS)
    heartbeat = sub.add_parser("heartbeat")
    heartbeat.add_argument("--db-path")
    heartbeat.add_argument("--lock-path")
    heartbeat.add_argument("--execution-id", required=True)
    heartbeat.add_argument("--pid", type=int)
    heartbeat.add_argument("--lease-seconds", type=int, default=DEFAULT_LEASE_SECONDS)
    inspect = sub.add_parser("inspect")
    inspect.add_argument("--db-path", required=True)
    inspect.add_argument("--execution-id", required=True)
    recover = sub.add_parser("recover")
    recover.add_argument("--operator-approved", action="store_true")
    recover.add_argument("--db-path", required=True)
    recover.add_argument("--execution-id", required=True)
    cancel = sub.add_parser("cancel")
    cancel.add_argument("--operator-approved", action="store_true")
    cancel.add_argument("--db-path", required=True)
    cancel.add_argument("--execution-id", required=True)
    request_stop = sub.add_parser("request-stop")
    request_stop.add_argument("--operator-approved", action="store_true")
    request_stop.add_argument("--lock-path", required=True)
    request_stop.add_argument("--execution-id", required=True)
    request_stop.add_argument("--reason", required=True)
    stop = sub.add_parser("stop")
    stop.add_argument("--operator-approved", action="store_true")
    stop.add_argument("--db-path", required=True)
    stop.add_argument("--execution-id", required=True)
    stop.add_argument("--reason", required=True)

    run = sub.add_parser("run")
    run.add_argument("--operator-approved", action="store_true")
    run.add_argument("--db-path", required=True)
    run.add_argument("--backup-proof-path", required=True)
    run.add_argument("--execution-id", required=True)
    args = parser.parse_args(list(argv) if argv is not None else None)
    try:
        if args.action == "inspect-lock":
            report = inspect_one_proof_lock(args.lock_path)
        elif args.action == "create":
            if not args.operator_approved:
                raise ProofSupervisionError("operator approval required")
            report = create_execution(
                args.db_path,
                execution_id=args.execution_id,
                owner_launcher_type=args.owner_launcher_type,
                process_id=args.pid,
                backup_db_path=args.backup_proof_path,
                one_proof_lock_path=args.lock_path,
                stdout_log_path=args.stdout_log_path,
                stderr_log_path=args.stderr_log_path,
                lease_seconds=args.lease_seconds,
            )
        elif args.action == "heartbeat":
            if args.lock_path:
                report = heartbeat_active_lease(
                    args.lock_path, args.execution_id, process_id=args.pid,
                    lease_seconds=args.lease_seconds,
                )
            elif args.db_path:
                report = heartbeat_execution(
                    args.db_path, args.execution_id, process_id=args.pid,
                    lease_seconds=args.lease_seconds,
                )
            else:
                raise ProofSupervisionError("heartbeat requires --lock-path or --db-path")
        elif args.action == "inspect":
            report = inspect_execution(args.db_path, args.execution_id)
        elif args.action == "recover":
            if not args.operator_approved:
                raise ProofSupervisionError("operator approval required")
            report = recover_abandoned_execution(args.db_path, args.execution_id)
        elif args.action == "request-stop":
            if not args.operator_approved:
                raise ProofSupervisionError("operator approval required")
            report = request_cooperative_stop(
                args.lock_path, args.execution_id, stop_reason=args.reason,
            )
        elif args.action == "stop":
            if not args.operator_approved:
                raise ProofSupervisionError("operator approval required")
            report = stop_execution(
                args.db_path, args.execution_id, stop_reason=args.reason,
            )
        elif args.action == "run":
            if not args.operator_approved:
                raise ProofSupervisionError("operator approval required")
            report = run_supervised_v2_9_proof(
                args.db_path, args.backup_proof_path, args.execution_id
            )
        else:
            if not args.operator_approved:
                raise ProofSupervisionError("operator approval required")
            report = cancel_execution(args.db_path, args.execution_id)
        print(json.dumps(report, indent=2, sort_keys=True))
        return 0
    except Exception as exc:
        print(json.dumps({
            "status": "SUPERVISION_BLOCKED",
            "error": f"{type(exc).__name__}: {exc}",
            "source_calls": 0,
            "automatic_retries": 0,
        }, indent=2, sort_keys=True))
        return 1


if __name__ == "__main__":  # pragma: no cover - exercised by PowerShell launcher
    raise SystemExit(main_supervision())
