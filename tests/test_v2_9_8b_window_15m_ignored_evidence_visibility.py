"""Focused ignored-evidence visibility reconciliation tests.

Every test uses a disposable repository and external fixture files. No provider,
database, Scheduler, campaign, memory, retrieval, or financial capability runs.
"""

from __future__ import annotations

import copy
import hashlib
import json
import os
from pathlib import Path
import socket
import subprocess
import tempfile
import unittest
from datetime import datetime, timedelta, timezone

from printer_v1.operator_cli.git_provenance_authorization_manifest import (
    APPLICATION_MARKER_SCHEMA_VERSION,
    AUTHORIZATION_PACKAGE_KIND,
    AUTHORIZATION_PACKAGE_ROOT,
    MANIFEST_SCHEMA_VERSION,
    MIGRATION_PACKAGE_KIND,
    MIGRATION_PACKAGE_ROOT,
    GitProvenanceAuthorizationError,
    compute_allowed_file_set_sha256,
    validate_git_provenance_authorization,
)


def _digest_records(manifest: dict) -> list:
    records = list(manifest["files"])
    for entry in manifest.get("historical_authorization_evidence") or []:
        records.append(
            {
                "package_kind": entry["evidence_class"],
                "path": entry["path"],
                "sha256": entry["sha256"],
                "size": entry["size"],
            }
        )
    return records


AUTH_ID = "V2_9_8B_WINDOW_15M_AUTH_IGNORED_TEST"
MIG_ID = "V2_9_8B_AUTHORITATIVE_MIG050_IGNORED_TEST"


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


class Fixture:
    def __init__(self, root: Path, *, tracked_operator_file: bool = False):
        self.root = root
        self.repo = root / "repository"
        self.external = root / "external"
        self.repo.mkdir()
        self.external.mkdir()
        self.git("init")
        self.git("config", "user.email", "printer-tests@example.invalid")
        self.git("config", "user.name", "Printer Tests")

        (self.repo / ".gitignore").write_text("*.sqlite3\n", encoding="ascii")
        (self.repo / "tracked.txt").write_text("clean\n", encoding="ascii")
        if tracked_operator_file:
            tracked = self.repo / "operator-runs" / "tracked-evidence.txt"
            tracked.parent.mkdir(parents=True)
            tracked.write_text("tracked\n", encoding="ascii")
        self.git("add", ".")
        self.git("commit", "-m", "fixture")
        self.head = self.git("rev-parse", "HEAD").stdout.strip().lower()
        self.branch = self.git("rev-parse", "--abbrev-ref", "HEAD").stdout.strip()

        self.auth_root = f"{AUTHORIZATION_PACKAGE_ROOT}/{AUTH_ID}"
        self.mig_root = f"{MIGRATION_PACKAGE_ROOT}/{MIG_ID}"
        issued = datetime.now(timezone.utc)
        self.authorization = {
            "authorization_id": AUTH_ID,
            "verdict": "V2_9_8B_WINDOW_15M_TEST_FINAL_AUTHORIZATION_PASS",
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
            "authoritative_database": {
                "path": "/tmp/testonly-printer-v1-ignored.sqlite3",
                "sha256": "b" * 64,
                "size": 1,
                "inode": 1,
                "mtime_ns": 1,
                "migration_count": 52,
                "migration_head": "052_memory_observation_eligibility_layers.sql",
            },
            "prior_authorizations_non_reusable": [],
        }
        self.files = []
        self.add(
            f"{self.auth_root}/final_authorization.json",
            json.dumps(self.authorization, sort_keys=True).encode(),
            AUTHORIZATION_PACKAGE_KIND,
        )
        self.add(
            f"{self.auth_root}/pre_run_evidence.json",
            b'{"kind":"pre_run"}\n',
            AUTHORIZATION_PACKAGE_KIND,
        )
        self.add(
            f"{self.auth_root}/application_started.json",
            b'{"kind":"started"}\n',
            AUTHORIZATION_PACKAGE_KIND,
        )
        self.add(
            f"{self.mig_root}/preflight.json",
            b'{"kind":"preflight"}\n',
            MIGRATION_PACKAGE_KIND,
        )
        for index in range(13):
            self.add(
                f"{self.mig_root}/evidence/evidence-{index:02d}.json",
                f'{{"index":{index}}}\n'.encode(),
                MIGRATION_PACKAGE_KIND,
            )
        self.add(
            f"{self.mig_root}/disposable-restore/printer_v1-rehearsal.sqlite3",
            b"SQLITE-REHEARSAL",
            MIGRATION_PACKAGE_KIND,
        )
        self.add(
            f"{self.mig_root}/verified-backup/printer_v1-pre050.sqlite3",
            b"SQLITE-BACKUP",
            MIGRATION_PACKAGE_KIND,
        )
        assert len(self.files) == 19

        auth_path = f"{self.auth_root}/final_authorization.json"
        auth_sha = _sha((self.repo / auth_path).read_bytes())
        self.manifest = {
            "schema_version": MANIFEST_SCHEMA_VERSION,
            "authorization_id": AUTH_ID,
            "authorization_file": {"path": auth_path, "sha256": auth_sha},
            "repository": {"branch": self.branch, "head": self.head},
            "authorized_command": {"mode": "run", "operator_approved": True},
            "migration_execution_id": MIG_ID,
            "created_at": datetime(2026, 8, 1, tzinfo=timezone.utc).isoformat(),
            "files": copy.deepcopy(self.files),
            "historical_authorization_evidence": [],
        }
        self.manifest_path = self.external / "manifest.json"
        self.marker_path = self.external / "marker.json"
        self.write_manifest(self.manifest)
        self.write_marker()

    def git(self, *args):
        return subprocess.run(
            ["git", *args],
            cwd=self.repo,
            capture_output=True,
            text=True,
            check=True,
        )

    def add(self, relative: str, data: bytes, kind: str):
        path = self.repo / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
        self.files.append(
            {
                "path": relative,
                "sha256": _sha(data),
                "size": len(data),
                "package_kind": kind,
            }
        )

    def write_manifest(self, manifest: dict):
        data = json.dumps(manifest, indent=2, sort_keys=True).encode()
        self.manifest_path.write_bytes(data)
        self.manifest_sha = _sha(data)
        self.manifest = manifest

    def write_marker(self):
        auth_path = self.manifest["authorization_file"]["path"]
        marker = {
            "schema_version": APPLICATION_MARKER_SCHEMA_VERSION,
            "authorization_id": AUTH_ID,
            "authorization_consumed_at": datetime(
                2026, 8, 1, 21, tzinfo=timezone.utc
            ).isoformat(),
            "authorization_sha256": _sha((self.repo / auth_path).read_bytes()),
            "manifest_sha256": self.manifest_sha,
            "allowed_file_set_sha256": compute_allowed_file_set_sha256(
                _digest_records(self.manifest)
            ),
            "repository_branch": self.branch,
            "repository_head": self.head,
            "command": {"mode": "run", "operator_approved": True},
            "allowed_invocation_count": 1,
            "automatic_retry_allowed": False,
            "manual_rerun_allowed": False,
            "resume_allowed": False,
            "restart_allowed": False,
            "successor_allowed": False,
        }
        data = json.dumps(marker, indent=2, sort_keys=True).encode()
        self.marker_path.write_bytes(data)
        self.marker_sha = _sha(data)

    def validate(self, **overrides):
        kwargs = {
            "repository_root": self.repo,
            "manifest_path": str(self.manifest_path),
            "manifest_sha256": self.manifest_sha,
            "marker_path": str(self.marker_path),
            "marker_sha256": self.marker_sha,
        }
        kwargs.update(overrides)
        return validate_git_provenance_authorization(**kwargs)

    def visible(self):
        raw = self.git(
            "ls-files", "--others", "--exclude-standard", "-z"
        ).stdout
        return {item for item in raw.split("\0") if item}

    def ignored(self):
        raw = self.git(
            "ls-files",
            "--others",
            "--ignored",
            "--exclude-standard",
            "-z",
            "--",
            "operator-runs/",
        ).stdout
        return {item for item in raw.split("\0") if item}


class IgnoredEvidenceVisibilityTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.fx = Fixture(Path(self.tmp.name))

    def tearDown(self):
        self.tmp.cleanup()

    def test_authoritative_shape_17_visible_2_ignored_passes(self):
        self.assertEqual(len(self.fx.visible()), 17)
        self.assertEqual(len(self.fx.ignored()), 2)
        result = self.fx.validate()
        self.assertEqual(result.file_count, 19)
        self.assertEqual(set(result.allowed_untracked_paths), {
            item["path"] for item in self.fx.files
        })

    def test_digest_includes_ignored_files_and_is_deterministic(self):
        full = compute_allowed_file_set_sha256(self.fx.manifest["files"])
        reverse = compute_allowed_file_set_sha256(
            list(reversed(self.fx.manifest["files"]))
        )
        visible_only = [
            item for item in self.fx.manifest["files"]
            if not item["path"].endswith(".sqlite3")
        ]
        self.assertEqual(full, reverse)
        self.assertNotEqual(full, compute_allowed_file_set_sha256(visible_only))

    def test_extra_ignored_inside_authorized_package_blocks(self):
        extra = self.fx.repo / self.fx.mig_root / "extra.sqlite3"
        extra.write_bytes(b"extra")
        with self.assertRaisesRegex(
            GitProvenanceAuthorizationError, "unexpected ignored operator-runs file"
        ):
            self.fx.validate()

    def test_extra_ignored_outside_authorized_packages_blocks(self):
        extra = self.fx.repo / "operator-runs" / "other-package" / "extra.sqlite3"
        extra.parent.mkdir(parents=True)
        extra.write_bytes(b"extra")
        with self.assertRaisesRegex(
            GitProvenanceAuthorizationError, "unexpected ignored operator-runs file"
        ):
            self.fx.validate()

    def test_ignored_file_missing_from_filesystem_blocks(self):
        path = self.fx.repo / self.fx.mig_root / "verified-backup" / "printer_v1-pre050.sqlite3"
        path.unlink()
        with self.assertRaisesRegex(
            GitProvenanceAuthorizationError, "missing or not a regular file"
        ):
            self.fx.validate()

    def test_ignored_file_omitted_from_manifest_blocks(self):
        manifest = copy.deepcopy(self.fx.manifest)
        manifest["files"] = [
            item for item in manifest["files"]
            if not item["path"].endswith("printer_v1-pre050.sqlite3")
        ]
        self.fx.write_manifest(manifest)
        with self.assertRaisesRegex(
            GitProvenanceAuthorizationError, "unexpected ignored operator-runs file"
        ):
            self.fx.validate()

    def test_tracked_operator_runs_file_is_bound_to_clean_head(self):
        other_tmp = tempfile.TemporaryDirectory()
        try:
            fixture = Fixture(Path(other_tmp.name), tracked_operator_file=True)
            result = fixture.validate()
            self.assertEqual(result.file_count, 19)
            self.assertNotIn(
                "operator-runs/tracked-evidence.txt",
                result.allowed_untracked_paths,
            )
        finally:
            other_tmp.cleanup()

    def test_visible_extra_outside_operator_runs_blocks(self):
        (self.fx.repo / "stray.txt").write_text("stray", encoding="ascii")
        with self.assertRaisesRegex(
            GitProvenanceAuthorizationError, "unexpected untracked repository file"
        ):
            self.fx.validate()

    def test_visible_extra_inside_operator_runs_blocks(self):
        extra = self.fx.repo / self.fx.mig_root / "extra.json"
        extra.write_text("{}", encoding="ascii")
        with self.assertRaisesRegex(
            GitProvenanceAuthorizationError, "unexpected untracked repository file"
        ):
            self.fx.validate()

    def test_extra_symlink_file_blocks(self):
        target = self.fx.root / "outside.txt"
        target.write_text("outside", encoding="ascii")
        link = self.fx.repo / self.fx.mig_root / "extra-link"
        os.symlink(target, link)
        with self.assertRaisesRegex(
            GitProvenanceAuthorizationError, "inventory contains a symlink"
        ):
            self.fx.validate()

    def test_extra_symlink_directory_blocks_without_traversal(self):
        outside = self.fx.root / "outside-dir"
        outside.mkdir()
        (outside / "secret").write_text("secret", encoding="ascii")
        link = self.fx.repo / "operator-runs" / "linked-dir"
        os.symlink(outside, link)
        with self.assertRaisesRegex(
            GitProvenanceAuthorizationError, "inventory contains a symlink"
        ):
            self.fx.validate()

    def test_non_regular_entry_blocks_when_fifo_supported(self):
        if not hasattr(os, "mkfifo"):
            self.skipTest("FIFO creation is unavailable")
        fifo = self.fx.repo / self.fx.mig_root / "evidence.fifo"
        os.mkfifo(fifo)
        with self.assertRaisesRegex(
            GitProvenanceAuthorizationError, "non-regular entry"
        ):
            self.fx.validate()

    def test_manifest_path_classified_by_neither_set_blocks(self):
        real_run = subprocess.run

        def runner(args, **kwargs):
            arguments = args[1:]
            if arguments[:4] == [
                "ls-files", "--others", "--ignored", "--exclude-standard"
            ]:
                return subprocess.CompletedProcess(args, 0, stdout="", stderr="")
            return real_run(args, **kwargs)

        with self.assertRaisesRegex(
            GitProvenanceAuthorizationError, "neither visible nor ignored"
        ):
            self.fx.validate(runner=runner)

    def test_visible_and_ignored_overlap_blocks(self):
        real_run = subprocess.run
        ignored = sorted(self.fx.ignored())
        visible_path = sorted(self.fx.visible())[0]

        def runner(args, **kwargs):
            arguments = args[1:]
            if arguments[:4] == [
                "ls-files", "--others", "--ignored", "--exclude-standard"
            ]:
                output = "\0".join([*ignored, visible_path]) + "\0"
                return subprocess.CompletedProcess(args, 0, stdout=output, stderr="")
            return real_run(args, **kwargs)

        with self.assertRaisesRegex(
            GitProvenanceAuthorizationError, "classifications overlap"
        ):
            self.fx.validate(runner=runner)

    def test_unrelated_ignored_content_outside_operator_runs_is_not_authorized(self):
        (self.fx.repo / "local.sqlite3").write_bytes(b"unrelated")
        result = self.fx.validate()
        self.assertEqual(result.file_count, 19)
        self.assertNotIn("local.sqlite3", result.allowed_untracked_paths)

    def test_validation_performs_no_network(self):
        real_socket = socket.socket

        def forbidden(*args, **kwargs):
            raise AssertionError("network access is forbidden")

        socket.socket = forbidden
        try:
            result = self.fx.validate()
        finally:
            socket.socket = real_socket
        self.assertEqual(result.file_count, 19)

    def test_existing_authorization_and_marker_contracts_remain_fail_closed(self):
        document_path = (
            self.fx.repo
            / self.fx.auth_root
            / "final_authorization.json"
        )
        document = copy.deepcopy(self.fx.authorization)
        document["verdict"] = "V2_9_8B_WINDOW_15M_TEST_BLOCKED"
        data = json.dumps(document, sort_keys=True).encode()
        document_path.write_bytes(data)

        manifest = copy.deepcopy(self.fx.manifest)
        new_sha = _sha(data)
        manifest["authorization_file"]["sha256"] = new_sha
        for record in manifest["files"]:
            if record["path"] == f"{self.fx.auth_root}/final_authorization.json":
                record["sha256"] = new_sha
                record["size"] = len(data)
        self.fx.write_manifest(manifest)
        self.fx.write_marker()

        with self.assertRaisesRegex(
            GitProvenanceAuthorizationError, "verdict is not PASS"
        ):
            self.fx.validate()

    def test_marker_digest_mismatch_still_blocks(self):
        marker = json.loads(self.fx.marker_path.read_text())
        marker["allowed_file_set_sha256"] = "1" * 64
        data = json.dumps(marker, indent=2, sort_keys=True).encode()
        self.fx.marker_path.write_bytes(data)
        self.fx.marker_sha = _sha(data)
        with self.assertRaisesRegex(
            GitProvenanceAuthorizationError, "allowed_file_set_sha256 mismatch"
        ):
            self.fx.validate()

    def test_manifest_schema_extra_key_still_blocks(self):
        manifest = copy.deepcopy(self.fx.manifest)
        manifest["extra"] = True
        self.fx.write_manifest(manifest)
        with self.assertRaisesRegex(
            GitProvenanceAuthorizationError, "manifest schema is malformed"
        ):
            self.fx.validate()

    def test_duplicate_manifest_path_still_blocks(self):
        manifest = copy.deepcopy(self.fx.manifest)
        manifest["files"].append(copy.deepcopy(manifest["files"][0]))
        self.fx.write_manifest(manifest)
        with self.assertRaisesRegex(
            GitProvenanceAuthorizationError, "duplicate manifest file path"
        ):
            self.fx.validate()

    def test_hash_and_size_validation_still_blocks(self):
        manifest = copy.deepcopy(self.fx.manifest)
        manifest["files"][3]["size"] += 1
        self.fx.write_manifest(manifest)
        with self.assertRaisesRegex(
            GitProvenanceAuthorizationError, "size mismatch"
        ):
            self.fx.validate()

    def test_staged_and_unstaged_tracked_changes_still_block(self):
        (self.fx.repo / "tracked.txt").write_text("unstaged\n", encoding="ascii")
        with self.assertRaisesRegex(
            GitProvenanceAuthorizationError, "unstaged changes"
        ):
            self.fx.validate()

        self.fx.git("checkout", "--", "tracked.txt")
        (self.fx.repo / "tracked.txt").write_text("staged\n", encoding="ascii")
        self.fx.git("add", "tracked.txt")
        with self.assertRaisesRegex(
            GitProvenanceAuthorizationError, "staged changes"
        ):
            self.fx.validate()

    def test_manifest_and_marker_must_remain_external(self):
        inside_manifest = self.fx.repo / "inside-manifest.json"
        inside_manifest.write_bytes(self.fx.manifest_path.read_bytes())
        with self.assertRaisesRegex(
            GitProvenanceAuthorizationError, "manifest must live outside"
        ):
            self.fx.validate(
                manifest_path=str(inside_manifest),
                manifest_sha256=_sha(inside_manifest.read_bytes()),
            )

    def test_summary_remains_bounded_and_filename_free(self):
        summary = self.fx.validate().summary()
        self.assertEqual(
            set(summary),
            {
                "authorization_id",
                "manifest_sha256",
                "marker_sha256",
                "allowed_file_set_sha256",
                "allowed_file_count",
            },
        )
        serialized = json.dumps(summary)
        for record in self.fx.files:
            self.assertNotIn(record["path"], serialized)


class CurrentVsHistoricalTrustBoundaryTests(unittest.TestCase):
    HISTORICAL_FILES = (
        "operator-runs/v2-9-7e-5-live-proof/result.json",
        "operator-runs/v2-9-7e-5-live-proof/runner.py",
        "operator-runs/v2-9-7e-5a-decisive-reproof/result.json",
        "operator-runs/v2-9-7e-5a-decisive-reproof/runner.py",
        "operator-runs/v2-9-7e-6-classification/result.json",
        "operator-runs/v2-9-7e-6-classification/runner.py",
        "operator-runs/v2-9-7e-6-final-proof/result.json",
        "operator-runs/v2-9-7e-6-final-proof/runner.py",
        "operator-runs/v2-9-8b-mig050-bounded-proof/CONTROLLING_EXECUTION",
        "operator-runs/v2-9-8b-mig050-bounded-proof/execution/proof_summary.json",
        "operator-runs/v2-9-8b-mig050-bounded-proof/proof_summary.json",
    )

    def make_fixture(self, *, tracked_in_current_root: bool = False):
        tmp = tempfile.TemporaryDirectory()
        root = Path(tmp.name)
        repo = root / "repository"
        external = root / "external"
        repo.mkdir()
        external.mkdir()

        def git(*args):
            return subprocess.run(
                ["git", *args],
                cwd=repo,
                capture_output=True,
                text=True,
                check=True,
            )

        git("init")
        git("config", "user.email", "printer-tests@example.invalid")
        git("config", "user.name", "Printer Tests")
        (repo / ".gitignore").write_text("*.sqlite3\n", encoding="ascii")
        (repo / "tracked.txt").write_text("clean\n", encoding="ascii")

        for index, relative in enumerate(self.HISTORICAL_FILES):
            path = repo / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(f"historical-{index}\n", encoding="ascii")

        auth_root = f"{AUTHORIZATION_PACKAGE_ROOT}/{AUTH_ID}"
        mig_root = f"{MIGRATION_PACKAGE_ROOT}/{MIG_ID}"
        if tracked_in_current_root:
            tracked = repo / auth_root / "tracked-current.txt"
            tracked.parent.mkdir(parents=True, exist_ok=True)
            tracked.write_text("must block\n", encoding="ascii")

        git("add", ".")
        git("commit", "-m", "historical baseline")
        head = git("rev-parse", "HEAD").stdout.strip().lower()
        branch = git("rev-parse", "--abbrev-ref", "HEAD").stdout.strip()

        issued = datetime.now(timezone.utc)
        authorization = {
            "authorization_id": AUTH_ID,
            "verdict": "V2_9_8B_WINDOW_15M_TEST_FINAL_AUTHORIZATION_PASS",
            "authorized_at": issued.isoformat(),
            "expires_at": (issued + timedelta(hours=12)).isoformat(),
            "validity_seconds": 43200,
            "authorized_git": {"branch": branch, "head": head},
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
            "authoritative_database": {
                "path": "/tmp/testonly-printer-v1-trust.sqlite3",
                "sha256": "c" * 64,
                "size": 1,
                "inode": 1,
                "mtime_ns": 1,
                "migration_count": 52,
                "migration_head": "052_memory_observation_eligibility_layers.sql",
            },
            "prior_authorizations_non_reusable": [],
        }

        files = []

        def add(relative: str, data: bytes, kind: str):
            path = repo / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(data)
            files.append(
                {
                    "path": relative,
                    "sha256": _sha(data),
                    "size": len(data),
                    "package_kind": kind,
                }
            )

        add(
            f"{auth_root}/final_authorization.json",
            json.dumps(authorization, sort_keys=True).encode(),
            AUTHORIZATION_PACKAGE_KIND,
        )
        add(
            f"{auth_root}/pre_run_evidence.json",
            b'{"kind":"pre_run"}\n',
            AUTHORIZATION_PACKAGE_KIND,
        )
        add(
            f"{auth_root}/application_started.json",
            b'{"kind":"started"}\n',
            AUTHORIZATION_PACKAGE_KIND,
        )
        add(
            f"{mig_root}/preflight.json",
            b'{"kind":"preflight"}\n',
            MIGRATION_PACKAGE_KIND,
        )
        for index in range(13):
            add(
                f"{mig_root}/evidence/evidence-{index:02d}.json",
                f'{{"index":{index}}}\n'.encode(),
                MIGRATION_PACKAGE_KIND,
            )
        add(
            f"{mig_root}/disposable-restore/printer_v1-rehearsal.sqlite3",
            b"SQLITE-REHEARSAL",
            MIGRATION_PACKAGE_KIND,
        )
        add(
            f"{mig_root}/verified-backup/printer_v1-pre050.sqlite3",
            b"SQLITE-BACKUP",
            MIGRATION_PACKAGE_KIND,
        )
        self.assertEqual(len(files), 19)

        auth_path = f"{auth_root}/final_authorization.json"
        manifest = {
            "schema_version": MANIFEST_SCHEMA_VERSION,
            "authorization_id": AUTH_ID,
            "authorization_file": {
                "path": auth_path,
                "sha256": _sha((repo / auth_path).read_bytes()),
            },
            "repository": {"branch": branch, "head": head},
            "authorized_command": {"mode": "run", "operator_approved": True},
            "migration_execution_id": MIG_ID,
            "created_at": datetime(2026, 8, 1, tzinfo=timezone.utc).isoformat(),
            "files": copy.deepcopy(files),
            "historical_authorization_evidence": [],
        }
        manifest_path = external / "manifest.json"
        marker_path = external / "marker.json"

        data = json.dumps(manifest, indent=2, sort_keys=True).encode()
        manifest_path.write_bytes(data)
        manifest_sha = _sha(data)
        marker = {
            "schema_version": APPLICATION_MARKER_SCHEMA_VERSION,
            "authorization_id": AUTH_ID,
            "authorization_consumed_at": datetime(
                2026, 8, 1, 21, tzinfo=timezone.utc
            ).isoformat(),
            "authorization_sha256": _sha((repo / auth_path).read_bytes()),
            "manifest_sha256": manifest_sha,
            "allowed_file_set_sha256": compute_allowed_file_set_sha256(
                _digest_records(manifest)
            ),
            "repository_branch": branch,
            "repository_head": head,
            "command": {"mode": "run", "operator_approved": True},
            "allowed_invocation_count": 1,
            "automatic_retry_allowed": False,
            "manual_rerun_allowed": False,
            "resume_allowed": False,
            "restart_allowed": False,
            "successor_allowed": False,
        }
        marker_data = json.dumps(marker, indent=2, sort_keys=True).encode()
        marker_path.write_bytes(marker_data)
        marker_sha = _sha(marker_data)

        def validate(**overrides):
            kwargs = {
                "repository_root": repo,
                "manifest_path": str(manifest_path),
                "manifest_sha256": manifest_sha,
                "marker_path": str(marker_path),
                "marker_sha256": marker_sha,
            }
            kwargs.update(overrides)
            return validate_git_provenance_authorization(**kwargs)

        return {
            "tmp": tmp,
            "repo": repo,
            "validate": validate,
            "files": files,
            "auth_root": auth_root,
            "mig_root": mig_root,
            "historical": set(self.HISTORICAL_FILES),
        }

    def test_real_shape_11_tracked_19_current_30_total_passes(self):
        fx = self.make_fixture()
        self.addCleanup(fx["tmp"].cleanup)
        result = fx["validate"]()
        allowed = set(result.allowed_untracked_paths)
        inventory = {
            path.relative_to(fx["repo"]).as_posix()
            for path in (fx["repo"] / "operator-runs").rglob("*")
            if path.is_file()
        }
        self.assertEqual(len(inventory), 30)
        self.assertEqual(result.file_count, 19)
        self.assertEqual(allowed, {record["path"] for record in fx["files"]})
        self.assertTrue(allowed.isdisjoint(fx["historical"]))

    def test_manifest_digest_excludes_tracked_history(self):
        fx = self.make_fixture()
        self.addCleanup(fx["tmp"].cleanup)
        digest = compute_allowed_file_set_sha256(fx["files"])
        for historical in fx["historical"]:
            self.assertNotIn(historical, json.dumps(fx["files"]))
        self.assertEqual(
            digest,
            compute_allowed_file_set_sha256(list(reversed(fx["files"]))),
        )

    def test_visible_untracked_historical_looking_file_blocks(self):
        fx = self.make_fixture()
        self.addCleanup(fx["tmp"].cleanup)
        extra = fx["repo"] / "operator-runs/v2-9-7e-5-live-proof/new.json"
        extra.write_text("{}\n", encoding="ascii")
        with self.assertRaisesRegex(
            GitProvenanceAuthorizationError, "unexpected untracked repository file"
        ):
            fx["validate"]()

    def test_ignored_untracked_historical_looking_file_blocks(self):
        fx = self.make_fixture()
        self.addCleanup(fx["tmp"].cleanup)
        extra = fx["repo"] / "operator-runs/v2-9-7e-5-live-proof/new.sqlite3"
        extra.write_bytes(b"unexpected")
        with self.assertRaisesRegex(
            GitProvenanceAuthorizationError, "unexpected ignored operator-runs file"
        ):
            fx["validate"]()

    def test_tracked_file_inside_current_root_blocks(self):
        fx = self.make_fixture(tracked_in_current_root=True)
        self.addCleanup(fx["tmp"].cleanup)
        with self.assertRaisesRegex(
            GitProvenanceAuthorizationError,
            "tracked file exists inside a current evidence package",
        ):
            fx["validate"]()

    def test_manifest_path_reported_tracked_blocks(self):
        fx = self.make_fixture()
        self.addCleanup(fx["tmp"].cleanup)
        real_run = subprocess.run
        manifest_path = fx["files"][0]["path"]

        def runner(args, **kwargs):
            arguments = args[1:]
            if arguments[:5] == [
                "ls-tree", "-r", "--name-only", "-z", "HEAD"
            ]:
                output = "\0".join([*sorted(fx["historical"]), manifest_path]) + "\0"
                return subprocess.CompletedProcess(args, 0, stdout=output, stderr="")
            return real_run(args, **kwargs)

        with self.assertRaisesRegex(
            GitProvenanceAuthorizationError,
            "classifications overlap|current manifest file is tracked",
        ):
            fx["validate"](runner=runner)

    def test_extra_visible_inside_current_root_blocks(self):
        fx = self.make_fixture()
        self.addCleanup(fx["tmp"].cleanup)
        extra = fx["repo"] / fx["auth_root"] / "extra.json"
        extra.write_text("{}\n", encoding="ascii")
        with self.assertRaisesRegex(
            GitProvenanceAuthorizationError, "unexpected untracked repository file"
        ):
            fx["validate"]()

    def test_extra_ignored_inside_current_root_blocks(self):
        fx = self.make_fixture()
        self.addCleanup(fx["tmp"].cleanup)
        extra = fx["repo"] / fx["mig_root"] / "extra.sqlite3"
        extra.write_bytes(b"extra")
        with self.assertRaisesRegex(
            GitProvenanceAuthorizationError, "unexpected ignored operator-runs file"
        ):
            fx["validate"]()

    def test_missing_manifest_file_blocks(self):
        fx = self.make_fixture()
        self.addCleanup(fx["tmp"].cleanup)
        path = fx["repo"] / fx["files"][-1]["path"]
        path.unlink()
        with self.assertRaisesRegex(
            GitProvenanceAuthorizationError, "missing or not a regular file"
        ):
            fx["validate"]()

    def test_modified_tracked_history_blocks_clean_tree(self):
        fx = self.make_fixture()
        self.addCleanup(fx["tmp"].cleanup)
        path = fx["repo"] / sorted(fx["historical"])[0]
        path.write_text("changed\n", encoding="ascii")
        with self.assertRaisesRegex(
            GitProvenanceAuthorizationError, "unstaged changes"
        ):
            fx["validate"]()

    def test_missing_tracked_history_report_blocks(self):
        fx = self.make_fixture()
        self.addCleanup(fx["tmp"].cleanup)
        real_run = subprocess.run
        ghost = "operator-runs/historical/ghost.json"

        def runner(args, **kwargs):
            arguments = args[1:]
            if arguments[:5] == [
                "ls-tree", "-r", "--name-only", "-z", "HEAD"
            ]:
                output = "\0".join([*sorted(fx["historical"]), ghost]) + "\0"
                return subprocess.CompletedProcess(args, 0, stdout=output, stderr="")
            return real_run(args, **kwargs)

        with self.assertRaisesRegex(
            GitProvenanceAuthorizationError,
            "tracked historical operator-runs path is absent",
        ):
            fx["validate"](runner=runner)

    def test_symlink_file_anywhere_under_operator_runs_blocks(self):
        fx = self.make_fixture()
        self.addCleanup(fx["tmp"].cleanup)
        outside = Path(fx["tmp"].name) / "outside.txt"
        outside.write_text("outside", encoding="ascii")
        link = fx["repo"] / "operator-runs/historical-link"
        os.symlink(outside, link)
        with self.assertRaisesRegex(
            GitProvenanceAuthorizationError, "inventory contains a symlink"
        ):
            fx["validate"]()

    def test_symlink_directory_anywhere_under_operator_runs_blocks(self):
        fx = self.make_fixture()
        self.addCleanup(fx["tmp"].cleanup)
        outside = Path(fx["tmp"].name) / "outside-dir"
        outside.mkdir()
        (outside / "secret").write_text("secret", encoding="ascii")
        link = fx["repo"] / "operator-runs/historical-dir-link"
        os.symlink(outside, link)
        with self.assertRaisesRegex(
            GitProvenanceAuthorizationError, "inventory contains a symlink"
        ):
            fx["validate"]()

    def test_non_regular_entry_blocks_when_fifo_supported(self):
        if not hasattr(os, "mkfifo"):
            self.skipTest("FIFO creation is unavailable")
        fx = self.make_fixture()
        self.addCleanup(fx["tmp"].cleanup)
        fifo = fx["repo"] / "operator-runs/historical.fifo"
        os.mkfifo(fifo)
        with self.assertRaisesRegex(
            GitProvenanceAuthorizationError, "non-regular entry"
        ):
            fx["validate"]()

    def test_duplicate_tracked_git_output_blocks(self):
        fx = self.make_fixture()
        self.addCleanup(fx["tmp"].cleanup)
        real_run = subprocess.run
        repeated = sorted(fx["historical"])[0]

        def runner(args, **kwargs):
            arguments = args[1:]
            if arguments[:5] == [
                "ls-tree", "-r", "--name-only", "-z", "HEAD"
            ]:
                output = "\0".join([*sorted(fx["historical"]), repeated]) + "\0"
                return subprocess.CompletedProcess(args, 0, stdout=output, stderr="")
            return real_run(args, **kwargs)

        with self.assertRaisesRegex(
            GitProvenanceAuthorizationError, "duplicate paths"
        ):
            fx["validate"](runner=runner)

    def test_tracked_visible_overlap_blocks(self):
        fx = self.make_fixture()
        self.addCleanup(fx["tmp"].cleanup)
        real_run = subprocess.run
        visible_manifest = fx["files"][0]["path"]

        def runner(args, **kwargs):
            arguments = args[1:]
            if arguments[:5] == [
                "ls-tree", "-r", "--name-only", "-z", "HEAD"
            ]:
                output = "\0".join(
                    [*sorted(fx["historical"]), visible_manifest]
                ) + "\0"
                return subprocess.CompletedProcess(args, 0, stdout=output, stderr="")
            return real_run(args, **kwargs)

        with self.assertRaisesRegex(
            GitProvenanceAuthorizationError, "classifications overlap"
        ):
            fx["validate"](runner=runner)

    def test_visible_extra_elsewhere_in_repository_blocks(self):
        fx = self.make_fixture()
        self.addCleanup(fx["tmp"].cleanup)
        (fx["repo"] / "stray.txt").write_text("stray\n", encoding="ascii")
        with self.assertRaisesRegex(
            GitProvenanceAuthorizationError, "unexpected untracked repository file"
        ):
            fx["validate"]()

    def test_unrelated_ignored_outside_operator_runs_is_not_authorized(self):
        fx = self.make_fixture()
        self.addCleanup(fx["tmp"].cleanup)
        (fx["repo"] / "local.sqlite3").write_bytes(b"local")
        result = fx["validate"]()
        self.assertNotIn("local.sqlite3", result.allowed_untracked_paths)

    def test_validation_performs_no_network(self):
        fx = self.make_fixture()
        self.addCleanup(fx["tmp"].cleanup)
        real_socket = socket.socket

        def forbidden(*args, **kwargs):
            raise AssertionError("network access is forbidden")

        socket.socket = forbidden
        try:
            result = fx["validate"]()
        finally:
            socket.socket = real_socket
        self.assertEqual(result.file_count, 19)


if __name__ == "__main__":
    unittest.main()
