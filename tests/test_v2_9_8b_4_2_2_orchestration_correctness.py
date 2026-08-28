"""Focused RED/GREEN contracts for the four 4/2/2 orchestration defects."""

from __future__ import annotations

import sqlite3
import unittest

from printer_v1.operator_cli import one_command_15m_factory as factory
from tests.test_v2_9_8b_post_dtw100_checkpoint6_1h_terminal_reconciliation import (
    Checkpoint6FirstHourTerminalReconciliationTests,
)


class OneHourCampaignBindingOrderTests(unittest.TestCase):
    def setUp(self) -> None:
        self.helper = Checkpoint6FirstHourTerminalReconciliationTests()
        self.fx = self.helper._prepared_campaign()
        self.close_step, self.memory_window_id = self.helper._physical_1h(self.fx)

    def tearDown(self) -> None:
        self.fx.close()

    def _bind(self):
        from printer_v1.operator_cli.operational_selective_1h import (
            bind_precreated_1h_campaign_window_memory_row,
        )

        window = self.helper._campaign_window(self.fx, 1)
        slot = self.fx.connection.execute(
            """SELECT token_slot_id FROM printer_memory_factory_campaign_token_slots
               WHERE campaign_id='campaign-1h' AND run_id='run-1h'
                 AND cycle_id='cycle-1h' AND token_row_id=1"""
        ).fetchone()
        return bind_precreated_1h_campaign_window_memory_row(
            self.fx.connection,
            campaign_id="campaign-1h",
            run_id="run-1h",
            cycle_id="cycle-1h",
            token_slot_id=str(slot["token_slot_id"]),
            token_row_id=1,
            pair_row_id=1,
            campaign_window_id=str(window["window_id"]),
            memory_window_row_id=self.memory_window_id,
        )

    def test_one_hour_identity_bind_is_idempotent_and_nonterminal(self) -> None:
        before = self.helper._campaign_window(self.fx, 1)
        first = self._bind()
        second = self._bind()
        after = self.helper._campaign_window(self.fx, 1)

        self.assertTrue(first["bound"])
        self.assertTrue(second["idempotent"])
        self.assertEqual(int(after["memory_window_row_id"]), self.memory_window_id)
        self.assertEqual(str(after["window_state"]), str(before["window_state"]))
        self.assertEqual(after["first_terminal_cause"], before["first_terminal_cause"])
        self.assertEqual(after["terminal_at"], before["terminal_at"])

    def test_one_hour_factory_owner_binds_before_terminal_reconciliation(self) -> None:
        result = factory._bind_precreated_1h_campaign_window_before_e2z(
            self.fx.connection,
            step=self.close_step,
            memory_window_row_id=self.memory_window_id,
        )
        row = self.helper._campaign_window(self.fx, 1)
        self.assertTrue(result["bound"])
        self.assertEqual(int(row["memory_window_row_id"]), self.memory_window_id)
        self.assertEqual(str(row["window_state"]), "CLOSE_PENDING")
        self.assertIsNone(row["first_terminal_cause"])
        self.assertIsNone(row["terminal_at"])

    def test_one_hour_bind_rejects_wrong_physical_token_pair(self) -> None:
        wrong = int(
            self.fx.connection.execute(
                """INSERT INTO printer_memory_windows(
                       token_id,pair_id,window_kind,opened_at,closed_at,
                       memory_status,data_quality_label,window_status,
                       memory_quality_label,do_not_train,supporting_context_json
                   ) VALUES (2,2,'WINDOW_1H','2026-08-01T00:00:00+00:00',
                       '2026-08-01T01:00:00+00:00','PARTIAL_MEMORY','CLEAN_DATA',
                       'WINDOW_CLOSED','PARTIAL_MEMORY',0,'{}')"""
            ).lastrowid
        )
        with self.assertRaisesRegex(Exception, "identity"):
            factory._bind_precreated_1h_campaign_window_before_e2z(
                self.fx.connection,
                step=self.close_step,
                memory_window_row_id=wrong,
            )
        self.assertIsNone(
            self.helper._campaign_window(self.fx, 1)["memory_window_row_id"]
        )

    def test_one_hour_bind_rejects_ambiguous_campaign_window(self) -> None:
        original = self.helper._campaign_window(self.fx, 1)
        self.fx.connection.execute(
            """INSERT INTO printer_memory_factory_campaign_windows(
                   window_id,campaign_id,run_id,cycle_id,token_slot_id,
                   token_row_id,pair_row_id,window_kind,window_state,
                   root_15m_lifecycle_identity,predecessor_window_id,
                   checkpoint_cutoff,support_only,created_at,updated_at
               ) VALUES ('ambiguous-1h','campaign-1h','run-1h','cycle-1h',?,
                   1,1,'WINDOW_1H','CLOSE_PENDING',?,?,?,0,?,?)""",
            (
                str(original["token_slot_id"]),
                str(original["root_15m_lifecycle_identity"]),
                str(original["predecessor_window_id"]),
                str(original["checkpoint_cutoff"]),
                str(original["created_at"]),
                str(original["updated_at"]),
            ),
        )
        self.fx.connection.commit()
        with self.assertRaisesRegex(Exception, "ambiguous"):
            self._bind()


if __name__ == "__main__":
    unittest.main()
