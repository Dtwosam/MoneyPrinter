from __future__ import annotations

import json
import argparse
import pathlib
import sqlite3
import tempfile
import unittest
from datetime import datetime, timedelta, timezone

from printer_v1.db.migrate import apply_migrations
from printer_v1.discovery.parser import normalize_candidate
from printer_v1.discovery.selection_batch import (
    BUCKET_A1,
    BUCKET_A3,
    assign_bucket,
    build_batch_item,
)
from printer_v1.operator_cli.commands import (
    build_discover_candidates_once_payload,
    enrich_candidate_with_governed_t3,
)
from printer_v1.sources.solana_rpc_token_age import fixture_t3_success_transport


MINT = "A3ProofMint11111111111111111111111111111111"
PAIR = "A3ProofPair11111111111111111111111111111111"


def _market_candidate(**overrides):
    candidate = {
        "token_mint": MINT,
        "pair_address": PAIR,
        "chain": "solana",
        "source_name": "geckoterminal",
        "source_response_id": 77,
        "source_channel": "GECKOTERMINAL_NEW_POOL",
        "captured_at": datetime.now(timezone.utc).isoformat(),
        "liquidity_usd": 8_000.0,
        "volume_5m": 2_000.0,
        "txns_5m": 20,
        "volume_1h": 10_000.0,
        "volume_24h": 25_000.0,
        "txns_1h": 100,
        "txns_24h": 300,
        "price_change_5m": 2.0,
        "price_change_1h": -5.0,
        "token_created_at": None,
        "token_age_seconds": None,
        "token_age_evidence_tier": None,
        "pair_created_at": (datetime.now(timezone.utc) - timedelta(days=2)).isoformat(),
        "pair_age_seconds": 172_800.0,
    }
    candidate.update(overrides)
    return candidate


def _t3_payload(*, age_seconds: float = 7_200.0):
    captured = datetime.now(timezone.utc)
    created = captured - timedelta(seconds=age_seconds)
    return {
        "t3_status": "success",
        "token_mint": MINT,
        "captured_at": captured.isoformat(),
        "token_created_at": created.isoformat(),
        "token_age_seconds": age_seconds,
        "token_age_evidence_tier": "T3",
        "t3_requested_mint": MINT,
        "t3_rpc_host_redacted": "api.mainnet-beta.solana.com",
        "t3_rpc_methods_attempted": ["getAccountInfo", "getSignaturesForAddress", "getTransaction"],
        "t3_request_ids": [1, 2, 3],
        "t3_pages_fetched": 1,
        "t3_signatures_inspected": 1,
        "t3_accepted_signature": "a3-init-signature",
        "t3_accepted_slot": 123,
        "t3_block_time_raw": int(created.timestamp()),
        "t3_block_time_source": "getTransaction",
        "t3_instruction_type": "initializeMint2",
        "t3_token_program": "token_2022",
        "t3_derived_token_created_at": created.isoformat(),
        "t3_derived_token_age_seconds": age_seconds,
        "t3_captured_at": captured.isoformat(),
        "t3_commitment": "finalized",
        "t3_finality_status": "finalized",
    }


class A3CategoricalContractTests(unittest.TestCase):
    def test_qualifying_real_age_candidate_is_a3(self):
        self.assertEqual(assign_bucket(_market_candidate(token_age_seconds=7_200.0))[0], BUCKET_A3)

    def test_recent_token_does_not_qualify(self):
        self.assertEqual(assign_bucket(_market_candidate(token_age_seconds=3_599.0))[0], BUCKET_A1)

    def test_unknown_token_age_does_not_qualify(self):
        self.assertEqual(assign_bucket(_market_candidate(token_age_seconds=None))[0], BUCKET_A1)

    def test_pair_age_only_does_not_qualify(self):
        self.assertEqual(
            assign_bucket(_market_candidate(token_age_seconds=None, pair_age_seconds=999_999.0))[0],
            BUCKET_A1,
        )

    def test_missing_or_non_negative_price_change_does_not_qualify(self):
        self.assertEqual(assign_bucket(_market_candidate(token_age_seconds=7_200.0, price_change_1h=None))[0], BUCKET_A1)
        self.assertEqual(assign_bucket(_market_candidate(token_age_seconds=7_200.0, price_change_1h=0.0))[0], BUCKET_A1)


class A3GovernedT3HandoffTests(unittest.TestCase):
    def test_governed_t3_overlay_survives_normalization_and_batch_metadata(self):
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
            db_path = f"{tmp}/a3.sqlite3"
            apply_migrations(db_path)
            candidate = _market_candidate()
            report = enrich_candidate_with_governed_t3(
                db_path,
                candidate,
                request_key="a3-fixture-proof",
                transport=fixture_t3_success_transport(_t3_payload()),
            )
            self.assertTrue(report["evidence_applied"])
            self.assertEqual(report["bucket_after_enrichment"], BUCKET_A3)
            self.assertEqual(candidate["t3_discovery_source_response_id"], 77)

            persisted_shape = normalize_candidate("geckoterminal", candidate)
            self.assertEqual(persisted_shape["token_age_evidence_tier"], "T3")
            self.assertEqual(assign_bucket(persisted_shape)[0], BUCKET_A3)
            item = build_batch_item(
                persisted_shape,
                item_status="SELECTED",
                primary_bucket=BUCKET_A3,
                selection_reason="fixture_a3",
            )
            metadata = json.loads(item["candidate_metadata_json"])
            self.assertEqual(metadata["t3_source_response_id"], report["source_response_id"])
            self.assertEqual(metadata["t3_discovery_source_response_id"], 77)
            self.assertEqual(metadata["t3_accepted_signature"], "a3-init-signature")

            connection = sqlite3.connect(db_path)
            try:
                self.assertEqual(connection.execute("SELECT COUNT(*) FROM printer_source_requests").fetchone()[0], 1)
                self.assertEqual(connection.execute("SELECT COUNT(*) FROM printer_source_responses").fetchone()[0], 1)
                self.assertEqual(connection.execute("SELECT COUNT(*) FROM printer_source_failures").fetchone()[0], 0)
            finally:
                connection.close()

    def test_normal_governed_discovery_path_classifies_enriched_candidate_as_a3(self):
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
            db_path = f"{tmp}/a3-command.sqlite3"
            apply_migrations(db_path)

            def discovery_transport(_context):
                return {
                    "pairs": [{
                        "chainId": "solana",
                        "pairAddress": PAIR,
                        "baseToken": {"address": MINT, "symbol": "A3", "name": "A3 Proof"},
                        "quoteToken": {"address": "So11111111111111111111111111111111111111112"},
                        "dexId": "raydium",
                        "priceUsd": "0.001",
                        "liquidity": {"usd": 8000},
                        "volume": {"m5": 2500, "h1": 12000, "h24": 50000},
                        "txns": {"m5": {"buys": 8, "sells": 6}, "h1": {"buys": 40, "sells": 25}},
                        "priceChange": {"m5": 2.0, "h1": -5.0},
                    }]
                }

            args = argparse.Namespace(
                db_path=db_path,
                project_root=str(pathlib.Path(__file__).resolve().parents[1]),
                format="json",
                operator_approved=True,
                chain="solana",
                max_candidates=1,
                max_source_requests=1,
                query="pump",
                timeout_seconds=5.0,
                source_name="dexscreener",
                request_kind=None,
                request_key="a3-command-proof",
                enrich_15m_market_evidence=False,
                enrich_t3_token_age=True,
                t3_solana_rpc_url=None,
            )
            payload = build_discover_candidates_once_payload(
                args,
                transport=discovery_transport,
                enrichment_transports={
                    "t3_token_age": fixture_t3_success_transport(_t3_payload())
                },
            )
            self.assertEqual(payload["t3_token_age_enrichment_report"]["status"], "EVIDENCE_APPLIED")
            self.assertEqual(payload["t3_token_age_enrichment_report"]["bucket_after_enrichment"], BUCKET_A3)
            self.assertEqual(payload["accepted_candidates"], [])
            self.assertEqual(payload["selection_handoff_report"]["batch_status"], "REJECTED")
            self.assertEqual(payload["selection_handoff_report"]["active_handoff_count"], 0)

            connection = sqlite3.connect(db_path)
            try:
                row = connection.execute(
                    "SELECT normalized_candidate_payload_json FROM printer_discovery_candidates"
                ).fetchone()
                stored = json.loads(row[0])
                self.assertEqual(stored["token_age_evidence_tier"], "T3")
                self.assertEqual(assign_bucket(stored)[0], BUCKET_A3)
                self.assertIsNotNone(stored["t3_source_response_id"])
            finally:
                connection.close()


if __name__ == "__main__":
    unittest.main()
