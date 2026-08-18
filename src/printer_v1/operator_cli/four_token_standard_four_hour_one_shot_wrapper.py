"""One-use application owner for one authorized operational four-token campaign.

This wrapper is the dedicated OPERATIONAL 4/2/2 authority for
``four-token-standard-four-hour-run``: one operator-approved bounded invocation
of exactly four through-4h token slots across exactly two governed cycles of
exactly two fresh distinct token/pair slots each.

It reuses the hardened ordinary one-shot filesystem/interpreter primitives but
owns a distinct authorization profile, manifest schema, command mode,
application namespace, and child-terminal mode.

It never widens the public two-token ``standard-four-hour-run`` wrapper into
four-token authority, never converts ``four-token-bounded-capacity-proof-run``
into ordinary operational authority, never authorizes 12h/24h, and never creates
a second factory runner or event loop.

Capacity is projected from the neutral operational composition facade, which
derives from ``scaled_standard_four_hour_capacity_contract(4)``, so this module
owns no independent numeric request/Scheduler authority.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
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
    FOUR_TOKEN_STANDARD_FOUR_HOUR_AUTHORIZATION_PROFILE,
    PreparedGitProvenanceAuthorization,
    ValidatedGitProvenanceAuthorization,
    HISTORICAL_MIGRATION_EVIDENCE_KEY,
    enumerate_historical_authorization_evidence,
    enumerate_historical_migration_evidence,
    extract_approved_historical_authorization_ids,
    validate_git_provenance_authorization,
    validate_git_provenance_manifest_pre_marker,
    validate_prior_authorizations_non_reusable,
)
# Re-exported so callers can read this authority's derived envelope without
# importing proof-named modules. The exact policy itself stays facade-owned.
from printer_v1.operator_cli.four_token_operational_composition import (
    FOUR_TOKEN_STANDARD_FOUR_HOUR_MODE,
    LIFECYCLE_REQUESTS_PER_TOKEN,
    LIFECYCLE_REQUEST_OUTER_CEILING,
    LIFECYCLE_SCHEDULER_OUTER_CEILING,
    MAX_ONE_SHOT_WALL_ENVELOPE_SECONDS,
    POLICY_VERSION,
    POST_SUPPLY_LIFECYCLE_DURATION_SECONDS,
    PRE_LIFECYCLE_ACQUISITION_DURATION_SECONDS,
    exact_operational_policy,
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


WRAPPER_SCHEMA_VERSION = (
    "PRINTER_V1_FOUR_TOKEN_STANDARD_4H_ONE_SHOT_WRAPPER_V1"
)
FINAL_AUTHORIZATION_SCHEMA_VERSION = (
    "PRINTER_V1_FOUR_TOKEN_STANDARD_4H_FINAL_AUTHORIZATION_V1"
)
AUTHORIZED_COMMAND_MODE = (
    FOUR_TOKEN_STANDARD_FOUR_HOUR_AUTHORIZATION_PROFILE.command_mode
)

APPLICATION_ROOT = (
    Path.home()
    / "PrinterOperations"
    / "v2-9-8"
    / "four-token-standard-four-hour-one-shot-applications"
)

_HEAD = re.compile(r"^[0-9a-f]{40}(?:[0-9a-f]{24})?$")
_SHA256 = re.compile(r"^[0-9a-f]{64}$")
_SAFE_ID = re.compile(r"^[A-Za-z0-9_.-]+$")

_DOCUMENT_KEYS = {
    "schema_version",
    "authorization_id",
    "migration_execution_id",
    "verdict",
    "authorized_at",
    "expires_at",
    "validity_seconds",
    "repository",
    "authorized_command",
    "one_shot_policy",
    "operational_policy",
    "authoritative_database",
    "prior_authorizations_non_reusable",
}
_DATABASE_KEYS = {
    "path",
    "sha256",
    "size",
    "inode",
    "mtime_ns",
    "migration_count",
    "migration_head",
}
_ONE_SHOT_POLICY = {
    "allowed_invocation_count": 1,
    "automatic_retry_allowed": False,
    "manual_rerun_allowed": False,
    "resume_allowed": False,
    "restart_allowed": False,
    "successor_allowed": False,
}


class FourTokenStandardFourHourOneShotWrapperError(RuntimeError):
    """Fail-closed operational four-token 4/2/2 wrapper/authorization fault."""


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise FourTokenStandardFourHourOneShotWrapperError(message)


def _safe_identifier(value: Any, *, label: str) -> str:
    _require(
        type(value) is str and bool(value) and _SAFE_ID.fullmatch(value) is not None,
        f"{label} is malformed",
    )
    return str(value)


# The exact operational policy is owned by the neutral composition facade so
# this wrapper cannot express a capacity the canonical contract does not derive.


def fixture_authorization_document(
    *,
    branch: str,
    head: str,
    database: Mapping[str, Any],
    authorization_id: str = "FIXTURE_FOUR_TOKEN_STANDARD_4H_AUTHORIZATION",
    migration_execution_id: str = "FIXTURE_MIGRATION_058",
    verdict: str = (
        "V2_9_8B_FOUR_TOKEN_STANDARD_4H_FINAL_AUTHORIZATION_PASS"
    ),
    authorized_at: str | None = None,
    expires_at: str | None = None,
    validity_seconds: int = 43_200,
    prior_authorizations_non_reusable: Sequence[str] = (),
) -> dict[str, Any]:
    """Build one offline fixture-shaped document. This creates no authority."""
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
        "one_shot_policy": dict(_ONE_SHOT_POLICY),
        "operational_policy": exact_operational_policy(),
        "authoritative_database": dict(database),
        "prior_authorizations_non_reusable": list(prior_authorizations_non_reusable),
    }


def validate_four_token_standard_four_hour_authorization_document(
    document: Mapping[str, Any],
) -> dict[str, Any]:
    """Validate one operational 4/2/2 authorization document and fail closed."""
    _require(isinstance(document, Mapping), "authorization must be an object")
    _require(set(document) == _DOCUMENT_KEYS, "authorization schema keys are malformed")
    _require(
        document.get("schema_version") == FINAL_AUTHORIZATION_SCHEMA_VERSION,
        "authorization schema version mismatch",
    )
    authorization_id = _safe_identifier(
        document.get("authorization_id"), label="authorization_id"
    )
    _safe_identifier(
        document.get("migration_execution_id"), label="migration_execution_id"
    )
    verdict = document.get("verdict")
    _require(
        type(verdict) is str and verdict.endswith("_PASS"),
        "authorization verdict is not PASS",
    )
    try:
        validate_authorization_temporal_validity(document)
    except AuthorizationTemporalError as exc:
        raise FourTokenStandardFourHourOneShotWrapperError(
            f"authorization temporal validity failed: {exc}"
        ) from exc

    repository = document.get("repository")
    _require(isinstance(repository, Mapping), "repository binding is malformed")
    _require(set(repository) == {"branch", "head"}, "repository keys are malformed")
    _require(
        type(repository.get("branch")) is str and bool(repository.get("branch")),
        "branch is malformed",
    )
    _require(
        type(repository.get("head")) is str
        and _HEAD.fullmatch(str(repository.get("head"))) is not None,
        "head is malformed",
    )
    command = document.get("authorized_command")
    _require(isinstance(command, Mapping), "authorized command is malformed")
    _require(
        set(command) == {"mode", "operator_approved"},
        "authorized command keys are malformed",
    )
    _require(
        command.get("mode") == AUTHORIZED_COMMAND_MODE,
        "authorized command mode mismatch",
    )
    _require(command.get("operator_approved") is True, "operator approval must be true")
    one_shot = document.get("one_shot_policy")
    _require(
        isinstance(one_shot, Mapping) and dict(one_shot) == _ONE_SHOT_POLICY,
        "one-shot policy mismatch",
    )
    operational_policy = document.get("operational_policy")
    _require(
        isinstance(operational_policy, Mapping),
        "operational policy is malformed",
    )
    expected_policy = exact_operational_policy()
    _require(
        set(operational_policy) == set(expected_policy),
        "operational policy keys are malformed",
    )
    # Exact equality against the one derived authority. A widened capacity, a
    # third cycle, a single-token cycle, shorter spacing, a collapsed or widened
    # clock, a copied two-token ceiling, a retry, endpoint rotation, or a long
    # window all fail closed here rather than reaching consumption.
    for key, expected in expected_policy.items():
        actual = operational_policy.get(key)
        _require(
            type(actual) is type(expected) and actual == expected,
            f"operational policy {key} mismatch",
        )
    database = document.get("authoritative_database")
    _require(
        isinstance(database, Mapping) and set(database) == _DATABASE_KEYS,
        "authoritative database keys are malformed",
    )
    _require(
        type(database.get("path")) is str and bool(database.get("path")),
        "database path is malformed",
    )
    _require(
        type(database.get("sha256")) is str
        and _SHA256.fullmatch(str(database.get("sha256"))) is not None,
        "database sha256 is malformed",
    )
    for key in ("size", "inode", "mtime_ns", "migration_count"):
        _require(
            type(database.get(key)) is int and int(database.get(key)) >= 0,
            f"database {key} is malformed",
        )
    _require(
        type(database.get("migration_head")) is str and bool(database.get("migration_head")),
        "migration head is malformed",
    )
    validate_prior_authorizations_non_reusable(
        document.get("prior_authorizations_non_reusable"),
        current_authorization_id=authorization_id,
    )
    return json.loads(json.dumps(dict(document)))


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _exact_sha256(value: Any, *, label: str) -> str:
    _require(
        type(value) is str and _SHA256.fullmatch(str(value)) is not None,
        f"{label} must be lowercase SHA-256",
    )
    return str(value)


def _resolve_authorization(
    *,
    repository_root: Path,
    authorization_file: str | Path,
    authorization_sha256: str,
) -> tuple[Path, dict[str, Any], str, str]:
    """Resolve one operational authorization in its exact package, no aliases."""
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
        raise FourTokenStandardFourHourOneShotWrapperError(
            "authorization file must be inside repository"
        ) from exc
    lexical_root = next(
        (
            ancestor
            for ancestor in lexical_candidate.parents
            if Path(os.path.realpath(ancestor)) == canonical_root
        ),
        None,
    )
    _require(
        lexical_root is not None,
        "authorization file repository boundary could not be established",
    )
    lexical_relative = lexical_candidate.relative_to(lexical_root).as_posix()
    _require(
        lexical_relative == relative,
        "authorization path contains an internal filesystem alias",
    )
    walked = lexical_root
    for part in PurePosixPath(lexical_relative).parts:
        walked = walked / part
        _require(not os.path.islink(walked), "authorization path contains a symlink")
    _require(canonical_candidate.is_file(), "authorization file is unavailable")
    _require(
        _sha256_file(canonical_candidate) == expected_hash,
        "authorization SHA-256 mismatch",
    )
    try:
        document = json.loads(canonical_candidate.read_text(encoding="utf-8"))
    except (OSError, ValueError, UnicodeError) as exc:
        raise FourTokenStandardFourHourOneShotWrapperError(
            "final authorization is unreadable or malformed"
        ) from exc
    validated = validate_four_token_standard_four_hour_authorization_document(document)
    authorization_id = _safe_identifier(
        validated["authorization_id"], label="authorization_id"
    )
    migration_execution_id = _safe_identifier(
        validated["migration_execution_id"], label="migration_execution_id"
    )
    expected_relative = (
        f"{FOUR_TOKEN_STANDARD_FOUR_HOUR_AUTHORIZATION_PROFILE.authorization_package_root}/"
        f"{authorization_id}/final_authorization.json"
    )
    _require(
        relative == expected_relative,
        "authorization file is outside its exact operational four-token package",
    )
    return canonical_candidate, validated, authorization_id, migration_execution_id


def build_manifest_bytes(
    *,
    repository_root: str | Path,
    authorization_file: str | Path,
    authorization_sha256: str,
    created_at: str | None = None,
) -> tuple[dict[str, Any], bytes]:
    """Bind the exact migration-058 and operational authorization packages only."""
    root = Path(repository_root).resolve()
    (
        authorization_path,
        document,
        authorization_id,
        migration_execution_id,
    ) = _resolve_authorization(
        repository_root=root,
        authorization_file=authorization_file,
        authorization_sha256=authorization_sha256,
    )
    approved_historical_ids = extract_approved_historical_authorization_ids(
        document, current_authorization_id=authorization_id
    )
    branch = str(document["repository"]["branch"])
    head = str(document["repository"]["head"])
    profile = FOUR_TOKEN_STANDARD_FOUR_HOUR_AUTHORIZATION_PROFILE
    migration_root = f"{profile.migration_package_root}/{migration_execution_id}"
    authorization_root = (
        f"{profile.authorization_package_root}/{authorization_id}"
    )
    try:
        files = _enumerate_package(
            root, migration_root, profile.migration_package_kind
        )
        files.extend(
            _enumerate_package(
                root, authorization_root, profile.authorization_package_kind
            )
        )
    except OneShotWrapperError as exc:
        raise FourTokenStandardFourHourOneShotWrapperError(
            f"four-token current evidence package is unavailable: {exc}"
        ) from exc
    files.sort(key=lambda item: item["path"])
    historical = list(
        enumerate_historical_authorization_evidence(
            repository_root=root,
            current_authorization_id=authorization_id,
            approved_historical_authorization_ids=approved_historical_ids,
            authorization_package_roots=(
                profile.historical_authorization_package_roots
            ),
            current_authorization_package_root=profile.authorization_package_root,
        )
    )
    # Preserved historical migration evidence is a separate, exact, profile-bound
    # class. It explains how the current database evolved and never becomes the
    # current schema transition, which stays migration 058 alone.
    historical_migration = list(
        enumerate_historical_migration_evidence(
            repository_root=root,
            historical_migration_packages=profile.historical_migration_packages,
        )
    )
    payload = {
        "schema_version": profile.manifest_schema_version,
        "authorization_id": authorization_id,
        "authorization_file": {
            "path": authorization_path.relative_to(root).as_posix(),
            "sha256": authorization_sha256,
        },
        "repository": {"branch": branch, "head": head},
        "authorized_command": {
            "mode": AUTHORIZED_COMMAND_MODE,
            "operator_approved": True,
        },
        "migration_execution_id": migration_execution_id,
        "created_at": created_at or _utc_now(),
        "files": files,
        "historical_authorization_evidence": historical,
        HISTORICAL_MIGRATION_EVIDENCE_KEY: historical_migration,
    }
    return payload, _canonical_json_bytes(payload)


def build_marker_bytes(
    prepared: PreparedGitProvenanceAuthorization,
    *,
    consumed_at: str | None = None,
) -> tuple[dict[str, Any], bytes]:
    """Build the one immutable marker for this operational authorization."""
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
    """Return the one dedicated operational 4/2/2 child invocation."""
    return [
        str(python_executable),
        "-m",
        "printer_v1.operator_cli.operational_memory_factory_command",
        AUTHORIZED_COMMAND_MODE,
        "--operator-approved",
    ]


def _default_zero_state_gate(
    *,
    authorization_document: Mapping[str, Any],
    environment: Mapping[str, str],
    authoritative_db_path: str | Path | None = None,
    printer_runtime_liveness_probe: Callable[[int | None], bool] | None = None,
    printer_host_process_inventory: Callable[..., Any] | None = None,
    **_unused: Any,
) -> Mapping[str, Any]:
    """Run the real read-only pre-consumption gate against live host state."""
    from printer_v1.operator_cli.four_token_proof_zero_state_gate import (
        FourTokenProofZeroStateError,
        active_printer_runtime_processes,
        assert_four_token_standard_four_hour_zero_state,
    )
    from printer_v1.operator_cli.operational_memory_factory_command import (
        AUTHORITATIVE_DB,
    )

    database = (
        Path(authoritative_db_path)
        if authoritative_db_path is not None
        else AUTHORITATIVE_DB
    )

    def _printer_process_probe() -> tuple[int, ...]:
        # One bounded read-only pass over durable supervision ownership. It
        # never polls, signals, or mutates a process, and it fails closed when
        # process state cannot be inspected reliably.
        return active_printer_runtime_processes(
            database,
            liveness_probe=printer_runtime_liveness_probe,
            host_process_inventory=printer_host_process_inventory,
        )

    try:
        return assert_four_token_standard_four_hour_zero_state(
            db_path=database,
            authorization_document=authorization_document,
            environment=environment,
            printer_process_probe=_printer_process_probe,
        )
    except FourTokenProofZeroStateError as exc:
        raise FourTokenStandardFourHourOneShotWrapperError(
            f"authorization blocked before consumption: {exc}"
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
    migration_ledger_guard: Callable[..., Any] | None = None,
    zero_state_gate: Callable[..., Mapping[str, Any]] | None = None,
    authoritative_db_path: str | Path | None = None,
    printer_runtime_liveness_probe: Callable[[int | None], bool] | None = None,
    printer_host_process_inventory: Callable[..., Any] | None = None,
    pre_marker_validator: Callable[
        ..., PreparedGitProvenanceAuthorization
    ] = validate_git_provenance_manifest_pre_marker,
    full_validator: Callable[
        ..., ValidatedGitProvenanceAuthorization
    ] = validate_git_provenance_authorization,
) -> dict[str, Any]:
    """Consume one operational 4/2/2 authorization and launch at most one child.

    Once the marker exists the authorization is consumed, even if the child later
    fails. There is no retry, rerun, resume, restart, or successor path.
    """
    _require(operator_approved is True, "explicit operator approval is required")
    root = Path(repository_root or _repository_root()).resolve()
    app_root = Path(application_root or APPLICATION_ROOT).expanduser().resolve()
    _require(
        not (app_root == root or app_root.is_relative_to(root)),
        "application artifacts must live outside repository",
    )
    _, document, authorization_id, _ = _resolve_authorization(
        repository_root=root,
        authorization_file=authorization_file,
        authorization_sha256=authorization_sha256,
    )
    try:
        validate_authorization_temporal_validity(document)
    except AuthorizationTemporalError as exc:
        raise FourTokenStandardFourHourOneShotWrapperError(
            f"authorization blocked before consumption: temporal validity: {exc}"
        ) from exc
    canonical_dir = app_root / authorization_id
    _require(
        not canonical_dir.exists(), "canonical authorization application already exists"
    )
    try:
        child_python = _select_child_python(
            repository_root=root, override=python_executable
        )
    except OneShotWrapperError as exc:
        raise FourTokenStandardFourHourOneShotWrapperError(str(exc)) from exc

    parent = dict(os.environ if environ is None else environ)
    child_env_preview = dict(parent)
    for name in BINDING_ENV_VARS:
        child_env_preview.pop(name, None)
    child_env_preview.pop(CHILD_TERMINAL_ENV_VAR, None)

    if migration_ledger_guard is not None:
        from printer_v1.operator_cli.pre_authorization_migration_ledger_guard import (
            MigrationLedgerDriftGuardError,
            package_binding_from_document,
        )

        try:
            migration_ledger_guard(
                mode="review", package_binding=package_binding_from_document(document)
            )
        except MigrationLedgerDriftGuardError as exc:
            raise FourTokenStandardFourHourOneShotWrapperError(
                f"authorization blocked before consumption: {exc}"
            ) from exc

    # Every free read-only gate runs while the authorization is still unconsumed.
    gate = zero_state_gate or _default_zero_state_gate
    zero_state_evidence = dict(
        gate(
            authorization_document=document,
            environment=child_env_preview,
            repository_root=root,
            authoritative_db_path=authoritative_db_path,
            printer_runtime_liveness_probe=printer_runtime_liveness_probe,
            printer_host_process_inventory=printer_host_process_inventory,
        )
        or {}
    )

    staging_dir = app_root / ".staging" / f"{authorization_id}-{uuid.uuid4().hex}"
    staging_active = False
    canonical_created = False
    try:
        staging_dir.mkdir(parents=True, exist_ok=False)
        staging_active = True
        staging_manifest = staging_dir / "git-provenance-manifest.json"
        _, manifest_bytes = build_manifest_bytes(
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
            profile=FOUR_TOKEN_STANDARD_FOUR_HOUR_AUTHORIZATION_PROFILE,
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
        _require(
            _sha256_file(manifest_path) == manifest_sha256,
            "published manifest SHA-256 mismatch",
        )
    except Exception as original:
        if staging_active:
            secondary = _cleanup_pre_marker_staging(staging_dir)
            if secondary is not None:
                _attach_secondary_cleanup_blocker(
                    original,
                    field="secondary_staging_cleanup_blocker",
                    message=secondary,
                )
        if canonical_created:
            secondary = _cleanup_invocation_empty_canonical(canonical_dir)
            if secondary is not None:
                _attach_secondary_cleanup_blocker(
                    original,
                    field="secondary_canonical_cleanup_blocker",
                    message=secondary,
                )
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
            profile=FOUR_TOKEN_STANDARD_FOUR_HOUR_AUTHORIZATION_PROFILE,
        )
        _require(
            _prepared_matches_validated(prepared, validated),
            "pre-marker and complete validation disagree",
        )
        _write_exclusive(stdout_path, b"")
        _write_exclusive(stderr_path, b"")
        child_env = dict(parent)
        for name in BINDING_ENV_VARS:
            child_env.pop(name, None)
        child_env.pop(CHILD_TERMINAL_ENV_VAR, None)
        child_env.update(
            {
                BINDING_ENV_VARS[0]: str(manifest_path.resolve()),
                BINDING_ENV_VARS[1]: manifest_sha256,
                BINDING_ENV_VARS[2]: str(marker_path.resolve()),
                BINDING_ENV_VARS[3]: marker_sha256,
                CHILD_TERMINAL_ENV_VAR: str(child_terminal_path.resolve()),
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
            "zero_state_gate": zero_state_evidence,
            "operational_policy": exact_operational_policy(),
            "automatic_retries": 0,
            "manual_reruns": 0,
            "resumes": 0,
            "restarts": 0,
            "successors": 0,
            "parent_environment_mutated": False,
            "terminal_classification": (
                ("CHILD_EXITED_ZERO" if returncode == 0 else "CHILD_EXITED_NONZERO")
                if child_envelope is not None
                else (
                    "CHILD_EXITED_ZERO_TERMINAL_INVALID"
                    if returncode == 0
                    else "CHILD_EXITED_NONZERO_TERMINAL_INVALID"
                )
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
                "marker_sha256": (
                    _sha256_file(marker_path) if marker_path.is_file() else None
                ),
                "repository_branch": prepared.repository_branch,
                "repository_head": prepared.repository_head,
                "wrapper_execution_id": canonical_dir.name,
                "child_command": child_command,
                "child_start_attempted": child_attempted,
                "child_exit_code": None,
                "process_start_error": f"{type(exc).__name__}:{exc}",
                "started_at": started_at,
                "ended_at": _utc_now(),
                "zero_state_gate": zero_state_evidence,
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


__all__ = [
    "APPLICATION_ROOT",
    "AUTHORIZED_COMMAND_MODE",
    "FINAL_AUTHORIZATION_SCHEMA_VERSION",
    "FOUR_TOKEN_STANDARD_FOUR_HOUR_MODE",
    "FourTokenStandardFourHourOneShotWrapperError",
    "LIFECYCLE_REQUESTS_PER_TOKEN",
    "LIFECYCLE_REQUEST_OUTER_CEILING",
    "LIFECYCLE_SCHEDULER_OUTER_CEILING",
    "MAX_ONE_SHOT_WALL_ENVELOPE_SECONDS",
    "POLICY_VERSION",
    "POST_SUPPLY_LIFECYCLE_DURATION_SECONDS",
    "PRE_LIFECYCLE_ACQUISITION_DURATION_SECONDS",
    "WRAPPER_SCHEMA_VERSION",
    "apply_authorization_once",
    "build_child_command",
    "build_manifest_bytes",
    "build_marker_bytes",
    "exact_operational_policy",
    "fixture_authorization_document",
    "validate_four_token_standard_four_hour_authorization_document",
]
