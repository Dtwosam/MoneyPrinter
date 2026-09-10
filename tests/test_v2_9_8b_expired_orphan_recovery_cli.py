"""Focused public-CLI contract for terminal-only expired-orphan recovery."""

from __future__ import annotations

from contextlib import redirect_stderr, redirect_stdout
import io
import unittest
from unittest import mock

from printer_v1.operator_cli import operational_memory_factory_command as command


INSPECT_MODE = "inspect-expired-orphan"
TERMINALIZE_MODE = "terminalize-expired-orphan"
SHA = "a" * 64


class ExpiredOrphanRecoveryCliTests(unittest.TestCase):
    def _main(self, argv: list[str]) -> int:
        stdout = io.StringIO()
        stderr = io.StringIO()
        try:
            with redirect_stdout(stdout), redirect_stderr(stderr):
                return command.main(argv)
        except SystemExit as exc:
            self.fail(f"recovery mode was rejected by argparse: {exc}")

    def test_inspect_mode_dispatches_exact_ids_without_run_authorization(self) -> None:
        result = {
            "status": "EXPIRED_ORPHAN_INSPECTION",
            "eligible": True,
            "inspection_sha256": SHA,
        }
        with mock.patch.object(
            command,
            "inspect_expired_orphan",
            create=True,
            return_value=result,
        ) as inspector:
            exit_code = self._main(
                [INSPECT_MODE, "--campaign-id", "campaign-exact", "--run-id", "run-exact"]
            )
        self.assertEqual(exit_code, 0)
        inspector.assert_called_once_with(
            command.AUTHORITATIVE_DB,
            campaign_id="campaign-exact",
            run_id="run-exact",
            artifact_root=command.ARTIFACT_ROOT,
            expected_db_path=command.AUTHORITATIVE_DB,
        )

    def test_terminalize_mode_requires_exact_sha_and_operator_approval(self) -> None:
        result = {
            "status": "RECOVERED_TERMINAL_FAILED",
            "campaign_id": "campaign-exact",
            "run_id": "run-exact",
        }
        with mock.patch.object(
            command,
            "terminalize_expired_orphan",
            create=True,
            return_value=result,
        ) as terminalizer:
            exit_code = self._main(
                [
                    TERMINALIZE_MODE,
                    "--campaign-id", "campaign-exact",
                    "--run-id", "run-exact",
                    "--inspection-sha256", SHA,
                    "--operator-approved",
                ]
            )
        self.assertEqual(exit_code, 0)
        terminalizer.assert_called_once_with(
            command.AUTHORITATIVE_DB,
            campaign_id="campaign-exact",
            run_id="run-exact",
            artifact_root=command.ARTIFACT_ROOT,
            expected_db_path=command.AUTHORITATIVE_DB,
            inspection_sha256=SHA,
            operator_approved=True,
        )

    def test_recovery_modes_never_fall_back_to_latest_identity(self) -> None:
        for mode in (INSPECT_MODE, TERMINALIZE_MODE):
            argv = [mode, "--campaign-id", "campaign-only"]
            if mode == TERMINALIZE_MODE:
                argv.extend(["--inspection-sha256", SHA, "--operator-approved"])
            target = (
                "inspect_expired_orphan"
                if mode == INSPECT_MODE
                else "terminalize_expired_orphan"
            )
            with self.subTest(mode=mode), mock.patch.object(
                command, target, create=True
            ) as owner:
                self.assertEqual(self._main(argv), 1)
                owner.assert_not_called()

    def test_terminalize_mode_does_not_use_wrapper_provenance_as_approval(self) -> None:
        with mock.patch.object(
            command,
            "terminalize_expired_orphan",
            create=True,
        ) as terminalizer:
            exit_code = self._main(
                [
                    TERMINALIZE_MODE,
                    "--campaign-id", "campaign-exact",
                    "--run-id", "run-exact",
                    "--inspection-sha256", SHA,
                ]
            )
        self.assertEqual(exit_code, 1)
        terminalizer.assert_not_called()


if __name__ == "__main__":
    unittest.main()
