"""Transactional campaign ownership graph persistence for V2-9.7D.6B.1."""

from __future__ import annotations

from contextlib import nullcontext
from contextlib import nullcontext
from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import json
import sqlite3
from typing import Any, Mapping, Sequence

from printer_v1.operator_cli.campaign_active_work import (
    campaign_scoped_job_ids,
)
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


def cycle_scoped_token_slot_id(*, cycle_id: str, slot_ordinal: int) -> str:
    """Return the canonical token-slot identity for one exact campaign cycle."""
    cycle = _required(cycle_id, "cycle_id")
    if type(slot_ordinal) is not int or slot_ordinal not in (1, 2):
        raise CampaignOwnershipError("token slot ordinal must be exactly 1 or 2")
    return f"slot-{cycle}-{slot_ordinal}"


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
    try:
        from printer_v1.operator_cli.action_local_mutation_recorder import emit_insert

        emit_insert("printer_memory_factory_campaign_runs", run_id)
    except Exception:
        pass


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
            try:
                from printer_v1.operator_cli.action_local_mutation_recorder import (
                    emit_update,
                )

                emit_update("printer_memory_factory_campaign_runs", campaign_run)
            except Exception:
                pass
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
    commit_transaction: bool = True,
) -> None:
    if len(slots) != 2:
        raise CampaignOwnershipError("a cycle requires exactly two token slots")
    if {int(slot.get("slot_ordinal", 0)) for slot in slots} != {1, 2}:
        raise CampaignOwnershipError("token slot ordinals must be exactly 1 and 2")
    timestamp = now or _utc_now()
    try:
        with (connection if commit_transaction else nullcontext(connection)):
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
    """Legacy window-bound insert (V1_WINDOW_BOUND contract).

    This predates the V2-9.8B stage-scoped amendment and remains only for
    historical/window-bound rows. Repaired operational Scheduler ownership must
    go through :func:`project_campaign_scheduler_work`, the single scope-aware
    authority, not through this helper.
    """
    timestamp = now or _utc_now()
    with connection:
        _write(
            connection,
            """INSERT INTO printer_memory_factory_campaign_scheduler_work(
                scheduler_work_id,campaign_id,run_id,cycle_id,token_slot_id,
                window_id,work_intent,deadline_at,work_state,scheduler_job_id,
                source_request_id,source_response_id,source_failure_id,
                ownership_contract_version,created_at,updated_at
            ) VALUES (?,?,?,?,?,?,?,?,'PENDING',?,?,?,?,'V1_WINDOW_BOUND',?,?)""",
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
            if str(step_kind) not in {"WINDOW_CLOSE", "WINDOW_CLOSE_AUDIT"}:
                raise CampaignOwnershipError(
                    f"{CAMPAIGN_WINDOW_OWNERSHIP_CONFLICT}:step is not terminal WINDOW_CLOSE"
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



_PRE_1H_HANDOFF_TOKEN_STATES = frozenset(
    {"SELECTED", "WINDOW_15M_ACTIVE", "WINDOW_15M_CLOSED"}
)
_PRE_1H_HANDOFF_NEXT_STATE = {
    "SELECTED": "WINDOW_15M_ACTIVE",
    "WINDOW_15M_ACTIVE": "WINDOW_15M_CLOSED",
    "WINDOW_15M_CLOSED": "WINDOW_1H_CONTINUING",
}


def persist_standard_first_hour_handoff_set(
    connection: sqlite3.Connection,
    *,
    campaign_id: str,
    configuration_id: str,
    run_id: str,
    cycle_id: str,
    object_kind: str,
    candidates: Sequence[Mapping[str, Any]],
    now: str | None = None,
) -> dict[str, Any]:
    """Atomically persist one complete two-slot standard-first-hour handoff.

    The first authoritative continuation decision set, any WINDOW_1H successors,
    and token-slot advancement to WINDOW_1H_CONTINUING are one transaction. Any
    ownership conflict rolls the whole handoff set back.
    """
    if len(candidates) != 2:
        raise CampaignOwnershipError(
            f"standard first-hour handoff requires exactly two candidates; found {len(candidates)}"
        )
    campaign = _required(campaign_id, "campaign_id")
    configuration = _required(configuration_id, "configuration_id")
    run = _required(run_id, "run_id")
    cycle = _required(cycle_id, "cycle_id")
    kind = _required(object_kind, "object_kind")
    timestamp = now or _utc_now()

    try:
        with connection:
            slot_rows = connection.execute(
                """SELECT token_slot_id, token_row_id, pair_row_id, mint_identity,
                          pair_identity, lifecycle_identity, token_state
                   FROM printer_memory_factory_campaign_token_slots
                   WHERE campaign_id=? AND run_id=? AND cycle_id=?
                   ORDER BY slot_ordinal""",
                (campaign, run, cycle),
            ).fetchall()
            if len(slot_rows) != 2:
                raise CampaignOwnershipError(
                    "standard first-hour handoff requires the exact two-slot ownership set"
                )
            slot_by_id = {str(row[0]): row for row in slot_rows}
            prepared: list[dict[str, Any]] = []
            candidate_slot_ids: set[str] = set()

            for candidate in candidates:
                object_id = _required(candidate.get("object_id"), "object_id")
                payload_raw = candidate.get("payload")
                info_raw = candidate.get("info")
                if not isinstance(payload_raw, Mapping) or not isinstance(info_raw, Mapping):
                    raise CampaignOwnershipError("handoff candidate payload/info must be mappings")
                payload = dict(payload_raw)
                info = dict(info_raw)
                slot_id = _required(info.get("token_slot_id"), "token_slot_id")
                if slot_id in candidate_slot_ids or slot_id not in slot_by_id:
                    raise CampaignOwnershipError("handoff candidate token-slot set mismatch")
                candidate_slot_ids.add(slot_id)
                slot = slot_by_id[slot_id]
                state = str(slot[6])
                if state not in _PRE_1H_HANDOFF_TOKEN_STATES:
                    raise CampaignOwnershipError(
                        f"pre-handoff token state conflict for {slot_id}: {state}"
                    )
                if (
                    int(slot[1]) != int(info["token_row_id"])
                    or int(slot[2]) != int(info["pair_row_id"])
                    or str(slot[3]) != str(info["mint_identity"])
                    or str(slot[4]) != str(info["pair_identity"])
                    or str(slot[5]) != str(info["lifecycle_identity"])
                ):
                    raise CampaignOwnershipError(
                        f"handoff slot identity mismatch for {slot_id}"
                    )

                predecessor_id = _required(
                    info.get("campaign_window_15m_id"),
                    "campaign_window_15m_id",
                )
                predecessor = connection.execute(
                    """SELECT campaign_id, run_id, cycle_id, token_slot_id,
                              token_row_id, pair_row_id, window_kind, window_state,
                              root_15m_lifecycle_identity, memory_window_row_id
                       FROM printer_memory_factory_campaign_windows
                       WHERE window_id=?""",
                    (predecessor_id,),
                ).fetchone()
                if predecessor is None:
                    raise CampaignOwnershipError(
                        f"handoff predecessor missing for {slot_id}"
                    )
                if (
                    str(predecessor[0]) != campaign
                    or str(predecessor[1]) != run
                    or str(predecessor[2]) != cycle
                    or str(predecessor[3]) != slot_id
                    or int(predecessor[4]) != int(info["token_row_id"])
                    or int(predecessor[5]) != int(info["pair_row_id"])
                    or str(predecessor[6]) != "WINDOW_15M"
                    or str(predecessor[8]) != str(info["lifecycle_identity"])
                    or predecessor[9] is None
                    or int(predecessor[9]) != int(info["memory_window_15m_id"])
                ):
                    raise CampaignOwnershipError(
                        f"handoff predecessor identity mismatch for {slot_id}"
                    )

                continue_ok = bool(candidate.get("continue_ok"))
                if continue_ok and str(predecessor[7]) != "CLEAN_PROMOTED":
                    raise CampaignOwnershipError(
                        f"continuing predecessor is not CLEAN_PROMOTED for {slot_id}"
                    )
                if connection.execute(
                    "SELECT 1 FROM printer_memory_factory_campaign_objects WHERE object_id=?",
                    (object_id,),
                ).fetchone() is not None:
                    raise CampaignOwnershipError(
                        f"first handoff evaluation object already exists: {object_id}"
                    )

                successor_id = payload.get("campaign_window_1h_id")
                if continue_ok:
                    successor_id = _required(successor_id, "campaign_window_1h_id")
                    if connection.execute(
                        "SELECT 1 FROM printer_memory_factory_campaign_windows WHERE window_id=?",
                        (successor_id,),
                    ).fetchone() is not None:
                        raise CampaignOwnershipError(
                            f"pre-existing WINDOW_1H conflicts with first handoff: {successor_id}"
                        )
                elif successor_id is not None:
                    raise CampaignOwnershipError(
                        "non-continuing handoff candidate cannot own WINDOW_1H"
                    )

                object_json, object_hash = canonical_object_payload(payload)
                prepared.append(
                    {
                        "object_id": object_id,
                        "object_json": object_json,
                        "object_hash": object_hash,
                        "payload": payload,
                        "info": info,
                        "continue_ok": continue_ok,
                        "successor_id": successor_id,
                        "initial_state": state,
                    }
                )

            if candidate_slot_ids != set(slot_by_id):
                raise CampaignOwnershipError("handoff candidates do not cover both token slots")

            # Persist the complete immutable decision set only after every identity
            # and state preflight passes.
            for item in prepared:
                info = item["info"]
                _write(
                    connection,
                    """INSERT INTO printer_memory_factory_campaign_objects(
                        object_id,object_kind,campaign_id,configuration_id,run_id,cycle_id,
                        token_slot_id,window_id,scheduler_work_id,object_hash,object_json,
                        authoritative_episode_id,safety_composite_id,lifecycle_event_id,created_at
                    ) VALUES (?,?,?,?,?,?,?,?,NULL,?,?,?,NULL,NULL,?)""",
                    (
                        item["object_id"], kind, campaign, configuration, run, cycle,
                        info["token_slot_id"], info["campaign_window_15m_id"],
                        item["object_hash"], item["object_json"],
                        info.get("authoritative_episode_id"), timestamp,
                    ),
                )

            for item in prepared:
                if not item["continue_ok"]:
                    continue
                info = item["info"]
                successor_id = str(item["successor_id"])
                _write(
                    connection,
                    """INSERT INTO printer_memory_factory_campaign_windows(
                        window_id,campaign_id,run_id,cycle_id,token_slot_id,token_row_id,
                        pair_row_id,window_kind,window_state,root_15m_lifecycle_identity,
                        predecessor_window_id,containing_main_window_id,memory_window_row_id,
                        checkpoint_cutoff,support_only,created_at,updated_at
                    ) VALUES (?,?,?,?,?,?,?,'WINDOW_1H','PLANNED',?,?,NULL,NULL,?,0,?,?)""",
                    (
                        successor_id, campaign, run, cycle, info["token_slot_id"],
                        int(info["token_row_id"]), int(info["pair_row_id"]),
                        info["lifecycle_identity"], info["campaign_window_15m_id"],
                        timestamp, timestamp, timestamp,
                    ),
                )
                current = str(item["initial_state"])
                while current != "WINDOW_1H_CONTINUING":
                    next_state = _PRE_1H_HANDOFF_NEXT_STATE.get(current)
                    if next_state is None:
                        raise CampaignOwnershipError(
                            f"no valid first-hour state path from {current}"
                        )
                    if current == "SELECTED" and next_state == "WINDOW_15M_ACTIVE":
                        from printer_v1.operator_cli.cadence_authority import (
                            CadenceAuthorityError,
                            assert_slot_bound_tracking_authority_for_window_15m_active,
                        )

                        try:
                            assert_slot_bound_tracking_authority_for_window_15m_active(
                                connection,
                                token_slot_id=str(info["token_slot_id"]),
                            )
                        except CadenceAuthorityError as exc:
                            raise CampaignOwnershipError(
                                "WINDOW_15M_ACTIVE requires exact slot tracking "
                                f"authority: {exc}"
                            ) from exc
                    cursor = connection.execute(
                        """UPDATE printer_memory_factory_campaign_token_slots
                           SET token_state=?, updated_at=?
                           WHERE token_slot_id=? AND campaign_id=? AND run_id=?
                             AND cycle_id=? AND token_state=?""",
                        (
                            next_state, timestamp, info["token_slot_id"], campaign,
                            run, cycle, current,
                        ),
                    )
                    if cursor.rowcount != 1:
                        raise CampaignOwnershipError(
                            f"first-hour token-state compare-and-update failed for {info['token_slot_id']}"
                        )
                    current = next_state

            # Read-back verification is inside the same transaction; any mismatch
            # raises and rolls back objects, successor windows, and slot updates.
            persisted_ids = {
                str(row[0])
                for row in connection.execute(
                    """SELECT object_id FROM printer_memory_factory_campaign_objects
                       WHERE campaign_id=? AND run_id=? AND cycle_id=? AND object_kind=?""",
                    (campaign, run, cycle, kind),
                ).fetchall()
            }
            expected_ids = {str(item["object_id"]) for item in prepared}
            if persisted_ids != expected_ids:
                raise CampaignOwnershipError(
                    "first-hour immutable handoff object read-back mismatch"
                )
            for item in prepared:
                if not item["continue_ok"]:
                    continue
                info = item["info"]
                verify = connection.execute(
                    """SELECT w.token_slot_id,w.token_row_id,w.pair_row_id,
                              w.window_kind,w.window_state,w.root_15m_lifecycle_identity,
                              w.predecessor_window_id,w.memory_window_row_id,s.token_state
                       FROM printer_memory_factory_campaign_windows AS w
                       JOIN printer_memory_factory_campaign_token_slots AS s
                         ON s.token_slot_id=w.token_slot_id
                       WHERE w.window_id=?""",
                    (item["successor_id"],),
                ).fetchone()
                if (
                    verify is None
                    or str(verify[0]) != str(info["token_slot_id"])
                    or int(verify[1]) != int(info["token_row_id"])
                    or int(verify[2]) != int(info["pair_row_id"])
                    or str(verify[3]) != "WINDOW_1H"
                    or str(verify[4]) != "PLANNED"
                    or str(verify[5]) != str(info["lifecycle_identity"])
                    or str(verify[6]) != str(info["campaign_window_15m_id"])
                    or verify[7] is not None
                    or str(verify[8]) != "WINDOW_1H_CONTINUING"
                ):
                    raise CampaignOwnershipError(
                        f"first-hour handoff read-back mismatch for {info['token_slot_id']}"
                    )

            return {
                "persisted": True,
                "object_ids": sorted(expected_ids),
                "continuation_count": sum(1 for item in prepared if item["continue_ok"]),
            }
    except sqlite3.Error as exc:
        raise CampaignOwnershipError(str(exc)) from exc


def persist_standard_four_hour_handoff_set(
    connection: sqlite3.Connection,
    *,
    campaign_id: str,
    run_id: str,
    cycle_id: str,
    candidates: Sequence[Mapping[str, Any]],
    eligible_token_slot_ids: Sequence[str] | None = None,
    now: str | None = None,
) -> dict[str, Any]:
    """Persist the exact eligible subset of the standard two-slot 1h -> 4h handoff.

    The campaign identity remains exactly two owned slots.  Only slots in the
    explicit eligible subset receive WINDOW_4H ownership.  ``None`` preserves
    the historical all-eligible caller contract.  This B1 primitive creates no
    Scheduler jobs and performs no source work.
    """
    if len(candidates) != 2:
        raise CampaignOwnershipError(
            f"standard four-hour handoff requires exactly two candidates; found {len(candidates)}"
        )
    candidate_ids = [
        _required(candidate.get("token_slot_id"), "token_slot_id")
        for candidate in candidates
    ]
    if len(set(candidate_ids)) != 2:
        raise CampaignOwnershipError("standard four-hour candidates must own two distinct slots")
    if eligible_token_slot_ids is None:
        eligible_ids = set(candidate_ids)
    else:
        requested = [
            _required(slot_id, "eligible_token_slot_id")
            for slot_id in eligible_token_slot_ids
        ]
        if len(requested) != len(set(requested)):
            raise CampaignOwnershipError("four-hour eligible token-slot set contains duplicates")
        eligible_ids = set(requested)
        if not eligible_ids.issubset(set(candidate_ids)):
            raise CampaignOwnershipError("four-hour eligible token-slot set is not campaign-owned")

    campaign = _required(campaign_id, "campaign_id")
    run = _required(run_id, "run_id")
    cycle = _required(cycle_id, "cycle_id")
    timestamp = now or _utc_now()
    savepoint_active = False

    def rollback_savepoint() -> None:
        nonlocal savepoint_active
        if not savepoint_active:
            return
        try:
            connection.execute(
                "ROLLBACK TO SAVEPOINT printer_standard_four_hour_handoff"
            )
            connection.execute(
                "RELEASE SAVEPOINT printer_standard_four_hour_handoff"
            )
        except sqlite3.Error:
            pass
        savepoint_active = False

    try:
        connection.execute("SAVEPOINT printer_standard_four_hour_handoff")
        savepoint_active = True
        slot_rows = connection.execute(
            """SELECT token_slot_id, token_row_id, pair_row_id, mint_identity,
                      pair_identity, lifecycle_identity, token_state
               FROM printer_memory_factory_campaign_token_slots
               WHERE campaign_id=? AND run_id=? AND cycle_id=?
               ORDER BY slot_ordinal""",
            (campaign, run, cycle),
        ).fetchall()
        if len(slot_rows) != 2:
            raise CampaignOwnershipError(
                "standard four-hour handoff requires the exact two-slot ownership set"
            )
        slot_by_id = {str(row[0]): row for row in slot_rows}
        if set(candidate_ids) != set(slot_by_id):
            raise CampaignOwnershipError(
                "four-hour handoff candidates do not cover both token slots"
            )

        prepared: list[dict[str, Any]] = []
        successor_ids: set[str] = set()
        handoff_modes: set[str] = set()

        for candidate in candidates:
            slot_id = _required(candidate.get("token_slot_id"), "token_slot_id")
            slot = slot_by_id[slot_id]
            try:
                token_row_id = int(candidate.get("token_row_id"))
                pair_row_id = int(candidate.get("pair_row_id"))
                memory_window_1h_id = int(candidate.get("memory_window_1h_id"))
            except (TypeError, ValueError) as exc:
                raise CampaignOwnershipError(
                    f"four-hour handoff numeric identity invalid for {slot_id}"
                ) from exc
            mint_identity = _required(candidate.get("mint_identity"), "mint_identity")
            pair_identity = _required(candidate.get("pair_identity"), "pair_identity")
            lifecycle_identity = _required(
                candidate.get("lifecycle_identity"), "lifecycle_identity"
            )
            predecessor_id = _required(
                candidate.get("campaign_window_1h_id"), "campaign_window_1h_id"
            )
            successor_id = _required(
                candidate.get("campaign_window_4h_id"), "campaign_window_4h_id"
            )
            tracking_lane = _required(candidate.get("tracking_lane"), "tracking_lane")
            state = str(slot[6])
            if (
                int(slot[1]) != token_row_id
                or int(slot[2]) != pair_row_id
                or str(slot[3]) != mint_identity
                or str(slot[4]) != pair_identity
                or str(slot[5]) != lifecycle_identity
            ):
                raise CampaignOwnershipError(
                    f"four-hour handoff slot identity mismatch for {slot_id}"
                )

            slot_successors = connection.execute(
                """SELECT window_id FROM printer_memory_factory_campaign_windows
                   WHERE campaign_id=? AND run_id=? AND cycle_id=?
                     AND token_slot_id=? AND window_kind='WINDOW_4H'
                   ORDER BY window_id""",
                (campaign, run, cycle, slot_id),
            ).fetchall()
            scoped_successor_ids = {str(row[0]) for row in slot_successors}
            existing_named = connection.execute(
                "SELECT token_slot_id FROM printer_memory_factory_campaign_windows WHERE window_id=?",
                (successor_id,),
            ).fetchone()

            if slot_id not in eligible_ids:
                if state == "WINDOW_4H_CONTINUING":
                    raise CampaignOwnershipError(
                        f"ineligible four-hour slot is already continuing: {slot_id}"
                    )
                if scoped_successor_ids:
                    raise CampaignOwnershipError(
                        f"ineligible four-hour slot has a successor: {slot_id}"
                    )
                if existing_named is not None:
                    raise CampaignOwnershipError(
                        f"ineligible four-hour successor identity is already owned: {successor_id}"
                    )
                continue

            if state not in {"WINDOW_1H_CLOSED", "WINDOW_4H_CONTINUING"}:
                raise CampaignOwnershipError(
                    f"pre-four-hour token state conflict for {slot_id}: {state}"
                )
            if successor_id in successor_ids:
                raise CampaignOwnershipError(
                    "four-hour handoff successor identity is duplicated"
                )
            successor_ids.add(successor_id)

            predecessor = connection.execute(
                """SELECT campaign_id, run_id, cycle_id, token_slot_id,
                          token_row_id, pair_row_id, window_kind, window_state,
                          root_15m_lifecycle_identity, memory_window_row_id
                   FROM printer_memory_factory_campaign_windows
                   WHERE window_id=?""",
                (predecessor_id,),
            ).fetchone()
            if predecessor is None:
                raise CampaignOwnershipError(
                    f"four-hour handoff predecessor missing for {slot_id}"
                )
            if (
                str(predecessor[0]) != campaign
                or str(predecessor[1]) != run
                or str(predecessor[2]) != cycle
                or str(predecessor[3]) != slot_id
                or int(predecessor[4]) != token_row_id
                or int(predecessor[5]) != pair_row_id
                or str(predecessor[6]) != "WINDOW_1H"
                or str(predecessor[7]) != "CLEAN_PROMOTED"
                or str(predecessor[8]) != lifecycle_identity
                or predecessor[9] is None
                or int(predecessor[9]) != memory_window_1h_id
            ):
                raise CampaignOwnershipError(
                    f"four-hour handoff predecessor identity/eligibility mismatch for {slot_id}"
                )

            physical = connection.execute(
                """SELECT token_id, pair_id, window_kind, window_status,
                          data_quality_label, do_not_train, window_end_at
                   FROM printer_memory_windows WHERE id=?""",
                (memory_window_1h_id,),
            ).fetchone()
            if (
                physical is None
                or int(physical[0]) != token_row_id
                or int(physical[1]) != pair_row_id
                or str(physical[2]) != "WINDOW_1H"
                or str(physical[3]) != "WINDOW_CLOSED"
                or str(physical[4]) != "CLEAN_DATA"
                or bool(physical[5])
                or physical[6] is None
            ):
                raise CampaignOwnershipError(
                    f"physical first-hour identity/quality mismatch for {slot_id}"
                )

            clean_episode_count = int(
                connection.execute(
                    """SELECT COUNT(*) FROM printer_episodes
                       WHERE memory_window_id=? AND token_id=? AND pair_id=?
                         AND episode_kind='WINDOW_1H_CLEAN_MEMORY'
                         AND episode_status='COMPLETE'
                         AND memory_status='CLEAN_MEMORY'
                         AND data_quality_label='CLEAN_DATA'
                         AND do_not_train=0
                         AND window_kind='WINDOW_1H'
                         AND memory_quality_label='CLEAN_MEMORY'""",
                    (memory_window_1h_id, token_row_id, pair_row_id),
                ).fetchone()[0]
            )
            if clean_episode_count != 1:
                raise CampaignOwnershipError(
                    f"exact clean first-hour predecessor object missing/ambiguous for {slot_id}"
                )

            from datetime import timedelta
            from printer_v1.snapshots.cadence_policy import get_policy

            policy = get_policy("WINDOW_4H", tracking_lane)
            if policy is None:
                raise CampaignOwnershipError(
                    f"WINDOW_4H cadence policy missing for {tracking_lane}"
                )
            try:
                predecessor_end = datetime.fromisoformat(
                    str(physical[6]).replace("Z", "+00:00")
                )
            except ValueError as exc:
                raise CampaignOwnershipError(
                    f"physical first-hour close timestamp invalid for {slot_id}"
                ) from exc
            if predecessor_end.tzinfo is None:
                raise CampaignOwnershipError(
                    f"physical first-hour close timestamp is timezone-naive for {slot_id}"
                )
            checkpoint_cutoff = (
                predecessor_end.astimezone(timezone.utc)
                + timedelta(seconds=int(policy.window_close_interval_seconds))
            ).isoformat()

            existing = connection.execute(
                """SELECT campaign_id, run_id, cycle_id, token_slot_id,
                          token_row_id, pair_row_id, window_kind, window_state,
                          root_15m_lifecycle_identity, predecessor_window_id,
                          memory_window_row_id
                   FROM printer_memory_factory_campaign_windows
                   WHERE window_id=?""",
                (successor_id,),
            ).fetchone()
            if existing is None:
                if state != "WINDOW_1H_CLOSED" or scoped_successor_ids:
                    raise CampaignOwnershipError(
                        f"partial/conflicting four-hour handoff state for {slot_id}"
                    )
                mode = "NEW"
            else:
                if scoped_successor_ids != {successor_id}:
                    raise CampaignOwnershipError(
                        f"competing four-hour successor ownership for {slot_id}"
                    )
                if (
                    str(existing[0]) != campaign
                    or str(existing[1]) != run
                    or str(existing[2]) != cycle
                    or str(existing[3]) != slot_id
                    or int(existing[4]) != token_row_id
                    or int(existing[5]) != pair_row_id
                    or str(existing[6]) != "WINDOW_4H"
                    or str(existing[7]) != "PLANNED"
                    or str(existing[8]) != lifecycle_identity
                    or str(existing[9]) != predecessor_id
                    or existing[10] is not None
                    or state != "WINDOW_4H_CONTINUING"
                ):
                    raise CampaignOwnershipError(
                        f"conflicting four-hour replay identity for {slot_id}"
                    )
                mode = "REPLAY"
            handoff_modes.add(mode)
            prepared.append(
                {
                    "token_slot_id": slot_id,
                    "token_row_id": token_row_id,
                    "pair_row_id": pair_row_id,
                    "lifecycle_identity": lifecycle_identity,
                    "predecessor_id": predecessor_id,
                    "successor_id": successor_id,
                    "checkpoint_cutoff": checkpoint_cutoff,
                }
            )

        if len(handoff_modes) > 1:
            raise CampaignOwnershipError(
                "partial standard four-hour handoff cannot be replayed or completed"
            )

        if handoff_modes == {"NEW"}:
            for item in prepared:
                connection.execute(
                    """INSERT INTO printer_memory_factory_campaign_windows(
                        window_id,campaign_id,run_id,cycle_id,token_slot_id,token_row_id,
                        pair_row_id,window_kind,window_state,root_15m_lifecycle_identity,
                        predecessor_window_id,containing_main_window_id,memory_window_row_id,
                        checkpoint_cutoff,support_only,created_at,updated_at
                    ) VALUES (?,?,?,?,?,?,?,'WINDOW_4H','PLANNED',?,?,NULL,NULL,?,0,?,?)""",
                    (
                        item["successor_id"], campaign, run, cycle,
                        item["token_slot_id"], item["token_row_id"],
                        item["pair_row_id"], item["lifecycle_identity"],
                        item["predecessor_id"], item["checkpoint_cutoff"],
                        timestamp, timestamp,
                    ),
                )
            for item in prepared:
                cursor = connection.execute(
                    """UPDATE printer_memory_factory_campaign_token_slots
                       SET token_state='WINDOW_4H_CONTINUING', updated_at=?
                       WHERE token_slot_id=? AND campaign_id=? AND run_id=?
                         AND cycle_id=? AND token_state='WINDOW_1H_CLOSED'""",
                    (timestamp, item["token_slot_id"], campaign, run, cycle),
                )
                if cursor.rowcount != 1:
                    raise CampaignOwnershipError(
                        f"four-hour token-state compare-and-update failed for {item['token_slot_id']}"
                    )

        verify_rows = connection.execute(
            """SELECT window_id,token_slot_id,token_row_id,pair_row_id,window_kind,
                      window_state,root_15m_lifecycle_identity,predecessor_window_id,
                      memory_window_row_id
               FROM printer_memory_factory_campaign_windows
               WHERE campaign_id=? AND run_id=? AND cycle_id=?
                 AND window_kind='WINDOW_4H'
               ORDER BY token_slot_id""",
            (campaign, run, cycle),
        ).fetchall()
        if (
            len(verify_rows) != len(eligible_ids)
            or {str(row[0]) for row in verify_rows} != successor_ids
        ):
            raise CampaignOwnershipError(
                "standard four-hour successor read-back count/identity mismatch"
            )
        expected_by_id = {str(item["successor_id"]): item for item in prepared}
        for row in verify_rows:
            item = expected_by_id[str(row[0])]
            if (
                str(row[1]) != str(item["token_slot_id"])
                or int(row[2]) != int(item["token_row_id"])
                or int(row[3]) != int(item["pair_row_id"])
                or str(row[4]) != "WINDOW_4H"
                or str(row[5]) != "PLANNED"
                or str(row[6]) != str(item["lifecycle_identity"])
                or str(row[7]) != str(item["predecessor_id"])
                or row[8] is not None
            ):
                raise CampaignOwnershipError(
                    f"standard four-hour successor read-back mismatch for {item['token_slot_id']}"
                )
            slot_state = connection.execute(
                """SELECT token_state FROM printer_memory_factory_campaign_token_slots
                   WHERE token_slot_id=? AND campaign_id=? AND run_id=? AND cycle_id=?""",
                (item["token_slot_id"], campaign, run, cycle),
            ).fetchone()
            if slot_state is None or str(slot_state[0]) != "WINDOW_4H_CONTINUING":
                raise CampaignOwnershipError(
                    f"standard four-hour token-state read-back mismatch for {item['token_slot_id']}"
                )

        for slot_id in set(candidate_ids) - eligible_ids:
            slot_state = connection.execute(
                """SELECT token_state FROM printer_memory_factory_campaign_token_slots
                   WHERE token_slot_id=? AND campaign_id=? AND run_id=? AND cycle_id=?""",
                (slot_id, campaign, run, cycle),
            ).fetchone()
            if slot_state is None or str(slot_state[0]) == "WINDOW_4H_CONTINUING":
                raise CampaignOwnershipError(
                    f"ineligible four-hour token-state read-back mismatch for {slot_id}"
                )

        replay = bool(eligible_ids) and handoff_modes == {"REPLAY"}
        connection.execute("RELEASE SAVEPOINT printer_standard_four_hour_handoff")
        savepoint_active = False
        return {
            "persisted": not replay,
            "replay": replay,
            "continuation_count": len(eligible_ids),
            "window_ids": sorted(successor_ids),
        }
    except sqlite3.Error as exc:
        rollback_savepoint()
        raise CampaignOwnershipError(str(exc)) from exc
    except Exception:
        rollback_savepoint()
        raise

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
            if (
                record_kind == "token_slot"
                and current == "SELECTED"
                and new_state == "WINDOW_15M_ACTIVE"
            ):
                from printer_v1.operator_cli.cadence_authority import (
                    CadenceAuthorityError,
                    assert_slot_bound_tracking_authority_for_window_15m_active,
                )

                try:
                    assert_slot_bound_tracking_authority_for_window_15m_active(
                        connection, token_slot_id=identity
                    )
                except CadenceAuthorityError as exc:
                    raise CampaignOwnershipError(
                        f"WINDOW_15M_ACTIVE requires exact slot tracking authority: {exc}"
                    ) from exc
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


# ---------------------------------------------------------------------------
# V2-9.8B campaign Scheduler ownership: one scope-aware projection authority.
#
# Correction (V2-9.8B migration implementation, "scheduler ownership projection
# truth"): a projection may not accept an arbitrary caller-provided Scheduler
# state, nor treat batch existence or an untyped caller job-id set as ownership.
# For every projection the recorded work state and terminal evidence are derived
# from the canonical ``printer_scheduler_jobs`` row (or durable Scheduler
# evidence), and every scope's exact job lineage and target are proven against a
# durable owner. See the migration implementation report for the full contract.
# ---------------------------------------------------------------------------

WORK_SCOPES = (
    "DISCOVERY_SELECTION",
    "FIRST_15M_HANDOFF",
    "WINDOW_LIFECYCLE",
    "TERMINAL_CLEANUP",
)
_TERMINAL_WORK_STATES = frozenset(
    {"SUCCEEDED", "FAILED", "SKIPPED", "CANCELLED"}
)
_NON_TERMINAL_WORK_STATES = frozenset({"PENDING", "RUNNING", "COOLDOWN"})
SCHEDULER_OWNERSHIP_STATE_DRIFT = "SCHEDULER_OWNERSHIP_STATE_DRIFT"

# Exact allowed target category per scope. Each scope validator additionally
# proves the target identity against the scope's durable ownership source, so no
# arbitrary non-empty target value can satisfy a projection.
_SCOPE_TARGET_CATEGORIES = {
    "DISCOVERY_SELECTION": frozenset({"DISCOVERY_WORK"}),
    "FIRST_15M_HANDOFF": frozenset({"SELECTED_ITEM", "MERGED_CANDIDATE"}),
    "WINDOW_LIFECYCLE": frozenset({"CAMPAIGN_WINDOW"}),
    "TERMINAL_CLEANUP": frozenset({"SCHEDULER_JOB"}),
}

# Every column that forms the exact, immutable projection identity. Idempotency
# is allowed only when all of these match; any difference is competing ownership.
_PROJECTION_IDENTITY_COLUMNS = (
    "campaign_id", "run_id", "cycle_id", "token_slot_id", "window_id",
    "work_intent", "deadline_at", "scheduler_job_id", "source_request_id",
    "source_response_id", "source_failure_id", "ownership_contract_version",
    "stage_id", "work_scope", "target_category", "target_identity",
    "factory_run_id",
)


@dataclass(frozen=True)
class SchedulerWorkProjectionResult:
    """Outcome of projecting an existing Central Scheduler job into ownership."""

    scheduler_work_id: str
    campaign_id: str
    work_scope: str
    stage_id: str
    scheduler_job_id: int
    work_state: str
    created: bool


@dataclass(frozen=True)
class SchedulerCleanupCapture:
    """Immutable identity-bearing capture of the campaign-scoped active Scheduler
    jobs, taken from the campaign active-work owner *before* cancellation.

    The capture is the honest boundary evidence terminal cleanup requires: it
    proves which exact jobs were campaign-scoped and active at the capture
    instant, so a job cancelled and then owned cannot be laundered through an
    untyped caller-supplied id set. ``job_states`` maps each captured job id to
    its pre-cancellation Scheduler state; it is a sorted tuple of pairs so the
    whole capture is frozen and hashable.
    """

    campaign_id: str
    run_id: str
    cycle_id: str
    captured_at: str
    job_states: tuple[tuple[int, str], ...]

    def pre_state(self, scheduler_job_id: int) -> str | None:
        for job_id, state in self.job_states:
            if job_id == int(scheduler_job_id):
                return state
        return None

    @property
    def job_ids(self) -> tuple[int, ...]:
        return tuple(job_id for job_id, _state in self.job_states)


def capture_campaign_active_scheduler_jobs(
    connection: sqlite3.Connection,
    *,
    campaign_id: str,
    run_id: str,
    cycle_id: str,
    factory_run_id: str | None = None,
    captured_at: str | None = None,
) -> SchedulerCleanupCapture:
    """Build the immutable cleanup capture from the campaign active-work owner.

    This must be called *before* the cleanup cancellation runs, so the recorded
    ``job_states`` are the real pre-cancellation Scheduler states. It reuses the
    single campaign-scoped active-work owner (:func:`campaign_scoped_job_ids`) as
    the source of the exact campaign job set; it performs no Scheduler mutation.
    """
    campaign_id = _required(campaign_id, "campaign_id")
    run_id = _required(run_id, "run_id")
    cycle_id = _required(cycle_id, "cycle_id")
    groups = campaign_scoped_job_ids(
        connection,
        factory_run_id=factory_run_id,
        campaign_id=campaign_id,
        run_id=run_id,
        cycle_id=cycle_id,
        exact_scope=True,
    )
    every_id: set[int] = set().union(*groups.values()) if groups else set()
    states: list[tuple[int, str]] = []
    for job_id in sorted(every_id):
        row = connection.execute(
            "SELECT status FROM printer_scheduler_jobs WHERE id = ?",
            (job_id,),
        ).fetchone()
        if row is None:
            raise CampaignOwnershipError(
                f"captured campaign job {job_id} has no Scheduler row"
            )
        state = str(row[0])
        if state in _NON_TERMINAL_WORK_STATES:
            states.append((int(job_id), state))
    return SchedulerCleanupCapture(
        campaign_id=campaign_id,
        run_id=run_id,
        cycle_id=cycle_id,
        captured_at=captured_at or _utc_now(),
        job_states=tuple(states),
    )


def _opt_int(value: object, label: str) -> int | None:
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError) as exc:
        raise CampaignOwnershipError(f"{label} must be an integer") from exc


def _scheduler_job_actual_state(
    connection: sqlite3.Connection, *, scheduler_job_id: int
) -> tuple[str, object, object]:
    """Read the canonical Scheduler row; return (status, finished_at, last_error).

    Raises when the job does not exist — a projection references an existing
    Central Scheduler job and never creates one.
    """
    row = connection.execute(
        "SELECT status, finished_at, last_error FROM printer_scheduler_jobs "
        "WHERE id = ?",
        (scheduler_job_id,),
    ).fetchone()
    if row is None:
        raise CampaignOwnershipError(
            "scheduler job does not exist; projection cannot create one"
        )
    return str(row[0]), row[1], row[2]


@dataclass(frozen=True)
class _ExactOwnerStateEvidence:
    source: str
    work_state: str
    first_terminal_cause: str | None
    terminal_at: str | None


def _resolve_scheduler_state(
    connection: sqlite3.Connection,
    *,
    scheduler_job_id: int,
    requested_state: str | None,
    requested_cause: str | None,
    requested_terminal_at: str | None,
    exact_owner_evidence: _ExactOwnerStateEvidence | None = None,
) -> tuple[str, str | None, str | None]:
    """Derive/validate the exact actual work state from the canonical Scheduler.

    The recorded ownership state is always the real Scheduler state, not a caller
    narrative. A requested state that contradicts the Scheduler row is rejected,
    and a terminal ownership state can never be recorded while the real job is
    active. Terminal cause/time come only from the canonical owner or durable
    Scheduler evidence.
    """
    status, finished_at, last_error = _scheduler_job_actual_state(
        connection, scheduler_job_id=scheduler_job_id
    )
    if status not in _NON_TERMINAL_WORK_STATES | _TERMINAL_WORK_STATES:
        raise CampaignOwnershipError(f"unknown scheduler job status: {status}")
    if requested_state is not None and str(requested_state) != status:
        raise CampaignOwnershipError(
            f"requested work_state {requested_state!r} contradicts actual "
            f"Scheduler state {status!r}"
        )

    if status in _NON_TERMINAL_WORK_STATES:
        if exact_owner_evidence is not None and exact_owner_evidence.work_state != status:
            raise CampaignOwnershipError(
                "exact owner work_state contradicts active Scheduler status"
            )
        # Never project CANCELLED/FAILED/SUCCEEDED/SKIPPED while the job is active.
        if requested_cause is not None or requested_terminal_at is not None:
            raise CampaignOwnershipError(
                "active Scheduler job cannot carry a terminal cause or terminal_at"
            )
        return status, None, None

    if exact_owner_evidence is not None:
        if exact_owner_evidence.work_state != status:
            raise CampaignOwnershipError(
                "exact owner work_state contradicts terminal Scheduler status"
            )
        cause = exact_owner_evidence.first_terminal_cause
        terminal_at = exact_owner_evidence.terminal_at
    else:
        terminal_at = str(finished_at) if finished_at else None
        if status == "FAILED":
            cause = (
                str(last_error)
                if last_error and str(last_error).strip()
                else None
            )
        else:
            cause = f"SCHEDULER_JOB_{status}"
    if terminal_at is None:
        raise CampaignOwnershipError(
            "terminal Scheduler job lacks a canonical terminal time"
        )
    if cause is None or not str(cause).strip():
        raise CampaignOwnershipError(
            "terminal Scheduler job lacks a canonical terminal cause"
        )
    if requested_cause is not None and str(requested_cause) != cause:
        raise CampaignOwnershipError(
            "requested first_terminal_cause contradicts canonical Scheduler evidence"
        )
    if requested_terminal_at is not None and str(requested_terminal_at) != terminal_at:
        raise CampaignOwnershipError(
            "requested terminal_at contradicts canonical Scheduler evidence"
        )
    return status, cause, terminal_at


def _validate_discovery_selection_ownership(
    connection: sqlite3.Connection, *, campaign_id: str, run_id: str,
    cycle_id: str, scheduler_job_id: int, target_category: str,
    target_identity: str,
) -> _ExactOwnerStateEvidence:
    """Prove the exact Scheduler job lineage for a discovery or selection job.

    Batch existence alone is not Scheduler ownership. ``printer_discovery_work``
    is the canonical durable row that binds campaign / run / cycle / the exact
    discovery-or-selection work identity / and the exact ``scheduler_job_id``
    (selection is a ``DISCOVERY_UNIFORM_SELECTION`` work row on the same table).
    The target must be that exact durable owner, and its bound Scheduler job must
    equal the projected job. There is no batch-presence proxy path: a discovery
    or selection Scheduler job with no durable exact linkage fails closed here.
    """
    if target_category != "DISCOVERY_WORK":
        raise CampaignOwnershipError(
            "DISCOVERY_SELECTION target_category must be DISCOVERY_WORK "
            "(the exact printer_discovery_work owner carrying scheduler_job_id)"
        )
    rows = connection.execute(
        """SELECT work_type, work_state, first_terminal_cause, terminal_at
           FROM printer_discovery_work
           WHERE discovery_work_id = ? AND campaign_id = ?
             AND run_id = ? AND cycle_id = ? AND scheduler_job_id = ?""",
        (target_identity, campaign_id, run_id, cycle_id, scheduler_job_id),
    ).fetchall()
    if not rows:
        raise CampaignOwnershipError(
            "no exact printer_discovery_work lineage binding this Scheduler job "
            "to the discovery/selection identity for DISCOVERY_SELECTION"
        )
    if len(rows) != 1:
        raise CampaignOwnershipError(
            "multiple exact discovery/selection terminal-evidence rows"
        )
    row = rows[0]
    return _ExactOwnerStateEvidence(
        source=f"printer_discovery_work:{target_identity}",
        work_state=str(row[1]),
        first_terminal_cause=(str(row[2]) if row[2] is not None else None),
        terminal_at=(str(row[3]) if row[3] is not None else None),
    )


def _validate_first_15m_handoff_ownership(
    connection: sqlite3.Connection, *, campaign_id: str, run_id: str,
    cycle_id: str, scheduler_job_id: int, token_slot_id: str | None,
    target_category: str, target_identity: str,
) -> None:
    target_column = (
        "selection_item_id"
        if target_category == "SELECTED_ITEM"
        else "merged_candidate_id"
    )
    rows = connection.execute(
        f"""SELECT selection_item_id, merged_candidate_id, token_slot_id
           FROM printer_discovery_selected_item_links
           WHERE first_window_15m_scheduler_job_id = ?
             AND campaign_id = ? AND run_id = ? AND cycle_id = ?
             AND {target_column} = ?""",
        (scheduler_job_id, campaign_id, run_id, cycle_id, target_identity),
    ).fetchall()
    if not rows:
        raise CampaignOwnershipError(
            "no lawful first-15m handoff owner for scheduler job"
        )
    if len(rows) != 1:
        raise CampaignOwnershipError(
            "multiple conflicting exact first-15m handoff owners"
        )
    row = rows[0]
    link_item_id, link_candidate, link_slot = row[0], row[1], row[2]
    if token_slot_id is not None:
        if link_slot is None or str(link_slot) != str(token_slot_id):
            raise CampaignOwnershipError(
                "first-15m handoff token slot ownership mismatch"
            )
    if target_category == "SELECTED_ITEM":
        if str(target_identity) != str(link_item_id):
            raise CampaignOwnershipError(
                "first-15m handoff target identity mismatch"
            )
    elif target_category == "MERGED_CANDIDATE":
        if str(target_identity) != str(link_candidate):
            raise CampaignOwnershipError(
                "first-15m handoff target identity mismatch"
            )
    else:
        raise CampaignOwnershipError(
            "FIRST_15M_HANDOFF target_category must be "
            "SELECTED_ITEM or MERGED_CANDIDATE"
        )


def _validate_window_lifecycle_ownership(
    connection: sqlite3.Connection, *, campaign_id: str, run_id: str,
    cycle_id: str, token_slot_id: str, window_id: str, factory_run_id: str,
    scheduler_job_id: int, target_identity: str,
) -> None:
    """Bind a lifecycle job to the exact campaign window and campaign factory run.

    Rows from an unrelated campaign run or an unrelated factory run must not be
    composable: the campaign run must belong to the campaign, its bound
    ``authoritative_run_id`` must equal the supplied ``factory_run_id``, the
    factory run-step must reference this exact Scheduler job, and the exact
    window/slot must exist for this campaign/run/cycle.
    """
    if str(target_identity) != str(window_id):
        raise CampaignOwnershipError(
            "WINDOW_LIFECYCLE target_identity must equal the window_id"
        )
    window = connection.execute(
        """SELECT 1 FROM printer_memory_factory_campaign_windows
           WHERE window_id = ? AND token_slot_id = ? AND cycle_id = ?
             AND run_id = ? AND campaign_id = ?""",
        (window_id, token_slot_id, cycle_id, run_id, campaign_id),
    ).fetchone()
    if window is None:
        raise CampaignOwnershipError(
            "no exact campaign window/slot for WINDOW_LIFECYCLE"
        )
    campaign_run = connection.execute(
        """SELECT authoritative_run_id
           FROM printer_memory_factory_campaign_runs
           WHERE run_id = ? AND campaign_id = ?""",
        (run_id, campaign_id),
    ).fetchone()
    if campaign_run is None:
        raise CampaignOwnershipError(
            "campaign run does not belong to the campaign for WINDOW_LIFECYCLE"
        )
    if campaign_run[0] is None or str(campaign_run[0]) != str(factory_run_id):
        raise CampaignOwnershipError(
            "campaign run authoritative_run_id does not equal the supplied "
            "factory_run_id for WINDOW_LIFECYCLE"
        )
    step = connection.execute(
        """SELECT 1 FROM printer_memory_factory_run_steps
           WHERE run_id = ? AND scheduler_job_id = ?""",
        (factory_run_id, scheduler_job_id),
    ).fetchone()
    if step is None:
        raise CampaignOwnershipError(
            "no exact factory run-step linkage for WINDOW_LIFECYCLE"
        )


def _cleanup_exact_owner_evidence(
    connection: sqlite3.Connection,
    *,
    campaign_id: str,
    run_id: str,
    cycle_id: str,
    scheduler_job_id: int,
) -> _ExactOwnerStateEvidence | None:
    """Resolve cleanup ownership and any state evidence at exact scope.

    Discovery-work and existing campaign Scheduler-work rows carry state/cause/
    time. Selected-item links carry exact ownership but no terminal fields, so
    their terminal evidence remains the canonical Scheduler row. Conflicting
    state-bearing owners fail closed; there is no arbitrary first-row choice.
    """
    evidence: list[_ExactOwnerStateEvidence] = []
    durable_owner_count = 0
    discovery_rows = connection.execute(
        """SELECT discovery_work_id, work_state, first_terminal_cause, terminal_at
           FROM printer_discovery_work
           WHERE scheduler_job_id=? AND campaign_id=? AND run_id=? AND cycle_id=?
           ORDER BY discovery_work_id""",
        (scheduler_job_id, campaign_id, run_id, cycle_id),
    ).fetchall()
    durable_owner_count += len(discovery_rows)
    evidence.extend(
        _ExactOwnerStateEvidence(
            source=f"printer_discovery_work:{row[0]}",
            work_state=str(row[1]),
            first_terminal_cause=(str(row[2]) if row[2] is not None else None),
            terminal_at=(str(row[3]) if row[3] is not None else None),
        )
        for row in discovery_rows
    )
    ownership_rows = connection.execute(
        """SELECT scheduler_work_id, work_state, first_terminal_cause, terminal_at
           FROM printer_memory_factory_campaign_scheduler_work
           WHERE scheduler_job_id=? AND campaign_id=? AND run_id=? AND cycle_id=?
             AND ownership_contract_version='V2_STAGE_SCOPED'
           ORDER BY scheduler_work_id""",
        (scheduler_job_id, campaign_id, run_id, cycle_id),
    ).fetchall()
    durable_owner_count += len(ownership_rows)
    evidence.extend(
        _ExactOwnerStateEvidence(
            source=f"campaign_scheduler_work:{row[0]}",
            work_state=str(row[1]),
            first_terminal_cause=(str(row[2]) if row[2] is not None else None),
            terminal_at=(str(row[3]) if row[3] is not None else None),
        )
        for row in ownership_rows
    )
    handoff_count = int(
        connection.execute(
            """SELECT COUNT(*)
               FROM printer_discovery_selected_item_links
               WHERE first_window_15m_scheduler_job_id=?
                 AND campaign_id=? AND run_id=? AND cycle_id=?""",
            (scheduler_job_id, campaign_id, run_id, cycle_id),
        ).fetchone()[0]
    )
    durable_owner_count += handoff_count
    if durable_owner_count == 0:
        raise CampaignOwnershipError(
            "cleanup Scheduler job has no exact durable campaign/run/cycle owner"
        )
    distinct = {
        (item.work_state, item.first_terminal_cause, item.terminal_at)
        for item in evidence
    }
    if len(distinct) > 1:
        raise CampaignOwnershipError(
            "multiple conflicting exact cleanup terminal-evidence rows"
        )
    return evidence[0] if evidence else None


def _validate_cleanup_token_slot(
    connection: sqlite3.Connection,
    *,
    campaign_id: str,
    run_id: str,
    cycle_id: str,
    scheduler_job_id: int,
    token_slot_id: str | None,
) -> None:
    """Validate an optional cleanup slot without inventing job-to-slot truth."""
    if token_slot_id is None:
        return
    slot = connection.execute(
        """SELECT 1 FROM printer_memory_factory_campaign_token_slots
           WHERE token_slot_id=? AND campaign_id=? AND run_id=? AND cycle_id=?""",
        (token_slot_id, campaign_id, run_id, cycle_id),
    ).fetchone()
    if slot is None:
        raise CampaignOwnershipError(
            "cleanup token_slot_id is not in the exact campaign/run/cycle"
        )
    linked = connection.execute(
        """SELECT 1 FROM printer_discovery_selected_item_links
           WHERE first_window_15m_scheduler_job_id=? AND token_slot_id=?
             AND campaign_id=? AND run_id=? AND cycle_id=?""",
        (scheduler_job_id, token_slot_id, campaign_id, run_id, cycle_id),
    ).fetchone()
    if linked is None:
        linked = connection.execute(
            """SELECT 1
               FROM printer_memory_factory_campaign_scheduler_work
               WHERE scheduler_job_id=? AND token_slot_id=?
                 AND campaign_id=? AND run_id=? AND cycle_id=?
                 AND ownership_contract_version='V2_STAGE_SCOPED'""",
            (scheduler_job_id, token_slot_id, campaign_id, run_id, cycle_id),
        ).fetchone()
    if linked is None:
        raise CampaignOwnershipError(
            "cleanup Scheduler job has no durable link to token_slot_id; omit it"
        )


def _validate_terminal_cleanup_ownership(
    connection: sqlite3.Connection, *, campaign_id: str, run_id: str,
    cycle_id: str, scheduler_job_id: int, target_category: str,
    target_identity: str, token_slot_id: str | None, cleanup_capture: object,
) -> _ExactOwnerStateEvidence | None:
    """Validate a terminal cleanup projection against an immutable capture.

    The projected job must: belong to the exact campaign/run/cycle (proven from
    the campaign active-work owner, re-derived here); have been present in the
    pre-cancellation capture with an active pre-state; be terminal now (its
    current Scheduler terminal state is the recorded ownership state); target
    category ``SCHEDULER_JOB``; and target identity equal to the exact job id.
    """
    if not isinstance(cleanup_capture, SchedulerCleanupCapture):
        raise CampaignOwnershipError(
            "TERMINAL_CLEANUP requires an immutable SchedulerCleanupCapture from "
            "the campaign active-work owner"
        )
    if (
        cleanup_capture.campaign_id != campaign_id
        or cleanup_capture.run_id != run_id
        or cleanup_capture.cycle_id != cycle_id
    ):
        raise CampaignOwnershipError(
            "cleanup capture belongs to a different campaign/run/cycle"
        )
    if target_category != "SCHEDULER_JOB":
        raise CampaignOwnershipError(
            "TERMINAL_CLEANUP target_category must be SCHEDULER_JOB"
        )
    if str(target_identity) != str(int(scheduler_job_id)):
        raise CampaignOwnershipError(
            "TERMINAL_CLEANUP target_identity must equal the exact Scheduler job id"
        )

    exact_evidence = _cleanup_exact_owner_evidence(
        connection,
        campaign_id=campaign_id,
        run_id=run_id,
        cycle_id=cycle_id,
        scheduler_job_id=scheduler_job_id,
    )
    _validate_cleanup_token_slot(
        connection,
        campaign_id=campaign_id,
        run_id=run_id,
        cycle_id=cycle_id,
        scheduler_job_id=scheduler_job_id,
        token_slot_id=token_slot_id,
    )

    # It must have been captured before cancellation, with an active pre-state; a
    # capture taken after cancellation (terminal pre-state) or missing the job
    # fails closed.
    pre_state = cleanup_capture.pre_state(scheduler_job_id)
    if pre_state is None:
        raise CampaignOwnershipError(
            "cleanup Scheduler job was not present in the pre-cancellation capture"
        )
    if pre_state not in _NON_TERMINAL_WORK_STATES:
        raise CampaignOwnershipError(
            "cleanup capture pre-state is not active; capture was taken after "
            "cancellation"
        )

    return exact_evidence


def project_campaign_scheduler_work(
    connection: sqlite3.Connection,
    *,
    scheduler_work_id: str,
    campaign_id: str,
    run_id: str,
    cycle_id: str,
    work_scope: str,
    stage_id: str,
    work_intent: str,
    deadline_at: str,
    scheduler_job_id: int,
    target_category: str,
    target_identity: str,
    token_slot_id: str | None = None,
    window_id: str | None = None,
    factory_run_id: str | None = None,
    source_request_id: int | None = None,
    source_response_id: int | None = None,
    source_failure_id: int | None = None,
    work_state: str | None = None,
    first_terminal_cause: str | None = None,
    terminal_at: str | None = None,
    cleanup_capture: object = None,
    now: str | None = None,
) -> SchedulerWorkProjectionResult:
    """Project one existing Central Scheduler job into campaign ownership.

    This is the single, scope-aware Scheduler-ownership authority. It never
    creates a Scheduler job; it references an existing ``printer_scheduler_jobs``
    row, derives the recorded work state and terminal evidence from that
    canonical row and the scope's exact durable owner, proves the exact job
    lineage and target against its durable owner, and records a
    ``V2_STAGE_SCOPED`` ownership row. ``work_state`` / ``first_terminal_cause``
    / ``terminal_at`` are optional *assertions*: when supplied they are validated
    against the actual Scheduler state and rejected on contradiction, but the
    recorded values always come from those canonical owners. It is idempotent
    only for the exact same complete identity and unchanged canonical state;
    lawful Scheduler advances are synchronized through ``transition_state``.
    It rejects competing
    campaign/scope/stage/target/linkage ownership, and never fabricates a window,
    slot, or factory run-step.
    """
    scheduler_work_id = _required(scheduler_work_id, "scheduler_work_id")
    campaign_id = _required(campaign_id, "campaign_id")
    run_id = _required(run_id, "run_id")
    cycle_id = _required(cycle_id, "cycle_id")
    stage_id = _required(stage_id, "stage_id")
    work_intent = _required(work_intent, "work_intent")
    deadline_at = _required(deadline_at, "deadline_at")
    target_category = _required(target_category, "target_category")
    target_identity = _required(target_identity, "target_identity")
    if work_scope not in WORK_SCOPES:
        raise CampaignOwnershipError(f"unsupported work scope: {work_scope}")
    if scheduler_job_id is None:
        raise CampaignOwnershipError("scheduler_job_id is required for projection")
    scheduler_job_id = int(scheduler_job_id)
    token_slot_id = token_slot_id if token_slot_id else None
    window_id = window_id if window_id else None
    factory_run_id = factory_run_id if factory_run_id else None
    source_request_id = _opt_int(source_request_id, "source_request_id")
    source_response_id = _opt_int(source_response_id, "source_response_id")
    source_failure_id = _opt_int(source_failure_id, "source_failure_id")

    # ``work_state`` / terminal evidence are optional caller assertions; the
    # recorded values are derived from the canonical Scheduler row inside the
    # transaction. Here only reject a plainly invalid asserted state.
    if work_state is not None and (
        work_state not in _NON_TERMINAL_WORK_STATES | _TERMINAL_WORK_STATES
    ):
        raise CampaignOwnershipError(f"invalid work_state: {work_state}")

    # Exact allowed target category per scope (target identity proven per scope).
    allowed_categories = _SCOPE_TARGET_CATEGORIES[work_scope]
    if target_category not in allowed_categories:
        raise CampaignOwnershipError(
            f"{work_scope} target_category must be one of "
            f"{sorted(allowed_categories)}"
        )

    # Scope-conditional nullability (fail closed before any durable lookup).
    if work_scope == "DISCOVERY_SELECTION":
        if token_slot_id is not None or window_id is not None or factory_run_id is not None:
            raise CampaignOwnershipError(
                "DISCOVERY_SELECTION cannot carry a slot, window, or factory run"
            )
    elif work_scope == "FIRST_15M_HANDOFF":
        if window_id is not None or factory_run_id is not None:
            raise CampaignOwnershipError(
                "FIRST_15M_HANDOFF cannot carry a window or factory run"
            )
    elif work_scope == "WINDOW_LIFECYCLE":
        if token_slot_id is None or window_id is None or factory_run_id is None:
            raise CampaignOwnershipError(
                "WINDOW_LIFECYCLE requires exact factory run, slot, and window"
            )
    elif work_scope == "TERMINAL_CLEANUP":
        if window_id is not None or factory_run_id is not None:
            raise CampaignOwnershipError(
                "TERMINAL_CLEANUP cannot carry a window or factory run"
            )

    desired = {
        "campaign_id": campaign_id,
        "run_id": run_id,
        "cycle_id": cycle_id,
        "token_slot_id": token_slot_id,
        "window_id": window_id,
        "work_intent": work_intent,
        "deadline_at": deadline_at,
        "scheduler_job_id": scheduler_job_id,
        "source_request_id": source_request_id,
        "source_response_id": source_response_id,
        "source_failure_id": source_failure_id,
        "ownership_contract_version": "V2_STAGE_SCOPED",
        "stage_id": stage_id,
        "work_scope": work_scope,
        "target_category": target_category,
        "target_identity": target_identity,
        "factory_run_id": factory_run_id,
    }
    timestamp = now or _utc_now()

    try:
        transaction_context = (
            connection if not connection.in_transaction else nullcontext(connection)
        )
        with transaction_context:
            existing = connection.execute(
                f"""SELECT work_state, first_terminal_cause, terminal_at,
                    {", ".join(_PROJECTION_IDENTITY_COLUMNS)}
                    FROM printer_memory_factory_campaign_scheduler_work
                    WHERE scheduler_work_id = ?""",
                (scheduler_work_id,),
            ).fetchone()
            if existing is not None:
                existing_state = existing[0]
                existing_cause = existing[1]
                existing_terminal_at = existing[2]
                existing_identity = {
                    column: existing[index + 3]
                    for index, column in enumerate(_PROJECTION_IDENTITY_COLUMNS)
                }
                if existing_identity["ownership_contract_version"] != "V2_STAGE_SCOPED":
                    raise CampaignOwnershipError(
                        "existing scheduler work is not a V2 stage-scoped row"
                    )
                if existing_identity != desired:
                    raise CampaignOwnershipError(
                        "competing campaign/scope/stage/target/linkage ownership "
                        "for scheduler_work_id"
                    )
            else:
                existing_state = None
                existing_cause = None
                existing_terminal_at = None
                # One canonical Scheduler job to one campaign ownership stage.
                conflict = connection.execute(
                    """SELECT 1
                       FROM printer_memory_factory_campaign_scheduler_work
                       WHERE scheduler_job_id = ? AND scheduler_work_id <> ?""",
                    (scheduler_job_id, scheduler_work_id),
                ).fetchone()
                if conflict is not None:
                    raise CampaignOwnershipError(
                        "scheduler job already owned by another campaign work row"
                    )

            # Validate the scope against its real durable ownership source and
            # prove exact job lineage / target before terminal evidence is read.
            exact_evidence: _ExactOwnerStateEvidence | None = None
            try:
                if work_scope == "DISCOVERY_SELECTION":
                    exact_evidence = _validate_discovery_selection_ownership(
                        connection, campaign_id=campaign_id, run_id=run_id,
                        cycle_id=cycle_id, scheduler_job_id=scheduler_job_id,
                        target_category=target_category,
                        target_identity=target_identity,
                    )
                elif work_scope == "FIRST_15M_HANDOFF":
                    _validate_first_15m_handoff_ownership(
                        connection, campaign_id=campaign_id, run_id=run_id,
                        cycle_id=cycle_id, scheduler_job_id=scheduler_job_id,
                        token_slot_id=token_slot_id,
                        target_category=target_category,
                        target_identity=target_identity,
                    )
                elif work_scope == "WINDOW_LIFECYCLE":
                    _validate_window_lifecycle_ownership(
                        connection, campaign_id=campaign_id, run_id=run_id,
                        cycle_id=cycle_id, token_slot_id=token_slot_id,
                        window_id=window_id, factory_run_id=factory_run_id,
                        scheduler_job_id=scheduler_job_id,
                        target_identity=target_identity,
                    )
                elif work_scope == "TERMINAL_CLEANUP":
                    exact_evidence = _validate_terminal_cleanup_ownership(
                        connection, campaign_id=campaign_id, run_id=run_id,
                        cycle_id=cycle_id, scheduler_job_id=scheduler_job_id,
                        target_category=target_category,
                        target_identity=target_identity,
                        token_slot_id=token_slot_id,
                        cleanup_capture=cleanup_capture,
                    )

                actual_state, resolved_cause, resolved_at = _resolve_scheduler_state(
                    connection,
                    scheduler_job_id=scheduler_job_id,
                    requested_state=work_state,
                    requested_cause=first_terminal_cause,
                    requested_terminal_at=terminal_at,
                    exact_owner_evidence=exact_evidence,
                )
                if (
                    work_scope == "TERMINAL_CLEANUP"
                    and actual_state not in _TERMINAL_WORK_STATES
                ):
                    raise CampaignOwnershipError(
                        "cleanup Scheduler job is not terminal"
                    )
            except CampaignOwnershipError as exc:
                if existing is not None:
                    raise CampaignOwnershipError(
                        f"{SCHEDULER_OWNERSHIP_STATE_DRIFT}: {exc}"
                    ) from exc
                raise

            if existing is not None:
                if str(existing_state) == actual_state:
                    if (
                        existing_cause != resolved_cause
                        or existing_terminal_at != resolved_at
                    ):
                        raise CampaignOwnershipError(
                            f"{SCHEDULER_OWNERSHIP_STATE_DRIFT}: canonical "
                            "terminal evidence differs from stored ownership"
                        )
                    return SchedulerWorkProjectionResult(
                        scheduler_work_id=scheduler_work_id,
                        campaign_id=campaign_id,
                        work_scope=work_scope,
                        stage_id=stage_id,
                        scheduler_job_id=scheduler_job_id,
                        work_state=actual_state,
                        created=False,
                    )
                try:
                    transitioned = transition_state(
                        connection,
                        record_kind="scheduler_work",
                        identity=scheduler_work_id,
                        expected_state=str(existing_state),
                        new_state=actual_state,
                        terminal_cause=resolved_cause,
                        now=resolved_at or timestamp,
                    )
                except CampaignOwnershipError as exc:
                    raise CampaignOwnershipError(
                        f"{SCHEDULER_OWNERSHIP_STATE_DRIFT}: {exc}"
                    ) from exc
                return SchedulerWorkProjectionResult(
                    scheduler_work_id=scheduler_work_id,
                    campaign_id=campaign_id,
                    work_scope=work_scope,
                    stage_id=stage_id,
                    scheduler_job_id=scheduler_job_id,
                    work_state=transitioned.current_state,
                    created=False,
                )

            connection.execute(
                """INSERT INTO printer_memory_factory_campaign_scheduler_work(
                    scheduler_work_id, campaign_id, run_id, cycle_id, token_slot_id,
                    window_id, work_intent, deadline_at, work_state, scheduler_job_id,
                    source_request_id, source_response_id, source_failure_id,
                    ownership_contract_version, stage_id, work_scope, target_category,
                    target_identity, factory_run_id, first_terminal_cause, terminal_at,
                    created_at, updated_at
                ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,'V2_STAGE_SCOPED',?,?,?,?,?,?,?,?,?)""",
                (
                    scheduler_work_id, campaign_id, run_id, cycle_id, token_slot_id,
                    window_id, work_intent, deadline_at, actual_state,
                    scheduler_job_id, source_request_id, source_response_id,
                    source_failure_id, stage_id, work_scope, target_category,
                    target_identity, factory_run_id, resolved_cause, resolved_at,
                    timestamp, timestamp,
                ),
            )
    except sqlite3.Error as exc:
        raise CampaignOwnershipError(str(exc)) from exc

    return SchedulerWorkProjectionResult(
        scheduler_work_id=scheduler_work_id,
        campaign_id=campaign_id,
        work_scope=work_scope,
        stage_id=stage_id,
        scheduler_job_id=scheduler_job_id,
        work_state=actual_state,
        created=True,
    )


def project_campaign_scheduler_job(
    connection: sqlite3.Connection,
    *,
    scheduler_work_id: str,
    campaign_id: str,
    run_id: str,
    cycle_id: str,
    token_slot_id: str,
    window_id: str,
    factory_run_id: str,
    work_intent: str,
    deadline_at: str,
    scheduler_job_id: int,
    stage_id: str,
    target_category: str = "CAMPAIGN_WINDOW",
    target_identity: str | None = None,
    source_request_id: int | None = None,
    source_response_id: int | None = None,
    source_failure_id: int | None = None,
    work_state: str | None = None,
    first_terminal_cause: str | None = None,
    terminal_at: str | None = None,
    now: str | None = None,
) -> SchedulerWorkProjectionResult:
    """Compatibility wrapper for WINDOW_LIFECYCLE ownership.

    Retained only so lifecycle callers keep working; it delegates to the single
    scope-aware owner :func:`project_campaign_scheduler_work` and introduces no
    second ownership authority.
    """
    return project_campaign_scheduler_work(
        connection,
        scheduler_work_id=scheduler_work_id,
        campaign_id=campaign_id,
        run_id=run_id,
        cycle_id=cycle_id,
        work_scope="WINDOW_LIFECYCLE",
        stage_id=stage_id,
        work_intent=work_intent,
        deadline_at=deadline_at,
        scheduler_job_id=scheduler_job_id,
        target_category=target_category,
        target_identity=target_identity if target_identity else window_id,
        token_slot_id=token_slot_id,
        window_id=window_id,
        factory_run_id=factory_run_id,
        source_request_id=source_request_id,
        source_response_id=source_response_id,
        source_failure_id=source_failure_id,
        work_state=work_state,
        first_terminal_cause=first_terminal_cause,
        terminal_at=terminal_at,
        now=now,
    )
