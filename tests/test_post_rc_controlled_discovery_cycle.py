import argparse
import pathlib
import sqlite3
import sys
import tempfile
import tomllib
import unittest

PROJECT_ROOT = pathlib.Path(__file__).resolve().parents[1]
SRC_PATH = PROJECT_ROOT / "src"
sys.path.insert(0, str(SRC_PATH))

from printer_v1.db import apply_migrations
from printer_v1.operator_cli.commands import build_discover_candidates_once_payload


def table_count(connection, table_name):
    return int(connection.execute(f"SELECT COUNT(*) FROM {table_name}").fetchone()[0])


class PostRcControlledDiscoveryCycleTests(unittest.TestCase):
    def make_db(self):
        temp_dir = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        db_path = pathlib.Path(temp_dir.name) / "post-rc-discovery.sqlite3"
        apply_migrations(db_path)
        self.addCleanup(temp_dir.cleanup)
        return db_path

    def args(self, db_path, **overrides):
        values = {
            "db_path": str(db_path),
            "project_root": str(PROJECT_ROOT),
            "format": "json",
            "no_color": True,
            "operator_approved": True,
            "chain": "solana",
            "max_candidates": 1,
            "query": "pump",
            "timeout_seconds": 5.0,
            "source_name": "dexscreener",
            "request_key": "post-rc-test-discovery",
        }
        values.update(overrides)
        return argparse.Namespace(**values)

    def success_transport(self, context):
        del context
        return {
            "pairs": [
                {
                    "chainId": "solana",
                    "pairAddress": "fresh-pair-1",
                    "baseToken": {"address": "fresh-mint-1", "symbol": "FRESH1", "name": "Fresh One"},
                    "quoteToken": {"address": "So11111111111111111111111111111111111111112"},
                    "dexId": "raydium",
                    "priceUsd": "0.001",
                    "liquidity": {"usd": 8000},
                    "volume": {"m5": 2500, "h1": 12000, "h24": 50000},
                    "txns": {"m5": {"buys": 8, "sells": 6}, "h1": {"buys": 40, "sells": 25}},
                },
                {
                    "chainId": "solana",
                    "pairAddress": "fresh-pair-2",
                    "baseToken": {"address": "fresh-mint-2", "symbol": "FRESH2", "name": "Fresh Two"},
                    "quoteToken": {"address": "So11111111111111111111111111111111111111112"},
                    "dexId": "raydium",
                    "priceUsd": "0.002",
                    "liquidity": {"usd": 3000},
                    "volume": {"m5": 50, "h1": 300, "h24": 1000},
                    "txns": {"m5": {"buys": 1, "sells": 1}},
                },
            ]
        }

    def weak_copycat_transport(self, context):
        del context
        return {
            "pairs": [
                {
                    "chainId": "solana",
                    "pairAddress": "copycat-pair-1",
                    "baseToken": {"address": "copycat-mint-1", "symbol": "PUMP", "name": "Pump.fun"},
                    "quoteToken": {"address": "So11111111111111111111111111111111111111112"},
                    "dexId": "raydium",
                    "priceUsd": "0.001",
                    "liquidity": {"usd": 8000},
                    "volume": {"m5": 0, "h1": 0, "h24": 4.65},
                    "txns": {"m5": 0, "h1": 0, "h24": 2},
                }
            ]
        }

    def active_same_symbol_transport(self, context):
        del context
        return {
            "pairs": [
                {
                    "chainId": "solana",
                    "pairAddress": "active-pump-pair",
                    "baseToken": {"address": "active-pump-mint", "symbol": "PUMP", "name": "Pump.fun"},
                    "quoteToken": {"address": "So11111111111111111111111111111111111111112"},
                    "dexId": "raydium",
                    "priceUsd": "0.003",
                    "liquidity": {"usd": 9000},
                    "volume": {"m5": 1800, "h1": 12000, "h24": 50000},
                    "txns": {"m5": 15, "h1": 80, "h24": 300},
                }
            ]
        }

    def test_command_exists_in_pyproject(self):
        scripts = tomllib.loads((PROJECT_ROOT / "pyproject.toml").read_text(encoding="utf-8"))["project"]["scripts"]
        self.assertEqual(
            scripts["printer-discover-candidates-once"],
            "printer_v1.operator_cli.commands:main_discover_candidates_once",
        )
        self.assertNotIn("printer-run-phase39", scripts)

    def test_requires_operator_approval(self):
        db_path = self.make_db()
        with self.assertRaisesRegex(ValueError, "operator approval"):
            build_discover_candidates_once_payload(
                self.args(db_path, operator_approved=False),
                transport=self.success_transport,
            )

    def test_rejects_non_solana_chain_and_candidate_cap(self):
        db_path = self.make_db()
        with self.assertRaisesRegex(ValueError, "Solana-only"):
            build_discover_candidates_once_payload(self.args(db_path, chain="ethereum"), transport=self.success_transport)
        # V2-2H.1 repaired the candidate cap from a hardcoded 1-3 range to a
        # configurable 1-50 range; values within the old cap (e.g. 4) must now
        # be accepted, and only values outside the new bound are rejected.
        with self.assertRaisesRegex(ValueError, "between 1 and 50"):
            build_discover_candidates_once_payload(self.args(db_path, max_candidates=51), transport=self.success_transport)
        with self.assertRaisesRegex(ValueError, "between 1 and 50"):
            build_discover_candidates_once_payload(self.args(db_path, max_candidates=0), transport=self.success_transport)

    def test_discovers_one_fresh_candidate_through_source_governor(self):
        db_path = self.make_db()
        payload = build_discover_candidates_once_payload(self.args(db_path), transport=self.success_transport)
        self.assertEqual(payload["source_request_delta"], 1)
        self.assertEqual(payload["source_response_delta"], 1)
        self.assertEqual(payload["source_failure_delta"], 0)
        self.assertEqual(payload["candidates_accepted"], 0)
        self.assertEqual(payload["token_delta"], 1)
        self.assertEqual(payload["pair_delta"], 1)
        self.assertEqual(payload["tracking_queue_delta"], 0)
        self.assertEqual(payload["paper_decision_delta"], 0)
        self.assertEqual(payload["paper_position_delta"], 0)
        self.assertEqual(payload["audited_discovery_results"][0]["classification"], "TRACK_FAST")
        self.assertEqual(payload["selection_handoff_report"]["batch_status"], "REJECTED")
        connection = sqlite3.connect(db_path)
        try:
            self.assertEqual(table_count(connection, "printer_discovery_candidates"), 1)
            self.assertEqual(table_count(connection, "printer_paper_decisions"), 0)
            self.assertEqual(table_count(connection, "printer_paper_positions"), 0)
            running = connection.execute("SELECT COUNT(*) FROM printer_scheduler_jobs WHERE status = 'RUNNING'").fetchone()[0]
        finally:
            connection.close()
        self.assertEqual(int(running), 0)

    def test_duplicate_existing_token_pair_is_not_reselected(self):
        db_path = self.make_db()
        connection = sqlite3.connect(db_path)
        try:
            cursor = connection.execute(
                """
                INSERT INTO printer_tokens (token_mint, chain, symbol, name, token_status)
                VALUES ('fresh-mint-1', 'solana', 'OLD', 'Old Existing', 'TRACK_NORMAL')
                """
            )
            token_id = int(cursor.lastrowid)
            connection.execute(
                """
                INSERT INTO printer_pairs (token_id, pair_address, dex, pool_source, base_token_mint)
                VALUES (?, 'fresh-pair-1', 'raydium', 'dexscreener', 'fresh-mint-1')
                """,
                (token_id,),
            )
            connection.commit()
        finally:
            connection.close()
        payload = build_discover_candidates_once_payload(self.args(db_path), transport=self.success_transport)
        self.assertEqual(payload["candidates_accepted"], 1)
        self.assertEqual(payload["accepted_candidates"][0]["token_mint"], "fresh-mint-2")
        self.assertEqual(payload["accepted_candidates"][0]["tracking_label"], "TRACK_NORMAL")

    def test_weak_same_symbol_candidate_is_not_promoted_to_memory_growth(self):
        db_path = self.make_db()
        connection = sqlite3.connect(db_path)
        try:
            connection.execute(
                """
                INSERT INTO printer_tokens (token_mint, chain, symbol, name, token_status)
                VALUES ('old-pump-mint', 'solana', 'PUMP', 'Pump.fun', 'TRACK_NORMAL')
                """
            )
            connection.commit()
        finally:
            connection.close()

        payload = build_discover_candidates_once_payload(self.args(db_path), transport=self.weak_copycat_transport)

        self.assertEqual(payload["candidates_accepted"], 0)
        self.assertEqual(payload["candidates_rejected"], 1)
        self.assertEqual(payload["rejected_candidates"][0]["reject_reason"], "weak_copycat_candidate")
        self.assertEqual(payload["tracking_queue_delta"], 0)

    def test_active_distinct_same_symbol_candidate_is_not_globally_blocked(self):
        db_path = self.make_db()
        connection = sqlite3.connect(db_path)
        try:
            connection.execute(
                """
                INSERT INTO printer_tokens (token_mint, chain, symbol, name, token_status)
                VALUES ('old-pump-mint', 'solana', 'PUMP', 'Pump.fun', 'TRACK_NORMAL')
                """
            )
            connection.commit()
        finally:
            connection.close()

        payload = build_discover_candidates_once_payload(self.args(db_path), transport=self.active_same_symbol_transport)

        self.assertEqual(payload["candidates_accepted"], 0)
        self.assertEqual(payload["selection_handoff_report"]["batch_status"], "REJECTED")
        self.assertEqual(payload["selection_handoff_report"]["discovery_evidence_only_count"], 1)

    def test_same_token_mint_different_pair_is_explicit_duplicate(self):
        db_path = self.make_db()
        connection = sqlite3.connect(db_path)
        try:
            connection.execute(
                """
                INSERT INTO printer_tokens (token_mint, chain, symbol, name, token_status)
                VALUES ('copycat-mint-1', 'solana', 'PUMP', 'Pump.fun', 'TRACK_NORMAL')
                """
            )
            connection.commit()
        finally:
            connection.close()

        payload = build_discover_candidates_once_payload(self.args(db_path), transport=self.weak_copycat_transport)

        self.assertEqual(payload["candidates_accepted"], 0)
        self.assertEqual(payload["rejected_candidates"][0]["reject_reason"], "duplicate_existing_token_mint")


if __name__ == "__main__":
    unittest.main()
