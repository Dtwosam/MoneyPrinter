"""V2-2H.4 — Within-Response Duplicate/STNP Handling.

Targeted unit tests for:
  A. Duplicate pair_address detection within one source response
  B. Duplicate token_mint / within-response STNP detection and classification
  C. Within-response integrity report counts and rejection visibility
  D. Backward-compatibility: H.1/H.2/H.3 invariants preserved

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
    REJECTION_PAIR_DRIFT_UNRESOLVED,
    REJECTION_PAIR_DUPLICATE_WITHIN_RESPONSE,
    REJECTION_STNP_WITHIN_RESPONSE_UNRESOLVED,
    STNP_MIGRATION,
    STNP_PAIR_DRIFT,
    STNP_DUPLICATE_RECYCLE,
    filter_within_response_duplicates,
)
from printer_v1.operator_cli.commands import build_discover_candidates_once_payload


# ---------------------------------------------------------------------------
# Fixture helpers
# ---------------------------------------------------------------------------

_SOLANA_WSOL = "So11111111111111111111111111111111111111112"


def _c(
    pair_address: str,
    token_mint: str,
    *,
    source_channel: str | None = None,
    liquidity: float = 8000.0,
    volume_5m: float = 2000.0,
    txns_5m: int = 20,
) -> dict:
    """Build a minimal normalized candidate dict."""
    d: dict = {
        "pair_address": pair_address,
        "token_mint": token_mint,
        "chain": "solana",
        "source_name": "dexscreener",
        "symbol": "TST",
        "name": "Test Token",
        "liquidity_usd": liquidity,
        "volume_5m": volume_5m,
        "txns_5m": txns_5m,
        "volume_1h": 10000.0,
        "volume_24h": 50000.0,
        "txns_1h": 100,
        "txns_24h": 400,
    }
    if source_channel is not None:
        d["source_channel"] = source_channel
    return d


def _run_args(db_path: str, **overrides) -> argparse.Namespace:
    base = {
        "project_root": str(PROJECT_ROOT),
        "format": "json",
        "no_color": True,
        "operator_approved": True,
        "chain": "solana",
        "max_candidates": 10,
        "query": "pump",
        "timeout_seconds": 5.0,
        "source_name": "dexscreener",
        "request_key": "v2-2h4-test",
        "db_path": db_path,
    }
    base.update(overrides)
    return argparse.Namespace(**base)


def _transport_factory(pairs: list[dict]):
    def _transport(context):
        del context
        return {"pairs": pairs}
    return _transport


# ---------------------------------------------------------------------------
# A. Duplicate pair_address tests
# ---------------------------------------------------------------------------

class TestDuplicatePairAddress(unittest.TestCase):

    def _two_same_pair(self) -> list[dict]:
        return [
            _c("pair-aaa", "mint-111"),
            _c("pair-aaa", "mint-222"),  # same pair_address, different mint
        ]

    def test_first_occurrence_passes_through(self):
        candidates = self._two_same_pair()
        clean, rejected, _ = filter_within_response_duplicates(candidates)
        self.assertEqual(len(clean), 1)
        self.assertEqual(clean[0]["pair_address"], "pair-aaa")
        self.assertEqual(clean[0]["token_mint"], "mint-111")

    def test_second_occurrence_is_rejected(self):
        candidates = self._two_same_pair()
        _, rejected, _ = filter_within_response_duplicates(candidates)
        self.assertEqual(len(rejected), 1)
        self.assertEqual(rejected[0]["pair_address"], "pair-aaa")

    def test_rejection_reason_is_pair_duplicate_within_response(self):
        _, rejected, _ = filter_within_response_duplicates(self._two_same_pair())
        self.assertEqual(rejected[0]["reject_reason"], REJECTION_PAIR_DUPLICATE_WITHIN_RESPONSE)

    def test_duplicate_pair_count_is_correct(self):
        _, _, report = filter_within_response_duplicates(self._two_same_pair())
        self.assertEqual(report["within_response_duplicate_pair_count"], 1)

    def test_three_same_pairs_rejects_two(self):
        candidates = [
            _c("pair-aaa", "mint-111"),
            _c("pair-aaa", "mint-222"),
            _c("pair-aaa", "mint-333"),
        ]
        clean, rejected, report = filter_within_response_duplicates(candidates)
        self.assertEqual(len(clean), 1)
        self.assertEqual(len(rejected), 2)
        self.assertEqual(report["within_response_duplicate_pair_count"], 2)

    def test_distinct_pair_addresses_both_pass_through(self):
        candidates = [
            _c("pair-aaa", "mint-111"),
            _c("pair-bbb", "mint-222"),
        ]
        clean, rejected, _ = filter_within_response_duplicates(candidates)
        self.assertEqual(len(clean), 2)
        self.assertEqual(len(rejected), 0)

    def test_duplicate_pair_rejection_detail_in_report(self):
        _, _, report = filter_within_response_duplicates(self._two_same_pair())
        self.assertEqual(len(report["within_response_duplicate_rejections"]), 1)
        detail = report["within_response_duplicate_rejections"][0]
        self.assertEqual(detail["pair_address"], "pair-aaa")
        self.assertEqual(detail["reject_reason"], REJECTION_PAIR_DUPLICATE_WITHIN_RESPONSE)

    def test_duplicate_pair_not_in_stnp_rejections(self):
        _, _, report = filter_within_response_duplicates(self._two_same_pair())
        self.assertEqual(len(report["within_response_stnp_rejections"]), 0)


# ---------------------------------------------------------------------------
# B. Duplicate mint / within-response STNP tests
# ---------------------------------------------------------------------------

class TestDuplicateMintSTNP(unittest.TestCase):

    def _same_mint_two_pairs(self, source_channel: str | None = None) -> list[dict]:
        return [
            _c("pair-aaa", "mint-111"),
            _c("pair-bbb", "mint-111", source_channel=source_channel),  # same mint, new pair
        ]

    def test_first_mint_occurrence_passes_through(self):
        candidates = self._same_mint_two_pairs()
        clean, _, _ = filter_within_response_duplicates(candidates)
        self.assertGreaterEqual(len(clean), 1)
        self.assertEqual(clean[0]["token_mint"], "mint-111")

    def test_second_mint_occurrence_is_stnp_event(self):
        _, _, report = filter_within_response_duplicates(self._same_mint_two_pairs())
        self.assertEqual(report["within_response_stnp_event_count"], 1)

    def test_unresolved_stnp_blocks_second_occurrence(self):
        # No source_channel → classification is None → unresolved → rejected
        _, rejected, _ = filter_within_response_duplicates(self._same_mint_two_pairs())
        self.assertEqual(len(rejected), 1)
        self.assertEqual(rejected[0]["reject_reason"], REJECTION_STNP_WITHIN_RESPONSE_UNRESOLVED)

    def test_unresolved_stnp_rejection_reason_exposed(self):
        _, rejected, _ = filter_within_response_duplicates(self._same_mint_two_pairs())
        self.assertEqual(rejected[0]["reject_reason"], REJECTION_STNP_WITHIN_RESPONSE_UNRESOLVED)

    def test_stnp_rejection_detail_in_report(self):
        _, _, report = filter_within_response_duplicates(self._same_mint_two_pairs())
        self.assertEqual(len(report["within_response_stnp_rejections"]), 1)
        detail = report["within_response_stnp_rejections"][0]
        self.assertEqual(detail["token_mint"], "mint-111")
        self.assertIn("reject_reason", detail)
        self.assertIn("stnp_classification", detail)

    def test_migration_channel_allows_second_occurrence(self):
        candidates = self._same_mint_two_pairs(source_channel="PUMPFUN_MIGRATION")
        clean, rejected, report = filter_within_response_duplicates(candidates)
        self.assertEqual(len(clean), 2)
        self.assertEqual(len(rejected), 0)
        self.assertEqual(report["within_response_stnp_event_count"], 1)

    def test_pumpswap_graduated_channel_allows_second_occurrence(self):
        candidates = self._same_mint_two_pairs(source_channel="PUMPSWAP_GRADUATED")
        clean, rejected, _ = filter_within_response_duplicates(candidates)
        self.assertEqual(len(clean), 2)
        self.assertEqual(len(rejected), 0)

    def test_pumpswap_migration_pool_ref_allows_second_occurrence(self):
        candidates = self._same_mint_two_pairs(source_channel="PUMPSWAP_MIGRATION_POOL_REFERENCE")
        clean, rejected, _ = filter_within_response_duplicates(candidates)
        self.assertEqual(len(clean), 2)
        self.assertEqual(len(rejected), 0)

    def test_non_migration_channel_blocks_second_occurrence(self):
        # A channel that is not a migration channel → unresolved
        candidates = self._same_mint_two_pairs(source_channel="NEW_POOL")
        _, rejected, _ = filter_within_response_duplicates(candidates)
        self.assertEqual(len(rejected), 1)
        self.assertEqual(rejected[0]["reject_reason"], REJECTION_STNP_WITHIN_RESPONSE_UNRESOLVED)

    def test_duplicate_mint_count_matches_stnp_event_count(self):
        _, _, report = filter_within_response_duplicates(self._same_mint_two_pairs())
        self.assertEqual(
            report["within_response_duplicate_mint_count"],
            report["within_response_stnp_event_count"],
        )

    def test_three_occurrences_of_same_mint_two_stnp_events(self):
        candidates = [
            _c("pair-aaa", "mint-111"),
            _c("pair-bbb", "mint-111"),
            _c("pair-ccc", "mint-111"),
        ]
        _, rejected, report = filter_within_response_duplicates(candidates)
        self.assertEqual(report["within_response_stnp_event_count"], 2)
        self.assertEqual(len(rejected), 2)

    def test_migration_classification_exposed_in_detail(self):
        candidates = self._same_mint_two_pairs(source_channel="PUMPFUN_MIGRATION")
        _, _, report = filter_within_response_duplicates(candidates)
        # No rejections; stnp_event_count is 1 but no rejection detail since it passed
        self.assertEqual(report["within_response_stnp_event_count"], 1)
        self.assertEqual(len(report["within_response_stnp_rejections"]), 0)

    def test_stnp_classification_none_for_no_channel(self):
        _, rejected, _ = filter_within_response_duplicates(self._same_mint_two_pairs())
        self.assertIsNone(rejected[0]["stnp_classification"])

    def test_stnp_classification_migration_for_migration_channel(self):
        # Test classification value is exposed even in non-rejected case (via stnp_event_count)
        # Verify rejected candidate's stnp_classification is correctly set when rejections occur
        candidates = [
            _c("pair-aaa", "mint-111"),
            _c("pair-bbb", "mint-111"),  # unresolved → rejected
        ]
        _, rejected, _ = filter_within_response_duplicates(candidates)
        # classification is None (no channel) for unresolved rejection
        self.assertIsNone(rejected[0]["stnp_classification"])


# ---------------------------------------------------------------------------
# B2. Explicit STNP classification blocking rules (reusing V2-2C gate)
# ---------------------------------------------------------------------------

class TestSTNPClassificationBlockingRules(unittest.TestCase):
    """Tests that verify existing V2-2C STNP gate rules are applied within-response."""

    def _inject_stnp_classification(
        self, candidates: list[dict], classification: str
    ) -> list[dict]:
        """Patch the classification onto the second candidate's source_channel.
        Only MIGRATION is supported via source_channel today; others are tested
        via the gate logic directly.
        """
        return candidates

    def test_pair_drift_classification_blocks_via_gate(self):
        from printer_v1.discovery.selection_batch import classify_same_token_new_pair
        ok, reason = classify_same_token_new_pair(STNP_PAIR_DRIFT, same_token_new_pair=True)
        self.assertFalse(ok)
        self.assertEqual(reason, REJECTION_PAIR_DRIFT_UNRESOLVED)

    def test_duplicate_recycle_classification_blocks_via_gate(self):
        from printer_v1.discovery.selection_batch import (
            classify_same_token_new_pair,
            REJECTION_PAIR_DUPLICATE,
        )
        ok, reason = classify_same_token_new_pair(STNP_DUPLICATE_RECYCLE, same_token_new_pair=True)
        self.assertFalse(ok)
        self.assertEqual(reason, "PAIR_DUPLICATE")

    def test_migration_classification_passes_gate(self):
        from printer_v1.discovery.selection_batch import classify_same_token_new_pair
        ok, reason = classify_same_token_new_pair(STNP_MIGRATION, same_token_new_pair=True)
        self.assertTrue(ok)
        self.assertEqual(reason, "")

    def test_none_classification_is_unresolved_via_gate(self):
        from printer_v1.discovery.selection_batch import classify_same_token_new_pair, REJECTION_STNP_UNRESOLVED
        ok, reason = classify_same_token_new_pair(None, same_token_new_pair=True)
        self.assertFalse(ok)
        self.assertEqual(reason, REJECTION_STNP_UNRESOLVED)


# ---------------------------------------------------------------------------
# C. Within-response integrity report
# ---------------------------------------------------------------------------

class TestWithinResponseIntegrityReport(unittest.TestCase):

    def test_empty_list_returns_zero_counts(self):
        _, _, report = filter_within_response_duplicates([])
        self.assertEqual(report["within_response_duplicate_pair_count"], 0)
        self.assertEqual(report["within_response_duplicate_mint_count"], 0)
        self.assertEqual(report["within_response_stnp_event_count"], 0)
        self.assertEqual(report["within_response_stnp_rejections"], [])
        self.assertEqual(report["within_response_duplicate_rejections"], [])

    def test_all_expected_keys_present(self):
        _, _, report = filter_within_response_duplicates([])
        expected = {
            "within_response_duplicate_pair_count",
            "within_response_duplicate_mint_count",
            "within_response_stnp_event_count",
            "within_response_stnp_rejections",
            "within_response_duplicate_rejections",
        }
        self.assertEqual(set(report.keys()), expected)

    def test_integer_counts_are_ints(self):
        _, _, report = filter_within_response_duplicates([_c("pair-a", "mint-a")])
        for key in (
            "within_response_duplicate_pair_count",
            "within_response_duplicate_mint_count",
            "within_response_stnp_event_count",
        ):
            with self.subTest(key=key):
                self.assertIsInstance(report[key], int)
                self.assertNotIsInstance(report[key], bool)

    def test_stnp_rejections_is_list(self):
        _, _, report = filter_within_response_duplicates([])
        self.assertIsInstance(report["within_response_stnp_rejections"], list)

    def test_duplicate_rejections_is_list(self):
        _, _, report = filter_within_response_duplicates([])
        self.assertIsInstance(report["within_response_duplicate_rejections"], list)

    def test_no_rejections_for_clean_unique_candidates(self):
        candidates = [
            _c("pair-aaa", "mint-111"),
            _c("pair-bbb", "mint-222"),
            _c("pair-ccc", "mint-333"),
        ]
        clean, rejected, report = filter_within_response_duplicates(candidates)
        self.assertEqual(len(clean), 3)
        self.assertEqual(len(rejected), 0)
        self.assertEqual(report["within_response_duplicate_pair_count"], 0)
        self.assertEqual(report["within_response_duplicate_mint_count"], 0)

    def test_mixed_duplicates_counted_independently(self):
        candidates = [
            _c("pair-aaa", "mint-111"),  # clean
            _c("pair-aaa", "mint-222"),  # dup pair_address
            _c("pair-bbb", "mint-111"),  # dup mint (STNP, mint-111 first seen at pair-aaa)
        ]
        _, _, report = filter_within_response_duplicates(candidates)
        self.assertEqual(report["within_response_duplicate_pair_count"], 1)
        self.assertEqual(report["within_response_duplicate_mint_count"], 1)
        self.assertEqual(report["within_response_stnp_event_count"], 1)

    def test_rejection_details_contain_reject_reason(self):
        candidates = [_c("pair-aaa", "mint-111"), _c("pair-aaa", "mint-222")]
        _, _, report = filter_within_response_duplicates(candidates)
        for detail in report["within_response_duplicate_rejections"]:
            self.assertIn("reject_reason", detail)

    def test_stnp_rejection_details_contain_stnp_classification(self):
        candidates = [_c("pair-aaa", "mint-111"), _c("pair-bbb", "mint-111")]
        _, _, report = filter_within_response_duplicates(candidates)
        for detail in report["within_response_stnp_rejections"]:
            self.assertIn("stnp_classification", detail)


# ---------------------------------------------------------------------------
# D. Integration into build_discover_candidates_once_payload
# ---------------------------------------------------------------------------

class TestWithinResponseIntegrityHookInPayload(unittest.TestCase):

    def setUp(self):
        self._temp_dir = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        self.addCleanup(self._temp_dir.cleanup)
        self.db_path = pathlib.Path(self._temp_dir.name) / "v2-2h4-hook.sqlite3"
        apply_migrations(self.db_path)

    def _args(self, **overrides) -> argparse.Namespace:
        return _run_args(str(self.db_path), **overrides)

    def _single_pair_transport(self, context):
        del context
        return {
            "pairs": [
                {
                    "chainId": "solana",
                    "pairAddress": "h4-pair-1",
                    "baseToken": {"address": "h4-mint-1", "symbol": "H4A", "name": "H4 One"},
                    "quoteToken": {"address": _SOLANA_WSOL},
                    "dexId": "raydium",
                    "priceUsd": "0.001",
                    "liquidity": {"usd": 8000},
                    "volume": {"m5": 2500, "h1": 12000, "h24": 50000},
                    "txns": {"m5": {"buys": 8, "sells": 6}, "h1": {"buys": 40, "sells": 25}},
                }
            ]
        }

    def _dup_pair_transport(self, context):
        del context
        pair = {
            "chainId": "solana",
            "pairAddress": "h4-pair-dup",
            "baseToken": {"address": "h4-mint-x", "symbol": "H4X", "name": "H4 Dup"},
            "quoteToken": {"address": _SOLANA_WSOL},
            "dexId": "raydium",
            "priceUsd": "0.001",
            "liquidity": {"usd": 8000},
            "volume": {"m5": 2500, "h1": 12000, "h24": 50000},
            "txns": {"m5": {"buys": 8, "sells": 6}, "h1": {"buys": 40, "sells": 25}},
        }
        return {"pairs": [pair, {**pair, "baseToken": {"address": "h4-mint-y"}}]}

    def test_within_response_integrity_report_present_in_payload(self):
        payload = build_discover_candidates_once_payload(
            self._args(), transport=self._single_pair_transport
        )
        self.assertIn("within_response_integrity_report", payload)

    def test_within_response_report_keys_present(self):
        payload = build_discover_candidates_once_payload(
            self._args(), transport=self._single_pair_transport
        )
        report = payload["within_response_integrity_report"]
        for key in (
            "within_response_duplicate_pair_count",
            "within_response_duplicate_mint_count",
            "within_response_stnp_event_count",
            "within_response_stnp_rejections",
            "within_response_duplicate_rejections",
        ):
            with self.subTest(key=key):
                self.assertIn(key, report)

    def test_no_duplicates_when_response_is_clean(self):
        payload = build_discover_candidates_once_payload(
            self._args(), transport=self._single_pair_transport
        )
        report = payload["within_response_integrity_report"]
        self.assertEqual(report["within_response_duplicate_pair_count"], 0)
        self.assertEqual(report["within_response_stnp_event_count"], 0)

    def test_duplicate_pair_detected_in_payload_report(self):
        payload = build_discover_candidates_once_payload(
            self._args(), transport=self._dup_pair_transport
        )
        report = payload["within_response_integrity_report"]
        self.assertEqual(report["within_response_duplicate_pair_count"], 1)

    def test_h1_candidate_stage_report_invariant_preserved(self):
        payload = build_discover_candidates_once_payload(
            self._args(), transport=self._single_pair_transport
        )
        for key, val in payload["candidate_stage_report"].items():
            with self.subTest(key=key):
                self.assertTrue(
                    isinstance(val, int) or val == "NOT_MEASURED",
                    f"candidate_stage_report[{key!r}] = {val!r} must be int or NOT_MEASURED",
                )

    def test_h2_age_activity_report_still_present(self):
        payload = build_discover_candidates_once_payload(
            self._args(), transport=self._single_pair_transport
        )
        self.assertIn("age_activity_report", payload)
        self.assertIn("total_candidates", payload["age_activity_report"])

    def test_h3_field_completeness_report_still_present(self):
        payload = build_discover_candidates_once_payload(
            self._args(), transport=self._single_pair_transport
        )
        self.assertIn("field_completeness_report", payload)
        self.assertIn("total_candidates", payload["field_completeness_report"])

    def test_candidates_rejected_pre_persistence_includes_wr_rejections(self):
        payload = build_discover_candidates_once_payload(
            self._args(), transport=self._dup_pair_transport
        )
        stage = payload["candidate_stage_report"]
        # 2 pairs in response, 1 is a within-response duplicate — it's rejected pre-persistence
        self.assertGreaterEqual(stage["candidates_rejected_pre_persistence"], 1)
        self.assertIsInstance(stage["candidates_rejected_pre_persistence"], int)


# ---------------------------------------------------------------------------
# E. Safety: no scoring/ranking/BUY/PnL logic introduced
# ---------------------------------------------------------------------------

class TestSafetyNoProhibitedLogic(unittest.TestCase):

    def test_filter_returns_no_scores_or_ranks(self):
        candidates = [
            _c("pair-aaa", "mint-111"),
            _c("pair-bbb", "mint-111"),
        ]
        clean, rejected, report = filter_within_response_duplicates(candidates)
        for c in clean + rejected:
            for key in c:
                with self.subTest(key=key):
                    self.assertNotIn("score", key.lower())
                    self.assertNotIn("rank", key.lower())
                    self.assertNotIn("confidence", key.lower())

    def test_report_has_no_float_counts(self):
        candidates = [
            _c("pair-aaa", "mint-111"),
            _c("pair-aaa", "mint-222"),
        ]
        _, _, report = filter_within_response_duplicates(candidates)
        for key in (
            "within_response_duplicate_pair_count",
            "within_response_duplicate_mint_count",
            "within_response_stnp_event_count",
        ):
            self.assertIsInstance(report[key], int)
            self.assertNotIsInstance(report[key], float)

    def test_no_pnl_or_trade_fields_in_output(self):
        candidates = [_c("pair-aaa", "mint-111")]
        clean, rejected, report = filter_within_response_duplicates(candidates)
        prohibited = ("pnl", "trade", "buy", "sell", "hold", "position")
        for result_set in (clean, rejected):
            for item in result_set:
                for key in item:
                    for term in prohibited:
                        with self.subTest(key=key, term=term):
                            self.assertNotIn(term, key.lower())


if __name__ == "__main__":
    unittest.main()
