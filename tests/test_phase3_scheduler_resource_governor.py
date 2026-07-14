import inspect
import pathlib
import sqlite3
import sys
import tempfile
import unittest
from datetime import datetime, timedelta, timezone

PROJECT_ROOT = pathlib.Path(__file__).resolve().parents[1]
SRC_PATH = PROJECT_ROOT / "src"
sys.path.insert(0, str(SRC_PATH))

from printer_v1.db import apply_migrations
from printer_v1.scheduler import resource_governor, scheduler
from printer_v1.scheduler.contracts import JOB_PRIORITY_ORDER, JobKind, JobStatus, LockResult
from printer_v1.scheduler.resource_governor import (
    effective_priority_value,
    is_higher_priority,
    should_delay_for_resource_pressure,
)
from printer_v1.scheduler.scheduler import (
    cancel_job,
    claim_due_job,
    complete_job,
    enqueue_job,
    fail_job,
    has_active_duplicate_job,
    list_due_jobs,
    release_stale_locks,
)


FORBIDDEN_FRAGMENTS = {
    "score",
    "confidence",
    "rank",
    "rating",
    "weight",
    "wallet",
    "private_key",
    "signed_tx",
    "live_trade",
}


class Phase3SchedulerResourceGovernorTest(unittest.TestCase):
    def setUp(self):
        self.tempdir = tempfile.TemporaryDirectory()
        self.db_path = pathlib.Path(self.tempdir.name) / "printer.sqlite3"
        apply_migrations(self.db_path)
        self.now = datetime(2026, 6, 19, 12, 0, tzinfo=timezone.utc)

    def tearDown(self):
        self.tempdir.cleanup()

    def fetch_job(self, job_id):
        connection = sqlite3.connect(self.db_path)
        connection.row_factory = sqlite3.Row
        try:
            return connection.execute(
                "SELECT * FROM printer_scheduler_jobs WHERE id = ?",
                (job_id,),
            ).fetchone()
        finally:
            connection.close()

    def enqueue(
        self,
        job_kind,
        *,
        job_name=None,
        target_table="printer_tokens",
        target_id=1,
        scheduled_for=None,
    ):
        return enqueue_job(
            self.db_path,
            job_name=job_name or f"{job_kind.value.lower()}_{target_id}",
            job_kind=job_kind,
            target_table=target_table,
            target_id=target_id,
            scheduled_for=scheduled_for or self.now,
        )

    def test_scheduler_files_import_successfully(self):
        self.assertTrue(inspect.ismodule(scheduler))
        self.assertTrue(inspect.ismodule(resource_governor))

    def test_required_job_priority_order_is_correct(self):
        # Long-window additions extend the established token-snapshot bands:
        # shorter FAST work precedes longer FAST work, then shorter NORMAL work
        # precedes longer NORMAL work. The shared close remains after all
        # snapshot evidence and before safety/discovery/context work. Cleanup
        # and reporting are synchronous terminal actions, not scheduler kinds.
        self.assertEqual(
            JOB_PRIORITY_ORDER,
            (
                JobKind.OPEN_PAPER_TRADE_MONITOR,
                JobKind.ACTIVE_EXIT_RISK_TOKEN,
                JobKind.TRACK_FAST_MICRO_EVENT,
                JobKind.TRACK_FAST_FIRST_15M,
                JobKind.TRACK_FAST_1H,
                JobKind.TRACK_FAST_4H,
                JobKind.TRACK_NORMAL_FIRST_15M,
                JobKind.TRACK_NORMAL_1H,
                JobKind.TRACK_NORMAL_4H,
                JobKind.MEMORY_WINDOW_CLOSE,
                JobKind.TRACKED_TOKEN_SAFETY_LIQUIDITY_REFRESH,
                JobKind.DISCOVERY_REFRESH,
                JobKind.MARKET_REGIME_CONTEXT,
                JobKind.SOLANA_CHAIN_HEAT_CONTEXT,
                JobKind.BACKUP_SOURCE_CHECK,
            ),
        )

    def test_open_paper_trade_monitoring_outranks_all_other_job_kinds(self):
        for job_kind in JobKind:
            if job_kind != JobKind.OPEN_PAPER_TRADE_MONITOR:
                self.assertTrue(is_higher_priority(JobKind.OPEN_PAPER_TRADE_MONITOR, job_kind))

    def test_active_exit_risk_token_outranks_lower_jobs(self):
        for job_kind in (
            JobKind.TRACK_FAST_MICRO_EVENT,
            JobKind.TRACK_FAST_FIRST_15M,
            JobKind.DISCOVERY_REFRESH,
            JobKind.MARKET_REGIME_CONTEXT,
            JobKind.BACKUP_SOURCE_CHECK,
        ):
            self.assertTrue(is_higher_priority(JobKind.ACTIVE_EXIT_RISK_TOKEN, job_kind))

    def test_track_fast_jobs_outrank_discovery_and_context(self):
        for track_fast in (JobKind.TRACK_FAST_MICRO_EVENT, JobKind.TRACK_FAST_FIRST_15M):
            for lower in (
                JobKind.DISCOVERY_REFRESH,
                JobKind.MARKET_REGIME_CONTEXT,
                JobKind.SOLANA_CHAIN_HEAT_CONTEXT,
                JobKind.BACKUP_SOURCE_CHECK,
            ):
                self.assertTrue(is_higher_priority(track_fast, lower))

    def test_discovery_refresh_outranks_context_and_backup(self):
        for lower in (
            JobKind.MARKET_REGIME_CONTEXT,
            JobKind.SOLANA_CHAIN_HEAT_CONTEXT,
            JobKind.BACKUP_SOURCE_CHECK,
        ):
            self.assertTrue(is_higher_priority(JobKind.DISCOVERY_REFRESH, lower))

    def test_backup_source_checks_are_lowest_priority(self):
        for job_kind in JobKind:
            if job_kind != JobKind.BACKUP_SOURCE_CHECK:
                self.assertTrue(is_higher_priority(job_kind, JobKind.BACKUP_SOURCE_CHECK))

    def test_starvation_protection_does_not_outrank_top_two(self):
        stale_time = self.now - timedelta(hours=3)
        bumped = effective_priority_value(
            JobKind.MARKET_REGIME_CONTEXT,
            scheduled_for=stale_time,
            now=self.now,
        )
        self.assertGreater(bumped, effective_priority_value(JobKind.OPEN_PAPER_TRADE_MONITOR))
        self.assertGreater(bumped, effective_priority_value(JobKind.ACTIVE_EXIT_RISK_TOKEN))

    def test_broad_context_delays_under_token_pressure(self):
        self.assertTrue(
            should_delay_for_resource_pressure(JobKind.MARKET_REGIME_CONTEXT, 1)
        )
        self.assertTrue(
            should_delay_for_resource_pressure(JobKind.BACKUP_SOURCE_CHECK, 1)
        )
        self.assertFalse(
            should_delay_for_resource_pressure(JobKind.TRACK_FAST_FIRST_15M, 1)
        )

    def test_enqueue_job_creates_scheduler_row(self):
        result, job_id = self.enqueue(JobKind.DISCOVERY_REFRESH)
        self.assertEqual(result, LockResult.ACQUIRED)
        row = self.fetch_job(job_id)
        self.assertEqual(row["status"], JobStatus.PENDING.value)

    def test_duplicate_active_jobs_are_prevented(self):
        self.enqueue(JobKind.DISCOVERY_REFRESH, job_name="discovery", target_id=None)
        result, job_id = self.enqueue(
            JobKind.DISCOVERY_REFRESH,
            job_name="discovery",
            target_id=None,
        )
        self.assertEqual(result, LockResult.DUPLICATE_ACTIVE_JOB)
        self.assertIsNone(job_id)
        self.assertTrue(
            has_active_duplicate_job(
                self.db_path,
                job_name="discovery",
                job_kind=JobKind.DISCOVERY_REFRESH,
                target_table="printer_tokens",
                target_id=None,
            )
        )

    def test_terminal_old_jobs_do_not_block_new_job(self):
        _, succeeded_id = self.enqueue(JobKind.DISCOVERY_REFRESH, job_name="refresh")
        complete_job(self.db_path, job_id=succeeded_id, now=self.now)
        result, new_id = self.enqueue(JobKind.DISCOVERY_REFRESH, job_name="refresh")
        self.assertEqual(result, LockResult.ACQUIRED)
        self.assertIsNotNone(new_id)

        _, failed_id = self.enqueue(JobKind.BACKUP_SOURCE_CHECK, job_name="backup")
        fail_job(self.db_path, job_id=failed_id, error="x", now=self.now, max_retries=1)
        result, new_id = self.enqueue(JobKind.BACKUP_SOURCE_CHECK, job_name="backup")
        self.assertEqual(result, LockResult.ACQUIRED)
        self.assertIsNotNone(new_id)

        _, cancelled_id = self.enqueue(JobKind.MARKET_REGIME_CONTEXT, job_name="market")
        cancel_job(self.db_path, job_id=cancelled_id, now=self.now)
        result, new_id = self.enqueue(JobKind.MARKET_REGIME_CONTEXT, job_name="market")
        self.assertEqual(result, LockResult.ACQUIRED)
        self.assertIsNotNone(new_id)

    def test_list_due_jobs_ignores_future_jobs(self):
        self.enqueue(
            JobKind.DISCOVERY_REFRESH,
            target_id=10,
            scheduled_for=self.now + timedelta(minutes=5),
        )
        self.enqueue(JobKind.BACKUP_SOURCE_CHECK, target_id=11, scheduled_for=self.now)
        due = list_due_jobs(self.db_path, now=self.now)
        self.assertEqual([row["job_kind"] for row in due], [JobKind.BACKUP_SOURCE_CHECK.value])

    def test_list_due_jobs_returns_priority_order(self):
        self.enqueue(JobKind.BACKUP_SOURCE_CHECK, target_id=1, scheduled_for=self.now)
        self.enqueue(JobKind.MARKET_REGIME_CONTEXT, target_id=2, scheduled_for=self.now)
        self.enqueue(JobKind.TRACK_FAST_FIRST_15M, target_id=3, scheduled_for=self.now)
        self.enqueue(JobKind.OPEN_PAPER_TRADE_MONITOR, target_id=4, scheduled_for=self.now)
        due = list_due_jobs(self.db_path, now=self.now)
        self.assertEqual(
            [row["job_kind"] for row in due],
            [
                JobKind.OPEN_PAPER_TRADE_MONITOR.value,
                JobKind.TRACK_FAST_FIRST_15M.value,
                JobKind.MARKET_REGIME_CONTEXT.value,
                JobKind.BACKUP_SOURCE_CHECK.value,
            ],
        )

    def test_claim_due_job_locks_exactly_one_job(self):
        _, job_id = self.enqueue(JobKind.DISCOVERY_REFRESH, target_id=1)
        result = claim_due_job(
            self.db_path,
            job_id=job_id,
            lock_owner="test-worker",
            now=self.now,
        )
        self.assertEqual(result, LockResult.ACQUIRED)
        row = self.fetch_job(job_id)
        self.assertEqual(row["status"], JobStatus.RUNNING.value)
        self.assertEqual(row["lock_owner"], "test-worker")

    def test_already_locked_job_cannot_be_claimed_twice(self):
        _, job_id = self.enqueue(JobKind.DISCOVERY_REFRESH, target_id=1)
        self.assertEqual(
            claim_due_job(self.db_path, job_id=job_id, lock_owner="a", now=self.now),
            LockResult.ACQUIRED,
        )
        self.assertEqual(
            claim_due_job(self.db_path, job_id=job_id, lock_owner="b", now=self.now),
            LockResult.ALREADY_LOCKED,
        )

    def test_complete_job_sets_succeeded(self):
        _, job_id = self.enqueue(JobKind.DISCOVERY_REFRESH)
        claim_due_job(self.db_path, job_id=job_id, lock_owner="a", now=self.now)
        complete_job(self.db_path, job_id=job_id, now=self.now)
        row = self.fetch_job(job_id)
        self.assertEqual(row["status"], JobStatus.SUCCEEDED.value)
        self.assertIsNone(row["locked_at"])

    def test_fail_job_increments_retry_and_cooldowns(self):
        _, job_id = self.enqueue(JobKind.TRACK_FAST_FIRST_15M)
        claim_due_job(self.db_path, job_id=job_id, lock_owner="a", now=self.now)
        status = fail_job(self.db_path, job_id=job_id, error="temporary", now=self.now)
        row = self.fetch_job(job_id)
        self.assertEqual(status, JobStatus.COOLDOWN)
        self.assertEqual(row["retry_count"], 1)
        self.assertEqual(row["status"], JobStatus.COOLDOWN.value)

    def test_fail_job_eventually_marks_over_retried_failed(self):
        _, job_id = self.enqueue(JobKind.TRACK_FAST_FIRST_15M)
        claim_due_job(self.db_path, job_id=job_id, lock_owner="a", now=self.now)
        status = fail_job(
            self.db_path,
            job_id=job_id,
            error="permanent",
            now=self.now,
            max_retries=1,
        )
        row = self.fetch_job(job_id)
        self.assertEqual(status, JobStatus.FAILED)
        self.assertEqual(row["status"], JobStatus.FAILED.value)

    def test_release_stale_locks_releases_running_jobs(self):
        stale_start = self.now - timedelta(minutes=10)
        _, job_id = self.enqueue(
            JobKind.DISCOVERY_REFRESH,
            scheduled_for=stale_start,
        )
        claim_due_job(self.db_path, job_id=job_id, lock_owner="stale", now=stale_start)
        released = release_stale_locks(
            self.db_path,
            now=self.now,
            lock_timeout_seconds=300,
        )
        row = self.fetch_job(job_id)
        self.assertEqual(released, 1)
        self.assertEqual(row["status"], JobStatus.PENDING.value)
        self.assertIsNone(row["lock_owner"])

    def test_source_backed_job_rejects_unknown_sources(self):
        result, job_id = enqueue_job(
            self.db_path,
            job_name="bad-source",
            job_kind=JobKind.BACKUP_SOURCE_CHECK,
            scheduled_for=self.now,
            source_name="paid_birdeye",
            source_request_kind="token_market_snapshot",
        )
        self.assertEqual(result, LockResult.SOURCE_NOT_ALLOWED)
        self.assertIsNone(job_id)

    def test_source_backed_job_rejects_invalid_request_kinds(self):
        result, job_id = enqueue_job(
            self.db_path,
            job_name="bad-kind",
            job_kind=JobKind.BACKUP_SOURCE_CHECK,
            scheduled_for=self.now,
            source_name="dexscreener",
            source_request_kind="fear_greed_context",
        )
        self.assertEqual(result, LockResult.SOURCE_NOT_ALLOWED)
        self.assertIsNone(job_id)

    def test_no_scheduler_function_performs_live_network_call(self):
        source_text = "\n".join(
            inspect.getsource(obj)
            for module in (scheduler, resource_governor)
            for _, obj in inspect.getmembers(module, inspect.isfunction)
            if obj.__module__ == module.__name__
        )
        forbidden_calls = [
            "requests.get",
            "requests.post",
            "httpx",
            "aiohttp",
            "urllib.request",
        ]
        self.assertFalse(any(call in source_text for call in forbidden_calls))

    def test_no_worker_dependency_exists(self):
        pyproject = (PROJECT_ROOT / "pyproject.toml").read_text(encoding="utf-8")
        lowered = pyproject.lower()
        for fragment in ("celery", "apscheduler", "cron", "requests", "httpx", "aiohttp"):
            self.assertNotIn(fragment, lowered)

    def test_no_forbidden_concept_is_introduced(self):
        names = []
        for module in (scheduler, resource_governor):
            names.extend(name.lower() for name, _ in inspect.getmembers(module))
        joined_names = " ".join(names)
        self.assertFalse(any(fragment in joined_names for fragment in FORBIDDEN_FRAGMENTS))


if __name__ == "__main__":
    unittest.main()
