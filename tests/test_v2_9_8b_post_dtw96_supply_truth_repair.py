from __future__ import annotations

import inspect

import pytest

from printer_v1.discovery import eligible_token_supply as ets
from printer_v1.discovery import permanent_discovery_availability as pda
from printer_v1.operator_cli import authoritative_live_operational_campaign as live
from printer_v1.operator_cli import graduated_supply_front_door as front


def test_reconciliation_fallback_cap_is_pre_io_contract() -> None:
    limiter = getattr(pda, "_bounded_geckoterminal_fallback_limit", None)
    assert limiter is not None, "DTW96 RED: pre-I/O fallback limiter is missing"

    assert limiter(unresolved_count=6, max_fallbacks=0) == 0
    assert limiter(unresolved_count=6, max_fallbacks=2) == 2
    assert limiter(unresolved_count=9, max_fallbacks=None) == 6
    assert limiter(unresolved_count=1, max_fallbacks=6) == 1
    with pytest.raises(ValueError, match="INVALID_RECONCILIATION_FALLBACK_CAP"):
        limiter(unresolved_count=1, max_fallbacks=-1)

    signature = inspect.signature(pda.run_dexscreener_batch_market_resolution)
    assert "max_geckoterminal_fallbacks" in signature.parameters


def test_permanent_outer_ready_cannot_override_persistent_not_ready() -> None:
    compose_ready = getattr(front, "_compose_graduated_supply_ready", None)
    assert compose_ready is not None, "DTW96 RED: permanent readiness combiner is missing"

    assert compose_ready(
        persistent_ready=False,
        authority_ready=True,
        supply_count=2,
        required_token_capacity=2,
        permanent_availability=True,
    ) is False
    assert compose_ready(
        persistent_ready=True,
        authority_ready=True,
        supply_count=2,
        required_token_capacity=2,
        permanent_availability=True,
    ) is True
    # Non-permanent compatibility: existing two-candidate readiness is unchanged.
    assert compose_ready(
        persistent_ready=False,
        authority_ready=True,
        supply_count=2,
        required_token_capacity=2,
        permanent_availability=False,
    ) is True


def test_lawful_work_remaining_outranks_tracking_shortage_mask() -> None:
    classify = getattr(ets, "_apply_permanent_shortage_precedence", None)
    assert classify is not None, "DTW96 RED: shortage precedence owner is missing"

    tracking = {
        "mint-a": {"eligible_for_evidence": False},
        "mint-b": {"eligible_for_evidence": True},
    }
    assert classify(
        shortage=ets.TRUE_MARKET_SUPPLY_SHORTAGE,
        last_stop_reason="LAWFUL_WORK_REMAINING_WITH_CAPACITY",
        tracking_dispositions=tracking,
        provider_failures=0,
        channels_unavailable=(),
        liquidity_source_unavailable=0,
        liquidity_stale_or_rate_limited=0,
        liquidity_malformed_or_partial=0,
        true_budget_exhausted=False,
        duration_exhausted=False,
    ) == ets.DISCOVERY_ARCHITECTURE_FALSE_SHORTAGE

    assert classify(
        shortage=ets.TRUE_MARKET_SUPPLY_SHORTAGE,
        last_stop_reason="ALL_REACHABLE_CANDIDATES_EVALUATED",
        tracking_dispositions=tracking,
        provider_failures=0,
        channels_unavailable=(),
        liquidity_source_unavailable=0,
        liquidity_stale_or_rate_limited=0,
        liquidity_malformed_or_partial=0,
        true_budget_exhausted=False,
        duration_exhausted=False,
    ) == ets.TRACKING_STATE_CAPACITY_BLOCKED


def test_terminal_certificate_projection_preserves_existing_authority() -> None:
    projector = getattr(live, "_project_supply_exhaustion_certificate", None)
    assert projector is not None, "DTW96 RED: terminal certificate projector is missing"

    certificate = {
        "certificate_id": "exh-dtw96-fixture",
        "required_eligible_capacity": 4,
        "eligible_reserve_count": 3,
        "shortage_classification": "TRACKING_STATE_CAPACITY_BLOCKED",
    }
    projected = projector({"exhaustion_certificate": certificate})
    assert projected == certificate
    assert projector({}) is None


def test_post_call_reconciliation_charge_cannot_exceed_pre_io_offer() -> None:
    validate = getattr(ets, "_validate_reconciliation_stage_charge", None)
    assert validate is not None, "DTW96 RED: reconciliation charge invariant is missing"

    assert validate(offered=2, actual=2) == 2
    assert validate(offered=2, actual=0) == 0
    with pytest.raises(
        ets.EligibleTokenSupplyError,
        match="RECONCILIATION_STAGE_CAPACITY_OVERRUN",
    ):
        validate(offered=1, actual=2)


def test_locked_capacity_and_reservations_are_unchanged() -> None:
    assert pda.MINIMUM_FREEZE_DEPTH == 4
    assert ets.REQUIRED_TOKEN_CAPACITY == 2
    assert tuple(pda.STAGE_RESERVATIONS) == (
        ("intake", 3),
        ("market_batching", 2),
        ("reconciliation", 6),
        ("protocol_confirmation", 7),
        ("holder_safety", 8),
        ("final_refresh_handoff", 4),
    )
