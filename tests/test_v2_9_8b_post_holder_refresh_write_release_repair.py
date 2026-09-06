"""Regression for post-holder campaign writes before nested temporal refresh.

Disposable SQLite only. No provider, Printer, authorization, or operational
Scheduler runtime is used.
"""

from __future__ import annotations

import inspect
import sqlite3

import pytest

from printer_v1.operator_cli import authoritative_live_operational_campaign as campaign


class _NestedRefreshWriter:
    def __init__(self, db_path):
        self.db_path = db_path

    def request_temporal_refresh(self, **_kwargs):
        connection = sqlite3.connect(self.db_path, timeout=0.05)
        try:
            connection.execute(
                "INSERT INTO write_probe(owner) VALUES (?)",
                ("refresh",),
            )
            connection.commit()
        finally:
            connection.close()
        return {"status": "REFRESH_ENQUEUED"}


def _database(tmp_path):
    db_path = tmp_path / "post-holder-refresh-lock.sqlite3"
    connection = sqlite3.connect(db_path)
    connection.execute(
        "CREATE TABLE write_probe(id INTEGER PRIMARY KEY, owner TEXT NOT NULL)"
    )
    connection.commit()
    return db_path, connection


def test_nested_refresh_writer_locks_when_campaign_write_is_not_released(tmp_path):
    db_path, connection = _database(tmp_path)
    try:
        connection.execute(
            "INSERT INTO write_probe(owner) VALUES (?)",
            ("campaign",),
        )
        assert connection.in_transaction is True

        with pytest.raises(sqlite3.OperationalError, match="locked"):
            _NestedRefreshWriter(db_path).request_temporal_refresh()

        connection.rollback()
    finally:
        connection.close()


def test_release_boundary_commits_campaign_write_before_nested_refresh_writer(tmp_path):
    db_path, connection = _database(tmp_path)
    try:
        connection.execute(
            "INSERT INTO write_probe(owner) VALUES (?)",
            ("campaign",),
        )
        assert connection.in_transaction is True

        result = campaign._request_temporal_refresh_after_releasing_campaign_write(
            connection,
            _NestedRefreshWriter(db_path),
            reserve_depth=3,
            required_capacity=4,
            universe_state="ALL_REACHABLE_CANDIDATES_EVALUATED",
            source_operations_remaining=1,
            provider_terminal_failure=False,
            now="2026-09-06T09:00:00+00:00",
        )

        assert result == {"status": "REFRESH_ENQUEUED"}
        assert connection.in_transaction is False
        rows = connection.execute(
            "SELECT owner FROM write_probe ORDER BY id"
        ).fetchall()
        assert [row[0] for row in rows] == ["campaign", "refresh"]
    finally:
        connection.close()


def test_freeze_coverage_wait_path_uses_release_boundary_before_refresh():
    source = inspect.getsource(campaign.AuthoritativeLiveOperationalCampaignOwner)
    assert (
        "_request_temporal_refresh_after_releasing_campaign_write(\n"
        "                                connection,\n"
        "                                pre_lifecycle_temporal_refresh_owner,"
    ) in source
