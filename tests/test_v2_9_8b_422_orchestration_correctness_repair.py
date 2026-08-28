"""Focused RED/GREEN proof for the V2-9.8B 4/2/2 orchestration repair.

Disposable in-memory SQLite only. No provider/RPC work and no authoritative DB.
"""

from __future__ import annotations

import inspect
import sqlite3
import unittest

from printer_v1.operator_cli import one_command_15m_factory as factory
from printer_v1.operator_cli import operational_selective_1h as selective


class Window1hPreE2zBindingRepairTests(unittest.TestCase):
    def _connection(self) -> sqlite3.Connection:
        connection = sqlite3.connect(":memory:")
        connection.row_factory = sqlite3.Row
        connection.executescript(
            """
            CREATE TABLE printer_memory_windows (
                id INTEGER PRIMARY KEY,
                token_id INTEGER NOT NULL,
                pair_id INTEGER NOT NULL,
                window_kind TEXT NOT NULL
            );
            CREATE TABLE printer_memory_factory_campaign_windows (
                window_id TEXT PRIMARY KEY,
                campaign_id TEXT NOT NULL,
                run_id TEXT NOT NULL,
                cycle_id TEXT NOT NULL,
                token_slot_id TEXT NOT NULL,
                token_row_id INTEGER NOT NULL,
                pair_row_id INTEGER NOT NULL,
                window_kind TEXT NOT NULL,
                window_state TEXT NOT NULL,
                memory_window_row_id INTEGER,
                first_terminal_cause TEXT,
                terminal_at TEXT,
                updated_at TEXT
            );
            INSERT INTO printer_memory_windows(id,token_id,pair_id,window_kind)
            VALUES (281,1,1,'WINDOW_1H');
            INSERT INTO printer_memory_windows(id,token_id,pair_id,window_kind)
            VALUES (282,1,1,'WINDOW_1H');
            INSERT INTO printer_memory_factory_campaign_windows(
                window_id,campaign_id,run_id,cycle_id,token_slot_id,
                token_row_id,pair_row_id,window_kind,window_state,
                memory_window_row_id,first_terminal_cause,terminal_at,updated_at
            ) VALUES (
                'cw-1h','campaign-a','run-a','cycle-a','slot-a',
                1,1,'WINDOW_1H','CLOSE_PENDING',NULL,NULL,NULL,
                '2026-08-28T00:00:00+00:00'
            );
            """
        )
        return connection

    def test_precreated_1h_bind_is_identity_only_and_idempotent(self) -> None:
        helper = getattr(
            selective, "bind_precreated_1h_campaign_window_memory_row", None
        )
        self.assertTrue(
            callable(helper),
            "missing identity-only WINDOW_1H pre-E2Z bind owner",
        )
        connection = self._connection()
        try:
            before = connection.execute(
                "SELECT window_state,first_terminal_cause,terminal_at "
                "FROM printer_memory_factory_campaign_windows WHERE window_id='cw-1h'"
            ).fetchone()
            first = helper(
                connection,
                campaign_id="campaign-a",
                run_id="run-a",
                cycle_id="cycle-a",
                token_slot_id="slot-a",
                token_row_id=1,
                pair_row_id=1,
                campaign_window_id="cw-1h",
                memory_window_row_id=281,
                now="2026-08-28T00:01:00+00:00",
            )
            after = connection.execute(
                "SELECT memory_window_row_id,window_state,first_terminal_cause,terminal_at "
                "FROM printer_memory_factory_campaign_windows WHERE window_id='cw-1h'"
            ).fetchone()
            self.assertEqual(int(after["memory_window_row_id"]), 281)
            self.assertEqual(
                tuple(before),
                (after["window_state"], after["first_terminal_cause"], after["terminal_at"]),
            )
            self.assertTrue(first["bound"])
            self.assertFalse(first["idempotent"])

            second = helper(
                connection,
                campaign_id="campaign-a",
                run_id="run-a",
                cycle_id="cycle-a",
                token_slot_id="slot-a",
                token_row_id=1,
                pair_row_id=1,
                campaign_window_id="cw-1h",
                memory_window_row_id=281,
                now="2026-08-28T00:02:00+00:00",
            )
            self.assertFalse(second["bound"])
            self.assertTrue(second["idempotent"])
        finally:
            connection.close()

    def test_precreated_1h_bind_rejects_different_physical_row(self) -> None:
        helper = getattr(
            selective, "bind_precreated_1h_campaign_window_memory_row", None
        )
        self.assertTrue(callable(helper))
        connection = self._connection()
        try:
            helper(
                connection,
                campaign_id="campaign-a",
                run_id="run-a",
                cycle_id="cycle-a",
                token_slot_id="slot-a",
                token_row_id=1,
                pair_row_id=1,
                campaign_window_id="cw-1h",
                memory_window_row_id=281,
            )
            with self.assertRaises(selective.Selective1hError):
                helper(
                    connection,
                    campaign_id="campaign-a",
                    run_id="run-a",
                    cycle_id="cycle-a",
                    token_slot_id="slot-a",
                    token_row_id=1,
                    pair_row_id=1,
                    campaign_window_id="cw-1h",
                    memory_window_row_id=282,
                )
        finally:
            connection.close()

    def test_1h_close_binds_campaign_window_before_e2z(self) -> None:
        source = inspect.getsource(factory._audit_1h_close_from_evidence)
        bind_marker = "_bind_precreated_1h_campaign_window_before_e2z"
        self.assertIn(bind_marker, source)
        self.assertIn("run_e2z_pipeline", source)
        self.assertLess(source.index(bind_marker), source.index("run_e2z_pipeline"))
        self.assertLess(source.index("conn.commit()"), source.index("run_e2z_pipeline"))


if __name__ == "__main__":
    unittest.main()
