"""Full disposable seam for post-holder refresh -> canonical resume -> re-freeze.

No provider, operational Printer, authorization, or live Scheduler runtime is used.
The real permanent-mode campaign owner, reconciliation, provenance and freeze
boundaries are exercised against disposable SQLite state.
"""
from __future__ import annotations

import hashlib
import json
import sqlite3
from dataclasses import replace
from unittest.mock import patch

import pytest

from printer_v1.discovery.eligible_token_supply import (
    temporal_refresh_terminal_cause,
)
from printer_v1.discovery.permanent_discovery_availability import (
    FrozenEligibleReserve,
    freeze_eligible_reserve_for_campaign,
)
from printer_v1.discovery.pre_lifecycle_temporal_acquisition import (
    ACQUISITION_DEADLINE_EXHAUSTED,
    INTERNAL_INVARIANT,
    REFRESH_COMPLETED,
    SOURCE_BUDGET_EXHAUSTED,
    UNSAFE_SCHEDULER_STATE,
    WAITING_FOR_ELIGIBLE_SUPPLY,
    TemporalRefreshOutcome,
)
from printer_v1.operator_cli import operational_memory_factory_command as command
from printer_v1.operator_cli.authoritative_live_operational_campaign import (
    AuthoritativeLiveOperationalCampaignOwner,
    PILOT_INPUT_READINESS,
    _carry_post_holder_refresh_evidence,
)
from printer_v1.operator_cli.graduated_supply_front_door import GraduatedSupply

import test_v2_9_7e_8_origin_to_lifecycle_integration as e8
from test_v2_9_7e_11_authoritative_live_operational_campaign import (
    _FakePumpTransport,
)
from test_v2_9_8b_remaining_runtime_blocker_repair import (
    GOV,
    SCH,
    _CampaignBase,
    _campaign_supply_diagnostics,
    _force_holder_extreme_ineligible,
    _permanent_supply,
    _seed_exact_markets_for_campaign,
)


def test_temporal_refresh_terminal_mapping_is_shared_and_categorical() -> None:
    assert temporal_refresh_terminal_cause(WAITING_FOR_ELIGIBLE_SUPPLY) == (
        WAITING_FOR_ELIGIBLE_SUPPLY
    )
    assert temporal_refresh_terminal_cause(SOURCE_BUDGET_EXHAUSTED) == (
        "DISCOVERY_OPERATION_BUDGET_EXHAUSTED"
    )
    assert temporal_refresh_terminal_cause(ACQUISITION_DEADLINE_EXHAUSTED) == (
        "PRE_LIFECYCLE_ACQUISITION_DURATION_EXHAUSTED"
    )
    assert temporal_refresh_terminal_cause(UNSAFE_SCHEDULER_STATE) == (
        "UNSAFE_SCHEDULER_OWNERSHIP_STATE"
    )
    assert temporal_refresh_terminal_cause(INTERNAL_INVARIANT) == (
        "DISCOVERY_ARCHITECTURE_FALSE_SHORTAGE"
    )


def test_refresh_evidence_carry_is_idempotent() -> None:
    entry = {
        "source_request_id": 77,
        "source_name": "dexscreener",
        "request_kind": "dexscreener_fresh_profiles",
        "logical_stage_id": "campaign|run|cycle|POST_HOLDER_REFRESH|1",
        "terminal_status": "COMPLETED",
        "transport_identity_count": 1,
        "normalized_member_count": 1,
        "transport_identity_keys": [
            [
                "POST_HOLDER_REFRESH",
                "dexscreener",
                "dexscreener",
                "dexscreener_fresh_profiles",
                "fixture",
                1,
                "MINT",
                "mint",
                32,
                1,
                "COMPLETE",
                None,
            ]
        ],
    }
    outcome = TemporalRefreshOutcome(
        status=REFRESH_COMPLETED,
        source_request_ids=(77,),
        source_request_coverage=(entry,),
    )
    once = _carry_post_holder_refresh_evidence({}, outcome)
    twice = _carry_post_holder_refresh_evidence(once, outcome)
    assert twice["final_refresh_source_request_ids"] == [77]
    assert len(twice["final_refresh_source_request_coverage"]) == 1


def test_four_token_standard4h_disposable_rehearsal_uses_proof_preflight(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class ReachedDisposablePreflight(RuntimeError):
        pass

    def disposable_preflight(_proof):
        raise ReachedDisposablePreflight("reached")

    def production_preflight(**_kwargs):
        raise AssertionError("production authorization preflight must not run")

    monkeypatch.setattr(
        command,
        "build_disposable_public_composition_preflight",
        disposable_preflight,
    )
    monkeypatch.setattr(
        command,
        "build_standard_four_hour_preflight",
        production_preflight,
    )

    with pytest.raises(ReachedDisposablePreflight, match="reached"):
        command.run_four_token_standard_four_hour_campaign(
            operator_approved=True,
            git_provenance_authorization=None,
            disposable_proof=object(),
        )


def test_post_holder_completed_refresh_resumes_canonical_supply_and_refreezes() -> None:
    base = _CampaignBase()
    base.setUp()
    try:
        selection_seed = "post-holder-canonical-resume"
        cycle_id = "cyc"
        supply = _permanent_supply(4)
        _seed_exact_markets_for_campaign(
            base.db,
            supply,
            command=base.command,
            selection_seed=selection_seed,
            cycle_id=cycle_id,
        )
        diagnostics = dict(supply.diagnostics)
        diagnostics["discovery_operations_used"] = 0
        diagnostics["discovery_operations_remaining"] = 10
        supply = replace(supply, diagnostics=diagnostics)

        initial_manifest = list(
            diagnostics["pre_holder_source_request_reconciliation"][
                "campaign_source_request_manifest"
            ]
        )
        projection_keys = [
            list(key)
            for entry in initial_manifest
            for key in entry.get("transport_identity_keys") or ()
        ]

        def accounting_projection():
            return {
                "campaign_transport_identities": list(projection_keys),
                "action_local_transport_identities": list(projection_keys),
            }

        class RefreshOwner:
            acquisition_deadline_at = "2099-01-01T00:00:00+00:00"
            refresh_interval_seconds = 1

            def __init__(self) -> None:
                self.calls = 0
                self.request_id = None

            def request_temporal_refresh(self, **_kwargs):
                self.calls += 1
                assert self.calls == 1
                root = str(supply.diagnostics["request_key_root"])
                campaign_id = str(base.command.campaign_id)
                run_id = str(base.command.run_id)
                mint = next(iter(supply.holder_reserve_candidates.values()))["mint"]
                key = [
                    "POST_HOLDER_REFRESH",
                    "dexscreener",
                    "dexscreener",
                    "dexscreener_fresh_profiles",
                    "fixture",
                    1,
                    "MINT",
                    mint,
                    32,
                    1,
                    "COMPLETE",
                    None,
                ]
                conn = sqlite3.connect(base.db)
                try:
                    request = conn.execute(
                        """INSERT INTO printer_source_requests(
                               source_name,request_kind,requested_at,request_key,
                               source_status,data_quality_label
                           ) VALUES (?,?,?,?,'COMPLETE','CLEAN_DATA')""",
                        (
                            "dexscreener",
                            "dexscreener_fresh_profiles",
                            e8.NOW,
                            f"{root}-post-holder-refresh-1",
                        ),
                    )
                    request_id = int(request.lastrowid)
                    payload = json.dumps(
                        {"chain": "solana", "mint": mint, "observed_at": e8.NOW},
                        sort_keys=True,
                    )
                    digest = hashlib.sha256(payload.encode()).hexdigest()
                    conn.execute(
                        """INSERT INTO printer_source_responses(
                               source_request_id,source_name,received_at,status_code,
                               source_status,data_quality_label,response_hash,
                               normalized_payload_json
                           ) VALUES (?,?,?,200,'COMPLETE','CLEAN_DATA',?,?)""",
                        (
                            request_id,
                            "dexscreener",
                            e8.NOW,
                            digest,
                            payload,
                        ),
                    )
                    conn.commit()
                finally:
                    conn.close()
                self.request_id = request_id
                projection_keys.append(key)
                coverage = {
                    "source_request_id": request_id,
                    "source_name": "dexscreener",
                    "request_kind": "dexscreener_fresh_profiles",
                    "logical_stage_id": (
                        f"{campaign_id}|{run_id}|{cycle_id}|POST_HOLDER_REFRESH|1"
                    ),
                    "terminal_status": "COMPLETED",
                    "transport_identity_count": 1,
                    "normalized_member_count": 1,
                    "transport_identity_keys": [key],
                }
                return TemporalRefreshOutcome(
                    status=REFRESH_COMPLETED,
                    claimed=True,
                    source_operations=1,
                    source_request_ids=(request_id,),
                    source_request_coverage=(coverage,),
                    reserve_depth_before=2,
                    reserve_depth_after=2,
                )

        refresh_owner = RefreshOwner()
        owner = AuthoritativeLiveOperationalCampaignOwner()
        _force_holder_extreme_ineligible(owner, supply.holder_reserve_supply)

        real_freeze = freeze_eligible_reserve_for_campaign
        freeze_calls = {"count": 0}

        def freeze_spy(connection, candidates, **kwargs):
            freeze_calls["count"] += 1
            materialized = list(candidates)
            if freeze_calls["count"] == 1:
                return FrozenEligibleReserve(
                    selected=(),
                    alternates=(),
                    rejected_stale=(),
                    frozen_at=str(kwargs["at"]),
                    selection_authority={
                        "coverage_blocker": True,
                        "valid_fresh_unique_observation_depth": 2,
                        "observation_eligible_count": 2,
                    },
                )
            assert len(materialized) >= 4
            return real_freeze(connection, materialized, **kwargs)

        resume_calls = {"count": 0}

        def resume_builder(_db_path, **kwargs):
            resume_calls["count"] += 1
            assert resume_calls["count"] == 1
            assert kwargs["cooperative_resume"] is True
            assert kwargs["prior_source_operations_used"] == 1
            assert kwargs["permanent_availability"] is True
            assert kwargs["tracking_precheck"] is True
            assert kwargs["campaign_source_request_scope"] is not None
            prior_coverage = [
                dict(entry) for entry in kwargs["prior_source_request_coverage"]
            ]
            assert refresh_owner.request_id in {
                int(entry["source_request_id"]) for entry in prior_coverage
            }
            updated = dict(supply.diagnostics)
            updated["source_request_coverage"] = prior_coverage
            updated["campaign_source_request_coverage"] = prior_coverage
            ids = sorted(
                {
                    int(entry["source_request_id"])
                    for entry in prior_coverage
                }
            )
            updated["source_request_ids"] = ids
            updated["stage_reported_request_ids"] = ids
            updated["discovery_operations_used"] = 1
            updated["discovery_operations_remaining"] = 9
            updated["last_stop_reason"] = "ELIGIBLE_CAPACITY_MET"
            updated["shortage_classification"] = None
            return replace(supply, diagnostics=updated)

        with patch(
            "printer_v1.discovery.permanent_discovery_availability."
            "freeze_eligible_reserve_for_campaign",
            side_effect=freeze_spy,
        ), patch(
            "printer_v1.operator_cli.graduated_supply_front_door."
            "build_graduated_supply",
            side_effect=resume_builder,
        ):
            result = owner.run(
                mode=PILOT_INPUT_READINESS,
                command=base.command,
                pump_transport=_FakePumpTransport([], {}),
                secondary_transport=None,
                source_governor=GOV,
                central_scheduler=SCH,
                selection_seed=selection_seed,
                cycle_id=cycle_id,
                cycle_cutoff=e8.CUTOFF,
                evaluated_at=e8.NOW,
                backup_path=base.backup,
                lifecycle_kwargs={},
                graduated_supply=supply,
                migration_transport=object(),
                pre_holder_accounting_projection=accounting_projection,
                pre_lifecycle_temporal_refresh_owner=refresh_owner,
            )

        assert refresh_owner.calls == 1
        assert resume_calls["count"] == 1
        assert freeze_calls["count"] == 2
        assert result.lifecycle_started is False
        assert result.lifecycle["stop_reason"] == "PILOT_INPUT_READY"
        final_diagnostics = _campaign_supply_diagnostics(result.lifecycle)
        assert (
            final_diagnostics["post_holder_refresh_resume"]["status"]
            == "CANONICAL_SUPPLY_RESUMED"
        )
        assert (
            final_diagnostics["post_holder_source_request_reconciliation"]["status"]
            == "OK"
        )
        assert (
            final_diagnostics["campaign_source_request_reconciliation"]["status"]
            == "OK"
        )
        assert final_diagnostics["freeze_depth_enforcement"]["selected_count"] == 2
        assert refresh_owner.request_id in final_diagnostics[
            "durable_campaign_request_ids"
        ]
    finally:
        base.tearDown()
