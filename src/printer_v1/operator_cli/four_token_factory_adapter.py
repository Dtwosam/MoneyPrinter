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
from typing import Any

from printer_v1.operator_cli.campaign_full_run_accounting import (
    OperationalLifecycleOwnershipContext,
)
from printer_v1.operator_cli.four_token_proof_integration import (
    FOUR_TOKEN_PROOF_MIN_SPACING_SECONDS,
    resolve_owned_cycle_for_scheduler_job,
)
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
