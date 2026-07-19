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
