"""Integrated disposable proof for the four-token wrapper/marker/terminal law.

Everything here is disposable: a temporary Git repository, a temporary external
application root, and a fake child launcher. No authorization is created, no
Printer runtime starts, no live source is called, and no authoritative database
is read or mutated.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
import unittest

from printer_v1.operator_cli import git_provenance_authorization_manifest as git_auth
from printer_v1.operator_cli import (
    four_token_proof_one_shot_wrapper as four_token,
)
from tests.test_v2_9_8b_four_token_proof_migration_055_evidence import (
    FourTokenProofFixture,
)
from tests.test_v2_9_8b_four_token_proof_one_shot_wrapper import _Launcher


class FourTokenProofIntegratedDisposableWrapperTests(unittest.TestCase):
    def _apply(self, fx, launcher, application_root, **overrides):
        arguments = {
            "authorization_file": fx.authorization_path,
            "authorization_sha256": fx.authorization_sha256,
            "operator_approved": True,
            "repository_root": fx.repo,
            "application_root": application_root,
            "python_executable": fx.make_fake_venv_python(),
            "environ": {"PATH": "/usr/bin"},
            "process_launcher": launcher,
            "migration_ledger_guard": lambda **_: None,
            "zero_state_gate": lambda **_: {"zero_state_ready": True},
        }
        arguments.update(overrides)
        return four_token.apply_authorization_once(**arguments)

    def test_one_disposable_application_proves_marker_terminal_and_non_reuse(
        self,
    ) -> None:
        fx = FourTokenProofFixture(
            historical_authorization_id="V2_9_8B_STANDARD_4H_AUTH_HISTORICAL"
        )
        try:
            application_root = fx.root / "applications"
            launcher = _Launcher()
            terminal = self._apply(fx, launcher, application_root)
            canonical = application_root / fx.authorization_id

            # One marker, one manifest, one wrapper terminal, one child.
            self.assertEqual(len(launcher.calls), 1)
            self.assertEqual(
                launcher.calls[0]["command"][-2:],
                ["four-token-bounded-capacity-proof-run", "--operator-approved"],
            )
            marker_path = canonical / "application-marker.json"
            manifest_path = canonical / "git-provenance-manifest.json"
            self.assertTrue(marker_path.is_file())
            self.assertTrue(manifest_path.is_file())

            # Wrapper artifacts live outside the repository and stay immutable.
            self.assertFalse(canonical.is_relative_to(fx.repo))
            for artifact in (marker_path, manifest_path):
                self.assertFalse(artifact.stat().st_mode & 0o222, artifact.name)

            # Exact identities are preserved end to end.
            manifest_bytes = manifest_path.read_bytes()
            self.assertEqual(
                terminal["manifest_sha256"],
                hashlib.sha256(manifest_bytes).hexdigest(),
            )
            self.assertEqual(
                terminal["marker_sha256"],
                hashlib.sha256(marker_path.read_bytes()).hexdigest(),
            )
            self.assertEqual(terminal["repository_branch"], fx.branch)
            self.assertEqual(terminal["repository_head"], fx.head)
            self.assertEqual(terminal["authorization_id"], fx.authorization_id)
            self.assertEqual(terminal["terminal_classification"], "CHILD_EXITED_ZERO")
            self.assertEqual(
                terminal["proof_policy"], four_token.exact_proof_policy()
            )

            # Historical authorization evidence is visible but non-reusable.
            manifest = json.loads(manifest_bytes.decode("utf-8"))
            historical = manifest["historical_authorization_evidence"]
            self.assertEqual(len(historical), 1)
            self.assertEqual(
                historical[0]["authorization_id"],
                "V2_9_8B_STANDARD_4H_AUTH_HISTORICAL",
            )
            self.assertEqual(
                historical[0]["evidence_class"],
                git_auth.HISTORICAL_AUTHORIZATION_EVIDENCE_CLASS,
            )
            self.assertNotIn(
                "V2_9_8B_STANDARD_4H_AUTH_HISTORICAL",
                {item["path"].split("/")[2] for item in manifest["files"]},
            )

            # The same authorization can never be applied twice.
            second = _Launcher()
            with self.assertRaises(four_token.FourTokenProofOneShotWrapperError):
                self._apply(fx, second, application_root)
            self.assertEqual(second.calls, [])
        finally:
            fx.close()

    def test_undeclared_historical_package_is_not_trusted(self) -> None:
        fx = FourTokenProofFixture(
            historical_authorization_id="V2_9_8B_STANDARD_4H_AUTH_UNDECLARED",
            declare_historical=False,
        )
        try:
            launcher = _Launcher()
            with self.assertRaises(git_auth.GitProvenanceAuthorizationError):
                self._apply(fx, launcher, fx.root / "applications")
            self.assertEqual(launcher.calls, [])
            self.assertFalse(
                (
                    fx.root
                    / "applications"
                    / fx.authorization_id
                    / "application-marker.json"
                ).exists()
            )
        finally:
            fx.close()

    def test_wrapper_never_converts_a_failed_child_into_a_pass(self) -> None:
        fx = FourTokenProofFixture()
        try:
            launcher = _Launcher(returncode=3)
            terminal = self._apply(fx, launcher, fx.root / "applications")
            self.assertEqual(terminal["child_exit_code"], 3)
            self.assertEqual(
                terminal["terminal_classification"], "CHILD_EXITED_NONZERO"
            )
            envelope = terminal["child_terminal_envelope"]
            self.assertIsNotNone(envelope)
            self.assertIs(envelope["success"], False)
            self.assertNotIn("pass", json.dumps(terminal).lower().split('"verdict":'))
            # The authorization is still consumed once, with no successor.
            for field in (
                "automatic_retries",
                "manual_reruns",
                "resumes",
                "restarts",
                "successors",
            ):
                self.assertEqual(terminal[field], 0, field)
        finally:
            fx.close()


if __name__ == "__main__":  # pragma: no cover - direct invocation guard
    unittest.main()
