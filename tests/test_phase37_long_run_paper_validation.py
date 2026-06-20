import pathlib
import sqlite3
import sys
import tomllib
import unittest
from datetime import datetime, timezone

PROJECT_ROOT = pathlib.Path(__file__).resolve().parents[1]
SRC_PATH = PROJECT_ROOT / "src"
sys.path.insert(0, str(SRC_PATH))

from printer_v1.operator_cli.commands import (
    PHASE37_MAX_JOBS_LIMIT,
    PHASE37_MAX_SECONDS_LIMIT,
    build_bounded_run_payload,
    build_long_paper_validation_payload,
)
from printer_v1.operator_db.status import classify_operator_db_state
from tests.test_phase35_scheduler_single_tick_executor import table_count
from tests.test_phase36_bounded_multi_tick_operator_runtime import Phase36BoundedMultiTickOperatorRuntimeTests


class Phase37LongRunPaperValidationTests(Phase36BoundedMultiTickOperatorRuntimeTests):
    def seed_phase36_state(self, db_path):
        self.seed_phase35_state(db_path)
        build_bounded_run_payload(self.bounded_args(db_path))

    def validation_args(self, db_path, **overrides):
        values = {
            "db_path": str(db_path),
            "project_root": str(PROJECT_ROOT),
            "format": "json",
            "no_color": True,
            "operator_approved": True,
            "max_jobs": 4,
            "max_seconds": 60,
            "create_approved_validation_jobs": 4,
        }
        values.update(overrides)
        return type("Args", (), values)()

    def test_long_validation_command_exists_in_pyproject(self):
        scripts = tomllib.loads((PROJECT_ROOT / "pyproject.toml").read_text(encoding="utf-8"))["project"]["scripts"]
        self.assertEqual(
            scripts["printer-run-long-paper-validation"],
            "printer_v1.operator_cli.commands:main_run_long_paper_validation",
        )

    def test_long_validation_requires_approval_and_caps(self):
        db_path = self.make_db()
        self.seed_phase36_state(db_path)
        with self.assertRaises(ValueError):
            build_long_paper_validation_payload(self.validation_args(db_path, operator_approved=False))
        with self.assertRaises(ValueError):
            build_long_paper_validation_payload(self.validation_args(db_path, max_jobs=None))
        with self.assertRaises(ValueError):
            build_long_paper_validation_payload(self.validation_args(db_path, max_seconds=None))
        with self.assertRaises(ValueError):
            build_long_paper_validation_payload(self.validation_args(db_path, max_jobs=0))
        with self.assertRaises(ValueError):
            build_long_paper_validation_payload(self.validation_args(db_path, max_seconds=0))
        with self.assertRaises(ValueError):
            build_long_paper_validation_payload(self.validation_args(db_path, max_jobs=PHASE37_MAX_JOBS_LIMIT + 1))
        with self.assertRaises(ValueError):
            build_long_paper_validation_payload(self.validation_args(db_path, max_seconds=PHASE37_MAX_SECONDS_LIMIT + 1))

    def test_long_validation_creates_four_jobs_report_and_no_guarded_rows(self):
        db_path = self.make_db()
        self.seed_phase36_state(db_path)
        self.assertEqual(classify_operator_db_state(db_path, PROJECT_ROOT), "PERSISTENT_DB_BOUNDED_RUNTIME_EXECUTED")
        payload = build_long_paper_validation_payload(self.validation_args(db_path))
        report = payload["validation_report"]

        self.assertEqual(payload["phase37_validation_jobs_created"], 4)
        self.assertEqual(payload["scheduler_job_delta"], 4)
        self.assertEqual(payload["scheduler_jobs_claimed"], 4)
        self.assertEqual(payload["scheduler_jobs_executed"], 4)
        self.assertEqual(payload["scheduler_jobs_completed"], 4)
        self.assertEqual(payload["scheduler_jobs_failed"], 0)
        self.assertEqual(payload["runtime_stop_reason"], "MAX_JOBS_REACHED")
        self.assertTrue(payload["runtime_stopped_cleanly"])
        self.assertFalse(payload["runtime_active_after_exit"])
        self.assertFalse(payload["unbounded_runtime_detected"])
        self.assertEqual(payload["running_scheduler_jobs_after_exit"], 0)
        self.assertEqual(payload["active_job_locks_after_exit"], 0)
        self.assertEqual(payload["guard_table_deltas"], {})
        self.assertEqual(payload["operator_review_report_delta"], 1)
        self.assertEqual(payload["operator_review_item_delta"], 4)
        self.assertEqual(payload["db_state_classification"], "PERSISTENT_DB_LONG_RUN_PAPER_VALIDATION")
        self.assertEqual(report["source_failure_visibility_label"], "SOURCE_FAILURES_VISIBLE")
        self.assertEqual(report["memory_quality_label"], "DIRTY_MEMORY_PRESENT_NO_CLEAN_MEMORY")
        self.assertEqual(report["clean_eligible_memory_count"], 0)
        self.assertEqual(report["dirty_memory_count"], 1)
        self.assertEqual(report["dirty_memory_blocking_label"], "DIRTY_MEMORY_BLOCKED")
        self.assertEqual(report["retrieval_quality_label"], "NO_CLEAN_MEMORY_MATCHES")
        self.assertEqual(report["paper_decision_quality_label"], "BLOCKED_DECISION_VALID")
        self.assertEqual(report["fake_profit_prevention_label"], "NO_FAKE_PROFIT")
        self.assertEqual(report["runtime_safety_label"], "BOUNDED_RUNTIME_SAFE")
        self.assertEqual(report["live_trading_safety_label"], "LIVE_TRADING_NOT_PRESENT")
        self.assertEqual(report["validation_verdict"], "PAPER_VALIDATION_SAFE_BUT_NO_CLEAN_MEMORY")
        self.assertTrue(report["release_candidate_allowed"])
        self.assertTrue(report["not_buy_ready"])
        self.assertTrue(report["not_live_ready"])
        self.assertTrue(report["not_profitable_claim"])

        connection = sqlite3.connect(db_path)
        try:
            self.assertEqual(table_count(connection, "printer_scheduler_jobs"), 7)
            self.assertEqual(table_count(connection, "printer_source_requests"), 1)
            self.assertEqual(table_count(connection, "printer_paper_decisions"), 1)
            self.assertEqual(table_count(connection, "printer_paper_positions"), 0)
            self.assertEqual(table_count(connection, "printer_paper_trade_events"), 0)
            self.assertEqual(table_count(connection, "printer_operator_review_reports"), 2)
            self.assertEqual(table_count(connection, "printer_operator_review_items"), 8)
        finally:
            connection.close()

    def test_long_validation_stops_when_no_eligible_jobs_remain(self):
        db_path = self.make_db()
        self.seed_phase36_state(db_path)
        payload = build_long_paper_validation_payload(
            self.validation_args(db_path, create_approved_validation_jobs=2, max_jobs=4)
        )
        self.assertEqual(payload["scheduler_jobs_executed"], 2)
        self.assertEqual(payload["runtime_stop_reason"], "NO_ELIGIBLE_JOBS_AFTER_WORK")
        self.assertTrue(payload["runtime_stopped_cleanly"])

    def test_long_validation_skips_unapproved_locked_completed_and_future_jobs(self):
        db_path = self.make_db()
        self.seed_phase36_state(db_path)
        self.insert_scheduler_job(db_path, status="SUCCEEDED")
        self.insert_scheduler_job(db_path, due=False)
        self.insert_scheduler_job(db_path, locked=True)
        self.insert_scheduler_job(db_path, job_kind="UNAPPROVED_DISCOVERY_PROMOTION")
        payload = build_long_paper_validation_payload(
            self.validation_args(db_path, create_approved_validation_jobs=0, max_jobs=4)
        )
        self.assertEqual(payload["scheduler_jobs_executed"], 0)
        self.assertEqual(payload["runtime_stop_reason"], "NO_ELIGIBLE_JOBS")

    def test_long_validation_state_is_unsafe_if_report_hides_source_failures(self):
        db_path = self.make_db()
        self.seed_phase36_state(db_path)
        build_long_paper_validation_payload(self.validation_args(db_path))
        self.assertEqual(classify_operator_db_state(db_path, PROJECT_ROOT), "PERSISTENT_DB_LONG_RUN_PAPER_VALIDATION")
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
        self.assertNotEqual(classify_operator_db_state(db_path, PROJECT_ROOT), "PERSISTENT_DB_LONG_RUN_PAPER_VALIDATION")

    def test_long_validation_state_is_unsafe_with_buy_or_pnl_rows(self):
        db_path = self.make_db()
        self.seed_phase36_state(db_path)
        build_long_paper_validation_payload(self.validation_args(db_path))
        connection = sqlite3.connect(db_path)
        try:
            connection.execute("UPDATE printer_paper_decisions SET final_action_label = 'BUY' WHERE id = 1")
            connection.commit()
        finally:
            connection.close()
        self.assertNotEqual(classify_operator_db_state(db_path, PROJECT_ROOT), "PERSISTENT_DB_LONG_RUN_PAPER_VALIDATION")

    def test_long_validation_state_with_active_lock_is_unsafe(self):
        db_path = self.make_db()
        self.seed_phase36_state(db_path)
        build_long_paper_validation_payload(self.validation_args(db_path))
        connection = sqlite3.connect(db_path)
        try:
            connection.execute(
                "UPDATE printer_scheduler_jobs SET locked_at = ?, lock_owner = 'phase37-test' WHERE id = 4",
                (datetime.now(timezone.utc).isoformat(),),
            )
            connection.commit()
        finally:
            connection.close()
        self.assertNotEqual(classify_operator_db_state(db_path, PROJECT_ROOT), "PERSISTENT_DB_LONG_RUN_PAPER_VALIDATION")

    def test_no_phase38_release_candidate_freeze_command_exists(self):
        scripts = tomllib.loads((PROJECT_ROOT / "pyproject.toml").read_text(encoding="utf-8"))["project"]["scripts"]
        self.assertNotIn("printer-freeze-release-candidate", scripts)
        self.assertNotIn("printer-run-phase38", scripts)


if __name__ == "__main__":
    unittest.main()
