from __future__ import annotations

from datetime import datetime, timedelta, timezone
import json
import sqlite3
from unittest.mock import patch

from printer_v1.db import apply_migrations
from printer_v1.operator_cli.abstract_campaign_command import (
    CENTRAL_SCHEDULER_OWNER,
    SOURCE_GOVERNOR_OWNER,
    OwnerPort,
)
from printer_v1.operator_cli.authoritative_live_operational_campaign import (
    AuthoritativeLiveOperationalCampaignOwner,
)
from printer_v1.operator_cli.campaign_ownership import create_cycle_with_two_slots
from printer_v1.operator_cli.four_token_proof_integration import (
    LaterCycleCandidateSupply,
    LaterCycleDiscoveryCandidate,
    LaterCycleSourceEvidence,
    build_four_token_proof_policy,
)
from printer_v1.operator_cli.multi_cycle_campaign_coordinator import (
    MultiCycleAdmissionHealth,
    MultiCycleCampaignBinding,
    admit_two_token_cycle_from_attempt,
    multi_cycle_configuration_contract,
)
from printer_v1.discovery.pre_admission_materialization import (
    materialize_consumed_pre_admission_pair,
)


START = datetime(2026, 8, 13, 12, 0, tzinfo=timezone.utc)
NOW = START + timedelta(minutes=5)
GRADUATED = "PUMPSWAP_GRADUATED_CONFIRMED"
POLICY = build_four_token_proof_policy()
BINDING = MultiCycleCampaignBinding(
    campaign_id="campaign-1",
    campaign_run_id="campaign-run-1",
    configuration_id="configuration-1",
    authoritative_factory_run_id="factory-1",
)
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
GOVERNOR = OwnerPort(SOURCE_GOVERNOR_OWNER, True)
SCHEDULER = OwnerPort(CENTRAL_SCHEDULER_OWNER, True)


def _slot(row_id: int, ordinal: int) -> dict[str, object]:
    return {
        "token_slot_id": f"t{ordinal}_c0001_slot",
        "slot_ordinal": ordinal,
        "token_identity": f"solana-mainnet:mint-{row_id}",
        "token_row_id": row_id,
        "mint_identity": f"mint-{row_id}",
        "pair_identity": f"pool-{row_id}",
        "pair_row_id": 100 + row_id,
        "lifecycle_identity": GRADUATED,
        "tracking_queue_id": None,
        "replacement_predecessor_slot_id": None,
    }


def _candidate(row_id: int, channel: str) -> LaterCycleDiscoveryCandidate:
    return LaterCycleDiscoveryCandidate(
        token_identity=f"solana-mainnet:mint-{row_id}",
        token_row_id=row_id,
        mint_identity=f"mint-{row_id}",
        pair_identity=f"pool-{row_id}",
        pair_row_id=100 + row_id,
        lifecycle_identity=GRADUATED,
        canonical_market_identity=f"solana-mainnet:pumpswap:pool-{row_id}",
        canonical_pool_identity=f"pool-{row_id}",
        channels=frozenset({channel}),
        holder_evidence_eligible=True,
        canonical_evidence_json=json.dumps(
            {"mint": f"mint-{row_id}", "quality": "exact"}, sort_keys=True
        ),
        canonical_evidence_hash=str(row_id) * 64,
        evidence_version="v1",
        observed_at=NOW,
    )


def _prepare_database(tmp_path):
    path = tmp_path / "callback-consume-materialize.sqlite3"
    apply_migrations(path)
    connection = sqlite3.connect(path)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys=ON")
    configuration = {
        "token_capacity": 2,
        "ceilings": {"cycle_count": POLICY.total_cycle_admission_ceiling},
        "multi_cycle_capacity": multi_cycle_configuration_contract(
            POLICY, intake_started_at=START
        ),
    }
    connection.execute(
        "INSERT INTO printer_memory_factory_campaigns("
        "campaign_id,campaign_state,db_mode,db_target_identity,policy_version) "
        "VALUES ('campaign-1','RUNNING','OPERATIONAL_PERSISTENT','db-1','policy-1')"
    )
    connection.execute(
        "INSERT INTO printer_memory_factory_campaign_configurations("
        "configuration_id,campaign_id,configuration_hash,configuration_json,"
        "launch_provenance_json) VALUES (?,?,?,?,?)",
        (
            "configuration-1",
            "campaign-1",
            "a" * 64,
            json.dumps(configuration, sort_keys=True),
            '{"commit":"disposable"}',
        ),
    )
    connection.execute(
        "INSERT INTO printer_memory_factory_runs("
        "run_id,run_status,window_kind,db_mode,config_hash,config_json,started_at) "
        "VALUES (?,?,?,?,?,?,?)",
        (
            "factory-1",
            "RUNNING",
            "WINDOW_15M",
            "OPERATIONAL_PERSISTENT",
            "a" * 64,
            "{}",
            START.isoformat(),
        ),
    )
    connection.execute(
        "INSERT INTO printer_memory_factory_campaign_runs("
        "run_id,campaign_id,run_ordinal,run_state,authoritative_run_id,created_at,updated_at) "
        "VALUES (?,?,?,?,?,?,?)",
        (
            "campaign-run-1",
            "campaign-1",
            1,
            "RUNNING",
            "factory-1",
            START.isoformat(),
            START.isoformat(),
        ),
    )
    for row_id in range(1, 5):
        connection.execute(
            "INSERT INTO printer_tokens(id,token_mint,chain) VALUES (?,?, 'solana')",
            (row_id, f"mint-{row_id}"),
        )
        connection.execute(
            "INSERT INTO printer_pairs(id,token_id,pair_address,base_token_mint) "
            "VALUES (?,?,?,?)",
            (100 + row_id, row_id, f"pool-{row_id}", f"mint-{row_id}"),
        )
    create_cycle_with_two_slots(
        connection,
        campaign_id=BINDING.campaign_id,
        run_id=BINDING.campaign_run_id,
        cycle_id="cycle-1",
        cycle_ordinal=1,
        slots=(_slot(1, 1), _slot(2, 2)),
        now=START.isoformat(),
    )
    request_id = int(
        connection.execute(
            "INSERT INTO printer_source_requests("
            "source_name,request_kind,requested_at,source_status,data_quality_label) "
            "VALUES ('dexscreener','fresh_profiles',?,'COMPLETE','CLEAN_DATA')",
            (NOW.isoformat(),),
        ).lastrowid
    )
    response_id = int(
        connection.execute(
            "INSERT INTO printer_source_responses("
            "source_request_id,source_name,received_at,source_status,data_quality_label) "
            "VALUES (?,'dexscreener',?,'COMPLETE','CLEAN_DATA')",
            (request_id, NOW.isoformat()),
        ).lastrowid
    )
    connection.commit()
    connection.close()
    return path, request_id, response_id


def test_real_callback_pair_consumes_and_materializes_without_refetch_or_reselection(tmp_path) -> None:
    path, request_id, response_id = _prepare_database(tmp_path)
    supply_calls = 0

    def supply(**_):
        nonlocal supply_calls
        supply_calls += 1
        return LaterCycleCandidateSupply(
            candidates=(
                _candidate(3, "LATEST_PUMPFUN"),
                _candidate(4, "TOP_PUMPFUN"),
            ),
            source_evidence=(
                LaterCycleSourceEvidence(
                    logical_stage="ELIGIBLE_SUPPLY",
                    source_request_id=request_id,
                    source_response_id=response_id,
                ),
            ),
            terminal_cause=None,
        )

    callback = AuthoritativeLiveOperationalCampaignOwner(
        later_cycle_candidate_supply=supply
    )._build_later_cycle_discovery_callback(
        db_path=path, configuration_id=BINDING.configuration_id
    )
    callback_result = callback(
        campaign_id=BINDING.campaign_id,
        campaign_run_id=BINDING.campaign_run_id,
        authoritative_factory_run_id=BINDING.authoritative_factory_run_id,
        cycle_id="cycle-1-2",
        cycle_ordinal=2,
        cycle_cutoff=NOW.isoformat(),
        evaluated_at=NOW.isoformat(),
        selection_seed="seed-2",
        source_governor=GOVERNOR,
        central_scheduler=SCHEDULER,
        admission_health=HEALTH,
    )
    assert callback_result.state == "PAIR_READY"
    assert callback_result.selected_count == 2

    connection = sqlite3.connect(path)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys=ON")
    source_count = int(
        connection.execute("SELECT COUNT(*) FROM printer_source_requests").fetchone()[0]
    )
    admission = admit_two_token_cycle_from_attempt(
        connection,
        binding=BINDING,
        policy=POLICY,
        now=NOW,
        attempt_id=callback_result.attempt_id,
        health=HEALTH,
    )
    assert admission.mutation_performed
    assert admission.cycle_id == "cycle-1-2"
    assert admission.cycle_ordinal == 2

    with patch(
        "printer_v1.discovery.combined_executor.apply_existing_discovery_gate_and_selection",
        side_effect=AssertionError("materialization must not reselect"),
    ):
        materialized = materialize_consumed_pre_admission_pair(
            connection,
            attempt_id=callback_result.attempt_id,
            campaign_id=BINDING.campaign_id,
            campaign_run_id=BINDING.campaign_run_id,
            configuration_id=BINDING.configuration_id,
            authoritative_factory_run_id=BINDING.authoritative_factory_run_id,
            cycle_id="cycle-1-2",
            now=NOW,
        )
    assert materialized.materialized_item_count == 2
    assert int(connection.execute(
        "SELECT COUNT(*) FROM printer_source_requests"
    ).fetchone()[0]) == source_count
    assert [tuple(row) for row in connection.execute(
        "SELECT token_slot_id,mint_identity,pair_identity,lifecycle_identity "
        "FROM printer_memory_factory_campaign_token_slots "
        "WHERE cycle_id='cycle-1-2' ORDER BY slot_ordinal"
    )] == [
        ("t1_c0002_slot", "mint-3", "pool-3", GRADUATED),
        ("t2_c0002_slot", "mint-4", "pool-4", GRADUATED),
    ]
    assert [tuple(row) for row in connection.execute(
        "SELECT token_slot_id,tracking_handoff_state,first_window_15m_scheduler_job_id "
        "FROM printer_discovery_selected_item_links ORDER BY token_slot_id"
    )] == [
        ("t1_c0002_slot", "LINKED_ONLY", None),
        ("t2_c0002_slot", "LINKED_ONLY", None),
    ]
    assert connection.execute(
        "SELECT COUNT(*) FROM printer_scheduler_jobs "
        "WHERE job_kind!='PRE_ADMISSION_DISCOVERY_SELECTION'"
    ).fetchone()[0] == 0
    assert connection.execute(
        "SELECT COUNT(*) FROM printer_pre_admission_discovery_attempts"
    ).fetchone()[0] == 1
    assert tuple(connection.execute(
        "SELECT attempt_state,consumed_cycle_id FROM "
        "printer_pre_admission_discovery_attempts"
    ).fetchone()) == ("CONSUMED", "cycle-1-2")
    assert tuple(connection.execute(
        "SELECT status,retry_count FROM printer_scheduler_jobs"
    ).fetchone()) == ("SUCCEEDED", 0)
    connection.close()

    repeated = callback(
        campaign_id=BINDING.campaign_id,
        campaign_run_id=BINDING.campaign_run_id,
        authoritative_factory_run_id=BINDING.authoritative_factory_run_id,
        cycle_id="cycle-1-2",
        cycle_ordinal=2,
        cycle_cutoff=NOW.isoformat(),
        evaluated_at=NOW.isoformat(),
        selection_seed="seed-2",
        source_governor=GOVERNOR,
        central_scheduler=SCHEDULER,
        admission_health=HEALTH,
    )
    assert repeated.state == "CONSUMED"
    assert repeated.attempt_id == callback_result.attempt_id
    assert supply_calls == 1
