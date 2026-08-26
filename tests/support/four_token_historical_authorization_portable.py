from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
import hashlib
import json
from pathlib import Path
import tempfile

from printer_v1.operator_cli.git_provenance_authorization_manifest import (
    APPLICATION_MARKER_SCHEMA_VERSION,
)
from printer_v1.operator_cli.window_15m_child_terminal import (
    ChildTerminalBinding,
    write_child_terminal_envelope,
)

AUTHORIZATION_ROOT = (
    "operator-runs/v2-9-8b-four-token-standard-four-hour-final-authorization"
)
MODE = "four-token-standard-four-hour-run"


def _canonical_bytes(payload: dict) -> bytes:
    return (json.dumps(payload, indent=2, sort_keys=True) + "\n").encode("utf-8")


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


@dataclass
class PortableFourTokenHistory:
    temp: tempfile.TemporaryDirectory
    root: Path
    applications: Path
    authorization_path: Path
    authorization_bytes: bytes
    authorization_document: dict
    authorization_sha256: str
    authorization_size: int
    marker_path: Path | None = None
    manifest_path: Path | None = None
    child_terminal_path: Path | None = None
    wrapper_terminal_path: Path | None = None
    marker: dict | None = None
    child_terminal: dict | None = None
    wrapper_terminal: dict | None = None
    marker_sha256: str | None = None
    child_terminal_sha256: str | None = None
    wrapper_terminal_sha256: str | None = None

    def close(self) -> None:
        self.temp.cleanup()


def build_portable_four_token_history(
    *,
    target_id: str,
    prior_ids: list[str] | tuple[str, ...],
    package_ids: list[str] | tuple[str, ...] | None = None,
    application_consumed_ids: list[str] | tuple[str, ...] = (),
    target_consumed: bool = False,
    bound_head: str = "f" * 40,
    authorized_at: str = "2026-08-24T12:00:00+00:00",
    validity_seconds: int = 43_200,
) -> PortableFourTokenHistory:
    temp = tempfile.TemporaryDirectory()
    root = Path(temp.name).resolve()
    applications = root / "applications"
    applications.mkdir(parents=True)
    auth_root = root / AUTHORIZATION_ROOT
    auth_root.mkdir(parents=True)

    prior = sorted(set(str(item) for item in prior_ids))
    issued = datetime.fromisoformat(authorized_at)
    if issued.tzinfo is None:
        issued = issued.replace(tzinfo=timezone.utc)
    target_document = {
        "authorization_id": target_id,
        "authorized_at": issued.isoformat(),
        "expires_at": (issued + timedelta(seconds=validity_seconds)).isoformat(),
        "validity_seconds": validity_seconds,
        "repository": {"branch": "portable-history-fixture", "head": bound_head},
        "authorized_git": {"branch": "portable-history-fixture", "head": bound_head},
        "authorized_command": {"mode": MODE, "operator_approved": True},
        "one_shot_policy": {
            "allowed_invocation_count": 1,
            "automatic_retry_allowed": False,
            "manual_rerun_allowed": False,
            "resume_allowed": False,
            "restart_allowed": False,
            "successor_allowed": False,
        },
        "prior_authorizations_non_reusable": prior,
        "fixture_role": "PORTABLE_HISTORICAL_POLICY_PROOF_ONLY",
    }
    target_dir = auth_root / target_id
    target_dir.mkdir()
    authorization_path = target_dir / "final_authorization.json"
    authorization_path.write_bytes(_canonical_bytes(target_document))
    authorization_path.chmod(0o444)

    packages = list(package_ids or prior)
    if target_id not in packages:
        packages.append(target_id)
    for index, package_id in enumerate(sorted(set(packages))):
        if package_id == target_id:
            continue
        package_dir = auth_root / package_id
        package_dir.mkdir(parents=True, exist_ok=True)
        payload = {
            "authorization_id": package_id,
            "historical": True,
            "fixture_padding": "x" * (index + 1),
        }
        package = package_dir / "final_authorization.json"
        package.write_bytes(_canonical_bytes(payload))
        package.chmod(0o444)

    for consumed_id in application_consumed_ids:
        (applications / consumed_id).mkdir(parents=True, exist_ok=True)

    result = PortableFourTokenHistory(
        temp=temp,
        root=root,
        applications=applications,
        authorization_path=authorization_path,
        authorization_bytes=authorization_path.read_bytes(),
        authorization_document=target_document,
        authorization_sha256=_sha(authorization_path),
        authorization_size=authorization_path.stat().st_size,
    )

    if target_consumed:
        app = applications / target_id
        app.mkdir(parents=True, exist_ok=True)
        manifest_path = app / "git-provenance-manifest.json"
        manifest_path.write_bytes(
            _canonical_bytes({"authorization_id": target_id, "fixture": True})
        )
        manifest_path.chmod(0o444)
        manifest_sha = _sha(manifest_path)
        consumed_at = (issued + timedelta(hours=1)).isoformat()
        marker = {
            "schema_version": APPLICATION_MARKER_SCHEMA_VERSION,
            "authorization_id": target_id,
            "authorization_consumed_at": consumed_at,
            "authorization_sha256": result.authorization_sha256,
            "manifest_sha256": manifest_sha,
            "allowed_file_set_sha256": "a" * 64,
            "repository_branch": "portable-history-fixture",
            "repository_head": bound_head,
            "command": {"mode": MODE, "operator_approved": True},
            "allowed_invocation_count": 1,
            "automatic_retry_allowed": False,
            "manual_rerun_allowed": False,
            "resume_allowed": False,
            "restart_allowed": False,
            "successor_allowed": False,
        }
        marker_path = app / "application-marker.json"
        marker_path.write_bytes(_canonical_bytes(marker))
        marker_path.chmod(0o444)
        marker_sha = _sha(marker_path)
        child_path = app / "child-terminal.json"
        binding = ChildTerminalBinding(
            terminal_path=child_path,
            marker_path=marker_path,
            authorization_id=target_id,
            marker_sha256=marker_sha,
        )
        child = write_child_terminal_envelope(
            binding=binding,
            source={
                "status": "OPERATIONAL_COMMAND_BLOCKED",
                "error_type": "RuntimeError",
                "error_message": "portable historical fixture",
                "lifecycle_started": True,
                "cleanup_complete": True,
                "lease_released": True,
                "source_calls": 1,
                "scheduler_runtime_calls": 0,
                "database_writes": 1,
            },
            mode=MODE,
            exit_code=1,
            success=False,
        )
        wrapper = {
            "authorization_id": target_id,
            "terminal_classification": "CHILD_EXITED_NONZERO",
            "child_exit_code": 1,
        }
        wrapper_path = app / "wrapper-terminal.json"
        wrapper_path.write_bytes(_canonical_bytes(wrapper))
        wrapper_path.chmod(0o444)
        result.marker_path = marker_path
        result.manifest_path = manifest_path
        result.child_terminal_path = child_path
        result.wrapper_terminal_path = wrapper_path
        result.marker = marker
        result.child_terminal = child
        result.wrapper_terminal = wrapper
        result.marker_sha256 = marker_sha
        result.child_terminal_sha256 = _sha(child_path)
        result.wrapper_terminal_sha256 = _sha(wrapper_path)

    return result
