"""V2-2H.2 — Age/Activity Buckets and Recent-Active Priority.

Targeted unit tests for the pure helper systems added in V2-2H.2:
  1. Age-bucket derivation (derive_age_bucket)
  2. Activity-bucket derivation (derive_activity_bucket)
  3. Low-volume/dead-token activity classification
  4. Recent-active priority tier derivation (derive_recent_active_tier)
  5. Candidate-universe age/activity reporting (build_age_activity_report)
  6. Reporting hook integration in build_discover_candidates_once_payload

Locks preserved: no discovery runs, no source fetching, no live DB mutation,
no memory generation, no retrieval, no paper decisions, no BUY/SELL/HOLD,
no positions/trades/audits/PnL, no scoring/ranking/confidence/weighted logic.
"""

from __future__ import annotations

import argparse
import pathlib
import sys
import tempfile
import unittest

PROJECT_ROOT = pathlib.Path(__file__).resolve().parents[1]
SRC_PATH = PROJECT_ROOT / "src"
sys.path.insert(0, str(SRC_PATH))

from printer_v1.db import apply_migrations
from printer_v1.discovery.selection_batch import (
    AGE_0_24H,
    AGE_1_7D,
    AGE_7_14D,
    AGE_14_28D,
    AGE_28D_PLUS,
    AGE_UNKNOWN,
    AGE_BUCKETS_RECENT,
    ACTIVITY_HIGH,
    ACTIVITY_MEDIUM,
    ACTIVITY_LOW,
    ACTIVITY_DEAD,
    ACTIVITY_REVIVING,
    ACTIVITY_UNKNOWN,
    RECENT_ACTIVE_TIER_1,
    RECENT_ACTIVE_TIER_2,
    OLDER_ACTIVE_TIER_3,
    LOW_ACTIVITY_TIER_4,
    UNKNOWN_TIER_5,
    derive_age_bucket,
    derive_activity_bucket,
    derive_recent_active_tier,
    build_age_activity_report,
)
from printer_v1.operator_cli.commands import build_discover_candidates_once_payload


# ---------------------------------------------------------------------------
# Shared fixture helpers
# ---------------------------------------------------------------------------

def _candidate(**fields) -> dict:
    base = {
        "liquidity_usd": 1000.0,
        "volume_5m": 0.0,
        "txns_5m": 0.0,
        "volume_1h": 0.0,
        "txns_1h": 0.0,
        "volume_24h": 0.0,
        "txns_24h": 0.0,
        "token_age_seconds": None,
    }
    base.update(fields)
    return base


def _args_for_reporting(**overrides) -> argparse.Namespace:
    values = {
        "db_path": None,
        "project_root": str(PROJECT_ROOT),
        "format": "json",
        "no_color": True,
        "operator_approved": True,
        "chain": "solana",
        "max_candidates": 10,
        "query": "pump",
        "timeout_seconds": 5.0,
        "source_name": "dexscreener",
        "request_key": "v2-2h2-test-discovery",
    }
    values.update(overrides)
    return argparse.Namespace(**values)


def _pair_fixture(pair_address: str, mint: str, liquidity: float = 1500.0) -> dict:
    return {
        "chainId": "solana",
        "pairAddress": pair_address,
        "baseToken": {"address": mint, "symbol": "SYM", "name": "Token"},
        "quoteToken": {"address": "So11111111111111111111111111111111111111112"},
        "dexId": "raydium",
        "priceUsd": "0.001",
        "liquidity": {"usd": liquidity},
        "volume": {"m5": 50, "h1": 300, "h24": 1000},
        "txns": {"m5": {"buys": 2, "sells": 1}, "h1": {"buys": 10, "sells": 5}},
    }


def _success_transport_factory(pairs: list[dict]):
    def _transport(context):
        del context
        return {"pairs": pairs}
    return _transport


# ---------------------------------------------------------------------------
# 1. Age-bucket derivation
# ---------------------------------------------------------------------------

class TestAgeBucketDerivation(unittest.TestCase):

    def test_age_0_24h_at_zero(self):
        self.assertEqual(derive_age_bucket(_candidate(token_age_seconds=0)), AGE_0_24H)

    def test_age_0_24h_near_upper_bound(self):
        self.assertEqual(derive_age_bucket(_candidate(token_age_seconds=86399)), AGE_0_24H)

    def test_age_1_7d_at_boundary(self):
        self.assertEqual(derive_age_bucket(_candidate(token_age_seconds=86400)), AGE_1_7D)

    def test_age_1_7d_midpoint(self):
        self.assertEqual(derive_age_bucket(_candidate(token_age_seconds=300_000)), AGE_1_7D)

    def test_age_7_14d_at_boundary(self):
        self.assertEqual(derive_age_bucket(_candidate(token_age_seconds=604_800)), AGE_7_14D)

    def test_age_14_28d_at_boundary(self):
        self.assertEqual(derive_age_bucket(_candidate(token_age_seconds=1_209_600)), AGE_14_28D)

    def test_age_28d_plus_at_boundary(self):
        self.assertEqual(derive_age_bucket(_candidate(token_age_seconds=2_419_200)), AGE_28D_PLUS)

    def test_age_28d_plus_large(self):
        self.assertEqual(derive_age_bucket(_candidate(token_age_seconds=10_000_000)), AGE_28D_PLUS)

    def test_age_unknown_when_field_missing(self):
        self.assertEqual(derive_age_bucket({}), AGE_UNKNOWN)

    def test_age_unknown_when_explicitly_none(self):
        self.assertEqual(derive_age_bucket(_candidate(token_age_seconds=None)), AGE_UNKNOWN)

    def test_age_unknown_when_negative(self):
        self.assertEqual(derive_age_bucket(_candidate(token_age_seconds=-1)), AGE_UNKNOWN)

    def test_age_unknown_when_invalid_string(self):
        self.assertEqual(derive_age_bucket(_candidate(token_age_seconds="not_a_number")), AGE_UNKNOWN)

    def test_missing_age_does_not_silently_become_age_0_24h(self):
        # The _f() helper would convert None → 0.0 → AGE_0_24H.
        # derive_age_bucket must NOT do that.
        result = derive_age_bucket({"token_age_seconds": None})
        self.assertNotEqual(result, AGE_0_24H)
        self.assertEqual(result, AGE_UNKNOWN)

    def test_age_buckets_recent_contains_four_members(self):
        self.assertEqual(
            AGE_BUCKETS_RECENT,
            frozenset({AGE_0_24H, AGE_1_7D, AGE_7_14D, AGE_14_28D}),
        )

    def test_age_28d_plus_not_in_recent_set(self):
        self.assertNotIn(AGE_28D_PLUS, AGE_BUCKETS_RECENT)

    def test_age_unknown_not_in_recent_set(self):
        self.assertNotIn(AGE_UNKNOWN, AGE_BUCKETS_RECENT)


# ---------------------------------------------------------------------------
# 2 & 3. Activity-bucket derivation
# ---------------------------------------------------------------------------

class TestActivityBucketDerivation(unittest.TestCase):

    def test_high_from_volume_5m(self):
        c = _candidate(liquidity_usd=6000, volume_5m=1500)
        self.assertEqual(derive_activity_bucket(c), ACTIVITY_HIGH)

    def test_high_from_txns_5m(self):
        c = _candidate(liquidity_usd=5000, txns_5m=10)
        self.assertEqual(derive_activity_bucket(c), ACTIVITY_HIGH)

    def test_high_exactly_at_liquidity_threshold_and_txns_threshold(self):
        c = _candidate(liquidity_usd=5000, txns_5m=10)
        self.assertEqual(derive_activity_bucket(c), ACTIVITY_HIGH)

    def test_high_fresh_launch_no_24h_history_needed(self):
        # A fresh token minutes old should still reach ACTIVITY_HIGH
        # via 5m/liquidity fields alone, with no volume_24h data.
        c = _candidate(liquidity_usd=8000, volume_5m=2000, volume_24h=None)
        self.assertEqual(derive_activity_bucket(c), ACTIVITY_HIGH)

    def test_not_high_when_liquidity_below_threshold(self):
        c = _candidate(liquidity_usd=4999, volume_5m=1500)
        self.assertNotEqual(derive_activity_bucket(c), ACTIVITY_HIGH)

    def test_not_high_when_volume_and_txns_both_below_threshold(self):
        c = _candidate(liquidity_usd=6000, volume_5m=999, txns_5m=9)
        self.assertNotEqual(derive_activity_bucket(c), ACTIVITY_HIGH)

    def test_dead_all_activity_near_zero(self):
        c = _candidate(
            liquidity_usd=200,
            volume_5m=0, txns_5m=0,
            volume_1h=0, txns_1h=0,
            volume_24h=5, txns_24h=1,
        )
        self.assertEqual(derive_activity_bucket(c), ACTIVITY_DEAD)

    def test_dead_at_tiny_volume_boundary(self):
        c = _candidate(
            liquidity_usd=200,
            volume_5m=0, txns_5m=0,
            volume_1h=0, txns_1h=0,
            volume_24h=10, txns_24h=2,
        )
        self.assertEqual(derive_activity_bucket(c), ACTIVITY_DEAD)

    def test_not_dead_when_volume_1h_nonzero(self):
        c = _candidate(
            liquidity_usd=200,
            volume_5m=0, txns_5m=0,
            volume_1h=1, txns_1h=0,
            volume_24h=5, txns_24h=0,
        )
        self.assertNotEqual(derive_activity_bucket(c), ACTIVITY_DEAD)

    def test_medium_sustained_24h_volume(self):
        c = _candidate(liquidity_usd=2000, volume_24h=300)
        self.assertEqual(derive_activity_bucket(c), ACTIVITY_MEDIUM)

    def test_medium_requires_liquidity_at_normal_threshold(self):
        c = _candidate(liquidity_usd=1000, volume_24h=300)
        self.assertEqual(derive_activity_bucket(c), ACTIVITY_MEDIUM)

    def test_not_medium_when_volume_24h_at_threshold(self):
        # Boundary: volume_24h must be > 200, not == 200
        c = _candidate(liquidity_usd=2000, volume_24h=200)
        self.assertNotEqual(derive_activity_bucket(c), ACTIVITY_MEDIUM)

    def test_low_catchall(self):
        c = _candidate(liquidity_usd=600, volume_24h=50)
        self.assertEqual(derive_activity_bucket(c), ACTIVITY_LOW)

    def test_low_when_liquidity_below_medium_threshold(self):
        c = _candidate(liquidity_usd=900, volume_24h=300)
        self.assertEqual(derive_activity_bucket(c), ACTIVITY_LOW)

    def test_reviving_from_archived(self):
        c = _candidate(liquidity_usd=800, volume_5m=100)
        self.assertEqual(
            derive_activity_bucket(c, prior_lifecycle_state="ARCHIVED"),
            ACTIVITY_REVIVING,
        )

    def test_reviving_from_cooldown(self):
        c = _candidate(liquidity_usd=800, txns_1h=5)
        self.assertEqual(
            derive_activity_bucket(c, prior_lifecycle_state="COOLDOWN"),
            ACTIVITY_REVIVING,
        )

    def test_reviving_from_dead(self):
        c = _candidate(liquidity_usd=800, volume_1h=50)
        self.assertEqual(
            derive_activity_bucket(c, prior_lifecycle_state="DEAD"),
            ACTIVITY_REVIVING,
        )

    def test_reviving_not_triggered_without_prior_state(self):
        c = _candidate(liquidity_usd=800, volume_5m=100)
        result = derive_activity_bucket(c, prior_lifecycle_state=None)
        self.assertNotEqual(result, ACTIVITY_REVIVING)

    def test_reviving_not_triggered_without_new_activity(self):
        # Prior state is dead but no new activity signal
        c = _candidate(
            liquidity_usd=800,
            volume_5m=0, txns_5m=0, volume_1h=0, txns_1h=0,
            volume_24h=5, txns_24h=1,
        )
        result = derive_activity_bucket(c, prior_lifecycle_state="DEAD")
        self.assertNotEqual(result, ACTIVITY_REVIVING)
        self.assertEqual(result, ACTIVITY_DEAD)

    def test_high_takes_precedence_over_reviving(self):
        c = _candidate(liquidity_usd=6000, volume_5m=2000)
        result = derive_activity_bucket(c, prior_lifecycle_state="DEAD")
        self.assertEqual(result, ACTIVITY_HIGH)

    def test_unknown_when_liquidity_usd_missing(self):
        c = {"volume_5m": 500, "txns_5m": 5}
        self.assertEqual(derive_activity_bucket(c), ACTIVITY_UNKNOWN)

    def test_unknown_when_liquidity_usd_explicitly_none(self):
        c = _candidate(liquidity_usd=None)
        self.assertEqual(derive_activity_bucket(c), ACTIVITY_UNKNOWN)


# ---------------------------------------------------------------------------
# 4. Recent-active priority tier derivation
# ---------------------------------------------------------------------------

class TestRecentActiveTierDerivation(unittest.TestCase):

    def test_tier_1_recent_high(self):
        self.assertEqual(derive_recent_active_tier(AGE_0_24H, ACTIVITY_HIGH), RECENT_ACTIVE_TIER_1)

    def test_tier_1_recent_medium(self):
        self.assertEqual(derive_recent_active_tier(AGE_14_28D, ACTIVITY_MEDIUM), RECENT_ACTIVE_TIER_1)

    def test_tier_1_all_recent_buckets_with_high(self):
        for age in (AGE_0_24H, AGE_1_7D, AGE_7_14D, AGE_14_28D):
            with self.subTest(age=age):
                self.assertEqual(
                    derive_recent_active_tier(age, ACTIVITY_HIGH),
                    RECENT_ACTIVE_TIER_1,
                )

    def test_tier_2_recent_reviving(self):
        self.assertEqual(derive_recent_active_tier(AGE_1_7D, ACTIVITY_REVIVING), RECENT_ACTIVE_TIER_2)

    def test_tier_2_all_recent_buckets_with_reviving(self):
        for age in (AGE_0_24H, AGE_1_7D, AGE_7_14D, AGE_14_28D):
            with self.subTest(age=age):
                self.assertEqual(
                    derive_recent_active_tier(age, ACTIVITY_REVIVING),
                    RECENT_ACTIVE_TIER_2,
                )

    def test_tier_3_older_high(self):
        self.assertEqual(derive_recent_active_tier(AGE_28D_PLUS, ACTIVITY_HIGH), OLDER_ACTIVE_TIER_3)

    def test_tier_3_older_medium(self):
        self.assertEqual(derive_recent_active_tier(AGE_28D_PLUS, ACTIVITY_MEDIUM), OLDER_ACTIVE_TIER_3)

    def test_tier_3_older_reviving(self):
        self.assertEqual(derive_recent_active_tier(AGE_28D_PLUS, ACTIVITY_REVIVING), OLDER_ACTIVE_TIER_3)

    def test_tier_4_low_activity_any_age(self):
        for age in (AGE_0_24H, AGE_7_14D, AGE_28D_PLUS):
            with self.subTest(age=age):
                self.assertEqual(
                    derive_recent_active_tier(age, ACTIVITY_LOW),
                    LOW_ACTIVITY_TIER_4,
                )

    def test_tier_4_dead_activity_any_age(self):
        for age in (AGE_0_24H, AGE_14_28D, AGE_28D_PLUS):
            with self.subTest(age=age):
                self.assertEqual(
                    derive_recent_active_tier(age, ACTIVITY_DEAD),
                    LOW_ACTIVITY_TIER_4,
                )

    def test_tier_5_unknown_age(self):
        self.assertEqual(derive_recent_active_tier(AGE_UNKNOWN, ACTIVITY_HIGH), UNKNOWN_TIER_5)

    def test_tier_5_unknown_activity(self):
        self.assertEqual(derive_recent_active_tier(AGE_0_24H, ACTIVITY_UNKNOWN), UNKNOWN_TIER_5)

    def test_tier_5_both_unknown(self):
        self.assertEqual(derive_recent_active_tier(AGE_UNKNOWN, ACTIVITY_UNKNOWN), UNKNOWN_TIER_5)

    def test_tier_is_string_not_int(self):
        tier = derive_recent_active_tier(AGE_0_24H, ACTIVITY_HIGH)
        self.assertIsInstance(tier, str)
        self.assertNotIsInstance(tier, int)

    def test_tiers_are_not_ordered_ints(self):
        # Tiers are categorical IDs, not orderable numeric scores.
        tier = derive_recent_active_tier(AGE_0_24H, ACTIVITY_HIGH)
        with self.assertRaises(TypeError):
            _ = tier + 1  # type: ignore[operator]


# ---------------------------------------------------------------------------
# 5. Age/activity report aggregation
# ---------------------------------------------------------------------------

class TestAgeActivityReport(unittest.TestCase):

    def test_empty_list(self):
        report = build_age_activity_report([])
        self.assertEqual(report["total_candidates"], 0)
        self.assertEqual(report["candidates_by_age_bucket"], {})
        self.assertEqual(report["candidates_by_activity_bucket"], {})
        self.assertEqual(report["candidates_by_priority_tier"], {})

    def test_single_candidate_counted(self):
        c = _candidate(
            token_age_seconds=3600,  # AGE_0_24H
            liquidity_usd=6000, volume_5m=1500,  # ACTIVITY_HIGH → TIER_1
        )
        report = build_age_activity_report([c])
        self.assertEqual(report["total_candidates"], 1)
        self.assertEqual(report["candidates_by_age_bucket"].get(AGE_0_24H), 1)
        self.assertEqual(report["candidates_by_activity_bucket"].get(ACTIVITY_HIGH), 1)
        self.assertEqual(report["candidates_by_priority_tier"].get(RECENT_ACTIVE_TIER_1), 1)

    def test_mixed_candidates_summed_correctly(self):
        candidates = [
            _candidate(token_age_seconds=3600, liquidity_usd=6000, volume_5m=1500),   # HIGH + 0_24H
            _candidate(token_age_seconds=3600, liquidity_usd=6000, volume_5m=1500),   # HIGH + 0_24H
            _candidate(token_age_seconds=200_000, liquidity_usd=500, volume_24h=50),  # LOW + 1_7D
        ]
        report = build_age_activity_report(candidates)
        self.assertEqual(report["total_candidates"], 3)
        self.assertEqual(report["candidates_by_age_bucket"][AGE_0_24H], 2)
        self.assertEqual(report["candidates_by_age_bucket"][AGE_1_7D], 1)
        self.assertEqual(report["candidates_by_activity_bucket"][ACTIVITY_HIGH], 2)
        self.assertEqual(report["candidates_by_activity_bucket"][ACTIVITY_LOW], 1)

    def test_all_expected_keys_present(self):
        report = build_age_activity_report([])
        for key in ("total_candidates", "candidates_by_age_bucket",
                    "candidates_by_activity_bucket", "candidates_by_priority_tier"):
            self.assertIn(key, report)

    def test_total_count_is_int_not_float(self):
        report = build_age_activity_report([_candidate(token_age_seconds=0)])
        self.assertIsInstance(report["total_candidates"], int)
        self.assertNotIsInstance(report["total_candidates"], bool)

    def test_bucket_counts_are_ints(self):
        c = _candidate(token_age_seconds=0, liquidity_usd=6000, volume_5m=1500)
        report = build_age_activity_report([c])
        for d in (
            report["candidates_by_age_bucket"],
            report["candidates_by_activity_bucket"],
            report["candidates_by_priority_tier"],
        ):
            for v in d.values():
                with self.subTest(value=v):
                    self.assertIsInstance(v, int)
                    self.assertNotIsInstance(v, bool)

    def test_unknown_age_candidate_counted_in_unknown_bucket(self):
        c = _candidate(token_age_seconds=None, liquidity_usd=6000, volume_5m=1500)
        report = build_age_activity_report([c])
        self.assertEqual(report["candidates_by_age_bucket"].get(AGE_UNKNOWN), 1)

    def test_unknown_liquidity_counted_as_unknown_activity(self):
        c = _candidate(liquidity_usd=None)
        report = build_age_activity_report([c])
        self.assertEqual(report["candidates_by_activity_bucket"].get(ACTIVITY_UNKNOWN), 1)
        self.assertEqual(report["candidates_by_priority_tier"].get(UNKNOWN_TIER_5), 1)


# ---------------------------------------------------------------------------
# 6. Reporting hook integration
# ---------------------------------------------------------------------------

class TestAgeActivityReportingHook(unittest.TestCase):

    def setUp(self):
        self._temp_dir = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        self.addCleanup(self._temp_dir.cleanup)
        self.db_path = pathlib.Path(self._temp_dir.name) / "v2-2h2-hook.sqlite3"
        apply_migrations(self.db_path)

    def _run_args(self, **overrides):
        base = _args_for_reporting(db_path=str(self.db_path))
        for k, v in overrides.items():
            setattr(base, k, v)
        return base

    def _two_pair_transport(self, context):
        del context
        return {
            "pairs": [
                _pair_fixture("h2-pair-1", "h2-mint-1", liquidity=8000),
                _pair_fixture("h2-pair-2", "h2-mint-2", liquidity=1200),
            ]
        }

    def test_age_activity_report_present_in_payload(self):
        payload = build_discover_candidates_once_payload(
            self._run_args(), transport=self._two_pair_transport
        )
        self.assertIn("age_activity_report", payload)

    def test_report_has_expected_top_level_keys(self):
        payload = build_discover_candidates_once_payload(
            self._run_args(), transport=self._two_pair_transport
        )
        report = payload["age_activity_report"]
        for key in ("total_candidates", "candidates_by_age_bucket",
                    "candidates_by_activity_bucket", "candidates_by_priority_tier"):
            self.assertIn(key, report)

    def test_report_total_matches_candidates_seen(self):
        payload = build_discover_candidates_once_payload(
            self._run_args(), transport=self._two_pair_transport
        )
        stage = payload["candidate_stage_report"]
        report = payload["age_activity_report"]
        self.assertEqual(report["total_candidates"], stage["candidates_seen_total"])

    def test_candidate_stage_report_invariant_preserved(self):
        # H.1 invariant: candidate_stage_report values must be int or NOT_MEASURED.
        # H.2 dicts must NOT appear inside candidate_stage_report.
        payload = build_discover_candidates_once_payload(
            self._run_args(), transport=self._two_pair_transport
        )
        report = payload["candidate_stage_report"]
        for key, value in report.items():
            with self.subTest(key=key):
                self.assertTrue(
                    isinstance(value, int) or value == "NOT_MEASURED",
                    f"candidate_stage_report[{key!r}] must be int or NOT_MEASURED, got {type(value).__name__}",
                )

    def test_report_bucket_counts_are_ints(self):
        payload = build_discover_candidates_once_payload(
            self._run_args(), transport=self._two_pair_transport
        )
        report = payload["age_activity_report"]
        for sub_key in ("candidates_by_age_bucket", "candidates_by_activity_bucket",
                        "candidates_by_priority_tier"):
            for v in report[sub_key].values():
                with self.subTest(sub_key=sub_key, value=v):
                    self.assertIsInstance(v, int)


if __name__ == "__main__":
    unittest.main()
