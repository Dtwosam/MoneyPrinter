import pathlib
import json
import sqlite3
import sys
import tempfile
import unittest
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone


PROJECT_ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from printer_v1.chain_heat.recorder import enqueue_chain_heat_refresh_job, record_chain_heat_snapshot
from printer_v1.chart_volatility.recorder import enqueue_chart_volatility_refresh_job
from printer_v1.context_evidence import build_window_15m_context_evidence
from printer_v1.db import apply_migrations
from printer_v1.liquidity_exit.recorder import enqueue_liquidity_exit_refresh_job
from printer_v1.market_regime.recorder import enqueue_market_regime_refresh_job, record_market_regime_snapshot
from printer_v1.paper_quote.evidence import insert_paper_quote_evidence
from printer_v1.safety.evidence import insert_solana_safety_evidence
from printer_v1.safety.recorder import enqueue_safety_rug_refresh_job
from printer_v1.snapshots.recorder import record_token_snapshot
from printer_v1.trading_flow.recorder import enqueue_trading_flow_refresh_job


class SharedWindow15mContextEvidenceTest(unittest.TestCase):
    def setUp(self):
        self.tempdir = tempfile.TemporaryDirectory()
        self.db_path = pathlib.Path(self.tempdir.name) / "shared-context.sqlite3"
        apply_migrations(self.db_path)
        self.start = datetime(2026, 7, 13, 12, 0, tzinfo=timezone.utc)
        self.end = self.start + timedelta(minutes=15)
        with self.connect() as connection:
            self.token_id = int(
                connection.execute(
                    "INSERT INTO printer_tokens (token_mint, chain) VALUES ('shared-mint', 'solana')"
                ).lastrowid
            )
            self.pair_id = int(
                connection.execute(
                    """
                    INSERT INTO printer_pairs (token_id, pair_address, dex, base_token_mint)
                    VALUES (?, 'shared-pair', 'test-dex', 'shared-mint')
                    """,
                    (self.token_id,),
                ).lastrowid
            )

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

    def source_trace(self, source_name, request_kind, captured_at, payload=None):
        with self.connect() as connection:
            request_id = int(
                connection.execute(
                    """
                    INSERT INTO printer_source_requests (
                        source_name, request_kind, requested_at, source_status, data_quality_label
                    ) VALUES (?, ?, ?, 'COMPLETE', 'CLEAN_DATA')
                    """,
                    (source_name, request_kind, captured_at.isoformat()),
                ).lastrowid
            )
            response_id = int(
                connection.execute(
                    """
                    INSERT INTO printer_source_responses (
                        source_request_id, source_name, received_at, source_status,
                        data_quality_label, normalized_payload_json
                    ) VALUES (?, ?, ?, 'COMPLETE', 'CLEAN_DATA', ?)
                    """,
                    (request_id, source_name, captured_at.isoformat(), "{}"),
                ).lastrowid
            )
            connection.commit()
        return request_id, response_id

    def add_snapshots(self, *, source_trace=True, dirty_index=None):
        request_id, response_id = self.source_trace(
            "dexscreener", "pair_market_snapshot", self.start
        )
        ids = []
        for index in range(6):
            captured_at = self.start + timedelta(minutes=index * 3)
            payload = {
                "token_id": self.token_id,
                "pair_id": self.pair_id,
                "token_mint": "shared-mint",
                "pair_address": "shared-pair",
                "captured_at": captured_at.isoformat(),
                "tracking_lane": "TRACK_FAST",
                "snapshot_mode": "NORMAL_MODE",
                "price_usd": 1.0 + (index * 0.05),
                "liquidity_usd": 100_000 + (index * 1_000),
                "volume_5m": 30_000 + (index * 1_000),
                "volume_15m": 80_000 + (index * 2_000),
                "volume_1h": 200_000,
                "volume_24h": 1_000_000,
                "txns_5m": 60,
                "txns_15m": 150,
                "txns_1h": 300,
                "txns_24h": 2_000,
                "buys_5m": 40,
                "sells_5m": 20,
                "unique_wallets_5m": 25,
                "source_status": "COMPLETE",
                "data_quality_label": "DIRTY_DATA" if dirty_index == index else "CLEAN_DATA",
            }
            if source_trace:
                payload.update(
                    {
                        "source_name": "dexscreener",
                        "source_request_id": request_id,
                        "source_response_id": response_id,
                    }
                )
            _created, snapshot_id = record_token_snapshot(
                self.db_path, payload, captured_at
            )
            ids.append(snapshot_id)
        return ids

    def add_broad_context(self, captured_at=None):
        when = captured_at or self.end
        market_request, market_response = self.source_trace(
            "coingecko", "broad_market_context", when
        )
        market_payload = {
            "captured_at": when.isoformat(),
            "assets": {
                "bitcoin": {"price_usd": 65_000, "change_24h": 2.5},
                "ethereum": {"price_usd": 3_500, "change_24h": 1.5},
                "solana": {"price_usd": 150, "change_24h": 4.0, "volume_24h": 2_000_000_000},
            },
            "fear_greed": {"value": 65, "label": "Greed"},
            "source_request_id": market_request,
            "source_response_id": market_response,
            "source_status": "COMPLETE",
            "data_quality_label": "CLEAN_DATA",
        }
        record_market_regime_snapshot(self.db_path, market_payload, when)

        chain_request, chain_response = self.source_trace(
            "defillama", "chain_liquidity_context", when
        )
        chain_payload = {
            "captured_at": when.isoformat(),
            "assets": {
                "solana": {
                    "price_usd": 150,
                    "change_24h": 4.0,
                    "volume_24h": 2_000_000_000,
                }
            },
            "network_context": {
                "active_addresses": 1_400_000,
                "tx_count_24h": 30_000_000,
                "priority_fee_context": "normal",
                "congestion_context": "normal",
                "new_token_count": 5_000,
            },
            "liquidity_context": {
                "tvl_usd": 4_800_000_000,
                "dex_volume_24h": 1_500_000_000,
                "stablecoin_supply": 3_500_000_000,
            },
            "meme_context": {
                "hot_pair_count": 48,
                "meme_volume_24h": 60_000_000,
                "meme_liquidity_usd": 12_000_000,
                "meme_new_pair_count": 90,
                "meme_graduation_count": 15,
                "meme_failed_pair_count": 4,
            },
            "source_request_id": chain_request,
            "source_response_id": chain_response,
            "source_status": "COMPLETE",
            "data_quality_label": "CLEAN_DATA",
        }
        record_chain_heat_snapshot(self.db_path, chain_payload, when)

    def add_safety_and_quotes(self, snapshot_id, *, pair_id=None, captured_at=None):
        when = captured_at or self.end
        safety_request, safety_response = self.source_trace(
            "goplus", "token_safety_context", when
        )
        safety = {
            "token_id": self.token_id,
            "pair_id": self.pair_id if pair_id is None else pair_id,
            "snapshot_id": snapshot_id,
            "memory_window_id": None,
            "evidence_window_id": None,
            "safety_evidence_role": "TOKEN_SAFETY_CONTEXT",
            "source_name": "goplus",
            "source_status": "COMPLETE",
            "data_quality_label": "CLEAN_DATA",
            "target_status": "TARGET_MATCH",
            "evidence_captured_at": when.isoformat(),
            "freshness_label": "SAFETY_EVIDENCE_FRESH",
            "mint_authority_status": "MINT_AUTHORITY_RENOUNCED",
            "freeze_authority_status": "FREEZE_AUTHORITY_DISABLED",
            "metadata_mutability_status": "METADATA_IMMUTABLE",
            "supply_sanity_label": "SUPPLY_SANITY_OK",
            "holder_concentration_label": "HOLDER_CONCENTRATION_HEALTHY",
            "liquidity_lock_or_burn_label": "LIQUIDITY_LOCK_OR_BURN_CONFIRMED",
            "known_risk_flag_label": "NO_KNOWN_RISK_FLAGS",
            "token_program_label": "SPL_TOKEN_OR_TOKEN_2022_VERIFIED",
            "safety_context_label": "SAFETY_CLEAN",
            "source_request_id": safety_request,
            "source_response_id": safety_response,
            "source_failure_id": None,
            "paper_only_context": True,
        }
        safety_result = insert_solana_safety_evidence(
            self.db_path,
            safety,
            scheduler_boundary_label="SCHEDULER_BOUNDARY_PRESENT",
            operator_approval_label="OPERATOR_APPROVED_MANUAL_PROOF",
        )
        self.assertTrue(safety_result.inserted)

        for direction in ("ENTRY", "EXIT"):
            request_id, response_id = self.source_trace(
                "jupiter", "paper_quote_realism", when
            )
            quote = {
                "token_id": self.token_id,
                "pair_id": self.pair_id if pair_id is None else pair_id,
                "snapshot_id": snapshot_id,
                "memory_window_id": None,
                "evidence_window_id": None,
                "quote_evidence_role": f"{direction}_QUOTE_CONTEXT",
                "quote_direction": direction,
                "quote_purpose": "PAPER_REALISM_ONLY",
                "source_name": "jupiter",
                "source_status": "COMPLETE",
                "data_quality_label": "CLEAN_DATA",
                "target_status": "TARGET_MATCH",
                "evidence_captured_at": when.isoformat(),
                "freshness_label": "QUOTE_FRESH",
                "quote_context_label": "QUOTE_ROUTE_AVAILABLE",
                "entry_realism_label": "ENTRY_REALISTIC" if direction == "ENTRY" else "ENTRY_UNKNOWN",
                "exit_realism_label": "EXIT_REALISTIC" if direction == "EXIT" else "EXIT_UNKNOWN",
                "route_available_label": "ROUTE_AVAILABLE",
                "slippage_context_label": "SLIPPAGE_ACCEPTABLE",
                "price_impact_context_label": "PRICE_IMPACT_ACCEPTABLE",
                "liquidity_context_label": "LIQUIDITY_CONTEXT_ACCEPTABLE",
                "quote_failure_label": None,
                "source_request_id": request_id,
                "source_response_id": response_id,
                "source_failure_id": None,
                "paper_only_context": True,
            }
            result = insert_paper_quote_evidence(
                self.db_path,
                quote,
                scheduler_boundary_label="SCHEDULER_BOUNDARY_PRESENT",
                operator_approval_label="OPERATOR_APPROVED_MANUAL_PROOF",
            )
            self.assertTrue(result.inserted)

    def report(self, snapshot_ids):
        with self.connect() as connection:
            return build_window_15m_context_evidence(
                connection,
                token_id=self.token_id,
                pair_id=self.pair_id,
                snapshot_start_id=snapshot_ids[0],
                snapshot_end_id=snapshot_ids[-1],
                window_start_at=self.start,
                window_end_at=self.end,
            )

    def test_complete_exact_bundle_resolves_all_six_foundations_without_writes(self):
        snapshot_ids = self.add_snapshots()
        self.add_broad_context()
        self.add_safety_and_quotes(snapshot_ids[-1])
        with self.connect() as connection:
            before = connection.total_changes
            first = build_window_15m_context_evidence(
                connection,
                token_id=self.token_id,
                pair_id=self.pair_id,
                snapshot_start_id=snapshot_ids[0],
                snapshot_end_id=snapshot_ids[-1],
                window_start_at=self.start,
                window_end_at=self.end,
            )
            second = build_window_15m_context_evidence(
                connection,
                token_id=self.token_id,
                pair_id=self.pair_id,
                snapshot_start_id=snapshot_ids[0],
                snapshot_end_id=snapshot_ids[-1],
                window_start_at=self.start,
                window_end_at=self.end,
            )
            self.assertEqual(connection.total_changes, before)
        self.assertEqual(first, second)
        self.assertTrue(first["clean_memory_context_ready"])
        self.assertEqual(first["blockers"], [])
        self.assertTrue(all(section["can_support_clean_memory"] for section in first["sections"].values()))
        self.assertEqual(first["sections"]["safety_rug"]["labels"]["safety_status_label"], "SAFETY_CLEAN")
        self.assertEqual(first["sections"]["liquidity_exit_realism"]["labels"]["entry_realism_label"], "ENTRY_REALISTIC")
        self.assertNotEqual(first["sections"]["trading_flow"]["labels"]["flow_direction_label"], "FLOW_UNKNOWN")
        self.assertNotEqual(first["sections"]["chart_volatility"]["labels"]["volatility_label"], "VOLATILITY_UNKNOWN")
        self.assertFalse(any(first["downstream_unlocks"].values()))

    def test_normalized_snapshot_trace_shape_used_by_e2m_is_accepted(self):
        snapshot_ids = self.add_snapshots()
        with self.connect() as connection:
            trace = json.loads(connection.execute(
                "SELECT raw_snapshot_payload_json FROM printer_token_snapshots WHERE id=?",
                (snapshot_ids[0],),
            ).fetchone()[0])
            normalized_trace = json.dumps({
                "source_name": trace["source_name"],
                "source_request_id": trace["source_request_id"],
                "source_response_id": trace["source_response_id"],
            }, sort_keys=True)
            connection.execute(
                "UPDATE printer_token_snapshots SET raw_snapshot_payload_json='{}', normalized_snapshot_payload_json=?",
                (normalized_trace,),
            )
            connection.commit()
        self.add_broad_context()
        self.add_safety_and_quotes(snapshot_ids[-1])
        result = self.report(snapshot_ids)
        self.assertTrue(all(trace["source_trace_clean"] for trace in result["snapshot_source_traces"]))
        self.assertNotIn("SNAPSHOT_SOURCE_TRACE_MISSING_OR_INVALID", result["blockers"])

    def test_future_context_and_evidence_never_attach(self):
        snapshot_ids = self.add_snapshots()
        future = self.end + timedelta(seconds=1)
        self.add_broad_context(future)
        self.add_safety_and_quotes(snapshot_ids[-1], captured_at=future)
        result = self.report(snapshot_ids)
        self.assertFalse(result["clean_memory_context_ready"])
        self.assertEqual(result["sections"]["market_regime"]["status"], "UNKNOWN_MARKET_REGIME")
        self.assertEqual(result["sections"]["solana_chain_heat"]["status"], "SOLANA_UNKNOWN")
        self.assertEqual(result["sections"]["safety_rug"]["status"], "UNKNOWN_SAFETY")
        # V2-9.4.6: evidence past the approved closing cutoff now reports the
        # specific late blocker instead of the generic "no evidence" name, which
        # was misleading -- the evidence exists, it is just too late to attach.
        self.assertIn("CLOSING_EVIDENCE_AFTER_APPROVED_CUTOFF", result["blockers"])
        self.assertIn(
            "CLOSING_EVIDENCE_AFTER_APPROVED_CUTOFF",
            result["sections"]["liquidity_exit_realism"]["blockers"],
        )

    def test_mismatched_target_and_dirty_snapshot_fail_closed(self):
        snapshot_ids = self.add_snapshots(dirty_index=2)
        self.add_broad_context()
        with self.connect() as connection:
            other_pair = int(
                connection.execute(
                    """
                    INSERT INTO printer_pairs (token_id, pair_address, dex, base_token_mint)
                    VALUES (?, 'other-pair', 'test-dex', 'shared-mint')
                    """,
                    (self.token_id,),
                ).lastrowid
            )
            connection.commit()
        self.add_safety_and_quotes(snapshot_ids[-1], pair_id=other_pair)
        result = self.report(snapshot_ids)
        self.assertFalse(result["clean_memory_context_ready"])
        self.assertIn("SNAPSHOT_DATA_NOT_CLEAN", result["sections"]["trading_flow"]["blockers"])
        self.assertEqual(result["sections"]["safety_rug"]["status"], "UNKNOWN_SAFETY")
        # V2-9.4.6: the quote is bound to another pair, so no row exists for the
        # exact closing snapshot. The specific absent-for-exact-snapshot blocker
        # replaces the generic name; the window still fails closed.
        self.assertIn("CLOSING_EXIT_QUOTE_ABSENT_FOR_EXACT_SNAPSHOT", result["blockers"])

    def test_missing_governed_snapshot_trace_blocks_flow_and_chart(self):
        snapshot_ids = self.add_snapshots(source_trace=False)
        self.add_broad_context()
        self.add_safety_and_quotes(snapshot_ids[-1])
        result = self.report(snapshot_ids)
        self.assertFalse(result["sections"]["trading_flow"]["can_support_clean_memory"])
        self.assertFalse(result["sections"]["chart_volatility"]["can_support_clean_memory"])
        self.assertIn("SNAPSHOT_SOURCE_TRACE_MISSING_OR_INVALID", result["blockers"])

    def test_stale_safety_evidence_cannot_use_15m_policy_to_bypass_freshness(self):
        snapshot_ids = self.add_snapshots()
        self.add_broad_context()
        self.add_safety_and_quotes(snapshot_ids[-1])
        with self.connect() as connection:
            connection.execute(
                "UPDATE printer_solana_safety_evidence SET freshness_label = 'SAFETY_EVIDENCE_STALE'"
            )
        result = self.report(snapshot_ids)
        self.assertFalse(result["sections"]["safety_rug"]["can_support_clean_memory"])
        self.assertEqual(result["sections"]["safety_rug"]["status"], "UNKNOWN_SAFETY")
        self.assertIn("NO_VALID_EXACT_TARGET_SAFETY_EVIDENCE", result["blockers"])

    def test_all_timed_foundations_enqueue_only_pending_central_scheduler_jobs(self):
        calls = (
            lambda: enqueue_market_regime_refresh_job(self.db_path, self.end, "shared_test"),
            lambda: enqueue_chain_heat_refresh_job(self.db_path, self.end, "shared_test"),
            lambda: enqueue_safety_rug_refresh_job(self.db_path, self.token_id, self.pair_id, self.end, "shared_test"),
            lambda: enqueue_liquidity_exit_refresh_job(self.db_path, self.token_id, self.pair_id, self.end, "shared_test"),
            lambda: enqueue_trading_flow_refresh_job(self.db_path, self.token_id, self.pair_id, self.end, "shared_test"),
            lambda: enqueue_chart_volatility_refresh_job(self.db_path, self.token_id, self.pair_id, self.end, "shared_test"),
        )
        job_ids = [call()[1] for call in calls]
        self.assertTrue(all(job_id is not None for job_id in job_ids))
        with self.connect() as connection:
            statuses = {
                row[0]
                for row in connection.execute(
                    "SELECT status FROM printer_scheduler_jobs"
                ).fetchall()
            }
            running = connection.execute(
                "SELECT COUNT(*) FROM printer_scheduler_jobs WHERE status = 'RUNNING'"
            ).fetchone()[0]
        self.assertEqual(statuses, {"PENDING"})
        self.assertEqual(running, 0)

    def test_short_or_reversed_window_is_rejected(self):
        snapshot_ids = self.add_snapshots()
        with self.connect() as connection:
            with self.assertRaisesRegex(ValueError, "at least 900 seconds"):
                build_window_15m_context_evidence(
                    connection,
                    token_id=self.token_id,
                    pair_id=self.pair_id,
                    snapshot_start_id=snapshot_ids[0],
                    snapshot_end_id=snapshot_ids[-1],
                    window_start_at=self.start,
                    window_end_at=self.end - timedelta(seconds=1),
                )


if __name__ == "__main__":
    unittest.main()
