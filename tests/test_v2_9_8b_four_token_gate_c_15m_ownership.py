from __future__ import annotations

from datetime import datetime, timezone
import json
import sqlite3

from printer_v1.db import apply_migrations
from printer_v1.operator_cli.campaign_ownership import create_cycle_with_two_slots
from printer_v1.operator_cli.one_command_15m_factory import _plan_opening_jobs
from printer_v1.operator_cli.operational_selective_1h import (
    persist_15m_campaign_window,
)


NOW = datetime(2026, 8, 13, 12, 0, tzinfo=timezone.utc)


def test_proof_opening_precreates_planned_windows_and_exact_scheduler_owners(tmp_path) -> None:
    path = tmp_path / "gate-c.sqlite3"
    apply_migrations(path)
    connection = sqlite3.connect(path)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys=ON")
    connection.execute(
        "INSERT INTO printer_memory_factory_campaigns("
        "campaign_id,campaign_state,db_mode,db_target_identity,policy_version) "
        "VALUES ('campaign-1','RUNNING','OPERATIONAL_PERSISTENT','db','policy')"
    )
    connection.execute(
        "INSERT INTO printer_memory_factory_runs("
        "run_id,run_status,window_kind,db_mode,config_hash,config_json,started_at) "
        "VALUES ('factory-1','RUNNING','WINDOW_15M','PROOF_ONLY',?,?,?)",
        (
            "a" * 64,
            json.dumps({
                "four_token_proof": True,
                "campaign_id": "campaign-1",
                "campaign_run_id": "campaign-run-1",
                "configuration_id": "configuration-1",
            }),
            NOW.isoformat(),
        ),
    )
    connection.execute(
        "INSERT INTO printer_memory_factory_campaign_runs("
        "run_id,campaign_id,run_ordinal,run_state,authoritative_run_id,created_at,updated_at) "
        "VALUES ('campaign-run-1','campaign-1',1,'RUNNING','factory-1',?,?)",
        (NOW.isoformat(), NOW.isoformat()),
    )
    slots = []
    targets = []
    for ordinal in (1, 2):
        connection.execute(
            "INSERT INTO printer_tokens(id,token_mint) VALUES (?,?)",
            (ordinal, f"mint-{ordinal}"),
        )
        connection.execute(
            "INSERT INTO printer_pairs(id,token_id,pair_address) VALUES (?,?,?)",
            (100 + ordinal, ordinal, f"pool-{ordinal}"),
        )
        slots.append({
            "token_slot_id": f"t{ordinal}_c0001_slot",
            "slot_ordinal": ordinal,
            "token_identity": f"solana-mainnet:mint-{ordinal}",
            "token_row_id": ordinal,
            "mint_identity": f"mint-{ordinal}",
            "pair_identity": f"pool-{ordinal}",
            "pair_row_id": 100 + ordinal,
            "lifecycle_identity": "PUMPSWAP_GRADUATED_CONFIRMED",
            "tracking_queue_id": None,
        })
        targets.append({
            "token_id": ordinal,
            "pair_id": 100 + ordinal,
            "token_mint": f"mint-{ordinal}",
            "pair_address": f"pool-{ordinal}",
            "tracking_lane": "TRACK_NORMAL",
        })
    create_cycle_with_two_slots(
        connection,
        campaign_id="campaign-1",
        run_id="campaign-run-1",
        cycle_id="cycle-1",
        cycle_ordinal=1,
        slots=slots,
        now=NOW.isoformat(),
    )

    _plan_opening_jobs(
        connection,
        "factory-1",
        targets,
        NOW,
        cycle_ordinal=1,
        four_token_proof=True,
    )

    windows = connection.execute(
        "SELECT cycle_id,token_slot_id,window_kind,window_state,memory_window_row_id "
        "FROM printer_memory_factory_campaign_windows ORDER BY token_slot_id"
    ).fetchall()
    assert [tuple(row) for row in windows] == [
        ("cycle-1", "t1_c0001_slot", "WINDOW_15M", "PLANNED", None),
        ("cycle-1", "t2_c0001_slot", "WINDOW_15M", "PLANNED", None),
    ]
    assert connection.execute(
        "SELECT COUNT(*) FROM printer_memory_factory_campaign_scheduler_work "
        "WHERE ownership_contract_version='V2_STAGE_SCOPED' "
        "AND work_scope='WINDOW_LIFECYCLE' AND stage_id='WINDOW_15M' "
        "AND factory_run_id='factory-1'"
    ).fetchone()[0] == 2
    original_ids = [str(row[0]) for row in connection.execute(
        "SELECT window_id FROM printer_memory_factory_campaign_windows ORDER BY token_slot_id"
    )]
    for ordinal in (1, 2):
        memory_id = int(connection.execute(
            "INSERT INTO printer_memory_windows("
            "token_id,pair_id,window_kind,opened_at,closed_at,memory_status,"
            "data_quality_label,do_not_train) "
            "VALUES (?,?, 'WINDOW_15M',?,?,'AUDIT_ONLY','CLEAN_DATA',1)",
            (ordinal, 100 + ordinal, NOW.isoformat(), NOW.isoformat()),
        ).lastrowid)
        persisted = persist_15m_campaign_window(
            connection,
            campaign_id="campaign-1",
            run_id="campaign-run-1",
            cycle_id="cycle-1",
            token_slot_id=f"t{ordinal}_c0001_slot",
            token_row_id=ordinal,
            pair_row_id=100 + ordinal,
            lifecycle_identity="PUMPSWAP_GRADUATED_CONFIRMED",
            memory_window_row_id=memory_id,
            checkpoint_cutoff=NOW.isoformat(),
            window_state="AUDITING",
            now=NOW.isoformat(),
        )
        assert persisted["window_id"] == original_ids[ordinal - 1]
    assert connection.execute(
        "SELECT COUNT(*) FROM printer_memory_factory_campaign_windows"
    ).fetchone()[0] == 2
    assert [row[0] for row in connection.execute(
        "SELECT window_state FROM printer_memory_factory_campaign_windows ORDER BY token_slot_id"
    )] == ["AUDITING", "AUDITING"]
    connection.close()
