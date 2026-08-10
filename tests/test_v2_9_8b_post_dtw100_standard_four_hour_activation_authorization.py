from __future__ import annotations

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
from printer_v1.operator_cli import operational_memory_factory_command as command
from printer_v1.operator_cli import standard_four_hour_one_shot_wrapper as wrapper
from printer_v1.operator_cli import window_15m_child_terminal as child_terminal


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


class StandardAuthorizationFixture:
    def __init__(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name).resolve()
        self.repo = self.root / "repo"
        self.external = self.root / "external"
        self.repo.mkdir()
        self.external.mkdir()
        self._git("init")
        self._git("config", "user.email", "tests@example.invalid")
        self._git("config", "user.name", "Standard 4h Tests")
        (self.repo / ".gitignore").write_text("*.sqlite3\n.venv/\n", encoding="utf-8")
        (self.repo / "tracked.txt").write_text("clean\n", encoding="utf-8")
        self._git("add", ".")
        self._git("commit", "-m", "baseline")
        self.branch = self._git("rev-parse", "--abbrev-ref", "HEAD").stdout.strip()
        self.head = self._git("rev-parse", "HEAD").stdout.strip()

        self.authorization_id = "V2_9_8B_STANDARD_4H_AUTH_TESTONLY"
        self.migration_id = "V2_9_8B_AUTHORITATIVE_MIG050_TESTONLY"
        self.migration_root = (
            self.repo / git_auth.MIGRATION_PACKAGE_ROOT / self.migration_id
        )
        self.authorization_root = (
            self.repo
            / git_auth.STANDARD_FOUR_HOUR_AUTHORIZATION_PROFILE.authorization_package_root
            / self.authorization_id
        )
        self.migration_root.mkdir(parents=True)
        self.authorization_root.mkdir(parents=True)
        (self.migration_root / "migration.json").write_text(
            json.dumps({"migration": self.migration_id}) + "\n", encoding="utf-8"
        )
        self.authorization_path = self.authorization_root / "final_authorization.json"
        now = datetime.now(timezone.utc)
        document = wrapper.fixture_authorization_document(
            branch=self.branch,
            head=self.head,
            database={
                "path": "/tmp/printer.sqlite3",
                "sha256": "b" * 64,
                "size": 1,
                "inode": 1,
                "mtime_ns": 1,
                "migration_count": 54,
                "migration_head": "054_pre_lifecycle_discovery_refresh_wait.sql",
            },
            authorization_id=self.authorization_id,
            migration_execution_id=self.migration_id,
            authorized_at=now.isoformat(),
            expires_at=(now + timedelta(hours=12)).isoformat(),
            validity_seconds=43_200,
            prior_authorizations_non_reusable=(),
        )
        self.authorization_path.write_text(
            json.dumps(document, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )
        self.authorization_sha256 = _sha(self.authorization_path)

    def _git(self, *args: str):
        return subprocess.run(
            ["git", *args], cwd=self.repo, capture_output=True, text=True, check=True
        )

    def build_manifest(self):
        payload, data = wrapper.build_manifest_bytes(
            repository_root=self.repo,
            authorization_file=self.authorization_path,
            authorization_sha256=self.authorization_sha256,
            created_at=datetime.now(timezone.utc).isoformat(),
        )
        path = self.external / "manifest.json"
        path.write_bytes(data)
        return payload, path, hashlib.sha256(data).hexdigest()

    def make_fake_venv_python(self) -> Path:
        venv = self.repo / ".venv"
        bindir = venv / ("Scripts" if os.name == "nt" else "bin")
        bindir.mkdir(parents=True)
        (venv / "pyvenv.cfg").write_text("home = fixture\n", encoding="utf-8")
        python_name = "python.exe" if os.name == "nt" else "python"
        executable = bindir / python_name
        executable.write_text("fixture interpreter\n", encoding="utf-8")
        executable.chmod(0o755)
        return executable

    def close(self) -> None:
        self.tmp.cleanup()


class StandardFourHourActivationAuthorizationTests(unittest.TestCase):
    def test_standard_manifest_and_marker_validate_only_under_standard_profile(self) -> None:
        fx = StandardAuthorizationFixture()
        try:
            manifest, manifest_path, manifest_sha = fx.build_manifest()
            profile = git_auth.STANDARD_FOUR_HOUR_AUTHORIZATION_PROFILE
            self.assertEqual(manifest["schema_version"], profile.manifest_schema_version)
            self.assertEqual(
                manifest["authorized_command"],
                {"mode": "standard-four-hour-run", "operator_approved": True},
            )
            kinds = {item["package_kind"] for item in manifest["files"]}
            self.assertEqual(
                kinds,
                {git_auth.MIGRATION_PACKAGE_KIND, profile.authorization_package_kind},
            )
            prepared = git_auth.validate_git_provenance_manifest_pre_marker(
                repository_root=fx.repo,
                manifest_path=str(manifest_path.resolve()),
                manifest_sha256=manifest_sha,
                profile=profile,
            )
            with self.assertRaises(git_auth.GitProvenanceAuthorizationError):
                git_auth.validate_git_provenance_manifest_pre_marker(
                    repository_root=fx.repo,
                    manifest_path=str(manifest_path.resolve()),
                    manifest_sha256=manifest_sha,
                )

            marker, marker_bytes = wrapper.build_marker_bytes(
                prepared, consumed_at=datetime.now(timezone.utc).isoformat()
            )
            self.assertEqual(marker["command"]["mode"], "standard-four-hour-run")
            self.assertEqual(marker["allowed_invocation_count"], 1)
            self.assertFalse(marker["automatic_retry_allowed"])
            self.assertFalse(marker["manual_rerun_allowed"])
            self.assertFalse(marker["resume_allowed"])
            self.assertFalse(marker["restart_allowed"])
            self.assertFalse(marker["successor_allowed"])
            marker_path = fx.external / "marker.json"
            marker_path.write_bytes(marker_bytes)
            marker_sha = hashlib.sha256(marker_bytes).hexdigest()
            validated = git_auth.validate_git_provenance_authorization(
                repository_root=fx.repo,
                manifest_path=str(manifest_path.resolve()),
                manifest_sha256=manifest_sha,
                marker_path=str(marker_path.resolve()),
                marker_sha256=marker_sha,
                profile=profile,
            )
            self.assertEqual(validated.authorization_id, fx.authorization_id)
            with self.assertRaises(git_auth.GitProvenanceAuthorizationError):
                git_auth.validate_git_provenance_authorization(
                    repository_root=fx.repo,
                    manifest_path=str(manifest_path.resolve()),
                    manifest_sha256=manifest_sha,
                    marker_path=str(marker_path.resolve()),
                    marker_sha256=marker_sha,
                )
        finally:
            fx.close()

    def test_standard_authorization_document_is_temporal_one_use_and_exact_scope(self) -> None:
        now = datetime.now(timezone.utc)
        document = wrapper.fixture_authorization_document(
            branch="agent/test",
            head="a" * 40,
            database={
                "path": "/tmp/printer.sqlite3",
                "sha256": "b" * 64,
                "size": 1,
                "inode": 1,
                "mtime_ns": 1,
                "migration_count": 54,
                "migration_head": "054_pre_lifecycle_discovery_refresh_wait.sql",
            },
            authorization_id="STANDARD_4H_TEST",
            migration_execution_id="MIG050_TEST",
            authorized_at=now.isoformat(),
            expires_at=(now + timedelta(hours=12)).isoformat(),
            validity_seconds=43_200,
            prior_authorizations_non_reusable=("OLD_AUTH",),
        )
        validated = wrapper.validate_standard_four_hour_authorization_document(document)
        self.assertEqual(validated["migration_execution_id"], "MIG050_TEST")
        self.assertEqual(validated["prior_authorizations_non_reusable"], ["OLD_AUTH"])
        self.assertTrue(validated["verdict"].endswith("_PASS"))
        self.assertEqual(validated["one_shot_policy"]["allowed_invocation_count"], 1)
        self.assertEqual(validated["campaign_policy"]["locked_windows"], ["WINDOW_12H", "WINDOW_24H"])

    def test_command_manifest_resolver_routes_standard_mode_to_standard_profile(self) -> None:
        env = {
            command.GIT_PROVENANCE_MANIFEST_ENV_VARS[0]: "/tmp/manifest.json",
            command.GIT_PROVENANCE_MANIFEST_ENV_VARS[1]: "a" * 64,
            command.GIT_PROVENANCE_MANIFEST_ENV_VARS[2]: "/tmp/marker.json",
            command.GIT_PROVENANCE_MANIFEST_ENV_VARS[3]: "b" * 64,
        }
        sentinel = object()
        with tempfile.TemporaryDirectory() as tmp, mock.patch.object(
            command, "validate_git_provenance_authorization", return_value=sentinel
        ) as validator:
            result = command._resolve_git_provenance_authorization(
                command.STANDARD_FOUR_HOUR_MODE,
                environ=env,
                repository_root=tmp,
            )
        self.assertIs(result, sentinel)
        self.assertEqual(
            validator.call_args.kwargs["profile"],
            git_auth.STANDARD_FOUR_HOUR_AUTHORIZATION_PROFILE,
        )

    def test_ordinary_manifest_resolver_keeps_ordinary_profile(self) -> None:
        env = {
            command.GIT_PROVENANCE_MANIFEST_ENV_VARS[0]: "/tmp/manifest.json",
            command.GIT_PROVENANCE_MANIFEST_ENV_VARS[1]: "a" * 64,
            command.GIT_PROVENANCE_MANIFEST_ENV_VARS[2]: "/tmp/marker.json",
            command.GIT_PROVENANCE_MANIFEST_ENV_VARS[3]: "b" * 64,
        }
        sentinel = object()
        with tempfile.TemporaryDirectory() as tmp, mock.patch.object(
            command, "validate_git_provenance_authorization", return_value=sentinel
        ) as validator:
            result = command._resolve_git_provenance_authorization(
                "run", environ=env, repository_root=tmp
            )
        self.assertIs(result, sentinel)
        self.assertIsNone(validator.call_args.kwargs.get("profile"))

    def test_standard_child_terminal_round_trip_is_mode_and_schema_bound(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp).resolve()
            marker_path = root / child_terminal.APPLICATION_MARKER_FILENAME
            marker_path.write_text(
                json.dumps({"authorization_id": "STANDARD_4H_TEST"}) + "\n",
                encoding="utf-8",
            )
            marker_sha = _sha(marker_path)
            terminal_path = root / child_terminal.CHILD_TERMINAL_FILENAME
            binding = child_terminal.resolve_child_terminal_binding(
                {
                    child_terminal.CHILD_TERMINAL_ENV_VAR: str(terminal_path),
                    child_terminal.APPLICATION_MARKER_ENV_VAR: str(marker_path),
                    child_terminal.APPLICATION_MARKER_SHA256_ENV_VAR: marker_sha,
                }
            )
            payload = child_terminal.write_child_terminal_envelope(
                binding=binding,
                source={"status": "OPERATIONAL_COMMAND_COMPLETE"},
                mode="standard-four-hour-run",
                exit_code=0,
                success=True,
            )
            self.assertEqual(
                payload["schema_version"],
                child_terminal.CHILD_TERMINAL_MODE_SCHEMAS["standard-four-hour-run"],
            )
            read_back = child_terminal.read_child_terminal_envelope(
                terminal_path,
                expected_authorization_id="STANDARD_4H_TEST",
                expected_marker_path=marker_path,
                expected_marker_sha256=marker_sha,
                expected_exit_code=0,
                expected_mode="standard-four-hour-run",
            )
            self.assertEqual(read_back["mode"], "standard-four-hour-run")
            with self.assertRaises(child_terminal.ChildTerminalError):
                child_terminal.read_child_terminal_envelope(
                    terminal_path,
                    expected_authorization_id="STANDARD_4H_TEST",
                    expected_marker_path=marker_path,
                    expected_marker_sha256=marker_sha,
                    expected_exit_code=0,
                    expected_mode="run",
                )

    def test_standard_wrapper_child_command_is_not_ordinary_run(self) -> None:
        child = wrapper.build_child_command("/repo/.venv/bin/python")
        self.assertEqual(
            child,
            [
                "/repo/.venv/bin/python",
                "-m",
                "printer_v1.operator_cli.operational_memory_factory_command",
                "standard-four-hour-run",
                "--operator-approved",
            ],
        )

    def test_standard_wrapper_consumes_once_and_launches_only_standard_child(self) -> None:
        fx = StandardAuthorizationFixture()
        launches: list[list[str]] = []
        try:
            child_python = fx.make_fake_venv_python()
            app_root = fx.external / "applications"

            def launcher(*, command, cwd, env, stdout_path, stderr_path):
                launches.append(list(command))
                binding = child_terminal.resolve_child_terminal_binding(env)
                child_terminal.write_child_terminal_envelope(
                    binding=binding,
                    source={"status": "OPERATIONAL_COMMAND_COMPLETE"},
                    mode="standard-four-hour-run",
                    exit_code=0,
                    success=True,
                )
                return {"returncode": 0, "pid": 1234}

            result = wrapper.apply_authorization_once(
                authorization_file=fx.authorization_path,
                authorization_sha256=fx.authorization_sha256,
                operator_approved=True,
                repository_root=fx.repo,
                application_root=app_root,
                python_executable=child_python,
                process_launcher=launcher,
                migration_ledger_guard=lambda **_: None,
                pre_launch_check=lambda **_: None,
            )
            self.assertEqual(result["child_exit_code"], 0)
            self.assertTrue(result["child_terminal_valid"])
            self.assertEqual(len(launches), 1)
            self.assertEqual(launches[0], wrapper.build_child_command(str(child_python)))
            self.assertEqual(
                launches[0][-2:], ["standard-four-hour-run", "--operator-approved"]
            )
            with self.assertRaises(wrapper.StandardFourHourOneShotWrapperError):
                wrapper.apply_authorization_once(
                    authorization_file=fx.authorization_path,
                    authorization_sha256=fx.authorization_sha256,
                    operator_approved=True,
                    repository_root=fx.repo,
                    application_root=app_root,
                    python_executable=child_python,
                    process_launcher=launcher,
                    migration_ledger_guard=lambda **_: None,
                    pre_launch_check=lambda **_: None,
                )
            self.assertEqual(len(launches), 1)
        finally:
            fx.close()


if __name__ == "__main__":
    unittest.main()
