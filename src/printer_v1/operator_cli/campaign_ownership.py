"""Transactional campaign ownership graph persistence for V2-9.7D.6B.1."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import json
import sqlite3
from typing import Any, Mapping, Sequence

from printer_v1.operator_cli.campaign_identity_state import (
    ALLOWED_CAMPAIGN_TRANSITIONS,
)


class CampaignOwnershipError(ValueError):
    """Raised when ownership or state evidence fails closed."""


@dataclass(frozen=True)
class StateTransitionResult:
    identity: str
    previous_state: str
    current_state: str
    first_terminal_cause: str | None
    terminal_at: str | None
    changed: bool


_RUN_TRANSITIONS = {
    state: set(targets)
    for state, targets in ALLOWED_CAMPAIGN_TRANSITIONS.items()
}
_CYCLE_SEQUENCE = (
    "PLANNED", "DISCOVERING", "SELECTING", "TRACKING", "CLOSING",
    "AUDITING", "ROTATING",
)
_CYCLE_TRANSITIONS = {
    state: ({_CYCLE_SEQUENCE[index + 1]} if index + 1 < len(_CYCLE_SEQUENCE) else set())
    for index, state in enumerate(_CYCLE_SEQUENCE)
}
_TOKEN_TRANSITIONS = {
    "SELECTED": {"WINDOW_15M_ACTIVE"},
    "WINDOW_15M_ACTIVE": {"WINDOW_15M_CLOSED"},
    "WINDOW_15M_CLOSED": {"WINDOW_1H_CONTINUING"},
    "WINDOW_1H_CONTINUING": {"WINDOW_1H_CLOSED"},
    "WINDOW_1H_CLOSED": {"WINDOW_4H_CONTINUING"},
    "WINDOW_4H_CONTINUING": {"WINDOW_4H_CLOSED"},
    "WINDOW_4H_CLOSED": set(),
}
_WINDOW_TRANSITIONS = {
    "PLANNED": {"COLLECTING"},
    "COLLECTING": {"CLOSE_PENDING"},
    "CLOSE_PENDING": {"AUDITING"},
    "AUDITING": set(),
}
_WORK_TRANSITIONS = {
    "PENDING": {"RUNNING", "COOLDOWN"},
    "RUNNING": {"COOLDOWN"},
    "COOLDOWN": {"PENDING", "RUNNING"},
}

_STATE_TABLES = {
    "campaign": (
        "printer_memory_factory_campaigns", "campaign_id", "campaign_state",
        _RUN_TRANSITIONS,
        {"TERMINAL_COMPLETED", "TERMINAL_STOPPED", "TERMINAL_BLOCKED", "TERMINAL_FAILED"},
    ),
    "run": (
        "printer_memory_factory_campaign_runs", "run_id", "run_state",
        _RUN_TRANSITIONS,
        {"TERMINAL_COMPLETED", "TERMINAL_STOPPED", "TERMINAL_BLOCKED", "TERMINAL_FAILED"},
    ),
    "cycle": (
        "printer_memory_factory_campaign_cycles", "cycle_id", "cycle_state",
        _CYCLE_TRANSITIONS,
        {"TERMINAL_COMPLETED", "TERMINAL_STOPPED", "TERMINAL_BLOCKED", "TERMINAL_FAILED"},
    ),
    "token_slot": (
        "printer_memory_factory_campaign_token_slots", "token_slot_id", "token_state",
        _TOKEN_TRANSITIONS, {"COOLDOWN", "ARCHIVED", "MANUAL_REVIEW", "FAILED"},
    ),
    "window": (
        "printer_memory_factory_campaign_windows", "window_id", "window_state",
        _WINDOW_TRANSITIONS,
        {"CLEAN_PROMOTED", "DIRTY", "BLOCKED", "NO_PROMOTION", "ALREADY_EXISTS_IDEMPOTENT", "CANCELLED"},
    ),
    "scheduler_work": (
        "printer_memory_factory_campaign_scheduler_work", "scheduler_work_id", "work_state",
        _WORK_TRANSITIONS, {"SUCCEEDED", "FAILED", "SKIPPED", "CANCELLED"},
    ),
}


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _required(value: object, label: str) -> str:
    text = str(value).strip()
    if not text:
        raise CampaignOwnershipError(f"{label} is required")
    return text


def _write(connection: sqlite3.Connection, sql: str, values: Sequence[object]) -> None:
    try:
        connection.execute(sql, tuple(values))
    except sqlite3.Error as exc:
        raise CampaignOwnershipError(str(exc)) from exc


def create_campaign_run(
    connection: sqlite3.Connection,
    *,
    campaign_id: str,
    run_id: str,
    run_ordinal: int,
    authoritative_run_id: str | None = None,
    proof_supervision_id: int | None = None,
    now: str | None = None,
) -> None:
    timestamp = now or _utc_now()
    with connection:
        _write(
            connection,
            """INSERT INTO printer_memory_factory_campaign_runs(
                run_id,campaign_id,run_ordinal,run_state,authoritative_run_id,
                proof_supervision_id,created_at,updated_at
            ) VALUES (?,?,?,'DRAFT',?,?,?,?)""",
            (_required(run_id, "run_id"), _required(campaign_id, "campaign_id"),
             run_ordinal, authoritative_run_id, proof_supervision_id, timestamp, timestamp),
        )


def bind_authoritative_run_id(
    connection: sqlite3.Connection,
    *,
    campaign_run_id: str,
    factory_run_id: str,
    now: str | None = None,
) -> StateTransitionResult:
    """One-shot bind of campaign run → factory run (NULL → value only)."""
    timestamp = now or _utc_now()
    campaign_run = _required(campaign_run_id, "campaign_run_id")
    factory_run = _required(factory_run_id, "factory_run_id")
    try:
        with connection:
            row = connection.execute(
                """SELECT authoritative_run_id, run_state
                   FROM printer_memory_factory_campaign_runs WHERE run_id=?""",
                (campaign_run,),
            ).fetchone()
            if row is None:
                raise CampaignOwnershipError(
                    f"unknown campaign run identity: {campaign_run}"
                )
            current = row[0]
            if current is not None:
                if str(current) == factory_run:
                    return StateTransitionResult(
                        campaign_run, str(row[1]), str(row[1]), None, None, False
                    )
                raise CampaignOwnershipError(
                    "authoritative_run_id already bound to a different factory run"
                )
            factory = connection.execute(
                "SELECT run_id FROM printer_memory_factory_runs WHERE run_id=?",
                (factory_run,),
            ).fetchone()
            if factory is None:
                raise CampaignOwnershipError(
                    f"factory run missing for authoritative bind: {factory_run}"
                )
            cursor = connection.execute(
                """UPDATE printer_memory_factory_campaign_runs
                   SET authoritative_run_id=?, updated_at=?
                   WHERE run_id=? AND authoritative_run_id IS NULL""",
                (factory_run, timestamp, campaign_run),
            )
            if cursor.rowcount != 1:
                raise CampaignOwnershipError(
                    "authoritative_run_id bind failed compare-and-update"
                )
            return StateTransitionResult(
                campaign_run, str(row[1]), str(row[1]), None, None, True
            )
    except sqlite3.Error as exc:
        raise CampaignOwnershipError(str(exc)) from exc


def bind_window_memory_row_id(
    connection: sqlite3.Connection,
    *,
    window_id: str,
    memory_window_row_id: int,
    now: str | None = None,
) -> bool:
    """One-shot bind of campaign window → printer_memory_windows row."""
    timestamp = now or _utc_now()
    identity = _required(window_id, "window_id")
    row_id = int(memory_window_row_id)
    try:
        with connection:
            row = connection.execute(
                """SELECT memory_window_row_id, window_kind, token_row_id, pair_row_id
                   FROM printer_memory_factory_campaign_windows WHERE window_id=?""",
                (identity,),
            ).fetchone()
            if row is None:
                raise CampaignOwnershipError(f"unknown campaign window: {identity}")
            current = row[0]
            if current is not None:
                if int(current) == row_id:
                    return False
                raise CampaignOwnershipError(
                    "memory_window_row_id already bound to a different row"
                )
            memory = connection.execute(
                """SELECT id, token_id, pair_id, window_kind
                   FROM printer_memory_windows WHERE id=?""",
                (row_id,),
            ).fetchone()
            if memory is None:
                raise CampaignOwnershipError(
                    f"memory window missing for bind: {row_id}"
                )
            if (
                int(memory[1]) != int(row[2])
                or int(memory[2]) != int(row[3])
                or str(memory[3]) != str(row[1])
            ):
                raise CampaignOwnershipError(
                    "memory window identity mismatch on bind"
                )
            cursor = connection.execute(
                """UPDATE printer_memory_factory_campaign_windows
                   SET memory_window_row_id=?, updated_at=?
                   WHERE window_id=? AND memory_window_row_id IS NULL""",
                (row_id, timestamp, identity),
            )
            if cursor.rowcount != 1:
                raise CampaignOwnershipError(
                    "memory_window_row_id bind failed compare-and-update"
                )
            return True
    except sqlite3.Error as exc:
        raise CampaignOwnershipError(str(exc)) from exc


def create_cycle_with_two_slots(
    connection: sqlite3.Connection,
    *,
    campaign_id: str,
    run_id: str,
    cycle_id: str,
    cycle_ordinal: int,
    slots: Sequence[Mapping[str, Any]],
    now: str | None = None,
) -> None:
    if len(slots) != 2:
        raise CampaignOwnershipError("a cycle requires exactly two token slots")
    if {int(slot.get("slot_ordinal", 0)) for slot in slots} != {1, 2}:
        raise CampaignOwnershipError("token slot ordinals must be exactly 1 and 2")
    timestamp = now or _utc_now()
    try:
        with connection:
            connection.execute(
                """INSERT INTO printer_memory_factory_campaign_cycles(
                    cycle_id,campaign_id,run_id,cycle_ordinal,cycle_state,
                    created_at,updated_at
                ) VALUES (?,?,?,?,'PLANNED',?,?)""",
                (cycle_id, campaign_id, run_id, cycle_ordinal, timestamp, timestamp),
            )
            for slot in slots:
                connection.execute(
                    """INSERT INTO printer_memory_factory_campaign_token_slots(
                        token_slot_id,campaign_id,run_id,cycle_id,slot_ordinal,
                        token_identity,token_row_id,mint_identity,pair_identity,
                        pair_row_id,lifecycle_identity,tracking_queue_id,
                        replacement_predecessor_slot_id,token_state,created_at,updated_at
                    ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,'SELECTED',?,?)""",
                    (
                        _required(slot.get("token_slot_id"), "token_slot_id"),
                        campaign_id, run_id, cycle_id, int(slot["slot_ordinal"]),
                        _required(slot.get("token_identity"), "token_identity"),
                        int(slot["token_row_id"]),
                        _required(slot.get("mint_identity"), "mint_identity"),
                        _required(slot.get("pair_identity"), "pair_identity"),
                        int(slot["pair_row_id"]),
                        _required(slot.get("lifecycle_identity"), "lifecycle_identity"),
                        slot.get("tracking_queue_id"),
                        slot.get("replacement_predecessor_slot_id"), timestamp, timestamp,
                    ),
                )
    except (KeyError, TypeError, ValueError, sqlite3.Error) as exc:
        raise CampaignOwnershipError(str(exc)) from exc


def persist_window(
    connection: sqlite3.Connection,
    *,
    window_id: str,
    campaign_id: str,
    run_id: str,
    cycle_id: str,
    token_slot_id: str,
    token_row_id: int,
    pair_row_id: int,
    window_kind: str,
    root_15m_lifecycle_identity: str,
    checkpoint_cutoff: str,
    predecessor_window_id: str | None = None,
    containing_main_window_id: str | None = None,
    memory_window_row_id: int | None = None,
    now: str | None = None,
) -> None:
    timestamp = now or _utc_now()
    support_only = int(window_kind == "WINDOW_5M_MICRO_EVENT")
    with connection:
        _write(
            connection,
            """INSERT INTO printer_memory_factory_campaign_windows(
                window_id,campaign_id,run_id,cycle_id,token_slot_id,token_row_id,
                pair_row_id,window_kind,window_state,root_15m_lifecycle_identity,
                predecessor_window_id,containing_main_window_id,memory_window_row_id,
                checkpoint_cutoff,support_only,created_at,updated_at
            ) VALUES (?,?,?,?,?,?,?,?,'PLANNED',?,?,?,?,?,?,?,?)""",
            (window_id,campaign_id,run_id,cycle_id,token_slot_id,token_row_id,pair_row_id,
             window_kind,root_15m_lifecycle_identity,predecessor_window_id,
             containing_main_window_id,memory_window_row_id,checkpoint_cutoff,
             support_only,timestamp,timestamp),
        )


def persist_scheduler_work(
    connection: sqlite3.Connection,
    *,
    scheduler_work_id: str,
    campaign_id: str,
    run_id: str,
    cycle_id: str,
    token_slot_id: str,
    window_id: str,
    work_intent: str,
    deadline_at: str,
    scheduler_job_id: int | None = None,
    source_request_id: int | None = None,
    source_response_id: int | None = None,
    source_failure_id: int | None = None,
    now: str | None = None,
) -> None:
    timestamp = now or _utc_now()
    with connection:
        _write(
            connection,
            """INSERT INTO printer_memory_factory_campaign_scheduler_work(
                scheduler_work_id,campaign_id,run_id,cycle_id,token_slot_id,
                window_id,work_intent,deadline_at,work_state,scheduler_job_id,
                source_request_id,source_response_id,source_failure_id,
                created_at,updated_at
            ) VALUES (?,?,?,?,?,?,?,?,'PENDING',?,?,?,?,?,?)""",
            (scheduler_work_id,campaign_id,run_id,cycle_id,token_slot_id,window_id,
             work_intent,deadline_at,scheduler_job_id,source_request_id,
             source_response_id,source_failure_id,timestamp,timestamp),
        )


_TERMINAL_WINDOW_STATES = frozenset(
    {"CLEAN_PROMOTED", "DIRTY", "BLOCKED", "NO_PROMOTION",
     "ALREADY_EXISTS_IDEMPOTENT", "CANCELLED"}
)
_TERMINAL_WORK_STATES = frozenset({"SUCCEEDED", "FAILED", "SKIPPED", "CANCELLED"})

CAMPAIGN_WINDOW_OWNERSHIP_CONFLICT = "CAMPAIGN_WINDOW_OWNERSHIP_CONFLICT"
CAMPAIGN_SCHEDULER_WORK_OWNERSHIP_CONFLICT = (
    "CAMPAIGN_SCHEDULER_WORK_OWNERSHIP_CONFLICT"
)


def register_campaign_window_close(
    connection: sqlite3.Connection,
    *,
    campaign_id: str,
    run_id: str,
    cycle_id: str,
    factory_run_id: str,
    token_slot_id: str,
    window_id: str,
    close_step_id: int,
    memory_window_row_id: int,
    root_15m_lifecycle_identity: str,
    checkpoint_cutoff: str,
    terminal_window_state: str,
    terminal_cause: str,
    window_kind: str = "WINDOW_15M",
    now: str | None = None,
) -> dict[str, Any]:
    """Register one real closed factory window under exact campaign ownership.

    Runs as one atomic transaction: it verifies the succeeded ``WINDOW_CLOSE``
    step belongs to the immutable ownership context, sets the memory window's
    exact ``cycle_id``, inserts the ``printer_memory_factory_campaign_windows``
    ownership row (idempotent on the exact identity tuple), binds the memory row,
    terminalizes the ownership row, and read-back verifies before returning. It
    reuses the existing ownership table — no parallel window map is created.

    Fails closed with ``CAMPAIGN_WINDOW_OWNERSHIP_CONFLICT`` on a competing
    campaign/run/cycle owner, a token/pair mismatch, a blank/mismatched cycle in a
    new run, or a close step outside the ownership context.
    """
    timestamp = now or _utc_now()
    campaign = _required(campaign_id, "campaign_id")
    run = _required(run_id, "run_id")
    cycle = _required(cycle_id, "cycle_id")
    factory_run = _required(factory_run_id, "factory_run_id")
    slot = _required(token_slot_id, "token_slot_id")
    window = _required(window_id, "window_id")
    lifecycle_identity = _required(
        root_15m_lifecycle_identity, "root_15m_lifecycle_identity"
    )
    cutoff = _required(checkpoint_cutoff, "checkpoint_cutoff")
    terminal_state = _required(terminal_window_state, "terminal_window_state")
    cause = _required(terminal_cause, "terminal_cause")
    row_id = int(memory_window_row_id)
    if terminal_state not in _TERMINAL_WINDOW_STATES:
        raise CampaignOwnershipError(
            f"invalid terminal window state: {terminal_state}"
        )
    try:
        with connection:
            step = connection.execute(
                """SELECT run_id, step_kind, step_status, token_id, pair_id,
                          memory_window_id, scheduler_job_id
                   FROM printer_memory_factory_run_steps WHERE id=?""",
                (int(close_step_id),),
            ).fetchone()
            if step is None:
                raise CampaignOwnershipError(
                    f"unknown close step identity: {close_step_id}"
                )
            step_run, step_kind, step_status, step_token, step_pair, step_window, _ = (
                step
            )
            if str(step_kind) != "WINDOW_CLOSE":
                raise CampaignOwnershipError(
                    f"{CAMPAIGN_WINDOW_OWNERSHIP_CONFLICT}:step is not WINDOW_CLOSE"
                )
            if str(step_status) != "SUCCEEDED":
                raise CampaignOwnershipError(
                    f"{CAMPAIGN_WINDOW_OWNERSHIP_CONFLICT}:close step not succeeded"
                )
            if str(step_run) != factory_run:
                raise CampaignOwnershipError(
                    f"{CAMPAIGN_WINDOW_OWNERSHIP_CONFLICT}:close step outside factory run"
                )
            if step_window is None or int(step_window) != row_id:
                raise CampaignOwnershipError(
                    f"{CAMPAIGN_WINDOW_OWNERSHIP_CONFLICT}:close step window mismatch"
                )

            campaign_run = connection.execute(
                """SELECT authoritative_run_id FROM printer_memory_factory_campaign_runs
                   WHERE run_id=? AND campaign_id=?""",
                (run, campaign),
            ).fetchone()
            if campaign_run is None:
                raise CampaignOwnershipError(f"unknown campaign run identity: {run}")
            if campaign_run[0] is None or str(campaign_run[0]) != factory_run:
                raise CampaignOwnershipError(
                    f"{CAMPAIGN_WINDOW_OWNERSHIP_CONFLICT}:factory run not bound to campaign run"
                )

            memory = connection.execute(
                """SELECT token_id, pair_id, window_kind, cycle_id
                   FROM printer_memory_windows WHERE id=?""",
                (row_id,),
            ).fetchone()
            if memory is None:
                raise CampaignOwnershipError(
                    f"memory window missing for registration: {row_id}"
                )
            mem_token, mem_pair, mem_kind, mem_cycle = memory
            if (
                int(mem_token) != int(step_token)
                or int(mem_pair) != int(step_pair)
                or str(mem_kind) != window_kind
            ):
                raise CampaignOwnershipError(
                    f"{CAMPAIGN_WINDOW_OWNERSHIP_CONFLICT}:memory window identity mismatch"
                )
            if mem_cycle is not None and str(mem_cycle).strip():
                if str(mem_cycle) != cycle:
                    raise CampaignOwnershipError(
                        f"{CAMPAIGN_WINDOW_OWNERSHIP_CONFLICT}:cycle already bound to another cycle"
                    )

            slot_row = connection.execute(
                """SELECT campaign_id, run_id, cycle_id, token_row_id, pair_row_id
                   FROM printer_memory_factory_campaign_token_slots
                   WHERE token_slot_id=?""",
                (slot,),
            ).fetchone()
            if slot_row is None:
                raise CampaignOwnershipError(f"unknown token slot identity: {slot}")
            if (
                str(slot_row[0]) != campaign
                or str(slot_row[1]) != run
                or str(slot_row[2]) != cycle
            ):
                raise CampaignOwnershipError(
                    f"{CAMPAIGN_WINDOW_OWNERSHIP_CONFLICT}:token slot outside ownership context"
                )
            token_row_id = int(slot_row[3])
            pair_row_id = int(slot_row[4])
            if token_row_id != int(step_token) or pair_row_id != int(step_pair):
                raise CampaignOwnershipError(
                    f"{CAMPAIGN_WINDOW_OWNERSHIP_CONFLICT}:slot token/pair mismatch"
                )

            existing = connection.execute(
                """SELECT campaign_id, run_id, cycle_id, token_slot_id, token_row_id,
                          pair_row_id, window_kind, memory_window_row_id, window_state
                   FROM printer_memory_factory_campaign_windows WHERE window_id=?""",
                (window,),
            ).fetchone()
            if existing is not None:
                same = (
                    str(existing[0]) == campaign
                    and str(existing[1]) == run
                    and str(existing[2]) == cycle
                    and str(existing[3]) == slot
                    and int(existing[4]) == token_row_id
                    and int(existing[5]) == pair_row_id
                    and str(existing[6]) == window_kind
                    and existing[7] is not None
                    and int(existing[7]) == row_id
                )
                if not same:
                    raise CampaignOwnershipError(
                        f"{CAMPAIGN_WINDOW_OWNERSHIP_CONFLICT}:window already owned differently"
                    )
                # Ensure the memory window cycle is bound even on idempotent replay.
                if mem_cycle is None or not str(mem_cycle).strip():
                    connection.execute(
                        "UPDATE printer_memory_windows SET cycle_id=?, updated_at=? WHERE id=?",
                        (cycle, timestamp, row_id),
                    )
                return {
                    "registered": False,
                    "idempotent": True,
                    "window_id": window,
                    "cycle_id": cycle,
                    "window_state": str(existing[8]),
                    "memory_window_row_id": row_id,
                }

            # New registration: bind memory cycle, insert PLANNED, terminalize.
            connection.execute(
                "UPDATE printer_memory_windows SET cycle_id=?, updated_at=? WHERE id=?",
                (cycle, timestamp, row_id),
            )
            connection.execute(
                """INSERT INTO printer_memory_factory_campaign_windows(
                    window_id,campaign_id,run_id,cycle_id,token_slot_id,token_row_id,
                    pair_row_id,window_kind,window_state,root_15m_lifecycle_identity,
                    predecessor_window_id,containing_main_window_id,memory_window_row_id,
                    checkpoint_cutoff,support_only,created_at,updated_at
                ) VALUES (?,?,?,?,?,?,?,?,'PLANNED',?,NULL,NULL,?,?,0,?,?)""",
                (window, campaign, run, cycle, slot, token_row_id, pair_row_id,
                 window_kind, lifecycle_identity, row_id, cutoff, timestamp, timestamp),
            )
            cursor = connection.execute(
                """UPDATE printer_memory_factory_campaign_windows
                   SET window_state=?, first_terminal_cause=?, terminal_at=?, updated_at=?
                   WHERE window_id=? AND window_state='PLANNED'""",
                (terminal_state, cause, timestamp, timestamp, window),
            )
            if cursor.rowcount != 1:
                raise CampaignOwnershipError(
                    f"{CAMPAIGN_WINDOW_OWNERSHIP_CONFLICT}:terminal compare-and-update failed"
                )

            # Read-back identity verification before returning success.
            verify = connection.execute(
                """SELECT w.cycle_id, w.memory_window_row_id, w.window_state, m.cycle_id
                   FROM printer_memory_factory_campaign_windows AS w
                   JOIN printer_memory_windows AS m ON m.id=w.memory_window_row_id
                   WHERE w.window_id=?""",
                (window,),
            ).fetchone()
            if (
                verify is None
                or str(verify[0]) != cycle
                or verify[1] is None
                or int(verify[1]) != row_id
                or str(verify[2]) != terminal_state
                or str(verify[3]) != cycle
            ):
                raise CampaignOwnershipError(
                    f"{CAMPAIGN_WINDOW_OWNERSHIP_CONFLICT}:read-back verification failed"
                )
            return {
                "registered": True,
                "idempotent": False,
                "window_id": window,
                "cycle_id": cycle,
                "window_state": terminal_state,
                "memory_window_row_id": row_id,
            }
    except sqlite3.Error as exc:
        raise CampaignOwnershipError(str(exc)) from exc


def campaign_scheduler_work_id(campaign_id: str, scheduler_job_id: int) -> str:
    """Deterministic campaign Scheduler ownership id for one existing job.

    One Scheduler job maps to exactly one campaign ownership row; the id is a
    stable function of campaign and job so re-projection is idempotent by primary
    key and one job cannot land in two accounting stages.
    """
    campaign = _required(campaign_id, "campaign_id")
    return f"campaign-work|{campaign}|{int(scheduler_job_id)}"


def project_campaign_scheduler_job(
    connection: sqlite3.Connection,
    *,
    campaign_id: str,
    run_id: str,
    cycle_id: str,
    factory_run_id: str,
    token_slot_id: str,
    window_id: str,
    scheduler_job_id: int,
    job_kind: str,
    deadline_at: str,
    terminal_state: str,
    terminal_cause: str,
    now: str | None = None,
) -> dict[str, Any]:
    """Project one existing factory Scheduler job into campaign ownership.

    References the canonical ``printer_scheduler_jobs`` row and the factory
    run-step linkage rather than creating a replacement job. Idempotent on the
    exact identity; a second projection of the same job under a different owner or
    window fails closed with ``CAMPAIGN_SCHEDULER_WORK_OWNERSHIP_CONFLICT``.
    """
    timestamp = now or _utc_now()
    campaign = _required(campaign_id, "campaign_id")
    run = _required(run_id, "run_id")
    cycle = _required(cycle_id, "cycle_id")
    factory_run = _required(factory_run_id, "factory_run_id")
    slot = _required(token_slot_id, "token_slot_id")
    window = _required(window_id, "window_id")
    kind = _required(job_kind, "job_kind")
    deadline = _required(deadline_at, "deadline_at")
    terminal = _required(terminal_state, "terminal_state")
    cause = _required(terminal_cause, "terminal_cause")
    job_id = int(scheduler_job_id)
    if terminal not in _TERMINAL_WORK_STATES:
        raise CampaignOwnershipError(f"invalid terminal work state: {terminal}")
    work_id = campaign_scheduler_work_id(campaign, job_id)
    work_intent = f"{kind}|factory_run={factory_run}|job={job_id}"
    try:
        with connection:
            job = connection.execute(
                "SELECT id, job_kind FROM printer_scheduler_jobs WHERE id=?",
                (job_id,),
            ).fetchone()
            if job is None:
                raise CampaignOwnershipError(
                    f"unknown scheduler job for projection: {job_id}"
                )
            step = connection.execute(
                """SELECT run_id FROM printer_memory_factory_run_steps
                   WHERE scheduler_job_id=? ORDER BY id LIMIT 1""",
                (job_id,),
            ).fetchone()
            if step is None or str(step[0]) != factory_run:
                raise CampaignOwnershipError(
                    f"{CAMPAIGN_SCHEDULER_WORK_OWNERSHIP_CONFLICT}:job not owned by factory run"
                )

            duplicate_owner = connection.execute(
                """SELECT scheduler_work_id FROM printer_memory_factory_campaign_scheduler_work
                   WHERE scheduler_job_id=?""",
                (job_id,),
            ).fetchone()
            if duplicate_owner is not None and str(duplicate_owner[0]) != work_id:
                raise CampaignOwnershipError(
                    f"{CAMPAIGN_SCHEDULER_WORK_OWNERSHIP_CONFLICT}:job already owned by another stage"
                )

            existing = connection.execute(
                """SELECT campaign_id, run_id, cycle_id, token_slot_id, window_id,
                          scheduler_job_id, work_state
                   FROM printer_memory_factory_campaign_scheduler_work
                   WHERE scheduler_work_id=?""",
                (work_id,),
            ).fetchone()
            if existing is not None:
                same = (
                    str(existing[0]) == campaign
                    and str(existing[1]) == run
                    and str(existing[2]) == cycle
                    and str(existing[3]) == slot
                    and str(existing[4]) == window
                    and existing[5] is not None
                    and int(existing[5]) == job_id
                )
                if not same:
                    raise CampaignOwnershipError(
                        f"{CAMPAIGN_SCHEDULER_WORK_OWNERSHIP_CONFLICT}:work already owned differently"
                    )
                return {
                    "registered": False,
                    "idempotent": True,
                    "scheduler_work_id": work_id,
                    "scheduler_job_id": job_id,
                    "work_state": str(existing[6]),
                }

            connection.execute(
                """INSERT INTO printer_memory_factory_campaign_scheduler_work(
                    scheduler_work_id,campaign_id,run_id,cycle_id,token_slot_id,
                    window_id,work_intent,deadline_at,work_state,scheduler_job_id,
                    source_request_id,source_response_id,source_failure_id,
                    created_at,updated_at
                ) VALUES (?,?,?,?,?,?,?,?,'PENDING',?,NULL,NULL,NULL,?,?)""",
                (work_id, campaign, run, cycle, slot, window, work_intent, deadline,
                 job_id, timestamp, timestamp),
            )
            cursor = connection.execute(
                """UPDATE printer_memory_factory_campaign_scheduler_work
                   SET work_state=?, first_terminal_cause=?, terminal_at=?, updated_at=?
                   WHERE scheduler_work_id=? AND work_state='PENDING'""",
                (terminal, cause, timestamp, timestamp, work_id),
            )
            if cursor.rowcount != 1:
                raise CampaignOwnershipError(
                    f"{CAMPAIGN_SCHEDULER_WORK_OWNERSHIP_CONFLICT}:terminal compare-and-update failed"
                )
            return {
                "registered": True,
                "idempotent": False,
                "scheduler_work_id": work_id,
                "scheduler_job_id": job_id,
                "job_kind": kind,
                "work_state": terminal,
            }
    except sqlite3.Error as exc:
        raise CampaignOwnershipError(str(exc)) from exc


def canonical_object_payload(payload: Mapping[str, Any]) -> tuple[str, str]:
    try:
        encoded = json.dumps(
            payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True,
            allow_nan=False,
        )
    except (TypeError, ValueError) as exc:
        raise CampaignOwnershipError(f"object payload is not canonical JSON: {exc}") from exc
    return encoded, hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def persist_immutable_object(
    connection: sqlite3.Connection,
    *,
    object_id: str,
    object_kind: str,
    campaign_id: str,
    configuration_id: str,
    run_id: str,
    cycle_id: str,
    token_slot_id: str,
    window_id: str,
    payload: Mapping[str, Any],
    scheduler_work_id: str | None = None,
    authoritative_episode_id: int | None = None,
    safety_composite_id: int | None = None,
    lifecycle_event_id: int | None = None,
    now: str | None = None,
) -> str:
    object_json, object_hash = canonical_object_payload(payload)
    with connection:
        _write(
            connection,
            """INSERT INTO printer_memory_factory_campaign_objects(
                object_id,object_kind,campaign_id,configuration_id,run_id,cycle_id,
                token_slot_id,window_id,scheduler_work_id,object_hash,object_json,
                authoritative_episode_id,safety_composite_id,lifecycle_event_id,created_at
            ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (object_id,object_kind,campaign_id,configuration_id,run_id,cycle_id,
             token_slot_id,window_id,scheduler_work_id,object_hash,object_json,
             authoritative_episode_id,safety_composite_id,lifecycle_event_id,
             now or _utc_now()),
        )
    return object_hash


def link_report_object(
    connection: sqlite3.Connection,
    *,
    report_id: str,
    campaign_id: str,
    configuration_id: str,
    object_id: str,
    now: str | None = None,
) -> None:
    with connection:
        _write(
            connection,
            """INSERT INTO printer_memory_factory_campaign_report_objects(
                report_id,campaign_id,configuration_id,object_id,created_at
            ) VALUES (?,?,?,?,?)""",
            (report_id,campaign_id,configuration_id,object_id,now or _utc_now()),
        )


def transition_state(
    connection: sqlite3.Connection,
    *,
    record_kind: str,
    identity: str,
    expected_state: str,
    new_state: str,
    terminal_cause: str | None = None,
    now: str | None = None,
) -> StateTransitionResult:
    if record_kind not in _STATE_TABLES:
        raise CampaignOwnershipError(f"unsupported state owner: {record_kind}")
    table, identity_column, state_column, transitions, terminal_states = _STATE_TABLES[record_kind]
    timestamp = now or _utc_now()
    try:
        with connection:
            row = connection.execute(
                f"SELECT {state_column},first_terminal_cause,terminal_at FROM {table} WHERE {identity_column}=?",
                (identity,),
            ).fetchone()
            if row is None:
                raise CampaignOwnershipError(f"unknown {record_kind} identity: {identity}")
            current, first_cause, terminal_at = map(lambda value: value, row)
            if current in terminal_states:
                if current == new_state and first_cause == terminal_cause:
                    return StateTransitionResult(identity,current,current,first_cause,terminal_at,False)
                raise CampaignOwnershipError("terminal state and first cause are immutable")
            if current != expected_state:
                raise CampaignOwnershipError(
                    f"compare-and-update mismatch: expected {expected_state}, found {current}"
                )
            allowed = set(transitions.get(current, set()))
            if record_kind not in {"campaign", "run"}:
                allowed |= terminal_states
            if new_state not in allowed:
                raise CampaignOwnershipError(f"invalid {record_kind} transition: {current} -> {new_state}")
            if new_state in terminal_states:
                cause = _required(terminal_cause, "terminal_cause")
                terminal_value = timestamp
            else:
                if terminal_cause is not None:
                    raise CampaignOwnershipError("non-terminal transition cannot set a terminal cause")
                cause = None
                terminal_value = None
            cursor = connection.execute(
                f"""UPDATE {table} SET {state_column}=?,first_terminal_cause=?,
                    terminal_at=?,updated_at=?
                    WHERE {identity_column}=? AND {state_column}=?""",
                (new_state,cause,terminal_value,timestamp,identity,current),
            )
            if cursor.rowcount != 1:
                raise CampaignOwnershipError("state changed during compare-and-update")
            return StateTransitionResult(
                identity,current,new_state,cause,terminal_value,True
            )
    except sqlite3.Error as exc:
        raise CampaignOwnershipError(str(exc)) from exc
