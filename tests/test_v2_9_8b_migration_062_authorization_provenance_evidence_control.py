"""Bounded proof for the migration-062 authorization-provenance cutover.

The real migration packages and authoritative database are read-only inputs.
Every mutation test uses a disposable copy. No authorization package or
application marker is created under a production root.
"""

from __future__ import annotations

import hashlib
from pathlib import Path

import pytest

from printer_v1.operator_cli import git_provenance_authorization_manifest as git_auth


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
AUTHORITATIVE_DB = REPOSITORY_ROOT / "data/printer_v1.sqlite3"
AUTHORIZATION_ROOT = (
    REPOSITORY_ROOT
    / "operator-runs/v2-9-8b-four-token-standard-four-hour-final-authorization"
)
MIGRATION_061_ROOT = "operator-runs/v2-9-8b-migration-061-application"
MIGRATION_062_ROOT = "operator-runs/v2-9-8b-migration-062-application"
MIGRATION_062_EXECUTION_ID = "MIGRATION_062_20260828T182504Z"
MIGRATION_062_KIND = "MIGRATION_062_EVIDENCE"
MIGRATION_062_FILE_COUNT = 4
MIGRATION_062_INVENTORY_SHA256 = (
    "fa617f77f288705e7e8a4d3676f78feee041f098292a59d431a60e66624bcd02"
)
MIGRATION_061_HISTORICAL_INVENTORY_SHA256 = (
    "ff8aefa1c0ee3fe4ec2063400a97cd81b8311bc4aa23dd402614bb609659a459"
)
CONSUMED_AUTHORIZATION_ID = (
    "V2_9_8B_FOUR_TOKEN_STD4H_AUTH_20260827T122355Z_8e43eae7"
)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _db_identity() -> tuple[int, int, int, str]:
    info = AUTHORITATIVE_DB.stat()
    return info.st_size, info.st_ino, info.st_mtime_ns, _sha256(AUTHORITATIVE_DB)


def _authorization_inventory() -> tuple[str, ...]:
    if not AUTHORIZATION_ROOT.is_dir():
        return ()
    return tuple(
        item.relative_to(AUTHORIZATION_ROOT).as_posix()
        for item in sorted(AUTHORIZATION_ROOT.rglob("*"))
        if item.is_file() or item.is_symlink()
    )


@pytest.fixture(scope="module", autouse=True)
def _prove_no_authority_or_database_mutation():
    before_db = _db_identity()
    before_authorizations = _authorization_inventory()
    yield
    assert _db_identity() == before_db
    assert _authorization_inventory() == before_authorizations


def test_both_four_token_profiles_bind_exact_current_migration_062() -> None:
    expected = (
        MIGRATION_062_ROOT,
        MIGRATION_062_KIND,
        MIGRATION_062_EXECUTION_ID,
        MIGRATION_062_FILE_COUNT,
        MIGRATION_062_INVENTORY_SHA256,
    )
    assert git_auth.MIGRATION_062_PACKAGE_ROOT == MIGRATION_062_ROOT
    assert git_auth.MIGRATION_062_PACKAGE_KIND == MIGRATION_062_KIND
    assert (
        git_auth.FOUR_TOKEN_CURRENT_MIGRATION_062_EXECUTION_ID
        == MIGRATION_062_EXECUTION_ID
    )
    assert (
        git_auth.FOUR_TOKEN_CURRENT_MIGRATION_062_EXPECTED_FILE_COUNT
        == MIGRATION_062_FILE_COUNT
    )
    assert (
        git_auth.FOUR_TOKEN_CURRENT_MIGRATION_062_EXPECTED_INVENTORY_SHA256
        == MIGRATION_062_INVENTORY_SHA256
    )
    for profile in (
        git_auth.FOUR_TOKEN_PROOF_AUTHORIZATION_PROFILE,
        git_auth.FOUR_TOKEN_STANDARD_FOUR_HOUR_AUTHORIZATION_PROFILE,
    ):
        assert (
            profile.migration_package_root,
            profile.migration_package_kind,
            profile.current_migration_execution_id,
            profile.current_migration_expected_file_count,
            profile.current_migration_expected_inventory_sha256,
        ) == expected


def test_migration_061_is_seventh_immutable_historical_package() -> None:
    packages = git_auth.FOUR_TOKEN_HISTORICAL_MIGRATION_PACKAGES
    assert len(packages) == 7
    historical_061 = packages[-1]
    assert historical_061 == git_auth.HistoricalMigrationPackage(
        package_root=MIGRATION_061_ROOT,
        execution_id="MIGRATION_061_20260823T200709Z",
        evidence_class="HISTORICAL_MIGRATION_061_EVIDENCE",
        expected_file_count=5,
        expected_inventory_sha256=MIGRATION_061_HISTORICAL_INVENTORY_SHA256,
    )
    for profile in (
        git_auth.FOUR_TOKEN_PROOF_AUTHORIZATION_PROFILE,
        git_auth.FOUR_TOKEN_STANDARD_FOUR_HOUR_AUTHORIZATION_PROFILE,
    ):
        assert profile.historical_migration_packages == packages
        assert MIGRATION_061_ROOT != profile.migration_package_root


def test_real_migration_062_package_matches_committed_complete_inventory() -> None:
    files = git_auth._inventory_bound_package_files(
        root=REPOSITORY_ROOT,
        package_dir=(
            REPOSITORY_ROOT / MIGRATION_062_ROOT / MIGRATION_062_EXECUTION_ID
        ),
        package_prefix=f"{MIGRATION_062_ROOT}/{MIGRATION_062_EXECUTION_ID}",
        label="migration-062 current evidence",
    )
    assert len(files) == MIGRATION_062_FILE_COUNT
    assert git_auth.compute_historical_migration_inventory_sha256(
        package_root=MIGRATION_062_ROOT,
        execution_id=MIGRATION_062_EXECUTION_ID,
        evidence_class=MIGRATION_062_KIND,
        files=files,
    ) == MIGRATION_062_INVENTORY_SHA256


def test_consumed_8e43eae7_is_diagnostic_history_only() -> None:
    assert (
        git_auth._terminal_disposition_for(CONSUMED_AUTHORIZATION_ID)
        == "CONSUMED_CHILD_EXITED_ZERO"
    )
    assert (
        git_auth._terminal_disposition_for(f"{CONSUMED_AUTHORIZATION_ID}_LOOKALIKE")
        == git_auth.DEFAULT_TERMINAL_DISPOSITION
    )
    approved_ids = sorted(
        item.name
        for item in AUTHORIZATION_ROOT.iterdir()
        if item.is_dir() and (item / "final_authorization.json").is_file()
    )
    records = git_auth.enumerate_historical_authorization_evidence(
        repository_root=REPOSITORY_ROOT,
        current_authorization_id="V2_9_8B_FOUR_TOKEN_STD4H_AUTH_FUTURE_TESTONLY",
        approved_historical_authorization_ids=approved_ids,
        tracked_operator_runs_paths=set(),
        authorization_package_roots=(
            "operator-runs/v2-9-8b-four-token-standard-four-hour-final-authorization",
        ),
        current_authorization_package_root=(
            "operator-runs/v2-9-8b-four-token-standard-four-hour-final-authorization"
        ),
    )
    consumed_records = tuple(
        item for item in records if item["authorization_id"] == CONSUMED_AUTHORIZATION_ID
    )
    assert consumed_records
    assert {
        item["terminal_disposition"] for item in consumed_records
    } == {"CONSUMED_CHILD_EXITED_ZERO"}
