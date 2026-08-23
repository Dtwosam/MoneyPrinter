"""Focused offline proof for the Migration-061 Git-evidence cutover.

The tests copy immutable operator evidence into disposable repositories. They
create only fixture authorization documents outside the real operator package,
write no SQLite file, create no application marker, and start no runtime.
"""

from __future__ import annotations

import contextlib
from datetime import datetime, timedelta, timezone
import hashlib
import json
from pathlib import Path
import shutil
import stat
import subprocess
from unittest import mock

import pytest

from printer_v1.operator_cli import git_provenance_authorization_manifest as git_auth
from printer_v1.operator_cli import four_token_proof_one_shot_wrapper as four_token


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
MIGRATION_061_ROOT = "operator-runs/v2-9-8b-migration-061-application"
MIGRATION_061_EXECUTION_ID = "MIGRATION_061_20260823T200709Z"
MIGRATION_061_KIND = "MIGRATION_061_EVIDENCE"
MIGRATION_061_FILE_COUNT = 5
MIGRATION_061_INVENTORY_SHA256 = (
    "a6eac8d12e30e9f134c137f79a8b72bbe4f9af9d62e65e159a025c5c87108bd6"
)
MIGRATION_059_ROOT = "operator-runs/v2-9-8b-migration-059-application"
MIGRATION_059_EXECUTION_ID = "MIGRATION_059_20260821T095456Z"
HISTORICAL_MIGRATION_059_KIND = "HISTORICAL_MIGRATION_059_EVIDENCE"
MIGRATION_059_FILE_COUNT = 5
MIGRATION_059_INVENTORY_SHA256 = (
    "d23c4f4bbf2b4683c69038bb6fc372f85c52e280b24662cb46c133690b1479c6"
)
CONSUMED_AUTHORIZATION_ID = (
    "V2_9_8B_FOUR_TOKEN_STD4H_AUTH_20260821T153458Z_512f2436"
)
SYNTHETIC_HISTORICAL_ROOT = "operator-runs/mig061-cutover-historical"
SYNTHETIC_HISTORICAL_EXECUTION_ID = "MIGRATION_050_TESTONLY"
SYNTHETIC_HISTORICAL_KIND = "HISTORICAL_MIGRATION_050_EVIDENCE"
SYNTHETIC_HISTORICAL_RELATIVE = "evidence.json"
SYNTHETIC_HISTORICAL_BYTES = b'{"historical": true}\n'


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _git(repo: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", *args],
        cwd=repo,
        check=True,
        capture_output=True,
        text=True,
    )


def _profile(
    *,
    current_execution_id: str | None = MIGRATION_061_EXECUTION_ID,
    current_file_count: int | None = MIGRATION_061_FILE_COUNT,
    current_inventory_sha256: str | None = MIGRATION_061_INVENTORY_SHA256,
) -> git_auth.GitAuthorizationProfile:
    """Keep the real proof authority while isolating unrelated evidence sets."""
    production = git_auth.FOUR_TOKEN_PROOF_AUTHORIZATION_PROFILE
    historical_path = (
        f"{SYNTHETIC_HISTORICAL_ROOT}/"
        f"{SYNTHETIC_HISTORICAL_EXECUTION_ID}/"
        f"{SYNTHETIC_HISTORICAL_RELATIVE}"
    )
    historical_digest = git_auth.compute_historical_migration_inventory_sha256(
        package_root=SYNTHETIC_HISTORICAL_ROOT,
        execution_id=SYNTHETIC_HISTORICAL_EXECUTION_ID,
        evidence_class=SYNTHETIC_HISTORICAL_KIND,
        files=(
            {
                "path": historical_path,
                "sha256": hashlib.sha256(SYNTHETIC_HISTORICAL_BYTES).hexdigest(),
                "size": len(SYNTHETIC_HISTORICAL_BYTES),
            },
        ),
    )
    return git_auth.GitAuthorizationProfile(
        command_mode=production.command_mode,
        authorization_package_root=production.authorization_package_root,
        authorization_package_kind=production.authorization_package_kind,
        manifest_schema_version=production.manifest_schema_version,
        historical_authorization_package_roots=(
            production.historical_authorization_package_roots
        ),
        migration_package_root=MIGRATION_061_ROOT,
        migration_package_kind=MIGRATION_061_KIND,
        current_migration_execution_id=current_execution_id,
        current_migration_expected_file_count=current_file_count,
        current_migration_expected_inventory_sha256=current_inventory_sha256,
        historical_migration_packages=(
            git_auth.HistoricalMigrationPackage(
                package_root=SYNTHETIC_HISTORICAL_ROOT,
                execution_id=SYNTHETIC_HISTORICAL_EXECUTION_ID,
                evidence_class=SYNTHETIC_HISTORICAL_KIND,
                expected_file_count=1,
                expected_inventory_sha256=historical_digest,
            ),
        ),
        historical_reconciliation_packages=(),
    )


@contextlib.contextmanager
def _patched_profile(profile: git_auth.GitAuthorizationProfile):
    with mock.patch.object(
        git_auth, "FOUR_TOKEN_PROOF_AUTHORIZATION_PROFILE", profile
    ), mock.patch.object(
        four_token, "FOUR_TOKEN_PROOF_AUTHORIZATION_PROFILE", profile
    ):
        yield


class CurrentMigrationFixture:
    """Disposable Git repository with exact copied 061 bytes and fixture auth."""

    authorization_id = "V2_9_8B_FOUR_TOKEN_AUTH_MIG061_TESTONLY"

    def __init__(self, tmp_path: Path, *, migration_id: str = MIGRATION_061_EXECUTION_ID):
        self.outer = tmp_path
        self.repo = tmp_path / "repo"
        self.repo.mkdir()
        _git(self.repo, "init")
        _git(self.repo, "config", "user.email", "tests@example.invalid")
        _git(self.repo, "config", "user.name", "Migration 061 Cutover Tests")
        (self.repo / "tracked.txt").write_text("clean\n", encoding="utf-8")
        _git(self.repo, "add", ".")
        _git(self.repo, "commit", "-m", "baseline")
        self.branch = _git(self.repo, "branch", "--show-current").stdout.strip()
        self.head = _git(self.repo, "rev-parse", "HEAD").stdout.strip()
        self.profile = _profile()
        self.migration_id = migration_id

        historical_dir = (
            self.repo
            / SYNTHETIC_HISTORICAL_ROOT
            / SYNTHETIC_HISTORICAL_EXECUTION_ID
        )
        historical_dir.mkdir(parents=True)
        (historical_dir / SYNTHETIC_HISTORICAL_RELATIVE).write_bytes(
            SYNTHETIC_HISTORICAL_BYTES
        )

        source = REPOSITORY_ROOT / MIGRATION_061_ROOT / MIGRATION_061_EXECUTION_ID
        self.migration_dir = self.repo / MIGRATION_061_ROOT / migration_id
        shutil.copytree(source, self.migration_dir)
        for copied in (self.migration_dir, *self.migration_dir.rglob("*")):
            mode = copied.stat().st_mode | stat.S_IWUSR
            if copied.is_dir():
                mode |= stat.S_IXUSR
            copied.chmod(mode)
        if migration_id != MIGRATION_061_EXECUTION_ID:
            expected_dir = self.repo / MIGRATION_061_ROOT / MIGRATION_061_EXECUTION_ID
            shutil.copytree(source, expected_dir)

        self.authorization_dir = (
            self.repo
            / self.profile.authorization_package_root
            / self.authorization_id
        )
        self.authorization_dir.mkdir(parents=True)
        self.authorization_path = self.authorization_dir / "final_authorization.json"
        now = datetime.now(timezone.utc)
        document = four_token.fixture_authorization_document(
            branch=self.branch,
            head=self.head,
            database={
                "path": "/tmp/printer-v1-migration-061-test.sqlite3",
                "sha256": "c" * 64,
                "size": 4096,
                "inode": 3,
                "mtime_ns": 5,
                "migration_count": 61,
                "migration_head": (
                    "061_standard_4h_progression_fault_preservation.sql"
                ),
            },
            authorization_id=self.authorization_id,
            migration_execution_id=migration_id,
            authorized_at=now.isoformat(),
            expires_at=(now + timedelta(hours=12)).isoformat(),
        )
        self.authorization_path.write_text(
            json.dumps(document, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )

    def build_manifest(self) -> tuple[dict[str, object], Path, str]:
        with _patched_profile(self.profile):
            payload, manifest_bytes = four_token.build_manifest_bytes(
                repository_root=self.repo,
                authorization_file=self.authorization_path,
                authorization_sha256=_sha256(self.authorization_path),
            )
        manifest_path = self.outer / "git-provenance-manifest.json"
        manifest_path.write_bytes(manifest_bytes)
        return payload, manifest_path, hashlib.sha256(manifest_bytes).hexdigest()

    def validate(
        self,
        manifest_path: Path,
        manifest_sha256: str,
        *,
        profile: git_auth.GitAuthorizationProfile | None = None,
    ) -> git_auth.PreparedGitProvenanceAuthorization:
        active = profile or self.profile
        with _patched_profile(active):
            return git_auth.validate_git_provenance_manifest_pre_marker(
                repository_root=self.repo,
                manifest_path=str(manifest_path),
                manifest_sha256=manifest_sha256,
                profile=active,
            )


def _inventory(
    root: Path, *, package_root: str, execution_id: str
) -> list[dict[str, object]]:
    return git_auth._inventory_bound_package_files(
        root=root,
        package_dir=root / package_root / execution_id,
        package_prefix=f"{package_root}/{execution_id}",
        label="focused migration inventory",
    )


def test_real_migration_061_inventory_and_canonical_pre_marker_pass(tmp_path: Path) -> None:
    live_files = _inventory(
        REPOSITORY_ROOT,
        package_root=MIGRATION_061_ROOT,
        execution_id=MIGRATION_061_EXECUTION_ID,
    )
    assert len(live_files) == MIGRATION_061_FILE_COUNT
    assert git_auth.compute_historical_migration_inventory_sha256(
        package_root=MIGRATION_061_ROOT,
        execution_id=MIGRATION_061_EXECUTION_ID,
        evidence_class=MIGRATION_061_KIND,
        files=live_files,
    ) == MIGRATION_061_INVENTORY_SHA256

    fixture = CurrentMigrationFixture(tmp_path)
    _payload, manifest_path, manifest_sha256 = fixture.build_manifest()
    prepared = fixture.validate(manifest_path, manifest_sha256)
    assert prepared.authorization_id == fixture.authorization_id


def test_sibling_execution_id_fails_before_pre_marker_pass(tmp_path: Path) -> None:
    fixture = CurrentMigrationFixture(tmp_path, migration_id="MIGRATION_061_SIBLING")
    _payload, manifest_path, manifest_sha256 = fixture.build_manifest()
    with pytest.raises(
        git_auth.GitProvenanceAuthorizationError,
        match="current migration execution_id",
    ):
        fixture.validate(manifest_path, manifest_sha256)


def test_tamper_before_manifest_fails_committed_current_digest(tmp_path: Path) -> None:
    fixture = CurrentMigrationFixture(tmp_path)
    target = fixture.migration_dir / "pre_application_snapshot.json"
    target.write_bytes(target.read_bytes() + b"\n")
    _payload, manifest_path, manifest_sha256 = fixture.build_manifest()
    with pytest.raises(
        git_auth.GitProvenanceAuthorizationError,
        match="current migration package inventory digest",
    ):
        fixture.validate(manifest_path, manifest_sha256)


@pytest.mark.parametrize("mutation", ["extra", "missing"])
def test_current_package_completeness_fails_before_manifest_validation(
    tmp_path: Path, mutation: str
) -> None:
    fixture = CurrentMigrationFixture(tmp_path)
    if mutation == "extra":
        (fixture.migration_dir / "extra.txt").write_text("extra\n", encoding="utf-8")
    else:
        (fixture.migration_dir / "pre_application_snapshot.json").unlink()
    _payload, manifest_path, manifest_sha256 = fixture.build_manifest()
    with pytest.raises(
        git_auth.GitProvenanceAuthorizationError,
        match="current migration package inventory file count",
    ):
        fixture.validate(manifest_path, manifest_sha256)


def test_tamper_after_manifest_still_fails_per_file_sha(tmp_path: Path) -> None:
    fixture = CurrentMigrationFixture(tmp_path)
    payload, manifest_path, manifest_sha256 = fixture.build_manifest()
    target = fixture.migration_dir / "pre_application_snapshot.json"
    original = target.read_bytes()
    target.write_bytes(bytes([original[0] ^ 1]) + original[1:])
    with pytest.raises(
        git_auth.GitProvenanceAuthorizationError,
        match="current migration package inventory digest",
    ):
        fixture.validate(manifest_path, manifest_sha256)
    with pytest.raises(
        git_auth.GitProvenanceAuthorizationError,
        match="manifest file SHA-256 mismatch",
    ):
        git_auth._validate_files(
            payload,
            root=fixture.repo,
            authorization_id=fixture.authorization_id,
            migration_execution_id=fixture.migration_id,
            profile=fixture.profile,
        )


@pytest.mark.parametrize(
    ("execution_id", "file_count", "inventory_sha256"),
    [
        (MIGRATION_061_EXECUTION_ID, None, None),
        (None, MIGRATION_061_FILE_COUNT, None),
        (None, None, MIGRATION_061_INVENTORY_SHA256),
        (MIGRATION_061_EXECUTION_ID, MIGRATION_061_FILE_COUNT, None),
        (MIGRATION_061_EXECUTION_ID, None, MIGRATION_061_INVENTORY_SHA256),
        (None, MIGRATION_061_FILE_COUNT, MIGRATION_061_INVENTORY_SHA256),
    ],
)
def test_partial_current_identity_profile_fails_closed(
    tmp_path: Path,
    execution_id: str | None,
    file_count: int | None,
    inventory_sha256: str | None,
) -> None:
    fixture = CurrentMigrationFixture(tmp_path)
    _payload, manifest_path, manifest_sha256 = fixture.build_manifest()
    malformed = _profile(
        current_execution_id=execution_id,
        current_file_count=file_count,
        current_inventory_sha256=inventory_sha256,
    )
    with pytest.raises(
        git_auth.GitProvenanceAuthorizationError,
        match="current migration identity fields must be all populated or all None",
    ):
        fixture.validate(manifest_path, manifest_sha256, profile=malformed)


def test_live_four_token_profiles_are_atomically_bound_to_current_061() -> None:
    proof = git_auth.FOUR_TOKEN_PROOF_AUTHORIZATION_PROFILE
    operational = git_auth.FOUR_TOKEN_STANDARD_FOUR_HOUR_AUTHORIZATION_PROFILE
    assert (
        proof.migration_package_kind,
        proof.migration_package_root,
        proof.current_migration_execution_id,
        proof.current_migration_expected_file_count,
        proof.current_migration_expected_inventory_sha256,
        proof.historical_migration_packages,
    ) == (
        operational.migration_package_kind,
        operational.migration_package_root,
        operational.current_migration_execution_id,
        operational.current_migration_expected_file_count,
        operational.current_migration_expected_inventory_sha256,
        operational.historical_migration_packages,
    )
    assert proof.migration_package_kind == MIGRATION_061_KIND
    assert proof.migration_package_root == MIGRATION_061_ROOT
    assert proof.current_migration_execution_id == MIGRATION_061_EXECUTION_ID
    assert proof.current_migration_expected_file_count == MIGRATION_061_FILE_COUNT
    assert (
        proof.current_migration_expected_inventory_sha256
        == MIGRATION_061_INVENTORY_SHA256
    )


def test_ordinary_profiles_remain_unconstrained() -> None:
    for profile in (
        git_auth.ORDINARY_AUTHORIZATION_PROFILE,
        git_auth.STANDARD_FOUR_HOUR_AUTHORIZATION_PROFILE,
    ):
        assert profile.current_migration_execution_id is None
        assert profile.current_migration_expected_file_count is None
        assert profile.current_migration_expected_inventory_sha256 is None
        assert profile.migration_package_root == git_auth.MIGRATION_PACKAGE_ROOT
        assert profile.migration_package_kind == git_auth.MIGRATION_PACKAGE_KIND


def _historical_059_package() -> git_auth.HistoricalMigrationPackage:
    return next(
        package
        for package in git_auth.FOUR_TOKEN_HISTORICAL_MIGRATION_PACKAGES
        if package.package_root == MIGRATION_059_ROOT
    )


def test_real_historical_059_declaration_and_enumeration_pass() -> None:
    package = _historical_059_package()
    files = _inventory(
        REPOSITORY_ROOT,
        package_root=MIGRATION_059_ROOT,
        execution_id=MIGRATION_059_EXECUTION_ID,
    )
    assert package.execution_id == MIGRATION_059_EXECUTION_ID
    assert package.evidence_class == HISTORICAL_MIGRATION_059_KIND
    assert package.expected_file_count == MIGRATION_059_FILE_COUNT
    assert package.expected_inventory_sha256 == MIGRATION_059_INVENTORY_SHA256
    assert package.inventory_sha256(files) == MIGRATION_059_INVENTORY_SHA256
    records = git_auth.enumerate_historical_migration_evidence(
        repository_root=REPOSITORY_ROOT,
        historical_migration_packages=(package,),
        tracked_operator_runs_paths=set(),
    )
    assert len(records) == MIGRATION_059_FILE_COUNT


@pytest.mark.parametrize("mutation", ["missing", "extra", "mutated"])
def test_disposable_historical_059_tamper_fails_closed(
    tmp_path: Path, mutation: str
) -> None:
    source = REPOSITORY_ROOT / MIGRATION_059_ROOT / MIGRATION_059_EXECUTION_ID
    target = tmp_path / MIGRATION_059_ROOT / MIGRATION_059_EXECUTION_ID
    shutil.copytree(source, target)
    if mutation == "missing":
        (target / "pre_application_snapshot.json").unlink()
    elif mutation == "extra":
        (target / "extra.txt").write_text("extra\n", encoding="utf-8")
    else:
        member = target / "pre_application_snapshot.json"
        member.chmod(member.stat().st_mode | stat.S_IWUSR)
        member.write_bytes(member.read_bytes() + b"\n")
    with pytest.raises(git_auth.GitProvenanceAuthorizationError):
        git_auth.enumerate_historical_migration_evidence(
            repository_root=tmp_path,
            historical_migration_packages=(_historical_059_package(),),
            tracked_operator_runs_paths=set(),
        )


def test_current_and_historical_roots_are_exclusive() -> None:
    profile = git_auth.FOUR_TOKEN_PROOF_AUTHORIZATION_PROFILE
    historical_roots = tuple(
        package.package_root for package in profile.historical_migration_packages
    )
    assert profile.migration_package_root == MIGRATION_061_ROOT
    assert MIGRATION_061_ROOT not in historical_roots
    assert historical_roots[-1] == MIGRATION_059_ROOT
    assert MIGRATION_059_ROOT != profile.migration_package_root
    assert len(historical_roots) == len(set(historical_roots)) == 6


def test_consumed_512f2436_authorization_remains_unusable() -> None:
    path = (
        REPOSITORY_ROOT
        / "operator-runs/v2-9-8b-four-token-standard-four-hour-final-authorization"
        / CONSUMED_AUTHORIZATION_ID
        / "final_authorization.json"
    )
    document = json.loads(path.read_text(encoding="utf-8"))
    assert document["authorization_id"] == CONSUMED_AUTHORIZATION_ID
    assert document["migration_execution_id"] == MIGRATION_059_EXECUTION_ID
    assert document["authoritative_database"]["migration_count"] == 59
    assert document["authoritative_database"]["migration_head"].startswith("059_")
    assert document["one_shot_policy"] == {
        "allowed_invocation_count": 1,
        "automatic_retry_allowed": False,
        "manual_rerun_allowed": False,
        "restart_allowed": False,
        "resume_allowed": False,
        "successor_allowed": False,
    }
    profile = git_auth.FOUR_TOKEN_STANDARD_FOUR_HOUR_AUTHORIZATION_PROFILE
    assert document["migration_execution_id"] != profile.current_migration_execution_id
    assert profile.migration_package_root == MIGRATION_061_ROOT
