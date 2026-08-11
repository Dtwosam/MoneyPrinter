"""One-shot application owner for one authorized standard first-four-hour run.

This wrapper reuses the hardened ordinary one-shot filesystem/interpreter
primitives, but owns a distinct authorization profile, manifest schema, command
mode, application namespace, and child-terminal mode. It never converts the
legacy proof path into production authority and never authorizes 12h/24h.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
from typing import Any, Callable, Mapping, Sequence
import uuid

from printer_v1.operator_cli.authorization_temporal_validity import (
    AuthorizationTemporalError,
    validate_authorization_temporal_validity,
)
from printer_v1.operator_cli.git_provenance_authorization_manifest import (
    APPLICATION_MARKER_SCHEMA_VERSION,
    MIGRATION_PACKAGE_KIND,
    MIGRATION_PACKAGE_ROOT,
    PreparedGitProvenanceAuthorization,
    STANDARD_FOUR_HOUR_AUTHORIZATION_PROFILE,
    ValidatedGitProvenanceAuthorization,
    enumerate_historical_authorization_evidence,
    extract_approved_historical_authorization_ids,
    validate_git_provenance_authorization,
    validate_git_provenance_manifest_pre_marker,
    validate_prior_authorizations_non_reusable,
)
from printer_v1.operator_cli.operational_standard_4h import (
    standard_four_hour_capacity_contract,
)
from printer_v1.operator_cli.pre_authorization_migration_ledger_guard import (
    GuardResult,
    MigrationLedgerDriftGuardError,
    assert_migration_ledger_ready,
    package_binding_from_document,
)
from printer_v1.operator_cli.window_15m_child_terminal import (
    CHILD_TERMINAL_ENV_VAR,
    ChildTerminalError,
    read_child_terminal_envelope,
)
from printer_v1.operator_cli.window_15m_one_shot_wrapper import (
    BINDING_ENV_VARS,
    OneShotWrapperError,
    _attach_secondary_cleanup_blocker,
    _canonical_json_bytes,
    _cleanup_invocation_empty_canonical,
    _cleanup_pre_marker_staging,
    _default_process_launcher,
    _enumerate_package,
    _file_identity,
    _fsync_directory,
    _make_read_only,
    _prepared_matches_validated,
    _repository_root,
    _select_child_python,
    _sha256_bytes,
    _sha256_file,
    _write_exclusive,
    _write_terminal,
)
from printer_v1.sources.operational_source_contracts import (
    SolanaRpcConfigurationError,
    validate_window_15m_source_configuration,
)


WRAPPER_SCHEMA_VERSION = "PRINTER_V1_STANDARD_FOUR_HOUR_ONE_SHOT_WRAPPER_V1"
FINAL_AUTHORIZATION_SCHEMA_VERSION = "PRINTER_V1_STANDARD_FOUR_HOUR_FINAL_AUTHORIZATION_V1"
AUTHORIZED_COMMAND_MODE = "standard-four-hour-run"
ELIGIBILITY_CONTRACT_VERSION = "STANDARD_4H_ELIGIBILITY_V1"
POLICY_VERSION = "V2-9.8-STANDARD-4H-OPERATIONAL-V1"
POST_SUPPLY_DURATION_SECONDS = 14_700
PRE_LIFECYCLE_DURATION_SECONDS = 900
# Authorization capacity is projected from the one derived public standard
# contract, which derives from the canonical ``one_token_4h_runtime`` lifecycle
# arithmetic. This wrapper owns no independent request/Scheduler authority, so a
# freshly constructed authorization can never disagree with the repaired policy.
_STANDARD_CAPACITY = standard_four_hour_capacity_contract()
LIFECYCLE_REQUEST_OUTER_CEILING = int(
    _STANDARD_CAPACITY["lifecycle_request_outer_ceiling"]
)
LIFECYCLE_SCHEDULER_OUTER_CEILING = int(
    _STANDARD_CAPACITY["lifecycle_scheduler_outer_ceiling"]
)
LOCKED_WINDOWS = ("WINDOW_12H", "WINDOW_24H")
APPLICATION_ROOT = (
    Path.home() / "PrinterOperations" / "v2-9-8" / "standard-four-hour-one-shot-applications"
)
_HEAD = re.compile(r"^[0-9a-f]{40}(?:[0-9a-f]{24})?$")
_SHA256 = re.compile(r"^[0-9a-f]{64}$")
_SAFE_ID = re.compile(r"^[A-Za-z0-9_.-]+$")


class StandardFourHourOneShotWrapperError(RuntimeError):
    """Fail-closed standard-four-hour wrapper/authorization fault."""


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise StandardFourHourOneShotWrapperError(message)


def _safe_identifier(value: Any, *, label: str) -> str:
    _require(type(value) is str and bool(value) and _SAFE_ID.fullmatch(value) is not None, f"{label} is malformed")
    return str(value)


def _exact_sha256(value: Any, *, label: str) -> str:
    _require(type(value) is str and _SHA256.fullmatch(str(value)) is not None, f"{label} must be lowercase SHA-256")
    return str(value)


def fixture_authorization_document(
    *,
    branch: str,
    head: str,
    database: Mapping[str, Any],
    authorization_id: str = "FIXTURE_STANDARD_FOUR_HOUR_AUTHORIZATION",
    migration_execution_id: str = "FIXTURE_MIGRATION_050",
    verdict: str = "V2_9_8B_STANDARD_FOUR_HOUR_FINAL_AUTHORIZATION_PASS",
    authorized_at: str | None = None,
    expires_at: str | None = None,
    validity_seconds: int = 43_200,
    prior_authorizations_non_reusable: Sequence[str] = (),
) -> dict[str, Any]:
    issued = (
        datetime.fromisoformat(authorized_at)
        if authorized_at is not None
        else datetime.now(timezone.utc)
    )
    if issued.tzinfo is None:
        issued = issued.replace(tzinfo=timezone.utc)
    expiry = (
        expires_at
        if expires_at is not None
        else (issued + timedelta(seconds=int(validity_seconds))).isoformat()
    )
    return {
        "schema_version": FINAL_AUTHORIZATION_SCHEMA_VERSION,
        "authorization_id": str(authorization_id),
        "migration_execution_id": str(migration_execution_id),
        "verdict": str(verdict),
        "authorized_at": authorized_at or issued.isoformat(),
        "expires_at": str(expiry),
        "validity_seconds": int(validity_seconds),
        "repository": {"branch": str(branch), "head": str(head)},
        "authorized_command": {
            "mode": AUTHORIZED_COMMAND_MODE,
            "operator_approved": True,
        },
        "one_shot_policy": {
            "allowed_invocation_count": 1,
            "automatic_retry_allowed": False,
            "manual_rerun_allowed": False,
            "resume_allowed": False,
            "restart_allowed": False,
            "successor_allowed": False,
        },
        "campaign_policy": {
            "policy_version": POLICY_VERSION,
            "token_capacity": 2,
            "root_main_window": "WINDOW_15M",
            "post_supply_duration_seconds": POST_SUPPLY_DURATION_SECONDS,
            "pre_lifecycle_duration_seconds": PRE_LIFECYCLE_DURATION_SECONDS,
            "lifecycle_request_outer_ceiling": LIFECYCLE_REQUEST_OUTER_CEILING,
            "lifecycle_scheduler_outer_ceiling": LIFECYCLE_SCHEDULER_OUTER_CEILING,
            "eligibility_contract_version": ELIGIBILITY_CONTRACT_VERSION,
            "locked_windows": list(LOCKED_WINDOWS),
        },
        "authoritative_database": dict(database),
        "prior_authorizations_non_reusable": list(prior_authorizations_non_reusable),
    }


def validate_standard_four_hour_authorization_document(
    document: Mapping[str, Any],
) -> dict[str, Any]:
    _require(isinstance(document, Mapping), "authorization must be an object")
    required = {
        "schema_version", "authorization_id", "migration_execution_id", "verdict",
        "authorized_at", "expires_at", "validity_seconds", "repository",
        "authorized_command", "one_shot_policy", "campaign_policy",
        "authoritative_database", "prior_authorizations_non_reusable",
    }
    _require(set(document) == required, "authorization schema keys are malformed")
    _require(document.get("schema_version") == FINAL_AUTHORIZATION_SCHEMA_VERSION, "authorization schema version mismatch")
    authorization_id = _safe_identifier(document.get("authorization_id"), label="authorization_id")
    _safe_identifier(document.get("migration_execution_id"), label="migration_execution_id")
    verdict = document.get("verdict")
    _require(type(verdict) is str and verdict.endswith("_PASS"), "authorization verdict is not PASS")
    try:
        validate_authorization_temporal_validity(document)
    except AuthorizationTemporalError as exc:
        raise StandardFourHourOneShotWrapperError(f"authorization temporal validity failed: {exc}") from exc

    repository = document.get("repository")
    _require(isinstance(repository, Mapping), "repository binding is malformed")
    _require(set(repository) == {"branch", "head"}, "repository keys are malformed")
    _require(type(repository.get("branch")) is str and bool(repository.get("branch")), "branch is malformed")
    _require(type(repository.get("head")) is str and _HEAD.fullmatch(str(repository.get("head"))) is not None, "head is malformed")
    command = document.get("authorized_command")
    _require(isinstance(command, Mapping), "authorized command is malformed")
    _require(set(command) == {"mode", "operator_approved"}, "authorized command keys are malformed")
    _require(command.get("mode") == AUTHORIZED_COMMAND_MODE, "authorized command mode mismatch")
    _require(command.get("operator_approved") is True, "operator approval must be true")
    one_shot = document.get("one_shot_policy")
    expected_one_shot = {
        "allowed_invocation_count": 1,
        "automatic_retry_allowed": False,
        "manual_rerun_allowed": False,
        "resume_allowed": False,
        "restart_allowed": False,
        "successor_allowed": False,
    }
    _require(isinstance(one_shot, Mapping) and dict(one_shot) == expected_one_shot, "one-shot policy mismatch")
    campaign = document.get("campaign_policy")
    expected_campaign = {
        "policy_version": POLICY_VERSION,
        "token_capacity": 2,
        "root_main_window": "WINDOW_15M",
        "post_supply_duration_seconds": POST_SUPPLY_DURATION_SECONDS,
        "pre_lifecycle_duration_seconds": PRE_LIFECYCLE_DURATION_SECONDS,
        "lifecycle_request_outer_ceiling": LIFECYCLE_REQUEST_OUTER_CEILING,
        "lifecycle_scheduler_outer_ceiling": LIFECYCLE_SCHEDULER_OUTER_CEILING,
        "eligibility_contract_version": ELIGIBILITY_CONTRACT_VERSION,
        "locked_windows": list(LOCKED_WINDOWS),
    }
    _require(isinstance(campaign, Mapping) and dict(campaign) == expected_campaign, "campaign policy mismatch")
    database = document.get("authoritative_database")
    required_db = {"path", "sha256", "size", "inode", "mtime_ns", "migration_count", "migration_head"}
    _require(isinstance(database, Mapping) and set(database) == required_db, "authoritative database keys are malformed")
    _require(type(database.get("path")) is str and bool(database.get("path")), "database path is malformed")
    _require(type(database.get("sha256")) is str and _SHA256.fullmatch(str(database.get("sha256"))) is not None, "database sha256 is malformed")
    for key in ("size", "inode", "mtime_ns", "migration_count"):
        _require(type(database.get(key)) is int and int(database.get(key)) >= 0, f"database {key} is malformed")
    _require(type(database.get("migration_head")) is str and bool(database.get("migration_head")), "migration head is malformed")
    validate_prior_authorizations_non_reusable(
        document.get("prior_authorizations_non_reusable"),
        current_authorization_id=authorization_id,
    )
    return json.loads(json.dumps(dict(document)))


def _resolve_authorization(
    *, repository_root: Path, authorization_file: str | Path, authorization_sha256: str
) -> tuple[Path, dict[str, Any], str, str]:
    expected_hash = _exact_sha256(authorization_sha256, label="authorization SHA-256")
    candidate = Path(authorization_file)
    if not candidate.is_absolute():
        candidate = repository_root / candidate
    lexical_candidate = Path(os.path.abspath(candidate))
    canonical_root = Path(os.path.realpath(repository_root))
    canonical_candidate = Path(os.path.realpath(lexical_candidate))
    try:
        relative = canonical_candidate.relative_to(canonical_root).as_posix()
    except ValueError as exc:
        raise StandardFourHourOneShotWrapperError("authorization file must be inside repository") from exc
    lexical_root = next(
        (ancestor for ancestor in lexical_candidate.parents if Path(os.path.realpath(ancestor)) == canonical_root),
        None,
    )
    _require(lexical_root is not None, "authorization file repository boundary could not be established")
    lexical_relative = lexical_candidate.relative_to(lexical_root).as_posix()
    _require(lexical_relative == relative, "authorization path contains an internal filesystem alias")
    walked = lexical_root
    for part in PurePosixPath(lexical_relative).parts:
        walked = walked / part
        _require(not os.path.islink(walked), "authorization path contains a symlink")
    _require(canonical_candidate.is_file(), "authorization file is unavailable")
    _require(_sha256_file(canonical_candidate) == expected_hash, "authorization SHA-256 mismatch")
    try:
        document = json.loads(canonical_candidate.read_text(encoding="utf-8"))
    except (OSError, ValueError, UnicodeError) as exc:
        raise StandardFourHourOneShotWrapperError("final authorization is unreadable or malformed") from exc
    validated = validate_standard_four_hour_authorization_document(document)
    authorization_id = _safe_identifier(validated["authorization_id"], label="authorization_id")
    migration_execution_id = _safe_identifier(validated["migration_execution_id"], label="migration_execution_id")
    expected_relative = (
        f"{STANDARD_FOUR_HOUR_AUTHORIZATION_PROFILE.authorization_package_root}/"
        f"{authorization_id}/final_authorization.json"
    )
    _require(relative == expected_relative, "authorization file is outside its exact standard-four-hour package")
    return canonical_candidate, validated, authorization_id, migration_execution_id


def build_manifest_bytes(
    *, repository_root: str | Path, authorization_file: str | Path,
    authorization_sha256: str, created_at: str | None = None
) -> tuple[dict[str, Any], bytes]:
    root = Path(repository_root).resolve()
    authorization_path, document, authorization_id, migration_execution_id = _resolve_authorization(
        repository_root=root,
        authorization_file=authorization_file,
        authorization_sha256=authorization_sha256,
    )
    approved_historical_ids = extract_approved_historical_authorization_ids(
        document, current_authorization_id=authorization_id
    )
    branch = str(document["repository"]["branch"])
    head = str(document["repository"]["head"])
    migration_root = f"{MIGRATION_PACKAGE_ROOT}/{migration_execution_id}"
    authorization_root = (
        f"{STANDARD_FOUR_HOUR_AUTHORIZATION_PROFILE.authorization_package_root}/{authorization_id}"
    )
    files = _enumerate_package(root, migration_root, MIGRATION_PACKAGE_KIND)
    files.extend(
        _enumerate_package(
            root, authorization_root, STANDARD_FOUR_HOUR_AUTHORIZATION_PROFILE.authorization_package_kind
        )
    )
    files.sort(key=lambda item: item["path"])
    historical = list(
        enumerate_historical_authorization_evidence(
            repository_root=root,
            current_authorization_id=authorization_id,
            approved_historical_authorization_ids=approved_historical_ids,
            authorization_package_roots=(
                STANDARD_FOUR_HOUR_AUTHORIZATION_PROFILE.historical_authorization_package_roots
            ),
            current_authorization_package_root=(
                STANDARD_FOUR_HOUR_AUTHORIZATION_PROFILE.authorization_package_root
            ),
        )
    )
    payload = {
        "schema_version": STANDARD_FOUR_HOUR_AUTHORIZATION_PROFILE.manifest_schema_version,
        "authorization_id": authorization_id,
        "authorization_file": {
            "path": authorization_path.relative_to(root).as_posix(),
            "sha256": authorization_sha256,
        },
        "repository": {"branch": branch, "head": head},
        "authorized_command": {"mode": AUTHORIZED_COMMAND_MODE, "operator_approved": True},
        "migration_execution_id": migration_execution_id,
        "created_at": created_at or _utc_now(),
        "files": files,
        "historical_authorization_evidence": historical,
    }
    return payload, _canonical_json_bytes(payload)


def build_marker_bytes(
    prepared: PreparedGitProvenanceAuthorization, *, consumed_at: str | None = None
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
        "command": {"mode": AUTHORIZED_COMMAND_MODE, "operator_approved": True},
        "allowed_invocation_count": 1,
        "automatic_retry_allowed": False,
        "manual_rerun_allowed": False,
        "resume_allowed": False,
        "restart_allowed": False,
        "successor_allowed": False,
    }
    return payload, _canonical_json_bytes(payload)


def build_child_command(python_executable: str) -> list[str]:
    return [
        str(python_executable), "-m",
        "printer_v1.operator_cli.operational_memory_factory_command",
        AUTHORIZED_COMMAND_MODE, "--operator-approved",
    ]


def _default_pre_launch_check(*, repository_root: Path, environment: Mapping[str, str]) -> None:
    try:
        validate_window_15m_source_configuration(environment)
        from printer_v1.operator_cli.window_15m_concrete_composition import (
            ConcreteCompositionError,
            run_window_15m_concrete_composition_preflight,
        )
        run_window_15m_concrete_composition_preflight(
            repository_root=str(repository_root), timeout_seconds=5.0, environment=environment
        )
    except (SolanaRpcConfigurationError, ConcreteCompositionError) as exc:
        raise StandardFourHourOneShotWrapperError(
            f"authorization blocked before consumption: composition/source preflight: {exc}"
        ) from exc


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
    migration_ledger_guard: Callable[..., GuardResult | None] = assert_migration_ledger_ready,
    pre_launch_check: Callable[..., Any] | None = None,
    pre_marker_validator: Callable[..., PreparedGitProvenanceAuthorization] = validate_git_provenance_manifest_pre_marker,
    full_validator: Callable[..., ValidatedGitProvenanceAuthorization] = validate_git_provenance_authorization,
) -> dict[str, Any]:
    """Consume one standard-4h authorization and launch at most one child."""
    _require(operator_approved is True, "explicit operator approval is required")
    root = Path(repository_root or _repository_root()).resolve()
    app_root = Path(application_root or APPLICATION_ROOT).expanduser().resolve()
    _require(not (app_root == root or app_root.is_relative_to(root)), "application artifacts must live outside repository")
    _, document, authorization_id, _ = _resolve_authorization(
        repository_root=root, authorization_file=authorization_file, authorization_sha256=authorization_sha256
    )
    try:
        validate_authorization_temporal_validity(document)
    except AuthorizationTemporalError as exc:
        raise StandardFourHourOneShotWrapperError(
            f"authorization blocked before consumption: temporal validity: {exc}"
        ) from exc
    canonical_dir = app_root / authorization_id
    _require(not canonical_dir.exists(), "canonical authorization application already exists")
    try:
        child_python = _select_child_python(repository_root=root, override=python_executable)
    except OneShotWrapperError as exc:
        raise StandardFourHourOneShotWrapperError(str(exc)) from exc
    try:
        package_binding = package_binding_from_document(document)
        migration_ledger_guard(mode="review", package_binding=package_binding)
    except MigrationLedgerDriftGuardError as exc:
        raise StandardFourHourOneShotWrapperError(
            f"authorization blocked before consumption: {exc}"
        ) from exc
    parent = dict(os.environ if environ is None else environ)
    child_env_preview = dict(parent)
    for name in BINDING_ENV_VARS:
        child_env_preview.pop(name, None)
    child_env_preview.pop(CHILD_TERMINAL_ENV_VAR, None)
    checker = pre_launch_check or _default_pre_launch_check
    checker(repository_root=root, environment=child_env_preview)

    staging_dir = app_root / ".staging" / f"{authorization_id}-{uuid.uuid4().hex}"
    staging_active = False
    canonical_created = False
    try:
        staging_dir.mkdir(parents=True, exist_ok=False)
        staging_active = True
        staging_manifest = staging_dir / "git-provenance-manifest.json"
        _, manifest_bytes = build_manifest_bytes(
            repository_root=root, authorization_file=authorization_file,
            authorization_sha256=authorization_sha256, created_at=created_at
        )
        _write_exclusive(staging_manifest, manifest_bytes)
        manifest_sha256 = _sha256_bytes(manifest_bytes)
        prepared = pre_marker_validator(
            repository_root=root,
            manifest_path=str(staging_manifest.resolve()),
            manifest_sha256=manifest_sha256,
            profile=STANDARD_FOUR_HOUR_AUTHORIZATION_PROFILE,
        )
        canonical_dir.mkdir(parents=True, exist_ok=False)
        canonical_created = True
        try:
            canonical_dir.chmod(0o700)
        except OSError:
            pass
        manifest_path = canonical_dir / "git-provenance-manifest.json"
        os.replace(staging_manifest, manifest_path)
        _fsync_directory(canonical_dir)
        try:
            staging_dir.rmdir()
        except OSError:
            pass
        staging_active = False
        _make_read_only(manifest_path)
        _require(_sha256_file(manifest_path) == manifest_sha256, "published manifest SHA-256 mismatch")
    except Exception as original:
        if staging_active:
            secondary = _cleanup_pre_marker_staging(staging_dir)
            if secondary is not None:
                _attach_secondary_cleanup_blocker(original, field="secondary_staging_cleanup_blocker", message=secondary)
        if canonical_created:
            secondary = _cleanup_invocation_empty_canonical(canonical_dir)
            if secondary is not None:
                _attach_secondary_cleanup_blocker(original, field="secondary_canonical_cleanup_blocker", message=secondary)
        raise

    _, marker_bytes = build_marker_bytes(prepared, consumed_at=consumed_at)
    marker_path = canonical_dir / "application-marker.json"
    terminal_path = canonical_dir / "wrapper-terminal.json"
    stdout_path = canonical_dir / "child-stdout.txt"
    stderr_path = canonical_dir / "child-stderr.txt"
    child_terminal_path = canonical_dir / "child-terminal.json"
    child_command = build_child_command(child_python)
    started_at = _utc_now()
    marker_created = False
    child_attempted = False
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
            profile=STANDARD_FOUR_HOUR_AUTHORIZATION_PROFILE,
        )
        _require(_prepared_matches_validated(prepared, validated), "pre-marker and complete validation disagree")
        _write_exclusive(stdout_path, b"")
        _write_exclusive(stderr_path, b"")
        child_env = dict(parent)
        for name in BINDING_ENV_VARS:
            child_env.pop(name, None)
        child_env.pop(CHILD_TERMINAL_ENV_VAR, None)
        child_env.update({
            BINDING_ENV_VARS[0]: str(manifest_path.resolve()),
            BINDING_ENV_VARS[1]: manifest_sha256,
            BINDING_ENV_VARS[2]: str(marker_path.resolve()),
            BINDING_ENV_VARS[3]: marker_sha256,
            CHILD_TERMINAL_ENV_VAR: str(child_terminal_path.resolve()),
        })
        launcher = process_launcher or _default_process_launcher
        child_attempted = True
        launched = dict(launcher(
            command=child_command, cwd=root, env=child_env,
            stdout_path=stdout_path, stderr_path=stderr_path
        ))
        returncode = launched.get("returncode")
        _require(type(returncode) is int, "child launcher returned invalid return code")
        pid = launched.get("pid")
        child_terminal_error = None
        child_envelope = None
        try:
            child_envelope = read_child_terminal_envelope(
                child_terminal_path,
                expected_authorization_id=authorization_id,
                expected_marker_path=marker_path,
                expected_marker_sha256=marker_sha256,
                expected_exit_code=int(returncode),
                expected_mode=AUTHORIZED_COMMAND_MODE,
            )
        except ChildTerminalError as exc:
            child_terminal_error = f"{type(exc).__name__}:{exc}"
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
            "child_terminal": _file_identity(child_terminal_path),
            "child_terminal_valid": child_envelope is not None,
            "child_terminal_error": child_terminal_error,
            "child_terminal_envelope": child_envelope,
            "automatic_retries": 0,
            "manual_reruns": 0,
            "resumes": 0,
            "restarts": 0,
            "successors": 0,
            "parent_environment_mutated": False,
            "terminal_classification": (
                ("CHILD_EXITED_ZERO" if returncode == 0 else "CHILD_EXITED_NONZERO")
                if child_envelope is not None
                else ("CHILD_EXITED_ZERO_TERMINAL_INVALID" if returncode == 0 else "CHILD_EXITED_NONZERO_TERMINAL_INVALID")
            ),
        }
        _write_terminal(terminal_path, terminal)
        _make_read_only(stdout_path)
        _make_read_only(stderr_path)
        if child_terminal_path.is_file():
            _make_read_only(child_terminal_path)
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
                "marker_sha256": _sha256_file(marker_path) if marker_path.is_file() else None,
                "repository_branch": prepared.repository_branch,
                "repository_head": prepared.repository_head,
                "wrapper_execution_id": canonical_dir.name,
                "child_command": child_command,
                "child_start_attempted": child_attempted,
                "child_exit_code": None,
                "process_start_error": f"{type(exc).__name__}:{exc}",
                "started_at": started_at,
                "ended_at": _utc_now(),
                "automatic_retries": 0,
                "manual_reruns": 0,
                "resumes": 0,
                "restarts": 0,
                "successors": 0,
                "parent_environment_mutated": False,
                "terminal_classification": (
                    "CONSUMED_CHILD_START_FAILED" if child_attempted else "CONSUMED_CHILD_NOT_STARTED"
                ),
            }
            try:
                _write_terminal(terminal_path, terminal)
            except Exception:
                pass
        raise


__all__ = [
    "APPLICATION_ROOT",
    "AUTHORIZED_COMMAND_MODE",
    "FINAL_AUTHORIZATION_SCHEMA_VERSION",
    "StandardFourHourOneShotWrapperError",
    "WRAPPER_SCHEMA_VERSION",
    "apply_authorization_once",
    "build_child_command",
    "build_manifest_bytes",
    "build_marker_bytes",
    "fixture_authorization_document",
    "validate_standard_four_hour_authorization_document",
]
