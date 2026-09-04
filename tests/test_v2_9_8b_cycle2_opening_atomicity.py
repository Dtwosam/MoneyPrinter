from __future__ import annotations

from datetime import datetime, timezone
import json
import sqlite3

import pytest

from printer_v1.db import apply_migrations
from printer_v1.operator_cli import one_command_15m_factory as factory
from printer_v1.operator_cli.cadence_authority import (
    claim_tracking_authority_for_slot_insert,
)
from printer_v1.operator_cli.campaign_ownership import create_cycle_with_two_slots


NOW = datetime(2026, 9, 4, 20, 15, tzinfo=timezone.utc)
CAMPAIGN_ID = "cycle2-opening-atomicity-campaign"
CAMPAIGN_RUN_ID = "cycle2-opening-atomicity-run"
FACTORY_RUN_ID = "cycle2-opening-atomicity-factory"
CYCLE2_ID = "cycle2-opening-atomicity-cycle-2"


def _slot(row_id: int, ordinal: int, queue_id: int) -> dict[str, object]:
    return {
        "token_slot_id": f"t{ordinal}_c0002_slot",
        "slot_ordinal": ordinal,
        "token_identity": f"solana-mainnet:mint-{row_id}",
        "token_row_id": row_id,
        "mint_identity": f"mint-{row_id}",
        "pair_identity": f"pool-{row_id}",
        "pair_row_id": 100 + row_id,
        "lifecycle_identity": "PUMPSWAP_GRADUATED_CONFIRMED",
        "tracking_queue_id": queue_id,
        "replacement_predecessor_slot_id": None,
    }


def _target(row_id: int, queue_id: int) -> dict[str, object]:
    return {
        "token_id": row_id,
        "pair_id": 100 + row_id,
        "token_mint": f"mint-{row_id}",
        "pair_address": f"pool-{row_id}",
        "tracking_lane": "TRACK_NORMAL",
        "tracking_queue_id": queue_id,
    }


def _seed(tmp_path):
    db = tmp_path / "cycle2-opening-atomicity.sqlite3"
    apply_migrations(db)
    connection = sqlite3.connect(db)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys=ON")

    connection.execute(
        "INSERT INTO printer_memory_factory_campaigns("
        "campaign_id,campaign_state,db_mode,db_target_identity,policy_version) "
        "VALUES (?,?,?,?,?)",
        (
            CAMPAIGN_ID,
            "RUNNING",
            "OPERATIONAL_PERSISTENT",
            "db-1",
            "policy-1",
        ),
    )
    connection.execute(
        "INSERT INTO printer_memory_factory_runs("
        "run_id,run_status,window_kind,db_mode,config_hash,config_json,"
        "started_at,created_at,updated_at) VALUES (?,?,?,?,?,?,?,?,?)",
        (
            FACTORY_RUN_ID,
            "RUNNING",
            "WINDOW_15M",
            "OPERATIONAL_PERSISTENT",
            "a" * 64,
            json.dumps(
                {
                    "campaign_id": CAMPAIGN_ID,
                    "campaign_run_id": CAMPAIGN_RUN_ID,
                    "four_token_proof": True,
                    "selective_1h_continuation": True,
                    "standard_four_hour_campaign": True,
                },
                sort_keys=True,
            ),
            NOW.isoformat(),
            NOW.isoformat(),
            NOW.isoformat(),
        ),
    )
    connection.execute(
        "INSERT INTO printer_memory_factory_campaign_runs("
        "run_id,campaign_id,run_ordinal,run_state,authoritative_run_id,"
        "created_at,updated_at) VALUES (?,?,?,?,?,?,?)",
        (
            CAMPAIGN_RUN_ID,
            CAMPAIGN_ID,
            1,
            "RUNNING",
            FACTORY_RUN_ID,
            NOW.isoformat(),
            NOW.isoformat(),
        ),
    )

    queue_ids: dict[int, int] = {}
    for row_id in (3, 4):
        connection.execute(
            "INSERT INTO printer_tokens(id,token_mint,chain) VALUES (?,?,'solana')",
            (row_id, f"mint-{row_id}"),
        )
        connection.execute(
            "INSERT INTO printer_pairs(id,token_id,pair_address,base_token_mint) "
            "VALUES (?,?,?,?)",
            (100 + row_id, row_id, f"pool-{row_id}", f"mint-{row_id}"),
        )
        queue_ids[row_id] = claim_tracking_authority_for_slot_insert(
            connection,
            token_row_id=row_id,
            pair_row_id=100 + row_id,
            tracking_lane="TRACK_NORMAL",
            now=NOW,
        )

    create_cycle_with_two_slots(
        connection,
        campaign_id=CAMPAIGN_ID,
        run_id=CAMPAIGN_RUN_ID,
        cycle_id=CYCLE2_ID,
        cycle_ordinal=2,
        slots=(
            _slot(3, 1, queue_ids[3]),
            _slot(4, 2, queue_ids[4]),
        ),
        now=NOW.isoformat(),
    )
    connection.commit()
    return db, connection, queue_ids


def test_cycle2_opening_rolls_back_slot1_when_slot2_planning_fails(
    tmp_path, monkeypatch
) -> None:
    db, connection, queue_ids = _seed(tmp_path)
    original_precreate = factory._precreate_proof_15m_window

    def fail_second_slot(*args, **kwargs):
        if int(kwargs["slot_ordinal"]) == 2:
            raise RuntimeError("INJECTED_SLOT2_OPENING_FAILURE")
        return original_precreate(*args, **kwargs)

    monkeypatch.setattr(factory, "_precreate_proof_15m_window", fail_second_slot)

    connection.execute("BEGIN IMMEDIATE")
    with pytest.raises(RuntimeError, match="INJECTED_SLOT2_OPENING_FAILURE"):
        factory._plan_opening_jobs(
            connection,
            FACTORY_RUN_ID,
            [_target(3, queue_ids[3]), _target(4, queue_ids[4])],
            NOW,
            cycle_ordinal=2,
            four_token_proof=True,
        )
    connection.rollback()

    # The two-slot first-15m opening set is one atomic planning boundary.
    # A slot-2 failure may not leave slot-1 window/job/step/work residue.
    assert int(
        connection.execute(
            "SELECT COUNT(*) FROM printer_memory_factory_campaign_windows "
            "WHERE campaign_id=? AND run_id=? AND cycle_id=?",
            (CAMPAIGN_ID, CAMPAIGN_RUN_ID, CYCLE2_ID),
        ).fetchone()[0]
    ) == 0
    assert int(
        connection.execute(
            "SELECT COUNT(*) FROM printer_memory_factory_run_steps "
            "WHERE run_id=? AND step_key LIKE 't%_c0002_snapshot_00'",
            (FACTORY_RUN_ID,),
        ).fetchone()[0]
    ) == 0
    assert int(
        connection.execute(
            "SELECT COUNT(*) FROM printer_memory_factory_campaign_scheduler_work "
            "WHERE campaign_id=? AND run_id=? AND cycle_id=?",
            (CAMPAIGN_ID, CAMPAIGN_RUN_ID, CYCLE2_ID),
        ).fetchone()[0]
    ) == 0
    assert int(
        connection.execute(
            "SELECT COUNT(*) FROM printer_scheduler_jobs "
            "WHERE job_name LIKE ?",
            (f"v2_4_{FACTORY_RUN_ID}_t%_c0002_snapshot_00",),
        ).fetchone()[0]
    ) == 0

    # Admission-time tracking claims are outside the opening transaction and
    # remain available for the existing terminal compensation owner.
    assert [
        tuple(row)
        for row in connection.execute(
            "SELECT queue_status,tracking_action FROM printer_tracking_queue "
            "WHERE id IN (?,?) ORDER BY id",
            (queue_ids[3], queue_ids[4]),
        ).fetchall()
    ] == [
        ("QUEUED", "PROMOTE_TO_TRACK_NORMAL"),
        ("QUEUED", "PROMOTE_TO_TRACK_NORMAL"),
    ]
    connection.close()
