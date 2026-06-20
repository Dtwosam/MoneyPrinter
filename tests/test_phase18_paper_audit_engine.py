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

from printer_v1.db import apply_migrations
from printer_v1.paper_audit import classifier, evidence, recorder, reports
from printer_v1.paper_audit.classifier import (
    classify_paper_audit_result,
    classify_paper_data_quality_audit,
    classify_paper_outcome_review,
    classify_paper_realism,
    classify_paper_rule_compliance,
    collect_paper_audit_issues,
    paper_audit_passes,
    paper_audit_requires_manual_review,
)
from printer_v1.paper_audit.contracts import (
    PaperAuditIssueLabel,
    PaperAuditResultLabel,
    PaperAuditScopeLabel,
    PaperDataQualityAuditLabel,
    PaperOutcomeReviewLabel,
    PaperRealismLabel,
    PaperRuleComplianceLabel,
)
from printer_v1.paper_audit.evidence import (
    collect_decision_audit_evidence,
    collect_local_context_around_entry,
    collect_local_context_around_exit,
    collect_monitoring_events_for_position,
    collect_paper_audit_evidence,
    collect_position_audit_evidence,
)
from printer_v1.paper_audit.recorder import (
    build_and_record_paper_audit,
    enqueue_paper_audit_job,
    get_latest_paper_audit,
    get_paper_audits_for_position,
    record_paper_audit_report,
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


class Phase18PaperAuditEngineTest(unittest.TestCase):
    def setUp(self):
        self.tempdir = tempfile.TemporaryDirectory()
        self.db_path = pathlib.Path(self.tempdir.name) / "printer.sqlite3"
        apply_migrations(self.db_path)
        self.now = datetime(2026, 6, 19, 12, 0, tzinfo=timezone.utc)
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
        with self.connect() as connection:
            token_id = connection.execute(
                "INSERT INTO printer_tokens (token_mint, chain) VALUES ('audit-mint', 'solana')"
            ).lastrowid
            pair_id = connection.execute(
                "INSERT INTO printer_pairs (token_id, pair_address, dex, pool_source) VALUES (?, 'audit-pair', 'raydium', 'local')",
                (token_id,),
            ).lastrowid
        return int(token_id), int(pair_id)

    def column_names(self, table):
        with self.connect() as connection:
            return {row[1] for row in connection.execute(f"PRAGMA table_info({table})")}

    def count_rows(self, table):
        with self.connect() as connection:
            return connection.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]

    def insert_decision(self, final_action="BUY", gate="DECISION_ALLOWED", status="PAPER_DECISION_PROPOSED", memory_gate="MEMORY_GATE_CLEAN_MATCH"):
        with self.connect() as connection:
            return int(
                connection.execute(
                    """
                    INSERT INTO printer_paper_decisions (
                        token_id, pair_id, token_mint, pair_address, decided_at,
                        requested_action_label, final_action_label, decision_gate_label,
                        memory_evidence_gate_label, paper_decision_status_label,
                        retrieval_query_id, decision_action, decision_status,
                        source_status, data_quality_label
                    )
                    VALUES (?, ?, 'audit-mint', 'audit-pair', ?, 'BUY', ?, ?, ?, ?, 1, ?, ?, 'COMPLETE', 'CLEAN_DATA')
                    """,
                    (self.token_id, self.pair_id, self.now.isoformat(), final_action, gate, memory_gate, status, final_action, status),
                ).lastrowid
            )

    def insert_position(self, decision_id=None, *, final_price=1.25, status="PAPER_POSITION_CLOSED", closed=True, realized=None):
        realized_value = 25.0 if realized is None else realized
        closed_at = (self.now + timedelta(minutes=10)).isoformat() if closed else None
        with self.connect() as connection:
            return int(
                connection.execute(
                    """
                    INSERT INTO printer_paper_positions (
                        paper_decision_id, retrieval_query_id, token_id, pair_id, token_mint, pair_address,
                        position_status, opened_at, closed_at, paper_entry_price, paper_exit_price,
                        paper_size_usd, paper_pnl_usd, paper_pnl_percent, entry_price_usd,
                        exit_price_usd, paper_token_amount, current_price_usd, unrealized_pnl_usd,
                        unrealized_pnl_percent, realized_pnl_usd, realized_pnl_percent,
                        max_runup_percent, max_drawdown_percent, entry_status_label,
                        paper_position_status_label, paper_monitor_state_label,
                        paper_exit_reason_label, paper_pnl_state_label
                    )
                    VALUES (?, 1, ?, ?, 'audit-mint', 'audit-pair', ?, ?, ?, 1.0, ?, 100.0,
                        ?, ?, 1.0, ?, 100.0, ?, 0.0, 0.0, ?, ?, 25.0, 5.0,
                        'PAPER_ENTRY_ALLOWED', ?, 'MONITOR_CLOSED',
                        'EXIT_REASON_TARGET_REACHED', 'PNL_REALIZED_PROFIT')
                    """,
                    (
                        decision_id,
                        self.token_id,
                        self.pair_id,
                        status,
                        self.now.isoformat(),
                        closed_at,
                        final_price,
                        realized_value,
                        realized_value,
                        final_price,
                        final_price,
                        realized_value,
                        realized_value,
                        status,
                    ),
                ).lastrowid
            )

    def insert_event(self, position_id, decision_id, minutes, label="PAPER_EVENT_SNAPSHOT_MONITORED"):
        with self.connect() as connection:
            connection.execute(
                """
                INSERT INTO printer_paper_trade_events (
                    paper_position_id, paper_decision_id, token_id, pair_id, event_kind,
                    event_at, paper_trade_event_label, paper_monitor_state_label,
                    paper_exit_reason_label, paper_pnl_state_label, event_payload_json,
                    source_status, data_quality_label
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, 'MONITOR_HEALTHY',
                    'EXIT_REASON_NO_EXIT', 'PNL_UNREALIZED_PROFIT', '{}',
                    'COMPLETE', 'CLEAN_DATA')
                """,
                (position_id, decision_id, self.token_id, self.pair_id, label, (self.now + timedelta(minutes=minutes)).isoformat(), label),
            )

    def insert_context(
        self,
        *,
        when=None,
        source_status="COMPLETE",
        data_quality="CLEAN_DATA",
        safety="SAFETY_CLEAN",
        entry="ENTRY_REALISTIC",
        exit_label="EXIT_REALISTIC",
        route="ROUTE_AVAILABLE",
        liquidity="LIQUIDITY_USABLE",
    ):
        captured_at = (when or self.now).isoformat()
        with self.connect() as connection:
            connection.execute(
                """
                INSERT INTO printer_token_snapshots (
                    token_id, pair_id, captured_at, tracking_lane, snapshot_mode,
                    price_usd, liquidity_usd, source_status, data_quality_label
                )
                VALUES (?, ?, ?, 'PAPER_MONITORING', 'PAPER_EXIT_PROTECTION_MODE', 1.0, 50000, ?, ?)
                """,
                (self.token_id, self.pair_id, captured_at, source_status, data_quality),
            )
            connection.execute(
                """
                INSERT INTO printer_liquidity_exit_snapshots (
                    token_id, pair_id, token_mint, pair_address, captured_at,
                    price_usd, liquidity_usd, expected_entry_size_usd,
                    expected_exit_size_usd, route_available, quote_status,
                    route_status, liquidity_state_label, entry_realism_label,
                    exit_realism_label, slippage_label, price_impact_label,
                    route_label, quote_age_label, liquidity_drain_label,
                    liquidity_exit_payload_quality_label, realism_gate_label,
                    source_status, data_quality_label, raw_liquidity_exit_payload_json,
                    normalized_liquidity_exit_payload_json
                )
                VALUES (?, ?, 'audit-mint', 'audit-pair', ?, 1.0, 50000, 100, 100, 1, 'QUOTE_FRESH',
                    'ROUTE_AVAILABLE', ?, ?, ?, 'SLIPPAGE_LOW', 'PRICE_IMPACT_LOW',
                    ?, 'QUOTE_FRESH', 'NO_LIQUIDITY_DRAIN',
                    'LIQUIDITY_EXIT_CONTEXT_CLEAN', 'REALISM_CONTEXT_ACCEPTABLE',
                    ?, ?, '{}', '{}')
                """,
                (self.token_id, self.pair_id, captured_at, liquidity, entry, exit_label, route, source_status, data_quality),
            )
            connection.execute(
                """
                INSERT INTO printer_safety_rug_snapshots (
                    token_id, pair_id, token_mint, pair_address, captured_at,
                    safety_status_label, rug_risk_label, liquidity_safety_label,
                    authority_label, distribution_label, safety_payload_quality_label,
                    safety_gate_label, source_status, data_quality_label,
                    raw_safety_payload_json, normalized_safety_payload_json
                )
                VALUES (?, ?, 'audit-mint', 'audit-pair', ?, ?, 'RUG_RISK_LOW',
                    'LIQUIDITY_SAFE', 'AUTHORITY_RENOUNCED_OR_SAFE',
                    'DISTRIBUTION_HEALTHY', 'SAFETY_CONTEXT_CLEAN',
                    'ALLOW_SAFETY_CONTEXT', ?, ?, '{}', '{}')
                """,
                (self.token_id, self.pair_id, captured_at, safety, source_status, data_quality),
            )

    def seed_clean_trade(self):
        decision_id = self.insert_decision()
        self.insert_context(when=self.now)
        self.insert_context(when=self.now + timedelta(minutes=10))
        position_id = self.insert_position(decision_id)
        self.insert_event(position_id, decision_id, 1, "PAPER_EVENT_POSITION_OPENED")
        self.insert_event(position_id, decision_id, 10, "PAPER_EVENT_POSITION_CLOSED")
        return decision_id, position_id

    def test_paper_monitor_package_and_audit_files_import(self):
        self.assertTrue((SRC_PATH / "printer_v1" / "paper_monitor" / "__init__.py").exists())
        for module in (classifier, evidence, recorder, reports):
            self.assertTrue(inspect.ismodule(module))

    def test_required_contract_labels_exist(self):
        self.assertIn("AUDIT_FULL_PAPER_TRADE", {label.value for label in PaperAuditScopeLabel})
        self.assertIn("PAPER_AUDIT_FAIL", {label.value for label in PaperAuditResultLabel})
        self.assertIn("RULES_VIOLATION", {label.value for label in PaperRuleComplianceLabel})
        self.assertIn("PAPER_REALISM_UNREALISTIC", {label.value for label in PaperRealismLabel})
        self.assertIn("PAPER_OUTCOME_PROTECTED_CAPITAL", {label.value for label in PaperOutcomeReviewLabel})
        self.assertIn("PAPER_AUDIT_DATA_CONFLICTING", {label.value for label in PaperDataQualityAuditLabel})
        self.assertIn("ISSUE_POSITION_WITHOUT_DECISION", {label.value for label in PaperAuditIssueLabel})

    def test_migration_table_fields_and_forbidden_columns(self):
        columns = self.column_names("printer_paper_audit_reports")
        for expected in {
            "paper_position_id",
            "paper_decision_id",
            "audit_scope_label",
            "paper_audit_result_label",
            "paper_rule_compliance_label",
            "paper_realism_label",
            "paper_outcome_review_label",
            "paper_data_quality_audit_label",
            "audit_report_json",
        }:
            self.assertIn(expected, columns)
        self.assertEqual(columns & FORBIDDEN_COLUMNS, set())

    def test_evidence_collection_reads_local_rows(self):
        decision_id, position_id = self.seed_clean_trade()
        self.assertEqual(collect_decision_audit_evidence(self.db_path, decision_id)["id"], decision_id)
        self.assertEqual(collect_position_audit_evidence(self.db_path, position_id)["id"], position_id)
        self.assertEqual(len(collect_monitoring_events_for_position(self.db_path, position_id)), 2)
        self.assertTrue(collect_local_context_around_entry(self.db_path, self.token_id, self.pair_id, self.now.isoformat())["token_snapshot"])
        self.assertTrue(collect_local_context_around_exit(self.db_path, self.token_id, self.pair_id, (self.now + timedelta(minutes=10)).isoformat())["liquidity_exit"])

    def test_rule_violations_for_invalid_decision_links(self):
        self.insert_context()
        position_without_decision = self.insert_position(999999)
        ev = collect_paper_audit_evidence(self.db_path, paper_position_id=position_without_decision)
        self.assertIn("ISSUE_POSITION_WITHOUT_DECISION", collect_paper_audit_issues(ev))
        self.assertEqual(classify_paper_rule_compliance(ev), PaperRuleComplianceLabel.RULES_VIOLATION)

        for kwargs in (
            {"gate": "DECISION_BLOCKED_NO_CLEAN_MEMORY", "status": "PAPER_DECISION_BLOCKED"},
            {"status": "PAPER_DECISION_AUDIT_ONLY"},
            {"final_action": "WAIT"},
            {"memory_gate": "MEMORY_GATE_NO_MATCH"},
        ):
            decision_id = self.insert_decision(**kwargs)
            position_id = self.insert_position(decision_id)
            self.insert_event(position_id, decision_id, 1)
            self.insert_event(position_id, decision_id, 2)
            ev = collect_paper_audit_evidence(self.db_path, paper_position_id=position_id)
            self.assertEqual(classify_paper_rule_compliance(ev), PaperRuleComplianceLabel.RULES_VIOLATION)

    def test_data_realism_monitoring_close_and_pnl_classification(self):
        decision_id = self.insert_decision()
        self.insert_context(source_status="STALE", data_quality="STALE_DATA")
        position_id = self.insert_position(decision_id)
        ev = collect_paper_audit_evidence(self.db_path, paper_position_id=position_id)
        self.assertIn("ISSUE_STALE_ENTRY_CONTEXT", collect_paper_audit_issues(ev))
        self.assertEqual(classify_paper_data_quality_audit(ev), PaperDataQualityAuditLabel.PAPER_AUDIT_DATA_STALE)

        self.insert_context(safety="SAFETY_UNSAFE", entry="ENTRY_UNREALISTIC", exit_label="EXIT_UNREALISTIC", route="ROUTE_FAILED", liquidity="LIQUIDITY_DRAINING")
        ev = collect_paper_audit_evidence(self.db_path, paper_position_id=position_id)
        issues = set(collect_paper_audit_issues(ev))
        self.assertIn("ISSUE_UNSAFE_CONTEXT_IGNORED", issues)
        self.assertIn("ISSUE_UNREALISTIC_ENTRY", issues)
        self.assertIn("ISSUE_UNREALISTIC_EXIT", issues)
        self.assertIn("ISSUE_ROUTE_RISK_IGNORED", issues)
        self.assertIn("ISSUE_LIQUIDITY_RISK_IGNORED", issues)
        self.assertEqual(classify_paper_realism(ev), PaperRealismLabel.PAPER_REALISM_UNREALISTIC)
        self.assertEqual(classify_paper_audit_result(ev), PaperAuditResultLabel.PAPER_AUDIT_FAIL)

        self.insert_context()
        incomplete_position = self.insert_position(self.insert_decision(), closed=True)
        ev = collect_paper_audit_evidence(self.db_path, paper_position_id=incomplete_position)
        self.assertIn("ISSUE_MONITORING_GAP", collect_paper_audit_issues(ev))
        self.assertEqual(classify_paper_rule_compliance(ev), PaperRuleComplianceLabel.RULES_INCOMPLETE_EVIDENCE)

        self.insert_context()
        missing_close = self.insert_position(self.insert_decision(), status="PAPER_POSITION_CLOSED", closed=False)
        ev = collect_paper_audit_evidence(self.db_path, paper_position_id=missing_close)
        self.assertIn("ISSUE_MISSING_CLOSE_EVIDENCE", collect_paper_audit_issues(ev))

        self.insert_context()
        bad_pnl = self.insert_position(self.insert_decision(), realized=999.0)
        ev = collect_paper_audit_evidence(self.db_path, paper_position_id=bad_pnl)
        self.assertIn("ISSUE_PNL_INCONSISTENT", collect_paper_audit_issues(ev))
        self.assertEqual(classify_paper_rule_compliance(ev), PaperRuleComplianceLabel.RULES_VIOLATION)

    def test_clean_trade_passes_and_inconclusive_data_is_audit_path(self):
        _, position_id = self.seed_clean_trade()
        ev = collect_paper_audit_evidence(self.db_path, paper_position_id=position_id)
        self.assertEqual(collect_paper_audit_issues(ev), ["ISSUE_NONE"])
        self.assertEqual(classify_paper_rule_compliance(ev), PaperRuleComplianceLabel.RULES_COMPLIANT)
        self.assertEqual(classify_paper_realism(ev), PaperRealismLabel.PAPER_REALISM_CLEAN)
        self.assertEqual(classify_paper_outcome_review(ev), PaperOutcomeReviewLabel.PAPER_OUTCOME_WORKED)
        self.assertEqual(classify_paper_audit_result(ev), PaperAuditResultLabel.PAPER_AUDIT_PASS)
        self.assertTrue(paper_audit_passes(ev))
        self.assertFalse(paper_audit_requires_manual_review(ev))

        empty = collect_paper_audit_evidence(self.db_path, paper_position_id=None, paper_decision_id=None)
        self.assertEqual(classify_paper_data_quality_audit(empty), PaperDataQualityAuditLabel.PAPER_AUDIT_DATA_MISSING)
        self.assertEqual(classify_paper_audit_result(empty), PaperAuditResultLabel.PAPER_AUDIT_FAIL)

    def test_report_recorder_lookup_scheduler_and_no_mutations(self):
        decision_id, position_id = self.seed_clean_trade()
        before = {
            "decisions": self.count_rows("printer_paper_decisions"),
            "positions": self.count_rows("printer_paper_positions"),
            "memory": self.count_rows("printer_memory_windows"),
            "retrieval": self.count_rows("printer_memory_retrieval_queries"),
            "lifecycle": self.count_rows("printer_token_lifecycle_events"),
        }
        audit_id, payload = build_and_record_paper_audit(self.db_path, paper_position_id=position_id)
        self.assertGreater(audit_id, 0)
        report = payload["audit_report"]
        self.assertTrue(reports.report_is_paper_audit_only(report))
        duplicate = record_paper_audit_report(self.db_path, payload)
        self.assertEqual(audit_id, duplicate)
        self.assertEqual(get_latest_paper_audit(self.db_path, paper_position_id=position_id)["id"], audit_id)
        self.assertEqual(len(get_paper_audits_for_position(self.db_path, position_id)), 1)
        job_result, job_id = enqueue_paper_audit_job(self.db_path, position_id, decision_id, self.now + timedelta(minutes=1), "phase18_test")
        self.assertEqual(job_result.value, "ACQUIRED")
        self.assertIsNotNone(job_id)
        with self.connect() as connection:
            running = connection.execute("SELECT COUNT(*) FROM printer_scheduler_jobs WHERE status = ?", (JobStatus.RUNNING.value,)).fetchone()[0]
            stored_report = json.loads(connection.execute("SELECT audit_report_json FROM printer_paper_audit_reports WHERE id = ?", (audit_id,)).fetchone()[0])
        self.assertEqual(running, 0)
        self.assertTrue(stored_report["live_execution"] is False)
        self.assertEqual(before["decisions"], self.count_rows("printer_paper_decisions"))
        self.assertEqual(before["positions"], self.count_rows("printer_paper_positions"))
        self.assertEqual(before["memory"], self.count_rows("printer_memory_windows"))
        self.assertEqual(before["retrieval"], self.count_rows("printer_memory_retrieval_queries"))
        self.assertEqual(before["lifecycle"], self.count_rows("printer_token_lifecycle_events"))

    def test_no_live_network_runtime_or_forbidden_concepts(self):
        source_text = "\n".join(inspect.getsource(module) for module in (classifier, evidence, recorder, reports))
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
        self.assertEqual(self.count_rows("printer_paper_decisions"), 0)
        self.assertEqual(self.count_rows("printer_paper_positions"), 0)


if __name__ == "__main__":
    unittest.main()
