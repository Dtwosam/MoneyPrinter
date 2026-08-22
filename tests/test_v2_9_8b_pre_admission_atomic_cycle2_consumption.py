from __future__ import annotations

from datetime import datetime, timedelta, timezone
import json
import sqlite3

import pytest

from printer_v1.db import apply_migrations
from printer_v1.operator_cli.campaign_ownership import (
    CampaignOwnershipError,
    create_cycle_with_two_slots,
)
from printer_v1.operator_cli.four_token_proof_integration import build_four_token_proof_policy
from printer_v1.operator_cli.multi_cycle_campaign_coordinator import (
    MultiCycleAdmissionHealth,
    MultiCycleCampaignBinding,
    MultiCycleCoordinatorError,
    admit_two_token_cycle_from_attempt,
    multi_cycle_configuration_contract,
)


START = datetime(2026, 8, 13, 12, 0, tzinfo=timezone.utc)
NOW = START + timedelta(minutes=5)
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


@pytest.fixture()
def connection(tmp_path):
    path = tmp_path / "atomic-consumption.sqlite3"
    apply_migrations(path)
    connection = sqlite3.connect(path)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys=ON")
    configuration = {
        "token_capacity": 2,
        "ceilings": {"cycle_count": 2},
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
        ("configuration-1", "campaign-1", "a" * 64, json.dumps(configuration, sort_keys=True), "{}"),
    )
    connection.execute(
        "INSERT INTO printer_memory_factory_runs("
        "run_id,run_status,window_kind,db_mode,config_hash,config_json,started_at) "
        "VALUES (?,?,?,?,?,?,?)",
        ("factory-1", "RUNNING", "WINDOW_15M", "OPERATIONAL_PERSISTENT", "a" * 64, "{}", START.isoformat()),
    )
    connection.execute(
        "INSERT INTO printer_memory_factory_campaign_runs("
        "run_id,campaign_id,run_ordinal,run_state,authoritative_run_id,created_at,updated_at) "
        "VALUES (?,?,?,?,?,?,?)",
        ("campaign-run-1", "campaign-1", 1, "RUNNING", "factory-1", START.isoformat(), START.isoformat()),
    )
    for row_id in range(1, 5):
        connection.execute(
            "INSERT INTO printer_tokens(id,token_mint,chain) VALUES (?,?, 'solana')",
            (row_id, f"mint-{row_id}"),
        )
        connection.execute(
            "INSERT INTO printer_pairs(id,token_id,pair_address) VALUES (?,?,?)",
            (100 + row_id, row_id, f"pair-{row_id}"),
        )
    create_cycle_with_two_slots(
        connection,
        campaign_id="campaign-1",
        run_id="campaign-run-1",
        cycle_id="cycle-1",
        cycle_ordinal=1,
        slots=tuple(
            {
                "token_slot_id": f"t{slot}_c0001_slot",
                "slot_ordinal": slot,
                "token_identity": f"token-{slot}",
                "token_row_id": slot,
                "mint_identity": f"mint-{slot}",
                "pair_identity": f"pair-{slot}",
                "pair_row_id": 100 + slot,
                "lifecycle_identity": f"lifecycle-{slot}",
            }
            for slot in (1, 2)
        ),
        now=START.isoformat(),
    )
    connection.execute(
        "INSERT INTO printer_scheduler_jobs("
        "job_name,job_kind,target_table,priority,status,scheduled_for) "
        "VALUES ('pre-admission:attempt-1','PRE_ADMISSION_DISCOVERY_SELECTION',"
        "'printer_pre_admission_discovery_attempts',13,'SUCCEEDED',?)",
        (NOW.isoformat(),),
    )
    connection.execute(
        """INSERT INTO printer_pre_admission_discovery_attempts(
               attempt_id,campaign_id,campaign_run_id,configuration_id,
               authoritative_factory_run_id,proposed_cycle_ordinal,proposed_cycle_id,
               scheduler_job_id,cycle_cutoff,evaluated_at,selection_seed_identity,
               attempt_state,first_terminal_cause,terminal_at,created_at,updated_at
           ) VALUES ('attempt-1','campaign-1','campaign-run-1','configuration-1',
               'factory-1',2,'cycle-1-2',1,?,?, 'seed-2','PAIR_READY',
               'EXACT_PAIR_FROZEN',?,?,?)""",
        (NOW.isoformat(), NOW.isoformat(), NOW.isoformat(), NOW.isoformat(), NOW.isoformat()),
    )
    for slot in (1, 2):
        row_id = slot + 2
        connection.execute(
            """INSERT INTO printer_pre_admission_discovery_attempt_items(
                   attempt_id,slot_ordinal,token_identity,token_row_id,mint_identity,
                   pair_identity,pair_row_id,lifecycle_identity,canonical_market_identity,
                   canonical_pool_identity,canonical_evidence_json,
                   canonical_evidence_hash,evidence_version,observed_at,created_at,
                   frozen_tracking_lane,frozen_discovery_action,frozen_discovery_label,
                   frozen_classification_reason,frozen_lane_evidence_hash,
                   frozen_lane_decided_at,frozen_lane_decision_owner
               ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (
                "attempt-1", slot, f"token-{row_id}", row_id, f"mint-{row_id}",
                f"pair-{row_id}", 100 + row_id, f"lifecycle-{row_id}",
                f"solana-mainnet:pumpswap:pair-{row_id}", f"pair-{row_id}",
                '{"quality":"exact"}', str(row_id) * 64, "v1", NOW.isoformat(), NOW.isoformat(),
                "TRACK_NORMAL", "TRACK_NORMAL", "TRACK_NORMAL_CANDIDATE",
                "clean_solana_candidate_with_basic_market_fields",
                "ab" * 32, NOW.isoformat(),
                "classify_discovery_candidate+choose_tracking_lane",
            ),
        )
    connection.commit()
    try:
        yield connection
    finally:
        connection.close()


def test_pair_ready_attempt_is_consumed_with_exact_cycle2_atomically(connection) -> None:
    result = admit_two_token_cycle_from_attempt(
        connection,
        binding=BINDING,
        policy=POLICY,
        now=NOW,
        attempt_id="attempt-1",
        health=HEALTH,
    )
    assert result.mutation_performed
    assert result.cycle_id == "cycle-1-2"
    assert result.cycle_ordinal == 2
    assert tuple(connection.execute(
        "SELECT attempt_state,consumed_cycle_id FROM printer_pre_admission_discovery_attempts"
    ).fetchone()) == ("CONSUMED", "cycle-1-2")
    assert connection.execute(
        "SELECT COUNT(*) FROM printer_memory_factory_campaign_token_slots "
        "WHERE cycle_id='cycle-1-2'"
    ).fetchone()[0] == 2
    assert [tuple(row) for row in connection.execute(
        "SELECT token_slot_id,slot_ordinal,mint_identity,pair_identity "
        "FROM printer_memory_factory_campaign_token_slots "
        "WHERE cycle_id='cycle-1-2' ORDER BY slot_ordinal"
    )] == [
        ("slot-cycle-1-2-1", 1, "mint-3", "pair-3"),
        ("slot-cycle-1-2-2", 2, "mint-4", "pair-4"),
    ]


def test_changed_admission_decision_leaves_frozen_attempt_unconsumed(connection) -> None:
    unhealthy = MultiCycleAdmissionHealth(**{
        **HEALTH.__dict__, "source_budget_available": False
    })
    result = admit_two_token_cycle_from_attempt(
        connection,
        binding=BINDING,
        policy=POLICY,
        now=NOW,
        attempt_id="attempt-1",
        health=unhealthy,
    )
    assert not result.mutation_performed
    assert connection.execute(
        "SELECT attempt_state FROM printer_pre_admission_discovery_attempts"
    ).fetchone()[0] == "PAIR_READY"
    assert connection.execute(
        "SELECT COUNT(*) FROM printer_memory_factory_campaign_cycles"
    ).fetchone()[0] == 1


def test_identity_reuse_or_persistence_fault_rolls_back_cycle_and_consumption(connection) -> None:
    with pytest.raises(sqlite3.IntegrityError):
        connection.execute(
            "UPDATE printer_pre_admission_discovery_attempt_items SET mint_identity='mint-1' "
            "WHERE attempt_id='attempt-1' AND slot_ordinal=1"
        )
    connection.rollback()
    connection.execute("DROP TRIGGER printer_pre_admission_attempt_item_immutable_update")
    connection.execute(
        "UPDATE printer_pre_admission_discovery_attempt_items SET mint_identity='mint-1' "
        "WHERE attempt_id='attempt-1' AND slot_ordinal=1"
    )
    connection.commit()
    with pytest.raises(MultiCycleCoordinatorError, match="historical identity reuse"):
        admit_two_token_cycle_from_attempt(
            connection,
            binding=BINDING,
            policy=POLICY,
            now=NOW,
            attempt_id="attempt-1",
            health=HEALTH,
        )
    assert tuple(connection.execute(
        "SELECT attempt_state,consumed_cycle_id,consumed_at "
        "FROM printer_pre_admission_discovery_attempts"
    ).fetchone()) == ("PAIR_READY", None, None)
    assert connection.execute(
        "SELECT COUNT(*) FROM printer_memory_factory_campaign_cycles"
    ).fetchone()[0] == 1


def test_second_slot_ownership_failure_rolls_back_cycle_and_attempt(connection) -> None:
    connection.execute(
        """CREATE TRIGGER injected_second_slot_ownership_failure
           BEFORE INSERT ON printer_memory_factory_campaign_token_slots
           WHEN NEW.cycle_id='cycle-1-2' AND NEW.slot_ordinal=2
           BEGIN
               SELECT RAISE(ABORT, 'injected exact ownership failure');
           END"""
    )
    connection.commit()

    with pytest.raises(
        CampaignOwnershipError,
        match="injected exact ownership failure",
    ):
        admit_two_token_cycle_from_attempt(
            connection,
            binding=BINDING,
            policy=POLICY,
            now=NOW,
            attempt_id="attempt-1",
            health=HEALTH,
        )

    assert connection.execute(
        "SELECT COUNT(*) FROM printer_memory_factory_campaign_cycles "
        "WHERE cycle_id='cycle-1-2'"
    ).fetchone()[0] == 0
    assert connection.execute(
        "SELECT COUNT(*) FROM printer_memory_factory_campaign_token_slots "
        "WHERE cycle_id='cycle-1-2'"
    ).fetchone()[0] == 0
    assert tuple(connection.execute(
        "SELECT attempt_state,consumed_cycle_id,consumed_at "
        "FROM printer_pre_admission_discovery_attempts"
    ).fetchone()) == ("PAIR_READY", None, None)
