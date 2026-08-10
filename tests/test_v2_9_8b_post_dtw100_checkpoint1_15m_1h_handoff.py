"""Post-DTW100 Checkpoint 1: strict clean 15m -> 1h handoff proof."""

from __future__ import annotations

import unittest

from printer_v1.operator_cli.operational_selective_1h import Selective1hError
from tests.test_v2_9_8b_operational_selective_1h import Selective1hFixture


class Checkpoint1Clean15mTo1hHandoffTests(unittest.TestCase):
    def setUp(self) -> None:
        self.fx = Selective1hFixture()

    def tearDown(self) -> None:
        self.fx.close()

    def test_successful_handoff_preserves_identity_and_advances_slots(self) -> None:
        self.fx.prepare_eligible(token_id=1, window_id=301, outcome="CONSOLIDATION")
        self.fx.prepare_eligible(token_id=2, window_id=302, outcome="NO_PUMP")

        result = self.fx.evaluate()
        self.assertEqual(result["continue_count"], 2)

        slots = self.fx.connection.execute(
            """SELECT token_slot_id, token_row_id, pair_row_id, lifecycle_identity,
                      token_state
               FROM printer_memory_factory_campaign_token_slots
               WHERE campaign_id='campaign-1h' AND run_id='run-1h'
                 AND cycle_id='cycle-1h'
               ORDER BY slot_ordinal"""
        ).fetchall()
        self.assertEqual([str(row["token_state"]) for row in slots], [
            "WINDOW_1H_CONTINUING",
            "WINDOW_1H_CONTINUING",
        ])

        windows = self.fx.connection.execute(
            """SELECT token_slot_id, token_row_id, pair_row_id, window_kind,
                      window_state, root_15m_lifecycle_identity,
                      predecessor_window_id, memory_window_row_id
               FROM printer_memory_factory_campaign_windows
               WHERE window_kind='WINDOW_1H'
               ORDER BY token_slot_id"""
        ).fetchall()
        self.assertEqual(len(windows), 2)
        plans = {p["token_slot_id"]: p for p in result["token_plans"]}
        for row in windows:
            slot_id = str(row["token_slot_id"])
            slot_ordinal = int(slot_id.rsplit("-", 1)[1])
            self.assertEqual(int(row["token_row_id"]), slot_ordinal)
            self.assertEqual(int(row["pair_row_id"]), slot_ordinal)
            self.assertEqual(str(row["window_kind"]), "WINDOW_1H")
            self.assertEqual(str(row["window_state"]), "PLANNED")
            self.assertEqual(
                str(row["root_15m_lifecycle_identity"]),
                f"lifecycle-{slot_ordinal}",
            )
            self.assertEqual(
                str(row["predecessor_window_id"]),
                str(plans[slot_id]["campaign_window_15m_id"]),
            )
            self.assertIsNone(row["memory_window_row_id"])

    def test_conflicting_slot_state_fails_before_any_handoff_side_effect(self) -> None:
        self.fx.prepare_eligible(token_id=1, window_id=311, outcome="DUMP")
        self.fx.prepare_eligible(token_id=2, window_id=312, outcome="CONSOLIDATION")
        # Schema-valid but impossible before a first handoff evaluation: the slot
        # already claims to be in 1h while no continuation object/window exists.
        with self.fx.connection:
            self.fx.connection.execute(
                """UPDATE printer_memory_factory_campaign_token_slots
                   SET token_state='WINDOW_1H_CONTINUING'
                   WHERE token_slot_id='slot-1'"""
            )

        before_objects = int(self.fx.connection.execute(
            """SELECT COUNT(*) FROM printer_memory_factory_campaign_objects
               WHERE object_kind='CONTINUATION_4A'"""
        ).fetchone()[0])
        before_1h = int(self.fx.connection.execute(
            """SELECT COUNT(*) FROM printer_memory_factory_campaign_windows
               WHERE window_kind='WINDOW_1H'"""
        ).fetchone()[0])

        with self.assertRaises(Selective1hError):
            self.fx.evaluate()

        after_objects = int(self.fx.connection.execute(
            """SELECT COUNT(*) FROM printer_memory_factory_campaign_objects
               WHERE object_kind='CONTINUATION_4A'"""
        ).fetchone()[0])
        after_1h = int(self.fx.connection.execute(
            """SELECT COUNT(*) FROM printer_memory_factory_campaign_windows
               WHERE window_kind='WINDOW_1H'"""
        ).fetchone()[0])
        slot2_state = str(self.fx.connection.execute(
            """SELECT token_state
               FROM printer_memory_factory_campaign_token_slots
               WHERE token_slot_id='slot-2'"""
        ).fetchone()[0])

        self.assertEqual(after_objects, before_objects)
        self.assertEqual(after_1h, before_1h)
        self.assertEqual(slot2_state, "SELECTED")


if __name__ == "__main__":
    unittest.main()
