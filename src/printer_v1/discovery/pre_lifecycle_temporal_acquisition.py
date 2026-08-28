"""V2-9.8B persistent pre-lifecycle temporal acquisition contract.

Owns the shared vocabulary and durable ownership rows for bounded,
Scheduler-owned pre-lifecycle acquisition waits:

* the 2400-second bounded acquisition horizon;
* the nonterminal ``WAITING_FOR_ELIGIBLE_SUPPLY`` state;
* the categorical wait-eligibility predicate;
* persistence for ``printer_pre_lifecycle_discovery_refresh_waits``.

It deliberately owns no Scheduler call, provider request, timer or orchestration.
Enqueue/claim/terminalize belong to the pre-lifecycle temporal refresh owner;
provider work belongs to the Source Governor; delayed work belongs to the
Central Scheduler.

Locked: no scoring/ranking/confidence/weights, no retrieval/decisions/positions/
trades/audits/PnL, no retry/restart/resume/successor, no second authorization,
no independent polling/sleep/reconnect loop.
"""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Any, Mapping, Sequence

WAIT_TABLE = "printer_pre_lifecycle_discovery_refresh_waits"

# Four bounded acquisition opportunities are possible: campaign-start intake,
# then due refreshes at +600s, +1200s and +1800s. Strict due < deadline keeps
# +2400s outside the horizon.
PRE_LIFECYCLE_ACQUISITION_DURATION_SECONDS = 2400

WAITING_FOR_ELIGIBLE_SUPPLY = "WAITING_FOR_ELIGIBLE_SUPPLY"
CURRENT_UNIVERSE_EXHAUSTED_WAITING = "CURRENT_UNIVERSE_EXHAUSTED_WAITING"
CURRENT_UNIVERSE_EXHAUSTED_TERMINAL = "CURRENT_UNIVERSE_EXHAUSTED_TERMINAL"
PRE_LIFECYCLE_ACQUISITION_DURATION_EXHAUSTED = (
    "PRE_LIFECYCLE_ACQUISITION_DURATION_EXHAUSTED"
)
CURRENT_UNIVERSE_EXHAUSTION_REASONS = (
    "ALL_REACHABLE_CANDIDATES_EVALUATED",
    "NO_ADDITIONAL_UNIQUE_CANDIDATES_REACHABLE",
)

WAIT_STATES = ("WAITING", "CLAIMED", "SUCCEEDED", "FAILED", "CANCELLED")
ACTIVE_WAIT_STATES = ("WAITING", "CLAIMED")

REFRESH_COMPLETED = "REFRESH_COMPLETED"
NO_LAWFUL_REFRESH_WINDOW = "NO_LAWFUL_REFRESH_WINDOW"
ACQUISITION_DEADLINE_EXHAUSTED = "ACQUISITION_DEADLINE_EXHAUSTED"
SOURCE_BUDGET_EXHAUSTED = "SOURCE_BUDGET_EXHAUSTED"
REFRESH_SOURCE_FAILURE = "REFRESH_SOURCE_FAILURE"
INTERNAL_INVARIANT = "INTERNAL_INVARIANT"
INTERNAL_RUNTIME_ERROR = "INTERNAL_RUNTIME_ERROR"
CANCELLED = "CANCELLED"
SUPERVISION_FAILED = "SUPERVISION_FAILED"
UNSAFE_SCHEDULER_STATE = "UNSAFE_SCHEDULER_STATE"
ALREADY_PENDING_REFRESH = "ALREADY_PENDING_REFRESH"
CAPACITY_ALREADY_MET = "CAPACITY_ALREADY_MET"
UNIVERSE_NOT_EXHAUSTED = "UNIVERSE_NOT_EXHAUSTED"
NOT_ELIGIBLE = "NOT_ELIGIBLE"

TERMINAL_PRECEDENCE = (
    SUPERVISION_FAILED,
    CANCELLED,
    UNSAFE_SCHEDULER_STATE,
    INTERNAL_INVARIANT,
    INTERNAL_RUNTIME_ERROR,
    REFRESH_SOURCE_FAILURE,
    SOURCE_BUDGET_EXHAUSTED,
    ACQUISITION_DEADLINE_EXHAUSTED,
    NO_LAWFUL_REFRESH_WINDOW,
)


class PreLifecycleTemporalAcquisitionError(RuntimeError):
    """Fail-closed pre-lifecycle temporal-acquisition fault."""


def parse_iso(value: str) -> datetime:
    parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def iso(value: datetime) -> str:
    return value.astimezone(timezone.utc).isoformat()


def acquisition_deadline_at(
    started_at: str,
    *,
    acquisition_duration_seconds: int = PRE_LIFECYCLE_ACQUISITION_DURATION_SECONDS,
) -> str:
    """Bounded acquisition deadline, separate from the lifecycle deadline."""
    duration = int(acquisition_duration_seconds)
    if duration <= 0:
        raise PreLifecycleTemporalAcquisitionError(
            "INVALID_PRE_LIFECYCLE_ACQUISITION_DURATION"
        )
    return iso(parse_iso(started_at) + timedelta(seconds=duration))


def refresh_opportunity_at(
    acquisition_started_at: str,
    *,
    refresh_ordinal: int,
    refresh_interval_seconds: int = 600,
) -> str:
    """Return the non-drifting temporal opportunity anchored at attempt start."""
    ordinal = int(refresh_ordinal)
    interval = int(refresh_interval_seconds)
    if ordinal < 1 or interval <= 0:
        raise PreLifecycleTemporalAcquisitionError(
            "INVALID_PRE_LIFECYCLE_REFRESH_OPPORTUNITY"
        )
    return iso(
        parse_iso(acquisition_started_at)
        + timedelta(seconds=ordinal * interval)
    )


@dataclass(frozen=True)
class TemporalRefreshOutcome:
    """Result of one requested Scheduler-owned temporal refresh opportunity."""

    status: str
    wait_id: str | None = None
    scheduler_job_id: int | None = None
    refresh_ordinal: int = 0
    scheduled_for: str | None = None
    claimed: bool = False
    source_operations: int = 0
    provider_failures: int = 0
    channels_unavailable: tuple[str, ...] = ()
    channels_attempted: tuple[str, ...] = ()
    channels_skipped: tuple[Mapping[str, Any], ...] = ()
    newly_observed_exact_identities: tuple[Mapping[str, Any], ...] = ()
    promoted_observation_eligible: tuple[Mapping[str, Any], ...] = ()
    reserve_depth_before: int = 0
    reserve_depth_after: int = 0
    detail: str = ""
    failure_domain: str | None = None
    next_governed_request_kind: str | None = None
    next_governed_request_worst_case_seconds: float | None = None

    @property
    def waiting(self) -> bool:
        return self.status == WAITING_FOR_ELIGIBLE_SUPPLY

    @property
    def completed(self) -> bool:
        return self.status == REFRESH_COMPLETED

    def to_dict(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "wait_id": self.wait_id,
            "scheduler_job_id": self.scheduler_job_id,
            "refresh_ordinal": self.refresh_ordinal,
            "scheduled_for": self.scheduled_for,
            "claimed": self.claimed,
            "source_operations": self.source_operations,
            "provider_failures": self.provider_failures,
            "channels_unavailable": list(self.channels_unavailable),
            "channels_attempted": list(self.channels_attempted),
            "channels_skipped": [dict(item) for item in self.channels_skipped],
            "newly_observed_exact_identities": [
                dict(item) for item in self.newly_observed_exact_identities
            ],
            "newly_observed_exact_identity_count": len(
                self.newly_observed_exact_identities
            ),
            "promoted_observation_eligible_count": len(
                self.promoted_observation_eligible
            ),
            "reserve_depth_before": self.reserve_depth_before,
            "reserve_depth_after": self.reserve_depth_after,
            "detail": self.detail,
            "failure_domain": self.failure_domain,
            "next_governed_request_kind": self.next_governed_request_kind,
            "next_governed_request_worst_case_seconds": (
                self.next_governed_request_worst_case_seconds
            ),
        }


@dataclass
class AcquisitionLedger:
    """Cumulative, honest pre-lifecycle acquisition facts for the certificate."""

    started_at: str
    acquisition_deadline_at: str
    acquisition_duration_seconds: int
    refresh_interval_seconds: int
    opportunities_scheduled: int = 0
    opportunities_claimed: int = 0
    opportunities_completed: int = 0
    opportunities_cancelled: int = 0
    waiting_states_entered: int = 0
    reserve_depth_transitions: list[dict[str, Any]] = field(default_factory=list)
    revalidation_outcomes: list[dict[str, Any]] = field(default_factory=list)
    outcomes: list[dict[str, Any]] = field(default_factory=list)
    final_current_universe_state: str = CURRENT_UNIVERSE_EXHAUSTED_TERMINAL
    controlling_shortage_classification: str | None = None

    def record(self, outcome: TemporalRefreshOutcome) -> None:
        self.outcomes.append(outcome.to_dict())
        if outcome.scheduler_job_id is not None:
            self.opportunities_scheduled += 1
        if outcome.claimed:
            self.opportunities_claimed += 1
        if outcome.status == REFRESH_COMPLETED:
            self.opportunities_completed += 1
            self.reserve_depth_transitions.append(
                {
                    "refresh_ordinal": outcome.refresh_ordinal,
                    "reserve_depth_before": outcome.reserve_depth_before,
                    "reserve_depth_after": outcome.reserve_depth_after,
                }
            )
        if outcome.status == CANCELLED:
            self.opportunities_cancelled += 1
        if outcome.status == WAITING_FOR_ELIGIBLE_SUPPLY:
            self.waiting_states_entered += 1
            self.final_current_universe_state = CURRENT_UNIVERSE_EXHAUSTED_WAITING

    def elapsed_seconds(self, now: str) -> float:
        return (parse_iso(now) - parse_iso(self.started_at)).total_seconds()

    def remaining_seconds(self, now: str) -> float:
        return (
            parse_iso(self.acquisition_deadline_at) - parse_iso(now)
        ).total_seconds()

    def to_dict(self, *, now: str) -> dict[str, Any]:
        return {
            "acquisition_started_at": self.started_at,
            "acquisition_deadline_at": self.acquisition_deadline_at,
            "acquisition_duration_seconds": self.acquisition_duration_seconds,
            "refresh_interval_seconds": self.refresh_interval_seconds,
            "acquisition_elapsed_seconds": self.elapsed_seconds(now),
            "acquisition_remaining_seconds": self.remaining_seconds(now),
            "temporal_refresh_opportunities_scheduled": self.opportunities_scheduled,
            "temporal_refresh_opportunities_claimed": self.opportunities_claimed,
            "temporal_refresh_opportunities_completed": self.opportunities_completed,
            "temporal_refresh_opportunities_cancelled": self.opportunities_cancelled,
            "waiting_states_entered": self.waiting_states_entered,
            "eligible_reserve_depth_transitions": [
                dict(item) for item in self.reserve_depth_transitions
            ],
            "candidate_revalidation_outcomes": [
                dict(item) for item in self.revalidation_outcomes
            ],
            "temporal_refresh_outcomes": [dict(item) for item in self.outcomes],
            "final_current_universe_state": self.final_current_universe_state,
            "controlling_shortage_classification": self.controlling_shortage_classification,
        }


@dataclass(frozen=True)
class WaitEligibility:
    eligible: bool
    reason: str


def evaluate_wait_eligibility(
    *,
    reserve_depth: int,
    required_capacity: int,
    universe_state: str,
    now: str,
    acquisition_deadline_at: str,
    source_operations_remaining: int,
    provider_terminal_failure: bool,
    supervision_active: bool,
    cancellation_requested: bool,
    pending_refresh_exists: bool,
) -> WaitEligibility:
    """Categorical, fail-closed eligibility to enter the waiting state."""
    if int(reserve_depth) >= int(required_capacity):
        return WaitEligibility(False, CAPACITY_ALREADY_MET)
    if str(universe_state) not in CURRENT_UNIVERSE_EXHAUSTION_REASONS:
        return WaitEligibility(False, UNIVERSE_NOT_EXHAUSTED)
    if not supervision_active:
        return WaitEligibility(False, SUPERVISION_FAILED)
    if cancellation_requested:
        return WaitEligibility(False, CANCELLED)
    if provider_terminal_failure:
        return WaitEligibility(False, REFRESH_SOURCE_FAILURE)
    if int(source_operations_remaining) <= 0:
        return WaitEligibility(False, SOURCE_BUDGET_EXHAUSTED)
    if (parse_iso(acquisition_deadline_at) - parse_iso(now)).total_seconds() <= 0:
        return WaitEligibility(False, ACQUISITION_DEADLINE_EXHAUSTED)
    if pending_refresh_exists:
        return WaitEligibility(False, ALREADY_PENDING_REFRESH)
    return WaitEligibility(True, WAITING_FOR_ELIGIBLE_SUPPLY)


def refresh_window_fits(
    *,
    now: str,
    acquisition_deadline_at: str,
    refresh_interval_seconds: int,
) -> bool:
    """Whether the next normal refresh is strictly before the acquisition deadline."""
    due = parse_iso(now) + timedelta(seconds=int(refresh_interval_seconds))
    return due < parse_iso(acquisition_deadline_at)


def wait_table_exists(connection: sqlite3.Connection) -> bool:
    return (
        connection.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?",
            (WAIT_TABLE,),
        ).fetchone()
        is not None
    )


def _require_table(connection: sqlite3.Connection) -> None:
    if not wait_table_exists(connection):
        raise PreLifecycleTemporalAcquisitionError(
            "PRE_LIFECYCLE_REFRESH_WAIT_TABLE_MISSING"
        )


def next_refresh_ordinal(
    connection: sqlite3.Connection,
    *,
    campaign_id: str,
    run_id: str,
    cycle_id: str,
) -> int:
    _require_table(connection)
    row = connection.execute(
        f"SELECT COALESCE(MAX(refresh_ordinal), 0) FROM {WAIT_TABLE} "
        "WHERE campaign_id=? AND run_id=? AND cycle_id=?",
        (campaign_id, run_id, cycle_id),
    ).fetchone()
    return int(row[0]) + 1


def active_refresh_waits(
    connection: sqlite3.Connection,
    *,
    campaign_id: str,
    run_id: str,
    cycle_id: str,
) -> list[sqlite3.Row]:
    """Every non-terminal wait row for the exact campaign/run/cycle."""
    if not wait_table_exists(connection):
        return []
    previous = connection.row_factory
    connection.row_factory = sqlite3.Row
    try:
        placeholders = ",".join("?" * len(ACTIVE_WAIT_STATES))
        return list(
            connection.execute(
                f"SELECT * FROM {WAIT_TABLE} "
                "WHERE campaign_id=? AND run_id=? AND cycle_id=? "
                f"AND wait_state IN ({placeholders}) ORDER BY refresh_ordinal",
                (campaign_id, run_id, cycle_id, *ACTIVE_WAIT_STATES),
            ).fetchall()
        )
    finally:
        connection.row_factory = previous


def insert_refresh_wait(
    connection: sqlite3.Connection,
    *,
    wait_id: str,
    campaign_id: str,
    run_id: str,
    cycle_id: str,
    supervision_id: str,
    scheduler_job_id: int,
    refresh_ordinal: int,
    scheduled_for: str,
    acquisition_deadline_at: str,
    now: str,
) -> None:
    """Persist one WAITING ownership row bound to one exact Scheduler job."""
    _require_table(connection)
    for label, value in (
        ("wait_id", wait_id),
        ("campaign_id", campaign_id),
        ("run_id", run_id),
        ("cycle_id", cycle_id),
        ("supervision_id", supervision_id),
    ):
        if not str(value or "").strip():
            raise PreLifecycleTemporalAcquisitionError(
                f"MISSING_PRE_LIFECYCLE_REFRESH_WAIT_{label.upper()}"
            )
    if int(refresh_ordinal) < 1:
        raise PreLifecycleTemporalAcquisitionError("INVALID_REFRESH_ORDINAL")
    connection.execute(
        f"""INSERT INTO {WAIT_TABLE}(
            wait_id, campaign_id, run_id, cycle_id, supervision_id,
            scheduler_job_id, refresh_ordinal, wait_state, scheduled_for,
            acquisition_deadline_at, created_at, updated_at
        ) VALUES (?,?,?,?,?,?,?,'WAITING',?,?,?,?)""",
        (
            wait_id,
            campaign_id,
            run_id,
            cycle_id,
            supervision_id,
            int(scheduler_job_id),
            int(refresh_ordinal),
            scheduled_for,
            acquisition_deadline_at,
            now,
            now,
        ),
    )


def mark_refresh_wait_claimed(
    connection: sqlite3.Connection, *, wait_id: str, now: str
) -> None:
    _require_table(connection)
    connection.execute(
        f"UPDATE {WAIT_TABLE} SET wait_state='CLAIMED', updated_at=? "
        "WHERE wait_id=? AND wait_state='WAITING'",
        (now, wait_id),
    )


def terminalize_refresh_wait(
    connection: sqlite3.Connection,
    *,
    wait_id: str,
    wait_state: str,
    first_terminal_cause: str,
    now: str,
) -> None:
    _require_table(connection)
    if wait_state not in ("SUCCEEDED", "FAILED", "CANCELLED"):
        raise PreLifecycleTemporalAcquisitionError("INVALID_TERMINAL_WAIT_STATE")
    if not str(first_terminal_cause or "").strip():
        raise PreLifecycleTemporalAcquisitionError("MISSING_FIRST_TERMINAL_CAUSE")
    connection.execute(
        f"""UPDATE {WAIT_TABLE}
               SET wait_state=?, first_terminal_cause=?, terminal_at=?,
                   updated_at=?
             WHERE wait_id=? AND wait_state IN ('WAITING','CLAIMED')""",
        (wait_state, first_terminal_cause, now, now, wait_id),
    )


def controlling_terminal(statuses: Sequence[str]) -> str | None:
    """Fail-closed controlling terminal across observed outcome statuses."""
    observed = set(str(status) for status in statuses)
    for candidate in TERMINAL_PRECEDENCE:
        if candidate in observed:
            return candidate
    return None


def summarize_waits(
    connection: sqlite3.Connection,
    *,
    campaign_id: str,
    run_id: str,
    cycle_id: str,
) -> dict[str, Any]:
    """Read-only wait-state census for terminal reporting and cleanup checks."""
    if not wait_table_exists(connection):
        return {"rows": 0, "by_state": {}, "active": 0}
    rows = connection.execute(
        f"SELECT wait_state, COUNT(*) FROM {WAIT_TABLE} "
        "WHERE campaign_id=? AND run_id=? AND cycle_id=? GROUP BY wait_state",
        (campaign_id, run_id, cycle_id),
    ).fetchall()
    by_state = {str(state): int(count) for state, count in rows}
    return {
        "rows": sum(by_state.values()),
        "by_state": by_state,
        "active": sum(by_state.get(state, 0) for state in ACTIVE_WAIT_STATES),
    }


__all__ = [
    "ACQUISITION_DEADLINE_EXHAUSTED",
    "ACTIVE_WAIT_STATES",
    "ALREADY_PENDING_REFRESH",
    "AcquisitionLedger",
    "CANCELLED",
    "CAPACITY_ALREADY_MET",
    "CURRENT_UNIVERSE_EXHAUSTED_TERMINAL",
    "CURRENT_UNIVERSE_EXHAUSTED_WAITING",
    "CURRENT_UNIVERSE_EXHAUSTION_REASONS",
    "NOT_ELIGIBLE",
    "NO_LAWFUL_REFRESH_WINDOW",
    "PRE_LIFECYCLE_ACQUISITION_DURATION_EXHAUSTED",
    "PRE_LIFECYCLE_ACQUISITION_DURATION_SECONDS",
    "PreLifecycleTemporalAcquisitionError",
    "REFRESH_COMPLETED",
    "REFRESH_SOURCE_FAILURE",
    "INTERNAL_INVARIANT",
    "INTERNAL_RUNTIME_ERROR",
    "SOURCE_BUDGET_EXHAUSTED",
    "SUPERVISION_FAILED",
    "TERMINAL_PRECEDENCE",
    "TemporalRefreshOutcome",
    "UNIVERSE_NOT_EXHAUSTED",
    "UNSAFE_SCHEDULER_STATE",
    "WAITING_FOR_ELIGIBLE_SUPPLY",
    "WAIT_STATES",
    "WAIT_TABLE",
    "WaitEligibility",
    "acquisition_deadline_at",
    "active_refresh_waits",
    "controlling_terminal",
    "evaluate_wait_eligibility",
    "insert_refresh_wait",
    "iso",
    "mark_refresh_wait_claimed",
    "next_refresh_ordinal",
    "parse_iso",
    "refresh_window_fits",
    "summarize_waits",
    "terminalize_refresh_wait",
    "wait_table_exists",
]
