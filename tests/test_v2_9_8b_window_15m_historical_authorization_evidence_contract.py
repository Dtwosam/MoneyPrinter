"""Focused disposable proofs for the historical authorization evidence contract.

Uses temporary Git repositories, temporary application roots, and disposable
package files only. Never mutates the authoritative database, never runs the
public PowerShell wrapper, and never contacts providers.
"""

from __future__ import annotations

import copy
import hashlib
import json
import os
import stat
import subprocess
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest import mock

from printer_v1.operator_cli.git_provenance import capture_git_provenance
from printer_v1.operator_cli.git_provenance_authorization_manifest import (
    APPLICATION_MARKER_SCHEMA_VERSION,
    AUTHORIZATION_PACKAGE_KIND,
    AUTHORIZATION_PACKAGE_ROOT,
    DEFAULT_TERMINAL_DISPOSITION,
    HISTORICAL_AUTHORIZATION_EVIDENCE_CLASS,
    MANIFEST_SCHEMA_VERSION,
    MIGRATION_PACKAGE_KIND,
    MIGRATION_PACKAGE_ROOT,
    GitProvenanceAuthorizationError,
    compute_allowed_file_set_sha256,
    enumerate_historical_authorization_evidence,
    extract_approved_historical_authorization_ids,
    validate_git_provenance_authorization,
    validate_git_provenance_manifest_pre_marker,
    validate_prior_authorizations_non_reusable,
)
from printer_v1.operator_cli.window_15m_authorization_preparation import (
    AuthorizationPreparationError,
    prepare_git_provenance_authorization_parity,
)
from printer_v1.operator_cli import window_15m_one_shot_wrapper as wrapper


CURRENT_AUTH = "V2_9_8B_WINDOW_15M_AUTH_CURRENT"
PRIOR_A = "V2_9_8B_WINDOW_15M_AUTH_PRIOR_A"
PRIOR_B = "V2_9_8B_WINDOW_15M_AUTH_PRIOR_B"
MIG_ID = "V2_9_8B_AUTHORITATIVE_MIG050_HIST_TEST"
UNLISTED = "V2_9_8B_WINDOW_15M_AUTH_UNLISTED_SAFE"


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _sha_file(path: Path) -> str:
    return _sha(path.read_bytes())


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


class HistoricalContractFixture:
    def __init__(
        self,
        *,
        prior_ids: list[str] | None = None,
        multi_file_prior: bool = False,
        tracked_prior_files: list[str] | None = None,
    ):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name).resolve()
        self.repo = self.root / "repo"
        self.external = self.root / "external"
        self.app = self.root / "applications"
        self.repo.mkdir()
        self.external.mkdir()
        self.app.mkdir()
        self.prior_ids = list(prior_ids if prior_ids is not None else [PRIOR_A])
        self.multi_file_prior = multi_file_prior
        self.tracked_prior_files = list(tracked_prior_files or [])
        self._git("init")
        self._git("config", "user.email", "hist-tests@example.invalid")
        self._git("config", "user.name", "Historical Tests")
        (self.repo / ".gitignore").write_text("*.sqlite3\n.venv/\n", encoding="utf-8")
        (self.repo / "tracked.txt").write_text("clean\n", encoding="utf-8")
        # Optional tracked historical files under approved prior packages.
        for relative in self.tracked_prior_files:
            path = self.repo / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text("tracked-prior\n", encoding="utf-8")
        self._git("add", ".")
        self._git("commit", "-m", "baseline")
        self.branch = self._git("rev-parse", "--abbrev-ref", "HEAD").stdout.strip()
        self.head = self._git("rev-parse", "HEAD").stdout.strip().lower()

        self.migration_root = (
            self.repo / "operator-runs/v2-9-8b-authoritative-mig050" / MIG_ID
        )
        self.auth_root = (
            self.repo
            / "operator-runs/v2-9-8b-window-15m-final-authorization"
            / CURRENT_AUTH
        )
        self.migration_root.mkdir(parents=True)
        self.auth_root.mkdir(parents=True)
        (self.migration_root / "preflight.json").write_text(
            '{"kind":"mig"}\n', encoding="utf-8"
        )
        (self.migration_root / "backup.sqlite3").write_bytes(b"SQLITE")
        for index in range(2):
            (self.auth_root / f"evidence-{index}.json").write_text(
                json.dumps({"e": index}) + "\n", encoding="utf-8"
            )
        self.authorization_path = self.auth_root / "final_authorization.json"
        self.rewrite_authorization(prior_ids=self.prior_ids)

        for prior in self.prior_ids:
            package = (
                self.repo
                / "operator-runs/v2-9-8b-window-15m-final-authorization"
                / prior
            )
            package.mkdir(parents=True, exist_ok=True)
            (package / "final_authorization.json").write_text(
                json.dumps({"authorization_id": prior, "historical": True}) + "\n",
                encoding="utf-8",
            )
            if self.multi_file_prior:
                (package / "report.json").write_text(
                    json.dumps({"report": prior}) + "\n", encoding="utf-8"
                )
                (package / "sidecar.sha256").write_text("deadbeef\n", encoding="utf-8")

        # Disposable venv for wrapper tests that reach apply_authorization_once.
        venv = self.repo / ".venv"
        bindir = venv / "bin"
        bindir.mkdir(parents=True)
        (venv / "pyvenv.cfg").write_text("home = /usr/bin\n", encoding="utf-8")
        base = self.root / "base-python"
        base.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
        base.chmod(0o755)
        entry = bindir / "python"
        os.symlink(base, entry)
        self.venv_python = entry

    def _git(self, *args):
        return subprocess.run(
            ["git", *args],
            cwd=self.repo,
            capture_output=True,
            text=True,
            check=True,
        )

    def rewrite_authorization(self, *, prior_ids: list[str]):
        issued = datetime.now(timezone.utc)
        self.branch = self._git("rev-parse", "--abbrev-ref", "HEAD").stdout.strip()
        self.head = self._git("rev-parse", "HEAD").stdout.strip().lower()
        payload = {
            "authorization_id": CURRENT_AUTH,
            "migration_execution_id": MIG_ID,
            "verdict": "V2_9_8B_WINDOW_15M_HIST_TEST_PASS",
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
                "path": "/tmp/testonly-printer-v1-hist.sqlite3",
                "sha256": "d" * 64,
                "size": 1,
                "inode": 1,
                "mtime_ns": 1,
                "migration_count": 52,
                "migration_head": "052_memory_observation_eligibility_layers.sql",
            },
            "prior_authorizations_non_reusable": sorted(prior_ids),
        }
        self.authorization_path.write_text(
            json.dumps(payload, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        self.authorization_sha256 = _sha_file(self.authorization_path)
        self.prior_ids = list(sorted(prior_ids))

    def build_manifest(self, *, created_at="2026-08-06T12:00:00+00:00"):
        return wrapper.build_manifest_bytes(
            repository_root=self.repo,
            authorization_file=self.authorization_path,
            authorization_sha256=self.authorization_sha256,
            created_at=created_at,
        )

    def write_external_manifest(self, payload: dict | None = None):
        if payload is None:
            payload, data = self.build_manifest()
        else:
            data = (
                json.dumps(
                    payload,
                    indent=2,
                    sort_keys=True,
                    ensure_ascii=True,
                    allow_nan=False,
                )
                + "\n"
            ).encode("utf-8")
        path = self.external / "git-provenance-manifest.json"
        path.write_bytes(data)
        return payload, path, _sha(data)

    def close(self):
        self.tmp.cleanup()


class TrustRootValidationTests(unittest.TestCase):
    def test_empty_array_is_lawful(self):
        self.assertEqual(
            validate_prior_authorizations_non_reusable(
                [], current_authorization_id=CURRENT_AUTH
            ),
            (),
        )

    def test_current_id_in_prior_blocks(self):
        with self.assertRaises(GitProvenanceAuthorizationError):
            validate_prior_authorizations_non_reusable(
                [CURRENT_AUTH], current_authorization_id=CURRENT_AUTH
            )

    def test_duplicate_ids_block(self):
        with self.assertRaises(GitProvenanceAuthorizationError):
            validate_prior_authorizations_non_reusable(
                [PRIOR_A, PRIOR_A], current_authorization_id=CURRENT_AUTH
            )

    def test_unsorted_ids_block(self):
        with self.assertRaises(GitProvenanceAuthorizationError):
            validate_prior_authorizations_non_reusable(
                [PRIOR_B, PRIOR_A], current_authorization_id=CURRENT_AUTH
            )

    def test_malformed_and_path_like_ids_block(self):
        for bad in ["", "bad id", "../escape", "a/b", "star*", "quest?", "brack["]:
            with self.assertRaises(GitProvenanceAuthorizationError):
                validate_prior_authorizations_non_reusable(
                    [bad], current_authorization_id=CURRENT_AUTH
                )


class HistoricalEvidenceContractTests(unittest.TestCase):
    def setUp(self):
        self.fx = HistoricalContractFixture(prior_ids=[PRIOR_A], multi_file_prior=True)

    def tearDown(self):
        self.fx.close()

    def _apply(self, **overrides):
        """Apply against disposable roots with non-consuming gates stubbed.

        Staging, marker, builder, and pre-marker validation remain real.
        """
        params = dict(
            authorization_file=self.fx.authorization_path,
            authorization_sha256=self.fx.authorization_sha256,
            operator_approved=True,
            repository_root=self.fx.repo,
            application_root=self.fx.app,
            python_executable=self.fx.venv_python,
            migration_ledger_guard=lambda **kwargs: mock.Mock(),
            process_launcher=lambda **kwargs: {"returncode": 0, "pid": 1},
            created_at="2026-08-06T12:00:00+00:00",
            consumed_at="2026-08-06T12:01:00+00:00",
        )
        params.update(overrides)
        with mock.patch(
            "printer_v1.operator_cli.window_15m_one_shot_wrapper.validate_window_15m_source_configuration"
        ), mock.patch(
            "printer_v1.operator_cli.window_15m_concrete_composition.run_window_15m_concrete_composition_preflight"
        ):
            return wrapper.apply_authorization_once(**params)

    def test_01_one_approved_prior_untracked_package_passes(self):
        payload, path, digest = self.fx.write_external_manifest()
        prepared = validate_git_provenance_manifest_pre_marker(
            repository_root=self.fx.repo,
            manifest_path=str(path),
            manifest_sha256=digest,
        )
        hist_paths = {
            item["path"] for item in payload["historical_authorization_evidence"]
        }
        self.assertTrue(hist_paths)
        self.assertTrue(
            all(PRIOR_A in path for path in hist_paths)
        )
        self.assertEqual(
            set(prepared.allowed_untracked_paths),
            {item["path"] for item in payload["files"]} | hist_paths,
        )
        self.assertEqual(
            prepared.file_count,
            len(payload["files"]) + len(payload["historical_authorization_evidence"]),
        )

    def test_02_multiple_approved_historical_ids_pass(self):
        self.fx.close()
        self.fx = HistoricalContractFixture(
            prior_ids=[PRIOR_A, PRIOR_B], multi_file_prior=True
        )
        payload, path, digest = self.fx.write_external_manifest()
        prepared = validate_git_provenance_manifest_pre_marker(
            repository_root=self.fx.repo,
            manifest_path=str(path),
            manifest_sha256=digest,
        )
        ids = {
            item["authorization_id"]
            for item in payload["historical_authorization_evidence"]
        }
        self.assertEqual(ids, {PRIOR_A, PRIOR_B})
        self.assertGreaterEqual(prepared.file_count, len(payload["files"]) + 4)

    def test_03_multi_file_historical_emits_every_untracked_file(self):
        payload, _ = self.fx.build_manifest()
        hist = payload["historical_authorization_evidence"]
        package = (
            self.fx.repo
            / "operator-runs/v2-9-8b-window-15m-final-authorization"
            / PRIOR_A
        )
        untracked = {
            path.relative_to(self.fx.repo).as_posix()
            for path in package.rglob("*")
            if path.is_file()
        }
        self.assertEqual({item["path"] for item in hist}, untracked)
        self.assertEqual(len(hist), 3)

    def test_04_omitting_one_historical_file_blocks(self):
        payload, _ = self.fx.build_manifest()
        payload = copy.deepcopy(payload)
        omitted = payload["historical_authorization_evidence"].pop()
        payload["historical_authorization_evidence"].sort(key=lambda i: i["path"])
        _, path, digest = self.fx.write_external_manifest(payload)
        with self.assertRaises(GitProvenanceAuthorizationError):
            validate_git_provenance_manifest_pre_marker(
                repository_root=self.fx.repo,
                manifest_path=str(path),
                manifest_sha256=digest,
            )
        self.assertTrue(omitted["path"].endswith("sidecar.sha256") or PRIOR_A in omitted["path"])

    def test_05_unlisted_random_package_directory_blocks(self):
        random_dir = (
            self.fx.repo
            / "operator-runs/v2-9-8b-window-15m-final-authorization"
            / "random-residue-package"
        )
        random_dir.mkdir(parents=True)
        (random_dir / "x.json").write_text("{}\n", encoding="utf-8")
        with self.assertRaises(GitProvenanceAuthorizationError):
            self.fx.build_manifest()

    def test_06_safe_looking_unlisted_auth_directory_blocks(self):
        package = (
            self.fx.repo
            / "operator-runs/v2-9-8b-window-15m-final-authorization"
            / UNLISTED
        )
        package.mkdir(parents=True)
        (package / "final_authorization.json").write_text("{}\n", encoding="utf-8")
        with self.assertRaises(GitProvenanceAuthorizationError):
            self.fx.build_manifest()

    def test_07_unlisted_package_added_before_build_is_not_trusted(self):
        package = (
            self.fx.repo
            / "operator-runs/v2-9-8b-window-15m-final-authorization"
            / UNLISTED
        )
        package.mkdir(parents=True)
        (package / "surprise.json").write_text('{"no":"trust"}\n', encoding="utf-8")
        with self.assertRaises(GitProvenanceAuthorizationError) as ctx:
            wrapper.build_manifest_bytes(
                repository_root=self.fx.repo,
                authorization_file=self.fx.authorization_path,
                authorization_sha256=self.fx.authorization_sha256,
                created_at="2026-08-06T12:00:00+00:00",
            )
        self.assertIn("unapproved historical authorization package", str(ctx.exception))

    def test_08_current_id_in_prior_field_blocks(self):
        raw = json.loads(self.fx.authorization_path.read_text(encoding="utf-8"))
        raw["prior_authorizations_non_reusable"] = [CURRENT_AUTH]
        self.fx.authorization_path.write_text(
            json.dumps(raw, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )
        self.fx.authorization_sha256 = _sha_file(self.fx.authorization_path)
        with self.assertRaises(GitProvenanceAuthorizationError):
            self.fx.build_manifest()

    def test_09_malformed_duplicate_unsorted_priors_block(self):
        for value in (
            "not-an-array",
            [PRIOR_A, PRIOR_A],
            [PRIOR_B, PRIOR_A],
            [""],
        ):
            raw = json.loads(self.fx.authorization_path.read_text(encoding="utf-8"))
            raw["prior_authorizations_non_reusable"] = value
            self.fx.authorization_path.write_text(
                json.dumps(raw, indent=2, sort_keys=True) + "\n", encoding="utf-8"
            )
            self.fx.authorization_sha256 = _sha_file(self.fx.authorization_path)
            with self.assertRaises(
                (wrapper.OneShotWrapperError, GitProvenanceAuthorizationError)
            ):
                self.fx.build_manifest()

    def test_10_empty_approved_set_passes_without_historical_files(self):
        self.fx.close()
        self.fx = HistoricalContractFixture(prior_ids=[])
        # No prior packages on disk.
        payload, path, digest = self.fx.write_external_manifest()
        self.assertEqual(payload["historical_authorization_evidence"], [])
        prepared = validate_git_provenance_manifest_pre_marker(
            repository_root=self.fx.repo,
            manifest_path=str(path),
            manifest_sha256=digest,
        )
        self.assertEqual(prepared.file_count, len(payload["files"]))

    def test_11_approved_absent_or_empty_package_does_not_invent_records(self):
        self.fx.close()
        self.fx = HistoricalContractFixture(prior_ids=[PRIOR_A])
        # Remove the package directory entirely.
        package = (
            self.fx.repo
            / "operator-runs/v2-9-8b-window-15m-final-authorization"
            / PRIOR_A
        )
        for child in package.rglob("*"):
            if child.is_file():
                child.unlink()
        package.rmdir()
        payload, path, digest = self.fx.write_external_manifest()
        self.assertEqual(payload["historical_authorization_evidence"], [])
        validate_git_provenance_manifest_pre_marker(
            repository_root=self.fx.repo,
            manifest_path=str(path),
            manifest_sha256=digest,
        )

    def test_12_approved_tracked_package_stays_in_T_not_H(self):
        relative = (
            f"{AUTHORIZATION_PACKAGE_ROOT}/{PRIOR_A}/final_authorization.json"
        )
        self.fx.close()
        # Commit the prior package fully into T; do not create untracked prior files.
        self.fx = HistoricalContractFixture(
            prior_ids=[],
            multi_file_prior=False,
            tracked_prior_files=[relative],
        )
        self.fx.rewrite_authorization(prior_ids=[PRIOR_A])
        payload, path, digest = self.fx.write_external_manifest()
        self.assertEqual(payload["historical_authorization_evidence"], [])
        prepared = validate_git_provenance_manifest_pre_marker(
            repository_root=self.fx.repo,
            manifest_path=str(path),
            manifest_sha256=digest,
        )
        self.assertNotIn(relative, prepared.allowed_untracked_paths)

    def test_13_mixed_tracked_and_untracked_split_exactly(self):
        tracked_rel = f"{AUTHORIZATION_PACKAGE_ROOT}/{PRIOR_A}/tracked.json"
        self.fx.close()
        self.fx = HistoricalContractFixture(
            prior_ids=[PRIOR_A],
            multi_file_prior=True,
            tracked_prior_files=[tracked_rel],
        )
        payload, path, digest = self.fx.write_external_manifest()
        hist_paths = {
            item["path"] for item in payload["historical_authorization_evidence"]
        }
        self.assertNotIn(tracked_rel, hist_paths)
        self.assertTrue(any(PRIOR_A in p for p in hist_paths))
        prepared = validate_git_provenance_manifest_pre_marker(
            repository_root=self.fx.repo,
            manifest_path=str(path),
            manifest_sha256=digest,
        )
        self.assertNotIn(tracked_rel, prepared.allowed_untracked_paths)
        self.assertTrue(hist_paths.issubset(set(prepared.allowed_untracked_paths)))

    def test_14_unknown_altered_missing_additional_historical_block(self):
        payload, path, digest = self.fx.write_external_manifest()
        # Altered file on disk vs H.
        target = (
            self.fx.repo
            / "operator-runs/v2-9-8b-window-15m-final-authorization"
            / PRIOR_A
            / "final_authorization.json"
        )
        target.write_text('{"altered":true}\n', encoding="utf-8")
        with self.assertRaises(GitProvenanceAuthorizationError):
            validate_git_provenance_manifest_pre_marker(
                repository_root=self.fx.repo,
                manifest_path=str(path),
                manifest_sha256=digest,
            )
        # Restore and test missing.
        self.fx.close()
        self.fx = HistoricalContractFixture(prior_ids=[PRIOR_A], multi_file_prior=True)
        payload, path, digest = self.fx.write_external_manifest()
        target = (
            self.fx.repo
            / "operator-runs/v2-9-8b-window-15m-final-authorization"
            / PRIOR_A
            / "report.json"
        )
        target.unlink()
        with self.assertRaises(GitProvenanceAuthorizationError):
            validate_git_provenance_manifest_pre_marker(
                repository_root=self.fx.repo,
                manifest_path=str(path),
                manifest_sha256=digest,
            )
        # Additional file after build.
        self.fx.close()
        self.fx = HistoricalContractFixture(prior_ids=[PRIOR_A], multi_file_prior=True)
        payload, path, digest = self.fx.write_external_manifest()
        extra = (
            self.fx.repo
            / "operator-runs/v2-9-8b-window-15m-final-authorization"
            / PRIOR_A
            / "extra-after-build.json"
        )
        extra.write_text("{}\n", encoding="utf-8")
        with self.assertRaises(GitProvenanceAuthorizationError):
            validate_git_provenance_manifest_pre_marker(
                repository_root=self.fx.repo,
                manifest_path=str(path),
                manifest_sha256=digest,
            )

    def test_15_historical_path_outside_authorization_root_blocks(self):
        payload, _ = self.fx.build_manifest()
        payload = copy.deepcopy(payload)
        entry = copy.deepcopy(payload["historical_authorization_evidence"][0])
        entry["path"] = "operator-runs/elsewhere/final_authorization.json"
        payload["historical_authorization_evidence"][0] = entry
        payload["historical_authorization_evidence"].sort(key=lambda i: i["path"])
        _, path, digest = self.fx.write_external_manifest(payload)
        with self.assertRaises(GitProvenanceAuthorizationError):
            validate_git_provenance_manifest_pre_marker(
                repository_root=self.fx.repo,
                manifest_path=str(path),
                manifest_sha256=digest,
            )

    def test_16_historical_record_claiming_current_id_blocks(self):
        payload, _ = self.fx.build_manifest()
        payload = copy.deepcopy(payload)
        entry = copy.deepcopy(payload["historical_authorization_evidence"][0])
        entry["authorization_id"] = CURRENT_AUTH
        payload["historical_authorization_evidence"][0] = entry
        _, path, digest = self.fx.write_external_manifest(payload)
        with self.assertRaises(GitProvenanceAuthorizationError):
            validate_git_provenance_manifest_pre_marker(
                repository_root=self.fx.repo,
                manifest_path=str(path),
                manifest_sha256=digest,
            )

    def test_17_duplicate_paths_across_files_and_historical_block(self):
        payload, _ = self.fx.build_manifest()
        payload = copy.deepcopy(payload)
        current_path = payload["files"][0]["path"]
        hist = copy.deepcopy(payload["historical_authorization_evidence"][0])
        hist["path"] = current_path
        # Keep keys valid but path collides.
        hist["authorization_id"] = PRIOR_A
        payload["historical_authorization_evidence"].append(hist)
        payload["historical_authorization_evidence"].sort(key=lambda i: i["path"])
        _, path, digest = self.fx.write_external_manifest(payload)
        with self.assertRaises(GitProvenanceAuthorizationError):
            validate_git_provenance_manifest_pre_marker(
                repository_root=self.fx.repo,
                manifest_path=str(path),
                manifest_sha256=digest,
            )

    def test_18_wildcard_and_directory_only_records_block(self):
        payload, _ = self.fx.build_manifest()
        for bad_path in (
            f"{AUTHORIZATION_PACKAGE_ROOT}/{PRIOR_A}/*",
            f"{AUTHORIZATION_PACKAGE_ROOT}/{PRIOR_A}/",
            f"{AUTHORIZATION_PACKAGE_ROOT}/{PRIOR_A}",
        ):
            bad = copy.deepcopy(payload)
            entry = copy.deepcopy(bad["historical_authorization_evidence"][0])
            entry["path"] = bad_path
            bad["historical_authorization_evidence"] = [entry]
            _, path, digest = self.fx.write_external_manifest(bad)
            with self.assertRaises(GitProvenanceAuthorizationError):
                validate_git_provenance_manifest_pre_marker(
                    repository_root=self.fx.repo,
                    manifest_path=str(path),
                    manifest_sha256=digest,
                )

    def test_19_20_current_only_C_and_complete_inventory_F(self):
        payload, path, digest = self.fx.write_external_manifest()
        prepared = validate_git_provenance_manifest_pre_marker(
            repository_root=self.fx.repo,
            manifest_path=str(path),
            manifest_sha256=digest,
        )
        m = {item["path"] for item in payload["files"]}
        h = {item["path"] for item in payload["historical_authorization_evidence"]}
        self.assertTrue(m.isdisjoint(h))
        self.assertEqual(set(prepared.allowed_untracked_paths), m | h)

    def test_21_22_23_allowlist_file_count_and_capture(self):
        payload, path, digest = self.fx.write_external_manifest()
        prepared = validate_git_provenance_manifest_pre_marker(
            repository_root=self.fx.repo,
            manifest_path=str(path),
            manifest_sha256=digest,
        )
        expected = tuple(
            sorted(
                {item["path"] for item in payload["files"]}
                | {
                    item["path"]
                    for item in payload["historical_authorization_evidence"]
                }
            )
        )
        self.assertEqual(prepared.allowed_untracked_paths, expected)
        self.assertEqual(prepared.file_count, len(expected))
        clean = capture_git_provenance(
            self.fx.repo,
            allowed_untracked_paths=prepared.allowed_untracked_paths,
        )
        self.assertFalse(clean["git_untracked_present"])
        (self.fx.repo / "extra-surprise.txt").write_text("no\n", encoding="utf-8")
        dirty = capture_git_provenance(
            self.fx.repo,
            allowed_untracked_paths=prepared.allowed_untracked_paths,
        )
        self.assertTrue(dirty["git_untracked_present"])

    def test_24_manifest_and_allowlist_digests_are_deterministic(self):
        first_payload, first_bytes = self.fx.build_manifest(
            created_at="2026-08-06T12:00:00+00:00"
        )
        second_payload, second_bytes = self.fx.build_manifest(
            created_at="2026-08-06T12:00:00+00:00"
        )
        self.assertEqual(first_bytes, second_bytes)
        self.assertEqual(
            compute_allowed_file_set_sha256(_digest_records(first_payload)),
            compute_allowed_file_set_sha256(_digest_records(second_payload)),
        )
        self.assertEqual(
            compute_allowed_file_set_sha256(_digest_records(first_payload)),
            compute_allowed_file_set_sha256(
                list(reversed(_digest_records(first_payload)))
            ),
        )

    def test_25_26_preparation_parity_matches_wrapper_and_creates_no_marker(self):
        payload, path, digest = self.fx.write_external_manifest()
        prepared = validate_git_provenance_manifest_pre_marker(
            repository_root=self.fx.repo,
            manifest_path=str(path),
            manifest_sha256=digest,
        )
        summary = prepare_git_provenance_authorization_parity(
            repository_root=self.fx.repo,
            authorization_file=self.fx.authorization_path,
            authorization_sha256=self.fx.authorization_sha256,
            created_at="2026-08-06T12:00:00+00:00",
            application_root=self.fx.app,
            temporary_parent=self.fx.external,
        )
        self.assertEqual(summary["manifest_sha256"], prepared.manifest_sha256)
        self.assertEqual(
            summary["allowed_file_set_sha256"], prepared.allowed_file_set_sha256
        )
        self.assertEqual(summary["status"], "inventory_pre_marker_parity_PASS")
        self.assertFalse(summary["full_apply_readiness_PASS"])
        self.assertFalse(summary["marker_created"])
        self.assertFalse(summary["canonical_application_directory_created"])
        self.assertFalse(summary["child_launched"])
        self.assertFalse((self.fx.app / CURRENT_AUTH).exists())
        # Prep temp dir must be gone.
        self.assertEqual(list(self.fx.external.iterdir()), [path])

    def test_27_pre_marker_failure_leaves_no_marker_and_no_child(self):
        (self.fx.repo / "extra.txt").write_text("extra\n", encoding="utf-8")
        calls = []

        def launcher(**kwargs):
            calls.append(kwargs)
            return {"returncode": 0, "pid": 1}

        with self.assertRaises(
            (GitProvenanceAuthorizationError, wrapper.OneShotWrapperError)
        ):
            self._apply(process_launcher=launcher)
        self.assertEqual(calls, [])
        self.assertFalse((self.fx.app / CURRENT_AUTH / "application-marker.json").exists())

    def test_28_29_staging_cleanup_on_build_and_pre_marker_failure(self):
        # Pre-marker validation failure cleans exact staging.
        (self.fx.repo / "extra.txt").write_text("extra\n", encoding="utf-8")
        with self.assertRaises(
            (GitProvenanceAuthorizationError, wrapper.OneShotWrapperError)
        ):
            self._apply()
        staging = self.fx.app / ".staging"
        if staging.exists():
            remaining = [p for p in staging.rglob("*") if p.is_file()]
            self.assertEqual(remaining, [])

    def test_30_unexpected_staging_entry_prevents_cleanup(self):
        observed = {}

        def validator(**kwargs):
            manifest_path = Path(kwargs["manifest_path"])
            staging_dir = manifest_path.parent
            (staging_dir / "stray.txt").write_text("keep\n", encoding="utf-8")
            observed["staging"] = staging_dir
            raise GitProvenanceAuthorizationError("forced pre-marker block")

        with self.assertRaises(GitProvenanceAuthorizationError) as ctx:
            self._apply(pre_marker_validator=validator)
        exc = ctx.exception
        # Original exception type and message remain controlling.
        self.assertEqual(type(exc).__name__, "GitProvenanceAuthorizationError")
        self.assertEqual(str(exc), "forced pre-marker block")
        self.assertIn(
            "unexpected staging entries",
            getattr(exc, "secondary_staging_cleanup_blocker", ""),
        )
        staging_dir = observed["staging"]
        self.assertTrue(staging_dir.is_dir())
        self.assertTrue((staging_dir / "stray.txt").is_file())
        self.assertFalse((self.fx.app / CURRENT_AUTH / "application-marker.json").exists())

    def test_31_32_marker_is_consumption_boundary_and_consumed_non_reusable(self):
        calls = []

        def launcher(**kwargs):
            calls.append(kwargs)
            return {"returncode": 0, "pid": 99}

        result = self._apply(process_launcher=launcher)
        self.assertEqual(len(calls), 1)
        marker = self.fx.app / CURRENT_AUTH / "application-marker.json"
        self.assertTrue(marker.is_file())
        self.assertTrue(result.get("authorization_id") == CURRENT_AUTH or marker.exists())
        with self.assertRaises(wrapper.OneShotWrapperError):
            self._apply(process_launcher=launcher)

    def test_33_exact_head_mismatch_blocks_before_marker(self):
        raw = json.loads(self.fx.authorization_path.read_text(encoding="utf-8"))
        raw["authorized_git"]["head"] = "0" * 40
        self.fx.authorization_path.write_text(
            json.dumps(raw, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )
        self.fx.authorization_sha256 = _sha_file(self.fx.authorization_path)
        with self.assertRaises(
            (GitProvenanceAuthorizationError, wrapper.OneShotWrapperError)
        ):
            self._apply()
        self.assertFalse((self.fx.app / CURRENT_AUTH / "application-marker.json").exists())

    def test_34_manifest_v1_rejected_after_atomic_v2_change(self):
        payload, _ = self.fx.build_manifest()
        payload = copy.deepcopy(payload)
        payload["schema_version"] = "PRINTER_V1_GIT_PROVENANCE_MANIFEST_V1"
        del payload["historical_authorization_evidence"]
        _, path, digest = self.fx.write_external_manifest(payload)
        with self.assertRaises(GitProvenanceAuthorizationError) as ctx:
            validate_git_provenance_manifest_pre_marker(
                repository_root=self.fx.repo,
                manifest_path=str(path),
                manifest_sha256=digest,
            )
        self.assertIn("schema", str(ctx.exception).lower())

    def test_35_marker_v1_remains_accepted(self):
        payload, path, digest = self.fx.write_external_manifest()
        prepared = validate_git_provenance_manifest_pre_marker(
            repository_root=self.fx.repo,
            manifest_path=str(path),
            manifest_sha256=digest,
        )
        marker = {
            "schema_version": APPLICATION_MARKER_SCHEMA_VERSION,
            "authorization_id": CURRENT_AUTH,
            "authorization_consumed_at": "2026-08-06T12:01:00+00:00",
            "authorization_sha256": prepared.authorization_sha256,
            "manifest_sha256": prepared.manifest_sha256,
            "allowed_file_set_sha256": prepared.allowed_file_set_sha256,
            "repository_branch": prepared.repository_branch,
            "repository_head": prepared.repository_head,
            "command": {"mode": "run", "operator_approved": True},
            "allowed_invocation_count": 1,
            "automatic_retry_allowed": False,
            "manual_rerun_allowed": False,
            "resume_allowed": False,
            "restart_allowed": False,
            "successor_allowed": False,
        }
        marker_path = self.fx.external / "application-marker.json"
        marker_bytes = (
            json.dumps(marker, indent=2, sort_keys=True) + "\n"
        ).encode("utf-8")
        marker_path.write_bytes(marker_bytes)
        validated = validate_git_provenance_authorization(
            repository_root=self.fx.repo,
            manifest_path=str(path),
            manifest_sha256=digest,
            marker_path=str(marker_path),
            marker_sha256=_sha(marker_bytes),
        )
        self.assertEqual(validated.authorization_id, CURRENT_AUTH)
        self.assertTrue(validated.authorization_consumed_once)

    def test_36_schema_is_manifest_v2(self):
        self.assertEqual(
            MANIFEST_SCHEMA_VERSION, "PRINTER_V1_GIT_PROVENANCE_MANIFEST_V2"
        )
        self.assertEqual(
            APPLICATION_MARKER_SCHEMA_VERSION, "PRINTER_V1_APPLICATION_MARKER_V1"
        )
        payload, _ = self.fx.build_manifest()
        self.assertEqual(
            payload["schema_version"], "PRINTER_V1_GIT_PROVENANCE_MANIFEST_V2"
        )
        self.assertIn("historical_authorization_evidence", payload)
        for item in payload["historical_authorization_evidence"]:
            self.assertEqual(
                item["evidence_class"], HISTORICAL_AUTHORIZATION_EVIDENCE_CLASS
            )
            self.assertIn(
                item["terminal_disposition"],
                {DEFAULT_TERMINAL_DISPOSITION, "PERMANENTLY_CONSUMED_PRESERVED", "BLOCKED_UNCONSUMED_SUPERSEDED"},
            )


class StagingCleanupUnitTests(unittest.TestCase):
    def test_cleanup_deletes_only_known_regular_manifest(self):
        with tempfile.TemporaryDirectory() as tmp:
            staging = Path(tmp) / "staging"
            staging.mkdir()
            manifest = staging / "git-provenance-manifest.json"
            manifest.write_bytes(b'{"ok":true}\n')
            secondary = wrapper._cleanup_pre_marker_staging(staging)
            self.assertIsNone(secondary)
            self.assertFalse(staging.exists())

    def test_cleanup_refuses_unexpected_entry(self):
        with tempfile.TemporaryDirectory() as tmp:
            staging = Path(tmp) / "staging"
            staging.mkdir()
            (staging / "git-provenance-manifest.json").write_bytes(b"{}\n")
            (staging / "stray.txt").write_text("x\n", encoding="utf-8")
            secondary = wrapper._cleanup_pre_marker_staging(staging)
            self.assertIsNotNone(secondary)
            self.assertIn("unexpected staging entries", secondary)
            self.assertTrue((staging / "stray.txt").is_file())
            self.assertTrue((staging / "git-provenance-manifest.json").is_file())


if __name__ == "__main__":
    unittest.main()
