"""Offline TDD for standard 4h eligible-subset handoff/planning/validation."""

from __future__ import annotations

import json
import unittest
from unittest.mock import patch

from printer_v1.operator_cli import campaign_ownership
from printer_v1.operator_cli import one_command_15m_factory as factory
from printer_v1.operator_cli import one_token_4h_runtime
from printer_v1.operator_cli.campaign_ownership import CampaignOwnershipError
from tests.test_v2_9_8b_post_dtw100_standard_four_hour_campaign_planning import (
    StandardFourHourCampaignPlanningTests,
)
from tests.test_v2_9_8b_operational_selective_1h import T1H, _iso


class StandardFourHourEligibleSubsetTests(unittest.TestCase):
    def setUp(self) -> None:
        helper = StandardFourHourCampaignPlanningTests()
        self.fx, self.candidates = helper._prepared()
        self.by_slot = {
            str(candidate["token_slot_id"]): dict(candidate)
            for candidate in self.candidates
        }

    def tearDown(self) -> None:
        self.fx.close()

    def _plan(self, eligible_slots: list[str]):
        planner = getattr(
            one_token_4h_runtime,
            "plan_standard_campaign_4h_handoff",
            None,
        )
        self.assertIsNotNone(planner)
        return planner(
            self.fx.connection,
            campaign_id="campaign-1h",
            run_id="run-1h",
            cycle_id="cycle-1h",
            factory_run_id="factory-run-1",
            candidates=self.candidates,
            eligible_token_slot_ids=eligible_slots,
            execution_authority=(
                one_token_4h_runtime.FourHourExecutionAuthority.STANDARD_CAMPAIGN
            ),
            now=_iso(T1H),
        )

    def _manifest_by_slot(self) -> dict[str, dict]:
        rows = self.fx.connection.execute(
            """SELECT token_id,pair_id,result_json
               FROM printer_memory_factory_run_steps
               WHERE run_id='factory-run-1'
                 AND step_kind='CONTINUATION_CLOSE'
                 AND step_status='SUCCEEDED'
               ORDER BY token_id"""
        ).fetchall()
        manifests: dict[str, dict] = {}
        for row in rows:
            payload = json.loads(str(row["result_json"] or "{}"))
            manifest = payload.get("standard_four_hour_eligibility")
            if isinstance(manifest, dict):
                manifests[str(manifest["token_slot_id"])] = manifest
        return manifests

    def _long_counts(self) -> list[tuple[int, int]]:
        rows = self.fx.connection.execute(
            """SELECT token_id,COUNT(*)
               FROM printer_memory_factory_run_steps
               WHERE run_id='factory-run-1'
                 AND step_kind LIKE 'LONG_CONTINUATION_%'
               GROUP BY token_id ORDER BY token_id"""
        ).fetchall()
        return [(int(row[0]), int(row[1])) for row in rows]

    def _window_slots(self) -> list[str]:
        rows = self.fx.connection.execute(
            """SELECT token_slot_id
               FROM printer_memory_factory_campaign_windows
               WHERE campaign_id='campaign-1h' AND run_id='run-1h'
                 AND cycle_id='cycle-1h' AND window_kind='WINDOW_4H'
               ORDER BY token_slot_id"""
        ).fetchall()
        return [str(row[0]) for row in rows]

    def _owned_counts(self) -> list[tuple[int, int]]:
        rows = self.fx.connection.execute(
            """SELECT rs.token_id,COUNT(*)
               FROM printer_memory_factory_campaign_scheduler_work AS sw
               JOIN printer_memory_factory_run_steps AS rs
                 ON rs.scheduler_job_id=sw.scheduler_job_id
               WHERE sw.campaign_id='campaign-1h' AND sw.run_id='run-1h'
                 AND sw.cycle_id='cycle-1h' AND sw.factory_run_id='factory-run-1'
                 AND sw.ownership_contract_version='V2_STAGE_SCOPED'
                 AND sw.work_scope='WINDOW_LIFECYCLE'
                 AND sw.stage_id='WINDOW_4H'
               GROUP BY rs.token_id ORDER BY rs.token_id"""
        ).fetchall()
        return [(int(row[0]), int(row[1])) for row in rows]

    def test_policy_derived_prefix_plus_subset_budget_matrix(self) -> None:
        budget_owner = getattr(
            one_token_4h_runtime,
            "standard_campaign_lifecycle_budget",
            None,
        )
        self.assertIsNotNone(
            budget_owner,
            "prefix-plus-eligible-4h campaign budget owner is missing",
        )
        # V2-9.8B first-hour safety provenance repair: each token's exact 1h
        # close reserves 3 fresh governed safety transports, so every request
        # ceiling gains 6. The 1h close happens regardless of 4h eligibility,
        # so the reserve applies to every mask. Scheduler ceilings are unchanged
        # because no new Scheduler job is introduced.
        cases = (
            (("TRACK_FAST", "TRACK_FAST"), (False, False), 98, 82),
            (("TRACK_FAST", "TRACK_FAST"), (True, False), 167, 146),
            (("TRACK_FAST", "TRACK_FAST"), (True, True), 236, 210),
            (("TRACK_FAST", "TRACK_NORMAL"), (False, False), 80, 64),
            (("TRACK_FAST", "TRACK_NORMAL"), (True, False), 149, 128),
            (("TRACK_FAST", "TRACK_NORMAL"), (False, True), 119, 98),
            (("TRACK_FAST", "TRACK_NORMAL"), (True, True), 188, 162),
            (("TRACK_NORMAL", "TRACK_NORMAL"), (False, False), 62, 46),
            (("TRACK_NORMAL", "TRACK_NORMAL"), (True, False), 101, 80),
            (("TRACK_NORMAL", "TRACK_NORMAL"), (True, True), 140, 114),
        )
        for lanes, mask, requests, scheduler in cases:
            budget = budget_owner(lanes, mask)
            self.assertEqual(int(budget["request_ceiling"]), requests)
            self.assertEqual(int(budget["scheduler_ceiling"]), scheduler)
            self.assertEqual(
                bool(budget["real_collection_enabled"]),
                bool(sum(mask)),
            )
            self.assertEqual(int(budget["continuation_count"]), sum(mask))

        compatibility = one_token_4h_runtime.standard_two_token_lifecycle_budget(
            ("TRACK_FAST", "TRACK_NORMAL")
        )
        self.assertEqual(int(compatibility["request_ceiling"]), 188)
        self.assertEqual(int(compatibility["scheduler_ceiling"]), 162)

    def test_only_normal_slot_continues_with_exact_manifest_and_ownership(self) -> None:
        result = self._plan(["slot-2"])
        self.assertTrue(result["planned"])
        self.assertFalse(result["replay"])
        self.assertEqual(int(result["continuation_count"]), 1)
        self.assertEqual(int(result["planned_jobs"]), 31)
        self.assertEqual(result["planned_by_slot"], {"slot-2": 31})
        self.assertEqual(int(result["budget"]["request_ceiling"]), 119)
        self.assertEqual(int(result["budget"]["scheduler_ceiling"]), 98)
        self.assertEqual(self._window_slots(), ["slot-2"])
        self.assertEqual(self._long_counts(), [(2, 31)])
        self.assertEqual(self._owned_counts(), [(2, 31)])

        states = self.fx.connection.execute(
            """SELECT token_slot_id,token_state
               FROM printer_memory_factory_campaign_token_slots
               WHERE campaign_id='campaign-1h' AND run_id='run-1h'
                 AND cycle_id='cycle-1h' ORDER BY slot_ordinal"""
        ).fetchall()
        self.assertEqual(
            [(str(row[0]), str(row[1])) for row in states],
            [("slot-1", "WINDOW_1H_CLOSED"), ("slot-2", "WINDOW_4H_CONTINUING")],
        )

        manifests = self._manifest_by_slot()
        self.assertEqual(set(manifests), {"slot-1", "slot-2"})
        self.assertFalse(bool(manifests["slot-1"]["eligible"]))
        self.assertEqual(manifests["slot-1"]["verdict"], "BLOCK_CONTINUATION")
        self.assertTrue(bool(manifests["slot-2"]["eligible"]))
        self.assertEqual(manifests["slot-2"]["verdict"], "CONTINUE_TO_WINDOW_4H")
        self.assertEqual(
            {manifest["contract_version"] for manifest in manifests.values()},
            {"STANDARD_4H_ELIGIBILITY_V1"},
        )
        self.assertEqual(
            int(self.fx.connection.execute(
                """SELECT COUNT(*) FROM printer_memory_factory_campaign_windows
                   WHERE window_kind IN ('WINDOW_12H','WINDOW_24H')"""
            ).fetchone()[0]),
            0,
        )

    def test_only_fast_slot_continues_and_exact_repeat_is_idempotent(self) -> None:
        first = self._plan(["slot-1"])
        counts_before = (
            len(self._window_slots()),
            sum(count for _token, count in self._long_counts()),
            sum(count for _token, count in self._owned_counts()),
            int(self.fx.connection.execute(
                "SELECT COUNT(*) FROM printer_scheduler_jobs"
            ).fetchone()[0]),
        )
        second = self._plan(["slot-1"])
        counts_after = (
            len(self._window_slots()),
            sum(count for _token, count in self._long_counts()),
            sum(count for _token, count in self._owned_counts()),
            int(self.fx.connection.execute(
                "SELECT COUNT(*) FROM printer_scheduler_jobs"
            ).fetchone()[0]),
        )
        self.assertTrue(first["planned"])
        self.assertFalse(first["replay"])
        self.assertTrue(second["planned"])
        self.assertTrue(second["replay"])
        self.assertEqual(int(second["planned_jobs"]), 61)
        self.assertEqual(second["planned_by_slot"], {"slot-1": 61})
        self.assertEqual(int(second["budget"]["request_ceiling"]), 149)
        self.assertEqual(int(second["budget"]["scheduler_ceiling"]), 128)
        self.assertEqual(self._window_slots(), ["slot-1"])
        self.assertEqual(self._long_counts(), [(1, 61)])
        self.assertEqual(counts_before, counts_after)

    def test_zero_eligible_persists_manifest_and_is_valid_noop(self) -> None:
        result = self._plan([])
        self.assertTrue(result["planned"])
        self.assertFalse(result["replay"])
        self.assertTrue(bool(result["no_op"]))
        self.assertEqual(int(result["continuation_count"]), 0)
        self.assertEqual(int(result["planned_jobs"]), 0)
        self.assertEqual(result["planned_by_slot"], {})
        self.assertEqual(int(result["budget"]["request_ceiling"]), 80)
        self.assertEqual(int(result["budget"]["scheduler_ceiling"]), 64)
        self.assertEqual(self._window_slots(), [])
        self.assertEqual(self._long_counts(), [])
        self.assertEqual(self._owned_counts(), [])
        manifests = self._manifest_by_slot()
        self.assertEqual(set(manifests), {"slot-1", "slot-2"})
        self.assertTrue(all(not bool(item["eligible"]) for item in manifests.values()))

        validator = getattr(
            factory,
            "_standard_campaign_four_hour_terminal_validation",
            None,
        )
        self.assertIsNotNone(validator)
        terminal = validator(
            self.fx.connection,
            factory_run_id="factory-run-1",
            campaign_id="campaign-1h",
            run_id="run-1h",
            cycle_id="cycle-1h",
        )
        self.assertTrue(terminal["enabled"])
        self.assertTrue(terminal["complete"], terminal.get("reasons"))
        self.assertEqual(int(terminal["expected_continuation_count"]), 0)
        self.assertEqual(int(terminal["window_count"]), 0)
        self.assertEqual(int(terminal["active_owned_four_hour_work"]), 0)

    def test_subset_drift_after_durable_plan_fails_closed(self) -> None:
        first = self._plan(["slot-2"])
        self.assertTrue(first["planned"])
        counts = (
            self._window_slots(),
            self._long_counts(),
            self._owned_counts(),
        )
        with self.assertRaises(Exception):
            self._plan(["slot-1"])
        self.assertEqual(
            (self._window_slots(), self._long_counts(), self._owned_counts()),
            counts,
        )
        manifests = self._manifest_by_slot()
        self.assertFalse(bool(manifests["slot-1"]["eligible"]))
        self.assertTrue(bool(manifests["slot-2"]["eligible"]))

    def test_projection_failure_rolls_back_fresh_subset_manifest_and_plan(self) -> None:
        baseline_jobs = int(
            self.fx.connection.execute("SELECT COUNT(*) FROM printer_scheduler_jobs").fetchone()[0]
        )
        real_project = campaign_ownership.project_campaign_scheduler_job
        calls = 0

        def fail_first(*args, **kwargs):
            nonlocal calls
            calls += 1
            if calls == 1:
                raise CampaignOwnershipError("injected_subset_projection_failure")
            return real_project(*args, **kwargs)

        with patch.object(
            campaign_ownership,
            "project_campaign_scheduler_job",
            side_effect=fail_first,
        ):
            with self.assertRaises(CampaignOwnershipError):
                self._plan(["slot-2"])

        self.assertEqual(self._manifest_by_slot(), {})
        self.assertEqual(self._window_slots(), [])
        self.assertEqual(self._long_counts(), [])
        self.assertEqual(self._owned_counts(), [])
        self.assertEqual(
            int(self.fx.connection.execute("SELECT COUNT(*) FROM printer_scheduler_jobs").fetchone()[0]),
            baseline_jobs,
        )
        states = self.fx.connection.execute(
            """SELECT token_state FROM printer_memory_factory_campaign_token_slots
               WHERE campaign_id='campaign-1h' AND run_id='run-1h'
                 AND cycle_id='cycle-1h' ORDER BY slot_ordinal"""
        ).fetchall()
        self.assertEqual(
            [str(row[0]) for row in states],
            ["WINDOW_1H_CLOSED", "WINDOW_1H_CLOSED"],
        )

    def _terminalize_dirty_eligible_token(self, token_id: int) -> None:
        rows = self.fx.connection.execute(
            """SELECT * FROM printer_memory_factory_run_steps
               WHERE run_id='factory-run-1' AND token_id=?
                 AND step_kind LIKE 'LONG_CONTINUATION_%'
               ORDER BY scheduled_for,id""",
            (int(token_id),),
        ).fetchall()
        self.assertGreater(len(rows), 0)
        snapshot_ids: list[int] = []
        with self.fx.connection:
            for index, row in enumerate(rows, start=1):
                snapshot_id = 60000 + int(token_id) * 100 + index
                snapshot_ids.append(snapshot_id)
                stamp = str(row["scheduled_for"])
                self.fx.connection.execute(
                    """INSERT INTO printer_token_snapshots(
                        id,token_id,pair_id,captured_at,tracking_lane,snapshot_mode,
                        source_status,data_quality_label
                    ) VALUES (?,?,?,?,?,'TOKEN','COMPLETE','CLEAN_DATA')""",
                    (
                        snapshot_id,
                        int(row["token_id"]),
                        int(row["pair_id"]),
                        stamp,
                        str(row["tracking_lane"]),
                    ),
                )
                self.fx.connection.execute(
                    """UPDATE printer_memory_factory_run_steps
                       SET step_status='SUCCEEDED',snapshot_id=?,started_at=?,finished_at=?,updated_at=?
                       WHERE id=?""",
                    (snapshot_id, stamp, stamp, stamp, int(row["id"])),
                )
                self.fx.connection.execute(
                    """UPDATE printer_scheduler_jobs
                       SET status='SUCCEEDED',started_at=?,finished_at=?,updated_at=?,
                           locked_at=NULL,lock_owner=NULL
                       WHERE id=?""",
                    (stamp, stamp, stamp, int(row["scheduler_job_id"])),
                )
                factory._sync_owned_campaign_scheduler_job(
                    self.fx.connection,
                    scheduler_job_id=int(row["scheduler_job_id"]),
                )

            candidate = next(
                item for item in self.candidates
                if int(item["token_row_id"]) == int(token_id)
            )
            window = self.fx.connection.execute(
                """SELECT window_id FROM printer_memory_factory_campaign_windows
                   WHERE campaign_id='campaign-1h' AND run_id='run-1h'
                     AND cycle_id='cycle-1h' AND token_slot_id=?
                     AND window_kind='WINDOW_4H'""",
                (candidate["token_slot_id"],),
            ).fetchone()
            self.assertIsNotNone(window)
            self.fx.connection.execute(
                """UPDATE printer_memory_factory_campaign_windows
                   SET window_state='CLOSE_PENDING',updated_at=? WHERE window_id=?""",
                (_iso(T1H), str(window[0])),
            )
            opened = str(rows[0]["scheduled_for"])
            closed = str(rows[-1]["scheduled_for"])
            cursor = self.fx.connection.execute(
                """INSERT INTO printer_memory_windows(
                    token_id,pair_id,window_kind,opened_at,closed_at,
                    window_start_at,window_end_at,snapshot_start_id,snapshot_end_id,
                    memory_status,data_quality_label,window_status,memory_quality_label,
                    outcome_label,do_not_train,supporting_context_json
                ) VALUES (?,?, 'WINDOW_4H',?,?,?,?,?,?,'DIRTY_MEMORY','DIRTY_DATA',
                          'WINDOW_CLOSED','DIRTY_MEMORY','CONSOLIDATION',1,'{}')""",
                (
                    int(candidate["token_row_id"]),
                    int(candidate["pair_row_id"]),
                    opened,
                    closed,
                    opened,
                    closed,
                    int(snapshot_ids[0]),
                    int(snapshot_ids[-1]),
                ),
            )
            memory_id = int(cursor.lastrowid)

        close = next(row for row in rows if str(row["step_kind"]) == "LONG_CONTINUATION_CLOSE")
        binding = factory._bind_owned_long_memory_window_at_close(
            self.fx.connection,
            scheduler_job_id=int(close["scheduler_job_id"]),
            memory_window_row_id=memory_id,
            result={"memory_pipeline": {"lane_k_status": "LANE_K_BLOCKED", "memory": None}},
        )
        self.assertIsNotNone(binding)
        self.assertEqual(binding["window_state"], "DIRTY")
        self.fx.connection.commit()

    def test_single_eligible_terminal_validator_accepts_exact_manifest_subset(self) -> None:
        self._plan(["slot-2"])
        self._terminalize_dirty_eligible_token(2)
        validator = getattr(
            factory,
            "_standard_campaign_four_hour_terminal_validation",
            None,
        )
        self.assertIsNotNone(validator)
        terminal = validator(
            self.fx.connection,
            factory_run_id="factory-run-1",
            campaign_id="campaign-1h",
            run_id="run-1h",
            cycle_id="cycle-1h",
        )
        self.assertTrue(terminal["enabled"])
        self.assertTrue(terminal["complete"], terminal.get("reasons"))
        self.assertEqual(int(terminal["expected_continuation_count"]), 1)
        self.assertEqual(int(terminal["window_count"]), 1)
        self.assertEqual(len(terminal["per_token"]), 1)
        self.assertEqual(int(terminal["per_token"][0]["token_id"]), 2)
        self.assertEqual(terminal["per_token"][0]["window_state"], "DIRTY")
        self.assertEqual(int(terminal["active_owned_four_hour_work"]), 0)
        self.assertEqual(int(terminal["nonterminal_owned_four_hour_windows"]), 0)

    def test_terminal_validator_rejects_missing_owned_close_for_manifest_subset(self) -> None:
        self._plan(["slot-2"])
        self._terminalize_dirty_eligible_token(2)
        close = self.fx.connection.execute(
            """SELECT scheduler_job_id FROM printer_memory_factory_run_steps
               WHERE run_id='factory-run-1' AND token_id=2
                 AND step_kind='LONG_CONTINUATION_CLOSE'"""
        ).fetchone()
        self.assertIsNotNone(close)
        with self.fx.connection:
            self.fx.connection.execute(
                "DELETE FROM printer_memory_factory_campaign_scheduler_work WHERE scheduler_job_id=?",
                (int(close[0]),),
            )
        terminal = factory._standard_campaign_four_hour_terminal_validation(
            self.fx.connection,
            factory_run_id="factory-run-1",
            campaign_id="campaign-1h",
            run_id="run-1h",
            cycle_id="cycle-1h",
        )
        self.assertTrue(terminal["enabled"])
        self.assertFalse(terminal["complete"])
        self.assertTrue(
            any("close" in str(reason).lower() for reason in terminal["reasons"]),
            terminal["reasons"],
        )


if __name__ == "__main__":
    unittest.main()
