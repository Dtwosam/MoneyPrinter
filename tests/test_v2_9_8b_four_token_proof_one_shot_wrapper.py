"""Focused contract for the dedicated one-use four-token proof wrapper.

Offline only. The child process is never really launched: a fake launcher stands
in for it. No authorization is created, no Printer runtime starts, no source is
called, and no authoritative database is touched.
"""

from __future__ import annotations

import json
from pathlib import Path
import unittest

from printer_v1.operator_cli import (
    four_token_proof_one_shot_wrapper as four_token,
)
from printer_v1.operator_cli.window_15m_child_terminal import (
    resolve_child_terminal_binding,
    write_child_terminal_envelope,
)
from tests.test_v2_9_8b_four_token_proof_migration_055_evidence import (
    FourTokenProofFixture,
)


class _Launcher:
    """One-attempt fake child that writes a valid child-terminal envelope."""

    def __init__(self, *, returncode: int = 0, write_terminal: bool = True) -> None:
        self.calls: list[dict] = []
        self.returncode = returncode
        self.write_terminal = write_terminal

    def __call__(self, *, command, cwd, env, stdout_path, stderr_path):
        self.calls.append({"command": list(command), "env": dict(env)})
        if self.write_terminal:
            # Use the real child-terminal owner so the envelope contract is not
            # simulated by a hand-written fixture payload.
            write_child_terminal_envelope(
                binding=resolve_child_terminal_binding(env),
                source={
                    "status": "OPERATIONAL_COMMAND_COMPLETE",
                    "campaign_id": "proof-campaign",
                    "run_id": "proof-campaign-run",
                    "cycle_id": "proof-cycle",
                    "execution_id": "proof-execution",
                    "lifecycle_started": True,
                    "cleanup_complete": True,
                    "lease_released": True,
                },
                mode=four_token.AUTHORIZED_COMMAND_MODE,
                exit_code=self.returncode,
                success=self.returncode == 0,
            )
        return {"returncode": self.returncode, "pid": 4321}


class FourTokenProofOneShotWrapperTests(unittest.TestCase):
    def setUp(self) -> None:
        self.fx = FourTokenProofFixture()
        self.python = self.fx.make_fake_venv_python()
        self.application_root = self.fx.root / "applications"
        self.zero_state_calls: list[dict] = []

    def tearDown(self) -> None:
        self.fx.close()

    def _zero_state_gate(self, **kwargs):
        marker_root = self.application_root / self.fx.authorization_id
        self.zero_state_calls.append(
            {
                "marker_exists": (marker_root / "application-marker.json").exists(),
                "kwargs": kwargs,
            }
        )
        return {"zero_state_ready": True, "blockers": []}

    def _apply(self, launcher, **overrides):
        arguments = {
            "authorization_file": self.fx.authorization_path,
            "authorization_sha256": self.fx.authorization_sha256,
            "operator_approved": True,
            "repository_root": self.fx.repo,
            "application_root": self.application_root,
            "python_executable": self.python,
            "environ": {"PATH": "/usr/bin"},
            "process_launcher": launcher,
            "migration_ledger_guard": lambda **_: None,
            "zero_state_gate": self._zero_state_gate,
        }
        arguments.update(overrides)
        return four_token.apply_authorization_once(**arguments)

    def test_dedicated_application_namespace_and_child_mode(self) -> None:
        self.assertEqual(
            four_token.APPLICATION_ROOT.name,
            "four-token-proof-one-shot-applications",
        )
        self.assertEqual(
            four_token.build_child_command("/usr/bin/python3"),
            [
                "/usr/bin/python3",
                "-m",
                "printer_v1.operator_cli.operational_memory_factory_command",
                "four-token-bounded-capacity-proof-run",
                "--operator-approved",
            ],
        )

    def test_one_marker_launches_exactly_one_child(self) -> None:
        launcher = _Launcher()
        terminal = self._apply(launcher)
        self.assertEqual(len(launcher.calls), 1)
        self.assertEqual(
            terminal["schema_version"], four_token.WRAPPER_SCHEMA_VERSION
        )
        self.assertEqual(terminal["authorization_id"], self.fx.authorization_id)
        self.assertEqual(terminal["child_exit_code"], 0)
        self.assertIs(terminal["child_start_attempted"], True)
        self.assertIs(terminal["child_terminal_valid"], True)
        self.assertIsNone(terminal["child_terminal_error"])
        for field in (
            "automatic_retries",
            "manual_reruns",
            "resumes",
            "restarts",
            "successors",
        ):
            self.assertEqual(terminal[field], 0, field)
        canonical = self.application_root / self.fx.authorization_id
        for name in (
            "application-marker.json",
            "git-provenance-manifest.json",
            "wrapper-terminal.json",
        ):
            self.assertTrue((canonical / name).is_file(), name)
        marker = json.loads(
            (canonical / "application-marker.json").read_text(encoding="utf-8")
        )
        self.assertEqual(
            marker["command"],
            {
                "mode": "four-token-bounded-capacity-proof-run",
                "operator_approved": True,
            },
        )
        self.assertEqual(marker["allowed_invocation_count"], 1)
        for flag in (
            "automatic_retry_allowed",
            "manual_rerun_allowed",
            "resume_allowed",
            "restart_allowed",
            "successor_allowed",
        ):
            self.assertIs(marker[flag], False, flag)

    def test_zero_state_gate_runs_before_the_marker_exists(self) -> None:
        launcher = _Launcher()
        self._apply(launcher)
        self.assertEqual(len(self.zero_state_calls), 1)
        self.assertIs(self.zero_state_calls[0]["marker_exists"], False)

    def test_blocked_zero_state_never_consumes_the_authorization(self) -> None:
        launcher = _Launcher()

        def blocked(**_kwargs):
            raise four_token.FourTokenProofOneShotWrapperError(
                "zero-state blocked"
            )

        with self.assertRaises(four_token.FourTokenProofOneShotWrapperError):
            self._apply(launcher, zero_state_gate=blocked)
        self.assertEqual(launcher.calls, [])
        canonical = self.application_root / self.fx.authorization_id
        self.assertFalse((canonical / "application-marker.json").exists())

    def test_second_application_is_refused_and_starts_no_second_child(self) -> None:
        first = _Launcher()
        self._apply(first)
        second = _Launcher()
        with self.assertRaises(four_token.FourTokenProofOneShotWrapperError):
            self._apply(second)
        self.assertEqual(len(first.calls), 1)
        self.assertEqual(second.calls, [])


if __name__ == "__main__":  # pragma: no cover - direct invocation guard
    unittest.main()
