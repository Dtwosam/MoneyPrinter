"""V2-4 bounded proof-only one-command WINDOW_15M Memory Factory."""

from __future__ import annotations

import argparse
from dataclasses import asdict, dataclass
import hashlib
import json
import os
import sqlite3
import time
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Callable, Mapping

from printer_v1.discovery.scheduler_parity import reconcile_discovery_work_jobs
from printer_v1.operator_cli.campaign_active_work import campaign_active_work_report
from printer_v1.operator_cli.quality_reporting import (
    build_memory_authority_summary,
    build_window_blocker_summary,
)
from printer_v1.operator_cli.safety_context_source_redundancy import (
    HOLDER_REQUEST_KIND as HOLDER_CONCENTRATION_REQUEST_KIND,
)
from printer_v1.operator_cli.git_provenance import (
    GitProvenanceError,
    capture_git_provenance,
    validate_launch_provenance,
)
from printer_v1.scheduler.contracts import (
    JOB_RESOURCE_CATEGORY_ORDER,
    JobKind,
    LockResult,
    job_resource_category,
)
from printer_v1.scheduler.scheduler import (
    cancel_job,
    claim_due_job,
    complete_job,
    enqueue_job,
    fail_job,
    skip_job,
    yield_job,
)
from printer_v1.scheduler.evidence_deadline import (
    deadline_order_value,
    project_scheduler_job_evidence_deadline,
)
from printer_v1.scheduler.two_token_fairness import (
    deterministic_token_fairness_key,
)
from printer_v1.operator_cli.close_phases import (
    AUDIT_STEP_KINDS,
    CLOSE_PHASE_STEP_KINDS,
    CONTEXT_STEP_KINDS,
    EVIDENCE_STEP_KINDS,
    PRE_CLOSE_STEP_KINDS,
    TERMINAL_CLOSE_STEP_KINDS,
    close_phase_dependency_ready,
    close_phase_metadata,
    close_phase_order,
    resolve_close_context,
    resolve_close_evidence,
    resolve_preclose_manifest,
)
from printer_v1.sources.measured_transport import (
    FIRST_HOUR_SAFETY_CONTEXT_REQUEST_COUNT,
    LIFECYCLE_RESERVED_OPERATIONS_BY_STEP_KIND,
    PRECLOSE_CONTEXT_REQUEST_COUNT,
)


COMMAND_NAME = "printer-run-one-command-15m-memory-factory"
POLICY_VERSION = "ONE_COMMAND_15M_FACTORY_V1"
WINDOW_KIND = "WINDOW_15M"
PERSISTENT_DB_NAME = "printer_v1.sqlite3"

STOP_COMPLETED = "COMPLETED_CLEAN_OR_DIRTY_RESULTS_REPORTED"
STOP_EMPTY = "SAFE_STOP_EMPTY_QUALIFIED_POOL"
STOP_PREFLIGHT = "SAFE_STOP_PREFLIGHT_FAILED"
STOP_SOURCE = "SAFE_STOP_SOURCE_FAILURE"
STOP_DURATION = "SAFE_STOP_TOTAL_DURATION_EXCEEDED"
STOP_INTERRUPTED = "SAFE_STOP_OPERATOR_INTERRUPTED"
STOP_AMBIGUOUS = "SAFE_STOP_AMBIGUOUS_PARTIAL_STEP"
STOP_RUNNING = "SAFE_STOP_RUNNING_JOB_REMAINS"
STOP_DB_DELTA = "SAFE_STOP_UNEXPECTED_DB_DELTA"
# V2-5: global budget/integrity safe stop (run-wide or per-token ceiling breach).
STOP_BUDGET = "SAFE_STOP_BUDGET_CEILING_EXCEEDED"
STOP_TERMINAL_4H = "SAFE_STOP_4H_TERMINAL_INCOMPLETE"
STOP_TWO_TOKEN_PROOF = "SAFE_STOP_TWO_TOKEN_CONTINUOUS_PROOF_INCOMPLETE"

# V2-5: token-local terminal markers (never a run-wide stop).
TOKEN_LOCAL_FAILED = "TOKEN_LOCAL_TERMINAL_FAILURE"
TOKEN_LOCAL_CANCELLED = "TOKEN_LOCAL_CANCELLED_AFTER_FAILURE"

# V2-9.7E.47 A4: the committed 15m close owner (`e2o_memory_window_close`) writes
# `WINDOW_CLOSED`, and the audit path writes `WINDOW_AUDIT_ONLY`. The terminal
# validation previously compared against `COMPLETE`, a value no owner writes, so
# even a fully clean two-token natural stop could never be reported complete.
# `COMPLETE` is retained for pre-existing fixtures.
_TERMINAL_WINDOW_STATUSES = frozenset(
    {"WINDOW_CLOSED", "WINDOW_AUDIT_ONLY", "COMPLETE"}
)

CLEAN_PROMOTED = "CLEAN_PROMOTED"
DIRTY_OR_BLOCKED = "DIRTY_OR_BLOCKED"
ALREADY_EXISTS_IDEMPOTENT = "ALREADY_EXISTS_IDEMPOTENT"
NO_PROMOTION = "NO_PROMOTION"

# V2-5 conservative three-token hard ceilings. These are hard limits, not
# targets; a breach is a global integrity safe-stop, never silently exceeded.
# V2-6.1a: the per-token snapshot count derives from the single authoritative
# cadence policy (WINDOW_15M TRACK_FAST = 16 snapshots) so budgets recalculate
# automatically when the cadence contract changes.
from printer_v1.snapshots.cadence_policy import get_policy as _cadence_get_policy

_V2_5_MAX_SELECTED_TOKENS = 3
_MAX_DISCOVERY_REQUESTS = 2
_CONTEXT_REQUESTS_PER_TOKEN = PRECLOSE_CONTEXT_REQUEST_COUNT
_MAX_HOLDER_FALLBACKS_PER_TOKEN = 1
# V2-9.6: at most one backup Solana-RPC holder endpoint per token, on top of the
# single primary holder fallback. So the holder RPC request budget per token is
# primary + backup = 2.
_MAX_HOLDER_RPC_BACKUP_ENDPOINTS_PER_TOKEN = 1
_MAX_HOLDER_RPC_REQUESTS_PER_TOKEN = (
    _MAX_HOLDER_FALLBACKS_PER_TOKEN + _MAX_HOLDER_RPC_BACKUP_ENDPOINTS_PER_TOKEN
)
_CONTINUATION_SECONDS = 2700.0
_CONTINUOUS_MAX_SELECTED_TOKENS = 1

PRECLOSE_CONTRACT_VERSION = "LANE2_TIMELY_PRECLOSE_V1"
PRECLOSE_RESELECTION_RESERVE_SECONDS = 1.0
_PRECLOSE_TERMINAL_STATES = frozenset(
    {
        "TIMELY",
        "LATE",
        "FAILED",
        "DENIED",
        "REUSED_PERIODIC",
        "MISSED_CUTOFF",
        "UNKNOWN_INTERRUPTED_AFTER_REQUEST",
        "NOT_REQUIRED",
        "CANCELLED_BEFORE_ATTEMPT",
        "CONTEXT_INTEGRITY_BLOCKED",
    }
)

_PRECLOSE_UNIT_DEFINITIONS = {
    "MARKET_CHAIN": ("coingecko", "broad_market_context", "market-chain"),
    "SAFETY_PRIMARY": ("goplus", "safety_reference", "safety"),
    "SAFETY_CORE": ("solana_rpc", "mint_account_reference", "core-safety"),
    "ENTRY_QUOTE": ("jupiter_quote", "paper_quote_realism", "entry"),
    "EXIT_QUOTE": ("jupiter_quote", "paper_quote_realism", "exit"),
    "HOLDER_PRIMARY": (
        "solana_rpc",
        HOLDER_CONCENTRATION_REQUEST_KIND,
        "holder",
    ),
    "HOLDER_BACKUP": (
        "helius_free",
        HOLDER_CONCENTRATION_REQUEST_KIND,
        "holder_backup",
    ),
}


@dataclass(frozen=True)
class CompressedTwoTokenProofPlan:
    """Exact fixture-evidence dispositions for one two-token proof only."""

    continuation_token_mint: str
    non_continuation_token_mint: str
    continuation_evidence: str = "LIQUIDITY_SHOCK_OBSERVED"
    non_continuation_evidence: str = "NO_UNRESOLVED_LEARNING_NEED"
    support_5m_trigger_family: str = "LIQUIDITY_SHOCK"

    def validate_shape(self) -> None:
        if (
            not self.continuation_token_mint
            or not self.non_continuation_token_mint
            or self.continuation_token_mint == self.non_continuation_token_mint
        ):
            raise ValueError("two-token proof requires two distinct mint identities")
        if self.continuation_evidence != "LIQUIDITY_SHOCK_OBSERVED":
            raise ValueError("unsupported continuation proof evidence")
        if self.non_continuation_evidence != "NO_UNRESOLVED_LEARNING_NEED":
            raise ValueError("unsupported non-continuation proof evidence")
        if self.support_5m_trigger_family not in {
            "FAST_COORDINATED_PUMP",
            "FAST_DUMP_OR_COLLAPSE",
            "WICK_OR_LATE_BUY_TRAP",
            "EXIT_REALISM_CHANGE",
            "LIQUIDITY_SHOCK",
            "FAST_BREAKDOWN_OR_RECLAIM",
        }:
            raise ValueError("unsupported support-only 5m trigger family")

    def validate_targets(self, targets: list[dict[str, Any]]) -> None:
        self.validate_shape()
        ordered = [str(target["token_mint"]) for target in targets]
        if len(ordered) != 2 or set(ordered) != {
            self.continuation_token_mint,
            self.non_continuation_token_mint,
        }:
            raise ValueError("two-token proof plan does not match activated targets")

        if ordered[-1] != self.continuation_token_mint:
            raise ValueError(
                "two-token proof continuation target must be the deterministic later target"
            )


@dataclass(frozen=True)
class FourTokenAdmissionBoundaryResult:
    disposition: Any
    admitted: bool
    attempt_id: str | None = None
    attempt_state: str | None = None
    attempt_terminal_cause: str | None = None
    cycle_id: str | None = None
    attempt_wake_at: datetime | None = None


def _later_cycle_acquisition_deadline_conflict(
    *,
    now: datetime,
    earliest_lifecycle_deadline: datetime | None,
    worst_case_quantum_seconds: float,
) -> bool:
    """Return whether one bounded acquisition quantum could cross lifecycle work."""
    if earliest_lifecycle_deadline is None:
        return False
    if worst_case_quantum_seconds <= 0:
        raise ValueError("acquisition quantum duration must be positive")
    current = now.astimezone(timezone.utc)
    deadline = earliest_lifecycle_deadline.astimezone(timezone.utc)
    return current + timedelta(seconds=worst_case_quantum_seconds) >= deadline


def _active_later_cycle_refresh_wake_at(
    connection: sqlite3.Connection,
    *,
    campaign_id: str,
    run_id: str,
    cycle_id: str,
) -> datetime | None:
    """Resolve exactly one WAITING later-cycle temporal-refresh wake, or None.

    CLAIMED or ambiguous active ownership fails closed.
    """
    from printer_v1.discovery.pre_lifecycle_temporal_acquisition import (
        active_refresh_waits,
        parse_iso,
    )

    waits = active_refresh_waits(
        connection,
        campaign_id=str(campaign_id),
        run_id=str(run_id),
        cycle_id=str(cycle_id),
    )
    if not waits:
        return None
    if len(waits) != 1:
        raise ValueError("ambiguous later-cycle refresh wait ownership")
    wait = waits[0]
    state = str(wait["wait_state"] or "")
    if state != "WAITING":
        raise ValueError(
            f"later-cycle refresh wait ownership is not WAITING: {state}"
        )
    return parse_iso(str(wait["scheduled_for"]))


def _cooperative_later_cycle_recheck(
    boundary: FourTokenAdmissionBoundaryResult,
    *,
    next_due_work_at: datetime | None,
    proof_deadline: datetime,
) -> tuple[bool, datetime | None]:
    """Decide whether a RUNNING later-cycle attempt requires coordinator re-entry.

    Returns:
      (False, None) for non-RUNNING attempts;
      (True, None) for a productive cooperative quantum with no refresh wait;
      (True, earliest_due) when a genuine WAITING refresh must bound the wake.
    """
    if str(boundary.attempt_state or "") != "RUNNING":
        return (False, None)
    refresh_due = boundary.attempt_wake_at
    if refresh_due is None:
        return (True, None)
    candidates = [
        refresh_due.astimezone(timezone.utc),
        proof_deadline.astimezone(timezone.utc),
    ]
    if next_due_work_at is not None:
        candidates.append(next_due_work_at.astimezone(timezone.utc))
    return (True, min(candidates))


def _resolve_acquisition_quantum_bound(
    bound: float | Callable[[], float],
) -> float:
    value = bound() if callable(bound) else bound
    seconds = float(value)
    if seconds <= 0:
        raise ValueError("acquisition quantum duration must be positive")
    return seconds


def _later_cycle_attempt_is_terminal(state: str | None) -> bool:
    value = str(state or "")
    return bool(value) and value != "RUNNING"


_CYCLE_LOCAL_MATERIALIZATION_REASONS = frozenset(
    {"UNSUPPORTED_MERGED_CANDIDATE_CHANNEL"}
)


def _terminalize_unstarted_cycle_after_materialization_failure(
    connection: sqlite3.Connection,
    *,
    cycle_id: str,
    terminal_cause: str,
    now: datetime,
) -> None:
    """Atomically isolate one admitted cycle before any lifecycle work exists."""
    if connection.in_transaction:
        raise ValueError("cycle-local isolation requires a clean transaction boundary")
    cause = str(terminal_cause).strip()[:128]
    if not cause:
        raise ValueError("cycle-local isolation requires terminal cause")
    timestamp = now.astimezone(timezone.utc).isoformat()
    cycle = connection.execute(
        "SELECT cycle_state FROM printer_memory_factory_campaign_cycles WHERE cycle_id=?",
        (cycle_id,),
    ).fetchone()
    slots = connection.execute(
        "SELECT token_slot_id,token_state,tracking_queue_id "
        "FROM printer_memory_factory_campaign_token_slots "
        "WHERE cycle_id=? ORDER BY slot_ordinal",
        (cycle_id,),
    ).fetchall()
    windows = int(
        connection.execute(
            "SELECT COUNT(*) FROM printer_memory_factory_campaign_windows WHERE cycle_id=?",
            (cycle_id,),
        ).fetchone()[0]
    )
    work = int(
        connection.execute(
            "SELECT COUNT(*) FROM printer_memory_factory_campaign_scheduler_work WHERE cycle_id=?",
            (cycle_id,),
        ).fetchone()[0]
    )
    if (
        cycle is None
        or str(cycle[0]) != "PLANNED"
        or len(slots) != 2
        or any(str(row[1]) != "SELECTED" for row in slots)
        or windows != 0
        or work != 0
    ):
        raise ValueError("cycle-local materialization isolation preconditions failed")
    connection.execute("BEGIN IMMEDIATE")
    try:
        from printer_v1.operator_cli.cadence_authority import (
            terminalize_unstarted_cycle_tracking_claims,
        )

        # Tracking queue may already be insert-bound by shared Cycle-N cadence
        # activation before materialization. Archive those claims so a never-
        # started cycle does not leave misleading active/queued authority.
        terminalize_unstarted_cycle_tracking_claims(
            connection, cycle_id=cycle_id, now=now
        )
        slot_update = connection.execute(
            """UPDATE printer_memory_factory_campaign_token_slots
               SET token_state='MANUAL_REVIEW',first_terminal_cause=?,
                   terminal_at=?,updated_at=?
               WHERE cycle_id=? AND token_state='SELECTED'""",
            (cause, timestamp, timestamp, cycle_id),
        )
        if slot_update.rowcount != 2:
            raise ValueError("cycle-local slot terminalization failed")
        cycle_update = connection.execute(
            """UPDATE printer_memory_factory_campaign_cycles
               SET cycle_state='TERMINAL_FAILED',first_terminal_cause=?,
                   terminal_at=?,updated_at=?
               WHERE cycle_id=? AND cycle_state='PLANNED'""",
            (cause, timestamp, timestamp, cycle_id),
        )
        if cycle_update.rowcount != 1:
            raise ValueError("cycle-local cycle terminalization failed")
        connection.commit()
    except Exception:
        connection.rollback()
        raise


def _run_four_token_admission_boundary(
    *,
    connection: Any,
    controller: Any,
    binding: Any,
    first_cycle_id: str,
    now: datetime,
    next_due_work_at: datetime | None,
    proof_deadline: datetime,
    project_health: Callable[[], Any],
    evaluate: Callable[[Any], Any],
    later_cycle_callback: Callable[..., Any],
    admit: Callable[..., Any],
    materialize: Callable[..., Any],
    plan_opening: Callable[..., Any],
    source_governor: Any | None = None,
    central_scheduler: Any | None = None,
    clock: Callable[[], datetime] | None = None,
    acquisition_quantum_worst_case_seconds: float | Callable[[], float] = 60.0,
) -> FourTokenAdmissionBoundaryResult:
    """Consume at most one due admission inside the canonical factory loop."""
    from printer_v1.operator_cli.four_token_proof_integration import (
        FourTokenAdmissionDispositionKind,
    )

    pre = project_health()
    disposition = evaluate(pre)
    if disposition.kind is not FourTokenAdmissionDispositionKind.CYCLE_ADMISSION:
        return FourTokenAdmissionBoundaryResult(disposition, False)
    if _later_cycle_acquisition_deadline_conflict(
        now=now,
        earliest_lifecycle_deadline=next_due_work_at,
        worst_case_quantum_seconds=_resolve_acquisition_quantum_bound(
            acquisition_quantum_worst_case_seconds
        ),
    ):
        from printer_v1.operator_cli.four_token_proof_integration import (
            FourTokenAdmissionDisposition,
        )

        return FourTokenAdmissionBoundaryResult(
            FourTokenAdmissionDisposition(
                FourTokenAdmissionDispositionKind.LIFECYCLE_WORK,
                "LIFECYCLE_DEADLINE_PROTECTS_CADENCE",
                next_due_work_at,
                False,
            ),
            False,
        )
    attempt = later_cycle_callback(
        campaign_id=binding.campaign_id,
        campaign_run_id=binding.campaign_run_id,
        authoritative_factory_run_id=binding.authoritative_factory_run_id,
        cycle_id=f"{first_cycle_id}-2",
        cycle_ordinal=2,
        cycle_cutoff=now.isoformat(),
        evaluated_at=now.isoformat(),
        selection_seed=(
            f"{binding.authoritative_factory_run_id}:"
            f"{binding.campaign_run_id}:c0002"
        ),
        source_governor=source_governor,
        central_scheduler=central_scheduler,
        admission_health=pre.health,
    )
    attempt_id = str(getattr(attempt, "attempt_id", "") or "")
    attempt_state = str(getattr(attempt, "state", "") or "")
    attempt_terminal_cause = str(
        getattr(attempt, "first_terminal_cause", "") or ""
    )
    later_cycle_id = f"{first_cycle_id}-2"
    if attempt_state != "PAIR_READY" or not attempt_id:
        wake_at = None
        if attempt_state == "RUNNING":
            wake_at = _active_later_cycle_refresh_wake_at(
                connection,
                campaign_id=str(binding.campaign_id),
                run_id=str(binding.campaign_run_id),
                cycle_id=later_cycle_id,
            )
        return FourTokenAdmissionBoundaryResult(
            disposition,
            False,
            attempt_id or None,
            attempt_state or None,
            attempt_terminal_cause or None,
            None,
            wake_at,
        )

    post_now = (clock or (lambda: now))()
    post = project_health()
    post_disposition = evaluate(post)
    if post_disposition.kind is not FourTokenAdmissionDispositionKind.CYCLE_ADMISSION:
        return FourTokenAdmissionBoundaryResult(
            post_disposition, False, attempt_id, attempt_state, None
        )
    admission = admit(
        connection=connection,
        binding=binding,
        policy=controller.policy,
        now=post_now,
        attempt_id=attempt_id,
        health=post.health,
    )
    if getattr(admission, "mutation_performed", False) is not True:
        return FourTokenAdmissionBoundaryResult(
            post_disposition, False, attempt_id, attempt_state, None
        )
    cycle_id = str(getattr(admission, "cycle_id", "") or "")
    from printer_v1.discovery.pre_admission_materialization import (
        PreAdmissionMaterializationError,
    )
    try:
        materialize(
            connection=connection,
            attempt_id=attempt_id,
            campaign_id=binding.campaign_id,
            campaign_run_id=binding.campaign_run_id,
            configuration_id=binding.configuration_id,
            authoritative_factory_run_id=binding.authoritative_factory_run_id,
            cycle_id=cycle_id,
            now=post_now,
        )
    except PreAdmissionMaterializationError as exc:
        persistence_reason = str(getattr(exc, "persistence_reason", "") or "")
        if persistence_reason not in _CYCLE_LOCAL_MATERIALIZATION_REASONS:
            raise
        terminal_cause = (
            f"CYCLE2_MATERIALIZATION_FAILED_{persistence_reason}"
        )[:128]
        _terminalize_unstarted_cycle_after_materialization_failure(
            connection,
            cycle_id=cycle_id,
            terminal_cause=terminal_cause,
            now=post_now,
        )
        return FourTokenAdmissionBoundaryResult(
            post_disposition,
            False,
            attempt_id,
            "CONSUMED",
            terminal_cause,
            cycle_id,
        )
    # Admit already claimed/bound insert-time tracking authority. Require it
    # again before WINDOW_15M opening so unbound slots cannot schedule.
    from printer_v1.operator_cli.cadence_authority import (
        CadenceAuthorityError,
        require_cycle_slot_tracking_authorities,
    )

    try:
        require_cycle_slot_tracking_authorities(
            connection,
            campaign_id=binding.campaign_id,
            run_id=binding.campaign_run_id,
            cycle_id=cycle_id,
            now=post_now,
        )
    except CadenceAuthorityError as exc:
        raise ValueError(
            "campaign slot missing exact tracking cadence authority before "
            f"WINDOW_15M opening: {exc}"
        ) from exc
    plan_opening(cycle_id=cycle_id, cycle_ordinal=2, now=post_now)
    return FourTokenAdmissionBoundaryResult(
        post_disposition, True, attempt_id, "CONSUMED", None, cycle_id
    )


def _cadence_expected_snapshots(lane: str) -> int:
    """Expected WINDOW_15M snapshot count for a lane, from the cadence policy."""
    policy = _cadence_get_policy(WINDOW_KIND, lane)
    if policy is not None:
        return int(policy.minimum_required_snapshots)
    return 16 if lane == "TRACK_FAST" else 9


# Worst-case (TRACK_FAST) per-token snapshot count drives the budgets.
_MAX_SNAPSHOTS_PER_TOKEN = _cadence_expected_snapshots("TRACK_FAST")
_MAX_GOVERNED_REQUESTS_PER_TOKEN = _MAX_SNAPSHOTS_PER_TOKEN + _CONTEXT_REQUESTS_PER_TOKEN
_MAX_GOVERNED_REQUESTS_RUN = (
    _MAX_DISCOVERY_REQUESTS + _V2_5_MAX_SELECTED_TOKENS * _MAX_GOVERNED_REQUESTS_PER_TOKEN
)
# Run-step jobs (one per snapshot) plus one cancelled discovery handoff per token.
_MAX_SCHEDULER_ROWS = (
    _V2_5_MAX_SELECTED_TOKENS * (_MAX_SNAPSHOTS_PER_TOKEN + 3)
    + _V2_5_MAX_SELECTED_TOKENS
)


def _continuation_expected_snapshots(lane: str) -> int:
    policy = _cadence_get_policy("WINDOW_1H", lane)
    if policy is None:
        return 24 if lane == "TRACK_FAST" else 13
    return int(policy.minimum_required_snapshots)


# The exact-pair 1h close also collects one fresh governed safety-only bundle,
# so the per-token continuous ceiling must allow that worst-case reserve or
# budget enforcement would reject the newly approved governed calls.
_CONTINUOUS_MAX_REQUESTS_PER_TOKEN = (
    _MAX_GOVERNED_REQUESTS_PER_TOKEN
    + _continuation_expected_snapshots("TRACK_FAST")
    + FIRST_HOUR_SAFETY_CONTEXT_REQUEST_COUNT
)
_CONTINUOUS_MAX_REQUESTS_RUN = _MAX_DISCOVERY_REQUESTS + _CONTINUOUS_MAX_REQUESTS_PER_TOKEN
_CONTINUOUS_MAX_SCHEDULER_ROWS = (
    _MAX_SNAPSHOTS_PER_TOKEN + 3
    + _continuation_expected_snapshots("TRACK_FAST") + 3
    + _CONTINUOUS_MAX_SELECTED_TOKENS
)
_COMPRESSED_TWO_TOKEN_MAX_REQUESTS_RUN = (
    _CONTINUOUS_MAX_REQUESTS_RUN + _MAX_GOVERNED_REQUESTS_PER_TOKEN
)
_COMPRESSED_TWO_TOKEN_MAX_SCHEDULER_ROWS = (
    _CONTINUOUS_MAX_SCHEDULER_ROWS
    + _MAX_SNAPSHOTS_PER_TOKEN + 3
    + 1  # second exact activation/discovery handoff allowance
)
# Exact selective-1h proof ceilings for two TRACK_FAST tokens. The cadence
# counts include the mandatory 15m and 1h close steps; the Scheduler total also
# includes one discovery/handoff allowance per token.
_SELECTIVE_1H_MAX_REQUESTS_PER_TOKEN = _CONTINUOUS_MAX_REQUESTS_PER_TOKEN
_SELECTIVE_1H_MAX_REQUESTS_RUN = (
    _MAX_DISCOVERY_REQUESTS
    + 2 * _SELECTIVE_1H_MAX_REQUESTS_PER_TOKEN
)
_SELECTIVE_1H_MAX_SCHEDULER_ROWS = 2 * (
    _MAX_SNAPSHOTS_PER_TOKEN + 3
    + _continuation_expected_snapshots("TRACK_FAST") + 3
    + 1
)


def _compressed_two_token_plan(config: Mapping[str, Any]) -> dict[str, str] | None:
    plan = config.get("compressed_two_token_proof_plan")
    return dict(plan) if isinstance(plan, Mapping) else None


def _operational_natural(config: Mapping[str, Any]) -> bool:
    """V2-9.7E.11 operational-natural two-token mode (no predeclared plan)."""
    return bool(config.get("operational_natural_disposition"))


def _two_token_lifecycle(config: Mapping[str, Any]) -> bool:
    """Two-token 15m→1h→4h budget/scheduler shape: compressed proof OR natural.

    Both drive exactly two atomic activations where one token may continue while
    the other stops, so they share the two-token cumulative ceilings. They are
    mutually exclusive (enforced at preflight and at the live owner boundary).
    """
    return _compressed_two_token_plan(config) is not None or _operational_natural(config)


def _selective_1h_lifecycle(config: Mapping[str, Any]) -> bool:
    """True only for the explicit campaign-owned selective WINDOW_1H path."""
    return bool(config.get("selective_1h_continuation"))


def _cumulative_lifecycle_budget_for_run(
    conn: sqlite3.Connection, run_id: str, continuation_lane: str,
    continuing_token_mint: str | None = None,
) -> dict[str, Any]:
    """Return the one-token budget plus only the two-token peer's 15m allowance.

    Compressed proof mode reads the peer from the predeclared plan; operational-
    natural mode reads the peer as the other activated token in the run ledger.
    Both allow exactly two 15m streams where one token continues.
    """
    from printer_v1.operator_cli.one_token_4h_runtime import cumulative_lifecycle_budget

    base = cumulative_lifecycle_budget(continuation_lane)
    request_components = dict(base["request_components"])
    scheduler_components = dict(base["scheduler_components"])
    config = _load_run_config(conn, run_id)
    plan = _compressed_two_token_plan(config)
    peer_mint: str | None = None
    if plan is not None:
        peer_mint = plan["non_continuation_token_mint"]
    elif _operational_natural(config):
        # Operational-natural two-token mode always reserves exactly one peer's
        # 15m allowance (there are two activated tokens; one may continue). When
        # the continuing token is known, the peer is the other token; otherwise
        # any second distinct token gives the same allowance (both share a lane).
        if continuing_token_mint is not None:
            peer_row = conn.execute(
                """SELECT token_mint FROM printer_memory_factory_run_steps
                   WHERE run_id=? AND token_mint!=? ORDER BY token_mint LIMIT 1""",
                (run_id, continuing_token_mint),
            ).fetchone()
            peer_mint = str(peer_row[0]) if peer_row is not None else None
        else:
            distinct = conn.execute(
                """SELECT DISTINCT token_mint FROM printer_memory_factory_run_steps
                   WHERE run_id=? ORDER BY token_mint""",
                (run_id,),
            ).fetchall()
            peer_mint = str(distinct[-1][0]) if len(distinct) >= 2 else None
    if peer_mint is not None:
        row = conn.execute(
            """SELECT tracking_lane FROM printer_memory_factory_run_steps
               WHERE run_id=? AND token_mint=? ORDER BY id LIMIT 1""",
            (run_id, peer_mint),
        ).fetchone()
        if row is None:
            raise _GlobalStop(
                STOP_BUDGET,
                scope="CUMULATIVE_LIFECYCLE",
                detail="two-token peer target missing from run ledger",
            )
        peer_lane = str(row[0])
        peer_policy = _cadence_get_policy(WINDOW_KIND, peer_lane)
        if peer_policy is None:
            raise _GlobalStop(
                STOP_BUDGET,
                scope="CUMULATIVE_LIFECYCLE",
                detail="two-token peer target has no 15m cadence policy",
            )
        request_components["proof_peer_window_15m"] = int(
            peer_policy.minimum_required_snapshots
        ) + _CONTEXT_REQUESTS_PER_TOKEN
        scheduler_components["proof_peer_discovery_handoff"] = 1
        scheduler_components["proof_peer_window_15m"] = (
            int(peer_policy.minimum_required_snapshots) + 2
        )
    return {
        **base,
        "request_components": request_components,
        "request_ceiling": sum(request_components.values()),
        "scheduler_components": scheduler_components,
        "scheduler_ceiling": sum(scheduler_components.values()),
        "compressed_two_token_proof": peer_mint is not None,
    }


class _GlobalStop(Exception):
    """Raised to signal a global safe stop with one authoritative reason."""

    def __init__(
        self, reason: str, *, scope: str | None = None, detail: str | None = None,
    ) -> None:
        super().__init__(reason)
        self.reason = reason
        self.scope = scope
        self.detail = detail


class _ExternalStop(Exception):
    """A cooperative launcher-requested stop with an immutable reason."""

    def __init__(self, reason: str) -> None:
        super().__init__(reason)
        self.reason = reason
        self.terminal_cause = reason


def _check_cancellation(probe: Callable[[], str | None] | None) -> None:
    if probe is None:
        return
    reason = probe()
    if reason:
        raise _ExternalStop(str(reason))


def _sleep_with_cancellation(
    seconds: float,
    *,
    sleep: Callable[[float], None],
    probe: Callable[[], str | None] | None,
) -> None:
    remaining = max(0.0, seconds)
    while remaining:
        _check_cancellation(probe)
        slice_seconds = min(1.0, remaining)
        sleep(slice_seconds)
        remaining -= slice_seconds
    _check_cancellation(probe)


def _emit_supervision_event(enabled: bool, event: str, **payload: Any) -> None:
    if not enabled:
        return
    print(json.dumps({"event": event, "at": _iso(), **payload}, sort_keys=True), flush=True)

_COUNT_TABLES = (
    "printer_source_requests", "printer_source_responses", "printer_source_failures",
    "printer_discovery_candidates", "printer_selection_batches",
    "printer_selection_batch_items", "printer_tracking_queue",
    "printer_scheduler_jobs", "printer_token_snapshots", "printer_memory_windows",
    "printer_memories", "printer_memory_fingerprints",
    "printer_market_regime_snapshots", "printer_solana_chain_heat_snapshots",
    "printer_solana_safety_evidence", "printer_paper_quote_evidence",
    "printer_safety_evidence_composites", "printer_safety_evidence_contributions",
    "printer_memory_retrieval_queries", "printer_memory_retrieval_matches",
    "printer_paper_decisions", "printer_paper_positions",
    "printer_paper_trade_events", "printer_paper_trade_audits",
    "printer_paper_audit_reports", "printer_memory_factory_runs",
    "printer_memory_factory_run_steps",
)

_FORBIDDEN_DELTA_TABLES = (
    "printer_memory_retrieval_queries", "printer_memory_retrieval_matches",
    "printer_paper_decisions", "printer_paper_positions",
    "printer_paper_trade_events", "printer_paper_trade_audits",
    "printer_paper_audit_reports",
)


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _iso(value: datetime | None = None) -> str:
    return (value or _now()).isoformat()


def _json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, default=str)


def _table_count(conn: sqlite3.Connection, table: str) -> int:
    exists = conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (table,)
    ).fetchone()
    return int(conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]) if exists else 0


def _counts(conn: sqlite3.Connection) -> dict[str, int]:
    return {table: _table_count(conn, table) for table in _COUNT_TABLES}


def _deltas(before: dict[str, int], after: dict[str, int]) -> dict[str, int]:
    return {key: after.get(key, 0) - before.get(key, 0) for key in before}


def _config_hash(config: dict[str, Any]) -> str:
    return hashlib.sha256(_json(config).encode("ascii")).hexdigest()


def _is_persistent_db(path: Path) -> bool:
    expected = (Path.cwd() / "data" / PERSISTENT_DB_NAME).resolve()
    return path.resolve() == expected


def _require_schema(conn: sqlite3.Connection) -> None:
    from printer_v1.operator_cli.proof_db_schema_readiness import (
        validate_runtime_schema_connection,
    )

    validate_runtime_schema_connection(conn)


def _build_discovery_args(
    db_path: Path, *, max_selected_tokens: int, max_source_requests: int,
    timeout_seconds: float, selection_seed: str | None,
) -> argparse.Namespace:
    return argparse.Namespace(
        operator_approved=True, chain="solana", max_candidates=max_selected_tokens,
        enrich_15m_market_evidence=False, enrich_t3_token_age=False,
        t3_solana_rpc_url=None, query="pump", timeout_seconds=timeout_seconds,
        source_name="geckoterminal", request_kind=None,
        request_key="v2-4-one-command-discovery",
        max_source_requests=max_source_requests, selection_seed=selection_seed,
        format="json", db_path=str(db_path), project_root=str(Path.cwd()),
    )


def _selected_targets(conn: sqlite3.Connection, batch_id: str) -> list[dict[str, Any]]:
    rows = conn.execute(
        """
        SELECT i.token_mint, i.pair_address, i.tracking_lane,
               t.id AS token_id, p.id AS pair_id
        FROM printer_selection_batch_items i
        JOIN printer_tokens t ON lower(t.token_mint) = lower(i.token_mint)
        JOIN printer_pairs p ON p.token_id = t.id
                            AND lower(p.pair_address) = lower(i.pair_address)
        WHERE i.batch_id = ? AND i.item_status = 'SELECTED'
          AND i.tracking_lane IN ('TRACK_FAST', 'TRACK_NORMAL')
        ORDER BY lower(i.token_mint), lower(i.pair_address)
        """,
        (batch_id,),
    ).fetchall()
    return [dict(row) for row in rows]


def _cycle_targets_for_factory(
    conn: sqlite3.Connection,
    *,
    campaign_id: str,
    campaign_run_id: str,
    cycle_id: str,
) -> list[dict[str, Any]]:
    rows = conn.execute(
        "SELECT s.slot_ordinal,s.token_row_id AS token_id,s.pair_row_id AS pair_id,"
        "s.mint_identity AS token_mint,s.pair_identity AS pair_address,"
        "s.tracking_queue_id,q.tracking_lane,q.token_id AS queue_token_id,"
        "q.pair_id AS queue_pair_id "
        "FROM printer_memory_factory_campaign_token_slots AS s "
        "LEFT JOIN printer_tracking_queue AS q ON q.id = s.tracking_queue_id "
        "WHERE s.campaign_id=? AND s.run_id=? AND s.cycle_id=? "
        "ORDER BY s.slot_ordinal",
        (campaign_id, campaign_run_id, cycle_id),
    ).fetchall()
    if len(rows) != 2 or tuple(int(row[0]) for row in rows) != (1, 2):
        raise ValueError("proof cycle does not own exact two factory targets")
    targets: list[dict[str, Any]] = []
    for row in rows:
        queue_id = row[5]
        lane = None if row[6] is None else str(row[6])
        if queue_id is None or lane not in {"TRACK_FAST", "TRACK_NORMAL"}:
            raise ValueError(
                "campaign slot missing exact tracking cadence authority before "
                "WINDOW_15M opening"
            )
        if int(row[7]) != int(row[1]) or (
            row[8] is not None and int(row[8]) != int(row[2])
        ):
            raise ValueError(
                "campaign slot tracking queue identity mismatch before "
                "WINDOW_15M opening"
            )
        targets.append(
            {
                "token_id": int(row[1]),
                "pair_id": int(row[2]),
                "token_mint": str(row[3]),
                "pair_address": str(row[4]),
                "tracking_lane": lane,
                "tracking_queue_id": int(queue_id),
            }
        )
    return targets


def _cancel_discovery_handoffs(conn: sqlite3.Connection, discovery: dict[str, Any]) -> None:
    for item in discovery.get("discovery_results", []):
        job_id = item.get("scheduler_job_id")
        if job_id is not None:
            cancel_job(conn, job_id=int(job_id))


def _schedule_offsets(lane: str, window_seconds: float) -> list[float]:
    # V2-6.1a: the snapshot count derives from the single authoritative cadence
    # policy (WINDOW_15M FAST=16, NORMAL=9) at the contract's nominal gap.
    attempts = _cadence_expected_snapshots(lane)
    # The opening and window-close jobs perform the boundary snapshot attempts;
    # the interior offsets are evenly spaced at the nominal cadence gap.
    return [
        round(window_seconds * index / (attempts - 1), 6)
        for index in range(1, attempts - 1)
    ]


def _lifecycle_operation_cycle_identity(
    conn: sqlite3.Connection, scheduler_job_id: int
) -> dict[str, Any]:
    """Resolve action-local cycle identity from the canonical Scheduler owner."""
    rows = conn.execute(
        "SELECT campaign_id,run_id AS campaign_run_id,cycle_id,factory_run_id,"
        "token_slot_id,window_id FROM "
        "printer_memory_factory_campaign_scheduler_work "
        "WHERE scheduler_job_id=? AND ownership_contract_version='V2_STAGE_SCOPED' "
        "AND work_scope='WINDOW_LIFECYCLE' ORDER BY scheduler_work_id",
        (int(scheduler_job_id),),
    ).fetchall()
    if len(rows) > 1:
        raise ValueError(
            "lifecycle action-local record has ambiguous cycle ownership"
        )
    if not rows:
        return {}
    row = rows[0]
    return {
        "campaign_id": str(row[0]),
        "campaign_run_id": str(row[1]),
        "cycle_id": str(row[2]),
        "factory_run_id": str(row[3]),
        "token_slot_id": str(row[4]),
        "window_id": str(row[5]),
    }


def _insert_step_and_job(
    conn: sqlite3.Connection, *, run_id: str, target: dict[str, Any],
    step_key: str, step_kind: str, scheduled_for: datetime,
    result_projection: Mapping[str, Any] | None = None,
    operation_observer: Callable[[Mapping[str, Any]], None] | None = None,
) -> int:
    # Scheduler-row ceiling: run-step jobs must stay within the cadence-derived
    # cap. Three TRACK_FAST tokens create _V2_5_MAX_SELECTED_TOKENS *
    # _MAX_SNAPSHOTS_PER_TOKEN run-step jobs; with up to one cancelled discovery
    # handoff per token that is the _MAX_SCHEDULER_ROWS design ceiling.
    run_config = _load_run_config(conn, run_id)
    continuous = bool(run_config.get("continuous_first_hour"))
    selective_1h = _selective_1h_lifecycle(run_config)
    compressed_two_token = _two_token_lifecycle(run_config)
    scheduler_ceiling = _scheduler_ceiling_for_run_config(run_config)
    discovery_handoff_allowance = (
        0
        if bool(run_config.get("four_token_proof"))
        else
        2
        if selective_1h or compressed_two_token
        else _CONTINUOUS_MAX_SELECTED_TOKENS
        if continuous
        else _V2_5_MAX_SELECTED_TOKENS
    )
    if _run_step_job_count(conn, run_id) >= scheduler_ceiling - discovery_handoff_allowance:
        raise _GlobalStop(STOP_BUDGET, scope="CUMULATIVE_LIFECYCLE")
    if step_kind in TERMINAL_CLOSE_STEP_KINDS or step_kind in CLOSE_PHASE_STEP_KINDS:
        job_kind = JobKind.MEMORY_WINDOW_CLOSE
    elif step_kind == "CONTINUATION_SNAPSHOT":
        job_kind = (
            JobKind.TRACK_FAST_1H
            if target["tracking_lane"] == "TRACK_FAST"
            else JobKind.TRACK_NORMAL_1H
        )
    else:
        job_kind = (
            JobKind.TRACK_FAST_FIRST_15M
            if target["tracking_lane"] == "TRACK_FAST"
            else JobKind.TRACK_NORMAL_FIRST_15M
        )
    # Design Lane 1 cadence authority does not require Scheduler target_id
    # binding; keep factory run-step jobs unbound to avoid Lane-2 leakage.
    result, job_id = enqueue_job(
        conn, job_name=f"v2_4_{run_id}_{step_key}", job_kind=job_kind,
        target_table="printer_tracking_queue", target_id=None,
        scheduled_for=scheduled_for,
    )
    if result != LockResult.ACQUIRED or job_id is None:
        raise ValueError(f"scheduler enqueue failed for {step_key}: {result}")
    projection = dict(result_projection) if result_projection is not None else None
    if step_kind in PRE_CLOSE_STEP_KINDS:
        if projection is None:
            raise ValueError("pre-close step requires frozen result projection")
        projection["scheduler_job_id"] = int(job_id)
        projection["intended_close_work_identity"] = str(step_key)
        for unit in projection.get("source_unit_manifest", []):
            role = str(unit["source_unit_identity"])
            request_suffix = _PRECLOSE_UNIT_DEFINITIONS[role][2]
            request_prefix = (
                f"{run_id}:{step_key}:scheduler-{int(job_id)}:"
                f"preclose:{role.lower()}:attempt-1"
            )
            unit.update(
                factory_run_id=str(run_id),
                scheduler_job_id=int(job_id),
                intended_close_work_identity=str(step_key),
                token_id=int(target["token_id"]),
                pair_id=int(target["pair_id"]),
                token_mint=str(target["token_mint"]),
                pair_address=str(target["pair_address"]),
                window_family=str(projection["close_family"]),
                request_key_prefix=request_prefix,
                request_key=f"{request_prefix}:{request_suffix}",
            )
    conn.execute(
        """
        INSERT INTO printer_memory_factory_run_steps
          (run_id, step_key, step_kind, step_status, token_id, pair_id,
           token_mint, pair_address, tracking_lane, scheduled_for,
           scheduler_job_id, result_json, created_at, updated_at)
        VALUES (?, ?, ?, 'PENDING', ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            run_id, step_key, step_kind, target["token_id"], target["pair_id"],
            target["token_mint"], target["pair_address"], target["tracking_lane"],
            _iso(scheduled_for), job_id,
            _json(projection) if projection is not None else None,
            _iso(), _iso(),
        ),
    )
    if bool(run_config.get("four_token_proof")) and (
        step_kind == "SNAPSHOT"
        or step_kind == "WINDOW_CLOSE"
        or step_kind.startswith("WINDOW_CLOSE_")
    ):
        _project_proof_15m_scheduler_owner(
            conn,
            run_id=run_id,
            step_key=step_key,
            step_kind=step_kind,
            scheduled_for=scheduled_for,
            scheduler_job_id=int(job_id),
        )
        if step_kind in PRE_CLOSE_STEP_KINDS:
            _attach_preclose_campaign_owner(conn, scheduler_job_id=int(job_id))
    # V2-9.8B action-local observation at the real Scheduler-enqueue boundary.
    # Verification-only: the observer never mutates factory state and fires only
    # when a coordinator threads it through. Reports exactly what was enqueued.
    if operation_observer is not None:
        operation_observer(
            {
                **_lifecycle_operation_cycle_identity(conn, int(job_id)),
                "boundary": "SCHEDULER_ENQUEUE",
                "run_id": run_id,
                "scheduler_job_id": int(job_id),
                "step_key": step_key,
                "step_kind": step_kind,
                "token_id": int(target["token_id"]),
                "pair_id": int(target["pair_id"]),
            }
        )
    if step_kind in PRE_CLOSE_STEP_KINDS:
        _refresh_preclose_contention_cohorts(conn, run_id=run_id)
    return int(job_id)


def _attach_preclose_campaign_owner(
    conn: sqlite3.Connection, *, scheduler_job_id: int
) -> None:
    """Freeze an already-projected exact campaign owner into the unit manifest."""
    rows = conn.execute(
        """SELECT campaign_id,run_id,cycle_id,token_slot_id,window_id,
                  factory_run_id,scheduler_work_id
           FROM printer_memory_factory_campaign_scheduler_work
           WHERE scheduler_job_id=? AND ownership_contract_version='V2_STAGE_SCOPED'
             AND work_scope='WINDOW_LIFECYCLE'""",
        (int(scheduler_job_id),),
    ).fetchall()
    if len(rows) != 1:
        raise ValueError("PRE_CLOSE_CAMPAIGN_OWNER_AMBIGUOUS")
    step = conn.execute(
        """SELECT * FROM printer_memory_factory_run_steps
           WHERE scheduler_job_id=?""",
        (int(scheduler_job_id),),
    ).fetchone()
    if step is None or str(step["step_kind"]) not in PRE_CLOSE_STEP_KINDS:
        raise ValueError("PRE_CLOSE_CAMPAIGN_STEP_INVALID")
    owner = rows[0]
    payload = _preclose_result_base(step)
    owner_projection = {
        "campaign_id": str(owner["campaign_id"]),
        "campaign_run_id": str(owner["run_id"]),
        "cycle_id": str(owner["cycle_id"]),
        "token_slot_id": str(owner["token_slot_id"]),
        "campaign_window_id": str(owner["window_id"]),
        "campaign_scheduler_work_id": str(owner["scheduler_work_id"]),
    }
    if str(owner["factory_run_id"]) != str(step["run_id"]):
        raise ValueError("PRE_CLOSE_CAMPAIGN_FACTORY_RUN_MISMATCH")
    payload.update(owner_projection)
    for unit in payload["source_unit_manifest"]:
        unit.update(owner_projection)
    conn.execute(
        "UPDATE printer_memory_factory_run_steps SET result_json=?,updated_at=? WHERE id=?",
        (_json(payload), _iso(), int(step["id"])),
    )


def _campaign_work_deadline_for_scheduler_job(
    conn: sqlite3.Connection,
    *,
    scheduler_job_id: int,
    fallback: datetime | str,
) -> str:
    """Keep campaign identity on the immutable evidence cutoff, not mutable fire time."""
    step = conn.execute(
        "SELECT step_kind,result_json FROM printer_memory_factory_run_steps "
        "WHERE scheduler_job_id=?",
        (int(scheduler_job_id),),
    ).fetchone()
    if step is not None and str(step["step_kind"]) in PRE_CLOSE_STEP_KINDS:
        payload = json.loads(str(step["result_json"] or "{}"))
        cutoffs = [
            datetime.fromisoformat(str(unit["acquisition_cutoff_at"]))
            for unit in payload.get("source_unit_manifest", [])
        ]
        if not cutoffs:
            raise ValueError("PRE_CLOSE_CAMPAIGN_DEADLINE_MISSING")
        return min(cutoffs).astimezone(timezone.utc).isoformat()
    return _iso(fallback) if isinstance(fallback, datetime) else str(fallback)


def _preclose_roles_for_family(family: str) -> tuple[str, ...]:
    if family == "WINDOW_CLOSE":
        return (
            "MARKET_CHAIN",
            "SAFETY_PRIMARY",
            "SAFETY_CORE",
            "ENTRY_QUOTE",
            "EXIT_QUOTE",
            "HOLDER_PRIMARY",
            "HOLDER_BACKUP",
        )
    if family == "CONTINUATION_CLOSE":
        return (
            "SAFETY_PRIMARY",
            "SAFETY_CORE",
            "HOLDER_PRIMARY",
            "HOLDER_BACKUP",
        )
    if family == "LONG_CONTINUATION_CLOSE":
        return (
            "MARKET_CHAIN",
            "SAFETY_PRIMARY",
            "SAFETY_CORE",
            "EXIT_QUOTE",
            "HOLDER_PRIMARY",
            "HOLDER_BACKUP",
        )
    raise ValueError(f"unsupported close family: {family}")


def _preclose_phase_plan(
    *,
    family: str,
    prefix: str,
    run_id: str,
    target: Mapping[str, Any],
    window_end_at: datetime,
    earliest_preclose_schedulable_at: datetime,
    timeout_seconds: float,
) -> tuple[str, str, datetime, dict[str, Any]]:
    """Freeze one exact identity-bound resumable pre-close work item."""
    from printer_v1.operator_cli.holder_reliability_budget_control import (
        deterministic_spacing_seconds,
    )

    if window_end_at.tzinfo is None or earliest_preclose_schedulable_at.tzinfo is None:
        raise ValueError("pre-close planning timestamps must be timezone-aware")
    if timeout_seconds <= 0:
        raise ValueError("pre-close timeout must be positive")
    stem = (
        f"{prefix}_window_close"
        if family == "WINDOW_CLOSE"
        else f"{prefix}_continuation_close"
        if family == "CONTINUATION_CLOSE"
        else f"{prefix}_close"
    )
    preclose_key = f"{stem}_pre_close_critical"
    evidence_key = f"{stem}_evidence"
    context_key = f"{stem}_context"
    audit_key = f"{stem}_audit"
    roles = list(_preclose_roles_for_family(family))
    # Equal-cutoff independent roles rotate only by immutable owner identity.
    # Dependencies remain declared in each unit and are not altered by rotation.
    rotation_seed = ":".join(
        (
            str(run_id),
            str(target["token_id"]),
            str(target["pair_id"]),
            family,
            window_end_at.astimezone(timezone.utc).isoformat(),
        )
    )
    rotation = int(hashlib.sha256(rotation_seed.encode("utf-8")).hexdigest(), 16) % len(roles)
    tie_ordinals = {
        role: ordinal
        for ordinal, role in enumerate(roles[rotation:] + roles[:rotation])
    }
    units: list[dict[str, Any]] = []
    for role in roles:
        source_name, request_kind, request_suffix = _PRECLOSE_UNIT_DEFINITIONS[role]
        cutoff = window_end_at
        if family == "LONG_CONTINUATION_CLOSE" and role in {
            "SAFETY_PRIMARY",
            "SAFETY_CORE",
            "EXIT_QUOTE",
            "HOLDER_PRIMARY",
            "HOLDER_BACKUP",
        }:
            cutoff += timedelta(seconds=60)
        bounded_claim_seconds = (
            float(timeout_seconds)
            + float(deterministic_spacing_seconds(source_name))
            + PRECLOSE_RESELECTION_RESERVE_SECONDS
        )
        dependency = (
            "SAFETY_PRIMARY"
            if role == "HOLDER_PRIMARY"
            else "HOLDER_PRIMARY"
            if role == "HOLDER_BACKUP"
            else None
        )
        request_prefix = (
            f"{run_id}:{preclose_key}:preclose:{role.lower()}:attempt-1"
        )
        units.append(
            {
                "source_unit_identity": role,
                "source_name": source_name,
                "request_kind": request_kind,
                "request_key_prefix": request_prefix,
                "request_key": f"{request_prefix}:{request_suffix}",
                "attempt_ordinal": 1,
                "dependency_source_unit_identity": dependency,
                "state": "BLOCKED_DEPENDENCY" if dependency else "PENDING",
                "acquisition_cutoff_at": cutoff.astimezone(timezone.utc).isoformat(),
                "bounded_claim_seconds": bounded_claim_seconds,
                "latest_safe_claim_at": (
                    cutoff - timedelta(seconds=bounded_claim_seconds)
                ).astimezone(timezone.utc).isoformat(),
                "deterministic_tie_ordinal": tie_ordinals[role],
            }
        )
    desired = min(
        datetime.fromisoformat(str(unit["acquisition_cutoff_at"])) for unit in units
    ) - timedelta(
        seconds=sum(float(unit["bounded_claim_seconds"]) for unit in units)
        + len(units) * PRECLOSE_RESELECTION_RESERVE_SECONDS
    )
    earliest = earliest_preclose_schedulable_at.astimezone(timezone.utc)
    schedulable = desired >= earliest
    scheduled_for = desired if schedulable else earliest
    if not schedulable:
        for unit in units:
            unit["state"] = "CANCELLED_BEFORE_ATTEMPT"
            unit["terminal_reason"] = "TIMELY_ACQUISITION_NOT_PRODUCIBLE"
    metadata = close_phase_metadata(
        family=family,
        phase="PRE_CLOSE",
        preclose_step_key=preclose_key,
        evidence_step_key=evidence_key,
        context_step_key=context_key,
    )
    return (
        preclose_key,
        f"{family}_PRE_CLOSE_CRITICAL",
        scheduled_for,
        {
            **metadata,
            "preclose_contract_version": PRECLOSE_CONTRACT_VERSION,
            "factory_run_id": str(run_id),
            "token_id": int(target["token_id"]),
            "pair_id": int(target["pair_id"]),
            "token_mint": str(target["token_mint"]),
            "pair_address": str(target["pair_address"]),
            "tracking_lane": str(target["tracking_lane"]),
            "window_end_at": window_end_at.astimezone(timezone.utc).isoformat(),
            "standalone_desired_preclose_scheduled_for": desired.isoformat(),
            "desired_preclose_scheduled_for": desired.isoformat(),
            "earliest_preclose_schedulable_at": earliest.isoformat(),
            "effective_preclose_scheduled_for": scheduled_for.isoformat(),
            "preclose_plan_state": (
                "SCHEDULABLE"
                if schedulable
                else "TIMELY_ACQUISITION_NOT_PRODUCIBLE"
            ),
            "source_unit_manifest": units,
            "terminal_unit_count": len(units) if not schedulable else 0,
            "provider_attempt_count": 0,
        },
    )


def _refresh_preclose_contention_cohorts(
    conn: sqlite3.Connection, *, run_id: str
) -> None:
    """Freeze overlap-connected single-worker pre-close lead cohorts."""
    rows = conn.execute(
        """SELECT s.*,j.status AS scheduler_status
           FROM printer_memory_factory_run_steps AS s
           JOIN printer_scheduler_jobs AS j ON j.id=s.scheduler_job_id
           WHERE s.run_id=? AND s.step_kind IN (?,?,?)
             AND s.step_status='PENDING' AND j.status IN ('PENDING','COOLDOWN')
           ORDER BY s.id""",
        (str(run_id), *sorted(PRE_CLOSE_STEP_KINDS)),
    ).fetchall()
    candidates: list[dict[str, Any]] = []
    for row in rows:
        payload = _preclose_result_base(row)
        units = list(payload["source_unit_manifest"])
        standalone = datetime.fromisoformat(
            str(payload["standalone_desired_preclose_scheduled_for"])
        )
        cutoff = min(
            datetime.fromisoformat(str(unit["acquisition_cutoff_at"]))
            for unit in units
        )
        candidates.append(
            {
                "row": row,
                "payload": payload,
                "standalone": standalone,
                "cutoff": cutoff,
                "units": units,
            }
        )
    candidates.sort(
        key=lambda item: (
            item["standalone"], item["cutoff"], int(item["row"]["id"])
        )
    )
    components: list[list[dict[str, Any]]] = []
    for item in candidates:
        if not components:
            components.append([item])
            continue
        current = components[-1]
        current_end = max(member["cutoff"] for member in current)
        if item["standalone"] <= current_end:
            current.append(item)
        else:
            components.append([item])
    for component in components:
        all_units = [unit for item in component for unit in item["units"]]
        lead_seconds = sum(
            float(unit["bounded_claim_seconds"]) for unit in all_units
        ) + len(all_units) * PRECLOSE_RESELECTION_RESERVE_SECONDS
        earliest_cutoff = min(
            datetime.fromisoformat(str(unit["acquisition_cutoff_at"]))
            for unit in all_units
        )
        desired = earliest_cutoff - timedelta(seconds=lead_seconds)
        cohort_members = sorted(
            f"{item['row']['run_id']}:{item['row']['step_key']}:"
            f"{int(item['row']['scheduler_job_id'])}"
            for item in component
        )
        cohort_identity = hashlib.sha256(
            "|".join(cohort_members).encode("utf-8")
        ).hexdigest()
        for item in component:
            row = item["row"]
            payload = item["payload"]
            earliest = datetime.fromisoformat(
                str(payload["earliest_preclose_schedulable_at"])
            )
            schedulable = desired >= earliest
            effective = desired if schedulable else earliest
            payload.update(
                contention_cohort_identity=cohort_identity,
                contention_cohort_members=cohort_members,
                contention_cohort_unit_count=len(all_units),
                cohort_required_lead_seconds=lead_seconds,
                desired_preclose_scheduled_for=desired.isoformat(),
                effective_preclose_scheduled_for=effective.isoformat(),
                preclose_plan_state=(
                    "SCHEDULABLE"
                    if schedulable
                    else "TIMELY_ACQUISITION_NOT_PRODUCIBLE"
                ),
            )
            if not schedulable:
                for unit in payload["source_unit_manifest"]:
                    if str(unit.get("state")) not in _PRECLOSE_TERMINAL_STATES:
                        unit["state"] = "CANCELLED_BEFORE_ATTEMPT"
                        unit["terminal_reason"] = (
                            "TIMELY_ACQUISITION_NOT_PRODUCIBLE"
                        )
                payload["terminal_unit_count"] = len(
                    payload["source_unit_manifest"]
                )
            conn.execute(
                """UPDATE printer_memory_factory_run_steps
                   SET scheduled_for=?,result_json=?,updated_at=? WHERE id=?""",
                (
                    effective.isoformat(),
                    _json(payload),
                    _iso(),
                    int(row["id"]),
                ),
            )
            conn.execute(
                """UPDATE printer_scheduler_jobs SET scheduled_for=?,updated_at=?
                   WHERE id=? AND status IN ('PENDING','COOLDOWN')""",
                (effective.isoformat(), _iso(), int(row["scheduler_job_id"])),
            )


def _close_phase_plan(
    *, family: str, prefix: str
) -> tuple[tuple[str, str, dict[str, Any]], ...]:
    """Build the exact post-preclose dependency projection for one close."""
    stem = (
        f"{prefix}_window_close"
        if family == "WINDOW_CLOSE"
        else f"{prefix}_continuation_close"
        if family == "CONTINUATION_CLOSE"
        else f"{prefix}_4h_close"
    )
    evidence_key = f"{stem}_evidence"
    context_key = f"{stem}_context"
    audit_key = f"{stem}_audit"
    return tuple(
        (
            {"EVIDENCE": evidence_key, "CONTEXT": context_key, "AUDIT": audit_key}[phase],
            f"{family}_{phase}",
            close_phase_metadata(
                family=family,
                phase=phase,
                preclose_step_key=f"{stem}_pre_close_critical",
                evidence_step_key=evidence_key,
                context_step_key=context_key,
            ),
        )
        for phase in ("EVIDENCE", "CONTEXT", "AUDIT")
    )


def _plan_opening_jobs(
    conn: sqlite3.Connection, run_id: str, targets: list[dict[str, Any]],
    scheduled_for: datetime,
    first_commit_callback: Callable[[sqlite3.Connection, str], None] | None = None,
    operation_observer: Callable[[Mapping[str, Any]], None] | None = None,
    cycle_ordinal: int = 1,
    four_token_proof: bool = False,
) -> None:
    if four_token_proof:
        from printer_v1.operator_cli.four_token_proof_integration import cycle_step_key
    for target_index, target in enumerate(targets):
        slot_ordinal = target_index + 1
        if four_token_proof:
            _precreate_proof_15m_window(
                conn,
                run_id=run_id,
                cycle_ordinal=cycle_ordinal,
                slot_ordinal=slot_ordinal,
                target=target,
                checkpoint_cutoff=_iso(scheduled_for),
            )
        step_key = (
            cycle_step_key(
                slot_ordinal=slot_ordinal,
                cycle_ordinal=cycle_ordinal,
                suffix="snapshot_00",
            )
            if four_token_proof
            else f"t{slot_ordinal}_snapshot_00"
        )
        _insert_step_and_job(
            conn, run_id=run_id, target=target,
            step_key=step_key, step_kind="SNAPSHOT",
            scheduled_for=scheduled_for, operation_observer=operation_observer,
        )
        if target_index == 0 and first_commit_callback is not None:
            conn.commit()
            first_commit_callback(conn, run_id)


def _proof_15m_owner(
    conn: sqlite3.Connection,
    *,
    run_id: str,
    cycle_ordinal: int,
    slot_ordinal: int,
) -> dict[str, Any]:
    config = _load_run_config(conn, run_id)
    campaign_id = str(config.get("campaign_id") or "")
    campaign_run_id = str(config.get("campaign_run_id") or "")
    if not campaign_id or not campaign_run_id:
        raise ValueError("proof 15m ownership campaign identity missing")
    row = conn.execute(
        "SELECT c.cycle_id,s.token_slot_id,s.token_row_id,s.pair_row_id,"
        "s.lifecycle_identity,w.window_id "
        "FROM printer_memory_factory_campaign_cycles AS c "
        "JOIN printer_memory_factory_campaign_token_slots AS s "
        "ON s.campaign_id=c.campaign_id AND s.run_id=c.run_id AND s.cycle_id=c.cycle_id "
        "LEFT JOIN printer_memory_factory_campaign_windows AS w "
        "ON w.campaign_id=s.campaign_id AND w.run_id=s.run_id "
        "AND w.cycle_id=s.cycle_id AND w.token_slot_id=s.token_slot_id "
        "AND w.window_kind='WINDOW_15M' "
        "WHERE c.campaign_id=? AND c.run_id=? AND c.cycle_ordinal=? "
        "AND s.slot_ordinal=?",
        (campaign_id, campaign_run_id, cycle_ordinal, slot_ordinal),
    ).fetchone()
    if row is None:
        raise ValueError("proof 15m cycle/slot ownership missing")
    return {
        "campaign_id": campaign_id,
        "campaign_run_id": campaign_run_id,
        "cycle_id": str(row[0]),
        "token_slot_id": str(row[1]),
        "token_row_id": int(row[2]),
        "pair_row_id": int(row[3]),
        "lifecycle_identity": str(row[4]),
        "window_id": None if row[5] is None else str(row[5]),
    }


def _precreate_proof_15m_window(
    conn: sqlite3.Connection,
    *,
    run_id: str,
    cycle_ordinal: int,
    slot_ordinal: int,
    target: Mapping[str, Any],
    checkpoint_cutoff: str,
) -> str:
    owner = _proof_15m_owner(
        conn,
        run_id=run_id,
        cycle_ordinal=cycle_ordinal,
        slot_ordinal=slot_ordinal,
    )
    if (
        owner["token_row_id"] != int(target["token_id"])
        or owner["pair_row_id"] != int(target["pair_id"])
    ):
        raise ValueError("proof 15m target/slot identity mismatch")
    from printer_v1.operator_cli.operational_selective_1h import (
        precreate_15m_campaign_window,
    )

    return precreate_15m_campaign_window(
        conn,
        campaign_id=owner["campaign_id"],
        run_id=owner["campaign_run_id"],
        cycle_id=owner["cycle_id"],
        token_slot_id=owner["token_slot_id"],
        token_row_id=owner["token_row_id"],
        pair_row_id=owner["pair_row_id"],
        lifecycle_identity=owner["lifecycle_identity"],
        checkpoint_cutoff=checkpoint_cutoff,
        now=checkpoint_cutoff,
    )


def _project_proof_15m_scheduler_owner(
    conn: sqlite3.Connection,
    *,
    run_id: str,
    step_key: str,
    step_kind: str,
    scheduled_for: datetime,
    scheduler_job_id: int,
) -> None:
    from printer_v1.operator_cli.campaign_ownership import (
        project_campaign_scheduler_job,
    )
    from printer_v1.operator_cli.four_token_proof_integration import (
        parse_cycle_step_key,
    )

    parsed = parse_cycle_step_key(step_key)
    owner = _proof_15m_owner(
        conn,
        run_id=run_id,
        cycle_ordinal=parsed.cycle_ordinal,
        slot_ordinal=parsed.slot_ordinal,
    )
    if owner["window_id"] is None:
        raise ValueError("proof 15m Scheduler owner window missing")
    project_campaign_scheduler_job(
        conn,
        scheduler_work_id=(
            f"cw15m:{owner['campaign_id']}:{owner['campaign_run_id']}:"
            f"{owner['cycle_id']}:{owner['token_slot_id']}:"
            f"{owner['window_id']}:{scheduler_job_id}"
        ),
        campaign_id=owner["campaign_id"],
        run_id=owner["campaign_run_id"],
        cycle_id=owner["cycle_id"],
        token_slot_id=owner["token_slot_id"],
        window_id=owner["window_id"],
        factory_run_id=run_id,
        work_intent=f"WINDOW_15M_{step_kind}",
        deadline_at=_campaign_work_deadline_for_scheduler_job(
            conn,
            scheduler_job_id=scheduler_job_id,
            fallback=scheduled_for,
        ),
        scheduler_job_id=scheduler_job_id,
        stage_id="WINDOW_15M",
        target_category="CAMPAIGN_WINDOW",
        target_identity=owner["window_id"],
        work_state="PENDING",
    )


def _advance_owned_proof_15m_window(
    conn: sqlite3.Connection,
    *,
    scheduler_job_id: int,
    step_kind: str,
) -> None:
    row = conn.execute(
        "SELECT w.window_id,w.window_state "
        "FROM printer_memory_factory_campaign_scheduler_work AS sw "
        "JOIN printer_memory_factory_campaign_windows AS w ON w.window_id=sw.window_id "
        "WHERE sw.scheduler_job_id=? AND sw.ownership_contract_version='V2_STAGE_SCOPED' "
        "AND sw.work_scope='WINDOW_LIFECYCLE' AND sw.stage_id='WINDOW_15M'",
        (scheduler_job_id,),
    ).fetchone()
    if row is None:
        return
    from printer_v1.operator_cli.campaign_ownership import transition_state

    state = str(row[1])
    window_id = str(row[0])
    if state == "PLANNED":
        transition_state(
            conn,
            record_kind="window",
            identity=window_id,
            expected_state="PLANNED",
            new_state="COLLECTING",
        )
        state = "COLLECTING"
    if step_kind in {"WINDOW_CLOSE", "WINDOW_CLOSE_EVIDENCE"} and state == "COLLECTING":
        transition_state(
            conn,
            record_kind="window",
            identity=window_id,
            expected_state="COLLECTING",
            new_state="CLOSE_PENDING",
        )


def _plan_anchored_jobs(
    conn: sqlite3.Connection, *, run_id: str, opening_step: sqlite3.Row,
    first_snapshot_captured_at: str, window_seconds: float,
    operation_observer: Callable[[Mapping[str, Any]], None] | None = None,
) -> None:
    """Plan one token's remaining work from its persisted opening evidence."""
    anchor = datetime.fromisoformat(first_snapshot_captured_at)
    prefix = str(opening_step["step_key"]).rsplit("_snapshot_", 1)[0]
    target = {
        "token_id": int(opening_step["token_id"]),
        "pair_id": int(opening_step["pair_id"]),
        "token_mint": str(opening_step["token_mint"]),
        "pair_address": str(opening_step["pair_address"]),
        "tracking_lane": str(opening_step["tracking_lane"]),
    }
    for slot_index, offset in enumerate(
        _schedule_offsets(target["tracking_lane"], window_seconds), start=1
    ):
        _insert_step_and_job(
            conn, run_id=run_id, target=target,
            step_key=f"{prefix}_snapshot_{slot_index:02d}", step_kind="SNAPSHOT",
            scheduled_for=anchor + timedelta(seconds=offset),
            operation_observer=operation_observer,
        )
    close_at = anchor + timedelta(seconds=window_seconds)
    run_config = _load_run_config(conn, run_id)
    preclose_key, preclose_kind, preclose_at, preclose_projection = (
        _preclose_phase_plan(
            family="WINDOW_CLOSE",
            prefix=prefix,
            run_id=run_id,
            target=target,
            window_end_at=close_at,
            earliest_preclose_schedulable_at=_now(),
            timeout_seconds=float(run_config.get("timeout_seconds") or 5.0),
        )
    )
    _insert_step_and_job(
        conn,
        run_id=run_id,
        target=target,
        step_key=preclose_key,
        step_kind=preclose_kind,
        scheduled_for=preclose_at,
        result_projection=preclose_projection,
        operation_observer=operation_observer,
    )
    for step_key, step_kind, projection in _close_phase_plan(
        family="WINDOW_CLOSE", prefix=prefix
    ):
        _insert_step_and_job(
            conn,
            run_id=run_id,
            target=target,
            step_key=step_key,
            step_kind=step_kind,
            scheduled_for=close_at,
            result_projection=projection,
            operation_observer=operation_observer,
        )


def _load_run_config(conn: sqlite3.Connection, run_id: str) -> dict[str, Any]:
    row = conn.execute(
        "SELECT config_json FROM printer_memory_factory_runs WHERE run_id=?",
        (run_id,),
    ).fetchone()
    if row is None:
        return {}
    try:
        return json.loads(str(row[0]) or "{}")
    except (TypeError, json.JSONDecodeError):
        return {}


def _plan_continuation_jobs(
    conn: sqlite3.Connection,
    *,
    run_id: str,
    close_step: sqlite3.Row,
    fifteen_m: dict[str, Any],
    continuation_seconds: float,
    ownership_context: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Enqueue one exact-target 45m continuation from a current-run 15m close.

    When the current V2-9.8B campaign supplies ``ownership_context``, every
    created continuation Scheduler job is immediately projected onto the exact
    Checkpoint-1 WINDOW_1H campaign successor through the canonical campaign
    Scheduler-ownership owner. Historical fixture-only callers may omit it.
    """
    from printer_v1.snapshots.lifecycle_continuity import build_1h_continuation_plan

    plan = build_1h_continuation_plan(fifteen_m)
    if not plan.get("enqueue_ok"):
        return {**plan, "planned_jobs": 0}
    close_at = datetime.fromisoformat(str(plan["enqueue_at"]))
    target = {
        "token_id": int(close_step["token_id"]),
        "pair_id": int(close_step["pair_id"]),
        "token_mint": str(close_step["token_mint"]),
        "pair_address": str(close_step["pair_address"]),
        "tracking_lane": str(close_step["tracking_lane"]),
    }
    prefix = _token_prefix(str(close_step["step_key"]))
    expected = _continuation_expected_snapshots(target["tracking_lane"])

    ownership: dict[str, str] | None = None
    if ownership_context is not None:
        required = (
            "campaign_id",
            "campaign_run_id",
            "cycle_id",
            "token_slot_id",
            "campaign_window_1h_id",
            "factory_run_id",
        )
        ownership = {
            key: str(ownership_context.get(key) or "")
            for key in required
        }
        missing = [key for key, value in ownership.items() if not value]
        if missing:
            raise ValueError(
                "continuation Scheduler ownership context missing: "
                + ",".join(missing)
            )
        if ownership["factory_run_id"] != str(run_id):
            raise ValueError("continuation Scheduler ownership factory-run mismatch")

    def insert_owned_job(
        *,
        step_key: str,
        step_kind: str,
        scheduled_for: datetime,
        result_projection: Mapping[str, Any] | None = None,
    ) -> int:
        job_id = _insert_step_and_job(
            conn,
            run_id=run_id,
            target=target,
            step_key=step_key,
            step_kind=step_kind,
            scheduled_for=scheduled_for,
            result_projection=result_projection,
        )
        if ownership is not None:
            from printer_v1.operator_cli.campaign_ownership import (
                project_campaign_scheduler_job,
            )

            project_campaign_scheduler_job(
                conn,
                scheduler_work_id=(
                    f"cw1h:{ownership['campaign_id']}:{ownership['campaign_run_id']}:"
                    f"{ownership['cycle_id']}:{ownership['token_slot_id']}:"
                    f"{ownership['campaign_window_1h_id']}:{job_id}"
                ),
                campaign_id=ownership["campaign_id"],
                run_id=ownership["campaign_run_id"],
                cycle_id=ownership["cycle_id"],
                token_slot_id=ownership["token_slot_id"],
                window_id=ownership["campaign_window_1h_id"],
                factory_run_id=ownership["factory_run_id"],
                work_intent=f"WINDOW_1H_{step_kind}",
                deadline_at=_campaign_work_deadline_for_scheduler_job(
                    conn,
                    scheduler_job_id=int(job_id),
                    fallback=scheduled_for,
                ),
                scheduler_job_id=int(job_id),
                stage_id="WINDOW_1H",
                target_category="CAMPAIGN_WINDOW",
                target_identity=ownership["campaign_window_1h_id"],
                work_state="PENDING",
            )
            if step_kind in PRE_CLOSE_STEP_KINDS:
                _attach_preclose_campaign_owner(
                    conn, scheduler_job_id=int(job_id)
                )
                _refresh_preclose_contention_cohorts(conn, run_id=run_id)
        return int(job_id)

    for index in range(expected - 1):
        offset = continuation_seconds * index / (expected - 1)
        insert_owned_job(
            step_key=f"{prefix}_continuation_snapshot_{index:02d}",
            step_kind="CONTINUATION_SNAPSHOT",
            scheduled_for=close_at + timedelta(seconds=offset),
        )
    continuation_close_at = close_at + timedelta(seconds=continuation_seconds)
    run_config = _load_run_config(conn, run_id)
    preclose_key, preclose_kind, preclose_at, preclose_projection = (
        _preclose_phase_plan(
            family="CONTINUATION_CLOSE",
            prefix=prefix,
            run_id=run_id,
            target=target,
            window_end_at=continuation_close_at,
            earliest_preclose_schedulable_at=_now(),
            timeout_seconds=float(run_config.get("timeout_seconds") or 5.0),
        )
    )
    insert_owned_job(
        step_key=preclose_key,
        step_kind=preclose_kind,
        scheduled_for=preclose_at,
        result_projection=preclose_projection,
    )
    for step_key, step_kind, projection in _close_phase_plan(
        family="CONTINUATION_CLOSE", prefix=prefix
    ):
        insert_owned_job(
            step_key=step_key,
            step_kind=step_kind,
            scheduled_for=continuation_close_at,
            result_projection=projection,
        )
    return {
        **plan,
        "planned_jobs": expected + 3,
        "expected_snapshots": expected,
        "close_phase_jobs": 4,
    }

def _evidence_duration_seconds(start_at: str, end_at: str) -> float:
    start = datetime.fromisoformat(start_at)
    end = datetime.fromisoformat(end_at)
    return (end - start).total_seconds()


def _evidence_duration_is_eligible(
    start_at: str, end_at: str, *, minimum_seconds: float = 900.0,
) -> bool:
    return _evidence_duration_seconds(start_at, end_at) >= minimum_seconds


def _persist_exact_pair_snapshot(
    conn: sqlite3.Connection, step: sqlite3.Row, execution: Any,
) -> dict[str, Any]:
    """Persist one snapshot from a governed exact-pair source response."""
    from printer_v1.operator_cli.e2m_snapshot_persistence import (
        E2M_STATUS_PERSISTED, persist_snapshot_from_source_response,
    )

    persisted = persist_snapshot_from_source_response(
        conn, int(execution.response_record.id), str(step["token_mint"]),
        expected_pair_address=str(step["pair_address"]),
        tracking_lane=str(step["tracking_lane"]),
    )
    out: dict[str, Any] = {
        "snapshot": persisted,
        "snapshot_id": persisted.get("snapshot_id") or persisted.get("existing_snapshot_id"),
        "ok": persisted.get("e2m_status") == E2M_STATUS_PERSISTED,
    }
    if not out["ok"]:
        out["blocked_reason"] = (
            "; ".join(persisted.get("blocked_reasons", [])) or persisted.get("e2m_status")
        )
    return out


def _execute_snapshot(
    conn: sqlite3.Connection, step: sqlite3.Row, *, adapter_factory: Callable[..., Any],
    timeout_seconds: float,
    fallback_adapter_factory: Callable[..., Any] | None = None,
) -> dict[str, Any]:
    """Execute one governed exact-pair snapshot.

    DexScreener is primary. On an eligible transient primary transport failure
    (V2-9.5), one governed GeckoTerminal fallback is attempted. At most one
    snapshot is created per scheduled observation; the original primary failure
    is always preserved; both attempts are separately persisted and budgeted.
    """
    from printer_v1.operator_cli.exact_pair_source_redundancy import (
        execute_geckoterminal_fallback,
        is_eligible_transient_primary_failure,
    )
    from printer_v1.sources.budget_accounting import count_recent_source_requests
    from printer_v1.sources.contracts import build_governed_source_request
    from printer_v1.sources.governed_execution import execute_source_request_with_governor

    from printer_v1.operator_cli.window_15m_concrete_composition import (
        require_concrete_adapter,
    )

    mint = str(step["token_mint"])
    request = build_governed_source_request(
        "dexscreener", "pair_market_snapshot",
        request_key=f"{step['run_id']}:{step['step_key']}",
        payload={"token_mint": mint, "pair_address": step["pair_address"]},
    )
    adapter = require_concrete_adapter(
        "lifecycle_exact_pair_dexscreener_primary",
        adapter_factory(token_mint=mint, timeout_seconds=timeout_seconds),
        expected_source_name="dexscreener",
    )
    execution = execute_source_request_with_governor(
        conn, request, adapter,
        recent_request_count=count_recent_source_requests(conn, "dexscreener"),
    )
    primary = {
        "source_name": "dexscreener",
        "source_request_id": int(execution.request_record.id),
        "source_response_id": (
            int(execution.response_record.id) if execution.response_record else None
        ),
        "source_failure_id": (
            int(execution.failure_record.id) if execution.failure_record else None
        ),
        "source_status": execution.normalized_result.source_status.value,
        "data_quality_label": execution.normalized_result.data_quality_label.value,
        "failure_type": execution.normalized_result.failure_type,
    }
    result: dict[str, Any] = {
        "primary": primary,
        "fallback_attempted": False,
        # Top-level source fields mirror the attempt that produced the snapshot;
        # until a snapshot exists they mirror the primary attempt.
        "source_request_id": primary["source_request_id"],
        "source_response_id": primary["source_response_id"],
        "source_failure_id": primary["source_failure_id"],
        "source_status": primary["source_status"],
        "data_quality_label": primary["data_quality_label"],
        "snapshot_source_name": "dexscreener",
    }

    if execution.response_record is not None:
        # DexScreener-only success path is unchanged.
        result.update(_persist_exact_pair_snapshot(conn, step, execution))
        return result

    # Primary produced no snapshot. Preserve the exact primary failure.
    result["ok"] = False
    result["blocked_reason"] = execution.normalized_result.failure_type or "source_response_missing"

    if fallback_adapter_factory is None or not is_eligible_transient_primary_failure(execution):
        # Non-transient / ineligible primary failure: fail closed, no fallback.
        return result

    # Eligible transient primary failure: one governed GeckoTerminal fallback.
    fb = execute_geckoterminal_fallback(
        conn, step,
        fallback_adapter_factory=fallback_adapter_factory,
        timeout_seconds=timeout_seconds,
    )
    fallback = {
        "source_name": "geckoterminal",
        "source_request_id": int(fb.request_record.id),
        "source_response_id": (
            int(fb.response_record.id) if fb.response_record else None
        ),
        "source_failure_id": (
            int(fb.failure_record.id) if fb.failure_record else None
        ),
        "source_status": fb.normalized_result.source_status.value,
        "data_quality_label": fb.normalized_result.data_quality_label.value,
        "failure_type": fb.normalized_result.failure_type,
    }
    result["fallback_attempted"] = True
    result["fallback"] = fallback
    result["primary_failure_preserved"] = primary["source_failure_id"]

    if fb.response_record is None:
        # Fallback also failed: fail closed on the preserved primary failure.
        result["fallback_ok"] = False
        return result

    persisted = _persist_exact_pair_snapshot(conn, step, fb)
    if not persisted.get("ok"):
        # Invalid fallback response (mismatch / stale / missing fields): fail closed.
        result["fallback_ok"] = False
        result["fallback_blocked_reason"] = persisted.get("blocked_reason")
        return result

    # Fallback produced exactly one valid snapshot. Surface it as the result.
    result["fallback_ok"] = True
    result["snapshot_source_name"] = "geckoterminal"
    result["source_request_id"] = fallback["source_request_id"]
    result["source_response_id"] = fallback["source_response_id"]
    result["source_failure_id"] = None
    result["source_status"] = fallback["source_status"]
    result["data_quality_label"] = fallback["data_quality_label"]
    result["snapshot"] = persisted["snapshot"]
    result["snapshot_id"] = persisted["snapshot_id"]
    result["ok"] = True
    result.pop("blocked_reason", None)
    return result


def _context_execution_summary(execution: Any) -> dict[str, Any]:
    return {
        "source_name": execution.request_record.source_name,
        "request_kind": execution.request_record.request_kind,
        "source_request_id": int(execution.request_record.id),
        "source_response_id": (
            int(execution.response_record.id) if execution.response_record else None
        ),
        "source_failure_id": (
            int(execution.failure_record.id) if execution.failure_record else None
        ),
        "source_status": execution.normalized_result.source_status.value,
        "data_quality_label": execution.normalized_result.data_quality_label.value,
        "failure_type": execution.normalized_result.failure_type,
    }


class PrecloseContextPartialError(RuntimeError):
    """Typed partial-result contract for governed pre-close context collection.

    Raised only when a caller opts in with ``preserve_partial_executions=True``
    (the holder-eligibility funnel). It carries every governed execution that
    really happened before the failure so an already-created
    ``printer_source_requests`` row can never disappear from holder IDs,
    coverage, or campaign reconciliation. The default behaviour for memory-close
    callers is unchanged: the original exception propagates untouched.
    """

    def __init__(
        self,
        code: str,
        *,
        executions: Mapping[str, Any],
        failed_stage: str,
        cause: BaseException | None = None,
    ) -> None:
        self.code = str(code)
        self.executions = dict(executions)
        self.failed_stage = str(failed_stage)
        self.cause = cause
        super().__init__(f"{self.code}:stage={self.failed_stage}")


@dataclass(frozen=True)
class HolderSafetyRequestPlanEntry:
    """One source-free request family in the existing holder safety path."""

    source_name: str
    request_kind: str
    condition: str
    condition_evidence: str
    governed_request_ceiling: int
    underlying_transport_ceiling: int
    rate_limit_owner: str
    execution_owner: str


def holder_safety_request_plan() -> tuple[HolderSafetyRequestPlanEntry, ...]:
    """Project the current GoPlus -> primary RPC -> Helius fallback plan.

    This helper is declarative only.  It derives transport costs from the three
    adapter owners and fails closed if their split stops matching the existing
    aggregate holder-budget contract.
    """
    from printer_v1.operator_cli.holder_reliability_budget_control import (
        HOLDER_WORST_CASE_GOVERNED_REQUESTS,
        HOLDER_WORST_CASE_TRANSPORT_OPERATIONS,
    )
    from printer_v1.sources.goplus import (
        GOPLUS_SAFETY_REQUEST_KIND,
        GOPLUS_SOURCE_NAME,
        GOPLUS_TRANSPORT_OPERATION_COST,
    )
    from printer_v1.sources.helius_holder import (
        HELIUS_HOLDER_TRANSPORT_OPERATION_COST,
        HELIUS_SOURCE_NAME,
    )
    from printer_v1.sources.solana_rpc_holder import (
        SOLANA_RPC_HOLDER_TRANSPORT_OPERATION_COST,
        SOLANA_RPC_SOURCE_NAME,
    )

    request_families = (
        (
            GOPLUS_SOURCE_NAME,
            GOPLUS_SAFETY_REQUEST_KIND,
            "ALWAYS",
            "PRE_CLOSE_SAFETY_REQUESTED",
            GOPLUS_TRANSPORT_OPERATION_COST,
            "_collect_preclose_context",
        ),
        (
            SOLANA_RPC_SOURCE_NAME,
            HOLDER_CONCENTRATION_REQUEST_KIND,
            "GOPLUS_HOLDER_CONCENTRATION_UNKNOWN",
            "GOPLUS_HOLDER_LABEL_EQUALS_UNKNOWN",
            SOLANA_RPC_HOLDER_TRANSPORT_OPERATION_COST,
            "_collect_preclose_context",
        ),
        (
            HELIUS_SOURCE_NAME,
            HOLDER_CONCENTRATION_REQUEST_KIND,
            "ELIGIBLE_TRANSIENT_PRIMARY_FAILURE",
            "is_eligible_transient_solana_rpc_failure",
            HELIUS_HOLDER_TRANSPORT_OPERATION_COST,
            "execute_solana_rpc_holder_backup",
        ),
    )
    if HOLDER_WORST_CASE_GOVERNED_REQUESTS != len(request_families):
        raise RuntimeError("HOLDER_GOVERNED_REQUEST_PLAN_DRIFT")
    governed_request_ceiling = (
        HOLDER_WORST_CASE_GOVERNED_REQUESTS // len(request_families)
    )
    plan = tuple(
        HolderSafetyRequestPlanEntry(
            source_name=source_name,
            request_kind=request_kind,
            condition=condition,
            condition_evidence=condition_evidence,
            governed_request_ceiling=governed_request_ceiling,
            underlying_transport_ceiling=transport_ceiling,
            rate_limit_owner=f"SOURCE_REGISTRY[{source_name}]",
            execution_owner=execution_owner,
        )
        for (
            source_name,
            request_kind,
            condition,
            condition_evidence,
            transport_ceiling,
            execution_owner,
        ) in request_families
    )
    if sum(row.underlying_transport_ceiling for row in plan) != (
        HOLDER_WORST_CASE_TRANSPORT_OPERATIONS
    ):
        raise RuntimeError("HOLDER_TRANSPORT_REQUEST_PLAN_DRIFT")
    return plan


def _collect_preclose_context(
    conn: sqlite3.Connection,
    step: sqlite3.Row,
    *,
    timeout_seconds: float,
    adapter_factories: dict[str, Callable[..., Any]] | None = None,
    include: frozenset[str] | None = None,
    cancellation_probe: Callable[[], str | None] | None = None,
    request_pacer: Any | None = None,
    preserve_partial_executions: bool = False,
    holder_transport_ledger: Any | None = None,
    request_key_prefix: str | None = None,
    source_unit_identity: str | None = None,
) -> dict[str, Any]:
    """Collect a fixed, governed context bundle before the close snapshot.

    ``preserve_partial_executions`` is a holder-specific fail-closed mode. When
    it is ``True`` any failure after one or more governed executions raises
    :class:`PrecloseContextPartialError` carrying those executions. It changes
    no provider or fallback policy and no default caller behaviour.
    """
    from printer_v1.paper_quote.jupiter_fixture import SOURCE_NAME as JUPITER_SOURCE
    from printer_v1.sources.budget_accounting import count_recent_source_requests
    from printer_v1.sources.coingecko import (
        build_coingecko_adapter,
        build_coingecko_market_transport,
    )
    from printer_v1.sources.contracts import build_governed_source_request
    from printer_v1.sources.goplus import (
        GOPLUS_SAFETY_REQUEST_KIND,
        build_goplus_adapter,
        build_goplus_token_safety_transport,
    )
    from printer_v1.sources.governed_execution import execute_source_request_with_governor
    from printer_v1.sources.jupiter_quote import (
        DEFAULT_PAPER_AMOUNT_LAMPORTS,
        DEFAULT_SLIPPAGE_BPS,
        WSOL_MINT,
        build_jupiter_paper_quote_transport,
        build_jupiter_quote_adapter,
    )
    from printer_v1.safety.goplus_normalizer import holder_concentration_label_from_goplus
    from printer_v1.sources.solana_rpc_holder import (
        build_solana_rpc_holder_adapter,
        build_solana_rpc_holder_transport,
    )
    from printer_v1.sources.solana_rpc_token_safety import (
        SOLANA_RPC_TOKEN_SAFETY_REQUEST_KIND,
        build_solana_rpc_token_safety_adapter,
        build_solana_rpc_token_safety_transport,
    )

    factories = adapter_factories or {}
    mint = str(step["token_mint"])
    pair = str(step["pair_address"])
    legacy_request_prefix = f"{step['run_id']}:{step['step_key']}:context"
    explicit_request_prefix = str(request_key_prefix or "").strip()
    request_prefix = explicit_request_prefix or legacy_request_prefix
    # E.24: the sole backup is the fixed Helius Free mainnet endpoint. Tests may
    # inject the new key or the historical fixture key; production has no
    # endpoint override, retry, or rotation.
    from printer_v1.operator_cli.safety_context_source_redundancy import (
        build_default_solana_rpc_holder_backup_adapter,
    )
    backup_source_name = (
        "solana_rpc" if "solana_rpc_holder_backup" in factories
        and "helius_holder_backup" not in factories else "helius_free"
    )
    holder_backup_adapter_factory = (
        factories.get("helius_holder_backup")
        or factories.get("solana_rpc_holder_backup")
        or build_default_solana_rpc_holder_backup_adapter
    )

    def holder_factory_call(factory: Callable[..., Any], **kwargs: Any) -> Any:
        """Pass the ledger only to factories that declare the repaired contract."""
        import inspect

        parameters = inspect.signature(factory).parameters.values()
        accepts_ledger = any(
            parameter.kind is inspect.Parameter.VAR_KEYWORD
            or parameter.name == "measured_transport_ledger"
            for parameter in parameters
        )
        if not accepts_ledger:
            kwargs.pop("measured_transport_ledger", None)
        return factory(**kwargs)

    def execute(source_name: str, request_kind: str, suffix: str, payload: dict[str, Any], adapter: Any) -> Any:
        from printer_v1.db.sqlite_write_contracts import release_write_transaction

        _check_cancellation(cancellation_probe)
        # V2-9.8B.20: pacing sleeps must not hold a deferred write lock.
        release_write_transaction(conn)
        if request_pacer is not None:
            request_pacer.pace(source_name)
        request = build_governed_source_request(
            source_name,
            request_kind,
            request_key=f"{request_prefix}:{suffix}",
            payload={"token_mint": mint, "pair_address": pair, **payload},
        )
        result = execute_source_request_with_governor(
            conn,
            request,
            adapter,
            recent_request_count=count_recent_source_requests(conn, source_name),
        )
        _check_cancellation(cancellation_probe)
        return result

    from printer_v1.operator_cli.window_15m_concrete_composition import (
        require_concrete_adapter,
    )

    market_factory = factories.get("coingecko")
    market_adapter = require_concrete_adapter(
        "preclose_coingecko_market_chain",
        (
            market_factory(timeout_seconds=timeout_seconds)
            if market_factory
            else build_coingecko_adapter(
                enabled=True,
                fixture_transport=build_coingecko_market_transport(
                    timeout_seconds=timeout_seconds
                ),
            )
        ),
        expected_source_name="coingecko",
    )
    safety_factory = factories.get("goplus")
    safety_adapter = require_concrete_adapter(
        "preclose_goplus_safety",
        (
            holder_factory_call(
                safety_factory,
                token_mint=mint,
                timeout_seconds=timeout_seconds,
                measured_transport_ledger=holder_transport_ledger,
            )
            if safety_factory
            else build_goplus_adapter(
                enabled=True,
                fixture_transport=build_goplus_token_safety_transport(
                    mint,
                    timeout_seconds=timeout_seconds,
                    measured_transport_ledger=holder_transport_ledger,
                ),
            )
        ),
        expected_source_name="goplus",
    )
    core_safety_factory = factories.get("solana_rpc_core_safety")
    core_safety_adapter = None
    if core_safety_factory is not None:
        core_safety_adapter = require_concrete_adapter(
            "preclose_solana_rpc_core_safety",
            holder_factory_call(
                core_safety_factory,
                token_mint=mint,
                timeout_seconds=timeout_seconds,
                measured_transport_ledger=holder_transport_ledger,
            ),
            expected_source_name="solana_rpc",
        )
    elif adapter_factories is None:
        core_safety_adapter = require_concrete_adapter(
            "preclose_solana_rpc_core_safety",
            build_solana_rpc_token_safety_adapter(
                enabled=True,
                fixture_transport=build_solana_rpc_token_safety_transport(
                    mint,
                    timeout_seconds=timeout_seconds,
                    measured_transport_ledger=holder_transport_ledger,
                ),
            ),
            expected_source_name="solana_rpc",
        )

    quote_factory = factories.get("jupiter_quote")

    def quote_adapter(input_mint: str, output_mint: str) -> Any:
        if quote_factory:
            return require_concrete_adapter(
                "preclose_jupiter_quote",
                quote_factory(
                    input_mint=input_mint,
                    output_mint=output_mint,
                    amount_lamports=DEFAULT_PAPER_AMOUNT_LAMPORTS,
                    slippage_bps=DEFAULT_SLIPPAGE_BPS,
                    timeout_seconds=timeout_seconds,
                ),
                expected_source_name="jupiter_quote",
            )
        return require_concrete_adapter(
            "preclose_jupiter_quote",
            build_jupiter_quote_adapter(
                enabled=True,
                fixture_transport=build_jupiter_paper_quote_transport(
                    input_mint=input_mint,
                    output_mint=output_mint,
                    amount_lamports=DEFAULT_PAPER_AMOUNT_LAMPORTS,
                    slippage_bps=DEFAULT_SLIPPAGE_BPS,
                    timeout_seconds=timeout_seconds,
                ),
            ),
            expected_source_name="jupiter_quote",
        )

    requested = include or frozenset({"market_chain", "safety", "entry_quote", "exit_quote"})
    executions: dict[str, Any] = {}
    stage = ["context_collection"]

    def _collect_all() -> None:
        if "market_chain" in requested:
            stage[0] = "market_chain"
            executions["market_chain"] = execute(
                "coingecko", "broad_market_context", "market-chain", {}, market_adapter
            )
        if "safety" in requested:
            stage[0] = "safety"
            executions["safety"] = execute(
                "goplus", GOPLUS_SAFETY_REQUEST_KIND, "safety", {}, safety_adapter
            )
            if core_safety_adapter is not None:
                stage[0] = "core_solana_safety"
                executions["core_solana_safety"] = execute(
                    "solana_rpc",
                    SOLANA_RPC_TOKEN_SAFETY_REQUEST_KIND,
                    "core-safety",
                    {},
                    core_safety_adapter,
                )
        if "entry_quote" in requested:
            stage[0] = "entry_quote"
            executions["entry_quote"] = execute(
                JUPITER_SOURCE,
                "paper_quote_realism",
                "entry",
                {
                    "quote_direction": "ENTRY",
                    "input_mint": WSOL_MINT,
                    "output_mint": mint,
                    "amount_lamports": DEFAULT_PAPER_AMOUNT_LAMPORTS,
                },
                quote_adapter(WSOL_MINT, mint),
            )
        if "exit_quote" in requested:
            stage[0] = "exit_quote"
            executions["exit_quote"] = execute(
                JUPITER_SOURCE,
                "paper_quote_realism",
                "exit",
                {
                    "quote_direction": "EXIT",
                    "input_mint": mint,
                    "output_mint": WSOL_MINT,
                    "amount_lamports": DEFAULT_PAPER_AMOUNT_LAMPORTS,
                },
                quote_adapter(mint, WSOL_MINT),
            )
        goplus_holder = (
            holder_concentration_label_from_goplus(
                executions["safety"].normalized_result.normalized_payload
            )
            if "safety" in executions else None
        )
        if goplus_holder == "HOLDER_CONCENTRATION_UNKNOWN":
            stage[0] = "holder_primary"
            holder_factory = factories.get("solana_rpc_holder")
            holder_adapter = require_concrete_adapter(
                "preclose_solana_rpc_holder_primary",
                (
                    holder_factory_call(
                        holder_factory,
                        token_mint=mint,
                        timeout_seconds=timeout_seconds,
                        measured_transport_ledger=holder_transport_ledger,
                    )
                    if holder_factory
                    else build_solana_rpc_holder_adapter(
                        enabled=True,
                        fixture_transport=build_solana_rpc_holder_transport(
                            mint,
                            timeout_seconds=timeout_seconds,
                            measured_transport_ledger=holder_transport_ledger,
                        ),
                    )
                ),
                expected_source_name="solana_rpc",
            )
            primary_holder = execute(
                "solana_rpc",
                HOLDER_CONCENTRATION_REQUEST_KIND,
                "holder",
                {},
                holder_adapter,
            )
            executions["holder_primary"] = primary_holder
            chosen_holder = primary_holder
            # V2-9.6: on an eligible transient primary-RPC failure, attempt exactly
            # one governed backup RPC endpoint. The composite still receives a single
            # holder contribution (the successful attempt, or the preserved primary
            # failure if both fail); both source attempts are persisted and budgeted.
            from printer_v1.operator_cli.safety_context_source_redundancy import (
                execute_solana_rpc_holder_backup,
                is_eligible_transient_solana_rpc_failure,
            )
            if (
                holder_backup_adapter_factory is not None
                and is_eligible_transient_solana_rpc_failure(primary_holder)
            ):
                stage[0] = "holder_backup"
                from printer_v1.db.sqlite_write_contracts import release_write_transaction

                release_write_transaction(conn)
                if request_pacer is not None:
                    request_pacer.pace(backup_source_name)
                backup_holder = execute_solana_rpc_holder_backup(
                    conn,
                    run_id=str(step["run_id"]),
                    step_key=str(step["step_key"]),
                    token_mint=mint,
                    pair_address=pair,
                    backup_adapter_factory=holder_backup_adapter_factory,
                    timeout_seconds=timeout_seconds,
                    source_name=backup_source_name,
                    measured_transport_ledger=holder_transport_ledger,
                    request_key_prefix=request_prefix,
                )
                executions["holder_backup"] = backup_holder
                if backup_holder.response_record is not None:
                    chosen_holder = backup_holder
            executions["holder"] = chosen_holder

    if source_unit_identity is not None:
        unit = str(source_unit_identity)
        if unit == "MARKET_CHAIN":
            executions["market_chain"] = execute(
                "coingecko", "broad_market_context", "market-chain", {}, market_adapter
            )
        elif unit == "SAFETY_PRIMARY":
            executions["safety"] = execute(
                "goplus", GOPLUS_SAFETY_REQUEST_KIND, "safety", {}, safety_adapter
            )
        elif unit == "SAFETY_CORE":
            if core_safety_adapter is None:
                raise ValueError("PRE_CLOSE_SAFETY_CORE_ADAPTER_UNAVAILABLE")
            executions["core_solana_safety"] = execute(
                "solana_rpc",
                SOLANA_RPC_TOKEN_SAFETY_REQUEST_KIND,
                "core-safety",
                {},
                core_safety_adapter,
            )
        elif unit in {"ENTRY_QUOTE", "EXIT_QUOTE"}:
            direction = "ENTRY" if unit == "ENTRY_QUOTE" else "EXIT"
            input_mint = WSOL_MINT if direction == "ENTRY" else mint
            output_mint = mint if direction == "ENTRY" else WSOL_MINT
            executions[f"{direction.lower()}_quote"] = execute(
                JUPITER_SOURCE,
                "paper_quote_realism",
                direction.lower(),
                {
                    "quote_direction": direction,
                    "input_mint": input_mint,
                    "output_mint": output_mint,
                    "amount_lamports": DEFAULT_PAPER_AMOUNT_LAMPORTS,
                },
                quote_adapter(input_mint, output_mint),
            )
        elif unit == "HOLDER_PRIMARY":
            holder_factory = factories.get("solana_rpc_holder")
            holder_adapter = require_concrete_adapter(
                "preclose_solana_rpc_holder_primary",
                (
                    holder_factory_call(
                        holder_factory,
                        token_mint=mint,
                        timeout_seconds=timeout_seconds,
                        measured_transport_ledger=holder_transport_ledger,
                    )
                    if holder_factory
                    else build_solana_rpc_holder_adapter(
                        enabled=True,
                        fixture_transport=build_solana_rpc_holder_transport(
                            mint,
                            timeout_seconds=timeout_seconds,
                            measured_transport_ledger=holder_transport_ledger,
                        ),
                    )
                ),
                expected_source_name="solana_rpc",
            )
            executions["holder_primary"] = execute(
                "solana_rpc",
                HOLDER_CONCENTRATION_REQUEST_KIND,
                "holder",
                {},
                holder_adapter,
            )
            executions["holder"] = executions["holder_primary"]
        elif unit == "HOLDER_BACKUP":
            from printer_v1.db.sqlite_write_contracts import release_write_transaction
            from printer_v1.operator_cli.safety_context_source_redundancy import (
                execute_solana_rpc_holder_backup,
            )

            release_write_transaction(conn)
            if request_pacer is not None:
                request_pacer.pace(backup_source_name)
            executions["holder_backup"] = execute_solana_rpc_holder_backup(
                conn,
                run_id=str(step["run_id"]),
                step_key=str(step["step_key"]),
                token_mint=mint,
                pair_address=pair,
                backup_adapter_factory=holder_backup_adapter_factory,
                timeout_seconds=timeout_seconds,
                source_name=backup_source_name,
                measured_transport_ledger=holder_transport_ledger,
                request_key_prefix=request_prefix,
            )
            executions["holder"] = executions["holder_backup"]
        else:
            raise ValueError(f"unsupported pre-close source unit: {unit}")
    elif not preserve_partial_executions:
        # Default behaviour for memory-close callers is unchanged.
        _collect_all()
    else:
        try:
            _collect_all()
        except Exception as exc:
            raise PrecloseContextPartialError(
                "PRECLOSE_CONTEXT_COLLECTION_FAILED",
                executions=executions,
                failed_stage=stage[0],
                cause=exc,
            ) from exc
    return {
        "executions": executions,
        "report": {
            "source_request_budget": (
                1
                if source_unit_identity is not None
                else len(requested) + (2 if "safety" in requested else 0)
            ),
            "source_requests_attempted": len({id(value) for value in executions.values()}),
            "items": {
                key: _context_execution_summary(value)
                for key, value in executions.items()
            },
        },
    }


def _persist_preclose_context(
    conn: sqlite3.Connection,
    *,
    step: sqlite3.Row,
    snapshot_id: int,
    context_bundle: dict[str, Any],
) -> dict[str, Any]:
    """Bind pre-close governed responses to the exact close snapshot."""
    from printer_v1.operator_cli.commands import (
        _insert_chain_heat_context_from_source_response,
        _insert_market_context_from_source_response,
    )
    from printer_v1.paper_quote.jupiter_fixture import (
        insert_jupiter_quote_fixture_evidence,
    )
    from printer_v1.safety.goplus_normalizer import (
        insert_goplus_safety_evidence_from_source_response,
    )
    from printer_v1.safety.composite import persist_safety_composite

    executions = context_bundle["executions"]
    snapshot = dict(conn.execute(
        "SELECT * FROM printer_token_snapshots WHERE id=?", (snapshot_id,)
    ).fetchone())
    target = {
        "token_id": int(step["token_id"]),
        "pair_id": int(step["pair_id"]),
        "token_mint": str(step["token_mint"]),
        "pair_address": str(step["pair_address"]),
    }
    inserted: dict[str, Any] = {}

    broad = executions.get("market_chain")
    if broad is not None and broad.response_record is not None:
        captured_at = str(broad.response_record.received_at)
        inserted["market_regime_row_id"] = _insert_market_context_from_source_response(
            conn,
            source_response_id=int(broad.response_record.id),
            target=target,
            snapshot=snapshot,
            captured_at=captured_at,
        )
        inserted["chain_heat_row_id"] = _insert_chain_heat_context_from_source_response(
            conn,
            source_response_id=int(broad.response_record.id),
            target=target,
            snapshot=snapshot,
            captured_at=captured_at,
        )

    safety = executions.get("safety")
    if safety is not None and safety.response_record is not None:
        returned_mint = str(
            safety.normalized_result.normalized_payload.get("token_mint") or ""
        )
        if returned_mint.lower() != target["token_mint"].lower():
            inserted["safety"] = {
                "inserted": False,
                "evidence_id": None,
                "clean_eligible": False,
                "audit_status": "REJECTED_TARGET_MINT_MISMATCH",
                "rejection_reasons": ["GOPLUS_TARGET_MINT_MISMATCH"],
            }
        else:
            safety_result = insert_goplus_safety_evidence_from_source_response(
                conn,
                source_response_id=int(safety.response_record.id),
                token_id=target["token_id"],
                pair_id=target["pair_id"],
                snapshot_id=snapshot_id,
                scheduler_boundary_label="SCHEDULER_BOUNDARY_PRESENT",
                operator_approval_label="OPERATOR_APPROVED_MANUAL_PROOF",
                caller="source_governor_scheduler_operator_flow",
            )
            inserted["safety"] = {
                "inserted": safety_result.inserted,
                "evidence_id": safety_result.evidence_id,
                "clean_eligible": safety_result.clean_eligible,
                "audit_status": safety_result.audit_status,
                "rejection_reasons": list(safety_result.rejection_reasons),
            }
    if safety is not None:
        inserted["safety_composite"] = persist_safety_composite(
            conn,
            token_id=target["token_id"],
            pair_id=target["pair_id"],
            snapshot_id=snapshot_id,
            token_mint=target["token_mint"],
            pair_address=target["pair_address"],
            # Context is now a later Scheduler phase. Its evaluation timestamp
            # is the real persistence instant, never the earlier snapshot
            # capture time. The exact snapshot linkage remains unchanged.
            evaluated_at=_iso(),
            goplus_execution=safety,
            holder_execution=executions.get("holder"),
            core_solana_execution=executions.get("core_solana_safety"),
        )

    for key, direction in (("entry_quote", "ENTRY"), ("exit_quote", "EXIT")):
        execution = executions.get(key)
        if execution is None:
            continue
        quote_payload = execution.normalized_result.normalized_payload
        expected_input = (
            str(step["token_mint"])
            if direction == "EXIT"
            else "So11111111111111111111111111111111111111112"
        )
        expected_output = (
            "So11111111111111111111111111111111111111112"
            if direction == "EXIT"
            else str(step["token_mint"])
        )
        if (
            str(quote_payload.get("input_mint") or "").lower()
            != expected_input.lower()
            or str(quote_payload.get("output_mint") or "").lower()
            != expected_output.lower()
        ):
            inserted[key] = {
                "inserted": False,
                "evidence_id": None,
                "clean_eligible": False,
                "audit_status": "REJECTED_TARGET_MINT_MISMATCH",
                "rejection_reasons": ["JUPITER_QUOTE_TARGET_MINT_MISMATCH"],
            }
            continue
        quote_result = insert_jupiter_quote_fixture_evidence(
            conn,
            execution.normalized_result,
            request_record=execution.request_record,
            response_record=execution.response_record,
            failure_record=execution.failure_record,
            quote_direction=direction,
            token_id=target["token_id"],
            pair_id=target["pair_id"],
            snapshot_id=snapshot_id,
            scheduler_boundary_label="SCHEDULER_BOUNDARY_PRESENT",
            operator_approval_label="OPERATOR_APPROVED_MANUAL_PROOF",
            caller="source_governor_scheduler_operator_flow",
        )
        inserted[key] = {
            "inserted": quote_result.inserted,
            "evidence_id": quote_result.evidence_id,
            "clean_eligible": quote_result.clean_eligible,
            "audit_status": quote_result.audit_status,
            "rejection_reasons": list(quote_result.rejection_reasons),
        }
    return inserted


def _attach_context_and_gate_window(
    conn: sqlite3.Connection, *, step: sqlite3.Row, window_id: int,
    snapshot_start_id: int, snapshot_end_id: int,
) -> dict[str, Any]:
    """Attach existing-engine context and fail closed before clean promotion."""
    from printer_v1.context_evidence import build_window_15m_context_evidence
    from printer_v1.operator_cli.commands import (
        _apply_clean_audit_evidence_labels,
        _classify_first_memory_review,
        _context_freshness_report,
        _context_memory_labels,
        _context_row_ids_for_memory,
        _derive_15m_window_context_from_snapshots,
        _insert_controlled_context_rows,
        _resolve_memory_context_rows,
    )

    snapshots = [dict(row) for row in conn.execute(
        """
        SELECT * FROM printer_token_snapshots
        WHERE token_id=? AND pair_id=? AND id BETWEEN ? AND ?
        ORDER BY captured_at, id
        """,
        (step["token_id"], step["pair_id"], snapshot_start_id, snapshot_end_id),
    ).fetchall()]
    if not snapshots:
        raise ValueError("exact snapshot range is empty")
    target = {
        "token_id": int(step["token_id"]),
        "pair_id": int(step["pair_id"]),
        "token_mint": str(step["token_mint"]),
        "pair_address": str(step["pair_address"]),
    }
    end_snapshot = snapshots[-1]
    _insert_controlled_context_rows(
        conn, target, end_snapshot, str(end_snapshot["captured_at"])
    )
    context_rows = _resolve_memory_context_rows(
        conn, target, int(end_snapshot["id"])
    )
    start_at = str(snapshots[0]["captured_at"])
    end_at = str(end_snapshot["captured_at"])
    freshness = _context_freshness_report(
        context_rows, end_snapshot, start_at, end_at
    )
    labels = _context_memory_labels(context_rows)
    derived = _derive_15m_window_context_from_snapshots(snapshots, WINDOW_KIND)
    labels.update(derived.get("labels") or {})
    evidence = _apply_clean_audit_evidence_labels(
        conn,
        window={
            "id": window_id,
            "token_id": target["token_id"],
            "pair_id": target["pair_id"],
            "snapshot_end_id": snapshot_end_id,
            "window_kind": WINDOW_KIND,
        },
        labels=labels,
    )
    try:
        shared_context = build_window_15m_context_evidence(
            conn,
            token_id=target["token_id"],
            pair_id=target["pair_id"],
            snapshot_start_id=snapshot_start_id,
            snapshot_end_id=snapshot_end_id,
            window_start_at=start_at,
            window_end_at=end_at,
            # V2-9.4.8: the closing snapshot is attached to the ledger before
            # this runs (see _attach_closing_snapshot_to_ledger), so the exact
            # current-run ledger identity is now safe to use here.
            #
            # tracking_lane remains deliberately absent: 15m has zero closing
            # evidence allowance even though Lane-2 context executes later.
            run_id=str(step["run_id"]),
        )
    except ValueError as exc:
        shared_context = {
            "clean_memory_context_ready": False,
            "blockers": [f"SHARED_CONTEXT_WINDOW_INVALID:{exc}"],
            "sections": {},
            "writes_performed": False,
        }
    shared_labels: dict[str, Any] = {}
    for section in shared_context.get("sections", {}).values():
        shared_labels.update(section.get("labels") or {})
    effective_labels = {**evidence["labels"], **shared_labels}
    shared_blockers = list(shared_context.get("blockers") or [])
    combined_evidence_blockers = list(dict.fromkeys(
        list(evidence["overlays"].get("evidence_blockers", []))
        + shared_blockers
    ))
    classification = _classify_first_memory_review(
        snapshots,
        context_rows,
        WINDOW_KIND,
        freshness,
        effective_labels=effective_labels,
        evidence_blockers=combined_evidence_blockers,
        outcome_label=derived.get("outcome_label"),
    )
    remaining = list(dict.fromkeys(
        freshness.get("context_blocking_reasons", [])
        + classification.get("unknown_context_blockers", [])
        + classification.get("evidence_blockers", [])
    ))
    row = conn.execute(
        "SELECT supporting_context_json FROM printer_memory_windows WHERE id=?",
        (window_id,),
    ).fetchone()
    supporting = json.loads(str(row[0]) or "{}") if row else {}
    supporting.update({
        "context_quality_reviewed": True,
        "context_row_ids": _context_row_ids_for_memory(context_rows),
        "context_labels": effective_labels,
        "context_freshness_report": freshness,
        "memory_build_evidence_overlays": evidence["overlays"],
        "shared_window_15m_context_evidence": shared_context,
        "derived_window_context": derived.get("payload"),
        "outcome_label": classification["outcome_label"],
        "remaining_blockers": remaining,
        "window_5m_support_role": "SUPPORT_ONLY_NOT_MAIN_EVIDENCE",
    })
    if classification["memory_quality_label"] == "CLEAN_MEMORY":
        # Lane K owns clean promotion; this row stays a PARTIAL_MEMORY candidate.
        quality = "PARTIAL_MEMORY"
        memory_status = "PARTIAL_MEMORY"
        data_quality = "CLEAN_DATA"
        do_not_train = 0
    else:
        quality = classification["memory_quality_label"]
        memory_status = classification["memory_status"]
        data_quality = classification["data_quality_label"]
        do_not_train = 1
    conn.execute(
        """
        UPDATE printer_memory_windows
        SET memory_quality_label=?, memory_status=?, data_quality_label=?,
            do_not_train=?, outcome_label=?, rejection_reasons_json=?,
            supporting_context_json=?, updated_at=?
        WHERE id=?
        """,
        (
            quality, memory_status, data_quality, do_not_train,
            classification["outcome_label"],
            _json(classification["rejection_reasons"]), _json(supporting),
            _iso(), window_id,
        ),
    )
    return {
        "classification": classification,
        "remaining_blockers": remaining,
        "context_row_ids": supporting["context_row_ids"],
        "context_labels": effective_labels,
        "derived_window_context": derived.get("payload"),
        "shared_context_evidence": shared_context,
        "clean_promotion_candidate": do_not_train == 0,
    }


def _attach_closing_snapshot_to_ledger(
    conn: sqlite3.Connection, *, step: sqlite3.Row, result: dict[str, Any],
) -> dict[str, Any]:
    """Attach the exact closing snapshot to this run's ledger before context resolves.

    V2-9.4.8: the exact-ledger resolver may consume only snapshots this run
    recorded. The 15m close previously resolved shared context before the close
    step's snapshot_id reached the ledger, which would report a false
    SNAPSHOT_SET_NOT_CURRENT_RUN_LEDGER. The 4h path already attaches first.

    Re-running an already-attached close is a no-op: the confirmation below reads
    the ledger rather than the UPDATE's rowcount, so replay after a later failure
    re-attaches the same snapshot_id instead of failing.
    """
    snapshot_id = int(result["snapshot_id"])
    run_id = str(step["run_id"])
    token_id = int(step["token_id"])
    pair_id = int(step["pair_id"])
    report: dict[str, Any] = {
        "attached": False,
        "run_id": run_id,
        "snapshot_id": snapshot_id,
        "token_id": token_id,
        "pair_id": pair_id,
    }
    owner = conn.execute(
        "SELECT token_id, pair_id FROM printer_token_snapshots WHERE id=?",
        (snapshot_id,),
    ).fetchone()
    if owner is None:
        report["reason"] = "CLOSING_SNAPSHOT_NOT_PERSISTED"
        return report
    # The closing snapshot must belong to this exact run's token and pair.
    if int(owner["token_id"]) != token_id or int(owner["pair_id"]) != pair_id:
        report["reason"] = "CLOSING_SNAPSHOT_TARGET_MISMATCH"
        report["snapshot_token_id"] = int(owner["token_id"])
        report["snapshot_pair_id"] = int(owner["pair_id"])
        return report
    conn.execute(
        """UPDATE printer_memory_factory_run_steps
           SET snapshot_id=?, source_request_id=?, source_response_id=?,
               source_failure_id=?, updated_at=?
           WHERE id=? AND run_id=? AND token_id=? AND pair_id=?
             AND step_status='RUNNING'""",
        (
            snapshot_id, result.get("source_request_id"),
            result.get("source_response_id"), result.get("source_failure_id"),
            _iso(), int(step["id"]), run_id, token_id, pair_id,
        ),
    )
    conn.commit()
    confirmed = conn.execute(
        """SELECT 1 FROM printer_memory_factory_run_steps
           WHERE id=? AND run_id=? AND token_id=? AND pair_id=? AND snapshot_id=?""",
        (int(step["id"]), run_id, token_id, pair_id, snapshot_id),
    ).fetchone()
    if confirmed is None:
        report["reason"] = "CLOSING_SNAPSHOT_LEDGER_ATTACHMENT_FAILED"
        return report
    report["attached"] = True
    return report


def _apply_clean_object_integrity_gate(result: dict[str, Any]) -> bool:
    """Make atomic clean-object failure categorical at the close boundary."""
    pipeline = result.get("memory_pipeline")
    if not isinstance(pipeline, Mapping) or not pipeline.get(
        "clean_object_integrity_blocked"
    ):
        return True
    reasons = [
        str(reason)
        for reason in (pipeline.get("blocked_reasons") or ())
        if str(reason).startswith("clean_object_integrity:")
    ]
    exact_cause = (
        reasons[0]
        if reasons
        else "clean_object_integrity:UNKNOWN_ATOMIC_INTEGRITY_FAILURE"
    )
    result.update(
        ok=False,
        blocked_reason=exact_cause,
        clean_object_integrity_reasons=reasons,
    )
    return False


def _close_phase_result_base(step: sqlite3.Row) -> dict[str, Any]:
    """Preserve the planned phase/dependency identity in terminal result truth."""
    try:
        planned = json.loads(str(step["result_json"] or "{}"))
    except (TypeError, json.JSONDecodeError):
        planned = {}
    expected = CLOSE_PHASE_STEP_KINDS.get(str(step["step_kind"]))
    if (
        expected is None
        or not isinstance(planned, dict)
        or planned.get("close_family") != expected[0]
        or planned.get("close_phase") != expected[1]
    ):
        raise ValueError("CLOSE_PHASE_METADATA_INVALID")
    return dict(planned)


def _preclose_result_base(step: sqlite3.Row) -> dict[str, Any]:
    payload = _close_phase_result_base(step)
    if (
        str(step["step_kind"]) not in PRE_CLOSE_STEP_KINDS
        or payload.get("preclose_contract_version") != PRECLOSE_CONTRACT_VERSION
        or payload.get("factory_run_id") != str(step["run_id"])
        or int(payload.get("token_id", -1)) != int(step["token_id"])
        or int(payload.get("pair_id", -1)) != int(step["pair_id"])
        or str(payload.get("token_mint", "")).lower()
        != str(step["token_mint"]).lower()
        or str(payload.get("pair_address", "")).lower()
        != str(step["pair_address"]).lower()
        or int(payload.get("scheduler_job_id", -1))
        != int(step["scheduler_job_id"])
        or payload.get("intended_close_work_identity") != str(step["step_key"])
    ):
        raise ValueError("PRE_CLOSE_MANIFEST_IDENTITY_INVALID")
    units = payload.get("source_unit_manifest")
    if not isinstance(units, list) or not units:
        raise ValueError("PRE_CLOSE_UNIT_MANIFEST_INVALID")
    identities = [str(unit.get("source_unit_identity") or "") for unit in units]
    if any(not identity for identity in identities) or len(set(identities)) != len(
        identities
    ):
        raise ValueError("PRE_CLOSE_UNIT_IDENTITY_AMBIGUOUS")
    exact_unit_fields = (
        "factory_run_id",
        "scheduler_job_id",
        "intended_close_work_identity",
        "token_id",
        "pair_id",
        "token_mint",
        "pair_address",
        "window_family",
    )
    if any(any(field not in unit for field in exact_unit_fields) for unit in units):
        raise ValueError("PRE_CLOSE_UNIT_OWNER_IDENTITY_MISSING")
    if any(
        str(unit["factory_run_id"]) != str(step["run_id"])
        or int(unit["scheduler_job_id"]) != int(step["scheduler_job_id"])
        or str(unit["intended_close_work_identity"]) != str(step["step_key"])
        or int(unit["token_id"]) != int(step["token_id"])
        or int(unit["pair_id"]) != int(step["pair_id"])
        or str(unit["token_mint"]).lower() != str(step["token_mint"]).lower()
        or str(unit["pair_address"]).lower() != str(step["pair_address"]).lower()
        or str(unit["window_family"]) != str(payload["close_family"])
        for unit in units
    ):
        raise ValueError("PRE_CLOSE_UNIT_OWNER_IDENTITY_INVALID")
    for unit in units:
        role = str(unit["source_unit_identity"])
        definition = _PRECLOSE_UNIT_DEFINITIONS.get(role)
        if definition is None:
            raise ValueError("PRE_CLOSE_SOURCE_UNIT_UNAUTHORIZED")
        expected_source, expected_kind, expected_suffix = definition
        expected_prefix = (
            f"{step['run_id']}:{step['step_key']}:"
            f"scheduler-{int(step['scheduler_job_id'])}:"
            f"preclose:{role.lower()}:attempt-1"
        )
        if (
            str(unit.get("source_name")) != expected_source
            or str(unit.get("request_kind")) != expected_kind
            or int(unit.get("attempt_ordinal") or -1) != 1
            or str(unit.get("request_key_prefix")) != expected_prefix
            or str(unit.get("request_key"))
            != f"{expected_prefix}:{expected_suffix}"
        ):
            raise ValueError("PRE_CLOSE_SOURCE_UNIT_REQUEST_IDENTITY_INVALID")
    return payload


def _preclose_terminal_count(units: list[dict[str, Any]]) -> int:
    return sum(1 for unit in units if str(unit.get("state")) in _PRECLOSE_TERMINAL_STATES)


def _bind_preclose_source_unit_for_claim(
    conn: sqlite3.Connection, *, step_id: int
) -> str | None:
    """Bind the Scheduler claim to one projected unit before execution."""
    step = conn.execute(
        "SELECT * FROM printer_memory_factory_run_steps WHERE id=?",
        (int(step_id),),
    ).fetchone()
    if step is None or str(step["step_kind"]) not in PRE_CLOSE_STEP_KINDS:
        raise ValueError("PRE_CLOSE_CLAIM_STEP_INVALID")
    job = conn.execute(
        "SELECT status,locked_at,lock_owner FROM printer_scheduler_jobs WHERE id=?",
        (int(step["scheduler_job_id"]),),
    ).fetchone()
    if (
        job is None
        or str(job["status"]) != "RUNNING"
        or job["locked_at"] is None
        or not str(job["lock_owner"] or "")
    ):
        raise ValueError("PRE_CLOSE_CLAIM_NOT_SCHEDULER_OWNED")
    phase = _preclose_result_base(step)
    campaign_owners = conn.execute(
        """SELECT campaign_id,run_id,cycle_id,token_slot_id,window_id,
                  scheduler_work_id
           FROM printer_memory_factory_campaign_scheduler_work
           WHERE scheduler_job_id=? AND ownership_contract_version='V2_STAGE_SCOPED'
             AND work_scope='WINDOW_LIFECYCLE'""",
        (int(step["scheduler_job_id"]),),
    ).fetchall()
    if len(campaign_owners) > 1:
        raise ValueError("PRE_CLOSE_CAMPAIGN_OWNER_AMBIGUOUS")
    if campaign_owners:
        owner = campaign_owners[0]
        expected_owner = {
            "campaign_id": str(owner["campaign_id"]),
            "campaign_run_id": str(owner["run_id"]),
            "cycle_id": str(owner["cycle_id"]),
            "token_slot_id": str(owner["token_slot_id"]),
            "campaign_window_id": str(owner["window_id"]),
            "campaign_scheduler_work_id": str(owner["scheduler_work_id"]),
        }
        if any(phase.get(key) != value for key, value in expected_owner.items()):
            raise ValueError("PRE_CLOSE_CAMPAIGN_OWNER_MISMATCH")
        if any(
            any(unit.get(key) != value for key, value in expected_owner.items())
            for unit in phase["source_unit_manifest"]
        ):
            raise ValueError("PRE_CLOSE_UNIT_CAMPAIGN_OWNER_MISMATCH")
    units = [dict(unit) for unit in phase["source_unit_manifest"]]
    _update_preclose_dependencies(units)
    ready = [unit for unit in units if str(unit.get("state")) == "PENDING"]
    active_identity: str | None = None
    if ready:
        active = min(
            ready,
            key=lambda item: (
                datetime.fromisoformat(str(item["latest_safe_claim_at"])),
                int(item["deterministic_tie_ordinal"]),
                str(item["source_unit_identity"]),
            ),
        )
        active_identity = str(active["source_unit_identity"])
    phase["source_unit_manifest"] = units
    phase["active_claim_source_unit_identity"] = active_identity
    phase["active_claim_scheduler_job_id"] = int(step["scheduler_job_id"])
    updated = conn.execute(
        "UPDATE printer_memory_factory_run_steps SET result_json=?,updated_at=? "
        "WHERE id=? AND step_status IN ('PENDING','RUNNING')",
        (_json(phase), _iso(), int(step_id)),
    )
    if int(updated.rowcount or 0) != 1:
        raise ValueError("PRE_CLOSE_CLAIM_STEP_STATE_INVALID")
    return active_identity


def _source_execution_from_rows(
    request: sqlite3.Row,
    response: sqlite3.Row | None,
    failure: sqlite3.Row | None,
) -> Any:
    from printer_v1.contracts.enums import DataQualityLabel, SourceStatus
    from printer_v1.sources.contracts import (
        NormalizedSourceResult,
        SourceFailureRecord,
        SourceRequestRecord,
        SourceResponseRecord,
    )
    from printer_v1.sources.governed_execution import GovernedSourceExecutionResult

    request_record = SourceRequestRecord(
        id=int(request["id"]),
        source_name=str(request["source_name"]),
        request_kind=str(request["request_kind"]),
        requested_at=str(request["requested_at"]),
        request_key=request["request_key"],
        tracking_priority=request["tracking_priority"],
        source_status=SourceStatus(str(request["source_status"])),
        data_quality_label=DataQualityLabel(str(request["data_quality_label"])),
    )
    response_record = None
    failure_record = None
    if response is not None:
        response_payload = json.loads(str(response["normalized_payload_json"] or "{}"))
        response_record = SourceResponseRecord(
            id=int(response["id"]),
            source_request_id=int(response["source_request_id"]),
            source_name=str(response["source_name"]),
            received_at=str(response["received_at"]),
            status_code=response["status_code"],
            source_status=SourceStatus(str(response["source_status"])),
            data_quality_label=DataQualityLabel(str(response["data_quality_label"])),
            response_hash=response["response_hash"],
            normalized_payload=response_payload,
        )
        normalized = NormalizedSourceResult(
            source_name=response_record.source_name,
            request_kind=request_record.request_kind,
            source_status=response_record.source_status,
            data_quality_label=response_record.data_quality_label,
            normalized_payload=response_payload,
            status_code=response_record.status_code,
            received_at=response_record.received_at,
        )
    elif failure is not None:
        failure_payload = json.loads(str(failure["normalized_payload_json"] or "{}"))
        failure_record = SourceFailureRecord(
            id=int(failure["id"]),
            source_name=str(failure["source_name"]),
            request_kind=str(failure["request_kind"]),
            failed_at=str(failure["failed_at"]),
            failure_type=str(failure["failure_type"]),
            failure_message=failure["failure_message"],
            source_status=SourceStatus(str(failure["source_status"])),
            data_quality_label=DataQualityLabel(str(failure["data_quality_label"])),
            retry_after_at=failure["retry_after_at"],
            normalized_payload=failure_payload,
            source_request_id=int(failure["source_request_id"]),
        )
        normalized = NormalizedSourceResult(
            source_name=failure_record.source_name,
            request_kind=failure_record.request_kind,
            source_status=failure_record.source_status,
            data_quality_label=failure_record.data_quality_label,
            normalized_payload=failure_payload,
            failure_type=failure_record.failure_type,
            failure_message=failure_record.failure_message,
            retry_after_at=failure_record.retry_after_at,
            received_at=failure_record.failed_at,
        )
    else:
        return None
    return GovernedSourceExecutionResult(
        request_record=request_record,
        normalized_result=normalized,
        response_record=response_record,
        failure_record=failure_record,
    )


def _reconcile_preclose_request(
    conn: sqlite3.Connection, unit: Mapping[str, Any]
) -> dict[str, Any]:
    requests = conn.execute(
        """SELECT * FROM printer_source_requests
           WHERE request_key=? ORDER BY id""",
        (str(unit["request_key"]),),
    ).fetchall()
    if not requests:
        return {"state": "NO_REQUEST"}
    if len(requests) != 1:
        return {"state": "INTEGRITY_BLOCKED", "reason": "DUPLICATE_REQUEST_IDENTITY"}
    request = requests[0]
    if (
        str(request["source_name"]) != str(unit["source_name"])
        or str(request["request_kind"]) != str(unit["request_kind"])
    ):
        return {"state": "INTEGRITY_BLOCKED", "reason": "FOREIGN_REQUEST_IDENTITY"}
    responses = conn.execute(
        "SELECT * FROM printer_source_responses WHERE source_request_id=? ORDER BY id",
        (int(request["id"]),),
    ).fetchall()
    failures = conn.execute(
        "SELECT * FROM printer_source_failures WHERE source_request_id=? ORDER BY id",
        (int(request["id"]),),
    ).fetchall()
    if len(responses) + len(failures) > 1 or (responses and failures):
        return {"state": "INTEGRITY_BLOCKED", "reason": "AMBIGUOUS_TERMINAL_SOURCE_RESULT"}
    if not responses and not failures:
        return {
            "state": "INTERRUPTED_AFTER_REQUEST",
            "request": request,
        }
    execution = _source_execution_from_rows(
        request,
        responses[0] if responses else None,
        failures[0] if failures else None,
    )
    return {
        "state": "TERMINAL",
        "request": request,
        "response": responses[0] if responses else None,
        "failure": failures[0] if failures else None,
        "execution": execution,
    }


def _update_preclose_dependencies(units: list[dict[str, Any]]) -> None:
    by_identity = {str(unit["source_unit_identity"]): unit for unit in units}
    safety = by_identity.get("SAFETY_PRIMARY")
    holder = by_identity.get("HOLDER_PRIMARY")
    backup = by_identity.get("HOLDER_BACKUP")
    if safety is not None and holder is not None and str(safety.get("state")) in _PRECLOSE_TERMINAL_STATES:
        label = str(safety.get("holder_concentration_label") or "")
        if label == "HOLDER_CONCENTRATION_UNKNOWN":
            if holder.get("state") == "BLOCKED_DEPENDENCY":
                holder["state"] = "PENDING"
        elif holder.get("state") == "BLOCKED_DEPENDENCY":
            holder["state"] = "NOT_REQUIRED"
            holder["terminal_reason"] = "GOPLUS_HOLDER_CONCENTRATION_AVAILABLE"
    if holder is not None and backup is not None and str(holder.get("state")) in _PRECLOSE_TERMINAL_STATES:
        from printer_v1.operator_cli.safety_context_source_redundancy import (
            ELIGIBLE_TRANSIENT_SOLANA_RPC_FAILURE_TYPES,
        )

        if str(holder.get("failure_type") or "") in ELIGIBLE_TRANSIENT_SOLANA_RPC_FAILURE_TYPES:
            if backup.get("state") == "BLOCKED_DEPENDENCY":
                backup["state"] = "PENDING"
        elif backup.get("state") == "BLOCKED_DEPENDENCY":
            backup["state"] = "NOT_REQUIRED"
            backup["terminal_reason"] = "HOLDER_BACKUP_NOT_AUTHORIZED"


def _execute_preclose_critical_phase(
    conn: sqlite3.Connection,
    step: sqlite3.Row,
    *,
    timeout_seconds: float,
    context_adapter_factories: dict[str, Callable[..., Any]] | None = None,
    cancellation_probe: Callable[[], str | None] | None = None,
    claimed_at: datetime | None = None,
) -> dict[str, Any]:
    """Execute or reconcile exactly one logical pre-close source unit."""
    phase = _preclose_result_base(step)
    units = [dict(unit) for unit in phase["source_unit_manifest"]]
    phase["source_unit_manifest"] = units
    if phase.get("preclose_plan_state") == "TIMELY_ACQUISITION_NOT_PRODUCIBLE":
        return {
            **phase,
            "ok": True,
            "terminal_job_status": "SKIPPED",
            "yield_required": False,
            "blocked_reason": "TIMELY_ACQUISITION_NOT_PRODUCIBLE",
        }
    _update_preclose_dependencies(units)
    current = (claimed_at or _now()).astimezone(timezone.utc)
    ready = [unit for unit in units if str(unit.get("state")) == "PENDING"]
    if not ready:
        if _preclose_terminal_count(units) != len(units):
            return {
                **phase,
                "ok": False,
                "yield_required": False,
                "blocked_reason": "PRE_CLOSE_DEPENDENCY_STATE_INVALID",
            }
        return {**phase, "ok": True, "yield_required": False}
    active_identity = str(phase.get("active_claim_source_unit_identity") or "")
    if int(phase.get("active_claim_scheduler_job_id") or -1) != int(
        step["scheduler_job_id"]
    ):
        raise ValueError("PRE_CLOSE_CLAIM_WORK_IDENTITY_INVALID")
    matches = [
        unit
        for unit in ready
        if str(unit["source_unit_identity"]) == active_identity
    ]
    if len(matches) != 1:
        raise ValueError("PRE_CLOSE_CLAIM_SOURCE_UNIT_IDENTITY_INVALID")
    unit = matches[0]
    role = str(unit["source_unit_identity"])
    phase["last_claim_source_unit_identity"] = role
    phase.pop("active_claim_source_unit_identity", None)
    phase.pop("active_claim_scheduler_job_id", None)
    if (
        role == "SAFETY_CORE"
        and context_adapter_factories is not None
        and "solana_rpc_core_safety" not in context_adapter_factories
    ):
        unit["state"] = "NOT_REQUIRED"
        unit["terminal_reason"] = "CORE_SAFETY_NOT_ACTIVE_FOR_RUN"
        phase["last_claim_reconciliation"] = "NOT_REQUIRED_BY_ACTIVE_SOURCE_SET"
        terminal_count = _preclose_terminal_count(units)
        phase.update(
            ok=True,
            terminal_unit_count=terminal_count,
            yield_required=terminal_count != len(units),
            next_preclose_scheduled_for=(
                current.isoformat() if terminal_count != len(units) else None
            ),
        )
        return phase
    if role == "MARKET_CHAIN":
        from printer_v1.chain_heat.lookup import chain_heat_snapshot_is_valid_for_memory
        from printer_v1.context_evidence.window_15m import _broad_context
        from printer_v1.market_regime.lookup import market_snapshot_is_valid_for_memory

        cutoff = datetime.fromisoformat(str(unit["acquisition_cutoff_at"]))
        market = _broad_context(
            conn,
            table="printer_market_regime_snapshots",
            payload_column="normalized_market_payload_json",
            target_time=cutoff,
            valid_for_memory=market_snapshot_is_valid_for_memory,
        )
        chain = _broad_context(
            conn,
            table="printer_solana_chain_heat_snapshots",
            payload_column="normalized_chain_heat_payload_json",
            target_time=cutoff,
            valid_for_memory=chain_heat_snapshot_is_valid_for_memory,
        )
        if market and chain:
            unit.update(
                state="REUSED_PERIODIC",
                terminal_reason="TIMELY_PERIODIC_CONTEXT_REUSED",
                observed_at=max(
                    datetime.fromisoformat(str(market["captured_at"])),
                    datetime.fromisoformat(str(chain["captured_at"])),
                ).isoformat(),
                market_regime_row_id=int(market["id"]),
                chain_heat_row_id=int(chain["id"]),
            )
            terminal_count = _preclose_terminal_count(units)
            phase.update(
                ok=True,
                terminal_unit_count=terminal_count,
                yield_required=terminal_count != len(units),
                next_preclose_scheduled_for=(
                    current.isoformat() if terminal_count != len(units) else None
                ),
                last_claim_reconciliation="REUSED_TIMELY_PERIODIC_CONTEXT",
            )
            return phase
    reconciliation = _reconcile_preclose_request(conn, unit)
    execution = None
    if reconciliation["state"] == "INTEGRITY_BLOCKED":
        unit["state"] = "CONTEXT_INTEGRITY_BLOCKED"
        unit["terminal_reason"] = str(reconciliation["reason"])
        phase.update(
            ok=False,
            yield_required=False,
            blocked_reason="CONTEXT_INTEGRITY_BLOCKED",
            terminal_unit_count=_preclose_terminal_count(units),
        )
        return phase
    if reconciliation["state"] == "INTERRUPTED_AFTER_REQUEST":
        request = reconciliation["request"]
        unit.update(
            state="UNKNOWN_INTERRUPTED_AFTER_REQUEST",
            terminal_reason="UNKNOWN_INTERRUPTED_AFTER_REQUEST",
            source_request_id=int(request["id"]),
            observed_at=None,
        )
        phase["last_claim_source_request_id"] = int(request["id"])
        phase["last_claim_reconciliation"] = "UNKNOWN_INTERRUPTED_AFTER_REQUEST"
    else:
        if reconciliation["state"] == "TERMINAL":
            execution = reconciliation["execution"]
            phase["last_claim_reconciliation"] = "REHYDRATED_TERMINAL_SOURCE_RESULT"
        else:
            if current > datetime.fromisoformat(str(unit["latest_safe_claim_at"])):
                unit["state"] = "MISSED_CUTOFF"
                unit["terminal_reason"] = "MISSED_PRE_CLOSE_START"
                phase["last_claim_reconciliation"] = "MISSED_WITHOUT_REQUEST"
            else:
                _check_cancellation(cancellation_probe)
                bundle = _collect_preclose_context(
                    conn,
                    step,
                    timeout_seconds=timeout_seconds,
                    adapter_factories=context_adapter_factories,
                    cancellation_probe=cancellation_probe,
                    request_key_prefix=str(unit["request_key_prefix"]),
                    source_unit_identity=role,
                )
                executions = list(
                    {
                        id(value): value
                        for value in bundle["executions"].values()
                    }.values()
                )
                if len(executions) != 1:
                    raise ValueError("PRE_CLOSE_CLAIM_ATTEMPT_COUNT_INVALID")
                execution = executions[0]
                phase["provider_attempt_count"] = int(
                    phase.get("provider_attempt_count") or 0
                ) + 1
                phase["last_claim_reconciliation"] = "FIRST_GOVERNED_ATTEMPT"
        if execution is not None:
            from printer_v1.safety.goplus_normalizer import (
                holder_concentration_label_from_goplus,
            )

            observed_at = str(
                execution.response_record.received_at
                if execution.response_record is not None
                else execution.failure_record.failed_at
                if execution.failure_record is not None
                else ""
            )
            cutoff = datetime.fromisoformat(str(unit["acquisition_cutoff_at"]))
            observed = datetime.fromisoformat(observed_at) if observed_at else None
            state = (
                "TIMELY"
                if execution.response_record is not None
                and observed is not None
                and observed <= cutoff
                else "LATE"
                if execution.response_record is not None
                else "DENIED"
                if str(execution.normalized_result.failure_type or "")
                in {"rate_limit_exceeded", "source_not_in_registry", "request_kind_not_allowed"}
                else "FAILED"
            )
            payload = dict(execution.normalized_result.normalized_payload or {})
            unit.update(
                state=state,
                terminal_reason=(None if state == "TIMELY" else state),
                source_request_id=int(execution.request_record.id),
                source_response_id=(
                    int(execution.response_record.id)
                    if execution.response_record is not None
                    else None
                ),
                source_failure_id=(
                    int(execution.failure_record.id)
                    if execution.failure_record is not None
                    else None
                ),
                observed_at=observed_at or None,
                failure_type=execution.normalized_result.failure_type,
                holder_concentration_label=(
                    holder_concentration_label_from_goplus(payload)
                    if role == "SAFETY_PRIMARY"
                    else None
                ),
            )
            phase["last_claim_source_request_id"] = int(execution.request_record.id)
            phase["last_claim_source_response_id"] = unit["source_response_id"]
            phase["last_claim_source_failure_id"] = unit["source_failure_id"]
    _update_preclose_dependencies(units)
    terminal_count = _preclose_terminal_count(units)
    manifest_terminal = terminal_count == len(units)
    phase.update(
        ok=True,
        terminal_unit_count=terminal_count,
        yield_required=not manifest_terminal,
        next_preclose_scheduled_for=(current.isoformat() if not manifest_terminal else None),
    )
    return phase


def _checkpoint_and_yield_preclose_claim(
    conn: sqlite3.Connection,
    *,
    step: sqlite3.Row,
    result: Mapping[str, Any],
    now: datetime | None = None,
) -> None:
    """Commit one unit checkpoint before yielding the same Scheduler work row."""
    if str(step["step_kind"]) not in PRE_CLOSE_STEP_KINDS:
        raise ValueError("pre-close yield received non-preclose step")
    if result.get("yield_required") is not True:
        raise ValueError("pre-close yield requires remaining source units")
    stamp = (now or _now()).astimezone(timezone.utc)
    conn.execute(
        """UPDATE printer_memory_factory_run_steps
           SET step_status='PENDING',source_request_id=NULL,
               source_response_id=NULL,source_failure_id=NULL,
               result_json=?,error_or_skip_reason=NULL,finished_at=NULL,updated_at=?
           WHERE id=? AND step_status='RUNNING'""",
        (_json(dict(result)), stamp.isoformat(), int(step["id"])),
    )
    conn.commit()
    yield_job(
        conn,
        job_id=int(step["scheduler_job_id"]),
        scheduled_for=stamp,
        now=stamp,
    )
    _sync_owned_campaign_scheduler_job(
        conn, scheduler_job_id=int(step["scheduler_job_id"])
    )
    conn.commit()


def _rehydrate_preclose_context_bundle(
    conn: sqlite3.Connection, manifest: Mapping[str, Any]
) -> dict[str, Any]:
    """Rebuild the exact source execution bundle without any provider call."""
    executions: dict[str, Any] = {}
    unit_results: list[dict[str, Any]] = []
    role_keys = {
        "MARKET_CHAIN": "market_chain",
        "SAFETY_PRIMARY": "safety",
        "SAFETY_CORE": "core_solana_safety",
        "ENTRY_QUOTE": "entry_quote",
        "EXIT_QUOTE": "exit_quote",
        "HOLDER_PRIMARY": "holder_primary",
        "HOLDER_BACKUP": "holder_backup",
    }
    for raw in manifest.get("source_unit_manifest", []):
        if not isinstance(raw, Mapping):
            raise ValueError("PRE_CLOSE_UNIT_MANIFEST_INVALID")
        unit = dict(raw)
        role = str(unit.get("source_unit_identity") or "")
        state = str(unit.get("state") or "")
        unit_results.append(
            {
                "source_unit_identity": role,
                "state": state,
                "observed_at": unit.get("observed_at"),
                "terminal_reason": unit.get("terminal_reason"),
                "source_request_id": unit.get("source_request_id"),
                "source_response_id": unit.get("source_response_id"),
                "source_failure_id": unit.get("source_failure_id"),
            }
        )
        if unit.get("source_request_id") is None:
            continue
        reconciled = _reconcile_preclose_request(conn, unit)
        if reconciled.get("state") != "TERMINAL":
            raise ValueError("CONTEXT_INTEGRITY_BLOCKED")
        execution = reconciled["execution"]
        if int(execution.request_record.id) != int(unit["source_request_id"]):
            raise ValueError("CONTEXT_INTEGRITY_BLOCKED")
        if (
            str(execution.request_record.source_name) != str(unit["source_name"])
            or str(execution.request_record.request_kind)
            != str(unit["request_kind"])
            or not isinstance(
                execution.normalized_result.normalized_payload, Mapping
            )
        ):
            raise ValueError("CONTEXT_INTEGRITY_BLOCKED")
        if unit.get("source_response_id") is not None and (
            execution.response_record is None
            or int(execution.response_record.id) != int(unit["source_response_id"])
            or str(execution.response_record.source_name)
            != str(unit["source_name"])
        ):
            raise ValueError("CONTEXT_INTEGRITY_BLOCKED")
        if unit.get("source_failure_id") is not None and (
            execution.failure_record is None
            or int(execution.failure_record.id) != int(unit["source_failure_id"])
            or str(execution.failure_record.source_name)
            != str(unit["source_name"])
            or str(execution.failure_record.request_kind)
            != str(unit["request_kind"])
        ):
            raise ValueError("CONTEXT_INTEGRITY_BLOCKED")
        executions[role_keys[role]] = execution
    primary_holder = executions.get("holder_primary")
    backup_holder = executions.get("holder_backup")
    if backup_holder is not None and backup_holder.response_record is not None:
        executions["holder"] = backup_holder
    elif primary_holder is not None:
        executions["holder"] = primary_holder
    return {
        "executions": executions,
        "report": {
            "source_request_budget": 0,
            "source_requests_attempted": 0,
            "post_capture_main_window_provider_calls": 0,
            "unit_results": unit_results,
            "items": {
                key: _context_execution_summary(value)
                for key, value in executions.items()
            },
        },
    }
def _execute_close_evidence_phase(
    conn: sqlite3.Connection,
    step: sqlite3.Row,
    *,
    adapter_factory: Callable[..., Any],
    timeout_seconds: float,
    fallback_adapter_factory: Callable[..., Any] | None = None,
) -> dict[str, Any]:
    """Capture and durably attach only the exact closing snapshot evidence."""
    if str(step["step_kind"]) not in EVIDENCE_STEP_KINDS:
        raise ValueError("close evidence executor received non-evidence step")
    phase = _close_phase_result_base(step)
    captured = _execute_snapshot(
        conn,
        step,
        adapter_factory=adapter_factory,
        timeout_seconds=timeout_seconds,
        fallback_adapter_factory=fallback_adapter_factory,
    )
    result = {**phase, **captured}
    if not result.get("ok"):
        return result
    result["ledger_attachment"] = _attach_closing_snapshot_to_ledger(
        conn, step=step, result=result
    )
    if not result["ledger_attachment"]["attached"]:
        result.update(
            ok=False,
            blocked_reason=result["ledger_attachment"]["reason"],
        )
        return result
    snapshot = conn.execute(
        """SELECT token_id,pair_id,captured_at FROM printer_token_snapshots
           WHERE id=?""",
        (int(result["snapshot_id"]),),
    ).fetchone()
    if (
        snapshot is None
        or int(snapshot["token_id"]) != int(step["token_id"])
        or int(snapshot["pair_id"]) != int(step["pair_id"])
        or not str(snapshot["captured_at"] or "")
    ):
        result.update(ok=False, blocked_reason="CLOSE_EVIDENCE_SNAPSHOT_MISMATCH")
        return result
    result["evidence_captured_at"] = str(snapshot["captured_at"])
    result["ok"] = True
    return result


def _execute_close_context_phase(
    conn: sqlite3.Connection,
    step: sqlite3.Row,
    *,
    timeout_seconds: float,
    context_adapter_factories: dict[str, Callable[..., Any]] | None = None,
    cancellation_probe: Callable[[], str | None] | None = None,
) -> dict[str, Any]:
    """Bind exact terminal pre-close truth after the closing snapshot exists."""
    if str(step["step_kind"]) not in CONTEXT_STEP_KINDS:
        raise ValueError("close context executor received non-context step")
    phase = _close_phase_result_base(step)
    evidence = resolve_close_evidence(conn, step)
    if not evidence.get("resolved"):
        return {
            **phase,
            "ok": False,
            "blocked_reason": str(evidence.get("reason")),
        }
    preclose = resolve_preclose_manifest(conn, step)
    if not preclose.get("resolved"):
        return {
            **phase,
            "ok": False,
            "blocked_reason": str(preclose.get("reason")),
        }
    validated_preclose_manifest = _preclose_result_base(
        preclose["preclose_step"]
    )
    _check_cancellation(cancellation_probe)
    context_bundle = _rehydrate_preclose_context_bundle(
        conn, validated_preclose_manifest
    )
    _check_cancellation(cancellation_probe)
    conn.execute("SAVEPOINT close_context_binding")
    try:
        persistence = _persist_preclose_context(
            conn,
            step=step,
            snapshot_id=int(evidence["snapshot_id"]),
            context_bundle=context_bundle,
        )
    except Exception:
        conn.execute("ROLLBACK TO SAVEPOINT close_context_binding")
        conn.execute("RELEASE SAVEPOINT close_context_binding")
        raise
    else:
        conn.execute("RELEASE SAVEPOINT close_context_binding")
    unit_states = {
        str(item.get("state") or "")
        for item in context_bundle["report"]["unit_results"]
    }
    if unit_states <= {"TIMELY", "REUSED_PERIODIC", "NOT_REQUIRED"}:
        context_state = "CONTEXT_COMPLETE"
    elif "CONTEXT_INTEGRITY_BLOCKED" in unit_states:
        raise ValueError("CONTEXT_INTEGRITY_BLOCKED")
    elif "UNKNOWN_INTERRUPTED_AFTER_REQUEST" in unit_states:
        context_state = "CONTEXT_UNKNOWN"
    elif unit_states & {"FAILED", "DENIED"}:
        context_state = "CONTEXT_PROVIDER_FAILED"
    else:
        context_state = "CONTEXT_PARTIAL"
    context_envelope = {
        "context_state": context_state,
        "closing_snapshot_id": int(evidence["snapshot_id"]),
        "preclose_manifest_step_id": int(preclose["preclose_step"]["id"]),
        "unit_results": list(context_bundle["report"]["unit_results"]),
    }
    # Deliberately use closing_snapshot_id instead of snapshot_id.  Only the
    # evidence step is an ACTUAL-capture carrier for cadence/deadline authority.
    return {
        **phase,
        "ok": True,
        "closing_snapshot_id": int(evidence["snapshot_id"]),
        "evidence_captured_at": str(evidence["evidence_captured_at"]),
        "governed_context_collection": context_bundle["report"],
        "governed_context_persistence": persistence,
        "preclose_manifest_step_id": int(preclose["preclose_step"]["id"]),
        "preclose_context_state": context_state,
        "closing_context_envelope": context_envelope,
        "evidence_bound_at": _iso(),
    }


def _close_context_result(step: sqlite3.Row) -> dict[str, Any]:
    try:
        payload = json.loads(str(step["result_json"] or "{}"))
    except (TypeError, json.JSONDecodeError) as exc:
        raise ValueError("CLOSE_CONTEXT_RESULT_MALFORMED") from exc
    if not isinstance(payload, dict) or payload.get("ok") is not True:
        raise ValueError("CLOSE_CONTEXT_RESULT_NOT_SUCCESSFUL")
    return payload


def _audit_15m_close_from_evidence(
    conn: sqlite3.Connection,
    step: sqlite3.Row,
    *,
    closing_snapshot_id: int,
    minimum_evidence_seconds: float,
    context_result: Mapping[str, Any],
    cancellation_probe: Callable[[], str | None] | None,
) -> dict[str, Any]:
    from printer_v1.operator_cli.e2o_memory_window_close import (
        close_15m_memory_window_from_snapshot,
    )
    from printer_v1.operator_cli.e2q_memory_window_audit import (
        audit_15m_memory_window,
    )
    from printer_v1.operator_cli.lane_k_e2z_pipeline_wiring import run_e2z_pipeline

    result = {
        **_close_phase_result_base(step),
        "ok": True,
        "closing_snapshot_id": int(closing_snapshot_id),
        "governed_context_collection": context_result.get(
            "governed_context_collection"
        ),
        "governed_context_persistence": context_result.get(
            "governed_context_persistence"
        ),
    }
    first = conn.execute(
        """SELECT s.snapshot_id,ts.captured_at
           FROM printer_memory_factory_run_steps AS s
           JOIN printer_token_snapshots AS ts ON ts.id=s.snapshot_id
           WHERE s.run_id=? AND s.token_id=? AND s.pair_id=?
             AND s.step_kind='SNAPSHOT' AND s.step_status='SUCCEEDED'
             AND s.snapshot_id IS NOT NULL
           ORDER BY s.scheduled_for,s.id LIMIT 1""",
        (step["run_id"], step["token_id"], step["pair_id"]),
    ).fetchone()
    end_row = conn.execute(
        "SELECT captured_at FROM printer_token_snapshots WHERE id=?",
        (int(closing_snapshot_id),),
    ).fetchone()
    if first is None:
        result.update(ok=False, blocked_reason="no successful opening snapshot")
        return result
    if end_row is None or not _evidence_duration_is_eligible(
        str(first["captured_at"]),
        str(end_row["captured_at"]),
        minimum_seconds=minimum_evidence_seconds,
    ):
        result.update(
            ok=False,
            blocked_reason="persisted snapshot evidence duration below required window",
            evidence_duration_seconds=(
                _evidence_duration_seconds(
                    str(first["captured_at"]), str(end_row["captured_at"])
                )
                if end_row is not None
                else None
            ),
        )
        return result
    _check_cancellation(cancellation_probe)
    close = close_15m_memory_window_from_snapshot(
        conn,
        int(closing_snapshot_id),
        str(step["token_mint"]),
        snapshot_start_id=int(first["snapshot_id"]),
    )
    window_id = close.get("window_id") or close.get("existing_window_id")
    result.update(window_close=close, memory_window_id=window_id)
    if window_id is None:
        result.update(
            ok=False,
            blocked_reason="; ".join(close.get("blocked_reasons", []))
            or "window close blocked",
        )
        return result
    result["context_quality"] = _attach_context_and_gate_window(
        conn,
        step=step,
        window_id=int(window_id),
        snapshot_start_id=int(first["snapshot_id"]),
        snapshot_end_id=int(closing_snapshot_id),
    )
    result["window_audit"] = audit_15m_memory_window(conn, int(window_id))
    conn.commit()
    result["memory_pipeline"] = run_e2z_pipeline(
        str(conn.execute("PRAGMA database_list").fetchone()[2]),
        operator_approved=True,
        production_mode=True,
        candidate_window_ids=[int(window_id)],
    )
    if not _apply_clean_object_integrity_gate(result):
        return result
    result["ok"] = True
    return result


def _audit_1h_close_from_evidence(
    conn: sqlite3.Connection,
    step: sqlite3.Row,
    *,
    closing_snapshot_id: int,
    context_result: Mapping[str, Any],
    cancellation_probe: Callable[[], str | None] | None,
) -> dict[str, Any]:
    from printer_v1.operator_cli.e2q_memory_window_audit import audit_15m_memory_window
    from printer_v1.operator_cli.first_hour_safety_binding import (
        FirstHourSafetyBindingError,
        attach_first_hour_safety_overlay,
    )
    from printer_v1.operator_cli.lane_e2o_1h_window_close import (
        E2O_1H_STATUS_BLOCKED,
        E2O_1H_STATUS_CONTINUITY_BLOCKED,
        close_1h_memory_window_from_snapshot,
    )
    from printer_v1.operator_cli.lane_k_e2z_pipeline_wiring import run_e2z_pipeline

    result = {
        **_close_phase_result_base(step),
        "ok": True,
        "closing_snapshot_id": int(closing_snapshot_id),
        "governed_context_collection": context_result.get(
            "governed_context_collection"
        ),
        "governed_context_persistence": context_result.get(
            "governed_context_persistence"
        ),
    }
    first = conn.execute(
        """SELECT s.snapshot_id,ts.captured_at
           FROM printer_memory_factory_run_steps AS s
           JOIN printer_token_snapshots AS ts ON ts.id=s.snapshot_id
           WHERE s.run_id=? AND s.token_id=? AND s.pair_id=?
             AND s.step_kind='CONTINUATION_SNAPSHOT'
             AND s.step_status='SUCCEEDED' AND s.snapshot_id IS NOT NULL
           ORDER BY s.scheduled_for,s.id LIMIT 1""",
        (step["run_id"], step["token_id"], step["pair_id"]),
    ).fetchone()
    if first is None:
        result.update(ok=False, blocked_reason="no real first continuation snapshot")
        return result
    source = _resolve_current_run_15m_source(
        conn,
        run_id=str(step["run_id"]),
        token_id=int(step["token_id"]),
        pair_id=int(step["pair_id"]),
        tracking_lane=str(step["tracking_lane"]),
    )
    if not source.get("resolved"):
        result.update(
            ok=False,
            continuity_blocked=True,
            blocked_reason="; ".join(source.get("reasons", [])),
            continuity_source=source,
        )
        return result
    _check_cancellation(cancellation_probe)
    close = close_1h_memory_window_from_snapshot(
        conn,
        int(closing_snapshot_id),
        str(step["token_mint"]),
        snapshot_start_id=int(first["snapshot_id"]),
        expected_pair_id=int(step["pair_id"]),
        continuation_of_15m=source["window"],
        consumed_15m_window_ids=source.get("consumed_ids", []),
    )
    result["window_close"] = close
    if close.get("e2o_1h_status") in {
        E2O_1H_STATUS_BLOCKED,
        E2O_1H_STATUS_CONTINUITY_BLOCKED,
    }:
        result.update(
            ok=False,
            continuity_blocked=(
                close.get("e2o_1h_status") == E2O_1H_STATUS_CONTINUITY_BLOCKED
            ),
            blocked_reason="; ".join(close.get("blocked_reasons", []))
            or str(close.get("e2o_1h_status")),
        )
        return result
    window_id = close.get("window_id") or close.get("existing_window_id")
    result["memory_window_id"] = window_id
    if window_id is None:
        result.update(ok=False, blocked_reason="1h close produced no window")
        return result
    persisted_context = result.get("governed_context_persistence")
    if not isinstance(persisted_context, Mapping):
        result.update(ok=False, blocked_reason="FIRST_HOUR_CONTEXT_TRUTH_MISSING")
        return result
    context_envelope = context_result.get("closing_context_envelope")
    if not isinstance(context_envelope, Mapping):
        result.update(ok=False, blocked_reason="FIRST_HOUR_CONTEXT_ENVELOPE_MISSING")
        return result
    try:
        result["first_hour_safety_binding"] = attach_first_hour_safety_overlay(
            conn,
            step=step,
            memory_window_id=int(window_id),
            closing_snapshot_id=int(closing_snapshot_id),
            persisted_context=persisted_context,
        )
    except FirstHourSafetyBindingError as exc:
        reason = str(exc)
        if reason not in {
            "FIRST_HOUR_SAFETY_COMPOSITE_MISSING",
            "FIRST_HOUR_SAFETY_LOGICAL_CUTOFF_EXCEEDED",
        }:
            raise
        result["first_hour_safety_binding"] = {
            "bound": False,
            "memory_window_id": int(window_id),
            "closing_snapshot_id": int(closing_snapshot_id),
            "context_state": str(
                context_envelope.get("context_state") or "CONTEXT_PARTIAL"
            ),
            "reason": reason,
        }
    window = conn.execute(
        """SELECT token_id,pair_id,snapshot_end_id,supporting_context_json
           FROM printer_memory_windows WHERE id=? AND window_kind='WINDOW_1H'""",
        (int(window_id),),
    ).fetchone()
    if (
        window is None
        or int(window["token_id"]) != int(step["token_id"])
        or int(window["pair_id"]) != int(step["pair_id"])
        or int(window["snapshot_end_id"] or -1) != int(closing_snapshot_id)
    ):
        raise ValueError("FIRST_HOUR_CONTEXT_ENVELOPE_TARGET_MISMATCH")
    try:
        supporting = json.loads(str(window["supporting_context_json"] or "{}"))
    except (TypeError, json.JSONDecodeError) as exc:
        raise ValueError("FIRST_HOUR_CONTEXT_ENVELOPE_MALFORMED") from exc
    if not isinstance(supporting, dict):
        raise ValueError("FIRST_HOUR_CONTEXT_ENVELOPE_MALFORMED")
    supporting["closing_context_envelope"] = {
        **dict(context_envelope),
        "safety_binding": dict(result["first_hour_safety_binding"]),
    }
    updated = conn.execute(
        """UPDATE printer_memory_windows SET supporting_context_json=?
           WHERE id=? AND token_id=? AND pair_id=? AND snapshot_end_id=?""",
        (
            _json(supporting),
            int(window_id),
            int(step["token_id"]),
            int(step["pair_id"]),
            int(closing_snapshot_id),
        ),
    )
    if int(updated.rowcount or 0) != 1:
        raise ValueError("FIRST_HOUR_CONTEXT_ENVELOPE_UPDATE_FAILED")
    result["full_first_hour_outcome"] = _derive_and_persist_first_hour_outcome(
        conn,
        run_id=str(step["run_id"]),
        token_id=int(step["token_id"]),
        pair_id=int(step["pair_id"]),
        window_id=int(window_id),
        current_close_snapshot_id=int(closing_snapshot_id),
    )
    result["window_audit"] = audit_15m_memory_window(conn, int(window_id))
    conn.commit()
    result["memory_pipeline"] = run_e2z_pipeline(
        str(conn.execute("PRAGMA database_list").fetchone()[2]),
        operator_approved=True,
        production_mode=True,
        candidate_window_ids=[int(window_id)],
    )
    result.update(ok=True, continuity_source=source)
    return result


def _execute_close_audit_phase(
    conn: sqlite3.Connection,
    step: sqlite3.Row,
    *,
    minimum_evidence_seconds: float,
    execution_authority: str,
    cancellation_probe: Callable[[], str | None] | None = None,
) -> dict[str, Any]:
    """Consume exact persisted evidence/context; never fetch or recapture."""
    if str(step["step_kind"]) not in AUDIT_STEP_KINDS:
        raise ValueError("close audit executor received non-audit step")
    resolved = resolve_close_context(conn, step)
    if not resolved.get("resolved"):
        return {
            **_close_phase_result_base(step),
            "ok": False,
            "blocked_reason": str(resolved.get("reason")),
        }
    context_result = _close_context_result(resolved["context_step"])
    if int(context_result.get("closing_snapshot_id", -1)) != int(
        resolved["snapshot_id"]
    ):
        return {
            **_close_phase_result_base(step),
            "ok": False,
            "blocked_reason": "CLOSE_CONTEXT_EVIDENCE_IDENTITY_MISMATCH",
        }
    family = CLOSE_PHASE_STEP_KINDS[str(step["step_kind"])][0]
    if family == "WINDOW_CLOSE":
        result = _audit_15m_close_from_evidence(
            conn,
            step,
            closing_snapshot_id=int(resolved["snapshot_id"]),
            minimum_evidence_seconds=minimum_evidence_seconds,
            context_result=context_result,
            cancellation_probe=cancellation_probe,
        )
    elif family == "CONTINUATION_CLOSE":
        result = _audit_1h_close_from_evidence(
            conn,
            step,
            closing_snapshot_id=int(resolved["snapshot_id"]),
            context_result=context_result,
            cancellation_probe=cancellation_probe,
        )
    else:
        result = _audit_4h_close_from_evidence(
            conn,
            step,
            evidence_step=resolved["evidence_step"],
            closing_snapshot_id=int(resolved["snapshot_id"]),
            context_result=context_result,
            execution_authority=execution_authority,
            cancellation_probe=cancellation_probe,
        )
    result["evidence_captured_at"] = str(resolved["evidence_captured_at"])
    result["closing_context_envelope"] = context_result.get(
        "closing_context_envelope"
    )
    return result


def _execute_close(
    conn: sqlite3.Connection, step: sqlite3.Row, *, adapter_factory: Callable[..., Any],
    timeout_seconds: float, minimum_evidence_seconds: float,
    context_adapter_factories: dict[str, Callable[..., Any]] | None = None,
    fallback_adapter_factory: Callable[..., Any] | None = None,
    cancellation_probe: Callable[[], str | None] | None = None,
) -> dict[str, Any]:
    from printer_v1.operator_cli.e2o_memory_window_close import close_15m_memory_window_from_snapshot
    from printer_v1.operator_cli.e2q_memory_window_audit import audit_15m_memory_window
    from printer_v1.operator_cli.lane_k_e2z_pipeline_wiring import run_e2z_pipeline

    context_bundle = _collect_preclose_context(
        conn,
        step,
        timeout_seconds=timeout_seconds,
        adapter_factories=context_adapter_factories,
        cancellation_probe=cancellation_probe,
    )
    _check_cancellation(cancellation_probe)
    result = _execute_snapshot(
        conn, step, adapter_factory=adapter_factory, timeout_seconds=timeout_seconds,
        fallback_adapter_factory=fallback_adapter_factory,
    )
    result["governed_context_collection"] = context_bundle["report"]
    if not result.get("ok"):
        return result
    # V2-9.4.8 ordering: the closing snapshot is persisted, so attach it to this
    # run's ledger and verify its identity BEFORE any context resolution reads
    # the ledger. Everything below may now rely on the exact ledger range.
    result["ledger_attachment"] = _attach_closing_snapshot_to_ledger(
        conn, step=step, result=result
    )
    if not result["ledger_attachment"]["attached"]:
        result.update(ok=False, blocked_reason=result["ledger_attachment"]["reason"])
        return result
    result["governed_context_persistence"] = _persist_preclose_context(
        conn,
        step=step,
        snapshot_id=int(result["snapshot_id"]),
        context_bundle=context_bundle,
    )
    first = conn.execute(
        """
        SELECT s.snapshot_id, ts.captured_at
        FROM printer_memory_factory_run_steps s
        JOIN printer_token_snapshots ts ON ts.id=s.snapshot_id
        WHERE s.run_id=? AND s.token_id=? AND s.pair_id=? AND s.step_kind='SNAPSHOT'
          AND step_status='SUCCEEDED' AND snapshot_id IS NOT NULL
        ORDER BY s.scheduled_for, s.id LIMIT 1
        """,
        (step["run_id"], step["token_id"], step["pair_id"]),
    ).fetchone()
    if first is None:
        result.update(ok=False, blocked_reason="no successful opening snapshot")
        return result
    end_row = conn.execute(
        "SELECT captured_at FROM printer_token_snapshots WHERE id=?",
        (int(result["snapshot_id"]),),
    ).fetchone()
    if end_row is None or not _evidence_duration_is_eligible(
        str(first["captured_at"]), str(end_row["captured_at"]),
        minimum_seconds=minimum_evidence_seconds,
    ):
        result.update(
            ok=False,
            blocked_reason="persisted snapshot evidence duration below required window",
            evidence_duration_seconds=(
                _evidence_duration_seconds(
                    str(first["captured_at"]), str(end_row["captured_at"])
                ) if end_row is not None else None
            ),
        )
        return result
    _check_cancellation(cancellation_probe)
    close = close_15m_memory_window_from_snapshot(
        conn, int(result["snapshot_id"]), str(step["token_mint"]),
        snapshot_start_id=int(first["snapshot_id"]),
    )
    window_id = close.get("window_id") or close.get("existing_window_id")
    result["window_close"] = close
    result["memory_window_id"] = window_id
    if window_id is None:
        result.update(ok=False, blocked_reason="; ".join(close.get("blocked_reasons", [])) or "window close blocked")
        return result
    result["context_quality"] = _attach_context_and_gate_window(
        conn,
        step=step,
        window_id=int(window_id),
        snapshot_start_id=int(first["snapshot_id"]),
        snapshot_end_id=int(result["snapshot_id"]),
    )
    result["window_audit"] = audit_15m_memory_window(conn, int(window_id))
    conn.commit()
    result["memory_pipeline"] = run_e2z_pipeline(
        str(conn.execute("PRAGMA database_list").fetchone()[2]),
        operator_approved=True,
        production_mode=True,
        candidate_window_ids=[int(window_id)],
    )
    if not _apply_clean_object_integrity_gate(result):
        return result
    result["ok"] = True
    return result


def _resolve_current_run_15m_source(
    conn: sqlite3.Connection,
    *,
    run_id: str,
    token_id: int,
    pair_id: int,
    tracking_lane: str,
    current_close_step_id: int | None = None,
) -> dict[str, Any]:
    """Resolve exactly one unconsumed 15m close from this run and target."""
    rows = conn.execute(
        """
        SELECT w.*, s.id AS close_step_id, s.step_kind,
               s.snapshot_id AS step_snapshot_id,
               s.token_mint, s.pair_address, s.tracking_lane AS step_lane
        FROM printer_memory_factory_run_steps s
        JOIN printer_memory_windows w ON w.id=s.memory_window_id
        WHERE s.run_id=? AND s.token_id=? AND s.pair_id=?
          AND s.tracking_lane=?
          AND s.step_kind IN ('WINDOW_CLOSE','WINDOW_CLOSE_AUDIT')
          AND (
            s.step_status='SUCCEEDED'
            OR (s.id=? AND s.step_status='RUNNING')
          )
          AND w.window_kind='WINDOW_15M'
        """,
        (run_id, token_id, pair_id, tracking_lane, current_close_step_id or -1),
    ).fetchall()
    reasons: list[str] = []
    if len(rows) != 1:
        reasons.append(f"current_run_15m_close_count={len(rows)} expected=1")
        return {"resolved": False, "reasons": reasons}
    row = dict(rows[0])
    if str(row.get("step_kind")) == "WINDOW_CLOSE_AUDIT":
        audit_step = conn.execute(
            "SELECT * FROM printer_memory_factory_run_steps WHERE id=?",
            (int(row["close_step_id"]),),
        ).fetchone()
        evidence = (
            resolve_close_evidence(conn, audit_step)
            if audit_step is not None
            else {"resolved": False}
        )
        row["step_snapshot_id"] = (
            int(evidence["snapshot_id"]) if evidence.get("resolved") else None
        )
    if row.get("snapshot_end_id") is None or row.get("step_snapshot_id") is None:
        reasons.append("missing_current_run_15m_closing_snapshot")
    elif int(row["snapshot_end_id"]) != int(row["step_snapshot_id"]):
        reasons.append("current_run_15m_closing_snapshot_mismatch")
    if int(row["token_id"]) != int(token_id) or int(row["pair_id"]) != int(pair_id):
        reasons.append("current_run_15m_target_mismatch")
    if str(row.get("step_lane")) != tracking_lane:
        reasons.append("current_run_15m_lane_mismatch")

    consumed: list[int] = []
    one_h_rows = conn.execute(
        "SELECT id, supporting_context_json FROM printer_memory_windows "
        "WHERE token_id=? AND pair_id=? AND window_kind='WINDOW_1H'",
        (token_id, pair_id),
    ).fetchall()
    for one_h in one_h_rows:
        try:
            context = json.loads(str(one_h["supporting_context_json"] or "{}"))
        except (TypeError, json.JSONDecodeError):
            context = {}
        linked_id = context.get("continuation_of_window_id")
        if linked_id is None:
            linked_id = (context.get("continuity") or {}).get("continuation_of_window_id")
        if linked_id is not None:
            consumed.append(int(linked_id))
    if int(row["id"]) in consumed:
        reasons.append("current_run_15m_window_already_consumed")
    if reasons:
        return {"resolved": False, "reasons": reasons, "window_id": row.get("id")}
    row["run_id"] = run_id
    row["tracking_lane"] = tracking_lane
    return {"resolved": True, "reasons": [], "window": row, "consumed_ids": consumed}


def _evaluate_event_time_5m_support_for_snapshot(
    conn: sqlite3.Connection,
    *,
    run_id: str,
    step: sqlite3.Row,
    result: Mapping[str, Any],
) -> dict[str, Any]:
    from printer_v1.operator_cli.checkpoint6_event_time_5m import (
        evaluate_event_time_5m_support_for_snapshot,
    )

    return evaluate_event_time_5m_support_for_snapshot(
        conn, factory_run_id=run_id, step=step, result=result
    )


def _materialize_frozen_5m_support(
    conn: sqlite3.Connection,
    *,
    run_id: str,
    close_step: sqlite3.Row,
    parent_window_id: int,
) -> dict[str, Any]:
    from printer_v1.operator_cli.checkpoint6_event_time_5m import (
        materialize_frozen_5m_support,
    )

    return materialize_frozen_5m_support(
        conn,
        factory_run_id=run_id,
        close_step=close_step,
        parent_window_id=parent_window_id,
    )


def _capture_same_stream_5m_support(
    conn: sqlite3.Connection,
    *,
    run_id: str,
    close_step: sqlite3.Row,
    parent_window_id: int,
) -> dict[str, Any]:
    """Persist a support-only 5m prefix from this run's 15m snapshot stream."""
    rows = conn.execute(
        """
        SELECT ts.id, ts.captured_at
        FROM printer_memory_factory_run_steps s
        JOIN printer_token_snapshots ts ON ts.id=s.snapshot_id
        WHERE s.run_id=? AND s.token_id=? AND s.pair_id=?
          AND s.step_kind='SNAPSHOT' AND s.step_status='SUCCEEDED'
        ORDER BY ts.captured_at, ts.id
        """,
        (run_id, close_step["token_id"], close_step["pair_id"]),
    ).fetchall()
    if len(rows) < 2:
        return {"captured": False, "blocked_reasons": ["insufficient same-stream 5m snapshots"]}
    opening_at = datetime.fromisoformat(str(rows[0]["captured_at"]))
    eligible = [
        row for row in rows
        if 0.0 <= (datetime.fromisoformat(str(row["captured_at"])) - opening_at).total_seconds() <= 300.0
    ]
    if len(eligible) < 2:
        return {"captured": False, "blocked_reasons": ["no same-stream 5m prefix"]}
    start_row = eligible[0]
    end_row = eligible[-1]
    conn.commit()
    from printer_v1.operator_cli.lane_x8_5m_support_integration import (
        capture_5m_support_evidence,
    )
    db_path = str(conn.execute("PRAGMA database_list").fetchone()[2])
    result = capture_5m_support_evidence(
        db_path,
        parent_window_id,
        int(close_step["token_id"]),
        int(close_step["pair_id"]),
        operator_approved=True,
        snapshot_start_id=int(start_row["id"]),
        snapshot_end_id=int(end_row["id"]),
        run_id=run_id,
        tracking_lane=str(close_step["tracking_lane"]),
    )
    window_id = result.get("window_5m_id")
    if window_id is not None:
        existing_step = conn.execute(
            "SELECT id FROM printer_memory_factory_run_steps WHERE run_id=? AND step_key=?",
            (run_id, f"{_token_prefix(str(close_step['step_key']))}_support_5m"),
        ).fetchone()
        if existing_step is None:
            now = _iso()
            conn.execute(
                """
                INSERT INTO printer_memory_factory_run_steps
                  (run_id,step_key,step_kind,step_status,token_id,pair_id,
                   token_mint,pair_address,tracking_lane,memory_window_id,
                   result_json,finished_at,created_at,updated_at)
                VALUES (?, ?, 'SUPPORT_5M', 'SUCCEEDED', ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    run_id,
                    f"{_token_prefix(str(close_step['step_key']))}_support_5m",
                    close_step["token_id"], close_step["pair_id"],
                    close_step["token_mint"], close_step["pair_address"],
                    close_step["tracking_lane"], int(window_id), _json(result),
                    now, now, now,
                ),
            )
    return result


def _operational_activated_token_count(
    conn: sqlite3.Connection, run_id: str, *, cycle_id: str | None = None
) -> int:
    """Count activated tokens that have a first-15m close step for this run."""
    if cycle_id is None:
        return int(conn.execute(
            "SELECT COUNT(DISTINCT token_id || ':' || pair_id) "
            "FROM printer_memory_factory_run_steps "
            "WHERE run_id=? AND step_kind IN ('WINDOW_CLOSE','WINDOW_CLOSE_AUDIT')",
            (run_id,),
        ).fetchone()[0])
    return int(conn.execute(
        "SELECT COUNT(DISTINCT s.token_id || ':' || s.pair_id) "
        "FROM printer_memory_factory_run_steps AS s "
        "JOIN printer_memory_factory_campaign_scheduler_work AS w "
        "ON w.scheduler_job_id=s.scheduler_job_id "
        "AND w.ownership_contract_version='V2_STAGE_SCOPED' "
        "AND w.work_scope='WINDOW_LIFECYCLE' "
        "WHERE s.run_id=? AND s.step_kind IN ('WINDOW_CLOSE','WINDOW_CLOSE_AUDIT') "
        "AND w.cycle_id=?",
        (run_id, cycle_id),
    ).fetchone()[0])


def _operational_terminal_15m_closes(
    conn: sqlite3.Connection,
    run_id: str,
    *,
    current_step_id: int,
    cycle_id: str | None = None,
) -> list[sqlite3.Row]:
    """Return every terminal 15m close (memory window attached) for this run.

    A close is terminal once its 15m memory window is attached and the step is
    SUCCEEDED, or is the exact current close still RUNNING. This is the barrier
    input: the operational-natural disposition may only be derived once every
    activated token appears here.
    """
    if cycle_id is None:
        return conn.execute(
        """
        SELECT * FROM printer_memory_factory_run_steps
        WHERE run_id=? AND step_kind IN ('WINDOW_CLOSE','WINDOW_CLOSE_AUDIT')
          AND memory_window_id IS NOT NULL
          AND (step_status='SUCCEEDED' OR (id=? AND step_status='RUNNING'))
        ORDER BY id
        """,
        (run_id, int(current_step_id)),
        ).fetchall()
    return conn.execute(
        "SELECT s.* FROM printer_memory_factory_run_steps AS s "
        "JOIN printer_memory_factory_campaign_scheduler_work AS w "
        "ON w.scheduler_job_id=s.scheduler_job_id "
        "AND w.ownership_contract_version='V2_STAGE_SCOPED' "
        "AND w.work_scope='WINDOW_LIFECYCLE' "
        "WHERE s.run_id=? AND s.step_kind IN ('WINDOW_CLOSE','WINDOW_CLOSE_AUDIT') "
        "AND s.memory_window_id IS NOT NULL "
        "AND (s.step_status='SUCCEEDED' OR (s.id=? AND s.step_status='RUNNING')) "
        "AND w.cycle_id=? ORDER BY s.id",
        (run_id, int(current_step_id), cycle_id),
    ).fetchall()


def _authoritative_terminal_15m_closes(
    conn: sqlite3.Connection, run_id: str, *, cycle_id: str | None = None
) -> list[sqlite3.Row]:
    """Return only succeeded, exactly linked starting-token 15m closes."""
    if cycle_id is None:
        return conn.execute(
        """
        SELECT * FROM printer_memory_factory_run_steps
        WHERE run_id=? AND step_kind IN ('WINDOW_CLOSE','WINDOW_CLOSE_AUDIT')
          AND memory_window_id IS NOT NULL AND step_status='SUCCEEDED'
        ORDER BY id
        """,
        (run_id,),
        ).fetchall()
    return conn.execute(
        "SELECT s.* FROM printer_memory_factory_run_steps AS s "
        "JOIN printer_memory_factory_campaign_scheduler_work AS w "
        "ON w.scheduler_job_id=s.scheduler_job_id "
        "AND w.ownership_contract_version='V2_STAGE_SCOPED' "
        "AND w.work_scope='WINDOW_LIFECYCLE' "
        "WHERE s.run_id=? AND s.step_kind IN ('WINDOW_CLOSE','WINDOW_CLOSE_AUDIT') "
        "AND s.memory_window_id IS NOT NULL AND s.step_status='SUCCEEDED' "
        "AND w.cycle_id=? ORDER BY s.id",
        (run_id, cycle_id),
    ).fetchall()


def _run_selective_1h_campaign_barrier(
    conn: sqlite3.Connection,
    *,
    db_path: str,
    run_id: str,
    config: Mapping[str, Any],
    continuation_seconds: float,
    cycle_id: str | None = None,
) -> dict[str, Any]:
    """Evaluate once after every activated 15m close is authoritative."""
    owned_cycle = cycle_id or str(config.get("cycle_id") or "")
    expected = _operational_activated_token_count(
        conn, run_id, cycle_id=(owned_cycle if cycle_id is not None else None)
    )
    closes = _authoritative_terminal_15m_closes(
        conn, run_id, cycle_id=(owned_cycle if cycle_id is not None else None)
    )
    if len(closes) < expected:
        return {
            "evaluation_reached": False,
            "reason": "AWAITING_AUTHORITATIVE_15M_CLOSES",
            "expected_close_count": expected,
            "authoritative_close_count": len(closes),
        }
    if expected not in {1, 2} or len(closes) != expected:
        raise ValueError("selective 1h authoritative close set is ambiguous")

    from printer_v1.operator_cli.campaign_authority_adapters import (
        load_authoritative_promotion_outcome,
    )
    from printer_v1.operator_cli.operational_selective_1h import (
        evaluate_selective_1h_for_cycle,
        persist_15m_campaign_window,
    )

    graph: list[tuple[sqlite3.Row, sqlite3.Row, str]] = []
    for close_row in closes:
        slot = conn.execute(
            """
            SELECT token_slot_id, lifecycle_identity
            FROM printer_memory_factory_campaign_token_slots
            WHERE campaign_id=? AND run_id=? AND cycle_id=?
              AND token_row_id=? AND pair_row_id=?
            """,
            (
                config.get("campaign_id"),
                config.get("campaign_run_id"),
                owned_cycle,
                int(close_row["token_id"]),
                int(close_row["pair_id"]),
            ),
        ).fetchone()
        if slot is None:
            raise ValueError("missing campaign token slot for selective 1h lineage")
        persisted = persist_15m_campaign_window(
            conn,
            campaign_id=str(config["campaign_id"]),
            run_id=str(config["campaign_run_id"]),
            cycle_id=owned_cycle,
            token_slot_id=str(slot["token_slot_id"]),
            token_row_id=int(close_row["token_id"]),
            pair_row_id=int(close_row["pair_id"]),
            lifecycle_identity=str(slot["lifecycle_identity"]),
            memory_window_row_id=int(close_row["memory_window_id"]),
            checkpoint_cutoff=_iso(),
            window_state="AUDITING",
        )
        # B.1 must resolve before immutable campaign evaluation ownership.
        load_authoritative_promotion_outcome(
            db_path,
            campaign_id=str(config["campaign_id"]),
            run_id=str(config["campaign_run_id"]),
            cycle_id=owned_cycle,
            token_slot_id=str(slot["token_slot_id"]),
            window_id=str(persisted["window_id"]),
        )
        graph.append((close_row, slot, str(persisted["window_id"])))

    evaluation = evaluate_selective_1h_for_cycle(
        conn,
        db_path=db_path,
        campaign_id=str(config["campaign_id"]),
        configuration_id=str(
            config.get("configuration_id") or config["campaign_id"]
        ),
        run_id=str(config["campaign_run_id"]),
        cycle_id=owned_cycle,
    )
    if evaluation.get("evaluation_created"):
        for close_row, _, _ in graph:
            support, continuation_plan = _selective_1h_schedule_for_close(
                conn,
                run_id=run_id,
                close_step=close_row,
                window_id=int(close_row["memory_window_id"]),
                continuation_seconds=continuation_seconds,
                evaluation=evaluation,
            )
            close_result = json.loads(str(close_row["result_json"] or "{}"))
            close_result["support_5m"] = support
            close_result["continuation_plan"] = continuation_plan
            close_result["selective_1h_evaluation"] = evaluation
            conn.execute(
                "UPDATE printer_memory_factory_run_steps SET result_json=?, updated_at=? "
                "WHERE id=? AND step_status='SUCCEEDED'",
                (_json(close_result), _iso(), int(close_row["id"])),
            )
        conn.commit()
    return {
        "evaluation_reached": True,
        "evaluation_created": bool(evaluation.get("evaluation_created")),
        "evaluation": evaluation,
    }


def _selective_1h_schedule_for_close(
    conn: sqlite3.Connection,
    *,
    run_id: str,
    close_step: sqlite3.Row,
    window_id: int,
    continuation_seconds: float,
    evaluation: Mapping[str, Any],
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Enqueue first-hour work only from an exact Checkpoint-1 successor."""
    from printer_v1.operator_cli.operational_selective_1h import should_continue_token

    token_id = int(close_step["token_id"])
    plan = next(
        (
            p
            for p in evaluation.get("token_plans") or ()
            if int(p["token_row_id"]) == token_id
        ),
        None,
    )
    if plan is None:
        raise ValueError(f"missing standard-first-hour token plan for token {token_id}")
    if not should_continue_token(evaluation, token_id=token_id):
        return (
            {
                "captured": False,
                "verdict": "VALID_NO_CAPTURE",
                "reason": plan.get("verdict", "STOP_OR_BLOCK"),
                "window_5m_id": None,
            },
            {
                "enqueue_ok": False,
                "planned_jobs": 0,
                "verdict": plan.get("verdict", "STOP_AFTER_WINDOW_15M"),
                "reason": ";".join(plan.get("reasons") or ["selective_stop"]),
            },
        )

    campaign_window_1h_id = str(plan.get("campaign_window_1h_id") or "")
    token_slot_id = str(plan.get("token_slot_id") or "")
    campaign_id = str(evaluation.get("campaign_id") or "")
    campaign_run_id = str(evaluation.get("run_id") or "")
    cycle_id = str(evaluation.get("cycle_id") or "")
    predecessor_window_id = str(plan.get("campaign_window_15m_id") or "")
    if not all(
        (
            campaign_window_1h_id,
            token_slot_id,
            campaign_id,
            campaign_run_id,
            cycle_id,
            predecessor_window_id,
        )
    ):
        raise ValueError("continuing token lacks exact WINDOW_1H ownership identity")

    successor = conn.execute(
        """SELECT w.campaign_id,w.run_id,w.cycle_id,w.token_slot_id,
                  w.token_row_id,w.pair_row_id,w.window_kind,w.window_state,
                  w.predecessor_window_id,w.memory_window_row_id,s.token_state
           FROM printer_memory_factory_campaign_windows AS w
           JOIN printer_memory_factory_campaign_token_slots AS s
             ON s.token_slot_id=w.token_slot_id
            AND s.campaign_id=w.campaign_id
            AND s.run_id=w.run_id
            AND s.cycle_id=w.cycle_id
           WHERE w.window_id=?""",
        (campaign_window_1h_id,),
    ).fetchone()
    expected_successor = (
        campaign_id,
        campaign_run_id,
        cycle_id,
        token_slot_id,
        token_id,
        int(close_step["pair_id"]),
        "WINDOW_1H",
        "PLANNED",
        predecessor_window_id,
    )
    if successor is None or tuple(successor[:9]) != expected_successor:
        raise ValueError("exact WINDOW_1H campaign successor identity mismatch")
    if successor[9] is not None:
        raise ValueError("WINDOW_1H successor already bound to a memory row before collection")
    if str(successor[10]) != "WINDOW_1H_CONTINUING":
        raise ValueError("token slot is not in WINDOW_1H_CONTINUING at initialization")

    support = _capture_same_stream_5m_support(
        conn,
        run_id=run_id,
        close_step=close_step,
        parent_window_id=int(window_id),
    )
    source = _resolve_current_run_15m_source(
        conn,
        run_id=run_id,
        token_id=token_id,
        pair_id=int(close_step["pair_id"]),
        tracking_lane=str(close_step["tracking_lane"]),
        current_close_step_id=int(close_step["id"]),
    )
    if not source.get("resolved"):
        raise ValueError(
            "current-run 15m continuation source blocked: "
            + "; ".join(source.get("reasons", []))
        )
    continuation_plan = _plan_continuation_jobs(
        conn,
        run_id=run_id,
        close_step=close_step,
        fifteen_m=source["window"],
        continuation_seconds=continuation_seconds,
        ownership_context={
            "campaign_id": campaign_id,
            "campaign_run_id": campaign_run_id,
            "cycle_id": cycle_id,
            "token_slot_id": token_slot_id,
            "campaign_window_1h_id": campaign_window_1h_id,
            "factory_run_id": str(run_id),
        },
    )
    if not continuation_plan.get("enqueue_ok"):
        raise ValueError(
            "continuation planning blocked: "
            + "; ".join(continuation_plan.get("reasons", []))
        )
    continuation_plan["verdict"] = "CONTINUE_TO_WINDOW_1H"
    continuation_plan["selective_1h"] = True
    continuation_plan["campaign_window_1h_id"] = campaign_window_1h_id
    continuation_plan["token_slot_id"] = token_slot_id
    return support, continuation_plan

def _natural_disposition_schedule(
    conn: sqlite3.Connection,
    *,
    run_id: str,
    close_step: sqlite3.Row,
    window_id: int,
    continuation_seconds: float,
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Derive final-15m continuation without creating retrospective 5m support.

    Event-time support is evaluated and frozen by Scheduler-owned SNAPSHOT work.
    This final-window owner remains the independent continuation authority only.
    """
    from printer_v1.operator_cli.authoritative_live_operational_campaign import (
        derive_natural_disposition,
    )

    disposition = derive_natural_disposition(conn, int(window_id))
    support = {
        "captured": False,
        "verdict": "EVENT_TIME_SUPPORT_HANDLED_SEPARATELY",
        "reason": "FINAL_15M_OUTCOME_NOT_SUPPORT_TRIGGER_AUTHORITY",
        "window_5m_id": None,
    }
    if disposition.should_continue:
        source = _resolve_current_run_15m_source(
            conn,
            run_id=run_id,
            token_id=int(close_step["token_id"]),
            pair_id=int(close_step["pair_id"]),
            tracking_lane=str(close_step["tracking_lane"]),
            current_close_step_id=int(close_step["id"]),
        )
        if not source.get("resolved"):
            raise ValueError(
                "current-run 15m continuation source blocked: "
                + "; ".join(source.get("reasons", []))
            )
        continuation_plan = _plan_continuation_jobs(
            conn,
            run_id=run_id,
            close_step=close_step,
            fifteen_m=source["window"],
            continuation_seconds=continuation_seconds,
        )
        if not continuation_plan.get("enqueue_ok"):
            raise ValueError(
                "continuation planning blocked: "
                + "; ".join(continuation_plan.get("reasons", []))
            )
        return support, continuation_plan
    reason = disposition.evidence_label
    continuation_plan = {
        "enqueue_ok": False,
        "planned_jobs": 0,
        "verdict": "STOP_AFTER_15M",
        "reason": reason,
    }
    return support, continuation_plan



def _derive_and_persist_first_hour_outcome(
    conn: sqlite3.Connection,
    *,
    run_id: str,
    token_id: int,
    pair_id: int,
    window_id: int,
    current_close_snapshot_id: int,
) -> dict[str, Any]:
    """Classify the complete first-hour path from exact current-run evidence only."""
    target = conn.execute(
        """SELECT id,token_id,pair_id,window_kind,supporting_context_json
           FROM printer_memory_windows WHERE id=?""",
        (int(window_id),),
    ).fetchone()
    if target is None:
        raise ValueError("WINDOW_1H_OUTCOME_TARGET_MISSING")
    if (
        int(target["token_id"]) != int(token_id)
        or int(target["pair_id"]) != int(pair_id)
        or str(target["window_kind"]) != "WINDOW_1H"
    ):
        raise ValueError("WINDOW_1H_OUTCOME_TARGET_IDENTITY_MISMATCH")

    ledger_rows = conn.execute(
        """SELECT snapshot_id
           FROM printer_memory_factory_run_steps
           WHERE run_id=? AND token_id=? AND pair_id=?
             AND step_kind IN (
                 'SNAPSHOT','WINDOW_CLOSE','WINDOW_CLOSE_EVIDENCE',
                 'CONTINUATION_SNAPSHOT','CONTINUATION_CLOSE_EVIDENCE'
             )
             AND step_status='SUCCEEDED' AND snapshot_id IS NOT NULL
           ORDER BY scheduled_for,id""",
        (str(run_id), int(token_id), int(pair_id)),
    ).fetchall()
    snapshot_ids: list[int] = []
    seen: set[int] = set()
    for row in ledger_rows:
        sid = int(row["snapshot_id"])
        if sid not in seen:
            seen.add(sid)
            snapshot_ids.append(sid)
    close_sid = int(current_close_snapshot_id)
    if close_sid not in seen:
        snapshot_ids.append(close_sid)
        seen.add(close_sid)
    if len(snapshot_ids) < 2:
        raise ValueError("WINDOW_1H_OUTCOME_INSUFFICIENT_CURRENT_RUN_SNAPSHOTS")

    placeholders = ",".join("?" for _ in snapshot_ids)
    snapshots = conn.execute(
        f"""SELECT * FROM printer_token_snapshots
            WHERE id IN ({placeholders})
            ORDER BY captured_at,id""",
        tuple(snapshot_ids),
    ).fetchall()
    if len(snapshots) != len(snapshot_ids):
        raise ValueError("WINDOW_1H_OUTCOME_SNAPSHOT_IDENTITY_INCOMPLETE")
    ordered: list[dict[str, Any]] = []
    ordered_ids: list[int] = []
    for row in snapshots:
        if int(row["token_id"]) != int(token_id) or int(row["pair_id"]) != int(pair_id):
            raise ValueError("WINDOW_1H_OUTCOME_SNAPSHOT_IDENTITY_MISMATCH")
        ordered.append(dict(row))
        ordered_ids.append(int(row["id"]))
    if close_sid not in ordered_ids:
        raise ValueError("WINDOW_1H_OUTCOME_CURRENT_CLOSE_SNAPSHOT_MISSING")

    from printer_v1.memory.outcomes import classify_episode_outcome

    outcome = classify_episode_outcome("WINDOW_1H", ordered)
    outcome_label = str(outcome.value)
    try:
        context = json.loads(str(target["supporting_context_json"] or "{}"))
    except json.JSONDecodeError as exc:
        raise ValueError("WINDOW_1H_OUTCOME_SUPPORTING_CONTEXT_MALFORMED") from exc
    context.update(
        {
            "full_first_hour_outcome_snapshot_ids": ordered_ids,
            "full_first_hour_outcome_snapshot_count": len(ordered_ids),
            "full_first_hour_outcome_path_start_at": str(ordered[0]["captured_at"]),
            "full_first_hour_outcome_path_end_at": str(ordered[-1]["captured_at"]),
            "full_first_hour_outcome_source": "EXACT_CURRENT_RUN_MAIN_LIFECYCLE",
        }
    )
    updated = conn.execute(
        """UPDATE printer_memory_windows
           SET outcome_label=?,supporting_context_json=?,updated_at=?
           WHERE id=? AND token_id=? AND pair_id=? AND window_kind='WINDOW_1H'""",
        (
            outcome_label,
            _json(context),
            _iso(),
            int(window_id),
            int(token_id),
            int(pair_id),
        ),
    )
    if int(updated.rowcount or 0) != 1:
        raise ValueError("WINDOW_1H_OUTCOME_TARGET_UPDATE_FAILED")
    return {
        "outcome_label": outcome_label,
        "snapshot_ids": ordered_ids,
        "snapshot_count": len(ordered_ids),
        "path_start_at": str(ordered[0]["captured_at"]),
        "path_end_at": str(ordered[-1]["captured_at"]),
    }

def _execute_continuation_close(
    conn: sqlite3.Connection,
    step: sqlite3.Row,
    *,
    adapter_factory: Callable[..., Any],
    timeout_seconds: float,
    context_adapter_factories: dict[str, Callable[..., Any]] | None = None,
    fallback_adapter_factory: Callable[..., Any] | None = None,
    cancellation_probe: Callable[[], str | None] | None = None,
) -> dict[str, Any]:
    """Persist the final 1h snapshot and close against the exact current-run 15m row."""
    _check_cancellation(cancellation_probe)
    from printer_v1.operator_cli.e2q_memory_window_audit import audit_15m_memory_window
    from printer_v1.operator_cli.first_hour_safety_binding import (
        attach_first_hour_safety_overlay,
    )
    from printer_v1.operator_cli.lane_e2o_1h_window_close import (
        E2O_1H_STATUS_BLOCKED,
        E2O_1H_STATUS_CONTINUITY_BLOCKED,
        close_1h_memory_window_from_snapshot,
    )
    from printer_v1.operator_cli.lane_k_e2z_pipeline_wiring import run_e2z_pipeline

    # V2-9.8B first-hour safety provenance: the 30-minute safety freshness
    # contract makes the earlier 15m composite unusable as first-hour authority,
    # so this Scheduler-owned close collects its own fresh safety-only bundle
    # through the existing governed collector before the final exact-pair
    # snapshot. The collector remains the sole provider-call owner and keeps the
    # holder primary plus single approved backup behaviour unchanged.
    context_bundle = _collect_preclose_context(
        conn, step, timeout_seconds=timeout_seconds,
        adapter_factories=context_adapter_factories,
        include=frozenset({"safety"}),
        cancellation_probe=cancellation_probe,
    )
    _check_cancellation(cancellation_probe)
    result = _execute_snapshot(
        conn, step, adapter_factory=adapter_factory, timeout_seconds=timeout_seconds,
        fallback_adapter_factory=fallback_adapter_factory,
    )
    result["governed_context_collection"] = context_bundle["report"]
    _check_cancellation(cancellation_probe)
    if not result.get("ok"):
        return result
    # Bind the fresh safety evidence/composite to the exact first-hour closing
    # snapshot so its evaluated_at and snapshot linkage are the real close
    # boundary the later 4h barrier reads.
    result["governed_context_persistence"] = _persist_preclose_context(
        conn, step=step, snapshot_id=int(result["snapshot_id"]),
        context_bundle=context_bundle,
    )
    first = conn.execute(
        """
        SELECT s.snapshot_id, ts.captured_at
        FROM printer_memory_factory_run_steps s
        JOIN printer_token_snapshots ts ON ts.id=s.snapshot_id
        WHERE s.run_id=? AND s.token_id=? AND s.pair_id=?
          AND s.step_kind='CONTINUATION_SNAPSHOT'
          AND s.step_status='SUCCEEDED' AND s.snapshot_id IS NOT NULL
        ORDER BY s.scheduled_for, s.id LIMIT 1
        """,
        (step["run_id"], step["token_id"], step["pair_id"]),
    ).fetchone()
    if first is None:
        result.update(ok=False, blocked_reason="no real first continuation snapshot")
        return result
    source = _resolve_current_run_15m_source(
        conn,
        run_id=str(step["run_id"]),
        token_id=int(step["token_id"]),
        pair_id=int(step["pair_id"]),
        tracking_lane=str(step["tracking_lane"]),
    )
    if not source.get("resolved"):
        result.update(
            ok=False,
            continuity_blocked=True,
            blocked_reason="; ".join(source.get("reasons", [])),
            continuity_source=source,
        )
        return result
    _check_cancellation(cancellation_probe)
    close = close_1h_memory_window_from_snapshot(
        conn,
        int(result["snapshot_id"]),
        str(step["token_mint"]),
        snapshot_start_id=int(first["snapshot_id"]),
        expected_pair_id=int(step["pair_id"]),
        continuation_of_15m=source["window"],
        consumed_15m_window_ids=source.get("consumed_ids", []),
    )
    result["window_close"] = close
    if close.get("e2o_1h_status") in {E2O_1H_STATUS_BLOCKED, E2O_1H_STATUS_CONTINUITY_BLOCKED}:
        result.update(
            ok=False,
            continuity_blocked=close.get("e2o_1h_status") == E2O_1H_STATUS_CONTINUITY_BLOCKED,
            blocked_reason="; ".join(close.get("blocked_reasons", [])) or str(close.get("e2o_1h_status")),
        )
        return result
    window_id = close.get("window_id") or close.get("existing_window_id")
    result["memory_window_id"] = window_id
    if window_id is None:
        result.update(ok=False, blocked_reason="1h close produced no window")
        return result
    # The exact fresh safety composite must be bound into this exact WINDOW_1H
    # before outcome derivation, audit, or E2Z observe the memory. This is
    # fail-closed: no clean 1h object may exist without its safety authority.
    result["first_hour_safety_binding"] = attach_first_hour_safety_overlay(
        conn,
        step=step,
        memory_window_id=int(window_id),
        closing_snapshot_id=int(result["snapshot_id"]),
        persisted_context=result["governed_context_persistence"],
    )
    result["full_first_hour_outcome"] = _derive_and_persist_first_hour_outcome(
        conn,
        run_id=str(step["run_id"]),
        token_id=int(step["token_id"]),
        pair_id=int(step["pair_id"]),
        window_id=int(window_id),
        current_close_snapshot_id=int(result["snapshot_id"]),
    )
    result["window_audit"] = audit_15m_memory_window(conn, int(window_id))
    conn.commit()
    result["memory_pipeline"] = run_e2z_pipeline(
        str(conn.execute("PRAGMA database_list").fetchone()[2]),
        operator_approved=True,
        production_mode=True,
        candidate_window_ids=[int(window_id)],
    )
    result["ok"] = True
    result["continuity_source"] = source
    return result



def _derive_and_persist_four_hour_outcome(
    conn: sqlite3.Connection,
    *,
    run_id: str,
    token_id: int,
    pair_id: int,
    window_id: int,
    current_close_snapshot_id: int,
) -> dict[str, Any]:
    """Classify the complete 4h path from exact current-run main-lifecycle evidence."""
    target = conn.execute(
        """SELECT id,token_id,pair_id,window_kind,supporting_context_json
           FROM printer_memory_windows WHERE id=?""",
        (int(window_id),),
    ).fetchone()
    if target is None:
        raise ValueError("WINDOW_4H_OUTCOME_TARGET_MISSING")
    if (
        int(target["token_id"]) != int(token_id)
        or int(target["pair_id"]) != int(pair_id)
        or str(target["window_kind"]) != "WINDOW_4H"
    ):
        raise ValueError("WINDOW_4H_OUTCOME_TARGET_IDENTITY_MISMATCH")

    ledger_rows = conn.execute(
        """SELECT snapshot_id
           FROM printer_memory_factory_run_steps
           WHERE run_id=? AND token_id=? AND pair_id=?
             AND step_kind IN (
                 'SNAPSHOT','WINDOW_CLOSE','WINDOW_CLOSE_EVIDENCE',
                 'CONTINUATION_SNAPSHOT','CONTINUATION_CLOSE',
                 'CONTINUATION_CLOSE_EVIDENCE','LONG_CONTINUATION_SNAPSHOT',
                 'LONG_CONTINUATION_CLOSE_EVIDENCE'
             )
             AND step_status='SUCCEEDED' AND snapshot_id IS NOT NULL
           ORDER BY scheduled_for,id""",
        (str(run_id), int(token_id), int(pair_id)),
    ).fetchall()
    snapshot_ids: list[int] = []
    seen: set[int] = set()
    for row in ledger_rows:
        sid = int(row["snapshot_id"])
        if sid not in seen:
            seen.add(sid)
            snapshot_ids.append(sid)
    close_sid = int(current_close_snapshot_id)
    if close_sid not in seen:
        snapshot_ids.append(close_sid)
        seen.add(close_sid)
    if len(snapshot_ids) < 2:
        raise ValueError("WINDOW_4H_OUTCOME_INSUFFICIENT_CURRENT_RUN_SNAPSHOTS")

    placeholders = ",".join("?" for _ in snapshot_ids)
    snapshots = conn.execute(
        f"""SELECT * FROM printer_token_snapshots
            WHERE id IN ({placeholders}) ORDER BY captured_at,id""",
        tuple(snapshot_ids),
    ).fetchall()
    if len(snapshots) != len(snapshot_ids):
        raise ValueError("WINDOW_4H_OUTCOME_SNAPSHOT_IDENTITY_INCOMPLETE")
    ordered: list[dict[str, Any]] = []
    ordered_ids: list[int] = []
    for row in snapshots:
        if int(row["token_id"]) != int(token_id) or int(row["pair_id"]) != int(pair_id):
            raise ValueError("WINDOW_4H_OUTCOME_SNAPSHOT_IDENTITY_MISMATCH")
        ordered.append(dict(row))
        ordered_ids.append(int(row["id"]))
    if close_sid not in ordered_ids:
        raise ValueError("WINDOW_4H_OUTCOME_CURRENT_CLOSE_SNAPSHOT_MISSING")

    from printer_v1.memory.outcomes import classify_episode_outcome

    outcome_label = str(classify_episode_outcome("WINDOW_4H", ordered).value)
    try:
        context = json.loads(str(target["supporting_context_json"] or "{}"))
    except json.JSONDecodeError as exc:
        raise ValueError("WINDOW_4H_OUTCOME_SUPPORTING_CONTEXT_MALFORMED") from exc
    context.update(
        {
            "full_four_hour_outcome_snapshot_ids": ordered_ids,
            "full_four_hour_outcome_snapshot_count": len(ordered_ids),
            "full_four_hour_outcome_path_start_at": str(ordered[0]["captured_at"]),
            "full_four_hour_outcome_path_end_at": str(ordered[-1]["captured_at"]),
            "full_four_hour_outcome_source": "EXACT_CURRENT_RUN_MAIN_LIFECYCLE",
        }
    )
    updated = conn.execute(
        """UPDATE printer_memory_windows
           SET outcome_label=?,supporting_context_json=?,updated_at=?
           WHERE id=? AND token_id=? AND pair_id=? AND window_kind='WINDOW_4H'""",
        (
            outcome_label,
            _json(context),
            _iso(),
            int(window_id),
            int(token_id),
            int(pair_id),
        ),
    )
    if int(updated.rowcount or 0) != 1:
        raise ValueError("WINDOW_4H_OUTCOME_TARGET_UPDATE_FAILED")
    return {
        "outcome_label": outcome_label,
        "snapshot_ids": ordered_ids,
        "snapshot_count": len(ordered_ids),
        "path_start_at": str(ordered[0]["captured_at"]),
        "path_end_at": str(ordered[-1]["captured_at"]),
    }


def _audit_4h_close_from_evidence(
    conn: sqlite3.Connection,
    step: sqlite3.Row,
    *,
    evidence_step: sqlite3.Row,
    closing_snapshot_id: int,
    context_result: Mapping[str, Any],
    execution_authority: str,
    cancellation_probe: Callable[[], str | None] | None,
) -> dict[str, Any]:
    from printer_v1.context_evidence import build_window_4h_context_evidence
    from printer_v1.operator_cli.one_token_4h_runtime import (
        close_current_run_4h,
        run_4h_quality_gates,
    )

    result = {
        **_close_phase_result_base(step),
        "ok": True,
        "closing_snapshot_id": int(closing_snapshot_id),
        "governed_context_collection": context_result.get(
            "governed_context_collection"
        ),
        "governed_context_persistence": context_result.get(
            "governed_context_persistence"
        ),
    }
    _check_cancellation(cancellation_probe)
    close = close_current_run_4h(
        conn,
        run_id=str(step["run_id"]),
        close_step=evidence_step,
        closing_snapshot_id=int(closing_snapshot_id),
        execution_authority=execution_authority,
    )
    result["window_close"] = close
    if not close.get("closed"):
        result.update(
            ok=False,
            continuity_blocked=True,
            blocked_reason="; ".join(close.get("blocked_reasons", [])),
        )
        return result
    window_id = int(close["window_id"])
    window = conn.execute(
        "SELECT * FROM printer_memory_windows WHERE id=?", (window_id,)
    ).fetchone()
    if window is None:
        result.update(ok=False, blocked_reason="WINDOW_4H_CLOSE_ROW_MISSING")
        return result
    shared = build_window_4h_context_evidence(
        conn,
        token_id=int(window["token_id"]),
        pair_id=int(window["pair_id"]),
        snapshot_start_id=int(window["snapshot_start_id"]),
        snapshot_end_id=int(window["snapshot_end_id"]),
        window_start_at=str(window["window_start_at"]),
        window_end_at=str(window["window_end_at"]),
        tracking_lane=str(step["tracking_lane"]),
        run_id=str(step["run_id"]),
    )
    context = json.loads(str(window["supporting_context_json"] or "{}"))
    context["shared_window_4h_context_evidence"] = shared
    if not shared["clean_memory_context_ready"]:
        conn.execute(
            """UPDATE printer_memory_windows
               SET memory_status='DIRTY_MEMORY',memory_quality_label='DIRTY_MEMORY',
                   data_quality_label='DIRTY_DATA',do_not_train=1,
                   supporting_context_json=? WHERE id=?""",
            (_json(context), window_id),
        )
    else:
        conn.execute(
            "UPDATE printer_memory_windows SET supporting_context_json=? WHERE id=?",
            (_json(context), window_id),
        )
    result["full_four_hour_outcome"] = _derive_and_persist_four_hour_outcome(
        conn,
        run_id=str(step["run_id"]),
        token_id=int(step["token_id"]),
        pair_id=int(step["pair_id"]),
        window_id=window_id,
        current_close_snapshot_id=int(closing_snapshot_id),
    )
    conn.commit()
    quality = run_4h_quality_gates(
        str(conn.execute("PRAGMA database_list").fetchone()[2]), window_id
    )
    result.update(
        ok=True,
        memory_window_id=window_id,
        shared_context_evidence=shared,
        window_audit=quality.get("e2q"),
        lane_q=quality.get("lane_q"),
        memory_pipeline=quality,
    )
    return result


def _execute_long_4h_step(
    conn: sqlite3.Connection,
    step: sqlite3.Row,
    *,
    execution_authority: str,
    adapter_factory: Callable[..., Any],
    timeout_seconds: float,
    context_adapter_factories: dict[str, Callable[..., Any]] | None = None,
    fallback_adapter_factory: Callable[..., Any] | None = None,
    cancellation_probe: Callable[[], str | None] | None = None,
) -> dict[str, Any]:
    """Execute one policy-planned 4h snapshot or close through shared boundaries."""
    from printer_v1.context_evidence import build_window_4h_context_evidence
    from printer_v1.operator_cli.one_token_4h_runtime import (
        close_current_run_4h,
        run_4h_quality_gates,
    )

    is_close = step["step_kind"] == "LONG_CONTINUATION_CLOSE"
    is_opening = str(step["step_key"]).endswith("_snapshot_000")
    context_bundle = None
    if is_opening:
        context_bundle = _collect_preclose_context(
            conn, step, timeout_seconds=timeout_seconds,
            adapter_factories=context_adapter_factories,
            include=frozenset({"market_chain", "entry_quote"}),
            cancellation_probe=cancellation_probe,
        )
    elif is_close:
        context_bundle = _collect_preclose_context(
            conn, step, timeout_seconds=timeout_seconds,
            adapter_factories=context_adapter_factories,
            include=frozenset({"market_chain", "safety", "exit_quote"}),
            cancellation_probe=cancellation_probe,
        )
    _check_cancellation(cancellation_probe)
    result = _execute_snapshot(
        conn, step, adapter_factory=adapter_factory, timeout_seconds=timeout_seconds,
        fallback_adapter_factory=fallback_adapter_factory,
    )
    _check_cancellation(cancellation_probe)
    if not result.get("ok"):
        return result
    if context_bundle is not None:
        result["governed_context_collection"] = context_bundle["report"]
        result["governed_context_persistence"] = _persist_preclose_context(
            conn, step=step, snapshot_id=int(result["snapshot_id"]),
            context_bundle=context_bundle,
        )
    if not is_close:
        return result

    # Cadence and continuity may consume only snapshots attached to this run's
    # ledger. The normal finalizer preserves these values after close returns.
    conn.execute(
        """UPDATE printer_memory_factory_run_steps
           SET snapshot_id=?, source_request_id=?, source_response_id=?,
               source_failure_id=?, updated_at=?
           WHERE id=? AND run_id=? AND step_status='RUNNING'""",
        (
            int(result["snapshot_id"]), result.get("source_request_id"),
            result.get("source_response_id"), result.get("source_failure_id"),
            _iso(), int(step["id"]), str(step["run_id"]),
        ),
    )
    conn.commit()

    _check_cancellation(cancellation_probe)
    close = close_current_run_4h(
        conn,
        run_id=str(step["run_id"]),
        close_step=step,
        closing_snapshot_id=int(result["snapshot_id"]),
        execution_authority=execution_authority,
    )
    result["window_close"] = close
    if not close.get("closed"):
        result.update(
            ok=False,
            continuity_blocked=True,
            blocked_reason="; ".join(close.get("blocked_reasons", [])),
        )
        return result
    window_id = int(close["window_id"])
    window = conn.execute(
        "SELECT * FROM printer_memory_windows WHERE id=?", (window_id,)
    ).fetchone()
    assert window is not None
    shared = build_window_4h_context_evidence(
        conn,
        token_id=int(window["token_id"]),
        pair_id=int(window["pair_id"]),
        snapshot_start_id=int(window["snapshot_start_id"]),
        snapshot_end_id=int(window["snapshot_end_id"]),
        window_start_at=str(window["window_start_at"]),
        window_end_at=str(window["window_end_at"]),
        # V2-9.4.6: exact current-run ledger identity and the approved
        # closing-evidence allowance for this lane.
        tracking_lane=str(step["tracking_lane"]),
        run_id=str(step["run_id"]),
    )
    context = json.loads(str(window["supporting_context_json"] or "{}"))
    context["shared_window_4h_context_evidence"] = shared
    if not shared["clean_memory_context_ready"]:
        conn.execute(
            "UPDATE printer_memory_windows SET memory_status='DIRTY_MEMORY',memory_quality_label='DIRTY_MEMORY',data_quality_label='DIRTY_DATA',do_not_train=1,supporting_context_json=? WHERE id=?",
            (_json(context), window_id),
        )
    else:
        conn.execute(
            "UPDATE printer_memory_windows SET supporting_context_json=? WHERE id=?",
            (_json(context), window_id),
        )
    result["full_four_hour_outcome"] = _derive_and_persist_four_hour_outcome(
        conn,
        run_id=str(step["run_id"]),
        token_id=int(step["token_id"]),
        pair_id=int(step["pair_id"]),
        window_id=window_id,
        current_close_snapshot_id=int(result["snapshot_id"]),
    )
    # E2Q/Lane-Q/E2Z use separate DB connections. Commit only the physical,
    # shared-context, and truthful outcome prerequisites before those owners run.
    conn.commit()
    quality = run_4h_quality_gates(
        str(conn.execute("PRAGMA database_list").fetchone()[2]), window_id
    )
    result.update(
        ok=True,
        memory_window_id=window_id,
        shared_context_evidence=shared,
        window_audit=quality.get("e2q"),
        lane_q=quality.get("lane_q"),
        memory_pipeline=quality,
    )
    return result


def _update_step(
    conn: sqlite3.Connection, step_id: int, status: str, result: dict[str, Any],
    *, error: str | None = None,
) -> None:
    conn.execute(
        """
        UPDATE printer_memory_factory_run_steps
        SET step_status=?, source_request_id=?, source_response_id=?,
            source_failure_id=?, snapshot_id=?, memory_window_id=?, result_json=?,
            error_or_skip_reason=?, finished_at=?, updated_at=?
        WHERE id=?
        """,
        (
            status, result.get("source_request_id"), result.get("source_response_id"),
            result.get("source_failure_id"), result.get("snapshot_id"),
            result.get("memory_window_id"), _json(result), error, _iso(), _iso(), step_id,
        ),
    )



def _merge_standard_four_hour_barrier_result(
    conn: sqlite3.Connection,
    *,
    run_id: str,
    step_id: int,
    barrier: Mapping[str, Any],
) -> dict[str, Any]:
    """Merge barrier truth into the authoritative successful 1h close payload."""
    if not isinstance(barrier, Mapping):
        raise ValueError(
            "standard four-hour barrier result must be a mapping"
        )

    row = conn.execute(
        """SELECT id,run_id,step_kind,step_status,result_json
           FROM printer_memory_factory_run_steps
           WHERE run_id=? AND id=?""",
        (run_id, step_id),
    ).fetchone()

    if row is None:
        raise ValueError(
            "standard four-hour close row missing during barrier merge"
        )

    if (
        str(row["run_id"]) != str(run_id)
        or str(row["step_kind"])
        not in {"CONTINUATION_CLOSE", "CONTINUATION_CLOSE_AUDIT"}
        or str(row["step_status"]) != "SUCCEEDED"
    ):
        raise ValueError(
            "standard four-hour barrier merge requires exact "
            "successful continuation close"
        )

    try:
        payload = json.loads(str(row["result_json"] or "{}"))
    except json.JSONDecodeError as exc:
        raise ValueError(
            "invalid successful continuation close result JSON"
        ) from exc

    if not isinstance(payload, dict):
        raise ValueError(
            "invalid successful continuation close result payload"
        )

    barrier_payload = dict(barrier)
    existing = payload.get("standard_four_hour_barrier")

    if existing is not None:
        if existing != barrier_payload:
            raise ValueError(
                "standard four-hour barrier result conflict"
            )
        return payload

    payload["standard_four_hour_barrier"] = barrier_payload

    updated = conn.execute(
        """UPDATE printer_memory_factory_run_steps
           SET result_json=?,updated_at=?
           WHERE run_id=? AND id=?
             AND step_kind IN ('CONTINUATION_CLOSE','CONTINUATION_CLOSE_AUDIT')
             AND step_status='SUCCEEDED'""",
        (_json(payload), _iso(), run_id, step_id),
    )

    if int(updated.rowcount or 0) != 1:
        raise ValueError(
            "standard four-hour barrier merge lost exact close identity"
        )

    return payload


def _owned_campaign_scheduler_row(
    conn: sqlite3.Connection, *, scheduler_job_id: int,
) -> sqlite3.Row | None:
    """Resolve at most one V2 stage-scoped campaign owner for a Scheduler job."""
    rows = conn.execute(
        """SELECT * FROM printer_memory_factory_campaign_scheduler_work
           WHERE scheduler_job_id=?
             AND ownership_contract_version='V2_STAGE_SCOPED'
           ORDER BY scheduler_work_id""",
        (int(scheduler_job_id),),
    ).fetchall()
    if not rows:
        return None
    if len(rows) != 1:
        raise ValueError(
            f"campaign Scheduler ownership is ambiguous for job {scheduler_job_id}"
        )
    return rows[0]


def _sync_owned_campaign_scheduler_job(
    conn: sqlite3.Connection, *, scheduler_job_id: int,
) -> str | None:
    """Synchronize an existing campaign projection from canonical Scheduler truth."""
    row = _owned_campaign_scheduler_row(
        conn, scheduler_job_id=int(scheduler_job_id)
    )
    if row is None:
        # Historical/non-campaign lifecycle callers have no V2 projection.
        return None
    if (
        str(row["work_scope"]) != "WINDOW_LIFECYCLE"
        or str(row["target_category"]) != "CAMPAIGN_WINDOW"
        or row["token_slot_id"] is None
        or row["window_id"] is None
        or row["factory_run_id"] is None
    ):
        raise ValueError("owned lifecycle Scheduler row has invalid immutable scope")
    from printer_v1.operator_cli.campaign_ownership import (
        project_campaign_scheduler_job,
    )

    projected = project_campaign_scheduler_job(
        conn,
        scheduler_work_id=str(row["scheduler_work_id"]),
        campaign_id=str(row["campaign_id"]),
        run_id=str(row["run_id"]),
        cycle_id=str(row["cycle_id"]),
        token_slot_id=str(row["token_slot_id"]),
        window_id=str(row["window_id"]),
        factory_run_id=str(row["factory_run_id"]),
        work_intent=str(row["work_intent"]),
        deadline_at=str(row["deadline_at"]),
        scheduler_job_id=int(scheduler_job_id),
        stage_id=str(row["stage_id"]),
        target_category=str(row["target_category"]),
        target_identity=str(row["target_identity"]),
        source_request_id=(
            int(row["source_request_id"])
            if row["source_request_id"] is not None else None
        ),
        source_response_id=(
            int(row["source_response_id"])
            if row["source_response_id"] is not None else None
        ),
        source_failure_id=(
            int(row["source_failure_id"])
            if row["source_failure_id"] is not None else None
        ),
    )
    return str(projected.work_state)


def _owned_lifecycle_window_for_job(
    conn: sqlite3.Connection,
    *,
    scheduler_job_id: int,
    expected_stage: str,
    expected_window_kind: str,
) -> sqlite3.Row | None:
    """Resolve one exact campaign lifecycle window for a V2 stage-scoped job."""
    owner = _owned_campaign_scheduler_row(
        conn, scheduler_job_id=int(scheduler_job_id)
    )
    if owner is None:
        return None
    if (
        str(owner["work_scope"]) != "WINDOW_LIFECYCLE"
        or str(owner["stage_id"]) != str(expected_stage)
        or str(owner["target_category"]) != "CAMPAIGN_WINDOW"
        or owner["token_slot_id"] is None
        or owner["window_id"] is None
        or owner["factory_run_id"] is None
        or str(owner["target_identity"]) != str(owner["window_id"])
    ):
        raise ValueError(
            f"lifecycle Scheduler ownership is not exact {expected_stage}"
        )
    rows = conn.execute(
        """SELECT * FROM printer_memory_factory_campaign_windows
           WHERE window_id=? AND campaign_id=? AND run_id=? AND cycle_id=?
             AND token_slot_id=? AND window_kind=?""",
        (
            str(owner["window_id"]),
            str(owner["campaign_id"]),
            str(owner["run_id"]),
            str(owner["cycle_id"]),
            str(owner["token_slot_id"]),
            str(expected_window_kind),
        ),
    ).fetchall()
    if len(rows) != 1:
        raise ValueError(
            f"owned lifecycle job has no unique exact {expected_window_kind}"
        )
    return rows[0]


def _owned_continuation_window_for_job(
    conn: sqlite3.Connection, *, scheduler_job_id: int,
) -> sqlite3.Row | None:
    """Resolve the exact WINDOW_1H campaign window owned by one continuation job."""
    return _owned_lifecycle_window_for_job(
        conn,
        scheduler_job_id=int(scheduler_job_id),
        expected_stage="WINDOW_1H",
        expected_window_kind="WINDOW_1H",
    )


def _owned_long_window_for_job(
    conn: sqlite3.Connection, *, scheduler_job_id: int,
) -> sqlite3.Row | None:
    """Resolve the exact WINDOW_4H campaign window owned by one long job."""
    return _owned_lifecycle_window_for_job(
        conn,
        scheduler_job_id=int(scheduler_job_id),
        expected_stage="WINDOW_4H",
        expected_window_kind="WINDOW_4H",
    )


def _mark_owned_continuation_window_collecting(
    conn: sqlite3.Connection, *, scheduler_job_id: int, step_kind: str,
) -> str | None:
    """Advance the exact first-hour window when real continuation collection starts."""
    if str(step_kind) != "CONTINUATION_SNAPSHOT":
        return None
    window = _owned_continuation_window_for_job(
        conn, scheduler_job_id=int(scheduler_job_id)
    )
    if window is None:
        return None
    state = str(window["window_state"])
    if state == "COLLECTING":
        return state
    if state != "PLANNED":
        raise ValueError(
            f"WINDOW_1H collection state conflict: expected PLANNED/COLLECTING, found {state}"
        )
    from printer_v1.operator_cli.campaign_ownership import transition_state

    transitioned = transition_state(
        conn,
        record_kind="window",
        identity=str(window["window_id"]),
        expected_state="PLANNED",
        new_state="COLLECTING",
    )
    return str(transitioned.current_state)


def _mark_owned_continuation_window_close_pending(
    conn: sqlite3.Connection, *, scheduler_job_id: int, step_kind: str,
) -> str | None:
    """Advance the exact first-hour window when its real close job is claimed."""
    if str(step_kind) not in {"CONTINUATION_CLOSE", "CONTINUATION_CLOSE_EVIDENCE"}:
        return None
    window = _owned_continuation_window_for_job(
        conn, scheduler_job_id=int(scheduler_job_id)
    )
    if window is None:
        return None
    state = str(window["window_state"])
    if state == "CLOSE_PENDING":
        return state
    if state != "COLLECTING":
        raise ValueError(
            "WINDOW_1H close state conflict: expected COLLECTING/CLOSE_PENDING, "
            f"found {state}"
        )
    from printer_v1.operator_cli.campaign_ownership import transition_state

    transitioned = transition_state(
        conn,
        record_kind="window",
        identity=str(window["window_id"]),
        expected_state="COLLECTING",
        new_state="CLOSE_PENDING",
    )
    return str(transitioned.current_state)



def _mark_owned_long_window_collecting(
    conn: sqlite3.Connection, *, scheduler_job_id: int, step_kind: str,
) -> str | None:
    """Advance the exact four-hour window when long collection actually starts."""
    if str(step_kind) != "LONG_CONTINUATION_SNAPSHOT":
        return None
    window = _owned_long_window_for_job(
        conn, scheduler_job_id=int(scheduler_job_id)
    )
    if window is None:
        return None
    state = str(window["window_state"])
    if state == "COLLECTING":
        return state
    if state != "PLANNED":
        raise ValueError(
            f"WINDOW_4H collection state conflict: expected PLANNED/COLLECTING, found {state}"
        )
    from printer_v1.operator_cli.campaign_ownership import transition_state

    transitioned = transition_state(
        conn,
        record_kind="window",
        identity=str(window["window_id"]),
        expected_state="PLANNED",
        new_state="COLLECTING",
    )
    return str(transitioned.current_state)


def _mark_owned_long_window_close_pending(
    conn: sqlite3.Connection, *, scheduler_job_id: int, step_kind: str,
) -> str | None:
    """Advance the exact four-hour window when its long close job is claimed."""
    if str(step_kind) not in {
        "LONG_CONTINUATION_CLOSE",
        "LONG_CONTINUATION_CLOSE_EVIDENCE",
    }:
        return None
    window = _owned_long_window_for_job(
        conn, scheduler_job_id=int(scheduler_job_id)
    )
    if window is None:
        return None
    state = str(window["window_state"])
    if state == "CLOSE_PENDING":
        return state
    if state != "COLLECTING":
        raise ValueError(
            "WINDOW_4H close state conflict: expected COLLECTING/CLOSE_PENDING, "
            f"found {state}"
        )
    from printer_v1.operator_cli.campaign_ownership import transition_state

    transitioned = transition_state(
        conn,
        record_kind="window",
        identity=str(window["window_id"]),
        expected_state="COLLECTING",
        new_state="CLOSE_PENDING",
    )
    return str(transitioned.current_state)


def _classify_owned_1h_terminal_state(
    conn: sqlite3.Connection, *, memory_window_row_id: int,
) -> str:
    """Classify campaign terminal state from authoritative first-hour memory truth."""
    memory = conn.execute(
        """SELECT id,window_kind,data_quality_label,do_not_train
           FROM printer_memory_windows WHERE id=?""",
        (int(memory_window_row_id),),
    ).fetchone()
    if memory is None or str(memory["window_kind"]) != "WINDOW_1H":
        raise ValueError("WINDOW_1H terminal classification target mismatch")
    clean_episode = conn.execute(
        """SELECT id FROM printer_episodes
           WHERE memory_window_id=?
             AND episode_kind='WINDOW_1H_CLEAN_MEMORY'
             AND memory_status='CLEAN_MEMORY'
             AND data_quality_label='CLEAN_DATA'
             AND do_not_train=0
           ORDER BY id LIMIT 1""",
        (int(memory_window_row_id),),
    ).fetchone()
    if clean_episode is not None:
        return "CLEAN_PROMOTED"
    if int(memory["do_not_train"] or 0) != 0 or str(
        memory["data_quality_label"] or ""
    ) != "CLEAN_DATA":
        return "DIRTY"
    return "NO_PROMOTION"


def _bind_owned_continuation_memory_window_at_close(
    conn: sqlite3.Connection,
    *,
    scheduler_job_id: int,
    memory_window_row_id: int,
) -> int | None:
    """Atomically bind and terminally reconcile one successful first-hour close."""
    window = _owned_continuation_window_for_job(
        conn, scheduler_job_id=int(scheduler_job_id)
    )
    if window is None:
        return None
    terminal_state = _classify_owned_1h_terminal_state(
        conn, memory_window_row_id=int(memory_window_row_id)
    )
    from printer_v1.operator_cli.operational_selective_1h import (
        reconcile_1h_terminal_lifecycle,
    )

    reconcile_1h_terminal_lifecycle(
        conn,
        campaign_window_1h_id=str(window["window_id"]),
        memory_window_row_id=int(memory_window_row_id),
        terminal_state=terminal_state,
        terminal_cause=f"window_1h_closed_{terminal_state.lower()}",
    )
    return int(memory_window_row_id)


def _terminalize_owned_continuation_window(
    conn: sqlite3.Connection,
    *,
    scheduler_job_id: int,
    terminal_state: str,
    terminal_cause: str,
) -> str | None:
    """Fail/cancel one exact first-hour lifecycle without touching its peer."""
    window = _owned_continuation_window_for_job(
        conn, scheduler_job_id=int(scheduler_job_id)
    )
    if window is None:
        return None
    from printer_v1.operator_cli.operational_selective_1h import (
        reconcile_1h_terminal_lifecycle,
    )

    reconciled = reconcile_1h_terminal_lifecycle(
        conn,
        campaign_window_1h_id=str(window["window_id"]),
        terminal_state=str(terminal_state),
        terminal_cause=str(terminal_cause),
    )
    return str(reconciled["window_state"])




def _exact_complete_clean_4h_object(
    conn: sqlite3.Connection, *, memory_window_row_id: int,
) -> dict[str, Any] | None:
    rows = conn.execute(
        """SELECT e.id AS episode_id,f.id AS fingerprint_id,e.token_id,e.pair_id,
                  e.window_kind,e.memory_window_id
           FROM printer_episodes AS e
           JOIN printer_memory_fingerprints AS f
             ON f.episode_id=e.id
            AND f.fingerprint_kind='STATIC_CONDITION_SUMMARY'
            AND f.memory_status='CLEAN_MEMORY'
            AND f.data_quality_label='CLEAN_DATA'
            AND f.do_not_train=0
           WHERE e.memory_window_id=?
             AND e.episode_kind='WINDOW_4H_CLEAN_MEMORY'
             AND e.window_kind='WINDOW_4H'
             AND e.episode_status='COMPLETE'
             AND e.memory_status='CLEAN_MEMORY'
             AND e.data_quality_label='CLEAN_DATA'
             AND e.do_not_train=0
             AND e.memory_quality_label='CLEAN_MEMORY'
             AND json_extract(f.fingerprint_payload_json,'$.episode_id')=e.id
             AND json_extract(f.fingerprint_payload_json,'$.window_id')=e.memory_window_id
             AND json_extract(f.fingerprint_payload_json,'$.token_id')=e.token_id
             AND json_extract(f.fingerprint_payload_json,'$.pair_id')=e.pair_id
             AND json_extract(f.fingerprint_payload_json,'$.window_kind')=e.window_kind
           ORDER BY e.id,f.id""",
        (int(memory_window_row_id),),
    ).fetchall()
    if not rows:
        return None
    identities = {
        (int(row["episode_id"]), int(row["fingerprint_id"])) for row in rows
    }
    if len(identities) != 1:
        raise ValueError("WINDOW_4H_CLEAN_OBJECT_IDENTITY_AMBIGUOUS")
    return dict(rows[0])


def _classify_owned_4h_terminal_state(
    conn: sqlite3.Connection,
    *,
    memory_window_row_id: int,
    result: Mapping[str, Any],
) -> str:
    """Classify campaign terminal truth from the exact physical 4h result."""
    memory = conn.execute(
        """SELECT id,token_id,pair_id,window_kind,window_status,memory_status,
                  memory_quality_label,data_quality_label,do_not_train,outcome_label
           FROM printer_memory_windows WHERE id=?""",
        (int(memory_window_row_id),),
    ).fetchone()
    if (
        memory is None
        or str(memory["window_kind"]) != "WINDOW_4H"
        or str(memory["window_status"] or "") != "WINDOW_CLOSED"
    ):
        raise ValueError("WINDOW_4H terminal classification target mismatch")
    clean_object = _exact_complete_clean_4h_object(
        conn, memory_window_row_id=int(memory_window_row_id)
    )
    pipeline = result.get("memory_pipeline") if isinstance(result, Mapping) else None
    memory_event = pipeline.get("memory") if isinstance(pipeline, Mapping) else None
    e2z_status = (
        str(memory_event.get("e2z_status"))
        if isinstance(memory_event, Mapping) and memory_event.get("e2z_status") is not None
        else None
    )
    if clean_object is not None:
        if e2z_status == "E2Z_MEMORY_CREATED":
            return "CLEAN_PROMOTED"
        if e2z_status == "E2Z_ALREADY_EXISTS":
            return "ALREADY_EXISTS_IDEMPOTENT"
        raise ValueError("WINDOW_4H_CLEAN_OBJECT_WITHOUT_EXACT_E2Z_EVENT")
    if (
        int(memory["do_not_train"] or 0) != 0
        or str(memory["data_quality_label"] or "") != "CLEAN_DATA"
        or str(memory["memory_status"] or "") in {
            "DIRTY_MEMORY", "AUDIT_ONLY_MEMORY", "DO_NOT_TRAIN"
        }
        or str(memory["memory_quality_label"] or "") in {
            "DIRTY_MEMORY", "AUDIT_ONLY_MEMORY", "DO_NOT_TRAIN"
        }
    ):
        return "DIRTY"
    return "NO_PROMOTION"


def _bind_owned_long_memory_window_at_close(
    conn: sqlite3.Connection,
    *,
    scheduler_job_id: int,
    memory_window_row_id: int,
    result: Mapping[str, Any],
) -> dict[str, Any] | None:
    """Bind one successful physical 4h close to its exact campaign lifecycle."""
    window = _owned_long_window_for_job(
        conn, scheduler_job_id=int(scheduler_job_id)
    )
    if window is None:
        return None
    memory = conn.execute(
        """SELECT token_id,pair_id,window_kind FROM printer_memory_windows WHERE id=?""",
        (int(memory_window_row_id),),
    ).fetchone()
    if (
        memory is None
        or int(memory["token_id"]) != int(window["token_row_id"])
        or int(memory["pair_id"]) != int(window["pair_row_id"])
        or str(memory["window_kind"]) != "WINDOW_4H"
    ):
        raise ValueError("WINDOW_4H_CAMPAIGN_PHYSICAL_IDENTITY_MISMATCH")
    terminal_state = _classify_owned_4h_terminal_state(
        conn,
        memory_window_row_id=int(memory_window_row_id),
        result=result,
    )
    from printer_v1.operator_cli.one_token_4h_runtime import (
        reconcile_4h_terminal_lifecycle,
    )

    return reconcile_4h_terminal_lifecycle(
        conn,
        campaign_window_4h_id=str(window["window_id"]),
        terminal_state=terminal_state,
        terminal_cause=f"window_4h_closed_{terminal_state.lower()}",
        memory_window_row_id=int(memory_window_row_id),
    )


def _terminalize_owned_long_window(
    conn: sqlite3.Connection,
    *,
    scheduler_job_id: int,
    terminal_state: str,
    terminal_cause: str,
) -> str | None:
    """Fail/cancel one exact four-hour lifecycle without touching its peer."""
    desired_window = str(terminal_state)
    desired_slot = {
        "BLOCKED": "FAILED",
        "CANCELLED": "MANUAL_REVIEW",
    }.get(desired_window)
    if desired_slot is None:
        raise ValueError(f"unsupported WINDOW_4H collection terminal state: {desired_window}")
    cause = str(terminal_cause).strip()
    if not cause:
        raise ValueError("WINDOW_4H terminal cause must be non-empty")
    window = _owned_long_window_for_job(
        conn, scheduler_job_id=int(scheduler_job_id)
    )
    if window is None:
        return None
    timestamp = _iso()
    savepoint = "printer_window_4h_collection_terminal"
    conn.execute(f"SAVEPOINT {savepoint}")
    try:
        current_window = conn.execute(
            """SELECT campaign_id,run_id,cycle_id,token_slot_id,token_row_id,
                      pair_row_id,window_state,first_terminal_cause,terminal_at
               FROM printer_memory_factory_campaign_windows WHERE window_id=?""",
            (str(window["window_id"]),),
        ).fetchone()
        if current_window is None:
            raise ValueError("WINDOW_4H terminal window disappeared")
        slot = conn.execute(
            """SELECT token_state,first_terminal_cause,terminal_at,token_row_id,pair_row_id
               FROM printer_memory_factory_campaign_token_slots
               WHERE token_slot_id=? AND campaign_id=? AND run_id=? AND cycle_id=?""",
            (
                str(current_window["token_slot_id"]),
                str(current_window["campaign_id"]),
                str(current_window["run_id"]),
                str(current_window["cycle_id"]),
            ),
        ).fetchone()
        if slot is None:
            raise ValueError("WINDOW_4H terminal token slot missing")
        if (
            int(slot["token_row_id"]) != int(current_window["token_row_id"])
            or int(slot["pair_row_id"]) != int(current_window["pair_row_id"])
        ):
            raise ValueError("WINDOW_4H terminal token/pair identity mismatch")
        window_state = str(current_window["window_state"])
        slot_state = str(slot["token_state"])
        if window_state == desired_window or slot_state == desired_slot:
            if not (
                window_state == desired_window
                and slot_state == desired_slot
                and str(current_window["first_terminal_cause"] or "") == cause
                and str(slot["first_terminal_cause"] or "") == cause
                and current_window["terminal_at"] is not None
                and slot["terminal_at"] is not None
            ):
                raise ValueError("conflicting WINDOW_4H terminal replay")
            conn.execute(f"RELEASE SAVEPOINT {savepoint}")
            return desired_window
        if window_state not in {"PLANNED", "COLLECTING", "CLOSE_PENDING", "AUDITING"}:
            raise ValueError(f"WINDOW_4H cannot terminalize from {window_state}")
        if slot_state != "WINDOW_4H_CONTINUING":
            raise ValueError(f"WINDOW_4H slot cannot terminalize from {slot_state}")
        window_update = conn.execute(
            """UPDATE printer_memory_factory_campaign_windows
               SET window_state=?,first_terminal_cause=?,terminal_at=?,updated_at=?
               WHERE window_id=? AND window_state=? AND first_terminal_cause IS NULL""",
            (
                desired_window,
                cause,
                timestamp,
                timestamp,
                str(window["window_id"]),
                window_state,
            ),
        )
        if window_update.rowcount != 1:
            raise ValueError("WINDOW_4H terminal compare-and-update failed")
        slot_update = conn.execute(
            """UPDATE printer_memory_factory_campaign_token_slots
               SET token_state=?,first_terminal_cause=?,terminal_at=?,updated_at=?
               WHERE token_slot_id=? AND token_state='WINDOW_4H_CONTINUING'
                 AND first_terminal_cause IS NULL""",
            (
                desired_slot,
                cause,
                timestamp,
                timestamp,
                str(current_window["token_slot_id"]),
            ),
        )
        if slot_update.rowcount != 1:
            raise ValueError("WINDOW_4H slot terminal compare-and-update failed")
        verify = conn.execute(
            """SELECT w.window_state,w.first_terminal_cause,s.token_state,s.first_terminal_cause
               FROM printer_memory_factory_campaign_windows AS w
               JOIN printer_memory_factory_campaign_token_slots AS s
                 ON s.token_slot_id=w.token_slot_id
               WHERE w.window_id=?""",
            (str(window["window_id"]),),
        ).fetchone()
        if (
            verify is None
            or str(verify[0]) != desired_window
            or str(verify[1]) != cause
            or str(verify[2]) != desired_slot
            or str(verify[3]) != cause
        ):
            raise ValueError("WINDOW_4H terminal read-back mismatch")
        conn.execute(f"RELEASE SAVEPOINT {savepoint}")
        return desired_window
    except Exception:
        conn.execute(f"ROLLBACK TO SAVEPOINT {savepoint}")
        conn.execute(f"RELEASE SAVEPOINT {savepoint}")
        raise


def _cancel_owned_continuation_windows_for_run(
    conn: sqlite3.Connection, *, factory_run_id: str, terminal_cause: str,
) -> int:
    """Cancel nonterminal owned WINDOW_1H and WINDOW_4H lifecycles after shared stop."""
    rows = conn.execute(
        """SELECT w.window_id,w.window_state,w.window_kind,sw.stage_id,
                  MIN(sw.scheduler_job_id) AS scheduler_job_id
           FROM printer_memory_factory_campaign_scheduler_work AS sw
           JOIN printer_memory_factory_campaign_windows AS w
             ON w.window_id=sw.window_id
           WHERE sw.factory_run_id=?
             AND sw.ownership_contract_version='V2_STAGE_SCOPED'
             AND sw.work_scope='WINDOW_LIFECYCLE'
             AND (
                 (sw.stage_id='WINDOW_1H' AND w.window_kind='WINDOW_1H')
                 OR
                 (sw.stage_id='WINDOW_4H' AND w.window_kind='WINDOW_4H')
             )
           GROUP BY w.window_id,w.window_state,w.window_kind,sw.stage_id
           ORDER BY w.window_id""",
        (str(factory_run_id),),
    ).fetchall()
    active_states = {"PLANNED", "COLLECTING", "CLOSE_PENDING", "AUDITING"}
    changed = 0
    if not rows:
        return changed
    from printer_v1.operator_cli.operational_selective_1h import (
        reconcile_1h_terminal_lifecycle,
    )

    for row in rows:
        state = str(row["window_state"])
        if state not in active_states:
            continue
        if str(row["window_kind"]) == "WINDOW_1H":
            reconcile_1h_terminal_lifecycle(
                conn,
                campaign_window_1h_id=str(row["window_id"]),
                terminal_state="CANCELLED",
                terminal_cause=str(terminal_cause),
            )
        elif str(row["window_kind"]) == "WINDOW_4H":
            if row["scheduler_job_id"] is None:
                raise ValueError("WINDOW_4H shared cleanup has no Scheduler owner")
            _terminalize_owned_long_window(
                conn,
                scheduler_job_id=int(row["scheduler_job_id"]),
                terminal_state="CANCELLED",
                terminal_cause=str(terminal_cause),
            )
        else:
            raise ValueError("unsupported owned lifecycle window in shared cleanup")
        changed += 1
    return changed


def _lifecycle_reservation_records_for_step(
    *, run_id: str, pending: sqlite3.Row, projected_requests: int,
) -> list[dict[str, Any]]:
    """Build verification-only reservation identities for lifecycle source work."""
    step_kind = str(pending["step_kind"])
    supported = {
        "SNAPSHOT",
        "WINDOW_CLOSE",
        "CONTINUATION_SNAPSHOT",
        "CONTINUATION_CLOSE",
        "LONG_CONTINUATION_SNAPSHOT",
        "LONG_CONTINUATION_CLOSE",
        *CLOSE_PHASE_STEP_KINDS,
    }
    if step_kind not in supported:
        return []
    preclose_unit_identity: str | None = None
    preclose_unit_ordinal = 0
    if step_kind in PRE_CLOSE_STEP_KINDS:
        payload = _preclose_result_base(pending)
        preclose_unit_identity = str(
            payload.get("active_claim_source_unit_identity") or ""
        )
        matching_ordinals = [
            index
            for index, unit in enumerate(
                payload["source_unit_manifest"], start=1
            )
            if str(unit["source_unit_identity"]) == preclose_unit_identity
        ]
        if len(matching_ordinals) != 1:
            raise ValueError("PRE_CLOSE_RESERVATION_UNIT_IDENTITY_INVALID")
        preclose_unit_ordinal = matching_ordinals[0]
    records: list[dict[str, Any]] = []
    for reservation_index in range(int(projected_requests)):
        if step_kind in {"WINDOW_CLOSE", "WINDOW_CLOSE_EVIDENCE"}:
            family = (
                "CLOSE_OBSERVATION"
                if reservation_index == 0 else "PRECLOSE_CONTEXT"
            )
        elif step_kind == "WINDOW_CLOSE_CONTEXT":
            family = "PRECLOSE_CONTEXT"
        elif step_kind == "WINDOW_CLOSE_PRE_CLOSE_CRITICAL":
            family = "PRECLOSE_CONTEXT_SOURCE_UNIT"
        elif step_kind == "SNAPSHOT":
            family = "SNAPSHOT_OBSERVATION"
        elif step_kind == "CONTINUATION_SNAPSHOT":
            family = "CONTINUATION_SNAPSHOT_OBSERVATION"
        elif step_kind in {"CONTINUATION_CLOSE", "CONTINUATION_CLOSE_EVIDENCE"}:
            family = (
                "CONTINUATION_CLOSE_OBSERVATION"
                if reservation_index == 0 else "FIRST_HOUR_SAFETY_CONTEXT"
            )
        elif step_kind == "CONTINUATION_CLOSE_CONTEXT":
            family = "FIRST_HOUR_SAFETY_CONTEXT"
        elif step_kind == "CONTINUATION_CLOSE_PRE_CLOSE_CRITICAL":
            family = "FIRST_HOUR_SAFETY_SOURCE_UNIT"
        elif step_kind in {
            "LONG_CONTINUATION_CLOSE",
            "LONG_CONTINUATION_CLOSE_EVIDENCE",
        }:
            family = "LONG_CONTINUATION_CLOSE_OBSERVATION"
        elif step_kind == "LONG_CONTINUATION_CLOSE_CONTEXT":
            family = "LONG_CONTINUATION_CLOSE_CONTEXT"
        elif step_kind == "LONG_CONTINUATION_CLOSE_PRE_CLOSE_CRITICAL":
            family = "LONG_CONTINUATION_CLOSE_SOURCE_UNIT"
        elif str(pending["step_key"]).endswith("_snapshot_000"):
            family = "LONG_CONTINUATION_OPENING_OBSERVATION"
        else:
            family = "LONG_CONTINUATION_SNAPSHOT_OBSERVATION"
        records.append(
            {
                "boundary": "LIFECYCLE_RESERVATION",
                "run_id": str(run_id),
                "scheduler_job_id": int(pending["scheduler_job_id"]),
                "step_key": str(pending["step_key"]),
                "step_kind": step_kind,
                "token_id": int(pending["token_id"]),
                "pair_id": int(pending["pair_id"]),
                "reservation_ordinal": (
                    int(pending["scheduler_job_id"]) * 100
                    + (
                        preclose_unit_ordinal
                        if preclose_unit_identity is not None
                        else reservation_index
                    )
                ),
                "operation_family": family,
                "source_unit_identity": preclose_unit_identity,
            }
        )
    return records


def _observe_scheduler_terminal(
    conn: sqlite3.Connection,
    *,
    observer: Callable[[Mapping[str, Any]], None] | None,
    run_id: str,
    step: sqlite3.Row,
) -> None:
    if observer is None or step["scheduler_job_id"] is None:
        return
    job_id = int(step["scheduler_job_id"])
    terminal = conn.execute(
        """SELECT status,finished_at,last_error
           FROM printer_scheduler_jobs WHERE id=?""",
        (job_id,),
    ).fetchone()
    if terminal is None:
        raise ValueError(f"SCHEDULER_TERMINAL_ROW_MISSING:{job_id}")
    observer(
        {
            **_lifecycle_operation_cycle_identity(conn, job_id),
            "boundary": "SCHEDULER_TERMINAL",
            "run_id": run_id,
            "scheduler_job_id": job_id,
            "step_key": str(step["step_key"]),
            "step_kind": str(step["step_kind"]),
            "token_id": int(step["token_id"]),
            "pair_id": int(step["pair_id"]),
            "terminal_state": str(terminal["status"]),
            "first_terminal_cause": terminal["last_error"],
            "terminal_at": terminal["finished_at"],
        }
    )


def _register_repaired_campaign_window_before_terminalization(
    conn: sqlite3.Connection,
    *,
    step: sqlite3.Row,
    result: Mapping[str, Any],
    ownership_context: Mapping[str, Any] | None,
) -> dict[str, Any] | None:
    """Register an exact campaign window before Scheduler/slot terminalization.

    The caller has updated the close step to ``SUCCEEDED`` in the current
    transaction but has not terminalized its Scheduler job or begun campaign
    reconciliation.  The scope-aware campaign owner validates and commits the
    exact run/slot/window graph.  A fault rolls the pending step update back and
    therefore cannot leave a report-only ownership claim.
    """
    if ownership_context is None or str(step["step_kind"]) not in {
        "WINDOW_CLOSE", "WINDOW_CLOSE_AUDIT"
    }:
        return None
    memory_window_id = result.get("memory_window_id")
    if memory_window_id is None:
        raise ValueError("WINDOW_CLOSE_SUCCEEDED_WITHOUT_MEMORY_WINDOW")
    from printer_v1.operator_cli.campaign_ownership import (
        register_campaign_window_close,
    )

    slot = conn.execute(
        """SELECT token_slot_id, lifecycle_identity
           FROM printer_memory_factory_campaign_token_slots
           WHERE campaign_id=? AND run_id=? AND cycle_id=?
             AND token_row_id=? AND pair_row_id=?""",
        (
            str(ownership_context["campaign_id"]),
            str(ownership_context["campaign_run_id"]),
            str(ownership_context["cycle_id"]),
            int(step["token_id"]),
            int(step["pair_id"]),
        ),
    ).fetchone()
    if slot is None:
        raise ValueError("WINDOW_CLOSE_CAMPAIGN_SLOT_MISSING")
    memory = conn.execute(
        """SELECT memory_status, data_quality_label, do_not_train, closed_at
           FROM printer_memory_windows WHERE id=?""",
        (int(memory_window_id),),
    ).fetchone()
    if memory is None:
        raise ValueError("WINDOW_CLOSE_MEMORY_ROW_MISSING")
    clean_episode = conn.execute(
        """SELECT id FROM printer_episodes
           WHERE memory_window_id=?
             AND episode_kind='WINDOW_15M_CLEAN_MEMORY'
             AND memory_status='CLEAN_MEMORY'
             AND data_quality_label='CLEAN_DATA'
             AND do_not_train=0
           ORDER BY id LIMIT 1""",
        (int(memory_window_id),),
    ).fetchone()
    if clean_episode is not None:
        terminal_state = "CLEAN_PROMOTED"
    elif int(memory["do_not_train"] or 0) != 0 or str(
        memory["data_quality_label"] or ""
    ) != "CLEAN_DATA":
        terminal_state = "DIRTY"
    else:
        terminal_state = "NO_PROMOTION"
    if bool(ownership_context.get("proof_cycle_owned")):
        from printer_v1.operator_cli.operational_selective_1h import (
            persist_15m_campaign_window,
        )

        persisted = persist_15m_campaign_window(
            conn,
            campaign_id=str(ownership_context["campaign_id"]),
            run_id=str(ownership_context["campaign_run_id"]),
            cycle_id=str(ownership_context["cycle_id"]),
            token_slot_id=str(slot["token_slot_id"]),
            token_row_id=int(step["token_id"]),
            pair_row_id=int(step["pair_id"]),
            lifecycle_identity=str(slot["lifecycle_identity"]),
            memory_window_row_id=int(memory_window_id),
            checkpoint_cutoff=str(memory["closed_at"] or _iso()),
            window_state="AUDITING",
        )
        return {
            **persisted,
            "terminal_window_state": terminal_state,
            "precreated_window_reused": True,
        }
    campaign_window_id = (
        f"{ownership_context['cycle_id']}:window:{int(step['token_id'])}"
    )
    return register_campaign_window_close(
        conn,
        campaign_id=str(ownership_context["campaign_id"]),
        run_id=str(ownership_context["campaign_run_id"]),
        cycle_id=str(ownership_context["cycle_id"]),
        factory_run_id=str(ownership_context["factory_run_id"]),
        token_slot_id=str(slot["token_slot_id"]),
        window_id=campaign_window_id,
        close_step_id=int(step["id"]),
        memory_window_row_id=int(memory_window_id),
        root_15m_lifecycle_identity=str(slot["lifecycle_identity"]),
        checkpoint_cutoff=str(memory["closed_at"] or _iso()),
        terminal_window_state=terminal_state,
        terminal_cause=f"window_closed_{terminal_state.lower()}",
    )


def _cancel_pending(conn: sqlite3.Connection, run_id: str, reason: str) -> None:
    rows = conn.execute(
        "SELECT id, scheduler_job_id FROM printer_memory_factory_run_steps WHERE run_id=? AND step_status='PENDING'",
        (run_id,),
    ).fetchall()
    for row in rows:
        if row["scheduler_job_id"] is not None:
            cancel_job(conn, job_id=int(row["scheduler_job_id"]))
            _sync_owned_campaign_scheduler_job(
                conn, scheduler_job_id=int(row["scheduler_job_id"])
            )
        conn.execute(
            "UPDATE printer_memory_factory_run_steps SET step_status='CANCELLED', error_or_skip_reason=?, finished_at=?, updated_at=? WHERE id=?",
            (reason, _iso(), _iso(), int(row["id"])),
        )


def _cancel_pending_for_token(
    conn: sqlite3.Connection, run_id: str, token_id: int, reason: str,
) -> int:
    """Cancel only the given token's pending steps (V2-5 failure isolation).

    Other tokens' pending steps are untouched. Returns the number cancelled.
    """
    rows = conn.execute(
        "SELECT id, scheduler_job_id FROM printer_memory_factory_run_steps "
        "WHERE run_id=? AND token_id=? AND step_status='PENDING'",
        (run_id, token_id),
    ).fetchall()
    for row in rows:
        if row["scheduler_job_id"] is not None:
            cancel_job(conn, job_id=int(row["scheduler_job_id"]))
            _sync_owned_campaign_scheduler_job(
                conn, scheduler_job_id=int(row["scheduler_job_id"])
            )
        conn.execute(
            "UPDATE printer_memory_factory_run_steps SET step_status='CANCELLED', error_or_skip_reason=?, finished_at=?, updated_at=? WHERE id=?",
            (reason, _iso(), _iso(), int(row["id"])),
        )
    return len(rows)


def _cancel_campaign_discovery_jobs(
    conn: sqlite3.Connection,
    discovery_batch_id: str | None,
    *,
    campaign_id: str | None = None,
    campaign_run_id: str | None = None,
    cycle_id: str | None = None,
    terminal_cause: str = "DISCOVERY_WORK_ABANDONED_AT_TERMINAL",
) -> dict[str, Any]:
    """Bring campaign discovery work and its Scheduler jobs to terminal parity.

    V2-9.7E.47 A2. Two defects are repaired here.

    1. The caller previously passed the *handoff* batch id
       (``origin-activated:<cycle>``) while the executor writes its work rows
       under ``discovery-batch:<campaign>:<run>:<cycle>``, so the old query
       matched zero rows and never cancelled anything — the exact mechanism that
       left eight ``DISCOVERY_REFRESH`` jobs ``PENDING`` at V2-9.7E.46 §10.2.
       The scope now also accepts the campaign / run / cycle identities, which
       every discovery work row carries directly.
    2. Cancelling was the wrong terminal for *successful* work. Parity is now
       driven by the work row's own terminal state through the Scheduler owner:
       ``SUCCEEDED`` work completes its job, ``FAILED`` work fails it, and only
       abandoned or terminally unnecessary work is cancelled.
    """
    if not any((discovery_batch_id, campaign_id, campaign_run_id, cycle_id)):
        return {
            "discovery_batch_id": None,
            "cancelled_jobs": 0,
            "job_actions": {},
            "terminal_work_with_active_job": 0,
        }
    # Identity scope wins when available: the id the factory receives is the
    # *handoff* batch (`origin-activated:<cycle>`), which is not the executor's
    # discovery batch id and matches no work row. Combining the two with AND
    # would reproduce the E.46 zero-match defect, so the handoff id is used only
    # as the fallback scope when no ownership identity was supplied.
    identity_scope = any((campaign_id, campaign_run_id, cycle_id))
    parity = reconcile_discovery_work_jobs(
        conn,
        discovery_batch_id=None if identity_scope else discovery_batch_id,
        campaign_id=campaign_id,
        run_id=campaign_run_id,
        cycle_id=cycle_id,
        abandoned_cause=terminal_cause,
    )
    actions = dict(parity["job_actions"])
    return {
        "discovery_batch_id": discovery_batch_id,
        "scope": parity["scope"],
        "work_rows": parity["work_rows"],
        "cancelled_active_work": parity["cancelled_active_work"],
        "cancelled_jobs": int(actions.get("CANCEL", 0)),
        "completed_jobs": int(actions.get("COMPLETE", 0)),
        "failed_jobs": int(actions.get("FAIL", 0)),
        "job_actions": actions,
        "terminal_work_with_active_job": parity["terminal_work_with_active_job"],
    }


def _token_prefix(step_key: str) -> str:
    """Return the exact proof prefix or the unchanged legacy token prefix."""
    from printer_v1.operator_cli.four_token_proof_integration import (
        FourTokenProofPolicyError,
        parse_cycle_step_key,
    )

    try:
        parsed = parse_cycle_step_key(str(step_key))
    except FourTokenProofPolicyError:
        return str(step_key).split("_", 1)[0]
    if parsed.cycle_ordinal == 1:
        return f"t{parsed.slot_ordinal}"
    return f"t{parsed.slot_ordinal}_c{parsed.cycle_ordinal:04d}"


def _run_request_count(conn: sqlite3.Connection, run_id: str) -> int:
    return int(conn.execute(
        "SELECT COUNT(*) FROM printer_source_requests WHERE request_key LIKE ?",
        (f"{run_id}:%",),
    ).fetchone()[0])


def _token_request_count(conn: sqlite3.Connection, run_id: str, token_prefix: str) -> int:
    run_prefix = f"{run_id}:"
    rows = conn.execute(
        "SELECT request_key FROM printer_source_requests "
        "WHERE request_key>=? AND request_key<?",
        (run_prefix, run_prefix + "\uffff"),
    ).fetchall()
    count = 0
    for row in rows:
        request_key = str(row[0] or "")
        step_key = request_key[len(run_prefix):].split(":", 1)[0]
        if _token_prefix(step_key) == token_prefix:
            count += 1
    return count


def _scheduler_ceiling_for_run_config(config: Mapping[str, Any]) -> int:
    if bool(config.get("four_token_proof")):
        from printer_v1.operator_cli.multi_cycle_memory_growth import (
            scaled_standard_four_hour_capacity_contract,
        )

        return int(
            scaled_standard_four_hour_capacity_contract(4)[
                "lifecycle_scheduler_outer_ceiling"
            ]
        )
    continuous = bool(config.get("continuous_first_hour"))
    selective_1h = _selective_1h_lifecycle(config)
    compressed_two_token = _two_token_lifecycle(config)
    return (
        _SELECTIVE_1H_MAX_SCHEDULER_ROWS
        if selective_1h
        else _COMPRESSED_TWO_TOKEN_MAX_SCHEDULER_ROWS
        if compressed_two_token
        else _CONTINUOUS_MAX_SCHEDULER_ROWS
        if continuous
        else _MAX_SCHEDULER_ROWS
    )


def _run_step_job_count(conn: sqlite3.Connection, run_id: str) -> int:
    return int(conn.execute(
        "SELECT COUNT(*) FROM printer_scheduler_jobs WHERE job_name LIKE ?",
        (f"v2_4_{run_id}_%",),
    ).fetchone()[0])


def _projected_requests_for_step(
    conn_or_step: sqlite3.Connection | sqlite3.Row,
    step: sqlite3.Row | None = None,
) -> int:
    conn = conn_or_step if isinstance(conn_or_step, sqlite3.Connection) else None
    current_step = step if step is not None else conn_or_step
    # A snapshot step issues one governed request; a close step issues one
    # snapshot request plus up to five close-time context requests.
    if str(current_step["step_kind"]) in PRE_CLOSE_STEP_KINDS:
        if conn is None:
            return 1
        phase = _preclose_result_base(current_step)
        active_identity = str(
            phase.get("active_claim_source_unit_identity") or ""
        )
        units = [
            unit
            for unit in phase["source_unit_manifest"]
            if str(unit["source_unit_identity"]) == active_identity
        ]
        if len(units) != 1:
            return 0
        return 0 if _reconcile_preclose_request(conn, units[0])["state"] != "NO_REQUEST" else 1
    if current_step["step_kind"] in LIFECYCLE_RESERVED_OPERATIONS_BY_STEP_KIND:
        return int(
            LIFECYCLE_RESERVED_OPERATIONS_BY_STEP_KIND[str(current_step["step_kind"])]
        )
    if current_step["step_kind"] == "LONG_CONTINUATION_CLOSE":
        return 5
    if current_step["step_kind"] == "LONG_CONTINUATION_SNAPSHOT" and str(current_step["step_key"]).endswith("_snapshot_000"):
        return 3
    return 1


def _standard_four_hour_cumulative_budget_for_run(
    conn: sqlite3.Connection,
    run_id: str,
    *,
    cycle_id: str | None = None,
) -> dict[str, Any]:
    """Resolve the exact standard 4h subset budget from durable campaign truth."""
    config = _load_run_config(conn, run_id)
    campaign_id = str(config.get("campaign_id") or "").strip()
    campaign_run_id = str(config.get("campaign_run_id") or "").strip()
    owned_cycle_id = str(cycle_id or config.get("cycle_id") or "").strip()
    if not all((campaign_id, campaign_run_id, owned_cycle_id, run_id)):
        raise ValueError("standard four-hour execution budget identity is incomplete")

    from printer_v1.operator_cli.one_token_4h_runtime import (
        load_standard_four_hour_eligibility_manifests,
        standard_campaign_lifecycle_budget,
    )

    slots = conn.execute(
        """SELECT token_slot_id,token_row_id,pair_row_id,slot_ordinal
           FROM printer_memory_factory_campaign_token_slots
           WHERE campaign_id=? AND run_id=? AND cycle_id=?
           ORDER BY slot_ordinal""",
        (campaign_id, campaign_run_id, owned_cycle_id),
    ).fetchall()
    if len(slots) != 2 or {int(row["slot_ordinal"]) for row in slots} != {1, 2}:
        raise ValueError("standard four-hour execution budget requires exact two campaign slots")

    manifests = load_standard_four_hour_eligibility_manifests(
        conn,
        campaign_id=campaign_id,
        run_id=campaign_run_id,
        cycle_id=owned_cycle_id,
        factory_run_id=run_id,
    )
    if manifests is None:
        raise ValueError("standard four-hour execution budget requires durable eligibility manifest")

    lanes: list[str] = []
    mask: list[bool] = []
    scoped_step_ids: tuple[int, ...] | None = None
    if cycle_id is not None:
        from printer_v1.operator_cli.four_token_proof_integration import (
            cycle_scoped_factory_step_ids,
        )

        scoped_step_ids = cycle_scoped_factory_step_ids(
            conn,
            campaign_id=campaign_id,
            campaign_run_id=campaign_run_id,
            factory_run_id=run_id,
            cycle_id=owned_cycle_id,
        )
        if not scoped_step_ids:
            raise ValueError("standard four-hour cycle has no owned factory steps")
    for slot in slots:
        slot_id = str(slot["token_slot_id"])
        if scoped_step_ids is None:
            closes = conn.execute(
                """SELECT tracking_lane FROM printer_memory_factory_run_steps
                   WHERE run_id=? AND token_id=? AND pair_id=?
                     AND step_kind IN ('CONTINUATION_CLOSE','CONTINUATION_CLOSE_AUDIT')
                     AND step_status='SUCCEEDED'
                   ORDER BY id""",
                (run_id, int(slot["token_row_id"]), int(slot["pair_row_id"])),
            ).fetchall()
        else:
            placeholders = ",".join("?" for _ in scoped_step_ids)
            closes = conn.execute(
                "SELECT tracking_lane FROM printer_memory_factory_run_steps "
                "WHERE run_id=? AND token_id=? AND pair_id=? "
                "AND step_kind IN ('CONTINUATION_CLOSE','CONTINUATION_CLOSE_AUDIT') "
                "AND step_status='SUCCEEDED' "
                f"AND id IN ({placeholders}) ORDER BY id",
                (
                    run_id,
                    int(slot["token_row_id"]),
                    int(slot["pair_row_id"]),
                    *scoped_step_ids,
                ),
            ).fetchall()
        if len(closes) != 1:
            raise ValueError(
                f"standard four-hour execution budget close identity missing/ambiguous for {slot_id}"
            )
        manifest = manifests.get(slot_id)
        if manifest is None or type(manifest.get("eligible")) is not bool:
            raise ValueError(
                f"standard four-hour execution budget manifest invalid for {slot_id}"
            )
        lanes.append(str(closes[0]["tracking_lane"]))
        mask.append(bool(manifest["eligible"]))

    budget = standard_campaign_lifecycle_budget(
        (lanes[0], lanes[1]), (mask[0], mask[1])
    )
    return {
        **budget,
        "cycle_id": owned_cycle_id,
        "expected_token_capacity": 2,
        "factory_step_ids": scoped_step_ids,
    }


def _standard_four_hour_reporting_budget_for_run(
    conn: sqlite3.Connection, run_id: str,
) -> dict[str, Any]:
    """Resolve reporting from the same exact standard subset owner as execution."""
    try:
        budget = _standard_four_hour_cumulative_budget_for_run(conn, run_id)
    except ValueError as exc:
        return {
            "available": False,
            "reason": str(exc),
            "budget": None,
        }
    return {
        "available": True,
        "reason": None,
        "budget": budget,
    }


def _enforce_budgets_before_step(
    conn: sqlite3.Connection,
    run_id: str,
    step: sqlite3.Row,
    *,
    projected_requests: int | None = None,
) -> None:
    """Raise _GlobalStop if executing this step would breach a hard ceiling.

    Hard ceilings are integrity limits, not targets: a projected breach is a
    global safe stop, never a silently exceeded call.
    """
    projected = (
        _projected_requests_for_step(conn, step)
        if projected_requests is None
        else int(projected_requests)
    )
    config = _load_run_config(conn, run_id)
    if str(step["step_kind"]).startswith("LONG_CONTINUATION_"):
        from printer_v1.operator_cli.one_token_4h_runtime import (
            cumulative_lifecycle_budget,
            require_projected_capacity,
            runtime_budget,
        )
        lane = str(step["tracking_lane"])
        phase = runtime_budget(lane)
        if bool(config.get("standard_four_hour_campaign")):
            try:
                budget_cycle_id: str | None = None
                if bool(config.get("four_token_proof")):
                    from printer_v1.operator_cli.four_token_proof_integration import (
                        resolve_owned_cycle_for_scheduler_job,
                    )

                    if step["scheduler_job_id"] is None:
                        raise ValueError(
                            "four-token standard step has no Scheduler identity"
                        )
                    budget_cycle_id = resolve_owned_cycle_for_scheduler_job(
                        conn,
                        scheduler_job_id=int(step["scheduler_job_id"]),
                        campaign_id=str(config.get("campaign_id") or ""),
                        campaign_run_id=str(config.get("campaign_run_id") or ""),
                        factory_run_id=run_id,
                    ).cycle_id
                cumulative = _standard_four_hour_cumulative_budget_for_run(
                    conn, run_id, cycle_id=budget_cycle_id
                )
            except ValueError as exc:
                raise _GlobalStop(
                    STOP_BUDGET, scope="STANDARD_FOUR_HOUR_SUBSET", detail=str(exc),
                ) from exc
            phase_request_ceiling = int(
                cumulative["phase_request_ceiling"]
            )
        else:
            cumulative = _cumulative_lifecycle_budget_for_run(conn, run_id, lane)
            phase_request_ceiling = int(phase["phase_request_ceiling"])
        phase_used = int(conn.execute(
            "SELECT COUNT(*) FROM printer_source_requests WHERE request_key LIKE ?",
            (f"{run_id}:%4h%",),
        ).fetchone()[0])
        # Discovery precedes run-local request keys; reserve its approved maximum.
        discovery_used = int(cumulative["request_components"]["discovery"])
        cumulative_used = discovery_used + _run_request_count(conn, run_id)
        try:
            require_projected_capacity(
                current=phase_used, projected=projected,
                ceiling=phase_request_ceiling,
                label="4h phase request",
            )
        except ValueError as exc:
            raise _GlobalStop(
                STOP_BUDGET, scope="FOUR_HOUR_PHASE", detail=str(exc),
            ) from exc
        try:
            require_projected_capacity(
                current=cumulative_used, projected=projected,
                ceiling=int(cumulative["request_ceiling"]),
                label="cumulative lifecycle request",
            )
        except ValueError as exc:
            raise _GlobalStop(
                STOP_BUDGET, scope="CUMULATIVE_LIFECYCLE", detail=str(exc),
            ) from exc
        return
    continuous = bool(config.get("continuous_first_hour"))
    selective_1h = _selective_1h_lifecycle(config)
    compressed_two_token = _two_token_lifecycle(config)
    run_ceiling = (
        _SELECTIVE_1H_MAX_REQUESTS_RUN
        if selective_1h
        else _COMPRESSED_TWO_TOKEN_MAX_REQUESTS_RUN
        if compressed_two_token
        else _CONTINUOUS_MAX_REQUESTS_RUN
        if continuous
        else _MAX_GOVERNED_REQUESTS_RUN
    )
    token_ceiling = (
        _CONTINUOUS_MAX_REQUESTS_PER_TOKEN
        if continuous else _MAX_GOVERNED_REQUESTS_PER_TOKEN
    )
    if _run_request_count(conn, run_id) + projected > run_ceiling:
        raise _GlobalStop(STOP_BUDGET, scope="CUMULATIVE_LIFECYCLE")
    prefix = _token_prefix(step["step_key"])
    if _token_request_count(conn, run_id, prefix) + projected > token_ceiling:
        raise _GlobalStop(STOP_BUDGET, scope="CUMULATIVE_LIFECYCLE")


def _step_e2z_status(step: dict[str, Any], window_id: int) -> str | None:
    """Read the exact attached window's E2Z event from its close-step report."""
    try:
        result = json.loads(str(step.get("result_json") or "{}"))
    except json.JSONDecodeError:
        return None
    pipeline = result.get("memory_pipeline")
    if not isinstance(pipeline, dict):
        return None
    matches = [
        item for item in pipeline.get("e2z_window_results", [])
        if isinstance(item, dict) and item.get("window_id") == window_id
    ]
    statuses = {str(item.get("e2z_status")) for item in matches}
    if "E2Z_MEMORY_CREATED" in statuses:
        return "E2Z_MEMORY_CREATED"
    if "E2Z_ALREADY_EXISTS" in statuses:
        return "E2Z_ALREADY_EXISTS"
    return None


def _authoritative_promotions_for_run(
    conn: sqlite3.Connection, run_id: str,
) -> dict[int, dict[str, Any]]:
    """Load eligible E2Z episodes for this run's attached windows, read-only."""
    rows = conn.execute(
        """
        SELECT e.*, f.id AS fingerprint_id,
               f.fingerprint_payload_json AS fingerprint_payload_json
        FROM printer_episodes e
        JOIN printer_memory_fingerprints f
          ON f.episode_id=e.id
         AND f.fingerprint_kind='STATIC_CONDITION_SUMMARY'
         AND f.memory_status='CLEAN_MEMORY'
         AND f.data_quality_label='CLEAN_DATA'
         AND f.do_not_train=0
        JOIN printer_memory_factory_run_steps s
          ON s.memory_window_id=e.memory_window_id
        WHERE s.run_id=?
          AND e.episode_status='COMPLETE'
          AND e.memory_status='CLEAN_MEMORY'
          AND e.data_quality_label='CLEAN_DATA'
          AND e.do_not_train=0
          AND e.memory_quality_label='CLEAN_MEMORY'
          AND json_extract(f.fingerprint_payload_json,'$.episode_id')=e.id
          AND json_extract(f.fingerprint_payload_json,'$.window_id')=e.memory_window_id
          AND json_extract(f.fingerprint_payload_json,'$.token_id')=e.token_id
          AND json_extract(f.fingerprint_payload_json,'$.pair_id')=e.pair_id
          AND json_extract(f.fingerprint_payload_json,'$.window_kind')=e.window_kind
        ORDER BY e.id
        """,
        (run_id,),
    ).fetchall()
    promotions: dict[int, dict[str, Any]] = {}
    for row in rows:
        episode = dict(row)
        promotions.setdefault(int(episode["memory_window_id"]), episode)
    return promotions


def _per_token_outcomes(
    steps: list[dict[str, Any]], windows_by_id: dict[int, dict[str, Any]],
    promotions_by_window_id: dict[int, dict[str, Any]] | None = None,
) -> list[dict[str, Any]]:
    """Build authoritative per-token outcomes from this run's steps only."""
    _DIRTY = {"DIRTY_MEMORY", "AUDIT_ONLY_MEMORY", "DO_NOT_TRAIN"}
    promotions_by_window_id = promotions_by_window_id or {}
    tokens: dict[int, dict[str, Any]] = {}
    order: list[int] = []
    for s in steps:
        tid = int(s["token_id"])
        if tid not in tokens:
            order.append(tid)
            lane = str(s["tracking_lane"])
            tokens[tid] = {
                "token_id": tid, "token_mint": s["token_mint"],
                "pair_id": s["pair_id"], "pair_address": s["pair_address"],
                "tracking_lane": lane,
                "expected_snapshots": _cadence_expected_snapshots(lane),
                "actual_snapshots": 0, "failed_steps": 0, "cancelled_steps": 0,
                "four_hour_expected_snapshots": None,
                "four_hour_actual_snapshots": 0,
                "close_status": None, "close_step_kind": None,
                "memory_window_id": None,
                "memory_quality_label": None,
                "source_memory_window_status": None,
                "promotion_status": NO_PROMOTION,
                "authoritative_episode_id": None,
                "blockers": [],
                "reached_terminal_window": False, "terminal_status": "INCOMPLETE",
            }
        t = tokens[tid]
        if s.get("snapshot_id") is not None:
            t["actual_snapshots"] += 1
            if str(s["step_kind"]).startswith("LONG_CONTINUATION_"):
                t["four_hour_actual_snapshots"] += 1
        if s["step_status"] == "FAILED":
            t["failed_steps"] += 1
        if s["step_status"] == "CANCELLED":
            t["cancelled_steps"] += 1
        if s["step_kind"] in TERMINAL_CLOSE_STEP_KINDS:
            t["close_status"] = s["step_status"]
            t["close_step_kind"] = s["step_kind"]
            t["memory_window_id"] = s.get("memory_window_id")
            t["close_step_e2z_status"] = (
                _step_e2z_status(s, int(s["memory_window_id"]))
                if s.get("memory_window_id") is not None else None
            )
            if s["step_kind"] in {
                "LONG_CONTINUATION_CLOSE", "LONG_CONTINUATION_CLOSE_AUDIT"
            }:
                t["four_hour_expected_snapshots"] = int(
                    _cadence_get_policy("WINDOW_4H", t["tracking_lane"]).minimum_required_snapshots
                )
    for tid in order:
        t = tokens[tid]
        wid = t["memory_window_id"]
        window = windows_by_id.get(int(wid)) if wid is not None else None
        if window is not None:
            t["memory_quality_label"] = window.get("memory_quality_label")
            t["source_memory_window_status"] = window.get("memory_status")
            # V2-6.3: report the 1h continuation plan for the closed 15m window -
            # enqueue at the exact 15m close, deadline anchored to close + 2700s.
            if window.get("window_kind") == "WINDOW_15M":
                from printer_v1.snapshots.lifecycle_continuity import (
                    build_1h_continuation_plan,
                )
                fifteen = dict(window)
                fifteen["tracking_lane"] = t["tracking_lane"]
                t["continuation_plan"] = build_1h_continuation_plan(fifteen)
        if t["close_status"] == "SUCCEEDED":
            t["reached_terminal_window"] = True
            q = t["memory_quality_label"]
            promotion = promotions_by_window_id.get(int(wid)) if wid is not None else None
            promotion_matches_target = (
                promotion is not None
                and int(promotion["token_id"]) == int(t["token_id"])
                and int(promotion["pair_id"]) == int(t["pair_id"])
                and str(promotion.get("window_kind"))
                == str(window.get("window_kind") if window else None)
            )
            if promotion_matches_target:
                t["authoritative_episode_id"] = int(promotion["id"])
                t["promotion_status"] = (
                    ALREADY_EXISTS_IDEMPOTENT
                    if t.get("close_step_e2z_status") == "E2Z_ALREADY_EXISTS"
                    else CLEAN_PROMOTED
                )
                t["terminal_status"] = "CLEAN"
            elif q in _DIRTY:
                t["promotion_status"] = DIRTY_OR_BLOCKED
                t["terminal_status"] = "DIRTY"
            else:
                t["promotion_status"] = NO_PROMOTION
                t["terminal_status"] = "NO_PROMOTION"
        elif t["close_status"] == "FAILED":
            t["reached_terminal_window"] = False
            t["promotion_status"] = DIRTY_OR_BLOCKED
            t["terminal_status"] = "TERMINAL_BLOCKED"
        elif t["failed_steps"]:
            t["terminal_status"] = "TOKEN_LOCAL_FAILED"
        elif t["cancelled_steps"]:
            t["terminal_status"] = "CANCELLED"
    return [tokens[tid] for tid in order]


def _memory_yield_report(
    per_token: list[dict[str, Any]], windows: list[dict[str, Any]],
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Reconcile run-local yield while preserving source-window candidates."""
    promoted = sum(t["promotion_status"] == CLEAN_PROMOTED for t in per_token)
    existing = sum(
        t["promotion_status"] == ALREADY_EXISTS_IDEMPOTENT for t in per_token
    )
    dirty_or_blocked = sum(
        t["promotion_status"] == DIRTY_OR_BLOCKED for t in per_token
    )
    no_promotion = sum(t["promotion_status"] == NO_PROMOTION for t in per_token)
    source_clean = sum(
        row.get("memory_quality_label") == "CLEAN_MEMORY" for row in windows
    )
    source_dirty = sum(
        row.get("memory_quality_label")
        in {"DIRTY_MEMORY", "AUDIT_ONLY_MEMORY", "DO_NOT_TRAIN"}
        for row in windows
    )
    source_partial = len(windows) - source_clean - source_dirty
    run_local = {
        "clean": promoted + existing,
        "clean_promoted": promoted,
        "already_exists_idempotent": existing,
        "dirty": sum(t["terminal_status"] == "DIRTY" for t in per_token),
        "blocked": sum(
            t["terminal_status"] == "TERMINAL_BLOCKED" for t in per_token
        ),
        "dirty_or_blocked": dirty_or_blocked,
        "no_promotion": no_promotion,
        "token_local_failed": sum(
            t["terminal_status"] == "TOKEN_LOCAL_FAILED" for t in per_token
        ),
        "authoritative_source": (
            "eligible_printer_episodes_joined_to_run_step_attached_memory_window_ids"
        ),
        "zero_clean_is_valid": True,
    }
    memory_results = {
        "clean": promoted + existing,
        "clean_promoted": promoted,
        "already_exists_idempotent": existing,
        "dirty_or_blocked": dirty_or_blocked,
        "no_promotion": no_promotion,
        "dirty_or_audit_only": source_dirty,
        "blocked_or_partial": source_partial,
        "source_window_candidates": {
            "clean": source_clean,
            "dirty_or_audit_only": source_dirty,
            "blocked_or_partial": source_partial,
        },
        "zero_clean_is_valid": True,
    }
    return run_local, memory_results

def _run_budgets(
    conn: sqlite3.Connection, run_id: str, discovery: dict[str, Any], steps: list[dict[str, Any]],
) -> dict[str, Any]:
    config = _load_run_config(conn, run_id)
    continuous = bool(config.get("continuous_first_hour"))
    handoffs = sum(
        1 for item in discovery.get("discovery_results", [])
        if item.get("scheduler_job_id") is not None
    )
    discovery_requests = int(
        discovery.get("source_budget_report", {}).get(
            "source_requests_attempted", discovery.get("source_request_delta", 0)
        ) or 0
    )
    runtime_requests = _run_request_count(conn, run_id)
    holder_fallbacks = int(conn.execute(
        "SELECT COUNT(*) FROM printer_source_requests "
        "WHERE source_name='solana_rpc' AND request_key LIKE ?",
        (f"{run_id}:%",),
    ).fetchone()[0])
    all_step_jobs = int(conn.execute(
        "SELECT COUNT(DISTINCT scheduler_job_id) "
        "FROM printer_memory_factory_run_steps "
        "WHERE run_id=? AND scheduler_job_id IS NOT NULL",
        (run_id,),
    ).fetchone()[0])
    cumulative_scheduler_rows = all_step_jobs + handoffs

    if config.get("continuous_four_hour"):
        from printer_v1.operator_cli.one_token_4h_runtime import (
            cumulative_lifecycle_budget,
            runtime_budget,
        )
        long_lane_row = conn.execute(
            "SELECT tracking_lane FROM printer_memory_factory_run_steps "
            "WHERE run_id=? AND step_kind LIKE 'LONG_CONTINUATION_%' LIMIT 1",
            (run_id,),
        ).fetchone()
        phase_started = long_lane_row is not None
        lane_row = long_lane_row or conn.execute(
            "SELECT tracking_lane FROM printer_memory_factory_run_steps "
            "WHERE run_id=? AND tracking_lane IS NOT NULL ORDER BY id LIMIT 1",
            (run_id,),
        ).fetchone()
        lane = str(lane_row[0]) if lane_row is not None else None
        if lane is None:
            return {
                "automatic_retries": 0,
                "continuous_first_hour": continuous,
                "four_hour_phase_usage": {
                    "state": "NOT_STARTED",
                    "available": True,
                    "tracking_lane": None,
                    "source_requests": 0,
                    "source_request_ceiling": None,
                    "source_requests_within_ceiling": None,
                    "scheduler_rows": 0,
                    "scheduler_row_ceiling": None,
                    "scheduler_rows_within_ceiling": None,
                    "budget_verdict": None,
                    "within_ceiling": None,
                },
                "cumulative_lifecycle_usage": {
                    "state": "UNAVAILABLE",
                    "available": False,
                    "tracking_lane": None,
                    "budget_verdict": None,
                    "within_ceiling": None,
                },
            }

        standard_campaign = bool(
            config.get("standard_four_hour_campaign")
        )
        reporting_unavailable_reason: str | None = None
        reporting_lane = lane

        if standard_campaign:
            standard_report = _standard_four_hour_reporting_budget_for_run(
                conn, run_id
            )
            if standard_report["available"]:
                standard_budget = standard_report.get("budget")
                if not isinstance(standard_budget, Mapping):
                    raise ValueError(
                        "standard four-hour reporting budget payload is invalid"
                    )
                cumulative = dict(standard_budget)
                phase = {
                    "phase_request_ceiling": int(
                        cumulative["phase_request_ceiling"]
                    ),
                    "phase_scheduler_ceiling": int(
                        cumulative["phase_scheduler_ceiling"]
                    ),
                    "holder_fallback_max": int(
                        cumulative["phase_holder_fallback_ceiling"]
                    ),
                }
                reporting_lane = "STANDARD_FOUR_HOUR_SUBSET"
            else:
                reporting_unavailable_reason = str(
                    standard_report.get("reason")
                    or "standard four-hour subset budget unavailable"
                )
                cumulative = None
                phase = None
                reporting_lane = "STANDARD_FOUR_HOUR_SUBSET"
        else:
            phase = runtime_budget(lane)
            cumulative = _cumulative_lifecycle_budget_for_run(
                conn, run_id, lane
            )
        phase_requests = int(conn.execute(
            "SELECT COUNT(*) FROM printer_source_requests WHERE request_key LIKE ?",
            (f"{run_id}:%4h%",),
        ).fetchone()[0]) if phase_started else 0
        phase_jobs = int(conn.execute(
            "SELECT COUNT(*) FROM printer_memory_factory_run_steps "
            "WHERE run_id=? AND step_kind LIKE 'LONG_CONTINUATION_%'",
            (run_id,),
        ).fetchone()[0]) if phase_started else 0
        phase_holder_fallbacks = int(conn.execute(
            "SELECT COUNT(*) FROM printer_source_requests "
            "WHERE source_name='solana_rpc' AND request_key LIKE ?",
            (f"{run_id}:%4h%",),
        ).fetchone()[0]) if phase_started else 0
        cumulative_requests = discovery_requests + runtime_requests

        if reporting_unavailable_reason is not None:
            prefixes = sorted(
                {_token_prefix(s["step_key"]) for s in steps}
            )
            per_token_requests = {
                prefix: _token_request_count(conn, run_id, prefix)
                for prefix in prefixes
            }
            return {
                "four_hour_phase_usage": {
                    "state": (
                        "STARTED" if phase_started else "NOT_STARTED"
                    ),
                    "available": False,
                    "reason": reporting_unavailable_reason,
                    "tracking_lane": reporting_lane,
                    "source_requests": phase_requests,
                    "source_request_ceiling": None,
                    "source_requests_within_ceiling": None,
                    "scheduler_rows": phase_jobs,
                    "scheduler_row_ceiling": None,
                    "scheduler_rows_within_ceiling": None,
                    "holder_fallbacks": phase_holder_fallbacks,
                    "holder_fallback_ceiling": None,
                    "automatic_retries": 0,
                    "endpoint_rotation": False,
                    "budget_verdict": None,
                    "within_ceiling": None,
                },
                "cumulative_lifecycle_usage": {
                    "state": "UNAVAILABLE",
                    "available": False,
                    "reason": reporting_unavailable_reason,
                    "tracking_lane": reporting_lane,
                    "source_requests": cumulative_requests,
                    "source_request_ceiling": None,
                    "source_requests_within_ceiling": None,
                    "scheduler_rows": cumulative_scheduler_rows,
                    "scheduler_row_ceiling": None,
                    "scheduler_rows_within_ceiling": None,
                    "discovery_source_requests": discovery_requests,
                    "runtime_source_requests": runtime_requests,
                    "budget_verdict": None,
                    "within_ceiling": None,
                },
                "governed_requests_run": cumulative_requests,
                "governed_requests_run_ceiling": None,
                "governed_requests_run_within_ceiling": None,
                "governed_requests_per_token": per_token_requests,
                "governed_requests_per_token_ceiling": None,
                "governed_requests_per_token_within_ceiling": None,
                "holder_rpc_fallbacks": phase_holder_fallbacks,
                "holder_rpc_fallbacks_ceiling": None,
                "scheduler_run_step_jobs": all_step_jobs,
                "scheduler_cancelled_discovery_handoffs": handoffs,
                "scheduler_rows_total": cumulative_scheduler_rows,
                "scheduler_rows_ceiling": None,
                "scheduler_rows_within_ceiling": None,
                "discovery_requests_ceiling": None,
                "automatic_retries": 0,
                "continuous_first_hour": continuous,
            }

        if not isinstance(phase, Mapping) or not isinstance(
            cumulative, Mapping
        ):
            raise ValueError(
                "four-hour reporting budget unexpectedly unavailable"
            )

        if phase_started:
            phase_requests_ok = phase_requests <= int(phase["phase_request_ceiling"])
            phase_jobs_ok = phase_jobs <= int(phase["phase_scheduler_ceiling"])
            phase_holder_ok = phase_holder_fallbacks <= int(phase["holder_fallback_max"])
            phase_within = phase_requests_ok and phase_jobs_ok and phase_holder_ok
            phase_verdict: str | None = "WITHIN_CEILING" if phase_within else "EXCEEDED"
        else:
            phase_requests_ok = None
            phase_jobs_ok = None
            phase_within = None
            phase_verdict = None
        phase_usage = {
            "state": "STARTED" if phase_started else "NOT_STARTED",
            "available": True,
            "tracking_lane": reporting_lane,
            "source_requests": phase_requests,
            "source_request_ceiling": int(phase["phase_request_ceiling"]),
            "source_requests_within_ceiling": phase_requests_ok,
            "scheduler_rows": phase_jobs,
            "scheduler_row_ceiling": int(phase["phase_scheduler_ceiling"]),
            "scheduler_rows_within_ceiling": phase_jobs_ok,
            "holder_fallbacks": phase_holder_fallbacks,
            "holder_fallback_ceiling": int(phase["holder_fallback_max"]),
            "automatic_retries": 0,
            "endpoint_rotation": False,
            "budget_verdict": phase_verdict,
            "within_ceiling": phase_within,
        }

        cumulative_requests_ok = cumulative_requests <= int(cumulative["request_ceiling"])
        cumulative_jobs_ok = cumulative_scheduler_rows <= int(cumulative["scheduler_ceiling"])
        cumulative_within = cumulative_requests_ok and cumulative_jobs_ok
        cumulative_usage = {
            "state": "REPORTED",
            "available": True,
            "tracking_lane": reporting_lane,
            "source_requests": cumulative_requests,
            "source_request_ceiling": int(cumulative["request_ceiling"]),
            "source_requests_within_ceiling": cumulative_requests_ok,
            "scheduler_rows": cumulative_scheduler_rows,
            "scheduler_row_ceiling": int(cumulative["scheduler_ceiling"]),
            "scheduler_rows_within_ceiling": cumulative_jobs_ok,
            "discovery_source_requests": discovery_requests,
            "runtime_source_requests": runtime_requests,
            "request_components": cumulative["request_components"],
            "scheduler_components": cumulative["scheduler_components"],
            "policy_derived": True,
            "budget_verdict": "WITHIN_CEILING" if cumulative_within else "EXCEEDED",
            "within_ceiling": cumulative_within,
        }
        compressed_two_token = _two_token_lifecycle(config)
        if standard_campaign:
            prefixes = sorted(
                {_token_prefix(s["step_key"]) for s in steps}
            )
            per_token_requests = {
                prefix: _token_request_count(conn, run_id, prefix)
                for prefix in prefixes
            }
            # Standard mode has an aggregate subset ceiling. Preserve
            # exact token-local usage without inventing a scalar
            # per-token ceiling from the aggregate projection.
            token_ceiling = None
            per_token_within = None
        elif compressed_two_token:
            prefixes = sorted({_token_prefix(s["step_key"]) for s in steps})
            per_token_requests = {
                prefix: _token_request_count(conn, run_id, prefix)
                for prefix in prefixes
            }
            token_ceiling = int(cumulative["request_ceiling"]) - int(
                cumulative["request_components"]["discovery"]
            )
            per_token_within = all(
                used <= token_ceiling for used in per_token_requests.values()
            )
        else:
            token_ceiling = int(cumulative["request_ceiling"]) - int(
                cumulative["request_components"]["discovery"]
            )
            per_token_requests = {"selected_token": runtime_requests}
            per_token_within = runtime_requests <= token_ceiling
        return {
            "four_hour_phase_usage": phase_usage,
            "cumulative_lifecycle_usage": cumulative_usage,
            # Compatibility fields use the applicable cumulative policy.
            "governed_requests_run": cumulative_requests,
            "governed_requests_run_ceiling": int(cumulative["request_ceiling"]),
            "governed_requests_run_within_ceiling": cumulative_requests_ok,
            "governed_requests_per_token": per_token_requests,
            "governed_requests_per_token_ceiling": token_ceiling,
            "governed_requests_per_token_within_ceiling": per_token_within,
            "holder_rpc_fallbacks": (
                phase_holder_fallbacks
                if standard_campaign
                else holder_fallbacks
            ),
            "holder_rpc_fallbacks_ceiling": int(
                phase["holder_fallback_max"]
            ),
            "scheduler_run_step_jobs": all_step_jobs,
            "scheduler_cancelled_discovery_handoffs": handoffs,
            "scheduler_rows_total": cumulative_scheduler_rows,
            "scheduler_rows_ceiling": int(cumulative["scheduler_ceiling"]),
            "scheduler_rows_within_ceiling": cumulative_jobs_ok,
            "discovery_requests_ceiling": int(cumulative["request_components"]["discovery"]),
            "automatic_retries": 0,
            "continuous_first_hour": continuous,
        }

    prefixes = sorted({_token_prefix(s["step_key"]) for s in steps})
    per_token = {p: _token_request_count(conn, run_id, p) for p in prefixes}
    selective_1h = _selective_1h_lifecycle(config)
    compressed_two_token = _two_token_lifecycle(config)
    run_ceiling = (
        _SELECTIVE_1H_MAX_REQUESTS_RUN
        if selective_1h
        else _COMPRESSED_TWO_TOKEN_MAX_REQUESTS_RUN
        if compressed_two_token
        else _CONTINUOUS_MAX_REQUESTS_RUN
        if continuous
        else _MAX_GOVERNED_REQUESTS_RUN
    )
    token_ceiling = (
        _CONTINUOUS_MAX_REQUESTS_PER_TOKEN
        if continuous else _MAX_GOVERNED_REQUESTS_PER_TOKEN
    )
    scheduler_ceiling = (
        _SELECTIVE_1H_MAX_SCHEDULER_ROWS
        if selective_1h
        else _COMPRESSED_TWO_TOKEN_MAX_SCHEDULER_ROWS
        if compressed_two_token
        else _CONTINUOUS_MAX_SCHEDULER_ROWS
        if continuous
        else _MAX_SCHEDULER_ROWS
    )
    return {
        "governed_requests_run": runtime_requests,
        "governed_requests_run_ceiling": run_ceiling,
        "governed_requests_run_within_ceiling": runtime_requests <= run_ceiling,
        "governed_requests_per_token": per_token,
        "governed_requests_per_token_ceiling": token_ceiling,
        "governed_requests_per_token_within_ceiling": all(
            value <= token_ceiling for value in per_token.values()
        ),
        "holder_rpc_fallbacks": holder_fallbacks,
        "holder_rpc_fallbacks_ceiling": (
            _MAX_HOLDER_RPC_REQUESTS_PER_TOKEN * max(1, len(prefixes))
        ),
        "scheduler_run_step_jobs": _run_step_job_count(conn, run_id),
        "scheduler_cancelled_discovery_handoffs": handoffs,
        "scheduler_rows_total": _run_step_job_count(conn, run_id) + handoffs,
        "scheduler_rows_ceiling": scheduler_ceiling,
        "scheduler_rows_within_ceiling": (
            _run_step_job_count(conn, run_id) + handoffs
        ) <= scheduler_ceiling,
        "discovery_requests_ceiling": _MAX_DISCOVERY_REQUESTS,
        "automatic_retries": 0,
        "continuous_first_hour": continuous,
    }

def _continuous_lifecycle_report(
    conn: sqlite3.Connection,
    run_id: str,
    steps: list[dict[str, Any]],
) -> dict[str, Any]:
    from printer_v1.snapshots.lifecycle_continuity import resolve_lifecycle_continuity

    config = _load_run_config(conn, run_id)
    if not config.get("continuous_first_hour"):
        return {"enabled": False}
    targets = {
        (int(step["token_id"]), int(step["pair_id"]), str(step["tracking_lane"]))
        for step in steps if step.get("token_id") is not None and step.get("pair_id") is not None
    }
    reports: list[dict[str, Any]] = []
    for token_id, pair_id, lane in sorted(targets):
        token_steps = [
            step for step in steps
            if int(step.get("token_id") or -1) == token_id
            and int(step.get("pair_id") or -1) == pair_id
        ]
        phases: dict[str, list[dict[str, Any]]] = {
            "window_15m": [], "continuation_1h": [], "continuation_4h": [],
        }
        for step in token_steps:
            if step.get("snapshot_id") is None:
                continue
            row = conn.execute(
                "SELECT id,captured_at FROM printer_token_snapshots WHERE id=?",
                (int(step["snapshot_id"]),),
            ).fetchone()
            if row is None:
                continue
            item = {"snapshot_id": int(row["id"]), "captured_at": str(row["captured_at"])}
            kind = str(step["step_kind"])
            phase = (
                "continuation_4h" if kind.startswith("LONG_CONTINUATION")
                else "continuation_1h" if kind.startswith("CONTINUATION")
                else "window_15m"
            )
            phases[phase].append(item)
        for items in phases.values():
            items.sort(key=lambda item: item["captured_at"])

        def gaps(items: list[dict[str, Any]]) -> list[float]:
            return [
                round((datetime.fromisoformat(items[index]["captured_at"]) -
                       datetime.fromisoformat(items[index - 1]["captured_at"])).total_seconds(), 6)
                for index in range(1, len(items))
            ]

        continuity = resolve_lifecycle_continuity(
            conn,
            run_id=run_id,
            token_id=token_id,
            pair_id=pair_id,
            tracking_lane=lane,
        )
        fifteen = next(
            (
                s for s in token_steps
                if s["step_kind"] in {"WINDOW_CLOSE", "WINDOW_CLOSE_AUDIT"}
            ),
            None,
        )
        continuation = next(
            (
                s for s in token_steps
                if s["step_kind"]
                in {"CONTINUATION_CLOSE", "CONTINUATION_CLOSE_AUDIT"}
            ),
            None,
        )
        four_hour = next(
            (
                s for s in token_steps
                if s["step_kind"]
                in {"LONG_CONTINUATION_CLOSE", "LONG_CONTINUATION_CLOSE_AUDIT"}
            ),
            None,
        )
        transition_gap = None
        if phases["window_15m"] and phases["continuation_1h"]:
            transition_gap = round((
                datetime.fromisoformat(phases["continuation_1h"][0]["captured_at"])
                - datetime.fromisoformat(phases["window_15m"][-1]["captured_at"])
            ).total_seconds(), 6)
        reports.append({
            "token_id": token_id,
            "pair_id": pair_id,
            "tracking_lane": lane,
            "window_15m": {
                "snapshots": phases["window_15m"],
                "snapshot_gaps_seconds": gaps(phases["window_15m"]),
                "memory_window_id": fifteen.get("memory_window_id") if fifteen else None,
            },
            "continuation_1h": {
                "snapshots": phases["continuation_1h"],
                "snapshot_gaps_seconds": gaps(phases["continuation_1h"]),
                "memory_window_id": continuation.get("memory_window_id") if continuation else None,
                "step_status": continuation.get("step_status") if continuation else None,
            },
            "transition_15m_to_1h_gap_seconds": transition_gap,
            "continuation_4h": {
                "snapshots": phases["continuation_4h"],
                "snapshot_gaps_seconds": gaps(phases["continuation_4h"]),
                "memory_window_id": four_hour.get("memory_window_id") if four_hour else None,
                "step_status": four_hour.get("step_status") if four_hour else None,
            },
            "transition_1h_to_4h_gap_seconds": (
                round((datetime.fromisoformat(phases["continuation_4h"][0]["captured_at"])
                       - datetime.fromisoformat(phases["continuation_1h"][-1]["captured_at"])).total_seconds(), 6)
                if phases["continuation_1h"] and phases["continuation_4h"] else None
            ),
            "continuity": continuity,
        })
    return {"enabled": True, "tokens": reports}


def _runtime_stage_for_step(step_kind: str) -> str:
    if step_kind.startswith("LONG_CONTINUATION_"):
        return "FOUR_HOUR"
    if step_kind.startswith("CONTINUATION_"):
        return "PRE_4H_1H"
    return "PRE_4H_15M"


def _primary_terminal_cause(
    conn: sqlite3.Connection, steps: list[dict[str, Any]], loop_stop_reason: str,
) -> dict[str, Any]:
    """Resolve the first genuine runtime cause; later reporting cannot replace it."""
    for step in steps:
        if step.get("step_status") != "FAILED":
            continue
        stage = _runtime_stage_for_step(str(step.get("step_kind") or ""))
        if step.get("source_failure_id") is not None:
            failure = conn.execute(
                "SELECT failure_type,failure_message,source_name,request_kind,failed_at "
                "FROM printer_source_failures WHERE id=?",
                (int(step["source_failure_id"]),),
            ).fetchone()
            failure_type = (
                str(failure["failure_type"]) if failure is not None
                else str(step.get("error_or_skip_reason") or "source_failure")
            )
            failure_message = (
                str(failure["failure_message"] or "") if failure is not None else ""
            )
            return {
                "present": True,
                "category": "SOURCE_FAILURE",
                "run_status": "FAILED",
                "stop_reason": STOP_SOURCE,
                "stage": stage,
                "pre_four_hour": stage in {"PRE_4H_15M", "PRE_4H_1H"},
                "step_id": int(step["id"]),
                "step_key": str(step.get("step_key") or ""),
                "step_kind": str(step.get("step_kind") or ""),
                "source_failure_id": int(step["source_failure_id"]),
                "failure_type": failure_type,
                "failure_message": failure_message,
                "source_name": str(failure["source_name"]) if failure is not None else None,
                "request_kind": str(failure["request_kind"]) if failure is not None else None,
                "failed_at": str(failure["failed_at"]) if failure is not None else None,
            }
        try:
            result = json.loads(str(step.get("result_json") or "{}"))
        except json.JSONDecodeError:
            result = {}
        if (
            step.get("error_or_skip_reason") == STOP_BUDGET
            or result.get("global_stop") == STOP_BUDGET
        ):
            return {
                "present": True,
                "category": "BUDGET",
                "run_status": "SAFE_STOPPED",
                "stop_reason": STOP_BUDGET,
                "stage": stage,
                "pre_four_hour": stage in {"PRE_4H_15M", "PRE_4H_1H"},
                "step_id": int(step["id"]),
                "step_key": str(step.get("step_key") or ""),
                "step_kind": str(step.get("step_kind") or ""),
                "budget_scope": result.get("budget_scope"),
                "budget_detail": result.get("budget_detail"),
            }
    if loop_stop_reason != STOP_COMPLETED:
        return {
            "present": True,
            "category": "RUN_STOP",
            "run_status": "SAFE_STOPPED",
            "stop_reason": loop_stop_reason,
            "stage": None,
            "pre_four_hour": None,
        }
    return {"present": False}


def _four_hour_terminal_validation(
    *, config: dict[str, Any], steps: list[dict[str, Any]],
    windows_by_id: dict[int, dict[str, Any]], budgets: dict[str, Any],
    pending_steps: int, running_jobs: int,
    primary_cause: dict[str, Any] | None = None,
    complete_clean_objects_by_window_id: Mapping[int, Mapping[str, Any]] | None = None,
) -> dict[str, Any]:
    """Prove either a terminal 4h outcome or an exact natural two-stop end."""
    if not config.get("continuous_four_hour"):
        return {
            "enabled": False,
            "complete": True,
            "reasons": [],
            "failure_reasons": [],
            "primary_cause": primary_cause or {"present": False},
        }
    phase = budgets.get("four_hour_phase_usage", {})
    cumulative = budgets.get("cumulative_lifecycle_usage", {})
    long_steps = [
        step for step in steps
        if str(step.get("step_kind", "")).startswith("LONG_CONTINUATION_")
    ]
    phase_state = str(
        phase.get("state") or ("STARTED" if long_steps else "UNAVAILABLE")
    )
    operational_natural = bool(config.get("operational_natural_disposition")) \
        and _compressed_two_token_plan(config) is None
    close_steps = [
        step for step in long_steps
        if step.get("step_kind")
        in {"LONG_CONTINUATION_CLOSE", "LONG_CONTINUATION_CLOSE_AUDIT"}
    ]
    lane = str(
        long_steps[0].get("tracking_lane")
        if long_steps else phase.get("tracking_lane") or ""
    )
    policy = _cadence_get_policy("WINDOW_4H", lane) if lane else None
    expected = int(policy.minimum_required_snapshots) if policy is not None else 0
    actual = sum(1 for step in long_steps if step.get("snapshot_id") is not None)
    reasons: list[str] = []
    failure_reasons = [
        str(step.get("error_or_skip_reason"))
        for step in long_steps
        if step.get("step_status") == "FAILED"
        and step.get("error_or_skip_reason")
    ]
    source_failure_reasons = [
        str(step.get("error_or_skip_reason"))
        for step in long_steps
        if step.get("step_status") == "FAILED"
        and step.get("error_or_skip_reason")
        and (
            step.get("source_failure_id") is not None
            or "transport" in str(step.get("error_or_skip_reason")).lower()
        )
    ]
    # V2-9.7E.47 A4: lifecycle completion and clean-memory success are separate
    # verdicts. A lawful no-continuation close is a COMPLETED governed
    # lifecycle; a dirty or audit-only memory result blocks only the pilot
    # ACCEPTANCE verdict below. Before this repair a dirty 15m close produced
    # `ineligible_or_dirty_terminal_15m_close` and therefore
    # SAFE_STOP_4H_TERMINAL_INCOMPLETE, which is reserved for a continuation or
    # required terminal phase that actually started or was required and did not
    # complete (V2-9.7E.46 §10 / §15 item 1).
    memory_acceptance: dict[str, Any] = {
        "evaluated": False,
        "clean_windows": 0,
        "dirty_or_audit_only_windows": 0,
        "verdict": "NOT_EVALUATED",
        "blocking_windows": [],
    }
    if policy is None and phase_state == "STARTED":
        reasons.append("missing_4h_cadence_policy")
    if phase_state == "NOT_STARTED":
        if operational_natural:
            closes_15m = [
                step for step in steps
                if step.get("step_kind")
                in {"WINDOW_CLOSE", "WINDOW_CLOSE_AUDIT"}
            ]
            if len(closes_15m) != 2 or any(
                step.get("step_status") != "SUCCEEDED" for step in closes_15m
            ):
                reasons.append("two_terminal_15m_closes_required")
            if len({step.get("token_id") for step in closes_15m}) != 2:
                reasons.append("two_distinct_terminal_tokens_required")
            memory_acceptance["evaluated"] = True
            for step in closes_15m:
                window_id = step.get("memory_window_id")
                window = (
                    windows_by_id.get(int(window_id))
                    if window_id is not None else None
                )
                # Lifecycle requirement: the window exists, is the approved main
                # 15m kind, and terminally completed. Evidence quality is NOT a
                # lifecycle-completion requirement.
                if (
                    window is None
                    or window.get("window_kind") != "WINDOW_15M"
                    or str(window.get("window_status") or "")
                    not in _TERMINAL_WINDOW_STATUSES
                ):
                    reasons.append("incomplete_terminal_15m_close")
                    continue
                clean = (
                    window.get("memory_status") == "CLEAN_MEMORY"
                    and window.get("memory_quality_label") == "CLEAN_MEMORY"
                    and window.get("data_quality_label") == "CLEAN_DATA"
                    and int(window.get("do_not_train") or 0) == 0
                )
                if clean:
                    if complete_clean_objects_by_window_id is None:
                        # Compatibility for isolated historical validator tests.
                        memory_acceptance["clean_windows"] += 1
                    elif int(window["id"]) in complete_clean_objects_by_window_id:
                        memory_acceptance["clean_windows"] += 1
                    else:
                        reasons.append(
                            f"incomplete_clean_object:{int(window['id'])}"
                        )
                        memory_acceptance["blocking_windows"].append(
                            {
                                "window_id": int(window["id"]),
                                "reason": "INCOMPLETE_CLEAN_OBJECT",
                            }
                        )
                else:
                    memory_acceptance["dirty_or_audit_only_windows"] += 1
                    memory_acceptance["blocking_windows"].append(
                        {
                            "window_id": (
                                int(window["id"])
                                if window.get("id") is not None
                                else step.get("memory_window_id")
                            ),
                            "memory_quality_label": window.get(
                                "memory_quality_label"
                            ),
                            "data_quality_label": window.get(
                                "data_quality_label"
                            ),
                            "do_not_train": int(window.get("do_not_train") or 0),
                        }
                    )
                try:
                    result = json.loads(str(step.get("result_json") or "{}"))
                except json.JSONDecodeError:
                    result = {}
                plan = result.get("continuation_plan")
                if (
                    not isinstance(plan, dict)
                    or plan.get("verdict") != "STOP_AFTER_15M"
                    or int(plan.get("planned_jobs") or 0) != 0
                ):
                    reasons.append("invalid_natural_stop_disposition")
            if any(
                step.get("step_kind")
                in {
                    "CONTINUATION_CLOSE",
                    "CONTINUATION_CLOSE_EVIDENCE",
                    "CONTINUATION_CLOSE_CONTEXT",
                    "CONTINUATION_CLOSE_AUDIT",
                    "LONG_CONTINUATION_CLOSE",
                    "LONG_CONTINUATION_CLOSE_EVIDENCE",
                    "LONG_CONTINUATION_CLOSE_CONTEXT",
                    "LONG_CONTINUATION_CLOSE_AUDIT",
                }
                for step in steps
            ):
                reasons.append("unexpected_continuation_in_natural_stop")
            memory_acceptance["verdict"] = (
                "CLEAN_MEMORY_ACHIEVED"
                if memory_acceptance["clean_windows"] == 2
                else "MEMORY_EVIDENCE_BLOCKED"
            )
        else:
            reasons.append("four_hour_phase_not_started")
    elif phase_state == "STARTED" and actual != expected:
        reasons.append(f"incomplete_4h_collection:{actual}/{expected}")

    close = None
    successor = None
    audit_path_complete = False
    if phase_state == "STARTED":
        if len(close_steps) != 1:
            reasons.append("missing_or_ambiguous_forced_close")
        else:
            close = close_steps[0]
            if close.get("step_status") != "SUCCEEDED":
                reasons.append(f"forced_close_not_succeeded:{close.get('step_status')}")
            window_id = close.get("memory_window_id")
            successor = (
                windows_by_id.get(int(window_id)) if window_id is not None else None
            )
            if successor is None or successor.get("window_kind") != "WINDOW_4H":
                reasons.append("missing_window_4h_successor")
            try:
                result = json.loads(str(close.get("result_json") or "{}"))
            except json.JSONDecodeError:
                result = {}
            audit_path_complete = (
                isinstance(result.get("window_audit"), dict)
                and isinstance(result.get("lane_q"), dict)
                and isinstance(result.get("memory_pipeline"), dict)
                and result["memory_pipeline"].get("lane_k_status") is not None
            )
            if not audit_path_complete:
                reasons.append("incomplete_4h_audit_report_path")

    phase_budget_verdict = phase.get("budget_verdict")
    cumulative_budget_verdict = cumulative.get("budget_verdict")
    # Compatibility for pre-V2-9.3 fixtures applies only to a started phase.
    if phase_state == "STARTED" and phase_budget_verdict is None:
        if phase.get("within_ceiling") is False:
            phase_budget_verdict = "EXCEEDED"
        elif phase.get("within_ceiling") is True:
            phase_budget_verdict = "WITHIN_CEILING"
    if phase_state == "STARTED" and cumulative_budget_verdict is None:
        if cumulative.get("within_ceiling") is False:
            cumulative_budget_verdict = "EXCEEDED"
        elif cumulative.get("within_ceiling") is True:
            cumulative_budget_verdict = "WITHIN_CEILING"

    budget_failure_scopes: list[str] = []
    if phase_state == "STARTED" and phase_budget_verdict == "EXCEEDED":
        reasons.append("four_hour_phase_budget_exceeded")
        budget_failure_scopes.append("FOUR_HOUR_PHASE")
    if cumulative_budget_verdict == "EXCEEDED":
        reasons.append("cumulative_lifecycle_budget_exceeded")
        budget_failure_scopes.append("CUMULATIVE_LIFECYCLE")
    if pending_steps:
        reasons.append(f"pending_or_running_steps:{pending_steps}")
    if running_jobs:
        reasons.append(f"running_jobs:{running_jobs}")
    if failure_reasons:
        reasons.append("terminal_4h_step_failure")

    complete = (
        phase_state == "STARTED"
        or (operational_natural and phase_state == "NOT_STARTED")
    ) and not reasons
    authoritative = primary_cause or {"present": False}
    if authoritative.get("present"):
        run_status = str(authoritative["run_status"])
        stop_reason = str(authoritative["stop_reason"])
    elif complete:
        run_status = "COMPLETED"
        stop_reason = STOP_COMPLETED
    elif source_failure_reasons:
        run_status = "FAILED"
        stop_reason = STOP_SOURCE
    elif budget_failure_scopes:
        run_status = "SAFE_STOPPED"
        stop_reason = STOP_BUDGET
    else:
        run_status = "SAFE_STOPPED"
        stop_reason = STOP_TERMINAL_4H
    return {
        "enabled": True,
        "complete": complete,
        "run_status": run_status,
        "stop_reason": stop_reason,
        "primary_cause": authoritative,
        "reasons": reasons,
        "failure_reasons": failure_reasons,
        "source_failure_reasons": source_failure_reasons,
        "budget_failure_scopes": budget_failure_scopes,
        "phase_state": phase_state,
        "operational_natural_stop": (
            operational_natural and phase_state == "NOT_STARTED"
        ),
        "tracking_lane": lane or None,
        "expected_snapshots": expected,
        "actual_snapshots": actual,
        "forced_close_present": len(close_steps) == 1,
        "forced_close_status": close.get("step_status") if close else None,
        "successor_window_id": (
            int(successor["id"]) if successor is not None else None
        ),
        "audit_path_complete": audit_path_complete,
        "cleanup_complete": pending_steps == 0 and running_jobs == 0,
        # V2-9.7E.47 A4: the pilot ACCEPTANCE verdict, reported separately from
        # the lifecycle terminal. Dirty or audit-only memory blocks acceptance
        # without falsely producing SAFE_STOP_4H_TERMINAL_INCOMPLETE.
        "memory_acceptance": memory_acceptance,
        "lifecycle_completion_independent_of_memory_quality": True,
    }


def _standard_campaign_four_hour_terminal_validation(
    conn: sqlite3.Connection,
    *,
    factory_run_id: str,
    campaign_id: str | None,
    run_id: str | None,
    cycle_id: str | None,
) -> dict[str, Any]:
    """Validate standard 4h terminal truth against the durable eligible subset."""
    if not all((campaign_id, run_id, cycle_id, factory_run_id)):
        return {"enabled": False, "complete": True, "reasons": [], "per_token": []}

    from printer_v1.operator_cli.standard_4h_progression import (
        derive_standard_4h_progression_status,
    )

    try:
        progression = derive_standard_4h_progression_status(
            conn,
            factory_run_id=str(factory_run_id),
            campaign_id=str(campaign_id),
            campaign_run_id=str(run_id),
            cycle_id=str(cycle_id),
        )
    except Exception as exc:
        return {
            "enabled": True,
            "complete": False,
            "reasons": [f"standard_four_hour_progression_invalid:{exc}"],
            "per_token": [],
            "expected_continuation_count": 0,
            "window_count": 0,
            "active_owned_four_hour_work": 0,
            "nonterminal_owned_four_hour_windows": 0,
        }
    if progression.get("enabled") is not True:
        return progression
    if progression.get("aggregate_state") != "HANDOFF_COMMITTED":
        return {
            **progression,
            "expected_continuation_count": sum(
                1
                for item in progression.get("per_token", [])
                if item.get("outcome")
                in {"ELIGIBLE_NOT_CREATED", "CREATED_PENDING", "RUNNING", "SUCCEEDED"}
            ),
            "window_count": 0,
            "active_owned_four_hour_work": 0,
            "nonterminal_owned_four_hour_windows": 0,
        }

    from printer_v1.operator_cli.one_token_4h_runtime import (
        load_standard_four_hour_eligibility_manifests,
    )
    manifests = load_standard_four_hour_eligibility_manifests(
        conn,
        campaign_id=str(campaign_id),
        run_id=str(run_id),
        cycle_id=str(cycle_id),
        factory_run_id=str(factory_run_id),
    )

    windows = conn.execute(
        """SELECT w.*,s.slot_ordinal,s.token_state,s.token_row_id AS slot_token_row_id,
                  s.pair_row_id AS slot_pair_row_id
           FROM printer_memory_factory_campaign_windows AS w
           JOIN printer_memory_factory_campaign_token_slots AS s
             ON s.token_slot_id=w.token_slot_id
            AND s.campaign_id=w.campaign_id AND s.run_id=w.run_id AND s.cycle_id=w.cycle_id
           WHERE w.campaign_id=? AND w.run_id=? AND w.cycle_id=?
             AND w.window_kind='WINDOW_4H'
           ORDER BY s.slot_ordinal,w.window_id""",
        (str(campaign_id), str(run_id), str(cycle_id)),
    ).fetchall()
    manifest_mode = True
    expected_slot_ids = (
        {slot_id for slot_id, manifest in manifests.items() if manifest["eligible"] is True}
        if manifests is not None
        else {str(row["token_slot_id"]) for row in windows}
    )
    expected_continuation_count = len(expected_slot_ids) if manifest_mode else 2
    reasons: list[str] = []
    actual_slot_ids = {str(row["token_slot_id"]) for row in windows}
    if len(windows) != expected_continuation_count:
        reasons.append(
            f"standard_window_4h_count:{len(windows)} expected={expected_continuation_count}"
        )
    if manifest_mode and actual_slot_ids != expected_slot_ids:
        reasons.append("standard_window_4h_slot_set_mismatch")
    if len(actual_slot_ids) != len(windows):
        reasons.append("duplicate_standard_window_4h_slot_identity")
    if len({int(row["token_row_id"]) for row in windows}) != len(windows):
        reasons.append("duplicate_standard_window_4h_token_identity")

    success_states = {
        "CLEAN_PROMOTED", "DIRTY", "NO_PROMOTION", "ALREADY_EXISTS_IDEMPOTENT"
    }
    per_token: list[dict[str, Any]] = []
    expected_owned_total = 0
    for window in windows:
        window_reasons: list[str] = []
        slot_id = str(window["token_slot_id"])
        token_id = int(window["token_row_id"])
        pair_id = int(window["pair_row_id"])
        if manifest_mode and slot_id not in expected_slot_ids:
            window_reasons.append("unexpected_4h_window_for_ineligible_slot")
        if (
            int(window["slot_token_row_id"]) != token_id
            or int(window["slot_pair_row_id"]) != pair_id
        ):
            window_reasons.append("slot_token_pair_identity_mismatch")
        owned = conn.execute(
            """SELECT s.*,j.status AS scheduler_status,sw.work_state,sw.scheduler_work_id
               FROM printer_memory_factory_campaign_scheduler_work AS sw
               JOIN printer_memory_factory_run_steps AS s
                 ON s.scheduler_job_id=sw.scheduler_job_id
               JOIN printer_scheduler_jobs AS j ON j.id=sw.scheduler_job_id
               WHERE sw.campaign_id=? AND sw.run_id=? AND sw.cycle_id=?
                 AND sw.factory_run_id=? AND sw.window_id=? AND sw.token_slot_id=?
                 AND sw.ownership_contract_version='V2_STAGE_SCOPED'
                 AND sw.work_scope='WINDOW_LIFECYCLE' AND sw.stage_id='WINDOW_4H'
                 AND sw.target_category='CAMPAIGN_WINDOW' AND sw.target_identity=sw.window_id
                 AND s.run_id=? AND s.token_id=? AND s.pair_id=?
                 AND s.step_kind IN (
                     'LONG_CONTINUATION_SNAPSHOT','LONG_CONTINUATION_CLOSE',
                     'LONG_CONTINUATION_CLOSE_PRE_CLOSE_CRITICAL',
                     'LONG_CONTINUATION_CLOSE_EVIDENCE',
                     'LONG_CONTINUATION_CLOSE_CONTEXT',
                     'LONG_CONTINUATION_CLOSE_AUDIT'
                 )
               ORDER BY s.scheduled_for,s.id""",
            (
                str(campaign_id), str(run_id), str(cycle_id), str(factory_run_id),
                str(window["window_id"]), slot_id, str(factory_run_id), token_id, pair_id,
            ),
        ).fetchall()
        lanes = {str(row["tracking_lane"]) for row in owned}
        lane = next(iter(lanes)) if len(lanes) == 1 else None
        if lane is None:
            window_reasons.append("missing_or_ambiguous_4h_tracking_lane")
            expected = 0
        else:
            try:
                policy = _cadence_get_policy("WINDOW_4H", lane)
                if policy is None:
                    raise ValueError("missing policy")
                expected = int(policy.minimum_required_snapshots)
            except Exception:
                expected = 0
                window_reasons.append("missing_4h_cadence_policy")
        expected_owned = expected + 3 if expected else 0
        expected_owned_total += expected_owned
        if expected and len(owned) != expected_owned:
            window_reasons.append(
                f"owned_4h_work_count:{len(owned)} expected={expected_owned}"
            )
        actual = sum(1 for row in owned if row["snapshot_id"] is not None)
        if expected and actual != expected:
            window_reasons.append(f"incomplete_4h_collection:{actual}/{expected}")
        closes = [
            row for row in owned
            if str(row["step_kind"])
            in {"LONG_CONTINUATION_CLOSE", "LONG_CONTINUATION_CLOSE_AUDIT"}
        ]
        if len(closes) != 1:
            window_reasons.append(f"owned_4h_close_count:{len(closes)} expected=1")
            close = None
        else:
            close = closes[0]
            if str(close["step_status"]) != "SUCCEEDED":
                window_reasons.append(f"owned_4h_close_not_succeeded:{close['step_status']}")
            if str(close["scheduler_status"]) != "SUCCEEDED":
                window_reasons.append(
                    f"owned_4h_close_scheduler_not_succeeded:{close['scheduler_status']}"
                )
            if str(close["work_state"]) != "SUCCEEDED":
                window_reasons.append(
                    f"owned_4h_close_campaign_work_not_succeeded:{close['work_state']}"
                )
        memory_id = (
            int(window["memory_window_row_id"])
            if window["memory_window_row_id"] is not None else None
        )
        if memory_id is None:
            window_reasons.append("missing_bound_4h_memory_window")
            physical = None
            clean_object = None
        else:
            physical = conn.execute(
                """SELECT id,token_id,pair_id,window_kind,data_quality_label,
                          memory_status,memory_quality_label,do_not_train
                   FROM printer_memory_windows WHERE id=?""",
                (memory_id,),
            ).fetchone()
            if (
                physical is None
                or int(physical["token_id"]) != token_id
                or int(physical["pair_id"]) != pair_id
                or str(physical["window_kind"]) != "WINDOW_4H"
            ):
                window_reasons.append("bound_4h_memory_identity_mismatch")
                clean_object = None
            else:
                clean_object = _exact_complete_clean_4h_object(
                    conn, memory_window_row_id=memory_id
                )
        window_state = str(window["window_state"])
        if window_state not in success_states:
            window_reasons.append(f"nonterminal_or_failed_4h_window_state:{window_state}")
        if str(window["token_state"]) != "WINDOW_4H_CLOSED":
            window_reasons.append(f"token_slot_not_window_4h_closed:{window['token_state']}")
        if window_state in {"CLEAN_PROMOTED", "ALREADY_EXISTS_IDEMPOTENT"}:
            if clean_object is None:
                window_reasons.append("clean_campaign_state_without_complete_clean_object")
        elif window_state == "DIRTY" and physical is not None:
            dirty = (
                int(physical["do_not_train"] or 0) != 0
                or str(physical["data_quality_label"] or "") != "CLEAN_DATA"
                or str(physical["memory_status"] or "") in {
                    "DIRTY_MEMORY", "AUDIT_ONLY_MEMORY", "DO_NOT_TRAIN"
                }
                or str(physical["memory_quality_label"] or "") in {
                    "DIRTY_MEMORY", "AUDIT_ONLY_MEMORY", "DO_NOT_TRAIN"
                }
            )
            if not dirty:
                window_reasons.append("dirty_campaign_state_without_dirty_physical_memory")
        elif window_state == "NO_PROMOTION" and clean_object is not None:
            window_reasons.append("no_promotion_campaign_state_with_clean_object")

        per_token.append(
            {
                "token_id": token_id,
                "pair_id": pair_id,
                "token_slot_id": slot_id,
                "window_id": str(window["window_id"]),
                "tracking_lane": lane,
                "expected_snapshots": expected,
                "actual_snapshots": actual,
                "window_state": window_state,
                "token_state": str(window["token_state"]),
                "memory_window_row_id": memory_id,
                "complete_clean_object": clean_object is not None,
                "reasons": window_reasons,
            }
        )
        reasons.extend(f"{window['window_id']}:{reason}" for reason in window_reasons)

    if manifest_mode and manifests is not None:
        for slot_id, manifest in manifests.items():
            if manifest["eligible"] is True:
                continue
            token_id = int(manifest["token_id"])
            pair_id = int(manifest["pair_id"])
            long_count = int(conn.execute(
                """SELECT COUNT(*) FROM printer_memory_factory_run_steps
                   WHERE run_id=? AND token_id=? AND pair_id=?
                     AND step_kind LIKE 'LONG_CONTINUATION_%'""",
                (str(factory_run_id), token_id, pair_id),
            ).fetchone()[0])
            owned_count = int(conn.execute(
                """SELECT COUNT(*) FROM printer_memory_factory_campaign_scheduler_work
                   WHERE campaign_id=? AND run_id=? AND cycle_id=? AND factory_run_id=?
                     AND token_slot_id=? AND ownership_contract_version='V2_STAGE_SCOPED'
                     AND work_scope='WINDOW_LIFECYCLE' AND stage_id='WINDOW_4H'""",
                (str(campaign_id), str(run_id), str(cycle_id), str(factory_run_id), slot_id),
            ).fetchone()[0])
            if long_count:
                reasons.append(f"ineligible_slot_long_work:{slot_id}:{long_count}")
            if owned_count:
                reasons.append(f"ineligible_slot_owned_4h_work:{slot_id}:{owned_count}")

    total_long = int(conn.execute(
        """SELECT COUNT(*) FROM printer_memory_factory_run_steps
           WHERE run_id=? AND step_kind LIKE 'LONG_CONTINUATION_%'""",
        (str(factory_run_id),),
    ).fetchone()[0])
    total_owned = int(conn.execute(
        """SELECT COUNT(*) FROM printer_memory_factory_campaign_scheduler_work
           WHERE campaign_id=? AND run_id=? AND cycle_id=? AND factory_run_id=?
             AND ownership_contract_version='V2_STAGE_SCOPED'
             AND work_scope='WINDOW_LIFECYCLE' AND stage_id='WINDOW_4H'""",
        (str(campaign_id), str(run_id), str(cycle_id), str(factory_run_id)),
    ).fetchone()[0])
    if manifest_mode:
        if total_long != expected_owned_total:
            reasons.append(f"standard_long_work_count:{total_long} expected={expected_owned_total}")
        if total_owned != expected_owned_total:
            reasons.append(f"standard_owned_4h_work_count:{total_owned} expected={expected_owned_total}")
        later = int(conn.execute(
            """SELECT COUNT(*) FROM printer_memory_factory_campaign_windows
               WHERE campaign_id=? AND run_id=? AND cycle_id=?
                 AND window_kind IN ('WINDOW_12H','WINDOW_24H')""",
            (str(campaign_id), str(run_id), str(cycle_id)),
        ).fetchone()[0])
        if later:
            reasons.append(f"unexpected_later_window_count:{later}")

    active_owned = int(conn.execute(
        """SELECT COUNT(*) FROM printer_memory_factory_campaign_scheduler_work
           WHERE campaign_id=? AND run_id=? AND cycle_id=? AND factory_run_id=?
             AND ownership_contract_version='V2_STAGE_SCOPED'
             AND work_scope='WINDOW_LIFECYCLE' AND stage_id='WINDOW_4H'
             AND work_state IN ('PENDING','RUNNING','COOLDOWN')""",
        (str(campaign_id), str(run_id), str(cycle_id), str(factory_run_id)),
    ).fetchone()[0])
    nonterminal_windows = int(conn.execute(
        """SELECT COUNT(*) FROM printer_memory_factory_campaign_windows
           WHERE campaign_id=? AND run_id=? AND cycle_id=? AND window_kind='WINDOW_4H'
             AND window_state IN ('PLANNED','COLLECTING','CLOSE_PENDING','AUDITING')""",
        (str(campaign_id), str(run_id), str(cycle_id)),
    ).fetchone()[0])
    if active_owned:
        reasons.append(f"active_owned_four_hour_work:{active_owned}")
    if nonterminal_windows:
        reasons.append(f"nonterminal_owned_four_hour_windows:{nonterminal_windows}")
    return {
        "enabled": True,
        "complete": bool(progression.get("complete")) and not reasons,
        "reasons": reasons,
        "per_token": progression.get("per_token", []),
        "eligible_window_details": per_token,
        "expected_continuation_count": expected_continuation_count,
        "progression_attempt_id": progression.get("progression_attempt_id"),
        "aggregate_state": progression.get("aggregate_state"),
        "requires_review": progression.get("requires_review", False),
        "active_owned_four_hour_work": active_owned,
        "nonterminal_owned_four_hour_windows": nonterminal_windows,
        "window_count": len(windows),
    }


def _durable_standard_4h_progression_stop_cause(
    conn: sqlite3.Connection,
    *,
    campaign_id: str,
    campaign_run_id: str,
    cycle_id: str,
    exc: BaseException,
) -> str | None:
    """Return a progression primary only for the exact progression exception."""
    if (
        type(exc).__name__ != "StandardFourHourOperationalError"
        or type(exc).__module__
        != "printer_v1.operator_cli.operational_standard_4h"
    ):
        return None
    row = conn.execute(
        """SELECT attempt_state,first_terminal_cause
           FROM printer_memory_factory_standard_4h_progression_attempts
           WHERE campaign_id=? AND campaign_run_id=? AND cycle_id=?""",
        (campaign_id, campaign_run_id, cycle_id),
    ).fetchone()
    if (
        row is None
        or str(row[0])
        not in {"TERMINAL_FAILED", "TERMINAL_CANCELLED", "INTERRUPTED_REVIEW"}
        or row[1] is None
        or not str(row[1]).strip()
    ):
        return None
    return str(row[1])

def _two_token_continuous_proof_validation(
    *,
    config: Mapping[str, Any],
    selected: list[dict[str, Any]],
    steps: list[dict[str, Any]],
    windows_by_id: Mapping[int, dict[str, Any]],
    promotions_by_window_id: Mapping[int, dict[str, Any]],
    pending_steps: int,
    running_jobs: int,
    forbidden: Mapping[str, int],
    dirty_promotion_count: int,
) -> dict[str, Any]:
    """Validate the exact E.9 proof shape; ordinary continuous runs are untouched."""
    plan = _compressed_two_token_plan(config)
    if plan is None:
        return {"enabled": False}

    reasons: list[str] = []
    selected_mints = [str(row.get("token_mint")) for row in selected]
    expected_mints = {
        plan["continuation_token_mint"],
        plan["non_continuation_token_mint"],
    }
    if len(selected_mints) != 2 or set(selected_mints) != expected_mints:
        reasons.append("selected_identity_set_mismatch")

    relevant = [
        step for step in steps
        if step.get("step_kind") in TERMINAL_CLOSE_STEP_KINDS
    ]
    foreign = [
        str(step.get("token_mint")) for step in steps
        if str(step.get("token_mint")) not in expected_mints
    ]
    if foreign:
        reasons.append("foreign_lifecycle_identity")

    closes_15m = [
        step for step in relevant
        if step.get("step_kind") in {"WINDOW_CLOSE", "WINDOW_CLOSE_AUDIT"}
    ]
    if len(closes_15m) != 2 or any(
        step.get("step_status") != "SUCCEEDED" for step in closes_15m
    ):
        reasons.append("two_terminal_15m_closes_required")
    for step in closes_15m:
        window_id = step.get("memory_window_id")
        window = windows_by_id.get(int(window_id)) if window_id is not None else None
        if window is None or window.get("window_kind") != "WINDOW_15M":
            reasons.append("invalid_15m_window_attachment")

    by_mint = {str(step.get("token_mint")): step for step in closes_15m}
    continuation_close_15m = by_mint.get(plan["continuation_token_mint"])
    stopped_close_15m = by_mint.get(plan["non_continuation_token_mint"])
    for step, expected_verdict, expected_reason in (
        (continuation_close_15m, None, plan["continuation_evidence"]),
        (stopped_close_15m, "VALID_NO_CAPTURE", plan["non_continuation_evidence"]),
    ):
        try:
            result = json.loads(str(step.get("result_json") or "{}")) if step else {}
        except json.JSONDecodeError:
            result = {}
        support = result.get("support_5m") if isinstance(result, dict) else None
        continuation = result.get("continuation_plan") if isinstance(result, dict) else None
        if expected_verdict is None:
            if not isinstance(support, dict) or support.get("window_5m_id") is None:
                reasons.append("positive_support_5m_missing")
            if not isinstance(support, dict) or support.get("proof_evidence") != expected_reason:
                reasons.append("continuation_evidence_mismatch")
            if not isinstance(continuation, dict) or continuation.get("enqueue_ok") is not True:
                reasons.append("continuation_plan_missing")
        else:
            if (
                not isinstance(support, dict)
                or support.get("verdict") != expected_verdict
                or support.get("reason") != expected_reason
                or support.get("window_5m_id") is not None
            ):
                reasons.append("negative_support_5m_disposition_missing")
            if (
                not isinstance(continuation, dict)
                or continuation.get("verdict") != "STOP_AFTER_15M"
                or continuation.get("reason") != expected_reason
                or continuation.get("planned_jobs") != 0
            ):
                reasons.append("non_continuation_disposition_missing")

    closes_1h = [
        step for step in relevant
        if step.get("step_kind")
        in {"CONTINUATION_CLOSE", "CONTINUATION_CLOSE_AUDIT"}
    ]
    if (
        len(closes_1h) != 1
        or closes_1h[0].get("step_status") != "SUCCEEDED"
        or closes_1h[0].get("token_mint") != plan["continuation_token_mint"]
    ):
        reasons.append("one_exact_terminal_1h_close_required")
    elif windows_by_id.get(int(closes_1h[0]["memory_window_id"]), {}).get("window_kind") != "WINDOW_1H":
        reasons.append("invalid_1h_window_attachment")

    closes_4h = [
        step for step in relevant
        if step.get("step_kind")
        in {"LONG_CONTINUATION_CLOSE", "LONG_CONTINUATION_CLOSE_AUDIT"}
    ]
    if (
        len(closes_4h) != 1
        or closes_4h[0].get("step_status") != "SUCCEEDED"
        or closes_4h[0].get("token_mint") != plan["continuation_token_mint"]
    ):
        reasons.append("one_exact_terminal_4h_close_required")
    elif windows_by_id.get(int(closes_4h[0]["memory_window_id"]), {}).get("window_kind") != "WINDOW_4H":
        reasons.append("invalid_4h_window_attachment")

    attached_ids = {
        int(step["memory_window_id"])
        for step in steps if step.get("memory_window_id") is not None
    }
    promotions = [
        promotion for window_id, promotion in promotions_by_window_id.items()
        if int(window_id) in attached_ids
    ]
    if len(promotions) != 1:
        reasons.append(f"exactly_one_authoritative_clean_promotion_required:{len(promotions)}")
    if dirty_promotion_count:
        reasons.append(f"dirty_promotion_present:{dirty_promotion_count}")
    if pending_steps:
        reasons.append(f"pending_or_running_steps:{pending_steps}")
    if running_jobs:
        reasons.append(f"running_jobs:{running_jobs}")
    if any(int(value) != 0 for value in forbidden.values()):
        reasons.append("forbidden_table_delta")

    return {
        "enabled": True,
        "complete": not reasons,
        "reasons": reasons,
        "continuation_token_mint": plan["continuation_token_mint"],
        "non_continuation_token_mint": plan["non_continuation_token_mint"],
        "terminal_15m_count": len(closes_15m),
        "terminal_1h_count": len(closes_1h),
        "terminal_4h_count": len(closes_4h),
        "authoritative_clean_promotion_count": len(promotions),
        "dirty_promotion_count": dirty_promotion_count,
        "cleanup_complete": pending_steps == 0 and running_jobs == 0,
    }

def _final_report(
    conn: sqlite3.Connection, *, run_id: str, config: dict[str, Any],
    discovery: dict[str, Any], before: dict[str, int], stop_reason: str,
    started_at: str,
) -> dict[str, Any]:
    provenance = validate_launch_provenance(config.get("git_provenance", {}))
    after = _counts(conn)
    deltas = _deltas(before, after)
    steps = [dict(row) for row in conn.execute(
        "SELECT * FROM printer_memory_factory_run_steps WHERE run_id=? ORDER BY scheduled_for, id", (run_id,)
    ).fetchall()]
    jobs = [dict(row) for row in conn.execute(
        "SELECT j.* FROM printer_scheduler_jobs j JOIN printer_memory_factory_run_steps s ON s.scheduler_job_id=j.id WHERE s.run_id=? ORDER BY j.id",
        (run_id,),
    ).fetchall()]
    # V2-9.7E.47 A3: the historic narrow count (this run's step jobs that are
    # RUNNING or locked) is preserved as a compatibility field, but the
    # authoritative terminal gate is now exact campaign-scoped active-work
    # accounting: PENDING / RUNNING / COOLDOWN / locked, across factory
    # run-step jobs, discovery jobs and campaign scheduler work.
    running_or_locked_run_step_jobs = sum(
        1 for job in jobs
        if job["status"] == "RUNNING" or job["locked_at"] or job["lock_owner"]
    )
    active_work = campaign_active_work_report(
        conn,
        factory_run_id=run_id,
        campaign_id=config.get("campaign_id") or None,
        run_id=config.get("campaign_run_id") or None,
        cycle_id=config.get("cycle_id") or None,
    )
    running = int(active_work["active_jobs"])
    forbidden = {table: deltas.get(table, 0) for table in _FORBIDDEN_DELTA_TABLES}
    windows = [dict(row) for row in conn.execute(
        "SELECT * FROM printer_memory_windows WHERE id IN (SELECT memory_window_id FROM printer_memory_factory_run_steps WHERE run_id=? AND memory_window_id IS NOT NULL)",
        (run_id,),
    ).fetchall()]
    selected = _selected_targets(conn, discovery.get("selection_handoff_report", {}).get("batch_id") or "")
    windows_by_id = {int(w["id"]): w for w in windows}
    promotions_by_window_id = _authoritative_promotions_for_run(conn, run_id)
    window_blocker_summary = build_window_blocker_summary(windows)
    memory_authority = build_memory_authority_summary(
        windows, promotions_by_window_id
    )
    dirty_promotion_count = int(conn.execute(
        """SELECT COUNT(DISTINCT e.id)
           FROM printer_episodes e
           JOIN printer_memory_factory_run_steps s ON s.memory_window_id=e.memory_window_id
           WHERE s.run_id=? AND (
               e.episode_status!='COMPLETE'
               OR e.memory_status!='CLEAN_MEMORY'
               OR e.data_quality_label!='CLEAN_DATA'
               OR e.do_not_train!=0
               OR e.memory_quality_label!='CLEAN_MEMORY'
           )""",
        (run_id,),
    ).fetchone()[0])
    per_token = _per_token_outcomes(steps, windows_by_id, promotions_by_window_id)
    run_local_yield, memory_results = _memory_yield_report(per_token, windows)
    terminal_window_outcomes = sum(1 for t in per_token if t["reached_terminal_window"])
    budgets = _run_budgets(conn, run_id, discovery, steps)
    lifecycle = _continuous_lifecycle_report(conn, run_id, steps)
    pending_run_steps = sum(1 for s in steps if s["step_status"] in {"PENDING", "RUNNING"})
    primary_cause = _primary_terminal_cause(conn, steps, stop_reason)
    historical_terminal_validation = _four_hour_terminal_validation(
        config=config, steps=steps, windows_by_id=windows_by_id,
        budgets=budgets, pending_steps=pending_run_steps, running_jobs=running,
        primary_cause=primary_cause,
        complete_clean_objects_by_window_id=promotions_by_window_id,
    )
    standard_four_hour_validation = _standard_campaign_four_hour_terminal_validation(
        conn,
        factory_run_id=run_id,
        campaign_id=config.get("campaign_id"),
        run_id=config.get("campaign_run_id"),
        cycle_id=config.get("cycle_id"),
    )
    if standard_four_hour_validation.get("enabled"):
        terminal_validation = {
            **standard_four_hour_validation,
            "run_status": (
                "COMPLETED" if standard_four_hour_validation.get("complete")
                else "SAFE_STOPPED"
            ),
            "stop_reason": (
                STOP_COMPLETED if standard_four_hour_validation.get("complete")
                else STOP_TERMINAL_4H
            ),
            "primary_cause": primary_cause,
            "historical_one_token_validator_applicable": False,
        }
    else:
        terminal_validation = historical_terminal_validation
    two_token_validation = _two_token_continuous_proof_validation(
        config=config, selected=selected, steps=steps,
        windows_by_id=windows_by_id,
        promotions_by_window_id=promotions_by_window_id,
        pending_steps=pending_run_steps, running_jobs=running,
        forbidden=forbidden,
        dirty_promotion_count=dirty_promotion_count,
    )
    effective_status = "COMPLETED" if stop_reason == STOP_COMPLETED else "SAFE_STOPPED"
    effective_reason = stop_reason
    if primary_cause.get("present"):
        effective_status = str(primary_cause["run_status"])
        effective_reason = str(primary_cause["stop_reason"])
    elif terminal_validation.get("enabled"):
        effective_status = str(terminal_validation["run_status"])
        effective_reason = str(terminal_validation["stop_reason"])
    if (
        two_token_validation.get("enabled")
        and not two_token_validation.get("complete")
        and not primary_cause.get("present")
    ):
        effective_status = "SAFE_STOPPED"
        effective_reason = STOP_TWO_TOKEN_PROOF
    return {
        "command": COMMAND_NAME, "policy_version": POLICY_VERSION,
        "run_id": run_id, "run_status": effective_status,
        "stop_reason": effective_reason, "started_at": started_at, "finished_at": _iso(),
        "config": config, "git_provenance": provenance,
        "selection_seed": discovery.get("selection_handoff_report", {}).get("selection_seed"),
        "eligible_pool_size": discovery.get("selection_handoff_report", {}).get("eligible_pool_size", 0),
        "selected_tokens": selected, "discovery_report": discovery,
        "scheduler_jobs": jobs, "steps": steps, "memory_windows": windows,
        # V2-9.7B.1: the attached window identifies the run-local candidate;
        # its eligible printer_episodes row is authoritative for clean yield.
        "per_token_outcomes": per_token,
        "terminal_window_outcomes": terminal_window_outcomes,
        "run_local_yield": run_local_yield,
        "blocking_reasons": window_blocker_summary["blocking_reasons"],
        "window_blocker_summary": window_blocker_summary,
        "memory_authority": memory_authority,
        "historical_report_note": (
            "Lane K/E2Z pipeline summaries embedded in step result_json may include "
            "historical windows copied into the proof DB and are not authoritative "
            "for clean yield on their own. Exact attached-window E2Z "
            "events distinguish created from idempotent replay, but clean yield is "
            "authoritative only when an eligible printer_episodes row matches the "
            "run-attached window, token, pair, and window kind."
        ),
        "run_budgets": budgets,
        "four_hour_phase_usage": budgets.get("four_hour_phase_usage"),
        "cumulative_lifecycle_usage": budgets.get("cumulative_lifecycle_usage"),
        "four_hour_terminal_validation": terminal_validation,
        "standard_four_hour_terminal_validation": standard_four_hour_validation,
        "historical_one_token_four_hour_terminal_validation": (
            historical_terminal_validation
            if standard_four_hour_validation.get("enabled") else None
        ),
        "two_token_continuous_proof": two_token_validation,
        "primary_terminal_cause": primary_cause,
        "secondary_terminal_details": [],
        "continuous_lifecycle": lifecycle,
        "pending_or_running_run_steps": pending_run_steps,
        "memory_results": memory_results,
        "counts_before": before, "counts_after": after, "table_deltas": deltas,
        "forbidden_deltas": forbidden, "running_jobs_after_stop": running,
        # V2-9.7E.47 A3 exact active-work report + preserved compatibility field.
        "campaign_active_work": active_work,
        "active_jobs_after_stop": int(active_work["active_jobs"]),
        "active_work_rows_after_stop": int(active_work["active_work_rows"]),
        "running_or_locked_run_step_jobs": running_or_locked_run_step_jobs,
        "locks_preserved": {
            "retrieval": all(value == 0 for table, value in forbidden.items() if "retrieval" in table),
            "financial": all(value == 0 for table, value in forbidden.items() if "retrieval" not in table),
            "window_15m_only": not bool(config.get("continuous_first_hour")),
            "approved_window_scope_only": all(
                str(row.get("window_kind")) in {"WINDOW_5M_MICRO_EVENT", "WINDOW_15M", "WINDOW_1H", "WINDOW_4H"}
                for row in windows
            ),
            "paper_decisions_off": True,
        },
    }


def _apply_post_report_integrity(report: dict[str, Any]) -> None:
    """Attach cleanup/integrity details without replacing an earlier cause."""
    details = report.setdefault("secondary_terminal_details", [])
    if report["running_jobs_after_stop"]:
        details.append({
            "reason": STOP_RUNNING,
            "running_jobs": report["running_jobs_after_stop"],
        })
        if report["run_status"] == "COMPLETED":
            report["stop_reason"] = STOP_RUNNING
            report["run_status"] = "SAFE_STOPPED"
    if any(report["forbidden_deltas"].values()):
        details.append({
            "reason": STOP_DB_DELTA,
            "forbidden_deltas": report["forbidden_deltas"],
        })
        if report["run_status"] == "COMPLETED":
            report["stop_reason"] = STOP_DB_DELTA
            report["run_status"] = "SAFE_STOPPED"

def load_report_only(db_path: str | Path, run_id: str) -> dict[str, Any]:
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    try:
        row = conn.execute(
            "SELECT final_report_json FROM printer_memory_factory_runs WHERE run_id=? AND final_report_json IS NOT NULL",
            (run_id,),
        ).fetchone()
        if row is None:
            raise ValueError(f"terminal report not found for run_id={run_id}")
        report = json.loads(str(row[0]))
        report["replay"] = {"mode": "REPORT_ONLY", "new_source_calls": 0, "new_evidence_rows": 0}
        return report
    finally:
        conn.close()


def _select_next_pending_step(
    conn: sqlite3.Connection, *, run_id: str, now: datetime,
) -> sqlite3.Row | None:
    """Select by AGENTS category, truthful deadline, then token fairness."""
    candidates = conn.execute(
        """SELECT s.id AS step_id,s.run_id,s.token_id,s.pair_id,s.token_mint,
                  s.pair_address,s.tracking_lane,s.step_kind,s.result_json,
                  j.id AS scheduler_job_id,j.job_kind,j.scheduled_for,j.created_at
           FROM printer_memory_factory_run_steps AS s
           JOIN printer_scheduler_jobs AS j ON j.id=s.scheduler_job_id
           WHERE s.run_id=? AND s.step_status='PENDING'
             AND j.status IN ('PENDING','COOLDOWN')
           ORDER BY j.scheduled_for,j.created_at,j.id,s.id""",
        (str(run_id),),
    ).fetchall()
    lawful = [
        row for row in candidates
        if JobKind(str(row["job_kind"])) is not JobKind.OPEN_PAPER_TRADE_MONITOR
        and close_phase_dependency_ready(conn, row)
    ]
    if not lawful:
        return None

    current_time = _scheduler_fairness_time(now)
    due = [
        row for row in lawful
        if _scheduler_fairness_time(row["scheduled_for"]) <= current_time
    ]
    if not due:
        selected_id = int(lawful[0]["step_id"])
        return conn.execute(
            "SELECT * FROM printer_memory_factory_run_steps WHERE id=?",
            (selected_id,),
        ).fetchone()

    winning_category: JobKind | None = None
    for category in JOB_RESOURCE_CATEGORY_ORDER:
        if any(job_resource_category(str(row["job_kind"])) is category for row in due):
            winning_category = category
            break
    if winning_category is None:
        raise ValueError("due Scheduler work has no canonical AGENTS category")
    category_rows = [
        row for row in due
        if job_resource_category(str(row["job_kind"])) is winning_category
    ]

    service_counts: dict[str, int] = {}

    def fairness_owner(row: Mapping[str, Any]) -> str:
        if str(row["step_kind"]) in PRE_CLOSE_STEP_KINDS:
            try:
                payload = json.loads(str(row["result_json"] or "{}"))
            except (TypeError, json.JSONDecodeError):
                payload = {}
            exact = tuple(
                str(payload.get(field) or "")
                for field in (
                    "campaign_run_id",
                    "cycle_id",
                    "token_slot_id",
                    "campaign_window_id",
                )
            )
            if all(exact):
                return "campaign:" + ":".join(exact)
        return "token:" + _scheduler_fairness_token_id(row["token_id"])

    served_rows = conn.execute(
        """SELECT s.token_id,s.step_kind,s.result_json,j.job_kind
           FROM printer_memory_factory_run_steps AS s
           JOIN printer_scheduler_jobs AS j ON j.id=s.scheduler_job_id
           WHERE s.run_id=? AND j.started_at IS NOT NULL""",
        (str(run_id),),
    ).fetchall()
    for row in served_rows:
        if job_resource_category(str(row["job_kind"])) is not winning_category:
            continue
        if str(row["step_kind"]) not in PRE_CLOSE_STEP_KINDS:
            owner_identity = fairness_owner(row)
            service_counts[owner_identity] = service_counts.get(owner_identity, 0) + 1
    preclose_service_rows = conn.execute(
        """SELECT token_id,step_kind,result_json
           FROM printer_memory_factory_run_steps
           WHERE run_id=? AND step_kind IN (?,?,?)""",
        (str(run_id), *sorted(PRE_CLOSE_STEP_KINDS)),
    ).fetchall()
    for row in preclose_service_rows:
        try:
            payload = json.loads(str(row["result_json"] or "{}"))
            count = int(payload.get("terminal_unit_count") or 0)
        except (TypeError, ValueError, json.JSONDecodeError):
            count = 0
        owner_identity = fairness_owner(row)
        service_counts[owner_identity] = service_counts.get(owner_identity, 0) + count

    def deadline_for(row: sqlite3.Row) -> str:
        if str(row["step_kind"]) in PRE_CLOSE_STEP_KINDS:
            try:
                payload = json.loads(str(row["result_json"] or "{}"))
                active = [
                    datetime.fromisoformat(str(unit["latest_safe_claim_at"]))
                    for unit in payload.get("source_unit_manifest", [])
                    if isinstance(unit, Mapping) and unit.get("state") == "PENDING"
                ]
                if active:
                    return min(active).astimezone(timezone.utc).isoformat()
            except (TypeError, ValueError, json.JSONDecodeError):
                pass
        return deadline_order_value(
            project_scheduler_job_evidence_deadline(
                conn,
                factory_run_id=str(run_id),
                scheduler_job_id=int(row["scheduler_job_id"]),
            )
        )

    selected = min(
        category_rows,
        key=lambda row: (
            close_phase_order(str(row["step_kind"]))
            if winning_category is JobKind.MEMORY_WINDOW_CLOSE
            else 0,
            deadline_for(row),
            *deterministic_token_fairness_key(
                ordinary_service_count=service_counts.get(
                    fairness_owner(row), 0
                ),
                scheduled_for=_scheduler_fairness_time(row["scheduled_for"]),
                created_at=_scheduler_fairness_time(row["created_at"]),
                stable_token_id=_scheduler_fairness_token_id(row["token_id"]),
                stable_work_id=int(row["scheduler_job_id"]),
            ),
        ),
    )
    selected_id = int(selected["step_id"])
    return conn.execute(
        "SELECT * FROM printer_memory_factory_run_steps WHERE id=?",
        (selected_id,),
    ).fetchone()


def _scheduler_fairness_time(value: object) -> datetime:
    parsed = datetime.fromisoformat(str(value))
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _scheduler_fairness_token_id(value: object) -> str:
    return "" if value is None else str(value)


def run_one_command_15m_factory(
    db_path: str | Path, backup_path: str | Path, *, operator_approved: bool,
    proof_mode: bool, window_kind: str = WINDOW_KIND, max_selected_tokens: int = 2,
    max_source_requests: int = 2, timeout_seconds: float = 5.0,
    total_duration_seconds: float = 1200.0, selection_seed: str | None = None,
    v2_5_proof_mode: bool = False,
    continuous_first_hour: bool = False,
    continuous_four_hour: bool = False,
    four_hour_proof_mode: bool = False,
    standard_four_hour_campaign: bool = False,
    selective_1h_continuation: bool = False,
    four_token_proof_controller: Any | None = None,
    later_cycle_discovery_callback: Callable[..., Any] | None = None,
    later_cycle_acquisition_quantum_seconds: float | Callable[[], float] = 60.0,
    four_token_health_projector: Callable[[sqlite3.Connection, datetime], Any]
    | None = None,
    four_token_shared_terminalizer: Callable[..., Mapping[str, Any]]
    | None = None,
    source_governor_owner: Any | None = None,
    central_scheduler_owner: Any | None = None,
    compressed_two_token_proof_plan: CompressedTwoTokenProofPlan | None = None,
    operational_natural_disposition: bool = False,
    supervision_execution_id: str | None = None,
    campaign_id: str | None = None,
    campaign_run_id: str | None = None,
    cycle_id: str | None = None,
    configuration_id: str | None = None,
    factory_run_id: str | None = None,
    cancellation_probe: Callable[[], str | None] | None = None,
    factory_run_initialized: Callable[[str], None] | None = None,
    discovery_transport: Any = None, discovery_runner: Callable[..., dict[str, Any]] | None = None,
    snapshot_adapter_factory: Callable[..., Any] | None = None,
    fallback_snapshot_adapter_factory: Callable[..., Any] | None = None,
    context_adapter_factories: dict[str, Callable[..., Any]] | None = None,
    _window_seconds: float = 900.0, _sleep: Callable[[float], None] = time.sleep,
    _monotonic: Callable[[], float] = time.monotonic,
    _continuation_seconds: float = _CONTINUATION_SECONDS,
    project_root: str | Path | None = None,
    launch_provenance: Mapping[str, Any] | None = None,
    operational_persistent_mode: bool = False,
    operational_database_target_binding: Any | None = None,
    disposable_public_composition_proof_binding: Any | None = None,
    lifecycle_ownership_context: Mapping[str, Any] | None = None,
    lifecycle_operation_observer: Callable[[Mapping[str, Any]], None] | None = None,
    _post_handoff_fault: str | None = None,
    _post_handoff_scope_recorder: Any | None = None,
) -> dict[str, Any]:
    path = Path(db_path).resolve()
    backup = Path(backup_path).resolve()
    reasons: list[str] = []
    provenance: dict[str, Any] | None = None
    try:
        provenance = (
            capture_git_provenance(project_root or Path.cwd())
            if launch_provenance is None
            else validate_launch_provenance(launch_provenance)
        )
    except GitProvenanceError as exc:
        reasons.append(f"Git provenance preflight failed: {exc}")
    if not operator_approved: reasons.append("operator approval required")
    if not proof_mode and not operational_persistent_mode:
        reasons.append("non-proof execution requires operational persistent mode")
    if proof_mode and operational_persistent_mode:
        reasons.append("proof and operational persistent modes are mutually exclusive")
    if four_token_proof_controller is not None:
        if not standard_four_hour_campaign:
            reasons.append(
                "four-token proof controller requires standard four-hour campaign authority"
            )
        if later_cycle_discovery_callback is None:
            reasons.append(
                "four-token proof controller requires authoritative later-cycle discovery callback"
            )
        if four_token_health_projector is None:
            reasons.append(
                "four-token proof controller requires authoritative admission health projector"
            )
        if four_token_shared_terminalizer is None:
            reasons.append(
                "four-token proof controller requires authoritative shared terminal owner"
            )
        try:
            _resolve_acquisition_quantum_bound(
                later_cycle_acquisition_quantum_seconds
            )
        except (TypeError, ValueError):
            reasons.append("later-cycle acquisition quantum duration must be positive")
    elif later_cycle_discovery_callback is not None:
        reasons.append(
            "later-cycle discovery callback requires four-token proof controller"
        )
    elif four_token_health_projector is not None:
        reasons.append(
            "admission health projector requires four-token proof controller"
        )
    elif four_token_shared_terminalizer is not None:
        reasons.append(
            "shared terminal owner requires four-token proof controller"
        )
    if _post_handoff_fault is not None:
        if not proof_mode or operational_persistent_mode:
            reasons.append(
                "post-handoff fault injection requires disposable proof mode"
            )
        if _post_handoff_scope_recorder is None:
            reasons.append("post-handoff fault injection requires exact scope recorder")
    if window_kind != WINDOW_KIND: reasons.append(f"unsupported window_kind: {window_kind}")
    if not path.is_file(): reasons.append(f"proof DB missing: {path}")
    if not backup.is_file(): reasons.append(f"backup missing: {backup}")
    if operational_persistent_mode:
        from printer_v1.operator_cli.proof_db_schema_readiness import (
            CANONICAL_PERSISTENT_DB,
        )
        from printer_v1.operator_cli.operational_database_target_binding import (
            DISPOSABLE_PUBLIC_COMPOSITION_PROOF_EXPECTATION_VERSION,
            build_disposable_public_composition_proof_expectation,
            load_durable_operational_database_target_expectation,
            validate_bound_operational_invocation,
            validate_disposable_public_composition_proof_invocation,
        )
        from printer_v1.db.migrate import (
            canonical_migration_count,
            canonical_migration_names,
        )
        canonical = Path(CANONICAL_PERSISTENT_DB).resolve()
        ownership_ready = all(
            (campaign_id, campaign_run_id, cycle_id, configuration_id)
        )
        durable_loaded = (
            load_durable_operational_database_target_expectation(
                path,
                campaign_id=str(campaign_id or ""),
                campaign_run_id=str(campaign_run_id or ""),
                cycle_id=str(cycle_id or ""),
                configuration_id=str(configuration_id or ""),
            )
            if ownership_ready
            else None
        )
        if operational_database_target_binding is not None:
            # Production binding has precedence and keeps existing law.
            binding_reason = validate_bound_operational_invocation(
                operational_database_target_binding,
                actual_db_path=path,
                canonical_authoritative_db_path=canonical,
                migration_count=canonical_migration_count(),
                migration_head=canonical_migration_names()[-1],
                campaign_id=campaign_id,
                campaign_run_id=campaign_run_id,
                cycle_id=cycle_id,
                configuration_id=configuration_id,
                durable_expectation=durable_loaded,
            )
            if binding_reason is not None:
                reasons.append(binding_reason)
        elif disposable_public_composition_proof_binding is not None:
            # Sole non-corpus alternative: already-owned C8 disposable binding.
            if (
                isinstance(durable_loaded, dict)
                and durable_loaded.get("expectation_version")
                == DISPOSABLE_PUBLIC_COMPOSITION_PROOF_EXPECTATION_VERSION
            ):
                disposable_expectation = durable_loaded
            else:
                disposable_expectation = (
                    build_disposable_public_composition_proof_expectation(
                        disposable_public_composition_proof_binding
                    )
                )
            disposable_reason = validate_disposable_public_composition_proof_invocation(
                disposable_public_composition_proof_binding,
                expectation=disposable_expectation,
                actual_db_path=path,
                canonical_authoritative_db_path=canonical,
                execution_id=str(
                    getattr(
                        disposable_public_composition_proof_binding,
                        "execution_id",
                        "",
                    )
                    or ""
                ),
                campaign_id=str(campaign_id or ""),
                campaign_run_id=str(campaign_run_id or ""),
                cycle_id=str(cycle_id or ""),
                configuration_id=str(configuration_id or ""),
                durable_db_target_identity=str(
                    getattr(
                        disposable_public_composition_proof_binding,
                        "db_target_identity",
                        "",
                    )
                    or ""
                ),
                fixture_composition_manifest_sha256=str(
                    getattr(
                        disposable_public_composition_proof_binding,
                        "fixture_composition_manifest_sha256",
                        "",
                    )
                    or ""
                ),
            )
            if disposable_reason is not None:
                reasons.append(disposable_reason)
        else:
            if path != canonical:
                reasons.append(
                    "operational persistent mode requires the authoritative corpus"
                )
            binding_reason = validate_bound_operational_invocation(
                None,
                actual_db_path=path,
                canonical_authoritative_db_path=canonical,
                migration_count=canonical_migration_count(),
                migration_head=canonical_migration_names()[-1],
                campaign_id=campaign_id,
                campaign_run_id=campaign_run_id,
                cycle_id=cycle_id,
                configuration_id=configuration_id,
                durable_expectation=durable_loaded,
            )
            if binding_reason is not None:
                reasons.append(binding_reason)
    elif _is_persistent_db(path):
        reasons.append("persistent DB is forbidden in proof mode")
    # V2-5: the explicit three-token proof mode permits exactly three autonomous
    # tokens. Normal mode stays capped at two. Four or more is always rejected.
    if compressed_two_token_proof_plan is not None and not continuous_first_hour:
        reasons.append("compressed two-token proof requires continuous first-hour mode")
    if standard_four_hour_campaign:
        if proof_mode:
            reasons.append("standard four-hour campaign requires operational persistent mode")
        if not operational_persistent_mode:
            reasons.append("standard four-hour campaign requires operational persistent mode")
        if four_hour_proof_mode:
            reasons.append("standard four-hour campaign cannot use four_hour_proof_mode")
        if compressed_two_token_proof_plan is not None or operational_natural_disposition:
            reasons.append("standard four-hour campaign excludes historical proof dispositions")
        if max_selected_tokens != 2:
            reasons.append("standard four-hour campaign requires exactly two token slots")
        if not selective_1h_continuation:
            reasons.append("standard four-hour campaign requires standard first-hour continuation")
        if not continuous_four_hour:
            reasons.append("standard four-hour campaign requires continuous_four_hour")
        if not all((campaign_id, campaign_run_id, cycle_id, configuration_id)):
            reasons.append("standard four-hour campaign requires exact campaign ownership identities")
    # V2-9.7E.11: operational-natural two-token mode and the E.9 compressed proof
    # plan are structurally mutually exclusive (predeclared dispositions can never
    # enter operational mode).
    if operational_natural_disposition and compressed_two_token_proof_plan is not None:
        reasons.append(
            "operational natural mode excludes the compressed two-token proof plan"
        )
    if (
        operational_natural_disposition
        and not continuous_first_hour
        and not operational_persistent_mode
    ):
        reasons.append(
            "operational natural 15m-only mode requires operational persistent mode"
        )
    if continuous_first_hour:
        if standard_four_hour_campaign:
            # The dedicated standard campaign checks above own the exact
            # persistent two-token production shape. Do not reinterpret it
            # as any historical compressed/natural/one-token proof mode.
            pass
        elif compressed_two_token_proof_plan is not None:
            try:
                compressed_two_token_proof_plan.validate_shape()
            except ValueError as exc:
                reasons.append(str(exc))
            if max_selected_tokens != 2:
                reasons.append("compressed two-token continuous proof requires exactly two tokens")
            if discovery_runner is None:
                reasons.append("compressed two-token proof requires injected origin discovery")
            if not continuous_four_hour or not four_hour_proof_mode:
                reasons.append("compressed two-token proof requires terminal 4h proof mode")
        elif operational_natural_disposition:
            if max_selected_tokens != 2:
                reasons.append("operational natural two-token mode requires exactly two tokens")
            if discovery_runner is None:
                reasons.append("operational natural mode requires injected origin discovery")
            if not continuous_four_hour or not four_hour_proof_mode:
                reasons.append("operational natural two-token mode requires terminal 4h proof mode")
        elif max_selected_tokens != _CONTINUOUS_MAX_SELECTED_TOKENS:
            reasons.append("continuous first-hour proof requires exactly one autonomous token")
        if v2_5_proof_mode:
            reasons.append("continuous first-hour proof cannot use V2-5 three-token mode")
    elif v2_5_proof_mode:
        if max_selected_tokens != _V2_5_MAX_SELECTED_TOKENS:
            reasons.append("V2-5 proof mode requires exactly three selected tokens")
    else:
        if not 1 <= max_selected_tokens <= 2:
            reasons.append("max_selected_tokens must be 1 or 2 outside V2-5 proof mode")
    if not 1 <= max_source_requests <= _MAX_DISCOVERY_REQUESTS: reasons.append("max_source_requests must be 1 or 2")
    if continuous_four_hour and not continuous_first_hour:
        reasons.append("4h continuation requires the same-run continuous first-hour path")
    if continuous_four_hour and not four_hour_proof_mode and not standard_four_hour_campaign:
        reasons.append("WINDOW_4H collection requires explicit proof or standard campaign authority")
    if selective_1h_continuation:
        if (continuous_four_hour or four_hour_proof_mode) and not standard_four_hour_campaign:
            reasons.append(
                "selective 1h continuation cannot enable 4h without standard campaign authority"
            )
        if not campaign_id or not campaign_run_id or not cycle_id:
            reasons.append(
                "selective 1h continuation requires campaign_id, campaign_run_id, and cycle_id"
            )
        if max_selected_tokens != 2:
            reasons.append("selective 1h continuation requires exactly two token slots")
        # Selective 1h reuses the continuous first-hour collection machinery for
        # CONTINUE tokens only; it does not unlock production by default.
        if not continuous_first_hour and not operational_persistent_mode:
            reasons.append(
                "selective 1h requires continuous_first_hour proof path or operational persistent mode"
            )
    if supervision_execution_id:
        try:
            from printer_v1.operator_cli.proof_supervision import inspect_execution
            supervision = inspect_execution(path, supervision_execution_id)
            if Path(str(supervision["proof_db_path"])).resolve() != path:
                reasons.append("supervision execution targets a different proof DB")
            if supervision["execution_status"] not in {"STARTING", "RUNNING"}:
                reasons.append("supervision execution is not active")
        except Exception as exc:
            reasons.append(f"supervision preflight failed: {type(exc).__name__}: {exc}")
    selective_1h = bool(selective_1h_continuation)
    effective_continuous_1h = bool(continuous_first_hour or selective_1h)
    required_duration = (
        _window_seconds
        + (_continuation_seconds if effective_continuous_1h else 0.0)
        + (10_800.0 if continuous_four_hour else 0.0)
    )
    if total_duration_seconds <= required_duration:
        reasons.append("total duration must exceed the complete approved lifecycle duration")
    if reasons:
        return {"command": COMMAND_NAME, "run_status": "SAFE_STOPPED", "stop_reason": STOP_PREFLIGHT, "blocked_reasons": reasons}

    from printer_v1.operator_cli.commands import build_discover_candidates_once_payload
    from printer_v1.operator_cli.e2i_source_transport import build_e2i_dexscreener_adapter

    discovery_callable = discovery_runner or build_discover_candidates_once_payload
    adapter_factory = snapshot_adapter_factory or build_e2i_dexscreener_adapter
    # V2-9.5: one governed GeckoTerminal exact-pair fallback, attempted at most
    # once after an eligible transient DexScreener transport failure. The real
    # builder is the default so live runs get redundancy; tests inject a fixture.
    from printer_v1.operator_cli.exact_pair_source_redundancy import (
        build_default_geckoterminal_fallback_adapter,
    )
    fallback_factory = (
        fallback_snapshot_adapter_factory or build_default_geckoterminal_fallback_adapter
    )
    config = {
        "db_mode": (
            "OPERATIONAL_PERSISTENT"
            if operational_persistent_mode else "PROOF_ONLY"
        ),
        "db_path": str(path), "backup_path": str(backup),
        "window_kind": window_kind, "max_selected_tokens": max_selected_tokens,
        "max_source_requests": max_source_requests, "timeout_seconds": timeout_seconds,
        "total_duration_seconds": total_duration_seconds, "window_seconds": _window_seconds,
        "automatic_retries": 0, "discovery_source": "geckoterminal",
        "context_source_requests_per_selected_token": 5,
        "context_source_request_budget": 5 * max_selected_tokens,
        "v2_5_proof_mode": bool(v2_5_proof_mode),
        # selective_1h reuses continuous 1h collection machinery for CONTINUE
        # tokens only; production public command never sets selective_1h.
        "continuous_first_hour": bool(effective_continuous_1h),
        "continuous_four_hour": bool(continuous_four_hour),
        "four_hour_proof_mode": bool(four_hour_proof_mode),
        "standard_four_hour_campaign": bool(standard_four_hour_campaign),
        "four_token_proof": bool(four_token_proof_controller is not None),
        "compressed_two_token_proof_plan": (
            asdict(compressed_two_token_proof_plan)
            if compressed_two_token_proof_plan is not None else None
        ),
        "operational_natural_disposition": bool(operational_natural_disposition),
        "operational_persistent_mode": bool(operational_persistent_mode),
        "supervision_execution_id": supervision_execution_id,
        # V2-9.7E.47 A2/A3: the campaign ownership identities the discovery work
        # rows carry, so terminal cleanup and active-work accounting can scope
        # every attributable Scheduler job without guessing a batch id.
        "campaign_id": campaign_id,
        "campaign_run_id": campaign_run_id,
        "cycle_id": cycle_id,
        "configuration_id": configuration_id,
        "selective_1h_continuation": bool(selective_1h),
        "git_provenance": provenance,
        "continuation_seconds": (
            _continuation_seconds if effective_continuous_1h else 0.0
        ),
        "hard_ceilings": {
            "discovery_requests": _MAX_DISCOVERY_REQUESTS,
            "governed_requests_run": _MAX_GOVERNED_REQUESTS_RUN,
            "governed_requests_per_token": _MAX_GOVERNED_REQUESTS_PER_TOKEN,
            "holder_fallbacks_per_token": _MAX_HOLDER_RPC_REQUESTS_PER_TOKEN,
            "scheduler_rows": _MAX_SCHEDULER_ROWS,
            "total_duration_seconds": total_duration_seconds,
            "automatic_retries": 0,
            "continuous_governed_requests_run": _CONTINUOUS_MAX_REQUESTS_RUN,
            "continuous_governed_requests_per_token": _CONTINUOUS_MAX_REQUESTS_PER_TOKEN,
            "continuous_scheduler_rows": _CONTINUOUS_MAX_SCHEDULER_ROWS,
            "selective_1h_governed_requests_run": (
                _SELECTIVE_1H_MAX_REQUESTS_RUN
            ),
            "selective_1h_governed_requests_per_token": (
                _SELECTIVE_1H_MAX_REQUESTS_PER_TOKEN
            ),
            "selective_1h_scheduler_rows": _SELECTIVE_1H_MAX_SCHEDULER_ROWS,
            "compressed_two_token_governed_requests_run": (
                _COMPRESSED_TWO_TOKEN_MAX_REQUESTS_RUN
            ),
            "compressed_two_token_scheduler_rows": (
                _COMPRESSED_TWO_TOKEN_MAX_SCHEDULER_ROWS
            ),
        },
    }
    run_id = str(factory_run_id or uuid.uuid4()).strip()
    if not run_id:
        raise ValueError("factory_run_id must be non-empty")
    started_dt = _now()
    started_at = _iso(started_dt)
    conn = sqlite3.connect(str(path))
    conn.row_factory = sqlite3.Row
    # V2-9.8B.10: factory-run insert sits outside the later lifecycle try/finally.
    # Close the connection on any pre-lifecycle fault so terminal cleanup cannot
    # contend with a leaked write handle (secondary cause of database is locked).
    try:
        conn.execute("PRAGMA foreign_keys=ON")
        conn.execute("PRAGMA busy_timeout=5000")
        _require_schema(conn)
        before = _counts(conn)
        conn.execute(
            "INSERT INTO printer_memory_factory_runs (run_id,run_status,window_kind,db_mode,config_hash,config_json,started_at,created_at,updated_at) VALUES (?,'RUNNING',?,?,?,?,?,?,?)",
            (
                run_id,
                window_kind,
                config["db_mode"],
                _config_hash(config),
                _json(config),
                started_at,
                started_at,
                started_at,
            ),
        )
        conn.commit()
    except BaseException:
        try:
            conn.close()
        except Exception:
            pass
        raise
    if supervision_execution_id:
        from printer_v1.operator_cli.proof_supervision import attach_run
        attach_run(
            path, supervision_execution_id, run_id, process_id=os.getpid(),
        )
    discovery: dict[str, Any] = {}
    stop_reason = STOP_COMPLETED
    start_mono = _monotonic()
    first_snapshot_checkpointed = False
    first_window_checkpointed = False
    post_activation_checkpointed = False
    proof_fault: BaseException | None = None
    progression_secondary_stop_fact: str | None = None
    progression_primary_write_failed_cycles: set[str] = set()
    governed_observer_token = None
    four_token_attempt_terminal_cause: str | None = None
    four_token_cycle_one_opening_completed = False
    if lifecycle_operation_observer is not None:
        from printer_v1.sources.governed_execution import (
            set_governed_attempt_observer,
        )

        def _observe_governed_attempt(record: Mapping[str, Any]) -> None:
            request_key = str(record.get("request_key") or "")
            prefix = f"{run_id}:"
            if not request_key.startswith(prefix):
                return
            step_key = request_key[len(prefix):].split(":", 1)[0]
            step_row = conn.execute(
                """SELECT step_key,step_kind,scheduler_job_id,token_id,pair_id
                   FROM printer_memory_factory_run_steps
                   WHERE run_id=? AND step_key=?""",
                (run_id, step_key),
            ).fetchone()
            if step_row is None:
                raise ValueError(
                    f"GOVERNED_ATTEMPT_WITHOUT_FACTORY_STEP:{request_key}"
                )
            attempt_count = int(
                conn.execute(
                    """SELECT COUNT(*) FROM printer_source_requests
                       WHERE request_key LIKE ? AND id<=?""",
                    (
                        f"{run_id}:{step_key}%",
                        int(record["source_request_id"]),
                    ),
                ).fetchone()[0]
            )
            lifecycle_operation_observer(
                {
                    **dict(record),
                    **_lifecycle_operation_cycle_identity(
                        conn, int(step_row["scheduler_job_id"])
                    ),
                    "run_id": run_id,
                    "step_key": str(step_row["step_key"]),
                    "step_kind": str(step_row["step_kind"]),
                    "scheduler_job_id": int(step_row["scheduler_job_id"]),
                    "token_id": int(step_row["token_id"]),
                    "pair_id": int(step_row["pair_id"]),
                    "attempt_ordinal": attempt_count,
                    "reserved_from": (
                        f"{run_id}:{step_key}:reservation:{attempt_count}"
                    ),
                }
            )

        governed_observer_token = set_governed_attempt_observer(
            _observe_governed_attempt
        )
    try:
        if factory_run_initialized is not None:
            factory_run_initialized(run_id)
        # V2-9.8B full-run ownership context: the factory may read the immutable
        # ownership context but must not replace any identity. If a non-empty
        # bound factory run id disagrees with this factory's run id, fail closed
        # before any lifecycle work (identity drift).
        if lifecycle_ownership_context is not None:
            required_context = {
                "campaign_id": campaign_id,
                "campaign_run_id": campaign_run_id,
                "cycle_id": cycle_id,
                "configuration_id": configuration_id,
                "factory_run_id": run_id,
                "expected_window_kind": window_kind,
                "expected_token_capacity": max_selected_tokens,
            }
            missing = [
                key
                for key, expected in required_context.items()
                if expected is None
                or str(lifecycle_ownership_context.get(key) or "").strip()
                == ""
            ]
            if missing:
                raise ValueError(
                    "INCOMPLETE_LIFECYCLE_OWNERSHIP_CONTEXT:"
                    + ",".join(sorted(missing))
                )
            drift = [
                key
                for key, expected in required_context.items()
                if str(lifecycle_ownership_context.get(key)) != str(expected)
            ]
            if drift:
                raise ValueError(
                    "LIFECYCLE_OWNERSHIP_CONTEXT_DRIFT:"
                    + ",".join(sorted(drift))
                )
        # One-shot campaign → factory authoritative linkage when campaign
        # ownership identities are present (V2-9.8B selective 1h readiness).
        if campaign_run_id:
            from printer_v1.operator_cli.operational_selective_1h import (
                ensure_authoritative_factory_link,
            )
            ensure_authoritative_factory_link(
                conn,
                campaign_run_id=str(campaign_run_id),
                factory_run_id=run_id,
            )
            conn.commit()
        _emit_supervision_event(
            bool(supervision_execution_id), "RUN_START", run_id=run_id
        )
        _check_cancellation(cancellation_probe)
        args = _build_discovery_args(
            path, max_selected_tokens=max_selected_tokens,
            max_source_requests=max_source_requests, timeout_seconds=timeout_seconds,
            selection_seed=selection_seed,
        )
        if discovery_runner is None:
            discovery = discovery_callable(args, transport=discovery_transport)
        else:
            discovery = discovery_callable(args)
        handoff = discovery.get("selection_handoff_report", {})
        batch_id = handoff.get("batch_id")
        targets = _selected_targets(conn, str(batch_id or ""))
        if compressed_two_token_proof_plan is not None:
            compressed_two_token_proof_plan.validate_targets(targets)
            origin_projection_count = int(conn.execute(
                """SELECT COUNT(*) FROM printer_selection_batch_items
                   WHERE batch_id=? AND item_status='SELECTED'
                     AND selection_reason='origin_confirmed_atomic_activation'
                     AND source_name='solana_rpc'""",
                (str(batch_id or ""),),
            ).fetchone()[0])
            if origin_projection_count != 2:
                raise ValueError(
                    "two-token proof targets must be exact origin-activated projections"
                )
        conn.execute(
            "UPDATE printer_memory_factory_runs SET selection_seed=?,selection_batch_id=?,eligible_pool_size=?,selected_token_count=?,updated_at=? WHERE run_id=?",
            (handoff.get("selection_seed"), batch_id, handoff.get("eligible_pool_size", 0), len(targets), _iso(), run_id),
        )
        _cancel_discovery_handoffs(conn, discovery)
        if not targets:
            stop_reason = STOP_EMPTY
        else:
            def _first_opening_commit(
                checkpoint_conn: sqlite3.Connection, checkpoint_run_id: str
            ) -> None:
                if _post_handoff_scope_recorder is not None:
                    _post_handoff_scope_recorder.checkpoint(
                        checkpoint_conn,
                        checkpoint_run_id,
                        "AFTER_FIRST_RUN_STEP_AND_SCHEDULER_COMMIT",
                    )

            planning_targets = targets
            if four_token_proof_controller is not None:
                if campaign_id is None or campaign_run_id is None or cycle_id is None:
                    raise ValueError(
                        "four-token Cycle-1 planning requires campaign/run/cycle identity"
                    )
                from printer_v1.operator_cli.cadence_authority import (
                    require_cycle_slot_tracking_authorities,
                )

                # Same Cycle-N authority gate as Cycle 2 / later: exact
                # slot→queue→lane must already be insert-bound before opening.
                require_cycle_slot_tracking_authorities(
                    conn,
                    campaign_id=str(campaign_id),
                    run_id=str(campaign_run_id),
                    cycle_id=str(cycle_id),
                    now=_now(),
                )
                planning_targets = _cycle_targets_for_factory(
                    conn,
                    campaign_id=str(campaign_id),
                    campaign_run_id=str(campaign_run_id),
                    cycle_id=str(cycle_id),
                )
            _plan_opening_jobs(
                conn,
                run_id,
                planning_targets,
                _now(),
                operation_observer=lifecycle_operation_observer,
                first_commit_callback=(
                    _first_opening_commit
                    if _post_handoff_scope_recorder is not None
                    else None
                ),
                cycle_ordinal=1,
                four_token_proof=bool(four_token_proof_controller is not None),
            )
            if four_token_proof_controller is not None:
                four_token_cycle_one_opening_completed = True
        conn.commit()

        admission_attempt_finished = False
        proof_deadline = min(
            started_dt
            + timedelta(seconds=float(four_token_proof_controller.policy.intake_duration_seconds)),
            started_dt + timedelta(seconds=float(total_duration_seconds)),
        ) if four_token_proof_controller is not None else None

        while stop_reason == STOP_COMPLETED:
            _check_cancellation(cancellation_probe)
            pending = _select_next_pending_step(
                conn, run_id=run_id, now=_now()
            )
            elapsed = _monotonic() - start_mono
            if elapsed >= total_duration_seconds:
                stop_reason = STOP_DURATION
                break
            if (
                four_token_proof_controller is not None
                and not admission_attempt_finished
            ):
                from printer_v1.discovery.pre_admission_materialization import (
                    materialize_consumed_pre_admission_pair,
                )
                from printer_v1.operator_cli.four_token_proof_integration import (
                    FourTokenAdmissionDispositionKind,
                    decide_four_token_admission_disposition,
                )
                from printer_v1.operator_cli.multi_cycle_campaign_coordinator import (
                    MultiCycleCampaignBinding,
                    admit_two_token_cycle_from_attempt,
                )

                binding = MultiCycleCampaignBinding(
                    campaign_id=str(campaign_id),
                    campaign_run_id=str(campaign_run_id),
                    configuration_id=str(configuration_id),
                    authoritative_factory_run_id=run_id,
                )
                cycle_count = int(conn.execute(
                    "SELECT COUNT(*) FROM printer_memory_factory_campaign_cycles "
                    "WHERE campaign_id=? AND run_id=?",
                    (str(campaign_id), str(campaign_run_id)),
                ).fetchone()[0])
                if cycle_count >= 2:
                    admission_attempt_finished = True
                else:
                    def _next_due() -> datetime | None:
                        row = _select_next_pending_step(
                            conn, run_id=run_id, now=_now()
                        )
                        return (
                            None
                            if row is None
                            else datetime.fromisoformat(str(row["scheduled_for"]))
                        )

                    def _project_health() -> Any:
                        if four_token_health_projector is None:
                            raise ValueError(
                                "authoritative four-token health projector missing"
                            )
                        return four_token_health_projector(conn, _now())

                    def _evaluate(projection: Any) -> Any:
                        instant = _now()
                        due_at = _next_due()
                        readiness = four_token_proof_controller.evaluate_factory_wake(
                            conn,
                            binding=binding,
                            now=instant,
                            next_due_work_at=due_at,
                            proof_deadline=proof_deadline,
                            admission_health=projection.health,
                        )
                        return decide_four_token_admission_disposition(
                            readiness=readiness,
                            health_projection=projection,
                            policy=four_token_proof_controller.policy,
                            now=instant,
                            next_due_work_at=due_at,
                            proof_deadline=proof_deadline,
                            relevant_pending_lifecycle_work=due_at is not None,
                        )

                    def _plan_second_cycle(
                        *, cycle_id: str, cycle_ordinal: int, now: datetime
                    ) -> None:
                        cycle_targets = _cycle_targets_for_factory(
                            conn,
                            campaign_id=str(campaign_id),
                            campaign_run_id=str(campaign_run_id),
                            cycle_id=cycle_id,
                        )
                        _plan_opening_jobs(
                            conn,
                            run_id,
                            cycle_targets,
                            now,
                            operation_observer=lifecycle_operation_observer,
                            cycle_ordinal=cycle_ordinal,
                            four_token_proof=True,
                        )
                        conn.commit()

                    boundary = _run_four_token_admission_boundary(
                        connection=conn,
                        controller=four_token_proof_controller,
                        binding=binding,
                        first_cycle_id=str(cycle_id),
                        now=_now(),
                        next_due_work_at=_next_due(),
                        proof_deadline=proof_deadline,
                        project_health=_project_health,
                        evaluate=_evaluate,
                        later_cycle_callback=later_cycle_discovery_callback,
                        admit=admit_two_token_cycle_from_attempt,
                        materialize=materialize_consumed_pre_admission_pair,
                        plan_opening=_plan_second_cycle,
                        source_governor=source_governor_owner,
                        central_scheduler=central_scheduler_owner,
                        clock=_now,
                        acquisition_quantum_worst_case_seconds=(
                            later_cycle_acquisition_quantum_seconds
                        ),
                    )
                    kind = boundary.disposition.kind
                    if boundary.admitted:
                        admission_attempt_finished = True
                        continue
                    if _later_cycle_attempt_is_terminal(boundary.attempt_state):
                        # The one durable opportunity has run. PAIR_READY may
                        # remain frozen after post-discovery health changed; no
                        # retry/successor is permitted.
                        admission_attempt_finished = True
                        if boundary.attempt_terminal_cause is not None:
                            four_token_attempt_terminal_cause = (
                                boundary.attempt_terminal_cause
                            )
                    if kind is FourTokenAdmissionDispositionKind.PROOF_DEADLINE:
                        stop_reason = STOP_DURATION
                        break
                    if kind in {
                        FourTokenAdmissionDispositionKind.BLOCKED,
                        FourTokenAdmissionDispositionKind.DRAIN,
                    }:
                        stop_reason = STOP_PREFLIGHT
                        break
                    if kind is FourTokenAdmissionDispositionKind.COMPLETE:
                        admission_attempt_finished = True
                    if kind is FourTokenAdmissionDispositionKind.REARM:
                        at = boundary.disposition.at
                        if at is None:
                            stop_reason = STOP_PREFLIGHT
                            break
                        wait = max(0.0, (at - _now()).total_seconds())
                        if wait:
                            _sleep_with_cancellation(
                                min(
                                    wait,
                                    max(0.0, total_duration_seconds - elapsed),
                                ),
                                sleep=_sleep,
                                probe=cancellation_probe,
                            )
                        continue
                    # D4/D5: after a cooperative later-cycle quantum, re-evaluate
                    # before any stale pending-None terminal path or lifecycle sleep.
                    should_recheck, cooperative_wake_at = (
                        _cooperative_later_cycle_recheck(
                            boundary,
                            next_due_work_at=_next_due(),
                            proof_deadline=proof_deadline,
                        )
                    )
                    if should_recheck:
                        if cooperative_wake_at is not None:
                            wait = max(
                                0.0,
                                (cooperative_wake_at - _now()).total_seconds(),
                            )
                            if wait:
                                _sleep_with_cancellation(
                                    min(
                                        wait,
                                        max(
                                            0.0,
                                            total_duration_seconds - elapsed,
                                        ),
                                    ),
                                    sleep=_sleep,
                                    probe=cancellation_probe,
                                )
                        continue
            if pending is None:
                if four_token_attempt_terminal_cause is not None:
                    # The sole pre-admission attempt terminalized honestly.
                    # Preserve its exact cause only after all existing cycle-1
                    # lifecycle work has drained; it must never terminate that
                    # work early.
                    stop_reason = four_token_attempt_terminal_cause
                break
            due = datetime.fromisoformat(str(pending["scheduled_for"]))
            wait = max(0.0, (due - _now()).total_seconds())
            if wait:
                _sleep_with_cancellation(
                    min(wait, max(0.0, total_duration_seconds - elapsed)),
                    sleep=_sleep,
                    probe=cancellation_probe,
                )
                continue
            job_id = int(pending["scheduler_job_id"])
            claimed = claim_due_job(conn, job_id=job_id, lock_owner=f"v2_4:{run_id}")
            if claimed != LockResult.ACQUIRED:
                stop_reason = STOP_AMBIGUOUS
                break
            active_preclose_unit: str | None = None
            if str(pending["step_kind"]) in PRE_CLOSE_STEP_KINDS:
                active_preclose_unit = _bind_preclose_source_unit_for_claim(
                    conn, step_id=int(pending["id"])
                )
                pending = conn.execute(
                    "SELECT * FROM printer_memory_factory_run_steps WHERE id=?",
                    (int(pending["id"]),),
                ).fetchone()
                if pending is None:
                    raise ValueError("PRE_CLOSE_CLAIM_STEP_MISSING")
            effective_lifecycle_ownership_context = lifecycle_ownership_context
            owned_proof_cycle_id: str | None = None
            if four_token_proof_controller is not None:
                from printer_v1.operator_cli.four_token_proof_integration import (
                    resolve_owned_cycle_for_scheduler_job,
                )

                owned = resolve_owned_cycle_for_scheduler_job(
                    conn,
                    scheduler_job_id=job_id,
                    campaign_id=str(campaign_id),
                    campaign_run_id=str(campaign_run_id),
                    factory_run_id=run_id,
                )
                owned_proof_cycle_id = owned.cycle_id
                effective_lifecycle_ownership_context = {
                    "campaign_id": owned.campaign_id,
                    "campaign_run_id": owned.campaign_run_id,
                    "cycle_id": owned.cycle_id,
                    "configuration_id": str(configuration_id),
                    "factory_run_id": owned.factory_run_id,
                    "expected_window_kind": WINDOW_KIND,
                    "expected_token_capacity": 2,
                    "proof_cycle_owned": True,
                }
            conn.execute(
                "UPDATE printer_memory_factory_run_steps SET step_status='RUNNING',started_at=?,updated_at=? WHERE id=?",
                (_iso(), _iso(), int(pending["id"])),
            )
            _sync_owned_campaign_scheduler_job(
                conn, scheduler_job_id=job_id
            )
            _advance_owned_proof_15m_window(
                conn,
                scheduler_job_id=job_id,
                step_kind=str(pending["step_kind"]),
            )
            _mark_owned_continuation_window_collecting(
                conn,
                scheduler_job_id=job_id,
                step_kind=str(pending["step_kind"]),
            )
            _mark_owned_continuation_window_close_pending(
                conn,
                scheduler_job_id=job_id,
                step_kind=str(pending["step_kind"]),
            )
            _mark_owned_long_window_collecting(
                conn,
                scheduler_job_id=job_id,
                step_kind=str(pending["step_kind"]),
            )
            _mark_owned_long_window_close_pending(
                conn,
                scheduler_job_id=job_id,
                step_kind=str(pending["step_kind"]),
            )
            conn.commit()
            if lifecycle_operation_observer is not None:
                lifecycle_operation_observer(
                    {
                        **_lifecycle_operation_cycle_identity(conn, job_id),
                        "boundary": "SCHEDULER_CLAIM",
                        "run_id": run_id,
                        "scheduler_job_id": job_id,
                        "step_key": str(pending["step_key"]),
                        "step_kind": str(pending["step_kind"]),
                        "token_id": int(pending["token_id"]),
                        "pair_id": int(pending["pair_id"]),
                        "source_unit_identity": active_preclose_unit,
                    }
                )
            token_id = int(pending["token_id"])
            try:
                _emit_supervision_event(
                    bool(supervision_execution_id),
                    "CLOSE_START" if "CLOSE" in str(pending["step_kind"]) else "STEP_START",
                    run_id=run_id,
                    step_key=str(pending["step_key"]),
                    step_kind=str(pending["step_kind"]),
                )
                _check_cancellation(cancellation_probe)
                # Hard ceilings are integrity limits; a projected breach is a
                # global safe stop (raises _GlobalStop), never an exceeded call.
                projected_requests = _projected_requests_for_step(conn, pending)
                _enforce_budgets_before_step(
                    conn,
                    run_id,
                    pending,
                    projected_requests=projected_requests,
                )
                reservation_records = _lifecycle_reservation_records_for_step(
                    run_id=run_id,
                    pending=pending,
                    projected_requests=projected_requests,
                )
                operation_cycle_identity = _lifecycle_operation_cycle_identity(
                    conn, job_id
                )
                reservation_records = [
                    {**operation_cycle_identity, **record}
                    for record in reservation_records
                ]
                if lifecycle_operation_observer is not None:
                    for reservation_record in reservation_records:
                        lifecycle_operation_observer(reservation_record)
                if str(pending["step_kind"]) in PRE_CLOSE_STEP_KINDS:
                    result = _execute_preclose_critical_phase(
                        conn,
                        pending,
                        timeout_seconds=timeout_seconds,
                        context_adapter_factories=context_adapter_factories,
                        cancellation_probe=cancellation_probe,
                    )
                elif str(pending["step_kind"]) in EVIDENCE_STEP_KINDS:
                    result = _execute_close_evidence_phase(
                        conn,
                        pending,
                        adapter_factory=adapter_factory,
                        timeout_seconds=timeout_seconds,
                        fallback_adapter_factory=fallback_factory,
                    )
                elif str(pending["step_kind"]) in CONTEXT_STEP_KINDS:
                    result = _execute_close_context_phase(
                        conn,
                        pending,
                        timeout_seconds=timeout_seconds,
                        context_adapter_factories=context_adapter_factories,
                        cancellation_probe=cancellation_probe,
                    )
                elif str(pending["step_kind"]) in AUDIT_STEP_KINDS:
                    result = _execute_close_audit_phase(
                        conn,
                        pending,
                        minimum_evidence_seconds=_window_seconds,
                        execution_authority=(
                            "STANDARD_CAMPAIGN"
                            if standard_four_hour_campaign
                            else "PROOF"
                            if four_hour_proof_mode
                            else "DISABLED"
                        ),
                        cancellation_probe=cancellation_probe,
                    )
                elif pending["step_kind"] == "WINDOW_CLOSE":
                    result = _execute_close(
                        conn, pending, adapter_factory=adapter_factory,
                        timeout_seconds=timeout_seconds,
                        minimum_evidence_seconds=_window_seconds,
                        context_adapter_factories=context_adapter_factories,
                        fallback_adapter_factory=fallback_factory,
                        cancellation_probe=cancellation_probe,
                    )
                elif pending["step_kind"] == "CONTINUATION_CLOSE":
                    result = _execute_continuation_close(
                        conn,
                        pending,
                        adapter_factory=adapter_factory,
                        timeout_seconds=timeout_seconds,
                        context_adapter_factories=context_adapter_factories,
                        fallback_adapter_factory=fallback_factory,
                        cancellation_probe=cancellation_probe,
                    )
                elif str(pending["step_kind"]).startswith("LONG_CONTINUATION_"):
                    result = _execute_long_4h_step(
                        conn,
                        pending,
                        execution_authority=(
                            "STANDARD_CAMPAIGN"
                            if standard_four_hour_campaign
                            else "PROOF"
                            if four_hour_proof_mode
                            else "DISABLED"
                        ),
                        adapter_factory=adapter_factory,
                        timeout_seconds=timeout_seconds,
                        context_adapter_factories=context_adapter_factories,
                        fallback_adapter_factory=fallback_factory,
                        cancellation_probe=cancellation_probe,
                    )
                else:
                    _check_cancellation(cancellation_probe)
                    result = _execute_snapshot(
                        conn, pending, adapter_factory=adapter_factory,
                        timeout_seconds=timeout_seconds,
                        fallback_adapter_factory=fallback_factory,
                    )
                result["lifecycle_reservations"] = reservation_records
                validation_kinds = [
                    "IMMUTABLE_IDENTITY_VALIDATED",
                    "CADENCE_DUE_VALIDATED",
                    "BUDGET_CAPACITY_VALIDATED",
                ]
                if result.get("source_response_id") is not None:
                    validation_kinds.append("EXACT_PAIR_VERIFICATION")
                if str(pending["step_kind"]) in {
                    "WINDOW_CLOSE", "WINDOW_CLOSE_AUDIT"
                } and result.get("ok"):
                    validation_kinds.extend(
                        [
                            "WINDOW_CLOSE_VALIDATED",
                            "SNAPSHOT_COVERAGE_VALIDATED",
                            "WINDOW_QUALITY_VALIDATED",
                        ]
                    )
                validation_records = [
                    {
                        **operation_cycle_identity,
                        "boundary": "LOCAL_VALIDATION",
                        "run_id": run_id,
                        "scheduler_job_id": int(pending["scheduler_job_id"]),
                        "step_key": str(pending["step_key"]),
                        "step_kind": str(pending["step_kind"]),
                        "token_id": int(pending["token_id"]),
                        "pair_id": int(pending["pair_id"]),
                        "subject_identity": str(pending["step_key"]),
                        "validation_kind": validation_kind,
                        "validation_ordinal": (
                            int(pending["scheduler_job_id"]) * 1000 + index
                        ),
                    }
                    for index, validation_kind in enumerate(
                        validation_kinds, start=1
                    )
                ]
                result["local_validations"] = validation_records
                if lifecycle_operation_observer is not None:
                    for validation_record in validation_records:
                        lifecycle_operation_observer(validation_record)
                if (
                    str(pending["step_kind"]) in PRE_CLOSE_STEP_KINDS
                    and result.get("yield_required") is True
                ):
                    _checkpoint_and_yield_preclose_claim(
                        conn,
                        step=pending,
                        result=result,
                        now=_now(),
                    )
                    if lifecycle_operation_observer is not None:
                        lifecycle_operation_observer(
                            {
                                "boundary": "SCHEDULER_YIELD",
                                "run_id": run_id,
                                "scheduler_job_id": job_id,
                                "step_key": str(pending["step_key"]),
                                "step_kind": str(pending["step_kind"]),
                                "token_id": int(pending["token_id"]),
                                "pair_id": int(pending["pair_id"]),
                                "source_unit_identity": result.get(
                                    "last_claim_source_unit_identity"
                                ),
                            }
                        )
                    continue
                if (
                    str(pending["step_kind"]) in PRE_CLOSE_STEP_KINDS
                    and result.get("terminal_job_status") == "SKIPPED"
                ):
                    reason = str(
                        result.get("blocked_reason")
                        or "TIMELY_ACQUISITION_NOT_PRODUCIBLE"
                    )
                    _update_step(
                        conn,
                        int(pending["id"]),
                        "SKIPPED",
                        result,
                        error=reason,
                    )
                    skip_job(conn, job_id=job_id, reason=reason)
                    _sync_owned_campaign_scheduler_job(
                        conn, scheduler_job_id=job_id
                    )
                    _observe_scheduler_terminal(
                        conn,
                        observer=lifecycle_operation_observer,
                        run_id=run_id,
                        step=pending,
                    )
                    conn.commit()
                    continue
                if (
                    _post_handoff_scope_recorder is not None
                    and result.get("snapshot_id") is not None
                    and not first_snapshot_checkpointed
                ):
                    conn.commit()
                    _post_handoff_scope_recorder.record_token_snapshot(
                        int(result["snapshot_id"])
                    )
                    _post_handoff_scope_recorder.checkpoint(
                        conn,
                        run_id,
                        "AFTER_FIRST_TOKEN_SNAPSHOT_COMMIT",
                    )
                    first_snapshot_checkpointed = True
                if (
                    _post_handoff_scope_recorder is not None
                    and str(pending["step_kind"]) in {
                        "WINDOW_CLOSE", "WINDOW_CLOSE_AUDIT"
                    }
                    and result.get("memory_window_id") is not None
                    and not first_window_checkpointed
                ):
                    conn.commit()
                    _post_handoff_scope_recorder.checkpoint(
                        conn,
                        run_id,
                        "AFTER_FIRST_LIFECYCLE_WINDOW_COMMIT",
                    )
                    first_window_checkpointed = True
                _check_cancellation(cancellation_probe)
                if result.get("ok"):
                    if pending["step_kind"] == "SNAPSHOT" and _operational_natural(config):
                        result["support_5m_event_time"] = (
                            _evaluate_event_time_5m_support_for_snapshot(
                                conn, run_id=run_id, step=pending, result=result
                            )
                        )
                    if pending["step_kind"] == "SNAPSHOT" and str(pending["step_key"]).endswith("_snapshot_00"):
                        captured = conn.execute(
                            "SELECT captured_at FROM printer_token_snapshots WHERE id=?",
                            (int(result["snapshot_id"]),),
                        ).fetchone()
                        if captured is None:
                            raise ValueError("opening snapshot was not persisted")
                        _plan_anchored_jobs(
                            conn,
                            run_id=run_id,
                            opening_step=pending,
                            first_snapshot_captured_at=str(captured[0]),
                            window_seconds=_window_seconds,
                            operation_observer=lifecycle_operation_observer,
                        )
                    elif str(pending["step_kind"]) in {
                        "WINDOW_CLOSE", "WINDOW_CLOSE_AUDIT"
                    } and effective_continuous_1h:
                        window_id = result.get("memory_window_id")
                        if window_id is None:
                            raise ValueError("current-run 15m close did not attach a memory window")
                        # Make the exact current close discoverable while it is still
                        # RUNNING. It is promoted to SUCCEEDED only after support and
                        # continuation planning complete.
                        conn.execute(
                            """UPDATE printer_memory_factory_run_steps
                               SET snapshot_id=?, memory_window_id=?, result_json=?, updated_at=?
                               WHERE id=? AND step_status='RUNNING'""",
                            (
                                result.get("snapshot_id"), int(window_id), _json(result),
                                _iso(), int(pending["id"]),
                            ),
                        )
                        conn.commit()
                        proof_plan = _compressed_two_token_plan(config)
                        natural_mode = _operational_natural(config)
                        selective_mode = bool(config.get("selective_1h_continuation"))
                        if selective_mode:
                            # Selective campaign evaluation is owned only by the
                            # post-SUCCEEDED barrier below. A RUNNING close can
                            # attach lineage here but cannot become evaluation
                            # evidence or schedule continuation.
                            deferred_reason = "AWAITING_AUTHORITATIVE_CAMPAIGN_EVALUATION"
                            result["support_5m"] = {
                                "captured": False,
                                "verdict": "DEFERRED_PENDING_AUTHORITATIVE_CLOSES",
                                "reason": deferred_reason,
                                "window_5m_id": None,
                            }
                            result["continuation_plan"] = {
                                "enqueue_ok": False,
                                "planned_jobs": 0,
                                "verdict": "DEFERRED_PENDING_AUTHORITATIVE_CLOSES",
                                "reason": deferred_reason,
                            }
                        elif natural_mode:
                            # V2-9.7E.11 two-terminal-15m-close barrier: the first
                            # terminal 15m close must not independently schedule
                            # continuation or support-only 5m capture. Only once
                            # every activated token has terminal 15m close evidence
                            # is each token evaluated from its own governed 15m
                            # window and the permitted continuation enqueued. The
                            # decisions are token-local, so they are identical
                            # regardless of close-arrival order.
                            expected = _operational_activated_token_count(
                                conn, run_id, cycle_id=owned_proof_cycle_id
                            )
                            closes = _operational_terminal_15m_closes(
                                conn,
                                run_id,
                                current_step_id=int(pending["id"]),
                                cycle_id=owned_proof_cycle_id,
                            )
                            if len(closes) < expected:
                                # First terminal close: defer, schedule nothing.
                                deferred_reason = "AWAITING_PEER_TERMINAL_15M_CLOSE"
                                result["support_5m"] = {
                                    "captured": False,
                                    "verdict": "DEFERRED_PENDING_PEER_15M_CLOSE",
                                    "reason": deferred_reason,
                                    "window_5m_id": None,
                                }
                                result["continuation_plan"] = {
                                    "enqueue_ok": False,
                                    "planned_jobs": 0,
                                    "verdict": "DEFERRED_PENDING_PEER_15M_CLOSE",
                                    "reason": deferred_reason,
                                }
                            else:
                                # Barrier released: evaluate and schedule for every
                                # activated token from its own governed evidence.
                                for close_row in closes:
                                    row_window_id = int(
                                        close_row["memory_window_id"]
                                    )
                                    support = _materialize_frozen_5m_support(
                                        conn,
                                        run_id=run_id,
                                        close_step=close_row,
                                        parent_window_id=row_window_id,
                                    )
                                    _, continuation_plan = (
                                        _natural_disposition_schedule(
                                            conn,
                                            run_id=run_id,
                                            close_step=close_row,
                                            window_id=row_window_id,
                                            continuation_seconds=_continuation_seconds,
                                        )
                                    )
                                    if int(close_row["id"]) == int(pending["id"]):
                                        result["support_5m"] = support
                                        result["continuation_plan"] = (
                                            continuation_plan
                                        )
                                    else:
                                        # Rewrite the earlier deferred close's
                                        # persisted result now that the barrier
                                        # has released.
                                        peer_result = json.loads(
                                            str(close_row["result_json"] or "{}")
                                        )
                                        peer_result["support_5m"] = support
                                        peer_result["continuation_plan"] = (
                                            continuation_plan
                                        )
                                        conn.execute(
                                            "UPDATE printer_memory_factory_run_steps "
                                            "SET result_json=?, updated_at=? "
                                            "WHERE id=?",
                                            (
                                                _json(peer_result),
                                                _iso(),
                                                int(close_row["id"]),
                                            ),
                                        )
                                conn.commit()
                        else:
                            should_continue = (
                                proof_plan is None
                                or str(pending["token_mint"])
                                == proof_plan["continuation_token_mint"]
                            )
                            if should_continue:
                                support = _capture_same_stream_5m_support(
                                    conn,
                                    run_id=run_id,
                                    close_step=pending,
                                    parent_window_id=int(window_id),
                                )
                                if support.get("window_5m_id") is None:
                                    raise ValueError(
                                        "same-stream 5m support capture blocked: "
                                        + "; ".join(support.get("blocked_reasons", []))
                                    )
                                if proof_plan is not None:
                                    support["trigger_family"] = proof_plan[
                                        "support_5m_trigger_family"
                                    ]
                                    support["proof_evidence"] = proof_plan[
                                        "continuation_evidence"
                                    ]
                                source = _resolve_current_run_15m_source(
                                    conn,
                                    run_id=run_id,
                                    token_id=int(pending["token_id"]),
                                    pair_id=int(pending["pair_id"]),
                                    tracking_lane=str(pending["tracking_lane"]),
                                    current_close_step_id=int(pending["id"]),
                                )
                                if not source.get("resolved"):
                                    raise ValueError(
                                        "current-run 15m continuation source blocked: "
                                        + "; ".join(source.get("reasons", []))
                                    )
                                continuation_plan = _plan_continuation_jobs(
                                    conn,
                                    run_id=run_id,
                                    close_step=pending,
                                    fifteen_m=source["window"],
                                    continuation_seconds=_continuation_seconds,
                                )
                                if not continuation_plan.get("enqueue_ok"):
                                    raise ValueError(
                                        "continuation planning blocked: "
                                        + "; ".join(continuation_plan.get("reasons", []))
                                    )
                            else:
                                if proof_plan is not None:
                                    no_continuation_reason = proof_plan[
                                        "non_continuation_evidence"
                                    ]
                                else:
                                    no_continuation_reason = "NO_UNRESOLVED_LEARNING_NEED"
                                support = {
                                    "captured": False,
                                    "verdict": "VALID_NO_CAPTURE",
                                    "reason": no_continuation_reason,
                                    "window_5m_id": None,
                                }
                                continuation_plan = {
                                    "enqueue_ok": False,
                                    "planned_jobs": 0,
                                    "verdict": "STOP_AFTER_15M",
                                    "reason": no_continuation_reason,
                                }
                            result["support_5m"] = support
                            result["continuation_plan"] = continuation_plan
                    elif (
                        str(pending["step_kind"]) in {
                            "CONTINUATION_CLOSE", "CONTINUATION_CLOSE_AUDIT"
                        }
                        and continuous_four_hour
                        and not standard_four_hour_campaign
                    ):
                        from printer_v1.operator_cli.one_token_4h_runtime import plan_current_run_4h
                        window_id = result.get("memory_window_id")
                        if window_id is None:
                            raise ValueError("current-run 1h close did not attach a memory window")
                        conn.execute(
                            "UPDATE printer_memory_factory_run_steps SET snapshot_id=?,memory_window_id=?,result_json=?,updated_at=? WHERE id=? AND step_status='RUNNING'",
                            (result.get("snapshot_id"), int(window_id), _json(result), _iso(), int(pending["id"])),
                        )
                        conn.commit()
                        plan = plan_current_run_4h(
                            conn,
                            run_id=run_id,
                            token_id=int(pending["token_id"]),
                            pair_id=int(pending["pair_id"]),
                            token_mint=str(pending["token_mint"]),
                            pair_address=str(pending["pair_address"]),
                            tracking_lane=str(pending["tracking_lane"]),
                            current_close_step_id=int(pending["id"]),
                            explicit_proof_mode=four_hour_proof_mode,
                            compressed_two_token_proof=_two_token_lifecycle(config),
                            cumulative_scheduler_ceiling=int(
                                _cumulative_lifecycle_budget_for_run(
                                    conn, run_id, str(pending["tracking_lane"]),
                                    continuing_token_mint=str(pending["token_mint"]),
                                )["scheduler_ceiling"]
                            ),
                        )
                        if not plan.get("planned"):
                            raise ValueError("4h planning blocked: " + "; ".join(plan.get("blocked_reasons", [])))
                        result["four_hour_plan"] = plan
                    _update_step(conn, int(pending["id"]), "SUCCEEDED", result)
                    result["campaign_window_registration"] = (
                        _register_repaired_campaign_window_before_terminalization(
                            conn,
                            step=pending,
                            result=result,
                            ownership_context=effective_lifecycle_ownership_context,
                        )
                    )
                    # Re-persist enriched close-step result_json (includes
                    # campaign_window_registration) before Scheduler terminalization.
                    # Registration remains inside the same open transaction; a
                    # registration fault still rolls back the SUCCEEDED update.
                    if result.get("campaign_window_registration") is not None:
                        _update_step(conn, int(pending["id"]), "SUCCEEDED", result)
                    if str(pending["step_kind"]) in {
                        "CONTINUATION_CLOSE", "CONTINUATION_CLOSE_AUDIT"
                    }:
                        memory_window_id = result.get("memory_window_id")
                        if memory_window_id is None:
                            raise ValueError(
                                "CONTINUATION_CLOSE_SUCCEEDED_WITHOUT_MEMORY_WINDOW"
                            )
                        result["campaign_window_1h_binding"] = (
                            _bind_owned_continuation_memory_window_at_close(
                                conn,
                                scheduler_job_id=job_id,
                                memory_window_row_id=int(memory_window_id),
                            )
                        )
                        _update_step(conn, int(pending["id"]), "SUCCEEDED", result)
                    elif str(pending["step_kind"]) in {
                        "LONG_CONTINUATION_CLOSE", "LONG_CONTINUATION_CLOSE_AUDIT"
                    }:
                        memory_window_id = result.get("memory_window_id")
                        if memory_window_id is None:
                            raise ValueError(
                                "LONG_CONTINUATION_CLOSE_SUCCEEDED_WITHOUT_MEMORY_WINDOW"
                            )
                        result["campaign_window_4h_binding"] = (
                            _bind_owned_long_memory_window_at_close(
                                conn,
                                scheduler_job_id=job_id,
                                memory_window_row_id=int(memory_window_id),
                                result=result,
                            )
                        )
                        _update_step(conn, int(pending["id"]), "SUCCEEDED", result)
                    complete_job(conn, job_id=job_id)
                    _sync_owned_campaign_scheduler_job(
                        conn, scheduler_job_id=job_id
                    )
                    _observe_scheduler_terminal(
                        conn,
                        observer=lifecycle_operation_observer,
                        run_id=run_id,
                        step=pending,
                    )
                    conn.commit()
                    if (
                        _post_handoff_scope_recorder is not None
                        and str(pending["step_kind"]) in {
                            "WINDOW_CLOSE", "WINDOW_CLOSE_AUDIT"
                        }
                        and not post_activation_checkpointed
                    ):
                        _post_handoff_scope_recorder.checkpoint(
                            conn,
                            run_id,
                            "AFTER_POST_ACTIVATION_15M_STATE_COMMIT",
                        )
                        post_activation_checkpointed = True
                    if (
                        str(pending["step_kind"]) in {
                            "WINDOW_CLOSE", "WINDOW_CLOSE_AUDIT"
                        }
                        and bool(config.get("selective_1h_continuation"))
                    ):
                        _run_selective_1h_campaign_barrier(
                            conn,
                            db_path=str(path),
                            run_id=run_id,
                            config=config,
                            continuation_seconds=_continuation_seconds,
                            cycle_id=owned_proof_cycle_id,
                        )
                else:
                    # V2-5 token-local terminal failure: isolate this token,
                    # cancel only its remaining pending jobs, continue others.
                    error = str(result.get("blocked_reason") or "governed step blocked")
                    _update_step(conn, int(pending["id"]), "FAILED", result, error=error)
                    fail_job(conn, job_id=job_id, error=error, max_retries=0)
                    _sync_owned_campaign_scheduler_job(
                        conn, scheduler_job_id=job_id
                    )
                    _observe_scheduler_terminal(
                        conn, observer=lifecycle_operation_observer,
                        run_id=run_id, step=pending,
                    )
                    _cancel_pending_for_token(conn, run_id, token_id, TOKEN_LOCAL_CANCELLED)
                    if str(pending["step_kind"]) in {
                        "CONTINUATION_SNAPSHOT", "CONTINUATION_CLOSE",
                        "CONTINUATION_CLOSE_EVIDENCE",
                        "CONTINUATION_CLOSE_CONTEXT",
                        "CONTINUATION_CLOSE_AUDIT",
                    }:
                        _terminalize_owned_continuation_window(
                            conn,
                            scheduler_job_id=job_id,
                            terminal_state="BLOCKED",
                            terminal_cause=error,
                        )
                    elif str(pending["step_kind"]).startswith("LONG_CONTINUATION_"):
                        _terminalize_owned_long_window(
                            conn,
                            scheduler_job_id=job_id,
                            terminal_state="BLOCKED",
                            terminal_cause=error,
                        )
                    conn.commit()
                    if (
                        _post_handoff_scope_recorder is not None
                        and str(pending["step_kind"]) in {
                            "WINDOW_CLOSE", "WINDOW_CLOSE_AUDIT"
                        }
                        and not post_activation_checkpointed
                    ):
                        _post_handoff_scope_recorder.checkpoint(
                            conn,
                            run_id,
                            "AFTER_POST_ACTIVATION_15M_STATE_COMMIT",
                        )
                        post_activation_checkpointed = True
            except _ExternalStop:
                raise
            except _GlobalStop as gstop:
                # Global integrity/budget breach cancels the entire run.
                stop_reason = gstop.reason
                _update_step(
                    conn, int(pending["id"]), "FAILED",
                    {
                        "ok": False,
                        "global_stop": gstop.reason,
                        "budget_scope": gstop.scope,
                        "budget_detail": gstop.detail,
                    },
                    error=gstop.reason,
                )
                fail_job(conn, job_id=job_id, error=gstop.reason, max_retries=0)
                _sync_owned_campaign_scheduler_job(
                    conn, scheduler_job_id=job_id
                )
                _observe_scheduler_terminal(
                    conn, observer=lifecycle_operation_observer,
                    run_id=run_id, step=pending,
                )
                conn.commit()
                if (
                    _post_handoff_scope_recorder is not None
                    and str(pending["step_kind"]) in {
                        "WINDOW_CLOSE", "WINDOW_CLOSE_AUDIT"
                    }
                    and not post_activation_checkpointed
                ):
                    _post_handoff_scope_recorder.checkpoint(
                        conn,
                        run_id,
                        "AFTER_POST_ACTIVATION_15M_STATE_COMMIT",
                    )
                    post_activation_checkpointed = True
            except Exception as exc:
                if getattr(exc, "post_handoff_proof_fault", False):
                    raise
                # Unexpected token-local failure: isolate this token, continue.
                result = {"ok": False, "exception": f"{type(exc).__name__}: {exc}"}
                _update_step(conn, int(pending["id"]), "FAILED", result, error=result["exception"])
                fail_job(conn, job_id=job_id, error=result["exception"], max_retries=0)
                _sync_owned_campaign_scheduler_job(
                    conn, scheduler_job_id=job_id
                )
                _observe_scheduler_terminal(
                    conn, observer=lifecycle_operation_observer,
                    run_id=run_id, step=pending,
                )
                _cancel_pending_for_token(conn, run_id, token_id, TOKEN_LOCAL_CANCELLED)
                if str(pending["step_kind"]) in {
                    "CONTINUATION_SNAPSHOT",
                    "CONTINUATION_CLOSE",
                    "CONTINUATION_CLOSE_EVIDENCE",
                    "CONTINUATION_CLOSE_CONTEXT",
                    "CONTINUATION_CLOSE_AUDIT",
                }:
                    _terminalize_owned_continuation_window(
                        conn,
                        scheduler_job_id=job_id,
                        terminal_state="BLOCKED",
                        terminal_cause=result["exception"],
                    )
                elif str(pending["step_kind"]).startswith("LONG_CONTINUATION_"):
                    _terminalize_owned_long_window(
                        conn,
                        scheduler_job_id=job_id,
                        terminal_state="BLOCKED",
                        terminal_cause=result["exception"],
                    )
                conn.commit()
                if (
                    _post_handoff_scope_recorder is not None
                    and str(pending["step_kind"]) in {
                        "WINDOW_CLOSE", "WINDOW_CLOSE_AUDIT"
                    }
                    and not post_activation_checkpointed
                ):
                    _post_handoff_scope_recorder.checkpoint(
                        conn,
                        run_id,
                        "AFTER_POST_ACTIVATION_15M_STATE_COMMIT",
                    )
                    post_activation_checkpointed = True
            # Post-1h progression deliberately executes outside the predecessor
            # step/job/work exception owner. Once those terminal surfaces commit,
            # a later progression fault can only belong to the durable progression
            # aggregate and cannot rewrite the predecessor.
            if (
                str(pending["step_kind"])
                in {"CONTINUATION_CLOSE", "CONTINUATION_CLOSE_AUDIT"}
                and standard_four_hour_campaign
            ):
                from printer_v1.operator_cli.operational_standard_4h import (
                    run_standard_four_hour_campaign_barrier,
                )

                def _progression_cancellation_reason() -> str | None:
                    external = (
                        None if cancellation_probe is None else cancellation_probe()
                    )
                    if external:
                        return str(external)
                    return None if stop_reason == STOP_COMPLETED else str(stop_reason)

                run_standard_four_hour_campaign_barrier(
                    conn,
                    db_path=str(path),
                    campaign_id=str(campaign_id),
                    configuration_id=str(configuration_id),
                    run_id=str(campaign_run_id),
                    cycle_id=str(
                        owned_proof_cycle_id
                        if four_token_proof_controller is not None
                        else cycle_id
                    ),
                    factory_run_id=str(run_id),
                    operational_db_binding=operational_database_target_binding,
                    canonical_authoritative_db_path=str(canonical),
                    cancellation_probe=_progression_cancellation_reason,
                )
    except _ExternalStop as external_stop:
        stop_reason = external_stop.reason
    except KeyboardInterrupt:
        stop_reason = STOP_INTERRUPTED
    except Exception as exc:
        if conn.in_transaction:
            conn.rollback()
        if getattr(exc, "post_handoff_proof_fault", False):
            proof_fault = exc
        else:
            progression_stop_cause = None
            if standard_four_hour_campaign and all(
                (campaign_id, campaign_run_id)
            ):
                progression_failure_cycle = str(
                    owned_proof_cycle_id
                    if four_token_proof_controller is not None
                    else cycle_id
                )
                progression_stop_cause = (
                    _durable_standard_4h_progression_stop_cause(
                        conn,
                        campaign_id=str(campaign_id),
                        campaign_run_id=str(campaign_run_id),
                        cycle_id=progression_failure_cycle,
                        exc=exc,
                    )
                )
                if progression_stop_cause is not None:
                    progression_secondary_stop_fact = STOP_PREFLIGHT
                elif isinstance(exc, sqlite3.Error):
                    progression_row = conn.execute(
                        """SELECT attempt_state,first_terminal_cause
                           FROM printer_memory_factory_standard_4h_progression_attempts
                           WHERE campaign_id=? AND campaign_run_id=?
                             AND cycle_id=?""",
                        (
                            str(campaign_id),
                            str(campaign_run_id),
                            progression_failure_cycle,
                        ),
                    ).fetchone()
                    if (
                        progression_row is not None
                        and progression_row[1] is None
                        and str(progression_row[0])
                        in {
                            "WAITING_FOR_PREDECESSORS",
                            "EVALUATING",
                            "ELIGIBILITY_COMPLETE",
                        }
                    ):
                        progression_primary_write_failed_cycles.add(
                            progression_failure_cycle
                        )
            stop_reason = progression_stop_cause or STOP_PREFLIGHT
            discovery = {
                **discovery,
                "orchestration_error": f"{type(exc).__name__}: {exc}",
            }
    finally:
        if governed_observer_token is not None:
            from printer_v1.sources.governed_execution import (
                reset_governed_attempt_observer,
            )
            reset_governed_attempt_observer(governed_observer_token)
        if proof_fault is not None:
            if _post_handoff_scope_recorder is not None:
                _post_handoff_scope_recorder.record_factory_rows(conn, run_id)
            conn.close()
            raise proof_fault
        _emit_supervision_event(
            bool(supervision_execution_id), "TERMINAL_CAUSE", reason=stop_reason,
        )
        if standard_four_hour_campaign and all((campaign_id, campaign_run_id)):
            from printer_v1.operator_cli.standard_4h_progression import (
                terminalize_stopped_standard_4h_progression,
            )

            progression_cycles = conn.execute(
                """SELECT cycle_id
                   FROM printer_memory_factory_standard_4h_progression_attempts
                   WHERE campaign_id=? AND campaign_run_id=?
                   ORDER BY cycle_id""",
                (str(campaign_id), str(campaign_run_id)),
            ).fetchall()
            for progression_cycle in progression_cycles:
                if str(progression_cycle[0]) in progression_primary_write_failed_cycles:
                    continue
                try:
                    with conn:
                        terminalize_stopped_standard_4h_progression(
                            conn,
                            campaign_id=str(campaign_id),
                            campaign_run_id=str(campaign_run_id),
                            cycle_id=str(progression_cycle[0]),
                            stop_cause=str(
                                progression_secondary_stop_fact or stop_reason
                            ),
                            now=_now(),
                        )
                except sqlite3.Error:
                    # Canonical progression persistence is the only fault owner.
                    # Preserve the prior row; read-side accounting derives review.
                    if conn.in_transaction:
                        conn.rollback()
        four_token_terminal: dict[str, Any] | None = None
        if four_token_proof_controller is not None:
            from printer_v1.operator_cli.four_token_factory_adapter import (
                finalize_four_token_shared_terminal,
                reconcile_four_token_cycle_terminal,
                resolve_peer_stop_origin_cycle_id,
            )

            admitted_cycles = conn.execute(
                "SELECT cycle_id,cycle_ordinal FROM printer_memory_factory_campaign_cycles "
                "WHERE campaign_id=? AND run_id=? ORDER BY cycle_ordinal",
                (str(campaign_id), str(campaign_run_id)),
            ).fetchall()
            if not admitted_cycles:
                raise ValueError("four-token terminal found no admitted cycle")
            if configuration_id is None:
                raise ValueError(
                    "four-token terminal requires exact configuration identity"
                )
            # The factory row is the real producer for a genuinely shared stop
            # cause. Preserve its first stop reason before any cycle consumer
            # evaluates a campaign-shared effect.
            conn.execute(
                "UPDATE printer_memory_factory_runs "
                "SET stop_reason=COALESCE(stop_reason,?),updated_at=? "
                "WHERE run_id=?",
                (str(stop_reason), _iso(), run_id),
            )
            conn.commit()
            admitted_cycle_ids = tuple(str(item[0]) for item in admitted_cycles)
            phase_a = []
            for admitted in admitted_cycles:
                admitted_cycle_id = str(admitted[0])
                peer_origin = resolve_peer_stop_origin_cycle_id(
                    conn,
                    campaign_id=str(campaign_id),
                    campaign_run_id=str(campaign_run_id),
                    configuration_id=str(configuration_id),
                    factory_run_id=run_id,
                    target_cycle_id=admitted_cycle_id,
                    admitted_cycle_ids=admitted_cycle_ids,
                )
                phase_a.append(
                    reconcile_four_token_cycle_terminal(
                        conn,
                        campaign_id=str(campaign_id),
                        campaign_run_id=str(campaign_run_id),
                        factory_run_id=run_id,
                        cycle_id=admitted_cycle_id,
                        configuration_id=str(configuration_id),
                        peer_stop_origin_cycle_id=peer_origin,
                        now=_now(),
                        terminal_phase=(
                            "CAMPAIGN_PRE_LIFECYCLE"
                            if (
                                str(admitted[0]) == str(cycle_id)
                                and not four_token_cycle_one_opening_completed
                            )
                            else None
                        ),
                    )
                )
            four_token_terminal = {"phase_a": tuple(phase_a)}
        else:
            _cancel_pending(conn, run_id, stop_reason)
            if stop_reason != STOP_COMPLETED:
                _cancel_owned_continuation_windows_for_run(
                    conn,
                    factory_run_id=run_id,
                    terminal_cause=stop_reason,
                )
        discovery_cleanup = _cancel_campaign_discovery_jobs(
            conn,
            discovery.get("selection_handoff_report", {}).get("batch_id"),
            campaign_id=campaign_id,
            campaign_run_id=campaign_run_id,
            cycle_id=cycle_id,
            terminal_cause=stop_reason,
        )
        conn.commit()
        report = _final_report(
            conn, run_id=run_id, config=config, discovery=discovery, before=before,
            stop_reason=stop_reason, started_at=started_at,
        )
        from printer_v1.operator_cli.tracking_lifecycle_reconciliation import (
            reconcile_factory_post_cycle_lifecycle,
        )
        lifecycle_reconciliation = reconcile_factory_post_cycle_lifecycle(
            conn,
            run_id=run_id,
            selected_tokens=report["selected_tokens"],
            discovery_results=discovery.get("discovery_results", []),
            per_token_outcomes=report["per_token_outcomes"],
            stop_reason=report["stop_reason"],
            archive_policy="cooldown",
        )
        conn.commit()
        if (
            _post_handoff_scope_recorder is not None
            and not first_window_checkpointed
        ):
            _post_handoff_scope_recorder.record_lifecycle_event_ids(
                tuple(
                    int(item["lifecycle_event_id"])
                    for item in lifecycle_reconciliation.get("transitions", ())
                    if item.get("lifecycle_event_id") is not None
                )
            )
            try:
                _post_handoff_scope_recorder.checkpoint(
                    conn,
                    run_id,
                    "AFTER_FIRST_LIFECYCLE_WINDOW_COMMIT",
                )
            except Exception:
                conn.close()
                raise
            first_window_checkpointed = True
        report = _final_report(
            conn, run_id=run_id, config=config, discovery=discovery, before=before,
            stop_reason=stop_reason, started_at=started_at,
        )
        if four_token_terminal is not None:
            if four_token_shared_terminalizer is None:
                raise ValueError("authoritative shared terminal owner missing")

            def _shared_terminal_from_accounting(
                *, terminal_accounting: Mapping[str, Any] | None = None
            ) -> Mapping[str, Any]:
                if terminal_accounting is None:
                    if len(phase_a) != 1 or not isinstance(phase_a[0], Mapping):
                        raise ValueError(
                            "no-accounting shared terminal requires one Phase-A result"
                        )
                    shared_cause = phase_a[0].get("first_terminal_cause")
                    phase_a_state = str(phase_a[0].get("cycle_state") or "")
                    if phase_a_state == "TERMINAL_COMPLETED":
                        shared_status = "COMPLETED"
                    elif phase_a_state == "TERMINAL_FAILED":
                        shared_status = "FAILED"
                    elif phase_a_state in {
                        "TERMINAL_STOPPED",
                        "TERMINAL_BLOCKED",
                    }:
                        shared_status = "SAFE_STOPPED"
                    else:
                        raise ValueError(
                            "no-accounting shared terminal has invalid Phase-A state"
                        )
                    if not str(shared_cause or "").strip():
                        raise ValueError(
                            "no-accounting shared terminal has no Phase-A cause"
                        )
                    return four_token_shared_terminalizer(
                        terminal_cause=str(shared_cause),
                        run_status=shared_status,
                    )
                aggregate_outcome = str(
                    terminal_accounting.get("execution_outcome") or ""
                )
                aggregate_first = terminal_accounting.get("first_cause")
                aggregate_cause = (
                    aggregate_first.get("cause")
                    if isinstance(aggregate_first, Mapping)
                    else None
                )
                if aggregate_outcome == "TERMINAL_SUCCESS":
                    shared_status = "COMPLETED"
                    shared_cause = STOP_COMPLETED
                elif aggregate_outcome in {
                    "CYCLE_FAILED",
                    "CAMPAIGN_FAILED",
                }:
                    shared_status = "FAILED"
                    shared_cause = aggregate_cause
                else:
                    shared_status = "SAFE_STOPPED"
                    shared_cause = aggregate_cause
                if not str(shared_cause or "").strip():
                    raise ValueError(
                        "canonical campaign aggregate has no terminal cause"
                    )
                return four_token_shared_terminalizer(
                    terminal_cause=str(shared_cause),
                    run_status=shared_status,
                )

            phase_b = finalize_four_token_shared_terminal(
                conn,
                campaign_id=str(campaign_id),
                campaign_run_id=str(campaign_run_id),
                factory_run_id=run_id,
                configuration_id=str(configuration_id),
                shared_terminalizer=_shared_terminal_from_accounting,
            )
            four_token_terminal.update(phase_b)
        report["post_cycle_lifecycle_reconciliation"] = lifecycle_reconciliation
        report["campaign_discovery_cleanup"] = discovery_cleanup
        if four_token_terminal is not None:
            report["four_token_terminal"] = four_token_terminal
        _apply_post_report_integrity(report)
        report["full_run_evidence_deltas"] = dict(report["table_deltas"])
        report["recovery_evidence_deltas"] = {
            table: 0 for table in report["table_deltas"]
        }

        if four_token_terminal is None:
            conn.execute(
                "UPDATE printer_memory_factory_runs SET run_status=?,stop_reason=?,finished_at=?,final_report_json=?,updated_at=? WHERE run_id=?",
                (report["run_status"], report["stop_reason"], report["finished_at"], _json(report), _iso(), run_id),
            )
        else:
            conn.execute(
                "UPDATE printer_memory_factory_runs SET stop_reason=COALESCE(stop_reason,?),"
                "finished_at=COALESCE(finished_at,?),final_report_json=?,updated_at=? "
                "WHERE run_id=? AND run_status!='RUNNING'",
                (report["stop_reason"], report["finished_at"], _json(report), _iso(), run_id),
            )
        conn.commit()
        _emit_supervision_event(
            bool(supervision_execution_id),
            "CLEANUP_COMPLETE",
            run_id=run_id,
            stop_reason=report["stop_reason"],
            running_jobs=report["running_jobs_after_stop"],
        )
        conn.close()
        if supervision_execution_id:
            from printer_v1.operator_cli.proof_supervision import (
                finalize_execution_from_report,
            )
            finalize_execution_from_report(path, supervision_execution_id, report)
    return report
