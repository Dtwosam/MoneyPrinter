from __future__ import annotations

from datetime import datetime, timezone
from types import SimpleNamespace

import pytest


def test_later_cycle_refresh_preserves_canonical_zero_freeze_ready_depth(monkeypatch):
    """Canonical freeze-ready zero must not fall back to a noncanonical reserve count."""
    from printer_v1.operator_cli import authoritative_live_operational_campaign as campaign
    from printer_v1.operator_cli import later_cycle_graduated_supply as later_supply
    from printer_v1.db import sqlite_write_contracts as sqlite_contracts

    class CaptureCallback(RuntimeError):
        pass

    class FakeConnection:
        def close(self) -> None:
            pass

    class RefreshOutcome:
        status = "WAITING_FOR_ELIGIBLE_SUPPLY"
        source_operations = 0
        source_request_coverage = ()
        next_governed_request_worst_case_seconds = 1.0

        def to_dict(self):
            return {
                "status": self.status,
                "source_operations": self.source_operations,
            }

    class ChildRefreshOwner:
        acquisition_deadline_at = "2026-09-01T20:00:00+00:00"

        def __init__(self) -> None:
            self.reserve_depths: list[int] = []

        def request_temporal_refresh(self, *, reserve_depth: int, **kwargs):
            self.reserve_depths.append(reserve_depth)
            return RefreshOutcome()

    child_refresh_owner = ChildRefreshOwner()

    class RootRefreshOwner:
        def for_cycle(self, **kwargs):
            return child_refresh_owner

    build_calls = 0

    def fake_build_later_cycle_graduated_supply(*args, **kwargs):
        nonlocal build_calls
        build_calls += 1
        return SimpleNamespace(
            terminal_cause="WAITING_FOR_ELIGIBLE_SUPPLY",
            diagnostics={
                "stage_local_source_requests": 0,
                "campaign_source_request_coverage": [],
                "freeze_ready_depth": 0,
                "eligible_reserve_count": 4,
                "next_cooperative_phase": "MARKET_DISCOVERY",
                "scheduler_yield": {"refresh_ordinal": 1},
            },
        )

    monkeypatch.setattr(
        later_supply,
        "build_later_cycle_graduated_supply",
        fake_build_later_cycle_graduated_supply,
    )
    monkeypatch.setattr(later_supply, "_source_lineage", lambda *args, **kwargs: ())
    monkeypatch.setattr(
        sqlite_contracts,
        "connect_operational",
        lambda *args, **kwargs: FakeConnection(),
    )

    owner = campaign.AuthoritativeLiveOperationalCampaignOwner()
    captured: dict[str, object] = {}

    def capture_callback(*, candidate_supply, **kwargs):
        captured["candidate_supply"] = candidate_supply
        raise CaptureCallback()

    monkeypatch.setattr(owner, "_build_later_cycle_discovery_callback", capture_callback)

    command = SimpleNamespace(
        db_path="unused.sqlite3",
        configuration_id="cfg",
        ceilings=SimpleNamespace(duration_seconds=60),
    )
    with pytest.raises(CaptureCallback):
        owner.run_operational(
            command=command,
            pump_transport=object(),
            source_governor=object(),
            central_scheduler=object(),
            selection_seed="seed",
            cycle_id="cycle-1",
            cycle_cutoff="2026-09-01T19:00:00+00:00",
            evaluated_at="2026-09-01T19:00:00+00:00",
            backup_path="unused.backup",
            lifecycle_kwargs={"four_token_proof_controller": object()},
            migration_transport=object(),
            pre_lifecycle_temporal_refresh_owner=RootRefreshOwner(),
        )

    candidate_supply = captured["candidate_supply"]
    context = {
        "campaign_id": "campaign",
        "campaign_run_id": "campaign-run",
        "authoritative_factory_run_id": "factory-run",
        "proposed_cycle_id": "cycle-2",
        "proposed_cycle_ordinal": 2,
        "cycle_cutoff": "2026-09-01T19:00:00+00:00",
        "evaluated_at": datetime(2026, 9, 1, 19, 1, tzinfo=timezone.utc),
        "selection_seed": "cycle-2-seed",
        "source_governor": object(),
        "central_scheduler": object(),
        "admission_health": object(),
    }

    first = candidate_supply(**context)
    assert first.terminal_cause == "WAITING_FOR_ELIGIBLE_SUPPLY"
    assert build_calls == 1

    second = candidate_supply(**context)
    assert second.terminal_cause == "WAITING_FOR_ELIGIBLE_SUPPLY"
    assert child_refresh_owner.reserve_depths == [0]
