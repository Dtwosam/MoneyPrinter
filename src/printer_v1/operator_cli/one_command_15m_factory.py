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
from printer_v1.operator_cli.git_provenance import (
    GitProvenanceError,
    capture_git_provenance,
    validate_launch_provenance,
)
from printer_v1.scheduler.contracts import JobKind, LockResult
from printer_v1.scheduler.scheduler import (
    cancel_job,
    claim_due_job,
    complete_job,
    enqueue_job,
    fail_job,
)
from printer_v1.sources.measured_transport import (
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
    _V2_5_MAX_SELECTED_TOKENS * _MAX_SNAPSHOTS_PER_TOKEN + _V2_5_MAX_SELECTED_TOKENS
)


def _continuation_expected_snapshots(lane: str) -> int:
    policy = _cadence_get_policy("WINDOW_1H", lane)
    if policy is None:
        return 24 if lane == "TRACK_FAST" else 13
    return int(policy.minimum_required_snapshots)


_CONTINUOUS_MAX_REQUESTS_PER_TOKEN = (
    _MAX_GOVERNED_REQUESTS_PER_TOKEN
    + _continuation_expected_snapshots("TRACK_FAST")
)
_CONTINUOUS_MAX_REQUESTS_RUN = _MAX_DISCOVERY_REQUESTS + _CONTINUOUS_MAX_REQUESTS_PER_TOKEN
_CONTINUOUS_MAX_SCHEDULER_ROWS = (
    _MAX_SNAPSHOTS_PER_TOKEN
    + _continuation_expected_snapshots("TRACK_FAST")
    + _CONTINUOUS_MAX_SELECTED_TOKENS
)
_COMPRESSED_TWO_TOKEN_MAX_REQUESTS_RUN = (
    _CONTINUOUS_MAX_REQUESTS_RUN + _MAX_GOVERNED_REQUESTS_PER_TOKEN
)
_COMPRESSED_TWO_TOKEN_MAX_SCHEDULER_ROWS = (
    _CONTINUOUS_MAX_SCHEDULER_ROWS
    + _MAX_SNAPSHOTS_PER_TOKEN
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
    _MAX_SNAPSHOTS_PER_TOKEN
    + _continuation_expected_snapshots("TRACK_FAST")
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
        scheduler_components["proof_peer_window_15m"] = int(
            peer_policy.minimum_required_snapshots
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


def _insert_step_and_job(
    conn: sqlite3.Connection, *, run_id: str, target: dict[str, Any],
    step_key: str, step_kind: str, scheduled_for: datetime,
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
    scheduler_ceiling = (
        _SELECTIVE_1H_MAX_SCHEDULER_ROWS
        if selective_1h
        else _COMPRESSED_TWO_TOKEN_MAX_SCHEDULER_ROWS
        if compressed_two_token
        else _CONTINUOUS_MAX_SCHEDULER_ROWS
        if continuous
        else _MAX_SCHEDULER_ROWS
    )
    discovery_handoff_allowance = (
        2
        if selective_1h or compressed_two_token
        else _CONTINUOUS_MAX_SELECTED_TOKENS
        if continuous
        else _V2_5_MAX_SELECTED_TOKENS
    )
    if _run_step_job_count(conn, run_id) >= scheduler_ceiling - discovery_handoff_allowance:
        raise _GlobalStop(STOP_BUDGET, scope="CUMULATIVE_LIFECYCLE")
    if step_kind in {"WINDOW_CLOSE", "CONTINUATION_CLOSE"}:
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
    result, job_id = enqueue_job(
        conn, job_name=f"v2_4_{run_id}_{step_key}", job_kind=job_kind,
        target_table="printer_tracking_queue", target_id=None,
        scheduled_for=scheduled_for,
    )
    if result != LockResult.ACQUIRED or job_id is None:
        raise ValueError(f"scheduler enqueue failed for {step_key}: {result}")
    conn.execute(
        """
        INSERT INTO printer_memory_factory_run_steps
          (run_id, step_key, step_kind, step_status, token_id, pair_id,
           token_mint, pair_address, tracking_lane, scheduled_for,
           scheduler_job_id, created_at, updated_at)
        VALUES (?, ?, ?, 'PENDING', ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            run_id, step_key, step_kind, target["token_id"], target["pair_id"],
            target["token_mint"], target["pair_address"], target["tracking_lane"],
            _iso(scheduled_for), job_id, _iso(), _iso(),
        ),
    )
    # V2-9.8B action-local observation at the real Scheduler-enqueue boundary.
    # Verification-only: the observer never mutates factory state and fires only
    # when a coordinator threads it through. Reports exactly what was enqueued.
    if operation_observer is not None:
        operation_observer(
            {
                "boundary": "SCHEDULER_ENQUEUE",
                "run_id": run_id,
                "scheduler_job_id": int(job_id),
                "step_key": step_key,
                "step_kind": step_kind,
                "token_id": int(target["token_id"]),
                "pair_id": int(target["pair_id"]),
            }
        )
    return int(job_id)


def _plan_opening_jobs(
    conn: sqlite3.Connection, run_id: str, targets: list[dict[str, Any]],
    scheduled_for: datetime,
    first_commit_callback: Callable[[sqlite3.Connection, str], None] | None = None,
    operation_observer: Callable[[Mapping[str, Any]], None] | None = None,
) -> None:
    for target_index, target in enumerate(targets):
        prefix = f"t{target_index + 1}"
        _insert_step_and_job(
            conn, run_id=run_id, target=target,
            step_key=f"{prefix}_snapshot_00", step_kind="SNAPSHOT",
            scheduled_for=scheduled_for, operation_observer=operation_observer,
        )
        if target_index == 0 and first_commit_callback is not None:
            conn.commit()
            first_commit_callback(conn, run_id)


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
    _insert_step_and_job(
        conn, run_id=run_id, target=target,
        step_key=f"{prefix}_window_close", step_kind="WINDOW_CLOSE",
        scheduled_for=anchor + timedelta(seconds=window_seconds),
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

    def insert_owned_job(*, step_key: str, step_kind: str, scheduled_for: datetime) -> int:
        job_id = _insert_step_and_job(
            conn,
            run_id=run_id,
            target=target,
            step_key=step_key,
            step_kind=step_kind,
            scheduled_for=scheduled_for,
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
                deadline_at=_iso(scheduled_for),
                scheduler_job_id=int(job_id),
                stage_id="WINDOW_1H",
                target_category="CAMPAIGN_WINDOW",
                target_identity=ownership["campaign_window_1h_id"],
                work_state="PENDING",
            )
        return int(job_id)

    for index in range(expected - 1):
        offset = continuation_seconds * index / (expected - 1)
        insert_owned_job(
            step_key=f"{prefix}_continuation_snapshot_{index:02d}",
            step_kind="CONTINUATION_SNAPSHOT",
            scheduled_for=close_at + timedelta(seconds=offset),
        )
    insert_owned_job(
        step_key=f"{prefix}_continuation_close",
        step_kind="CONTINUATION_CLOSE",
        scheduled_for=close_at + timedelta(seconds=continuation_seconds),
    )
    return {**plan, "planned_jobs": expected, "expected_snapshots": expected}

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
                "goplus", "safety_reference", "safety", {}, safety_adapter
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
                "holder_concentration_reference",
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

    if not preserve_partial_executions:
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
            "source_request_budget": len(requested) + (1 if "safety" in requested else 0),
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
            evaluated_at=str(snapshot["captured_at"]),
            goplus_execution=safety,
            holder_execution=executions.get("holder"),
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
            # tracking_lane is deliberately still not passed: it would resolve a
            # closing-evidence allowance and silently widen 15m closing lateness
            # from 0s to the 4h 60s allowance. The 15m lateness contract is
            # unchanged by this lane.
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
        SELECT w.*, s.id AS close_step_id, s.snapshot_id AS step_snapshot_id,
               s.token_mint, s.pair_address, s.tracking_lane AS step_lane
        FROM printer_memory_factory_run_steps s
        JOIN printer_memory_windows w ON w.id=s.memory_window_id
        WHERE s.run_id=? AND s.token_id=? AND s.pair_id=?
          AND s.tracking_lane=? AND s.step_kind='WINDOW_CLOSE'
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
    conn: sqlite3.Connection, run_id: str
) -> int:
    """Count activated tokens that have a first-15m close step for this run."""
    return int(
        conn.execute(
            "SELECT COUNT(DISTINCT token_id || ':' || pair_id) "
            "FROM printer_memory_factory_run_steps "
            "WHERE run_id=? AND step_kind='WINDOW_CLOSE'",
            (run_id,),
        ).fetchone()[0]
    )


def _operational_terminal_15m_closes(
    conn: sqlite3.Connection, run_id: str, *, current_step_id: int
) -> list[sqlite3.Row]:
    """Return every terminal 15m close (memory window attached) for this run.

    A close is terminal once its 15m memory window is attached and the step is
    SUCCEEDED, or is the exact current close still RUNNING. This is the barrier
    input: the operational-natural disposition may only be derived once every
    activated token appears here.
    """
    return conn.execute(
        """
        SELECT * FROM printer_memory_factory_run_steps
        WHERE run_id=? AND step_kind='WINDOW_CLOSE'
          AND memory_window_id IS NOT NULL
          AND (step_status='SUCCEEDED' OR (id=? AND step_status='RUNNING'))
        ORDER BY id
        """,
        (run_id, int(current_step_id)),
    ).fetchall()


def _authoritative_terminal_15m_closes(
    conn: sqlite3.Connection, run_id: str
) -> list[sqlite3.Row]:
    """Return only succeeded, exactly linked starting-token 15m closes."""
    return conn.execute(
        """
        SELECT * FROM printer_memory_factory_run_steps
        WHERE run_id=? AND step_kind='WINDOW_CLOSE'
          AND memory_window_id IS NOT NULL AND step_status='SUCCEEDED'
        ORDER BY id
        """,
        (run_id,),
    ).fetchall()


def _run_selective_1h_campaign_barrier(
    conn: sqlite3.Connection,
    *,
    db_path: str,
    run_id: str,
    config: Mapping[str, Any],
    continuation_seconds: float,
) -> dict[str, Any]:
    """Evaluate once after every activated 15m close is authoritative."""
    expected = _operational_activated_token_count(conn, run_id)
    closes = _authoritative_terminal_15m_closes(conn, run_id)
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
                config.get("cycle_id"),
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
            cycle_id=str(config["cycle_id"]),
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
            cycle_id=str(config["cycle_id"]),
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
        cycle_id=str(config["cycle_id"]),
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
             AND step_kind IN ('SNAPSHOT','WINDOW_CLOSE','CONTINUATION_SNAPSHOT')
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
    fallback_adapter_factory: Callable[..., Any] | None = None,
    cancellation_probe: Callable[[], str | None] | None = None,
) -> dict[str, Any]:
    """Persist the final 1h snapshot and close against the exact current-run 15m row."""
    _check_cancellation(cancellation_probe)
    from printer_v1.operator_cli.e2q_memory_window_audit import audit_15m_memory_window
    from printer_v1.operator_cli.lane_e2o_1h_window_close import (
        E2O_1H_STATUS_BLOCKED,
        E2O_1H_STATUS_CONTINUITY_BLOCKED,
        close_1h_memory_window_from_snapshot,
    )
    from printer_v1.operator_cli.lane_k_e2z_pipeline_wiring import run_e2z_pipeline

    _check_cancellation(cancellation_probe)
    result = _execute_snapshot(
        conn, step, adapter_factory=adapter_factory, timeout_seconds=timeout_seconds,
        fallback_adapter_factory=fallback_adapter_factory,
    )
    _check_cancellation(cancellation_probe)
    if not result.get("ok"):
        return result
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
                 'SNAPSHOT','WINDOW_CLOSE','CONTINUATION_SNAPSHOT',
                 'CONTINUATION_CLOSE','LONG_CONTINUATION_SNAPSHOT'
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


def _execute_long_4h_step(
    conn: sqlite3.Connection,
    step: sqlite3.Row,
    *,
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
    if str(step_kind) != "CONTINUATION_CLOSE":
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
    if str(step_kind) != "LONG_CONTINUATION_CLOSE":
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
    }
    if step_kind not in supported:
        return []
    records: list[dict[str, Any]] = []
    for reservation_index in range(int(projected_requests)):
        if step_kind == "WINDOW_CLOSE":
            family = (
                "CLOSE_OBSERVATION"
                if reservation_index == 0 else "PRECLOSE_CONTEXT"
            )
        elif step_kind == "SNAPSHOT":
            family = "SNAPSHOT_OBSERVATION"
        elif step_kind == "CONTINUATION_SNAPSHOT":
            family = "CONTINUATION_SNAPSHOT_OBSERVATION"
        elif step_kind == "CONTINUATION_CLOSE":
            family = "CONTINUATION_CLOSE_OBSERVATION"
        elif step_kind == "LONG_CONTINUATION_CLOSE":
            family = "LONG_CONTINUATION_CLOSE_OBSERVATION"
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
                    int(pending["scheduler_job_id"]) * 100 + reservation_index
                ),
                "operation_family": family,
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
    if ownership_context is None or str(step["step_kind"]) != "WINDOW_CLOSE":
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
    """Return the per-token step-key prefix (e.g. 't1') for budget accounting."""
    return str(step_key).split("_", 1)[0]


def _run_request_count(conn: sqlite3.Connection, run_id: str) -> int:
    return int(conn.execute(
        "SELECT COUNT(*) FROM printer_source_requests WHERE request_key LIKE ?",
        (f"{run_id}:%",),
    ).fetchone()[0])


def _token_request_count(conn: sqlite3.Connection, run_id: str, token_prefix: str) -> int:
    return int(conn.execute(
        "SELECT COUNT(*) FROM printer_source_requests WHERE request_key LIKE ?",
        (f"{run_id}:{token_prefix}_%",),
    ).fetchone()[0])


def _run_step_job_count(conn: sqlite3.Connection, run_id: str) -> int:
    return int(conn.execute(
        "SELECT COUNT(*) FROM printer_scheduler_jobs WHERE job_name LIKE ?",
        (f"v2_4_{run_id}_%",),
    ).fetchone()[0])


def _projected_requests_for_step(step: sqlite3.Row) -> int:
    # A snapshot step issues one governed request; a close step issues one
    # snapshot request plus up to five close-time context requests.
    if step["step_kind"] in LIFECYCLE_RESERVED_OPERATIONS_BY_STEP_KIND:
        return int(
            LIFECYCLE_RESERVED_OPERATIONS_BY_STEP_KIND[str(step["step_kind"])]
        )
    if step["step_kind"] == "LONG_CONTINUATION_CLOSE":
        return 5
    if step["step_kind"] == "LONG_CONTINUATION_SNAPSHOT" and str(step["step_key"]).endswith("_snapshot_000"):
        return 3
    return 1


def _enforce_budgets_before_step(conn: sqlite3.Connection, run_id: str, step: sqlite3.Row) -> None:
    """Raise _GlobalStop if executing this step would breach a hard ceiling.

    Hard ceilings are integrity limits, not targets: a projected breach is a
    global safe stop, never a silently exceeded call.
    """
    projected = _projected_requests_for_step(step)
    config = _load_run_config(conn, run_id)
    if str(step["step_kind"]).startswith("LONG_CONTINUATION_"):
        from printer_v1.operator_cli.one_token_4h_runtime import (
            cumulative_lifecycle_budget,
            require_projected_capacity,
            runtime_budget,
        )
        lane = str(step["tracking_lane"])
        phase = runtime_budget(lane)
        cumulative = _cumulative_lifecycle_budget_for_run(conn, run_id, lane)
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
                ceiling=int(phase["phase_request_ceiling"]),
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
        if s["step_kind"] in {"WINDOW_CLOSE", "CONTINUATION_CLOSE", "LONG_CONTINUATION_CLOSE"}:
            t["close_status"] = s["step_status"]
            t["close_step_kind"] = s["step_kind"]
            t["memory_window_id"] = s.get("memory_window_id")
            t["close_step_e2z_status"] = (
                _step_e2z_status(s, int(s["memory_window_id"]))
                if s.get("memory_window_id") is not None else None
            )
            if s["step_kind"] == "LONG_CONTINUATION_CLOSE":
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

        phase = runtime_budget(lane)
        cumulative = _cumulative_lifecycle_budget_for_run(conn, run_id, lane)
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
            "tracking_lane": lane,
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
            "tracking_lane": lane,
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
        if compressed_two_token:
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
            "holder_rpc_fallbacks": holder_fallbacks,
            "holder_rpc_fallbacks_ceiling": int(phase["holder_fallback_max"]),
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
        fifteen = next((s for s in token_steps if s["step_kind"] == "WINDOW_CLOSE"), None)
        continuation = next((s for s in token_steps if s["step_kind"] == "CONTINUATION_CLOSE"), None)
        four_hour = next((s for s in token_steps if s["step_kind"] == "LONG_CONTINUATION_CLOSE"), None)
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
        if step.get("step_kind") == "LONG_CONTINUATION_CLOSE"
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
                if step.get("step_kind") == "WINDOW_CLOSE"
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
                step.get("step_kind") in {
                    "CONTINUATION_CLOSE", "LONG_CONTINUATION_CLOSE"
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
    """Validate the exact B2 two-window WINDOW_4H campaign set categorically."""
    if not all((campaign_id, run_id, cycle_id, factory_run_id)):
        return {"enabled": False, "complete": True, "reasons": [], "per_token": []}
    windows = conn.execute(
        """SELECT w.*,s.slot_ordinal,s.token_state,s.token_row_id AS slot_token_row_id,
                  s.pair_row_id AS slot_pair_row_id
           FROM printer_memory_factory_campaign_windows AS w
           JOIN printer_memory_factory_campaign_token_slots AS s
             ON s.token_slot_id=w.token_slot_id
            AND s.campaign_id=w.campaign_id
            AND s.run_id=w.run_id
            AND s.cycle_id=w.cycle_id
           WHERE w.campaign_id=? AND w.run_id=? AND w.cycle_id=?
             AND w.window_kind='WINDOW_4H'
           ORDER BY s.slot_ordinal,w.window_id""",
        (str(campaign_id), str(run_id), str(cycle_id)),
    ).fetchall()
    if not windows:
        return {"enabled": False, "complete": True, "reasons": [], "per_token": []}

    reasons: list[str] = []
    if len(windows) != 2:
        reasons.append(f"standard_window_4h_count:{len(windows)} expected=2")
    if len({str(row["token_slot_id"]) for row in windows}) != len(windows):
        reasons.append("duplicate_standard_window_4h_slot_identity")
    if len({int(row["token_row_id"]) for row in windows}) != len(windows):
        reasons.append("duplicate_standard_window_4h_token_identity")

    success_states = {
        "CLEAN_PROMOTED", "DIRTY", "NO_PROMOTION", "ALREADY_EXISTS_IDEMPOTENT"
    }
    per_token: list[dict[str, Any]] = []
    for window in windows:
        window_reasons: list[str] = []
        token_id = int(window["token_row_id"])
        pair_id = int(window["pair_row_id"])
        if (
            int(window["slot_token_row_id"]) != token_id
            or int(window["slot_pair_row_id"]) != pair_id
        ):
            window_reasons.append("slot_token_pair_identity_mismatch")
        owned = conn.execute(
            """SELECT s.*,j.status AS scheduler_status,sw.work_state,
                      sw.scheduler_work_id
               FROM printer_memory_factory_campaign_scheduler_work AS sw
               JOIN printer_memory_factory_run_steps AS s
                 ON s.scheduler_job_id=sw.scheduler_job_id
               JOIN printer_scheduler_jobs AS j ON j.id=sw.scheduler_job_id
               WHERE sw.campaign_id=? AND sw.run_id=? AND sw.cycle_id=?
                 AND sw.factory_run_id=? AND sw.window_id=?
                 AND sw.token_slot_id=?
                 AND sw.ownership_contract_version='V2_STAGE_SCOPED'
                 AND sw.work_scope='WINDOW_LIFECYCLE'
                 AND sw.stage_id='WINDOW_4H'
                 AND sw.target_category='CAMPAIGN_WINDOW'
                 AND sw.target_identity=sw.window_id
                 AND s.run_id=? AND s.token_id=? AND s.pair_id=?
                 AND s.step_kind IN ('LONG_CONTINUATION_SNAPSHOT','LONG_CONTINUATION_CLOSE')
               ORDER BY s.scheduled_for,s.id""",
            (
                str(campaign_id), str(run_id), str(cycle_id), str(factory_run_id),
                str(window["window_id"]), str(window["token_slot_id"]),
                str(factory_run_id), token_id, pair_id,
            ),
        ).fetchall()
        lanes = {str(row["tracking_lane"]) for row in owned}
        lane = next(iter(lanes)) if len(lanes) == 1 else None
        if lane is None:
            window_reasons.append("missing_or_ambiguous_4h_tracking_lane")
            expected = 0
        else:
            try:
                expected = int(
                    _cadence_get_policy("WINDOW_4H", lane).minimum_required_snapshots
                )
            except Exception:
                expected = 0
                window_reasons.append("missing_4h_cadence_policy")
        actual = sum(1 for row in owned if row["snapshot_id"] is not None)
        if expected and actual != expected:
            window_reasons.append(f"incomplete_4h_collection:{actual}/{expected}")
        closes = [row for row in owned if str(row["step_kind"]) == "LONG_CONTINUATION_CLOSE"]
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
        memory_id = int(window["memory_window_row_id"]) if window["memory_window_row_id"] is not None else None
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
                "token_slot_id": str(window["token_slot_id"]),
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
        "complete": not reasons,
        "reasons": reasons,
        "per_token": per_token,
        "active_owned_four_hour_work": active_owned,
        "nonterminal_owned_four_hour_windows": nonterminal_windows,
        "window_count": len(windows),
    }


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
        if step.get("step_kind") in {
            "WINDOW_CLOSE", "CONTINUATION_CLOSE", "LONG_CONTINUATION_CLOSE"
        }
    ]
    foreign = [
        str(step.get("token_mint")) for step in steps
        if str(step.get("token_mint")) not in expected_mints
    ]
    if foreign:
        reasons.append("foreign_lifecycle_identity")

    closes_15m = [step for step in relevant if step.get("step_kind") == "WINDOW_CLOSE"]
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

    closes_1h = [step for step in relevant if step.get("step_kind") == "CONTINUATION_CLOSE"]
    if (
        len(closes_1h) != 1
        or closes_1h[0].get("step_status") != "SUCCEEDED"
        or closes_1h[0].get("token_mint") != plan["continuation_token_mint"]
    ):
        reasons.append("one_exact_terminal_1h_close_required")
    elif windows_by_id.get(int(closes_1h[0]["memory_window_id"]), {}).get("window_kind") != "WINDOW_1H":
        reasons.append("invalid_1h_window_attachment")

    closes_4h = [step for step in relevant if step.get("step_kind") == "LONG_CONTINUATION_CLOSE"]
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
    """Select the next step, adding categorical fairness only for exact owned 4h work."""
    fallback = conn.execute(
        """SELECT s.* FROM printer_memory_factory_run_steps AS s
           WHERE s.run_id=? AND s.step_status='PENDING'
           ORDER BY s.scheduled_for,s.id LIMIT 1""",
        (str(run_id),),
    ).fetchone()
    if fallback is None:
        return None
    due_at = datetime.fromisoformat(str(fallback["scheduled_for"]))
    if due_at > now:
        return fallback
    owner = _owned_campaign_scheduler_row(
        conn, scheduler_job_id=int(fallback["scheduler_job_id"])
    )
    if owner is None or not (
        str(owner["work_scope"]) == "WINDOW_LIFECYCLE"
        and str(owner["stage_id"]) == "WINDOW_4H"
        and str(owner["target_category"]) == "CAMPAIGN_WINDOW"
        and owner["window_id"] is not None
        and owner["token_slot_id"] is not None
        and owner["factory_run_id"] is not None
        and str(owner["factory_run_id"]) == str(run_id)
        and str(owner["target_identity"]) == str(owner["window_id"])
        and str(fallback["step_kind"]).startswith("LONG_CONTINUATION_")
    ):
        return fallback

    due_rows = conn.execute(
        """SELECT s.*,sw.window_id,sw.token_slot_id,slot.slot_ordinal,
                  j.id AS canonical_scheduler_job_id
           FROM printer_memory_factory_run_steps AS s
           JOIN printer_scheduler_jobs AS j ON j.id=s.scheduler_job_id
           JOIN printer_memory_factory_campaign_scheduler_work AS sw
             ON sw.scheduler_job_id=j.id
           JOIN printer_memory_factory_campaign_windows AS w
             ON w.window_id=sw.window_id
            AND w.campaign_id=sw.campaign_id
            AND w.run_id=sw.run_id
            AND w.cycle_id=sw.cycle_id
            AND w.token_slot_id=sw.token_slot_id
           JOIN printer_memory_factory_campaign_token_slots AS slot
             ON slot.token_slot_id=sw.token_slot_id
            AND slot.campaign_id=sw.campaign_id
            AND slot.run_id=sw.run_id
            AND slot.cycle_id=sw.cycle_id
           WHERE s.run_id=? AND s.step_status='PENDING'
             AND s.step_kind IN ('LONG_CONTINUATION_SNAPSHOT','LONG_CONTINUATION_CLOSE')
             AND j.status='PENDING' AND j.scheduled_for<=?
             AND sw.ownership_contract_version='V2_STAGE_SCOPED'
             AND sw.work_scope='WINDOW_LIFECYCLE'
             AND sw.stage_id='WINDOW_4H'
             AND sw.target_category='CAMPAIGN_WINDOW'
             AND sw.target_identity=sw.window_id
             AND sw.factory_run_id=s.run_id
             AND w.window_kind='WINDOW_4H'
           ORDER BY j.scheduled_for,j.id,slot.slot_ordinal""",
        (str(run_id), now.isoformat()),
    ).fetchall()
    if not due_rows:
        return fallback
    closes = [
        row for row in due_rows
        if str(row["step_kind"]) == "LONG_CONTINUATION_CLOSE"
    ]
    if closes:
        selected = min(
            closes,
            key=lambda row: (
                str(row["scheduled_for"]),
                int(row["canonical_scheduler_job_id"]),
                int(row["slot_ordinal"]),
            ),
        )
    else:
        service_counts: dict[str, int] = {}
        for row in due_rows:
            window_id = str(row["window_id"])
            if window_id not in service_counts:
                service_counts[window_id] = int(conn.execute(
                    """SELECT COUNT(DISTINCT j2.id)
                       FROM printer_memory_factory_campaign_scheduler_work AS sw2
                       JOIN printer_scheduler_jobs AS j2
                         ON j2.id=sw2.scheduler_job_id
                       JOIN printer_memory_factory_run_steps AS s2
                         ON s2.scheduler_job_id=j2.id
                       WHERE sw2.window_id=?
                         AND sw2.ownership_contract_version='V2_STAGE_SCOPED'
                         AND sw2.work_scope='WINDOW_LIFECYCLE'
                         AND sw2.stage_id='WINDOW_4H'
                         AND s2.run_id=?
                         AND s2.step_kind='LONG_CONTINUATION_SNAPSHOT'
                         AND j2.started_at IS NOT NULL""",
                    (window_id, str(run_id)),
                ).fetchone()[0])
        selected = min(
            due_rows,
            key=lambda row: (
                service_counts[str(row["window_id"])],
                int(row["canonical_scheduler_job_id"]),
                int(row["slot_ordinal"]),
            ),
        )
    selected_id = int(selected["id"])
    return conn.execute(
        "SELECT * FROM printer_memory_factory_run_steps WHERE id=?",
        (selected_id,),
    ).fetchone()


def run_one_command_15m_factory(
    db_path: str | Path, backup_path: str | Path, *, operator_approved: bool,
    proof_mode: bool, window_kind: str = WINDOW_KIND, max_selected_tokens: int = 2,
    max_source_requests: int = 2, timeout_seconds: float = 5.0,
    total_duration_seconds: float = 1200.0, selection_seed: str | None = None,
    v2_5_proof_mode: bool = False,
    continuous_first_hour: bool = False,
    continuous_four_hour: bool = False,
    four_hour_proof_mode: bool = False,
    selective_1h_continuation: bool = False,
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
        if compressed_two_token_proof_plan is not None:
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
    if continuous_four_hour and not four_hour_proof_mode:
        reasons.append("WINDOW_4H real collection remains disabled without explicit proof mode")
    if selective_1h_continuation:
        if continuous_four_hour or four_hour_proof_mode:
            reasons.append(
                "selective 1h continuation cannot enable 4h; 4h remains a separate locked lane"
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
    governed_observer_token = None
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

            _plan_opening_jobs(
                conn,
                run_id,
                targets,
                _now(),
                operation_observer=lifecycle_operation_observer,
                first_commit_callback=(
                    _first_opening_commit
                    if _post_handoff_scope_recorder is not None
                    else None
                ),
            )
        conn.commit()

        while stop_reason == STOP_COMPLETED:
            pending = _select_next_pending_step(
                conn, run_id=run_id, now=_now()
            )
            if pending is None:
                break
            elapsed = _monotonic() - start_mono
            if elapsed >= total_duration_seconds:
                stop_reason = STOP_DURATION
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
            conn.execute(
                "UPDATE printer_memory_factory_run_steps SET step_status='RUNNING',started_at=?,updated_at=? WHERE id=?",
                (_iso(), _iso(), int(pending["id"])),
            )
            _sync_owned_campaign_scheduler_job(
                conn, scheduler_job_id=job_id
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
                        "boundary": "SCHEDULER_CLAIM",
                        "run_id": run_id,
                        "scheduler_job_id": job_id,
                        "step_key": str(pending["step_key"]),
                        "step_kind": str(pending["step_kind"]),
                        "token_id": int(pending["token_id"]),
                        "pair_id": int(pending["pair_id"]),
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
                _enforce_budgets_before_step(conn, run_id, pending)
                reservation_records = _lifecycle_reservation_records_for_step(
                    run_id=run_id,
                    pending=pending,
                    projected_requests=_projected_requests_for_step(pending),
                )
                if lifecycle_operation_observer is not None:
                    for reservation_record in reservation_records:
                        lifecycle_operation_observer(reservation_record)
                if pending["step_kind"] == "WINDOW_CLOSE":
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
                        fallback_adapter_factory=fallback_factory,
                        cancellation_probe=cancellation_probe,
                    )
                elif str(pending["step_kind"]).startswith("LONG_CONTINUATION_"):
                    result = _execute_long_4h_step(
                        conn,
                        pending,
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
                if str(pending["step_kind"]) == "WINDOW_CLOSE" and result.get("ok"):
                    validation_kinds.extend(
                        [
                            "WINDOW_CLOSE_VALIDATED",
                            "SNAPSHOT_COVERAGE_VALIDATED",
                            "WINDOW_QUALITY_VALIDATED",
                        ]
                    )
                validation_records = [
                    {
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
                    and pending["step_kind"] == "WINDOW_CLOSE"
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
                    elif pending["step_kind"] == "WINDOW_CLOSE" and effective_continuous_1h:
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
                                conn, run_id
                            )
                            closes = _operational_terminal_15m_closes(
                                conn, run_id, current_step_id=int(pending["id"])
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
                    elif pending["step_kind"] == "CONTINUATION_CLOSE" and continuous_four_hour:
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
                            ownership_context=lifecycle_ownership_context,
                        )
                    )
                    # Re-persist enriched close-step result_json (includes
                    # campaign_window_registration) before Scheduler terminalization.
                    # Registration remains inside the same open transaction; a
                    # registration fault still rolls back the SUCCEEDED update.
                    if result.get("campaign_window_registration") is not None:
                        _update_step(conn, int(pending["id"]), "SUCCEEDED", result)
                    if str(pending["step_kind"]) == "CONTINUATION_CLOSE":
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
                    elif str(pending["step_kind"]) == "LONG_CONTINUATION_CLOSE":
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
                        and pending["step_kind"] == "WINDOW_CLOSE"
                        and not post_activation_checkpointed
                    ):
                        _post_handoff_scope_recorder.checkpoint(
                            conn,
                            run_id,
                            "AFTER_POST_ACTIVATION_15M_STATE_COMMIT",
                        )
                        post_activation_checkpointed = True
                    if (
                        pending["step_kind"] == "WINDOW_CLOSE"
                        and bool(config.get("selective_1h_continuation"))
                    ):
                        _run_selective_1h_campaign_barrier(
                            conn,
                            db_path=str(path),
                            run_id=run_id,
                            config=config,
                            continuation_seconds=_continuation_seconds,
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
                        "CONTINUATION_SNAPSHOT", "CONTINUATION_CLOSE"
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
                        and pending["step_kind"] == "WINDOW_CLOSE"
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
                    and pending["step_kind"] == "WINDOW_CLOSE"
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
                    "CONTINUATION_SNAPSHOT", "CONTINUATION_CLOSE"
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
                    and pending["step_kind"] == "WINDOW_CLOSE"
                    and not post_activation_checkpointed
                ):
                    _post_handoff_scope_recorder.checkpoint(
                        conn,
                        run_id,
                        "AFTER_POST_ACTIVATION_15M_STATE_COMMIT",
                    )
                    post_activation_checkpointed = True
    except _ExternalStop as external_stop:
        stop_reason = external_stop.reason
    except KeyboardInterrupt:
        stop_reason = STOP_INTERRUPTED
    except Exception as exc:
        if getattr(exc, "post_handoff_proof_fault", False):
            proof_fault = exc
        else:
            stop_reason = STOP_PREFLIGHT
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
        report["post_cycle_lifecycle_reconciliation"] = lifecycle_reconciliation
        report["campaign_discovery_cleanup"] = discovery_cleanup
        _apply_post_report_integrity(report)
        report["full_run_evidence_deltas"] = dict(report["table_deltas"])
        report["recovery_evidence_deltas"] = {
            table: 0 for table in report["table_deltas"]
        }

        conn.execute(
            "UPDATE printer_memory_factory_runs SET run_status=?,stop_reason=?,finished_at=?,final_report_json=?,updated_at=? WHERE run_id=?",
            (report["run_status"], report["stop_reason"], report["finished_at"], _json(report), _iso(), run_id),
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
