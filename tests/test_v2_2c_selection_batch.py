"""V2-2C selection-batch unit tests.

Tests cover:
  - bucket assignment (all groups)
  - asset-class derivation
  - behavior-context label validation (categorical only)
  - same-token/new-pair classification gates
  - cooldown/archive/reopen gates
  - WATCH_ONLY silent-promotion gate
  - batch quota validation
  - selection/rejection reason persistence
  - duplicate mint/pair rejection
  - candidate-universe summary output
  - DB persistence (via in-memory SQLite + migrations)
  - no score/rank/confidence/weighted logic
  - no BUY/paper/PnL/retrieval side effects

All tests use fixtures only. No live discovery, source fetching,
DB mutation against the live DB, memory generation, retrieval,
paper decisions, or financial rows.
"""

import json
import pathlib
import sqlite3
import sys
import tempfile
import unittest

PROJECT_ROOT = pathlib.Path(__file__).resolve().parents[1]
SRC_PATH = PROJECT_ROOT / "src"
sys.path.insert(0, str(SRC_PATH))

from printer_v1.db import apply_migrations
from printer_v1.discovery.selection_batch import (
    # Buckets
    BUCKET_A1, BUCKET_A2, BUCKET_A3, BUCKET_A4,
    BUCKET_B1, BUCKET_B2, BUCKET_B3, BUCKET_B4, BUCKET_B5,
    BUCKET_C1, BUCKET_C2, BUCKET_C3,
    BUCKET_D1, BUCKET_D2, BUCKET_D3, BUCKET_D4,
    BUCKET_E1, BUCKET_E2,
    BUCKET_F1, BUCKET_F2,
    BUCKET_NAMES,
    GROUP_A_BUCKETS, GROUP_B_BUCKETS, GROUP_C_BUCKETS,
    GROUP_D_BUCKETS, GROUP_E_BUCKETS, GROUP_F_BUCKETS,
    TRAP_FAILURE_BUCKETS,
    # Asset classes
    ALLOWED_ASSET_CLASSES,
    ASSET_CLASS_UNKNOWN_UNCLASSIFIED,
    ASSET_CLASS_DEAD_TOKEN,
    ASSET_CLASS_FAST_PUMP,
    ASSET_CLASS_MIGRATED_TOKEN,
    # Behavior context labels
    ALLOWED_BEHAVIOR_CONTEXT_LABELS,
    BEHAVIOR_ATTENTION_SPIKE,
    BEHAVIOR_UNKNOWN_BEHAVIOR_CONTEXT,
    # STNP classifications
    ALLOWED_STNP_CLASSIFICATIONS,
    STNP_MIGRATION, STNP_REVIVAL, STNP_PAIR_DRIFT,
    STNP_DUPLICATE_RECYCLE, STNP_DISTINCT_EVIDENCE,
    # Rejection reasons
    REJECTION_MINT_DUPLICATE, REJECTION_PAIR_DUPLICATE,
    REJECTION_ACTIVE_COOLDOWN, REJECTION_ARCHIVED_NO_REOPEN,
    REJECTION_STNP_UNRESOLVED, REJECTION_PAIR_DRIFT_UNRESOLVED,
    REJECTION_GROUP_F_CORPUS_TOO_SMALL,
    # Item / batch status
    ITEM_STATUS_SELECTED, ITEM_STATUS_REJECTED, ITEM_STATUS_UNCLASSIFIED,
    BATCH_STATUS_ASSEMBLED,
    # Functions
    assign_bucket,
    derive_asset_class,
    classify_same_token_new_pair,
    check_cooldown_archive_gate,
    check_watch_only_promotion_gate,
    validate_batch_quota,
    build_candidate_universe_summary,
    build_batch_item,
    persist_selection_batch,
    extract_candidate_metadata,
    GROUP_F_MINIMUM_CORPUS_EPISODES,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_db() -> sqlite3.Connection:
    """Return an in-memory SQLite connection with all migrations applied."""
    with tempfile.NamedTemporaryFile(suffix=".sqlite3", delete=False) as f:
        db_path = f.name
    apply_migrations(db_path)
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    return conn


def _fast_candidate(**overrides: object) -> dict:
    base = {
        "token_mint": "MintAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA",
        "pair_address": "PairAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA",
        "chain": "solana",
        "source_name": "dexscreener",
        "source_channel": "DEXSCREENER_SEARCH",
        "tracking_lane": "TRACK_FAST",
        "discovery_action": "TRACK_FAST",
        "liquidity_usd": 10_000.0,
        "volume_5m": 2_000.0,
        "volume_1h": 20_000.0,
        "volume_24h": 80_000.0,
        "txns_5m": 20,
        "txns_1h": 80,
        "txns_24h": 300,
        "price_usd": 0.001,
        "price_change_5m": 5.0,
        "price_change_1h": 15.0,
        "price_change_24h": 30.0,
        "token_age_seconds": 600.0,
        "safety_label": "SAFE",
        "source_response_id": 1,
    }
    base.update(overrides)
    return base


def _dead_candidate(**overrides: object) -> dict:
    base = {
        "token_mint": "MintDEADAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA",
        "pair_address": "PairDEADAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA",
        "chain": "solana",
        "source_name": "dexscreener",
        "tracking_lane": "WATCH_ONLY",
        "discovery_action": "WATCH_ONLY",
        "liquidity_usd": 50.0,
        "volume_5m": 0.0,
        "volume_1h": 0.0,
        "volume_24h": 5.0,
        "txns_5m": 0,
        "txns_1h": 0,
        "txns_24h": 1,
        "price_usd": 0.000001,
        "price_change_5m": 0.0,
        "price_change_1h": 0.0,
        "price_change_24h": -95.0,
        "token_age_seconds": 86400.0,
        "safety_label": "SAFE",
        "source_response_id": 2,
    }
    base.update(overrides)
    return base


def _normal_candidate(**overrides: object) -> dict:
    base = {
        "token_mint": "MintNORMALAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA",
        "pair_address": "PairNORMALAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA",
        "chain": "solana",
        "source_name": "geckoterminal",
        "source_channel": "GECKOTERMINAL_NEW_POOL",
        "tracking_lane": "TRACK_NORMAL",
        "discovery_action": "TRACK_NORMAL",
        "liquidity_usd": 3_000.0,
        "volume_5m": 0.0,
        "volume_1h": 500.0,
        "volume_24h": 5_000.0,
        "txns_5m": 0,
        "txns_1h": 10,
        "txns_24h": 40,
        "price_usd": 0.0005,
        "price_change_5m": 0.0,
        "price_change_1h": 2.0,
        "price_change_24h": 5.0,
        "token_age_seconds": 7_200.0,
        "safety_label": "SAFE",
        "source_response_id": 3,
    }
    base.update(overrides)
    return base


def _selected_item(mint: str, pair: str, bucket: str, lane: str) -> dict:
    return {
        "item_status": ITEM_STATUS_SELECTED,
        "token_mint": mint,
        "pair_address": pair,
        "primary_bucket": bucket,
        "tracking_lane": lane,
    }


# ---------------------------------------------------------------------------
# 1. Bucket assignment
# ---------------------------------------------------------------------------

class TestBucketAssignment(unittest.TestCase):

    def test_dead_token_d1(self):
        c = _dead_candidate()
        bucket_id, name = assign_bucket(c)
        self.assertEqual(bucket_id, BUCKET_D1)
        self.assertEqual(name, "DEAD_TOKEN")

    def test_liquidity_removed_c3(self):
        c = _normal_candidate(liquidity_usd=300.0)
        bucket_id, _ = assign_bucket(c)
        self.assertEqual(bucket_id, BUCKET_C3)

    def test_suspicious_safety_d4(self):
        c = _fast_candidate(safety_label="BLACKLISTED")
        bucket_id, _ = assign_bucket(c)
        self.assertEqual(bucket_id, BUCKET_D4)

    def test_migration_channel_d3(self):
        c = _fast_candidate(source_channel="PUMPFUN_MIGRATION")
        bucket_id, _ = assign_bucket(c)
        self.assertEqual(bucket_id, BUCKET_D3)

    def test_pumpswap_graduated_d3(self):
        c = _fast_candidate(source_channel="PUMPSWAP_GRADUATED")
        bucket_id, _ = assign_bucket(c)
        self.assertEqual(bucket_id, BUCKET_D3)

    def test_fast_pump_follow_a1(self):
        c = _fast_candidate(price_change_5m=5.0, token_age_seconds=300.0)
        bucket_id, _ = assign_bucket(c)
        self.assertEqual(bucket_id, BUCKET_A1)

    def test_wick_only_pump_a2(self):
        c = _fast_candidate(price_change_5m=-25.0, volume_5m=3_000.0)
        bucket_id, _ = assign_bucket(c)
        self.assertEqual(bucket_id, BUCKET_A2)

    def test_late_buy_trap_a3(self):
        c = _fast_candidate(
            token_age_seconds=7_200.0,
            price_change_1h=-15.0,
            price_change_5m=1.0,
        )
        bucket_id, _ = assign_bucket(c)
        self.assertEqual(bucket_id, BUCKET_A3)

    def test_volume_rising_b1(self):
        # price_change_1h must be > 0 but <= 10.0; > 10.0 triggers C1 instead
        c = _normal_candidate(price_change_1h=5.0)
        bucket_id, _ = assign_bucket(c)
        self.assertEqual(bucket_id, BUCKET_B1)

    def test_volume_decaying_b2(self):
        # price_change_1h must be < 0 but >= -10.0; < -10.0 triggers C2 instead
        c = _normal_candidate(price_change_1h=-5.0)
        bucket_id, _ = assign_bucket(c)
        self.assertEqual(bucket_id, BUCKET_B2)

    def test_transaction_spike_b3(self):
        c = _normal_candidate(txns_5m=15, volume_5m=100.0, liquidity_usd=3_000.0)
        bucket_id, _ = assign_bucket(c)
        self.assertEqual(bucket_id, BUCKET_B3)

    def test_transaction_decay_b4(self):
        c = _normal_candidate(
            volume_1h=0.0, txns_1h=0, volume_24h=500.0,
            txns_5m=0, volume_5m=0.0, price_change_1h=0.0
        )
        bucket_id, _ = assign_bucket(c)
        self.assertEqual(bucket_id, BUCKET_B4)

    def test_consolidation_b5(self):
        # price_change_1h=0.0 avoids B1 (requires > 0) and B2 (requires < 0)
        c = _normal_candidate(
            volume_1h=200.0, txns_1h=5, price_change_1h=0.0,
            txns_5m=0, volume_5m=0.0
        )
        bucket_id, _ = assign_bucket(c)
        self.assertEqual(bucket_id, BUCKET_B5)

    def test_liquidity_falling_c2_low_liquidity(self):
        c = _normal_candidate(liquidity_usd=600.0)
        bucket_id, _ = assign_bucket(c)
        self.assertEqual(bucket_id, BUCKET_C2)

    def test_liquidity_rising_c1(self):
        c = _normal_candidate(
            liquidity_usd=4_000.0,
            price_change_1h=15.0,
            txns_5m=0, volume_5m=0.0
        )
        bucket_id, _ = assign_bucket(c)
        self.assertEqual(bucket_id, BUCKET_C1)

    def test_bucket_ids_are_strings(self):
        for candidate in [_fast_candidate(), _dead_candidate(), _normal_candidate()]:
            bucket_id, name = assign_bucket(candidate)
            self.assertIsInstance(bucket_id, str)
            self.assertIsInstance(name, str)

    def test_assign_bucket_never_returns_float(self):
        candidates = [_fast_candidate(), _dead_candidate(), _normal_candidate()]
        for c in candidates:
            result = assign_bucket(c)
            self.assertIsInstance(result, tuple)
            self.assertEqual(len(result), 2)
            for part in result:
                self.assertNotIsInstance(part, float)
                self.assertNotIsInstance(part, int)

    def test_all_bucket_ids_in_names_map(self):
        for bucket_id in [
            BUCKET_A1, BUCKET_A2, BUCKET_A3, BUCKET_A4,
            BUCKET_B1, BUCKET_B2, BUCKET_B3, BUCKET_B4, BUCKET_B5,
            BUCKET_C1, BUCKET_C2, BUCKET_C3,
            BUCKET_D1, BUCKET_D2, BUCKET_D3, BUCKET_D4,
            BUCKET_E1, BUCKET_E2,
        ]:
            self.assertIn(bucket_id, BUCKET_NAMES)
            self.assertIsInstance(BUCKET_NAMES[bucket_id], str)


# ---------------------------------------------------------------------------
# 2. Asset-class derivation
# ---------------------------------------------------------------------------

class TestAssetClassDerivation(unittest.TestCase):

    def test_a1_maps_to_fast_pump(self):
        self.assertEqual(derive_asset_class(BUCKET_A1), ASSET_CLASS_FAST_PUMP)

    def test_d1_maps_to_dead_token(self):
        self.assertEqual(derive_asset_class(BUCKET_D1), ASSET_CLASS_DEAD_TOKEN)

    def test_d3_maps_to_migrated(self):
        self.assertEqual(derive_asset_class(BUCKET_D3), ASSET_CLASS_MIGRATED_TOKEN)

    def test_unknown_bucket_returns_unknown(self):
        self.assertEqual(derive_asset_class("ZZ"), ASSET_CLASS_UNKNOWN_UNCLASSIFIED)

    def test_all_asset_classes_are_allowed(self):
        for bucket_id in BUCKET_NAMES:
            ac = derive_asset_class(bucket_id)
            self.assertIn(ac, ALLOWED_ASSET_CLASSES)

    def test_derive_asset_class_never_returns_score(self):
        for bucket_id in BUCKET_NAMES:
            result = derive_asset_class(bucket_id)
            self.assertIsInstance(result, str)
            self.assertNotIn("score", result.lower())
            self.assertNotIn("rank", result.lower())
            self.assertNotIn("confidence", result.lower())


# ---------------------------------------------------------------------------
# 3. Behavior-context label validation
# ---------------------------------------------------------------------------

class TestBehaviorContextLabels(unittest.TestCase):

    def test_valid_label_passes(self):
        item = build_batch_item(
            _fast_candidate(),
            item_status=ITEM_STATUS_SELECTED,
            behavior_context_labels=[BEHAVIOR_ATTENTION_SPIKE],
        )
        labels = json.loads(item["behavior_context_labels"])
        self.assertIn(BEHAVIOR_ATTENTION_SPIKE, labels)

    def test_invalid_label_stripped(self):
        item = build_batch_item(
            _fast_candidate(),
            item_status=ITEM_STATUS_SELECTED,
            behavior_context_labels=["BUY_SIGNAL_NOW", "RANK_HIGH"],
        )
        self.assertIsNone(item["behavior_context_labels"])

    def test_mixed_valid_invalid_only_valid_kept(self):
        item = build_batch_item(
            _fast_candidate(),
            item_status=ITEM_STATUS_SELECTED,
            behavior_context_labels=[BEHAVIOR_ATTENTION_SPIKE, "FAKE_LABEL"],
        )
        labels = json.loads(item["behavior_context_labels"])
        self.assertEqual(labels, [BEHAVIOR_ATTENTION_SPIKE])

    def test_no_behavior_label_field_is_none(self):
        item = build_batch_item(_fast_candidate(), item_status=ITEM_STATUS_SELECTED)
        self.assertIsNone(item["behavior_context_labels"])

    def test_behavior_labels_are_not_numeric(self):
        for label in ALLOWED_BEHAVIOR_CONTEXT_LABELS:
            self.assertIsInstance(label, str)
            try:
                float(label)
                self.fail(f"Behavior label {label!r} looks numeric")
            except ValueError:
                pass

    def test_unknown_behavior_context_is_allowed(self):
        item = build_batch_item(
            _fast_candidate(),
            item_status=ITEM_STATUS_SELECTED,
            behavior_context_labels=[BEHAVIOR_UNKNOWN_BEHAVIOR_CONTEXT],
        )
        labels = json.loads(item["behavior_context_labels"])
        self.assertIn(BEHAVIOR_UNKNOWN_BEHAVIOR_CONTEXT, labels)


# ---------------------------------------------------------------------------
# 4. Same-token/new-pair classification gate
# ---------------------------------------------------------------------------

class TestSameTokenNewPairGate(unittest.TestCase):

    def test_not_stnp_always_ok(self):
        ok, reason = classify_same_token_new_pair(None, False)
        self.assertTrue(ok)
        self.assertEqual(reason, "")

    def test_stnp_none_classification_blocked(self):
        ok, reason = classify_same_token_new_pair(None, True)
        self.assertFalse(ok)
        self.assertEqual(reason, REJECTION_STNP_UNRESOLVED)

    def test_stnp_unknown_classification_blocked(self):
        ok, reason = classify_same_token_new_pair("SOMETHING_ELSE", True)
        self.assertFalse(ok)
        self.assertEqual(reason, REJECTION_STNP_UNRESOLVED)

    def test_pair_drift_blocked(self):
        ok, reason = classify_same_token_new_pair(STNP_PAIR_DRIFT, True)
        self.assertFalse(ok)
        self.assertEqual(reason, REJECTION_PAIR_DRIFT_UNRESOLVED)

    def test_duplicate_recycle_blocked(self):
        ok, reason = classify_same_token_new_pair(STNP_DUPLICATE_RECYCLE, True)
        self.assertFalse(ok)
        self.assertEqual(reason, REJECTION_PAIR_DUPLICATE)

    def test_migration_allowed(self):
        ok, _ = classify_same_token_new_pair(STNP_MIGRATION, True)
        self.assertTrue(ok)

    def test_revival_allowed(self):
        ok, _ = classify_same_token_new_pair(STNP_REVIVAL, True)
        self.assertTrue(ok)

    def test_distinct_evidence_allowed(self):
        ok, _ = classify_same_token_new_pair(STNP_DISTINCT_EVIDENCE, True)
        self.assertTrue(ok)

    def test_all_allowed_classifications_pass(self):
        for cls in ALLOWED_STNP_CLASSIFICATIONS:
            if cls in {STNP_PAIR_DRIFT, STNP_DUPLICATE_RECYCLE}:
                continue
            ok, reason = classify_same_token_new_pair(cls, True)
            self.assertTrue(ok, f"{cls} should be allowed but got reason={reason}")


# ---------------------------------------------------------------------------
# 5. Cooldown / archive / reopen gate
# ---------------------------------------------------------------------------

class TestCooldownArchiveGate(unittest.TestCase):

    def test_active_state_ok(self):
        ok, _ = check_cooldown_archive_gate("ACTIVE", False, None)
        self.assertTrue(ok)

    def test_queued_state_ok(self):
        ok, _ = check_cooldown_archive_gate("QUEUED", False, None)
        self.assertTrue(ok)

    def test_none_state_ok(self):
        ok, _ = check_cooldown_archive_gate(None, False, None)
        self.assertTrue(ok)

    def test_cooldown_without_reopen_blocked(self):
        ok, reason = check_cooldown_archive_gate("COOLDOWN", False, None)
        self.assertFalse(ok)
        self.assertEqual(reason, REJECTION_ACTIVE_COOLDOWN)

    def test_archived_without_reopen_blocked(self):
        ok, reason = check_cooldown_archive_gate("ARCHIVED", False, None)
        self.assertFalse(ok)
        self.assertEqual(reason, REJECTION_ARCHIVED_NO_REOPEN)

    def test_cooldown_with_reopen_and_reason_ok(self):
        ok, _ = check_cooldown_archive_gate("COOLDOWN", True, "new_pool_found")
        self.assertTrue(ok)

    def test_cooldown_with_reopen_but_no_reason_blocked(self):
        ok, reason = check_cooldown_archive_gate("COOLDOWN", True, None)
        self.assertFalse(ok)
        self.assertEqual(reason, REJECTION_ACTIVE_COOLDOWN)

    def test_archived_with_reopen_and_reason_ok(self):
        ok, _ = check_cooldown_archive_gate("ARCHIVED", True, "revival_detected")
        self.assertTrue(ok)


# ---------------------------------------------------------------------------
# 6. WATCH_ONLY promotion gate
# ---------------------------------------------------------------------------

class TestWatchOnlyPromotionGate(unittest.TestCase):

    def test_watch_only_lane_from_watch_only_discovery_ok(self):
        ok, _ = check_watch_only_promotion_gate("WATCH_ONLY", "WATCH_ONLY")
        self.assertTrue(ok)

    def test_track_fast_from_track_fast_discovery_ok(self):
        ok, _ = check_watch_only_promotion_gate("TRACK_FAST", "TRACK_FAST")
        self.assertTrue(ok)

    def test_track_normal_from_track_normal_discovery_ok(self):
        ok, _ = check_watch_only_promotion_gate("TRACK_NORMAL", "TRACK_NORMAL")
        self.assertTrue(ok)

    def test_track_fast_with_watch_only_discovery_blocked(self):
        ok, reason = check_watch_only_promotion_gate("TRACK_FAST", "WATCH_ONLY")
        self.assertFalse(ok)
        self.assertIn("WATCH_ONLY", reason)

    def test_track_normal_with_watch_only_discovery_blocked(self):
        ok, reason = check_watch_only_promotion_gate("TRACK_NORMAL", "WATCH_ONLY")
        self.assertFalse(ok)
        self.assertIn("WATCH_ONLY", reason)

    def test_track_fast_with_none_discovery_blocked(self):
        ok, _ = check_watch_only_promotion_gate("TRACK_FAST", None)
        self.assertFalse(ok)

    def test_watch_only_never_creates_memory_flag(self):
        # WATCH_ONLY lane does not create WINDOW_15M — validated by gate
        ok, _ = check_watch_only_promotion_gate("WATCH_ONLY", "WATCH_ONLY")
        # OK to keep as WATCH_ONLY; the runner must not create windows (tested separately)
        self.assertTrue(ok)


# ---------------------------------------------------------------------------
# 7. Batch quota validation
# ---------------------------------------------------------------------------

class TestBatchQuotaValidation(unittest.TestCase):

    def _six_item_batch(self) -> list[dict]:
        return [
            _selected_item("MintA", "PairA", BUCKET_A1, "TRACK_FAST"),
            _selected_item("MintB", "PairB", BUCKET_A2, "TRACK_FAST"),
            _selected_item("MintC", "PairC", BUCKET_B2, "TRACK_NORMAL"),
            _selected_item("MintD", "PairD", BUCKET_D1, "WATCH_ONLY"),
            _selected_item("MintE", "PairE", BUCKET_B1, "TRACK_NORMAL"),
            _selected_item("MintF", "PairF", BUCKET_C2, "TRACK_NORMAL"),
        ]

    def test_valid_six_item_batch_passes(self):
        ok, violations = validate_batch_quota(self._six_item_batch())
        self.assertTrue(ok, violations)
        self.assertEqual(violations, [])

    def test_duplicate_mint_rejected(self):
        items = self._six_item_batch()
        items[1]["token_mint"] = items[0]["token_mint"]
        ok, violations = validate_batch_quota(items)
        self.assertFalse(ok)
        self.assertIn("DUPLICATE_MINT_IN_BATCH", violations)

    def test_duplicate_pair_rejected(self):
        items = self._six_item_batch()
        items[2]["pair_address"] = items[0]["pair_address"]
        ok, violations = validate_batch_quota(items)
        self.assertFalse(ok)
        self.assertIn("DUPLICATE_PAIR_IN_BATCH", violations)

    def test_a1_winner_cap_at_two(self):
        items = [
            _selected_item("MintA", "PairA", BUCKET_A1, "TRACK_FAST"),
            _selected_item("MintB", "PairB", BUCKET_A1, "TRACK_FAST"),
            _selected_item("MintC", "PairC", BUCKET_A1, "TRACK_FAST"),
            _selected_item("MintD", "PairD", BUCKET_D1, "WATCH_ONLY"),
            _selected_item("MintE", "PairE", BUCKET_B2, "TRACK_NORMAL"),
            _selected_item("MintF", "PairF", BUCKET_A2, "TRACK_FAST"),
        ]
        ok, violations = validate_batch_quota(items)
        self.assertFalse(ok)
        self.assertIn("WINNER_CAP_EXCEEDED_A1_MAX_2", violations)

    def test_group_a_without_trap_failure_rejected(self):
        items = [
            _selected_item("MintA", "PairA", BUCKET_A1, "TRACK_FAST"),
            _selected_item("MintB", "PairB", BUCKET_A1, "TRACK_FAST"),
            _selected_item("MintC", "PairC", BUCKET_B1, "TRACK_NORMAL"),
            _selected_item("MintD", "PairD", BUCKET_D1, "WATCH_ONLY"),
            _selected_item("MintE", "PairE", BUCKET_B2, "TRACK_NORMAL"),
            _selected_item("MintF", "PairF", BUCKET_C2, "TRACK_NORMAL"),
        ]
        ok, violations = validate_batch_quota(items)
        self.assertFalse(ok)
        self.assertIn("GROUP_A_PRESENT_BUT_NO_TRAP_FAILURE_BUCKET", violations)

    def test_missing_d1_in_six_plus_batch_rejected(self):
        items = [
            _selected_item("MintA", "PairA", BUCKET_A1, "TRACK_FAST"),
            _selected_item("MintB", "PairB", BUCKET_A2, "TRACK_FAST"),
            _selected_item("MintC", "PairC", BUCKET_B1, "TRACK_NORMAL"),
            _selected_item("MintD", "PairD", BUCKET_B2, "TRACK_NORMAL"),
            _selected_item("MintE", "PairE", BUCKET_B5, "TRACK_NORMAL"),
            _selected_item("MintF", "PairF", BUCKET_C2, "WATCH_ONLY"),
        ]
        ok, violations = validate_batch_quota(items)
        self.assertFalse(ok)
        self.assertIn("MISSING_D1_DEAD_TOKEN_REQUIRED_FOR_6PLUS_BATCH", violations)

    def test_missing_watch_only_in_six_plus_batch_rejected(self):
        items = [
            _selected_item("MintA", "PairA", BUCKET_A1, "TRACK_FAST"),
            _selected_item("MintB", "PairB", BUCKET_A2, "TRACK_FAST"),
            _selected_item("MintC", "PairC", BUCKET_D1, "TRACK_NORMAL"),
            _selected_item("MintD", "PairD", BUCKET_B2, "TRACK_NORMAL"),
            _selected_item("MintE", "PairE", BUCKET_B5, "TRACK_NORMAL"),
            _selected_item("MintF", "PairF", BUCKET_C2, "TRACK_NORMAL"),
        ]
        ok, violations = validate_batch_quota(items)
        self.assertFalse(ok)
        self.assertIn("MISSING_WATCH_ONLY_REQUIRED_FOR_6PLUS_BATCH", violations)

    def test_five_item_batch_no_d1_required(self):
        items = [
            _selected_item("MintA", "PairA", BUCKET_A1, "TRACK_FAST"),
            _selected_item("MintB", "PairB", BUCKET_A2, "TRACK_FAST"),
            _selected_item("MintC", "PairC", BUCKET_B1, "TRACK_NORMAL"),
            _selected_item("MintD", "PairD", BUCKET_B2, "TRACK_NORMAL"),
            _selected_item("MintE", "PairE", BUCKET_B5, "WATCH_ONLY"),
        ]
        ok, violations = validate_batch_quota(items)
        self.assertTrue(ok, violations)

    def test_group_f_without_corpus_rejected(self):
        items = [
            _selected_item("MintA", "PairA", BUCKET_F1, "WATCH_ONLY"),
            _selected_item("MintB", "PairB", BUCKET_A2, "TRACK_FAST"),
            _selected_item("MintC", "PairC", BUCKET_D1, "WATCH_ONLY"),
        ]
        ok, violations = validate_batch_quota(items, min_corpus_episodes=0)
        self.assertFalse(ok)
        self.assertTrue(any("GROUP_F_REQUIRES" in v for v in violations))

    def test_group_f_with_sufficient_corpus_passes(self):
        items = [
            _selected_item("MintA", "PairA", BUCKET_F1, "WATCH_ONLY"),
            _selected_item("MintB", "PairB", BUCKET_A2, "TRACK_FAST"),
            _selected_item("MintC", "PairC", BUCKET_D1, "WATCH_ONLY"),
        ]
        ok, violations = validate_batch_quota(
            items, min_corpus_episodes=GROUP_F_MINIMUM_CORPUS_EPISODES
        )
        self.assertTrue(ok, violations)

    def test_empty_batch_passes_no_violations(self):
        ok, violations = validate_batch_quota([])
        self.assertTrue(ok)
        self.assertEqual(violations, [])

    def test_single_item_batch_passes(self):
        # Use a non-Group-A bucket; a single A1 item correctly triggers
        # GROUP_A_PRESENT_BUT_NO_TRAP_FAILURE_BUCKET (correct enforcement).
        items = [_selected_item("MintA", "PairA", BUCKET_B1, "TRACK_NORMAL")]
        ok, violations = validate_batch_quota(items)
        self.assertTrue(ok, violations)


# ---------------------------------------------------------------------------
# 8. Selection and rejection reason persistence
# ---------------------------------------------------------------------------

class TestReasonPersistence(unittest.TestCase):

    def test_selection_reason_preserved_in_item(self):
        item = build_batch_item(
            _fast_candidate(),
            item_status=ITEM_STATUS_SELECTED,
            selection_reason="FAST_ACTIVITY_CONFIRMED",
        )
        self.assertEqual(item["selection_reason"], "FAST_ACTIVITY_CONFIRMED")
        self.assertIsNone(item["rejection_reason"])

    def test_rejection_reason_preserved_in_item(self):
        item = build_batch_item(
            _fast_candidate(),
            item_status=ITEM_STATUS_REJECTED,
            rejection_reason="MINT_DUPLICATE",
        )
        self.assertEqual(item["rejection_reason"], "MINT_DUPLICATE")

    def test_selected_item_has_selected_at(self):
        item = build_batch_item(
            _fast_candidate(),
            item_status=ITEM_STATUS_SELECTED,
        )
        self.assertIsNotNone(item["selected_at"])

    def test_rejected_item_has_no_selected_at(self):
        item = build_batch_item(
            _fast_candidate(),
            item_status=ITEM_STATUS_REJECTED,
            rejection_reason="MINT_DUPLICATE",
        )
        self.assertIsNone(item["selected_at"])

    def test_source_trace_fields_preserved(self):
        c = _fast_candidate(source_response_id=42, source_request_id=7, discovery_candidate_id=3)
        item = build_batch_item(c, item_status=ITEM_STATUS_SELECTED)
        self.assertEqual(item["source_response_id"], 42)
        self.assertEqual(item["source_request_id"], 7)
        self.assertEqual(item["discovery_candidate_id"], 3)

    def test_operator_approved_stored(self):
        item = build_batch_item(
            _fast_candidate(),
            item_status=ITEM_STATUS_SELECTED,
            operator_approved=True,
        )
        self.assertTrue(item["operator_approved"])

    def test_manual_override_reason_stored(self):
        item = build_batch_item(
            _fast_candidate(),
            item_status=ITEM_STATUS_SELECTED,
            manual_override_reason="WATCH_ONLY_TO_TRACK_NORMAL_APPROVED",
        )
        self.assertEqual(item["manual_override_reason"], "WATCH_ONLY_TO_TRACK_NORMAL_APPROVED")

    def test_cooldown_reopen_fields_stored(self):
        item = build_batch_item(
            _fast_candidate(),
            item_status=ITEM_STATUS_SELECTED,
            cooldown_reopened=True,
            cooldown_reopen_reason="new_pool_detected",
        )
        self.assertTrue(item["cooldown_reopened"])
        self.assertEqual(item["cooldown_reopen_reason"], "new_pool_detected")

    def test_stnp_classification_stored(self):
        item = build_batch_item(
            _fast_candidate(),
            item_status=ITEM_STATUS_SELECTED,
            same_token_new_pair=True,
            same_token_new_pair_classification=STNP_MIGRATION,
        )
        self.assertTrue(item["same_token_new_pair"])
        self.assertEqual(item["same_token_new_pair_classification"], STNP_MIGRATION)


# ---------------------------------------------------------------------------
# 9. Candidate metadata extraction
# ---------------------------------------------------------------------------

class TestCandidateMetadata(unittest.TestCase):

    def test_all_metadata_fields_extracted(self):
        c = _fast_candidate(
            price_usd=0.001,
            liquidity_usd=10_000.0,
            volume_5m=2_000.0,
            fdv=50_000.0,
            market_cap=40_000.0,
        )
        meta = extract_candidate_metadata(c)
        self.assertIn("price_usd", meta)
        self.assertIn("liquidity_usd", meta)
        self.assertIn("volume_5m", meta)
        self.assertIn("fdv", meta)
        self.assertIn("market_cap", meta)

    def test_missing_fields_return_none(self):
        c = {"token_mint": "MintX", "pair_address": "PairX"}
        meta = extract_candidate_metadata(c)
        self.assertIsNone(meta["price_usd"])
        self.assertIsNone(meta["liquidity_usd"])
        self.assertIsNone(meta["fdv"])

    def test_metadata_stored_as_json_in_item(self):
        c = _fast_candidate(price_usd=0.002, liquidity_usd=5_000.0)
        item = build_batch_item(c, item_status=ITEM_STATUS_SELECTED)
        meta = json.loads(item["candidate_metadata_json"])
        self.assertAlmostEqual(meta["price_usd"], 0.002)
        self.assertAlmostEqual(meta["liquidity_usd"], 5_000.0)


# ---------------------------------------------------------------------------
# 10. Candidate-universe summary
# ---------------------------------------------------------------------------

class TestCandidateUniverseSummary(unittest.TestCase):

    def _make_candidates(self) -> list[dict]:
        fast = _fast_candidate(primary_bucket=BUCKET_A1, asset_class="FAST_PUMP")
        trap = _fast_candidate(
            token_mint="MintTRAP", pair_address="PairTRAP",
            primary_bucket=BUCKET_A2, asset_class="WICK_ONLY_PUMP",
            source_channel="DEXSCREENER_SEARCH",
            source_response_id=10,
        )
        dead = _dead_candidate(primary_bucket=BUCKET_D1, asset_class="DEAD_TOKEN")
        return [fast, trap, dead]

    def test_summary_contains_required_fields(self):
        candidates = self._make_candidates()
        selected = [candidates[0], candidates[1]]
        rejected = [candidates[2]]
        summary = build_candidate_universe_summary(candidates, selected, rejected)
        required = [
            "candidate_pool_total",
            "selected_count",
            "rejected_count",
            "unavailable_or_unclassified_count",
            "candidate_pool_by_source",
            "candidate_pool_by_source_channel",
            "candidate_pool_by_discovery_action",
            "candidate_pool_by_bucket",
            "candidate_pool_by_tracking_lane",
            "candidate_pool_by_asset_class",
            "candidate_pool_by_rejection_reason",
            "pool_diversity_notes",
            "pool_quality_notes",
        ]
        for field in required:
            self.assertIn(field, summary, f"Missing field: {field}")

    def test_total_counts_correct(self):
        candidates = self._make_candidates()
        selected = [candidates[0]]
        rejected = [candidates[1], candidates[2]]
        summary = build_candidate_universe_summary(candidates, selected, rejected)
        self.assertEqual(summary["candidate_pool_total"], 3)
        self.assertEqual(summary["selected_count"], 1)
        self.assertEqual(summary["rejected_count"], 2)
        self.assertEqual(summary["unavailable_or_unclassified_count"], 0)

    def test_all_winner_batch_triggers_diversity_note(self):
        c = _fast_candidate(primary_bucket=BUCKET_A1, asset_class="FAST_PUMP")
        c2 = _fast_candidate(
            token_mint="MintA2", pair_address="PairA2",
            primary_bucket=BUCKET_A1, asset_class="FAST_PUMP",
        )
        selected_items = [
            {"primary_bucket": BUCKET_A1, "tracking_lane": "TRACK_FAST"},
            {"primary_bucket": BUCKET_A1, "tracking_lane": "TRACK_FAST"},
        ]
        summary = build_candidate_universe_summary([c, c2], selected_items, [])
        self.assertTrue(
            any("all_selected_are_A1" in note for note in summary["pool_diversity_notes"])
        )

    def test_missing_source_trace_in_quality_notes(self):
        c = _fast_candidate(source_response_id=None)
        summary = build_candidate_universe_summary([c], [], [c])
        self.assertTrue(
            any("missing_source_trace" in note for note in summary["pool_quality_notes"])
        )

    def test_empty_pool_produces_valid_summary(self):
        summary = build_candidate_universe_summary([], [], [])
        self.assertEqual(summary["candidate_pool_total"], 0)
        self.assertEqual(summary["selected_count"], 0)
        self.assertEqual(summary["rejected_count"], 0)


# ---------------------------------------------------------------------------
# 11. DB persistence
# ---------------------------------------------------------------------------

class TestPersistSelectionBatch(unittest.TestCase):

    def setUp(self):
        self.conn = _make_db()

    def tearDown(self):
        self.conn.close()

    def _make_items(self) -> list[dict]:
        fast = build_batch_item(
            _fast_candidate(),
            item_status=ITEM_STATUS_SELECTED,
            primary_bucket=BUCKET_A1,
            bucket_name="FAST_PUMP_FOLLOW",
            asset_class=ASSET_CLASS_FAST_PUMP,
            selection_reason="FAST_ACTIVITY_CONFIRMED",
            tracking_lane="TRACK_FAST",
            operator_approved=True,
        )
        dead = build_batch_item(
            _dead_candidate(),
            item_status=ITEM_STATUS_SELECTED,
            primary_bucket=BUCKET_D1,
            bucket_name="DEAD_TOKEN",
            asset_class=ASSET_CLASS_DEAD_TOKEN,
            selection_reason="DEAD_TOKEN_PROTECTION_SAMPLE",
            tracking_lane="WATCH_ONLY",
            operator_approved=True,
        )
        rejected = build_batch_item(
            _normal_candidate(token_mint="MintREJECT", pair_address="PairREJECT"),
            item_status=ITEM_STATUS_REJECTED,
            rejection_reason="MINT_DUPLICATE",
        )
        return [fast, dead, rejected]

    def test_batch_row_written(self):
        items = self._make_items()
        result = persist_selection_batch(self.conn, "TEST_BATCH_001", items)
        self.assertEqual(result["batch_id"], "TEST_BATCH_001")
        row = self.conn.execute(
            "SELECT * FROM printer_selection_batches WHERE batch_id = ?",
            ("TEST_BATCH_001",),
        ).fetchone()
        self.assertIsNotNone(row)
        self.assertEqual(row["batch_status"], BATCH_STATUS_ASSEMBLED)

    def test_item_rows_written(self):
        items = self._make_items()
        persist_selection_batch(self.conn, "TEST_BATCH_002", items)
        rows = self.conn.execute(
            "SELECT * FROM printer_selection_batch_items WHERE batch_id = ?",
            ("TEST_BATCH_002",),
        ).fetchall()
        self.assertEqual(len(rows), 3)

    def test_selected_items_stored_correctly(self):
        items = self._make_items()
        persist_selection_batch(self.conn, "TEST_BATCH_003", items)
        rows = self.conn.execute(
            "SELECT * FROM printer_selection_batch_items WHERE batch_id = ? AND item_status = ?",
            ("TEST_BATCH_003", ITEM_STATUS_SELECTED),
        ).fetchall()
        self.assertEqual(len(rows), 2)

    def test_rejected_item_stored_with_rejection_reason(self):
        items = self._make_items()
        persist_selection_batch(self.conn, "TEST_BATCH_004", items)
        row = self.conn.execute(
            "SELECT * FROM printer_selection_batch_items WHERE batch_id = ? AND item_status = ?",
            ("TEST_BATCH_004", ITEM_STATUS_REJECTED),
        ).fetchone()
        self.assertIsNotNone(row)
        self.assertEqual(row["rejection_reason"], "MINT_DUPLICATE")

    def test_auto_batch_id_when_none(self):
        items = self._make_items()
        result = persist_selection_batch(self.conn, None, items)
        self.assertIsNotNone(result["batch_id"])
        self.assertTrue(len(result["batch_id"]) > 0)

    def test_selected_count_in_batch_row(self):
        items = self._make_items()
        persist_selection_batch(self.conn, "TEST_BATCH_005", items)
        row = self.conn.execute(
            "SELECT selected_count, rejected_count FROM printer_selection_batches WHERE batch_id = ?",
            ("TEST_BATCH_005",),
        ).fetchone()
        self.assertEqual(row["selected_count"], 2)
        self.assertEqual(row["rejected_count"], 1)

    def test_pool_summary_json_stored(self):
        items = self._make_items()
        candidates = [_fast_candidate(), _dead_candidate()]
        universe = build_candidate_universe_summary(candidates, items[:2], items[2:])
        persist_selection_batch(
            self.conn, "TEST_BATCH_006", items, universe_summary=universe
        )
        row = self.conn.execute(
            "SELECT pool_summary_json FROM printer_selection_batches WHERE batch_id = ?",
            ("TEST_BATCH_006",),
        ).fetchone()
        summary = json.loads(row["pool_summary_json"])
        self.assertIn("candidate_pool_total", summary)

    def test_migration_in_db_has_stnp_classification(self):
        c = _fast_candidate(token_mint="MintMIG", pair_address="PairMIG")
        item = build_batch_item(
            c,
            item_status=ITEM_STATUS_SELECTED,
            same_token_new_pair=True,
            same_token_new_pair_classification=STNP_MIGRATION,
            primary_bucket=BUCKET_D3,
            bucket_name="MIGRATION_EVENT",
        )
        persist_selection_batch(self.conn, "TEST_BATCH_007", [item])
        row = self.conn.execute(
            "SELECT same_token_new_pair, same_token_new_pair_classification "
            "FROM printer_selection_batch_items WHERE batch_id = ?",
            ("TEST_BATCH_007",),
        ).fetchone()
        self.assertEqual(row["same_token_new_pair"], 1)
        self.assertEqual(row["same_token_new_pair_classification"], STNP_MIGRATION)

    def test_window_kind_stored(self):
        items = self._make_items()
        persist_selection_batch(self.conn, "TEST_BATCH_008", items, window_kind="WINDOW_15M")
        row = self.conn.execute(
            "SELECT window_kind FROM printer_selection_batches WHERE batch_id = ?",
            ("TEST_BATCH_008",),
        ).fetchone()
        self.assertEqual(row["window_kind"], "WINDOW_15M")


# ---------------------------------------------------------------------------
# 12. No score/rank/confidence/weighted logic
# ---------------------------------------------------------------------------

class TestNoScoreRankConfidenceWeighted(unittest.TestCase):

    def test_assign_bucket_returns_tuple_of_strings(self):
        result = assign_bucket(_fast_candidate())
        self.assertIsInstance(result, tuple)
        bucket_id, name = result
        self.assertIsInstance(bucket_id, str)
        self.assertIsInstance(name, str)

    def test_assign_bucket_never_returns_float(self):
        for fn in [_fast_candidate, _dead_candidate, _normal_candidate]:
            bucket_id, name = assign_bucket(fn())
            self.assertNotIsInstance(bucket_id, float)
            self.assertNotIsInstance(name, float)

    def test_quota_violations_are_strings(self):
        items = [_selected_item("M", "P", BUCKET_A1, "TRACK_FAST")] * 3
        ok, violations = validate_batch_quota(items)
        for v in violations:
            self.assertIsInstance(v, str)
            self.assertNotIsInstance(v, float)

    def test_universe_summary_counts_are_integers(self):
        candidates = [_fast_candidate(), _dead_candidate()]
        summary = build_candidate_universe_summary(candidates, [candidates[0]], [candidates[1]])
        for count_key in ["candidate_pool_total", "selected_count", "rejected_count"]:
            self.assertIsInstance(summary[count_key], int)

    def test_batch_item_has_no_score_field(self):
        item = build_batch_item(_fast_candidate(), item_status=ITEM_STATUS_SELECTED)
        forbidden = {"score", "rank", "confidence", "weight", "probability", "alpha"}
        for key in item:
            self.assertNotIn(key.lower(), forbidden, f"Forbidden field found: {key}")

    def test_bucket_names_contain_no_numeric_rank(self):
        for bucket_id, name in BUCKET_NAMES.items():
            self.assertNotIn("score", name.lower())
            self.assertNotIn("rank", name.lower())
            self.assertNotIn("confidence", name.lower())


# ---------------------------------------------------------------------------
# 13. No BUY/paper/PnL/retrieval side effects
# ---------------------------------------------------------------------------

class TestNoFinancialSideEffects(unittest.TestCase):

    def setUp(self):
        self.conn = _make_db()

    def tearDown(self):
        self.conn.close()

    def _persist_and_check(self):
        items = [
            build_batch_item(
                _fast_candidate(),
                item_status=ITEM_STATUS_SELECTED,
                primary_bucket=BUCKET_A1,
                operator_approved=True,
            ),
        ]
        persist_selection_batch(self.conn, "SAFETY_BATCH_001", items)

    def test_no_paper_decisions_created(self):
        self._persist_and_check()
        count = self.conn.execute(
            "SELECT COUNT(*) FROM printer_paper_decisions"
        ).fetchone()[0]
        self.assertEqual(count, 0)

    def test_no_paper_positions_created(self):
        self._persist_and_check()
        count = self.conn.execute(
            "SELECT COUNT(*) FROM printer_paper_positions"
        ).fetchone()[0]
        self.assertEqual(count, 0)

    def test_no_paper_trade_events_created(self):
        self._persist_and_check()
        count = self.conn.execute(
            "SELECT COUNT(*) FROM printer_paper_trade_events"
        ).fetchone()[0]
        self.assertEqual(count, 0)

    def test_no_retrieval_matches_created(self):
        self._persist_and_check()
        count = self.conn.execute(
            "SELECT COUNT(*) FROM printer_memory_retrieval_matches"
        ).fetchone()[0]
        self.assertEqual(count, 0)

    def test_no_memory_windows_created(self):
        self._persist_and_check()
        count = self.conn.execute(
            "SELECT COUNT(*) FROM printer_memory_windows"
        ).fetchone()[0]
        self.assertEqual(count, 0)


# ---------------------------------------------------------------------------
# 14. WATCH_ONLY no WINDOW_15M contract
# ---------------------------------------------------------------------------

class TestWatchOnlyNoMemoryWindow(unittest.TestCase):

    def test_watch_only_cannot_silently_enter_track_fast(self):
        ok, reason = check_watch_only_promotion_gate("TRACK_FAST", "WATCH_ONLY")
        self.assertFalse(ok)

    def test_watch_only_cannot_silently_enter_track_normal(self):
        ok, reason = check_watch_only_promotion_gate("TRACK_NORMAL", "WATCH_ONLY")
        self.assertFalse(ok)

    def test_watch_only_item_has_correct_tracking_lane(self):
        item = build_batch_item(
            _dead_candidate(),
            item_status=ITEM_STATUS_SELECTED,
            primary_bucket=BUCKET_D1,
            tracking_lane="WATCH_ONLY",
        )
        self.assertEqual(item["tracking_lane"], "WATCH_ONLY")

    def test_bucket_d1_assigned_watch_only_lane(self):
        c = _dead_candidate()
        bucket_id, _ = assign_bucket(c)
        self.assertEqual(bucket_id, BUCKET_D1)
        # WATCH_ONLY is the correct lane for dead tokens
        ok, _ = check_watch_only_promotion_gate("WATCH_ONLY", "WATCH_ONLY")
        self.assertTrue(ok)


# ---------------------------------------------------------------------------
# 15. Migration table created by migration file
# ---------------------------------------------------------------------------

class TestMigration025(unittest.TestCase):

    def test_selection_batches_table_exists(self):
        conn = _make_db()
        try:
            rows = conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name='printer_selection_batches'"
            ).fetchall()
            self.assertEqual(len(rows), 1)
        finally:
            conn.close()

    def test_selection_batch_items_table_exists(self):
        conn = _make_db()
        try:
            rows = conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name='printer_selection_batch_items'"
            ).fetchall()
            self.assertEqual(len(rows), 1)
        finally:
            conn.close()

    def test_batch_items_has_primary_bucket_column(self):
        conn = _make_db()
        try:
            conn.execute(
                "SELECT primary_bucket FROM printer_selection_batch_items LIMIT 0"
            )
        finally:
            conn.close()

    def test_batch_items_has_behavior_context_labels_column(self):
        conn = _make_db()
        try:
            conn.execute(
                "SELECT behavior_context_labels FROM printer_selection_batch_items LIMIT 0"
            )
        finally:
            conn.close()

    def test_batch_items_has_candidate_metadata_json_column(self):
        conn = _make_db()
        try:
            conn.execute(
                "SELECT candidate_metadata_json FROM printer_selection_batch_items LIMIT 0"
            )
        finally:
            conn.close()


if __name__ == "__main__":
    unittest.main()
