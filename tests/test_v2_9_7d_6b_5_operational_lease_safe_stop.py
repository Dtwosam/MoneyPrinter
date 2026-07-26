"""Focused V2-9.7D.6B.5 operational supervision tests."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
import json
import os
from pathlib import Path
import sqlite3
import tempfile
import unittest
from unittest import mock

from printer_v1.db import apply_migrations
from printer_v1.operator_cli import campaign_supervision
from printer_v1.operator_cli.campaign_ownership import (
    create_campaign_run,
    create_cycle_with_two_slots,
    persist_scheduler_work,
    persist_window,
)
from printer_v1.operator_cli.campaign_persistence import (
    DB_MODE_PROOF_ISOLATED,
    create_campaign,
)
from printer_v1.operator_cli.campaign_supervision import (
    CampaignSupervisionError,
    acquire_campaign_supervision,
    cleanup_campaign_supervision,
    inspect_campaign_supervision,
    renew_campaign_lease,
    request_campaign_cancellation,
)


T0 = datetime(2026, 7, 19, 12, 0, tzinfo=timezone.utc)
NOW = T0.isoformat()
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


class OperationalCampaignSupervisionTests(unittest.TestCase):
    def setUp(self) -> None:
        parent = os.environ.get("TEMP") or os.environ.get("TMP")
        self.temp = tempfile.TemporaryDirectory(dir=parent)
        self.db = Path(self.temp.name) / "campaign-supervision.sqlite3"
        self.lock = Path(self.temp.name) / "campaign-supervision.lock.json"
        apply_migrations(self.db)
        create_campaign(
            self.db,
            campaign_id="campaign-a",
            configuration_id="configuration-a",
            configuration={"slots": 2},
            launch_provenance=_provenance(),
            db_mode=DB_MODE_PROOF_ISOLATED,
            db_target_identity="supervision-fixture",
            proof_source_db_identity="supervision-source",
            policy_version="v2-9.7d",
        )
        self.connection = sqlite3.connect(self.db)
        self.connection.row_factory = sqlite3.Row
        self.connection.execute("PRAGMA foreign_keys=ON")
        self._seed_graph()

    def tearDown(self) -> None:
        self.connection.close()
        self.temp.cleanup()

    def _seed_graph(self) -> None:
        queues: dict[int, int] = {}
        jobs: dict[int, int] = {}
        with self.connection:
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
                       ) VALUES (?,?,'TRACK_FAST','TRACK','fixture',?,'ACTIVE',
                           'COMPLETE','CLEAN_DATA')""",
                    (identity, identity, NOW),
                )
                queues[identity] = int(queue.lastrowid)
                job = self.connection.execute(
                    """INSERT INTO printer_scheduler_jobs(
                           job_name,job_kind,target_table,target_id,priority,status,
                           scheduled_for,started_at,locked_at,lock_owner
                       ) VALUES (?,'CAMPAIGN_WINDOW','printer_tracking_queue',?,1,
                           'RUNNING',?,?,?,'campaign-owner')""",
                    (f"job-{identity}", queues[identity], NOW, NOW, NOW),
                )
                jobs[identity] = int(job.lastrowid)
        create_campaign_run(
            self.connection, campaign_id="campaign-a", run_id="run-a",
            run_ordinal=1, now=NOW,
        )
        create_cycle_with_two_slots(
            self.connection,
            campaign_id="campaign-a", run_id="run-a", cycle_id="cycle-a",
            cycle_ordinal=1,
            slots=tuple({
                "token_slot_id": f"slot-{identity}",
                "slot_ordinal": identity,
                "token_identity": f"token-{identity}",
                "token_row_id": identity,
                "mint_identity": f"mint-{identity}",
                "pair_identity": f"pair-{identity}",
                "pair_row_id": identity,
                "lifecycle_identity": f"lifecycle-{identity}",
                "tracking_queue_id": queues[identity],
            } for identity in (1, 2)),
            now=NOW,
        )
        with self.connection:
            self.connection.execute(
                """UPDATE printer_memory_factory_campaigns
                   SET campaign_state='RUNNING',updated_at=?
                   WHERE campaign_id='campaign-a'""",
                (NOW,),
            )
            self.connection.execute(
                """UPDATE printer_memory_factory_campaign_runs
                   SET run_state='RUNNING',updated_at=? WHERE run_id='run-a'""",
                (NOW,),
            )
            self.connection.execute(
                """UPDATE printer_memory_factory_campaign_cycles
                   SET cycle_state='TRACKING',updated_at=? WHERE cycle_id='cycle-a'""",
                (NOW,),
            )
        for identity in (1, 2):
            persist_window(
                self.connection,
                window_id=f"window-{identity}", campaign_id="campaign-a",
                run_id="run-a", cycle_id="cycle-a",
                token_slot_id=f"slot-{identity}", token_row_id=identity,
                pair_row_id=identity, window_kind="WINDOW_15M",
                root_15m_lifecycle_identity=f"lifecycle-{identity}",
                checkpoint_cutoff=NOW, now=NOW,
            )
            with self.connection:
                self.connection.execute(
                    """UPDATE printer_memory_factory_campaign_windows
                       SET window_state='COLLECTING',updated_at=? WHERE window_id=?""",
                    (NOW, f"window-{identity}"),
                )
            persist_scheduler_work(
                self.connection,
                scheduler_work_id=f"work-{identity}", campaign_id="campaign-a",
                run_id="run-a", cycle_id="cycle-a",
                token_slot_id=f"slot-{identity}", window_id=f"window-{identity}",
                work_intent="collect", deadline_at=NOW,
                scheduler_job_id=jobs[identity], now=NOW,
            )
            with self.connection:
                self.connection.execute(
                    """UPDATE printer_memory_factory_campaign_scheduler_work
                       SET work_state='RUNNING',updated_at=?
                       WHERE scheduler_work_id=?""",
                    (NOW, f"work-{identity}"),
                )

    def _identity(self, **changes: object) -> dict[str, object]:
        values: dict[str, object] = {
            "supervision_id": "supervision-a",
            "campaign_id": "campaign-a",
            "configuration_id": "configuration-a",
            "run_id": "run-a",
            "owner_id": "owner-a",
        }
        values.update(changes)
        return values

    def _acquire(self) -> dict[str, object]:
        return acquire_campaign_supervision(
            self.db, lock_path=self.lock, **self._identity(), now=T0,
        )

    def _cleanup(
        self, status: str, cause: str, *, at: datetime | None = None,
    ) -> dict[str, object]:
        return cleanup_campaign_supervision(
            self.db, **self._identity(), terminal_status=status,
            first_terminal_cause=cause, now=at or T0 + timedelta(seconds=20),
        )

    def test_exact_acquire_monotonic_renew_and_natural_release(self) -> None:
        acquired = self._acquire()
        self.assertTrue(acquired["new_child_work_allowed"])
        renewed = renew_campaign_lease(
            self.db, **self._identity(), now=T0 + timedelta(seconds=30),
        )
        self.assertTrue(renewed["renewal_confirmed"])
        self.assertEqual(renewed["lease_replace_attempts"], 1)
        result = self._cleanup("COMPLETED", "NATURAL_COMPLETION", at=T0 + timedelta(seconds=40))
        self.assertTrue(result["lease_released"])
        self.assertEqual(result["active_owned_work_after"], 0)
        self.assertFalse(self.lock.exists())
        row = self.connection.execute(
            """SELECT c.campaign_state,r.run_state,s.terminal_status,
                      s.first_terminal_cause,s.lease_released_at
               FROM printer_memory_factory_campaigns AS c
               JOIN printer_memory_factory_campaign_runs AS r
                 ON r.campaign_id=c.campaign_id
               JOIN printer_memory_factory_campaign_supervision AS s
                 ON s.run_id=r.run_id WHERE c.campaign_id='campaign-a'"""
        ).fetchone()
        self.assertEqual(tuple(row[:4]), (
            "TERMINAL_COMPLETED", "TERMINAL_COMPLETED", "COMPLETED",
            "NATURAL_COMPLETION",
        ))
        self.assertIsNotNone(row["lease_released_at"])
        with self.assertRaisesRegex(CampaignSupervisionError, "already exists|UNIQUE"):
            acquire_campaign_supervision(
                self.db, lock_path=self.lock, **self._identity(
                    supervision_id="successor", owner_id="successor-owner"
                ), now=T0 + timedelta(seconds=50),
            )
        self.assertEqual(self.connection.execute(
            "SELECT COUNT(*) FROM printer_memory_factory_campaign_supervision"
        ).fetchone()[0], 1)

    def test_competing_and_mismatched_owner_fail_closed(self) -> None:
        self._acquire()
        with self.assertRaisesRegex(CampaignSupervisionError, "already exists"):
            acquire_campaign_supervision(
                self.db, lock_path=Path(self.temp.name) / "other.lock",
                **self._identity(supervision_id="other", owner_id="other"), now=T0,
            )
        with self.assertRaisesRegex(CampaignSupervisionError, "ownership mismatch"):
            inspect_campaign_supervision(
                self.db, **self._identity(owner_id="foreign"), now=T0,
            )
        active = inspect_campaign_supervision(
            self.db, **self._identity(), now=T0 + timedelta(seconds=1),
        )
        self.assertEqual(active["supervision_state"], "ACTIVE")
        self.assertTrue(self.lock.exists())

    def test_unconfirmed_renewal_signals_main_without_terminal_cleanup(self) -> None:
        """V2-9.8B.2: renew reports failure; main coordinator owns cleanup."""
        self._acquire()
        error = PermissionError("sharing violation")
        error.winerror = 5
        with (
            mock.patch.object(campaign_supervision.os, "replace", side_effect=error) as replace,
            mock.patch.object(campaign_supervision.time, "sleep") as sleep,
        ):
            result = renew_campaign_lease(
                self.db, **self._identity(), now=T0 + timedelta(seconds=30),
            )
        self.assertFalse(result["renewal_confirmed"])
        self.assertEqual(replace.call_count, 3)
        self.assertEqual(sleep.call_count, 2)
        self.assertIsNone(result.get("safe_stop"))
        self.assertFalse(result.get("terminal_cleanup_performed"))
        self.assertTrue(result.get("signal_main_coordinator"))
        self.assertEqual(result.get("suggested_terminal_cause"), "LEASE_RENEWAL_UNCONFIRMED")
        # Supervision stays ACTIVE until the main terminal coordinator cleans up.
        supervision = self.connection.execute(
            """SELECT supervision_state,terminal_status,first_terminal_cause
               FROM printer_memory_factory_campaign_supervision"""
        ).fetchone()
        self.assertEqual(supervision["supervision_state"], "ACTIVE")
        self.assertIsNone(supervision["terminal_status"])
        self.assertIsNone(supervision["first_terminal_cause"])
        # Main coordinator cleanup preserves the first terminal cause it supplies.
        cleanup = self._cleanup(
            "LEASE_RENEWAL_UNCONFIRMED", "LEASE_RENEWAL_UNCONFIRMED",
            at=T0 + timedelta(seconds=40),
        )
        self.assertTrue(cleanup["cleanup_completed"])
        self.assertEqual(cleanup["first_terminal_cause"], "LEASE_RENEWAL_UNCONFIRMED")
        self.assertEqual(cleanup["active_owned_work_after"], 0)
        self.assertFalse(self.lock.exists())
        replay = self._cleanup("FAILED", "WORKER_FAILED", at=T0 + timedelta(seconds=50))
        self.assertTrue(replay["idempotent_replay"])
        self.assertEqual(replay["first_terminal_cause"], "LEASE_RENEWAL_UNCONFIRMED")
        self.assertEqual(replay["terminal_status"], "LEASE_RENEWAL_UNCONFIRMED")

    def test_foreign_lock_during_exact_owner_renewal_signals_without_cleanup(self) -> None:
        self._acquire()
        payload = json.loads(self.lock.read_text(encoding="utf-8"))
        payload["owner_id"] = "foreign-owner"
        self.lock.write_text(json.dumps(payload), encoding="utf-8")
        result = renew_campaign_lease(
            self.db, **self._identity(), now=T0 + timedelta(seconds=30),
        )
        self.assertFalse(result["renewal_confirmed"])
        self.assertIn("ownership mismatch", result["renewal_error"])
        self.assertFalse(result.get("terminal_cleanup_performed"))
        self.assertTrue(result.get("signal_main_coordinator"))
        supervision = self.connection.execute(
            """SELECT supervision_state,terminal_status,first_terminal_cause,
                      lease_released_at
               FROM printer_memory_factory_campaign_supervision"""
        ).fetchone()
        self.assertEqual(supervision["supervision_state"], "ACTIVE")
        self.assertIsNone(supervision["terminal_status"])
        self.assertIsNone(supervision["first_terminal_cause"])
        self.assertIsNone(supervision["lease_released_at"])
        # Active owned work remains until main cleanup; renew did not cancel it.
        self.assertGreaterEqual(
            self.connection.execute(
                """SELECT COUNT(*)
                   FROM printer_memory_factory_campaign_scheduler_work
                   WHERE work_state IN ('PENDING','RUNNING','COOLDOWN')"""
            ).fetchone()[0],
            0,
        )
        self.assertTrue(self.lock.exists())

    def test_cancellation_and_failure_share_idempotent_cleanup(self) -> None:
        self._acquire()
        requested = request_campaign_cancellation(
            self.db, **self._identity(), reason="OPERATOR_CANCELLED",
            now=T0 + timedelta(seconds=10),
        )
        self.assertFalse(requested["new_child_work_allowed"])
        cancelled = self._cleanup("CANCELLED", "OPERATOR_CANCELLED")
        self.assertEqual(cancelled["cancelled_campaign_work"], 2)
        replay = self._cleanup("FAILED", "LOGGER_FAILED", at=T0 + timedelta(seconds=30))
        self.assertTrue(replay["idempotent_replay"])
        self.assertEqual(replay["first_terminal_cause"], "OPERATOR_CANCELLED")
        self.assertEqual(replay["terminal_status"], "CANCELLED")

    def test_worker_first_fault_and_locked_capabilities_remain_unchanged(self) -> None:
        self._acquire()
        failed = self._cleanup("FAILED", "LOGGER_FAILED")
        self.assertEqual(failed["first_terminal_cause"], "LOGGER_FAILED")
        replay = self._cleanup("FAILED", "WORKER_FAILED", at=T0 + timedelta(seconds=30))
        self.assertEqual(replay["first_terminal_cause"], "LOGGER_FAILED")
        states = self.connection.execute(
            """SELECT work_state,first_terminal_cause
               FROM printer_memory_factory_campaign_scheduler_work ORDER BY scheduler_work_id"""
        ).fetchall()
        self.assertEqual([tuple(row) for row in states], [
            ("CANCELLED", "LOGGER_FAILED"), ("CANCELLED", "LOGGER_FAILED"),
        ])
        jobs = self.connection.execute(
            "SELECT status,locked_at,lock_owner FROM printer_scheduler_jobs ORDER BY id"
        ).fetchall()
        self.assertEqual([tuple(row) for row in jobs], [
            ("CANCELLED", None, None), ("CANCELLED", None, None),
        ])
        self.assertEqual(self.connection.execute(
            "SELECT COUNT(*) FROM printer_proof_run_supervision"
        ).fetchone()[0], 0)
        for table in LOCKED_TABLES:
            with self.subTest(table=table):
                self.assertEqual(self.connection.execute(
                    f"SELECT COUNT(*) FROM {table}"
                ).fetchone()[0], 0)


if __name__ == "__main__":
    unittest.main()
