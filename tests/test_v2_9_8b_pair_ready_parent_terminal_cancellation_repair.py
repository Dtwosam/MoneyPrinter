from __future__ import annotations

from datetime import datetime, timezone
import json
import sqlite3

import pytest

from printer_v1.db import apply_migrations
from printer_v1.operator_cli.pre_admission_discovery_attempt import (
    PreAdmissionAttemptError,
    PreAdmissionAttemptState,
    cancel_pair_ready_pre_admission_attempt_for_terminal_parent,
    terminalize_pre_admission_attempt,
)
from printer_v1.operator_cli.unified_terminal_closure import reconcile_campaign_terminal


NOW = datetime(2026, 8, 20, 12, 0, tzinfo=timezone.utc)
CANCEL_NOW = datetime(2026, 8, 20, 12, 5, tzinfo=timezone.utc)
CAUSE = "OPERATIONAL_CAMPAIGN_FAILED:FourTokenFactoryAdapterError"


def _seed_graph(connection: sqlite3.Connection) -> None:
    connection.execute(
        "INSERT INTO printer_memory_factory_campaigns("
        "campaign_id,campaign_state,db_mode,db_target_identity,policy_version,"
        "created_at,updated_at) VALUES (?,?,?,?,?,?,?)",
        (
            "campaign-1", "RUNNING", "OPERATIONAL_PERSISTENT", "db-1", "policy-1",
            NOW.isoformat(), NOW.isoformat(),
        ),
    )
    connection.execute(
        "INSERT INTO printer_memory_factory_campaign_configurations("
        "configuration_id,campaign_id,configuration_hash,configuration_json,"
        "launch_provenance_json,created_at) VALUES (?,?,?,?,?,?)",
        ("configuration-1", "campaign-1", "a" * 64, "{}", "{}", NOW.isoformat()),
    )
    connection.execute(
        "INSERT INTO printer_memory_factory_runs("
        "run_id,run_status,window_kind,db_mode,config_hash,config_json,started_at,"
        "created_at,updated_at) VALUES (?,?,?,?,?,?,?,?,?)",
        (
            "factory-1", "RUNNING", "WINDOW_15M", "OPERATIONAL_PERSISTENT",
            "a" * 64, "{}", NOW.isoformat(), NOW.isoformat(), NOW.isoformat(),
        ),
    )
    connection.execute(
        "INSERT INTO printer_memory_factory_campaign_runs("
        "run_id,campaign_id,run_ordinal,run_state,authoritative_run_id,created_at,updated_at) "
        "VALUES (?,?,?,?,?,?,?)",
        (
            "campaign-run-1", "campaign-1", 1, "RUNNING", "factory-1",
            NOW.isoformat(), NOW.isoformat(),
        ),
    )
    connection.execute(
        "INSERT INTO printer_memory_factory_campaign_cycles("
        "cycle_id,campaign_id,run_id,cycle_ordinal,cycle_state,created_at,updated_at) "
        "VALUES (?,?,?,?,?,?,?)",
        (
            "cycle-1", "campaign-1", "campaign-run-1", 1, "PLANNED",
            NOW.isoformat(), NOW.isoformat(),
        ),
    )
    for row_id in (3, 4):
        connection.execute(
            "INSERT INTO printer_tokens(id,token_mint,chain) VALUES (?,?, 'solana')",
            (row_id, f"mint-{row_id}"),
        )
        connection.execute(
            "INSERT INTO printer_pairs(id,token_id,pair_address) VALUES (?,?,?)",
            (100 + row_id, row_id, f"pair-{row_id}"),
        )
    cursor = connection.execute(
        "INSERT INTO printer_scheduler_jobs("
        "job_name,job_kind,target_table,priority,status,scheduled_for,finished_at) "
        "VALUES (?,?,?,?,?,?,?)",
        (
            "pre-admission:attempt-pair-ready",
            "PRE_ADMISSION_DISCOVERY_SELECTION",
            "printer_pre_admission_discovery_attempts",
            13,
            "SUCCEEDED",
            NOW.isoformat(),
            NOW.isoformat(),
        ),
    )
    job_id = int(cursor.lastrowid)
    connection.execute(
        """INSERT INTO printer_pre_admission_discovery_attempts(
               attempt_id,campaign_id,campaign_run_id,configuration_id,
               authoritative_factory_run_id,proposed_cycle_ordinal,proposed_cycle_id,
               scheduler_job_id,cycle_cutoff,evaluated_at,selection_seed_identity,
               attempt_state,first_terminal_cause,terminal_at,created_at,updated_at
           ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
        (
            "attempt-pair-ready", "campaign-1", "campaign-run-1", "configuration-1",
            "factory-1", 2, "cycle-2", job_id, NOW.isoformat(), NOW.isoformat(),
            "seed-frozen-pair", "PAIR_READY", "EXACT_PAIR_FROZEN",
            NOW.isoformat(), NOW.isoformat(), NOW.isoformat(),
        ),
    )
    for slot in (1, 2):
        row_id = slot + 2
        connection.execute(
            """INSERT INTO printer_pre_admission_discovery_attempt_items(
                   attempt_id,slot_ordinal,token_identity,token_row_id,mint_identity,
                   pair_identity,pair_row_id,lifecycle_identity,canonical_market_identity,
                   canonical_pool_identity,canonical_evidence_json,
                   canonical_evidence_hash,evidence_version,observed_at,created_at
               ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (
                "attempt-pair-ready", slot, f"token-{row_id}", row_id, f"mint-{row_id}",
                f"pair-{row_id}", 100 + row_id, f"lifecycle-{row_id}",
                f"solana-mainnet:pumpswap:pair-{row_id}", f"pair-{row_id}",
                json.dumps({"quality": "exact"}, sort_keys=True),
                str(row_id) * 64, "v1", NOW.isoformat(), NOW.isoformat(),
            ),
        )
    connection.commit()


@pytest.fixture()
def db_path(tmp_path):
    path = tmp_path / "pair-ready-parent-terminal.sqlite3"
    apply_migrations(path)
    connection = sqlite3.connect(path)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys=ON")
    try:
        _seed_graph(connection)
    finally:
        connection.close()
    return path


def _open(db_path):
    connection = sqlite3.connect(db_path)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys=ON")
    return connection


def _snapshot(connection: sqlite3.Connection):
    row = connection.execute(
        "SELECT * FROM printer_pre_admission_discovery_attempts "
        "WHERE attempt_id='attempt-pair-ready'"
    ).fetchone()
    items = connection.execute(
        "SELECT * FROM printer_pre_admission_discovery_attempt_items "
        "WHERE attempt_id='attempt-pair-ready' ORDER BY slot_ordinal"
    ).fetchall()
    return (
        {key: row[key] for key in row.keys()},
        [{key: item[key] for key in item.keys()} for item in items],
    )


def test_parent_terminal_reconcile_cancels_pair_ready_without_rewriting_frozen_truth(db_path) -> None:
    connection = _open(db_path)
    try:
        before_row, before_items = _snapshot(connection)
    finally:
        connection.close()

    result = reconcile_campaign_terminal(
        db_path,
        campaign_id="campaign-1",
        run_id="campaign-run-1",
        cycle_id="cycle-1",
        terminal_cause=CAUSE,
        run_status="FAILED",
        factory_run_id="factory-1",
        lifecycle_started=False,
        now=CANCEL_NOW.isoformat(),
    )

    connection = _open(db_path)
    try:
        after_row, after_items = _snapshot(connection)
        assert after_row["attempt_state"] == "CANCELLED"
        assert after_row["first_terminal_cause"] == "EXACT_PAIR_FROZEN"
        assert after_row["terminal_at"] == before_row["terminal_at"]
        assert after_row["consumed_cycle_id"] is None
        assert after_row["consumed_at"] is None
        assert after_row["updated_at"] == CANCEL_NOW.isoformat()
        assert after_items == before_items
        assert connection.execute(
            "SELECT COUNT(*) FROM printer_memory_factory_campaign_cycles "
            "WHERE campaign_id='campaign-1' AND cycle_ordinal=2"
        ).fetchone()[0] == 0
        assert [entry["prior_state"] for entry in result["pre_admission_attempts"]] == [
            "PAIR_READY"
        ]
    finally:
        connection.close()

    second = reconcile_campaign_terminal(
        db_path,
        campaign_id="campaign-1",
        run_id="campaign-run-1",
        cycle_id="cycle-1",
        terminal_cause="SECOND_CAUSE_MUST_NOT_REWRITE",
        run_status="FAILED",
        factory_run_id="factory-1",
        lifecycle_started=False,
        now=datetime(2026, 8, 20, 12, 10, tzinfo=timezone.utc).isoformat(),
    )
    assert second["pre_admission_attempts"] == []
    connection = _open(db_path)
    try:
        final_row, final_items = _snapshot(connection)
        assert final_row == after_row
        assert final_items == before_items
    finally:
        connection.close()


def test_generic_terminalizer_still_cannot_cancel_pair_ready(db_path) -> None:
    connection = _open(db_path)
    try:
        with pytest.raises(PreAdmissionAttemptError, match="INVALID_ATTEMPT_TRANSITION"):
            terminalize_pre_admission_attempt(
                connection,
                attempt_id="attempt-pair-ready",
                state=PreAdmissionAttemptState.CANCELLED,
                cause=CAUSE,
                now=CANCEL_NOW,
            )
    finally:
        connection.close()


def test_parent_terminal_pair_ready_owner_fails_closed_on_ownership_mismatch(db_path) -> None:
    connection = _open(db_path)
    try:
        before = _snapshot(connection)
        with pytest.raises(
            PreAdmissionAttemptError, match="PARENT_TERMINAL_OWNERSHIP_MISMATCH"
        ):
            cancel_pair_ready_pre_admission_attempt_for_terminal_parent(
                connection,
                attempt_id="attempt-pair-ready",
                campaign_id="wrong-campaign",
                campaign_run_id="campaign-run-1",
                authoritative_factory_run_id="factory-1",
                now=CANCEL_NOW,
            )
        assert _snapshot(connection) == before
    finally:
        connection.close()
