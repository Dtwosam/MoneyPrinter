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
from printer_v1.operator_db import status as operator_db_status
from printer_v1.operator_review import evidence, exports, recorder, reports, summaries
from printer_v1.operator_review.contracts import (
    OperatorAttentionLabel,
    OperatorReviewLabel,
    ReportFormatLabel,
    ReportScopeLabel,
    ReportStatusLabel,
)
from printer_v1.operator_review.evidence import (
    collect_db_state_evidence,
    collect_full_operator_review_evidence,
    collect_lifecycle_queue_evidence,
    collect_paper_audit_evidence,
    collect_paper_decision_evidence,
    collect_paper_position_evidence,
    collect_scheduler_health_evidence,
    collect_source_health_evidence,
    collect_system_health_evidence,
    collect_token_snapshot_evidence,
)
from printer_v1.operator_review.recorder import (
    build_and_record_operator_review_report,
    enqueue_operator_review_job,
    get_latest_operator_review_report,
    get_operator_review_reports,
    record_operator_review_items,
    record_operator_review_report,
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


class Phase19ReportingOperatorReviewTest(unittest.TestCase):
    def setUp(self):
        self.tempdir = tempfile.TemporaryDirectory()
        self.db_path = pathlib.Path(self.tempdir.name) / "printer.sqlite3"
        apply_migrations(self.db_path)
        self.now = datetime(2026, 6, 20, 12, 0, tzinfo=timezone.utc)
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
            token_id = connection.execute("INSERT INTO printer_tokens (token_mint, chain) VALUES ('operator-mint', 'solana')").lastrowid
            pair_id = connection.execute(
                "INSERT INTO printer_pairs (token_id, pair_address, dex, pool_source) VALUES (?, 'operator-pair', 'raydium', 'local')",
                (token_id,),
            ).lastrowid
        return int(token_id), int(pair_id)

    def column_names(self, table):
        with self.connect() as connection:
            return {row[1] for row in connection.execute(f"PRAGMA table_info({table})")}

    def count_rows(self, table):
        with self.connect() as connection:
            return connection.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]

    def insert_local_review_data(self):
        with self.connect() as connection:
            connection.execute(
                """
                INSERT INTO printer_source_failures (
                    source_name, request_kind, failed_at, failure_type,
                    source_status, data_quality_label
                )
                VALUES ('local_source', 'review', ?, 'local_failure', 'FAILED', 'DIRTY_DATA')
                """,
                (self.now.isoformat(),),
            )
            connection.execute(
                """
                INSERT INTO printer_scheduler_jobs (job_name, job_kind, priority, status, scheduled_for)
                VALUES ('operator-review-pending', 'BACKUP_SOURCE_CHECK', 10, 'PENDING', ?)
                """,
                (self.now.isoformat(),),
            )
            connection.execute(
                """
                INSERT INTO printer_tracking_queue (
                    token_id, pair_id, tracking_lane, tracking_action,
                    source_status, data_quality_label, queue_status
                )
                VALUES (?, ?, 'TRACK_NORMAL', 'WATCH_ONLY', 'COMPLETE', 'CLEAN_DATA', 'PENDING')
                """,
                (self.token_id, self.pair_id),
            )
            connection.execute(
                """
                INSERT INTO printer_token_snapshots (
                    token_id, pair_id, captured_at, tracking_lane, snapshot_mode,
                    price_usd, liquidity_usd, source_status, data_quality_label
                )
                VALUES (?, ?, ?, 'TRACK_NORMAL', 'NORMAL_SNAPSHOT', 1.0, 10000, 'STALE', 'STALE_DATA')
                """,
                (self.token_id, self.pair_id, (self.now - timedelta(minutes=30)).isoformat()),
            )
            connection.execute(
                """
                INSERT INTO printer_memory_windows (
                    token_id, pair_id, window_kind, opened_at, memory_status,
                    data_quality_label, window_status, memory_quality_label
                )
                VALUES (?, ?, 'WINDOW_15M', ?, 'DIRTY_MEMORY', 'DIRTY_DATA', 'WINDOW_BROKEN', 'DIRTY_MEMORY')
                """,
                (self.token_id, self.pair_id, self.now.isoformat()),
            )
            connection.execute(
                """
                INSERT INTO printer_paper_decisions (
                    token_id, pair_id, token_mint, pair_address, decided_at,
                    requested_action_label, final_action_label, decision_gate_label,
                    memory_evidence_gate_label, paper_decision_status_label,
                    decision_action, decision_status, source_status, data_quality_label
                )
                VALUES (?, ?, 'operator-mint', 'operator-pair', ?, 'BUY', 'NO_ACTION',
                    'DECISION_BLOCKED_NO_CLEAN_MEMORY', 'MEMORY_GATE_NO_MATCH',
                    'PAPER_DECISION_BLOCKED', 'NO_ACTION', 'PAPER_DECISION_BLOCKED',
                    'COMPLETE', 'CLEAN_DATA')
                """,
                (self.token_id, self.pair_id, self.now.isoformat()),
            )
            decision_id = connection.execute("SELECT id FROM printer_paper_decisions ORDER BY id DESC LIMIT 1").fetchone()[0]
            connection.execute(
                """
                INSERT INTO printer_paper_positions (
                    paper_decision_id, token_id, pair_id, position_status, opened_at,
                    paper_entry_price, paper_size_usd, entry_status_label,
                    paper_position_status_label, paper_monitor_state_label,
                    paper_exit_reason_label, paper_pnl_state_label
                )
                VALUES (?, ?, ?, 'PAPER_POSITION_OPEN', ?, 1.0, 100.0,
                    'PAPER_ENTRY_ALLOWED', 'PAPER_POSITION_OPEN',
                    'MONITOR_EXIT_RISK', 'EXIT_REASON_NO_EXIT', 'PNL_UNREALIZED_LOSS')
                """,
                (decision_id, self.token_id, self.pair_id, self.now.isoformat()),
            )
            position_id = connection.execute("SELECT id FROM printer_paper_positions ORDER BY id DESC LIMIT 1").fetchone()[0]
            connection.execute(
                """
                INSERT INTO printer_paper_audit_reports (
                    paper_position_id, paper_decision_id, token_id, pair_id,
                    audit_at, audit_scope_label, paper_audit_result_label,
                    paper_rule_compliance_label, paper_realism_label,
                    paper_outcome_review_label, paper_data_quality_audit_label
                )
                VALUES (?, ?, ?, ?, ?, 'AUDIT_FULL_PAPER_TRADE', 'PAPER_AUDIT_FAIL',
                    'RULES_VIOLATION', 'PAPER_REALISM_UNREALISTIC',
                    'PAPER_OUTCOME_FAILED', 'PAPER_AUDIT_DATA_CLEAN')
                """,
                (position_id, decision_id, self.token_id, self.pair_id, self.now.isoformat()),
            )

    def test_operator_db_and_paper_audit_packages_exist_and_imports_work(self):
        self.assertTrue((SRC_PATH / "printer_v1" / "operator_db" / "__init__.py").exists())
        self.assertTrue((SRC_PATH / "printer_v1" / "paper_audit" / "__init__.py").exists())
        for module in (evidence, exports, recorder, reports, summaries):
            self.assertTrue(inspect.ismodule(module))

    def test_required_contract_labels_exist(self):
        self.assertIn("REPORT_FULL_OPERATOR_REVIEW", {label.value for label in ReportScopeLabel})
        self.assertIn("REPORT_SCHEMA_ONLY", {label.value for label in ReportStatusLabel})
        self.assertIn("OPERATOR_REVIEW_NEEDS_ATTENTION", {label.value for label in OperatorReviewLabel})
        self.assertIn("ATTENTION_PAPER_AUDIT_FAILURE", {label.value for label in OperatorAttentionLabel})
        self.assertEqual({label.value for label in ReportFormatLabel}, {"REPORT_FORMAT_JSON", "REPORT_FORMAT_MARKDOWN", "REPORT_FORMAT_TEXT"})

    def test_migration_tables_and_forbidden_columns(self):
        self.assertIn("report_scope_label", self.column_names("printer_operator_review_reports"))
        self.assertIn("attention_label", self.column_names("printer_operator_review_items"))
        for table in ("printer_operator_review_reports", "printer_operator_review_items"):
            self.assertEqual(self.column_names(table) & FORBIDDEN_COLUMNS, set(), table)

    def test_no_db_and_schema_only_reports(self):
        missing = pathlib.Path(self.tempdir.name) / "missing.sqlite3"
        no_db_evidence = collect_db_state_evidence(missing)
        no_db_report = reports.build_db_state_report(no_db_evidence, self.now)
        self.assertEqual(no_db_evidence["state_classification"], "NO_PERSISTENT_DB_FOUND")
        self.assertEqual(no_db_report["report_status_label"], "REPORT_NO_DB")
        self.assertEqual(no_db_report["operator_review_label"], "OPERATOR_REVIEW_NO_DB")
        schema_db = pathlib.Path(self.tempdir.name) / "schema.sqlite3"
        apply_migrations(schema_db)
        schema_evidence = collect_db_state_evidence(schema_db)
        schema_report = reports.build_db_state_report(schema_evidence, self.now)
        self.assertEqual(schema_evidence["state_classification"], "PERSISTENT_DB_EMPTY_SCHEMA_ONLY")
        self.assertEqual(schema_report["report_status_label"], "REPORT_SCHEMA_ONLY")
        self.assertEqual(schema_report["operator_review_label"], "OPERATOR_REVIEW_SCHEMA_ONLY")

    def test_local_summaries_and_attention_labels(self):
        self.insert_local_review_data()
        system_summary = summaries.summarize_system_health(collect_system_health_evidence(self.db_path))
        source_summary = summaries.summarize_source_health(collect_source_health_evidence(self.db_path))
        scheduler_summary = summaries.summarize_scheduler_health(collect_scheduler_health_evidence(self.db_path))
        lifecycle_summary = summaries.summarize_lifecycle_queue(collect_lifecycle_queue_evidence(self.db_path))
        snapshot_summary = summaries.summarize_token_snapshots(collect_token_snapshot_evidence(self.db_path, token_id=self.token_id, pair_id=self.pair_id))
        memory_summary = summaries.summarize_memory(evidence.collect_memory_evidence(self.db_path, token_id=self.token_id, pair_id=self.pair_id))
        decision_summary = summaries.summarize_paper_decisions(collect_paper_decision_evidence(self.db_path, token_id=self.token_id, pair_id=self.pair_id))
        position_summary = summaries.summarize_paper_positions(collect_paper_position_evidence(self.db_path, token_id=self.token_id, pair_id=self.pair_id))
        audit_summary = summaries.summarize_paper_audits(collect_paper_audit_evidence(self.db_path, token_id=self.token_id, pair_id=self.pair_id))
        self.assertGreaterEqual(system_summary["token_snapshot_count"], 1)
        self.assertEqual(source_summary["failure_count"], 1)
        self.assertEqual(scheduler_summary["pending_jobs"], 1)
        self.assertEqual(lifecycle_summary["queue_item_count"], 1)
        self.assertEqual(snapshot_summary["stale_snapshot_count"], 1)
        self.assertEqual(memory_summary["dirty_memory_count"], 1)
        self.assertEqual(decision_summary["blocked_decision_count"], 1)
        self.assertEqual(position_summary["open_position_count"], 1)
        self.assertEqual(position_summary["exit_risk_count"], 1)
        self.assertEqual(audit_summary["audit_failure_count"], 1)
        self.assertIn("ATTENTION_STALE_SNAPSHOTS", summaries.collect_attention_labels(snapshot_summary))
        self.assertIn("ATTENTION_DIRTY_MEMORY", summaries.collect_attention_labels(memory_summary))
        self.assertIn("ATTENTION_BLOCKED_PAPER_DECISIONS", summaries.collect_attention_labels(decision_summary))
        self.assertIn("ATTENTION_OPEN_PAPER_POSITION", summaries.collect_attention_labels(position_summary))
        self.assertIn("ATTENTION_PAPER_AUDIT_FAILURE", summaries.collect_attention_labels(audit_summary))
        self.assertEqual(summaries.classify_report_status(source_summary), ReportStatusLabel.REPORT_PARTIAL)
        self.assertEqual(summaries.classify_operator_review(position_summary), OperatorReviewLabel.OPERATOR_REVIEW_NEEDS_ATTENTION)

    def test_full_review_report_and_exports(self):
        self.insert_local_review_data()
        full_evidence = collect_full_operator_review_evidence(self.db_path, token_id=self.token_id, pair_id=self.pair_id)
        full_summary = summaries.summarize_full_operator_review(full_evidence)
        self.assertIn("paper_positions", full_summary["sections"])
        report = reports.build_full_operator_review_report(full_evidence, token_id=self.token_id, pair_id=self.pair_id, now=self.now)
        self.assertTrue(reports.report_payload_is_review_only(report))
        self.assertIn("ATTENTION_PAPER_EXIT_RISK", report["attention_labels"])
        self.assertIsInstance(exports.export_report_as_json_payload(report), dict)
        self.assertIn("# Full Operator Review", exports.export_report_as_markdown_text(report))
        self.assertIn("Paper-only", exports.export_report_as_plain_text(report))
        self.assertEqual(exports.validate_report_format("REPORT_FORMAT_TEXT"), ReportFormatLabel.REPORT_FORMAT_TEXT)

    def test_report_status_empty_and_ready(self):
        snapshot_evidence = collect_token_snapshot_evidence(self.db_path, token_id=self.token_id, pair_id=self.pair_id)
        snapshot_summary = summaries.summarize_token_snapshots(snapshot_evidence)
        self.assertEqual(summaries.classify_report_status(snapshot_summary), ReportStatusLabel.REPORT_EMPTY)
        with self.connect() as connection:
            connection.execute(
                """
                INSERT INTO printer_source_requests (
                    source_name, request_kind, requested_at, source_status, data_quality_label
                )
                VALUES ('local_source', 'review', ?, 'COMPLETE', 'CLEAN_DATA')
                """,
                (self.now.isoformat(),),
            )
        source_summary = summaries.summarize_source_health(collect_source_health_evidence(self.db_path))
        self.assertEqual(summaries.classify_report_status(source_summary), ReportStatusLabel.REPORT_READY)

    def test_record_reports_items_lookup_duplicates_and_enqueue_only(self):
        self.insert_local_review_data()
        before = {
            "decisions": self.count_rows("printer_paper_decisions"),
            "positions": self.count_rows("printer_paper_positions"),
            "memory": self.count_rows("printer_memory_windows"),
            "retrieval": self.count_rows("printer_memory_retrieval_queries"),
            "lifecycle": self.count_rows("printer_token_lifecycle_events"),
        }
        report_id, payload = build_and_record_operator_review_report(
            self.db_path,
            ReportScopeLabel.REPORT_FULL_OPERATOR_REVIEW,
            token_id=self.token_id,
            pair_id=self.pair_id,
            report_format_label=ReportFormatLabel.REPORT_FORMAT_MARKDOWN,
            now=self.now,
        )
        self.assertGreater(report_id, 0)
        duplicate_id = record_operator_review_report(self.db_path, payload)
        self.assertEqual(report_id, duplicate_id)
        record_operator_review_items(self.db_path, report_id, payload["items"])
        self.assertEqual(get_latest_operator_review_report(self.db_path, ReportScopeLabel.REPORT_FULL_OPERATOR_REVIEW)["id"], report_id)
        self.assertGreaterEqual(len(get_operator_review_reports(self.db_path, ReportScopeLabel.REPORT_FULL_OPERATOR_REVIEW)), 1)
        result, job_id = enqueue_operator_review_job(self.db_path, ReportScopeLabel.REPORT_SYSTEM_HEALTH, self.now + timedelta(minutes=5), reason="phase19_test")
        self.assertEqual(result.value, "ACQUIRED")
        self.assertIsNotNone(job_id)
        with self.connect() as connection:
            running = connection.execute("SELECT COUNT(*) FROM printer_scheduler_jobs WHERE status = ?", (JobStatus.RUNNING.value,)).fetchone()[0]
        self.assertEqual(running, 0)
        self.assertEqual(before["decisions"], self.count_rows("printer_paper_decisions"))
        self.assertEqual(before["positions"], self.count_rows("printer_paper_positions"))
        self.assertEqual(before["memory"], self.count_rows("printer_memory_windows"))
        self.assertEqual(before["retrieval"], self.count_rows("printer_memory_retrieval_queries"))
        self.assertEqual(before["lifecycle"], self.count_rows("printer_token_lifecycle_events"))

    def test_no_project_db_runtime_network_or_forbidden_capabilities(self):
        self.assertFalse((PROJECT_ROOT / "data" / "printer_v1.sqlite3").exists())
        source_text = "\n".join(inspect.getsource(module) for module in (evidence, exports, recorder, reports, summaries))
        for fragment in (
            "requests.get",
            "requests.post",
            "httpx",
            "aiohttp",
            "urllib.request",
            "claim_due_job",
            "complete_job",
            "while True",
            "APScheduler",
            "FastAPI",
            "Flask",
            "Django",
            "React",
            "Vue",
            "Svelte",
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
        self.assertFalse(operator_db_status.runtime_has_started(self.db_path))


if __name__ == "__main__":
    unittest.main()
