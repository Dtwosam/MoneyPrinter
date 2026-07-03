"""Lane X2 — Two-Token Controlled 15m Memory Factory Proof.

Exactly two operator-approved TRACK_FAST Solana tokens. WINDOW_15M only.
Deterministic A/B snapshot rotation. Separate evidence identity per token.
No token/pair mixing. Idempotent replay preserved. All financial locks remain.

This module provides a Lane X2-specific validator and runner path.
The existing single-token E2I / E2J / Lane U path is NOT modified.

Token list shape (Lane X2 format — distinct from E2I format):

  {
    "tokens": [
      {
        "token_mint": "<MINT_A>",
        "pair_address": "<PAIR_A>",
        "chain": "solana",
        "tracking_lane": "TRACK_FAST",
        "operator_approved": true
      },
      {
        "token_mint": "<MINT_B>",
        "pair_address": "<PAIR_B>",
        "chain": "solana",
        "tracking_lane": "TRACK_FAST",
        "operator_approved": true
      }
    ]
  }

A/B rotation: even ticks → slot A, odd ticks → slot B.
Each tick: snapshot only; if the slot's window is elapsed, close it and run Lane K.

Hard rules:
- Operator approval required.
- Exactly 2 TRACK_FAST tokens (not 1, not 3, not more).
- WINDOW_15M only. No 5m main. No 1h/4h/12h/24h.
- No BUY/SELL/HOLD. No paper decisions. No positions. No PnL.
- No retrieval activation. No scoring/ranking/confidence/weighted logic.
- No wallet/private keys. No live trading. No paid APIs.
- No Source Governor bypass. No Central Scheduler bypass.
- No token/pair mixing. Separate evidence identity per token.
- Zero clean memories is always a valid outcome.
"""

from __future__ import annotations

import json
import sqlite3
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


LANE_X2_COMMAND_NAME: str = "printer-run-lane-x2-two-token-cycle"
LANE_X2_STATUS_COMPLETED: str = "LANE_X2_COMPLETED"
LANE_X2_STATUS_BLOCKED: str = "LANE_X2_BLOCKED"
LANE_X2_STATUS_STOPPED: str = "LANE_X2_STOPPED"

# Exactly two tokens — not one, not three.
LANE_X2_EXACT_TOKEN_COUNT: int = 2

# Token list field names for the Lane X2 format (distinct from E2I format).
_TL_TRACKING_LANE: str = "tracking_lane"
_TL_OPERATOR_APPROVED: str = "operator_approved"
_TL_CHAIN: str = "chain"
_TL_TOKEN_MINT: str = "token_mint"
_TL_PAIR_ADDRESS: str = "pair_address"

_REQUIRED_TRACKING_LANE: str = "TRACK_FAST"
_REQUIRED_CHAIN: str = "solana"
_PLACEHOLDER_PREFIX: str = "PLACEHOLDER"

# Duration profiles — same as Lane U.
_DURATION_PROFILES: dict[str, int] = {
    "1h": 3600,
    "4h": 14400,
    "6h": 21600,
    "12h": 43200,
    "24h": 86400,
}
_LONG_RUN_PROFILES: frozenset[str] = frozenset({"12h", "24h"})
_DEFAULT_PROFILE: str = "6h"

# Window-kind policy — same as Lane U.
_ENABLED_MAIN_WINDOW_KIND: str = "WINDOW_15M"
_DISABLED_COLLECTION_WINDOW_KINDS: frozenset[str] = frozenset(
    {"WINDOW_1H", "WINDOW_4H", "WINDOW_12H", "WINDOW_24H"}
)
_SUPPORT_ONLY_WINDOW_KINDS: frozenset[str] = frozenset({"WINDOW_5M_MICRO_EVENT"})
_FORBIDDEN_AS_MAIN_WINDOW: frozenset[str] = frozenset({"WINDOW_5M_MICRO_EVENT"})

# Slot labels for the two tokens.
_SLOT_A: str = "A"
_SLOT_B: str = "B"

# Step status strings — match E2J constants so downstream consumers can compare.
_X2_STEP_EXECUTED: str = "E2J_FIRST_15M_CYCLE_EXECUTED"
_X2_STEP_BLOCKED: str = "E2J_FIRST_15M_CYCLE_BLOCKED"

_X2_JOB_KIND: str = "TRACK_FAST_FIRST_15M"
_X2_JOB_NAME_PREFIX: str = "x2_track_fast_15m_slot"
_X2_LOCK_OWNER_PREFIX: str = "lane_x2_two_token_slot"

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
    "no_1h_4h_12h_24h_collection": True,
    "no_5m_main_window": True,
    "no_trade_events": True,
    "no_paper_trade_audits": True,
    "no_token_pair_mixing": True,
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


def _get_audit_counts(db_path: str | Path) -> dict[str, int]:
    return {t: _count_table_rows(db_path, t) for t in _AUDIT_TABLES}


def _check_forbidden_tables(db_path: str | Path) -> dict[str, int]:
    return {t: _count_table(db_path, t) for t in _FORBIDDEN_WRITE_TABLES}


# ---------------------------------------------------------------------------
# Lane X2-specific two-token validator
# ---------------------------------------------------------------------------

def _load_and_validate_two_token_list(
    path: str | Path | None,
) -> tuple[bool, str, dict[str, Any], dict[str, Any]]:
    """Validate exactly 2 TRACK_FAST approved Solana tokens for Lane X2.

    Returns (valid, reason, token_a_entry, token_b_entry).

    Uses the Lane X2 token-list format (tracking_lane / operator_approved).
    Does NOT call or modify the existing E2I single-token validator.
    """
    if path is None:
        return False, "token_list_path is required", {}, {}
    try:
        data = json.loads(Path(path).read_text(encoding="utf-8"))
    except FileNotFoundError:
        return False, f"token list file not found: {path}", {}, {}
    except (json.JSONDecodeError, OSError) as exc:
        return False, f"token list file unreadable: {exc}", {}, {}

    tokens: list[dict[str, Any]] = list(data.get("tokens", []))
    if len(tokens) != LANE_X2_EXACT_TOKEN_COUNT:
        return (
            False,
            f"Lane X2 requires exactly {LANE_X2_EXACT_TOKEN_COUNT} TRACK_FAST tokens;"
            f" found {len(tokens)} total token entries",
            {},
            {},
        )

    errors: list[str] = []
    for i, tok in enumerate(tokens):
        lane = str(tok.get(_TL_TRACKING_LANE, ""))
        approved = bool(tok.get(_TL_OPERATOR_APPROVED, False))
        chain = str(tok.get(_TL_CHAIN, ""))
        mint = str(tok.get(_TL_TOKEN_MINT, ""))
        pair = str(tok.get(_TL_PAIR_ADDRESS, ""))

        if lane != _REQUIRED_TRACKING_LANE:
            errors.append(
                f"token[{i}]: tracking_lane must be {_REQUIRED_TRACKING_LANE!r};"
                f" got {lane!r}"
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
                f"token[{i}]: invalid or placeholder pair_address: {pair!r}"
            )

    if errors:
        return False, "; ".join(errors), {}, {}

    mints = [str(t.get(_TL_TOKEN_MINT, "")) for t in tokens]
    if len(set(mints)) != LANE_X2_EXACT_TOKEN_COUNT:
        return (
            False,
            f"duplicate token_mint detected: {mints}; both tokens must have distinct mints",
            {},
            {},
        )

    pairs = [str(t.get(_TL_PAIR_ADDRESS, "")) for t in tokens]
    if len(set(pairs)) != LANE_X2_EXACT_TOKEN_COUNT:
        return (
            False,
            f"duplicate pair_address detected: {pairs};"
            " both tokens must have distinct pair addresses",
            {},
            {},
        )

    mint_a = mints[0]
    mint_b = mints[1]
    return (
        True,
        f"2 TRACK_FAST approved solana tokens validated:"
        f" mint_a={mint_a!r} mint_b={mint_b!r}",
        tokens[0],
        tokens[1],
    )


# ---------------------------------------------------------------------------
# Per-token scheduler job helpers (X2-specific, mirrors E2J pattern)
# ---------------------------------------------------------------------------

def _create_x2_job(connection: sqlite3.Connection, slot: str) -> int:
    """Create a TRACK_FAST_FIRST_15M scheduler job for slot A or B.

    Checks no RUNNING jobs exist before creating, matching E2J's gate.
    """
    running = int(
        connection.execute(
            "SELECT COUNT(*) FROM printer_scheduler_jobs WHERE status = 'RUNNING'"
        ).fetchone()[0]
    )
    if running:
        raise ValueError(
            f"Lane X2 slot {slot}: {running} RUNNING job(s) already exist;"
            " cannot create new job while another is active"
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
        (f"{_X2_JOB_NAME_PREFIX}_{slot.lower()}", _X2_JOB_KIND, now, now, now),
    )
    return int(cursor.lastrowid)


def _claim_x2_job(connection: sqlite3.Connection, job_id: int, slot: str) -> bool:
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
        (f"{_X2_LOCK_OWNER_PREFIX}_{slot.lower()}", now, now, now, job_id),
    )
    return int(cursor.rowcount) == 1


def _complete_x2_job(connection: sqlite3.Connection, job_id: int) -> None:
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


def _fail_x2_job(connection: sqlite3.Connection, job_id: int, error: str) -> None:
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


def _load_x2_job_row(
    connection: sqlite3.Connection, job_id: int
) -> sqlite3.Row | None:
    return connection.execute(
        "SELECT * FROM printer_scheduler_jobs WHERE id = ?", (job_id,)
    ).fetchone()


# ---------------------------------------------------------------------------
# Per-token step execution (X2-specific — no E2J token-list loading, no E2G gate)
# ---------------------------------------------------------------------------

def _run_x2_token_step(
    db_path: str | Path,
    mint: str,
    slot: str,
    *,
    adapter: Any = None,
    close_window: bool = False,
    snapshot_start_id: int | None = None,
) -> dict[str, Any]:
    """Run one snapshot or window-close step for one token.

    Mirrors E2J's cycle execution but:
    - Takes mint directly (no token-list file loading).
    - No E2G gate check (X2 validates upfront via _load_and_validate_two_token_list).
    - Calls E2H, E2M, E2O, E2Q through the same governed path as E2J.

    adapter: fixture adapter for tests; None = build real DexScreener adapter.
    close_window: True for window-close calls; False for snapshot-only.
    snapshot_start_id: first snapshot ID in the current window (passed to E2O).
    """
    from printer_v1.operator_cli.e2h_runtime_handler import (
        E2H_STATUS_EXECUTED,
        execute_track_fast_first_15m_job,
    )

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

    try:
        job_id = _create_x2_job(connection, slot)
        connection.commit()

        claimed = _claim_x2_job(connection, job_id, slot)
        if not claimed:
            raise ValueError(
                f"Lane X2 slot {slot}: failed to claim job {job_id}"
            )
        connection.commit()

        job_row = _load_x2_job_row(connection, job_id)
        if job_row is None:
            raise ValueError(
                f"Lane X2 slot {slot}: job {job_id} not found after claim"
            )

        if adapter is not None:
            real_adapter = adapter
        else:
            from printer_v1.operator_cli.e2i_source_transport import (
                build_e2i_dexscreener_adapter,
            )
            real_adapter = build_e2i_dexscreener_adapter(token_mint=mint)

        handler_result = execute_track_fast_first_15m_job(
            connection, job_row, adapter=real_adapter
        )

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
                    _fail_x2_job(connection, job_id, reason)
                    cycle_status = "E2M_BLOCKED"
                    exec_error = reason

                elif not close_window:
                    snapshot_id_for_window = (
                        snapshot_result.get("snapshot_id")
                        or snapshot_result.get("existing_snapshot_id")
                    )
                    _complete_x2_job(connection, job_id)
                    cycle_status = "SUCCEEDED_SNAPSHOT_ONLY"

                else:
                    snapshot_id_for_window = (
                        snapshot_result.get("snapshot_id")
                        or snapshot_result.get("existing_snapshot_id")
                    )
                    if snapshot_id_for_window is not None:
                        from printer_v1.operator_cli.e2o_memory_window_close import (
                            E2O_STATUS_BLOCKED as _E2O_BLOCKED,
                            close_15m_memory_window_from_snapshot,
                        )
                        window_result = close_15m_memory_window_from_snapshot(
                            connection,
                            int(snapshot_id_for_window),
                            mint,
                            snapshot_start_id=snapshot_start_id,
                        )
                        memory_window_close_status = str(
                            window_result.get("e2o_status", "UNKNOWN")
                        )
                        window_start_at = window_result.get("window_start_at")
                        window_end_at = window_result.get("window_end_at")
                        elapsed_seconds_val = window_result.get("elapsed_seconds")
                        lane_q_integrity_eligible = bool(
                            window_result.get("lane_q_integrity_eligible", False)
                        )

                        if window_result.get("e2o_status") == _E2O_BLOCKED:
                            reason = "E2O_BLOCKED: " + "; ".join(
                                window_result.get(
                                    "blocked_reasons", ["memory window close blocked"]
                                )
                            )
                            _fail_x2_job(connection, job_id, reason)
                            cycle_status = "E2O_BLOCKED"
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
                                    _fail_x2_job(connection, job_id, reason)
                                    cycle_status = "E2Q_BLOCKED"
                                    exec_error = reason
                                else:
                                    _complete_x2_job(connection, job_id)
                                    cycle_status = "SUCCEEDED"
                            else:
                                _complete_x2_job(connection, job_id)
                                cycle_status = "SUCCEEDED"
                    else:
                        _complete_x2_job(connection, job_id)
                        cycle_status = "SUCCEEDED"
            else:
                _complete_x2_job(connection, job_id)
                cycle_status = "SUCCEEDED"

        else:
            reason = handler_result.get("blocked_reason") or "; ".join(
                handler_result.get("blocked_gates", ["handler blocked"])
            )
            _fail_x2_job(connection, job_id, reason)
            cycle_status = "HANDLER_BLOCKED"
            exec_error = reason

        connection.commit()

    except Exception as exc:
        exec_error = str(exc)
        cycle_status = "EXCEPTION"
        if job_id is not None:
            try:
                _fail_x2_job(connection, job_id, str(exc))
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
        "e2j_status": _X2_STEP_EXECUTED if executed else _X2_STEP_BLOCKED,
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
        "exec_error": exec_error,
        "deltas": deltas,
    }


# ---------------------------------------------------------------------------
# Blocked result helper
# ---------------------------------------------------------------------------

def _blocked_result(
    reasons: list[str],
    db_path_str: str,
    duration_profile: str,
    window_kind: str,
) -> dict[str, Any]:
    return {
        "command": LANE_X2_COMMAND_NAME,
        "lane_x2_status": LANE_X2_STATUS_BLOCKED,
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
        "token_a_mint": None,
        "token_b_mint": None,
        "total_window_closes": 0,
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
        "hard_locks": dict(_HARD_LOCKS),
        "buy_enabled": False,
        "sell_enabled": False,
        "hold_enabled": False,
        "token_a_report": None,
        "token_b_report": None,
        "cycles": [],
        "forbidden_table_counts": {},
    }


# ---------------------------------------------------------------------------
# Main bounded two-token runner
# ---------------------------------------------------------------------------

def run_two_token_memory_factory_cycle(
    token_list_path: str | Path | None,
    db_path: str | Path | None,
    backup_proof_path: str | Path | None,
    *,
    operator_approved: bool = False,
    duration_profile: str = _DEFAULT_PROFILE,
    window_kind: str = "WINDOW_15M",
    allow_long_bounded_run: bool = False,
    snapshot_interval_seconds: float = 0.0,
    window_close_interval_seconds: float = 0.0,
    _adapter_map: dict[str, Any] | None = None,
    _cycle_budget: int | None = None,
) -> dict[str, Any]:
    """Run a bounded two-token A/B rotation Memory Factory cycle for Lane X2.

    Parameters
    ----------
    token_list_path:
        Path to the Lane X2 token list JSON (exactly 2 TRACK_FAST tokens).
    db_path:
        Path to the operator-approved SQLite DB.
    backup_proof_path:
        Path to a DB backup proof file.
    operator_approved:
        Must be True; gate refuses without explicit approval.
    duration_profile:
        One of "1h", "4h", "6h", "12h", "24h".
    window_kind:
        Must be "WINDOW_15M".
    allow_long_bounded_run:
        Must be True for "12h" or "24h" profiles.
    snapshot_interval_seconds:
        Sleep between snapshots (0 = no sleep, test mode).
    window_close_interval_seconds:
        Window duration before close attempt (0 = close immediately after first snapshot).
    _adapter_map:
        {token_mint: adapter} fixture map for tests.  None = production DexScreener.
    _cycle_budget:
        Test-only: max total window-close events across both tokens combined.
        None = duration controls.
    """
    db_path_str = str(db_path) if db_path is not None else ""
    blocked_reasons: list[str] = []

    if not operator_approved:
        blocked_reasons.append(
            "operator_approved must be True to run the Lane X2 two-token cycle"
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

    # Window-kind gates — same policy as Lane U.
    if window_kind in _FORBIDDEN_AS_MAIN_WINDOW:
        blocked_reasons.append(
            f"window_kind {window_kind!r} is support-only and must not be used as"
            " the main window; WINDOW_5M_MICRO_EVENT is support evidence only"
        )
    elif window_kind in _DISABLED_COLLECTION_WINDOW_KINDS:
        blocked_reasons.append(
            f"window_kind {window_kind!r} real collection is disabled in Lane X2;"
            " WINDOW_1H/4H/12H/24H require a separate future approved lane"
        )
    elif window_kind != _ENABLED_MAIN_WINDOW_KIND:
        blocked_reasons.append(
            f"window_kind {window_kind!r} is not recognized;"
            f" Lane X2 only supports {_ENABLED_MAIN_WINDOW_KIND!r}"
        )

    # Duration profile gates.
    if duration_profile not in _DURATION_PROFILES:
        blocked_reasons.append(
            f"unsupported duration_profile {duration_profile!r};"
            f" allowed: {sorted(_DURATION_PROFILES)}"
        )
    elif duration_profile in _LONG_RUN_PROFILES and not allow_long_bounded_run:
        blocked_reasons.append(
            f"duration_profile {duration_profile!r} requires allow_long_bounded_run=True"
        )

    # Token list validation — requires exactly 2 TRACK_FAST tokens.
    token_a_entry: dict[str, Any] = {}
    token_b_entry: dict[str, Any] = {}
    mint_a: str = ""
    mint_b: str = ""
    token_list_valid = False
    token_list_reason = "not checked"

    if token_list_path is not None and Path(token_list_path).is_file():
        token_list_valid, token_list_reason, token_a_entry, token_b_entry = (
            _load_and_validate_two_token_list(token_list_path)
        )
        if not token_list_valid:
            blocked_reasons.append(f"token list invalid: {token_list_reason}")
        else:
            mint_a = str(token_a_entry.get(_TL_TOKEN_MINT, ""))
            mint_b = str(token_b_entry.get(_TL_TOKEN_MINT, ""))

    if blocked_reasons:
        result = _blocked_result(
            blocked_reasons, db_path_str, duration_profile, window_kind
        )
        result["token_a_mint"] = mint_a or None
        result["token_b_mint"] = mint_b or None
        return result

    # Dependency check — Lane K must be importable.
    try:
        from printer_v1.operator_cli.lane_k_e2z_pipeline_wiring import (  # noqa: F401
            run_e2z_pipeline,
        )
    except ImportError as exc:
        return _blocked_result(
            [f"Lane K / E2Z path unavailable: {exc}"],
            db_path_str, duration_profile, window_kind,
        )

    from printer_v1.operator_cli.lane_k_e2z_pipeline_wiring import (
        LANE_K_STATUS_COMPLETED,
        run_e2z_pipeline,
    )

    # ---------- INIT ----------
    max_duration_seconds = _DURATION_PROFILES[duration_profile]
    run_started_at = _utc_now()
    loop_start = time.monotonic()

    # Per-token state dicts.
    def _new_token_state(slot: str, mint: str) -> dict[str, Any]:
        return {
            "slot": slot,
            "mint": mint,
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
            "cycles": [],
        }

    token_states = [
        _new_token_state(_SLOT_A, mint_a),
        _new_token_state(_SLOT_B, mint_b),
    ]

    # Global counters.
    total_window_closes: int = 0
    clean_memory_rows_created: int = 0
    e2z_already_exists_count: int = 0
    dirty_or_blocked_memory_count: int = 0
    tick_count: int = 0
    final_status = LANE_X2_STATUS_COMPLETED
    stopped_safely_reason: str | None = None

    # ---------- A/B ROTATION LOOP ----------
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

        # A/B rotation: even ticks → slot A (index 0), odd ticks → slot B (index 1).
        active_idx = tick_count % 2
        tok = token_states[active_idx]
        slot = tok["slot"]
        mint = tok["mint"]
        adapter = (
            _adapter_map.get(mint) if _adapter_map is not None else None
        )

        # Phase 1: Snapshot-only for the active token.
        snap_result = _run_x2_token_step(
            db_path,
            mint,
            slot,
            adapter=adapter,
            close_window=False,
            snapshot_start_id=None,
        )

        # Window opens on first snapshot attempt for this token.
        if tok["window_open_mono"] is None:
            tok["window_open_mono"] = time.monotonic()

        snap_id = snap_result.get("snapshot_id")
        if snap_id is not None and tok["window_start_snapshot_id"] is None:
            tok["window_start_snapshot_id"] = int(snap_id)

        if snap_result.get("snapshot_persistence_status") == "E2M_SNAPSHOT_PERSISTED":
            tok["snapshots_created"] += 1

        snap_deltas = snap_result.get("deltas", {})
        tok["source_requests_created"] += max(
            0, int(snap_deltas.get("printer_source_requests", 0) or 0)
        )
        tok["source_responses_created"] += max(
            0, int(snap_deltas.get("printer_source_responses", 0) or 0)
        )
        tok["source_failures_created"] += max(
            0, int(snap_deltas.get("printer_source_failures", 0) or 0)
        )

        if snap_result.get("e2j_status") != _X2_STEP_EXECUTED:
            stopped_safely_reason = (
                f"slot {slot} snapshot stopped:"
                f" {snap_result.get('cycle_status', 'UNKNOWN')}"
                + (
                    f" — {snap_result.get('exec_error', '')}"
                    if snap_result.get("exec_error")
                    else ""
                )
            )
            final_status = LANE_X2_STATUS_STOPPED
            break

        # Phase 2: Check if this token's window should close.
        window_elapsed = _elapsed(tok["window_open_mono"])  # type: ignore[arg-type]
        if window_elapsed >= window_close_interval_seconds:
            close_result = _run_x2_token_step(
                db_path,
                mint,
                slot,
                adapter=adapter,
                close_window=True,
                snapshot_start_id=tok["window_start_snapshot_id"],
            )

            close_deltas = close_result.get("deltas", {})
            tok["source_requests_created"] += max(
                0, int(close_deltas.get("printer_source_requests", 0) or 0)
            )
            tok["source_responses_created"] += max(
                0, int(close_deltas.get("printer_source_responses", 0) or 0)
            )
            tok["source_failures_created"] += max(
                0, int(close_deltas.get("printer_source_failures", 0) or 0)
            )
            tok["memory_windows_created"] += max(
                0, int(close_deltas.get("printer_memory_windows", 0) or 0)
            )

            if close_result.get("snapshot_persistence_status") == "E2M_SNAPSHOT_PERSISTED":
                tok["snapshots_created"] += 1

            if close_result.get("lane_q_integrity_eligible"):
                tok["lane_q_valid_windows"] += 1
            elif close_result.get("memory_window_close_status") not in (
                "NOT_ATTEMPTED", None
            ):
                tok["lane_q_blocked_windows"] += 1

            cycle_summary: dict[str, Any] = {
                "slot": slot,
                "mint": mint,
                "tick": tick_count,
                "e2j_status": close_result.get("e2j_status"),
                "snapshot_id": close_result.get("snapshot_id"),
                "snapshot_id_for_window": close_result.get("snapshot_id_for_window"),
                "snapshot_start_id": tok["window_start_snapshot_id"],
                "memory_window_id": close_result.get("memory_window_id"),
                "window_start_at": close_result.get("window_start_at"),
                "window_end_at": close_result.get("window_end_at"),
                "elapsed_seconds": close_result.get("elapsed_seconds"),
                "lane_q_integrity_eligible": close_result.get("lane_q_integrity_eligible"),
                "memory_quality_label": close_result.get("memory_quality_label"),
                "exec_error": close_result.get("exec_error"),
            }

            if close_result.get("e2j_status") != _X2_STEP_EXECUTED:
                stopped_safely_reason = (
                    f"slot {slot} window-close stopped:"
                    f" {close_result.get('cycle_status', 'UNKNOWN')}"
                    + (
                        f" — {close_result.get('exec_error', '')}"
                        if close_result.get("exec_error")
                        else ""
                    )
                )
                final_status = LANE_X2_STATUS_STOPPED
                tok["cycles"].append(cycle_summary)
                break

            total_window_closes += 1
            tok["window_closes"] += 1

            # Lane K: process all eligible windows (both tokens).
            lane_k_result = run_e2z_pipeline(
                db_path, operator_approved=True, production_mode=True
            )
            tok["lane_k_runs"] += 1

            k_clean = int(lane_k_result.get("clean_memory_rows_created", 0) or 0)
            k_already = int(lane_k_result.get("e2z_already_exists_count", 0) or 0)
            k_blocked = int(lane_k_result.get("e2z_blocked_count", 0) or 0)

            tok["clean_memory_created"] += k_clean
            tok["e2z_already_exists_count"] += k_already
            tok["dirty_memory_count"] += k_blocked
            clean_memory_rows_created += k_clean
            e2z_already_exists_count += k_already
            dirty_or_blocked_memory_count += k_blocked

            cycle_summary["lane_k_status"] = lane_k_result.get("lane_k_status")
            cycle_summary["lane_k_clean_created"] = k_clean
            tok["cycles"].append(cycle_summary)

            # Reset window state for this token.
            tok["window_open_mono"] = None
            tok["window_start_snapshot_id"] = None

        tick_count += 1

        if snapshot_interval_seconds > 0:
            remaining = max_duration_seconds - _elapsed(loop_start)
            actual_sleep = min(snapshot_interval_seconds, max(0.0, remaining))
            if actual_sleep > 0:
                time.sleep(actual_sleep)

    run_finished_at = _utc_now()
    actual_duration_seconds = _elapsed(loop_start)

    if final_status == LANE_X2_STATUS_COMPLETED and stopped_safely_reason is None:
        stopped_safely_reason = (
            f"duration limit reached after {total_window_closes} window close(s)"
        )

    forbidden_counts = _check_forbidden_tables(db_path)

    def _token_report(tok: dict[str, Any]) -> dict[str, Any]:
        return {
            "slot": tok["slot"],
            "mint": tok["mint"],
            "snapshots_created": tok["snapshots_created"],
            "memory_windows_created": tok["memory_windows_created"],
            "source_requests_created": tok["source_requests_created"],
            "source_responses_created": tok["source_responses_created"],
            "source_failures_created": tok["source_failures_created"],
            "lane_q_valid_windows": tok["lane_q_valid_windows"],
            "lane_q_blocked_windows": tok["lane_q_blocked_windows"],
            "window_closes": tok["window_closes"],
            "clean_memory_created": tok["clean_memory_created"],
            "dirty_memory_count": tok["dirty_memory_count"],
            "e2z_already_exists_count": tok["e2z_already_exists_count"],
            "lane_k_runs": tok["lane_k_runs"],
        }

    return {
        "command": LANE_X2_COMMAND_NAME,
        "lane_x2_status": final_status,
        "operator_approved": True,
        "db_path": db_path_str,
        "selected_profile": duration_profile,
        "requested_duration_seconds": max_duration_seconds,
        "actual_duration_seconds": round(actual_duration_seconds, 3),
        "run_started_at": run_started_at,
        "run_finished_at": run_finished_at,
        "window_kind": window_kind,
        "window_kind_enabled": window_kind == _ENABLED_MAIN_WINDOW_KIND,
        "disabled_collection_window_kinds": sorted(_DISABLED_COLLECTION_WINDOW_KINDS),
        "support_only_window_kinds": sorted(_SUPPORT_ONLY_WINDOW_KINDS),
        "selected_token_count": LANE_X2_EXACT_TOKEN_COUNT,
        "token_a_mint": mint_a,
        "token_b_mint": mint_b,
        "token_list_valid": token_list_valid,
        "token_list_reason": token_list_reason,
        "total_window_closes": total_window_closes,
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
        "hard_locks": dict(_HARD_LOCKS),
        "buy_enabled": False,
        "sell_enabled": False,
        "hold_enabled": False,
        "forbidden_table_counts": forbidden_counts,
        "token_a_report": _token_report(token_states[0]),
        "token_b_report": _token_report(token_states[1]),
        "cycles": token_states[0]["cycles"] + token_states[1]["cycles"],
    }
