from __future__ import annotations

from types import SimpleNamespace


def _coverage(request_id: int, suffix: str = "a") -> dict[str, object]:
    return {
        "source_request_id": request_id,
        "source_name": "dexscreener",
        "request_kind": "fresh_profiles",
        "logical_stage_id": f"campaign|run|cycle|REFRESH|{request_id}",
        "terminal_status": "COMPLETED",
        "transport_identity_count": 1,
        "normalized_member_count": 1,
        "transport_identity_keys": [["transport", request_id, suffix]],
    }


def test_completed_refresh_carries_stage_coverage_out_of_existing_owner(tmp_path):
    """Behavioral RED: a real completed refresh must carry its exact coverage."""
    from printer_v1.db import apply_migrations
    from printer_v1.discovery.pre_lifecycle_temporal_acquisition import REFRESH_COMPLETED
    from printer_v1.operator_cli.pre_lifecycle_persistent_refresh_owner import (
        PreLifecycleTemporalRefreshOwner,
    )

    db_path = tmp_path / "refresh-coverage.sqlite3"
    apply_migrations(db_path)
    entry = _coverage(42)

    def refresh_stage(
        connection,
        *,
        campaign_id,
        run_id,
        cycle_id,
        **kwargs,
    ):
        return {
            "campaign_id": campaign_id,
            "run_id": run_id,
            "cycle_id": cycle_id,
            "source_operations": 1,
            "provider_failures": 0,
            "channels_unavailable": (),
            "channels_attempted": ("dexscreener",),
            "channels_skipped": (),
            "stage_reports": {
                "dex": {
                    "source_request_ids": [42],
                    "source_request_coverage": [entry],
                },
            },
        }

    owner = PreLifecycleTemporalRefreshOwner(
        db_path,
        campaign_id="campaign",
        run_id="run",
        cycle_id="cycle",
        supervision_id="supervision",
        source_governor=SimpleNamespace(available=True),
        central_scheduler=SimpleNamespace(available=True),
        acquisition_started_at="2026-08-31T23:59:59+00:00",
        acquisition_deadline_at="2026-09-01T00:10:00+00:00",
        work_deadline_at="2026-09-01T00:20:00+00:00",
        refresh_stage=refresh_stage,
        waiter=lambda _seconds: False,
        refresh_interval_seconds=1,
    )
    outcome = owner.request_temporal_refresh(
        reserve_depth=0,
        required_capacity=4,
        universe_state="ALL_REACHABLE_CANDIDATES_EVALUATED",
        source_operations_remaining=4,
        now="2026-09-01T00:00:00+00:00",
    )

    assert outcome.status == REFRESH_COMPLETED
    payload = outcome.to_dict()
    assert payload["source_request_ids"] == [42]
    assert [
        int(row["source_request_id"])
        for row in payload["source_request_coverage"]
    ] == [42]



def test_completed_refresh_progress_merges_prior_and_current_coverage():
    from printer_v1.operator_cli.authoritative_live_operational_campaign import (
        _persist_completed_later_cycle_refresh_progress,
    )

    prior = _coverage(51)
    completed = _coverage(52)
    progress = {
        "source_operations_used": 3,
        "reserve_depth": 1,
        "source_request_coverage": [prior],
    }
    progress_by_cycle: dict[str, dict[str, object]] = {}
    updated = _persist_completed_later_cycle_refresh_progress(
        progress_by_cycle,
        progress_key="cycle-2",
        progress=progress,
        refresh_owner=object(),
        completed_source_operations=2,
        completed_source_request_coverage=(completed,),
    )
    assert updated["source_operations_used"] == 5
    assert [
        int(row["source_request_id"])
        for row in updated["source_request_coverage"]
    ] == [51, 52]
    assert progress_by_cycle["cycle-2"] is updated


def test_acquisition_ledger_preserves_refresh_ids_and_manifest_independently():
    from printer_v1.discovery.eligible_token_supply import (
        temporal_refresh_source_request_evidence,
    )
    from printer_v1.discovery.pre_lifecycle_temporal_acquisition import (
        AcquisitionLedger,
        REFRESH_COMPLETED,
        TemporalRefreshOutcome,
    )

    entry = _coverage(61)
    ledger = AcquisitionLedger(
        started_at="2026-09-01T00:00:00+00:00",
        acquisition_deadline_at="2026-09-01T00:10:00+00:00",
        acquisition_duration_seconds=600,
        refresh_interval_seconds=60,
    )
    ledger.record(
        TemporalRefreshOutcome(
            status=REFRESH_COMPLETED,
            source_request_ids=(61,),
            source_request_coverage=(entry,),
        )
    )

    request_ids, coverage = temporal_refresh_source_request_evidence(ledger)
    assert request_ids == [61]
    assert coverage == [entry]


def test_cooperative_waiting_branch_carries_partial_refresh_coverage_before_yield():
    import inspect
    from printer_v1.operator_cli import authoritative_live_operational_campaign as campaign

    source = inspect.getsource(campaign)
    waiting = source.index("if outcome.status == WAITING_FOR_ELIGIBLE_SUPPLY:")
    returned = source.index("return LaterCycleCandidateSupply(", waiting)
    merge = source.index('progress["source_request_coverage"] = (', waiting)
    assert waiting < merge < returned
    assert "outcome.source_request_coverage" in source[merge:returned]
