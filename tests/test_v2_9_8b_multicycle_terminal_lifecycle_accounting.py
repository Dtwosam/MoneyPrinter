from __future__ import annotations

from datetime import datetime, timezone
import sqlite3

from printer_v1.db import apply_migrations
from printer_v1.operator_cli.cadence_authority import (
    claim_tracking_authority_for_slot_insert,
)
from printer_v1.operator_cli.campaign_ownership import create_cycle_with_two_slots
from printer_v1.operator_cli.one_command_15m_factory import (
    _terminal_lifecycle_reconciliation_targets,
)
from printer_v1.operator_cli.tracking_lifecycle_reconciliation import (
    reconcile_factory_post_cycle_lifecycle,
)


NOW = datetime(2026, 9, 4, 21, 15, tzinfo=timezone.utc)
CAMPAIGN_ID = "lifecycle-campaign"
CAMPAIGN_RUN_ID = "lifecycle-run"
FACTORY_RUN_ID = "lifecycle-factory"


def _slot(*, cycle_ordinal: int, slot_ordinal: int, row_id: int, queue_id: int):
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


def _seed(tmp_path):
    db = tmp_path / "terminal-lifecycle.sqlite3"
    apply_migrations(db)
    conn = sqlite3.connect(db)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys=ON")
    conn.execute(
        "INSERT INTO printer_memory_factory_campaigns("
        "campaign_id,campaign_state,db_mode,db_target_identity,policy_version) "
        "VALUES (?,?,?,?,?)",
        (
            CAMPAIGN_ID,
            "RUNNING",
            "OPERATIONAL_PERSISTENT",
            "db-lifecycle",
            "policy-lifecycle",
        ),
    )
    conn.execute(
        "INSERT INTO printer_memory_factory_runs("
        "run_id,run_status,window_kind,db_mode,config_hash,config_json,"
        "started_at,created_at,updated_at) VALUES (?,?,?,?,?,?,?,?,?)",
        (
            FACTORY_RUN_ID,
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
    conn.execute(
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

    queues = {}
    for row_id in range(1, 5):
        conn.execute(
            "INSERT INTO printer_tokens(id,token_mint,chain) VALUES (?,?,'solana')",
            (row_id, f"mint-{row_id}"),
        )
        conn.execute(
            "INSERT INTO printer_pairs(id,token_id,pair_address,base_token_mint) "
            "VALUES (?,?,?,?)",
            (100 + row_id, row_id, f"pool-{row_id}", f"mint-{row_id}"),
        )
        lane = "TRACK_FAST" if row_id in (1, 3) else "TRACK_NORMAL"
        queues[row_id] = claim_tracking_authority_for_slot_insert(
            conn,
            token_row_id=row_id,
            pair_row_id=100 + row_id,
            tracking_lane=lane,
            now=NOW,
        )

    for cycle_ordinal, (cycle_id, token_ids) in enumerate(
        (("cycle-1", (1, 2)), ("cycle-2", (3, 4))), start=1
    ):
        create_cycle_with_two_slots(
            conn,
            campaign_id=CAMPAIGN_ID,
            run_id=CAMPAIGN_RUN_ID,
            cycle_id=cycle_id,
            cycle_ordinal=cycle_ordinal,
            slots=tuple(
                _slot(
                    cycle_ordinal=cycle_ordinal,
                    slot_ordinal=slot_ordinal,
                    row_id=row_id,
                    queue_id=queues[row_id],
                )
                for slot_ordinal, row_id in enumerate(token_ids, start=1)
            ),
            now=NOW.isoformat(),
        )
    conn.commit()
    return conn, queues


def test_four_token_terminal_accounting_uses_all_admitted_slots(tmp_path) -> None:
    conn, queues = _seed(tmp_path)
    try:
        historical_cycle1_selection = [
            {
                "token_id": row_id,
                "pair_id": 100 + row_id,
                "token_mint": f"mint-{row_id}",
                "pair_address": f"pool-{row_id}",
                "tracking_lane": "TRACK_FAST" if row_id == 1 else "TRACK_NORMAL",
                "tracking_queue_id": queues[row_id],
            }
            for row_id in (1, 2)
        ]

        targets = _terminal_lifecycle_reconciliation_targets(
            conn,
            selected_tokens=historical_cycle1_selection,
            campaign_id=CAMPAIGN_ID,
            campaign_run_id=CAMPAIGN_RUN_ID,
            four_token_campaign=True,
        )

        # The public/historical discovery selection remains Cycle 1 only, while
        # terminal B.3 accounting uses the durable 4-slot campaign ownership set.
        assert [row["token_id"] for row in historical_cycle1_selection] == [1, 2]
        assert [row["token_id"] for row in targets] == [1, 2, 3, 4]
        assert [row["cycle_id"] for row in targets] == [
            "cycle-1",
            "cycle-1",
            "cycle-2",
            "cycle-2",
        ]
        assert [row["tracking_lane"] for row in targets] == [
            "TRACK_FAST",
            "TRACK_NORMAL",
            "TRACK_FAST",
            "TRACK_NORMAL",
        ]

        outcomes = [
            {
                "token_id": row["token_id"],
                "pair_id": row["pair_id"],
                "terminal_status": "CLEAN",
                "reached_terminal_window": True,
            }
            for row in targets
        ]
        reconciliation = reconcile_factory_post_cycle_lifecycle(
            conn,
            run_id=FACTORY_RUN_ID,
            selected_tokens=targets,
            discovery_results=targets,
            per_token_outcomes=outcomes,
            stop_reason="COMPLETED_CLEAN_OR_DIRTY_RESULTS_REPORTED",
            archive_policy="cooldown",
        )
        conn.commit()

        assert reconciliation["selected_token_count"] == 4
        assert reconciliation["reconciled_token_count"] == 4
        assert reconciliation["exactly_one_disposition_per_selected_token"] is True
        assert [row["token_id"] for row in reconciliation["transitions"]] == [1, 2, 3, 4]
        assert int(
            conn.execute(
                "SELECT COUNT(*) FROM printer_token_lifecycle_events "
                "WHERE priority_reason='factory_post_cycle_reconciliation'"
            ).fetchone()[0]
        ) == 4
        assert [
            tuple(row)
            for row in conn.execute(
                "SELECT s.cycle_id,s.slot_ordinal,q.queue_status "
                "FROM printer_memory_factory_campaign_token_slots AS s "
                "JOIN printer_tracking_queue AS q ON q.id=s.tracking_queue_id "
                "WHERE s.campaign_id=? AND s.run_id=? "
                "ORDER BY s.cycle_id,s.slot_ordinal",
                (CAMPAIGN_ID, CAMPAIGN_RUN_ID),
            ).fetchall()
        ] == [
            ("cycle-1", 1, "COOLDOWN"),
            ("cycle-1", 2, "COOLDOWN"),
            ("cycle-2", 1, "COOLDOWN"),
            ("cycle-2", 2, "COOLDOWN"),
        ]
    finally:
        conn.close()


def test_non_four_token_terminal_accounting_preserves_selected_surface(tmp_path) -> None:
    conn, queues = _seed(tmp_path)
    try:
        selected = [
            {
                "token_id": 1,
                "pair_id": 101,
                "tracking_lane": "TRACK_FAST",
                "tracking_queue_id": queues[1],
            }
        ]
        assert _terminal_lifecycle_reconciliation_targets(
            conn,
            selected_tokens=selected,
            campaign_id=None,
            campaign_run_id=None,
            four_token_campaign=False,
        ) == selected
    finally:
        conn.close()
