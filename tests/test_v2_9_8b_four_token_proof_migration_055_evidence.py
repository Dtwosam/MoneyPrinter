"""Focused contract for narrowly bound migration-055 four-token proof evidence.

Offline only. Every repository/database identity in this file is a disposable
temporary fixture. No authorization is created, no Printer process is started,
no source is called, and no authoritative database is touched.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
import hashlib
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

from printer_v1.operator_cli import git_provenance_authorization_manifest as git_auth
from printer_v1.operator_cli import (
    four_token_proof_one_shot_wrapper as four_token,
)


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


class FourTokenProofFixture:
    """Disposable repository carrying one exact migration-055 proof package."""

    authorization_id = "V2_9_8B_FOUR_TOKEN_AUTH_TESTONLY"
    migration_id = "MIGRATION_055_TESTONLY"

    def __init__(self, *, migration_root: str | None = None) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name).resolve()
        self.repo = self.root / "repo"
        self.external = self.root / "external"
        self.repo.mkdir()
        self.external.mkdir()
        self._git("init")
        self._git("config", "user.email", "tests@example.invalid")
        self._git("config", "user.name", "Four Token Proof Tests")
        (self.repo / ".gitignore").write_text("*.sqlite3\n.venv/\n", encoding="utf-8")
        (self.repo / "tracked.txt").write_text("clean\n", encoding="utf-8")
        self._git("add", ".")
        self._git("commit", "-m", "baseline")
        self.branch = self._git("rev-parse", "--abbrev-ref", "HEAD").stdout.strip()
        self.head = self._git("rev-parse", "HEAD").stdout.strip()

        self.migration_package_root = (
            migration_root or git_auth.MIGRATION_055_PACKAGE_ROOT
        )
        self.migration_root = (
            self.repo / self.migration_package_root / self.migration_id
        )
        self.authorization_root = (
            self.repo
            / git_auth.FOUR_TOKEN_PROOF_AUTHORIZATION_PROFILE.authorization_package_root
            / self.authorization_id
        )
        self.migration_root.mkdir(parents=True)
        self.authorization_root.mkdir(parents=True)
        (self.migration_root / "migration_055_application_result.json").write_text(
            json.dumps({"migration": self.migration_id}) + "\n", encoding="utf-8"
        )
        self.authorization_path = self.authorization_root / "final_authorization.json"
        now = datetime.now(timezone.utc)
        document = four_token.fixture_authorization_document(
            branch=self.branch,
            head=self.head,
            database={
                "path": "/tmp/printer.sqlite3",
                "sha256": "c" * 64,
                "size": 4096,
                "inode": 3,
                "mtime_ns": 5,
                "migration_count": 55,
                "migration_head": (
                    "055_pre_admission_discovery_attempt_ownership.sql"
                ),
            },
            authorization_id=self.authorization_id,
            migration_execution_id=self.migration_id,
            authorized_at=now.isoformat(),
            expires_at=(now + timedelta(hours=12)).isoformat(),
        )
        self.authorization_path.write_text(
            json.dumps(document, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )
        self.authorization_sha256 = _sha(self.authorization_path)

    def _git(self, *args: str):
        return subprocess.run(
            ["git", *args], cwd=self.repo, capture_output=True, text=True, check=True
        )

    def manifest(self):
        payload, data = four_token.build_manifest_bytes(
            repository_root=self.repo,
            authorization_file=self.authorization_path,
            authorization_sha256=self.authorization_sha256,
        )
        path = self.root / "git-provenance-manifest.json"
        path.write_bytes(data)
        return payload, path, hashlib.sha256(data).hexdigest()

    def validate(self):
        _payload, path, digest = self.manifest()
        return git_auth.validate_git_provenance_manifest_pre_marker(
            repository_root=self.repo,
            manifest_path=str(path),
            manifest_sha256=digest,
            profile=git_auth.FOUR_TOKEN_PROOF_AUTHORIZATION_PROFILE,
        )

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


class FourTokenProofMigration055EvidenceTests(unittest.TestCase):
    def test_migration_055_identities_are_distinct_from_migration_050(self) -> None:
        self.assertEqual(
            git_auth.MIGRATION_055_PACKAGE_ROOT,
            "operator-runs/v2-9-8b-migration-055-application",
        )
        self.assertEqual(
            git_auth.MIGRATION_055_PACKAGE_KIND, "MIGRATION_055_EVIDENCE"
        )
        profile = git_auth.FOUR_TOKEN_PROOF_AUTHORIZATION_PROFILE
        self.assertEqual(
            profile.migration_package_root, git_auth.MIGRATION_055_PACKAGE_ROOT
        )
        self.assertEqual(
            profile.migration_package_kind, git_auth.MIGRATION_055_PACKAGE_KIND
        )

    def test_existing_profiles_keep_migration_050_defaults(self) -> None:
        for profile in (
            git_auth.ORDINARY_AUTHORIZATION_PROFILE,
            git_auth.STANDARD_FOUR_HOUR_AUTHORIZATION_PROFILE,
        ):
            with self.subTest(profile=profile.command_mode):
                self.assertEqual(
                    profile.migration_package_root, git_auth.MIGRATION_PACKAGE_ROOT
                )
                self.assertEqual(
                    profile.migration_package_kind, git_auth.MIGRATION_PACKAGE_KIND
                )

    def test_exact_migration_055_package_is_bound_and_accepted(self) -> None:
        fixture = FourTokenProofFixture()
        try:
            payload, _path, _digest = fixture.manifest()
            self.assertEqual(
                payload["schema_version"],
                "PRINTER_V1_GIT_PROVENANCE_MANIFEST_FOUR_TOKEN_PROOF_V1",
            )
            kinds = {item["package_kind"] for item in payload["files"]}
            self.assertEqual(
                kinds,
                {
                    git_auth.MIGRATION_055_PACKAGE_KIND,
                    "FOUR_TOKEN_PROOF_AUTHORIZATION_EVIDENCE",
                },
            )
            migration_files = [
                item
                for item in payload["files"]
                if item["package_kind"] == git_auth.MIGRATION_055_PACKAGE_KIND
            ]
            self.assertEqual(len(migration_files), 1)
            self.assertTrue(
                migration_files[0]["path"].startswith(
                    f"{git_auth.MIGRATION_055_PACKAGE_ROOT}/{fixture.migration_id}/"
                )
            )
            self.assertEqual(
                migration_files[0]["sha256"],
                _sha(
                    fixture.migration_root
                    / "migration_055_application_result.json"
                ),
            )
            prepared = fixture.validate()
            self.assertEqual(prepared.authorization_id, fixture.authorization_id)
            self.assertEqual(prepared.file_count, 2)
        finally:
            fixture.close()

    def test_unrelated_operator_runs_evidence_is_not_trusted(self) -> None:
        fixture = FourTokenProofFixture()
        try:
            stray = (
                fixture.repo
                / git_auth.OPERATOR_RUNS_ROOT
                / "v2-9-8b-unrelated-evidence"
            )
            stray.mkdir(parents=True)
            (stray / "stray.json").write_text("{}\n", encoding="utf-8")
            with self.assertRaises(git_auth.GitProvenanceAuthorizationError):
                fixture.validate()
        finally:
            fixture.close()

    def test_migration_050_root_cannot_supply_four_token_current_evidence(
        self,
    ) -> None:
        fixture = FourTokenProofFixture(
            migration_root=git_auth.MIGRATION_PACKAGE_ROOT
        )
        try:
            # The dedicated wrapper owns the failure; a foreign one-shot error
            # type must never leak out of the four-token authority.
            with self.assertRaises(four_token.FourTokenProofOneShotWrapperError):
                fixture.validate()
        finally:
            fixture.close()


if __name__ == "__main__":  # pragma: no cover - direct invocation guard
    unittest.main()
