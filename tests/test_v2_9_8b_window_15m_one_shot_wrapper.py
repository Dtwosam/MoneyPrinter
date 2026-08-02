import contextlib
import hashlib
import io
import json
import os
from pathlib import Path
import socket
import sqlite3
import subprocess
import tempfile
import unittest
from unittest import mock

from printer_v1.operator_cli import operational_memory_factory_command as command
from printer_v1.operator_cli import window_15m_one_shot_wrapper as wrapper
from printer_v1.operator_cli.git_provenance_authorization_manifest import (
    GitProvenanceAuthorizationError,
    validate_git_provenance_authorization,
    validate_git_provenance_manifest_pre_marker,
)


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


class Fixture:
    def __init__(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.repo = self.root / "repo"
        self.app = self.root / "applications"
        self.repo.mkdir()
        self._git("init")
        self._git("config", "user.email", "tests@example.invalid")
        self._git("config", "user.name", "Wrapper Tests")
        (self.repo / ".gitignore").write_text("*.sqlite3\n", encoding="utf-8")
        (self.repo / "tracked.txt").write_text("clean\n", encoding="utf-8")
        history = self.repo / "operator-runs/history"
        history.mkdir(parents=True)
        for index in range(11):
            (history / f"historical-{index:02d}.json").write_text(
                json.dumps({"historical": index}) + "\n", encoding="utf-8"
            )
        self._git("add", ".")
        self._git("commit", "-m", "historical baseline")
        self.branch = self._git("rev-parse", "--abbrev-ref", "HEAD").stdout.strip()
        self.head = self._git("rev-parse", "HEAD").stdout.strip()

        self.authorization_id = "V2_9_8B_WINDOW_15M_AUTH_TESTONLY"
        self.migration_id = "V2_9_8B_AUTHORITATIVE_MIG050_TESTONLY"
        self.migration_root = (
            self.repo
            / "operator-runs/v2-9-8b-authoritative-mig050"
            / self.migration_id
        )
        self.authorization_root = (
            self.repo
            / "operator-runs/v2-9-8b-window-15m-final-authorization"
            / self.authorization_id
        )
        self.migration_root.mkdir(parents=True)
        self.authorization_root.mkdir(parents=True)

        for index in range(7):
            (self.migration_root / f"migration-{index:02d}.json").write_text(
                json.dumps({"migration": index}) + "\n", encoding="utf-8"
            )
        (self.migration_root / "backup-a.sqlite3").write_bytes(b"SQLITE-A")
        (self.migration_root / "backup-b.sqlite3").write_bytes(b"SQLITE-B")

        for index in range(9):
            (self.authorization_root / f"evidence-{index:02d}.json").write_text(
                json.dumps({"evidence": index}) + "\n", encoding="utf-8"
            )
        self.authorization_path = self.authorization_root / "final_authorization.json"
        self.rewrite_authorization()

    def _git(self, *args):
        return subprocess.run(
            ["git", *args],
            cwd=self.repo,
            capture_output=True,
            text=True,
            check=True,
        )

    def rewrite_authorization(self):
        self.branch = self._git("rev-parse", "--abbrev-ref", "HEAD").stdout.strip()
        self.head = self._git("rev-parse", "HEAD").stdout.strip()
        payload = {
            "authorization_id": self.authorization_id,
            "migration_execution_id": self.migration_id,
            "verdict": "V2_9_8B_WINDOW_15M_TEST_AUTHORIZATION_PASS",
            "authorized_git": {"branch": self.branch, "head": self.head},
            "authorized_command": {
                "mode": "run",
                "operator_approved": True,
                "allowed_invocation_count": 1,
                "automatic_retry_allowed": False,
                "manual_rerun_allowed": False,
                "resume_allowed": False,
                "restart_allowed": False,
                "successor_allowed": False,
            },
            "campaign_policy": {
                "main_window": "WINDOW_15M",
                "selective_1h_continuation": False,
            },
        }
        self.authorization_path.write_text(
            json.dumps(payload, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        self.authorization_sha256 = _sha(self.authorization_path)

    def build_external_manifest(self, *, created_at="2026-08-01T20:00:00+00:00"):
        payload, data = wrapper.build_manifest_bytes(
            repository_root=self.repo,
            authorization_file=self.authorization_path,
            authorization_sha256=self.authorization_sha256,
            created_at=created_at,
        )
        self.app.mkdir(exist_ok=True)
        path = self.app / "manifest.json"
        path.write_bytes(data)
        return payload, path, hashlib.sha256(data).hexdigest()

    def fake_launcher(self, *, returncode=0, raises=None):
        calls = []

        def launch(**kwargs):
            calls.append(kwargs)
            if raises is not None:
                raise raises
            kwargs["stdout_path"].write_text("child stdout\n", encoding="utf-8")
            kwargs["stderr_path"].write_text("child stderr\n", encoding="utf-8")
            return {"returncode": returncode, "pid": 4242}

        return calls, launch

    def close(self):
        self.tmp.cleanup()


class WrapperImplementationTests(unittest.TestCase):
    def setUp(self):
        self.fx = Fixture()

    def tearDown(self):
        self.fx.close()

    def apply(self, **overrides):
        params = dict(
            authorization_file=self.fx.authorization_path,
            authorization_sha256=self.fx.authorization_sha256,
            operator_approved=True,
            repository_root=self.fx.repo,
            application_root=self.fx.app,
            python_executable=self.fx.repo / ".venv/bin/python",
            created_at="2026-08-01T20:00:00+00:00",
            consumed_at="2026-08-01T20:01:00+00:00",
        )
        params.update(overrides)
        return wrapper.apply_authorization_once(**params)

    def test_01_manifest_exact_19_current_files(self):
        payload, _, _ = self.fx.build_external_manifest()
        self.assertEqual(len(payload["files"]), 19)
        self.assertEqual(
            len([item for item in payload["files"] if item["path"].endswith(".sqlite3")]),
            2,
        )

    def test_02_manifest_is_deterministic_for_fixed_time(self):
        first = wrapper.build_manifest_bytes(
            repository_root=self.fx.repo,
            authorization_file=self.fx.authorization_path,
            authorization_sha256=self.fx.authorization_sha256,
            created_at="2026-08-01T20:00:00+00:00",
        )[1]
        second = wrapper.build_manifest_bytes(
            repository_root=self.fx.repo,
            authorization_file=self.fx.authorization_path,
            authorization_sha256=self.fx.authorization_sha256,
            created_at="2026-08-01T20:00:00+00:00",
        )[1]
        self.assertEqual(first, second)

    def test_03_pre_marker_prepares_19_and_11_history(self):
        _, path, digest = self.fx.build_external_manifest()
        prepared = validate_git_provenance_manifest_pre_marker(
            repository_root=self.fx.repo,
            manifest_path=str(path.resolve()),
            manifest_sha256=digest,
        )
        self.assertEqual(prepared.file_count, 19)
        self.assertEqual(len(prepared.allowed_untracked_paths), 19)

    def test_04_pre_marker_and_full_validation_match(self):
        _, path, digest = self.fx.build_external_manifest()
        prepared = validate_git_provenance_manifest_pre_marker(
            repository_root=self.fx.repo,
            manifest_path=str(path.resolve()),
            manifest_sha256=digest,
        )
        _, marker = wrapper.build_marker_bytes(
            prepared, consumed_at="2026-08-01T20:01:00+00:00"
        )
        marker_path = self.fx.app / "marker.json"
        marker_path.write_bytes(marker)
        validated = validate_git_provenance_authorization(
            repository_root=self.fx.repo,
            manifest_path=str(path.resolve()),
            manifest_sha256=digest,
            marker_path=str(marker_path.resolve()),
            marker_sha256=hashlib.sha256(marker).hexdigest(),
        )
        self.assertEqual(
            prepared.allowed_untracked_paths, validated.allowed_untracked_paths
        )
        self.assertEqual(
            prepared.allowed_file_set_sha256, validated.allowed_file_set_sha256
        )

    def test_05_success_launches_exactly_one_child(self):
        calls, launcher = self.fx.fake_launcher()
        result = self.apply(process_launcher=launcher)
        self.assertEqual(result["child_exit_code"], 0)
        self.assertEqual(len(calls), 1)
        self.assertEqual(
            calls[0]["command"][2:],
            [
                "printer_v1.operator_cli.operational_memory_factory_command",
                "run",
                "--operator-approved",
            ],
        )
        self.assertTrue(os.path.samefile(calls[0]["cwd"], self.fx.repo))

    def test_06_child_receives_exact_four_bindings(self):
        calls, launcher = self.fx.fake_launcher()
        self.apply(process_launcher=launcher, environ={"BASE": "1"})
        env = calls[0]["env"]
        self.assertEqual({name for name in wrapper.BINDING_ENV_VARS if name in env},
                         set(wrapper.BINDING_ENV_VARS))
        self.assertEqual(env["BASE"], "1")

    def test_07_parent_environment_mapping_is_unchanged(self):
        parent = {name: f"old-{index}" for index, name in enumerate(wrapper.BINDING_ENV_VARS)}
        parent["BASE"] = "1"
        snapshot = dict(parent)
        _, launcher = self.fx.fake_launcher()
        self.apply(process_launcher=launcher, environ=parent)
        self.assertEqual(parent, snapshot)

    def test_08_marker_and_terminal_are_create_once(self):
        _, launcher = self.fx.fake_launcher()
        result = self.apply(process_launcher=launcher)
        marker = Path(result["marker_path"])
        terminal = marker.parent / "wrapper-terminal.json"
        self.assertTrue(marker.is_file())
        self.assertTrue(terminal.is_file())
        with self.assertRaises(wrapper.OneShotWrapperError):
            self.apply(process_launcher=launcher)

    def test_09_nonzero_child_is_terminal_without_retry(self):
        calls, launcher = self.fx.fake_launcher(returncode=7)
        result = self.apply(process_launcher=launcher)
        self.assertEqual(result["terminal_classification"], "CHILD_EXITED_NONZERO")
        self.assertEqual(result["automatic_retries"], 0)
        self.assertEqual(result["successors"], 0)
        self.assertEqual(len(calls), 1)

    def test_10_child_start_failure_consumes_without_successor(self):
        calls, launcher = self.fx.fake_launcher(raises=OSError("no child"))
        with self.assertRaises(OSError):
            self.apply(process_launcher=launcher)
        canonical = self.fx.app / self.fx.authorization_id
        self.assertTrue((canonical / "application-marker.json").exists())
        terminal = json.loads((canonical / "wrapper-terminal.json").read_text())
        self.assertEqual(terminal["terminal_classification"],
                         "CONSUMED_CHILD_START_FAILED")
        self.assertEqual(terminal["successors"], 0)
        self.assertEqual(len(calls), 1)

    def test_11_wrong_authorization_hash_blocks_before_marker(self):
        with self.assertRaises(wrapper.OneShotWrapperError):
            self.apply(authorization_sha256="0" * 64)
        self.assertFalse((self.fx.app / self.fx.authorization_id).exists())

    def test_12_explicit_operator_approval_is_required(self):
        with self.assertRaises(wrapper.OneShotWrapperError):
            self.apply(operator_approved=False)

    def test_13_dirty_tracked_tree_blocks_before_marker(self):
        (self.fx.repo / "tracked.txt").write_text("dirty\n", encoding="utf-8")
        with self.assertRaises(GitProvenanceAuthorizationError):
            self.apply()
        canonical = self.fx.app / self.fx.authorization_id
        self.assertFalse((canonical / "application-marker.json").exists())

    def test_14_extra_visible_file_blocks_before_marker(self):
        (self.fx.repo / "extra.txt").write_text("extra", encoding="utf-8")
        with self.assertRaises(GitProvenanceAuthorizationError):
            self.apply()

    def test_15_historical_mutation_blocks_before_marker(self):
        target = self.fx.repo / "operator-runs/history/historical-00.json"
        target.write_text("changed\n", encoding="utf-8")
        with self.assertRaises(GitProvenanceAuthorizationError):
            self.apply()

    @unittest.skipIf(not hasattr(os, "symlink"), "symlink unavailable")
    def test_16_symlink_in_current_package_blocks(self):
        target = self.fx.migration_root / "migration-00.json"
        target.unlink()
        os.symlink(self.fx.repo / "tracked.txt", target)
        with self.assertRaises(wrapper.OneShotWrapperError):
            self.apply()

    def test_17_preexisting_canonical_directory_blocks(self):
        (self.fx.app / self.fx.authorization_id).mkdir(parents=True)
        with self.assertRaises(wrapper.OneShotWrapperError):
            self.apply()

    def test_18_full_validation_disagreement_consumes_without_child(self):
        calls, launcher = self.fx.fake_launcher()

        def disagree(**kwargs):
            valid = validate_git_provenance_authorization(**kwargs)
            return type(valid)(
                allowed_untracked_paths=valid.allowed_untracked_paths[:-1],
                authorization_id=valid.authorization_id,
                manifest_sha256=valid.manifest_sha256,
                marker_sha256=valid.marker_sha256,
                allowed_file_set_sha256=valid.allowed_file_set_sha256,
                file_count=valid.file_count - 1,
            )

        with self.assertRaises(wrapper.OneShotWrapperError):
            self.apply(process_launcher=launcher, full_validator=disagree)
        canonical = self.fx.app / self.fx.authorization_id
        self.assertTrue((canonical / "application-marker.json").exists())
        self.assertEqual(calls, [])

    def test_19_partial_binding_environment_blocks_operational_command(self):
        with self.assertRaises(command.OperationalMemoryFactoryError):
            command._resolve_git_provenance_authorization(
                "run",
                environ={wrapper.BINDING_ENV_VARS[0]: "/tmp/manifest"},
                repository_root=self.fx.repo,
            )

    def test_20_direct_run_without_bindings_blocks_before_campaign(self):
        cleaned = {name: value for name, value in os.environ.items()
                   if name not in wrapper.BINDING_ENV_VARS}
        stderr = io.StringIO()
        with mock.patch.dict(os.environ, cleaned, clear=True), contextlib.redirect_stderr(stderr):
            result = command.main(["run", "--operator-approved"])
        self.assertEqual(result, 1)
        self.assertIn("ordinary run requires", stderr.getvalue())

    def test_21_preflight_only_remains_available_without_bindings(self):
        stdout = io.StringIO()
        with mock.patch.object(
            command, "build_activation_preflight", return_value={"status": "READY"}
        ), contextlib.redirect_stdout(stdout):
            result = command.main(["preflight-only"])
        self.assertEqual(result, 0)
        self.assertIn("READY", stdout.getvalue())

    def test_22_cli_rejects_unsupported_override(self):
        stderr = io.StringIO()
        with contextlib.redirect_stderr(stderr), self.assertRaises(SystemExit):
            wrapper.main(
                [
                    "--authorization-file", str(self.fx.authorization_path),
                    "--authorization-sha256", self.fx.authorization_sha256,
                    "--operator-approved",
                    "--artifact-root", str(self.fx.app),
                ]
            )

    def test_23_network_and_authoritative_sqlite_are_unused(self):
        calls, launcher = self.fx.fake_launcher()
        with mock.patch.object(
            socket.socket, "connect", side_effect=AssertionError("network")
        ), mock.patch.object(
            sqlite3, "connect", side_effect=AssertionError("sqlite")
        ):
            result = self.apply(process_launcher=launcher)
        self.assertEqual(result["child_exit_code"], 0)
        self.assertEqual(len(calls), 1)

    def test_24_tracked_file_in_current_root_blocks(self):
        target = self.fx.migration_root / "migration-00.json"
        self.fx._git("add", str(target.relative_to(self.fx.repo)))
        self.fx._git("commit", "-m", "track current file")
        self.fx.rewrite_authorization()
        with self.assertRaises(GitProvenanceAuthorizationError):
            self.apply()

    def test_25_wrong_authorization_location_blocks(self):
        copy = self.fx.repo / "operator-runs/wrong/final_authorization.json"
        copy.parent.mkdir(parents=True)
        copy.write_bytes(self.fx.authorization_path.read_bytes())
        with self.assertRaises(wrapper.OneShotWrapperError):
            self.apply(
                authorization_file=copy,
                authorization_sha256=_sha(copy),
            )

    def test_26_marker_payload_binds_preparation(self):
        _, path, digest = self.fx.build_external_manifest()
        prepared = validate_git_provenance_manifest_pre_marker(
            repository_root=self.fx.repo,
            manifest_path=str(path.resolve()),
            manifest_sha256=digest,
        )
        payload, data = wrapper.build_marker_bytes(
            prepared, consumed_at="2026-08-01T20:01:00+00:00"
        )
        self.assertEqual(payload["manifest_sha256"], digest)
        self.assertEqual(
            payload["allowed_file_set_sha256"],
            prepared.allowed_file_set_sha256,
        )
        self.assertTrue(data.endswith(b"\n"))


    def test_28_parent_alias_is_canonicalized_but_internal_alias_blocks(self):
        alias_parent = self.fx.root / "alias-parent"
        if not hasattr(os, "symlink"):
            self.skipTest("symlink unavailable")
        os.symlink(self.fx.root, alias_parent)
        aliased_authorization = (
            alias_parent
            / "repo"
            / self.fx.authorization_path.relative_to(self.fx.repo)
        )
        payload, data = wrapper.build_manifest_bytes(
            repository_root=self.fx.repo,
            authorization_file=aliased_authorization,
            authorization_sha256=self.fx.authorization_sha256,
            created_at="2026-08-01T20:00:00+00:00",
        )
        self.assertEqual(len(payload["files"]), 19)
        self.assertTrue(data.endswith(b"\n"))

        internal_alias = self.fx.repo / "authorization-alias"
        os.symlink(self.fx.authorization_root, internal_alias)
        aliased_inside_repo = internal_alias / "final_authorization.json"
        with self.assertRaisesRegex(
            wrapper.OneShotWrapperError,
            "internal filesystem alias",
        ):
            wrapper.build_manifest_bytes(
                repository_root=self.fx.repo,
                authorization_file=aliased_inside_repo,
                authorization_sha256=self.fx.authorization_sha256,
                created_at="2026-08-01T20:00:00+00:00",
            )

class LauncherShapeTests(unittest.TestCase):
    def test_27_powershell_is_thin_and_does_not_set_bindings(self):
        repository = Path(__file__).resolve().parents[1]
        text = (
            repository / "scripts/Start-PrinterV1-Window15M-OneShot.ps1"
        ).read_text(encoding="utf-8")
        self.assertIn("window_15m_one_shot_wrapper", text)
        self.assertNotIn("PRINTER_V1_GIT_PROVENANCE_MANIFEST_PATH", text)
        self.assertNotIn("operational_memory_factory_command", text)


if __name__ == "__main__":
    unittest.main()
