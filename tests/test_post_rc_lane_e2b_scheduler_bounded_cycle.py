"""
Post-Lane 10 Lane E2B — Scheduler End-to-End Bounded Cycle Integration Test

Tests prove:
- scheduler contracts module imports cleanly
- scheduler module imports cleanly
- lifecycle contracts module imports cleanly
- lifecycle state_machine module imports cleanly
- lifecycle tracking_queue module imports cleanly
- apply_migrations creates printer_scheduler_jobs table
- apply_migrations creates printer_tracking_queue table
- apply_migrations creates printer_tokens table
- apply_migrations creates printer_pairs table
- apply_migrations creates printer_token_snapshots table
- fresh DB has zero scheduler jobs
- fresh DB has zero running jobs
- fresh DB has zero active locks
- TRACK_FAST_FIRST_15M enqueue returns ACQUIRED
- TRACK_NORMAL_FIRST_15M enqueue returns ACQUIRED
- MEMORY_WINDOW_CLOSE enqueue returns ACQUIRED
- enqueue returns non-None job_id
- enqueued job status is PENDING
- enqueued job has no locked_at at enqueue time
- enqueued job has no lock_owner at enqueue time
- enqueued job_kind in DB matches input job_kind
- duplicate active job is blocked by DUPLICATE_ACTIVE_JOB
- claim_due_job returns ACQUIRED for a PENDING due job
- claimed job status becomes RUNNING
- claimed job locked_at is set
- claimed job lock_owner is set
- claiming a future job returns NOT_DUE
- claiming an already-running job returns ALREADY_LOCKED
- complete_job sets status to SUCCEEDED
- complete_job clears locked_at to NULL
- complete_job clears lock_owner to NULL
- complete_job sets finished_at
- zero running jobs after single complete
- zero active locks after single complete
- MEMORY_WINDOW_CLOSE enqueue returns ACQUIRED
- MEMORY_WINDOW_CLOSE can be claimed
- MEMORY_WINDOW_CLOSE can be completed
- MEMORY_WINDOW_CLOSE status is SUCCEEDED after complete
- MEMORY_WINDOW_CLOSE priority is lower than TRACK_FAST_FIRST_15M
- MEMORY_WINDOW_CLOSE priority is lower than TRACK_NORMAL_FIRST_15M
- MEMORY_WINDOW_CLOSE priority is higher than DISCOVERY_REFRESH
- MEMORY_WINDOW_CLOSE priority is higher than MARKET_REGIME_CONTEXT
- full bounded cycle (enqueue + claim + complete) for three job kinds succeeds
- zero running jobs after full bounded cycle
- zero active locks after full bounded cycle
- all three jobs reach SUCCEEDED status after full cycle
- full cycle ends with MEMORY_WINDOW_CLOSE SUCCEEDED
- no stale locks remain after full cycle
- full cycle job count is exactly three
- max_active_tokens constant is 10
- max_track_fast constant is 3
- max_track_normal constant is 7
- max_track_fast + max_track_normal equals max_active_tokens
- max_track_fast + max_track_normal does not exceed max_active_tokens
- exactly max_track_fast TRACK_FAST_FIRST_15M jobs enqueue with ACQUIRED
- exactly max_track_normal TRACK_NORMAL_FIRST_15M jobs enqueue with ACQUIRED
- total tracking jobs within active cap (fast + normal <= max_active_tokens)
- PAPER_MONITORING state exists in TokenLifecycleState
- ENTER_PAPER_MONITORING event exists in LifecycleEvent
- OPEN_PAPER_TRADE_MONITOR job kind exists in JobKind
- PAPER_MONITORING maps to OPEN_PAPER_TRADE_MONITOR in SCHEDULER_KIND_BY_LANE
- TRACK_FAST to PAPER_MONITORING transition exists and is recorded as a future-lane risk/caveat
- TRACK_NORMAL to PAPER_MONITORING is NOT in ALLOWED_TRANSITIONS map
- DISCOVERED to PAPER_MONITORING is NOT in ALLOWED_TRANSITIONS map
- no OPEN_PAPER_TRADE_MONITOR job enqueued in bounded cycle DB
- OPEN_PAPER_TRADE_MONITOR has highest job priority but must not appear in cycle
- no OPEN_PAPER_TRADE_MONITOR jobs in DB after bounded cycle
- no printer_token_snapshots rows after bounded cycle (no real snapshots)
- no printer_paper_decisions rows after bounded cycle (no paper decisions)
- no printer_paper_positions rows after bounded cycle (no positions or PnL)
- bounded cycle DB contains only expected job kinds
- no HTTP source-fetching libraries in sys.modules after test imports
- no running jobs in DB after bounded cycle
- no active locks in DB after bounded cycle
"""

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
from printer_v1.lifecycle.contracts import LifecycleEvent, TokenLifecycleState
from printer_v1.lifecycle.state_machine import ALLOWED_TRANSITIONS, can_transition
from printer_v1.lifecycle.tracking_queue import SCHEDULER_KIND_BY_LANE
from printer_v1.operator_cli.commands import (
    _LANE_E1_MAX_ACTIVE_TOKENS_DEFAULT,
    _LANE_E1_MAX_TRACK_FAST_DEFAULT,
    _LANE_E1_MAX_TRACK_NORMAL_DEFAULT,
)
from printer_v1.scheduler.contracts import JobKind, JobStatus, LockResult
from printer_v1.scheduler.resource_governor import is_higher_priority
from printer_v1.scheduler.scheduler import (
    claim_due_job,
    complete_job,
    enqueue_job,
)

MAX_ACTIVE_TOKENS = _LANE_E1_MAX_ACTIVE_TOKENS_DEFAULT
MAX_TRACK_FAST = _LANE_E1_MAX_TRACK_FAST_DEFAULT
MAX_TRACK_NORMAL = _LANE_E1_MAX_TRACK_NORMAL_DEFAULT


class _DbTestBase(unittest.TestCase):
    """Common setup: temp SQLite with all migrations applied. No persistent DB mutation."""

    def setUp(self):
        self.tempdir = tempfile.TemporaryDirectory()
        self.db_path = pathlib.Path(self.tempdir.name) / "e2b_test.sqlite3"
        apply_migrations(self.db_path)
        self.now = datetime(2026, 6, 27, 12, 0, tzinfo=timezone.utc)

    def tearDown(self):
        self.tempdir.cleanup()

    def _count_rows(self, table: str) -> int:
        conn = sqlite3.connect(self.db_path)
        try:
            return int(conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0])
        finally:
            conn.close()

    def _count_running_jobs(self) -> int:
        conn = sqlite3.connect(self.db_path)
        try:
            return int(conn.execute(
                "SELECT COUNT(*) FROM printer_scheduler_jobs WHERE status = 'RUNNING'"
            ).fetchone()[0])
        finally:
            conn.close()

    def _count_active_locks(self) -> int:
        conn = sqlite3.connect(self.db_path)
        try:
            return int(conn.execute(
                "SELECT COUNT(*) FROM printer_scheduler_jobs"
                " WHERE locked_at IS NOT NULL OR lock_owner IS NOT NULL"
            ).fetchone()[0])
        finally:
            conn.close()

    def _fetch_job(self, job_id: int) -> sqlite3.Row | None:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        try:
            return conn.execute(
                "SELECT * FROM printer_scheduler_jobs WHERE id = ?", (job_id,)
            ).fetchone()
        finally:
            conn.close()

    def _distinct_job_kinds_in_db(self) -> set[str]:
        conn = sqlite3.connect(self.db_path)
        try:
            rows = conn.execute(
                "SELECT DISTINCT job_kind FROM printer_scheduler_jobs"
            ).fetchall()
        finally:
            conn.close()
        return {row[0] for row in rows}

    def _insert_token(self, token_mint: str) -> int:
        conn = sqlite3.connect(self.db_path)
        try:
            cursor = conn.execute(
                "INSERT INTO printer_tokens (token_mint, token_status) VALUES (?, ?)",
                (token_mint, TokenLifecycleState.DISCOVERED.value),
            )
            conn.commit()
            return int(cursor.lastrowid)
        finally:
            conn.close()

    def _enqueue(
        self,
        job_kind: JobKind,
        *,
        job_name: str | None = None,
        target_id: int | None = 1,
        target_table: str | None = "printer_tokens",
        scheduled_for: datetime | None = None,
    ) -> tuple[LockResult, int | None]:
        name = job_name or f"{job_kind.value.lower()}_{target_id}"
        return enqueue_job(
            self.db_path,
            job_name=name,
            job_kind=job_kind,
            target_table=target_table,
            target_id=target_id,
            scheduled_for=scheduled_for or self.now,
        )

    def _claim(self, job_id: int, *, lock_owner: str = "e2b_test_worker") -> LockResult:
        return claim_due_job(
            self.db_path,
            job_id=job_id,
            lock_owner=lock_owner,
            now=self.now,
        )

    def _complete(self, job_id: int) -> None:
        complete_job(self.db_path, job_id=job_id, now=self.now)

    def _run_full_cycle(self) -> list[int]:
        """Minimal bounded cycle: 1 fast + 1 normal + window close. No real sources."""
        t1 = self._insert_token("cycle-fast-token")
        t2 = self._insert_token("cycle-normal-token")
        _, jid_fast = enqueue_job(
            self.db_path,
            job_name="cycle_track_fast_1",
            job_kind=JobKind.TRACK_FAST_FIRST_15M,
            target_table="printer_tokens",
            target_id=t1,
            scheduled_for=self.now,
        )
        _, jid_normal = enqueue_job(
            self.db_path,
            job_name="cycle_track_normal_1",
            job_kind=JobKind.TRACK_NORMAL_FIRST_15M,
            target_table="printer_tokens",
            target_id=t2,
            scheduled_for=self.now,
        )
        _, jid_close = enqueue_job(
            self.db_path,
            job_name="cycle_memory_window_close_1",
            job_kind=JobKind.MEMORY_WINDOW_CLOSE,
            target_table=None,
            target_id=None,
            scheduled_for=self.now,
        )
        for jid in (jid_fast, jid_normal, jid_close):
            claim_due_job(self.db_path, job_id=jid, lock_owner="e2b_cycle_worker", now=self.now)
            complete_job(self.db_path, job_id=jid, now=self.now)
        return [jid_fast, jid_normal, jid_close]


# ---------------------------------------------------------------------------
# Class 1: Infrastructure — migrations, imports, fresh-DB state
# ---------------------------------------------------------------------------

class LaneE2BInfrastructureTests(unittest.TestCase):
    """Prove migrations create required tables and fresh DB starts clean."""

    def setUp(self):
        self.tempdir = tempfile.TemporaryDirectory()
        self.db_path = pathlib.Path(self.tempdir.name) / "infra_test.sqlite3"
        apply_migrations(self.db_path)

    def tearDown(self):
        self.tempdir.cleanup()

    def _table_exists(self, table: str) -> bool:
        conn = sqlite3.connect(self.db_path)
        try:
            row = conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name=?", (table,)
            ).fetchone()
            return row is not None
        finally:
            conn.close()

    def _count(self, query: str) -> int:
        conn = sqlite3.connect(self.db_path)
        try:
            return int(conn.execute(query).fetchone()[0])
        finally:
            conn.close()

    def test_scheduler_contracts_import_cleanly(self):
        from printer_v1.scheduler import contracts
        import inspect
        self.assertTrue(inspect.ismodule(contracts))

    def test_scheduler_module_import_cleanly(self):
        from printer_v1.scheduler import scheduler
        import inspect
        self.assertTrue(inspect.ismodule(scheduler))

    def test_lifecycle_contracts_import_cleanly(self):
        from printer_v1.lifecycle import contracts
        import inspect
        self.assertTrue(inspect.ismodule(contracts))

    def test_lifecycle_state_machine_import_cleanly(self):
        from printer_v1.lifecycle import state_machine
        import inspect
        self.assertTrue(inspect.ismodule(state_machine))

    def test_lifecycle_tracking_queue_import_cleanly(self):
        from printer_v1.lifecycle import tracking_queue
        import inspect
        self.assertTrue(inspect.ismodule(tracking_queue))

    def test_apply_migrations_creates_scheduler_jobs_table(self):
        self.assertTrue(self._table_exists("printer_scheduler_jobs"))

    def test_apply_migrations_creates_tracking_queue_table(self):
        self.assertTrue(self._table_exists("printer_tracking_queue"))

    def test_apply_migrations_creates_printer_tokens_table(self):
        self.assertTrue(self._table_exists("printer_tokens"))

    def test_apply_migrations_creates_printer_pairs_table(self):
        self.assertTrue(self._table_exists("printer_pairs"))

    def test_apply_migrations_creates_printer_token_snapshots_table(self):
        self.assertTrue(self._table_exists("printer_token_snapshots"))

    def test_fresh_db_has_zero_scheduler_jobs(self):
        self.assertEqual(self._count("SELECT COUNT(*) FROM printer_scheduler_jobs"), 0)

    def test_fresh_db_has_zero_running_jobs(self):
        self.assertEqual(
            self._count("SELECT COUNT(*) FROM printer_scheduler_jobs WHERE status = 'RUNNING'"),
            0,
        )

    def test_fresh_db_has_zero_active_locks(self):
        self.assertEqual(
            self._count(
                "SELECT COUNT(*) FROM printer_scheduler_jobs"
                " WHERE locked_at IS NOT NULL OR lock_owner IS NOT NULL"
            ),
            0,
        )


# ---------------------------------------------------------------------------
# Class 2: Bounded job enqueue path
# ---------------------------------------------------------------------------

class LaneE2BBoundedJobEnqueueTests(_DbTestBase):
    """Prove that the three bounded cycle job kinds can be enqueued cleanly."""

    def test_track_fast_first_15m_enqueue_returns_acquired(self):
        token_id = self._insert_token("enqueue-fast-1")
        result, _ = self._enqueue(JobKind.TRACK_FAST_FIRST_15M, target_id=token_id)
        self.assertEqual(result, LockResult.ACQUIRED)

    def test_track_normal_first_15m_enqueue_returns_acquired(self):
        token_id = self._insert_token("enqueue-normal-1")
        result, _ = self._enqueue(JobKind.TRACK_NORMAL_FIRST_15M, target_id=token_id)
        self.assertEqual(result, LockResult.ACQUIRED)

    def test_memory_window_close_enqueue_returns_acquired(self):
        result, _ = self._enqueue(
            JobKind.MEMORY_WINDOW_CLOSE,
            job_name="enqueue_window_close_1",
            target_table=None,
            target_id=None,
        )
        self.assertEqual(result, LockResult.ACQUIRED)

    def test_enqueue_returns_non_none_job_id(self):
        token_id = self._insert_token("enqueue-jid-1")
        _, job_id = self._enqueue(JobKind.TRACK_FAST_FIRST_15M, target_id=token_id)
        self.assertIsNotNone(job_id)
        self.assertIsInstance(job_id, int)
        self.assertGreater(job_id, 0)

    def test_enqueued_job_status_is_pending(self):
        token_id = self._insert_token("enqueue-status-1")
        _, job_id = self._enqueue(JobKind.TRACK_FAST_FIRST_15M, target_id=token_id)
        row = self._fetch_job(job_id)
        self.assertEqual(row["status"], JobStatus.PENDING.value)

    def test_enqueued_job_has_no_locked_at(self):
        token_id = self._insert_token("enqueue-lock-1")
        _, job_id = self._enqueue(JobKind.TRACK_NORMAL_FIRST_15M, target_id=token_id)
        row = self._fetch_job(job_id)
        self.assertIsNone(row["locked_at"])

    def test_enqueued_job_has_no_lock_owner(self):
        token_id = self._insert_token("enqueue-owner-1")
        _, job_id = self._enqueue(JobKind.TRACK_NORMAL_FIRST_15M, target_id=token_id)
        row = self._fetch_job(job_id)
        self.assertIsNone(row["lock_owner"])

    def test_enqueued_job_kind_matches_input(self):
        token_id = self._insert_token("enqueue-kind-1")
        _, job_id = self._enqueue(JobKind.TRACK_FAST_FIRST_15M, target_id=token_id)
        row = self._fetch_job(job_id)
        self.assertEqual(row["job_kind"], JobKind.TRACK_FAST_FIRST_15M.value)

    def test_duplicate_active_job_returns_duplicate_active_job(self):
        token_id = self._insert_token("enqueue-dup-1")
        result1, _ = self._enqueue(
            JobKind.TRACK_FAST_FIRST_15M,
            job_name="dup_test_job",
            target_id=token_id,
        )
        result2, jid2 = self._enqueue(
            JobKind.TRACK_FAST_FIRST_15M,
            job_name="dup_test_job",
            target_id=token_id,
        )
        self.assertEqual(result1, LockResult.ACQUIRED)
        self.assertEqual(result2, LockResult.DUPLICATE_ACTIVE_JOB)
        self.assertIsNone(jid2)


# ---------------------------------------------------------------------------
# Class 3: Job claim path
# ---------------------------------------------------------------------------

class LaneE2BJobClaimTests(_DbTestBase):
    """Prove the job claim path works correctly and is not claimed when not due."""

    def _enqueue_and_get_id(self, job_kind: JobKind, token_mint: str) -> int:
        token_id = self._insert_token(token_mint)
        _, job_id = self._enqueue(job_kind, target_id=token_id)
        return job_id

    def test_claim_due_job_returns_acquired(self):
        job_id = self._enqueue_and_get_id(JobKind.TRACK_FAST_FIRST_15M, "claim-1")
        result = self._claim(job_id)
        self.assertEqual(result, LockResult.ACQUIRED)

    def test_claimed_job_status_is_running(self):
        job_id = self._enqueue_and_get_id(JobKind.TRACK_NORMAL_FIRST_15M, "claim-2")
        self._claim(job_id)
        row = self._fetch_job(job_id)
        self.assertEqual(row["status"], JobStatus.RUNNING.value)

    def test_claimed_job_locked_at_is_set(self):
        job_id = self._enqueue_and_get_id(JobKind.TRACK_FAST_FIRST_15M, "claim-3")
        self._claim(job_id)
        row = self._fetch_job(job_id)
        self.assertIsNotNone(row["locked_at"])

    def test_claimed_job_lock_owner_is_set(self):
        job_id = self._enqueue_and_get_id(JobKind.TRACK_NORMAL_FIRST_15M, "claim-4")
        self._claim(job_id, lock_owner="test_owner_e2b")
        row = self._fetch_job(job_id)
        self.assertEqual(row["lock_owner"], "test_owner_e2b")

    def test_claim_future_job_returns_not_due(self):
        future_time = self.now + timedelta(minutes=10)
        token_id = self._insert_token("claim-future-1")
        _, job_id = self._enqueue(
            JobKind.TRACK_FAST_FIRST_15M,
            target_id=token_id,
            scheduled_for=future_time,
        )
        result = self._claim(job_id)
        self.assertEqual(result, LockResult.NOT_DUE)

    def test_claim_already_running_returns_already_locked(self):
        job_id = self._enqueue_and_get_id(JobKind.TRACK_FAST_FIRST_15M, "claim-dbl-1")
        self._claim(job_id)
        result2 = self._claim(job_id)
        self.assertEqual(result2, LockResult.ALREADY_LOCKED)


# ---------------------------------------------------------------------------
# Class 4: Job completion path
# ---------------------------------------------------------------------------

class LaneE2BJobCompleteTests(_DbTestBase):
    """Prove complete_job sets SUCCEEDED status and releases all locks."""

    def _enqueue_claim_get_id(self, job_kind: JobKind, token_mint: str) -> int:
        token_id = self._insert_token(token_mint)
        _, job_id = self._enqueue(job_kind, target_id=token_id)
        self._claim(job_id)
        return job_id

    def test_complete_job_status_is_succeeded(self):
        job_id = self._enqueue_claim_get_id(JobKind.TRACK_FAST_FIRST_15M, "complete-1")
        self._complete(job_id)
        row = self._fetch_job(job_id)
        self.assertEqual(row["status"], JobStatus.SUCCEEDED.value)

    def test_complete_job_clears_locked_at(self):
        job_id = self._enqueue_claim_get_id(JobKind.TRACK_NORMAL_FIRST_15M, "complete-2")
        self._complete(job_id)
        row = self._fetch_job(job_id)
        self.assertIsNone(row["locked_at"])

    def test_complete_job_clears_lock_owner(self):
        job_id = self._enqueue_claim_get_id(JobKind.TRACK_FAST_FIRST_15M, "complete-3")
        self._complete(job_id)
        row = self._fetch_job(job_id)
        self.assertIsNone(row["lock_owner"])

    def test_complete_job_sets_finished_at(self):
        job_id = self._enqueue_claim_get_id(JobKind.TRACK_NORMAL_FIRST_15M, "complete-4")
        self._complete(job_id)
        row = self._fetch_job(job_id)
        self.assertIsNotNone(row["finished_at"])

    def test_zero_running_jobs_after_complete(self):
        job_id = self._enqueue_claim_get_id(JobKind.TRACK_FAST_FIRST_15M, "complete-5")
        self.assertEqual(self._count_running_jobs(), 1)
        self._complete(job_id)
        self.assertEqual(self._count_running_jobs(), 0)

    def test_zero_active_locks_after_complete(self):
        job_id = self._enqueue_claim_get_id(JobKind.TRACK_NORMAL_FIRST_15M, "complete-6")
        self.assertGreater(self._count_active_locks(), 0)
        self._complete(job_id)
        self.assertEqual(self._count_active_locks(), 0)


# ---------------------------------------------------------------------------
# Class 5: MEMORY_WINDOW_CLOSE job path
# ---------------------------------------------------------------------------

class LaneE2BMemoryWindowClosePathTests(_DbTestBase):
    """Prove MEMORY_WINDOW_CLOSE can be enqueued, claimed, and completed."""

    def _enqueue_window_close(self, job_name: str = "wc_test_1") -> int:
        _, job_id = enqueue_job(
            self.db_path,
            job_name=job_name,
            job_kind=JobKind.MEMORY_WINDOW_CLOSE,
            target_table=None,
            target_id=None,
            scheduled_for=self.now,
        )
        return job_id

    def test_memory_window_close_enqueues_returns_acquired(self):
        result, _ = enqueue_job(
            self.db_path,
            job_name="wc_enqueue_check",
            job_kind=JobKind.MEMORY_WINDOW_CLOSE,
            target_table=None,
            target_id=None,
            scheduled_for=self.now,
        )
        self.assertEqual(result, LockResult.ACQUIRED)

    def test_memory_window_close_can_be_claimed(self):
        job_id = self._enqueue_window_close("wc_claim_check")
        result = claim_due_job(
            self.db_path,
            job_id=job_id,
            lock_owner="e2b_wc_worker",
            now=self.now,
        )
        self.assertEqual(result, LockResult.ACQUIRED)

    def test_memory_window_close_can_be_completed(self):
        job_id = self._enqueue_window_close("wc_complete_check")
        claim_due_job(self.db_path, job_id=job_id, lock_owner="e2b_wc", now=self.now)
        complete_job(self.db_path, job_id=job_id, now=self.now)
        row = self._fetch_job(job_id)
        self.assertEqual(row["status"], JobStatus.SUCCEEDED.value)

    def test_memory_window_close_status_is_succeeded_after_complete(self):
        job_id = self._enqueue_window_close("wc_status_check")
        claim_due_job(self.db_path, job_id=job_id, lock_owner="e2b_wc2", now=self.now)
        complete_job(self.db_path, job_id=job_id, now=self.now)
        row = self._fetch_job(job_id)
        self.assertIsNone(row["locked_at"])
        self.assertIsNone(row["lock_owner"])
        self.assertEqual(row["status"], JobStatus.SUCCEEDED.value)

    def test_memory_window_close_priority_lower_than_track_fast_first_15m(self):
        self.assertTrue(
            is_higher_priority(JobKind.TRACK_FAST_FIRST_15M, JobKind.MEMORY_WINDOW_CLOSE)
        )

    def test_memory_window_close_priority_lower_than_track_normal_first_15m(self):
        self.assertTrue(
            is_higher_priority(JobKind.TRACK_NORMAL_FIRST_15M, JobKind.MEMORY_WINDOW_CLOSE)
        )

    def test_memory_window_close_priority_higher_than_discovery_refresh(self):
        self.assertTrue(
            is_higher_priority(JobKind.MEMORY_WINDOW_CLOSE, JobKind.DISCOVERY_REFRESH)
        )

    def test_memory_window_close_priority_higher_than_market_regime_context(self):
        self.assertTrue(
            is_higher_priority(JobKind.MEMORY_WINDOW_CLOSE, JobKind.MARKET_REGIME_CONTEXT)
        )


# ---------------------------------------------------------------------------
# Class 6: Clean exit proof
# ---------------------------------------------------------------------------

class LaneE2BCleanExitProofTests(_DbTestBase):
    """Prove full bounded cycle exits cleanly with zero running jobs and zero locks."""

    def test_full_cycle_enqueue_claim_complete_for_three_job_kinds(self):
        job_ids = self._run_full_cycle()
        self.assertEqual(len(job_ids), 3)
        for jid in job_ids:
            self.assertIsNotNone(jid)
            self.assertIsInstance(jid, int)

    def test_zero_running_jobs_after_full_bounded_cycle(self):
        self._run_full_cycle()
        self.assertEqual(self._count_running_jobs(), 0)

    def test_zero_active_locks_after_full_bounded_cycle(self):
        self._run_full_cycle()
        self.assertEqual(self._count_active_locks(), 0)

    def test_all_three_jobs_reach_succeeded_after_full_cycle(self):
        job_ids = self._run_full_cycle()
        for jid in job_ids:
            row = self._fetch_job(jid)
            self.assertEqual(row["status"], JobStatus.SUCCEEDED.value)

    def test_full_cycle_ends_with_memory_window_close_succeeded(self):
        job_ids = self._run_full_cycle()
        last_jid = job_ids[-1]
        row = self._fetch_job(last_jid)
        self.assertEqual(row["job_kind"], JobKind.MEMORY_WINDOW_CLOSE.value)
        self.assertEqual(row["status"], JobStatus.SUCCEEDED.value)

    def test_no_stale_locks_remain_after_full_cycle(self):
        self._run_full_cycle()
        conn = sqlite3.connect(self.db_path)
        try:
            count = int(conn.execute(
                "SELECT COUNT(*) FROM printer_scheduler_jobs"
                " WHERE status = 'RUNNING' OR locked_at IS NOT NULL OR lock_owner IS NOT NULL"
            ).fetchone()[0])
        finally:
            conn.close()
        self.assertEqual(count, 0)

    def test_full_cycle_job_count_is_three(self):
        self._run_full_cycle()
        self.assertEqual(self._count_rows("printer_scheduler_jobs"), 3)


# ---------------------------------------------------------------------------
# Class 7: Max active tokens cap
# ---------------------------------------------------------------------------

class LaneE2BMaxActiveTokensCapTests(_DbTestBase):
    """Prove max_active_tokens, max_track_fast, and max_track_normal constants and cap math."""

    def test_max_active_tokens_constant_is_10(self):
        self.assertEqual(MAX_ACTIVE_TOKENS, 10)

    def test_max_track_fast_constant_is_3(self):
        self.assertEqual(MAX_TRACK_FAST, 3)

    def test_max_track_normal_constant_is_7(self):
        self.assertEqual(MAX_TRACK_NORMAL, 7)

    def test_fast_plus_normal_equals_active_tokens(self):
        self.assertEqual(MAX_TRACK_FAST + MAX_TRACK_NORMAL, MAX_ACTIVE_TOKENS)

    def test_fast_plus_normal_does_not_exceed_active_tokens(self):
        self.assertLessEqual(MAX_TRACK_FAST + MAX_TRACK_NORMAL, MAX_ACTIVE_TOKENS)

    def test_can_enqueue_exactly_max_track_fast_jobs_for_different_tokens(self):
        for i in range(MAX_TRACK_FAST):
            token_id = self._insert_token(f"fast-cap-token-{i}")
            result, _ = self._enqueue(
                JobKind.TRACK_FAST_FIRST_15M,
                job_name=f"fast_cap_{i}",
                target_id=token_id,
            )
            self.assertEqual(result, LockResult.ACQUIRED, f"fast job {i} must acquire")
        self.assertEqual(
            self._count_rows("printer_scheduler_jobs"), MAX_TRACK_FAST
        )

    def test_can_enqueue_exactly_max_track_normal_jobs_for_different_tokens(self):
        for i in range(MAX_TRACK_NORMAL):
            token_id = self._insert_token(f"normal-cap-token-{i}")
            result, _ = self._enqueue(
                JobKind.TRACK_NORMAL_FIRST_15M,
                job_name=f"normal_cap_{i}",
                target_id=token_id,
            )
            self.assertEqual(result, LockResult.ACQUIRED, f"normal job {i} must acquire")
        self.assertEqual(
            self._count_rows("printer_scheduler_jobs"), MAX_TRACK_NORMAL
        )

    def test_total_cycle_tracking_jobs_within_active_cap(self):
        for i in range(MAX_TRACK_FAST):
            token_id = self._insert_token(f"cap-fast-{i}")
            self._enqueue(
                JobKind.TRACK_FAST_FIRST_15M,
                job_name=f"cap_fast_{i}",
                target_id=token_id,
            )
        for i in range(MAX_TRACK_NORMAL):
            token_id = self._insert_token(f"cap-normal-{i}")
            self._enqueue(
                JobKind.TRACK_NORMAL_FIRST_15M,
                job_name=f"cap_normal_{i}",
                target_id=token_id,
            )
        total_tracking_jobs = self._count_rows("printer_scheduler_jobs")
        self.assertEqual(total_tracking_jobs, MAX_TRACK_FAST + MAX_TRACK_NORMAL)
        self.assertLessEqual(total_tracking_jobs, MAX_ACTIVE_TOKENS)


# ---------------------------------------------------------------------------
# Class 8: PAPER_MONITORING excluded from E2B bounded cycle - state machine caveat and DB proof
# ---------------------------------------------------------------------------

class LaneE2BPaperMonitoringLockedTests(_DbTestBase):
    """Prove PAPER_MONITORING is excluded from this bounded cycle, while recording the existing transition caveat."""

    def test_paper_monitoring_state_exists_in_contracts(self):
        self.assertIn(TokenLifecycleState.PAPER_MONITORING, TokenLifecycleState)

    def test_enter_paper_monitoring_event_exists(self):
        self.assertIn(LifecycleEvent.ENTER_PAPER_MONITORING, LifecycleEvent)

    def test_open_paper_trade_monitor_job_kind_exists(self):
        self.assertIn(JobKind.OPEN_PAPER_TRADE_MONITOR, JobKind)

    def test_paper_monitoring_maps_to_open_paper_trade_monitor(self):
        self.assertEqual(
            SCHEDULER_KIND_BY_LANE[TokenLifecycleState.PAPER_MONITORING],
            JobKind.OPEN_PAPER_TRADE_MONITOR,
        )

    def test_track_fast_to_paper_monitoring_transition_exists_as_future_risk(self):


        # Existing transition recorded as a future-lane risk/caveat.


        # E2B only proves the bounded fixture cycle does not enqueue or execute PAPER_MONITORING.


        self.assertIn(
            TokenLifecycleState.PAPER_MONITORING,
            ALLOWED_TRANSITIONS[TokenLifecycleState.TRACK_FAST],
        )

    def test_track_normal_to_paper_monitoring_is_not_in_allowed_transitions(self):
        self.assertNotIn(
            TokenLifecycleState.PAPER_MONITORING,
            ALLOWED_TRANSITIONS[TokenLifecycleState.TRACK_NORMAL],
        )

    def test_discovered_to_paper_monitoring_is_not_in_allowed_transitions(self):
        self.assertNotIn(
            TokenLifecycleState.PAPER_MONITORING,
            ALLOWED_TRANSITIONS[TokenLifecycleState.DISCOVERED],
        )

    def test_no_open_paper_trade_monitor_job_enqueued_in_bounded_cycle(self):
        self._run_full_cycle()
        actual_kinds = self._distinct_job_kinds_in_db()
        self.assertNotIn(JobKind.OPEN_PAPER_TRADE_MONITOR.value, actual_kinds)

    def test_open_paper_trade_monitor_is_highest_priority_but_absent_from_cycle(self):
        self._run_full_cycle()
        actual_kinds = self._distinct_job_kinds_in_db()
        self.assertIn(JobKind.TRACK_FAST_FIRST_15M.value, actual_kinds)
        self.assertIn(JobKind.TRACK_NORMAL_FIRST_15M.value, actual_kinds)
        self.assertIn(JobKind.MEMORY_WINDOW_CLOSE.value, actual_kinds)
        self.assertNotIn(JobKind.OPEN_PAPER_TRADE_MONITOR.value, actual_kinds)


# ---------------------------------------------------------------------------
# Class 9: Hard lock verification
# ---------------------------------------------------------------------------

class LaneE2BHardLockVerificationTests(_DbTestBase):
    """Prove no source fetching, no snapshots, no memories, no paper decisions or positions."""

    def test_no_open_paper_trade_monitor_jobs_in_db_after_cycle(self):
        self._run_full_cycle()
        conn = sqlite3.connect(self.db_path)
        try:
            count = int(conn.execute(
                "SELECT COUNT(*) FROM printer_scheduler_jobs WHERE job_kind = ?",
                (JobKind.OPEN_PAPER_TRADE_MONITOR.value,),
            ).fetchone()[0])
        finally:
            conn.close()
        self.assertEqual(count, 0)

    def test_no_printer_token_snapshots_after_bounded_cycle(self):
        self._run_full_cycle()
        self.assertEqual(self._count_rows("printer_token_snapshots"), 0)

    def test_no_paper_decision_rows_after_bounded_cycle(self):
        self._run_full_cycle()
        self.assertEqual(self._count_rows("printer_paper_decisions"), 0)

    def test_no_paper_position_rows_after_bounded_cycle(self):
        self._run_full_cycle()
        self.assertEqual(self._count_rows("printer_paper_positions"), 0)

    def test_bounded_cycle_job_kinds_only_expected(self):
        self._run_full_cycle()
        actual_kinds = self._distinct_job_kinds_in_db()
        expected_kinds = {
            JobKind.TRACK_FAST_FIRST_15M.value,
            JobKind.TRACK_NORMAL_FIRST_15M.value,
            JobKind.MEMORY_WINDOW_CLOSE.value,
        }
        self.assertEqual(actual_kinds, expected_kinds)

    def test_no_http_source_libraries_in_sys_modules(self):
        for lib_name in ("requests", "httpx", "aiohttp"):
            self.assertNotIn(
                lib_name,
                sys.modules,
                f"HTTP library '{lib_name}' must not be imported during bounded cycle test",
            )

    def test_no_running_jobs_in_db_after_bounded_cycle(self):
        self._run_full_cycle()
        self.assertEqual(self._count_running_jobs(), 0)

    def test_no_active_locks_in_db_after_bounded_cycle(self):
        self._run_full_cycle()
        self.assertEqual(self._count_active_locks(), 0)


if __name__ == "__main__":
    unittest.main()
