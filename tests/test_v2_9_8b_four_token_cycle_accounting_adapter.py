from __future__ import annotations

import json
import sqlite3

import pytest

from printer_v1.operator_cli import four_token_factory_adapter as adapter
from printer_v1.operator_cli.one_command_15m_factory import _plan_opening_jobs
from tests.test_v2_9_8b_callback_consume_materialize_integration import (
    BINDING,
    NOW,
    _prepare_database,
)


def _planned_cycle(tmp_path):
    path, _request_id, _response_id = _prepare_database(tmp_path)
    connection = sqlite3.connect(path)
    connection.row_factory = sqlite3.Row
    connection.execute(
        "UPDATE printer_memory_factory_runs SET config_json=? WHERE run_id=?",
        (json.dumps({
            "four_token_proof": True,
            "campaign_id": BINDING.campaign_id,
            "campaign_run_id": BINDING.campaign_run_id,
            "configuration_id": BINDING.configuration_id,
        }, sort_keys=True), BINDING.authoritative_factory_run_id),
    )
    targets = [dict(row) for row in connection.execute(
        "SELECT token_row_id AS token_id,pair_row_id AS pair_id,"
        "mint_identity AS token_mint,pair_identity AS pair_address,"
        "'TRACK_NORMAL' AS tracking_lane "
        "FROM printer_memory_factory_campaign_token_slots "
        "WHERE cycle_id='cycle-1' ORDER BY slot_ordinal"
    ).fetchall()]
    _plan_opening_jobs(
        connection,
        BINDING.authoritative_factory_run_id,
        targets,
        NOW,
        cycle_ordinal=1,
        four_token_proof=True,
    )
    step = connection.execute(
        "SELECT step_key FROM printer_memory_factory_run_steps "
        "WHERE run_id=? ORDER BY id LIMIT 1",
        (BINDING.authoritative_factory_run_id,),
    ).fetchone()
    request_id = int(connection.execute(
        "INSERT INTO printer_source_requests("
        "source_name,request_kind,requested_at,request_key,source_status,"
        "data_quality_label) VALUES "
        "('dexscreener','pair',?,?, 'COMPLETE','CLEAN_DATA')",
        (NOW.isoformat(), f"{BINDING.authoritative_factory_run_id}:{step[0]}:proof"),
    ).lastrowid)
    connection.execute(
        "INSERT INTO printer_source_responses("
        "source_request_id,source_name,received_at,source_status,data_quality_label) "
        "VALUES (?,'dexscreener',?,'COMPLETE','CLEAN_DATA')",
        (request_id, NOW.isoformat()),
    )
    connection.commit()
    return connection, request_id


def _build(connection):
    return adapter.build_four_token_cycle_accounting_package(
        connection,
        campaign_id=BINDING.campaign_id,
        campaign_run_id=BINDING.campaign_run_id,
        factory_run_id=BINDING.authoritative_factory_run_id,
        cycle_id="cycle-1",
    )


def test_opening_only_cycle_cannot_project_structurally_safe_through_4h(
    tmp_path,
) -> None:
    connection, _request_id = _planned_cycle(tmp_path)
    writes_before = connection.total_changes
    with pytest.raises(
        adapter.FourTokenFactoryAdapterError,
        match="canonical lifecycle accounting is incomplete",
    ):
        _build(connection)
    assert connection.total_changes == writes_before
    connection.close()


def test_cycle_accounting_projects_exact_durable_scheduler_and_source_ownership(
    tmp_path,
) -> None:
    connection, request_id = _planned_cycle(tmp_path)
    writes_before = connection.total_changes
    package = _build(connection)
    assert connection.total_changes == writes_before
    assert package["cycle_id"] == "cycle-1"
    assert package["cycle_ordinal"] == 1
    assert package["factory_run_id"] == BINDING.authoritative_factory_run_id
    assert package["structurally_safe"] is True
    assert len(package["selected_targets"]) == 2
    assert package["memory_quality"] == ("NO_PROMOTION", "NO_PROMOTION")
    accounting = package["accounting_package"]
    assert accounting["expected_token_capacity"] == 2
    assert len(accounting["factory_step_ids"]) == 2
    assert accounting["scheduler_jobs"] == 2
    assert accounting["source_requests"] == 1
    assert accounting["source_request_ids"] == (request_id,)
    assert len(accounting["scheduler_job_ids"]) == 2
    assert len(accounting["scheduler_work_ids"]) == 2
    connection.close()


def test_cycle_accounting_fails_closed_on_missing_or_extra_ownership(tmp_path) -> None:
    connection, _ = _planned_cycle(tmp_path)
    connection.execute(
        "DELETE FROM printer_memory_factory_campaign_scheduler_work "
        "WHERE scheduler_work_id=("
        "SELECT scheduler_work_id FROM printer_memory_factory_campaign_scheduler_work "
        "ORDER BY scheduler_work_id LIMIT 1)"
    )
    with pytest.raises(adapter.FourTokenFactoryAdapterError, match="ownership"):
        _build(connection)

    connection.rollback()
    connection.execute(
        "INSERT INTO printer_source_requests("
        "source_name,request_kind,requested_at,request_key,source_status,"
        "data_quality_label) VALUES "
        "('dexscreener','pair',?,?, 'COMPLETE','CLEAN_DATA')",
        (NOW.isoformat(), f"{BINDING.authoritative_factory_run_id}:unowned:proof"),
    )
    connection.commit()
    with pytest.raises(adapter.FourTokenFactoryAdapterError, match="ownership"):
        _build(connection)
    connection.close()
