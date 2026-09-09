"""V2-9.8B report/operator-review read-only boundary regression.

Disposable SQLite only. Report and review surfaces may inspect stored historical
memory/paper evidence, but their database handles must be physically read-only
and must not fall back to writable access while downstream capabilities remain
locked.
"""

from __future__ import annotations

import argparse
import sqlite3

import pytest

from printer_v1.contracts import capability_locks
from printer_v1.db import apply_migrations
from printer_v1.operator_cli import commands
from printer_v1.operator_cli import e2u_15m_cycle_closeout_report as e2u
from printer_v1.operator_cli import e2w_5m_linkage_report as e2w
from printer_v1.operator_cli import lane_v_clean_memory_retrieval_report as lane_v


LOCKED_TABLES = (
    "printer_memory_retrieval_queries",
    "printer_memory_retrieval_matches",
    "printer_paper_decisions",
    "printer_paper_positions",
    "printer_paper_trade_events",
    "printer_paper_trade_audits",
    "printer_paper_audit_reports",
)


@pytest.fixture
def db_path(tmp_path):
    path = tmp_path / "readonly-report.sqlite3"
    apply_migrations(path)
    return path


def _count(path, table: str) -> int:
    connection = sqlite3.connect(path)
    try:
        return int(connection.execute(f'SELECT COUNT(*) FROM "{table}"').fetchone()[0])
    finally:
        connection.close()


@pytest.mark.parametrize(
    "opener",
    (
        commands._open_report_read_only_connection,
        e2u._connect_ro,
        e2w._connect_ro,
        lane_v._connect_ro,
    ),
)
def test_report_connections_are_physically_read_only(db_path, opener) -> None:
    connection = opener(db_path)
    try:
        assert int(connection.execute("PRAGMA query_only").fetchone()[0]) == 1
        with pytest.raises(sqlite3.OperationalError):
            connection.execute(
                "INSERT INTO printer_tokens (token_mint, chain) "
                "VALUES ('must-not-write', 'solana')"
            )
    finally:
        connection.close()

    assert _count(db_path, "printer_tokens") == 0


@pytest.mark.parametrize(
    ("module", "opener_name"),
    (
        (commands, "_open_report_read_only_connection"),
        (e2u, "_connect_ro"),
        (e2w, "_connect_ro"),
        (lane_v, "_connect_ro"),
    ),
)
def test_read_only_open_failure_never_retries_as_writable(
    db_path, monkeypatch, module, opener_name
) -> None:
    calls: list[tuple[tuple[object, ...], dict[str, object]]] = []

    def fail_connect(*args, **kwargs):
        calls.append((args, kwargs))
        raise sqlite3.OperationalError("read-only open failed")

    monkeypatch.setattr(module.sqlite3, "connect", fail_connect)

    with pytest.raises(sqlite3.OperationalError, match="read-only open failed"):
        getattr(module, opener_name)(db_path)

    assert len(calls) == 1
    args, kwargs = calls[0]
    assert "mode=ro" in str(args[0])
    assert kwargs.get("uri") is True


def _report_args(db_path, *, paper_decision_id: int | None = None) -> argparse.Namespace:
    values = {
        "db_path": str(db_path),
        "project_root": None,
        "format": "json",
        "no_color": True,
        "operator_approved": True,
        "chain": "solana",
    }
    if paper_decision_id is not None:
        values["paper_decision_id"] = paper_decision_id
    return argparse.Namespace(**values)


@pytest.mark.parametrize(
    ("builder", "args"),
    (
        (
            commands.build_clean_memory_retrieval_report_once_payload,
            lambda path: _report_args(path),
        ),
        (
            commands.build_wait_avoid_no_action_readiness_payload,
            lambda path: _report_args(path),
        ),
        (
            commands.build_conservative_paper_decision_audit_review_payload,
            lambda path: _report_args(path, paper_decision_id=1),
        ),
    ),
)
def test_post_rc_report_review_builders_use_strict_shared_opener(
    db_path, monkeypatch, builder, args
) -> None:
    def blocked_open(_path):
        raise RuntimeError("strict-read-only-opener-used")

    monkeypatch.setattr(
        commands,
        "_open_report_read_only_connection",
        blocked_open,
    )

    with pytest.raises(RuntimeError, match="strict-read-only-opener-used"):
        builder(args(db_path))


def test_lane_v_builder_uses_strict_opener(db_path, monkeypatch) -> None:
    def blocked_open(_path):
        raise RuntimeError("strict-lane-v-opener-used")

    monkeypatch.setattr(lane_v, "_connect_ro", blocked_open)

    with pytest.raises(RuntimeError, match="strict-lane-v-opener-used"):
        lane_v.build_clean_memory_retrieval_report(db_path)


def test_report_only_surfaces_leave_locked_capability_tables_unchanged(db_path) -> None:
    assert capability_locks.RETRIEVAL_ACTIVATION_ENABLED is False
    assert capability_locks.PAPER_DECISIONS_ENABLED is False
    assert capability_locks.PAPER_POSITIONS_ENABLED is False
    assert capability_locks.PAPER_AUDITS_ENABLED is False
    assert capability_locks.PAPER_PNL_ENABLED is False

    before = {table: _count(db_path, table) for table in LOCKED_TABLES}

    lane7 = commands.build_clean_memory_retrieval_report_once_payload(
        _report_args(db_path)
    )
    lane8a = commands.build_wait_avoid_no_action_readiness_payload(
        _report_args(db_path)
    )
    lane8c = commands.build_conservative_paper_decision_audit_review_payload(
        _report_args(db_path, paper_decision_id=1)
    )
    lane_v_report = lane_v.build_clean_memory_retrieval_report(db_path)

    after = {table: _count(db_path, table) for table in LOCKED_TABLES}
    assert after == before

    assert lane7["report_only"] is True
    assert lane7["retrieval_matches_created"] == 0
    assert lane7["buy_unlock"] is False
    assert lane7["pnl_unlock"] is False

    assert lane8a["report_only"] is True
    assert lane8a["paper_decisions_created"] == 0
    assert lane8a["buy_unlock"] is False
    assert lane8a["position_unlock"] is False
    assert lane8a["pnl_unlock"] is False

    assert lane8c["report_only"] is True
    assert lane8c["review_rows_created"] == 0
    assert lane8c["buy_unlock"] is False
    assert lane8c["position_unlock"] is False
    assert lane8c["pnl_unlock"] is False

    assert lane_v_report["retrieval_activation"] is False
    assert lane_v_report["paper_decisions_created"] == 0
    assert lane_v_report["positions_created"] == 0
    assert lane_v_report["pnl_created"] == 0
