"""Canonical non-consuming preparation for four-token Standard-4H authority.

This owner creates one immutable final-authorization package only after the
explicit inputs agree with live local Git, the bound database file, and the
profile-owned Migration-062 and historical-non-reuse declarations. It neither
creates application artifacts nor launches any runtime.
"""

from __future__ import annotations

from datetime import datetime, timedelta
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import stat
import subprocess
import tempfile
from types import MappingProxyType
from typing import Any, Mapping, Sequence

from printer_v1.operator_cli import git_provenance_authorization_manifest as git_auth
from printer_v1.operator_cli.four_token_standard_four_hour_one_shot_wrapper import (
    APPLICATION_ROOT,
    FINAL_AUTHORIZATION_SCHEMA_VERSION,
    _authorization_document,
    _canonical_json_bytes,
    _fsync_directory,
    _make_read_only,
    _sha256_file,
    _write_exclusive,
    build_manifest_bytes,
    exact_operational_policy,
    validate_four_token_standard_four_hour_authorization_document,
)
from printer_v1.operator_cli.window_15m_authorization_preparation import (
    _validate_created_temp_dir,
    _validate_temp_parent,
)


FOUR_TOKEN_STANDARD_FOUR_HOUR_AUTHORIZATION_PROFILE = (
    git_auth.FOUR_TOKEN_STANDARD_FOUR_HOUR_AUTHORIZATION_PROFILE
)
_AUTHORIZATION_ID = re.compile(
    r"^V2_9_8B_FOUR_TOKEN_STD4H_AUTH_\d{8}T\d{6}Z_[0-9a-f]{8}$"
)
_DATABASE_KEYS = frozenset(
    {
        "path",
        "sha256",
        "size",
        "inode",
        "mtime_ns",
        "migration_count",
        "migration_head",
    }
)


class FourTokenAuthorizationPreparationError(RuntimeError):
    """Fail-closed four-token authorization-preparation fault."""


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise FourTokenAuthorizationPreparationError(message)


def _canonical_repository_child(root: Path, relative: str) -> Path:
    """Resolve a profile-owned relative path without accepting symlink aliases."""
    parts = PurePosixPath(relative).parts
    _require(
        bool(parts) and not PurePosixPath(relative).is_absolute() and ".." not in parts,
        "profile package root is malformed",
    )
    current = root
    for part in parts:
        current = current / part
        _require(not os.path.islink(current), "profile package path contains a symlink")
    resolved = current.resolve()
    try:
        resolved.relative_to(root)
    except ValueError as exc:
        raise FourTokenAuthorizationPreparationError(
            "profile package path escaped repository"
        ) from exc
    return current


def _validate_authorization_id(value: Any) -> str:
    try:
        authorization_id = git_auth.require_safe_authorization_id(
            value, label="authorization_id"
        )
    except git_auth.GitProvenanceAuthorizationError as exc:
        raise FourTokenAuthorizationPreparationError(str(exc)) from exc
    _require(
        _AUTHORIZATION_ID.fullmatch(authorization_id) is not None,
        "authorization_id does not use the canonical four-token Standard-4H form",
    )
    return authorization_id


def _validate_database_binding(raw: Mapping[str, Any]) -> dict[str, Any]:
    """Require a supplied DB binding to match one stable local file identity."""
    _require(isinstance(raw, Mapping) and set(raw) == _DATABASE_KEYS, "authoritative database keys are malformed")
    path_value = raw.get("path")
    _require(type(path_value) is str and bool(path_value), "database path is malformed")
    path = Path(path_value)
    _require(path.is_absolute(), "database path must be absolute")
    walked = path
    while True:
        _require(
            not os.path.islink(walked), "database path must not contain a symlink"
        )
        if walked.parent == walked:
            break
        walked = walked.parent
    _require(path.is_file(), "authoritative database file is unavailable")
    before = path.stat()
    actual_sha256 = _sha256_file(path)
    after = path.stat()
    _require(
        (before.st_size, before.st_ino, before.st_mtime_ns)
        == (after.st_size, after.st_ino, after.st_mtime_ns),
        "authoritative database changed while its identity was inspected",
    )
    _require(raw.get("sha256") == actual_sha256, "authoritative database SHA-256 mismatch")
    for key, actual in (
        ("size", before.st_size),
        ("inode", before.st_ino),
        ("mtime_ns", before.st_mtime_ns),
    ):
        _require(type(raw.get(key)) is int and raw[key] == actual, f"authoritative database {key} mismatch")
    _require(
        type(raw.get("migration_count")) is int and raw["migration_count"] >= 0,
        "authoritative database migration_count is malformed",
    )
    _require(
        type(raw.get("migration_head")) is str and bool(raw["migration_head"]),
        "authoritative database migration_head is malformed",
    )
    return {
        "path": str(path.resolve()),
        "sha256": actual_sha256,
        "size": before.st_size,
        "inode": before.st_ino,
        "mtime_ns": before.st_mtime_ns,
        "migration_count": raw["migration_count"],
        "migration_head": raw["migration_head"],
    }


def _seal_prepared_package(*, authorization_file: Path, package_dir: Path) -> None:
    """Require read-only authorization bytes and a non-writable package directory."""
    _make_read_only(authorization_file)
    try:
        file_mode = stat.S_IMODE(authorization_file.stat().st_mode)
        _require(file_mode & 0o222 == 0, "final authorization remained writable")
        package_dir.chmod(0o555)
        package_mode = stat.S_IMODE(package_dir.stat().st_mode)
        _require(package_mode & 0o222 == 0, "authorization package remained writable")
        _fsync_directory(package_dir)
        _fsync_directory(package_dir.parent)
    except OSError as exc:
        raise FourTokenAuthorizationPreparationError(
            f"final authorization sealing failed: {exc}"
        ) from exc


def _remove_unpublished_package(package_dir: Path) -> None:
    """Remove only the just-created package after preparation fails closed."""
    authorization_file = package_dir / "final_authorization.json"
    try:
        _require(
            not package_dir.is_symlink(),
            "unpublished authorization cleanup found a symlinked package",
        )
        if authorization_file.exists() or authorization_file.is_symlink():
            _require(
                authorization_file.is_file() and not authorization_file.is_symlink(),
                "unpublished authorization cleanup found an unsafe file",
            )
            authorization_file.chmod(0o600)
            package_dir.chmod(0o700)
            authorization_file.unlink()
        else:
            package_dir.chmod(0o700)
        package_dir.rmdir()
        _fsync_directory(package_dir.parent)
    except (OSError, RuntimeError) as exc:
        raise FourTokenAuthorizationPreparationError(
            f"unpublished authorization cleanup failed: {exc}"
        ) from exc


def _validate_profile_migration(
    *, root: Path, migration_execution_id: str
) -> None:
    profile = FOUR_TOKEN_STANDARD_FOUR_HOUR_AUTHORIZATION_PROFILE
    try:
        identity = git_auth._validated_current_migration_identity(profile)
        _require(identity is not None, "four-token profile has no current migration identity")
        _require(
            migration_execution_id == identity[0],
            "migration execution ID does not match the exact four-token profile identity",
        )
        git_auth._validate_current_migration_package_identity(
            root=root, profile=profile, identity=identity
        )
        git_auth.enumerate_historical_migration_evidence(
            repository_root=root,
            historical_migration_packages=profile.historical_migration_packages,
        )
    except git_auth.GitProvenanceAuthorizationError as exc:
        raise FourTokenAuthorizationPreparationError(str(exc)) from exc


def _validate_prior_inventory(
    *, root: Path, authorization_id: str, prior_authorizations_non_reusable: Sequence[str]
) -> tuple[str, ...]:
    profile = FOUR_TOKEN_STANDARD_FOUR_HOUR_AUTHORIZATION_PROFILE
    try:
        prior = git_auth.validate_prior_authorizations_non_reusable(
            list(prior_authorizations_non_reusable),
            current_authorization_id=authorization_id,
        )
        git_auth.enumerate_historical_authorization_evidence(
            repository_root=root,
            current_authorization_id=authorization_id,
            approved_historical_authorization_ids=prior,
            authorization_package_roots=profile.historical_authorization_package_roots,
            current_authorization_package_root=profile.authorization_package_root,
        )
        return prior
    except git_auth.GitProvenanceAuthorizationError as exc:
        raise FourTokenAuthorizationPreparationError(str(exc)) from exc


def _pre_marker_parity(
    *,
    root: Path,
    authorization_file: Path,
    authorization_sha256: str,
    created_at: str,
    application_root: str | Path | None,
    temporary_parent: str | Path | None,
) -> dict[str, Any]:
    """Run the exact four-token manifest/pre-marker validator without a marker."""
    app_root = Path(application_root or APPLICATION_ROOT).expanduser().resolve()
    proposed_parent = temporary_parent or Path(tempfile.gettempdir())
    try:
        parent = _validate_temp_parent(
            temporary_parent=proposed_parent,
            repository_root=root,
            application_root=app_root,
        )
        temporary_root = Path(
            tempfile.mkdtemp(prefix="printer-v1-four-token-prep-", dir=str(parent))
        )
        temporary_root = _validate_created_temp_dir(
            temporary_root,
            repository_root=root,
            application_root=app_root,
            temporary_parent=parent,
        )
    except Exception as exc:
        raise FourTokenAuthorizationPreparationError(
            f"pre-marker temporary manifest preparation blocked: {exc}"
        ) from exc

    manifest_path = temporary_root / "git-provenance-manifest.json"
    try:
        _, manifest_bytes = build_manifest_bytes(
            repository_root=root,
            authorization_file=authorization_file,
            authorization_sha256=authorization_sha256,
            created_at=created_at,
        )
        _write_exclusive(manifest_path, manifest_bytes)
        manifest_sha256 = hashlib.sha256(manifest_bytes).hexdigest()
        prepared = git_auth.validate_git_provenance_manifest_pre_marker(
            repository_root=root,
            manifest_path=str(manifest_path),
            manifest_sha256=manifest_sha256,
            profile=FOUR_TOKEN_STANDARD_FOUR_HOUR_AUTHORIZATION_PROFILE,
        )
        return {
            "inventory_pre_marker_parity_PASS": True,
            "manifest_sha256": prepared.manifest_sha256,
            "allowed_file_set_sha256": prepared.allowed_file_set_sha256,
            "file_count": prepared.file_count,
        }
    except (git_auth.GitProvenanceAuthorizationError, RuntimeError) as exc:
        raise FourTokenAuthorizationPreparationError(
            f"inventory pre-marker parity blocked: {exc}"
        ) from exc
    finally:
        try:
            if manifest_path.is_file() and not manifest_path.is_symlink():
                manifest_path.unlink()
            temporary_root.rmdir()
        except OSError:
            pass


def prepare_four_token_standard_four_hour_authorization(
    *,
    repository_root: str | Path,
    branch: str,
    head: str,
    authoritative_database: Mapping[str, Any],
    migration_execution_id: str,
    prior_authorizations_non_reusable: Sequence[str],
    authorization_id: str,
    authorized_at: str,
    validity_seconds: int,
    operator_approved: bool,
    application_root: str | Path | None = None,
    temporary_parent: str | Path | None = None,
) -> Mapping[str, Any]:
    """Create one final authorization package and prove non-consuming parity.

    The caller supplies already-verified bindings. This function refuses any
    disagreement with live Git and the supplied database file, derives policy
    exclusively from the operational facade, and never creates application or
    process artifacts.
    """
    _require(operator_approved is True, "explicit preparation approval is required")
    root = Path(repository_root).resolve()
    _require(root.is_dir(), "repository root is unavailable")
    try:
        live_branch, live_head = git_auth._live_repository_identity(
            root,
            git_executable="git",
            timeout_seconds=git_auth.GIT_COMMAND_TIMEOUT_SECONDS,
            runner=subprocess.run,
        )
    except git_auth.GitProvenanceAuthorizationError as exc:
        raise FourTokenAuthorizationPreparationError(str(exc)) from exc
    _require(branch == live_branch, "branch does not match live Git state")
    _require(head == live_head, "HEAD does not match live Git state")
    _require(type(authorized_at) is str and bool(authorized_at), "authorized_at is malformed")
    _require(
        type(validity_seconds) is int and validity_seconds > 0,
        "validity_seconds is malformed",
    )
    authorization_id = _validate_authorization_id(authorization_id)
    database = _validate_database_binding(authoritative_database)
    _validate_profile_migration(root=root, migration_execution_id=migration_execution_id)
    prior = _validate_prior_inventory(
        root=root,
        authorization_id=authorization_id,
        prior_authorizations_non_reusable=prior_authorizations_non_reusable,
    )

    try:
        issued = datetime.fromisoformat(authorized_at)
    except ValueError as exc:
        raise FourTokenAuthorizationPreparationError("authorized_at is malformed") from exc
    _require(issued.tzinfo is not None, "authorized_at must be timezone-aware")
    expires_at = (issued + timedelta(seconds=validity_seconds)).isoformat()
    document = _authorization_document(
        branch=branch,
        head=head,
        database=database,
        authorization_id=authorization_id,
        migration_execution_id=migration_execution_id,
        verdict="V2_9_8B_FOUR_TOKEN_STANDARD_4H_FINAL_AUTHORIZATION_PASS",
        authorized_at=authorized_at,
        expires_at=expires_at,
        validity_seconds=validity_seconds,
        prior_authorizations_non_reusable=prior,
    )
    try:
        validated = validate_four_token_standard_four_hour_authorization_document(document)
    except RuntimeError as exc:
        raise FourTokenAuthorizationPreparationError(str(exc)) from exc
    _require(
        validated["operational_policy"] == exact_operational_policy(),
        "derived operational policy did not survive document validation",
    )

    package_parent = _canonical_repository_child(
        root, FOUR_TOKEN_STANDARD_FOUR_HOUR_AUTHORIZATION_PROFILE.authorization_package_root
    )
    if not package_parent.exists():
        package_parent.mkdir(parents=True, exist_ok=False)
        _fsync_directory(package_parent.parent)
    _require(package_parent.is_dir(), "authorization package root is unavailable")
    package_dir = package_parent / authorization_id
    _require(not package_dir.exists(), "current authorization package already exists")
    try:
        package_dir.mkdir(mode=0o700, exist_ok=False)
    except FileExistsError as exc:
        raise FourTokenAuthorizationPreparationError(
            "current authorization package already exists"
        ) from exc
    _fsync_directory(package_parent)
    authorization_file = package_dir / "final_authorization.json"
    try:
        _require(
            _validate_database_binding(authoritative_database) == database,
            "authoritative database identity changed before publication",
        )
        authorization_bytes = _canonical_json_bytes(validated)
        _write_exclusive(authorization_file, authorization_bytes)
        _seal_prepared_package(
            authorization_file=authorization_file, package_dir=package_dir
        )
        authorization_sha256 = hashlib.sha256(authorization_bytes).hexdigest()
        _require(
            _sha256_file(authorization_file) == authorization_sha256,
            "published authorization SHA-256 mismatch",
        )
        just_written = validate_four_token_standard_four_hour_authorization_document(
            json.loads(authorization_file.read_text(encoding="utf-8"))
        )
        _require(just_written == validated, "published authorization bytes changed")
        parity = _pre_marker_parity(
            root=root,
            authorization_file=authorization_file,
            authorization_sha256=authorization_sha256,
            created_at=authorized_at,
            application_root=application_root,
            temporary_parent=temporary_parent,
        )
    except Exception as original:
        try:
            _remove_unpublished_package(package_dir)
        except FourTokenAuthorizationPreparationError as cleanup:
            raise FourTokenAuthorizationPreparationError(
                f"authorization preparation failed ({original}); cleanup blocked ({cleanup})"
            ) from original
        if isinstance(original, FourTokenAuthorizationPreparationError):
            raise
        raise FourTokenAuthorizationPreparationError(
            f"published authorization validation failed: {original}"
        ) from original
    return MappingProxyType(
        {
            "authorization_id": authorization_id,
            "authorization_file": str(authorization_file),
            "authorization_sha256": authorization_sha256,
            "schema_version": FINAL_AUTHORIZATION_SCHEMA_VERSION,
            "repository_branch": branch,
            "repository_head": head,
            "authoritative_database": MappingProxyType(database),
            "migration_execution_id": migration_execution_id,
            "authorized_at": authorized_at,
            "expires_at": expires_at,
            "validity_seconds": validity_seconds,
            "prior_non_reusable_count": len(prior),
            "marker_created": False,
            "consumed": False,
            "application_created": False,
            "child_launched": False,
            **parity,
        }
    )


__all__ = [
    "FourTokenAuthorizationPreparationError",
    "prepare_four_token_standard_four_hour_authorization",
]
