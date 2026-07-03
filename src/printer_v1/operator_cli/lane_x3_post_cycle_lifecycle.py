"""Lane X3 — Post-Cycle Cooldown / Archive / Rotation Lifecycle Wiring.

Prevents Printer from tracking the same stale token/pair forever after a memory
cycle completes. Wires ENTER_COOLDOWN and ARCHIVE_AFTER_MEMORY_WINDOW lifecycle
events, blocks immediate stale re-selection, and allows intentional revival.

Key design decisions:
- Uses existing printer_tracking_queue and printer_token_lifecycle_events tables.
- Does NOT modify lane_x2_two_token_runner.py or any existing runner.
- Is called as a post-cycle step, or its gate function is called pre-cycle.
- The "most recent queue entry" model: reopen creates a new QUEUED entry so the
  cooldown gate only sees the latest status per (token_id, pair_id).
- Dirty/audit-only memory is NOT touched — only lifecycle state is updated.

Stale re-selection prevention:
  1. X2 cycle completes → caller invokes enter_cooldown_after_window (or
     evaluate_post_cycle_lifecycle) → COOLDOWN entries written to tracking queue.
  2. Next X2 attempt → check_x3_cooldown_gate detects COOLDOWN → BLOCKED.
  3. Operator calls reopen_token → new QUEUED entry overrides COOLDOWN.
  4. X2 retry → gate passes → cycle proceeds.

Hard rules (same as X2):
- No BUY/SELL/HOLD. No paper decisions. No positions. No PnL.
- No retrieval activation. No scoring/ranking/confidence/weighted logic.
- No wallet/private keys. No live trading. No paid APIs.
- Dirty/audit-only memory is preserved — lifecycle transitions only.
- Zero clean memories remains valid after any lifecycle transition.
"""

from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


LANE_X3_COMMAND_NAME: str = "printer-run-lane-x3-post-cycle-lifecycle"

LANE_X3_STATUS_COOLDOWN_ENTERED: str = "LANE_X3_COOLDOWN_ENTERED"
LANE_X3_STATUS_ARCHIVED: str = "LANE_X3_ARCHIVED"
LANE_X3_STATUS_REOPENED: str = "LANE_X3_REOPENED"
LANE_X3_STATUS_NO_ACTION: str = "LANE_X3_NO_ACTION"
LANE_X3_STATUS_BLOCKED: str = "LANE_X3_BLOCKED"

# Queue status values (match printer_tracking_queue.queue_status CHECK constraint)
_QUEUE_STATUS_QUEUED: str = "QUEUED"
_QUEUE_STATUS_COOLDOWN: str = "COOLDOWN"
_QUEUE_STATUS_ARCHIVED: str = "ARCHIVED"

# Lifecycle events (match printer_token_lifecycle_events.lifecycle_event)
_EVENT_ENTER_COOLDOWN: str = "ENTER_COOLDOWN"
_EVENT_ARCHIVE_AFTER_MEMORY_WINDOW: str = "ARCHIVE_AFTER_MEMORY_WINDOW"
_EVENT_REOPEN_REVIVED_TOKEN: str = "REOPEN_REVIVED_TOKEN"

# Lifecycle state values (match printer_token_lifecycle_events.new_state)
_STATE_TRACK_FAST: str = "TRACK_FAST"
_STATE_COOLDOWN: str = "COOLDOWN"
_STATE_ARCHIVED: str = "ARCHIVED"
_STATE_WATCH_ONLY: str = "WATCH_ONLY"

_ARCHIVE_POLICY_COOLDOWN: str = "cooldown"
_ARCHIVE_POLICY_ARCHIVE: str = "archive"

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
    "no_memory_deletion": True,
}

_MEMORY_TABLES: tuple[str, ...] = (
    "printer_memory_windows",
    "printer_token_snapshots",
    "printer_memory_audit_reports",
    "printer_memory_fingerprints",
    "printer_episodes",
    "printer_episode_snapshots",
    "printer_episode_outcomes",
)

_FORBIDDEN_WRITE_TABLES: tuple[str, ...] = (
    "printer_paper_decisions",
    "printer_paper_positions",
    "printer_paper_trade_events",
    "printer_paper_trade_audits",
    "printer_paper_audit_reports",
    "printer_retrieval_candidates",
    "printer_retrieval_results",
)


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


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
        except Exception:
            return 0
        finally:
            conn.close()
    except Exception:
        return 0


# ---------------------------------------------------------------------------
# Low-level DB helpers (direct SQLite — no dependency on tracking_queue.py)
# ---------------------------------------------------------------------------

def _get_or_create_token(conn: sqlite3.Connection, mint: str, now: str) -> int:
    """Find or create a minimal printer_tokens record; return token_id."""
    conn.execute(
        """
        INSERT OR IGNORE INTO printer_tokens
            (token_mint, chain, first_seen_at, last_seen_at, created_at, updated_at)
        VALUES (?, 'solana', ?, ?, ?, ?)
        """,
        (mint, now, now, now, now),
    )
    row = conn.execute(
        "SELECT id FROM printer_tokens WHERE token_mint = ?", (mint,)
    ).fetchone()
    return int(row["id"])


def _get_or_create_pair(
    conn: sqlite3.Connection, token_id: int, pair_address: str, now: str
) -> int:
    """Find or create a minimal printer_pairs record; return pair_id."""
    conn.execute(
        """
        INSERT OR IGNORE INTO printer_pairs
            (token_id, pair_address, first_seen_at, last_seen_at, created_at, updated_at)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (token_id, pair_address, now, now, now, now),
    )
    row = conn.execute(
        "SELECT id FROM printer_pairs WHERE pair_address = ?", (pair_address,)
    ).fetchone()
    return int(row["id"])


def _insert_queue_entry(
    conn: sqlite3.Connection,
    token_id: int,
    pair_id: int,
    tracking_lane: str,
    tracking_action: str,
    queue_status: str,
    now: str,
) -> int:
    """Insert a new tracking queue entry; return queue_id."""
    cursor = conn.execute(
        """
        INSERT INTO printer_tracking_queue (
            token_id, pair_id, tracking_lane, tracking_action,
            priority_reason, next_check_at, queue_status,
            source_status, data_quality_label, created_at, updated_at
        ) VALUES (?, ?, ?, ?, 'post_cycle_x3', ?, ?, 'COMPLETE', 'CLEAN_DATA', ?, ?)
        """,
        (token_id, pair_id, tracking_lane, tracking_action, now, queue_status, now, now),
    )
    return int(cursor.lastrowid)


def _record_lifecycle_event_direct(
    conn: sqlite3.Connection,
    *,
    token_id: int,
    pair_id: int,
    previous_state: str | None,
    new_state: str,
    lifecycle_event: str,
    source_status: str,
    data_quality_label: str,
    event_payload: dict | None,
) -> int:
    """Write a lifecycle event row; return event_id."""
    payload_json = json.dumps(event_payload or {}, sort_keys=True)
    cursor = conn.execute(
        """
        INSERT INTO printer_token_lifecycle_events (
            token_id, pair_id, previous_state, new_state,
            lifecycle_event, priority_reason,
            source_status, data_quality_label, event_payload_json
        ) VALUES (?, ?, ?, ?, ?, 'post_cycle_x3', ?, ?, ?)
        """,
        (
            token_id,
            pair_id,
            previous_state,
            new_state,
            lifecycle_event,
            source_status,
            data_quality_label,
            payload_json,
        ),
    )
    return int(cursor.lastrowid)


def _find_pair_address_for_mint(db_path: str | Path, mint: str) -> str | None:
    """Return the most recent pair_address for the given mint, or None."""
    try:
        conn = sqlite3.connect(str(db_path))
        conn.row_factory = sqlite3.Row
        try:
            row = conn.execute(
                """
                SELECT pp.pair_address
                FROM printer_pairs pp
                JOIN printer_tokens pt ON pp.token_id = pt.id
                WHERE pt.token_mint = ?
                ORDER BY pp.id DESC
                LIMIT 1
                """,
                (mint,),
            ).fetchone()
            return str(row["pair_address"]) if row else None
        finally:
            conn.close()
    except Exception:
        return None


def _most_recent_queue_status(db_path: str | Path, token_mint: str) -> str | None:
    """Return the most recent queue_status for this mint, or None if no entries."""
    try:
        conn = sqlite3.connect(str(db_path))
        conn.row_factory = sqlite3.Row
        try:
            # Find token_id
            tok = conn.execute(
                "SELECT id FROM printer_tokens WHERE token_mint = ?", (token_mint,)
            ).fetchone()
            if tok is None:
                return None
            token_id = int(tok["id"])
            row = conn.execute(
                """
                SELECT queue_status
                FROM printer_tracking_queue
                WHERE token_id = ?
                ORDER BY created_at DESC, id DESC
                LIMIT 1
                """,
                (token_id,),
            ).fetchone()
            return str(row["queue_status"]) if row else None
        finally:
            conn.close()
    except Exception:
        return None


# ---------------------------------------------------------------------------
# Public lifecycle functions
# ---------------------------------------------------------------------------

def enter_cooldown_after_window(
    db_path: str | Path,
    token_mint: str,
    pair_address: str,
    *,
    event_payload: dict | None = None,
    source_status: str = "COMPLETE",
    data_quality_label: str = "CLEAN_DATA",
) -> dict[str, Any]:
    """Record ENTER_COOLDOWN lifecycle event and add COOLDOWN tracking-queue entry.

    Creates minimal token/pair records if they don't already exist.
    Does NOT delete or modify any snapshot, memory window, or episode data.
    """
    now = _utc_now()
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    try:
        token_id = _get_or_create_token(conn, token_mint, now)
        pair_id = _get_or_create_pair(conn, token_id, pair_address, now)
        queue_id = _insert_queue_entry(
            conn, token_id, pair_id,
            _STATE_TRACK_FAST, _EVENT_ENTER_COOLDOWN,
            _QUEUE_STATUS_COOLDOWN, now,
        )
        event_id = _record_lifecycle_event_direct(
            conn,
            token_id=token_id,
            pair_id=pair_id,
            previous_state=_STATE_TRACK_FAST,
            new_state=_STATE_COOLDOWN,
            lifecycle_event=_EVENT_ENTER_COOLDOWN,
            source_status=source_status,
            data_quality_label=data_quality_label,
            event_payload=event_payload,
        )
        conn.commit()
        return {
            "lane_x3_status": LANE_X3_STATUS_COOLDOWN_ENTERED,
            "token_mint": token_mint,
            "pair_address": pair_address,
            "token_id": token_id,
            "pair_id": pair_id,
            "queue_id": queue_id,
            "lifecycle_event_id": event_id,
            "lifecycle_event": _EVENT_ENTER_COOLDOWN,
            "previous_state": _STATE_TRACK_FAST,
            "new_state": _STATE_COOLDOWN,
            "memory_tables_preserved": True,
        }
    except Exception as exc:
        try:
            conn.rollback()
        except Exception:
            pass
        return {
            "lane_x3_status": LANE_X3_STATUS_BLOCKED,
            "token_mint": token_mint,
            "pair_address": pair_address,
            "error": str(exc),
        }
    finally:
        conn.close()


def archive_after_memory_window(
    db_path: str | Path,
    token_mint: str,
    pair_address: str,
    *,
    event_payload: dict | None = None,
    source_status: str = "COMPLETE",
    data_quality_label: str = "CLEAN_DATA",
) -> dict[str, Any]:
    """Record ARCHIVE_AFTER_MEMORY_WINDOW lifecycle event and add ARCHIVED queue entry.

    Appropriate when a token/pair has completed enough memory and does not need
    to be immediately re-tracked.  Old snapshots, memory windows, and episodes
    are NOT modified — they remain available for retrieval reporting.
    """
    now = _utc_now()
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    try:
        token_id = _get_or_create_token(conn, token_mint, now)
        pair_id = _get_or_create_pair(conn, token_id, pair_address, now)
        queue_id = _insert_queue_entry(
            conn, token_id, pair_id,
            _STATE_TRACK_FAST, _EVENT_ARCHIVE_AFTER_MEMORY_WINDOW,
            _QUEUE_STATUS_ARCHIVED, now,
        )
        event_id = _record_lifecycle_event_direct(
            conn,
            token_id=token_id,
            pair_id=pair_id,
            previous_state=_STATE_TRACK_FAST,
            new_state=_STATE_ARCHIVED,
            lifecycle_event=_EVENT_ARCHIVE_AFTER_MEMORY_WINDOW,
            source_status=source_status,
            data_quality_label=data_quality_label,
            event_payload=event_payload,
        )
        conn.commit()
        return {
            "lane_x3_status": LANE_X3_STATUS_ARCHIVED,
            "token_mint": token_mint,
            "pair_address": pair_address,
            "token_id": token_id,
            "pair_id": pair_id,
            "queue_id": queue_id,
            "lifecycle_event_id": event_id,
            "lifecycle_event": _EVENT_ARCHIVE_AFTER_MEMORY_WINDOW,
            "previous_state": _STATE_TRACK_FAST,
            "new_state": _STATE_ARCHIVED,
            "memory_tables_preserved": True,
        }
    except Exception as exc:
        try:
            conn.rollback()
        except Exception:
            pass
        return {
            "lane_x3_status": LANE_X3_STATUS_BLOCKED,
            "token_mint": token_mint,
            "pair_address": pair_address,
            "error": str(exc),
        }
    finally:
        conn.close()


def is_token_in_cooldown_or_archived(db_path: str | Path, token_mint: str) -> bool:
    """Return True if the most recent tracking-queue entry is COOLDOWN or ARCHIVED.

    A fresh mint with no queue entries is NOT in cooldown (returns False).
    """
    status = _most_recent_queue_status(db_path, token_mint)
    return status in {_QUEUE_STATUS_COOLDOWN, _QUEUE_STATUS_ARCHIVED}


def get_token_lifecycle_status(db_path: str | Path, token_mint: str) -> dict[str, Any]:
    """Read current lifecycle state for a token from tracking queue and events."""
    queue_status = _most_recent_queue_status(db_path, token_mint)
    blocked = queue_status in {_QUEUE_STATUS_COOLDOWN, _QUEUE_STATUS_ARCHIVED}
    return {
        "token_mint": token_mint,
        "most_recent_queue_status": queue_status,
        "in_cooldown_or_archived": blocked,
    }


def reopen_token(
    db_path: str | Path,
    token_mint: str,
    pair_address: str,
    *,
    event_payload: dict | None = None,
    source_status: str = "COMPLETE",
    data_quality_label: str = "CLEAN_DATA",
) -> dict[str, Any]:
    """Record REOPEN_REVIVED_TOKEN event and add a QUEUED entry so the cooldown
    gate will pass on the next cycle.

    The previous COOLDOWN/ARCHIVED entries are left intact for audit history.
    Only the most-recent-entry check in check_x3_cooldown_gate determines
    whether re-selection is blocked.
    """
    now = _utc_now()
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    try:
        token_id = _get_or_create_token(conn, token_mint, now)
        pair_id = _get_or_create_pair(conn, token_id, pair_address, now)
        queue_id = _insert_queue_entry(
            conn, token_id, pair_id,
            _STATE_WATCH_ONLY, _EVENT_REOPEN_REVIVED_TOKEN,
            _QUEUE_STATUS_QUEUED, now,
        )
        event_id = _record_lifecycle_event_direct(
            conn,
            token_id=token_id,
            pair_id=pair_id,
            previous_state=_STATE_COOLDOWN,
            new_state=_STATE_WATCH_ONLY,
            lifecycle_event=_EVENT_REOPEN_REVIVED_TOKEN,
            source_status=source_status,
            data_quality_label=data_quality_label,
            event_payload=event_payload,
        )
        conn.commit()
        return {
            "lane_x3_status": LANE_X3_STATUS_REOPENED,
            "token_mint": token_mint,
            "pair_address": pair_address,
            "token_id": token_id,
            "pair_id": pair_id,
            "queue_id": queue_id,
            "lifecycle_event_id": event_id,
            "lifecycle_event": _EVENT_REOPEN_REVIVED_TOKEN,
            "previous_state": _STATE_COOLDOWN,
            "new_state": _STATE_WATCH_ONLY,
        }
    except Exception as exc:
        try:
            conn.rollback()
        except Exception:
            pass
        return {
            "lane_x3_status": LANE_X3_STATUS_BLOCKED,
            "token_mint": token_mint,
            "pair_address": pair_address,
            "error": str(exc),
        }
    finally:
        conn.close()


def check_x3_cooldown_gate(
    db_path: str | Path,
    token_mints: list[str],
) -> list[str]:
    """Return a list of mints that are currently in COOLDOWN or ARCHIVED.

    Empty list → all mints are clear, cycle may proceed.
    Non-empty list → at least one mint is stale, cycle should be blocked.

    This gate is checked BEFORE starting a new X2 cycle.  If a mint has no
    queue entry at all (fresh DB), it is considered clear (not blocked).
    """
    blocked: list[str] = []
    for mint in token_mints:
        if is_token_in_cooldown_or_archived(db_path, mint):
            status = _most_recent_queue_status(db_path, mint)
            blocked.append(
                f"{mint}: most_recent_queue_status={status!r}"
                " — enter cooldown or archived; call reopen_token to unblock"
            )
    return blocked


# ---------------------------------------------------------------------------
# Post-cycle batch evaluator
# ---------------------------------------------------------------------------

def evaluate_post_cycle_lifecycle(
    db_path: str | Path,
    x2_result: dict[str, Any],
    *,
    pair_address_by_mint: dict[str, str] | None = None,
    archive_policy: str = _ARCHIVE_POLICY_COOLDOWN,
) -> dict[str, Any]:
    """Process an X2 cycle result and apply lifecycle transitions for each token.

    For each token slot that had at least one window close:
    - archive_policy="cooldown" (default): call enter_cooldown_after_window.
    - archive_policy="archive": call archive_after_memory_window.

    Tokens with zero window closes are not transitioned (NO_ACTION).

    pair_address_by_mint: optional override {mint: pair_address}.  When None,
        the pair address is discovered from the DB via the most recent snapshot.

    Returns a summary dict with per-token transition results.
    """
    x2_status = x2_result.get("lane_x2_status", "")
    if x2_status not in {"LANE_X2_COMPLETED", "LANE_X2_STOPPED"}:
        return {
            "lane_x3_status": LANE_X3_STATUS_BLOCKED,
            "blocked_reason": (
                f"x2 result status {x2_status!r} is not a processable terminal state"
            ),
            "transitions": [],
            "hard_locks": dict(_HARD_LOCKS),
        }

    transitions: list[dict[str, Any]] = []

    for slot_key in ("token_a_report", "token_b_report"):
        report = x2_result.get(slot_key) or {}
        mint = str(report.get("mint", ""))
        if not mint:
            continue

        window_closes = int(report.get("window_closes", 0) or 0)
        if window_closes == 0:
            transitions.append({
                "mint": mint,
                "slot": report.get("slot"),
                "lane_x3_status": LANE_X3_STATUS_NO_ACTION,
                "reason": "no window closes in this cycle",
            })
            continue

        # Discover pair_address
        pair_address = (pair_address_by_mint or {}).get(mint)
        if pair_address is None:
            pair_address = _find_pair_address_for_mint(db_path, mint) or ""

        if archive_policy == _ARCHIVE_POLICY_ARCHIVE:
            result = archive_after_memory_window(db_path, mint, pair_address)
        else:
            result = enter_cooldown_after_window(db_path, mint, pair_address)

        result["slot"] = report.get("slot")
        result["window_closes"] = window_closes
        transitions.append(result)

    # Count results
    cooldown_count = sum(
        1 for t in transitions if t.get("lane_x3_status") == LANE_X3_STATUS_COOLDOWN_ENTERED
    )
    archive_count = sum(
        1 for t in transitions if t.get("lane_x3_status") == LANE_X3_STATUS_ARCHIVED
    )
    no_action_count = sum(
        1 for t in transitions if t.get("lane_x3_status") == LANE_X3_STATUS_NO_ACTION
    )

    return {
        "lane_x3_status": (
            LANE_X3_STATUS_ARCHIVED if archive_count > 0 and cooldown_count == 0
            else LANE_X3_STATUS_COOLDOWN_ENTERED if cooldown_count > 0
            else LANE_X3_STATUS_NO_ACTION
        ),
        "x2_status": x2_status,
        "archive_policy": archive_policy,
        "cooldown_entered_count": cooldown_count,
        "archived_count": archive_count,
        "no_action_count": no_action_count,
        "transitions": transitions,
        "memory_tables_preserved": True,
        "zero_clean_memories_is_valid": True,
        "hard_locks": dict(_HARD_LOCKS),
        "buy_enabled": False,
        "sell_enabled": False,
        "hold_enabled": False,
        "paper_decisions_created": 0,
        "positions_created": 0,
        "pnl_created": 0,
        "retrieval_rows_created": 0,
    }


def check_memory_preservation(db_path: str | Path) -> dict[str, int]:
    """Count rows in memory tables to prove they were not deleted.

    Returns {table_name: row_count} for all relevant memory tables.
    """
    return {t: _count_table(db_path, t) for t in _MEMORY_TABLES}


def check_forbidden_tables(db_path: str | Path) -> dict[str, int]:
    """Return counts for tables that must remain zero."""
    return {t: _count_table(db_path, t) for t in _FORBIDDEN_WRITE_TABLES}
