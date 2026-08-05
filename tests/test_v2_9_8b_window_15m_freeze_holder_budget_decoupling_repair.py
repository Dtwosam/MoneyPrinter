from __future__ import annotations

from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from typing import Any

import pytest

from printer_v1.operator_cli import holder_reliability_budget_control as budget
from printer_v1.operator_cli.authoritative_live_operational_campaign import (
    AuthoritativeLiveOperationalCampaignOwner,
    _graduated_admission_candidate_cap,
    _holder_observation_context,
)
from printer_v1.operator_cli.operational_memory_factory_command import (
    build_pre_holder_accounting_projection,
)
from printer_v1.sources.campaign_six_unit_accounting import CampaignSixUnitOwner
from printer_v1.sources.measured_transport import TransportOperationIdentity
from printer_v1.sources.governed_execution import build_fixture_source_adapter

import test_v2_9_8b_holder_partial_accounting_repair as holder_fixtures


NOW = datetime(2026, 8, 5, 12, 0, tzinfo=timezone.utc)
CAMPAIGN_ID = "campaign-freeze-holder-budget"


def _transport(*, ordinal: int, stage: str = "DIRECT_MIGRATION") -> dict[str, object]:
    return {
        "stage": stage,
        "source_name": "solana_rpc",
        "endpoint_owner": "direct_pump_migration",
        "governed_request_kind": "pump_migration_transaction",
        "method_or_endpoint": "getTransaction",
        "within_request_ordinal": ordinal,
        "target_category": "signature",
        "target_identity": f"signature-{ordinal}",
        "response_bytes": 100 + ordinal,
        "normalized_rows": 1,
        "result": "COMPLETE",
        "reserved_from": None,
    }


def _manifest(*, request_id: int, transport_count: int) -> dict[str, object]:
    return {
        "source_request_id": request_id,
        "source_name": "solana_rpc",
        "request_kind": "pump_migration_transaction",
        "logical_stage_id": f"{CAMPAIGN_ID}|run|cycle|DIRECT_MIGRATION|1",
        "terminal_status": "COMPLETED",
        "transport_identity_count": transport_count,
        "normalized_member_count": 1,
    }


def test_exact_ledger_keeps_governed_requests_separate_from_measured_transports() -> None:
    ledger = budget.build_ledger_from_exact_counts(
        governed_request_count=11,
        underlying_transport_operations=17,
        deadline_at=NOW + timedelta(minutes=15),
    )

    assert ledger.governed_requests == 11
    assert ledger.underlying_transport_operations == 17
    assert ledger.charged_operations == 26
    assert ledger.available_before_reservation == 13
    assert ledger.candidate_cap() == 2


def test_request_count_is_reporting_truth_not_an_operation_charge() -> None:
    low_request_count = budget.build_ledger_from_exact_counts(
        governed_request_count=2,
        underlying_transport_operations=17,
        deadline_at=NOW + timedelta(minutes=15),
    )
    high_request_count = budget.build_ledger_from_exact_counts(
        governed_request_count=20,
        underlying_transport_operations=17,
        deadline_at=NOW + timedelta(minutes=15),
    )

    assert low_request_count.charged_operations == 26
    assert high_request_count.charged_operations == 26
    assert low_request_count.available_before_reservation == 13
    assert high_request_count.available_before_reservation == 13


def test_pre_holder_snapshot_reconciles_request_and_transport_identities_exactly() -> None:
    transports = tuple(_transport(ordinal=index) for index in range(1, 4))
    snapshot = budget.build_pre_holder_budget_snapshot(
        campaign_id=CAMPAIGN_ID,
        governed_request_ids=(41, 42),
        request_manifest=(
            _manifest(request_id=41, transport_count=2),
            _manifest(request_id=42, transport_count=1),
        ),
        campaign_transport_identities=transports,
        action_local_transport_identities=transports,
    )

    assert snapshot.governed_request_ids == (41, 42)
    assert snapshot.governed_request_count == 2
    assert snapshot.measured_transport_count == 3
    assert len(snapshot.measured_transport_identity_keys) == 3
    assert snapshot.zero_transport_operations == 9
    assert snapshot.reserved_snapshot_operations == 2
    assert snapshot.reserved_snapshot_completion_operations == 4


def test_public_accounting_projection_reads_existing_owner_without_closing_it() -> None:
    owner = CampaignSixUnitOwner(
        campaign_id=CAMPAIGN_ID,
        run_id="run",
        cycle_id="cycle",
        started_at=NOW.isoformat(),
    )
    identity = TransportOperationIdentity(
        stage="DIRECT_MIGRATION",
        source_name="solana_rpc",
        endpoint_owner="direct_pump_migration",
        governed_request_kind="pump_migration_transaction",
        method_or_endpoint="getTransaction",
        within_request_ordinal=1,
        target_category="signature",
        target_identity="signature-1",
        response_bytes=101,
        normalized_rows=1,
        result="COMPLETE",
    )
    owner.record_transport(identity)

    projection = build_pre_holder_accounting_projection(
        campaign_units=owner,
        action_local_transport_identities=(identity.as_dict(),),
    )

    assert projection["campaign_transport_identities"] == [identity.as_dict()]
    assert projection["action_local_transport_identities"] == [identity.as_dict()]
    assert projection["campaign_transport_count"] == 1
    assert projection["action_local_transport_count"] == 1
    assert owner.ended_at is None


@pytest.mark.parametrize(
    ("mutation", "expected_code"),
    (
        ("duplicate_transport", "PRE_HOLDER_DUPLICATE_MEASURED_TRANSPORT_IDENTITY"),
        ("request_manifest_mismatch", "PRE_HOLDER_REQUEST_MANIFEST_MISMATCH"),
        ("missing_campaign_ownership", "PRE_HOLDER_REQUEST_CAMPAIGN_OWNERSHIP_MISSING"),
        ("transport_count_without_identity", "PRE_HOLDER_TRANSPORT_COUNT_WITHOUT_IDENTITIES"),
        ("stage_campaign_mismatch", "PRE_HOLDER_STAGE_CAMPAIGN_RECONCILIATION_MISMATCH"),
    ),
)
def test_pre_holder_snapshot_fails_closed_on_inconsistent_accounting(
    mutation: str,
    expected_code: str,
) -> None:
    transports = [_transport(ordinal=1), _transport(ordinal=2)]
    action_local = list(transports)
    request_ids = [41]
    manifest = [_manifest(request_id=41, transport_count=2)]

    if mutation == "duplicate_transport":
        transports.append(dict(transports[0]))
        action_local.append(dict(action_local[0]))
        manifest[0]["transport_identity_count"] = 3
    elif mutation == "request_manifest_mismatch":
        request_ids.append(42)
    elif mutation == "missing_campaign_ownership":
        manifest[0]["logical_stage_id"] = "other-campaign|run|cycle|DIRECT_MIGRATION|1"
    elif mutation == "transport_count_without_identity":
        manifest[0]["transport_identity_count"] = 3
    elif mutation == "stage_campaign_mismatch":
        action_local[1] = _transport(ordinal=3)

    with pytest.raises(budget.HolderBudgetError) as raised:
        budget.build_pre_holder_budget_snapshot(
            campaign_id=CAMPAIGN_ID,
            governed_request_ids=tuple(request_ids),
            request_manifest=tuple(manifest),
            campaign_transport_identities=tuple(transports),
            action_local_transport_identities=tuple(action_local),
        )

    assert raised.value.code == expected_code


def test_legacy_ledger_retains_explicit_request_equals_transport_compatibility() -> None:
    ledger = budget.build_ledger(
        pump_operations=7,
        additional_governed_operations=4,
        deadline_at=NOW + timedelta(minutes=15),
    )

    assert ledger.governed_requests == 11
    assert ledger.underlying_transport_operations == 11
    assert ledger.charged_operations == 20


def test_holder_attempt_admission_is_non_mutating_and_enforces_campaign_and_stage_budget() -> None:
    ledger = budget.build_ledger_from_exact_counts(
        governed_request_count=11,
        underlying_transport_operations=17,
        deadline_at=NOW + timedelta(minutes=15),
    )

    allowed = budget.holder_attempt_admission(
        ledger,
        now=NOW,
        permanent_stage_operations_used=3,
    )
    stage_exhausted = budget.holder_attempt_admission(
        ledger,
        now=NOW,
        permanent_stage_operations_used=4,
    )
    deadline_expired = budget.holder_attempt_admission(
        ledger,
        now=NOW + timedelta(minutes=16),
        permanent_stage_operations_used=0,
    )

    assert allowed.allowed is True
    assert allowed.available_operations == 13
    assert allowed.required_worst_case_operations == 5
    assert allowed.permanent_stage_operations_used == 3
    assert allowed.permanent_stage_operations_remaining == 5
    assert stage_exhausted.allowed is False
    assert stage_exhausted.reason == "HOLDER_CONTEXT_BUDGET_EXHAUSTED"
    assert deadline_expired.allowed is False
    assert deadline_expired.deadline_expired is True
    assert ledger.underlying_transport_operations == 17


def test_permanent_admission_never_consults_holder_candidate_cap() -> None:
    class LedgerWhoseHolderCapMustNotBeRead:
        def candidate_cap(self) -> int:
            raise AssertionError("permanent observation admission consulted holder cap")

    assert _graduated_admission_candidate_cap(
        permanent_memory_observation=True,
        ledger=LedgerWhoseHolderCapMustNotBeRead(),
    ) == 8


def test_legacy_admission_retains_holder_coupled_candidate_cap() -> None:
    class LegacyLedger:
        def candidate_cap(self) -> int:
            return 3

    assert _graduated_admission_candidate_cap(
        permanent_memory_observation=False,
        ledger=LegacyLedger(),
    ) == 3


def test_unattempted_holder_fact_converts_to_exact_budget_bound_unknown_context() -> None:
    context = _holder_observation_context(
        {
            "eligible": False,
            "holder_condition": "UNKNOWN",
            "holder_evidence_status": "SOURCE_NOT_EVALUATED_BUDGET_BOUND",
            "future_action_eligibility": "BLOCKED_OR_UNKNOWN",
            "source_name": None,
            "source_request_ids": [],
        }
    )

    assert context == {
        "holder_condition": "UNKNOWN",
        "holder_evidence_status": "SOURCE_NOT_EVALUATED_BUDGET_BOUND",
        "future_action_eligibility": "BLOCKED_OR_UNKNOWN",
        "fully_eligible": False,
    }


@pytest.mark.parametrize(
    ("fact", "fully_eligible"),
    (
        (
            {
                "eligible": True,
                "holder_concentration_label": "HOLDER_CONCENTRATION_HEALTHY",
                "source_name": "goplus",
            },
            True,
        ),
        (
            {
                "eligible": False,
                "holder_concentration_label": "HOLDER_CONCENTRATION_EXTREME",
                "reason": "HOLDER_CONCENTRATION_EXTREME",
                "source_name": "goplus",
            },
            False,
        ),
        ({}, False),
    ),
)
def test_only_actual_holder_pass_converts_to_fully_eligible(
    fact: dict[str, object],
    fully_eligible: bool,
) -> None:
    context = _holder_observation_context(fact)

    assert context["fully_eligible"] is fully_eligible
    assert context["future_action_eligibility"] == "BLOCKED_OR_UNKNOWN"


def _evaluate_permanent_holder_context(
    connection,
    *,
    per_candidate_transport_cost: int | tuple[int, ...],
):
    def goplus(**kwargs: Any):
        mint = str(kwargs.get("token_mint") or "")
        if isinstance(per_candidate_transport_cost, tuple):
            transport_cost = per_candidate_transport_cost[
                holder_fixtures._MINTS.index(mint)
            ]
        else:
            transport_cost = per_candidate_transport_cost
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
                "underlying_operation_count": transport_cost,
            },
        )

    proofs = tuple(
        SimpleNamespace(mint=mint, bonding_curve=holder_fixtures._POOLS[index], block_time=0)
        for index, mint in enumerate(holder_fixtures._MINTS)
    )
    ledger = budget.build_ledger_from_exact_counts(
        governed_request_count=11,
        underlying_transport_operations=17,
        deadline_at=NOW + timedelta(minutes=30),
    )
    return AuthoritativeLiveOperationalCampaignOwner()._evaluate_holder_eligibility(
        connection,
        command=SimpleNamespace(run_id="run", campaign_id="campaign"),
        cycle_id="cycle",
        bounded_candidates=proofs,
        evaluated=NOW,
        deadline=NOW + timedelta(minutes=30),
        ledger=ledger,
        timeout_seconds=1.0,
        context_factories={"goplus": goplus},
        request_pacer=budget.SequentialRequestPacer(
            now_fn=lambda: NOW,
            sleep_fn=lambda _seconds: None,
        ),
        tracking_pair_by_mint={
            mint.lower(): holder_fixtures._POOLS[index]
            for index, mint in enumerate(holder_fixtures._MINTS)
        },
        eligible_target=4,
        permanent_memory_observation=True,
    )


def test_low_cost_holder_context_evaluates_all_four_when_budget_permits(tmp_path) -> None:
    connection = holder_fixtures._db(tmp_path)
    try:
        result = _evaluate_permanent_holder_context(
            connection,
            per_candidate_transport_cost=1,
        )

        assert result.evaluated_candidate_mints == tuple(
            mint.lower() for mint in holder_fixtures._MINTS
        )
        assert result.unattempted_candidate_mints == ()
        assert result.budget_exhausted is False
        assert result.measured_transport_count == 4
        assert result.governed_request_count == 4
        assert result.ledger_before_holder.underlying_transport_operations == 17
        assert result.ledger_after_holder.underlying_transport_operations == 21
        assert len(result.holder_attempt_budget_trace) == 4
    finally:
        connection.close()


@pytest.mark.parametrize(
    ("transport_costs", "evaluated_count"),
    (((1, 1, 2, 2), 3), ((3, 3, 3, 3), 2)),
)
def test_higher_cost_holder_context_stops_without_request_or_exception(
    tmp_path,
    transport_costs: tuple[int, ...],
    evaluated_count: int,
) -> None:
    connection = holder_fixtures._db(tmp_path)
    try:
        result = _evaluate_permanent_holder_context(
            connection,
            per_candidate_transport_cost=transport_costs,
        )
        expected_evaluated = tuple(
            mint.lower() for mint in holder_fixtures._MINTS[:evaluated_count]
        )
        expected_unattempted = tuple(
            mint.lower() for mint in holder_fixtures._MINTS[evaluated_count:]
        )

        assert result.evaluated_candidate_mints == expected_evaluated
        assert result.unattempted_candidate_mints == expected_unattempted
        assert result.budget_exhausted is True
        assert result.budget_exhaustion_reason == "HOLDER_CONTEXT_BUDGET_EXHAUSTED"
        assert result.governed_request_count == evaluated_count
        assert len(result.source_request_ids) == evaluated_count
        durable_request_count = connection.execute(
            "SELECT COUNT(*) FROM printer_source_requests"
        ).fetchone()[0]
        assert durable_request_count == evaluated_count
        for mint in expected_unattempted:
            assert result.holder_facts[mint] == {
                "eligible": False,
                "holder_condition": "UNKNOWN",
                "holder_evidence_status": "SOURCE_NOT_EVALUATED_BUDGET_BOUND",
                "future_action_eligibility": "BLOCKED_OR_UNKNOWN",
                "source_name": None,
                "source_request_ids": [],
            }
    finally:
        connection.close()
