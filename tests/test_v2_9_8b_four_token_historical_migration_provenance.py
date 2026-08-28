"""Focused contract for exact four-token historical migration-050 provenance.

Offline only. Every repository, authorization document, migration package and
database identity in this file is a disposable temporary fixture. No real
authorization is prepared or created, no application marker is written, no
Printer runtime is started, no source or RPC is contacted, and no authoritative
database is read or mutated.

The lane under test is the historical migration evidence class ``Hm``:

* ``T``  tracked operator-run history
* ``M``  current manifest evidence (migration 055 + current four-token auth)
* ``Ha`` explicitly approved historical authorization evidence
* ``Hm`` explicitly profile-bound historical migration evidence

``U = M ∪ Ha ∪ Hm`` is the untracked allowlist and ``F = T ∪ M ∪ Ha ∪ Hm`` is
the complete operator-runs inventory. Current-package equality stays ``C == M``.
"""

from __future__ import annotations

import contextlib
from datetime import datetime, timedelta, timezone
import hashlib
import json
import os
from pathlib import Path
import shutil
import stat
import subprocess
import tempfile
import unittest
from unittest import mock

from printer_v1.operator_cli import git_provenance_authorization_manifest as git_auth
from printer_v1.operator_cli.authorization_temporal_validity import (
    AuthorizationTemporalError,
    validate_authorization_temporal_validity,
)
from printer_v1.operator_cli import (
    four_token_proof_one_shot_wrapper as four_token,
)


# The exact preserved historical migration package that blocked the first
# four-token authorization preparation.
HISTORICAL_MIGRATION_ROOT = "operator-runs/v2-9-8b-authoritative-mig050"
HISTORICAL_MIGRATION_EXECUTION_ID = (
    "V2_9_8B_AUTHORITATIVE_MIG050_20260801T202423Z_f697cc0f"
)

MIGRATION_058_ROOT = "operator-runs/v2-9-8b-migration-058-application"
MIGRATION_058_EXECUTION_ID = "MIGRATION_058_20260818T082552Z"
MIGRATION_058_PATHS = frozenset(
    f"{MIGRATION_058_ROOT}/{MIGRATION_058_EXECUTION_ID}/{relative}"
    for relative in (
        ".gitignore",
        "README.md",
        "__pycache__/apply_migration_058.cpython-312.pyc",
        "apply_migration_058.py",
        "authoritative-pre-058.sqlite3",
        "disposable/migration-058-rehearsal.sqlite3",
        "disposable_rehearsal.json",
        "migration_058_application_result.json",
        "post_application_snapshot.json",
        "post_application_verification.json",
        "pre_application_snapshot.json",
    )
)

MIGRATION_061_ROOT = "operator-runs/v2-9-8b-migration-061-application"
MIGRATION_061_EXECUTION_ID = "MIGRATION_061_20260823T200709Z"
MIGRATION_062_ROOT = "operator-runs/v2-9-8b-migration-062-application"
MIGRATION_062_EXECUTION_ID = "MIGRATION_062_20260828T182504Z"

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
FOUR_TOKEN_STANDARD_FOUR_HOUR_AUTHORIZATION_ROOT = (
    "operator-runs/v2-9-8b-four-token-standard-four-hour-final-authorization"
)
EXPIRED_FRESH_AUTHORIZATION_ID = (
    "V2_9_8B_FOUR_TOKEN_STD4H_AUTH_20260823T221645Z_6af1423a"
)
EXPIRED_FRESH_AUTHORIZATION_RELATIVE_PATH = (
    f"{FOUR_TOKEN_STANDARD_FOUR_HOUR_AUTHORIZATION_ROOT}/"
    f"{EXPIRED_FRESH_AUTHORIZATION_ID}/final_authorization.json"
)
EXPIRED_FRESH_AUTHORIZATION_SHA256 = (
    "c0d05a6c9de103e911f00d7f7e471e27d08fa983a57c6de33b6286a55388fb69"
)
CONSUMED_FOUR_TOKEN_STANDARD_FOUR_HOUR_AUTHORIZATION_ID = (
    "V2_9_8B_FOUR_TOKEN_STD4H_AUTH_20260821T153458Z_512f2436"
)
LATEST_CONSUMED_FOUR_TOKEN_STANDARD_FOUR_HOUR_AUTHORIZATION_ID = (
    "V2_9_8B_FOUR_TOKEN_STD4H_AUTH_20260824T123555Z_95dc47dd"
)
SUPERSEDED_UNCONSUMED_FOUR_TOKEN_STANDARD_FOUR_HOUR_AUTHORIZATION_ID = (
    "V2_9_8B_FOUR_TOKEN_STD4H_AUTH_20260824T222638Z_17181afc"
)
NEWER_CONSUMED_FOUR_TOKEN_STANDARD_FOUR_HOUR_AUTHORIZATION_ID = (
    "V2_9_8B_FOUR_TOKEN_STD4H_AUTH_20260825T105852Z_07d92adf"
)
LATEST_HISTORICAL_FOUR_TOKEN_STANDARD_FOUR_HOUR_AUTHORIZATION_IDS = (
    "V2_9_8B_FOUR_TOKEN_STD4H_AUTH_20260825T134723Z_4563a9dd",
    "V2_9_8B_FOUR_TOKEN_STD4H_AUTH_20260826T114542Z_d3bc361a",
    "V2_9_8B_FOUR_TOKEN_STD4H_AUTH_20260826T185611Z_b861fd4c",
    "V2_9_8B_FOUR_TOKEN_STD4H_AUTH_20260826T203834Z_c3063b7c",
    "V2_9_8B_FOUR_TOKEN_STD4H_AUTH_20260827T122355Z_8e43eae7",
)
FUTURE_FOUR_TOKEN_STANDARD_FOUR_HOUR_AUTHORIZATION_ID = (
    "V2_9_8B_FOUR_TOKEN_STD4H_AUTH_FUTURE_TESTONLY"
)

PAIR_READY_ROOT = (
    "operator-runs/v2-9-8b-pair-ready-residual-reconciliation"
)
PAIR_READY_EXECUTION_ID = "RECONCILIATION_20260821T110736Z"
PAIR_READY_PATHS = frozenset(
    f"{PAIR_READY_ROOT}/{PAIR_READY_EXECUTION_ID}/{relative}"
    for relative in (
        "backup_and_disposable_rehearsal.json",
        "post_reconciliation_snapshot.json",
        "pre_reconciliation_snapshot.json",
        "reconcile_pair_ready_residual.py",
        "reconciliation_receipt.json",
    )
)

# Faithful to the preserved package: nested evidence plus ignored database
# artifacts under the same exact execution ID.
_HISTORICAL_MIGRATION_FILES = {
    "application_started.json": '{"execution_id": "mig050"}\n',
    "final_authorization.json": '{"verdict": "HISTORICAL_MIG050_PASS"}\n',
    "post_migration_proof.json": '{"migration_count": 50}\n',
    "preflight.json": '{"preflight": "ok"}\n',
    "disposable-restore/printer_v1-rehearsal.sqlite3": "rehearsal-bytes\n",
    "verified-backup/printer_v1-pre050.sqlite3": "pre050-bytes\n",
}


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _synthetic_completeness_identity(
    *, repo: Path, package_root: str, execution_id: str, evidence_class: str
) -> tuple[int, str]:
    """Derive a synthetic package's OWN immutable completeness identity.

    A disposable fixture never claims the real production package's 12-file
    identity. It declares exactly what its own synthetic tree contains, so the
    completeness law is genuinely exercised rather than bypassed.
    """
    base = repo / package_root / execution_id
    files = [
        {
            "path": item.relative_to(repo).as_posix(),
            "sha256": _sha(item),
            "size": item.stat().st_size,
        }
        for item in sorted(base.rglob("*"))
        if item.is_file() and not item.is_symlink()
    ]
    digest = git_auth.compute_historical_migration_inventory_sha256(
        package_root=package_root,
        execution_id=execution_id,
        evidence_class=evidence_class,
        files=files,
    )
    return len(files), digest


@contextlib.contextmanager
def _patched_four_token_profile(profile):
    """Temporarily scope one fixture profile over both production bindings."""
    with mock.patch.object(
        git_auth, "FOUR_TOKEN_PROOF_AUTHORIZATION_PROFILE", profile
    ), mock.patch.object(
        four_token, "FOUR_TOKEN_PROOF_AUTHORIZATION_PROFILE", profile
    ):
        yield profile


def _replace_historical_migration_packages(profile, packages):
    """Return a fixture-scoped profile differing only in its Hm declarations."""
    return git_auth.GitAuthorizationProfile(
        command_mode=profile.command_mode,
        authorization_package_root=profile.authorization_package_root,
        authorization_package_kind=profile.authorization_package_kind,
        manifest_schema_version=profile.manifest_schema_version,
        historical_authorization_package_roots=(
            profile.historical_authorization_package_roots
        ),
        migration_package_root=profile.migration_package_root,
        migration_package_kind=profile.migration_package_kind,
        historical_migration_packages=packages,
    )


class ExpiredFreshAuthorizationHistoricalAdoptionTests(unittest.TestCase):
    """Read-only production-path proof for the immutable expired package."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.authorization_path = (
            REPOSITORY_ROOT / EXPIRED_FRESH_AUTHORIZATION_RELATIVE_PATH
        )
        cls.authorization_bytes = cls.authorization_path.read_bytes()
        cls.authorization_document = json.loads(cls.authorization_bytes)
        superseded_authorization_path = (
            REPOSITORY_ROOT
            / FOUR_TOKEN_STANDARD_FOUR_HOUR_AUTHORIZATION_ROOT
            / SUPERSEDED_UNCONSUMED_FOUR_TOKEN_STANDARD_FOUR_HOUR_AUTHORIZATION_ID
            / "final_authorization.json"
        )
        superseded_authorization_document = json.loads(
            superseded_authorization_path.read_bytes()
        )
        cls.future_document = {
            "authorization_id": FUTURE_FOUR_TOKEN_STANDARD_FOUR_HOUR_AUTHORIZATION_ID,
            "prior_authorizations_non_reusable": sorted(
                [
                    *superseded_authorization_document[
                        "prior_authorizations_non_reusable"
                    ],
                    SUPERSEDED_UNCONSUMED_FOUR_TOKEN_STANDARD_FOUR_HOUR_AUTHORIZATION_ID,
                    NEWER_CONSUMED_FOUR_TOKEN_STANDARD_FOUR_HOUR_AUTHORIZATION_ID,
                    *LATEST_HISTORICAL_FOUR_TOKEN_STANDARD_FOUR_HOUR_AUTHORIZATION_IDS,
                ]
            ),
        }

    @classmethod
    def _approved_future_ids(cls) -> tuple[str, ...]:
        return git_auth.extract_approved_historical_authorization_ids(
            cls.future_document,
            current_authorization_id=(
                FUTURE_FOUR_TOKEN_STANDARD_FOUR_HOUR_AUTHORIZATION_ID
            ),
        )

    @classmethod
    def _enumerate_real_history(cls) -> tuple[dict[str, object], ...]:
        profile = git_auth.FOUR_TOKEN_STANDARD_FOUR_HOUR_AUTHORIZATION_PROFILE
        return git_auth.enumerate_historical_authorization_evidence(
            repository_root=REPOSITORY_ROOT,
            current_authorization_id=(
                FUTURE_FOUR_TOKEN_STANDARD_FOUR_HOUR_AUTHORIZATION_ID
            ),
            approved_historical_authorization_ids=cls._approved_future_ids(),
            authorization_package_roots=(
                profile.historical_authorization_package_roots
            ),
            current_authorization_package_root=(
                profile.authorization_package_root
            ),
        )

    def test_approved_complete_future_trust_root_emits_exact_expired_package(self) -> None:
        """Break caught: the policy owner omits or misclassifies this package."""
        self.assertEqual(
            self.authorization_document["authorization_id"],
            EXPIRED_FRESH_AUTHORIZATION_ID,
        )
        self.assertEqual(len(self.authorization_bytes), 4218)
        self.assertEqual(
            hashlib.sha256(self.authorization_bytes).hexdigest(),
            EXPIRED_FRESH_AUTHORIZATION_SHA256,
        )
        self.assertEqual(
            stat.S_IMODE(self.authorization_path.stat().st_mode), 0o444
        )

        approved = self._approved_future_ids()
        self.assertEqual(approved, tuple(sorted(approved)))
        self.assertEqual(len(approved), len(set(approved)))
        self.assertIn(EXPIRED_FRESH_AUTHORIZATION_ID, approved)
        self.assertIn(
            LATEST_CONSUMED_FOUR_TOKEN_STANDARD_FOUR_HOUR_AUTHORIZATION_ID,
            approved,
        )
        self.assertIn(
            SUPERSEDED_UNCONSUMED_FOUR_TOKEN_STANDARD_FOUR_HOUR_AUTHORIZATION_ID,
            approved,
        )
        self.assertIn(
            NEWER_CONSUMED_FOUR_TOKEN_STANDARD_FOUR_HOUR_AUTHORIZATION_ID,
            approved,
        )
        self.assertTrue(
            set(
                self.authorization_document[
                    "prior_authorizations_non_reusable"
                ]
            ).issubset(approved)
        )

        records = [
            item
            for item in self._enumerate_real_history()
            if item["authorization_id"] == EXPIRED_FRESH_AUTHORIZATION_ID
        ]
        self.assertEqual(
            records,
            [
                {
                    "path": EXPIRED_FRESH_AUTHORIZATION_RELATIVE_PATH,
                    "sha256": EXPIRED_FRESH_AUTHORIZATION_SHA256,
                    "size": 4218,
                    "evidence_class": (
                        git_auth.HISTORICAL_AUTHORIZATION_EVIDENCE_CLASS
                    ),
                    "authorization_id": EXPIRED_FRESH_AUTHORIZATION_ID,
                    "terminal_disposition": (
                        "BLOCKED_UNCONSUMED_SUPERSEDED"
                    ),
                }
            ],
        )

    def test_omission_from_future_trust_root_fails_closed(self) -> None:
        """Break caught: directory discovery silently broadens future trust."""
        profile = git_auth.FOUR_TOKEN_STANDARD_FOUR_HOUR_AUTHORIZATION_PROFILE
        omitted_document = {
            "prior_authorizations_non_reusable": list(
                self.authorization_document[
                    "prior_authorizations_non_reusable"
                ]
            )
        }
        approved = git_auth.extract_approved_historical_authorization_ids(
            omitted_document,
            current_authorization_id=(
                FUTURE_FOUR_TOKEN_STANDARD_FOUR_HOUR_AUTHORIZATION_ID
            ),
        )
        with self.assertRaisesRegex(
            git_auth.GitProvenanceAuthorizationError,
            "unapproved historical authorization package",
        ):
            git_auth.enumerate_historical_authorization_evidence(
                repository_root=REPOSITORY_ROOT,
                current_authorization_id=(
                    FUTURE_FOUR_TOKEN_STANDARD_FOUR_HOUR_AUTHORIZATION_ID
                ),
                approved_historical_authorization_ids=approved,
                authorization_package_roots=(
                    profile.historical_authorization_package_roots
                ),
                current_authorization_package_root=(
                    profile.authorization_package_root
                ),
            )

    def test_tampered_disposable_copy_fails_existing_sha_binding(self) -> None:
        """Break caught: bound Ha bytes change after future enumeration."""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp).resolve()
            copied = root / EXPIRED_FRESH_AUTHORIZATION_RELATIVE_PATH
            copied.parent.mkdir(parents=True)
            shutil.copy2(self.authorization_path, copied)
            records = git_auth.enumerate_historical_authorization_evidence(
                repository_root=root,
                current_authorization_id=(
                    FUTURE_FOUR_TOKEN_STANDARD_FOUR_HOUR_AUTHORIZATION_ID
                ),
                approved_historical_authorization_ids=[
                    EXPIRED_FRESH_AUTHORIZATION_ID
                ],
                tracked_operator_runs_paths=set(),
                authorization_package_roots=(
                    FOUR_TOKEN_STANDARD_FOUR_HOUR_AUTHORIZATION_ROOT,
                ),
                current_authorization_package_root=(
                    FOUR_TOKEN_STANDARD_FOUR_HOUR_AUTHORIZATION_ROOT
                ),
            )
            os.chmod(copied, 0o644)
            tampered = bytearray(self.authorization_bytes)
            tampered[0] = ord("[")
            copied.write_bytes(tampered)
            with self.assertRaisesRegex(
                git_auth.GitProvenanceAuthorizationError, "SHA-256 mismatch"
            ):
                git_auth._validate_historical_authorization_evidence(
                    {"historical_authorization_evidence": list(records)},
                    root=root,
                    authorization_id=(
                        FUTURE_FOUR_TOKEN_STANDARD_FOUR_HOUR_AUTHORIZATION_ID
                    ),
                    approved_historical_authorization_ids=[
                        EXPIRED_FRESH_AUTHORIZATION_ID
                    ],
                    tracked_paths=set(),
                    current_manifest_paths=set(),
                    profile=(
                        git_auth.FOUR_TOKEN_STANDARD_FOUR_HOUR_AUTHORIZATION_PROFILE
                    ),
                )

    def test_wrong_authorization_id_is_not_adopted(self) -> None:
        """Break caught: a lookalike package inherits the adopted diagnostic."""
        wrong_id = f"{EXPIRED_FRESH_AUTHORIZATION_ID}_WRONG"
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp).resolve()
            copied = (
                root
                / FOUR_TOKEN_STANDARD_FOUR_HOUR_AUTHORIZATION_ROOT
                / wrong_id
                / "final_authorization.json"
            )
            copied.parent.mkdir(parents=True)
            shutil.copy2(self.authorization_path, copied)
            with self.assertRaisesRegex(
                git_auth.GitProvenanceAuthorizationError,
                "unapproved historical authorization package",
            ):
                git_auth.enumerate_historical_authorization_evidence(
                    repository_root=root,
                    current_authorization_id=(
                        FUTURE_FOUR_TOKEN_STANDARD_FOUR_HOUR_AUTHORIZATION_ID
                    ),
                    approved_historical_authorization_ids=[
                        EXPIRED_FRESH_AUTHORIZATION_ID
                    ],
                    tracked_operator_runs_paths=set(),
                    authorization_package_roots=(
                        FOUR_TOKEN_STANDARD_FOUR_HOUR_AUTHORIZATION_ROOT,
                    ),
                    current_authorization_package_root=(
                        FOUR_TOKEN_STANDARD_FOUR_HOUR_AUTHORIZATION_ROOT
                    ),
                )
        self.assertEqual(
            git_auth._terminal_disposition_for(wrong_id),
            git_auth.DEFAULT_TERMINAL_DISPOSITION,
        )

    def test_expired_package_is_historical_non_reusable_and_never_current(self) -> None:
        """Break caught: diagnostic adoption revives current/reuse authority."""
        records = self._enumerate_real_history()
        expired = [
            item
            for item in records
            if item["authorization_id"] == EXPIRED_FRESH_AUTHORIZATION_ID
        ]
        consumed = [
            item
            for item in records
            if item["authorization_id"]
            == CONSUMED_FOUR_TOKEN_STANDARD_FOUR_HOUR_AUTHORIZATION_ID
        ]
        self.assertEqual(len(expired), 1)
        self.assertEqual(len(consumed), 1)
        self.assertNotEqual(
            expired[0]["authorization_id"], consumed[0]["authorization_id"]
        )
        self.assertEqual(
            expired[0]["evidence_class"],
            git_auth.HISTORICAL_AUTHORIZATION_EVIDENCE_CLASS,
        )
        future_current_authorization_path = (
            f"{FOUR_TOKEN_STANDARD_FOUR_HOUR_AUTHORIZATION_ROOT}/"
            f"{FUTURE_FOUR_TOKEN_STANDARD_FOUR_HOUR_AUTHORIZATION_ID}/"
            "final_authorization.json"
        )
        self.assertNotEqual(
            EXPIRED_FRESH_AUTHORIZATION_RELATIVE_PATH,
            future_current_authorization_path,
        )
        one_shot = self.authorization_document["one_shot_policy"]
        self.assertEqual(one_shot["allowed_invocation_count"], 1)
        for flag in (
            "automatic_retry_allowed",
            "manual_rerun_allowed",
            "resume_allowed",
            "restart_allowed",
            "successor_allowed",
        ):
            self.assertIs(one_shot[flag], False)
        with self.assertRaisesRegex(
            AuthorizationTemporalError, "AUTHORIZATION_EXPIRED"
        ):
            validate_authorization_temporal_validity(
                self.authorization_document,
                now=datetime(2026, 8, 24, 10, 20, 30, tzinfo=timezone.utc),
            )


class FourTokenHistoricalMigrationFixture:
    """Disposable repository carrying M, Ha and the exact preserved Hm package."""

    authorization_id = "V2_9_8B_FOUR_TOKEN_AUTH_TESTONLY"
    migration_id = "MIGRATION_061_TESTONLY"
    historical_authorization_id = "V2_9_8B_STANDARD_4H_AUTH_TESTONLY"

    def __init__(
        self,
        *,
        historical_migration_execution_id: str = HISTORICAL_MIGRATION_EXECUTION_ID,
        create_historical_migration: bool = True,
        with_historical_authorization: bool = True,
    ) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name).resolve()
        self.repo = self.root / "repo"
        self.repo.mkdir()
        self._git("init")
        self._git("config", "user.email", "tests@example.invalid")
        self._git("config", "user.name", "Four Token Historical Migration Tests")
        (self.repo / ".gitignore").write_text("*.sqlite3\n.venv/\n", encoding="utf-8")
        (self.repo / "tracked.txt").write_text("clean\n", encoding="utf-8")
        self._git("add", ".")
        self._git("commit", "-m", "baseline")
        self.branch = self._git("rev-parse", "--abbrev-ref", "HEAD").stdout.strip()
        self.head = self._git("rev-parse", "HEAD").stdout.strip()

        profile = git_auth.FOUR_TOKEN_PROOF_AUTHORIZATION_PROFILE

        # M: current migration-055 evidence.
        self.migration_root = (
            self.repo / profile.migration_package_root / self.migration_id
        )
        self.migration_root.mkdir(parents=True)
        (self.migration_root / "migration_061_application_result.json").write_text(
            json.dumps({"migration": self.migration_id}) + "\n", encoding="utf-8"
        )

        # M: current four-token authorization evidence.
        self.authorization_root = (
            self.repo / profile.authorization_package_root / self.authorization_id
        )
        self.authorization_root.mkdir(parents=True)

        # Ha: one approved historical authorization package.
        prior_non_reusable: tuple[str, ...] = ()
        if with_historical_authorization:
            historical_root = (
                self.repo
                / "operator-runs/v2-9-8b-standard-four-hour-final-authorization"
                / self.historical_authorization_id
            )
            historical_root.mkdir(parents=True)
            (historical_root / "final_authorization.json").write_text(
                json.dumps({"authorization_id": self.historical_authorization_id})
                + "\n",
                encoding="utf-8",
            )
            prior_non_reusable = (self.historical_authorization_id,)

        # Hm: the exact preserved historical migration-050 package, ignored the
        # same way the real preserved package is ignored.
        self.historical_migration_execution_id = historical_migration_execution_id
        self.historical_migration_root = (
            self.repo / HISTORICAL_MIGRATION_ROOT / historical_migration_execution_id
        )
        if create_historical_migration:
            self.write_historical_migration_package(
                self.historical_migration_root, _HISTORICAL_MIGRATION_FILES
            )

        # The fixture declares its OWN immutable completeness identity for the
        # synthetic package. It never borrows the real production declaration.
        if create_historical_migration:
            count, digest = _synthetic_completeness_identity(
                repo=self.repo,
                package_root=HISTORICAL_MIGRATION_ROOT,
                execution_id=historical_migration_execution_id,
                evidence_class=git_auth.HISTORICAL_MIGRATION_EVIDENCE_CLASS,
            )
        else:
            # Absent-package cases still declare a real identity so the missing
            # root/execution directory is what fails closed, not a malformed
            # declaration.
            count, digest = len(_HISTORICAL_MIGRATION_FILES), "0" * 64
        self.synthetic_expected_file_count = count
        self.synthetic_expected_inventory_sha256 = digest
        self.profile = _replace_historical_migration_packages(
            git_auth.FOUR_TOKEN_PROOF_AUTHORIZATION_PROFILE,
            (
                git_auth.HistoricalMigrationPackage(
                    package_root=HISTORICAL_MIGRATION_ROOT,
                    execution_id=historical_migration_execution_id,
                    evidence_class=git_auth.HISTORICAL_MIGRATION_EVIDENCE_CLASS,
                    expected_file_count=count,
                    expected_inventory_sha256=digest,
                ),
            ),
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
            prior_authorizations_non_reusable=prior_non_reusable,
        )
        self.authorization_path.write_text(
            json.dumps(document, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )
        self.authorization_sha256 = _sha(self.authorization_path)

    # -- fixture helpers -------------------------------------------------

    def _git(self, *args: str):
        return subprocess.run(
            ["git", *args], cwd=self.repo, capture_output=True, text=True, check=True
        )

    def write_historical_migration_package(
        self, package_dir: Path, files: dict[str, str]
    ) -> None:
        for relative, content in files.items():
            target = package_dir / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(content, encoding="utf-8")
        self.exclude(package_dir)

    def exclude(self, target: Path) -> None:
        """Ignore an operator-runs path exactly like the preserved package."""
        exclude_file = self.repo / ".git" / "info" / "exclude"
        exclude_file.parent.mkdir(parents=True, exist_ok=True)
        existing = (
            exclude_file.read_text(encoding="utf-8")
            if exclude_file.exists()
            else ""
        )
        lines = []
        if target.is_dir():
            for path in sorted(target.rglob("*")):
                if path.is_file():
                    lines.append(path.relative_to(self.repo).as_posix())
        else:
            lines.append(target.relative_to(self.repo).as_posix())
        exclude_file.write_text(
            existing + "".join(f"{line}\n" for line in lines), encoding="utf-8"
        )

    def historical_migration_paths(self) -> list[str]:
        base = f"{HISTORICAL_MIGRATION_ROOT}/{self.historical_migration_execution_id}"
        return sorted(
            f"{base}/{relative}" for relative in _HISTORICAL_MIGRATION_FILES
        )

    def active_profile(self):
        """Scope the fixture profile over both production import bindings.

        ``build_manifest_bytes()`` reads the profile from its own module global
        and ``_resolved_profile()`` accepts only the module-level profiles, so
        both bindings are patched together. ``mock.patch.object`` restores each
        one on every exit path, including exceptions.
        """
        return _patched_four_token_profile(self.profile)

    def manifest(self):
        with self.active_profile():
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
        return self.validate_prebuilt(path, digest)

    def validate_prebuilt(self, manifest_path: Path, digest: str):
        with self.active_profile():
            return git_auth.validate_git_provenance_manifest_pre_marker(
                repository_root=self.repo,
                manifest_path=str(manifest_path),
                manifest_sha256=digest,
                profile=self.profile,
            )

    def close(self) -> None:
        self.tmp.cleanup()


class FourTokenHistoricalMigrationProvenanceTests(unittest.TestCase):
    """GREEN proofs 1-11 for the exact profile-bound ``Hm`` evidence class."""

    def test_preserved_migration050_package_does_not_block_preparation(self) -> None:
        """RED reproduction of the real pre-marker preparation blocker.

        Migration-055 current evidence plus the exact four-token authorization
        plus the preserved ignored migration-050 package must reconcile instead
        of failing as unexplained ignored ``operator-runs/`` evidence.
        """
        fixture = FourTokenHistoricalMigrationFixture()
        try:
            prepared = fixture.validate()
            self.assertEqual(prepared.authorization_id, fixture.authorization_id)
        finally:
            fixture.close()

    def test_exact_historical_migration050_package_passes(self) -> None:
        """GREEN 1: the exact preserved package is accepted, not rejected."""
        fixture = FourTokenHistoricalMigrationFixture()
        try:
            payload, _path, _digest = fixture.manifest()
            records = payload["historical_migration_evidence"]
            self.assertEqual(
                [item["path"] for item in records],
                fixture.historical_migration_paths(),
            )
            prepared = fixture.validate()
            for path in fixture.historical_migration_paths():
                self.assertIn(path, prepared.allowed_untracked_paths)
            # 2 current files + 1 historical authorization file + 6 Hm files.
            self.assertEqual(prepared.file_count, 9)
        finally:
            fixture.close()

    def test_historical_migration_binding_is_exact_and_profile_scoped(self) -> None:
        """GREEN 1: only the four-token profile carries the exact binding."""
        profile = git_auth.FOUR_TOKEN_PROOF_AUTHORIZATION_PROFILE
        # 050, 055, 056, 057, 058, 059 and 061 are immutable historical
        # packages after migration 062 becomes current authority.
        self.assertEqual(len(profile.historical_migration_packages), 7)
        by_root = {
            item.package_root: item
            for item in profile.historical_migration_packages
        }
        package = by_root[HISTORICAL_MIGRATION_ROOT]
        self.assertEqual(package.package_root, HISTORICAL_MIGRATION_ROOT)
        self.assertEqual(package.execution_id, HISTORICAL_MIGRATION_EXECUTION_ID)
        self.assertEqual(
            package.evidence_class,
            git_auth.HISTORICAL_MIGRATION_EVIDENCE_CLASS,
        )
        # Each declared package carries its own immutable completeness identity.
        self.assertEqual(package.expected_file_count, 12)
        self.assertEqual(
            package.expected_inventory_sha256,
            git_auth.FOUR_TOKEN_HISTORICAL_MIGRATION_EXPECTED_INVENTORY_SHA256,
        )
        # 055, 056 and 057 keep distinct roots, executions and evidence classes.
        self.assertEqual(
            set(by_root),
            {
                HISTORICAL_MIGRATION_ROOT,
                git_auth.MIGRATION_055_PACKAGE_ROOT,
                git_auth.MIGRATION_056_PACKAGE_ROOT,
                git_auth.MIGRATION_057_PACKAGE_ROOT,
                MIGRATION_058_ROOT,
                git_auth.MIGRATION_059_PACKAGE_ROOT,
                git_auth.MIGRATION_061_PACKAGE_ROOT,
            },
        )
        self.assertEqual(
            {item.evidence_class for item in profile.historical_migration_packages},
            {
                git_auth.HISTORICAL_MIGRATION_EVIDENCE_CLASS,
                git_auth.HISTORICAL_MIGRATION_055_EVIDENCE_CLASS,
                git_auth.HISTORICAL_MIGRATION_056_EVIDENCE_CLASS,
                git_auth.HISTORICAL_MIGRATION_057_EVIDENCE_CLASS,
                "HISTORICAL_MIGRATION_058_EVIDENCE",
                "HISTORICAL_MIGRATION_059_EVIDENCE",
                "HISTORICAL_MIGRATION_061_EVIDENCE",
            },
        )
        # None of them is the current schema transition, which is now 062.
        self.assertNotIn(
            profile.migration_package_root, set(by_root)
        )
        # The historical migration class is not an authorization class and does
        # not reuse the authorization trust root.
        self.assertNotEqual(
            git_auth.HISTORICAL_MIGRATION_EVIDENCE_CLASS,
            git_auth.HISTORICAL_AUTHORIZATION_EVIDENCE_CLASS,
        )
        self.assertNotIn(
            HISTORICAL_MIGRATION_ROOT,
            profile.historical_authorization_package_roots,
        )

    def test_migration062_identity_is_committed_and_old_auth_is_superseded(
        self,
    ) -> None:
        profile = git_auth.FOUR_TOKEN_STANDARD_FOUR_HOUR_AUTHORIZATION_PROFILE
        self.assertEqual(profile.migration_package_root, MIGRATION_062_ROOT)
        self.assertEqual(profile.migration_package_kind, "MIGRATION_062_EVIDENCE")
        self.assertEqual(
            profile.current_migration_execution_id, MIGRATION_062_EXECUTION_ID
        )
        self.assertEqual(
            git_auth._terminal_disposition_for(
                "V2_9_8B_FOUR_TOKEN_STD4H_AUTH_20260821T124505Z_8cf7ee5d"
            ),
            "BLOCKED_UNCONSUMED_SUPERSEDED",
        )

    def test_migration050_remains_historical_never_current(self) -> None:
        """GREEN 2/6: Hm never becomes current schema-transition evidence."""
        fixture = FourTokenHistoricalMigrationFixture()
        try:
            payload, _path, _digest = fixture.manifest()
            current_kinds = {item["package_kind"] for item in payload["files"]}
            # The synthetic profile keeps flexible execution identity on the
            # current Migration-062 root/kind.
            self.assertEqual(
                current_kinds,
                {
                    "MIGRATION_062_EVIDENCE",
                    "FOUR_TOKEN_PROOF_AUTHORIZATION_EVIDENCE",
                },
            )
            current_paths = {item["path"] for item in payload["files"]}
            for path in fixture.historical_migration_paths():
                self.assertNotIn(path, current_paths)
                self.assertFalse(path.startswith(MIGRATION_062_ROOT))
            for item in payload["historical_migration_evidence"]:
                self.assertEqual(
                    item["evidence_class"],
                    git_auth.HISTORICAL_MIGRATION_EVIDENCE_CLASS,
                )
                self.assertEqual(
                    item["migration_execution_id"],
                    HISTORICAL_MIGRATION_EXECUTION_ID,
                )
                self.assertNotEqual(
                    item["migration_execution_id"],
                    payload["migration_execution_id"],
                )
            # The disposable authorization supplies the exact current execution
            # identity at preparation time because its current identity fields
            # are intentionally unconstrained for this synthetic fixture.
            self.assertEqual(
                payload["migration_execution_id"], fixture.migration_id
            )
        finally:
            fixture.close()

    def test_legitimate_migration062_and_pair_ready_inventory_is_classified(
        self,
    ) -> None:
        """Exact 062 current + 058 Hm + PAIR_READY Hr must reconcile.

        The break this catches is removal or omission of either exact profile
        declaration.  The strict reconciler remains unchanged: profile data
        must classify these legitimate paths before it is called.
        """
        profile = git_auth.FOUR_TOKEN_STANDARD_FOUR_HOUR_AUTHORIZATION_PROFILE
        authorization_id = "V2_9_8B_FOUR_TOKEN_STD4H_AUTH_TESTONLY"
        current_paths = {
            (
                f"{MIGRATION_062_ROOT}/{MIGRATION_062_EXECUTION_ID}/"
                "migration_062_controlled_application_evidence.json"
            ),
            (
                f"{profile.authorization_package_root}/{authorization_id}/"
                "final_authorization.json"
            ),
        }
        historical_migration_paths = (
            set(MIGRATION_058_PATHS)
            if any(
                package.package_root == MIGRATION_058_ROOT
                and package.execution_id == MIGRATION_058_EXECUTION_ID
                for package in profile.historical_migration_packages
            )
            else set()
        )
        historical_reconciliation_paths = {
            member.path
            for package in profile.historical_reconciliation_packages
            if package.package_root == PAIR_READY_ROOT
            and package.execution_id == PAIR_READY_EXECUTION_ID
            for member in package.files
        }
        complete_inventory = (
            current_paths | set(MIGRATION_058_PATHS) | set(PAIR_READY_PATHS)
        )

        git_auth._reconcile_evidence_sets(
            current_manifest_paths=current_paths,
            historical_paths=set(),
            historical_migration_paths=historical_migration_paths,
            historical_reconciliation_paths=historical_reconciliation_paths,
            visible_paths=complete_inventory,
            ignored_paths=set(),
            tracked_paths=set(),
            inventory_paths=complete_inventory,
            current_package_roots=(
                f"{MIGRATION_062_ROOT}/{MIGRATION_062_EXECUTION_ID}",
                f"{profile.authorization_package_root}/{authorization_id}",
            ),
            sidecar_untracked_paths=(),
        )

    def test_current_equality_remains_migration062_plus_current_authorization(
        self,
    ) -> None:
        """GREEN 3/5: C == M only; an extra current-package file fails closed."""
        fixture = FourTokenHistoricalMigrationFixture()
        try:
            payload, _path, _digest = fixture.manifest()
            profile = git_auth.FOUR_TOKEN_PROOF_AUTHORIZATION_PROFILE
            expected_current = {
                (
                    f"{profile.migration_package_root}/{fixture.migration_id}/"
                    "migration_061_application_result.json"
                ),
                (
                    f"{profile.authorization_package_root}/"
                    f"{fixture.authorization_id}/final_authorization.json"
                ),
            }
            self.assertEqual(
                {item["path"] for item in payload["files"]}, expected_current
            )
            _payload, manifest_path, digest = fixture.manifest()
            (fixture.migration_root / "stray_current.json").write_text(
                "{}\n", encoding="utf-8"
            )
            with self.assertRaises(git_auth.GitProvenanceAuthorizationError):
                fixture.validate_prebuilt(manifest_path, digest)
        finally:
            fixture.close()

    def test_every_historical_migration_file_is_path_size_sha_bound(self) -> None:
        """GREEN 4: each Hm record carries normalized path, size and SHA-256."""
        fixture = FourTokenHistoricalMigrationFixture()
        try:
            payload, _path, _digest = fixture.manifest()
            records = payload["historical_migration_evidence"]
            self.assertEqual(len(records), len(_HISTORICAL_MIGRATION_FILES))
            for item in records:
                self.assertEqual(
                    set(item),
                    {
                        "path",
                        "sha256",
                        "size",
                        "evidence_class",
                        "migration_execution_id",
                    },
                )
                target = fixture.repo / item["path"]
                self.assertEqual(item["sha256"], _sha(target))
                self.assertEqual(item["size"], target.stat().st_size)
                self.assertEqual(Path(item["path"]).as_posix(), item["path"])
            self.assertEqual(
                [item["path"] for item in records],
                sorted(item["path"] for item in records),
            )
        finally:
            fixture.close()

    def test_mutated_historical_migration_file_fails_closed(self) -> None:
        """GREEN 5: byte mutation after manifest creation fails closed."""
        fixture = FourTokenHistoricalMigrationFixture()
        try:
            _payload, manifest_path, digest = fixture.manifest()
            target = fixture.historical_migration_root / "preflight.json"
            target.write_text('{"preflight": "tampered"}\n', encoding="utf-8")
            with self.assertRaises(git_auth.GitProvenanceAuthorizationError):
                fixture.validate_prebuilt(manifest_path, digest)
        finally:
            fixture.close()

    def test_deleted_historical_migration_file_fails_closed(self) -> None:
        """GREEN 6: deletion of bound Hm evidence fails closed."""
        fixture = FourTokenHistoricalMigrationFixture()
        try:
            _payload, manifest_path, digest = fixture.manifest()
            (fixture.historical_migration_root / "preflight.json").unlink()
            with self.assertRaises(git_auth.GitProvenanceAuthorizationError):
                fixture.validate_prebuilt(manifest_path, digest)
        finally:
            fixture.close()

    def test_extra_historical_migration_file_fails_closed(self) -> None:
        """GREEN 7: an unbound extra file inside the exact package fails closed."""
        fixture = FourTokenHistoricalMigrationFixture()
        try:
            _payload, manifest_path, digest = fixture.manifest()
            extra = fixture.historical_migration_root / "extra_evidence.json"
            extra.write_text("{}\n", encoding="utf-8")
            fixture.exclude(extra)
            with self.assertRaises(git_auth.GitProvenanceAuthorizationError):
                fixture.validate_prebuilt(manifest_path, digest)
        finally:
            fixture.close()

    def test_second_migration050_package_fails_closed(self) -> None:
        """GREEN 8: no other package under the mig050 root is trusted."""
        fixture = FourTokenHistoricalMigrationFixture()
        try:
            second = (
                fixture.repo
                / HISTORICAL_MIGRATION_ROOT
                / "V2_9_8B_AUTHORITATIVE_MIG050_20260801T202423Z_deadbeef"
            )
            fixture.write_historical_migration_package(
                second, {"final_authorization.json": "{}\n"}
            )
            with self.assertRaises(git_auth.GitProvenanceAuthorizationError):
                fixture.validate()
        finally:
            fixture.close()

    def test_symlinked_historical_migration_entry_fails_closed(self) -> None:
        """GREEN 9: symlink/alias evidence inside the exact package fails closed."""
        fixture = FourTokenHistoricalMigrationFixture()
        try:
            link = fixture.historical_migration_root / "aliased_preflight.json"
            link.symlink_to(fixture.historical_migration_root / "preflight.json")
            fixture.exclude(link)
            with self.assertRaises(git_auth.GitProvenanceAuthorizationError):
                fixture.validate()
        finally:
            fixture.close()

    def test_non_regular_historical_migration_entry_fails_closed(self) -> None:
        """GREEN 9: a non-regular entry inside the exact package fails closed."""
        fixture = FourTokenHistoricalMigrationFixture()
        try:
            fifo = fixture.historical_migration_root / "evidence.fifo"
            os.mkfifo(fifo)
            fixture.exclude(fifo)
            with self.assertRaises(git_auth.GitProvenanceAuthorizationError):
                fixture.validate()
        finally:
            fixture.close()

    def test_arbitrary_ignored_operator_runs_evidence_still_fails(self) -> None:
        """GREEN 10: broad operator-runs trust is not introduced."""
        fixture = FourTokenHistoricalMigrationFixture()
        try:
            stray_dir = (
                fixture.repo
                / git_auth.OPERATOR_RUNS_ROOT
                / "v2-9-8b-unrelated-evidence"
            )
            stray_dir.mkdir(parents=True)
            stray = stray_dir / "stray.json"
            stray.write_text("{}\n", encoding="utf-8")
            fixture.exclude(stray)
            with self.assertRaises(git_auth.GitProvenanceAuthorizationError):
                fixture.validate()
        finally:
            fixture.close()

    def test_allowed_file_set_digest_covers_historical_migration_evidence(
        self,
    ) -> None:
        """GREEN 11: Hm bytes enter the allowed-file-set digest."""
        fixture = FourTokenHistoricalMigrationFixture()
        try:
            payload, _path, _digest = fixture.manifest()
            prepared = fixture.validate()
            with_hm = git_auth.compute_allowed_file_set_sha256(
                [
                    {
                        "package_kind": item["package_kind"],
                        "path": item["path"],
                        "sha256": item["sha256"],
                        "size": item["size"],
                    }
                    for item in payload["files"]
                ]
                + [
                    {
                        "package_kind": item["evidence_class"],
                        "path": item["path"],
                        "sha256": item["sha256"],
                        "size": item["size"],
                    }
                    for item in payload["historical_authorization_evidence"]
                ]
                + [
                    {
                        "package_kind": item["evidence_class"],
                        "path": item["path"],
                        "sha256": item["sha256"],
                        "size": item["size"],
                    }
                    for item in payload["historical_migration_evidence"]
                ]
            )
            self.assertEqual(prepared.allowed_file_set_sha256, with_hm)

            without_hm = git_auth.compute_allowed_file_set_sha256(
                [
                    {
                        "package_kind": item["package_kind"],
                        "path": item["path"],
                        "sha256": item["sha256"],
                        "size": item["size"],
                    }
                    for item in payload["files"]
                ]
                + [
                    {
                        "package_kind": item["evidence_class"],
                        "path": item["path"],
                        "sha256": item["sha256"],
                        "size": item["size"],
                    }
                    for item in payload["historical_authorization_evidence"]
                ]
            )
            self.assertNotEqual(prepared.allowed_file_set_sha256, without_hm)
        finally:
            fixture.close()

    def test_historical_migration_is_disjoint_from_other_evidence_sets(self) -> None:
        """GREEN 2/4: Hm is disjoint from T, M and Ha."""
        fixture = FourTokenHistoricalMigrationFixture()
        try:
            payload, _path, _digest = fixture.manifest()
            hm = {item["path"] for item in payload["historical_migration_evidence"]}
            m_paths = {item["path"] for item in payload["files"]}
            ha_paths = {
                item["path"]
                for item in payload["historical_authorization_evidence"]
            }
            tracked = set(
                subprocess.run(
                    ["git", "ls-files"],
                    cwd=fixture.repo,
                    capture_output=True,
                    text=True,
                    check=True,
                ).stdout.split()
            )
            self.assertTrue(hm)
            self.assertTrue(ha_paths)
            self.assertFalse(hm & m_paths)
            self.assertFalse(hm & ha_paths)
            self.assertFalse(hm & tracked)
        finally:
            fixture.close()

    def test_missing_declared_package_root_fails_closed(self) -> None:
        """Required presence 1: a declared package root may not be absent.

        The four-token profile explicitly declares the preserved migration-050
        package. Removing it before preparation must not silently produce an
        empty ``historical_migration_evidence`` array.
        """
        fixture = FourTokenHistoricalMigrationFixture(
            create_historical_migration=False
        )
        try:
            self.assertFalse((fixture.repo / HISTORICAL_MIGRATION_ROOT).exists())
            with self.assertRaises(git_auth.GitProvenanceAuthorizationError):
                git_auth.enumerate_historical_migration_evidence(
                    repository_root=fixture.repo,
                    historical_migration_packages=(
                        fixture.profile.historical_migration_packages
                    ),
                )
            with self.assertRaises(git_auth.GitProvenanceAuthorizationError):
                fixture.manifest()
        finally:
            fixture.close()

    def test_missing_exact_execution_directory_fails_closed(self) -> None:
        """Required presence 2: the exact execution directory may not be absent."""
        fixture = FourTokenHistoricalMigrationFixture(
            create_historical_migration=False
        )
        try:
            (fixture.repo / HISTORICAL_MIGRATION_ROOT).mkdir(parents=True)
            self.assertTrue((fixture.repo / HISTORICAL_MIGRATION_ROOT).is_dir())
            self.assertFalse(fixture.historical_migration_root.exists())
            with self.assertRaises(git_auth.GitProvenanceAuthorizationError):
                git_auth.enumerate_historical_migration_evidence(
                    repository_root=fixture.repo,
                    historical_migration_packages=(
                        fixture.profile.historical_migration_packages
                    ),
                )
            with self.assertRaises(git_auth.GitProvenanceAuthorizationError):
                fixture.manifest()
        finally:
            fixture.close()

    def test_empty_exact_execution_directory_fails_closed(self) -> None:
        """Required presence 3: the exact package must hold bound evidence."""
        fixture = FourTokenHistoricalMigrationFixture(
            create_historical_migration=False
        )
        try:
            fixture.historical_migration_root.mkdir(parents=True)
            self.assertTrue(fixture.historical_migration_root.is_dir())
            self.assertEqual(list(fixture.historical_migration_root.iterdir()), [])
            with self.assertRaises(git_auth.GitProvenanceAuthorizationError):
                git_auth.enumerate_historical_migration_evidence(
                    repository_root=fixture.repo,
                    historical_migration_packages=(
                        fixture.profile.historical_migration_packages
                    ),
                )
            with self.assertRaises(git_auth.GitProvenanceAuthorizationError):
                fixture.manifest()
        finally:
            fixture.close()

    def test_declared_package_root_must_be_a_real_directory(self) -> None:
        """Required presence: a file or symlink standing in for the root fails."""
        fixture = FourTokenHistoricalMigrationFixture(
            create_historical_migration=False
        )
        try:
            root_path = fixture.repo / HISTORICAL_MIGRATION_ROOT
            root_path.parent.mkdir(parents=True, exist_ok=True)
            root_path.write_text("not a directory\n", encoding="utf-8")
            fixture.exclude(root_path)
            with self.assertRaises(git_auth.GitProvenanceAuthorizationError):
                git_auth.enumerate_historical_migration_evidence(
                    repository_root=fixture.repo,
                    historical_migration_packages=(
                        fixture.profile.historical_migration_packages
                    ),
                )
        finally:
            fixture.close()

    def test_symlinked_exact_execution_directory_fails_closed(self) -> None:
        """Required presence: an aliased execution directory is not real evidence."""
        fixture = FourTokenHistoricalMigrationFixture(
            create_historical_migration=False
        )
        try:
            real = fixture.repo / "elsewhere-mig050"
            real.mkdir(parents=True)
            (real / "preflight.json").write_text("{}\n", encoding="utf-8")
            fixture.historical_migration_root.parent.mkdir(parents=True)
            fixture.historical_migration_root.symlink_to(real, target_is_directory=True)
            with self.assertRaises(git_auth.GitProvenanceAuthorizationError):
                git_auth.enumerate_historical_migration_evidence(
                    repository_root=fixture.repo,
                    historical_migration_packages=(
                        fixture.profile.historical_migration_packages
                    ),
                )
        finally:
            fixture.close()


class UnchangedProfileBehaviourTests(unittest.TestCase):
    """GREEN 12/13: ordinary and standard-four-hour behavior is untouched."""

    def test_window_15m_profile_declares_no_historical_migration(self) -> None:
        profile = git_auth.ORDINARY_AUTHORIZATION_PROFILE
        self.assertEqual(profile.historical_migration_packages, ())
        self.assertEqual(profile.command_mode, "run")
        self.assertEqual(
            profile.manifest_schema_version, git_auth.MANIFEST_SCHEMA_VERSION
        )
        self.assertEqual(
            profile.migration_package_root, git_auth.MIGRATION_PACKAGE_ROOT
        )
        self.assertEqual(
            profile.migration_package_kind, git_auth.MIGRATION_PACKAGE_KIND
        )

    def test_standard_four_hour_profile_declares_no_historical_migration(
        self,
    ) -> None:
        profile = git_auth.STANDARD_FOUR_HOUR_AUTHORIZATION_PROFILE
        self.assertEqual(profile.historical_migration_packages, ())
        self.assertEqual(profile.command_mode, "standard-four-hour-run")
        self.assertEqual(
            profile.manifest_schema_version,
            "PRINTER_V1_GIT_PROVENANCE_MANIFEST_STANDARD_4H_V1",
        )
        self.assertEqual(
            profile.migration_package_root, git_auth.MIGRATION_PACKAGE_ROOT
        )

    def test_only_four_token_profile_accepts_the_historical_migration_field(
        self,
    ) -> None:
        """Ordinary/standard manifests must keep their exact key sets."""
        for profile in (
            git_auth.ORDINARY_AUTHORIZATION_PROFILE,
            git_auth.STANDARD_FOUR_HOUR_AUTHORIZATION_PROFILE,
        ):
            with self.subTest(profile=profile.command_mode):
                self.assertEqual(
                    git_auth.expected_manifest_keys(profile), git_auth._MANIFEST_KEYS
                )
        self.assertEqual(
            git_auth.expected_manifest_keys(
                git_auth.FOUR_TOKEN_PROOF_AUTHORIZATION_PROFILE
            ),
            git_auth._MANIFEST_KEYS | {"historical_migration_evidence"},
        )


if __name__ == "__main__":  # pragma: no cover - direct invocation guard
    unittest.main()
