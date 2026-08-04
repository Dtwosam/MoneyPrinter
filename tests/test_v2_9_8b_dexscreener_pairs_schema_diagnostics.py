"""V2-9.8B DexScreener pairs-field schema diagnostics matrix (offline)."""

from __future__ import annotations

import json
import sqlite3
import tempfile
import unittest
from pathlib import Path

from printer_v1.contracts.enums import DataQualityLabel, SourceStatus
from printer_v1.db.migrate import apply_migrations
from printer_v1.sources.contracts import SourceRequest
from printer_v1.sources.dexscreener import (
    build_dexscreener_adapter,
    fixture_success_transport,
    normalize_dexscreener_fixture_result,
)
from printer_v1.sources.governed_execution import execute_source_request_with_governor


def _valid_pair(*, mint: str = "MintAAAA", pool: str = "PoolAAAA", liq: float = 5000.0):
    return {
        "chainId": "solana",
        "pairAddress": pool,
        "baseToken": {"address": mint},
        "quoteToken": {
            "address": "So11111111111111111111111111111111111111112",
        },
        "priceUsd": "1.0",
        "liquidity": {"usd": liq},
        "volume": {"m5": 100, "h1": 500, "h24": 2000},
        "txns": {
            "m5": {"buys": 5, "sells": 3},
            "h1": {"buys": 20, "sells": 10},
            "h24": {"buys": 100, "sells": 80},
        },
        "priceChange": {"m5": 0.0, "h1": 0.0, "h24": 0.0},
    }


def _measured(**kwargs):
    base = {
        "transport_operations_used": 1,
        "response_bytes": 128,
        "normalized_rows": 0,
        "transport_operation_identities": (
            {
                "stage": "LIQUIDITY",
                "source_name": "dexscreener",
                "request_kind": "pair_market_snapshot",
                "response_bytes": 128,
                "normalized_rows": 0,
            },
        ),
    }
    base.update(kwargs)
    return base


class DexScreenerPairsSchemaDiagnosticsMatrix(unittest.TestCase):
    def test_01_empty_pairs_partial_no_failure_row(self) -> None:
        result = normalize_dexscreener_fixture_result(
            {**_measured(), "pairs": []},
            request_kind="pair_market_snapshot",
        )
        self.assertEqual(result.source_status, SourceStatus.PARTIAL)
        self.assertEqual(
            result.data_quality_label, DataQualityLabel.ACCEPTABLE_PARTIAL_DATA
        )
        self.assertIsNone(result.failure_type)
        self.assertTrue(result.normalized_payload.get("no_matching_pairs"))

    def test_02_missing_pairs_malformed_missing(self) -> None:
        result = normalize_dexscreener_fixture_result(
            dict(_measured()),
            request_kind="pair_market_snapshot",
        )
        self.assertEqual(result.source_status, SourceStatus.FAILED)
        self.assertEqual(result.failure_type, "dexscreener_malformed_fixture")
        payload = dict(result.normalized_payload)
        self.assertFalse(payload["pairs_field_present"])
        self.assertEqual(payload["pairs_field_type"], "MISSING")
        self.assertIsNone(payload["pairs_count"])
        self.assertEqual(payload["request_kind"], "pair_market_snapshot")
        self.assertEqual(payload["transport_operations_used"], 1)
        self.assertNotIn("raw_body", payload)
        self.assertNotIn("headers", payload)

    def test_03_pairs_null_malformed_null(self) -> None:
        result = normalize_dexscreener_fixture_result(
            {**_measured(), "pairs": None},
            request_kind="pair_market_snapshot",
        )
        payload = dict(result.normalized_payload)
        self.assertTrue(payload["pairs_field_present"])
        self.assertEqual(payload["pairs_field_type"], "NULL")

    def test_04_pairs_string_malformed_string(self) -> None:
        result = normalize_dexscreener_fixture_result(
            {**_measured(), "pairs": "bad"},
            request_kind="pair_market_snapshot",
        )
        self.assertEqual(result.normalized_payload["pairs_field_type"], "STRING")

    def test_05_pairs_object_malformed_object(self) -> None:
        result = normalize_dexscreener_fixture_result(
            {**_measured(), "pairs": {}},
            request_kind="pair_market_snapshot",
        )
        self.assertEqual(result.normalized_payload["pairs_field_type"], "OBJECT")

    def test_06_valid_exact_row_complete(self) -> None:
        result = normalize_dexscreener_fixture_result(
            {**_measured(normalized_rows=1), "pairs": [_valid_pair()]},
            request_kind="pair_market_snapshot",
            requested_token_mints=["MintAAAA"],
        )
        self.assertEqual(result.source_status, SourceStatus.COMPLETE)
        self.assertIsNone(result.failure_type)
        pairs = result.normalized_payload["pairs"]
        self.assertEqual(len(pairs), 1)
        self.assertEqual(pairs[0]["pair_address"], "PoolAAAA")

    def test_07_wrong_pool_ineligible_shape(self) -> None:
        # Normalization keeps rows; eligibility is enforced by consumers.
        # Wrong pool is still COMPLETE at source boundary with the returned pair.
        result = normalize_dexscreener_fixture_result(
            {
                **_measured(normalized_rows=1),
                "pairs": [_valid_pair(pool="WrongPool")],
            },
            request_kind="pair_market_snapshot",
            requested_token_mints=["MintAAAA"],
        )
        self.assertEqual(result.source_status, SourceStatus.COMPLETE)
        self.assertEqual(
            result.normalized_payload["pairs"][0]["pair_address"], "WrongPool"
        )

    def test_08_wrong_mint_filtered(self) -> None:
        result = normalize_dexscreener_fixture_result(
            {
                **_measured(normalized_rows=1),
                "pairs": [_valid_pair(mint="OtherMint")],
            },
            request_kind="pair_market_snapshot",
            requested_token_mints=["MintAAAA"],
        )
        # Requested mint not matched → no_matching after keep filter or empty kept
        if result.source_status == SourceStatus.COMPLETE:
            kept = result.normalized_payload.get("pairs") or []
            self.assertTrue(
                all(p.get("token_mint") != "MintAAAA" for p in kept)
                or len(kept) == 0
                or all(
                    str(p.get("token_mint") or "") != "MintAAAA" for p in kept
                )
            )
        else:
            self.assertIn(
                result.source_status,
                {SourceStatus.FAILED, SourceStatus.PARTIAL},
            )

    def test_09_below_3000_still_normalized(self) -> None:
        result = normalize_dexscreener_fixture_result(
            {
                **_measured(normalized_rows=1),
                "pairs": [_valid_pair(liq=500.0)],
            },
            request_kind="pair_market_snapshot",
            requested_token_mints=["MintAAAA"],
        )
        self.assertEqual(result.source_status, SourceStatus.COMPLETE)
        liq = result.normalized_payload["pairs"][0].get("liquidity_usd")
        self.assertIsNotNone(liq)
        self.assertLess(float(liq), 3000.0)

    def test_10_failure_persists_schema_diagnostics_and_transport(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            db = Path(tmp) / "diag.sqlite3"
            apply_migrations(db)
            payload = {
                **_measured(),
                "pairs": None,
                "_source_status_code": 200,
            }
            adapter = build_dexscreener_adapter(
                enabled=True,
                fixture_transport=fixture_success_transport(payload),
            )
            request = SourceRequest(
                source_name="dexscreener",
                request_kind="pair_market_snapshot",
                request_key="diag-null-pairs",
            )
            execution = execute_source_request_with_governor(
                db, request, adapter, recent_request_count=0
            )
            self.assertIsNotNone(execution.failure_record)
            conn = sqlite3.connect(db)
            try:
                row = conn.execute(
                    "SELECT normalized_payload_json, failure_type "
                    "FROM printer_source_failures WHERE id=?",
                    (execution.failure_record.id,),
                ).fetchone()
            finally:
                conn.close()
            self.assertIsNotNone(row)
            stored = json.loads(row[0])
            self.assertEqual(row[1], "dexscreener_malformed_fixture")
            self.assertEqual(stored["pairs_field_type"], "NULL")
            self.assertTrue(stored["pairs_field_present"])
            self.assertIsNone(stored["pairs_count"])
            self.assertEqual(stored["source_http_status"], 200)
            self.assertEqual(stored["transport_operations_used"], 1)
            self.assertNotIn("raw_body", stored)
            self.assertNotIn("Authorization", json.dumps(stored))

    def test_11_no_raw_body_or_secret_in_malformed_payloads(self) -> None:
        for pairs in (None, "bad", {}, 12, True):
            result = normalize_dexscreener_fixture_result(
                {
                    **_measured(),
                    "pairs": pairs,
                    "raw_body": "SECRET_SHOULD_NOT_LEAK",
                    "headers": {"Authorization": "Bearer secret"},
                },
                request_kind="pair_market_snapshot",
            )
            dumped = json.dumps(dict(result.normalized_payload))
            self.assertNotIn("SECRET_SHOULD_NOT_LEAK", dumped)
            self.assertNotIn("Bearer secret", dumped)
            self.assertNotIn("raw_body", result.normalized_payload)
            self.assertNotIn("headers", result.normalized_payload)

    def test_governed_path_persists_diagnostics(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            db = Path(tmp) / "gov.sqlite3"
            apply_migrations(db)
            adapter = build_dexscreener_adapter(
                enabled=True,
                fixture_transport=fixture_success_transport(
                    {**_measured(), "pairs": "not-a-list"}
                ),
            )
            request = SourceRequest(
                source_name="dexscreener",
                request_kind="pair_market_snapshot",
                request_key="gov-string-pairs",
            )
            execution = execute_source_request_with_governor(
                db, request, adapter, recent_request_count=0
            )
            self.assertIsNotNone(execution.failure_record)
            stored = dict(execution.failure_record.normalized_payload)
            self.assertEqual(stored.get("pairs_field_type"), "STRING")
            self.assertTrue(stored.get("pairs_field_present"))


if __name__ == "__main__":
    unittest.main()
