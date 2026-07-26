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
from typing import Any, Callable

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


@dataclass(frozen=True)
class ActivationResult:
    terminal_status: str
    first_terminal_cause: str
    activated_slots: tuple[dict[str, Any], ...]
    selection_batch_id: str | None


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
    connection: sqlite3.Connection, slots: list[dict[str, Any]]
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
    return cancelled


def materialize_origin_activated_batch(
    connection: sqlite3.Connection,
    *,
    cycle_id: str,
    selection_seed: str,
    tracking_lane: str = "TRACK_NORMAL",
    now: str | None = None,
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

    _cancel_executor_first_15m_jobs(connection, slots)

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
        lifecycle_kwargs: dict[str, Any] | None = None,
    ) -> OriginLifecycleResult:
        """Run one integrated campaign: activation, then lifecycle on those slots."""
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

        connection = sqlite3.connect(Path(command.db_path))
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        try:
            slots = _read_activated_slots(connection, fixtures.cycle_id)
            batch_id = materialize_origin_activated_batch(
                connection,
                cycle_id=fixtures.cycle_id,
                selection_seed=selection_seed,
            )
            connection.commit()
        finally:
            connection.close()

        activation_result = ActivationResult(
            terminal_status=activation.terminal_status,
            first_terminal_cause=activation.first_terminal_cause,
            activated_slots=tuple(slots),
            selection_batch_id=batch_id,
        )

        if batch_id is None:
            # Zero-slot or rolled-back activation: no lifecycle work.
            return OriginLifecycleResult(
                activation=activation_result,
                lifecycle={
                    "run_status": "NOT_STARTED",
                    "stop_reason": "NO_ATOMIC_ACTIVATION",
                    "first_terminal_cause": activation.first_terminal_cause,
                },
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
