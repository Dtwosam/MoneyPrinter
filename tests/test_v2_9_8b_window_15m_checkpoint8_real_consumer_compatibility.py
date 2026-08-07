from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

from printer_v1.operator_cli import (
    window_15m_disposable_public_composition_proof as proof,
)
from printer_v1.operator_cli.checkpoint8_real_consumer_compatibility import (
    _accepted_source_result,
    _context,
)
from printer_v1.operator_cli.window_15m_concrete_composition import (
    COMPOSITION_MATRIX,
    ordinary_window_15m_builder_identities,
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
