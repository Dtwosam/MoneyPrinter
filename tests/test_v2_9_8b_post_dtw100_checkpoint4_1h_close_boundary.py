"""Post-DTW100 Checkpoint 4: truthful first-hour close boundary."""

from __future__ import annotations

from datetime import timedelta
import unittest

from printer_v1.operator_cli import one_command_15m_factory as factory
from printer_v1.operator_cli.lane_e2o_1h_window_close import (
    E2O_1H_STATUS_BLOCKED,
    E2O_1H_STATUS_CREATED,
    close_1h_memory_window_from_snapshot,
)
from printer_v1.scheduler.scheduler import LockResult, claim_due_job
from printer_v1.snapshots.cadence_policy import (
    CADENCE_POLICY_BLOCKED,
    CADENCE_POLICY_DIRTY,
    CADENCE_POLICY_PASS,
    evaluate_cadence_policy,
    get_policy,
)
from tests.test_v2_9_8b_operational_selective_1h import (
    NOW,
    T15,
    T1H,
    Selective1hFixture,
    _iso,
)


class Checkpoint4FirstHourCloseBoundaryTests(unittest.TestCase):
    def _prepared_campaign(self) -> Selective1hFixture:
        fx = Selective1hFixture()
        fx.prepare_eligible(token_id=1, window_id=601, outcome="CONSOLIDATION")
        fx.prepare_eligible(token_id=2, window_id=602, outcome="NO_PUMP")
        with fx.connection:
            for token_id in (1, 2):
                fx.connection.execute(
                    """UPDATE printer_memory_factory_run_steps
                       SET snapshot_id=?
                       WHERE run_id='factory-run-1' AND token_id=?
                         AND step_kind='WINDOW_CLOSE'""",
                    (5000 + token_id, token_id),
                )
        factory._run_selective_1h_campaign_barrier(
            fx.connection,
            db_path=str(fx.db),
            run_id="factory-run-1",
            config={
                "campaign_id": "campaign-1h",
                "campaign_run_id": "run-1h",
                "cycle_id": "cycle-1h",
                "configuration_id": "config-1h",
            },
            continuation_seconds=2700.0,
        )
        return fx

    @staticmethod
    def _continuation_step(fx: Selective1hFixture, token_id: int, kind: str):
        row = fx.connection.execute(
            """SELECT * FROM printer_memory_factory_run_steps
               WHERE run_id='factory-run-1' AND token_id=? AND step_kind=?
               ORDER BY scheduled_for,id LIMIT 1""",
            (token_id, kind),
        ).fetchone()
        if row is None:
            raise AssertionError(f"missing {kind} for token {token_id}")
        return row

    @staticmethod
    def _campaign_window(fx: Selective1hFixture, token_id: int):
        row = fx.connection.execute(
            """SELECT * FROM printer_memory_factory_campaign_windows
               WHERE campaign_id='campaign-1h' AND run_id='run-1h'
                 AND cycle_id='cycle-1h' AND token_row_id=?
                 AND window_kind='WINDOW_1H'""",
            (token_id,),
        ).fetchone()
        if row is None:
            raise AssertionError(f"missing WINDOW_1H for token {token_id}")
        return row

    def test_close_claim_moves_exact_owned_window_to_close_pending(self) -> None:
        fx = self._prepared_campaign()
        try:
            snapshot = self._continuation_step(fx, 1, "CONTINUATION_SNAPSHOT")
            factory._mark_owned_continuation_window_collecting(
                fx.connection,
                scheduler_job_id=int(snapshot["scheduler_job_id"]),
                step_kind="CONTINUATION_SNAPSHOT",
            )
            self.assertEqual(str(self._campaign_window(fx, 1)["window_state"]), "COLLECTING")
            self.assertEqual(str(self._campaign_window(fx, 2)["window_state"]), "PLANNED")

            close = self._continuation_step(fx, 1, "CONTINUATION_CLOSE")
            claimed = claim_due_job(
                fx.connection,
                job_id=int(close["scheduler_job_id"]),
                lock_owner="checkpoint4-close",
                now=T1H,
            )
            self.assertEqual(claimed, LockResult.ACQUIRED)
            factory._update_step(fx.connection, int(close["id"]), "RUNNING", {})
            factory._sync_owned_campaign_scheduler_job(
                fx.connection, scheduler_job_id=int(close["scheduler_job_id"])
            )
            state = factory._mark_owned_continuation_window_close_pending(
                fx.connection,
                scheduler_job_id=int(close["scheduler_job_id"]),
                step_kind="CONTINUATION_CLOSE",
            )
            self.assertEqual(state, "CLOSE_PENDING")
            self.assertEqual(str(self._campaign_window(fx, 1)["window_state"]), "CLOSE_PENDING")
            self.assertEqual(str(self._campaign_window(fx, 2)["window_state"]), "PLANNED")
        finally:
            fx.close()

    def _insert_1h_snapshots(
        self,
        fx: Selective1hFixture,
        *,
        start_id: int,
        close_id: int,
        close_at,
    ) -> dict:
        with fx.connection:
            fx.connection.execute(
                """INSERT INTO printer_token_snapshots(
                    id,token_id,pair_id,captured_at,tracking_lane,snapshot_mode,
                    source_status,data_quality_label
                ) VALUES (?,1,1,?,'TRACK_NORMAL','TOKEN','COMPLETE','CLEAN_DATA')""",
                (start_id, _iso(T15)),
            )
            fx.connection.execute(
                """INSERT INTO printer_token_snapshots(
                    id,token_id,pair_id,captured_at,tracking_lane,snapshot_mode,
                    source_status,data_quality_label
                ) VALUES (?,1,1,?,'TRACK_NORMAL','TOKEN','COMPLETE','CLEAN_DATA')""",
                (close_id, _iso(close_at)),
            )
        predecessor = dict(
            fx.connection.execute(
                "SELECT * FROM printer_memory_windows WHERE id=601"
            ).fetchone()
        )
        predecessor.update(
            run_id="factory-run-1",
            tracking_lane="TRACK_NORMAL",
        )
        return predecessor

    def test_early_closing_snapshot_cannot_create_window_1h(self) -> None:
        fx = Selective1hFixture()
        try:
            fx.prepare_eligible(token_id=1, window_id=601)
            predecessor = self._insert_1h_snapshots(
                fx,
                start_id=8101,
                close_id=8102,
                close_at=T1H - timedelta(seconds=1),
            )
            result = close_1h_memory_window_from_snapshot(
                fx.connection,
                8102,
                "mint-1",
                snapshot_start_id=8101,
                expected_pair_id=1,
                continuation_of_15m=predecessor,
                consumed_15m_window_ids=[],
            )
            self.assertEqual(result["e2o_1h_status"], E2O_1H_STATUS_BLOCKED)
            self.assertTrue(
                any(
                    str(reason).startswith("closing_snapshot_precedes_fixed_deadline")
                    for reason in result["blocked_reasons"]
                )
            )
            count = int(
                fx.connection.execute(
                    "SELECT COUNT(*) FROM printer_memory_windows WHERE window_kind='WINDOW_1H'"
                ).fetchone()[0]
            )
            self.assertEqual(count, 0)
        finally:
            fx.close()

    def test_exact_deadline_close_reports_observed_lateness_and_binds_exact_row(self) -> None:
        fx = self._prepared_campaign()
        try:
            snapshot = self._continuation_step(fx, 1, "CONTINUATION_SNAPSHOT")
            factory._mark_owned_continuation_window_collecting(
                fx.connection,
                scheduler_job_id=int(snapshot["scheduler_job_id"]),
                step_kind="CONTINUATION_SNAPSHOT",
            )
            close_step = self._continuation_step(fx, 1, "CONTINUATION_CLOSE")
            factory._mark_owned_continuation_window_close_pending(
                fx.connection,
                scheduler_job_id=int(close_step["scheduler_job_id"]),
                step_kind="CONTINUATION_CLOSE",
            )
            predecessor = self._insert_1h_snapshots(
                fx,
                start_id=8201,
                close_id=8202,
                close_at=T1H,
            )
            result = close_1h_memory_window_from_snapshot(
                fx.connection,
                8202,
                "mint-1",
                snapshot_start_id=8201,
                expected_pair_id=1,
                continuation_of_15m=predecessor,
                consumed_15m_window_ids=[],
            )
            self.assertEqual(result["e2o_1h_status"], E2O_1H_STATUS_CREATED)
            self.assertEqual(result["closing_snapshot_lateness_seconds"], 0.0)
            memory_window_id = int(result["window_id"])
            factory._bind_owned_continuation_memory_window_at_close(
                fx.connection,
                scheduler_job_id=int(close_step["scheduler_job_id"]),
                memory_window_row_id=memory_window_id,
            )
            campaign = self._campaign_window(fx, 1)
            self.assertEqual(int(campaign["memory_window_row_id"]), memory_window_id)
            self.assertEqual(str(campaign["window_state"]), "NO_PROMOTION")
            slot_state = fx.connection.execute(
                """SELECT token_state FROM printer_memory_factory_campaign_token_slots
                   WHERE campaign_id='campaign-1h' AND run_id='run-1h'
                     AND cycle_id='cycle-1h' AND token_row_id=1"""
            ).fetchone()[0]
            self.assertEqual(str(slot_state), "WINDOW_1H_CLOSED")
        finally:
            fx.close()

    def test_window_1h_reuses_forced_closing_freshness_contract(self) -> None:
        policy = get_policy("WINDOW_1H", "TRACK_NORMAL")
        self.assertIsNotNone(policy)
        self.assertTrue(policy.require_full_anchored_duration)
        self.assertTrue(policy.require_forced_closing_snapshot)

        start = T15
        end = T1H
        interval = timedelta(seconds=240)
        base = [
            {"captured_at": _iso(start + interval * index)}
            for index in range(12)
        ]

        at_deadline = base + [{"captured_at": _iso(end)}]
        clean = evaluate_cadence_policy(
            at_deadline, _iso(start), _iso(end), policy, production_mode=True
        )
        self.assertEqual(clean.cadence_policy_status, CADENCE_POLICY_PASS)
        self.assertEqual(clean.closing_snapshot_lateness_seconds, 0.0)

        late_dirty = base + [{"captured_at": _iso(end + timedelta(seconds=61))}]
        dirty = evaluate_cadence_policy(
            late_dirty, _iso(start), _iso(end), policy, production_mode=True
        )
        self.assertEqual(dirty.cadence_policy_status, CADENCE_POLICY_DIRTY)

        late_blocked = base + [{"captured_at": _iso(end + timedelta(seconds=240))}]
        blocked = evaluate_cadence_policy(
            late_blocked, _iso(start), _iso(end), policy, production_mode=True
        )
        self.assertEqual(blocked.cadence_policy_status, CADENCE_POLICY_BLOCKED)


if __name__ == "__main__":
    unittest.main()
