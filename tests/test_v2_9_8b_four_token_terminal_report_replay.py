"""Focused four-token terminal-report and zero-source replay parity tests."""

from __future__ import annotations

import hashlib
import json
import unittest

from printer_v1.operator_cli.campaign_ownership import (
    create_cycle_with_two_slots,
    persist_scheduler_work,
    persist_window,
)
from printer_v1.operator_cli.final_campaign_report import (
    FinalCampaignReportError,
    assemble_final_campaign_report,
    persist_final_campaign_report,
)
from printer_v1.operator_cli.zero_source_campaign_replay import (
    REPLAY_VERIFIED,
    replay_terminal_campaign_report,
)
import test_v2_9_7d_6b_6_final_campaign_report as _fixture


NOW = _fixture.NOW
CUTOFF = _fixture.CUTOFF


class FourTokenTerminalReportReplayTests(unittest.TestCase):
    _slot = staticmethod(_fixture.FinalCampaignReportTests._slot)
    _seed_authoritative_graph = (
        _fixture.FinalCampaignReportTests._seed_authoritative_graph
    )

    def setUp(self) -> None:
        _fixture.FinalCampaignReportTests.setUp(self)
        self._seed_cycle_two()

    def tearDown(self) -> None:
        _fixture.FinalCampaignReportTests.tearDown(self)

    @staticmethod
    def _cycle_two_slot(
        identity: int, slot_ordinal: int, queue_id: int
    ) -> dict[str, object]:
        return {
            "token_slot_id": f"slot-{identity}",
            "slot_ordinal": slot_ordinal,
            "token_identity": f"token-{identity}",
            "token_row_id": identity,
            "mint_identity": f"mint-{identity}",
            "pair_identity": f"pair-{identity}",
            "pair_row_id": identity,
            "lifecycle_identity": f"lifecycle-{identity}",
            "tracking_queue_id": queue_id,
        }

    def _seed_cycle_two(self) -> None:
        queues: dict[int, int] = {}
        jobs: dict[int, int] = {}
        with self.connection:
            for identity in (3, 4):
                self.connection.execute(
                    "INSERT INTO printer_tokens(id,token_mint,token_status) VALUES (?,?,?)",
                    (identity, f"mint-{identity}", "TRACK_FAST"),
                )
                self.connection.execute(
                    """INSERT INTO printer_pairs(
                           id,token_id,pair_address,base_token_mint
                       ) VALUES (?,?,?,?)""",
                    (identity, identity, f"pair-{identity}", f"mint-{identity}"),
                )
                queue = self.connection.execute(
                    """INSERT INTO printer_tracking_queue(
                           token_id,pair_id,tracking_lane,tracking_action,
                           priority_reason,next_check_at,queue_status,source_status,
                           data_quality_label
                       ) VALUES (?,?,'TRACK_FAST','TRACK','cycle2-fixture',?,
                           'COOLDOWN','COMPLETE','CLEAN_DATA')""",
                    (identity, identity, NOW),
                )
                queues[identity] = int(queue.lastrowid)
                job = self.connection.execute(
                    """INSERT INTO printer_scheduler_jobs(
                           job_name,job_kind,target_table,target_id,priority,status,
                           scheduled_for,finished_at
                       ) VALUES (?,'CAMPAIGN_WINDOW','printer_tracking_queue',?,1,
                           'CANCELLED',?,?)""",
                    (f"cycle2-job-{identity}", queues[identity], NOW, CUTOFF),
                )
                jobs[identity] = int(job.lastrowid)
                self.connection.execute(
                    """INSERT INTO printer_source_requests(
                           id,source_name,request_kind,request_key,requested_at,
                           source_status,data_quality_label
                       ) VALUES (?,'geckoterminal','SNAPSHOT',?,?, 'COMPLETE',
                           'CLEAN_DATA')""",
                    (
                        identity,
                        f"authority-run:t{identity - 2}_c0002_snapshot_00:attempt-1",
                        NOW,
                    ),
                )
                self.connection.execute(
                    """INSERT INTO printer_source_responses(
                           id,source_request_id,source_name,received_at,
                           source_status,data_quality_label
                       ) VALUES (?,?, 'geckoterminal',?,'COMPLETE','CLEAN_DATA')""",
                    (identity, identity, NOW),
                )
                self.connection.execute(
                    """INSERT INTO printer_memory_windows(
                           id,token_id,pair_id,window_kind,opened_at,closed_at,
                           memory_status,data_quality_label,window_status,
                           memory_quality_label
                       ) VALUES (?,?,?,'WINDOW_15M',?,?,'PARTIAL_MEMORY',
                           'CLEAN_DATA','WINDOW_CLOSED','PARTIAL_MEMORY')""",
                    (100 + identity, identity, identity, NOW, CUTOFF),
                )
                self.connection.execute(
                    """INSERT INTO printer_memory_factory_run_steps(
                           run_id,step_key,step_kind,step_status,token_id,pair_id,
                           token_mint,pair_address,tracking_lane,scheduler_job_id,
                           source_request_id,source_response_id,memory_window_id,
                           result_json,finished_at
                       ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                    (
                        "authority-run",
                        f"close-{identity}",
                        "WINDOW_CLOSE",
                        "SUCCEEDED",
                        identity,
                        identity,
                        f"mint-{identity}",
                        f"pair-{identity}",
                        "TRACK_FAST",
                        jobs[identity],
                        identity,
                        identity,
                        100 + identity,
                        "{}",
                        CUTOFF,
                    ),
                )

        create_cycle_with_two_slots(
            self.connection,
            campaign_id="campaign-a",
            run_id="run-a",
            cycle_id="cycle-b",
            cycle_ordinal=2,
            slots=(
                self._cycle_two_slot(3, 1, queues[3]),
                self._cycle_two_slot(4, 2, queues[4]),
            ),
            now=NOW,
        )
        for identity in (3, 4):
            persist_window(
                self.connection,
                window_id=f"window-{identity}",
                campaign_id="campaign-a",
                run_id="run-a",
                cycle_id="cycle-b",
                token_slot_id=f"slot-{identity}",
                token_row_id=identity,
                pair_row_id=identity,
                window_kind="WINDOW_15M",
                root_15m_lifecycle_identity=f"lifecycle-{identity}",
                memory_window_row_id=100 + identity,
                checkpoint_cutoff=CUTOFF,
                now=NOW,
            )
            persist_scheduler_work(
                self.connection,
                scheduler_work_id=f"work-{identity}",
                campaign_id="campaign-a",
                run_id="run-a",
                cycle_id="cycle-b",
                token_slot_id=f"slot-{identity}",
                window_id=f"window-{identity}",
                work_intent="collect",
                deadline_at=CUTOFF,
                scheduler_job_id=jobs[identity],
                source_request_id=identity,
                source_response_id=identity,
                now=NOW,
            )
            with self.connection:
                self.connection.execute(
                    """UPDATE printer_memory_factory_campaign_scheduler_work
                       SET work_state='SUCCEEDED',first_terminal_cause='WORK_COMPLETE',
                           terminal_at=?,updated_at=?
                       WHERE scheduler_work_id=?""",
                    (CUTOFF, CUTOFF, f"work-{identity}"),
                )
                payload = {
                    "factory_reconciliation_key": (
                        f"authority-run:{identity}:{identity}"
                    ),
                    "run_id": "authority-run",
                    "stop_reason": "NATURAL_COMPLETION",
                    "terminal_status": "NO_PROMOTION",
                    "main_window_only": True,
                    "support_5m_audit_only": True,
                }
                self.connection.execute(
                    """INSERT INTO printer_token_lifecycle_events(
                           token_id,pair_id,previous_state,new_state,lifecycle_event,
                           priority_reason,source_status,data_quality_label,
                           event_payload_json,created_at
                       ) VALUES (?,?,'TRACK_FAST','COOLDOWN','ENTER_COOLDOWN',
                           'factory_post_cycle_reconciliation','COMPLETE',
                           'CLEAN_DATA',?,?)""",
                    (
                        identity,
                        identity,
                        json.dumps(payload, sort_keys=True),
                        CUTOFF,
                    ),
                )

        discovery_payload = '{"logical_stage":"ELIGIBLE_SUPPLY"}'
        discovery_hash = hashlib.sha256(
            discovery_payload.encode("utf-8")
        ).hexdigest()
        with self.connection:
            pre_job = self.connection.execute(
                """INSERT INTO printer_scheduler_jobs(
                       job_name,job_kind,target_table,priority,status,
                       scheduled_for,finished_at
                   ) VALUES ('pre-admission:terminal-report-cycle2',
                       'PRE_ADMISSION_DISCOVERY_SELECTION',
                       'printer_pre_admission_discovery_attempts',13,'SUCCEEDED',?,?)""",
                (NOW, CUTOFF),
            )
            pre_job_id = int(pre_job.lastrowid)
            self.connection.execute(
                """INSERT INTO printer_source_requests(
                       id,source_name,request_kind,request_key,requested_at,
                       source_status,data_quality_label
                   ) VALUES (5,'geckoterminal','DISCOVERY',
                       'campaign-a:cycle2:discovery:attempt-1',?,
                       'COMPLETE','CLEAN_DATA')""",
                (NOW,),
            )
            self.connection.execute(
                """INSERT INTO printer_source_responses(
                       id,source_request_id,source_name,received_at,
                       source_status,data_quality_label
                   ) VALUES (5,5,'geckoterminal',?,'COMPLETE','CLEAN_DATA')""",
                (NOW,),
            )
            self.connection.execute(
                """INSERT INTO printer_pre_admission_discovery_attempts(
                       attempt_id,campaign_id,campaign_run_id,configuration_id,
                       authoritative_factory_run_id,proposed_cycle_ordinal,
                       proposed_cycle_id,scheduler_job_id,cycle_cutoff,evaluated_at,
                       selection_seed_identity,attempt_state,first_terminal_cause,
                       terminal_at,consumed_cycle_id,consumed_at,created_at,updated_at
                   ) VALUES ('attempt-terminal-report-cycle2','campaign-a','run-a',
                       'configuration-a','authority-run',2,'cycle-b',?,?,?,
                       'seed-cycle2','CONSUMED','EXACT_PAIR_FROZEN',?,
                       'cycle-b',?,?,?)""",
                (pre_job_id, CUTOFF, CUTOFF, CUTOFF, CUTOFF, NOW, CUTOFF),
            )
            self.connection.execute(
                """INSERT INTO printer_pre_admission_attempt_evidence(
                       attempt_id,event_key,opportunity_ordinal,claim_ordinal,
                       evidence_kind,categorical_reason,source_request_id,
                       source_response_id,payload_json,payload_hash,observed_at,
                       created_at
                   ) VALUES ('attempt-terminal-report-cycle2','source-request-5',
                       0,1,'SOURCE_REQUEST_TERMINAL','COMPLETE',5,5,?,?,?,?)""",
                (discovery_payload, discovery_hash, NOW, NOW),
            )
            self.connection.execute(
                """UPDATE printer_memory_factory_campaign_cycles
                   SET cycle_state='TERMINAL_COMPLETED',
                       first_terminal_cause='NATURAL_COMPLETION',
                       terminal_at=?,updated_at=?
                   WHERE cycle_id='cycle-b'""",
                (CUTOFF, CUTOFF),
            )
            self.connection.execute(
                """UPDATE printer_memory_factory_campaign_windows
                   SET window_state='NO_PROMOTION',
                       first_terminal_cause='WINDOW_COMPLETE',
                       terminal_at=?,updated_at=?
                   WHERE cycle_id='cycle-b'""",
                (CUTOFF, CUTOFF),
            )
            row = self.connection.execute(
                """SELECT final_report_json
                   FROM printer_memory_factory_runs
                   WHERE run_id='authority-run'"""
            ).fetchone()
            authority = json.loads(str(row[0]))
            authority["run_budgets"] = {
                "governed_requests_run": 5,
                "governed_requests_run_ceiling": 100,
                "scheduler_rows_total": 5,
                "scheduler_rows_ceiling": 100,
                "automatic_retries": 0,
                "four_hour_phase_usage": {
                    "state": "STARTED",
                    "available": True,
                    "source_requests": 1,
                    "source_request_ceiling": 20,
                    "scheduler_rows": 1,
                    "scheduler_row_ceiling": 20,
                    "within_ceiling": True,
                },
                "cumulative_lifecycle_usage": {
                    "state": "REPORTED",
                    "available": True,
                    "source_requests": 5,
                    "source_request_ceiling": 100,
                    "scheduler_rows": 5,
                    "scheduler_row_ceiling": 100,
                    "discovery_source_requests": 1,
                    "later_cycle_discovery_source_requests": 1,
                    "later_cycle_discovery_scheduler_rows": 1,
                    "runtime_source_requests": 4,
                    "request_components": {
                        "discovery": 1,
                        "cycle1_lifecycle": 2,
                        "cycle2_pre4h": 1,
                        "cycle2_4h": 1,
                    },
                    "scheduler_components": {},
                    "policy_derived": True,
                    "budget_verdict": "WITHIN_CEILING",
                    "within_ceiling": True,
                },
            }
            self.connection.execute(
                """UPDATE printer_memory_factory_runs
                   SET final_report_json=?
                   WHERE run_id='authority-run'""",
                (json.dumps(authority, sort_keys=True),),
            )

    def _assemble(self):
        return assemble_final_campaign_report(
            self.db,
            campaign_id="campaign-a",
            configuration_id="configuration-a",
            run_id="run-a",
        )

    def test_four_token_terminal_report_and_replay_are_complete(self) -> None:
        assembled = self._assemble()
        report = assembled.report

        self.assertEqual(len(report["identity"]["cycles"]), 2)
        self.assertEqual(len(report["identity"]["two_token_slots"]), 4)
        self.assertEqual(len(report["lifecycle_b3"]), 4)
        cycle_two = [
            slot
            for slot in report["identity"]["two_token_slots"]
            if slot["cycle_id"] == "cycle-b"
        ]
        self.assertEqual(
            [
                (
                    slot["token_slot_id"],
                    int(slot["token_row_id"]),
                    int(slot["pair_row_id"]),
                    int(slot["tracking_queue_id"]),
                )
                for slot in cycle_two
            ],
            [
                ("slot-3", 3, 3, int(cycle_two[0]["tracking_queue_id"])),
                ("slot-4", 4, 4, int(cycle_two[1]["tracking_queue_id"])),
            ],
        )
        self.assertEqual(
            {item["token_slot_id"] for item in report["lifecycle_b3"]},
            {"slot-1", "slot-2", "slot-3", "slot-4"},
        )
        self.assertTrue(
            all(item["active_associated_work_after"] == 0 for item in report["lifecycle_b3"])
        )

        usage = report["source_scheduler_ceiling_usage"]
        budgets = usage["authoritative_run_budgets"]
        cumulative = budgets["cumulative_lifecycle_usage"]
        self.assertEqual(cumulative["source_requests"], 5)
        self.assertEqual(cumulative["later_cycle_discovery_source_requests"], 1)
        self.assertEqual(cumulative["later_cycle_discovery_scheduler_rows"], 1)
        self.assertEqual(cumulative["runtime_source_requests"], 4)
        self.assertEqual(
            cumulative["request_components"],
            {
                "discovery": 1,
                "cycle1_lifecycle": 2,
                "cycle2_pre4h": 1,
                "cycle2_4h": 1,
            },
        )
        # The Cycle-2 discovery request is attempt-owned rather than attached
        # to campaign Scheduler work, but it is still governed campaign usage.
        self.assertEqual(usage["source_request_ids"], [1, 2, 3, 4, 5])
        self.assertEqual(usage["source_response_ids"], [1, 2, 3, 4, 5])
        self.assertEqual(usage["scheduler_job_ids"], [1, 2, 3, 4, 5])

        persisted = persist_final_campaign_report(
            self.db,
            report_id="four-token-report",
            campaign_id="campaign-a",
            configuration_id="configuration-a",
            run_id="run-a",
        )
        replay = replay_terminal_campaign_report(
            self.db,
            campaign_id="campaign-a",
            configuration_id="configuration-a",
            report_id="four-token-report",
            report_hash=str(persisted["report_hash"]),
        )
        self.assertEqual(replay["replay_state"], REPLAY_VERIFIED)
        self.assertEqual(replay["reasons"], [])
        self.assertEqual(
            replay["diagnostics"]["source_scheduler_ceiling_usage"],
            report["source_scheduler_ceiling_usage"],
        )
        self.assertEqual(
            replay["zero_work_evidence"],
            {
                "source_calls": 0,
                "scheduler_work": 0,
                "memory_writes": 0,
                "database_writes": 0,
            },
        )
        self.assertEqual(
            replay["database_read_only_evidence"]["before_sha256"],
            replay["database_read_only_evidence"]["after_sha256"],
        )
        self.assertEqual(
            replay["database_read_only_evidence"]["before_row_counts"],
            replay["database_read_only_evidence"]["after_row_counts"],
        )
        self.assertEqual(
            replay["database_read_only_evidence"]["total_changes"], 0
        )
        self.assertFalse(
            any(
                window["window_kind"] in {"WINDOW_12H", "WINDOW_24H"}
                for window in report["identity"]["windows"]
            )
        )
        self.assertTrue(report["locked_capabilities"]["all_deltas_zero"])

    def test_missing_cycle_two_b3_lifecycle_fails_closed(self) -> None:
        with self.connection:
            self.connection.execute(
                """DELETE FROM printer_token_lifecycle_events
                   WHERE token_id=4 AND pair_id=4"""
            )
        with self.assertRaisesRegex(
            FinalCampaignReportError,
            "exactly one B.3 lifecycle reconciliation event is required",
        ):
            self._assemble()

    def test_duplicate_cycle_two_b3_lifecycle_fails_closed(self) -> None:
        with self.connection:
            self.connection.execute(
                """INSERT INTO printer_token_lifecycle_events(
                       token_id,pair_id,previous_state,new_state,lifecycle_event,
                       priority_reason,source_status,data_quality_label,
                       event_payload_json,created_at
                   )
                   SELECT token_id,pair_id,previous_state,new_state,lifecycle_event,
                          priority_reason,source_status,data_quality_label,
                          event_payload_json,created_at
                   FROM printer_token_lifecycle_events
                   WHERE token_id=4 AND pair_id=4"""
            )
        with self.assertRaisesRegex(
            FinalCampaignReportError,
            "exactly one B.3 lifecycle reconciliation event is required",
        ):
            self._assemble()


if __name__ == "__main__":
    unittest.main()
