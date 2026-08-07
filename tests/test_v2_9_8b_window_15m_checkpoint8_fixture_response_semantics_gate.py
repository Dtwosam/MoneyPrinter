from __future__ import annotations

import importlib.util
from pathlib import Path
from types import SimpleNamespace

import pytest

from printer_v1.operator_cli.window_15m_concrete_composition import (
    ordinary_window_15m_builder_identities,
)


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


def test_success_fixture_response_semantics_cover_exact_twenty_labels_and_two_candidates() -> None:
    harness = _load_harness("checkpoint8_fixture_response_semantics")
    summary = harness.checkpoint8_success_fixture_response_semantics()
    expected = tuple(ordinary_window_15m_builder_identities())
    assert summary["ready"] is True
    assert tuple(summary["labels"]) == expected
    assert len(expected) == 20
    assert summary["candidate_count"] == 2
    assert len(set(summary["candidate_mints"])) == 2
    assert summary["infrastructure_mint_count"] == 0
    assert summary["all_routes_have_explicit_payload_contracts"] is True


def test_top_level_fixture_transports_return_payloads_not_fixture_self(tmp_path: Path) -> None:
    harness = _load_harness("checkpoint8_fixture_response_top_level")
    prepared = harness.prepare_checkpoint8_controlling_entry(
        tmp_path,
        proof_id="checkpoint8-response-semantics",
        git_head="a" * 40,
    )
    materialized = harness.proof.materialize_disposable_public_composition_execution(
        prepared.runtime
    )
    pump = materialized.top_level_transports["pump_transport"]
    secondary = materialized.top_level_transports["secondary_transport"]

    page = pump.json_rpc(
        "getSignaturesForAddress",
        ["fixture-program", {"limit": 16}],
        timeout_seconds=1.0,
        byte_ceiling=1_000_000,
    )
    assert isinstance(page, list)
    assert len(page) == 2
    assert page is not pump

    body = secondary.json_get(
        "https://fixture.invalid/trending_pools",
        params={},
        headers={},
        timeout_seconds=1.0,
        byte_ceiling=1_000_000,
    )
    assert isinstance(body, (dict, list))
    assert body is not secondary


def test_pre_run_evidence_blocks_execution_until_fixture_response_semantics_are_ready(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    harness = _load_harness("checkpoint8_fixture_response_execution_gate")
    prepared = harness.prepare_checkpoint8_controlling_entry(
        tmp_path,
        proof_id="checkpoint8-response-gate",
        git_head="b" * 40,
    )
    assert prepared.pre_run_evidence["fixture_response_semantics_ready"] is True
    assert prepared.pre_run_evidence["fixture_candidate_count"] == 2

    prepared.pre_run_evidence["fixture_response_semantics_ready"] = False
    monkeypatch.setattr(
        harness,
        "run_operational_campaign",
        lambda **kwargs: (_ for _ in ()).throw(
            AssertionError("campaign reached with unready fixture semantics")
        ),
        raising=False,
    )
    with pytest.raises(
        harness.Checkpoint8ControllingProofError,
        match="CHECKPOINT8_FIXTURE_RESPONSE_SEMANTICS_NOT_READY",
    ):
        harness.execute_checkpoint8_public_sequence(
            prepared,
            git_head="b" * 40,
        )
