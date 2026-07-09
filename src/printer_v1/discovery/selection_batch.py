"""V2-2C Selection-batch persistence, bucket assignment, and quota validation.

All bucket assignments are categorical. No scores, ranks, confidence
percentages, or weighted logic are used or stored.

Bucket taxonomy (from V2-2B design):
  Group A  fast-event / high-activity
  Group B  normal-activity / slow-moving
  Group C  liquidity-state
  Group D  lifecycle / state-change
  Group E  exit-evidence annotations
  Group F  counterfactual avoidance/wait (deferred — requires corpus)

Asset-class labels and behavior-context tags are audit/learning metadata
only. They must never become scores, ranks, BUY probabilities, or paper
decision triggers.

Locks preserved:
  No discovery automation, source fetching, memory generation, retrieval,
  paper decisions, BUY/SELL/HOLD, positions, trades, audits, PnL.
"""

from __future__ import annotations

import json
import sqlite3
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

# ---------------------------------------------------------------------------
# Bucket taxonomy — categorical IDs only
# ---------------------------------------------------------------------------

BUCKET_A1 = "A1"
BUCKET_A2 = "A2"
BUCKET_A3 = "A3"
BUCKET_A4 = "A4"
BUCKET_B1 = "B1"
BUCKET_B2 = "B2"
BUCKET_B3 = "B3"
BUCKET_B4 = "B4"
BUCKET_B5 = "B5"
BUCKET_C1 = "C1"
BUCKET_C2 = "C2"
BUCKET_C3 = "C3"
BUCKET_D1 = "D1"
BUCKET_D2 = "D2"
BUCKET_D3 = "D3"
BUCKET_D4 = "D4"
BUCKET_E1 = "E1"
BUCKET_E2 = "E2"
BUCKET_F1 = "F1"
BUCKET_F2 = "F2"
BUCKET_F3 = "F3"
BUCKET_F4 = "F4"

BUCKET_NAMES: dict[str, str] = {
    BUCKET_A1: "FAST_PUMP_FOLLOW",
    BUCKET_A2: "WICK_ONLY_PUMP",
    BUCKET_A3: "LATE_BUY_TRAP",
    BUCKET_A4: "FAILED_PUMP",
    BUCKET_B1: "VOLUME_RISING",
    BUCKET_B2: "VOLUME_DECAYING",
    BUCKET_B3: "TRANSACTION_SPIKE",
    BUCKET_B4: "TRANSACTION_DECAY",
    BUCKET_B5: "CONSOLIDATION",
    BUCKET_C1: "LIQUIDITY_RISING",
    BUCKET_C2: "LIQUIDITY_FALLING",
    BUCKET_C3: "LIQUIDITY_REMOVED",
    BUCKET_D1: "DEAD_TOKEN",
    BUCKET_D2: "REVIVAL",
    BUCKET_D3: "MIGRATION_EVENT",
    BUCKET_D4: "SUSPICIOUS_SAFETY",
    BUCKET_E1: "REALISTIC_EXIT",
    BUCKET_E2: "UNREALISTIC_EXIT",
    BUCKET_F1: "CORRECT_AVOID",
    BUCKET_F2: "WRONG_AVOID",
    BUCKET_F3: "CORRECT_WAIT",
    BUCKET_F4: "WRONG_WAIT",
}

GROUP_A_BUCKETS = frozenset({BUCKET_A1, BUCKET_A2, BUCKET_A3, BUCKET_A4})
GROUP_B_BUCKETS = frozenset({BUCKET_B1, BUCKET_B2, BUCKET_B3, BUCKET_B4, BUCKET_B5})
GROUP_C_BUCKETS = frozenset({BUCKET_C1, BUCKET_C2, BUCKET_C3})
GROUP_D_BUCKETS = frozenset({BUCKET_D1, BUCKET_D2, BUCKET_D3, BUCKET_D4})
GROUP_E_BUCKETS = frozenset({BUCKET_E1, BUCKET_E2})
GROUP_F_BUCKETS = frozenset({BUCKET_F1, BUCKET_F2, BUCKET_F3, BUCKET_F4})
TRAP_FAILURE_BUCKETS = frozenset({BUCKET_A2, BUCKET_A3, BUCKET_A4})

# Group F requires at minimum 10 clean episodes in the corpus before use.
GROUP_F_MINIMUM_CORPUS_EPISODES = 10

# ---------------------------------------------------------------------------
# Asset-class labels — categorical, audit/learning metadata only
# ---------------------------------------------------------------------------

ASSET_CLASS_NEW_LAUNCH = "NEW_LAUNCH"
ASSET_CLASS_MIGRATED_TOKEN = "MIGRATED_TOKEN"
ASSET_CLASS_HOT_TRENDING_PAIR = "HOT_TRENDING_PAIR"
ASSET_CLASS_BOOSTED_TOKEN = "BOOSTED_TOKEN"
ASSET_CLASS_FAST_PUMP = "FAST_PUMP"
ASSET_CLASS_FAILED_PUMP = "FAILED_PUMP"
ASSET_CLASS_WICK_ONLY_PUMP = "WICK_ONLY_PUMP"
ASSET_CLASS_LATE_BUY_TRAP = "LATE_BUY_TRAP"
ASSET_CLASS_DEAD_TOKEN = "DEAD_TOKEN"
ASSET_CLASS_REVIVAL_TOKEN = "REVIVAL_TOKEN"
ASSET_CLASS_LIQUIDITY_RISING = "LIQUIDITY_RISING"
ASSET_CLASS_LIQUIDITY_FALLING = "LIQUIDITY_FALLING"
ASSET_CLASS_LIQUIDITY_REMOVED = "LIQUIDITY_REMOVED"
ASSET_CLASS_VOLUME_RISING = "VOLUME_RISING"
ASSET_CLASS_VOLUME_DECAYING = "VOLUME_DECAYING"
ASSET_CLASS_CONSOLIDATION = "CONSOLIDATION"
ASSET_CLASS_SUSPICIOUS_SAFETY = "SUSPICIOUS_SAFETY"
ASSET_CLASS_REALISTIC_EXIT_CANDIDATE = "REALISTIC_EXIT_CANDIDATE"
ASSET_CLASS_UNREALISTIC_EXIT_CANDIDATE = "UNREALISTIC_EXIT_CANDIDATE"
ASSET_CLASS_UNKNOWN_UNCLASSIFIED = "UNKNOWN_UNCLASSIFIED"

ALLOWED_ASSET_CLASSES = frozenset({
    ASSET_CLASS_NEW_LAUNCH,
    ASSET_CLASS_MIGRATED_TOKEN,
    ASSET_CLASS_HOT_TRENDING_PAIR,
    ASSET_CLASS_BOOSTED_TOKEN,
    ASSET_CLASS_FAST_PUMP,
    ASSET_CLASS_FAILED_PUMP,
    ASSET_CLASS_WICK_ONLY_PUMP,
    ASSET_CLASS_LATE_BUY_TRAP,
    ASSET_CLASS_DEAD_TOKEN,
    ASSET_CLASS_REVIVAL_TOKEN,
    ASSET_CLASS_LIQUIDITY_RISING,
    ASSET_CLASS_LIQUIDITY_FALLING,
    ASSET_CLASS_LIQUIDITY_REMOVED,
    ASSET_CLASS_VOLUME_RISING,
    ASSET_CLASS_VOLUME_DECAYING,
    ASSET_CLASS_CONSOLIDATION,
    ASSET_CLASS_SUSPICIOUS_SAFETY,
    ASSET_CLASS_REALISTIC_EXIT_CANDIDATE,
    ASSET_CLASS_UNREALISTIC_EXIT_CANDIDATE,
    ASSET_CLASS_UNKNOWN_UNCLASSIFIED,
})

# ---------------------------------------------------------------------------
# Behavior/psychology context labels — categorical audit tags only
# ---------------------------------------------------------------------------

BEHAVIOR_ATTENTION_SPIKE = "ATTENTION_SPIKE"
BEHAVIOR_LATE_CHASER_RISK = "LATE_CHASER_RISK"
BEHAVIOR_PANIC_DUMP = "PANIC_DUMP"
BEHAVIOR_ROTATION_BEHAVIOR = "ROTATION_BEHAVIOR"
BEHAVIOR_POST_PUMP_EXHAUSTION = "POST_PUMP_EXHAUSTION"
BEHAVIOR_LIQUIDITY_TRAP_BEHAVIOR = "LIQUIDITY_TRAP_BEHAVIOR"
BEHAVIOR_HYPE_WITH_WEAK_LIQUIDITY = "HYPE_WITH_WEAK_LIQUIDITY"
BEHAVIOR_UNKNOWN_BEHAVIOR_CONTEXT = "UNKNOWN_BEHAVIOR_CONTEXT"

ALLOWED_BEHAVIOR_CONTEXT_LABELS = frozenset({
    BEHAVIOR_ATTENTION_SPIKE,
    BEHAVIOR_LATE_CHASER_RISK,
    BEHAVIOR_PANIC_DUMP,
    BEHAVIOR_ROTATION_BEHAVIOR,
    BEHAVIOR_POST_PUMP_EXHAUSTION,
    BEHAVIOR_LIQUIDITY_TRAP_BEHAVIOR,
    BEHAVIOR_HYPE_WITH_WEAK_LIQUIDITY,
    BEHAVIOR_UNKNOWN_BEHAVIOR_CONTEXT,
})

# ---------------------------------------------------------------------------
# Same-token/new-pair classifications
# ---------------------------------------------------------------------------

STNP_MIGRATION = "MIGRATION"
STNP_REVIVAL = "REVIVAL"
STNP_PAIR_DRIFT = "PAIR_DRIFT"
STNP_DUPLICATE_RECYCLE = "DUPLICATE_RECYCLE"
STNP_DISTINCT_EVIDENCE = "DISTINCT_EVIDENCE"

ALLOWED_STNP_CLASSIFICATIONS = frozenset({
    STNP_MIGRATION,
    STNP_REVIVAL,
    STNP_PAIR_DRIFT,
    STNP_DUPLICATE_RECYCLE,
    STNP_DISTINCT_EVIDENCE,
})

# ---------------------------------------------------------------------------
# Pair age context labels (V2-2P) — T4-safe context only, never gate-driving
# ---------------------------------------------------------------------------

PAIR_AGE_CONTEXT_RECENT_LAUNCH = "RECENT_LAUNCH"
PAIR_AGE_CONTEXT_OLDER_TOKEN = "OLDER_TOKEN"
PAIR_AGE_CONTEXT_RECENT_PAIR_FOR_EXISTING_TOKEN = "RECENT_PAIR_FOR_EXISTING_TOKEN"
PAIR_AGE_CONTEXT_PAIR_ONLY_AGE_KNOWN = "PAIR_ONLY_AGE_KNOWN"
PAIR_AGE_CONTEXT_UNKNOWN_TOKEN_AGE = "UNKNOWN_TOKEN_AGE"

ALLOWED_PAIR_AGE_CONTEXT_LABELS: frozenset[str] = frozenset({
    PAIR_AGE_CONTEXT_RECENT_LAUNCH,
    PAIR_AGE_CONTEXT_OLDER_TOKEN,
    PAIR_AGE_CONTEXT_RECENT_PAIR_FOR_EXISTING_TOKEN,
    PAIR_AGE_CONTEXT_PAIR_ONLY_AGE_KNOWN,
    PAIR_AGE_CONTEXT_UNKNOWN_TOKEN_AGE,
})

# ---------------------------------------------------------------------------
# Item status
# ---------------------------------------------------------------------------

ITEM_STATUS_SELECTED = "SELECTED"
ITEM_STATUS_REJECTED = "REJECTED"
ITEM_STATUS_UNCLASSIFIED = "UNCLASSIFIED"

# ---------------------------------------------------------------------------
# Batch status
# ---------------------------------------------------------------------------

BATCH_STATUS_ASSEMBLED = "ASSEMBLED"
BATCH_STATUS_REJECTED = "REJECTED"
BATCH_STATUS_PENDING_PROOF = "PENDING_PROOF"

# ---------------------------------------------------------------------------
# Selection / rejection reason labels
# ---------------------------------------------------------------------------

REASON_FAST_ACTIVITY_CONFIRMED = "FAST_ACTIVITY_CONFIRMED"
REASON_NORMAL_ACTIVITY_BASELINE = "NORMAL_ACTIVITY_BASELINE"
REASON_TRANSACTION_SPIKE_DETECTED = "TRANSACTION_SPIKE_DETECTED"
REASON_VOLUME_RISING_TREND = "VOLUME_RISING_TREND"
REASON_VOLUME_DECAY_PATTERN = "VOLUME_DECAY_PATTERN"
REASON_CONSOLIDATION_PATTERN = "CONSOLIDATION_PATTERN"
REASON_LIQUIDITY_ABOVE_THRESHOLD = "LIQUIDITY_ABOVE_THRESHOLD"
REASON_LIQUIDITY_BELOW_THRESHOLD = "LIQUIDITY_BELOW_THRESHOLD"
REASON_LIQUIDITY_NEAR_ZERO = "LIQUIDITY_NEAR_ZERO"
REASON_LIQUIDITY_REMOVED_SIGNAL = "LIQUIDITY_REMOVED_SIGNAL"
REASON_DEAD_TOKEN_PROTECTION_SAMPLE = "DEAD_TOKEN_PROTECTION_SAMPLE"
REASON_REVIVAL_DETECTED = "REVIVAL_DETECTED"
REASON_MIGRATION_DETECTED = "MIGRATION_DETECTED"
REASON_SUSPICIOUS_SAFETY_SIGNAL = "SUSPICIOUS_SAFETY_SIGNAL"
REASON_WICK_ONLY_EVIDENCE = "WICK_ONLY_EVIDENCE"
REASON_LATE_ENTRY_RISK = "LATE_ENTRY_RISK"
REASON_FAILED_PUMP_EVIDENCE = "FAILED_PUMP_EVIDENCE"
REASON_TRAP_MEMORY_REQUIRED = "TRAP_MEMORY_REQUIRED"
REASON_CORRECT_AVOID_CANDIDATE = "CORRECT_AVOID_CANDIDATE"
REASON_WRONG_AVOID_CANDIDATE = "WRONG_AVOID_CANDIDATE"
REASON_CORRECT_WAIT_CANDIDATE = "CORRECT_WAIT_CANDIDATE"
REASON_WRONG_WAIT_CANDIDATE = "WRONG_WAIT_CANDIDATE"
REASON_EXIT_REALISM_SAMPLE = "EXIT_REALISM_SAMPLE"
REASON_UNREALISTIC_EXIT_EVIDENCE = "UNREALISTIC_EXIT_EVIDENCE"

REJECTION_MINT_DUPLICATE = "MINT_DUPLICATE"
REJECTION_PAIR_DUPLICATE = "PAIR_DUPLICATE"
REJECTION_ACTIVE_COOLDOWN = "ACTIVE_COOLDOWN"
REJECTION_ARCHIVED_NO_REOPEN = "ARCHIVED_NO_REOPEN"
REJECTION_BATCH_QUOTA_EXCEEDED = "BATCH_QUOTA_EXCEEDED"
REJECTION_WINNER_CAP_EXCEEDED = "WINNER_CAP_EXCEEDED"
REJECTION_STALE_SOURCE_DATA = "STALE_SOURCE_DATA"
REJECTION_CHAIN_NOT_SOLANA = "CHAIN_NOT_SOLANA"
REJECTION_INSTANT_REJECT_CLASSIFICATION = "INSTANT_REJECT_CLASSIFICATION"
REJECTION_IGNORE_CLASSIFICATION = "IGNORE_CLASSIFICATION"
REJECTION_NO_SOURCE_TRACE = "NO_SOURCE_TRACE"
REJECTION_PAIR_DRIFT_UNRESOLVED = "PAIR_DRIFT_UNRESOLVED"
REJECTION_STNP_UNRESOLVED = "STNP_UNRESOLVED"
REJECTION_SAFETY_RISK_OPERATOR_OVERRIDE = "SAFETY_RISK_OPERATOR_OVERRIDE"
REJECTION_MANUAL_EXCLUSION = "MANUAL_EXCLUSION"
REJECTION_GROUP_F_CORPUS_TOO_SMALL = "GROUP_F_CORPUS_TOO_SMALL"
# Within-response integrity constants (V2-2H.4).
# Distinct from DB-level STNP_UNRESOLVED/PAIR_DUPLICATE to make reporting
# unambiguous: these values only appear in within_response_integrity_report.
REJECTION_PAIR_DUPLICATE_WITHIN_RESPONSE = "PAIR_DUPLICATE_WITHIN_RESPONSE"
REJECTION_STNP_WITHIN_RESPONSE_UNRESOLVED = "STNP_WITHIN_RESPONSE_UNRESOLVED"

# ---------------------------------------------------------------------------
# Thresholds for bucket assignment (all categorical gates, no scores)
# ---------------------------------------------------------------------------

_LIQUIDITY_NEAR_ZERO_USD = 500.0
_LIQUIDITY_FAST_THRESHOLD_USD = 5_000.0
_LIQUIDITY_NORMAL_THRESHOLD_USD = 1_000.0
_VOLUME_FAST_5M_USD = 1_000.0
_TXNS_FAST_5M = 10
_TINY_VOLUME_24H_USD = 10.0
_TINY_TXNS_24H = 2
_WICK_PRICE_CHANGE_REVERSAL_PCT = -20.0
_LATE_BUY_TOKEN_AGE_SECONDS = 3600.0
_TRANSACTION_SPIKE_RATIO = 3.0

# ---------------------------------------------------------------------------
# Age bucket taxonomy (V2-2H.2) — categorical IDs only
# ---------------------------------------------------------------------------

AGE_0_24H = "AGE_0_24H"
AGE_1_7D = "AGE_1_7D"
AGE_7_14D = "AGE_7_14D"
AGE_14_28D = "AGE_14_28D"
AGE_28D_PLUS = "AGE_28D_PLUS"
AGE_UNKNOWN = "AGE_UNKNOWN"

# Frozenset of buckets considered "recent" for priority-tier derivation.
AGE_BUCKETS_RECENT: frozenset[str] = frozenset({AGE_0_24H, AGE_1_7D, AGE_7_14D, AGE_14_28D})

_AGE_24H_SECONDS = 86_400.0     # 24 h
_AGE_7D_SECONDS = 604_800.0    # 7 d
_AGE_14D_SECONDS = 1_209_600.0  # 14 d
_AGE_28D_SECONDS = 2_419_200.0  # 28 d

# ---------------------------------------------------------------------------
# Activity bucket taxonomy (V2-2H.2) — categorical IDs only
# ---------------------------------------------------------------------------

ACTIVITY_HIGH = "ACTIVITY_HIGH"
ACTIVITY_MEDIUM = "ACTIVITY_MEDIUM"
ACTIVITY_LOW = "ACTIVITY_LOW"
ACTIVITY_DEAD = "ACTIVITY_DEAD"
ACTIVITY_REVIVING = "ACTIVITY_REVIVING"
ACTIVITY_UNKNOWN = "ACTIVITY_UNKNOWN"

_ACTIVITY_MEDIUM_VOLUME_24H_USD = 200.0
_ACTIVITY_REVIVING_LIFECYCLE_STATES: frozenset[str] = frozenset({"ARCHIVED", "COOLDOWN", "DEAD"})

# ---------------------------------------------------------------------------
# Recent-active priority tier taxonomy (V2-2H.2) — categorical IDs only
# ---------------------------------------------------------------------------

RECENT_ACTIVE_TIER_1 = "RECENT_ACTIVE_TIER_1"
RECENT_ACTIVE_TIER_2 = "RECENT_ACTIVE_TIER_2"
OLDER_ACTIVE_TIER_3 = "OLDER_ACTIVE_TIER_3"
LOW_ACTIVITY_TIER_4 = "LOW_ACTIVITY_TIER_4"
UNKNOWN_TIER_5 = "UNKNOWN_TIER_5"


def _f(value: Any) -> float:
    return 0.0 if value is None else float(value)


def _migration_channel(source_channel: str | None) -> bool:
    return source_channel in {
        "PUMPFUN_MIGRATION",
        "PUMPSWAP_GRADUATED",
        "PUMPSWAP_MIGRATION_POOL_REFERENCE",
    }


# ---------------------------------------------------------------------------
# Bucket assignment
# ---------------------------------------------------------------------------

def assign_bucket(candidate: dict[str, Any]) -> tuple[str, str]:
    """Return (bucket_id, bucket_name) for a normalized candidate dict.

    The assignment is purely categorical — no scores, no ranks, no floats
    are returned. Inputs are read from candidate fields; the output is one
    of the fixed bucket IDs in BUCKET_NAMES.

    Precedence order (first match wins):
      D1 dead token
      C3 liquidity removed
      D4 suspicious safety
      D3 migration event
      D2 revival (from cooldown_reopened flag on the item, not here —
                  callers should override to D2 when cooldown_reopened=True)
      A-tier fast-event
      C1/C2 liquidity trend
      B-tier normal-activity
      B5 consolidation / fallback
    """
    liquidity = _f(candidate.get("liquidity_usd"))
    volume_5m = _f(candidate.get("volume_5m"))
    volume_1h = _f(candidate.get("volume_1h"))
    volume_24h = _f(candidate.get("volume_24h"))
    txns_5m = _f(candidate.get("txns_5m"))
    txns_1h = _f(candidate.get("txns_1h"))
    txns_24h = _f(candidate.get("txns_24h"))
    price_change_5m = _f(candidate.get("price_change_5m"))
    price_change_1h = _f(candidate.get("price_change_1h"))
    token_age = _f(candidate.get("token_age_seconds"))
    safety_label = candidate.get("safety_label") or ""
    source_channel = candidate.get("source_channel")
    discovery_action = candidate.get("discovery_action") or candidate.get("tracking_lane") or ""

    # V2-2H.3: raw-None guards for A2/A3. _f() converts None→0.0, which
    # accidentally blocks A2 (0.0 <= -20.0 is False) and A3 (0.0 >= 3600 is
    # False), but that is coincidental and not the explicit design intent.
    # These flags make the gate explicit: missing field → A1, not A2/A3.
    _pc5m_known = candidate.get("price_change_5m") is not None
    _pc1h_known = candidate.get("price_change_1h") is not None
    _tok_age_known = candidate.get("token_age_seconds") is not None

    is_near_dead = (
        volume_5m <= 0
        and txns_5m <= 0
        and volume_1h <= 0
        and txns_1h <= 0
        and volume_24h <= _TINY_VOLUME_24H_USD
        and txns_24h <= _TINY_TXNS_24H
    )
    if is_near_dead:
        return BUCKET_D1, BUCKET_NAMES[BUCKET_D1]

    if 0 < liquidity <= _LIQUIDITY_NEAR_ZERO_USD:
        return BUCKET_C3, BUCKET_NAMES[BUCKET_C3]

    if safety_label and safety_label not in {"", "SAFE", "UNKNOWN"}:
        return BUCKET_D4, BUCKET_NAMES[BUCKET_D4]

    if _migration_channel(source_channel):
        return BUCKET_D3, BUCKET_NAMES[BUCKET_D3]

    is_fast_tier = (
        liquidity >= _LIQUIDITY_FAST_THRESHOLD_USD
        and (volume_5m >= _VOLUME_FAST_5M_USD or txns_5m >= _TXNS_FAST_5M)
    )
    if is_fast_tier:
        if (
            _pc5m_known
            and price_change_5m <= _WICK_PRICE_CHANGE_REVERSAL_PCT
            and volume_5m >= _VOLUME_FAST_5M_USD
        ):
            return BUCKET_A2, BUCKET_NAMES[BUCKET_A2]
        if (
            _tok_age_known
            and _pc1h_known
            and token_age >= _LATE_BUY_TOKEN_AGE_SECONDS
            and price_change_1h < 0
        ):
            return BUCKET_A3, BUCKET_NAMES[BUCKET_A3]
        return BUCKET_A1, BUCKET_NAMES[BUCKET_A1]

    if liquidity < _LIQUIDITY_NORMAL_THRESHOLD_USD and liquidity > _LIQUIDITY_NEAR_ZERO_USD:
        return BUCKET_C2, BUCKET_NAMES[BUCKET_C2]

    if price_change_1h > 10.0 and volume_1h > 0:
        return BUCKET_C1, BUCKET_NAMES[BUCKET_C1]
    if price_change_1h < -10.0 and liquidity > 0:
        return BUCKET_C2, BUCKET_NAMES[BUCKET_C2]

    if txns_5m >= _TXNS_FAST_5M and volume_5m > 0:
        return BUCKET_B3, BUCKET_NAMES[BUCKET_B3]

    if volume_24h > _TINY_VOLUME_24H_USD:
        if volume_1h > 0 and price_change_1h > 0:
            return BUCKET_B1, BUCKET_NAMES[BUCKET_B1]
        if volume_1h <= 0 and txns_1h <= 0:
            return BUCKET_B4, BUCKET_NAMES[BUCKET_B4]
        if price_change_1h < 0:
            return BUCKET_B2, BUCKET_NAMES[BUCKET_B2]
        return BUCKET_B5, BUCKET_NAMES[BUCKET_B5]

    return BUCKET_B5, BUCKET_NAMES[BUCKET_B5]


# ---------------------------------------------------------------------------
# Asset-class assignment — categorical metadata tag, not a selection criterion
# ---------------------------------------------------------------------------

_BUCKET_TO_ASSET_CLASS: dict[str, str] = {
    BUCKET_A1: ASSET_CLASS_FAST_PUMP,
    BUCKET_A2: ASSET_CLASS_WICK_ONLY_PUMP,
    BUCKET_A3: ASSET_CLASS_LATE_BUY_TRAP,
    BUCKET_A4: ASSET_CLASS_FAILED_PUMP,
    BUCKET_B1: ASSET_CLASS_VOLUME_RISING,
    BUCKET_B2: ASSET_CLASS_VOLUME_DECAYING,
    BUCKET_B3: ASSET_CLASS_HOT_TRENDING_PAIR,
    BUCKET_B4: ASSET_CLASS_VOLUME_DECAYING,
    BUCKET_B5: ASSET_CLASS_CONSOLIDATION,
    BUCKET_C1: ASSET_CLASS_LIQUIDITY_RISING,
    BUCKET_C2: ASSET_CLASS_LIQUIDITY_FALLING,
    BUCKET_C3: ASSET_CLASS_LIQUIDITY_REMOVED,
    BUCKET_D1: ASSET_CLASS_DEAD_TOKEN,
    BUCKET_D2: ASSET_CLASS_REVIVAL_TOKEN,
    BUCKET_D3: ASSET_CLASS_MIGRATED_TOKEN,
    BUCKET_D4: ASSET_CLASS_SUSPICIOUS_SAFETY,
    BUCKET_E1: ASSET_CLASS_REALISTIC_EXIT_CANDIDATE,
    BUCKET_E2: ASSET_CLASS_UNREALISTIC_EXIT_CANDIDATE,
}


def derive_asset_class(bucket_id: str) -> str:
    """Return asset-class label for a bucket. Categorical tag only."""
    return _BUCKET_TO_ASSET_CLASS.get(bucket_id, ASSET_CLASS_UNKNOWN_UNCLASSIFIED)


# ---------------------------------------------------------------------------
# Age bucket derivation (V2-2H.2)
# ---------------------------------------------------------------------------

def derive_age_bucket(candidate: dict[str, Any]) -> str:
    """Return categorical age bucket for a candidate.

    Uses explicit None check — never uses _f() — so a missing
    token_age_seconds returns AGE_UNKNOWN rather than AGE_0_24H (which
    _f()'s default 0.0 would silently cause).
    """
    age = candidate.get("token_age_seconds")
    if age is None:
        return AGE_UNKNOWN
    try:
        age_f = float(age)
    except (TypeError, ValueError):
        return AGE_UNKNOWN
    if age_f < 0:
        return AGE_UNKNOWN
    if age_f < _AGE_24H_SECONDS:
        return AGE_0_24H
    if age_f < _AGE_7D_SECONDS:
        return AGE_1_7D
    if age_f < _AGE_14D_SECONDS:
        return AGE_7_14D
    if age_f < _AGE_28D_SECONDS:
        return AGE_14_28D
    return AGE_28D_PLUS


# ---------------------------------------------------------------------------
# Activity bucket derivation (V2-2H.2)
# ---------------------------------------------------------------------------

def derive_activity_bucket(
    candidate: dict[str, Any],
    *,
    prior_lifecycle_state: str | None = None,
) -> str:
    """Return categorical activity bucket for a candidate.

    prior_lifecycle_state enables ACTIVITY_REVIVING classification. When the
    candidate's prior state was ARCHIVED, COOLDOWN, or DEAD and new short-
    window activity is now present, the token is classified REVIVING rather
    than LOW or DEAD.

    Fresh-launch safe: ACTIVITY_HIGH is reachable from 5m + liquidity fields
    alone without requiring volume_24h history. A token minutes old is not
    penalized for absent 24h data.
    """
    liquidity = candidate.get("liquidity_usd")
    if liquidity is None:
        return ACTIVITY_UNKNOWN

    liq = _f(liquidity)
    vol5m = _f(candidate.get("volume_5m"))
    txns5m = _f(candidate.get("txns_5m"))
    vol1h = _f(candidate.get("volume_1h"))
    txns1h = _f(candidate.get("txns_1h"))
    vol24h = _f(candidate.get("volume_24h"))
    txns24h = _f(candidate.get("txns_24h"))

    if liq >= _LIQUIDITY_FAST_THRESHOLD_USD and (
        vol5m >= _VOLUME_FAST_5M_USD or txns5m >= _TXNS_FAST_5M
    ):
        return ACTIVITY_HIGH

    if prior_lifecycle_state in _ACTIVITY_REVIVING_LIFECYCLE_STATES and (
        vol5m > 0 or txns5m > 0 or vol1h > 0 or txns1h > 0
    ):
        return ACTIVITY_REVIVING

    if (
        vol5m <= 0
        and txns5m <= 0
        and vol1h <= 0
        and txns1h <= 0
        and vol24h <= _TINY_VOLUME_24H_USD
        and txns24h <= _TINY_TXNS_24H
    ):
        return ACTIVITY_DEAD

    if liq >= _LIQUIDITY_NORMAL_THRESHOLD_USD and vol24h > _ACTIVITY_MEDIUM_VOLUME_24H_USD:
        return ACTIVITY_MEDIUM

    return ACTIVITY_LOW


# ---------------------------------------------------------------------------
# Recent-active priority tier derivation (V2-2H.2)
# ---------------------------------------------------------------------------

def derive_recent_active_tier(age_bucket: str, activity_bucket: str) -> str:
    """Return categorical priority tier from age and activity buckets.

    Tiers are categorical ordering for memory-diet consideration only. They
    are not token rankings, selection scores, or trading signals.

      RECENT_ACTIVE_TIER_1  recent (0-28d) + HIGH or MEDIUM
      RECENT_ACTIVE_TIER_2  recent (0-28d) + REVIVING
      OLDER_ACTIVE_TIER_3   28d+ + HIGH, MEDIUM, or REVIVING
      LOW_ACTIVITY_TIER_4   any age + LOW or DEAD
      UNKNOWN_TIER_5        AGE_UNKNOWN or ACTIVITY_UNKNOWN
    """
    if age_bucket == AGE_UNKNOWN or activity_bucket == ACTIVITY_UNKNOWN:
        return UNKNOWN_TIER_5

    is_recent = age_bucket in AGE_BUCKETS_RECENT

    if is_recent and activity_bucket in {ACTIVITY_HIGH, ACTIVITY_MEDIUM}:
        return RECENT_ACTIVE_TIER_1
    if is_recent and activity_bucket == ACTIVITY_REVIVING:
        return RECENT_ACTIVE_TIER_2
    if not is_recent and activity_bucket in {ACTIVITY_HIGH, ACTIVITY_MEDIUM, ACTIVITY_REVIVING}:
        return OLDER_ACTIVE_TIER_3
    if activity_bucket in {ACTIVITY_LOW, ACTIVITY_DEAD}:
        return LOW_ACTIVITY_TIER_4
    return UNKNOWN_TIER_5


# ---------------------------------------------------------------------------
# Age/activity report aggregation (V2-2H.2)
# ---------------------------------------------------------------------------

def build_age_activity_report(candidates: list[dict[str, Any]]) -> dict[str, Any]:
    """Return age/activity/tier bucket counts for a list of candidate dicts.

    All counts are ints. No scores, floats, or weighted logic are produced.
    """
    by_age: dict[str, int] = {}
    by_activity: dict[str, int] = {}
    by_tier: dict[str, int] = {}

    for c in candidates:
        age_b = derive_age_bucket(c)
        act_b = derive_activity_bucket(c)
        tier = derive_recent_active_tier(age_b, act_b)

        by_age[age_b] = by_age.get(age_b, 0) + 1
        by_activity[act_b] = by_activity.get(act_b, 0) + 1
        by_tier[tier] = by_tier.get(tier, 0) + 1

    return {
        "total_candidates": len(candidates),
        "candidates_by_age_bucket": by_age,
        "candidates_by_activity_bucket": by_activity,
        "candidates_by_priority_tier": by_tier,
    }


# ---------------------------------------------------------------------------
# A4 failed-pump helper (V2-2H.3)
# ---------------------------------------------------------------------------

def derive_failed_pump_bucket(
    current_candidate: dict[str, Any],
    prior_candidate: dict[str, Any],
) -> tuple[str, str] | None:
    """Return (BUCKET_A4, name) if the current candidate qualifies as a failed pump.

    Returns None if A4 conditions are not met. The caller is responsible for
    verifying the current candidate does not qualify for A-tier before routing
    here (or this function will return None if it still qualifies).

    A4 conditions (V2-2G design):
      - prior candidate had an A-tier primary bucket
      - current candidate no longer qualifies for fast-tier
      - liquidity has not been fully removed (>LIQUIDITY_NEAR_ZERO threshold)

    Integration: assign_bucket() does not receive prior candidate context.
    Wire this helper only where prior candidate data is available in the
    selection path. Until that wiring exists, A4 derivation is deferred at
    the assign_bucket() call site but the helper is testable in isolation.
    """
    prior_bucket = prior_candidate.get("primary_bucket")
    if prior_bucket not in GROUP_A_BUCKETS:
        return None

    liq = _f(current_candidate.get("liquidity_usd"))
    vol5m = _f(current_candidate.get("volume_5m"))
    txns5m = _f(current_candidate.get("txns_5m"))

    is_still_fast_tier = (
        liq >= _LIQUIDITY_FAST_THRESHOLD_USD
        and (vol5m >= _VOLUME_FAST_5M_USD or txns5m >= _TXNS_FAST_5M)
    )
    if is_still_fast_tier:
        return None

    if liq <= _LIQUIDITY_NEAR_ZERO_USD:
        return None  # liquidity removed → route as C3, not A4

    return BUCKET_A4, BUCKET_NAMES[BUCKET_A4]


# ---------------------------------------------------------------------------
# Field completeness report (V2-2H.3)
# ---------------------------------------------------------------------------

_CRITICAL_FAST_EVENT_FIELDS: tuple[str, ...] = (
    "token_created_at",
    "pair_created_at",
    "token_age_seconds",
    "pair_age_seconds",
    "price_change_5m",
    "price_change_15m",
    "price_change_1h",
    "price_change_24h",
    "volume_15m",
)


def build_field_completeness_report(candidates: list[dict[str, Any]]) -> dict[str, Any]:
    """Return per-field missing counts for critical fast-event fields.

    All counts are ints. A field is counted as missing when it is None or absent.
    """
    counts: dict[str, int] = {f"missing_{f}_count": 0 for f in _CRITICAL_FAST_EVENT_FIELDS}
    for c in candidates:
        for field in _CRITICAL_FAST_EVENT_FIELDS:
            if c.get(field) is None:
                counts[f"missing_{field}_count"] += 1
    counts["total_candidates"] = len(candidates)
    return counts


# ---------------------------------------------------------------------------
# Pair age context report (V2-2P)
# ---------------------------------------------------------------------------

def build_pair_age_context_report(candidates: list[dict[str, Any]]) -> dict[str, Any]:
    """Return label counts for pair_age_context_label and token_age_evidence_tier.

    These are T4-safe context fields only. They do not drive age gates, A3,
    derive_age_bucket, or derive_recent_active_tier. All counts are ints.
    """
    label_counts: dict[str, int] = {
        PAIR_AGE_CONTEXT_RECENT_LAUNCH: 0,
        PAIR_AGE_CONTEXT_OLDER_TOKEN: 0,
        PAIR_AGE_CONTEXT_RECENT_PAIR_FOR_EXISTING_TOKEN: 0,
        PAIR_AGE_CONTEXT_PAIR_ONLY_AGE_KNOWN: 0,
        PAIR_AGE_CONTEXT_UNKNOWN_TOKEN_AGE: 0,
    }
    tier_counts: dict[str, int] = {
        "T1": 0,
        "T2": 0,
        "T3": 0,
        "T4_PAIR_ONLY": 0,
        "T5_UNKNOWN": 0,
    }
    for c in candidates:
        label = c.get("pair_age_context_label")
        if label in label_counts:
            label_counts[label] += 1
        tier = c.get("token_age_evidence_tier")
        if tier in ("T1", "T2", "T3"):
            tier_counts[tier] += 1
        elif c.get("pair_age_seconds") is not None:
            tier_counts["T4_PAIR_ONLY"] += 1
        else:
            tier_counts["T5_UNKNOWN"] += 1
    return {
        "pair_age_context_label_counts": label_counts,
        "token_age_evidence_tier_counts": tier_counts,
        "tok_age_known_count": sum(1 for c in candidates if c.get("token_age_seconds") is not None),
        "pair_age_known_count": sum(1 for c in candidates if c.get("pair_age_seconds") is not None),
        "total_candidates": len(candidates),
    }


# ---------------------------------------------------------------------------
# Within-response duplicate / STNP filter (V2-2H.4)
# ---------------------------------------------------------------------------

_MIGRATION_CHANNELS: frozenset[str] = frozenset({
    "PUMPFUN_MIGRATION",
    "PUMPSWAP_GRADUATED",
    "PUMPSWAP_MIGRATION_POOL_REFERENCE",
})


def _classify_within_response_stnp(candidate: dict[str, Any]) -> str | None:
    """Attempt STNP classification for a within-response duplicate-mint candidate.

    Returns an STNP_* constant when a safe classification can be derived from
    the candidate's own data, or None (unresolved) when it cannot.
    Errs heavily toward None — within-response STNP is only safe to allow if
    the source channel unambiguously signals a known migration event.
    """
    source_channel = candidate.get("source_channel") or ""
    if source_channel in _MIGRATION_CHANNELS:
        return STNP_MIGRATION
    return None


def filter_within_response_duplicates(
    candidates: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], dict[str, Any]]:
    """Detect and reject within-response duplicate pair addresses and duplicate mints.

    First valid occurrence of each pair_address and token_mint passes through.
    Subsequent occurrences are rejected with explicit reasons and surfaced in
    the returned report — never silently dropped.

    Same-token/new-pair (STNP) classification reuses existing V2-2C gate logic
    via classify_same_token_new_pair(). If classification is unresolved or the
    gate would block persistence, the candidate is rejected.

    Returns:
        clean_candidates  — candidates cleared to proceed to normal gates
        rejected_candidates — candidates rejected at this stage (never persisted)
        within_response_integrity_report — count dict + rejection detail lists
    """
    seen_pair_addresses: set[str] = set()
    seen_mints: set[str] = set()

    clean: list[dict[str, Any]] = []
    rejected: list[dict[str, Any]] = []

    dup_pair_count = 0
    dup_mint_count = 0
    stnp_event_count = 0
    stnp_rejection_details: list[dict[str, Any]] = []
    dup_rejection_details: list[dict[str, Any]] = []

    for candidate in candidates:
        pair_address = candidate.get("pair_address") or ""
        token_mint = candidate.get("token_mint") or ""

        reject_reason: str | None = None
        stnp_classification: str | None = None

        if pair_address and pair_address in seen_pair_addresses:
            # Same pair_address seen earlier in this response.
            reject_reason = REJECTION_PAIR_DUPLICATE_WITHIN_RESPONSE
            dup_pair_count += 1
        elif token_mint and token_mint in seen_mints:
            # Same mint seen earlier with a different pair_address — STNP event.
            stnp_event_count += 1
            dup_mint_count += 1
            stnp_classification = _classify_within_response_stnp(candidate)
            ok, gate_reason = classify_same_token_new_pair(stnp_classification, same_token_new_pair=True)
            if not ok:
                # Map gate reasons to within-response variants where applicable.
                reject_reason = (
                    REJECTION_STNP_WITHIN_RESPONSE_UNRESOLVED
                    if gate_reason == REJECTION_STNP_UNRESOLVED
                    else gate_reason
                )

        # Track first-seen occurrences only.
        if pair_address:
            seen_pair_addresses.add(pair_address)
        if token_mint:
            seen_mints.add(token_mint)

        if reject_reason:
            detail: dict[str, Any] = {
                "token_mint": token_mint or None,
                "pair_address": pair_address or None,
                "reject_reason": reject_reason,
                "stnp_classification": stnp_classification,
            }
            rejected.append({**candidate, **detail})
            if reject_reason == REJECTION_PAIR_DUPLICATE_WITHIN_RESPONSE:
                dup_rejection_details.append(detail)
            else:
                stnp_rejection_details.append(detail)
        else:
            clean.append(candidate)

    report: dict[str, Any] = {
        "within_response_duplicate_pair_count": dup_pair_count,
        "within_response_duplicate_mint_count": dup_mint_count,
        "within_response_stnp_event_count": stnp_event_count,
        "within_response_stnp_rejections": stnp_rejection_details,
        "within_response_duplicate_rejections": dup_rejection_details,
    }
    return clean, rejected, report


# ---------------------------------------------------------------------------
# Same-token/new-pair classification gate
# ---------------------------------------------------------------------------

def classify_same_token_new_pair(
    classification: str | None,
    same_token_new_pair: bool,
) -> tuple[bool, str]:
    """Validate same-token/new-pair state.

    Returns (ok, rejection_reason).
    ok=True means the item may proceed to batch selection.
    ok=False means the item must be rejected with the given reason.
    """
    if not same_token_new_pair:
        return True, ""
    if classification is None:
        return False, REJECTION_STNP_UNRESOLVED
    if classification not in ALLOWED_STNP_CLASSIFICATIONS:
        return False, REJECTION_STNP_UNRESOLVED
    if classification == STNP_PAIR_DRIFT:
        return False, REJECTION_PAIR_DRIFT_UNRESOLVED
    if classification == STNP_DUPLICATE_RECYCLE:
        return False, REJECTION_PAIR_DUPLICATE
    return True, ""


# ---------------------------------------------------------------------------
# Cooldown / archive / reopen gate
# ---------------------------------------------------------------------------

def check_cooldown_archive_gate(
    lifecycle_state: str | None,
    cooldown_reopened: bool,
    cooldown_reopen_reason: str | None,
) -> tuple[bool, str]:
    """Return (ok, rejection_reason) for lifecycle state gate.

    COOLDOWN without approved reopen → reject.
    ARCHIVED without explicit reopen → reject.
    cooldown_reopened=True without cooldown_reopen_reason → reject.
    """
    if lifecycle_state in {"COOLDOWN", "ARCHIVED"}:
        if not cooldown_reopened:
            if lifecycle_state == "COOLDOWN":
                return False, REJECTION_ACTIVE_COOLDOWN
            return False, REJECTION_ARCHIVED_NO_REOPEN
        if not cooldown_reopen_reason:
            return False, REJECTION_ACTIVE_COOLDOWN
    return True, ""


# ---------------------------------------------------------------------------
# WATCH_ONLY promotion gate
# ---------------------------------------------------------------------------

def check_watch_only_promotion_gate(
    tracking_lane: str | None,
    discovery_action: str | None,
) -> tuple[bool, str]:
    """Block silent WATCH_ONLY → TRACK_FAST or TRACK_NORMAL promotion.

    A WATCH_ONLY token may only move to TRACK_FAST or TRACK_NORMAL through
    a new discovery classification that sets discovery_action accordingly.
    If discovery_action is still WATCH_ONLY but tracking_lane is not, block.

    Returns (ok, reason). ok=True means the lane assignment is valid.
    """
    is_fast_or_normal = tracking_lane in {"TRACK_FAST", "TRACK_NORMAL"}
    is_watch_only_discovery = discovery_action in {"WATCH_ONLY", None}
    if is_fast_or_normal and is_watch_only_discovery:
        return False, "WATCH_ONLY_SILENT_PROMOTION_BLOCKED"
    return True, ""


# ---------------------------------------------------------------------------
# Batch quota validation
# ---------------------------------------------------------------------------

def validate_batch_quota(
    items: list[dict[str, Any]],
    *,
    min_corpus_episodes: int = 0,
) -> tuple[bool, list[str]]:
    """Validate a proposed list of SELECTED batch items against quota rules.

    items must contain dicts with at least:
      - primary_bucket: str
      - tracking_lane: str
      - token_mint: str
      - pair_address: str

    Returns (ok, violations) where violations is a list of reason strings.
    ok=True only when violations is empty.

    Quota rules (from V2-2B Section 5):
      - No duplicate token mints.
      - No duplicate pair addresses.
      - If 6+ items: at least 1 D1 (DEAD_TOKEN).
      - If Group A present: at least 1 trap/failure/wick bucket (A2/A3/A4).
      - A1 (FAST_PUMP_FOLLOW) cap: max 2.
      - If 6+ items: at least 1 WATCH_ONLY token.
      - If 6+ items: at least 1 Group B or D token.
      - Group F buckets require minimum corpus size.
    """
    violations: list[str] = []
    n = len(items)

    mints = [i.get("token_mint", "") for i in items]
    pairs = [i.get("pair_address", "") for i in items]
    if len(set(mints)) < len(mints):
        violations.append("DUPLICATE_MINT_IN_BATCH")
    if len(set(pairs)) < len(pairs):
        violations.append("DUPLICATE_PAIR_IN_BATCH")

    buckets = [i.get("primary_bucket", "") for i in items]
    lanes = [i.get("tracking_lane", "") for i in items]

    a1_count = buckets.count(BUCKET_A1)
    if a1_count > 2:
        violations.append("WINNER_CAP_EXCEEDED_A1_MAX_2")

    group_a_present = any(b in GROUP_A_BUCKETS for b in buckets)
    has_trap_failure = any(b in TRAP_FAILURE_BUCKETS for b in buckets)
    if group_a_present and not has_trap_failure:
        violations.append("GROUP_A_PRESENT_BUT_NO_TRAP_FAILURE_BUCKET")

    if n >= 6:
        if not any(b == BUCKET_D1 for b in buckets):
            violations.append("MISSING_D1_DEAD_TOKEN_REQUIRED_FOR_6PLUS_BATCH")
        if not any(la == "WATCH_ONLY" for la in lanes):
            violations.append("MISSING_WATCH_ONLY_REQUIRED_FOR_6PLUS_BATCH")
        has_group_b_or_d = any(b in GROUP_B_BUCKETS or b in GROUP_D_BUCKETS for b in buckets)
        if not has_group_b_or_d:
            violations.append("NO_GROUP_B_OR_D_TOKEN_IN_BATCH")

    if any(b in GROUP_F_BUCKETS for b in buckets):
        if min_corpus_episodes < GROUP_F_MINIMUM_CORPUS_EPISODES:
            violations.append(
                f"GROUP_F_REQUIRES_{GROUP_F_MINIMUM_CORPUS_EPISODES}_CLEAN_EPISODES"
            )

    return len(violations) == 0, violations


# ---------------------------------------------------------------------------
# Candidate-universe summary
# ---------------------------------------------------------------------------

def build_candidate_universe_summary(
    all_candidates: list[dict[str, Any]],
    selected_items: list[dict[str, Any]],
    rejected_items: list[dict[str, Any]],
) -> dict[str, Any]:
    """Build a pool-level summary dict for a selection batch.

    Inputs:
      all_candidates  — full list of considered candidates (may include
                        both selected and rejected).
      selected_items  — items that passed all gates and quota.
      rejected_items  — items that failed at least one gate.

    Returns a summary dict suitable for storage in pool_summary_json and
    for report output. All counts are categorical/count-based only.
    """
    total = len(all_candidates)
    unclassified = total - len(selected_items) - len(rejected_items)
    unclassified = max(0, unclassified)

    by_source: dict[str, int] = {}
    by_channel: dict[str, int] = {}
    by_discovery_action: dict[str, int] = {}
    by_bucket: dict[str, int] = {}
    by_lane: dict[str, int] = {}
    by_asset_class: dict[str, int] = {}

    for c in all_candidates:
        src = c.get("source_name") or "unknown"
        by_source[src] = by_source.get(src, 0) + 1

        ch = c.get("source_channel") or "unknown"
        by_channel[ch] = by_channel.get(ch, 0) + 1

        da = c.get("discovery_action") or c.get("tracking_lane") or "unknown"
        by_discovery_action[da] = by_discovery_action.get(da, 0) + 1

        bucket_id = c.get("primary_bucket") or "unassigned"
        by_bucket[bucket_id] = by_bucket.get(bucket_id, 0) + 1

        lane = c.get("tracking_lane") or "unknown"
        by_lane[lane] = by_lane.get(lane, 0) + 1

        ac = c.get("asset_class") or ASSET_CLASS_UNKNOWN_UNCLASSIFIED
        by_asset_class[ac] = by_asset_class.get(ac, 0) + 1

    by_rejection: dict[str, int] = {}
    for r in rejected_items:
        rr = r.get("rejection_reason") or "unknown"
        by_rejection[rr] = by_rejection.get(rr, 0) + 1

    diversity_notes: list[str] = []
    selected_buckets = [s.get("primary_bucket") for s in selected_items]
    if selected_buckets and all(b == BUCKET_A1 for b in selected_buckets if b):
        diversity_notes.append("all_selected_are_A1_winner_only_bias_risk")
    selected_d1 = sum(1 for b in selected_buckets if b == BUCKET_D1)
    if len(selected_items) >= 6 and selected_d1 == 0:
        diversity_notes.append("no_dead_token_selected_in_6plus_batch")
    selected_watch = [s for s in selected_items if s.get("tracking_lane") == "WATCH_ONLY"]
    if len(selected_items) >= 6 and not selected_watch:
        diversity_notes.append("no_watch_only_in_6plus_batch")

    quality_notes: list[str] = []
    no_source_trace = sum(1 for c in all_candidates if not c.get("source_response_id"))
    if no_source_trace > 0:
        quality_notes.append(f"{no_source_trace}_candidates_missing_source_trace")
    stale_count = sum(
        1 for r in rejected_items if r.get("rejection_reason") == REJECTION_STALE_SOURCE_DATA
    )
    if stale_count > 0:
        quality_notes.append(f"{stale_count}_candidates_rejected_stale_source")

    return {
        "candidate_pool_total": total,
        "selected_count": len(selected_items),
        "rejected_count": len(rejected_items),
        "unavailable_or_unclassified_count": unclassified,
        "candidate_pool_by_source": by_source,
        "candidate_pool_by_source_channel": by_channel,
        "candidate_pool_by_discovery_action": by_discovery_action,
        "candidate_pool_by_bucket": by_bucket,
        "candidate_pool_by_tracking_lane": by_lane,
        "candidate_pool_by_asset_class": by_asset_class,
        "candidate_pool_by_rejection_reason": by_rejection,
        "pool_diversity_notes": diversity_notes,
        "pool_quality_notes": quality_notes,
    }


# ---------------------------------------------------------------------------
# Candidate metadata extraction
# ---------------------------------------------------------------------------

_METADATA_FIELDS = (
    "asset_class",
    "asset_class_reason",
    "discovery_reason",
    "token_created_at",
    "pair_created_at",
    "token_age_seconds",
    "pair_age_seconds",
    "price_usd",
    "liquidity_usd",
    "volume_5m",
    "volume_15m",
    "volume_1h",
    "volume_24h",
    "txns_5m",
    "txns_1h",
    "price_change_5m",
    "price_change_15m",
    "price_change_1h",
    "price_change_24h",
    "fdv",
    "market_cap",
    "fdv_liquidity_ratio",
    "volume_liquidity_ratio",
    "boost_status",
    "migration_status",
    "safety_label",
    "exit_realism_state",
    "source_status",
    "data_quality_label",
    # V2-2P: T4-safe pair-age context metadata. Never drives age gates or A3.
    "pair_age_context_label",
    "token_age_evidence_tier",
)


def extract_candidate_metadata(candidate: dict[str, Any]) -> dict[str, Any]:
    """Extract market-structure and asset-class metadata from a candidate dict."""
    return {k: candidate.get(k) for k in _METADATA_FIELDS}


# ---------------------------------------------------------------------------
# Batch item builder
# ---------------------------------------------------------------------------

def build_batch_item(
    candidate: dict[str, Any],
    *,
    item_status: str,
    primary_bucket: str | None = None,
    bucket_name: str | None = None,
    asset_class: str | None = None,
    behavior_context_labels: list[str] | None = None,
    selection_reason: str | None = None,
    rejection_reason: str | None = None,
    tracking_lane: str | None = None,
    lane_rationale: str | None = None,
    same_token_new_pair: bool = False,
    same_token_new_pair_classification: str | None = None,
    operator_approved: bool = False,
    manual_override_reason: str | None = None,
    cooldown_reopened: bool = False,
    cooldown_reopen_reason: str | None = None,
) -> dict[str, Any]:
    """Assemble a batch item dict from a normalized candidate and gate results.

    This produces a dict suitable for insertion into printer_selection_batch_items
    or for in-memory batch assembly and reporting.
    """
    validated_labels: list[str] = []
    for label in (behavior_context_labels or []):
        if label in ALLOWED_BEHAVIOR_CONTEXT_LABELS:
            validated_labels.append(label)

    metadata = extract_candidate_metadata(candidate)

    return {
        "item_status": item_status,
        "token_id": candidate.get("token_id"),
        "pair_id": candidate.get("pair_id"),
        "token_mint": candidate.get("token_mint", ""),
        "pair_address": candidate.get("pair_address", ""),
        "chain": candidate.get("chain", "solana"),
        "primary_bucket": primary_bucket,
        "bucket_name": bucket_name,
        "asset_class": asset_class,
        "asset_class_reason": candidate.get("asset_class_reason"),
        "behavior_context_labels": json.dumps(validated_labels) if validated_labels else None,
        "selection_reason": selection_reason,
        "rejection_reason": rejection_reason,
        "tracking_lane": tracking_lane or candidate.get("tracking_lane"),
        "lane_rationale": lane_rationale,
        "source_name": candidate.get("source_name"),
        "source_channel": candidate.get("source_channel"),
        "source_request_id": candidate.get("source_request_id"),
        "source_response_id": candidate.get("source_response_id"),
        "discovery_candidate_id": candidate.get("discovery_candidate_id"),
        "same_token_new_pair": same_token_new_pair,
        "same_token_new_pair_classification": same_token_new_pair_classification,
        "operator_approved": operator_approved,
        "manual_override_reason": manual_override_reason,
        "selected_at": datetime.now(timezone.utc).isoformat() if item_status == ITEM_STATUS_SELECTED else None,
        "cooldown_reopened": cooldown_reopened,
        "cooldown_reopen_reason": cooldown_reopen_reason,
        "candidate_metadata_json": json.dumps(metadata),
    }


# ---------------------------------------------------------------------------
# Schema readiness check (V2-2H.1)
# ---------------------------------------------------------------------------
#
# The V2-2 live capacity audit (commit 01cba36) found that migration
# 025_selection_batch.sql was absent from a copy of the current live DB even
# though this module's persistence path depends on it, and the audit had to
# apply the migration to a proof DB copy as an ad hoc step to proceed. This
# check makes that dependency explicit and fails fast with a clear, actionable
# error instead of surfacing a raw "no such table" error from sqlite3, and
# instead of silently creating the schema. It never mutates the database.

_REQUIRED_SELECTION_BATCH_COLUMNS: dict[str, tuple[str, ...]] = {
    "printer_selection_batches": (
        "batch_id",
        "batch_status",
        "window_kind",
        "candidate_pool_total",
        "selected_count",
        "rejected_count",
        "unavailable_or_unclassified_count",
        "pool_summary_json",
        "pool_diversity_notes",
        "pool_quality_notes",
        "operator_approved",
    ),
    "printer_selection_batch_items": (
        "batch_id",
        "item_status",
        "token_id",
        "pair_id",
        "token_mint",
        "pair_address",
        "chain",
        "primary_bucket",
        "bucket_name",
        "asset_class",
        "asset_class_reason",
        "behavior_context_labels",
        "selection_reason",
        "rejection_reason",
        "tracking_lane",
        "lane_rationale",
        "source_name",
        "source_channel",
        "source_request_id",
        "source_response_id",
        "discovery_candidate_id",
        "same_token_new_pair",
        "same_token_new_pair_classification",
        "operator_approved",
        "manual_override_reason",
        "selected_at",
        "cooldown_reopened",
        "cooldown_reopen_reason",
        "candidate_metadata_json",
    ),
}


class SelectionBatchSchemaNotReadyError(RuntimeError):
    """Raised when the selection-batch schema is missing or incomplete.

    This means migration 025_selection_batch.sql has not been applied (or was
    only partially applied) to the target database.
    """


def check_selection_batch_schema_ready(
    db_or_connection: str | Path | sqlite3.Connection,
) -> None:
    """Fail-fast readiness check for the selection-batch schema.

    Confirms both `printer_selection_batches` and `printer_selection_batch_items`
    exist and contain the critical columns this module's persistence path
    depends on. Raises `SelectionBatchSchemaNotReadyError` with a clear,
    actionable message if not.

    Read-only: never mutates the database, never creates tables, and never
    applies a migration. Callers are responsible for applying
    `migrations/025_selection_batch.sql` through the normal migration path
    before selection-batch persistence is attempted.
    """
    own_connection = not isinstance(db_or_connection, sqlite3.Connection)
    if own_connection:
        conn = sqlite3.connect(f"file:{Path(db_or_connection)}?mode=ro", uri=True)
        conn.execute("PRAGMA query_only = ON")
    else:
        conn = db_or_connection

    try:
        existing_tables = {
            row[0]
            for row in conn.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table'"
            ).fetchall()
        }
        missing_tables = [
            table
            for table in _REQUIRED_SELECTION_BATCH_COLUMNS
            if table not in existing_tables
        ]
        if missing_tables:
            raise SelectionBatchSchemaNotReadyError(
                "selection-batch schema is not ready: missing table(s) "
                f"{missing_tables}. migrations/025_selection_batch.sql has not "
                "been applied to this database. Apply the migration through "
                "the normal migration path before running selection-batch "
                "operations; this check does not apply migrations or create "
                "tables automatically."
            )

        missing_columns: dict[str, list[str]] = {}
        for table, required_columns in _REQUIRED_SELECTION_BATCH_COLUMNS.items():
            existing_columns = {
                row[1] for row in conn.execute(f"PRAGMA table_info({table})").fetchall()
            }
            missing = [c for c in required_columns if c not in existing_columns]
            if missing:
                missing_columns[table] = missing
        if missing_columns:
            raise SelectionBatchSchemaNotReadyError(
                "selection-batch schema is not ready: missing critical "
                f"column(s) {missing_columns}. migrations/025_selection_batch.sql "
                "may be partially applied or out of date on this database."
            )
    finally:
        if own_connection:
            conn.close()


# ---------------------------------------------------------------------------
# DB persistence
# ---------------------------------------------------------------------------

def _connect(db_or_connection: str | Path | sqlite3.Connection) -> sqlite3.Connection:
    if isinstance(db_or_connection, sqlite3.Connection):
        return db_or_connection
    conn = sqlite3.connect(Path(db_or_connection))
    conn.execute("PRAGMA foreign_keys = ON")
    conn.row_factory = sqlite3.Row
    return conn


def persist_selection_batch(
    db_or_connection: str | Path | sqlite3.Connection,
    batch_id: str | None,
    items: list[dict[str, Any]],
    universe_summary: dict[str, Any] | None = None,
    *,
    operator_approved: bool = False,
    window_kind: str = "WINDOW_15M",
    pool_diversity_notes: str | None = None,
    pool_quality_notes: str | None = None,
) -> dict[str, Any]:
    """Persist a selection batch and its items to the DB.

    Returns a summary dict with batch_id, row counts, and status.

    This function does not run discovery, fetch sources, generate memory,
    activate retrieval, create paper decisions, or unlock any financial
    capability.
    """
    _batch_id = batch_id or str(uuid.uuid4())
    selected = [i for i in items if i.get("item_status") == ITEM_STATUS_SELECTED]
    rejected = [i for i in items if i.get("item_status") == ITEM_STATUS_REJECTED]
    unclassified = [i for i in items if i.get("item_status") == ITEM_STATUS_UNCLASSIFIED]

    summary = universe_summary or {}
    pool_json = json.dumps(summary)

    own_connection = not isinstance(db_or_connection, sqlite3.Connection)
    conn = _connect(db_or_connection)
    try:
        check_selection_batch_schema_ready(conn)
        conn.execute(
            """
            INSERT INTO printer_selection_batches
              (batch_id, batch_status, window_kind,
               candidate_pool_total, selected_count, rejected_count,
               unavailable_or_unclassified_count,
               pool_summary_json, pool_diversity_notes, pool_quality_notes,
               operator_approved)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                _batch_id,
                BATCH_STATUS_ASSEMBLED,
                window_kind,
                summary.get("candidate_pool_total", len(items)),
                len(selected),
                len(rejected),
                len(unclassified),
                pool_json,
                pool_diversity_notes,
                pool_quality_notes,
                1 if operator_approved else 0,
            ),
        )

        for item in items:
            conn.execute(
                """
                INSERT INTO printer_selection_batch_items
                  (batch_id, item_status, token_id, pair_id,
                   token_mint, pair_address, chain,
                   primary_bucket, bucket_name, asset_class, asset_class_reason,
                   behavior_context_labels,
                   selection_reason, rejection_reason,
                   tracking_lane, lane_rationale,
                   source_name, source_channel,
                   source_request_id, source_response_id, discovery_candidate_id,
                   same_token_new_pair, same_token_new_pair_classification,
                   operator_approved, manual_override_reason,
                   selected_at, cooldown_reopened, cooldown_reopen_reason,
                   candidate_metadata_json)
                VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                """,
                (
                    _batch_id,
                    item.get("item_status", ITEM_STATUS_UNCLASSIFIED),
                    item.get("token_id"),
                    item.get("pair_id"),
                    item.get("token_mint", ""),
                    item.get("pair_address", ""),
                    item.get("chain", "solana"),
                    item.get("primary_bucket"),
                    item.get("bucket_name"),
                    item.get("asset_class"),
                    item.get("asset_class_reason"),
                    item.get("behavior_context_labels"),
                    item.get("selection_reason"),
                    item.get("rejection_reason"),
                    item.get("tracking_lane"),
                    item.get("lane_rationale"),
                    item.get("source_name"),
                    item.get("source_channel"),
                    item.get("source_request_id"),
                    item.get("source_response_id"),
                    item.get("discovery_candidate_id"),
                    1 if item.get("same_token_new_pair") else 0,
                    item.get("same_token_new_pair_classification"),
                    1 if item.get("operator_approved") else 0,
                    item.get("manual_override_reason"),
                    item.get("selected_at"),
                    1 if item.get("cooldown_reopened") else 0,
                    item.get("cooldown_reopen_reason"),
                    item.get("candidate_metadata_json"),
                ),
            )

        if own_connection:
            conn.commit()

        return {
            "batch_id": _batch_id,
            "batch_status": BATCH_STATUS_ASSEMBLED,
            "selected_count": len(selected),
            "rejected_count": len(rejected),
            "unclassified_count": len(unclassified),
            "total_items": len(items),
        }
    finally:
        if own_connection:
            conn.close()
