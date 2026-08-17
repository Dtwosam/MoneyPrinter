from __future__ import annotations

from datetime import datetime, timezone
import sqlite3

import pytest

from printer_v1.db import apply_migrations
from printer_v1.operator_cli.abstract_campaign_command import (
    CENTRAL_SCHEDULER_OWNER,
    SOURCE_GOVERNOR_OWNER,
    OwnerPort,
)
from printer_v1.operator_cli.authoritative_live_operational_campaign import (
    AuthoritativeLiveOperationalCampaignOwner,
    LiveOperationalError,
)
from printer_v1.operator_cli.four_token_proof_integration import (
    LaterCycleCandidateSupply,
    LaterCycleDiscoveryCandidate,
    LaterCycleSourceEvidence,
)
from printer_v1.operator_cli.graduated_supply_front_door import GraduatedSupply
from printer_v1.operator_cli.later_cycle_graduated_supply import (
    FAILURE_DOMAIN_INTERNAL,
    build_later_cycle_graduated_supply,
)
from printer_v1.operator_cli.multi_cycle_campaign_coordinator import (
    MultiCycleAdmissionHealth,
)


NOW = datetime(2026, 8, 13, 12, 0, tzinfo=timezone.utc)
GOVERNOR = OwnerPort(SOURCE_GOVERNOR_OWNER, True)
SCHEDULER = OwnerPort(CENTRAL_SCHEDULER_OWNER, True)
HEALTH = MultiCycleAdmissionHealth(
    source_budget_available=True,
    provider_budgets_available=True,
    scheduler_budget_available=True,
    scheduler_due_work_healthy=True,
    close_reserve_available=True,
    campaign_supervision_healthy=True,
    lease_healthy=True,
    db_healthy=True,
    shared_terminal_condition=False,
    cancellation_requested=False,
    discovery_capacity_available=True,
    protected_work_capacity_available=True,
)


@pytest.fixture()
def database(tmp_path):
    path = tmp_path / "later-cycle-callback.sqlite3"
    apply_migrations(path)
    connection = sqlite3.connect(path)
    connection.execute("PRAGMA foreign_keys=ON")
    connection.execute(
        "INSERT INTO printer_memory_factory_campaigns("
        "campaign_id,campaign_state,db_mode,db_target_identity,policy_version) "
        "VALUES ('campaign-1','RUNNING','OPERATIONAL_PERSISTENT','db-1','policy-1')"
    )
    connection.execute(
        "INSERT INTO printer_memory_factory_campaign_configurations("
        "configuration_id,campaign_id,configuration_hash,configuration_json,"
        "launch_provenance_json) VALUES (?,?,?,?,?)",
        ("configuration-1", "campaign-1", "a" * 64, "{}", "{}"),
    )
    connection.execute(
        "INSERT INTO printer_memory_factory_runs("
        "run_id,run_status,window_kind,db_mode,config_hash,config_json,started_at) "
        "VALUES (?,?,?,?,?,?,?)",
        ("factory-1", "RUNNING", "WINDOW_15M", "OPERATIONAL_PERSISTENT", "a" * 64, "{}", NOW.isoformat()),
    )
    connection.execute(
        "INSERT INTO printer_memory_factory_campaign_runs("
        "run_id,campaign_id,run_ordinal,run_state,authoritative_run_id,created_at,updated_at) "
        "VALUES (?,?,?,?,?,?,?)",
        ("campaign-run-1", "campaign-1", 1, "RUNNING", "factory-1", NOW.isoformat(), NOW.isoformat()),
    )
    for slot in (1, 2):
        connection.execute(
            "INSERT INTO printer_tokens(id,token_mint,chain) VALUES (?,?, 'solana')",
            (slot, f"mint-{slot}"),
        )
        connection.execute(
            "INSERT INTO printer_pairs(id,token_id,pair_address) VALUES (?,?,?)",
            (slot, slot, f"pool-{slot}"),
        )
    request_id = connection.execute(
        "INSERT INTO printer_source_requests("
        "source_name,request_kind,requested_at,source_status,data_quality_label) "
        "VALUES ('dexscreener','fresh_profiles',?,'COMPLETE','CLEAN_DATA')",
        (NOW.isoformat(),),
    ).lastrowid
    response_id = connection.execute(
        "INSERT INTO printer_source_responses("
        "source_request_id,source_name,received_at,source_status,data_quality_label) "
        "VALUES (?,'dexscreener',?,'COMPLETE','CLEAN_DATA')",
        (request_id, NOW.isoformat()),
    ).lastrowid
    connection.commit()
    connection.close()
    return path, int(request_id), int(response_id)


def _candidate(slot: int) -> LaterCycleDiscoveryCandidate:
    return LaterCycleDiscoveryCandidate(
        token_identity=f"solana-mainnet:mint-{slot}",
        token_row_id=slot,
        mint_identity=f"mint-{slot}",
        pair_identity=f"pool-{slot}",
        pair_row_id=slot,
        lifecycle_identity="PUMPSWAP_GRADUATED_CONFIRMED",
        canonical_market_identity=f"solana-mainnet:pumpswap:pool-{slot}",
        canonical_pool_identity=f"pool-{slot}",
        channels=frozenset({"LATEST_PUMPFUN" if slot == 1 else "TOP_PUMPFUN"}),
        holder_evidence_eligible=True,
        canonical_evidence_json='{"quality":"exact"}',
        canonical_evidence_hash=str(slot) * 64,
        evidence_version="v1",
        observed_at=NOW,
    )


def _invoke(callback):
    return callback(
        campaign_id="campaign-1",
        campaign_run_id="campaign-run-1",
        authoritative_factory_run_id="factory-1",
        cycle_id="cycle-2",
        cycle_ordinal=2,
        cycle_cutoff=NOW.isoformat(),
        evaluated_at=NOW.isoformat(),
        selection_seed="seed-2",
        source_governor=GOVERNOR,
        central_scheduler=SCHEDULER,
        admission_health=HEALTH,
    )


def test_callback_executes_one_durable_zero_or_two_attempt(database) -> None:
    path, request_id, response_id = database
    calls = []

    def supply(**context):
        calls.append(context)
        return LaterCycleCandidateSupply(
            candidates=(_candidate(1), _candidate(2)),
            source_evidence=(
                LaterCycleSourceEvidence(
                    logical_stage="ELIGIBLE_SUPPLY",
                    source_request_id=request_id,
                    source_response_id=response_id,
                ),
            ),
            terminal_cause=None,
        )

    owner = AuthoritativeLiveOperationalCampaignOwner(
        later_cycle_candidate_supply=supply
    )
    callback = owner._build_later_cycle_discovery_callback(
        db_path=path, configuration_id="configuration-1"
    )
    first = _invoke(callback)
    second = _invoke(callback)

    assert first.attempt_id == second.attempt_id
    assert first.state == "PAIR_READY"
    assert first.selected_count == 2
    assert len(calls) == 1
    assert calls[0]["source_governor"] is GOVERNOR
    assert calls[0]["central_scheduler"] is SCHEDULER
    connection = sqlite3.connect(path)
    try:
        assert connection.execute(
            "SELECT COUNT(*) FROM printer_pre_admission_discovery_attempts"
        ).fetchone()[0] == 1
        assert connection.execute(
            "SELECT COUNT(*) FROM printer_pre_admission_discovery_attempt_items"
        ).fetchone()[0] == 2
        assert connection.execute(
            "SELECT COUNT(*) FROM printer_memory_factory_campaign_cycles "
            "WHERE cycle_ordinal=2"
        ).fetchone()[0] == 0
        assert connection.execute(
            "SELECT status FROM printer_scheduler_jobs"
        ).fetchone()[0] == "SUCCEEDED"
    finally:
        connection.close()


def test_callback_fails_before_attempt_without_exact_authority(database) -> None:
    path, _, _ = database
    owner = AuthoritativeLiveOperationalCampaignOwner(
        later_cycle_candidate_supply=lambda **_: LaterCycleCandidateSupply((), (), "NO_PAIR")
    )
    callback = owner._build_later_cycle_discovery_callback(
        db_path=path, configuration_id="configuration-1"
    )
    with pytest.raises(LiveOperationalError, match="LATER_CYCLE_CONTEXT_INVALID"):
        callback(
            campaign_id="campaign-1",
            campaign_run_id="campaign-run-1",
            authoritative_factory_run_id="wrong-factory",
            cycle_id="cycle-2",
            cycle_ordinal=2,
            cycle_cutoff=NOW.isoformat(),
            evaluated_at=NOW.isoformat(),
            selection_seed="seed-2",
            source_governor=GOVERNOR,
            central_scheduler=SCHEDULER,
            admission_health=HEALTH,
        )
    connection = sqlite3.connect(path)
    try:
        assert connection.execute(
            "SELECT COUNT(*) FROM printer_pre_admission_discovery_attempts"
        ).fetchone()[0] == 0
        assert connection.execute("SELECT COUNT(*) FROM printer_scheduler_jobs").fetchone()[0] == 0
    finally:
        connection.close()


def test_supply_failure_terminalizes_once_without_retry_or_successor(database) -> None:
    path, _, _ = database
    calls = 0

    def failed_supply(**_):
        nonlocal calls
        calls += 1
        raise RuntimeError("injected provider failure")

    callback = AuthoritativeLiveOperationalCampaignOwner(
        later_cycle_candidate_supply=failed_supply
    )._build_later_cycle_discovery_callback(
        db_path=path, configuration_id="configuration-1"
    )
    first = _invoke(callback)
    second = _invoke(callback)

    assert first == second
    assert first.state == "FAILED"
    assert first.first_terminal_cause == "LATER_CYCLE_SUPPLY_EXCEPTION_RUNTIMEERROR"
    assert calls == 1
    connection = sqlite3.connect(path)
    try:
        assert connection.execute(
            "SELECT status,retry_count FROM printer_scheduler_jobs"
        ).fetchone() == ("FAILED", 1)
        assert connection.execute(
            "SELECT COUNT(*) FROM printer_pre_admission_discovery_attempts"
        ).fetchone()[0] == 1
    finally:
        connection.close()


def test_missing_supply_terminalizes_blocked_and_cancels_scheduler(database) -> None:
    path, _, _ = database
    callback = AuthoritativeLiveOperationalCampaignOwner()._build_later_cycle_discovery_callback(
        db_path=path, configuration_id="configuration-1"
    )
    result = _invoke(callback)
    assert result.state == "BLOCKED"
    assert result.first_terminal_cause == "LATER_CYCLE_CANDIDATE_SUPPLY_NOT_WIRED"
    connection = sqlite3.connect(path)
    try:
        assert connection.execute(
            "SELECT status FROM printer_scheduler_jobs"
        ).fetchone()[0] == "CANCELLED"
    finally:
        connection.close()


def test_internal_refresh_outcome_remains_internal_at_final_attempt_result(
    database,
    monkeypatch,
) -> None:
    path, _, _ = database

    monkeypatch.setattr(
        "printer_v1.operator_cli.later_cycle_graduated_supply.build_graduated_supply",
        lambda db_path, **kwargs: GraduatedSupply(
            ready=False,
            terminal="BLOCKED_INSUFFICIENT_ELIGIBLE_CANDIDATE_POOL",
            graduated_supply=(),
            graduation_proofs={},
            candidate_a=None,
            candidate_b=None,
            two_candidate_selection={},
            handoff_readiness={},
            discovery_report={},
            front_door_report={},
            diagnostics={
                "shortage_classification": "DISCOVERY_ARCHITECTURE_FALSE_SHORTAGE",
                "pre_lifecycle_acquisition": {
                    "temporal_refresh_outcomes": [
                        {
                            "status": "INTERNAL_INVARIANT",
                            "failure_domain": "INTERNAL",
                        }
                    ]
                },
            },
            holder_reserve_supply=(),
            holder_reserve_candidates={},
        ),
    )

    def supply(**context):
        return build_later_cycle_graduated_supply(
            path,
            campaign_id=context["campaign_id"],
            campaign_run_id=context["campaign_run_id"],
            authoritative_factory_run_id=context["authoritative_factory_run_id"],
            proposed_cycle_id=context["proposed_cycle_id"],
            proposed_cycle_ordinal=context["proposed_cycle_ordinal"],
            evaluated_at=context["evaluated_at"],
            execution_id="execution-internal-refresh",
            selection_seed=context["selection_seed"],
            migration_transport=object(),
            graduated_supply_kwargs={},
        )

    callback = AuthoritativeLiveOperationalCampaignOwner(
        later_cycle_candidate_supply=supply
    )._build_later_cycle_discovery_callback(
        db_path=path,
        configuration_id="configuration-1",
    )

    result = _invoke(callback)

    assert result.state == "NO_PAIR"
    assert result.first_terminal_cause == "DISCOVERY_ARCHITECTURE_FALSE_SHORTAGE"
    assert result.failure_domain == FAILURE_DOMAIN_INTERNAL
