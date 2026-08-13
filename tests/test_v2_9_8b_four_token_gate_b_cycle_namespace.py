from __future__ import annotations

from datetime import datetime, timezone
import json
import sqlite3

from printer_v1.db import apply_migrations
from printer_v1.operator_cli.campaign_ownership import create_cycle_with_two_slots
from printer_v1.operator_cli.four_token_proof_integration import cycle_step_key
from printer_v1.operator_cli.multi_cycle_memory_growth import (
    scaled_standard_four_hour_capacity_contract,
)
from printer_v1.operator_cli.one_command_15m_factory import (
    _plan_opening_jobs,
    _scheduler_ceiling_for_run_config,
    _token_prefix,
    _token_request_count,
)


NOW = datetime(2026, 8, 13, 12, 0, tzinfo=timezone.utc)


def _run(connection: sqlite3.Connection) -> None:
    config = {
        "four_token_proof": True,
        "standard_four_hour_campaign": True,
        "campaign_id": "campaign-1",
        "campaign_run_id": "campaign-run-1",
    }
    connection.execute(
        "INSERT INTO printer_memory_factory_campaigns("
        "campaign_id,campaign_state,db_mode,db_target_identity,policy_version) "
        "VALUES ('campaign-1','RUNNING','OPERATIONAL_PERSISTENT','db','policy')"
    )
    connection.execute(
        "INSERT INTO printer_memory_factory_runs("
        "run_id,run_status,window_kind,db_mode,config_hash,config_json,started_at) "
        "VALUES ('factory-1','RUNNING','WINDOW_15M','PROOF_ONLY',?,?,?)",
        ("a" * 64, json.dumps(config), NOW.isoformat()),
    )
    connection.execute(
        "INSERT INTO printer_memory_factory_campaign_runs("
        "run_id,campaign_id,run_ordinal,run_state,authoritative_run_id,created_at,updated_at) "
        "VALUES ('campaign-run-1','campaign-1',1,'RUNNING','factory-1',?,?)",
        (NOW.isoformat(), NOW.isoformat()),
    )


def test_cycle_two_opening_and_request_accounting_are_namespaced(tmp_path) -> None:
    path = tmp_path / "gate-b.sqlite3"
    apply_migrations(path)
    connection = sqlite3.connect(path)
    connection.row_factory = sqlite3.Row
    _run(connection)
    targets = [
        {
            "token_id": ordinal,
            "pair_id": 100 + ordinal,
            "token_mint": f"mint-{ordinal}",
            "pair_address": f"pool-{ordinal}",
            "tracking_lane": "TRACK_NORMAL",
        }
        for ordinal in (3, 4)
    ]
    for target in targets:
        connection.execute(
            "INSERT INTO printer_tokens(id,token_mint) VALUES (?,?)",
            (target["token_id"], target["token_mint"]),
        )
        connection.execute(
            "INSERT INTO printer_pairs(id,token_id,pair_address) VALUES (?,?,?)",
            (target["pair_id"], target["token_id"], target["pair_address"]),
        )
    create_cycle_with_two_slots(
        connection,
        campaign_id="campaign-1",
        run_id="campaign-run-1",
        cycle_id="cycle-2",
        cycle_ordinal=2,
        slots=tuple({
            "token_slot_id": f"t{slot}_c0002_slot",
            "slot_ordinal": slot,
            "token_identity": f"solana-mainnet:mint-{target['token_id']}",
            "token_row_id": target["token_id"],
            "mint_identity": target["token_mint"],
            "pair_identity": target["pair_address"],
            "pair_row_id": target["pair_id"],
            "lifecycle_identity": "PUMPSWAP_GRADUATED_CONFIRMED",
            "tracking_queue_id": None,
        } for slot, target in enumerate(targets, start=1)),
        now=NOW.isoformat(),
    )
    _plan_opening_jobs(
        connection,
        "factory-1",
        targets,
        NOW,
        cycle_ordinal=2,
        four_token_proof=True,
    )
    assert [row[0] for row in connection.execute(
        "SELECT step_key FROM printer_memory_factory_run_steps ORDER BY id"
    )] == [
        cycle_step_key(slot_ordinal=1, cycle_ordinal=2, suffix="snapshot_00"),
        cycle_step_key(slot_ordinal=2, cycle_ordinal=2, suffix="snapshot_00"),
    ]
    assert _token_prefix("t1_snapshot_00") == "t1"
    assert _token_prefix("t1_c0002_snapshot_00") == "t1_c0002"
    connection.execute(
        "INSERT INTO printer_source_requests("
        "source_name,request_kind,requested_at,request_key,source_status,data_quality_label) "
        "VALUES ('dexscreener','pair',?,?, 'COMPLETE','CLEAN_DATA')",
        (NOW.isoformat(), "factory-1:t1_c0002_snapshot_00:1"),
    )
    assert _token_request_count(connection, "factory-1", "t1_c0002") == 1
    assert _token_request_count(connection, "factory-1", "t1") == 0
    connection.close()


def test_four_token_scheduler_ceiling_is_derived_not_copied() -> None:
    expected = int(
        scaled_standard_four_hour_capacity_contract(4)[
            "lifecycle_scheduler_outer_ceiling"
        ]
    )
    assert _scheduler_ceiling_for_run_config({"four_token_proof": True}) == expected
