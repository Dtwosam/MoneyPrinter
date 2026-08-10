"""Offline TDD for two-token 4h planning + exact Scheduler ownership."""

from __future__ import annotations

from unittest.mock import patch
import json
import unittest

from printer_v1.operator_cli import campaign_ownership, one_token_4h_runtime
from printer_v1.operator_cli.campaign_ownership import CampaignOwnershipError
from tests.test_v2_9_8b_post_dtw100_standard_four_hour_campaign_handoff import (
    StandardFourHourCampaignHandoffTests,
)
from tests.test_v2_9_8b_operational_selective_1h import T1H, _iso


class StandardFourHourCampaignPlanningTests(unittest.TestCase):
    def _prepared(self):
        helper = StandardFourHourCampaignHandoffTests()
        fx = helper._prepared_closed_first_hour()
        candidates = helper._candidates(fx)
        authoritative = fx.connection.execute(
            """SELECT authoritative_run_id
               FROM printer_memory_factory_campaign_runs
               WHERE campaign_id='campaign-1h' AND run_id='run-1h'"""
        ).fetchone()
        self.assertIsNotNone(authoritative)
        self.assertEqual(str(authoritative[0]), "factory-run-1")
        return fx, candidates

    def _plan(self, fx, candidates):
        planner = getattr(
            one_token_4h_runtime,
            "plan_standard_campaign_4h_handoff",
            None,
        )
        self.assertIsNotNone(
            planner,
            "two-token standard four-hour planning/Scheduler ownership owner is missing",
        )
        return planner(
            fx.connection,
            campaign_id="campaign-1h",
            run_id="run-1h",
            cycle_id="cycle-1h",
            factory_run_id="factory-run-1",
            candidates=candidates,
            execution_authority=(
                one_token_4h_runtime.FourHourExecutionAuthority.STANDARD_CAMPAIGN
            ),
            now=_iso(T1H),
        )

    def test_enabled_cadence_without_standard_authority_fails_closed(self) -> None:
        fx, candidates = self._prepared()
        try:
            planner = one_token_4h_runtime.plan_standard_campaign_4h_handoff
            with self.assertRaisesRegex(ValueError, "explicit STANDARD_CAMPAIGN authority"):
                planner(
                    fx.connection,
                    campaign_id="campaign-1h",
                    run_id="run-1h",
                    cycle_id="cycle-1h",
                    factory_run_id="factory-run-1",
                    candidates=candidates,
                    now=_iso(T1H),
                )
            self.assertEqual(
                int(fx.connection.execute(
                    "SELECT COUNT(*) FROM printer_memory_factory_campaign_windows WHERE window_kind='WINDOW_4H'"
                ).fetchone()[0]),
                0,
            )
        finally:
            fx.close()

    def test_mixed_fast_normal_plans_exact_two_token_long_work_and_ownership(self) -> None:
        fx, candidates = self._prepared()
        try:
            budget = one_token_4h_runtime.standard_two_token_lifecycle_budget(
                ("TRACK_FAST", "TRACK_NORMAL")
            )
            self.assertEqual(int(budget["request_ceiling"]), 182)
            self.assertEqual(int(budget["scheduler_ceiling"]), 162)
            self.assertTrue(bool(budget["real_collection_enabled"]))

            result = self._plan(fx, candidates)
            self.assertTrue(result["planned"])
            self.assertFalse(result["replay"])
            self.assertEqual(int(result["planned_jobs"]), 92)
            self.assertEqual(
                result["planned_by_slot"], {"slot-1": 61, "slot-2": 31}
            )

            steps = fx.connection.execute(
                """SELECT token_id,COUNT(*) AS total,
                          SUM(CASE WHEN step_kind='LONG_CONTINUATION_CLOSE' THEN 1 ELSE 0 END) AS closes,
                          COUNT(DISTINCT scheduler_job_id) AS jobs
                   FROM printer_memory_factory_run_steps
                   WHERE run_id='factory-run-1'
                     AND step_kind LIKE 'LONG_CONTINUATION_%'
                   GROUP BY token_id ORDER BY token_id"""
            ).fetchall()
            self.assertEqual(
                [(int(r[0]), int(r[1]), int(r[2]), int(r[3])) for r in steps],
                [(1, 61, 1, 61), (2, 31, 1, 31)],
            )

            owned = fx.connection.execute(
                """SELECT rs.token_id,COUNT(*) AS total,
                          SUM(CASE WHEN cw.work_intent=rs.step_kind THEN 1 ELSE 0 END) AS intent_matches,
                          COUNT(DISTINCT cw.scheduler_job_id) AS jobs
                   FROM printer_memory_factory_campaign_scheduler_work AS cw
                   JOIN printer_memory_factory_run_steps AS rs
                     ON rs.scheduler_job_id=cw.scheduler_job_id
                   WHERE cw.campaign_id='campaign-1h' AND cw.run_id='run-1h'
                     AND cw.cycle_id='cycle-1h'
                     AND cw.ownership_contract_version='V2_STAGE_SCOPED'
                     AND cw.work_scope='WINDOW_LIFECYCLE'
                     AND cw.stage_id='WINDOW_4H'
                     AND cw.target_category='CAMPAIGN_WINDOW'
                     AND cw.factory_run_id='factory-run-1'
                   GROUP BY rs.token_id ORDER BY rs.token_id"""
            ).fetchall()
            self.assertEqual(
                [(int(r[0]), int(r[1]), int(r[2]), int(r[3])) for r in owned],
                [(1, 61, 61, 61), (2, 31, 31, 31)],
            )

            for candidate, expected in zip(candidates, (61, 31), strict=True):
                exact = fx.connection.execute(
                    """SELECT COUNT(*)
                       FROM printer_memory_factory_campaign_scheduler_work AS cw
                       JOIN printer_memory_factory_run_steps AS rs
                         ON rs.scheduler_job_id=cw.scheduler_job_id
                       WHERE cw.campaign_id='campaign-1h' AND cw.run_id='run-1h'
                         AND cw.cycle_id='cycle-1h'
                         AND cw.token_slot_id=? AND cw.window_id=?
                         AND cw.target_identity=cw.window_id
                         AND rs.token_id=? AND rs.pair_id=?
                         AND rs.tracking_lane=?
                         AND rs.step_kind LIKE 'LONG_CONTINUATION_%'""",
                    (
                        candidate["token_slot_id"],
                        candidate["campaign_window_4h_id"],
                        candidate["token_row_id"],
                        candidate["pair_row_id"],
                        candidate["tracking_lane"],
                    ),
                ).fetchone()[0]
                self.assertEqual(int(exact), expected)

            self.assertEqual(
                int(fx.connection.execute(
                    """SELECT COUNT(*) FROM printer_memory_factory_campaign_windows
                       WHERE window_kind IN ('WINDOW_12H','WINDOW_24H')"""
                ).fetchone()[0]),
                0,
            )
            for lane in ("TRACK_FAST", "TRACK_NORMAL"):
                self.assertTrue(
                    bool(one_token_4h_runtime.runtime_budget(lane)["enabled_for_real_collection"])
                )
        finally:
            fx.close()

    def test_projection_failure_rolls_back_windows_slots_steps_jobs_and_ownership(self) -> None:
        fx, candidates = self._prepared()
        try:
            baseline_jobs = int(
                fx.connection.execute("SELECT COUNT(*) FROM printer_scheduler_jobs").fetchone()[0]
            )
            real_project = campaign_ownership.project_campaign_scheduler_job
            calls = 0

            def fail_on_second(*args, **kwargs):
                nonlocal calls
                calls += 1
                if calls == 2:
                    raise CampaignOwnershipError("injected_b2_projection_failure")
                return real_project(*args, **kwargs)

            with patch.object(
                campaign_ownership,
                "project_campaign_scheduler_job",
                side_effect=fail_on_second,
            ):
                with self.assertRaises(CampaignOwnershipError):
                    self._plan(fx, candidates)

            self.assertEqual(
                int(fx.connection.execute(
                    "SELECT COUNT(*) FROM printer_memory_factory_campaign_windows WHERE window_kind='WINDOW_4H'"
                ).fetchone()[0]),
                0,
            )
            states = fx.connection.execute(
                """SELECT token_state FROM printer_memory_factory_campaign_token_slots
                   WHERE campaign_id='campaign-1h' AND run_id='run-1h'
                     AND cycle_id='cycle-1h' ORDER BY slot_ordinal"""
            ).fetchall()
            self.assertEqual(
                [str(row[0]) for row in states],
                ["WINDOW_1H_CLOSED", "WINDOW_1H_CLOSED"],
            )
            self.assertEqual(
                int(fx.connection.execute(
                    """SELECT COUNT(*) FROM printer_memory_factory_run_steps
                       WHERE run_id='factory-run-1' AND step_kind LIKE 'LONG_CONTINUATION_%'"""
                ).fetchone()[0]),
                0,
            )
            self.assertEqual(
                int(fx.connection.execute(
                    """SELECT COUNT(*) FROM printer_memory_factory_campaign_scheduler_work
                       WHERE stage_id='WINDOW_4H'"""
                ).fetchone()[0]),
                0,
            )
            self.assertEqual(
                int(fx.connection.execute("SELECT COUNT(*) FROM printer_scheduler_jobs").fetchone()[0]),
                baseline_jobs,
            )
        finally:
            fx.close()

    def test_exact_repeat_is_idempotent_across_full_plan(self) -> None:
        fx, candidates = self._prepared()
        try:
            first = self._plan(fx, candidates)
            counts_before = tuple(
                int(fx.connection.execute(query).fetchone()[0])
                for query in (
                    "SELECT COUNT(*) FROM printer_memory_factory_campaign_windows WHERE window_kind='WINDOW_4H'",
                    "SELECT COUNT(*) FROM printer_memory_factory_run_steps WHERE run_id='factory-run-1' AND step_kind LIKE 'LONG_CONTINUATION_%'",
                    "SELECT COUNT(*) FROM printer_memory_factory_campaign_scheduler_work WHERE stage_id='WINDOW_4H'",
                    "SELECT COUNT(*) FROM printer_scheduler_jobs",
                )
            )
            second = self._plan(fx, candidates)
            counts_after = tuple(
                int(fx.connection.execute(query).fetchone()[0])
                for query in (
                    "SELECT COUNT(*) FROM printer_memory_factory_campaign_windows WHERE window_kind='WINDOW_4H'",
                    "SELECT COUNT(*) FROM printer_memory_factory_run_steps WHERE run_id='factory-run-1' AND step_kind LIKE 'LONG_CONTINUATION_%'",
                    "SELECT COUNT(*) FROM printer_memory_factory_campaign_scheduler_work WHERE stage_id='WINDOW_4H'",
                    "SELECT COUNT(*) FROM printer_scheduler_jobs",
                )
            )
            self.assertTrue(first["planned"])
            self.assertTrue(second["planned"])
            self.assertTrue(second["replay"])
            self.assertEqual(counts_before, counts_after)
        finally:
            fx.close()

    def test_preexisting_partial_long_plan_blocks_before_four_hour_handoff(self) -> None:
        fx, candidates = self._prepared()
        try:
            with fx.connection:
                fx.connection.execute(
                    """INSERT INTO printer_memory_factory_run_steps(
                        run_id,step_key,step_kind,step_status,token_id,pair_id,
                        token_mint,pair_address,tracking_lane,scheduled_for,result_json
                    ) VALUES ('factory-run-1','partial-4h','LONG_CONTINUATION_SNAPSHOT',
                        'PENDING',1,1,'mint-1','pair-1','TRACK_FAST',?,?)""",
                    (_iso(T1H), json.dumps({"partial": True})),
                )
            with self.assertRaises(Exception):
                self._plan(fx, candidates)
            self.assertEqual(
                int(fx.connection.execute(
                    "SELECT COUNT(*) FROM printer_memory_factory_campaign_windows WHERE window_kind='WINDOW_4H'"
                ).fetchone()[0]),
                0,
            )
            self.assertEqual(
                int(fx.connection.execute(
                    """SELECT COUNT(*) FROM printer_memory_factory_run_steps
                       WHERE run_id='factory-run-1' AND step_kind LIKE 'LONG_CONTINUATION_%'"""
                ).fetchone()[0]),
                1,
            )
        finally:
            fx.close()


if __name__ == "__main__":
    unittest.main()
