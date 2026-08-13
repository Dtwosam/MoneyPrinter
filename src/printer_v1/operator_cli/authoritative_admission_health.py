"""Proof-only read-side owners for four-token admission health.

This module projects existing budget, Scheduler, supervision, database, and
provider facts.  It never reserves work, executes a source, mutates SQLite, or
admits another cycle.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
import sqlite3
from typing import Any, Mapping

from printer_v1.operator_cli import one_command_15m_factory as factory
from printer_v1.operator_cli.campaign_active_work import (
    ACTIVE_WORK_STATES,
    campaign_active_work_report,
    campaign_scoped_job_ids,
)
from printer_v1.operator_cli.multi_cycle_campaign_coordinator import (
    MultiCycleAdmissionHealth,
    MultiCycleCampaignBinding,
)
from printer_v1.operator_cli.multi_cycle_memory_growth import (
    scaled_standard_four_hour_capacity_contract,
)
from printer_v1.operator_cli.campaign_supervision import (
    CampaignSupervisionError,
    inspect_campaign_supervision,
)
from printer_v1.operator_cli.operational_database_target_binding import (
    OperationalDatabaseTargetBinding,
    validate_operational_database_target_binding,
)
from printer_v1.operator_cli.operational_standard_4h import (
    standard_four_hour_capacity_contract,
)
from printer_v1.operator_cli.one_token_4h_runtime import require_projected_capacity
from printer_v1.operator_cli.proof_db_schema_readiness import (
    validate_runtime_schema_connection,
)
from printer_v1.operator_cli.source_free_discovery_capacity import (
    LaterCycleDiscoveryAttemptManifest,
)
from printer_v1.operator_cli.source_free_discovery_provider_capacity import (
    compose_later_cycle_discovery_capacity,
)


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


@dataclass(frozen=True)
class OperationalHealthProjection:
    campaign_supervision_healthy: bool
    lease_healthy: bool
    db_healthy: bool
    shared_terminal_condition: bool
    cancellation_requested: bool
    lease_expires_at: datetime | None
    recheck_on_lifecycle_change: bool
    reasons: tuple[str, ...]


@dataclass(frozen=True)
class AdmissionHealthFieldEvidence:
    field: str
    value: bool
    owner: str
    reason: str
    details: tuple[tuple[str, str], ...] = ()


@dataclass(frozen=True)
class AdmissionHealthProjection:
    health: MultiCycleAdmissionHealth
    recheck_at: datetime | None
    recheck_on_lifecycle_change: bool
    evidence: tuple[AdmissionHealthFieldEvidence, ...]
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


def _aware_utc(value: object) -> datetime:
    parsed = datetime.fromisoformat(str(value))
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ValueError("timestamp must be timezone-aware")
    return parsed.astimezone(timezone.utc)


def _connection_path(connection: sqlite3.Connection) -> Path | None:
    rows = connection.execute("PRAGMA database_list").fetchall()
    main = [row for row in rows if str(row[1]) == "main"]
    if len(main) != 1 or not str(main[0][2]):
        return None
    return Path(str(main[0][2])).resolve()


def project_operational_health(
    connection: sqlite3.Connection,
    *,
    db_path: str | Path,
    binding: MultiCycleCampaignBinding,
    first_cycle_id: str,
    operational_db_binding: OperationalDatabaseTargetBinding | None,
    operational_db_expected: Mapping[str, Any],
    canonical_authoritative_db_path: str | Path,
    supervision_id: str,
    supervision_owner_id: str,
    now: datetime,
) -> OperationalHealthProjection:
    """Read schema/binding, supervision, lease, cancellation, and terminal facts."""
    reasons: list[str] = []
    resolved_path = Path(db_path).resolve()
    instant = _aware_utc(now)

    graph = None
    report: Mapping[str, Any] | None = None
    try:
        graph = connection.execute(
            """SELECT c.campaign_state,c.db_target_identity,
                      r.run_state,r.authoritative_run_id,
                      cy.cycle_state,f.run_status
               FROM printer_memory_factory_campaigns AS c
               JOIN printer_memory_factory_campaign_configurations AS cfg
                 ON cfg.campaign_id=c.campaign_id AND cfg.configuration_id=?
               JOIN printer_memory_factory_campaign_runs AS r
                 ON r.campaign_id=c.campaign_id AND r.run_id=?
               JOIN printer_memory_factory_campaign_cycles AS cy
                 ON cy.campaign_id=c.campaign_id AND cy.run_id=r.run_id
                AND cy.cycle_id=? AND cy.cycle_ordinal=1
               JOIN printer_memory_factory_runs AS f
                 ON f.run_id=r.authoritative_run_id
               WHERE c.campaign_id=? AND r.authoritative_run_id=?""",
            (
                binding.configuration_id,
                binding.campaign_run_id,
                first_cycle_id,
                binding.campaign_id,
                binding.authoritative_factory_run_id,
            ),
        ).fetchone()
        report = campaign_active_work_report(
            connection,
            factory_run_id=binding.authoritative_factory_run_id,
            campaign_id=binding.campaign_id,
            run_id=binding.campaign_run_id,
            cycle_id=first_cycle_id,
        )
    except (sqlite3.Error, TypeError, ValueError, KeyError):
        graph = None
    if graph is None or report is None:
        reasons.append("CAMPAIGN_OWNERSHIP_EVIDENCE_INCOMPLETE")

    db_healthy = True
    try:
        mismatch = validate_operational_database_target_binding(
            operational_db_binding,
            actual_db_path=resolved_path,
            canonical_authoritative_db_path=canonical_authoritative_db_path,
            expected=operational_db_expected,
        )
        if mismatch is not None:
            db_healthy = False
            reasons.append(mismatch)
        schema = validate_runtime_schema_connection(
            connection,
            raise_on_error=False,
        )
        if schema.get("runtime_ready") is not True:
            db_healthy = False
            reasons.append("RUNTIME_SCHEMA_NOT_READY")
        if _connection_path(connection) != resolved_path:
            db_healthy = False
            reasons.append("OPERATIONAL_DB_CONNECTION_PATH_MISMATCH")
        if (
            graph is None
            or operational_db_binding is None
            or str(graph["db_target_identity"])
            != operational_db_binding.db_target_identity
        ):
            db_healthy = False
            reasons.append("DURABLE_DB_TARGET_IDENTITY_MISMATCH")
    except (sqlite3.Error, TypeError, ValueError, KeyError, OSError):
        db_healthy = False
        reasons.append("OPERATIONAL_DB_EVIDENCE_INCOMPLETE")

    supervision: Mapping[str, Any] | None = None
    try:
        supervision = inspect_campaign_supervision(
            resolved_path,
            supervision_id=supervision_id,
            campaign_id=binding.campaign_id,
            configuration_id=binding.configuration_id,
            run_id=binding.campaign_run_id,
            owner_id=supervision_owner_id,
            now=instant,
        )
    except (CampaignSupervisionError, sqlite3.Error, OSError, ValueError):
        reasons.append("CAMPAIGN_SUPERVISION_EVIDENCE_INCOMPLETE")

    campaign_supervision_healthy = False
    lease_healthy = False
    lease_expires_at: datetime | None = None
    supervision_cancelled = True
    supervision_terminal = True
    if supervision is not None:
        state = str(supervision.get("supervision_state") or "")
        campaign_supervision_healthy = (
            supervision.get("read_only") is True
            and state in {"ACTIVE", "STOPPING"}
        )
        try:
            lease_expires_at = _aware_utc(supervision.get("lease_expires_at"))
        except (TypeError, ValueError):
            reasons.append("CAMPAIGN_LEASE_TIMESTAMP_INCOMPLETE")
        lease_healthy = (
            campaign_supervision_healthy
            and supervision.get("lease_expired") is False
            and lease_expires_at is not None
        )
        supervision_cancelled = (
            supervision.get("cancellation_requested_at") is not None
            or state == "STOPPING"
        )
        supervision_terminal = state == "TERMINAL"
        if not campaign_supervision_healthy:
            reasons.append("CAMPAIGN_SUPERVISION_NOT_ACTIVE_OR_STOPPING")
        if not lease_healthy:
            reasons.append(
                "CAMPAIGN_LEASE_EXPIRED"
                if supervision.get("lease_expired") is True
                else "CAMPAIGN_LEASE_EVIDENCE_INCOMPLETE"
            )

    graph_cancelled = True
    shared_terminal_condition = True
    if graph is not None:
        campaign_state = str(graph["campaign_state"])
        run_state = str(graph["run_state"])
        cycle_state = str(graph["cycle_state"])
        factory_state = str(graph["run_status"])
        graph_cancelled = (
            campaign_state == "STOP_REQUESTED" or run_state == "STOP_REQUESTED"
        )
        explicit_terminal = (
            campaign_state.startswith("TERMINAL_")
            or run_state.startswith("TERMINAL_")
            or cycle_state.startswith("TERMINAL_")
            or factory_state in {"COMPLETED", "FAILED", "SAFE_STOPPED"}
            or supervision_terminal
        )
        non_running_block = (
            campaign_state not in {"RUNNING", "STOP_REQUESTED"}
            or run_state not in {"RUNNING", "STOP_REQUESTED"}
            or factory_state != "RUNNING"
        )
        shared_terminal_condition = explicit_terminal or non_running_block
        if shared_terminal_condition:
            reasons.append("PERSISTED_SHARED_TERMINAL_STATE")
            if report is not None and report.get("clean_terminal") is not True:
                reasons.append("TERMINAL_ACTIVE_WORK_DRIFT")

    cancellation_requested = supervision_cancelled or graph_cancelled
    recheck_on_lifecycle_change = any(
        (
            not campaign_supervision_healthy,
            not lease_healthy,
            not db_healthy,
            shared_terminal_condition,
            cancellation_requested,
        )
    )
    return OperationalHealthProjection(
        campaign_supervision_healthy=campaign_supervision_healthy,
        lease_healthy=lease_healthy,
        db_healthy=db_healthy,
        shared_terminal_condition=shared_terminal_condition,
        cancellation_requested=cancellation_requested,
        lease_expires_at=lease_expires_at,
        recheck_on_lifecycle_change=recheck_on_lifecycle_change,
        reasons=tuple(dict.fromkeys(reasons)),
    )


def _evidence(
    *,
    field: str,
    value: bool,
    owner: str,
    reasons: tuple[str, ...],
    details: tuple[tuple[str, str], ...] = (),
) -> AdmissionHealthFieldEvidence:
    return AdmissionHealthFieldEvidence(
        field=field,
        value=value,
        owner=owner,
        reason=";".join(reasons) if reasons else "OWNER_EVIDENCE_HEALTHY",
        details=details,
    )


def project_authoritative_admission_health(
    connection: sqlite3.Connection,
    *,
    db_path: str | Path,
    binding: MultiCycleCampaignBinding,
    first_cycle_id: str,
    operational_db_binding: OperationalDatabaseTargetBinding | None,
    operational_db_expected: Mapping[str, Any],
    canonical_authoritative_db_path: str | Path,
    supervision_id: str,
    supervision_owner_id: str,
    discovery_manifest: LaterCycleDiscoveryAttemptManifest,
    now: datetime,
) -> AdmissionHealthProjection:
    """Compose all twelve admission fields without executing any capability."""
    budget = project_lifecycle_budget_reserve(
        connection,
        factory_run_id=binding.authoritative_factory_run_id,
    )
    scheduler = project_scheduler_health(
        connection,
        binding=binding,
        first_cycle_id=first_cycle_id,
    )
    operational = project_operational_health(
        connection,
        db_path=db_path,
        binding=binding,
        first_cycle_id=first_cycle_id,
        operational_db_binding=operational_db_binding,
        operational_db_expected=operational_db_expected,
        canonical_authoritative_db_path=canonical_authoritative_db_path,
        supervision_id=supervision_id,
        supervision_owner_id=supervision_owner_id,
        now=now,
    )

    provider_reasons: tuple[str, ...]
    provider_recheck_at: datetime | None
    try:
        discovery = compose_later_cycle_discovery_capacity(
            connection,
            manifest=discovery_manifest,
            now=_aware_utc(now),
        )
        provider_budgets_available = discovery.provider_budgets_available
        discovery_capacity_available = discovery.discovery_capacity_available
        provider_recheck_at = discovery.recheck_at
        provider_reasons = tuple(discovery.reasons)
    except (AttributeError, KeyError, TypeError, ValueError):
        provider_budgets_available = False
        discovery_capacity_available = False
        provider_recheck_at = None
        provider_reasons = ("DISCOVERY_CAPACITY_EVIDENCE_INCOMPLETE",)

    health = MultiCycleAdmissionHealth(
        source_budget_available=budget.source_budget_available,
        provider_budgets_available=provider_budgets_available,
        scheduler_budget_available=scheduler.scheduler_budget_available,
        scheduler_due_work_healthy=scheduler.scheduler_due_work_healthy,
        close_reserve_available=budget.close_reserve_available,
        campaign_supervision_healthy=(
            operational.campaign_supervision_healthy
        ),
        lease_healthy=operational.lease_healthy,
        db_healthy=operational.db_healthy,
        shared_terminal_condition=operational.shared_terminal_condition,
        cancellation_requested=operational.cancellation_requested,
        discovery_capacity_available=discovery_capacity_available,
        protected_work_capacity_available=(
            budget.protected_work_capacity_available
        ),
    )

    budget_details = (
        ("cycle_one_consumed_requests", str(budget.cycle_one_consumed_requests)),
        ("cycle_one_request_ceiling", str(budget.cycle_one_request_ceiling)),
        ("four_token_request_ceiling", str(budget.four_token_request_ceiling)),
    )
    scheduler_details = (
        ("attributable_job_count", str(scheduler.attributable_job_count)),
        ("cycle_one_scheduler_ceiling", str(scheduler.cycle_one_scheduler_ceiling)),
        ("four_token_scheduler_ceiling", str(scheduler.four_token_scheduler_ceiling)),
    )
    provider_details = (
        ("recheck_at", str(provider_recheck_at)),
        ("manifest_target_count", str(getattr(discovery_manifest, "target_count", None))),
    )
    operational_details = (
        ("lease_expires_at", str(operational.lease_expires_at)),
        ("first_cycle_id", str(first_cycle_id)),
    )
    evidence = (
        _evidence(
            field="source_budget_available",
            value=health.source_budget_available,
            owner=(
                "standard_campaign_lifecycle_budget/"
                "standard_four_hour_capacity_contract/"
                "one_command_15m_factory._run_request_count"
            ),
            reasons=budget.reasons,
            details=budget_details,
        ),
        _evidence(
            field="provider_budgets_available",
            value=health.provider_budgets_available,
            owner=(
                "source_free_discovery_provider_capacity."
                "compose_later_cycle_discovery_capacity"
            ),
            reasons=provider_reasons,
            details=provider_details,
        ),
        _evidence(
            field="scheduler_budget_available",
            value=health.scheduler_budget_available,
            owner=(
                "campaign_active_work.campaign_scoped_job_ids/"
                "scaled_standard_four_hour_capacity_contract"
            ),
            reasons=scheduler.reasons,
            details=scheduler_details,
        ),
        _evidence(
            field="scheduler_due_work_healthy",
            value=health.scheduler_due_work_healthy,
            owner="Central Scheduler rows/campaign_active_work_report",
            reasons=scheduler.reasons,
            details=scheduler_details,
        ),
        _evidence(
            field="close_reserve_available",
            value=health.close_reserve_available,
            owner=(
                "one_command_15m_factory._projected_requests_for_step/"
                "_lifecycle_reservation_records_for_step/"
                "_enforce_budgets_before_step"
            ),
            reasons=budget.reasons,
            details=budget_details,
        ),
        _evidence(
            field="campaign_supervision_healthy",
            value=health.campaign_supervision_healthy,
            owner="campaign_supervision.inspect_campaign_supervision",
            reasons=operational.reasons,
            details=operational_details,
        ),
        _evidence(
            field="lease_healthy",
            value=health.lease_healthy,
            owner="campaign_supervision.inspect_campaign_supervision",
            reasons=operational.reasons,
            details=operational_details,
        ),
        _evidence(
            field="db_healthy",
            value=health.db_healthy,
            owner=(
                "operational_database_target_binding/"
                "proof_db_schema_readiness.validate_runtime_schema_connection"
            ),
            reasons=operational.reasons,
            details=operational_details,
        ),
        _evidence(
            field="shared_terminal_condition",
            value=health.shared_terminal_condition,
            owner="persisted campaign/run/cycle/factory state/campaign_active_work_report",
            reasons=operational.reasons,
            details=operational_details,
        ),
        _evidence(
            field="cancellation_requested",
            value=health.cancellation_requested,
            owner="campaign supervision and campaign/run STOP_REQUESTED state",
            reasons=operational.reasons,
            details=operational_details,
        ),
        _evidence(
            field="discovery_capacity_available",
            value=health.discovery_capacity_available,
            owner=(
                "source_free_discovery_provider_capacity."
                "compose_later_cycle_discovery_capacity"
            ),
            reasons=provider_reasons,
            details=provider_details,
        ),
        _evidence(
            field="protected_work_capacity_available",
            value=health.protected_work_capacity_available,
            owner=(
                "one_command_15m_factory lifecycle reservation/"
                "standard_campaign_lifecycle_budget"
            ),
            reasons=budget.reasons,
            details=budget_details,
        ),
    )
    positive_fields = (
        health.source_budget_available,
        health.provider_budgets_available,
        health.scheduler_budget_available,
        health.scheduler_due_work_healthy,
        health.close_reserve_available,
        health.campaign_supervision_healthy,
        health.lease_healthy,
        health.db_healthy,
        health.discovery_capacity_available,
        health.protected_work_capacity_available,
    )
    blocked = (
        not all(positive_fields)
        or health.shared_terminal_condition
        or health.cancellation_requested
    )
    recheck_on_lifecycle_change = (
        budget.recheck_on_lifecycle_change
        or scheduler.recheck_on_lifecycle_change
        or operational.recheck_on_lifecycle_change
        or (blocked and provider_recheck_at is None)
    )
    reasons = tuple(
        dict.fromkeys(
            (*budget.reasons, *scheduler.reasons, *operational.reasons, *provider_reasons)
        )
    )
    return AdmissionHealthProjection(
        health=health,
        recheck_at=provider_recheck_at,
        recheck_on_lifecycle_change=recheck_on_lifecycle_change,
        evidence=evidence,
        reasons=reasons,
    )


__all__ = [
    "AdmissionHealthFieldEvidence",
    "AdmissionHealthProjection",
    "LifecycleBudgetReserveProjection",
    "OperationalHealthProjection",
    "SchedulerHealthProjection",
    "project_lifecycle_budget_reserve",
    "project_operational_health",
    "project_authoritative_admission_health",
    "project_scheduler_health",
]
