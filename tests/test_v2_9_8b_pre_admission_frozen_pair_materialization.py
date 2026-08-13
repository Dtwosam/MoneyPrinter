from __future__ import annotations

from datetime import datetime, timezone
import json
import sqlite3
from unittest.mock import patch

import pytest

from printer_v1.db import apply_migrations
from printer_v1.operator_cli.campaign_ownership import create_cycle_with_two_slots
from printer_v1.discovery.pre_admission_materialization import (
    PreAdmissionMaterializationError,
    materialize_consumed_pre_admission_pair,
)


NOW = datetime(2026, 8, 13, 12, 0, tzinfo=timezone.utc)


def _slot(row_id: int, ordinal: int, cycle_ordinal: int) -> dict[str, object]:
    return {
        "token_slot_id": f"t{ordinal}_c{cycle_ordinal:04d}_slot",
        "slot_ordinal": ordinal,
        "token_identity": f"solana-mainnet:mint-{row_id}",
        "token_row_id": row_id,
        "mint_identity": f"mint-{row_id}",
        "pair_identity": f"pool-{row_id}",
        "pair_row_id": 100 + row_id,
        "lifecycle_identity": "PUMPSWAP_GRADUATED_CONFIRMED",
    }


@pytest.fixture()
def connection(tmp_path):
    path = tmp_path / "frozen-materialization.sqlite3"
    apply_migrations(path)
    connection = sqlite3.connect(path)
    connection.row_factory = sqlite3.Row
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
        ("configuration-1", "campaign-1", "a" * 64, "{}", '{"commit":"frozen"}'),
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
    for row_id in range(1, 5):
        connection.execute(
            "INSERT INTO printer_tokens(id,token_mint,chain) VALUES (?,?, 'solana')",
            (row_id, f"mint-{row_id}"),
        )
        connection.execute(
            "INSERT INTO printer_pairs(id,token_id,pair_address,base_token_mint) VALUES (?,?,?,?)",
            (100 + row_id, row_id, f"pool-{row_id}", f"mint-{row_id}"),
        )
    create_cycle_with_two_slots(
        connection,
        campaign_id="campaign-1",
        run_id="campaign-run-1",
        cycle_id="cycle-1",
        cycle_ordinal=1,
        slots=(_slot(1, 1, 1), _slot(2, 2, 1)),
        now=NOW.isoformat(),
    )
    create_cycle_with_two_slots(
        connection,
        campaign_id="campaign-1",
        run_id="campaign-run-1",
        cycle_id="cycle-2",
        cycle_ordinal=2,
        slots=(_slot(3, 1, 2), _slot(4, 2, 2)),
        now=NOW.isoformat(),
    )
    scheduler_job_id = int(connection.execute(
        "INSERT INTO printer_scheduler_jobs("
        "job_name,job_kind,target_table,priority,status,scheduled_for,finished_at) "
        "VALUES ('pre-admission:attempt-1','PRE_ADMISSION_DISCOVERY_SELECTION',"
        "'printer_pre_admission_discovery_attempts',13,'SUCCEEDED',?,?)",
        (NOW.isoformat(), NOW.isoformat()),
    ).lastrowid)
    request_id = int(connection.execute(
        "INSERT INTO printer_source_requests("
        "source_name,request_kind,requested_at,source_status,data_quality_label) "
        "VALUES ('dexscreener','fresh_profiles',?,'COMPLETE','CLEAN_DATA')",
        (NOW.isoformat(),),
    ).lastrowid)
    response_id = int(connection.execute(
        "INSERT INTO printer_source_responses("
        "source_request_id,source_name,received_at,source_status,data_quality_label) "
        "VALUES (?,'dexscreener',?,'COMPLETE','CLEAN_DATA')",
        (request_id, NOW.isoformat()),
    ).lastrowid)
    connection.execute(
        """INSERT INTO printer_pre_admission_discovery_attempts(
               attempt_id,campaign_id,campaign_run_id,configuration_id,
               authoritative_factory_run_id,proposed_cycle_ordinal,proposed_cycle_id,
               scheduler_job_id,cycle_cutoff,evaluated_at,selection_seed_identity,
               attempt_state,first_terminal_cause,terminal_at,consumed_cycle_id,
               consumed_at,created_at,updated_at
           ) VALUES ('attempt-1','campaign-1','campaign-run-1','configuration-1',
               'factory-1',2,'cycle-2',?,?,?,'seed-2','CONSUMED',
               'EXACT_PAIR_FROZEN',?,'cycle-2',?,?,?)""",
        (scheduler_job_id, NOW.isoformat(), NOW.isoformat(), NOW.isoformat(), NOW.isoformat(), NOW.isoformat(), NOW.isoformat()),
    )
    channels = (("LATEST_PUMPFUN",), ("TOP_PUMPFUN",))
    for ordinal, row_id in enumerate((3, 4), start=1):
        evidence_json = json.dumps({"mint": f"mint-{row_id}", "quality": "exact"}, sort_keys=True)
        connection.execute(
            """INSERT INTO printer_pre_admission_discovery_attempt_items(
                   attempt_id,slot_ordinal,token_identity,token_row_id,mint_identity,
                   pair_identity,pair_row_id,lifecycle_identity,canonical_market_identity,
                   canonical_pool_identity,channel_labels_json,canonical_evidence_json,
                   canonical_evidence_hash,evidence_version,observed_at,created_at
               ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (
                "attempt-1", ordinal, f"solana-mainnet:mint-{row_id}", row_id,
                f"mint-{row_id}", f"pool-{row_id}", 100 + row_id,
                "PUMPSWAP_GRADUATED_CONFIRMED",
                f"solana-mainnet:pumpswap:pool-{row_id}", f"pool-{row_id}",
                json.dumps(channels[ordinal - 1]), evidence_json,
                str(row_id) * 64, "v1", NOW.isoformat(), NOW.isoformat(),
            ),
        )
    connection.execute(
        "INSERT INTO printer_pre_admission_discovery_attempt_source_links("
        "attempt_id,link_ordinal,logical_stage,source_request_id,source_response_id,created_at) "
        "VALUES ('attempt-1',1,'ELIGIBLE_SUPPLY',?,?,?)",
        (request_id, response_id, NOW.isoformat()),
    )
    connection.commit()
    try:
        yield connection
    finally:
        connection.close()


def _materialize(connection, **overrides):
    arguments = {
        "attempt_id": "attempt-1",
        "campaign_id": "campaign-1",
        "campaign_run_id": "campaign-run-1",
        "configuration_id": "configuration-1",
        "authoritative_factory_run_id": "factory-1",
        "cycle_id": "cycle-2",
        "now": NOW,
    }
    arguments.update(overrides)
    return materialize_consumed_pre_admission_pair(connection, **arguments)


def test_consumed_pair_materializes_cycle_rooted_ownership_without_refetch_or_reselection(connection) -> None:
    source_count = connection.execute("SELECT COUNT(*) FROM printer_source_requests").fetchone()[0]
    traced: list[str] = []
    connection.set_trace_callback(traced.append)
    with patch(
        "printer_v1.discovery.combined_executor.apply_existing_discovery_gate_and_selection",
        side_effect=AssertionError("selector must not run"),
    ):
        result = _materialize(connection)
    connection.set_trace_callback(None)

    assert result.discovery_batch_id == "pre-admission-materialized:attempt-1"
    assert result.selection_batch_id == "selection:pre-admission-materialized:attempt-1"
    assert result.materialized_item_count == 2
    assert connection.execute("SELECT COUNT(*) FROM printer_source_requests").fetchone()[0] == source_count
    assert not any("INSERT INTO printer_source_requests" in statement for statement in traced)
    assert [tuple(row) for row in connection.execute(
        "SELECT token_slot_id,tracking_handoff_state,first_window_15m_scheduler_job_id "
        "FROM printer_discovery_selected_item_links ORDER BY token_slot_id"
    )] == [
        ("t1_c0002_slot", "LINKED_ONLY", None),
        ("t2_c0002_slot", "LINKED_ONLY", None),
    ]
    assert [json.loads(row[0]) for row in connection.execute(
        "SELECT channel_labels_json FROM printer_discovery_merged_candidates "
        "ORDER BY mint_identity"
    )] == [["LATEST_PUMPFUN"], ["TOP_PUMPFUN"]]
    assert connection.execute(
        "SELECT COUNT(*) FROM printer_discovery_work_source_links"
    ).fetchone()[0] == 1


@pytest.mark.parametrize(
    ("mutation", "error"),
    (
        ("unconsumed", "ATTEMPT_NOT_CONSUMED"),
        ("pair_substitution", "FROZEN_PAIR_CYCLE_DRIFT"),
        ("evidence_drift", "SOURCE_EVIDENCE_DRIFT"),
    ),
)
def test_materialization_fails_closed_on_state_identity_or_evidence_drift(connection, mutation, error) -> None:
    if mutation == "unconsumed":
        connection.execute("DROP TRIGGER printer_pre_admission_attempt_transition")
        connection.execute(
            "UPDATE printer_pre_admission_discovery_attempts SET attempt_state='PAIR_READY',"
            "consumed_cycle_id=NULL,consumed_at=NULL WHERE attempt_id='attempt-1'"
        )
    elif mutation == "pair_substitution":
        connection.execute(
            "UPDATE printer_memory_factory_campaign_token_slots SET mint_identity='mint-substitute' "
            "WHERE cycle_id='cycle-2' AND slot_ordinal=1"
        )
    else:
        second_request = int(connection.execute(
            "INSERT INTO printer_source_requests("
            "source_name,request_kind,requested_at,source_status,data_quality_label) "
            "VALUES ('geckoterminal','new_pools',?,'COMPLETE','CLEAN_DATA')",
            (NOW.isoformat(),),
        ).lastrowid)
        connection.execute(
            "UPDATE printer_source_responses SET source_request_id=? WHERE id=1",
            (second_request,),
        )
    connection.commit()
    with pytest.raises(PreAdmissionMaterializationError, match=error):
        _materialize(connection)
    assert connection.execute("SELECT COUNT(*) FROM printer_discovery_batches").fetchone()[0] == 0


def test_materialization_rejects_wrong_cycle_or_factory_owner(connection) -> None:
    with pytest.raises(PreAdmissionMaterializationError, match="ATTEMPT_OWNERSHIP_MISMATCH"):
        _materialize(connection, authoritative_factory_run_id="wrong-factory")
    with pytest.raises(PreAdmissionMaterializationError, match="CONSUMED_CYCLE_MISMATCH"):
        _materialize(connection, cycle_id="cycle-1")

