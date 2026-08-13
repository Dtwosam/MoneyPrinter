"""One-use application owner for one authorized four-token bounded-capacity proof.

This wrapper is a dedicated proof-only authority. It reuses the hardened ordinary
one-shot filesystem/interpreter primitives but owns a distinct authorization
profile, manifest schema, command mode, application namespace, and child-terminal
mode. It never widens the public two-token ``standard-four-hour-run`` wrapper into
four-token authority, never authorizes 12h/24h, and never creates a second factory
runner or event loop.

Capacity is projected from ``scaled_standard_four_hour_capacity_contract(4)`` so
this module owns no independent numeric request/Scheduler authority.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
import json
import os
from pathlib import Path, PurePosixPath
import re
from typing import Any, Mapping, Sequence

from printer_v1.operator_cli.authorization_temporal_validity import (
    AuthorizationTemporalError,
    validate_authorization_temporal_validity,
)
from printer_v1.operator_cli.git_provenance_authorization_manifest import (
    FOUR_TOKEN_PROOF_AUTHORIZATION_PROFILE,
    enumerate_historical_authorization_evidence,
    extract_approved_historical_authorization_ids,
    validate_prior_authorizations_non_reusable,
)
from printer_v1.operator_cli.multi_cycle_memory_growth import (
    scaled_standard_four_hour_capacity_contract,
)
from printer_v1.operator_cli.window_15m_one_shot_wrapper import (
    OneShotWrapperError,
    _canonical_json_bytes,
    _enumerate_package,
    _sha256_file,
)


WRAPPER_SCHEMA_VERSION = "PRINTER_V1_FOUR_TOKEN_PROOF_ONE_SHOT_WRAPPER_V1"
FINAL_AUTHORIZATION_SCHEMA_VERSION = (
    "PRINTER_V1_FOUR_TOKEN_PROOF_FINAL_AUTHORIZATION_V1"
)
AUTHORIZED_COMMAND_MODE = FOUR_TOKEN_PROOF_AUTHORIZATION_PROFILE.command_mode
POLICY_VERSION = "V2-9.8B-FOUR-TOKEN-BOUNDED-CAPACITY-PROOF-V1"

# The two bounded clocks stay separate. The derived wall envelope below is
# supervision/diagnostic only and never replaces either contract.
PRE_LIFECYCLE_ACQUISITION_DURATION_SECONDS = 900
POST_SUPPLY_PROOF_DURATION_SECONDS = 18_000
MAX_ONE_SHOT_WALL_ENVELOPE_SECONDS = (
    PRE_LIFECYCLE_ACQUISITION_DURATION_SECONDS + POST_SUPPLY_PROOF_DURATION_SECONDS
)

ROOT_MAIN_WINDOW = "WINDOW_15M"
LOCKED_WINDOWS = ("WINDOW_12H", "WINDOW_24H")

# One derived numeric authority for the whole proof lane.
_PROOF_CAPACITY = scaled_standard_four_hour_capacity_contract(4)
CONFIGURED_THROUGH_4H_TOKENS = int(_PROOF_CAPACITY["configured_through_4h_tokens"])
CONFIGURED_ACTIVE_CYCLES = int(_PROOF_CAPACITY["configured_active_cycles"])
TOTAL_CYCLE_ADMISSION_CEILING = CONFIGURED_ACTIVE_CYCLES
TOKENS_PER_CYCLE = int(_PROOF_CAPACITY["tokens_per_cycle"])
MINIMUM_CYCLE_ADMISSION_SPACING_SECONDS = int(
    _PROOF_CAPACITY["minimum_cycle_admission_spacing_seconds"]
)
SHARED_DISCOVERY_REQUESTS = int(_PROOF_CAPACITY["shared_discovery_requests"])
LIFECYCLE_REQUEST_OUTER_CEILING = int(
    _PROOF_CAPACITY["lifecycle_request_outer_ceiling"]
)
LIFECYCLE_REQUESTS_PER_TOKEN = int(_PROOF_CAPACITY["lifecycle_requests_per_token"])
LIFECYCLE_SCHEDULER_OUTER_CEILING = int(
    _PROOF_CAPACITY["lifecycle_scheduler_outer_ceiling"]
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
    "proof_policy",
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


class FourTokenProofOneShotWrapperError(RuntimeError):
    """Fail-closed four-token proof wrapper/authorization fault."""


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise FourTokenProofOneShotWrapperError(message)


def _safe_identifier(value: Any, *, label: str) -> str:
    _require(
        type(value) is str and bool(value) and _SAFE_ID.fullmatch(value) is not None,
        f"{label} is malformed",
    )
    return str(value)


def exact_proof_policy() -> dict[str, Any]:
    """Return the one exact 4/2/2 proof policy this authority may ever bind."""
    return {
        "policy_version": POLICY_VERSION,
        "configured_through_4h_tokens": CONFIGURED_THROUGH_4H_TOKENS,
        "configured_active_cycles": CONFIGURED_ACTIVE_CYCLES,
        "total_cycle_admission_ceiling": TOTAL_CYCLE_ADMISSION_CEILING,
        "tokens_per_cycle": TOKENS_PER_CYCLE,
        "minimum_cycle_admission_spacing_seconds": (
            MINIMUM_CYCLE_ADMISSION_SPACING_SECONDS
        ),
        "standard_four_hour_campaign": True,
        "root_main_window": ROOT_MAIN_WINDOW,
        "pre_lifecycle_acquisition_duration_seconds": (
            PRE_LIFECYCLE_ACQUISITION_DURATION_SECONDS
        ),
        "post_supply_proof_duration_seconds": POST_SUPPLY_PROOF_DURATION_SECONDS,
        "shared_discovery_requests": SHARED_DISCOVERY_REQUESTS,
        "lifecycle_request_outer_ceiling": LIFECYCLE_REQUEST_OUTER_CEILING,
        "lifecycle_requests_per_token": LIFECYCLE_REQUESTS_PER_TOKEN,
        "lifecycle_scheduler_outer_ceiling": LIFECYCLE_SCHEDULER_OUTER_CEILING,
        "automatic_retries": 0,
        "endpoint_rotation": False,
        "long_windows_activated": False,
        "locked_windows": list(LOCKED_WINDOWS),
    }


def fixture_authorization_document(
    *,
    branch: str,
    head: str,
    database: Mapping[str, Any],
    authorization_id: str = "FIXTURE_FOUR_TOKEN_PROOF_AUTHORIZATION",
    migration_execution_id: str = "FIXTURE_MIGRATION_055",
    verdict: str = "V2_9_8B_FOUR_TOKEN_PROOF_FINAL_AUTHORIZATION_PASS",
    authorized_at: str | None = None,
    expires_at: str | None = None,
    validity_seconds: int = 43_200,
    prior_authorizations_non_reusable: Sequence[str] = (),
) -> dict[str, Any]:
    """Build one offline fixture-shaped proof document. This creates no authority."""
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
        "proof_policy": exact_proof_policy(),
        "authoritative_database": dict(database),
        "prior_authorizations_non_reusable": list(prior_authorizations_non_reusable),
    }


def validate_four_token_proof_authorization_document(
    document: Mapping[str, Any],
) -> dict[str, Any]:
    """Validate one four-token proof authorization document and fail closed."""
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
        raise FourTokenProofOneShotWrapperError(
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
    proof_policy = document.get("proof_policy")
    _require(isinstance(proof_policy, Mapping), "proof policy is malformed")
    expected_policy = exact_proof_policy()
    _require(
        set(proof_policy) == set(expected_policy),
        "proof policy keys are malformed",
    )
    # Exact equality against the one derived authority. A widened capacity, a
    # third cycle, a single-token cycle, shorter spacing, a collapsed or widened
    # clock, a copied two-token ceiling, a retry, endpoint rotation, or a long
    # window all fail closed here rather than reaching consumption.
    for key, expected in expected_policy.items():
        actual = proof_policy.get(key)
        _require(
            type(actual) is type(expected) and actual == expected,
            f"proof policy {key} mismatch",
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
    """Resolve one proof authorization inside its exact package, without aliases."""
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
        raise FourTokenProofOneShotWrapperError(
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
        raise FourTokenProofOneShotWrapperError(
            "final authorization is unreadable or malformed"
        ) from exc
    validated = validate_four_token_proof_authorization_document(document)
    authorization_id = _safe_identifier(
        validated["authorization_id"], label="authorization_id"
    )
    migration_execution_id = _safe_identifier(
        validated["migration_execution_id"], label="migration_execution_id"
    )
    expected_relative = (
        f"{FOUR_TOKEN_PROOF_AUTHORIZATION_PROFILE.authorization_package_root}/"
        f"{authorization_id}/final_authorization.json"
    )
    _require(
        relative == expected_relative,
        "authorization file is outside its exact four-token proof package",
    )
    return canonical_candidate, validated, authorization_id, migration_execution_id


def build_manifest_bytes(
    *,
    repository_root: str | Path,
    authorization_file: str | Path,
    authorization_sha256: str,
    created_at: str | None = None,
) -> tuple[dict[str, Any], bytes]:
    """Bind the exact migration-055 and four-token authorization packages only."""
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
    profile = FOUR_TOKEN_PROOF_AUTHORIZATION_PROFILE
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
        raise FourTokenProofOneShotWrapperError(
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
    }
    return payload, _canonical_json_bytes(payload)


__all__ = [
    "AUTHORIZED_COMMAND_MODE",
    "build_manifest_bytes",
    "FINAL_AUTHORIZATION_SCHEMA_VERSION",
    "FourTokenProofOneShotWrapperError",
    "LIFECYCLE_REQUEST_OUTER_CEILING",
    "LIFECYCLE_SCHEDULER_OUTER_CEILING",
    "MAX_ONE_SHOT_WALL_ENVELOPE_SECONDS",
    "POLICY_VERSION",
    "POST_SUPPLY_PROOF_DURATION_SECONDS",
    "PRE_LIFECYCLE_ACQUISITION_DURATION_SECONDS",
    "WRAPPER_SCHEMA_VERSION",
    "exact_proof_policy",
    "fixture_authorization_document",
    "validate_four_token_proof_authorization_document",
]
