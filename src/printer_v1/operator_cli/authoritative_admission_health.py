"""Proof-only read-side owners for four-token admission health.

This module projects existing budget, Scheduler, supervision, database, and
provider facts.  It never reserves work, executes a source, mutates SQLite, or
admits another cycle.
"""

from __future__ import annotations

from dataclasses import dataclass
import sqlite3

from printer_v1.operator_cli import one_command_15m_factory as factory
from printer_v1.operator_cli.campaign_active_work import (
    ACTIVE_WORK_STATES,
    campaign_active_work_report,
    campaign_scoped_job_ids,
)
from printer_v1.operator_cli.multi_cycle_campaign_coordinator import (
    MultiCycleCampaignBinding,
)
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


@dataclass(frozen=True)
class SchedulerHealthProjection:
    scheduler_budget_available: bool
    scheduler_due_work_healthy: bool
    attributable_job_count: int | None
    attributable_job_ids: tuple[int, ...]
    cycle_one_scheduler_ceiling: int
    second_cycle_scheduler_envelope: int
    four_token_scheduler_ceiling: int
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

    close_reserve_available = (
        reservation_complete
        and close_execution_guard_healthy
        and _fits(
            current=cycle_one_consumed,
            projected=close_reserved,
            ceiling=cycle_one_ceiling,
            label="cycle-one close reserve",
        )
    )
    protected_work_capacity_available = (
        reservation_complete
        and protected_execution_guard_healthy
        and _fits(
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


def project_scheduler_health(
    connection: sqlite3.Connection,
    *,
    binding: MultiCycleCampaignBinding,
    first_cycle_id: str,
) -> SchedulerHealthProjection:
    """Project exact attributable Scheduler capacity and integrity read-only."""
    base = standard_four_hour_capacity_contract()
    scaled = scaled_standard_four_hour_capacity_contract(4)
    cycle_one_ceiling = int(base["lifecycle_scheduler_outer_ceiling"])
    second_cycle_envelope = int(base["lifecycle_scheduler_outer_ceiling"])
    four_token_ceiling = int(scaled["lifecycle_scheduler_outer_ceiling"])
    reasons: list[str] = []

    try:
        raw_step_rows = connection.execute(
            """SELECT step_status,scheduler_job_id
               FROM printer_memory_factory_run_steps
               WHERE run_id=? ORDER BY id""",
            (binding.authoritative_factory_run_id,),
        ).fetchall()
        raw_step_job_ids = {
            int(row["scheduler_job_id"])
            for row in raw_step_rows
            if row["scheduler_job_id"] is not None
        }
        if any(
            row["scheduler_job_id"] is None
            and str(row["step_status"]) in ACTIVE_WORK_STATES
            for row in raw_step_rows
        ):
            reasons.append("ORPHAN_FACTORY_RUN_STEP_SCHEDULER_JOB")

        groups = campaign_scoped_job_ids(
            connection,
            factory_run_id=binding.authoritative_factory_run_id,
            campaign_id=binding.campaign_id,
            run_id=binding.campaign_run_id,
            cycle_id=first_cycle_id,
            exact_scope=True,
        )
        attributable_ids = set().union(*groups.values()) if groups else set()
        if not raw_step_job_ids.issubset(attributable_ids):
            reasons.append("ORPHAN_FACTORY_RUN_STEP_SCHEDULER_JOB")

        if attributable_ids:
            placeholders = ",".join("?" for _ in attributable_ids)
            job_rows = connection.execute(
                f"""SELECT id,status,locked_at,lock_owner
                    FROM printer_scheduler_jobs
                    WHERE id IN ({placeholders}) ORDER BY id""",
                tuple(sorted(attributable_ids)),
            ).fetchall()
        else:
            job_rows = []
        if len(job_rows) != len(attributable_ids):
            reasons.append("ATTRIBUTABLE_SCHEDULER_JOB_MISSING")

        for row in job_rows:
            status = str(row["status"])
            locked_at = row["locked_at"]
            lock_owner = row["lock_owner"]
            complete_lock = locked_at is not None and lock_owner is not None
            empty_lock = locked_at is None and lock_owner is None
            if status == "RUNNING":
                if not complete_lock:
                    reasons.append("SCHEDULER_LOCK_STATUS_CONTRADICTION")
            elif not empty_lock:
                reasons.append("SCHEDULER_LOCK_STATUS_CONTRADICTION")
            if status not in {
                "PENDING",
                "RUNNING",
                "COOLDOWN",
                "SUCCEEDED",
                "FAILED",
                "SKIPPED",
                "CANCELLED",
            }:
                reasons.append("SCHEDULER_STATUS_UNRECOGNIZED")

        duplicate_rows = connection.execute(
            """SELECT scheduler_job_id
               FROM printer_memory_factory_campaign_scheduler_work
               WHERE campaign_id=? AND run_id=? AND cycle_id=?
                 AND ownership_contract_version='V2_STAGE_SCOPED'
                 AND scheduler_job_id IS NOT NULL
               GROUP BY scheduler_job_id HAVING COUNT(*) > 1""",
            (binding.campaign_id, binding.campaign_run_id, first_cycle_id),
        ).fetchall()
        if duplicate_rows:
            reasons.append("AMBIGUOUS_SCHEDULER_OWNERSHIP")

        terminal_work_active = int(
            connection.execute(
                """SELECT COUNT(*)
                   FROM printer_memory_factory_campaign_scheduler_work AS w
                   JOIN printer_scheduler_jobs AS j ON j.id=w.scheduler_job_id
                   WHERE w.campaign_id=? AND w.run_id=? AND w.cycle_id=?
                     AND w.ownership_contract_version='V2_STAGE_SCOPED'
                     AND w.work_state NOT IN ('PENDING','RUNNING','COOLDOWN')
                     AND (j.status IN ('PENDING','RUNNING','COOLDOWN')
                          OR j.locked_at IS NOT NULL OR j.lock_owner IS NOT NULL)""",
                (binding.campaign_id, binding.campaign_run_id, first_cycle_id),
            ).fetchone()[0]
        )
        if terminal_work_active:
            reasons.append("TERMINAL_WORK_ACTIVE_SCHEDULER_JOB")

        active_work_terminal = int(
            connection.execute(
                """SELECT COUNT(*)
                   FROM printer_memory_factory_campaign_scheduler_work AS w
                   JOIN printer_scheduler_jobs AS j ON j.id=w.scheduler_job_id
                   WHERE w.campaign_id=? AND w.run_id=? AND w.cycle_id=?
                     AND w.ownership_contract_version='V2_STAGE_SCOPED'
                     AND w.work_state IN ('PENDING','RUNNING','COOLDOWN')
                     AND j.status IN ('SUCCEEDED','FAILED','SKIPPED','CANCELLED')""",
                (binding.campaign_id, binding.campaign_run_id, first_cycle_id),
            ).fetchone()[0]
        )
        if active_work_terminal:
            reasons.append("ACTIVE_WORK_TERMINAL_SCHEDULER_JOB")

        report = campaign_active_work_report(
            connection,
            factory_run_id=binding.authoritative_factory_run_id,
            campaign_id=binding.campaign_id,
            run_id=binding.campaign_run_id,
            cycle_id=first_cycle_id,
        )
        if int(report["terminal_work_with_active_job"]):
            reasons.append("TERMINAL_WORK_ACTIVE_SCHEDULER_JOB")
    except (sqlite3.Error, TypeError, ValueError, KeyError):
        return SchedulerHealthProjection(
            scheduler_budget_available=False,
            scheduler_due_work_healthy=False,
            attributable_job_count=None,
            attributable_job_ids=(),
            cycle_one_scheduler_ceiling=cycle_one_ceiling,
            second_cycle_scheduler_envelope=second_cycle_envelope,
            four_token_scheduler_ceiling=four_token_ceiling,
            recheck_on_lifecycle_change=True,
            reasons=("SCHEDULER_EVIDENCE_INCOMPLETE",),
        )

    attributable_count = len(attributable_ids)
    scheduler_budget_available = _fits(
        current=attributable_count,
        projected=0,
        ceiling=cycle_one_ceiling,
        label="cycle-one Scheduler",
    ) and _fits(
        current=attributable_count,
        projected=second_cycle_envelope,
        ceiling=four_token_ceiling,
        label="four-token Scheduler",
    )
    if not scheduler_budget_available:
        reasons.append("CYCLE_ONE_SCHEDULER_ENVELOPE_EXCEEDED")

    integrity_reasons = {
        "ORPHAN_FACTORY_RUN_STEP_SCHEDULER_JOB",
        "ATTRIBUTABLE_SCHEDULER_JOB_MISSING",
        "SCHEDULER_LOCK_STATUS_CONTRADICTION",
        "SCHEDULER_STATUS_UNRECOGNIZED",
        "AMBIGUOUS_SCHEDULER_OWNERSHIP",
        "TERMINAL_WORK_ACTIVE_SCHEDULER_JOB",
        "ACTIVE_WORK_TERMINAL_SCHEDULER_JOB",
    }
    scheduler_due_work_healthy = not any(
        reason in integrity_reasons for reason in reasons
    )
    return SchedulerHealthProjection(
        scheduler_budget_available=scheduler_budget_available,
        scheduler_due_work_healthy=scheduler_due_work_healthy,
        attributable_job_count=attributable_count,
        attributable_job_ids=tuple(sorted(attributable_ids)),
        cycle_one_scheduler_ceiling=cycle_one_ceiling,
        second_cycle_scheduler_envelope=second_cycle_envelope,
        four_token_scheduler_ceiling=four_token_ceiling,
        recheck_on_lifecycle_change=(
            not scheduler_budget_available or not scheduler_due_work_healthy
        ),
        reasons=tuple(dict.fromkeys(reasons)),
    )


__all__ = [
    "LifecycleBudgetReserveProjection",
    "SchedulerHealthProjection",
    "project_lifecycle_budget_reserve",
    "project_scheduler_health",
]
