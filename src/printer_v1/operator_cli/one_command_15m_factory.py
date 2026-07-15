"""V2-4 bounded proof-only one-command WINDOW_15M Memory Factory."""

from __future__ import annotations

import argparse
import hashlib
import json
import sqlite3
import time
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Callable

from printer_v1.scheduler.contracts import JobKind, LockResult
from printer_v1.scheduler.scheduler import (
    cancel_job,
    claim_due_job,
    complete_job,
    enqueue_job,
    fail_job,
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

# V2-5: token-local terminal markers (never a run-wide stop).
TOKEN_LOCAL_FAILED = "TOKEN_LOCAL_TERMINAL_FAILURE"
TOKEN_LOCAL_CANCELLED = "TOKEN_LOCAL_CANCELLED_AFTER_FAILURE"

# V2-5 conservative three-token hard ceilings. These are hard limits, not
# targets; a breach is a global integrity safe-stop, never silently exceeded.
# V2-6.1a: the per-token snapshot count derives from the single authoritative
# cadence policy (WINDOW_15M TRACK_FAST = 16 snapshots) so budgets recalculate
# automatically when the cadence contract changes.
from printer_v1.snapshots.cadence_policy import get_policy as _cadence_get_policy

_V2_5_MAX_SELECTED_TOKENS = 3
_MAX_DISCOVERY_REQUESTS = 2
_CONTEXT_REQUESTS_PER_TOKEN = 5
_MAX_HOLDER_FALLBACKS_PER_TOKEN = 1
_CONTINUATION_SECONDS = 2700.0
_CONTINUOUS_MAX_SELECTED_TOKENS = 1


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


class _GlobalStop(Exception):
    """Raised to signal a global (run-wide) safe stop with an explicit reason."""

    def __init__(self, reason: str) -> None:
        super().__init__(reason)
        self.reason = reason

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
) -> int:
    # Scheduler-row ceiling: run-step jobs must stay within the cadence-derived
    # cap. Three TRACK_FAST tokens create _V2_5_MAX_SELECTED_TOKENS *
    # _MAX_SNAPSHOTS_PER_TOKEN run-step jobs; with up to one cancelled discovery
    # handoff per token that is the _MAX_SCHEDULER_ROWS design ceiling.
    run_config = _load_run_config(conn, run_id)
    continuous = bool(run_config.get("continuous_first_hour"))
    scheduler_ceiling = (
        _CONTINUOUS_MAX_SCHEDULER_ROWS if continuous else _MAX_SCHEDULER_ROWS
    )
    discovery_handoff_allowance = (
        _CONTINUOUS_MAX_SELECTED_TOKENS if continuous else _V2_5_MAX_SELECTED_TOKENS
    )
    if _run_step_job_count(conn, run_id) >= scheduler_ceiling - discovery_handoff_allowance:
        raise _GlobalStop(STOP_BUDGET)
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
    return int(job_id)


def _plan_opening_jobs(
    conn: sqlite3.Connection, run_id: str, targets: list[dict[str, Any]],
    scheduled_for: datetime,
) -> None:
    for target_index, target in enumerate(targets):
        prefix = f"t{target_index + 1}"
        _insert_step_and_job(
            conn, run_id=run_id, target=target,
            step_key=f"{prefix}_snapshot_00", step_kind="SNAPSHOT",
            scheduled_for=scheduled_for,
        )


def _plan_anchored_jobs(
    conn: sqlite3.Connection, *, run_id: str, opening_step: sqlite3.Row,
    first_snapshot_captured_at: str, window_seconds: float,
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
        )
    _insert_step_and_job(
        conn, run_id=run_id, target=target,
        step_key=f"{prefix}_window_close", step_kind="WINDOW_CLOSE",
        scheduled_for=anchor + timedelta(seconds=window_seconds),
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
) -> dict[str, Any]:
    """Enqueue one exact-target 45m continuation from a current-run 15m close."""
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
    for index in range(expected - 1):
        offset = continuation_seconds * index / (expected - 1)
        _insert_step_and_job(
            conn,
            run_id=run_id,
            target=target,
            step_key=f"{prefix}_continuation_snapshot_{index:02d}",
            step_kind="CONTINUATION_SNAPSHOT",
            scheduled_for=close_at + timedelta(seconds=offset),
        )
    _insert_step_and_job(
        conn,
        run_id=run_id,
        target=target,
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


def _execute_snapshot(
    conn: sqlite3.Connection, step: sqlite3.Row, *, adapter_factory: Callable[..., Any],
    timeout_seconds: float,
) -> dict[str, Any]:
    from printer_v1.operator_cli.e2m_snapshot_persistence import (
        E2M_STATUS_PERSISTED, persist_snapshot_from_source_response,
    )
    from printer_v1.sources.budget_accounting import count_recent_source_requests
    from printer_v1.sources.contracts import build_governed_source_request
    from printer_v1.sources.governed_execution import execute_source_request_with_governor

    mint = str(step["token_mint"])
    request = build_governed_source_request(
        "dexscreener", "pair_market_snapshot",
        request_key=f"{step['run_id']}:{step['step_key']}",
        payload={"token_mint": mint, "pair_address": step["pair_address"]},
    )
    adapter = adapter_factory(token_mint=mint, timeout_seconds=timeout_seconds)
    execution = execute_source_request_with_governor(
        conn, request, adapter,
        recent_request_count=count_recent_source_requests(conn, "dexscreener"),
    )
    result: dict[str, Any] = {
        "source_request_id": int(execution.request_record.id),
        "source_response_id": (
            int(execution.response_record.id) if execution.response_record else None
        ),
        "source_failure_id": (
            int(execution.failure_record.id) if execution.failure_record else None
        ),
        "source_status": execution.normalized_result.source_status.value,
        "data_quality_label": execution.normalized_result.data_quality_label.value,
    }
    if execution.response_record is None:
        result["ok"] = False
        result["blocked_reason"] = execution.normalized_result.failure_type or "source_response_missing"
        return result
    persisted = persist_snapshot_from_source_response(
        conn, int(execution.response_record.id), mint,
        expected_pair_address=str(step["pair_address"]),
        tracking_lane=str(step["tracking_lane"]),
    )
    result["snapshot"] = persisted
    result["snapshot_id"] = persisted.get("snapshot_id") or persisted.get("existing_snapshot_id")
    result["ok"] = persisted.get("e2m_status") == E2M_STATUS_PERSISTED
    if not result["ok"]:
        result["blocked_reason"] = "; ".join(persisted.get("blocked_reasons", [])) or persisted.get("e2m_status")
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


def _collect_preclose_context(
    conn: sqlite3.Connection,
    step: sqlite3.Row,
    *,
    timeout_seconds: float,
    adapter_factories: dict[str, Callable[..., Any]] | None = None,
    include: frozenset[str] | None = None,
) -> dict[str, Any]:
    """Collect a fixed, governed context bundle before the close snapshot."""
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
    request_prefix = f"{step['run_id']}:{step['step_key']}:context"

    def execute(source_name: str, request_kind: str, suffix: str, payload: dict[str, Any], adapter: Any) -> Any:
        request = build_governed_source_request(
            source_name,
            request_kind,
            request_key=f"{request_prefix}:{suffix}",
            payload={"token_mint": mint, "pair_address": pair, **payload},
        )
        return execute_source_request_with_governor(
            conn,
            request,
            adapter,
            recent_request_count=count_recent_source_requests(conn, source_name),
        )

    market_factory = factories.get("coingecko")
    market_adapter = (
        market_factory(timeout_seconds=timeout_seconds)
        if market_factory
        else build_coingecko_adapter(
            enabled=True,
            fixture_transport=build_coingecko_market_transport(
                timeout_seconds=timeout_seconds
            ),
        )
    )
    safety_factory = factories.get("goplus")
    safety_adapter = (
        safety_factory(token_mint=mint, timeout_seconds=timeout_seconds)
        if safety_factory
        else build_goplus_adapter(
            enabled=True,
            fixture_transport=build_goplus_token_safety_transport(
                mint, timeout_seconds=timeout_seconds
            ),
        )
    )
    quote_factory = factories.get("jupiter_quote")

    def quote_adapter(input_mint: str, output_mint: str) -> Any:
        if quote_factory:
            return quote_factory(
                input_mint=input_mint,
                output_mint=output_mint,
                amount_lamports=DEFAULT_PAPER_AMOUNT_LAMPORTS,
                slippage_bps=DEFAULT_SLIPPAGE_BPS,
                timeout_seconds=timeout_seconds,
            )
        return build_jupiter_quote_adapter(
            enabled=True,
            fixture_transport=build_jupiter_paper_quote_transport(
                input_mint=input_mint,
                output_mint=output_mint,
                amount_lamports=DEFAULT_PAPER_AMOUNT_LAMPORTS,
                slippage_bps=DEFAULT_SLIPPAGE_BPS,
                timeout_seconds=timeout_seconds,
            ),
        )

    requested = include or frozenset({"market_chain", "safety", "entry_quote", "exit_quote"})
    executions: dict[str, Any] = {}
    if "market_chain" in requested:
        executions["market_chain"] = execute(
            "coingecko", "broad_market_context", "market-chain", {}, market_adapter
        )
    if "safety" in requested:
        executions["safety"] = execute(
            "goplus", "safety_reference", "safety", {}, safety_adapter
        )
    if "entry_quote" in requested:
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
        holder_factory = factories.get("solana_rpc_holder")
        holder_adapter = (
            holder_factory(token_mint=mint, timeout_seconds=timeout_seconds)
            if holder_factory
            else build_solana_rpc_holder_adapter(
                enabled=True,
                fixture_transport=build_solana_rpc_holder_transport(
                    mint, timeout_seconds=timeout_seconds
                ),
            )
        )
        executions["holder"] = execute(
            "solana_rpc",
            "holder_concentration_reference",
            "holder",
            {},
            holder_adapter,
        )
    return {
        "executions": executions,
        "report": {
            "source_request_budget": len(requested) + (1 if "safety" in requested else 0),
            "source_requests_attempted": len(executions),
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


def _execute_close(
    conn: sqlite3.Connection, step: sqlite3.Row, *, adapter_factory: Callable[..., Any],
    timeout_seconds: float, minimum_evidence_seconds: float,
    context_adapter_factories: dict[str, Callable[..., Any]] | None = None,
) -> dict[str, Any]:
    from printer_v1.operator_cli.e2o_memory_window_close import close_15m_memory_window_from_snapshot
    from printer_v1.operator_cli.e2q_memory_window_audit import audit_15m_memory_window
    from printer_v1.operator_cli.lane_k_e2z_pipeline_wiring import run_e2z_pipeline

    context_bundle = _collect_preclose_context(
        conn,
        step,
        timeout_seconds=timeout_seconds,
        adapter_factories=context_adapter_factories,
    )
    result = _execute_snapshot(
        conn, step, adapter_factory=adapter_factory, timeout_seconds=timeout_seconds
    )
    result["governed_context_collection"] = context_bundle["report"]
    if not result.get("ok"):
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
        operator_approved=True, production_mode=True,
    )
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


def _execute_continuation_close(
    conn: sqlite3.Connection,
    step: sqlite3.Row,
    *,
    adapter_factory: Callable[..., Any],
    timeout_seconds: float,
) -> dict[str, Any]:
    """Persist the final 1h snapshot and close against the exact current-run 15m row."""
    from printer_v1.operator_cli.e2q_memory_window_audit import audit_15m_memory_window
    from printer_v1.operator_cli.lane_e2o_1h_window_close import (
        E2O_1H_STATUS_BLOCKED,
        E2O_1H_STATUS_CONTINUITY_BLOCKED,
        close_1h_memory_window_from_snapshot,
    )
    from printer_v1.operator_cli.lane_k_e2z_pipeline_wiring import run_e2z_pipeline

    result = _execute_snapshot(
        conn, step, adapter_factory=adapter_factory, timeout_seconds=timeout_seconds
    )
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
    result["window_audit"] = audit_15m_memory_window(conn, int(window_id))
    conn.commit()
    result["memory_pipeline"] = run_e2z_pipeline(
        str(conn.execute("PRAGMA database_list").fetchone()[2]),
        operator_approved=True,
        production_mode=True,
    )
    result["ok"] = True
    result["continuity_source"] = source
    return result


def _execute_long_4h_step(
    conn: sqlite3.Connection,
    step: sqlite3.Row,
    *,
    adapter_factory: Callable[..., Any],
    timeout_seconds: float,
    context_adapter_factories: dict[str, Callable[..., Any]] | None = None,
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
        )
    elif is_close:
        context_bundle = _collect_preclose_context(
            conn, step, timeout_seconds=timeout_seconds,
            adapter_factories=context_adapter_factories,
            include=frozenset({"market_chain", "safety", "exit_quote"}),
        )
    result = _execute_snapshot(
        conn, step, adapter_factory=adapter_factory, timeout_seconds=timeout_seconds
    )
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


def _cancel_pending(conn: sqlite3.Connection, run_id: str, reason: str) -> None:
    rows = conn.execute(
        "SELECT id, scheduler_job_id FROM printer_memory_factory_run_steps WHERE run_id=? AND step_status='PENDING'",
        (run_id,),
    ).fetchall()
    for row in rows:
        if row["scheduler_job_id"] is not None:
            cancel_job(conn, job_id=int(row["scheduler_job_id"]))
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
        conn.execute(
            "UPDATE printer_memory_factory_run_steps SET step_status='CANCELLED', error_or_skip_reason=?, finished_at=?, updated_at=? WHERE id=?",
            (reason, _iso(), _iso(), int(row["id"])),
        )
    return len(rows)


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
    if step["step_kind"] == "WINDOW_CLOSE":
        return 6
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
        cumulative = cumulative_lifecycle_budget(lane)
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
            require_projected_capacity(
                current=cumulative_used, projected=projected,
                ceiling=int(cumulative["request_ceiling"]),
                label="cumulative lifecycle request",
            )
        except ValueError as exc:
            raise _GlobalStop(STOP_BUDGET) from exc
        return
    continuous = bool(config.get("continuous_first_hour"))
    run_ceiling = _CONTINUOUS_MAX_REQUESTS_RUN if continuous else _MAX_GOVERNED_REQUESTS_RUN
    token_ceiling = (
        _CONTINUOUS_MAX_REQUESTS_PER_TOKEN
        if continuous else _MAX_GOVERNED_REQUESTS_PER_TOKEN
    )
    if _run_request_count(conn, run_id) + projected > run_ceiling:
        raise _GlobalStop(STOP_BUDGET)
    prefix = _token_prefix(step["step_key"])
    if _token_request_count(conn, run_id, prefix) + projected > token_ceiling:
        raise _GlobalStop(STOP_BUDGET)


def _per_token_outcomes(
    steps: list[dict[str, Any]], windows_by_id: dict[int, dict[str, Any]],
) -> list[dict[str, Any]]:
    """Build authoritative per-token outcomes from this run's steps only."""
    _CLEAN = {"CLEAN_MEMORY"}
    _DIRTY = {"DIRTY_MEMORY", "AUDIT_ONLY_MEMORY", "DO_NOT_TRAIN"}
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
                "memory_quality_label": None, "blockers": [],
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
            # V2-6.3: report the 1h continuation plan for the closed 15m window —
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
            t["terminal_status"] = (
                "CLEAN" if q in _CLEAN else "DIRTY" if q in _DIRTY else "BLOCKED_QUALITY"
            )
        elif t["close_status"] == "FAILED":
            t["reached_terminal_window"] = False
            t["terminal_status"] = "TERMINAL_BLOCKED"
        elif t["failed_steps"]:
            t["terminal_status"] = "TOKEN_LOCAL_FAILED"
        elif t["cancelled_steps"]:
            t["terminal_status"] = "CANCELLED"
    return [tokens[tid] for tid in order]


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
        lane_row = conn.execute(
            "SELECT tracking_lane FROM printer_memory_factory_run_steps "
            "WHERE run_id=? AND step_kind LIKE 'LONG_CONTINUATION_%' LIMIT 1",
            (run_id,),
        ).fetchone()
        if lane_row is None:
            return {
                "automatic_retries": 0,
                "continuous_first_hour": continuous,
                "four_hour_phase_usage": {
                    "available": False,
                    "within_ceiling": False,
                },
                "cumulative_lifecycle_usage": {
                    "available": False,
                    "within_ceiling": False,
                },
            }
        lane = str(lane_row[0])
        phase = runtime_budget(lane)
        cumulative = cumulative_lifecycle_budget(lane)
        phase_requests = int(conn.execute(
            "SELECT COUNT(*) FROM printer_source_requests WHERE request_key LIKE ?",
            (f"{run_id}:%4h%",),
        ).fetchone()[0])
        phase_jobs = int(conn.execute(
            "SELECT COUNT(*) FROM printer_memory_factory_run_steps "
            "WHERE run_id=? AND step_kind LIKE 'LONG_CONTINUATION_%'",
            (run_id,),
        ).fetchone()[0])
        cumulative_requests = discovery_requests + runtime_requests
        phase_usage = {
            "available": True,
            "tracking_lane": lane,
            "source_requests": phase_requests,
            "source_request_ceiling": int(phase["phase_request_ceiling"]),
            "source_requests_within_ceiling": (
                phase_requests <= int(phase["phase_request_ceiling"])
            ),
            "scheduler_rows": phase_jobs,
            "scheduler_row_ceiling": int(phase["phase_scheduler_ceiling"]),
            "scheduler_rows_within_ceiling": (
                phase_jobs <= int(phase["phase_scheduler_ceiling"])
            ),
            "holder_fallbacks": holder_fallbacks,
            "holder_fallback_ceiling": int(phase["holder_fallback_max"]),
            "automatic_retries": 0,
            "endpoint_rotation": False,
        }
        phase_usage["within_ceiling"] = (
            phase_usage["source_requests_within_ceiling"]
            and phase_usage["scheduler_rows_within_ceiling"]
            and holder_fallbacks <= phase_usage["holder_fallback_ceiling"]
        )
        cumulative_usage = {
            "available": True,
            "tracking_lane": lane,
            "source_requests": cumulative_requests,
            "source_request_ceiling": int(cumulative["request_ceiling"]),
            "source_requests_within_ceiling": (
                cumulative_requests <= int(cumulative["request_ceiling"])
            ),
            "scheduler_rows": cumulative_scheduler_rows,
            "scheduler_row_ceiling": int(cumulative["scheduler_ceiling"]),
            "scheduler_rows_within_ceiling": (
                cumulative_scheduler_rows <= int(cumulative["scheduler_ceiling"])
            ),
            "discovery_source_requests": discovery_requests,
            "runtime_source_requests": runtime_requests,
            "request_components": cumulative["request_components"],
            "scheduler_components": cumulative["scheduler_components"],
            "policy_derived": True,
        }
        cumulative_usage["within_ceiling"] = (
            cumulative_usage["source_requests_within_ceiling"]
            and cumulative_usage["scheduler_rows_within_ceiling"]
        )
        token_ceiling = int(cumulative["request_ceiling"]) - int(
            cumulative["request_components"]["discovery"]
        )
        return {
            "four_hour_phase_usage": phase_usage,
            "cumulative_lifecycle_usage": cumulative_usage,
            # Compatibility fields now use the applicable cumulative policy.
            "governed_requests_run": cumulative_requests,
            "governed_requests_run_ceiling": int(cumulative["request_ceiling"]),
            "governed_requests_run_within_ceiling": cumulative_usage[
                "source_requests_within_ceiling"
            ],
            "governed_requests_per_token": {"selected_token": runtime_requests},
            "governed_requests_per_token_ceiling": token_ceiling,
            "governed_requests_per_token_within_ceiling": (
                runtime_requests <= token_ceiling
            ),
            "holder_rpc_fallbacks": holder_fallbacks,
            "holder_rpc_fallbacks_ceiling": int(phase["holder_fallback_max"]),
            "scheduler_run_step_jobs": all_step_jobs,
            "scheduler_cancelled_discovery_handoffs": handoffs,
            "scheduler_rows_total": cumulative_scheduler_rows,
            "scheduler_rows_ceiling": int(cumulative["scheduler_ceiling"]),
            "scheduler_rows_within_ceiling": cumulative_usage[
                "scheduler_rows_within_ceiling"
            ],
            "discovery_requests_ceiling": int(
                cumulative["request_components"]["discovery"]
            ),
            "automatic_retries": 0,
            "continuous_first_hour": continuous,
        }

    prefixes = sorted({_token_prefix(s["step_key"]) for s in steps})
    per_token = {p: _token_request_count(conn, run_id, p) for p in prefixes}
    run_ceiling = (
        _CONTINUOUS_MAX_REQUESTS_RUN if continuous
        else _MAX_GOVERNED_REQUESTS_RUN
    )
    token_ceiling = (
        _CONTINUOUS_MAX_REQUESTS_PER_TOKEN
        if continuous else _MAX_GOVERNED_REQUESTS_PER_TOKEN
    )
    scheduler_ceiling = (
        _CONTINUOUS_MAX_SCHEDULER_ROWS if continuous else _MAX_SCHEDULER_ROWS
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
            _MAX_HOLDER_FALLBACKS_PER_TOKEN * max(1, len(prefixes))
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


def _four_hour_terminal_validation(
    *, config: dict[str, Any], steps: list[dict[str, Any]],
    windows_by_id: dict[int, dict[str, Any]], budgets: dict[str, Any],
    pending_steps: int, running_jobs: int,
) -> dict[str, Any]:
    """Independently prove a complete, audited terminal WINDOW_4H outcome."""
    if not config.get("continuous_four_hour"):
        return {
            "enabled": False,
            "complete": True,
            "reasons": [],
            "failure_reasons": [],
        }
    long_steps = [
        step for step in steps
        if str(step.get("step_kind", "")).startswith("LONG_CONTINUATION_")
    ]
    close_steps = [
        step for step in long_steps
        if step.get("step_kind") == "LONG_CONTINUATION_CLOSE"
    ]
    lane = str(long_steps[0].get("tracking_lane")) if long_steps else ""
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
    if expected == 0:
        reasons.append("missing_4h_cadence_policy")
    if actual != expected:
        reasons.append(f"incomplete_4h_collection:{actual}/{expected}")
    if len(close_steps) != 1:
        reasons.append("missing_or_ambiguous_forced_close")
        close = None
    else:
        close = close_steps[0]
        if close.get("step_status") != "SUCCEEDED":
            reasons.append(
                f"forced_close_not_succeeded:{close.get('step_status')}"
            )
    successor = None
    audit_path_complete = False
    if close is not None:
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
    phase = budgets.get("four_hour_phase_usage", {})
    cumulative = budgets.get("cumulative_lifecycle_usage", {})
    if not phase.get("within_ceiling", False):
        reasons.append("four_hour_phase_budget_exceeded")
    if not cumulative.get("within_ceiling", False):
        reasons.append("cumulative_lifecycle_budget_exceeded")
    if pending_steps:
        reasons.append(f"pending_or_running_steps:{pending_steps}")
    if running_jobs:
        reasons.append(f"running_jobs:{running_jobs}")
    if failure_reasons:
        reasons.append("terminal_4h_step_failure")
    complete = not reasons
    if complete:
        run_status = "COMPLETED"
        stop_reason = STOP_COMPLETED
    elif source_failure_reasons:
        run_status = "FAILED"
        stop_reason = STOP_SOURCE
    elif any("budget_exceeded" in reason for reason in reasons):
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
        "reasons": reasons,
        "failure_reasons": failure_reasons,
        "source_failure_reasons": source_failure_reasons,
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
    }


def _final_report(
    conn: sqlite3.Connection, *, run_id: str, config: dict[str, Any],
    discovery: dict[str, Any], before: dict[str, int], stop_reason: str,
    started_at: str,
) -> dict[str, Any]:
    after = _counts(conn)
    deltas = _deltas(before, after)
    steps = [dict(row) for row in conn.execute(
        "SELECT * FROM printer_memory_factory_run_steps WHERE run_id=? ORDER BY scheduled_for, id", (run_id,)
    ).fetchall()]
    jobs = [dict(row) for row in conn.execute(
        "SELECT j.* FROM printer_scheduler_jobs j JOIN printer_memory_factory_run_steps s ON s.scheduler_job_id=j.id WHERE s.run_id=? ORDER BY j.id",
        (run_id,),
    ).fetchall()]
    running = sum(1 for job in jobs if job["status"] == "RUNNING" or job["locked_at"] or job["lock_owner"])
    forbidden = {table: deltas.get(table, 0) for table in _FORBIDDEN_DELTA_TABLES}
    windows = [dict(row) for row in conn.execute(
        "SELECT * FROM printer_memory_windows WHERE id IN (SELECT memory_window_id FROM printer_memory_factory_run_steps WHERE run_id=? AND memory_window_id IS NOT NULL)",
        (run_id,),
    ).fetchall()]
    selected = _selected_targets(conn, discovery.get("selection_handoff_report", {}).get("batch_id") or "")
    windows_by_id = {int(w["id"]): w for w in windows}
    per_token = _per_token_outcomes(steps, windows_by_id)
    terminal_window_outcomes = sum(1 for t in per_token if t["reached_terminal_window"])
    budgets = _run_budgets(conn, run_id, discovery, steps)
    lifecycle = _continuous_lifecycle_report(conn, run_id, steps)
    pending_run_steps = sum(1 for s in steps if s["step_status"] in {"PENDING", "RUNNING"})
    terminal_validation = _four_hour_terminal_validation(
        config=config, steps=steps, windows_by_id=windows_by_id,
        budgets=budgets, pending_steps=pending_run_steps, running_jobs=running,
    )
    effective_status = "COMPLETED" if stop_reason == STOP_COMPLETED else "SAFE_STOPPED"
    effective_reason = stop_reason
    if terminal_validation.get("enabled"):
        effective_status = str(terminal_validation["run_status"])
        effective_reason = str(terminal_validation["stop_reason"])
    return {
        "command": COMMAND_NAME, "policy_version": POLICY_VERSION,
        "run_id": run_id, "run_status": effective_status,
        "stop_reason": effective_reason, "started_at": started_at, "finished_at": _iso(),
        "config": config, "selection_seed": discovery.get("selection_handoff_report", {}).get("selection_seed"),
        "eligible_pool_size": discovery.get("selection_handoff_report", {}).get("eligible_pool_size", 0),
        "selected_tokens": selected, "discovery_report": discovery,
        "scheduler_jobs": jobs, "steps": steps, "memory_windows": windows,
        # V2-5: authoritative per-token outcomes and run-local yield, keyed by
        # run_id/step/target/attached memory-window id. These, not embedded Lane
        # K/E2Z pipeline summaries, are authoritative for yield and verdict.
        "per_token_outcomes": per_token,
        "terminal_window_outcomes": terminal_window_outcomes,
        "run_local_yield": {
            "clean": sum(1 for t in per_token if t["terminal_status"] == "CLEAN"),
            "dirty": sum(1 for t in per_token if t["terminal_status"] == "DIRTY"),
            "blocked": sum(1 for t in per_token if t["terminal_status"] in {"BLOCKED_QUALITY", "TERMINAL_BLOCKED"}),
            "token_local_failed": sum(1 for t in per_token if t["terminal_status"] == "TOKEN_LOCAL_FAILED"),
            "authoritative_source": "run_step_attached_memory_window_ids",
            "zero_clean_is_valid": True,
        },
        "historical_report_note": (
            "Lane K/E2Z pipeline summaries embedded in step result_json may include "
            "historical windows copied into the proof DB. They are NOT authoritative for "
            "per-token yield or verdict; only per_token_outcomes and run_local_yield "
            "(run-step-attached memory_window_ids) are authoritative."
        ),
        "run_budgets": budgets,
        "four_hour_phase_usage": budgets.get("four_hour_phase_usage"),
        "cumulative_lifecycle_usage": budgets.get("cumulative_lifecycle_usage"),
        "four_hour_terminal_validation": terminal_validation,
        "continuous_lifecycle": lifecycle,
        "pending_or_running_run_steps": pending_run_steps,
        "memory_results": {
            "clean": sum(1 for row in windows if row.get("memory_quality_label") == "CLEAN_MEMORY"),
            "dirty_or_audit_only": sum(1 for row in windows if row.get("memory_quality_label") in {"DIRTY_MEMORY", "AUDIT_ONLY_MEMORY", "DO_NOT_TRAIN"}),
            "blocked_or_partial": sum(1 for row in windows if row.get("memory_quality_label") not in {"CLEAN_MEMORY", "DIRTY_MEMORY", "AUDIT_ONLY_MEMORY", "DO_NOT_TRAIN"}),
            "zero_clean_is_valid": True,
        },
        "counts_before": before, "counts_after": after, "table_deltas": deltas,
        "forbidden_deltas": forbidden, "running_jobs_after_stop": running,
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


def run_one_command_15m_factory(
    db_path: str | Path, backup_path: str | Path, *, operator_approved: bool,
    proof_mode: bool, window_kind: str = WINDOW_KIND, max_selected_tokens: int = 2,
    max_source_requests: int = 2, timeout_seconds: float = 5.0,
    total_duration_seconds: float = 1200.0, selection_seed: str | None = None,
    v2_5_proof_mode: bool = False,
    continuous_first_hour: bool = False,
    continuous_four_hour: bool = False,
    four_hour_proof_mode: bool = False,
    discovery_transport: Any = None, discovery_runner: Callable[..., dict[str, Any]] | None = None,
    snapshot_adapter_factory: Callable[..., Any] | None = None,
    context_adapter_factories: dict[str, Callable[..., Any]] | None = None,
    _window_seconds: float = 900.0, _sleep: Callable[[float], None] = time.sleep,
    _monotonic: Callable[[], float] = time.monotonic,
    _continuation_seconds: float = _CONTINUATION_SECONDS,
) -> dict[str, Any]:
    path = Path(db_path).resolve()
    backup = Path(backup_path).resolve()
    reasons: list[str] = []
    if not operator_approved: reasons.append("operator approval required")
    if not proof_mode: reasons.append("first V2-4 command supports proof mode only")
    if window_kind != WINDOW_KIND: reasons.append(f"unsupported window_kind: {window_kind}")
    if not path.is_file(): reasons.append(f"proof DB missing: {path}")
    if not backup.is_file(): reasons.append(f"backup missing: {backup}")
    if _is_persistent_db(path): reasons.append("persistent DB is forbidden in first proof")
    # V2-5: the explicit three-token proof mode permits exactly three autonomous
    # tokens. Normal mode stays capped at two. Four or more is always rejected.
    if continuous_first_hour:
        if max_selected_tokens != _CONTINUOUS_MAX_SELECTED_TOKENS:
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
    required_duration = _window_seconds + (_continuation_seconds if continuous_first_hour else 0.0) + (10_800.0 if continuous_four_hour else 0.0)
    if total_duration_seconds <= required_duration:
        reasons.append("total duration must exceed the complete approved lifecycle duration")
    if reasons:
        return {"command": COMMAND_NAME, "run_status": "SAFE_STOPPED", "stop_reason": STOP_PREFLIGHT, "blocked_reasons": reasons}

    from printer_v1.operator_cli.commands import build_discover_candidates_once_payload
    from printer_v1.operator_cli.e2i_source_transport import build_e2i_dexscreener_adapter

    discovery_callable = discovery_runner or build_discover_candidates_once_payload
    adapter_factory = snapshot_adapter_factory or build_e2i_dexscreener_adapter
    config = {
        "db_mode": "PROOF_ONLY", "db_path": str(path), "backup_path": str(backup),
        "window_kind": window_kind, "max_selected_tokens": max_selected_tokens,
        "max_source_requests": max_source_requests, "timeout_seconds": timeout_seconds,
        "total_duration_seconds": total_duration_seconds, "window_seconds": _window_seconds,
        "automatic_retries": 0, "discovery_source": "geckoterminal",
        "context_source_requests_per_selected_token": 5,
        "context_source_request_budget": 5 * max_selected_tokens,
        "v2_5_proof_mode": bool(v2_5_proof_mode),
        "continuous_first_hour": bool(continuous_first_hour),
        "continuous_four_hour": bool(continuous_four_hour),
        "four_hour_proof_mode": bool(four_hour_proof_mode),
        "continuation_seconds": _continuation_seconds if continuous_first_hour else 0.0,
        "hard_ceilings": {
            "discovery_requests": _MAX_DISCOVERY_REQUESTS,
            "governed_requests_run": _MAX_GOVERNED_REQUESTS_RUN,
            "governed_requests_per_token": _MAX_GOVERNED_REQUESTS_PER_TOKEN,
            "holder_fallbacks_per_token": _MAX_HOLDER_FALLBACKS_PER_TOKEN,
            "scheduler_rows": _MAX_SCHEDULER_ROWS,
            "total_duration_seconds": total_duration_seconds,
            "automatic_retries": 0,
            "continuous_governed_requests_run": _CONTINUOUS_MAX_REQUESTS_RUN,
            "continuous_governed_requests_per_token": _CONTINUOUS_MAX_REQUESTS_PER_TOKEN,
            "continuous_scheduler_rows": _CONTINUOUS_MAX_SCHEDULER_ROWS,
        },
    }
    run_id = str(uuid.uuid4())
    started_dt = _now()
    started_at = _iso(started_dt)
    conn = sqlite3.connect(str(path))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys=ON")
    _require_schema(conn)
    before = _counts(conn)
    conn.execute(
        "INSERT INTO printer_memory_factory_runs (run_id,run_status,window_kind,db_mode,config_hash,config_json,started_at,created_at,updated_at) VALUES (?,'RUNNING',?,'PROOF_ONLY',?,?,?,?,?)",
        (run_id, window_kind, _config_hash(config), _json(config), started_at, started_at, started_at),
    )
    conn.commit()
    discovery: dict[str, Any] = {}
    stop_reason = STOP_COMPLETED
    start_mono = _monotonic()
    try:
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
        conn.execute(
            "UPDATE printer_memory_factory_runs SET selection_seed=?,selection_batch_id=?,eligible_pool_size=?,selected_token_count=?,updated_at=? WHERE run_id=?",
            (handoff.get("selection_seed"), batch_id, handoff.get("eligible_pool_size", 0), len(targets), _iso(), run_id),
        )
        _cancel_discovery_handoffs(conn, discovery)
        if not targets:
            stop_reason = STOP_EMPTY
        else:
            _plan_opening_jobs(conn, run_id, targets, _now())
        conn.commit()

        while stop_reason == STOP_COMPLETED:
            pending = conn.execute(
                "SELECT s.* FROM printer_memory_factory_run_steps s WHERE s.run_id=? AND s.step_status='PENDING' ORDER BY s.scheduled_for,s.id LIMIT 1",
                (run_id,),
            ).fetchone()
            if pending is None:
                break
            elapsed = _monotonic() - start_mono
            if elapsed >= total_duration_seconds:
                stop_reason = STOP_DURATION
                break
            due = datetime.fromisoformat(str(pending["scheduled_for"]))
            wait = max(0.0, (due - _now()).total_seconds())
            if wait:
                _sleep(min(wait, max(0.0, total_duration_seconds - elapsed)))
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
            conn.commit()
            token_id = int(pending["token_id"])
            try:
                # Hard ceilings are integrity limits; a projected breach is a
                # global safe stop (raises _GlobalStop), never an exceeded call.
                _enforce_budgets_before_step(conn, run_id, pending)
                if pending["step_kind"] == "WINDOW_CLOSE":
                    result = _execute_close(
                        conn, pending, adapter_factory=adapter_factory,
                        timeout_seconds=timeout_seconds,
                        minimum_evidence_seconds=_window_seconds,
                        context_adapter_factories=context_adapter_factories,
                    )
                elif pending["step_kind"] == "CONTINUATION_CLOSE":
                    result = _execute_continuation_close(
                        conn,
                        pending,
                        adapter_factory=adapter_factory,
                        timeout_seconds=timeout_seconds,
                    )
                elif str(pending["step_kind"]).startswith("LONG_CONTINUATION_"):
                    result = _execute_long_4h_step(
                        conn,
                        pending,
                        adapter_factory=adapter_factory,
                        timeout_seconds=timeout_seconds,
                        context_adapter_factories=context_adapter_factories,
                    )
                else:
                    result = _execute_snapshot(
                        conn, pending, adapter_factory=adapter_factory,
                        timeout_seconds=timeout_seconds,
                    )
                if result.get("ok"):
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
                        )
                    elif pending["step_kind"] == "WINDOW_CLOSE" and continuous_first_hour:
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
                        )
                        if not plan.get("planned"):
                            raise ValueError("4h planning blocked: " + "; ".join(plan.get("blocked_reasons", [])))
                        result["four_hour_plan"] = plan
                    _update_step(conn, int(pending["id"]), "SUCCEEDED", result)
                    complete_job(conn, job_id=job_id)
                    conn.commit()
                else:
                    # V2-5 token-local terminal failure: isolate this token,
                    # cancel only its remaining pending jobs, continue others.
                    error = str(result.get("blocked_reason") or "governed step blocked")
                    _update_step(conn, int(pending["id"]), "FAILED", result, error=error)
                    fail_job(conn, job_id=job_id, error=error, max_retries=0)
                    _cancel_pending_for_token(conn, run_id, token_id, TOKEN_LOCAL_CANCELLED)
                    conn.commit()
            except _GlobalStop as gstop:
                # Global integrity/budget breach cancels the entire run.
                stop_reason = gstop.reason
                _update_step(conn, int(pending["id"]), "FAILED", {"ok": False, "global_stop": gstop.reason}, error=gstop.reason)
                fail_job(conn, job_id=job_id, error=gstop.reason, max_retries=0)
                conn.commit()
            except Exception as exc:
                # Unexpected token-local failure: isolate this token, continue.
                result = {"ok": False, "exception": f"{type(exc).__name__}: {exc}"}
                _update_step(conn, int(pending["id"]), "FAILED", result, error=result["exception"])
                fail_job(conn, job_id=job_id, error=result["exception"], max_retries=0)
                _cancel_pending_for_token(conn, run_id, token_id, TOKEN_LOCAL_CANCELLED)
                conn.commit()
    except KeyboardInterrupt:
        stop_reason = STOP_INTERRUPTED
    except Exception as exc:
        stop_reason = STOP_PREFLIGHT
        discovery = {**discovery, "orchestration_error": f"{type(exc).__name__}: {exc}"}
    finally:
        _cancel_pending(conn, run_id, stop_reason)
        conn.commit()
        report = _final_report(
            conn, run_id=run_id, config=config, discovery=discovery, before=before,
            stop_reason=stop_reason, started_at=started_at,
        )
        if report["running_jobs_after_stop"]:
            report["stop_reason"] = STOP_RUNNING
            report["run_status"] = "SAFE_STOPPED"
        if any(report["forbidden_deltas"].values()):
            report["stop_reason"] = STOP_DB_DELTA
            report["run_status"] = "SAFE_STOPPED"
        conn.execute(
            "UPDATE printer_memory_factory_runs SET run_status=?,stop_reason=?,finished_at=?,final_report_json=?,updated_at=? WHERE run_id=?",
            (report["run_status"], report["stop_reason"], report["finished_at"], _json(report), _iso(), run_id),
        )
        conn.commit()
        conn.close()
    return report
