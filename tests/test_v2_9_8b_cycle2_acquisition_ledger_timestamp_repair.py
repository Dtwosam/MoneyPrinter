from __future__ import annotations

from types import SimpleNamespace

from printer_v1.discovery.eligible_token_supply import (
    _build_temporal_acquisition_ledger,
)


def test_later_cycle_ledger_uses_actual_rebound_start_and_effective_horizon() -> None:
    owner = SimpleNamespace(
        acquisition_started_at="2026-09-12T12:53:43.814174+00:00",
        acquisition_deadline_at="2026-09-12T13:03:10.513888+00:00",
        refresh_interval_seconds=600,
    )

    ledger = _build_temporal_acquisition_ledger(
        temporal_refresh_owner=owner,
        deadline_at=owner.acquisition_deadline_at,
        now="2026-09-12T12:53:43.814174+00:00",
    )

    assert ledger.started_at == owner.acquisition_started_at
    assert ledger.acquisition_deadline_at == owner.acquisition_deadline_at
    assert ledger.acquisition_duration_seconds == 566
    assert ledger.elapsed_seconds("2026-09-12T12:58:14.223914+00:00") < 271
