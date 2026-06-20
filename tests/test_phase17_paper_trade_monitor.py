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
from printer_v1.paper_monitor import events, evidence, monitor, positions, recorder, reports
from printer_v1.paper_monitor.contracts import (
    PaperEntryStatusLabel,
    PaperExitReasonLabel,
    PaperMonitorQualityLabel,
    PaperMonitorStateLabel,
    PaperPnlStateLabel,
    PaperPositionStatusLabel,
    PaperTradeEventLabel,
)
from printer_v1.paper_monitor.events import build_paper_trade_event_payload, event_has_no_live_execution, event_is_paper_only
from printer_v1.paper_monitor.monitor import build_monitor_update, build_paper_exit_payload, classify_paper_monitor_state
from printer_v1.paper_monitor.positions import (
    calculate_paper_token_amount,
    calculate_realized_pnl,
    calculate_unrealized_pnl,
    classify_entry_status,
    classify_paper_pnl_state,
)
from printer_v1.paper_monitor.recorder import (
    close_paper_position,
    enqueue_paper_monitor_job,
    get_open_paper_positions,
    open_paper_position_from_decision,
    record_paper_trade_audit,
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


class Phase17PaperTradeMonitorTest(unittest.TestCase):
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
            token_id = connection.execute("INSERT INTO printer_tokens (token_mint, chain) VALUES ('monitor-mint', 'solana')").lastrowid
            pair_id = connection.execute(
                "INSERT INTO printer_pairs (token_id, pair_address, dex, pool_source) VALUES (?, 'monitor-pair', 'raydium', 'local')",
                (token_id,),
            ).lastrowid
        return int(token_id), int(pair_id)

    def column_names(self, table):
        with self.connect() as connection:
            return {row[1] for row in connection.execute(f"PRAGMA table_info({table})")}

    def count_rows(self, table):
        with self.connect() as connection:
            return connection.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]

    def insert_decision(self, final_action="BUY", gate="DECISION_ALLOWED", status="PAPER_DECISION_PROPOSED"):
        with self.connect() as connection:
            return int(connection.execute(
                """
                INSERT INTO printer_paper_decisions (
                    token_id, pair_id, token_mint, pair_address, decided_at,
                    requested_action_label, final_action_label, decision_gate_label,
                    memory_evidence_gate_label, paper_decision_status_label,
                    retrieval_query_id, decision_action, decision_status,
                    source_status, data_quality_label
                )
                VALUES (?, ?, 'monitor-mint', 'monitor-pair', ?, 'BUY', ?, ?, 'MEMORY_GATE_CLEAN_MATCH', ?, 1, ?, ?, 'COMPLETE', 'CLEAN_DATA')
                """,
                (self.token_id, self.pair_id, self.now.isoformat(), final_action, gate, status, final_action, status),
            ).lastrowid)

    def insert_snapshot(self, price=1.0, source_status="COMPLETE", data_quality="CLEAN_DATA", when=None):
        with self.connect() as connection:
            connection.execute(
                """
                INSERT INTO printer_token_snapshots (
                    token_id, pair_id, captured_at, tracking_lane, snapshot_mode,
                    price_usd, liquidity_usd, source_status, data_quality_label
                )
                VALUES (?, ?, ?, 'PAPER_MONITORING', 'PAPER_EXIT_PROTECTION_MODE', ?, 50000, ?, ?)
                """,
                (self.token_id, self.pair_id, (when or self.now).isoformat(), price, source_status, data_quality),
            )

    def insert_liquidity(self, route="ROUTE_AVAILABLE", state="LIQUIDITY_USABLE", entry="ENTRY_REALISTIC", exit_label="EXIT_REALISTIC"):
        with self.connect() as connection:
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
                VALUES (?, ?, 'monitor-mint', 'monitor-pair', ?, 1.0, 50000, 100, 100, 1, 'QUOTE_FRESH',
                    'ROUTE_AVAILABLE', ?, ?, ?, 'SLIPPAGE_LOW', 'PRICE_IMPACT_LOW',
                    ?, 'QUOTE_FRESH', 'NO_LIQUIDITY_DRAIN',
                    'LIQUIDITY_EXIT_CONTEXT_CLEAN', 'REALISM_CONTEXT_ACCEPTABLE',
                    'COMPLETE', 'CLEAN_DATA', '{}', '{}')
                """,
                (self.token_id, self.pair_id, self.now.isoformat(), state, entry, exit_label, route),
            )

    def insert_safety(self, safety="SAFETY_CLEAN"):
        with self.connect() as connection:
            connection.execute(
                """
                INSERT INTO printer_safety_rug_snapshots (
                    token_id, pair_id, token_mint, pair_address, captured_at,
                    safety_status_label, rug_risk_label, liquidity_safety_label,
                    authority_label, distribution_label, safety_payload_quality_label,
                    safety_gate_label, source_status, data_quality_label,
                    raw_safety_payload_json, normalized_safety_payload_json
                )
                VALUES (?, ?, 'monitor-mint', 'monitor-pair', ?, ?, 'RUG_RISK_LOW',
                    'LIQUIDITY_SAFE', 'AUTHORITY_RENOUNCED_OR_SAFE',
                    'DISTRIBUTION_HEALTHY', 'SAFETY_CONTEXT_CLEAN',
                    'ALLOW_SAFETY_CONTEXT', 'COMPLETE', 'CLEAN_DATA', '{}', '{}')
                """,
                (self.token_id, self.pair_id, self.now.isoformat(), safety),
            )

    def seed_valid_entry(self):
        self.insert_snapshot(price=1.0)
        self.insert_liquidity()
        self.insert_safety()
        return self.insert_decision()

    def test_paper_decision_package_and_monitor_files_import(self):
        self.assertTrue((SRC_PATH / "printer_v1" / "paper_decision" / "__init__.py").exists())
        for module in (events, evidence, monitor, positions, recorder, reports):
            self.assertTrue(inspect.ismodule(module))

    def test_required_contract_labels_exist(self):
        self.assertIn("PAPER_POSITION_OPEN", {label.value for label in PaperPositionStatusLabel})
        self.assertIn("PAPER_ENTRY_BLOCKED_NO_DECISION", {label.value for label in PaperEntryStatusLabel})
        self.assertIn("MONITOR_EXIT_RISK", {label.value for label in PaperMonitorStateLabel})
        self.assertIn("EXIT_REASON_ROUTE_FAILED", {label.value for label in PaperExitReasonLabel})
        self.assertIn("PNL_REALIZED_PROFIT", {label.value for label in PaperPnlStateLabel})
        self.assertIn("PAPER_EVENT_POSITION_CLOSED", {label.value for label in PaperTradeEventLabel})
        self.assertIn("PAPER_MONITOR_CONTEXT_CLEAN", {label.value for label in PaperMonitorQualityLabel})

    def test_migration_fields_and_forbidden_columns(self):
        self.assertIn("entry_status_label", self.column_names("printer_paper_positions"))
        self.assertIn("paper_trade_event_label", self.column_names("printer_paper_trade_events"))
        self.assertIn("audit_label", self.column_names("printer_paper_trade_audits"))
        for table in ("printer_paper_positions", "printer_paper_trade_events", "printer_paper_trade_audits"):
            self.assertEqual(self.column_names(table) & FORBIDDEN_COLUMNS, set(), table)

    def test_position_entry_rules(self):
        none_id, none_payload = open_paper_position_from_decision(self.db_path, 999, self.now)
        self.assertIsNone(none_id)
        self.assertEqual(none_payload["entry_status_label"], "PAPER_ENTRY_BLOCKED_NO_DECISION")
        self.insert_snapshot()
        self.insert_liquidity()
        self.insert_safety()
        blocked = self.insert_decision(gate="DECISION_BLOCKED_NO_CLEAN_MEMORY", status="PAPER_DECISION_BLOCKED")
        audit = self.insert_decision(status="PAPER_DECISION_AUDIT_ONLY")
        wait = self.insert_decision(final_action="WAIT")
        for decision_id in (blocked, audit, wait):
            position_id, payload = open_paper_position_from_decision(self.db_path, decision_id, self.now)
            self.assertIsNone(position_id)
            self.assertNotEqual(payload["entry_status_label"], "PAPER_ENTRY_ALLOWED")
        buy = self.insert_decision()
        position_id, payload = open_paper_position_from_decision(self.db_path, buy, self.now)
        self.assertIsNotNone(position_id)
        self.assertEqual(payload["paper_size_usd"], 100.0)
        self.assertEqual(payload["paper_position_status_label"], "PAPER_POSITION_OPEN")
        duplicate_id, _ = open_paper_position_from_decision(self.db_path, buy, self.now)
        self.assertEqual(position_id, duplicate_id)

    def test_calculations_are_deterministic(self):
        amount = calculate_paper_token_amount(100.0, 2.0)
        self.assertEqual(amount, 50.0)
        self.assertEqual(calculate_unrealized_pnl(2.0, 3.0, amount), (50.0, 50.0))
        self.assertEqual(calculate_realized_pnl(2.0, 1.0, amount), (-50.0, -50.0))
        self.assertEqual(classify_paper_pnl_state(unrealized_pnl_usd=1).value, "PNL_UNREALIZED_PROFIT")
        self.assertEqual(classify_paper_pnl_state(realized_pnl_usd=-1).value, "PNL_REALIZED_LOSS")

    def test_monitor_detects_profit_loss_drawdown_and_risks(self):
        decision_id = self.seed_valid_entry()
        position_id, _ = open_paper_position_from_decision(self.db_path, decision_id, self.now)
        self.insert_snapshot(price=1.3, when=self.now + timedelta(minutes=1))
        update = recorder.monitor_paper_position(self.db_path, position_id, (self.now + timedelta(minutes=1)).isoformat())
        self.assertEqual(update["paper_monitor_state_label"], "MONITOR_PROFIT_WATCH")
        self.insert_snapshot(price=0.85, when=self.now + timedelta(minutes=2))
        update = recorder.monitor_paper_position(self.db_path, position_id, (self.now + timedelta(minutes=2)).isoformat())
        self.assertEqual(update["paper_monitor_state_label"], "MONITOR_DRAWDOWN_WATCH")
        self.insert_liquidity(route="ROUTE_FAILED")
        evidence_payload = evidence.collect_paper_monitor_evidence(self.db_path, position_id)
        self.assertEqual(classify_paper_monitor_state(evidence_payload["paper_position"], evidence_payload).value, "MONITOR_ROUTE_RISK")
        self.insert_liquidity(state="LIQUIDITY_DRAINING")
        evidence_payload = evidence.collect_paper_monitor_evidence(self.db_path, position_id)
        self.assertIn(classify_paper_monitor_state(evidence_payload["paper_position"], evidence_payload).value, {"MONITOR_ROUTE_RISK", "MONITOR_LIQUIDITY_RISK"})
        self.insert_safety("SAFETY_UNSAFE")
        evidence_payload = evidence.collect_paper_monitor_evidence(self.db_path, position_id)
        self.assertEqual(classify_paper_monitor_state(evidence_payload["paper_position"], evidence_payload).value, "MONITOR_SAFETY_RISK")

    def test_close_events_audit_open_lookup_and_scheduler_only(self):
        decision_id = self.seed_valid_entry()
        position_id, _ = open_paper_position_from_decision(self.db_path, decision_id, self.now)
        self.assertEqual(len(get_open_paper_positions(self.db_path)), 1)
        self.insert_snapshot(price=1.25, when=self.now + timedelta(minutes=3))
        update = build_monitor_update(self.db_path, position_id, (self.now + timedelta(minutes=3)).isoformat())
        with self.connect() as connection:
            position = dict(connection.execute("SELECT * FROM printer_paper_positions WHERE id = ?", (position_id,)).fetchone())
        exit_payload = build_paper_exit_payload(position, update["monitor_evidence"], self.now + timedelta(minutes=3))
        close_paper_position(self.db_path, position_id, exit_payload, self.now + timedelta(minutes=3))
        self.assertEqual(len(get_open_paper_positions(self.db_path)), 0)
        self.assertGreaterEqual(self.count_rows("printer_paper_trade_events"), 2)
        event_payload = build_paper_trade_event_payload(position_id, decision_id, self.token_id, self.pair_id, "audit_recorded", {"paper_monitor_state_label": "MONITOR_CLOSED"})
        self.assertTrue(event_is_paper_only(event_payload))
        self.assertTrue(event_has_no_live_execution(event_payload))
        audit_id = record_paper_trade_audit(self.db_path, {"paper_position_id": position_id, "paper_decision_id": decision_id, "token_id": self.token_id, "pair_id": self.pair_id, "audit_label": "PAPER_EVENT_AUDIT_RECORDED"})
        self.assertGreater(audit_id, 0)
        job_result, job_id = enqueue_paper_monitor_job(self.db_path, position_id, self.now + timedelta(minutes=1), reason="phase17_test")
        self.assertEqual(job_result.value, "ACQUIRED")
        self.assertIsNotNone(job_id)
        with self.connect() as connection:
            running = connection.execute("SELECT COUNT(*) FROM printer_scheduler_jobs WHERE status = ?", (JobStatus.RUNNING.value,)).fetchone()[0]
            lifecycle_events = connection.execute("SELECT COUNT(*) FROM printer_token_lifecycle_events").fetchone()[0]
        self.assertEqual(running, 0)
        self.assertEqual(lifecycle_events, 0)

    def test_reports_and_no_forbidden_runtime_concepts(self):
        decision_id = self.seed_valid_entry()
        position_id, _ = open_paper_position_from_decision(self.db_path, decision_id, self.now)
        with self.connect() as connection:
            position = dict(connection.execute("SELECT * FROM printer_paper_positions WHERE id = ?", (position_id,)).fetchone())
        report = reports.build_paper_position_report(position)
        self.assertTrue(reports.report_is_paper_only(report))
        source_text = "\n".join(inspect.getsource(module) for module in (events, evidence, monitor, positions, recorder, reports))
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


if __name__ == "__main__":
    unittest.main()
