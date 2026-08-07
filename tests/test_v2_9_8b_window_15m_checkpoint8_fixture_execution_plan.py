from __future__ import annotations

from dataclasses import replace
import hashlib
from pathlib import Path

import pytest

from printer_v1.db.migrate import canonical_migration_count, canonical_migration_names
from printer_v1.operator_cli import window_15m_disposable_public_composition_proof as proof
from printer_v1.operator_cli.proof_db_schema_readiness import CANONICAL_PERSISTENT_DB
from printer_v1.operator_cli.window_15m_concrete_composition import (
    ordinary_window_15m_builder_identities,
)


def _runtime(tmp_path: Path, calls: list[str] | None = None):
    db_path = tmp_path / "checkpoint8-execution-plan.sqlite3"
    db_path.write_bytes(b"checkpoint8-fixture-execution-plan")
    labels = ordinary_window_15m_builder_identities()
    builders = {}
    for label in labels:
        def builder(label=label):
            if calls is not None:
                calls.append(label)
            return {"fixture_label": label}

        builders[label] = proof.mark_checkpoint8_fixture_builder(
            builder,
            label=label,
        )
    plan = proof.build_disposable_public_composition_proof_plan(
        proof_id="checkpoint8-fixture-execution-plan",
        db_path=db_path,
        db_sha256=hashlib.sha256(db_path.read_bytes()).hexdigest(),
        migration_count=canonical_migration_count(),
        migration_head=canonical_migration_names()[-1],
        artifact_root=tmp_path / "proof-artifacts",
        composition_labels=labels,
        provider_execution_allowed=False,
        automatic_retry_allowed=False,
        manual_rerun_allowed=False,
        resume_allowed=False,
        restart_allowed=False,
        successor_allowed=False,
    )
    composition = proof.build_window_15m_fixture_composition(builders)
    return proof.build_disposable_public_composition_proof_runtime(
        plan,
        composition,
        canonical_db_path=CANONICAL_PERSISTENT_DB,
    )


def _execution_bindings(runtime):
    return proof.build_disposable_public_composition_execution_bindings(runtime)


def test_execution_binding_plan_covers_exact_registry_without_running_builders(
    tmp_path: Path,
) -> None:
    calls: list[str] = []
    runtime = _runtime(tmp_path, calls)
    bindings = _execution_bindings(runtime)
    assert calls == []
    assert bindings.registry_labels == ordinary_window_15m_builder_identities()
    assert bindings.unmapped_labels == ()
    assert bindings.provider_fallback_allowed is False
    assert bindings.fixture_composition_manifest_sha256 == (
        runtime.fixture_composition_manifest_sha256
    )


def test_execution_binding_plan_uses_existing_top_level_transport_seams(
    tmp_path: Path,
) -> None:
    bindings = _execution_bindings(_runtime(tmp_path))
    assert bindings.top_level_transport_labels == {
        "pump_transport": "pump_origin_solana_rpc_transport",
        "secondary_transport": "secondary_discovery_http_transport",
        "migration_transport": "direct_pump_finalized_migration_transport",
    }


def test_execution_binding_plan_uses_existing_graduated_supply_seams(
    tmp_path: Path,
) -> None:
    bindings = _execution_bindings(_runtime(tmp_path))
    routes = bindings.route_by_label
    assert routes["exact_pump_pumpswap_graduation_verifier_transport"] == (
        "graduated_supply.verifier_transport_factory"
    )
    assert routes["dexscreener_fresh_profiles_discovery"] == (
        "graduated_supply.locator_transport"
    )
    assert routes["dexscreener_mint_batch_discovery"] == (
        "graduated_supply.dexscreener_batch_transport_factory"
    )
    assert routes["geckoterminal_fresh_nomination"] == (
        "graduated_supply.geckoterminal_nomination_transport"
    )
    assert routes["geckoterminal_token_pools_discovery"] == (
        "graduated_supply.geckoterminal_reconciliation_transport_factory"
    )
    # The existing bounded backup owner reuses the same two batch-factory seams;
    # labels remain distinct proof identities even though the DI seam is shared.
    assert routes["unknown_liquidity_backup_dex_to_gecko"] == (
        "graduated_supply.geckoterminal_reconciliation_transport_factory"
    )
    assert routes["unknown_liquidity_backup_gecko_to_dex"] == (
        "graduated_supply.dexscreener_batch_transport_factory"
    )


def test_execution_binding_plan_uses_existing_lifecycle_context_seams(
    tmp_path: Path,
) -> None:
    bindings = _execution_bindings(_runtime(tmp_path))
    routes = bindings.route_by_label
    assert routes["lifecycle_exact_pair_dexscreener_primary"] == (
        "lifecycle.snapshot_adapter_factory"
    )
    assert routes["lifecycle_exact_pair_geckoterminal_fallback"] == (
        "lifecycle.fallback_snapshot_adapter_factory"
    )
    assert routes["preclose_coingecko_market_chain"] == (
        "lifecycle.context_adapter_factories.coingecko"
    )
    assert routes["preclose_goplus_safety"] == (
        "lifecycle.context_adapter_factories.goplus"
    )
    assert routes["preclose_jupiter_entry_quote"] == (
        "lifecycle.context_adapter_factories.jupiter_quote"
    )
    assert routes["preclose_jupiter_exit_quote"] == (
        "lifecycle.context_adapter_factories.jupiter_quote"
    )
    assert routes["preclose_solana_rpc_holder_primary"] == (
        "lifecycle.context_adapter_factories.solana_rpc_holder"
    )
    assert routes["preclose_helius_holder_backup"] == (
        "lifecycle.context_adapter_factories.helius_holder_backup"
    )


def test_execution_binding_plan_accounts_every_registry_label_exactly_once(
    tmp_path: Path,
) -> None:
    bindings = _execution_bindings(_runtime(tmp_path))
    labels = ordinary_window_15m_builder_identities()
    assert tuple(bindings.route_by_label.keys()) == labels
    assert len(bindings.route_by_label) == len(labels)
    assert set(bindings.route_by_label) == set(labels)
    assert all(str(route).strip() for route in bindings.route_by_label.values())


def test_execution_binding_plan_rejects_runtime_manifest_drift(tmp_path: Path) -> None:
    runtime = _runtime(tmp_path)
    drifted = replace(
        runtime,
        fixture_composition_manifest_sha256="f" * 64,
    )
    with pytest.raises(
        proof.DisposablePublicCompositionProofError,
        match="FIXTURE_COMPOSITION_MANIFEST_MISMATCH",
    ):
        _execution_bindings(drifted)
