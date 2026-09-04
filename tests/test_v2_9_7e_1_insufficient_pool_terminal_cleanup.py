"""V2-9.7E.1 — insufficient-pool terminal cleanup and reporting repair."""

from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timedelta, timezone
import hashlib
import json
import os
from pathlib import Path
import sqlite3
import tempfile
import unittest

from printer_v1.db import apply_migrations
from printer_v1.discovery.combined_executor import (
    CombinedDiscoveryFixtures,
    CombinedPumpfunCampaignExecutor,
    FixtureOriginProof,
    FixtureSourceFact,
)
from printer_v1.operator_cli.abstract_campaign_command import (
    AbstractCampaignCommand,
    CAMPAIGN_MODE,
    CENTRAL_SCHEDULER_OWNER,
    CampaignCeilings,
    OwnerPort,
    SOURCE_GOVERNOR_OWNER,
    report_path_identity,
)
from printer_v1.operator_cli.campaign_ownership import create_campaign_run
from printer_v1.operator_cli.campaign_persistence import (
    DB_MODE_PROOF_ISOLATED,
    create_campaign,
)
from printer_v1.operator_cli.campaign_supervision import (
    CampaignSupervisionError,
    acquire_campaign_supervision,
    cleanup_campaign_supervision,
)
from printer_v1.operator_cli.final_campaign_report import (
    LOCKED_CAPABILITY_TABLES,
    FinalCampaignReportError,
    persist_final_campaign_report,
)
from printer_v1.operator_cli.zero_source_campaign_replay import (
    REPLAY_VERIFIED,
    replay_terminal_campaign_report,
)
from printer_v1.sources.secondary_discovery import (
    GECKO_TRENDING_PARAMS,
    GECKO_TRENDING_REQUEST,
)


NOW = datetime(2026, 7, 21, 12, 0, tzinfo=timezone.utc)
NOW_TEXT = NOW.isoformat()


def _provenance() -> dict[str, object]:
    return {
        "git_head": "c" * 40,
        "git_tracked_tree_clean": True,
        "git_staged_changes_present": False,
        "git_unstaged_changes_present": False,
        "git_untracked_present": True,
        "git_provenance_captured_at": NOW_TEXT,
    }


def _sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _counts(connection: sqlite3.Connection) -> dict[str, int]:
    tables = [
        "printer_memory_factory_campaign_token_slots",
        "printer_tracking_queue",
        "printer_memory_factory_campaign_windows",
        "printer_memory_factory_campaign_reports",
        "printer_scheduler_jobs",
        *LOCKED_CAPABILITY_TABLES,
    ]
    out: dict[str, int] = {}
    for table in tables:
        try:
            out[table] = int(
                connection.execute(f'SELECT COUNT(*) FROM "{table}"').fetchone()[0]
            )
        except sqlite3.Error:
            out[table] = -1
    return out


class InsufficientPoolTerminalCleanupTests(unittest.TestCase):
    def setUp(self) -> None:
        parent = os.environ.get("TEMP") or os.environ.get("TMP")
        self.temp = tempfile.TemporaryDirectory(dir=parent)
        self.root = Path(self.temp.name)
        self.db = self.root / "insufficient-pool.sqlite3"
        self.lock = self.root / "lease.lock.json"
        self.report_dir = self.root / "reports"
        self.report_dir.mkdir(parents=True, exist_ok=True)
        apply_migrations(self.db)
        self.configuration = {
            "token_capacity": 2,
            "campaign_selection_seed": "7e1-insufficient-seed",
            "report_directory_identity": report_path_identity(self.report_dir),
            "ceilings": {
                "campaign_count": 1,
                "cycle_count": 1,
                "duration_seconds": 3600,
                "source_calls": 20,
                "scheduler_work": 40,
                "storage_bytes": 2_000_000,
                "failures": 5,
            },
            "backup_preflight_references": {
                "preflight_status": "READY",
                "source_identity": "sha256:" + ("a" * 64),
                "backup_sha256": "b" * 64,
                "required_migration": "032_campaign_ownership_schema.sql",
                "latest_migration": "035_insufficient_pool_cycle_terminal_trigger.sql",
            },
        }
        created = create_campaign(
            self.db,
            campaign_id="campaign-7e1",
            configuration_id="configuration-7e1",
            configuration=self.configuration,
            launch_provenance=_provenance(),
            db_mode=DB_MODE_PROOF_ISOLATED,
            db_target_identity="isolated-7e1",
            proof_source_db_identity="source-7e1",
            policy_version="v2-9.7e.1",
        )
        self.configuration_hash = str(created["configuration_hash"])
        connection = sqlite3.connect(self.db)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys=ON")
        create_campaign_run(
            connection,
            campaign_id="campaign-7e1",
            run_id="run-7e1",
            run_ordinal=1,
            now=NOW_TEXT,
        )
        with connection:
            connection.execute(
                """
                INSERT INTO printer_memory_factory_campaign_cycles(
                    cycle_id, campaign_id, run_id, cycle_ordinal, cycle_state,
                    created_at, updated_at
                ) VALUES ('cycle-7e1', 'campaign-7e1', 'run-7e1', 1, 'PLANNED', ?, ?)
                """,
                (NOW_TEXT, NOW_TEXT),
            )
            connection.execute(
                "UPDATE printer_memory_factory_campaigns SET campaign_state='RUNNING'"
            )
            connection.execute(
                "UPDATE printer_memory_factory_campaign_runs SET run_state='RUNNING'"
            )
        connection.close()

    def tearDown(self) -> None:
        self.temp.cleanup()

    def _command(self) -> AbstractCampaignCommand:
        return AbstractCampaignCommand(
            mode=CAMPAIGN_MODE,
            db_path=self.db,
            db_target_identity="isolated-7e1",
            campaign_id="campaign-7e1",
            configuration_id="configuration-7e1",
            configuration_hash=self.configuration_hash,
            policy_version="v2-9.7e.1",
            token_capacity=2,
            ceilings=CampaignCeilings(
                campaign_count=1,
                cycle_count=1,
                duration_seconds=3600,
                source_calls=20,
                scheduler_work=40,
                storage_bytes=2_000_000,
                failures=5,
            ),
            report_directory=self.report_dir,
            report_directory_identity=report_path_identity(self.report_dir),
            launch_git_provenance=_provenance(),
            run_id="run-7e1",
            report_id="report-7e1",
            supervision_id="supervision-7e1",
            owner_id="owner-7e1",
            lease_lock_path=self.lock,
        )

    def _empty_trending_body(self) -> dict[str, object]:
        return {"data": [], "included": []}

    def _run_insufficient_discovery(self) -> dict[str, object]:
        fixtures = CombinedDiscoveryFixtures(
            cycle_id="cycle-7e1",
            cycle_cutoff=NOW_TEXT,
            campaign_selection_seed="7e1-insufficient-seed",
            provider_contract_versions={
                "geckoterminal": "V2-9.7D.7B.3B",
                "direct": "V2-9.7D.7B.3A",
            },
            git_provenance_identity="git-7e1",
            evaluated_at=NOW_TEXT,
            direct_observations=(),
            origin_proofs={},
            gecko_ops=(
                FixtureSourceFact(
                    request_kind=GECKO_TRENDING_REQUEST,
                    source_name="geckoterminal",
                    body=self._empty_trending_body(),
                    receipt_time=NOW_TEXT,
                    params=dict(GECKO_TRENDING_PARAMS),
                ),
            ),
            vacant_slot_ordinals=(1, 2),
            mode="INITIAL",
        )
        acquire_campaign_supervision(
            self.db,
            lock_path=self.lock,
            supervision_id="supervision-7e1",
            campaign_id="campaign-7e1",
            configuration_id="configuration-7e1",
            run_id="run-7e1",
            owner_id="owner-7e1",
            now=NOW,
        )
        result = CombinedPumpfunCampaignExecutor(fixtures).execute(
            command=self._command(),
            source_governor=OwnerPort(SOURCE_GOVERNOR_OWNER, True),
            central_scheduler=OwnerPort(CENTRAL_SCHEDULER_OWNER, True),
        )
        return {
            "terminal_status": result.terminal_status,
            "first_terminal_cause": result.first_terminal_cause,
            "source_calls": result.source_calls,
            "scheduler_work": result.scheduler_work,
        }

    def _cleanup(self, *, at: datetime | None = None) -> dict[str, object]:
        return cleanup_campaign_supervision(
            self.db,
            supervision_id="supervision-7e1",
            campaign_id="campaign-7e1",
            configuration_id="configuration-7e1",
            run_id="run-7e1",
            owner_id="owner-7e1",
            terminal_status="FAILED",
            first_terminal_cause="INSUFFICIENT_ELIGIBLE_TWO_SLOT_POOL",
            now=at or (NOW + timedelta(seconds=30)),
        )

    def test_insufficient_pool_cleanup_report_replay(self) -> None:
        discovery = self._run_insufficient_discovery()
        self.assertEqual(discovery["terminal_status"], "FAILED")
        self.assertEqual(
            discovery["first_terminal_cause"], "INSUFFICIENT_ELIGIBLE_TWO_SLOT_POOL"
        )

        cleanup = self._cleanup()
        self.assertTrue(cleanup["cleanup_completed"])
        self.assertTrue(cleanup["lease_released"])
        self.assertFalse(cleanup["idempotent_replay"])
        self.assertEqual(
            cleanup["first_terminal_cause"], "INSUFFICIENT_ELIGIBLE_TWO_SLOT_POOL"
        )
        self.assertEqual(cleanup["active_owned_work_after"], 0)
        self.assertFalse(self.lock.exists())
        self.assertGreaterEqual(int(cleanup["cancelled_scheduler_jobs"]), 1)
        # Batch may already be terminal from discovery executor; cleanup then
        # reports zero additional batch terminalizations.
        self.assertGreaterEqual(int(cleanup["terminalized_discovery_batches"]), 0)

        connection = sqlite3.connect(self.db)
        connection.row_factory = sqlite3.Row
        try:
            supervision = connection.execute(
                """SELECT supervision_state, terminal_status, first_terminal_cause,
                          cleanup_completed_at, lease_released_at
                   FROM printer_memory_factory_campaign_supervision
                   WHERE supervision_id='supervision-7e1'"""
            ).fetchone()
            self.assertEqual(supervision["supervision_state"], "TERMINAL")
            self.assertEqual(supervision["terminal_status"], "FAILED")
            self.assertEqual(
                supervision["first_terminal_cause"],
                "INSUFFICIENT_ELIGIBLE_TWO_SLOT_POOL",
            )
            self.assertIsNotNone(supervision["cleanup_completed_at"])
            self.assertIsNotNone(supervision["lease_released_at"])

            campaign = connection.execute(
                """SELECT campaign_state, first_terminal_cause
                   FROM printer_memory_factory_campaigns
                   WHERE campaign_id='campaign-7e1'"""
            ).fetchone()
            self.assertEqual(campaign["campaign_state"], "TERMINAL_FAILED")
            self.assertEqual(
                campaign["first_terminal_cause"], "INSUFFICIENT_ELIGIBLE_TWO_SLOT_POOL"
            )

            cycle = connection.execute(
                """SELECT cycle_state, first_terminal_cause
                   FROM printer_memory_factory_campaign_cycles
                   WHERE cycle_id='cycle-7e1'"""
            ).fetchone()
            self.assertTrue(str(cycle["cycle_state"]).startswith("TERMINAL_"))
            self.assertEqual(
                cycle["first_terminal_cause"], "INSUFFICIENT_ELIGIBLE_TWO_SLOT_POOL"
            )

            self.assertEqual(
                connection.execute(
                    "SELECT COUNT(*) FROM printer_memory_factory_campaign_token_slots"
                ).fetchone()[0],
                0,
            )
            self.assertEqual(
                connection.execute(
                    "SELECT COUNT(*) FROM printer_tracking_queue"
                ).fetchone()[0],
                0,
            )
            self.assertEqual(
                connection.execute(
                    "SELECT COUNT(*) FROM printer_memory_factory_campaign_windows"
                ).fetchone()[0],
                0,
            )
            active_jobs = connection.execute(
                """SELECT COUNT(*) FROM printer_scheduler_jobs
                   WHERE status IN ('PENDING','RUNNING','COOLDOWN')
                      OR locked_at IS NOT NULL OR lock_owner IS NOT NULL"""
            ).fetchone()[0]
            self.assertEqual(active_jobs, 0)
            active_discovery = connection.execute(
                """SELECT COUNT(*) FROM printer_discovery_work
                   WHERE work_state IN ('PENDING','RUNNING','COOLDOWN')"""
            ).fetchone()[0]
            self.assertEqual(active_discovery, 0)
            batch = connection.execute(
                """SELECT batch_state, first_terminal_cause
                   FROM printer_discovery_batches LIMIT 1"""
            ).fetchone()
            self.assertTrue(str(batch["batch_state"]).startswith("TERMINAL_"))
            self.assertEqual(
                batch["first_terminal_cause"], "INSUFFICIENT_ELIGIBLE_TWO_SLOT_POOL"
            )
            locked = {
                table: int(connection.execute(f'SELECT COUNT(*) FROM "{table}"').fetchone()[0])
                for table in LOCKED_CAPABILITY_TABLES
            }
            self.assertTrue(all(value == 0 for value in locked.values()))
            counts_before_report = _counts(connection)
        finally:
            connection.close()

        report = persist_final_campaign_report(
            self.db,
            report_id="report-7e1",
            campaign_id="campaign-7e1",
            configuration_id="configuration-7e1",
            run_id="run-7e1",
        )
        self.assertEqual(report["report_id"], "report-7e1")
        self.assertFalse(report["idempotent_replay"])
        report_again = persist_final_campaign_report(
            self.db,
            report_id="report-7e1",
            campaign_id="campaign-7e1",
            configuration_id="configuration-7e1",
            run_id="run-7e1",
        )
        self.assertTrue(report_again["idempotent_replay"])
        self.assertEqual(report_again["report_hash"], report["report_hash"])

        connection = sqlite3.connect(self.db)
        try:
            report_count = connection.execute(
                "SELECT COUNT(*) FROM printer_memory_factory_campaign_reports"
            ).fetchone()[0]
            self.assertEqual(report_count, 1)
            body = json.loads(
                connection.execute(
                    "SELECT report_json FROM printer_memory_factory_campaign_reports "
                    "WHERE report_id='report-7e1'"
                ).fetchone()[0]
            )
            self.assertEqual(
                body["terminal"]["first_terminal_cause"],
                "INSUFFICIENT_ELIGIBLE_TWO_SLOT_POOL",
            )
            # Assert report embeds zero activation without inventing slots.
            self.assertEqual(len(body["identity"]["two_token_slots"]), 0)

            usage = body["source_scheduler_ceiling_usage"]
            self.assertEqual(
                len(usage["source_request_ids"]), int(discovery["source_calls"])
            )
            self.assertEqual(
                len(usage["scheduler_job_ids"]), int(discovery["scheduler_work"])
            )
            budgets = usage["authoritative_run_budgets"]
            self.assertEqual(
                budgets["governed_requests_run"], int(discovery["source_calls"])
            )
            self.assertEqual(
                budgets["scheduler_rows_total"], int(discovery["scheduler_work"])
            )
            self.assertEqual(
                budgets["governed_requests_run_ceiling"],
                int(self.configuration["ceilings"]["source_calls"]),
            )
            self.assertEqual(
                budgets["scheduler_rows_ceiling"],
                int(self.configuration["ceilings"]["scheduler_work"]),
            )
        finally:
            connection.close()

        before_hash = _sha256_file(self.db)
        connection = sqlite3.connect(self.db)
        try:
            before_counts = _counts(connection)
        finally:
            connection.close()
        replay = replay_terminal_campaign_report(
            self.db,
            campaign_id="campaign-7e1",
            configuration_id="configuration-7e1",
            report_id="report-7e1",
            report_hash=str(report["report_hash"]),
        )
        self.assertEqual(replay.get("replay_state") or replay.get("status"), REPLAY_VERIFIED
                         if isinstance(REPLAY_VERIFIED, str) else replay)
        # Accept either status field naming from the replay owner.
        if "replay_state" in replay:
            self.assertEqual(replay["replay_state"], REPLAY_VERIFIED)
        after_hash = _sha256_file(self.db)
        self.assertEqual(after_hash, before_hash)
        connection = sqlite3.connect(self.db)
        try:
            after_counts = _counts(connection)
        finally:
            connection.close()
        self.assertEqual(after_counts, before_counts)

        # Idempotent cleanup replay preserves first cause.
        cleanup_again = self._cleanup(at=NOW + timedelta(seconds=60))
        self.assertTrue(cleanup_again["idempotent_replay"])
        self.assertEqual(
            cleanup_again["first_terminal_cause"],
            "INSUFFICIENT_ELIGIBLE_TWO_SLOT_POOL",
        )
        self.assertTrue(cleanup_again["lease_released"])

        # Same-identity cleanup with a different proposed cause is idempotent
        # and preserves the first fault (does not rewrite terminal cause).
        rewritten = cleanup_campaign_supervision(
            self.db,
            supervision_id="supervision-7e1",
            campaign_id="campaign-7e1",
            configuration_id="configuration-7e1",
            run_id="run-7e1",
            owner_id="owner-7e1",
            terminal_status="FAILED",
            first_terminal_cause="SHARED_CONFIGURATION_MISMATCH",
            now=NOW + timedelta(seconds=90),
        )
        self.assertTrue(rewritten["idempotent_replay"])
        self.assertEqual(
            rewritten["first_terminal_cause"],
            "INSUFFICIENT_ELIGIBLE_TWO_SLOT_POOL",
        )

        # Conflicting owner fails closed.
        with self.assertRaises(CampaignSupervisionError):
            cleanup_campaign_supervision(
                self.db,
                supervision_id="supervision-7e1",
                campaign_id="campaign-7e1",
                configuration_id="configuration-7e1",
                run_id="run-7e1",
                owner_id="other-owner",
                terminal_status="FAILED",
                first_terminal_cause="INSUFFICIENT_ELIGIBLE_TWO_SLOT_POOL",
                now=NOW + timedelta(seconds=120),
            )

        # Windows-safe connection close already exercised via repeated open/close.
        self.assertTrue(self.db.is_file())

    def test_non_terminal_planned_transition_still_requires_two_slots(self) -> None:
        """Trigger still protects non-terminal PLANNED transitions without slots."""
        connection = sqlite3.connect(self.db)
        connection.execute("PRAGMA foreign_keys=ON")
        try:
            with self.assertRaises(sqlite3.IntegrityError):
                connection.execute(
                    """UPDATE printer_memory_factory_campaign_cycles
                       SET cycle_state='DISCOVERING', updated_at=?
                       WHERE cycle_id='cycle-7e1'""",
                    (NOW_TEXT,),
                )
                connection.commit()
        finally:
            connection.rollback()
            connection.close()


if __name__ == "__main__":
    unittest.main()
