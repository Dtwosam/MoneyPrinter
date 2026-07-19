"""Focused V2-9.7D.6B.4 lifecycle/rotation adapter tests."""

from __future__ import annotations

import json
import os
from pathlib import Path
import sqlite3
import tempfile
import unittest

from printer_v1.db import apply_migrations
from printer_v1.operator_cli.campaign_lifecycle_rotation_adapter import (
    CampaignLifecycleAdapterError,
    CampaignTerminalOutcome,
    TerminalCampaignToken,
    evaluate_slot_replacement,
    reconcile_terminal_campaign_token,
)
from printer_v1.operator_cli.campaign_ownership import (
    create_campaign_run,
    create_cycle_with_two_slots,
)
from printer_v1.operator_cli.campaign_persistence import (
    DB_MODE_PROOF_ISOLATED,
    create_campaign,
)


NOW = "2026-07-19T00:00:00+00:00"
LOCKED_TABLES = (
    "printer_memory_retrieval_queries", "printer_memory_retrieval_matches",
    "printer_paper_decisions", "printer_paper_positions",
    "printer_paper_trade_events", "printer_paper_trade_audits",
    "printer_paper_audit_reports",
)


def _provenance() -> dict[str, object]:
    return {
        "git_head": "a" * 40,
        "git_tracked_tree_clean": True,
        "git_staged_changes_present": False,
        "git_unstaged_changes_present": False,
        "git_untracked_present": True,
        "git_provenance_captured_at": NOW,
    }


class LifecycleRotationIntegrationTests(unittest.TestCase):
    def setUp(self) -> None:
        parent = os.environ.get("TEMP") or os.environ.get("TMP")
        self.temp = tempfile.TemporaryDirectory(dir=parent)
        self.db = Path(self.temp.name) / "lifecycle.sqlite3"
        apply_migrations(self.db)
        create_campaign(
            self.db,
            campaign_id="campaign-a",
            configuration_id="configuration-a",
            configuration={"slots": 2},
            launch_provenance=_provenance(),
            db_mode=DB_MODE_PROOF_ISOLATED,
            db_target_identity="lifecycle-fixture",
            proof_source_db_identity="lifecycle-source",
            policy_version="v2-9.7d",
        )
        self.connection = sqlite3.connect(self.db)
        self.connection.execute("PRAGMA foreign_keys=ON")
        self.connection.row_factory = sqlite3.Row
        self.queues: dict[int, int] = {}
        self.jobs: dict[int, int] = {}
        self._seed_graph()

    def tearDown(self) -> None:
        self.connection.close()
        self.temp.cleanup()

    def _seed_graph(self) -> None:
        with self.connection:
            self.connection.execute(
                """INSERT INTO printer_memory_factory_runs(
                    run_id,run_status,window_kind,db_mode,config_hash,
                    config_json,selected_token_count,started_at
                ) VALUES ('authority-run','COMPLETED','WINDOW_15M','PROOF_ONLY',
                    'hash','{}',2,?)""",
                (NOW,),
            )
            for identity in (1, 2, 3, 4):
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
            for identity in (1, 2):
                cursor = self.connection.execute(
                    """INSERT INTO printer_tracking_queue(
                        token_id,pair_id,tracking_lane,tracking_action,
                        priority_reason,next_check_at,queue_status,source_status,
                        data_quality_label
                    ) VALUES (?,?,'TRACK_FAST','TRACK','fixture',?,'QUEUED',
                        'COMPLETE','CLEAN_DATA')""",
                    (identity, identity, NOW),
                )
                self.queues[identity] = int(cursor.lastrowid)
                cursor = self.connection.execute(
                    """INSERT INTO printer_scheduler_jobs(
                        job_name,job_kind,target_table,target_id,priority,status,
                        scheduled_for
                    ) VALUES (?,'TRACK_FAST_FIRST_15M','printer_tracking_queue',
                        ?,1,'PENDING',?)""",
                    (f"job-{identity}", self.queues[identity], NOW),
                )
                self.jobs[identity] = int(cursor.lastrowid)
            cursor = self.connection.execute(
                """INSERT INTO printer_tracking_queue(
                    token_id,pair_id,tracking_lane,tracking_action,
                    priority_reason,next_check_at,queue_status,source_status,
                    data_quality_label
                ) VALUES (4,4,'TRACK_FAST','TRACK','fixture',?,'COOLDOWN',
                    'COMPLETE','CLEAN_DATA')""",
                (NOW,),
            )
            self.queues[4] = int(cursor.lastrowid)
        create_campaign_run(
            self.connection,
            campaign_id="campaign-a",
            run_id="run-a",
            run_ordinal=1,
            authoritative_run_id="authority-run",
            now=NOW,
        )
        create_cycle_with_two_slots(
            self.connection,
            campaign_id="campaign-a",
            run_id="run-a",
            cycle_id="cycle-a",
            cycle_ordinal=1,
            slots=(self._slot(1), self._slot(2)),
            now=NOW,
        )

    def _slot(self, identity: int) -> dict[str, object]:
        return {
            "token_slot_id": f"slot-{identity}",
            "slot_ordinal": identity,
            "token_identity": f"token-{identity}",
            "token_row_id": identity,
            "mint_identity": f"mint-{identity}",
            "pair_identity": f"pair-{identity}",
            "pair_row_id": identity,
            "lifecycle_identity": f"lifecycle-{identity}",
            "tracking_queue_id": self.queues[identity],
        }

    def _terminal(
        self, identity: int, outcome: CampaignTerminalOutcome,
    ) -> TerminalCampaignToken:
        return TerminalCampaignToken(
            campaign_id="campaign-a",
            run_id="run-a",
            cycle_id="cycle-a",
            token_slot_id=f"slot-{identity}",
            token_identity=f"token-{identity}",
            mint_identity=f"mint-{identity}",
            pair_identity=f"pair-{identity}",
            lifecycle_identity=f"lifecycle-{identity}",
            outcome=outcome,
        )

    def _set_terminal_state(
        self, identity: int, outcome: CampaignTerminalOutcome,
    ) -> None:
        state = {
            CampaignTerminalOutcome.NATURAL: "WINDOW_15M_CLOSED",
            CampaignTerminalOutcome.DIRTY: "WINDOW_15M_CLOSED",
            CampaignTerminalOutcome.BLOCKED: "FAILED",
            CampaignTerminalOutcome.CANCELLED: "MANUAL_REVIEW",
        }[outcome]
        terminal = state in {"FAILED", "MANUAL_REVIEW"}
        with self.connection:
            self.connection.execute(
                """UPDATE printer_memory_factory_campaign_token_slots
                   SET token_state=?,first_terminal_cause=?,terminal_at=?,updated_at=?
                   WHERE token_slot_id=?""",
                (
                    state,
                    f"fixture-{outcome.value.lower()}" if terminal else None,
                    NOW if terminal else None,
                    NOW,
                    f"slot-{identity}",
                ),
            )

    def _reconcile(
        self,
        identity: int,
        outcome: CampaignTerminalOutcome,
        *,
        archive_policy: str = "cooldown",
    ) -> dict[str, object]:
        self._set_terminal_state(identity, outcome)
        return reconcile_terminal_campaign_token(
            self.db,
            token=self._terminal(identity, outcome),
            stop_reason=f"fixture-{outcome.value.lower()}",
            archive_policy=archive_policy,
        )

    def _count_events(self, identity: int) -> int:
        return int(self.connection.execute(
            """SELECT COUNT(*) FROM printer_token_lifecycle_events
               WHERE token_id=? AND pair_id=?
                 AND priority_reason='factory_post_cycle_reconciliation'""",
            (identity, identity),
        ).fetchone()[0])

    def test_natural_completion_has_one_cooldown_disposition_and_zero_work(self) -> None:
        result = self._reconcile(1, CampaignTerminalOutcome.NATURAL)
        self.assertEqual(result["terminal_disposition"], "COOLDOWN")
        self.assertEqual(result["lifecycle_event"], "ENTER_COOLDOWN")
        self.assertEqual(result["active_associated_work"]["total"], 0)
        self.assertTrue(result["slot_vacant"])
        self.assertEqual(self._count_events(1), 1)
        queue = self.connection.execute(
            "SELECT queue_status FROM printer_tracking_queue WHERE id=?",
            (self.queues[1],),
        ).fetchone()[0]
        job = self.connection.execute(
            "SELECT status FROM printer_scheduler_jobs WHERE id=?",
            (self.jobs[1],),
        ).fetchone()[0]
        self.assertEqual(queue, "COOLDOWN")
        self.assertEqual(job, "CANCELLED")

    def test_dirty_archive_is_explicit_nonpermanent_and_idempotent(self) -> None:
        first = self._reconcile(
            1, CampaignTerminalOutcome.DIRTY, archive_policy="archive"
        )
        second = reconcile_terminal_campaign_token(
            self.db,
            token=self._terminal(1, CampaignTerminalOutcome.DIRTY),
            stop_reason="fixture-dirty",
            archive_policy="archive",
        )
        self.assertEqual(first["terminal_disposition"], "ARCHIVED")
        self.assertFalse(first["idempotent_replay"])
        self.assertTrue(second["idempotent_replay"])
        self.assertEqual(first["lifecycle_event_id"], second["lifecycle_event_id"])
        self.assertEqual(self._count_events(1), 1)
        gate = evaluate_slot_replacement(
            self.db,
            token=self._terminal(1, CampaignTerminalOutcome.DIRTY),
            candidate_token_row_id=1,
            candidate_mint_identity="mint-1",
            candidate_pair_row_id=1,
            candidate_pair_identity="pair-1",
        )
        self.assertFalse(gate["archive_is_permanent_rejection"])
        self.assertIn("same_pair_recycling_blocked", gate["reasons"])

    def test_blocked_and_cancelled_are_independent_manual_review_dispositions(self) -> None:
        blocked = self._reconcile(1, CampaignTerminalOutcome.BLOCKED)
        self.assertEqual(blocked["terminal_disposition"], "SKIPPED")
        self.assertEqual(blocked["lifecycle_event"], "MANUAL_REVIEW")
        other_queue_before = self.connection.execute(
            "SELECT queue_status FROM printer_tracking_queue WHERE id=?",
            (self.queues[2],),
        ).fetchone()[0]
        other_job_before = self.connection.execute(
            "SELECT status FROM printer_scheduler_jobs WHERE id=?",
            (self.jobs[2],),
        ).fetchone()[0]
        self.assertEqual(other_queue_before, "QUEUED")
        self.assertEqual(other_job_before, "PENDING")

        cancelled = self._reconcile(2, CampaignTerminalOutcome.CANCELLED)
        self.assertEqual(cancelled["terminal_disposition"], "SKIPPED")
        self.assertEqual(cancelled["lifecycle_event"], "MANUAL_REVIEW")
        self.assertEqual(self._count_events(1), 1)
        self.assertEqual(self._count_events(2), 1)

    def test_replacement_requires_reconciliation_and_pair_cooldown_blocks(self) -> None:
        token = self._terminal(1, CampaignTerminalOutcome.NATURAL)
        before = evaluate_slot_replacement(
            self.db,
            token=token,
            candidate_token_row_id=3,
            candidate_mint_identity="mint-3",
            candidate_pair_row_id=3,
            candidate_pair_identity="pair-3",
        )
        self.assertFalse(before["replacement_allowed"])
        self.assertIn("terminal_token_not_successfully_reconciled", before["reasons"])

        self._reconcile(1, CampaignTerminalOutcome.NATURAL)
        after = evaluate_slot_replacement(
            self.db,
            token=token,
            candidate_token_row_id=3,
            candidate_mint_identity="mint-3",
            candidate_pair_row_id=3,
            candidate_pair_identity="pair-3",
        )
        self.assertTrue(after["replacement_allowed"])
        self.assertTrue(after["slot_vacant"])

        cooldown = evaluate_slot_replacement(
            self.db,
            token=token,
            candidate_token_row_id=4,
            candidate_mint_identity="mint-4",
            candidate_pair_row_id=4,
            candidate_pair_identity="pair-4",
        )
        self.assertFalse(cooldown["replacement_allowed"])
        self.assertIn("candidate_pair_cooldown_active", cooldown["reasons"])

    def test_identity_mismatch_fails_before_b3_and_same_pair_recycling_blocks(self) -> None:
        self._set_terminal_state(1, CampaignTerminalOutcome.NATURAL)
        mismatched = TerminalCampaignToken(
            **{
                **self._terminal(1, CampaignTerminalOutcome.NATURAL).__dict__,
                "pair_identity": "pair-foreign",
            }
        )
        with self.assertRaisesRegex(
            CampaignLifecycleAdapterError, "identity mismatch"
        ):
            reconcile_terminal_campaign_token(
                self.db,
                token=mismatched,
                stop_reason="fixture-mismatch",
            )
        self.assertEqual(self._count_events(1), 0)
        self._reconcile(1, CampaignTerminalOutcome.NATURAL)
        same = evaluate_slot_replacement(
            self.db,
            token=self._terminal(1, CampaignTerminalOutcome.NATURAL),
            candidate_token_row_id=1,
            candidate_mint_identity="mint-1",
            candidate_pair_row_id=1,
            candidate_pair_identity="pair-1",
        )
        self.assertFalse(same["replacement_allowed"])
        self.assertIn("same_pair_recycling_blocked", same["reasons"])

    def test_support_5m_is_cleanup_only_and_locked_capabilities_stay_empty(self) -> None:
        cursor = self.connection.execute(
            """INSERT INTO printer_scheduler_jobs(
                job_name,job_kind,target_table,priority,status,scheduled_for
            ) VALUES ('support-job','TRACK_FAST_MICRO_EVENT',
                'printer_memory_factory_run_steps',1,'RUNNING',?)""",
            (NOW,),
        )
        support_job = int(cursor.lastrowid)
        self.connection.execute(
            """INSERT INTO printer_memory_factory_run_steps(
                run_id,step_key,step_kind,step_status,token_id,pair_id,
                token_mint,pair_address,tracking_lane,scheduler_job_id,result_json
            ) VALUES ('authority-run','support-1','SUPPORT_5M','PENDING',1,1,
                'mint-1','pair-1','TRACK_FAST',?,?)""",
            (support_job, json.dumps({"claimed_disposition": "ARCHIVED"})),
        )
        self.connection.commit()
        result = self._reconcile(1, CampaignTerminalOutcome.NATURAL)
        self.assertEqual(result["terminal_disposition"], "COOLDOWN")
        self.assertTrue(result["support_5m"]["support_only"])
        self.assertFalse(result["support_5m"]["determined_lifecycle"])
        self.assertEqual(result["active_associated_work"]["total"], 0)
        self.assertEqual(
            self.connection.execute(
                "SELECT status FROM printer_scheduler_jobs WHERE id=?",
                (support_job,),
            ).fetchone()[0],
            "CANCELLED",
        )
        for table in LOCKED_TABLES:
            self.assertEqual(
                self.connection.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0],
                0,
                table,
            )


if __name__ == "__main__":
    unittest.main()
