"""Focused V2-9.7D.6B.6 final campaign report tests."""

from __future__ import annotations

import json
import os
from pathlib import Path
import sqlite3
import tempfile
import unittest

from printer_v1.db import apply_migrations
from printer_v1.operator_cli.campaign_ownership import (
    create_campaign_run,
    create_cycle_with_two_slots,
    persist_immutable_object,
    persist_scheduler_work,
    persist_window,
)
from printer_v1.operator_cli.campaign_persistence import (
    CampaignPersistenceError,
    DB_MODE_PROOF_ISOLATED,
    create_campaign,
    persist_terminal_report_with_objects,
)
from printer_v1.operator_cli.final_campaign_report import (
    LOCKED_CAPABILITY_TABLES,
    FinalCampaignReportError,
    assemble_final_campaign_report,
    persist_final_campaign_report,
)


NOW = "2026-07-19T00:00:00+00:00"
CUTOFF = "2026-07-19T00:15:00+00:00"


def _provenance() -> dict[str, object]:
    return {
        "git_head": "b" * 40,
        "git_tracked_tree_clean": True,
        "git_staged_changes_present": False,
        "git_unstaged_changes_present": False,
        "git_untracked_present": True,
        "git_provenance_captured_at": NOW,
    }


class FinalCampaignReportTests(unittest.TestCase):
    def setUp(self) -> None:
        parent = os.environ.get("TEMP") or os.environ.get("TMP")
        self.temp = tempfile.TemporaryDirectory(dir=parent)
        self.db = Path(self.temp.name) / "final-report.sqlite3"
        apply_migrations(self.db)
        create_campaign(
            self.db,
            campaign_id="campaign-a",
            configuration_id="configuration-a",
            configuration={
                "slots": 2,
                "backup_preflight_references": {
                    "preflight_id": "preflight-a",
                    "backup_sha256": "c" * 64,
                    "restore_migration": "032_campaign_ownership_schema.sql",
                },
            },
            launch_provenance=_provenance(),
            db_mode=DB_MODE_PROOF_ISOLATED,
            db_target_identity="final-report-fixture",
            proof_source_db_identity="final-report-source",
            policy_version="v2-9.7d",
        )
        self.connection = sqlite3.connect(self.db)
        self.connection.row_factory = sqlite3.Row
        self.connection.execute("PRAGMA foreign_keys=ON")
        self._seed_authoritative_graph()

    def tearDown(self) -> None:
        self.connection.close()
        self.temp.cleanup()

    @staticmethod
    def _slot(identity: int, queue_id: int) -> dict[str, object]:
        return {
            "token_slot_id": f"slot-{identity}",
            "slot_ordinal": identity,
            "token_identity": f"token-{identity}",
            "token_row_id": identity,
            "mint_identity": f"mint-{identity}",
            "pair_identity": f"pair-{identity}",
            "pair_row_id": identity,
            "lifecycle_identity": f"lifecycle-{identity}",
            "tracking_queue_id": queue_id,
        }

    def _seed_authoritative_graph(self) -> None:
        zero_counts = {table: 0 for table in LOCKED_CAPABILITY_TABLES}
        authority_report = {
            "counts_before": zero_counts,
            "counts_after": zero_counts,
            "forbidden_deltas": zero_counts,
            "run_budgets": {
                "governed_requests_run": 2,
                "governed_requests_run_ceiling": 20,
                "scheduler_rows_total": 2,
                "scheduler_rows_ceiling": 40,
                "automatic_retries": 0,
            },
        }
        queues: dict[int, int] = {}
        jobs: dict[int, int] = {}
        with self.connection:
            self.connection.execute(
                """INSERT INTO printer_memory_factory_runs(
                       run_id,run_status,stop_reason,window_kind,db_mode,
                       config_hash,config_json,selected_token_count,started_at,
                       finished_at,final_report_json
                   ) VALUES ('authority-run','COMPLETED','NATURAL_COMPLETION',
                       'WINDOW_15M','PROOF_ONLY','hash','{}',2,?,?,?)""",
                (NOW, CUTOFF, json.dumps(authority_report, sort_keys=True)),
            )
            for identity in (1, 2):
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
                       ) VALUES (?,?,'TRACK_FAST','TRACK','fixture',?,'COOLDOWN',
                           'COMPLETE','CLEAN_DATA')""",
                    (identity, identity, NOW),
                )
                queues[identity] = int(queue.lastrowid)
                job = self.connection.execute(
                    """INSERT INTO printer_scheduler_jobs(
                           job_name,job_kind,target_table,target_id,priority,status,
                           scheduled_for,finished_at
                       ) VALUES (?,'CAMPAIGN_WINDOW','printer_tracking_queue',?,1,
                           'CANCELLED',?,?)""",
                    (f"job-{identity}", queues[identity], NOW, CUTOFF),
                )
                jobs[identity] = int(job.lastrowid)
                self.connection.execute(
                    """INSERT INTO printer_source_requests(
                           id,source_name,request_kind,requested_at,source_status,
                           data_quality_label
                       ) VALUES (?,'geckoterminal','SNAPSHOT',?,'COMPLETE','CLEAN_DATA')""",
                    (identity, NOW),
                )
                self.connection.execute(
                    """INSERT INTO printer_source_responses(
                           id,source_request_id,source_name,received_at,
                           source_status,data_quality_label
                       ) VALUES (?,?, 'geckoterminal',?,'COMPLETE','CLEAN_DATA')""",
                    (identity, identity, NOW),
                )
                quality = "CLEAN_MEMORY" if identity == 1 else "PARTIAL_MEMORY"
                self.connection.execute(
                    """INSERT INTO printer_memory_windows(
                           id,token_id,pair_id,window_kind,opened_at,closed_at,
                           memory_status,data_quality_label,window_status,
                           memory_quality_label
                       ) VALUES (?,?,?,'WINDOW_15M',?,?,'PARTIAL_MEMORY',
                           'CLEAN_DATA','WINDOW_CLOSED',?)""",
                    (100 + identity, identity, identity, NOW, CUTOFF, quality),
                )
                self.connection.execute(
                    """INSERT INTO printer_memory_factory_run_steps(
                           run_id,step_key,step_kind,step_status,token_id,pair_id,
                           token_mint,pair_address,tracking_lane,scheduler_job_id,
                           source_request_id,source_response_id,memory_window_id,
                           result_json,finished_at
                       ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                    (
                        "authority-run", f"close-{identity}", "WINDOW_CLOSE",
                        "SUCCEEDED", identity, identity,
                        f"mint-{identity}", f"pair-{identity}", "TRACK_FAST",
                        jobs[identity], identity, identity, 100 + identity,
                        "{}", CUTOFF,
                    ),
                )
            self.connection.execute(
                """INSERT INTO printer_episodes(
                       memory_window_id,token_id,pair_id,episode_kind,
                       episode_status,memory_status,data_quality_label,do_not_train,
                       window_kind,memory_quality_label
                   ) VALUES (101,1,1,'MEMORY_WINDOW','COMPLETE','CLEAN_MEMORY',
                       'CLEAN_DATA',0,'WINDOW_15M','CLEAN_MEMORY')"""
            )
        create_campaign_run(
            self.connection,
            campaign_id="campaign-a", run_id="run-a", run_ordinal=1,
            authoritative_run_id="authority-run", now=NOW,
        )
        create_cycle_with_two_slots(
            self.connection,
            campaign_id="campaign-a", run_id="run-a", cycle_id="cycle-a",
            cycle_ordinal=1,
            slots=(self._slot(1, queues[1]), self._slot(2, queues[2])),
            now=NOW,
        )
        for identity in (1, 2):
            persist_window(
                self.connection,
                window_id=f"window-{identity}", campaign_id="campaign-a",
                run_id="run-a", cycle_id="cycle-a",
                token_slot_id=f"slot-{identity}", token_row_id=identity,
                pair_row_id=identity, window_kind="WINDOW_15M",
                root_15m_lifecycle_identity=f"lifecycle-{identity}",
                memory_window_row_id=100 + identity,
                checkpoint_cutoff=CUTOFF, now=NOW,
            )
            persist_scheduler_work(
                self.connection,
                scheduler_work_id=f"work-{identity}", campaign_id="campaign-a",
                run_id="run-a", cycle_id="cycle-a",
                token_slot_id=f"slot-{identity}", window_id=f"window-{identity}",
                work_intent="collect", deadline_at=CUTOFF,
                scheduler_job_id=jobs[identity], source_request_id=identity,
                source_response_id=identity, now=NOW,
            )
            with self.connection:
                self.connection.execute(
                    """UPDATE printer_memory_factory_campaign_scheduler_work
                       SET work_state='SUCCEEDED',first_terminal_cause='WORK_COMPLETE',
                           terminal_at=?,updated_at=? WHERE scheduler_work_id=?""",
                    (CUTOFF, CUTOFF, f"work-{identity}"),
                )
                payload = {
                    "factory_reconciliation_key": f"authority-run:{identity}:{identity}",
                    "run_id": "authority-run",
                    "stop_reason": "NATURAL_COMPLETION",
                    "terminal_status": "CLEAN" if identity == 1 else "NO_PROMOTION",
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
                    (identity, identity, json.dumps(payload, sort_keys=True), CUTOFF),
                )
        persist_window(
            self.connection,
            window_id="support-1", campaign_id="campaign-a", run_id="run-a",
            cycle_id="cycle-a", token_slot_id="slot-1", token_row_id=1,
            pair_row_id=1, window_kind="WINDOW_5M_MICRO_EVENT",
            root_15m_lifecycle_identity="lifecycle-1",
            containing_main_window_id="window-1", checkpoint_cutoff=CUTOFF,
            now=NOW,
        )
        payloads = {
            "CONTINUATION_4A": {
                "verdict": "STOP_AFTER_15M", "unknowns": ["continuation_unknown"],
            },
            "SUPPORT_EVIDENCE_4B": {
                "support_only": True, "gaps": ["holder_authenticity_unknown"],
            },
            "TRAJECTORY_5A": {
                "trajectory_id": "trajectory-a", "evidence_gaps": ["gap-a"],
            },
            "CHECKPOINT_5A": {
                "checkpoint_id": "checkpoint-a", "evidence_gaps": ["gap-b"],
            },
            "MANIPULATION_CONTEXT_5B": {
                "market_integrity": "MANIPULATION_PRESENT",
                "tradeability": "TRADEABILITY_UNKNOWN",
                "unknowns": ["wallet_control_unknown", "intent_unknown"],
            },
            "OPPORTUNITY_SEGMENT_5C": {
                "full_window_outcome": "DUMP",
                "internal_trade_opportunity_outcome": "SHORT_TERM_PUMP",
                "opportunity_class": "CHART_OPPORTUNITY",
                "evidence_gaps": ["quote_missing", "slippage_missing"],
            },
        }
        for index, (kind, payload) in enumerate(payloads.items(), 1):
            window_id = "support-1" if kind == "SUPPORT_EVIDENCE_4B" else "window-1"
            persist_immutable_object(
                self.connection,
                object_id=f"object-{index}", object_kind=kind,
                campaign_id="campaign-a", configuration_id="configuration-a",
                run_id="run-a", cycle_id="cycle-a", token_slot_id="slot-1",
                window_id=window_id, payload=payload, now=NOW,
            )
        with self.connection:
            self.connection.execute(
                """UPDATE printer_memory_factory_campaigns
                   SET campaign_state='TERMINAL_COMPLETED',
                       first_terminal_cause='NATURAL_COMPLETION',terminal_at=?,updated_at=?
                   WHERE campaign_id='campaign-a'""",
                (CUTOFF, CUTOFF),
            )
            self.connection.execute(
                """UPDATE printer_memory_factory_campaign_runs
                   SET run_state='TERMINAL_COMPLETED',
                       first_terminal_cause='NATURAL_COMPLETION',terminal_at=?,updated_at=?
                   WHERE run_id='run-a'""",
                (CUTOFF, CUTOFF),
            )
            self.connection.execute(
                """UPDATE printer_memory_factory_campaign_cycles
                   SET cycle_state='TERMINAL_COMPLETED',
                       first_terminal_cause='NATURAL_COMPLETION',terminal_at=?,updated_at=?
                   WHERE cycle_id='cycle-a'""",
                (CUTOFF, CUTOFF),
            )
            for identity in (1, 2):
                self.connection.execute(
                    """UPDATE printer_memory_factory_campaign_windows
                       SET window_state='NO_PROMOTION',
                           first_terminal_cause='WINDOW_COMPLETE',terminal_at=?,updated_at=?
                       WHERE window_id=?""",
                    (CUTOFF, CUTOFF, f"window-{identity}"),
                )
            self.connection.execute(
                """UPDATE printer_memory_factory_campaign_windows
                   SET window_state='NO_PROMOTION',
                       first_terminal_cause='SUPPORT_COMPLETE',terminal_at=?,updated_at=?
                   WHERE window_id='support-1'""",
                (CUTOFF, CUTOFF),
            )
            self.connection.execute(
                """INSERT INTO printer_memory_factory_campaign_supervision(
                       supervision_id,campaign_id,configuration_id,run_id,owner_id,
                       supervision_state,terminal_status,first_terminal_cause,
                       heartbeat_at,lease_expires_at,lease_lock_path,
                       cleanup_completed_at,lease_released_at,created_at,updated_at
                   ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (
                    "supervision-a", "campaign-a", "configuration-a", "run-a",
                    "owner-a", "TERMINAL", "COMPLETED", "NATURAL_COMPLETION",
                    NOW, CUTOFF, "fixture.lock", CUTOFF, CUTOFF, NOW, CUTOFF,
                ),
            )

    def test_complete_report_is_deterministic_and_preserves_independent_layers(self) -> None:
        first = assemble_final_campaign_report(
            self.db, campaign_id="campaign-a",
            configuration_id="configuration-a", run_id="run-a",
        )
        second = assemble_final_campaign_report(
            self.db, campaign_id="campaign-a",
            configuration_id="configuration-a", run_id="run-a",
        )
        self.assertEqual(first.canonical_bytes, second.canonical_bytes)
        self.assertEqual(first.report_hash, second.report_hash)
        report = first.report
        self.assertEqual(len(report["identity"]["two_token_slots"]), 2)
        self.assertEqual(len(report["promotion_outcomes_b1"]), 2)
        self.assertEqual(len(report["lifecycle_b3"]), 2)
        self.assertEqual(report["terminal"]["first_terminal_cause"], "NATURAL_COMPLETION")
        self.assertEqual(report["launch_git_provenance"], _provenance())
        self.assertFalse(report["git_provenance_recaptured"])
        layer = report["opportunity_outcome_layers"][0]
        self.assertEqual(layer["full_window_outcome"], "DUMP")
        self.assertEqual(layer["internal_trade_opportunity_outcome"], "SHORT_TERM_PUMP")
        self.assertNotEqual(
            layer["full_window_outcome"],
            layer["internal_trade_opportunity_outcome"],
        )
        self.assertTrue(report["visible_unknowns_and_evidence_gaps"])
        self.assertEqual(
            report["backup_preflight_references"]["preflight_id"], "preflight-a"
        )
        usage = report["source_scheduler_ceiling_usage"]
        self.assertEqual(usage["source_request_ids"], [1, 2])
        self.assertEqual(usage["scheduler_job_ids"], [1, 2])
        self.assertEqual(usage["campaign_scheduler_work_total"], 2)
        self.assertTrue(report["locked_capabilities"]["all_deltas_zero"])

    def test_persistence_is_atomic_idempotent_and_conflicts_fail_closed(self) -> None:
        first = persist_final_campaign_report(
            self.db, report_id="report-a", campaign_id="campaign-a",
            configuration_id="configuration-a", run_id="run-a",
        )
        second = persist_final_campaign_report(
            self.db, report_id="report-a", campaign_id="campaign-a",
            configuration_id="configuration-a", run_id="run-a",
        )
        self.assertEqual(first["report_hash"], second["report_hash"])
        self.assertFalse(first["idempotent_replay"])
        self.assertTrue(second["idempotent_replay"])
        self.assertEqual(self.connection.execute(
            "SELECT COUNT(*) FROM printer_memory_factory_campaign_reports"
        ).fetchone()[0], 1)
        self.assertEqual(self.connection.execute(
            "SELECT COUNT(*) FROM printer_memory_factory_campaign_report_objects"
        ).fetchone()[0], 6)
        altered = json.loads(first["canonical_json"])
        altered["terminal"]["first_terminal_cause"] = "CONFLICT"
        with self.assertRaisesRegex(CampaignPersistenceError, "payload already differs"):
            persist_terminal_report_with_objects(
                self.db, report_id="report-a", campaign_id="campaign-a",
                configuration_id="configuration-a", report=altered,
                object_ids=first["object_ids"],
            )

    def test_cross_campaign_run_or_configuration_identity_fails_closed(self) -> None:
        cases = (
            {"campaign_id": "campaign-foreign"},
            {"configuration_id": "configuration-foreign"},
            {"run_id": "run-foreign"},
        )
        for changes in cases:
            with self.subTest(changes=changes):
                values = {
                    "campaign_id": "campaign-a",
                    "configuration_id": "configuration-a",
                    "run_id": "run-a",
                    **changes,
                }
                with self.assertRaisesRegex(
                    FinalCampaignReportError, "ownership mismatch"
                ):
                    assemble_final_campaign_report(self.db, **values)

    def test_report_creates_no_forbidden_rows(self) -> None:
        before = {
            table: self.connection.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
            for table in LOCKED_CAPABILITY_TABLES
        }
        persist_final_campaign_report(
            self.db, report_id="report-a", campaign_id="campaign-a",
            configuration_id="configuration-a", run_id="run-a",
        )
        after = {
            table: self.connection.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
            for table in LOCKED_CAPABILITY_TABLES
        }
        self.assertEqual(before, after)
        self.assertTrue(all(value == 0 for value in after.values()))


if __name__ == "__main__":
    unittest.main()
