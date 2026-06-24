"""Mini-Sprint B: market regime NEUTRAL fallback and safe evidence reuse for context revisions."""

import argparse
import json
import pathlib
import sqlite3
import sys
import tempfile
import unittest
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone

PROJECT_ROOT = pathlib.Path(__file__).resolve().parents[1]
SRC_PATH = PROJECT_ROOT / "src"
sys.path.insert(0, str(SRC_PATH))

from printer_v1.contracts.enums import DataQualityLabel, SourceStatus
from printer_v1.db import apply_migrations
from printer_v1.market_regime.classifier import classify_market_regime
from printer_v1.market_regime.recorder import record_market_regime_snapshot
from printer_v1.operator_cli.commands import (
    build_collect_context_once_payload,
    build_collect_token_snapshots_once_payload,
    build_manual_intake_token_pair_payload,
    build_memory_window_once_payload,
)
from printer_v1.paper_quote.evidence import insert_paper_quote_evidence
from printer_v1.safety.evidence import insert_solana_safety_evidence


def count_rows(connection, table):
    return int(connection.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0])


# ---------------------------------------------------------------------------
# Class 1: Scope A — market regime NEUTRAL fallback
# ---------------------------------------------------------------------------

class PostRcMarketRegimeNeutralFallbackTests(unittest.TestCase):
    """classify_market_regime must return NEUTRAL (not UNKNOWN) when BTC/SOL
    data is present and clean but values do not reach any named threshold."""

    def _payload(self, btc_24h, sol_24h, fear_greed_value=None):
        payload = {
            "btc_change_24h": btc_24h,
            "sol_change_24h": sol_24h,
            "source_status": "COMPLETE",
            "data_quality_label": "CLEAN_DATA",
        }
        if fear_greed_value is not None:
            payload["fear_greed_value"] = fear_greed_value
        return payload

    def test_mild_btc_sol_movement_classifies_as_neutral_not_unknown(self):
        result = classify_market_regime(self._payload(btc_24h=1.0, sol_24h=2.5))
        self.assertEqual(result.value, "NEUTRAL")

    def test_slightly_negative_btc_sol_outside_choppy_band_classifies_as_neutral(self):
        # btc=-1.0, sol=-2.5: abs(sol) > 2.0 → not CHOPPY → falls to NEUTRAL
        result = classify_market_regime(self._payload(btc_24h=-1.0, sol_24h=-2.5))
        self.assertEqual(result.value, "NEUTRAL")

    def test_mixed_moderate_btc_sol_without_fear_greed_classifies_as_neutral(self):
        result = classify_market_regime(self._payload(btc_24h=1.8, sol_24h=2.8))
        self.assertEqual(result.value, "NEUTRAL")

    def test_missing_btc_and_sol_with_no_fear_greed_classifies_as_unknown(self):
        result = classify_market_regime({
            "btc_change_24h": None,
            "sol_change_24h": None,
            "fear_greed_value": None,
            "source_status": "COMPLETE",
            "data_quality_label": "CLEAN_DATA",
        })
        self.assertEqual(result.value, "UNKNOWN")

    def test_missing_btc_and_sol_even_with_fear_greed_returns_fear_label_not_neutral(self):
        result = classify_market_regime({
            "btc_change_24h": None,
            "sol_change_24h": None,
            "fear_greed_value": 66,
            "source_status": "COMPLETE",
            "data_quality_label": "CLEAN_DATA",
        })
        self.assertEqual(result.value, "GREED")

    def test_risk_off_still_classifies_correctly(self):
        result = classify_market_regime(self._payload(btc_24h=-4.0, sol_24h=-5.0))
        self.assertEqual(result.value, "RISK_OFF")

    def test_risk_on_still_classifies_correctly(self):
        result = classify_market_regime(self._payload(btc_24h=3.0, sol_24h=5.0))
        self.assertEqual(result.value, "RISK_ON")

    def test_choppy_still_classifies_correctly(self):
        result = classify_market_regime(self._payload(btc_24h=0.5, sol_24h=1.0))
        self.assertEqual(result.value, "CHOPPY")

    def test_volatile_still_classifies_correctly(self):
        result = classify_market_regime(self._payload(btc_24h=6.0, sol_24h=-5.0))
        self.assertEqual(result.value, "VOLATILE")

    def test_neutral_with_mild_btc_sol_stored_correctly_in_db(self):
        with tempfile.TemporaryDirectory() as tmp:
            db_path = pathlib.Path(tmp) / "market-neutral.sqlite3"
            apply_migrations(db_path)
            now = datetime(2026, 6, 24, 12, 0, tzinfo=timezone.utc)
            created, row_id = record_market_regime_snapshot(
                db_path,
                {
                    "captured_at": now.isoformat(),
                    "assets": {
                        "bitcoin": {
                            "market_data": {
                                "current_price": {"usd": 64000},
                                "price_change_percentage_24h": 1.0,
                                "price_change_percentage_7d": 3.0,
                            },
                            "price_change_percentage_1h": 0.2,
                        },
                        "solana": {
                            "market_data": {
                                "current_price": {"usd": 150},
                                "price_change_percentage_24h": 2.5,
                                "price_change_percentage_7d": 5.0,
                                "total_volume": {"usd": 1_500_000_000},
                            },
                            "price_change_percentage_1h": 0.4,
                        },
                    },
                    "source_status": "COMPLETE",
                    "data_quality_label": "CLEAN_DATA",
                },
                now,
            )
            conn = sqlite3.connect(db_path)
            conn.row_factory = sqlite3.Row
            try:
                row = conn.execute(
                    "SELECT * FROM printer_market_regime_snapshots WHERE id = ?",
                    (row_id,),
                ).fetchone()
            finally:
                conn.close()
            self.assertTrue(created)
            self.assertEqual(row["market_regime_label"], "NEUTRAL")
            self.assertEqual(row["market_payload_quality_label"], "MARKET_CONTEXT_CLEAN")
            self.assertEqual(row["source_status"], "COMPLETE")

    def test_stale_or_dirty_context_still_records_unknown_regardless(self):
        with tempfile.TemporaryDirectory() as tmp:
            db_path = pathlib.Path(tmp) / "market-bad.sqlite3"
            apply_migrations(db_path)
            now = datetime(2026, 6, 24, 12, 0, tzinfo=timezone.utc)
            for overrides, expected_quality in (
                ({"source_status": "FAILED"}, {"MARKET_CONTEXT_DO_NOT_USE_FOR_MEMORY"}),
                ({"source_status": "CONFLICTING"}, {"MARKET_CONTEXT_CONFLICTING", "MARKET_CONTEXT_DO_NOT_USE_FOR_MEMORY"}),
                ({"data_quality_label": "DIRTY_DATA"}, {"MARKET_CONTEXT_DO_NOT_USE_FOR_MEMORY"}),
            ):
                payload = {
                    "captured_at": (now + timedelta(minutes=len(overrides))).isoformat(),
                    "assets": {
                        "bitcoin": {
                            "market_data": {
                                "current_price": {"usd": 64000},
                                "price_change_percentage_24h": 1.0,
                            },
                        },
                        "solana": {
                            "market_data": {
                                "current_price": {"usd": 150},
                                "price_change_percentage_24h": 2.5,
                            },
                        },
                    },
                    "source_status": "COMPLETE",
                    "data_quality_label": "CLEAN_DATA",
                }
                payload.update(overrides)
                record_market_regime_snapshot(db_path, payload, now)
                conn = sqlite3.connect(db_path)
                conn.row_factory = sqlite3.Row
                try:
                    row = conn.execute(
                        "SELECT * FROM printer_market_regime_snapshots ORDER BY id DESC LIMIT 1"
                    ).fetchone()
                finally:
                    conn.close()
                self.assertEqual(row["market_regime_label"], "UNKNOWN")
                self.assertIn(row["market_payload_quality_label"], expected_quality)


# ---------------------------------------------------------------------------
# Class 2: Scope B — evidence reuse across context revisions
# ---------------------------------------------------------------------------

class PostRcEvidenceReuseContextRevisionTests(unittest.TestCase):
    """Clean safety/quote evidence bound to an older memory_window_id must be
    reusable for a context-only revision that produces a new distinct window."""

    def setUp(self):
        self.tempdir = tempfile.TemporaryDirectory()
        self.db_path = pathlib.Path(self.tempdir.name) / "sprint-b-evidence-reuse.sqlite3"
        apply_migrations(self.db_path)
        self.base_time = datetime(2026, 6, 25, 12, 0, tzinfo=timezone.utc)

    def tearDown(self):
        self.tempdir.cleanup()

    @contextmanager
    def connect(self):
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
            conn.commit()
        finally:
            conn.close()

    def _args(self, **kw):
        defaults = {
            "db_path": str(self.db_path),
            "project_root": str(PROJECT_ROOT),
            "format": "json",
            "no_color": True,
            "operator_approved": True,
            "token_mint": "revision-mint",
            "token_id": None,
            "pair_address": "revision-pair",
            "pair_id": None,
            "snapshot_id": None,
            "snapshot_count": 1,
            "max_seconds": 5.0,
            "source_name": "dexscreener",
            "source_reference": "revision-ref",
            "chain": "solana",
            "memory_window": "15m",
        }
        defaults.update(kw)
        return argparse.Namespace(**defaults)

    def _transport(self, ctx):
        del ctx
        return {
            "pairs": [{
                "chainId": "solana",
                "pairAddress": "revision-pair",
                "baseToken": {"address": "revision-mint", "symbol": "REV", "name": "Revision Token"},
                "priceUsd": "0.00050",
                "liquidity": {"usd": 32000.0},
                "volume": {"m5": 14000.0, "h1": 80000.0, "h24": 310000.0},
                "txns": {"m5": {"buys": 40, "sells": 16}, "h1": {"buys": 180, "sells": 70}},
                "fdv": 500000.0,
                "marketCap": 455000.0,
                "priceChange": {"m5": 12.0, "h1": 22.0, "h24": 33.0},
            }]
        }

    def _seed_snapshots(self):
        build_manual_intake_token_pair_payload(self._args(
            pool_address=None, intake_reason="revision-test", source_request_id=None,
            token_symbol="REV", token_name="Revision Token", dex_id="raydium",
            intake_json=None,
        ))
        snapshot_ids = []
        for i in range(6):
            build_collect_token_snapshots_once_payload(
                self._args(snapshot_count=1, max_seconds=5.0, source_reference=f"rev-snap-{i}"),
                transport=self._transport,
            )
            with self.connect() as conn:
                row = conn.execute(
                    "SELECT id FROM printer_token_snapshots ORDER BY id DESC LIMIT 1"
                ).fetchone()
                snap_id = int(row["id"])
                captured_at = (self.base_time + timedelta(minutes=i * 3)).isoformat()
                conn.execute(
                    "UPDATE printer_token_snapshots SET captured_at = ? WHERE id = ?",
                    (captured_at, snap_id),
                )
                snapshot_ids.append(snap_id)
        return snapshot_ids

    def _force_all_context_known(self):
        with self.connect() as conn:
            conn.execute(
                """UPDATE printer_market_regime_snapshots SET
                    market_regime_label = 'RISK_ON',
                    market_transition_label = 'RISK_OFF_TO_RISK_ON',
                    market_payload_quality_label = 'MARKET_CONTEXT_CLEAN',
                    data_quality_label = 'CLEAN_DATA', source_status = 'COMPLETE'"""
            )
            conn.execute(
                """UPDATE printer_solana_chain_heat_snapshots SET
                    chain_heat_label = 'SOLANA_WARM', activity_label = 'ACTIVITY_ELEVATED',
                    liquidity_label = 'LIQUIDITY_STABLE', congestion_label = 'CONGESTION_LOW',
                    chain_heat_payload_quality_label = 'CHAIN_HEAT_CONTEXT_CLEAN',
                    data_quality_label = 'CLEAN_DATA', source_status = 'COMPLETE'"""
            )
            conn.execute(
                """UPDATE printer_safety_rug_snapshots SET
                    safety_status_label = 'SAFETY_CLEAN', rug_risk_label = 'RUG_RISK_LOW',
                    liquidity_safety_label = 'LIQUIDITY_SAFE',
                    authority_label = 'AUTHORITY_RENOUNCED_OR_SAFE',
                    distribution_label = 'DISTRIBUTION_HEALTHY',
                    safety_payload_quality_label = 'SAFETY_CONTEXT_CLEAN',
                    safety_gate_label = 'ALLOW_SAFETY_CONTEXT',
                    data_quality_label = 'CLEAN_DATA', source_status = 'COMPLETE'"""
            )
            conn.execute(
                """UPDATE printer_liquidity_exit_snapshots SET
                    entry_realism_label = 'ENTRY_REALISTIC', exit_realism_label = 'EXIT_REALISTIC',
                    slippage_label = 'SLIPPAGE_LOW', price_impact_label = 'PRICE_IMPACT_LOW',
                    route_label = 'ROUTE_AVAILABLE', quote_age_label = 'QUOTE_FRESH',
                    liquidity_drain_label = 'NO_LIQUIDITY_DRAIN',
                    liquidity_exit_payload_quality_label = 'LIQUIDITY_EXIT_CONTEXT_CLEAN',
                    realism_gate_label = 'REALISM_CONTEXT_ACCEPTABLE',
                    data_quality_label = 'CLEAN_DATA', source_status = 'COMPLETE'"""
            )
            conn.execute(
                """UPDATE printer_trading_flow_snapshots SET
                    flow_direction_label = 'FLOW_ACCUMULATION',
                    flow_pressure_label = 'PRESSURE_MODERATE_INFLOW',
                    imbalance_label = 'IMBALANCE_BUY_HEAVY',
                    volume_activity_label = 'VOLUME_NORMAL', tx_activity_label = 'TX_ACTIVITY_NORMAL',
                    wallet_participation_label = 'WALLETS_BROAD_PARTICIPATION',
                    trading_flow_payload_quality_label = 'TRADING_FLOW_CONTEXT_CLEAN',
                    flow_memory_gate_label = 'FLOW_CONTEXT_ACCEPTABLE',
                    data_quality_label = 'CLEAN_DATA', source_status = 'COMPLETE'"""
            )
            conn.execute(
                """UPDATE printer_chart_volatility_snapshots SET
                    trend_structure_label = 'TREND_UP', volatility_label = 'VOLATILITY_NORMAL',
                    range_behavior_label = 'RANGE_EXPANDING', momentum_label = 'MOMENTUM_STABLE',
                    drawdown_recovery_label = 'DRAWDOWN_NONE', candle_path_label = 'PATH_STEADY_CLIMB',
                    chart_payload_quality_label = 'CHART_CONTEXT_CLEAN',
                    chart_memory_gate_label = 'CHART_CONTEXT_ACCEPTABLE',
                    data_quality_label = 'CLEAN_DATA', source_status = 'COMPLETE'"""
            )
            conn.execute(
                """UPDATE printer_micro_events SET
                    micro_event_state_label = 'NO_MICRO_EVENT',
                    micro_event_move_label = 'MOVE_NO_CLEAR_EVENT',
                    micro_exit_realism_label = 'MICRO_EXIT_REALISTIC',
                    late_buy_trap_label = 'NO_LATE_BUY_TRAP',
                    held_to_15m_result_label = 'HELD_TO_15M_CONSOLIDATED',
                    micro_event_payload_quality_label = 'MICRO_EVENT_CONTEXT_CLEAN',
                    micro_event_memory_gate_label = 'MICRO_EVENT_SUPPORT_EVIDENCE',
                    data_quality_label = 'CLEAN_DATA', source_status = 'COMPLETE'"""
            )

    def _seed_source_trace(self, conn, request_id, response_id, source_name):
        conn.execute(
            """INSERT OR IGNORE INTO printer_source_requests
               (id, source_name, request_kind, requested_at, request_key,
                tracking_priority, source_status, data_quality_label)
               VALUES (?, ?, 'evidence_fixture', ?, ?, 1, 'COMPLETE', 'CLEAN_DATA')""",
            (request_id, source_name, self.base_time.isoformat(), source_name),
        )
        conn.execute(
            """INSERT OR IGNORE INTO printer_source_responses
               (id, source_request_id, source_name, received_at, status_code,
                source_status, data_quality_label, response_hash, normalized_payload_json)
               VALUES (?, ?, ?, ?, 200, 'COMPLETE', 'CLEAN_DATA', ?, '{}')""",
            (response_id, request_id, source_name, self.base_time.isoformat(), f"hash-{response_id}"),
        )

    def _insert_safety(self, snapshot_id, memory_window_id, **overrides):
        with self.connect() as conn:
            self._seed_source_trace(conn, 900, 901, "fixture_safety")
        evidence = {
            "token_id": 1, "pair_id": 1, "snapshot_id": snapshot_id,
            "memory_window_id": memory_window_id, "evidence_window_id": None,
            "safety_evidence_role": "TOKEN_SAFETY_CONTEXT", "source_name": "fixture_safety",
            "source_status": "COMPLETE", "data_quality_label": "CLEAN_DATA",
            "target_status": "TARGET_MATCH", "evidence_captured_at": self.base_time.isoformat(),
            "freshness_label": "SAFETY_EVIDENCE_FRESH",
            "mint_authority_status": "MINT_AUTHORITY_RENOUNCED",
            "freeze_authority_status": "FREEZE_AUTHORITY_DISABLED",
            "metadata_mutability_status": "METADATA_IMMUTABLE",
            "supply_sanity_label": "SUPPLY_SANITY_OK",
            "holder_concentration_label": "HOLDER_CONCENTRATION_HEALTHY",
            "liquidity_lock_or_burn_label": "LIQUIDITY_LOCK_OR_BURN_CONFIRMED",
            "known_risk_flag_label": "NO_KNOWN_RISK_FLAGS",
            "token_program_label": "SPL_TOKEN_OR_TOKEN_2022_VERIFIED",
            "safety_context_label": "SAFETY_CLEAR",
            "source_request_id": 900, "source_response_id": 901,
            "source_failure_id": None, "paper_only_context": True,
        }
        evidence.update(overrides)
        return insert_solana_safety_evidence(
            self.db_path, evidence,
            scheduler_boundary_label="SCHEDULER_BOUNDARY_PRESENT",
            operator_approval_label="OPERATOR_APPROVED_MANUAL_PROOF",
        )

    def _insert_quote(self, snapshot_id, direction, req_id, resp_id, memory_window_id, **overrides):
        src = f"fixture_{direction.lower()}_quote"
        with self.connect() as conn:
            self._seed_source_trace(conn, req_id, resp_id, src)
        evidence = {
            "token_id": 1, "pair_id": 1, "snapshot_id": snapshot_id,
            "memory_window_id": memory_window_id, "evidence_window_id": None,
            "quote_evidence_role": f"{direction}_QUOTE_CONTEXT",
            "quote_direction": direction, "quote_purpose": "PAPER_REALISM_ONLY",
            "source_name": src, "source_status": "COMPLETE", "data_quality_label": "CLEAN_DATA",
            "target_status": "TARGET_MATCH", "evidence_captured_at": self.base_time.isoformat(),
            "freshness_label": "QUOTE_FRESH", "quote_context_label": "QUOTE_ROUTE_AVAILABLE",
            "entry_realism_label": "ENTRY_REALISTIC" if direction == "ENTRY" else "ENTRY_UNKNOWN",
            "exit_realism_label": "EXIT_REALISTIC" if direction == "EXIT" else "EXIT_UNKNOWN",
            "route_available_label": "ROUTE_AVAILABLE",
            "slippage_context_label": "SLIPPAGE_ACCEPTABLE",
            "price_impact_context_label": "PRICE_IMPACT_ACCEPTABLE",
            "liquidity_context_label": "LIQUIDITY_CONTEXT_ACCEPTABLE",
            "quote_failure_label": None,
            "source_request_id": req_id, "source_response_id": resp_id,
            "source_failure_id": None, "paper_only_context": True,
        }
        evidence.update(overrides)
        return insert_paper_quote_evidence(
            self.db_path, evidence,
            scheduler_boundary_label="SCHEDULER_BOUNDARY_PRESENT",
            operator_approval_label="OPERATOR_APPROVED_MANUAL_PROOF",
        )

    def _insert_new_market_regime_row(self, snapshot_id):
        """Insert a second market regime row (different ID) to change context_row_ids."""
        now = self.base_time + timedelta(minutes=30)
        payload = {
            "captured_at": now.isoformat(),
            "snapshot_id": snapshot_id,
            "assets": {
                "bitcoin": {
                    "market_data": {
                        "current_price": {"usd": 64500},
                        "price_change_percentage_24h": 1.0,
                        "price_change_percentage_7d": 3.0,
                    },
                    "price_change_percentage_1h": 0.2,
                },
                "solana": {
                    "market_data": {
                        "current_price": {"usd": 151},
                        "price_change_percentage_24h": 2.5,
                        "price_change_percentage_7d": 5.0,
                        "total_volume": {"usd": 1_500_000_000},
                    },
                    "price_change_percentage_1h": 0.4,
                },
            },
            "source_status": "COMPLETE",
            "data_quality_label": "CLEAN_DATA",
        }
        _created, new_id = record_market_regime_snapshot(self.db_path, payload, now)
        return new_id

    def _assert_no_downstream_unlocks(self):
        with self.connect() as conn:
            for table in (
                "printer_memory_retrieval_queries",
                "printer_memory_retrieval_matches",
                "printer_paper_decisions",
                "printer_paper_positions",
                "printer_paper_trade_events",
                "printer_paper_trade_audits",
            ):
                self.assertEqual(count_rows(conn, table), 0, f"expected 0 rows in {table}")

    def test_evidence_from_prior_window_reused_for_new_distinct_context_revision(self):
        """Core scenario: evidence bound to mw_first is found for a new distinct window."""
        snapshot_ids = self._seed_snapshots()
        last_snapshot_id = snapshot_ids[-1]

        build_collect_context_once_payload(
            self._args(snapshot_id=last_snapshot_id, source_reference="initial-context")
        )
        self._force_all_context_known()

        # Build mw_first — AUDIT_ONLY because no safety/quote evidence
        mw_first_result = build_memory_window_once_payload(self._args(
            snapshot_id=last_snapshot_id,
            source_reference="first-audit-only-window",
        ))
        mw_first_id = int(mw_first_result["memory_result"]["memory_window_id"])
        self.assertEqual(mw_first_result["memory_result"]["memory_quality_label"], "AUDIT_ONLY_MEMORY")

        # Insert clean evidence bound to mw_first
        self._insert_safety(last_snapshot_id, memory_window_id=mw_first_id)
        self._insert_quote(last_snapshot_id, "ENTRY", 910, 911, memory_window_id=mw_first_id)
        self._insert_quote(last_snapshot_id, "EXIT", 920, 921, memory_window_id=mw_first_id)

        # Insert a new market regime row → changes market context_row_id
        # This triggers functional evidence search to fail for mw_first → new distinct window
        new_market_id = self._insert_new_market_regime_row(last_snapshot_id)
        self.assertIsNotNone(new_market_id)

        # Build a new distinct window (different source_reference + different market context_row_id)
        new_memory = build_memory_window_once_payload(self._args(
            snapshot_id=last_snapshot_id,
            source_reference="context-revision-new-market",
        ))
        result = new_memory["memory_result"]

        # With the fix: evidence from mw_first is found → applied → CLEAN_MEMORY
        self.assertNotEqual(result["memory_window_id"], mw_first_id,
                            "should create a new window, not return mw_first")
        self.assertEqual(result["memory_quality_label"], "CLEAN_MEMORY")
        self.assertTrue(result["retrieval_ready"])
        self.assertEqual(result["do_not_train"], 0)
        self.assertIsNotNone(result["applied_safety_evidence_row_id"])
        self.assertIsNotNone(result["applied_entry_quote_evidence_row_id"])
        self.assertIsNotNone(result["applied_exit_quote_evidence_row_id"])
        self.assertEqual(result["evidence_blockers"], [])
        self._assert_no_downstream_unlocks()

    def test_dirty_evidence_is_not_reused_across_windows(self):
        """Evidence with dirty data_quality_label must never be applied."""
        snapshot_ids = self._seed_snapshots()
        last_snapshot_id = snapshot_ids[-1]
        build_collect_context_once_payload(
            self._args(snapshot_id=last_snapshot_id, source_reference="dirty-evidence-ctx")
        )
        self._force_all_context_known()

        mw_result = build_memory_window_once_payload(self._args(
            snapshot_id=last_snapshot_id,
            source_reference="dirty-evidence-first-window",
        ))
        mw_id = int(mw_result["memory_result"]["memory_window_id"])

        # Insert dirty evidence (data_quality_label = DIRTY_DATA)
        self._insert_safety(
            last_snapshot_id,
            memory_window_id=mw_id,
            data_quality_label="DIRTY_DATA",
            source_status="COMPLETE",
        )

        # Even without a new-distinct trigger, directly test: mw_id lookup finds dirty row → rejected
        new_memory = build_memory_window_once_payload(self._args(
            snapshot_id=last_snapshot_id,
            source_reference="dirty-evidence-second-window",
        ))
        result = new_memory["memory_result"]

        # Safety evidence was dirty → blocker still present → AUDIT_ONLY
        self.assertIn(result["memory_quality_label"], {"AUDIT_ONLY_MEMORY", "DIRTY_MEMORY"})
        self.assertFalse(result.get("retrieval_ready", False))
        self.assertNotIn("SAFETY_CLEAN", [
            result.get("safety_status_label"), result.get("applied_safety_evidence_row_id")
        ])
        self._assert_no_downstream_unlocks()

    def test_stale_evidence_is_not_reused_across_windows(self):
        """Evidence with stale freshness_label must never be applied."""
        snapshot_ids = self._seed_snapshots()
        last_snapshot_id = snapshot_ids[-1]
        build_collect_context_once_payload(
            self._args(snapshot_id=last_snapshot_id, source_reference="stale-evidence-ctx")
        )
        self._force_all_context_known()

        mw_result = build_memory_window_once_payload(self._args(
            snapshot_id=last_snapshot_id,
            source_reference="stale-first-window",
        ))
        mw_id = int(mw_result["memory_result"]["memory_window_id"])

        # Insert stale safety evidence
        self._insert_safety(
            last_snapshot_id,
            memory_window_id=mw_id,
            freshness_label="SAFETY_EVIDENCE_STALE",
        )

        new_memory = build_memory_window_once_payload(self._args(
            snapshot_id=last_snapshot_id,
            source_reference="stale-second-window",
        ))
        result = new_memory["memory_result"]

        # Stale safety → blocked
        self.assertIn(result["memory_quality_label"], {"AUDIT_ONLY_MEMORY", "DIRTY_MEMORY"})
        self.assertFalse(result.get("retrieval_ready", False))
        self._assert_no_downstream_unlocks()

    def test_target_mismatched_evidence_is_not_reused(self):
        """Evidence with target_status != TARGET_MATCH must never be applied."""
        snapshot_ids = self._seed_snapshots()
        last_snapshot_id = snapshot_ids[-1]
        build_collect_context_once_payload(
            self._args(snapshot_id=last_snapshot_id, source_reference="mismatch-ctx")
        )
        self._force_all_context_known()

        mw_result = build_memory_window_once_payload(self._args(
            snapshot_id=last_snapshot_id,
            source_reference="mismatch-first-window",
        ))
        mw_id = int(mw_result["memory_result"]["memory_window_id"])

        # Insert target-mismatched evidence
        self._insert_safety(
            last_snapshot_id,
            memory_window_id=mw_id,
            target_status="TARGET_MISMATCH",
        )

        new_memory = build_memory_window_once_payload(self._args(
            snapshot_id=last_snapshot_id,
            source_reference="mismatch-second-window",
        ))
        result = new_memory["memory_result"]

        # Mismatched target → rejected
        self.assertIn(result["memory_quality_label"], {"AUDIT_ONLY_MEMORY", "DIRTY_MEMORY"})
        self._assert_no_downstream_unlocks()

    def test_5m_window_remains_do_not_train_regardless(self):
        """5m micro-event support windows must not be elevated by evidence reuse."""
        snapshot_ids = self._seed_snapshots()
        last_snapshot_id = snapshot_ids[-1]
        build_collect_context_once_payload(
            self._args(snapshot_id=last_snapshot_id, source_reference="5m-test-ctx")
        )
        self._force_all_context_known()

        mw_result = build_memory_window_once_payload(self._args(
            snapshot_id=last_snapshot_id,
            source_reference="5m-window-test",
            memory_window="5m",
        ))
        result = mw_result["memory_result"]

        self.assertIn(result["memory_quality_label"],
                      {"AUDIT_ONLY_MEMORY", "DO_NOT_TRAIN_MEMORY", "DIRTY_MEMORY"})
        self.assertFalse(result.get("retrieval_ready", False))
        self.assertEqual(result.get("do_not_train", 1), 1)
        self._assert_no_downstream_unlocks()

    def test_retrieval_matches_remains_zero_after_evidence_reuse(self):
        """Evidence reuse must never unlock retrieval."""
        snapshot_ids = self._seed_snapshots()
        last_snapshot_id = snapshot_ids[-1]
        build_collect_context_once_payload(
            self._args(snapshot_id=last_snapshot_id, source_reference="retrieval-guard-ctx")
        )
        self._force_all_context_known()

        mw_result = build_memory_window_once_payload(self._args(
            snapshot_id=last_snapshot_id,
            source_reference="retrieval-guard-first-window",
        ))
        mw_id = int(mw_result["memory_result"]["memory_window_id"])
        self._insert_safety(last_snapshot_id, memory_window_id=mw_id)
        self._insert_quote(last_snapshot_id, "ENTRY", 930, 931, memory_window_id=mw_id)
        self._insert_quote(last_snapshot_id, "EXIT", 940, 941, memory_window_id=mw_id)
        self._insert_new_market_regime_row(last_snapshot_id)

        build_memory_window_once_payload(self._args(
            snapshot_id=last_snapshot_id,
            source_reference="retrieval-guard-new-window",
        ))

        with self.connect() as conn:
            self.assertEqual(count_rows(conn, "printer_memory_retrieval_queries"), 0)
            self.assertEqual(count_rows(conn, "printer_memory_retrieval_matches"), 0)
            self.assertEqual(count_rows(conn, "printer_paper_decisions"), 0)
            self.assertEqual(count_rows(conn, "printer_paper_positions"), 0)
            self.assertEqual(count_rows(conn, "printer_paper_trade_events"), 0)
            self.assertEqual(count_rows(conn, "printer_paper_trade_audits"), 0)


if __name__ == "__main__":
    unittest.main()
