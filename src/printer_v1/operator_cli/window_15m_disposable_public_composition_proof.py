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
class DisposablePublicCompositionProofRuntime:
    # Validated C8 runtime capability. It owns no authorization truth.
    plan: DisposablePublicCompositionProofPlan
    fixture_composition: Window15MFixtureComposition
    fixture_composition_manifest_sha256: str


@dataclass(frozen=True)
class DisposablePublicCompositionExecutionBindings:
    # Immutable zero-I/O map from canonical labels to existing DI seams.
    registry_labels: tuple[str, ...]
    route_by_label: dict[str, str]
    top_level_transport_labels: dict[str, str]
    unmapped_labels: tuple[str, ...]
    fixture_composition_manifest_sha256: str
    provider_fallback_allowed: bool = False


@dataclass(frozen=True)
class DisposablePublicCompositionMaterializedExecution:
    # Explicit fixture-built values routed only through existing DI seams.
    outputs_by_label: dict[str, Any]
    top_level_transports: dict[str, Any]
    graduated_supply_kwargs: dict[str, Any]
    lifecycle_kwargs: dict[str, Any]
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


def mark_checkpoint8_fixture_output(
    output: Any,
    *,
    label: str,
) -> Any:
    # Mark a built C8 value explicitly while preserving object identity.
    expected_label = str(label or "").strip()
    if not expected_label:
        raise DisposablePublicCompositionProofError(
            "FIXTURE_OUTPUT_LABEL_MISSING"
        )
    if output is None:
        raise DisposablePublicCompositionProofError(
            f"FIXTURE_OUTPUT_NOT_EXPLICIT:{expected_label}"
        )
    try:
        labels = set(
            getattr(output, "_printer_checkpoint8_fixture_output_labels", ())
        )
        labels.add(expected_label)
        setattr(output, "_printer_checkpoint8_fixture_output", True)
        setattr(
            output,
            "_printer_checkpoint8_fixture_output_labels",
            frozenset(labels),
        )
    except Exception as exc:
        raise DisposablePublicCompositionProofError(
            f"FIXTURE_OUTPUT_NOT_MARKABLE:{expected_label}"
        ) from exc
    return output


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


def build_disposable_public_composition_proof_runtime(
    plan: DisposablePublicCompositionProofPlan,
    fixture_composition: Window15MFixtureComposition,
    *,
    canonical_db_path: str | Path,
) -> DisposablePublicCompositionProofRuntime:
    # Bind the validated plan to the exact zero-provider fixture registry.
    validated_plan = validate_disposable_public_composition_proof_plan(
        plan,
        canonical_db_path=canonical_db_path,
        expected_composition_labels=ordinary_window_15m_builder_identities(),
    )
    validated_composition = validate_window_15m_fixture_composition(
        fixture_composition,
        expected_labels=ordinary_window_15m_builder_identities(),
    )
    if validated_plan.composition_labels != validated_composition.labels:
        raise DisposablePublicCompositionProofError(
            "FIXTURE_COMPOSITION_REGISTRY_IDENTITY_MISMATCH"
        )
    if validated_plan.composition_registry_sha256 != _labels_sha256(
        validated_composition.labels
    ):
        raise DisposablePublicCompositionProofError(
            "FIXTURE_COMPOSITION_REGISTRY_HASH_MISMATCH"
        )
    if validated_composition.provider_fallback_allowed is not False:
        raise DisposablePublicCompositionProofError(
            "FIXTURE_PROVIDER_FALLBACK_FORBIDDEN"
        )
    return DisposablePublicCompositionProofRuntime(
        plan=validated_plan,
        fixture_composition=validated_composition,
        fixture_composition_manifest_sha256=(
            validated_composition.fixture_composition_manifest_sha256
        ),
    )


_EXECUTION_ROUTE_BY_LABEL: tuple[tuple[str, str], ...] = (
    ("pump_origin_solana_rpc_transport", "top_level.pump_transport"),
    ("direct_pump_finalized_migration_transport", "top_level.migration_transport"),
    (
        "exact_pump_pumpswap_graduation_verifier_transport",
        "graduated_supply.verifier_transport_factory",
    ),
    ("secondary_discovery_http_transport", "top_level.secondary_transport"),
    (
        "pumpswap_migration_pool_confirmation",
        "graduated_supply.verifier_transport_factory",
    ),
    (
        "pumpswap_account_batch_transport",
        "graduated_supply.verifier_transport_factory",
    ),
    (
        "dexscreener_fresh_profiles_discovery",
        "graduated_supply.locator_transport",
    ),
    (
        "dexscreener_mint_batch_discovery",
        "graduated_supply.dexscreener_batch_transport_factory",
    ),
    (
        "geckoterminal_fresh_nomination",
        "graduated_supply.geckoterminal_nomination_transport",
    ),
    (
        "geckoterminal_token_pools_discovery",
        "graduated_supply.geckoterminal_reconciliation_transport_factory",
    ),
    (
        "unknown_liquidity_backup_dex_to_gecko",
        "graduated_supply.geckoterminal_reconciliation_transport_factory",
    ),
    (
        "unknown_liquidity_backup_gecko_to_dex",
        "graduated_supply.dexscreener_batch_transport_factory",
    ),
    (
        "lifecycle_exact_pair_dexscreener_primary",
        "lifecycle.snapshot_adapter_factory",
    ),
    (
        "lifecycle_exact_pair_geckoterminal_fallback",
        "lifecycle.fallback_snapshot_adapter_factory",
    ),
    (
        "preclose_coingecko_market_chain",
        "lifecycle.context_adapter_factories.coingecko",
    ),
    (
        "preclose_goplus_safety",
        "lifecycle.context_adapter_factories.goplus",
    ),
    (
        "preclose_jupiter_entry_quote",
        "lifecycle.context_adapter_factories.jupiter_quote",
    ),
    (
        "preclose_jupiter_exit_quote",
        "lifecycle.context_adapter_factories.jupiter_quote",
    ),
    (
        "preclose_solana_rpc_holder_primary",
        "lifecycle.context_adapter_factories.solana_rpc_holder",
    ),
    (
        "preclose_helius_holder_backup",
        "lifecycle.context_adapter_factories.helius_holder_backup",
    ),
)

_TOP_LEVEL_TRANSPORT_LABELS = {
    "pump_transport": "pump_origin_solana_rpc_transport",
    "secondary_transport": "secondary_discovery_http_transport",
    "migration_transport": "direct_pump_finalized_migration_transport",
}


def build_disposable_public_composition_execution_bindings(
    runtime: DisposablePublicCompositionProofRuntime,
) -> DisposablePublicCompositionExecutionBindings:
    # Plan exact fixture-to-DI routing without invoking any fixture builder.
    if not isinstance(runtime, DisposablePublicCompositionProofRuntime):
        raise DisposablePublicCompositionProofError(
            "DISPOSABLE_PUBLIC_COMPOSITION_PROOF_RUNTIME_REQUIRED"
        )

    canonical = tuple(ordinary_window_15m_builder_identities())
    composition = runtime.fixture_composition

    if runtime.plan.composition_labels != canonical:
        raise DisposablePublicCompositionProofError(
            "FIXTURE_COMPOSITION_REGISTRY_IDENTITY_MISMATCH"
        )
    if runtime.plan.composition_registry_sha256 != _labels_sha256(canonical):
        raise DisposablePublicCompositionProofError(
            "FIXTURE_COMPOSITION_REGISTRY_HASH_MISMATCH"
        )
    if composition.labels != canonical or tuple(composition.builders.keys()) != canonical:
        raise DisposablePublicCompositionProofError(
            "FIXTURE_COMPOSITION_REGISTRY_IDENTITY_MISMATCH"
        )
    expected_manifest = _fixture_manifest_sha256(canonical)
    if (
        composition.fixture_composition_manifest_sha256 != expected_manifest
        or runtime.fixture_composition_manifest_sha256 != expected_manifest
    ):
        raise DisposablePublicCompositionProofError(
            "FIXTURE_COMPOSITION_MANIFEST_MISMATCH"
        )
    if composition.provider_fallback_allowed is not False:
        raise DisposablePublicCompositionProofError(
            "FIXTURE_PROVIDER_FALLBACK_FORBIDDEN"
        )

    route_labels = tuple(label for label, _ in _EXECUTION_ROUTE_BY_LABEL)
    if route_labels != canonical:
        raise DisposablePublicCompositionProofError(
            "FIXTURE_EXECUTION_ROUTE_REGISTRY_MISMATCH"
        )
    route_by_label = dict(_EXECUTION_ROUTE_BY_LABEL)
    unmapped = tuple(label for label in canonical if label not in route_by_label)
    if unmapped:
        raise DisposablePublicCompositionProofError(
            "FIXTURE_EXECUTION_ROUTE_UNMAPPED:" + ",".join(unmapped)
        )
    if any(not str(route).strip() for route in route_by_label.values()):
        raise DisposablePublicCompositionProofError(
            "FIXTURE_EXECUTION_ROUTE_EMPTY"
        )

    return DisposablePublicCompositionExecutionBindings(
        registry_labels=canonical,
        route_by_label=route_by_label,
        top_level_transport_labels=dict(_TOP_LEVEL_TRANSPORT_LABELS),
        unmapped_labels=(),
        fixture_composition_manifest_sha256=expected_manifest,
        provider_fallback_allowed=False,
    )


def materialize_disposable_public_composition_execution(
    runtime: DisposablePublicCompositionProofRuntime,
) -> DisposablePublicCompositionMaterializedExecution:
    # Execute every explicit fixture builder exactly once, then route built
    # values only through the existing production DI seams.
    bindings = build_disposable_public_composition_execution_bindings(runtime)
    composition = runtime.fixture_composition

    outputs_by_label: dict[str, Any] = {}
    output_by_route: dict[str, Any] = {}

    for label in bindings.registry_labels:
        builder = composition.builders[label]
        try:
            built = builder()
        except DisposablePublicCompositionProofError:
            raise
        except Exception as exc:
            raise DisposablePublicCompositionProofError(
                f"FIXTURE_BUILDER_RAISED:{label}:{type(exc).__name__}"
            ) from exc

        marked = bool(
            getattr(built, "_printer_checkpoint8_fixture_output", False)
        )
        marked_labels = set(
            getattr(
                built,
                "_printer_checkpoint8_fixture_output_labels",
                (),
            )
        )
        if not marked or label not in marked_labels:
            raise DisposablePublicCompositionProofError(
                f"FIXTURE_OUTPUT_NOT_EXPLICIT:{label}"
            )

        outputs_by_label[label] = built
        route = bindings.route_by_label[label]
        if route in output_by_route and output_by_route[route] is not built:
            raise DisposablePublicCompositionProofError(
                f"FIXTURE_ROUTE_OUTPUT_CONFLICT:{route}"
            )
        output_by_route.setdefault(route, built)

    def routed(route: str) -> Any:
        if route not in output_by_route:
            raise DisposablePublicCompositionProofError(
                f"FIXTURE_EXECUTION_ROUTE_UNMAPPED:{route}"
            )
        return output_by_route[route]

    top_level = {
        key: outputs_by_label[label]
        for key, label in bindings.top_level_transport_labels.items()
    }
    graduated = {
        "verifier_transport_factory": routed(
            "graduated_supply.verifier_transport_factory"
        ),
        "locator_transport": routed(
            "graduated_supply.locator_transport"
        ),
        "dexscreener_batch_transport_factory": routed(
            "graduated_supply.dexscreener_batch_transport_factory"
        ),
        "geckoterminal_nomination_transport": routed(
            "graduated_supply.geckoterminal_nomination_transport"
        ),
        "geckoterminal_reconciliation_transport_factory": routed(
            "graduated_supply.geckoterminal_reconciliation_transport_factory"
        ),
    }
    lifecycle = {
        "snapshot_adapter_factory": routed(
            "lifecycle.snapshot_adapter_factory"
        ),
        "fallback_snapshot_adapter_factory": routed(
            "lifecycle.fallback_snapshot_adapter_factory"
        ),
        "context_adapter_factories": {
            "coingecko": routed(
                "lifecycle.context_adapter_factories.coingecko"
            ),
            "goplus": routed(
                "lifecycle.context_adapter_factories.goplus"
            ),
            "jupiter_quote": routed(
                "lifecycle.context_adapter_factories.jupiter_quote"
            ),
            "solana_rpc_holder": routed(
                "lifecycle.context_adapter_factories.solana_rpc_holder"
            ),
            "helius_holder_backup": routed(
                "lifecycle.context_adapter_factories.helius_holder_backup"
            ),
        },
    }
    return DisposablePublicCompositionMaterializedExecution(
        outputs_by_label=outputs_by_label,
        top_level_transports=top_level,
        graduated_supply_kwargs=graduated,
        lifecycle_kwargs=lifecycle,
        fixture_composition_manifest_sha256=(
            bindings.fixture_composition_manifest_sha256
        ),
        provider_fallback_allowed=False,
    )


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
    "DisposablePublicCompositionExecutionBindings",
    "DisposablePublicCompositionMaterializedExecution",
    "DisposablePublicCompositionProofBinding",
    "DisposablePublicCompositionProofError",
    "DisposablePublicCompositionProofPlan",
    "DisposablePublicCompositionProofRuntime",
    "PROOF_SCHEMA_VERSION",
    "Window15MFixtureComposition",
    "build_disposable_public_composition_execution_bindings",
    "build_disposable_public_composition_proof_binding",
    "materialize_disposable_public_composition_execution",
    "build_disposable_public_composition_proof_plan",
    "build_disposable_public_composition_proof_runtime",
    "build_window_15m_fixture_composition",
    "mark_checkpoint8_fixture_builder",
    "mark_checkpoint8_fixture_output",
    "validate_disposable_public_composition_proof_binding",
    "validate_disposable_public_composition_proof_plan",
    "validate_window_15m_fixture_composition",
]
