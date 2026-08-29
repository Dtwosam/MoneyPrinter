"""Bounded, fail-closed Git-provenance authorization manifest validator.

This module implements the approved
``V2-9.8B WINDOW_15M One-Shot Wrapper Git-Provenance Compatibility`` design and
its authoritative ignored-evidence visibility repair.

It converts an already-produced, authorization-bound, out-of-repository manifest
and one-attempt application marker into a validated exact repository-relative
untracked-file allowlist that the existing ``capture_git_provenance()`` helper can
accept without weakening any launch-time Git safety rule.

The validator:

* reads explicit external manifest and marker paths and their expected SHA-256;
* parses both exact schemas with no extra keys and no duplicate keys;
* validates the referenced repository-local final-authorization document;
* validates every manifest file's exact repository-relative path, package root,
  size, and SHA-256;
* reconciles committed historical ``operator-runs/`` files bound by the exact
  Git HEAD with current manifest-bound visible and ignored untracked evidence;
* binds the marker to the manifest SHA-256 and to the allowed-file-set digest.

It makes no network request, no database read or write, and creates no files.
It only reads the named files, walks the bounded ``operator-runs/`` namespace,
and runs read-only ``git`` plumbing commands.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import stat
import subprocess
from typing import Any, Callable, Collection, Iterable, Mapping


GIT_COMMAND_TIMEOUT_SECONDS = 5.0

MANIFEST_SCHEMA_VERSION = "PRINTER_V1_GIT_PROVENANCE_MANIFEST_V2"
APPLICATION_MARKER_SCHEMA_VERSION = "PRINTER_V1_APPLICATION_MARKER_V1"

MIGRATION_PACKAGE_KIND = "MIGRATION_050_EVIDENCE"
AUTHORIZATION_PACKAGE_KIND = "WINDOW_15M_AUTHORIZATION_EVIDENCE"
HISTORICAL_AUTHORIZATION_EVIDENCE_CLASS = (
    "HISTORICAL_WINDOW_15M_AUTHORIZATION_EVIDENCE"
)
PACKAGE_KINDS = (MIGRATION_PACKAGE_KIND, AUTHORIZATION_PACKAGE_KIND)

OPERATOR_RUNS_ROOT = "operator-runs"
MIGRATION_PACKAGE_ROOT = "operator-runs/v2-9-8b-authoritative-mig050"
AUTHORIZATION_PACKAGE_ROOT = "operator-runs/v2-9-8b-window-15m-final-authorization"

# The controlled migration-055 application is the schema transition that produced
# the current authoritative database. It is a distinct current-evidence identity
# and never a rename of the historical migration-050 evidence contract.
MIGRATION_055_PACKAGE_KIND = "MIGRATION_055_EVIDENCE"
MIGRATION_055_PACKAGE_ROOT = "operator-runs/v2-9-8b-migration-055-application"

# The controlled migration-056 application is the schema transition that admits a
# bounded four-token proof, because it owns the immutable pre-lifecycle terminal
# provenance. It is its own current-evidence identity and never a rename of the
# migration-050 or migration-055 evidence contracts.
MIGRATION_056_PACKAGE_KIND = "MIGRATION_056_EVIDENCE"
MIGRATION_056_PACKAGE_ROOT = "operator-runs/v2-9-8b-migration-056-application"

# The controlled migration-057 application is the current schema transition for
# the four-token proof after persistent pre-lifecycle discovery-refresh ownership
# was added. It is its own current-evidence identity and never renames or absorbs
# the migration-050, migration-055, or migration-056 evidence contracts.
MIGRATION_057_PACKAGE_KIND = "MIGRATION_057_EVIDENCE"
MIGRATION_057_PACKAGE_ROOT = "operator-runs/v2-9-8b-migration-057-application"

# Migration 058 remains a distinct evidence identity after it is demoted to
# preserved historical schema-transition evidence by Migration 059.
MIGRATION_058_PACKAGE_KIND = "MIGRATION_058_EVIDENCE"
MIGRATION_058_PACKAGE_ROOT = "operator-runs/v2-9-8b-migration-058-application"

# Migration 059 remains a distinct evidence identity after it is demoted to
# preserved historical schema-transition evidence by Migration 061.
MIGRATION_059_PACKAGE_KIND = "MIGRATION_059_EVIDENCE"
MIGRATION_059_PACKAGE_ROOT = "operator-runs/v2-9-8b-migration-059-application"

# Migration 061 remains a distinct package identity after migration 062 promotes
# it to preserved historical schema-transition evidence.
MIGRATION_061_PACKAGE_KIND = "MIGRATION_061_EVIDENCE"
MIGRATION_061_PACKAGE_ROOT = "operator-runs/v2-9-8b-migration-061-application"

# The controlled migration-062 application is the singular current schema
# transition for both four-token authorities. Its exact execution and complete
# inventory identity are committed on the profiles below; filesystem discovery
# may only prove equality or fail closed.
MIGRATION_062_PACKAGE_KIND = "MIGRATION_062_EVIDENCE"
MIGRATION_062_PACKAGE_ROOT = "operator-runs/v2-9-8b-migration-062-application"

# Preserved historical schema-transition evidence. This class explains how the
# current database evolved; it never becomes current schema-transition authority
# and never carries authorization reuse authority.
HISTORICAL_MIGRATION_EVIDENCE_CLASS = "HISTORICAL_MIGRATION_050_EVIDENCE"
FOUR_TOKEN_HISTORICAL_MIGRATION_EXECUTION_ID = (
    "V2_9_8B_AUTHORITATIVE_MIG050_20260801T202423Z_f697cc0f"
)

# Migration 055 became preserved historical evidence once migration 056 took over
# current schema-transition authority. It keeps its own evidence class and
# execution identity; it is demoted, never renamed or absorbed.
HISTORICAL_MIGRATION_055_EVIDENCE_CLASS = "HISTORICAL_MIGRATION_055_EVIDENCE"
FOUR_TOKEN_HISTORICAL_MIGRATION_055_EXECUTION_ID = "MIGRATION_055_20260813T220109Z"

# Migration 056 became preserved historical evidence once migration 057 took over
# current schema-transition authority. It keeps its own evidence class and
# execution identity; it is demoted, never renamed or absorbed.
HISTORICAL_MIGRATION_056_EVIDENCE_CLASS = "HISTORICAL_MIGRATION_056_EVIDENCE"
FOUR_TOKEN_HISTORICAL_MIGRATION_056_EXECUTION_ID = "MIGRATION_056_20260815T164802Z"

# Migration 057 became preserved historical evidence once migration 058 took over
# current schema-transition authority. It keeps its own evidence class and
# execution identity; it is demoted, never renamed or absorbed.
HISTORICAL_MIGRATION_057_EVIDENCE_CLASS = "HISTORICAL_MIGRATION_057_EVIDENCE"
FOUR_TOKEN_HISTORICAL_MIGRATION_057_EXECUTION_ID = "MIGRATION_057_20260816T191558Z"

# Migration 058 became preserved historical evidence once migration 059 took
# over current schema-transition authority. It keeps its own evidence class and
# exact execution identity; it is demoted, never renamed or absorbed.
HISTORICAL_MIGRATION_058_EVIDENCE_CLASS = "HISTORICAL_MIGRATION_058_EVIDENCE"
FOUR_TOKEN_HISTORICAL_MIGRATION_058_EXECUTION_ID = "MIGRATION_058_20260818T082552Z"

# Migration 059 became preserved historical evidence once Migration 061 took
# over current schema-transition authority. It keeps its own historical class
# and exact execution identity; it is demoted, never renamed or absorbed.
HISTORICAL_MIGRATION_059_EVIDENCE_CLASS = "HISTORICAL_MIGRATION_059_EVIDENCE"
FOUR_TOKEN_HISTORICAL_MIGRATION_059_EXECUTION_ID = "MIGRATION_059_20260821T095456Z"

# Migration 061 became preserved historical evidence once Migration 062 took
# over current schema-transition authority. Its historical class deliberately
# produces a different inventory digest from its former current class.
HISTORICAL_MIGRATION_061_EVIDENCE_CLASS = "HISTORICAL_MIGRATION_061_EVIDENCE"
FOUR_TOKEN_HISTORICAL_MIGRATION_061_EXECUTION_ID = "MIGRATION_061_20260823T200709Z"

# Immutable COMPLETE current inventory identity for both four-token profiles.
FOUR_TOKEN_CURRENT_MIGRATION_062_EXECUTION_ID = "MIGRATION_062_20260828T182504Z"
FOUR_TOKEN_CURRENT_MIGRATION_062_EXPECTED_FILE_COUNT = 4
FOUR_TOKEN_CURRENT_MIGRATION_062_EXPECTED_INVENTORY_SHA256 = (
    "fa617f77f288705e7e8a4d3676f78feee041f098292a59d431a60e66624bcd02"
)

# Immutable COMPLETE inventory identity for every declared historical migration
# package. These are committed constants bound by the authorization's Git HEAD.
# Filesystem discovery may only prove equality against them or fail closed; it
# never defines a new trusted package identity.
FOUR_TOKEN_HISTORICAL_MIGRATION_EXPECTED_FILE_COUNT = 12
FOUR_TOKEN_HISTORICAL_MIGRATION_EXPECTED_INVENTORY_SHA256 = (
    "2bcbfdd3e9b1bf0a2f53bcdd386d0f782b698b883d5d4bb43d1a8a7bd795f8d5"
)
FOUR_TOKEN_HISTORICAL_MIGRATION_055_EXPECTED_FILE_COUNT = 5
FOUR_TOKEN_HISTORICAL_MIGRATION_055_EXPECTED_INVENTORY_SHA256 = (
    "c00443733269993b40353b61390753a49dad184541120916c6e2a400fdd9e625"
)
FOUR_TOKEN_HISTORICAL_MIGRATION_056_EXPECTED_FILE_COUNT = 6
FOUR_TOKEN_HISTORICAL_MIGRATION_056_EXPECTED_INVENTORY_SHA256 = (
    "4918774b95998aab821d69d06854665697347664faf04a3340f2299db95868f3"
)
FOUR_TOKEN_HISTORICAL_MIGRATION_057_EXPECTED_FILE_COUNT = 6
FOUR_TOKEN_HISTORICAL_MIGRATION_057_EXPECTED_INVENTORY_SHA256 = (
    "9272f596e7a82c3cfe9d824595be74f34c7203dccab3bd541c187dc236519535"
)
FOUR_TOKEN_HISTORICAL_MIGRATION_058_EXPECTED_FILE_COUNT = 11
FOUR_TOKEN_HISTORICAL_MIGRATION_058_EXPECTED_INVENTORY_SHA256 = (
    "d6dc1431a3a99a8c2f521a3033948d11bbdd4e7151ddabc1127c7fb3b9138fa8"
)
FOUR_TOKEN_HISTORICAL_MIGRATION_059_EXPECTED_FILE_COUNT = 5
FOUR_TOKEN_HISTORICAL_MIGRATION_059_EXPECTED_INVENTORY_SHA256 = (
    "d23c4f4bbf2b4683c69038bb6fc372f85c52e280b24662cb46c133690b1479c6"
)
FOUR_TOKEN_HISTORICAL_MIGRATION_061_EXPECTED_FILE_COUNT = 5
FOUR_TOKEN_HISTORICAL_MIGRATION_061_EXPECTED_INVENTORY_SHA256 = (
    "ff8aefa1c0ee3fe4ec2063400a97cd81b8311bc4aa23dd402614bb609659a459"
)

# Preserved historical reconciliation evidence is neither schema-transition
# evidence nor authorization evidence.  These two classes explain exact
# operator repair artifacts only and carry no execution/reuse authority.
PRE_ADMISSION_2364_RECONCILIATION_PACKAGE_ROOT = (
    "operator-runs/v2-9-8b-pre-admission-2364-reconciliation"
)
PRE_ADMISSION_2364_RECONCILIATION_EXECUTION_ID = "RECONCILE_20260820T174324Z"
PRE_ADMISSION_2364_RECONCILIATION_EVIDENCE_CLASS = (
    "HISTORICAL_PRE_ADMISSION_2364_RECONCILIATION_EVIDENCE"
)
PRE_ADMISSION_2364_RECONCILIATION_EXPECTED_FILE_COUNT = 3
PRE_ADMISSION_2364_RECONCILIATION_EXPECTED_INVENTORY_SHA256 = (
    "f3b030d9b396380efd87310e4b1e72161271bbd0869ed4fae2b533d4e338bfcd"
)

ORPHAN_FACTORY_RUN_RECONCILIATION_PACKAGE_ROOT = (
    "operator-runs/v2-9-8b-historical-orphan-factory-run-reconciliation"
)
ORPHAN_FACTORY_RUN_RECONCILIATION_EXECUTION_ID = "RECONCILE_20260820T192309Z"
ORPHAN_FACTORY_RUN_RECONCILIATION_EVIDENCE_CLASS = (
    "HISTORICAL_ORPHAN_FACTORY_RUN_RECONCILIATION_EVIDENCE"
)
ORPHAN_FACTORY_RUN_RECONCILIATION_EXPECTED_FILE_COUNT = 4
ORPHAN_FACTORY_RUN_RECONCILIATION_EXPECTED_INVENTORY_SHA256 = (
    "23ea78d77776c1bb566ec098623eb2957dff280a15701fd2fe4779d0e82d0ff3"
)

PAIR_READY_RESIDUAL_RECONCILIATION_PACKAGE_ROOT = (
    "operator-runs/v2-9-8b-pair-ready-residual-reconciliation"
)
PAIR_READY_RESIDUAL_RECONCILIATION_EXECUTION_ID = (
    "RECONCILIATION_20260821T110736Z"
)
PAIR_READY_RESIDUAL_RECONCILIATION_EVIDENCE_CLASS = (
    "HISTORICAL_PAIR_READY_RESIDUAL_RECONCILIATION_EVIDENCE"
)
PAIR_READY_RESIDUAL_RECONCILIATION_EXPECTED_FILE_COUNT = 5
PAIR_READY_RESIDUAL_RECONCILIATION_EXPECTED_INVENTORY_SHA256 = (
    "94cb775d8f1a0d095669c3a1285b8484d7bfbae62c50bf327669516d942285d7"
)

REQUIRED_MAIN_WINDOW = "WINDOW_15M"
REQUIRED_COMMAND_MODE = "run"


# Domain separator for the immutable historical-package completeness identity.
# It binds a digest to this exact purpose, so an inventory digest can never be
# replayed from another digest domain.
HISTORICAL_MIGRATION_INVENTORY_DOMAIN = (
    "PRINTER_V1_HISTORICAL_MIGRATION_PACKAGE_INVENTORY_V1"
)
HISTORICAL_RECONCILIATION_INVENTORY_DOMAIN = (
    "PRINTER_V1_HISTORICAL_RECONCILIATION_PACKAGE_INVENTORY_V1"
)


def compute_historical_migration_inventory_sha256(
    *,
    package_root: str,
    execution_id: str,
    evidence_class: str,
    files: Iterable[Mapping[str, Any]],
) -> str:
    """Canonically digest one COMPLETE historical migration package inventory.

    The digest binds the exact package identity and every member file by
    normalized repository-relative path, byte size and SHA-256. It is
    deterministic and domain-separated, so it cannot be replayed for a different
    package root, execution ID, evidence class, or digest purpose.
    """
    records = sorted(
        (
            {
                "path": _require_str(
                    item["path"], label="historical migration inventory path"
                ),
                "sha256": _require_hex64(
                    item["sha256"], label="historical migration inventory sha256"
                ),
                "size": int(item["size"]),
            }
            for item in files
        ),
        key=lambda record: record["path"],
    )
    canonical = json.dumps(
        {
            "domain": HISTORICAL_MIGRATION_INVENTORY_DOMAIN,
            "package_root": package_root,
            "execution_id": execution_id,
            "evidence_class": evidence_class,
            "file_count": len(records),
            "files": records,
        },
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
        allow_nan=False,
    )
    return hashlib.sha256(canonical.encode("ascii")).hexdigest()


def compute_historical_reconciliation_inventory_sha256(
    *,
    package_root: str,
    execution_id: str,
    evidence_class: str,
    files: Iterable[Mapping[str, Any]],
) -> str:
    """Digest one complete historical reconciliation package declaration."""
    records = sorted(
        (
            {
                "path": _require_str(
                    item["path"], label="historical reconciliation inventory path"
                ),
                "sha256": _require_hex64(
                    item["sha256"],
                    label="historical reconciliation inventory sha256",
                ),
                "size": int(item["size"]),
            }
            for item in files
        ),
        key=lambda record: record["path"],
    )
    canonical = json.dumps(
        {
            "domain": HISTORICAL_RECONCILIATION_INVENTORY_DOMAIN,
            "package_root": package_root,
            "execution_id": execution_id,
            "evidence_class": evidence_class,
            "file_count": len(records),
            "files": records,
        },
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
        allow_nan=False,
    )
    return hashlib.sha256(canonical.encode("ascii")).hexdigest()


@dataclass(frozen=True)
class HistoricalMigrationPackage:
    """One exact, profile-bound preserved historical migration package.

    Trust is the exact package root plus the exact execution ID, plus an
    immutable declaration of the package's COMPLETE inventory. Directory
    presence alone creates nothing, no sibling package under the same root is
    implied, and this class never satisfies current-package identity.

    ``expected_file_count`` and ``expected_inventory_sha256`` are mandatory and
    carry no defaults. They come from committed source at the bound Git HEAD,
    never from filesystem discovery, so a partially eroded, byte-modified or
    intruded package can never be silently redefined by a fresh manifest
    preparation.
    """

    package_root: str
    execution_id: str
    expected_file_count: int
    expected_inventory_sha256: str
    evidence_class: str = HISTORICAL_MIGRATION_EVIDENCE_CLASS

    @property
    def package_prefix(self) -> str:
        return f"{self.package_root}/{self.execution_id}"

    def inventory_sha256(self, files: Iterable[Mapping[str, Any]]) -> str:
        """Digest an actual inventory under this package's exact identity."""
        return compute_historical_migration_inventory_sha256(
            package_root=self.package_root,
            execution_id=self.execution_id,
            evidence_class=self.evidence_class,
            files=files,
        )


@dataclass(frozen=True)
class HistoricalReconciliationFile:
    """One immutable member of a historical reconciliation package."""

    path: str
    size: int
    sha256: str


@dataclass(frozen=True)
class HistoricalReconciliationPackage:
    """One exact historical reconciliation package with committed members."""

    package_root: str
    execution_id: str
    evidence_class: str
    expected_file_count: int
    expected_inventory_sha256: str
    execution_directories: tuple[str, ...]
    files: tuple[HistoricalReconciliationFile, ...]

    def inventory_sha256(self) -> str:
        """Digest the committed member declarations under this identity."""
        return compute_historical_reconciliation_inventory_sha256(
            package_root=self.package_root,
            execution_id=self.execution_id,
            evidence_class=self.evidence_class,
            files=(
                {"path": item.path, "sha256": item.sha256, "size": item.size}
                for item in self.files
            ),
        )


@dataclass(frozen=True)
class GitAuthorizationProfile:
    command_mode: str
    authorization_package_root: str
    authorization_package_kind: str
    manifest_schema_version: str
    historical_authorization_package_roots: tuple[str, ...]
    # Exact current migration evidence for this profile. The defaults preserve
    # identical migration-050 behavior for every previously defined profile.
    migration_package_root: str = MIGRATION_PACKAGE_ROOT
    migration_package_kind: str = MIGRATION_PACKAGE_KIND
    # Optional immutable current-package identity. All three fields are either
    # populated together or all None. Ordinary profiles intentionally keep None
    # and preserve their caller-supplied execution-ID semantics.
    current_migration_execution_id: str | None = None
    current_migration_expected_file_count: int | None = None
    current_migration_expected_inventory_sha256: str | None = None
    # Exact preserved historical migration evidence for this profile. The empty
    # default keeps ordinary and standard-four-hour manifest semantics, schema
    # key sets, and reconciliation behavior byte-for-byte unchanged.
    historical_migration_packages: tuple[HistoricalMigrationPackage, ...] = ()
    # Exact historical operator-reconciliation evidence.  It is deliberately
    # profile data rather than public manifest data, and therefore can never be
    # supplied or redefined by a future authorization preparation.
    historical_reconciliation_packages: tuple[
        HistoricalReconciliationPackage, ...
    ] = ()


ORDINARY_AUTHORIZATION_PROFILE = GitAuthorizationProfile(
    command_mode=REQUIRED_COMMAND_MODE,
    authorization_package_root=AUTHORIZATION_PACKAGE_ROOT,
    authorization_package_kind=AUTHORIZATION_PACKAGE_KIND,
    manifest_schema_version=MANIFEST_SCHEMA_VERSION,
    historical_authorization_package_roots=(AUTHORIZATION_PACKAGE_ROOT,),
)

STANDARD_FOUR_HOUR_AUTHORIZATION_PROFILE = GitAuthorizationProfile(
    command_mode="standard-four-hour-run",
    authorization_package_root=(
        "operator-runs/v2-9-8b-standard-four-hour-final-authorization"
    ),
    authorization_package_kind="STANDARD_FOUR_HOUR_AUTHORIZATION_EVIDENCE",
    manifest_schema_version="PRINTER_V1_GIT_PROVENANCE_MANIFEST_STANDARD_4H_V1",
    historical_authorization_package_roots=(
        AUTHORIZATION_PACKAGE_ROOT,
        "operator-runs/v2-9-8b-standard-four-hour-final-authorization",
    ),
)


# The preserved historical migration chain shared by every four-token authority.
#
# Migrations 050, 055, 056, 057, 058, 059 and 061 are the declared *required*
# historical packages. Each was demoted in turn when its successor took over
# current schema-transition authority; none is renamed, absorbed, or promoted
# back to current authority, which is Migration 062 alone.
#
# Every entry is mandatory for every manifest build, so declaring them requires
# their operator evidence to exist. That obligation is deliberate: it is the only
# way to explain their untracked bytes without publishing SQLite database images
# into the public Git remote.
#
# Every entry declares its COMPLETE inventory identity, so partial erosion, byte
# modification, intrusion, and a member that quietly became tracked all fail
# closed at fresh preparation rather than being silently re-bound into a new
# manifest.
FOUR_TOKEN_HISTORICAL_MIGRATION_PACKAGES: tuple[HistoricalMigrationPackage, ...] = (
    HistoricalMigrationPackage(
        package_root=MIGRATION_PACKAGE_ROOT,
        execution_id=FOUR_TOKEN_HISTORICAL_MIGRATION_EXECUTION_ID,
        evidence_class=HISTORICAL_MIGRATION_EVIDENCE_CLASS,
        expected_file_count=FOUR_TOKEN_HISTORICAL_MIGRATION_EXPECTED_FILE_COUNT,
        expected_inventory_sha256=(
            FOUR_TOKEN_HISTORICAL_MIGRATION_EXPECTED_INVENTORY_SHA256
        ),
    ),
    HistoricalMigrationPackage(
        package_root=MIGRATION_055_PACKAGE_ROOT,
        execution_id=FOUR_TOKEN_HISTORICAL_MIGRATION_055_EXECUTION_ID,
        evidence_class=HISTORICAL_MIGRATION_055_EVIDENCE_CLASS,
        expected_file_count=(
            FOUR_TOKEN_HISTORICAL_MIGRATION_055_EXPECTED_FILE_COUNT
        ),
        expected_inventory_sha256=(
            FOUR_TOKEN_HISTORICAL_MIGRATION_055_EXPECTED_INVENTORY_SHA256
        ),
    ),
    HistoricalMigrationPackage(
        package_root=MIGRATION_056_PACKAGE_ROOT,
        execution_id=FOUR_TOKEN_HISTORICAL_MIGRATION_056_EXECUTION_ID,
        evidence_class=HISTORICAL_MIGRATION_056_EVIDENCE_CLASS,
        expected_file_count=(
            FOUR_TOKEN_HISTORICAL_MIGRATION_056_EXPECTED_FILE_COUNT
        ),
        expected_inventory_sha256=(
            FOUR_TOKEN_HISTORICAL_MIGRATION_056_EXPECTED_INVENTORY_SHA256
        ),
    ),
    HistoricalMigrationPackage(
        package_root=MIGRATION_057_PACKAGE_ROOT,
        execution_id=FOUR_TOKEN_HISTORICAL_MIGRATION_057_EXECUTION_ID,
        evidence_class=HISTORICAL_MIGRATION_057_EVIDENCE_CLASS,
        expected_file_count=(
            FOUR_TOKEN_HISTORICAL_MIGRATION_057_EXPECTED_FILE_COUNT
        ),
        expected_inventory_sha256=(
            FOUR_TOKEN_HISTORICAL_MIGRATION_057_EXPECTED_INVENTORY_SHA256
        ),
    ),
    HistoricalMigrationPackage(
        package_root=MIGRATION_058_PACKAGE_ROOT,
        execution_id=FOUR_TOKEN_HISTORICAL_MIGRATION_058_EXECUTION_ID,
        evidence_class=HISTORICAL_MIGRATION_058_EVIDENCE_CLASS,
        expected_file_count=(
            FOUR_TOKEN_HISTORICAL_MIGRATION_058_EXPECTED_FILE_COUNT
        ),
        expected_inventory_sha256=(
            FOUR_TOKEN_HISTORICAL_MIGRATION_058_EXPECTED_INVENTORY_SHA256
        ),
    ),
    HistoricalMigrationPackage(
        package_root=MIGRATION_059_PACKAGE_ROOT,
        execution_id=FOUR_TOKEN_HISTORICAL_MIGRATION_059_EXECUTION_ID,
        evidence_class=HISTORICAL_MIGRATION_059_EVIDENCE_CLASS,
        expected_file_count=(
            FOUR_TOKEN_HISTORICAL_MIGRATION_059_EXPECTED_FILE_COUNT
        ),
        expected_inventory_sha256=(
            FOUR_TOKEN_HISTORICAL_MIGRATION_059_EXPECTED_INVENTORY_SHA256
        ),
    ),
    HistoricalMigrationPackage(
        package_root=MIGRATION_061_PACKAGE_ROOT,
        execution_id=FOUR_TOKEN_HISTORICAL_MIGRATION_061_EXECUTION_ID,
        evidence_class=HISTORICAL_MIGRATION_061_EVIDENCE_CLASS,
        expected_file_count=(
            FOUR_TOKEN_HISTORICAL_MIGRATION_061_EXPECTED_FILE_COUNT
        ),
        expected_inventory_sha256=(
            FOUR_TOKEN_HISTORICAL_MIGRATION_061_EXPECTED_INVENTORY_SHA256
        ),
    ),
)


FOUR_TOKEN_OPERATIONAL_HISTORICAL_RECONCILIATION_PACKAGES: tuple[
    HistoricalReconciliationPackage, ...
] = (
    HistoricalReconciliationPackage(
        package_root=PRE_ADMISSION_2364_RECONCILIATION_PACKAGE_ROOT,
        execution_id=PRE_ADMISSION_2364_RECONCILIATION_EXECUTION_ID,
        evidence_class=PRE_ADMISSION_2364_RECONCILIATION_EVIDENCE_CLASS,
        expected_file_count=(
            PRE_ADMISSION_2364_RECONCILIATION_EXPECTED_FILE_COUNT
        ),
        expected_inventory_sha256=(
            PRE_ADMISSION_2364_RECONCILIATION_EXPECTED_INVENTORY_SHA256
        ),
        execution_directories=(
            "RECONCILE_20260820T174244Z",
            "RECONCILE_20260820T174324Z",
        ),
        files=(
            HistoricalReconciliationFile(
                path=(
                    "operator-runs/v2-9-8b-pre-admission-2364-reconciliation/"
                    "RECONCILE_20260820T174324Z/disposable-root/"
                    "disposable-restore.sqlite3"
                ),
                size=112144384,
                sha256=(
                    "769befd90ab82e2ed7443b19ba8834dbf7807e0c0aaed20549e0e4ab6acc3847"
                ),
            ),
            HistoricalReconciliationFile(
                path=(
                    "operator-runs/v2-9-8b-pre-admission-2364-reconciliation/"
                    "RECONCILE_20260820T174324Z/reconciliation_evidence.json"
                ),
                size=1639,
                sha256=(
                    "ee538e004d5f1de9db6b4aff86002b8c2375fa547481ee1311917f1816ab17ad"
                ),
            ),
            HistoricalReconciliationFile(
                path=(
                    "operator-runs/v2-9-8b-pre-admission-2364-reconciliation/"
                    "RECONCILE_20260820T174324Z/verified-backup.sqlite3"
                ),
                size=112144384,
                sha256=(
                    "769befd90ab82e2ed7443b19ba8834dbf7807e0c0aaed20549e0e4ab6acc3847"
                ),
            ),
        ),
    ),
    HistoricalReconciliationPackage(
        package_root=ORPHAN_FACTORY_RUN_RECONCILIATION_PACKAGE_ROOT,
        execution_id=ORPHAN_FACTORY_RUN_RECONCILIATION_EXECUTION_ID,
        evidence_class=ORPHAN_FACTORY_RUN_RECONCILIATION_EVIDENCE_CLASS,
        expected_file_count=(
            ORPHAN_FACTORY_RUN_RECONCILIATION_EXPECTED_FILE_COUNT
        ),
        expected_inventory_sha256=(
            ORPHAN_FACTORY_RUN_RECONCILIATION_EXPECTED_INVENTORY_SHA256
        ),
        execution_directories=(
            "RECONCILE_20260820T185845Z",
            "RECONCILE_20260820T192309Z",
        ),
        files=(
            HistoricalReconciliationFile(
                path=(
                    "operator-runs/v2-9-8b-historical-orphan-factory-run-"
                    "reconciliation/RECONCILE_20260820T185845Z/"
                    "disposable-root/disposable-restore.sqlite3"
                ),
                size=112144384,
                sha256=(
                    "f167858a7a47c2837bced97223501f8d1c004d1c8c7a8177ed080c4e8d27f341"
                ),
            ),
            HistoricalReconciliationFile(
                path=(
                    "operator-runs/v2-9-8b-historical-orphan-factory-run-"
                    "reconciliation/RECONCILE_20260820T185845Z/"
                    "verified-backup.sqlite3"
                ),
                size=112144384,
                sha256=(
                    "f167858a7a47c2837bced97223501f8d1c004d1c8c7a8177ed080c4e8d27f341"
                ),
            ),
            HistoricalReconciliationFile(
                path=(
                    "operator-runs/v2-9-8b-historical-orphan-factory-run-"
                    "reconciliation/RECONCILE_20260820T192309Z/"
                    "disposable-root/disposable-restore.sqlite3"
                ),
                size=112144384,
                sha256=(
                    "f167858a7a47c2837bced97223501f8d1c004d1c8c7a8177ed080c4e8d27f341"
                ),
            ),
            HistoricalReconciliationFile(
                path=(
                    "operator-runs/v2-9-8b-historical-orphan-factory-run-"
                    "reconciliation/RECONCILE_20260820T192309Z/"
                    "verified-backup.sqlite3"
                ),
                size=112144384,
                sha256=(
                    "f167858a7a47c2837bced97223501f8d1c004d1c8c7a8177ed080c4e8d27f341"
                ),
            ),
        ),
    ),
    HistoricalReconciliationPackage(
        package_root=PAIR_READY_RESIDUAL_RECONCILIATION_PACKAGE_ROOT,
        execution_id=PAIR_READY_RESIDUAL_RECONCILIATION_EXECUTION_ID,
        evidence_class=PAIR_READY_RESIDUAL_RECONCILIATION_EVIDENCE_CLASS,
        expected_file_count=(
            PAIR_READY_RESIDUAL_RECONCILIATION_EXPECTED_FILE_COUNT
        ),
        expected_inventory_sha256=(
            PAIR_READY_RESIDUAL_RECONCILIATION_EXPECTED_INVENTORY_SHA256
        ),
        execution_directories=(
            PAIR_READY_RESIDUAL_RECONCILIATION_EXECUTION_ID,
        ),
        files=(
            HistoricalReconciliationFile(
                path=(
                    "operator-runs/v2-9-8b-pair-ready-residual-reconciliation/"
                    "RECONCILIATION_20260821T110736Z/"
                    "backup_and_disposable_rehearsal.json"
                ),
                size=306712,
                sha256=(
                    "a74406aec8e240d6627a04cf0299bbc95b35a45f2fd98261f60c040e3eb48cf0"
                ),
            ),
            HistoricalReconciliationFile(
                path=(
                    "operator-runs/v2-9-8b-pair-ready-residual-reconciliation/"
                    "RECONCILIATION_20260821T110736Z/"
                    "post_reconciliation_snapshot.json"
                ),
                size=92014,
                sha256=(
                    "633424430f850c70a58cd03a6fa4f73b6b89c8baab570946ad7bb79e899aa76c"
                ),
            ),
            HistoricalReconciliationFile(
                path=(
                    "operator-runs/v2-9-8b-pair-ready-residual-reconciliation/"
                    "RECONCILIATION_20260821T110736Z/"
                    "pre_reconciliation_snapshot.json"
                ),
                size=92083,
                sha256=(
                    "1f5a2b4b7ba16ec4f4378259bfe863f0bac5c4cd0ff5594c3154e3356b9e26e6"
                ),
            ),
            HistoricalReconciliationFile(
                path=(
                    "operator-runs/v2-9-8b-pair-ready-residual-reconciliation/"
                    "RECONCILIATION_20260821T110736Z/"
                    "reconcile_pair_ready_residual.py"
                ),
                size=33379,
                sha256=(
                    "64da79ef2cf1cae93f6fe4acb48f2c4f0c5d22214fc04ed05898776775c8c31a"
                ),
            ),
            HistoricalReconciliationFile(
                path=(
                    "operator-runs/v2-9-8b-pair-ready-residual-reconciliation/"
                    "RECONCILIATION_20260821T110736Z/"
                    "reconciliation_receipt.json"
                ),
                size=29684,
                sha256=(
                    "cbdd06a2cd33d1f1917c1b26210f9c27dc4a8b8384004cdb6462eca476544022"
                ),
            ),
        ),
    ),
)


FOUR_TOKEN_PROOF_AUTHORIZATION_PROFILE = GitAuthorizationProfile(
    command_mode="four-token-bounded-capacity-proof-run",
    authorization_package_root=(
        "operator-runs/v2-9-8b-four-token-final-authorization"
    ),
    authorization_package_kind="FOUR_TOKEN_PROOF_AUTHORIZATION_EVIDENCE",
    manifest_schema_version="PRINTER_V1_GIT_PROVENANCE_MANIFEST_FOUR_TOKEN_PROOF_V2",
    historical_authorization_package_roots=(
        AUTHORIZATION_PACKAGE_ROOT,
        "operator-runs/v2-9-8b-standard-four-hour-final-authorization",
        "operator-runs/v2-9-8b-four-token-final-authorization",
    ),
    migration_package_root=MIGRATION_062_PACKAGE_ROOT,
    migration_package_kind=MIGRATION_062_PACKAGE_KIND,
    current_migration_execution_id=FOUR_TOKEN_CURRENT_MIGRATION_062_EXECUTION_ID,
    current_migration_expected_file_count=(
        FOUR_TOKEN_CURRENT_MIGRATION_062_EXPECTED_FILE_COUNT
    ),
    current_migration_expected_inventory_sha256=(
        FOUR_TOKEN_CURRENT_MIGRATION_062_EXPECTED_INVENTORY_SHA256
    ),
    historical_migration_packages=FOUR_TOKEN_HISTORICAL_MIGRATION_PACKAGES,
    historical_reconciliation_packages=(
        FOUR_TOKEN_OPERATIONAL_HISTORICAL_RECONCILIATION_PACKAGES
    ),
)


# The fourth distinct Git authorization authority: one operator-approved bounded
# operational campaign of exactly four through-4h token slots across exactly two
# governed cycles of exactly two fresh slots each.
#
# It shares no authorization identity with the ordinary, two-token
# standard-four-hour, or four-token proof authorities. Historical visibility over
# their roots is enumeration only and never creates reuse authority: no ordinary,
# Standard-4H or proof authorization can be reinterpreted as authority for this
# mode.
FOUR_TOKEN_STANDARD_FOUR_HOUR_AUTHORIZATION_PROFILE = GitAuthorizationProfile(
    command_mode="four-token-standard-four-hour-run",
    authorization_package_root=(
        "operator-runs/v2-9-8b-four-token-standard-four-hour-final-authorization"
    ),
    authorization_package_kind=(
        "FOUR_TOKEN_STANDARD_FOUR_HOUR_AUTHORIZATION_EVIDENCE"
    ),
    manifest_schema_version=(
        "PRINTER_V1_GIT_PROVENANCE_MANIFEST_FOUR_TOKEN_STANDARD_4H_V1"
    ),
    historical_authorization_package_roots=(
        AUTHORIZATION_PACKAGE_ROOT,
        "operator-runs/v2-9-8b-standard-four-hour-final-authorization",
        "operator-runs/v2-9-8b-four-token-final-authorization",
        "operator-runs/v2-9-8b-four-token-standard-four-hour-final-authorization",
    ),
    migration_package_root=MIGRATION_062_PACKAGE_ROOT,
    migration_package_kind=MIGRATION_062_PACKAGE_KIND,
    current_migration_execution_id=FOUR_TOKEN_CURRENT_MIGRATION_062_EXECUTION_ID,
    current_migration_expected_file_count=(
        FOUR_TOKEN_CURRENT_MIGRATION_062_EXPECTED_FILE_COUNT
    ),
    current_migration_expected_inventory_sha256=(
        FOUR_TOKEN_CURRENT_MIGRATION_062_EXPECTED_INVENTORY_SHA256
    ),
    historical_migration_packages=FOUR_TOKEN_HISTORICAL_MIGRATION_PACKAGES,
    historical_reconciliation_packages=(
        FOUR_TOKEN_OPERATIONAL_HISTORICAL_RECONCILIATION_PACKAGES
    ),
)


#: Every Git authorization profile this validator will ever accept. Anything
#: else fails closed. This name tuple is the single allowlist declaration.
_SUPPORTED_PROFILE_NAMES: tuple[str, ...] = (
    "ORDINARY_AUTHORIZATION_PROFILE",
    "STANDARD_FOUR_HOUR_AUTHORIZATION_PROFILE",
    "FOUR_TOKEN_PROOF_AUTHORIZATION_PROFILE",
    "FOUR_TOKEN_STANDARD_FOUR_HOUR_AUTHORIZATION_PROFILE",
)


def supported_profiles() -> tuple[GitAuthorizationProfile, ...]:
    """Return the live supported profiles, resolved at call time.

    Resolving through the module globals keeps the allowlist a single declared
    name tuple while preserving the long-standing behaviour that a focused test
    scoping a disposable fixture profile over a production name is accepted.
    """
    return tuple(globals()[name] for name in _SUPPORTED_PROFILE_NAMES)


def _resolved_profile(
    profile: GitAuthorizationProfile | None,
) -> GitAuthorizationProfile:
    if profile is None:
        return ORDINARY_AUTHORIZATION_PROFILE
    if profile not in supported_profiles():
        raise GitProvenanceAuthorizationError("unsupported Git authorization profile")
    return profile

# Diagnostic-only disposition vocabulary. Never creates trust or reuse authority.
TERMINAL_DISPOSITION_VOCABULARY = frozenset(
    {
        "CONSUMED_CHILD_EXITED_ZERO",
        "CONSUMED_CHILD_EXITED_NONZERO",
        "CONSUMED_CHILD_START_FAILED",
        "CONSUMED_CHILD_NOT_STARTED",
        "BLOCKED_UNCONSUMED_SUPERSEDED",
        "PERMANENTLY_CONSUMED_PRESERVED",
        "DISPOSITION_NOT_AVAILABLE",
    }
)
DEFAULT_TERMINAL_DISPOSITION = "DISPOSITION_NOT_AVAILABLE"
# Named policy dispositions assigned by approved closeout/design only.
_POLICY_TERMINAL_DISPOSITIONS = {
    "V2_9_8B_WINDOW_15M_AUTH_20260806T005252Z": "BLOCKED_UNCONSUMED_SUPERSEDED",
    "V2_9_8B_WINDOW_15M_AUTH_20260805T224959Z": "PERMANENTLY_CONSUMED_PRESERVED",
    "V2_9_8B_FOUR_TOKEN_STD4H_AUTH_20260821T124505Z_8cf7ee5d": (
        "BLOCKED_UNCONSUMED_SUPERSEDED"
    ),
    "V2_9_8B_FOUR_TOKEN_STD4H_AUTH_20260823T221645Z_6af1423a": (
        "BLOCKED_UNCONSUMED_SUPERSEDED"
    ),
    "V2_9_8B_FOUR_TOKEN_STD4H_AUTH_20260824T123555Z_95dc47dd": (
        "CONSUMED_CHILD_EXITED_NONZERO"
    ),
    "V2_9_8B_FOUR_TOKEN_STD4H_AUTH_20260824T222638Z_17181afc": (
        "BLOCKED_UNCONSUMED_SUPERSEDED"
    ),
    "V2_9_8B_FOUR_TOKEN_STD4H_AUTH_20260825T105852Z_07d92adf": (
        "CONSUMED_CHILD_EXITED_NONZERO"
    ),
    "V2_9_8B_FOUR_TOKEN_STD4H_AUTH_20260825T134723Z_4563a9dd": (
        "CONSUMED_CHILD_EXITED_ZERO"
    ),
    "V2_9_8B_FOUR_TOKEN_STD4H_AUTH_20260827T122355Z_8e43eae7": (
        "CONSUMED_CHILD_EXITED_ZERO"
    ),
    "V2_9_8B_FOUR_TOKEN_STD4H_AUTH_20260828T211924Z_5fcb1bf5": (
        "CONSUMED_CHILD_EXITED_NONZERO"
    ),
}

_MANIFEST_KEYS = frozenset(
    {
        "schema_version",
        "authorization_id",
        "authorization_file",
        "repository",
        "authorized_command",
        "migration_execution_id",
        "created_at",
        "files",
        "historical_authorization_evidence",
    }
)
_MANIFEST_AUTHORIZATION_FILE_KEYS = frozenset({"path", "sha256"})
_MANIFEST_REPOSITORY_KEYS = frozenset({"branch", "head"})
_COMMAND_KEYS = frozenset({"mode", "operator_approved"})
_MANIFEST_FILE_KEYS = frozenset({"path", "sha256", "size", "package_kind"})
_HISTORICAL_EVIDENCE_KEYS = frozenset(
    {
        "path",
        "sha256",
        "size",
        "evidence_class",
        "authorization_id",
        "terminal_disposition",
    }
)
# Historical migration evidence is a separate class. It deliberately carries no
# authorization id and no terminal disposition, so it can never be read as an
# authorization or as reusable execution authority.
HISTORICAL_MIGRATION_EVIDENCE_KEY = "historical_migration_evidence"
_HISTORICAL_MIGRATION_EVIDENCE_KEYS = frozenset(
    {
        "path",
        "sha256",
        "size",
        "evidence_class",
        "migration_execution_id",
    }
)
_SAFE_AUTHORIZATION_ID = re.compile(r"^[A-Za-z0-9_.-]+$")

_MARKER_KEYS = frozenset(
    {
        "schema_version",
        "authorization_id",
        "authorization_consumed_at",
        "authorization_sha256",
        "manifest_sha256",
        "allowed_file_set_sha256",
        "repository_branch",
        "repository_head",
        "command",
        "allowed_invocation_count",
        "automatic_retry_allowed",
        "manual_rerun_allowed",
        "resume_allowed",
        "restart_allowed",
        "successor_allowed",
    }
)
_MARKER_FALSE_FLAGS = (
    "automatic_retry_allowed",
    "manual_rerun_allowed",
    "resume_allowed",
    "restart_allowed",
    "successor_allowed",
)

_SHA256_PATTERN = re.compile(r"^[0-9a-f]{64}$")
_HEAD_PATTERN = re.compile(r"^[0-9a-f]{40}(?:[0-9a-f]{24})?$")
_GLOB_CHARACTERS = ("*", "?", "[")
_NON_RECONCILIATION_EVIDENCE_CLASSES = frozenset(
    {
        HISTORICAL_AUTHORIZATION_EVIDENCE_CLASS,
        HISTORICAL_MIGRATION_EVIDENCE_CLASS,
        HISTORICAL_MIGRATION_055_EVIDENCE_CLASS,
        HISTORICAL_MIGRATION_056_EVIDENCE_CLASS,
        HISTORICAL_MIGRATION_057_EVIDENCE_CLASS,
        HISTORICAL_MIGRATION_058_EVIDENCE_CLASS,
        HISTORICAL_MIGRATION_059_EVIDENCE_CLASS,
        HISTORICAL_MIGRATION_061_EVIDENCE_CLASS,
        MIGRATION_PACKAGE_KIND,
        MIGRATION_055_PACKAGE_KIND,
        MIGRATION_056_PACKAGE_KIND,
        MIGRATION_057_PACKAGE_KIND,
        MIGRATION_058_PACKAGE_KIND,
        MIGRATION_059_PACKAGE_KIND,
        MIGRATION_061_PACKAGE_KIND,
        MIGRATION_062_PACKAGE_KIND,
        AUTHORIZATION_PACKAGE_KIND,
    }
)


class GitProvenanceAuthorizationError(RuntimeError):
    """Fail-closed Git-provenance authorization manifest error."""


def expected_manifest_keys(profile: GitAuthorizationProfile) -> frozenset[str]:
    """Return the exact manifest key set for one profile.

    Only a profile that declares an exact historical migration package gains the
    additional ``historical_migration_evidence`` key. Every previously consumed
    ordinary and standard-four-hour manifest keeps its original exact key set.
    """
    if profile.historical_migration_packages:
        return _MANIFEST_KEYS | {HISTORICAL_MIGRATION_EVIDENCE_KEY}
    return _MANIFEST_KEYS


def require_safe_authorization_id(value: Any, *, label: str) -> str:
    """Validate the existing safe authorization-ID law."""
    if type(value) is not str or not value or _SAFE_AUTHORIZATION_ID.fullmatch(value) is None:
        raise GitProvenanceAuthorizationError(f"{label} is malformed")
    if any(character in value for character in _GLOB_CHARACTERS):
        raise GitProvenanceAuthorizationError(f"{label} must not contain glob characters")
    if "/" in value or "\\" in value:
        raise GitProvenanceAuthorizationError(f"{label} must not contain path separators")
    return value


def validate_prior_authorizations_non_reusable(
    raw: Any,
    *,
    current_authorization_id: str,
) -> tuple[str, ...]:
    """Validate the historical-authorization trust root from the current package.

    Trust comes only from this explicit declaration. Directory discovery never
    creates or broadens the approved historical authorization ID set.
    """
    current = require_safe_authorization_id(
        current_authorization_id, label="current authorization_id"
    )
    if not isinstance(raw, list):
        raise GitProvenanceAuthorizationError(
            "prior_authorizations_non_reusable must be an array"
        )
    if len(raw) == 0:
        return ()
    validated: list[str] = []
    seen: set[str] = set()
    for index, item in enumerate(raw):
        label = f"prior_authorizations_non_reusable[{index}]"
        if type(item) is not str or not item:
            raise GitProvenanceAuthorizationError(
                f"{label} must be a non-empty string"
            )
        auth_id = require_safe_authorization_id(item, label=label)
        if auth_id == current:
            raise GitProvenanceAuthorizationError(
                "prior_authorizations_non_reusable must not include the current "
                "authorization_id"
            )
        if auth_id in seen:
            raise GitProvenanceAuthorizationError(
                f"prior_authorizations_non_reusable contains a duplicate id: {auth_id}"
            )
        seen.add(auth_id)
        validated.append(auth_id)
    if validated != sorted(validated):
        raise GitProvenanceAuthorizationError(
            "prior_authorizations_non_reusable must be lexicographically sorted"
        )
    return tuple(validated)


def extract_approved_historical_authorization_ids(
    document: Mapping[str, Any],
    *,
    current_authorization_id: str,
) -> tuple[str, ...]:
    """Extract and validate the approved historical-ID trust root from a document."""
    if "prior_authorizations_non_reusable" not in document:
        raise GitProvenanceAuthorizationError(
            "final authorization document is missing prior_authorizations_non_reusable"
        )
    return validate_prior_authorizations_non_reusable(
        document.get("prior_authorizations_non_reusable"),
        current_authorization_id=current_authorization_id,
    )


def _terminal_disposition_for(authorization_id: str) -> str:
    return _POLICY_TERMINAL_DISPOSITIONS.get(
        authorization_id, DEFAULT_TERMINAL_DISPOSITION
    )



@dataclass(frozen=True)
class PreparedGitProvenanceAuthorization:
    """Immutable result of complete manifest validation before consumption."""

    allowed_untracked_paths: tuple[str, ...]
    authorization_id: str
    authorization_sha256: str
    manifest_sha256: str
    allowed_file_set_sha256: str
    repository_branch: str
    repository_head: str
    file_count: int
    authoritative_database: Mapping[str, Any]

    def summary(self) -> dict[str, Any]:
        return {
            "authorization_id": self.authorization_id,
            "authorization_sha256": self.authorization_sha256,
            "manifest_sha256": self.manifest_sha256,
            "allowed_file_set_sha256": self.allowed_file_set_sha256,
            "repository_branch": self.repository_branch,
            "repository_head": self.repository_head,
            "allowed_file_count": self.file_count,
        }


@dataclass(frozen=True)
class ValidatedGitProvenanceAuthorization:
    """Immutable result of a passed manifest/marker validation.

    ``allowed_untracked_paths`` is the exact repository-relative allowlist that
    may be handed, unchanged, to ``capture_git_provenance()``.
    """

    allowed_untracked_paths: tuple[str, ...]
    authorization_id: str
    manifest_sha256: str
    marker_sha256: str
    allowed_file_set_sha256: str
    file_count: int
    authorization_consumed_once: bool
    invocation_count: int
    allowed_invocation_count: int
    automatic_retry_allowed: bool
    manual_rerun_allowed: bool
    resume_allowed: bool
    restart_allowed: bool
    successor_allowed: bool
    authoritative_database: Mapping[str, Any]

    def summary(self) -> dict[str, Any]:
        """Return the bounded manifest/marker summary for preflight evidence.

        It never exposes file names; only counts and bound digests appear.
        """
        return {
            "authorization_id": self.authorization_id,
            "manifest_sha256": self.manifest_sha256,
            "marker_sha256": self.marker_sha256,
            "allowed_file_set_sha256": self.allowed_file_set_sha256,
            "allowed_file_count": self.file_count,
        }


def compute_allowed_file_set_sha256(files: Iterable[Mapping[str, Any]]) -> str:
    """Deterministically digest the manifest file records."""
    records = []
    for entry in files:
        records.append(
            {
                "package_kind": entry["package_kind"],
                "path": entry["path"],
                "sha256": entry["sha256"],
                "size": entry["size"],
            }
        )
    records.sort(key=lambda record: record["path"])
    canonical = json.dumps(
        records,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
        allow_nan=False,
    )
    return hashlib.sha256(canonical.encode("ascii")).hexdigest()


def _no_duplicate_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise GitProvenanceAuthorizationError(
                f"duplicate JSON key is not accepted: {key!r}"
            )
        result[key] = value
    return result


def _load_json_object(path: Path, *, label: str) -> dict[str, Any]:
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise GitProvenanceAuthorizationError(
            f"{label} could not be read: {exc}"
        ) from exc
    try:
        value = json.loads(text, object_pairs_hook=_no_duplicate_keys)
    except ValueError as exc:
        raise GitProvenanceAuthorizationError(
            f"{label} is not canonical JSON: {exc}"
        ) from exc
    if not isinstance(value, dict):
        raise GitProvenanceAuthorizationError(f"{label} must be a JSON object")
    return value


def _require_keys(
    value: Mapping[str, Any], expected: frozenset[str], *, label: str
) -> None:
    actual = frozenset(value)
    if actual != expected:
        missing = sorted(expected - actual)
        extra = sorted(actual - expected)
        raise GitProvenanceAuthorizationError(
            f"{label} schema is malformed (missing={missing} extra={extra})"
        )


def _require_str(value: Any, *, label: str) -> str:
    if type(value) is not str or not value:
        raise GitProvenanceAuthorizationError(f"{label} must be a non-empty string")
    return value


def _require_hex64(value: Any, *, label: str) -> str:
    if type(value) is not str or _SHA256_PATTERN.fullmatch(value) is None:
        raise GitProvenanceAuthorizationError(
            f"{label} must be 64 lowercase hexadecimal characters"
        )
    return value


def _require_head(value: Any, *, label: str) -> str:
    if type(value) is not str or _HEAD_PATTERN.fullmatch(value) is None:
        raise GitProvenanceAuthorizationError(f"{label} is malformed")
    return value


def _require_true(value: Any, *, label: str) -> None:
    if type(value) is not bool or value is not True:
        raise GitProvenanceAuthorizationError(f"{label} must be exactly true")


def _require_false(value: Any, *, label: str) -> None:
    if type(value) is not bool or value is not False:
        raise GitProvenanceAuthorizationError(f"{label} must be exactly false")


def _require_tz_aware(value: Any, *, label: str) -> None:
    text = _require_str(value, label=label)
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError as exc:
        raise GitProvenanceAuthorizationError(f"{label} is malformed") from exc
    if parsed.tzinfo is None:
        raise GitProvenanceAuthorizationError(f"{label} must be timezone-aware")


def _require_command(
    value: Any, *, label: str, required_mode: str = REQUIRED_COMMAND_MODE
) -> None:
    if not isinstance(value, Mapping):
        raise GitProvenanceAuthorizationError(f"{label} must be an object")
    _require_keys(value, _COMMAND_KEYS, label=label)
    if value.get("mode") != required_mode:
        raise GitProvenanceAuthorizationError(
            f"{label} mode must be {required_mode!r}"
        )
    _require_true(value.get("operator_approved"), label=f"{label} operator_approved")


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _resolve_external_file(
    raw_path: str, *, root: Path, expected_sha256: str, label: str
) -> tuple[Path, str]:
    """Validate an absolute, outside-repository, regular, non-symlink file."""
    text = _require_str(raw_path, label=f"{label} path")
    candidate = Path(text)
    if not candidate.is_absolute():
        raise GitProvenanceAuthorizationError(f"{label} path must be absolute")
    if os.path.islink(text):
        raise GitProvenanceAuthorizationError(f"{label} path must not be a symlink")
    if not candidate.is_file():
        raise GitProvenanceAuthorizationError(f"{label} is not a regular file")
    resolved = candidate.resolve()
    if resolved == root or resolved.is_relative_to(root):
        raise GitProvenanceAuthorizationError(
            f"{label} must live outside the repository"
        )
    expected = _require_hex64(expected_sha256, label=f"{label} expected SHA-256")
    actual = _sha256_file(candidate)
    if actual != expected:
        raise GitProvenanceAuthorizationError(f"{label} SHA-256 mismatch")
    return candidate, actual


def _git(
    root: Path,
    arguments: list[str],
    *,
    git_executable: str,
    timeout_seconds: float,
    runner: Callable[..., Any],
    allowed: set[int],
    label: str,
) -> Any:
    try:
        result = runner(
            [git_executable, *arguments],
            cwd=str(root),
            capture_output=True,
            text=True,
            timeout=timeout_seconds,
            check=False,
            shell=False,
        )
    except FileNotFoundError as exc:
        raise GitProvenanceAuthorizationError("Git executable is unavailable") from exc
    except subprocess.TimeoutExpired as exc:
        raise GitProvenanceAuthorizationError(f"Git {label} timed out") from exc
    except OSError as exc:
        raise GitProvenanceAuthorizationError(
            f"Git {label} failed: {exc}"
        ) from exc
    code = getattr(result, "returncode", None)
    if type(code) is not int or code not in allowed:
        raise GitProvenanceAuthorizationError(f"Git {label} could not be verified")
    return result


def _normalize_git_path(raw: str, *, label: str) -> str:
    if not raw:
        raise GitProvenanceAuthorizationError(f"Git {label} returned an empty path")
    if "\\" in raw or raw.startswith("/") or raw.endswith("/"):
        raise GitProvenanceAuthorizationError(f"Git {label} returned a malformed path")
    candidate = PurePosixPath(raw)
    if any(part in ("", ".", "..") for part in candidate.parts):
        raise GitProvenanceAuthorizationError(f"Git {label} returned a malformed path")
    normalized = candidate.as_posix()
    if normalized != raw:
        raise GitProvenanceAuthorizationError(f"Git {label} returned a malformed path")
    return normalized


def _parse_git_path_set(result: Any, *, label: str) -> set[str]:
    output = getattr(result, "stdout", None)
    if not isinstance(output, str):
        raise GitProvenanceAuthorizationError(f"Git {label} output is malformed")
    raw_items = [item for item in output.split("\0") if item]
    normalized = [_normalize_git_path(item, label=label) for item in raw_items]
    if len(normalized) != len(set(normalized)):
        raise GitProvenanceAuthorizationError(
            f"Git {label} returned duplicate paths"
        )
    return set(normalized)


def _live_repository_identity(
    root: Path,
    *,
    git_executable: str,
    timeout_seconds: float,
    runner: Callable[..., Any],
) -> tuple[str, str]:
    head_result = _git(
        root,
        ["rev-parse", "--verify", "HEAD^{commit}"],
        git_executable=git_executable,
        timeout_seconds=timeout_seconds,
        runner=runner,
        allowed={0},
        label="HEAD",
    )
    head = str(getattr(head_result, "stdout", "")).strip().lower()
    if _HEAD_PATTERN.fullmatch(head) is None:
        raise GitProvenanceAuthorizationError("Git HEAD output is malformed")

    branch_result = _git(
        root,
        ["rev-parse", "--abbrev-ref", "HEAD"],
        git_executable=git_executable,
        timeout_seconds=timeout_seconds,
        runner=runner,
        allowed={0},
        label="branch",
    )
    branch = str(getattr(branch_result, "stdout", "")).strip()
    if not branch or branch == "HEAD":
        raise GitProvenanceAuthorizationError("Git branch could not be determined")

    staged = _git(
        root,
        ["diff", "--cached", "--quiet", "--no-ext-diff", "--"],
        git_executable=git_executable,
        timeout_seconds=timeout_seconds,
        runner=runner,
        allowed={0, 1},
        label="staged status",
    )
    if getattr(staged, "returncode", None) == 1:
        raise GitProvenanceAuthorizationError("launch Git tree has staged changes")

    unstaged = _git(
        root,
        ["diff", "--quiet", "--no-ext-diff", "--"],
        git_executable=git_executable,
        timeout_seconds=timeout_seconds,
        runner=runner,
        allowed={0, 1},
        label="unstaged status",
    )
    if getattr(unstaged, "returncode", None) == 1:
        raise GitProvenanceAuthorizationError("launch Git tree has unstaged changes")

    return branch, head


def _visible_untracked_paths(
    root: Path,
    *,
    git_executable: str,
    timeout_seconds: float,
    runner: Callable[..., Any],
) -> set[str]:
    result = _git(
        root,
        ["ls-files", "--others", "--exclude-standard", "-z"],
        git_executable=git_executable,
        timeout_seconds=timeout_seconds,
        runner=runner,
        allowed={0},
        label="untracked status",
    )
    return _parse_git_path_set(result, label="untracked status")


def _ignored_operator_runs_paths(
    root: Path,
    *,
    git_executable: str,
    timeout_seconds: float,
    runner: Callable[..., Any],
) -> set[str]:
    result = _git(
        root,
        [
            "ls-files",
            "--others",
            "--ignored",
            "--exclude-standard",
            "-z",
            "--",
            f"{OPERATOR_RUNS_ROOT}/",
        ],
        git_executable=git_executable,
        timeout_seconds=timeout_seconds,
        runner=runner,
        allowed={0},
        label="ignored operator-runs status",
    )
    paths = _parse_git_path_set(result, label="ignored operator-runs status")
    prefix = f"{OPERATOR_RUNS_ROOT}/"
    outside = {path for path in paths if not path.startswith(prefix)}
    if outside:
        raise GitProvenanceAuthorizationError(
            "Git ignored operator-runs status returned a path outside operator-runs: "
            + ", ".join(sorted(outside))
        )
    return paths


def _tracked_operator_runs_paths(
    root: Path,
    *,
    git_executable: str,
    timeout_seconds: float,
    runner: Callable[..., Any],
) -> set[str]:
    # Return path identities tracked by the exact HEAD under operator-runs.
    result = _git(
        root,
        [
            "ls-tree",
            "-r",
            "--name-only",
            "-z",
            "HEAD",
            "--",
            f"{OPERATOR_RUNS_ROOT}/",
        ],
        git_executable=git_executable,
        timeout_seconds=timeout_seconds,
        runner=runner,
        allowed={0},
        label="tracked operator-runs status",
    )
    paths = _parse_git_path_set(result, label="tracked operator-runs status")
    prefix = f"{OPERATOR_RUNS_ROOT}/"
    outside = {path for path in paths if not path.startswith(prefix)}
    if outside:
        raise GitProvenanceAuthorizationError(
            "Git tracked operator-runs status returned a path outside operator-runs: "
            + ", ".join(sorted(outside))
        )
    return paths


def _inventory_operator_runs(root: Path) -> set[str]:
    """Return every regular file below operator-runs without following symlinks."""
    operator_root = root / OPERATOR_RUNS_ROOT
    if os.path.islink(operator_root):
        raise GitProvenanceAuthorizationError(
            "operator-runs evidence root must not be a symlink"
        )
    if not operator_root.is_dir():
        raise GitProvenanceAuthorizationError(
            "operator-runs evidence root is unavailable"
        )

    inventory: set[str] = set()
    stack = [operator_root]
    while stack:
        directory = stack.pop()
        try:
            entries = sorted(os.scandir(directory), key=lambda entry: entry.name)
        except OSError as exc:
            raise GitProvenanceAuthorizationError(
                f"operator-runs evidence inventory could not be read: {exc}"
            ) from exc

        for entry in entries:
            path = Path(entry.path)
            try:
                relative = path.relative_to(root).as_posix()
            except ValueError as exc:
                raise GitProvenanceAuthorizationError(
                    "operator-runs evidence entry resolves outside the repository"
                ) from exc

            if entry.is_symlink():
                raise GitProvenanceAuthorizationError(
                    f"operator-runs evidence inventory contains a symlink: {relative}"
                )
            try:
                mode = entry.stat(follow_symlinks=False).st_mode
            except OSError as exc:
                raise GitProvenanceAuthorizationError(
                    f"operator-runs evidence entry could not be inspected: {relative}"
                ) from exc

            if stat.S_ISDIR(mode):
                stack.append(path)
                continue
            if not stat.S_ISREG(mode):
                raise GitProvenanceAuthorizationError(
                    f"operator-runs evidence inventory contains a non-regular entry: {relative}"
                )
            normalized = _normalize_git_path(relative, label="operator-runs inventory")
            if normalized in inventory:
                raise GitProvenanceAuthorizationError(
                    f"operator-runs evidence inventory contains a duplicate path: {normalized}"
                )
            inventory.add(normalized)
    return inventory


def _is_beneath_root(path: str, root: str) -> bool:
    prefix = f"{root}/"
    return path.startswith(prefix) and len(path) > len(prefix)


def _current_package_inventory(
    inventory_paths: set[str], current_package_roots: tuple[str, str]
) -> set[str]:
    return {
        path
        for path in inventory_paths
        if any(_is_beneath_root(path, root) for root in current_package_roots)
    }


def _normalize_sidecar_paths(paths: Iterable[str]) -> set[str]:
    normalized = set()
    for item in paths:
        text = Path(str(item)).as_posix()
        normalized.add(_normalize_git_path(text, label="sidecar allowlist"))
    return normalized


def _reconcile_evidence_sets(
    *,
    current_manifest_paths: set[str],
    historical_paths: set[str],
    visible_paths: set[str],
    ignored_paths: set[str],
    tracked_paths: set[str],
    inventory_paths: set[str],
    current_package_roots: tuple[str, str],
    sidecar_untracked_paths: Iterable[str],
    historical_migration_paths: set[str] | None = None,
    historical_reconciliation_paths: set[str] | None = None,
) -> None:
    """Reconcile complete operator-runs inventory against T, M, Ha, Hm and Hr.

    M (current_manifest_paths) is current-only and is the only set used for
    current-package equality (C == M). Ha is approved historical authorization
    evidence, Hm is exact profile-bound historical migration evidence, and Hr
    is exact profile-bound historical reconciliation evidence.
    U = M ∪ Ha ∪ Hm ∪ Hr is the untracked allowlist and
    F = T ∪ M ∪ Ha ∪ Hm ∪ Hr is the complete inventory. Never pass U into
    current-package equality checks.
    """
    m_paths = set(current_manifest_paths)
    h_paths = set(historical_paths)
    hm_paths = set(historical_migration_paths or ())
    hr_paths = set(historical_reconciliation_paths or ())
    allowlist_u = m_paths | h_paths | hm_paths | hr_paths
    t_paths = set(tracked_paths)
    f_paths = set(inventory_paths)

    effective_visible = visible_paths - _normalize_sidecar_paths(
        sidecar_untracked_paths
    )

    overlaps = {
        "tracked and visible untracked": t_paths & effective_visible,
        "tracked and ignored untracked": t_paths & ignored_paths,
        "visible and ignored untracked": effective_visible & ignored_paths,
    }
    for label, overlap in overlaps.items():
        if overlap:
            raise GitProvenanceAuthorizationError(
                f"Git {label} classifications overlap: "
                + ", ".join(sorted(overlap))
            )

    if m_paths & h_paths:
        raise GitProvenanceAuthorizationError(
            "duplicate path across current files and historical authorization "
            "evidence: "
            + ", ".join(sorted(m_paths & h_paths))
        )

    if m_paths & hm_paths:
        raise GitProvenanceAuthorizationError(
            "duplicate path across current files and historical migration "
            "evidence: "
            + ", ".join(sorted(m_paths & hm_paths))
        )

    if h_paths & hm_paths:
        raise GitProvenanceAuthorizationError(
            "duplicate path across historical authorization evidence and "
            "historical migration evidence: "
            + ", ".join(sorted(h_paths & hm_paths))
        )

    for label, overlap in (
        ("current files", m_paths & hr_paths),
        ("historical authorization evidence", h_paths & hr_paths),
        ("historical migration evidence", hm_paths & hr_paths),
    ):
        if overlap:
            raise GitProvenanceAuthorizationError(
                "duplicate path across historical reconciliation evidence and "
                + label
                + ": "
                + ", ".join(sorted(overlap))
            )

    unexpected_visible = effective_visible - allowlist_u
    if unexpected_visible:
        raise GitProvenanceAuthorizationError(
            "unexpected untracked repository file not covered by manifest: "
            + ", ".join(sorted(unexpected_visible))
        )

    unexpected_ignored = ignored_paths - allowlist_u
    if unexpected_ignored:
        raise GitProvenanceAuthorizationError(
            "unexpected ignored operator-runs file not covered by manifest: "
            + ", ".join(sorted(unexpected_ignored))
        )

    tracked_allowlist_overlap = t_paths & allowlist_u
    if tracked_allowlist_overlap:
        raise GitProvenanceAuthorizationError(
            "untracked allowlist path is tracked instead of untracked: "
            + ", ".join(sorted(tracked_allowlist_overlap))
        )

    current_inventory = _current_package_inventory(f_paths, current_package_roots)
    tracked_current = {
        path
        for path in t_paths
        if any(_is_beneath_root(path, root) for root in current_package_roots)
    }
    if tracked_current:
        raise GitProvenanceAuthorizationError(
            "tracked file exists inside a current evidence package: "
            + ", ".join(sorted(tracked_current))
        )

    missing_current_manifest = m_paths - f_paths
    if missing_current_manifest:
        raise GitProvenanceAuthorizationError(
            "manifest file is absent from the complete operator-runs inventory: "
            + ", ".join(sorted(missing_current_manifest))
        )
    missing_historical = h_paths - f_paths
    if missing_historical:
        raise GitProvenanceAuthorizationError(
            "historical authorization evidence is absent from the complete "
            "operator-runs inventory: "
            + ", ".join(sorted(missing_historical))
        )
    missing_historical_migration = hm_paths - f_paths
    if missing_historical_migration:
        raise GitProvenanceAuthorizationError(
            "historical migration evidence is absent from the complete "
            "operator-runs inventory: "
            + ", ".join(sorted(missing_historical_migration))
        )
    missing_historical_reconciliation = hr_paths - f_paths
    if missing_historical_reconciliation:
        raise GitProvenanceAuthorizationError(
            "historical reconciliation evidence is absent from the complete "
            "operator-runs inventory: "
            + ", ".join(sorted(missing_historical_reconciliation))
        )

    ignored_outside_inventory = ignored_paths - f_paths
    if ignored_outside_inventory:
        raise GitProvenanceAuthorizationError(
            "ignored operator-runs path is absent from the filesystem inventory: "
            + ", ".join(sorted(ignored_outside_inventory))
        )

    tracked_outside_inventory = t_paths - f_paths
    if tracked_outside_inventory:
        raise GitProvenanceAuthorizationError(
            "tracked historical operator-runs path is absent from the filesystem "
            "inventory: "
            + ", ".join(sorted(tracked_outside_inventory))
        )

    classified_allowlist = (effective_visible & allowlist_u) | (
        ignored_paths & allowlist_u
    )
    unclassified = allowlist_u - classified_allowlist
    if unclassified:
        raise GitProvenanceAuthorizationError(
            "manifest file is neither visible nor ignored untracked: "
            + ", ".join(sorted(unclassified))
        )

    # Current-package equality uses M only. Historical paths must never satisfy
    # current-package identity.
    missing_current = m_paths - current_inventory
    if missing_current:
        raise GitProvenanceAuthorizationError(
            "current evidence package is missing a manifest file: "
            + ", ".join(sorted(missing_current))
        )
    unexpected_current = current_inventory - m_paths
    if unexpected_current:
        raise GitProvenanceAuthorizationError(
            "unexpected file exists inside a current evidence package: "
            + ", ".join(sorted(unexpected_current))
        )
    if current_inventory != m_paths:
        raise GitProvenanceAuthorizationError(
            "current package inventory does not equal current manifest file set"
        )

    historical_in_current = h_paths & current_inventory
    if historical_in_current:
        raise GitProvenanceAuthorizationError(
            "historical authorization evidence path lies inside a current package: "
            + ", ".join(sorted(historical_in_current))
        )

    historical_migration_in_current = hm_paths & current_inventory
    if historical_migration_in_current:
        raise GitProvenanceAuthorizationError(
            "historical migration evidence path lies inside a current package: "
            + ", ".join(sorted(historical_migration_in_current))
        )

    historical_reconciliation_in_current = hr_paths & current_inventory
    if historical_reconciliation_in_current:
        raise GitProvenanceAuthorizationError(
            "historical reconciliation evidence path lies inside a current "
            "package: "
            + ", ".join(sorted(historical_reconciliation_in_current))
        )

    expected_inventory = t_paths | m_paths | h_paths | hm_paths | hr_paths
    unexplained_inventory = f_paths - expected_inventory
    if unexplained_inventory:
        raise GitProvenanceAuthorizationError(
            "unexpected operator-runs filesystem file is neither tracked history, "
            "current manifest evidence, approved historical authorization "
            "evidence, approved historical migration evidence, nor approved "
            "historical reconciliation evidence: "
            + ", ".join(sorted(unexplained_inventory))
        )

    missing_inventory = expected_inventory - f_paths
    if missing_inventory:
        raise GitProvenanceAuthorizationError(
            "tracked-history/current-manifest/historical path is absent from "
            "operator-runs inventory: "
            + ", ".join(sorted(missing_inventory))
        )

    if f_paths != expected_inventory:
        raise GitProvenanceAuthorizationError(
            "complete operator-runs inventory does not equal tracked history plus "
            "current manifest files plus approved historical authorization "
            "evidence plus approved historical migration evidence plus approved "
            "historical reconciliation evidence"
        )


def enumerate_historical_authorization_evidence(
    *,
    repository_root: str | Path,
    current_authorization_id: str,
    approved_historical_authorization_ids: Collection[str],
    tracked_operator_runs_paths: set[str] | None = None,
    authorization_package_roots: Collection[str] | None = None,
    current_authorization_package_root: str = AUTHORIZATION_PACKAGE_ROOT,
    git_executable: str = "git",
    timeout_seconds: float = GIT_COMMAND_TIMEOUT_SECONDS,
    runner: Callable[..., Any] = subprocess.run,
) -> tuple[dict[str, Any], ...]:
    """Return approved historical authorization evidence across explicit roots.

    Directory discovery never creates trust. Only IDs declared by the current
    authorization may enter H. A single approved ID appearing untracked under
    more than one allowed authorization root is ambiguous and fails closed.
    """
    if not 0 < timeout_seconds <= GIT_COMMAND_TIMEOUT_SECONDS:
        raise GitProvenanceAuthorizationError(
            "Git provenance timeout is outside the fixed ceiling"
        )
    root = Path(repository_root).resolve()
    if not root.is_dir():
        raise GitProvenanceAuthorizationError("repository root is unavailable")
    current_id = require_safe_authorization_id(
        current_authorization_id, label="current authorization_id"
    )
    approved = validate_prior_authorizations_non_reusable(
        list(approved_historical_authorization_ids),
        current_authorization_id=current_id,
    )
    approved_set = set(approved)
    roots = tuple(dict.fromkeys(authorization_package_roots or (AUTHORIZATION_PACKAGE_ROOT,)))
    if not roots or any(not isinstance(item, str) or not item for item in roots):
        raise GitProvenanceAuthorizationError("historical authorization roots are malformed")
    if current_authorization_package_root not in roots:
        raise GitProvenanceAuthorizationError(
            "current authorization root must be included in historical scan roots"
        )

    operator_root = root / OPERATOR_RUNS_ROOT
    if os.path.islink(operator_root) or not operator_root.is_dir():
        raise GitProvenanceAuthorizationError(
            "operator-runs evidence root is unavailable or is a symlink"
        )
    tracked = (
        _tracked_operator_runs_paths(
            root,
            git_executable=git_executable,
            timeout_seconds=timeout_seconds,
            runner=runner,
        )
        if tracked_operator_runs_paths is None
        else set(tracked_operator_runs_paths)
    )

    records: list[dict[str, Any]] = []
    seen_paths: set[str] = set()
    approved_untracked_root: dict[str, str] = {}
    for authorization_root in roots:
        package_root_path = root / authorization_root
        if os.path.islink(package_root_path):
            raise GitProvenanceAuthorizationError(
                f"authorization package root must not be a symlink: {authorization_root}"
            )
        if not package_root_path.exists():
            continue
        if not package_root_path.is_dir():
            raise GitProvenanceAuthorizationError(
                f"authorization package root is not a directory: {authorization_root}"
            )
        try:
            package_entries = sorted(
                os.scandir(package_root_path), key=lambda entry: entry.name
            )
        except OSError as exc:
            raise GitProvenanceAuthorizationError(
                f"authorization package root could not be read: {exc}"
            ) from exc

        for entry in package_entries:
            package_relative = f"{authorization_root}/{entry.name}"
            if entry.is_symlink():
                raise GitProvenanceAuthorizationError(
                    f"authorization package directory is a symlink: {package_relative}"
                )
            try:
                mode = entry.stat(follow_symlinks=False).st_mode
            except OSError as exc:
                raise GitProvenanceAuthorizationError(
                    f"authorization package directory could not be inspected: {package_relative}"
                ) from exc
            if not stat.S_ISDIR(mode):
                raise GitProvenanceAuthorizationError(
                    f"authorization package root contains a non-package entry: {package_relative}"
                )
            try:
                package_id = require_safe_authorization_id(
                    entry.name, label="historical authorization package directory"
                )
            except GitProvenanceAuthorizationError as exc:
                raise GitProvenanceAuthorizationError(
                    "authorization package directory name is not a safe authorization id: "
                    + package_relative
                ) from exc

            package_dir = Path(entry.path)
            package_files = _inventory_authorization_package_files(
                root=root,
                package_dir=package_dir,
                package_id=package_id,
                authorization_package_root=authorization_root,
            )
            untracked_files = [
                item for item in package_files if item["path"] not in tracked
            ]
            if package_id == current_id:
                if authorization_root == current_authorization_package_root:
                    continue
                if untracked_files:
                    raise GitProvenanceAuthorizationError(
                        "current authorization id also appears under another authorization root"
                    )
                continue
            if package_id not in approved_set:
                if untracked_files:
                    raise GitProvenanceAuthorizationError(
                        "unapproved historical authorization package contains untracked files "
                        "not covered by the trust root: "
                        + ", ".join(item["path"] for item in untracked_files)
                    )
                continue
            if not untracked_files:
                continue
            prior_root = approved_untracked_root.get(package_id)
            if prior_root is not None and prior_root != authorization_root:
                raise GitProvenanceAuthorizationError(
                    "approved historical authorization id is ambiguous across roots: "
                    + package_id
                )
            approved_untracked_root[package_id] = authorization_root
            disposition = _terminal_disposition_for(package_id)
            for item in untracked_files:
                path = item["path"]
                if path in seen_paths:
                    raise GitProvenanceAuthorizationError(
                        f"duplicate historical authorization evidence path: {path}"
                    )
                seen_paths.add(path)
                records.append(
                    {
                        "path": path,
                        "sha256": item["sha256"],
                        "size": item["size"],
                        "evidence_class": HISTORICAL_AUTHORIZATION_EVIDENCE_CLASS,
                        "authorization_id": package_id,
                        "terminal_disposition": disposition,
                    }
                )
    records.sort(key=lambda record: record["path"])
    return tuple(records)


def enumerate_historical_migration_evidence(
    *,
    repository_root: str | Path,
    historical_migration_packages: Collection[HistoricalMigrationPackage],
    tracked_operator_runs_paths: set[str] | None = None,
    git_executable: str = "git",
    timeout_seconds: float = GIT_COMMAND_TIMEOUT_SECONDS,
    runner: Callable[..., Any] = subprocess.run,
) -> tuple[dict[str, Any], ...]:
    """Return exact profile-bound preserved historical migration evidence.

    Trust comes only from the explicit ``(package_root, execution_id)`` pairs the
    active profile declares. The package root itself is never broadly trusted:
    any other package beneath it that still holds untracked files fails closed,
    and every accepted regular file is bound by normalized path, size and
    SHA-256.

    Every declared package is required, not optional. Its exact root and exact
    execution directory must exist as real readable directories and the exact
    package must yield at least one bound regular file, so preserved historical
    migration evidence cannot be removed before preparation to make the manifest
    silently emit an empty array. A profile that declares no package keeps the
    empty-default behavior and performs no filesystem work at all.
    """
    packages = tuple(historical_migration_packages)
    if not packages:
        return ()
    if not 0 < timeout_seconds <= GIT_COMMAND_TIMEOUT_SECONDS:
        raise GitProvenanceAuthorizationError(
            "Git provenance timeout is outside the fixed ceiling"
        )
    root = Path(repository_root).resolve()
    if not root.is_dir():
        raise GitProvenanceAuthorizationError("repository root is unavailable")

    approved_by_root: dict[str, set[str]] = {}
    for package in packages:
        if (
            not isinstance(package.package_root, str)
            or not package.package_root
            or not isinstance(package.execution_id, str)
            or not package.execution_id
            or not isinstance(package.evidence_class, str)
            or not package.evidence_class
            or type(package.expected_file_count) is not int
            or type(package.expected_file_count) is bool
            or package.expected_file_count < 1
            or type(package.expected_inventory_sha256) is not str
            or _SHA256_PATTERN.fullmatch(package.expected_inventory_sha256) is None
        ):
            raise GitProvenanceAuthorizationError(
                "historical migration package declaration is malformed"
            )
        if not _is_beneath_root(
            f"{package.package_root}/{package.execution_id}", OPERATOR_RUNS_ROOT
        ):
            raise GitProvenanceAuthorizationError(
                "historical migration package root must live under operator-runs"
            )
        require_safe_authorization_id(
            package.execution_id, label="historical migration execution_id"
        )
        approved_by_root.setdefault(package.package_root, set()).add(
            package.execution_id
        )

    tracked = (
        _tracked_operator_runs_paths(
            root,
            git_executable=git_executable,
            timeout_seconds=timeout_seconds,
            runner=runner,
        )
        if tracked_operator_runs_paths is None
        else set(tracked_operator_runs_paths)
    )

    records: list[dict[str, Any]] = []
    seen_paths: set[str] = set()
    for package in packages:
        package_root_path = root / package.package_root
        if os.path.islink(package_root_path):
            raise GitProvenanceAuthorizationError(
                "historical migration package root must not be a symlink: "
                + package.package_root
            )
        if not package_root_path.exists():
            raise GitProvenanceAuthorizationError(
                "declared historical migration package root is missing: "
                + package.package_root
            )
        if not package_root_path.is_dir():
            raise GitProvenanceAuthorizationError(
                "historical migration package root is not a directory: "
                + package.package_root
            )
        if not os.access(package_root_path, os.R_OK | os.X_OK):
            raise GitProvenanceAuthorizationError(
                "declared historical migration package root is not readable: "
                + package.package_root
            )
        # The exact declared execution directory is required evidence, not an
        # optional discovery. Absence, aliasing or unreadability fails closed.
        execution_dir = package_root_path / package.execution_id
        if os.path.islink(execution_dir):
            raise GitProvenanceAuthorizationError(
                "declared historical migration execution directory must not be "
                "a symlink: " + package.package_prefix
            )
        if not execution_dir.exists():
            raise GitProvenanceAuthorizationError(
                "declared historical migration execution directory is missing: "
                + package.package_prefix
            )
        if not execution_dir.is_dir():
            raise GitProvenanceAuthorizationError(
                "declared historical migration execution directory is not a "
                "directory: " + package.package_prefix
            )
        if not os.access(execution_dir, os.R_OK | os.X_OK):
            raise GitProvenanceAuthorizationError(
                "declared historical migration execution directory is not "
                "readable: " + package.package_prefix
            )
        try:
            entries = sorted(
                os.scandir(package_root_path), key=lambda entry: entry.name
            )
        except OSError as exc:
            raise GitProvenanceAuthorizationError(
                f"historical migration package root could not be read: {exc}"
            ) from exc

        approved_ids = approved_by_root[package.package_root]
        bound_for_package = 0
        for entry in entries:
            entry_relative = f"{package.package_root}/{entry.name}"
            if entry.is_symlink():
                raise GitProvenanceAuthorizationError(
                    "historical migration package directory is a symlink: "
                    + entry_relative
                )
            try:
                mode = entry.stat(follow_symlinks=False).st_mode
            except OSError as exc:
                raise GitProvenanceAuthorizationError(
                    "historical migration package directory could not be "
                    "inspected: " + entry_relative
                ) from exc
            if not stat.S_ISDIR(mode):
                raise GitProvenanceAuthorizationError(
                    "historical migration package root contains a non-package "
                    "entry: " + entry_relative
                )
            package_files = _inventory_bound_package_files(
                root=root,
                package_dir=Path(entry.path),
                package_prefix=entry_relative,
                label="historical migration package",
            )
            untracked_files = [
                item for item in package_files if item["path"] not in tracked
            ]
            if entry.name not in approved_ids:
                if untracked_files:
                    raise GitProvenanceAuthorizationError(
                        "unapproved historical migration package contains "
                        "untracked files not covered by the exact profile "
                        "binding: "
                        + ", ".join(item["path"] for item in untracked_files)
                    )
                continue
            if entry.name != package.execution_id:
                continue
            # Immutable completeness law. The COMPLETE accepted inventory of the
            # exact declared package must equal its committed declaration before
            # any record is emitted. This runs at fresh preparation, so a missing
            # member, a modified byte, an intruded file, or a member that quietly
            # became tracked can never be silently re-bound into a new manifest.
            if len(package_files) != package.expected_file_count:
                raise GitProvenanceAuthorizationError(
                    "declared historical migration package inventory file count "
                    "does not match its immutable declaration: "
                    f"{package.package_prefix} "
                    f"(expected {package.expected_file_count}, "
                    f"found {len(package_files)})"
                )
            if len(untracked_files) != len(package_files):
                tracked_members = sorted(
                    item["path"]
                    for item in package_files
                    if item["path"] in tracked
                )
                raise GitProvenanceAuthorizationError(
                    "declared historical migration package member is tracked at "
                    "HEAD instead of preserved untracked evidence: "
                    + ", ".join(tracked_members)
                )
            actual_inventory_sha256 = package.inventory_sha256(package_files)
            if actual_inventory_sha256 != package.expected_inventory_sha256:
                raise GitProvenanceAuthorizationError(
                    "declared historical migration package inventory digest does "
                    "not match its immutable declaration: "
                    f"{package.package_prefix} "
                    f"(expected {package.expected_inventory_sha256}, "
                    f"computed {actual_inventory_sha256})"
                )
            for item in untracked_files:
                path = item["path"]
                if path in seen_paths:
                    raise GitProvenanceAuthorizationError(
                        f"duplicate historical migration evidence path: {path}"
                    )
                seen_paths.add(path)
                bound_for_package += 1
                records.append(
                    {
                        "path": path,
                        "sha256": item["sha256"],
                        "size": item["size"],
                        "evidence_class": package.evidence_class,
                        "migration_execution_id": package.execution_id,
                    }
                )
        if bound_for_package == 0:
            raise GitProvenanceAuthorizationError(
                "declared historical migration package contains no bound "
                "untracked evidence: " + package.package_prefix
            )
    records.sort(key=lambda record: record["path"])
    return tuple(records)


def enumerate_historical_reconciliation_evidence(
    *,
    repository_root: str | Path,
    historical_reconciliation_packages: Collection[
        HistoricalReconciliationPackage
    ],
    tracked_operator_runs_paths: set[str] | None = None,
    git_executable: str = "git",
    timeout_seconds: float = GIT_COMMAND_TIMEOUT_SECONDS,
    runner: Callable[..., Any] = subprocess.run,
) -> tuple[dict[str, Any], ...]:
    """Validate and enumerate immutable historical reconciliation evidence.

    Package membership comes only from committed profile declarations.  The
    filesystem can prove exact equality or fail closed; it cannot add, remove,
    or redefine a member during manifest preparation.
    """
    packages = tuple(historical_reconciliation_packages)
    if not packages:
        return ()
    if not 0 < timeout_seconds <= GIT_COMMAND_TIMEOUT_SECONDS:
        raise GitProvenanceAuthorizationError(
            "Git provenance timeout is outside the fixed ceiling"
        )
    root = Path(repository_root).resolve()
    if not root.is_dir():
        raise GitProvenanceAuthorizationError("repository root is unavailable")
    tracked = (
        _tracked_operator_runs_paths(
            root,
            git_executable=git_executable,
            timeout_seconds=timeout_seconds,
            runner=runner,
        )
        if tracked_operator_runs_paths is None
        else set(tracked_operator_runs_paths)
    )

    records: list[dict[str, Any]] = []
    seen_paths: set[str] = set()
    seen_roots: set[str] = set()
    for package in packages:
        if (
            not isinstance(package.package_root, str)
            or not package.package_root
            or not isinstance(package.execution_id, str)
            or not package.execution_id
            or not isinstance(package.evidence_class, str)
            or not package.evidence_class
            or type(package.expected_file_count) is not int
            or type(package.expected_file_count) is bool
            or package.expected_file_count < 1
            or _SHA256_PATTERN.fullmatch(package.expected_inventory_sha256) is None
            or not isinstance(package.execution_directories, tuple)
            or not package.execution_directories
            or not isinstance(package.files, tuple)
        ):
            raise GitProvenanceAuthorizationError(
                "historical reconciliation package declaration is malformed"
            )
        if package.evidence_class in _NON_RECONCILIATION_EVIDENCE_CLASSES:
            raise GitProvenanceAuthorizationError(
                "historical reconciliation evidence_class reuses a migration "
                "or authorization evidence class"
            )
        normalized_root = _normalize_git_path(
            package.package_root, label="historical reconciliation package root"
        )
        if normalized_root != package.package_root or not _is_beneath_root(
            f"{normalized_root}/{package.execution_id}", OPERATOR_RUNS_ROOT
        ):
            raise GitProvenanceAuthorizationError(
                "historical reconciliation package root must live under operator-runs"
            )
        if normalized_root in seen_roots:
            raise GitProvenanceAuthorizationError(
                "duplicate historical reconciliation package root"
            )
        seen_roots.add(normalized_root)
        require_safe_authorization_id(
            package.execution_id,
            label="historical reconciliation execution_id",
        )
        if (
            tuple(sorted(package.execution_directories))
            != package.execution_directories
            or len(set(package.execution_directories))
            != len(package.execution_directories)
        ):
            raise GitProvenanceAuthorizationError(
                "historical reconciliation execution-directory declaration is "
                "not exact, unique and sorted"
            )
        for directory_id in package.execution_directories:
            require_safe_authorization_id(
                directory_id,
                label="historical reconciliation execution directory",
            )
        if package.execution_id not in package.execution_directories:
            raise GitProvenanceAuthorizationError(
                "historical reconciliation execution_id is not one of the "
                "declared execution directories"
            )
        if len(package.files) != package.expected_file_count:
            raise GitProvenanceAuthorizationError(
                "historical reconciliation declared file count does not match "
                "its immutable declaration"
            )

        declared: list[dict[str, Any]] = []
        declared_paths: set[str] = set()
        expected_execution_directories = set(package.execution_directories)
        prefix = f"{normalized_root}/"
        for member in package.files:
            if not isinstance(member, HistoricalReconciliationFile):
                raise GitProvenanceAuthorizationError(
                    "historical reconciliation member declaration is malformed"
                )
            normalized = _normalize_git_path(
                member.path, label="historical reconciliation member path"
            )
            if not normalized.startswith(prefix):
                raise GitProvenanceAuthorizationError(
                    "historical reconciliation member is outside its package root"
                )
            if normalized in declared_paths:
                raise GitProvenanceAuthorizationError(
                    "duplicate historical reconciliation member path"
                )
            if (
                type(member.size) is not int
                or type(member.size) is bool
                or member.size < 0
            ):
                raise GitProvenanceAuthorizationError(
                    "historical reconciliation member size is invalid"
                )
            digest = _require_hex64(
                member.sha256, label="historical reconciliation member sha256"
            )
            declared_paths.add(normalized)
            relative_member = normalized[len(prefix) :]
            member_execution_directory = relative_member.split("/", 1)[0]
            if member_execution_directory not in expected_execution_directories:
                raise GitProvenanceAuthorizationError(
                    "historical reconciliation member is outside the exact "
                    "execution-directory declaration"
                )
            declared.append(
                {"path": normalized, "sha256": digest, "size": member.size}
            )
        declared.sort(key=lambda item: item["path"])
        if package.inventory_sha256() != package.expected_inventory_sha256:
            raise GitProvenanceAuthorizationError(
                "historical reconciliation package inventory digest does not "
                "match its immutable declaration: " + normalized_root
            )

        package_dir = root / normalized_root
        if os.path.islink(package_dir):
            raise GitProvenanceAuthorizationError(
                "historical reconciliation package root must not be a symlink: "
                + normalized_root
            )
        if not package_dir.is_dir():
            raise GitProvenanceAuthorizationError(
                "declared historical reconciliation package root is missing: "
                + normalized_root
            )
        try:
            root_entries = sorted(
                os.scandir(package_dir), key=lambda entry: entry.name
            )
        except OSError as exc:
            raise GitProvenanceAuthorizationError(
                "historical reconciliation package root could not be read: "
                + normalized_root
            ) from exc
        actual_execution_directories: set[str] = set()
        for entry in root_entries:
            relative = f"{normalized_root}/{entry.name}"
            if entry.is_symlink():
                raise GitProvenanceAuthorizationError(
                    "historical reconciliation package contains a symlink: "
                    + relative
                )
            try:
                mode = entry.stat(follow_symlinks=False).st_mode
            except OSError as exc:
                raise GitProvenanceAuthorizationError(
                    "historical reconciliation package entry could not be "
                    "inspected: " + relative
                ) from exc
            if not stat.S_ISDIR(mode):
                raise GitProvenanceAuthorizationError(
                    "historical reconciliation package root contains a "
                    "non-execution entry: " + relative
                )
            actual_execution_directories.add(entry.name)
        if actual_execution_directories != expected_execution_directories:
            raise GitProvenanceAuthorizationError(
                "historical reconciliation execution-directory inventory does "
                "not match its immutable declaration: " + normalized_root
            )

        actual = _inventory_bound_package_files(
            root=root,
            package_dir=package_dir,
            package_prefix=normalized_root,
            label="historical reconciliation package",
        )
        if actual != declared:
            raise GitProvenanceAuthorizationError(
                "historical reconciliation package file inventory does not "
                "match its immutable declaration: " + normalized_root
            )
        tracked_members = sorted(
            item["path"] for item in actual if item["path"] in tracked
        )
        if tracked_members:
            raise GitProvenanceAuthorizationError(
                "historical reconciliation package member is tracked at HEAD "
                "instead of preserved untracked evidence: "
                + ", ".join(tracked_members)
            )
        for item in actual:
            if item["path"] in seen_paths:
                raise GitProvenanceAuthorizationError(
                    "duplicate historical reconciliation evidence path: "
                    + item["path"]
                )
            seen_paths.add(item["path"])
            records.append(
                {
                    **item,
                    "evidence_class": package.evidence_class,
                    "reconciliation_execution_id": package.execution_id,
                }
            )
    records.sort(key=lambda item: item["path"])
    return tuple(records)


def _inventory_bound_package_files(
    *,
    root: Path,
    package_dir: Path,
    package_prefix: str,
    label: str,
) -> list[dict[str, Any]]:
    """Recursively inventory regular files under one exact package directory."""
    prefix = f"{package_prefix}/"
    collected: list[dict[str, Any]] = []
    stack = [package_dir]
    while stack:
        directory = stack.pop()
        try:
            entries = sorted(os.scandir(directory), key=lambda item: item.name)
        except OSError as exc:
            raise GitProvenanceAuthorizationError(
                f"{label} could not be read: {package_prefix}"
            ) from exc
        for entry in entries:
            path = Path(entry.path)
            try:
                relative = path.relative_to(root).as_posix()
            except ValueError as exc:
                raise GitProvenanceAuthorizationError(
                    f"{label} entry resolves outside the repository"
                ) from exc
            if entry.is_symlink():
                raise GitProvenanceAuthorizationError(
                    f"{label} contains a symlink: {relative}"
                )
            try:
                mode = entry.stat(follow_symlinks=False).st_mode
            except OSError as exc:
                raise GitProvenanceAuthorizationError(
                    f"{label} entry could not be inspected: {relative}"
                ) from exc
            if stat.S_ISDIR(mode):
                stack.append(path)
                continue
            if not stat.S_ISREG(mode):
                raise GitProvenanceAuthorizationError(
                    f"{label} contains a non-regular entry: {relative}"
                )
            normalized = _normalize_git_path(relative, label=f"{label} inventory")
            if not normalized.startswith(prefix):
                raise GitProvenanceAuthorizationError(
                    f"{label} path is outside its package root: {normalized}"
                )
            collected.append(
                {
                    "path": normalized,
                    "sha256": _sha256_file(path),
                    "size": path.stat().st_size,
                }
            )
    collected.sort(key=lambda item: item["path"])
    return collected


def _validated_current_migration_identity(
    profile: GitAuthorizationProfile,
) -> tuple[str, int, str] | None:
    """Validate the optional all-or-nothing current-package declaration."""
    values = (
        profile.current_migration_execution_id,
        profile.current_migration_expected_file_count,
        profile.current_migration_expected_inventory_sha256,
    )
    populated = tuple(value is not None for value in values)
    if not any(populated):
        return None
    if not all(populated):
        raise GitProvenanceAuthorizationError(
            "current migration identity fields must be all populated or all None"
        )
    execution_id = require_safe_authorization_id(
        profile.current_migration_execution_id,
        label="current migration execution_id",
    )
    expected_file_count = profile.current_migration_expected_file_count
    if (
        type(expected_file_count) is not int
        or type(expected_file_count) is bool
        or expected_file_count < 1
    ):
        raise GitProvenanceAuthorizationError(
            "current migration expected file count must be a positive integer"
        )
    expected_inventory_sha256 = _require_hex64(
        profile.current_migration_expected_inventory_sha256,
        label="current migration expected inventory sha256",
    )
    return execution_id, expected_file_count, expected_inventory_sha256


def _validate_current_migration_package_identity(
    *,
    root: Path,
    profile: GitAuthorizationProfile,
    identity: tuple[str, int, str],
) -> None:
    """Require the complete current package to equal its committed identity."""
    execution_id, expected_file_count, expected_inventory_sha256 = identity
    package_root = root / profile.migration_package_root
    package_prefix = f"{profile.migration_package_root}/{execution_id}"
    package_dir = package_root / execution_id
    if os.path.islink(package_root) or os.path.islink(package_dir):
        raise GitProvenanceAuthorizationError(
            "current migration package identity must not contain a symlink: "
            + package_prefix
        )
    if not package_dir.exists():
        raise GitProvenanceAuthorizationError(
            "current migration package execution directory is missing: "
            + package_prefix
        )
    if not package_dir.is_dir():
        raise GitProvenanceAuthorizationError(
            "current migration package execution path is not a directory: "
            + package_prefix
        )
    if not os.access(package_dir, os.R_OK | os.X_OK):
        raise GitProvenanceAuthorizationError(
            "current migration package execution directory is not readable: "
            + package_prefix
        )
    files = _inventory_bound_package_files(
        root=root,
        package_dir=package_dir,
        package_prefix=package_prefix,
        label="current migration package",
    )
    if len(files) != expected_file_count:
        raise GitProvenanceAuthorizationError(
            "current migration package inventory file count does not match its "
            f"immutable declaration: {package_prefix} "
            f"(expected {expected_file_count}, found {len(files)})"
        )
    inventory_sha256 = compute_historical_migration_inventory_sha256(
        package_root=profile.migration_package_root,
        execution_id=execution_id,
        evidence_class=profile.migration_package_kind,
        files=files,
    )
    if inventory_sha256 != expected_inventory_sha256:
        raise GitProvenanceAuthorizationError(
            "current migration package inventory digest does not match its "
            f"immutable declaration: {package_prefix} "
            f"(expected {expected_inventory_sha256}, computed {inventory_sha256})"
        )


def _inventory_authorization_package_files(
    *,
    root: Path,
    package_dir: Path,
    package_id: str,
    authorization_package_root: str = AUTHORIZATION_PACKAGE_ROOT,
) -> list[dict[str, Any]]:
    """Recursively inventory regular files under one authorization package."""
    prefix = f"{authorization_package_root}/{package_id}/"
    collected: list[dict[str, Any]] = []
    stack = [package_dir]
    while stack:
        directory = stack.pop()
        try:
            entries = sorted(os.scandir(directory), key=lambda item: item.name)
        except OSError as exc:
            raise GitProvenanceAuthorizationError(
                f"historical authorization package could not be read: {package_id}"
            ) from exc
        for entry in entries:
            path = Path(entry.path)
            try:
                relative = path.relative_to(root).as_posix()
            except ValueError as exc:
                raise GitProvenanceAuthorizationError(
                    "historical authorization package entry resolves outside the repository"
                ) from exc
            if entry.is_symlink():
                raise GitProvenanceAuthorizationError(
                    f"historical authorization package contains a symlink: {relative}"
                )
            try:
                mode = entry.stat(follow_symlinks=False).st_mode
            except OSError as exc:
                raise GitProvenanceAuthorizationError(
                    f"historical authorization package entry could not be inspected: {relative}"
                ) from exc
            if stat.S_ISDIR(mode):
                stack.append(path)
                continue
            if not stat.S_ISREG(mode):
                raise GitProvenanceAuthorizationError(
                    f"historical authorization package contains a non-regular entry: {relative}"
                )
            normalized = _normalize_git_path(
                relative, label="historical authorization inventory"
            )
            if not normalized.startswith(prefix):
                raise GitProvenanceAuthorizationError(
                    f"historical authorization path is outside its package root: {normalized}"
                )
            collected.append(
                {
                    "path": normalized,
                    "sha256": _sha256_file(path),
                    "size": path.stat().st_size,
                }
            )
    collected.sort(key=lambda item: item["path"])
    return collected


def _validate_repository_relative_path(raw_path: Any, *, package_root: str) -> str:
    text = _require_str(raw_path, label="manifest file path")
    if "\\" in text:
        raise GitProvenanceAuthorizationError(
            "manifest file path must be POSIX and contain no backslash"
        )
    candidate = PurePosixPath(text)
    if candidate.is_absolute():
        raise GitProvenanceAuthorizationError(
            "manifest file path must not be absolute"
        )
    parts = candidate.parts
    if ".." in parts or any(part in ("", ".") for part in parts):
        raise GitProvenanceAuthorizationError(
            "manifest file path must not contain traversal or empty segments"
        )
    if text.endswith("/"):
        raise GitProvenanceAuthorizationError(
            "manifest file path must not be a directory"
        )
    if any(character in text for character in _GLOB_CHARACTERS):
        raise GitProvenanceAuthorizationError(
            "manifest file path must not contain glob characters"
        )
    normalized = candidate.as_posix()
    if normalized != text:
        raise GitProvenanceAuthorizationError(
            "manifest file path must be already normalized"
        )
    prefix = f"{package_root}/"
    if not normalized.startswith(prefix) or len(normalized) <= len(prefix):
        raise GitProvenanceAuthorizationError(
            "manifest file path is outside its declared package root"
        )
    return normalized


def _validate_repository_file(
    normalized: str, *, root: Path, expected_sha256: str, expected_size: int
) -> None:
    walked = root
    for part in PurePosixPath(normalized).parts:
        walked = walked / part
        if os.path.islink(walked):
            raise GitProvenanceAuthorizationError(
                "manifest file path contains a symlink component"
            )
    absolute = (root / normalized).resolve()
    if not (absolute == root or absolute.is_relative_to(root)):
        raise GitProvenanceAuthorizationError(
            "manifest file resolves outside the repository"
        )
    target = root / normalized
    if not target.is_file():
        raise GitProvenanceAuthorizationError(
            f"manifest file is missing or not a regular file: {normalized}"
        )
    actual_size = target.stat().st_size
    if actual_size != expected_size:
        raise GitProvenanceAuthorizationError(
            f"manifest file size mismatch: {normalized}"
        )
    actual_sha256 = _sha256_file(target)
    if actual_sha256 != expected_sha256:
        raise GitProvenanceAuthorizationError(
            f"manifest file SHA-256 mismatch: {normalized}"
        )


def _validate_authorization_document(
    manifest: Mapping[str, Any],
    *,
    root: Path,
    authorization_id: str,
    migration_execution_id: str,
    branch: str,
    head: str,
    profile: GitAuthorizationProfile,
) -> tuple[str, dict[str, Any], tuple[str, ...]]:
    reference = manifest["authorization_file"]
    if not isinstance(reference, Mapping):
        raise GitProvenanceAuthorizationError("authorization_file must be an object")
    _require_keys(
        reference, _MANIFEST_AUTHORIZATION_FILE_KEYS, label="authorization_file"
    )
    relative = _validate_repository_relative_path(
        reference["path"], package_root=profile.authorization_package_root
    )
    expected_sha256 = _require_hex64(
        reference["sha256"], label="authorization_file sha256"
    )
    prefix = f"{profile.authorization_package_root}/{authorization_id}/"
    if not relative.startswith(prefix):
        raise GitProvenanceAuthorizationError(
            "authorization_file is outside the authorization package"
        )
    document_path = root / relative
    if not document_path.is_file():
        raise GitProvenanceAuthorizationError(
            "referenced final authorization document is missing"
        )
    actual_sha256 = _sha256_file(document_path)
    if actual_sha256 != expected_sha256:
        raise GitProvenanceAuthorizationError(
            "referenced final authorization document SHA-256 mismatch"
        )
    document = _load_json_object(document_path, label="final authorization document")
    if document.get("authorization_id") != authorization_id:
        raise GitProvenanceAuthorizationError(
            "final authorization document authorization_id mismatch"
        )
    if document.get("migration_execution_id") != migration_execution_id:
        raise GitProvenanceAuthorizationError(
            "final authorization migration_execution_id mismatch"
        )
    if (
        profile.current_migration_execution_id is not None
        and document.get("migration_execution_id")
        != profile.current_migration_execution_id
    ):
        raise GitProvenanceAuthorizationError(
            "final authorization current migration_execution_id mismatch"
        )
    approved_historical_ids = extract_approved_historical_authorization_ids(
        document, current_authorization_id=authorization_id
    )
    try:
        from printer_v1.operator_cli.authorization_temporal_validity import (
            AuthorizationTemporalError,
            validate_authorization_temporal_validity,
        )
        validate_authorization_temporal_validity(document)
    except AuthorizationTemporalError as exc:
        raise GitProvenanceAuthorizationError(
            f"authorization temporal validity failed: {exc}"
        ) from exc

    from printer_v1.operator_cli.pre_authorization_migration_ledger_guard import (
        PACKAGE_BINDING_FIELDS,
        MigrationLedgerDriftGuardError,
        package_binding_from_document,
    )

    # Each wrapper-bound profile validates its document with its OWN authority.
    # A document that satisfies one authority can never satisfy another: the
    # schema version, authorized mode and exact policy key all differ.
    if profile in (
        STANDARD_FOUR_HOUR_AUTHORIZATION_PROFILE,
        FOUR_TOKEN_PROOF_AUTHORIZATION_PROFILE,
        FOUR_TOKEN_STANDARD_FOUR_HOUR_AUTHORIZATION_PROFILE,
    ):
        if profile == STANDARD_FOUR_HOUR_AUTHORIZATION_PROFILE:
            try:
                from printer_v1.operator_cli.standard_four_hour_one_shot_wrapper import (
                    StandardFourHourOneShotWrapperError,
                    validate_standard_four_hour_authorization_document,
                )
                validated_document = validate_standard_four_hour_authorization_document(document)
            except StandardFourHourOneShotWrapperError as exc:
                raise GitProvenanceAuthorizationError(
                    f"standard four-hour authorization document rejected: {exc}"
                ) from exc
        elif profile == FOUR_TOKEN_STANDARD_FOUR_HOUR_AUTHORIZATION_PROFILE:
            try:
                from printer_v1.operator_cli.four_token_standard_four_hour_one_shot_wrapper import (
                    FourTokenStandardFourHourOneShotWrapperError,
                    validate_four_token_standard_four_hour_authorization_document,
                )
                validated_document = (
                    validate_four_token_standard_four_hour_authorization_document(
                        document
                    )
                )
            except FourTokenStandardFourHourOneShotWrapperError as exc:
                raise GitProvenanceAuthorizationError(
                    "four-token standard four-hour authorization document "
                    f"rejected: {exc}"
                ) from exc
        else:
            try:
                from printer_v1.operator_cli.four_token_proof_one_shot_wrapper import (
                    FourTokenProofOneShotWrapperError,
                    validate_four_token_proof_authorization_document,
                )
                validated_document = validate_four_token_proof_authorization_document(
                    document
                )
            except FourTokenProofOneShotWrapperError as exc:
                raise GitProvenanceAuthorizationError(
                    f"four-token proof authorization document rejected: {exc}"
                ) from exc
        repository = validated_document["repository"]
        if repository.get("branch") != branch:
            raise GitProvenanceAuthorizationError(
                "final authorization branch does not match live Git state"
            )
        if _require_head(repository.get("head"), label="authorization head") != head:
            raise GitProvenanceAuthorizationError(
                "final authorization HEAD does not match live Git state"
            )
        command = validated_document["authorized_command"]
        _require_command(
            command, label="authorized_command", required_mode=profile.command_mode
        )
        document_for_binding = validated_document
    else:
        verdict = _require_str(document.get("verdict"), label="authorization verdict")
        if not verdict.endswith("_PASS"):
            raise GitProvenanceAuthorizationError(
                "final authorization verdict is not PASS"
            )
        authorized_git = document.get("authorized_git")
        if not isinstance(authorized_git, Mapping):
            raise GitProvenanceAuthorizationError("authorized_git must be an object")
        if authorized_git.get("branch") != branch:
            raise GitProvenanceAuthorizationError(
                "final authorization branch does not match live Git state"
            )
        if _require_head(authorized_git.get("head"), label="authorization head") != head:
            raise GitProvenanceAuthorizationError(
                "final authorization HEAD does not match live Git state"
            )
        command = document.get("authorized_command")
        if not isinstance(command, Mapping):
            raise GitProvenanceAuthorizationError("authorized_command must be an object")
        if command.get("mode") != profile.command_mode:
            raise GitProvenanceAuthorizationError(
                f"authorized command mode must be {profile.command_mode!r}"
            )
        _require_true(
            command.get("operator_approved"), label="authorized operator_approved"
        )
        if command.get("allowed_invocation_count") != 1 or type(
            command.get("allowed_invocation_count")
        ) is bool:
            raise GitProvenanceAuthorizationError(
                "authorized allowed_invocation_count must be exactly 1"
            )
        for flag in _MARKER_FALSE_FLAGS:
            _require_false(command.get(flag), label=f"authorized {flag}")
        policy = document.get("campaign_policy")
        if not isinstance(policy, Mapping):
            raise GitProvenanceAuthorizationError("campaign_policy must be an object")
        if policy.get("main_window") != REQUIRED_MAIN_WINDOW:
            raise GitProvenanceAuthorizationError(
                f"campaign main_window must be {REQUIRED_MAIN_WINDOW!r}"
            )
        _require_false(
            policy.get("selective_1h_continuation"),
            label="campaign selective_1h_continuation",
        )
        document_for_binding = document

    try:
        database = package_binding_from_document(document_for_binding)
    except MigrationLedgerDriftGuardError as exc:
        raise GitProvenanceAuthorizationError(str(exc)) from exc
    if set(database) != set(PACKAGE_BINDING_FIELDS):
        raise GitProvenanceAuthorizationError(
            "authoritative_database must contain the exact required fields"
        )
    database["path"] = _require_str(
        database["path"], label="authoritative_database path"
    )
    database["sha256"] = _require_hex64(
        database["sha256"], label="authoritative_database sha256"
    )
    for field in ("size", "inode", "mtime_ns", "migration_count"):
        value = database[field]
        if type(value) is not int or value < 0:
            raise GitProvenanceAuthorizationError(
                f"authoritative_database {field} must be a non-negative integer"
            )
    database["migration_head"] = _require_str(
        database["migration_head"], label="authoritative_database migration_head"
    )
    return actual_sha256, database, approved_historical_ids


def _validate_files(
    manifest: Mapping[str, Any],
    *,
    root: Path,
    authorization_id: str,
    migration_execution_id: str,
    profile: GitAuthorizationProfile,
) -> tuple[str, ...]:
    files = manifest["files"]
    if not isinstance(files, list) or not files:
        raise GitProvenanceAuthorizationError(
            "manifest files must be a non-empty array"
        )
    valid_kinds = {profile.migration_package_kind, profile.authorization_package_kind}
    seen: set[str] = set()
    ordered: list[str] = []
    for entry in files:
        if not isinstance(entry, Mapping):
            raise GitProvenanceAuthorizationError("manifest file entry must be object")
        _require_keys(entry, _MANIFEST_FILE_KEYS, label="manifest file entry")
        package_kind = entry["package_kind"]
        if package_kind not in valid_kinds:
            raise GitProvenanceAuthorizationError(
                f"manifest file package_kind is invalid: {package_kind!r}"
            )
        package_root = (
            f"{profile.migration_package_root}/{migration_execution_id}"
            if package_kind == profile.migration_package_kind
            else f"{profile.authorization_package_root}/{authorization_id}"
        )
        normalized = _validate_repository_relative_path(
            entry["path"], package_root=package_root
        )
        if normalized in seen:
            raise GitProvenanceAuthorizationError(
                f"duplicate manifest file path: {normalized}"
            )
        seen.add(normalized)
        size = entry["size"]
        if type(size) is not int or type(size) is bool or size < 0:
            raise GitProvenanceAuthorizationError(
                "manifest file size must be a non-negative integer"
            )
        expected_sha256 = _require_hex64(
            entry["sha256"], label="manifest file sha256"
        )
        _validate_repository_file(
            normalized, root=root, expected_sha256=expected_sha256, expected_size=size
        )
        ordered.append(normalized)
    return tuple(ordered)


def _validate_historical_authorization_evidence(
    manifest: Mapping[str, Any],
    *,
    root: Path,
    authorization_id: str,
    approved_historical_authorization_ids: Collection[str],
    tracked_paths: set[str],
    current_manifest_paths: set[str],
    profile: GitAuthorizationProfile,
) -> tuple[str, ...]:
    historical = manifest.get("historical_authorization_evidence")
    if not isinstance(historical, list):
        raise GitProvenanceAuthorizationError(
            "historical_authorization_evidence must be an array"
        )
    approved = set(
        validate_prior_authorizations_non_reusable(
            list(approved_historical_authorization_ids),
            current_authorization_id=authorization_id,
        )
    )
    seen: set[str] = set()
    ordered: list[str] = []
    root_by_authorization: dict[str, str] = {}
    for entry in historical:
        if not isinstance(entry, Mapping):
            raise GitProvenanceAuthorizationError(
                "historical authorization evidence entry must be an object"
            )
        _require_keys(
            entry, _HISTORICAL_EVIDENCE_KEYS,
            label="historical authorization evidence entry",
        )
        if entry.get("evidence_class") != HISTORICAL_AUTHORIZATION_EVIDENCE_CLASS:
            raise GitProvenanceAuthorizationError(
                "historical authorization evidence_class is invalid"
            )
        hist_auth_id = require_safe_authorization_id(
            entry.get("authorization_id"), label="historical authorization_id"
        )
        if hist_auth_id == authorization_id or hist_auth_id not in approved:
            raise GitProvenanceAuthorizationError(
                "historical authorization evidence authorization_id is not approved"
            )
        raw_path = _require_str(entry.get("path"), label="historical authorization path")
        matching_roots = [
            auth_root
            for auth_root in profile.historical_authorization_package_roots
            if raw_path.startswith(f"{auth_root}/{hist_auth_id}/")
        ]
        if len(matching_roots) != 1:
            raise GitProvenanceAuthorizationError(
                "historical authorization evidence path does not bind one approved root"
            )
        authorization_root = matching_roots[0]
        prior_root = root_by_authorization.get(hist_auth_id)
        if prior_root is not None and prior_root != authorization_root:
            raise GitProvenanceAuthorizationError(
                "historical authorization id is ambiguous across authorization roots"
            )
        root_by_authorization[hist_auth_id] = authorization_root
        package_root = f"{authorization_root}/{hist_auth_id}"
        normalized = _validate_repository_relative_path(
            raw_path, package_root=package_root
        )
        if normalized in seen or normalized in current_manifest_paths:
            raise GitProvenanceAuthorizationError(
                f"duplicate historical authorization evidence path: {normalized}"
            )
        if normalized in tracked_paths:
            raise GitProvenanceAuthorizationError(
                f"historical authorization evidence path is tracked at HEAD: {normalized}"
            )
        seen.add(normalized)
        size = entry["size"]
        if type(size) is not int or type(size) is bool or size < 0:
            raise GitProvenanceAuthorizationError(
                "historical authorization evidence size must be a non-negative integer"
            )
        expected_sha256 = _require_hex64(
            entry["sha256"], label="historical authorization evidence sha256"
        )
        disposition = entry.get("terminal_disposition")
        if (
            type(disposition) is not str
            or not disposition
            or disposition not in TERMINAL_DISPOSITION_VOCABULARY
        ):
            raise GitProvenanceAuthorizationError(
                "historical authorization terminal_disposition is invalid"
            )
        _validate_repository_file(
            normalized, root=root, expected_sha256=expected_sha256, expected_size=size
        )
        ordered.append(normalized)
    if ordered != sorted(ordered):
        raise GitProvenanceAuthorizationError(
            "historical_authorization_evidence must be sorted by path"
        )
    return tuple(ordered)


def _validate_historical_migration_evidence(
    manifest: Mapping[str, Any],
    *,
    root: Path,
    tracked_paths: set[str],
    current_manifest_paths: set[str],
    historical_authorization_paths: set[str],
    current_package_roots: tuple[str, str],
    profile: GitAuthorizationProfile,
) -> tuple[str, ...]:
    """Validate declared historical migration evidence against the exact binding.

    Every record must name one exact profile-bound package and bind a real
    regular file by normalized path, size and SHA-256. This class never carries
    authorization identity, never reuses the authorization trust root, and never
    lies inside a current evidence package.
    """
    declared = manifest.get(HISTORICAL_MIGRATION_EVIDENCE_KEY)
    if not profile.historical_migration_packages:
        if declared is not None:
            raise GitProvenanceAuthorizationError(
                "historical_migration_evidence is not accepted by this profile"
            )
        return ()
    if not isinstance(declared, list):
        raise GitProvenanceAuthorizationError(
            "historical_migration_evidence must be an array"
        )
    approved = {
        package.package_prefix: package
        for package in profile.historical_migration_packages
    }
    seen: set[str] = set()
    ordered: list[str] = []
    for entry in declared:
        if not isinstance(entry, Mapping):
            raise GitProvenanceAuthorizationError(
                "historical migration evidence entry must be an object"
            )
        _require_keys(
            entry,
            _HISTORICAL_MIGRATION_EVIDENCE_KEYS,
            label="historical migration evidence entry",
        )
        raw_path = _require_str(entry.get("path"), label="historical migration path")
        matching = [
            package
            for prefix, package in approved.items()
            if raw_path.startswith(f"{prefix}/")
        ]
        if len(matching) != 1:
            raise GitProvenanceAuthorizationError(
                "historical migration evidence path does not bind one exact "
                "approved historical migration package"
            )
        package = matching[0]
        if entry.get("evidence_class") != package.evidence_class:
            raise GitProvenanceAuthorizationError(
                "historical migration evidence_class is invalid"
            )
        if entry.get("migration_execution_id") != package.execution_id:
            raise GitProvenanceAuthorizationError(
                "historical migration evidence migration_execution_id is not the "
                "approved historical execution id"
            )
        if entry.get("migration_execution_id") == manifest.get(
            "migration_execution_id"
        ):
            raise GitProvenanceAuthorizationError(
                "historical migration evidence must not claim the current "
                "migration execution id"
            )
        normalized = _validate_repository_relative_path(
            raw_path, package_root=package.package_prefix
        )
        if any(
            _is_beneath_root(normalized, current_root)
            for current_root in current_package_roots
        ):
            raise GitProvenanceAuthorizationError(
                "historical migration evidence path lies inside a current "
                f"evidence package: {normalized}"
            )
        if (
            normalized in seen
            or normalized in current_manifest_paths
            or normalized in historical_authorization_paths
        ):
            raise GitProvenanceAuthorizationError(
                f"duplicate historical migration evidence path: {normalized}"
            )
        if normalized in tracked_paths:
            raise GitProvenanceAuthorizationError(
                f"historical migration evidence path is tracked at HEAD: {normalized}"
            )
        seen.add(normalized)
        size = entry["size"]
        if type(size) is not int or type(size) is bool or size < 0:
            raise GitProvenanceAuthorizationError(
                "historical migration evidence size must be a non-negative integer"
            )
        expected_sha256 = _require_hex64(
            entry["sha256"], label="historical migration evidence sha256"
        )
        _validate_repository_file(
            normalized, root=root, expected_sha256=expected_sha256, expected_size=size
        )
        ordered.append(normalized)
    if ordered != sorted(ordered):
        raise GitProvenanceAuthorizationError(
            "historical_migration_evidence must be sorted by path"
        )
    return tuple(ordered)


def _allowed_file_digest_records(
    manifest: Mapping[str, Any],
    *,
    historical_reconciliation_evidence: Iterable[Mapping[str, Any]] = (),
) -> list[dict[str, Any]]:
    """Map current files and historical evidence into allowlist digest records."""
    records: list[dict[str, Any]] = []
    for entry in manifest["files"]:
        records.append(
            {
                "package_kind": entry["package_kind"],
                "path": entry["path"],
                "sha256": entry["sha256"],
                "size": entry["size"],
            }
        )
    historical = manifest.get("historical_authorization_evidence") or []
    for entry in historical:
        records.append(
            {
                "package_kind": entry["evidence_class"],
                "path": entry["path"],
                "sha256": entry["sha256"],
                "size": entry["size"],
            }
        )
    # Historical migration bytes are cryptographically bound before any marker
    # is created, exactly like current and historical authorization evidence.
    historical_migration = manifest.get(HISTORICAL_MIGRATION_EVIDENCE_KEY) or []
    for entry in historical_migration:
        records.append(
            {
                "package_kind": entry["evidence_class"],
                "path": entry["path"],
                "sha256": entry["sha256"],
                "size": entry["size"],
            }
        )
    for entry in historical_reconciliation_evidence:
        records.append(
            {
                "package_kind": entry["evidence_class"],
                "path": entry["path"],
                "sha256": entry["sha256"],
                "size": entry["size"],
            }
        )
    return records


def _validate_marker(
    marker_path: Path,
    *,
    marker_sha256: str,
    authorization_id: str,
    authorization_sha256: str,
    manifest_sha256: str,
    allowed_file_set_sha256: str,
    branch: str,
    head: str,
    required_mode: str = REQUIRED_COMMAND_MODE,
) -> dict[str, Any]:
    marker = _load_json_object(marker_path, label="application marker")
    _require_keys(marker, _MARKER_KEYS, label="application marker")
    if marker.get("schema_version") != APPLICATION_MARKER_SCHEMA_VERSION:
        raise GitProvenanceAuthorizationError("application marker schema_version is invalid")
    if marker.get("authorization_id") != authorization_id:
        raise GitProvenanceAuthorizationError("application marker authorization_id mismatch")
    _require_tz_aware(
        marker.get("authorization_consumed_at"),
        label="application marker authorization_consumed_at",
    )
    if _require_hex64(marker.get("authorization_sha256"), label="marker authorization_sha256") != authorization_sha256:
        raise GitProvenanceAuthorizationError("application marker authorization_sha256 mismatch")
    if _require_hex64(marker.get("manifest_sha256"), label="marker manifest_sha256") != manifest_sha256:
        raise GitProvenanceAuthorizationError("application marker manifest_sha256 mismatch")
    if _require_hex64(marker.get("allowed_file_set_sha256"), label="marker allowed_file_set_sha256") != allowed_file_set_sha256:
        raise GitProvenanceAuthorizationError("application marker allowed_file_set_sha256 mismatch")
    if marker.get("repository_branch") != branch:
        raise GitProvenanceAuthorizationError("application marker repository_branch mismatch")
    if _require_head(marker.get("repository_head"), label="marker repository_head") != head:
        raise GitProvenanceAuthorizationError("application marker repository_head mismatch")
    _require_command(
        marker.get("command"), label="application marker command", required_mode=required_mode
    )
    if marker.get("allowed_invocation_count") != 1 or type(marker.get("allowed_invocation_count")) is bool:
        raise GitProvenanceAuthorizationError(
            "application marker allowed_invocation_count must be exactly 1"
        )
    for flag in _MARKER_FALSE_FLAGS:
        _require_false(marker.get(flag), label=f"application marker {flag}")
    return marker


def validate_git_provenance_manifest_pre_marker(
    *,
    repository_root: str | Path,
    manifest_path: str,
    manifest_sha256: str,
    profile: GitAuthorizationProfile | None = None,
    git_executable: str = "git",
    timeout_seconds: float = GIT_COMMAND_TIMEOUT_SECONDS,
    runner: Callable[..., Any] = subprocess.run,
    sidecar_untracked_paths: Iterable[str] = (),
) -> PreparedGitProvenanceAuthorization:
    """Validate the full manifest/Git/filesystem boundary before consumption."""
    active_profile = _resolved_profile(profile)
    current_migration_identity = _validated_current_migration_identity(
        active_profile
    )
    if not 0 < timeout_seconds <= GIT_COMMAND_TIMEOUT_SECONDS:
        raise GitProvenanceAuthorizationError(
            "Git provenance timeout is outside the fixed ceiling"
        )
    root = Path(repository_root).resolve()
    if not root.is_dir():
        raise GitProvenanceAuthorizationError("repository root is unavailable")
    manifest_file, actual_manifest_sha256 = _resolve_external_file(
        manifest_path, root=root, expected_sha256=manifest_sha256, label="manifest"
    )
    manifest = _load_json_object(manifest_file, label="manifest")
    _require_keys(
        manifest, expected_manifest_keys(active_profile), label="manifest"
    )
    if manifest.get("schema_version") != active_profile.manifest_schema_version:
        raise GitProvenanceAuthorizationError("manifest schema_version is invalid")
    authorization_id = _require_str(
        manifest.get("authorization_id"), label="manifest authorization_id"
    )
    migration_execution_id = _require_str(
        manifest.get("migration_execution_id"), label="manifest migration_execution_id"
    )
    if (
        current_migration_identity is not None
        and migration_execution_id != current_migration_identity[0]
    ):
        raise GitProvenanceAuthorizationError(
            "manifest current migration execution_id does not match the exact "
            "profile identity"
        )
    _require_tz_aware(manifest.get("created_at"), label="manifest created_at")
    repository = manifest.get("repository")
    if not isinstance(repository, Mapping):
        raise GitProvenanceAuthorizationError("manifest repository must be an object")
    _require_keys(repository, _MANIFEST_REPOSITORY_KEYS, label="manifest repository")
    manifest_branch = _require_str(repository.get("branch"), label="manifest repository branch")
    manifest_head = _require_head(repository.get("head"), label="manifest repository head")
    _require_command(
        manifest.get("authorized_command"),
        label="manifest authorized_command",
        required_mode=active_profile.command_mode,
    )
    branch, head = _live_repository_identity(
        root, git_executable=git_executable, timeout_seconds=timeout_seconds, runner=runner
    )
    if manifest_branch != branch or manifest_head != head:
        raise GitProvenanceAuthorizationError(
            "manifest repository identity does not match live Git state"
        )
    authorization_sha256, authoritative_database, approved_historical_ids = (
        _validate_authorization_document(
            manifest,
            root=root,
            authorization_id=authorization_id,
            migration_execution_id=migration_execution_id,
            branch=branch,
            head=head,
            profile=active_profile,
        )
    )
    if current_migration_identity is not None:
        _validate_current_migration_package_identity(
            root=root,
            profile=active_profile,
            identity=current_migration_identity,
        )
    current_paths = _validate_files(
        manifest,
        root=root,
        authorization_id=authorization_id,
        migration_execution_id=migration_execution_id,
        profile=active_profile,
    )
    tracked_paths = _tracked_operator_runs_paths(
        root, git_executable=git_executable, timeout_seconds=timeout_seconds, runner=runner
    )
    historical_paths = _validate_historical_authorization_evidence(
        manifest,
        root=root,
        authorization_id=authorization_id,
        approved_historical_authorization_ids=approved_historical_ids,
        tracked_paths=tracked_paths,
        current_manifest_paths=set(current_paths),
        profile=active_profile,
    )
    expected_historical = enumerate_historical_authorization_evidence(
        repository_root=root,
        current_authorization_id=authorization_id,
        approved_historical_authorization_ids=approved_historical_ids,
        tracked_operator_runs_paths=tracked_paths,
        authorization_package_roots=active_profile.historical_authorization_package_roots,
        current_authorization_package_root=active_profile.authorization_package_root,
        git_executable=git_executable,
        timeout_seconds=timeout_seconds,
        runner=runner,
    )
    expected_historical_paths = tuple(item["path"] for item in expected_historical)
    if historical_paths != expected_historical_paths:
        raise GitProvenanceAuthorizationError(
            "historical_authorization_evidence does not match the approved historical authorization inventory"
        )
    current_package_roots = (
        f"{active_profile.migration_package_root}/{migration_execution_id}",
        f"{active_profile.authorization_package_root}/{authorization_id}",
    )
    historical_migration_paths = _validate_historical_migration_evidence(
        manifest,
        root=root,
        tracked_paths=tracked_paths,
        current_manifest_paths=set(current_paths),
        historical_authorization_paths=set(historical_paths),
        current_package_roots=current_package_roots,
        profile=active_profile,
    )
    expected_historical_migration = enumerate_historical_migration_evidence(
        repository_root=root,
        historical_migration_packages=active_profile.historical_migration_packages,
        tracked_operator_runs_paths=tracked_paths,
        git_executable=git_executable,
        timeout_seconds=timeout_seconds,
        runner=runner,
    )
    expected_historical_migration_paths = tuple(
        item["path"] for item in expected_historical_migration
    )
    if historical_migration_paths != expected_historical_migration_paths:
        raise GitProvenanceAuthorizationError(
            "historical_migration_evidence does not match the exact approved "
            "historical migration package inventory"
        )
    historical_reconciliation = enumerate_historical_reconciliation_evidence(
        repository_root=root,
        historical_reconciliation_packages=(
            active_profile.historical_reconciliation_packages
        ),
        tracked_operator_runs_paths=tracked_paths,
        git_executable=git_executable,
        timeout_seconds=timeout_seconds,
        runner=runner,
    )
    historical_reconciliation_paths = tuple(
        item["path"] for item in historical_reconciliation
    )
    visible_paths = _visible_untracked_paths(
        root, git_executable=git_executable, timeout_seconds=timeout_seconds, runner=runner
    )
    ignored_paths = _ignored_operator_runs_paths(
        root, git_executable=git_executable, timeout_seconds=timeout_seconds, runner=runner
    )
    inventory_paths = _inventory_operator_runs(root)
    _reconcile_evidence_sets(
        current_manifest_paths=set(current_paths),
        historical_paths=set(historical_paths),
        visible_paths=visible_paths,
        ignored_paths=ignored_paths,
        tracked_paths=tracked_paths,
        inventory_paths=inventory_paths,
        current_package_roots=current_package_roots,
        sidecar_untracked_paths=sidecar_untracked_paths,
        historical_migration_paths=set(historical_migration_paths),
        historical_reconciliation_paths=set(historical_reconciliation_paths),
    )
    allowed_untracked_paths = tuple(
        sorted(
            set(current_paths)
            | set(historical_paths)
            | set(historical_migration_paths)
            | set(historical_reconciliation_paths)
        )
    )
    allowed_file_set_sha256 = compute_allowed_file_set_sha256(
        _allowed_file_digest_records(
            manifest,
            historical_reconciliation_evidence=historical_reconciliation,
        )
    )
    return PreparedGitProvenanceAuthorization(
        allowed_untracked_paths=allowed_untracked_paths,
        authorization_id=authorization_id,
        authorization_sha256=authorization_sha256,
        manifest_sha256=actual_manifest_sha256,
        allowed_file_set_sha256=allowed_file_set_sha256,
        repository_branch=branch,
        repository_head=head,
        file_count=len(allowed_untracked_paths),
        authoritative_database=authoritative_database,
    )


def validate_git_provenance_authorization(
    *,
    repository_root: str | Path,
    manifest_path: str,
    manifest_sha256: str,
    marker_path: str,
    marker_sha256: str,
    profile: GitAuthorizationProfile | None = None,
    git_executable: str = "git",
    timeout_seconds: float = GIT_COMMAND_TIMEOUT_SECONDS,
    runner: Callable[..., Any] = subprocess.run,
    sidecar_untracked_paths: Iterable[str] = (),
) -> ValidatedGitProvenanceAuthorization:
    """Validate an external manifest and marker and return an exact allowlist."""
    active_profile = _resolved_profile(profile)
    prepared = validate_git_provenance_manifest_pre_marker(
        repository_root=repository_root,
        manifest_path=manifest_path,
        manifest_sha256=manifest_sha256,
        profile=active_profile,
        git_executable=git_executable,
        timeout_seconds=timeout_seconds,
        runner=runner,
        sidecar_untracked_paths=sidecar_untracked_paths,
    )
    root = Path(repository_root).resolve()
    marker_file, actual_marker_sha256 = _resolve_external_file(
        marker_path, root=root, expected_sha256=marker_sha256, label="marker"
    )
    marker = _validate_marker(
        marker_file,
        marker_sha256=actual_marker_sha256,
        authorization_id=prepared.authorization_id,
        authorization_sha256=prepared.authorization_sha256,
        manifest_sha256=prepared.manifest_sha256,
        allowed_file_set_sha256=prepared.allowed_file_set_sha256,
        branch=prepared.repository_branch,
        head=prepared.repository_head,
        required_mode=active_profile.command_mode,
    )
    return ValidatedGitProvenanceAuthorization(
        allowed_untracked_paths=prepared.allowed_untracked_paths,
        authorization_id=prepared.authorization_id,
        manifest_sha256=prepared.manifest_sha256,
        marker_sha256=actual_marker_sha256,
        allowed_file_set_sha256=prepared.allowed_file_set_sha256,
        file_count=prepared.file_count,
        authorization_consumed_once=bool(marker.get("authorization_consumed_at")),
        invocation_count=(1 if marker.get("authorization_consumed_at") else 0),
        allowed_invocation_count=int(marker["allowed_invocation_count"]),
        automatic_retry_allowed=bool(marker["automatic_retry_allowed"]),
        manual_rerun_allowed=bool(marker["manual_rerun_allowed"]),
        resume_allowed=bool(marker["resume_allowed"]),
        restart_allowed=bool(marker["restart_allowed"]),
        successor_allowed=bool(marker["successor_allowed"]),
        authoritative_database=dict(prepared.authoritative_database),
    )


__all__ = [
    "APPLICATION_MARKER_SCHEMA_VERSION",
    "AUTHORIZATION_PACKAGE_KIND",
    "AUTHORIZATION_PACKAGE_ROOT",
    "DEFAULT_TERMINAL_DISPOSITION",
    "GitProvenanceAuthorizationError",
    "HISTORICAL_AUTHORIZATION_EVIDENCE_CLASS",
    "HISTORICAL_MIGRATION_EVIDENCE_CLASS",
    "HISTORICAL_MIGRATION_EVIDENCE_KEY",
    "HISTORICAL_MIGRATION_INVENTORY_DOMAIN",
    "HISTORICAL_RECONCILIATION_INVENTORY_DOMAIN",
    "HISTORICAL_MIGRATION_055_EVIDENCE_CLASS",
    "HISTORICAL_MIGRATION_056_EVIDENCE_CLASS",
    "HISTORICAL_MIGRATION_058_EVIDENCE_CLASS",
    "HISTORICAL_MIGRATION_059_EVIDENCE_CLASS",
    "HISTORICAL_MIGRATION_061_EVIDENCE_CLASS",
    "FOUR_TOKEN_CURRENT_MIGRATION_062_EXECUTION_ID",
    "FOUR_TOKEN_CURRENT_MIGRATION_062_EXPECTED_FILE_COUNT",
    "FOUR_TOKEN_CURRENT_MIGRATION_062_EXPECTED_INVENTORY_SHA256",
    "FOUR_TOKEN_HISTORICAL_MIGRATION_EXECUTION_ID",
    "FOUR_TOKEN_HISTORICAL_MIGRATION_055_EXECUTION_ID",
    "FOUR_TOKEN_HISTORICAL_MIGRATION_056_EXECUTION_ID",
    "FOUR_TOKEN_HISTORICAL_MIGRATION_058_EXECUTION_ID",
    "FOUR_TOKEN_HISTORICAL_MIGRATION_059_EXECUTION_ID",
    "FOUR_TOKEN_HISTORICAL_MIGRATION_061_EXECUTION_ID",
    "FOUR_TOKEN_HISTORICAL_MIGRATION_EXPECTED_FILE_COUNT",
    "FOUR_TOKEN_HISTORICAL_MIGRATION_EXPECTED_INVENTORY_SHA256",
    "FOUR_TOKEN_HISTORICAL_MIGRATION_055_EXPECTED_FILE_COUNT",
    "FOUR_TOKEN_HISTORICAL_MIGRATION_055_EXPECTED_INVENTORY_SHA256",
    "FOUR_TOKEN_HISTORICAL_MIGRATION_056_EXPECTED_FILE_COUNT",
    "FOUR_TOKEN_HISTORICAL_MIGRATION_056_EXPECTED_INVENTORY_SHA256",
    "FOUR_TOKEN_HISTORICAL_MIGRATION_058_EXPECTED_FILE_COUNT",
    "FOUR_TOKEN_HISTORICAL_MIGRATION_058_EXPECTED_INVENTORY_SHA256",
    "FOUR_TOKEN_HISTORICAL_MIGRATION_059_EXPECTED_FILE_COUNT",
    "FOUR_TOKEN_HISTORICAL_MIGRATION_059_EXPECTED_INVENTORY_SHA256",
    "FOUR_TOKEN_HISTORICAL_MIGRATION_061_EXPECTED_FILE_COUNT",
    "FOUR_TOKEN_HISTORICAL_MIGRATION_061_EXPECTED_INVENTORY_SHA256",
    "compute_historical_migration_inventory_sha256",
    "compute_historical_reconciliation_inventory_sha256",
    "MANIFEST_SCHEMA_VERSION",
    "MIGRATION_PACKAGE_KIND",
    "MIGRATION_PACKAGE_ROOT",
    "MIGRATION_059_PACKAGE_KIND",
    "MIGRATION_059_PACKAGE_ROOT",
    "MIGRATION_061_PACKAGE_KIND",
    "MIGRATION_061_PACKAGE_ROOT",
    "MIGRATION_062_PACKAGE_KIND",
    "MIGRATION_062_PACKAGE_ROOT",
    "FOUR_TOKEN_PROOF_AUTHORIZATION_PROFILE",
    "FOUR_TOKEN_STANDARD_FOUR_HOUR_AUTHORIZATION_PROFILE",
    "supported_profiles",
    "GitAuthorizationProfile",
    "HistoricalMigrationPackage",
    "HistoricalReconciliationFile",
    "HistoricalReconciliationPackage",
    "ORDINARY_AUTHORIZATION_PROFILE",
    "STANDARD_FOUR_HOUR_AUTHORIZATION_PROFILE",
    "PreparedGitProvenanceAuthorization",
    "TERMINAL_DISPOSITION_VOCABULARY",
    "ValidatedGitProvenanceAuthorization",
    "compute_allowed_file_set_sha256",
    "enumerate_historical_authorization_evidence",
    "enumerate_historical_migration_evidence",
    "enumerate_historical_reconciliation_evidence",
    "expected_manifest_keys",
    "extract_approved_historical_authorization_ids",
    "require_safe_authorization_id",
    "validate_git_provenance_authorization",
    "validate_git_provenance_manifest_pre_marker",
    "validate_prior_authorizations_non_reusable",
]
