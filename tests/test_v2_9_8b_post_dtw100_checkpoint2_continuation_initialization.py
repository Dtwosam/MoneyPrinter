"""Post-DTW100 Checkpoint 2: exact WINDOW_1H continuation initialization."""

from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timedelta
import unittest

from printer_v1.operator_cli import one_command_15m_factory as factory
from printer_v1.operator_cli.operational_selective_1h import Selective1hError
from tests.test_v2_9_8b_operational_selective_1h import (
    NOW,
    Selective1hFixture,
)


class Checkpoint2ContinuationInitializationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.fx = Selective1hFixture()
        self.config = {
            "campaign_id": "campaign-1h",
            "campaign_run_id": "run-1h",
            "cycle_id": "cycle-1h",
            "configuration_id": "config-1h",
        }

    def tearDown(self) -> None:
        self.fx.close()

    def _prepare_both(self) -> None:
        self.fx.prepare_eligible(token_id=1, window_id=401, outcome="CONSOLIDATION")
        self.fx.prepare_eligible(token_id=2, window_id=402, outcome="NO_PUMP")

    def test_real_barrier_initializes_exact_owned_45m_schedule_for_both_tokens(self) -> None:
        self._prepare_both()

        result = factory._run_selective_1h_campaign_barrier(
            self.fx.connection,
            db_path=str(self.fx.db),
            run_id="factory-run-1",
            config=self.config,
            continuation_seconds=2700.0,
        )
        self.assertTrue(result["evaluation_reached"])
        self.assertTrue(result["evaluation_created"])
        self.assertEqual(result["evaluation"]["continue_count"], 2)

        plans = {
            str(plan["token_slot_id"]): plan
            for plan in result["evaluation"]["token_plans"]
        }
        self.assertEqual(set(plans), {"slot-1", "slot-2"})
        self.assertTrue(all(plan["campaign_window_1h_id"] for plan in plans.values()))

        steps = self.fx.connection.execute(
            """SELECT id,step_key,step_kind,token_id,pair_id,tracking_lane,
                      scheduled_for,scheduler_job_id
               FROM printer_memory_factory_run_steps
               WHERE run_id='factory-run-1'
                 AND step_kind IN ('CONTINUATION_SNAPSHOT','CONTINUATION_CLOSE')
               ORDER BY token_id,scheduled_for,id"""
        ).fetchall()
        self.assertEqual(len(steps), 26)  # 13 per TRACK_NORMAL token.

        close_at = datetime.fromisoformat(NOW)
        one_hour_close = close_at + timedelta(seconds=2700)
        for token_id in (1, 2):
            token_steps = [row for row in steps if int(row["token_id"]) == token_id]
            self.assertEqual(len(token_steps), 13)
            self.assertEqual(str(token_steps[0]["step_kind"]), "CONTINUATION_SNAPSHOT")
            self.assertEqual(
                datetime.fromisoformat(str(token_steps[0]["scheduled_for"])),
                close_at,
            )
            self.assertEqual(str(token_steps[-1]["step_kind"]), "CONTINUATION_CLOSE")
            self.assertEqual(
                datetime.fromisoformat(str(token_steps[-1]["scheduled_for"])),
                one_hour_close,
            )
            self.assertTrue(all(str(row["tracking_lane"]) == "TRACK_NORMAL" for row in token_steps))

        owned = self.fx.connection.execute(
            """SELECT scheduler_work_id,campaign_id,run_id,cycle_id,token_slot_id,
                      window_id,work_intent,deadline_at,work_state,scheduler_job_id,
                      ownership_contract_version,stage_id,work_scope,target_category,
                      target_identity,factory_run_id
               FROM printer_memory_factory_campaign_scheduler_work
               WHERE ownership_contract_version='V2_STAGE_SCOPED'
                 AND work_scope='WINDOW_LIFECYCLE'
               ORDER BY scheduler_job_id"""
        ).fetchall()
        self.assertEqual(len(owned), len(steps))
        owned_by_job = {int(row["scheduler_job_id"]): row for row in owned}
        self.assertEqual(len(owned_by_job), len(steps))

        for step in steps:
            job_id = int(step["scheduler_job_id"])
            self.assertIn(job_id, owned_by_job)
            row = owned_by_job[job_id]
            slot_id = f"slot-{int(step['token_id'])}"
            self.assertEqual(str(row["campaign_id"]), "campaign-1h")
            self.assertEqual(str(row["run_id"]), "run-1h")
            self.assertEqual(str(row["cycle_id"]), "cycle-1h")
            self.assertEqual(str(row["token_slot_id"]), slot_id)
            self.assertEqual(str(row["window_id"]), str(plans[slot_id]["campaign_window_1h_id"]))
            self.assertEqual(str(row["target_identity"]), str(row["window_id"]))
            self.assertEqual(str(row["target_category"]), "CAMPAIGN_WINDOW")
            self.assertEqual(str(row["work_scope"]), "WINDOW_LIFECYCLE")
            self.assertEqual(str(row["ownership_contract_version"]), "V2_STAGE_SCOPED")
            self.assertEqual(str(row["factory_run_id"]), "factory-run-1")
            self.assertEqual(str(row["deadline_at"]), str(step["scheduled_for"]))
            self.assertEqual(str(row["work_state"]), "PENDING")

    def test_missing_exact_successor_id_fails_before_continuation_scheduler_jobs(self) -> None:
        self._prepare_both()
        evaluation = self.fx.evaluate()
        broken = deepcopy(evaluation)
        for plan in broken["token_plans"]:
            if int(plan["token_row_id"]) == 1:
                plan["campaign_window_1h_id"] = None

        close_step = self.fx.connection.execute(
            """SELECT * FROM printer_memory_factory_run_steps
               WHERE run_id='factory-run-1' AND token_id=1
                 AND step_kind='WINDOW_CLOSE'
               ORDER BY id LIMIT 1"""
        ).fetchone()
        self.assertIsNotNone(close_step)
        before = int(self.fx.connection.execute(
            """SELECT COUNT(*) FROM printer_memory_factory_run_steps
               WHERE run_id='factory-run-1'
                 AND step_kind IN ('CONTINUATION_SNAPSHOT','CONTINUATION_CLOSE')"""
        ).fetchone()[0])

        with self.assertRaises((Selective1hError, ValueError)):
            factory._selective_1h_schedule_for_close(
                self.fx.connection,
                run_id="factory-run-1",
                close_step=close_step,
                window_id=401,
                continuation_seconds=2700.0,
                evaluation=broken,
            )

        after = int(self.fx.connection.execute(
            """SELECT COUNT(*) FROM printer_memory_factory_run_steps
               WHERE run_id='factory-run-1'
                 AND step_kind IN ('CONTINUATION_SNAPSHOT','CONTINUATION_CLOSE')"""
        ).fetchone()[0])
        self.assertEqual(after, before)


if __name__ == "__main__":
    unittest.main()
