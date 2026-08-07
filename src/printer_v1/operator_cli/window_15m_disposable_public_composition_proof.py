"""Checkpoint 8 disposable public-composition proof identity contracts.

This module contains proof-only immutable identities. It creates no campaign,
performs no source/provider work, owns no Scheduler behavior, and cannot target
the canonical production database. Production authorization remains owned by
the existing one-shot authorization path.
"""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
from pathlib import Path
import re
from typing import Any, Iterable, Sequence

from printer_v1.db.migrate import canonical_migration_count, canonical_migration_names
from printer_v1.operator_cli.window_15m_concrete_composition import (
    ordinary_window_15m_builder_identities,
)


PROOF_SCHEMA_VERSION = "WINDOW_15M_DISPOSABLE_PUBLIC_COMPOSITION_PROOF_V1"
BINDING_SCHEMA_VERSION = "WINDOW_15M_DISPOSABLE_PUBLIC_COMPOSITION_BINDING_V1"
_SHA256 = re.compile(r"^[0-9a-f]{64}$")
_SAFE_ID = re.compile(r"^[A-Za-z0-9_.-]+$")


class DisposablePublicCompositionProofError(ValueError):
    """Fail-closed proof capability validation fault."""


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _labels_sha256(labels: Sequence[str]) -> str:
    payload = json.dumps(
        list(labels),
        ensure_ascii=True,
        separators=(",", ":"),
        sort_keys=False,
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def _require_sha256(value: Any, *, label: str) -> str:
    text = str(value or "")
    if _SHA256.fullmatch(text) is None:
        raise DisposablePublicCompositionProofError(f"{label}_INVALID")
    return text


def _require_false(value: Any, *, label: str) -> bool:
    if value is not False:
        raise DisposablePublicCompositionProofError(f"{label}_MUST_BE_FALSE")
    return False


def _require_exact_registry(labels: Iterable[str]) -> tuple[str, ...]:
    observed = tuple(str(item) for item in labels)
    expected = tuple(ordinary_window_15m_builder_identities())
    if observed != expected:
        raise DisposablePublicCompositionProofError(
            "FIXTURE_COMPOSITION_REGISTRY_IDENTITY_MISMATCH"
        )
    return observed


@dataclass(frozen=True)
class DisposablePublicCompositionProofPlan:
    proof_schema_version: str
    proof_id: str
    resolved_db_path: str
    pre_mutation_db_sha256: str
    migration_count: int
    migration_head: str
    resolved_artifact_root: str
    composition_labels: tuple[str, ...]
    composition_registry_sha256: str
    provider_execution_allowed: bool
    automatic_retry_allowed: bool
    manual_rerun_allowed: bool
    resume_allowed: bool
    restart_allowed: bool
    successor_allowed: bool


@dataclass(frozen=True)
class Window15MFixtureComposition:
    """Exact offline implementation map for the ordinary 15m registry."""

    labels: tuple[str, ...]
    builders: dict[str, Any]
    fixture_composition_manifest_sha256: str
    provider_fallback_allowed: bool = False


@dataclass(frozen=True)
class DisposablePublicCompositionProofBinding:
    binding_schema_version: str
    proof_schema_version: str
    proof_id: str
    resolved_db_path: str
    pre_mutation_db_sha256: str
    migration_count: int
    migration_head: str
    composition_registry_sha256: str
    provider_execution_allowed: bool
    automatic_retry_allowed: bool
    manual_rerun_allowed: bool
    resume_allowed: bool
    restart_allowed: bool
    successor_allowed: bool
    execution_id: str
    campaign_id: str
    campaign_run_id: str
    cycle_id: str
    configuration_id: str
    db_target_identity: str
    fixture_composition_manifest_sha256: str


def mark_checkpoint8_fixture_builder(
    builder: Any,
    *,
    label: str,
) -> Any:
    """Mark one callable as an explicit C8 zero-provider fixture builder."""
    if not callable(builder):
        raise DisposablePublicCompositionProofError(
            f"FIXTURE_BUILDER_NOT_CALLABLE:{label}"
        )
    expected_label = str(label or "").strip()
    if not expected_label:
        raise DisposablePublicCompositionProofError("FIXTURE_BUILDER_LABEL_MISSING")
    setattr(builder, "_printer_checkpoint8_fixture_builder", True)
    setattr(builder, "_printer_checkpoint8_fixture_label", expected_label)
    return builder


def _fixture_manifest_sha256(labels: Sequence[str]) -> str:
    payload = {
        "proof_schema_version": PROOF_SCHEMA_VERSION,
        "labels": list(labels),
        "provider_fallback_allowed": False,
    }
    return hashlib.sha256(
        json.dumps(
            payload,
            ensure_ascii=True,
            separators=(",", ":"),
            sort_keys=True,
        ).encode("utf-8")
    ).hexdigest()


def build_window_15m_fixture_composition(
    builders: Any,
) -> Window15MFixtureComposition:
    """Build one exact full-registry fixture map with no production fallback."""
    if not hasattr(builders, "keys"):
        raise DisposablePublicCompositionProofError(
            "FIXTURE_COMPOSITION_REGISTRY_IDENTITY_MISMATCH"
        )
    expected = tuple(ordinary_window_15m_builder_identities())
    observed = tuple(str(label) for label in builders.keys())
    if observed != expected:
        raise DisposablePublicCompositionProofError(
            "FIXTURE_COMPOSITION_REGISTRY_IDENTITY_MISMATCH"
        )

    normalized: dict[str, Any] = {}
    for label in expected:
        builder = builders[label]
        if (
            not callable(builder)
            or getattr(builder, "_printer_checkpoint8_fixture_builder", False)
            is not True
            or str(getattr(builder, "_printer_checkpoint8_fixture_label", ""))
            != label
        ):
            raise DisposablePublicCompositionProofError(
                f"FIXTURE_BUILDER_NOT_EXPLICIT:{label}"
            )
        normalized[label] = builder

    return Window15MFixtureComposition(
        labels=expected,
        builders=normalized,
        fixture_composition_manifest_sha256=_fixture_manifest_sha256(expected),
        provider_fallback_allowed=False,
    )


def validate_window_15m_fixture_composition(
    composition: Window15MFixtureComposition,
    *,
    expected_labels: Iterable[str],
) -> Window15MFixtureComposition:
    """Validate exact fixture coverage without invoking a single builder."""
    if not isinstance(composition, Window15MFixtureComposition):
        raise DisposablePublicCompositionProofError(
            "FIXTURE_COMPOSITION_TYPE_INVALID"
        )
    expected = tuple(str(label) for label in expected_labels)
    canonical = tuple(ordinary_window_15m_builder_identities())
    if expected != canonical or composition.labels != canonical:
        raise DisposablePublicCompositionProofError(
            "FIXTURE_COMPOSITION_REGISTRY_IDENTITY_MISMATCH"
        )
    if tuple(composition.builders.keys()) != canonical:
        raise DisposablePublicCompositionProofError(
            "FIXTURE_COMPOSITION_REGISTRY_IDENTITY_MISMATCH"
        )
    if composition.provider_fallback_allowed is not False:
        raise DisposablePublicCompositionProofError(
            "FIXTURE_PROVIDER_FALLBACK_FORBIDDEN"
        )
    if composition.fixture_composition_manifest_sha256 != _fixture_manifest_sha256(canonical):
        raise DisposablePublicCompositionProofError(
            "FIXTURE_COMPOSITION_MANIFEST_MISMATCH"
        )
    for label in canonical:
        builder = composition.builders[label]
        if (
            not callable(builder)
            or getattr(builder, "_printer_checkpoint8_fixture_builder", False)
            is not True
            or str(getattr(builder, "_printer_checkpoint8_fixture_label", ""))
            != label
        ):
            raise DisposablePublicCompositionProofError(
                f"FIXTURE_BUILDER_NOT_EXPLICIT:{label}"
            )
    return composition


def build_disposable_public_composition_proof_plan(
    *,
    proof_id: str,
    db_path: str | Path,
    db_sha256: str,
    migration_count: int,
    migration_head: str,
    artifact_root: str | Path,
    composition_labels: Iterable[str],
    provider_execution_allowed: bool,
    automatic_retry_allowed: bool,
    manual_rerun_allowed: bool,
    resume_allowed: bool,
    restart_allowed: bool,
    successor_allowed: bool,
) -> DisposablePublicCompositionProofPlan:
    proof_text = str(proof_id or "")
    if _SAFE_ID.fullmatch(proof_text) is None:
        raise DisposablePublicCompositionProofError("PROOF_ID_INVALID")

    path = Path(db_path).expanduser().resolve()
    if not path.is_file():
        raise DisposablePublicCompositionProofError("DISPOSABLE_DB_MISSING")
    digest = _require_sha256(db_sha256, label="DISPOSABLE_DB_SHA256")
    if _sha256_file(path) != digest:
        raise DisposablePublicCompositionProofError("DISPOSABLE_DB_SHA256_MISMATCH")

    count = int(migration_count)
    head = str(migration_head or "")
    if count != canonical_migration_count() or head != canonical_migration_names()[-1]:
        raise DisposablePublicCompositionProofError(
            "DISPOSABLE_DB_MIGRATION_IDENTITY_MISMATCH"
        )

    labels = _require_exact_registry(composition_labels)
    _require_false(provider_execution_allowed, label="PROVIDER_EXECUTION_ALLOWED")
    _require_false(automatic_retry_allowed, label="AUTOMATIC_RETRY_ALLOWED")
    _require_false(manual_rerun_allowed, label="MANUAL_RERUN_ALLOWED")
    _require_false(resume_allowed, label="RESUME_ALLOWED")
    _require_false(restart_allowed, label="RESTART_ALLOWED")
    _require_false(successor_allowed, label="SUCCESSOR_ALLOWED")

    return DisposablePublicCompositionProofPlan(
        proof_schema_version=PROOF_SCHEMA_VERSION,
        proof_id=proof_text,
        resolved_db_path=str(path),
        pre_mutation_db_sha256=digest,
        migration_count=count,
        migration_head=head,
        resolved_artifact_root=str(Path(artifact_root).expanduser().resolve()),
        composition_labels=labels,
        composition_registry_sha256=_labels_sha256(labels),
        provider_execution_allowed=False,
        automatic_retry_allowed=False,
        manual_rerun_allowed=False,
        resume_allowed=False,
        restart_allowed=False,
        successor_allowed=False,
    )


def validate_disposable_public_composition_proof_plan(
    plan: DisposablePublicCompositionProofPlan,
    *,
    canonical_db_path: str | Path,
    expected_composition_labels: Iterable[str],
) -> DisposablePublicCompositionProofPlan:
    if not isinstance(plan, DisposablePublicCompositionProofPlan):
        raise DisposablePublicCompositionProofError("PROOF_PLAN_TYPE_INVALID")
    if plan.proof_schema_version != PROOF_SCHEMA_VERSION:
        raise DisposablePublicCompositionProofError("PROOF_SCHEMA_UNSUPPORTED")

    db_path = Path(plan.resolved_db_path).resolve()
    if db_path == Path(canonical_db_path).resolve():
        raise DisposablePublicCompositionProofError("CANONICAL_PRODUCTION_DB_FORBIDDEN")
    if not db_path.is_file():
        raise DisposablePublicCompositionProofError("DISPOSABLE_DB_MISSING")
    if _sha256_file(db_path) != plan.pre_mutation_db_sha256:
        raise DisposablePublicCompositionProofError("DISPOSABLE_DB_SHA256_MISMATCH")
    if (
        plan.migration_count != canonical_migration_count()
        or plan.migration_head != canonical_migration_names()[-1]
    ):
        raise DisposablePublicCompositionProofError(
            "DISPOSABLE_DB_MIGRATION_IDENTITY_MISMATCH"
        )

    expected = tuple(str(item) for item in expected_composition_labels)
    if plan.composition_labels != expected:
        raise DisposablePublicCompositionProofError(
            "FIXTURE_COMPOSITION_REGISTRY_IDENTITY_MISMATCH"
        )
    if plan.composition_registry_sha256 != _labels_sha256(expected):
        raise DisposablePublicCompositionProofError(
            "FIXTURE_COMPOSITION_REGISTRY_HASH_MISMATCH"
        )

    for field_name in (
        "provider_execution_allowed",
        "automatic_retry_allowed",
        "manual_rerun_allowed",
        "resume_allowed",
        "restart_allowed",
        "successor_allowed",
    ):
        _require_false(getattr(plan, field_name), label=field_name.upper())
    return plan


def build_disposable_public_composition_proof_binding(
    plan: DisposablePublicCompositionProofPlan,
    *,
    execution_id: str,
    campaign_id: str,
    campaign_run_id: str,
    cycle_id: str,
    configuration_id: str,
    db_target_identity: str,
    fixture_composition_manifest_sha256: str,
) -> DisposablePublicCompositionProofBinding:
    manifest_sha = _require_sha256(
        fixture_composition_manifest_sha256,
        label="FIXTURE_COMPOSITION_MANIFEST_SHA256",
    )
    expected_target = f"sha256:{plan.pre_mutation_db_sha256}"
    if str(db_target_identity) != expected_target:
        raise DisposablePublicCompositionProofError("DB_TARGET_IDENTITY_MISMATCH")
    identities = {
        "execution_id": execution_id,
        "campaign_id": campaign_id,
        "campaign_run_id": campaign_run_id,
        "cycle_id": cycle_id,
        "configuration_id": configuration_id,
    }
    if any(not str(value or "").strip() for value in identities.values()):
        raise DisposablePublicCompositionProofError("PROOF_OWNERSHIP_IDENTITY_MISSING")
    return DisposablePublicCompositionProofBinding(
        binding_schema_version=BINDING_SCHEMA_VERSION,
        proof_schema_version=plan.proof_schema_version,
        proof_id=plan.proof_id,
        resolved_db_path=plan.resolved_db_path,
        pre_mutation_db_sha256=plan.pre_mutation_db_sha256,
        migration_count=plan.migration_count,
        migration_head=plan.migration_head,
        composition_registry_sha256=plan.composition_registry_sha256,
        provider_execution_allowed=plan.provider_execution_allowed,
        automatic_retry_allowed=plan.automatic_retry_allowed,
        manual_rerun_allowed=plan.manual_rerun_allowed,
        resume_allowed=plan.resume_allowed,
        restart_allowed=plan.restart_allowed,
        successor_allowed=plan.successor_allowed,
        execution_id=str(execution_id),
        campaign_id=str(campaign_id),
        campaign_run_id=str(campaign_run_id),
        cycle_id=str(cycle_id),
        configuration_id=str(configuration_id),
        db_target_identity=expected_target,
        fixture_composition_manifest_sha256=manifest_sha,
    )


def validate_disposable_public_composition_proof_binding(
    binding: DisposablePublicCompositionProofBinding,
    *,
    actual_db_path: str | Path,
    canonical_db_path: str | Path,
    expected_plan: DisposablePublicCompositionProofPlan,
) -> str | None:
    if not isinstance(binding, DisposablePublicCompositionProofBinding):
        return "DISPOSABLE_PROOF_BINDING_TYPE_INVALID"
    if binding.binding_schema_version != BINDING_SCHEMA_VERSION:
        return "DISPOSABLE_PROOF_BINDING_VERSION_UNSUPPORTED"
    actual = Path(actual_db_path).resolve()
    bound = Path(binding.resolved_db_path).resolve()
    canonical = Path(canonical_db_path).resolve()
    if actual == canonical or bound == canonical:
        return "DISPOSABLE_PROOF_CANONICAL_DB_FORBIDDEN"
    if actual != bound or bound != Path(expected_plan.resolved_db_path).resolve():
        return "DISPOSABLE_PROOF_DB_PATH_MISMATCH"
    if not actual.is_file():
        return "DISPOSABLE_PROOF_DB_MISSING"
    if _sha256_file(actual) != binding.pre_mutation_db_sha256:
        return "DISPOSABLE_PROOF_DB_SHA256_MISMATCH"
    if binding.pre_mutation_db_sha256 != expected_plan.pre_mutation_db_sha256:
        return "DISPOSABLE_PROOF_DB_SHA256_MISMATCH"
    if (
        binding.migration_count != expected_plan.migration_count
        or binding.migration_head != expected_plan.migration_head
    ):
        return "DISPOSABLE_PROOF_MIGRATION_IDENTITY_MISMATCH"
    if binding.proof_id != expected_plan.proof_id:
        return "DISPOSABLE_PROOF_IDENTITY_MISMATCH"
    if binding.composition_registry_sha256 != expected_plan.composition_registry_sha256:
        return "DISPOSABLE_PROOF_COMPOSITION_IDENTITY_MISMATCH"
    if binding.db_target_identity != f"sha256:{binding.pre_mutation_db_sha256}":
        return "DISPOSABLE_PROOF_DB_TARGET_IDENTITY_MISMATCH"
    for field_name in (
        "provider_execution_allowed",
        "automatic_retry_allowed",
        "manual_rerun_allowed",
        "resume_allowed",
        "restart_allowed",
        "successor_allowed",
    ):
        if getattr(binding, field_name) is not False:
            return "DISPOSABLE_PROOF_REUSE_OR_PROVIDER_POLICY_MISMATCH"
    return None


__all__ = [
    "BINDING_SCHEMA_VERSION",
    "DisposablePublicCompositionProofBinding",
    "DisposablePublicCompositionProofError",
    "DisposablePublicCompositionProofPlan",
    "PROOF_SCHEMA_VERSION",
    "Window15MFixtureComposition",
    "build_disposable_public_composition_proof_binding",
    "build_disposable_public_composition_proof_plan",
    "build_window_15m_fixture_composition",
    "mark_checkpoint8_fixture_builder",
    "validate_disposable_public_composition_proof_binding",
    "validate_disposable_public_composition_proof_plan",
    "validate_window_15m_fixture_composition",
]
