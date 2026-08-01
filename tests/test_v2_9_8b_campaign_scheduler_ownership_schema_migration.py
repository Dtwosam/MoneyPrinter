"""Focused V2-9.8B campaign Scheduler ownership schema migration tests.

Disposable databases only. These exercise migration 050
(``050_campaign_scheduler_ownership_scope.sql``) and the corrected single
scope-aware projection authority ``project_campaign_scheduler_work`` plus its
``WINDOW_LIFECYCLE`` compatibility wrapper. They never touch the authoritative
database or any operational/runtime path.

Correction lane ("scheduler ownership projection truth"): the projection now
derives the recorded work state and terminal evidence from the canonical
``printer_scheduler_jobs`` row (or durable Scheduler evidence), proves exact job
lineage per scope through the durable owner (``printer_discovery_work`` for
discovery/selection, the selected-item link for handoff, the factory run-step +
campaign-run authoritative bind for lifecycle, and an immutable pre-cancellation
capture for cleanup), and validates every scope's exact target.

The controlling compatibility correction also proves that historical
``V1_WINDOW_BOUND`` rows remain readable but cannot act as repaired V2 capture,
terminal, slot-link, equality, report, or replay evidence. Exact cancellation is
exercised only by a disposable test-local harness over the immutable capture;
no operational terminal path is imported or invoked here.
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
import os
import sqlite3
import tempfile
import unittest

from printer_v1.db import apply_migrations
from printer_v1.db import migrate as migration_runner
from printer_v1.operator_cli.campaign_active_work import campaign_scoped_job_ids
from printer_v1.operator_cli.campaign_ownership import (
    CampaignOwnershipError,
    SchedulerCleanupCapture,
    _cleanup_exact_owner_evidence,
    _validate_cleanup_token_slot,
    bind_authoritative_run_id,
    capture_campaign_active_scheduler_jobs,
    create_campaign_run,
    create_cycle_with_two_slots,
    persist_scheduler_work,
    persist_window,
    project_campaign_scheduler_job,
    project_campaign_scheduler_work,
    transition_state,
)
from printer_v1.operator_cli.campaign_persistence import (
    DB_MODE_PROOF_ISOLATED,
    create_campaign,
)
from printer_v1.scheduler.scheduler import cancel_job


NOW = "2026-08-01T00:00:00+00:00"
LATER = "2027-01-01T00:00:00+00:00"
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
            for job_id in range(1, 21):
                self.connection.execute(
                    """INSERT INTO printer_scheduler_jobs(
                        id,job_name,job_kind,status,scheduled_for
                    ) VALUES (?,?,?,'PENDING',?)""",
                    (job_id, f"job-{job_id}", "CAMPAIGN_WORK", NOW),
                )

    @staticmethod
    def _slot(slot: int, token: int, *, ordinal: int | None = None) -> dict[str, object]:
        return {
            "token_slot_id": f"slot-{slot}",
            "slot_ordinal": ordinal if ordinal is not None else slot,
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

    def _seed_second_cycle(self, *, cycle_id: str = "cycle-b") -> None:
        create_cycle_with_two_slots(
            self.connection, campaign_id="campaign-a", run_id="run-a",
            cycle_id=cycle_id, cycle_ordinal=2,
            slots=(
                self._slot(3, 1, ordinal=1),
                self._slot(4, 2, ordinal=2),
            ), now=NOW,
        )

    def _seed_second_run(self) -> None:
        create_campaign_run(
            self.connection, campaign_id="campaign-a", run_id="run-b",
            run_ordinal=2, now=NOW,
        )
        create_cycle_with_two_slots(
            self.connection, campaign_id="campaign-a", run_id="run-b",
            cycle_id="cycle-run-b", cycle_ordinal=1,
            slots=(
                self._slot(5, 1, ordinal=1),
                self._slot(6, 2, ordinal=2),
            ), now=NOW,
        )

    def _seed_factory_run(self, *, factory_run_id: str) -> None:
        with self.connection:
            self.connection.execute(
                """INSERT INTO printer_memory_factory_runs(
                    run_id,run_status,window_kind,db_mode,config_hash,config_json,
                    started_at
                ) VALUES (?,'RUNNING','WINDOW_15M','PROOF_ONLY',?,?,?)""",
                (factory_run_id, HEX64_A, "{}", NOW),
            )

    def _seed_factory_run_step(self, *, factory_run_id: str, scheduler_job_id: int) -> None:
        self._seed_factory_run(factory_run_id=factory_run_id)
        with self.connection:
            self.connection.execute(
                """INSERT INTO printer_memory_factory_run_steps(
                    run_id,step_key,step_kind,step_status,scheduler_job_id,created_at,updated_at
                ) VALUES (?,?,?,'SUCCEEDED',?,?,?)""",
                (factory_run_id, f"step-{scheduler_job_id}", "WINDOW_CLOSE",
                 scheduler_job_id, NOW, NOW),
            )

    def _seed_discovery_batch(
        self, discovery_batch_id: str, *, run_id: str = "run-a",
        cycle_id: str = "cycle-a",
    ) -> None:
        connection = sqlite3.connect(self.db)
        try:
            connection.execute("PRAGMA foreign_keys = ON")
            connection.execute(
                """INSERT INTO printer_discovery_batches(
                    discovery_batch_id,campaign_id,configuration_id,run_id,cycle_id,
                    cycle_cutoff,policy_version,provider_contract_versions_json,
                    git_provenance_identity,campaign_selection_seed_identity,
                    cycle_seed_hash,pump_continuity_state,batch_state,canonical_hash,
                    created_at
                ) VALUES (?,?,?,?,?,?,?,?,?,?,?,'NONE','DISCOVERING',?,?)""",
                (discovery_batch_id, "campaign-a", "configuration-a", run_id,
                 cycle_id, NOW, "policy-1", "{}", "git-1", "seed-1",
                 HEX64_A, HEX64_B, NOW),
            )
            connection.commit()
        finally:
            connection.close()

    def _seed_discovery_work(
        self, *, discovery_work_id: str, scheduler_job_id: int,
        work_type: str = "DISCOVERY_PUMPFUN_LATEST", work_state: str = "PENDING",
        first_terminal_cause: str | None = None, terminal_at: str | None = None,
        discovery_batch_id: str = "disc-1", run_id: str = "run-a",
        cycle_id: str = "cycle-a",
    ) -> None:
        connection = sqlite3.connect(self.db)
        try:
            connection.execute("PRAGMA foreign_keys = ON")
            connection.execute(
                """INSERT INTO printer_discovery_work(
                    discovery_work_id,discovery_batch_id,campaign_id,run_id,cycle_id,
                    scheduler_job_id,work_type,work_state,deadline_at,
                    first_terminal_cause,terminal_at,created_at,updated_at
                ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (discovery_work_id, discovery_batch_id, "campaign-a", run_id,
                 cycle_id, scheduler_job_id, work_type, work_state, NOW,
                 first_terminal_cause, terminal_at, NOW, NOW),
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

    def _set_job_status(
        self, job_id: int, status: str, *, finished_at: str | None = None,
        last_error: str | None = None,
    ) -> None:
        with self.connection:
            self.connection.execute(
                "UPDATE printer_scheduler_jobs "
                "SET status=?, finished_at=?, last_error=? WHERE id=?",
                (status, finished_at, last_error, job_id),
            )

    def _set_discovery_work_terminal(
        self, discovery_work_id: str, state: str, cause: str,
        *, terminal_at: str = NOW,
    ) -> None:
        with self.connection:
            self.connection.execute(
                """UPDATE printer_discovery_work
                   SET work_state=?, first_terminal_cause=?, terminal_at=?,
                       updated_at=?
                   WHERE discovery_work_id=?""",
                (state, cause, terminal_at, terminal_at, discovery_work_id),
            )

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

    def _seed_v2_cleanup_work(
        self, *, scheduler_work_id: str, scheduler_job_id: int,
        token_slot_id: str | None = None,
    ) -> None:
        with self.connection:
            self.connection.execute(
                """INSERT INTO printer_memory_factory_campaign_scheduler_work(
                    scheduler_work_id,campaign_id,run_id,cycle_id,token_slot_id,
                    work_intent,deadline_at,work_state,scheduler_job_id,
                    ownership_contract_version,stage_id,work_scope,
                    target_category,target_identity,created_at,updated_at
                ) VALUES (?,'campaign-a','run-a','cycle-a',?,'CANCEL',?,
                    'PENDING',?,'V2_STAGE_SCOPED','STAGE_TERMINAL',
                    'TERMINAL_CLEANUP','SCHEDULER_JOB',?,?,?)""",
                (
                    scheduler_work_id, token_slot_id, NOW, scheduler_job_id,
                    str(scheduler_job_id), NOW, NOW,
                ),
            )

    def _seed_v1_terminal_work(
        self, *, scheduler_work_id: str, scheduler_job_id: int,
        terminal_cause: str,
    ) -> None:
        with self.connection:
            self.connection.execute(
                """INSERT INTO printer_memory_factory_campaign_scheduler_work(
                    scheduler_work_id,campaign_id,run_id,cycle_id,token_slot_id,
                    window_id,work_intent,deadline_at,work_state,scheduler_job_id,
                    ownership_contract_version,first_terminal_cause,terminal_at,
                    created_at,updated_at
                ) VALUES (?,'campaign-a','run-a','cycle-a','slot-1',
                    'window-15m-a','CLOSE_WINDOW',?,'CANCELLED',?,
                    'V1_WINDOW_BOUND',?,?,?,?)""",
                (
                    scheduler_work_id, NOW, scheduler_job_id, terminal_cause,
                    NOW, NOW, NOW,
                ),
            )

    # -- lawful projection helpers ------------------------------------------

    def _project_discovery(
        self, *, work_id: str = "work-disc", job: int = 1,
        dwork: str = "dwork-1", work_type: str = "DISCOVERY_PUMPFUN_LATEST",
        stage: str = "STAGE_DISCOVERY", seed_batch: bool = True,
        seed_work: bool = True,
    ) -> object:
        if seed_batch:
            self._seed_discovery_batch("disc-1")
        if seed_work:
            self._seed_discovery_work(
                discovery_work_id=dwork, scheduler_job_id=job, work_type=work_type,
            )
        return project_campaign_scheduler_work(
            self.connection, scheduler_work_id=work_id, campaign_id="campaign-a",
            run_id="run-a", cycle_id="cycle-a", work_scope="DISCOVERY_SELECTION",
            stage_id=stage, work_intent="DISCOVER", deadline_at=NOW,
            scheduler_job_id=job, target_category="DISCOVERY_WORK",
            target_identity=dwork, now=NOW,
        )

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
    # Migration preservation / schema (proof 12 + retained schema proofs)
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
        indexes = {
            row[1] for row in self.connection.execute(
                "PRAGMA index_list('printer_memory_factory_campaign_scheduler_work')"
            )
        }
        self.assertIn("idx_campaign_work_scheduler_job_unique", indexes)

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

    def test_04_duplicate_historical_job_blocks_migration(self) -> None:
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

    def test_05_injected_failure_rolls_back(self) -> None:
        upgrade_db = Path(self.temp.name) / "fail.sqlite3"
        _apply_through(upgrade_db, 49)
        _insert_pre050_work_row(
            upgrade_db, scheduler_work_id="w-keep", campaign_id="c", run_id="r",
            cycle_id="cy", token_slot_id="s", window_id="win", work_intent="i",
            deadline_at=NOW, work_state="PENDING", scheduler_job_id=1,
            created_at=NOW, updated_at=NOW,
        )
        script = (migration_runner.MIGRATIONS_DIR / MIGRATION_050).read_text("utf-8")
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

    def test_06_invalid_nullable_combinations_block(self) -> None:
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
            "'DISCOVERY_SELECTION','DISCOVERY_WORK','d',NULL,'win',NULL,?,?)",
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

    def test_07_identity_mutation_blocks(self) -> None:
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

    def test_08_v1_rows_cannot_be_v2_evidence(self) -> None:
        self._create_graph()
        persist_scheduler_work(
            self.connection, scheduler_work_id="v1-a", campaign_id="campaign-a",
            run_id="run-a", cycle_id="cycle-a", token_slot_id="slot-1",
            window_id="window-15m-a", work_intent="CLOSE_WINDOW", deadline_at=NOW,
            scheduler_job_id=1, now=NOW,
        )
        self._seed_discovery_batch("disc-1")
        self._seed_discovery_work(discovery_work_id="dwork-1", scheduler_job_id=1)
        # Re-using the V1 scheduler_work_id as a V2 projection is rejected.
        with self.assertRaises(CampaignOwnershipError):
            project_campaign_scheduler_work(
                self.connection, scheduler_work_id="v1-a",
                campaign_id="campaign-a", run_id="run-a", cycle_id="cycle-a",
                work_scope="DISCOVERY_SELECTION", stage_id="STAGE_DISCOVERY",
                work_intent="DISCOVER", deadline_at=NOW, scheduler_job_id=1,
                target_category="DISCOVERY_WORK", target_identity="dwork-1",
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
                target_category="DISCOVERY_WORK", target_identity="dwork-1",
                now=NOW,
            )
        row = self._work_row("v1-a")
        self.assertEqual(row["ownership_contract_version"], "V1_WINDOW_BOUND")

    def test_08b_v1_does_not_admit_exact_capture_while_v2_does(self) -> None:
        self._create_graph()
        persist_scheduler_work(
            self.connection, scheduler_work_id="v1-capture",
            campaign_id="campaign-a", run_id="run-a", cycle_id="cycle-a",
            token_slot_id="slot-1", window_id="window-15m-a",
            work_intent="CLOSE_WINDOW", deadline_at=NOW,
            scheduler_job_id=1, now=NOW,
        )
        self._seed_v2_cleanup_work(
            scheduler_work_id="v2-capture", scheduler_job_id=2,
            token_slot_id="slot-1",
        )

        broad_groups = campaign_scoped_job_ids(
            self.connection, campaign_id="campaign-a", run_id="run-a",
            cycle_id="cycle-a",
        )
        exact_groups = campaign_scoped_job_ids(
            self.connection, campaign_id="campaign-a", run_id="run-a",
            cycle_id="cycle-a", exact_scope=True,
        )
        capture = capture_campaign_active_scheduler_jobs(
            self.connection, campaign_id="campaign-a", run_id="run-a",
            cycle_id="cycle-a", captured_at=NOW,
        )

        self.assertEqual(
            broad_groups["campaign_scheduler_work_jobs"], {1, 2}
        )
        self.assertEqual(
            exact_groups["campaign_scheduler_work_jobs"], {2}
        )
        self.assertEqual(capture.job_ids, (2,))
        self.assertIsNone(capture.pre_state(1))
        self.assertEqual(capture.pre_state(2), "PENDING")
        versions = {
            str(row[0]): str(row[1])
            for row in self.connection.execute(
                """SELECT scheduler_work_id, ownership_contract_version
                   FROM printer_memory_factory_campaign_scheduler_work
                   WHERE scheduler_work_id IN ('v1-capture','v2-capture')"""
            )
        }
        self.assertEqual(
            versions,
            {
                "v1-capture": "V1_WINDOW_BOUND",
                "v2-capture": "V2_STAGE_SCOPED",
            },
        )

    def test_08c_mixed_fixture_uses_only_v2_terminal_and_slot_evidence(self) -> None:
        self._create_graph()
        self._seed_v1_terminal_work(
            scheduler_work_id="v1-evidence", scheduler_job_id=1,
            terminal_cause="V1_ONLY_CAUSE",
        )
        self._seed_v2_cleanup_work(
            scheduler_work_id="v2-evidence", scheduler_job_id=2,
            token_slot_id="slot-1",
        )
        capture = capture_campaign_active_scheduler_jobs(
            self.connection, campaign_id="campaign-a", run_id="run-a",
            cycle_id="cycle-a", captured_at=NOW,
        )
        transition_state(
            self.connection, record_kind="scheduler_work", identity="v2-evidence",
            expected_state="PENDING", new_state="CANCELLED",
            terminal_cause="V2_LAWFUL_CAUSE", now=NOW,
        )
        self._set_job_status(1, "CANCELLED", finished_at=NOW)
        self._set_job_status(2, "CANCELLED", finished_at=NOW)

        with self.assertRaisesRegex(
            CampaignOwnershipError, "no exact durable campaign/run/cycle owner"
        ):
            _cleanup_exact_owner_evidence(
                self.connection, campaign_id="campaign-a", run_id="run-a",
                cycle_id="cycle-a", scheduler_job_id=1,
            )
        with self.assertRaisesRegex(
            CampaignOwnershipError, "no durable link to token_slot_id"
        ):
            _validate_cleanup_token_slot(
                self.connection, campaign_id="campaign-a", run_id="run-a",
                cycle_id="cycle-a", scheduler_job_id=1,
                token_slot_id="slot-1",
            )

        evidence = _cleanup_exact_owner_evidence(
            self.connection, campaign_id="campaign-a", run_id="run-a",
            cycle_id="cycle-a", scheduler_job_id=2,
        )
        self.assertIsNotNone(evidence)
        self.assertEqual(evidence.source, "campaign_scheduler_work:v2-evidence")
        self.assertEqual(evidence.first_terminal_cause, "V2_LAWFUL_CAUSE")
        _validate_cleanup_token_slot(
            self.connection, campaign_id="campaign-a", run_id="run-a",
            cycle_id="cycle-a", scheduler_job_id=2, token_slot_id="slot-1",
        )
        result = project_campaign_scheduler_work(
            self.connection, scheduler_work_id="v2-evidence",
            campaign_id="campaign-a", run_id="run-a", cycle_id="cycle-a",
            work_scope="TERMINAL_CLEANUP", stage_id="STAGE_TERMINAL",
            work_intent="CANCEL", deadline_at=NOW, scheduler_job_id=2,
            target_category="SCHEDULER_JOB", target_identity="2",
            token_slot_id="slot-1", cleanup_capture=capture, now=LATER,
        )
        self.assertFalse(result.created)
        self.assertEqual(result.work_state, "CANCELLED")
        self.assertEqual(
            self._work_row("v1-evidence")["first_terminal_cause"],
            "V1_ONLY_CAUSE",
        )

    # =======================================================================
    # Proof 1: PENDING Scheduler job projected as CANCELLED blocks
    # =======================================================================
    def test_10_pending_job_projected_terminal_blocks(self) -> None:
        self._create_graph()
        self._seed_discovery_batch("disc-1")
        self._seed_discovery_work(discovery_work_id="dwork-1", scheduler_job_id=1)
        # Job 1 is PENDING; asserting a terminal ownership state contradicts it.
        with self.assertRaises(CampaignOwnershipError):
            project_campaign_scheduler_work(
                self.connection, scheduler_work_id="work-x",
                campaign_id="campaign-a", run_id="run-a", cycle_id="cycle-a",
                work_scope="DISCOVERY_SELECTION", stage_id="STAGE_DISCOVERY",
                work_intent="DISCOVER", deadline_at=NOW, scheduler_job_id=1,
                target_category="DISCOVERY_WORK", target_identity="dwork-1",
                work_state="CANCELLED", first_terminal_cause="c", terminal_at=NOW,
                now=NOW,
            )
        self.assertIsNone(self._work_row("work-x"))

    # =======================================================================
    # Proof 2: terminal-state or terminal-cause mismatch blocks
    # =======================================================================
    def test_11_terminal_state_or_cause_mismatch_blocks(self) -> None:
        self._create_graph()
        self._seed_discovery_batch("disc-1")
        self._seed_discovery_work(discovery_work_id="dwork-1", scheduler_job_id=1)
        # Actual state SUCCEEDED, asserted FAILED -> state mismatch blocks.
        self._set_job_status(1, "SUCCEEDED", finished_at=NOW)
        with self.assertRaises(CampaignOwnershipError):
            project_campaign_scheduler_work(
                self.connection, scheduler_work_id="work-s",
                campaign_id="campaign-a", run_id="run-a", cycle_id="cycle-a",
                work_scope="DISCOVERY_SELECTION", stage_id="STAGE_DISCOVERY",
                work_intent="DISCOVER", deadline_at=NOW, scheduler_job_id=1,
                target_category="DISCOVERY_WORK", target_identity="dwork-1",
                work_state="FAILED", first_terminal_cause="x", terminal_at=NOW,
                now=NOW,
            )
        self.assertIsNone(self._work_row("work-s"))
        # Actual FAILED with real last_error; asserted cause differs -> blocks.
        self._seed_discovery_work(
            discovery_work_id="dwork-2", scheduler_job_id=2,
            work_type="DISCOVERY_DEXSCREENER_ACTIVE",
        )
        self._set_job_status(2, "FAILED", finished_at=NOW, last_error="real_error")
        with self.assertRaises(CampaignOwnershipError):
            project_campaign_scheduler_work(
                self.connection, scheduler_work_id="work-c",
                campaign_id="campaign-a", run_id="run-a", cycle_id="cycle-a",
                work_scope="DISCOVERY_SELECTION", stage_id="STAGE_DISCOVERY",
                work_intent="DISCOVER", deadline_at=NOW, scheduler_job_id=2,
                target_category="DISCOVERY_WORK", target_identity="dwork-2",
                work_state="FAILED", first_terminal_cause="wrong_cause",
                terminal_at=NOW, now=NOW,
            )
        self.assertIsNone(self._work_row("work-c"))

    # =======================================================================
    # Proof 3: discovery batch presence / unrelated Scheduler job blocks
    # =======================================================================
    def test_12_discovery_batch_presence_or_unrelated_job_blocks(self) -> None:
        self._create_graph()
        self._seed_discovery_batch("disc-1")
        self._seed_discovery_work(discovery_work_id="dwork-1", scheduler_job_id=1)
        # Batch exists but is not a discovery_work owner -> no exact lineage.
        with self.assertRaises(CampaignOwnershipError):
            project_campaign_scheduler_work(
                self.connection, scheduler_work_id="work-b",
                campaign_id="campaign-a", run_id="run-a", cycle_id="cycle-a",
                work_scope="DISCOVERY_SELECTION", stage_id="STAGE_DISCOVERY",
                work_intent="DISCOVER", deadline_at=NOW, scheduler_job_id=1,
                target_category="DISCOVERY_WORK", target_identity="disc-1",
                now=NOW,
            )
        self.assertIsNone(self._work_row("work-b"))
        # Discovery_work owns job 1, but an unrelated job 2 is projected -> blocks.
        with self.assertRaises(CampaignOwnershipError):
            project_campaign_scheduler_work(
                self.connection, scheduler_work_id="work-u",
                campaign_id="campaign-a", run_id="run-a", cycle_id="cycle-a",
                work_scope="DISCOVERY_SELECTION", stage_id="STAGE_DISCOVERY",
                work_intent="DISCOVER", deadline_at=NOW, scheduler_job_id=2,
                target_category="DISCOVERY_WORK", target_identity="dwork-1",
                now=NOW,
            )
        self.assertIsNone(self._work_row("work-u"))

    # =======================================================================
    # Proof 4: selection owner plus unrelated Scheduler job blocks
    # =======================================================================
    def test_13_selection_owner_unrelated_job_blocks(self) -> None:
        self._create_graph()
        self._seed_discovery_batch("disc-1")
        # Selection is a DISCOVERY_UNIFORM_SELECTION discovery_work bound to job 2.
        self._seed_discovery_work(
            discovery_work_id="sel-work", scheduler_job_id=2,
            work_type="DISCOVERY_UNIFORM_SELECTION",
        )
        # Projecting the selection owner against an unrelated job 3 -> blocks.
        with self.assertRaises(CampaignOwnershipError):
            project_campaign_scheduler_work(
                self.connection, scheduler_work_id="work-sel",
                campaign_id="campaign-a", run_id="run-a", cycle_id="cycle-a",
                work_scope="DISCOVERY_SELECTION", stage_id="STAGE_SELECTION",
                work_intent="SELECT", deadline_at=NOW, scheduler_job_id=3,
                target_category="DISCOVERY_WORK", target_identity="sel-work",
                now=NOW,
            )
        self.assertIsNone(self._work_row("work-sel"))
        # Batch-presence proxy (SELECTION_BATCH) is no longer an accepted target.
        self._seed_selection_link(
            discovery_batch_id="disc-1", selection_batch_id="sel-1"
        )
        with self.assertRaises(CampaignOwnershipError):
            project_campaign_scheduler_work(
                self.connection, scheduler_work_id="work-sel2",
                campaign_id="campaign-a", run_id="run-a", cycle_id="cycle-a",
                work_scope="DISCOVERY_SELECTION", stage_id="STAGE_SELECTION",
                work_intent="SELECT", deadline_at=NOW, scheduler_job_id=2,
                target_category="SELECTION_BATCH", target_identity="sel-1",
                now=NOW,
            )
        self.assertIsNone(self._work_row("work-sel2"))

    def test_13b_shared_job_uses_only_exact_target_terminal_evidence(self) -> None:
        self._create_graph()
        self._seed_discovery_batch("disc-1")
        self._seed_discovery_work(
            discovery_work_id="target-work", scheduler_job_id=8,
            work_type="DISCOVERY_PUMPFUN_LATEST", work_state="SUCCEEDED",
            first_terminal_cause="TARGET_CAUSE", terminal_at=NOW,
        )
        self._seed_discovery_work(
            discovery_work_id="other-work", scheduler_job_id=8,
            work_type="DISCOVERY_DEXSCREENER_ACTIVE", work_state="FAILED",
            first_terminal_cause="OTHER_CAUSE", terminal_at=LATER,
        )
        self._set_job_status(8, "SUCCEEDED", finished_at=NOW)
        result = project_campaign_scheduler_work(
            self.connection, scheduler_work_id="work-target",
            campaign_id="campaign-a", run_id="run-a", cycle_id="cycle-a",
            work_scope="DISCOVERY_SELECTION", stage_id="STAGE_DISCOVERY",
            work_intent="DISCOVER", deadline_at=NOW, scheduler_job_id=8,
            target_category="DISCOVERY_WORK", target_identity="target-work",
            now=NOW,
        )
        self.assertTrue(result.created)
        row = self._work_row("work-target")
        self.assertEqual(row["first_terminal_cause"], "TARGET_CAUSE")
        self.assertEqual(row["terminal_at"], NOW)

    def test_13c_terminal_evidence_must_match_exact_target_work_row(self) -> None:
        self._create_graph()
        self._seed_discovery_batch("disc-1")
        self._seed_discovery_work(
            discovery_work_id="target-active", scheduler_job_id=9,
            work_type="DISCOVERY_PUMPFUN_LATEST", work_state="RUNNING",
        )
        self._seed_discovery_work(
            discovery_work_id="other-terminal", scheduler_job_id=9,
            work_type="DISCOVERY_DEXSCREENER_ACTIVE", work_state="SUCCEEDED",
            first_terminal_cause="OTHER_ONLY", terminal_at=NOW,
        )
        self._set_job_status(9, "SUCCEEDED", finished_at=NOW)
        with self.assertRaises(CampaignOwnershipError):
            project_campaign_scheduler_work(
                self.connection, scheduler_work_id="work-target-active",
                campaign_id="campaign-a", run_id="run-a", cycle_id="cycle-a",
                work_scope="DISCOVERY_SELECTION", stage_id="STAGE_DISCOVERY",
                work_intent="DISCOVER", deadline_at=NOW, scheduler_job_id=9,
                target_category="DISCOVERY_WORK", target_identity="target-active",
                now=NOW,
            )
        self.assertIsNone(self._work_row("work-target-active"))

    def test_13d_terminal_work_state_must_match_scheduler_status(self) -> None:
        self._create_graph()
        self._seed_discovery_batch("disc-1")
        self._seed_discovery_work(
            discovery_work_id="failed-work", scheduler_job_id=10,
            work_state="FAILED", first_terminal_cause="WORK_FAILED",
            terminal_at=NOW,
        )
        self._set_job_status(10, "CANCELLED", finished_at=NOW)
        with self.assertRaises(CampaignOwnershipError):
            project_campaign_scheduler_work(
                self.connection, scheduler_work_id="work-state-mismatch",
                campaign_id="campaign-a", run_id="run-a", cycle_id="cycle-a",
                work_scope="DISCOVERY_SELECTION", stage_id="STAGE_DISCOVERY",
                work_intent="DISCOVER", deadline_at=NOW, scheduler_job_id=10,
                target_category="DISCOVERY_WORK", target_identity="failed-work",
                now=NOW,
            )

    # =======================================================================
    # Proof 5: exact capture excludes another cycle of the same campaign/run
    # =======================================================================
    def test_14_cleanup_foreign_run_or_cycle_blocks(self) -> None:
        self._create_graph()
        self._seed_second_cycle(cycle_id="cycle-b")
        self._seed_discovery_batch("disc-b", cycle_id="cycle-b")
        # Job 6 belongs to campaign-a but under cycle-b, not cycle-a.
        self._seed_discovery_work(
            discovery_work_id="dwork-b", scheduler_job_id=6,
            discovery_batch_id="disc-b", cycle_id="cycle-b",
        )
        capture = capture_campaign_active_scheduler_jobs(
            self.connection, campaign_id="campaign-a", run_id="run-a",
            cycle_id="cycle-a",
        )
        self.assertIsNone(capture.pre_state(6))
        self._set_job_status(6, "CANCELLED", finished_at=NOW)
        with self.assertRaises(CampaignOwnershipError):
            project_campaign_scheduler_work(
                self.connection, scheduler_work_id="work-cf",
                campaign_id="campaign-a", run_id="run-a", cycle_id="cycle-a",
                work_scope="TERMINAL_CLEANUP", stage_id="STAGE_TERMINAL",
                work_intent="CANCEL", deadline_at=NOW, scheduler_job_id=6,
                target_category="SCHEDULER_JOB", target_identity="6",
                cleanup_capture=capture, now=NOW,
            )
        self.assertIsNone(self._work_row("work-cf"))

    def test_14b_capture_excludes_foreign_run(self) -> None:
        self._create_graph()
        self._seed_second_run()
        self._seed_discovery_batch(
            "disc-run-b", run_id="run-b", cycle_id="cycle-run-b"
        )
        self._seed_discovery_work(
            discovery_work_id="dwork-run-b", scheduler_job_id=7,
            discovery_batch_id="disc-run-b", run_id="run-b",
            cycle_id="cycle-run-b",
        )
        capture = capture_campaign_active_scheduler_jobs(
            self.connection, campaign_id="campaign-a", run_id="run-a",
            cycle_id="cycle-a",
        )
        self.assertIsNone(capture.pre_state(7))

    def test_14c_terminal_cleanup_cancels_only_exact_capture(self) -> None:
        self._create_graph()
        self._seed_second_cycle(cycle_id="cycle-b")
        self._seed_discovery_batch("disc-a")
        self._seed_discovery_batch("disc-b", cycle_id="cycle-b")
        self._seed_discovery_work(
            discovery_work_id="dwork-a", scheduler_job_id=5,
            discovery_batch_id="disc-a",
        )
        self._seed_discovery_work(
            discovery_work_id="dwork-b", scheduler_job_id=6,
            discovery_batch_id="disc-b", cycle_id="cycle-b",
        )
        capture = capture_campaign_active_scheduler_jobs(
            self.connection, campaign_id="campaign-a", run_id="run-a",
            cycle_id="cycle-a", captured_at=NOW,
        )
        self.assertEqual(capture.job_ids, (5,))
        for job_id in capture.job_ids:
            cancel_job(
                self.connection, job_id=job_id,
                now=datetime.fromisoformat(NOW),
            )
        statuses = {
            int(row[0]): str(row[1])
            for row in self.connection.execute(
                "SELECT id,status FROM printer_scheduler_jobs WHERE id IN (5,6)"
            )
        }
        self.assertEqual(statuses[5], "CANCELLED")
        self.assertEqual(statuses[6], "PENDING")

    # =======================================================================
    # Proof 6: cleanup capture after cancellation / missing pre-state blocks
    # =======================================================================
    def test_15_cleanup_capture_after_cancel_or_missing_prestate_blocks(self) -> None:
        self._create_graph()
        self._seed_discovery_batch("disc-1")
        self._seed_discovery_work(discovery_work_id="dwork-5", scheduler_job_id=5)
        # (a) Capture taken AFTER cancellation -> pre-state already terminal.
        self._set_job_status(5, "CANCELLED", finished_at=NOW)
        late_capture = capture_campaign_active_scheduler_jobs(
            self.connection, campaign_id="campaign-a", run_id="run-a",
            cycle_id="cycle-a",
        )
        self.assertIsNone(late_capture.pre_state(5))
        with self.assertRaises(CampaignOwnershipError):
            project_campaign_scheduler_work(
                self.connection, scheduler_work_id="work-late",
                campaign_id="campaign-a", run_id="run-a", cycle_id="cycle-a",
                work_scope="TERMINAL_CLEANUP", stage_id="STAGE_TERMINAL",
                work_intent="CANCEL", deadline_at=NOW, scheduler_job_id=5,
                target_category="SCHEDULER_JOB", target_identity="5",
                cleanup_capture=late_capture, now=NOW,
            )
        self.assertIsNone(self._work_row("work-late"))
        # (b) Capture missing the job entirely -> no pre-state.
        empty_capture = SchedulerCleanupCapture(
            campaign_id="campaign-a", run_id="run-a", cycle_id="cycle-a",
            captured_at=NOW, job_states=(),
        )
        with self.assertRaises(CampaignOwnershipError):
            project_campaign_scheduler_work(
                self.connection, scheduler_work_id="work-miss",
                campaign_id="campaign-a", run_id="run-a", cycle_id="cycle-a",
                work_scope="TERMINAL_CLEANUP", stage_id="STAGE_TERMINAL",
                work_intent="CANCEL", deadline_at=NOW, scheduler_job_id=5,
                target_category="SCHEDULER_JOB", target_identity="5",
                cleanup_capture=empty_capture, now=NOW,
            )
        self.assertIsNone(self._work_row("work-miss"))
        # (c) An untyped caller-supplied job-id set is no longer accepted.
        with self.assertRaises(CampaignOwnershipError):
            project_campaign_scheduler_work(
                self.connection, scheduler_work_id="work-raw",
                campaign_id="campaign-a", run_id="run-a", cycle_id="cycle-a",
                work_scope="TERMINAL_CLEANUP", stage_id="STAGE_TERMINAL",
                work_intent="CANCEL", deadline_at=NOW, scheduler_job_id=5,
                target_category="SCHEDULER_JOB", target_identity="5",
                cleanup_capture=[5], now=NOW,
            )
        self.assertIsNone(self._work_row("work-raw"))

    # =======================================================================
    # Proof 7: cleanup target identity different from the job id blocks
    # =======================================================================
    def test_16_cleanup_target_identity_mismatch_blocks(self) -> None:
        self._create_graph()
        self._seed_discovery_batch("disc-1")
        self._seed_discovery_work(discovery_work_id="dwork-5", scheduler_job_id=5)
        capture = capture_campaign_active_scheduler_jobs(
            self.connection, campaign_id="campaign-a", run_id="run-a",
            cycle_id="cycle-a",
        )
        self._set_job_status(5, "CANCELLED", finished_at=NOW)
        with self.assertRaises(CampaignOwnershipError):
            project_campaign_scheduler_work(
                self.connection, scheduler_work_id="work-tid",
                campaign_id="campaign-a", run_id="run-a", cycle_id="cycle-a",
                work_scope="TERMINAL_CLEANUP", stage_id="STAGE_TERMINAL",
                work_intent="CANCEL", deadline_at=NOW, scheduler_job_id=5,
                target_category="SCHEDULER_JOB", target_identity="999",
                cleanup_capture=capture, now=NOW,
            )
        self.assertIsNone(self._work_row("work-tid"))
        # Wrong target category likewise blocks.
        with self.assertRaises(CampaignOwnershipError):
            project_campaign_scheduler_work(
                self.connection, scheduler_work_id="work-tc",
                campaign_id="campaign-a", run_id="run-a", cycle_id="cycle-a",
                work_scope="TERMINAL_CLEANUP", stage_id="STAGE_TERMINAL",
                work_intent="CANCEL", deadline_at=NOW, scheduler_job_id=5,
                target_category="DISCOVERY_WORK", target_identity="5",
                cleanup_capture=capture, now=NOW,
            )
        self.assertIsNone(self._work_row("work-tc"))

    def test_16b_cleanup_token_slot_requires_exact_durable_job_link(self) -> None:
        self._create_graph()
        self._seed_second_cycle(cycle_id="cycle-b")
        self._seed_discovery_batch("disc-1")
        self._seed_discovery_work(discovery_work_id="dwork-5", scheduler_job_id=5)
        capture = capture_campaign_active_scheduler_jobs(
            self.connection, campaign_id="campaign-a", run_id="run-a",
            cycle_id="cycle-a",
        )
        self._set_discovery_work_terminal(
            "dwork-5", "CANCELLED", "CLEANUP_CANCELLED"
        )
        self._set_job_status(5, "CANCELLED", finished_at=NOW)
        for index, slot_id in enumerate(("slot-3", "missing-slot", "slot-1")):
            with self.assertRaises(CampaignOwnershipError):
                project_campaign_scheduler_work(
                    self.connection, scheduler_work_id=f"work-slot-{index}",
                    campaign_id="campaign-a", run_id="run-a", cycle_id="cycle-a",
                    work_scope="TERMINAL_CLEANUP", stage_id="STAGE_TERMINAL",
                    work_intent="CANCEL", deadline_at=NOW, scheduler_job_id=5,
                    target_category="SCHEDULER_JOB", target_identity="5",
                    token_slot_id=slot_id, cleanup_capture=capture, now=NOW,
                )
        lawful = project_campaign_scheduler_work(
            self.connection, scheduler_work_id="work-job-only",
            campaign_id="campaign-a", run_id="run-a", cycle_id="cycle-a",
            work_scope="TERMINAL_CLEANUP", stage_id="STAGE_TERMINAL",
            work_intent="CANCEL", deadline_at=NOW, scheduler_job_id=5,
            target_category="SCHEDULER_JOB", target_identity="5",
            cleanup_capture=capture, now=NOW,
        )
        self.assertTrue(lawful.created)
        self.assertIsNone(self._work_row("work-job-only")["token_slot_id"])

    def test_16c_cleanup_token_slot_with_exact_handoff_link_passes(self) -> None:
        self._create_graph()
        self._seed_discovery_batch("disc-1")
        self._seed_selected_item_link(
            discovery_batch_id="disc-1", selection_batch_id="sel-1",
            selection_item_id=1, merged_candidate_id="cand-1",
            first_window_15m_scheduler_job_id=3, token_slot_id="slot-1",
        )
        capture = capture_campaign_active_scheduler_jobs(
            self.connection, campaign_id="campaign-a", run_id="run-a",
            cycle_id="cycle-a",
        )
        self._set_job_status(3, "CANCELLED", finished_at=NOW)
        result = project_campaign_scheduler_work(
            self.connection, scheduler_work_id="work-linked-slot",
            campaign_id="campaign-a", run_id="run-a", cycle_id="cycle-a",
            work_scope="TERMINAL_CLEANUP", stage_id="STAGE_TERMINAL",
            work_intent="CANCEL", deadline_at=NOW, scheduler_job_id=3,
            target_category="SCHEDULER_JOB", target_identity="3",
            token_slot_id="slot-1", cleanup_capture=capture, now=NOW,
        )
        self.assertTrue(result.created)

    def test_16d_conflicting_cleanup_terminal_evidence_blocks(self) -> None:
        self._create_graph()
        self._seed_discovery_batch("disc-1")
        self._seed_discovery_work(
            discovery_work_id="cleanup-owner-a", scheduler_job_id=11,
            work_type="DISCOVERY_PUMPFUN_LATEST",
        )
        self._seed_discovery_work(
            discovery_work_id="cleanup-owner-b", scheduler_job_id=11,
            work_type="DISCOVERY_DEXSCREENER_ACTIVE",
        )
        capture = capture_campaign_active_scheduler_jobs(
            self.connection, campaign_id="campaign-a", run_id="run-a",
            cycle_id="cycle-a",
        )
        self._set_discovery_work_terminal(
            "cleanup-owner-a", "CANCELLED", "CAUSE_A", terminal_at=NOW
        )
        self._set_discovery_work_terminal(
            "cleanup-owner-b", "CANCELLED", "CAUSE_B", terminal_at=LATER
        )
        self._set_job_status(11, "CANCELLED", finished_at=NOW)
        with self.assertRaises(CampaignOwnershipError):
            project_campaign_scheduler_work(
                self.connection, scheduler_work_id="work-conflicting-cleanup",
                campaign_id="campaign-a", run_id="run-a", cycle_id="cycle-a",
                work_scope="TERMINAL_CLEANUP", stage_id="STAGE_TERMINAL",
                work_intent="CANCEL", deadline_at=NOW, scheduler_job_id=11,
                target_category="SCHEDULER_JOB", target_identity="11",
                cleanup_capture=capture, now=NOW,
            )

    # =======================================================================
    # Proof 8: lifecycle run-step from a factory run not bound to the campaign
    #          run blocks
    # =======================================================================
    def test_17_lifecycle_factory_run_not_bound_blocks(self) -> None:
        self._create_graph()
        # factory-a carries the run-step for job 4, but the campaign run is bound
        # to a different factory run (factory-b).
        self._seed_factory_run_step(factory_run_id="factory-a", scheduler_job_id=4)
        self._seed_factory_run(factory_run_id="factory-b")
        bind_authoritative_run_id(
            self.connection, campaign_run_id="run-a", factory_run_id="factory-b",
            now=NOW,
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

    def test_17b_lifecycle_unbound_campaign_run_blocks(self) -> None:
        # A campaign run whose authoritative_run_id is still NULL cannot own a
        # lifecycle job even when the factory run-step exists.
        self._create_graph()
        self._seed_factory_run_step(factory_run_id="factory-a", scheduler_job_id=4)
        with self.assertRaises(CampaignOwnershipError):
            project_campaign_scheduler_job(
                self.connection, scheduler_work_id="work-life2",
                campaign_id="campaign-a", run_id="run-a", cycle_id="cycle-a",
                token_slot_id="slot-1", window_id="window-15m-a",
                factory_run_id="factory-a", work_intent="CLOSE_WINDOW",
                deadline_at=NOW, scheduler_job_id=4, stage_id="STAGE_WINDOW_15M",
                now=NOW,
            )
        self.assertIsNone(self._work_row("work-life2"))

    # =======================================================================
    # Proof 9: lifecycle target mismatch blocks
    # =======================================================================
    def test_18_lifecycle_target_mismatch_blocks(self) -> None:
        self._create_graph()
        self._seed_factory_run_step(factory_run_id="factory-a", scheduler_job_id=4)
        bind_authoritative_run_id(
            self.connection, campaign_run_id="run-a", factory_run_id="factory-a",
            now=NOW,
        )
        with self.assertRaises(CampaignOwnershipError):
            project_campaign_scheduler_work(
                self.connection, scheduler_work_id="work-life",
                campaign_id="campaign-a", run_id="run-a", cycle_id="cycle-a",
                work_scope="WINDOW_LIFECYCLE", stage_id="STAGE_WINDOW_15M",
                work_intent="CLOSE_WINDOW", deadline_at=NOW, scheduler_job_id=4,
                target_category="CAMPAIGN_WINDOW", target_identity="not-the-window",
                token_slot_id="slot-1", window_id="window-15m-a",
                factory_run_id="factory-a", now=NOW,
            )
        self.assertIsNone(self._work_row("work-life"))
        # Wrong window/slot pairing also blocks.
        with self.assertRaises(CampaignOwnershipError):
            project_campaign_scheduler_job(
                self.connection, scheduler_work_id="work-life3",
                campaign_id="campaign-a", run_id="run-a", cycle_id="cycle-a",
                token_slot_id="slot-2", window_id="window-15m-a",
                factory_run_id="factory-a", work_intent="CLOSE_WINDOW",
                deadline_at=NOW, scheduler_job_id=4, stage_id="STAGE_WINDOW_15M",
                now=NOW,
            )

    # =======================================================================
    # Proof 10: exact lawful state and lineage for every scope passes
    # =======================================================================
    def test_19_all_four_scopes_lawful_pass(self) -> None:
        self._create_graph()
        self._seed_discovery_batch("disc-1")
        # Discovery (job 1) and selection (job 2) both proven via discovery_work.
        self._seed_discovery_work(discovery_work_id="dwork-1", scheduler_job_id=1)
        self._seed_discovery_work(
            discovery_work_id="sel-work", scheduler_job_id=2,
            work_type="DISCOVERY_UNIFORM_SELECTION",
        )
        # Handoff (job 3) proven via the selected-item link.
        self._seed_selected_item_link(
            discovery_batch_id="disc-1", selection_batch_id="sel-1",
            selection_item_id=1, merged_candidate_id="cand-1",
            first_window_15m_scheduler_job_id=3, token_slot_id="slot-1",
        )
        # Lifecycle (job 4) proven via factory run-step + authoritative bind.
        self._seed_factory_run_step(factory_run_id="factory-a", scheduler_job_id=4)
        bind_authoritative_run_id(
            self.connection, campaign_run_id="run-a", factory_run_id="factory-a",
            now=NOW,
        )
        # Cleanup (job 5) proven via discovery_work + pre-cancellation capture.
        self._seed_discovery_work(
            discovery_work_id="dwork-5", scheduler_job_id=5,
            work_type="DISCOVERY_DEXSCREENER_ACTIVE",
        )
        capture = capture_campaign_active_scheduler_jobs(
            self.connection, campaign_id="campaign-a", run_id="run-a",
            cycle_id="cycle-a",
        )
        cleanup_at = "2026-08-01T01:00:00+00:00"
        self._set_discovery_work_terminal(
            "dwork-5", "CANCELLED", "CLEANUP_CANCELLED", terminal_at=cleanup_at
        )
        self._set_job_status(5, "CANCELLED", finished_at=cleanup_at)

        disc = project_campaign_scheduler_work(
            self.connection, scheduler_work_id="s-disc", campaign_id="campaign-a",
            run_id="run-a", cycle_id="cycle-a", work_scope="DISCOVERY_SELECTION",
            stage_id="STAGE_DISCOVERY", work_intent="DISCOVER", deadline_at=NOW,
            scheduler_job_id=1, target_category="DISCOVERY_WORK",
            target_identity="dwork-1", now=NOW,
        )
        self.assertTrue(disc.created)
        self.assertEqual(disc.work_state, "PENDING")

        project_campaign_scheduler_work(
            self.connection, scheduler_work_id="s-sel", campaign_id="campaign-a",
            run_id="run-a", cycle_id="cycle-a", work_scope="DISCOVERY_SELECTION",
            stage_id="STAGE_SELECTION", work_intent="SELECT", deadline_at=NOW,
            scheduler_job_id=2, target_category="DISCOVERY_WORK",
            target_identity="sel-work", now=NOW,
        )
        project_campaign_scheduler_work(
            self.connection, scheduler_work_id="s-hand", campaign_id="campaign-a",
            run_id="run-a", cycle_id="cycle-a", work_scope="FIRST_15M_HANDOFF",
            stage_id="STAGE_HANDOFF", work_intent="HANDOFF", deadline_at=NOW,
            scheduler_job_id=3, target_category="MERGED_CANDIDATE",
            target_identity="cand-1", token_slot_id="slot-1", now=NOW,
        )
        project_campaign_scheduler_job(
            self.connection, scheduler_work_id="s-life", campaign_id="campaign-a",
            run_id="run-a", cycle_id="cycle-a", token_slot_id="slot-1",
            window_id="window-15m-a", factory_run_id="factory-a",
            work_intent="CLOSE_WINDOW", deadline_at=NOW, scheduler_job_id=4,
            stage_id="STAGE_WINDOW_15M", now=NOW,
        )
        clean = project_campaign_scheduler_work(
            self.connection, scheduler_work_id="s-clean", campaign_id="campaign-a",
            run_id="run-a", cycle_id="cycle-a", work_scope="TERMINAL_CLEANUP",
            stage_id="STAGE_TERMINAL", work_intent="CANCEL", deadline_at=NOW,
            scheduler_job_id=5, target_category="SCHEDULER_JOB",
            target_identity="5", cleanup_capture=capture, now=NOW,
        )
        self.assertTrue(clean.created)
        clean_row = self._work_row("s-clean")
        # Terminal state and evidence derived from the canonical Scheduler owner.
        self.assertEqual(clean_row["work_state"], "CANCELLED")
        self.assertEqual(clean_row["first_terminal_cause"], "CLEANUP_CANCELLED")
        self.assertEqual(clean_row["terminal_at"], cleanup_at)

        scopes = {
            row[0] for row in self.connection.execute(
                "SELECT work_scope FROM printer_memory_factory_campaign_scheduler_work "
                "WHERE ownership_contract_version='V2_STAGE_SCOPED'"
            )
        }
        self.assertEqual(scopes, {
            "DISCOVERY_SELECTION", "FIRST_15M_HANDOFF", "WINDOW_LIFECYCLE",
            "TERMINAL_CLEANUP",
        })

    def test_19b_handoff_and_lifecycle_use_scheduler_terminal_fields(self) -> None:
        self._create_graph()
        self._seed_discovery_batch("disc-1")
        self._seed_selected_item_link(
            discovery_batch_id="disc-1", selection_batch_id="sel-1",
            selection_item_id=1, merged_candidate_id="cand-1",
            first_window_15m_scheduler_job_id=3, token_slot_id="slot-1",
        )
        self._seed_factory_run_step(factory_run_id="factory-a", scheduler_job_id=4)
        bind_authoritative_run_id(
            self.connection, campaign_run_id="run-a", factory_run_id="factory-a",
            now=NOW,
        )
        self._set_job_status(3, "CANCELLED", finished_at=NOW)
        self._set_job_status(4, "FAILED", finished_at=LATER, last_error="STEP_FAILED")
        project_campaign_scheduler_work(
            self.connection, scheduler_work_id="terminal-hand",
            campaign_id="campaign-a", run_id="run-a", cycle_id="cycle-a",
            work_scope="FIRST_15M_HANDOFF", stage_id="STAGE_HANDOFF",
            work_intent="HANDOFF", deadline_at=NOW, scheduler_job_id=3,
            target_category="MERGED_CANDIDATE", target_identity="cand-1",
            token_slot_id="slot-1", now=NOW,
        )
        project_campaign_scheduler_job(
            self.connection, scheduler_work_id="terminal-life",
            campaign_id="campaign-a", run_id="run-a", cycle_id="cycle-a",
            token_slot_id="slot-1", window_id="window-15m-a",
            factory_run_id="factory-a", work_intent="CLOSE_WINDOW",
            deadline_at=NOW, scheduler_job_id=4,
            stage_id="STAGE_WINDOW_15M", now=NOW,
        )
        hand = self._work_row("terminal-hand")
        life = self._work_row("terminal-life")
        self.assertEqual(hand["first_terminal_cause"], "SCHEDULER_JOB_CANCELLED")
        self.assertEqual(hand["terminal_at"], NOW)
        self.assertEqual(life["first_terminal_cause"], "STEP_FAILED")
        self.assertEqual(life["terminal_at"], LATER)

    # =======================================================================
    # Proof 11: unchanged repeat is idempotent; lawful Scheduler advance syncs
    # =======================================================================
    def test_20_exact_repeat_idempotent_then_syncs_terminal_advance(self) -> None:
        self._create_graph()
        first = self._project_discovery(work_id="work-disc", job=1)
        self.assertTrue(first.created)
        self.assertEqual(first.work_state, "PENDING")
        unchanged = project_campaign_scheduler_work(
            self.connection, scheduler_work_id="work-disc", campaign_id="campaign-a",
            run_id="run-a", cycle_id="cycle-a", work_scope="DISCOVERY_SELECTION",
            stage_id="STAGE_DISCOVERY", work_intent="DISCOVER", deadline_at=NOW,
            scheduler_job_id=1, target_category="DISCOVERY_WORK",
            target_identity="dwork-1", now=LATER,
        )
        self.assertFalse(unchanged.created)
        self.assertEqual(unchanged.work_state, "PENDING")
        self.assertEqual(self._work_row("work-disc")["updated_at"], NOW)
        # The exact durable owner and Scheduler then advance together.
        self._set_discovery_work_terminal(
            "dwork-1", "CANCELLED", "EXACT_CANCEL", terminal_at=NOW
        )
        self._set_job_status(1, "CANCELLED", finished_at=NOW)
        second = project_campaign_scheduler_work(
            self.connection, scheduler_work_id="work-disc", campaign_id="campaign-a",
            run_id="run-a", cycle_id="cycle-a", work_scope="DISCOVERY_SELECTION",
            stage_id="STAGE_DISCOVERY", work_intent="DISCOVER", deadline_at=NOW,
            scheduler_job_id=1, target_category="DISCOVERY_WORK",
            target_identity="dwork-1", now=LATER,
        )
        self.assertFalse(second.created)
        self.assertEqual(second.work_state, "CANCELLED")
        row = self._work_row("work-disc")
        self.assertEqual(row["work_state"], "CANCELLED")
        self.assertEqual(row["first_terminal_cause"], "EXACT_CANCEL")
        self.assertEqual(row["terminal_at"], NOW)
        self.assertEqual(
            self.connection.execute(
                "SELECT COUNT(*) FROM printer_memory_factory_campaign_scheduler_work"
            ).fetchone()[0],
            1,
        )

    def test_20b_incomplete_scheduler_advance_returns_drift(self) -> None:
        self._create_graph()
        self._project_discovery(work_id="work-disc", job=1)
        self._set_job_status(1, "CANCELLED", finished_at=NOW)
        with self.assertRaisesRegex(
            CampaignOwnershipError, "SCHEDULER_OWNERSHIP_STATE_DRIFT"
        ):
            project_campaign_scheduler_work(
                self.connection, scheduler_work_id="work-disc",
                campaign_id="campaign-a", run_id="run-a", cycle_id="cycle-a",
                work_scope="DISCOVERY_SELECTION", stage_id="STAGE_DISCOVERY",
                work_intent="DISCOVER", deadline_at=NOW, scheduler_job_id=1,
                target_category="DISCOVERY_WORK", target_identity="dwork-1",
                now=LATER,
            )
        self.assertEqual(self._work_row("work-disc")["work_state"], "PENDING")

    def test_20c_first_terminal_cause_remains_immutable(self) -> None:
        self._create_graph()
        self._project_discovery(work_id="work-disc", job=1)
        self._set_discovery_work_terminal(
            "dwork-1", "CANCELLED", "FIRST_CAUSE", terminal_at=NOW
        )
        self._set_job_status(1, "CANCELLED", finished_at=NOW)
        project_campaign_scheduler_work(
            self.connection, scheduler_work_id="work-disc",
            campaign_id="campaign-a", run_id="run-a", cycle_id="cycle-a",
            work_scope="DISCOVERY_SELECTION", stage_id="STAGE_DISCOVERY",
            work_intent="DISCOVER", deadline_at=NOW, scheduler_job_id=1,
            target_category="DISCOVERY_WORK", target_identity="dwork-1", now=NOW,
        )
        self._set_discovery_work_terminal(
            "dwork-1", "CANCELLED", "LATER_CAUSE", terminal_at=LATER
        )
        with self.assertRaisesRegex(
            CampaignOwnershipError, "SCHEDULER_OWNERSHIP_STATE_DRIFT"
        ):
            project_campaign_scheduler_work(
                self.connection, scheduler_work_id="work-disc",
                campaign_id="campaign-a", run_id="run-a", cycle_id="cycle-a",
                work_scope="DISCOVERY_SELECTION", stage_id="STAGE_DISCOVERY",
                work_intent="DISCOVER", deadline_at=NOW, scheduler_job_id=1,
                target_category="DISCOVERY_WORK", target_identity="dwork-1",
                now=LATER,
            )
        row = self._work_row("work-disc")
        self.assertEqual(row["first_terminal_cause"], "FIRST_CAUSE")
        self.assertEqual(row["terminal_at"], NOW)

    # =======================================================================
    # Retained: duplicate job ownership + competing identity + handoff owner
    # =======================================================================
    def test_21_duplicate_scheduler_job_blocks(self) -> None:
        self._create_graph()
        self._project_discovery(work_id="work-disc", job=1)
        self._seed_discovery_work(
            discovery_work_id="dwork-x", scheduler_job_id=1,
            work_type="DISCOVERY_DEXSCREENER_ACTIVE",
        )
        with self.assertRaises(CampaignOwnershipError):
            project_campaign_scheduler_work(
                self.connection, scheduler_work_id="work-other",
                campaign_id="campaign-a", run_id="run-a", cycle_id="cycle-a",
                work_scope="DISCOVERY_SELECTION", stage_id="STAGE_DISCOVERY",
                work_intent="DISCOVER", deadline_at=NOW, scheduler_job_id=1,
                target_category="DISCOVERY_WORK", target_identity="dwork-x",
                now=NOW,
            )
        self.assertIsNone(self._work_row("work-other"))

    def test_22_competing_identity_blocks(self) -> None:
        self._create_graph()
        self._project_discovery(work_id="work-disc", job=1)
        # Same scheduler_work_id, different stage -> competing ownership.
        with self.assertRaises(CampaignOwnershipError):
            project_campaign_scheduler_work(
                self.connection, scheduler_work_id="work-disc",
                campaign_id="campaign-a", run_id="run-a", cycle_id="cycle-a",
                work_scope="DISCOVERY_SELECTION", stage_id="STAGE_OTHER",
                work_intent="DISCOVER", deadline_at=NOW, scheduler_job_id=1,
                target_category="DISCOVERY_WORK", target_identity="dwork-1",
                now=NOW,
            )
        self.assertEqual(self._work_row("work-disc")["stage_id"], "STAGE_DISCOVERY")

    def test_23_handoff_without_owner_blocks(self) -> None:
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


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
