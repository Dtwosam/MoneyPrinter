"""Proof-only read-side owners for four-token admission health.

This module projects existing budget, Scheduler, supervision, database, and
provider facts.  It never reserves work, executes a source, mutates SQLite, or
admits another cycle.
"""

from __future__ import annotations

from dataclasses import dataclass
import sqlite3

from printer_v1.operator_cli import one_command_15m_factory as factory
from printer_v1.operator_cli.multi_cycle_memory_growth import (
    scaled_standard_four_hour_capacity_contract,
)
from printer_v1.operator_cli.operational_standard_4h import (
    standard_four_hour_capacity_contract,
)
from printer_v1.operator_cli.one_token_4h_runtime import require_projected_capacity


@dataclass(frozen=True)
class LifecycleBudgetReserveProjection:
    source_budget_available: bool
    close_reserve_available: bool
    protected_work_capacity_available: bool
    cycle_one_consumed_requests: int | None
    cycle_one_request_ceiling: int
    second_cycle_request_envelope: int
    four_token_request_ceiling: int
    close_reserved_requests: int | None
    protected_reserved_requests: int | None
    recheck_on_lifecycle_change: bool
    reasons: tuple[str, ...]


_LIFECYCLE_STEP_KINDS = frozenset(
    {
        "SNAPSHOT",
        "WINDOW_CLOSE",
        "CONTINUATION_SNAPSHOT",
        "CONTINUATION_CLOSE",
        "LONG_CONTINUATION_SNAPSHOT",
        "LONG_CONTINUATION_CLOSE",
    }
)
_CLOSE_STEP_KINDS = frozenset(
    {"WINDOW_CLOSE", "CONTINUATION_CLOSE", "LONG_CONTINUATION_CLOSE"}
)


def _fits(*, current: int, projected: int, ceiling: int, label: str) -> bool:
    try:
        require_projected_capacity(
            current=current,
            projected=projected,
            ceiling=ceiling,
            label=label,
        )
    except ValueError:
        return False
    return True


def project_lifecycle_budget_reserve(
    connection: sqlite3.Connection,
    *,
    factory_run_id: str,
) -> LifecycleBudgetReserveProjection:
    """Forecast cycle-one and owed-work capacity from factory-owned arithmetic."""
    base = standard_four_hour_capacity_contract()
    scaled = scaled_standard_four_hour_capacity_contract(4)
    cycle_one_ceiling = int(base["lifecycle_request_outer_ceiling"])
    second_cycle_envelope = int(base["lifecycle_request_outer_ceiling"])
    four_token_ceiling = int(scaled["lifecycle_request_outer_ceiling"])
    reasons: list[str] = []

    try:
        run_consumed = factory._run_request_count(connection, factory_run_id)
        cycle_one_consumed = int(base["shared_discovery_requests"]) + run_consumed
        rows = connection.execute(
            """SELECT * FROM printer_memory_factory_run_steps
               WHERE run_id=? AND step_status IN ('PENDING','RUNNING')
               ORDER BY id""",
            (factory_run_id,),
        ).fetchall()
    except (sqlite3.Error, TypeError, ValueError):
        return LifecycleBudgetReserveProjection(
            source_budget_available=False,
            close_reserve_available=False,
            protected_work_capacity_available=False,
            cycle_one_consumed_requests=None,
            cycle_one_request_ceiling=cycle_one_ceiling,
            second_cycle_request_envelope=second_cycle_envelope,
            four_token_request_ceiling=four_token_ceiling,
            close_reserved_requests=None,
            protected_reserved_requests=None,
            recheck_on_lifecycle_change=True,
            reasons=("LIFECYCLE_BUDGET_EVIDENCE_INCOMPLETE",),
        )

    source_budget_available = _fits(
        current=cycle_one_consumed,
        projected=0,
        ceiling=cycle_one_ceiling,
        label="cycle-one lifecycle request",
    ) and _fits(
        current=cycle_one_consumed,
        projected=second_cycle_envelope,
        ceiling=four_token_ceiling,
        label="four-token lifecycle request",
    )
    if not source_budget_available:
        reasons.append("CYCLE_ONE_SOURCE_ENVELOPE_EXCEEDED")

    close_reserved = 0
    protected_reserved = 0
    reservation_complete = True
    close_execution_guard_healthy = True
    protected_execution_guard_healthy = True
    for pending in rows:
        step_kind = str(pending["step_kind"])
        if step_kind not in _LIFECYCLE_STEP_KINDS:
            continue
        try:
            projected = factory._projected_requests_for_step(pending)
            records = factory._lifecycle_reservation_records_for_step(
                run_id=factory_run_id,
                pending=pending,
                projected_requests=projected,
            )
            if len(records) != projected:
                raise ValueError("lifecycle reservation cardinality mismatch")
        except (sqlite3.Error, TypeError, ValueError, KeyError):
            reservation_complete = False
            continue

        protected_reserved += projected
        if step_kind in _CLOSE_STEP_KINDS:
            close_reserved += projected
        try:
            factory._enforce_budgets_before_step(
                connection,
                factory_run_id,
                pending,
            )
        except factory._GlobalStop:
            protected_execution_guard_healthy = False
            if step_kind in _CLOSE_STEP_KINDS:
                close_execution_guard_healthy = False

    if not reservation_complete:
        reasons.append("LIFECYCLE_RESERVATION_EVIDENCE_INCOMPLETE")
    if not protected_execution_guard_healthy:
        reasons.append("FACTORY_EXECUTION_BUDGET_GUARD_BLOCKED")

    close_reserve_available = reservation_complete and close_execution_guard_healthy and _fits(
        current=cycle_one_consumed,
        projected=close_reserved,
        ceiling=cycle_one_ceiling,
        label="cycle-one close reserve",
    )
    protected_work_capacity_available = (
        reservation_complete and protected_execution_guard_healthy and _fits(
        current=cycle_one_consumed,
        projected=protected_reserved,
        ceiling=cycle_one_ceiling,
        label="cycle-one protected lifecycle reserve",
        )
    )
    if not close_reserve_available:
        reasons.append("CLOSE_RESERVE_UNAVAILABLE")
    if not protected_work_capacity_available:
        reasons.append("PROTECTED_WORK_CAPACITY_UNAVAILABLE")

    return LifecycleBudgetReserveProjection(
        source_budget_available=source_budget_available,
        close_reserve_available=close_reserve_available,
        protected_work_capacity_available=protected_work_capacity_available,
        cycle_one_consumed_requests=cycle_one_consumed,
        cycle_one_request_ceiling=cycle_one_ceiling,
        second_cycle_request_envelope=second_cycle_envelope,
        four_token_request_ceiling=four_token_ceiling,
        close_reserved_requests=(close_reserved if reservation_complete else None),
        protected_reserved_requests=(
            protected_reserved if reservation_complete else None
        ),
        recheck_on_lifecycle_change=(
            not close_reserve_available or not protected_work_capacity_available
        ),
        reasons=tuple(dict.fromkeys(reasons)),
    )


__all__ = [
    "LifecycleBudgetReserveProjection",
    "project_lifecycle_budget_reserve",
]
