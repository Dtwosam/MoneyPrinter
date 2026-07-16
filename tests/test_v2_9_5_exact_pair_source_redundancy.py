"""V2-9.5 unified exact-pair snapshot source redundancy — deterministic proof.

Fixture-only. No live source calls. Proves the governed DexScreener -> single
GeckoTerminal fallback contract:

- primary success makes no fallback call;
- an eligible transient primary failure plus a valid fallback creates exactly
  one snapshot, attributed to GeckoTerminal;
- both attempts stay visible and budgeted, and the primary failure is preserved;
- identity-mismatch / stale / missing-field / malformed fallback responses are
  blocked (fail closed);
- non-transient primary failures do not fall back;
- a fallback failure fails closed on the preserved primary cause;
- no duplicate jobs, snapshots, or evidence.
"""

from __future__ import annotations

from contextlib import closing
from pathlib import Path
import sqlite3
import tempfile
import unittest

from printer_v1.db import apply_migrations
from printer_v1.operator_cli.one_command_15m_factory import _execute_snapshot, _run_request_count
from printer_v1.operator_cli.exact_pair_source_redundancy import (
    ELIGIBLE_TRANSIENT_PRIMARY_FAILURE_TYPES,
    is_eligible_transient_primary_failure,
)
from printer_v1.sources.dexscreener import build_dexscreener_adapter
from printer_v1.sources.geckoterminal import build_geckoterminal_adapter

MINT = "G9j8WWDeJXZdvwQgP82ooDuHmpc3Gy8NCSins71Lpump"
PAIR = "HuqmPUBBdq8w56Y6WGd8LiMbf4zgYXS2ACzLZs8MYLna"
RUN_ID = "run-v2-9-5"
T0 = "2026-07-16T09:00:00+00:00"


def _dex_success_payload():
    return {
        "_source_status_code": 200,
        "pairs": [{
            "chainId": "solana",
            "pairAddress": PAIR,
            "baseToken": {"address": MINT, "symbol": "TOK", "name": "Token"},
            "priceUsd": "0.00265",
            "liquidity": {"usd": 272141.56},
            "volume": {"m5": 1125.0, "h1": 47310.0, "h24": 1590700.0},
            "txns": {"m5": {"buys": 170, "sells": 63}, "h1": {"buys": 2402, "sells": 970},
                     "h24": {"buys": 53860, "sells": 23746}},
            "fdv": 1000000.0,
            "marketCap": 900000.0,
            "priceChange": {"m5": -2.6, "h1": 1.2, "h24": 5.5},
            "pairCreatedAt": 1_700_000_000_000,
        }],
    }


def _dex_failure_payload(failure_type: str):
    return {
        "fixture_status": "failure",
        "failure_type": failure_type,
        "failure_message": f"simulated {failure_type}",
    }


def _gt_pool_attributes(**overrides):
    attrs = {
        "address": PAIR,
        "name": "TOK / SOL",
        "base_token_price_usd": "0.00265",
        "reserve_in_usd": "272141.56",
        "fdv_usd": "1000000",
        "market_cap_usd": "900000",
        "pool_created_at": "2026-07-15T20:00:00Z",
        "volume_usd": {"m5": "1125", "h1": "47310", "h24": "1590700"},
        "transactions": {
            "m5": {"buys": 170, "sells": 63},
            "h1": {"buys": 2402, "sells": 970},
            "h24": {"buys": 53860, "sells": 23746},
        },
        "price_change_percentage": {"m5": "-2.6", "h1": "1.2", "h24": "5.5"},
    }
    attrs.update(overrides)
    return attrs


def _gt_payload(*, pool_address=PAIR, token_mint=MINT, network="solana",
                stale=False, attributes=None):
    return {
        "data": {
            "id": f"solana_{pool_address}",
            "type": "pool",
            "attributes": attributes if attributes is not None else _gt_pool_attributes(),
            "relationships": {"base_token": {"data": {"id": f"solana_{token_mint}"}}},
        },
        "_requested_pool_address": pool_address,
        "_requested_token_mint": token_mint,
        "_requested_network": network,
        "_requested_endpoint": "fixture",
        "_source_status_code": 200,
        "fixture_stale": stale,
    }


def _gt_failure_payload():
    return {
        "fixture_status": "failure",
        "failure_type": "geckoterminal_transport_failure",
        "failure_message": "simulated geckoterminal transport failure",
    }


class ExactPairSourceRedundancyTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory(dir=Path.cwd())
        self.db_path = Path(self.temp.name) / "proof.sqlite3"
        apply_migrations(self.db_path)
        self.conn = sqlite3.connect(self.db_path)
        self.conn.row_factory = sqlite3.Row
        self.conn.execute("PRAGMA foreign_keys=ON")
        self._seed_run_and_step()

    def tearDown(self) -> None:
        self.conn.close()
        self.temp.cleanup()

    def _seed_run_and_step(self) -> None:
        c = self.conn
        c.execute(
            "INSERT INTO printer_tokens (token_mint, chain, token_status, first_seen_at,"
            " last_seen_at, created_at, updated_at) VALUES (?, 'solana', 'TRACKING', ?, ?, ?, ?)",
            (MINT, T0, T0, T0, T0),
        )
        token_id = int(c.execute("SELECT id FROM printer_tokens WHERE token_mint=?", (MINT,)).fetchone()["id"])
        c.execute(
            "INSERT INTO printer_pairs (token_id, pair_address, base_token_mint, first_seen_at,"
            " last_seen_at, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (token_id, PAIR, PAIR, T0, T0, T0, T0),
        )
        pair_id = int(c.execute("SELECT id FROM printer_pairs WHERE pair_address=?", (PAIR,)).fetchone()["id"])
        c.execute(
            "INSERT INTO printer_memory_factory_runs (run_id, run_status, window_kind, db_mode,"
            " config_hash, config_json, started_at, created_at, updated_at)"
            " VALUES (?, 'RUNNING', 'WINDOW_15M', 'PROOF_ONLY', 'h', '{}', ?, ?, ?)",
            (RUN_ID, T0, T0, T0),
        )
        c.execute(
            "INSERT INTO printer_memory_factory_run_steps (run_id, step_key, step_kind, step_status,"
            " token_id, pair_id, token_mint, pair_address, tracking_lane, scheduled_for, created_at, updated_at)"
            " VALUES (?, 't1_snapshot_01', 'SNAPSHOT', 'RUNNING', ?, ?, ?, ?, 'TRACK_FAST', ?, ?, ?)",
            (RUN_ID, token_id, pair_id, MINT, PAIR, T0, T0, T0),
        )
        c.commit()
        self.token_id = token_id
        self.pair_id = pair_id

    def _step(self) -> sqlite3.Row:
        return self.conn.execute(
            "SELECT * FROM printer_memory_factory_run_steps WHERE run_id=? AND step_key='t1_snapshot_01'",
            (RUN_ID,),
        ).fetchone()

    def _primary_factory(self, payload):
        def factory(*, token_mint, timeout_seconds):
            from printer_v1.sources.dexscreener import fixture_success_transport
            return build_dexscreener_adapter(enabled=True, fixture_transport=fixture_success_transport(payload))
        return factory

    def _fallback_factory(self, payload=None, *, raise_if_called=False):
        def factory(*, pair_address, token_mint, timeout_seconds):
            from printer_v1.sources.geckoterminal import fixture_success_transport
            if raise_if_called:
                raise AssertionError("fallback adapter must not be built on primary success")
            return build_geckoterminal_adapter(
                enabled=True, fixture_transport=fixture_success_transport(payload),
            )
        return factory

    def _counts(self):
        c = self.conn
        return {
            "requests": int(c.execute("SELECT COUNT(*) FROM printer_source_requests").fetchone()[0]),
            "responses": int(c.execute("SELECT COUNT(*) FROM printer_source_responses").fetchone()[0]),
            "failures": int(c.execute("SELECT COUNT(*) FROM printer_source_failures").fetchone()[0]),
            "snapshots": int(c.execute("SELECT COUNT(*) FROM printer_token_snapshots").fetchone()[0]),
        }

    # --- eligibility allowlist ---------------------------------------------

    def test_eligible_allowlist_is_exact(self):
        self.assertEqual(
            ELIGIBLE_TRANSIENT_PRIMARY_FAILURE_TYPES,
            frozenset({
                "dexscreener_transport_failure",
                "dexscreener_http_server_error",
                "dexscreener_rate_limited_fixture",
            }),
        )
        self.assertFalse(is_eligible_transient_primary_failure(None))

    # --- 1. primary success => no fallback ---------------------------------

    def test_primary_success_makes_no_fallback_call(self):
        result = _execute_snapshot(
            self.conn, self._step(),
            adapter_factory=self._primary_factory(_dex_success_payload()),
            timeout_seconds=5.0,
            fallback_adapter_factory=self._fallback_factory(raise_if_called=True),
        )
        self.conn.commit()
        self.assertTrue(result["ok"])
        self.assertFalse(result["fallback_attempted"])
        self.assertEqual(result["snapshot_source_name"], "dexscreener")
        counts = self._counts()
        self.assertEqual(counts["snapshots"], 1)
        self.assertEqual(counts["requests"], 1)  # only the primary
        gt = self.conn.execute(
            "SELECT COUNT(*) FROM printer_source_requests WHERE source_name='geckoterminal'"
        ).fetchone()[0]
        self.assertEqual(int(gt), 0)

    # --- 2/3/7. eligible failure + valid fallback => exactly one snapshot ---

    def test_eligible_failure_valid_fallback_creates_one_geckoterminal_snapshot(self):
        for failure_type in sorted(ELIGIBLE_TRANSIENT_PRIMARY_FAILURE_TYPES):
            with self.subTest(failure_type=failure_type):
                self.tearDown()
                self.setUp()
                result = _execute_snapshot(
                    self.conn, self._step(),
                    adapter_factory=self._primary_factory(_dex_failure_payload(failure_type)),
                    timeout_seconds=5.0,
                    fallback_adapter_factory=self._fallback_factory(_gt_payload()),
                )
                self.conn.commit()
                self.assertTrue(result["ok"], result.get("blocked_reason"))
                self.assertTrue(result["fallback_attempted"])
                self.assertTrue(result["fallback_ok"])
                self.assertEqual(result["snapshot_source_name"], "geckoterminal")
                # exactly one snapshot, attributed to geckoterminal
                counts = self._counts()
                self.assertEqual(counts["snapshots"], 1)
                snap = self.conn.execute(
                    "SELECT normalized_snapshot_payload_json FROM printer_token_snapshots"
                ).fetchone()[0]
                self.assertIn('"source_name": "geckoterminal"', snap)
                # both attempts visible: primary failure preserved + gt response
                self.assertEqual(counts["failures"], 1)  # the preserved primary failure
                self.assertEqual(counts["responses"], 1)  # the gt fallback response
                self.assertEqual(counts["requests"], 2)   # primary + fallback
                self.assertIsNotNone(result["primary"]["source_failure_id"])
                self.assertEqual(result["primary"]["source_name"], "dexscreener")
                self.assertEqual(result["fallback"]["source_name"], "geckoterminal")
                # both attempts budgeted against this run
                self.assertEqual(_run_request_count(self.conn, RUN_ID), 2)

    # --- 5. non-transient primary failure => no fallback -------------------

    def test_non_transient_primary_failure_does_not_fallback(self):
        for failure_type in ("dexscreener_malformed_payload", "dexscreener_http_client_error",
                             "dexscreener_fixture_failure"):
            with self.subTest(failure_type=failure_type):
                self.tearDown()
                self.setUp()
                result = _execute_snapshot(
                    self.conn, self._step(),
                    adapter_factory=self._primary_factory(_dex_failure_payload(failure_type)),
                    timeout_seconds=5.0,
                    fallback_adapter_factory=self._fallback_factory(_gt_payload()),
                )
                self.conn.commit()
                self.assertFalse(result["ok"])
                self.assertFalse(result["fallback_attempted"])
                self.assertEqual(result["blocked_reason"], failure_type)
                counts = self._counts()
                self.assertEqual(counts["snapshots"], 0)
                self.assertEqual(counts["requests"], 1)  # only primary, no gt call

    # --- 6. fallback failure => fail closed on preserved primary cause -----

    def test_fallback_failure_fails_closed_and_preserves_primary(self):
        result = _execute_snapshot(
            self.conn, self._step(),
            adapter_factory=self._primary_factory(_dex_failure_payload("dexscreener_transport_failure")),
            timeout_seconds=5.0,
            fallback_adapter_factory=self._fallback_factory(_gt_failure_payload()),
        )
        self.conn.commit()
        self.assertFalse(result["ok"])
        self.assertTrue(result["fallback_attempted"])
        self.assertFalse(result["fallback_ok"])
        self.assertEqual(result["blocked_reason"], "dexscreener_transport_failure")
        self.assertIsNotNone(result["primary_failure_preserved"])
        counts = self._counts()
        self.assertEqual(counts["snapshots"], 0)
        self.assertEqual(counts["requests"], 2)   # both attempts visible
        self.assertEqual(counts["failures"], 2)   # primary + fallback failures

    # --- 4. invalid fallback responses remain blocked ---------------------

    def _assert_fallback_blocked(self, gt_payload):
        result = _execute_snapshot(
            self.conn, self._step(),
            adapter_factory=self._primary_factory(_dex_failure_payload("dexscreener_transport_failure")),
            timeout_seconds=5.0,
            fallback_adapter_factory=self._fallback_factory(gt_payload),
        )
        self.conn.commit()
        self.assertFalse(result["ok"])
        self.assertTrue(result["fallback_attempted"])
        self.assertEqual(self._counts()["snapshots"], 0)
        # primary failure preserved as the terminal cause
        self.assertEqual(result["blocked_reason"], "dexscreener_transport_failure")

    def test_fallback_pair_mismatch_blocked(self):
        self._assert_fallback_blocked(_gt_payload(pool_address="WrongPairAddress1111111111111111111111111111"))

    def test_fallback_token_mismatch_blocked(self):
        self._assert_fallback_blocked(_gt_payload(token_mint="WrongMint11111111111111111111111111111111111"))

    def test_fallback_stale_blocked(self):
        self._assert_fallback_blocked(_gt_payload(stale=True))

    def test_fallback_missing_mandatory_field_blocked(self):
        attrs = _gt_pool_attributes()
        attrs.pop("reserve_in_usd")  # drop mandatory liquidity
        self._assert_fallback_blocked(_gt_payload(attributes=attrs))

    def test_fallback_missing_fdv_and_market_cap_blocked(self):
        attrs = _gt_pool_attributes()
        attrs.pop("fdv_usd")
        attrs.pop("market_cap_usd")
        self._assert_fallback_blocked(_gt_payload(attributes=attrs))

    def test_fallback_non_solana_network_blocked(self):
        self._assert_fallback_blocked(_gt_payload(network="ethereum"))

    def test_fallback_malformed_missing_data_blocked(self):
        result = _execute_snapshot(
            self.conn, self._step(),
            adapter_factory=self._primary_factory(_dex_failure_payload("dexscreener_transport_failure")),
            timeout_seconds=5.0,
            fallback_adapter_factory=self._fallback_factory({
                "_requested_pool_address": PAIR, "_requested_token_mint": MINT,
                "_requested_network": "solana",
            }),
        )
        self.conn.commit()
        self.assertFalse(result["ok"])
        self.assertEqual(self._counts()["snapshots"], 0)


if __name__ == "__main__":
    unittest.main()
