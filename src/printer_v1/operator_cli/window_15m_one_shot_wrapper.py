"""One-shot application owner for one authorized ordinary WINDOW_15M run.

This module constructs and validates external Git-provenance artifacts, consumes
one final authorization with a create-once marker, and launches exactly one
existing operational-command child. It owns no provider, Scheduler, campaign,
database, memory, retrieval, or paper-trading behavior.
"""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import stat
import subprocess
import sys
from typing import Any, Callable, Mapping
import uuid

from printer_v1.operator_cli.git_provenance_authorization_manifest import (
    APPLICATION_MARKER_SCHEMA_VERSION,
    AUTHORIZATION_PACKAGE_KIND,
    AUTHORIZATION_PACKAGE_ROOT,
    GIT_COMMAND_TIMEOUT_SECONDS,
    MANIFEST_SCHEMA_VERSION,
    MIGRATION_PACKAGE_KIND,
    MIGRATION_PACKAGE_ROOT,
    PreparedGitProvenanceAuthorization,
    ValidatedGitProvenanceAuthorization,
    compute_allowed_file_set_sha256,
    validate_git_provenance_authorization,
    validate_git_provenance_manifest_pre_marker,
)


WRAPPER_SCHEMA_VERSION = "PRINTER_V1_WINDOW_15M_ONE_SHOT_WRAPPER_V1"
APPLICATION_ROOT = (
    Path.home()
    / "PrinterOperations"
    / "v2-9-8"
    / "window-15m-one-shot-applications"
)
BINDING_ENV_VARS = (
    "PRINTER_V1_GIT_PROVENANCE_MANIFEST_PATH",
    "PRINTER_V1_GIT_PROVENANCE_MANIFEST_SHA256",
    "PRINTER_V1_APPLICATION_MARKER_PATH",
    "PRINTER_V1_APPLICATION_MARKER_SHA256",
)
_SHA256 = re.compile(r"^[0-9a-f]{64}$")
_HEAD = re.compile(r"^[0-9a-f]{40}$")
_SAFE_ID = re.compile(r"^[A-Za-z0-9_.-]+$")


class OneShotWrapperError(RuntimeError):
    """Fail-closed one-shot wrapper fault."""


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _no_duplicate_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise OneShotWrapperError(f"duplicate JSON key: {key!r}")
        result[key] = value
    return result


def _load_json_object(path: Path, *, label: str) -> dict[str, Any]:
    try:
        value = json.loads(
            path.read_text(encoding="utf-8"),
            object_pairs_hook=_no_duplicate_keys,
        )
    except (OSError, ValueError, UnicodeError) as exc:
        raise OneShotWrapperError(f"{label} is unreadable or malformed: {exc}") from exc
    if not isinstance(value, dict):
        raise OneShotWrapperError(f"{label} must be a JSON object")
    return value


def _canonical_json_bytes(value: Mapping[str, Any]) -> bytes:
    return (
        json.dumps(
            dict(value),
            indent=2,
            sort_keys=True,
            ensure_ascii=True,
            allow_nan=False,
        )
        + "\n"
    ).encode("utf-8")


def _repository_root() -> Path:
    return Path(__file__).resolve().parents[3]


def _safe_identifier(value: Any, *, label: str) -> str:
    if type(value) is not str or not value or _SAFE_ID.fullmatch(value) is None:
        raise OneShotWrapperError(f"{label} is malformed")
    return value


def _exact_sha256(value: Any, *, label: str) -> str:
    if type(value) is not str or _SHA256.fullmatch(value) is None:
        raise OneShotWrapperError(f"{label} must be lowercase SHA-256")
    return value


def _resolve_authorization(
    *,
    repository_root: Path,
    authorization_file: str | Path,
    authorization_sha256: str,
) -> tuple[Path, dict[str, Any], str, str]:
    expected_hash = _exact_sha256(
        authorization_sha256, label="authorization SHA-256"
    )
    candidate = Path(authorization_file)
    if not candidate.is_absolute():
        candidate = repository_root / candidate

    # macOS exposes the temporary directory through both /var and /private/var.
    # Compare canonical identities, but preserve the supplied lexical path so
    # symlinks introduced *inside* the repository remain detectable.
    lexical_candidate = Path(os.path.abspath(candidate))
    canonical_root = Path(os.path.realpath(repository_root))
    canonical_candidate = Path(os.path.realpath(lexical_candidate))
    try:
        relative = canonical_candidate.relative_to(canonical_root).as_posix()
    except ValueError as exc:
        raise OneShotWrapperError(
            "authorization file must be inside the repository"
        ) from exc

    lexical_root = None
    for ancestor in lexical_candidate.parents:
        if Path(os.path.realpath(ancestor)) == canonical_root:
            lexical_root = ancestor
            break
    if lexical_root is None:
        raise OneShotWrapperError(
            "authorization file repository boundary could not be established"
        )
    try:
        lexical_relative = lexical_candidate.relative_to(lexical_root).as_posix()
    except ValueError as exc:
        raise OneShotWrapperError(
            "authorization file repository boundary is malformed"
        ) from exc
    if lexical_relative != relative:
        raise OneShotWrapperError(
            "authorization path contains an internal filesystem alias"
        )

    walked = lexical_root
    for part in PurePosixPath(lexical_relative).parts:
        walked = walked / part
        if os.path.islink(walked):
            raise OneShotWrapperError("authorization path contains a symlink")
    candidate = canonical_candidate
    if not candidate.is_file():
        raise OneShotWrapperError("authorization file is unavailable")
    actual_hash = _sha256_file(candidate)
    if actual_hash != expected_hash:
        raise OneShotWrapperError("authorization SHA-256 mismatch")

    document = _load_json_object(candidate, label="final authorization")
    authorization_id = _safe_identifier(
        document.get("authorization_id"), label="authorization_id"
    )
    migration_execution_id = _safe_identifier(
        document.get("migration_execution_id"), label="migration_execution_id"
    )
    expected_relative = (
        f"{AUTHORIZATION_PACKAGE_ROOT}/{authorization_id}/final_authorization.json"
    )
    if relative != expected_relative:
        raise OneShotWrapperError(
            "authorization file is outside its exact authorization package"
        )
    verdict = document.get("verdict")
    if type(verdict) is not str or not verdict.endswith("_PASS"):
        raise OneShotWrapperError("authorization verdict is not PASS")
    authorized_git = document.get("authorized_git")
    if not isinstance(authorized_git, Mapping):
        raise OneShotWrapperError("authorized_git is missing")
    branch = authorized_git.get("branch")
    head = authorized_git.get("head")
    if type(branch) is not str or not branch:
        raise OneShotWrapperError("authorized branch is malformed")
    if type(head) is not str or _HEAD.fullmatch(head) is None:
        raise OneShotWrapperError("authorized HEAD is malformed")
    command = document.get("authorized_command")
    if not isinstance(command, Mapping):
        raise OneShotWrapperError("authorized_command is missing")
    if command.get("mode") != "run" or command.get("operator_approved") is not True:
        raise OneShotWrapperError("authorization is not for approved ordinary run")
    if command.get("allowed_invocation_count") != 1:
        raise OneShotWrapperError("authorization invocation count is not one")
    for flag in (
        "automatic_retry_allowed",
        "manual_rerun_allowed",
        "resume_allowed",
        "restart_allowed",
        "successor_allowed",
    ):
        if command.get(flag) is not False:
            raise OneShotWrapperError(f"authorization flag must be false: {flag}")
    policy = document.get("campaign_policy")
    if not isinstance(policy, Mapping):
        raise OneShotWrapperError("campaign_policy is missing")
    if policy.get("main_window") != "WINDOW_15M":
        raise OneShotWrapperError("authorization main window is not WINDOW_15M")
    if policy.get("selective_1h_continuation") is not False:
        raise OneShotWrapperError("selective 1h continuation is not false")
    return candidate, document, authorization_id, migration_execution_id


def _enumerate_package(
    repository_root: Path,
    package_root: str,
    package_kind: str,
) -> list[dict[str, Any]]:
    absolute_root = repository_root / package_root
    if os.path.islink(absolute_root) or not absolute_root.is_dir():
        raise OneShotWrapperError(f"evidence package is unavailable: {package_root}")
    records: list[dict[str, Any]] = []
    stack = [absolute_root]
    while stack:
        directory = stack.pop()
        try:
            entries = sorted(os.scandir(directory), key=lambda item: item.name)
        except OSError as exc:
            raise OneShotWrapperError(
                f"evidence package could not be read: {package_root}"
            ) from exc
        for entry in entries:
            path = Path(entry.path)
            relative = path.relative_to(repository_root).as_posix()
            if entry.is_symlink():
                raise OneShotWrapperError(f"evidence package contains symlink: {relative}")
            mode = entry.stat(follow_symlinks=False).st_mode
            if stat.S_ISDIR(mode):
                stack.append(path)
                continue
            if not stat.S_ISREG(mode):
                raise OneShotWrapperError(
                    f"evidence package contains non-regular entry: {relative}"
                )
            info = path.stat()
            records.append(
                {
                    "path": relative,
                    "sha256": _sha256_file(path),
                    "size": info.st_size,
                    "package_kind": package_kind,
                }
            )
    records.sort(key=lambda item: item["path"])
    if not records:
        raise OneShotWrapperError(f"evidence package is empty: {package_root}")
    return records


def build_manifest_bytes(
    *,
    repository_root: str | Path,
    authorization_file: str | Path,
    authorization_sha256: str,
    created_at: str | None = None,
) -> tuple[dict[str, Any], bytes]:
    """Build deterministic manifest bytes from two exact current packages."""
    root = Path(repository_root).resolve()
    authorization_path, document, authorization_id, migration_execution_id = (
        _resolve_authorization(
            repository_root=root,
            authorization_file=authorization_file,
            authorization_sha256=authorization_sha256,
        )
    )
    branch = str(document["authorized_git"]["branch"])
    head = str(document["authorized_git"]["head"])
    migration_root = f"{MIGRATION_PACKAGE_ROOT}/{migration_execution_id}"
    authorization_root = f"{AUTHORIZATION_PACKAGE_ROOT}/{authorization_id}"
    files = _enumerate_package(root, migration_root, MIGRATION_PACKAGE_KIND)
    files.extend(
        _enumerate_package(root, authorization_root, AUTHORIZATION_PACKAGE_KIND)
    )
    files.sort(key=lambda item: item["path"])
    relative_authorization = authorization_path.relative_to(root).as_posix()
    payload = {
        "schema_version": MANIFEST_SCHEMA_VERSION,
        "authorization_id": authorization_id,
        "authorization_file": {
            "path": relative_authorization,
            "sha256": authorization_sha256,
        },
        "repository": {"branch": branch, "head": head},
        "authorized_command": {"mode": "run", "operator_approved": True},
        "migration_execution_id": migration_execution_id,
        "created_at": created_at or _utc_now(),
        "files": files,
    }
    return payload, _canonical_json_bytes(payload)


def build_marker_bytes(
    prepared: PreparedGitProvenanceAuthorization,
    *,
    consumed_at: str | None = None,
) -> tuple[dict[str, Any], bytes]:
    payload = {
        "schema_version": APPLICATION_MARKER_SCHEMA_VERSION,
        "authorization_id": prepared.authorization_id,
        "authorization_consumed_at": consumed_at or _utc_now(),
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
    return payload, _canonical_json_bytes(payload)


def _write_exclusive(path: Path, value: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        with path.open("xb") as handle:
            handle.write(value)
            handle.flush()
            os.fsync(handle.fileno())
    except FileExistsError as exc:
        raise OneShotWrapperError(f"create-once artifact already exists: {path}") from exc


def _make_read_only(path: Path) -> None:
    try:
        path.chmod(0o444)
    except OSError:
        pass


def _fsync_directory(path: Path) -> None:
    try:
        descriptor = os.open(path, os.O_RDONLY)
    except OSError:
        return
    try:
        os.fsync(descriptor)
    except OSError:
        pass
    finally:
        os.close(descriptor)


def _default_process_launcher(
    *,
    command: list[str],
    cwd: Path,
    env: Mapping[str, str],
    stdout_path: Path,
    stderr_path: Path,
) -> dict[str, Any]:
    with stdout_path.open("wb") as stdout, stderr_path.open("wb") as stderr:
        process = subprocess.Popen(
            command,
            cwd=str(cwd),
            env=dict(env),
            stdout=stdout,
            stderr=stderr,
            shell=False,
        )
        returncode = process.wait()
    return {"returncode": int(returncode), "pid": int(process.pid)}


def _file_identity(path: Path) -> dict[str, Any]:
    if not path.is_file():
        return {"exists": False, "size": 0, "sha256": None}
    return {
        "exists": True,
        "size": path.stat().st_size,
        "sha256": _sha256_file(path),
    }


def _write_terminal(path: Path, payload: Mapping[str, Any]) -> None:
    _write_exclusive(path, _canonical_json_bytes(payload))
    _make_read_only(path)


def _prepared_matches_validated(
    prepared: PreparedGitProvenanceAuthorization,
    validated: ValidatedGitProvenanceAuthorization,
) -> bool:
    return bool(
        prepared.allowed_untracked_paths == validated.allowed_untracked_paths
        and prepared.authorization_id == validated.authorization_id
        and prepared.manifest_sha256 == validated.manifest_sha256
        and prepared.allowed_file_set_sha256 == validated.allowed_file_set_sha256
        and prepared.file_count == validated.file_count
    )


def _select_child_python(
    *,
    repository_root: Path,
    override: str | Path | None,
) -> str:
    """Select and validate the one-shot child interpreter path.

    The returned string is the *lexical* absolute repository virtual-environment
    entrypoint (``.venv/bin/python`` on POSIX or ``.venv/Scripts/python.exe`` on
    Windows). The entrypoint is deliberately never dereferenced: a normal POSIX
    venv resolves through its symlink chain to an external base interpreter, and
    launching that base target discards the environment identity carried by
    ``pyvenv.cfg`` and the venv ``site`` configuration. Symlink targets are
    followed only to *validate* that the entrypoint reaches an existing regular
    executable; the dereferenced target is never placed in the child command.

    This is intentionally the only place the wrapper abandons canonicalization:
    repository, authorization, manifest, marker, application-root, and evidence
    paths continue to canonicalize as before.
    """
    executable_dir_name = "Scripts" if os.name == "nt" else "bin"

    source = os.fspath(override) if override is not None else sys.executable
    if not source:
        raise OneShotWrapperError(
            "child interpreter blocked: interpreter path is empty"
        )

    # Absolute, normalized, *lexical* path. ``expanduser`` + ``abspath`` removes
    # relative and "."/".." segments without following any symlink.
    lexical = Path(os.path.abspath(os.path.expanduser(source)))
    if not lexical.is_absolute():
        raise OneShotWrapperError(
            "child interpreter blocked: interpreter path is not absolute"
        )

    venv_root = Path(os.path.abspath(repository_root)) / ".venv"
    executable_dir = venv_root / executable_dir_name

    # Lexical containment under <repository>/.venv, with the exact venv
    # executable directory as the immediate parent.
    try:
        lexical.relative_to(venv_root)
    except ValueError as exc:
        raise OneShotWrapperError(
            "child interpreter blocked: interpreter is outside the repository .venv"
        ) from exc
    if lexical.parent != executable_dir:
        raise OneShotWrapperError(
            "child interpreter blocked: interpreter parent is not the venv "
            f"{executable_dir_name} directory"
        )

    # No venv ancestor directory may be a symlink; both must be real directories.
    for ancestor in (venv_root, executable_dir):
        if os.path.islink(ancestor):
            raise OneShotWrapperError(
                "child interpreter blocked: venv ancestor is a symlink"
            )
        if not os.path.isdir(ancestor):
            raise OneShotWrapperError(
                "child interpreter blocked: venv ancestor directory is missing"
            )

    # ``pyvenv.cfg`` must exist as a regular, non-symlink file.
    pyvenv_cfg = venv_root / "pyvenv.cfg"
    if os.path.islink(pyvenv_cfg):
        raise OneShotWrapperError(
            "child interpreter blocked: pyvenv.cfg must not be a symlink"
        )
    try:
        cfg_mode = os.stat(pyvenv_cfg, follow_symlinks=False).st_mode
    except OSError as exc:
        raise OneShotWrapperError(
            "child interpreter blocked: pyvenv.cfg is missing"
        ) from exc
    if not stat.S_ISREG(cfg_mode):
        raise OneShotWrapperError(
            "child interpreter blocked: pyvenv.cfg is not a regular file"
        )

    # The entrypoint itself may be a regular file or a normal venv symlink.
    try:
        entry_mode = os.lstat(lexical).st_mode
    except OSError as exc:
        raise OneShotWrapperError(
            "child interpreter blocked: interpreter entrypoint is missing"
        ) from exc
    if not (stat.S_ISREG(entry_mode) or stat.S_ISLNK(entry_mode)):
        raise OneShotWrapperError(
            "child interpreter blocked: interpreter entrypoint is not a regular "
            "file or symlink"
        )

    # Follow the entrypoint *only for validation*: it must reach an existing
    # regular file. The dereferenced target is never returned.
    try:
        target_mode = os.stat(lexical).st_mode
    except OSError as exc:
        raise OneShotWrapperError(
            "child interpreter blocked: interpreter target is missing or broken"
        ) from exc
    if not stat.S_ISREG(target_mode):
        raise OneShotWrapperError(
            "child interpreter blocked: interpreter target is not a regular file"
        )

    # Platform executable-permission contract.
    if os.name != "nt" and not os.access(lexical, os.X_OK):
        raise OneShotWrapperError(
            "child interpreter blocked: interpreter is not executable"
        )

    return str(lexical)


def apply_authorization_once(
    *,
    authorization_file: str | Path,
    authorization_sha256: str,
    operator_approved: bool,
    repository_root: str | Path | None = None,
    application_root: str | Path | None = None,
    python_executable: str | Path | None = None,
    environ: Mapping[str, str] | None = None,
    created_at: str | None = None,
    consumed_at: str | None = None,
    process_launcher: Callable[..., Mapping[str, Any]] | None = None,
    pre_marker_validator: Callable[..., PreparedGitProvenanceAuthorization] = (
        validate_git_provenance_manifest_pre_marker
    ),
    full_validator: Callable[..., ValidatedGitProvenanceAuthorization] = (
        validate_git_provenance_authorization
    ),
) -> dict[str, Any]:
    """Consume one authorization and launch at most one ordinary run child."""
    if operator_approved is not True:
        raise OneShotWrapperError("explicit operator approval is required")
    root = Path(repository_root or _repository_root()).resolve()
    app_root = Path(application_root or APPLICATION_ROOT).expanduser().resolve()
    if app_root == root or app_root.is_relative_to(root):
        raise OneShotWrapperError("application artifacts must live outside repository")

    _, _, authorization_id, _ = _resolve_authorization(
        repository_root=root,
        authorization_file=authorization_file,
        authorization_sha256=authorization_sha256,
    )
    canonical_dir = app_root / authorization_id
    if canonical_dir.exists():
        raise OneShotWrapperError("canonical authorization application already exists")

    # Select and validate the lexical venv child interpreter before any staging,
    # manifest, or marker artifact is created. A directly supplied base/Homebrew
    # interpreter, a symlinked venv ancestor, a missing/symlinked pyvenv.cfg, or
    # a broken entrypoint fails closed here with no consumption side effects.
    child_python = _select_child_python(
        repository_root=root, override=python_executable
    )

    staging_dir = app_root / ".staging" / f"{authorization_id}-{uuid.uuid4().hex}"
    staging_dir.mkdir(parents=True, exist_ok=False)
    staging_manifest = staging_dir / "git-provenance-manifest.json"
    manifest_payload, manifest_bytes = build_manifest_bytes(
        repository_root=root,
        authorization_file=authorization_file,
        authorization_sha256=authorization_sha256,
        created_at=created_at,
    )
    _write_exclusive(staging_manifest, manifest_bytes)
    manifest_sha256 = _sha256_bytes(manifest_bytes)
    prepared = pre_marker_validator(
        repository_root=root,
        manifest_path=str(staging_manifest.resolve()),
        manifest_sha256=manifest_sha256,
    )

    canonical_dir.mkdir(parents=True, exist_ok=False)
    try:
        canonical_dir.chmod(0o700)
    except OSError:
        pass
    manifest_path = canonical_dir / "git-provenance-manifest.json"
    os.replace(staging_manifest, manifest_path)
    _fsync_directory(canonical_dir)
    # Best-effort, non-recursive removal of the now-empty future staging
    # directory only. ``rmdir`` refuses to delete a non-empty directory, so no
    # staging evidence is ever recursively removed; a residual directory is a
    # benign efficiency residue that never consumes an authorization, launches a
    # second child, or overwrites the first terminal cause. The historical
    # incident staging directory lives under a different application root and is
    # never targeted.
    try:
        staging_dir.rmdir()
    except OSError:
        pass
    _make_read_only(manifest_path)
    if _sha256_file(manifest_path) != manifest_sha256:
        raise OneShotWrapperError("published manifest SHA-256 mismatch")

    marker_payload, marker_bytes = build_marker_bytes(
        prepared, consumed_at=consumed_at
    )
    marker_path = canonical_dir / "application-marker.json"
    terminal_path = canonical_dir / "wrapper-terminal.json"
    stdout_path = canonical_dir / "child-stdout.txt"
    stderr_path = canonical_dir / "child-stderr.txt"

    marker_created = False
    child_attempted = False
    started_at = _utc_now()
    child_command = [
        child_python,
        "-m",
        "printer_v1.operator_cli.operational_memory_factory_command",
        "run",
        "--operator-approved",
    ]
    try:
        _write_exclusive(marker_path, marker_bytes)
        marker_created = True
        _make_read_only(marker_path)
        marker_sha256 = _sha256_bytes(marker_bytes)
        validated = full_validator(
            repository_root=root,
            manifest_path=str(manifest_path.resolve()),
            manifest_sha256=manifest_sha256,
            marker_path=str(marker_path.resolve()),
            marker_sha256=marker_sha256,
        )
        if not _prepared_matches_validated(prepared, validated):
            raise OneShotWrapperError("pre-marker and complete validation disagree")

        _write_exclusive(stdout_path, b"")
        _write_exclusive(stderr_path, b"")
        parent = dict(os.environ if environ is None else environ)
        child_env = dict(parent)
        for name in BINDING_ENV_VARS:
            child_env.pop(name, None)
        child_env.update(
            {
                BINDING_ENV_VARS[0]: str(manifest_path.resolve()),
                BINDING_ENV_VARS[1]: manifest_sha256,
                BINDING_ENV_VARS[2]: str(marker_path.resolve()),
                BINDING_ENV_VARS[3]: marker_sha256,
            }
        )
        launcher = process_launcher or _default_process_launcher
        child_attempted = True
        launched = dict(
            launcher(
                command=child_command,
                cwd=root,
                env=child_env,
                stdout_path=stdout_path,
                stderr_path=stderr_path,
            )
        )
        returncode = launched.get("returncode")
        if type(returncode) is not int:
            raise OneShotWrapperError("child launcher returned invalid return code")
        pid = launched.get("pid")
        terminal = {
            "schema_version": WRAPPER_SCHEMA_VERSION,
            "authorization_id": authorization_id,
            "manifest_path": str(manifest_path.resolve()),
            "manifest_sha256": manifest_sha256,
            "marker_path": str(marker_path.resolve()),
            "marker_sha256": marker_sha256,
            "repository_branch": prepared.repository_branch,
            "repository_head": prepared.repository_head,
            "wrapper_execution_id": canonical_dir.name,
            "child_command": child_command,
            "child_start_attempted": True,
            "child_pid": int(pid) if type(pid) is int else None,
            "started_at": started_at,
            "ended_at": _utc_now(),
            "child_exit_code": int(returncode),
            "process_start_error": None,
            "stdout": _file_identity(stdout_path),
            "stderr": _file_identity(stderr_path),
            "automatic_retries": 0,
            "manual_reruns": 0,
            "resumes": 0,
            "restarts": 0,
            "successors": 0,
            "parent_environment_mutated": False,
            "terminal_classification": (
                "CHILD_EXITED_ZERO" if returncode == 0 else "CHILD_EXITED_NONZERO"
            ),
        }
        _write_terminal(terminal_path, terminal)
        _make_read_only(stdout_path)
        _make_read_only(stderr_path)
        return terminal
    except Exception as exc:
        marker_created = marker_created or marker_path.exists()
        if marker_created and not terminal_path.exists():
            terminal = {
                "schema_version": WRAPPER_SCHEMA_VERSION,
                "authorization_id": authorization_id,
                "manifest_path": str(manifest_path.resolve()),
                "manifest_sha256": manifest_sha256,
                "marker_path": str(marker_path.resolve()),
                "marker_sha256": (
                    _sha256_file(marker_path) if marker_path.is_file() else None
                ),
                "repository_branch": prepared.repository_branch,
                "repository_head": prepared.repository_head,
                "wrapper_execution_id": canonical_dir.name,
                "child_command": child_command,
                "child_start_attempted": child_attempted,
                "child_pid": None,
                "started_at": started_at,
                "ended_at": _utc_now(),
                "child_exit_code": None,
                "process_start_error": f"{type(exc).__name__}:{exc}",
                "stdout": _file_identity(stdout_path),
                "stderr": _file_identity(stderr_path),
                "automatic_retries": 0,
                "manual_reruns": 0,
                "resumes": 0,
                "restarts": 0,
                "successors": 0,
                "parent_environment_mutated": False,
                "terminal_classification": (
                    "CONSUMED_CHILD_START_FAILED"
                    if child_attempted
                    else "CONSUMED_CHILD_NOT_STARTED"
                ),
            }
            try:
                _write_terminal(terminal_path, terminal)
            except Exception:
                pass
        raise


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Apply one fresh WINDOW_15M authorization exactly once."
    )
    parser.add_argument("--authorization-file", required=True)
    parser.add_argument("--authorization-sha256", required=True)
    parser.add_argument("--operator-approved", action="store_true")
    args = parser.parse_args(argv)
    try:
        result = apply_authorization_once(
            authorization_file=args.authorization_file,
            authorization_sha256=args.authorization_sha256,
            operator_approved=args.operator_approved,
        )
        print(json.dumps(result, indent=2, sort_keys=True))
        return 0 if result.get("child_exit_code") == 0 else 1
    except Exception as exc:
        print(
            json.dumps(
                {
                    "status": "WINDOW_15M_ONE_SHOT_WRAPPER_BLOCKED",
                    "error_type": type(exc).__name__,
                    "error_message": str(exc),
                    "automatic_retries": 0,
                    "manual_reruns": 0,
                    "resumes": 0,
                    "restarts": 0,
                    "successors": 0,
                },
                sort_keys=True,
            ),
            file=sys.stderr,
        )
        return 2


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())


__all__ = [
    "APPLICATION_ROOT",
    "BINDING_ENV_VARS",
    "OneShotWrapperError",
    "WRAPPER_SCHEMA_VERSION",
    "apply_authorization_once",
    "build_manifest_bytes",
    "build_marker_bytes",
    "main",
]
