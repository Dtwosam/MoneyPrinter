"""Post-DTW100 Checkpoint 6: first-hour lifecycle terminal reconciliation."""

from __future__ import annotations

import unittest

from printer_v1.operator_cli import one_command_15m_factory as factory
from printer_v1.operator_cli.lane_e2o_1h_window_close import (
    E2O_1H_STATUS_CREATED,
    close_1h_memory_window_from_snapshot,
)
from tests.test_v2_9_8b_post_dtw100_checkpoint4_1h_close_boundary import (
    Checkpoint4FirstHourCloseBoundaryTests,
)
from tests.test_v2_9_8b_operational_selective_1h import T1H


class Checkpoint6FirstHourTerminalReconciliationTests(unittest.TestCase):
    def _prepared_campaign(self):
        return Checkpoint4FirstHourCloseBoundaryTests()._prepared_campaign()

    @staticmethod
    def _continuation_step(fx, token_id: int, kind: str):
        return Checkpoint4FirstHourCloseBoundaryTests._continuation_step(
            fx, token_id, kind
        )

    @staticmethod
    def _campaign_window(fx, token_id: int):
        return Checkpoint4FirstHourCloseBoundaryTests._campaign_window(fx, token_id)

    def _physical_1h(self, fx, *, clean_episode: bool = False) -> tuple[object, int]:
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
        helper = Checkpoint4FirstHourCloseBoundaryTests()
        predecessor = helper._insert_1h_snapshots(
            fx,
            start_id=9101,
            close_id=9102,
            close_at=T1H,
        )
        close = close_1h_memory_window_from_snapshot(
            fx.connection,
            9102,
            "mint-1",
            snapshot_start_id=9101,
            expected_pair_id=1,
            continuation_of_15m=predecessor,
            consumed_15m_window_ids=[],
        )
        self.assertEqual(close["e2o_1h_status"], E2O_1H_STATUS_CREATED)
        memory_window_id = int(close["window_id"])
        if clean_episode:
            with fx.connection:
                fx.connection.execute(
                    """UPDATE printer_memory_windows
                       SET outcome_label='CONSOLIDATION'
                       WHERE id=?""",
                    (memory_window_id,),
                )
                fx.connection.execute(
                    """INSERT INTO printer_episodes(
                        memory_window_id,token_id,pair_id,episode_kind,
                        episode_status,memory_status,data_quality_label,do_not_train,
                        window_kind,memory_quality_label,episode_outcome_label
                    ) VALUES (?,1,1,'WINDOW_1H_CLEAN_MEMORY','COMPLETE','CLEAN_MEMORY',
                        'CLEAN_DATA',0,'WINDOW_1H','CLEAN_MEMORY','CONSOLIDATION')""",
                    (memory_window_id,),
                )
        return close_step, memory_window_id

    @staticmethod
    def _slot_state(fx, token_id: int) -> str:
        return str(
            fx.connection.execute(
                """SELECT token_state
                   FROM printer_memory_factory_campaign_token_slots
                   WHERE campaign_id='campaign-1h' AND run_id='run-1h'
                     AND cycle_id='cycle-1h' AND token_row_id=?""",
                (token_id,),
            ).fetchone()[0]
        )

    def test_clean_success_terminalizes_exact_window_and_closes_token(self) -> None:
        fx = self._prepared_campaign()
        try:
            close_step, memory_window_id = self._physical_1h(fx, clean_episode=True)
            factory._bind_owned_continuation_memory_window_at_close(
                fx.connection,
                scheduler_job_id=int(close_step["scheduler_job_id"]),
                memory_window_row_id=memory_window_id,
            )
            window = self._campaign_window(fx, 1)
            self.assertEqual(str(window["window_state"]), "CLEAN_PROMOTED")
            self.assertEqual(self._slot_state(fx, 1), "WINDOW_1H_CLOSED")
            self.assertEqual(str(self._campaign_window(fx, 2)["window_state"]), "PLANNED")
            self.assertEqual(self._slot_state(fx, 2), "WINDOW_1H_CONTINUING")
        finally:
            fx.close()

    def test_dirty_success_terminalizes_dirty_but_closes_token_normally(self) -> None:
        fx = self._prepared_campaign()
        try:
            close_step, memory_window_id = self._physical_1h(fx)
            with fx.connection:
                fx.connection.execute(
                    """UPDATE printer_memory_windows
                       SET memory_status='DIRTY_MEMORY',memory_quality_label='DIRTY_MEMORY',
                           data_quality_label='DIRTY_DATA',do_not_train=1
                       WHERE id=?""",
                    (memory_window_id,),
                )
            factory._bind_owned_continuation_memory_window_at_close(
                fx.connection,
                scheduler_job_id=int(close_step["scheduler_job_id"]),
                memory_window_row_id=memory_window_id,
            )
            self.assertEqual(str(self._campaign_window(fx, 1)["window_state"]), "DIRTY")
            self.assertEqual(self._slot_state(fx, 1), "WINDOW_1H_CLOSED")
        finally:
            fx.close()

    def test_clean_data_without_clean_object_terminalizes_no_promotion(self) -> None:
        fx = self._prepared_campaign()
        try:
            close_step, memory_window_id = self._physical_1h(fx)
            factory._bind_owned_continuation_memory_window_at_close(
                fx.connection,
                scheduler_job_id=int(close_step["scheduler_job_id"]),
                memory_window_row_id=memory_window_id,
            )
            self.assertEqual(
                str(self._campaign_window(fx, 1)["window_state"]), "NO_PROMOTION"
            )
            self.assertEqual(self._slot_state(fx, 1), "WINDOW_1H_CLOSED")
        finally:
            fx.close()

    def test_token_local_failure_blocks_window_and_fails_only_exact_slot(self) -> None:
        fx = self._prepared_campaign()
        try:
            snapshot = self._continuation_step(fx, 1, "CONTINUATION_SNAPSHOT")
            factory._mark_owned_continuation_window_collecting(
                fx.connection,
                scheduler_job_id=int(snapshot["scheduler_job_id"]),
                step_kind="CONTINUATION_SNAPSHOT",
            )
            factory._terminalize_owned_continuation_window(
                fx.connection,
                scheduler_job_id=int(snapshot["scheduler_job_id"]),
                terminal_state="BLOCKED",
                terminal_cause="checkpoint6-token-local-failure",
            )
            window = self._campaign_window(fx, 1)
            self.assertEqual(str(window["window_state"]), "BLOCKED")
            self.assertEqual(self._slot_state(fx, 1), "FAILED")
            self.assertEqual(str(self._campaign_window(fx, 2)["window_state"]), "PLANNED")
            self.assertEqual(self._slot_state(fx, 2), "WINDOW_1H_CONTINUING")
        finally:
            fx.close()

    def test_runwide_cancel_sends_only_active_first_hour_slots_to_manual_review(self) -> None:
        fx = self._prepared_campaign()
        try:
            snapshot = self._continuation_step(fx, 1, "CONTINUATION_SNAPSHOT")
            factory._mark_owned_continuation_window_collecting(
                fx.connection,
                scheduler_job_id=int(snapshot["scheduler_job_id"]),
                step_kind="CONTINUATION_SNAPSHOT",
            )
            peer = self._campaign_window(fx, 2)
            with fx.connection:
                fx.connection.execute(
                    """UPDATE printer_memory_factory_campaign_windows
                       SET window_state='NO_PROMOTION',first_terminal_cause='peer-complete',
                           terminal_at=?,updated_at=? WHERE window_id=?""",
                    (str(T1H.isoformat()), str(T1H.isoformat()), str(peer["window_id"])),
                )
                fx.connection.execute(
                    """UPDATE printer_memory_factory_campaign_token_slots
                       SET token_state='WINDOW_1H_CLOSED',updated_at=?
                       WHERE campaign_id='campaign-1h' AND run_id='run-1h'
                         AND cycle_id='cycle-1h' AND token_row_id=2""",
                    (str(T1H.isoformat()),),
                )
            changed = factory._cancel_owned_continuation_windows_for_run(
                fx.connection,
                factory_run_id="factory-run-1",
                terminal_cause="SAFE_STOP_CHECKPOINT6",
            )
            self.assertEqual(changed, 1)
            self.assertEqual(str(self._campaign_window(fx, 1)["window_state"]), "CANCELLED")
            self.assertEqual(self._slot_state(fx, 1), "MANUAL_REVIEW")
            peer_after = self._campaign_window(fx, 2)
            self.assertEqual(str(peer_after["window_state"]), "NO_PROMOTION")
            self.assertEqual(str(peer_after["first_terminal_cause"]), "peer-complete")
            self.assertEqual(self._slot_state(fx, 2), "WINDOW_1H_CLOSED")
        finally:
            fx.close()

    def test_exact_success_repeat_is_idempotent(self) -> None:
        fx = self._prepared_campaign()
        try:
            close_step, memory_window_id = self._physical_1h(fx, clean_episode=True)
            first = factory._bind_owned_continuation_memory_window_at_close(
                fx.connection,
                scheduler_job_id=int(close_step["scheduler_job_id"]),
                memory_window_row_id=memory_window_id,
            )
            first_window = self._campaign_window(fx, 1)
            second = factory._bind_owned_continuation_memory_window_at_close(
                fx.connection,
                scheduler_job_id=int(close_step["scheduler_job_id"]),
                memory_window_row_id=memory_window_id,
            )
            second_window = self._campaign_window(fx, 1)
            self.assertEqual(first, second)
            self.assertEqual(str(second_window["window_state"]), "CLEAN_PROMOTED")
            self.assertEqual(
                str(second_window["first_terminal_cause"]),
                str(first_window["first_terminal_cause"]),
            )
            self.assertEqual(self._slot_state(fx, 1), "WINDOW_1H_CLOSED")
        finally:
            fx.close()

    def test_conflicting_memory_identity_still_fails_before_lifecycle_terminalization(self) -> None:
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
            with fx.connection:
                fx.connection.execute(
                    """INSERT INTO printer_memory_windows(
                        id,token_id,pair_id,window_kind,opened_at,closed_at,
                        memory_status,data_quality_label,window_status,
                        memory_quality_label,do_not_train,supporting_context_json
                    ) VALUES (9991,2,2,'WINDOW_1H',?,?,'PARTIAL_MEMORY','CLEAN_DATA',
                        'WINDOW_CLOSED','PARTIAL_MEMORY',0,'{}')""",
                    (str(T1H.isoformat()), str(T1H.isoformat())),
                )
            with self.assertRaises(Exception):
                factory._bind_owned_continuation_memory_window_at_close(
                    fx.connection,
                    scheduler_job_id=int(close_step["scheduler_job_id"]),
                    memory_window_row_id=9991,
                )
            self.assertEqual(
                str(self._campaign_window(fx, 1)["window_state"]), "CLOSE_PENDING"
            )
            self.assertEqual(self._slot_state(fx, 1), "WINDOW_1H_CONTINUING")
        finally:
            fx.close()


if __name__ == "__main__":
    unittest.main()
