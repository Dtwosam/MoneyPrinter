"""Immutable operational database authorization passed through the live stack."""

from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
import sqlite3
from typing import Any, Mapping

from printer_v1.db.migrate import (
    canonical_migration_count,
    canonical_migration_names,
)


PRODUCTION_AUTHORITATIVE = "PRODUCTION_AUTHORITATIVE"
AUTHORIZED_DISPOSABLE_OPERATIONAL_PROOF = (
    "AUTHORIZED_DISPOSABLE_OPERATIONAL_PROOF"
)
DISPOSABLE_PUBLIC_COMPOSITION_PROOF = (
    "DISPOSABLE_PUBLIC_COMPOSITION_PROOF"
)
DISPOSABLE_PUBLIC_COMPOSITION_PROOF_EXPECTATION_VERSION = (
    "DISPOSABLE_PUBLIC_COMPOSITION_PROOF_EXPECTATION_V1"
)
ALLOWED_OPERATIONAL_DATABASE_TARGET_KINDS = frozenset(
    {PRODUCTION_AUTHORITATIVE, AUTHORIZED_DISPOSABLE_OPERATIONAL_PROOF}
)
OPERATIONAL_DATABASE_TARGET_BINDING_VERSION = (
    "OPERATIONAL_DATABASE_TARGET_BINDING_V1"
)


def build_durable_operational_database_target_expectation(**values: Any) -> dict[str, Any]:
    """Build the configuration-owned facts used to validate a later binding."""
    normalized = dict(values)
    if "manifest_sha256" in normalized:
        normalized["authorization_marker_sha256"] = normalized.pop(
            "manifest_sha256"
        )
    if "resolved_db_path" in normalized:
        normalized["resolved_db_path"] = str(
            Path(normalized["resolved_db_path"]).resolve()
        )
    normalized["expectation_version"] = (
        "OPERATIONAL_DATABASE_TARGET_EXPECTATION_V1"
    )
    return normalized


def validated_authorization_runtime_facts(authorization: Any | None) -> dict[str, Any]:
    """Project real validated manifest/marker facts or fail before binding."""
    if authorization is None:
        raise ValueError("VALIDATED_AUTHORIZATION_REQUIRED")
    if not str(getattr(authorization, "authorization_id", "")):
        raise ValueError("VALIDATED_AUTHORIZATION_ID_REQUIRED")
    if not str(getattr(authorization, "manifest_sha256", "")):
        raise ValueError("AUTHORIZATION_MANIFEST_REQUIRED")
    if not str(getattr(authorization, "marker_sha256", "")):
        raise ValueError("APPLICATION_MARKER_REQUIRED")
    authorized_database = getattr(authorization, "authoritative_database", None)
    if not isinstance(authorized_database, Mapping):
        raise ValueError("AUTHORIZED_DATABASE_BINDING_REQUIRED")
    required_database_fields = (
        "path",
        "sha256",
        "migration_count",
        "migration_head",
    )
    if any(
        authorized_database.get(field) in (None, "")
        for field in required_database_fields
    ):
        raise ValueError("AUTHORIZED_DATABASE_BINDING_REQUIRED")
    if getattr(authorization, "authorization_consumed_once", None) is not True:
        raise ValueError("AUTHORIZATION_CONSUMPTION_REQUIRED")
    for field in ("invocation_count", "allowed_invocation_count"):
        value = getattr(authorization, field, None)
        if type(value) is not int:
            raise ValueError("AUTHORIZATION_INVOCATION_FACT_REQUIRED")
    reuse_flags = (
        "automatic_retry_allowed",
        "manual_rerun_allowed",
        "resume_allowed",
        "restart_allowed",
        "successor_allowed",
    )
    if any(
        type(getattr(authorization, field, None)) is not bool
        for field in reuse_flags
    ):
        raise ValueError("AUTHORIZATION_REUSE_FACT_REQUIRED")
    return {
        "authorization_id": str(authorization.authorization_id),
        "manifest_sha256": str(authorization.manifest_sha256),
        "application_marker_sha256": str(authorization.marker_sha256),
        "authorization_consumed_once": authorization.authorization_consumed_once,
        "invocation_count": authorization.invocation_count,
        "allowed_invocation_count": authorization.allowed_invocation_count,
        "automatic_retry_allowed": getattr(
            authorization, "automatic_retry_allowed", None
        ),
        "manual_rerun_allowed": getattr(
            authorization, "manual_rerun_allowed", None
        ),
        "resume_allowed": getattr(authorization, "resume_allowed", None),
        "restart_allowed": getattr(authorization, "restart_allowed", None),
        "successor_allowed": getattr(authorization, "successor_allowed", None),
        "authorized_db_path": str(
            Path(str(authorized_database["path"])).resolve()
        ),
        "authorized_pre_mutation_sha256": str(authorized_database["sha256"]),
        "migration_count": int(authorized_database["migration_count"]),
        "migration_head": str(authorized_database["migration_head"]),
    }


def validate_authorized_database_preflight(
    authorization_facts: Mapping[str, Any],
    *,
    actual_db_path: str | Path,
    preflight: Mapping[str, Any],
) -> None:
    """Block before campaign construction unless preflight matches authorization."""
    actual = Path(actual_db_path).resolve()
    authorized = Path(str(authorization_facts["authorized_db_path"])).resolve()
    if actual != authorized:
        raise ValueError("AUTHORIZED_DATABASE_PATH_MISMATCH")
    if str(preflight.get("database_sha256") or "") != str(
        authorization_facts["authorized_pre_mutation_sha256"]
    ):
        raise ValueError("AUTHORIZED_DATABASE_SHA256_MISMATCH")
    if int(preflight.get("migration_count", canonical_migration_count())) != int(
        authorization_facts["migration_count"]
    ):
        raise ValueError("AUTHORIZED_DATABASE_MIGRATION_MISMATCH")
    observed_migration_head = str(
        preflight.get("latest_migration") or canonical_migration_names()[-1]
    )
    if observed_migration_head != str(authorization_facts["migration_head"]):
        raise ValueError("AUTHORIZED_DATABASE_MIGRATION_MISMATCH")


def load_durable_operational_database_target_expectation(
    db_path: str | Path,
    *,
    campaign_id: str,
    campaign_run_id: str,
    cycle_id: str,
    configuration_id: str,
) -> Mapping[str, Any] | None:
    """Load the configuration-owned expectation without consulting a binding."""
    connection = sqlite3.connect(Path(db_path))
    connection.row_factory = sqlite3.Row
    try:
        row = connection.execute(
            """SELECT campaign_id, configuration_json
                 FROM printer_memory_factory_campaign_configurations
                WHERE configuration_id=? AND campaign_id=?""",
            (configuration_id, campaign_id),
        ).fetchone()
    except sqlite3.Error:
        return None
    finally:
        connection.close()
    if row is None:
        return None
    try:
        configuration = json.loads(str(row["configuration_json"]))
    except (TypeError, ValueError, json.JSONDecodeError):
        return None
    expectation = configuration.get("operational_database_target_expectation")
    if not isinstance(expectation, Mapping):
        return None
    ownership = {
        "campaign_id": campaign_id,
        "campaign_run_id": campaign_run_id,
        "cycle_id": cycle_id,
        "configuration_id": configuration_id,
    }
    if any(str(expectation.get(field) or "") != value for field, value in ownership.items()):
        return None
    return dict(expectation)


@dataclass(frozen=True)
class OperationalDatabaseTargetBinding:
    binding_version: str
    target_kind: str
    resolved_db_path: str
    authorized_pre_mutation_sha256: str
    migration_count: int
    migration_head: str
    db_target_identity: str
    authorization_id: str
    authorization_marker_sha256: str
    application_marker_sha256: str
    execution_id: str
    campaign_id: str
    campaign_run_id: str
    cycle_id: str
    configuration_id: str
    authorization_consumed_once: bool
    invocation_count: int
    allowed_invocation_count: int
    automatic_retry_allowed: bool
    manual_rerun_allowed: bool
    resume_allowed: bool
    restart_allowed: bool
    successor_allowed: bool


def build_operational_database_target_binding(
    *,
    target_kind: str,
    resolved_db_path: str | Path,
    authorized_pre_mutation_sha256: str,
    migration_count: int,
    migration_head: str,
    authorization_id: str,
    authorization_marker_sha256: str,
    application_marker_sha256: str,
    execution_id: str,
    campaign_id: str,
    campaign_run_id: str,
    cycle_id: str,
    configuration_id: str,
    authorization_consumed_once: bool,
    invocation_count: int,
    allowed_invocation_count: int,
    automatic_retry_allowed: bool,
    manual_rerun_allowed: bool,
    resume_allowed: bool,
    restart_allowed: bool,
    successor_allowed: bool,
) -> OperationalDatabaseTargetBinding:
    """Coordinator-only constructor for the immutable downstream capability."""
    return OperationalDatabaseTargetBinding(
        binding_version=OPERATIONAL_DATABASE_TARGET_BINDING_VERSION,
        target_kind=target_kind,
        resolved_db_path=str(Path(resolved_db_path).resolve()),
        authorized_pre_mutation_sha256=str(authorized_pre_mutation_sha256),
        migration_count=int(migration_count),
        migration_head=str(migration_head),
        db_target_identity=f"sha256:{authorized_pre_mutation_sha256}",
        authorization_id=str(authorization_id),
        authorization_marker_sha256=str(authorization_marker_sha256),
        application_marker_sha256=str(application_marker_sha256),
        execution_id=str(execution_id),
        campaign_id=str(campaign_id),
        campaign_run_id=str(campaign_run_id),
        cycle_id=str(cycle_id),
        configuration_id=str(configuration_id),
        authorization_consumed_once=authorization_consumed_once,
        invocation_count=int(invocation_count),
        allowed_invocation_count=int(allowed_invocation_count),
        automatic_retry_allowed=automatic_retry_allowed,
        manual_rerun_allowed=manual_rerun_allowed,
        resume_allowed=resume_allowed,
        restart_allowed=restart_allowed,
        successor_allowed=successor_allowed,
    )


def validate_operational_database_target_binding(
    binding: OperationalDatabaseTargetBinding | None,
    *,
    actual_db_path: str | Path,
    canonical_authoritative_db_path: str | Path,
    expected: Mapping[str, Any],
) -> str | None:
    """Return the first categorical mismatch without reading mutable DB bytes."""
    if binding is None:
        return "OPERATIONAL_DB_BINDING_MISSING"
    if binding.binding_version != OPERATIONAL_DATABASE_TARGET_BINDING_VERSION:
        return "OPERATIONAL_DB_BINDING_VERSION_UNSUPPORTED"
    if binding.target_kind not in ALLOWED_OPERATIONAL_DATABASE_TARGET_KINDS:
        return "OPERATIONAL_DB_BINDING_KIND_INVALID"
    actual = Path(actual_db_path).resolve()
    bound = Path(binding.resolved_db_path).resolve()
    canonical = Path(canonical_authoritative_db_path).resolve()
    if actual != bound:
        return "OPERATIONAL_DB_BINDING_PATH_MISMATCH"
    if binding.target_kind == PRODUCTION_AUTHORITATIVE and bound != canonical:
        return "OPERATIONAL_DB_BINDING_PRODUCTION_PATH_MISMATCH"
    if (
        binding.target_kind == AUTHORIZED_DISPOSABLE_OPERATIONAL_PROOF
        and bound == canonical
    ):
        return "OPERATIONAL_DB_BINDING_PRODUCTION_PATH_MISMATCH"
    if (
        expected.get("target_kind") is not None
        and str(expected["target_kind"]) != binding.target_kind
    ):
        return "OPERATIONAL_DB_BINDING_AUTHORIZATION_MISMATCH"
    if expected.get("resolved_db_path") is not None and Path(
        str(expected["resolved_db_path"])
    ).resolve() != bound:
        return "OPERATIONAL_DB_BINDING_PATH_MISMATCH"

    expected_baseline = str(
        expected.get("authorized_pre_mutation_sha256") or ""
    )
    if expected_baseline and binding.authorized_pre_mutation_sha256 != expected_baseline:
        return "OPERATIONAL_DB_BINDING_BASELINE_SHA_MISMATCH"
    if binding.db_target_identity != f"sha256:{binding.authorized_pre_mutation_sha256}":
        return "OPERATIONAL_DB_BINDING_BASELINE_SHA_MISMATCH"

    if (
        expected.get("migration_count") is not None
        and int(binding.migration_count) != int(expected["migration_count"])
    ) or (
        expected.get("migration_head") is not None
        and binding.migration_head != str(expected["migration_head"])
    ):
        return "OPERATIONAL_DB_BINDING_MIGRATION_MISMATCH"

    if (
        expected.get("authorization_id") is not None
        and binding.authorization_id != str(expected["authorization_id"])
    ) or (
        expected.get("authorization_marker_sha256") is not None
        and binding.authorization_marker_sha256
        != str(expected["authorization_marker_sha256"])
    ):
        return "OPERATIONAL_DB_BINDING_AUTHORIZATION_MISMATCH"
    if (
        expected.get("application_marker_sha256") is not None
        and binding.application_marker_sha256
        != str(expected["application_marker_sha256"])
    ):
        return "OPERATIONAL_DB_BINDING_APPLICATION_MARKER_MISMATCH"

    ownership_fields = (
        "execution_id",
        "campaign_id",
        "campaign_run_id",
        "cycle_id",
        "configuration_id",
    )
    if any(
        expected.get(field) is not None
        and getattr(binding, field) != str(expected[field])
        for field in ownership_fields
    ):
        return "OPERATIONAL_DB_BINDING_OWNERSHIP_MISMATCH"
    if (
        expected.get("durable_db_target_identity") is not None
        and binding.db_target_identity
        != str(expected["durable_db_target_identity"])
    ):
        return "OPERATIONAL_DB_BINDING_OWNERSHIP_MISMATCH"

    if binding.target_kind == AUTHORIZED_DISPOSABLE_OPERATIONAL_PROOF:
        fixture = expected.get("fixture_authorization")
        if not isinstance(fixture, Mapping):
            return "OPERATIONAL_DB_BINDING_AUTHORIZATION_MISMATCH"
        fixture_path = fixture.get("resolved_db_path")
        if fixture_path is None or Path(str(fixture_path)).resolve() != bound:
            return "OPERATIONAL_DB_BINDING_AUTHORIZATION_MISMATCH"
        fixture_authorization_fields = (
            "authorized_pre_mutation_sha256",
            "authorization_id",
            "authorization_marker_sha256",
            "execution_id",
            "campaign_id",
            "campaign_run_id",
            "cycle_id",
            "configuration_id",
        )
        if any(
            fixture.get(field) is None
            or str(fixture[field]) != str(getattr(binding, field))
            for field in fixture_authorization_fields
        ):
            return "OPERATIONAL_DB_BINDING_AUTHORIZATION_MISMATCH"
        if (
            fixture.get("application_marker_sha256") is None
            or str(fixture["application_marker_sha256"])
            != binding.application_marker_sha256
        ):
            return "OPERATIONAL_DB_BINDING_APPLICATION_MARKER_MISMATCH"
        if (
            int(fixture.get("migration_count", -1)) != binding.migration_count
            or str(fixture.get("migration_head") or "") != binding.migration_head
        ):
            return "OPERATIONAL_DB_BINDING_MIGRATION_MISMATCH"
    elif expected.get("disposable_proof_identity") not in (None, ""):
        return "OPERATIONAL_DB_BINDING_AUTHORIZATION_MISMATCH"

    retry_flags = (
        "automatic_retry_allowed",
        "manual_rerun_allowed",
        "resume_allowed",
        "restart_allowed",
        "successor_allowed",
    )
    reuse_source = (
        expected.get("fixture_authorization")
        if binding.target_kind == AUTHORIZED_DISPOSABLE_OPERATIONAL_PROOF
        else expected
    )
    if (
        binding.authorization_consumed_once
        is not expected.get("authorization_consumed_once")
        or binding.invocation_count != int(expected.get("invocation_count", 0))
        or (
            expected.get("allowed_invocation_count") is not None
            and binding.allowed_invocation_count
            != int(expected["allowed_invocation_count"])
        )
        or any(
            getattr(binding, flag) is not expected.get(flag)
            for flag in retry_flags
        )
        or expected.get("authorization_consumed_once") is not True
        or int(expected.get("invocation_count", 0)) != 1
        or (
            expected.get("allowed_invocation_count") is not None
            and int(expected["allowed_invocation_count"]) != 1
        )
        or not isinstance(reuse_source, Mapping)
        or any(reuse_source.get(flag) is not False for flag in retry_flags)
        or (
            binding.target_kind == AUTHORIZED_DISPOSABLE_OPERATIONAL_PROOF
            and int(reuse_source.get("allowed_invocation_count", 0)) != 1
        )
    ):
        return "OPERATIONAL_DB_BINDING_REUSE_OR_HISTORY_MISMATCH"
    return None


def build_disposable_public_composition_proof_expectation(
    binding: Any,
) -> dict[str, Any]:
    """Build durable C8 proof truth without fabricated authorization facts."""
    required = (
        "proof_schema_version",
        "proof_id",
        "resolved_db_path",
        "pre_mutation_db_sha256",
        "migration_count",
        "migration_head",
        "composition_registry_sha256",
        "provider_execution_allowed",
        "automatic_retry_allowed",
        "manual_rerun_allowed",
        "resume_allowed",
        "restart_allowed",
        "successor_allowed",
        "execution_id",
        "campaign_id",
        "campaign_run_id",
        "cycle_id",
        "configuration_id",
        "db_target_identity",
        "fixture_composition_manifest_sha256",
    )
    if any(not hasattr(binding, field) for field in required):
        raise ValueError("DISPOSABLE_PUBLIC_COMPOSITION_PROOF_BINDING_INCOMPLETE")
    return {
        "expectation_version": DISPOSABLE_PUBLIC_COMPOSITION_PROOF_EXPECTATION_VERSION,
        "target_kind": DISPOSABLE_PUBLIC_COMPOSITION_PROOF,
        "proof_schema_version": str(binding.proof_schema_version),
        "proof_id": str(binding.proof_id),
        "resolved_db_path": str(Path(binding.resolved_db_path).resolve()),
        "pre_mutation_db_sha256": str(binding.pre_mutation_db_sha256),
        "migration_count": int(binding.migration_count),
        "migration_head": str(binding.migration_head),
        "composition_registry_sha256": str(binding.composition_registry_sha256),
        "provider_execution_allowed": binding.provider_execution_allowed,
        "automatic_retry_allowed": binding.automatic_retry_allowed,
        "manual_rerun_allowed": binding.manual_rerun_allowed,
        "resume_allowed": binding.resume_allowed,
        "restart_allowed": binding.restart_allowed,
        "successor_allowed": binding.successor_allowed,
        "execution_id": str(binding.execution_id),
        "campaign_id": str(binding.campaign_id),
        "campaign_run_id": str(binding.campaign_run_id),
        "cycle_id": str(binding.cycle_id),
        "configuration_id": str(binding.configuration_id),
        "durable_db_target_identity": str(binding.db_target_identity),
        "fixture_composition_manifest_sha256": str(binding.fixture_composition_manifest_sha256),
    }


def validate_disposable_public_composition_proof_invocation(
    binding: Any,
    *,
    expectation: Mapping[str, Any] | None,
    actual_db_path: str | Path,
    canonical_authoritative_db_path: str | Path,
    execution_id: str,
    campaign_id: str,
    campaign_run_id: str,
    cycle_id: str,
    configuration_id: str,
    durable_db_target_identity: str,
    fixture_composition_manifest_sha256: str,
) -> str | None:
    """Validate C8 proof truth without consulting authorization fields."""
    if not isinstance(expectation, Mapping):
        return "DISPOSABLE_PROOF_EXPECTATION_MISSING"
    expected = dict(expectation)
    if expected.get("expectation_version") != DISPOSABLE_PUBLIC_COMPOSITION_PROOF_EXPECTATION_VERSION:
        return "DISPOSABLE_PROOF_EXPECTATION_VERSION_MISMATCH"
    if expected.get("target_kind") != DISPOSABLE_PUBLIC_COMPOSITION_PROOF:
        return "DISPOSABLE_PROOF_TARGET_KIND_MISMATCH"
    if any(str(key).startswith("authorization") for key in expected) or "application_marker_sha256" in expected:
        return "DISPOSABLE_PROOF_AUTHORIZATION_FACT_FORBIDDEN"

    actual = Path(actual_db_path).resolve()
    canonical = Path(canonical_authoritative_db_path).resolve()
    bound_path = Path(str(getattr(binding, "resolved_db_path", ""))).resolve()
    expected_path = Path(str(expected.get("resolved_db_path") or "")).resolve()
    if actual == canonical or bound_path == canonical or expected_path == canonical:
        return "DISPOSABLE_PROOF_CANONICAL_DB_FORBIDDEN"
    if actual != bound_path or actual != expected_path:
        return "DISPOSABLE_PROOF_DB_PATH_MISMATCH"

    expected_pairs = {
        "proof_schema_version": getattr(binding, "proof_schema_version", None),
        "proof_id": getattr(binding, "proof_id", None),
        "pre_mutation_db_sha256": getattr(binding, "pre_mutation_db_sha256", None),
        "migration_count": getattr(binding, "migration_count", None),
        "migration_head": getattr(binding, "migration_head", None),
        "composition_registry_sha256": getattr(binding, "composition_registry_sha256", None),
        "execution_id": execution_id,
        "campaign_id": campaign_id,
        "campaign_run_id": campaign_run_id,
        "cycle_id": cycle_id,
        "configuration_id": configuration_id,
        "durable_db_target_identity": durable_db_target_identity,
        "fixture_composition_manifest_sha256": fixture_composition_manifest_sha256,
    }
    binding_runtime = {
        "execution_id": getattr(binding, "execution_id", None),
        "campaign_id": getattr(binding, "campaign_id", None),
        "campaign_run_id": getattr(binding, "campaign_run_id", None),
        "cycle_id": getattr(binding, "cycle_id", None),
        "configuration_id": getattr(binding, "configuration_id", None),
        "durable_db_target_identity": getattr(binding, "db_target_identity", None),
        "fixture_composition_manifest_sha256": getattr(binding, "fixture_composition_manifest_sha256", None),
    }
    for field, runtime_value in expected_pairs.items():
        if str(expected.get(field)) != str(runtime_value):
            return "DISPOSABLE_PROOF_EXPECTATION_IDENTITY_MISMATCH"
        if field in binding_runtime and str(binding_runtime[field]) != str(runtime_value):
            return "DISPOSABLE_PROOF_BINDING_OWNERSHIP_MISMATCH"

    if str(getattr(binding, "db_target_identity", "")) != f"sha256:{getattr(binding, 'pre_mutation_db_sha256', '')}":
        return "DISPOSABLE_PROOF_DB_TARGET_IDENTITY_MISMATCH"

    for field in (
        "provider_execution_allowed",
        "automatic_retry_allowed",
        "manual_rerun_allowed",
        "resume_allowed",
        "restart_allowed",
        "successor_allowed",
    ):
        if getattr(binding, field, None) is not False or expected.get(field) is not False:
            return "DISPOSABLE_PROOF_REUSE_OR_PROVIDER_POLICY_MISMATCH"
    return None


def validate_bound_operational_invocation(
    binding: OperationalDatabaseTargetBinding | None,
    *,
    actual_db_path: str | Path,
    canonical_authoritative_db_path: str | Path,
    migration_count: int | None = None,
    migration_head: str | None = None,
    execution_id: str | None = None,
    campaign_id: str | None = None,
    campaign_run_id: str | None = None,
    cycle_id: str | None = None,
    configuration_id: str | None = None,
    durable_db_target_identity: str | None = None,
    durable_expectation: Mapping[str, Any] | None = None,
) -> str | None:
    """Validate a capability only against separately loaded durable facts."""
    if binding is None:
        return "OPERATIONAL_DB_BINDING_MISSING"
    if not isinstance(durable_expectation, Mapping):
        return "OPERATIONAL_DB_BINDING_EXPECTATION_MISSING"
    expected = dict(durable_expectation)
    required = (
        "expectation_version",
        "authorized_pre_mutation_sha256",
        "migration_count",
        "migration_head",
        "durable_db_target_identity",
        "authorization_id",
        "authorization_marker_sha256",
        "application_marker_sha256",
        "execution_id",
        "campaign_id",
        "campaign_run_id",
        "cycle_id",
        "configuration_id",
        "authorization_consumed_once",
        "invocation_count",
        "allowed_invocation_count",
        "automatic_retry_allowed",
        "manual_rerun_allowed",
        "resume_allowed",
        "restart_allowed",
        "successor_allowed",
    )
    if any(field not in expected for field in required):
        return "OPERATIONAL_DB_BINDING_EXPECTATION_INCOMPLETE"
    if expected["expectation_version"] != "OPERATIONAL_DATABASE_TARGET_EXPECTATION_V1":
        return "OPERATIONAL_DB_BINDING_EXPECTATION_INCOMPLETE"
    # Runtime ownership remains independent input and may only further restrict
    # the durable configuration; it never supplies authorization facts.
    runtime_ownership = {
        "migration_count": migration_count,
        "migration_head": migration_head,
        "durable_db_target_identity": durable_db_target_identity,
        "execution_id": execution_id,
        "campaign_id": campaign_id,
        "campaign_run_id": campaign_run_id,
        "cycle_id": cycle_id,
        "configuration_id": configuration_id,
    }
    if any(
        value is not None and str(expected.get(field)) != str(value)
        for field, value in runtime_ownership.items()
    ):
        return "OPERATIONAL_DB_BINDING_OWNERSHIP_MISMATCH"
    if binding is not None and binding.target_kind == AUTHORIZED_DISPOSABLE_OPERATIONAL_PROOF:
        expected["fixture_authorization"] = dict(expected)
    return validate_operational_database_target_binding(
        binding,
        actual_db_path=actual_db_path,
        canonical_authoritative_db_path=canonical_authoritative_db_path,
        expected=expected,
    )


__all__ = [
    "ALLOWED_OPERATIONAL_DATABASE_TARGET_KINDS",
    "AUTHORIZED_DISPOSABLE_OPERATIONAL_PROOF",
    "DISPOSABLE_PUBLIC_COMPOSITION_PROOF",
    "DISPOSABLE_PUBLIC_COMPOSITION_PROOF_EXPECTATION_VERSION",
    "OperationalDatabaseTargetBinding",
    "OPERATIONAL_DATABASE_TARGET_BINDING_VERSION",
    "PRODUCTION_AUTHORITATIVE",
    "build_disposable_public_composition_proof_expectation",
    "build_operational_database_target_binding",
    "build_durable_operational_database_target_expectation",
    "load_durable_operational_database_target_expectation",
    "validated_authorization_runtime_facts",
    "validate_authorized_database_preflight",
    "validate_disposable_public_composition_proof_invocation",
    "validate_operational_database_target_binding",
    "validate_bound_operational_invocation",
]
