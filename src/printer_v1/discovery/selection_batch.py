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
        if price_change_5m <= _WICK_PRICE_CHANGE_REVERSAL_PCT and volume_5m >= _VOLUME_FAST_5M_USD:
            return BUCKET_A2, BUCKET_NAMES[BUCKET_A2]
        if token_age >= _LATE_BUY_TOKEN_AGE_SECONDS and price_change_1h < 0:
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
