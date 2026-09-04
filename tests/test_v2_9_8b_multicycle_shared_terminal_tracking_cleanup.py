from __future__ import annotations

from datetime import datetime, timezone
import sqlite3

from printer_v1.db import apply_migrations
from printer_v1.operator_cli.cadence_authority import (
    claim_tracking_authority_for_slot_insert,
)
from printer_v1.operator_cli.campaign_ownership import (
    create_cycle_with_two_slots,
    transition_state,
)
from printer_v1.operator_cli.unified_terminal_closure import (
    reconcile_campaign_terminal,
)


NOW = datetime(2026, 9, 4, 19, 55, tzinfo=timezone.utc)
CAUSE = "CYCLE2_OPENING_PLAN_FAILED"


def _slot(
    *,
    cycle_ordinal: int,
    slot_ordinal: int,
    row_id: int,
    queue_id: int,
) -> dict[str, object]:
    return {
        "token_slot_id": f"t{slot_ordinal}_c{cycle_ordinal:04d}_slot",
        "slot_ordinal": slot_ordinal,
        "token_identity": f"solana-mainnet:mint-{row_id}",
        "token_row_id": row_id,
        "mint_identity": f"mint-{row_id}",
        "pair_identity": f"pool-{row_id}",
        "pair_row_id": 100 + row_id,
        "lifecycle_identity": "PUMPSWAP_GRADUATED_CONFIRMED",
        "tracking_queue_id": queue_id,
        "replacement_predecessor_slot_id": None,
    }


def test_shared_terminal_reconciles_tracking_for_every_admitted_cycle(tmp_path) -> None:
    db = tmp_path / "multicycle-terminal.sqlite3"
    apply_migrations(db)
    connection = sqlite3.connect(db)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys=ON")

    connection.execute(
        "INSERT INTO printer_memory_factory_campaigns("
        "campaign_id,campaign_state,db_mode,db_target_identity,policy_version) "
        "VALUES ('campaign-1','RUNNING','OPERATIONAL_PERSISTENT','db-1','policy-1')"
    )
    connection.execute(
        "INSERT INTO printer_memory_factory_runs("
        "run_id,run_status,window_kind,db_mode,config_hash,config_json,started_at,"
        "created_at,updated_at) VALUES (?,?,?,?,?,?,?,?,?)",
        (
            "factory-1",
            "RUNNING",
            "WINDOW_15M",
            "OPERATIONAL_PERSISTENT",
            "a" * 64,
            "{}",
            NOW.isoformat(),
            NOW.isoformat(),
            NOW.isoformat(),
        ),
    )
    connection.execute(
        "INSERT INTO printer_memory_factory_campaign_runs("
        "run_id,campaign_id,run_ordinal,run_state,authoritative_run_id,created_at,"
        "updated_at) VALUES (?,?,?,?,?,?,?)",
        (
            "run-1",
            "campaign-1",
            1,
            "RUNNING",
            "factory-1",
            NOW.isoformat(),
            NOW.isoformat(),
        ),
    )

    queues: dict[int, int] = {}
    for row_id in range(1, 5):
        connection.execute(
            "INSERT INTO printer_tokens(id,token_mint,chain) VALUES (?,?,'solana')",
            (row_id, f"mint-{row_id}"),
        )
        connection.execute(
            "INSERT INTO printer_pairs(id,token_id,pair_address,base_token_mint) "
            "VALUES (?,?,?,?)",
            (100 + row_id, row_id, f"pool-{row_id}", f"mint-{row_id}"),
        )
        queues[row_id] = claim_tracking_authority_for_slot_insert(
            connection,
            token_row_id=row_id,
            pair_row_id=100 + row_id,
            tracking_lane="TRACK_NORMAL",
            now=NOW,
        )

    create_cycle_with_two_slots(
        connection,
        campaign_id="campaign-1",
        run_id="run-1",
        cycle_id="cycle-1",
        cycle_ordinal=1,
        slots=tuple(
            _slot(
                cycle_ordinal=1,
                slot_ordinal=ordinal,
                row_id=row_id,
                queue_id=queues[row_id],
            )
            for ordinal, row_id in enumerate((1, 2), start=1)
        ),
        now=NOW.isoformat(),
    )
    create_cycle_with_two_slots(
        connection,
        campaign_id="campaign-1",
        run_id="run-1",
        cycle_id="cycle-2",
        cycle_ordinal=2,
        slots=tuple(
            _slot(
                cycle_ordinal=2,
                slot_ordinal=ordinal,
                row_id=row_id,
                queue_id=queues[row_id],
            )
            for ordinal, row_id in enumerate((3, 4), start=1)
        ),
        now=NOW.isoformat(),
    )
    connection.commit()

    # Production Phase A has already terminalized Cycle 2 after an opening-plan
    # failure. No WINDOW_15M work survived the failed opening transaction, but
    # insert-time tracking authority is durable and still QUEUED.
    for slot_id in ("t1_c0002_slot", "t2_c0002_slot"):
        transition_state(
            connection,
            record_kind="token_slot",
            identity=slot_id,
            expected_state="SELECTED",
            new_state="MANUAL_REVIEW",
            terminal_cause=CAUSE,
            now=NOW.isoformat(),
        )
    transition_state(
        connection,
        record_kind="cycle",
        identity="cycle-2",
        expected_state="PLANNED",
        new_state="TERMINAL_FAILED",
        terminal_cause=CAUSE,
        now=NOW.isoformat(),
    )

    before_cycle2 = [
        tuple(row)
        for row in connection.execute(
            "SELECT q.queue_status,q.tracking_action "
            "FROM printer_memory_factory_campaign_token_slots AS s "
            "JOIN printer_tracking_queue AS q ON q.id=s.tracking_queue_id "
            "WHERE s.cycle_id='cycle-2' ORDER BY s.slot_ordinal"
        ).fetchall()
    ]
    assert before_cycle2 == [
        ("QUEUED", "PROMOTE_TO_TRACK_NORMAL"),
        ("QUEUED", "PROMOTE_TO_TRACK_NORMAL"),
    ]
    connection.close()

    report = reconcile_campaign_terminal(
        db,
        campaign_id="campaign-1",
        run_id="run-1",
        cycle_id="cycle-1",
        terminal_cause=CAUSE,
        run_status="FAILED",
        factory_run_id="factory-1",
        lifecycle_started=True,
        now=NOW.isoformat(),
    )

    connection = sqlite3.connect(db)
    connection.row_factory = sqlite3.Row
    try:
        all_queues = [
            tuple(row)
            for row in connection.execute(
                "SELECT s.cycle_id,s.slot_ordinal,q.queue_status,q.tracking_action "
                "FROM printer_memory_factory_campaign_token_slots AS s "
                "JOIN printer_tracking_queue AS q ON q.id=s.tracking_queue_id "
                "WHERE s.campaign_id='campaign-1' AND s.run_id='run-1' "
                "ORDER BY s.cycle_id,s.slot_ordinal"
            ).fetchall()
        ]
        cycle2_slots = [
            tuple(row)
            for row in connection.execute(
                "SELECT token_state,first_terminal_cause "
                "FROM printer_memory_factory_campaign_token_slots "
                "WHERE cycle_id='cycle-2' ORDER BY slot_ordinal"
            ).fetchall()
        ]
    finally:
        connection.close()

    assert all_queues == [
        ("cycle-1", 1, "SKIPPED", "MANUAL_REVIEW"),
        ("cycle-1", 2, "SKIPPED", "MANUAL_REVIEW"),
        ("cycle-2", 1, "SKIPPED", "MANUAL_REVIEW"),
        ("cycle-2", 2, "SKIPPED", "MANUAL_REVIEW"),
    ]
    assert cycle2_slots == [
        ("MANUAL_REVIEW", CAUSE),
        ("MANUAL_REVIEW", CAUSE),
    ]
    assert len(report["pre_lifecycle_dispositions"]) == 4
    assert report["reconciled"] is True
