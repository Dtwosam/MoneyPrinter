from __future__ import annotations

from pathlib import Path
import hashlib
import inspect

import pytest

from printer_v1.db.migrate import canonical_migration_count, canonical_migration_names
from printer_v1.operator_cli import operational_memory_factory_command as command
from printer_v1.operator_cli import window_15m_disposable_public_composition_proof as proof
from printer_v1.operator_cli.proof_db_schema_readiness import CANONICAL_PERSISTENT_DB
from printer_v1.operator_cli.window_15m_concrete_composition import (
    ordinary_window_15m_builder_identities,
)


class _FixtureValue:
    pass


def _runtime(tmp_path: Path):
    db_path = tmp_path / "checkpoint8-owner-di.sqlite3"
    db_path.write_bytes(b"checkpoint8-owner-di")
    labels = ordinary_window_15m_builder_identities()

    plan = proof.build_disposable_public_composition_proof_plan(
        proof_id="checkpoint8-owner-di",
        db_path=db_path,
        db_sha256=hashlib.sha256(db_path.read_bytes()).hexdigest(),
        migration_count=canonical_migration_count(),
        migration_head=canonical_migration_names()[-1],
        artifact_root=tmp_path / "artifacts",
        composition_labels=labels,
        provider_execution_allowed=False,
        automatic_retry_allowed=False,
        manual_rerun_allowed=False,
        resume_allowed=False,
        restart_allowed=False,
        successor_allowed=False,
    )

    # First obtain the already-GREEN canonical route ownership so labels sharing
    # one existing DI seam return the same fixture object.
    temporary_builders = {
        label: proof.mark_checkpoint8_fixture_builder(
            lambda label=label: {"label": label},
            label=label,
        )
        for label in labels
    }
    temporary_composition = proof.build_window_15m_fixture_composition(
        temporary_builders
    )
    temporary_runtime = proof.build_disposable_public_composition_proof_runtime(
        plan,
        temporary_composition,
        canonical_db_path=CANONICAL_PERSISTENT_DB,
    )
    routes = proof.build_disposable_public_composition_execution_bindings(
        temporary_runtime
    ).route_by_label

    by_route: dict[str, _FixtureValue] = {}
    builders = {}
    for label in labels:
        value = by_route.setdefault(routes[label], _FixtureValue())

        def builder(label=label, value=value):
            return proof.mark_checkpoint8_fixture_output(value, label=label)

        builders[label] = proof.mark_checkpoint8_fixture_builder(
            builder,
            label=label,
        )

    composition = proof.build_window_15m_fixture_composition(builders)
    return proof.build_disposable_public_composition_proof_runtime(
        plan,
        composition,
        canonical_db_path=CANONICAL_PERSISTENT_DB,
    )


def test_owner_bridge_builds_exact_invocation_binding(tmp_path: Path) -> None:
    runtime = _runtime(tmp_path)
    prepared = command._prepare_disposable_public_composition_execution(runtime)
    bridge = command._build_disposable_public_composition_owner_bridge(
        disposable_proof=runtime,
        prepared_proof=prepared,
        execution_id="exec-c8",
    )
    binding = bridge.proof_binding
    assert binding.execution_id == "exec-c8"
    assert binding.campaign_id == "exec-c8-campaign"
    assert binding.campaign_run_id == "exec-c8-campaign-run"
    assert binding.cycle_id == "exec-c8-cycle"
    assert binding.configuration_id == "exec-c8-configuration"
    assert binding.resolved_db_path == runtime.plan.resolved_db_path
    assert binding.db_target_identity == f"sha256:{runtime.plan.pre_mutation_db_sha256}"
    assert binding.fixture_composition_manifest_sha256 == (
        runtime.fixture_composition_manifest_sha256
    )


def test_owner_bridge_exposes_only_materialized_existing_di(tmp_path: Path) -> None:
    runtime = _runtime(tmp_path)
    prepared = command._prepare_disposable_public_composition_execution(runtime)
    bridge = command._build_disposable_public_composition_owner_bridge(
        disposable_proof=runtime,
        prepared_proof=prepared,
        execution_id="exec-c8",
    )
    materialized = prepared.materialized
    assert bridge.pump_transport is materialized.top_level_transports["pump_transport"]
    assert bridge.secondary_transport is materialized.top_level_transports[
        "secondary_transport"
    ]
    assert bridge.migration_transport is materialized.top_level_transports[
        "migration_transport"
    ]
    assert bridge.graduated_supply_kwargs == materialized.graduated_supply_kwargs
    assert bridge.lifecycle_kwargs == materialized.lifecycle_kwargs
    assert bridge.provider_fallback_allowed is False


def test_owner_bridge_uses_dedicated_proof_binding_not_production_binding(
    tmp_path: Path,
) -> None:
    runtime = _runtime(tmp_path)
    prepared = command._prepare_disposable_public_composition_execution(runtime)
    bridge = command._build_disposable_public_composition_owner_bridge(
        disposable_proof=runtime,
        prepared_proof=prepared,
        execution_id="exec-c8",
    )
    assert bridge.operational_database_target_binding is None
    assert bridge.disposable_public_composition_proof_binding is bridge.proof_binding
    assert bridge.db_path == Path(runtime.plan.resolved_db_path).resolve()
    assert bridge.artifact_root == Path(runtime.plan.resolved_artifact_root).resolve()


def test_owner_bridge_rejects_prepared_manifest_drift(tmp_path: Path) -> None:
    runtime = _runtime(tmp_path)
    prepared = command._prepare_disposable_public_composition_execution(runtime)
    object.__setattr__(
        prepared.materialized,
        "fixture_composition_manifest_sha256",
        "f" * 64,
    )
    with pytest.raises(
        command.OperationalMemoryFactoryError,
        match="FIXTURE_COMPOSITION_MANIFEST_MISMATCH",
    ):
        command._build_disposable_public_composition_owner_bridge(
            disposable_proof=runtime,
            prepared_proof=prepared,
            execution_id="exec-c8",
        )


def test_public_coordinator_has_no_half_wired_proof_stop() -> None:
    source = inspect.getsource(command._run_operational_campaign)
    assert "DISPOSABLE_PROOF_COORDINATOR_DI_NOT_WIRED" not in source


def test_owner_bridge_api_is_not_a_second_public_runner() -> None:
    signature = inspect.signature(command._build_disposable_public_composition_owner_bridge)
    assert tuple(signature.parameters) == (
        "disposable_proof",
        "prepared_proof",
        "execution_id",
    )
    assert "operator_approved" not in signature.parameters
    assert "owner" not in signature.parameters
    assert not hasattr(command, "run_disposable_public_composition_campaign")
