"""Lane X8 -- 5m Support Evidence Integration.

Wires WINDOW_5M_MICRO_EVENT as support-only evidence inside bounded WINDOW_15M runs.

Design decisions:
- 5m support can be captured (written to printer_memory_windows) linked to a
  parent WINDOW_15M window by parent_window_id stored in supporting_context_json.
- 5m support enriches the 15m memory context; it does not replace it.
- 5m evidence is always SUPPORT_EVIDENCE or AUDIT_ONLY; never CLEAN_MEMORY.
- Cross-token or cross-pair linkage is rejected at capture and at enrich.
- Missing parent 15m window causes capture to return BLOCKED.
- Dirty/stale/failed/mismatched 5m evidence is marked AUDIT_ONLY / DIRTY_MEMORY;
  do_not_train=1.  Dirty evidence stays audit-only — it cannot upgrade to clean.
- No retrieval activation from 5m evidence.
- No paper decisions, BUY/SELL/HOLD, positions, or PnL from 5m evidence.
- X5 five-token WINDOW_15M behavior is not modified.
- X6 discovery/selection behavior is not modified.
- X3 cooldown/archive behavior is not modified.

Hard rules (26 locks):
- Operator approval required.
- No BUY/SELL/HOLD.  No paper decisions.  No positions.  No PnL.
- No retrieval activation from 5m.  No 5m clean memory.
- No wallet/private keys.  No live trading.  No paid APIs.
- No discovery automation.  No long-window expansion.
- No 1h/4h/12h/24h collection.
- No scoring/ranking/confidence/weighted logic.  No embeddings/vectors.
- No token/pair mixing.  Cross-token/cross-pair linkage rejected.
- No X5/X6/X3 weakening.
- Zero clean memories from 5m is always a valid outcome.
"""

from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


# ---------------------------------------------------------------------------
# Module identity
# ---------------------------------------------------------------------------

LANE_X8_COMMAND_NAME: str = "printer-run-lane-x8-5m-support-integration"
LANE_X8_STATUS_COMPLETED: str = "LANE_X8_COMPLETED"
LANE_X8_STATUS_BLOCKED: str = "LANE_X8_BLOCKED"

_WINDOW_5M: str = "WINDOW_5M_MICRO_EVENT"
_WINDOW_15M: str = "WINDOW_15M"
_CREATED_BY: str = "lane_x8"

_QUALITY_SUPPORT: str = "SUPPORT_EVIDENCE"
_QUALITY_AUDIT: str = "AUDIT_ONLY"
_QUALITY_DIRTY: str = "DIRTY_MEMORY"
_QUALITY_DO_NOT_TRAIN: str = "DO_NOT_TRAIN"

_STATUS_PARTIAL: str = "PARTIAL_MEMORY"
_STATUS_DIRTY: str = "DIRTY_MEMORY"
_STATUS_AUDIT: str = "AUDIT_ONLY"

_DIRTY_DATA_LABELS: frozenset[str] = frozenset({
    "DIRTY_DATA",
    "STALE_DATA",
    "MISSING_CRITICAL_DATA",
    "CONFLICTING_DATA",
    "DO_NOT_TRAIN",
})
_DIRTY_SOURCE_STATUSES: frozenset[str] = frozenset({
    "FAILED",
    "STALE",
    "CONFLICTING",
})
_DIRTY_MEMORY_LABELS: frozenset[str] = frozenset({"DIRTY_MEMORY", "DO_NOT_TRAIN"})

# Tables that must never be written by Lane X8
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
    "no_5m_clean_memory": True,    # X8: 5m can never produce clean memory
    "no_x5_weakening": True,       # X8: WINDOW_15M X5 behavior is not modified
}


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


def _count_table(conn: sqlite3.Connection, table: str) -> int:
    try:
        return int(conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0])
    except sqlite3.OperationalError:
        return 0


def _classify_evidence_quality(
    *,
    data_quality_label: str,
    source_status: str,
    is_stale: bool,
    is_incomplete: bool,
    is_failed: bool,
    is_mismatched: bool,
) -> tuple[str, str, bool]:
    """Return (memory_quality_label, memory_status, do_not_train).

    Never returns CLEAN_MEMORY -- that is the key X8 invariant.
    """
    is_dirty = (
        data_quality_label in _DIRTY_DATA_LABELS
        or source_status in _DIRTY_SOURCE_STATUSES
        or is_stale
        or is_failed
        or is_mismatched
    )
    if is_dirty:
        return _QUALITY_DIRTY, _STATUS_DIRTY, True
    if is_incomplete or data_quality_label == "ACCEPTABLE_PARTIAL_DATA":
        return _QUALITY_AUDIT, _STATUS_AUDIT, True
    return _QUALITY_SUPPORT, _STATUS_PARTIAL, False


# ---------------------------------------------------------------------------
# Core validators
# ---------------------------------------------------------------------------

def validate_5m_linkage_for_parent(
    conn: sqlite3.Connection,
    parent_window_id: int,
    token_id: int,
    pair_id: int,
) -> dict[str, Any]:
    """Validate that parent_window_id is a WINDOW_15M for (token_id, pair_id).

    Returns:
      valid: bool
      blocked_reason: str | None
      parent_window_kind: str | None
      parent_token_id: int | None
      parent_pair_id: int | None
    """
    try:
        row = conn.execute(
            "SELECT id, window_kind, token_id, pair_id"
            " FROM printer_memory_windows WHERE id = ?",
            (parent_window_id,),
        ).fetchone()
    except sqlite3.OperationalError:
        return {
            "valid": False,
            "blocked_reason": "printer_memory_windows table not found",
            "parent_window_kind": None,
            "parent_token_id": None,
            "parent_pair_id": None,
        }

    if row is None:
        return {
            "valid": False,
            "blocked_reason": (
                f"parent_window_id={parent_window_id} not found"
                " in printer_memory_windows"
            ),
            "parent_window_kind": None,
            "parent_token_id": None,
            "parent_pair_id": None,
        }

    parent_kind = str(row["window_kind"])
    parent_token_id = int(row["token_id"])
    parent_pair_id = int(row["pair_id"])

    if parent_kind != _WINDOW_15M:
        return {
            "valid": False,
            "blocked_reason": (
                f"parent_window_id={parent_window_id} has"
                f" window_kind={parent_kind!r}; must be {_WINDOW_15M!r}"
            ),
            "parent_window_kind": parent_kind,
            "parent_token_id": parent_token_id,
            "parent_pair_id": parent_pair_id,
        }

    if parent_token_id != token_id:
        return {
            "valid": False,
            "blocked_reason": (
                "cross-token linkage rejected:"
                f" parent token_id={parent_token_id}"
                f" != provided token_id={token_id}"
            ),
            "parent_window_kind": parent_kind,
            "parent_token_id": parent_token_id,
            "parent_pair_id": parent_pair_id,
        }

    if parent_pair_id != pair_id:
        return {
            "valid": False,
            "blocked_reason": (
                "cross-pair linkage rejected:"
                f" parent pair_id={parent_pair_id}"
                f" != provided pair_id={pair_id}"
            ),
            "parent_window_kind": parent_kind,
            "parent_token_id": parent_token_id,
            "parent_pair_id": parent_pair_id,
        }

    return {
        "valid": True,
        "blocked_reason": None,
        "parent_window_kind": parent_kind,
        "parent_token_id": parent_token_id,
        "parent_pair_id": parent_pair_id,
    }


# ---------------------------------------------------------------------------
# Core operations
# ---------------------------------------------------------------------------

def capture_5m_support_evidence(
    db_path: str | Path,
    parent_window_id: int,
    token_id: int,
    pair_id: int,
    *,
    operator_approved: bool = False,
    data_quality_label: str = "CLEAN_DATA",
    source_status: str = "COMPLETE",
    is_stale: bool = False,
    is_incomplete: bool = False,
    is_failed: bool = False,
    is_mismatched: bool = False,
    opened_at: str | None = None,
    closed_at: str | None = None,
    snapshot_start_id: int | None = None,
    snapshot_end_id: int | None = None,
    run_id: str | None = None,
    tracking_lane: str | None = None,
) -> dict[str, Any]:
    """Write a WINDOW_5M_MICRO_EVENT row linked to a parent WINDOW_15M window.

    Hard rules enforced here:
    - operator_approved must be True.
    - parent_window_id must reference a WINDOW_15M with matching token_id/pair_id.
    - memory_quality_label is never CLEAN_MEMORY.
    - Forbidden write tables (paper, retrieval, memories) are never touched.
    - Cross-token and cross-pair linkage is rejected.
    - Missing parent returns BLOCKED.
    """
    blocked_reasons: list[str] = []

    if not operator_approved:
        blocked_reasons.append(
            "operator_approved must be True for Lane X8 capture"
        )
    if not db_path:
        blocked_reasons.append("db_path is required")

    if blocked_reasons:
        return {
            "lane_x8_capture_status": LANE_X8_STATUS_BLOCKED,
            "captured": False,
            "blocked_reasons": blocked_reasons,
            "window_5m_id": None,
            "parent_window_id": parent_window_id,
            "token_id": token_id,
            "pair_id": pair_id,
            "memory_quality_label": None,
            "do_not_train": True,
            "5m_clean_memory_blocked": True,
            "retrieval_from_5m_blocked": True,
            "hard_locks": dict(_HARD_LOCKS),
        }

    now = _utc_now()
    opened_at_val = opened_at or now
    closed_at_val = closed_at or now

    conn = _connect(db_path)
    try:
        linkage = validate_5m_linkage_for_parent(conn, parent_window_id, token_id, pair_id)
        if not linkage["valid"]:
            return {
                "lane_x8_capture_status": LANE_X8_STATUS_BLOCKED,
                "captured": False,
                "blocked_reasons": [linkage["blocked_reason"]],
                "window_5m_id": None,
                "parent_window_id": parent_window_id,
                "token_id": token_id,
                "pair_id": pair_id,
                "memory_quality_label": None,
                "do_not_train": True,
                "5m_clean_memory_blocked": True,
                "retrieval_from_5m_blocked": True,
                "hard_locks": dict(_HARD_LOCKS),
                "linkage_validation": linkage,
            }

        resolved_start_at = opened_at_val
        resolved_end_at = closed_at_val
        if snapshot_start_id is not None or snapshot_end_id is not None:
            if snapshot_start_id is None or snapshot_end_id is None:
                return {
                    "lane_x8_capture_status": LANE_X8_STATUS_BLOCKED,
                    "captured": False,
                    "blocked_reasons": ["both 5m snapshot boundaries are required"],
                    "window_5m_id": None,
                    "parent_window_id": parent_window_id,
                    "token_id": token_id,
                    "pair_id": pair_id,
                    "do_not_train": True,
                    "hard_locks": dict(_HARD_LOCKS),
                }
            boundary_rows = conn.execute(
                """
                SELECT id, token_id, pair_id, captured_at
                FROM printer_token_snapshots
                WHERE id IN (?, ?)
                ORDER BY id
                """,
                (snapshot_start_id, snapshot_end_id),
            ).fetchall()
            by_id = {int(row["id"]): row for row in boundary_rows}
            start_row = by_id.get(int(snapshot_start_id))
            end_row = by_id.get(int(snapshot_end_id))
            if start_row is None or end_row is None:
                return {
                    "lane_x8_capture_status": LANE_X8_STATUS_BLOCKED,
                    "captured": False,
                    "blocked_reasons": ["5m snapshot boundary not found"],
                    "window_5m_id": None,
                    "parent_window_id": parent_window_id,
                    "token_id": token_id,
                    "pair_id": pair_id,
                    "do_not_train": True,
                    "hard_locks": dict(_HARD_LOCKS),
                }
            for row in (start_row, end_row):
                if int(row["token_id"]) != int(token_id) or int(row["pair_id"]) != int(pair_id):
                    return {
                        "lane_x8_capture_status": LANE_X8_STATUS_BLOCKED,
                        "captured": False,
                        "blocked_reasons": ["5m snapshot boundary target mismatch"],
                        "window_5m_id": None,
                        "parent_window_id": parent_window_id,
                        "token_id": token_id,
                        "pair_id": pair_id,
                        "do_not_train": True,
                        "hard_locks": dict(_HARD_LOCKS),
                    }
            resolved_start_at = str(start_row["captured_at"])
            resolved_end_at = str(end_row["captured_at"])
            try:
                if datetime.fromisoformat(resolved_end_at) < datetime.fromisoformat(resolved_start_at):
                    raise ValueError("reversed")
            except (TypeError, ValueError):
                return {
                    "lane_x8_capture_status": LANE_X8_STATUS_BLOCKED,
                    "captured": False,
                    "blocked_reasons": ["invalid or reversed 5m snapshot timestamps"],
                    "window_5m_id": None,
                    "parent_window_id": parent_window_id,
                    "token_id": token_id,
                    "pair_id": pair_id,
                    "do_not_train": True,
                    "hard_locks": dict(_HARD_LOCKS),
                }

            existing = conn.execute(
                """
                SELECT id FROM printer_memory_windows
                WHERE token_id=? AND pair_id=? AND window_kind=?
                  AND snapshot_start_id=? AND snapshot_end_id=?
                """,
                (token_id, pair_id, _WINDOW_5M, snapshot_start_id, snapshot_end_id),
            ).fetchone()
            if existing is not None:
                return {
                    "lane_x8_capture_status": LANE_X8_STATUS_COMPLETED,
                    "captured": False,
                    "duplicate": True,
                    "existing_window_id": int(existing["id"]),
                    "window_5m_id": int(existing["id"]),
                    "parent_window_id": parent_window_id,
                    "token_id": token_id,
                    "pair_id": pair_id,
                    "snapshot_start_id": snapshot_start_id,
                    "snapshot_end_id": snapshot_end_id,
                    "do_not_train": True,
                    "hard_locks": dict(_HARD_LOCKS),
                }

        quality_label, memory_status, do_not_train = _classify_evidence_quality(
            data_quality_label=data_quality_label,
            source_status=source_status,
            is_stale=is_stale,
            is_incomplete=is_incomplete,
            is_failed=is_failed,
            is_mismatched=is_mismatched,
        )

        ctx: dict[str, Any] = {
            "created_by": _CREATED_BY,
            "parent_window_id": parent_window_id,
            "parent_window_kind": _WINDOW_15M,
            "run_id": run_id,
            "tracking_lane": tracking_lane,
            "same_opening_stream": snapshot_start_id is not None,
        }

        cur = conn.execute(
            """
            INSERT INTO printer_memory_windows (
                token_id, pair_id, window_kind, opened_at, closed_at,
                memory_status, data_quality_label, do_not_train,
                window_status, memory_quality_label,
                supporting_context_json, created_by_phase, created_at, updated_at
                , window_start_at, window_end_at, snapshot_start_id, snapshot_end_id
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                token_id, pair_id, _WINDOW_5M,
                resolved_start_at, resolved_end_at,
                memory_status, data_quality_label, 1 if do_not_train else 0,
                "WINDOW_CLOSED", quality_label,
                json.dumps(ctx, sort_keys=True), _CREATED_BY, now, now,
                resolved_start_at, resolved_end_at, snapshot_start_id, snapshot_end_id,
            ),
        )
        window_5m_id = int(cur.lastrowid)
        conn.commit()
    finally:
        conn.close()

    return {
        "lane_x8_capture_status": LANE_X8_STATUS_COMPLETED,
        "captured": True,
        "blocked_reasons": [],
        "window_5m_id": window_5m_id,
        "parent_window_id": parent_window_id,
        "token_id": token_id,
        "pair_id": pair_id,
        "memory_quality_label": quality_label,
        "memory_status": memory_status,
        "do_not_train": do_not_train,
        "data_quality_label": data_quality_label,
        "source_status": source_status,
        "opened_at": resolved_start_at,
        "closed_at": resolved_end_at,
        "snapshot_start_id": snapshot_start_id,
        "snapshot_end_id": snapshot_end_id,
        "run_id": run_id,
        "tracking_lane": tracking_lane,
        "5m_main_window_blocked": True,
        "5m_clean_memory_blocked": True,
        "retrieval_from_5m_blocked": True,
        "paper_decision_from_5m_blocked": True,
        "buy_from_5m_blocked": True,
        "position_from_5m_blocked": True,
        "hard_locks": dict(_HARD_LOCKS),
    }


def enrich_15m_context_with_5m_support(
    db_path: str | Path,
    parent_window_id: int,
    token_id: int,
    pair_id: int,
) -> dict[str, Any]:
    """Read all WINDOW_5M_MICRO_EVENT rows linked to a parent WINDOW_15M window.

    Returns the enriched context. Read-only. No DB mutations.
    Dirty/stale/do_not_train rows are included in the summary as audit-only entries.
    Cross-pair rows are classified 'cross_pair_rejected'.
    """
    conn = _connect(db_path)
    try:
        parent_row = None
        try:
            parent_row = conn.execute(
                """
                SELECT id, window_kind, token_id, pair_id, memory_status,
                       memory_quality_label, window_status, opened_at, closed_at
                FROM printer_memory_windows WHERE id = ?
                """,
                (parent_window_id,),
            ).fetchone()
        except sqlite3.OperationalError:
            pass

        if parent_row is None:
            return {
                "enrichment_status": "UNENRICHED",
                "parent_window_id": parent_window_id,
                "parent_found": False,
                "token_id": token_id,
                "pair_id": pair_id,
                "support_5m_count": 0,
                "valid_support_count": 0,
                "dirty_support_count": 0,
                "support_entries": [],
                "15m_clean_memory_unaffected": True,
                "5m_main_window_blocked": True,
                "5m_clean_memory_blocked": True,
                "retrieval_from_5m_blocked": True,
                "paper_decision_from_5m_blocked": True,
                "hard_locks": dict(_HARD_LOCKS),
            }

        five_m_rows: list[sqlite3.Row] = []
        try:
            five_m_rows = conn.execute(
                """
                SELECT id, token_id, pair_id, window_kind, window_status,
                       memory_status, data_quality_label, memory_quality_label,
                       do_not_train, supporting_context_json, opened_at, closed_at
                FROM printer_memory_windows
                WHERE window_kind = ?
                  AND json_extract(supporting_context_json, '$.parent_window_id') = ?
                """,
                (_WINDOW_5M, parent_window_id),
            ).fetchall()
        except sqlite3.OperationalError:
            pass

        support_entries: list[dict[str, Any]] = []
        valid_count = 0
        dirty_count = 0

        for row in five_m_rows:
            row_token_id = int(row["token_id"])
            row_pair_id = int(row["pair_id"])
            cross_pair = (row_token_id != token_id or row_pair_id != pair_id)

            try:
                ctx = json.loads(row["supporting_context_json"] or "{}")
            except (json.JSONDecodeError, TypeError):
                ctx = {}

            is_dirty = (
                bool(row["do_not_train"])
                or (row["data_quality_label"] or "") in _DIRTY_DATA_LABELS
                or (row["memory_quality_label"] or "") in _DIRTY_MEMORY_LABELS
            )

            if cross_pair:
                classification = "cross_pair_rejected"
            elif is_dirty:
                classification = "dirty"
            else:
                classification = "valid_support"

            entry: dict[str, Any] = {
                "id": int(row["id"]),
                "token_id": row_token_id,
                "pair_id": row_pair_id,
                "window_kind": str(row["window_kind"]),
                "memory_quality_label": row["memory_quality_label"],
                "data_quality_label": row["data_quality_label"],
                "do_not_train": bool(row["do_not_train"]),
                "parent_window_id": ctx.get("parent_window_id"),
                "parent_window_kind": ctx.get("parent_window_kind"),
                "opened_at": row["opened_at"],
                "closed_at": row["closed_at"],
                "classification": classification,
                "cross_pair": cross_pair,
                "is_dirty": is_dirty,
                "5m_main_window_blocked": True,
                "5m_clean_memory_blocked": True,
                "retrieval_blocked": True,
            }
            support_entries.append(entry)

            if not is_dirty and not cross_pair:
                valid_count += 1
            elif is_dirty and not cross_pair:
                dirty_count += 1

        enrichment_status = (
            "ENRICHED" if valid_count > 0
            else ("PARTIAL" if dirty_count > 0 else "UNENRICHED")
        )

    finally:
        conn.close()

    parent_data: dict[str, Any] = {
        "id": int(parent_row["id"]),
        "window_kind": str(parent_row["window_kind"]),
        "token_id": int(parent_row["token_id"]),
        "pair_id": int(parent_row["pair_id"]),
        "memory_status": parent_row["memory_status"],
        "memory_quality_label": parent_row["memory_quality_label"],
        "window_status": parent_row["window_status"],
        "opened_at": parent_row["opened_at"],
        "closed_at": parent_row["closed_at"],
    }

    return {
        "enrichment_status": enrichment_status,
        "parent_window_id": parent_window_id,
        "parent_found": True,
        "parent_window": parent_data,
        "token_id": token_id,
        "pair_id": pair_id,
        "support_5m_count": len(five_m_rows),
        "valid_support_count": valid_count,
        "dirty_support_count": dirty_count,
        "support_entries": support_entries,
        "15m_clean_memory_unaffected": True,
        "5m_main_window_blocked": True,
        "5m_clean_memory_blocked": True,
        "retrieval_from_5m_blocked": True,
        "paper_decision_from_5m_blocked": True,
        "hard_locks": dict(_HARD_LOCKS),
    }


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------

def run_lane_x8_5m_support_integration(
    db_path: str | Path | None,
    backup_proof_path: str | Path | None,
    *,
    operator_approved: bool = False,
    parent_window_id: int | None = None,
    token_id: int | None = None,
    pair_id: int | None = None,
    # Evidence quality parameters (for capture)
    data_quality_label: str = "CLEAN_DATA",
    source_status: str = "COMPLETE",
    is_stale: bool = False,
    is_incomplete: bool = False,
    is_failed: bool = False,
    is_mismatched: bool = False,
    opened_at: str | None = None,
    closed_at: str | None = None,
    # Mode flags
    capture: bool = True,
    enrich: bool = True,
) -> dict[str, Any]:
    """Main entry point for Lane X8 5m support evidence integration.

    Captures WINDOW_5M_MICRO_EVENT evidence linked to a parent WINDOW_15M window,
    then reads back the enriched 15m context.

    capture=True (default): writes 5m evidence to DB.
    enrich=True (default): reads back enriched context after capture.
    capture=False, enrich=True: read-only enrichment report.
    capture=True, enrich=False: capture only.
    """
    blocked_reasons: list[str] = []

    if not operator_approved:
        blocked_reasons.append("operator_approved must be True for Lane X8")

    if db_path is None:
        blocked_reasons.append("db_path is required")

    if backup_proof_path is None:
        blocked_reasons.append("backup_proof_path is required")
    else:
        bp = Path(backup_proof_path)
        if not bp.exists():
            blocked_reasons.append(f"backup_proof_path not found: {backup_proof_path}")

    ids_needed_for_capture = capture
    if ids_needed_for_capture and (
        parent_window_id is None or token_id is None or pair_id is None
    ):
        blocked_reasons.append(
            "parent_window_id, token_id, and pair_id are all required"
            " when capture=True"
        )

    if blocked_reasons:
        return {
            "command": LANE_X8_COMMAND_NAME,
            "lane_x8_status": LANE_X8_STATUS_BLOCKED,
            "operator_approved": operator_approved,
            "blocked_reasons": blocked_reasons,
            "capture_result": None,
            "enrich_result": None,
            "5m_main_window_blocked": True,
            "5m_clean_memory_blocked": True,
            "retrieval_from_5m_blocked": True,
            "paper_decision_from_5m_blocked": True,
            "buy_from_5m_blocked": True,
            "position_from_5m_blocked": True,
            "hard_locks": dict(_HARD_LOCKS),
        }

    capture_result: dict[str, Any] | None = None
    enrich_result: dict[str, Any] | None = None

    if capture and parent_window_id is not None and token_id is not None and pair_id is not None:
        capture_result = capture_5m_support_evidence(
            db_path,
            parent_window_id,
            token_id,
            pair_id,
            operator_approved=operator_approved,
            data_quality_label=data_quality_label,
            source_status=source_status,
            is_stale=is_stale,
            is_incomplete=is_incomplete,
            is_failed=is_failed,
            is_mismatched=is_mismatched,
            opened_at=opened_at,
            closed_at=closed_at,
        )
        if capture_result.get("lane_x8_capture_status") == LANE_X8_STATUS_BLOCKED:
            return {
                "command": LANE_X8_COMMAND_NAME,
                "lane_x8_status": LANE_X8_STATUS_BLOCKED,
                "operator_approved": operator_approved,
                "blocked_reasons": capture_result.get("blocked_reasons", []),
                "capture_result": capture_result,
                "enrich_result": None,
                "5m_main_window_blocked": True,
                "5m_clean_memory_blocked": True,
                "retrieval_from_5m_blocked": True,
                "paper_decision_from_5m_blocked": True,
                "buy_from_5m_blocked": True,
                "position_from_5m_blocked": True,
                "hard_locks": dict(_HARD_LOCKS),
            }

    if (
        enrich
        and parent_window_id is not None
        and token_id is not None
        and pair_id is not None
    ):
        enrich_result = enrich_15m_context_with_5m_support(
            db_path,
            parent_window_id,
            token_id,
            pair_id,
        )

    return {
        "command": LANE_X8_COMMAND_NAME,
        "lane_x8_status": LANE_X8_STATUS_COMPLETED,
        "operator_approved": operator_approved,
        "blocked_reasons": [],
        "capture_result": capture_result,
        "enrich_result": enrich_result,
        "5m_main_window_blocked": True,
        "5m_clean_memory_blocked": True,
        "retrieval_from_5m_blocked": True,
        "paper_decision_from_5m_blocked": True,
        "buy_from_5m_blocked": True,
        "position_from_5m_blocked": True,
        "hard_locks": dict(_HARD_LOCKS),
    }
