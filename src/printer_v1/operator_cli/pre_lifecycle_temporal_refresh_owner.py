"""V2-9.8B Post-DTW98 pre-lifecycle temporal refresh owner.

The canonical operational orchestration owner for one bounded, Scheduler-owned
pre-lifecycle acquisition wait. ``eligible_token_supply`` remains the supply and
budget/exhaustion owner and never calls the Scheduler itself; it asks this owner
for a temporal refresh opportunity through a dependency-injected boundary.

Exact contract (design §4), in order:

1. prove Source Governor / Central Scheduler owner availability;
2. prove no open SQLite write transaction is held across waiting;
3. compute the next due time from the canonical ``DISCOVERY_REFRESH`` interval;
4. enqueue exactly one future ``DISCOVERY_REFRESH`` job;
5. persist the exact pending-refresh ownership row bound to that job;
6. publish ``WAITING_FOR_ELIGIBLE_SUPPLY``;
7. suspend the *already authorized* child once, to the due instant or the
   acquisition deadline — one bounded interruptible wait, never a poll loop;
8. let the existing campaign heartbeat thread keep renewing the lease;
9. on wake, check supervision/cancellation/deadline/exact job identity first;
10. claim that exact due Scheduler job once;
11. only after a successful claim, create the exact ``printer_discovery_work``
    RUNNING row linked to that same Scheduler job;
12. run one bounded Source-Governed refresh stage;
13. terminalize discovery work, Scheduler job and wait row consistently.

A timer only suspends an already-authorized child. The persisted Scheduler job
remains the sole authority for whether refresh work may start.

Forbidden here and never added: sleep-based polling, an unbounded loop, a
background refresh worker, a child-process restart, a second child, a second
authorization, retry/restart/resume/successor semantics, or any provider request
that is not owned by the injected Source-Governed refresh stage.
"""

from __future__ import annotations

import sqlite3
import threading
from datetime import timedelta
from pathlib import Path
from typing import Any, Callable, Mapping

from printer_v1.discovery.persistence import insert_discovery_work
from printer_v1.discovery.pre_lifecycle_temporal_acquisition import (
    ACQUISITION_DEADLINE_EXHAUSTED,
    ALREADY_PENDING_REFRESH,
    CANCELLED,
    REFRESH_COMPLETED,
    REFRESH_SOURCE_FAILURE,
    SOURCE_BUDGET_EXHAUSTED,
    SUPERVISION_FAILED,
    UNSAFE_SCHEDULER_STATE,
    WAITING_FOR_ELIGIBLE_SUPPLY,
    TemporalRefreshOutcome,
    active_refresh_waits,
    evaluate_wait_eligibility,
    insert_refresh_wait,
    iso,
    mark_refresh_wait_claimed,
    next_refresh_ordinal,
    parse_iso,
    refresh_window_fits,
    terminalize_refresh_wait,
)
from printer_v1.scheduler.contracts import JobKind, JobStatus, LockResult
from printer_v1.scheduler.resource_governor import next_check_interval_seconds
from printer_v1.scheduler.scheduler import (
    cancel_job,
    claim_due_job,
    complete_job,
    fail_job,
)
from printer_v1.scheduler.scheduler import enqueue_job

#: The refresh stage's exact discovery work type. A temporal refresh reopens
#: bounded lawful *nomination* of newly reachable identities, which is the
#: aggregator fresh-pool nomination category — not the Pump latest-tail stage
#: the combined executor owns (``DISCOVERY_PUMPFUN_LATEST``).
#:
#: Two applied-schema constraints bound this, and neither may be relaxed here:
#: ``printer_discovery_batches`` is UNIQUE per ``cycle_id`` and
#: ``printer_discovery_work`` is UNIQUE ``(discovery_batch_id, work_type)``.
#: Exactly one temporal refresh work row can therefore exist per cycle — which
#: is exactly what the 900-second horizon permits (design §2). A second one
#: fails closed at the database rather than silently overwriting the first.
REFRESH_WORK_TYPE = "DISCOVERY_GECKOTERMINAL_TRENDING_ACTIVE"

WAIT_ABORT_SUPERVISION = "SUPERVISION_FAILED"
WAIT_ABORT_CANCELLED = "CANCELLATION_REQUESTED"


class PreLifecycleTemporalRefreshError(RuntimeError):
    """Fail-closed pre-lifecycle temporal refresh orchestration fault."""


def bounded_interruptible_wait(
    seconds: float, abort_event: threading.Event | None
) -> bool:
    """Suspend this already-authorized child once, interruptibly.

    Returns ``True`` when the wait was aborted early. This is one bounded
    ``Event.wait`` — it is not a poll loop, it performs no work, it issues no
    provider request, and it holds no SQLite write transaction.
    """
    if seconds <= 0:
        return bool(abort_event is not None and abort_event.is_set())
    event = abort_event if abort_event is not None else threading.Event()
    return bool(event.wait(timeout=seconds))


class PreLifecycleTemporalRefreshOwner:
    """One-invocation owner of bounded pre-lifecycle temporal refreshes.

    Identity is fixed at construction: the same authorization, campaign, run,
    cycle and supervision are used for every refresh opportunity. Nothing here
    creates a successor campaign, a retry, a resume or a second authorization.
    """

    def __init__(
        self,
        db_path: str | Path,
        *,
        campaign_id: str,
        run_id: str,
        cycle_id: str,
        supervision_id: str,
        source_governor: Any,
        central_scheduler: Any,
        acquisition_deadline_at: str,
        work_deadline_at: str,
        refresh_stage: Callable[..., Mapping[str, Any]],
        discovery_batch_resolver: Callable[[sqlite3.Connection, str, int], str],
        supervision_probe: Callable[[], Mapping[str, Any]] | None = None,
        waiter: Callable[[float], bool] | None = None,
        clock: Callable[[], str] | None = None,
        publisher: Callable[[Mapping[str, Any]], None] | None = None,
        abort_event: threading.Event | None = None,
        refresh_interval_seconds: int | None = None,
    ) -> None:
        self.db_path = Path(db_path)
        self.campaign_id = str(campaign_id)
        self.run_id = str(run_id)
        self.cycle_id = str(cycle_id)
        self.supervision_id = str(supervision_id)
        self.source_governor = source_governor
        self.central_scheduler = central_scheduler
        self.acquisition_deadline_at = str(acquisition_deadline_at)
        self.work_deadline_at = str(work_deadline_at)
        self._refresh_stage = refresh_stage
        self._discovery_batch_resolver = discovery_batch_resolver
        self._supervision_probe = supervision_probe
        self._waiter = waiter
        self._clock = clock
        self._publisher = publisher
        self._abort_event = abort_event
        # Canonical Central Scheduler cadence. Never independently tuned.
        self.refresh_interval_seconds = int(
            next_check_interval_seconds(JobKind.DISCOVERY_REFRESH)
            if refresh_interval_seconds is None
            else refresh_interval_seconds
        )
        self.published_states: list[dict[str, Any]] = []
        # Acquisition-clock high-water mark. A completed refresh really
        # consumed one whole interval of the horizon, so the next window must
        # be measured from the instant the child woke — never from a caller's
        # unadvanced wall clock. This is what makes the 900s horizon admit
        # exactly one normal 600s refresh (design §2).
        self._acquisition_mark: str | None = None

    # -- helpers ---------------------------------------------------------- #

    def _now(self, fallback: str) -> str:
        return self._clock() if self._clock is not None else fallback

    def _acquisition_now(self, now: str) -> str:
        """The later of the caller's instant and the acquisition high-water mark."""
        if self._acquisition_mark is None:
            return now
        return (
            self._acquisition_mark
            if parse_iso(self._acquisition_mark) > parse_iso(now)
            else now
        )

    def _publish(self, state: str, **evidence: Any) -> None:
        payload = {
            "state": state,
            "campaign_id": self.campaign_id,
            "run_id": self.run_id,
            "cycle_id": self.cycle_id,
            "supervision_id": self.supervision_id,
            **evidence,
        }
        self.published_states.append(payload)
        if self._publisher is not None:
            self._publisher(payload)

    def _owners_available(self) -> bool:
        for owner in (self.source_governor, self.central_scheduler):
            if owner is None:
                return False
            if not bool(getattr(owner, "available", owner)):
                return False
        return True

    def _supervision(self) -> tuple[bool, bool]:
        """Return ``(supervision_active, cancellation_requested)``."""
        if self._supervision_probe is None:
            return True, False
        state = dict(self._supervision_probe() or {})
        cancelled = bool(
            state.get("cancellation_requested")
            or state.get("cancellation_requested_at")
        )
        active = bool(
            state.get(
                "supervision_active",
                state.get("supervision_state", "ACTIVE") == "ACTIVE"
                and not state.get("lease_expired", False),
            )
        )
        return active, cancelled

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.db_path)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys=ON")
        return connection

    # -- public boundary --------------------------------------------------- #

    def request_temporal_refresh(
        self,
        *,
        reserve_depth: int,
        required_capacity: int,
        universe_state: str,
        source_operations_remaining: int,
        provider_terminal_failure: bool = False,
        now: str,
    ) -> TemporalRefreshOutcome:
        """Request exactly one Scheduler-owned temporal refresh opportunity."""
        connection = self._connect()
        try:
            return self._request(
                connection,
                reserve_depth=int(reserve_depth),
                required_capacity=int(required_capacity),
                universe_state=str(universe_state),
                source_operations_remaining=int(source_operations_remaining),
                provider_terminal_failure=bool(provider_terminal_failure),
                now=str(now),
            )
        finally:
            connection.close()

    # Supply calls the owner as a plain callable boundary too.
    __call__ = request_temporal_refresh

    def _request(
        self,
        connection: sqlite3.Connection,
        *,
        reserve_depth: int,
        required_capacity: int,
        universe_state: str,
        source_operations_remaining: int,
        provider_terminal_failure: bool,
        now: str,
    ) -> TemporalRefreshOutcome:
        now = self._acquisition_now(now)
        # 1. Owner availability.
        if not self._owners_available():
            return TemporalRefreshOutcome(
                status=UNSAFE_SCHEDULER_STATE,
                reserve_depth_before=reserve_depth,
                reserve_depth_after=reserve_depth,
                detail="source governor or central scheduler owner unavailable",
            )

        # 2. No open write transaction may be held across a wait.
        if connection.in_transaction:
            return TemporalRefreshOutcome(
                status=UNSAFE_SCHEDULER_STATE,
                reserve_depth_before=reserve_depth,
                reserve_depth_after=reserve_depth,
                detail="open sqlite write transaction held at wait boundary",
            )

        supervision_active, cancellation_requested = self._supervision()
        pending = active_refresh_waits(
            connection,
            campaign_id=self.campaign_id,
            run_id=self.run_id,
            cycle_id=self.cycle_id,
        )
        eligibility = evaluate_wait_eligibility(
            reserve_depth=reserve_depth,
            required_capacity=required_capacity,
            universe_state=universe_state,
            now=now,
            acquisition_deadline_at=self.acquisition_deadline_at,
            source_operations_remaining=source_operations_remaining,
            provider_terminal_failure=provider_terminal_failure,
            supervision_active=supervision_active,
            cancellation_requested=cancellation_requested,
            pending_refresh_exists=bool(pending),
        )
        if not eligibility.eligible:
            return TemporalRefreshOutcome(
                status=eligibility.reason,
                reserve_depth_before=reserve_depth,
                reserve_depth_after=reserve_depth,
                detail="wait eligibility not satisfied",
            )

        # 3-4. Canonical cadence; refuse to schedule past the horizon.
        if not refresh_window_fits(
            now=now,
            acquisition_deadline_at=self.acquisition_deadline_at,
            refresh_interval_seconds=self.refresh_interval_seconds,
        ):
            return TemporalRefreshOutcome(
                status="NO_LAWFUL_REFRESH_WINDOW",
                reserve_depth_before=reserve_depth,
                reserve_depth_after=reserve_depth,
                detail=(
                    "next canonical DISCOVERY_REFRESH interval is not strictly "
                    "before the pre-lifecycle acquisition deadline"
                ),
            )

        due_at = parse_iso(now) + timedelta(seconds=self.refresh_interval_seconds)
        ordinal = next_refresh_ordinal(
            connection,
            campaign_id=self.campaign_id,
            run_id=self.run_id,
            cycle_id=self.cycle_id,
        )
        job_name = (
            f"PRE_LIFECYCLE_DISCOVERY_REFRESH:{self.campaign_id}:"
            f"{self.run_id}:{self.cycle_id}:{ordinal}"
        )
        result, job_id = enqueue_job(
            connection,
            job_name=job_name,
            job_kind=JobKind.DISCOVERY_REFRESH,
            target_table="printer_discovery_batches",
            scheduled_for=due_at,
        )
        if job_id is None:
            return TemporalRefreshOutcome(
                status=ALREADY_PENDING_REFRESH
                if result == LockResult.DUPLICATE_ACTIVE_JOB
                else UNSAFE_SCHEDULER_STATE,
                reserve_depth_before=reserve_depth,
                reserve_depth_after=reserve_depth,
                detail=f"enqueue refused: {result}",
            )

        # 5. Exact pending-refresh ownership, bound to that job.
        wait_id = (
            f"prelifecycle-refresh-wait:{self.campaign_id}:{self.run_id}:"
            f"{self.cycle_id}:{ordinal}"
        )
        scheduled_for = iso(due_at)
        insert_refresh_wait(
            connection,
            wait_id=wait_id,
            campaign_id=self.campaign_id,
            run_id=self.run_id,
            cycle_id=self.cycle_id,
            supervision_id=self.supervision_id,
            scheduler_job_id=int(job_id),
            refresh_ordinal=ordinal,
            scheduled_for=scheduled_for,
            acquisition_deadline_at=self.acquisition_deadline_at,
            now=now,
        )
        connection.commit()

        # 6. Publish the nonterminal state.
        self._publish(
            WAITING_FOR_ELIGIBLE_SUPPLY,
            wait_id=wait_id,
            scheduler_job_id=int(job_id),
            refresh_ordinal=ordinal,
            scheduled_for=scheduled_for,
            eligible_reserve_depth=reserve_depth,
            required_eligible_capacity=required_capacity,
            acquisition_deadline_at=self.acquisition_deadline_at,
        )

        waiting_outcome = TemporalRefreshOutcome(
            status=WAITING_FOR_ELIGIBLE_SUPPLY,
            wait_id=wait_id,
            scheduler_job_id=int(job_id),
            refresh_ordinal=ordinal,
            scheduled_for=scheduled_for,
            reserve_depth_before=reserve_depth,
            reserve_depth_after=reserve_depth,
            detail="pre-lifecycle acquisition waiting for a due Scheduler refresh",
        )
        if self._waiter is None:
            # No waiter supplied: the nonterminal waiting state is entered,
            # published and durably owned. Nothing further may run here.
            return waiting_outcome

        # 7. One bounded interruptible suspension of this same child. Zero
        #    provider operations occur while waiting.
        wait_seconds = (due_at - parse_iso(now)).total_seconds()
        aborted = bool(self._waiter(max(0.0, wait_seconds)))
        woke_at = self._now(scheduled_for)
        self._acquisition_mark = woke_at

        # 9. Supervision, cancellation, deadline and exact job identity first.
        supervision_active, cancellation_requested = self._supervision()
        if aborted or not supervision_active or cancellation_requested:
            cause = (
                WAIT_ABORT_SUPERVISION
                if not supervision_active
                else WAIT_ABORT_CANCELLED
            )
            status = SUPERVISION_FAILED if not supervision_active else CANCELLED
            self._abandon_pending_wait(
                connection,
                wait_id=wait_id,
                job_id=int(job_id),
                wait_state="CANCELLED",
                cause=cause,
                now=woke_at,
            )
            return TemporalRefreshOutcome(
                status=status,
                wait_id=wait_id,
                scheduler_job_id=int(job_id),
                refresh_ordinal=ordinal,
                scheduled_for=scheduled_for,
                reserve_depth_before=reserve_depth,
                reserve_depth_after=reserve_depth,
                detail=cause,
            )
        if parse_iso(woke_at) >= parse_iso(self.acquisition_deadline_at):
            self._abandon_pending_wait(
                connection,
                wait_id=wait_id,
                job_id=int(job_id),
                wait_state="CANCELLED",
                cause="PRE_LIFECYCLE_ACQUISITION_DEADLINE_EXHAUSTED",
                now=woke_at,
            )
            return TemporalRefreshOutcome(
                status=ACQUISITION_DEADLINE_EXHAUSTED,
                wait_id=wait_id,
                scheduler_job_id=int(job_id),
                refresh_ordinal=ordinal,
                scheduled_for=scheduled_for,
                reserve_depth_before=reserve_depth,
                reserve_depth_after=reserve_depth,
                detail="acquisition deadline reached before the refresh was due",
            )

        # 10. Claim that exact due Scheduler job, once.
        lock_owner = f"pre-lifecycle-refresh:{wait_id}"
        claim_result = claim_due_job(
            connection,
            job_id=int(job_id),
            lock_owner=lock_owner,
            now=parse_iso(woke_at),
        )
        if claim_result != LockResult.ACQUIRED:
            self._abandon_pending_wait(
                connection,
                wait_id=wait_id,
                job_id=int(job_id),
                wait_state="FAILED",
                cause=f"PRE_LIFECYCLE_REFRESH_CLAIM_{claim_result.value}",
                now=woke_at,
            )
            return TemporalRefreshOutcome(
                status=UNSAFE_SCHEDULER_STATE,
                wait_id=wait_id,
                scheduler_job_id=int(job_id),
                refresh_ordinal=ordinal,
                scheduled_for=scheduled_for,
                reserve_depth_before=reserve_depth,
                reserve_depth_after=reserve_depth,
                detail=f"claim not acquired: {claim_result}",
            )
        self._require_claimed_identity(
            connection, job_id=int(job_id), job_name=job_name, lock_owner=lock_owner
        )
        mark_refresh_wait_claimed(connection, wait_id=wait_id, now=woke_at)
        connection.commit()

        # 11. Only now may discovery work exist.
        # Each refresh opportunity is its own bounded discovery batch:
        # printer_discovery_work is UNIQUE (discovery_batch_id, work_type), so
        # reusing one batch across ordinals would silently collide rather than
        # record two honestly distinct stages.
        batch_id = self._discovery_batch_resolver(connection, woke_at, ordinal)
        work_id = f"work:{REFRESH_WORK_TYPE}:{wait_id}"
        insert_discovery_work(
            connection,
            discovery_work_id=work_id,
            discovery_batch_id=str(batch_id),
            campaign_id=self.campaign_id,
            run_id=self.run_id,
            cycle_id=self.cycle_id,
            scheduler_job_id=int(job_id),
            work_type=REFRESH_WORK_TYPE,
            deadline_at=self.work_deadline_at,
            work_state="RUNNING",
            now=woke_at,
        )
        connection.commit()

        # 12. One bounded Source-Governed refresh stage.
        try:
            stage = dict(
                self._refresh_stage(
                    connection,
                    campaign_id=self.campaign_id,
                    run_id=self.run_id,
                    cycle_id=self.cycle_id,
                    discovery_work_id=work_id,
                    scheduler_job_id=int(job_id),
                    refresh_ordinal=ordinal,
                    source_operations_remaining=source_operations_remaining,
                    now=woke_at,
                )
                or {}
            )
        except Exception as exc:  # fail closed; never retry here
            self._terminalize_after_claim(
                connection,
                wait_id=wait_id,
                work_id=work_id,
                job_id=int(job_id),
                succeeded=False,
                cause="PRE_LIFECYCLE_REFRESH_STAGE_FAILED",
                now=woke_at,
            )
            return TemporalRefreshOutcome(
                status=REFRESH_SOURCE_FAILURE,
                wait_id=wait_id,
                scheduler_job_id=int(job_id),
                refresh_ordinal=ordinal,
                scheduled_for=scheduled_for,
                claimed=True,
                reserve_depth_before=reserve_depth,
                reserve_depth_after=reserve_depth,
                detail=f"refresh stage failed: {type(exc).__name__}",
            )

        source_operations = int(stage.get("source_operations") or 0)
        provider_failures = int(stage.get("provider_failures") or 0)
        channels_unavailable = tuple(
            str(item) for item in (stage.get("channels_unavailable") or ())
        )
        if source_operations > int(source_operations_remaining):
            self._terminalize_after_claim(
                connection,
                wait_id=wait_id,
                work_id=work_id,
                job_id=int(job_id),
                succeeded=False,
                cause="PRE_LIFECYCLE_REFRESH_BUDGET_OVERRUN",
                now=woke_at,
            )
            return TemporalRefreshOutcome(
                status=SOURCE_BUDGET_EXHAUSTED,
                wait_id=wait_id,
                scheduler_job_id=int(job_id),
                refresh_ordinal=ordinal,
                scheduled_for=scheduled_for,
                claimed=True,
                source_operations=int(source_operations_remaining),
                reserve_depth_before=reserve_depth,
                reserve_depth_after=reserve_depth,
                detail="refresh stage exceeded the cumulative discovery budget",
            )

        # 13. Consistent terminalization of work, job and wait row.
        self._terminalize_after_claim(
            connection,
            wait_id=wait_id,
            work_id=work_id,
            job_id=int(job_id),
            succeeded=True,
            cause="PRE_LIFECYCLE_REFRESH_COMPLETED",
            now=woke_at,
        )
        self._publish(
            REFRESH_COMPLETED,
            wait_id=wait_id,
            scheduler_job_id=int(job_id),
            refresh_ordinal=ordinal,
            source_operations=source_operations,
        )
        return TemporalRefreshOutcome(
            status=REFRESH_COMPLETED,
            wait_id=wait_id,
            scheduler_job_id=int(job_id),
            refresh_ordinal=ordinal,
            scheduled_for=scheduled_for,
            claimed=True,
            source_operations=source_operations,
            provider_failures=provider_failures,
            channels_unavailable=channels_unavailable,
            reserve_depth_before=reserve_depth,
            reserve_depth_after=reserve_depth,
            detail="bounded Source-Governed refresh stage completed",
        )

    # -- terminalization --------------------------------------------------- #

    def _require_claimed_identity(
        self,
        connection: sqlite3.Connection,
        *,
        job_id: int,
        job_name: str,
        lock_owner: str,
    ) -> None:
        row = connection.execute(
            "SELECT id, job_name, job_kind, status, lock_owner "
            "FROM printer_scheduler_jobs WHERE id=?",
            (job_id,),
        ).fetchone()
        if (
            row is None
            or int(row["id"]) != int(job_id)
            or str(row["job_name"]) != job_name
            or str(row["job_kind"]) != JobKind.DISCOVERY_REFRESH.value
            or str(row["status"]) != JobStatus.RUNNING.value
            or str(row["lock_owner"] or "") != lock_owner
        ):
            raise PreLifecycleTemporalRefreshError(
                "PRE_LIFECYCLE_REFRESH_CLAIMED_IDENTITY_MISMATCH"
            )

    def cancel_pending_wait(
        self,
        *,
        wait_id: str,
        scheduler_job_id: int,
        cause: str,
        now: str,
    ) -> None:
        """Safe-stop capture: cancel a not-yet-claimed pending refresh exactly.

        Creates no ``printer_discovery_work`` row and leaves zero active
        Scheduler or wait residue for the campaign.
        """
        connection = self._connect()
        try:
            self._abandon_pending_wait(
                connection,
                wait_id=wait_id,
                job_id=int(scheduler_job_id),
                wait_state="CANCELLED",
                cause=cause,
                now=now,
            )
        finally:
            connection.close()

    def _abandon_pending_wait(
        self,
        connection: sqlite3.Connection,
        *,
        wait_id: str,
        job_id: int,
        wait_state: str,
        cause: str,
        now: str,
    ) -> None:
        cancel_job(connection, job_id=int(job_id))
        terminalize_refresh_wait(
            connection,
            wait_id=wait_id,
            wait_state=wait_state,
            first_terminal_cause=cause,
            now=now,
        )
        connection.commit()
        self._publish(
            wait_state,
            wait_id=wait_id,
            scheduler_job_id=int(job_id),
            first_terminal_cause=cause,
        )

    def _terminalize_after_claim(
        self,
        connection: sqlite3.Connection,
        *,
        wait_id: str,
        work_id: str,
        job_id: int,
        succeeded: bool,
        cause: str,
        now: str,
    ) -> None:
        connection.execute(
            """UPDATE printer_discovery_work
                  SET work_state=?, first_terminal_cause=?, terminal_at=?,
                      updated_at=?
                WHERE discovery_work_id=?""",
            (
                "SUCCEEDED" if succeeded else "FAILED",
                cause,
                now,
                now,
                work_id,
            ),
        )
        if succeeded:
            complete_job(connection, job_id=int(job_id))
        else:
            # max_retries=0 forbids a COOLDOWN re-arm: a failed pre-lifecycle
            # refresh is terminal and leaves zero active Scheduler residue. This
            # owner never retries, resumes or creates a successor.
            fail_job(
                connection, job_id=int(job_id), error=cause, max_retries=0
            )
        terminalize_refresh_wait(
            connection,
            wait_id=wait_id,
            wait_state="SUCCEEDED" if succeeded else "FAILED",
            first_terminal_cause=cause,
            now=now,
        )
        connection.commit()


__all__ = [
    "PreLifecycleTemporalRefreshError",
    "PreLifecycleTemporalRefreshOwner",
    "REFRESH_WORK_TYPE",
    "bounded_interruptible_wait",
]
