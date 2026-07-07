"""Lane X10.9 — Pre-Snapshot Freshness Revalidation Gate.

Read-only. No DB writes. No network calls. No Source Governor bypass.
No scoring, ranking, confidence, or weighted logic.

Freshness proof priority (per token-pair):
  1. Most recent governed source response with this pair_address in
     normalized_payload_json (printer_source_responses.received_at,
     filtered by source_status='COMPLETE')
  2. Most recent discovery candidate for the exact token + pair
     (printer_discovery_candidates.created_at via JOIN to printer_tokens
     and printer_pairs)
  3. captured_at inside normalized_candidate_payload_json of the discovery
     candidate, if present

TRACK_FAST policy:
  preferred max age : 120 seconds
  hard max age      : 180 seconds
  >180 seconds      → STALE_TRACK_FAST_BLOCKED
  no evidence       → FRESHNESS_UNKNOWN_BLOCKED

selected_at usage:
  May be included in the token list for traceability only.
  Does NOT constitute freshness proof.
  A stale token with a recent selected_at remains STALE_TRACK_FAST_BLOCKED.

Hard rules (inherited from V1):
  no_buy_sell_hold / no_paper_decisions / no_positions / no_pnl /
  no_retrieval_activation / no_live_trading / no_paid_api /
  no_source_governor_bypass / no_scoring_ranking_confidence /
  no_weighted_logic / no_live_source_fetching / no_db_writes_in_gate
"""

from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


# ---------------------------------------------------------------------------
# Policy constants
# ---------------------------------------------------------------------------

TRACK_FAST_PREFERRED_MAX_AGE_SECONDS: int = 120
TRACK_FAST_HARD_MAX_AGE_SECONDS: int = 180

# ---------------------------------------------------------------------------
# Status constants
# ---------------------------------------------------------------------------

FRESHNESS_STATUS_FRESH_PREFERRED: str = "FRESH_WITHIN_PREFERRED_LIMIT"
FRESHNESS_STATUS_FRESH_HARD: str = "FRESH_WITHIN_HARD_LIMIT"
FRESHNESS_STATUS_STALE_BLOCKED: str = "STALE_TRACK_FAST_BLOCKED"
FRESHNESS_STATUS_UNKNOWN_BLOCKED: str = "FRESHNESS_UNKNOWN_BLOCKED"

# ---------------------------------------------------------------------------
# Evidence type constants
# ---------------------------------------------------------------------------

EVIDENCE_SOURCE_RESPONSE: str = "source_response"
EVIDENCE_DISCOVERY_CANDIDATE: str = "discovery_candidate"
EVIDENCE_PAYLOAD_CAPTURED_AT: str = "payload_captured_at"
EVIDENCE_NONE: str = "none"


# ---------------------------------------------------------------------------
# FreshnessResult
# ---------------------------------------------------------------------------

@dataclass
class FreshnessResult:
    """Per-token freshness gate result. Immutable after construction."""
    mint: str
    pair_address: str
    slot: str
    status: str
    evidence_type: str
    freshness_timestamp: str | None
    age_seconds: int | None
    reason: str
    freshness_warning: bool

    def to_dict(self) -> dict[str, Any]:
        return {
            "mint": self.mint,
            "pair_address": self.pair_address,
            "slot": self.slot,
            "status": self.status,
            "evidence_type": self.evidence_type,
            "freshness_timestamp": self.freshness_timestamp,
            "age_seconds": self.age_seconds,
            "reason": self.reason,
            "freshness_warning": self.freshness_warning,
        }


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _parse_utc(ts: str | None) -> datetime | None:
    """Parse an ISO or SQLite timestamp to a UTC-aware datetime."""
    if not ts:
        return None
    try:
        dt = datetime.fromisoformat(ts.strip())
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt
    except (ValueError, TypeError):
        return None


def _age_seconds(ts: datetime, now: datetime) -> int:
    """Return non-negative integer seconds between ts and now."""
    return max(0, int((now - ts).total_seconds()))


def _status_from_age(age_s: int) -> tuple[str, bool]:
    """Return (status, freshness_warning) for a given age in seconds."""
    if age_s <= TRACK_FAST_PREFERRED_MAX_AGE_SECONDS:
        return FRESHNESS_STATUS_FRESH_PREFERRED, False
    if age_s <= TRACK_FAST_HARD_MAX_AGE_SECONDS:
        return FRESHNESS_STATUS_FRESH_HARD, True
    return FRESHNESS_STATUS_STALE_BLOCKED, True


def _query_source_response(
    conn: sqlite3.Connection,
    pair_address: str,
) -> str | None:
    """Return the most recent received_at for a COMPLETE source response
    whose normalized_payload_json contains pair_address.

    Read-only. No DB writes. No network calls.
    Solana base58 pair addresses are sufficiently unique substrings —
    false positives from the LIKE match are not possible in practice.
    """
    try:
        row = conn.execute(
            """
            SELECT received_at
            FROM printer_source_responses
            WHERE normalized_payload_json LIKE ?
              AND source_status = 'COMPLETE'
            ORDER BY received_at DESC
            LIMIT 1
            """,
            (f"%{pair_address}%",),
        ).fetchone()
        return str(row[0]) if row and row[0] else None
    except sqlite3.OperationalError:
        return None


def _query_discovery_candidate(
    conn: sqlite3.Connection,
    mint: str,
    pair_address: str,
) -> tuple[str | None, str | None]:
    """Return (created_at, normalized_candidate_payload_json) for the most
    recent discovery candidate matching the exact mint + pair_address.

    Read-only. No DB writes. No network calls.
    """
    try:
        row = conn.execute(
            """
            SELECT dc.created_at, dc.normalized_candidate_payload_json
            FROM printer_discovery_candidates dc
            JOIN printer_tokens pt ON pt.id = dc.token_id
            JOIN printer_pairs pp ON pp.id = dc.pair_id
            WHERE pt.token_mint = ?
              AND pp.pair_address = ?
            ORDER BY dc.created_at DESC
            LIMIT 1
            """,
            (mint, pair_address),
        ).fetchone()
        if row is None:
            return None, None
        return (str(row[0]) if row[0] else None), (str(row[1]) if row[1] else None)
    except sqlite3.OperationalError:
        return None, None


def _extract_captured_at(payload_json: str | None) -> str | None:
    """Extract the captured_at field from a normalized candidate JSON blob."""
    if not payload_json:
        return None
    try:
        payload = json.loads(payload_json)
        val = payload.get("captured_at")
        return str(val) if val else None
    except (json.JSONDecodeError, TypeError):
        return None


def _make_result_from_age(
    mint: str,
    pair_address: str,
    slot: str,
    age_s: int,
    ts_str: str,
    evidence_type: str,
    field_name: str,
) -> FreshnessResult:
    status, warning = _status_from_age(age_s)
    if status == FRESHNESS_STATUS_FRESH_PREFERRED:
        detail = f"<= {TRACK_FAST_PREFERRED_MAX_AGE_SECONDS}s preferred limit"
    elif status == FRESHNESS_STATUS_FRESH_HARD:
        detail = (
            f"> {TRACK_FAST_PREFERRED_MAX_AGE_SECONDS}s but"
            f" <= {TRACK_FAST_HARD_MAX_AGE_SECONDS}s hard limit"
        )
    else:
        detail = (
            f"> {TRACK_FAST_HARD_MAX_AGE_SECONDS}s hard limit;"
            " re-run discovery or revalidate before X5"
        )
    reason = f"{field_name}={ts_str} age={age_s}s; {detail}"
    return FreshnessResult(
        mint=mint,
        pair_address=pair_address,
        slot=slot,
        status=status,
        evidence_type=evidence_type,
        freshness_timestamp=ts_str,
        age_seconds=age_s,
        reason=reason,
        freshness_warning=warning,
    )


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def check_token_freshness(
    mint: str,
    pair_address: str,
    slot: str,
    db_path: str | Path,
    *,
    now: datetime | None = None,
) -> FreshnessResult:
    """Check freshness for a single TRACK_FAST token-pair.

    Evidence is queried in priority order (source_response → discovery_candidate
    created_at → payload captured_at). The most recent timestamp found is used.
    selected_at is never queried and never accepted as freshness evidence.

    Read-only. No DB writes. No network calls. No source governor access.
    """
    if now is None:
        now = datetime.now(timezone.utc)

    if not mint or not pair_address:
        return FreshnessResult(
            mint=mint,
            pair_address=pair_address,
            slot=slot,
            status=FRESHNESS_STATUS_UNKNOWN_BLOCKED,
            evidence_type=EVIDENCE_NONE,
            freshness_timestamp=None,
            age_seconds=None,
            reason="mint or pair_address is empty; cannot verify freshness",
            freshness_warning=True,
        )

    try:
        conn = sqlite3.connect(str(db_path))
        try:
            sr_ts = _query_source_response(conn, pair_address)
            dc_created_at, dc_payload_json = _query_discovery_candidate(conn, mint, pair_address)
        finally:
            conn.close()
    except Exception as exc:
        return FreshnessResult(
            mint=mint,
            pair_address=pair_address,
            slot=slot,
            status=FRESHNESS_STATUS_UNKNOWN_BLOCKED,
            evidence_type=EVIDENCE_NONE,
            freshness_timestamp=None,
            age_seconds=None,
            reason=f"DB read error: {exc}",
            freshness_warning=True,
        )

    dc_captured_at = _extract_captured_at(dc_payload_json)

    # Priority 1: most recent source response received_at
    if sr_ts:
        dt = _parse_utc(sr_ts)
        if dt is not None:
            return _make_result_from_age(
                mint, pair_address, slot,
                _age_seconds(dt, now), sr_ts,
                EVIDENCE_SOURCE_RESPONSE, "source_response.received_at",
            )

    # Priority 2: discovery candidate created_at
    if dc_created_at:
        dt = _parse_utc(dc_created_at)
        if dt is not None:
            return _make_result_from_age(
                mint, pair_address, slot,
                _age_seconds(dt, now), dc_created_at,
                EVIDENCE_DISCOVERY_CANDIDATE, "discovery_candidate.created_at",
            )

    # Priority 3: captured_at inside normalized payload
    if dc_captured_at:
        dt = _parse_utc(dc_captured_at)
        if dt is not None:
            return _make_result_from_age(
                mint, pair_address, slot,
                _age_seconds(dt, now), dc_captured_at,
                EVIDENCE_PAYLOAD_CAPTURED_AT, "payload.captured_at",
            )

    # No evidence found
    return FreshnessResult(
        mint=mint,
        pair_address=pair_address,
        slot=slot,
        status=FRESHNESS_STATUS_UNKNOWN_BLOCKED,
        evidence_type=EVIDENCE_NONE,
        freshness_timestamp=None,
        age_seconds=None,
        reason=(
            f"no freshness evidence for mint={mint} pair={pair_address};"
            " no source_response.received_at, no discovery_candidate.created_at,"
            " no payload.captured_at; re-run discovery before X5"
        ),
        freshness_warning=True,
    )


def check_token_list_freshness(
    tokens: list[dict[str, Any]],
    db_path: str | Path,
    *,
    now: datetime | None = None,
) -> list[FreshnessResult]:
    """Check freshness for all tokens in a list.

    Each token dict must contain: mint, pair_address, slot.
    Returns one FreshnessResult per token, in input order.

    Read-only. No DB writes. No network calls. No source calls.
    """
    if now is None:
        now = datetime.now(timezone.utc)
    return [
        check_token_freshness(
            mint=str(tok.get("mint", "")),
            pair_address=str(tok.get("pair_address", "")),
            slot=str(tok.get("slot", "")),
            db_path=db_path,
            now=now,
        )
        for tok in tokens
    ]
