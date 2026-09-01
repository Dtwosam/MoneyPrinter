from __future__ import annotations

import inspect


def test_continuation_helper_does_not_accept_temporal_owner_runtime_facts():
    from printer_v1.discovery.eligible_token_supply import (
        decide_pre_lifecycle_supply_continuation,
    )

    signature = inspect.signature(decide_pre_lifecycle_supply_continuation)
    for forbidden in (
        "supervision_active",
        "cancellation_requested",
        "pending_refresh_exists",
    ):
        assert forbidden not in signature.parameters

    decision = decide_pre_lifecycle_supply_continuation(
        freeze_ready_depth=2,
        enrichment_work_remaining=False,
        source_operations_remaining=4,
        acquisition_deadline_at="2026-09-01T00:20:00+00:00",
        now="2026-09-01T00:00:00+00:00",
        universe_state="ALL_REACHABLE_CANDIDATES_EVALUATED",
        refresh_interval_seconds=600,
    )
    assert decision.status == "WAITING_FOR_ELIGIBLE_SUPPLY"
    assert decision.final_terminal_cause is None


def test_no_lawful_static_refresh_window_can_close_as_coverage_insufficient():
    from printer_v1.discovery.eligible_token_supply import (
        PRE_LIFECYCLE_DISCOVERY_SELECTION_COVERAGE_INSUFFICIENT,
        decide_pre_lifecycle_supply_continuation,
    )

    decision = decide_pre_lifecycle_supply_continuation(
        freeze_ready_depth=2,
        enrichment_work_remaining=False,
        source_operations_remaining=4,
        acquisition_deadline_at="2026-09-01T00:05:00+00:00",
        now="2026-09-01T00:00:00+00:00",
        universe_state="ALL_REACHABLE_CANDIDATES_EVALUATED",
        refresh_interval_seconds=600,
    )
    assert (
        decision.status
        == PRE_LIFECYCLE_DISCOVERY_SELECTION_COVERAGE_INSUFFICIENT
    )


def test_production_supply_delegates_temporal_runtime_truth_to_owner():
    import printer_v1.discovery.eligible_token_supply as supply

    source = inspect.getsource(supply.run_persistent_eligible_token_supply)
    assert "supervision_active=True" not in source
    assert "cancellation_requested=False" not in source
    assert "pending_refresh_exists=False" not in source

    marker = "continuation = decide_pre_lifecycle_supply_continuation("
    start = source.index(marker)
    end = source.index("if ready:", start)
    block = source[start:end]
    assert "_request_temporal_refresh(" in block
    assert "CURRENT_UNIVERSE_EXHAUSTION_REASONS" in source[:start]
