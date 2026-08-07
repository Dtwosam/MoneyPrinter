from __future__ import annotations

import importlib.util
from datetime import datetime, timezone
from pathlib import Path
import sqlite3

import pytest

from printer_v1.operator_cli import (
    operational_memory_factory_command as operational_command,
    window_15m_disposable_public_composition_proof as proof,
)
from printer_v1.operator_cli.graduated_supply_front_door import (
    OPERATIONAL_GRADUATED_SUPPLY_KWARGS,
    build_graduated_supply,
)
from printer_v1.discovery.permanent_discovery_availability import (
    build_campaign_source_request_scope,
)
from printer_v1.discovery.direct_migration_discovery import (
    run_direct_migration_discovery,
)
from printer_v1.operator_cli.checkpoint8_real_consumer_compatibility import (
    _accepted_source_result,
    _context,
)
from printer_v1.operator_cli.window_15m_concrete_composition import (
    COMPOSITION_MATRIX,
    ordinary_window_15m_builder_identities,
)
from printer_v1.sources.dexscreener import build_dexscreener_adapter
from printer_v1.sources.geckoterminal import build_geckoterminal_adapter
from printer_v1.sources.measured_transport import (
    MeasuredTransportLedger,
    canonical_transport_identity_key,
    identities_from_payload,
)
from printer_v1.sources.contracts import build_governed_source_request
from printer_v1.sources.governed_execution import (
    execute_source_request_with_governor,
)
from printer_v1.sources.pumpswap import build_pumpswap_adapter


ROOT = Path(__file__).resolve().parents[1]
HARNESS_PATH = (
    ROOT / "scripts" / "v2_9_8b_checkpoint8_controlling_public_composition_proof.py"
)


def _load_harness(module_name: str):
    spec = importlib.util.spec_from_file_location(module_name, HARNESS_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _prepared(harness, tmp_path: Path):
    return harness.prepare_checkpoint8_controlling_entry(
        tmp_path,
        proof_id="checkpoint8-real-consumer-compatibility",
        git_head="a" * 40,
    )


def test_checkpoint8_real_consumer_matrix_covers_exact_twenty_routes(tmp_path: Path) -> None:
    harness = _load_harness("checkpoint8_real_consumer_matrix")
    prepared = _prepared(harness, tmp_path)
    expected = tuple(ordinary_window_15m_builder_identities())
    metadata = {spec.label: spec for spec in COMPOSITION_MATRIX}

    tripwire = harness.Checkpoint8NetworkTripwire()
    with tripwire:
        report = harness.checkpoint8_real_consumer_compatibility_matrix(
            prepared.runtime
        )

    assert tripwire.attempt_count == 0
    assert report["ready"] is True
    assert tuple(report["labels"]) == expected
    assert len(expected) == 20
    assert len(report["probes"]) == 20
    assert report["provider_fallback_used"] is False
    assert report["generic_ready_placeholder_count"] == 0
    assert report["returned_fixture_self_count"] == 0

    by_label = {row["label"]: row for row in report["probes"]}
    assert tuple(by_label) == expected
    for label in expected:
        row = by_label[label]
        spec = metadata[label]
        assert row["accepted"] is True, label
        assert row["consumer_executed"] is True, label
        assert row["source_name"] == spec.source_name, label
        assert row["request_kind"] == spec.request_kind, label
        assert row["owner"] == spec.owner, label
        assert row["operation_count_delta"] >= 1, label
        assert row["returned_fixture_self"] is False, label
        assert row["generic_ready_placeholder"] is False, label


def test_checkpoint8_real_consumer_matrix_uses_fixture_operations_not_materialization(
    tmp_path: Path,
) -> None:
    harness = _load_harness("checkpoint8_real_consumer_operation_count")
    prepared = _prepared(harness, tmp_path)
    assert harness.checkpoint8_fixture_transport_operation_count(prepared.runtime) == 0

    tripwire = harness.Checkpoint8NetworkTripwire()
    with tripwire:
        report = harness.checkpoint8_real_consumer_compatibility_matrix(
            prepared.runtime
        )

    assert tripwire.attempt_count == 0
    assert report["fixture_transport_operation_count"] >= 20
    assert harness.checkpoint8_fixture_transport_operation_count(prepared.runtime) >= 20


def test_checkpoint8_pumpswap_verifier_factory_matches_canonical_mint_signature_order(
    tmp_path: Path,
) -> None:
    harness = _load_harness("checkpoint8_verifier_factory_order")
    prepared = _prepared(harness, tmp_path)
    materialized = proof.materialize_disposable_public_composition_execution(
        prepared.runtime
    )
    verifier = materialized.outputs_by_label[
        "exact_pump_pumpswap_graduation_verifier_transport"
    ]
    candidate = harness._checkpoint8_candidate_records()[0]
    mint = candidate["mint"]
    signature = candidate["migration_signature"]
    pool = candidate["pumpswap_pool"]

    transport = verifier(mint, signature)
    adapter = build_pumpswap_adapter(enabled=True, fixture_transport=transport)
    result = adapter.execute(
        _context(
            "pumpswap",
            "pumpswap_onchain_pool_confirmation",
            payload={"expected_mint": mint, "pool_address": pool},
            ordinal=77,
        )
    )
    assert _accepted_source_result(result)

    with pytest.raises(
        harness.Checkpoint8ControllingProofError,
        match="CHECKPOINT8_PUMPSWAP_FIXTURE_TARGET_MISSING",
    ):
        verifier(signature, mint)

def test_checkpoint8_direct_migration_fixture_reconciles_and_persists_two_candidates(
    tmp_path: Path,
) -> None:
    harness = _load_harness("checkpoint8_direct_migration_accounting")
    prepared = _prepared(harness, tmp_path)
    materialized = proof.materialize_disposable_public_composition_execution(
        prepared.runtime
    )
    tripwire = harness.Checkpoint8NetworkTripwire()
    with tripwire:
        report = run_direct_migration_discovery(
            prepared.runtime.plan.resolved_db_path,
            migration_transport=materialized.top_level_transports["migration_transport"],
            verifier_transport_factory=materialized.graduated_supply_kwargs[
                "verifier_transport_factory"
            ],
            now=datetime.now(timezone.utc).isoformat(),
            request_key_prefix="checkpoint8-direct-migration-accounting",
            max_candidates=2,
            collection_rounds=1,
            settle_seconds=0.0,
            reverify_on_transient=False,
            reverify_settle_seconds=0.0,
        )

    assert tripwire.attempt_count == 0
    assert report["status"] == "COMPLETE"
    assert report["confirmed_count"] == 2
    ledger = report["source_operation_ledger"]
    assert ledger["operation_accounting_reconciled"] is True
    assert ledger["source_requests"] == 5
    assert ledger["identity_transport_operations"] == 7
    assert ledger["transport_operations"] == 7

    now_epoch = int(datetime.now(timezone.utc).timestamp())
    for candidate in harness._checkpoint8_candidate_records():
        assert int(candidate["migration_block_time"]) <= now_epoch + 300

    connection = sqlite3.connect(prepared.runtime.plan.resolved_db_path)
    try:
        count = int(
            connection.execute(
                "SELECT COUNT(*) FROM printer_pumpswap_graduated_candidate_registry"
            ).fetchone()[0]
        )
    finally:
        connection.close()
    assert count == 2

def test_checkpoint8_disposable_bridge_preserves_canonical_operational_supply_policy(
    tmp_path: Path,
) -> None:
    harness = _load_harness("checkpoint8_bridge_policy_overlay")
    prepared = _prepared(harness, tmp_path)
    materialized = proof.materialize_disposable_public_composition_execution(
        prepared.runtime
    )

    merged = operational_command._merge_disposable_graduated_supply_kwargs(
        materialized.graduated_supply_kwargs
    )

    for key, value in OPERATIONAL_GRADUATED_SUPPLY_KWARGS.items():
        assert merged[key] == value, key
    assert merged["permanent_availability"] is True
    assert merged["run_locator"] is True
    assert merged["run_geckoterminal_nomination"] is True
    for key, value in materialized.graduated_supply_kwargs.items():
        assert merged[key] is value, key

    with pytest.raises(
        operational_command.OperationalMemoryFactoryError,
        match=(
            "DISPOSABLE_PROOF_OPERATIONAL_SUPPLY_POLICY_OVERRIDE_FORBIDDEN:"
            "permanent_availability"
        ),
    ):
        operational_command._merge_disposable_graduated_supply_kwargs(
            {
                **materialized.graduated_supply_kwargs,
                "permanent_availability": False,
            }
        )



def test_checkpoint8_measured_market_fixture_identities_survive_real_adapters(tmp_path):
    harness = _load_harness("dtw46-measured-market")
    prepared = _prepared(harness, tmp_path)
    m = proof.materialize_disposable_public_composition_execution(prepared.runtime)
    mints = tuple(x["mint"] for x in harness._checkpoint8_candidate_records())

    cases = [
        (
            build_dexscreener_adapter(enabled=True, fixture_transport=m.graduated_supply_kwargs["locator_transport"]),
            _context("dexscreener", "dexscreener_fresh_profiles", payload={"chain":"solana","request_kind":"dexscreener_fresh_profiles"}, ordinal=90),
            "DEXSCREENER_DISCOVERY", "dexscreener", "dexscreener_fresh_profiles",
        ),
        (
            build_dexscreener_adapter(enabled=True, fixture_transport=m.graduated_supply_kwargs["dexscreener_batch_transport_factory"](mints)),
            _context("dexscreener", "candidate_market_batch", payload={"chain":"solana","token_mints":list(mints)}, ordinal=91),
            "MINT_MARKET_BATCH", "dexscreener", "candidate_market_batch",
        ),
        (
            build_geckoterminal_adapter(enabled=True, fixture_transport=m.graduated_supply_kwargs["geckoterminal_nomination_transport"]),
            _context("geckoterminal", "geckoterminal_new_pool_discovery", payload={"chain":"solana"}, ordinal=92),
            "FRESH_POOL_NOMINATION", "geckoterminal", "geckoterminal_new_pool_discovery",
        ),
        (
            build_geckoterminal_adapter(enabled=True, fixture_transport=m.graduated_supply_kwargs["geckoterminal_reconciliation_transport_factory"](mints[0])),
            _context("geckoterminal", "candidate_market_batch", payload={"chain":"solana","token_mint":mints[0]}, ordinal=93),
            "MINT_MARKET_BATCH", "geckoterminal", "candidate_market_batch",
        ),
    ]

    tripwire = harness.Checkpoint8NetworkTripwire()
    with tripwire:
        for adapter, ctx, stage, source, kind in cases:
            result = adapter.execute(ctx)
            assert _accepted_source_result(result)
            assert result.normalized_payload["transport_operations_used"] == 1
            identities = identities_from_payload(result.normalized_payload)
            assert len(identities) == 1
            identity = identities[0]
            assert identity.stage == stage
            assert identity.source_name == source
            assert identity.governed_request_kind == kind
            assert identity.target_identity
            assert identity.response_bytes > 0
            assert identity.normalized_rows > 0

    assert tripwire.attempt_count == 0



def test_checkpoint8_permanent_four_reserve_carries_direct_evidence_and_exact_budget(tmp_path):
    harness = _load_harness("dtw47-four-reserve-green")
    prepared = _prepared(harness, tmp_path)
    materialized = proof.materialize_disposable_public_composition_execution(
        prepared.runtime
    )

    execution_id = "dtw47-green-execution"
    campaign_id = "dtw47-green-campaign"
    run_id = "dtw47-green-run"
    cycle_id = "dtw47-green-cycle"

    kwargs = operational_command._merge_disposable_graduated_supply_kwargs(
        materialized.graduated_supply_kwargs
    )
    scope = build_campaign_source_request_scope(
        execution_id=execution_id,
        campaign_id=campaign_id,
        run_id=run_id,
        cycle_id=cycle_id,
    )
    kwargs.update(
        execution_id=execution_id,
        campaign_id=campaign_id,
        run_id=run_id,
        cycle_id=cycle_id,
        campaign_source_request_scope=scope,
        discovery_request_key_prefix=scope.request_key_root,
        front_door_request_key_prefix=scope.request_key_root,
    )

    tripwire = harness.Checkpoint8NetworkTripwire()
    with tripwire:
        supply = build_graduated_supply(
            prepared.runtime.plan.resolved_db_path,
            cycle_seed=execution_id,
            migration_transport=materialized.top_level_transports[
                "migration_transport"
            ],
            now=datetime.now(timezone.utc).isoformat(),
            **kwargs,
        )

    assert tripwire.attempt_count == 0
    assert supply.ready is True
    assert supply.terminal == "CANDIDATE_SUPPLY_READY"
    assert len(supply.holder_reserve_supply) == 4
    assert len(supply.graduated_supply) == 2

    diagnostics = dict(supply.diagnostics)
    assert diagnostics["required_token_capacity"] == 4
    assert diagnostics["eligible_reserve_count"] == 4
    assert diagnostics["discovery_source_requests"] == 9
    assert diagnostics["direct_migration_protocol_confirmation_requests"] == 4
    assert diagnostics["last_stop_reason"] == "ELIGIBLE_CAPACITY_MET"

    assert len(supply.holder_reserve_candidates) == 4
    for candidate in supply.holder_reserve_candidates.values():
        evidence = candidate.get("direct_pump_evidence")
        assert isinstance(evidence, dict)
        assert evidence["mint"] == candidate["mint"]
        assert evidence["pool"] == candidate["pool"]
        assert evidence["confirmed"] is True


def test_checkpoint8_lifecycle_market_fixture_is_exact_target_aware(tmp_path):
    harness = _load_harness("dtw47-lifecycle-target")
    prepared = _prepared(harness, tmp_path)
    materialized = proof.materialize_disposable_public_composition_execution(
        prepared.runtime
    )
    candidates = harness._checkpoint8_candidate_records()
    assert len(candidates) == 4

    primary = materialized.lifecycle_kwargs["snapshot_adapter_factory"]
    fallback = materialized.lifecycle_kwargs[
        "fallback_snapshot_adapter_factory"
    ]

    tripwire = harness.Checkpoint8NetworkTripwire()
    with tripwire:
        for ordinal, candidate in enumerate(candidates[:2], start=120):
            mint = candidate["mint"]
            pool = candidate["pumpswap_pool"]

            for factory, source in (
                (primary, "dexscreener"),
                (fallback, "geckoterminal"),
            ):
                adapter = factory(
                    token_mint=mint,
                    pool_address=pool,
                    timeout_seconds=1.0,
                )
                result = adapter.execute(
                    _context(
                        source,
                        "pair_market_snapshot",
                        payload={
                            "token_mint": mint,
                            "pool_address": pool,
                        },
                        ordinal=ordinal,
                    )
                )
                assert _accepted_source_result(result)
                pairs = list(result.normalized_payload.get("pairs") or ())
                assert len(pairs) == 1
                assert pairs[0]["token_mint"] == mint
                assert pairs[0]["pair_address"] == pool

        with pytest.raises(
            harness.Checkpoint8ControllingProofError,
            match="CHECKPOINT8_LIFECYCLE_FIXTURE_TARGET_MISMATCH",
        ):
            primary(
                token_mint=candidates[0]["mint"],
                pool_address=candidates[1]["pumpswap_pool"],
                timeout_seconds=1.0,
            )

    assert tripwire.attempt_count == 0



def test_checkpoint8_goplus_fixture_records_exact_holder_measured_identity(
    tmp_path: Path,
) -> None:
    harness = _load_harness("dtw48-goplus-holder-identity")
    prepared = _prepared(harness, tmp_path)
    materialized = proof.materialize_disposable_public_composition_execution(
        prepared.runtime
    )

    candidate = harness._checkpoint8_candidate_records()[0]
    mint = candidate["mint"]

    holder_ledger = MeasuredTransportLedger(
        campaign_id="dtw48-green-campaign",
        run_id="dtw48-green-run",
        cycle_id="dtw48-green-cycle",
    )

    factory = materialized.lifecycle_kwargs[
        "context_adapter_factories"
    ]["goplus"]

    adapter = factory(
        token_mint=mint,
        timeout_seconds=1.0,
        measured_transport_ledger=holder_ledger,
    )

    request = build_governed_source_request(
        "goplus",
        "safety_reference",
        request_key="dtw48-green:goplus-holder",
        payload={"token_mint": mint},
    )

    tripwire = harness.Checkpoint8NetworkTripwire()
    with tripwire:
        execution = execute_source_request_with_governor(
            prepared.runtime.plan.resolved_db_path,
            request,
            adapter,
            recent_request_count=0,
        )

    result = execution.normalized_result
    payload = dict(result.normalized_payload)

    assert tripwire.attempt_count == 0
    assert result.source_status.value == "COMPLETE"
    assert result.data_quality_label.value == "CLEAN_DATA"
    assert payload["token_mint"].lower() == mint.lower()
    assert payload["transport_operations_used"] == 1
    assert payload["underlying_operation_count"] == 1

    payload_identities = identities_from_payload(payload)
    assert len(holder_ledger.transports) == 1
    assert len(payload_identities) == 1

    ledger_identity = holder_ledger.transports[0]
    payload_identity = payload_identities[0]

    assert (
        canonical_transport_identity_key(ledger_identity)
        == canonical_transport_identity_key(payload_identity)
    )

    assert ledger_identity.stage == "HOLDER_SAFETY"
    assert ledger_identity.source_name == "goplus"
    assert ledger_identity.endpoint_owner == "api.gopluslabs.io"
    assert ledger_identity.governed_request_kind == "safety_reference"
    assert ledger_identity.method_or_endpoint == "GET_TOKEN_SECURITY"
    assert ledger_identity.within_request_ordinal == 1
    assert ledger_identity.target_category == "TOKEN_MINT"
    assert ledger_identity.target_identity == mint
    assert ledger_identity.response_bytes > 0
    assert ledger_identity.normalized_rows == 1
    assert ledger_identity.result == "COMPLETED"
