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

from printer_v1.db import apply_migrations
from printer_v1.operator_cli.commands import (
    build_collect_context_once_payload,
    build_collect_token_snapshots_once_payload,
    build_manual_intake_token_pair_payload,
    build_memory_quality_audit_once_payload,
    build_memory_window_once_payload,
)
from printer_v1.paper_quote.evidence import insert_paper_quote_evidence
from printer_v1.safety.evidence import insert_solana_safety_evidence


def count_rows(connection, table):
    return int(connection.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0])


class PostRCMinimalCleanMemoryAuditEvidenceReadTests(unittest.TestCase):
    def setUp(self):
        self.tempdir = tempfile.TemporaryDirectory()
        self.db_path = pathlib.Path(self.tempdir.name) / "audit-evidence-read.sqlite3"
        apply_migrations(self.db_path)
        self.base_time = datetime(2026, 6, 25, 12, 0, tzinfo=timezone.utc)

    def tearDown(self):
        self.tempdir.cleanup()

    @contextmanager
    def connect(self):
        connection = sqlite3.connect(self.db_path)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        try:
            yield connection
            connection.commit()
        finally:
            connection.close()

    def args(self, **overrides):
        values = {
            "db_path": str(self.db_path),
            "project_root": str(PROJECT_ROOT),
            "format": "json",
            "no_color": True,
            "operator_approved": True,
            "token_mint": "audit-evidence-mint",
            "token_id": None,
            "pair_address": "audit-evidence-pair",
            "pair_id": None,
            "snapshot_id": None,
            "memory_window_id": None,
            "episode_id": None,
            "chain": "solana",
        }
        values.update(overrides)
        return argparse.Namespace(**values)

    def transport(self, context):
        del context
        return {
            "pairs": [
                {
                    "chainId": "solana",
                    "pairAddress": "audit-evidence-pair",
                    "baseToken": {
                        "address": "audit-evidence-mint",
                        "symbol": "AUD",
                        "name": "Audit Evidence",
                    },
                    "priceUsd": "0.00050",
                    "liquidity": {"usd": 31000.0},
                    "volume": {"m5": 15000.0, "h1": 85000.0, "h24": 320000.0},
                    "txns": {
                        "m5": {"buys": 42, "sells": 18},
                        "h1": {"buys": 190, "sells": 72},
                        "h24": {"buys": 900, "sells": 640},
                    },
                    "fdv": 500000.0,
                    "marketCap": 455000.0,
                    "priceChange": {"m5": 14.0, "h1": 24.0, "h24": 35.0},
                }
            ]
        }

    def seed_window(self):
        build_manual_intake_token_pair_payload(self.args(
            pair_id=None,
            pool_address=None,
            intake_reason="minimal audit evidence read",
            source_reference="audit-evidence-intake",
            source_request_id=None,
            token_symbol="AUD",
            token_name="Audit Evidence",
            dex_id="dexscreener",
            intake_json=None,
        ))
        for index in range(6):
            build_collect_token_snapshots_once_payload(self.args(
                snapshot_count=1,
                max_seconds=5.0,
                source_name="dexscreener",
                source_reference=f"audit-evidence-snapshot-{index}",
            ), transport=self.transport)
        with self.connect() as connection:
            snapshot_rows = connection.execute(
                "SELECT id, normalized_snapshot_payload_json FROM printer_token_snapshots ORDER BY id"
            ).fetchall()
            snapshot_ids = [int(row["id"]) for row in snapshot_rows]
            for offset, row in enumerate(snapshot_rows):
                captured_at = (self.base_time + timedelta(minutes=offset * 3)).isoformat()
                normalized = json.loads(row["normalized_snapshot_payload_json"] or "{}")
                normalized["captured_at"] = captured_at
                connection.execute(
                    """
                    UPDATE printer_token_snapshots
                    SET captured_at = ?, normalized_snapshot_payload_json = ?
                    WHERE id = ?
                    """,
                    (captured_at, json.dumps(normalized, sort_keys=True), int(row["id"])),
                )
        build_collect_context_once_payload(self.args(snapshot_id=snapshot_ids[-1], source_name="dexscreener"))
        memory = build_memory_window_once_payload(self.args(
            snapshot_id=snapshot_ids[-1],
            memory_window="15m",
            source_reference="audit-evidence-memory",
        ))
        return snapshot_ids[-1], int(memory["memory_result"]["memory_window_id"])

    def force_known_context_except_safety_and_quotes(self):
        with self.connect() as connection:
            connection.execute(
                """
                UPDATE printer_market_regime_snapshots
                SET market_regime_label = 'RISK_ON',
                    market_transition_label = 'RISK_OFF_TO_RISK_ON',
                    market_payload_quality_label = 'MARKET_CONTEXT_CLEAN',
                    data_quality_label = 'CLEAN_DATA',
                    source_status = 'COMPLETE'
                """
            )
            connection.execute(
                """
                UPDATE printer_solana_chain_heat_snapshots
                SET chain_heat_label = 'SOLANA_WARM',
                    activity_label = 'ACTIVITY_ELEVATED',
                    liquidity_label = 'LIQUIDITY_STABLE',
                    congestion_label = 'CONGESTION_LOW',
                    chain_heat_payload_quality_label = 'CHAIN_HEAT_CONTEXT_CLEAN',
                    data_quality_label = 'CLEAN_DATA',
                    source_status = 'COMPLETE'
                """
            )
            connection.execute(
                """
                UPDATE printer_trading_flow_snapshots
                SET flow_direction_label = 'FLOW_ACCUMULATION',
                    flow_pressure_label = 'PRESSURE_MODERATE_INFLOW',
                    trading_flow_payload_quality_label = 'TRADING_FLOW_CONTEXT_CLEAN',
                    flow_memory_gate_label = 'FLOW_CONTEXT_ACCEPTABLE',
                    data_quality_label = 'CLEAN_DATA',
                    source_status = 'COMPLETE'
                """
            )
            connection.execute(
                """
                UPDATE printer_chart_volatility_snapshots
                SET trend_structure_label = 'TREND_UP',
                    volatility_label = 'VOLATILITY_NORMAL',
                    chart_payload_quality_label = 'CHART_CONTEXT_CLEAN',
                    chart_memory_gate_label = 'CHART_CONTEXT_ACCEPTABLE',
                    data_quality_label = 'CLEAN_DATA',
                    source_status = 'COMPLETE'
                """
            )
            connection.execute(
                """
                UPDATE printer_micro_events
                SET micro_event_state_label = 'NO_MICRO_EVENT',
                    held_to_15m_result_label = 'HELD_TO_15M_CONSOLIDATED',
                    micro_event_payload_quality_label = 'MICRO_EVENT_CONTEXT_CLEAN',
                    micro_event_memory_gate_label = 'MICRO_EVENT_SUPPORT_EVIDENCE',
                    data_quality_label = 'CLEAN_DATA',
                    source_status = 'COMPLETE'
                """
            )

    def seed_source_trace(self, source_name, request_id, response_id):
        with self.connect() as connection:
            connection.execute(
                """
                INSERT OR IGNORE INTO printer_source_requests (
                    id, source_name, request_kind, requested_at, request_key,
                    tracking_priority, source_status, data_quality_label
                ) VALUES (?, ?, 'AUDIT_EVIDENCE_FIXTURE', ?, ?, 1, 'COMPLETE', 'CLEAN_DATA')
                """,
                (request_id, source_name, self.base_time.isoformat(), source_name),
            )
            connection.execute(
                """
                INSERT OR IGNORE INTO printer_source_responses (
                    id, source_request_id, source_name, received_at, status_code,
                    source_status, data_quality_label, response_hash, normalized_payload_json
                ) VALUES (?, ?, ?, ?, 200, 'COMPLETE', 'CLEAN_DATA', ?, '{}')
                """,
                (response_id, request_id, source_name, self.base_time.isoformat(), f"{source_name}-hash"),
            )

    def insert_safety(self, snapshot_id, memory_window_id, **overrides):
        self.seed_source_trace("fixture_safety_source", 100, 101)
        evidence = {
            "token_id": 1,
            "pair_id": 1,
            "snapshot_id": snapshot_id,
            "memory_window_id": memory_window_id,
            "evidence_window_id": None,
            "safety_evidence_role": "TOKEN_SAFETY_CONTEXT",
            "source_name": "fixture_safety_source",
            "source_status": "COMPLETE",
            "data_quality_label": "CLEAN_DATA",
            "target_status": "TARGET_MATCH",
            "evidence_captured_at": self.base_time.isoformat(),
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
            "source_request_id": 100,
            "source_response_id": 101,
            "source_failure_id": None,
            "paper_only_context": True,
        }
        evidence.update(overrides)
        return insert_solana_safety_evidence(
            self.db_path,
            evidence,
            scheduler_boundary_label="SCHEDULER_BOUNDARY_PRESENT",
            operator_approval_label="OPERATOR_APPROVED_MANUAL_PROOF",
        )

    def insert_quote(self, snapshot_id, memory_window_id, direction, request_id, response_id, **overrides):
        source_name = f"fixture_{direction.lower()}_quote_source"
        self.seed_source_trace(source_name, request_id, response_id)
        evidence = {
            "token_id": 1,
            "pair_id": 1,
            "snapshot_id": snapshot_id,
            "memory_window_id": memory_window_id,
            "evidence_window_id": None,
            "quote_evidence_role": f"{direction}_QUOTE_CONTEXT",
            "quote_direction": direction,
            "quote_purpose": "PAPER_REALISM_ONLY",
            "source_name": source_name,
            "source_status": "COMPLETE",
            "data_quality_label": "CLEAN_DATA",
            "target_status": "TARGET_MATCH",
            "evidence_captured_at": self.base_time.isoformat(),
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
        evidence.update(overrides)
        return insert_paper_quote_evidence(
            self.db_path,
            evidence,
            scheduler_boundary_label="SCHEDULER_BOUNDARY_PRESENT",
            operator_approval_label="OPERATOR_APPROVED_MANUAL_PROOF",
        )

    def audit_report(self, memory_window_id):
        payload = build_memory_quality_audit_once_payload(self.args(memory_window_id=memory_window_id))
        return payload["audit_report"]

    def test_all_valid_controlled_evidence_removes_unknown_blockers_at_audit_label_level(self):
        snapshot_id, memory_window_id = self.seed_window()
        self.force_known_context_except_safety_and_quotes()
        self.insert_safety(snapshot_id, memory_window_id)
        self.insert_quote(snapshot_id, memory_window_id, "ENTRY", 200, 201)
        self.insert_quote(snapshot_id, memory_window_id, "EXIT", 300, 301)

        report = self.audit_report(memory_window_id)
        summary = report["context_quality_summary"]
        labels = summary["context_labels"]

        self.assertEqual(labels["safety_status_label"], "SAFETY_CLEAN")
        self.assertEqual(labels["entry_realism_label"], "ENTRY_REALISTIC")
        self.assertEqual(labels["exit_realism_label"], "EXIT_REALISTIC")
        self.assertEqual(labels["market_regime_label"], "RISK_ON")
        self.assertEqual(labels["chain_heat_label"], "SOLANA_WARM")
        self.assertEqual(labels["flow_direction_label"], "FLOW_ACCUMULATION")
        self.assertEqual(labels["flow_pressure_label"], "PRESSURE_MODERATE_INFLOW")
        self.assertEqual(summary["unknown_or_audit_only_context"], {})
        self.assertTrue(summary["audit_evidence_overlays"]["safety_evidence_applied"])
        self.assertTrue(summary["audit_evidence_overlays"]["entry_quote_evidence_applied"])
        self.assertTrue(summary["audit_evidence_overlays"]["exit_quote_evidence_applied"])
        self.assertEqual(report["memory_quality_label"], "AUDIT_ONLY_MEMORY")
        self.assertFalse(report["retrieval_ready"])
        self.assertFalse(report["clean_memory_eligible"])

    def test_missing_or_unsafe_evidence_keeps_corresponding_blocker(self):
        cases = [
            ("missing_safety", {"safety": False, "entry": True, "exit": True}, "safety_status_label"),
            ("missing_quote", {"safety": True, "entry": False, "exit": False}, "entry_realism_label"),
            ("missing_flow", {"safety": True, "entry": True, "exit": True, "flow": False}, "flow_direction_label"),
            ("missing_chain", {"safety": True, "entry": True, "exit": True, "chain": False}, "chain_heat_label"),
            ("missing_market", {"safety": True, "entry": True, "exit": True, "market": False}, "market_regime_label"),
        ]
        for name, toggles, expected_blocker in cases:
            with self.subTest(name=name):
                snapshot_id, memory_window_id = self.seed_window()
                self.force_known_context_except_safety_and_quotes()
                with self.connect() as connection:
                    if toggles.get("flow") is False:
                        connection.execute("UPDATE printer_trading_flow_snapshots SET flow_direction_label = 'FLOW_UNKNOWN', flow_pressure_label = 'PRESSURE_UNKNOWN'")
                    if toggles.get("chain") is False:
                        connection.execute("UPDATE printer_solana_chain_heat_snapshots SET chain_heat_label = 'SOLANA_UNKNOWN'")
                    if toggles.get("market") is False:
                        connection.execute("UPDATE printer_market_regime_snapshots SET market_regime_label = 'UNKNOWN'")
                if toggles.get("safety", True):
                    self.insert_safety(snapshot_id, memory_window_id)
                if toggles.get("entry", True):
                    self.insert_quote(snapshot_id, memory_window_id, "ENTRY", 200 + memory_window_id * 10, 201 + memory_window_id * 10)
                if toggles.get("exit", True):
                    self.insert_quote(snapshot_id, memory_window_id, "EXIT", 300 + memory_window_id * 10, 301 + memory_window_id * 10)

                summary = self.audit_report(memory_window_id)["context_quality_summary"]
                self.assertIn(expected_blocker, summary["unknown_or_audit_only_context"])

    def test_dirty_stale_or_failed_evidence_is_not_treated_as_clean(self):
        snapshot_id, memory_window_id = self.seed_window()
        self.force_known_context_except_safety_and_quotes()
        self.insert_safety(snapshot_id, memory_window_id, data_quality_label="STALE_DATA")
        self.insert_quote(snapshot_id, memory_window_id, "ENTRY", 200, 201, freshness_label="QUOTE_STALE")
        self.insert_quote(snapshot_id, memory_window_id, "EXIT", 300, 301, source_status="FAILED", source_response_id=None, source_failure_id=1)

        summary = self.audit_report(memory_window_id)["context_quality_summary"]
        self.assertFalse(summary["audit_evidence_overlays"]["safety_evidence_applied"])
        self.assertFalse(summary["audit_evidence_overlays"]["entry_quote_evidence_applied"])
        self.assertFalse(summary["audit_evidence_overlays"]["exit_quote_evidence_applied"])
        self.assertIn("safety_status_label", summary["unknown_or_audit_only_context"])
        self.assertIn("entry_realism_label", summary["unknown_or_audit_only_context"])
        self.assertIn("exit_realism_label", summary["unknown_or_audit_only_context"])

    def test_audit_integration_does_not_create_retrieval_paper_or_pnl_outputs(self):
        snapshot_id, memory_window_id = self.seed_window()
        self.force_known_context_except_safety_and_quotes()
        self.insert_safety(snapshot_id, memory_window_id)
        self.insert_quote(snapshot_id, memory_window_id, "ENTRY", 200, 201)
        self.insert_quote(snapshot_id, memory_window_id, "EXIT", 300, 301)
        self.audit_report(memory_window_id)

        with self.connect() as connection:
            self.assertEqual(count_rows(connection, "printer_memory_retrieval_queries"), 0)
            self.assertEqual(count_rows(connection, "printer_memory_retrieval_matches"), 0)
            self.assertEqual(count_rows(connection, "printer_paper_decisions"), 0)
            self.assertEqual(count_rows(connection, "printer_paper_positions"), 0)
            self.assertEqual(count_rows(connection, "printer_paper_trade_events"), 0)
            row = connection.execute(
                "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = 'printer_paper_pl_calculations'"
            ).fetchone()
            if row is not None:
                self.assertEqual(count_rows(connection, "printer_paper_pl_calculations"), 0)


if __name__ == "__main__":
    unittest.main()
