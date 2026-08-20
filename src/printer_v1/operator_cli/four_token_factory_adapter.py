"""Proof-only adapter between the four-token controller and existing owners.

This module reserves only the second cycle row. The existing combined discovery
executor remains the sole owner of the atomic two-slot activation for that cycle.
It also reconstructs the existing two-token lifecycle ownership context from the
stage-scoped Scheduler owner for each claimed lifecycle job.

Nothing here fetches sources, runs discovery, schedules lifecycle work, activates
12h/24h, retrieves memory, or creates financial actions.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import sqlite3
from typing import Any, Callable, Mapping

from printer_v1.operator_cli.campaign_full_run_accounting import (
    OperationalLifecycleOwnershipContext,
    load_attributable_lifecycle_source_attempts,
    project_cycle_lifecycle_accounting_completeness,
)
from printer_v1.operator_cli.four_token_proof_integration import (
    FOUR_TOKEN_PROOF_MIN_SPACING_SECONDS,
    cycle_scoped_factory_step_ids,
    resolve_owned_cycle_for_scheduler_job,
)
from printer_v1.operator_cli.campaign_ownership import WORK_SCOPES
from printer_v1.operator_cli.multi_cycle_memory_growth import (
    scaled_standard_four_hour_capacity_contract,
)


class FourTokenFactoryAdapterError(ValueError):
    """Fail-closed four-token proof adapter violation."""


@dataclass(frozen=True)
class ReservedProofCycle:
    cycle_id: str
    cycle_ordinal: int
    cycle_state: str
    admitted_at: datetime


def _utc(value: datetime, label: str) -> datetime:
    if not isinstance(value, datetime) or value.tzinfo is None or value.utcoffset() is None:
        raise FourTokenFactoryAdapterError(f"{label} must be timezone-aware")
    return value.astimezone(timezone.utc)


def _required(value: object, label: str) -> str:
    if not isinstance(value, str) or not value or value != value.strip():
        raise FourTokenFactoryAdapterError(f"{label} must be a non-empty exact string")
    return value


def _table_exists(connection: sqlite3.Connection, table: str) -> bool:
    return connection.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?",
        (table,),
    ).fetchone() is not None


def _parse_time(value: object, label: str) -> datetime:
    if not isinstance(value, str) or not value.strip():
        raise FourTokenFactoryAdapterError(f"{label} is missing")
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError as exc:
        raise FourTokenFactoryAdapterError(f"{label} is malformed") from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise FourTokenFactoryAdapterError(f"{label} must be timezone-aware")
    return parsed.astimezone(timezone.utc)


def four_token_scaled_capacity_contract() -> dict[str, Any]:
    """Return the exact four-token envelope derived from canonical two-token law."""
    contract = scaled_standard_four_hour_capacity_contract(4)
    if (
        int(contract.get("configured_through_4h_tokens", 0)) != 4
        or int(contract.get("configured_active_cycles", 0)) != 2
        or int(contract.get("tokens_per_cycle", 0)) != 2
    ):
        raise FourTokenFactoryAdapterError("derived four-token capacity contract drifted")
    if contract.get("long_windows_activated") is not False:
        raise FourTokenFactoryAdapterError("long-window activation is forbidden")
    return contract


def build_four_token_cycle_accounting_package(
    connection: sqlite3.Connection,
    *,
    campaign_id: str,
    campaign_run_id: str,
    factory_run_id: str,
    cycle_id: str,
) -> dict[str, Any]:
    """Project one read-only two-token accounting package from durable owners."""
    campaign = _required(campaign_id, "campaign_id")
    run = _required(campaign_run_id, "campaign_run_id")
    factory = _required(factory_run_id, "factory_run_id")
    cycle = _required(cycle_id, "cycle_id")
    _require_exact_shared_run(
        connection,
        campaign_id=campaign,
        campaign_run_id=run,
        factory_run_id=factory,
    )
    cycle_row = connection.execute(
        "SELECT cycle_ordinal FROM printer_memory_factory_campaign_cycles "
        "WHERE campaign_id=? AND run_id=? AND cycle_id=?",
        (campaign, run, cycle),
    ).fetchone()
    if cycle_row is None or int(cycle_row[0]) not in (1, 2):
        raise FourTokenFactoryAdapterError(
            "cycle accounting ownership is missing or has invalid ordinal"
        )
    slots = connection.execute(
        "SELECT token_slot_id,slot_ordinal,token_row_id,pair_row_id "
        "FROM printer_memory_factory_campaign_token_slots "
        "WHERE campaign_id=? AND run_id=? AND cycle_id=? ORDER BY slot_ordinal",
        (campaign, run, cycle),
    ).fetchall()
    if len(slots) != 2 or tuple(int(row[1]) for row in slots) != (1, 2):
        raise FourTokenFactoryAdapterError(
            "cycle accounting requires exact two-slot ownership"
        )
    targets = tuple(
        {"token_id": int(row[2]), "pair_id": int(row[3])} for row in slots
    )
    if len({(item["token_id"], item["pair_id"]) for item in targets}) != 2:
        raise FourTokenFactoryAdapterError(
            "cycle accounting token/pair ownership is ambiguous"
        )

    scoped_step_ids = cycle_scoped_factory_step_ids(
        connection,
        campaign_id=campaign,
        campaign_run_id=run,
        factory_run_id=factory,
        cycle_id=cycle,
    )
    if not scoped_step_ids:
        raise FourTokenFactoryAdapterError(
            "cycle accounting Scheduler ownership is missing"
        )
    target_step_ids: list[int] = []
    for target in targets:
        target_step_ids.extend(int(row[0]) for row in connection.execute(
            "SELECT id FROM printer_memory_factory_run_steps "
            "WHERE run_id=? AND token_id=? AND pair_id=? "
            "AND scheduler_job_id IS NOT NULL ORDER BY id",
            (factory, target["token_id"], target["pair_id"]),
        ).fetchall())
    if tuple(sorted(target_step_ids)) != tuple(sorted(scoped_step_ids)):
        raise FourTokenFactoryAdapterError(
            "cycle accounting factory-step ownership is missing or extra"
        )

    placeholders = ",".join("?" for _ in scoped_step_ids)
    step_rows = connection.execute(
        "SELECT s.id,s.step_key,s.scheduler_job_id,j.status,w.scheduler_work_id "
        "FROM printer_memory_factory_run_steps AS s "
        "JOIN printer_scheduler_jobs AS j ON j.id=s.scheduler_job_id "
        "JOIN printer_memory_factory_campaign_scheduler_work AS w "
        "ON w.scheduler_job_id=s.scheduler_job_id "
        "AND w.ownership_contract_version='V2_STAGE_SCOPED' "
        f"WHERE s.id IN ({placeholders}) "
        "AND s.run_id=? AND w.campaign_id=? AND w.run_id=? "
        "AND w.factory_run_id=? AND w.cycle_id=? "
        "AND w.work_scope='WINDOW_LIFECYCLE' ORDER BY s.id,w.scheduler_work_id",
        (*scoped_step_ids, factory, campaign, run, factory, cycle),
    ).fetchall()
    if len(step_rows) != len(scoped_step_ids):
        raise FourTokenFactoryAdapterError(
            "cycle accounting Scheduler ownership is missing, extra, or ambiguous"
        )
    scheduler_job_ids = tuple(int(row[2]) for row in step_rows)
    scheduler_work_ids = tuple(str(row[4]) for row in step_rows)
    if (
        len(set(scheduler_job_ids)) != len(scheduler_job_ids)
        or len(set(scheduler_work_ids)) != len(scheduler_work_ids)
    ):
        raise FourTokenFactoryAdapterError(
            "cycle accounting Scheduler ownership is ambiguous"
        )
    owned_work = connection.execute(
        "SELECT scheduler_job_id FROM printer_memory_factory_campaign_scheduler_work "
        "WHERE campaign_id=? AND run_id=? AND factory_run_id=? AND cycle_id=? "
        "AND ownership_contract_version='V2_STAGE_SCOPED' "
        "AND work_scope='WINDOW_LIFECYCLE' ORDER BY scheduler_work_id",
        (campaign, run, factory, cycle),
    ).fetchall()
    if sorted(int(row[0]) for row in owned_work) != sorted(scheduler_job_ids):
        raise FourTokenFactoryAdapterError(
            "cycle accounting Scheduler ownership is missing or extra"
        )

    all_steps = connection.execute(
        "SELECT id,step_key FROM printer_memory_factory_run_steps "
        "WHERE run_id=? AND scheduler_job_id IS NOT NULL ORDER BY id",
        (factory,),
    ).fetchall()
    matched_requests: dict[int, int] = {}
    cycle_source_ids: list[int] = []
    for step in all_steps:
        attempts = load_attributable_lifecycle_source_attempts(
            connection,
            factory_run_id=factory,
            step_key=str(step[1]),
        )
        for attempt in attempts:
            request_id = int(attempt["source_request_id"])
            prior = matched_requests.get(request_id)
            if prior is not None and prior != int(step[0]):
                raise FourTokenFactoryAdapterError(
                    "cycle accounting source ownership is ambiguous"
                )
            matched_requests[request_id] = int(step[0])
            response_count = int(connection.execute(
                "SELECT COUNT(*) FROM printer_source_responses WHERE source_request_id=?",
                (request_id,),
            ).fetchone()[0])
            failure_count = int(connection.execute(
                "SELECT COUNT(*) FROM printer_source_failures WHERE source_request_id=?",
                (request_id,),
            ).fetchone()[0])
            if response_count > 1 or failure_count > 1 or (
                response_count and failure_count
            ):
                raise FourTokenFactoryAdapterError(
                    "cycle accounting source ownership is ambiguous"
                )
            if int(step[0]) in scoped_step_ids:
                cycle_source_ids.append(request_id)
    factory_request_ids = tuple(int(row[0]) for row in connection.execute(
        "SELECT id FROM printer_source_requests WHERE request_key LIKE ? ORDER BY id",
        (f"{factory}:%",),
    ).fetchall())
    if set(factory_request_ids) != set(matched_requests):
        raise FourTokenFactoryAdapterError(
            "cycle accounting source ownership is missing or extra"
        )
    if len(cycle_source_ids) != len(set(cycle_source_ids)):
        raise FourTokenFactoryAdapterError(
            "cycle accounting source ownership is ambiguous"
        )

    configuration_rows = connection.execute(
        "SELECT configuration_id FROM "
        "printer_memory_factory_campaign_configurations WHERE campaign_id=?",
        (campaign,),
    ).fetchall()
    if len(configuration_rows) != 1:
        raise FourTokenFactoryAdapterError(
            "cycle accounting configuration ownership is missing or ambiguous"
        )
    lifecycle_completeness = project_cycle_lifecycle_accounting_completeness(
        connection,
        context=OperationalLifecycleOwnershipContext(
            campaign_id=campaign,
            campaign_run_id=run,
            cycle_id=cycle,
            configuration_id=_required(
                configuration_rows[0][0], "configuration_id"
            ),
            factory_run_id=factory,
            expected_window_kind="WINDOW_15M",
            expected_token_capacity=2,
        ),
        factory_step_ids=scoped_step_ids,
    )
    if lifecycle_completeness.get("complete") is not True:
        reasons = ",".join(
            str(item) for item in lifecycle_completeness.get("reasons", ())
        )
        raise FourTokenFactoryAdapterError(
            "canonical lifecycle accounting is incomplete"
            + (f": {reasons}" if reasons else "")
        )

    memory_quality: list[str] = []
    for slot in slots:
        windows = connection.execute(
            "SELECT mw.memory_quality_label "
            "FROM printer_memory_factory_campaign_windows AS cw "
            "LEFT JOIN printer_memory_windows AS mw ON mw.id=cw.memory_window_row_id "
            "WHERE cw.campaign_id=? AND cw.run_id=? AND cw.cycle_id=? "
            "AND cw.token_slot_id=? AND cw.window_kind='WINDOW_15M'",
            (campaign, run, cycle, str(slot[0])),
        ).fetchall()
        if len(windows) > 1:
            raise FourTokenFactoryAdapterError(
                "cycle accounting window ownership is ambiguous"
            )
        label = None if not windows else windows[0][0]
        memory_quality.append(str(label or "NO_PROMOTION"))

    return {
        "cycle_id": cycle,
        "cycle_ordinal": int(cycle_row[0]),
        "factory_run_id": factory,
        "structurally_safe": True,
        "selected_targets": targets,
        "memory_quality": tuple(memory_quality),
        "accounting_package": {
            "expected_token_capacity": 2,
            "factory_step_ids": tuple(scoped_step_ids),
            "source_requests": len(cycle_source_ids),
            "source_request_ids": tuple(sorted(cycle_source_ids)),
            "scheduler_jobs": len(scheduler_job_ids),
            "scheduler_job_ids": scheduler_job_ids,
            "scheduler_work_ids": scheduler_work_ids,
            "scheduler_statuses": tuple(str(row[3]) for row in step_rows),
            "attribution_owner": "V2_STAGE_SCOPED_SCHEDULER_AND_FULL_RUN_REQUEST_KEY",
            "lifecycle_completeness": lifecycle_completeness,
        },
    }


def _require_exact_shared_run(
    connection: sqlite3.Connection,
    *,
    campaign_id: str,
    campaign_run_id: str,
    factory_run_id: str,
) -> None:
    row = connection.execute(
        """SELECT run_state,authoritative_run_id
           FROM printer_memory_factory_campaign_runs
           WHERE campaign_id=? AND run_id=?""",
        (campaign_id, campaign_run_id),
    ).fetchone()
    if row is None:
        raise FourTokenFactoryAdapterError("campaign run identity is missing")
    if str(row[0]) != "RUNNING":
        raise FourTokenFactoryAdapterError("campaign run is not RUNNING")
    if str(row[1] or "") != factory_run_id:
        raise FourTokenFactoryAdapterError(
            "campaign run is not bound to the expected authoritative factory run"
        )


def reserve_second_proof_cycle(
    connection: sqlite3.Connection,
    *,
    campaign_id: str,
    campaign_run_id: str,
    factory_run_id: str,
    first_cycle_id: str,
    now: datetime,
) -> ReservedProofCycle:
    """Reserve cycle ordinal 2 only; do not create token slots.

    The combined discovery executor requires a durable cycle row before it begins
    its governed cycle. It remains the sole owner of the two-slot activation.
    """
    campaign = _required(campaign_id, "campaign_id")
    run = _required(campaign_run_id, "campaign_run_id")
    factory = _required(factory_run_id, "factory_run_id")
    first_cycle = _required(first_cycle_id, "first_cycle_id")
    instant = _utc(now, "now")

    if connection.in_transaction:
        raise FourTokenFactoryAdapterError(
            "second-cycle reservation requires ownership of a fresh transaction"
        )
    try:
        connection.execute("BEGIN IMMEDIATE")
        _require_exact_shared_run(
            connection,
            campaign_id=campaign,
            campaign_run_id=run,
            factory_run_id=factory,
        )
        cycles = connection.execute(
            """SELECT cycle_id,cycle_ordinal,cycle_state,created_at
               FROM printer_memory_factory_campaign_cycles
               WHERE campaign_id=? AND run_id=?
               ORDER BY cycle_ordinal""",
            (campaign, run),
        ).fetchall()
        if len(cycles) != 1:
            raise FourTokenFactoryAdapterError(
                "second-cycle proof reservation requires exactly one existing cycle"
            )
        first = cycles[0]
        if (
            str(first[0]) != first_cycle
            or int(first[1]) != 1
            or str(first[2]).startswith("TERMINAL_")
        ):
            raise FourTokenFactoryAdapterError(
                "first-cycle identity/state is not eligible for second-cycle proof admission"
            )
        slots = connection.execute(
            """SELECT slot_ordinal,created_at
               FROM printer_memory_factory_campaign_token_slots
               WHERE campaign_id=? AND run_id=? AND cycle_id=?
               ORDER BY slot_ordinal""",
            (campaign, run, first_cycle),
        ).fetchall()
        if len(slots) != 2 or {int(row[0]) for row in slots} != {1, 2}:
            raise FourTokenFactoryAdapterError(
                "first cycle must already own exactly two token slots"
            )
        admitted_times = {_parse_time(row[1], "first-cycle slot created_at") for row in slots}
        if len(admitted_times) != 1:
            raise FourTokenFactoryAdapterError(
                "first-cycle pair does not have one atomic admission timestamp"
            )
        first_admitted_at = next(iter(admitted_times))
        if (instant - first_admitted_at).total_seconds() < FOUR_TOKEN_PROOF_MIN_SPACING_SECONDS:
            raise FourTokenFactoryAdapterError(
                "second-cycle proof admission cannot occur before 300 seconds"
            )

        second_cycle_id = f"{first_cycle}-2"
        if connection.execute(
            "SELECT 1 FROM printer_memory_factory_campaign_cycles WHERE cycle_id=?",
            (second_cycle_id,),
        ).fetchone() is not None:
            raise FourTokenFactoryAdapterError("second proof cycle is already reserved")
        timestamp = instant.isoformat()
        connection.execute(
            """INSERT INTO printer_memory_factory_campaign_cycles(
                   cycle_id,campaign_id,run_id,cycle_ordinal,cycle_state,
                   first_terminal_cause,terminal_at,created_at,updated_at
               ) VALUES (?,?,?,?, 'PLANNED',NULL,NULL,?,?)""",
            (second_cycle_id, campaign, run, 2, timestamp, timestamp),
        )
        connection.commit()
        return ReservedProofCycle(
            cycle_id=second_cycle_id,
            cycle_ordinal=2,
            cycle_state="PLANNED",
            admitted_at=instant,
        )
    except FourTokenFactoryAdapterError:
        if connection.in_transaction:
            connection.rollback()
        raise
    except sqlite3.Error as exc:
        if connection.in_transaction:
            connection.rollback()
        raise FourTokenFactoryAdapterError(
            f"second-cycle reservation persistence failed: {exc}"
        ) from exc


def validate_second_cycle_atomic_activation(
    connection: sqlite3.Connection,
    *,
    campaign_id: str,
    campaign_run_id: str,
    factory_run_id: str,
    cycle_id: str,
) -> dict[str, Any]:
    """Verify that the existing discovery owner created exactly two new slots."""
    campaign = _required(campaign_id, "campaign_id")
    run = _required(campaign_run_id, "campaign_run_id")
    factory = _required(factory_run_id, "factory_run_id")
    cycle = _required(cycle_id, "cycle_id")
    _require_exact_shared_run(
        connection,
        campaign_id=campaign,
        campaign_run_id=run,
        factory_run_id=factory,
    )
    row = connection.execute(
        """SELECT cycle_ordinal,cycle_state
           FROM printer_memory_factory_campaign_cycles
           WHERE campaign_id=? AND run_id=? AND cycle_id=?""",
        (campaign, run, cycle),
    ).fetchone()
    if row is None or int(row[0]) != 2:
        raise FourTokenFactoryAdapterError("second cycle identity is missing or not ordinal 2")
    slots = connection.execute(
        """SELECT slot_ordinal,token_row_id,pair_row_id,mint_identity,pair_identity
           FROM printer_memory_factory_campaign_token_slots
           WHERE campaign_id=? AND run_id=? AND cycle_id=?
           ORDER BY slot_ordinal""",
        (campaign, run, cycle),
    ).fetchall()
    if len(slots) != 2 or tuple(int(item[0]) for item in slots) != (1, 2):
        raise FourTokenFactoryAdapterError(
            "second cycle activation is not an exact two-slot atomic handoff"
        )
    for column_index, label in ((1, "token"), (2, "pair"), (3, "mint"), (4, "pair identity")):
        values = {item[column_index] for item in slots}
        if len(values) != 2:
            raise FourTokenFactoryAdapterError(
                f"second cycle {label} identities are not distinct"
            )
    first_values = connection.execute(
        """SELECT token_row_id,pair_row_id,mint_identity,pair_identity
           FROM printer_memory_factory_campaign_token_slots
           WHERE campaign_id=? AND run_id=? AND cycle_id<>?""",
        (campaign, run, cycle),
    ).fetchall()
    first_tokens = {item[0] for item in first_values}
    first_pairs = {item[1] for item in first_values}
    first_mints = {item[2] for item in first_values}
    first_pair_identities = {item[3] for item in first_values}
    if any(
        item[1] in first_tokens
        or item[2] in first_pairs
        or item[3] in first_mints
        or item[4] in first_pair_identities
        for item in slots
    ):
        raise FourTokenFactoryAdapterError(
            "second-cycle token/pair identity duplicates the first cycle"
        )
    return {
        "cycle_id": cycle,
        "cycle_ordinal": 2,
        "cycle_state": str(row[1]),
        "slot_count": 2,
        "slot_ordinals": (1, 2),
        "distinct_from_first_cycle": True,
        "factory_run_id": factory,
    }


def terminalize_unfilled_reserved_cycle(
    connection: sqlite3.Connection,
    *,
    campaign_id: str,
    campaign_run_id: str,
    cycle_id: str,
    cause: str,
    now: datetime,
) -> dict[str, Any]:
    """Terminalize only an empty reserved cycle; leave shared run/campaign alive."""
    campaign = _required(campaign_id, "campaign_id")
    run = _required(campaign_run_id, "campaign_run_id")
    cycle = _required(cycle_id, "cycle_id")
    reason = _required(cause, "cause")
    instant = _utc(now, "now")
    if connection.in_transaction:
        raise FourTokenFactoryAdapterError(
            "reserved-cycle terminalization requires a fresh transaction"
        )
    try:
        connection.execute("BEGIN IMMEDIATE")
        row = connection.execute(
            """SELECT cycle_state FROM printer_memory_factory_campaign_cycles
               WHERE campaign_id=? AND run_id=? AND cycle_id=?""",
            (campaign, run, cycle),
        ).fetchone()
        if row is None:
            raise FourTokenFactoryAdapterError("reserved cycle does not exist")
        if str(row[0]).startswith("TERMINAL_"):
            raise FourTokenFactoryAdapterError("reserved cycle is already terminal")
        slots = int(connection.execute(
            """SELECT COUNT(*) FROM printer_memory_factory_campaign_token_slots
               WHERE campaign_id=? AND run_id=? AND cycle_id=?""",
            (campaign, run, cycle),
        ).fetchone()[0])
        if slots != 0:
            raise FourTokenFactoryAdapterError(
                "filled cycle cannot use unfilled-reservation terminalization"
            )
        timestamp = instant.isoformat()
        cursor = connection.execute(
            """UPDATE printer_memory_factory_campaign_cycles
               SET cycle_state='TERMINAL_BLOCKED',first_terminal_cause=?,
                   terminal_at=?,updated_at=?
               WHERE campaign_id=? AND run_id=? AND cycle_id=?
                 AND cycle_state NOT LIKE 'TERMINAL_%'""",
            (reason, timestamp, timestamp, campaign, run, cycle),
        )
        if cursor.rowcount != 1:
            raise FourTokenFactoryAdapterError(
                "reserved cycle terminal compare-and-update failed"
            )
        connection.commit()
        return {
            "cycle_id": cycle,
            "cycle_state": "TERMINAL_BLOCKED",
            "first_terminal_cause": reason,
            "shared_run_terminalized": False,
        }
    except FourTokenFactoryAdapterError:
        if connection.in_transaction:
            connection.rollback()
        raise
    except sqlite3.Error as exc:
        if connection.in_transaction:
            connection.rollback()
        raise FourTokenFactoryAdapterError(
            f"reserved-cycle terminalization failed: {exc}"
        ) from exc


def build_cycle_lifecycle_ownership_context(
    connection: sqlite3.Connection,
    *,
    scheduler_job_id: int,
    campaign_id: str,
    campaign_run_id: str,
    configuration_id: str,
    factory_run_id: str,
) -> OperationalLifecycleOwnershipContext:
    """Reconstruct the existing exact two-token context for a claimed job's cycle."""
    configuration = _required(configuration_id, "configuration_id")
    try:
        owner = resolve_owned_cycle_for_scheduler_job(
            connection,
            scheduler_job_id=scheduler_job_id,
            campaign_id=campaign_id,
            campaign_run_id=campaign_run_id,
            factory_run_id=factory_run_id,
        )
        return OperationalLifecycleOwnershipContext(
            campaign_id=owner.campaign_id,
            campaign_run_id=owner.campaign_run_id,
            cycle_id=owner.cycle_id,
            configuration_id=configuration,
            factory_run_id=owner.factory_run_id,
            expected_window_kind="WINDOW_15M",
            expected_token_capacity=2,
        )
    except Exception as exc:
        if isinstance(exc, FourTokenFactoryAdapterError):
            raise
        raise FourTokenFactoryAdapterError(
            f"cycle lifecycle ownership context could not be resolved: {exc}"
        ) from exc


def _validate_pre_lifecycle_zero_attempt_provenance_shape(
    connection: sqlite3.Connection,
    *,
    campaign_id: str,
    campaign_run_id: str,
    factory_run_id: str,
    cycle_id: str,
    cycle_ordinal: int,
    run_status: str | None,
    terminal_phase: str | None,
) -> bool:
    if terminal_phase is None:
        return False
    if terminal_phase != "CAMPAIGN_PRE_LIFECYCLE":
        raise FourTokenFactoryAdapterError(
            "unsupported four-token terminal phase provenance"
        )
    if not _table_exists(
        connection, "printer_four_token_pre_lifecycle_terminal_provenance"
    ):
        raise FourTokenFactoryAdapterError(
            "pre-lifecycle zero-attempt provenance table is missing"
        )
    if int(cycle_ordinal) != 1:
        raise FourTokenFactoryAdapterError(
            "pre-lifecycle zero-attempt provenance requires Cycle 1"
        )
    if str(run_status or "").strip().upper() == "COMPLETED":
        raise FourTokenFactoryAdapterError(
            "completed cycle cannot carry pre-lifecycle zero-attempt provenance"
        )
    cycles = connection.execute(
        "SELECT cycle_id,cycle_ordinal FROM printer_memory_factory_campaign_cycles "
        "WHERE campaign_id=? AND run_id=? ORDER BY cycle_ordinal",
        (campaign_id, campaign_run_id),
    ).fetchall()
    attempt_count = int(connection.execute(
        "SELECT COUNT(*) FROM printer_pre_admission_discovery_attempts "
        "WHERE campaign_id=? AND campaign_run_id=? "
        "AND authoritative_factory_run_id=? AND proposed_cycle_ordinal=2",
        (campaign_id, campaign_run_id, factory_run_id),
    ).fetchone()[0])
    window_count = int(connection.execute(
        "SELECT COUNT(*) FROM printer_memory_factory_campaign_windows "
        "WHERE campaign_id=? AND run_id=? AND cycle_id=?",
        (campaign_id, campaign_run_id, cycle_id),
    ).fetchone()[0])
    existing = int(connection.execute(
        "SELECT COUNT(*) FROM printer_four_token_pre_lifecycle_terminal_provenance "
        "WHERE campaign_id=? AND campaign_run_id=? "
        "AND authoritative_factory_run_id=? AND proposed_cycle_ordinal=2",
        (campaign_id, campaign_run_id, factory_run_id),
    ).fetchone()[0])
    if (
        len(cycles) != 1
        or str(cycles[0][0]) != cycle_id
        or int(cycles[0][1]) != 1
        or attempt_count != 0
        or window_count != 0
        or existing != 0
    ):
        raise FourTokenFactoryAdapterError(
            "pre-lifecycle zero-attempt provenance requires exact persisted shape"
        )
    return True


def _insert_pre_lifecycle_zero_attempt_provenance(
    connection: sqlite3.Connection,
    *,
    campaign_id: str,
    campaign_run_id: str,
    factory_run_id: str,
    cycle_id: str,
    cause: str,
    recorded_at: str,
) -> None:
    try:
        connection.execute(
            """INSERT INTO printer_four_token_pre_lifecycle_terminal_provenance(
                   campaign_id,campaign_run_id,authoritative_factory_run_id,
                   cycle_id,cycle_ordinal,proposed_cycle_ordinal,terminal_phase,
                   first_terminal_cause,recorded_at
               ) VALUES (?,?,?,?,1,2,'CAMPAIGN_PRE_LIFECYCLE',?,?)""",
            (
                campaign_id,
                campaign_run_id,
                factory_run_id,
                cycle_id,
                cause,
                recorded_at,
            ),
        )
    except sqlite3.Error as exc:
        raise FourTokenFactoryAdapterError(
            f"pre-lifecycle zero-attempt provenance insert failed: {exc}"
        ) from exc


def reconcile_four_token_cycle_terminal(
    connection: sqlite3.Connection,
    *,
    campaign_id: str,
    campaign_run_id: str,
    factory_run_id: str,
    cycle_id: str,
    cause: str,
    run_status: str | None,
    now: datetime,
    terminal_phase: str | None = None,
) -> dict[str, Any]:
    """Phase A: terminalize one exact proof cycle without shared state."""
    campaign = _required(campaign_id, "campaign_id")
    run = _required(campaign_run_id, "campaign_run_id")
    factory = _required(factory_run_id, "factory_run_id")
    cycle = _required(cycle_id, "cycle_id")
    reason = _required(cause, "cause")
    instant = _utc(now, "now")
    timestamp = instant.isoformat()
    if connection.in_transaction:
        raise FourTokenFactoryAdapterError(
            "cycle terminal reconciliation requires a fresh transaction"
        )
    _require_exact_shared_run(
        connection,
        campaign_id=campaign,
        campaign_run_id=run,
        factory_run_id=factory,
    )
    row = connection.execute(
        "SELECT cycle_ordinal,cycle_state,first_terminal_cause "
        "FROM printer_memory_factory_campaign_cycles "
        "WHERE campaign_id=? AND run_id=? AND cycle_id=?",
        (campaign, run, cycle),
    ).fetchone()
    if row is None or int(row[0]) not in (1, 2):
        raise FourTokenFactoryAdapterError("proof cycle identity is missing or invalid")
    if str(row[1]).startswith("TERMINAL_"):
        return {
            "cycle_id": cycle,
            "cycle_state": str(row[1]),
            "first_terminal_cause": str(row[2]),
            "shared_terminalized": False,
            "already_terminal": True,
        }
    slot_count = int(connection.execute(
        "SELECT COUNT(*) FROM printer_memory_factory_campaign_token_slots "
        "WHERE campaign_id=? AND run_id=? AND cycle_id=?",
        (campaign, run, cycle),
    ).fetchone()[0])
    if slot_count != 2:
        raise FourTokenFactoryAdapterError(
            "filled proof-cycle terminal reconciliation requires exactly two slots"
        )
    pre_lifecycle_provenance_eligible = (
        _validate_pre_lifecycle_zero_attempt_provenance_shape(
            connection,
            campaign_id=campaign,
            campaign_run_id=run,
            factory_run_id=factory,
            cycle_id=cycle,
            cycle_ordinal=int(row[0]),
            run_status=run_status,
            terminal_phase=terminal_phase,
        )
    )
    work_rows = connection.execute(
        "SELECT scheduler_work_id,scheduler_job_id,ownership_contract_version,"
        "work_scope,work_state FROM printer_memory_factory_campaign_scheduler_work "
        "WHERE campaign_id=? AND run_id=? AND cycle_id=? ORDER BY scheduler_work_id",
        (campaign, run, cycle),
    ).fetchall()
    if any(
        str(item[2]) != "V2_STAGE_SCOPED"
        or str(item[3]) not in WORK_SCOPES
        or item[1] is None
        for item in work_rows
    ):
        raise FourTokenFactoryAdapterError(
            "cycle terminal reconciliation found non-canonical lifecycle ownership"
        )
    from printer_v1.operator_cli.four_token_proof_integration import (
        cycle_scoped_factory_step_ids,
    )
    scoped_step_ids = cycle_scoped_factory_step_ids(
        connection,
        campaign_id=campaign,
        campaign_run_id=run,
        factory_run_id=factory,
        cycle_id=cycle,
    )

    from printer_v1.operator_cli.unified_terminal_closure import (
        resolve_terminal_state,
    )
    from printer_v1.operator_cli.campaign_ownership import transition_state
    from printer_v1.scheduler.scheduler import cancel_job

    for item in work_rows:
        job = connection.execute(
            "SELECT status,locked_at,lock_owner FROM printer_scheduler_jobs WHERE id=?",
            (int(item[1]),),
        ).fetchone()
        if job is None:
            raise FourTokenFactoryAdapterError(
                "cycle lifecycle Scheduler job is missing"
            )
        if str(job[0]) in {"PENDING", "RUNNING", "COOLDOWN"} or (
            job[1] is not None or job[2] is not None
        ):
            cancel_job(connection, job_id=int(item[1]), now=instant)

    terminal_state = resolve_terminal_state(
        run_status=run_status, terminal_cause=reason
    )
    for item in work_rows:
        if str(item[4]) in {"PENDING", "RUNNING", "COOLDOWN"}:
            transition_state(
                connection,
                record_kind="scheduler_work",
                identity=str(item[0]),
                expected_state=str(item[4]),
                new_state="CANCELLED",
                terminal_cause=reason,
                now=timestamp,
            )
    window_rows = connection.execute(
        "SELECT window_id,window_state FROM printer_memory_factory_campaign_windows "
        "WHERE campaign_id=? AND run_id=? AND cycle_id=? ORDER BY window_id",
        (campaign, run, cycle),
    ).fetchall()
    for window in window_rows:
        if str(window[1]) in {"PLANNED", "COLLECTING", "CLOSE_PENDING", "AUDITING"}:
            transition_state(
                connection,
                record_kind="window",
                identity=str(window[0]),
                expected_state=str(window[1]),
                new_state="CANCELLED",
                terminal_cause=reason,
                now=timestamp,
            )
    slot_rows = connection.execute(
        "SELECT token_slot_id,token_state FROM printer_memory_factory_campaign_token_slots "
        "WHERE campaign_id=? AND run_id=? AND cycle_id=? ORDER BY slot_ordinal",
        (campaign, run, cycle),
    ).fetchall()
    for slot in slot_rows:
        if str(slot[1]) not in {"COOLDOWN", "ARCHIVED", "MANUAL_REVIEW", "FAILED"}:
            transition_state(
                connection,
                record_kind="token_slot",
                identity=str(slot[0]),
                expected_state=str(slot[1]),
                new_state="MANUAL_REVIEW",
                terminal_cause=reason,
                now=timestamp,
            )
    if scoped_step_ids:
        placeholders = ",".join("?" for _ in scoped_step_ids)
        connection.execute(
            "UPDATE printer_memory_factory_run_steps "
            "SET step_status='CANCELLED',error_or_skip_reason=?,"
            "finished_at=?,updated_at=? "
            f"WHERE id IN ({placeholders}) "
            "AND step_status IN ('PENDING','RUNNING')",
            (reason, timestamp, timestamp, *scoped_step_ids),
        )
        connection.commit()
    pre_lifecycle_provenance_recorded = False
    if pre_lifecycle_provenance_eligible:
        _insert_pre_lifecycle_zero_attempt_provenance(
            connection,
            campaign_id=campaign,
            campaign_run_id=run,
            factory_run_id=factory,
            cycle_id=cycle,
            cause=reason,
            recorded_at=timestamp,
        )
        pre_lifecycle_provenance_recorded = True
    transition_state(
        connection,
        record_kind="cycle",
        identity=cycle,
        expected_state=str(row[1]),
        new_state=terminal_state,
        terminal_cause=reason,
        now=timestamp,
    )

    active_work = int(connection.execute(
        "SELECT COUNT(*) FROM printer_memory_factory_campaign_scheduler_work "
        "WHERE campaign_id=? AND run_id=? AND cycle_id=? "
        "AND work_state IN ('PENDING','RUNNING','COOLDOWN')",
        (campaign, run, cycle),
    ).fetchone()[0])
    active_jobs = 0
    for item in work_rows:
        job = connection.execute(
            "SELECT status,locked_at,lock_owner FROM printer_scheduler_jobs WHERE id=?",
            (int(item[1]),),
        ).fetchone()
        if job is not None and (
            str(job[0]) in {"PENDING", "RUNNING", "COOLDOWN"}
            or job[1] is not None
            or job[2] is not None
        ):
            active_jobs += 1
    if active_work or active_jobs:
        raise FourTokenFactoryAdapterError(
            "cycle terminal reconciliation left active owned work"
        )
    if scoped_step_ids:
        placeholders = ",".join("?" for _ in scoped_step_ids)
        active_steps = int(connection.execute(
            "SELECT COUNT(*) FROM printer_memory_factory_run_steps "
            f"WHERE id IN ({placeholders}) AND step_status IN ('PENDING','RUNNING')",
            scoped_step_ids,
        ).fetchone()[0])
        if active_steps:
            raise FourTokenFactoryAdapterError(
                "cycle terminal reconciliation left active owned factory steps"
            )
    return {
        "cycle_id": cycle,
        "cycle_state": terminal_state,
        "first_terminal_cause": reason,
        "active_owned_work": 0,
        "active_owned_jobs": 0,
        "pre_lifecycle_zero_attempt_provenance_recorded": (
            pre_lifecycle_provenance_recorded
        ),
        "shared_terminalized": False,
        "already_terminal": False,
    }


def finalize_four_token_shared_terminal(
    connection: sqlite3.Connection,
    *,
    campaign_id: str,
    campaign_run_id: str,
    factory_run_id: str,
    shared_terminalizer: Callable[[], Mapping[str, Any]],
) -> dict[str, Any]:
    """Phase B: compose the existing shared terminal/cleanup owner once."""
    campaign = _required(campaign_id, "campaign_id")
    run = _required(campaign_run_id, "campaign_run_id")
    factory = _required(factory_run_id, "factory_run_id")
    rows = connection.execute(
        "SELECT cycle_id,cycle_ordinal,cycle_state,first_terminal_cause "
        "FROM printer_memory_factory_campaign_cycles "
        "WHERE campaign_id=? AND run_id=? ORDER BY cycle_ordinal",
        (campaign, run),
    ).fetchall()
    ordinals = [int(item[1]) for item in rows]
    admitted_shape = "TWO_CYCLE_COMPLETION"
    if len(rows) == 1 and ordinals == [1]:
        attempt_rows = connection.execute(
            "SELECT attempt_state,first_terminal_cause,consumed_cycle_id "
            "FROM printer_pre_admission_discovery_attempts "
            "WHERE campaign_id=? AND campaign_run_id=? "
            "AND authoritative_factory_run_id=? AND proposed_cycle_ordinal=2",
            (campaign, run, factory),
        ).fetchall()
        provenance_rows = (
            connection.execute(
                "SELECT cycle_id,cycle_ordinal,proposed_cycle_ordinal,terminal_phase,"
                "first_terminal_cause "
                "FROM printer_four_token_pre_lifecycle_terminal_provenance "
                "WHERE campaign_id=? AND campaign_run_id=? "
                "AND authoritative_factory_run_id=? AND proposed_cycle_ordinal=2",
                (campaign, run, factory),
            ).fetchall()
            if _table_exists(
                connection, "printer_four_token_pre_lifecycle_terminal_provenance"
            )
            else []
        )
        honest_no_admission = (
            len(attempt_rows) == 1
            and str(attempt_rows[0][0]) in {
                "NO_PAIR", "BLOCKED", "FAILED", "CANCELLED"
            }
            and bool(str(attempt_rows[0][1] or "").strip())
            and attempt_rows[0][2] is None
        )
        if honest_no_admission:
            if provenance_rows:
                raise FourTokenFactoryAdapterError(
                    "one-cycle terminal has contradictory attempt and pre-lifecycle provenance"
                )
            admitted_shape = "ONE_CYCLE_HONEST_NO_ADMISSION"
        elif len(attempt_rows) == 0:
            cycle_cause = str(rows[0][3] or "").strip()
            window_count = int(connection.execute(
                "SELECT COUNT(*) FROM printer_memory_factory_campaign_windows "
                "WHERE campaign_id=? AND run_id=? AND cycle_id=?",
                (campaign, run, str(rows[0][0])),
            ).fetchone()[0])
            if (
                len(provenance_rows) != 1
                or str(provenance_rows[0][0]) != str(rows[0][0])
                or int(provenance_rows[0][1]) != 1
                or int(provenance_rows[0][2]) != 2
                or str(provenance_rows[0][3]) != "CAMPAIGN_PRE_LIFECYCLE"
                or not cycle_cause
                or str(provenance_rows[0][4] or "").strip() != cycle_cause
                or window_count != 0
            ):
                raise FourTokenFactoryAdapterError(
                    "one-cycle shared terminal requires exact pre-lifecycle zero-attempt provenance"
                )
            admitted_shape = "ONE_CYCLE_PRE_LIFECYCLE_ZERO_ATTEMPT"
        else:
            raise FourTokenFactoryAdapterError(
                "one-cycle shared terminal requires exact terminal no-admission evidence"
            )
    elif len(rows) != 2 or ordinals != [1, 2]:
        raise FourTokenFactoryAdapterError(
            "shared terminal requires exact admitted-cycle ownership"
        )
    if any(not str(item[2]).startswith("TERMINAL_") for item in rows):
        raise FourTokenFactoryAdapterError(
            "shared terminal requires both cycles to be terminal"
        )
    active = int(connection.execute(
        "SELECT COUNT(*) FROM printer_memory_factory_campaign_scheduler_work AS w "
        "JOIN printer_scheduler_jobs AS j ON j.id=w.scheduler_job_id "
        "WHERE w.campaign_id=? AND w.run_id=? "
        "AND (w.work_state IN ('PENDING','RUNNING','COOLDOWN') "
        "OR j.status IN ('PENDING','RUNNING','COOLDOWN') "
        "OR j.locked_at IS NOT NULL OR j.lock_owner IS NOT NULL)",
        (campaign, run),
    ).fetchone()[0])
    if active:
        raise FourTokenFactoryAdapterError(
            "shared terminal requires zero active or orphan lifecycle work"
        )
    pending_steps = int(connection.execute(
        "SELECT COUNT(*) FROM printer_memory_factory_run_steps "
        "WHERE run_id=? AND step_status IN ('PENDING','RUNNING')",
        (factory,),
    ).fetchone()[0])
    if pending_steps:
        raise FourTokenFactoryAdapterError(
            "shared terminal requires zero active factory steps"
        )
    from printer_v1.operator_cli.campaign_active_work import (
        campaign_active_work_report,
    )

    active_report = campaign_active_work_report(
        connection,
        factory_run_id=factory,
        campaign_id=campaign,
        run_id=run,
    )
    run_row = connection.execute(
        "SELECT run_state,authoritative_run_id FROM printer_memory_factory_campaign_runs "
        "WHERE campaign_id=? AND run_id=?",
        (campaign, run),
    ).fetchone()
    if run_row is None or str(run_row[1] or "") != factory:
        raise FourTokenFactoryAdapterError("shared terminal identity is missing")
    factory_row = connection.execute(
        "SELECT run_status FROM printer_memory_factory_runs WHERE run_id=?",
        (factory,),
    ).fetchone()
    if factory_row is None:
        raise FourTokenFactoryAdapterError("shared terminal factory identity is missing")
    factory_status = str(factory_row[0])
    factory_active = factory_status in {"PENDING", "RUNNING"}
    campaign_already_terminal = str(run_row[0]).startswith("TERMINAL_")

    # Linked factory PENDING/RUNNING is owned residue that the canonical terminal
    # owner must still clear. Any other uncleanness remains fail-closed.
    otherwise_clean = (
        int(active_report.get("active_jobs") or 0) == 0
        and int(active_report.get("active_work_rows") or 0) == 0
        and int(active_report.get("terminal_work_with_active_job") or 0) == 0
        and int(active_report.get("pending_or_running_run_steps") or 0) == 0
        and int(active_report.get("active_pre_lifecycle_refresh_waits") or 0) == 0
        and int(active_report.get("active_pre_admission_attempts") or 0) == 0
    )
    if not otherwise_clean:
        raise FourTokenFactoryAdapterError(
            "shared terminal requires zero active or orphan campaign work"
        )
    if campaign_already_terminal and not factory_active:
        if active_report.get("clean_terminal") is not True:
            raise FourTokenFactoryAdapterError(
                "shared terminal requires zero active or orphan campaign work"
            )
        return {
            "shared_terminalized": False,
            "shared_cleanup_count": 0,
            "already_terminal": True,
            "admitted_shape": admitted_shape,
        }
    result = shared_terminalizer()
    if not isinstance(result, Mapping):
        raise FourTokenFactoryAdapterError(
            "shared terminal owner did not return evidence"
        )
    if result.get("clean_terminal") is not True or result.get("lease_released") is not True:
        raise FourTokenFactoryAdapterError(
            "shared terminal owner did not prove clean terminal and lease release"
        )
    run_after = connection.execute(
        "SELECT run_state FROM printer_memory_factory_campaign_runs "
        "WHERE campaign_id=? AND run_id=?",
        (campaign, run),
    ).fetchone()
    factory_after = connection.execute(
        "SELECT run_status FROM printer_memory_factory_runs WHERE run_id=?",
        (factory,),
    ).fetchone()
    if (
        run_after is None
        or not str(run_after[0]).startswith("TERMINAL_")
        or factory_after is None
        or str(factory_after[0]) in {"PENDING", "RUNNING"}
    ):
        raise FourTokenFactoryAdapterError(
            "shared terminal owner did not terminalize shared run identities"
        )
    return {
        "shared_terminalized": True,
        "shared_cleanup_count": 1,
        "already_terminal": False,
        "admitted_shape": admitted_shape,
        "shared_evidence": dict(result),
        "active_work": active_report,
    }
