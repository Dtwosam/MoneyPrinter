"""Offline TDD for the exact two-slot standard 1h -> 4h campaign handoff."""

from __future__ import annotations

from datetime import timedelta
import json
import unittest

from printer_v1.operator_cli import campaign_ownership
from printer_v1.operator_cli.operational_selective_1h import campaign_window_id_for
from tests.test_v2_9_8b_post_dtw100_checkpoint4_1h_close_boundary import (
    Checkpoint4FirstHourCloseBoundaryTests,
)
from tests.test_v2_9_8b_operational_selective_1h import T15, T1H, _iso


class StandardFourHourCampaignHandoffTests(unittest.TestCase):
    def _prepared_closed_first_hour(self):
        fx = Checkpoint4FirstHourCloseBoundaryTests()._prepared_campaign(
            standard_four_hour_campaign=True
        )
        with fx.connection:
            for token_id, lane in ((1, "TRACK_FAST"), (2, "TRACK_NORMAL")):
                fx.connection.execute(
                    "UPDATE printer_tokens SET token_status=? WHERE id=?",
                    (lane, token_id),
                )
                start_id = 12000 + token_id * 10
                close_id = start_id + 1
                fx.connection.execute(
                    """INSERT INTO printer_token_snapshots(
                        id,token_id,pair_id,captured_at,tracking_lane,snapshot_mode,
                        source_status,data_quality_label
                    ) VALUES (?,?,?,?,?,'TOKEN','COMPLETE','CLEAN_DATA')""",
                    (start_id, token_id, token_id, _iso(T15), lane),
                )
                fx.connection.execute(
                    """INSERT INTO printer_token_snapshots(
                        id,token_id,pair_id,captured_at,tracking_lane,snapshot_mode,
                        source_status,data_quality_label
                    ) VALUES (?,?,?,?,?,'TOKEN','COMPLETE','CLEAN_DATA')""",
                    (close_id, token_id, token_id, _iso(T1H), lane),
                )
                memory_id = 13000 + token_id
                fx.connection.execute(
                    """INSERT INTO printer_memory_windows(
                        id,token_id,pair_id,window_kind,opened_at,closed_at,
                        window_start_at,window_end_at,snapshot_start_id,snapshot_end_id,
                        memory_status,data_quality_label,window_status,
                        memory_quality_label,outcome_label,do_not_train,supporting_context_json
                    ) VALUES (?,?,?,'WINDOW_1H',?,?,?,?,?,?,'PARTIAL_MEMORY',
                        'CLEAN_DATA','WINDOW_CLOSED','PARTIAL_MEMORY','CONSOLIDATION',0,?)""",
                    (
                        memory_id, token_id, token_id,
                        _iso(T15), _iso(T1H), _iso(T15), _iso(T1H),
                        start_id, close_id,
                        json.dumps({
                            "tracking_lane": lane,
                            "continuation_of_window_id": 600 + token_id,
                            "linked_closing_snapshot_id": 5000 + token_id,
                        }),
                    ),
                )
                fx.connection.execute(
                    """INSERT INTO printer_episodes(
                        memory_window_id,token_id,pair_id,episode_kind,episode_status,
                        memory_status,data_quality_label,do_not_train,window_kind,
                        memory_quality_label,episode_outcome_label
                    ) VALUES (?,?,?,'WINDOW_1H_CLEAN_MEMORY','COMPLETE','CLEAN_MEMORY',
                        'CLEAN_DATA',0,'WINDOW_1H','CLEAN_MEMORY','CONSOLIDATION')""",
                    (memory_id, token_id, token_id),
                )
                close_step = fx.connection.execute(
                    """SELECT id FROM printer_memory_factory_run_steps
                       WHERE run_id='factory-run-1' AND token_id=?
                         AND step_kind IN (
                             'CONTINUATION_CLOSE','CONTINUATION_CLOSE_AUDIT'
                         )""",
                    (token_id,),
                ).fetchone()
                self.assertIsNotNone(close_step)
                fx.connection.execute(
                    """UPDATE printer_memory_factory_run_steps
                       SET step_status='SUCCEEDED',snapshot_id=?,memory_window_id=?,
                           tracking_lane=?,result_json=?
                       WHERE id=?""",
                    (
                        close_id, memory_id, lane,
                        json.dumps({"ok": True, "memory_window_id": memory_id}),
                        int(close_step[0]),
                    ),
                )
                scheduler_job_id = int(
                    fx.connection.execute(
                        "SELECT scheduler_job_id FROM printer_memory_factory_run_steps "
                        "WHERE id=?",
                        (int(close_step[0]),),
                    ).fetchone()[0]
                )
                fx.connection.execute(
                    """UPDATE printer_scheduler_jobs
                       SET status='SUCCEEDED',finished_at=?,locked_at=NULL,
                           lock_owner=NULL,last_error=NULL
                       WHERE id=?""",
                    (_iso(T1H), scheduler_job_id),
                )
                fx.connection.execute(
                    """UPDATE printer_memory_factory_campaign_scheduler_work
                       SET work_state='SUCCEEDED',first_terminal_cause='fixture_clean_1h',
                           terminal_at=?,updated_at=?
                       WHERE scheduler_job_id=?""",
                    (_iso(T1H), _iso(T1H), scheduler_job_id),
                )
                campaign_1h = fx.connection.execute(
                    """SELECT window_id FROM printer_memory_factory_campaign_windows
                       WHERE campaign_id='campaign-1h' AND run_id='run-1h'
                         AND cycle_id='cycle-1h' AND token_slot_id=?
                         AND window_kind='WINDOW_1H'""",
                    (f"slot-{token_id}",),
                ).fetchone()
                self.assertIsNotNone(campaign_1h)
                fx.connection.execute(
                    """UPDATE printer_memory_factory_campaign_windows
                       SET window_state='CLEAN_PROMOTED',memory_window_row_id=?,
                           first_terminal_cause='fixture_clean_1h',terminal_at=?,updated_at=?
                       WHERE window_id=?""",
                    (memory_id, _iso(T1H), _iso(T1H), str(campaign_1h[0])),
                )
                fx.connection.execute(
                    """UPDATE printer_memory_factory_campaign_token_slots
                       SET token_state='WINDOW_1H_CLOSED',updated_at=?
                       WHERE token_slot_id=?""",
                    (_iso(T1H), f"slot-{token_id}"),
                )
        return fx

    @staticmethod
    def _candidates(fx):
        out = []
        for token_id, lane in ((1, "TRACK_FAST"), (2, "TRACK_NORMAL")):
            predecessor = fx.connection.execute(
                """SELECT window_id,memory_window_row_id,root_15m_lifecycle_identity
                   FROM printer_memory_factory_campaign_windows
                   WHERE campaign_id='campaign-1h' AND run_id='run-1h'
                     AND cycle_id='cycle-1h' AND token_slot_id=?
                     AND window_kind='WINDOW_1H'""",
                (f"slot-{token_id}",),
            ).fetchone()
            memory_id = int(predecessor["memory_window_row_id"])
            out.append(
                {
                    "token_slot_id": f"slot-{token_id}",
                    "token_row_id": token_id,
                    "pair_row_id": token_id,
                    "mint_identity": f"mint-{token_id}",
                    "pair_identity": f"pair-{token_id}",
                    "lifecycle_identity": str(predecessor["root_15m_lifecycle_identity"]),
                    "campaign_window_1h_id": str(predecessor["window_id"]),
                    "memory_window_1h_id": memory_id,
                    "campaign_window_4h_id": campaign_window_id_for(
                        campaign_id="campaign-1h",
                        run_id="run-1h",
                        cycle_id="cycle-1h",
                        token_slot_id=f"slot-{token_id}",
                        window_kind="WINDOW_4H",
                        period_key=str(memory_id),
                    ),
                    "tracking_lane": lane,
                }
            )
        return out

    def _handoff(self, fx, candidates):
        owner = getattr(campaign_ownership, "persist_standard_four_hour_handoff_set", None)
        self.assertIsNotNone(owner, "standard four-hour campaign handoff owner is missing")
        return owner(
            fx.connection,
            campaign_id="campaign-1h",
            run_id="run-1h",
            cycle_id="cycle-1h",
            candidates=candidates,
            now=_iso(T1H + timedelta(seconds=1)),
        )

    def test_two_clean_first_hour_predecessors_create_two_exact_4h_successors(self) -> None:
        fx = self._prepared_closed_first_hour()
        try:
            candidates = self._candidates(fx)
            result = self._handoff(fx, candidates)
            self.assertTrue(result["persisted"])
            self.assertEqual(result["continuation_count"], 2)
            rows = fx.connection.execute(
                """SELECT token_slot_id,token_row_id,pair_row_id,window_kind,
                          window_state,root_15m_lifecycle_identity,predecessor_window_id,
                          memory_window_row_id
                   FROM printer_memory_factory_campaign_windows
                   WHERE campaign_id='campaign-1h' AND run_id='run-1h'
                     AND cycle_id='cycle-1h' AND window_kind='WINDOW_4H'
                   ORDER BY token_slot_id"""
            ).fetchall()
            self.assertEqual(len(rows), 2)
            self.assertEqual([str(r["window_state"]) for r in rows], ["PLANNED", "PLANNED"])
            self.assertTrue(all(r["memory_window_row_id"] is None for r in rows))
            self.assertEqual(
                [str(r["predecessor_window_id"]) for r in rows],
                [candidates[0]["campaign_window_1h_id"], candidates[1]["campaign_window_1h_id"]],
            )
            states = fx.connection.execute(
                """SELECT token_state FROM printer_memory_factory_campaign_token_slots
                   WHERE campaign_id='campaign-1h' AND run_id='run-1h'
                     AND cycle_id='cycle-1h' ORDER BY slot_ordinal"""
            ).fetchall()
            self.assertEqual([str(r[0]) for r in states], [
                "WINDOW_4H_CONTINUING", "WINDOW_4H_CONTINUING"
            ])
        finally:
            fx.close()

    def test_one_bad_predecessor_rolls_back_both_successors_and_slot_changes(self) -> None:
        fx = self._prepared_closed_first_hour()
        try:
            candidates = self._candidates(fx)
            with fx.connection:
                fx.connection.execute(
                    """UPDATE printer_memory_factory_campaign_windows
                       SET window_state='DIRTY'
                       WHERE window_id=?""",
                    (candidates[1]["campaign_window_1h_id"],),
                )
            with self.assertRaises(Exception):
                self._handoff(fx, candidates)
            count = int(fx.connection.execute(
                "SELECT COUNT(*) FROM printer_memory_factory_campaign_windows WHERE window_kind='WINDOW_4H'"
            ).fetchone()[0])
            self.assertEqual(count, 0)
            states = fx.connection.execute(
                """SELECT token_state FROM printer_memory_factory_campaign_token_slots
                   WHERE campaign_id='campaign-1h' AND run_id='run-1h'
                     AND cycle_id='cycle-1h' ORDER BY slot_ordinal"""
            ).fetchall()
            self.assertEqual([str(r[0]) for r in states], ["WINDOW_1H_CLOSED", "WINDOW_1H_CLOSED"])
        finally:
            fx.close()

    def test_exact_repeat_is_idempotent_and_creates_no_duplicate_successor(self) -> None:
        fx = self._prepared_closed_first_hour()
        try:
            candidates = self._candidates(fx)
            first = self._handoff(fx, candidates)
            second = self._handoff(fx, candidates)
            self.assertTrue(first["persisted"])
            self.assertFalse(second["persisted"])
            self.assertTrue(second["replay"])
            self.assertEqual(
                int(fx.connection.execute(
                    "SELECT COUNT(*) FROM printer_memory_factory_campaign_windows WHERE window_kind='WINDOW_4H'"
                ).fetchone()[0]),
                2,
            )
        finally:
            fx.close()

    def test_physical_first_hour_identity_mismatch_blocks_before_successor_creation(self) -> None:
        fx = self._prepared_closed_first_hour()
        try:
            candidates = self._candidates(fx)
            with fx.connection:
                fx.connection.execute(
                    "UPDATE printer_memory_windows SET pair_id=2 WHERE id=?",
                    (candidates[0]["memory_window_1h_id"],),
                )
            with self.assertRaises(Exception):
                self._handoff(fx, candidates)
            self.assertEqual(
                int(fx.connection.execute(
                    "SELECT COUNT(*) FROM printer_memory_factory_campaign_windows WHERE window_kind='WINDOW_4H'"
                ).fetchone()[0]),
                0,
            )
        finally:
            fx.close()


if __name__ == "__main__":
    unittest.main()
