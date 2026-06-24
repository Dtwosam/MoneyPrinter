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
    build_memory_window_once_payload,
)
from printer_v1.paper_quote.evidence import insert_paper_quote_evidence
from printer_v1.safety.evidence import insert_solana_safety_evidence


def count_rows(connection, table):
    return int(connection.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0])


class PostRCNewMemoryBuildSafetyQuoteEvidenceReadTests(unittest.TestCase):
    def setUp(self):
        self.tempdir = tempfile.TemporaryDirectory()
        self.db_path = pathlib.Path(self.tempdir.name) / "new-memory-build.sqlite3"
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
            "token_mint": "new-memory-mint",
            "token_id": None,
            "pair_address": "new-memory-pair",
            "pair_id": None,
            "snapshot_id": None,
            "memory_window_id": None,
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
                    "pairAddress": "new-memory-pair",
                    "baseToken": {"address": "new-memory-mint", "symbol": "NEW", "name": "New Memory"},
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

    def seed_token_pair(self):
        build_manual_intake_token_pair_payload(self.args(
            pair_id=None,
            pool_address=None,
            intake_reason="new memory build evidence read",
            source_reference="new-memory-intake",
            source_request_id=None,
            token_symbol="NEW",
            token_name="New Memory",
            dex_id="dexscreener",
            intake_json=None,
        ))

    def collect_snapshot_at(self, index, captured_at):
        build_collect_token_snapshots_once_payload(self.args(
            snapshot_count=1,
            max_seconds=5.0,
            source_name="dexscreener",
            source_reference=f"new-memory-snapshot-{index}",
        ), transport=self.transport)
        with self.connect() as connection:
            row = connection.execute(
                "SELECT id, normalized_snapshot_payload_json FROM printer_token_snapshots ORDER BY id DESC LIMIT 1"
            ).fetchone()
            normalized = json.loads(row["normalized_snapshot_payload_json"] or "{}")
            normalized["captured_at"] = captured_at.isoformat()
            connection.execute(
                """
                UPDATE printer_token_snapshots
                SET captured_at = ?, normalized_snapshot_payload_json = ?
                WHERE id = ?
                """,
                (captured_at.isoformat(), json.dumps(normalized, sort_keys=True), int(row["id"])),
            )
            return int(row["id"])

    def seed_initial_audit_only_window(self):
        self.seed_token_pair()
        snapshot_ids = [
            self.collect_snapshot_at(index, self.base_time + timedelta(minutes=index * 3))
            for index in range(6)
        ]
        build_collect_context_once_payload(self.args(snapshot_id=snapshot_ids[-1], source_name="dexscreener"))
        memory = build_memory_window_once_payload(self.args(
            snapshot_id=snapshot_ids[-1],
            memory_window="15m",
            source_reference="old-audit-only-window",
        ))
        self.assertEqual(memory["memory_result"]["memory_quality_label"], "AUDIT_ONLY_MEMORY")
        self.assertFalse(memory["memory_result"]["retrieval_ready"])
        return snapshot_ids, int(memory["memory_result"]["memory_window_id"])

    def add_distinct_window_snapshot_and_context(self):
        snapshot_id = self.collect_snapshot_at(6, self.base_time + timedelta(minutes=18))
        build_collect_context_once_payload(self.args(snapshot_id=snapshot_id, source_name="dexscreener"))
        return snapshot_id

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

    def force_known_broad_and_flow_context_only(self):
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

    def seed_source_trace(self, source_name, request_id, response_id):
        with self.connect() as connection:
            connection.execute(
                """
                INSERT OR IGNORE INTO printer_source_requests (
                    id, source_name, request_kind, requested_at, request_key,
                    tracking_priority, source_status, data_quality_label
                ) VALUES (?, ?, 'MEMORY_BUILD_EVIDENCE_FIXTURE', ?, ?, 1, 'COMPLETE', 'CLEAN_DATA')
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

    def insert_safety(self, snapshot_id, **overrides):
        self.seed_source_trace("fixture_safety_source", 100, 101)
        evidence = {
            "token_id": 1,
            "pair_id": 1,
            "snapshot_id": snapshot_id,
            "memory_window_id": None,
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

    def insert_quote(self, snapshot_id, direction, request_id, response_id, **overrides):
        source_name = f"fixture_{direction.lower()}_quote_source"
        self.seed_source_trace(source_name, request_id, response_id)
        evidence = {
            "token_id": 1,
            "pair_id": 1,
            "snapshot_id": snapshot_id,
            "memory_window_id": None,
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

    def insert_valid_safety_and_quotes(self, snapshot_id):
        self.insert_safety(snapshot_id)
        self.insert_quote(snapshot_id, "ENTRY", 200, 201)
        self.insert_quote(snapshot_id, "EXIT", 300, 301)

    def latest_fingerprint(self, memory_window_id):
        with self.connect() as connection:
            row = connection.execute(
                """
                SELECT f.*
                FROM printer_memory_fingerprints f
                JOIN printer_episodes e ON e.id = f.episode_id
                WHERE e.memory_window_id = ?
                ORDER BY f.id DESC
                LIMIT 1
                """,
                (memory_window_id,),
            ).fetchone()
            payload = json.loads(row["fingerprint_payload_json"] or "{}")
            return row, payload

    def assert_no_downstream_unlocks(self):
        with self.connect() as connection:
            self.assertEqual(count_rows(connection, "printer_memory_retrieval_queries"), 0)
            self.assertEqual(count_rows(connection, "printer_memory_retrieval_matches"), 0)
            self.assertEqual(count_rows(connection, "printer_paper_decisions"), 0)
            self.assertEqual(count_rows(connection, "printer_paper_positions"), 0)
            self.assertEqual(count_rows(connection, "printer_paper_trade_events"), 0)
            self.assertEqual(count_rows(connection, "printer_paper_trade_audits"), 0)

    def test_new_distinct_window_can_be_clean_with_valid_controlled_safety_and_quote_evidence(self):
        _old_snapshot_ids, old_window_id = self.seed_initial_audit_only_window()
        new_snapshot_id = self.add_distinct_window_snapshot_and_context()
        self.force_known_context_except_safety_and_quotes()
        self.insert_valid_safety_and_quotes(new_snapshot_id)

        new_memory = build_memory_window_once_payload(self.args(
            snapshot_id=new_snapshot_id,
            memory_window="15m",
            source_reference="new-clean-evidence-window",
        ))
        result = new_memory["memory_result"]

        self.assertNotEqual(result["memory_window_id"], old_window_id)
        self.assertEqual(result["memory_quality_label"], "CLEAN_MEMORY")
        self.assertTrue(result["retrieval_ready"])
        self.assertEqual(result["do_not_train"], 0)
        self.assertEqual(result["rejection_reasons"], ["REVIEW_PASSED"])
        self.assertEqual(result["coverage_policy_used"], "WINDOW_15M_TRACKED_SPACED_6_SNAPSHOT_POLICY")
        self.assertEqual(result["expected_snapshot_count"], 6)
        self.assertEqual(result["actual_snapshot_count"], 6)
        self.assertEqual(result["missing_snapshot_count"], 0)
        self.assertEqual(result["unknown_context_blockers"], [])
        self.assertEqual(result["evidence_blockers"], [])
        self.assertTrue(result["snapshot_start_id"] > 1)
        fingerprint, payload = self.latest_fingerprint(result["memory_window_id"])
        self.assertEqual(fingerprint["memory_status"], "CLEAN_MEMORY")
        self.assertEqual(fingerprint["do_not_train"], 0)
        self.assertTrue(payload["retrieval_ready"])
        self.assertEqual(payload["safety_status_label"], "SAFETY_CLEAN")
        self.assertEqual(payload["entry_realism_label"], "ENTRY_REALISTIC")
        self.assertEqual(payload["exit_realism_label"], "EXIT_REALISTIC")

        with self.connect() as connection:
            old = connection.execute(
                "SELECT * FROM printer_memory_windows WHERE id = ?",
                (old_window_id,),
            ).fetchone()
            self.assertEqual(old["memory_quality_label"], "AUDIT_ONLY_MEMORY")
            self.assertEqual(old["do_not_train"], 1)
            self.assertEqual(count_rows(connection, "printer_memory_retrieval_queries"), 0)
            self.assertEqual(count_rows(connection, "printer_memory_retrieval_matches"), 0)
            self.assertEqual(count_rows(connection, "printer_paper_decisions"), 0)
            self.assertEqual(count_rows(connection, "printer_paper_positions"), 0)
            self.assertEqual(count_rows(connection, "printer_paper_trade_events"), 0)

    def test_six_snapshot_window_derives_chart_and_held_outcome_without_manual_context_patching(self):
        self.seed_token_pair()
        snapshot_ids = [
            self.collect_snapshot_at(index, self.base_time + timedelta(minutes=index * 3))
            for index in range(6)
        ]
        build_collect_context_once_payload(self.args(snapshot_id=snapshot_ids[-1], source_name="dexscreener"))
        self.force_known_broad_and_flow_context_only()
        self.insert_valid_safety_and_quotes(snapshot_ids[-1])

        memory = build_memory_window_once_payload(self.args(
            snapshot_id=snapshot_ids[-1],
            memory_window="15m",
            source_reference="derived-chart-held-outcome",
        ))
        result = memory["memory_result"]

        self.assertEqual(result["memory_quality_label"], "CLEAN_MEMORY")
        self.assertTrue(result["retrieval_ready"])
        self.assertNotEqual(result["volatility_label"], "VOLATILITY_UNKNOWN")
        self.assertEqual(result["held_to_15m_result_label"], "HELD_TO_15M_CONSOLIDATED")
        self.assertEqual(result["unknown_context_blockers"], [])
        self.assertEqual(result["evidence_blockers"], [])
        with self.connect() as connection:
            window = connection.execute(
                "SELECT supporting_context_json FROM printer_memory_windows WHERE id = ?",
                (result["memory_window_id"],),
            ).fetchone()
            support = json.loads(window["supporting_context_json"])
            self.assertTrue(support["derived_window_context"]["derived"])
            self.assertEqual(support["derived_window_context"]["snapshot_ids"], snapshot_ids)

    def test_existing_clean_memory_same_evidence_remains_duplicate_noop(self):
        self.seed_token_pair()
        snapshot_ids = [
            self.collect_snapshot_at(index, self.base_time + timedelta(minutes=index * 3))
            for index in range(6)
        ]
        build_collect_context_once_payload(self.args(snapshot_id=snapshot_ids[-1], source_name="dexscreener"))
        self.force_known_context_except_safety_and_quotes()
        self.insert_valid_safety_and_quotes(snapshot_ids[-1])

        first = build_memory_window_once_payload(self.args(
            snapshot_id=snapshot_ids[-1],
            memory_window="15m",
            source_reference="clean-duplicate-proof",
        ))
        first_result = first["memory_result"]
        self.assertEqual(first_result["memory_quality_label"], "CLEAN_MEMORY")
        self.assertTrue(first_result["retrieval_ready"])

        second = build_memory_window_once_payload(self.args(
            snapshot_id=snapshot_ids[-1],
            memory_window="15m",
            source_reference="clean-duplicate-proof",
        ))
        second_result = second["memory_result"]

        self.assertEqual(second_result["memory_window_id"], first_result["memory_window_id"])
        self.assertEqual(second_result["duplicate_guard_status"], "DUPLICATE_SAME_EVIDENCE_NOOP")
        self.assertEqual(second_result["skipped_reason"], "duplicate_same_evidence_noop")
        self.assertFalse(second_result["evidence_revision_created"])
        with self.connect() as connection:
            self.assertEqual(count_rows(connection, "printer_memory_windows"), 1)
        self.assert_no_downstream_unlocks()

    def test_existing_audit_only_without_new_evidence_remains_duplicate_noop(self):
        _snapshot_ids, old_window_id = self.seed_initial_audit_only_window()

        duplicate = build_memory_window_once_payload(self.args(
            snapshot_id=None,
            memory_window="15m",
            source_reference="old-audit-only-window",
        ))
        result = duplicate["memory_result"]

        self.assertEqual(result["memory_window_id"], old_window_id)
        self.assertEqual(result["memory_quality_label"], "AUDIT_ONLY_MEMORY")
        self.assertEqual(result["duplicate_guard_status"], "DUPLICATE_SAME_EVIDENCE_NOOP")
        self.assertEqual(result["skipped_reason"], "duplicate_same_evidence_noop")
        self.assertFalse(result["evidence_revision_created"])
        with self.connect() as connection:
            self.assertEqual(count_rows(connection, "printer_memory_windows"), 1)
        self.assert_no_downstream_unlocks()

    def test_existing_audit_only_with_new_memory_bound_evidence_creates_revision_row(self):
        snapshot_ids, old_window_id = self.seed_initial_audit_only_window()
        safety = self.insert_safety(snapshot_ids[-1], memory_window_id=old_window_id)
        entry = self.insert_quote(snapshot_ids[-1], "ENTRY", 200, 201, memory_window_id=old_window_id)
        exit_quote = self.insert_quote(snapshot_ids[-1], "EXIT", 300, 301, memory_window_id=old_window_id)

        revision = build_memory_window_once_payload(self.args(
            snapshot_id=snapshot_ids[-1],
            memory_window="15m",
            source_reference="old-audit-only-window",
        ))
        result = revision["memory_result"]

        self.assertNotEqual(result["memory_window_id"], old_window_id)
        self.assertEqual(result["existing_memory_window_id"], old_window_id)
        self.assertTrue(result["evidence_revision_created"])
        self.assertIn("new_clean_safety_evidence", result["evidence_revision_reason"])
        self.assertIn("new_clean_entry_quote_evidence", result["evidence_revision_reason"])
        self.assertIn("new_clean_exit_quote_evidence", result["evidence_revision_reason"])
        self.assertEqual(result["duplicate_guard_status"], "EVIDENCE_REVISION_CREATED")
        self.assertEqual(result["applied_safety_evidence_row_id"], safety.evidence_id)
        self.assertEqual(result["applied_entry_quote_evidence_row_id"], entry.evidence_id)
        self.assertEqual(result["applied_exit_quote_evidence_row_id"], exit_quote.evidence_id)
        self.assertEqual(result["safety_status_label"], "SAFETY_CLEAN")
        self.assertEqual(result["entry_realism_label"], "ENTRY_REALISTIC")
        self.assertEqual(result["exit_realism_label"], "EXIT_REALISTIC")
        self.assertEqual(result["memory_quality_label"], "AUDIT_ONLY_MEMORY")
        self.assertFalse(result["retrieval_ready"])
        self.assertTrue(result["remaining_blockers"])

        with self.connect() as connection:
            old = connection.execute(
                "SELECT * FROM printer_memory_windows WHERE id = ?",
                (old_window_id,),
            ).fetchone()
            self.assertEqual(old["memory_quality_label"], "AUDIT_ONLY_MEMORY")
            self.assertEqual(old["do_not_train"], 1)
            self.assertEqual(count_rows(connection, "printer_memory_windows"), 2)
            revision_row = connection.execute(
                "SELECT supporting_context_json FROM printer_memory_windows WHERE id = ?",
                (result["memory_window_id"],),
            ).fetchone()
            support = json.loads(revision_row["supporting_context_json"])
            self.assertTrue(support["evidence_revision_created"])
            self.assertEqual(support["existing_memory_window_id"], old_window_id)
            self.assertEqual(support["applied_safety_evidence_row_id"], safety.evidence_id)
        self.assert_no_downstream_unlocks()

    def test_dirty_or_stale_memory_bound_evidence_does_not_create_revision(self):
        snapshot_ids, old_window_id = self.seed_initial_audit_only_window()
        self.insert_safety(
            snapshot_ids[-1],
            memory_window_id=old_window_id,
            freshness_label="SAFETY_EVIDENCE_STALE",
        )
        self.insert_quote(
            snapshot_ids[-1],
            "ENTRY",
            200,
            201,
            memory_window_id=old_window_id,
            freshness_label="QUOTE_STALE",
        )
        self.insert_quote(
            snapshot_ids[-1],
            "EXIT",
            300,
            301,
            memory_window_id=old_window_id,
            freshness_label="QUOTE_STALE",
        )

        duplicate = build_memory_window_once_payload(self.args(
            snapshot_id=snapshot_ids[-1],
            memory_window="15m",
            source_reference="old-audit-only-window",
        ))
        result = duplicate["memory_result"]

        self.assertEqual(result["memory_window_id"], old_window_id)
        self.assertEqual(result["duplicate_guard_status"], "DUPLICATE_SAME_EVIDENCE_NOOP")
        self.assertEqual(result["skipped_reason"], "duplicate_same_evidence_noop")
        self.assertFalse(result["evidence_revision_created"])
        with self.connect() as connection:
            self.assertEqual(count_rows(connection, "printer_memory_windows"), 1)
        self.assert_no_downstream_unlocks()

    def test_missing_or_unsafe_safety_or_quote_evidence_keeps_new_memory_blocked(self):
        self.seed_token_pair()
        cases = [
            ("missing_safety", {
                "safety": False,
                "entry": True,
                "exit": True,
                "expected_blockers": ["NO_VALID_SAFETY_EVIDENCE_FOR_TARGET"],
            }),
            ("stale_safety", {
                "safety": True,
                "entry": True,
                "exit": True,
                "safety_overrides": {"freshness_label": "SAFETY_EVIDENCE_STALE"},
                "expected_blockers": ["SAFETY_EVIDENCE_STALE"],
            }),
            ("mismatched_safety", {
                "safety": True,
                "entry": True,
                "exit": True,
                "safety_overrides": {"target_status": "TARGET_MISMATCH"},
                "expected_blockers": ["SAFETY_EVIDENCE_TARGET_MISMATCH"],
            }),
            ("missing_quote", {
                "safety": True,
                "entry": False,
                "exit": False,
                "expected_blockers": [
                    "ENTRY_QUOTE_EVIDENCE_TARGET_MISMATCH",
                    "EXIT_QUOTE_EVIDENCE_TARGET_MISMATCH",
                ],
            }),
            ("stale_quote", {
                "safety": True,
                "entry": True,
                "exit": True,
                "quote_overrides": {"freshness_label": "QUOTE_STALE"},
                "expected_blockers": ["ENTRY_QUOTE_EVIDENCE_STALE", "EXIT_QUOTE_EVIDENCE_STALE"],
            }),
            ("mismatched_quote", {
                "safety": True,
                "entry": True,
                "exit": True,
                "quote_overrides": {"target_status": "TARGET_MISMATCH"},
                "expected_blockers": [
                    "ENTRY_QUOTE_EVIDENCE_TARGET_MISMATCH",
                    "EXIT_QUOTE_EVIDENCE_TARGET_MISMATCH",
                ],
            }),
        ]
        for case_index, (name, toggles) in enumerate(cases):
            with self.subTest(name=name):
                start = self.base_time + timedelta(hours=case_index + 1)
                snapshot_ids = [
                    self.collect_snapshot_at(case_index * 10 + index, start + timedelta(minutes=index * 3))
                    for index in range(6)
                ]
                build_collect_context_once_payload(self.args(snapshot_id=snapshot_ids[-1], source_name="dexscreener"))
                self.force_known_context_except_safety_and_quotes()
                if toggles.get("safety"):
                    self.insert_safety(snapshot_ids[-1], **toggles.get("safety_overrides", {}))
                if toggles.get("entry"):
                    self.insert_quote(snapshot_ids[-1], "ENTRY", 200, 201, **toggles.get("quote_overrides", {}))
                if toggles.get("exit"):
                    self.insert_quote(snapshot_ids[-1], "EXIT", 300, 301, **toggles.get("quote_overrides", {}))

                memory = build_memory_window_once_payload(self.args(
                    snapshot_id=snapshot_ids[-1],
                    memory_window="15m",
                    source_reference=f"blocked-{name}",
                ))
                result = memory["memory_result"]
                self.assertEqual(result["memory_quality_label"], "AUDIT_ONLY_MEMORY")
                self.assertFalse(result["retrieval_ready"])
                self.assertEqual(result["do_not_train"], 1)
                self.assertIn("MISSING_OR_UNKNOWN_CONTEXT", result["rejection_reasons"])
                self.assertTrue(result["context_blocking_reasons"])
                self.assertTrue(result["unknown_context_blockers"] or result["evidence_blockers"])
                for blocker in toggles["expected_blockers"]:
                    self.assertIn(blocker, result["evidence_blockers"])

    def test_two_snapshot_15m_window_reports_sparse_coverage_not_full_proof(self):
        self.seed_token_pair()
        snapshot_ids = [
            self.collect_snapshot_at(index, self.base_time + timedelta(minutes=index * 3))
            for index in range(2)
        ]
        build_collect_context_once_payload(self.args(snapshot_id=snapshot_ids[-1], source_name="dexscreener"))
        self.force_known_context_except_safety_and_quotes()
        self.insert_valid_safety_and_quotes(snapshot_ids[-1])

        memory = build_memory_window_once_payload(self.args(
            snapshot_id=snapshot_ids[-1],
            memory_window="15m",
            source_reference="sparse-15m-window",
        ))
        result = memory["memory_result"]

        self.assertEqual(result["coverage_policy_used"], "WINDOW_15M_TRACKED_SPACED_6_SNAPSHOT_POLICY")
        self.assertEqual(result["expected_snapshot_count"], 6)
        self.assertEqual(result["actual_snapshot_count"], 2)
        self.assertEqual(result["missing_snapshot_count"], 4)
        self.assertEqual(result["coverage_state"], "INCOMPLETE_15M_WINDOW")
        self.assertEqual(result["memory_quality_label"], "DIRTY_MEMORY")
        self.assertFalse(result["retrieval_ready"])
        self.assertIn("INSUFFICIENT_SNAPSHOT_COVERAGE", result["rejection_reasons"])

    def test_missing_evidence_reports_exact_overlay_blockers(self):
        self.seed_token_pair()
        snapshot_ids = [
            self.collect_snapshot_at(index, self.base_time + timedelta(minutes=index * 3))
            for index in range(6)
        ]
        build_collect_context_once_payload(self.args(snapshot_id=snapshot_ids[-1], source_name="dexscreener"))
        self.force_known_context_except_safety_and_quotes()

        memory = build_memory_window_once_payload(self.args(
            snapshot_id=snapshot_ids[-1],
            memory_window="15m",
            source_reference="missing-overlays",
        ))
        result = memory["memory_result"]

        self.assertEqual(result["memory_quality_label"], "AUDIT_ONLY_MEMORY")
        self.assertIn("NO_VALID_SAFETY_EVIDENCE_FOR_TARGET", result["evidence_blockers"])
        self.assertIn("NO_VALID_ENTRY_QUOTE_EVIDENCE_FOR_TARGET", result["evidence_blockers"])
        self.assertIn("NO_VALID_EXIT_QUOTE_EVIDENCE_FOR_TARGET", result["evidence_blockers"])
        self.assertTrue(result["context_blocking_reasons"])
        self.assertFalse(result["retrieval_ready"])

    def test_5m_micro_event_remains_support_only_even_with_valid_safety_and_quote_evidence(self):
        self.seed_token_pair()
        snapshot_ids = [
            self.collect_snapshot_at(index, self.base_time + timedelta(minutes=index))
            for index in range(6)
        ]
        build_collect_context_once_payload(self.args(snapshot_id=snapshot_ids[-1], source_name="dexscreener"))
        self.force_known_context_except_safety_and_quotes()
        self.insert_valid_safety_and_quotes(snapshot_ids[-1])

        memory = build_memory_window_once_payload(self.args(
            snapshot_id=snapshot_ids[-1],
            memory_window="5m",
            source_reference="support-only-5m",
        ))
        result = memory["memory_result"]

        self.assertEqual(result["memory_quality_label"], "AUDIT_ONLY_MEMORY")
        self.assertFalse(result["retrieval_ready"])
        self.assertEqual(result["do_not_train"], 1)
        self.assertIn("REJECT_5M_ONLY_WINDOW", result["rejection_reasons"])


if __name__ == "__main__":
    unittest.main()
