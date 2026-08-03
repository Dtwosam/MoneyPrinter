"""Focused tests for discovery Scheduler claim-at-work-start repair.

Offline disposable DBs only. No provider, RPC, WebSocket, operational command,
public composition, authorization, or financial capability.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
import os
from pathlib import Path
import sqlite3
import tempfile
import unittest
from unittest.mock import patch

from printer_v1.db import apply_migrations
from printer_v1.discovery.combined_executor import (
    CombinedDiscoveryError,
    CombinedDiscoveryFixtures,
    CombinedPumpfunCampaignExecutor,
    _Usage,
)
from printer_v1.discovery.persistence import insert_discovery_batch
from printer_v1.discovery.scheduler_parity import (
    reconcile_discovery_work_jobs,
    terminalize_scheduler_job_for_work,
)
from printer_v1.operator_cli.abstract_campaign_command import (
    AbstractCampaignCommand,
    CAMPAIGN_MODE,
    CampaignCeilings,
)
from printer_v1.operator_cli.campaign_ownership import create_campaign_run
from printer_v1.operator_cli.campaign_persistence import (
    DB_MODE_PROOF_ISOLATED,
    create_campaign,
)
from printer_v1.scheduler.contracts import JobKind, JobStatus, LockResult
from printer_v1.scheduler.scheduler import (
    cancel_job,
    claim_due_job,
    complete_job,
    enqueue_job,
    reset_scheduler_operation_observer,
    set_scheduler_operation_observer,
)


NOW = "2026-08-03T12:00:00+00:00"
CUTOFF = "2026-08-03T12:06:00+00:00"
CAMPAIGN = "campaign-claim"
RUN = "run-claim"
CYCLE = "cycle-claim"
BATCH = f"discovery-batch:{CAMPAIGN}:{RUN}:{CYCLE}"
WORK_TYPE = "DISCOVERY_IDENTITY_MERGE"
WORK_ID = f"work:{WORK_TYPE}:{BATCH}"
LOCK_OWNER = f"discovery-work:{WORK_ID}"
JOB_NAME = f"{WORK_TYPE}:{BATCH}"


class DiscoverySchedulerClaimAtWorkStartTests(unittest.TestCase):
    def setUp(self) -> None:
        parent = os.environ.get("TEMP") or os.environ.get("TMP")
        self.temp = tempfile.TemporaryDirectory(dir=parent)
        self.db = Path(self.temp.name) / "claim-at-work-start.sqlite3"
        apply_migrations(self.db)
        ceilings = CampaignCeilings(
            campaign_count=1,
            cycle_count=1,
            duration_seconds=3600,
            source_calls=45,
            scheduler_work=40,
            storage_bytes=8_000_000,
            failures=10,
        )
        provenance = {
            "git_head": "d" * 40,
            "git_tracked_tree_clean": True,
            "git_staged_changes_present": False,
            "git_unstaged_changes_present": False,
            "git_untracked_present": True,
            "git_provenance_captured_at": NOW,
        }
        configuration = {
            "token_capacity": 2,
            "ceilings": {
                "campaign_count": 1,
                "cycle_count": 1,
                "duration_seconds": 3600,
                "source_calls": 45,
                "scheduler_work": 40,
                "storage_bytes": 8_000_000,
                "failures": 10,
            },
            "campaign_selection_seed": "seed",
            "report_directory_identity": "path-sha256:" + "e" * 64,
            "backup_preflight_references": {
                "preflight_status": "READY",
                "source_identity": "sha256:" + "a" * 64,
                "backup_sha256": "b" * 64,
                "required_migration": "032_campaign_ownership_schema.sql",
                "latest_migration": "050_token_slot_id_projection.sql",
            },
        }
        created = create_campaign(
            self.db,
            campaign_id=CAMPAIGN,
            configuration_id="configuration-claim",
            configuration=configuration,
            launch_provenance=provenance,
            db_mode=DB_MODE_PROOF_ISOLATED,
            db_target_identity="isolated-claim",
            proof_source_db_identity="source-claim",
            policy_version="v2-9.8b-claim",
        )
        self.connection = sqlite3.connect(self.db)
        self.connection.row_factory = sqlite3.Row
        self.connection.execute("PRAGMA foreign_keys=ON")
        create_campaign_run(
            self.connection,
            campaign_id=CAMPAIGN,
            run_id=RUN,
            run_ordinal=1,
            now=NOW,
        )
        with self.connection:
            self.connection.execute(
                """
                INSERT INTO printer_memory_factory_campaign_cycles(
                    cycle_id, campaign_id, run_id, cycle_ordinal, cycle_state,
                    created_at, updated_at
                ) VALUES (?, ?, ?, 1, 'PLANNED', ?, ?)
                """,
                (CYCLE, CAMPAIGN, RUN, NOW, NOW),
            )
            self.connection.execute(
                "UPDATE printer_memory_factory_campaigns SET campaign_state='RUNNING'"
            )
            self.connection.execute(
                "UPDATE printer_memory_factory_campaign_runs SET run_state='RUNNING'"
            )
        insert_discovery_batch(
            self.connection,
            discovery_batch_id=BATCH,
            campaign_id=CAMPAIGN,
            configuration_id="configuration-claim",
            run_id=RUN,
            cycle_id=CYCLE,
            cycle_cutoff=CUTOFF,
            policy_version="v2-9.8b-claim",
            provider_contract_versions={"direct": "fixture"},
            git_provenance_identity="git-claim",
            campaign_selection_seed_identity="seed",
            cycle_seed_hash="a" * 64,
            pump_continuity_state="UNKNOWN",
            batch_state="DISCOVERING",
            now=NOW,
        )
        self.connection.commit()
        self.command = AbstractCampaignCommand(
            mode=CAMPAIGN_MODE,
            db_path=self.db,
            db_target_identity="isolated-claim",
            campaign_id=CAMPAIGN,
            configuration_id="configuration-claim",
            configuration_hash=str(created["configuration_hash"]),
            policy_version="v2-9.8b-claim",
            token_capacity=2,
            ceilings=ceilings,
            report_directory=Path(self.temp.name),
            report_directory_identity="path-sha256:" + "e" * 64,
            launch_git_provenance=provenance,
            run_id=RUN,
            report_id="report-claim",
        )
        self.fixtures = CombinedDiscoveryFixtures(
            cycle_id=CYCLE,
            cycle_cutoff=CUTOFF,
            campaign_selection_seed="seed",
            provider_contract_versions={"direct": "fixture"},
            git_provenance_identity="git-claim",
            evaluated_at=NOW,
        )
        self.executor = CombinedPumpfunCampaignExecutor(self.fixtures)
        self.usage = _Usage()
        self.events: list[dict] = []
        self.observer_token = set_scheduler_operation_observer(
            lambda event: self.events.append(dict(event))
        )

    def tearDown(self) -> None:
        reset_scheduler_operation_observer(self.observer_token)
        try:
            self.connection.close()
        except Exception:
            pass
        try:
            self.temp.cleanup()
        except Exception:
            pass

    def _create(self) -> str:
        return self.executor._create_work(
            self.connection,
            self.command,
            self.usage,
            BATCH,
            WORK_TYPE,
            NOW,
        )

    def _job(self, job_id: int) -> sqlite3.Row:
        row = self.connection.execute(
            "SELECT * FROM printer_scheduler_jobs WHERE id=?",
            (job_id,),
        ).fetchone()
        self.assertIsNotNone(row)
        return row

    def _work(self, work_id: str = WORK_ID) -> sqlite3.Row | None:
        return self.connection.execute(
            "SELECT * FROM printer_discovery_work WHERE discovery_work_id=?",
            (work_id,),
        ).fetchone()

    def test_success_records_enqueue_claim_terminal_order_and_lock_fields(self) -> None:
        work_id = self._create()
        self.assertEqual(work_id, WORK_ID)
        work = self._work()
        self.assertIsNotNone(work)
        assert work is not None
        job_id = int(work["scheduler_job_id"])
        job = self._job(job_id)
        self.assertEqual(job["status"], JobStatus.RUNNING.value)
        self.assertEqual(job["lock_owner"], LOCK_OWNER)
        self.assertIsNotNone(job["locked_at"])
        self.assertIsNotNone(job["started_at"])
        self.assertEqual(job["job_kind"], JobKind.DISCOVERY_REFRESH.value)
        self.assertEqual(job["job_name"], JOB_NAME)
        self.assertEqual(work["work_state"], "RUNNING")

        boundaries = [
            event["boundary"]
            for event in self.events
            if int(event.get("scheduler_job_id") or 0) == job_id
        ]
        self.assertEqual(
            boundaries,
            ["SCHEDULER_ENQUEUE", "SCHEDULER_CLAIM"],
        )

        self.executor._terminalize_work(
            self.connection, work_id, "SUCCEEDED", "MERGE_COMPLETE", NOW
        )
        job = self._job(job_id)
        self.assertEqual(job["status"], JobStatus.SUCCEEDED.value)
        self.assertIsNone(job["lock_owner"])
        self.assertIsNone(job["locked_at"])
        boundaries = [
            event["boundary"]
            for event in self.events
            if int(event.get("scheduler_job_id") or 0) == job_id
        ]
        self.assertEqual(
            boundaries,
            ["SCHEDULER_ENQUEUE", "SCHEDULER_CLAIM", "SCHEDULER_TERMINAL"],
        )
        terminal = [
            event
            for event in self.events
            if event.get("boundary") == "SCHEDULER_TERMINAL"
            and int(event.get("scheduler_job_id") or 0) == job_id
        ][0]
        self.assertEqual(terminal["terminal_state"], JobStatus.SUCCEEDED.value)

    def test_exact_linked_job_claimed_other_pending_untouched(self) -> None:
        other_result, other_id = enqueue_job(
            self.connection,
            job_name="unrelated-pending",
            job_kind=JobKind.DISCOVERY_REFRESH,
            scheduled_for=datetime.fromisoformat(NOW.replace("Z", "+00:00")),
        )
        self.assertEqual(str(other_result), LockResult.ACQUIRED.value)
        self.assertIsNotNone(other_id)
        assert other_id is not None
        work_id = self._create()
        work = self._work(work_id)
        assert work is not None
        claimed_id = int(work["scheduler_job_id"])
        self.assertNotEqual(claimed_id, int(other_id))
        other = self._job(int(other_id))
        self.assertEqual(other["status"], JobStatus.PENDING.value)
        self.assertIsNone(other["lock_owner"])
        self.assertIsNone(other["locked_at"])
        claimed = self._job(claimed_id)
        self.assertEqual(claimed["status"], JobStatus.RUNNING.value)
        self.assertEqual(claimed["lock_owner"], LOCK_OWNER)

    def test_work_not_inserted_before_successful_claim(self) -> None:
        with patch(
            "printer_v1.discovery.combined_executor.claim_due_job",
            return_value=LockResult.NOT_DUE,
        ) as claim_mock:
            with self.assertRaises(CombinedDiscoveryError) as raised:
                self._create()
        self.assertEqual(raised.exception.code, "DISCOVERY_SCHEDULER_CLAIM_NOT_DUE")
        claim_mock.assert_called_once()
        self.assertIsNone(self._work())
        # Enqueued residue must be terminalized (unclaimed PENDING cancel).
        rows = self.connection.execute(
            "SELECT status, lock_owner FROM printer_scheduler_jobs "
            "WHERE job_name=?",
            (JOB_NAME,),
        ).fetchall()
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["status"], JobStatus.CANCELLED.value)
        self.assertIsNone(rows[0]["lock_owner"])

    def test_not_found_already_owned_and_identity_mismatch_fail_closed(self) -> None:
        with patch(
            "printer_v1.discovery.combined_executor.claim_due_job",
            return_value=LockResult.NOT_FOUND,
        ):
            with self.assertRaises(CombinedDiscoveryError) as raised:
                self._create()
        self.assertEqual(raised.exception.code, "DISCOVERY_SCHEDULER_CLAIM_NOT_FOUND")
        self.assertIsNone(self._work())

        self.tearDown()
        self.setUp()
        with patch(
            "printer_v1.discovery.combined_executor.claim_due_job",
            return_value=LockResult.ALREADY_LOCKED,
        ):
            with self.assertRaises(CombinedDiscoveryError) as raised:
                self._create()
        self.assertEqual(
            raised.exception.code, "DISCOVERY_SCHEDULER_CLAIM_ALREADY_OWNED"
        )
        self.assertIsNone(self._work())

        self.tearDown()
        self.setUp()
        real_claim = claim_due_job

        def claim_then_corrupt(*args, **kwargs):
            result = real_claim(*args, **kwargs)
            job_id = int(kwargs["job_id"])
            self.connection.execute(
                "UPDATE printer_scheduler_jobs SET job_kind=? WHERE id=?",
                (JobKind.TRACK_NORMAL_FIRST_15M.value, job_id),
            )
            return result

        with patch(
            "printer_v1.discovery.combined_executor.claim_due_job",
            side_effect=claim_then_corrupt,
        ):
            with self.assertRaises(CombinedDiscoveryError) as raised:
                self._create()
        self.assertEqual(
            raised.exception.code, "DISCOVERY_SCHEDULER_CLAIM_IDENTITY_MISMATCH"
        )
        self.assertIsNone(self._work())
        job = self.connection.execute(
            "SELECT status, lock_owner FROM printer_scheduler_jobs WHERE job_name=?",
            (JOB_NAME,),
        ).fetchone()
        self.assertEqual(job["status"], JobStatus.CANCELLED.value)
        self.assertIsNone(job["lock_owner"])

    def test_failure_after_claim_before_work_insert_clears_lock(self) -> None:
        with patch(
            "printer_v1.discovery.combined_executor.insert_discovery_work",
            side_effect=RuntimeError("insert exploded"),
        ):
            with self.assertRaises(CombinedDiscoveryError) as raised:
                self._create()
        self.assertEqual(
            raised.exception.code, "DISCOVERY_SCHEDULER_JOB_LINK_MISMATCH"
        )
        self.assertIsNone(self._work())
        job = self.connection.execute(
            "SELECT status, lock_owner, locked_at FROM printer_scheduler_jobs "
            "WHERE job_name=?",
            (JOB_NAME,),
        ).fetchone()
        self.assertIsNotNone(job)
        self.assertEqual(job["status"], JobStatus.CANCELLED.value)
        self.assertIsNone(job["lock_owner"])
        self.assertIsNone(job["locked_at"])

    def test_already_owned_job_is_not_stolen(self) -> None:
        result, job_id = enqueue_job(
            self.connection,
            job_name=JOB_NAME,
            job_kind=JobKind.DISCOVERY_REFRESH,
            target_table="printer_discovery_batches",
            scheduled_for=datetime.fromisoformat(NOW.replace("Z", "+00:00")),
        )
        self.assertEqual(str(result), LockResult.ACQUIRED.value)
        assert job_id is not None
        claimed = claim_due_job(
            self.connection,
            job_id=int(job_id),
            lock_owner="foreign-worker",
            now=datetime.fromisoformat(NOW.replace("Z", "+00:00")),
        )
        self.assertEqual(claimed, LockResult.ACQUIRED)
        with self.assertRaises(CombinedDiscoveryError) as raised:
            self._create()
        self.assertEqual(
            raised.exception.code, "DISCOVERY_SCHEDULER_CLAIM_ALREADY_OWNED"
        )
        foreign = self._job(int(job_id))
        self.assertEqual(foreign["status"], JobStatus.RUNNING.value)
        self.assertEqual(foreign["lock_owner"], "foreign-worker")
        self.assertIsNone(self._work())

    def test_success_failure_cancel_reconcile_and_repeat_terminal_idempotent(
        self,
    ) -> None:
        work_id = self._create()
        work = self._work(work_id)
        assert work is not None
        job_id = int(work["scheduler_job_id"])

        self.executor._terminalize_work(
            self.connection, work_id, "SUCCEEDED", "OK", NOW
        )
        self.assertEqual(self._job(job_id)["status"], JobStatus.SUCCEEDED.value)
        # Repeated terminalization must not rewrite terminal state.
        applied = terminalize_scheduler_job_for_work(
            self.connection,
            job_id=job_id,
            work_state="FAILED",
            cause="SHOULD_NOT_APPLY",
        )
        self.assertIsNone(applied)
        self.assertEqual(self._job(job_id)["status"], JobStatus.SUCCEEDED.value)

        # Fresh unit for failure path.
        fail_type = "DISCOVERY_FIXED_ELIGIBILITY_GATES"
        fail_work = self.executor._create_work(
            self.connection,
            self.command,
            self.usage,
            BATCH,
            fail_type,
            NOW,
        )
        fail_row = self._work(fail_work)
        assert fail_row is not None
        fail_job = int(fail_row["scheduler_job_id"])
        self.executor._terminalize_work(
            self.connection, fail_work, "FAILED", "GATES_FAILED", NOW
        )
        self.assertEqual(self._job(fail_job)["status"], JobStatus.FAILED.value)

        # Pure cancel without prior claim remains lawful.
        cancel_result, cancel_id = enqueue_job(
            self.connection,
            job_name="pure-cancel",
            job_kind=JobKind.DISCOVERY_REFRESH,
            scheduled_for=datetime.fromisoformat(NOW.replace("Z", "+00:00")),
        )
        self.assertEqual(str(cancel_result), LockResult.ACQUIRED.value)
        assert cancel_id is not None
        cancel_job(self.connection, job_id=int(cancel_id))
        cancel_row = self._job(int(cancel_id))
        self.assertEqual(cancel_row["status"], JobStatus.CANCELLED.value)
        self.assertIsNone(cancel_row["lock_owner"])
        # No claim event required for pure cancel; only ENQUEUE + TERMINAL.
        cancel_boundaries = [
            event["boundary"]
            for event in self.events
            if int(event.get("scheduler_job_id") or 0) == int(cancel_id)
        ]
        self.assertEqual(
            cancel_boundaries,
            ["SCHEDULER_ENQUEUE", "SCHEDULER_TERMINAL"],
        )

        # Batch reconciliation leaves zero active/locked residue for this batch.
        running_type = "DISCOVERY_UNIFORM_SELECTION"
        running_work = self.executor._create_work(
            self.connection,
            self.command,
            self.usage,
            BATCH,
            running_type,
            NOW,
        )
        parity = reconcile_discovery_work_jobs(
            self.connection,
            discovery_batch_id=BATCH,
            abandoned_cause="TEST_RECONCILE",
        )
        self.assertGreaterEqual(parity["work_rows"], 1)
        self.assertEqual(parity["terminal_work_with_active_job"], 0)
        active = self.connection.execute(
            """
            SELECT COUNT(*) FROM printer_scheduler_jobs
            WHERE status IN ('PENDING', 'RUNNING', 'COOLDOWN')
            """
        ).fetchone()[0]
        locked = self.connection.execute(
            """
            SELECT COUNT(*) FROM printer_scheduler_jobs
            WHERE locked_at IS NOT NULL OR lock_owner IS NOT NULL
            """
        ).fetchone()[0]
        self.assertEqual(active, 0)
        self.assertEqual(locked, 0)
        del running_work

    def test_not_due_real_path_without_hiding_result(self) -> None:
        future = datetime.fromisoformat(NOW.replace("Z", "+00:00")) + timedelta(
            hours=1
        )
        result, job_id = enqueue_job(
            self.connection,
            job_name="future-job",
            job_kind=JobKind.DISCOVERY_REFRESH,
            scheduled_for=future,
        )
        self.assertEqual(str(result), LockResult.ACQUIRED.value)
        assert job_id is not None
        claim = claim_due_job(
            self.connection,
            job_id=int(job_id),
            lock_owner="probe",
            now=datetime.fromisoformat(NOW.replace("Z", "+00:00")),
        )
        self.assertEqual(claim, LockResult.NOT_DUE)
        # Exact-id claim primitive still returns NOT_DUE honestly.
        self.assertEqual(self._job(int(job_id))["status"], JobStatus.PENDING.value)


class DiscoveryClaimAtWorkStartLifecycleIsolationTests(unittest.TestCase):
    """Shared Scheduler claim primitive remains exact-id for lifecycle jobs."""

    def setUp(self) -> None:
        parent = os.environ.get("TEMP") or os.environ.get("TMP")
        self.temp = tempfile.TemporaryDirectory(dir=parent)
        self.db = Path(self.temp.name) / "lifecycle-claim.sqlite3"
        apply_migrations(self.db)

    def tearDown(self) -> None:
        try:
            self.temp.cleanup()
        except Exception:
            pass

    def test_lifecycle_exact_id_claim_untouched(self) -> None:
        now = datetime(2026, 8, 3, 12, 0, tzinfo=timezone.utc)
        events: list[dict] = []
        token = set_scheduler_operation_observer(lambda e: events.append(dict(e)))
        try:
            first_result, first_id = enqueue_job(
                self.db,
                job_name="lifecycle-a",
                job_kind=JobKind.TRACK_NORMAL_FIRST_15M,
                scheduled_for=now,
            )
            second_result, second_id = enqueue_job(
                self.db,
                job_name="lifecycle-b",
                job_kind=JobKind.TRACK_NORMAL_FIRST_15M,
                scheduled_for=now,
            )
            self.assertEqual(str(first_result), LockResult.ACQUIRED.value)
            self.assertEqual(str(second_result), LockResult.ACQUIRED.value)
            assert first_id is not None and second_id is not None
            claimed = claim_due_job(
                self.db,
                job_id=int(second_id),
                lock_owner="v2_4:factory-run",
                now=now,
            )
            self.assertEqual(claimed, LockResult.ACQUIRED)
            complete_job(self.db, job_id=int(second_id), now=now)
            conn = sqlite3.connect(self.db)
            conn.row_factory = sqlite3.Row
            try:
                first = conn.execute(
                    "SELECT status, lock_owner FROM printer_scheduler_jobs WHERE id=?",
                    (int(first_id),),
                ).fetchone()
                second = conn.execute(
                    "SELECT status, lock_owner FROM printer_scheduler_jobs WHERE id=?",
                    (int(second_id),),
                ).fetchone()
            finally:
                conn.close()
            self.assertEqual(first["status"], JobStatus.PENDING.value)
            self.assertIsNone(first["lock_owner"])
            self.assertEqual(second["status"], JobStatus.SUCCEEDED.value)
            self.assertIsNone(second["lock_owner"])
            second_boundaries = [
                event["boundary"]
                for event in events
                if int(event.get("scheduler_job_id") or 0) == int(second_id)
            ]
            self.assertEqual(
                second_boundaries,
                ["SCHEDULER_ENQUEUE", "SCHEDULER_CLAIM", "SCHEDULER_TERMINAL"],
            )
        finally:
            reset_scheduler_operation_observer(token)


if __name__ == "__main__":
    unittest.main()
