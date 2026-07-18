"""V2-9.7D.2A campaign persistence tests using temporary databases only."""

from __future__ import annotations

from contextlib import closing
from datetime import datetime, timezone
import os
from pathlib import Path
import shutil
import sqlite3
import tempfile
import unittest
from unittest.mock import patch

from printer_v1.db import apply_migrations
from printer_v1.db import migrate as migration_runner
from printer_v1.operator_cli.campaign_persistence import (
    CampaignPersistenceError,
    DB_MODE_OPERATIONAL_PERSISTENT,
    DB_MODE_PROOF_ISOLATED,
    create_campaign,
    persist_report_replay,
    persist_terminal_report,
)


MIGRATION = "031_operational_campaign_persistence.sql"
NEW_TABLES = (
    "printer_memory_factory_campaigns",
    "printer_memory_factory_campaign_configurations",
    "printer_memory_factory_campaign_reports",
)
LOCKED_TABLES = (
    "printer_source_requests",
    "printer_source_responses",
    "printer_source_failures",
    "printer_scheduler_jobs",
    "printer_token_snapshots",
    "printer_memory_windows",
    "printer_episodes",
    "printer_memory_retrieval_queries",
    "printer_memory_retrieval_matches",
    "printer_paper_decisions",
    "printer_paper_positions",
    "printer_paper_trade_events",
    "printer_paper_trade_audits",
    "printer_paper_audit_reports",
)


def _apply_through(db_path: Path, maximum_prefix: int) -> None:
    connection = sqlite3.connect(db_path)
    try:
        connection.execute("PRAGMA foreign_keys = ON")
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS printer_schema_migrations (
                version TEXT PRIMARY KEY,
                applied_at TEXT NOT NULL DEFAULT (datetime('now'))
            )
            """
        )
        applied = {
            str(row[0])
            for row in connection.execute(
                "SELECT version FROM printer_schema_migrations"
            ).fetchall()
        }
        for path in sorted(migration_runner.MIGRATIONS_DIR.glob("*.sql")):
            if int(path.name.split("_", 1)[0]) > maximum_prefix:
                continue
            if path.name in applied:
                continue
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
        "git_provenance_captured_at": "2026-07-18T00:00:00+00:00",
    }


class CampaignPersistenceTests(unittest.TestCase):
    def setUp(self) -> None:
        configured_temp = os.environ.get("TEMP") or os.environ.get("TMP")
        self.temp = tempfile.TemporaryDirectory(dir=configured_temp)
        self.root = Path(self.temp.name)
        self.db = self.root / "isolated.sqlite3"

    def tearDown(self) -> None:
        self.temp.cleanup()

    def _create(
        self,
        campaign_id: str = "campaign-a",
        configuration_id: str = "config-a",
        **overrides: object,
    ) -> dict[str, object]:
        arguments: dict[str, object] = {
            "campaign_id": campaign_id,
            "configuration_id": configuration_id,
            "configuration": {"cycle_limit": 2, "token_capacity": 2},
            "launch_provenance": _provenance(),
            "db_mode": DB_MODE_OPERATIONAL_PERSISTENT,
            "db_target_identity": "sha256:operational-db",
            "policy_version": "V2-9.7C",
            "now": datetime(2026, 7, 18, tzinfo=timezone.utc),
        }
        arguments.update(overrides)
        return create_campaign(self.db, **arguments)

    def test_fresh_schema_and_repeated_migration_are_idempotent(self) -> None:
        apply_migrations(self.db)
        apply_migrations(self.db)

        with closing(sqlite3.connect(self.db)) as connection:
            tables = {
                str(row[0])
                for row in connection.execute(
                    "SELECT name FROM sqlite_master WHERE type='table'"
                ).fetchall()
            }
            versions = connection.execute(
                "SELECT COUNT(*) FROM printer_schema_migrations WHERE version=?",
                (MIGRATION,),
            ).fetchone()[0]
            counts = {
                table: connection.execute(
                    f"SELECT COUNT(*) FROM {table}"
                ).fetchone()[0]
                for table in NEW_TABLES
            }

        self.assertTrue(set(NEW_TABLES).issubset(tables))
        self.assertEqual(versions, 1)
        self.assertEqual(counts, {table: 0 for table in NEW_TABLES})

    def test_upgrade_preserves_existing_rows(self) -> None:
        _apply_through(self.db, 30)
        with closing(sqlite3.connect(self.db)) as connection:
            connection.execute(
                """
                INSERT INTO printer_tokens(
                    token_mint, chain, symbol, token_status
                ) VALUES ('mint-before-031', 'solana', 'OLD', 'TRACKING')
                """
            )
            connection.execute(
                """
                INSERT INTO printer_memory_factory_runs(
                    run_id, run_status, window_kind, db_mode,
                    config_hash, config_json, started_at
                ) VALUES (
                    'run-before-031', 'TERMINAL', 'WINDOW_15M',
                    'PROOF_ONLY', 'old-hash', '{}', '2026-07-17T00:00:00Z'
                )
                """
            )
            connection.commit()

        disposable_copy = self.root / "upgrade-copy.sqlite3"
        shutil.copy2(self.db, disposable_copy)
        apply_migrations(disposable_copy)

        with closing(sqlite3.connect(disposable_copy)) as connection:
            token = connection.execute(
                "SELECT token_mint, symbol FROM printer_tokens"
            ).fetchone()
            run = connection.execute(
                "SELECT run_id, db_mode FROM printer_memory_factory_runs"
            ).fetchone()
            version = connection.execute(
                "SELECT COUNT(*) FROM printer_schema_migrations WHERE version=?",
                (MIGRATION,),
            ).fetchone()[0]
        self.assertEqual(token, ("mint-before-031", "OLD"))
        self.assertEqual(run, ("run-before-031", "PROOF_ONLY"))
        self.assertEqual(version, 1)

    def test_db_modes_are_explicit_and_fail_closed(self) -> None:
        apply_migrations(self.db)
        proof = self._create(
            campaign_id="campaign-proof",
            configuration_id="config-proof",
            db_mode=DB_MODE_PROOF_ISOLATED,
            db_target_identity="sha256:proof-copy",
            proof_source_db_identity="sha256:persistent-source",
        )
        operational = self._create()

        self.assertEqual(proof["db_mode"], DB_MODE_PROOF_ISOLATED)
        self.assertEqual(
            proof["proof_source_db_identity"], "sha256:persistent-source"
        )
        self.assertEqual(
            operational["db_mode"], DB_MODE_OPERATIONAL_PERSISTENT
        )
        self.assertIsNone(operational["proof_source_db_identity"])

        with self.assertRaisesRegex(
            CampaignPersistenceError, "proof and source DB identities must differ"
        ):
            self._create(
                campaign_id="bad-proof",
                configuration_id="bad-proof-config",
                db_mode=DB_MODE_PROOF_ISOLATED,
                db_target_identity="same",
                proof_source_db_identity="same",
            )
        with self.assertRaisesRegex(
            CampaignPersistenceError,
            "operational mode cannot carry a proof source",
        ):
            self._create(
                campaign_id="bad-operational",
                configuration_id="bad-operational-config",
                proof_source_db_identity="sha256:unexpected-source",
            )

    def test_configuration_is_immutable_and_creation_is_idempotent(self) -> None:
        apply_migrations(self.db)
        first = self._create()
        repeated = self._create()
        self.assertEqual(first["configuration_hash"], repeated["configuration_hash"])

        with self.assertRaisesRegex(
            CampaignPersistenceError, "immutable configuration already differs"
        ):
            self._create(configuration={"cycle_limit": 3, "token_capacity": 2})

        with closing(sqlite3.connect(self.db)) as connection:
            with self.assertRaisesRegex(
                sqlite3.IntegrityError, "campaign configuration is immutable"
            ):
                connection.execute(
                    """UPDATE printer_memory_factory_campaign_configurations
                       SET configuration_json='{}'
                       WHERE configuration_id='config-a'"""
                )
            with self.assertRaisesRegex(
                sqlite3.IntegrityError, "campaign configuration is immutable"
            ):
                connection.execute(
                    """DELETE FROM printer_memory_factory_campaign_configurations
                       WHERE configuration_id='config-a'"""
                )

    def test_configuration_identity_conflict_rolls_back_campaign(self) -> None:
        apply_migrations(self.db)
        self._create()
        with self.assertRaisesRegex(
            CampaignPersistenceError, "campaign persistence failed"
        ):
            self._create(campaign_id="campaign-b", configuration_id="config-a")
        with closing(sqlite3.connect(self.db)) as connection:
            count = connection.execute(
                "SELECT COUNT(*) FROM printer_memory_factory_campaigns "
                "WHERE campaign_id='campaign-b'"
            ).fetchone()[0]
        self.assertEqual(count, 0)

    def test_reports_and_replays_are_exact_linked_and_idempotent(self) -> None:
        apply_migrations(self.db)
        self._create()
        self._create("campaign-b", "config-b")

        terminal = persist_terminal_report(
            self.db,
            report_id="report-a",
            campaign_id="campaign-a",
            configuration_id="config-a",
            report={"status": "TERMINAL_COMPLETED", "clean_yield": 0},
        )
        repeated = persist_terminal_report(
            self.db,
            report_id="report-a",
            campaign_id="campaign-a",
            configuration_id="config-a",
            report={"clean_yield": 0, "status": "TERMINAL_COMPLETED"},
        )
        self.assertEqual(terminal["report_hash"], repeated["report_hash"])

        replay = persist_report_replay(
            self.db,
            report_id="replay-a",
            campaign_id="campaign-a",
            configuration_id="config-a",
            replay_of_report_id="report-a",
            replay_state="REPLAY_VERIFIED",
            report={"semantic_equivalent": True, "sources_run": False},
        )
        self.assertEqual(replay["replay_of_report_id"], "report-a")

        with self.assertRaisesRegex(
            CampaignPersistenceError, "report persistence failed"
        ):
            persist_report_replay(
                self.db,
                report_id="cross-campaign-replay",
                campaign_id="campaign-b",
                configuration_id="config-b",
                replay_of_report_id="report-a",
                replay_state="REPLAY_BLOCKED",
                report={"reason": "identity mismatch"},
            )
        with self.assertRaisesRegex(
            CampaignPersistenceError, "report persistence failed"
        ):
            persist_report_replay(
                self.db,
                report_id="replay-of-replay",
                campaign_id="campaign-a",
                configuration_id="config-a",
                replay_of_report_id="replay-a",
                replay_state="REPLAY_BLOCKED",
                report={"reason": "not a terminal report"},
            )
        with self.assertRaisesRegex(
            CampaignPersistenceError, "immutable payload already differs"
        ):
            persist_terminal_report(
                self.db,
                report_id="report-a",
                campaign_id="campaign-a",
                configuration_id="config-a",
                report={"status": "TERMINAL_FAILED"},
            )

        with closing(sqlite3.connect(self.db)) as connection:
            with self.assertRaisesRegex(
                sqlite3.IntegrityError, "terminal report or replay is immutable"
            ):
                connection.execute(
                    """UPDATE printer_memory_factory_campaign_reports
                       SET report_json='{}' WHERE report_id='report-a'"""
                )

    def test_failed_migration_leaves_no_partial_campaign_schema(self) -> None:
        broken_dir = self.root / "broken-migrations"
        broken_dir.mkdir()
        source = migration_runner.MIGRATIONS_DIR / MIGRATION
        broken = broken_dir / MIGRATION
        broken.write_text(
            source.read_text(encoding="utf-8")
            + "\nSELECT * FROM missing_v2_9_7d_2a_fixture;\n",
            encoding="utf-8",
        )

        with patch.object(migration_runner, "MIGRATIONS_DIR", broken_dir):
            with self.assertRaises(sqlite3.OperationalError):
                migration_runner.apply_migrations(self.db)

        with closing(sqlite3.connect(self.db)) as connection:
            objects = {
                str(row[0])
                for row in connection.execute(
                    "SELECT name FROM sqlite_master "
                    "WHERE type IN ('table','index','trigger')"
                ).fetchall()
            }
            applied = connection.execute(
                "SELECT COUNT(*) FROM printer_schema_migrations WHERE version=?",
                (MIGRATION,),
            ).fetchone()[0]
        self.assertTrue(set(NEW_TABLES).isdisjoint(objects))
        self.assertEqual(applied, 0)

    def test_persistence_creates_no_locked_capability_rows(self) -> None:
        apply_migrations(self.db)
        self._create()
        persist_terminal_report(
            self.db,
            report_id="report-a",
            campaign_id="campaign-a",
            configuration_id="config-a",
            report={"status": "TERMINAL_BLOCKED"},
        )
        persist_report_replay(
            self.db,
            report_id="replay-a",
            campaign_id="campaign-a",
            configuration_id="config-a",
            replay_of_report_id="report-a",
            replay_state="REPLAY_BLOCKED",
            report={"reason": "fixture-only"},
        )
        with closing(sqlite3.connect(self.db)) as connection:
            counts = {
                table: connection.execute(
                    f"SELECT COUNT(*) FROM {table}"
                ).fetchone()[0]
                for table in LOCKED_TABLES
            }
        self.assertEqual(counts, {table: 0 for table in LOCKED_TABLES})


if __name__ == "__main__":
    unittest.main()
