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

from dataclasses import dataclass, field
from datetime import datetime, timezone
import sqlite3
from pathlib import Path
from typing import Any, Callable, Mapping, Sequence

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


# The six post-handoff lifecycle stages that run AFTER a successful initial
# atomic two-slot handoff. A disposable-DB fault injected at any one of them must
# leave zero newly active or orphan state (compensating teardown).
POST_HANDOFF_STAGES = (
    "LIFECYCLE_SELECTION_BATCH_CREATION",
    "EXECUTOR_JOB_CANCELLATION",
    "AFTER_FIRST_RUN_STEP_AND_SCHEDULER_COMMIT",
    "AFTER_FIRST_TOKEN_SNAPSHOT_COMMIT",
    "AFTER_FIRST_LIFECYCLE_WINDOW_COMMIT",
    "AFTER_POST_ACTIVATION_15M_STATE_COMMIT",
)


class PostHandoffInjectedFault(RuntimeError):
    """A fault injected at a specific post-handoff lifecycle stage (proof only)."""

    def __init__(self, stage: str) -> None:
        self.stage = stage
        self.post_handoff_proof_fault = True
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
    cancellation_reason: str | None = None
    fault_details: Mapping[str, Any] | None = None
    accountable_stage_started: bool = False
    successor_created: bool = False
    restart_created: bool = False


@dataclass(frozen=True)
class OriginLifecycleResult:
    activation: ActivationResult
    lifecycle: dict[str, Any]
    lifecycle_started: bool


@dataclass(frozen=True)
class PostHandoffCompensationScope:
    """Exact durable rows owned by one post-handoff campaign attempt."""

    campaign_id: str
    run_id: str
    cycle_id: str
    factory_run_id: str | None
    selection_batch_id: str | None
    activated_token_ids: tuple[int, ...]
    activated_pair_ids: tuple[int, ...]
    executor_first_15m_job_ids: tuple[int, ...]
    lifecycle_scheduler_job_ids: tuple[int, ...]
    run_step_ids: tuple[int, ...]
    lifecycle_event_ids: tuple[int, ...]
    token_snapshot_ids: tuple[int, ...]
    episode_snapshot_ids: tuple[int, ...]
    owned_lease_ids: tuple[str, ...]


@dataclass
class _PostHandoffScopeRecorder:
    """Mutable attempt-local recorder; freezes to the immutable public scope."""

    campaign_id: str
    run_id: str
    cycle_id: str
    activated_token_ids: tuple[int, ...]
    activated_pair_ids: tuple[int, ...]
    factory_run_id: str | None = None
    selection_batch_id: str | None = None
    executor_first_15m_job_ids: set[int] = field(default_factory=set)
    lifecycle_scheduler_job_ids: set[int] = field(default_factory=set)
    run_step_ids: set[int] = field(default_factory=set)
    lifecycle_event_ids: set[int] = field(default_factory=set)
    token_snapshot_ids: set[int] = field(default_factory=set)
    episode_snapshot_ids: set[int] = field(default_factory=set)
    owned_lease_ids: set[str] = field(default_factory=set)
    proof_fault: str | None = None

    def record_factory_rows(
        self, connection: sqlite3.Connection, factory_run_id: str
    ) -> None:
        """Record only rows linked to the real factory run's exact durable ID."""
        self.factory_run_id = str(factory_run_id)
        rows = connection.execute(
            "SELECT id,scheduler_job_id,snapshot_id FROM "
            "printer_memory_factory_run_steps WHERE run_id=? ORDER BY id",
            (self.factory_run_id,),
        ).fetchall()
        for row in rows:
            self.run_step_ids.add(int(row[0]))
            if row[1] is not None:
                self.lifecycle_scheduler_job_ids.add(int(row[1]))
            if row[2] is not None:
                self.token_snapshot_ids.add(int(row[2]))
        if self.token_snapshot_ids:
            placeholders = ",".join("?" * len(self.token_snapshot_ids))
            for row in connection.execute(
                "SELECT id FROM printer_episode_snapshots "
                f"WHERE token_snapshot_id IN ({placeholders}) ORDER BY id",
                tuple(sorted(self.token_snapshot_ids)),
            ).fetchall():
                self.episode_snapshot_ids.add(int(row[0]))

    def checkpoint(
        self,
        connection: sqlite3.Connection,
        factory_run_id: str,
        stage: str,
    ) -> None:
        self.record_factory_rows(connection, factory_run_id)
        if self.proof_fault == stage:
            raise PostHandoffInjectedFault(stage)

    def record_token_snapshot(self, snapshot_id: int) -> None:
        self.token_snapshot_ids.add(int(snapshot_id))

    def record_lifecycle_event_ids(self, event_ids: tuple[int, ...]) -> None:
        self.lifecycle_event_ids.update(int(value) for value in event_ids)

    def freeze(self) -> PostHandoffCompensationScope:
        return PostHandoffCompensationScope(
            campaign_id=self.campaign_id,
            run_id=self.run_id,
            cycle_id=self.cycle_id,
            factory_run_id=self.factory_run_id,
            selection_batch_id=self.selection_batch_id,
            activated_token_ids=tuple(sorted(self.activated_token_ids)),
            activated_pair_ids=tuple(sorted(self.activated_pair_ids)),
            executor_first_15m_job_ids=tuple(
                sorted(self.executor_first_15m_job_ids)
            ),
            lifecycle_scheduler_job_ids=tuple(
                sorted(self.lifecycle_scheduler_job_ids)
            ),
            run_step_ids=tuple(sorted(self.run_step_ids)),
            lifecycle_event_ids=tuple(sorted(self.lifecycle_event_ids)),
            token_snapshot_ids=tuple(sorted(self.token_snapshot_ids)),
            episode_snapshot_ids=tuple(sorted(self.episode_snapshot_ids)),
            owned_lease_ids=tuple(sorted(self.owned_lease_ids)),
        )


class PostHandoffCompensationError(RuntimeError):
    """Structured exact-scope compensation or verification failure."""

    def __init__(
        self,
        code: str,
        *,
        operation: str,
        table: str,
        scope: PostHandoffCompensationScope,
        sqlite_error_category: str | None = None,
        rollback_completed: bool,
        first_terminal_cause: str | None = None,
        detail: str = "",
    ) -> None:
        self.code = code
        self.operation = operation
        self.table = table
        self.campaign_id = scope.campaign_id
        self.run_id = scope.run_id
        self.cycle_id = scope.cycle_id
        self.sqlite_error_category = sqlite_error_category
        self.rollback_completed = rollback_completed
        self.first_terminal_cause = first_terminal_cause
        self.detail = detail
        super().__init__(
            f"{code}:operation={operation}:table={table}:"
            f"campaign={scope.campaign_id}:run={scope.run_id}:"
            f"cycle={scope.cycle_id}:sqlite={sqlite_error_category or 'NONE'}:"
            f"rollback_completed={str(rollback_completed).lower()}:"
            f"first_terminal_cause={first_terminal_cause or 'NONE'}:"
            f"detail={detail}"
        )


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
        SELECT s.token_slot_id, s.slot_ordinal, s.token_row_id, s.pair_row_id,
               s.mint_identity, s.pair_identity, s.token_state,
               p.pair_address, t.token_status
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
    scope_recorder: _PostHandoffScopeRecorder | None = None,
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
    if scope_recorder is not None:
        scope_recorder.selection_batch_id = batch_id
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


def _open_compensation_connection(
    db_path: str | Path, *, phase: str
) -> sqlite3.Connection:
    """Narrow proof seam for phase-specific SQLite fault injection."""
    del phase
    return sqlite3.connect(Path(db_path))


def _compensation_sql_fault_hook(operation: str, table: str) -> None:
    """No-op proof seam for operation-specific SQLite error injection."""
    del operation, table


def _unrelated_compensation_snapshot(
    connection: sqlite3.Connection, scope: PostHandoffCompensationScope
) -> dict[str, tuple[tuple[Any, ...], ...]]:
    """Ordered content snapshot of same-token history and unrelated owners."""
    token_ids = scope.activated_token_ids
    token_ph = ",".join("?" * len(token_ids)) if token_ids else "NULL"

    def rows(sql: str, params: tuple[Any, ...] = ()) -> tuple[tuple[Any, ...], ...]:
        return tuple(tuple(row) for row in connection.execute(sql, params).fetchall())

    result: dict[str, tuple[tuple[Any, ...], ...]] = {}
    for label, table, scoped_ids in (
        ("run_steps", "printer_memory_factory_run_steps", scope.run_step_ids),
        (
            "lifecycle_events",
            "printer_token_lifecycle_events",
            scope.lifecycle_event_ids,
        ),
        ("token_snapshots", "printer_token_snapshots", scope.token_snapshot_ids),
    ):
        exclusion = (
            " AND id NOT IN (%s)" % ",".join("?" * len(scoped_ids))
            if scoped_ids
            else ""
        )
        result[label] = rows(
            f"SELECT * FROM {table} WHERE token_id IN ({token_ph})"
            f"{exclusion} ORDER BY id",
            (*token_ids, *scoped_ids),
        )
    episode_exclusion = (
        " AND es.id NOT IN (%s)"
        % ",".join("?" * len(scope.episode_snapshot_ids))
        if scope.episode_snapshot_ids
        else ""
    )
    result["episode_snapshots"] = rows(
        "SELECT es.* FROM printer_episode_snapshots AS es "
        "JOIN printer_token_snapshots AS ts ON ts.id=es.token_snapshot_id "
        f"WHERE ts.token_id IN ({token_ph}){episode_exclusion} ORDER BY es.id",
        (*token_ids, *scope.episode_snapshot_ids),
    )
    result["selection_batches"] = rows(
        "SELECT * FROM printer_selection_batches "
        "WHERE (? IS NULL OR batch_id<>?) ORDER BY id",
        (scope.selection_batch_id, scope.selection_batch_id),
    )
    result["selection_batch_items"] = rows(
        "SELECT * FROM printer_selection_batch_items "
        "WHERE (? IS NULL OR batch_id<>?) ORDER BY id",
        (scope.selection_batch_id, scope.selection_batch_id),
    )
    scoped_jobs = tuple(
        sorted(
            set(scope.executor_first_15m_job_ids)
            | set(scope.lifecycle_scheduler_job_ids)
        )
    )
    job_exclusion = (
        " WHERE id NOT IN (%s)" % ",".join("?" * len(scoped_jobs))
        if scoped_jobs
        else ""
    )
    result["scheduler_jobs"] = rows(
        f"SELECT * FROM printer_scheduler_jobs{job_exclusion} ORDER BY id",
        scoped_jobs,
    )
    lease_exclusion = (
        " WHERE lease_id NOT IN (%s)"
        % ",".join("?" * len(scope.owned_lease_ids))
        if scope.owned_lease_ids
        else ""
    )
    result["leases"] = rows(
        "SELECT * FROM printer_candidate_acquisition_leases"
        f"{lease_exclusion} ORDER BY lease_id",
        scope.owned_lease_ids,
    )
    return result


def _compensate_post_handoff_teardown(
    db_path: str | Path,
    *,
    scope: PostHandoffCompensationScope,
    terminal_cause: str,
    now: str | None = None,
) -> dict[str, Any]:
    """Terminalize only the exact current-attempt post-handoff graph.

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
    residue and cancelling the executor's cycle-scoped first-15m jobs (whose
    in-handoff cancellation rolled back with the failed transaction).
    Candidate-acquisition leases remain outside ordinary-factory authority.

    Idempotent: every step is guarded by current row state, so a second pass
    performs no duplicate transition, cancellation, or deletion.
    """
    from printer_v1.operator_cli.unified_terminal_closure import (
        reconcile_campaign_terminal,
    )

    instant = now or _utc_now()
    campaign_id = scope.campaign_id
    run_id = scope.run_id
    cycle_id = scope.cycle_id
    batch_id = scope.selection_batch_id
    token_ids = list(scope.activated_token_ids)
    pair_ids = set(scope.activated_pair_ids)

    for label, values in (
        ("activated_token_ids", scope.activated_token_ids),
        ("activated_pair_ids", scope.activated_pair_ids),
        ("executor_first_15m_job_ids", scope.executor_first_15m_job_ids),
        ("lifecycle_scheduler_job_ids", scope.lifecycle_scheduler_job_ids),
        ("run_step_ids", scope.run_step_ids),
        ("lifecycle_event_ids", scope.lifecycle_event_ids),
        ("token_snapshot_ids", scope.token_snapshot_ids),
        ("episode_snapshot_ids", scope.episode_snapshot_ids),
        ("owned_lease_ids", scope.owned_lease_ids),
    ):
        if len(values) != len(set(values)):
            raise PostHandoffCompensationError(
                "POST_HANDOFF_COMPENSATION_SCOPE_MISMATCH",
                operation="validate_scope",
                table=label,
                scope=scope,
                rollback_completed=True,
                first_terminal_cause=terminal_cause,
                detail="duplicate IDs are forbidden",
            )
    if set(scope.executor_first_15m_job_ids) & set(
        scope.lifecycle_scheduler_job_ids
    ):
        raise PostHandoffCompensationError(
            "POST_HANDOFF_COMPENSATION_SCOPE_MISMATCH",
            operation="validate_scope",
            table="printer_scheduler_jobs",
            scope=scope,
            rollback_completed=True,
            first_terminal_cause=terminal_cause,
            detail="Scheduler ID appears in two ownership sets",
        )
    if scope.selection_batch_id not in (
        None,
        f"{ORIGIN_BATCH_PREFIX}:{scope.cycle_id}",
    ):
        raise PostHandoffCompensationError(
            "POST_HANDOFF_COMPENSATION_SCOPE_MISMATCH",
            operation="validate_scope",
            table="printer_selection_batches",
            scope=scope,
            rollback_completed=True,
            first_terminal_cause=terminal_cause,
            detail="selection batch is not the exact origin-activated cycle batch",
        )
    if scope.owned_lease_ids:
        raise PostHandoffCompensationError(
            "POST_HANDOFF_COMPENSATION_SCOPE_MISMATCH",
            operation="validate_scope",
            table="printer_candidate_acquisition_leases",
            scope=scope,
            rollback_completed=True,
            first_terminal_cause=terminal_cause,
            detail="ordinary 15m factory owns no candidate-acquisition lease",
        )

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
    cleanup_errors: list[dict[str, Any]] = []
    unrelated_before: dict[str, tuple[tuple[Any, ...], ...]] = {}

    # -- Phase 1: delete deletable residue and cancel exact first-15m/lifecycle
    #    jobs. Candidate-acquisition leases are verification-only here.
    connection = _open_compensation_connection(
        db_path, phase="VERIFY_AND_MUTATE"
    )
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    try:
        connection.execute("BEGIN IMMEDIATE")
        _compensation_sql_fault_hook(
            "lease_verification", "printer_candidate_acquisition_leases"
        )
        unrelated_before = _unrelated_compensation_snapshot(connection, scope)

        def _mismatch(table: str, detail: str) -> None:
            raise PostHandoffCompensationError(
                "POST_HANDOFF_COMPENSATION_SCOPE_MISMATCH",
                operation="verify_ownership",
                table=table,
                scope=scope,
                rollback_completed=False,
                first_terminal_cause=terminal_cause,
                detail=detail,
            )

        def _rows_for_ids(table: str, ids: tuple[Any, ...]) -> list[sqlite3.Row]:
            if not ids:
                return []
            placeholders = ",".join("?" * len(ids))
            return connection.execute(
                f"SELECT * FROM {table} WHERE id IN ({placeholders}) ORDER BY id",
                tuple(ids),
            ).fetchall()

        # Verify the exact run-step/factory-run relationship before mutation.
        run_step_rows = _rows_for_ids(
            "printer_memory_factory_run_steps", scope.run_step_ids
        )
        if scope.factory_run_id is not None:
            actual_run_step_ids = {
                int(row[0])
                for row in connection.execute(
                    "SELECT id FROM printer_memory_factory_run_steps "
                    "WHERE run_id=? ORDER BY id",
                    (scope.factory_run_id,),
                ).fetchall()
            }
            if not actual_run_step_ids.issubset(set(scope.run_step_ids)):
                _mismatch(
                    "printer_memory_factory_run_steps",
                    "factory run contains unrecorded current-attempt rows",
                )
        for row in run_step_rows:
            if (
                scope.factory_run_id is None
                or str(row["run_id"]) != scope.factory_run_id
                or int(row["token_id"]) not in token_ids
                or int(row["pair_id"]) not in pair_ids
            ):
                _mismatch(
                    "printer_memory_factory_run_steps",
                    f"id={row['id']} is not owned by factory run/activated slots",
                )

        # Tables without campaign columns require an exact recorded PK and one
        # of the two activated token/pair identities.
        lifecycle_rows = _rows_for_ids(
            "printer_token_lifecycle_events", scope.lifecycle_event_ids
        )
        for row in lifecycle_rows:
            if int(row["token_id"]) not in token_ids or (
                row["pair_id"] is not None and int(row["pair_id"]) not in pair_ids
            ):
                _mismatch(
                    "printer_token_lifecycle_events",
                    f"id={row['id']} is outside activated token/pair slots",
                )
        snapshot_rows = _rows_for_ids(
            "printer_token_snapshots", scope.token_snapshot_ids
        )
        for row in snapshot_rows:
            if int(row["token_id"]) not in token_ids or (
                row["pair_id"] is not None and int(row["pair_id"]) not in pair_ids
            ):
                _mismatch(
                    "printer_token_snapshots",
                    f"id={row['id']} is outside activated token/pair slots",
                )
        episode_rows = _rows_for_ids(
            "printer_episode_snapshots", scope.episode_snapshot_ids
        )
        for row in episode_rows:
            if int(row["token_snapshot_id"]) not in scope.token_snapshot_ids:
                _mismatch(
                    "printer_episode_snapshots",
                    f"id={row['id']} does not reference a scoped token snapshot",
                )

        if batch_id:
            batch_row = connection.execute(
                "SELECT batch_id FROM printer_selection_batches WHERE batch_id=?",
                (batch_id,),
            ).fetchone()
            if batch_row is not None and str(batch_row["batch_id"]) != batch_id:
                _mismatch(
                    "printer_selection_batches",
                    "selection batch identity mismatch",
                )

        # Verify exact Scheduler ownership: immutable link for executor jobs;
        # exact factory run-step relationship for lifecycle jobs.
        for job_id in scope.executor_first_15m_job_ids:
            linked = connection.execute(
                "SELECT 1 FROM printer_discovery_selected_item_links "
                "WHERE campaign_id=? AND cycle_id=? "
                "AND first_window_15m_scheduler_job_id=?",
                (campaign_id, cycle_id, job_id),
            ).fetchone()
            if linked is None:
                _mismatch(
                    "printer_scheduler_jobs",
                    f"executor first-15m job id={job_id} lacks immutable ownership link",
                )
        for job_id in scope.lifecycle_scheduler_job_ids:
            job_row = connection.execute(
                "SELECT status FROM printer_scheduler_jobs WHERE id=?",
                (job_id,),
            ).fetchone()
            linked = connection.execute(
                "SELECT 1 FROM printer_memory_factory_run_steps "
                "WHERE id IN (%s) AND scheduler_job_id=? AND run_id=?"
                % (
                    ",".join("?" * len(scope.run_step_ids))
                    if scope.run_step_ids
                    else "NULL"
                ),
                (
                    *scope.run_step_ids,
                    job_id,
                    scope.factory_run_id,
                )
                if scope.run_step_ids
                else (job_id, scope.factory_run_id),
            ).fetchone()
            if (
                linked is None
                and job_row is not None
                and str(job_row["status"]) in ACTIVE_STATUS_VALUES
            ):
                _mismatch(
                    "printer_scheduler_jobs",
                    f"lifecycle job id={job_id} lacks exact run-step ownership",
                )

        # Mutate exact primary keys only. Episode links must be removed before
        # their exact token snapshots.
        for label, table, ids in (
            (
                "episode_snapshots",
                "printer_episode_snapshots",
                scope.episode_snapshot_ids,
            ),
            ("lifecycle_events", "printer_token_lifecycle_events", scope.lifecycle_event_ids),
            ("run_steps", "printer_memory_factory_run_steps", scope.run_step_ids),
            ("token_snapshots", "printer_token_snapshots", scope.token_snapshot_ids),
        ):
            if ids:
                _compensation_sql_fault_hook("scoped_row_deletion", table)
                placeholders = ",".join("?" * len(ids))
                deleted[label] = connection.execute(
                    f"DELETE FROM {table} WHERE id IN ({placeholders})",
                    tuple(ids),
                ).rowcount

        if batch_id:
            deleted["selection_batch_items"] = connection.execute(
                "DELETE FROM printer_selection_batch_items WHERE batch_id=?",
                (batch_id,),
            ).rowcount
            deleted["selection_batches"] = connection.execute(
                "DELETE FROM printer_selection_batches WHERE batch_id=?", (batch_id,)
            ).rowcount

        # Cancel the executor's first-15m jobs whose in-handoff cancellation
        # rolled back. Only still-active jobs are cancelled (idempotent replay).
        for job_id in (
            *scope.executor_first_15m_job_ids,
            *scope.lifecycle_scheduler_job_ids,
        ):
            row = connection.execute(
                "SELECT status FROM printer_scheduler_jobs WHERE id=?", (job_id,)
            ).fetchone()
            if row is not None and str(row["status"]) in ACTIVE_STATUS_VALUES:
                _compensation_sql_fault_hook(
                    "first_15m_job_cancellation",
                    "printer_scheduler_jobs",
                )
                cancel_job(connection, job_id=job_id)
                first_15m_cancelled += 1

        connection.commit()
    except PostHandoffCompensationError as exc:
        rollback_completed = False
        try:
            connection.rollback()
            rollback_completed = True
        finally:
            pass
        raise PostHandoffCompensationError(
            exc.code,
            operation=exc.operation,
            table=exc.table,
            scope=scope,
            sqlite_error_category=exc.sqlite_error_category,
            rollback_completed=rollback_completed,
            first_terminal_cause=terminal_cause,
            detail=exc.detail,
        ) from exc
    except sqlite3.Error as exc:
        rollback_completed = False
        try:
            connection.rollback()
            rollback_completed = True
        finally:
            pass
        raise PostHandoffCompensationError(
            "POST_HANDOFF_COMPENSATION_SQL_FAILURE",
            operation="verify_and_mutate_scope",
            table="scoped_compensation",
            scope=scope,
            sqlite_error_category=type(exc).__name__,
            rollback_completed=rollback_completed,
            first_terminal_cause=terminal_cause,
            detail=str(exc),
        ) from exc
    finally:
        connection.close()

    # -- Phase 2: the single terminal authority. Terminalizes slots
    #    (SELECTED -> MANUAL_REVIEW, cause recorded), slot-linked tracking
    #    (QUEUED -> SKIPPED), every campaign-scoped Scheduler job, windows, and
    #    cycle/run/campaign. Idempotent over an already-terminal graph.
    try:
        reconciliation = reconcile_campaign_terminal(
            db_path,
            campaign_id=campaign_id,
            run_id=run_id,
            cycle_id=cycle_id,
            terminal_cause=terminal_cause,
            run_status="FAILED",
            factory_run_id=scope.factory_run_id,
            lifecycle_started=bool(scope.factory_run_id),
            now=instant,
        )
    except sqlite3.Error as exc:
        raise PostHandoffCompensationError(
            "POST_HANDOFF_COMPENSATION_SQL_FAILURE",
            operation="terminal_reconciliation",
            table="campaign_terminal_graph",
            scope=scope,
            sqlite_error_category=type(exc).__name__,
            rollback_completed=False,
            first_terminal_cause=terminal_cause,
            detail=str(exc),
        ) from exc
    except Exception as exc:
        raise PostHandoffCompensationError(
            "POST_HANDOFF_COMPENSATION_TERMINAL_FAILURE",
            operation="terminal_reconciliation",
            table="campaign_terminal_graph",
            scope=scope,
            rollback_completed=False,
            first_terminal_cause=terminal_cause,
            detail=f"{type(exc).__name__}:{exc}",
        ) from exc
    dispositions = reconciliation.get("pre_lifecycle_dispositions", []) or []
    slots_transitioned = sum(
        1
        for d in dispositions
        if str(d.get("slot_disposition")) in _TERMINAL_SLOT_STATES
    )

    # -- Phase 3: deterministic compensation report from a fresh read.
    report_conn = _open_compensation_connection(
        db_path, phase="RESIDUE_VERIFICATION"
    )
    report_conn.row_factory = sqlite3.Row
    report_conn.execute("PRAGMA foreign_keys = ON")
    try:
        _compensation_sql_fault_hook(
            "residue_verification", "scoped_residual_matrix"
        )
        def _count(sql: str, params: tuple = ()) -> int:
            return int(report_conn.execute(sql, params).fetchone()[0])

        cycle_job_ids = list(scope.executor_first_15m_job_ids)
        lifecycle_job_ids = list(scope.lifecycle_scheduler_job_ids)
        all_scoped_job_ids = sorted(set(cycle_job_ids + lifecycle_job_ids))
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
        active_leases = 0
        if scope.owned_lease_ids:
            lease_ph = ",".join("?" * len(scope.owned_lease_ids))
            active_leases = _count(
                "SELECT COUNT(*) FROM printer_candidate_acquisition_leases "
                f"WHERE lease_id IN ({lease_ph}) "
                "AND lease_state IN ('ACTIVE','STOPPING')",
                tuple(scope.owned_lease_ids),
            )
        unrelated_active_leases = _count(
            "SELECT COUNT(*) FROM printer_candidate_acquisition_leases "
            "WHERE lease_state IN ('ACTIVE','STOPPING')"
            + (
                " AND lease_id NOT IN (%s)"
                % ",".join("?" * len(scope.owned_lease_ids))
                if scope.owned_lease_ids
                else ""
            ),
            tuple(scope.owned_lease_ids),
        )
        def _remaining_ids(table: str, ids: tuple[Any, ...]) -> int:
            if not ids:
                return 0
            placeholders = ",".join("?" * len(ids))
            return _count(
                f"SELECT COUNT(*) FROM {table} WHERE id IN ({placeholders})",
                tuple(ids),
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
            + _remaining_ids(
                "printer_memory_factory_run_steps", scope.run_step_ids
            )
            + _remaining_ids(
                "printer_token_lifecycle_events", scope.lifecycle_event_ids
            )
            + _remaining_ids("printer_token_snapshots", scope.token_snapshot_ids)
            + _remaining_ids(
                "printer_episode_snapshots", scope.episode_snapshot_ids
            )
        )
        active_campaign_jobs = int(
            (reconciliation.get("active_work") or {}).get("active_jobs", 0)
        )

        def _state_verification(
            table: str,
            identity_column: str,
            state_column: str,
            identity: str,
            active_states: tuple[str, ...],
        ) -> dict[str, Any]:
            row = report_conn.execute(
                f"SELECT {state_column} FROM {table} WHERE {identity_column}=?",
                (identity,),
            ).fetchone()
            state = None if row is None else str(row[0])
            return {
                "present": row is not None,
                "state": state,
                "active": state in active_states,
            }

        terminal_state_verification = {
            "campaign": _state_verification(
                "printer_memory_factory_campaigns",
                "campaign_id",
                "campaign_state",
                campaign_id,
                ("DRAFT", "PREFLIGHT", "RUNNING", "STOP_REQUESTED"),
            ),
            "run": _state_verification(
                "printer_memory_factory_campaign_runs",
                "run_id",
                "run_state",
                run_id,
                ("DRAFT", "PREFLIGHT", "RUNNING", "STOP_REQUESTED"),
            ),
            "cycle": _state_verification(
                "printer_memory_factory_campaign_cycles",
                "cycle_id",
                "cycle_state",
                cycle_id,
                (
                    "PLANNED",
                    "DISCOVERING",
                    "SELECTING",
                    "TRACKING",
                    "CLOSING",
                    "AUDITING",
                    "ROTATING",
                ),
            ),
        }
        if scope.factory_run_id is not None:
            terminal_state_verification["factory_run"] = _state_verification(
                "printer_memory_factory_runs",
                "run_id",
                "run_status",
                scope.factory_run_id,
                ("RUNNING",),
            )
        active_state_records = sum(
            1
            for state in terminal_state_verification.values()
            if bool(state["active"])
        )
        terminal_states_complete = all(
            bool(state["present"]) and not bool(state["active"])
            for state in terminal_state_verification.values()
        )

        remaining_active_work = {
            "active_slots": slots_active,
            "queued_or_active_tracking": tracking_active,
            "active_first_15m_jobs": first_15m_active,
            "active_campaign_jobs": active_campaign_jobs,
            "active_leases": active_leases,
            "deletable_residue_rows": deletable_remaining,
        }
        active_scoped_lifecycle_jobs = 0
        active_scoped_locks = 0
        if all_scoped_job_ids:
            scoped_job_ph = ",".join("?" * len(all_scoped_job_ids))
            active_scoped_lifecycle_jobs = _count(
                "SELECT COUNT(*) FROM printer_scheduler_jobs "
                f"WHERE id IN ({scoped_job_ph}) "
                f"AND status IN ({active_status_ph})",
                (*all_scoped_job_ids, *ACTIVE_STATUS_VALUES),
            )
            active_scoped_locks = _count(
                "SELECT COUNT(*) FROM printer_scheduler_jobs "
                f"WHERE id IN ({scoped_job_ph}) "
                "AND (locked_at IS NOT NULL OR lock_owner IS NOT NULL)",
                tuple(all_scoped_job_ids),
            )
        remaining_scoped_active_work = {
            **remaining_active_work,
            "active_scoped_lifecycle_jobs": active_scoped_lifecycle_jobs,
            "active_scoped_job_locks": active_scoped_locks,
            "active_campaign_state_records": active_state_records,
        }
        verification_complete = True
        unrelated_after = _unrelated_compensation_snapshot(report_conn, scope)
        historical_rows_preserved = all(
            unrelated_before.get(key) == unrelated_after.get(key)
            for key in (
                "run_steps",
                "lifecycle_events",
                "token_snapshots",
                "episode_snapshots",
                "selection_batches",
                "selection_batch_items",
                "scheduler_jobs",
            )
        )
        unrelated_leases_preserved = (
            unrelated_before.get("leases") == unrelated_after.get("leases")
        )
        verification_complete = (
            verification_complete
            and historical_rows_preserved
            and unrelated_leases_preserved
            and terminal_states_complete
        )
        clean = (
            verification_complete
            and not cleanup_errors
            and all(
                value == 0 for value in remaining_scoped_active_work.values()
            )
        )
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
            "scope": {
                field_name: getattr(scope, field_name)
                for field_name in scope.__dataclass_fields__
            },
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
            "verification_complete": verification_complete,
            "cleanup_errors": tuple(cleanup_errors),
            "remaining_scoped_active_work": remaining_scoped_active_work,
            "historical_rows_preserved": historical_rows_preserved,
            "unrelated_leases_preserved": unrelated_leases_preserved,
            "unrelated_active_leases": unrelated_active_leases,
            "terminal_state_verification": terminal_state_verification,
            "clean_zero_active_work": clean,
            "mutations_this_pass": mutations_this_pass,
            "reconciliation": reconciliation,
        }
    except sqlite3.Error as exc:
        raise PostHandoffCompensationError(
            "POST_HANDOFF_COMPENSATION_SQL_FAILURE",
            operation="residue_verification",
            table="scoped_residual_matrix",
            scope=scope,
            sqlite_error_category=type(exc).__name__,
            rollback_completed=True,
            first_terminal_cause=terminal_cause,
            detail=str(exc),
        ) from exc
    finally:
        report_conn.close()


def _observe_accountable_discovery_stage(
    connection: sqlite3.Connection,
    *,
    command: AbstractCampaignCommand,
    cycle_id: str,
    slots: Sequence[Mapping[str, Any]],
    observer: Callable[[Mapping[str, Any]], Any],
    terminal_status: str,
    first_terminal_cause: str | None,
    cancellation_reason: str | None,
) -> int:
    """Project and observe one real discovery stage from durable identities.

    A failed transaction can legitimately leave no durable rows.  In that case
    this helper returns zero and never manufactures a Scheduler identity or an
    empty stage.  The public finalizer then treats a previously claimed stage as
    missing evidence and fails closed while retaining the operational cause.
    """
    from printer_v1.operator_cli.campaign_ownership import (
        campaign_scheduler_work_id,
        project_campaign_scheduler_work,
    )
    from printer_v1.sources.campaign_six_unit_accounting import (
        build_campaign_stage_id,
    )

    stage_id = build_campaign_stage_id(
        campaign_id=command.campaign_id,
        run_id=command.run_id,
        cycle_id=cycle_id,
        stage_kind="DISCOVERY_SELECTION_SCHEDULER",
        stage_sequence=1,
    )
    projected: list[dict[str, Any]] = []
    discovery_rows = connection.execute(
        """SELECT discovery_work_id,scheduler_job_id,work_type,deadline_at
           FROM printer_discovery_work
           WHERE campaign_id=? AND run_id=? AND cycle_id=?
             AND scheduler_job_id IS NOT NULL
           ORDER BY discovery_work_id""",
        (command.campaign_id, command.run_id, cycle_id),
    ).fetchall()
    for row in discovery_rows:
        job_id = int(row["scheduler_job_id"])
        projection = project_campaign_scheduler_work(
            connection,
            scheduler_work_id=campaign_scheduler_work_id(
                command.campaign_id, job_id
            ),
            campaign_id=command.campaign_id,
            run_id=command.run_id,
            cycle_id=cycle_id,
            work_scope="DISCOVERY_SELECTION",
            stage_id=stage_id,
            work_intent=str(row["work_type"]),
            deadline_at=str(row["deadline_at"]),
            scheduler_job_id=job_id,
            target_category="DISCOVERY_WORK",
            target_identity=str(row["discovery_work_id"]),
        )
        projected.append(
            {
                "stage_id": stage_id,
                "scheduler_job_id": job_id,
                "job_kind": str(row["work_type"]),
                "target_category": "DISCOVERY_WORK",
                "target_identity": str(row["discovery_work_id"]),
                "work_scope": projection.work_scope,
            }
        )
    handoff_rows = connection.execute(
        """SELECT first_window_15m_scheduler_job_id,token_slot_id,
                  merged_candidate_id
           FROM printer_discovery_selected_item_links
           WHERE campaign_id=? AND run_id=? AND cycle_id=?
             AND first_window_15m_scheduler_job_id IS NOT NULL
           ORDER BY selection_item_id""",
        (command.campaign_id, command.run_id, cycle_id),
    ).fetchall()
    for row in handoff_rows:
        job_id = int(row["first_window_15m_scheduler_job_id"])
        job = connection.execute(
            """SELECT scheduled_for,job_kind
               FROM printer_scheduler_jobs WHERE id=?""",
            (job_id,),
        ).fetchone()
        if job is None:
            continue
        project_campaign_scheduler_work(
            connection,
            scheduler_work_id=campaign_scheduler_work_id(
                command.campaign_id, job_id
            ),
            campaign_id=command.campaign_id,
            run_id=command.run_id,
            cycle_id=cycle_id,
            work_scope="FIRST_15M_HANDOFF",
            stage_id=stage_id,
            work_intent="FIRST_15M_HANDOFF",
            deadline_at=str(job["scheduled_for"]),
            scheduler_job_id=job_id,
            target_category="MERGED_CANDIDATE",
            target_identity=str(row["merged_candidate_id"]),
            token_slot_id=str(row["token_slot_id"]),
        )
        projected.append(
            {
                "stage_id": stage_id,
                "scheduler_job_id": job_id,
                "job_kind": str(job["job_kind"]),
                "target_category": "MERGED_CANDIDATE",
                "target_identity": str(row["merged_candidate_id"]),
                "work_scope": "FIRST_15M_HANDOFF",
            }
        )
    if not projected and not slots:
        return 0
    observer(
        {
            "boundary": "DISCOVERY_SELECTION_TERMINAL",
            "stage_id": stage_id,
            "stage_terminal_status": str(terminal_status),
            "stage_first_terminal_cause": first_terminal_cause,
            "cancellation_reason": cancellation_reason,
            "scheduler_work_identities": projected,
            "slots": [dict(row) for row in slots],
        }
    )
    return len(projected) + len(slots)


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
        operational_database_target_binding: Any | None = None,
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
        lifecycle_options = dict(lifecycle_kwargs or {})
        full_run_stage_observer = lifecycle_options.pop(
            "full_run_stage_observer", None
        )

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

        # Classify the activation result before opening, projecting, or sealing
        # any accountable discovery-selection stage. A failed, cancelled,
        # blocked, stopped, or otherwise non-completed activation is already the
        # authoritative terminal for this owner. It must reach the public
        # coordinator unchanged instead of being masked by a later empty-stage
        # observer/accounting failure.
        if activation.terminal_status != "COMPLETED":
            fault_details = dict(activation.fault_details or {})
            propagation_failures = list(
                fault_details.get("propagation_failures") or []
            )
            observer_invoked = False
            evidence_identity_count = 0
            if (
                activation.accountable_stage_started
                and full_run_stage_observer is not None
            ):
                failed_connection = sqlite3.connect(Path(command.db_path))
                failed_connection.row_factory = sqlite3.Row
                failed_connection.execute("PRAGMA foreign_keys = ON")
                try:
                    try:
                        evidence_identity_count = _observe_accountable_discovery_stage(
                            failed_connection,
                            command=command,
                            cycle_id=fixtures.cycle_id,
                            slots=(),
                            observer=full_run_stage_observer,
                            terminal_status=(
                                activation.terminal_status
                                if activation.terminal_status in {"FAILED", "BLOCKED"}
                                else "FAILED"
                            ),
                            first_terminal_cause=activation.first_terminal_cause,
                            cancellation_reason=activation.cancellation_reason,
                        )
                        observer_invoked = evidence_identity_count > 0
                        failed_connection.commit()
                    except Exception as observer_exc:
                        failed_connection.rollback()
                        observer_invoked = True
                        propagation_failures.append(
                            {
                                "stage": "FAILED_DISCOVERY_STAGE_OBSERVER",
                                "exception_class": type(observer_exc).__name__,
                                "sanitized_message": str(observer_exc),
                            }
                        )
                finally:
                    failed_connection.close()
            if (
                activation.accountable_stage_started
                and evidence_identity_count == 0
            ):
                propagation_failures.append(
                    {
                        "stage": "FAILED_DISCOVERY_STAGE_EVIDENCE",
                        "classification": "CLAIMED_STAGE_EVIDENCE_MISSING",
                    }
                )
            if propagation_failures:
                fault_details["propagation_failures"] = propagation_failures
            activation_result = ActivationResult(
                terminal_status=activation.terminal_status,
                first_terminal_cause=activation.first_terminal_cause,
                activated_slots=(),
                selection_batch_id=None,
                cancellation_reason=activation.cancellation_reason,
                fault_details=fault_details or None,
                accountable_stage_started=activation.accountable_stage_started,
                successor_created=activation.successor_created,
                restart_created=activation.restart_created,
            )
            lifecycle = {
                "run_status": "NOT_STARTED",
                "stop_reason": activation.first_terminal_cause,
                "first_terminal_cause": activation.first_terminal_cause,
                "activation_terminal_status": activation.terminal_status,
                "accountable_stage_started": activation.accountable_stage_started,
                "stage_observer_invoked": observer_invoked,
                "stage_evidence_identity_count": evidence_identity_count,
                "successor_created": activation.successor_created,
                "restart_created": activation.restart_created,
            }
            if activation.cancellation_reason is not None:
                lifecycle["cancellation_reason"] = activation.cancellation_reason
            if fault_details:
                lifecycle["fault_details"] = fault_details
            return OriginLifecycleResult(
                activation=activation_result,
                lifecycle=lifecycle,
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
            recorder = _PostHandoffScopeRecorder(
                campaign_id=command.campaign_id,
                run_id=command.run_id,
                cycle_id=fixtures.cycle_id,
                activated_token_ids=tuple(
                    int(slot["token_row_id"]) for slot in committed_slots
                ),
                activated_pair_ids=tuple(
                    int(slot["pair_row_id"]) for slot in committed_slots
                ),
                proof_fault=post_handoff_fault,
            )
            recorder.executor_first_15m_job_ids.update(
                _cycle_first_15m_job_ids(capture_conn, fixtures.cycle_id)
            )
        finally:
            capture_conn.close()

        def _fault_result(fault: PostHandoffInjectedFault) -> OriginLifecycleResult:
            cause = f"POST_HANDOFF_{fault.stage}"
            report = _compensate_post_handoff_teardown(
                command.db_path,
                scope=recorder.freeze(),
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
                    scope_recorder=recorder,
                )
                connection.commit()
                # Observe a completed accountable stage only after a
                # successful activation produced a real two-slot handoff.
                if batch_id is not None and full_run_stage_observer is not None:
                    _observe_accountable_discovery_stage(
                        connection,
                        command=command,
                        cycle_id=fixtures.cycle_id,
                        slots=slots,
                        observer=full_run_stage_observer,
                        terminal_status="COMPLETED",
                        first_terminal_cause=None,
                        cancellation_reason=None,
                    )
            finally:
                connection.close()
        except PostHandoffInjectedFault as fault:
            return _fault_result(fault)

        activation_result = ActivationResult(
            terminal_status=activation.terminal_status,
            first_terminal_cause=activation.first_terminal_cause,
            activated_slots=tuple(slots),
            selection_batch_id=batch_id,
            cancellation_reason=activation.cancellation_reason,
            fault_details=activation.fault_details,
            accountable_stage_started=activation.accountable_stage_started,
            successor_created=activation.successor_created,
            restart_created=activation.restart_created,
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
        runner_scope_kwargs = (
            {
                "_post_handoff_fault": post_handoff_fault,
                "_post_handoff_scope_recorder": recorder,
            }
            if post_handoff_fault is not None
            else {}
        )
        try:
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
                operational_database_target_binding=(
                    operational_database_target_binding
                ),
                max_selected_tokens=2,
                campaign_id=command.campaign_id,
                campaign_run_id=command.run_id,
                cycle_id=fixtures.cycle_id,
                **runner_scope_kwargs,
                **lifecycle_options,
            )
        except PostHandoffInjectedFault as fault:
            return _fault_result(fault)
        return OriginLifecycleResult(
            activation=activation_result,
            lifecycle=lifecycle,
            lifecycle_started=True,
        )
