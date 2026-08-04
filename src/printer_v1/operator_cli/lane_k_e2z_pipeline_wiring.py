"""Lane K — E2Q-to-E2Z Clean-Memory Pipeline Wiring Boundary.

Connects existing audited 15m windows into the clean-memory creation path:

  E2Q-audited WINDOW_15M
  → E2X eligibility (build_e2x_15m_clean_memory_eligibility_report)
  → Lane Q integrity guard (guard_candidate_windows) — filters by real 15m
  → Lane U2 coverage persistence (persist_coverage_for_windows) — runs for
      ALL Lane Q-valid windows, independent of E2Y same-pair grouping
  → E2Y candidate set gate (build_e2y_15m_candidate_set_gate_report)
      — informational reporting for mixed operational batches
  → E2Z clean-memory creation (create_clean_memory_from_window) with
      individual_promotion=True

Coverage persistence is decoupled from the E2Y set gate so that valid
WINDOW_15M windows get their coverage written even when E2Y fails because
windows are split across different pair_ids or mixed memory statuses.

Adopted promotion contract (Lane X10 / V2-6.1a closeouts):
  * Operational mixed batches use individual promotion: E2Y batch passage is
    NOT mandatory for E2Z. E2Z per-window ``_gate_window`` is the final
    individual authority (dirty / do_not_train / quality still block).
  * E2Y remains available and mandatory for explicit batch mode
    (``individual_promotion=False`` on ``create_clean_memory_from_window``).
  * Zero clean memories is a valid outcome when no window passes per-window
    gates (independent of E2Y batch status).

Requires operator_approved=True and a valid db_path.

Idempotent: a second call for the same DB creates zero new rows (E2Z returns
E2Z_ALREADY_EXISTS for each window it already processed).

Permanently locked (no unlock path in this module):
  retrieval, paper decisions, BUY/SELL/HOLD, positions, trade events,
  paper trade audits, PnL, live trading, wallet/private keys,
  source fetching, scheduler jobs, paid APIs, scoring, embeddings,
  5m as main outcome memory.

Classification outcomes:
  LANE_K_COMPLETED  — pipeline ran; clean_memory_rows_created >= 0 (zero valid)
  LANE_K_BLOCKED    — operator_approved not set or db_path missing/invalid
"""

from __future__ import annotations

import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from printer_v1.operator_cli.e2x_15m_clean_memory_eligibility import (
    E2X_STATUS_BLOCKED as _E2X_STATUS_BLOCKED,
    build_e2x_15m_clean_memory_eligibility_report,
)
from printer_v1.operator_cli.e2y_15m_candidate_set_gate import (
    build_e2y_15m_candidate_set_gate_report,
)
from printer_v1.operator_cli.e2z_clean_memory_creation import (
    E2Z_STATUS_ALREADY_EXISTS,
    E2Z_STATUS_BLOCKED as _E2Z_STATUS_BLOCKED,
    E2Z_STATUS_CREATED,
    create_clean_memory_from_window,
)
from printer_v1.operator_cli.lane_q_15m_window_integrity_guard import (
    LANE_Q_GUARD_COMPLETED,
    guard_candidate_windows,
)
from printer_v1.operator_cli.lane_u2_coverage_audit_persistence import (
    COVERAGE_STATE_BLOCKED,
    LANE_U2_STATUS_COMPLETED,
    persist_coverage_for_windows,
)


LANE_K_STATUS_COMPLETED: str = "LANE_K_COMPLETED"
LANE_K_STATUS_BLOCKED: str = "LANE_K_BLOCKED"

LANE_K_NAME: str = "Lane K — E2Q-to-E2Z Clean-Memory Pipeline Wiring"

_TRACKED_TABLES: tuple[str, ...] = (
    "printer_episodes",
    "printer_snapshot_window_coverage",
    "printer_snapshot_gap_audits",
    "printer_source_requests",
    "printer_source_responses",
    "printer_source_failures",
    "printer_scheduler_jobs",
    "printer_paper_decisions",
    "printer_paper_positions",
    "printer_paper_trade_events",
    "printer_paper_trade_audits",
)

_HARD_LOCKS: dict[str, bool] = {
    "no_retrieval_activation": True,
    "no_paper_decisions": True,
    "no_buy_sell_hold": True,
    "no_positions": True,
    "no_pnl": True,
    "no_live_trading": True,
    "no_wallet_private_key": True,
    "no_paid_api": True,
    "no_source_fetching": True,
    "no_scheduler_runtime_expansion": True,
    "no_scoring_ranking_confidence": True,
    "no_embeddings_vectors": True,
    "no_5m_main_outcome": True,
    "no_new_write_path_outside_e2z": True,
    "no_scheduler_jobs_created": True,
    "no_source_requests_created": True,
    "no_trade_events_created": True,
    "no_paper_trade_audits_created": True,
}

_LOCKED_CAPABILITIES: dict[str, bool] = {
    "retrieval_active": False,
    "paper_decision_creation_active": False,
    "buy_unlock_active": False,
    "sell_unlock_active": False,
    "hold_unlock_active": False,
    "paper_positions_active": False,
    "pnl_active": False,
    "trade_events_active": False,
    "paper_trade_audits_active": False,
    "live_trading_active": False,
    "wallet_active": False,
    "5m_main_outcome_active": False,
    "scheduler_jobs_created": False,
    "source_requests_created": False,
}

_RECOMMENDED_NEXT_ACTION: str = (
    "Rerun to verify idempotency (e2z_already_exists_count should equal "
    "e2z_created_count from the first run). Operational promotion uses "
    "individual_promotion=True: when e2z_created_count is zero, inspect "
    "per-window E2X / Lane Q / Lane U2 / E2Z _gate_window blockers rather "
    "than requiring E2Y batch passage. E2Y remains informational in mixed "
    "batches and is still mandatory only for explicit batch-mode promotion."
)


def _count_table(db_path: str, table: str) -> int | str:
    try:
        conn = sqlite3.connect(db_path)
        try:
            row = conn.execute(
                "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?",
                (table,),
            ).fetchone()
            if row is None:
                return "table_absent"
            return int(conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0])
        finally:
            conn.close()
    except Exception:
        return "count_error"


def _snapshot_counts(db_path: str) -> dict[str, int | str]:
    return {t: _count_table(db_path, t) for t in _TRACKED_TABLES}


def _delta_summary(
    before: dict[str, int | str],
    after: dict[str, int | str],
) -> dict[str, Any]:
    summary: dict[str, Any] = {}
    for table in _TRACKED_TABLES:
        b = before[table]
        a = after[table]
        if isinstance(b, int) and isinstance(a, int):
            summary[table] = {"before": b, "after": a, "delta": a - b}
        else:
            summary[table] = {"before": b, "after": a, "delta": "unknown"}
    return summary


def _blocked_result(reasons: list[str], db_path_str: str) -> dict[str, Any]:
    return {
        "lane_k_status": LANE_K_STATUS_BLOCKED,
        "lane": LANE_K_NAME,
        "operator_approved": False,
        "db_path": db_path_str,
        "blocked_reasons": reasons,
        "e2x_status": _E2X_STATUS_BLOCKED,
        "e2y_status": "E2Y_SET_GATE_BLOCKED",
        "e2y_set_gate_passed": False,
        "e2z_created_count": 0,
        "e2z_already_exists_count": 0,
        "e2z_blocked_count": 0,
        "clean_memory_rows_created": 0,
        "candidate_window_ids": [],
        "zero_clean_memories_valid": True,
        "hard_locks": dict(_HARD_LOCKS),
        "locked_capabilities": dict(_LOCKED_CAPABILITIES),
        "db_delta_summary": {},
        "recommended_next_action": _RECOMMENDED_NEXT_ACTION,
        "retrieval_activated": False,
        "paper_decisions_created": 0,
        "buy_enabled": False,
        "sell_enabled": False,
        "hold_enabled": False,
        "positions_created": 0,
        "pnl_created": 0,
        "trade_events_created": 0,
        "paper_trade_audits_created": 0,
    }


def _downgrade_blocked_windows(db_path: str, window_ids: list[int]) -> None:
    """Downgrade quality fields on printer_memory_windows for Lane Q-blocked windows.

    Prevents E2Y's independent DB query from including windows that Lane Q
    already rejected due to coverage policy violations (gap or count failures).
    Must be called BEFORE E2Y runs.
    """
    if not window_ids:
        return
    now = datetime.now(tz=timezone.utc).isoformat()
    conn = sqlite3.connect(db_path)
    try:
        placeholders = ",".join("?" * len(window_ids))
        conn.execute(
            f"""
            UPDATE printer_memory_windows
            SET data_quality_label = 'MISSING_CRITICAL_DATA',
                memory_status = 'DIRTY_MEMORY',
                do_not_train = 1,
                updated_at = ?
            WHERE id IN ({placeholders})
            """,
            (now, *window_ids),
        )
        conn.commit()
    finally:
        conn.close()


def _e2y_blocked_reason(
    set_gate: dict[str, Any],
    token_pairs: list,
    coverage_blocked_count: int = 0,
    lane_q_excluded_count: int = 0,
) -> str:
    """Derive a human-readable explanation of why the E2Y set gate did not pass."""
    parts: list[str] = []
    total_excluded = coverage_blocked_count + lane_q_excluded_count
    if total_excluded > 0:
        parts.append(
            f"{total_excluded} window(s) excluded from candidacy: "
            "coverage BLOCKED (snapshot count or gap policy violation); "
            "these windows do not count toward the 5-window gate"
        )
    if not set_gate.get("candidate_count_is_5"):
        parts.append("fewer than 5 coverage-eligible candidate windows")
    if not set_gate.get("all_same_token_pair") and len(token_pairs) > 1:
        n = len(token_pairs)
        parts.append(
            f"windows span {n} different (token_id, pair_id) combinations; "
            "no single pair has 5 or more coverage-eligible windows "
            "(check whether a second source run used a different pair_address)"
        )
    if not set_gate.get("all_partial_memory"):
        parts.append("not all windows have PARTIAL_MEMORY status")
    if not set_gate.get("all_e2q_audited"):
        parts.append("not all windows are E2Q-audited")
    if not set_gate.get("all_clean_data"):
        parts.append("not all windows have CLEAN_DATA label")
    if not parts:
        parts.append("set gate condition(s) not satisfied")
    return "; ".join(parts)


def run_e2z_pipeline(
    db_path: str | Path | None,
    *,
    operator_approved: bool = False,
    production_mode: bool = False,
) -> dict[str, Any]:
    """Wire E2X eligibility → Lane Q guard → Lane U2 coverage → E2Y set gate → E2Z.

    Coverage persistence (Lane U2) runs for ALL Lane Q-valid windows regardless of
    whether the E2Y same-pair set gate passes.  E2Y still gates clean-memory
    creation (E2Z); zero clean memories is always a valid outcome.

    Requires operator_approved=True and a valid db_path.
    Idempotent: re-running does not duplicate coverage or clean-memory rows.
    """
    blocked_reasons: list[str] = []

    if not operator_approved:
        blocked_reasons.append("operator_approved must be True")

    db_path_str: str = ""
    if db_path is None:
        blocked_reasons.append("db_path is required")
    else:
        p = Path(db_path)
        db_path_str = str(p)
        if not p.is_file():
            blocked_reasons.append(f"db_path not found: {db_path}")

    if blocked_reasons:
        return _blocked_result(blocked_reasons, db_path_str)

    before = _snapshot_counts(db_path_str)

    # Step 1: E2X eligibility — all WINDOW_15M candidates
    e2x_report = build_e2x_15m_clean_memory_eligibility_report(
        db_path, operator_approved=True
    )
    e2x_status = e2x_report.get("e2x_status", _E2X_STATUS_BLOCKED)
    all_eligible_ids: list[int] = list(e2x_report.get("review_candidate_ids", []))

    # Step 2: Lane Q guard for ALL E2X-eligible windows — runs before E2Y so
    #         coverage can be persisted regardless of same-pair grouping outcome.
    lane_q_guard = guard_candidate_windows(
        db_path, all_eligible_ids, operator_approved=True,
        production_mode=production_mode,
    )
    all_valid_ids: list[int] = lane_q_guard.get("valid_window_ids", [])
    all_lane_q_blocked_ids: list[int] = lane_q_guard.get("blocked_window_ids", [])
    all_valid_set: set[int] = set(all_valid_ids)

    # Downgrade Lane Q-blocked windows before E2Y runs so E2Y's independent DB
    # query does not include them in the clean-memory candidate set.
    _downgrade_blocked_windows(db_path_str, all_lane_q_blocked_ids)

    # Step 3: Lane U2 — persist coverage for ALL Lane Q-valid windows.
    #         Decoupled from E2Y: writes coverage rows even when E2Y fails.
    lane_u2_result = persist_coverage_for_windows(
        db_path,
        all_valid_ids,
        operator_approved=True,
        production_mode=production_mode,
    )
    _coverage_blocked: set[int] = set(
        lane_u2_result.get("coverage_blocked_ids", [])
    )
    if production_mode:
        _coverage_blocked |= set(lane_u2_result.get("coverage_unknown_ids", []))
    coverage_persisted_count: int = lane_u2_result.get("coverage_rows_written", 0)
    coverage_blocked_count: int = len(_coverage_blocked)

    # Step 4: E2Y set gate — informational reporting only.
    # The E2Y batch gate (all_partial_memory, candidate_count_is_5) is NOT used
    # to gate E2Z in mixed batches. Individual per-window eligibility (E2Z gate)
    # is the sole authority for clean-memory creation.  This allows a run with
    # 3 PARTIAL_MEMORY + 10 DIRTY_MEMORY windows to promote the 3 clean ones
    # without being blocked by the 10 dirty ones.
    e2y_report = build_e2y_15m_candidate_set_gate_report(
        db_path, operator_approved=True
    )
    e2y_status = e2y_report.get("e2y_status", "E2Y_SET_GATE_BLOCKED")
    set_gate_passed: bool = bool(e2y_report.get("set_gate_passed", False))
    e2y_candidate_ids: list[int] = (
        e2y_report.get("candidate_set_summary", {}).get("candidate_ids", [])
    )

    e2y_candidate_reason: str | None = None
    if not set_gate_passed:
        set_gate = e2y_report.get("set_gate", {})
        token_pairs = (
            e2y_report.get("candidate_set_summary", {}).get("token_pairs", [])
        )
        e2y_candidate_reason = _e2y_blocked_reason(
            set_gate, token_pairs, coverage_blocked_count,
            lane_q_excluded_count=len(all_lane_q_blocked_ids),
        )

    _e2y_css = e2y_report.get("candidate_set_summary", {})

    # Step 5: E2Z for individually eligible windows.
    # Eligible = Lane Q valid ∩ not coverage blocked.
    # E2Z's per-window gate (_gate_window) is the final individual check:
    # it blocks dirty/do_not_train windows that shouldn't be promoted.
    # Dirty windows never reach this set (E2X filters them out before Lane Q).
    e2z_eligible_ids: list[int] = [
        wid for wid in all_valid_ids
        if wid not in _coverage_blocked
    ]

    created_count = 0
    already_exists_count = 0
    e2z_blocked_count = 0
    window_results: list[dict[str, Any]] = []

    for wid in e2z_eligible_ids:
        result = create_clean_memory_from_window(
            db_path,
            wid,
            operator_approved=True,
            individual_promotion=True,
        )
        status = result.get("e2z_status")
        if status == E2Z_STATUS_CREATED:
            created_count += 1
        elif status == E2Z_STATUS_ALREADY_EXISTS:
            already_exists_count += 1
        else:
            e2z_blocked_count += 1
        window_results.append({
            "window_id": wid,
            "e2z_status": status,
            "episode_id": result.get("episode_id"),
            "blocked_by": (
                "e2z_per_window_gate" if status == _E2Z_STATUS_BLOCKED else None
            ),
        })

    # Report coverage-blocked windows (Lane Q valid but coverage blocked — did not reach E2Z)
    for wid in sorted(_coverage_blocked):
        if wid in all_valid_set:
            u2_win_result = next(
                (v for v in lane_u2_result.get("window_coverage_results", [])
                 if v.get("window_id") == wid),
                {},
            )
            window_results.append({
                "window_id": wid,
                "e2z_status": "LANE_U2_COVERAGE_BLOCKED",
                "episode_id": None,
                "blocked_by": "lane_u2_coverage_audit",
                "coverage_state": u2_win_result.get("coverage_state"),
                "coverage_blocked_reason": u2_win_result.get("blocked_reason"),
            })
            e2z_blocked_count += 1

    # Report Lane Q blocked windows (did not reach coverage or E2Z)
    for wid in all_lane_q_blocked_ids:
        lane_q_verdict = next(
            (v for v in lane_q_guard.get("window_verdicts", []) if v.get("window_id") == wid),
            {},
        )
        window_results.append({
            "window_id": wid,
            "e2z_status": "LANE_Q_BLOCKED",
            "episode_id": None,
            "blocked_by": "lane_q_integrity_guard",
            "lane_q_blocked_reasons": lane_q_verdict.get("blocked_reasons", []),
        })

    after = _snapshot_counts(db_path_str)

    blocked_reasons: list[str] = (
        ["E2Y set gate not passed — individual promotion applied"]
        if not set_gate_passed
        else []
    )

    return {
        "lane_k_status": LANE_K_STATUS_COMPLETED,
        "lane": LANE_K_NAME,
        "operator_approved": True,
        "db_path": db_path_str,
        "blocked_reasons": blocked_reasons,
        "e2x_status": e2x_status,
        "e2y_status": e2y_status,
        "e2y_set_gate_passed": set_gate_passed,
        "e2y_candidate_reason": e2y_candidate_reason,
        "selected_candidate_token_id": _e2y_css.get("selected_candidate_token_id"),
        "selected_candidate_pair_id": _e2y_css.get("selected_candidate_pair_id"),
        "ignored_other_pair_candidate_count": _e2y_css.get("ignored_other_pair_candidate_count", 0),
        "coverage_persisted_count": coverage_persisted_count,
        "coverage_blocked_count": coverage_blocked_count,
        "lane_q_guard_status": lane_q_guard.get("lane_q_guard_status"),
        "lane_q_valid_window_ids": all_valid_ids,
        "lane_q_blocked_window_ids": all_lane_q_blocked_ids,
        "lane_q_blocked_count": len(all_lane_q_blocked_ids),
        "lane_u2_status": lane_u2_result.get("lane_u2_status"),
        "lane_u2_coverage_pass_ids": lane_u2_result.get("coverage_pass_ids", []),
        "lane_u2_coverage_blocked_ids": lane_u2_result.get("coverage_blocked_ids", []),
        "lane_u2_coverage_unknown_ids": lane_u2_result.get("coverage_unknown_ids", []),
        "lane_u2_coverage_rows_written": lane_u2_result.get("coverage_rows_written", 0),
        "lane_u2_gap_audit_rows_written": lane_u2_result.get("gap_audit_rows_written", 0),
        "lane_u2_e2z_eligible_ids": e2z_eligible_ids,
        "e2z_created_count": created_count,
        "e2z_already_exists_count": already_exists_count,
        "e2z_blocked_count": e2z_blocked_count,
        "clean_memory_rows_created": created_count,
        "candidate_window_ids": e2y_candidate_ids,
        "zero_clean_memories_valid": True,
        "hard_locks": dict(_HARD_LOCKS),
        "locked_capabilities": dict(_LOCKED_CAPABILITIES),
        "db_delta_summary": _delta_summary(before, after),
        "recommended_next_action": _RECOMMENDED_NEXT_ACTION,
        "e2z_window_results": window_results,
        "retrieval_activated": False,
        "paper_decisions_created": 0,
        "buy_enabled": False,
        "sell_enabled": False,
        "hold_enabled": False,
        "positions_created": 0,
        "pnl_created": 0,
        "trade_events_created": 0,
        "paper_trade_audits_created": 0,
    }
