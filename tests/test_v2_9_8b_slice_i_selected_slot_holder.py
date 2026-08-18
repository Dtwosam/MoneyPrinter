"""Slice I — selected-slot holder budget ownership.

Reproduce the committed defects first:
- reserve traversal order differs from the selected pair and unselected
  candidates currently consume holder work;
- a selected token with holder UNKNOWN/unavailable is wrongly rejected in
  later-cycle flow;
- selected-slot holder accounting must charge each real transport once.

Holder concentration and source-unavailable states are descriptive context.
They must not reject, replace, or reshuffle the already-selected pair.
"""

from __future__ import annotations

from datetime import datetime, timezone
import inspect
import json
from types import SimpleNamespace
from unittest.mock import patch

import pytest

from printer_v1.db import apply_migrations
from printer_v1.lifecycle.tracking_queue import (
    HANDOFF_ACTIVE_CONFLICT,
    HANDOFF_UNSUPPORTED_STATE,
)
from printer_v1.operator_cli.authoritative_live_operational_campaign import (
    AuthoritativeLiveOperationalCampaignOwner,
)
from printer_v1.operator_cli.graduated_supply_front_door import GraduatedSupply
from printer_v1.operator_cli.later_cycle_graduated_supply import (
    LaterCycleGraduatedSupplyError,
    build_later_cycle_graduated_supply,
    holder_fact_blocks_selected_admission,
    selected_slot_holder_candidates,
)


NOW = datetime(2026, 8, 18, 12, 5, tzinfo=timezone.utc)

UNSELECTED_A = "mint-unselected-a"
UNSELECTED_B = "mint-unselected-b"
SELECTED_A = "mint-selected-a"
SELECTED_B = "mint-selected-b"


def _admission(mint: str, pool: str):
    return SimpleNamespace(
        mint=mint,
        pool_address=pool,
        bonding_curve=pool,
        market_identity=f"solana-mainnet:pumpswap:{pool}",
        temporal_context=SimpleNamespace(
            admission_observed_at_utc=NOW.isoformat()
        ),
    )


def _candidate_mapping(item, *, provenance: str) -> dict[str, object]:
    return {
        "mint": item.mint,
        "pool": item.pool_address,
        "pumpswap_pool": item.pool_address,
        "market_identity": item.market_identity,
        "provenance": provenance,
        "holder_evidence_eligible": True,
    }


def _split_reserve_supply() -> GraduatedSupply:
    """Reserve order differs from the already-selected pair."""
    unselected = (
        _admission(UNSELECTED_A, "pool-unselected-a"),
        _admission(UNSELECTED_B, "pool-unselected-b"),
    )
    selected = (
        _admission(SELECTED_A, "pool-selected-a"),
        _admission(SELECTED_B, "pool-selected-b"),
    )
    reserve = unselected + selected
    mappings = {
        item.mint: _candidate_mapping(
            item,
            provenance=(
                "LATEST_GRADUATED"
                if item.mint.endswith("-a")
                else "PERSISTED_GRADUATED"
            ),
        )
        for item in reserve
    }
    return GraduatedSupply(
        ready=True,
        terminal="CANDIDATE_SUPPLY_READY",
        graduated_supply=selected,
        graduation_proofs={},
        candidate_a=mappings[SELECTED_A],
        candidate_b=mappings[SELECTED_B],
        two_candidate_selection={
            "ready": True,
            "selected": [mappings[SELECTED_A], mappings[SELECTED_B]],
        },
        handoff_readiness={},
        discovery_report={},
        front_door_report={},
        holder_reserve_supply=reserve,
        holder_reserve_candidates={
            key.lower(): value for key, value in mappings.items()
        },
        diagnostics={"permanent_availability": True},
    )


def _seed_cycle_lineage(db_path, *, request_key_root: str) -> None:
    connection = __import__("sqlite3").connect(db_path)
    request_id = int(
        connection.execute(
            "INSERT INTO printer_source_requests("
            "source_name,request_kind,requested_at,request_key,"
            "source_status,data_quality_label) "
            "VALUES ('dexscreener','pair_market_snapshot',?,?, "
            "'COMPLETE','CLEAN_DATA')",
            (NOW.isoformat(), f"{request_key_root}-market-1"),
        ).lastrowid
    )
    connection.execute(
        "INSERT INTO printer_source_responses("
        "source_request_id,source_name,received_at,source_status,"
        "data_quality_label) VALUES (?,'dexscreener',?,'COMPLETE','CLEAN_DATA')",
        (request_id, NOW.isoformat()),
    )
    connection.commit()
    connection.close()


def _run_later_cycle(tmp_path, holder_facts, *, supply=None):
    path = tmp_path / "slice-i-later-cycle.sqlite3"
    apply_migrations(path)
    frozen = supply or _split_reserve_supply()
    observed_owner_targets: list[str] = []

    def canonical_builder(db_path, **kwargs):
        _seed_cycle_lineage(
            db_path,
            request_key_root=kwargs[
                "campaign_source_request_scope"
            ].request_key_root,
        )
        return frozen

    def holder_owner(received):
        observed_owner_targets.extend(
            item.mint for item in selected_slot_holder_candidates(received)
        )
        return {
            item.mint.lower(): dict(holder_facts[item.mint.lower()])
            for item in selected_slot_holder_candidates(received)
        }

    with patch(
        "printer_v1.operator_cli.later_cycle_graduated_supply.build_graduated_supply",
        side_effect=canonical_builder,
    ):
        result = build_later_cycle_graduated_supply(
            path,
            campaign_id="campaign-i",
            campaign_run_id="run-i",
            authoritative_factory_run_id="factory-i",
            proposed_cycle_id="cycle-2",
            proposed_cycle_ordinal=2,
            evaluated_at=NOW,
            execution_id="execution-i",
            selection_seed="factory-i-cycle-2",
            migration_transport=object(),
            graduated_supply_kwargs={},
            holder_evidence_owner=holder_owner,
        )
    return result, frozen, observed_owner_targets


def _descriptive_fact(reason: str, **extra) -> dict[str, object]:
    payload = {
        "eligible": False,
        "reason": reason,
        "source_name": extra.pop("source_name", None),
        "holder_concentration_label": extra.pop(
            "holder_concentration_label", reason
        ),
        "holder_condition": extra.pop("holder_condition", reason),
    }
    payload.update(extra)
    return payload


def test_reserve_order_differs_from_selected_pair_and_unselected_are_excluded():
    supply = _split_reserve_supply()
    reserve = [item.mint for item in supply.holder_reserve_supply]
    selected = [item.mint for item in supply.graduated_supply]
    assert reserve == [UNSELECTED_A, UNSELECTED_B, SELECTED_A, SELECTED_B]
    assert selected == [SELECTED_A, SELECTED_B]
    assert selected_slot_holder_candidates(supply) == supply.graduated_supply
    assert [item.mint for item in selected_slot_holder_candidates(supply)] == selected
    assert UNSELECTED_A not in {
        item.mint for item in selected_slot_holder_candidates(supply)
    }


def test_production_holder_callers_use_selected_slots_not_reserve():
    owner_src = inspect.getsource(AuthoritativeLiveOperationalCampaignOwner)
    later_src = inspect.getsource(build_later_cycle_graduated_supply)
    assert "selected_slot_holder_candidates" in owner_src
    assert later_src.count("fact.get(\"eligible\") is not True") == 0
    later_owner = owner_src[
        owner_src.index("def holder_evidence_owner") :
        owner_src.index("prior_operations = int")
    ]
    assert "selected_slot_holder_candidates" in later_owner
    assert "holder_reserve_supply" not in later_owner.split("bounded_candidates")[1][
        :240
    ]
    cycle_one = owner_src[
        owner_src.index("holder_transport_before = int") :
        owner_src.index("holder_facts = dict(holder_result.holder_facts)")
    ]
    assert "selected_slot_holder_candidates" in cycle_one
    assert "bounded_candidates=graduated_candidates" not in cycle_one


@pytest.mark.parametrize(
    "fact",
    (
        _descriptive_fact("HOLDER_CONCENTRATION_UNKNOWN"),
        _descriptive_fact("HOLDER_CONCENTRATION_CONCENTRATED"),
        _descriptive_fact("HOLDER_CONCENTRATION_EXTREME"),
        _descriptive_fact("HOLDER_CONCENTRATION_HEALTHY", eligible=True),
        _descriptive_fact(
            "HOLDER_EVIDENCE_UNAVAILABLE",
            holder_concentration_label="HOLDER_CONCENTRATION_UNKNOWN",
            holder_condition="HOLDER_CONCENTRATION_UNKNOWN",
        ),
        _descriptive_fact(
            "HOLDER_CONTEXT_DEADLINE_EXPIRED",
            holder_evidence_status="SOURCE_NOT_EVALUATED_BUDGET_BOUND",
            holder_condition="UNKNOWN",
            holder_concentration_label="HOLDER_CONCENTRATION_UNKNOWN",
        ),
    ),
)
def test_descriptive_holder_states_do_not_block_selected_admission(fact):
    blocked, _reason = holder_fact_blocks_selected_admission(fact)
    assert blocked is False


@pytest.mark.parametrize(
    "fact",
    (
        _descriptive_fact("HOLDER_EVIDENCE_TARGET_MISMATCH"),
        {
            "eligible": False,
            "reason": HANDOFF_ACTIVE_CONFLICT,
            "tracking_handoff_eligible": False,
            "tracking_handoff_reason": HANDOFF_ACTIVE_CONFLICT,
        },
        {
            "eligible": False,
            "reason": HANDOFF_UNSUPPORTED_STATE,
            "tracking_handoff_eligible": False,
            "tracking_handoff_reason": HANDOFF_UNSUPPORTED_STATE,
        },
        _descriptive_fact("HOLDER_EVIDENCE_CROSS_TOKEN"),
    ),
)
def test_identity_and_tracking_failures_still_block_selected_admission(fact):
    blocked, reason = holder_fact_blocks_selected_admission(fact)
    assert blocked is True
    assert reason


@pytest.mark.parametrize(
    "label",
    (
        "HOLDER_CONCENTRATION_UNKNOWN",
        "HOLDER_CONCENTRATION_CONCENTRATED",
        "HOLDER_CONCENTRATION_EXTREME",
        "HOLDER_EVIDENCE_UNAVAILABLE",
    ),
)
def test_later_cycle_descriptive_holder_keeps_selected_pair(tmp_path, label):
    facts = {
        SELECTED_A.lower(): _descriptive_fact(label),
        SELECTED_B.lower(): _descriptive_fact(label),
    }
    result, supply, owner_targets = _run_later_cycle(tmp_path, facts)
    assert owner_targets == [SELECTED_A, SELECTED_B]
    assert [item.mint_identity for item in result.candidates] == [
        SELECTED_A,
        SELECTED_B,
    ]
    assert [item.pair_identity for item in result.candidates] == [
        "pool-selected-a",
        "pool-selected-b",
    ]
    for item in result.candidates:
        evidence = json.loads(item.canonical_evidence_json)
        holder = evidence["holder_evidence"]
        if label.startswith("HOLDER_CONCENTRATION_"):
            assert holder["holder_concentration_label"] == label
        if label != "HOLDER_CONCENTRATION_HEALTHY":
            assert holder.get("holder_concentration_label") != (
                "HOLDER_CONCENTRATION_HEALTHY"
            )
        assert holder["reason"] == label
        assert "SAFE" not in str(holder.get("holder_concentration_label") or "")
        assert item.holder_evidence_eligible is True
    assert [
        item.mint for item in supply.graduated_supply
    ] == [SELECTED_A, SELECTED_B]


def test_later_cycle_unknown_holder_is_not_fabricated_healthy(tmp_path):
    facts = {
        SELECTED_A.lower(): _descriptive_fact("HOLDER_CONCENTRATION_UNKNOWN"),
        SELECTED_B.lower(): _descriptive_fact(
            "HOLDER_EVIDENCE_UNAVAILABLE",
            holder_concentration_label="HOLDER_CONCENTRATION_UNKNOWN",
            holder_condition="UNKNOWN",
        ),
    }
    result, _supply, _targets = _run_later_cycle(tmp_path, facts)
    labels = [
        json.loads(item.canonical_evidence_json)["holder_evidence"][
            "holder_concentration_label"
        ]
        for item in result.candidates
    ]
    assert labels == [
        "HOLDER_CONCENTRATION_UNKNOWN",
        "HOLDER_CONCENTRATION_UNKNOWN",
    ]


def test_later_cycle_target_mismatch_still_blocks(tmp_path):
    facts = {
        SELECTED_A.lower(): _descriptive_fact("HOLDER_EVIDENCE_TARGET_MISMATCH"),
        SELECTED_B.lower(): _descriptive_fact("HOLDER_CONCENTRATION_UNKNOWN"),
    }
    with pytest.raises(
        LaterCycleGraduatedSupplyError,
        match="HOLDER_EVIDENCE_INELIGIBLE:mint-selected-a",
    ):
        _run_later_cycle(tmp_path, facts)


def test_later_cycle_tracking_conflict_still_blocks(tmp_path):
    facts = {
        SELECTED_A.lower(): {
            "eligible": False,
            "reason": HANDOFF_ACTIVE_CONFLICT,
            "tracking_handoff_eligible": False,
            "tracking_handoff_reason": HANDOFF_ACTIVE_CONFLICT,
        },
        SELECTED_B.lower(): _descriptive_fact("HOLDER_CONCENTRATION_UNKNOWN"),
    }
    with pytest.raises(
        LaterCycleGraduatedSupplyError,
        match="HOLDER_EVIDENCE_INELIGIBLE:mint-selected-a",
    ):
        _run_later_cycle(tmp_path, facts)


def test_later_cycle_missing_provenance_still_blocks(tmp_path):
    supply = _split_reserve_supply()
    broken = dict(supply.holder_reserve_candidates)
    broken[SELECTED_A.lower()] = {
        **broken[SELECTED_A.lower()],
        "provenance": "",
    }
    supply = GraduatedSupply(
        ready=supply.ready,
        terminal=supply.terminal,
        graduated_supply=supply.graduated_supply,
        graduation_proofs=supply.graduation_proofs,
        candidate_a=supply.candidate_a,
        candidate_b=supply.candidate_b,
        two_candidate_selection=supply.two_candidate_selection,
        handoff_readiness=supply.handoff_readiness,
        discovery_report=supply.discovery_report,
        front_door_report=supply.front_door_report,
        diagnostics=supply.diagnostics,
        holder_reserve_supply=supply.holder_reserve_supply,
        holder_reserve_candidates=broken,
    )
    facts = {
        SELECTED_A.lower(): _descriptive_fact("HOLDER_CONCENTRATION_UNKNOWN"),
        SELECTED_B.lower(): _descriptive_fact("HOLDER_CONCENTRATION_UNKNOWN"),
    }
    with pytest.raises(
        LaterCycleGraduatedSupplyError,
        match="CANDIDATE_PROVENANCE_MISSING:mint-selected-a",
    ):
        _run_later_cycle(tmp_path, facts, supply=supply)


def test_later_cycle_callback_does_not_add_descriptive_holder_gap():
    src = inspect.getsource(
        AuthoritativeLiveOperationalCampaignOwner._build_later_cycle_discovery_callback
    )
    assert "holder_evidence_eligible" in src
    assert "HOLDER_EVIDENCE_INELIGIBLE" in src


def test_combined_handoff_preserves_explicit_tracking_requalification_contract():
    from printer_v1.discovery import combined_executor

    source = inspect.getsource(combined_executor.CombinedPumpfunCampaignExecutor._handoff_one_slot)
    assert 'holder_fact.get("eligible") is True' in source
    assert 'holder_fact.get("tracking_requalification_required") is True' in source


def test_holder_ceilings_remain_unchanged():
    from printer_v1.operator_cli.holder_reliability_budget_control import (
        HOLDER_WORST_CASE_TRANSPORT_OPERATIONS,
        OPERATION_CEILING,
        PERMANENT_HOLDER_STAGE_TRANSPORT_CEILING,
    )

    assert OPERATION_CEILING == 45
    assert HOLDER_WORST_CASE_TRANSPORT_OPERATIONS == 5
    assert PERMANENT_HOLDER_STAGE_TRANSPORT_CEILING == 8


def _selected_slot_holder_result(
    tmp_path,
    *,
    remaining_stage_operations: int | None = None,
    reuse_second_pass: bool = False,
):
    from datetime import timedelta

    import test_v2_9_8b_holder_partial_accounting_repair as holder_fixtures
    from printer_v1.discovery.combined_executor import FixtureOriginProof
    from printer_v1.operator_cli import holder_reliability_budget_control as budget
    from printer_v1.sources.governed_execution import build_fixture_source_adapter

    connection = holder_fixtures._db(tmp_path)
    called: list[str] = []

    def goplus(**kwargs):
        mint = str(kwargs.get("token_mint") or "")
        called.append(mint.lower())
        return build_fixture_source_adapter(
            "goplus",
            fixture_payload={
                "token_mint": mint,
                "mint_authority": None,
                "freeze_authority": None,
                "metadata_mutable": False,
                "total_supply": "1000000000",
                "top_10_holders": [{"percent": "3"} for _ in range(10)],
                "lp_info": [{"locked": True}],
                "risk_flags": [],
                "underlying_operation_count": 1,
            },
        )

    selected = holder_fixtures._MINTS[:2]
    unselected = holder_fixtures._MINTS[2:]
    proofs = tuple(
        FixtureOriginProof(
            mint=mint,
            signature=f"sig{index}" + "1" * 80,
            slot=432_499_500 + index,
            block_time=1_700_000_000 + index,
            bonding_curve=holder_fixtures._POOLS[index],
            confirmed=True,
        )
        for index, mint in enumerate(selected)
    )
    evaluated = datetime(2026, 8, 4, 17, 0, tzinfo=timezone.utc)
    deadline = evaluated + timedelta(minutes=30)
    ledger = budget.build_ledger_from_exact_counts(
        governed_request_count=11,
        underlying_transport_operations=17,
        deadline_at=deadline,
    )
    owner = AuthoritativeLiveOperationalCampaignOwner()
    kwargs = {
        "command": SimpleNamespace(run_id="run", campaign_id="campaign"),
        "cycle_id": "cycle",
        "bounded_candidates": proofs,
        "evaluated": evaluated,
        "deadline": deadline,
        "ledger": ledger,
        "timeout_seconds": 1.0,
        "context_factories": {"goplus": goplus},
        "request_pacer": budget.SequentialRequestPacer(
            now_fn=lambda: evaluated,
            sleep_fn=lambda _seconds: None,
        ),
        "tracking_pair_by_mint": {
            mint.lower(): holder_fixtures._POOLS[index]
            for index, mint in enumerate(selected)
        },
        "eligible_target": 2,
        "permanent_memory_observation": True,
        "campaign_request_key_root": "campaign-slice-i",
    }
    first = owner._evaluate_holder_eligibility(connection, **kwargs)
    second = None
    if reuse_second_pass:
        second = owner._evaluate_holder_eligibility(
            connection,
            **{
                **kwargs,
                "ledger": first.ledger,
                "cycle_id": "cycle-reuse",
            },
        )
    denied = None
    if remaining_stage_operations is not None:
        denied_calls: list[str] = []

        def denied_goplus(**kwargs):
            denied_calls.append(str(kwargs.get("token_mint") or "").lower())
            raise AssertionError("budget denial must not start holder I/O")

        tight = budget.build_ledger_from_exact_counts(
            governed_request_count=11,
            underlying_transport_operations=26,
            deadline_at=deadline,
        )
        denied = owner._evaluate_holder_eligibility(
            connection,
            **{
                **kwargs,
                "ledger": tight,
                "cycle_id": "cycle-denied",
                "context_factories": {"goplus": denied_goplus},
            },
        )
        denied = (denied, denied_calls)
    return connection, called, selected, unselected, first, second, denied


def test_selected_slot_holder_transports_are_single_owned_and_unselected_are_zero(
    tmp_path,
):
    connection, called, selected, unselected, first, _second, _denied = (
        _selected_slot_holder_result(tmp_path)
    )
    try:
        assert [mint.lower() for mint in selected] == list(called)
        assert all(mint.lower() not in called for mint in unselected)
        assert first.measured_transport_count == len(called)
        assert first.governed_request_count == len(called)
        assert (
            first.ledger_after_holder.underlying_transport_operations
            - first.ledger_before_holder.underlying_transport_operations
            == first.measured_transport_count
        )
        assert first.measured_transport_count == 2
    finally:
        connection.close()


def test_reused_selected_slot_holder_evidence_costs_zero_new_transports(tmp_path):
    connection, first_calls, _selected, _unselected, first, second, _denied = (
        _selected_slot_holder_result(tmp_path, reuse_second_pass=True)
    )
    try:
        assert second is not None
        assert first.measured_transport_count == 2
        assert second.measured_transport_count == 0
        assert second.evaluated_candidate_mints == first.evaluated_candidate_mints
        assert len(first_calls) == 2
        assert (
            second.ledger_after_holder.underlying_transport_operations
            == first.ledger_after_holder.underlying_transport_operations
        )
    finally:
        connection.close()


def test_budget_denial_blocks_selected_slot_lookup_before_io(tmp_path):
    connection, _called, selected, _unselected, _first, _second, denied = (
        _selected_slot_holder_result(tmp_path, remaining_stage_operations=0)
    )
    try:
        result, denied_calls = denied
        assert denied_calls == []
        assert result.measured_transport_count == 0
        assert result.governed_request_count == 0
        assert result.budget_exhausted is True
        for mint in selected:
            fact = result.holder_facts[mint.lower()]
            assert fact["eligible"] is False
            assert fact["holder_condition"] == "UNKNOWN"
            assert fact["holder_evidence_status"] == "SOURCE_NOT_EVALUATED_BUDGET_BOUND"
            blocked, _reason = holder_fact_blocks_selected_admission(fact)
            assert blocked is False
    finally:
        connection.close()
