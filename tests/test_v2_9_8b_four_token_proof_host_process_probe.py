"""Focused contract for independent four-token host-process coverage.

Offline only. No Printer runtime is ever started: the lowest-level host process
inventory seam is injected so a real current operational command line can be
modelled without a live child. No authorization is created, no source is called,
and no authoritative database is mutated.
"""

from __future__ import annotations

import os
import sqlite3
import subprocess
import tempfile
import unittest
from pathlib import Path

from printer_v1.db import apply_migrations
from printer_v1.operator_cli import four_token_proof_zero_state_gate as gate
from printer_v1.operator_cli import (
    four_token_proof_one_shot_wrapper as four_token,
)
from printer_v1.operator_cli import operational_campaign_recovery as recovery
from printer_v1.operator_cli.pre_authorization_migration_ledger_guard import (
    PACKAGE_BINDING_FIELDS,
    inspect_authoritative_database,
)
from tests.test_v2_9_8b_four_token_proof_migration_055_evidence import (
    FourTokenProofFixture,
)
from tests.test_v2_9_8b_four_token_proof_one_shot_wrapper import _Launcher


PYTHON = "/Users/operator/Developer/MoneyPrinter/.venv/bin/python"
MODULE = "printer_v1.operator_cli.operational_memory_factory_command"

ORDINARY_CHILD = (
    4_101,
    f"{PYTHON} -m {MODULE} run --operator-approved",
)
STANDARD_FOUR_HOUR_CHILD = (
    4_102,
    f"{PYTHON} -m {MODULE} standard-four-hour-run --operator-approved",
)
FOUR_TOKEN_CHILD = (
    4_103,
    f"{PYTHON} -m {MODULE} four-token-bounded-capacity-proof-run "
    "--operator-approved",
)
UNRELATED_PROCESSES = (
    (5_201, "/usr/bin/python3 -m pytest tests/test_four_token_proof.py"),
    (5_202, "/usr/bin/python3 -m http.server 8000"),
    (5_203, "/bin/zsh -l"),
    # A read-only auxiliary mode of the same command is not a Printer runtime.
    (5_204, f"{PYTHON} -m {MODULE} status"),
    (5_205, "grep -rn operational_memory_factory_command src/"),
)


class FourTokenProofHostProcessProbeTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.tmp_path = Path(self._tmp.name)

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def _quiescent_database(self):
        """A post-055 database with no proof-supervision row at all."""
        path = self.tmp_path / "host-process-probe.sqlite3"
        apply_migrations(path)
        connection = sqlite3.connect(path)
        try:
            self.assertEqual(
                connection.execute(
                    "SELECT COUNT(*) FROM printer_proof_run_supervision"
                ).fetchone()[0],
                0,
            )
        finally:
            connection.close()
        return path

    def _probe(self, db_path, inventory):
        return gate.active_printer_runtime_processes(
            db_path, host_process_inventory=lambda: tuple(inventory)
        )

    def test_durable_pid_authority_alone_misses_a_live_operational_child(
        self,
    ) -> None:
        """The exact coverage gap: no proof-supervision row, live child.

        Proof-supervision PIDs are already rejected by the durable zero-state
        domain, so a probe reading only that ledger adds no host coverage. A
        current wrapper-bound operational child owns no proof-supervision row,
        and must still be detected.
        """
        db_path = self._quiescent_database()
        self.assertEqual(
            gate.active_printer_runtime_processes(
                db_path, liveness_probe=lambda _pid: True
            ),
            (),
        )
        self.assertEqual(
            self._probe(db_path, (*UNRELATED_PROCESSES, ORDINARY_CHILD)),
            (ORDINARY_CHILD[0],),
        )

    def test_live_operational_children_block_without_proof_supervision(
        self,
    ) -> None:
        db_path = self._quiescent_database()
        for label, child in (
            ("ordinary", ORDINARY_CHILD),
            ("standard-four-hour", STANDARD_FOUR_HOUR_CHILD),
            ("four-token", FOUR_TOKEN_CHILD),
        ):
            with self.subTest(child=label):
                observed = self._probe(
                    db_path, (*UNRELATED_PROCESSES, child)
                )
                self.assertEqual(observed, (child[0],))

    def test_unrelated_processes_do_not_false_positive(self) -> None:
        db_path = self._quiescent_database()
        self.assertEqual(self._probe(db_path, UNRELATED_PROCESSES), ())

    def test_current_wrapper_context_is_excluded(self) -> None:
        db_path = self._quiescent_database()
        inventory = (
            (os.getpid(), f"{PYTHON} -m {MODULE} run --operator-approved"),
            (os.getppid(), f"{PYTHON} -m {MODULE} run --operator-approved"),
        )
        self.assertEqual(self._probe(db_path, inventory), ())

    def test_host_inspection_failure_fails_closed(self) -> None:
        db_path = self._quiescent_database()

        def unavailable():
            raise recovery.OperationalCampaignRecoveryError(
                "live Printer process state could not be verified"
            )

        with self.assertRaises(gate.FourTokenProofZeroStateError) as caught:
            gate.active_printer_runtime_processes(
                db_path, host_process_inventory=unavailable
            )
        self.assertIn("printer_process_state_unavailable", str(caught.exception))

    def test_host_inspection_is_one_bounded_pass(self) -> None:
        db_path = self._quiescent_database()
        calls: list[int] = []

        def counting():
            calls.append(1)
            return UNRELATED_PROCESSES

        gate.active_printer_runtime_processes(
            db_path, host_process_inventory=counting
        )
        self.assertEqual(len(calls), 1)


class FourTokenProofHostProcessWrapperTests(unittest.TestCase):
    """The production default gate must carry the host check end to end."""

    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.tmp_path = Path(self._tmp.name)
        self.db_path = self.tmp_path / "wrapper-host-probe.sqlite3"
        apply_migrations(self.db_path)

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def _fixture(self):
        identity = inspect_authoritative_database(self.db_path)
        return FourTokenProofFixture(
            database={field: identity[field] for field in PACKAGE_BINDING_FIELDS}
        )

    def _apply(self, fx, launcher, inventory):
        return four_token.apply_authorization_once(
            authorization_file=fx.authorization_path,
            authorization_sha256=fx.authorization_sha256,
            operator_approved=True,
            repository_root=fx.repo,
            application_root=fx.root / "applications",
            python_executable=fx.make_fake_venv_python(),
            environ={"PATH": "/usr/bin"},
            process_launcher=launcher,
            # The real default zero-state gate is exercised; only the database
            # target and the lowest-level host inventory seam are injected.
            authoritative_db_path=self.db_path,
            printer_host_process_inventory=lambda: tuple(inventory),
        )

    def test_live_operational_child_blocks_before_marker_creation(self) -> None:
        fx = self._fixture()
        try:
            launcher = _Launcher()
            with self.assertRaises(
                four_token.FourTokenProofOneShotWrapperError
            ) as caught:
                self._apply(fx, launcher, (*UNRELATED_PROCESSES, FOUR_TOKEN_CHILD))
            self.assertIn("printer_process_present", str(caught.exception))
            self.assertEqual(launcher.calls, [])
            canonical = fx.root / "applications" / fx.authorization_id
            self.assertFalse(canonical.exists())
        finally:
            fx.close()

    def test_clean_host_state_proceeds(self) -> None:
        fx = self._fixture()
        try:
            launcher = _Launcher()
            terminal = self._apply(fx, launcher, UNRELATED_PROCESSES)
            self.assertEqual(len(launcher.calls), 1)
            self.assertEqual(terminal["zero_state_gate"]["printer_processes"], 0)
        finally:
            fx.close()


class HostProcessInventoryOwnerTests(unittest.TestCase):
    """The reused platform owner stays bounded, read-only, and fail-closed."""

    def test_posix_inventory_parses_pid_and_command_line(self) -> None:
        captured: list[dict] = []

        def runner(command, **kwargs):
            captured.append({"command": list(command), "kwargs": dict(kwargs)})
            return subprocess.CompletedProcess(
                command,
                0,
                stdout=(
                    "  4101 /usr/bin/python3 -m printer_v1.x run\n"
                    "\n"
                    "  5201 /bin/zsh -l\n"
                ),
                stderr="",
            )

        inventory = recovery.host_process_inventory(runner=runner)
        self.assertEqual(
            inventory,
            (
                (4101, "/usr/bin/python3 -m printer_v1.x run"),
                (5201, "/bin/zsh -l"),
            ),
        )
        self.assertEqual(len(captured), 1)
        self.assertLessEqual(captured[0]["kwargs"]["timeout"], 5.0)
        self.assertIs(captured[0]["kwargs"]["check"], False)
        self.assertIs(captured[0]["kwargs"]["shell"], False)

    def test_inventory_fails_closed(self) -> None:
        def failing(command, **_kwargs):
            return subprocess.CompletedProcess(command, 1, stdout="", stderr="")

        with self.assertRaises(recovery.OperationalCampaignRecoveryError):
            recovery.host_process_inventory(runner=failing)

        def raising(command, **_kwargs):
            raise OSError("ps is unavailable")

        with self.assertRaises(recovery.OperationalCampaignRecoveryError):
            recovery.host_process_inventory(runner=raising)

    def test_existing_recovery_probe_behavior_is_unchanged(self) -> None:
        def runner(command, **_kwargs):
            return subprocess.CompletedProcess(
                command,
                0,
                stdout=(
                    f"  {os.getpid()} python -m {MODULE} run\n"
                    "  7001 /usr/bin/python3 -m http.server\n"
                ),
                stderr="",
            )

        # Own PID is skipped and unrelated processes do not match.
        self.assertIs(
            recovery._default_live_process_probe("exec-1", runner=runner), False
        )

        def matching(command, **_kwargs):
            return subprocess.CompletedProcess(
                command,
                0,
                stdout=f"  7002 python -m {MODULE} run\n",
                stderr="",
            )

        self.assertIs(
            recovery._default_live_process_probe("exec-1", runner=matching), True
        )

        def execution_id_match(command, **_kwargs):
            return subprocess.CompletedProcess(
                command, 0, stdout="  7003 something exec-1 else\n", stderr=""
            )

        self.assertIs(
            recovery._default_live_process_probe("exec-1", runner=execution_id_match),
            True,
        )


if __name__ == "__main__":  # pragma: no cover - direct invocation guard
    unittest.main()
