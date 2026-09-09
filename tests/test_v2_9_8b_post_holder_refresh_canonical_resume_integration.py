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

from printer_v1.db import apply_migrations
from printer_v1.discovery import eligible_token_supply as eligible_supply_module
from printer_v1.discovery.eligible_token_supply import (
    temporal_refresh_terminal_cause,
)
from printer_v1.discovery.permanent_discovery_availability import (
    FrozenEligibleReserve,
    StageBudget,
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
    LiveOperationalError,
    PILOT_INPUT_READINESS,
    _carry_post_holder_refresh_evidence,
    _persist_supply_exhaustion_certificate_at_terminal,
    _post_holder_resumed_supply_terminal_cause,
    _post_holder_supply_resume_coverage,
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


def test_post_holder_resumed_budget_exhaustion_preserves_shortage_classification(
    tmp_path,
) -> None:
    """A resumed supply's authoritative shortage must beat its raw stop code."""
    supply = GraduatedSupply(
        ready=False,
        terminal="BLOCKED_INSUFFICIENT_ELIGIBLE_GRADUATED_POOL",
        graduated_supply=(),
        graduation_proofs={},
        candidate_a=None,
        candidate_b=None,
        two_candidate_selection={},
        handoff_readiness={},
        discovery_report={},
        front_door_report={},
        diagnostics={
            "last_stop_reason": "DISCOVERY_OPERATION_BUDGET_EXHAUSTED",
            "shortage_classification": "BUDGET_EXHAUSTION",
            "exhaustion_certificate": {
                "certificate_id": "exh-post-holder-budget",
                "campaign_id": "campaign",
                "execution_id": "execution",
                "run_id": "run",
                "cycle_id": "cycle",
                "required_eligible_capacity": 2,
                "eligible_reserve_count": 0,
                "shortage_classification": "BUDGET_EXHAUSTION",
                "certificate_version": "V2_9_8B_LIQUIDITY_EVIDENCE_EXHAUSTION_V2",
                "created_at": "2026-09-08T17:56:45+00:00",
            },
        },
        holder_reserve_supply=(),
        holder_reserve_candidates={},
    )

    assert _post_holder_resumed_supply_terminal_cause(
        supply,
        fallback="INSUFFICIENT_ELIGIBLE_TWO_SLOT_POOL",
    ) == "BUDGET_EXHAUSTION"

    db = tmp_path / "post-holder-budget.sqlite3"
    apply_migrations(db)
    connection = sqlite3.connect(db)
    try:
        _persist_supply_exhaustion_certificate_at_terminal(connection, supply)
        connection.commit()
        row = connection.execute(
            "SELECT shortage_classification, certificate_json "
            "FROM printer_discovery_exhaustion_certificates "
            "WHERE certificate_id='exh-post-holder-budget'"
        ).fetchone()
        assert row is not None
        assert row[0] == "BUDGET_EXHAUSTION"
        assert json.loads(row[1]) == supply.diagnostics["exhaustion_certificate"]
    finally:
        connection.close()


def test_post_holder_resume_keeps_generic_pool_shortfall_without_shortage_classification() -> None:
    supply = GraduatedSupply(
        ready=False,
        terminal="BLOCKED_INSUFFICIENT_ELIGIBLE_GRADUATED_POOL",
        graduated_supply=(),
        graduation_proofs={},
        candidate_a=None,
        candidate_b=None,
        two_candidate_selection={},
        handoff_readiness={},
        discovery_report={},
        front_door_report={},
        diagnostics={},
        holder_reserve_supply=(),
        holder_reserve_candidates={},
    )

    assert _post_holder_resumed_supply_terminal_cause(
        supply,
        fallback="INSUFFICIENT_ELIGIBLE_TWO_SLOT_POOL",
    ) == "BLOCKED_INSUFFICIENT_ELIGIBLE_GRADUATED_POOL"


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



def test_supply_resume_coverage_excludes_holder_owned_stage_evidence() -> None:
    discovery = {
        "source_request_id": 11,
        "source_name": "dexscreener",
        "request_kind": "candidate_market_batch",
        "logical_stage_id": "campaign|run|cycle|MINT_MARKET_BATCH|1",
        "terminal_status": "COMPLETED",
        "transport_identity_count": 1,
        "normalized_member_count": 1,
        "transport_identity_keys": [
            [
                "MARKET_DISCOVERY",
                "dexscreener",
                "candidate_market_batch",
                "fixture",
                1,
                "MINT",
                "mint-a",
            ]
        ],
    }
    refresh = {
        "source_request_id": 12,
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
                "dexscreener_fresh_profiles",
                "fixture",
                1,
                "MINT",
                "mint-b",
            ]
        ],
    }
    holder = {
        "source_request_id": 13,
        "source_name": "goplus",
        "request_kind": "token_security",
        "logical_stage_id": "campaign|run|cycle|HOLDER_SAFETY|1",
        "terminal_status": "COMPLETED",
        "transport_identity_count": 1,
        "normalized_member_count": 1,
        "transport_identity_keys": [
            [
                "HOLDER_SAFETY",
                "goplus",
                "token_security",
                "fixture",
                1,
                "MINT",
                "mint-a",
            ]
        ],
    }

    coverage = _post_holder_supply_resume_coverage(
        {
            "campaign_source_request_coverage": [discovery],
            "final_refresh_source_request_coverage": [refresh],
            "holder_source_request_coverage": [holder],
        }
    )

    assert [entry["source_request_id"] for entry in coverage] == [11, 12]


def test_stage_budget_snapshot_round_trip_preserves_consumed_capacity() -> None:
    budget = StageBudget.permanent_discovery_default()
    budget.consume("intake", 2)
    budget.seal("intake")
    budget.consume("market_batching", 1)

    restored = StageBudget.from_snapshot(budget.snapshot())

    assert restored.snapshot() == budget.snapshot()
    assert restored.available("market_batching") == budget.available(
        "market_batching"
    )


def test_non_quantum_resume_rehydrates_inventory_before_campaign_start_acquisition(
    tmp_path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    db = tmp_path / "post-holder-resume.sqlite3"
    apply_migrations(db)

    class ReachedDurableInventory(RuntimeError):
        pass

    def forbidden(*_args, **_kwargs):
        raise AssertionError(
            "non-quantum cooperative resume must not re-enter campaign-start acquisition"
        )

    monkeypatch.setattr(
        eligible_supply_module,
        "run_direct_migration_discovery",
        forbidden,
    )
    monkeypatch.setattr(
        eligible_supply_module,
        "run_geckoterminal_fresh_nomination",
        forbidden,
    )

    from printer_v1.discovery import permanent_discovery_availability as permanent

    monkeypatch.setattr(
        permanent,
        "run_bounded_unknown_liquidity_backup",
        forbidden,
    )
    monkeypatch.setattr(
        permanent,
        "process_protocol_confirmation_queue",
        forbidden,
    )

    # Regression for the live Cycle-1 post-holder seam: the canonical
    # non-quantum resume must restore this campaign's durable fresh MOE before
    # traversing the existing graduated inventory.  This is zero-source reuse,
    # not a fresh discovery call.
    from printer_v1.discovery import later_cycle_fresh_inventory as fresh_inventory

    rehydration_calls: list[tuple[str, str]] = []
    original_loader = fresh_inventory.load_campaign_fresh_moe_candidates

    def tracked_loader(connection, *, campaign_id: str, at: str):
        rehydration_calls.append((campaign_id, at))
        return original_loader(connection, campaign_id=campaign_id, at=at)

    monkeypatch.setattr(
        fresh_inventory,
        "load_campaign_fresh_moe_candidates",
        tracked_loader,
    )

    def reached_inventory(_connection):
        raise ReachedDurableInventory("durable inventory reached")

    monkeypatch.setattr(
        eligible_supply_module,
        "export_graduated_candidates",
        reached_inventory,
    )

    prior_budget = StageBudget.permanent_discovery_default()
    prior_budget.consume("intake", 2)
    prior_budget.seal("intake")
    prior_budget.consume("market_batching", 1)
    resumed_budget = StageBudget.from_snapshot(prior_budget.snapshot())

    with pytest.raises(ReachedDurableInventory, match="durable inventory reached"):
        eligible_supply_module.run_persistent_eligible_token_supply(
            db,
            cycle_seed="post-holder-existing-inventory",
            migration_transport=lambda _context: {},
            now="2026-09-06T15:45:12+00:00",
            permanent_availability=True,
            cooperative_resume=True,
            cooperative_stage_budget=resumed_budget,
            prior_source_operations_used=3,
            run_geckoterminal_nomination=True,
            campaign_id="campaign",
            execution_id="execution",
            run_id="run",
            cycle_id="cycle",
            discovery_request_key_prefix="resume-root",
            front_door_request_key_prefix="resume-root",
        )

    assert rehydration_calls == [
        ("campaign", "2026-09-06T15:45:12+00:00")
    ]


def test_cycle1_terminal_owner_persists_exact_certificate_once_and_conflicts_fail(
    tmp_path,
) -> None:
    db = tmp_path / "cycle1-terminal-certificate.sqlite3"
    apply_migrations(db)
    certificate = {
        "certificate_id": "exh-execution",
        "campaign_id": "campaign",
        "execution_id": "execution",
        "run_id": "run",
        "cycle_id": "cycle",
        "required_eligible_capacity": 4,
        "eligible_reserve_count": 1,
        "shortage_classification": "TRUE_MARKET_SUPPLY_SHORTAGE",
        "certificate_version": "V2_9_8B_LIQUIDITY_EVIDENCE_EXHAUSTION_V2",
        "created_at": "2026-09-06T17:57:26+00:00",
    }
    supply = GraduatedSupply(
        ready=False,
        terminal="BLOCKED_INSUFFICIENT_ELIGIBLE_GRADUATED_POOL",
        graduated_supply=(),
        graduation_proofs={},
        candidate_a=None,
        candidate_b=None,
        two_candidate_selection={},
        handoff_readiness={},
        discovery_report={},
        front_door_report={},
        diagnostics={"exhaustion_certificate": certificate},
        holder_reserve_supply=(),
        holder_reserve_candidates={},
    )

    connection = sqlite3.connect(db)
    try:
        first = _persist_supply_exhaustion_certificate_at_terminal(
            connection,
            supply,
        )
        connection.commit()
        assert dict(first or {}) == certificate
        assert connection.execute(
            "SELECT COUNT(*) FROM printer_discovery_exhaustion_certificates "
            "WHERE certificate_id='exh-execution'"
        ).fetchone()[0] == 1

        second = _persist_supply_exhaustion_certificate_at_terminal(
            connection,
            supply,
        )
        assert dict(second or {}) == certificate
        assert connection.execute(
            "SELECT COUNT(*) FROM printer_discovery_exhaustion_certificates "
            "WHERE certificate_id='exh-execution'"
        ).fetchone()[0] == 1

        conflicting = replace(
            supply,
            diagnostics={
                "exhaustion_certificate": {
                    **certificate,
                    "eligible_reserve_count": 2,
                }
            },
        )
        with pytest.raises(
            LiveOperationalError,
            match="CYCLE1_EXHAUSTION_CERTIFICATE_PAYLOAD_CONFLICT",
        ):
            _persist_supply_exhaustion_certificate_at_terminal(
                connection,
                conflicting,
            )
    finally:
        connection.close()


def test_live_permanent_supply_defers_terminal_certificate_persistence(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    base = _CampaignBase()
    base.setUp()
    try:
        class CapturedDeferredPersistence(RuntimeError):
            pass

        def capture_builder(_db_path, **kwargs):
            assert kwargs["permanent_availability"] is True
            assert kwargs["persist_terminal_certificate"] is False
            raise CapturedDeferredPersistence("captured")

        owner = AuthoritativeLiveOperationalCampaignOwner()
        with patch(
            "printer_v1.operator_cli.graduated_supply_front_door."
            "build_graduated_supply",
            side_effect=capture_builder,
        ):
            with pytest.raises(CapturedDeferredPersistence, match="captured"):
                owner.run(
                    mode=PILOT_INPUT_READINESS,
                    command=base.command,
                    pump_transport=_FakePumpTransport([], {}),
                    secondary_transport=None,
                    source_governor=GOV,
                    central_scheduler=SCH,
                    selection_seed="cycle1-deferred-certificate",
                    cycle_id="cyc",
                    cycle_cutoff=e8.CUTOFF,
                    evaluated_at=e8.NOW,
                    backup_path=base.backup,
                    lifecycle_kwargs={},
                    graduated_supply=None,
                    graduated_supply_kwargs={"permanent_availability": True},
                    migration_transport=object(),
                )
    finally:
        base.tearDown()


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


def test_post_holder_resumed_budget_exhaustion_preserves_terminal_and_certificate() -> None:
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
        initial_stage_budget = StageBudget.permanent_discovery_default()
        initial_stage_budget.consume("intake", 2)
        initial_stage_budget.seal("intake")
        initial_stage_budget.consume("market_batching", 1)
        diagnostics["stage_capacity"] = initial_stage_budget.snapshot()
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

        freeze_calls = {"count": 0}

        def freeze_spy(connection, candidates, **kwargs):
            freeze_calls["count"] += 1
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
            return FrozenEligibleReserve(
                selected=(),
                alternates=(),
                rejected_stale=(),
                frozen_at=str(kwargs["at"]),
                selection_authority={
                    "coverage_blocker": True,
                    "valid_fresh_unique_observation_depth": 0,
                    "observation_eligible_count": 0,
                },
            )

        resume_calls = {"count": 0}

        def resume_builder(_db_path, **kwargs):
            resume_calls["count"] += 1
            assert resume_calls["count"] == 1
            assert kwargs["cooperative_resume"] is True
            assert isinstance(kwargs["cooperative_stage_budget"], StageBudget)
            assert kwargs["cooperative_stage_budget"].snapshot() == (
                initial_stage_budget.snapshot()
            )
            assert kwargs["persist_terminal_certificate"] is False
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
            refresh_only = [
                entry
                for entry in prior_coverage
                if int(entry["source_request_id"]) == refresh_owner.request_id
            ]
            assert len(refresh_only) == 1
            # Reproduce the live defect: canonical resumed diagnostics describe
            # only the resumed/refresh round. The campaign owner, not this
            # builder, must restore the earlier cumulative request provenance.
            updated["source_request_coverage"] = refresh_only
            updated["campaign_source_request_coverage"] = refresh_only
            updated["source_request_ids"] = [refresh_owner.request_id]
            updated["stage_reported_request_ids"] = [refresh_owner.request_id]
            updated["discovery_operations_used"] = 1
            updated["discovery_operations_remaining"] = 9
            updated["last_stop_reason"] = "DISCOVERY_OPERATION_BUDGET_EXHAUSTED"
            updated["shortage_classification"] = "BUDGET_EXHAUSTION"
            updated["exhaustion_certificate"] = {
                "certificate_id": "exh-post-holder-campaign-budget",
                "campaign_id": base.command.campaign_id,
                "execution_id": selection_seed,
                "run_id": base.command.run_id,
                "cycle_id": cycle_id,
                "required_eligible_capacity": 2,
                "eligible_reserve_count": 0,
                "shortage_classification": "BUDGET_EXHAUSTION",
                "certificate_version": "V2_9_8B_LIQUIDITY_EVIDENCE_EXHAUSTION_V2",
                "created_at": e8.NOW,
            }
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
        assert result.lifecycle["stop_reason"] == "BUDGET_EXHAUSTION"
        final_diagnostics = _campaign_supply_diagnostics(result.lifecycle)
        assert (
            final_diagnostics["post_holder_refresh_resume"]["status"]
            == "CANONICAL_SUPPLY_RESUMED"
        )
        post_holder_recon = final_diagnostics[
            "post_holder_source_request_reconciliation"
        ]
        assert post_holder_recon["status"] == "OK"
        expected_request_ids = sorted(
            {
                *[
                    int(entry["source_request_id"])
                    for entry in initial_manifest
                ],
                int(refresh_owner.request_id),
            }
        )
        assert post_holder_recon["durable_campaign_request_ids"] == (
            expected_request_ids
        )
        assert post_holder_recon["stage_reported_request_ids"] == (
            expected_request_ids
        )
        assert post_holder_recon["durable_not_stage_reported"] == []
        assert [
            int(entry["source_request_id"])
            for entry in post_holder_recon["campaign_source_request_manifest"]
        ] == expected_request_ids
        assert (
            final_diagnostics["campaign_source_request_reconciliation"]["status"]
            == "OK"
        )
        assert final_diagnostics["freeze_depth_enforcement"]["selected_count"] == 0
        assert refresh_owner.request_id in final_diagnostics[
            "durable_campaign_request_ids"
        ]
        connection = sqlite3.connect(base.db)
        try:
            row = connection.execute(
                "SELECT shortage_classification, certificate_json "
                "FROM printer_discovery_exhaustion_certificates "
                "WHERE certificate_id='exh-post-holder-campaign-budget'"
            ).fetchone()
            assert row is not None
            assert row[0] == "BUDGET_EXHAUSTION"
            assert json.loads(row[1]) == final_diagnostics["exhaustion_certificate"]
        finally:
            connection.close()
    finally:
        base.tearDown()
