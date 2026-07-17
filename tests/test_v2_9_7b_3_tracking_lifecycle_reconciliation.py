"""Focused V2-9.7B.3 tracking/lifecycle reconciliation tests."""

from __future__ import annotations

import json
import sqlite3
import tempfile
import unittest
from pathlib import Path

from printer_v1.db.migrate import apply_migrations
from printer_v1.operator_cli.tracking_lifecycle_reconciliation import (
    reconcile_factory_post_cycle_lifecycle,
)


class TrackingLifecycleReconciliationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.db = Path(self.temp.name) / "fixture.sqlite3"
        apply_migrations(self.db)
        self.conn = sqlite3.connect(self.db)
        self.conn.row_factory = sqlite3.Row
        self.conn.execute("PRAGMA foreign_keys=ON")
        self.conn.execute(
            "INSERT INTO printer_memory_factory_runs "
            "(run_id,run_status,window_kind,db_mode,config_hash,config_json,started_at) "
            "VALUES ('run-1','RUNNING','WINDOW_15M','PROOF_ONLY','hash','{}','2026-07-17T00:00:00+00:00')"
        )
        self.targets = [self._target("A", "TRACK_FAST")]
        self.conn.commit()

    def tearDown(self) -> None:
        self.conn.close()
        self.temp.cleanup()

    def _target(self, suffix: str, lane: str) -> dict:
        mint = (suffix * 32)[:32]
        pair = (suffix.lower() * 44)[:44]
        cursor = self.conn.execute(
            "INSERT INTO printer_tokens(token_mint,chain,token_status) VALUES (?,'solana',?)",
            (mint, lane),
        )
        token_id = int(cursor.lastrowid)
        cursor = self.conn.execute(
            "INSERT INTO printer_pairs(token_id,pair_address,base_token_mint) VALUES (?,?,?)",
            (token_id, pair, mint),
        )
        pair_id = int(cursor.lastrowid)
        cursor = self.conn.execute(
            "INSERT INTO printer_tracking_queue "
            "(token_id,pair_id,tracking_lane,tracking_action,priority_reason,next_check_at,"
            "queue_status,source_status,data_quality_label) "
            "VALUES (?,?,?,'NEW_DISCOVERY','fixture','2026-07-17T00:00:00+00:00',"
            "'QUEUED','COMPLETE','CLEAN_DATA')",
            (token_id, pair_id, lane),
        )
        queue_id = int(cursor.lastrowid)
        cursor = self.conn.execute(
            "INSERT INTO printer_scheduler_jobs "
            "(job_name,job_kind,target_table,target_id,priority,status,scheduled_for) "
            "VALUES (?,?, 'printer_tracking_queue',?,1,'PENDING','2026-07-17T00:00:00+00:00')",
            (f"handoff-{suffix}", "TRACK_FAST_FIRST_15M" if lane == "TRACK_FAST" else "TRACK_NORMAL_FIRST_15M", queue_id),
        )
        return {
            "token_id": token_id,
            "pair_id": pair_id,
            "token_mint": mint,
            "pair_address": pair,
            "tracking_lane": lane,
            "tracking_queue_id": queue_id,
            "scheduler_job_id": int(cursor.lastrowid),
        }

    def _make_outcome(self, target: dict, terminal_status: str, reached: bool) -> dict:
        return {
            "token_id": target["token_id"],
            "pair_id": target["pair_id"],
            "terminal_status": terminal_status,
            "reached_terminal_window": reached,
        }

    def _run(self, outcomes: list[dict], *, policy: str = "cooldown") -> dict:
        return reconcile_factory_post_cycle_lifecycle(
            self.conn,
            run_id="run-1",
            selected_tokens=self.targets,
            discovery_results=self.targets,
            per_token_outcomes=outcomes,
            stop_reason="fixture-terminal",
            archive_policy=policy,
        )

    def _queue_status(self, target: dict) -> str:
        return str(self.conn.execute(
            "SELECT queue_status FROM printer_tracking_queue WHERE id=?",
            (target["tracking_queue_id"],),
        ).fetchone()[0])

    def _event_count(self) -> int:
        return int(self.conn.execute(
            "SELECT COUNT(*) FROM printer_token_lifecycle_events "
            "WHERE priority_reason='factory_post_cycle_reconciliation'"
        ).fetchone()[0])

    def test_clean_main_completion_enters_cooldown_once(self) -> None:
        result = self._run([self._make_outcome(self.targets[0], "CLEAN", True)])
        transition = result["transitions"][0]
        self.assertEqual(transition["terminal_disposition"], "COOLDOWN")
        self.assertEqual(transition["lifecycle_event"], "ENTER_COOLDOWN")
        self.assertEqual(self._queue_status(self.targets[0]), "COOLDOWN")
        self.assertEqual(transition["remaining_active_scheduler_jobs"], 0)
        self.assertTrue(result["exactly_one_disposition_per_selected_token"])

    def test_dirty_main_completion_can_use_explicit_archive_policy(self) -> None:
        result = self._run(
            [self._make_outcome(self.targets[0], "DIRTY", True)], policy="archive"
        )
        self.assertEqual(result["transitions"][0]["terminal_disposition"], "ARCHIVED")
        self.assertEqual(self._queue_status(self.targets[0]), "ARCHIVED")
        self.assertEqual(self._event_count(), 1)

    def test_failed_token_is_skipped_and_replay_is_idempotent(self) -> None:
        outcome = [self._make_outcome(self.targets[0], "TOKEN_LOCAL_FAILED", False)]
        first = self._run(outcome)
        updated_at = self.conn.execute(
            "SELECT updated_at FROM printer_tracking_queue WHERE id=?",
            (self.targets[0]["tracking_queue_id"],),
        ).fetchone()[0]
        second = self._run(outcome)
        replay_updated_at = self.conn.execute(
            "SELECT updated_at FROM printer_tracking_queue WHERE id=?",
            (self.targets[0]["tracking_queue_id"],),
        ).fetchone()[0]
        self.assertEqual(first["transitions"][0]["terminal_disposition"], "SKIPPED")
        self.assertEqual(updated_at, replay_updated_at)
        self.assertEqual(first["transitions"][0]["lifecycle_event"], "MANUAL_REVIEW")
        self.assertEqual(self._queue_status(self.targets[0]), "SKIPPED")
        self.assertEqual(self._event_count(), 1)
        self.assertTrue(second["transitions"][0]["idempotent_replay"])

    def test_two_tokens_reconcile_independently_on_stop(self) -> None:
        second = self._target("B", "TRACK_NORMAL")
        self.targets.append(second)
        result = self._run([
            self._make_outcome(self.targets[0], "CLEAN", True),
            self._make_outcome(second, "CANCELLED", False),
        ])
        dispositions = {
            row["token_id"]: row["terminal_disposition"]
            for row in result["transitions"]
        }
        self.assertEqual(dispositions[self.targets[0]["token_id"]], "COOLDOWN")
        self.assertEqual(dispositions[second["token_id"]], "SKIPPED")
        self.assertEqual(self._queue_status(self.targets[0]), "COOLDOWN")
        self.assertEqual(self._queue_status(second), "SKIPPED")
        self.assertEqual(result["active_scheduler_jobs_after_reconciliation"], 0)
        self.assertEqual(self._event_count(), 2)

    def test_support_5m_is_linked_audit_only_and_cannot_choose_disposition(self) -> None:
        target = self.targets[0]
        cursor = self.conn.execute(
            "INSERT INTO printer_scheduler_jobs "
            "(job_name,job_kind,target_table,target_id,priority,status,scheduled_for) "
            "VALUES ('support-job','TRACK_FAST_MICRO_EVENT','printer_memory_factory_run_steps',"
            "NULL,1,'RUNNING','2026-07-17T00:00:00+00:00')"
        )
        support_job_id = int(cursor.lastrowid)
        self.conn.execute(
            "INSERT INTO printer_memory_factory_run_steps "
            "(run_id,step_key,step_kind,step_status,token_id,pair_id,token_mint,"
            "pair_address,tracking_lane,scheduler_job_id) "
            "VALUES ('run-1','t1_support_5m','SUPPORT_5M','PENDING',?,?,?,?,?,?)",
            (
                target["token_id"], target["pair_id"], target["token_mint"],
                target["pair_address"], target["tracking_lane"], support_job_id,
            ),
        )
        result = self._run([self._make_outcome(target, "CLEAN", True)])
        transition = result["transitions"][0]
        self.assertEqual(transition["terminal_disposition"], "COOLDOWN")
        self.assertTrue(transition["support_5m"]["support_only"])
        self.assertFalse(transition["support_5m"]["determined_lifecycle"])
        self.assertFalse(transition["support_5m"]["triggered_continuation"])
        self.assertEqual(transition["support_5m"]["step_count"], 1)
        status = self.conn.execute(
            "SELECT status FROM printer_scheduler_jobs WHERE id=?", (support_job_id,)
        ).fetchone()[0]
        self.assertEqual(status, "CANCELLED")
        step_status = self.conn.execute(
            "SELECT step_status FROM printer_memory_factory_run_steps WHERE step_key='t1_support_5m'"
        ).fetchone()[0]
        self.assertEqual(step_status, "CANCELLED")
        payload = json.loads(self.conn.execute(
            "SELECT event_payload_json FROM printer_token_lifecycle_events "
            "WHERE priority_reason='factory_post_cycle_reconciliation'"
        ).fetchone()[0])
        self.assertTrue(payload["support_5m_audit_only"])


if __name__ == "__main__":
    unittest.main()