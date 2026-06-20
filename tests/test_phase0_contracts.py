import inspect
import pathlib
import sys
import unittest

PROJECT_ROOT = pathlib.Path(__file__).resolve().parents[1]
SRC_PATH = PROJECT_ROOT / "src"
sys.path.insert(0, str(SRC_PATH))

from printer_v1.contracts import enums, rules
from printer_v1.contracts.enums import (
    DataQualityLabel,
    MemoryStatus,
    PaperAction,
    SourceStatus,
)


def enum_values(enum_type):
    return {item.value for item in enum_type}


class Phase0ContractsTest(unittest.TestCase):
    def test_paper_actions_match_docs_exactly(self):
        self.assertEqual(
            enum_values(PaperAction),
            {"BUY", "SELL", "HOLD", "WAIT", "AVOID", "NO_ACTION"},
        )

    def test_all_v1_bans_exist(self):
        self.assertEqual(
            rules.V1_BANS,
            frozenset(
                {
                    "live_trading",
                    "wallet_connection",
                    "private_keys",
                    "real_funds",
                    "live_execution",
                    "paid_api_dependency",
                    "scoring_system",
                    "multi_chain_logic",
                    "engine_direct_external_source_calls",
                    "engine_independent_timing_loops",
                    "paper_buy_without_clean_memory_comparison",
                }
            ),
        )

    def test_printer_chain_and_mode_are_locked(self):
        self.assertEqual(rules.PRINTER_CHAIN, "solana")
        self.assertEqual(rules.PRINTER_MODE, "paper_only")

    def test_source_status_labels_match_docs(self):
        self.assertEqual(
            enum_values(SourceStatus),
            {"COMPLETE", "PARTIAL", "FAILED", "STALE", "CONFLICTING"},
        )

    def test_data_quality_labels_match_docs(self):
        self.assertEqual(
            enum_values(DataQualityLabel),
            {
                "CLEAN_DATA",
                "ACCEPTABLE_PARTIAL_DATA",
                "DIRTY_DATA",
                "STALE_DATA",
                "MISSING_CRITICAL_DATA",
                "CONFLICTING_DATA",
                "DO_NOT_TRAIN",
            },
        )

    def test_memory_status_labels_match_docs(self):
        self.assertEqual(
            enum_values(MemoryStatus),
            {
                "CLEAN_MEMORY",
                "PARTIAL_MEMORY",
                "DIRTY_MEMORY",
                "DO_NOT_TRAIN",
                "AUDIT_ONLY",
            },
        )

    def test_no_score_confidence_or_ranking_enum_exists(self):
        enum_names = {
            name.lower()
            for name, value in inspect.getmembers(enums, inspect.isclass)
            if value.__module__ == enums.__name__
        }
        forbidden_fragments = {"score", "confidence", "ranking", "rank"}
        self.assertFalse(
            any(fragment in name for name in enum_names for fragment in forbidden_fragments)
        )

    def test_no_wallet_live_or_private_key_capability_is_exposed(self):
        exposed_names = set(rules.__all__) if hasattr(rules, "__all__") else set(dir(rules))
        exposed_text = " ".join(sorted(exposed_names)).lower()
        self.assertNotIn("sign_transaction", exposed_text)
        self.assertNotIn("execute_trade", exposed_text)
        self.assertNotIn("live_trade", exposed_text)
        self.assertTrue(rules.is_banned_v1_capability("wallet_connection"))
        self.assertTrue(rules.is_banned_v1_capability("private_keys"))
        self.assertTrue(rules.is_banned_v1_capability("live_trading"))


if __name__ == "__main__":
    unittest.main()
