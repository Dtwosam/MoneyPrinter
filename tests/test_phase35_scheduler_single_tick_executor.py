import argparse
import pathlib
import sqlite3
import sys
import tempfile
import tomllib
import unittest
from datetime import datetime, timedelta, timezone

PROJECT_ROOT = pathlib.Path(__file__).resolve().parents[1]
SRC_PATH = PROJECT_ROOT / "src"
sys.path.insert(0, str(SRC_PATH))

from printer_v1.db import apply_migrations
from printer_v1.operator_cli.commands import (
    PHASE35_SELF_CHECK_JOB_KIND,
    PHASE35_SELF_CHECK_JOB_NAME,
    build_audit_paper_decision_once_payload,
    build_collect_context_once_payload,
    build_collect_token_snapshots_once_payload,
    build_create_paper_decision_once_payload,
    build_manual_intake_token_pair_payload,
    build_memory_quality_audit_once_payload,
    build_memory_window_once_payload,
    build_retrieve_clean_memory_once_payload,
    build_scheduler_single_tick_payload,
)
from printer_v1.operator_db.status import classify_operator_db_state


def table_count(connection, table_name):
    return int(connection.execute(f"SELECT COUNT(*) FROM {table_name}").fetchone()[0])


class Phase35SchedulerSingleTickExecutorTests(unittest.TestCase):
    def make_db(self):
        temp_dir = tempfile.TemporaryDirectory()
        db_path = pathlib.Path(temp_dir.name) / "phase35.sqlite3"
        apply_migrations(db_path)
        self.addCleanup(temp_dir.cleanup)
        return db_path

    def intake_args(self, db_path):
        return argparse.Namespace(
            db_path=str(db_path),
            project_root=str(PROJECT_ROOT),
            format="json",
            no_color=True,
            operator_approved=True,
            token_mint="phase35-mint",
            pair_address="phase35-pair",
            pool_address=None,
            chain="solana",
            intake_reason="operator approved phase 35 test",
            source_reference="manual-phase35-test",
            source_request_id=None,
            token_symbol="P35",
            token_name="Phase 35",
            dex_id="dexscreener",
            intake_json=None,
        )

    def snapshot_args(self, db_path):
        return argparse.Namespace(
            db_path=str(db_path),
            project_root=str(PROJECT_ROOT),
            format="json",
            no_color=True,
            operator_approved=True,
            token_mint="phase35-mint",
            token_id=None,
            pair_address="phase35-pair",
            pair_id=None,
            chain="solana",
            snapshot_count=1,
            max_seconds=5.0,
            source_name="dexscreener",
            source_reference="phase35-fixture",
        )

    def context_args(self, db_path):
        return argparse.Namespace(
            db_path=str(db_path),
            project_root=str(PROJECT_ROOT),
            format="json",
            no_color=True,
            operator_approved=True,
            token_mint="phase35-mint",
            token_id=None,
            pair_address="phase35-pair",
            pair_id=None,
            snapshot_id=None,
            chain="solana",
            source_name="dexscreener",
        )

    def memory_args(self, db_path):
        return argparse.Namespace(
            db_path=str(db_path),
            project_root=str(PROJECT_ROOT),
            format="json",
            no_color=True,
            operator_approved=True,
            token_mint="phase35-mint",
            token_id=None,
            pair_address="phase35-pair",
            pair_id=None,
            snapshot_id=None,
            chain="solana",
            memory_window="15m",
            source_reference="phase35-test",
        )

    def audit_memory_args(self, db_path):
        return argparse.Namespace(
            db_path=str(db_path),
            project_root=str(PROJECT_ROOT),
            format="json",
            no_color=True,
            operator_approved=True,
            memory_window_id=1,
            episode_id=None,
            token_mint=None,
            token_id=None,
            pair_address=None,
            pair_id=None,
            chain="solana",
        )

    def retrieval_args(self, db_path):
        return argparse.Namespace(
            db_path=str(db_path),
            project_root=str(PROJECT_ROOT),
            format="json",
            no_color=True,
            operator_approved=True,
            snapshot_id=1,
            token_mint=None,
            token_id=None,
            pair_address=None,
            pair_id=None,
            chain="solana",
        )

    def decision_args(self, db_path):
        return argparse.Namespace(
            db_path=str(db_path),
            project_root=str(PROJECT_ROOT),
            format="json",
            no_color=True,
            operator_approved=True,
            retrieval_query_id=1,
            snapshot_id=1,
            token_mint=None,
            token_id=None,
            pair_address=None,
            pair_id=None,
            chain="solana",
        )

    def paper_audit_args(self, db_path):
        return argparse.Namespace(
            db_path=str(db_path),
            project_root=str(PROJECT_ROOT),
            format="json",
            no_color=True,
            operator_approved=True,
            decision_id=1,
            snapshot_id=1,
            token_mint=None,
            token_id=None,
            pair_address=None,
            pair_id=None,
            chain="solana",
        )

    def scheduler_args(self, db_path, **overrides):
        values = {
            "db_path": str(db_path),
            "project_root": str(PROJECT_ROOT),
            "format": "json",
            "no_color": True,
            "operator_approved": True,
            "job_id": None,
            "create_approved_self_check_job": True,
            "max_jobs": 1,
        }
        values.update(overrides)
        return argparse.Namespace(**values)

    def success_transport(self, context):
        del context
        return {
            "pairs": [
                {
                    "chainId": "solana",
                    "pairAddress": "phase35-pair",
                    "baseToken": {"address": "phase35-mint", "symbol": "P35", "name": "Phase 35"},
                    "priceUsd": "0.00042",
                    "liquidity": {"usd": 12345.67},
                    "volume": {"m5": 100.0, "h1": 500.0, "h24": 2400.0},
                    "txns": {"m5": {"buys": 2, "sells": 1}},
                    "fdv": 420000.0,
                    "marketCap": 390000.0,
                    "priceChange": {"m5": 1.2, "h1": 4.5, "h24": 9.0},
                }
            ]
        }

    def seed_phase34_state(self, db_path):
        build_manual_intake_token_pair_payload(self.intake_args(db_path))
        build_collect_token_snapshots_once_payload(self.snapshot_args(db_path), transport=self.success_transport)
        build_collect_context_once_payload(self.context_args(db_path))
        build_memory_window_once_payload(self.memory_args(db_path))
        build_memory_quality_audit_once_payload(self.audit_memory_args(db_path))
        build_retrieve_clean_memory_once_payload(self.retrieval_args(db_path))
        build_create_paper_decision_once_payload(self.decision_args(db_path))
        build_audit_paper_decision_once_payload(self.paper_audit_args(db_path))

    def insert_scheduler_job(self, db_path, *, job_kind=PHASE35_SELF_CHECK_JOB_KIND, priority=11, status="PENDING", due=True, locked=False):
        scheduled_for = datetime.now(timezone.utc) + (timedelta(minutes=-1) if due else timedelta(minutes=30))
        connection = sqlite3.connect(db_path)
        try:
            cursor = connection.execute(
                """
                INSERT INTO printer_scheduler_jobs (
                    job_name, job_kind, target_table, target_id, priority,
                    status, scheduled_for, locked_at, lock_owner
                )
                VALUES (?, ?, 'printer_operator_review_reports', 1, ?, ?, ?, ?, ?)
                """,
                (
                    PHASE35_SELF_CHECK_JOB_NAME,
                    job_kind,
                    priority,
                    status,
                    scheduled_for.isoformat(),
                    datetime.now(timezone.utc).isoformat() if locked else None,
                    "phase35-test-lock" if locked else None,
                ),
            )
            connection.commit()
            return int(cursor.lastrowid)
        finally:
            connection.close()

    def test_scheduler_single_tick_command_exists_in_pyproject(self):
        scripts = tomllib.loads((PROJECT_ROOT / "pyproject.toml").read_text(encoding="utf-8"))["project"]["scripts"]
        self.assertEqual(
            scripts["printer-run-scheduler-single-tick"],
            "printer_v1.operator_cli.commands:main_run_scheduler_single_tick",
        )

    def test_scheduler_single_tick_requires_approval_and_refuses_multiple_jobs(self):
        db_path = self.make_db()
        self.seed_phase34_state(db_path)
        with self.assertRaises(ValueError):
            build_scheduler_single_tick_payload(self.scheduler_args(db_path, operator_approved=False))
        with self.assertRaises(ValueError):
            build_scheduler_single_tick_payload(self.scheduler_args(db_path, max_jobs=2))

    def test_scheduler_single_tick_creates_and_completes_one_self_check_job_only(self):
        db_path = self.make_db()
        self.seed_phase34_state(db_path)
        self.assertEqual(classify_operator_db_state(db_path, PROJECT_ROOT), "PERSISTENT_DB_REAL_PAPER_AUDIT_OPERATOR_REVIEW")
        payload = build_scheduler_single_tick_payload(self.scheduler_args(db_path))

        self.assertTrue(payload["scheduler_job_created"])
        self.assertEqual(payload["scheduler_job_delta"], 1)
        self.assertEqual(payload["scheduler_job_kind"], PHASE35_SELF_CHECK_JOB_KIND)
        self.assertEqual(payload["scheduler_job_status"], "SUCCEEDED")
        self.assertEqual(payload["scheduler_jobs_claimed"], 1)
        self.assertEqual(payload["scheduler_jobs_executed"], 1)
        self.assertEqual(payload["scheduler_jobs_completed"], 1)
        self.assertEqual(payload["scheduler_jobs_failed"], 0)
        self.assertEqual(payload["running_scheduler_jobs_after_exit"], 0)
        self.assertEqual(payload["active_job_locks_after_exit"], 0)
        self.assertEqual(payload["guard_table_deltas"], {})
        self.assertFalse(payload["runtime_has_started"])
        self.assertEqual(payload["db_state_classification"], "PERSISTENT_DB_SCHEDULER_SINGLE_TICK_EXECUTED")

        connection = sqlite3.connect(db_path)
        connection.row_factory = sqlite3.Row
        try:
            self.assertEqual(table_count(connection, "printer_scheduler_jobs"), 1)
            job = connection.execute("SELECT * FROM printer_scheduler_jobs WHERE id = 1").fetchone()
            self.assertEqual(job["status"], "SUCCEEDED")
            self.assertIsNone(job["locked_at"])
            self.assertIsNone(job["lock_owner"])
            self.assertEqual(table_count(connection, "printer_source_requests"), 1)
            self.assertEqual(table_count(connection, "printer_token_snapshots"), 1)
            self.assertEqual(table_count(connection, "printer_paper_decisions"), 1)
            self.assertEqual(table_count(connection, "printer_paper_positions"), 0)
            self.assertEqual(table_count(connection, "printer_paper_trade_events"), 0)
        finally:
            connection.close()

    def test_scheduler_single_tick_respects_priority_and_executes_at_most_one_job(self):
        db_path = self.make_db()
        self.seed_phase34_state(db_path)
        low_priority_job = self.insert_scheduler_job(db_path, priority=20)
        high_priority_job = self.insert_scheduler_job(db_path, priority=1)
        payload = build_scheduler_single_tick_payload(
            self.scheduler_args(db_path, create_approved_self_check_job=False)
        )

        self.assertEqual(payload["selected_scheduler_job_id"], high_priority_job)
        self.assertEqual(payload["scheduler_jobs_executed"], 1)
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

    def test_scheduler_single_tick_skips_locked_completed_future_and_unsupported_jobs(self):
        db_path = self.make_db()
        self.seed_phase34_state(db_path)
        self.insert_scheduler_job(db_path, status="SUCCEEDED")
        self.insert_scheduler_job(db_path, locked=True)
        self.insert_scheduler_job(db_path, due=False)
        self.insert_scheduler_job(db_path, job_kind="UNAPPROVED_DISCOVERY_PROMOTION")
        payload = build_scheduler_single_tick_payload(
            self.scheduler_args(db_path, create_approved_self_check_job=False)
        )

        self.assertIsNone(payload["selected_scheduler_job_id"])
        self.assertEqual(payload["scheduler_jobs_executed"], 0)
        self.assertEqual(payload["scheduler_jobs_completed"], 0)
        self.assertEqual(payload["scheduler_jobs_failed"], 0)

    def test_scheduler_single_tick_records_selected_unsupported_job_failure_honestly(self):
        db_path = self.make_db()
        self.seed_phase34_state(db_path)
        job_id = self.insert_scheduler_job(db_path, job_kind="UNSUPPORTED_PHASE35_JOB")
        payload = build_scheduler_single_tick_payload(
            self.scheduler_args(db_path, create_approved_self_check_job=False, job_id=job_id)
        )

        self.assertEqual(payload["selected_scheduler_job_id"], job_id)
        self.assertEqual(payload["scheduler_jobs_claimed"], 1)
        self.assertEqual(payload["scheduler_jobs_executed"], 1)
        self.assertEqual(payload["scheduler_jobs_completed"], 0)
        self.assertEqual(payload["scheduler_jobs_failed"], 1)
        self.assertEqual(payload["running_scheduler_jobs_after_exit"], 0)
        self.assertEqual(payload["active_job_locks_after_exit"], 0)
        connection = sqlite3.connect(db_path)
        try:
            job = connection.execute("SELECT status, last_error FROM printer_scheduler_jobs WHERE id = ?", (job_id,)).fetchone()
            self.assertEqual(job[0], "FAILED")
            self.assertEqual(job[1], "UNSUPPORTED_JOB_KIND_PHASE35")
        finally:
            connection.close()

    def test_scheduler_single_tick_state_with_running_job_or_runtime_marker_is_unsafe(self):
        db_path = self.make_db()
        self.seed_phase34_state(db_path)
        build_scheduler_single_tick_payload(self.scheduler_args(db_path))
        self.assertEqual(classify_operator_db_state(db_path, PROJECT_ROOT), "PERSISTENT_DB_SCHEDULER_SINGLE_TICK_EXECUTED")
        connection = sqlite3.connect(db_path)
        try:
            connection.execute("UPDATE printer_scheduler_jobs SET status = 'RUNNING', locked_at = ?, lock_owner = 'phase35-test' WHERE id = 1", (datetime.now(timezone.utc).isoformat(),))
            connection.commit()
        finally:
            connection.close()
        self.assertNotEqual(classify_operator_db_state(db_path, PROJECT_ROOT), "PERSISTENT_DB_SCHEDULER_SINGLE_TICK_EXECUTED")

    def test_no_phase36_bounded_runtime_command_exists(self):
        scripts = tomllib.loads((PROJECT_ROOT / "pyproject.toml").read_text(encoding="utf-8"))["project"]["scripts"]
        self.assertNotIn("printer-run-bounded-runtime", scripts)
        self.assertNotIn("printer-run-scheduler-runtime", scripts)


if __name__ == "__main__":
    unittest.main()
