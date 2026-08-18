"""Focused contract for the one-use operational four-token 4/2/2 wrapper.

Offline only. The child process is never really launched: a fake launcher stands
in for it. No authorization is created, no Printer runtime starts, no source is
called, and no authoritative database is touched.
"""

from __future__ import annotations

import contextlib
from datetime import datetime, timedelta, timezone
import hashlib
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest import mock

from printer_v1.operator_cli import git_provenance_authorization_manifest as git_auth
from printer_v1.operator_cli import (
    four_token_standard_four_hour_one_shot_wrapper as operational,
)
from printer_v1.operator_cli.window_15m_child_terminal import (
    resolve_child_terminal_binding,
    write_child_terminal_envelope,
)


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _synthetic_profile(repo: Path, package_dir: Path):
    """Fixture-scoped profile declaring only the synthetic package identity.

    The disposable package never claims a real production migration identity: it
    declares exactly its own synthetic inventory, so the immutable completeness
    law is exercised rather than bypassed.
    """
    production = git_auth.FOUR_TOKEN_STANDARD_FOUR_HOUR_AUTHORIZATION_PROFILE
    files = [
        {
            "path": item.relative_to(repo).as_posix(),
            "sha256": _sha(item),
            "size": item.stat().st_size,
        }
        for item in sorted(package_dir.rglob("*"))
        if item.is_file() and not item.is_symlink()
    ]
    digest = git_auth.compute_historical_migration_inventory_sha256(
        package_root=git_auth.MIGRATION_PACKAGE_ROOT,
        execution_id=git_auth.FOUR_TOKEN_HISTORICAL_MIGRATION_EXECUTION_ID,
        evidence_class=git_auth.HISTORICAL_MIGRATION_EVIDENCE_CLASS,
        files=files,
    )
    return git_auth.GitAuthorizationProfile(
        command_mode=production.command_mode,
        authorization_package_root=production.authorization_package_root,
        authorization_package_kind=production.authorization_package_kind,
        manifest_schema_version=production.manifest_schema_version,
        historical_authorization_package_roots=(
            production.historical_authorization_package_roots
        ),
        migration_package_root=production.migration_package_root,
        migration_package_kind=production.migration_package_kind,
        historical_migration_packages=(
            git_auth.HistoricalMigrationPackage(
                package_root=git_auth.MIGRATION_PACKAGE_ROOT,
                execution_id=git_auth.FOUR_TOKEN_HISTORICAL_MIGRATION_EXECUTION_ID,
                evidence_class=git_auth.HISTORICAL_MIGRATION_EVIDENCE_CLASS,
                expected_file_count=len(files) or 1,
                expected_inventory_sha256=digest,
            ),
        ),
    )


@contextlib.contextmanager
def _patched_profile(profile):
    with mock.patch.object(
        git_auth,
        "FOUR_TOKEN_STANDARD_FOUR_HOUR_AUTHORIZATION_PROFILE",
        profile,
    ), mock.patch.object(
        operational,
        "FOUR_TOKEN_STANDARD_FOUR_HOUR_AUTHORIZATION_PROFILE",
        profile,
    ):
        yield profile


class OperationalFixture:
    """Disposable repository carrying one exact operational 4/2/2 package."""

    authorization_id = "V2_9_8B_FOUR_TOKEN_STD4H_AUTH_TESTONLY"
    migration_id = "MIGRATION_058_TESTONLY"

    def __init__(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name).resolve()
        self.repo = self.root / "repo"
        self.repo.mkdir()
        self._git("init")
        self._git("config", "user.email", "tests@example.invalid")
        self._git("config", "user.name", "Four Token Operational Tests")
        (self.repo / ".gitignore").write_text("*.sqlite3\n.venv/\n", encoding="utf-8")
        (self.repo / "tracked.txt").write_text("clean\n", encoding="utf-8")
        self._git("add", ".")
        self._git("commit", "-m", "baseline")
        self.branch = self._git("rev-parse", "--abbrev-ref", "HEAD").stdout.strip()
        self.head = self._git("rev-parse", "HEAD").stdout.strip()

        profile = git_auth.FOUR_TOKEN_STANDARD_FOUR_HOUR_AUTHORIZATION_PROFILE
        self.migration_root = (
            self.repo / profile.migration_package_root / self.migration_id
        )
        self.authorization_root = (
            self.repo / profile.authorization_package_root / self.authorization_id
        )
        self.migration_root.mkdir(parents=True)
        self.authorization_root.mkdir(parents=True)
        (self.migration_root / "migration_058_application_result.json").write_text(
            json.dumps({"migration": self.migration_id}) + "\n", encoding="utf-8"
        )
        self.historical_migration_root = (
            self.repo
            / git_auth.MIGRATION_PACKAGE_ROOT
            / git_auth.FOUR_TOKEN_HISTORICAL_MIGRATION_EXECUTION_ID
        )
        self.historical_migration_root.mkdir(parents=True)
        (self.historical_migration_root / "post_migration_proof.json").write_text(
            json.dumps({"migration_count": 50}) + "\n", encoding="utf-8"
        )

        self.authorization_path = self.authorization_root / "final_authorization.json"
        now = datetime.now(timezone.utc)
        document = operational.fixture_authorization_document(
            branch=self.branch,
            head=self.head,
            database={
                "path": "/tmp/printer.sqlite3",
                "sha256": "c" * 64,
                "size": 4096,
                "inode": 3,
                "mtime_ns": 5,
                "migration_count": 58,
                "migration_head": "058_direct_pump_migration_cursor.sql",
            },
            authorization_id=self.authorization_id,
            migration_execution_id=self.migration_id,
            authorized_at=now.isoformat(),
            expires_at=(now + timedelta(hours=12)).isoformat(),
        )
        self.document = document
        self.authorization_path.write_text(
            json.dumps(document, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )
        self.authorization_sha256 = _sha(self.authorization_path)

    def _git(self, *args: str):
        return subprocess.run(
            ["git", *args], cwd=self.repo, capture_output=True, text=True, check=True
        )

    @property
    def profile(self):
        return _synthetic_profile(self.repo, self.historical_migration_root)

    def make_fake_venv_python(self) -> Path:
        venv = self.repo / ".venv"
        bindir = venv / ("Scripts" if os.name == "nt" else "bin")
        bindir.mkdir(parents=True, exist_ok=True)
        (venv / "pyvenv.cfg").write_text("home = fixture\n", encoding="utf-8")
        name = "python.exe" if os.name == "nt" else "python"
        executable = bindir / name
        executable.write_text("fixture interpreter\n", encoding="utf-8")
        executable.chmod(0o755)
        return executable

    def close(self) -> None:
        self.tmp.cleanup()


class _Launcher:
    """One-attempt fake child that writes a valid child-terminal envelope."""

    def __init__(self, *, returncode: int = 0) -> None:
        self.calls: list[dict] = []
        self.returncode = returncode

    def __call__(self, *, command, cwd, env, stdout_path, stderr_path):
        self.calls.append({"command": list(command), "env": dict(env)})
        write_child_terminal_envelope(
            binding=resolve_child_terminal_binding(env),
            source={
                "status": "OPERATIONAL_COMMAND_COMPLETE",
                "campaign_id": "operational-campaign",
                "run_id": "operational-campaign-run",
                "cycle_id": "operational-cycle",
                "execution_id": "operational-execution",
                "lifecycle_started": True,
                "cleanup_complete": True,
                "lease_released": True,
            },
            mode=operational.AUTHORIZED_COMMAND_MODE,
            exit_code=self.returncode,
            success=self.returncode == 0,
        )
        return {"returncode": self.returncode, "pid": 5432}


class OperationalOneShotWrapperTests(unittest.TestCase):
    def setUp(self) -> None:
        self.fx = OperationalFixture()
        self.python = self.fx.make_fake_venv_python()
        self.application_root = self.fx.root / "applications"
        self.zero_state_calls: list[dict] = []

    def tearDown(self) -> None:
        self.fx.close()

    def _zero_state_gate(self, **kwargs):
        marker_root = self.application_root / self.fx.authorization_id
        self.zero_state_calls.append(
            {"marker_exists": (marker_root / "application-marker.json").exists()}
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
        with _patched_profile(self.fx.profile):
            return operational.apply_authorization_once(**arguments)

    # --- identity -----------------------------------------------------------

    def test_authorized_mode_and_schema_identity(self) -> None:
        self.assertEqual(
            operational.AUTHORIZED_COMMAND_MODE,
            "four-token-standard-four-hour-run",
        )
        self.assertEqual(
            operational.FINAL_AUTHORIZATION_SCHEMA_VERSION,
            "PRINTER_V1_FOUR_TOKEN_STANDARD_4H_FINAL_AUTHORIZATION_V1",
        )
        self.assertEqual(
            operational.WRAPPER_SCHEMA_VERSION,
            "PRINTER_V1_FOUR_TOKEN_STANDARD_4H_ONE_SHOT_WRAPPER_V1",
        )
        self.assertEqual(
            operational.APPLICATION_ROOT,
            Path.home()
            / "PrinterOperations"
            / "v2-9-8"
            / "four-token-standard-four-hour-one-shot-applications",
        )

    def test_child_command_is_the_exact_operational_child(self) -> None:
        self.assertEqual(
            operational.build_child_command("/x/python"),
            [
                "/x/python",
                "-m",
                "printer_v1.operator_cli.operational_memory_factory_command",
                "four-token-standard-four-hour-run",
                "--operator-approved",
            ],
        )

    # --- one-use law --------------------------------------------------------

    def test_one_application_launches_exactly_one_child(self) -> None:
        launcher = _Launcher()
        terminal = self._apply(launcher)
        self.assertEqual(len(launcher.calls), 1)
        self.assertEqual(terminal["child_exit_code"], 0)
        self.assertEqual(terminal["automatic_retries"], 0)
        self.assertEqual(terminal["manual_reruns"], 0)
        self.assertEqual(terminal["resumes"], 0)
        self.assertEqual(terminal["restarts"], 0)
        self.assertEqual(terminal["successors"], 0)
        self.assertIs(terminal["parent_environment_mutated"], False)
        marker = (
            self.application_root
            / self.fx.authorization_id
            / "application-marker.json"
        )
        payload = json.loads(marker.read_text(encoding="utf-8"))
        self.assertEqual(payload["allowed_invocation_count"], 1)
        for flag in (
            "automatic_retry_allowed",
            "manual_rerun_allowed",
            "resume_allowed",
            "restart_allowed",
            "successor_allowed",
        ):
            self.assertIs(payload[flag], False, flag)
        self.assertEqual(
            payload["command"],
            {
                "mode": "four-token-standard-four-hour-run",
                "operator_approved": True,
            },
        )

    def test_second_application_of_the_same_authorization_is_refused(self) -> None:
        first = _Launcher()
        self._apply(first)
        second = _Launcher()
        with self.assertRaises(operational.FourTokenStandardFourHourOneShotWrapperError):
            self._apply(second)
        self.assertEqual(len(second.calls), 0)

    def test_operator_approval_is_required(self) -> None:
        launcher = _Launcher()
        with self.assertRaises(operational.FourTokenStandardFourHourOneShotWrapperError):
            self._apply(launcher, operator_approved=False)
        self.assertEqual(len(launcher.calls), 0)

    def test_authorization_hash_mismatch_fails_closed(self) -> None:
        launcher = _Launcher()
        with self.assertRaises(operational.FourTokenStandardFourHourOneShotWrapperError):
            self._apply(launcher, authorization_sha256="d" * 64)
        self.assertEqual(len(launcher.calls), 0)

    def test_blocked_zero_state_leaves_authorization_unconsumed(self) -> None:
        def blocked(**_kwargs):
            raise operational.FourTokenStandardFourHourOneShotWrapperError(
                "authorization blocked before consumption: active campaign"
            )

        launcher = _Launcher()
        with self.assertRaises(operational.FourTokenStandardFourHourOneShotWrapperError):
            self._apply(launcher, zero_state_gate=blocked)
        self.assertEqual(len(launcher.calls), 0)
        self.assertFalse(
            (
                self.application_root
                / self.fx.authorization_id
                / "application-marker.json"
            ).exists()
        )

    def test_zero_state_gate_runs_before_the_marker_exists(self) -> None:
        self._apply(_Launcher())
        self.assertEqual(len(self.zero_state_calls), 1)
        self.assertIs(self.zero_state_calls[0]["marker_exists"], False)

    # --- document validation ------------------------------------------------

    def test_document_binds_the_exact_operational_policy(self) -> None:
        from printer_v1.operator_cli import four_token_operational_composition

        validated = operational.validate_four_token_standard_four_hour_authorization_document(
            self.fx.document
        )
        self.assertEqual(
            validated["operational_policy"],
            four_token_operational_composition.exact_operational_policy(),
        )
        self.assertEqual(
            validated["authorized_command"],
            {
                "mode": "four-token-standard-four-hour-run",
                "operator_approved": True,
            },
        )
        self.assertEqual(
            validated["one_shot_policy"],
            {
                "allowed_invocation_count": 1,
                "automatic_retry_allowed": False,
                "manual_rerun_allowed": False,
                "resume_allowed": False,
                "restart_allowed": False,
                "successor_allowed": False,
            },
        )

    def test_wrong_command_mode_fails_closed(self) -> None:
        document = json.loads(json.dumps(self.fx.document))
        document["authorized_command"]["mode"] = "standard-four-hour-run"
        with self.assertRaises(operational.FourTokenStandardFourHourOneShotWrapperError):
            operational.validate_four_token_standard_four_hour_authorization_document(
                document
            )

    def test_proof_authorization_cannot_authorize_the_operational_mode(self) -> None:
        from printer_v1.operator_cli import four_token_proof_one_shot_wrapper as proof

        proof_document = proof.fixture_authorization_document(
            branch=self.fx.branch,
            head=self.fx.head,
            database={
                "path": "/tmp/printer.sqlite3",
                "sha256": "c" * 64,
                "size": 4096,
                "inode": 3,
                "mtime_ns": 5,
                "migration_count": 58,
                "migration_head": "058_direct_pump_migration_cursor.sql",
            },
        )
        with self.assertRaises(operational.FourTokenStandardFourHourOneShotWrapperError):
            operational.validate_four_token_standard_four_hour_authorization_document(
                proof_document
            )

    def test_widened_policy_fails_closed(self) -> None:
        for key, value in (
            ("configured_through_4h_tokens", 6),
            ("configured_active_cycles", 3),
            ("total_cycle_admission_ceiling", 3),
            ("tokens_per_cycle", 3),
            ("automatic_retries", 1),
            ("endpoint_rotation", True),
            ("long_windows_activated", True),
        ):
            with self.subTest(key=key):
                document = json.loads(json.dumps(self.fx.document))
                document["operational_policy"][key] = value
                with self.assertRaises(
                    operational.FourTokenStandardFourHourOneShotWrapperError
                ):
                    operational.validate_four_token_standard_four_hour_authorization_document(
                        document
                    )

    def test_bound_head_is_enforced(self) -> None:
        launcher = _Launcher()
        terminal = self._apply(launcher)
        self.assertEqual(terminal["repository_head"], self.fx.head)
        self.assertEqual(terminal["repository_branch"], self.fx.branch)

    def test_head_drift_fails_closed(self) -> None:
        (self.fx.repo / "drift.txt").write_text("drift\n", encoding="utf-8")
        self.fx._git("add", "drift.txt")
        self.fx._git("commit", "-m", "drift")
        launcher = _Launcher()
        with self.assertRaises(Exception):
            self._apply(launcher)
        self.assertEqual(len(launcher.calls), 0)


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
