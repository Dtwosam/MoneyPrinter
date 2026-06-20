import pathlib
import sqlite3
import sys
import tomllib
import unittest
from datetime import datetime, timedelta, timezone

PROJECT_ROOT = pathlib.Path(__file__).resolve().parents[1]
SRC_PATH = PROJECT_ROOT / "src"
sys.path.insert(0, str(SRC_PATH))

from printer_v1.operator_cli.commands import (
    PHASE35_SELF_CHECK_JOB_KIND,
    PHASE36_MAX_JOBS_LIMIT,
    PHASE36_MAX_SECONDS_LIMIT,
    PHASE36_SELF_CHECK_JOB_NAME,
    build_bounded_run_payload,
    build_scheduler_single_tick_payload,
)
from printer_v1.operator_db.status import classify_operator_db_state
from tests.test_phase35_scheduler_single_tick_executor import Phase35SchedulerSingleTickExecutorTests, table_count


class Phase36BoundedMultiTickOperatorRuntimeTests(Phase35SchedulerSingleTickExecutorTests):
    def seed_phase35_state(self, db_path):
        self.seed_phase34_state(db_path)
        build_scheduler_single_tick_payload(self.scheduler_args(db_path))

    def bounded_args(self, db_path, **overrides):
        values = {
            "db_path": str(db_path),
            "project_root": str(PROJECT_ROOT),
            "format": "json",
            "no_color": True,
            "operator_approved": True,
            "max_jobs": 2,
            "max_seconds": 30,
            "create_approved_self_check_jobs": 2,
        }
        values.update(overrides)
        return type("Args", (), values)()

    def test_bounded_command_exists_in_pyproject(self):
        scripts = tomllib.loads((PROJECT_ROOT / "pyproject.toml").read_text(encoding="utf-8"))["project"]["scripts"]
        self.assertEqual(
            scripts["printer-run-bounded"],
            "printer_v1.operator_cli.commands:main_run_bounded",
        )

    def test_bounded_run_requires_approval_and_caps(self):
        db_path = self.make_db()
        self.seed_phase35_state(db_path)
        with self.assertRaises(ValueError):
            build_bounded_run_payload(self.bounded_args(db_path, operator_approved=False))
        with self.assertRaises(ValueError):
            build_bounded_run_payload(self.bounded_args(db_path, max_jobs=None))
        with self.assertRaises(ValueError):
            build_bounded_run_payload(self.bounded_args(db_path, max_seconds=None))
        with self.assertRaises(ValueError):
            build_bounded_run_payload(self.bounded_args(db_path, max_jobs=0))
        with self.assertRaises(ValueError):
            build_bounded_run_payload(self.bounded_args(db_path, max_seconds=0))
        with self.assertRaises(ValueError):
            build_bounded_run_payload(self.bounded_args(db_path, max_jobs=PHASE36_MAX_JOBS_LIMIT + 1))
        with self.assertRaises(ValueError):
            build_bounded_run_payload(self.bounded_args(db_path, max_seconds=PHASE36_MAX_SECONDS_LIMIT + 1))

    def test_bounded_run_creates_two_self_check_jobs_and_stops_at_max_jobs(self):
        db_path = self.make_db()
        self.seed_phase35_state(db_path)
        self.assertEqual(classify_operator_db_state(db_path, PROJECT_ROOT), "PERSISTENT_DB_SCHEDULER_SINGLE_TICK_EXECUTED")
        payload = build_bounded_run_payload(self.bounded_args(db_path))

        self.assertEqual(payload["phase36_scheduler_jobs_created"], 2)
        self.assertEqual(payload["scheduler_job_delta"], 2)
        self.assertEqual(payload["scheduler_jobs_claimed"], 2)
        self.assertEqual(payload["scheduler_jobs_executed"], 2)
        self.assertEqual(payload["scheduler_jobs_completed"], 2)
        self.assertEqual(payload["scheduler_jobs_failed"], 0)
        self.assertEqual(payload["runtime_stop_reason"], "MAX_JOBS_REACHED")
        self.assertTrue(payload["runtime_stopped_cleanly"])
        self.assertFalse(payload["runtime_active_after_exit"])
        self.assertFalse(payload["unbounded_runtime_detected"])
        self.assertEqual(payload["running_scheduler_jobs_after_exit"], 0)
        self.assertEqual(payload["active_job_locks_after_exit"], 0)
        self.assertEqual(payload["guard_table_deltas"], {})
        self.assertEqual(payload["db_state_classification"], "PERSISTENT_DB_BOUNDED_RUNTIME_EXECUTED")

        connection = sqlite3.connect(db_path)
        try:
            self.assertEqual(table_count(connection, "printer_scheduler_jobs"), 3)
            self.assertEqual(
                connection.execute(
                    "SELECT COUNT(*) FROM printer_scheduler_jobs WHERE job_name = ? AND status = 'SUCCEEDED'",
                    (PHASE36_SELF_CHECK_JOB_NAME,),
                ).fetchone()[0],
                2,
            )
            self.assertEqual(table_count(connection, "printer_source_requests"), 1)
            self.assertEqual(table_count(connection, "printer_token_snapshots"), 1)
            self.assertEqual(table_count(connection, "printer_paper_decisions"), 1)
            self.assertEqual(table_count(connection, "printer_paper_positions"), 0)
            self.assertEqual(table_count(connection, "printer_paper_trade_events"), 0)
        finally:
            connection.close()

    def test_bounded_run_stops_when_no_eligible_jobs_remain(self):
        db_path = self.make_db()
        self.seed_phase35_state(db_path)
        payload = build_bounded_run_payload(
            self.bounded_args(db_path, create_approved_self_check_jobs=1, max_jobs=2)
        )

        self.assertEqual(payload["scheduler_jobs_executed"], 1)
        self.assertEqual(payload["runtime_stop_reason"], "NO_ELIGIBLE_JOBS_AFTER_WORK")
        self.assertTrue(payload["runtime_stopped_cleanly"])

    def test_bounded_run_respects_priority_and_max_jobs_cap(self):
        db_path = self.make_db()
        self.seed_phase35_state(db_path)
        low_priority_job = self.insert_scheduler_job(db_path, priority=20)
        high_priority_job = self.insert_scheduler_job(db_path, priority=1)
        payload = build_bounded_run_payload(
            self.bounded_args(db_path, create_approved_self_check_jobs=0, max_jobs=1)
        )

        self.assertEqual(payload["scheduler_jobs_executed"], 1)
        self.assertEqual(payload["job_results"][0]["job_id"], high_priority_job)
        connection = sqlite3.connect(db_path)
        try:
            self.assertEqual(
                connection.execute("SELECT status FROM printer_scheduler_jobs WHERE id = ?", (high_priority_job,)).fetchone()[0],
                "SUCCEEDED",
            )
            self.assertEqual(
                connection.execute("SELECT status FROM printer_scheduler_jobs WHERE id = ?", (low_priority_job,)).fetchone()[0],
                "PENDING",
            )
        finally:
            connection.close()

    def test_bounded_run_skips_locked_completed_future_and_unapproved_jobs(self):
        db_path = self.make_db()
        self.seed_phase35_state(db_path)
        self.insert_scheduler_job(db_path, status="SUCCEEDED")
        self.insert_scheduler_job(db_path, due=False)
        self.insert_scheduler_job(db_path, job_kind="UNAPPROVED_DISCOVERY_PROMOTION")
        payload = build_bounded_run_payload(
            self.bounded_args(db_path, create_approved_self_check_jobs=0, max_jobs=2)
        )

        self.assertEqual(payload["scheduler_jobs_executed"], 0)
        self.assertEqual(payload["runtime_stop_reason"], "NO_ELIGIBLE_JOBS")
        self.assertTrue(payload["runtime_stopped_cleanly"])

    def test_bounded_run_records_failed_job_honestly_and_releases_lock(self):
        db_path = self.make_db()
        self.seed_phase35_state(db_path)
        job_id = self.insert_scheduler_job(db_path)
        connection = sqlite3.connect(db_path)
        try:
            connection.execute(
                "UPDATE printer_paper_decisions SET paper_decision_status_label = 'PAPER_DECISION_EXPIRED' WHERE id = 1"
            )
            connection.commit()
        finally:
            connection.close()
        payload = build_bounded_run_payload(
            self.bounded_args(db_path, create_approved_self_check_jobs=0, max_jobs=1)
        )

        self.assertEqual(payload["scheduler_jobs_executed"], 1)
        self.assertEqual(payload["scheduler_jobs_completed"], 0)
        self.assertEqual(payload["scheduler_jobs_failed"], 1)
        self.assertEqual(payload["running_scheduler_jobs_after_exit"], 0)
        self.assertEqual(payload["active_job_locks_after_exit"], 0)
        connection = sqlite3.connect(db_path)
        try:
            job = connection.execute("SELECT status, last_error FROM printer_scheduler_jobs WHERE id = ?", (job_id,)).fetchone()
            self.assertEqual(job[0], "FAILED")
            self.assertEqual(job[1], "SCHEDULER_SELF_CHECK_UNSAFE_DECISION_STATE")
        finally:
            connection.close()

    def test_bounded_runtime_state_with_active_lock_is_unsafe(self):
        db_path = self.make_db()
        self.seed_phase35_state(db_path)
        build_bounded_run_payload(self.bounded_args(db_path))
        self.assertEqual(classify_operator_db_state(db_path, PROJECT_ROOT), "PERSISTENT_DB_BOUNDED_RUNTIME_EXECUTED")
        connection = sqlite3.connect(db_path)
        try:
            connection.execute(
                "UPDATE printer_scheduler_jobs SET locked_at = ?, lock_owner = 'phase36-test' WHERE id = 2",
                (datetime.now(timezone.utc).isoformat(),),
            )
            connection.commit()
        finally:
            connection.close()
        self.assertNotEqual(classify_operator_db_state(db_path, PROJECT_ROOT), "PERSISTENT_DB_BOUNDED_RUNTIME_EXECUTED")

    def test_no_phase38_release_candidate_command_exists(self):
        scripts = tomllib.loads((PROJECT_ROOT / "pyproject.toml").read_text(encoding="utf-8"))["project"]["scripts"]
        self.assertNotIn("printer-freeze-release-candidate", scripts)
        self.assertNotIn("printer-run-phase38", scripts)


if __name__ == "__main__":
    unittest.main()
