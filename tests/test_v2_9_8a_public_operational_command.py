from __future__ import annotations

import json
from pathlib import Path
import shutil
import tempfile
import unittest
from unittest.mock import patch

from printer_v1.operator_cli import operational_memory_factory_command as command


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "data" / "printer_v1.sqlite3"


class _Dependency:
    status = "READY"
    def to_dict(self):
        return {"status": "READY", "external_requests": 0, "database_writes": 0}


class PublicOperationalCommandTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.db = Path(self.temp.name) / "printer_v1.sqlite3"
        shutil.copy2(SOURCE, self.db)

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
        connection = __import__("sqlite3").connect(self.db)
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
            "tracked_tree_clean": True,
            "staged_changes": False,
            "unstaged_changes": False,
            "untracked_changes": False,
            "captured_at": "2026-07-26T17:00:00+00:00",
        }
        with (
            patch.object(command, "AUTHORITATIVE_DB", self.db.resolve()),
            patch.object(command, "build_readiness_source_contract_preflight", return_value=source_ready),
            patch.object(command, "assert_runtime_dependency_preflight", return_value=_Dependency()),
            patch.object(command, "capture_git_provenance", return_value=provenance),
        ):
            report = command.build_activation_preflight(
                db_path=self.db, repository_root=ROOT
            )
        self.assertEqual("V2_9_8_OPERATIONAL_PREFLIGHT_READY", report["status"])
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

    def test_cli_parser_rejects_unknown_mode(self) -> None:
        with self.assertRaises(SystemExit):
            command.main(["proof"])


if __name__ == "__main__":
    unittest.main()
