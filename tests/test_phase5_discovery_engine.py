import inspect
import pathlib
import sqlite3
import sys
import tempfile
import unittest
from contextlib import contextmanager
from datetime import datetime, timezone

PROJECT_ROOT = pathlib.Path(__file__).resolve().parents[1]
SRC_PATH = PROJECT_ROOT / "src"
sys.path.insert(0, str(SRC_PATH))

from printer_v1.db import apply_migrations
from printer_v1.discovery import classifier, discovery, parser
from printer_v1.discovery.classifier import classify_discovery_candidate
from printer_v1.discovery.contracts import (
    DiscoveryCandidateLabel,
    DiscoveryOutputAction,
    DiscoveryPayloadState,
)
from printer_v1.discovery.discovery import process_discovery_payload
from printer_v1.discovery.parser import (
    normalize_candidates,
    normalize_candidate,
    validate_discovery_payload,
)


REQUIRED_PAYLOAD_STATES = {
    "VALID_PAYLOAD",
    "PARTIAL_PAYLOAD",
    "MISSING_CRITICAL_FIELDS",
    "UNSUPPORTED_CHAIN",
    "UNSUPPORTED_PAIR",
    "STALE_SOURCE_DATA",
    "CONFLICTING_SOURCE_DATA",
}

REQUIRED_CANDIDATE_LABELS = {
    "NEW_CANDIDATE",
    "EXISTING_TOKEN_NEW_PAIR",
    "EXISTING_TOKEN_EXISTING_PAIR",
    "DUPLICATE_IGNORED",
    "INSTANT_REJECT",
    "WATCH_ONLY_CANDIDATE",
    "TRACK_NORMAL_CANDIDATE",
    "TRACK_FAST_CANDIDATE",
}

REQUIRED_OUTPUT_ACTIONS = {
    "IGNORE",
    "WATCH_ONLY",
    "TRACK_NORMAL",
    "TRACK_FAST",
    "INSTANT_REJECT_MEMORY_ONLY",
}

FORBIDDEN_FRAGMENTS = {
    "score",
    "confidence",
    "rank",
    "rating",
    "weight",
    "wallet",
    "private_key",
    "signed_tx",
    "live_trade",
}


class Phase5DiscoveryEngineTest(unittest.TestCase):
    def setUp(self):
        self.tempdir = tempfile.TemporaryDirectory()
        self.db_path = pathlib.Path(self.tempdir.name) / "printer.sqlite3"
        apply_migrations(self.db_path)
        self.now = datetime(2026, 6, 19, 12, 0, tzinfo=timezone.utc)

    def tearDown(self):
        self.tempdir.cleanup()

    @contextmanager
    def connect(self):
        connection = sqlite3.connect(self.db_path)
        connection.row_factory = sqlite3.Row
        try:
            yield connection
            connection.commit()
        finally:
            connection.close()

    def dexscreener_payload(self, *, mint="mint-fast", pair="pair-fast"):
        return {
            "pairs": [
                {
                    "chainId": "solana",
                    "pairAddress": pair,
                    "dexId": "raydium",
                    "baseToken": {"address": mint, "symbol": "FAST", "name": "Fast Coin"},
                    "quoteToken": {"address": "So11111111111111111111111111111111111111112"},
                    "priceUsd": "0.01",
                    "liquidity": {"usd": 10000},
                    "volume": {"m5": 2500, "m15": 5000, "h1": 12000, "h24": 50000},
                    "txns": {"m5": 12, "m15": 30, "h1": 80, "h24": 300},
                    "fdv": 100000,
                    "marketCap": 90000,
                    "captured_at": self.now.isoformat(),
                }
            ]
        }

    def gecko_payload(self):
        return {
            "data": [
                {
                    "id": "solana_pair_gecko",
                    "attributes": {
                        "chain": "solana",
                        "address": "gecko-pair",
                        "base_token_address": "gecko-mint",
                        "quote_token_address": "So11111111111111111111111111111111111111112",
                        "name": "Gecko Coin",
                        "symbol": "GECKO",
                        "dex": "orca",
                        "pool_source": "geckoterminal",
                        "price_usd": "0.02",
                        "reserve_in_usd": "2200",
                        "volume_5m": "20",
                        "volume_15m": "80",
                        "volume_1h": "200",
                        "volume_24h": "5000",
                        "txns_5m": "1",
                        "txns_15m": "2",
                        "txns_1h": "8",
                        "txns_24h": "100",
                        "captured_at": self.now.isoformat(),
                    },
                }
            ]
        }

    def pumpportal_payload(self):
        return {
            "tokens": [
                {
                    "chain": "solana",
                    "mint": "pump-mint",
                    "pairAddress": "pump-pair",
                    "symbol": "PUMP",
                    "name": "Pump Coin",
                    "dex": "pumpfun",
                    "poolSource": "pumpportal",
                    "price_usd": "0.001",
                    "liquidity_usd": 100,
                    "captured_at": self.now.isoformat(),
                }
            ]
        }

    def count_rows(self, table):
        with self.connect() as connection:
            return connection.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]

    def test_discovery_files_import_successfully(self):
        self.assertTrue(inspect.ismodule(parser))
        self.assertTrue(inspect.ismodule(classifier))
        self.assertTrue(inspect.ismodule(discovery))

    def test_lifecycle_package_has_dunder_init_not_accidental_init(self):
        self.assertTrue((SRC_PATH / "printer_v1" / "lifecycle" / "__init__.py").exists())
        self.assertFalse((SRC_PATH / "printer_v1" / "lifecycle" / "init.py").exists())

    def test_all_required_discovery_payload_states_exist(self):
        self.assertEqual({state.value for state in DiscoveryPayloadState}, REQUIRED_PAYLOAD_STATES)

    def test_all_required_discovery_candidate_labels_exist(self):
        self.assertEqual(
            {label.value for label in DiscoveryCandidateLabel},
            REQUIRED_CANDIDATE_LABELS,
        )

    def test_all_required_discovery_output_actions_exist(self):
        self.assertEqual(
            {action.value for action in DiscoveryOutputAction},
            REQUIRED_OUTPUT_ACTIONS,
        )

    def test_parser_rejects_unknown_sources(self):
        with self.assertRaises(ValueError):
            validate_discovery_payload("paid_birdeye", self.dexscreener_payload(), self.now)

    def test_parser_rejects_non_solana_candidates(self):
        payload = self.dexscreener_payload()
        payload["pairs"][0]["chainId"] = "ethereum"
        result = validate_discovery_payload("dexscreener", payload, self.now)
        self.assertEqual(result.state, DiscoveryPayloadState.UNSUPPORTED_CHAIN)

    def test_parser_labels_missing_critical_fields(self):
        payload = self.dexscreener_payload()
        del payload["pairs"][0]["pairAddress"]
        result = validate_discovery_payload("dexscreener", payload, self.now)
        self.assertEqual(result.state, DiscoveryPayloadState.MISSING_CRITICAL_FIELDS)

    def test_parser_normalizes_fake_dexscreener_payload(self):
        candidate = normalize_candidates("dexscreener", self.dexscreener_payload())[0]
        self.assertEqual(candidate["token_mint"], "mint-fast")
        self.assertEqual(candidate["pair_address"], "pair-fast")
        self.assertEqual(candidate["chain"], "solana")
        self.assertEqual(candidate["liquidity_usd"], 10000.0)

    def test_parser_normalizes_fake_geckoterminal_payload(self):
        candidate = normalize_candidates("geckoterminal", self.gecko_payload())[0]
        self.assertEqual(candidate["token_mint"], "gecko-mint")
        self.assertEqual(candidate["pair_address"], "gecko-pair")
        self.assertEqual(candidate["liquidity_usd"], 2200.0)

    def test_parser_normalizes_fake_pumpportal_payload(self):
        candidate = normalize_candidates("pumpportal", self.pumpportal_payload())[0]
        self.assertEqual(candidate["token_mint"], "pump-mint")
        self.assertEqual(candidate["pair_address"], "pump-pair")
        self.assertEqual(candidate["chain"], "solana")

    def test_classifier_sends_unsupported_chain_to_instant_reject(self):
        candidate = normalize_candidates("dexscreener", self.dexscreener_payload())[0]
        candidate["chain"] = "ethereum"
        classification = classify_discovery_candidate(candidate)
        self.assertEqual(
            classification.discovery_action,
            DiscoveryOutputAction.INSTANT_REJECT_MEMORY_ONLY,
        )

    def test_classifier_sends_missing_critical_data_to_watch_or_reject(self):
        candidate = normalize_candidates("pumpportal", self.pumpportal_payload())[0]
        candidate["price_usd"] = None
        classification = classify_discovery_candidate(candidate)
        self.assertIn(
            classification.discovery_action,
            {DiscoveryOutputAction.WATCH_ONLY, DiscoveryOutputAction.INSTANT_REJECT_MEMORY_ONLY},
        )

    def test_classifier_sends_clean_usable_solana_candidate_to_track_normal(self):
        candidate = normalize_candidates("geckoterminal", self.gecko_payload())[0]
        classification = classify_discovery_candidate(candidate)
        self.assertEqual(classification.discovery_action, DiscoveryOutputAction.TRACK_NORMAL)

    def test_dead_1h_and_weak_24h_candidate_is_not_memory_growth_tracking(self):
        candidate = normalize_candidates("dexscreener", self.dexscreener_payload())[0]
        candidate.update(
            {
                "volume_5m": 0,
                "txns_5m": 0,
                "volume_1h": 0,
                "txns_1h": 0,
                "volume_24h": 4.65,
                "txns_24h": 2,
            }
        )
        classification = classify_discovery_candidate(candidate)

        self.assertEqual(classification.discovery_action, DiscoveryOutputAction.WATCH_ONLY)
        self.assertNotEqual(classification.discovery_action, DiscoveryOutputAction.TRACK_NORMAL)
        self.assertNotEqual(classification.discovery_action, DiscoveryOutputAction.TRACK_FAST)
        self.assertEqual(classification.reason, "insufficient_activity_for_memory_growth")

    def test_classifier_sends_strong_fresh_candidate_to_track_fast(self):
        candidate = normalize_candidates("dexscreener", self.dexscreener_payload())[0]
        classification = classify_discovery_candidate(candidate)
        self.assertEqual(classification.discovery_action, DiscoveryOutputAction.TRACK_FAST)

    def test_classifier_does_not_create_forbidden_concepts(self):
        names = " ".join(name.lower() for name, _ in inspect.getmembers(classifier))
        self.assertFalse(any(fragment in names for fragment in FORBIDDEN_FRAGMENTS))

    def test_process_discovery_payload_inserts_token_and_pair_rows(self):
        process_discovery_payload(self.db_path, "dexscreener", self.dexscreener_payload(), self.now)
        self.assertEqual(self.count_rows("printer_tokens"), 1)
        self.assertEqual(self.count_rows("printer_pairs"), 1)

    def test_process_discovery_payload_prevents_duplicate_token_and_pair_rows(self):
        payload = self.dexscreener_payload()
        process_discovery_payload(self.db_path, "dexscreener", payload, self.now)
        process_discovery_payload(self.db_path, "dexscreener", payload, self.now)
        self.assertEqual(self.count_rows("printer_tokens"), 1)
        self.assertEqual(self.count_rows("printer_pairs"), 1)

    def test_process_discovery_payload_records_candidate_audit(self):
        process_discovery_payload(self.db_path, "dexscreener", self.dexscreener_payload(), self.now)
        self.assertEqual(self.count_rows("printer_discovery_candidates"), 1)

    def test_track_fast_candidate_creates_tracking_queue_row(self):
        process_discovery_payload(self.db_path, "dexscreener", self.dexscreener_payload(), self.now)
        with self.connect() as connection:
            row = connection.execute("SELECT tracking_lane FROM printer_tracking_queue").fetchone()
        self.assertEqual(row["tracking_lane"], "TRACK_FAST")

    def test_track_normal_candidate_creates_tracking_queue_row(self):
        process_discovery_payload(self.db_path, "geckoterminal", self.gecko_payload(), self.now)
        with self.connect() as connection:
            row = connection.execute("SELECT tracking_lane FROM printer_tracking_queue").fetchone()
        self.assertEqual(row["tracking_lane"], "TRACK_NORMAL")

    def test_watch_only_candidate_creates_tracking_queue_row(self):
        process_discovery_payload(self.db_path, "pumpportal", self.pumpportal_payload(), self.now)
        with self.connect() as connection:
            row = connection.execute("SELECT tracking_lane FROM printer_tracking_queue").fetchone()
        self.assertEqual(row["tracking_lane"], "WATCH_ONLY")

    def test_instant_reject_candidate_does_not_create_active_tracking_row(self):
        payload = self.dexscreener_payload()
        payload["pairs"][0]["chainId"] = "ethereum"
        process_discovery_payload(self.db_path, "dexscreener", payload, self.now)
        self.assertEqual(self.count_rows("printer_tracking_queue"), 0)

    def test_discovery_feeds_lifecycle_event_state(self):
        process_discovery_payload(self.db_path, "dexscreener", self.dexscreener_payload(), self.now)
        with self.connect() as connection:
            row = connection.execute("SELECT new_state FROM printer_token_lifecycle_events").fetchone()
        self.assertEqual(row["new_state"], "TRACK_FAST")

    def test_discovery_enqueues_scheduler_rows_only(self):
        process_discovery_payload(self.db_path, "dexscreener", self.dexscreener_payload(), self.now)
        with self.connect() as connection:
            row = connection.execute("SELECT status FROM printer_scheduler_jobs").fetchone()
            running = connection.execute(
                "SELECT COUNT(*) FROM printer_scheduler_jobs WHERE status = 'RUNNING'"
            ).fetchone()[0]
        self.assertEqual(row["status"], "PENDING")
        self.assertEqual(running, 0)

    def test_no_paper_decision_or_position_rows_are_created(self):
        process_discovery_payload(self.db_path, "dexscreener", self.dexscreener_payload(), self.now)
        self.assertEqual(self.count_rows("printer_paper_decisions"), 0)
        self.assertEqual(self.count_rows("printer_paper_positions"), 0)

    def test_no_live_network_calls_source_adapters_or_runtime_loop_exist(self):
        source_text = "\n".join(
            inspect.getsource(obj)
            for module in (parser, classifier, discovery)
            for _, obj in inspect.getmembers(module, inspect.isfunction)
            if obj.__module__ == module.__name__
        )
        for fragment in (
            "requests.get",
            "requests.post",
            "httpx",
            "aiohttp",
            "urllib.request",
            "while True",
        ):
            self.assertNotIn(fragment, source_text)

    def test_no_forbidden_concept_or_capability_is_introduced(self):
        names = []
        for module in (parser, classifier, discovery):
            names.extend(name.lower() for name, _ in inspect.getmembers(module))
        joined_names = " ".join(names)
        self.assertFalse(any(fragment in joined_names for fragment in FORBIDDEN_FRAGMENTS))


if __name__ == "__main__":
    unittest.main()
