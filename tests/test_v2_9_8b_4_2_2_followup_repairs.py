"""Regression proof for independently found 4/2/2 implementation gaps."""
from __future__ import annotations

import inspect
import sqlite3
from types import SimpleNamespace

from printer_v1.db import apply_migrations


def test_real_cooperative_refresh_composition_stops_after_one_new_request(
    tmp_path, monkeypatch
) -> None:
    from printer_v1.discovery import pre_lifecycle_refresh_composition as refresh
    from printer_v1.discovery.permanent_discovery_availability import StageBudget
    from printer_v1.operator_cli import graduated_supply_front_door as front_door

    database = tmp_path / "cooperative-refresh-real.sqlite3"
    apply_migrations(database)
    connection = sqlite3.connect(database)
    connection.row_factory = sqlite3.Row
    calls: list[str] = []

    def fresh(*_args, **_kwargs):
        calls.append("fresh")
        return {
            "source_requests": 1,
            "status": "empty",
            "pool_observations": [],
            "accounting_blocker": False,
        }

    def backup(*_args, **_kwargs):
        calls.append("backup")
        return {"source_requests": 1, "accounting_blocker": False}

    def protocol(*_args, **_kwargs):
        calls.append("protocol")
        return {
            "source_requests": 1,
            "shared_source_failures": 0,
            "promoted_observation_eligible": [],
        }

    monkeypatch.setattr(front_door, "run_fresh_profile_locator", fresh)
    monkeypatch.setattr(refresh, "run_bounded_unknown_liquidity_backup", backup)
    monkeypatch.setattr(refresh, "process_protocol_confirmation_queue", protocol)

    stage = refresh.build_pre_lifecycle_refresh_stage(
        db_path=database,
        request_key_prefix="followup-refresh",
    )
    try:
        result = stage(
            connection,
            campaign_id="campaign",
            run_id="run",
            cycle_id="cycle",
            discovery_work_id="work",
            scheduler_job_id=1,
            refresh_ordinal=2,
            source_operations_remaining=10,
            now="2026-08-28T12:10:00+00:00",
            cooperative_yield=True,
            cooperative_stage_budget=StageBudget.permanent_discovery_default(),
        )
    finally:
        connection.close()

    assert calls == ["fresh"]
    assert result["source_operations"] == 1
    assert result["cooperative_incomplete"] is True
    assert float(result["next_governed_request_worst_case_seconds"]) > 0


def test_production_attempt_evidence_keeps_exact_pair_reobservations_and_outcomes(
    tmp_path,
) -> None:
    from printer_v1.operator_cli.pre_admission_attempt_evidence import (
        record_later_cycle_supply_evidence,
    )

    database = tmp_path / "attempt-evidence-producer.sqlite3"
    apply_migrations(database)
    connection = sqlite3.connect(database)
    candidate_a = {
        "mint": "MINT_A",
        "pool": "PAIR_A",
        "eligible": False,
        "reason": "LIQUIDITY_BELOW_SELECTION_FLOOR",
        "exact_pair_confirmed": True,
        "pumpswap_confirmed": True,
        "liquidity_status": "LIQUIDITY_BELOW_SELECTION_FLOOR",
        "safety_evidence_status": "PASS",
        "inventory_status": "RETAINED",
    }
    candidate_b = {**candidate_a, "pool": "PAIR_B", "reason": "EXACT_PAIR_NO_MATCH"}
    first = SimpleNamespace(
        diagnostics={"candidates": [candidate_a, candidate_b]},
        source_evidence=(),
        candidates=(),
        terminal_cause="ACQUISITION_QUANTUM_YIELDED",
    )
    second = SimpleNamespace(
        diagnostics={"candidates": [candidate_a]},
        source_evidence=(),
        candidates=(),
        terminal_cause="ACQUISITION_QUANTUM_YIELDED",
    )
    try:
        record_later_cycle_supply_evidence(
            connection,
            attempt_id="attempt-producer",
            supply=first,
            observed_at="2026-08-28T12:00:00+00:00",
        )
        record_later_cycle_supply_evidence(
            connection,
            attempt_id="attempt-producer",
            supply=second,
            observed_at="2026-08-28T12:00:10+00:00",
        )
        rows = connection.execute(
            """SELECT evidence_kind,mint_identity,pair_identity
                 FROM printer_pre_admission_attempt_evidence
                WHERE attempt_id='attempt-producer'
                ORDER BY opportunity_ordinal,claim_ordinal,event_key"""
        ).fetchall()
    finally:
        connection.close()

    facts = [(str(kind), mint, pair) for kind, mint, pair in rows]
    assert ("CANDIDATE_OBSERVED", "MINT_A", "PAIR_A") in facts
    assert ("CANDIDATE_OBSERVED", "MINT_A", "PAIR_B") in facts
    assert ("CANDIDATE_REOBSERVED", "MINT_A", "PAIR_A") in facts
    assert ("EXACT_PAIR_RESULT", "MINT_A", "PAIR_A") in facts
    assert ("PUMPSWAP_RESULT", "MINT_A", "PAIR_A") in facts
    assert ("LIQUIDITY_RESULT", "MINT_A", "PAIR_A") in facts
    assert ("SAFETY_EVIDENCE_RESULT", "MINT_A", "PAIR_A") in facts
    assert ("INVENTORY_RESULT", "MINT_A", "PAIR_A") in facts


def test_attempt_reduction_is_certificate_authority_not_a_lower_bound() -> None:
    from printer_v1.operator_cli.pre_admission_attempt_evidence import (
        rebuild_exhaustion_certificate_from_attempt_evidence,
    )

    rebuilt = rebuild_exhaustion_certificate_from_attempt_evidence(
        {
            "unique_tokens_observed": 99,
            "rejected_count": 99,
            "rejection_reasons": {"LOCAL_ONLY": 99},
            "provider_failures": 99,
            "discovery_rounds": 99,
        },
        {
            "unique_tokens_observed": 4,
            "rejected_count": 3,
            "rejection_reasons": {"LIQUIDITY_BELOW_SELECTION_FLOOR": 2},
            "provider_failures": 1,
            "opportunities_executed": [0, 1, 2],
        },
    )
    assert rebuilt["unique_tokens_observed"] == 4
    assert rebuilt["rejected_count"] == 3
    assert rebuilt["provider_failures"] == 1
    assert rebuilt["discovery_rounds"] == 3
    assert rebuilt["rejection_reasons"] == {
        "LIQUIDITY_BELOW_SELECTION_FLOOR": 2
    }


def test_preclose_has_durable_reservation_checkpoint_owner_before_provider() -> None:
    from printer_v1.operator_cli import one_command_15m_factory as factory

    assert hasattr(factory, "_persist_preclose_reservation_manifest_before_provider")
    source = inspect.getsource(factory)
    checkpoint = source.index(
        "_persist_preclose_reservation_manifest_before_provider(\n                        conn"
    )
    provider = source.index("_execute_preclose_critical_phase(", checkpoint)
    assert checkpoint < provider


def test_full_run_preclose_projection_requires_exact_source_unit_manifest() -> None:
    from printer_v1.operator_cli import campaign_full_run_accounting as accounting

    signature = inspect.signature(accounting.reservation_identities_from_durable_records)
    assert "source_unit_manifest" in signature.parameters
