"""Non-consuming WINDOW_15M Git-provenance authorization preparation parity.

Runs the exact production manifest builder and pre-marker validator so a
preparation PASS cannot coexist with an immediate wrapper pre-marker inventory
rejection. Creates no application marker, no canonical application directory,
no child process, no provider contact, no DB mutation, and no Git mutation.

Honest scope:

```text
inventory_pre_marker_parity_PASS
does not by itself equal full_apply_readiness_PASS
```
"""

from __future__ import annotations

import hashlib
import os
import subprocess
import tempfile
from pathlib import Path
from typing import Any

from printer_v1.operator_cli.git_provenance_authorization_manifest import (
    GIT_COMMAND_TIMEOUT_SECONDS,
    GitProvenanceAuthorizationError,
    _inventory_operator_runs,
    _tracked_operator_runs_paths,
    enumerate_historical_authorization_evidence,
    extract_approved_historical_authorization_ids,
    validate_git_provenance_manifest_pre_marker,
)
from printer_v1.operator_cli.window_15m_one_shot_wrapper import (
    APPLICATION_ROOT,
    OneShotWrapperError,
    _resolve_authorization,
    build_manifest_bytes,
)


class AuthorizationPreparationError(RuntimeError):
    """Fail-closed non-consuming preparation parity error."""


def _path_is_or_inside(candidate: Path, boundary: Path) -> bool:
    """Return True when candidate is boundary or a strict descendant."""
    if candidate == boundary:
        return True
    try:
        return candidate.is_relative_to(boundary)
    except (ValueError, AttributeError):
        return False


def _validate_temp_parent(
    *,
    temporary_parent: str | Path,
    repository_root: Path,
    application_root: Path,
) -> Path:
    """Resolve and validate the temporary parent before any directory creation.

    Blocks when the parent is unavailable, a symlink, inside the repository, or
    inside the application root.
    """
    raw = Path(os.path.expanduser(os.fspath(temporary_parent)))
    if os.path.islink(raw):
        raise AuthorizationPreparationError(
            "temporary preparation parent must not be a symlink"
        )
    if not raw.exists() or not raw.is_dir():
        raise AuthorizationPreparationError(
            "temporary preparation parent is unavailable"
        )
    # Reject symlink ancestors that would launder placement under a boundary.
    walked = raw
    for _ in range(len(raw.parts) + 2):
        if os.path.islink(walked):
            raise AuthorizationPreparationError(
                "temporary preparation parent path contains a symlink component"
            )
        if walked.parent == walked:
            break
        walked = walked.parent

    resolved = raw.resolve()
    if os.path.islink(resolved):
        raise AuthorizationPreparationError(
            "temporary preparation parent must not be a symlink"
        )
    if not resolved.is_dir():
        raise AuthorizationPreparationError(
            "temporary preparation parent is unavailable"
        )
    if _path_is_or_inside(resolved, repository_root):
        raise AuthorizationPreparationError(
            "temporary preparation parent must live outside the repository"
        )
    if _path_is_or_inside(resolved, application_root):
        raise AuthorizationPreparationError(
            "temporary preparation parent must live outside APPLICATION_ROOT"
        )
    return resolved


def _validate_created_temp_dir(
    created: Path,
    *,
    repository_root: Path,
    application_root: Path,
    temporary_parent: Path,
) -> Path:
    """Revalidate the created temporary directory before any write."""
    if os.path.islink(created):
        raise AuthorizationPreparationError(
            "temporary preparation directory must not be a symlink"
        )
    if not created.is_dir():
        raise AuthorizationPreparationError(
            "temporary preparation directory is unavailable"
        )
    resolved = created.resolve()
    if not _path_is_or_inside(resolved, temporary_parent):
        raise AuthorizationPreparationError(
            "temporary preparation directory escaped its validated parent"
        )
    if _path_is_or_inside(resolved, repository_root):
        raise AuthorizationPreparationError(
            "temporary preparation directory must live outside the repository"
        )
    if _path_is_or_inside(resolved, application_root):
        raise AuthorizationPreparationError(
            "temporary preparation directory must live outside APPLICATION_ROOT"
        )
    return resolved


def prepare_git_provenance_authorization_parity(
    *,
    repository_root: str | Path,
    authorization_file: str | Path,
    authorization_sha256: str,
    created_at: str | None = None,
    application_root: str | Path | None = None,
    temporary_parent: str | Path | None = None,
) -> dict[str, Any]:
    """Build and pre-marker-validate using exact production functions only.

    Temporary manifest bytes are written only beneath a validated temporary
    parent that is outside the repository and outside APPLICATION_ROOT. The
    temporary directory is removed in ``finally``.
    """
    root = Path(repository_root).resolve()
    if not root.is_dir():
        raise AuthorizationPreparationError("repository root is unavailable")

    # Canonical application-root identity for containment. The directory need
    # not exist yet; only its resolved path identity is used to refuse temp
    # placement under APPLICATION_ROOT.
    app_root = Path(
        os.path.expanduser(os.fspath(application_root or APPLICATION_ROOT))
    ).resolve()
    if _path_is_or_inside(app_root, root):
        raise AuthorizationPreparationError(
            "application root must live outside the repository"
        )

    try:
        authorization_path, document, authorization_id, _migration_id = (
            _resolve_authorization(
                repository_root=root,
                authorization_file=authorization_file,
                authorization_sha256=authorization_sha256,
            )
        )
    except OneShotWrapperError as exc:
        raise AuthorizationPreparationError(str(exc)) from exc

    try:
        approved_historical_ids = extract_approved_historical_authorization_ids(
            document, current_authorization_id=authorization_id
        )
    except GitProvenanceAuthorizationError as exc:
        raise AuthorizationPreparationError(str(exc)) from exc

    temp_dir: str | None = None
    try:
        try:
            payload, manifest_bytes = build_manifest_bytes(
                repository_root=root,
                authorization_file=authorization_file,
                authorization_sha256=authorization_sha256,
                created_at=created_at,
            )
        except (OneShotWrapperError, GitProvenanceAuthorizationError) as exc:
            raise AuthorizationPreparationError(
                f"manifest construction blocked: {exc}"
            ) from exc

        proposed_parent = (
            temporary_parent
            if temporary_parent is not None
            else Path(tempfile.gettempdir())
        )
        validated_parent = _validate_temp_parent(
            temporary_parent=proposed_parent,
            repository_root=root,
            application_root=app_root,
        )
        # Create only after the parent has been proven safe.
        temp_dir = tempfile.mkdtemp(
            prefix="printer-v1-window15m-prep-",
            dir=str(validated_parent),
        )
        temp_root = _validate_created_temp_dir(
            Path(temp_dir),
            repository_root=root,
            application_root=app_root,
            temporary_parent=validated_parent,
        )

        manifest_path = temp_root / "git-provenance-manifest.json"
        with manifest_path.open("xb") as handle:
            handle.write(manifest_bytes)
            handle.flush()
            os.fsync(handle.fileno())
        manifest_sha256 = hashlib.sha256(manifest_bytes).hexdigest()

        try:
            prepared = validate_git_provenance_manifest_pre_marker(
                repository_root=root,
                manifest_path=str(manifest_path.resolve()),
                manifest_sha256=manifest_sha256,
            )
        except GitProvenanceAuthorizationError as exc:
            raise AuthorizationPreparationError(
                f"inventory_pre_marker_parity_BLOCKED: {exc}"
            ) from exc

        historical_count = len(payload.get("historical_authorization_evidence") or [])
        current_count = len(payload.get("files") or [])
        tracked = _tracked_operator_runs_paths(
            root,
            git_executable="git",
            timeout_seconds=GIT_COMMAND_TIMEOUT_SECONDS,
            runner=subprocess.run,
        )
        inventory = _inventory_operator_runs(root)
        owner_rows = enumerate_historical_authorization_evidence(
            repository_root=root,
            current_authorization_id=authorization_id,
            approved_historical_authorization_ids=approved_historical_ids,
            tracked_operator_runs_paths=tracked,
        )
        if len(owner_rows) != historical_count:
            raise AuthorizationPreparationError(
                "historical evidence owner count disagrees with built manifest"
            )

        branch = str(document["authorized_git"]["branch"])
        head = str(document["authorized_git"]["head"])
        return {
            "authorization_id": authorization_id,
            "branch": branch,
            "head": head,
            "status": "inventory_pre_marker_parity_PASS",
            "inventory_pre_marker_parity_PASS": True,
            "full_apply_readiness_PASS": False,
            "does_not_by_itself_equal_full_apply_readiness_PASS": True,
            "tracked_historical_count": len(tracked),
            "current_manifest_count": current_count,
            "historical_authorization_count": historical_count,
            "complete_inventory_count": len(inventory),
            "allowed_untracked_count": prepared.file_count,
            "approved_historical_authorization_id_count": len(approved_historical_ids),
            "manifest_sha256": prepared.manifest_sha256,
            "allowed_file_set_sha256": prepared.allowed_file_set_sha256,
            "file_count": prepared.file_count,
            "marker_created": False,
            "canonical_application_directory_created": False,
            "child_launched": False,
        }
    finally:
        if temp_dir is not None:
            # Exact-path cleanup of the disposable temp directory only. Delete
            # known regular files then rmdir; never shutil.rmtree.
            try:
                for name in os.listdir(temp_dir):
                    path = os.path.join(temp_dir, name)
                    if os.path.islink(path):
                        continue
                    if os.path.isfile(path):
                        try:
                            os.unlink(path)
                        except OSError:
                            pass
                try:
                    os.rmdir(temp_dir)
                except OSError:
                    pass
            except OSError:
                pass


__all__ = [
    "AuthorizationPreparationError",
    "prepare_git_provenance_authorization_parity",
]
