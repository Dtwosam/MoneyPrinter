from __future__ import annotations

import sqlite3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from printer_v1.discovery import pre_lifecycle_refresh_composition as composition
from printer_v1.discovery.pre_lifecycle_temporal_acquisition import (
    PRE_LIFECYCLE_ACQUISITION_DURATION_SECONDS,
    acquisition_deadline_at,
    refresh_window_fits,
)


def test_horizon_allows_three_delayed_refreshes_only():
    assert PRE_LIFECYCLE_ACQUISITION_DURATION_SECONDS == 2400
    start = "2026-08-16T00:00:00+00:00"
    deadline = acquisition_deadline_at(start)
    assert refresh_window_fits(now=start, acquisition_deadline_at=deadline, refresh_interval_seconds=600)
    assert refresh_window_fits(now="2026-08-16T00:10:00+00:00", acquisition_deadline_at=deadline, refresh_interval_seconds=600)
    assert refresh_window_fits(now="2026-08-16T00:20:00+00:00", acquisition_deadline_at=deadline, refresh_interval_seconds=600)
    assert not refresh_window_fits(now="2026-08-16T00:30:00+00:00", acquisition_deadline_at=deadline, refresh_interval_seconds=600)


def _install_stage_fakes(monkeypatch, calls):
    def fake_pump(*args, **kwargs):
        calls.append("pump")
        return {
            "status": "COMPLETE",
            "source_request_ids": [101, 102],
            "verifications": [
                {"mint": "MINT_A", "pool": "POOL_A", "verified": True},
                {"mint": "MINT_REJECT", "pool": "POOL_REJECT", "verified": False},
            ],
        }

    def fake_locator(*args, **kwargs):
        calls.append("dex")
        return {
            "status": "ok",
            "source_requests": 1,
            "request_id": 201,
            "response_id": 202,
            "pool_observations": [
                {"mint": "MINT_B", "pool": "POOL_B", "liquidity_usd": 5000},
            ],
        }

    def fake_gt(*args, **kwargs):
        calls.append("gt")
        return {
            "status": "COMPLETE",
            "failure_type": None,
            "source_requests": 1,
            "nominations": [
                {"mint": "MINT_B", "pool": "POOL_B", "liquidity_usd": 5000},
                {"mint": "MINT_C", "pool": "POOL_C", "liquidity_usd": 6000},
            ],
        }

    def fake_backup(*args, **kwargs):
        calls.append("backup")
        return {"source_requests": 0, "accounting_blocker": False}

    def fake_protocol(*args, **kwargs):
        calls.append("protocol")
        return {
            "source_requests": 1,
            "shared_source_failures": 0,
            "promoted_observation_eligible": [
                {"mint": "MINT_C", "pool": "POOL_C"},
            ],
        }

    monkeypatch.setattr(
        "printer_v1.discovery.direct_migration_discovery.run_direct_migration_discovery",
        fake_pump,
    )
    monkeypatch.setattr(
        "printer_v1.operator_cli.graduated_supply_front_door.run_fresh_profile_locator",
        fake_locator,
    )
    monkeypatch.setattr(composition, "run_geckoterminal_fresh_nomination", fake_gt)
    monkeypatch.setattr(composition, "run_bounded_unknown_liquidity_backup", fake_backup)
    monkeypatch.setattr(composition, "process_protocol_confirmation_queue", fake_protocol)
    monkeypatch.setattr(
        composition,
        "record_fresh_pool_nominations",
        lambda *args, **kwargs: {"accepted": list(kwargs["observations"]), "exclusions": []},
    )


def _stage(tmp_path, monkeypatch, calls):
    _install_stage_fakes(monkeypatch, calls)
    return composition.build_pre_lifecycle_refresh_stage(
        db_path=tmp_path / "proof.sqlite3",
        request_key_prefix="proof",
        migration_transport=lambda _ctx: {},
        locator_transport=lambda _ctx: {},
    )


def _run(stage, *, remaining=30, ordinal=1):
    return stage(
        sqlite3.connect(":memory:"),
        campaign_id="c",
        run_id="r",
        cycle_id="y",
        discovery_work_id=f"w{ordinal}",
        scheduler_job_id=ordinal,
        refresh_ordinal=ordinal,
        source_operations_remaining=remaining,
        now=f"2026-08-16T00:{ordinal * 10:02d}:00+00:00",
    )


def test_full_refresh_round_rotates_sources_and_dedups_exact_identities(tmp_path, monkeypatch):
    calls = []
    stage = _stage(tmp_path, monkeypatch, calls)
    first = _run(stage, remaining=30, ordinal=1)
    assert calls[:3] == ["pump", "dex", "gt"]
    assert calls[3:] == ["backup", "protocol"]
    assert first["source_operations"] == 5
    assert first["channels_unavailable"] == ()
    assert first["newly_observed_exact_identities"] == (
        {"mint": "MINT_A", "pool": "POOL_A"},
        {"mint": "MINT_B", "pool": "POOL_B"},
        {"mint": "MINT_C", "pool": "POOL_C"},
    )
    assert first["promoted_observation_eligible"] == ({"mint": "MINT_C", "pool": "POOL_C"},)

    calls.clear()
    second = _run(stage, remaining=25, ordinal=2)
    assert calls[:3] == ["dex", "gt", "pump"]
    assert second["source_operations"] == 5


def test_low_remaining_budget_skips_pump_but_keeps_peer_sources(tmp_path, monkeypatch):
    calls = []
    stage = _stage(tmp_path, monkeypatch, calls)
    result = _run(stage, remaining=3)
    assert "pump" not in calls
    assert calls[:2] == ["dex", "gt"]
    assert result["source_operations"] <= 3
    assert any(
        item["channel"] == composition.PUMP_FRESH_CHANNEL
        and item["reason"] == "INSUFFICIENT_WORST_CASE_SOURCE_BUDGET"
        for item in result["channels_skipped"]
    )


def test_candidate_local_pump_rejection_does_not_stop_peer_sources(tmp_path, monkeypatch):
    calls = []
    stage = _stage(tmp_path, monkeypatch, calls)
    result = _run(stage)
    assert calls[:3] == ["pump", "dex", "gt"]
    assert result["provider_failures"] == 0
    assert {x["mint"] for x in result["newly_observed_exact_identities"]} == {"MINT_A", "MINT_B", "MINT_C"}


def test_source_local_geckoterminal_failure_does_not_suppress_other_channels(tmp_path, monkeypatch):
    calls = []
    stage = _stage(tmp_path, monkeypatch, calls)

    def failing_gt(*args, **kwargs):
        calls.append("gt")
        return {
            "status": "FAILED",
            "failure_type": "fixture_gt_unavailable",
            "source_requests": 1,
            "nominations": [],
        }

    monkeypatch.setattr(composition, "run_geckoterminal_fresh_nomination", failing_gt)
    result = _run(stage)
    assert calls[:3] == ["pump", "dex", "gt"]
    assert "backup" in calls
    assert "protocol" in calls
    assert result["provider_failures"] == 1
    assert result["channels_unavailable"] == (composition.GECKOTERMINAL_NOMINATION_CHANNEL,)
    assert {x["mint"] for x in result["newly_observed_exact_identities"]} == {"MINT_A", "MINT_B"}


def test_zero_budget_performs_no_source_work(tmp_path, monkeypatch):
    calls = []
    stage = _stage(tmp_path, monkeypatch, calls)
    result = _run(stage, remaining=0)
    assert calls == []
    assert result["source_operations"] == 0
    assert result["budget_exhausted_before_refresh"] is True
    assert result["channels_attempted"] == ()
    assert len(result["channels_skipped"]) == 5



def test_partial_refresh_source_failure_is_not_terminal_source_exhaustion():
    from types import SimpleNamespace
    from printer_v1.discovery.eligible_token_supply import (
        _temporal_terminal_source_failure_facts,
    )

    ledger = SimpleNamespace(outcomes=[{
        "status": "REFRESH_COMPLETED",
        "channels_attempted": [
            composition.PUMP_FRESH_CHANNEL,
            composition.DEXSCREENER_FRESH_CHANNEL,
            composition.GECKOTERMINAL_NOMINATION_CHANNEL,
        ],
        "channels_unavailable": [composition.GECKOTERMINAL_NOMINATION_CHANNEL],
    }])
    failures, unavailable = _temporal_terminal_source_failure_facts(
        provider_failures=1,
        channels_unavailable=[composition.GECKOTERMINAL_NOMINATION_CHANNEL],
        acquisition_ledger=ledger,
        last_stop_reason="DISCOVERY_OPERATION_BUDGET_EXHAUSTED",
    )
    assert failures == 0
    assert unavailable == []


def test_all_fresh_refresh_sources_unavailable_remains_terminal_source_fact():
    from types import SimpleNamespace
    from printer_v1.discovery.eligible_token_supply import (
        _temporal_terminal_source_failure_facts,
    )

    all_fresh = [
        composition.PUMP_FRESH_CHANNEL,
        composition.DEXSCREENER_FRESH_CHANNEL,
        composition.GECKOTERMINAL_NOMINATION_CHANNEL,
    ]
    ledger = SimpleNamespace(outcomes=[{
        "status": "REFRESH_COMPLETED",
        "channels_attempted": all_fresh,
        "channels_unavailable": all_fresh,
    }])
    failures, unavailable = _temporal_terminal_source_failure_facts(
        provider_failures=3,
        channels_unavailable=all_fresh,
        acquisition_ledger=ledger,
        last_stop_reason="ALL_REACHABLE_CANDIDATES_EVALUATED",
    )
    assert failures == 3
    assert unavailable == sorted(all_fresh)



def test_delayed_refresh_stage_sequences_start_after_campaign_start(tmp_path, monkeypatch):
    seen = {"pump": [], "dex": [], "gt": [], "backup_base": [], "protocol": []}

    def fake_pump(*args, **kwargs):
        seen["pump"].append(kwargs["stage_sequence"])
        return {"status": "COMPLETE", "source_request_ids": [1], "verifications": []}

    def fake_dex(*args, **kwargs):
        seen["dex"].append(kwargs["stage_sequence"])
        return {
            "status": "empty", "source_requests": 1, "request_id": 2,
            "response_id": 3, "pool_observations": [],
        }

    def fake_gt(*args, **kwargs):
        seen["gt"].append(kwargs["stage_sequence"])
        return {"status": "COMPLETE", "failure_type": None, "source_requests": 1, "nominations": []}

    def fake_backup(*args, **kwargs):
        seen["backup_base"].append(kwargs["stage_sequence_base"])
        return {"source_requests": 0, "accounting_blocker": False}

    def fake_protocol(*args, **kwargs):
        seen["protocol"].append(kwargs["stage_sequence"])
        return {"source_requests": 0, "shared_source_failures": 0, "promoted_observation_eligible": []}

    monkeypatch.setattr(
        "printer_v1.discovery.direct_migration_discovery.run_direct_migration_discovery",
        fake_pump,
    )
    monkeypatch.setattr(
        "printer_v1.operator_cli.graduated_supply_front_door.run_fresh_profile_locator",
        fake_dex,
    )
    monkeypatch.setattr(composition, "run_geckoterminal_fresh_nomination", fake_gt)
    monkeypatch.setattr(composition, "run_bounded_unknown_liquidity_backup", fake_backup)
    monkeypatch.setattr(composition, "process_protocol_confirmation_queue", fake_protocol)

    stage = composition.build_pre_lifecycle_refresh_stage(
        db_path=tmp_path / "proof.sqlite3",
        request_key_prefix="proof",
        migration_transport=lambda _ctx: {},
        locator_transport=lambda _ctx: {},
    )
    for ordinal in (1, 2, 3):
        _run(stage, remaining=30, ordinal=ordinal)

    assert seen["pump"] == [2, 3, 4]
    assert seen["dex"] == [2, 3, 4]
    assert seen["gt"] == [2, 3, 4]
    assert seen["backup_base"] == [1, 2, 3]
    assert seen["protocol"] == [2, 3, 4]
