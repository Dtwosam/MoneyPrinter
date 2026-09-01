from __future__ import annotations

from pathlib import Path
import sys


def replace_once(path: str, old: str, new: str) -> None:
    p = Path(path)
    text = p.read_text()
    count = text.count(old)
    if count != 1:
        raise SystemExit(f"{path}: expected one replacement, found {count}")
    p.write_text(text.replace(old, new, 1))


def write_tests() -> None:
    Path("tests/test_v2_9_8b_continuation_owner_truth.py").write_text(
        '''from __future__ import annotations

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
'''
    )


def apply_patch() -> None:
    path = "src/printer_v1/discovery/eligible_token_supply.py"

    replace_once(
        path,
        '''    universe_state: str,\n    supervision_active: bool,\n    cancellation_requested: bool,\n    pending_refresh_exists: bool,\n    refresh_interval_seconds: int = 600,\n''',
        '''    universe_state: str,\n    refresh_interval_seconds: int = 600,\n''',
    )
    replace_once(
        path,
        '''    from printer_v1.discovery.pre_lifecycle_temporal_acquisition import (\n        evaluate_wait_eligibility,\n        refresh_window_fits,\n    )\n''',
        '''    from printer_v1.discovery.pre_lifecycle_temporal_acquisition import (\n        refresh_window_fits,\n    )\n''',
    )
    replace_once(
        path,
        '''    if refresh_window_fits(\n        now=now,\n        acquisition_deadline_at=acquisition_deadline_at,\n        refresh_interval_seconds=int(refresh_interval_seconds),\n    ):\n        eligibility = evaluate_wait_eligibility(\n            reserve_depth=int(freeze_ready_depth),\n            required_capacity=threshold,\n            universe_state=str(universe_state),\n            now=now,\n            acquisition_deadline_at=acquisition_deadline_at,\n            source_operations_remaining=int(source_operations_remaining),\n            provider_terminal_failure=False,\n            supervision_active=bool(supervision_active),\n            cancellation_requested=bool(cancellation_requested),\n            pending_refresh_exists=bool(pending_refresh_exists),\n        )\n        if eligibility.eligible:\n            return PreLifecycleSupplyContinuationDecision(\n                status=WAITING_FOR_ELIGIBLE_SUPPLY,\n                final_terminal_cause=None,\n            )\n''',
        '''    if (\n        str(universe_state) in CURRENT_UNIVERSE_EXHAUSTION_REASONS\n        and int(source_operations_remaining) > 0\n        and refresh_window_fits(\n            now=now,\n            acquisition_deadline_at=acquisition_deadline_at,\n            refresh_interval_seconds=int(refresh_interval_seconds),\n        )\n    ):\n        # Runtime supervision, cancellation, and pending-refresh truth belongs\n        # exclusively to the temporal owner. This helper only establishes that\n        # another refresh is statically possible under capacity/horizon/budget.\n        return PreLifecycleSupplyContinuationDecision(\n            status=WAITING_FOR_ELIGIBLE_SUPPLY,\n            final_terminal_cause=None,\n        )\n''',
    )
    replace_once(
        path,
        '''            and temporal_refresh_owner is not None\n            and acquisition_ledger is not None\n            and deadline_dt is not None\n        ):\n''',
        '''            and temporal_refresh_owner is not None\n            and acquisition_ledger is not None\n            and deadline_dt is not None\n            and last_stop_reason in CURRENT_UNIVERSE_EXHAUSTION_REASONS\n        ):\n''',
    )
    replace_once(
        path,
        '''                universe_state=(\n                    last_stop_reason\n                    if last_stop_reason\n                    in {\n                        "ALL_REACHABLE_CANDIDATES_EVALUATED",\n                        "NO_ADDITIONAL_UNIQUE_CANDIDATES_REACHABLE",\n                    }\n                    else "ALL_REACHABLE_CANDIDATES_EVALUATED"\n                ),\n                supervision_active=True,\n                cancellation_requested=False,\n                pending_refresh_exists=False,\n''',
        '''                universe_state=str(last_stop_reason),\n''',
    )

    reliability_path = (
        "tests/test_v2_9_8b_freeze_ready_candidate_supply_reliability.py"
    )
    replace_once(
        reliability_path,
        '''        acquisition_deadline_at="2026-09-01T12:16:19+00:00",\n        now=NOW,\n        universe_state="ALL_REACHABLE_CANDIDATES_EVALUATED",\n        supervision_active=True,\n        cancellation_requested=False,\n        pending_refresh_exists=False,\n        refresh_interval_seconds=600,\n''',
        '''        acquisition_deadline_at="2026-09-01T12:16:19+00:00",\n        now=NOW,\n        universe_state="ALL_REACHABLE_CANDIDATES_EVALUATED",\n        refresh_interval_seconds=600,\n''',
    )
    replace_once(
        reliability_path,
        '''        acquisition_deadline_at="2026-09-01T11:40:00+00:00",\n        now="2026-09-01T11:39:30+00:00",\n        universe_state="ALL_REACHABLE_CANDIDATES_EVALUATED",\n        supervision_active=True,\n        cancellation_requested=False,\n        pending_refresh_exists=False,\n        refresh_interval_seconds=600,\n''',
        '''        acquisition_deadline_at="2026-09-01T11:40:00+00:00",\n        now="2026-09-01T11:39:30+00:00",\n        universe_state="ALL_REACHABLE_CANDIDATES_EVALUATED",\n        refresh_interval_seconds=600,\n''',
    )


if __name__ == "__main__":
    mode = sys.argv[1] if len(sys.argv) > 1 else ""
    if mode == "tests":
        write_tests()
    elif mode == "patch":
        apply_patch()
    else:
        raise SystemExit("usage: assistant_continuation_owner_fix.py tests|patch")
