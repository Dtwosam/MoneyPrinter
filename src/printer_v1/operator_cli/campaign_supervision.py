"""Operational campaign lease ownership and transactional safe-stop."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
import json
import os
from pathlib import Path
import sqlite3
import time
from typing import Any, Callable, Mapping
import uuid

from printer_v1.operator_cli.campaign_persistence import (
    campaign_evidence_sha256,
    canonical_campaign_evidence_json,
)


OPERATIONAL_SCOPE = "OPERATIONAL_CAMPAIGN"
INVOCATION_MARKER_KIND = "PRINTER_V1_CAMPAIGN_SUPERVISION_ACQUISITION"
INVOCATION_MARKER_VERSION = "V2_9_8B_C12_C14_V1"
DEFAULT_LEASE_SECONDS = 90
LEASE_REPLACE_MAX_ATTEMPTS = 3
LEASE_REPLACE_RETRY_SECONDS = 0.05
# V2-9.8B.2: bounded SQLite lock wait. timeout=0 caused the heartbeat renewer to
# fail immediately under a legitimate main-writer lock and previously triggered
# terminal cleanup from the heartbeat thread.
SQLITE_BUSY_TIMEOUT_SECONDS = 2.0
SQLITE_BUSY_MAX_ATTEMPTS = 5
SQLITE_BUSY_RETRY_SECONDS = 0.05
# V2-9.8B post-consumption lease-contention contract: one hard renewal deadline.
LEASE_CONTENTION_WALL_CLOCK_SECONDS = 15.0
LEASE_CONTENTION_REMAINING_SAFETY_SECONDS = 15.0
LEASE_CONTENTION_OUTER_MAX_ATTEMPTS = 3
LEASE_CONTENTION_OUTER_SLEEP_SECONDS = 0.25
LEASE_CONTENTION_MIN_BLOCK_SECONDS = 0.001
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


def build_invocation_marker_payload(
    supervision: Mapping[str, Any], *, authorization_marker_id: str
) -> dict[str, Any]:
    """Reconstruct the canonical marker owned by supervision acquisition."""
    supervision_id = _required(supervision.get("supervision_id"), "supervision_id")
    created_at = _required(supervision.get("created_at"), "created_at")
    lease_lock_path = _required(
        supervision.get("lease_lock_path"), "lease_lock_path"
    )
    payload = {
        "marker_kind": INVOCATION_MARKER_KIND,
        "marker_version": INVOCATION_MARKER_VERSION,
        "marker_id": f"{supervision_id}-invocation-marker",
        "supervision_id": supervision_id,
        "campaign_id": _required(supervision.get("campaign_id"), "campaign_id"),
        "configuration_id": _required(
            supervision.get("configuration_id"), "configuration_id"
        ),
        "run_id": _required(supervision.get("run_id"), "run_id"),
        "owner_id": _required(supervision.get("owner_id"), "owner_id"),
        "lease_lock_path": lease_lock_path,
        "lease_lock_path_identity": campaign_evidence_sha256(
            {"lease_lock_path": lease_lock_path}
        ),
        "acquisition_identity": f"{supervision_id}|{created_at}",
        "acquired_at": created_at,
        "authorization_marker_id": _required(
            authorization_marker_id, "authorization_marker_id"
        ),
    }
    canonical_campaign_evidence_json(payload)
    return payload


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


def _connect(
    db_path: str | Path,
    *,
    read_only: bool = False,
    busy_timeout_seconds: float | None = None,
) -> sqlite3.Connection:
    path = Path(db_path).resolve()
    if not path.is_file():
        raise CampaignSupervisionError(f"database missing: {path}")
    timeout = (
        SQLITE_BUSY_TIMEOUT_SECONDS
        if busy_timeout_seconds is None
        else float(busy_timeout_seconds)
    )
    if timeout < 0:
        raise CampaignSupervisionError("busy timeout must be non-negative")
    if read_only:
        connection = sqlite3.connect(
            f"file:{path.as_posix()}?mode=ro", uri=True, timeout=timeout
        )
        connection.execute("PRAGMA query_only=ON")
    else:
        connection = sqlite3.connect(path, timeout=timeout)
        connection.execute("PRAGMA foreign_keys=ON")
        connection.execute(f"PRAGMA busy_timeout={int(timeout * 1000)}")
    connection.row_factory = sqlite3.Row
    return connection


def _configure_busy_timeout(
    connection: sqlite3.Connection, *, busy_timeout_seconds: float
) -> None:
    timeout = float(busy_timeout_seconds)
    if timeout < 0:
        raise CampaignSupervisionError("busy timeout must be non-negative")
    connection.execute(f"PRAGMA busy_timeout={int(timeout * 1000)}")


def _begin_immediate(
    connection: sqlite3.Connection,
    *,
    deadline_monotonic: float | None = None,
    busy_timeout_ceiling: float | None = None,
    before_block: Callable[[float], None] | None = None,
) -> None:
    """Begin IMMEDIATE with bounded retries for transient SQLite lock contention.

    When ``deadline_monotonic`` is set, every inner wait/sleep is clamped so the
    call cannot extend past that hard deadline. A renewal-only ``before_block``
    callback may additionally re-prove lease safety before each blocking wait or
    retry sleep. Other callers omit both and keep the historical busy contract.
    """
    last_error: BaseException | None = None
    ceiling = (
        SQLITE_BUSY_TIMEOUT_SECONDS
        if busy_timeout_ceiling is None
        else float(busy_timeout_ceiling)
    )
    for attempt in range(1, SQLITE_BUSY_MAX_ATTEMPTS + 1):
        planned = ceiling
        if deadline_monotonic is not None:
            remaining = deadline_monotonic - time.monotonic()
            if remaining < LEASE_CONTENTION_MIN_BLOCK_SECONDS:
                raise sqlite3.OperationalError("database is locked")
            planned = min(ceiling, remaining)
            if planned < LEASE_CONTENTION_MIN_BLOCK_SECONDS:
                raise sqlite3.OperationalError("database is locked")
        if before_block is not None:
            before_block(planned)
        if deadline_monotonic is not None:
            _configure_busy_timeout(connection, busy_timeout_seconds=planned)
        try:
            connection.execute("BEGIN IMMEDIATE")
            return
        except sqlite3.OperationalError as exc:
            last_error = exc
            if not _is_sqlite_locked(exc) or attempt >= SQLITE_BUSY_MAX_ATTEMPTS:
                raise
            sleep_for = SQLITE_BUSY_RETRY_SECONDS
            if deadline_monotonic is not None:
                remaining = deadline_monotonic - time.monotonic()
                if sleep_for > remaining:
                    raise sqlite3.OperationalError("database is locked")
            if before_block is not None:
                before_block(sleep_for)
            time.sleep(sleep_for)
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
    connection: sqlite3.Connection | None = None
    try:
        connection = _connect(db_path)
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
        if connection is not None:
            connection.rollback()
        try:
            lock.unlink(missing_ok=True)
        except OSError as cleanup_exc:
            exc.add_note(
                "new supervision lock cleanup failed: "
                f"{type(cleanup_exc).__name__}:{cleanup_exc}"
            )
        if isinstance(exc, CampaignSupervisionError):
            raise
        raise CampaignSupervisionError(str(exc)) from exc
    finally:
        if connection is not None:
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


def _renewal_contention_preflight(
    *,
    row: sqlite3.Row,
    check_now: datetime,
    renewal_deadline: float,
) -> float:
    """Return planned busy seconds or raise fail-closed without blocking."""
    remaining_deadline = renewal_deadline - time.monotonic()
    if remaining_deadline < LEASE_CONTENTION_MIN_BLOCK_SECONDS:
        raise sqlite3.OperationalError("database is locked")
    if str(row["supervision_state"]) != "ACTIVE":
        raise CampaignSupervisionError("campaign supervision is not renewable")
    previous_expiry = _parse(str(row["lease_expires_at"]))
    remaining_lease = (previous_expiry - check_now).total_seconds()
    if remaining_lease <= 0:
        raise CampaignSupervisionError("operational campaign lease is expired")
    if remaining_lease <= LEASE_CONTENTION_REMAINING_SAFETY_SECONDS:
        raise sqlite3.OperationalError("database is locked")
    planned_block = min(SQLITE_BUSY_TIMEOUT_SECONDS, remaining_deadline)
    if planned_block < LEASE_CONTENTION_MIN_BLOCK_SECONDS:
        raise sqlite3.OperationalError("database is locked")
    if (
        remaining_lease - planned_block
        <= LEASE_CONTENTION_REMAINING_SAFETY_SECONDS
    ):
        raise sqlite3.OperationalError("database is locked")
    return planned_block


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

    Post-consumption amendment: one hard monotonic 15s deadline, deadline-clamped
    busy waits, DB ledger CAS commit before lease-file mirror, and
    ``renewal_confirmed=True`` only when DB and file agree.
    """
    if lease_seconds < 15:
        raise CampaignSupervisionError("lease must be at least 15 seconds")
    t0 = time.monotonic()
    renewal_deadline = t0 + LEASE_CONTENTION_WALL_CLOCK_SECONDS
    instant = now or datetime.now(timezone.utc)
    attempt_at = _iso(instant)
    row: sqlite3.Row | None = None
    db_ledger_advanced = False
    contention_outer_attempts = 0
    next_heartbeat = _iso(instant)
    next_expiry_iso = _iso(instant + timedelta(seconds=lease_seconds))
    previous_heartbeat_iso: str | None = None
    previous_expiry_iso: str | None = None
    lock: Path | None = None
    lease_replace_attempts = 0

    def _renewal_now() -> datetime:
        if now is None:
            return datetime.now(timezone.utc)
        elapsed = max(0.0, time.monotonic() - t0)
        return instant + timedelta(seconds=elapsed)

    def _renewal_block_preflight(planned_block: float) -> None:
        remaining_deadline = renewal_deadline - time.monotonic()
        planned = float(planned_block)
        if (
            planned < LEASE_CONTENTION_MIN_BLOCK_SECONDS
            or remaining_deadline < LEASE_CONTENTION_MIN_BLOCK_SECONDS
            or planned > remaining_deadline
        ):
            raise sqlite3.OperationalError("database is locked")
        preflight = _connect(
            db_path,
            read_only=True,
            busy_timeout_seconds=0.0,
        )
        try:
            current = _load_exact(
                preflight,
                supervision_id=supervision_id,
                campaign_id=campaign_id,
                configuration_id=configuration_id,
                run_id=run_id,
                owner_id=owner_id,
            )
            if str(current["supervision_state"]) != "ACTIVE":
                raise CampaignSupervisionError(
                    "campaign supervision is not renewable"
                )
            remaining_lease = (
                _parse(str(current["lease_expires_at"])) - _renewal_now()
            ).total_seconds()
            if remaining_lease <= 0:
                raise CampaignSupervisionError(
                    "operational campaign lease is expired"
                )
            if (
                remaining_lease <= LEASE_CONTENTION_REMAINING_SAFETY_SECONDS
                or remaining_lease - planned
                <= LEASE_CONTENTION_REMAINING_SAFETY_SECONDS
            ):
                raise sqlite3.OperationalError("database is locked")
        finally:
            preflight.close()

    def _failure_return(exc: BaseException) -> dict[str, Any]:
        nonlocal db_ledger_advanced
        if db_ledger_advanced:
            evidence = _safe_renewal_failure(
                CampaignSupervisionError(
                    "Operational campaign lease renewal was not confirmed."
                ),
                attempted_at=attempt_at,
                prior_heartbeat_at=previous_heartbeat_iso,
                prior_lease_expires_at=previous_expiry_iso,
            )
        else:
            evidence = _safe_renewal_failure(
                exc,
                attempted_at=attempt_at,
                prior_heartbeat_at=previous_heartbeat_iso,
                prior_lease_expires_at=previous_expiry_iso,
            )
        durable_location: str | None = None
        # After a contention-bound failure the writer may still hold SQLite.
        # Prefer lease-file evidence immediately for lock contention so failure
        # persistence cannot extend past the renewal deadline; otherwise try DB.
        if evidence.get("sqlite_locked") and row is not None:
            if _persist_failure_to_lease_file(row, evidence):
                durable_location = "LEASE_FILE"
        if durable_location is None:
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
            "db_ledger_advanced": db_ledger_advanced,
            "lease_file_synced": False,
            "contention_outer_attempts": contention_outer_attempts,
            "contention_wait_ms": int(max(0.0, (time.monotonic() - t0) * 1000.0)),
        }

    # Ownership / ACTIVE precheck remains outside the sanitized failure-return
    # path so exact ownership mismatches still raise to the caller.
    connection = _connect(db_path, read_only=True)
    try:
        row = _load_exact(
            connection, supervision_id=supervision_id, campaign_id=campaign_id,
            configuration_id=configuration_id, run_id=run_id, owner_id=owner_id,
        )
        if row["supervision_state"] != "ACTIVE":
            raise CampaignSupervisionError("campaign supervision is not renewable")
        previous_heartbeat = _parse(str(row["heartbeat_at"]))
        previous_expiry = _parse(str(row["lease_expires_at"]))
        previous_heartbeat_iso = str(row["heartbeat_at"])
        previous_expiry_iso = str(row["lease_expires_at"])
        lock = Path(str(row["lease_lock_path"]))
        payload = _lock_payload(lock)
        _exact_lock(payload, row)
    finally:
        connection.close()

    try:
        if previous_expiry <= instant:
            raise CampaignSupervisionError("operational campaign lease is expired")
        next_expiry = instant + timedelta(seconds=lease_seconds)
        if instant <= previous_heartbeat or next_expiry <= previous_expiry:
            raise CampaignSupervisionError(
                "lease renewal must advance monotonically"
            )
        next_expiry_iso = _iso(next_expiry)

        for outer in range(1, LEASE_CONTENTION_OUTER_MAX_ATTEMPTS + 1):
            contention_outer_attempts = outer
            remaining_deadline = renewal_deadline - time.monotonic()
            if remaining_deadline < LEASE_CONTENTION_MIN_BLOCK_SECONDS:
                raise sqlite3.OperationalError("database is locked")
            preflight_busy = min(
                SQLITE_BUSY_TIMEOUT_SECONDS, remaining_deadline
            )
            connection = _connect(
                db_path,
                read_only=True,
                busy_timeout_seconds=preflight_busy,
            )
            try:
                row = _load_exact(
                    connection,
                    supervision_id=supervision_id,
                    campaign_id=campaign_id,
                    configuration_id=configuration_id,
                    run_id=run_id,
                    owner_id=owner_id,
                )
                planned_block = _renewal_contention_preflight(
                    row=row,
                    check_now=_renewal_now(),
                    renewal_deadline=renewal_deadline,
                )
                previous_heartbeat_iso = str(row["heartbeat_at"])
                previous_expiry_iso = str(row["lease_expires_at"])
                lock = Path(str(row["lease_lock_path"]))
            finally:
                connection.close()

            connection = _connect(db_path, busy_timeout_seconds=planned_block)
            try:
                _begin_immediate(
                    connection,
                    deadline_monotonic=renewal_deadline,
                    busy_timeout_ceiling=planned_block,
                    before_block=_renewal_block_preflight,
                )
                cursor = connection.execute(
                    """UPDATE printer_memory_factory_campaign_supervision
                       SET heartbeat_at=?,lease_expires_at=?,updated_at=?
                       WHERE supervision_id=? AND owner_id=?
                         AND supervision_state='ACTIVE'
                         AND heartbeat_at=? AND lease_expires_at=?""",
                    (
                        next_heartbeat, next_expiry_iso, next_heartbeat,
                        supervision_id, owner_id,
                        previous_heartbeat_iso, previous_expiry_iso,
                    ),
                )
                if cursor.rowcount != 1:
                    raise CampaignSupervisionError(
                        "lease ledger renewal was unconfirmed"
                    )
                connection.commit()
                db_ledger_advanced = True
                break
            except sqlite3.OperationalError as exc:
                connection.rollback()
                if not _is_sqlite_locked(exc):
                    raise
                if outer >= LEASE_CONTENTION_OUTER_MAX_ATTEMPTS:
                    raise
                remaining = renewal_deadline - time.monotonic()
                if LEASE_CONTENTION_OUTER_SLEEP_SECONDS > remaining:
                    raise sqlite3.OperationalError("database is locked")
                _renewal_block_preflight(LEASE_CONTENTION_OUTER_SLEEP_SECONDS)
                time.sleep(LEASE_CONTENTION_OUTER_SLEEP_SECONDS)
                continue
            except Exception:
                connection.rollback()
                raise
            finally:
                connection.close()
        else:
            raise sqlite3.OperationalError("database is locked")

        assert lock is not None
        remaining = renewal_deadline - time.monotonic()
        if remaining < LEASE_CONTENTION_MIN_BLOCK_SECONDS:
            raise CampaignSupervisionError(
                "Operational campaign lease renewal was not confirmed."
            )
        payload = _lock_payload(lock)
        _exact_lock(payload, row)
        payload.update({
            "heartbeat_at": next_heartbeat,
            "lease_expires_at": next_expiry_iso,
            "updated_at": next_heartbeat,
        })
        # Existing replace-attempt bound; no new SQLite waits on this path.
        lease_replace_attempts = _replace_lock(lock, payload, row)

        connection = _connect(db_path, read_only=True)
        try:
            durable = _load_exact(
                connection,
                supervision_id=supervision_id,
                campaign_id=campaign_id,
                configuration_id=configuration_id,
                run_id=run_id,
                owner_id=owner_id,
            )
            file_payload = _lock_payload(lock)
            _exact_lock(file_payload, durable)
            if (
                str(durable["heartbeat_at"]) != next_heartbeat
                or str(durable["lease_expires_at"]) != next_expiry_iso
                or file_payload.get("heartbeat_at") != next_heartbeat
                or file_payload.get("lease_expires_at") != next_expiry_iso
            ):
                raise CampaignSupervisionError(
                    "Operational campaign lease renewal was not confirmed."
                )
        finally:
            connection.close()
    except (CampaignSupervisionError, OSError, sqlite3.Error) as exc:
        return _failure_return(exc)

    return {
        "renewal_confirmed": True,
        "heartbeat_at": next_heartbeat,
        "lease_expires_at": next_expiry_iso,
        "lease_replace_attempts": lease_replace_attempts,
        "lease_replace_retries": max(0, lease_replace_attempts - 1),
        "terminal_cleanup_performed": False,
        "new_child_work_allowed": True,
        "db_ledger_advanced": True,
        "lease_file_synced": True,
        "contention_outer_attempts": contention_outer_attempts,
        "contention_wait_ms": int(max(0.0, (time.monotonic() - t0) * 1000.0)),
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
    scheduler_operation_observer: Callable[[Mapping[str, Any]], None] | None = None,
    lease_lock_path_override: str | Path | None = None,
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
    pre_admission_job_rowcount = 0
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
                cancelled_job_rows = connection.execute(
                    """SELECT id FROM printer_scheduler_jobs
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
                              OR locked_at IS NOT NULL OR lock_owner IS NOT NULL)
                       ORDER BY id""",
                    (campaign_id, run_id, campaign_id, run_id),
                ).fetchall()
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
                cancelled_job_rows = connection.execute(
                    """SELECT id FROM printer_scheduler_jobs
                       WHERE id IN (
                           SELECT scheduler_job_id
                           FROM printer_memory_factory_campaign_scheduler_work
                           WHERE campaign_id=? AND run_id=?
                             AND scheduler_job_id IS NOT NULL
                       ) AND (status IN ('PENDING','RUNNING','COOLDOWN')
                              OR locked_at IS NOT NULL OR lock_owner IS NOT NULL)
                       ORDER BY id""",
                    (campaign_id, run_id),
                ).fetchall()
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
            pre_admission_job_rowcount = 0
            if _table_exists(
                connection, "printer_pre_admission_discovery_attempts"
            ):
                pre_admission_job_rows = connection.execute(
                    """SELECT id FROM printer_scheduler_jobs
                       WHERE id IN (
                           SELECT scheduler_job_id
                           FROM printer_pre_admission_discovery_attempts
                           WHERE campaign_id=? AND campaign_run_id=?
                             AND scheduler_job_id IS NOT NULL
                       ) AND (status IN ('PENDING','RUNNING','COOLDOWN')
                              OR locked_at IS NOT NULL OR lock_owner IS NOT NULL)
                       ORDER BY id""",
                    (campaign_id, run_id),
                ).fetchall()
                pre_admission_job_cursor = connection.execute(
                    """UPDATE printer_scheduler_jobs
                       SET status='CANCELLED',finished_at=?,locked_at=NULL,
                           lock_owner=NULL,
                           last_error=COALESCE(last_error,?),updated_at=?
                       WHERE id IN (
                           SELECT scheduler_job_id
                           FROM printer_pre_admission_discovery_attempts
                           WHERE campaign_id=? AND campaign_run_id=?
                             AND scheduler_job_id IS NOT NULL
                       ) AND (status IN ('PENDING','RUNNING','COOLDOWN')
                              OR locked_at IS NOT NULL OR lock_owner IS NOT NULL)""",
                    (timestamp, cause, timestamp, campaign_id, run_id),
                )
                pre_admission_job_rowcount = int(pre_admission_job_cursor.rowcount)
                cancelled_job_rows = list(cancelled_job_rows) + list(
                    pre_admission_job_rows
                )
            if scheduler_operation_observer is not None:
                for cancelled_job in cancelled_job_rows:
                    scheduler_operation_observer(
                        {
                            "boundary": "SCHEDULER_TERMINAL",
                            "scheduler_job_id": int(cancelled_job["id"]),
                            "terminal_state": "CANCELLED",
                            "first_terminal_cause": cause,
                            "terminal_at": timestamp,
                            "operation_owner": "UNIFIED_TERMINAL_CLEANUP",
                        }
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
                if current is None:
                    raise CampaignSupervisionError("campaign terminal ownership is inconsistent")
                if str(current[state_column]).startswith("TERMINAL_"):
                    # Reconcile-then-cleanup may already have terminalized campaign/run
                    # with the same first cause while supervision remains ACTIVE.
                    if str(current["first_terminal_cause"] or "") != cause:
                        raise CampaignSupervisionError(
                            "campaign terminal ownership is inconsistent"
                        )
                    continue
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
            active_pre_admission = 0
            if _table_exists(
                connection, "printer_pre_admission_discovery_attempts"
            ):
                active_pre_admission = int(connection.execute(
                    """SELECT COUNT(*)
                       FROM printer_pre_admission_discovery_attempts AS attempt
                       JOIN printer_scheduler_jobs AS job
                         ON job.id=attempt.scheduler_job_id
                       WHERE attempt.campaign_id=? AND attempt.campaign_run_id=?
                         AND (job.status IN ('PENDING','RUNNING','COOLDOWN')
                              OR job.locked_at IS NOT NULL
                              OR job.lock_owner IS NOT NULL)""",
                    (campaign_id, run_id),
                ).fetchone()[0])
            if active_work or active_discovery or active_pre_admission:
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
        if _table_exists(connection, "printer_pre_admission_discovery_attempts"):
            active_after += int(connection.execute(
                """SELECT COUNT(*)
                   FROM printer_pre_admission_discovery_attempts AS attempt
                   JOIN printer_scheduler_jobs AS job
                     ON job.id=attempt.scheduler_job_id
                   WHERE attempt.campaign_id=? AND attempt.campaign_run_id=?
                     AND (job.status IN ('PENDING','RUNNING','COOLDOWN')
                          OR job.locked_at IS NOT NULL
                          OR job.lock_owner IS NOT NULL)""",
                (campaign_id, run_id),
            ).fetchone()[0])
    finally:
        connection.close()
    release_path = (
        Path(lease_lock_path_override).resolve()
        if lease_lock_path_override is not None
        else Path(terminal_row["lease_lock_path"]).resolve()
    )
    released = _release_lock(release_path, terminal_row)
    if not released:
        raise CampaignSupervisionError("operational campaign lease release failed")
    _finish_released_lease(db_path, terminal_row, released_at=timestamp)
    # Durable read-back of the exact persisted timestamps. Never trust the local
    # ``timestamp`` variable: the durable row owns the truth (COALESCE preserves a
    # prior idempotent release), and the accounting gate requires equality with
    # this exact supervision row.
    connection = _connect(db_path, read_only=True)
    try:
        durable_row = _load_exact(
            connection, supervision_id=supervision_id, campaign_id=campaign_id,
            configuration_id=configuration_id, run_id=run_id, owner_id=owner_id,
        )
        durable_cleanup_completed_at = durable_row["cleanup_completed_at"]
        durable_lease_released_at = durable_row["lease_released_at"]
    finally:
        connection.close()
    return {
        "supervision_id": supervision_id,
        "campaign_id": campaign_id,
        "configuration_id": configuration_id,
        "run_id": run_id,
        "owner_id": owner_id,
        "terminal_status": terminal_status,
        "first_terminal_cause": cause,
        "cleanup_completed_at": durable_cleanup_completed_at,
        "lease_released_at": durable_lease_released_at,
        "cancelled_campaign_work": 0 if replay else int(work_cursor.rowcount),
        "cancelled_discovery_work": 0 if replay else discovery_work_rowcount,
        "terminalized_discovery_batches": (
            0 if replay else discovery_batch_rowcount
        ),
        "cancelled_scheduler_jobs": (
            0
            if replay
            else int(job_cursor.rowcount) + int(pre_admission_job_rowcount)
        ),
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
