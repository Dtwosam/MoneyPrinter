"""Lane X12 — WINDOW_1H Bounded Memory Growth Runner.

Provides 1h continuation-phase memory for TRACK_FAST and TRACK_NORMAL tokens.
Two modes: TRACK_FAST (1-5 tokens) and TRACK_NORMAL (1-7 tokens).
Separate CLI commands per mode prevent lane mixing in a single run.
WINDOW_1H only — WINDOW_15M, WINDOW_5M_MICRO_EVENT, and 4h/12h/24h windows
are all rejected at the pre-flight gate.

This runner is the Lane X12 structural implementation.  It does NOT run a live
proof against the production DB.  That requires a separate operator-approved
X12 proof run using the bounded CLI commands with real token lists.

Token list format (same field names as X5 / X10.10B):

  {
    "tokens": [
      {
        "token_mint": "<MINT>",
        "pair_address": "<PAIR>",
        "chain": "solana",
        "tracking_lane": "TRACK_FAST",  // or "TRACK_NORMAL"
        "operator_approved": true
      }
    ]
  }

TRACK_FAST mode: 1-5 tokens, all must have tracking_lane = "TRACK_FAST".
TRACK_NORMAL mode: 1-7 tokens, all must have tracking_lane = "TRACK_NORMAL".

Snapshot cadence (from frequency.py, 1h-continuation phase):
  TRACK_FAST:   240s interval (~11 snapshots per 2700s window)
  TRACK_NORMAL: 720s interval (~4 snapshots per 2700s window)

Window close interval: 2700s (45-minute continuation phase, t=15m → t=60m).

Freshness policy:
  TRACK_FAST:   hard gate (X10.9 rules — stale blocks the run)
  TRACK_NORMAL: advisory only (stale logs warning, never blocks)
  Freshness gate skipped when _adapter_map is not None (test-fixture mode).

Hard rules (all V1 locks preserved):
- Operator approval required.
- WINDOW_1H only.  No WINDOW_15M, no 5m main, no 4h/12h/24h.
- No BUY/SELL/HOLD. No paper decisions. No positions. No PnL.
- No retrieval activation. No scoring/ranking/confidence/weighted logic.
- No wallet/private keys. No live trading. No paid APIs.
- No Source Governor bypass. No Central Scheduler bypass.
- No token/pair mixing. Separate evidence identity per token.
- Source budget cannot be bypassed.
- Zero clean memories is always a valid outcome.
- No fake WINDOW_1H assembled from WINDOW_15M snapshots.
"""

from __future__ import annotations

import json
import sqlite3
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping, Sequence


# ---------------------------------------------------------------------------
# Public constants
# ---------------------------------------------------------------------------

LANE_X12_FAST_COMMAND_NAME: str = "printer-run-lane-x12-fast-1h-cycle"
LANE_X12_NORMAL_COMMAND_NAME: str = "printer-run-lane-x12-normal-1h-cycle"

LANE_X12_STATUS_COMPLETED: str = "LANE_X12_COMPLETED"
LANE_X12_STATUS_BLOCKED: str = "LANE_X12_BLOCKED"
LANE_X12_STATUS_STOPPED: str = "LANE_X12_STOPPED"

# Mode identifiers
LANE_X12_MODE_FAST: str = "TRACK_FAST"
LANE_X12_MODE_NORMAL: str = "TRACK_NORMAL"

# Token count limits per mode
LANE_X12_FAST_MIN_TOKEN_COUNT: int = 1
LANE_X12_FAST_MAX_TOKEN_COUNT: int = 5
LANE_X12_NORMAL_MIN_TOKEN_COUNT: int = 1
LANE_X12_NORMAL_MAX_TOKEN_COUNT: int = 7

# ---------------------------------------------------------------------------
# Private constants
# ---------------------------------------------------------------------------

_TL_TRACKING_LANE: str = "tracking_lane"
_TL_OPERATOR_APPROVED: str = "operator_approved"
_TL_CHAIN: str = "chain"
_TL_TOKEN_MINT: str = "token_mint"
_TL_PAIR_ADDRESS: str = "pair_address"
# V2-6.3: optional per-token linkage to the preceding closed 15m window that
# this 1h phase continues (id, snapshot_end_id, closed_at, run_id, tracking_lane).
_TL_CONTINUATION_OF_15M: str = "continuation_of_15m"

_REQUIRED_CHAIN: str = "solana"
_PLACEHOLDER_PREFIX: str = "PLACEHOLDER"

_DURATION_PROFILES: dict[str, int] = {
    "1h": 3600,
    "4h": 14400,
    "6h": 21600,
    "12h": 43200,
    "24h": 86400,
}
_LONG_RUN_PROFILES: frozenset[str] = frozenset({"12h", "24h"})
_DEFAULT_PROFILE: str = "4h"

# Window kind policy
_ENABLED_MAIN_WINDOW_KIND: str = "WINDOW_1H"
_DISABLED_COLLECTION_WINDOW_KINDS: frozenset[str] = frozenset(
    {"WINDOW_15M", "WINDOW_4H", "WINDOW_12H", "WINDOW_24H"}
)
_FORBIDDEN_AS_MAIN_WINDOW: frozenset[str] = frozenset({"WINDOW_5M_MICRO_EVENT"})

# Job / step constants per mode
_FAST_JOB_KIND: str = "TRACK_FAST_1H"
_FAST_JOB_NAME_PREFIX: str = "x12_track_fast_1h_slot"
_FAST_LOCK_OWNER_PREFIX: str = "lane_x12_fast_1h_slot"

_NORMAL_JOB_KIND: str = "TRACK_NORMAL_1H"
_NORMAL_JOB_NAME_PREFIX: str = "x12_track_normal_1h_slot"
_NORMAL_LOCK_OWNER_PREFIX: str = "lane_x12_normal_1h_slot"

# Slots: FAST uses A-E (max 5); NORMAL uses A-G (max 7).
_ALL_SLOTS: tuple[str, ...] = ("A", "B", "C", "D", "E", "F", "G")

# Step status strings
_X12_STEP_EXECUTED: str = "X12_1H_CYCLE_EXECUTED"
_X12_STEP_BLOCKED: str = "X12_1H_CYCLE_BLOCKED"

# Default cadence parameters — derived from the single authoritative cadence
# policy (V2-6.1a) so the 1h-phase collection rate can never drift from the
# contract. WINDOW_1H: TRACK_FAST 120s (min 24), TRACK_NORMAL 240s (min 13).
def _policy_1h_interval(lane: str, fallback: float) -> float:
    from printer_v1.snapshots.cadence_policy import get_policy as _get_policy
    p = _get_policy("WINDOW_1H", lane)
    return float(p.target_snapshot_interval_seconds) if p is not None else fallback


_DEFAULT_FAST_SNAPSHOT_INTERVAL_SECONDS: float = _policy_1h_interval("TRACK_FAST", 120.0)
_DEFAULT_NORMAL_SNAPSHOT_INTERVAL_SECONDS: float = _policy_1h_interval("TRACK_NORMAL", 240.0)
_DEFAULT_WINDOW_CLOSE_INTERVAL_SECONDS: float = 2700.0    # 45-min continuation window

_DEFAULT_SOURCE_BUDGET_MAX_CONSECUTIVE_FAILURES: int = 5
_DEFAULT_THROTTLE_BACKOFF_SECONDS: float = 0.0

_HARD_LOCKS: dict[str, bool] = {
    "no_buy_sell_hold": True,
    "no_paper_decisions": True,
    "no_positions": True,
    "no_pnl": True,
    "no_retrieval_activation": True,
    "no_live_trading": True,
    "no_paid_api": True,
    "no_wallet_private_key": True,
    "no_generic_search": True,
    "no_unbounded_loop": True,
    "no_daemon_mode": True,
    "no_scheduler_bypass": True,
    "no_source_governor_bypass": True,
    "no_ad_hoc_api_loop": True,
    "no_direct_adapter_call": True,
    "no_scoring_ranking_confidence": True,
    "no_embeddings_vectors": True,
    "no_4h_12h_24h_collection": True,
    "no_window_15m_in_1h_runner": True,
    "no_5m_main_window": True,
    "no_trade_events": True,
    "no_paper_trade_audits": True,
    "no_token_pair_mixing": True,
    "no_source_budget_bypass": True,
    "no_fake_1h_from_15m": True,
    "no_lane_mixing_fast_normal": True,
}

_FORBIDDEN_WRITE_TABLES: tuple[str, ...] = (
    "printer_paper_decisions",
    "printer_paper_positions",
    "printer_paper_trade_events",
    "printer_paper_trade_audits",
    "printer_paper_audit_reports",
    "printer_retrieval_candidates",
    "printer_retrieval_results",
)

_AUDIT_TABLES: tuple[str, ...] = (
    "printer_source_requests",
    "printer_source_responses",
    "printer_source_failures",
    "printer_scheduler_jobs",
    "printer_token_snapshots",
    "printer_memory_windows",
)


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _elapsed(start: float) -> float:
    return time.monotonic() - start


def _count_table_rows(db_path: str | Path, table: str) -> int:
    try:
        conn = sqlite3.connect(str(db_path))
        try:
            return int(conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0])
        except Exception:
            return 0
        finally:
            conn.close()
    except Exception:
        return 0


def _count_table(db_path: str | Path, table: str) -> int:
    try:
        conn = sqlite3.connect(str(db_path))
        try:
            row = conn.execute(
                "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (table,)
            ).fetchone()
            if row is None:
                return 0
            return int(conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0])
        finally:
            conn.close()
    except Exception:
        return 0


def _get_audit_counts(db_path: str | Path) -> dict[str, int]:
    return {t: _count_table_rows(db_path, t) for t in _AUDIT_TABLES}


def _check_forbidden_tables(db_path: str | Path) -> dict[str, int]:
    return {t: _count_table(db_path, t) for t in _FORBIDDEN_WRITE_TABLES}


# ---------------------------------------------------------------------------
# Continuation planning seam (V2-6.3)
# ---------------------------------------------------------------------------

def plan_1h_continuation(token_entry: Mapping[str, Any]) -> dict[str, Any]:
    """Live planning path for a token's 1h continuation.

    Delegates to the V2-6.2 contract's ``build_1h_continuation_plan`` so the
    continuation is enqueued at the *exact 15m close* and the deadline is fixed at
    ``15m close + 2700s``. The deadline is derived solely from the preceding 15m
    window's close, so a delayed first snapshot (or delayed planning) can never
    extend it. Returns ``{"is_continuation": False}`` when the token carries no
    continuation linkage (a first-cycle / non-continuation 1h phase).
    """
    from printer_v1.snapshots.lifecycle_continuity import build_1h_continuation_plan

    fifteen_m = token_entry.get(_TL_CONTINUATION_OF_15M)
    if not fifteen_m:
        return {"is_continuation": False, "plan": None}
    plan = build_1h_continuation_plan(fifteen_m)
    return {
        "is_continuation": True,
        "plan": plan,
        "enqueue_at": plan.get("enqueue_at"),
        "deadline_at": plan.get("deadline_at"),
        "deadline_anchored_to": plan.get("deadline_anchored_to"),
        "continuation_of_window_id": plan.get("continuation_of_window_id"),
        "linked_closing_snapshot_id": plan.get("linked_closing_snapshot_id"),
        "enqueue_ok": plan.get("enqueue_ok"),
        "reasons": plan.get("reasons", []),
    }


# ---------------------------------------------------------------------------
# Token list validator
# ---------------------------------------------------------------------------

def _load_and_validate_token_list(
    path: str | Path | None,
    mode: str,
) -> tuple[bool, str, list[dict[str, Any]]]:
    """Validate 1-5 (TRACK_FAST) or 1-7 (TRACK_NORMAL) Solana tokens.

    Returns (valid, reason, tokens_list).
    All tokens must have the tracking_lane matching mode.
    WATCH_ONLY, IGNORE, INSTANT_REJECT, COOLDOWN, ARCHIVED are rejected.
    """
    if path is None:
        return False, "token_list_path is required", []
    try:
        data = json.loads(Path(path).read_text(encoding="utf-8"))
    except FileNotFoundError:
        return False, f"token list file not found: {path}", []
    except (json.JSONDecodeError, OSError) as exc:
        return False, f"token list file unreadable: {exc}", []

    tokens: list[dict[str, Any]] = list(data.get("tokens", []))

    if mode == LANE_X12_MODE_FAST:
        min_count = LANE_X12_FAST_MIN_TOKEN_COUNT
        max_count = LANE_X12_FAST_MAX_TOKEN_COUNT
    else:
        min_count = LANE_X12_NORMAL_MIN_TOKEN_COUNT
        max_count = LANE_X12_NORMAL_MAX_TOKEN_COUNT

    if len(tokens) < min_count:
        return (
            False,
            f"Lane X12 {mode} mode requires at least {min_count} token;"
            f" found {len(tokens)}",
            [],
        )
    if len(tokens) > max_count:
        return (
            False,
            f"Lane X12 {mode} mode accepts at most {max_count} tokens;"
            f" found {len(tokens)}",
            [],
        )

    _REJECTED_LANES: frozenset[str] = frozenset(
        {"WATCH_ONLY", "IGNORE", "INSTANT_REJECT", "COOLDOWN", "ARCHIVED"}
    )

    errors: list[str] = []
    for i, tok in enumerate(tokens):
        lane = str(tok.get(_TL_TRACKING_LANE, ""))
        approved = bool(tok.get(_TL_OPERATOR_APPROVED, False))
        chain = str(tok.get(_TL_CHAIN, ""))
        mint = str(tok.get(_TL_TOKEN_MINT, ""))
        pair = str(tok.get(_TL_PAIR_ADDRESS, ""))

        if lane != mode:
            if lane in _REJECTED_LANES:
                errors.append(
                    f"token[{i}]: tracking_lane {lane!r} is not allowed in"
                    " Lane X12; only {mode!r} tokens are accepted in {mode} mode"
                )
            else:
                errors.append(
                    f"token[{i}]: tracking_lane must be {mode!r} for"
                    f" Lane X12 {mode} mode; got {lane!r}"
                )
        if not approved:
            errors.append(f"token[{i}]: operator_approved must be true")
        if chain != _REQUIRED_CHAIN:
            errors.append(
                f"token[{i}]: chain must be {_REQUIRED_CHAIN!r}; got {chain!r}"
            )
        if not mint or mint.startswith(_PLACEHOLDER_PREFIX):
            errors.append(f"token[{i}]: invalid or placeholder token_mint: {mint!r}")
        if not pair or pair.startswith(_PLACEHOLDER_PREFIX):
            errors.append(
                f"token[{i}]: pair_address is required and must not be a placeholder:"
                f" {pair!r}"
            )

    if errors:
        return False, "; ".join(errors), []

    mints = [str(t.get(_TL_TOKEN_MINT, "")) for t in tokens]
    if len(set(mints)) != len(tokens):
        return (
            False,
            f"duplicate token_mint detected: {mints}; all tokens must have distinct mints",
            [],
        )

    pairs = [str(t.get(_TL_PAIR_ADDRESS, "")) for t in tokens]
    if len(set(pairs)) != len(tokens):
        return (
            False,
            f"duplicate pair_address detected: {pairs};"
            " all tokens must have distinct pair addresses",
            [],
        )

    mint_list = ", ".join(f"{m!r}" for m in mints)
    return (
        True,
        f"{len(tokens)} {mode} approved solana token(s) validated: {mint_list}",
        tokens,
    )


# ---------------------------------------------------------------------------
# Per-token scheduler job helpers
# ---------------------------------------------------------------------------

def _create_x12_job(
    connection: sqlite3.Connection, slot: str, mode: str
) -> int:
    running = int(
        connection.execute(
            "SELECT COUNT(*) FROM printer_scheduler_jobs WHERE status = 'RUNNING'"
        ).fetchone()[0]
    )
    if running:
        raise ValueError(
            f"Lane X12 slot {slot}: {running} RUNNING job(s) already exist;"
            " cannot create new job while another is active"
        )
    job_kind = _FAST_JOB_KIND if mode == LANE_X12_MODE_FAST else _NORMAL_JOB_KIND
    job_name_prefix = (
        _FAST_JOB_NAME_PREFIX if mode == LANE_X12_MODE_FAST else _NORMAL_JOB_NAME_PREFIX
    )
    now = _utc_now()
    cursor = connection.execute(
        """
        INSERT INTO printer_scheduler_jobs (
            job_name, job_kind, target_table, target_id, priority,
            status, scheduled_for, created_at, updated_at
        )
        VALUES (?, ?, NULL, NULL, 5, 'PENDING', ?, ?, ?)
        """,
        (f"{job_name_prefix}_{slot.lower()}", job_kind, now, now, now),
    )
    return int(cursor.lastrowid)


def _claim_x12_job(
    connection: sqlite3.Connection, job_id: int, slot: str, mode: str
) -> bool:
    lock_prefix = (
        _FAST_LOCK_OWNER_PREFIX if mode == LANE_X12_MODE_FAST else _NORMAL_LOCK_OWNER_PREFIX
    )
    now = _utc_now()
    cursor = connection.execute(
        """
        UPDATE printer_scheduler_jobs
        SET status = 'RUNNING',
            lock_owner = ?,
            locked_at = ?,
            started_at = ?,
            updated_at = ?
        WHERE id = ?
          AND status = 'PENDING'
        """,
        (f"{lock_prefix}_{slot.lower()}", now, now, now, job_id),
    )
    return int(cursor.rowcount) == 1


def _complete_x12_job(connection: sqlite3.Connection, job_id: int) -> None:
    now = _utc_now()
    connection.execute(
        """
        UPDATE printer_scheduler_jobs
        SET status = 'SUCCEEDED',
            finished_at = ?,
            locked_at = NULL,
            lock_owner = NULL,
            last_error = NULL,
            updated_at = ?
        WHERE id = ?
        """,
        (now, now, job_id),
    )


def _fail_x12_job(connection: sqlite3.Connection, job_id: int, error: str) -> None:
    now = _utc_now()
    connection.execute(
        """
        UPDATE printer_scheduler_jobs
        SET status = 'FAILED',
            finished_at = ?,
            locked_at = NULL,
            lock_owner = NULL,
            retry_count = retry_count + 1,
            last_error = ?,
            updated_at = ?
        WHERE id = ?
        """,
        (now, error[:500], now, job_id),
    )


def _load_x12_job_row(
    connection: sqlite3.Connection, job_id: int
) -> sqlite3.Row | None:
    return connection.execute(
        "SELECT * FROM printer_scheduler_jobs WHERE id = ?", (job_id,)
    ).fetchone()


# ---------------------------------------------------------------------------
# Per-token step execution
# ---------------------------------------------------------------------------

def _run_x12_token_step(
    db_path: str | Path,
    mint: str,
    slot: str,
    mode: str,
    *,
    adapter: Any = None,
    close_window: bool = False,
    snapshot_start_id: int | None = None,
    pair_id_expected: int | None = None,
    continuation_of_15m: Mapping[str, Any] | None = None,
    consumed_15m_window_ids: Sequence[int] | None = None,
) -> dict[str, Any]:
    """Run one snapshot or window-close step for one token (X12 variant).

    mode: "TRACK_FAST" or "TRACK_NORMAL" — selects the correct handler.
    close_window: True triggers E2O_1H close after snapshot persistence.
    snapshot_start_id: first snapshot of the current 1h window (for E2O_1H).
    pair_id_expected: if set, enforces pair drift check in E2O_1H close.
    continuation_of_15m: when set, the E2O_1H close consumes the V2-6.2 continuity
        contract — anchoring the deadline to 15m close + 2700s, forcing
        do_not_train on a DIRTY transition, and blocking window creation on a
        BLOCKED transition (delayed restart / reused window / target drift).
    adapter: fixture adapter for tests; None = build real DexScreener adapter.
    """
    if mode == LANE_X12_MODE_FAST:
        from printer_v1.operator_cli.lane_e2h_fast_1h_handler import (
            E2H_FAST_1H_STATUS_EXECUTED,
            execute_track_fast_1h_job,
        )
        handler_fn = execute_track_fast_1h_job
        executed_status = E2H_FAST_1H_STATUS_EXECUTED
    else:
        from printer_v1.operator_cli.lane_e2h_normal_1h_handler import (
            E2H_NORMAL_1H_STATUS_EXECUTED,
            execute_track_normal_1h_job,
        )
        handler_fn = execute_track_normal_1h_job
        executed_status = E2H_NORMAL_1H_STATUS_EXECUTED

    before_counts = _get_audit_counts(db_path)

    connection = sqlite3.connect(str(db_path))
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")

    job_id: int | None = None
    handler_result: dict[str, Any] = {}
    snapshot_result: dict[str, Any] = {}
    window_result: dict[str, Any] = {}
    audit_result: dict[str, Any] = {}
    cycle_status: str = "UNKNOWN"
    exec_error: str | None = None
    snapshot_persistence_status: str = "NOT_ATTEMPTED"
    memory_window_close_status: str = "NOT_ATTEMPTED"
    snapshot_id_for_window: int | None = None
    memory_window_id: int | None = None
    window_start_at: str | None = None
    window_end_at: str | None = None
    elapsed_seconds_val: float | None = None
    lane_q_integrity_eligible: bool = False
    memory_quality_label: str | None = None
    pair_drift_detected: bool = False

    try:
        job_id = _create_x12_job(connection, slot, mode)
        connection.commit()

        claimed = _claim_x12_job(connection, job_id, slot, mode)
        if not claimed:
            raise ValueError(f"Lane X12 slot {slot}: failed to claim job {job_id}")
        connection.commit()

        job_row = _load_x12_job_row(connection, job_id)
        if job_row is None:
            raise ValueError(f"Lane X12 slot {slot}: job {job_id} not found after claim")

        if adapter is not None:
            real_adapter = adapter
        else:
            from printer_v1.operator_cli.e2i_source_transport import (
                build_e2i_dexscreener_adapter,
            )
            real_adapter = build_e2i_dexscreener_adapter(token_mint=mint)

        handler_result = handler_fn(connection, job_row, adapter=real_adapter)

        if handler_result.get("executed", False):
            source_response_id: int | None = None
            for sr in handler_result.get("source_results", []):
                if (
                    sr.get("source_name") == "dexscreener"
                    and sr.get("source_status") == "COMPLETE"
                    and sr.get("data_quality_label") == "CLEAN_DATA"
                    and sr.get("response_recorded")
                    and sr.get("source_response_id") is not None
                ):
                    source_response_id = int(sr["source_response_id"])
                    break

            if source_response_id is not None:
                from printer_v1.operator_cli.e2m_snapshot_persistence import (
                    E2M_STATUS_BLOCKED as _E2M_BLOCKED,
                    persist_snapshot_from_source_response,
                )
                snapshot_result = persist_snapshot_from_source_response(
                    connection, source_response_id, mint
                )
                snapshot_persistence_status = str(
                    snapshot_result.get("e2m_status", "UNKNOWN")
                )

                if snapshot_result.get("e2m_status") == _E2M_BLOCKED:
                    reason = "E2M_BLOCKED: " + "; ".join(
                        snapshot_result.get(
                            "blocked_reasons", ["snapshot persistence blocked"]
                        )
                    )
                    _fail_x12_job(connection, job_id, reason)
                    cycle_status = "E2M_BLOCKED"
                    exec_error = reason

                elif not close_window:
                    snapshot_id_for_window = (
                        snapshot_result.get("snapshot_id")
                        or snapshot_result.get("existing_snapshot_id")
                    )
                    _complete_x12_job(connection, job_id)
                    cycle_status = "SUCCEEDED_SNAPSHOT_ONLY"

                else:
                    snapshot_id_for_window = (
                        snapshot_result.get("snapshot_id")
                        or snapshot_result.get("existing_snapshot_id")
                    )
                    if snapshot_id_for_window is not None:
                        from printer_v1.operator_cli.lane_e2o_1h_window_close import (
                            E2O_1H_STATUS_BLOCKED as _E2O_1H_BLOCKED,
                            E2O_1H_STATUS_CONTINUITY_BLOCKED as _E2O_1H_CONTINUITY_BLOCKED,
                            close_1h_memory_window_from_snapshot,
                        )
                        window_result = close_1h_memory_window_from_snapshot(
                            connection,
                            int(snapshot_id_for_window),
                            mint,
                            snapshot_start_id=snapshot_start_id,
                            expected_pair_id=pair_id_expected,
                            continuation_of_15m=continuation_of_15m,
                            consumed_15m_window_ids=consumed_15m_window_ids,
                        )
                        memory_window_close_status = str(
                            window_result.get("e2o_1h_status", "UNKNOWN")
                        )
                        window_start_at = window_result.get("window_start_at")
                        window_end_at = window_result.get("window_end_at")
                        elapsed_seconds_val = window_result.get("elapsed_seconds")
                        lane_q_integrity_eligible = bool(
                            window_result.get("lane_q_integrity_eligible", False)
                        )
                        pair_drift_detected = bool(
                            window_result.get("pair_drift_detected", False)
                        )

                        # V2-6.3: both a hard E2O block and a BLOCKED continuity
                        # transition (delayed restart, reused historical window,
                        # target drift) prevent 1h window creation — fail the job,
                        # never fabricate a continuation.
                        if window_result.get("e2o_1h_status") in (
                            _E2O_1H_BLOCKED, _E2O_1H_CONTINUITY_BLOCKED
                        ):
                            _blk = str(window_result.get("e2o_1h_status"))
                            reason = _blk + ": " + "; ".join(
                                window_result.get(
                                    "blocked_reasons", ["memory window close blocked"]
                                )
                            )
                            _fail_x12_job(connection, job_id, reason)
                            cycle_status = _blk
                            exec_error = reason
                        else:
                            mem_window_id = (
                                window_result.get("window_id")
                                or window_result.get("existing_window_id")
                            )
                            if mem_window_id is not None:
                                memory_window_id = int(mem_window_id)
                                from printer_v1.operator_cli.e2q_memory_window_audit import (
                                    E2Q_STATUS_BLOCKED as _E2Q_BLOCKED,
                                    audit_15m_memory_window,
                                )
                                audit_result = audit_15m_memory_window(
                                    connection, int(mem_window_id)
                                )
                                memory_quality_label = audit_result.get(
                                    "memory_quality_label"
                                )
                                if audit_result.get("e2q_status") == _E2Q_BLOCKED:
                                    reason = "E2Q_BLOCKED: " + "; ".join(
                                        audit_result.get(
                                            "blocked_reasons", ["audit blocked"]
                                        )
                                    )
                                    _fail_x12_job(connection, job_id, reason)
                                    cycle_status = "E2Q_BLOCKED"
                                    exec_error = reason
                                else:
                                    _complete_x12_job(connection, job_id)
                                    cycle_status = "SUCCEEDED"
                            else:
                                _complete_x12_job(connection, job_id)
                                cycle_status = "SUCCEEDED"
                    else:
                        _complete_x12_job(connection, job_id)
                        cycle_status = "SUCCEEDED"
            else:
                _complete_x12_job(connection, job_id)
                cycle_status = "SUCCEEDED"

        else:
            reason = handler_result.get("blocked_reason") or "; ".join(
                handler_result.get("blocked_gates", ["handler blocked"])
            )
            _fail_x12_job(connection, job_id, reason)
            cycle_status = "HANDLER_BLOCKED"
            exec_error = reason

        connection.commit()

    except Exception as exc:
        exec_error = str(exc)
        cycle_status = "EXCEPTION"
        if job_id is not None:
            try:
                _fail_x12_job(connection, job_id, str(exc))
                connection.commit()
            except Exception:
                pass
    finally:
        connection.close()

    after_counts = _get_audit_counts(db_path)
    deltas: dict[str, int | str] = {}
    for t in _AUDIT_TABLES:
        b, a = before_counts.get(t, 0), after_counts.get(t, 0)
        deltas[t] = (a - b) if isinstance(b, int) and isinstance(a, int) else "unknown"

    executed = cycle_status in {"SUCCEEDED", "SUCCEEDED_SNAPSHOT_ONLY"}

    return {
        "slot": slot,
        "mint": mint,
        "mode": mode,
        "x12_step_status": _X12_STEP_EXECUTED if executed else _X12_STEP_BLOCKED,
        "executed": executed,
        "cycle_status": cycle_status,
        "close_window": close_window,
        "snapshot_id": snapshot_result.get("snapshot_id"),
        "snapshot_id_for_window": snapshot_id_for_window,
        "snapshot_start_id": snapshot_start_id,
        "snapshot_persistence_status": snapshot_persistence_status,
        "memory_window_close_status": memory_window_close_status,
        "memory_window_id": memory_window_id,
        "window_start_at": window_start_at,
        "window_end_at": window_end_at,
        "elapsed_seconds": elapsed_seconds_val,
        "lane_q_integrity_eligible": lane_q_integrity_eligible,
        "memory_quality_label": memory_quality_label,
        "pair_drift_detected": pair_drift_detected,
        "exec_error": exec_error,
        "deltas": deltas,
    }


# ---------------------------------------------------------------------------
# Blocked result helper
# ---------------------------------------------------------------------------

def _blocked_result(
    reasons: list[str],
    db_path_str: str,
    mode: str,
    duration_profile: str,
    window_kind: str,
) -> dict[str, Any]:
    return {
        "command": (
            LANE_X12_FAST_COMMAND_NAME
            if mode == LANE_X12_MODE_FAST
            else LANE_X12_NORMAL_COMMAND_NAME
        ),
        "lane_x12_status": LANE_X12_STATUS_BLOCKED,
        "mode": mode,
        "operator_approved": False,
        "db_path": db_path_str,
        "blocked_reasons": reasons,
        "selected_profile": duration_profile,
        "requested_duration_seconds": _DURATION_PROFILES.get(duration_profile, 0),
        "actual_duration_seconds": 0.0,
        "run_started_at": None,
        "run_finished_at": None,
        "window_kind": window_kind,
        "selected_token_count": 0,
        "total_window_closes": 0,
        "total_1h_windows_created": 0,
        "clean_memory_rows_created": 0,
        "e2z_already_exists_count": 0,
        "dirty_or_blocked_memory_count": 0,
        "retrieval_rows_created": 0,
        "paper_decisions_created": 0,
        "positions_created": 0,
        "trade_events_created": 0,
        "paper_trade_audits_created": 0,
        "pnl_created": 0,
        "stopped_safely_reason": "; ".join(reasons),
        "zero_clean_memories_is_valid": True,
        "source_budget_max_consecutive_failures": _DEFAULT_SOURCE_BUDGET_MAX_CONSECUTIVE_FAILURES,
        "throttle_backoff_seconds": _DEFAULT_THROTTLE_BACKOFF_SECONDS,
        "total_source_failures": 0,
        "hard_locks": dict(_HARD_LOCKS),
        "buy_enabled": False,
        "sell_enabled": False,
        "hold_enabled": False,
        "cadence_cycles_completed": 0,
        "pair_drift_detected": False,
        "total_pair_drift_events": 0,
        "freshness_gate_results": [],
        "freshness_advisory_results": [],
        "token_reports": [],
        "cycles": [],
        "forbidden_table_counts": {},
    }


# ---------------------------------------------------------------------------
# Main bounded runner
# ---------------------------------------------------------------------------

def run_1h_memory_factory_cycle(
    token_list_path: str | Path | None,
    db_path: str | Path | None,
    backup_proof_path: str | Path | None,
    *,
    mode: str,
    operator_approved: bool = False,
    duration_profile: str = _DEFAULT_PROFILE,
    window_kind: str = "WINDOW_1H",
    allow_long_bounded_run: bool = False,
    snapshot_interval_seconds: float = 0.0,
    window_close_interval_seconds: float = 0.0,
    source_budget_max_consecutive_failures: int = _DEFAULT_SOURCE_BUDGET_MAX_CONSECUTIVE_FAILURES,
    throttle_backoff_seconds: float = _DEFAULT_THROTTLE_BACKOFF_SECONDS,
    _adapter_map: dict[str, Any] | None = None,
    _cycle_budget: int | None = None,
) -> dict[str, Any]:
    """Run a bounded WINDOW_1H Memory Factory cycle for Lane X12.

    Parameters
    ----------
    token_list_path:
        Path to the Lane X12 token list JSON.
    db_path:
        Path to the operator-approved SQLite DB.
    backup_proof_path:
        Path to a DB backup proof file.
    mode:
        "TRACK_FAST" (1-5 tokens) or "TRACK_NORMAL" (1-7 tokens).
    operator_approved:
        Must be True; gate refuses without explicit approval.
    duration_profile:
        One of "1h", "4h", "6h", "12h", "24h".  Default: "4h".
    window_kind:
        Must be "WINDOW_1H".  WINDOW_15M and others are rejected.
    allow_long_bounded_run:
        Must be True for "12h" or "24h" profiles.
    snapshot_interval_seconds:
        Sleep between snapshots (0 = no sleep).
        Default = FAST: 240s, NORMAL: 720s (cadence-matched).
        Set to 0 for tests.
    window_close_interval_seconds:
        Window duration before close attempt.  Default = 2700s (45 min).
        Set to 0 for tests (immediate close).
    source_budget_max_consecutive_failures:
        Max consecutive source failures before safe stop.  Default = 5.
    throttle_backoff_seconds:
        Sleep after each failure.  Default = 0.0.
    _adapter_map:
        {token_mint: adapter} fixture map for tests.  None = production.
        When set, freshness gate is skipped.
    _cycle_budget:
        Test-only: max total window-close events across all tokens combined.
    """
    db_path_str = str(db_path) if db_path is not None else ""
    blocked_reasons: list[str] = []
    freshness_gate_results: list[dict[str, Any]] = []
    freshness_advisory_results: list[dict[str, Any]] = []

    # Mode validation
    if mode not in (LANE_X12_MODE_FAST, LANE_X12_MODE_NORMAL):
        blocked_reasons.append(
            f"mode must be {LANE_X12_MODE_FAST!r} or {LANE_X12_MODE_NORMAL!r};"
            f" got {mode!r}"
        )

    if not operator_approved:
        blocked_reasons.append(
            "operator_approved must be True to run the Lane X12 1h cycle"
        )

    if db_path is None:
        blocked_reasons.append("db_path is required")
    elif not Path(db_path).is_file():
        blocked_reasons.append(f"db_path not found: {db_path}")

    if backup_proof_path is None:
        blocked_reasons.append("backup_proof_path is required")
    elif not Path(backup_proof_path).is_file():
        blocked_reasons.append(f"backup_proof_path not found: {backup_proof_path}")

    if token_list_path is None:
        blocked_reasons.append("token_list_path is required")
    elif not Path(token_list_path).is_file():
        blocked_reasons.append(f"token_list_path not found: {token_list_path}")

    # Window-kind gates
    if window_kind in _FORBIDDEN_AS_MAIN_WINDOW:
        blocked_reasons.append(
            f"window_kind {window_kind!r} is support-only and must not be used as"
            " the main window; WINDOW_5M_MICRO_EVENT is support evidence only"
        )
    elif window_kind in _DISABLED_COLLECTION_WINDOW_KINDS:
        blocked_reasons.append(
            f"window_kind {window_kind!r} is not supported in Lane X12;"
            " WINDOW_15M is handled by X5/X10.10B; 4h/12h/24h require future lanes"
        )
    elif window_kind != _ENABLED_MAIN_WINDOW_KIND:
        blocked_reasons.append(
            f"window_kind {window_kind!r} is not recognized;"
            f" Lane X12 only supports {_ENABLED_MAIN_WINDOW_KIND!r}"
        )

    # Duration profile gates
    if duration_profile not in _DURATION_PROFILES:
        blocked_reasons.append(
            f"unsupported duration_profile {duration_profile!r};"
            f" allowed: {sorted(_DURATION_PROFILES)}"
        )
    elif duration_profile in _LONG_RUN_PROFILES and not allow_long_bounded_run:
        blocked_reasons.append(
            f"duration_profile {duration_profile!r} requires allow_long_bounded_run=True"
        )

    # Token list validation
    tokens: list[dict[str, Any]] = []
    token_list_valid = False
    token_list_reason = "not checked"

    if (
        token_list_path is not None
        and Path(token_list_path).is_file()
        and mode in (LANE_X12_MODE_FAST, LANE_X12_MODE_NORMAL)
    ):
        token_list_valid, token_list_reason, tokens = _load_and_validate_token_list(
            token_list_path, mode
        )
        if not token_list_valid:
            blocked_reasons.append(f"token list invalid: {token_list_reason}")
        elif tokens and db_path is not None and Path(db_path_str).is_file() and _adapter_map is None:
            # Freshness gate — only when token list is valid and no test adapter
            try:
                from printer_v1.operator_cli.lane_x10_9_freshness_gate import (
                    FRESHNESS_STATUS_STALE_BLOCKED,
                    FRESHNESS_STATUS_UNKNOWN_BLOCKED,
                    check_token_list_freshness,
                )
                fresh_tokens = [
                    {
                        "mint": str(t.get(_TL_TOKEN_MINT, "")),
                        "pair_address": str(t.get(_TL_PAIR_ADDRESS, "")),
                        "slot": _ALL_SLOTS[i],
                    }
                    for i, t in enumerate(tokens)
                ]
                fr = check_token_list_freshness(fresh_tokens, db_path_str)
                if mode == LANE_X12_MODE_FAST:
                    # TRACK_FAST: hard gate — stale blocks
                    for fr_item in fr:
                        freshness_gate_results.append(fr_item.to_dict())
                        if fr_item.status in (
                            FRESHNESS_STATUS_STALE_BLOCKED,
                            FRESHNESS_STATUS_UNKNOWN_BLOCKED,
                        ):
                            blocked_reasons.append(
                                f"X10.9 freshness gate: slot {fr_item.slot}"
                                f" mint {fr_item.mint}"
                                f" ({fr_item.status}): {fr_item.reason}"
                            )
                else:
                    # TRACK_NORMAL: advisory only — stale never blocks
                    for fr_item in fr:
                        freshness_advisory_results.append(fr_item.to_dict())
            except ImportError:
                pass

    if blocked_reasons:
        result = _blocked_result(
            blocked_reasons, db_path_str, mode, duration_profile, window_kind
        )
        result["freshness_gate_results"] = freshness_gate_results
        result["freshness_advisory_results"] = freshness_advisory_results
        return result

    # Lane K dependency check
    try:
        from printer_v1.operator_cli.lane_k_e2z_pipeline_wiring import (  # noqa: F401
            run_e2z_pipeline,
        )
    except ImportError as exc:
        return _blocked_result(
            [f"Lane K / E2Z path unavailable: {exc}"],
            db_path_str, mode, duration_profile, window_kind,
        )

    from printer_v1.operator_cli.lane_k_e2z_pipeline_wiring import (
        LANE_K_STATUS_COMPLETED,
        run_e2z_pipeline,
    )

    # Resolve effective intervals
    if mode == LANE_X12_MODE_FAST:
        effective_snapshot_interval = (
            snapshot_interval_seconds
            if snapshot_interval_seconds > 0.0
            else _DEFAULT_FAST_SNAPSHOT_INTERVAL_SECONDS
        )
    else:
        effective_snapshot_interval = (
            snapshot_interval_seconds
            if snapshot_interval_seconds > 0.0
            else _DEFAULT_NORMAL_SNAPSHOT_INTERVAL_SECONDS
        )

    effective_window_close_interval = (
        window_close_interval_seconds
        if window_close_interval_seconds > 0.0
        else _DEFAULT_WINDOW_CLOSE_INTERVAL_SECONDS
    )

    slots_to_use = _ALL_SLOTS[: len(tokens)]

    # ---------- INIT ----------
    max_duration_seconds = _DURATION_PROFILES[duration_profile]
    run_started_at = _utc_now()
    loop_start = time.monotonic()

    def _new_token_state(slot: str, tok: dict[str, Any]) -> dict[str, Any]:
        # V2-6.3: an optional continuation linkage to the token's preceding closed
        # 15m window. When present, the runner plans the continuation via
        # build_1h_continuation_plan (deadline anchored to 15m close + 2700s) and
        # the E2O close consumes the transition verdict.
        continuation = tok.get(_TL_CONTINUATION_OF_15M)
        plan = plan_1h_continuation(tok) if continuation else None
        return {
            "slot": slot,
            "mint": str(tok.get(_TL_TOKEN_MINT, "")),
            "pair_address_supplied": str(tok.get(_TL_PAIR_ADDRESS, "")),
            "continuation_of_15m": continuation,
            "continuation_plan": plan,
            "continuity_terminal_blocked": False,
            "window_open_mono": None,
            "window_start_snapshot_id": None,
            "snapshots_created": 0,
            "memory_windows_created": 0,
            "source_requests_created": 0,
            "source_responses_created": 0,
            "source_failures_created": 0,
            "lane_q_valid_windows": 0,
            "lane_q_blocked_windows": 0,
            "window_closes": 0,
            "clean_memory_created": 0,
            "dirty_memory_count": 0,
            "e2z_already_exists_count": 0,
            "lane_k_runs": 0,
            "pair_address_drift_count": 0,
            "pair_drift_events": [],
            "cycles": [],
        }

    token_states = [
        _new_token_state(slots_to_use[i], tokens[i]) for i in range(len(tokens))
    ]

    total_window_closes: int = 0
    total_1h_windows_created: int = 0
    clean_memory_rows_created: int = 0
    e2z_already_exists_count: int = 0
    dirty_or_blocked_memory_count: int = 0
    cadence_cycle_count: int = 0
    final_status = LANE_X12_STATUS_COMPLETED
    stopped_safely_reason: str | None = None

    consecutive_source_failures: int = 0
    total_source_failures: int = 0

    # ---------- CADENCE LOOP ----------
    while True:
        elapsed_now = _elapsed(loop_start)
        if elapsed_now >= max_duration_seconds:
            stopped_safely_reason = (
                f"duration limit reached: {elapsed_now:.1f}s"
                f" >= {max_duration_seconds}s ({duration_profile})"
            )
            break

        if _cycle_budget is not None and total_window_closes >= _cycle_budget:
            stopped_safely_reason = (
                f"cycle budget exhausted: {_cycle_budget} window close(s) completed"
            )
            break

        cadence_cycle_count += 1
        cycle_stopped = False

        for tok in token_states:
            if cycle_stopped:
                break
            if tok["continuity_terminal_blocked"]:
                continue

            slot = tok["slot"]
            mint = tok["mint"]
            adapter = _adapter_map.get(mint) if _adapter_map is not None else None

            # Phase 1: Snapshot for this token
            snap_result = _run_x12_token_step(
                db_path,
                mint,
                slot,
                mode,
                adapter=adapter,
                close_window=False,
                snapshot_start_id=None,
            )

            tok["cycles"].append(
                {"phase": 1, "slot": slot, "cycle": cadence_cycle_count, **snap_result}
            )

            if snap_result.get("executed"):
                consecutive_source_failures = 0
                snap_id = snap_result.get("snapshot_id") or snap_result.get(
                    "snapshot_id_for_window"
                )
                if snap_id is not None:
                    tok["snapshots_created"] += 1
                    if tok["window_start_snapshot_id"] is None:
                        tok["window_start_snapshot_id"] = int(snap_id)
                        tok["window_open_mono"] = time.monotonic()
                    deltas = snap_result.get("deltas", {})
                    tok["source_requests_created"] += int(
                        deltas.get("printer_source_requests", 0) or 0
                    )
                    tok["source_responses_created"] += int(
                        deltas.get("printer_source_responses", 0) or 0
                    )
            else:
                consecutive_source_failures += 1
                total_source_failures += 1
                tok["source_failures_created"] += 1
                if consecutive_source_failures > source_budget_max_consecutive_failures:
                    stopped_safely_reason = (
                        f"source budget exceeded: {consecutive_source_failures}"
                        f" consecutive failures > max {source_budget_max_consecutive_failures}"
                    )
                    final_status = LANE_X12_STATUS_STOPPED
                    cycle_stopped = True
                    break
                if throttle_backoff_seconds > 0:
                    time.sleep(throttle_backoff_seconds)

            # Phase 2: Window close if elapsed
            window_elapsed = (
                time.monotonic() - tok["window_open_mono"]
                if tok["window_open_mono"] is not None
                else 0.0
            )
            should_close = (
                tok["window_open_mono"] is not None
                and window_elapsed >= effective_window_close_interval
            )
            if not should_close:
                continue

            close_result = _run_x12_token_step(
                db_path,
                mint,
                slot,
                mode,
                adapter=adapter,
                close_window=True,
                snapshot_start_id=tok["window_start_snapshot_id"],
                pair_id_expected=None,
                continuation_of_15m=tok.get("continuation_of_15m"),
            )

            tok["cycles"].append(
                {"phase": 2, "slot": slot, "cycle": cadence_cycle_count, **close_result}
            )

            if close_result.get("pair_drift_detected"):
                tok["pair_address_drift_count"] += 1
                tok["pair_drift_events"].append(
                    {
                        "cycle": cadence_cycle_count,
                        "mint": mint,
                        "pair_address_supplied": tok["pair_address_supplied"],
                    }
                )
                dirty_or_blocked_memory_count += 1
            elif close_result.get("executed"):
                consecutive_source_failures = 0
                total_window_closes += 1
                tok["window_closes"] += 1
                tok["window_start_snapshot_id"] = None
                tok["window_open_mono"] = None

                mem_id = close_result.get("memory_window_id")
                if mem_id is not None:
                    tok["memory_windows_created"] += 1
                    total_1h_windows_created += 1
                    ql = close_result.get("memory_quality_label")
                    if ql:
                        memory_quality_label_s = str(ql).upper()
                        if "DIRTY" in memory_quality_label_s or "BLOCKED" in memory_quality_label_s:
                            tok["dirty_memory_count"] += 1
                            dirty_or_blocked_memory_count += 1

                # Lane K / E2Z pipeline after window close
                try:
                    k_result = run_e2z_pipeline(db_path_str)
                    tok["lane_k_runs"] += 1
                    if k_result.get("lane_k_status") == LANE_K_STATUS_COMPLETED:
                        e2z_count = int(k_result.get("e2z_episodes_created", 0) or 0)
                        already = int(k_result.get("e2z_already_exists_count", 0) or 0)
                        clean_memory_rows_created += e2z_count
                        e2z_already_exists_count += already
                        tok["clean_memory_created"] += e2z_count
                        tok["e2z_already_exists_count"] += already
                except Exception:
                    pass
            else:
                if close_result.get("cycle_status") == "E2O_1H_CONTINUITY_BLOCKED":
                    tok["continuity_terminal_blocked"] = True
                    tok["continuation_of_15m"] = None
                    tok["continuation_plan"] = None
                consecutive_source_failures += 1
                total_source_failures += 1
                tok["source_failures_created"] += 1
                tok["window_start_snapshot_id"] = None
                tok["window_open_mono"] = None
                dirty_or_blocked_memory_count += 1
                if consecutive_source_failures > source_budget_max_consecutive_failures:
                    stopped_safely_reason = (
                        f"source budget exceeded: {consecutive_source_failures}"
                        f" consecutive failures > max {source_budget_max_consecutive_failures}"
                    )
                    final_status = LANE_X12_STATUS_STOPPED
                    cycle_stopped = True
                    break
                if throttle_backoff_seconds > 0:
                    time.sleep(throttle_backoff_seconds)

        if token_states and all(tok["continuity_terminal_blocked"] for tok in token_states):
            stopped_safely_reason = "all continuation tokens terminally blocked"
            final_status = LANE_X12_STATUS_STOPPED
            break

        if cycle_stopped or final_status == LANE_X12_STATUS_STOPPED:
            break

        # Sleep between cadence cycles
        if snapshot_interval_seconds > 0:
            time.sleep(snapshot_interval_seconds)

    run_finished_at = _utc_now()
    actual_duration = _elapsed(loop_start)

    forbidden_counts = _check_forbidden_tables(db_path_str)
    total_pair_drift = sum(
        tok["pair_address_drift_count"] for tok in token_states
    )

    return {
        "command": (
            LANE_X12_FAST_COMMAND_NAME
            if mode == LANE_X12_MODE_FAST
            else LANE_X12_NORMAL_COMMAND_NAME
        ),
        "lane_x12_status": final_status,
        "mode": mode,
        "operator_approved": True,
        "db_path": db_path_str,
        "selected_profile": duration_profile,
        "requested_duration_seconds": max_duration_seconds,
        "actual_duration_seconds": round(actual_duration, 3),
        "run_started_at": run_started_at,
        "run_finished_at": run_finished_at,
        "window_kind": window_kind,
        "selected_token_count": len(tokens),
        "total_window_closes": total_window_closes,
        "total_1h_windows_created": total_1h_windows_created,
        "clean_memory_rows_created": clean_memory_rows_created,
        "e2z_already_exists_count": e2z_already_exists_count,
        "dirty_or_blocked_memory_count": dirty_or_blocked_memory_count,
        "retrieval_rows_created": 0,
        "paper_decisions_created": 0,
        "positions_created": 0,
        "trade_events_created": 0,
        "paper_trade_audits_created": 0,
        "pnl_created": 0,
        "stopped_safely_reason": stopped_safely_reason,
        "zero_clean_memories_is_valid": True,
        "source_budget_max_consecutive_failures": source_budget_max_consecutive_failures,
        "throttle_backoff_seconds": throttle_backoff_seconds,
        "total_source_failures": total_source_failures,
        "hard_locks": dict(_HARD_LOCKS),
        "buy_enabled": False,
        "sell_enabled": False,
        "hold_enabled": False,
        "cadence_cycles_completed": cadence_cycle_count,
        "pair_drift_detected": total_pair_drift > 0,
        "total_pair_drift_events": total_pair_drift,
        "freshness_gate_results": freshness_gate_results,
        "freshness_advisory_results": freshness_advisory_results,
        "token_reports": [
            {
                "slot": tok["slot"],
                "mint": tok["mint"],
                "pair_address_supplied": tok["pair_address_supplied"],
                "snapshots_created": tok["snapshots_created"],
                "memory_windows_created": tok["memory_windows_created"],
                "window_closes": tok["window_closes"],
                "clean_memory_created": tok["clean_memory_created"],
                "dirty_memory_count": tok["dirty_memory_count"],
                "e2z_already_exists_count": tok["e2z_already_exists_count"],
                "lane_k_runs": tok["lane_k_runs"],
                "pair_address_drift_count": tok["pair_address_drift_count"],
                "pair_drift_events": tok["pair_drift_events"],
                "source_requests_created": tok["source_requests_created"],
                "source_responses_created": tok["source_responses_created"],
                "source_failures_created": tok["source_failures_created"],
                "continuity_terminal_blocked": tok["continuity_terminal_blocked"],
            }
            for tok in token_states
        ],
        "cycles": [
            cycle_entry
            for tok in token_states
            for cycle_entry in tok["cycles"]
        ],
        "forbidden_table_counts": forbidden_counts,
    }
