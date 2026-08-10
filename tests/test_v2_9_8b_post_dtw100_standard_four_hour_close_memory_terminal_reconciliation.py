"""Offline TDD for standard two-token 4h close/memory/campaign terminal composition."""

from __future__ import annotations

from datetime import timedelta
import json
import unittest

from printer_v1.memory.clean_object_promotion import promote_clean_object
from printer_v1.operator_cli import one_command_15m_factory as factory
from printer_v1.operator_cli import one_token_4h_runtime
from tests.test_v2_9_8b_post_dtw100_standard_four_hour_campaign_planning import (
    StandardFourHourCampaignPlanningTests,
)
from tests.test_v2_9_8b_operational_selective_1h import T1H, _iso


class StandardFourHourCloseMemoryTerminalTests(unittest.TestCase):
    def setUp(self) -> None:
        helper = StandardFourHourCampaignPlanningTests()
        self.fx, self.candidates = helper._prepared()
        result = helper._plan(self.fx, self.candidates)
        self.assertTrue(result["planned"])
        self.assertFalse(result["replay"])

    def tearDown(self) -> None:
        self.fx.close()

    def _candidate(self, token_id: int) -> dict:
        return next(
            dict(item)
            for item in self.candidates
            if int(item["token_row_id"]) == int(token_id)
        )

    def _window(self, token_id: int):
        row = self.fx.connection.execute(
            """SELECT w.*,s.token_state
               FROM printer_memory_factory_campaign_windows AS w
               JOIN printer_memory_factory_campaign_token_slots AS s
                 ON s.token_slot_id=w.token_slot_id
                AND s.campaign_id=w.campaign_id
                AND s.run_id=w.run_id
                AND s.cycle_id=w.cycle_id
               WHERE w.campaign_id='campaign-1h' AND w.run_id='run-1h'
                 AND w.cycle_id='cycle-1h' AND w.token_row_id=?
                 AND w.window_kind='WINDOW_4H'""",
            (int(token_id),),
        ).fetchone()
        self.assertIsNotNone(row)
        return row

    def _close_step(self, token_id: int):
        row = self.fx.connection.execute(
            """SELECT * FROM printer_memory_factory_run_steps
               WHERE run_id='factory-run-1' AND token_id=?
                 AND step_kind='LONG_CONTINUATION_CLOSE'""",
            (int(token_id),),
        ).fetchone()
        self.assertIsNotNone(row)
        return row

    def _set_close_pending(self, token_id: int) -> None:
        window = self._window(token_id)
        with self.fx.connection:
            self.fx.connection.execute(
                """UPDATE printer_memory_factory_campaign_windows
                   SET window_state='CLOSE_PENDING',updated_at=?
                   WHERE window_id=?""",
                (_iso(T1H), str(window["window_id"])),
            )

    def _insert_physical_4h(
        self,
        token_id: int,
        *,
        clean: bool = True,
        pair_id: int | None = None,
        window_kind: str = "WINDOW_4H",
    ) -> int:
        candidate = self._candidate(token_id)
        actual_pair = int(candidate["pair_row_id"]) if pair_id is None else int(pair_id)
        lane = str(candidate["tracking_lane"])
        start_id = 20000 + token_id * 10
        end_id = start_id + 1
        memory_id = 21000 + token_id
        end_at = T1H + timedelta(seconds=10_800)
        with self.fx.connection:
            for snapshot_id, captured_at in ((start_id, T1H), (end_id, end_at)):
                self.fx.connection.execute(
                    """INSERT INTO printer_token_snapshots(
                        id,token_id,pair_id,captured_at,tracking_lane,snapshot_mode,
                        source_status,data_quality_label
                    ) VALUES (?,?,?,?,?,'TOKEN','COMPLETE','CLEAN_DATA')""",
                    (snapshot_id, token_id, actual_pair, _iso(captured_at), lane),
                )
            context = {
                "snapshot_id": end_id,
                "tracking_lane": lane,
                "run_id": "factory-run-1",
                "continuation_of_window_id": 13000 + token_id,
                "linked_closing_snapshot_id": 12000 + token_id * 10 + 1,
                "linked_first_snapshot_id": start_id,
                "fixed_deadline_at": _iso(end_at),
                "continuity_status": "CONTINUITY_CLEAN",
                "e2q_audited": True,
                "e2q_audited_by": "lane_e2q",
                "shared_window_4h_context_evidence": {
                    "clean_memory_context_ready": bool(clean),
                },
            }
            self.fx.connection.execute(
                """INSERT INTO printer_memory_windows(
                    id,token_id,pair_id,window_kind,opened_at,closed_at,
                    window_start_at,window_end_at,snapshot_start_id,snapshot_end_id,
                    memory_status,data_quality_label,window_status,memory_quality_label,
                    outcome_label,do_not_train,supporting_context_json
                ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (
                    memory_id,
                    token_id,
                    actual_pair,
                    window_kind,
                    _iso(T1H),
                    _iso(end_at),
                    _iso(T1H),
                    _iso(end_at),
                    start_id,
                    end_id,
                    "PARTIAL_MEMORY" if clean else "DIRTY_MEMORY",
                    "CLEAN_DATA" if clean else "DIRTY_DATA",
                    "WINDOW_CLOSED",
                    "PARTIAL_MEMORY" if clean else "DIRTY_MEMORY",
                    "CONSOLIDATION",
                    0 if clean else 1,
                    json.dumps(context, sort_keys=True),
                ),
            )
        return memory_id

    @staticmethod
    def _pipeline(e2z_status: str | None) -> dict:
        memory = None if e2z_status is None else {"e2z_status": e2z_status}
        return {
            "memory_pipeline": {
                "lane_k_status": (
                    "LANE_K_COMPLETED" if e2z_status is not None else "LANE_K_BLOCKED"
                ),
                "memory": memory,
            }
        }

    def _promote(self, memory_id: int) -> tuple[int, int]:
        result = promote_clean_object(self.fx.connection, window_id=int(memory_id))
        self.fx.connection.commit()
        return int(result.episode_id), int(result.fingerprint_id)

    def _binder(self):
        binder = getattr(factory, "_bind_owned_long_memory_window_at_close", None)
        self.assertIsNotNone(binder, "successful WINDOW_4H campaign binding owner is missing")
        return binder

    def _reconciler(self):
        reconciler = getattr(one_token_4h_runtime, "reconcile_4h_terminal_lifecycle", None)
        self.assertIsNotNone(reconciler, "successful WINDOW_4H terminal reconciler is missing")
        return reconciler

    def _validator(self):
        validator = getattr(factory, "_standard_campaign_four_hour_terminal_validation", None)
        self.assertIsNotNone(validator, "standard two-window WINDOW_4H terminal validator is missing")
        return validator

    def test_clean_created_binds_exact_window_and_closes_only_its_slot(self) -> None:
        self._set_close_pending(1)
        memory_id = self._insert_physical_4h(1, clean=True)
        self._promote(memory_id)
        close = self._close_step(1)
        result = self._binder()(
            self.fx.connection,
            scheduler_job_id=int(close["scheduler_job_id"]),
            memory_window_row_id=memory_id,
            result=self._pipeline("E2Z_MEMORY_CREATED"),
        )
        self.fx.connection.commit()
        self.assertEqual(result["window_state"], "CLEAN_PROMOTED")
        token1 = self._window(1)
        token2 = self._window(2)
        self.assertEqual(str(token1["window_state"]), "CLEAN_PROMOTED")
        self.assertEqual(str(token1["token_state"]), "WINDOW_4H_CLOSED")
        self.assertEqual(int(token1["memory_window_row_id"]), memory_id)
        self.assertEqual(str(token2["window_state"]), "PLANNED")
        self.assertEqual(str(token2["token_state"]), "WINDOW_4H_CONTINUING")

    def test_existing_clean_object_replay_is_idempotent_without_duplicate_object(self) -> None:
        self._set_close_pending(1)
        memory_id = self._insert_physical_4h(1, clean=True)
        self._promote(memory_id)
        before = (
            int(self.fx.connection.execute(
                "SELECT COUNT(*) FROM printer_episodes WHERE memory_window_id=?",
                (memory_id,),
            ).fetchone()[0]),
            int(self.fx.connection.execute(
                """SELECT COUNT(*) FROM printer_memory_fingerprints f
                   JOIN printer_episodes e ON e.id=f.episode_id
                   WHERE e.memory_window_id=?""",
                (memory_id,),
            ).fetchone()[0]),
        )
        close = self._close_step(1)
        binder = self._binder()
        first = binder(
            self.fx.connection,
            scheduler_job_id=int(close["scheduler_job_id"]),
            memory_window_row_id=memory_id,
            result=self._pipeline("E2Z_ALREADY_EXISTS"),
        )
        second = binder(
            self.fx.connection,
            scheduler_job_id=int(close["scheduler_job_id"]),
            memory_window_row_id=memory_id,
            result=self._pipeline("E2Z_ALREADY_EXISTS"),
        )
        self.fx.connection.commit()
        self.assertEqual(first["window_state"], "ALREADY_EXISTS_IDEMPOTENT")
        self.assertTrue(second["idempotent"])
        after = (
            int(self.fx.connection.execute(
                "SELECT COUNT(*) FROM printer_episodes WHERE memory_window_id=?",
                (memory_id,),
            ).fetchone()[0]),
            int(self.fx.connection.execute(
                """SELECT COUNT(*) FROM printer_memory_fingerprints f
                   JOIN printer_episodes e ON e.id=f.episode_id
                   WHERE e.memory_window_id=?""",
                (memory_id,),
            ).fetchone()[0]),
        )
        self.assertEqual(before, after)

    def test_dirty_and_clean_no_object_are_distinct_terminal_outcomes(self) -> None:
        binder = self._binder()
        for token_id, clean, expected in (
            (1, False, "DIRTY"),
            (2, True, "NO_PROMOTION"),
        ):
            self._set_close_pending(token_id)
            memory_id = self._insert_physical_4h(token_id, clean=clean)
            close = self._close_step(token_id)
            result = binder(
                self.fx.connection,
                scheduler_job_id=int(close["scheduler_job_id"]),
                memory_window_row_id=memory_id,
                result=self._pipeline(None),
            )
            self.assertEqual(result["window_state"], expected)
            self.assertEqual(str(self._window(token_id)["token_state"]), "WINDOW_4H_CLOSED")
        self.fx.connection.commit()
        self.assertEqual(
            int(self.fx.connection.execute(
                """SELECT COUNT(*) FROM printer_episodes
                   WHERE window_kind='WINDOW_4H' AND memory_status='CLEAN_MEMORY'"""
            ).fetchone()[0]),
            0,
        )

    def test_physical_identity_mismatch_fails_before_campaign_terminalization(self) -> None:
        self._set_close_pending(1)
        memory_id = self._insert_physical_4h(1, clean=True, pair_id=2)
        close = self._close_step(1)
        with self.assertRaises(Exception):
            self._binder()(
                self.fx.connection,
                scheduler_job_id=int(close["scheduler_job_id"]),
                memory_window_row_id=memory_id,
                result=self._pipeline(None),
            )
        row = self._window(1)
        self.assertEqual(str(row["window_state"]), "CLOSE_PENDING")
        self.assertEqual(str(row["token_state"]), "WINDOW_4H_CONTINUING")
        self.assertIsNone(row["memory_window_row_id"])

    def test_success_reconciler_does_not_commit_callers_outer_transaction(self) -> None:
        self._set_close_pending(1)
        memory_id = self._insert_physical_4h(1, clean=True)
        window_id = str(self._window(1)["window_id"])
        self.fx.connection.execute("BEGIN")
        self._reconciler()(
            self.fx.connection,
            campaign_window_4h_id=window_id,
            terminal_state="NO_PROMOTION",
            terminal_cause="window_4h_closed_no_promotion",
            memory_window_row_id=memory_id,
            now=_iso(T1H + timedelta(seconds=10_801)),
        )
        in_tx = self.fx.connection.in_transaction
        self.fx.connection.rollback()
        row = self._window(1)
        self.assertTrue(in_tx)
        self.assertEqual(str(row["window_state"]), "CLOSE_PENDING")
        self.assertEqual(str(row["token_state"]), "WINDOW_4H_CONTINUING")
        self.assertIsNone(row["memory_window_row_id"])

    def test_conflicting_success_replay_fails_closed(self) -> None:
        self._set_close_pending(1)
        memory_id = self._insert_physical_4h(1, clean=True)
        self._promote(memory_id)
        close = self._close_step(1)
        binder = self._binder()
        binder(
            self.fx.connection,
            scheduler_job_id=int(close["scheduler_job_id"]),
            memory_window_row_id=memory_id,
            result=self._pipeline("E2Z_MEMORY_CREATED"),
        )
        with self.assertRaises(Exception):
            binder(
                self.fx.connection,
                scheduler_job_id=int(close["scheduler_job_id"]),
                memory_window_row_id=memory_id,
                result=self._pipeline("E2Z_ALREADY_EXISTS"),
            )

    def _complete_standard_long_work(self) -> dict[int, int]:
        """Make all 92 planned long jobs/snapshots terminal without source execution."""
        memory_ids: dict[int, int] = {}
        next_snapshot_id = 30000
        rows = self.fx.connection.execute(
            """SELECT * FROM printer_memory_factory_run_steps
               WHERE run_id='factory-run-1' AND step_kind LIKE 'LONG_CONTINUATION_%'
               ORDER BY scheduled_for,id"""
        ).fetchall()
        for row in rows:
            next_snapshot_id += 1
            captured = str(row["scheduled_for"])
            self.fx.connection.execute(
                """INSERT INTO printer_token_snapshots(
                    id,token_id,pair_id,captured_at,tracking_lane,snapshot_mode,
                    source_status,data_quality_label
                ) VALUES (?,?,?,?,?,'TOKEN','COMPLETE','CLEAN_DATA')""",
                (
                    next_snapshot_id,
                    int(row["token_id"]),
                    int(row["pair_id"]),
                    captured,
                    str(row["tracking_lane"]),
                ),
            )
            self.fx.connection.execute(
                """UPDATE printer_memory_factory_run_steps
                   SET step_status='SUCCEEDED',snapshot_id=?,started_at=?,finished_at=?,updated_at=?
                   WHERE id=?""",
                (next_snapshot_id, captured, captured, captured, int(row["id"])),
            )
            self.fx.connection.execute(
                """UPDATE printer_scheduler_jobs
                   SET status='SUCCEEDED',started_at=?,finished_at=?,updated_at=?,
                       locked_at=NULL,lock_owner=NULL
                   WHERE id=?""",
                (captured, captured, captured, int(row["scheduler_job_id"])),
            )
            factory._sync_owned_campaign_scheduler_job(
                self.fx.connection, scheduler_job_id=int(row["scheduler_job_id"])
            )
        self.fx.connection.commit()

        for token_id in (1, 2):
            self._set_close_pending(token_id)
            memory_id = self._insert_physical_4h(token_id, clean=(token_id == 1))
            memory_ids[token_id] = memory_id
            close = self._close_step(token_id)
            if token_id == 1:
                self._promote(memory_id)
                pipeline = self._pipeline("E2Z_MEMORY_CREATED")
            else:
                pipeline = self._pipeline(None)
            self._binder()(
                self.fx.connection,
                scheduler_job_id=int(close["scheduler_job_id"]),
                memory_window_row_id=memory_id,
                result=pipeline,
            )
            self.fx.connection.execute(
                """UPDATE printer_memory_factory_run_steps
                   SET memory_window_id=?,result_json=?,updated_at=? WHERE id=?""",
                (
                    memory_id,
                    json.dumps({**pipeline, "memory_window_id": memory_id}, sort_keys=True),
                    _iso(T1H + timedelta(seconds=10_801)),
                    int(close["id"]),
                ),
            )
        self.fx.connection.commit()
        return memory_ids

    def test_standard_validator_accepts_mixed_lane_two_window_terminal_set(self) -> None:
        self._complete_standard_long_work()
        report = self._validator()(
            self.fx.connection,
            factory_run_id="factory-run-1",
            campaign_id="campaign-1h",
            run_id="run-1h",
            cycle_id="cycle-1h",
        )
        self.assertTrue(report["enabled"])
        self.assertTrue(report["complete"], report.get("reasons"))
        by_token = {int(row["token_id"]): row for row in report["per_token"]}
        self.assertEqual(int(by_token[1]["expected_snapshots"]), 61)
        self.assertEqual(int(by_token[2]["expected_snapshots"]), 31)
        self.assertEqual(by_token[1]["window_state"], "CLEAN_PROMOTED")
        self.assertEqual(by_token[2]["window_state"], "DIRTY")
        self.assertEqual(report["active_owned_four_hour_work"], 0)
        self.assertEqual(report["nonterminal_owned_four_hour_windows"], 0)

    def test_standard_validator_rejects_missing_close_identity(self) -> None:
        self._complete_standard_long_work()
        close = self._close_step(2)
        with self.fx.connection:
            self.fx.connection.execute(
                "DELETE FROM printer_memory_factory_campaign_scheduler_work WHERE scheduler_job_id=?",
                (int(close["scheduler_job_id"]),),
            )
        report = self._validator()(
            self.fx.connection,
            factory_run_id="factory-run-1",
            campaign_id="campaign-1h",
            run_id="run-1h",
            cycle_id="cycle-1h",
        )
        self.assertTrue(report["enabled"])
        self.assertFalse(report["complete"])
        self.assertTrue(any("close" in str(reason).lower() for reason in report["reasons"]))


if __name__ == "__main__":
    unittest.main()
