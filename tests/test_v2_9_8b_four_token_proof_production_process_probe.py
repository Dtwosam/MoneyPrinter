"""Focused contract for the production four-token Printer-process probe.

Offline only. No Printer runtime is started: the OS liveness predicate is
injected so an "existing Printer runtime" is simulated from durable supervision
evidence alone. The wrapper's own default zero-state gate is exercised — it is
never replaced by a fake gate — and no authoritative database is touched.
"""

from __future__ import annotations

import os
import sqlite3
import tempfile
import unittest
from pathlib import Path

from printer_v1.db import apply_migrations
from printer_v1.operator_cli import (
    four_token_proof_one_shot_wrapper as four_token,
)
from printer_v1.operator_cli import four_token_proof_zero_state_gate as gate
from printer_v1.operator_cli.pre_authorization_migration_ledger_guard import (
    PACKAGE_BINDING_FIELDS,
    inspect_authoritative_database,
)
from tests.test_v2_9_8b_four_token_proof_migration_055_evidence import (
    FourTokenProofFixture,
)
from tests.test_v2_9_8b_four_token_proof_one_shot_wrapper import _Launcher
from tests.test_v2_9_8b_four_token_proof_zero_state_gate import (
    _proof_supervision_row,
)


LIVE_PID = 991_100


class FourTokenProofProductionProcessProbeTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.tmp_path = Path(self._tmp.name)

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def _database(self, *, execution_status, process_id=LIVE_PID):
        path = self.tmp_path / "printer-process-probe.sqlite3"
        apply_migrations(path)
        connection = sqlite3.connect(path)
        try:
            _proof_supervision_row(
                connection,
                execution_status=execution_status,
                process_id=process_id,
            )
            connection.commit()
        finally:
            connection.close()
        return path

    def _fixture_for(self, db_path):
        identity = inspect_authoritative_database(db_path)
        return FourTokenProofFixture(
            database={field: identity[field] for field in PACKAGE_BINDING_FIELDS}
        )

    def _apply(self, fx, db_path, launcher, **overrides):
        arguments = {
            "authorization_file": fx.authorization_path,
            "authorization_sha256": fx.authorization_sha256,
            "operator_approved": True,
            "repository_root": fx.repo,
            "application_root": fx.root / "applications",
            "python_executable": fx.make_fake_venv_python(),
            "environ": {"PATH": "/usr/bin"},
            "process_launcher": launcher,
            # The default production zero-state gate is deliberately NOT
            # replaced: only the database target and the OS liveness predicate
            # are injected so no real Printer runtime has to exist.
            "authoritative_db_path": db_path,
            "printer_runtime_liveness_probe": lambda pid: pid == LIVE_PID,
        }
        arguments.update(overrides)
        return four_token.apply_authorization_once(**arguments)

    def test_existing_printer_runtime_blocks_before_consumption(self) -> None:
        db_path = self._database(execution_status="RUNNING")
        fx = self._fixture_for(db_path)
        try:
            launcher = _Launcher()
            with self.assertRaises(
                four_token.FourTokenProofOneShotWrapperError
            ) as caught:
                self._apply(fx, db_path, launcher)
            self.assertIn("printer_process_present", str(caught.exception))
            self.assertEqual(launcher.calls, [])
            canonical = fx.root / "applications" / fx.authorization_id
            self.assertFalse((canonical / "application-marker.json").exists())
            self.assertFalse(canonical.exists())
        finally:
            fx.close()

    def test_clean_process_state_proceeds_through_the_free_gates(self) -> None:
        db_path = self._database(execution_status="TERMINAL")
        fx = self._fixture_for(db_path)
        try:
            launcher = _Launcher()
            terminal = self._apply(fx, db_path, launcher)
            self.assertEqual(len(launcher.calls), 1)
            self.assertIs(terminal["zero_state_gate"]["zero_state_ready"], True)
            self.assertEqual(terminal["zero_state_gate"]["printer_processes"], 0)
        finally:
            fx.close()

    def test_probe_reads_durable_state_and_never_mutates(self) -> None:
        db_path = self._database(execution_status="RUNNING")
        before = db_path.stat()
        observed = gate.active_printer_runtime_processes(
            db_path, liveness_probe=lambda pid: pid == LIVE_PID
        )
        after = db_path.stat()
        self.assertEqual(observed, (LIVE_PID,))
        self.assertEqual(after.st_mtime_ns, before.st_mtime_ns)
        self.assertEqual(after.st_size, before.st_size)

    def test_terminal_supervision_is_not_an_active_runtime(self) -> None:
        db_path = self._database(execution_status="TERMINAL")
        self.assertEqual(
            gate.active_printer_runtime_processes(
                db_path, liveness_probe=lambda pid: True
            ),
            (),
        )

    def test_dead_recorded_process_is_not_an_active_runtime(self) -> None:
        db_path = self._database(execution_status="RUNNING")
        self.assertEqual(
            gate.active_printer_runtime_processes(
                db_path, liveness_probe=lambda pid: False
            ),
            (),
        )

    def test_the_wrapper_process_itself_is_never_an_active_runtime(self) -> None:
        db_path = self._database(
            execution_status="RUNNING", process_id=os.getpid()
        )
        self.assertEqual(
            gate.active_printer_runtime_processes(
                db_path, liveness_probe=lambda pid: True
            ),
            (),
        )

    def test_unreadable_process_state_fails_closed(self) -> None:
        missing = self.tmp_path / "absent.sqlite3"
        with self.assertRaises(gate.FourTokenProofZeroStateError):
            gate.active_printer_runtime_processes(missing)

        db_path = self._database(execution_status="RUNNING")

        def unreliable(_pid):
            raise OSError("process state is unavailable")

        with self.assertRaises(gate.FourTokenProofZeroStateError):
            gate.active_printer_runtime_processes(
                db_path, liveness_probe=unreliable
            )

    def test_probe_performs_no_polling_loop(self) -> None:
        db_path = self._database(execution_status="RUNNING")
        calls: list[int] = []

        def counting(pid):
            calls.append(pid)
            return True

        gate.active_printer_runtime_processes(db_path, liveness_probe=counting)
        self.assertEqual(calls, [LIVE_PID])


if __name__ == "__main__":  # pragma: no cover - direct invocation guard
    unittest.main()
