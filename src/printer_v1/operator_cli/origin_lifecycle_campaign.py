"""V2-9.7E.8 origin-to-lifecycle operational campaign driver.

Internal, dependency-injected composition owner. It joins the two subsystems
that were previously disconnected (V2-9.7E.7 finding):

* ``CombinedPumpfunCampaignExecutor`` — discovery, registry-first finalized Pump
  origin, fixed gates, deterministic uniform selection, atomic two-or-none
  activation into ``printer_memory_factory_campaign_token_slots``;
* ``one_command_15m_factory.run_one_command_15m_factory`` — the proven
  ``WINDOW_15M`` → ``WINDOW_1H`` → ``WINDOW_4H`` → support-only 5m → memory
  promotion → report → replay → cleanup lifecycle.

The bridge is the factory's existing ``discovery_runner`` seam: the driver runs
the executor exactly once, then materialises its atomic activation into the
factory's ``printer_selection_batch_items`` shape without any second discovery
or reselection. See
``docs/printer-v1-v2-9-7e-8-origin-to-lifecycle-integration-design.md``.

There is deliberately no public CLI and no live source path here. Every source
call stays inside the governed executor and the governed factory adapters.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import sqlite3
from pathlib import Path
from typing import Any, Callable, Mapping

from printer_v1.discovery.combined_executor import (
    CombinedDiscoveryError,
    CombinedDiscoveryFixtures,
    CombinedPumpfunCampaignExecutor,
)
from printer_v1.operator_cli.abstract_campaign_command import (
    AbstractCampaignCommand,
    CENTRAL_SCHEDULER_OWNER,
    OwnerPort,
    SOURCE_GOVERNOR_OWNER,
)
from printer_v1.operator_cli.one_command_15m_factory import run_one_command_15m_factory
from printer_v1.scheduler.scheduler import ACTIVE_STATUS_VALUES, cancel_job


ORIGIN_BATCH_PREFIX = "origin-activated"
LIFECYCLE_WINDOW_KIND = "WINDOW_15M"


class OriginLifecycleError(RuntimeError):
    """Fail-closed origin-to-lifecycle composition fault."""

    def __init__(self, code: str, detail: str = "") -> None:
        self.code = code
        self.detail = detail
        super().__init__(code if not detail else f"{code}: {detail}")


# The five post-handoff lifecycle stages that run AFTER a successful initial
# atomic two-slot handoff. A disposable-DB fault injected at any one of them must
# leave zero newly active or orphan state (compensating teardown).
POST_HANDOFF_STAGES = (
    "LIFECYCLE_SELECTION_BATCH_CREATION",
    "EXECUTOR_JOB_CANCELLATION",
    "LIFECYCLE_JOB_REPLANNING",
    "LIFECYCLE_OBJECT_MATERIALIZATION",
    "POST_ACTIVATION_STATE_TRANSITION",
)


class PostHandoffInjectedFault(RuntimeError):
    """A fault injected at a specific post-handoff lifecycle stage (proof only)."""

    def __init__(self, stage: str) -> None:
        self.stage = stage
        super().__init__(f"POST_HANDOFF_INJECTED_FAULT:{stage}")


def _maybe_inject(post_handoff_fault: str | None, stage: str) -> None:
    if post_handoff_fault is not None and str(post_handoff_fault) == stage:
        raise PostHandoffInjectedFault(stage)


@dataclass(frozen=True)
class ActivationResult:
    terminal_status: str
    first_terminal_cause: str
    activated_slots: tuple[dict[str, Any], ...]
    selection_batch_id: str | None
    fault_details: Mapping[str, Any] | None = None


@dataclass(frozen=True)
class OriginLifecycleResult:
    activation: ActivationResult
    lifecycle: dict[str, Any]
    lifecycle_started: bool


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _read_activated_slots(
    connection: sqlite3.Connection, cycle_id: str
) -> list[dict[str, Any]]:
    """Return the two atomically activated slots for a cycle, ordered 1,2.

    Only slots in a live SELECTED/active state are returned; failed, cooldown,
    or archived slots are not lifecycle targets.
    """
    rows = connection.execute(
        """
        SELECT s.slot_ordinal, s.token_row_id, s.pair_row_id, s.mint_identity,
               s.pair_identity, s.token_state, p.pair_address, t.token_status
        FROM printer_memory_factory_campaign_token_slots AS s
        JOIN printer_pairs AS p ON p.id = s.pair_row_id
        JOIN printer_tokens AS t ON t.id = s.token_row_id
        WHERE s.cycle_id = ?
          AND s.token_state = 'SELECTED'
        ORDER BY s.slot_ordinal
        """,
        (cycle_id,),
    ).fetchall()
    return [dict(row) for row in rows]


def _cancel_executor_first_15m_jobs(
    connection: sqlite3.Connection,
    slots: list[dict[str, Any]],
    *,
    post_handoff_fault: str | None = None,
) -> int:
    """Cancel the executor's own first-15m jobs; the factory owns scheduling.

    The executor's atomic activation queues one ``TRACK_NORMAL_FIRST_15M`` job
    per slot (``window15m:<mint>:<pool>``). The factory replans opening jobs
    deterministically, so those are superseded and must not linger as stale
    scheduler work. Cancellation uses the canonical Scheduler owner; the
    activation rows themselves (slots, tracking queue) are preserved.
    """
    cancelled = 0
    for slot in slots:
        pool = str(slot["pair_identity"]).rsplit(":", 1)[-1]
        job_name = f"window15m:{slot['mint_identity']}:{pool}"
        for (job_id,) in connection.execute(
            """
            SELECT id FROM printer_scheduler_jobs
            WHERE job_name = ? AND status IN (%s)
            """
            % ",".join("?" * len(ACTIVE_STATUS_VALUES)),
            (job_name, *ACTIVE_STATUS_VALUES),
        ).fetchall():
            cancel_job(connection, job_id=int(job_id))
            cancelled += 1
            # Inject mid-cancellation: at least one job already cancelled.
            _maybe_inject(post_handoff_fault, "EXECUTOR_JOB_CANCELLATION")
    return cancelled


def materialize_origin_activated_batch(
    connection: sqlite3.Connection,
    *,
    cycle_id: str,
    selection_seed: str,
    tracking_lane: str = "TRACK_NORMAL",
    now: str | None = None,
    post_handoff_fault: str | None = None,
) -> str | None:
    """Mirror the two activated slots into a factory-consumable selection batch.

    Identity-preserving: every field comes from the already-activated slots and
    their shared ``printer_tokens``/``printer_pairs`` rows. Returns the batch id
    on exactly two activated slots, else ``None`` (no lifecycle work).
    """
    stamp = now or _utc_now()
    slots = _read_activated_slots(connection, cycle_id)
    if len(slots) != 2:
        return None
    if len({s["token_row_id"] for s in slots}) != 2:
        raise OriginLifecycleError(
            "IDENTITY_MISMATCH", "two slots share a token identity"
        )
    if any(s["slot_ordinal"] not in (1, 2) for s in slots):
        raise OriginLifecycleError("IDENTITY_MISMATCH", "unexpected slot ordinal")

    _cancel_executor_first_15m_jobs(
        connection, slots, post_handoff_fault=post_handoff_fault
    )

    batch_id = f"{ORIGIN_BATCH_PREFIX}:{cycle_id}"
    connection.execute(
        """
        INSERT INTO printer_selection_batches(
            batch_id, batch_status, window_kind, candidate_pool_total,
            selected_count, rejected_count, unavailable_or_unclassified_count,
            operator_approved, created_at
        ) VALUES (?, 'ASSEMBLED', ?, 2, 2, 0, 0, 1, ?)
        """,
        (batch_id, LIFECYCLE_WINDOW_KIND, stamp),
    )
    # Inject after the batch row exists, before its items — a partial batch.
    _maybe_inject(post_handoff_fault, "LIFECYCLE_SELECTION_BATCH_CREATION")
    for slot in slots:
        connection.execute(
            """
            INSERT INTO printer_selection_batch_items(
                batch_id, item_status, token_id, pair_id, token_mint,
                pair_address, chain, tracking_lane, selection_reason,
                source_name, same_token_new_pair, operator_approved,
                selected_at, cooldown_reopened, created_at
            ) VALUES (?, 'SELECTED', ?, ?, ?, ?, 'solana', ?,
                      'origin_confirmed_atomic_activation', 'solana_rpc',
                      0, 1, ?, 0, ?)
            """,
            (
                batch_id,
                int(slot["token_row_id"]),
                int(slot["pair_row_id"]),
                slot["mint_identity"],
                slot["pair_address"],
                tracking_lane,
                stamp,
                stamp,
            ),
        )
    return batch_id


# Lawful non-runnable terminal token-slot states (migration 032 CHECK).
_TERMINAL_SLOT_STATES = ("COOLDOWN", "ARCHIVED", "MANUAL_REVIEW", "FAILED")
# Tracking-queue states that keep a row runnable / promotable (migration 001).
_ACTIVE_TRACKING_STATES = ("QUEUED", "ACTIVE", "PAUSED", "COOLDOWN")


def _cycle_first_15m_job_ids(
    connection: sqlite3.Connection, cycle_id: str
) -> list[int]:
    """The executor's first-15m Scheduler jobs for a cycle, via the immutable link.

    These jobs (``window15m:<mint>:<pool>``, ``TRACK_NORMAL_FIRST_15M``) carry no
    discovery-work / campaign-scheduler-work row, so the campaign-scoped job scan
    never reaches them. The append-only
    ``printer_discovery_selected_item_links.first_window_15m_scheduler_job_id`` is
    the exact cycle-scoped handle.
    """
    return [
        int(row[0])
        for row in connection.execute(
            """
            SELECT DISTINCT first_window_15m_scheduler_job_id
            FROM printer_discovery_selected_item_links
            WHERE cycle_id = ? AND first_window_15m_scheduler_job_id IS NOT NULL
            ORDER BY first_window_15m_scheduler_job_id
            """,
            (cycle_id,),
        ).fetchall()
    ]


def _compensate_post_handoff_teardown(
    db_path: str | Path,
    *,
    campaign_id: str,
    run_id: str,
    cycle_id: str,
    activated_slots: list[dict[str, Any]],
    batch_id: str | None,
    terminal_cause: str,
    now: str | None = None,
) -> dict[str, Any]:
    """Terminalize the whole post-handoff campaign graph to zero active work.

    Runs in a new independent transaction *after* the failed materialization
    transaction has rolled back. The accepted invariant is not literal row-zero
    (unreachable — the atomic handoff commits an append-only immutable
    selected-item link that FK-pins the token slots and the first-15m job) but:

        zero active, runnable, leased, reusable, or orphan work;
        immutable terminal handoff audit evidence may remain.

    So the pinned rows are moved to a lawful **non-runnable terminal state**, not
    deleted, and the immutable links are preserved untouched as terminal audit
    evidence.

    This owner introduces no second cleanup authority: slot / tracking / cycle /
    run / campaign terminalization, campaign-scoped Scheduler cancellation,
    window terminalization, and the zero-active-work proof are delegated to the
    existing ``reconcile_campaign_terminal``. It adds only what that authority
    does not reach — deleting legally deletable lifecycle-materialization
    residue, cancelling the executor's cycle-scoped first-15m jobs (whose
    in-handoff cancellation rolled back with the failed transaction), and
    releasing active leases.

    Idempotent: every step is guarded by current row state, so a second pass
    performs no duplicate transition, cancellation, or deletion.
    """
    from printer_v1.operator_cli.unified_terminal_closure import (
        reconcile_campaign_terminal,
    )

    instant = now or _utc_now()
    token_ids = sorted({int(s["token_row_id"]) for s in activated_slots})

    deleted: dict[str, int] = {
        "run_steps": 0,
        "lifecycle_events": 0,
        "token_snapshots": 0,
        "episode_snapshots": 0,
        "selection_batch_items": 0,
        "selection_batches": 0,
    }
    first_15m_cancelled = 0
    leases_released = 0

    # -- Phase 1: delete deletable residue, cancel cycle-scoped first-15m jobs,
    #    release active leases. Each step guarded so a replay mutates nothing.
    connection = sqlite3.connect(Path(db_path))
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    try:
        ph = ",".join("?" * len(token_ids)) if token_ids else ""
        if token_ids:
            deleted["run_steps"] = connection.execute(
                f"DELETE FROM printer_memory_factory_run_steps WHERE token_id IN ({ph})",
                token_ids,
            ).rowcount
            for label, tbl in (
                ("lifecycle_events", "printer_token_lifecycle_events"),
                ("token_snapshots", "printer_token_snapshots"),
                ("episode_snapshots", "printer_episode_snapshots"),
            ):
                try:
                    deleted[label] = connection.execute(
                        f"DELETE FROM {tbl} WHERE token_id IN ({ph})", token_ids
                    ).rowcount
                except sqlite3.OperationalError:
                    deleted[label] = 0
        if batch_id:
            # The origin-activated factory batch only (never the executor's
            # audit selection items, which the immutable link FK-pins).
            deleted["selection_batch_items"] = connection.execute(
                "DELETE FROM printer_selection_batch_items WHERE batch_id=?",
                (batch_id,),
            ).rowcount
            deleted["selection_batches"] = connection.execute(
                "DELETE FROM printer_selection_batches WHERE batch_id=?", (batch_id,)
            ).rowcount

        # Cancel the executor's first-15m jobs whose in-handoff cancellation
        # rolled back. Only still-active jobs are cancelled (idempotent replay).
        for job_id in _cycle_first_15m_job_ids(connection, cycle_id):
            row = connection.execute(
                "SELECT status FROM printer_scheduler_jobs WHERE id=?", (job_id,)
            ).fetchone()
            if row is not None and str(row["status"]) in ACTIVE_STATUS_VALUES:
                cancel_job(connection, job_id=job_id)
                first_15m_cancelled += 1

        # Release/terminalize any active lease (safety net; N2/N7 out of scope).
        try:
            active_leases = connection.execute(
                "SELECT lease_id FROM printer_candidate_acquisition_leases "
                "WHERE lease_state IN ('ACTIVE','STOPPING') ORDER BY lease_id"
            ).fetchall()
            for (lease_id,) in active_leases:
                connection.execute(
                    """UPDATE printer_candidate_acquisition_leases
                       SET lease_state='TERMINAL', terminal_status='CANCELLED',
                           first_terminal_cause=?, released_at=?, updated_at=?
                       WHERE lease_id=? AND lease_state IN ('ACTIVE','STOPPING')""",
                    (terminal_cause, instant, instant, lease_id),
                )
                leases_released += 1
        except sqlite3.OperationalError:
            pass
        connection.commit()
    finally:
        connection.close()

    # -- Phase 2: the single terminal authority. Terminalizes slots
    #    (SELECTED -> MANUAL_REVIEW, cause recorded), slot-linked tracking
    #    (QUEUED -> SKIPPED), every campaign-scoped Scheduler job, windows, and
    #    cycle/run/campaign. Idempotent over an already-terminal graph.
    reconciliation = reconcile_campaign_terminal(
        db_path,
        campaign_id=campaign_id,
        run_id=run_id,
        cycle_id=cycle_id,
        terminal_cause=terminal_cause,
        run_status="FAILED",
        factory_run_id=None,
        lifecycle_started=False,
        now=instant,
    )
    dispositions = reconciliation.get("pre_lifecycle_dispositions", []) or []
    slots_transitioned = sum(
        1
        for d in dispositions
        if str(d.get("slot_disposition")) in _TERMINAL_SLOT_STATES
    )

    # -- Phase 3: deterministic compensation report from a fresh read.
    report_conn = sqlite3.connect(Path(db_path))
    report_conn.row_factory = sqlite3.Row
    report_conn.execute("PRAGMA foreign_keys = ON")
    try:
        def _count(sql: str, params: tuple = ()) -> int:
            return int(report_conn.execute(sql, params).fetchone()[0])

        cycle_job_ids = _cycle_first_15m_job_ids(report_conn, cycle_id)
        job_ph = ",".join("?" * len(cycle_job_ids)) if cycle_job_ids else ""
        tracking_ids = [
            int(r[0])
            for r in report_conn.execute(
                "SELECT tracking_queue_id FROM "
                "printer_memory_factory_campaign_token_slots "
                "WHERE cycle_id=? AND tracking_queue_id IS NOT NULL",
                (cycle_id,),
            ).fetchall()
        ]
        trk_ph = ",".join("?" * len(tracking_ids)) if tracking_ids else ""
        active_status_ph = ",".join("?" * len(ACTIVE_STATUS_VALUES))
        active_trk_ph = ",".join("?" * len(_ACTIVE_TRACKING_STATES))
        terminal_slot_ph = ",".join("?" * len(_TERMINAL_SLOT_STATES))

        immutable_links = _count(
            "SELECT COUNT(*) FROM printer_discovery_selected_item_links "
            "WHERE cycle_id=?",
            (cycle_id,),
        )
        slots_terminal = _count(
            "SELECT COUNT(*) FROM printer_memory_factory_campaign_token_slots "
            f"WHERE cycle_id=? AND token_state IN ({terminal_slot_ph})",
            (cycle_id, *_TERMINAL_SLOT_STATES),
        )
        slots_active = _count(
            "SELECT COUNT(*) FROM printer_memory_factory_campaign_token_slots "
            f"WHERE cycle_id=? AND token_state NOT IN ({terminal_slot_ph})",
            (cycle_id, *_TERMINAL_SLOT_STATES),
        )
        first_15m_cancelled_total = (
            _count(
                "SELECT COUNT(*) FROM printer_scheduler_jobs "
                f"WHERE id IN ({job_ph}) AND status='CANCELLED'",
                tuple(cycle_job_ids),
            )
            if cycle_job_ids
            else 0
        )
        first_15m_active = (
            _count(
                "SELECT COUNT(*) FROM printer_scheduler_jobs "
                f"WHERE id IN ({job_ph}) AND status IN ({active_status_ph})",
                (*cycle_job_ids, *ACTIVE_STATUS_VALUES),
            )
            if cycle_job_ids
            else 0
        )
        tracking_terminal = (
            _count(
                "SELECT COUNT(*) FROM printer_tracking_queue "
                f"WHERE id IN ({trk_ph}) AND queue_status IN ('SKIPPED','ARCHIVED')",
                tuple(tracking_ids),
            )
            if tracking_ids
            else 0
        )
        tracking_active = (
            _count(
                "SELECT COUNT(*) FROM printer_tracking_queue "
                f"WHERE id IN ({trk_ph}) AND queue_status IN ({active_trk_ph})",
                (*tracking_ids, *_ACTIVE_TRACKING_STATES),
            )
            if tracking_ids
            else 0
        )
        active_leases = _count(
            "SELECT COUNT(*) FROM printer_candidate_acquisition_leases "
            "WHERE lease_state IN ('ACTIVE','STOPPING')"
        )
        deletable_remaining = (
            _count(
                "SELECT COUNT(*) FROM printer_selection_batches WHERE batch_id=?",
                (batch_id or "",),
            )
            + _count(
                "SELECT COUNT(*) FROM printer_selection_batch_items WHERE batch_id=?",
                (batch_id or "",),
            )
            + (
                _count(
                    "SELECT COUNT(*) FROM printer_memory_factory_run_steps "
                    f"WHERE token_id IN ({ph})",
                    tuple(token_ids),
                )
                + _count(
                    "SELECT COUNT(*) FROM printer_token_lifecycle_events "
                    f"WHERE token_id IN ({ph})",
                    tuple(token_ids),
                )
                if token_ids
                else 0
            )
        )
        active_campaign_jobs = int(
            (reconciliation.get("active_work") or {}).get("active_jobs", 0)
        )

        remaining_active_work = {
            "active_slots": slots_active,
            "queued_or_active_tracking": tracking_active,
            "active_first_15m_jobs": first_15m_active,
            "active_campaign_jobs": active_campaign_jobs,
            "active_leases": active_leases,
            "deletable_residue_rows": deletable_remaining,
        }
        clean = all(value == 0 for value in remaining_active_work.values())
        mutations_this_pass = {
            "rows_deleted": sum(deleted.values()),
            "first_15m_jobs_cancelled": first_15m_cancelled,
            "slots_transitioned": slots_transitioned,
            "campaign_jobs_cancelled": int(reconciliation.get("cancelled_jobs", 0)),
            "leases_released": leases_released,
        }

        return {
            "compensation_owner": "V2_9_8B_POST_HANDOFF_TERMINAL_COMPENSATION",
            "terminal_cause": terminal_cause,
            "campaign_id": campaign_id,
            "run_id": run_id,
            "cycle_id": cycle_id,
            "immutable_retained_evidence": {
                "selected_item_links": immutable_links,
                "pinned_first_15m_jobs": len(cycle_job_ids),
            },
            "terminalized_pinned_rows": {
                "token_slots_terminalized": slots_terminal,
                "first_15m_jobs_cancelled": first_15m_cancelled_total,
                "tracking_rows_terminalized": tracking_terminal,
            },
            "deleted_lifecycle_residue": dict(deleted),
            "remaining_active_work": remaining_active_work,
            "clean_zero_active_work": clean,
            "mutations_this_pass": mutations_this_pass,
            "reconciliation": reconciliation,
        }
    finally:
        report_conn.close()


class OriginToLifecycleCampaignDriver:
    """Compose origin activation with the memory lifecycle (internal, DI-only)."""

    def __init__(
        self,
        *,
        executor_factory: Callable[[CombinedDiscoveryFixtures], CombinedPumpfunCampaignExecutor]
        | None = None,
        lifecycle_runner: Callable[..., dict[str, Any]] | None = None,
    ) -> None:
        self._executor_factory = executor_factory or CombinedPumpfunCampaignExecutor
        self._lifecycle_runner = lifecycle_runner or run_one_command_15m_factory

    def _apply_and_fault_post_runner(
        self,
        db_path: str | Path,
        *,
        cycle_id: str,
        batch_id: str | None,
        activated_slots: list[dict[str, Any]],
        stage: str,
    ) -> None:
        """Apply a representative post-runner object/transition, then fault.

        Proves the compensating teardown removes lifecycle objects and reverses
        a post-activation state transition, not only the initial handoff rows.
        """
        connection = sqlite3.connect(Path(db_path))
        connection.execute("PRAGMA foreign_keys = ON")
        try:
            if stage == "LIFECYCLE_OBJECT_MATERIALIZATION" and activated_slots:
                slot = activated_slots[0]
                connection.execute(
                    """
                    INSERT INTO printer_token_lifecycle_events(
                        token_id, pair_id, new_state, lifecycle_event,
                        source_status, data_quality_label, created_at
                    ) VALUES (?, ?, 'TRACK_NORMAL', 'MATERIALIZED_LIFECYCLE_OBJECT',
                              'COMPLETE', 'CLEAN_DATA', ?)
                    """,
                    (int(slot["token_row_id"]), int(slot["pair_row_id"]), _utc_now()),
                )
            elif stage == "POST_ACTIVATION_STATE_TRANSITION" and batch_id:
                connection.execute(
                    "UPDATE printer_selection_batches SET batch_status='PENDING_PROOF' "
                    "WHERE batch_id=?",
                    (batch_id,),
                )
            connection.commit()
        finally:
            connection.close()
        raise PostHandoffInjectedFault(stage)

    def run(
        self,
        *,
        command: AbstractCampaignCommand,
        fixtures: CombinedDiscoveryFixtures,
        backup_path: str | Path,
        source_governor: OwnerPort | None = None,
        central_scheduler: OwnerPort | None = None,
        selection_seed: str,
        proof_mode: bool = True,
        continuous_first_hour: bool = False,
        continuous_four_hour: bool = False,
        four_hour_proof_mode: bool = False,
        operational_persistent_mode: bool = False,
        lifecycle_kwargs: dict[str, Any] | None = None,
        post_handoff_fault: str | None = None,
    ) -> OriginLifecycleResult:
        """Run one integrated campaign: activation, then lifecycle on those slots.

        ``post_handoff_fault`` (proof only) injects a fault at one of the five
        post-handoff lifecycle stages after the successful initial handoff; the
        driver then runs a compensating teardown leaving zero orphan state.
        """
        if post_handoff_fault is not None and post_handoff_fault not in POST_HANDOFF_STAGES:
            raise OriginLifecycleError("UNKNOWN_POST_HANDOFF_STAGE", post_handoff_fault)
        governor = source_governor or OwnerPort(SOURCE_GOVERNOR_OWNER, True)
        scheduler = central_scheduler or OwnerPort(CENTRAL_SCHEDULER_OWNER, True)

        executor = self._executor_factory(fixtures)
        try:
            activation = executor.execute(
                command=command,
                source_governor=governor,
                central_scheduler=scheduler,
            )
        except CombinedDiscoveryError as exc:
            # Owner-unavailable and other pre-cycle faults fail closed: no
            # activation, therefore no lifecycle work.
            return OriginLifecycleResult(
                activation=ActivationResult(
                    terminal_status="FAILED",
                    first_terminal_cause=exc.code,
                    activated_slots=(),
                    selection_batch_id=None,
                ),
                lifecycle={
                    "run_status": "NOT_STARTED",
                    "stop_reason": "ACTIVATION_FAILED",
                    "first_terminal_cause": exc.code,
                },
                lifecycle_started=False,
            )

        # The initial atomic two-slot handoff has now committed. Capture its
        # activated slots up front so a post-handoff fault can be compensated to
        # zero orphan state regardless of which later stage fails.
        capture_conn = sqlite3.connect(Path(command.db_path))
        capture_conn.row_factory = sqlite3.Row
        capture_conn.execute("PRAGMA foreign_keys = ON")
        try:
            committed_slots = _read_activated_slots(capture_conn, fixtures.cycle_id)
        finally:
            capture_conn.close()

        try:
            connection = sqlite3.connect(Path(command.db_path))
            connection.row_factory = sqlite3.Row
            connection.execute("PRAGMA foreign_keys = ON")
            try:
                slots = _read_activated_slots(connection, fixtures.cycle_id)
                batch_id = materialize_origin_activated_batch(
                    connection,
                    cycle_id=fixtures.cycle_id,
                    selection_seed=selection_seed,
                    post_handoff_fault=post_handoff_fault,
                )
                connection.commit()
            finally:
                connection.close()

            # Stage 3: lifecycle job replanning (handoff to the lifecycle runner).
            _maybe_inject(post_handoff_fault, "LIFECYCLE_JOB_REPLANNING")
            # Stages 4/5: object materialization / post-activation state
            # transition. A representative lifecycle object / transition is
            # applied on a disposable DB before the fault so compensation is
            # proven to remove even post-runner state.
            if post_handoff_fault in (
                "LIFECYCLE_OBJECT_MATERIALIZATION",
                "POST_ACTIVATION_STATE_TRANSITION",
            ):
                self._apply_and_fault_post_runner(
                    command.db_path,
                    cycle_id=fixtures.cycle_id,
                    batch_id=batch_id,
                    activated_slots=committed_slots,
                    stage=post_handoff_fault,
                )
        except PostHandoffInjectedFault as fault:
            cause = f"POST_HANDOFF_{fault.stage}"
            report = _compensate_post_handoff_teardown(
                command.db_path,
                campaign_id=command.campaign_id,
                run_id=command.run_id,
                cycle_id=fixtures.cycle_id,
                activated_slots=committed_slots,
                batch_id=f"{ORIGIN_BATCH_PREFIX}:{fixtures.cycle_id}",
                terminal_cause=cause,
            )
            return OriginLifecycleResult(
                activation=ActivationResult(
                    terminal_status="FAILED",
                    first_terminal_cause=cause,
                    activated_slots=(),
                    selection_batch_id=None,
                    fault_details={
                        "post_handoff_stage": fault.stage,
                        "compensation_report": report,
                    },
                ),
                lifecycle={
                    "run_status": "FAILED",
                    "stop_reason": cause,
                    "first_terminal_cause": cause,
                    "post_handoff_compensation_report": report,
                },
                lifecycle_started=False,
            )

        activation_result = ActivationResult(
            terminal_status=activation.terminal_status,
            first_terminal_cause=activation.first_terminal_cause,
            activated_slots=tuple(slots),
            selection_batch_id=batch_id,
            fault_details=activation.fault_details,
        )

        if batch_id is None:
            # Zero-slot or rolled-back activation: no lifecycle work.
            lifecycle = {
                "run_status": "NOT_STARTED",
                "stop_reason": "NO_ATOMIC_ACTIVATION",
                "first_terminal_cause": activation.first_terminal_cause,
            }
            if activation.fault_details:
                lifecycle["fault_details"] = dict(activation.fault_details)
            return OriginLifecycleResult(
                activation=activation_result,
                lifecycle=lifecycle,
                lifecycle_started=False,
            )

        # Identity-preserving handoff: the factory consumes exactly the two
        # activated slots via a discovery_runner that only mirrors them. It runs
        # no discovery and no reselection of its own.
        def origin_discovery_runner(_args: Any) -> dict[str, Any]:
            return {
                "selection_handoff_report": {
                    "batch_id": batch_id,
                    "selection_seed": selection_seed,
                    "eligible_pool_size": 2,
                },
                "discovery_results": [],
            }

        # V2-9.7E.47 A2/A3: the lifecycle owner receives the exact campaign
        # ownership identities so its terminal cleanup can reach every
        # campaign-scoped Scheduler job. The handoff batch id
        # (`origin-activated:<cycle>`) is deliberately NOT the executor's
        # discovery batch id, which is why identity-based scoping is required.
        lifecycle = self._lifecycle_runner(
            command.db_path,
            backup_path,
            operator_approved=True,
            proof_mode=proof_mode,
            discovery_runner=origin_discovery_runner,
            continuous_first_hour=continuous_first_hour,
            continuous_four_hour=continuous_four_hour,
            four_hour_proof_mode=four_hour_proof_mode,
            operational_persistent_mode=operational_persistent_mode,
            max_selected_tokens=2,
            campaign_id=command.campaign_id,
            campaign_run_id=command.run_id,
            cycle_id=fixtures.cycle_id,
            **(lifecycle_kwargs or {}),
        )
        return OriginLifecycleResult(
            activation=activation_result,
            lifecycle=lifecycle,
            lifecycle_started=True,
        )
