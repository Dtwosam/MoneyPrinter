"""V2-9.8B WINDOW_15M one-shot wrapper Git-provenance compatibility tests.

Focused, disposable-only coverage for the manifest/marker authorization
validator and its narrow operational preflight integration. Every test uses a
temporary Git repository and disposable external fixtures. No provider, source,
Scheduler, campaign, memory, retrieval, or authoritative-database work occurs.
"""

import copy
import hashlib
import json
import os
import socket
import subprocess
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

from printer_v1.operator_cli.git_provenance import (
    GIT_PROVENANCE_FIELDS,
    capture_git_provenance,
)
from printer_v1.operator_cli.git_provenance_authorization_manifest import (
    APPLICATION_MARKER_SCHEMA_VERSION,
    AUTHORIZATION_PACKAGE_KIND,
    AUTHORIZATION_PACKAGE_ROOT,
    MANIFEST_SCHEMA_VERSION,
    MIGRATION_PACKAGE_KIND,
    MIGRATION_PACKAGE_ROOT,
    GitProvenanceAuthorizationError,
    ValidatedGitProvenanceAuthorization,
    compute_allowed_file_set_sha256,
    validate_git_provenance_authorization,
)
from printer_v1.operator_cli import operational_memory_factory_command as command


AUTH_ID = "V2_9_8B_WINDOW_15M_AUTH_TESTONLY"
MIG_ID = "V2_9_8B_AUTHORITATIVE_MIG050_TESTONLY_abcd1234"


def _sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


class _Fixture:
    """Build a disposable temp repo with valid manifest and marker fixtures."""

    def __init__(self, root: Path):
        self.tmp = root
        self.repo = root / "repository"
        self.external = root / "external-authorizations"
        self.repo.mkdir()
        self.external.mkdir()
        self._git("init")
        self._git("config", "user.email", "printer-tests@example.invalid")
        self._git("config", "user.name", "Printer Tests")
        (self.repo / "tracked.txt").write_text("clean\n", encoding="ascii")
        self._git("add", "tracked.txt")
        self._git("commit", "-m", "fixture")
        self.head = self._git("rev-parse", "HEAD").stdout.strip().lower()
        self.branch = self._git("rev-parse", "--abbrev-ref", "HEAD").stdout.strip()

        self.auth_root = f"{AUTHORIZATION_PACKAGE_ROOT}/{AUTH_ID}"
        self.mig_root = f"{MIGRATION_PACKAGE_ROOT}/{MIG_ID}"

        self.authorization_document = self._build_authorization_document()
        self.files = []  # list of manifest file records
        # WINDOW_15M authorization evidence package.
        self._add_repo_file(
            f"{self.auth_root}/final_authorization.json",
            json.dumps(self.authorization_document, indent=2, sort_keys=True).encode(
                "utf-8"
            ),
            AUTHORIZATION_PACKAGE_KIND,
        )
        self._add_repo_file(
            f"{self.auth_root}/pre_run_evidence.json",
            b'{"kind":"pre_run"}\n',
            AUTHORIZATION_PACKAGE_KIND,
        )
        self._add_repo_file(
            f"{self.auth_root}/application_started.json",
            b'{"kind":"started"}\n',
            AUTHORIZATION_PACKAGE_KIND,
        )
        # Migration-050 evidence package (including a nested subdirectory file).
        self._add_repo_file(
            f"{self.mig_root}/preflight.json",
            b'{"kind":"migration_preflight"}\n',
            MIGRATION_PACKAGE_KIND,
        )
        self._add_repo_file(
            f"{self.mig_root}/verified-backup/printer_v1-pre050.sqlite3",
            b"SQLITE-BACKUP-BYTES",
            MIGRATION_PACKAGE_KIND,
        )

        self.authorization_sha256 = self._repo_file_sha256(
            f"{self.auth_root}/final_authorization.json"
        )
        self.manifest = self._build_manifest()
        self.manifest_path = self.external / "git-provenance-manifest.json"
        manifest_bytes = json.dumps(self.manifest, indent=2, sort_keys=True).encode(
            "utf-8"
        )
        self.manifest_path.write_bytes(manifest_bytes)
        self.manifest_sha256 = _sha256_bytes(manifest_bytes)
        self.file_set_sha256 = compute_allowed_file_set_sha256(self.manifest["files"])

        self.marker = self._build_marker()
        self.marker_path = self.external / "application_started.json"
        marker_bytes = json.dumps(self.marker, indent=2, sort_keys=True).encode(
            "utf-8"
        )
        self.marker_path.write_bytes(marker_bytes)
        self.marker_sha256 = _sha256_bytes(marker_bytes)

    # -- helpers ---------------------------------------------------------
    def _git(self, *arguments):
        return subprocess.run(
            ["git", *arguments],
            cwd=self.repo,
            capture_output=True,
            text=True,
            check=True,
            shell=False,
        )

    def _add_repo_file(self, relative: str, data: bytes, package_kind: str):
        target = self.repo / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)
        self.files.append(
            {
                "path": relative,
                "sha256": _sha256_bytes(data),
                "size": len(data),
                "package_kind": package_kind,
            }
        )

    def _repo_file_sha256(self, relative: str) -> str:
        return _sha256_bytes((self.repo / relative).read_bytes())

    def _build_authorization_document(self) -> dict:
        issued = datetime.now(timezone.utc)
        return {
            "authorization_id": AUTH_ID,
            "verdict": "V2_9_8B_WINDOW_15M_TESTONLY_FINAL_AUTHORIZATION_PASS",
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
        }

    def _build_manifest(self) -> dict:
        return {
            "schema_version": MANIFEST_SCHEMA_VERSION,
            "authorization_id": AUTH_ID,
            "authorization_file": {
                "path": f"{self.auth_root}/final_authorization.json",
                "sha256": self.authorization_sha256,
            },
            "repository": {"branch": self.branch, "head": self.head},
            "authorized_command": {"mode": "run", "operator_approved": True},
            "migration_execution_id": MIG_ID,
            "created_at": datetime(2026, 8, 1, tzinfo=timezone.utc).isoformat(),
            "files": copy.deepcopy(self.files),
        }

    def _build_marker(self) -> dict:
        return {
            "schema_version": APPLICATION_MARKER_SCHEMA_VERSION,
            "authorization_id": AUTH_ID,
            "authorization_consumed_at": datetime(
                2026, 8, 1, 21, tzinfo=timezone.utc
            ).isoformat(),
            "authorization_sha256": self.authorization_sha256,
            "manifest_sha256": self.manifest_sha256,
            "allowed_file_set_sha256": self.file_set_sha256,
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

    def rewrite_manifest(self, manifest: dict) -> None:
        manifest_bytes = json.dumps(manifest, indent=2, sort_keys=True).encode("utf-8")
        self.manifest_path.write_bytes(manifest_bytes)
        self.manifest_sha256 = _sha256_bytes(manifest_bytes)

    def rewrite_marker(self, marker: dict) -> None:
        marker_bytes = json.dumps(marker, indent=2, sort_keys=True).encode("utf-8")
        self.marker_path.write_bytes(marker_bytes)
        self.marker_sha256 = _sha256_bytes(marker_bytes)

    def validate(self, **overrides):
        params = dict(
            repository_root=self.repo,
            manifest_path=str(self.manifest_path),
            manifest_sha256=self.manifest_sha256,
            marker_path=str(self.marker_path),
            marker_sha256=self.marker_sha256,
            sidecar_untracked_paths=command.AUTHORITATIVE_SQLITE_RUNTIME_SIDECARS,
        )
        params.update(overrides)
        return validate_git_provenance_authorization(**params)


class GitProvenanceAuthorizationManifestTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.fx = _Fixture(Path(self._tmp.name))

    def tearDown(self):
        self._tmp.cleanup()

    # 1. valid exact manifest and marker pass.
    def test_valid_manifest_and_marker_pass(self):
        result = self.fx.validate()
        self.assertIsInstance(result, ValidatedGitProvenanceAuthorization)
        self.assertEqual(result.authorization_id, AUTH_ID)
        self.assertEqual(result.file_count, len(self.fx.files))
        self.assertEqual(result.manifest_sha256, self.fx.manifest_sha256)
        self.assertEqual(result.marker_sha256, self.fx.marker_sha256)
        self.assertEqual(result.allowed_file_set_sha256, self.fx.file_set_sha256)
        self.assertEqual(
            set(result.allowed_untracked_paths),
            {record["path"] for record in self.fx.files},
        )
        # The validated allowlist makes capture_git_provenance pass cleanly.
        provenance = capture_git_provenance(
            self.fx.repo, allowed_untracked_paths=result.allowed_untracked_paths
        )
        self.assertFalse(provenance["git_untracked_present"])

    # 2. no allowlist still detects repository evidence.
    def test_no_allowlist_detects_repository_evidence(self):
        provenance = capture_git_provenance(self.fx.repo)
        self.assertTrue(provenance["git_untracked_present"])
        self.assertTrue(provenance["git_tracked_tree_clean"])

    # 3. unrelated untracked file blocks.
    def test_unrelated_untracked_file_blocks(self):
        (self.fx.repo / "unrelated.txt").write_text("stray", encoding="ascii")
        with self.assertRaisesRegex(
            GitProvenanceAuthorizationError, "unexpected untracked repository file"
        ):
            self.fx.validate()

    # 4. missing manifest file blocks.
    def test_missing_manifest_file_blocks(self):
        (self.fx.repo / self.fx.mig_root / "preflight.json").unlink()
        with self.assertRaisesRegex(
            GitProvenanceAuthorizationError, "missing or not a regular file"
        ):
            self.fx.validate()

    # 4b. manifest-listed file absent from observed set blocks (extra manifest entry).
    def test_manifest_listed_file_absent_from_observed_blocks(self):
        manifest = copy.deepcopy(self.fx.manifest)
        phantom = f"{self.fx.mig_root}/phantom.json"
        manifest["files"].append(
            {
                "path": phantom,
                "sha256": _sha256_bytes(b"phantom"),
                "size": 7,
                "package_kind": MIGRATION_PACKAGE_KIND,
            }
        )
        self.fx.rewrite_manifest(manifest)
        with self.assertRaises(GitProvenanceAuthorizationError):
            self.fx.validate()

    # 5. changed (hash-mismatched, same-size) file blocks.
    def test_hash_mismatched_file_blocks(self):
        target = self.fx.repo / self.fx.mig_root / "preflight.json"
        original = target.read_bytes()
        target.write_bytes(b"X" * len(original))  # same size, different bytes
        with self.assertRaisesRegex(
            GitProvenanceAuthorizationError, "SHA-256 mismatch"
        ):
            self.fx.validate()

    # 6. size-mismatched file blocks.
    def test_size_mismatched_file_blocks(self):
        manifest = copy.deepcopy(self.fx.manifest)
        manifest["files"][3]["size"] = manifest["files"][3]["size"] + 1
        self.fx.rewrite_manifest(manifest)
        with self.assertRaisesRegex(
            GitProvenanceAuthorizationError, "size mismatch"
        ):
            self.fx.validate()

    # 6b. extra untracked file (observed) not covered by manifest blocks.
    def test_extra_observed_file_blocks(self):
        extra = f"{self.fx.auth_root}/extra_evidence.json"
        (self.fx.repo / extra).write_bytes(b"{}\n")
        with self.assertRaisesRegex(
            GitProvenanceAuthorizationError, "unexpected untracked repository file"
        ):
            self.fx.validate()

    # 7. duplicate path blocks.
    def test_duplicate_path_blocks(self):
        manifest = copy.deepcopy(self.fx.manifest)
        manifest["files"].append(copy.deepcopy(manifest["files"][3]))
        self.fx.rewrite_manifest(manifest)
        with self.assertRaisesRegex(
            GitProvenanceAuthorizationError, "duplicate manifest file path"
        ):
            self.fx.validate()

    # 7b. malformed (absolute / traversal / glob / directory / backslash) paths block.
    def test_malformed_paths_block(self):
        for bad in (
            "/etc/passwd",
            f"{self.fx.mig_root}/../escape.json",
            f"{self.fx.mig_root}/glob*.json",
            f"{self.fx.mig_root}/subdir/",
            f"{self.fx.mig_root}\\preflight.json",
            f"{self.fx.mig_root}/./preflight.json",
        ):
            manifest = copy.deepcopy(self.fx.manifest)
            manifest["files"][3]["path"] = bad
            self.fx.rewrite_manifest(manifest)
            with self.assertRaises(GitProvenanceAuthorizationError):
                self.fx.validate()

    # 7c. out-of-root path (valid form, wrong package location) blocks.
    def test_out_of_root_path_blocks(self):
        manifest = copy.deepcopy(self.fx.manifest)
        manifest["files"][3]["path"] = "operator-runs/elsewhere/preflight.json"
        self.fx.rewrite_manifest(manifest)
        with self.assertRaisesRegex(
            GitProvenanceAuthorizationError, "outside its declared package root"
        ):
            self.fx.validate()

    # 7d. symlink component blocks.
    def test_symlink_component_blocks(self):
        # Replace a real file with a symlink to itself's content elsewhere.
        target = self.fx.repo / self.fx.mig_root / "preflight.json"
        outside = self.fx.tmp / "outside_preflight.json"
        outside.write_bytes(b'{"kind":"migration_preflight"}\n')
        target.unlink()
        os.symlink(outside, target)
        with self.assertRaisesRegex(
            GitProvenanceAuthorizationError, "symlink"
        ):
            self.fx.validate()

    # 8. wrong package kind blocks.
    def test_wrong_package_kind_blocks(self):
        manifest = copy.deepcopy(self.fx.manifest)
        # A migration-package file mislabeled as authorization evidence.
        manifest["files"][3]["package_kind"] = AUTHORIZATION_PACKAGE_KIND
        self.fx.rewrite_manifest(manifest)
        with self.assertRaisesRegex(
            GitProvenanceAuthorizationError, "outside its declared package root"
        ):
            self.fx.validate()

    # 8b. wrong package root (migration id) blocks.
    def test_wrong_migration_execution_id_blocks(self):
        manifest = copy.deepcopy(self.fx.manifest)
        manifest["migration_execution_id"] = "V2_9_8B_AUTHORITATIVE_MIG050_WRONG_0000"
        self.fx.rewrite_manifest(manifest)
        with self.assertRaisesRegex(
            GitProvenanceAuthorizationError, "outside its declared package root"
        ):
            self.fx.validate()

    # 9. wrong authorization ID blocks.
    def test_wrong_authorization_id_blocks(self):
        manifest = copy.deepcopy(self.fx.manifest)
        manifest["authorization_id"] = "V2_9_8B_WINDOW_15M_AUTH_OTHER"
        self.fx.rewrite_manifest(manifest)
        with self.assertRaises(GitProvenanceAuthorizationError):
            self.fx.validate()

    # 10a. wrong branch blocks.
    def test_wrong_branch_blocks(self):
        manifest = copy.deepcopy(self.fx.manifest)
        manifest["repository"]["branch"] = "agent/some-other-branch"
        self.fx.rewrite_manifest(manifest)
        with self.assertRaisesRegex(
            GitProvenanceAuthorizationError, "branch does not match live"
        ):
            self.fx.validate()

    # 10b. wrong HEAD blocks.
    def test_wrong_head_blocks(self):
        manifest = copy.deepcopy(self.fx.manifest)
        manifest["repository"]["head"] = "0" * 40
        self.fx.rewrite_manifest(manifest)
        with self.assertRaisesRegex(
            GitProvenanceAuthorizationError, "HEAD does not match live"
        ):
            self.fx.validate()

    # 11. non-PASS authorization verdict blocks.
    def test_non_pass_verdict_blocks(self):
        document = copy.deepcopy(self.fx.authorization_document)
        document["verdict"] = "V2_9_8B_WINDOW_15M_TESTONLY_FINAL_AUTHORIZATION_BLOCKED"
        self._rewrite_authorization_document(document)
        with self.assertRaisesRegex(
            GitProvenanceAuthorizationError, "verdict is not PASS"
        ):
            self.fx.validate()

    # 12a. wrong command mode in authorization blocks.
    def test_wrong_command_mode_blocks(self):
        document = copy.deepcopy(self.fx.authorization_document)
        document["authorized_command"]["mode"] = "selective-1h-proof"
        self._rewrite_authorization_document(document)
        with self.assertRaisesRegex(
            GitProvenanceAuthorizationError, "command mode must be 'run'"
        ):
            self.fx.validate()

    # 12b. selective-1h authorization blocks.
    def test_selective_1h_authorization_blocks(self):
        document = copy.deepcopy(self.fx.authorization_document)
        document["campaign_policy"]["selective_1h_continuation"] = True
        self._rewrite_authorization_document(document)
        with self.assertRaisesRegex(
            GitProvenanceAuthorizationError, "selective_1h_continuation"
        ):
            self.fx.validate()

    # 12c. non-one invocation count in authorization blocks.
    def test_authorization_invocation_count_blocks(self):
        document = copy.deepcopy(self.fx.authorization_document)
        document["authorized_command"]["allowed_invocation_count"] = 2
        self._rewrite_authorization_document(document)
        with self.assertRaisesRegex(
            GitProvenanceAuthorizationError, "allowed_invocation_count must be exactly 1"
        ):
            self.fx.validate()

    # 12d. a retry/rerun/etc flag true in authorization blocks.
    def test_authorization_flag_true_blocks(self):
        document = copy.deepcopy(self.fx.authorization_document)
        document["authorized_command"]["manual_rerun_allowed"] = True
        self._rewrite_authorization_document(document)
        with self.assertRaisesRegex(
            GitProvenanceAuthorizationError, "manual_rerun_allowed must be exactly false"
        ):
            self.fx.validate()

    # 13. manifest inside the repository blocks.
    def test_manifest_inside_repository_blocks(self):
        inside = self.fx.repo / "inside-manifest.json"
        inside.write_bytes(self.fx.manifest_path.read_bytes())
        with self.assertRaisesRegex(
            GitProvenanceAuthorizationError, "manifest must live outside the repository"
        ):
            self.fx.validate(
                manifest_path=str(inside),
                manifest_sha256=_sha256_bytes(inside.read_bytes()),
            )

    # 13b. marker inside the repository blocks.
    #
    # A marker placed inside the repository is caught fail-closed: it appears as
    # an unexpected untracked file (the untracked-equality gate runs before the
    # marker is resolved). The marker's own outside-repository check shares the
    # exact code path exercised by test_manifest_inside_repository_blocks.
    def test_marker_inside_repository_blocks(self):
        inside = self.fx.repo / "inside-marker.json"
        inside.write_bytes(self.fx.marker_path.read_bytes())
        with self.assertRaises(GitProvenanceAuthorizationError):
            self.fx.validate(
                marker_path=str(inside),
                marker_sha256=_sha256_bytes(inside.read_bytes()),
            )

    # 14a. manifest hash mismatch blocks.
    def test_manifest_hash_mismatch_blocks(self):
        with self.assertRaisesRegex(
            GitProvenanceAuthorizationError, "manifest SHA-256 mismatch"
        ):
            self.fx.validate(manifest_sha256="0" * 64)

    # 14b. marker hash mismatch blocks.
    def test_marker_hash_mismatch_blocks(self):
        with self.assertRaisesRegex(
            GitProvenanceAuthorizationError, "marker SHA-256 mismatch"
        ):
            self.fx.validate(marker_sha256="0" * 64)

    # 14c. marker-to-manifest digest mismatch blocks.
    def test_marker_file_set_digest_mismatch_blocks(self):
        marker = copy.deepcopy(self.fx.marker)
        marker["allowed_file_set_sha256"] = "1" * 64
        self.fx.rewrite_marker(marker)
        with self.assertRaisesRegex(
            GitProvenanceAuthorizationError, "allowed_file_set_sha256 mismatch"
        ):
            self.fx.validate()

    # 14d. marker-to-manifest manifest_sha256 mismatch blocks.
    def test_marker_manifest_sha_mismatch_blocks(self):
        marker = copy.deepcopy(self.fx.marker)
        marker["manifest_sha256"] = "2" * 64
        self.fx.rewrite_marker(marker)
        with self.assertRaisesRegex(
            GitProvenanceAuthorizationError, "manifest_sha256 mismatch"
        ):
            self.fx.validate()

    # 15a. malformed / extra manifest schema keys block.
    def test_extra_manifest_key_blocks(self):
        manifest = copy.deepcopy(self.fx.manifest)
        manifest["unexpected_key"] = "x"
        self.fx.rewrite_manifest(manifest)
        with self.assertRaisesRegex(
            GitProvenanceAuthorizationError, "manifest schema is malformed"
        ):
            self.fx.validate()

    # 15b. extra file-entry key blocks.
    def test_extra_file_entry_key_blocks(self):
        manifest = copy.deepcopy(self.fx.manifest)
        manifest["files"][0]["mode"] = "0644"
        self.fx.rewrite_manifest(manifest)
        with self.assertRaisesRegex(
            GitProvenanceAuthorizationError, "manifest file entry schema is malformed"
        ):
            self.fx.validate()

    # 15c. extra marker schema key blocks.
    def test_extra_marker_key_blocks(self):
        marker = copy.deepcopy(self.fx.marker)
        marker["extra"] = True
        self.fx.rewrite_marker(marker)
        with self.assertRaisesRegex(
            GitProvenanceAuthorizationError, "application marker schema is malformed"
        ):
            self.fx.validate()

    # 15d. duplicate JSON keys in manifest block.
    def test_duplicate_json_keys_block(self):
        self.fx.manifest_path.write_text(
            '{"schema_version":"x","schema_version":"y"}', encoding="utf-8"
        )
        sha = _sha256_bytes(self.fx.manifest_path.read_bytes())
        with self.assertRaisesRegex(
            GitProvenanceAuthorizationError, "duplicate JSON key"
        ):
            self.fx.validate(manifest_sha256=sha)

    # 16a. staged tracked changes block.
    def test_staged_changes_block(self):
        (self.fx.repo / "tracked.txt").write_text("staged\n", encoding="ascii")
        self.fx._git("add", "tracked.txt")
        with self.assertRaisesRegex(
            GitProvenanceAuthorizationError, "staged changes"
        ):
            self.fx.validate()

    # 16b. unstaged tracked changes block.
    def test_unstaged_changes_block(self):
        (self.fx.repo / "tracked.txt").write_text("unstaged\n", encoding="ascii")
        with self.assertRaisesRegex(
            GitProvenanceAuthorizationError, "unstaged changes"
        ):
            self.fx.validate()

    # 17. exact-file-set digest is deterministic and order-independent.
    def test_file_set_digest_is_deterministic(self):
        first = compute_allowed_file_set_sha256(self.fx.manifest["files"])
        reversed_files = list(reversed(self.fx.manifest["files"]))
        second = compute_allowed_file_set_sha256(reversed_files)
        self.assertEqual(first, second)
        self.assertRegex(first, r"^[0-9a-f]{64}$")

    # 18. wrong authorization-file SHA reference blocks.
    def test_authorization_file_sha_mismatch_blocks(self):
        manifest = copy.deepcopy(self.fx.manifest)
        manifest["authorization_file"]["sha256"] = "3" * 64
        self.fx.rewrite_manifest(manifest)
        with self.assertRaises(GitProvenanceAuthorizationError):
            self.fx.validate()

    # 19. marker invocation count / flags enforced.
    def test_marker_flag_true_blocks(self):
        marker = copy.deepcopy(self.fx.marker)
        marker["successor_allowed"] = True
        self.fx.rewrite_marker(marker)
        with self.assertRaisesRegex(
            GitProvenanceAuthorizationError, "successor_allowed must be exactly false"
        ):
            self.fx.validate()

    def _rewrite_authorization_document(self, document: dict) -> None:
        relative = f"{self.fx.auth_root}/final_authorization.json"
        data = json.dumps(document, indent=2, sort_keys=True).encode("utf-8")
        (self.fx.repo / relative).write_bytes(data)
        new_sha = _sha256_bytes(data)
        # Keep the manifest/marker consistent with the new authorization bytes so
        # the test isolates the specific rejected field (not a SHA mismatch).
        manifest = copy.deepcopy(self.fx.manifest)
        manifest["authorization_file"]["sha256"] = new_sha
        for record in manifest["files"]:
            if record["path"] == relative:
                record["sha256"] = new_sha
                record["size"] = len(data)
        self.fx.rewrite_manifest(manifest)
        self.fx.file_set_sha256 = compute_allowed_file_set_sha256(manifest["files"])
        marker = copy.deepcopy(self.fx.marker)
        marker["authorization_sha256"] = new_sha
        marker["manifest_sha256"] = self.fx.manifest_sha256
        marker["allowed_file_set_sha256"] = self.fx.file_set_sha256
        self.fx.rewrite_marker(marker)


class OperationalPreflightIntegrationTests(unittest.TestCase):
    """Narrow env/mode-gate and capture-combination tests (no DB, no network)."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.fx = _Fixture(Path(self._tmp.name))

    def tearDown(self):
        self._tmp.cleanup()

    def _full_env(self) -> dict:
        return {
            "PRINTER_V1_GIT_PROVENANCE_MANIFEST_PATH": str(self.fx.manifest_path),
            "PRINTER_V1_GIT_PROVENANCE_MANIFEST_SHA256": self.fx.manifest_sha256,
            "PRINTER_V1_APPLICATION_MARKER_PATH": str(self.fx.marker_path),
            "PRINTER_V1_APPLICATION_MARKER_SHA256": self.fx.marker_sha256,
        }

    # 15 (task list). Environment variables are all-or-none.
    def test_env_absent_returns_none(self):
        self.assertIsNone(
            command._resolve_git_provenance_authorization("run", environ={})
        )

    def test_partial_env_blocks(self):
        env = self._full_env()
        del env["PRINTER_V1_APPLICATION_MARKER_SHA256"]
        with self.assertRaisesRegex(
            command.OperationalMemoryFactoryError, "all be set together or all be unset"
        ):
            command._resolve_git_provenance_authorization(
                "run", environ=env, repository_root=self.fx.repo
            )

    def test_full_env_valid_resolves(self):
        result = command._resolve_git_provenance_authorization(
            "run", environ=self._full_env(), repository_root=self.fx.repo
        )
        self.assertIsInstance(result, ValidatedGitProvenanceAuthorization)
        self.assertEqual(result.authorization_id, AUTH_ID)

    def test_preflight_only_mode_supported(self):
        result = command._resolve_git_provenance_authorization(
            "preflight-only", environ=self._full_env(), repository_root=self.fx.repo
        )
        self.assertIsInstance(result, ValidatedGitProvenanceAuthorization)

    # 16 (task list). Unsupported modes reject the variables.
    def test_unsupported_modes_reject_env(self):
        for mode in (
            "selective-1h-preflight",
            "selective-1h-proof",
            "discovery-only",
            "status",
            "cooperative-stop",
            "recover-orphan",
            "report-only",
        ):
            with self.assertRaisesRegex(
                command.OperationalMemoryFactoryError, "is not accepted for mode"
            ):
                command._resolve_git_provenance_authorization(
                    mode, environ=self._full_env(), repository_root=self.fx.repo
                )

    def test_resolver_wraps_validation_failure(self):
        env = self._full_env()
        env["PRINTER_V1_GIT_PROVENANCE_MANIFEST_SHA256"] = "0" * 64
        with self.assertRaisesRegex(
            command.OperationalMemoryFactoryError,
            "git provenance manifest authorization rejected",
        ):
            command._resolve_git_provenance_authorization(
                "run", environ=env, repository_root=self.fx.repo
            )

    # Combines validated paths with the fixed sidecar tuple in the capture helper.
    def test_capture_helper_combines_validated_paths(self):
        result = self.fx.validate()
        provenance = command._capture_operational_git_provenance(
            self.fx.repo,
            additional_allowed_untracked_paths=result.allowed_untracked_paths,
        )
        self.assertFalse(provenance["git_untracked_present"])
        self.assertTrue(provenance["git_tracked_tree_clean"])

    def test_capture_helper_still_blocks_unrelated_file(self):
        result = self.fx.validate()
        (self.fx.repo / "stray.txt").write_text("stray", encoding="ascii")
        with self.assertRaisesRegex(
            command.GitProvenanceError, "arbitrary untracked file"
        ):
            command._capture_operational_git_provenance(
                self.fx.repo,
                additional_allowed_untracked_paths=result.allowed_untracked_paths,
            )

    # 14 (task list). Canonical six-field Git-provenance object remains unchanged.
    def test_canonical_six_field_payload_unchanged(self):
        self.assertEqual(len(GIT_PROVENANCE_FIELDS), 6)
        result = self.fx.validate()
        provenance = command._capture_operational_git_provenance(
            self.fx.repo,
            additional_allowed_untracked_paths=result.allowed_untracked_paths,
        )
        self.assertEqual(set(provenance), set(GIT_PROVENANCE_FIELDS))

    # Bounded summary never leaks file names.
    def test_summary_is_bounded(self):
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
        blob = json.dumps(summary)
        for record in self.fx.files:
            self.assertNotIn(record["path"], blob)

    # 17 (task list). No provider / source / Scheduler / campaign / DB / network
    # call occurs during focused validation. Disabling sockets must not affect a
    # successful validation.
    def test_validation_performs_no_network(self):
        real_socket = socket.socket

        def _forbidden(*args, **kwargs):
            raise AssertionError("network access is forbidden during preflight")

        socket.socket = _forbidden
        try:
            result = self.fx.validate()
        finally:
            socket.socket = real_socket
        self.assertEqual(result.authorization_id, AUTH_ID)


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
