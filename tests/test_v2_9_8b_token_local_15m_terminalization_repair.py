from __future__ import annotations

import inspect
import sqlite3

import pytest

from printer_v1.operator_cli import one_command_15m_factory as factory


def _db() -> sqlite3.Connection:
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.executescript(
        """
        CREATE TABLE printer_memory_factory_campaign_windows(
            window_id TEXT PRIMARY KEY,
            campaign_id TEXT NOT NULL,
            run_id TEXT NOT NULL,
            cycle_id TEXT NOT NULL,
            token_slot_id TEXT NOT NULL,
            token_row_id INTEGER NOT NULL,
            pair_row_id INTEGER NOT NULL,
            window_kind TEXT NOT NULL,
            window_state TEXT NOT NULL,
            first_terminal_cause TEXT,
            terminal_at TEXT,
            updated_at TEXT
        );
        CREATE TABLE printer_memory_factory_campaign_token_slots(
            token_slot_id TEXT PRIMARY KEY,
            campaign_id TEXT NOT NULL,
            run_id TEXT NOT NULL,
            cycle_id TEXT NOT NULL,
            token_row_id INTEGER NOT NULL,
            pair_row_id INTEGER NOT NULL,
            token_state TEXT NOT NULL,
            first_terminal_cause TEXT,
            terminal_at TEXT,
            updated_at TEXT
        );
        """
    )
    for slot, token, pair in (("slot-failed", 11, 21), ("slot-peer", 12, 22)):
        conn.execute(
            "INSERT INTO printer_memory_factory_campaign_token_slots VALUES (?,?,?,?,?,?,?,?,?,?)",
            (slot, "campaign", "run", "cycle-1", token, pair, "WINDOW_15M_ACTIVE", None, None, None),
        )
        conn.execute(
            "INSERT INTO printer_memory_factory_campaign_windows VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
            (f"window-{slot}", "campaign", "run", "cycle-1", slot, token, pair,
             "WINDOW_15M", "COLLECTING", None, None, None),
        )
    conn.commit()
    return conn


def test_owned_15m_token_failure_terminalizes_only_exact_slot(monkeypatch: pytest.MonkeyPatch) -> None:
    conn = _db()

    def owned_window(_conn, *, scheduler_job_id, expected_stage, expected_window_kind):
        assert scheduler_job_id == 101
        assert expected_stage == "WINDOW_15M"
        assert expected_window_kind == "WINDOW_15M"
        return _conn.execute(
            "SELECT * FROM printer_memory_factory_campaign_windows WHERE window_id='window-slot-failed'"
        ).fetchone()

    monkeypatch.setattr(factory, "_owned_lifecycle_window_for_job", owned_window)
    cause = "dexscreener_transport_failure+geckoterminal_transport_failure"
    result = factory._terminalize_owned_15m_token_failure(
        conn, scheduler_job_id=101, terminal_cause=cause
    )

    failed_window = conn.execute(
        "SELECT window_state,first_terminal_cause FROM printer_memory_factory_campaign_windows WHERE window_id='window-slot-failed'"
    ).fetchone()
    failed_slot = conn.execute(
        "SELECT token_state,first_terminal_cause FROM printer_memory_factory_campaign_token_slots WHERE token_slot_id='slot-failed'"
    ).fetchone()
    peer_window = conn.execute(
        "SELECT window_state,first_terminal_cause FROM printer_memory_factory_campaign_windows WHERE window_id='window-slot-peer'"
    ).fetchone()
    peer_slot = conn.execute(
        "SELECT token_state,first_terminal_cause FROM printer_memory_factory_campaign_token_slots WHERE token_slot_id='slot-peer'"
    ).fetchone()

    assert result == "BLOCKED"
    assert tuple(failed_window) == ("BLOCKED", cause)
    assert tuple(failed_slot) == ("FAILED", cause)
    assert tuple(peer_window) == ("COLLECTING", None)
    assert tuple(peer_slot) == ("WINDOW_15M_ACTIVE", None)


def test_token_local_failure_paths_call_owned_15m_terminalizer() -> None:
    source = inspect.getsource(factory.run_one_command_15m_factory)
    assert source.count("_terminalize_owned_15m_token_failure(") >= 2
    assert "incomplete cycle cannot consume a completion stop cause" not in source
