from __future__ import annotations

from pathlib import Path
import shutil
import sqlite3
import tempfile
import unittest
from unittest.mock import patch

from printer_v1.db.migrate import (
    MIGRATIONS_DIR,
    canonical_migration_count,
    canonical_migration_names,
)
from printer_v1.operator_cli import operational_memory_factory_command as command


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "data" / "printer_v1.sqlite3"


class _Dependency:
    status = "READY"

    def to_dict(self):
        return {"status": "READY", "external_requests": 0, "database_writes": 0}


def _build_quiescent_preflight_fixture(destination: Path) -> None:
    """Copy the authoritative corpus into a relationally valid quiescent fixture.

    Historical campaign/discovery/holder rows remain intact so foreign keys stay
    valid. Only active operational surfaces are forced terminal/unlocked.
    """
    if not SOURCE.is_file():
        raise unittest.SkipTest("authoritative corpus unavailable for fixture copy")
    shutil.copy2(SOURCE, destination)
    connection = sqlite3.connect(destination)
    try:
        connection.execute("PRAGMA foreign_keys=ON")
        # Apply any canonical migrations missing from the live corpus copy so
        # preflight can validate against the current code surface without
        # mutating data/printer_v1.sqlite3.
        connection.execute(
            """CREATE TABLE IF NOT EXISTS printer_schema_migrations (
                   version TEXT PRIMARY KEY,
                   applied_at TEXT NOT NULL DEFAULT (datetime('now'))
               )"""
        )
        applied = {
            row[0]
            for row in connection.execute(
                "SELECT version FROM printer_schema_migrations"
            )
        }
        for migration in sorted(MIGRATIONS_DIR.glob("*.sql")):
            if migration.name in applied:
                continue
            connection.executescript(migration.read_text(encoding="utf-8"))
            connection.execute(
                "INSERT INTO printer_schema_migrations(version) VALUES (?)",
                (migration.name,),
            )
        connection.execute(
            """
            UPDATE printer_scheduler_jobs
            SET status='CANCELLED',
                finished_at=COALESCE(finished_at, '2026-07-26T17:00:00+00:00'),
                updated_at='2026-07-26T17:00:00+00:00',
                locked_at=NULL,
                lock_owner=NULL
            WHERE status IN ('PENDING', 'RUNNING')
               OR locked_at IS NOT NULL
               OR lock_owner IS NOT NULL
            """
        )
        connection.execute(
            """
            UPDATE printer_memory_factory_campaigns
            SET campaign_state='TERMINAL_COMPLETED',
                updated_at='2026-07-26T17:00:00+00:00'
            WHERE campaign_state IN ('PREFLIGHT', 'RUNNING', 'STOP_REQUESTED', 'DRAFT')
            """
        )
        connection.execute(
            """
            UPDATE printer_memory_factory_campaign_runs
            SET run_state='TERMINAL_COMPLETED',
                updated_at='2026-07-26T17:00:00+00:00'
            WHERE run_state IN ('RUNNING', 'STOP_REQUESTED')
            """
        )
        connection.execute(
            """
            UPDATE printer_memory_factory_campaign_supervision
            SET supervision_state='TERMINAL',
                terminal_status=COALESCE(terminal_status, 'COMPLETED'),
                updated_at='2026-07-26T17:00:00+00:00'
            WHERE supervision_state IN ('ACTIVE', 'STOPPING')
            """
        )
        connection.execute(
            """
            UPDATE printer_discovery_work
            SET work_state='TERMINAL',
                updated_at='2026-07-26T17:00:00+00:00'
            WHERE work_state IN ('PENDING', 'RUNNING', 'COOLDOWN')
            """
        )
        connection.execute(
            """
            UPDATE printer_memory_factory_run_steps
            SET step_status='SKIPPED',
                updated_at='2026-07-26T17:00:00+00:00'
            WHERE step_status IN ('PENDING', 'RUNNING')
            """
        )
        connection.execute(
            """
            UPDATE printer_proof_run_supervision
            SET execution_status='TERMINAL',
                updated_at='2026-07-26T17:00:00+00:00'
            WHERE execution_status IN ('STARTING', 'RUNNING')
            """
        )
        foreign_keys = connection.execute("PRAGMA foreign_key_check").fetchall()
        if foreign_keys:
            raise AssertionError(
                f"quiescent fixture has FK violations: {foreign_keys[:5]}"
            )
        integrity = connection.execute("PRAGMA integrity_check").fetchone()[0]
        if integrity != "ok":
            raise AssertionError(f"quiescent fixture integrity failed: {integrity}")
        connection.commit()
    finally:
        connection.close()


class PublicOperationalCommandTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.db = Path(self.temp.name) / "printer_v1.sqlite3"
        _build_quiescent_preflight_fixture(self.db)

    def tearDown(self) -> None:
        self.temp.cleanup()

    def test_fixed_policy_is_two_token_15m_only(self) -> None:
        self.assertEqual(2, command.TOKEN_CAPACITY)
        self.assertEqual("WINDOW_15M", command.MAIN_WINDOW)
        self.assertEqual(900, command.MAIN_WINDOW_SECONDS)
        self.assertEqual(
            ("WINDOW_1H", "WINDOW_4H", "WINDOW_12H", "WINDOW_24H"),
            command.LOCKED_WINDOWS,
        )
        self.assertEqual(0, command.AUTOMATIC_RETRIES)
        self.assertEqual(51, command.SCHEDULER_ROW_CEILING)
        self.assertEqual(65, command.GOVERNED_15M_REQUEST_CEILING)

    def test_proof_or_alternate_db_is_rejected(self) -> None:
        with self.assertRaises(command.OperationalMemoryFactoryError):
            command.build_activation_preflight(db_path=self.db)

    def test_preflight_is_zero_source_and_zero_write_after_scheduler_terminal(self) -> None:
        connection = sqlite3.connect(self.db)
        connection.execute(
            "UPDATE printer_scheduler_jobs SET status='CANCELLED',"
            "finished_at='2026-07-26T17:00:00+00:00',"
            "updated_at='2026-07-26T17:00:00+00:00' "
            "WHERE id IN (8,9,10,11,12,13,14,15,16,17,18,738,980,981,982)"
        )
        connection.commit()
        connection.close()
        before = self.db.read_bytes()
        source_ready = {
            "status": "READY",
            "external_requests": 0,
            "secret_material_recorded": False,
        }
        provenance = {
            "git_head": "93a3ca214277c5840fc35d88f44ca15c1ec10863",
            "git_tracked_tree_clean": True,
            "git_staged_changes_present": False,
            "git_unstaged_changes_present": False,
            "git_untracked_present": False,
            "git_provenance_captured_at": "2026-07-26T17:00:00+00:00",
        }
        with (
            patch.object(command, "AUTHORITATIVE_DB", self.db.resolve()),
            patch.object(
                command,
                "build_readiness_source_contract_preflight",
                return_value=source_ready,
            ),
            patch.object(
                command,
                "assert_runtime_dependency_preflight",
                return_value=_Dependency(),
            ),
            patch.object(command, "capture_git_provenance", return_value=provenance),
            patch.object(
                command,
                "_capture_operational_git_provenance",
                return_value=provenance,
            ),
        ):
            report = command.build_activation_preflight(
                db_path=self.db, repository_root=ROOT
            )
        self.assertEqual("V2_9_8_OPERATIONAL_PREFLIGHT_READY", report["status"])
        self.assertEqual(canonical_migration_count(), report["migration_count"])
        self.assertEqual(canonical_migration_names()[-1], report["latest_migration"])
        self.assertEqual(0, report["source_calls"])
        self.assertEqual(0, report["scheduler_runtime_calls"])
        self.assertEqual(0, report["database_writes"])
        self.assertEqual(before, self.db.read_bytes())

    def test_run_requires_explicit_operator_approval_before_preflight(self) -> None:
        with self.assertRaises(command.OperationalMemoryFactoryError):
            command.run_operational_campaign(operator_approved=False)

    def test_registered_cli_and_wrapper_do_not_reference_proof_launcher(self) -> None:
        pyproject = (ROOT / "pyproject.toml").read_text()
        wrapper = (ROOT / "scripts" / "Start-PrinterV1-MemoryFactory.ps1").read_text()
        self.assertIn("printer-run-v2-9-8-memory-factory", pyproject)
        self.assertIn("operational_memory_factory_command:main", pyproject)
        self.assertNotIn("Start-V2-9-Proof", wrapper)
        self.assertNotIn("v2_9_7e_14_two_token_operational_pilot", wrapper)
        self.assertIn("selective-1h-preflight", wrapper)
        self.assertIn("selective-1h-proof", wrapper)

    def test_normal_run_and_selective_proof_use_distinct_fixed_policies(self) -> None:
        with patch.object(
            command, "_run_operational_campaign", return_value={"status": "TEST"}
        ) as runner:
            command.run_operational_campaign(operator_approved=True)
            normal = runner.call_args.kwargs["policy"]
            self.assertEqual("run", normal.mode)
            self.assertFalse(normal.selective_1h_continuation)
            self.assertIn("WINDOW_1H", normal.locked_windows)
            self.assertEqual(1200, normal.duration_seconds)

            command.run_selective_1h_proof(operator_approved=True)
            selective = runner.call_args.kwargs["policy"]
            self.assertEqual("selective-1h-proof", selective.mode)
            self.assertTrue(selective.selective_1h_continuation)
            self.assertNotIn("WINDOW_1H", selective.locked_windows)
            self.assertEqual(
                ("WINDOW_4H", "WINDOW_12H", "WINDOW_24H"),
                selective.locked_windows,
            )
            self.assertEqual(3900, selective.duration_seconds)
            self.assertEqual(92, selective.governed_request_ceiling)
            self.assertEqual(45, selective.governed_requests_per_token)
            self.assertEqual(82, selective.scheduler_row_ceiling)

    def test_selective_proof_requires_operator_approval_before_preflight(self) -> None:
        with self.assertRaises(command.OperationalMemoryFactoryError):
            command.run_selective_1h_proof(operator_approved=False)

    def test_python_cli_dispatches_both_selective_modes(self) -> None:
        with (
            patch.object(
                command,
                "build_selective_1h_preflight",
                return_value={"mode": "selective-1h-preflight"},
            ) as preflight,
            patch("builtins.print"),
        ):
            self.assertEqual(0, command.main(["selective-1h-preflight"]))
        preflight.assert_called_once_with()

        with (
            patch.object(
                command,
                "run_selective_1h_proof",
                return_value={"mode": "selective-1h-proof"},
            ) as proof,
            patch("builtins.print"),
        ):
            self.assertEqual(
                0,
                command.main(["selective-1h-proof", "--operator-approved"]),
            )
        proof.assert_called_once_with(operator_approved=True)

    def test_selective_preflight_is_read_only_and_reports_fixed_policy(self) -> None:
        before = self.db.read_bytes()
        source_ready = {
            "status": "READY",
            "external_requests": 0,
            "secret_material_recorded": False,
        }
        provenance = {
            "git_head": "67ae2a3a1d7bdd89d1acdf44a00f21091d727661",
            "git_tracked_tree_clean": True,
            "git_staged_changes_present": False,
            "git_unstaged_changes_present": False,
            "git_untracked_present": False,
            "git_provenance_captured_at": "2026-07-28T17:00:00+00:00",
        }
        with (
            patch.object(command, "AUTHORITATIVE_DB", self.db.resolve()),
            patch.object(
                command,
                "build_readiness_source_contract_preflight",
                return_value=source_ready,
            ),
            patch.object(
                command,
                "assert_runtime_dependency_preflight",
                return_value=_Dependency(),
            ),
            patch.object(command, "capture_git_provenance", return_value=provenance),
            patch.object(
                command,
                "_capture_operational_git_provenance",
                return_value=provenance,
            ),
        ):
            report = command.build_selective_1h_preflight(
                db_path=self.db, repository_root=ROOT
            )
        self.assertEqual(
            "V2_9_8B_SELECTIVE_1H_PREFLIGHT_READY", report["status"]
        )
        self.assertEqual(0, report["source_calls"])
        self.assertEqual(0, report["scheduler_runtime_calls"])
        self.assertEqual(0, report["database_writes"])
        self.assertTrue(report["migration_requirement"]["applied"])
        self.assertEqual(92, report["proof_ceilings"]["governed_requests"])
        self.assertEqual(82, report["proof_ceilings"]["scheduler_rows"])
        self.assertEqual(4, report["proof_ceilings"]["reserved_mandatory_close_steps"])
        self.assertTrue(report["host_awake_requirement"]["required"])
        self.assertTrue(
            report["backup_restore_requirement"]["required_before_campaign_creation"]
        )
        self.assertFalse(report["proof_policy"]["continuous_four_hour"])
        self.assertFalse(report["proof_policy"]["restart_created"])
        self.assertFalse(report["proof_policy"]["successor_created"])
        self.assertEqual(before, self.db.read_bytes())

    def test_selective_preflight_blocks_when_migration_047_is_missing(self) -> None:
        connection = sqlite3.connect(self.db)
        connection.execute(
            "DELETE FROM printer_schema_migrations WHERE version=?",
            (command.SELECTIVE_1H_REQUIRED_MIGRATION,),
        )
        connection.commit()
        connection.close()
        before = self.db.read_bytes()
        with patch.object(command, "AUTHORITATIVE_DB", self.db.resolve()):
            with self.assertRaisesRegex(
                command.OperationalMemoryFactoryError, "gate=migration_047"
            ):
                command.build_selective_1h_preflight(db_path=self.db)
        self.assertEqual(before, self.db.read_bytes())

    def test_cli_parser_rejects_unknown_mode(self) -> None:
        with self.assertRaises(SystemExit):
            command.main(["proof"])


if __name__ == "__main__":
    unittest.main()
