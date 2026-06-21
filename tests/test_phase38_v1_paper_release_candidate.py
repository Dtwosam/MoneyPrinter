import pathlib
import sqlite3
import sys
import tomllib
import unittest

PROJECT_ROOT = pathlib.Path(__file__).resolve().parents[1]
SRC_PATH = PROJECT_ROOT / "src"
sys.path.insert(0, str(SRC_PATH))

from printer_v1.operator_cli.commands import (
    build_long_paper_validation_payload,
    build_v1_paper_rc_payload,
)
from printer_v1.operator_db.status import classify_operator_db_state
from tests.test_phase35_scheduler_single_tick_executor import table_count
from tests.test_phase37_long_run_paper_validation import Phase37LongRunPaperValidationTests


class Phase38V1PaperReleaseCandidateTests(Phase37LongRunPaperValidationTests):
    def seed_phase37_state(self, db_path):
        self.seed_phase36_state(db_path)
        build_long_paper_validation_payload(self.validation_args(db_path))

    def rc_args(self, db_path, **overrides):
        values = {
            "db_path": str(db_path),
            "project_root": str(PROJECT_ROOT),
            "format": "json",
            "no_color": True,
            "operator_approved": True,
            "rc_name": "printer-v1-paper-rc1",
            "acknowledge_no_clean_memory_blocker": True,
            "acknowledge_paper_only": True,
        }
        values.update(overrides)
        return type("Args", (), values)()

    def test_rc_command_exists_in_pyproject(self):
        scripts = tomllib.loads((PROJECT_ROOT / "pyproject.toml").read_text(encoding="utf-8"))["project"]["scripts"]
        self.assertEqual(
            scripts["printer-freeze-v1-paper-rc"],
            "printer_v1.operator_cli.commands:main_freeze_v1_paper_rc",
        )

    def test_rc_requires_approval_name_and_acknowledgements(self):
        db_path = self.make_db()
        self.seed_phase37_state(db_path)
        with self.assertRaises(ValueError):
            build_v1_paper_rc_payload(self.rc_args(db_path, operator_approved=False))
        with self.assertRaises(ValueError):
            build_v1_paper_rc_payload(self.rc_args(db_path, rc_name=""))
        with self.assertRaises(ValueError):
            build_v1_paper_rc_payload(self.rc_args(db_path, acknowledge_no_clean_memory_blocker=False))
        with self.assertRaises(ValueError):
            build_v1_paper_rc_payload(self.rc_args(db_path, acknowledge_paper_only=False))

    def test_rc_refuses_before_phase37_ready(self):
        db_path = self.make_db()
        self.seed_phase36_state(db_path)
        with self.assertRaises(ValueError):
            build_v1_paper_rc_payload(self.rc_args(db_path))

    def test_rc_freeze_creates_manifest_report_and_no_guarded_rows(self):
        db_path = self.make_db()
        self.seed_phase37_state(db_path)
        self.assertEqual(classify_operator_db_state(db_path, PROJECT_ROOT), "PERSISTENT_DB_LONG_RUN_PAPER_VALIDATION")
        payload = build_v1_paper_rc_payload(self.rc_args(db_path))
        manifest = payload["rc_report_manifest"]

        self.assertEqual(payload["db_state_classification"], "PERSISTENT_DB_V1_PAPER_RELEASE_CANDIDATE")
        self.assertEqual(payload["readiness_label"], "READY_V1_PAPER_RELEASE_CANDIDATE")
        self.assertEqual(payload["rc_report_manifest_rows"], 1)
        self.assertEqual(payload["operator_review_report_delta"], 1)
        self.assertEqual(payload["operator_review_item_delta"], 4)
        self.assertEqual(payload["guard_table_deltas"], {})
        self.assertEqual(manifest["rc_name"], "printer-v1-paper-rc1")
        self.assertEqual(manifest["rc_type"], "PAPER_ONLY")
        self.assertEqual(manifest["rc_status"], "PAPER_RC_FROZEN_WITH_BLOCKER")
        self.assertEqual(manifest["rc_verdict"], "PAPER_ONLY_RC_SAFE_BUT_NO_CLEAN_MEMORY")
        self.assertEqual(manifest["clean_memory_status"], "NO_CLEAN_ELIGIBLE_MEMORY")
        self.assertEqual(manifest["buy_status"], "BUY_LOCKED")
        self.assertEqual(manifest["live_status"], "LIVE_TRADING_NOT_PRESENT")
        self.assertEqual(manifest["profit_claim_status"], "NOT_PROFIT_CLAIM_READY")
        self.assertEqual(manifest["paper_position_status"], "NO_POSITION_OPENED")
        self.assertEqual(manifest["memory_safety_status"], "DIRTY_MEMORY_BLOCKED")
        self.assertEqual(manifest["source_status"], "SOURCE_FAILURES_VISIBLE")
        self.assertEqual(manifest["scheduler_status"], "BOUNDED_SCHEDULER_SAFE")
        self.assertEqual(manifest["runtime_status"], "BOUNDED_RUNTIME_SAFE")
        self.assertEqual(manifest["fake_profit_status"], "NO_FAKE_PROFIT")
        self.assertIn("NO_CLEAN_ELIGIBLE_MEMORY", manifest["known_blockers"])
        self.assertIn("BUY_LOCKED", manifest["known_blockers"])
        self.assertIn("NOT_LIVE_READY", manifest["known_blockers"])
        self.assertIn("NOT_PROFIT_CLAIM_READY", manifest["known_blockers"])
        self.assertIn("BUY_READY", manifest["release_candidate_forbidden_claims"])
        self.assertIn("LIVE_READY", manifest["release_candidate_forbidden_claims"])
        self.assertIn("PROFITABLE", manifest["release_candidate_forbidden_claims"])

        connection = sqlite3.connect(db_path)
        try:
            self.assertEqual(table_count(connection, "printer_source_requests"), 1)
            self.assertEqual(table_count(connection, "printer_source_responses"), 1)
            self.assertEqual(table_count(connection, "printer_source_failures"), 0)
            self.assertEqual(table_count(connection, "printer_tokens"), 1)
            self.assertEqual(table_count(connection, "printer_pairs"), 1)
            self.assertEqual(table_count(connection, "printer_token_snapshots"), 1)
            self.assertEqual(table_count(connection, "printer_memory_windows"), 1)
            self.assertEqual(table_count(connection, "printer_memory_retrieval_queries"), 1)
            self.assertEqual(table_count(connection, "printer_memory_retrieval_matches"), 0)
            self.assertEqual(table_count(connection, "printer_paper_decisions"), 1)
            self.assertEqual(table_count(connection, "printer_paper_positions"), 0)
            self.assertEqual(table_count(connection, "printer_paper_trade_events"), 0)
            self.assertEqual(table_count(connection, "printer_paper_trade_audits"), 0)
            self.assertEqual(table_count(connection, "printer_scheduler_jobs"), 7)
            self.assertEqual(table_count(connection, "printer_operator_review_reports"), 3)
            self.assertEqual(table_count(connection, "printer_operator_review_items"), 12)
        finally:
            connection.close()

    def test_rc_refuses_if_source_failures_are_hidden(self):
        db_path = self.make_db()
        self.seed_phase37_state(db_path)
        connection = sqlite3.connect(db_path)
        try:
            connection.execute(
                """
                UPDATE printer_operator_review_reports
                SET report_payload_json = REPLACE(report_payload_json, 'SOURCE_FAILURES_VISIBLE', 'SOURCE_OK_HIDDEN')
                WHERE report_title = 'Phase 37 Long-Run Paper Validation'
                """
            )
            connection.commit()
        finally:
            connection.close()
        with self.assertRaises(ValueError):
            build_v1_paper_rc_payload(self.rc_args(db_path))

    def test_rc_refuses_dirty_memory_promotion_or_buy_without_clean_memory(self):
        db_path = self.make_db()
        self.seed_phase37_state(db_path)
        connection = sqlite3.connect(db_path)
        try:
            connection.execute("UPDATE printer_memory_windows SET memory_quality_label = 'CLEAN_MEMORY', do_not_train = 0 WHERE id = 1")
            connection.commit()
        finally:
            connection.close()
        with self.assertRaises(ValueError):
            build_v1_paper_rc_payload(self.rc_args(db_path))

        db_path = self.make_db()
        self.seed_phase37_state(db_path)
        connection = sqlite3.connect(db_path)
        try:
            connection.execute("UPDATE printer_paper_decisions SET final_action_label = 'BUY' WHERE id = 1")
            connection.commit()
        finally:
            connection.close()
        with self.assertRaises(ValueError):
            build_v1_paper_rc_payload(self.rc_args(db_path))

    def test_rc_refuses_paper_position_or_runtime_marker(self):
        db_path = self.make_db()
        self.seed_phase37_state(db_path)
        connection = sqlite3.connect(db_path)
        try:
            connection.execute(
                """
                INSERT INTO printer_paper_positions (
                    token_id, pair_id, paper_decision_id, position_status,
                    paper_entry_price, paper_size_usd, opened_at, created_at
                )
                VALUES (1, 1, 1, 'OPEN', 1, 1, '2026-01-01T00:00:00+00:00', '2026-01-01T00:00:00+00:00')
                """
            )
            connection.commit()
        finally:
            connection.close()
        with self.assertRaises(ValueError):
            build_v1_paper_rc_payload(self.rc_args(db_path))

        db_path = self.make_db()
        self.seed_phase37_state(db_path)
        connection = sqlite3.connect(db_path)
        try:
            connection.execute("UPDATE printer_scheduler_jobs SET status = 'RUNNING' WHERE id = 1")
            connection.commit()
        finally:
            connection.close()
        with self.assertRaises(ValueError):
            build_v1_paper_rc_payload(self.rc_args(db_path))

    def test_rc_state_is_unsafe_with_hidden_blocker_or_positive_claim(self):
        db_path = self.make_db()
        self.seed_phase37_state(db_path)
        build_v1_paper_rc_payload(self.rc_args(db_path))
        self.assertEqual(classify_operator_db_state(db_path, PROJECT_ROOT), "PERSISTENT_DB_V1_PAPER_RELEASE_CANDIDATE")
        connection = sqlite3.connect(db_path)
        try:
            connection.execute(
                """
                UPDATE printer_operator_review_reports
                SET report_payload_json = REPLACE(report_payload_json, 'NO_CLEAN_ELIGIBLE_MEMORY', 'CLEAN_MEMORY_READY')
                WHERE report_title = 'Phase 38 V1 Paper Release Candidate'
                """
            )
            connection.commit()
        finally:
            connection.close()
        self.assertNotEqual(classify_operator_db_state(db_path, PROJECT_ROOT), "PERSISTENT_DB_V1_PAPER_RELEASE_CANDIDATE")

        db_path = self.make_db()
        self.seed_phase37_state(db_path)
        build_v1_paper_rc_payload(self.rc_args(db_path))
        connection = sqlite3.connect(db_path)
        try:
            connection.execute(
                """
                UPDATE printer_operator_review_reports
                SET report_payload_json = REPLACE(report_payload_json, '"buy_status": "BUY_LOCKED"', '"buy_status": "BUY_READY"')
                WHERE report_title = 'Phase 38 V1 Paper Release Candidate'
                """
            )
            connection.commit()
        finally:
            connection.close()
        self.assertNotEqual(classify_operator_db_state(db_path, PROJECT_ROOT), "PERSISTENT_DB_V1_PAPER_RELEASE_CANDIDATE")

    def test_no_future_phase39_command_exists(self):
        scripts = tomllib.loads((PROJECT_ROOT / "pyproject.toml").read_text(encoding="utf-8"))["project"]["scripts"]
        self.assertNotIn("printer-run-phase39", scripts)
        self.assertNotIn("printer-start-next-data-cycle", scripts)


if __name__ == "__main__":
    unittest.main()
