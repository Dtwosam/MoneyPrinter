"""Lane X10.6 — Discovery Selection Traceability + Smart Memory-Value Selection.

Builds on Lane X6 (dedup / diet-label / cooldown-aware selection) by adding:

1. Qualitative event-kind classification — explains *what memory event* a
   candidate represents (MICRO_CAP_FAST_EVENT, MIGRATION_EVENT, …).
   These are NOT scores, ranks, confidence values, or BUY signals.

2. Context tags — one or more risk/context labels per candidate
   (MICRO_CAP, THIN_LIQUIDITY, HIGH_VOLATILITY, …).
   Tags do not block selection by themselves; they exist for traceability.

3. Market-cap neutrality — micro-cap tokens can qualify for TRACK_FAST when
   activity/liquidity/pair evidence makes them worth capturing quickly.
   Large-cap tokens with no active event can be WATCH_ONLY or TRACK_NORMAL.
   Neither cap level is automatically TRACK_FAST.

4. Manual override gating — WATCH_ONLY-to-TRACK_FAST, no-discovery-origin,
   and pair-drift cases require explicit operator override reason fields.

5. Pair drift explicit acknowledgment — a candidate flagged for pair drift
   must carry pair_drift_acknowledged=True and a manual_override_reason.

6. Selection batch artifact — a structured output linking discovery candidate
   IDs, selected token mints, event kinds, context tags, source trace IDs,
   memory-diet labels, manual overrides, operator approvals, and the optional
   output token-list path.

7. Balance preference — the batch report notes whether the selection covers
   multiple event-kind categories. If not enough candidates exist to cover
   all categories, the report says so rather than forcing artificial diversity.

Hard rules (unchanged from Lane X6):
- No BUY / SELL / HOLD. No paper decisions. No positions. No PnL.
- No retrieval activation.
- No scoring / ranking / confidence / weighted logic.
- No Source Governor bypass. No Central Scheduler bypass.
- No live source fetching in this module.
- No wallet / private keys. No live trading. No paid APIs.
- No discovery automation (discovery remains intake, not alpha).
- Operator approval required.
- Zero selected candidates is a valid outcome.
- Selection is memory-value based, not BUY-probability based.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any


LANE_X10_6_STATUS_COMPLETED: str = "LANE_X10_6_COMPLETED"
LANE_X10_6_STATUS_BLOCKED: str = "LANE_X10_6_BLOCKED"

# ---------------------------------------------------------------------------
# Qualitative event-kind labels (NOT scores, NOT buy signals)
# ---------------------------------------------------------------------------

EVENT_MICRO_CAP_FAST_EVENT: str = "MICRO_CAP_FAST_EVENT"
EVENT_MIGRATION_EVENT: str = "MIGRATION_EVENT"
EVENT_NEW_PAIR_EVENT: str = "NEW_PAIR_EVENT"
EVENT_LIQUIDITY_DECAY_EVENT: str = "LIQUIDITY_DECAY_EVENT"
EVENT_HIGH_ACTIVITY_NO_FOLLOW_THROUGH: str = "HIGH_ACTIVITY_NO_FOLLOW_THROUGH"
EVENT_REVIVAL_EVENT: str = "REVIVAL_EVENT"
EVENT_HOT_PAIR_REFERENCE: str = "HOT_PAIR_REFERENCE"
EVENT_SOCIAL_ATTENTION_ADVISORY: str = "SOCIAL_ATTENTION_ADVISORY"
EVENT_SAFETY_RISK_MEMORY: str = "SAFETY_RISK_MEMORY"
EVENT_AMBIGUOUS_MEMORY_CANDIDATE: str = "AMBIGUOUS_MEMORY_CANDIDATE"

ALL_EVENT_KINDS: tuple[str, ...] = (
    EVENT_MICRO_CAP_FAST_EVENT,
    EVENT_MIGRATION_EVENT,
    EVENT_NEW_PAIR_EVENT,
    EVENT_LIQUIDITY_DECAY_EVENT,
    EVENT_HIGH_ACTIVITY_NO_FOLLOW_THROUGH,
    EVENT_REVIVAL_EVENT,
    EVENT_HOT_PAIR_REFERENCE,
    EVENT_SOCIAL_ATTENTION_ADVISORY,
    EVENT_SAFETY_RISK_MEMORY,
    EVENT_AMBIGUOUS_MEMORY_CANDIDATE,
)

# Broad balance groups (used for batch balance assessment, not selection gating)
_EVENT_GROUP_LIQUID_REFERENCE = frozenset({EVENT_HOT_PAIR_REFERENCE})
_EVENT_GROUP_FAST_MICRO = frozenset({EVENT_MICRO_CAP_FAST_EVENT, EVENT_NEW_PAIR_EVENT, EVENT_MIGRATION_EVENT})
_EVENT_GROUP_RISK_DECAY = frozenset({EVENT_SAFETY_RISK_MEMORY, EVENT_LIQUIDITY_DECAY_EVENT, EVENT_HIGH_ACTIVITY_NO_FOLLOW_THROUGH})
_EVENT_GROUP_AMBIGUOUS = frozenset({EVENT_AMBIGUOUS_MEMORY_CANDIDATE, EVENT_SOCIAL_ATTENTION_ADVISORY, EVENT_REVIVAL_EVENT})

# ---------------------------------------------------------------------------
# Context tags (risk / market context labels — NOT scores, NOT blocking alone)
# ---------------------------------------------------------------------------

TAG_MICRO_CAP: str = "MICRO_CAP"
TAG_THIN_LIQUIDITY: str = "THIN_LIQUIDITY"
TAG_EXIT_REALISM_UNKNOWN: str = "EXIT_REALISM_UNKNOWN"
TAG_HIGH_VOLATILITY: str = "HIGH_VOLATILITY"
TAG_POSSIBLE_WICK_PUMP: str = "POSSIBLE_WICK_PUMP"
TAG_POSSIBLE_LATE_BUY_TRAP: str = "POSSIBLE_LATE_BUY_TRAP"
TAG_POSSIBLE_SNIPER_OR_BUNDLE_RISK: str = "POSSIBLE_SNIPER_OR_BUNDLE_RISK"
TAG_HOLDER_CONCENTRATION_RISK: str = "HOLDER_CONCENTRATION_RISK"

ALL_CONTEXT_TAGS: tuple[str, ...] = (
    TAG_MICRO_CAP,
    TAG_THIN_LIQUIDITY,
    TAG_EXIT_REALISM_UNKNOWN,
    TAG_HIGH_VOLATILITY,
    TAG_POSSIBLE_WICK_PUMP,
    TAG_POSSIBLE_LATE_BUY_TRAP,
    TAG_POSSIBLE_SNIPER_OR_BUNDLE_RISK,
    TAG_HOLDER_CONCENTRATION_RISK,
)

# ---------------------------------------------------------------------------
# Market-cap thresholds for context tagging (NOT selection gates)
# ---------------------------------------------------------------------------

_DEFAULT_MICRO_CAP_FDV_THRESHOLD: float = 500_000.0   # USD FDV
_DEFAULT_THIN_LIQUIDITY_THRESHOLD: float = 5_000.0    # USD liquidity
_DEFAULT_HIGH_VOL_5M_THRESHOLD: float = 30.0           # 5m price % change
_DEFAULT_HIGH_VOL_1H_THRESHOLD: float = 80.0           # 1h price % change

_HARD_LOCKS: dict[str, bool] = {
    "no_buy_sell_hold": True,
    "no_paper_decisions": True,
    "no_positions": True,
    "no_pnl": True,
    "no_retrieval_activation": True,
    "no_live_trading": True,
    "no_paid_api": True,
    "no_wallet_private_key": True,
    "no_scoring_ranking_confidence": True,
    "no_weighted_logic": True,
    "no_source_governor_bypass": True,
    "no_central_scheduler_bypass": True,
    "no_discovery_automation": True,
    "no_live_source_fetching": True,
    "no_embeddings_vectors": True,
    "no_1h_4h_12h_24h_collection": True,
    "no_5m_main_window": True,
    "no_trade_events": True,
    "no_paper_trade_audits": True,
    "no_token_pair_mixing": True,
}


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


# ---------------------------------------------------------------------------
# Context tag classification (deterministic, no scoring)
# ---------------------------------------------------------------------------

def classify_context_tags(
    candidate: dict[str, Any],
    *,
    micro_cap_fdv_threshold: float = _DEFAULT_MICRO_CAP_FDV_THRESHOLD,
    thin_liquidity_threshold: float = _DEFAULT_THIN_LIQUIDITY_THRESHOLD,
) -> list[str]:
    """Return a list of context tags applicable to this candidate.

    Tags are deterministic, based on observed field values.
    Multiple tags may apply. Tags do not block selection by themselves.
    They are for traceability, operator audit, and memory-diet context.
    """
    tags: list[str] = []

    fdv = _float_or_zero(candidate.get("fdv_usd") or candidate.get("market_cap_usd"))
    liquidity = _float_or_zero(candidate.get("liquidity_usd"))
    price_5m = _float_or_zero(candidate.get("price_change_5m"))
    price_1h = _float_or_zero(candidate.get("price_change_1h"))
    price_24h = _float_or_zero(candidate.get("price_change_24h"))

    # MICRO_CAP — FDV below threshold (context, not a block)
    if 0 < fdv < micro_cap_fdv_threshold:
        tags.append(TAG_MICRO_CAP)

    # THIN_LIQUIDITY — liquidity below threshold or absent
    if liquidity < thin_liquidity_threshold:
        tags.append(TAG_THIN_LIQUIDITY)

    # EXIT_REALISM_UNKNOWN — no liquidity data at all
    if liquidity <= 0:
        tags.append(TAG_EXIT_REALISM_UNKNOWN)

    # HIGH_VOLATILITY — large price move in either direction in recent periods
    if abs(price_5m) > _DEFAULT_HIGH_VOL_5M_THRESHOLD or abs(price_1h) > _DEFAULT_HIGH_VOL_1H_THRESHOLD:
        tags.append(TAG_HIGH_VOLATILITY)

    # POSSIBLE_WICK_PUMP — large 5m spike that did NOT persist into 1h
    if price_5m > 30.0 and abs(price_1h) < 10.0:
        tags.append(TAG_POSSIBLE_WICK_PUMP)

    # POSSIBLE_LATE_BUY_TRAP — already moved very large over 24h
    if price_24h > 200.0:
        tags.append(TAG_POSSIBLE_LATE_BUY_TRAP)

    # POSSIBLE_SNIPER_OR_BUNDLE_RISK — operator-supplied flag
    if candidate.get("possible_sniper_or_bundle_risk") is True:
        tags.append(TAG_POSSIBLE_SNIPER_OR_BUNDLE_RISK)

    # HOLDER_CONCENTRATION_RISK — operator-supplied flag
    if candidate.get("holder_concentration_risk") is True:
        tags.append(TAG_HOLDER_CONCENTRATION_RISK)

    return tags


# ---------------------------------------------------------------------------
# Event-kind classification (deterministic, no scoring)
# ---------------------------------------------------------------------------

def classify_event_kind(
    candidate: dict[str, Any],
    *,
    micro_cap_fdv_threshold: float = _DEFAULT_MICRO_CAP_FDV_THRESHOLD,
) -> str:
    """Classify candidate into an event-kind label.

    The event-kind describes *what type of memory event* the candidate
    represents, NOT its likelihood to produce a profitable trade.
    No scores, no ranks, no confidence values, no BUY signals.

    Priority order (first matching rule wins):
    1. SAFETY_RISK_MEMORY      — operator flagged as unsafe/safety risk
    2. REVIVAL_EVENT           — cooled/dead token with new activity
    3. MIGRATION_EVENT         — pair_is_migration flag or source channel says so
    4. NEW_PAIR_EVENT          — same-token new-pair case
    5. MICRO_CAP_FAST_EVENT    — micro-cap token with meaningful fast activity
    6. HIGH_ACTIVITY_NO_FOLLOW_THROUGH — high txns/vol but no sustained price
    7. LIQUIDITY_DECAY_EVENT   — liquidity dropping or thin with no volume
    8. HOT_PAIR_REFERENCE      — high fdv / well-known reference token
    9. SOCIAL_ATTENTION_ADVISORY — operator-flagged social attention
    10. AMBIGUOUS_MEMORY_CANDIDATE — fallback
    """
    # Safety risk — operator-supplied
    if candidate.get("safety_risk") is True or candidate.get("is_safety_risk_memory") is True:
        return EVENT_SAFETY_RISK_MEMORY

    # Revival — was previously cooled/dead, now active again
    is_revival = candidate.get("is_revival") is True or (
        candidate.get("_lifecycle_status") == "QUEUED"
        and candidate.get("_was_cooled") is True
    )
    if is_revival:
        return EVENT_REVIVAL_EVENT

    # Migration — explicit flag or source-channel hint
    source_channel = str(candidate.get("source_channel") or "").upper()
    if (
        candidate.get("pair_is_migration") is True
        or "MIGRATION" in source_channel
        or "PUMPSWAP" in source_channel
    ):
        return EVENT_MIGRATION_EVENT

    # New pair for existing token
    if candidate.get("same_token_new_pair") is True or candidate.get("is_new_pair_for_existing_token") is True:
        return EVENT_NEW_PAIR_EVENT

    fdv = _float_or_zero(candidate.get("fdv_usd") or candidate.get("market_cap_usd"))
    liquidity = _float_or_zero(candidate.get("liquidity_usd"))
    price_5m = _float_or_zero(candidate.get("price_change_5m"))
    price_1h = _float_or_zero(candidate.get("price_change_1h"))
    vol_5m = _float_or_zero(candidate.get("volume_5m"))
    vol_1h = _float_or_zero(candidate.get("volume_1h"))
    vol_24h = _float_or_zero(candidate.get("volume_24h"))
    txns_5m = _int_or_zero(candidate.get("txns_5m"))
    txns_1h = _int_or_zero(candidate.get("txns_1h"))

    # Micro-cap with a fast, observable event worth capturing
    is_micro = 0 < fdv < micro_cap_fdv_threshold
    has_fast_activity = (
        (abs(price_5m) > 15.0 and txns_5m > 5 and vol_5m > 500.0)
        or (abs(price_1h) > 30.0 and txns_1h > 10 and vol_1h > 1_000.0)
    )
    if is_micro and has_fast_activity:
        return EVENT_MICRO_CAP_FAST_EVENT

    # High activity but price did not follow through (trap or sell pressure memory)
    high_txns = txns_5m > 30 or txns_1h > 100
    no_price_follow = abs(price_5m) < 10.0 and abs(price_1h) < 15.0
    if high_txns and no_price_follow and vol_1h > 2_000.0:
        return EVENT_HIGH_ACTIVITY_NO_FOLLOW_THROUGH

    # Liquidity decay
    is_thin = liquidity < _DEFAULT_THIN_LIQUIDITY_THRESHOLD
    volume_absent = vol_24h < 500.0
    if is_thin and volume_absent and liquidity > 0:
        return EVENT_LIQUIDITY_DECAY_EVENT

    # Hot pair / large reference token (useful for baseline comparison memory)
    is_large = fdv >= micro_cap_fdv_threshold * 10
    if is_large:
        return EVENT_HOT_PAIR_REFERENCE

    # Social attention advisory — operator-supplied flag only
    if candidate.get("social_attention_advisory") is True:
        return EVENT_SOCIAL_ATTENTION_ADVISORY

    return EVENT_AMBIGUOUS_MEMORY_CANDIDATE


# ---------------------------------------------------------------------------
# Manual override validation
# ---------------------------------------------------------------------------

def validate_manual_override(
    candidate: dict[str, Any],
) -> tuple[bool, str | None]:
    """Check whether a candidate requires a manual override and if it is present.

    Returns (override_required, missing_reason).
    If override_required=False, missing_reason is None.
    If override_required=True and the override is correctly populated,
    missing_reason is None.
    If override_required=True and the override is missing, missing_reason
    explains what is absent.
    """
    requires_override = False
    missing: list[str] = []

    # Detect WATCH_ONLY→TRACK_FAST from explicit flag OR from lane field mismatch.
    is_watch_only_upgrade = (
        candidate.get("watch_only_to_track_fast_override") is True
        or (
            str(candidate.get("db_lane_before_selection") or "").upper() == "WATCH_ONLY"
            and str(candidate.get("selected_lane_for_batch") or "").upper() == "TRACK_FAST"
        )
    )
    no_discovery_origin = candidate.get("no_discovery_origin") is True
    has_pair_drift = (
        candidate.get("pair_drift_acknowledged") is True
        or candidate.get("same_token_new_pair") is True
        or candidate.get("is_new_pair_for_existing_token") is True
    )

    if is_watch_only_upgrade or no_discovery_origin or has_pair_drift:
        requires_override = True

    if requires_override:
        if not candidate.get("manual_override"):
            missing.append("manual_override must be True")
        if not candidate.get("manual_override_reason"):
            missing.append("manual_override_reason must be set")
        if has_pair_drift and not candidate.get("pair_drift_acknowledged"):
            missing.append("pair_drift_acknowledged must be True when pair drift is present")

    if missing:
        return requires_override, "; ".join(missing)
    return requires_override, None


# ---------------------------------------------------------------------------
# Batch balance assessment
# ---------------------------------------------------------------------------

def assess_batch_balance(
    selected: list[dict[str, Any]],
) -> dict[str, Any]:
    """Assess whether the selected batch covers multiple event-kind groups.

    Returns a summary with:
    - count by event_kind
    - group coverage (which broad groups are represented)
    - balance_note: describes any coverage gaps
    - is_balanced: True if all 4 broad groups have ≥ 1 candidate

    This is informational only. An unbalanced batch is not automatically
    rejected — the operator decides whether to add candidates.
    """
    event_counts: dict[str, int] = {ek: 0 for ek in ALL_EVENT_KINDS}
    for cand in selected:
        ek = cand.get("event_kind", EVENT_AMBIGUOUS_MEMORY_CANDIDATE)
        event_counts[ek] = event_counts.get(ek, 0) + 1

    selected_kinds = {ek for ek, cnt in event_counts.items() if cnt > 0}

    has_liquid_ref = bool(selected_kinds & _EVENT_GROUP_LIQUID_REFERENCE)
    has_fast_micro = bool(selected_kinds & _EVENT_GROUP_FAST_MICRO)
    has_risk_decay = bool(selected_kinds & _EVENT_GROUP_RISK_DECAY)
    has_ambiguous = bool(selected_kinds & _EVENT_GROUP_AMBIGUOUS)

    is_balanced = has_liquid_ref and has_fast_micro and has_risk_decay and has_ambiguous

    gaps: list[str] = []
    if not has_liquid_ref:
        gaps.append("no liquid/reference candidate (HOT_PAIR_REFERENCE)")
    if not has_fast_micro:
        gaps.append("no micro/fast-event candidate (MICRO_CAP_FAST_EVENT, NEW_PAIR_EVENT, MIGRATION_EVENT)")
    if not has_risk_decay:
        gaps.append("no risk/decay candidate (SAFETY_RISK_MEMORY, LIQUIDITY_DECAY_EVENT, HIGH_ACTIVITY_NO_FOLLOW_THROUGH)")
    if not has_ambiguous:
        gaps.append("no ambiguous/advisory candidate (AMBIGUOUS_MEMORY_CANDIDATE, SOCIAL_ATTENTION_ADVISORY, REVIVAL_EVENT)")

    if is_balanced:
        balance_note = "batch covers all four event-kind groups"
    elif not selected:
        balance_note = "no candidates selected; batch is empty but valid"
    else:
        balance_note = "gaps present: " + "; ".join(gaps)

    return {
        "event_kind_counts": event_counts,
        "has_liquid_reference": has_liquid_ref,
        "has_fast_micro_event": has_fast_micro,
        "has_risk_decay_event": has_risk_decay,
        "has_ambiguous_advisory": has_ambiguous,
        "is_balanced": is_balanced,
        "balance_note": balance_note,
        "coverage_gaps": gaps,
    }


# ---------------------------------------------------------------------------
# Blocked result helper
# ---------------------------------------------------------------------------

def _blocked_result(
    reasons: list[str],
    *,
    db_path: str = "",
    operator_approved: bool = False,
) -> dict[str, Any]:
    return {
        "lane_x10_6_status": LANE_X10_6_STATUS_BLOCKED,
        "blocked_reasons": reasons,
        "operator_approved": operator_approved,
        "db_path": db_path,
        "selected_count": 0,
        "rejected_count": 0,
        "override_required_count": 0,
        "override_missing_count": 0,
        "pair_drift_pending_acknowledgment": 0,
        "selected_candidates": [],
        "rejected_candidates": [],
        "manual_overrides": [],
        "pair_drift_items": [],
        "batch_balance": assess_batch_balance([]),
        "event_kind_summary": {ek: 0 for ek in ALL_EVENT_KINDS},
        "automated_selection_locked": True,
        "discovery_is_intake_not_alpha": True,
        "selection_is_memory_value_based_not_buy_probability": True,
        "hard_locks": dict(_HARD_LOCKS),
        "buy_enabled": False,
        "sell_enabled": False,
        "hold_enabled": False,
        "paper_decisions_created": 0,
        "positions_created": 0,
        "trade_events_created": 0,
        "pnl_created": 0,
        "run_started_at": _utc_now(),
        "run_finished_at": _utc_now(),
    }


# ---------------------------------------------------------------------------
# Main public function
# ---------------------------------------------------------------------------

def _compute_candidate_age_seconds(
    candidate_ts_str: str | None,
    batch_started_dt: datetime | None,
) -> int | None:
    """Compute candidate age in seconds relative to batch start. Read-only."""
    if not candidate_ts_str or batch_started_dt is None:
        return None
    try:
        dt = datetime.fromisoformat(candidate_ts_str.strip())
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return max(0, int((batch_started_dt - dt).total_seconds()))
    except (ValueError, TypeError):
        return None


def _freshness_advisory_from_age(age_s: int | None) -> str:
    """Return a freshness advisory label for traceability (not a gate)."""
    if age_s is None:
        return "FRESHNESS_UNKNOWN"
    if age_s <= 120:
        return "FRESH_PREFERRED"
    if age_s <= 180:
        return "FRESH_WITHIN_HARD_LIMIT"
    return "STALE_AT_SELECTION_TIME"


def build_selection_batch(
    db_path: str | None,
    backup_proof_path: str | None,
    *,
    operator_approved: bool = False,
    candidate_list_override: list[dict[str, Any]] | None = None,
    proposed_x5_token_list_path: str | None = None,
    micro_cap_fdv_threshold: float = _DEFAULT_MICRO_CAP_FDV_THRESHOLD,
    thin_liquidity_threshold: float = _DEFAULT_THIN_LIQUIDITY_THRESHOLD,
) -> dict[str, Any]:
    """Build a traceable selection batch artifact for a bounded X5 run.

    Each candidate in the batch receives:
    - event_kind: qualitative event label (NOT a score)
    - context_tags: list of risk/context labels
    - inclusion_reason: human-readable inclusion justification
    - rejection_reason: set if candidate is rejected
    - manual_override: True/False (required for WATCH_ONLY→TRACK_FAST, no-origin, pair-drift)
    - manual_override_reason: required string when manual_override=True
    - watch_only_to_track_fast_override: True if DB lane was WATCH_ONLY
    - no_discovery_origin: True if no discovery candidate row exists
    - pair_drift_acknowledged: True if pair drift is present AND operator confirmed
    - db_lane_before_selection: the lane from the discovery/tracking DB
    - selected_lane_for_batch: the lane the operator is selecting this token for
    - source_trace: dict with discovery_candidate_id, source_request_id, source_response_id

    Parameters
    ----------
    db_path:
        Path to Printer V1 SQLite database. Required (may be ignored when
        candidate_list_override is supplied, but must still be a non-empty
        string for the operator-proof check).
    backup_proof_path:
        Path to an existing backup file (operator proof that backup was taken).
    operator_approved:
        Must be True. Gate prevents accidental runs.
    candidate_list_override:
        When provided, used instead of a live DB read. Each entry is a dict
        that may include any of: token_mint, pair_address, chain, fdv_usd,
        market_cap_usd, liquidity_usd, price_change_5m, price_change_1h,
        price_change_24h, volume_5m, volume_1h, volume_24h, txns_5m,
        txns_1h, txns_24h, discovery_action, priority_reason, source_channel,
        _db_candidate_id, source_request_id, source_response_id,
        watch_only_to_track_fast_override, no_discovery_origin,
        pair_drift_acknowledged, manual_override, manual_override_reason,
        db_lane_before_selection, selected_lane_for_batch, is_revival,
        safety_risk, social_attention_advisory, pair_is_migration,
        same_token_new_pair, is_new_pair_for_existing_token,
        possible_sniper_or_bundle_risk, holder_concentration_risk.
    proposed_x5_token_list_path:
        Optional path to an existing operator-supplied X5 JSON token-list
        file. Recorded in the output for traceability; not read in this call.
    micro_cap_fdv_threshold:
        FDV below which a token is context-tagged MICRO_CAP. Default 500k USD.
    thin_liquidity_threshold:
        Liquidity below which a token is context-tagged THIN_LIQUIDITY.
        Default 5k USD.
    """
    started_at = _utc_now()

    # Parse batch start time for per-candidate age computation (traceability only).
    try:
        _batch_started_dt: datetime | None = datetime.fromisoformat(started_at)
        if _batch_started_dt.tzinfo is None:  # type: ignore[union-attr]
            _batch_started_dt = _batch_started_dt.replace(tzinfo=timezone.utc)
    except (ValueError, TypeError):
        _batch_started_dt = None

    blocked_reasons: list[str] = []

    if not operator_approved:
        blocked_reasons.append("operator_approved is required")

    if not db_path:
        blocked_reasons.append("db_path is required")

    if backup_proof_path is None:
        blocked_reasons.append("backup_proof_path is required")

    if blocked_reasons:
        return _blocked_result(blocked_reasons, db_path=str(db_path or ""), operator_approved=operator_approved)

    # Resolve candidates
    raw: list[dict[str, Any]] = [dict(c) for c in (candidate_list_override or [])]

    selected_candidates: list[dict[str, Any]] = []
    rejected_candidates: list[dict[str, Any]] = []
    manual_overrides: list[dict[str, Any]] = []
    pair_drift_items: list[dict[str, Any]] = []
    event_kind_summary: dict[str, int] = {ek: 0 for ek in ALL_EVENT_KINDS}
    override_missing_count = 0

    for raw_cand in raw:
        mint = raw_cand.get("token_mint", "")
        pair = raw_cand.get("pair_address", "")

        # Classify event kind and context tags
        event_kind = classify_event_kind(
            raw_cand,
            micro_cap_fdv_threshold=micro_cap_fdv_threshold,
        )
        context_tags = classify_context_tags(
            raw_cand,
            micro_cap_fdv_threshold=micro_cap_fdv_threshold,
            thin_liquidity_threshold=thin_liquidity_threshold,
        )

        # Source trace
        source_trace: dict[str, Any] = {
            "discovery_candidate_id": raw_cand.get("_db_candidate_id"),
            "source_request_id": raw_cand.get("source_request_id"),
            "source_response_id": raw_cand.get("source_response_id"),
            "source_channel": raw_cand.get("source_channel"),
            "priority_reason": raw_cand.get("priority_reason"),
        }

        # Freshness traceability fields (advisory only — no blocking in X10.6)
        _cand_ts = raw_cand.get("created_at") or raw_cand.get("captured_at")
        _cand_age_s = _compute_candidate_age_seconds(_cand_ts, _batch_started_dt)
        _freshness_advisory = _freshness_advisory_from_age(_cand_age_s)

        # Manual override validation
        override_required, override_missing = validate_manual_override(raw_cand)
        has_override = bool(raw_cand.get("manual_override"))
        manual_override_reason = raw_cand.get("manual_override_reason", "")

        # Pair drift handling
        has_pair_drift = (
            raw_cand.get("pair_drift_acknowledged") is True
            or raw_cand.get("same_token_new_pair") is True
            or raw_cand.get("is_new_pair_for_existing_token") is True
        )
        drift_acknowledged = raw_cand.get("pair_drift_acknowledged") is True

        if has_pair_drift:
            pair_drift_items.append({
                "token_mint": mint,
                "pair_address": pair,
                "pair_drift_acknowledged": drift_acknowledged,
                "manual_override": has_override,
                "manual_override_reason": manual_override_reason,
            })

        # Build the candidate record
        cand_record: dict[str, Any] = {
            "token_mint": mint,
            "pair_address": pair,
            "chain": raw_cand.get("chain", "solana"),
            "event_kind": event_kind,
            "context_tags": context_tags,
            "discovery_action": raw_cand.get("discovery_action", "UNKNOWN"),
            "db_lane_before_selection": raw_cand.get("db_lane_before_selection") or raw_cand.get("discovery_action", "UNKNOWN"),
            "selected_lane_for_batch": raw_cand.get("selected_lane_for_batch", "TRACK_FAST"),
            "manual_override": has_override,
            "manual_override_reason": manual_override_reason,
            "watch_only_to_track_fast_override": bool(raw_cand.get("watch_only_to_track_fast_override")),
            "no_discovery_origin": bool(raw_cand.get("no_discovery_origin")),
            "pair_drift_acknowledged": drift_acknowledged,
            "operator_approved": operator_approved,
            "source_trace": source_trace,
            "candidate_age_at_selection_seconds": _cand_age_s,
            "freshness_advisory": _freshness_advisory,
        }

        # Reject: override required but missing
        if override_required and override_missing:
            override_missing_count += 1
            rejected_candidates.append({
                **cand_record,
                "included": False,
                "rejection_reason": f"manual_override_required: {override_missing}",
                "inclusion_reason": None,
            })
            continue

        # Reject: pair drift present but not acknowledged
        if has_pair_drift and not drift_acknowledged and not has_override:
            rejected_candidates.append({
                **cand_record,
                "included": False,
                "rejection_reason": "pair_drift_not_acknowledged: operator must set pair_drift_acknowledged=True and provide manual_override_reason",
                "inclusion_reason": None,
            })
            continue

        # Reject: missing mint
        if not mint:
            rejected_candidates.append({
                **cand_record,
                "included": False,
                "rejection_reason": "missing_token_mint",
                "inclusion_reason": None,
            })
            continue

        # Accept
        inclusion_reason = (
            f"{event_kind}:{raw_cand.get('discovery_action', 'UNKNOWN')}:{raw_cand.get('priority_reason', '')}"
        )
        if context_tags:
            inclusion_reason += f":context_tags=[{','.join(context_tags)}]"
        if has_override:
            inclusion_reason += f":manual_override={manual_override_reason}"

        event_kind_summary[event_kind] = event_kind_summary.get(event_kind, 0) + 1

        selected_entry = {
            **cand_record,
            "included": True,
            "inclusion_reason": inclusion_reason,
            "rejection_reason": None,
        }
        selected_candidates.append(selected_entry)

        if has_override:
            manual_overrides.append({
                "token_mint": mint,
                "pair_address": pair,
                "manual_override_reason": manual_override_reason,
                "watch_only_to_track_fast_override": bool(raw_cand.get("watch_only_to_track_fast_override")),
                "no_discovery_origin": bool(raw_cand.get("no_discovery_origin")),
                "pair_drift_acknowledged": drift_acknowledged,
            })

    batch_balance = assess_batch_balance(selected_candidates)

    pair_drift_pending = sum(
        1 for item in pair_drift_items if not item["pair_drift_acknowledged"]
    )

    finished_at = _utc_now()

    return {
        "lane_x10_6_status": LANE_X10_6_STATUS_COMPLETED,
        "operator_approved": operator_approved,
        "db_path": str(db_path),
        "proposed_x5_token_list_path": proposed_x5_token_list_path,
        "batch_produced_at": started_at,
        "run_started_at": started_at,
        "run_finished_at": finished_at,
        "candidate_count_input": len(raw),
        "selected_count": len(selected_candidates),
        "rejected_count": len(rejected_candidates),
        "override_required_count": len(manual_overrides),
        "override_missing_count": override_missing_count,
        "pair_drift_pending_acknowledgment": pair_drift_pending,
        "selected_candidates": selected_candidates,
        "rejected_candidates": rejected_candidates,
        "manual_overrides": manual_overrides,
        "pair_drift_items": pair_drift_items,
        "event_kind_summary": event_kind_summary,
        "batch_balance": batch_balance,
        "automated_selection_locked": True,
        "discovery_is_intake_not_alpha": True,
        "selection_is_memory_value_based_not_buy_probability": True,
        "hard_locks": dict(_HARD_LOCKS),
        "buy_enabled": False,
        "sell_enabled": False,
        "hold_enabled": False,
        "paper_decisions_created": 0,
        "positions_created": 0,
        "trade_events_created": 0,
        "pnl_created": 0,
    }
