import contextlib
import hashlib
import io
import json
import os
from pathlib import Path
import socket
import sqlite3
import subprocess
import sys
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


def live_authoritative_database_binding() -> dict:
    """Observe the live authoritative database and return an honest binding.

    Read-only: the file is hashed and stat'd, never opened for writing.
    """
    path = command.AUTHORITATIVE_DB
    info = path.stat()
    connection = sqlite3.connect(
        f"file:{path.as_posix()}?mode=ro&immutable=1", uri=True, timeout=0.0
    )
    try:
        ledger = [
            str(row[0])
            for row in connection.execute(
                "SELECT version FROM printer_schema_migrations ORDER BY rowid"
            ).fetchall()
        ]
    finally:
        connection.close()
    return {
        "path": str(path),
        "sha256": _sha(path),
        "size": info.st_size,
        "inode": info.st_ino,
        "mtime_ns": info.st_mtime_ns,
        "migration_count": len(ledger),
        "migration_head": ledger[-1],
    }


def build_venv_layout(venv_dir: Path, base_target: Path) -> tuple[Path, Path]:
    """Create a disposable venv-style layout with a real symlink chain.

    The layout mirrors a normal POSIX virtual environment:
    ``.venv/bin/python -> python3 -> <external base target>`` with a regular,
    non-symlink ``pyvenv.cfg``. Returns ``(entrypoint, base_target)`` where the
    lexical ``entrypoint`` is what the wrapper must preserve and ``base_target``
    is the dereferenced executable that must never appear in the child command.
    """
    if os.name == "nt":
        exec_dir_name = "Scripts"
        entry_name = "python.exe"
    else:
        exec_dir_name = "bin"
        entry_name = "python"
    exec_dir = venv_dir / exec_dir_name
    exec_dir.mkdir(parents=True)
    (venv_dir / "pyvenv.cfg").write_text(
        "home = /usr/bin\nversion = 3.12.0\n", encoding="utf-8"
    )
    base_target.parent.mkdir(parents=True, exist_ok=True)
    base_target.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
    base_target.chmod(0o755)
    intermediate = exec_dir / (entry_name + "3" if os.name != "nt" else "python3.exe")
    entry = exec_dir / entry_name
    os.symlink(base_target, intermediate)
    os.symlink(intermediate, entry)
    return entry, base_target


class Fixture:
    def __init__(self):
        self.tmp = tempfile.TemporaryDirectory()
        # Resolve the temporary root so the repository, its ``.venv`` and every
        # derived path share one canonical prefix. macOS exposes the temporary
        # directory through both ``/var`` and ``/private/var``; the repaired
        # wrapper preserves the *lexical* venv entrypoint without dereferencing
        # symlinks, so the injected interpreter path and the resolved repository
        # root must not disagree only by that alias.
        self.root = Path(self.tmp.name).resolve()
        self.repo = self.root / "repo"
        self.app = self.root / "applications"
        self.repo.mkdir()
        self._git("init")
        self._git("config", "user.email", "tests@example.invalid")
        self._git("config", "user.name", "Wrapper Tests")
        (self.repo / ".gitignore").write_text(".venv/\n*.sqlite3\n", encoding="utf-8")
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

        # A real repository ``.venv`` symlink chain, gitignored so it never
        # perturbs the Git-provenance untracked/ignored evidence reconciliation.
        self.venv_dir = self.repo / ".venv"
        self.venv_base_target = self.root / "venv-base-python"
        self.venv_python, _ = build_venv_layout(
            self.venv_dir, self.venv_base_target
        )

    def _git(self, *args):
        return subprocess.run(
            ["git", *args],
            cwd=self.repo,
            capture_output=True,
            text=True,
            check=True,
        )

    def rewrite_authorization(self):
        from datetime import datetime, timedelta, timezone

        self.branch = self._git("rev-parse", "--abbrev-ref", "HEAD").stdout.strip()
        self.head = self._git("rev-parse", "HEAD").stdout.strip()
        issued = datetime.now(timezone.utc)
        payload = {
            "authorization_id": self.authorization_id,
            "migration_execution_id": self.migration_id,
            "verdict": "V2_9_8B_WINDOW_15M_TEST_AUTHORIZATION_PASS",
            "authorized_at": issued.isoformat(),
            "expires_at": (issued + timedelta(hours=12)).isoformat(),
            "validity_seconds": 43200,
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
            # The wrapper reviews this binding against the live authoritative
            # database before consuming anything, so the fixture must bind the
            # real file honestly rather than assert a convenient fiction.
            "authoritative_database": live_authoritative_database_binding(),
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
            python_executable=self.fx.venv_python,
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

    def test_23_network_unused_and_sqlite_limited_to_immutable_ledger_guard(self):
        """Network stays forbidden; SQLite is limited to the drift guard.

        The wrapper now runs the pre-authorization migration-ledger drift guard
        before staging, so it does open the authoritative database. That access
        must be immutable and read-only, and it must be the *only* SQLite use in
        the wrapper path.
        """
        calls, launcher = self.fx.fake_launcher()
        opened: list[tuple[str, bool]] = []
        real_connect = sqlite3.connect

        def recording_connect(target, *args, **kwargs):
            opened.append((str(target), bool(kwargs.get("uri"))))
            return real_connect(target, *args, **kwargs)

        db_before = _sha(command.AUTHORITATIVE_DB)
        with mock.patch.object(
            socket.socket, "connect", side_effect=AssertionError("network")
        ), mock.patch.object(sqlite3, "connect", side_effect=recording_connect):
            result = self.apply(process_launcher=launcher)

        self.assertEqual(result["child_exit_code"], 0)
        self.assertEqual(len(calls), 1)

        # Exactly one SQLite open, and it is the guard's immutable read-only
        # handle on the authoritative database.
        self.assertEqual(len(opened), 1, opened)
        target, used_uri = opened[0]
        self.assertTrue(used_uri)
        self.assertIn("mode=ro", target)
        self.assertIn("immutable=1", target)
        self.assertIn(command.AUTHORITATIVE_DB.as_posix(), target)

        # The authoritative database is observed, never written.
        self.assertEqual(_sha(command.AUTHORITATIVE_DB), db_before)

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

def _exec_dir_name() -> str:
    return "Scripts" if os.name == "nt" else "bin"


def _entry_name() -> str:
    return "python.exe" if os.name == "nt" else "python"


class ChildInterpreterPreservationTests(unittest.TestCase):
    """Integration coverage for lexical venv entrypoint preservation and the
    future-only staging cleanup, exercised through the injected launcher."""

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
            python_executable=self.fx.venv_python,
            created_at="2026-08-01T20:00:00+00:00",
            consumed_at="2026-08-01T20:01:00+00:00",
        )
        params.update(overrides)
        return wrapper.apply_authorization_once(**params)

    def test_29_symlink_chain_command_stays_lexical(self):
        calls, launcher = self.fx.fake_launcher()
        result = self.apply(process_launcher=launcher)
        self.assertEqual(len(calls), 1)
        command = calls[0]["command"]
        lexical = str(self.fx.venv_python)
        resolved_target = os.path.realpath(self.fx.venv_python)
        # The lexical venv entrypoint is preserved byte-for-byte.
        self.assertEqual(command[0], lexical)
        # The dereferenced base target never replaces the entrypoint.
        self.assertNotEqual(command[0], resolved_target)
        self.assertNotIn(resolved_target, command)
        self.assertNotEqual(command[0], str(self.fx.venv_base_target))
        # Terminal evidence records the same lexical entrypoint.
        self.assertEqual(result["child_command"][0], lexical)
        # The remaining operational arguments and launch shape are unchanged.
        self.assertEqual(
            command[1:],
            [
                "-m",
                "printer_v1.operator_cli.operational_memory_factory_command",
                "run",
                "--operator-approved",
            ],
        )
        self.assertEqual(
            set(calls[0]),
            {"command", "cwd", "env", "stdout_path", "stderr_path"},
        )
        self.assertTrue(os.path.samefile(calls[0]["cwd"], self.fx.repo))

    def test_30_direct_base_interpreter_blocks_before_marker(self):
        calls, launcher = self.fx.fake_launcher()
        # Passing the dereferenced Homebrew-style base interpreter directly (the
        # exact historical defect) is lexically outside <repo>/.venv.
        with self.assertRaises(wrapper.OneShotWrapperError):
            self.apply(
                process_launcher=launcher,
                python_executable=self.fx.venv_base_target,
            )
        self.assertEqual(calls, [])
        self.assertFalse((self.fx.app / self.fx.authorization_id).exists())
        self.assertFalse((self.fx.app / ".staging").exists())

    def test_31_future_empty_staging_is_removed(self):
        _, launcher = self.fx.fake_launcher()
        result = self.apply(process_launcher=launcher)
        self.assertEqual(result["child_exit_code"], 0)
        staging_parent = self.fx.app / ".staging"
        remaining = (
            list(staging_parent.iterdir()) if staging_parent.exists() else []
        )
        self.assertEqual(remaining, [])

    def test_32_non_empty_staging_is_not_recursively_deleted(self):
        calls, launcher = self.fx.fake_launcher()
        real_replace = os.replace
        littered = {}

        def replace_and_litter(src, dst, *args, **kwargs):
            real_replace(src, dst, *args, **kwargs)
            staging = Path(src).parent
            stray = staging / "residual-evidence.txt"
            stray.write_text(
                "must not be recursively deleted\n", encoding="utf-8"
            )
            littered["staging"] = staging
            littered["stray"] = stray

        with mock.patch.object(
            wrapper.os, "replace", side_effect=replace_and_litter
        ):
            result = self.apply(process_launcher=launcher)

        self.assertEqual(result["child_exit_code"], 0)
        # Exactly one child; cleanup residue changes no one-attempt counter.
        self.assertEqual(len(calls), 1)
        self.assertEqual(result["automatic_retries"], 0)
        self.assertEqual(result["successors"], 0)
        # The non-empty staging directory and its evidence survive untouched.
        self.assertTrue(littered["staging"].is_dir())
        self.assertTrue(littered["stray"].is_file())


class ChildInterpreterSelectorUnitTests(unittest.TestCase):
    """Fail-closed boundary and file-type coverage for ``_select_child_python``."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name).resolve()
        self.repo = self.root / "repo"
        self.repo.mkdir()

    def tearDown(self):
        self.tmp.cleanup()

    def select(self, override):
        return wrapper._select_child_python(
            repository_root=self.repo, override=override
        )

    def healthy(self):
        return build_venv_layout(self.repo / ".venv", self.root / "base-python")

    def test_33_healthy_chain_returns_lexical_entrypoint(self):
        entry, base = self.healthy()
        selected = self.select(entry)
        self.assertEqual(selected, str(entry))
        self.assertNotEqual(selected, os.path.realpath(entry))
        self.assertNotEqual(selected, str(base))

    def test_34_outside_venv_override_blocks(self):
        self.healthy()
        with self.assertRaisesRegex(
            wrapper.OneShotWrapperError, "outside the repository .venv"
        ):
            self.select(self.root / "base-python")

    def test_35_missing_pyvenv_cfg_blocks(self):
        entry, _ = self.healthy()
        (self.repo / ".venv" / "pyvenv.cfg").unlink()
        with self.assertRaisesRegex(wrapper.OneShotWrapperError, "pyvenv.cfg"):
            self.select(entry)

    @unittest.skipIf(not hasattr(os, "symlink"), "symlink unavailable")
    def test_36_symlinked_pyvenv_cfg_blocks(self):
        entry, _ = self.healthy()
        cfg = self.repo / ".venv" / "pyvenv.cfg"
        cfg.unlink()
        outside = self.root / "outside-pyvenv.cfg"
        outside.write_text("home = /usr/bin\n", encoding="utf-8")
        os.symlink(outside, cfg)
        with self.assertRaisesRegex(wrapper.OneShotWrapperError, "pyvenv.cfg"):
            self.select(entry)

    @unittest.skipIf(not hasattr(os, "symlink"), "symlink unavailable")
    def test_37_symlinked_venv_directory_blocks(self):
        real_venv = self.root / "real-venv"
        build_venv_layout(real_venv, self.root / "base-python")
        os.symlink(real_venv, self.repo / ".venv")
        lexical_entry = (
            self.repo / ".venv" / _exec_dir_name() / _entry_name()
        )
        with self.assertRaisesRegex(wrapper.OneShotWrapperError, "symlink"):
            self.select(lexical_entry)

    @unittest.skipIf(not hasattr(os, "symlink"), "symlink unavailable")
    def test_38_symlinked_executable_directory_blocks(self):
        venv = self.repo / ".venv"
        venv.mkdir()
        (venv / "pyvenv.cfg").write_text("home = /usr/bin\n", encoding="utf-8")
        real_bin = self.root / "real-bin"
        real_bin.mkdir()
        base = self.root / "base-python"
        base.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
        base.chmod(0o755)
        os.symlink(base, real_bin / _entry_name())
        os.symlink(real_bin, venv / _exec_dir_name())
        with self.assertRaisesRegex(wrapper.OneShotWrapperError, "symlink"):
            self.select(venv / _exec_dir_name() / _entry_name())

    @unittest.skipIf(not hasattr(os, "symlink"), "symlink unavailable")
    def test_39_broken_target_blocks(self):
        venv = self.repo / ".venv"
        (venv / _exec_dir_name()).mkdir(parents=True)
        (venv / "pyvenv.cfg").write_text("home = /usr/bin\n", encoding="utf-8")
        entry = venv / _exec_dir_name() / _entry_name()
        os.symlink(self.root / "does-not-exist", entry)
        with self.assertRaisesRegex(wrapper.OneShotWrapperError, "target"):
            self.select(entry)

    @unittest.skipIf(not hasattr(os, "symlink"), "symlink unavailable")
    def test_40_non_regular_target_blocks(self):
        venv = self.repo / ".venv"
        (venv / _exec_dir_name()).mkdir(parents=True)
        (venv / "pyvenv.cfg").write_text("home = /usr/bin\n", encoding="utf-8")
        target_dir = self.root / "target-dir"
        target_dir.mkdir()
        entry = venv / _exec_dir_name() / _entry_name()
        os.symlink(target_dir, entry)
        with self.assertRaisesRegex(wrapper.OneShotWrapperError, "regular file"):
            self.select(entry)

    def test_41_non_executable_entrypoint_blocks(self):
        if os.name == "nt":
            self.skipTest("POSIX executable-bit contract")
        venv = self.repo / ".venv"
        (venv / _exec_dir_name()).mkdir(parents=True)
        (venv / "pyvenv.cfg").write_text("home = /usr/bin\n", encoding="utf-8")
        entry = venv / _exec_dir_name() / _entry_name()
        entry.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
        entry.chmod(0o644)
        with self.assertRaisesRegex(wrapper.OneShotWrapperError, "not executable"):
            self.select(entry)

    def test_42_missing_entrypoint_blocks(self):
        venv = self.repo / ".venv"
        (venv / _exec_dir_name()).mkdir(parents=True)
        (venv / "pyvenv.cfg").write_text("home = /usr/bin\n", encoding="utf-8")
        entry = venv / _exec_dir_name() / _entry_name()
        with self.assertRaisesRegex(wrapper.OneShotWrapperError, "missing"):
            self.select(entry)


class RealVenvBootstrapProofTests(unittest.TestCase):
    """One real disposable subprocess boundary using the repository ``.venv``.

    The proof asserts venv identity and operational module-spec discovery
    without importing or executing the operational command and without creating
    any manifest, marker, campaign, database, memory, or provider artifact.
    """

    def _repo(self):
        return Path(__file__).resolve().parents[1]

    def _venv_python(self):
        return (
            self._repo() / ".venv" / _exec_dir_name() / _entry_name()
        )

    def test_43_default_selection_uses_lexical_repo_venv(self):
        repo = self._repo()
        venv_python = self._venv_python()
        if not venv_python.exists():
            self.skipTest("repository .venv is unavailable")
        if os.path.abspath(sys.executable) != str(venv_python):
            self.skipTest("tests are not running from the repository .venv")
        selected = wrapper._select_child_python(
            repository_root=repo, override=None
        )
        self.assertEqual(selected, str(venv_python))
        self.assertNotEqual(selected, os.path.realpath(venv_python))

    def test_44_real_subprocess_bootstrap_proof(self):
        repo = self._repo()
        venv_python = self._venv_python()
        if not venv_python.exists():
            self.skipTest("repository .venv is unavailable")
        # The lexical entrypoint must differ from its resolved base target.
        self.assertNotEqual(str(venv_python), os.path.realpath(venv_python))
        probe = (
            "import json, sys, importlib.util as u\n"
            "print(json.dumps({\n"
            "  'executable': sys.executable,\n"
            "  'prefix': sys.prefix,\n"
            "  'base_prefix': sys.base_prefix,\n"
            "  'is_venv': sys.prefix != sys.base_prefix,\n"
            "  'printer_v1': u.find_spec('printer_v1') is not None,\n"
            "  'operational': u.find_spec(\n"
            "     'printer_v1.operator_cli.operational_memory_factory_command'\n"
            "  ) is not None,\n"
            "}, sort_keys=True))\n"
        )
        result = subprocess.run(
            [str(venv_python), "-c", probe],
            cwd=str(repo),
            capture_output=True,
            text=True,
            timeout=30,
            shell=False,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        data = json.loads(result.stdout)
        self.assertTrue(data["is_venv"])
        self.assertNotEqual(data["prefix"], data["base_prefix"])
        self.assertTrue(os.path.samefile(data["prefix"], repo / ".venv"))
        self.assertTrue(data["printer_v1"])
        self.assertTrue(data["operational"])


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
