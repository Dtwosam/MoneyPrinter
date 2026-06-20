import inspect
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
from printer_v1.memory.contracts import MemoryQualityLabel
from printer_v1.memory_retrieval.contracts import MatchStrengthLabel, MemoryEvidenceLabel, RetrievalResultLabel
from printer_v1.paper_decision import classifier, evidence, gates, recorder, reports
from printer_v1.paper_decision.classifier import (
    classify_final_paper_action,
    classify_requested_action_from_memory_evidence,
    paper_decision_can_open_position_later,
)
from printer_v1.paper_decision.contracts import (
    DecisionGateLabel,
    MemoryEvidenceGateLabel,
    PaperDecisionActionLabel,
    PaperDecisionReasonLabel,
    PaperDecisionStatusLabel,
)
from printer_v1.paper_decision.evidence import collect_paper_decision_evidence
from printer_v1.paper_decision.gates import classify_decision_gate, classify_memory_evidence_gate
from printer_v1.paper_decision.recorder import (
    build_and_record_paper_decision,
    build_decision_payload,
    enqueue_paper_decision_job,
    record_paper_decision,
    record_paper_decision_audit,
)
from printer_v1.scheduler.contracts import JobStatus


FORBIDDEN_COLUMNS = {
    "score",
    "confidence",
    "rank",
    "rating",
    "weight",
    "wallet_address",
    "private_key",
    "signed_tx",
    "live_trade",
    "transaction_signature",
    "tx_signature",
    "execute_trade",
}


class Phase16PaperDecisionTest(unittest.TestCase):
    def setUp(self):
        self.tempdir = tempfile.TemporaryDirectory()
        self.db_path = pathlib.Path(self.tempdir.name) / "printer.sqlite3"
        apply_migrations(self.db_path)
        self.now = datetime(2026, 6, 19, 12, 0, tzinfo=timezone.utc)
        self.next_token_number = 0
        self.token_id, self.pair_id = self.insert_token_pair()

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

    def insert_token_pair(self):
        self.next_token_number += 1
        mint = f"decision-mint-{self.next_token_number}"
        pair = f"decision-pair-{self.next_token_number}"
        with self.connect() as connection:
            token_id = connection.execute("INSERT INTO printer_tokens (token_mint, chain) VALUES (?, 'solana')", (mint,)).lastrowid
            pair_id = connection.execute(
                "INSERT INTO printer_pairs (token_id, pair_address, dex, pool_source) VALUES (?, ?, 'raydium', 'local')",
                (token_id, pair),
            ).lastrowid
        return int(token_id), int(pair_id)

    def column_names(self, table):
        with self.connect() as connection:
            return {row[1] for row in connection.execute(f"PRAGMA table_info({table})")}

    def count_rows(self, table):
        with self.connect() as connection:
            return connection.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]

    def insert_current_context(self, **overrides):
        payload = {
            "token_id": self.token_id,
            "pair_id": self.pair_id,
            "token_mint": f"decision-mint-{self.next_token_number}",
            "pair_address": f"decision-pair-{self.next_token_number}",
            "captured_at": self.now.isoformat(),
            "liquidity_usd": 50000,
            "expected_entry_size_usd": 100,
            "expected_exit_size_usd": 100,
            "route_available": 1,
            "quote_status": "QUOTE_FRESH",
            "route_status": "ROUTE_AVAILABLE",
            "liquidity_state_label": "LIQUIDITY_USABLE",
            "entry_realism_label": "ENTRY_REALISTIC",
            "exit_realism_label": "EXIT_REALISTIC",
            "slippage_label": "SLIPPAGE_LOW",
            "price_impact_label": "PRICE_IMPACT_LOW",
            "route_label": "ROUTE_AVAILABLE",
            "quote_age_label": "QUOTE_FRESH",
            "liquidity_drain_label": "NO_LIQUIDITY_DRAIN",
            "liquidity_exit_payload_quality_label": "LIQUIDITY_EXIT_CONTEXT_CLEAN",
            "realism_gate_label": "REALISM_CONTEXT_ACCEPTABLE",
            "source_status": SourceStatus.COMPLETE.value,
            "data_quality_label": DataQualityLabel.CLEAN_DATA.value,
        }
        payload.update(overrides)
        with self.connect() as connection:
            connection.execute(
                """
                INSERT INTO printer_liquidity_exit_snapshots (
                    token_id, pair_id, token_mint, pair_address, captured_at,
                    liquidity_usd, expected_entry_size_usd, expected_exit_size_usd,
                    route_available, quote_status, route_status, liquidity_state_label,
                    entry_realism_label, exit_realism_label, slippage_label,
                    price_impact_label, route_label, quote_age_label,
                    liquidity_drain_label, liquidity_exit_payload_quality_label,
                    realism_gate_label, source_status, data_quality_label,
                    raw_liquidity_exit_payload_json, normalized_liquidity_exit_payload_json
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, '{}', '{}')
                """,
                (
                    payload["token_id"],
                    payload["pair_id"],
                    payload["token_mint"],
                    payload["pair_address"],
                    payload["captured_at"],
                    payload["liquidity_usd"],
                    payload["expected_entry_size_usd"],
                    payload["expected_exit_size_usd"],
                    payload["route_available"],
                    payload["quote_status"],
                    payload["route_status"],
                    payload["liquidity_state_label"],
                    payload["entry_realism_label"],
                    payload["exit_realism_label"],
                    payload["slippage_label"],
                    payload["price_impact_label"],
                    payload["route_label"],
                    payload["quote_age_label"],
                    payload["liquidity_drain_label"],
                    payload["liquidity_exit_payload_quality_label"],
                    payload["realism_gate_label"],
                    payload["source_status"],
                    payload["data_quality_label"],
                ),
            )
            connection.execute(
                """
                INSERT INTO printer_safety_rug_snapshots (
                    token_id, pair_id, token_mint, pair_address, captured_at,
                    safety_status_label, rug_risk_label, liquidity_safety_label,
                    authority_label, distribution_label, safety_gate_label,
                    safety_payload_quality_label, source_status, data_quality_label,
                    raw_safety_payload_json, normalized_safety_payload_json
                )
                VALUES (?, ?, ?, ?, ?, ?, 'RUG_RISK_LOW', 'LIQUIDITY_SAFE',
                    'AUTHORITY_RENOUNCED_OR_SAFE', 'DISTRIBUTION_HEALTHY',
                    'ALLOW_SAFETY_CONTEXT', 'SAFETY_CONTEXT_CLEAN', ?, ?, '{}', '{}')
                """,
                (
                    self.token_id,
                    self.pair_id,
                    payload["token_mint"],
                    payload["pair_address"],
                    self.now.isoformat(),
                    payload.get("safety_status_label", "SAFETY_CLEAN"),
                    payload["source_status"],
                    payload["data_quality_label"],
                ),
            )

    def insert_retrieval(self, *, result="RETRIEVAL_HAS_CLEAN_MATCHES", evidence_label="MEMORY_EVIDENCE_STRONG", clean=True, outcome="REALISTIC_PAPER_PROFIT", lesson="ACTION_BUY_WORKED"):
        with self.connect() as connection:
            query_id = connection.execute(
                """
                INSERT INTO printer_memory_retrieval_queries (
                    query_type, token_id, pair_id, query_at, current_fingerprint_json,
                    query_context_json, retrieval_result_label, memory_evidence_label,
                    data_quality_label, source_status
                )
                VALUES ('CURRENT_SETUP_QUERY', ?, ?, ?, '{}', '{}', ?, ?, 'CLEAN_DATA', 'COMPLETE')
                """,
                (self.token_id, self.pair_id, self.now.isoformat(), result, evidence_label),
            ).lastrowid
            if result != "RETRIEVAL_NO_MATCHES":
                connection.execute(
                    """
                    INSERT INTO printer_memory_retrieval_matches (
                        retrieval_query_id, episode_id, memory_window_id, token_id, pair_id,
                        window_kind, outcome_label, action_lesson_label, memory_quality_label,
                        match_strength_label, included_as_clean_evidence, included_as_audit_context
                    )
                    VALUES (?, 10, 20, ?, ?, 'WINDOW_15M', ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        query_id,
                        self.token_id,
                        self.pair_id,
                        outcome,
                        lesson,
                        MemoryQualityLabel.CLEAN_MEMORY.value if clean else MemoryQualityLabel.DIRTY_MEMORY.value,
                        MatchStrengthLabel.EXACT_CONDITION_MATCH.value if clean else MatchStrengthLabel.DIRTY_MEMORY_EXCLUDED.value,
                        1 if clean else 0,
                        0 if clean else 1,
                    ),
                )
        return int(query_id)

    def test_memory_retrieval_package_has_dunder_init_not_accidental_init(self):
        self.assertTrue((SRC_PATH / "printer_v1" / "memory_retrieval" / "__init__.py").exists())
        self.assertFalse((SRC_PATH / "printer_v1" / "memory_retrieval" / "init.py").exists())

    def test_files_import_and_contract_labels_exist(self):
        for module in (classifier, evidence, gates, recorder, reports):
            self.assertTrue(inspect.ismodule(module))
        self.assertEqual({label.value for label in PaperDecisionActionLabel}, {"BUY", "SELL", "HOLD", "WAIT", "AVOID", "NO_ACTION"})
        self.assertIn("DECISION_BLOCKED_NO_CLEAN_MEMORY", {label.value for label in DecisionGateLabel})
        self.assertIn("MEMORY_GATE_CLEAN_MATCH", {label.value for label in MemoryEvidenceGateLabel})
        self.assertIn("REASON_NOT_ENOUGH_CLEAN_MEMORY", {label.value for label in PaperDecisionReasonLabel})
        self.assertIn("PAPER_DECISION_PROPOSED", {label.value for label in PaperDecisionStatusLabel})

    def test_migration_tables_and_forbidden_columns(self):
        self.assertIn("final_action_label", self.column_names("printer_paper_decisions"))
        self.assertIn("audit_payload_json", self.column_names("printer_paper_decision_audits"))
        for table in ("printer_paper_decisions", "printer_paper_decision_audits"):
            self.assertEqual(self.column_names(table) & FORBIDDEN_COLUMNS, set(), table)

    def test_gates_block_missing_dirty_unsafe_unrealistic_stale_conflicting_and_weak(self):
        self.insert_current_context()
        no_memory = collect_paper_decision_evidence(self.db_path, self.token_id, self.pair_id)
        self.assertEqual(classify_decision_gate(no_memory), DecisionGateLabel.DECISION_BLOCKED_NO_CLEAN_MEMORY)
        cases = [
            ({"data_quality_label": DataQualityLabel.DIRTY_DATA.value}, DecisionGateLabel.DECISION_BLOCKED_DIRTY_CURRENT_CONTEXT),
            ({"safety_status_label": "SAFETY_UNSAFE"}, DecisionGateLabel.DECISION_BLOCKED_UNSAFE_TOKEN),
            ({"exit_realism_label": "EXIT_UNREALISTIC"}, DecisionGateLabel.DECISION_BLOCKED_UNREALISTIC_EXIT),
            ({"route_label": "ROUTE_NOT_AVAILABLE"}, DecisionGateLabel.DECISION_BLOCKED_NO_ROUTE),
            ({"source_status": SourceStatus.STALE.value}, DecisionGateLabel.DECISION_BLOCKED_STALE_DATA),
            ({"source_status": SourceStatus.CONFLICTING.value}, DecisionGateLabel.DECISION_BLOCKED_CONFLICTING_DATA),
        ]
        for overrides, expected in cases:
            other_token, other_pair = self.insert_token_pair()
            self.token_id, self.pair_id = other_token, other_pair
            self.insert_current_context(**overrides)
            self.insert_retrieval()
            ev = collect_paper_decision_evidence(self.db_path, self.token_id, self.pair_id)
            self.assertEqual(classify_decision_gate(ev), expected)
        other_token, other_pair = self.insert_token_pair()
        self.token_id, self.pair_id = other_token, other_pair
        self.insert_current_context()
        self.insert_retrieval(evidence_label=MemoryEvidenceLabel.MEMORY_EVIDENCE_WEAK.value)
        ev = collect_paper_decision_evidence(self.db_path, self.token_id, self.pair_id)
        self.assertEqual(classify_memory_evidence_gate(ev), MemoryEvidenceGateLabel.MEMORY_GATE_WEAK_MATCH)
        self.assertEqual(classify_decision_gate(ev), DecisionGateLabel.DECISION_BLOCKED_INSUFFICIENT_EVIDENCE)

    def test_clean_memory_and_context_allow_buy_avoid_wait_and_force_no_action_when_blocked(self):
        self.insert_current_context()
        self.insert_retrieval()
        ev = collect_paper_decision_evidence(self.db_path, self.token_id, self.pair_id)
        self.assertEqual(classify_decision_gate(ev), DecisionGateLabel.DECISION_ALLOWED)
        self.assertEqual(classify_requested_action_from_memory_evidence(ev), PaperDecisionActionLabel.BUY)
        self.assertEqual(classify_final_paper_action(ev), PaperDecisionActionLabel.BUY)
        self.assertTrue(paper_decision_can_open_position_later(build_decision_payload(ev)))

        other_token, other_pair = self.insert_token_pair()
        self.token_id, self.pair_id = other_token, other_pair
        self.insert_current_context()
        self.insert_retrieval(outcome="REALISTIC_CAPITAL_PROTECTION", lesson="ACTION_AVOID_WORKED")
        ev = collect_paper_decision_evidence(self.db_path, self.token_id, self.pair_id)
        self.assertEqual(classify_requested_action_from_memory_evidence(ev), PaperDecisionActionLabel.AVOID)

        other_token, other_pair = self.insert_token_pair()
        self.token_id, self.pair_id = other_token, other_pair
        self.insert_current_context(safety_status_label="SAFETY_CAUTION")
        self.insert_retrieval()
        ev = collect_paper_decision_evidence(self.db_path, self.token_id, self.pair_id)
        self.assertEqual(classify_requested_action_from_memory_evidence(ev), PaperDecisionActionLabel.WAIT)

        other_token, other_pair = self.insert_token_pair()
        self.token_id, self.pair_id = other_token, other_pair
        self.insert_current_context(exit_realism_label="EXIT_UNREALISTIC")
        self.insert_retrieval()
        ev = collect_paper_decision_evidence(self.db_path, self.token_id, self.pair_id)
        self.assertEqual(classify_final_paper_action(ev), PaperDecisionActionLabel.NO_ACTION)

    def test_audit_only_forces_no_action_and_hold_sell_are_labels_only(self):
        self.insert_current_context()
        self.insert_retrieval(evidence_label=MemoryEvidenceLabel.MEMORY_EVIDENCE_MIXED.value)
        ev = collect_paper_decision_evidence(self.db_path, self.token_id, self.pair_id)
        payload = build_decision_payload(ev, requested_action_label=PaperDecisionActionLabel.HOLD)
        self.assertEqual(payload["decision_gate_label"], DecisionGateLabel.DECISION_AUDIT_ONLY.value)
        self.assertEqual(payload["final_action_label"], PaperDecisionActionLabel.NO_ACTION.value)
        self.assertFalse(paper_decision_can_open_position_later(payload))
        payload = build_decision_payload({**ev, "requested_action_label": PaperDecisionActionLabel.SELL.value})
        self.assertEqual(payload["final_action_label"], PaperDecisionActionLabel.NO_ACTION.value)

    def test_recorders_insert_decision_audit_report_and_scheduler_only(self):
        self.insert_current_context()
        self.insert_retrieval()
        ev = collect_paper_decision_evidence(self.db_path, self.token_id, self.pair_id)
        payload = build_decision_payload(ev)
        decision_id = record_paper_decision(self.db_path, payload)
        duplicate_id = record_paper_decision(self.db_path, payload)
        self.assertEqual(decision_id, duplicate_id)
        audit_id = record_paper_decision_audit(self.db_path, decision_id, {"token_id": self.token_id, "pair_id": self.pair_id, "audit_label": "PHASE16_AUDIT"})
        self.assertGreater(audit_id, 0)
        self.assertEqual(self.count_rows("printer_paper_decisions"), 1)
        self.assertEqual(self.count_rows("printer_paper_decision_audits"), 1)
        with self.connect() as connection:
            row = connection.execute("SELECT * FROM printer_paper_decisions WHERE id = ?", (decision_id,)).fetchone()
        report = json.loads(row["decision_report_json"])
        self.assertEqual(report["mode"], "paper_only")
        self.assertFalse(report["live_execution"])
        second_id, second_payload = build_and_record_paper_decision(self.db_path, self.token_id, self.pair_id)
        self.assertGreater(second_id, 0)
        self.assertIn("decision_report", second_payload)
        job_result, job_id = enqueue_paper_decision_job(self.db_path, self.token_id, self.pair_id, self.now + timedelta(minutes=1), reason="phase16_test")
        self.assertEqual(job_result.value, "ACQUIRED")
        self.assertIsNotNone(job_id)
        with self.connect() as connection:
            running = connection.execute("SELECT COUNT(*) FROM printer_scheduler_jobs WHERE status = ?", (JobStatus.RUNNING.value,)).fetchone()[0]
        self.assertEqual(running, 0)
        self.assertEqual(self.count_rows("printer_paper_positions"), 0)
        self.assertEqual(self.count_rows("printer_token_lifecycle_events"), 0)

    def test_no_network_source_runtime_or_forbidden_concepts(self):
        source_text = "\n".join(inspect.getsource(module) for module in (classifier, evidence, gates, recorder, reports))
        for fragment in (
            "requests.get",
            "requests.post",
            "httpx",
            "aiohttp",
            "urllib.request",
            "while True",
            "APScheduler",
            "confidence_score",
            "buy_score",
            "ranking_score",
            "rank_score",
            "score =",
            "confidence =",
            "embedding",
            "vector",
        ):
            self.assertNotIn(fragment, source_text)
        self.assertEqual(self.count_rows("printer_paper_positions"), 0)


if __name__ == "__main__":
    unittest.main()
