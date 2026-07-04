"""Lane X6 — Discovery / Selection / Dedup Repair.

Repairs discovery, selection, and dedup so Printer can produce a fresh, useful,
non-duplicate Solana memecoin tracking set for bounded memory growth.

Design decisions:
- Reads candidates from the DB ``printer_discovery_candidates`` table, or
  from a caller-supplied ``candidate_list_override`` (tests, offline review).
- Deduplicates by mint first, then by pair.
- Explicitly detects same-token/new-pair and documents it in the output.
- Cooldown-aware: excludes mints with a most-recent COOLDOWN or ARCHIVED queue
  entry unless ``include_revivals=True`` and the mint's most-recent entry is
  QUEUED (i.e., already reopened by the operator).
- Assigns a deterministic memory-diet label to every candidate:
  PUMP / DUMP / FAKE_PUMP / WICK_ONLY / LATE_BUY_TRAP / LIQUIDITY_DECAY /
  DEAD_TOKEN / REVIVAL / AMBIGUOUS.
- Records an auditable selection reason for every accepted or rejected candidate.
- Never does live source fetching, never creates paper decisions, never creates
  trade events, never opens positions, never produces PnL.

Hard rules:
- Operator approval required.
- No BUY/SELL/HOLD. No paper decisions. No positions. No PnL.
- No retrieval activation. No scoring/ranking/confidence/weighted logic.
- No wallet/private keys. No live trading. No paid APIs.
- No discovery automation (discovery remains intake, not alpha).
- No token/pair mixing.
- Zero clean memories is always a valid outcome.
- Selection is memory-value based, not BUY-probability based.
"""

from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


LANE_X6_COMMAND_NAME: str = "printer-run-lane-x6-discovery-selection-repair"
LANE_X6_STATUS_COMPLETED: str = "LANE_X6_COMPLETED"
LANE_X6_STATUS_BLOCKED: str = "LANE_X6_BLOCKED"

# Memory diet labels — deterministic rule-based, not scoring.
DIET_PUMP: str = "PUMP"
DIET_DUMP: str = "DUMP"
DIET_FAKE_PUMP: str = "FAKE_PUMP"
DIET_WICK_ONLY: str = "WICK_ONLY"
DIET_LATE_BUY_TRAP: str = "LATE_BUY_TRAP"
DIET_LIQUIDITY_DECAY: str = "LIQUIDITY_DECAY"
DIET_DEAD_TOKEN: str = "DEAD_TOKEN"
DIET_REVIVAL: str = "REVIVAL"
DIET_AMBIGUOUS: str = "AMBIGUOUS"

ALL_DIET_LABELS: tuple[str, ...] = (
    DIET_PUMP,
    DIET_DUMP,
    DIET_FAKE_PUMP,
    DIET_WICK_ONLY,
    DIET_LATE_BUY_TRAP,
    DIET_LIQUIDITY_DECAY,
    DIET_DEAD_TOKEN,
    DIET_REVIVAL,
    DIET_AMBIGUOUS,
)

# Queue status values from printer_tracking_queue (must match schema).
_QUEUE_COOLDOWN: str = "COOLDOWN"
_QUEUE_ARCHIVED: str = "ARCHIVED"
_QUEUE_QUEUED: str = "QUEUED"

_DEFAULT_MAX_CANDIDATES: int = 20

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


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _float_or_zero(value: Any) -> float:
    if value is None:
        return 0.0
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def _int_or_zero(value: Any) -> int:
    if value is None:
        return 0
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0


def _count_forbidden_table(db_path: str | Path, table: str) -> int:
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


def _check_forbidden_tables(db_path: str | Path) -> dict[str, int]:
    return {t: _count_forbidden_table(db_path, t) for t in _FORBIDDEN_WRITE_TABLES}


# ---------------------------------------------------------------------------
# Memory diet classification (deterministic, no scoring)
# ---------------------------------------------------------------------------

def classify_memory_diet_label(
    candidate: dict[str, Any],
    *,
    is_revival: bool = False,
) -> str:
    """Classify candidate into a memory-diet label.

    Rules are deterministic and based on observed market-data fields.
    No scores, no ranks, no confidence values are computed or stored.
    The label describes the *kind of market behaviour* the candidate exhibits,
    which is the memory-value basis for inclusion in a diverse training set.
    """
    if is_revival:
        return DIET_REVIVAL

    price_5m = _float_or_zero(candidate.get("price_change_5m"))
    price_1h = _float_or_zero(candidate.get("price_change_1h"))
    price_24h = _float_or_zero(candidate.get("price_change_24h"))
    vol_5m = _float_or_zero(candidate.get("volume_5m"))
    vol_1h = _float_or_zero(candidate.get("volume_1h"))
    vol_24h = _float_or_zero(candidate.get("volume_24h"))
    txns_5m = _int_or_zero(candidate.get("txns_5m"))
    txns_1h = _int_or_zero(candidate.get("txns_1h"))
    txns_24h = _int_or_zero(candidate.get("txns_24h"))
    liquidity = _float_or_zero(candidate.get("liquidity_usd"))

    # FAKE_PUMP — price spike with thin liquidity (manipulation signal).
    # Checked before DEAD_TOKEN: a price spike is evidence the token is not dead.
    if (price_1h > 50.0 or price_5m > 30.0) and liquidity < 3_000.0:
        return DIET_FAKE_PUMP

    # WICK_ONLY — large 5m spike that did NOT persist into the 1h.
    # Checked before DEAD_TOKEN for the same reason.
    if price_5m > 30.0 and abs(price_1h) < 10.0:
        return DIET_WICK_ONLY

    # LATE_BUY_TRAP — already moved very large over 24h, entry is risky.
    if price_24h > 200.0 and vol_24h > 5_000.0:
        return DIET_LATE_BUY_TRAP

    # DEAD_TOKEN — near-zero activity across all timeframes (no price signal above).
    is_dead = (
        vol_5m <= 0
        and txns_5m <= 0
        and vol_1h <= 0
        and txns_1h <= 0
        and vol_24h <= 10.0
        and txns_24h <= 2
    )
    if is_dead:
        return DIET_DEAD_TOKEN

    # PUMP — genuine fast move with real volume and activity
    if (price_5m > 20.0 and vol_5m > 5_000.0 and txns_5m > 20) or (
        price_1h > 50.0 and vol_1h > 10_000.0
    ):
        return DIET_PUMP

    # DUMP — significant price decline with real volume
    if (price_1h < -30.0 and vol_1h > 5_000.0) or (
        price_24h < -50.0 and vol_24h > 5_000.0
    ):
        return DIET_DUMP

    # LIQUIDITY_DECAY — liquidity above minimum threshold but volume almost absent
    if liquidity > 1_000.0 and vol_24h < 500.0 and txns_24h < 5:
        return DIET_LIQUIDITY_DECAY

    return DIET_AMBIGUOUS


# ---------------------------------------------------------------------------
# Dedup helpers
# ---------------------------------------------------------------------------

def dedup_by_mint(
    candidates: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Collapse candidates with the same token_mint.

    Within duplicates, keep the one with the most recent ``captured_at``
    (falling back to list order). Return (kept, collapsed).
    """
    seen: dict[str, dict[str, Any]] = {}
    collapsed: list[dict[str, Any]] = []

    for cand in candidates:
        mint = cand.get("token_mint", "")
        if not mint:
            collapsed.append({**cand, "_collapse_reason": "missing_mint"})
            continue
        if mint not in seen:
            seen[mint] = cand
        else:
            existing = seen[mint]
            existing_ts = existing.get("captured_at", "")
            new_ts = cand.get("captured_at", "")
            if new_ts > existing_ts:
                collapsed.append({**existing, "_collapse_reason": "mint_duplicate_older"})
                seen[mint] = cand
            else:
                collapsed.append({**cand, "_collapse_reason": "mint_duplicate_older"})

    kept = list(seen.values())
    return kept, collapsed


def dedup_by_pair(
    candidates: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Collapse candidates with the same pair_address (after mint dedup).

    Within duplicates, keep the one with the most recent ``captured_at``.
    Return (kept, collapsed).
    """
    seen: dict[str, dict[str, Any]] = {}
    collapsed: list[dict[str, Any]] = []

    for cand in candidates:
        pair = cand.get("pair_address", "")
        if not pair:
            # No pair address — keep as-is (may be marked with its own reason)
            key = f"_no_pair_{id(cand)}"
            seen[key] = cand
            continue
        if pair not in seen:
            seen[pair] = cand
        else:
            existing = seen[pair]
            existing_ts = existing.get("captured_at", "")
            new_ts = cand.get("captured_at", "")
            if new_ts > existing_ts:
                collapsed.append({**existing, "_collapse_reason": "pair_duplicate_older"})
                seen[pair] = cand
            else:
                collapsed.append({**cand, "_collapse_reason": "pair_duplicate_older"})

    kept = list(seen.values())
    return kept, collapsed


def detect_same_token_new_pair(
    candidates: list[dict[str, Any]],
    already_known_pairs_by_mint: dict[str, list[str]] | None = None,
) -> list[dict[str, Any]]:
    """Detect cases where the same mint appears with multiple pair addresses.

    Returns a list of records documenting each same-token/new-pair situation.
    ``already_known_pairs_by_mint`` maps mint → list of pair addresses already
    in the DB for that mint, enabling detection of DB-side duplication too.
    """
    mint_to_pairs: dict[str, list[str]] = {}
    for cand in candidates:
        mint = cand.get("token_mint", "")
        pair = cand.get("pair_address", "")
        if mint and pair:
            mint_to_pairs.setdefault(mint, [])
            if pair not in mint_to_pairs[mint]:
                mint_to_pairs[mint].append(pair)

    if already_known_pairs_by_mint:
        for mint, known_pairs in already_known_pairs_by_mint.items():
            if mint not in mint_to_pairs:
                continue
            for kp in known_pairs:
                if kp not in mint_to_pairs[mint]:
                    mint_to_pairs[mint].append(kp)

    cases = []
    for mint, pairs in mint_to_pairs.items():
        if len(pairs) > 1:
            cases.append({
                "token_mint": mint,
                "pair_count": len(pairs),
                "pairs": pairs,
                "handling": "keep_freshest_pair_after_dedup",
                "reason": "same_token_new_pair_detected_explicitly",
            })
    return cases


# ---------------------------------------------------------------------------
# Cooldown-aware filtering
# ---------------------------------------------------------------------------

def _load_mint_lifecycle_statuses(
    db_path: str | Path,
    mints: list[str],
) -> dict[str, str]:
    """Return {mint → most_recent_queue_status} for the given mints.

    Queries ``printer_tracking_queue`` via a JOIN to ``printer_tokens``.
    Returns an empty dict if the table does not exist or DB is unreadable.
    """
    if not mints:
        return {}
    try:
        conn = sqlite3.connect(str(db_path))
        conn.row_factory = sqlite3.Row
        try:
            rows = conn.execute(
                """
                SELECT pt.token_mint,
                       tq.queue_status
                FROM printer_tracking_queue tq
                JOIN printer_tokens pt ON pt.id = tq.token_id
                WHERE pt.token_mint IN ({placeholders})
                ORDER BY tq.updated_at DESC, tq.id DESC
                """.format(placeholders=",".join("?" * len(mints))),
                mints,
            ).fetchall()
        except sqlite3.OperationalError:
            return {}
        finally:
            conn.close()
    except Exception:
        return {}

    # Keep only the most-recent queue_status per mint.
    result: dict[str, str] = {}
    for row in rows:
        mint = row["token_mint"]
        if mint not in result:
            result[mint] = row["queue_status"]
    return result


def filter_cooldown_blocked(
    candidates: list[dict[str, Any]],
    lifecycle_statuses: dict[str, str],
    *,
    include_revivals: bool = True,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Split candidates into (allowed, cooldown_blocked).

    A candidate is blocked when its most-recent queue status is COOLDOWN or
    ARCHIVED, UNLESS ``include_revivals=True`` and the status is QUEUED
    (operator already reopened it).
    """
    allowed: list[dict[str, Any]] = []
    blocked: list[dict[str, Any]] = []

    for cand in candidates:
        mint = cand.get("token_mint", "")
        status = lifecycle_statuses.get(mint)

        if status in (_QUEUE_COOLDOWN, _QUEUE_ARCHIVED):
            blocked.append({
                **cand,
                "_blocked_reason": f"lifecycle_status_{status.lower()}",
                "_lifecycle_status": status,
            })
        else:
            is_revival = (
                include_revivals
                and status == _QUEUE_QUEUED
                and lifecycle_statuses.get(mint) == _QUEUE_QUEUED
            )
            allowed.append({**cand, "_lifecycle_status": status or "unknown"})

    return allowed, blocked


def _load_same_token_new_pair_db(
    db_path: str | Path,
    mints: list[str],
) -> dict[str, list[str]]:
    """Load existing pair addresses per mint from DB.

    Returns {mint → [pair_address, ...]} for mints that have pairs in DB.
    """
    if not mints:
        return {}
    try:
        conn = sqlite3.connect(str(db_path))
        conn.row_factory = sqlite3.Row
        try:
            rows = conn.execute(
                """
                SELECT pt.token_mint, pp.pair_address
                FROM printer_pairs pp
                JOIN printer_tokens pt ON pt.id = pp.token_id
                WHERE pt.token_mint IN ({placeholders})
                """.format(placeholders=",".join("?" * len(mints))),
                mints,
            ).fetchall()
        except sqlite3.OperationalError:
            return {}
        finally:
            conn.close()
    except Exception:
        return {}

    result: dict[str, list[str]] = {}
    for row in rows:
        mint = row["token_mint"]
        result.setdefault(mint, [])
        if row["pair_address"] not in result[mint]:
            result[mint].append(row["pair_address"])
    return result


def _load_recent_candidates_from_db(
    db_path: str | Path,
    max_candidates: int,
) -> list[dict[str, Any]]:
    """Load recent TRACK_FAST/TRACK_NORMAL candidates from the DB.

    Reads from ``printer_discovery_candidates`` ordered by most recent first.
    Returns empty list if table does not exist or DB is unreadable.
    """
    try:
        conn = sqlite3.connect(str(db_path))
        conn.row_factory = sqlite3.Row
        try:
            rows = conn.execute(
                """
                SELECT dc.id,
                       pt.token_mint,
                       pp.pair_address,
                       dc.discovery_action,
                       dc.priority_reason,
                       dc.source_channel,
                       dc.normalized_candidate_payload_json,
                       dc.created_at
                FROM printer_discovery_candidates dc
                LEFT JOIN printer_tokens pt ON pt.id = dc.token_id
                LEFT JOIN printer_pairs pp ON pp.id = dc.pair_id
                WHERE dc.discovery_action IN ('TRACK_FAST', 'TRACK_NORMAL')
                  AND pt.token_mint IS NOT NULL
                  AND pp.pair_address IS NOT NULL
                ORDER BY dc.created_at DESC, dc.id DESC
                LIMIT ?
                """,
                (max_candidates * 4,),  # fetch extra before dedup
            ).fetchall()
        except sqlite3.OperationalError:
            return []
        finally:
            conn.close()
    except Exception:
        return []

    results = []
    for row in rows:
        normalized = {}
        raw = row["normalized_candidate_payload_json"]
        if raw:
            try:
                normalized = json.loads(raw)
            except (json.JSONDecodeError, TypeError):
                pass
        entry = dict(normalized)
        entry["token_mint"] = row["token_mint"]
        entry["pair_address"] = row["pair_address"]
        entry["discovery_action"] = row["discovery_action"]
        entry["priority_reason"] = row["priority_reason"]
        entry["source_channel"] = row["source_channel"]
        entry["captured_at"] = row["created_at"] or ""
        entry["_db_candidate_id"] = row["id"]
        results.append(entry)
    return results


# ---------------------------------------------------------------------------
# Blocked result helper
# ---------------------------------------------------------------------------

def _blocked_result(reason: str, **extra: Any) -> dict[str, Any]:
    return {
        "command": LANE_X6_COMMAND_NAME,
        "lane_x6_status": LANE_X6_STATUS_BLOCKED,
        "blocked_reason": reason,
        "operator_approved": extra.get("operator_approved", False),
        "db_path": str(extra.get("db_path", "")),
        "candidate_count_input": 0,
        "mint_duplicates_collapsed": 0,
        "pair_duplicates_collapsed": 0,
        "same_token_new_pair_cases": 0,
        "cooldown_blocked_count": 0,
        "selected_count": 0,
        "selected_candidates": [],
        "dedup_report": {"mint_duplicates": [], "pair_duplicates": [], "same_token_new_pair_cases": []},
        "cooldown_blocked": [],
        "memory_diet_summary": {lbl: 0 for lbl in ALL_DIET_LABELS},
        "zero_candidates_is_valid": True,
        "discovery_is_intake_not_alpha": True,
        "hard_locks": dict(_HARD_LOCKS),
        "buy_enabled": False,
        "sell_enabled": False,
        "hold_enabled": False,
        "paper_decisions_created": 0,
        "retrieval_rows_created": 0,
        "positions_created": 0,
        "trade_events_created": 0,
        "paper_trade_audits_created": 0,
        "pnl_created": 0,
        "forbidden_table_counts": {t: 0 for t in _FORBIDDEN_WRITE_TABLES},
        "run_started_at": _utc_now(),
        "run_finished_at": _utc_now(),
    }


# ---------------------------------------------------------------------------
# Main public function
# ---------------------------------------------------------------------------

def select_candidates_for_memory_growth(
    db_path: str | Path | None,
    backup_proof_path: str | Path | None,
    *,
    operator_approved: bool = False,
    max_candidates: int = _DEFAULT_MAX_CANDIDATES,
    cooldown_aware: bool = True,
    include_revivals: bool = True,
    candidate_list_override: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Select a fresh, non-duplicate Solana memecoin tracking set.

    Parameters
    ----------
    db_path:
        Path to the Printer V1 SQLite database. Must already exist.
    backup_proof_path:
        Path to an existing backup file. Proves the operator took a backup.
    operator_approved:
        Must be True. Gate prevents accidental runs.
    max_candidates:
        Maximum number of candidates to include in the selected set.
    cooldown_aware:
        When True, tokens currently in COOLDOWN or ARCHIVED status in the
        tracking queue are excluded from the output (unless reopened).
    include_revivals:
        When True and ``cooldown_aware=True``, tokens whose most-recent
        queue status is QUEUED (already reopened by the operator) are
        allowed even if they were previously cooled down.
    candidate_list_override:
        When provided, used instead of the DB read. Each entry should be a
        dict with at minimum ``token_mint``, ``pair_address``, ``chain``,
        and any market-data fields (volume_*, price_change_*, liquidity_usd,
        etc.) that inform the memory-diet classification.
    """
    started_at = _utc_now()
    blocked_reasons: list[str] = []

    if not operator_approved:
        blocked_reasons.append("operator_approved is required")

    if db_path is None or (
        candidate_list_override is None
        and not Path(str(db_path)).exists()
    ):
        blocked_reasons.append("db_path is required and must exist")

    if backup_proof_path is None or not Path(str(backup_proof_path)).exists():
        blocked_reasons.append("backup_proof_path is required and must exist")

    if blocked_reasons:
        r = _blocked_result(
            "; ".join(blocked_reasons),
            operator_approved=operator_approved,
            db_path=db_path,
        )
        r["blocked_reasons"] = blocked_reasons
        return r

    # ------------------------------------------------------------------
    # 1. Load candidates
    # ------------------------------------------------------------------
    if candidate_list_override is not None:
        raw_candidates: list[dict[str, Any]] = [dict(c) for c in candidate_list_override]
    else:
        raw_candidates = _load_recent_candidates_from_db(db_path, max_candidates)

    candidate_count_input = len(raw_candidates)

    # ------------------------------------------------------------------
    # 2. Mint-level dedup
    # ------------------------------------------------------------------
    after_mint_dedup, mint_collapsed = dedup_by_mint(raw_candidates)

    # ------------------------------------------------------------------
    # 3. Pair-level dedup (within the mint-deduped set)
    # ------------------------------------------------------------------
    after_pair_dedup, pair_collapsed = dedup_by_pair(after_mint_dedup)

    # ------------------------------------------------------------------
    # 4. Detect same-token/new-pair (cross-reference with DB if available)
    # ------------------------------------------------------------------
    all_mints = [c.get("token_mint", "") for c in raw_candidates if c.get("token_mint")]
    known_pairs_by_mint: dict[str, list[str]] = {}
    if candidate_list_override is None and db_path is not None:
        known_pairs_by_mint = _load_same_token_new_pair_db(db_path, all_mints)

    same_token_new_pair_cases = detect_same_token_new_pair(
        raw_candidates,
        already_known_pairs_by_mint=known_pairs_by_mint,
    )

    # ------------------------------------------------------------------
    # 5. Cooldown-aware filtering
    # ------------------------------------------------------------------
    cooldown_blocked: list[dict[str, Any]] = []
    if cooldown_aware:
        deduped_mints = [c.get("token_mint", "") for c in after_pair_dedup if c.get("token_mint")]
        lifecycle_statuses: dict[str, str] = {}
        if candidate_list_override is None and db_path is not None:
            lifecycle_statuses = _load_mint_lifecycle_statuses(db_path, deduped_mints)
        elif candidate_list_override is not None:
            # Support _lifecycle_status override in test candidates.
            for cand in after_pair_dedup:
                mint = cand.get("token_mint", "")
                if mint and "_lifecycle_status" in cand:
                    lifecycle_statuses[mint] = cand["_lifecycle_status"]

        after_pair_dedup, cooldown_blocked = filter_cooldown_blocked(
            after_pair_dedup,
            lifecycle_statuses,
            include_revivals=include_revivals,
        )

    # ------------------------------------------------------------------
    # 6. Cap at max_candidates
    # ------------------------------------------------------------------
    selected_pool = after_pair_dedup[:max_candidates]

    # ------------------------------------------------------------------
    # 7. Classify memory diet + build auditable selection reason
    # ------------------------------------------------------------------
    diet_summary: dict[str, int] = {lbl: 0 for lbl in ALL_DIET_LABELS}
    selected_candidates: list[dict[str, Any]] = []

    for cand in selected_pool:
        mint = cand.get("token_mint", "")
        pair = cand.get("pair_address", "")
        lifecycle_status = cand.get("_lifecycle_status", "unknown")
        is_revival = (
            lifecycle_status == _QUEUE_QUEUED
            and cand.get("_was_cooled", False)
        )
        diet_label = classify_memory_diet_label(cand, is_revival=is_revival)
        diet_summary[diet_label] = diet_summary.get(diet_label, 0) + 1

        # Auditable reason: diet_label:discovery_action:priority_reason
        discovery_action = cand.get("discovery_action", "UNKNOWN")
        priority_reason = cand.get("priority_reason", "")
        selection_reason = f"{diet_label}:{discovery_action}:{priority_reason}"

        is_same_token_new_pair = any(
            c["token_mint"] == mint and c["pair_count"] > 1
            for c in same_token_new_pair_cases
        )

        selected_candidates.append({
            "token_mint": mint,
            "pair_address": pair,
            "chain": cand.get("chain", "solana"),
            "memory_diet_label": diet_label,
            "selection_reason": selection_reason,
            "lifecycle_status": lifecycle_status,
            "is_revival": is_revival,
            "same_token_new_pair": is_same_token_new_pair,
            "discovery_action": discovery_action,
            "source_channel": cand.get("source_channel"),
        })

    # ------------------------------------------------------------------
    # 8. Forbidden table counts (read-only check — no writes occur)
    # ------------------------------------------------------------------
    forbidden_counts: dict[str, int] = {}
    if db_path is not None:
        try:
            forbidden_counts = _check_forbidden_tables(db_path)
        except Exception:
            forbidden_counts = {t: 0 for t in _FORBIDDEN_WRITE_TABLES}
    else:
        forbidden_counts = {t: 0 for t in _FORBIDDEN_WRITE_TABLES}

    finished_at = _utc_now()

    return {
        "command": LANE_X6_COMMAND_NAME,
        "lane_x6_status": LANE_X6_STATUS_COMPLETED,
        "operator_approved": operator_approved,
        "db_path": str(db_path) if db_path else "",
        "run_started_at": started_at,
        "run_finished_at": finished_at,
        "candidate_count_input": candidate_count_input,
        "mint_duplicates_collapsed": len(mint_collapsed),
        "pair_duplicates_collapsed": len(pair_collapsed),
        "same_token_new_pair_cases": len(same_token_new_pair_cases),
        "cooldown_blocked_count": len(cooldown_blocked),
        "selected_count": len(selected_candidates),
        "selected_candidates": selected_candidates,
        "dedup_report": {
            "mint_duplicates": [
                {
                    "token_mint": c.get("token_mint", ""),
                    "pair_address": c.get("pair_address", ""),
                    "collapse_reason": c.get("_collapse_reason", ""),
                }
                for c in mint_collapsed
            ],
            "pair_duplicates": [
                {
                    "token_mint": c.get("token_mint", ""),
                    "pair_address": c.get("pair_address", ""),
                    "collapse_reason": c.get("_collapse_reason", ""),
                }
                for c in pair_collapsed
            ],
            "same_token_new_pair_cases": same_token_new_pair_cases,
        },
        "cooldown_blocked": [
            {
                "token_mint": c.get("token_mint", ""),
                "blocked_reason": c.get("_blocked_reason", ""),
                "lifecycle_status": c.get("_lifecycle_status", ""),
            }
            for c in cooldown_blocked
        ],
        "memory_diet_summary": diet_summary,
        "max_candidates": max_candidates,
        "cooldown_aware": cooldown_aware,
        "include_revivals": include_revivals,
        "zero_candidates_is_valid": True,
        "discovery_is_intake_not_alpha": True,
        "selection_is_memory_value_based_not_buy_probability": True,
        "hard_locks": dict(_HARD_LOCKS),
        "buy_enabled": False,
        "sell_enabled": False,
        "hold_enabled": False,
        "paper_decisions_created": 0,
        "retrieval_rows_created": 0,
        "positions_created": 0,
        "trade_events_created": 0,
        "paper_trade_audits_created": 0,
        "pnl_created": 0,
        "forbidden_table_counts": forbidden_counts,
    }
