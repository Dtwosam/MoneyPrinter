"""Focused V2-9.8B campaign Scheduler ownership schema migration tests.

Disposable databases only. These exercise migration 050
(``050_campaign_scheduler_ownership_scope.sql``) and the single scope-aware
projection authority ``project_campaign_scheduler_work`` plus its
``WINDOW_LIFECYCLE`` compatibility wrapper. They never touch the authoritative
database or any operational/runtime path.
"""

from __future__ import annotations

from pathlib import Path
import os
import sqlite3
import tempfile
import unittest

from printer_v1.db import apply_migrations
from printer_v1.db import migrate as migration_runner
from printer_v1.operator_cli.campaign_ownership import (
    CampaignOwnershipError,
    create_campaign_run,
    create_cycle_with_two_slots,
    persist_scheduler_work,
    persist_window,
    project_campaign_scheduler_job,
    project_campaign_scheduler_work,
)
from printer_v1.operator_cli.campaign_persistence import (
    DB_MODE_PROOF_ISOLATED,
    create_campaign,
)


NOW = "2026-08-01T00:00:00+00:00"
HEX64_A = "a" * 64
HEX64_B = "b" * 64
MIGRATION_050 = "050_campaign_scheduler_ownership_scope.sql"
WORK_COLUMNS = (
    "scheduler_work_id", "campaign_id", "run_id", "cycle_id", "token_slot_id",
    "window_id", "work_intent", "deadline_at", "work_state", "scheduler_job_id",
    "source_request_id", "source_response_id", "source_failure_id",
    "first_terminal_cause", "terminal_at", "created_at", "updated_at",
)


def _provenance() -> dict[str, object]:
    return {
        "git_head": "a" * 40,
        "git_tracked_tree_clean": True,
        "git_staged_changes_present": False,
        "git_unstaged_changes_present": False,
        "git_untracked_present": True,
        "git_provenance_captured_at": NOW,
    }


def _apply_through(db_path: Path, maximum_prefix: int) -> None:
    connection = sqlite3.connect(db_path)
    try:
        connection.execute("PRAGMA foreign_keys = ON")
        connection.execute(
            """CREATE TABLE IF NOT EXISTS printer_schema_migrations (
                version TEXT PRIMARY KEY,
                applied_at TEXT NOT NULL DEFAULT (datetime('now'))
            )"""
        )
        applied = {
            row[0] for row in connection.execute(
                "SELECT version FROM printer_schema_migrations"
            )
        }
        for path in sorted(migration_runner.MIGRATIONS_DIR.glob("*.sql")):
            if int(path.name.split("_", 1)[0]) > maximum_prefix:
                continue
            if path.name not in applied:
                connection.executescript(path.read_text(encoding="utf-8"))
                connection.execute(
                    "INSERT INTO printer_schema_migrations(version) VALUES (?)",
                    (path.name,),
                )
        connection.commit()
    finally:
        connection.close()


def _insert_pre050_work_row(db_path: Path, **columns: object) -> None:
    """Insert a pre-050 window-bound scheduler_work row (FK enforcement off).

    Historical rows only; used to prove exact migration preservation without
    building the full window dependency chain.
    """
    connection = sqlite3.connect(db_path)
    try:
        keys = ", ".join(columns)
        placeholders = ", ".join("?" for _ in columns)
        connection.execute(
            f"INSERT INTO printer_memory_factory_campaign_scheduler_work({keys}) "
            f"VALUES ({placeholders})",
            tuple(columns.values()),
        )
        connection.commit()
    finally:
        connection.close()


class SchedulerOwnershipSchemaMigrationTests(unittest.TestCase):
    def setUp(self) -> None:
        temp_parent = os.environ.get("TEMP") or os.environ.get("TMP")
        self.temp = tempfile.TemporaryDirectory(dir=temp_parent)
        self.db = Path(self.temp.name) / "campaign.sqlite3"
        apply_migrations(self.db)
        create_campaign(
            self.db,
            campaign_id="campaign-a",
            configuration_id="configuration-a",
            configuration={"slots": 2},
            launch_provenance=_provenance(),
            db_mode=DB_MODE_PROOF_ISOLATED,
            db_target_identity="isolated-a",
            proof_source_db_identity="source-a",
            policy_version="v2-9.8b",
        )
        self.connection = sqlite3.connect(self.db)
        self.connection.execute("PRAGMA foreign_keys = ON")
        self.connection.row_factory = sqlite3.Row
        self._seed_base_rows()

    def tearDown(self) -> None:
        self.connection.close()
        self.temp.cleanup()

    # -- fixtures -----------------------------------------------------------

    def _seed_base_rows(self) -> None:
        with self.connection:
            for token_id in (1, 2):
                self.connection.execute(
                    "INSERT INTO printer_tokens(id,token_mint) VALUES (?,?)",
                    (token_id, f"mint-{token_id}"),
                )
                self.connection.execute(
                    "INSERT INTO printer_pairs(id,token_id,pair_address) VALUES (?,?,?)",
                    (token_id, token_id, f"pair-{token_id}"),
                )
            self.connection.execute(
                """INSERT INTO printer_memory_windows(
                    id,token_id,pair_id,window_kind,opened_at,memory_status,
                    data_quality_label
                ) VALUES (1,1,1,'WINDOW_15M',?,'CLEAN_MEMORY','CLEAN_DATA')""",
                (NOW,),
            )
            for job_id in range(1, 9):
                self.connection.execute(
                    """INSERT INTO printer_scheduler_jobs(
                        id,job_name,job_kind,status,scheduled_for
                    ) VALUES (?,?,?,'PENDING',?)""",
                    (job_id, f"job-{job_id}", "CAMPAIGN_WORK", NOW),
                )

    @staticmethod
    def _slot(slot: int, token: int) -> dict[str, object]:
        return {
            "token_slot_id": f"slot-{slot}",
            "slot_ordinal": slot,
            "token_identity": f"token-{token}",
            "token_row_id": token,
            "mint_identity": f"mint-{token}",
            "pair_identity": f"pair-{token}",
            "pair_row_id": token,
            "lifecycle_identity": f"lifecycle-{token}",
        }

    def _create_graph(self) -> None:
        create_campaign_run(
            self.connection, campaign_id="campaign-a", run_id="run-a",
            run_ordinal=1, now=NOW,
        )
        create_cycle_with_two_slots(
            self.connection, campaign_id="campaign-a", run_id="run-a",
            cycle_id="cycle-a", cycle_ordinal=1,
            slots=(self._slot(1, 1), self._slot(2, 2)), now=NOW,
        )
        persist_window(
            self.connection, window_id="window-15m-a", campaign_id="campaign-a",
            run_id="run-a", cycle_id="cycle-a", token_slot_id="slot-1",
            token_row_id=1, pair_row_id=1, window_kind="WINDOW_15M",
            root_15m_lifecycle_identity="lifecycle-1", checkpoint_cutoff=NOW,
            memory_window_row_id=1, now=NOW,
        )

    def _seed_factory_run_step(self, *, factory_run_id: str, scheduler_job_id: int) -> None:
        with self.connection:
            self.connection.execute(
                """INSERT INTO printer_memory_factory_runs(
                    run_id,run_status,window_kind,db_mode,config_hash,config_json,
                    started_at
                ) VALUES (?,'RUNNING','WINDOW_15M','PROOF_ONLY',?,?,?)""",
                (factory_run_id, HEX64_A, "{}", NOW),
            )
            self.connection.execute(
                """INSERT INTO printer_memory_factory_run_steps(
                    run_id,step_key,step_kind,step_status,scheduler_job_id,created_at,updated_at
                ) VALUES (?,?,?,'SUCCEEDED',?,?,?)""",
                (factory_run_id, f"step-{scheduler_job_id}", "WINDOW_CLOSE",
                 scheduler_job_id, NOW, NOW),
            )

    def _seed_discovery_batch(self, discovery_batch_id: str) -> None:
        connection = sqlite3.connect(self.db)
        try:
            connection.execute(
                """INSERT INTO printer_discovery_batches(
                    discovery_batch_id,campaign_id,configuration_id,run_id,cycle_id,
                    cycle_cutoff,policy_version,provider_contract_versions_json,
                    git_provenance_identity,campaign_selection_seed_identity,
                    cycle_seed_hash,pump_continuity_state,batch_state,canonical_hash,
                    created_at
                ) VALUES (?,?,?,?,?,?,?,?,?,?,?,'NONE','DISCOVERING',?,?)""",
                (discovery_batch_id, "campaign-a", "configuration-a", "run-a",
                 "cycle-a", NOW, "policy-1", "{}", "git-1", "seed-1",
                 HEX64_A, HEX64_B, NOW),
            )
            connection.commit()
        finally:
            connection.close()

    def _seed_selection_link(self, *, discovery_batch_id: str, selection_batch_id: str) -> None:
        connection = sqlite3.connect(self.db)
        try:
            connection.execute(
                """INSERT INTO printer_discovery_selection_links(
                    discovery_batch_id,selection_batch_id,campaign_id,run_id,cycle_id,
                    created_at
                ) VALUES (?,?,?,?,?,?)""",
                (discovery_batch_id, selection_batch_id, "campaign-a", "run-a",
                 "cycle-a", NOW),
            )
            connection.commit()
        finally:
            connection.close()

    def _seed_selected_item_link(
        self, *, discovery_batch_id: str, selection_batch_id: str,
        selection_item_id: int, merged_candidate_id: str,
        first_window_15m_scheduler_job_id: int, token_slot_id: str | None = None,
    ) -> None:
        connection = sqlite3.connect(self.db)
        try:
            connection.execute(
                """INSERT INTO printer_discovery_selected_item_links(
                    discovery_batch_id,selection_batch_id,selection_item_id,
                    merged_candidate_id,campaign_id,run_id,cycle_id,token_slot_id,
                    tracking_handoff_state,first_window_15m_scheduler_job_id,created_at
                ) VALUES (?,?,?,?,?,?,?,?,'HANDOFF_RECORDED',?,?)""",
                (discovery_batch_id, selection_batch_id, selection_item_id,
                 merged_candidate_id, "campaign-a", "run-a", "cycle-a",
                 token_slot_id, first_window_15m_scheduler_job_id, NOW),
            )
            connection.commit()
        finally:
            connection.close()

    def _seed_real_graph(self, db_path: Path, *, extra_job_ids=()) -> None:
        """Seed a complete, FK-valid campaign window chain on ``db_path``."""
        create_campaign(
            db_path, campaign_id="campaign-a", configuration_id="configuration-a",
            configuration={"slots": 2}, launch_provenance=_provenance(),
            db_mode=DB_MODE_PROOF_ISOLATED, db_target_identity="isolated-h",
            proof_source_db_identity="source-h", policy_version="v2-9.8b",
        )
        connection = sqlite3.connect(db_path)
        try:
            connection.execute("PRAGMA foreign_keys = ON")
            connection.row_factory = sqlite3.Row
            with connection:
                for token_id in (1, 2):
                    connection.execute(
                        "INSERT INTO printer_tokens(id,token_mint) VALUES (?,?)",
                        (token_id, f"mint-{token_id}"),
                    )
                    connection.execute(
                        "INSERT INTO printer_pairs(id,token_id,pair_address) "
                        "VALUES (?,?,?)",
                        (token_id, token_id, f"pair-{token_id}"),
                    )
                connection.execute(
                    """INSERT INTO printer_memory_windows(
                        id,token_id,pair_id,window_kind,opened_at,memory_status,
                        data_quality_label
                    ) VALUES (1,1,1,'WINDOW_15M',?,'CLEAN_MEMORY','CLEAN_DATA')""",
                    (NOW,),
                )
                for job_id in extra_job_ids:
                    connection.execute(
                        """INSERT INTO printer_scheduler_jobs(
                            id,job_name,job_kind,status,scheduled_for
                        ) VALUES (?,?,?,'PENDING',?)""",
                        (job_id, f"job-{job_id}", "CAMPAIGN_WORK", NOW),
                    )
            create_campaign_run(
                connection, campaign_id="campaign-a", run_id="run-a",
                run_ordinal=1, now=NOW,
            )
            create_cycle_with_two_slots(
                connection, campaign_id="campaign-a", run_id="run-a",
                cycle_id="cycle-a", cycle_ordinal=1,
                slots=(self._slot(1, 1), self._slot(2, 2)), now=NOW,
            )
            persist_window(
                connection, window_id="window-15m-a", campaign_id="campaign-a",
                run_id="run-a", cycle_id="cycle-a", token_slot_id="slot-1",
                token_row_id=1, pair_row_id=1, window_kind="WINDOW_15M",
                root_15m_lifecycle_identity="lifecycle-1", checkpoint_cutoff=NOW,
                memory_window_row_id=1, now=NOW,
            )
        finally:
            connection.close()

    def _work_row(self, scheduler_work_id: str) -> sqlite3.Row:
        return self.connection.execute(
            "SELECT * FROM printer_memory_factory_campaign_scheduler_work "
            "WHERE scheduler_work_id=?",
            (scheduler_work_id,),
        ).fetchone()

    # -- discovery/selection projection -------------------------------------

    def _project_discovery(self, *, work_id="work-disc", job=1) -> object:
        self._seed_discovery_batch("disc-1")
        return project_campaign_scheduler_work(
            self.connection, scheduler_work_id=work_id, campaign_id="campaign-a",
            run_id="run-a", cycle_id="cycle-a", work_scope="DISCOVERY_SELECTION",
            stage_id="STAGE_DISCOVERY", work_intent="DISCOVER",
            deadline_at=NOW, scheduler_job_id=job,
            target_category="DISCOVERY_BATCH", target_identity="disc-1", now=NOW,
        )

    # =======================================================================
    # 1. Historical rows migrate without row/identity/status/cause/timestamp drift
    # =======================================================================
    def test_01_historical_rows_migrate_without_drift(self) -> None:
        upgrade_db = Path(self.temp.name) / "hist.sqlite3"
        _apply_through(upgrade_db, 49)
        # Build a real window chain so historical rows satisfy every foreign key,
        # matching how the authoritative DB actually stores window-bound work.
        self._seed_real_graph(upgrade_db, extra_job_ids=(101,))
        connection = sqlite3.connect(upgrade_db)
        try:
            connection.execute("PRAGMA foreign_keys = ON")
            connection.execute(
                """INSERT INTO printer_memory_factory_campaign_scheduler_work(
                    scheduler_work_id,campaign_id,run_id,cycle_id,token_slot_id,
                    window_id,work_intent,deadline_at,work_state,scheduler_job_id,
                    created_at,updated_at
                ) VALUES ('w-live','campaign-a','run-a','cycle-a','slot-1',
                    'window-15m-a','CLOSE_WINDOW',?, 'PENDING',101,?,?)""",
                (NOW, NOW, NOW),
            )
            connection.execute(
                """INSERT INTO printer_memory_factory_campaign_scheduler_work(
                    scheduler_work_id,campaign_id,run_id,cycle_id,token_slot_id,
                    window_id,work_intent,deadline_at,work_state,scheduler_job_id,
                    first_terminal_cause,terminal_at,created_at,updated_at
                ) VALUES ('w-term','campaign-a','run-a','cycle-a','slot-1',
                    'window-15m-a','SNAPSHOT',?, 'SUCCEEDED',NULL,'done',?,?,?)""",
                (NOW, NOW, NOW, NOW),
            )
            connection.commit()
        finally:
            connection.close()
        before = self._snapshot(upgrade_db)
        connection = sqlite3.connect(upgrade_db)
        try:
            connection.execute("PRAGMA foreign_keys = ON")
            connection.executescript(
                (migration_runner.MIGRATIONS_DIR / MIGRATION_050).read_text("utf-8")
            )
            connection.commit()
        finally:
            connection.close()
        after = self._snapshot(upgrade_db)
        self.assertEqual(before, after)
        connection = sqlite3.connect(upgrade_db)
        try:
            versions = connection.execute(
                "SELECT DISTINCT ownership_contract_version "
                "FROM printer_memory_factory_campaign_scheduler_work"
            ).fetchall()
        finally:
            connection.close()
        self.assertEqual(versions, [("V1_WINDOW_BOUND",)])

    def _snapshot(self, db_path: Path) -> list[tuple]:
        connection = sqlite3.connect(db_path)
        try:
            return connection.execute(
                "SELECT " + ", ".join(WORK_COLUMNS)
                + " FROM printer_memory_factory_campaign_scheduler_work "
                "ORDER BY scheduler_work_id"
            ).fetchall()
        finally:
            connection.close()

    # =======================================================================
    # 2. Foreign-key and integrity checks pass after migration
    # =======================================================================
    def test_02_foreign_key_and_integrity_pass(self) -> None:
        self.assertEqual(
            self.connection.execute(
                "SELECT COUNT(*) FROM pragma_foreign_key_check"
            ).fetchone()[0],
            0,
        )
        self.assertEqual(
            self.connection.execute(
                "SELECT COUNT(*) FROM pragma_integrity_check "
                "WHERE integrity_check <> 'ok'"
            ).fetchone()[0],
            0,
        )
        # Partial unique index for one job -> one ownership row exists.
        indexes = {
            row[1] for row in self.connection.execute(
                "PRAGMA index_list('printer_memory_factory_campaign_scheduler_work')"
            )
        }
        self.assertIn("idx_campaign_work_scheduler_job_unique", indexes)

    # =======================================================================
    # 3. V1 rows remain readable and immutable
    # =======================================================================
    def test_03_v1_rows_readable_and_immutable(self) -> None:
        self._create_graph()
        persist_scheduler_work(
            self.connection, scheduler_work_id="v1-a", campaign_id="campaign-a",
            run_id="run-a", cycle_id="cycle-a", token_slot_id="slot-1",
            window_id="window-15m-a", work_intent="CLOSE_WINDOW", deadline_at=NOW,
            scheduler_job_id=1, now=NOW,
        )
        row = self._work_row("v1-a")
        self.assertEqual(row["ownership_contract_version"], "V1_WINDOW_BOUND")
        self.assertEqual(row["work_state"], "PENDING")
        with self.assertRaises(sqlite3.IntegrityError):
            self.connection.execute(
                "UPDATE printer_memory_factory_campaign_scheduler_work "
                "SET work_intent='X' WHERE scheduler_work_id='v1-a'"
            )
        self.connection.rollback()
        with self.assertRaises(sqlite3.IntegrityError):
            self.connection.execute(
                "UPDATE printer_memory_factory_campaign_scheduler_work "
                "SET campaign_id='other' WHERE scheduler_work_id='v1-a'"
            )
        self.connection.rollback()

    # =======================================================================
    # 4. Discovery/selection ownership works without slot/window
    # =======================================================================
    def test_04_discovery_selection_without_slot_or_window(self) -> None:
        self._create_graph()
        result = self._project_discovery(work_id="work-disc", job=1)
        self.assertTrue(result.created)
        row = self._work_row("work-disc")
        self.assertEqual(row["work_scope"], "DISCOVERY_SELECTION")
        self.assertEqual(row["ownership_contract_version"], "V2_STAGE_SCOPED")
        self.assertIsNone(row["token_slot_id"])
        self.assertIsNone(row["window_id"])
        self.assertIsNone(row["factory_run_id"])

        # selection-batch discovery source also works.
        self._seed_selection_link(
            discovery_batch_id="disc-1", selection_batch_id="sel-1"
        )
        selection = project_campaign_scheduler_work(
            self.connection, scheduler_work_id="work-sel", campaign_id="campaign-a",
            run_id="run-a", cycle_id="cycle-a", work_scope="DISCOVERY_SELECTION",
            stage_id="STAGE_SELECTION", work_intent="SELECT", deadline_at=NOW,
            scheduler_job_id=2, target_category="SELECTION_BATCH",
            target_identity="sel-1", now=NOW,
        )
        self.assertTrue(selection.created)

    def test_04b_discovery_selection_without_source_blocks(self) -> None:
        self._create_graph()
        with self.assertRaises(CampaignOwnershipError):
            project_campaign_scheduler_work(
                self.connection, scheduler_work_id="work-x",
                campaign_id="campaign-a", run_id="run-a", cycle_id="cycle-a",
                work_scope="DISCOVERY_SELECTION", stage_id="STAGE_DISCOVERY",
                work_intent="DISCOVER", deadline_at=NOW, scheduler_job_id=1,
                target_category="DISCOVERY_BATCH", target_identity="missing",
                now=NOW,
            )
        self.assertIsNone(self._work_row("work-x"))

    # =======================================================================
    # 5. Handoff ownership works without a window
    # =======================================================================
    def test_05_handoff_without_window(self) -> None:
        self._create_graph()
        self._seed_selected_item_link(
            discovery_batch_id="disc-1", selection_batch_id="sel-1",
            selection_item_id=77, merged_candidate_id="cand-77",
            first_window_15m_scheduler_job_id=3, token_slot_id="slot-1",
        )
        result = project_campaign_scheduler_work(
            self.connection, scheduler_work_id="work-handoff",
            campaign_id="campaign-a", run_id="run-a", cycle_id="cycle-a",
            work_scope="FIRST_15M_HANDOFF", stage_id="STAGE_HANDOFF",
            work_intent="HANDOFF", deadline_at=NOW, scheduler_job_id=3,
            target_category="MERGED_CANDIDATE", target_identity="cand-77",
            token_slot_id="slot-1", now=NOW,
        )
        self.assertTrue(result.created)
        row = self._work_row("work-handoff")
        self.assertEqual(row["work_scope"], "FIRST_15M_HANDOFF")
        self.assertIsNone(row["window_id"])
        self.assertIsNone(row["factory_run_id"])

    def test_05b_handoff_without_owner_blocks(self) -> None:
        self._create_graph()
        with self.assertRaises(CampaignOwnershipError):
            project_campaign_scheduler_work(
                self.connection, scheduler_work_id="work-h2",
                campaign_id="campaign-a", run_id="run-a", cycle_id="cycle-a",
                work_scope="FIRST_15M_HANDOFF", stage_id="STAGE_HANDOFF",
                work_intent="HANDOFF", deadline_at=NOW, scheduler_job_id=3,
                target_category="MERGED_CANDIDATE", target_identity="cand-77",
                now=NOW,
            )
        self.assertIsNone(self._work_row("work-h2"))

    # =======================================================================
    # 6. Lifecycle ownership requires exact factory/window/slot/run-step linkage
    # =======================================================================
    def test_06_lifecycle_requires_exact_linkage(self) -> None:
        self._create_graph()
        self._seed_factory_run_step(factory_run_id="factory-a", scheduler_job_id=4)
        result = project_campaign_scheduler_job(
            self.connection, scheduler_work_id="work-life",
            campaign_id="campaign-a", run_id="run-a", cycle_id="cycle-a",
            token_slot_id="slot-1", window_id="window-15m-a",
            factory_run_id="factory-a", work_intent="CLOSE_WINDOW",
            deadline_at=NOW, scheduler_job_id=4, stage_id="STAGE_WINDOW_15M",
            now=NOW,
        )
        self.assertTrue(result.created)
        row = self._work_row("work-life")
        self.assertEqual(row["work_scope"], "WINDOW_LIFECYCLE")
        self.assertEqual(row["factory_run_id"], "factory-a")
        self.assertEqual(row["window_id"], "window-15m-a")

    def test_06b_lifecycle_missing_runstep_blocks(self) -> None:
        self._create_graph()
        # factory run exists but no run-step links this scheduler job.
        with self.connection:
            self.connection.execute(
                """INSERT INTO printer_memory_factory_runs(
                    run_id,run_status,window_kind,db_mode,config_hash,config_json,
                    started_at
                ) VALUES ('factory-a','RUNNING','WINDOW_15M','PROOF_ONLY',?,?,?)""",
                (HEX64_A, "{}", NOW),
            )
        with self.assertRaises(CampaignOwnershipError):
            project_campaign_scheduler_job(
                self.connection, scheduler_work_id="work-life",
                campaign_id="campaign-a", run_id="run-a", cycle_id="cycle-a",
                token_slot_id="slot-1", window_id="window-15m-a",
                factory_run_id="factory-a", work_intent="CLOSE_WINDOW",
                deadline_at=NOW, scheduler_job_id=4, stage_id="STAGE_WINDOW_15M",
                now=NOW,
            )
        self.assertIsNone(self._work_row("work-life"))

    def test_06c_lifecycle_wrong_window_blocks(self) -> None:
        self._create_graph()
        self._seed_factory_run_step(factory_run_id="factory-a", scheduler_job_id=4)
        with self.assertRaises(CampaignOwnershipError):
            project_campaign_scheduler_job(
                self.connection, scheduler_work_id="work-life",
                campaign_id="campaign-a", run_id="run-a", cycle_id="cycle-a",
                token_slot_id="slot-2", window_id="window-15m-a",
                factory_run_id="factory-a", work_intent="CLOSE_WINDOW",
                deadline_at=NOW, scheduler_job_id=4, stage_id="STAGE_WINDOW_15M",
                now=NOW,
            )
        self.assertIsNone(self._work_row("work-life"))

    # =======================================================================
    # 7. Cleanup ownership works without a window using a captured job
    # =======================================================================
    def test_07_cleanup_without_window(self) -> None:
        self._create_graph()
        # Job 5 belongs to the campaign via a selected-item handoff link.
        self._seed_selected_item_link(
            discovery_batch_id="disc-1", selection_batch_id="sel-1",
            selection_item_id=55, merged_candidate_id="cand-55",
            first_window_15m_scheduler_job_id=5,
        )
        result = project_campaign_scheduler_work(
            self.connection, scheduler_work_id="work-clean",
            campaign_id="campaign-a", run_id="run-a", cycle_id="cycle-a",
            work_scope="TERMINAL_CLEANUP", stage_id="STAGE_TERMINAL",
            work_intent="CANCEL", deadline_at=NOW, scheduler_job_id=5,
            target_category="SCHEDULER_JOB", target_identity="5",
            work_state="CANCELLED", first_terminal_cause="cleanup_cancel",
            terminal_at=NOW, captured_campaign_job_ids=[5], now=NOW,
        )
        self.assertTrue(result.created)
        row = self._work_row("work-clean")
        self.assertEqual(row["work_scope"], "TERMINAL_CLEANUP")
        self.assertEqual(row["work_state"], "CANCELLED")
        self.assertEqual(row["first_terminal_cause"], "cleanup_cancel")
        self.assertIsNone(row["window_id"])

    def test_07b_cleanup_uncaptured_or_foreign_job_blocks(self) -> None:
        self._create_graph()
        self._seed_selected_item_link(
            discovery_batch_id="disc-1", selection_batch_id="sel-1",
            selection_item_id=55, merged_candidate_id="cand-55",
            first_window_15m_scheduler_job_id=5,
        )
        # Job 6 is not campaign-scoped -> blocks.
        with self.assertRaises(CampaignOwnershipError):
            project_campaign_scheduler_work(
                self.connection, scheduler_work_id="work-c2",
                campaign_id="campaign-a", run_id="run-a", cycle_id="cycle-a",
                work_scope="TERMINAL_CLEANUP", stage_id="STAGE_TERMINAL",
                work_intent="CANCEL", deadline_at=NOW, scheduler_job_id=6,
                target_category="SCHEDULER_JOB", target_identity="6",
                work_state="CANCELLED", first_terminal_cause="x", terminal_at=NOW,
                captured_campaign_job_ids=[6], now=NOW,
            )
        self.assertIsNone(self._work_row("work-c2"))
        # Job not in captured set -> blocks.
        with self.assertRaises(CampaignOwnershipError):
            project_campaign_scheduler_work(
                self.connection, scheduler_work_id="work-c3",
                campaign_id="campaign-a", run_id="run-a", cycle_id="cycle-a",
                work_scope="TERMINAL_CLEANUP", stage_id="STAGE_TERMINAL",
                work_intent="CANCEL", deadline_at=NOW, scheduler_job_id=5,
                target_category="SCHEDULER_JOB", target_identity="5",
                work_state="CANCELLED", first_terminal_cause="x", terminal_at=NOW,
                captured_campaign_job_ids=[7], now=NOW,
            )
        self.assertIsNone(self._work_row("work-c3"))

    # =======================================================================
    # 8. All four scopes coexist in one table and helper
    # =======================================================================
    def test_08_all_four_scopes_coexist(self) -> None:
        self._create_graph()
        self._seed_discovery_batch("disc-1")
        self._seed_selected_item_link(
            discovery_batch_id="disc-1", selection_batch_id="sel-1",
            selection_item_id=1, merged_candidate_id="cand-1",
            first_window_15m_scheduler_job_id=2, token_slot_id="slot-1",
        )
        self._seed_selected_item_link(
            discovery_batch_id="disc-1", selection_batch_id="sel-1",
            selection_item_id=2, merged_candidate_id="cand-2",
            first_window_15m_scheduler_job_id=5,
        )
        self._seed_factory_run_step(factory_run_id="factory-a", scheduler_job_id=4)

        project_campaign_scheduler_work(
            self.connection, scheduler_work_id="s-disc", campaign_id="campaign-a",
            run_id="run-a", cycle_id="cycle-a", work_scope="DISCOVERY_SELECTION",
            stage_id="STAGE_DISCOVERY", work_intent="DISCOVER", deadline_at=NOW,
            scheduler_job_id=1, target_category="DISCOVERY_BATCH",
            target_identity="disc-1", now=NOW,
        )
        project_campaign_scheduler_work(
            self.connection, scheduler_work_id="s-hand", campaign_id="campaign-a",
            run_id="run-a", cycle_id="cycle-a", work_scope="FIRST_15M_HANDOFF",
            stage_id="STAGE_HANDOFF", work_intent="HANDOFF", deadline_at=NOW,
            scheduler_job_id=2, target_category="MERGED_CANDIDATE",
            target_identity="cand-1", token_slot_id="slot-1", now=NOW,
        )
        project_campaign_scheduler_job(
            self.connection, scheduler_work_id="s-life", campaign_id="campaign-a",
            run_id="run-a", cycle_id="cycle-a", token_slot_id="slot-1",
            window_id="window-15m-a", factory_run_id="factory-a",
            work_intent="CLOSE_WINDOW", deadline_at=NOW, scheduler_job_id=4,
            stage_id="STAGE_WINDOW_15M", now=NOW,
        )
        project_campaign_scheduler_work(
            self.connection, scheduler_work_id="s-clean", campaign_id="campaign-a",
            run_id="run-a", cycle_id="cycle-a", work_scope="TERMINAL_CLEANUP",
            stage_id="STAGE_TERMINAL", work_intent="CANCEL", deadline_at=NOW,
            scheduler_job_id=5, target_category="SCHEDULER_JOB",
            target_identity="5", work_state="CANCELLED",
            first_terminal_cause="cleanup", terminal_at=NOW,
            captured_campaign_job_ids=[5], now=NOW,
        )
        scopes = {
            row[0] for row in self.connection.execute(
                "SELECT work_scope FROM printer_memory_factory_campaign_scheduler_work "
                "WHERE ownership_contract_version='V2_STAGE_SCOPED'"
            )
        }
        self.assertEqual(scopes, set(
            ["DISCOVERY_SELECTION", "FIRST_15M_HANDOFF", "WINDOW_LIFECYCLE",
             "TERMINAL_CLEANUP"]
        ))

    # =======================================================================
    # 9. Duplicate Scheduler job ownership blocks
    # =======================================================================
    def test_09_duplicate_scheduler_job_blocks(self) -> None:
        self._create_graph()
        self._project_discovery(work_id="work-disc", job=1)
        self._seed_selection_link(
            discovery_batch_id="disc-1", selection_batch_id="sel-1"
        )
        with self.assertRaises(CampaignOwnershipError):
            project_campaign_scheduler_work(
                self.connection, scheduler_work_id="work-other",
                campaign_id="campaign-a", run_id="run-a", cycle_id="cycle-a",
                work_scope="DISCOVERY_SELECTION", stage_id="STAGE_SELECTION",
                work_intent="SELECT", deadline_at=NOW, scheduler_job_id=1,
                target_category="SELECTION_BATCH", target_identity="sel-1",
                now=NOW,
            )
        self.assertIsNone(self._work_row("work-other"))

    # =======================================================================
    # 10. Exact-repeat projection is idempotent
    # =======================================================================
    def test_10_exact_repeat_idempotent(self) -> None:
        self._create_graph()
        first = self._project_discovery(work_id="work-disc", job=1)
        self.assertTrue(first.created)
        second = project_campaign_scheduler_work(
            self.connection, scheduler_work_id="work-disc", campaign_id="campaign-a",
            run_id="run-a", cycle_id="cycle-a", work_scope="DISCOVERY_SELECTION",
            stage_id="STAGE_DISCOVERY", work_intent="DISCOVER", deadline_at=NOW,
            scheduler_job_id=1, target_category="DISCOVERY_BATCH",
            target_identity="disc-1", now="2027-01-01T00:00:00+00:00",
        )
        self.assertFalse(second.created)
        self.assertEqual(
            self.connection.execute(
                "SELECT COUNT(*) FROM printer_memory_factory_campaign_scheduler_work"
            ).fetchone()[0],
            1,
        )

    # =======================================================================
    # 11. Different scope/stage/target/campaign/linkage conflicts block
    # =======================================================================
    def test_11_competing_identity_blocks(self) -> None:
        self._create_graph()
        self._project_discovery(work_id="work-disc", job=1)
        self._seed_selection_link(
            discovery_batch_id="disc-1", selection_batch_id="sel-1"
        )
        # Same scheduler_work_id, different stage -> competing ownership.
        with self.assertRaises(CampaignOwnershipError):
            project_campaign_scheduler_work(
                self.connection, scheduler_work_id="work-disc",
                campaign_id="campaign-a", run_id="run-a", cycle_id="cycle-a",
                work_scope="DISCOVERY_SELECTION", stage_id="STAGE_OTHER",
                work_intent="DISCOVER", deadline_at=NOW, scheduler_job_id=1,
                target_category="DISCOVERY_BATCH", target_identity="disc-1",
                now=NOW,
            )
        self.assertEqual(self._work_row("work-disc")["stage_id"], "STAGE_DISCOVERY")

    # =======================================================================
    # 12. Invalid nullable-field combinations block (schema CHECKs)
    # =======================================================================
    def test_12_invalid_nullable_combinations_block(self) -> None:
        base = (
            "INSERT INTO printer_memory_factory_campaign_scheduler_work("
            "scheduler_work_id,campaign_id,run_id,cycle_id,work_intent,deadline_at,"
            "work_state,scheduler_job_id,ownership_contract_version,stage_id,"
            "work_scope,target_category,target_identity,token_slot_id,window_id,"
            "factory_run_id,created_at,updated_at) VALUES "
        )
        cases = [
            # V2 discovery carrying a window (fabricated).
            "('x','c','r','cy','i',?,'PENDING',1,'V2_STAGE_SCOPED','st',"
            "'DISCOVERY_SELECTION','DISCOVERY_BATCH','d',NULL,'win',NULL,?,?)",
            # V2 window-lifecycle missing window.
            "('x','c','r','cy','i',?,'PENDING',1,'V2_STAGE_SCOPED','st',"
            "'WINDOW_LIFECYCLE','CAMPAIGN_WINDOW','w','slot',NULL,'f',?,?)",
            # V2 missing work_scope.
            "('x','c','r','cy','i',?,'PENDING',1,'V2_STAGE_SCOPED','st',"
            "NULL,'CAMPAIGN_WINDOW','w','slot','win','f',?,?)",
            # V1 carrying a scope (should be pure window-bound).
            "('x','c','r','cy','i',?,'PENDING',1,'V1_WINDOW_BOUND',NULL,"
            "'WINDOW_LIFECYCLE',NULL,NULL,'slot','win',NULL,?,?)",
            # V2 handoff carrying a factory run (fabricated run-step).
            "('x','c','r','cy','i',?,'PENDING',1,'V2_STAGE_SCOPED','st',"
            "'FIRST_15M_HANDOFF','MERGED_CANDIDATE','m',NULL,NULL,'f',?,?)",
        ]
        for case in cases:
            with self.assertRaises(sqlite3.IntegrityError):
                self.connection.execute(base + case, (NOW, NOW, NOW))
            self.connection.rollback()

    # =======================================================================
    # 13. Identity mutation blocks
    # =======================================================================
    def test_13_identity_mutation_blocks(self) -> None:
        self._create_graph()
        self._project_discovery(work_id="work-disc", job=1)
        for column, value in (
            ("work_scope", "TERMINAL_CLEANUP"),
            ("stage_id", "STAGE_OTHER"),
            ("target_identity", "other"),
            ("ownership_contract_version", "V1_WINDOW_BOUND"),
            ("factory_run_id", "factory-x"),
            ("scheduler_job_id", 2),
        ):
            with self.assertRaises(sqlite3.IntegrityError):
                self.connection.execute(
                    "UPDATE printer_memory_factory_campaign_scheduler_work "
                    f"SET {column}=? WHERE scheduler_work_id='work-disc'",
                    (value,),
                )
            self.connection.rollback()

    # =======================================================================
    # 14. Duplicate historical ownership blocks migration readiness
    # =======================================================================
    def test_14_duplicate_historical_job_blocks_migration(self) -> None:
        upgrade_db = Path(self.temp.name) / "dup.sqlite3"
        _apply_through(upgrade_db, 49)
        for suffix in ("a", "b"):
            _insert_pre050_work_row(
                upgrade_db, scheduler_work_id=f"w-{suffix}", campaign_id="c",
                run_id="r", cycle_id="cy", token_slot_id="s", window_id="win",
                work_intent="i", deadline_at=NOW, work_state="PENDING",
                scheduler_job_id=999, created_at=NOW, updated_at=NOW,
            )
        connection = sqlite3.connect(upgrade_db)
        try:
            connection.execute("PRAGMA foreign_keys = ON")
            with self.assertRaises(sqlite3.IntegrityError):
                connection.executescript(
                    (migration_runner.MIGRATIONS_DIR / MIGRATION_050).read_text("utf-8")
                )
            connection.rollback()
            # Original table still pre-050 (no ownership_contract_version column).
            cols = {
                row[1] for row in connection.execute(
                    "PRAGMA table_info(printer_memory_factory_campaign_scheduler_work)"
                )
            }
            self.assertNotIn("ownership_contract_version", cols)
            self.assertEqual(
                connection.execute(
                    "SELECT COUNT(*) FROM printer_memory_factory_campaign_scheduler_work"
                ).fetchone()[0],
                2,
            )
            leftover = connection.execute(
                "SELECT COUNT(*) FROM sqlite_master WHERE name LIKE '%__v2_9_8b_050'"
            ).fetchone()[0]
            self.assertEqual(leftover, 0)
        finally:
            connection.close()

    # =======================================================================
    # 15. Injected mid-rebuild failure rolls back without partial schema/row loss
    # =======================================================================
    def test_15_injected_failure_rolls_back(self) -> None:
        upgrade_db = Path(self.temp.name) / "fail.sqlite3"
        _apply_through(upgrade_db, 49)
        _insert_pre050_work_row(
            upgrade_db, scheduler_work_id="w-keep", campaign_id="c", run_id="r",
            cycle_id="cy", token_slot_id="s", window_id="win", work_intent="i",
            deadline_at=NOW, work_state="PENDING", scheduler_job_id=1,
            created_at=NOW, updated_at=NOW,
        )
        script = (migration_runner.MIGRATIONS_DIR / MIGRATION_050).read_text("utf-8")
        # Inject a guaranteed failure after the new table is built and copied but
        # before the swap/commit.
        marker = "-- 6. Swap the rebuilt table into place."
        self.assertIn(marker, script)
        injected = script.replace(
            marker,
            "INSERT INTO _mig050_guard_rowcount(ok) VALUES (0);\n" + marker,
        )
        connection = sqlite3.connect(upgrade_db)
        try:
            connection.execute("PRAGMA foreign_keys = ON")
            with self.assertRaises(sqlite3.IntegrityError):
                connection.executescript(injected)
            connection.rollback()
            cols = {
                row[1] for row in connection.execute(
                    "PRAGMA table_info(printer_memory_factory_campaign_scheduler_work)"
                )
            }
            self.assertNotIn("ownership_contract_version", cols)
            self.assertEqual(
                connection.execute(
                    "SELECT scheduler_work_id FROM "
                    "printer_memory_factory_campaign_scheduler_work"
                ).fetchall(),
                [("w-keep",)],
            )
            leftover = connection.execute(
                "SELECT COUNT(*) FROM sqlite_master WHERE name LIKE '%__v2_9_8b_050'"
            ).fetchone()[0]
            self.assertEqual(leftover, 0)
        finally:
            connection.close()

    # =======================================================================
    # 16. V1 rows cannot be treated as V2 evidence
    # =======================================================================
    def test_16_v1_rows_cannot_be_v2_evidence(self) -> None:
        self._create_graph()
        persist_scheduler_work(
            self.connection, scheduler_work_id="v1-a", campaign_id="campaign-a",
            run_id="run-a", cycle_id="cycle-a", token_slot_id="slot-1",
            window_id="window-15m-a", work_intent="CLOSE_WINDOW", deadline_at=NOW,
            scheduler_job_id=1, now=NOW,
        )
        self._seed_discovery_batch("disc-1")
        # Re-using the V1 scheduler_work_id as a V2 projection is rejected.
        with self.assertRaises(CampaignOwnershipError):
            project_campaign_scheduler_work(
                self.connection, scheduler_work_id="v1-a",
                campaign_id="campaign-a", run_id="run-a", cycle_id="cycle-a",
                work_scope="DISCOVERY_SELECTION", stage_id="STAGE_DISCOVERY",
                work_intent="DISCOVER", deadline_at=NOW, scheduler_job_id=1,
                target_category="DISCOVERY_BATCH", target_identity="disc-1",
                now=NOW,
            )
        # The V1 row still occupies the unique job slot: a new V2 row reusing the
        # same Scheduler job is rejected as duplicate ownership.
        with self.assertRaises(CampaignOwnershipError):
            project_campaign_scheduler_work(
                self.connection, scheduler_work_id="v2-a",
                campaign_id="campaign-a", run_id="run-a", cycle_id="cycle-a",
                work_scope="DISCOVERY_SELECTION", stage_id="STAGE_DISCOVERY",
                work_intent="DISCOVER", deadline_at=NOW, scheduler_job_id=1,
                target_category="DISCOVERY_BATCH", target_identity="disc-1",
                now=NOW,
            )
        row = self._work_row("v1-a")
        self.assertEqual(row["ownership_contract_version"], "V1_WINDOW_BOUND")


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
