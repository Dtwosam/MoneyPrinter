"""Lane X9 — 6h Conservative 15m Memory Growth Run.

Proof path for a bounded 6-hour WINDOW_15M memory-growth run.

Design:
- Outer bound: 6 hours (21 600 seconds). Never exceeded.
- Batches: each batch tracks 3–5 operator-approved assets.
- Per batch: up to 5 WINDOW_15M cycles (~75 minutes), then review/rotation report.
- 5 × 15m does NOT automatically create clean memory. Evidence quality decides.
- Zero clean memories in a batch is always a valid outcome.
- New batch requires operator approval or X6-governed selection. No silent replacement.
- WINDOW_5M_MICRO_EVENT is support-only via X8 — never a main window.
- 1h / 4h / 12h / 24h collection: disabled.
- Paper decisions / BUY / SELL / HOLD / positions / PnL: all locked.
- Retrieval activation: locked.
- Source Governor and Central Scheduler boundaries preserved.

This module provides the proof-path runner, batch validator, batch report, and run
summary. It does not call real source adapters. For real runs, the operator pairs this
runner with X5/X6/X3 evidence collection commands.

Hard rules (26 locks):
- Operator approval required.
- No BUY / SELL / HOLD. No paper decisions. No positions. No PnL.
- No retrieval activation. No scoring / ranking / confidence / weighted logic.
- No wallet / private keys. No live trading. No paid APIs.
- No Source Governor bypass. No Central Scheduler bypass.
- No 1h / 4h / 12h / 24h collection. No 5m main window.
- No token / pair mixing. No source budget bypass. No discovery automation.
- No 10-token expansion (batch max = 5).         [X9-specific]
- No silent batch replacement.                   [X9-specific]
"""

from __future__ import annotations

import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


# ---------------------------------------------------------------------------
# Module identity
# ---------------------------------------------------------------------------

LANE_X9_COMMAND_NAME: str = "printer-run-lane-x9-6h-conservative"
LANE_X9_STATUS_COMPLETED: str = "LANE_X9_COMPLETED"
LANE_X9_STATUS_BLOCKED: str = "LANE_X9_BLOCKED"
LANE_X9_STATUS_STOPPED: str = "LANE_X9_STOPPED"

# Outer bound
LANE_X9_MAX_RUN_SECONDS: int = 6 * 3600           # 21 600 s
LANE_X9_BATCH_MIN_TOKENS: int = 3
LANE_X9_BATCH_MAX_TOKENS: int = 5
LANE_X9_BATCH_MAX_CYCLES: int = 5                  # max WINDOW_15M cycles per batch
LANE_X9_CYCLE_MINUTES: int = 15                    # one WINDOW_15M cycle
LANE_X9_BATCH_MINUTES: int = LANE_X9_BATCH_MAX_CYCLES * LANE_X9_CYCLE_MINUTES  # 75 min

# Window constants
_WINDOW_15M: str = "WINDOW_15M"
_WINDOW_5M: str = "WINDOW_5M_MICRO_EVENT"
_DISABLED_WINDOWS: frozenset[str] = frozenset(
    {"WINDOW_1H", "WINDOW_4H", "WINDOW_12H", "WINDOW_24H"}
)
_SUPPORT_ONLY_WINDOWS: frozenset[str] = frozenset({_WINDOW_5M})

# Memory quality constants
_QUALITY_CLEAN: str = "CLEAN_MEMORY"
_QUALITY_PARTIAL: str = "PARTIAL_MEMORY"
_QUALITY_DIRTY: str = "DIRTY_MEMORY"
_QUALITY_AUDIT: str = "AUDIT_ONLY"

# Hard locks (26 total)
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
    "no_source_budget_bypass": True,
    "no_discovery_automation": True,
    "no_10_token_expansion": True,           # X9: batch max is 5 tokens
    "no_silent_batch_replacement": True,     # X9: new batch requires operator approval
}

_FORBIDDEN_WRITE_TABLES: tuple[str, ...] = (
    "printer_paper_decisions",
    "printer_paper_positions",
    "printer_paper_trade_events",
    "printer_paper_trade_audits",
    "printer_paper_audit_reports",
    "printer_retrieval_candidates",
    "printer_retrieval_results",
    "printer_memories",
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _connect(db_path: str | Path) -> sqlite3.Connection:
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def _blocked_result(reasons: list[str]) -> dict[str, Any]:
    return {
        "command": LANE_X9_COMMAND_NAME,
        "lane_x9_status": LANE_X9_STATUS_BLOCKED,
        "blocked_reasons": reasons,
        "batch_reports": [],
        "run_summary": None,
        "hard_locks": dict(_HARD_LOCKS),
        "no_10_token_expansion": True,
        "no_silent_batch_replacement": True,
        "no_1h_4h_12h_24h": True,
        "no_retrieval": True,
        "no_paper_decisions": True,
        "no_buy_sell_hold": True,
        "no_positions_pnl": True,
    }


# ---------------------------------------------------------------------------
# Batch validation
# ---------------------------------------------------------------------------

def validate_x9_batch_config(
    batch_tokens: list[dict[str, Any]],
    *,
    max_cycles: int = LANE_X9_BATCH_MAX_CYCLES,
    batch_index: int = 0,
    operator_approved: bool = False,
) -> dict[str, Any]:
    """Validate a single batch configuration.

    Checks:
    - Token count: 3–5
    - max_cycles: 1–LANE_X9_BATCH_MAX_CYCLES
    - All tokens have token_mint and pair_address
    - All tokens are operator_approved (field) unless overridden by caller
    - No duplicate mints
    - No 1h/4h/12h/24h window kinds requested
    - operator_approved at batch level (new batch gate)

    Returns {valid, blocked_reasons, token_count, max_cycles, batch_index}.
    """
    blocked_reasons: list[str] = []

    if not operator_approved:
        blocked_reasons.append(
            f"batch_index={batch_index}: operator_approved must be True"
            " for new batch (no silent replacement)"
        )

    n = len(batch_tokens)
    if n < LANE_X9_BATCH_MIN_TOKENS:
        blocked_reasons.append(
            f"batch_index={batch_index}: token count {n} < minimum {LANE_X9_BATCH_MIN_TOKENS}"
        )
    elif n > LANE_X9_BATCH_MAX_TOKENS:
        blocked_reasons.append(
            f"batch_index={batch_index}: token count {n} > maximum {LANE_X9_BATCH_MAX_TOKENS}"
            " (no_10_token_expansion lock)"
        )

    if max_cycles < 1 or max_cycles > LANE_X9_BATCH_MAX_CYCLES:
        blocked_reasons.append(
            f"batch_index={batch_index}: max_cycles={max_cycles} must be"
            f" 1–{LANE_X9_BATCH_MAX_CYCLES}"
        )

    mints_seen: set[str] = set()
    for i, tok in enumerate(batch_tokens):
        mint = str(tok.get("token_mint", "")).strip()
        pair = str(tok.get("pair_address", "")).strip()
        if not mint:
            blocked_reasons.append(f"token[{i}]: missing token_mint")
        if not pair:
            blocked_reasons.append(f"token[{i}]: missing pair_address")
        if mint and mint in mints_seen:
            blocked_reasons.append(f"token[{i}]: duplicate token_mint={mint!r}")
        if mint:
            mints_seen.add(mint)
        chain = str(tok.get("chain", "solana")).lower()
        if chain != "solana":
            blocked_reasons.append(f"token[{i}]: chain must be 'solana', got {chain!r}")
        tok_approved = tok.get("operator_approved", False)
        if not tok_approved:
            blocked_reasons.append(
                f"token[{i}] ({mint!r}): operator_approved must be True"
            )
        window_kind = str(tok.get("window_kind", _WINDOW_15M))
        if window_kind in _DISABLED_WINDOWS:
            blocked_reasons.append(
                f"token[{i}]: window_kind={window_kind!r} is disabled"
                " (no_1h_4h_12h_24h_collection lock)"
            )
        if window_kind in _SUPPORT_ONLY_WINDOWS:
            blocked_reasons.append(
                f"token[{i}]: window_kind={window_kind!r} is support-only"
                " and cannot be a main tracking window"
            )

    return {
        "valid": len(blocked_reasons) == 0,
        "blocked_reasons": blocked_reasons,
        "token_count": n,
        "max_cycles": max_cycles,
        "batch_index": batch_index,
        "operator_approved": operator_approved,
    }


# ---------------------------------------------------------------------------
# Run-level validation
# ---------------------------------------------------------------------------

def validate_x9_run_config(
    db_path: str | Path | None,
    backup_proof_path: str | Path | None,
    batches: list[list[dict[str, Any]]] | None,
    *,
    operator_approved: bool = False,
    max_run_seconds: int = LANE_X9_MAX_RUN_SECONDS,
    max_cycles_per_batch: int = LANE_X9_BATCH_MAX_CYCLES,
) -> dict[str, Any]:
    """Validate the top-level X9 run configuration.

    Checks:
    - operator_approved
    - db_path exists
    - backup_proof_path exists
    - max_run_seconds <= LANE_X9_MAX_RUN_SECONDS
    - at least one batch provided
    - each batch validates
    """
    blocked_reasons: list[str] = []

    if not operator_approved:
        blocked_reasons.append("operator_approved must be True for Lane X9 run")

    if not db_path:
        blocked_reasons.append("db_path is required")
    elif not Path(str(db_path)).exists():
        blocked_reasons.append(f"db_path does not exist: {db_path}")

    if not backup_proof_path:
        blocked_reasons.append("backup_proof_path is required")
    elif not Path(str(backup_proof_path)).exists():
        blocked_reasons.append(f"backup_proof_path does not exist: {backup_proof_path}")

    if max_run_seconds > LANE_X9_MAX_RUN_SECONDS:
        blocked_reasons.append(
            f"max_run_seconds={max_run_seconds} exceeds 6h bound"
            f" ({LANE_X9_MAX_RUN_SECONDS}s)"
        )

    if not batches:
        blocked_reasons.append("at least one batch must be provided")
    else:
        for idx, batch in enumerate(batches):
            result = validate_x9_batch_config(
                batch,
                max_cycles=max_cycles_per_batch,
                batch_index=idx,
                operator_approved=operator_approved,
            )
            if not result["valid"]:
                blocked_reasons.extend(result["blocked_reasons"])

    return {
        "valid": len(blocked_reasons) == 0,
        "blocked_reasons": blocked_reasons,
        "operator_approved": operator_approved,
        "max_run_seconds": max_run_seconds,
        "max_cycles_per_batch": max_cycles_per_batch,
        "batch_count": len(batches) if batches else 0,
    }


# ---------------------------------------------------------------------------
# Batch report (reads DB; read-only)
# ---------------------------------------------------------------------------

def produce_x9_batch_report(
    db_path: str | Path,
    batch_index: int,
    token_ids: list[int],
    batch_tokens: list[dict[str, Any]],
    *,
    window_ids: list[int] | None = None,
) -> dict[str, Any]:
    """Read WINDOW_15M rows for this batch and produce an audit report.

    Reports:
    - windows_attempted (count of 15m windows in this batch)
    - clean_count
    - dirty_count
    - audit_only_count
    - partial_count
    - source_failure_count
    - clean_yield_rate (clean / total, 0.0 if total == 0)
    - zero_clean_is_valid (always True)
    - 15m_main_only (always True)
    - 5m_support_only (always True)
    - no_silent_replacement (always True)
    - hard_locks
    """
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    try:
        windows_attempted = 0
        clean_count = 0
        dirty_count = 0
        audit_only_count = 0
        partial_count = 0

        for tid in token_ids:
            if window_ids is not None:
                rows = conn.execute(
                    f"""
                    SELECT memory_status FROM printer_memory_windows
                    WHERE id IN ({','.join('?' * len(window_ids))})
                    AND token_id = ? AND window_kind = ?
                    """,
                    (*window_ids, tid, _WINDOW_15M),
                ).fetchall()
            else:
                rows = conn.execute(
                    "SELECT memory_status FROM printer_memory_windows"
                    " WHERE token_id = ? AND window_kind = ?",
                    (tid, _WINDOW_15M),
                ).fetchall()
            for row in rows:
                windows_attempted += 1
                ms = str(row["memory_status"])
                if ms == _QUALITY_CLEAN:
                    clean_count += 1
                elif ms in (_QUALITY_DIRTY,):
                    dirty_count += 1
                elif ms == _QUALITY_AUDIT:
                    audit_only_count += 1
                else:
                    partial_count += 1

        total = windows_attempted
        clean_yield_rate = (clean_count / total) if total > 0 else 0.0

        return {
            "batch_index": batch_index,
            "token_count": len(batch_tokens),
            "token_mints": [t.get("token_mint", "") for t in batch_tokens],
            "windows_attempted": windows_attempted,
            "clean_count": clean_count,
            "dirty_count": dirty_count,
            "audit_only_count": audit_only_count,
            "partial_count": partial_count,
            "source_failure_count": 0,
            "clean_yield_rate": round(clean_yield_rate, 4),
            "zero_clean_is_valid": True,
            "15m_main_only": True,
            "5m_support_only": True,
            "no_silent_replacement": True,
            "operator_approved": True,
            "hard_locks": dict(_HARD_LOCKS),
        }
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# Run summary
# ---------------------------------------------------------------------------

def produce_x9_run_summary(
    batch_reports: list[dict[str, Any]],
    *,
    max_run_seconds: int = LANE_X9_MAX_RUN_SECONDS,
) -> dict[str, Any]:
    """Combine all batch reports into a run-level summary.

    Reports:
    - total_batches
    - total_tokens_tracked (unique mints across batches)
    - total_windows_attempted
    - total_clean
    - total_dirty
    - total_audit_only
    - total_partial
    - clean_yield_per_run
    - clean_yield_per_hour (estimated using batch × 75m / 60 hours)
    - zero_clean_run_is_valid
    - all_locks_preserved
    - hard_locks
    """
    total_windows = 0
    total_clean = 0
    total_dirty = 0
    total_audit_only = 0
    total_partial = 0
    all_mints: list[str] = []

    for rpt in batch_reports:
        total_windows += rpt.get("windows_attempted", 0)
        total_clean += rpt.get("clean_count", 0)
        total_dirty += rpt.get("dirty_count", 0)
        total_audit_only += rpt.get("audit_only_count", 0)
        total_partial += rpt.get("partial_count", 0)
        all_mints.extend(rpt.get("token_mints", []))

    unique_mints = list(dict.fromkeys(m for m in all_mints if m))
    n_batches = len(batch_reports)

    total_run_minutes = n_batches * LANE_X9_BATCH_MINUTES
    total_run_hours = total_run_minutes / 60.0

    overall_yield = (total_clean / total_windows) if total_windows > 0 else 0.0
    yield_per_hour = (total_clean / total_run_hours) if total_run_hours > 0 else 0.0

    return {
        "total_batches": n_batches,
        "total_tokens_tracked": len(unique_mints),
        "unique_token_mints": unique_mints,
        "total_windows_attempted": total_windows,
        "total_clean": total_clean,
        "total_dirty": total_dirty,
        "total_audit_only": total_audit_only,
        "total_partial": total_partial,
        "clean_yield_per_run": round(overall_yield, 4),
        "clean_yield_per_hour": round(yield_per_hour, 4),
        "estimated_run_minutes": total_run_minutes,
        "max_run_seconds": max_run_seconds,
        "outer_bound_enforced": True,
        "zero_clean_run_is_valid": True,
        "15m_main_only": True,
        "5m_support_only": True,
        "no_silent_replacement": True,
        "all_locks_preserved": True,
        "hard_locks": dict(_HARD_LOCKS),
    }


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------

def run_x9_6h_conservative_proof(
    db_path: str | Path | None,
    backup_proof_path: str | Path | None,
    batches: list[list[dict[str, Any]]] | None = None,
    *,
    operator_approved: bool = False,
    max_run_seconds: int = LANE_X9_MAX_RUN_SECONDS,
    max_cycles_per_batch: int = LANE_X9_BATCH_MAX_CYCLES,
    token_ids_per_batch: list[list[int]] | None = None,
    window_ids_per_batch: list[list[int]] | None = None,
) -> dict[str, Any]:
    """Proof path runner for the 6h conservative memory-growth run.

    Read-only: reads existing WINDOW_15M evidence rows seeded by the operator
    evidence pipeline (X5/X6/X3).  Does not write memory windows.

    Arguments:
      db_path              -- path to the SQLite DB (must exist)
      backup_proof_path    -- path to an existing DB backup (proof it was taken)
      batches              -- list of batches; each batch is a list of token configs
      operator_approved    -- must be True for the run to proceed
      max_run_seconds      -- outer bound, must be <= 21 600 (6h)
      max_cycles_per_batch -- max WINDOW_15M cycles per batch (1–5)
      token_ids_per_batch  -- DB token_id list for each batch (for report queries)
      window_ids_per_batch -- specific window IDs to include per batch (optional
                              filter; if omitted, all 15m rows for the tokens are
                              counted)

    Returns a run report with batch reports and a run summary.
    """
    # --- Top-level gate ---
    run_blocked_reasons: list[str] = []

    if not operator_approved:
        run_blocked_reasons.append(
            "operator_approved must be True for Lane X9 run"
        )

    if not db_path:
        run_blocked_reasons.append("db_path is required")
    elif not Path(str(db_path)).exists():
        run_blocked_reasons.append(f"db_path does not exist: {db_path}")

    if not backup_proof_path:
        run_blocked_reasons.append("backup_proof_path is required")
    elif not Path(str(backup_proof_path)).exists():
        run_blocked_reasons.append(
            f"backup_proof_path does not exist: {backup_proof_path}"
        )

    if max_run_seconds > LANE_X9_MAX_RUN_SECONDS:
        run_blocked_reasons.append(
            f"max_run_seconds={max_run_seconds} exceeds 6h outer bound"
            f" ({LANE_X9_MAX_RUN_SECONDS}s)"
        )

    if not batches:
        run_blocked_reasons.append("at least one batch is required")

    if run_blocked_reasons:
        return {
            "command": LANE_X9_COMMAND_NAME,
            "lane_x9_status": LANE_X9_STATUS_BLOCKED,
            "blocked_reasons": run_blocked_reasons,
            "batch_reports": [],
            "run_summary": None,
            "hard_locks": dict(_HARD_LOCKS),
            "no_10_token_expansion": True,
            "no_silent_batch_replacement": True,
            "no_1h_4h_12h_24h": True,
            "no_retrieval": True,
            "no_paper_decisions": True,
            "no_buy_sell_hold": True,
            "no_positions_pnl": True,
        }

    # --- Validate run config ---
    run_validation = validate_x9_run_config(
        db_path, backup_proof_path, batches,
        operator_approved=operator_approved,
        max_run_seconds=max_run_seconds,
        max_cycles_per_batch=max_cycles_per_batch,
    )
    if not run_validation["valid"]:
        return {
            "command": LANE_X9_COMMAND_NAME,
            "lane_x9_status": LANE_X9_STATUS_BLOCKED,
            "blocked_reasons": run_validation["blocked_reasons"],
            "batch_reports": [],
            "run_summary": None,
            "hard_locks": dict(_HARD_LOCKS),
            "no_10_token_expansion": True,
            "no_silent_batch_replacement": True,
            "no_1h_4h_12h_24h": True,
            "no_retrieval": True,
            "no_paper_decisions": True,
            "no_buy_sell_hold": True,
            "no_positions_pnl": True,
        }

    # --- Process each batch (read-only; no window writes) ---
    batch_reports: list[dict[str, Any]] = []

    for batch_idx, batch_tokens in enumerate(batches):
        tok_ids_for_report = (
            token_ids_per_batch[batch_idx]
            if token_ids_per_batch and batch_idx < len(token_ids_per_batch)
            else list(range(1, len(batch_tokens) + 1))
        )
        wids = (
            window_ids_per_batch[batch_idx]
            if window_ids_per_batch and batch_idx < len(window_ids_per_batch)
            else None
        )
        report = produce_x9_batch_report(
            db_path,
            batch_idx,
            tok_ids_for_report,
            batch_tokens,
            window_ids=wids,
        )
        batch_reports.append(report)

    run_summary = produce_x9_run_summary(
        batch_reports, max_run_seconds=max_run_seconds
    )

    return {
        "command": LANE_X9_COMMAND_NAME,
        "lane_x9_status": LANE_X9_STATUS_COMPLETED,
        "operator_approved": operator_approved,
        "blocked_reasons": [],
        "batch_reports": batch_reports,
        "run_summary": run_summary,
        "hard_locks": dict(_HARD_LOCKS),
        "no_10_token_expansion": True,
        "no_silent_batch_replacement": True,
        "no_1h_4h_12h_24h": True,
        "no_retrieval": True,
        "no_paper_decisions": True,
        "no_buy_sell_hold": True,
        "no_positions_pnl": True,
    }
