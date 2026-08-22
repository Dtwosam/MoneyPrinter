"""Offline TDD for standard two-token 4h collection state/accounting composition."""

from __future__ import annotations

from datetime import timedelta
import unittest

from printer_v1.operator_cli import campaign_ownership
from printer_v1.operator_cli import one_command_15m_factory as factory
from printer_v1.scheduler.scheduler import (
    LockResult,
    claim_due_job,
    fail_job,
)
from tests.test_v2_9_8b_post_dtw100_standard_four_hour_campaign_planning import (
    StandardFourHourCampaignPlanningTests,
)
from tests.test_v2_9_8b_operational_selective_1h import T1H, _iso


class StandardFourHourCollectionStateAccountingTests(unittest.TestCase):
    def setUp(self) -> None:
        helper = StandardFourHourCampaignPlanningTests()
        self.fx, self.candidates = helper._prepared()
        result = helper._plan(self.fx, self.candidates)
        self.assertTrue(result["planned"])
        self.assertFalse(result["replay"])

    def tearDown(self) -> None:
        self.fx.close()

    def _step(self, token_id: int, kind: str, *, index: int = 0):
        rows = self.fx.connection.execute(
            """SELECT * FROM printer_memory_factory_run_steps
               WHERE run_id='factory-run-1' AND token_id=? AND step_kind=?
               ORDER BY scheduled_for,id""",
            (token_id, kind),
        ).fetchall()
        self.assertGreater(len(rows), index)
        return rows[index]

    def _window_state(self, token_id: int) -> str:
        row = self.fx.connection.execute(
            """SELECT window_state FROM printer_memory_factory_campaign_windows
               WHERE campaign_id='campaign-1h' AND run_id='run-1h'
                 AND cycle_id='cycle-1h' AND token_row_id=?
                 AND window_kind='WINDOW_4H'""",
            (token_id,),
        ).fetchone()
        self.assertIsNotNone(row)
        return str(row[0])

    def _slot_state(self, token_id: int) -> str:
        row = self.fx.connection.execute(
            """SELECT token_state FROM printer_memory_factory_campaign_token_slots
               WHERE campaign_id='campaign-1h' AND run_id='run-1h'
                 AND cycle_id='cycle-1h' AND token_row_id=?""",
            (token_id,),
        ).fetchone()
        self.assertIsNotNone(row)
        return str(row[0])

    def _work_state(self, job_id: int) -> str:
        row = self.fx.connection.execute(
            """SELECT work_state FROM printer_memory_factory_campaign_scheduler_work
               WHERE scheduler_job_id=? AND stage_id='WINDOW_4H'""",
            (job_id,),
        ).fetchone()
        self.assertIsNotNone(row)
        return str(row[0])

    def _claim(self, step, *, now=T1H) -> int:
        job_id = int(step["scheduler_job_id"])
        claimed = claim_due_job(
            self.fx.connection,
            job_id=job_id,
            lock_owner="four-hour-state-test",
            now=now,
        )
        self.assertEqual(claimed, LockResult.ACQUIRED)
        factory._update_step(
            self.fx.connection, int(step["id"]), "RUNNING", {}
        )
        factory._sync_owned_campaign_scheduler_job(
            self.fx.connection, scheduler_job_id=job_id
        )
        return job_id

    def test_long_snapshot_claim_moves_exact_owned_4h_window_to_collecting(self) -> None:
        step = self._step(1, "LONG_CONTINUATION_SNAPSHOT")
        job_id = self._claim(step)
        self.assertEqual(self._work_state(job_id), "RUNNING")
        self.assertEqual(self._window_state(1), "PLANNED")
        marker = getattr(factory, "_mark_owned_long_window_collecting", None)
        self.assertIsNotNone(marker, "4h collecting-state owner is missing")
        marker(
            self.fx.connection,
            scheduler_job_id=job_id,
            step_kind="LONG_CONTINUATION_SNAPSHOT",
        )
        self.assertEqual(self._window_state(1), "COLLECTING")
        self.assertEqual(self._window_state(2), "PLANNED")

    def test_long_close_claim_moves_only_collecting_4h_window_to_close_pending(self) -> None:
        snapshot = self._step(1, "LONG_CONTINUATION_SNAPSHOT")
        snapshot_job = self._claim(snapshot)
        collecting = getattr(factory, "_mark_owned_long_window_collecting", None)
        self.assertIsNotNone(collecting, "4h collecting-state owner is missing")
        collecting(
            self.fx.connection,
            scheduler_job_id=snapshot_job,
            step_kind="LONG_CONTINUATION_SNAPSHOT",
        )
        close = self._step(1, "LONG_CONTINUATION_CLOSE")
        close_due = __import__("datetime").datetime.fromisoformat(str(close["scheduled_for"]))
        close_job = self._claim(close, now=close_due)
        closer = getattr(factory, "_mark_owned_long_window_close_pending", None)
        self.assertIsNotNone(closer, "4h close-pending owner is missing")
        closer(
            self.fx.connection,
            scheduler_job_id=close_job,
            step_kind="LONG_CONTINUATION_CLOSE",
        )
        self.assertEqual(self._window_state(1), "CLOSE_PENDING")
        self.assertEqual(self._window_state(2), "PLANNED")

    def test_long_reservation_records_match_existing_projected_request_shapes(self) -> None:
        opening = self._step(1, "LONG_CONTINUATION_SNAPSHOT", index=0)
        ordinary = self._step(1, "LONG_CONTINUATION_SNAPSHOT", index=1)
        close = self._step(1, "LONG_CONTINUATION_CLOSE")
        cases = (
            (opening, "LONG_CONTINUATION_OPENING_OBSERVATION"),
            (ordinary, "LONG_CONTINUATION_SNAPSHOT_OBSERVATION"),
            (close, "LONG_CONTINUATION_CLOSE_OBSERVATION"),
        )
        for step, family in cases:
            projected = factory._projected_requests_for_step(step)
            reservations = factory._lifecycle_reservation_records_for_step(
                run_id="factory-run-1",
                pending=step,
                projected_requests=projected,
            )
            self.assertEqual(len(reservations), projected)
            self.assertEqual(
                {str(row["operation_family"]) for row in reservations}, {family}
            )
            self.assertEqual(
                len({int(row["reservation_ordinal"]) for row in reservations}),
                projected,
            )

    def test_long_failure_blocks_only_failed_token_4h_lifecycle(self) -> None:
        step = self._step(1, "LONG_CONTINUATION_SNAPSHOT")
        job_id = self._claim(step)
        collecting = getattr(factory, "_mark_owned_long_window_collecting", None)
        terminalize = getattr(factory, "_terminalize_owned_long_window", None)
        self.assertIsNotNone(collecting, "4h collecting-state owner is missing")
        self.assertIsNotNone(terminalize, "4h terminal lifecycle owner is missing")
        collecting(
            self.fx.connection,
            scheduler_job_id=job_id,
            step_kind="LONG_CONTINUATION_SNAPSHOT",
        )
        fail_job(
            self.fx.connection,
            job_id=job_id,
            error="four_hour_fixture_failure",
            now=T1H,
            max_retries=0,
        )
        factory._update_step(
            self.fx.connection,
            int(step["id"]),
            "FAILED",
            {},
            error="four_hour_fixture_failure",
        )
        factory._sync_owned_campaign_scheduler_job(
            self.fx.connection, scheduler_job_id=job_id
        )
        factory._cancel_pending_for_token(
            self.fx.connection,
            "factory-run-1",
            1,
            "four_hour_fixture_failure",
        )
        terminalize(
            self.fx.connection,
            scheduler_job_id=job_id,
            terminal_state="BLOCKED",
            terminal_cause="four_hour_fixture_failure",
        )
        self.assertEqual(self._window_state(1), "BLOCKED")
        self.assertEqual(self._slot_state(1), "FAILED")
        self.assertEqual(self._window_state(2), "PLANNED")
        self.assertEqual(self._slot_state(2), "WINDOW_4H_CONTINUING")
        peer_pending = int(self.fx.connection.execute(
            """SELECT COUNT(*) FROM printer_memory_factory_run_steps
               WHERE run_id='factory-run-1' AND token_id=2
                 AND step_kind LIKE 'LONG_CONTINUATION_%' AND step_status='PENDING'"""
        ).fetchone()[0])
        self.assertGreater(peer_pending, 0)

    def test_shared_stop_cancels_both_4h_windows_slots_and_owned_work(self) -> None:
        factory._cancel_pending(
            self.fx.connection, "factory-run-1", "four_hour_shared_stop"
        )
        changed = factory._cancel_owned_continuation_windows_for_run(
            self.fx.connection,
            factory_run_id="factory-run-1",
            terminal_cause="four_hour_shared_stop",
        )
        self.assertEqual(changed, 2)
        self.assertEqual(self._window_state(1), "CANCELLED")
        self.assertEqual(self._window_state(2), "CANCELLED")
        self.assertEqual(self._slot_state(1), "MANUAL_REVIEW")
        self.assertEqual(self._slot_state(2), "MANUAL_REVIEW")
        active = int(self.fx.connection.execute(
            """SELECT COUNT(*) FROM printer_memory_factory_campaign_scheduler_work
               WHERE factory_run_id='factory-run-1' AND stage_id='WINDOW_4H'
                 AND work_state IN ('PENDING','RUNNING','COOLDOWN')"""
        ).fetchone()[0])
        self.assertEqual(active, 0)

    def _selector(self, *, now=T1H):
        selector = getattr(factory, "_select_next_pending_step", None)
        self.assertIsNotNone(selector, "categorical WINDOW_4H fairness selector is missing")
        return selector(self.fx.connection, run_id="factory-run-1", now=now)

    def _isolate_4h_fairness_scope(self) -> None:
        """Remove unrelated pending fixture work so 4h fairness is the active scope."""
        with self.fx.connection:
            rows = self.fx.connection.execute(
                """SELECT id,scheduler_job_id
                   FROM printer_memory_factory_run_steps
                   WHERE run_id='factory-run-1' AND step_status='PENDING'
                     AND step_kind NOT LIKE 'LONG_CONTINUATION_%'"""
            ).fetchall()
            for row in rows:
                self.fx.connection.execute(
                    """UPDATE printer_memory_factory_run_steps
                       SET step_status='CANCELLED',finished_at=?,updated_at=?
                       WHERE id=?""",
                    (_iso(T1H), _iso(T1H), int(row["id"])),
                )
                if row["scheduler_job_id"] is not None:
                    self.fx.connection.execute(
                        """UPDATE printer_scheduler_jobs
                           SET status='CANCELLED',finished_at=?,updated_at=?
                           WHERE id=? AND status='PENDING'""",
                        (_iso(T1H), _iso(T1H), int(row["scheduler_job_id"])),
                    )

    def _make_second_fast_snapshot_due(self) -> tuple[object, object]:
        self._isolate_4h_fairness_scope()
        token1_open = self._step(1, "LONG_CONTINUATION_SNAPSHOT", index=0)
        token1_second = self._step(1, "LONG_CONTINUATION_SNAPSHOT", index=1)
        token2_open = self._step(2, "LONG_CONTINUATION_SNAPSHOT", index=0)
        with self.fx.connection:
            self.fx.connection.execute(
                """UPDATE printer_scheduler_jobs
                   SET status='SUCCEEDED',started_at=?,finished_at=?,updated_at=?
                   WHERE id=?""",
                (_iso(T1H), _iso(T1H), _iso(T1H), int(token1_open["scheduler_job_id"])),
            )
            self.fx.connection.execute(
                """UPDATE printer_memory_factory_run_steps
                   SET step_status='SUCCEEDED',started_at=?,finished_at=?,updated_at=?
                   WHERE id=?""",
                (_iso(T1H), _iso(T1H), _iso(T1H), int(token1_open["id"])),
            )
            self.fx.connection.execute(
                "UPDATE printer_scheduler_jobs SET scheduled_for=? WHERE id=?",
                (_iso(T1H), int(token1_second["scheduler_job_id"])),
            )
            self.fx.connection.execute(
                "UPDATE printer_memory_factory_run_steps SET scheduled_for=? WHERE id=?",
                (_iso(T1H), int(token1_second["id"])),
            )
        return token1_second, token2_open

    def test_mixed_lane_due_fairness_serves_less_served_token(self) -> None:
        token1_second, token2_open = self._make_second_fast_snapshot_due()
        selected = self._selector()
        self.assertEqual(int(selected["id"]), int(token2_open["id"]))
        self.assertNotEqual(int(selected["id"]), int(token1_second["id"]))

    def test_same_lane_due_fairness_serves_peer_before_second_ordinary_unit(self) -> None:
        token1_second, token2_open = self._make_second_fast_snapshot_due()
        with self.fx.connection:
            self.fx.connection.execute(
                "UPDATE printer_memory_factory_run_steps SET tracking_lane='TRACK_FAST' WHERE id=?",
                (int(token2_open["id"]),),
            )
        selected = self._selector()
        self.assertEqual(int(selected["id"]), int(token2_open["id"]))
        self.assertEqual(str(selected["tracking_lane"]), "TRACK_FAST")
        self.assertNotEqual(int(selected["id"]), int(token1_second["id"]))

    def test_due_long_track_snapshot_preserves_agents_priority_over_close(self) -> None:
        self._isolate_4h_fairness_scope()
        ordinary = self._step(2, "LONG_CONTINUATION_SNAPSHOT", index=0)
        close = self._step(1, "LONG_CONTINUATION_CLOSE")
        with self.fx.connection:
            self.fx.connection.execute(
                "UPDATE printer_scheduler_jobs SET scheduled_for=? WHERE id=?",
                (_iso(T1H), int(close["scheduler_job_id"])),
            )
            self.fx.connection.execute(
                "UPDATE printer_memory_factory_run_steps SET scheduled_for=? WHERE id=?",
                (_iso(T1H), int(close["id"])),
            )
        selected = self._selector()
        self.assertEqual(int(selected["id"]), int(ordinary["id"]))
        self.assertNotEqual(int(selected["id"]), int(close["id"]))

    def test_no_due_4h_work_preserves_earliest_future_pending_step(self) -> None:
        future = T1H + timedelta(hours=1)
        with self.fx.connection:
            rows = self.fx.connection.execute(
                """SELECT id,scheduler_job_id FROM printer_memory_factory_run_steps
                   WHERE run_id='factory-run-1' AND step_status='PENDING'
                     AND step_kind LIKE 'LONG_CONTINUATION_%'"""
            ).fetchall()
            for offset, row in enumerate(rows):
                stamp = _iso(future + timedelta(seconds=offset))
                self.fx.connection.execute(
                    "UPDATE printer_memory_factory_run_steps SET scheduled_for=? WHERE id=?",
                    (stamp, int(row["id"])),
                )
                self.fx.connection.execute(
                    "UPDATE printer_scheduler_jobs SET scheduled_for=? WHERE id=?",
                    (stamp, int(row["scheduler_job_id"])),
                )
        expected = self.fx.connection.execute(
            """SELECT * FROM printer_memory_factory_run_steps
               WHERE run_id='factory-run-1' AND step_status='PENDING'
               ORDER BY scheduled_for,id LIMIT 1"""
        ).fetchone()
        selected = self._selector(now=T1H)
        self.assertEqual(int(selected["id"]), int(expected["id"]))


if __name__ == "__main__":
    unittest.main()
