"""Durable one-shot ownership for discovery before proposed cycle 2 exists."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from enum import StrEnum
import json
import sqlite3
from typing import Sequence

from printer_v1.scheduler.contracts import JobKind, JobStatus, LockResult
from printer_v1.scheduler.scheduler import enqueue_job


class PreAdmissionAttemptError(ValueError):
    """Fail-closed pre-admission persistence contract violation."""


class PreAdmissionAttemptState(StrEnum):
    PLANNED = "PLANNED"
    RUNNING = "RUNNING"
    PAIR_READY = "PAIR_READY"
    NO_PAIR = "NO_PAIR"
    BLOCKED = "BLOCKED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"
    CONSUMED = "CONSUMED"


@dataclass(frozen=True)
class PreAdmissionDiscoveryAttempt:
    attempt_id: str
    campaign_id: str
    campaign_run_id: str
    configuration_id: str
    authoritative_factory_run_id: str
    proposed_cycle_ordinal: int
    proposed_cycle_id: str
    scheduler_job_id: int
    cycle_cutoff: datetime
    evaluated_at: datetime
    selection_seed_identity: str
    state: PreAdmissionAttemptState
    first_terminal_cause: str | None
    terminal_at: datetime | None
    consumed_cycle_id: str | None
    consumed_at: datetime | None


@dataclass(frozen=True)
class PreAdmissionAttemptItem:
    attempt_id: str
    slot_ordinal: int
    token_identity: str
    token_row_id: int
    mint_identity: str
    pair_identity: str
    pair_row_id: int
    lifecycle_identity: str
    canonical_market_identity: str
    canonical_pool_identity: str
    canonical_evidence_json: str
    canonical_evidence_hash: str
    evidence_version: str
    observed_at: datetime
    channel_labels: tuple[str, ...] = ()


def _required(value: object, label: str) -> str:
    if not isinstance(value, str) or not value or value != value.strip():
        raise PreAdmissionAttemptError(f"{label.upper()}_INVALID")
    return value


def _utc(value: datetime, label: str) -> datetime:
    if not isinstance(value, datetime) or value.tzinfo is None or value.utcoffset() is None:
        raise PreAdmissionAttemptError(f"{label.upper()}_MUST_BE_TIMEZONE_AWARE")
    return value.astimezone(timezone.utc)


def _timestamp(value: datetime, label: str) -> str:
    return _utc(value, label).isoformat()


def _parse_timestamp(value: object, label: str) -> datetime:
    try:
        parsed = datetime.fromisoformat(str(value))
    except (TypeError, ValueError) as exc:
        raise PreAdmissionAttemptError(f"{label.upper()}_MALFORMED") from exc
    return _utc(parsed, label)


def _optional_timestamp(value: object, label: str) -> datetime | None:
    return None if value is None else _parse_timestamp(value, label)


def _attempt_from_row(row: sqlite3.Row) -> PreAdmissionDiscoveryAttempt:
    return PreAdmissionDiscoveryAttempt(
        attempt_id=str(row["attempt_id"]),
        campaign_id=str(row["campaign_id"]),
        campaign_run_id=str(row["campaign_run_id"]),
        configuration_id=str(row["configuration_id"]),
        authoritative_factory_run_id=str(row["authoritative_factory_run_id"]),
        proposed_cycle_ordinal=int(row["proposed_cycle_ordinal"]),
        proposed_cycle_id=str(row["proposed_cycle_id"]),
        scheduler_job_id=int(row["scheduler_job_id"]),
        cycle_cutoff=_parse_timestamp(row["cycle_cutoff"], "cycle_cutoff"),
        evaluated_at=_parse_timestamp(row["evaluated_at"], "evaluated_at"),
        selection_seed_identity=str(row["selection_seed_identity"]),
        state=PreAdmissionAttemptState(str(row["attempt_state"])),
        first_terminal_cause=(
            None if row["first_terminal_cause"] is None else str(row["first_terminal_cause"])
        ),
        terminal_at=_optional_timestamp(row["terminal_at"], "terminal_at"),
        consumed_cycle_id=(
            None if row["consumed_cycle_id"] is None else str(row["consumed_cycle_id"])
        ),
        consumed_at=_optional_timestamp(row["consumed_at"], "consumed_at"),
    )


def load_pre_admission_attempt(
    connection: sqlite3.Connection, *, attempt_id: str
) -> PreAdmissionDiscoveryAttempt:
    connection.row_factory = sqlite3.Row
    exact_id = _required(attempt_id, "attempt_id")
    row = connection.execute(
        "SELECT * FROM printer_pre_admission_discovery_attempts WHERE attempt_id=?",
        (exact_id,),
    ).fetchone()
    if row is None:
        raise PreAdmissionAttemptError("ATTEMPT_NOT_FOUND")
    return _attempt_from_row(row)


def create_pre_admission_attempt(
    connection: sqlite3.Connection,
    *,
    attempt_id: str,
    campaign_id: str,
    campaign_run_id: str,
    configuration_id: str,
    authoritative_factory_run_id: str,
    proposed_cycle_ordinal: int,
    proposed_cycle_id: str,
    scheduler_job_id: int,
    cycle_cutoff: datetime,
    evaluated_at: datetime,
    selection_seed_identity: str,
    now: datetime,
) -> PreAdmissionDiscoveryAttempt:
    values = {
        "attempt_id": _required(attempt_id, "attempt_id"),
        "campaign_id": _required(campaign_id, "campaign_id"),
        "campaign_run_id": _required(campaign_run_id, "campaign_run_id"),
        "configuration_id": _required(configuration_id, "configuration_id"),
        "factory_run_id": _required(
            authoritative_factory_run_id, "authoritative_factory_run_id"
        ),
        "proposed_cycle_id": _required(proposed_cycle_id, "proposed_cycle_id"),
        "selection_seed": _required(selection_seed_identity, "selection_seed_identity"),
    }
    if type(proposed_cycle_ordinal) is not int or proposed_cycle_ordinal != 2:
        raise PreAdmissionAttemptError("PROPOSED_CYCLE_ORDINAL_INVALID")
    if type(scheduler_job_id) is not int or scheduler_job_id <= 0:
        raise PreAdmissionAttemptError("SCHEDULER_JOB_ID_INVALID")
    owner = connection.execute(
        """SELECT 1
           FROM printer_memory_factory_campaign_runs AS r
           JOIN printer_memory_factory_campaign_configurations AS c
             ON c.campaign_id=r.campaign_id AND c.configuration_id=?
           JOIN printer_memory_factory_runs AS f
             ON f.run_id=r.authoritative_run_id
           WHERE r.run_id=? AND r.campaign_id=? AND f.run_id=?""",
        (
            values["configuration_id"],
            values["campaign_run_id"],
            values["campaign_id"],
            values["factory_run_id"],
        ),
    ).fetchone()
    if owner is None:
        raise PreAdmissionAttemptError("OWNERSHIP_MISMATCH")
    scheduler = connection.execute(
        "SELECT job_kind FROM printer_scheduler_jobs WHERE id=?",
        (scheduler_job_id,),
    ).fetchone()
    if scheduler is None or str(scheduler[0]) != "PRE_ADMISSION_DISCOVERY_SELECTION":
        raise PreAdmissionAttemptError("SCHEDULER_OWNERSHIP_MISMATCH")
    created_at = _timestamp(now, "now")
    try:
        connection.execute(
            """INSERT INTO printer_pre_admission_discovery_attempts(
                   attempt_id,campaign_id,campaign_run_id,configuration_id,
                   authoritative_factory_run_id,proposed_cycle_ordinal,
                   proposed_cycle_id,scheduler_job_id,cycle_cutoff,evaluated_at,
                   selection_seed_identity,attempt_state,created_at,updated_at
               ) VALUES (?,?,?,?,?,?,?,?,?,?,?,'PLANNED',?,?)""",
            (
                values["attempt_id"], values["campaign_id"],
                values["campaign_run_id"], values["configuration_id"],
                values["factory_run_id"], proposed_cycle_ordinal,
                values["proposed_cycle_id"], scheduler_job_id,
                _timestamp(cycle_cutoff, "cycle_cutoff"),
                _timestamp(evaluated_at, "evaluated_at"),
                values["selection_seed"], created_at, created_at,
            ),
        )
    except sqlite3.IntegrityError as exc:
        message = str(exc)
        if "UNIQUE constraint failed" in message:
            raise PreAdmissionAttemptError("ATTEMPT_ALREADY_EXISTS") from exc
        raise PreAdmissionAttemptError("ATTEMPT_PERSISTENCE_FAILED") from exc
    return load_pre_admission_attempt(connection, attempt_id=values["attempt_id"])


def _transition(
    connection: sqlite3.Connection,
    *,
    attempt_id: str,
    expected: PreAdmissionAttemptState,
    target: PreAdmissionAttemptState,
    now: datetime,
    cause: str | None = None,
) -> PreAdmissionDiscoveryAttempt:
    instant = _timestamp(now, "now")
    terminal = target not in {PreAdmissionAttemptState.PLANNED, PreAdmissionAttemptState.RUNNING}
    cursor = connection.execute(
        """UPDATE printer_pre_admission_discovery_attempts
           SET attempt_state=?,first_terminal_cause=?,terminal_at=?,updated_at=?
           WHERE attempt_id=? AND attempt_state=?""",
        (
            target.value,
            _required(cause, "cause") if terminal else None,
            instant if terminal else None,
            instant,
            _required(attempt_id, "attempt_id"),
            expected.value,
        ),
    )
    if cursor.rowcount != 1:
        raise PreAdmissionAttemptError("INVALID_ATTEMPT_TRANSITION")
    return load_pre_admission_attempt(connection, attempt_id=attempt_id)


def mark_pre_admission_attempt_running(
    connection: sqlite3.Connection, *, attempt_id: str, now: datetime
) -> PreAdmissionDiscoveryAttempt:
    attempt = load_pre_admission_attempt(connection, attempt_id=attempt_id)
    job = connection.execute(
        "SELECT job_kind,status,lock_owner FROM printer_scheduler_jobs WHERE id=?",
        (attempt.scheduler_job_id,),
    ).fetchone()
    expected_owner = pre_admission_attempt_lock_owner(attempt.attempt_id)
    if (
        job is None
        or str(job["job_kind"]) != JobKind.PRE_ADMISSION_DISCOVERY_SELECTION.value
        or str(job["status"]) != JobStatus.RUNNING.value
        or str(job["lock_owner"] or "") != expected_owner
    ):
        raise PreAdmissionAttemptError("SCHEDULER_CLAIM_MISMATCH")
    return _transition(
        connection,
        attempt_id=attempt_id,
        expected=PreAdmissionAttemptState.PLANNED,
        target=PreAdmissionAttemptState.RUNNING,
        now=now,
    )


def pre_admission_attempt_lock_owner(attempt_id: str) -> str:
    return f"pre-admission-discovery:{_required(attempt_id, 'attempt_id')}"


def create_scheduled_pre_admission_attempt(
    connection: sqlite3.Connection,
    *,
    attempt_id: str,
    campaign_id: str,
    campaign_run_id: str,
    configuration_id: str,
    authoritative_factory_run_id: str,
    proposed_cycle_ordinal: int,
    proposed_cycle_id: str,
    cycle_cutoff: datetime,
    evaluated_at: datetime,
    selection_seed_identity: str,
    scheduled_for: datetime,
    now: datetime,
) -> PreAdmissionDiscoveryAttempt:
    """Atomically create the one exact Scheduler job and PLANNED attempt."""
    if connection.in_transaction:
        raise PreAdmissionAttemptError("OPEN_TRANSACTION_FORBIDDEN")
    exact_id = _required(attempt_id, "attempt_id")
    existing = connection.execute(
        """SELECT 1 FROM printer_pre_admission_discovery_attempts
           WHERE campaign_id=? AND campaign_run_id=?
             AND authoritative_factory_run_id=? AND proposed_cycle_ordinal=?""",
        (
            campaign_id, campaign_run_id, authoritative_factory_run_id,
            proposed_cycle_ordinal,
        ),
    ).fetchone()
    if existing is not None:
        raise PreAdmissionAttemptError("ATTEMPT_ALREADY_EXISTS")
    owner = connection.execute(
        """SELECT 1 FROM printer_memory_factory_campaign_runs AS r
           JOIN printer_memory_factory_campaign_configurations AS c
             ON c.campaign_id=r.campaign_id AND c.configuration_id=?
           WHERE r.run_id=? AND r.campaign_id=? AND r.authoritative_run_id=?""",
        (
            configuration_id, campaign_run_id, campaign_id,
            authoritative_factory_run_id,
        ),
    ).fetchone()
    if owner is None:
        raise PreAdmissionAttemptError("OWNERSHIP_MISMATCH")
    connection.execute("BEGIN IMMEDIATE")
    try:
        result, scheduler_job_id = enqueue_job(
            connection,
            job_name=f"pre-admission-discovery-selection:{exact_id}",
            job_kind=JobKind.PRE_ADMISSION_DISCOVERY_SELECTION,
            target_table="printer_pre_admission_discovery_attempts",
            target_id=None,
            scheduled_for=_utc(scheduled_for, "scheduled_for"),
        )
        if result is not LockResult.ACQUIRED or scheduler_job_id is None:
            raise PreAdmissionAttemptError("SCHEDULER_OWNERSHIP_CREATE_FAILED")
        attempt = create_pre_admission_attempt(
            connection,
            attempt_id=exact_id,
            campaign_id=campaign_id,
            campaign_run_id=campaign_run_id,
            configuration_id=configuration_id,
            authoritative_factory_run_id=authoritative_factory_run_id,
            proposed_cycle_ordinal=proposed_cycle_ordinal,
            proposed_cycle_id=proposed_cycle_id,
            scheduler_job_id=scheduler_job_id,
            cycle_cutoff=cycle_cutoff,
            evaluated_at=evaluated_at,
            selection_seed_identity=selection_seed_identity,
            now=now,
        )
        connection.commit()
        return attempt
    except Exception:
        connection.rollback()
        raise


def terminalize_pre_admission_attempt(
    connection: sqlite3.Connection,
    *,
    attempt_id: str,
    state: PreAdmissionAttemptState,
    cause: str,
    now: datetime,
) -> PreAdmissionDiscoveryAttempt:
    try:
        target = PreAdmissionAttemptState(state)
    except ValueError as exc:
        raise PreAdmissionAttemptError("TERMINAL_STATE_INVALID") from exc
    if target not in {
        PreAdmissionAttemptState.NO_PAIR,
        PreAdmissionAttemptState.BLOCKED,
        PreAdmissionAttemptState.FAILED,
        PreAdmissionAttemptState.CANCELLED,
    }:
        raise PreAdmissionAttemptError("TERMINAL_STATE_INVALID")
    current = load_pre_admission_attempt(connection, attempt_id=attempt_id)
    allowed_from = {
        PreAdmissionAttemptState.NO_PAIR: {PreAdmissionAttemptState.RUNNING},
        PreAdmissionAttemptState.FAILED: {PreAdmissionAttemptState.RUNNING},
        PreAdmissionAttemptState.BLOCKED: {
            PreAdmissionAttemptState.PLANNED,
            PreAdmissionAttemptState.RUNNING,
        },
        PreAdmissionAttemptState.CANCELLED: {
            PreAdmissionAttemptState.PLANNED,
            PreAdmissionAttemptState.RUNNING,
        },
    }[target]
    if current.state not in allowed_from:
        raise PreAdmissionAttemptError("INVALID_ATTEMPT_TRANSITION")
    return _transition(
        connection,
        attempt_id=attempt_id,
        expected=current.state,
        target=target,
        cause=cause,
        now=now,
    )


def _validate_pair(attempt_id: str, items: Sequence[PreAdmissionAttemptItem]) -> tuple[PreAdmissionAttemptItem, PreAdmissionAttemptItem]:
    if len(items) != 2:
        raise PreAdmissionAttemptError("EXACT_TWO_ITEMS_REQUIRED")
    ordered = tuple(sorted(items, key=lambda item: item.slot_ordinal))
    if tuple(item.slot_ordinal for item in ordered) != (1, 2):
        raise PreAdmissionAttemptError("EXACT_TWO_ITEMS_REQUIRED")
    if any(item.attempt_id != attempt_id for item in ordered):
        raise PreAdmissionAttemptError("ITEM_ATTEMPT_ID_MISMATCH")
    distinct_fields = (
        "token_identity", "token_row_id", "mint_identity", "pair_identity",
        "pair_row_id", "canonical_market_identity", "canonical_pool_identity",
    )
    if any(len({getattr(item, field) for item in ordered}) != 2 for field in distinct_fields):
        raise PreAdmissionAttemptError("PAIR_IDENTITIES_NOT_DISTINCT")
    for item in ordered:
        labels = tuple(sorted(set(item.channel_labels)))
        if not labels or any(
            not isinstance(label, str) or not label or label != label.strip()
            for label in labels
        ):
            raise PreAdmissionAttemptError("CHANNEL_LABELS_INVALID")
    return ordered  # type: ignore[return-value]


def persist_pre_admission_pair(
    connection: sqlite3.Connection,
    *,
    attempt_id: str,
    items: Sequence[PreAdmissionAttemptItem],
    now: datetime,
) -> PreAdmissionDiscoveryAttempt:
    exact_id = _required(attempt_id, "attempt_id")
    ordered = _validate_pair(exact_id, items)
    if load_pre_admission_attempt(connection, attempt_id=exact_id).state is not PreAdmissionAttemptState.RUNNING:
        raise PreAdmissionAttemptError("INVALID_ATTEMPT_TRANSITION")
    instant = _timestamp(now, "now")
    connection.execute("SAVEPOINT persist_pre_admission_pair")
    try:
        for item in ordered:
            connection.execute(
                """INSERT INTO printer_pre_admission_discovery_attempt_items(
                       attempt_id,slot_ordinal,token_identity,token_row_id,mint_identity,
                       pair_identity,pair_row_id,lifecycle_identity,
                       canonical_market_identity,canonical_pool_identity,channel_labels_json,
                       canonical_evidence_json,canonical_evidence_hash,evidence_version,
                       observed_at,created_at
                   ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (
                    exact_id, item.slot_ordinal, _required(item.token_identity, "token_identity"),
                    item.token_row_id, _required(item.mint_identity, "mint_identity"),
                    _required(item.pair_identity, "pair_identity"), item.pair_row_id,
                    _required(item.lifecycle_identity, "lifecycle_identity"),
                    _required(item.canonical_market_identity, "canonical_market_identity"),
                    _required(item.canonical_pool_identity, "canonical_pool_identity"),
                    json.dumps(sorted(set(item.channel_labels)), separators=(",", ":")),
                    _required(item.canonical_evidence_json, "canonical_evidence_json"),
                    _required(item.canonical_evidence_hash, "canonical_evidence_hash"),
                    _required(item.evidence_version, "evidence_version"),
                    _timestamp(item.observed_at, "observed_at"), instant,
                ),
            )
        result = _transition(
            connection,
            attempt_id=exact_id,
            expected=PreAdmissionAttemptState.RUNNING,
            target=PreAdmissionAttemptState.PAIR_READY,
            cause="EXACT_PAIR_FROZEN",
            now=now,
        )
        connection.execute("RELEASE SAVEPOINT persist_pre_admission_pair")
        return result
    except (sqlite3.Error, PreAdmissionAttemptError) as exc:
        connection.execute("ROLLBACK TO SAVEPOINT persist_pre_admission_pair")
        connection.execute("RELEASE SAVEPOINT persist_pre_admission_pair")
        if isinstance(exc, PreAdmissionAttemptError):
            raise
        raise PreAdmissionAttemptError("PAIR_PERSISTENCE_FAILED") from exc


def load_pre_admission_pair(
    connection: sqlite3.Connection, *, attempt_id: str
) -> tuple[PreAdmissionAttemptItem, PreAdmissionAttemptItem]:
    attempt = load_pre_admission_attempt(connection, attempt_id=attempt_id)
    if attempt.state not in {
        PreAdmissionAttemptState.PAIR_READY, PreAdmissionAttemptState.CONSUMED
    }:
        raise PreAdmissionAttemptError("PAIR_NOT_READY")
    rows = connection.execute(
        """SELECT * FROM printer_pre_admission_discovery_attempt_items
           WHERE attempt_id=? ORDER BY slot_ordinal""",
        (attempt_id,),
    ).fetchall()
    if len(rows) != 2 or tuple(int(row["slot_ordinal"]) for row in rows) != (1, 2):
        raise PreAdmissionAttemptError("EXACT_TWO_ITEMS_REQUIRED")
    result = tuple(
        PreAdmissionAttemptItem(
            attempt_id=str(row["attempt_id"]), slot_ordinal=int(row["slot_ordinal"]),
            token_identity=str(row["token_identity"]), token_row_id=int(row["token_row_id"]),
            mint_identity=str(row["mint_identity"]), pair_identity=str(row["pair_identity"]),
            pair_row_id=int(row["pair_row_id"]), lifecycle_identity=str(row["lifecycle_identity"]),
            canonical_market_identity=str(row["canonical_market_identity"]),
            canonical_pool_identity=str(row["canonical_pool_identity"]),
            canonical_evidence_json=str(row["canonical_evidence_json"]),
            canonical_evidence_hash=str(row["canonical_evidence_hash"]),
            evidence_version=str(row["evidence_version"]),
            observed_at=_parse_timestamp(row["observed_at"], "observed_at"),
            channel_labels=tuple(json.loads(str(row["channel_labels_json"]))),
        )
        for row in rows
    )
    return result  # type: ignore[return-value]


def link_pre_admission_source_evidence(
    connection: sqlite3.Connection,
    *,
    attempt_id: str,
    link_ordinal: int,
    logical_stage: str,
    source_request_id: int,
    source_response_id: int | None = None,
    source_failure_id: int | None = None,
    now: datetime,
) -> None:
    if source_response_id is not None and source_failure_id is not None:
        raise PreAdmissionAttemptError("AMBIGUOUS_SOURCE_EVIDENCE")
    if type(link_ordinal) is not int or link_ordinal <= 0:
        raise PreAdmissionAttemptError("LINK_ORDINAL_INVALID")
    if type(source_request_id) is not int or source_request_id <= 0:
        raise PreAdmissionAttemptError("SOURCE_REQUEST_ID_INVALID")
    try:
        connection.execute(
            """INSERT INTO printer_pre_admission_discovery_attempt_source_links(
                   attempt_id,link_ordinal,logical_stage,source_request_id,
                   source_response_id,source_failure_id,created_at
               ) VALUES (?,?,?,?,?,?,?)""",
            (
                _required(attempt_id, "attempt_id"), link_ordinal,
                _required(logical_stage, "logical_stage"), source_request_id,
                source_response_id, source_failure_id, _timestamp(now, "now"),
            ),
        )
    except sqlite3.IntegrityError as exc:
        raise PreAdmissionAttemptError("SOURCE_EVIDENCE_LINK_INVALID") from exc


__all__ = [
    "PreAdmissionAttemptError", "PreAdmissionAttemptItem",
    "PreAdmissionAttemptState", "PreAdmissionDiscoveryAttempt",
    "create_pre_admission_attempt", "create_scheduled_pre_admission_attempt",
    "link_pre_admission_source_evidence",
    "load_pre_admission_attempt", "load_pre_admission_pair",
    "mark_pre_admission_attempt_running", "persist_pre_admission_pair",
    "pre_admission_attempt_lock_owner", "terminalize_pre_admission_attempt",
]
