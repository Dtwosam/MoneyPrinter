"""Lane U — Governed Reusable Memory Factory Operator Runner.

Exposes a bounded, operator-approved Memory Factory runner that grows real 15m
memory through the governed path only:

  Discovery / token-list selection
  → Repeated snapshot-only E2J calls every snapshot_interval_seconds
  → Window-close E2J call after window_close_interval_seconds has elapsed
  → Lane K (E2X→E2Y→Lane Q guard→E2Z) after each window close
  → bounded by wall-clock duration (1h / 4h / 6h / 12h / 24h)
  → 12h/24h require allow_long_bounded_run=True (config-gated, not hardcoded)

Two-interval timing model:
  snapshot_interval_seconds     — how often snapshots are captured inside a window
  window_close_interval_seconds — when the 15m memory window is closed/evaluated

For WINDOW_15M TRACK_FAST:
  target_snapshot_interval_seconds = 90   (use snapshot_interval_seconds=90)
  window_close_interval_seconds    = 900  (15m window)

For WINDOW_15M TRACK_NORMAL:
  target_snapshot_interval_seconds = 180  (use snapshot_interval_seconds=180)
  window_close_interval_seconds    = 900  (15m window)

Hard rules:
- Operator approval required.
- WINDOW_15M is the only enabled main memory window in this lane.
- WINDOW_1H/4H/12H/24H real collection is refused.
- WINDOW_5M_MICRO_EVENT is recognized as support-only; not activated as main.
- No unbounded loop. No daemon mode. No background process.
- No BUY/SELL/HOLD. No paper decisions. No positions. No PnL.
- No direct adapter/source bypass. No ad-hoc API loop.
- No Source Governor bypass. No Central Scheduler bypass.
- No paid APIs. No wallet/private keys. No live trading.
- No retrieval activation.
- No scoring/ranking/confidence/weighted logic.
- No embeddings/vectors.
- Zero clean memories is always a valid outcome.
- Lane K is called with production_mode=True: 0 snapshots in a window range
  → CADENCE_POLICY_BLOCKED (not UNKNOWN); real production must have real coverage.

Duration profiles:
  "1h"  →  3 600 s  — short test run
  "4h"  → 14 400 s  — conservative real run
  "6h"  → 21 600 s  — default approved profile (Memory Factory Guide §20)
  "12h" → 43 200 s  — requires allow_long_bounded_run=True
  "24h" → 86 400 s  — requires allow_long_bounded_run=True

_cycle_budget counting:
  _cycle_budget counts WINDOW CLOSE events, not snapshot-only calls.
  Each window close (full E2J → E2O → E2Q + Lane K) = 1 cycle.
  Snapshot-only calls do not increment the budget counter.

Start-snapshot threading (Lane T compatible):
  window_start_snapshot_id tracks the first snapshot in the current window.
  The window-close E2J call receives it as _snapshot_start_id so E2O can
  write real window_start_at/window_end_at/elapsed_seconds for Lane Q.

Classification outcomes:
  LANE_U_COMPLETED  — run finished within duration; zero or more clean memories
  LANE_U_BLOCKED    — gate check failed before any cycle ran
  LANE_U_STOPPED    — run halted early due to stop condition or failed cycle
"""

from __future__ import annotations

import sqlite3
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from printer_v1.snapshots.cadence_policy import (
    get_policy as _get_cadence_policy,
)


LANE_U_COMMAND_NAME: str = "printer-run-memory-factory-cycle"

LANE_U_STATUS_COMPLETED: str = "LANE_U_COMPLETED"
LANE_U_STATUS_BLOCKED: str = "LANE_U_BLOCKED"
LANE_U_STATUS_STOPPED: str = "LANE_U_STOPPED"

# Duration profiles — seconds.  All short-run profiles require no extra gate.
_DURATION_PROFILES: dict[str, int] = {
    "1h": 3600,
    "4h": 14400,
    "6h": 21600,
    "12h": 43200,
    "24h": 86400,
}
_LONG_RUN_PROFILES: frozenset[str] = frozenset({"12h", "24h"})
_DEFAULT_PROFILE: str = "6h"

# Window-kind policy
_ENABLED_MAIN_WINDOW_KINDS: frozenset[str] = frozenset({"WINDOW_15M"})
_DISABLED_COLLECTION_WINDOW_KINDS: frozenset[str] = frozenset(
    {"WINDOW_1H", "WINDOW_4H", "WINDOW_12H", "WINDOW_24H"}
)
_SUPPORT_ONLY_WINDOW_KINDS: frozenset[str] = frozenset({"WINDOW_5M_MICRO_EVENT"})
_FORBIDDEN_AS_MAIN_WINDOW: frozenset[str] = frozenset({"WINDOW_5M_MICRO_EVENT"})

# Token limits
_MAX_ACTIVE_TOKENS_HARD_CAP: int = 10
_MAX_NEW_TOKENS_HARD_CAP: int = 50

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
}

# Tables whose row counts are tracked for delta / zero-check reporting
_FORBIDDEN_WRITE_TABLES: tuple[str, ...] = (
    "printer_paper_decisions",
    "printer_paper_positions",
    "printer_paper_trade_events",
    "printer_paper_trade_audits",
    "printer_paper_audit_reports",
    "printer_retrieval_candidates",
    "printer_retrieval_results",
)


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _elapsed(start: float) -> float:
    return time.monotonic() - start


def _count_table(db_path: str | Path, table: str) -> int:
    try:
        conn = sqlite3.connect(str(db_path))
        try:
            row = conn.execute(
                "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?",
                (table,),
            ).fetchone()
            if row is None:
                return 0
            return int(conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0])
        finally:
            conn.close()
    except Exception:
        return 0


def _check_forbidden_tables(db_path: str | Path) -> dict[str, int]:
    return {t: _count_table(db_path, t) for t in _FORBIDDEN_WRITE_TABLES}


def _count_active_locks(db_path: str | Path) -> int:
    try:
        conn = sqlite3.connect(str(db_path))
        try:
            return int(
                conn.execute(
                    "SELECT COUNT(*) FROM printer_scheduler_jobs"
                    " WHERE locked_at IS NOT NULL OR lock_owner IS NOT NULL"
                ).fetchone()[0]
            )
        finally:
            conn.close()
    except Exception:
        return 0


def _check_governed_dependency() -> tuple[bool, str]:
    """Verify the governed E2J → Lane K chain is importable."""
    try:
        from printer_v1.operator_cli.e2j_first_15m_cycle import (  # noqa: F401
            build_e2j_first_15m_cycle_payload,
        )
    except ImportError as exc:
        return False, f"governed E2J path unavailable: {exc}"
    try:
        from printer_v1.operator_cli.lane_k_e2z_pipeline_wiring import (  # noqa: F401
            run_e2z_pipeline,
        )
    except ImportError as exc:
        return False, f"Lane K / E2Z path unavailable: {exc}"
    try:
        from printer_v1.operator_cli.e2i_source_transport import (  # noqa: F401
            build_e2i_dexscreener_adapter,
        )
    except ImportError as exc:
        return False, f"E2I source transport unavailable: {exc}"
    return True, "governed_path_available"


def _blocked_result(
    reasons: list[str],
    db_path_str: str,
    duration_profile: str,
    window_kind: str,
    support_window_kind: str | None,
    max_active_tokens: int,
    max_new_tokens: int,
) -> dict[str, Any]:
    return {
        "command": LANE_U_COMMAND_NAME,
        "lane_u_status": LANE_U_STATUS_BLOCKED,
        "operator_approved": False,
        "db_path": db_path_str,
        "blocked_reasons": reasons,
        "selected_profile": duration_profile,
        "requested_duration_seconds": _DURATION_PROFILES.get(duration_profile, 0),
        "actual_duration_seconds": 0.0,
        "run_started_at": None,
        "run_finished_at": None,
        "window_kind": window_kind,
        "support_window_kind": support_window_kind,
        "max_active_tokens": max_active_tokens,
        "max_new_tokens": max_new_tokens,
        "selected_token_count": 0,
        "discovered_count": None,
        "tracking_queue_selected_count": None,
        "total_cycles_attempted": 0,
        "total_cycles_completed": 0,
        "scheduler_jobs_created": 0,
        "source_requests_created": 0,
        "source_responses_created": 0,
        "source_failures_created": 0,
        "snapshots_created": 0,
        "memory_windows_created": 0,
        "lane_q_valid_windows": 0,
        "lane_q_blocked_windows": 0,
        "lane_k_runs": 0,
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
        "window_kind_enabled": window_kind in _ENABLED_MAIN_WINDOW_KINDS,
        "disabled_collection_window_kinds": sorted(_DISABLED_COLLECTION_WINDOW_KINDS),
        "support_only_window_kinds": sorted(_SUPPORT_ONLY_WINDOW_KINDS),
        "governed_path_available": False,
        # Two-interval timing model reporting
        "cadence_policy_active": True,
        "target_snapshot_interval_seconds": None,
        "max_clean_snapshot_gap_seconds": None,
        "coverage_policy_warning": None,
        "snapshot_interval_seconds": 0.0,
        "window_close_interval_seconds": 0.0,
    }


def run_memory_factory_cycle(
    token_list_path: str | Path | None,
    db_path: str | Path | None,
    backup_proof_path: str | Path | None,
    *,
    operator_approved: bool = False,
    duration_profile: str = _DEFAULT_PROFILE,
    window_kind: str = "WINDOW_15M",
    support_window_kind: str | None = None,
    max_active_tokens: int = _MAX_ACTIVE_TOKENS_HARD_CAP,
    max_new_tokens: int = _MAX_NEW_TOKENS_HARD_CAP,
    allow_long_bounded_run: bool = False,
    snapshot_interval_seconds: float = 0.0,
    window_close_interval_seconds: float = 0.0,
    _adapter: Any = None,
    _cycle_budget: int | None = None,
) -> dict[str, Any]:
    """Run a bounded, governed Memory Factory cycle.

    Parameters
    ----------
    token_list_path:
        Path to the operator-approved token list JSON (exactly 1 TRACK_FAST token).
    db_path:
        Path to the operator-approved SQLite DB.
    backup_proof_path:
        Path to a DB backup file (proof backup exists before run).
    operator_approved:
        Must be True; gate refuses without explicit approval.
    duration_profile:
        One of "1h", "4h", "6h", "12h", "24h".  "12h" and "24h" also require
        allow_long_bounded_run=True.
    window_kind:
        Must be "WINDOW_15M" (only enabled main window in this lane).
    support_window_kind:
        Recognized: "WINDOW_5M_MICRO_EVENT" (support-only, not activated as main).
        Refused if specified as main window kind.
    max_active_tokens:
        Hard cap on simultaneously tracked tokens (≤ _MAX_ACTIVE_TOKENS_HARD_CAP).
    max_new_tokens:
        Discovery intake cap per run (≤ _MAX_NEW_TOKENS_HARD_CAP).
    allow_long_bounded_run:
        Must be True to use "12h" or "24h" duration profiles.
    snapshot_interval_seconds:
        How often snapshot-only E2J calls are issued inside a window.
        Use 90.0 for WINDOW_15M/TRACK_FAST, 180.0 for TRACK_NORMAL.
        0.0 = no sleep between snapshots (useful for tests).
    window_close_interval_seconds:
        How long to collect snapshots before closing/evaluating the window.
        Use 900.0 for real 15m windows.
        0.0 = close immediately after the first snapshot attempt (test mode).
    _adapter:
        Fixture adapter injected by tests; None in production.
    _cycle_budget:
        Test-only: maximum number of WINDOW CLOSE cycles.  Does not count
        snapshot-only calls.  None (default) means duration controls.
    """
    db_path_str = str(db_path) if db_path is not None else ""
    blocked_reasons: list[str] = []

    if not operator_approved:
        blocked_reasons.append(
            "operator_approved must be True to run the Memory Factory cycle"
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

    # Duration profile validation
    if duration_profile not in _DURATION_PROFILES:
        blocked_reasons.append(
            f"unsupported duration_profile {duration_profile!r}; "
            f"allowed: {sorted(_DURATION_PROFILES)}"
        )
    elif duration_profile in _LONG_RUN_PROFILES and not allow_long_bounded_run:
        blocked_reasons.append(
            f"duration_profile {duration_profile!r} requires allow_long_bounded_run=True "
            "(12h and 24h profiles need explicit config-gate approval)"
        )

    # Window-kind validation — WINDOW_15M is the only enabled main window
    if window_kind in _FORBIDDEN_AS_MAIN_WINDOW:
        blocked_reasons.append(
            f"window_kind {window_kind!r} is a support-only window and may not be "
            "used as the main Memory Factory window; 5m is support evidence only"
        )
    elif window_kind in _DISABLED_COLLECTION_WINDOW_KINDS:
        blocked_reasons.append(
            f"window_kind {window_kind!r} real collection is disabled in this lane; "
            "WINDOW_1H/4H/12H/24H require a separate future approved lane"
        )
    elif window_kind not in _ENABLED_MAIN_WINDOW_KINDS:
        blocked_reasons.append(
            f"window_kind {window_kind!r} is not recognized; "
            f"enabled: {sorted(_ENABLED_MAIN_WINDOW_KINDS)}"
        )

    # Support window kind — accepted only as support (not main)
    if support_window_kind is not None:
        if support_window_kind not in _SUPPORT_ONLY_WINDOW_KINDS:
            blocked_reasons.append(
                f"support_window_kind {support_window_kind!r} is not a recognized "
                "support-only window kind; allowed: WINDOW_5M_MICRO_EVENT"
            )

    # Token limit validation
    if not isinstance(max_active_tokens, int) or max_active_tokens < 1:
        blocked_reasons.append(
            f"max_active_tokens must be a positive integer; got {max_active_tokens!r}"
        )
    elif max_active_tokens > _MAX_ACTIVE_TOKENS_HARD_CAP:
        blocked_reasons.append(
            f"max_active_tokens {max_active_tokens} exceeds hard cap "
            f"{_MAX_ACTIVE_TOKENS_HARD_CAP}"
        )

    if not isinstance(max_new_tokens, int) or max_new_tokens < 1:
        blocked_reasons.append(
            f"max_new_tokens must be a positive integer; got {max_new_tokens!r}"
        )
    elif max_new_tokens > _MAX_NEW_TOKENS_HARD_CAP:
        blocked_reasons.append(
            f"max_new_tokens {max_new_tokens} exceeds hard cap "
            f"{_MAX_NEW_TOKENS_HARD_CAP}"
        )

    if blocked_reasons:
        return _blocked_result(
            blocked_reasons, db_path_str, duration_profile, window_kind,
            support_window_kind, max_active_tokens, max_new_tokens,
        )

    # Governed dependency check — E2J + Lane K + E2I must be importable
    governed_ok, governed_reason = _check_governed_dependency()
    if not governed_ok:
        return _blocked_result(
            [governed_reason], db_path_str, duration_profile, window_kind,
            support_window_kind, max_active_tokens, max_new_tokens,
        )

    # Pre-cycle lock check
    active_locks = _count_active_locks(db_path)
    if active_locks:
        return _blocked_result(
            [f"pre-run check: {active_locks} active scheduler lock(s) found"],
            db_path_str, duration_profile, window_kind, support_window_kind,
            max_active_tokens, max_new_tokens,
        )

    # Load governed modules (safe after dependency check)
    from printer_v1.operator_cli.e2j_first_15m_cycle import (
        E2J_STATUS_EXECUTED,
        build_e2j_first_15m_cycle_payload,
    )
    from printer_v1.operator_cli.lane_k_e2z_pipeline_wiring import (
        LANE_K_STATUS_COMPLETED,
        run_e2z_pipeline,
    )

    # Cadence policy lookup — determines whether snapshot_interval_seconds is
    # adequate for real clean-memory production under the active policy.
    _cadence_policy = _get_cadence_policy(window_kind, "TRACK_FAST")
    _target_interval = (
        _cadence_policy.target_snapshot_interval_seconds
        if _cadence_policy is not None
        else None
    )
    _max_gap_limit = (
        _cadence_policy.max_clean_snapshot_gap_seconds
        if _cadence_policy is not None
        else None
    )
    coverage_policy_warning: str | None = None
    if _target_interval is not None and snapshot_interval_seconds < _target_interval:
        coverage_policy_warning = (
            f"snapshot_interval_seconds={snapshot_interval_seconds:.1f}s is below the "
            f"target_snapshot_interval_seconds={_target_interval}s for "
            f"{window_kind}/TRACK_FAST.  Back-to-back snapshots will be too close "
            f"together for Lane Q coverage policy to pass.  CLEAN_MEMORY will be "
            f"blocked by the cadence/gap policy unless real time elapses between "
            f"snapshots.  Use --snapshot-interval-seconds {_target_interval} or "
            f"greater for real clean-memory production."
        )

    # ---------- RUN ----------

    max_duration_seconds = _DURATION_PROFILES[duration_profile]
    run_started_at = _utc_now_iso()
    loop_start = time.monotonic()

    # Counters
    total_cycles_attempted = 0
    total_cycles_completed = 0
    scheduler_jobs_created = 0
    source_requests_created = 0
    source_responses_created = 0
    source_failures_created = 0
    snapshots_created = 0
    memory_windows_created = 0
    lane_q_valid_windows = 0
    lane_q_blocked_windows = 0
    lane_k_runs = 0
    clean_memory_rows_created = 0
    e2z_already_exists_count = 0
    dirty_or_blocked_memory_count = 0
    cycles_run: list[dict[str, Any]] = []

    # Two-level timing state:
    # window_start_snapshot_id — ID of the first snapshot captured in the current window
    # window_open_mono — monotonic time when the current window opened
    window_start_snapshot_id: int | None = None
    window_open_mono: float | None = None
    total_window_closes = 0  # drives _cycle_budget count
    cycle_num = 0
    prev_close_snapshot_id: int | None = None
    stopped_safely_reason: str | None = None
    final_status = LANE_U_STATUS_COMPLETED

    while True:
        elapsed_now = _elapsed(loop_start)
        if elapsed_now >= max_duration_seconds:
            stopped_safely_reason = (
                f"duration limit reached: {elapsed_now:.1f}s "
                f">= {max_duration_seconds}s ({duration_profile})"
            )
            break

        if _cycle_budget is not None and total_window_closes >= _cycle_budget:
            stopped_safely_reason = (
                f"cycle budget exhausted: {_cycle_budget} window close(s) completed"
            )
            break

        # --- Phase 1: Snapshot-only E2J call ---
        # Snapshot-only calls do not count toward total_cycles_attempted;
        # only window-close calls count (mirrors _cycle_budget semantics).
        snap_result = build_e2j_first_15m_cycle_payload(
            token_list_path,
            db_path,
            backup_proof_path,
            operator_approved=True,
            _adapter=_adapter,
            _snapshot_start_id=None,
            _close_window=False,
        )

        # The window "opens" from the first snapshot attempt, even if no snapshot
        # was produced (adapter=None test mode).
        if window_open_mono is None:
            window_open_mono = time.monotonic()

        # Record the first real snapshot ID as the window's start boundary.
        snap_id = snap_result.get("snapshot_id")
        if snap_id is not None and window_start_snapshot_id is None:
            window_start_snapshot_id = int(snap_id)

        if snap_result.get("snapshot_persistence_status") == "E2M_SNAPSHOT_PERSISTED":
            snapshots_created += 1

        if snap_result.get("e2j_status") != E2J_STATUS_EXECUTED:
            stopped_safely_reason = (
                "snapshot-only E2J call stopped: "
                f"{snap_result.get('cycle_status', 'UNKNOWN')}"
                + (
                    f" — {snap_result.get('exec_error', '')}"
                    if snap_result.get("exec_error")
                    else ""
                )
            )
            final_status = LANE_U_STATUS_STOPPED
            break

        # --- Phase 2: Window close check ---
        window_elapsed = _elapsed(window_open_mono)  # type: ignore[arg-type]
        if window_elapsed >= window_close_interval_seconds:
            cycle_num += 1
            total_cycles_attempted += 1  # window-close = 1 cycle attempt

            close_result = build_e2j_first_15m_cycle_payload(
                token_list_path,
                db_path,
                backup_proof_path,
                operator_approved=True,
                _adapter=_adapter,
                _snapshot_start_id=window_start_snapshot_id,
                _close_window=True,
            )

            # Thread the close snapshot forward for E2O start-ID threading.
            win_snap = (
                close_result.get("snapshot_id_for_window")
                or close_result.get("snapshot_id")
            )
            if win_snap is not None:
                prev_close_snapshot_id = int(win_snap)

            # Accumulate delta counters from the window-close cycle.
            deltas = close_result.get("deltas", {})
            scheduler_jobs_created += max(0, int(deltas.get("printer_scheduler_jobs", 0) or 0))
            source_requests_created += max(0, int(deltas.get("printer_source_requests", 0) or 0))
            source_responses_created += max(0, int(deltas.get("printer_source_responses", 0) or 0))
            source_failures_created += max(0, int(deltas.get("printer_source_failures", 0) or 0))
            memory_windows_created += max(0, int(deltas.get("printer_memory_windows", 0) or 0))

            if close_result.get("snapshot_persistence_status") == "E2M_SNAPSHOT_PERSISTED":
                snapshots_created += 1

            if close_result.get("lane_q_integrity_eligible"):
                lane_q_valid_windows += 1
            elif close_result.get("memory_window_close_status") not in (
                "NOT_ATTEMPTED", None
            ):
                lane_q_blocked_windows += 1

            cycle_summary: dict[str, Any] = {
                "cycle_num": cycle_num,
                "e2j_status": close_result.get("e2j_status"),
                "snapshot_id": close_result.get("snapshot_id"),
                "snapshot_id_for_window": close_result.get("snapshot_id_for_window"),
                "snapshot_start_id": window_start_snapshot_id,
                "memory_window_id": close_result.get("memory_window_id"),
                "window_start_at": close_result.get("window_start_at"),
                "window_end_at": close_result.get("window_end_at"),
                "elapsed_seconds": close_result.get("elapsed_seconds"),
                "lane_q_integrity_eligible": close_result.get("lane_q_integrity_eligible"),
                "memory_quality_label": close_result.get("memory_quality_label"),
                "exec_error": close_result.get("exec_error"),
            }

            if close_result.get("e2j_status") != E2J_STATUS_EXECUTED:
                stopped_safely_reason = (
                    f"window-close E2J cycle {cycle_num} stopped: "
                    f"{close_result.get('cycle_status', 'UNKNOWN')}"
                    + (
                        f" — {close_result.get('exec_error', '')}"
                        if close_result.get("exec_error")
                        else ""
                    )
                )
                final_status = LANE_U_STATUS_STOPPED
                cycles_run.append(cycle_summary)
                break

            total_cycles_completed += 1
            total_window_closes += 1

            # Lane K with production_mode=True — real coverage required.
            lane_k_result = run_e2z_pipeline(
                db_path, operator_approved=True, production_mode=True
            )
            lane_k_runs += 1
            clean_memory_rows_created += int(
                lane_k_result.get("clean_memory_rows_created", 0) or 0
            )
            e2z_already_exists_count += int(
                lane_k_result.get("e2z_already_exists_count", 0) or 0
            )
            dirty_or_blocked_memory_count += int(
                lane_k_result.get("e2z_blocked_count", 0) or 0
            )

            cycle_summary["lane_k_status"] = lane_k_result.get("lane_k_status")
            cycle_summary["lane_k_clean_created"] = lane_k_result.get(
                "clean_memory_rows_created", 0
            )
            cycles_run.append(cycle_summary)

            # Reset window state for the next window.
            window_start_snapshot_id = None
            window_open_mono = None

        # Sleep between snapshot captures.
        if snapshot_interval_seconds > 0:
            remaining = max_duration_seconds - _elapsed(loop_start)
            actual_sleep = min(snapshot_interval_seconds, max(0, remaining))
            if actual_sleep > 0:
                time.sleep(actual_sleep)

    run_finished_at = _utc_now_iso()
    actual_duration_seconds = _elapsed(loop_start)

    if final_status == LANE_U_STATUS_COMPLETED and stopped_safely_reason is None:
        stopped_safely_reason = (
            f"duration limit reached after {total_cycles_completed} window close(s)"
        )

    # Verify forbidden tables remain zero
    forbidden_counts = _check_forbidden_tables(db_path)

    return {
        "command": LANE_U_COMMAND_NAME,
        "lane_u_status": final_status,
        "operator_approved": True,
        "db_path": db_path_str,
        "selected_profile": duration_profile,
        "requested_duration_seconds": max_duration_seconds,
        "actual_duration_seconds": round(actual_duration_seconds, 3),
        "run_started_at": run_started_at,
        "run_finished_at": run_finished_at,
        "window_kind": window_kind,
        "support_window_kind": support_window_kind,
        "window_kind_enabled": window_kind in _ENABLED_MAIN_WINDOW_KINDS,
        "disabled_collection_window_kinds": sorted(_DISABLED_COLLECTION_WINDOW_KINDS),
        "support_only_window_kinds": sorted(_SUPPORT_ONLY_WINDOW_KINDS),
        "max_active_tokens": max_active_tokens,
        "max_new_tokens": max_new_tokens,
        "selected_token_count": 1,
        "discovered_count": None,
        "tracking_queue_selected_count": None,
        "total_cycles_attempted": total_cycles_attempted,
        "total_cycles_completed": total_cycles_completed,
        "scheduler_jobs_created": scheduler_jobs_created,
        "source_requests_created": source_requests_created,
        "source_responses_created": source_responses_created,
        "source_failures_created": source_failures_created,
        "snapshots_created": snapshots_created,
        "memory_windows_created": memory_windows_created,
        "lane_q_valid_windows": lane_q_valid_windows,
        "lane_q_blocked_windows": lane_q_blocked_windows,
        "lane_k_runs": lane_k_runs,
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
        "governed_path_available": True,
        "prev_close_snapshot_id": prev_close_snapshot_id,
        "cycles": cycles_run,
        "forbidden_table_counts": forbidden_counts,
        "hard_locks": dict(_HARD_LOCKS),
        "buy_enabled": False,
        "sell_enabled": False,
        "hold_enabled": False,
        # Two-interval timing model reporting
        "cadence_policy_active": True,
        "target_snapshot_interval_seconds": _target_interval,
        "max_clean_snapshot_gap_seconds": _max_gap_limit,
        "coverage_policy_warning": coverage_policy_warning,
        "snapshot_interval_seconds": snapshot_interval_seconds,
        "window_close_interval_seconds": window_close_interval_seconds,
    }
