"""Operational campaign lease ownership and transactional safe-stop."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
import json
import os
from pathlib import Path
import sqlite3
import time
from typing import Any
import uuid


OPERATIONAL_SCOPE = "OPERATIONAL_CAMPAIGN"
DEFAULT_LEASE_SECONDS = 90
LEASE_REPLACE_MAX_ATTEMPTS = 3
LEASE_REPLACE_RETRY_SECONDS = 0.05
# V2-9.8B.2: bounded SQLite lock wait. timeout=0 caused the heartbeat renewer to
# fail immediately under a legitimate main-writer lock and previously triggered
# terminal cleanup from the heartbeat thread.
SQLITE_BUSY_TIMEOUT_SECONDS = 2.0
SQLITE_BUSY_MAX_ATTEMPTS = 5
SQLITE_BUSY_RETRY_SECONDS = 0.05
_TRANSIENT_WINDOWS_REPLACE_ERRORS = {5, 32, 33}
_ACTIVE_WORK = ("PENDING", "RUNNING", "COOLDOWN")
_ACTIVE_WINDOWS = ("PLANNED", "COLLECTING", "CLOSE_PENDING", "AUDITING")
_TERMINAL_STATUSES = {
    "COMPLETED", "FAILED", "CANCELLED", "LEASE_RENEWAL_UNCONFIRMED",
}
_LEASE_FAILURE_FILE_KEY = "first_heartbeat_renewal_failure"
_SAFE_FAILURES = {
    "SQLITE_LOCK_CONTENTION": (
        "SQLiteOperationalError",
        "SQLite lease renewal was not confirmed because the database was busy or locked.",
        "LEASE_RENEWAL_SQLITE_LOCKED",
    ),
    "LEASE_EXPIRED": (
        "CampaignSupervisionError",
        "The operational campaign lease had expired before renewal could be confirmed.",
        "LEASE_RENEWAL_LEASE_EXPIRED",
    ),
    "OWNERSHIP_MISMATCH": (
        "CampaignSupervisionError",
        "Operational campaign lease ownership could not be confirmed.",
        "LEASE_RENEWAL_OWNERSHIP_MISMATCH",
    ),
    "LEASE_RENEWAL_ERROR": (
        "LeaseRenewalError",
        "Operational campaign lease renewal was not confirmed.",
        "LEASE_RENEWAL_UNCONFIRMED",
    ),
}


class CampaignSupervisionError(RuntimeError):
    """Raised when operational campaign supervision cannot be proven."""


def _iso(value: datetime | None = None) -> str:
    return (value or datetime.now(timezone.utc)).astimezone(timezone.utc).isoformat()


def _parse(value: str) -> datetime:
    try:
        parsed = datetime.fromisoformat(value)
    except (TypeError, ValueError) as exc:
        raise CampaignSupervisionError("lease timestamp is malformed") from exc
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _required(value: object, label: str) -> str:
    text = str(value).strip()
    if not text:
        raise CampaignSupervisionError(f"{label} is required")
    return text


def _is_sqlite_locked(exc: BaseException) -> bool:
    if isinstance(exc, sqlite3.OperationalError):
        return "locked" in str(exc).lower() or "busy" in str(exc).lower()
    return False


def _safe_renewal_failure(
    exc: BaseException,
    *,
    attempted_at: str,
    prior_heartbeat_at: str | None,
    prior_lease_expires_at: str | None,
) -> dict[str, Any]:
    raw = str(exc).lower()
    if _is_sqlite_locked(exc):
        category = "SQLITE_LOCK_CONTENTION"
    elif "expired" in raw:
        category = "LEASE_EXPIRED"
    elif "ownership mismatch" in raw:
        category = "OWNERSHIP_MISMATCH"
    else:
        category = "LEASE_RENEWAL_ERROR"
    safe_type, safe_message, terminal_cause = _SAFE_FAILURES[category]
    return {
        "safe_error_type": safe_type,
        "safe_error_category": category,
        "safe_message": safe_message,
        "sqlite_locked": category == "SQLITE_LOCK_CONTENTION",
        "attempted_at": attempted_at,
        "prior_heartbeat_at": prior_heartbeat_at,
        "prior_lease_expires_at": prior_lease_expires_at,
        "renewal_confirmed": False,
        "terminal_cause": terminal_cause,
    }


def _persist_failure_to_lease_file(
    row: sqlite3.Row, evidence: dict[str, Any]
) -> bool:
    lock = Path(str(row["lease_lock_path"]))
    payload = _lock_payload(lock)
    _exact_lock(payload, row)
    existing = payload.get(_LEASE_FAILURE_FILE_KEY)
    if existing is not None:
        return existing == evidence
    payload[_LEASE_FAILURE_FILE_KEY] = dict(evidence)
    _replace_lock(lock, payload, row)
    return True


def persist_campaign_heartbeat_failure(
    db_path: str | Path,
    *,
    supervision_id: str,
    campaign_id: str,
    configuration_id: str,
    run_id: str,
    owner_id: str,
    evidence: dict[str, Any],
) -> dict[str, Any]:
    """Persist the first sanitized renewal failure; identical replay is a no-op."""
    required = {
        "safe_error_type", "safe_error_category", "safe_message",
        "sqlite_locked", "attempted_at", "renewal_confirmed", "terminal_cause",
    }
    if not required.issubset(evidence):
        raise CampaignSupervisionError("heartbeat failure evidence is incomplete")
    connection = _connect(db_path)
    try:
        _begin_immediate(connection)
        row = _load_exact(
            connection, supervision_id=supervision_id, campaign_id=campaign_id,
            configuration_id=configuration_id, run_id=run_id, owner_id=owner_id,
        )
        existing = connection.execute(
            "SELECT * FROM printer_memory_factory_campaign_heartbeat_failures "
            "WHERE supervision_id=?", (supervision_id,),
        ).fetchone()
        record = {
            "supervision_id": supervision_id,
            "campaign_id": campaign_id,
            "configuration_id": configuration_id,
            "run_id": run_id,
            "owner_id": owner_id,
            **evidence,
        }
        if existing is None:
            connection.execute(
                """INSERT INTO printer_memory_factory_campaign_heartbeat_failures(
                       supervision_id,campaign_id,configuration_id,run_id,owner_id,
                       safe_error_type,safe_error_category,safe_message,sqlite_locked,
                       attempted_at,prior_heartbeat_at,prior_lease_expires_at,
                       renewal_confirmed,terminal_cause,created_at
                   ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (
                    supervision_id, campaign_id, configuration_id, run_id, owner_id,
                    evidence["safe_error_type"], evidence["safe_error_category"],
                    evidence["safe_message"], int(bool(evidence["sqlite_locked"])),
                    evidence["attempted_at"], evidence.get("prior_heartbeat_at"),
                    evidence.get("prior_lease_expires_at"),
                    int(bool(evidence["renewal_confirmed"])),
                    evidence["terminal_cause"], evidence["attempted_at"],
                ),
            )
            created = True
        else:
            comparable = dict(existing)
            comparable["sqlite_locked"] = bool(comparable["sqlite_locked"])
            comparable["renewal_confirmed"] = bool(comparable["renewal_confirmed"])
            expected = {key: record.get(key) for key in comparable if key != "created_at"}
            actual = {key: comparable.get(key) for key in comparable if key != "created_at"}
            if actual != expected:
                raise CampaignSupervisionError(
                    "first heartbeat-renewal failure is immutable"
                )
            created = False
        connection.commit()
        try:
            lock_payload = _lock_payload(Path(str(row["lease_lock_path"])))
            _exact_lock(lock_payload, row)
        except CampaignSupervisionError:
            lock_payload = {}
        return {
            "persisted": True,
            "created": created,
            "lease_file_evidence_present": (
                lock_payload.get(_LEASE_FAILURE_FILE_KEY) == evidence
            ),
            "evidence": dict(evidence),
        }
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


def _connect(db_path: str | Path, *, read_only: bool = False) -> sqlite3.Connection:
    path = Path(db_path).resolve()
    if not path.is_file():
        raise CampaignSupervisionError(f"database missing: {path}")
    timeout = SQLITE_BUSY_TIMEOUT_SECONDS
    if read_only:
        connection = sqlite3.connect(
            f"file:{path.as_posix()}?mode=ro", uri=True, timeout=timeout
        )
        connection.execute("PRAGMA query_only=ON")
    else:
        connection = sqlite3.connect(path, timeout=timeout)
        connection.execute("PRAGMA foreign_keys=ON")
        connection.execute(
            f"PRAGMA busy_timeout={int(SQLITE_BUSY_TIMEOUT_SECONDS * 1000)}"
        )
    connection.row_factory = sqlite3.Row
    return connection


def _begin_immediate(connection: sqlite3.Connection) -> None:
    """Begin IMMEDIATE with bounded retries for transient SQLite lock contention."""
    last_error: BaseException | None = None
    for attempt in range(1, SQLITE_BUSY_MAX_ATTEMPTS + 1):
        try:
            connection.execute("BEGIN IMMEDIATE")
            return
        except sqlite3.OperationalError as exc:
            last_error = exc
            if not _is_sqlite_locked(exc) or attempt >= SQLITE_BUSY_MAX_ATTEMPTS:
                raise
            time.sleep(SQLITE_BUSY_RETRY_SECONDS)
    if last_error is not None:
        raise last_error


def _lock_payload(path: Path) -> dict[str, Any]:
    if not path.is_file():
        raise CampaignSupervisionError("operational campaign lease is missing")
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise CampaignSupervisionError("operational campaign lease is ambiguous") from exc
    if not isinstance(value, dict):
        raise CampaignSupervisionError("operational campaign lease is ambiguous")
    return value


def _exact_lock(payload: dict[str, Any], row: sqlite3.Row) -> None:
    expected = {
        "scope": OPERATIONAL_SCOPE,
        "supervision_id": row["supervision_id"],
        "campaign_id": row["campaign_id"],
        "configuration_id": row["configuration_id"],
        "run_id": row["run_id"],
        "owner_id": row["owner_id"],
    }
    if any(payload.get(key) != value for key, value in expected.items()):
        raise CampaignSupervisionError("operational campaign lease ownership mismatch")


def _write_new_lock(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        with path.open("x", encoding="utf-8", newline="\n") as handle:
            handle.write(json.dumps(payload, indent=2, sort_keys=True) + "\n")
    except FileExistsError as exc:
        raise CampaignSupervisionError("operational campaign lease already exists") from exc


def _is_transient_replace_error(exc: OSError) -> bool:
    return getattr(exc, "winerror", None) in _TRANSIENT_WINDOWS_REPLACE_ERRORS


def _replace_lock(path: Path, payload: dict[str, Any], row: sqlite3.Row) -> int:
    temporary = path.with_name(f".{path.name}.{uuid.uuid4().hex}.tmp")
    try:
        temporary.write_text(
            json.dumps(payload, indent=2, sort_keys=True) + "\n",
            encoding="utf-8", newline="\n",
        )
        for attempt in range(1, LEASE_REPLACE_MAX_ATTEMPTS + 1):
            _exact_lock(_lock_payload(path), row)
            try:
                os.replace(temporary, path)
                return attempt
            except OSError as exc:
                if not _is_transient_replace_error(exc) or (
                    attempt >= LEASE_REPLACE_MAX_ATTEMPTS
                ):
                    raise CampaignSupervisionError(
                        f"operational lease replacement unconfirmed after {attempt} attempt(s)"
                    ) from exc
                time.sleep(LEASE_REPLACE_RETRY_SECONDS)
        raise CampaignSupervisionError("operational lease replacement unconfirmed")
    finally:
        temporary.unlink(missing_ok=True)


def _release_lock(path: Path, row: sqlite3.Row) -> bool:
    if not path.exists():
        return True
    _exact_lock(_lock_payload(path), row)
    path.unlink()
    return not path.exists()


def _load_exact(
    connection: sqlite3.Connection,
    *,
    supervision_id: str,
    campaign_id: str,
    configuration_id: str,
    run_id: str,
    owner_id: str,
) -> sqlite3.Row:
    row = connection.execute(
        """SELECT * FROM printer_memory_factory_campaign_supervision
           WHERE supervision_id=? AND campaign_id=? AND configuration_id=?
             AND run_id=? AND owner_id=?""",
        (supervision_id, campaign_id, configuration_id, run_id, owner_id),
    ).fetchone()
    if row is None:
        raise CampaignSupervisionError("campaign supervision ownership mismatch")
    return row


def acquire_campaign_supervision(
    db_path: str | Path,
    *,
    lock_path: str | Path,
    supervision_id: str,
    campaign_id: str,
    configuration_id: str,
    run_id: str,
    owner_id: str,
    lease_seconds: int = DEFAULT_LEASE_SECONDS,
    now: datetime | None = None,
) -> dict[str, Any]:
    """Acquire the only lifetime operational owner for one campaign run."""
    if lease_seconds < 15:
        raise CampaignSupervisionError("lease must be at least 15 seconds")
    identities = {
        "supervision_id": _required(supervision_id, "supervision_id"),
        "campaign_id": _required(campaign_id, "campaign_id"),
        "configuration_id": _required(configuration_id, "configuration_id"),
        "run_id": _required(run_id, "run_id"),
        "owner_id": _required(owner_id, "owner_id"),
    }
    instant = now or datetime.now(timezone.utc)
    heartbeat = _iso(instant)
    expiry = _iso(instant + timedelta(seconds=lease_seconds))
    lock = Path(lock_path).resolve()
    payload = {
        "scope": OPERATIONAL_SCOPE,
        **identities,
        "heartbeat_at": heartbeat,
        "lease_expires_at": expiry,
        "created_at": heartbeat,
        "updated_at": heartbeat,
    }
    _write_new_lock(lock, payload)
    connection = _connect(db_path)
    try:
        _begin_immediate(connection)
        graph = connection.execute(
            """SELECT c.campaign_state,r.run_state
               FROM printer_memory_factory_campaigns AS c
               JOIN printer_memory_factory_campaign_configurations AS cfg
                 ON cfg.campaign_id=c.campaign_id AND cfg.configuration_id=?
               JOIN printer_memory_factory_campaign_runs AS r
                 ON r.campaign_id=c.campaign_id AND r.run_id=?
               WHERE c.campaign_id=?""",
            (configuration_id, run_id, campaign_id),
        ).fetchone()
        if graph is None:
            raise CampaignSupervisionError("campaign/configuration/run ownership mismatch")
        existing = connection.execute(
            """SELECT supervision_id
               FROM printer_memory_factory_campaign_supervision
               WHERE campaign_id=? AND run_id=?""",
            (campaign_id, run_id),
        ).fetchone()
        if existing is not None:
            raise CampaignSupervisionError(
                "campaign run supervision already exists; resume is forbidden"
            )
        if graph["campaign_state"] != "RUNNING" or graph["run_state"] != "RUNNING":
            raise CampaignSupervisionError("campaign and run must both be RUNNING")
        connection.execute(
            """INSERT INTO printer_memory_factory_campaign_supervision(
                   supervision_id,campaign_id,configuration_id,run_id,owner_id,
                   supervision_state,heartbeat_at,lease_expires_at,lease_lock_path,
                   created_at,updated_at
               ) VALUES (?,?,?,?,?,'ACTIVE',?,?,?,?,?)""",
            (
                supervision_id, campaign_id, configuration_id, run_id, owner_id,
                heartbeat, expiry, str(lock), heartbeat, heartbeat,
            ),
        )
        connection.commit()
    except (sqlite3.Error, CampaignSupervisionError) as exc:
        connection.rollback()
        lock.unlink(missing_ok=True)
        if isinstance(exc, CampaignSupervisionError):
            raise
        raise CampaignSupervisionError(str(exc)) from exc
    finally:
        connection.close()
    return inspect_campaign_supervision(
        db_path, **identities, now=instant
    )


def inspect_campaign_supervision(
    db_path: str | Path,
    *,
    supervision_id: str,
    campaign_id: str,
    configuration_id: str,
    run_id: str,
    owner_id: str,
    now: datetime | None = None,
) -> dict[str, Any]:
    connection = _connect(db_path, read_only=True)
    try:
        row = _load_exact(
            connection, supervision_id=supervision_id, campaign_id=campaign_id,
            configuration_id=configuration_id, run_id=run_id, owner_id=owner_id,
        )
        result = dict(row)
        if row["supervision_state"] != "TERMINAL":
            payload = _lock_payload(Path(row["lease_lock_path"]))
            _exact_lock(payload, row)
            result["lock_heartbeat_at"] = payload.get("heartbeat_at")
            result["lock_lease_expires_at"] = payload.get("lease_expires_at")
        instant = now or datetime.now(timezone.utc)
        result["lease_expired"] = _parse(str(row["lease_expires_at"])) <= instant
        result["new_child_work_allowed"] = (
            row["supervision_state"] == "ACTIVE"
            and not result["lease_expired"]
            and row["cancellation_requested_at"] is None
        )
        result["read_only"] = True
        return result
    finally:
        connection.close()


def renew_campaign_lease(
    db_path: str | Path,
    *,
    supervision_id: str,
    campaign_id: str,
    configuration_id: str,
    run_id: str,
    owner_id: str,
    lease_seconds: int = DEFAULT_LEASE_SECONDS,
    now: datetime | None = None,
) -> dict[str, Any]:
    """Renew monotonically or report failure without performing terminal cleanup.

    V2-9.8B.2: lease renewal never terminalizes owned work. Heartbeat threads must
    only signal failure; the main terminal coordinator owns cleanup, first-cause
    preservation, lease release, and report persistence.
    """
    if lease_seconds < 15:
        raise CampaignSupervisionError("lease must be at least 15 seconds")
    instant = now or datetime.now(timezone.utc)
    attempt_at = _iso(instant)
    row: sqlite3.Row | None = None
    connection = _connect(db_path, read_only=True)
    try:
        row = _load_exact(
            connection, supervision_id=supervision_id, campaign_id=campaign_id,
            configuration_id=configuration_id, run_id=run_id, owner_id=owner_id,
        )
        if row["supervision_state"] != "ACTIVE":
            raise CampaignSupervisionError("campaign supervision is not renewable")
    finally:
        connection.close()

    try:
        previous_heartbeat = _parse(str(row["heartbeat_at"]))
        previous_expiry = _parse(str(row["lease_expires_at"]))
        if previous_expiry <= instant:
            raise CampaignSupervisionError("operational campaign lease is expired")
        next_expiry = instant + timedelta(seconds=lease_seconds)
        if instant <= previous_heartbeat or next_expiry <= previous_expiry:
            raise CampaignSupervisionError("lease renewal must advance monotonically")
        lock = Path(row["lease_lock_path"])
        payload = _lock_payload(lock)
        _exact_lock(payload, row)
        payload.update({
            "heartbeat_at": _iso(instant),
            "lease_expires_at": _iso(next_expiry),
            "updated_at": _iso(instant),
        })
        attempts = _replace_lock(lock, payload, row)
        connection = _connect(db_path)
        try:
            _begin_immediate(connection)
            cursor = connection.execute(
                """UPDATE printer_memory_factory_campaign_supervision
                   SET heartbeat_at=?,lease_expires_at=?,updated_at=?
                   WHERE supervision_id=? AND owner_id=?
                     AND supervision_state='ACTIVE'
                     AND heartbeat_at=? AND lease_expires_at=?""",
                (
                    _iso(instant), _iso(next_expiry), _iso(instant),
                    supervision_id, owner_id, _iso(previous_heartbeat),
                    _iso(previous_expiry),
                ),
            )
            if cursor.rowcount != 1:
                raise CampaignSupervisionError("lease ledger renewal was unconfirmed")
            connection.commit()
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()
    except (CampaignSupervisionError, OSError, sqlite3.Error) as exc:
        evidence = _safe_renewal_failure(
            exc,
            attempted_at=attempt_at,
            prior_heartbeat_at=(None if row is None else str(row["heartbeat_at"])),
            prior_lease_expires_at=(
                None if row is None else str(row["lease_expires_at"])
            ),
        )
        durable_location: str | None = None
        try:
            persist_campaign_heartbeat_failure(
                db_path,
                supervision_id=supervision_id, campaign_id=campaign_id,
                configuration_id=configuration_id, run_id=run_id,
                owner_id=owner_id, evidence=evidence,
            )
            durable_location = "SQLITE"
        except (CampaignSupervisionError, OSError, sqlite3.Error):
            if row is not None and _persist_failure_to_lease_file(row, evidence):
                durable_location = "LEASE_FILE"
        return {
            "renewal_confirmed": False,
            "renewal_error": evidence["safe_message"],
            "renewal_error_type": evidence["safe_error_type"],
            "renewal_error_category": evidence["safe_error_category"],
            "sqlite_locked": evidence["sqlite_locked"],
            "attempted_at": evidence["attempted_at"],
            "prior_heartbeat_at": evidence["prior_heartbeat_at"],
            "prior_lease_expires_at": evidence["prior_lease_expires_at"],
            "failure_evidence": evidence,
            "durable_evidence_location": durable_location,
            "terminal_cleanup_performed": False,
            "safe_stop": None,
            "new_child_work_allowed": False,
            "signal_main_coordinator": True,
            "suggested_terminal_cause": evidence["terminal_cause"],
        }
    return {
        "renewal_confirmed": True,
        "heartbeat_at": _iso(instant),
        "lease_expires_at": _iso(next_expiry),
        "lease_replace_attempts": attempts,
        "lease_replace_retries": attempts - 1,
        "terminal_cleanup_performed": False,
        "new_child_work_allowed": True,
    }


def request_campaign_cancellation(
    db_path: str | Path,
    *,
    supervision_id: str,
    campaign_id: str,
    configuration_id: str,
    run_id: str,
    owner_id: str,
    reason: str,
    now: datetime | None = None,
) -> dict[str, Any]:
    """Persist a cooperative stop request without running child work."""
    cause = _required(reason, "cancellation reason")
    timestamp = _iso(now)
    connection = _connect(db_path)
    try:
        _begin_immediate(connection)
        row = _load_exact(
            connection, supervision_id=supervision_id, campaign_id=campaign_id,
            configuration_id=configuration_id, run_id=run_id, owner_id=owner_id,
        )
        if row["supervision_state"] == "TERMINAL":
            raise CampaignSupervisionError("terminal campaign cannot accept cancellation")
        if row["cancellation_reason"] not in (None, cause):
            raise CampaignSupervisionError("first cancellation reason is immutable")
        connection.execute(
            """UPDATE printer_memory_factory_campaign_supervision
               SET supervision_state='STOPPING',
                   cancellation_requested_at=COALESCE(cancellation_requested_at,?),
                   cancellation_reason=COALESCE(cancellation_reason,?),updated_at=?
               WHERE supervision_id=? AND owner_id=?""",
            (timestamp, cause, timestamp, supervision_id, owner_id),
        )
        for table, identity_column, identity in (
            ("printer_memory_factory_campaigns", "campaign_id", campaign_id),
            ("printer_memory_factory_campaign_runs", "run_id", run_id),
        ):
            connection.execute(
                f"""UPDATE {table} SET
                    {('campaign_state' if identity_column == 'campaign_id' else 'run_state')}='STOP_REQUESTED',
                    updated_at=? WHERE {identity_column}=?
                    AND {('campaign_state' if identity_column == 'campaign_id' else 'run_state')}='RUNNING'""",
                (timestamp, identity),
            )
        connection.commit()
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()
    return {
        "cancellation_requested": True,
        "cancellation_reason": cause,
        "new_child_work_allowed": False,
    }


def _terminal_targets(terminal_status: str) -> tuple[str, str]:
    if terminal_status == "COMPLETED":
        return "TERMINAL_COMPLETED", "TERMINAL_COMPLETED"
    if terminal_status == "CANCELLED":
        return "TERMINAL_STOPPED", "TERMINAL_STOPPED"
    return "TERMINAL_FAILED", "TERMINAL_FAILED"


def _table_exists(connection: sqlite3.Connection, table: str) -> bool:
    return (
        connection.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?",
            (table,),
        ).fetchone()
        is not None
    )


def _finish_released_lease(
    db_path: str | Path, row: sqlite3.Row, *, released_at: str,
) -> None:
    connection = _connect(db_path)
    try:
        connection.execute(
            """UPDATE printer_memory_factory_campaign_supervision
               SET lease_released_at=COALESCE(lease_released_at,?),updated_at=?
               WHERE supervision_id=? AND owner_id=? AND supervision_state='TERMINAL'""",
            (released_at, released_at, row["supervision_id"], row["owner_id"]),
        )
        connection.commit()
    finally:
        connection.close()


def cleanup_campaign_supervision(
    db_path: str | Path,
    *,
    supervision_id: str,
    campaign_id: str,
    configuration_id: str,
    run_id: str,
    owner_id: str,
    terminal_status: str,
    first_terminal_cause: str,
    now: datetime | None = None,
) -> dict[str, Any]:
    """Use one transactional cleanup path, then release the exact lease."""
    if terminal_status not in _TERMINAL_STATUSES:
        raise CampaignSupervisionError("unsupported operational terminal status")
    cause = _required(first_terminal_cause, "first_terminal_cause")
    timestamp = _iso(now)
    connection = _connect(db_path)
    replay = False
    discovery_work_rowcount = 0
    discovery_batch_rowcount = 0
    work_cursor = None
    job_cursor = None
    window_cursor = None
    cycle_cursor = None
    try:
        _begin_immediate(connection)
        row = _load_exact(
            connection, supervision_id=supervision_id, campaign_id=campaign_id,
            configuration_id=configuration_id, run_id=run_id, owner_id=owner_id,
        )
        if row["supervision_state"] == "TERMINAL":
            # Idempotent same-identity cleanup always preserves the first
            # terminal status/cause (first-fault). Ownership mismatches still
            # fail closed via _load_exact before this branch.
            replay = True
            terminal_status = str(row["terminal_status"])
            cause = str(row["first_terminal_cause"])
            connection.rollback()
        else:
            shared = connection.execute(
                """SELECT work.scheduler_job_id
                   FROM printer_memory_factory_campaign_scheduler_work AS work
                   WHERE work.campaign_id=? AND work.run_id=?
                     AND work.scheduler_job_id IS NOT NULL
                     AND EXISTS (
                         SELECT 1
                         FROM printer_memory_factory_campaign_scheduler_work AS other
                         WHERE other.scheduler_job_id=work.scheduler_job_id
                           AND (other.campaign_id<>work.campaign_id
                                OR other.run_id<>work.run_id)
                     ) LIMIT 1""",
                (campaign_id, run_id),
            ).fetchone()
            if shared is not None:
                raise CampaignSupervisionError("scheduler job ownership is ambiguous")
            run_target, cycle_target = _terminal_targets(terminal_status)
            work_cursor = connection.execute(
                """UPDATE printer_memory_factory_campaign_scheduler_work
                   SET work_state='CANCELLED',first_terminal_cause=?,terminal_at=?,updated_at=?
                   WHERE campaign_id=? AND run_id=?
                     AND work_state IN ('PENDING','RUNNING','COOLDOWN')""",
                (cause, timestamp, timestamp, campaign_id, run_id),
            )
            # Discovery intake work is owned via printer_discovery_work (migration
            # 034), not only campaign_scheduler_work. Terminalize those rows and
            # cancel their Scheduler jobs so insufficient-pool stops leave no
            # ACTIVE discovery residue.
            discovery_work_rowcount = 0
            discovery_batch_rowcount = 0
            if _table_exists(connection, "printer_discovery_work"):
                discovery_work_cursor = connection.execute(
                    """UPDATE printer_discovery_work
                       SET work_state=CASE
                             WHEN work_state IN ('SUCCEEDED','FAILED','CANCELLED')
                             THEN work_state ELSE 'FAILED' END,
                           first_terminal_cause=COALESCE(first_terminal_cause,?),
                           terminal_at=COALESCE(terminal_at,?),
                           updated_at=?
                       WHERE campaign_id=? AND run_id=?
                         AND work_state IN ('PENDING','RUNNING','COOLDOWN')""",
                    (cause, timestamp, timestamp, campaign_id, run_id),
                )
                discovery_work_rowcount = int(discovery_work_cursor.rowcount)
            if _table_exists(connection, "printer_discovery_batches"):
                discovery_batch_cursor = connection.execute(
                    """UPDATE printer_discovery_batches
                       SET batch_state='TERMINAL_FAILED',
                           first_terminal_cause=COALESCE(first_terminal_cause,?),
                           terminal_at=COALESCE(terminal_at,?)
                       WHERE campaign_id=? AND run_id=?
                         AND batch_state NOT LIKE 'TERMINAL_%'""",
                    (cause, timestamp, campaign_id, run_id),
                )
                discovery_batch_rowcount = int(discovery_batch_cursor.rowcount)
            if _table_exists(connection, "printer_discovery_work"):
                job_cursor = connection.execute(
                    """UPDATE printer_scheduler_jobs
                       SET status='CANCELLED',finished_at=?,locked_at=NULL,
                           lock_owner=NULL,
                           last_error=COALESCE(last_error,?),updated_at=?
                       WHERE (
                           id IN (
                               SELECT scheduler_job_id
                               FROM printer_memory_factory_campaign_scheduler_work
                               WHERE campaign_id=? AND run_id=?
                                 AND scheduler_job_id IS NOT NULL
                           )
                           OR id IN (
                               SELECT scheduler_job_id
                               FROM printer_discovery_work
                               WHERE campaign_id=? AND run_id=?
                                 AND scheduler_job_id IS NOT NULL
                           )
                       ) AND (status IN ('PENDING','RUNNING','COOLDOWN')
                              OR locked_at IS NOT NULL OR lock_owner IS NOT NULL)""",
                    (
                        timestamp, cause, timestamp,
                        campaign_id, run_id,
                        campaign_id, run_id,
                    ),
                )
            else:
                job_cursor = connection.execute(
                    """UPDATE printer_scheduler_jobs
                       SET status='CANCELLED',finished_at=?,locked_at=NULL,
                           lock_owner=NULL,
                           last_error=COALESCE(last_error,?),updated_at=?
                       WHERE id IN (
                           SELECT scheduler_job_id
                           FROM printer_memory_factory_campaign_scheduler_work
                           WHERE campaign_id=? AND run_id=?
                             AND scheduler_job_id IS NOT NULL
                       ) AND (status IN ('PENDING','RUNNING','COOLDOWN')
                              OR locked_at IS NOT NULL OR lock_owner IS NOT NULL)""",
                    (timestamp, cause, timestamp, campaign_id, run_id),
                )
            window_cursor = connection.execute(
                """UPDATE printer_memory_factory_campaign_windows
                   SET window_state='CANCELLED',first_terminal_cause=?,terminal_at=?,updated_at=?
                   WHERE campaign_id=? AND run_id=?
                     AND window_state IN ('PLANNED','COLLECTING','CLOSE_PENDING','AUDITING')""",
                (cause, timestamp, timestamp, campaign_id, run_id),
            )
            cycle_cursor = connection.execute(
                """UPDATE printer_memory_factory_campaign_cycles
                   SET cycle_state=?,first_terminal_cause=?,terminal_at=?,updated_at=?
                   WHERE campaign_id=? AND run_id=? AND cycle_state NOT LIKE 'TERMINAL_%'""",
                (cycle_target, cause, timestamp, timestamp, campaign_id, run_id),
            )
            for table, state_column, identity_column, identity in (
                ("printer_memory_factory_campaign_runs", "run_state", "run_id", run_id),
                ("printer_memory_factory_campaigns", "campaign_state", "campaign_id", campaign_id),
            ):
                current = connection.execute(
                    f"SELECT {state_column},first_terminal_cause FROM {table} WHERE {identity_column}=?",
                    (identity,),
                ).fetchone()
                if current is None or str(current[state_column]).startswith("TERMINAL_"):
                    raise CampaignSupervisionError("campaign terminal ownership is inconsistent")
                connection.execute(
                    f"""UPDATE {table} SET {state_column}=?,first_terminal_cause=?,
                        terminal_at=?,updated_at=? WHERE {identity_column}=?""",
                    (run_target, cause, timestamp, timestamp, identity),
                )
            active_work = int(connection.execute(
                """SELECT COUNT(*)
                   FROM printer_memory_factory_campaign_scheduler_work AS work
                   LEFT JOIN printer_scheduler_jobs AS job ON job.id=work.scheduler_job_id
                   WHERE work.campaign_id=? AND work.run_id=?
                     AND (work.work_state IN ('PENDING','RUNNING','COOLDOWN')
                          OR job.status IN ('PENDING','RUNNING','COOLDOWN')
                          OR job.locked_at IS NOT NULL OR job.lock_owner IS NOT NULL)""",
                (campaign_id, run_id),
            ).fetchone()[0])
            active_discovery = 0
            if _table_exists(connection, "printer_discovery_work"):
                active_discovery = int(connection.execute(
                    """SELECT COUNT(*)
                       FROM printer_discovery_work AS work
                       LEFT JOIN printer_scheduler_jobs AS job
                         ON job.id=work.scheduler_job_id
                       WHERE work.campaign_id=? AND work.run_id=?
                         AND (work.work_state IN ('PENDING','RUNNING','COOLDOWN')
                              OR job.status IN ('PENDING','RUNNING','COOLDOWN')
                              OR job.locked_at IS NOT NULL
                              OR job.lock_owner IS NOT NULL)""",
                    (campaign_id, run_id),
                ).fetchone()[0])
            if active_work or active_discovery:
                raise CampaignSupervisionError("campaign child-work cleanup is incomplete")
            connection.execute(
                """UPDATE printer_memory_factory_campaign_supervision
                   SET supervision_state='TERMINAL',terminal_status=?,
                       first_terminal_cause=?,cleanup_completed_at=?,updated_at=?
                   WHERE supervision_id=? AND owner_id=?
                     AND supervision_state IN ('ACTIVE','STOPPING')""",
                (terminal_status, cause, timestamp, timestamp, supervision_id, owner_id),
            )
            connection.commit()
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()

    connection = _connect(db_path, read_only=True)
    try:
        terminal_row = _load_exact(
            connection, supervision_id=supervision_id, campaign_id=campaign_id,
            configuration_id=configuration_id, run_id=run_id, owner_id=owner_id,
        )
        active_after = int(connection.execute(
            """SELECT COUNT(*)
               FROM printer_memory_factory_campaign_scheduler_work AS work
               LEFT JOIN printer_scheduler_jobs AS job ON job.id=work.scheduler_job_id
               WHERE work.campaign_id=? AND work.run_id=?
                 AND (work.work_state IN ('PENDING','RUNNING','COOLDOWN')
                      OR job.status IN ('PENDING','RUNNING','COOLDOWN')
                      OR job.locked_at IS NOT NULL OR job.lock_owner IS NOT NULL)""",
            (campaign_id, run_id),
        ).fetchone()[0])
        if _table_exists(connection, "printer_discovery_work"):
            active_after += int(connection.execute(
                """SELECT COUNT(*)
                   FROM printer_discovery_work AS work
                   LEFT JOIN printer_scheduler_jobs AS job
                     ON job.id=work.scheduler_job_id
                   WHERE work.campaign_id=? AND work.run_id=?
                     AND (work.work_state IN ('PENDING','RUNNING','COOLDOWN')
                          OR job.status IN ('PENDING','RUNNING','COOLDOWN')
                          OR job.locked_at IS NOT NULL
                          OR job.lock_owner IS NOT NULL)""",
                (campaign_id, run_id),
            ).fetchone()[0])
    finally:
        connection.close()
    released = _release_lock(Path(terminal_row["lease_lock_path"]), terminal_row)
    if not released:
        raise CampaignSupervisionError("operational campaign lease release failed")
    _finish_released_lease(db_path, terminal_row, released_at=timestamp)
    return {
        "supervision_id": supervision_id,
        "campaign_id": campaign_id,
        "configuration_id": configuration_id,
        "run_id": run_id,
        "owner_id": owner_id,
        "terminal_status": terminal_status,
        "first_terminal_cause": cause,
        "cancelled_campaign_work": 0 if replay else int(work_cursor.rowcount),
        "cancelled_discovery_work": 0 if replay else discovery_work_rowcount,
        "terminalized_discovery_batches": (
            0 if replay else discovery_batch_rowcount
        ),
        "cancelled_scheduler_jobs": 0 if replay else int(job_cursor.rowcount),
        "cancelled_windows": 0 if replay else int(window_cursor.rowcount),
        "terminalized_cycles": 0 if replay else int(cycle_cursor.rowcount),
        "active_owned_work_after": active_after,
        "cleanup_completed": True,
        "lease_released": True,
        "new_child_work_allowed": False,
        "idempotent_replay": replay,
        "automatic_retries": 0,
        "resume_created": False,
        "successor_created": False,
        "restart_created": False,
    }
