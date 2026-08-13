from __future__ import annotations

import sqlite3

import pytest

from printer_v1.db import apply_migrations
from printer_v1.scheduler.contracts import JOB_PRIORITY_ORDER, JobKind


MIGRATION = "055_pre_admission_discovery_attempt_ownership.sql"


@pytest.fixture()
def connection(tmp_path):
    path = tmp_path / "pre-admission-schema.sqlite3"
    apply_migrations(path)
    connection = sqlite3.connect(path)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys=ON")
    try:
        yield connection
    finally:
        connection.close()


def test_migration_055_adds_only_the_three_dedicated_tables(connection) -> None:
    applied = {
        row[0] for row in connection.execute("SELECT version FROM printer_schema_migrations")
    }
    assert MIGRATION in applied
    tables = {
        row[0]
        for row in connection.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        )
    }
    assert {
        "printer_pre_admission_discovery_attempts",
        "printer_pre_admission_discovery_attempt_items",
        "printer_pre_admission_discovery_attempt_source_links",
    } <= tables
    assert connection.execute("PRAGMA foreign_key_check").fetchall() == []
    assert connection.execute("PRAGMA integrity_check").fetchone()[0] == "ok"


def test_scheduler_kind_is_immediately_below_discovery_refresh() -> None:
    discovery_index = JOB_PRIORITY_ORDER.index(JobKind.DISCOVERY_REFRESH)
    assert (
        JOB_PRIORITY_ORDER[discovery_index + 1]
        is JobKind.PRE_ADMISSION_DISCOVERY_SELECTION
    )
    assert JOB_PRIORITY_ORDER[discovery_index + 2] is JobKind.MARKET_REGIME_CONTEXT


def test_attempt_schema_has_no_preconsumption_cycle_foreign_key(connection) -> None:
    foreign_keys = connection.execute(
        "PRAGMA foreign_key_list(printer_pre_admission_discovery_attempts)"
    ).fetchall()
    referenced = {row[2] for row in foreign_keys}
    assert "printer_memory_factory_campaign_cycles" in referenced
    cycle_fk_rows = [
        row for row in foreign_keys if row[2] == "printer_memory_factory_campaign_cycles"
    ]
    assert {row[3] for row in cycle_fk_rows} == {
        "consumed_cycle_id",
        "campaign_run_id",
        "campaign_id",
    }


def test_attempt_state_and_proposed_ordinal_fail_closed(connection) -> None:
    sql = connection.execute(
        "SELECT sql FROM sqlite_master WHERE type='table' "
        "AND name='printer_pre_admission_discovery_attempts'"
    ).fetchone()[0]
    assert "proposed_cycle_ordinal = 2" in sql
    assert "PAIR_READY" in sql
    assert "CONSUMED" in sql
    assert "consumed_cycle_id IS NOT NULL" in sql
    assert "consumed_cycle_id IS NULL" in sql


def test_items_and_source_links_preserve_exact_pair_and_lineage_shape(connection) -> None:
    item_sql = connection.execute(
        "SELECT sql FROM sqlite_master WHERE type='table' "
        "AND name='printer_pre_admission_discovery_attempt_items'"
    ).fetchone()[0]
    link_sql = connection.execute(
        "SELECT sql FROM sqlite_master WHERE type='table' "
        "AND name='printer_pre_admission_discovery_attempt_source_links'"
    ).fetchone()[0]
    assert "slot_ordinal IN (1, 2)" in item_sql
    assert "json_valid(canonical_evidence_json)" in item_sql
    assert "source_response_id IS NULL OR source_failure_id IS NULL" in link_sql
    assert "source_response_id IS NULL OR source_request_id IS NOT NULL" in link_sql
    assert "source_failure_id IS NULL OR source_request_id IS NOT NULL" in link_sql
