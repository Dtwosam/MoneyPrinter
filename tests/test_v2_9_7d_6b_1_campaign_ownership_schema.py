"""Focused V2-9.7D.6B.1 ownership/schema tests; disposable DBs only."""

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
    canonical_object_payload,
    create_campaign_run,
    create_cycle_with_two_slots,
    link_report_object,
    persist_immutable_object,
    persist_scheduler_work,
    persist_window,
    transition_state,
)
from printer_v1.operator_cli.campaign_persistence import (
    DB_MODE_PROOF_ISOLATED,
    create_campaign,
)


NOW = "2026-07-19T00:00:00+00:00"
LOCKED_TABLES = (
    "printer_memory_retrieval_queries", "printer_memory_retrieval_matches",
    "printer_paper_decisions", "printer_paper_positions",
    "printer_paper_trade_events", "printer_paper_trade_audits",
    "printer_paper_audit_reports",
)


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


def _provenance() -> dict[str, object]:
    return {
        "git_head": "a" * 40,
        "git_tracked_tree_clean": True,
        "git_staged_changes_present": False,
        "git_unstaged_changes_present": False,
        "git_untracked_present": True,
        "git_provenance_captured_at": NOW,
    }


class CampaignOwnershipSchemaTests(unittest.TestCase):
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
            policy_version="v2-9.7d",
        )
        self.connection = sqlite3.connect(self.db)
        self.connection.execute("PRAGMA foreign_keys = ON")
        self.connection.row_factory = sqlite3.Row
        self._seed_existing_rows()

    def tearDown(self) -> None:
        self.connection.close()
        self.temp.cleanup()

    def _seed_existing_rows(self) -> None:
        with self.connection:
            for token_id in (1, 2, 3):
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
            self.connection.execute(
                """INSERT INTO printer_scheduler_jobs(
                    id,job_name,job_kind,status,scheduled_for
                ) VALUES (1,'close-1','MEMORY_WINDOW_CLOSE','PENDING',?)""",
                (NOW,),
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

    def test_upgrade_from_031_preserves_existing_campaign_and_token_rows(self) -> None:
        upgrade_db = Path(self.temp.name) / "upgrade.sqlite3"
        _apply_through(upgrade_db, 31)
        create_campaign(
            upgrade_db, campaign_id="upgrade-campaign",
            configuration_id="upgrade-configuration", configuration={"slots": 2},
            launch_provenance=_provenance(), db_mode=DB_MODE_PROOF_ISOLATED,
            db_target_identity="upgrade-isolated",
            proof_source_db_identity="upgrade-source", policy_version="v2-9.7d",
        )
        upgrade_connection = sqlite3.connect(upgrade_db)
        try:
            upgrade_connection.execute(
                "INSERT INTO printer_tokens(id,token_mint) VALUES (91,'mint-91')"
            )
            upgrade_connection.commit()
        finally:
            upgrade_connection.close()
        apply_migrations(upgrade_db)
        upgrade_connection = sqlite3.connect(upgrade_db)
        try:
            self.assertEqual(
                upgrade_connection.execute(
                    "SELECT campaign_state FROM printer_memory_factory_campaigns WHERE campaign_id='upgrade-campaign'"
                ).fetchone()[0],
                "DRAFT",
            )
            self.assertEqual(
                upgrade_connection.execute(
                    "SELECT token_mint FROM printer_tokens WHERE id=91"
                ).fetchone()[0],
                "mint-91",
            )
            self.assertIsNotNone(
                upgrade_connection.execute(
                    "SELECT 1 FROM printer_schema_migrations WHERE version='032_campaign_ownership_schema.sql'"
                ).fetchone()
            )
        finally:
            upgrade_connection.close()

    def test_clean_migration_graph_has_exact_two_slots_and_reopens(self) -> None:
        before = tuple(
            self.connection.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
            for table in ("printer_tokens", "printer_pairs", "printer_memory_windows")
        )
        self._create_graph()
        persist_scheduler_work(
            self.connection, scheduler_work_id="work-a", campaign_id="campaign-a",
            run_id="run-a", cycle_id="cycle-a", token_slot_id="slot-1",
            window_id="window-15m-a", work_intent="CLOSE_WINDOW",
            deadline_at=NOW, scheduler_job_id=1, now=NOW,
        )
        self.assertEqual(
            self.connection.execute(
                "SELECT COUNT(*) FROM printer_memory_factory_campaign_token_slots WHERE cycle_id='cycle-a'"
            ).fetchone()[0],
            2,
        )
        self.assertEqual(before, tuple(
            self.connection.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
            for table in ("printer_tokens", "printer_pairs", "printer_memory_windows")
        ))
        self.connection.close()
        self.connection = sqlite3.connect(self.db)
        self.connection.execute("PRAGMA foreign_keys = ON")
        self.assertEqual(
            self.connection.execute("PRAGMA foreign_key_check").fetchall(), []
        )
        self.assertEqual(
            self.connection.execute(
                "SELECT scheduler_job_id FROM printer_memory_factory_campaign_scheduler_work WHERE scheduler_work_id='work-a'"
            ).fetchone()[0],
            1,
        )

    def test_exact_two_slots_and_mismatches_fail_and_roll_back(self) -> None:
        create_campaign_run(
            self.connection, campaign_id="campaign-a", run_id="run-a",
            run_ordinal=1, now=NOW,
        )
        with self.assertRaisesRegex(CampaignOwnershipError, "exactly two"):
            create_cycle_with_two_slots(
                self.connection, campaign_id="campaign-a", run_id="run-a",
                cycle_id="cycle-short", cycle_ordinal=1,
                slots=(self._slot(1, 1),), now=NOW,
            )
        bad = self._slot(2, 2)
        bad["pair_row_id"] = 3
        bad["pair_identity"] = "pair-3"
        with self.assertRaisesRegex(CampaignOwnershipError, "token and pair"):
            create_cycle_with_two_slots(
                self.connection, campaign_id="campaign-a", run_id="run-a",
                cycle_id="cycle-bad", cycle_ordinal=1,
                slots=(self._slot(1, 1), bad), now=NOW,
            )
        self.assertEqual(
            self.connection.execute(
                "SELECT COUNT(*) FROM printer_memory_factory_campaign_cycles"
            ).fetchone()[0],
            0,
        )

    def test_predecessor_and_cross_token_window_mismatches_fail_closed(self) -> None:
        self._create_graph()
        with self.assertRaisesRegex(CampaignOwnershipError, "token or pair"):
            persist_window(
                self.connection, window_id="wrong-token", campaign_id="campaign-a",
                run_id="run-a", cycle_id="cycle-a", token_slot_id="slot-1",
                token_row_id=2, pair_row_id=2, window_kind="WINDOW_1H",
                root_15m_lifecycle_identity="lifecycle-1", checkpoint_cutoff=NOW,
                predecessor_window_id="window-15m-a", now=NOW,
            )
        persist_window(
            self.connection, window_id="window-15m-b", campaign_id="campaign-a",
            run_id="run-a", cycle_id="cycle-a", token_slot_id="slot-2",
            token_row_id=2, pair_row_id=2, window_kind="WINDOW_15M",
            root_15m_lifecycle_identity="lifecycle-2", checkpoint_cutoff=NOW,
            now=NOW,
        )
        with self.assertRaises(CampaignOwnershipError):
            persist_window(
                self.connection, window_id="foreign-predecessor", campaign_id="campaign-a",
                run_id="run-a", cycle_id="cycle-a", token_slot_id="slot-1",
                token_row_id=1, pair_row_id=1, window_kind="WINDOW_1H",
                root_15m_lifecycle_identity="lifecycle-1", checkpoint_cutoff=NOW,
                predecessor_window_id="window-15m-b", now=NOW,
            )

    def test_compare_update_terminalization_is_idempotent_and_cause_immutable(self) -> None:
        self._create_graph()
        first = transition_state(
            self.connection, record_kind="run", identity="run-a",
            expected_state="DRAFT", new_state="TERMINAL_BLOCKED",
            terminal_cause="FIRST_FAULT", now=NOW,
        )
        repeated = transition_state(
            self.connection, record_kind="run", identity="run-a",
            expected_state="DRAFT", new_state="TERMINAL_BLOCKED",
            terminal_cause="FIRST_FAULT", now="2026-07-19T01:00:00+00:00",
        )
        self.assertTrue(first.changed)
        self.assertFalse(repeated.changed)
        self.assertEqual(repeated.terminal_at, NOW)
        with self.assertRaisesRegex(CampaignOwnershipError, "immutable"):
            transition_state(
                self.connection, record_kind="run", identity="run-a",
                expected_state="DRAFT", new_state="TERMINAL_FAILED",
                terminal_cause="LATER_FAULT", now=NOW,
            )
        with self.assertRaisesRegex(CampaignOwnershipError, "compare-and-update"):
            transition_state(
                self.connection, record_kind="cycle", identity="cycle-a",
                expected_state="TRACKING", new_state="CLOSING", now=NOW,
            )

    def test_immutable_canonical_objects_are_deterministic_and_create_no_locked_rows(self) -> None:
        self._create_graph()
        first_json, first_hash = canonical_object_payload({"b": 2, "a": [1]})
        second_json, second_hash = canonical_object_payload({"a": [1], "b": 2})
        self.assertEqual((first_json, first_hash), (second_json, second_hash))
        stored_hash = persist_immutable_object(
            self.connection, object_id="trajectory-a", object_kind="TRAJECTORY_5A",
            campaign_id="campaign-a", configuration_id="configuration-a",
            run_id="run-a", cycle_id="cycle-a", token_slot_id="slot-1",
            window_id="window-15m-a", payload={"b": 2, "a": [1]}, now=NOW,
        )
        self.assertEqual(stored_hash, first_hash)
        with self.connection:
            self.connection.execute(
                """INSERT INTO printer_memory_factory_campaign_reports(
                    report_id,campaign_id,configuration_id,report_kind,
                    report_state,created_at
                ) VALUES ('report-a','campaign-a','configuration-a',
                    'TERMINAL','REPORT_PENDING',?)""",
                (NOW,),
            )
        link_report_object(
            self.connection, report_id="report-a", campaign_id="campaign-a",
            configuration_id="configuration-a", object_id="trajectory-a", now=NOW,
        )
        with self.assertRaises(sqlite3.IntegrityError):
            self.connection.execute(
                "UPDATE printer_memory_factory_campaign_objects SET object_json='{}' WHERE object_id='trajectory-a'"
            )
        with self.assertRaises(sqlite3.IntegrityError):
            self.connection.execute(
                "UPDATE printer_memory_factory_campaign_report_objects SET object_id='changed' WHERE report_id='report-a'"
            )
        for table in LOCKED_TABLES:
            self.assertEqual(
                self.connection.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0],
                0,
                table,
            )


if __name__ == "__main__":
    unittest.main()
